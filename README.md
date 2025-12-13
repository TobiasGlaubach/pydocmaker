# pydocmaker

a minimal python document maker to create reports in the following formats:

- `pdf`: PDF
- `md`: Markdown
- `html`: HTML
- `json`: JSON
- `docx`:: Word docx
- `textile`: Textile Markup language (with images as attachments)
- `ipynb`: Jupyter/ IPython Notebooks
- `tex`: Latex Documents (with external images)
- `redmine`: Textile Markup language ready for uplaod to Redmine 


Written in pure python 
**NOTE:** some functions will try to call pandoc and fall back if not found.
**NOTE:** exporting PDFs need a latex compiler such as pdflatex, lualatex, xelatex


## Installation

Install via:

```bash
pip install pydocmaker
```


## TL;DR;

### Snippet:

```python

import pydocmaker as pyd

doc = pyd.Doc.get_example()
doc.show()
```

### Minimal Usage Example:

```python

import pydocmaker as pyd

doc = pyd.Doc() # basic doc where we always append to the end
doc.add('dummy text') # adds raw text

# this is how to add parts to the document
doc.add_pre('this will be shown as preformatted') # preformatted
doc.add_md('This is some *fancy* `markdown` **text**') # markdown
doc.add_tex(r'\textbf{Hello, LaTeX!}') # latex

# this is how to add an image from link
doc.add_image("https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png", caption='', children='', width=0.8)

doc.show()
```

### Showing Documents in iPython

the Doc class has a method called show which will detect if it is running in Ipython. If it does it will render the document and show it. 
The desired rendering format can be set with the `engine` argument. Markdown, HTML, or PDF is possible. 

In Ipython:

```python
doc.show('md')
```
Or: 
```python
doc.show('html')
```
Or (**NOTE**: some IDEs do not support this and instead open a "save" dialog, but in a browser with jupyter this works): 
```python
doc.show('pdf')
```


### Exporting:

export via:

```python
# returns string
text_html = doc.export('html')
# or write a file
doc.export('path/to/my_file.html')
```

Or alternatively:

```python
doc.to_html('path/to/my_file.html') # will write a HTML file
doc.to_pdf('path/to/my_file.pdf') # will write a PDF file
doc.to_pdf('path/to/my_file.zip') # will write the whole latex project dir as a pdf file
doc.to_markdown('path/to/my_file.md') # will write a Markdown file
doc.to_docx('path/to/my_file.docx') # will write a docx file
doc.to_textile('path/to/my_file.textile.zip') # will pack all textile files and write them to a zip archive
doc.to_tex('path/to/my_file.tex.zip') # will pack all tex files and write them to a zip archive
doc.to_ipynb('path/to/my_file.ipynb') # will write a ipynb file

doc.to_json('path/to/doc.json') # saves the document
```
### Writing Word docx Documents with templates and fields

Below is an example on how to use pydocmaker to write word docx documents from format templates
and also automatically "replace" fields (MergeFields in Word or plain text) to be filled out in 
the docx document with text from python.

(NOTE: some of the code below utilized the win32com api and only works on windows)

```python 
import pydocmaker as pyd

# this is some fields in my template which I want to populate automatically
metadata = {
    'repno': "1234",
    "summary": "This is a nice workflow for automatically creating docx documents",
    "date": "2025-12-13",
    "comment": f"this works!",
    "author": "Me"
}

templatepath = 'my/path/template.docx'
outpath = 'my/path/outfile.docx'

# get a pyd example document to combine with my doxc template
docx_bts = pyd.get_example().to_docx()

print('replacing keywords...')
# HOWTO: 
#  Adding MergeFields In Word to replace them later: 
#    Go to Insert -> Quick Parts -> Field -> MergeField.
template = pyd.docx_replace_fields(templatepath, metadata)

# Alternative calls working with plain strings as keywords to replace 
# -- see the function documentation for info
# template = pyd.docx_replace_keywords_raw(template, metadata)
# template = pyd.docx_replace_keywords(template, metadata)

# merge two or more documents by appending them
docx_bts = pyd.docx_merge(template, docx_bts)

# save out file
with open(outpath, "wb") as fp:
    fp.write(docx_bts)

# use the win32com.client api with word to update all fields 
# like the table of contents in the document after we changed it

# WARNING! only works in windows and with word installed
pyd.docx_update_w32(outpath)


print(outpath)

```


### Uploading to Redmine

upload to redmine via:

```python
import redminelib
redmine = redminelib.Redmine('https://your-redmine-instance.com', key='your_redmine_token')
page = doc.to_redmine_upload(redmine, 'your-test-project')
```
### Using Template Folders

pydocmaker supports mounting Jinja2 Templates organized in folders together with (optional) default parameters and assets. Suppose you have the following folder structure 

```
home/jovyan/templates/
├─ assets/
│  ├─ i_can_use_this_everywhere.png
├─ fancy_tempate.assets/
│  ├─ fancy_logo.png
│  ├─ fancy_title_picture.png
├─ fancy_template.params.json
├─ fancy_template.tex.j2
├─ normal_template.params.json
├─ normal_template.tex.j2
```

(NOTE: you can also check out the `templates` folder in this repository for an example).

You can then mount this folder in pydocmaker using 

```python
pyd.register_new_template_dir(r'home/jovyan/templates/')
```

Which will give you two available templates to use for exporting tex and pdf documents: 


```python
print(pyd.get_available_template_ids())
```
`>>> ["fancy_template", "normal_template"]`



You can mark the templates to be used for a doc by setting it to the reports metadata:
```python
import pydocmaker as pyd
doc = pyd.get_example()
doc.set_template_to_meta('fancy_template')
```

which will write all needed data to the documents "metadata". Specifically:
- `template_id` will hold the id with which the specific template can be loaded. In our case it will be `fancy_template`.
- `files_to_upload` will hold all assets as base64 encoded bytes in our case the following files:
   - **key**: `fancy_logo.png` **value** content from `.../fancy_tempate.assets/fancy_logo.png`
   - **key**: `fancy_title_picture.png` **value** content from `.../fancy_tempate.assets/fancy_title_picture.png` 
    - **key**: `i_can_use_this_everywhere.png` **value** content from `.../assets/i_can_use_this_everywhere.png` (content from `assets` will be made available shared for all templates)
- and all other fields loaded from `fancy_template.params.json` will be loaded to the metadata dictionary directly. 

If you thereafter export your document to pdf (or html if you have an html type template), pydocmaker will automatically load the template and render it with parameters, attachments and your document as the body. 

you can view the template and params by 
```python
print(doc.get_meta())
```

and change them by:

```python
doc.update_meta(author='Me!')
```


### Using Jinja2 Templates Directly for Exporting to HTML or PDF

you can also use Jinja2 Templates directly to make HTML or PDF (latex) documents. An example is given below:

```python

# This is a minimal template, the document will be written to the "body" part.
template_string = r'''
\documentclass[a4paper]{article}

{% if title %}\title{{ title }}{% endif %}
{% if author %}\author{{ author }}{% endif %}

\begin{document}

{{ body }}

\end{document}
'''

from jinja2 import Environment, FileSystemLoader
import pydocmaker as pyd

# Create a Template object
template = Template(template_string)

doc = pyd.get_example()
pdf_bytes = doc.to_pdf(template=template, template_params=dict(title='My Title', author='Me'))

```

**NOTE**: If your document template has external references such as logos, you need to load them to a bytes array and pass them as a filename, content dictionary into the to_pdf(...) methods using the `files_to_upload` argument.


```python
assets = {}
with open('my_logo.png', 'rb') as fp:
    assets = {'my_logo.png': fp.read()} 

pdf_bytes = doc.to_pdf(template=template, template_params=dict(title='My Title', author='Me'), files_to_upload=assets)

```
___

## Detailed Usage Instructions

Given here is a brief overview. See the ipython notebooks within the `examples` folder within this repository for more detailed usage examples. 

## Document Builder

The `DocBuilder` class from `pydocmaker` is the basic building element for making a report. Here each element will be appended to the end of the document if no `index` or `chapter` is given. Alternatively the chapter to which to append a document part can be specified by `chapter='xxx'`. Furthermore you can also specify the index position (after which part of the document to insert) by adding `index=i` where `i` is `int`. You can use the object like a list.



## Document Parts and Schema for them

The basic building blocks for a document are called `document parts` and are always either of type `dict` or type `str` (A string will automatically parsed as a text dict element). 

Each document part has a `typ` field which states the type of document part and a `children` field, which can be either `string` or `list`. This way hirachical documents can be build if needed. 

The `document-parts` are:
- `text`: holds text as string (`children`) which will inserted directly as raw text
- `markdown`: holds text as string (`children`) which will be rendered by markdown markup language before parsing into the documents
- `image`: holds all needed information to render an image in a report. The image data is saved as a string in base64 encoded format in the `imageblob` field. A `caption` (str) can be given which will be inserted below the image. The filename is given by the `children` field. The relative width can be given by the `width` field (float). 
- `verbatim`: holds text as string (`children`) which will be inserted as preformatted text into the documents
- `iter`: a meta `document-part` which holds n sub `document-parts` in the `children` field which will be rendered and inserted into the documents in given order. 

An example of the whole schema is given below.

```json
{
  "text":     {"typ": "text", "children": ""},
  "markdown": {"typ": "markdown", "children": ""},
  "image":    {"typ": "image", "children": "", "imageblob": "", "caption": "", "width": 0.8},
  "verbatim": {"typ": "verbatim", "children": ""},
  "iter":     {"typ": "iter", "children": [] }
}
```


### Adding document parts to a doc

Alternatively you can add elements to a document directly using the add and add_kw methods of the document builders:


```python

import pydocmaker as pyd

doc = pyd.DocBuilder()
doc.add('dummy text')
doc.add({"typ": "markdown","children": "some dummy markdown text!"})
doc.add_kw('verbatim', 'this text will be shown preformatted!')
doc.add_image('https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png', caption='', children='', width=0.8)

doc.show()

```

You can also combine the two:

```python

import pydocmaker as pyd
import numpy as np

doc = pyd.DocBuilder()
doc.add('dummy text')

doc.show()

```

### Working with Images

Image from pyplot figure

```python
doc = pyd.DocBuilder()
doc.add(pyd.constr.image_from_fig(caption='test figure', fig=fig))
```

Image from link

```python
doc = pyd.DocBuilder()
doc.add(pyd.constr.image_from_link("https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png"))
```

Image from numpy array 

```python
import numpy as np
m = np.array([np.arange(255).astype(np.uint8).tolist() for i in range(255)], dtype=np.uint8)
doc = pyd.DocBuilder()
doc.add(pyd.constr.image_from_obj(m, caption = 'numpy generated image', width=0.8, name=None))
```

### Adding to Specific Chapters

as said above you can also add elements to specific chapters or locations. below is an example


```python
doc = pyd.DocBuilder()

# this will add a section 'Introduction'
doc.add_section('Introduction')

# now I can add / access the section (which is a DocBuilder) direcly like a dict
doc.add('dummy text which will be added to the introduction', chapter='Introduction')

# this will add the section 'Weather Info' and add a markdown element to it
doc.add_kw('markdown', 'This is my fancy `markdown` text for the Second Chapter', 
           chapter='Second Chapter')

# I can also add parts to the Introduction like this
doc.add_kw('markdown', 'This text will be appended to the first section after the 2nd element (`index` is zero based!), which is the text (the chapter definition itself is the 1st element!)', 
           index=1)

# and like this
doc.add_image("https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png", 
              chapter='Second Chapter')


doc.show()
```


### Upload to Redmine as Wiki Page

This is how to upload to redmine (assumes `doc` exists as generated in any of the above examples)

```python
import redminelib, datetime

text_textile, attachments_lst = doc.to_redmine()
redmine = redminelib.Redmine('https://your-redmine-instance.com', key='my_token')

page = redmine.wiki_page.new()
page.project_id = 'myproject'
page.title = 'My Wiki Page'

page.text = text_textile
page.uploads = attachments_lst
page.comments = f'updated at {datetime.datetime.utcnow().isoformat()}'
page.save()
```

### Constructing Document Parts using the `constr` factory

`document-parts` are under the hood constructed using the `constr` class which is basically a factory for `document-parts`

```python

import pydocmaker as pyd
import numpy as np

docpart = pyd.constr.markdown(children='')
docpart = pyd.constr.text(children='')
docpart = pyd.constr.verbatim(children='')
docpart = pyd.constr.iter(children=[])
docpart = pyd.constr.image(imageblob='', caption='', children='', width=0.8)
docpart = pyd.constr.image_from_link(url='https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png', caption='', children='', width=0.8)
docpart = pyd.constr.image_from_file(path='path/to/your_file.png', children='', caption='', width=0.8)
docpart = pyd.constr.image_from_fig(caption='', width=0.8, name=None, fig=None)
docpart = pyd.constr.image_from_obj(np.array(np.arange(255).tolist() * 255, dtype="uint8"), caption = '', width=0.8, name=None)
```

you can also combine adding and the functionality from above:

```python 
import pydocmaker as pyd
doc.add(pyd.constr.image_from_link("https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png"))
```

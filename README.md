# pydocmaker

<div align="center">

![Icon](icon.png)

</div>

Please find the full documentation at https://pydocmaker.readthedocs.io/en/latest/

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


## TL;DR; Code examples

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


### Install Optional Requirements


#### Optional Requirement `pandoc`

In order to get all functionality `pandoc` needs to be available. Please follow the recommended installation steps on the software projects webpage. For convenience the minimal installation is listed here:

On Linux (Debian/Ubuntu) install via: 

```bash
sudo apt update
sudo apt install pandoc
```

On MacOS: 

```bash
brew install pandoc
```

On Windows: 

```bash
winget install JohnMacFarlane.Pandoc
```


### Optional Requirement `Latex`

In order to get all functionality a latex compiler needs to be available. Please follow the recommended installation steps on the webpage. For convenience the minimal installation is listed here:

On Linux (Debian/Ubuntu) install via: 

```bash
sudo apt update
sudo apt install texlive-full
```

On MacOS: @git

```bash
brew install --cask mactex
```

On Windows:

```bash
winget install MiKTeX.MiKTeX
```

### Optional Requirement for DOCX either `libreoffice` or `win32com`


Some DOCX functionality need either Microsoft Windows and Microsoft Word and the `win32com` library or `libreoffice` available. 


#### Installing `pywin32` (Windows only)

Install via: 
```bash
pip install pywin32
```

#### Installing `libreoffice`

On a Linux (Debian/Ubuntu) system insall via:

```bash
sudo apt update
sudo apt-get install libreoffice
```

On MacOS: 

```bash
brew install --cask libreoffice
```

On Windows:

**NOTE**: You need to add 

```bash
winget install TheDocumentFoundation.LibreOffice
```

### Writing Word docx Documents with templates and fields

Below is an example on how to use pydocmaker to write word docx documents from format templates
and also automatically "replace" fields (MergeFields in Word or plain text) to be filled out in 
the docx document with text from python.

(**NOTE**: some of the code below utilized the ``win32com`` api and only works on windows)

prepare a report, a template and some fields in the template:

```python

import pydocmaker as pyd

metadata = {
    'repno': "1234",
    "summary": "This is a nice workflow for automatically creating docx documents",
    "date": "2025-12-13",
    "comment": f"this works!",
    "author": "Me"
}

# HOWTO: 
#  Adding MergeFields In Word to replace them later: 
#    Go to Insert → Quick Parts → Field → MergeField.
templatepath = 'my/path/template.docx'
outpath = 'my/path/outfile.docx'

# get a pyd example document to show the concept
doc = pyd.get_example()

```

this is the quick and easy way using the common pydocmaker api:

```python
# three different examples below
docx_bts = doc.to_docx("my/path/outfile.docx", template=templatepath, template_params=metadata, use_w32=False)
docx_bts = doc.to_docx("my/path/outfile_w32.docx", template=templatepath, template_params=metadata, use_w32=True)
docx_bts = doc.to_docx("my/path/outfile_w32_comp.pdf", template=templatepath, template_params=metadata, use_w32=True, as_pdf=True, compress_images=True)
```



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

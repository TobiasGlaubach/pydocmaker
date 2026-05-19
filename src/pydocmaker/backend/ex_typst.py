import base64, time, io, copy, json, traceback, hashlib, markdown, re
import warnings
from typing import List, Union
import json

try:
    from pydocmaker.backend.baseformatter import BaseFormatter, _handle_template
except Exception as err:
    from .baseformatter import BaseFormatter, _handle_template
    
try:
    from pydocmaker import util
except Exception as err:
    from .. import util


    
try:
    from pydocmaker import b64_data
except Exception as err:
    from .. import b64_data


try:
    from pydocmaker.backend.pandoc_api import can_run_pandoc, pandoc_convert, pandoc_convert_file
except Exception as err:
    from .pandoc_api import can_run_pandoc, pandoc_convert, pandoc_convert_file

import logging

# Configure once
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s | %(levelname)-8s | %(filename)-15s:%(lineno)3d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

log = logging.getLogger(__name__)


__paper_template = """


#show link: set text(fill: blue, weight: 700)
#show link: underline
//#show table.cell.where(y: 0): set text(weight: "bold")

// code blocks
#let code-border = luma(0)
// #show raw: set text(font: (fonts.mono), fallback: true)
#show raw.where(block: false): set text(weight: "semibold")
#show raw.where(block: true): set text(size: 0.8em)
#show raw.where(block: true): it => {
    block(
        width:100%,
        inset: 10pt,
        radius: 4pt,
        stroke: 0.1pt + code-border,
        it,
    )
}

#set figure(numbering: "1")
#set figure.caption(separator: " - ") // With a nice separator
#set math.equation(numbering: "(1)", supplement: "Eq.")


#set document(title: [ {{ title }} ])
#let conf(
  authors: (),
  abstract: [],
  doc,
) = {
  // Set and show rules from before.
  ...

  place(
    top + center,
    float: true,
    scope: "parent",
    clearance: 2em,
    {
      title()

      let count = authors.len()
      let ncols = calc.min(count, 3)
      grid(
        columns: (1fr,) * ncols,
        row-gutter: 24pt,
        ..authors.map(author => [
          #author.name \
          #author.affiliation \
          #link("mailto:" + author.email)
        ]),
      )

      par(justify: false)[
        *Abstract* \
        #abstract
      ]

    }
  )

  doc
}

#set document(title: [
  A Fluid Dynamic Model for
  Glacier Flow
])

#show: conf.with(
  authors: (
    (
      name: "Theresa Tungsten",
      affiliation: "Artos Institute",
      email: "tung@artos.edu",
    ),
    (
      name: "Eugene Deklan",
      affiliation: "Honduras State",
      email: "e.deklan@hstate.hn",
    ),
  ),
  abstract: lorem(80),
)

"""

__default_template = """
#import "@preview/based:0.2.0": base64

#set page(paper: "a4")
#set heading(numbering: "1.")


#show link: set text(fill: blue, weight: 700)
#show link: underline
//#show table.cell.where(y: 0): set text(weight: "bold")

// code blocks
#let code-border = luma(0)
// #show raw: set text(font: (fonts.mono), fallback: true)
#show raw.where(block: false): set text(weight: "semibold")
#show raw.where(block: true): set text(size: 0.8em)
#show raw.where(block: true): it => {
    block(
        width:100%,
        inset: 10pt,
        radius: 4pt,
        stroke: 0.1pt + code-border,
        it,
    )
}

#set figure(numbering: "1")
#set figure.caption(separator: " - ") // With a nice separator
#set math.equation(numbering: "(1)", supplement: "Eq.")

//-------------------------------------
// Metadata of the document
//
#let doc= (
{% if title %}
  title    : [*{{ title }}*],
{% endif %}
  

{% if authors %}
  authors: (
{% for author in authors %}
    (
      name        : [{{ author }}],
    ),
{% endfor %}
  ),
{% elif author %}
  authors: (
    (
      name        : [{{ author }}],
    ),
  ),
{% endif %}

  keywords : ("Typst", "Template", "Report", "pydocmaker"),
  version  : "v0.1.0",
)

//-------------------------------------
// Settings
//
{% if date %}
#let date= "{{ date }}"
{% else %}
#let date= datetime.today()
{% endif %}

#let logo_b64 = "{{ logo_b64 }}"

#set page(
// Increase the top margin so the body text starts lower down
  margin: (top: 6.5cm, bottom: 2.5cm, left: 2.5cm, right: 2.5cm),
  
  // This defines the size of the header box, preventing it from clipping the top
  header-ascent: 3.5cm,

  header: context {
  let current = counter(page).get().first()
  let total = counter(page).final().first()
  
  // 1. Give the header content a tiny bit of top clearance if needed
  v(5pt)
  
  // 2. The main grid. Notice 'align: bottom' added right here!
  grid(
    columns: (auto, 1fr, auto), // Changed middle column to 1fr so it spaces out nicely
    align: bottom,              // Forces all 3 columns to align perfectly at their baselines
    gutter: 10pt,               // Keeps the columns from bumping into each other

    
    // COLUMN 1: INSTITUTION & TITLE
    [
      #table(
        columns: (100%),
        stroke: none,
        inset: 0pt, // Keeps formatting tight
        {% if institution %}[*{{ institution }}*],{% endif %}
        {% if title %}[#text(size: 0.8em)[{{ title }}]],{% endif %}
        {% if project %}[#text(size: 0.8em)[{{ project }}]],{% endif %}
      )
    ],
    [],
    // COLUMN 2: METADATA
    [
      #text(size: 0.8em)[
        #grid(
          columns: (auto, auto),
          gutter: 3pt,
          {% if doc_no %}[Doc \#:], [{{ doc_no }}],{% endif %}
          {% if revision %}[Rev.:], [{{ revision }}],{% endif %}
          {% if status %}[Status:], [{{ status }}],{% endif %}
          [Date:], [#date.display()],
          [Page:], [#current / #total],
        )
      ]
    ],
  )

  // 3. Spacing between your bottom-aligned grid and the divider line
  v(5pt) 
  line(length: 100%, stroke: 0.4pt)
},
  {% if footer_str_left or footer_str_right %}
  footer: context {
    line(length: 100%, stroke: 0.4pt)
    grid(
      columns: (1fr, 1fr),
      [{{ footer_str_left | default('') }}],
      align(right)[{{ footer_str_right | default('') }}]
    )
  }
  {% endif %}
)

{% if title %}
= {{ title }}
{% endif %}
  




{% if applicables or references or acronyms %}


// #let terms = ({{ terms | join(', ') }})

// #let pattern = "\\b(" + terms.join("|") + ")\\b"

// #show regex(pattern): it => {
  // Use lower() to ensure "Servo" and "servo" both point to <servo>
  // link(label(lower(it.text)))[#it]
// }

== References
{% endif %}

{% if acronyms %}

=== List of Acronyms

#table(
  columns: (auto, 1fr),
  stroke: none,
{% for key, value in acronyms.items() %}
   [*{{ key }}:* <{{key}}>], [{{ value }}],
{% endfor %}
)

{% endif %}


{% if applicables %}

=== Applicable Documents

#table(
  columns: (auto, 1fr),
  stroke: none,
{% for (key, value) in applicables.items() %}
   [*AD{{ loop.index }}:* <{{key}}>], [{{ value }}],
{% endfor %}
)

{% endif %}

{% if references %}
=== Reference Documents


#table(
  columns: (auto, 1fr),
  stroke: none,
{% for (key, value) in references.items() %}
   [*RD{{ loop.index }}:* <{{key}}>], [{{ value }}],
{% endfor %}
    
)
{% endif %}

{{ body }}

"""


_table_template = """
#figure(
table(
    columns: {n_cols:},
    stroke: {stroke:},
    align:(left+horizon),
    {header:}
    {rows:}
),
{suffix:}
) <{name:}>

"""

_figure_template = """
#figure(
  image(base64.decode({name:}), {width:} format: "{ext:}"),
  {suffix:}
) <{name:}>
"""

DATA_URI_IMAGE_RE = re.compile(
    r'^\s*data:image/(?P<mime>[A-Za-z0-9.+-]+)\s*;\s*base64\s*,\s*(?P<data>[A-Za-z0-9+/=\s]+)\s*$',
    re.IGNORECASE,
)

def test_typst_installed():
    try:
        import typst
        return True
    except ImportError:
        return False

def to_typst_string(text):
    # Escape backslashes first, then double quotes, then newlines
    safe_text = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{safe_text}"'

def compile_with_typst(typst_code: Union[str, List[dict]], output: str = None, verb=1, on_warning='warn', format=None, **kwargs):
    try:
            
        import typst

        if not isinstance(typst_code, str):
            typst_code = convert(typst_code)

        typst_code = typst_code.encode('utf-8')
        
        format = format or ''

        ext = None
        if output and '.' in output:
            ext = output.rsplit('.', 1)[-1].lower()
        elif format:
            ext = format.lower()
        else:
            ext = 'pdf'
        
        if on_warning is None:
            on_warning = 'ignore'

        kw = {
            'input': typst_code,
            'output': output,
            'format': ext,
            **kwargs
        }
        if verb:
            logging.info(f'Compiling typst document to {output} format {ext} with typst compiler...')
            res, warns = typst.compile_with_warnings(**kw)

            if warns:
                s = f'Typst compilation finished with warnings.'
                for i, warn in enumerate(warns, 1):
                    s += f'\n\nWARNING {i}: {warn.message}\nDiagnostic: {warn.diagnostic}'
                    if warn.hints:
                        s += '\nHints:\n' + '\n'.join(warn.hints)
                    if warn.trace:
                        s += '\nTrace:\n' + '\n'.join(warn.trace)

                if on_warning == 'warn':
                    warnings.warn(s)
                elif on_warning == 'raise':
                    raise RuntimeError(s)
                elif on_warning == 'log' or on_warning == 'logging':
                    log.warning(s)
                elif on_warning == 'print':
                    print(s)
                else:

                    logging.info(f'Compiling typst document... success')
        
        else:
            res = typst.compile(**kw)
    except ImportError as err:
        log.error(f'Typst is not installed: {err}', exc_info=1)
        raise

    except typst.TypstError as err:
        sshort = f'Typst failed with error:\n- ERROR: {err.message}\n- Diagnostic:\n{err.diagnostic}'
        s = sshort
        if err.hints:
            s += '\nHints:\n' + '\n'.join(err.hints)
        if err.trace:
            s += '\nTrace:\n' + '\n'.join(err.trace)
        log.error(s, exc_info=1)
        raise 

    return res

# def _typstraw():
#     import typst
#     compiler = typst.Compiler()
#     compiler.compile(input="hello.typ", format="png", ppi=144.0)

def convert(doc:List[dict], template = None, template_params=None, **kwargs):

    if not template_params:
        template_params = {}

    unknown_params = kwargs
    if unknown_params:
        warnings.warn(f'Unknown parameters passed: {unknown_params=}')


    formatter = DocumentTypstFormatter()
    tmp = list(doc.values()) if isinstance(doc, dict) else doc
    body = formatter.digest(tmp)

    template_obj, attachments = _handle_template(template, __default_template)
    


    kw = copy.deepcopy(template_params)
    libraries = kw.pop("libraries", [])
    libraries.extend(formatter.libraries)

    if not 'logo_b64' in kw:
        kw['logo_b64'] = b64_data.logo_b64    

    terms = list(template_params.get('applicables', {})) + list(template_params.get('references', {})) + list(template_params.get('acronyms', {}))

    if terms:
        if "terms" in kw:
            kw['terms'].extend(terms)
        else:
            kw['terms'] = terms
    
    if 'terms' in kw:
        # ensure all terms are properly escaped etc. for typst
        kw['terms'] = [json.dumps(term) for term in set(kw['terms'])]
    
    if 'authors' in kw:
        # ensure all authors are properly escaped etc. for typst
        kw['authors'] = [json.dumps(author) for author in kw['authors']]

    if 'author' in kw:
        kw['author'] = json.dumps(kw['author'])

    assert not ('body' in kw), f'the "body" keyword is an invalid keyword for templates as it is reserved for the document body.'
    
    if libraries:
        b = ('\n'.join(libraries) + '\n\n' + body)
    else:
        b = body
    kw['body'] = b
    
    # typst can handle named references, so we can directly pass the dict to the template
    # if 'applicables' in kw:
    #     kw['applicables'] = {i:v for i, v in enumerate(kw['applicables'].values(), 1)} 
    # if 'references' in kw:
    #     kw['references'] = {i:v for i, v in enumerate(kw['references'].values(), 1)} 

    try:
        doc_typst = template_obj.render(**kw)
    except Exception as err:
        s = f'Error while rendering the typst template: {err}'
        log.error(s)
        log.error(traceback.format_exc())
        raise 

    return doc_typst



class DocumentTypstFormatter(BaseFormatter):

    def __init__(self) -> None:
        self.cnt_img = 0
        self.cnt_tables = 0
        self.libraries = set()


    def _handle_color(self, part, color=None, **kwargs):
        if color:
            s = '#text(fill: ' + color + ')[\n' + str(part) + '\n]\n'
            return s
        else:
            return part
        

    def digest_latex(self, children: str, **kwargs):
        s = None
        if can_run_pandoc():
            try:
                s = pandoc_convert(children, 'latex', 'typst')
                return self._handle_color(s, **kwargs)
            except Exception as err:
                s = 'Can not convert latex to typst! Embedding the latex code verbatim...\n\n'
        else:
            s = 'Pandoc is not available to convert latex to typst! Embedding the latex code verbatim...\n\n'
        
        s += self.digest_verbatim(children=children, lang='latex', **kwargs)
        return self._handle_color(s, 'orange')

    def digest_markdown(self, children='', **kwargs) -> list:
        s = None
        if can_run_pandoc():
            try:
                s = pandoc_convert(children, 'markdown', 'typst')
            except Exception as err:
                pass

        if s is None:
            self.libraries.add('#import "@preview/cmarker:0.1.8"')
            self.libraries.add('#import "@preview/mitex:0.2.6": mitex')
            safe_markdown = json.dumps(children) # escape all chars etc. and put quotes around it
            s = f'#cmarker.render({safe_markdown}, math: mitex)'
            
        return self._handle_color(s, **kwargs)
    
    def digest_text(self, children='', **kwargs):
        return self._handle_color(children, **kwargs)
    
    def digest_table(self, children=None, **kwargs) -> str:

        borders = kwargs.pop('borders', None)
        if borders is None:
            borders = True
        caption = kwargs.pop('caption', '')
        if not caption:
            caption = ''

        name = kwargs.pop('name', None)

        suffix = ' ' + f'caption: [{caption}],' if caption else ''
        stroke = '0.5pt + rgb("666675")' if borders else "none"

        head, mat = self._map_table2mat(children=children, **kwargs)

        n_cols = len(mat[0]) if mat else (len(head) if head else 0)
        n_rows = len(mat)
        to_row = lambda row: ', '.join([f'[{s}]' for s in row])

        header = f"table.header({to_row(head)})," if head else ''
        rows = ',\n'.join([to_row(row) for row in mat])

        self.cnt_tables += 1
        name = f'table_{self.cnt_tables}' if not name else util.filename2identifier(name)
        body = _table_template.format(n_cols=n_cols, n_rows=n_rows, stroke=stroke, header=header, rows=rows, suffix=suffix, name=name)
        
        return self._handle_color(body, **kwargs)

   
            

    def digest_image(self, **kwargs) -> list:
        
        filename = kwargs.get('filename')
        caption = kwargs.get('caption')
        imageblob = kwargs.get('imageblob')
        name = kwargs.get('name', filename)
        width = kwargs.get('width', None)
        
        if name:
            name = util.filename2identifier(name)
        else:
            name = f'image_{self.cnt_img+1}'
        
        description = caption or filename
        if width is None:
            width = ''
        elif isinstance(width, (int, float)):
            width = f'width: {int(width*100)}%,'
        elif isinstance(width, str):
            width = width
        else:
            width = str(width)


        suffix = ' ' + f'caption: [{description}],' if description else ''
        self.libraries.add('#import "@preview/based:0.2.0": base64')

        imageblob_str = imageblob.decode('utf-8') if isinstance(imageblob, bytes) else str(imageblob)
        mime_match = DATA_URI_IMAGE_RE.fullmatch(imageblob_str)
        if mime_match:
            ext = mime_match.group('mime').lower()
            b64data = mime_match.group('data').replace('\n', '').replace('\r', '')            
        elif filename and '.' in filename:
            _, ext = filename.rsplit('.', 1)
            ext = ext.lower()
            b64data = imageblob_str.strip()
        else:
            ext = 'png'
            b64data = imageblob_str.strip()

        lines = ['']
        lines.append(f'#let {name} = "{b64data}"')
        lines.append('')
        lines.append(_figure_template.format(name=name, ext=ext, width=width, suffix=suffix))
        lines.append('')

        self.cnt_img += 1

        s =  '\n'.join(lines)
        return self._handle_color(s, **kwargs)
    

    def digest_verbatim(self, children='', **kwargs) -> list:
        lang = kwargs.pop('lang', kwargs.get('language', None))

        if lang is None:
            lang = ''
        else:
            lang = f'"{str(lang).strip()}"'


        if isinstance(children, str):
            txt = children.strip('\n') # to_typst_string(children) #.strip('\n')
        else:
            txt = self.digest(children)
        
        s = f"""```{lang}\n{txt}\n```"""
        # s = f'\n#raw(`{}`, block: true, lang: {lang})\n\n'
        
        return self._handle_color(s, **kwargs)
    
        

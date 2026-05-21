import os
from pathlib import Path
import base64, time, io, copy, json, traceback, hashlib, markdown, re
import warnings
from typing import List, Union
import json
import tempfile

try:
    from pydocmaker.backend.baseformatter import BaseFormatter, _handle_template
except Exception as err:
    from .baseformatter import BaseFormatter, _handle_template
    
try:
    from pydocmaker import util
except Exception as err:
    from .. import util

try:
    from pydocmaker import templating
except Exception as err:
    from .. import templating

    
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


__default_template = """

#set page("a4")

#show link: set text(fill: blue, weight: 700)
#show link: underline

// code blocks
#let code-border = luma(0)
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

{{ body}}

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


def _compile(verb, on_warning, **kw):
    inp = kw.get('input', None)
    if isinstance(inp, dict):
        # check if we have any binary content
        if [k for k, v in inp.items() if k != 'main.typ' and not isinstance(v, (str, Path))]:
            logging.info(f'found attachments that need to be passed as files compiling typst in temporary dictionary...')
            with tempfile.TemporaryDirectory() as tempdir:
                p = Path(tempdir)

                newinp = {}
                for k, v in inp.items():
                    fp = (p / k)
                    with open(fp, 'wb') as f:
                        f.write(v) if isinstance(v, bytes) else f.write(v.encode('utf-8'))
                    newinp[k] = fp
                
                kw['input'] = {'main.typ': newinp['main.typ']}
                kw.pop('root') # remove root as we are now in tempdir # NOTE: this could be a bit problematic if we have unknown files in base_dir
                return _compile(verb, on_warning, root=str(tempdir), **kw)


    import typst
    try:
        if verb:
            logging.info(f'Compiling typst document to {kw.get("output", "N/A")} format {kw.get("format", "N/A")} with typst compiler...')
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

def compile_with_typst(typst_code: Union[str, List[dict]], output: str = None, verb=1, on_warning='warn', format=None, attachments=None, **kwargs):

    if not isinstance(typst_code, str):
        typst_code = convert(typst_code)

    # Keep typst_code as string; typst.compile expects str values in files dict
    
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

    if attachments is None:
        attachments = {}

    files_to_upload = kwargs.pop('files_to_upload', {})

    if files_to_upload:
        attachments.update(files_to_upload)

    for k in attachments:
        if isinstance(attachments[k], str) and os.path.exists(attachments[k]):
            attachments[k] = Path(attachments[k])
        elif isinstance(attachments[k], Path) and attachments[k].exists():
            pass
        # Keep strings as strings (typst will handle them as text files)
        # Keep bytes as bytes (typst will handle them as binary files)
    
    if attachments:
        files = {
            "main.typ": typst_code,
            **attachments,
        }
    else:
        files = typst_code


    kw = {
        'input': files,
        'output': output,
        'format': ext,
        **kwargs
    }
        
    return _compile(verb, on_warning, **kw)

# def _typstraw():
#     import typst
#     compiler = typst.Compiler()
#     compiler.compile(input="hello.typ", format="png", ppi=144.0)

def convert(doc:List[dict], template = None, template_params=None, ret_attachments=False, **kwargs):

    if not template_params:
        template_params = {}

    unknown_params = kwargs
    if unknown_params:
        warnings.warn(f'Unknown parameters passed: {unknown_params=}')


    formatter = DocumentTypstFormatter()
    tmp = list(doc.values()) if isinstance(doc, dict) else doc
    body = formatter.digest(tmp)

    template_obj, attachments, template_str = _handle_template(template, __default_template)
    
    try:
        dt = templating.DocTemplate(template_str)
        expected_variables = dt.find_undeclared_variables()
    except Exception as err:
        log.warning(f'failed to extract expected_variables from template: {err} will continue without expected_variables')
        expected_variables = set()


    kw = copy.deepcopy(template_params)
    libraries = kw.pop("libraries", [])
    libraries.extend(formatter.libraries)

    if not 'logo_b64_pydocmaker' in kw and (not expected_variables or 'logo_b64_pydocmaker' in expected_variables):
        kw['logo_b64_pydocmaker'] = b64_data.logo_b64_pydocmaker    

    if not 'version' in kw and (not expected_variables or 'version' in expected_variables):
        if 'revision' in kw and not 'revision' in expected_variables:
            kw["version"] = f'Revision {kw["revision"]}'

    terms = list(template_params.get('applicables', {})) + list(template_params.get('references', {})) + list(template_params.get('acronyms', {}))

    if terms:
        if "terms" in kw:
            kw['terms'].extend(terms)
        else:
            kw['terms'] = terms
    
    if 'terms' in kw:
        # ensure all terms are properly escaped etc. for typst
        kw['terms'] = [json.dumps(term) for term in set(kw['terms'])]


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
        # {{ body }} was not part of the template... just append it to the end
        if not b in doc_typst:
            doc_typst += '\n\n' + b

    except Exception as err:
        s = f'Error while rendering the typst template: {err}'
        log.error(s)
        log.error(traceback.format_exc())
        raise 
    
    if ret_attachments:
        return doc_typst, attachments
    else:
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

        if head:
          head = [f'#strong[{s}]' for s in head]
          header = f"table.header({to_row(head)}),"
        else:
          header = ''
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
    
        

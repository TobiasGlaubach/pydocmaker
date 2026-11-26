import os
from pathlib import Path
import base64, time, io, copy, json, traceback, hashlib, markdown, re
import warnings
from typing import List, Union
import json
import tempfile


try:
    from pydocmaker.backend.baseformatter import BaseFormatter
except Exception as err:
    from .baseformatter import BaseFormatter

try:
    from pydocmaker.templating import handle_template
except Exception as err:
    from ..templating import handle_template

try:
    from pydocmaker import util
except Exception as err:
    from .. import util

try:
    from pydocmaker import templating
except Exception as err:
    from .. import templating

try:
    from pydocmaker import util
except Exception as err:
    from .. import util

    
try:
    from pydocmaker import b64_data
except Exception as err:
    from .. import b64_data

try:
    from pydocmaker import blocktmpl
except Exception as err:
    from .. import blocktmpl

try:
    from pydocmaker.templating import BlockDocTemplate
except Exception as err:
    from ..templating import BlockDocTemplate

try:
    from pydocmaker.param_mapping import map_legacy_params
except Exception as err:
    from ..param_mapping import map_legacy_params


try:
    from pydocmaker.backend.pandoc_api import can_run_pandoc, pandoc_convert, pandoc_convert_file, pandoc_convert_batch, config_use_pandoc_for_md_render_get
except Exception as err:
    from .pandoc_api import can_run_pandoc, pandoc_convert, pandoc_convert_file, pandoc_convert_batch, config_use_pandoc_for_md_render_get

try:
    from pydocmaker.backend.pandoc_batch import PandocBatchMixin
except Exception as err:
    from .pandoc_batch import PandocBatchMixin

log = util.log


CODLY_LIBS = """#import "@preview/codly:1.3.0": *
#import "@preview/codly-languages:0.1.1": *
#show: codly-init.with()
#codly(languages: codly-languages)
#codly(zebra-fill: none)
#codly(number-format: none) """

__default_template = """

// pydocmaker:parameters:begin
// pydocmaker:param:pTitle
#let pTitle = "My Report"
// pydocmaker:param:pAuthor
#let pAuthor = "Automatically Generated via pydocmaker"
// pydocmaker:param:pDate
#let pDate = ""
// pydocmaker:param:pAcronyms
#let pAcronyms = (:)
// pydocmaker:param:pApplicables
#let pApplicables = (:)
// pydocmaker:param:pReferences
#let pReferences = (:)
// pydocmaker:parameters:end

#set page("a4")
#set document(title: if pTitle != "" { pTitle } else { "untitled" })

#show link: set text(fill: blue, weight: 700)
#show link: underline
#show text.where(fill: green): set text(fill: green.darken(35%))


// code blocks
#let code-border = luma(0)
#show raw.where(block: false): set text(weight: "semibold")
#show raw.where(block: true): set text(size: 0.8em)
#show raw.where(block: true): it => {
    block(
        width: 100%,
        inset: 10pt,
        radius: 4pt,
        stroke: 0.1pt + code-border,
        it,
    )
}

#set figure(numbering: "1")
#set figure.caption(separator: " - ")
#set math.equation(numbering: "(1)", supplement: "Eq.")

#let kv_rows(mydict) = {
    let rows = ()
    for (k, v) in mydict {
        rows.push([#strong[#k]])
        rows.push([#v])
    }
    rows
}

#let render_kvtable(mydict) = table(
    columns: (auto, 1fr),
    stroke: none,
    ..kv_rows(mydict),
)

#if pTitle != "" [
    #heading(level: 1)[#pTitle]
]
#if pAuthor != "" [
    #text(size: 0.9em)[#pAuthor]
]
#if pDate != "" [
    #text(size: 0.9em)[#pDate]
]

#if pAcronyms.len() > 0 [
    #heading(level: 2)[List of Acronyms]
    #render_kvtable(pAcronyms)
]
#if pApplicables.len() > 0 [
    #heading(level: 2)[Applicable Documents]
    #render_kvtable(pApplicables)
]
#if pReferences.len() > 0 [
    #heading(level: 2)[Reference Documents]
    #render_kvtable(pReferences)
]

// pydocmaker:body:begin
Document body placeholder
// pydocmaker:body:end


"""



_table_template = """
#figure(
wrappable(table(
    columns: {n_cols:},
    stroke: {stroke:},
    align:(left+horizon),
    {header:}
    {rows:}
)),
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
DO_REPLACE_HORIZONTALRULE = True
USE_CODELY = True




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


#: typst source patterns that reference external files (group 1 = the
#: reference; single and double quotes are accepted). The function calls
#: appear with or without a leading ``#`` (inside content blocks), so only a
#: word boundary is required.
_TYPST_FILE_REF_RES = (
    re.compile(r'\b(?:image|bibliography|json|yaml|csv|toml|xml)\(\s*["\']([^"\']+)["\']'),
    re.compile(r'\bread\(\s*["\']([^"\']+)["\']'),
    re.compile(r'\binclude\s+["\']([^"\']+)["\']'),
)


def _copy_missing_file_refs(inp, tempdir, orig_root):
    """Copy files referenced by typst sources into the compile tempdir.

    Document content converted from markdown may reference local files by
    their bare name (``#image("icon.png")``). Those references resolve
    relative to the compile root (usually the working directory); when the
    compilation is relocated into a temporary directory (because the input
    contains in-memory content), the files would be lost. This copies every
    referenced file that is not already part of the input from the original
    root into the tempdir so the references resolve.

    Args:
        inp (dict): the compile input mapping (keys = file names).
        tempdir (Path): the compile tempdir (copy destination).
        orig_root (str): the original compile root (copy source base).
    """
    refs = []
    for value in inp.values():
        if isinstance(value, bytes):
            try:
                value = value.decode('utf-8', 'replace')
            except Exception:
                continue
        if not isinstance(value, str):
            continue
        for pattern in _TYPST_FILE_REF_RES:
            refs += pattern.findall(value)
    for ref in dict.fromkeys(r.strip() for r in refs):
        if not ref or ref.startswith('http') or '\\' in ref or '{{' in ref:
            continue
        if ref in inp or (tempdir / ref).exists():
            continue  # already provided with the input
        src = Path(orig_root) / ref
        if not src.is_file():
            continue
        dst = tempdir / ref
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            import shutil
            shutil.copy2(src, dst)
        except OSError as err:
            log.warning(f'could not copy referenced file {src!r} into the '
                        f'typst compile directory: {err}')


def _compile(verb, on_warning, **kw):
    inp = kw.get('input', None)
    if isinstance(inp, (list, zip)):
        inp = dict(inp) # naively try casting to dict

    if isinstance(inp, dict):
        code = inp.get('main.typ', None)

        # handle case of only one input and that being "main.typ"
        if len(inp) == 1 and code:
            if isinstance(code, Path) and code.exists():
                kw['input'] = code.read_bytes()
                return _compile(verb, on_warning, **kw)
            elif isinstance(code, str) and Path(code).exists():
                kw['input'] = Path(code).read_bytes()
                return _compile(verb, on_warning, **kw)
            elif isinstance(code, str):
                kw['input'] = code.encode()
                return _compile(verb, on_warning, **kw)
            
        # Check if any values need to be written to temp files (strings, bytes, or Path objects).
        # The typst Rust library expects Path objects for file paths and tries to canonicalize
        # them. When we pass string or bytes content, it interpretes it as a file path, causing
        # errors. So we always write string/bytes values to temp files first.
        needs_temp = any(not isinstance(v, Path) for v in inp.values())
        
        if needs_temp:
            if verb:
                log.info('found non-path content in input dict, compiling typst in temporary directory...')
            with tempfile.TemporaryDirectory() as tempdir:
                p = Path(tempdir)
                # copy everything to tempdir
                newinp = {}
                context = {}

                for k, v in inp.items():
                    newpath = None
                    if isinstance(v, Path) and v.exists():
                        newpath:Path = (p / k)
                        newpath.parent.mkdir(parents=True, exist_ok=True)
                        newpath.write_bytes(v.read_bytes())

                    elif isinstance(v, bytes) and util.bytes_path_exists(v):
                        v = Path(v.decode())
                        newpath:Path = (p / k)
                        newpath.parent.mkdir(parents=True, exist_ok=True)
                        newpath.write_bytes(v.read_bytes())

                    elif isinstance(v, bytes) and v:
                        newpath:Path = (p / k)
                        newpath.parent.mkdir(parents=True, exist_ok=True)
                        newpath.write_bytes(v)

                    elif isinstance(v, str) and v and os.path.exists(v):
                        v = Path(v).resolve()
                        newpath:Path = (p / k)
                        newpath.parent.mkdir(parents=True, exist_ok=True)
                        newpath.write_bytes(v.read_bytes())

                    elif isinstance(v, str) and v:
                        newpath:Path = (p / k)
                        newpath.parent.mkdir(parents=True, exist_ok=True)
                        newpath.write_bytes(v.encode())

                    # typst rust bindings do not like non text files (but will try to find them at the given
                    # pathes within the document). Therefore only include typst files.
                    if newpath and newpath.suffix in ['.typ', '.txt', '.csv', '.json']:
                        newinp[k] = newpath.resolve()
                    elif newpath:
                        context[k] = newpath.resolve()

                # bring along files that are referenced by the sources but are
                # not part of the input (e.g. local images referenced by
                # markdown-converted document content)
                _copy_missing_file_refs(inp, p, kw.get('root') or os.getcwd())

                kw['input'] = newinp
                
                if context and not 'context' in kw:
                    kw['context'] = context
                elif context:
                    kw['context'].update(context)

                kw.pop('root', None)  # remove root as we are now in tempdir
                return _compile(verb, on_warning, root=str(tempdir), **kw)


    import typst
    context = kw.pop('context', {}) or {}

    try:
        if verb:
            log.info(f'Compiling typst document to {kw.get("output", "N/A")} format {kw.get("format", "N/A")} with typst compiler...')

        if verb:
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
                    log.info(f'Compiling typst document... success')
        else:
            res = typst.compile(**kw)
            warns = []
    except ImportError as err:
        log.error(f'Typst is not installed: {err}', exc_info=1)
        err.context = util.get_inp_context('main.typ', context=context, **kw)
        raise

    except typst.TypstError as err:
        sshort = f'Typst failed with error:\n- ERROR: {err.message}\n- Diagnostic:\n{err.diagnostic}'
        s = sshort
        if err.hints:
            s += '\nHints:\n' + '\n'.join(err.hints)
        if err.trace:
            s += '\nTrace:\n' + '\n'.join(err.trace)
        log.error(s, exc_info=1)
        err.context = util.get_inp_context('main.typ', context=context, **kw)
        if int(verb) >= 2:

            log.info(f'here is the info from typst compilation:')
            for k, v in kw.items():
                v:bytes = v
                if isinstance(v, bytes):
                    s = v.decode('ascii', errors='replace').splitlines()
                else:
                    s = v.splitlines()
                s = [f'{i} | {l}' for i, l in enumerate(s, 1)]
                s = '\n'.join(s)
                log.info(f'---\n{k}\n{s}')
        raise 
    except Exception as err:
        err.context = util.get_inp_context('main.typ', context=context, **kw)
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
    elif isinstance(typst_code, str) and not os.path.exists(typst_code):
        files = typst_code.encode()
    else:
        # # Always use dict format for input when passing source code directly.
        # # On Windows, passing input as a string (source code) to typst.compile
        # # causes error 123 because typst interprets it as a file path.
        files = {
            "main.typ": typst_code,
        }


    # Build kw dict, only including output if it's set (None causes Windows error 123)
    kw = {
        'input': files,
        'format': ext,
        **kwargs
    }
    if output is not None:
        kw['output'] = output
    
    # On Windows, typst needs a valid root directory to resolve relative paths.
    # If root is not provided, use current directory.
    if 'root' not in kw:
        kw['root'] = os.getcwd()
        
    return _compile(verb, on_warning, **kw)

# def _typstraw():
#     import typst
#     compiler = typst.Compiler()
#     compiler.compile(input="hello.typ", format="png", ppi=144.0)

def convert(doc:List[dict], template = None, template_params=None, ret_attachments=False, verb=0, template_engine='auto', **kwargs):

    if not template_params:
        template_params = {}

    unknown_params = kwargs
    if unknown_params:
        warnings.warn(f'Unknown parameters passed: {unknown_params=}')


    formatter = DocumentTypstFormatter()
    tmp = list(doc.values()) if isinstance(doc, dict) else doc
    body = formatter.digest(tmp)

    template_obj, attachments, template_str = handle_template(template, __default_template, tformat='typ', template_engine=template_engine)
    

    try:
        if blocktmpl.detect(template_str):
            doc_b = blocktmpl.parse(template_str, tformat='typ', strict=False)
            expected_variables = {k: p.value for k, p in doc_b.params_section.params.items()} if doc_b.params_section else {}
        else:
            tds = templating.TemplateDirSource(None, tformat='typ')
            expected_variables = tds.get_params(template_str if template_str else template_obj)
    except Exception as err:
        log.warning(f'failed to extract expected_variables from template: {err} will continue without expected_variables')
        expected_variables = {}


    kw = copy.deepcopy(template_params)
    libraries = kw.pop("libraries", [])
    libraries.extend(formatter.libraries)
    kw = util.remove_undefined(kw)
    # treat empty values (e.g. block template defaults carried via the metadata
    # flow) as "not given" so the pydocmaker logo is still auto injected
    if not kw.get('logo_b64_pydocmaker') and (not expected_variables or 'logo_b64_pydocmaker' in expected_variables):
        kw['logo_b64_pydocmaker'] = b64_data.logo_b64_pydocmaker
    if not kw.get('pLogoB64Pydocmaker') and 'pLogoB64Pydocmaker' in expected_variables:
        kw['pLogoB64Pydocmaker'] = b64_data.logo_b64_pydocmaker



    assert not ('body' in kw), f'the "body" keyword is an invalid keyword for templates as it is reserved for the document body.'
    
    if 'applicables' in kw and isinstance(kw['applicables'], str):
        kw['applicables'] = {}
    if 'references' in kw and isinstance(kw['references'], str):
        kw['references'] = {}
    if 'acronyms' in kw and isinstance(kw['acronyms'], str):
        kw['acronyms'] = {}

    # map legacy parameter names (e.g. "title") onto the new names (e.g.
    # "pDocTitle") for plain jinja2 templates; the block engine does its own
    # template-aware mapping while rendering
    if not isinstance(template_obj, BlockDocTemplate):
        kw = map_legacy_params(kw)

    # if libraries:
    #     b = ('\n'.join(libraries) + '\n\n' + body)
    # else:
    #     b = body
    kw['body'] = body
    
    # typst can handle named references, so we can directly pass the dict to the template
    # if 'applicables' in kw:
    #     kw['applicables'] = {i:v for i, v in enumerate(kw['applicables'].values(), 1)} 
    # if 'references' in kw:
    #     kw['references'] = {i:v for i, v in enumerate(kw['references'].values(), 1)} 

    kw = util.remove_undefined(kw)
    if verb > 1:
        log.info(f'"typst" backend creating ".typ" document with')
        log.info(f'   template={util.limit_len(template_obj, 30)!r}') 
        log.info(f'      -> str: {util.limit_len(template_str, 30)!r}') 
        log.info(f'   {kw.keys()=}')
        log.info(f'   {attachments.keys()=}')
    
    libraries = list(sorted(libraries))
    
    try:
        doc_typst = template_obj.render(**kw)

        # append the libraries to the front
        doc_typst = '\n'.join(libraries) + '\n\n' + doc_typst

        # {{ body }} was not part of the template... just append it to the end
        if not body in doc_typst:
            doc_typst += '\n\n' + body

        if DO_REPLACE_HORIZONTALRULE:
            doc_typst = doc_typst.replace('#horizontalrule', '#line(length: 100%, stroke: 0.5pt)')

    except Exception as err:
        s = f'Error while rendering the typst template: {err}'
        log.error(s)
        log.error(traceback.format_exc())
        raise 
    
    if ret_attachments:
        return doc_typst, attachments
    else:
        return doc_typst



class DocumentTypstFormatter(PandocBatchMixin, BaseFormatter):

    # kind (pandoc input format) -> (output format, is_code)
    _pandoc_batch_specs = {
        'markdown': ('typst', False),
        'latex': ('typst', False),
    }

    def __init__(self) -> None:
        self.cnt_img = 0
        self.cnt_tables = 0
        self.libraries = set()
        self._pandoc_batch_init()

    def _handle_color(self, part, color=None, **kwargs) -> str:
        if color:
            s = '#text(fill: ' + color + ')[\n' + str(part) + '\n]\n'
            return s
        else:
            return part

    def _pandoc_finalize(self, kind, el, converted=None, err=None) -> str:
        kwargs = dict(el)
        children = kwargs.pop('children', '')
        if kind == 'markdown':
            return self._finalize_markdown(children, converted=converted, **kwargs)
        else:
            return self._finalize_latex(children, converted=converted, **kwargs)

    def _finalize_latex(self, children, converted=None, **kwargs):
        """Post-conversion handling for a latex element (behavior unchanged).

        ``converted`` is the typst string produced by the batch or per-block
        pandoc conversion; ``converted=None`` triggers the verbatim mitex
        fallback (pandoc missing or conversion failed).
        """
        s = converted
        err = ''
        if can_run_pandoc():
            if s is not None:
                return self._handle_color(s, **kwargs)
            err = 'Can not convert latex to typst! Embedding the latex code verbatim...\n\n'
        else:
            err = 'Pandoc is not available to convert latex to typst! Embedding the latex code verbatim...\n\n'

        if s is None:
            self.libraries.add('#import "@preview/cmarker:0.1.8"')
            self.libraries.add('#import "@preview/mitex:0.2.7": *')
            safe_latex = json.dumps(children, cls=util.CommonJSONEncoder) # escape all chars etc. and put quotes around it
            s = f'#mitext({safe_latex})'
            return s

        s = err
        s += self.digest_verbatim(children=children, lang='latex', **kwargs)
        return self._handle_color(s, 'orange')

    def _finalize_markdown(self, children, converted=None, **kwargs):
        """Post-conversion handling for a markdown element (behavior unchanged).

        ``converted`` is the typst string produced by the batch or per-block
        pandoc conversion; ``converted=None`` triggers the cmarker fallback
        (pandoc missing or conversion failed).
        """
        s = converted

        if s is None:
            self.libraries.add('#import "@preview/cmarker:0.1.8"')
            self.libraries.add('#import "@preview/mitex:0.2.6": mitex')
            safe_markdown = json.dumps(children, cls=util.CommonJSONEncoder) # escape all chars etc. and put quotes around it
            s = f'#cmarker.render({safe_markdown}, math: mitex)'

        return self._handle_color(s, **kwargs)

    def digest_latex(self, children: str, **kwargs):
        if can_run_pandoc():
            return self._pandoc_register('latex', dict(children=children, **kwargs), children=children)

        return self._finalize_latex(children, **kwargs)

    def digest_markdown(self, children='', **kwargs) -> str:
        if config_use_pandoc_for_md_render_get() and can_run_pandoc():
            return self._pandoc_register('markdown', dict(children=children, **kwargs), children=children)

        return self._finalize_markdown(children, **kwargs)
    
    def digest_text(self, children='', **kwargs):
        return self._handle_color(children, **kwargs)
    
    def digest_table(self, children=None, **kwargs) -> str:
        
        self.libraries.add('#show figure.where(kind: table): set block(breakable: true)') # make a table break at end of page
        self.libraries.add('#let wrappable(body) = {\n  show regex("[.,:\\\\-_]"): it => [#it#sym.zws]\n  body\n}') # make column text also break on ,.:-

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

        if not imageblob:
            return ''
        
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

        if not lang:
            lang = ''
        else:
            lang = f'{str(lang).strip()}'
            if USE_CODELY:
                self.libraries.add(CODLY_LIBS)
        


        if isinstance(children, str):
            txt = children.strip('\n') # to_typst_string(children) #.strip('\n')
        else:
            txt = self.digest(children)
            
        s = f"""````{lang}\n{txt}\n````"""
        # s = f'\n#raw(`{}`, block: true, lang: {lang})\n\n'
        # if USE_CODELY and not lang:
        #     s = f'#no-codly[\n{s}\n]'
                

        return self._handle_color(s, **kwargs)
    
        

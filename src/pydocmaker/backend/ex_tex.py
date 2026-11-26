
import base64
import copy
import os
from pathlib import Path
import json

import traceback

from jinja2 import Template
from typing import List
from string import Template
from typing import List, Optional



    
try:
    from pydocmaker import util
except Exception as err:
    from . import util

try:
    from pydocmaker.param_mapping import map_legacy_params
except Exception as err:
    from ..param_mapping import map_legacy_params

log = util.log

try:
    from pydocmaker.backend.baseformatter import BaseFormatter
except Exception as err:
    from .baseformatter import BaseFormatter

try:
    from pydocmaker.templating import handle_template, BlockDocTemplate
except Exception as err:
    from ..templating import handle_template, BlockDocTemplate

try:
    from pydocmaker.backend import pdf_maker_tex
except Exception as err:
    from . import pdf_maker_tex
    

try:
    from pydocmaker.backend.pandoc_api import can_run_pandoc, pandoc_convert, config_use_pandoc_for_md_render_get
except Exception as err:
    from .pandoc_api import can_run_pandoc, pandoc_convert, config_use_pandoc_for_md_render_get

try:
    from pydocmaker.backend.pandoc_batch import PandocBatchMixin
except Exception as err:
    from .pandoc_batch import PandocBatchMixin




USE_XLTABULAR = True

latex = None
md = None
latex_mdx = None

def _lazy_import():
    global md, latex
    if latex is None:
        try:
            import latex
        except ImportError:
            latex = None
    if md is None:
        import markdown
        try:
            import pydocmaker.backend.mdx_latex as mdx_latex
        except Exception as err:
            from . import mdx_latex

        md = markdown.Markdown()
        latex_mdx = mdx_latex.LaTeXExtension()
        latex_mdx.extendMarkdown(md)


color_map = {
    'green': 'ForestGreen',
    'blue': 'NavyBlue'
}


_TABLE_WITH_CAPTION = Template(r"""\begin{table}[h!]
\centering
\begin{tabular}{ $colspec }
$body
\end{tabular}
\caption{$caption}
\end{table}""")

_TABLE_NO_CAPTION = Template(r"""\begin{center}
\begin{tabular}{ $colspec }
$body
\end{tabular}
\end{center}""")


def render_latex_table(
    colspec: str,
    rows: List[str],
    caption: Optional[str] = None,
    border: bool = True,
) -> str:
    if border:
        hline = r'\hline'
        parts = [hline]
        for row in rows:
            parts.append(row)
            parts.append(hline)
        body = '\n'.join(parts)
    else:
        body = '\n'.join(rows)
    if caption:
        return _TABLE_WITH_CAPTION.substitute(
            colspec=colspec,
            body=body,
            caption=escape(caption),
        )
    return _TABLE_NO_CAPTION.substitute(
        colspec=colspec,
        body=body,
    )


_XLTABULAR_WITH_CAPTION = Template(r"""\begin{xltabular}{\textwidth}{ $colspec }
\caption{$caption} \\
\hline
$header
\hline
\endfirsthead
\hline
$header
\hline
\endhead
\hline
\multicolumn{$ncols}{r}{\small\textit{Continued on next page}} \\
\endfoot
\hline
\endlastfoot
$body
\end{xltabular}""")

_XLTABULAR_NO_CAPTION = Template(r"""\begin{xltabular}{\textwidth}{ $colspec }
\hline
$header
\hline
\endfirsthead
\hline
$header
\hline
\endhead
\hline
\multicolumn{$ncols}{r}{\small\textit{Continued on next page}} \\
\endfoot
\hline
\endlastfoot
$body
\end{xltabular}""")

_XLTABULAR_WITH_CAPTION_NO_BORDER = Template(r"""\begin{xltabular}{\textwidth}{ $colspec }
\caption{$caption} \\
$header
\endfirsthead
$header
\endhead
\multicolumn{$ncols}{r}{\small\textit{Continued on next page}} \\
\endfoot
\endlastfoot
$body
\end{xltabular}""")

_XLTABULAR_NO_CAPTION_NO_BORDER = Template(r"""\begin{xltabular}{\textwidth}{ $colspec }
$header
\endfirsthead
$header
\endhead
\multicolumn{$ncols}{r}{\small\textit{Continued on next page}} \\
\endfoot
\endlastfoot
$body
\end{xltabular}""")


def render_xltabular(
    colspec: str,
    header: str,
    rows: List[str],
    ncols: int,
    caption: Optional[str] = None,
    border: bool = True,
) -> str:
    body = '\n\\hline\n'.join(rows) if border else '\n'.join(rows)
    if caption:
        tmpl = _XLTABULAR_WITH_CAPTION if border else _XLTABULAR_WITH_CAPTION_NO_BORDER
        return tmpl.substitute(
            colspec=colspec,
            header=header,
            body=body,
            ncols=ncols,
            caption=escape(caption),
        )
    tmpl = _XLTABULAR_NO_CAPTION if border else _XLTABULAR_NO_CAPTION_NO_BORDER
    return tmpl.substitute(
        colspec=colspec,
        header=header,
        body=body,
        ncols=ncols,
    )

__default_template = r"""


\documentclass[a4paper]{article}
\usepackage{hyperref}
\usepackage{graphicx}
\usepackage[dvipsnames]{xcolor}
\usepackage{listings}
\usepackage{xltabular}
\usepackage{array}
\usepackage{calc}
\usepackage{booktabs}

\lstset{
  frame=single,
  rulecolor=\color{black},
  breaklines=true,
  breakatwhitespace=false,
  postbreak=\mbox{\textcolor{gray}{$\hookrightarrow$}\space},
  basicstyle=\ttfamily\small,
  columns=fullflexible,
  keywordstyle=\color{Blue}\bfseries,
  stringstyle=\color{ForestGreen},
  commentstyle=\color{Gray}\itshape
}


\makeatletter
\newcommand{\pydifempty}[1]{%
\if\relax\detokenize\expandafter{#1}\relax
\expandafter\@firstoftwo
\else
\expandafter\@secondoftwo
\fi
}
\makeatother



% pydocmaker:parameters:begin
% NOTE: parameter names use a leading "p" (pTitle, pAuthor, ...) so the derived
% LaTeX macros (\pTitle, ...) never collide with LaTeX kernel macros.
% pydocmaker:param:pTitle
\providecommand{\pTitle}{My Report}
% pydocmaker:param:pAuthor
\providecommand{\pAuthor}{Automatically Generated via pydocmaker}
% pydocmaker:param:pDate
\providecommand{\pDate}{\today}
% pydocmaker:param:pAcronyms
\providecommand{\pAcronyms}{}
% pydocmaker:param:pApplicables
\providecommand{\pApplicables}{}
% pydocmaker:param:pReferences
\providecommand{\pReferences}{}
% pydocmaker:parameters:end

\begin{document}

\pydifempty\pTitle{}{\begin{center}{\LARGE \textbf{\pTitle}}\end{center}}

\pydifempty\pAuthor{}{\begin{center}{\large \pAuthor}\end{center}}

\pydifempty\pDate{}{\begin{center}{\pDate}\end{center}}

\pydifempty\pAcronyms{}{\section*{List of Acronyms}\pAcronyms}

\pydifempty\pApplicables{}{\section*{Applicable Documents}\pApplicables}

\pydifempty\pReferences{}{\section*{Reference Documents}\pReferences}

% pydocmaker:body:begin
Document body placeholder
% pydocmaker:body:end

\end{document}
"""



def escape(s):
    _lazy_import()
    if latex is None:
        raise ImportError("The 'latex' package is required for escaping LaTeX special characters. Please install it using 'pip install latex'.")
    if isinstance(s, dict):
        return {k:latex.escape(v) for k, v in s.items()}
    elif isinstance(s, str):
        return latex.escape(s)
    else:
        return s

def auto_escape_latex(params):
    """Auto-escape plain-text parameter values for LaTeX; strings starting with
    the ``%%latex`` / ``%latex`` / ``%tex`` marker pass through unchanged."""
    if isinstance(params, str):
        return params if params.startswith('%%latex') or params.startswith('%latex') or params.startswith('%tex') else escape(params)
    elif isinstance(params, dict):
        return {k:auto_escape_latex(v) for k, v in params.items()}
    elif isinstance(params, list):
        return [auto_escape_latex(v) for v in params]
    else:
        return params



def convert(doc:List[dict], with_attachments=True, files_to_upload=None, template = None, do_escape_template_params=False, template_params=None, verb=0, template_engine='auto', **kwargs):

    if not files_to_upload:
        files_to_upload = {}

    if not template_params:
        template_params = {}

    if isinstance(files_to_upload, str) and os.path.exists(files_to_upload) and os.path.isdir(files_to_upload):
        d = files_to_upload
        files_to_upload = {}
        for root, dirs, files in os.walk(d):
            for file in files:
                file_path = os.path.join(root, file)
                with open(file_path, 'rb') as f:
                    files_to_upload[file] = f.read()

    formatter = LatexElementFormatter()
    s = formatter.format(doc)
    formatter.attachments.update(files_to_upload)

    body = '\n'.join(s) if isinstance(s, list) else s

    template_obj, attachments, template_str = handle_template(template, __default_template, tformat='tex', template_engine=template_engine)
    
    if template == '':
        s = 'It seems you have provided an empty template to use. This will most likely fail, since LaTeX actually needs imports etc. to work. I will try anyways though.'
        log.warning(s)
    
    kw = copy.deepcopy(template_params)
    if do_escape_template_params == 'auto':
        # The block templating engine escapes parameter values itself when it
        # serializes the macro assignments, so pre-escaping here would
        # double-escape them (a "\today" default would come out as
        # "\textbackslash\{\}today"). Only plain Jinja2 LaTeX templates
        # interpolate values verbatim and need plain-text values pre-escaped.
        if not isinstance(template_obj, BlockDocTemplate):
            kw = auto_escape_latex(kw)
        do_escape_template_params = False
    if do_escape_template_params:
        kw = {k:escape(v) for k, v in kw.items()}

    assert not ('body' in kw), f'the "body" keyword is an invalid keyword for templates as it is reserved for the document body.'
    kw['body'] = body
    
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

    if 'applicables' in kw:
        kw['applicables'] = {i:escape(v) for i, v in enumerate(kw['applicables'].values(), 1)} 
    if 'references' in kw:
        kw['references'] = {i:escape(v) for i, v in enumerate(kw['references'].values(), 1)} 

    kw = util.remove_undefined(kw)
    if verb > 1:
        log.info(f'"tex" backend creating ".tex" document with')
        log.info(f'   template={util.limit_len(template_obj, 30)!r}') 
        log.info(f'      -> str: {util.limit_len(template_str, 30)!r}') 
        log.info(f'   {kw.keys()=}')
        log.info(f'   {attachments.keys()=}')

    doc_tex = template_obj.render(**kw)
    formatter.attachments.update(attachments)

    # remote the pandoc specific macros
    macros = ("passthrough", "tightlist", "lstinline", "Verb")
    for macro in macros:
        macro = "\\" + macro
        cmd = "\\providecommand{%s}" % macro
        if cmd not in doc_tex and macro in doc_tex:
            if verb: log.warning(f'found "{macro}" in tex source but no "{cmd}" will replace all occurances')
            doc_tex = doc_tex.replace(macro, "")


    if with_attachments:
        return doc_tex, formatter.attachments
    else:
        return doc_tex
    

def make_pdf(doc:List[dict], files_to_upload=None, template = None, template_params=True, do_escape_template_params=False, docname=None, verb=0, template_engine='auto', **kwargs):
    """
    Generate a PDF document from a list of dictionaries.

    Args:
        doc (List[dict]): A list of dictionaries containing the data for the document.
        files_to_upload (optional): A list of files to be uploaded with the document.
        template_header (str, optional): A string containing the LaTeX code for the document header.
            If not provided, a default header will be used.
        template_footer (str, optional): A string containing the LaTeX code for the document footer.
            If not provided, a default footer will be used.
        docname (str, optional): The name of the document.
        template_engine (str, optional): Template engine selection ('auto', 'jinja2', 'blocks').
        **kwargs: Additional keyword arguments to be passed to the PDF maker.

    Returns:
        bytes: A bytes object containing the PDF data.
    """

    latex_str, attachments_dc = convert(doc, files_to_upload=files_to_upload, template=template, template_params=template_params, do_escape_template_params=do_escape_template_params, with_attachments=True, verb=verb, template_engine=template_engine)
    if verb > 1:
        log.info(f'"tex" backend creating ".tex" document from latex string {util.limit_len(latex_str, 30)!r} and attachments {attachments_dc.keys()!r}')        
    return pdf_maker_tex.make_pdf_from_tex(input_latex_text=latex_str, attachments_dc=attachments_dc, docname=docname, out_format='pdf', verb=verb, **kwargs)

    
def make_pdf_zip(doc:List[dict], files_to_upload=None, template = None, template_params=True, do_escape_template_params=False, docname=None, verb=0, template_engine='auto', **kwargs):
    """
    Generates a PDF zip file from a list of dictionaries.

    Args:
        doc (List[dict]): A list of dictionaries containing the data to be converted into a PDF.
        files_to_upload (dict, optional): A dictionary of files to be uploaded. Defaults to None.
        template_header (str, optional): The header template for the LaTeX document. Defaults to a default header.
        template_footer (str, optional): The footer template for the LaTeX document. Defaults to a default footer.
        docname (str, optional): The name of the document. Defaults to None.
        **kwargs: Additional keyword arguments to be passed to the PDF maker.

    Returns:
        bytes: A zip file containing the generated PDF and any attachments.
    """
    if hasattr(doc, 'dump'):
        doc = doc.dump()
    
    if not files_to_upload:
        files_to_upload = {}
    files_to_upload['doc.json'] = json.dumps(doc, cls=util.CommonJSONEncoder, indent=2)
    latex_str, attachments_dc = convert(doc, files_to_upload=files_to_upload, template=template, template_params=template_params, do_escape_template_params=do_escape_template_params, with_attachments=True, verb=verb, template_engine=template_engine)
    return pdf_maker_tex.make_pdf_from_tex(input_latex_text=latex_str, attachments_dc=attachments_dc, docname=docname, out_format='zip', **kwargs)

    


###########################################################################################
"""

███████  ██████  ██████  ███    ███  █████  ████████ 
██      ██    ██ ██   ██ ████  ████ ██   ██    ██    
█████   ██    ██ ██████  ██ ████ ██ ███████    ██    
██      ██    ██ ██   ██ ██  ██  ██ ██   ██    ██    
██       ██████  ██   ██ ██      ██ ██   ██    ██    
                                                     
"""
###########################################################################################

from enum import Enum

class bcolors(Enum):
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'



def _find_all_indices(s, c):
    inds, i = [], 0
    while (i := s.find(c, i)) >= 0:
        inds.append(i)
        i += len(c)
    return inds

def _get_substrings(s):
    inds = []
    for c in bcolors:
        inds += [(v,c) for v in _find_all_indices(s, c.value)]
    inds.sort(key=lambda i:i[0])
    subs = []
    if inds:
        for (k, c), (k2, c2) in zip(inds[0:], inds[1:]):
            if (k, c) == inds[0] and k != 0: # first iter
                subs.append((s[:k], None))
            subs.append((s[k:k2], c))
            if (k2, c2) == inds[-1] and k2 != len(s): # last iter
                k2 += len(c2.value)
                subs.append((s[k2:], None))
    else:
        subs.append((s, None))
    return subs
        
        


def _handle_bcolors(txt, color):
    if color is None:
        return txt
    
    sub = txt[len(color.value):]
    if color == bcolors.HEADER:
        return '\\textcolor{%s}{%s}' % (mapc("purple"), sub,)
    elif color == bcolors.OKBLUE:
        return '\\textcolor{%s}{%s}' % (mapc("blue"), sub,)
    elif color == bcolors.OKCYAN:
        return '\\textcolor{%s}{%s}' % (mapc("cyan"), sub,)
    elif color == bcolors.OKGREEN:
        return '\\textcolor{%s}{%s}' % (mapc("green"), sub,)
    elif color == bcolors.WARNING:
        return '\\textcolor{%s}{%s}' % (mapc("yellow"), sub,)
    elif color == bcolors.FAIL:
        return '\\textcolor{%s}{%s}' % (mapc("red"), sub,)
    elif color == bcolors.ENDC:
        return sub
    elif color == bcolors.BOLD:
        return '\\textbf{%s}' % (sub,)
    elif color == bcolors.UNDERLINE:
        return '\\underline{%s}' % (sub,)
    else:
        return txt

def replace_bcolors(s):
    new_parts = [_handle_bcolors(*t) for t in _get_substrings(s)]
    return ''.join(new_parts)

def mapc(c):
    if c:
        c = color_map.get(c.lower(), c)
        c = c[0].upper() + c[1:]
    return c
    

def map_colornames(txt, c):
    if c:
        c = color_map.get(c.lower(), c)
        c = c[0].upper() + c[1:]
        return '\\color{%s}{%s}' % (c, txt)
    else:
        return txt
    

def handle_color(func):
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        c = kwargs.get('color', None)
        return map_colornames(result, c)
    return wrapper

class LatexElementFormatter(PandocBatchMixin, BaseFormatter):

    # kind (pandoc input format) -> (output format, is_code)
    _pandoc_batch_specs = {'markdown': ('latex', True)}

    def __init__(self, make_blue=False) -> None:
        self.attachments = {}
        self.make_blue = make_blue

        self._escape_strings = False
        self._pandoc_batch_init()

    def handle_error(self, err, el):
        txt = 'ERROR WHILE HANDLING ELEMENT:\n{}\n\n'.format(el)
        if not isinstance(err, str):
            tb_str = '\n'.join(traceback.format_exception(type(err), value=err, tb=err.__traceback__, limit=5))
            txt += tb_str + '\n'
        else:
            txt += err + '\n'
        txt = r"""\begin{small}\begin{lstlisting}[breaklines=true,basicstyle=\ttfamily]
<REPLACEME:VERBTEXT>
\end{lstlisting}\end{small}""".replace('<REPLACEME:VERBTEXT>', txt)
        txt = f'{{\\color{{red}}{txt}}}'

        return txt

    def digest_markdown(self, children='', **kwargs) -> str:
        if config_use_pandoc_for_md_render_get() and can_run_pandoc():
            return self._pandoc_register('markdown', dict(children=children, **kwargs), children=replace_bcolors(children))

        _lazy_import()
        tex = md.convert(replace_bcolors(children)).lstrip('<root>').rstrip('</root>')
        return map_colornames(str(tex), kwargs.get('color'))

    def _pandoc_finalize(self, kind, el, converted=None, err=None) -> str:
        if converted is not None:
            return map_colornames(converted, el.get('color'))
        return self.handle_error(err, el)

    
    def digest_image(self, children='', width=None, caption='', imageblob='', **kwargs) -> str:

        if width is None:
            width = 0.8
            
        if not isinstance(width, str):
            width = 'width={}\\textwidth'.format(width)

        
        file_name = os.path.basename(children)
        assert file_name, 'need to give a file name for the image'

        if imageblob:
            if isinstance(imageblob, str):
                if not file_name.lower().endswith("png") and "image/png" in imageblob[:100]:
                    file_name = str(Path(file_name).with_suffix(".png"))

                if ';base64, ' in imageblob:
                    imageblob = imageblob.replace(';base64, ', ';base64,')

                imageblob = imageblob.encode("utf8")

            data = imageblob.split(b";base64,")[-1]
            self.attachments[file_name] = base64.decodebytes(data)

        txt = fr'\includegraphics[{width}]{{{file_name}}}'

        if caption:
            c = escape(caption)
            txt += '\n' + fr'\caption{{{c}}}'

        txt = r"\begin{figure}[h!]" + '\n' + r"\centering" '\n' + txt + '\n' + r"\end{figure}"
        return txt


    @handle_color
    def digest_verbatim(self, children='', **kwargs) -> str:
        txt = self.digest(children)
        template = r"""\begin{tabular}{|p{.95\textwidth}|}
\hline
\begin{small}\begin{lstlisting}[breaklines=true,basicstyle=\ttfamily]
<REPLACEME:VERBTEXT>
\end{lstlisting}\end{small}
\\
\hline
\end{tabular}\par"""
        txt = txt.strip('\n')
        parts = []

        while len(txt) > 2000:
            parts.append(template.replace('<REPLACEME:VERBTEXT>', txt[:2000]))
            txt = txt[2000:]
        parts.append(template.replace('<REPLACEME:VERBTEXT>', txt))

        txt = '\n\n'.join(parts)
        return txt

    def _dig_str(self, children:str, **kwargs):
        s = replace_bcolors(str(children))
        return auto_escape_latex(s) if self._escape_strings else s

    @handle_color
    def digest_text(self, children:str, **kwargs):
        return self._dig_str(children, **kwargs)
    
    @handle_color
    def digest_str(self, el):
        return self._dig_str(el)
    
    @handle_color
    def digest_latex(self, children:str, **kwargs):
        return replace_bcolors(str(children))
    
    @handle_color
    def digest_line(self, children:str, **kwargs):
        return self._dig_str(children, **kwargs)

    def digest_table(self, children=None, **kwargs) -> str:
        borders = kwargs.pop('borders', None)
        if borders is None:
            borders = True

        caption = kwargs.pop('caption', '')
        if not caption:
            caption = ''

        def fun_tmp(*a, **kw):
            self._escape_strings = True
            try:
                return self.digest(*a, **kw)
            finally:
                self._escape_strings = False

        head, mat = self._map_table2mat(children=children, fun=fun_tmp, **kwargs)
        if not head and not mat[0]:
            return ''
        

        striprow = lambda x: [str(xx).strip() for xx in x]
        bold = lambda x: '\\textbf{' + str(x).strip() + '}'

        n_cols = len(head) if head else len(mat[0])

        header = ' & '.join([bold(hh) for hh in head]) + r' \\' if head else ''
        rows = [' & '.join(striprow(row)) + r' \\' for row in mat]

        if USE_XLTABULAR and head:
            # xltabular is based on tabularx, so X columns can be used: they
            # wrap their content and keep the table width at \textwidth
            xcol = r'>{\raggedright\arraybackslash}X'
            if borders:
                colspec = '|' + '|'.join([xcol] * n_cols) + '|'
            else:
                colspec = ' '.join([xcol] * n_cols)

            return render_xltabular(
                colspec=colspec,
                header=header,
                rows=rows,
                ncols=n_cols,
                caption=caption or None,
                border=borders,
            )

        if borders:
            colspec = '|' + '|'.join(['c'] * n_cols) + '|'
        else:
            colspec = ' '.join(['c'] * n_cols)

        if head:
            rows = [header] + rows

        return render_latex_table(
            colspec=colspec,
            rows=rows,
            caption=caption or None,
            border=borders,
        )


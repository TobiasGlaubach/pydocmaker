
import argparse
import base64
import copy
import io
import os
import re
from pathlib import Path
import json
import shutil
import subprocess
import time
import traceback
import sys

import tempfile
import shutil
from io import BytesIO

import zipfile
import latex
from jinja2 import Template

from typing import List
import markdown
try:
    import pydocmaker.backend.mdx_latex as mdx_latex
except Exception as err:
    from . import mdx_latex
    

try:
    from pydocmaker.backend.baseformatter import BaseFormatter
except Exception as err:
    from .baseformatter import BaseFormatter
    
try:
    from pydocmaker.backend import pdf_maker
except Exception as err:
    from . import pdf_maker
    

    
try:
    from pydocmaker.backend.pandoc_api import can_run_pandoc, pandoc_convert
except Exception as err:
    from .pandoc_api import can_run_pandoc, pandoc_convert
    

md = markdown.Markdown()
latex_mdx = mdx_latex.LaTeXExtension()
latex_mdx.extendMarkdown(md)

color_map = {
    'green': 'ForestGreen',
    'blue': 'NavyBlue'
}

__default_template = r"""
\documentclass[a4paper]{article}
\usepackage{hyperref}
\usepackage{graphicx}
\usepackage[dvipsnames]{xcolor}
\usepackage{listings}

{% if title %}\title{{ title }}{% endif %}
{% if author %}\author{{ author }}{% endif %}
{% if date %}\date{{ date }}{% endif %}

{% if applicables or references or acronyms %}
\section*{References}
{% endif %}
{% if acronyms %}
\subsection*{List of Acronyms}
\begin{tabular}{l@{\hspace{3cm}}l}
{% for key, value in acronyms.items() %}
{{ key }} & {{ value }} \\
{% endfor %}
\end{tabular}
{% endif %}
{% if applicables %}
\subsection*{Applicable Documents}
\begin{tabular}{l@{\hspace{1cm}}p{13cm}}
{% for i, value in applicables.items() %}
AD[{{ i }}] & {{ value }} \\
{% endfor %}
\end{tabular}
{% endif %}
{% if references %}
\subsection*{Reference Documents}
\begin{tabular}{l@{\hspace{1cm}}p{13cm}}
{% for i, value in references.items() %}
RD[{{ i }}] & {{ value }} \\
{% endfor %}
\end{tabular}
{% endif %}


\begin{document}

{{ body }}

\end{document}
"""

def get_default_tex_template(as_string=False):
    return __default_template if as_string else Template(__default_template)


registered_templates = {
    'default': Template(__default_template)
}

template_attachments = {
    'default': {}
}

def register_template(new_template, template_id=None, allow_overwrite=False, attachments_dc=None):
    """
    Register a new template for use in generating documentation.

    Parameters:
    new_template (str or Template): The template to register. If a string, it is treated as a filename and the contents of the file are read. If a Template object, it is used directly.
    template_id (str, optional): The ID to use for the template. If not provided, the basename of the filename is used.
    allow_overwrite (bool, optional): If True, allow overwriting an existing template with the same ID. If False, raise an AssertionError if the ID already exists.
    attachments_dc (dict, optional): A dictionary of attachments to associate with the template. If not provided, an empty dictionary is used.

    Raises:
    AssertionError: If allow_overwrite is False and the template ID already exists in the registered templates.
    AssertionError: If the new_template object does not implement the "render" method.
    """
    
    global registered_templates, template_attachments
    if not allow_overwrite:
        assert template_id not in registered_templates, f'{template_id=} already exists in registered templates'
    
    if isinstance(new_template, str)  and os.path.exists(new_template):
        template_id = template_id if template_id else os.path.basename(new_template)
        with open(new_template, 'r') as fp:
            new_template = fp.read()

    if not attachments_dc:
        attachments_dc = {}

    if isinstance(new_template, str):
        new_template = Template(new_template)
    assert hasattr(new_template, 'render'), f'the template object must be either a string, a file, or implement the "render method", but given was {type(new_template)=}'

    template_attachments[template_id] = copy.deepcopy(attachments_dc)
    registered_templates[template_id] = copy.deepcopy(new_template)


def escape(s):
    if isinstance(s, dict):
        return {k:latex.escape(v) for k, v in s.items()}
    elif isinstance(s, str):
        return latex.escape(s)
    else:
        return s

def _handle_template(template):
    if not template:
        template = 'default'

    attachments = {}
    if isinstance(template, (list, tuple)) and len(template) == 2:
        template_header, template_footer = template
        template_obj = Template('\n\n'.join([template_header, '\n\n{{ body }}\n\n', template_footer]))
    elif hasattr(template, 'render'):
        template_obj = template
    elif isinstance(template, str) and template in registered_templates:
        template_obj = registered_templates[template]
        attachments = template_attachments.get(template, attachments)
    elif isinstance(template, str) and os.path.exists(template):
        with open(template, 'r') as fp:
            template_obj = Template(fp.read())
    elif isinstance(template, str):
        template_obj = Template(template)
    else:
        raise KeyError(f'Unknown template type! {type(template)=}')    
    return template_obj, attachments

def convert(doc:List[dict], with_attachments=True, files_to_upload=None, template = None, do_escape_template_params=False, template_params=None):

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

    template_obj, attachments = _handle_template(template)
    
    kw = copy.deepcopy(template_params)
    if do_escape_template_params:
        kw = {k:escape(v) for k, v in kw.items()}

    assert not ('body' in kw), f'the "body" keyword is an invalid keyword for templates as it is reserved for the document body.'
    kw['body'] = body
    
    if 'applicables' in kw:
        kw['applicables'] = {i:escape(v) for i, v in enumerate(kw['applicables'].values(), 1)} 
    if 'references' in kw:
        kw['references'] = {i:escape(v) for i, v in enumerate(kw['references'].values(), 1)} 

    doc_tex = template_obj.render(**kw)
    formatter.attachments.update(attachments)

    if with_attachments:
        return doc_tex, formatter.attachments
    else:
        return doc_tex
    

def make_pdf(doc:List[dict], files_to_upload=None, template = None, template_params=True, do_escape_template_params=False, docname=None, **kwargs):
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
        **kwargs: Additional keyword arguments to be passed to the PDF maker.

    Returns:
        bytes: A bytes object containing the PDF data.
    """

    latex_str, attachments_dc = convert(doc, files_to_upload=files_to_upload, template=template, template_params=template_params, do_escape_template_params=do_escape_template_params, with_attachments=True)
    return pdf_maker.make_pdf_from_tex(input_latex_text=latex_str, attachments_dc=attachments_dc, docname=docname, out_format='pdf', **kwargs)

    
def make_pdf_zip(doc:List[dict], files_to_upload=None, template = None, template_params=True, do_escape_template_params=False, docname=None, **kwargs):
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
    files_to_upload['doc.json'] = json.dumps(doc, indent=2)
    latex_str, attachments_dc = convert(doc, files_to_upload=files_to_upload, template=template, template_params=template_params, do_escape_template_params=do_escape_template_params, with_attachments=True)
    return pdf_maker.make_pdf_from_tex(input_latex_text=latex_str, attachments_dc=attachments_dc, docname=docname, out_format='zip', **kwargs)

    


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

class LatexElementFormatter(BaseFormatter):

    def __init__(self, make_blue=False) -> None:
        self.attachments = {}
        self.make_blue = make_blue


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

    @handle_color
    def digest_markdown(self, children='', **kwargs) -> str:
        if can_run_pandoc():
            return pandoc_convert(replace_bcolors(children), 'markdown', 'latex')
        else:
            tex = md.convert(replace_bcolors(children)).lstrip('<root>').rstrip('</root>')
        return str(tex)

    
    def digest_image(self, children='', width=0.8, caption='', imageblob='', **kwargs) -> str:

        if not isinstance(width, str):
            width = 'width={}\\textwidth'.format(width)

        
        file_name = os.path.basename(children)
        assert file_name, 'need to give a file name for the image'

        if imageblob:
            if isinstance(imageblob, str):
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

    @handle_color
    def digest_text(self, children:str, **kwargs):
        return replace_bcolors(str(children))
    
    @handle_color
    def digest_latex(self, children:str, **kwargs):
        return replace_bcolors(str(children))
    
    @handle_color
    def digest_line(self, children:str, **kwargs):
        return replace_bcolors(str(children))


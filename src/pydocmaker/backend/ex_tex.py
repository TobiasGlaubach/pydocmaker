
import argparse
import base64
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


__template_header_default = """
\\documentclass[12pt, a4paper]{article}
\\usepackage{graphicx}
\\usepackage{media9}
\\usepackage{a4}
\\usepackage{fancyhdr}
\\usepackage[scaled]{helvet}
\\usepackage[T1]{fontenc}
\\usepackage{subcaption}
\\usepackage[dvipsnames]{xcolor} 
\\usepackage[utf8]{inputenc}
\\usepackage[toc]{appendix}
\\usepackage[most]{tcolorbox}
\\usepackage{float}
\\usepackage{placeins}
\\usepackage{afterpage}
\\usepackage{longtable}
\\usepackage{background}
\\usetikzlibrary{calc}
\\usepackage{txfonts}
\\usepackage{hyperref}

\\hypersetup{
    colorlinks=true,
    linkcolor=black,
    filecolor=black,      
    urlcolor=black
}

\\renewcommand\\familydefault{\\sfdefault}

\\textwidth16cm
\\topmargin-1cm
\\topskip0cm
\\textheight22cm
\\setlength{\\headheight}{0pt}

\\parindent0pt

\\pagestyle{fancy}
\\fancyhf{}
\\fancyfoot{}
\\fancyhead{}

\\begin{document}

"""


__template_footer_default = """

\\end{document}
"""

def convert(doc:List[dict], with_attachments=True, files_to_upload=None, template_header=None, template_footer=None):

    if template_header is None:
        template_header = ''
    if template_footer is None:
        template_footer = ''
    if not files_to_upload:
        files_to_upload = {}

    formatter = ElementFormatter()
    s = formatter.format(doc)
    formatter.attachments.update(files_to_upload)

    text = '\n'.join(s) if isinstance(s, list) else s

    text = '\n\n'.join([template_header, text, template_footer])

    if with_attachments:
        return text, formatter.attachments
    else:
        return text
    

def make_pdf(doc:List[dict], files_to_upload=None, template_header=None, template_footer=None, docname=None, **kwargs):
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
    if template_header is None:
        template_header = __template_header_default
    if template_footer is None:
        template_footer = __template_footer_default

    latex_str, attachments_dc = convert(doc, files_to_upload=files_to_upload, with_attachments=True)

    latex_str = '\n\n'.join([template_header, latex_str, template_footer])
    return pdf_maker.make_pdf_from_tex(input_latex_text=latex_str, attachments_dc=attachments_dc, docname=docname, out_format='pdf', **kwargs)

    
def make_pdf_zip(doc:List[dict], files_to_upload=None, template_header=None, template_footer=None, docname=None, **kwargs):
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

    if template_header is None:
        template_header = __template_header_default
    if template_footer is None:
        template_footer = __template_footer_default
    
    if not files_to_upload:
        files_to_upload = {}
    files_to_upload['doc.json'] = json.dumps(doc, indent=2)
    latex_str, attachments_dc = convert(doc, files_to_upload=files_to_upload, with_attachments=True)

    latex_str = '\n\n'.join([template_header, latex_str, template_footer])
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


class ElementFormatter(BaseFormatter):

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
        txt = r"""
\begin{verbatim}

<REPLACEME:VERBTEXT>

\end{verbatim}""".replace('<REPLACEME:VERBTEXT>', txt)
        txt = f'{{\\color{{red}}{txt}}}'

        return txt

    def digest_markdown(self, children='', **kwargs) -> str:
        if can_run_pandoc():
            return pandoc_convert(children, 'markdown', 'latex')
        else:
            tex = md.convert(children).lstrip('<root>').rstrip('</root>')
        return tex

    
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
            txt += '\n' + fr'\caption{{{caption}}}'

        txt = r"\begin{figure}[h!]" + '\n' + r"\centering" '\n' + txt + '\n' + r"\end{figure}"
        return txt



    def digest_verbatim(self, children='', **kwargs) -> str:
        txt = self.digest(children)
        template = r"""\begin{tabular}{|p{.95\textwidth}|}
\hline
\begin{tiny}\begin{verbatim}
<REPLACEME:VERBTEXT>
\end{verbatim}\end{tiny}
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
        # if caption:
        #     caption = fr'\caption{{{caption}}}'

        # txt = txt.replace('<REPLACEME:CAPTION>', caption)

        return txt


    def digest_iterator(self, el) -> str:
        if isinstance(el, dict) and el.get('typ', '') == 'iter' and isinstance(el.get('children', None), list):
            el = el['children']
        return '\n\n'.join([f'% Iterator Element {i}\n' + self.digest(e) for i, e in enumerate(el)])

    def digest_text(self, children:str, **kwargs):
        c = kwargs.get('color')
        return '\\color{%s}{%s}' % (c, children) if c else children
    
    def digest_latex(self, children:str, **kwargs):
        c = kwargs.get('color')
        return '\\color{%s}{%s}' % (c, children) if c else children
    
    def digest_line(self, children:str, **kwargs):
        c = kwargs.get('color')
        return '\\color{%s}{%s}' % (c, children) if c else children

    def digest(self, el, make_blue=False):
        blue = lambda s: f'{{\\color{{blue}}{s}}}'
        
        if isinstance(el, dict) and isinstance(el.get('color'), str):
            color = el.get('color')
        else:
            color = None

        set_color = lambda s: f'{{\\color{color}{s}}}'

        try:
            
            if not el:
                return ''
            elif isinstance(el, str):
                ret = self.digest_str(el)
            elif isinstance(el, dict) and el.get('typ') == 'iter':
                ret = self.digest_iterator(el)
            elif isinstance(el, list) and el:
                ret = self.digest_iterator(el)
            elif isinstance(el, dict) and el.get('typ', None) == 'image':
                ret = self.digest_image(**el)
            elif isinstance(el, dict) and el.get('typ', None) == 'text':
                ret = self.digest_text(**el)
            elif isinstance(el, dict) and el.get('typ', None) == 'latex':
                ret = self.digest_latex(**el)
            elif isinstance(el, dict) and el.get('typ', None) == 'line':
                ret = self.digest_line(**el)
            elif isinstance(el, dict) and el.get('typ', None) == 'verbatim':
                ret = self.digest_verbatim(**el)
            elif isinstance(el, dict) and el.get('typ', None) == 'markdown':
                ret = self.digest_markdown(**el)
            else:
                return self.handle_error(f'the element of typ {type(el)}, could not be parsed.', el)
            
            return blue(ret) if make_blue else (set_color(ret) if color else ret)
        
        except Exception as err:
            return self.handle_error(err, el)


    def format(self, doc:list) -> str:
        return '\n\n'.join([self.digest(e, make_blue=self.make_blue) for e in doc])












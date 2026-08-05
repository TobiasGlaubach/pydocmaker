from collections import namedtuple
import copy
import io
import json
import random
import textwrap
import time
import traceback
import urllib
import re
import uuid
import os
import base64
import warnings
import markdown
from typing import List

from jinja2 import Template


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
    from . import util
    
try:
    from pydocmaker.backend.pandoc_api import can_run_pandoc, pandoc_convert
except Exception as err:
    from .pandoc_api import can_run_pandoc, pandoc_convert


__default_template = """<!DOCTYPE html>
<html>
<head>
    <style>
        
    </style>
    {% if title %}
    <title>{{ title }}</title>
    {% endif %}
</head>
<body>

{% if applicables or references or acronyms %}
<h1>{References}</h1>
{% endif %}
{% if acronyms %}
<h2>List of Acronyms</h2>
<table>
{% for key, value in acronyms.items() %}
<tr><td><b>{{ key }}</b></td><td>{{ value }}</td></tr>
{% endfor %}
</table>
{% endif %}
{% if applicables %}
<h2>Applicable Documents</h2>
<table>
{% for key, value in applicables.items() %}
<tr><td><b>AD[{{ key }}]</b></td><td>{{ value }}</td></tr>
{% endfor %}
</table>
{% endif %}
{% if references %}
<h2>Reference Documents</h2>
<table>
{% for key, value in references.items() %}
<tr><td><b>RD[{{ key }}]</b></td><td>{{ value }}</td></tr>
{% endfor %}
</table>
{% endif %}

    {{ body }}

</body>
</html>

"""




"""

 ██████  ██████  ███    ██ ██    ██ ███████ ██████  ████████ 
██      ██    ██ ████   ██ ██    ██ ██      ██   ██    ██    
██      ██    ██ ██ ██  ██ ██    ██ █████   ██████     ██    
██      ██    ██ ██  ██ ██  ██  ██  ██      ██   ██    ██    
 ██████  ██████  ██   ████   ████   ███████ ██   ██    ██    
                                                             
                                                                                                                                                                                                                                       
"""

# DEFAULT_IMAGE_PATH = os.path.join(parent_dir, 'ReqTracker', 'assets', 'mpifr.png')
# with open(DEFAULT_IMAGE_PATH, 'rb') as fp:
#     DEFAULT_IMAGE_BLOB = '' # base64.b64encode(fp.read()).decode('utf-8')
# DEFAULT_IMAGE_BLOB = ''

def mk_link(id_, label=None, pth='show', p0='uib', v='v1', **kwargs):
    return f'<a href="/{p0}/{v}/{pth}/{urllib.parse.quote_plus(id_)}" target="_self">{label if label else id_}</a>'

def mk_tpl(id_, label=None, pth='show', p0='uib', v='v1', **kwargs):
    return f"/{p0}/{v}/{pth}/{urllib.parse.quote_plus(id_)}", label if label else id_


def convert(doc:List[dict], template = None, template_params=None, **kwargs):

    if not template_params:
        template_params = {}

    unknown_params = kwargs
    if unknown_params:
        warnings.warn(f'Unknown parameters passed: {unknown_params=}')


    tmp = list(doc.values()) if isinstance(doc, dict) else doc
    body = html_renderer().format(tmp)

    template_obj, attachments, template_str = handle_template(template, __default_template, tformat='html')
    
    kw = copy.deepcopy(template_params)

    assert not ('body' in kw), f'the "body" keyword is an invalid keyword for templates as it is reserved for the document body.'
    kw['body'] = body
    
    if 'applicables' in kw:
        kw['applicables'] = {i:v for i, v in enumerate(kw['applicables'].values(), 1)} 
    if 'references' in kw:
        kw['references'] = {i:v for i, v in enumerate(kw['references'].values(), 1)} 

    kw = util.remove_undefined(kw)
    doc_html = template_obj.render(**kw)

    return doc_html
 





###########################################################################################
"""

███████  ██████  ██████  ███    ███  █████  ████████ 
██      ██    ██ ██   ██ ████  ████ ██   ██    ██    
█████   ██    ██ ██████  ██ ████ ██ ███████    ██    
██      ██    ██ ██   ██ ██  ██  ██ ██   ██    ██    
██       ██████  ██   ██ ██      ██ ██   ██    ██    
                                                     
"""
###########################################################################################

class html_renderer(BaseFormatter):

    def __init__(self):
        self.cnt_img = 0
        self.cnt_table = 0

        super().__init__()

    def digest_text(self, **kwargs):
        label = kwargs.get('label', '')
        content = kwargs.get('content', kwargs.get('children'))
        color = kwargs.get('color', '')
        if color:
            color = f'color:{color};'

        if label:
            return f'<div style="min-width:100;{color}">{label}</div><div style="{color}">{content}</div>'
        else:
            if color:
                return f'<div style="{color}">{content}</div>'
            else:
                return f'<div>{content}</div>'
    
    
    def digest_latex(self, **kwargs):
        if can_run_pandoc():
            return pandoc_convert(kwargs.get('children', ''), 'latex', 'html')
        else:
            s = 'native backend can not convert latex to html and no pandoc is available. Falling back to show as verbatim'
            warnings.warn(s)
            return '<br>' + self.digest_text(children='Warning! ' + s, color='purple') + self.digest_verbatim(**kwargs)    

    
    def digest_markdown(self, **kwargs):
        label = kwargs.get('label', '')
        content = kwargs.get('content', kwargs.get('children'))
        color = kwargs.get('color', '')
        use_pandoc = kwargs.get('use_pandoc', 0)

        if color:
            color = f'color:{color};'

        parts = []
        if label:
            parts += [
                f'<div style="min-width:100;{color}">{label}</div>',
                '<hr/>'
            ]

        if use_pandoc and can_run_pandoc():
            s = pandoc_convert(content, 'markdown', 'html')
        else:
            s = markdown.markdown(content)

        fun = lambda x:  f'<div style="{color}">{x}</div>' if color else f'<div>{x}</div>'
        parts += [fun(s)]
        return '\n\n'.join(parts)
    

    def digest_verbatim(self, **kwargs):
        label = kwargs.get('caption', kwargs.get('label', ''))
        content = kwargs.get('content', kwargs.get('children'))
        color = kwargs.get('color', '')
        if color:
            color = f'color:{color};'

        j = content
        children = [
            f'<div style="min-width:100;{color}">{label}</div>',
            f'<pre style="white-space: pre-wrap; margin: 15px; margin-left: 25px; padding: 10px; border: 1px solid gray; border-radius: 3px;">{j}</pre>'
        ]
        return '\n\n'.join(children)

        
    def digest_image(self, **kwargs):
        imageblob = kwargs.get('imageblob', None)
        imgname = kwargs.get('children', '')
        width = kwargs.get('width', 0.8)
        caption = kwargs.get('caption', "")

        if width is None:
            width = 0.8
            
        if imageblob is None:
            imageblob = ''

        s = imageblob.decode("utf-8") if isinstance(imageblob, bytes) else imageblob
        if not s.startswith('data:image'):
            s = 'data:image/png;base64,' + s
        
        children = [f"<div style=\"width: 100%; text-align: center;\"><img class=\"pyd-image\" data-img-no=\"{self.cnt_img}\" data-img-name=\"{imgname}\" src=\"{s}\" style=\"max-width:{int(width*100)}%;display: inline-block;\"></img></div>"]

        if caption:
            self.cnt_img += 1
            children += [f'<div style="width: 100%; text-align: center;"><span style="min-width:100;display: inline-block;"><b>Figure {self.cnt_img}: </b>{caption}</span></div>']

        return '\n\n'.join(children)

    def digest_table(self, children=None, **kwargs) -> str:
        borders = kwargs.get('borders', None)
        if borders is None:
            borders = True
        caption = kwargs.get('caption', '')
        if not caption:
            caption = ''

        head, mat = self._map_table2mat(children=children, **kwargs)
        lines = []
        st = ' style="border: 1px solid black;"' if borders else ''

        lines.append('<table style="border-collapse: collapse; margin-left: auto; margin-right: auto;">')
        lines.append("  <tr>")
        lines += [f"    <th{st}>{h}</th>" for h in head]
        lines.append("  </tr>")
        for row in mat:
            lines.append("  <tr>")
            lines += [f"    <td{st}>{cell}</td>" for cell in row]
            lines.append("  </tr>")

        lines.append("</table>")

        body = '\n'.join(lines)
        txt = f'<div>{body}</div>'

        if caption:
            self.cnt_table += 1
            txt += f'\n<div style="text-align: center;"><span style="min-width:100;display: inline-block;"><b>Table {self.cnt_table}: </b>{caption}</span></div>'

        return txt
        
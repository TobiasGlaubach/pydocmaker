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



def get_default_html_template(as_string=False):
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


    template_obj, attachments = _handle_template(template)
    
    kw = copy.deepcopy(template_params)

    assert not ('body' in kw), f'the "body" keyword is an invalid keyword for templates as it is reserved for the document body.'
    kw['body'] = body
    
    if 'applicables' in kw:
        kw['applicables'] = {i:v for i, v in enumerate(kw['applicables'].values(), 1)} 
    if 'references' in kw:
        kw['references'] = {i:v for i, v in enumerate(kw['references'].values(), 1)} 

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
            return '<br>' + self.digest_text(children='Warning! ' + s, color='purple') + html_renderer.digest_verbatim(**kwargs)    

    
    def digest_markdown(self, **kwargs):
        label = kwargs.get('label', '')
        content = kwargs.get('content', kwargs.get('children'))
        color = kwargs.get('color', '')
        if color:
            color = f'color:{color};'

        parts = []
        if label:
            parts += [
                f'<div style="min-width:100;{color}">{label}</div>',
                '<hr/>'
            ]
        
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

    
    def digest_image(self, imageblob=None, children='', width=0.8, caption="", **kwargs):       
        
        if imageblob is None:
            imageblob = ''

        s = imageblob.decode("utf-8") if isinstance(imageblob, bytes) else imageblob
        if not s.startswith('data:image'):
            s = 'data:image/png;base64,' + s
        
        children = [f"<div style=\"width: 100%; text-align: center;\"><img src=\"{s}\" style=\"max-width:{int(width*100)}%;display: inline-block;\"></img></div>"]

        if caption:
            children += [f'<div style="width: 100%; text-align: center;"><span style="min-width:100;display: inline-block;"><b>caption: </b>{caption}</span></div>']

        return '\n\n'.join(children)

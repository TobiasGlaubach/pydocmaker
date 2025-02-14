from collections import namedtuple
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

try:
    from pydocmaker.backend.baseformatter import BaseFormatter
except Exception as err:
    from .baseformatter import BaseFormatter
    
try:
    from pydocmaker.backend.pandoc_api import can_run_pandoc, pandoc_convert
except Exception as err:
    from .pandoc_api import can_run_pandoc, pandoc_convert
    



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


def convert(doc:List[dict], **kwargs):
    tmp = doc.values() if isinstance(doc, dict) else doc
    return html_renderer().format(tmp)


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

    def digest_line(self, **kwargs):
        return self.digest_text(**kwargs)
    
    
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
            
        # s = f'<pre disabled=true style="width:90%; min-height:200px; overflow-x: scroll; overflow-y: none; margin:5px;display:block;font-family: Lucida Console, Courier New, monospace;font-size: 0.8em;">\n\n{content}\n\n</pre>'
        #s = f'<span style="display:block;" class="note">\n\n{content}\n\n</span>'
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


        if not children:
            uid = (id(imageblob) + int(time.time()) + random.randint(1, 100))
            children = f'image_{uid}.png'

        s = imageblob.decode("utf-8") if isinstance(imageblob, bytes) else imageblob
        if not s.startswith('data:image'):
            s = 'data:image/png;base64,' + s
        
        if children:
            children = [
                # f'<div style="margin-top: 1.5em; width: 100%; text-align: center;"><span style="min-width:100;display: inline-block;"><b>image-name: </b>{children}</span></div>',
            ]
        else:
            children = []
        
        children += [    
            f"<div style=\"width: 100%; text-align: center;\"><img src=\"{s}\" style=\"max-width:{int(width*100)}%;display: inline-block;\"></img></div>",
        ]

        if caption:
            children.append(f'<div style="width: 100%; text-align: center;"><span style="min-width:100;display: inline-block;"><b>caption: </b>{caption}</span></div>')
        
        # children = dcc.Upload(id=self.mkid('helper_uploadfile'), children=children, multiple=False, disable_click=True)

        return '\n\n'.join(children)

    def digest_iterator(self, **kwargs):
        content = kwargs.get('content', kwargs.get('children'))
        return f'\n\n'.join([f'<div>{c}</div>' for c in content])

    
    def format(self, doc:list):
        return '\n\n'.join([self.digest(dc) for dc in doc])
    
    def handle_error(self, err, el) -> list:
        txt = 'ERROR WHILE HANDLING ELEMENT:\n{}\n\n'.format(el)
        if not isinstance(err, str):
            tb_str = '\n'.join(traceback.format_exception(type(err), value=err, tb=err.__traceback__, limit=5))
            txt += tb_str + '\n'
        else:
            txt += err + '\n'
        txt = f'\n<pre style="margin: 15px; margin-left: 25px; padding: 10px; border: 1px solid gray; border-radius: 3px; color: red;">\n{txt}\n</pre>\n'

        return txt
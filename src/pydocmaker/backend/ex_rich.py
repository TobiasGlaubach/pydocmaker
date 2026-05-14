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
from typing import List


try:
    from pydocmaker.backend.baseformatter import BaseFormatter, _handle_template
except Exception as err:
    from .baseformatter import BaseFormatter, _handle_template
    
    
try:
    from pydocmaker.backend.pandoc_api import can_run_pandoc, pandoc_convert
except Exception as err:
    from .pandoc_api import can_run_pandoc, pandoc_convert

try:
    from pydocmaker.util import _raise_missing
except Exception as err:
    from ..util import _raise_missing
    
try:
    from rich import box
    from rich.console import Console, Group
    from rich.text import Text
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.table import Table
    from rich.align import Align

except ImportError:
    Console = None




# # Define colors that are dark enough to be seen on white
# light_bg_theme = Theme({
#     "info": "bold blue",
#     "warning": "bold magenta",
#     "danger": "bold red",
#     "success": "bold green",
#     "custom": "black on #EEEEEE" # Dark text on light grey
# })

import datetime

CONSOLE_WIDTH_MAX = 200

"""

 ██████  ██████  ███    ██ ██    ██ ███████ ██████  ████████ 
██      ██    ██ ████   ██ ██    ██ ██      ██   ██    ██    
██      ██    ██ ██ ██  ██ ██    ██ █████   ██████     ██    
██      ██    ██ ██  ██ ██  ██  ██  ██      ██   ██    ██    
 ██████  ██████  ██   ████   ████   ███████ ██   ██    ██    
                                                             
                                                                                                                                                                                                                                       
"""


def convert(doc:List[dict], stream=None, title:str=None, embed_images=True, **kwargs):
    if Console is None:
        raise ImportError('rich library is not installed. Please install it to use the rich backend.')
        
    if title is None:
        title = f'{datetime.datetime.now().strftime("%Y-%m-%d %H%M")} my-pydoc'
    unknown_params = kwargs
    if unknown_params:
        warnings.warn(f'Unknown parameters passed: {unknown_params=}')

    tmp = list(doc.values()) if isinstance(doc, dict) else doc
    rr = rich_renderer(stream=stream, embed_images=embed_images, theme=None)
    parts = rr.format(tmp)
    #style =  Style(bgcolor='#FFFFFF')
    rr.console.print(Panel(Group(*parts), title=title))

    return ''
 


###########################################################################################
"""

███████  ██████  ██████  ███    ███  █████  ████████ 
██      ██    ██ ██   ██ ████  ████ ██   ██    ██    
█████   ██    ██ ██████  ██ ████ ██ ███████    ██    
██      ██    ██ ██   ██ ██  ██  ██ ██   ██    ██    
██       ██████  ██   ██ ██      ██ ██   ██    ██    
                                                     
"""
###########################################################################################

class rich_renderer(BaseFormatter):

    def __init__(self, stream=None, embed_images=True, theme=None):
        self.cnt_img = 0
        self.cnt_table = 0

        self.embed_images = embed_images
        self.stream = stream
        self.console = Console(file=stream, theme=theme)
        if self.console.width > CONSOLE_WIDTH_MAX:
            self.console.width = CONSOLE_WIDTH_MAX

        super().__init__()

    def digest_str(self, el):
        return Text(str(el))
    
    def digest_text(self, **kwargs):
        label = kwargs.get('label', None)
        content = kwargs.get('content', kwargs.get('children'))
        color = kwargs.get('color', '')
        
        part = Text(content, style=color)
        if label:
            part = Panel.fit(part, title=label, style=color)
        
        return part

    
    def digest_latex(self, **kwargs):
        if can_run_pandoc():
            kw = {k:v for k, v in kwargs.items() if k != 'children'}
            kw['children'] = pandoc_convert(kwargs.get('children', ''), 'latex', 'markdown')
            return self.digest_markdown(**kw)
        else:
            s = 'rich text backend can not parse latex and no pandoc is available. Falling back to show as verbatim'
            warnings.warn(s)
            a = self.digest_text(children=f'Warning! {s}', color='purple') 
            b = self.digest_verbatim(**kwargs)    
            return Group(a, b)
        
    
    def digest_markdown(self, **kwargs):
        label = kwargs.get('label', None)
        content = kwargs.get('content', kwargs.get('children'))
        color = kwargs.get('color', None)
        use_pandoc = kwargs.get('use_pandoc', 0)

        part = Markdown(content.strip(), style=color)
        if label:
            part = Panel.fit(part, title=label, style=color)
            part = Group('', part, '\n')
        return part

    def digest_iterator(self, **kwargs):
        content = kwargs.get('children', kwargs.get('content'))
        return Group(*[self.digest(c) for c in content])

    def digest_verbatim(self, **kwargs):
        label = kwargs.get('label', None)
        content = kwargs.get('content', kwargs.get('children'))
        color = kwargs.get('color', '')
        
        part = Align(Panel.fit(Text(content, style=color), title=label, style=color), 'center')
        return Group('', part, '\n')
    
        
    def digest_image(self, **kwargs):
        

        imageblob = kwargs.get('imageblob', None)
        children = kwargs.get('children', '')
        width = kwargs.get('width', None)
        caption = kwargs.get('caption', "")
        color = kwargs.get('color', '')

        if imageblob is None:
            imageblob = ''

        s = imageblob.decode("utf-8") if isinstance(imageblob, bytes) else imageblob
        if not s.startswith('data:image'):
            s = 'data:image/png;base64,' + s
        
        self.cnt_img += 1
        if caption:
            
            label = f'Figure {self.cnt_img}: {caption}'
        elif children: 
            label = f'Figure {self.cnt_img}: name={children}'
        else: 
            label = f'Figure {self.cnt_img}'

        if imageblob and self.embed_images:
            from PIL import Image
            from rich_pixels import Pixels

            if isinstance(imageblob, str):
                if ';base64, ' in imageblob:
                    imageblob = imageblob.replace(';base64, ', ';base64,')

                imageblob = imageblob.encode("utf8")

            data = imageblob.split(b";base64,")[-1]
            bts = base64.decodebytes(data)
            image = Image.open(io.BytesIO(bts))
            (w, h) = image.size
            if not width is None:
                # width is a fraction of available console size
                w_default = max(self.console.width-10, 10)
                wnew = int(w_default * width)
                hnew = int(h * wnew/w)
                size = (wnew, hnew)
            elif w > max(self.console.width-10, 10):
                # no specific size given, but image size bigger 
                # than console -> downscale
                wnew = max(self.console.width-10, 10)
                hnew = int(h * wnew/w)
                size = (wnew, hnew)
            else:
                # nothing given and image fits in colsole size
                size = None # -> keep original size

            # img2 = image.resize((w_default, hnew))
            part = Pixels.from_image(image, resize=size)
        elif imageblob and not self.embed_images:
            if isinstance(imageblob, str):
                s = imageblob
            else:
                s = imageblob.decode()
            if len(s) > 60:
                sshort = f'{s[:30]}...{s[-30:]}'
            else:
                sshort = s
            part = Text(f'\nPLACEHOLDER FOR IMAGE:\n name: {children}\n base64 size: {len(s)}\n content: {sshort}\n', style='gray')
        else:
            if not children:
                c = f"<<EMPTY_IMAGE>>"
            else:
                c = f"<<EMPTY_IMAGE with name={children}>>"
            part = Text(c)
        part = Panel(Align(part, 'center'), subtitle=label, style=color)
        return Group('', part, '\n')

    def digest_table(self, children=None, **kwargs) -> str:
        borders = kwargs.get('borders', None)
        if borders is None:
            borders = True
        caption = kwargs.get('caption', '')
        if not caption:
            caption = ''
 
        head, mat = self._map_table2mat(children=children, **kwargs)
        
        
        table = Table(title=caption, 
                      show_header = True if head else False, 
                      box=box.HEAVY_HEAD if borders else None)

        for h in head:
            table.add_column(h)
        
        for row in mat:
            table.add_row(*row)
        
        part = Align(table, 'center')
        return Group('', part, '\n')
    
        
    def format(self, doc:list) -> str:
        if hasattr(doc, 'dump'):
            doc = doc.dump()
        if not isinstance(doc, list):
            doc = [doc]
        return [self.digest(p) for p in doc]
    
    
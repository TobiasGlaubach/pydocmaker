import base64, time, io, copy, json, traceback, hashlib, markdown, re
from typing import List

try:
    from pydocmaker.backend.baseformatter import BaseFormatter
except Exception as err:
    from .baseformatter import BaseFormatter

def convert(doc:List[dict], embed_images=True):

    formatter = DocumentMarkdownFormatter(embed_images=embed_images)
    s = formatter.digest(doc)
    return s

class DocumentMarkdownFormatter(BaseFormatter):

    def __init__(self, embed_images=True) -> None:
        self.embed_images = embed_images

    def digest_latex(self, children: str, **kwargs):
        return self.digest_verbatim(children=children, **kwargs)
    
    def digest_markdown(self, children='', **kwargs) -> list:
        return children
    
    def digest_table(self, children=None, **kwargs) -> str:
        borders = kwargs.pop('borders', None)
        if borders is None:
            borders = True
        caption = kwargs.pop('caption', '')
        if not caption:
            caption = ''

        head, mat = self._map_table2mat(children=children, **kwargs)
        striprow = lambda x: [str(xx).strip() for xx in x]

        header = '| ' + ' | '.join(striprow(head)) + ' |'
        separator = '|' + (' --- |' if borders else ' ---:|') * len(head)
        rows = ['| ' + ' | '.join(striprow(row)) + ' |' for row in mat]
        body = '\n'.join([header, separator] + rows)
    
        if caption:
            body += f'\n\n**Caption:** {caption}\n'

        return body

   
        
    def digest_image(self, **kwargs) -> list:
        
        filename = kwargs.get('filename')
        caption = kwargs.get('caption')
        imageblob = kwargs.get('imageblob')
        
        description = ''

        if filename:
            description += ' ' + str(filename)
        if caption:
            description += ' ' + str(caption)

        if not description:
            description = f'{time.time_ns()}_embedded_image'

        lines = []
        lines.append('')

        if filename:    
            lines.append(f'*filename:* {filename}')
            lines.append('')
        
        lines.append('')

        # HACK: handle non PNG type properly!
        if imageblob.startswith('data:image/png;base64,'):
            i = imageblob
        else:
            i = 'data:image/png;base64,' + str(imageblob)

        if self.embed_images:
            lines.append(f'![{description}]({i})')
        else:
            i = i[:35] + f'... (n={len(i)-35} more chars hidden))' if len(i) > 35 else i
            lines.append(f'#[{description}]({i}')
        lines.append('')

        if caption:
            lines.append(f'*caption:* {filename}')
            lines.append('')

        return '\n'.join(lines)
    

    def digest_verbatim(self, children='', **kwargs) -> list:
        if isinstance(children, str):
            txt = children.strip('\n')
        else:
            txt = self.digest(children)
        s = f"""```\n{txt}\n```"""
        return s

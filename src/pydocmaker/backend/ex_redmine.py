import base64, time, io, copy, json, traceback, hashlib, markdown, re
from typing import List

try:
    from pydocmaker import util
except Exception as err:
    from .. import util

    
try:
    from pydocmaker.backend.baseformatter import BaseFormatter
except Exception as err:
    from .baseformatter import BaseFormatter
    
try:
    from pydocmaker.backend.pandoc_api import can_run_pandoc, pandoc_convert
except Exception as err:
    from .pandoc_api import can_run_pandoc, pandoc_convert
    

def convert(doc:List[dict], with_attachments=True, aformat_redmine=False):

    formatter = DocumentRedmineFormatter(aformat_redmine=aformat_redmine)
    text = formatter.digest(doc)
    if with_attachments:
        if aformat_redmine:
            attachments = [v for v in formatter.attachments]
        else:
            attachments = {'doc.json': json.dumps(doc, cls=util.CommonJSONEncoder, indent=2)}
            for path, content in formatter.attachments:
                attachments[path] = content
        return text, attachments
    else:
        return text
    
def im2file(dc_img):
    mapper = {
            '/' : 'jpg',
            'i' : 'png',
            'R' : 'gif',
            'U' : 'webp'
        }
    filename = dc_img.get('children', None)
    imageblob = dc_img.get('imageblob')

    if not filename: 
        if ';base64' in imageblob:
            ext = imageblob.split(';base64')[0].split('/')[-1]
        elif mapper.get(imageblob[0], None):
            ext = mapper.get(imageblob[0], None)
        else:
            raise KeyError('extension could not be determined from imageblob')

        #filename = f'img_{time.time_ns()}_{str(id(dc))[-4:]}.{ext}'
        filename = f"img_{hashlib.md5(imageblob.encode('utf-8')).hexdigest()}.{ext}"
        
    data = imageblob.split('base64,')[-1]
    content = io.BytesIO(base64.b64decode(data))
    return filename, content

def im2attachment(dc_img, filename, content):
    
    description = dc_img.get('caption', '')
    if not description: 
        description = filename

    assert isinstance(content, (bytes, io.BytesIO)), f'content must be type bytes but was {type(content)=} {content=}'
    content = io.BytesIO(content) if isinstance(content, bytes) else content
    return {"path" : content, "filename" : filename, "content_type" : "application/octet-stream", "description": description}


def handle_color(func):
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        color = kwargs.get('color', '')
        if color:
            result = '%{color:' +  str(color) + '}' + str(result) + '%'
        return result
    
    return wrapper


class DocumentRedmineFormatter(BaseFormatter):

    def __init__(self, aformat_redmine=True, out_format='textile') -> None:
        self.attachments = []
        self.out_format = out_format
        self.aformat_redmine = aformat_redmine

    def handle_error(self, err, el) -> list:
        txt = 'ERROR WHILE HANDLING ELEMENT:\n{}\n\n'.format(el)
        if not isinstance(err, str):
            tb_str = '\n'.join(traceback.format_exception(type(err), value=err, tb=err.__traceback__, limit=5))
            txt += tb_str + '\n'
        else:
            txt += err + '\n'
        txt = f"""<pre style="margin: 15px; margin-left: 25px; padding: 10px; border: 1px solid gray; border-radius: 3px; color: red;">\n{txt}\n</pre>"""

        return txt

    @handle_color
    def digest_markdown(self, children='', **kwargs) -> str:
        if can_run_pandoc():
            return pandoc_convert(children, 'markdown', 'textile')
        else:
            return children

    @handle_color
    def digest_text(self, children='', **kwargs) -> str:
        return children
    

    def digest_image(self, **kwargs) -> str:
        filename, content = im2file(kwargs)
        attachment = im2attachment(kwargs, filename, content)

        filename = attachment.get('filename')
        caption = attachment.get('description')
        if self.aformat_redmine:
            self.attachments.append(attachment)
        else:
            self.attachments.append((filename, content.read()))

        s = f'!{filename}({caption})!\n**IMAGE:** attachment:"{filename}" {caption}\n'
        return s
    
    def digest_latex(self, children='', **kwargs) -> str:
        if can_run_pandoc():
            return pandoc_convert(children, 'latex', 'textile')
        else:
            return self.digest_verbatim(children=children, **kwargs)
        
    @handle_color
    def digest_verbatim(self, children='', **kwargs) -> str:
        if isinstance(children, str):
            txt = children.strip('\n')
        else:
            txt = self.digest(children)
        color = kwargs.get('color', 'black')
        s = f"""<pre style="margin: 15px; margin-left: 25px; padding: 10px; border: 1px solid gray; border-radius: 3px;color={color}">{txt}</pre>"""
        return s

    
    def digest_table(self, children=None, **kwargs) -> str:
        borders = kwargs.pop('borders', None)
        if borders is None:
            borders = True
        caption = kwargs.pop('caption', '')
        if not caption:
            caption = ''

        head, mat = self._map_table2mat(children=children, **kwargs)
        striprow = lambda x: [str(xx).strip() for xx in x]

        header = '|_.' + ' |_.'.join(striprow(head)) + ' |'
        
        rows = ['| ' + ' |'.join(striprow(row)) + ' |' for row in mat]
        body = '\n'.join([header] + rows)
        if caption:
            body += f'\n\nCaption: {caption}\n'
        return body
    
   
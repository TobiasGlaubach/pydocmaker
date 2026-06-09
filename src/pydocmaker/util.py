import copy
import enum
import json
import os
from pathlib import Path, PurePath
import re
import tempfile
from typing import Any, Dict
import io, datetime
import time
import random
import string
from enum import Enum
import re

from jinja2 import Undefined
UNDEFINED_PREFIX = '__jinja2.Undefined'

import logging
# Configure once
logging.basicConfig(
    level=logging.INFO,
    # format='[%(asctime)s | %(levelname)-8s | %(filename)-15s:%(lineno)4d] %(message)s',
    format='[%(asctime)s | %(levelname)-5s | %(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

log = logging.getLogger("pydocmaker")


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

colors_dc = {
    'purple': bcolors.HEADER.value,
    'blue': bcolors.OKBLUE.value,
    'cyan': bcolors.OKCYAN.value,
    'green': bcolors.OKGREEN.value,
    'warning': bcolors.WARNING.value,
    'red': bcolors.FAIL.value,
    'endc': bcolors.ENDC.value,
    'bold': bcolors.BOLD.value,
    'underline': bcolors.UNDERLINE.value
}

colors_dc.update({e.name:e.value for e in bcolors})
colors_dc.update({e.name.lower():e.value for e in bcolors})
colors_dc.update({e.value:e.value for e in bcolors})

def txtcolor(s:str, color:str):
    c = colors_dc.get(str(color).lower(), '')
    if c:
        return str(c) + s + str(bcolors.ENDC.value)
    else:
        return s

def split_camel_case(st:str):
    words = []
    s, last, last2, word = list(st), None, None, ''
    while s:
        now = s.pop(0)
        if not now.isalnum(): # split by non alpha numeric
            if word:
                words.append(word)
                word = ''
            last, last2 = None, None
        elif last2 is not None and last is not None and now.islower() and last.isupper() and last2.isupper():
            n, word = word[-1], word[:-1]
            words.append(word)
            word, last, last2 = n + now, None, None
        elif last is not None and now.isupper() and last.islower():
            words.append(word)
            word, last = now, None
        
        else:
            word += now
            last2 = last
            last = now
    if word:
        words.append(word)
    return words

def flatten_list(lst):
    result = []
    for i in lst:
        if isinstance(i, list):
            result.extend(flatten_list(i))
        elif isinstance(i, dict) and i.get('typ', '').startswith('iter'):
            result.extend(flatten_list(i['children']))
        else:
            result.append(i)
    return result

def generate_unique_id():
    random_chars = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
    return f"{int(time.time())}_{random_chars}"

def get_page_title(docname):
    docname = next(iter(docname)) if not isinstance(docname, str) else docname
    return 'wikidoc_' + docname.replace('.', '_').replace(' ', '_').replace('|', '_')
    


def path2attachment(path, filename):
    return {"path" : path, "filename" : filename, "content_type" : "application/octet-stream"}




def upload_report_to_redmine(doc, redmine, project_id, report_name=None, page_title=None, force_overwrite=False, verb=True):
    """Uploads a report generated from a Doc object to a Redmine wiki page.

    Args:
        doc (Doc): The Doc object containing the report data.
        redmine (redminelib.Redmine): A Redmine connection object.
        project_id (str): The ID of the Redmine project where the report should be uploaded.
        report_name (str, optional): The name of the report. If not provided, the follwoing schema `%Y%m%d_%H%M_exported_report` will be used.
        page_title (str, optional): The title of the Redmine wiki page. If not provided, it will be derived from the report name.
        force_overwrite (bool, optional): Whether to overwrite an existing page with the same title. Defaults to False.
        verb (bool, optional): Whether to print verbose output during upload. Defaults to True.

    Returns:
        redminelib.WikiPage: The uploaded Redmine wiki page object.

    Raises:
        AssertionError: If any of the `doc`, `project_id` or `redmine` arguments is None or empty.
    """

    if not report_name:
        report_name = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M') + '_exported_report'
    
    assert doc, 'input can not be none or empty'
    assert project_id, 'project_id can not be none or empty'
    assert isinstance(project_id, (str, int)), f'project_id must be str or int but was {type(project_id)=} {project_id=}'
    assert redmine, 'redmine can not be none or empty'
    assert report_name, 'report_name can not be none or empty'


    with tempfile.TemporaryDirectory() as tmpdir:
        dc_written = doc.export_all(report_name=report_name, dir_path=tmpdir)
        s, attachments_lst = doc.to_redmine()

        attachments = []

        # write all the io.BytesIO to the temp folder and add to be uploaded
        for dc_attachment in attachments_lst:
            abspath = os.path.join(tmpdir, re.sub(r"[^a-zA-Z0-9_.-]", "", dc_attachment['filename']))
            with open(abspath, 'wb') as fp:
                fp.write(dc_attachment['path'].read())
            attachments.append(path2attachment(abspath, os.path.basename(abspath)))
        
    
        for abspath, success in dc_written.items():
            if 'redmine' in abspath:
                continue
            assert success, f'{abspath=} failed to be saved!' 
            attachments.append(path2attachment(abspath, os.path.basename(abspath)))
        
        if not page_title:
            page_title = get_page_title(report_name)

        text = f'h1. {report_name}\n\n' + s

        try:
            page = redmine.wiki_page.get(page_title, project_id=project_id, include=['attachments'])
        except Exception as err:
            if 'ResourceNotFoundError' in str(type(err)):
                page = None
            else:
                raise

        
        #print(page)
        if not page:
            is_new = True
            page = redmine.wiki_page.new()
        else:
            is_new = False
        
        if not is_new and not force_overwrite:
            a_dc = {a.filename:a for a in page.attachments}
            to_upload = []
            for at in attachments:
                # check file sizes for images... if same name and same size... skip the upload
                n_new = os.path.getsize(at.get('path'))
                filename = at.get('filename')
                ext = filename.split('.')[-1]
                if ext in 'jpg png gif webp json'.split():
                    a_old = a_dc.get(filename, None)
                    if not a_old is None:
                        
                        if n_new == a_old.filesize:
                            if verb:
                                print(f'{filename} | {n_new=} | {a_old.filesize=} | Equal?: {n_new == a_old.filesize} --> SKIPPING!')
                            continue
                        else:
                            if verb:
                                print(f'{filename} | {n_new=} | {a_old.filesize=} | Equal?: {n_new == a_old.filesize} --> UPLOADING!')
                if verb:
                    print(filename, ' --> UPLOADING!')
                to_upload.append(at)

            filenames = [f.get('filename') for f in to_upload]
            to_delete = [a for a in page.attachments if a.filename in filenames]

            
        else:
            to_upload = attachments
            to_delete = []

        if force_overwrite:
            to_delete = [a for a in page.attachments]

        for a in to_delete:
            a.delete()
            
        if is_new:
            page.project_id = project_id
            page.title = page_title
        

        page.text = text
        page.uploads = to_upload
        page.comments = f'updated at {datetime.datetime.utcnow().isoformat()}'
        page.save()

        return page.url if page else ''




def filename2identifier(filename):
    """Converts a filename to a valid identifier by:
    1. Stripping the file extension
    2. Replacing any non-alphanumeric character with an underscore
    3. Ensuring it doesn't start with a digit
    """
    name = filename.rsplit('.', 1)[0]
    identifier = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if identifier[0].isdigit():
        identifier = '_' + identifier
        
    return identifier

class _raise_missing:
    def __init__(self, *args, **kwargs):
        raise ImportError('latex package not found. This needs the full pydocmaker installation. Please install pydocmaker with "pip install pydocmaker[full]" to use this function.')
    
    @classmethod
    def __getattr__(self, name):
        raise ImportError('latex package not found. This needs the full pydocmaker installation. Please install pydocmaker with "pip install pydocmaker[full]" to use this function.')

def bytes_path_exists(b: bytes, encoding: str = "utf-8") -> bool:
    """Check if a bytes literal refers to an existing file/directory."""
    try:
        if isinstance(b, bytes):
            b = b.decode()

        return Path(b).exists()
    except (UnicodeDecodeError, OSError):
        return False
    
def get_inp_context(default_name='main', context:dict=None, **kw):
    try:
        context = context or {}
        inp = kw.get('input')
        
        if not isinstance(inp, dict):
            inp = {default_name: inp}
        
        inp.update(context)
        context = {}

        for k, v in inp.items():
            if isinstance(v, Path) and v.exists():
                context[k] = v.read_bytes()
            elif isinstance(v, str) and os.path.exists(v):
                context[k] = Path(v).read_bytes()
            elif isinstance(v, str):
                context[k] = v.encode()
            elif isinstance(v, bytes):
                context[k] = v
            else:
                context[k] = str(v)
        return context    
    except Exception as err:
        return {}


def undefined_obj2str(obj:Undefined):
    return undefined_name2str(obj.name)

def undefined_name2str(name, sep=','):
    return f'{UNDEFINED_PREFIX}{sep}{name}'

def undefined_str2obj(s:str):
    if isinstance(s, str) and s.startswith(UNDEFINED_PREFIX):
        return Undefined(s.split(',')[-1])
    return s

def remove_undefined(params):
    _filt = lambda v: isinstance(v, Undefined) or (isinstance(v, str) and v.startswith(UNDEFINED_PREFIX))
    return {k:v for k,v in params.items() if not _filt(v)}

class MyJSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        # Call parent constructor with custom object_hook
        super().__init__(object_hook=self.custom_object_hook, *args, **kwargs)
    
    def custom_object_hook(self, dct):
        """
        Custom hook to transform decoded objects.
        """
        for key, value in dct.items():
            if isinstance(value, str) and value.startswith(UNDEFINED_PREFIX):
                dct[key] = undefined_str2obj(value)
        return dct

class CommonJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Exception):
            return {
                "type": type(obj).__name__,
                "message": str(obj),
                "args": obj.args,
                "module": type(obj).__module__,
                "full_name": f"{type(obj).__module__}.{type(obj).__name__}"
            }
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, enum.Enum):
            return obj.value
        if isinstance(obj, bytes):
            return obj.decode(errors="replace")
        if isinstance(obj, type):
            return f"<class '{type(obj).__module__}.{type(obj).__name__}'>"
        if hasattr(obj, 'shape') and hasattr(obj, 'tolist'): # numpy array
            return obj.tolist()
        if hasattr(obj, 'columns') and hasattr(obj, 'index') and hasattr(obj, 'to_dict'): # pandas dataframe
            return obj.to_dict()
        if isinstance(obj, Undefined):
            return undefined_name2str(obj.name)
        
        return super().default(obj)



def limit_len(k, n_max =10, LR='L'):
    if k is None:
        return str(None)
    k = str(k)
    if LR == 'L':
        return k if len(k) < n_max else k[:n_max]+'...'
    else:
        return k if len(k) < n_max else '...' + k[-n_max:]
    

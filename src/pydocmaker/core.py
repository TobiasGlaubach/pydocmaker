from dataclasses import dataclass, field, is_dataclass
from collections import UserDict, UserList
import json, io
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any, Dict, List, BinaryIO, TextIO, Tuple, Union
import warnings
import zipfile

import base64
import copy

import subprocess
import os

import shlex

from .util import flatten_list, split_camel_case, upload_report_to_redmine


from .backend.ex_html import convert as to_html
from .backend.ex_docx import convert as to_docx
from .backend.ex_ipynb import convert as to_ipynb
from .backend.ex_tex import convert as to_tex
from .backend.ex_markdown import convert as to_markdown
from .backend.ex_redmine import convert as to_textile
from .backend.ex_tex import make_pdf as to_pdf_tex
from .backend.ex_tex import make_pdf_zip as to_pdf_zip
from .backend.ex_rich import convert as print_rich
from .backend.ex_typst import convert as to_typst, compile_with_typst as to_pdf_typst, test_typst_installed, compile_with_typst
from .backend.ex_tex import auto_escape_latex

from .backend.pdf_maker_tex import make_pdf_from_tex, config_latex_compiler_get, config_latex_compiler_set
from .backend import ex_docx

from .templating import DocTemplate

from .backend.pandoc_api import can_run_pandoc, pandoc_convert, pandoc_to_pdf

np = None
gImage = None

chapter_level = 1 # this is the level of heading to use for chapters which is equivalent to html <h1> to <h5> or whatever

_pdf_engine = None
_renderer_default = 'auto'

import logging

# Configure once
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s | %(levelname)-8s | %(filename)-15s:%(lineno)3d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

log = logging.getLogger(__name__)


def config_renderer_default_set(choice:str='auto'):
    """
    Sets the PDF engine to be used for generating PDF documents.

    Parameters:
    choice (str): The desired renderer for showing reports within python. Must be any of 'auto', 'rich', 'md', 'html', 'pdf'.
                  Default is 'auto'.

    Returns:
    str: The selected renderer_default.

    Raises:
    ValueError: If the provided choice is not one of the allowed options.
    """
    options = "auto rich md html pdf".split()
    choice = str(choice).lower()
    if not choice in options:
        raise ValueError(f'_renderer_default must be one of {options=} but was {choice=}')
    
    global _renderer_default
    _renderer_default = choice
    return _renderer_default

def config_renderer_default_get():
    global _renderer_default
    return _renderer_default



def config_pdf_engine_set(choice:str='typst'):
    """
    Sets the PDF engine to be used for generating PDF documents.

    Parameters:
    choice (str): The desired PDF engine. Must be one of 'tex', 'word', 'libreoffice', 'typst', or 'pandoc'.
                  Default is 'typst'.

    Returns:
    str: The selected PDF engine.

    Raises:
    ValueError: If the provided choice is not one of the allowed options.
    """
    options = "tex word libreoffice typst pandoc".split()
    choice = str(choice).lower()
    if not choice in options:
        raise ValueError(f'PDF engine must be one of {options=} but was {choice=}')
    
    global _pdf_engine
    _pdf_engine = choice
    return _pdf_engine


def config_pdf_engine_get():
    global _pdf_engine
    if _pdf_engine is None:
        config_pdf_engine_testset()
    return _pdf_engine


def config_pdf_engine_test(raise_on_error=True, force_reload=False):
    """
    tests the availability of the currently configured PDF engine.

    Args:
        raise_on_error (bool): If True, raises a ValueError if no valid compiler is found.
        force_reload (bool): If True, forces a reload of the PDF engine configuration.

    Returns:
        bool: True if a valid compiler is found, False otherwise.
    """
    res = False
    global _pdf_engine
    if _pdf_engine == 'typst':
        res = test_typst_installed()
    elif _pdf_engine == 'tex':
        res = config_latex_compiler_get()
    elif _pdf_engine == 'word':
        res = ex_docx.can_use_w32_word(force_reload=force_reload)
    elif _pdf_engine == 'libreoffice':
        res = ex_docx.can_use_libreoffice(force_reload=force_reload)
    elif _pdf_engine == 'pandoc':
        res = can_run_pandoc(force_retest=force_reload)
    else: ValueError(f'PDF engine must be one of "{"tex word libreoffice".split()}" but was "{_pdf_engine}"')

    if raise_on_error and not res:
        raise ValueError(f'No valid compiler found for pdf_engine="{_pdf_engine}"')
    
    return res



def config_pdf_engine_scan(force_reload=False, firstonly=False):
    """
    Configures the PDF engine and tests its availability.

    Args:
        raise_on_error (bool): If True, raises a ValueError if no valid compiler is found.
        force_reload (bool): If True, forces a reload of the PDF engine configuration.

    Returns:
        bool: True if a valid compiler is found, False otherwise.
    """
    res = []
    if test_typst_installed(): res.append('typst')
    if firstonly and res: return res[0]
    if config_latex_compiler_get(): res.append('tex')
    if firstonly and res: return res[0]
    if ex_docx.can_use_w32_word(force_reload=force_reload): res.append('word')
    if firstonly and res: return res[0]
    if ex_docx.can_use_libreoffice(force_reload=force_reload): res.append('libreoffice')
    if firstonly and res: return res[0]
    if config_latex_compiler_get() and can_run_pandoc(force_retest=force_reload): res.append('pandoc')
    if firstonly and res: return res[0]
    if firstonly and not res: return ''
    return res

def config_pdf_engine_testset():
    eng = config_pdf_engine_scan(firstonly=True)
    if eng:
        return config_pdf_engine_set(eng)
    else:
        global _pdf_engine
        _pdf_engine = ''

    
    
def is_notebook() -> bool:
    try:
        shell = get_ipython().__class__.__name__ # type: ignore
        if shell == 'ZMQInteractiveShell':
            return True   # Jupyter notebook or qtconsole
    except NameError:
        pass

    try:
        # Check if running in Google Colab
        import google.colab # type: ignore
        return True
    except ImportError:
        pass

    return False      # Probably standard Python interpreter


def show_pdf(pdf_bytes:bytes, width=1000, height=1200):
    """
    Display a PDF file within an IPython environment.

    This function takes a PDF file in bytes or base64 encoded string format and displays it within an IPython notebook.

    Parameters:
    pdf_bytes (bytes or str): The PDF file in bytes or base64 encoded string format.
    width (int, optional): The width of the IFrame in which the PDF is displayed. Default is 1000.
    height (int, optional): The height of the IFrame in which the PDF is displayed. Default is 1200.

    Raises:
    AssertionError: If the function is not called within an IPython environment.

    Example:
    >>> with open('example.pdf', 'rb') as file:
    ...     pdf_bytes = file.read()
    >>> show_pdf(pdf_bytes)
    """
    assert is_notebook(), 'can only show a PDF file within an ipython environment!'
    from IPython.display import display, IFrame 
    if isinstance(pdf_bytes, bytes):
        pdf_bytes = base64.b64encode(pdf_bytes)
    pdf_bytes = pdf_bytes.decode()
    if not pdf_bytes.startswith('data:application/pdf;base64,'):
        pdf_bytes = 'data:application/pdf;base64,' + pdf_bytes
    display(IFrame(pdf_bytes, width=width, height=height))


def _is_chapter(dc):
    global chapter_level
    pre='#' * chapter_level
    if not isinstance(dc, dict):
        return ''
    if not dc.get('typ') == 'markdown':
        return ''
    lines = dc.get('children', '').split('\n')
    if not len(lines) == 1:
        return ''
    if not lines[0].startswith(pre + ' '):
        return ''
    return lines[0].lstrip(pre).strip()

    

def make_png_imageblob(im_bytes:str):
    imageblob = 'data:image/png;base64,' + im_bytes
    return imageblob
    


class constr():
    """This is the basic schema for the main building blocks for a document"""

    # some aliases
    typalias = {
        'pre': 'verbatim',
        'metadata': 'meta',
        'md': 'markdown',
        'txt': 'text',
        'tex': 'latex', 
        'iterator': 'iter',
        'picture': 'image'
    }

    @staticmethod
    def meta(children='', data=None, **kwargs):
        data = {k:v for k,v in data.items()} if data else {}
        data.update(kwargs)
        return {
            'typ': 'meta',
            'children': children,
            'data': data,
        }
    
    @staticmethod
    def markdown(children='', color='', end=None):
        return {
            'typ': 'markdown',
            'children': children,
            'color': color,
            'end': end
        }
    
    @staticmethod
    def text(children='', color='', end=None):
        return {
            'typ': 'text',
            'children': children,
            'color': color,
            'end': end
        }
    
    @staticmethod
    def line(children='', color='', end=None):
        return {
            'typ': 'line',
            'children': children,
            'color': color,
            'end': '\n' if end is None else end
        }
    
    @staticmethod
    def latex(children='', color='', end=None):
        return {
            'typ': 'latex',
            'children': children,
            'color': color,
            'end': end
        }
    

    @staticmethod
    def verbatim(children='', color='', end=None):
        return {
            'typ': 'verbatim',
            'children': children,
            'color': color,
            'end': end
        }
    
    @staticmethod
    def iter(children:list=None, color='', end=None):
        return {
            'typ': 'iter',
            'children': [] if children is None else children,
            'color': color,
            'end': end
        }
    
    @staticmethod
    def table(children:list=None, color='', end=None, header=None, caption=None, n_cols=None, n_rows=None, borders=True):
        return {
            'typ': 'table',
            'children': children,
            'n_cols': n_cols,
            'n_rows': n_rows,
            'borders': borders,
            'header': header,
            'caption': caption,
            'color': color,
            'end': end,
        }
    
    @staticmethod
    def image(imageblob='', caption='', children='', width=None, color='', end=None):

        if not children:
            # HACK: need to get format somehow
            children = f'img_{time.time_ns()}.png'

        return {
            'typ': 'image',
            'children': re.sub(r"[^a-zA-Z0-9_.-]", '', children),
            'imageblob': imageblob.decode("utf-8") if isinstance(imageblob, bytes) else imageblob,
            'caption': caption,
            'width': width,
            'color': color,
            'end': end
        }
    

    @staticmethod
    def image_from_link(url, caption='', children='', width=None, color='', end=None):
        import requests
        assert url, 'need to give an URL!'

        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        
        mime_type = response.headers.get("Content-Type")
        assert mime_type.startswith('image'), f'the downloaded content does not seem to be of any image type! {mime_type=}'
        
        if not children:
            children = url.split('/')[-1]
            if children.startswith('File:'):
                children = children[len('File:'):]
        
        children = children.strip()
        
        if not caption and children:
            caption = children

        children = re.sub(r'[^a-zA-Z0-9._-]', '', children)

        if not '.' in children:
            children += '.' + mime_type.split('/')[-1]

        imageblob = base64.b64encode(response.content).decode('utf-8')
        return constr.image(imageblob=imageblob, children=children, caption=caption, width=width, color=color, end=end)
    


    @staticmethod
    def image_from_file(path, children='', caption='', width=None, color='', end=None):

        assert path, 'need to give a path!'

        if hasattr(path, 'read'):
            bts = path.read()
        else:
            with open(path, 'rb') as fp:
                bts = fp.read()
        
        assert bts and isinstance(bts, bytes), f'the loaded content needs to be of type bytes but was {bts=}'
        
        if not children:
            children = os.path.basename(path)
        
        if not caption and children:
            caption = children

        imageblob = base64.b64encode(bts).decode('utf-8')
        return constr.image(imageblob=imageblob, children=children, caption=caption, width=width, color=color, end=end)
        

    def image_from_fig(caption='', width=None, children=None, fig=None, color='', end=None, bbox_inches='tight', **kwargs):
        """convert a matplotlib figure (or the current figure) to a document image dict to later add to a document

        Args:
            caption (str, optional): the caption to give to the image. Defaults to ''.
            width (float, optional): The width for the image to have in the document None will let the individual formatter determine the width. Defaults to None.
            children (str, optional): A specific name/id to give to the image (will be auto generated if None). Defaults to None.
            fig (matplotlib figure, optional): the figure which to upload (or the current figure if None). Defaults to None.

        Returns:
            dict
        """
        if not 'plt' in locals():
            import matplotlib.pyplot as plt

        with io.BytesIO() as buf:
            if fig:
                fig.savefig(buf, format='png', bbox_inches=bbox_inches, **kwargs)
            else:
                plt.savefig(buf, format='png', bbox_inches=bbox_inches, **kwargs)
            buf.seek(0)   

            img = base64.b64encode(buf.read()).decode('utf-8')
        
        if children is None:
            id_ = str(id(img))[-2:]
            children = f'figure_{int(time.time())}_{id_}.png'

        return constr.image(imageblob = make_png_imageblob(img), children=children, caption=caption, width=width, color=color, end=end)


    @staticmethod
    def image_from_obj(img, caption = '', width=None, children=None, color='', end=None):
        """make a image type dict from given image of type matrix, filelike or PIL image

        Args:
            im (np.array): the image as NxMx
            caption (str, optional): the caption to give to the image. Defaults to ''.
            width (float, optional): The width for the image to have in the document None will let the individual formatter determine the width. Defaults to None.
            children (str, optional): A specific name/id to give to the image (will be auto generated if None). Defaults to None.

        Returns:
            dict with the results
        """
        global np, gImage

        if np is None:
            import numpy 
            np = numpy

        if gImage is None:
            from PIL import Image
            gImage = Image

        # 2D matrix as lists --> make nummpy array
        if isinstance(img, list) and img and img[0] and isinstance(img[0], list):
            img = np.array(img)

        # numpy array --> make PIL image
        if hasattr(img, 'shape') and len(img.shape) == 2:
            img = gImage.fromarray(img)
        
        # PIL image --> make filelike
        if hasattr(img, 'save'):
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)   
            img = buf

        # filepath --> make filelike
        if isinstance(img, str) and os.path.exists(img):
            if not children:
                children = os.path.basename(img)            
            img = open(img, 'rb')

        # file like --> make bytes
        if hasattr(img, 'read'):
            img.seek(0)   
            img = img.read()
        
        # bytes --> make b64 string
        if isinstance(img, bytes):
            img = base64.b64encode(img).decode('utf-8')

        if children is None:
            id_ = str(id(img))[-2:]
            children = f'image_{int(time.time())}_{id_}.png'

        return constr.image(imageblob = make_png_imageblob(img), children=children, caption=caption, width=width, color=color, end=end)

buildingblocks = 'text markdown image verbatim iter line latex meta'.split()



class Doc(UserList):
            
    """a collection of document parts to make a document (can be used like a list)"""

    DEFAULT_ADD_STRING_TYPE = 'markdown'
    EXPORT_ENGINES = ['md', 'html', 'typst', 'json', 'docx', 'textile', 'ipynb', 'tex', 'redmine', 'pdf']
    EXPORT_ENGINES_EXTENSIONS = {'md': '.md', 'html':'.html', 'typst': '.typ', 'json':'.json', 'docx': '.docx', 'textile': '.textile.zip', 'ipynb': '.ipynb', 'tex': '.tex.zip', 'pdf': '.pdf'}

    @staticmethod
    def load_json(path):
        """Load a JSON file and return a Doc object.

        Args:
            path (str or file-like object): The path to the JSON file or a file-like object.

        Returns:
            Doc: A Doc object initialized with the loaded JSON data.

        Raises:
            json.JSONDecodeError: If the JSON file is not valid.
            TypeError: If the loaded JSON object is not of type list.
        """
        if hasattr(path, 'read'): # test file pointer
            lst = json.load(path)
        else:
            with open(path, 'r') as fp:
                lst = json.load(fp)
        if not isinstance(lst, list):
            warnings.warn(f'The loaded json object is not of type list, but instead of type ({type(lst)=})')
        return Doc(lst)
    
    def __init__(self, initial_data=None):
        if initial_data is None:
            initial_data = []

        super().__init__(initial_data)

    def __add__(a, b):
        """Add (join) two Docs into a single one and return a new instance.

        This method combines two `Doc` objects into one. If `b` is a tuple or list containing a string and a default type,
        it uses the provided default type. If `b` is a string, it wraps it in a `Doc` object using the default type.
        """

        default = a.DEFAULT_ADD_STRING_TYPE
        
        if hasattr(a, 'dump'):
            a = a.dump()
        if hasattr(b, 'dump'):
            b = b.dump()
        

        if hasattr(b, 'dump'):
            b = b.dump()
        if isinstance(b, (tuple, list)) and len(b) == 2 and isinstance(b[0], str) and isinstance(b[-1], str):
            (b, default) = b
        if isinstance(b, str):
            b = Doc().add_kw(default, b, end='').dump()
        if not isinstance(b, list):
            b = [b]
        return Doc(a + b)
    
    def __iadd__(self, b):
        """
        Add content to the current instance using the += operator.

        Parameters:
        b (str, tuple, list, or object with a dump method): The content to add.
            - If `b` has a `dump` method, it will be called to get the content.
            - If `b` is a tuple or list of length 2 with both elements being strings,
            the first element is used as the key and the second as the value.
            - If `b` is a string, it will be added with the default key.

        Returns:
        self: The modified instance after adding the content.
        """
        
        default = self.DEFAULT_ADD_STRING_TYPE

        if hasattr(b, 'dump'):
            b = b.dump()
        if isinstance(b, (tuple, list)) and len(b) == 2 and isinstance(b[0], str) and isinstance(b[-1], str):
            (b, default) = b
        if isinstance(b, str):
            b = Doc().add_kw(default, b, end='').dump()
        for k in b:
            self.add(k)
        return self
    
    def flatten(self):
        """Unpacks all iterator elements within this document and returns a new flat document.

        Returns:
            Doc: A new document with all elements flattened.
        """
        return Doc(flatten_list(self.dump()))

    def add_chapter(self, chapter_name:str, chapter_index=None, color=''):
        """Adds a new chapter to the document.

        Args:
            chapter_name (str): The name of the new chapter.
            chapter_index (int, optional): The index after which chapter to insert the new chapter. If None, appends to the end.

        Raises:
            AssertionError: If `chapter_name` is not a string or is empty.
        """
        global chapter_level
        assert isinstance(chapter_name, str), f'chapter name must be type string but was {type(chapter_name)=} {chapter_name=}'
        assert chapter_name, 'chapter_name can not be empty'
        chapters = list(self.get_chapters().keys())
        assert chapter_name not in chapters, f'chapter with {chapter_name=} already exists in document {chapters=}!'
        self.add_kw('markdown', '#' * chapter_level + ' ' + chapter_name, chapter=chapter_index, color=color)
        return self
    
    def get_chapter(self, chapter) -> List[dict]:
        """Retrieves a specific chapter from the document.

        Args:
            chapter (str): The name of the chapter to retrieve.

        Returns:
            List[dict]: A list of dictionaries representing the content of the specified chapter.
        """
        return self.get_chapters(as_ranges=False)[chapter]
    
    def get_chapters(self, as_ranges=False) -> dict:
        """Extracts chapters from the internal data and returns them as either dictionaries or ranges.

        This method iterates through the internal data structure (represented by `self.data`) and identifies chapters based on a custom logic implemented in the `_is_chapter` function.

        Args:
            as_ranges (bool, optional): If True, returns chapters as dictionaries with keys as chapter names (obtained from the previous chapter) and values as ranges of indices (inclusive-exclusive) within the data list representing the chapter content. Defaults to False.

        Returns:
            dict or dict[str, range]:
                If `as_ranges` is False, returns a dictionary where keys are chapter names and values are corresponding chapter content extracted from the data list using the identified ranges.
                If `as_ranges` is True, returns a dictionary where keys are chapter names and values are ranges of indices (inclusive-exclusive) within the data list representing the chapter content.
        """

        chapters = {}
        last_chap_name = ''
        i_low = 0
        for i, part in enumerate(self.data):
            i_chap_name = _is_chapter(part)
            if i_chap_name and i == 0 and i_low == 0:
                last_chap_name = i_chap_name

            if i_chap_name and i_chap_name != last_chap_name and i >= i_low:
                chapters[last_chap_name] = slice(i_low, i)
                i_low = i
                last_chap_name = i_chap_name

        if last_chap_name and i >= i_low and not last_chap_name in chapters:
            chapters[last_chap_name] = slice(i_low, i+1)
            
        if not as_ranges:
            return {k:self.data[rng] for k, rng in chapters.items()}
        else:
            return chapters


    def get_template_from_meta(self, tformat ='', template_dir = None) -> DocTemplate:
        """Gets the template from the metadata in this document if there is any defined.

        Args:
            tformat (str, optional): The format of the template either 'tex' or 'html'. Defaults to ''.
            template_dir (str, optional): If this is given only this specific template dir is mounted to load templates from. Otherwise all registered templates are loaded

        Returns:
            DocTemplate: The template object if a template_id is found in the metadata, otherwise None.
        """
        meta = self.get_meta({}).get("data", {})
        template_id = meta.get("template_id", None)

        attachments = meta.get("files_to_upload", {})
        attachments.update(meta.get("attachments", {}))
        attachments = {k:base64.b64decode(v) if isinstance(v, str) else v for k, v in attachments.items()}
    
        if template_id is None:
            template_str = meta.get("template", None)
            if template_str:
                return DocTemplate(template_str, attachments=attachments)
            else:
                return None    
        

        try:
            template = DocTemplate.from_tid(template_id, tformat, template_dir)
            template.params = {k:v for k, v in meta.items() if k in template.params}

            template.attachments.update(attachments)
            return template
        except KeyError as err:
            if 'my_template_id=' in str(err):
                tformat = 'Any' if not tformat else tformat
                s = f'The {template_id=} was defined for this document, and the current serializer tried to get it with the format="{tformat}", but it could not be resolved.\nWill continue without template. Original Error message\n' + str(err) 
                warnings.warn(s)
                return None
            else:
                raise

    

    def set_template_to_meta(self, template_id:str, with_params=True, with_assets=True, test_found=True, on_exist='fail') -> dict:
        """
        Sets a template by a given template_id to the document metadata.

        Args:
            template_id (str): The ID of the template to set.
            with_params (bool, optional): Whether to include the (defalt) parameters from the template in the metadata. Defaults to True.
            with_assets (bool, optional): Whether to include the assets (files) from the template in the metadata. Defaults to True.
            test_found (bool, optional): Whether to test if the template exists before adding anything. Defaults to True.
            on_exist (str, optional): What to do if the parameters or assets from a template already exist in the metadata. Can be 'fail', 'overwrite', or 'skip'. Defaults to 'fail'.

        Raises:
            FileNotFoundError: If the template with the given ID does not exist.
            AssertionError: If overwrite protection is enabled and the template would overwrite existing data.
            ValueError: If an unknown value is passed for the on_exist parameter.

        Returns:
            dict: the meta elements data (content)
        """
        if (test_found or with_params or with_assets) and not DocTemplate.test_tid_exists(template_id):
            available_tids = DocTemplate.get_available_tids()
            raise FileNotFoundError(f'The template with the ID {template_id=} could not be found in {available_tids=}')

        if with_params or with_assets:
            template = DocTemplate.from_tid(template_id)

        params = template.params if with_params else {}
        files_to_upload = template.attachments if with_assets else {}
        files_to_upload = {k:base64.b64encode(v).decode() if isinstance(v, bytes) else v for k, v in files_to_upload.items()}

        meta = self.get_meta({}).get("data", {})

        if on_exist == 'fail':
            if files_to_upload:
                assert not "files_to_upload" in meta or not meta.get("files_to_upload", None), f'Overwrite Protection! found "files_to_upload" key in meta, but this would be overwritten by assets from template. If this is what you want set on_exist="overwrite".'
            if params:
                existing_keys = [k for k in params if k in meta]
                assert not existing_keys, f'Overwrite Protection! found {existing_keys=} in meta, but this would be overwritten by params from template. If this is what you want set on_exist="overwrite".'
            if not 'files_to_upload' in meta:
                meta['files_to_upload'] = {}
            meta["files_to_upload"].update(files_to_upload)
            meta.update(params)

        elif on_exist == 'overwrite':
            if not 'files_to_upload' in meta:
                meta['files_to_upload'] = {}
            meta["files_to_upload"].update(files_to_upload)
            meta.update(params)
        elif on_exist == "skip":
            if not 'files_to_upload' in meta:
                meta['files_to_upload'] = {}
            meta["files_to_upload"].update(files_to_upload)
            meta.update(params)
        else:
            raise ValueError(f'Unknown key for {on_exist=} allowed is only "fail", "overwrite", or "skip"')
        
        meta['template_id'] = template_id

        return self.update_meta(meta)
    

    def parse_filename_meta(self, doc_name, regex_pattern: str, fancy_title_analysis=True) -> dict:
        r"""
        Parses the metadata from a document name using a regular expression pattern.

        Args:
            doc_name (str): The name of the document.
            regex_pattern (str): The regular expression pattern to use for parsing (can also give multiple as list or tuple).
            fancy_title_analysis (bool, optional): Will Analyse the title for "signed" in it and also resolve CamelCasing from it

        Returns:
            dict: A dictionary containing the parsed metadata.

        Example:
            >>> import pydocmaker as pyd
            >>> doc = pyd.Doc()
            >>> regex_pattern = r'(?P<title>\w+)-(?P<version>[a-zA-Z0-9]+)-(?P<state>\w+)'
            >>> doc_name = 'myfile-01-draft'
            >>> doc.parse_filename_meta(doc_name, regex_pattern)
            {'doc_name': 'myfile-01-draft', 'title': 'myfile', 'version': '01', 'state': 'draft'}

        """

        if isinstance(regex_pattern, str):
            regex_pattern = [regex_pattern]

        dc = dict(doc_name=doc_name)
        for pattern in regex_pattern:
            match = re.match(pattern, doc_name)
            if match:
                dc.update(match.groupdict())

        if fancy_title_analysis and 'title' in dc:
            title = dc['title']
            if 'signed' in title and not dc.get('status'):
                dc['status'] = 'signed'
            title = re.sub('signed', '', title, flags=re.IGNORECASE)
            title = ' '.join(split_camel_case(title))
            title = title.strip(' -_')
            dc['title'] = title

        self.update_meta(dc)
        return dc

    def set_meta(self, *args, **kwargs) -> dict:
        """
        Sets the metadata for this document. 
        Can be used in two ways:
        - By passing a dictionary: `.set_meta({'doc_name': 'test'})`
        - By passing keyword arguments: `.set_meta(doc_name='test')`

        This method updates the existing metadata or creates new metadata if it doesn't exist.

        Args:
            *args: A single dictionary containing metadata.
            **kwargs: Key-value pairs representing metadata.

        Returns:
            dict: The updated metadata.
        """
        data = next(iter(args), {})
        data.update(kwargs)

        meta = self.get_meta()
        if meta is None:
            return self.add_meta(data)
        else:
            if not 'data' in meta:
                meta['data'] = {}
            meta['data'].clear()
            meta['data'].update(data)
            return meta['data']
        
    def get_meta(self, default=None) -> Union[Dict, None]:
        """gets the (first) meta element in this document if it exists. If not returns None"""
        return next((k for k in self if isinstance(k, dict) and k.get('typ') == 'meta'), default)
    
    def get_metadata(self) -> Union[Dict, None]:
        """Equivalent to self.get_meta(default={}).get('data', {})
        Gets the data of the (first) meta element in this document if it exists. 
        If not exists an new empty dict is returned"""
        return self.get_meta(default={}).get('data', {})
    
    def has_meta(self) -> bool:
        """tests if this document has one or more metadata objects"""
        return False if self.get_meta() is None else True
    
    def update_meta(self, *args, **kwargs) -> Union[Dict, None]:
        """Updates the metadata element in this document if it exists.
        If not, it will be added with the content provided. The content can be
        provided either as a dictionary or as keyword arguments.

        Examples:
            .update_meta({'doc_name': 'test'})
            .update_meta(doc_name='test')

        Returns:
            dict: The updated metadata content.
        """
        
        data = next(iter(args), {})
        meta = self.get_meta()
        data.update(kwargs)
        if meta is None: 
            return self.add_meta(data)
        else:
            if not 'data' in meta:
                meta['data'] = {}
            meta['data'].update(**data)
            return meta['data']

    def add_meta(self, *args, **kwargs) -> dict:
        """Adds a metadata element to this document. If the metadata already exists,
        it will be updated. The content can be provided either as a dictionary or as keyword arguments.

        Examples:
            .add_meta({'doc_name': 'test'})
            .add_meta(doc_name='test')

        Returns:
            dict: The metadata element's data (content).
        """
        data = next(iter(args), {})
        data.update(kwargs)

        if self.has_meta():
            return self.update_meta(data)
        else:
            el = constr.meta(data=data)
            self.add(el)
            return el['data']
        
    def add(self, part:dict=None, index=None, chapter=None, color='', end=None):
        """Appends a new document part to the given location or end of this document.

        Args:
            part (dict): The part to add. See the `constr` class for all possible parts.
            index (int, optional): The index where to insert the part. If None, appends to the end.
            chapter (str | int, optional): The chapter name or index where to insert the part. If None, appends to the end.
            color (str, optional): any color which can be rendered by html or latex (ONLY VALID FOR string INPUTS!). Empty string for default.
            end (str, optional): If you want to insert a different line ending (than the default) for this element set this argument to any string. None for default.

        Raises:
            ValueError: If the `part` is invalid, or if both `index` and `chapter` are specified.
            AssertionError: If `index` is not an integer or is out of bounds.
        """
        assert part, f'need to give an element_to_add!, but got {type(part)=} {part=}'
        
        if isinstance(part, str):
            part = constr.text(part, color=color, end=end)
            color = ''
        
        
        assert not color, 'giving a color is only allowed for string inputs!'
        assert not end, 'giving a "end" argument is only allowed for string inputs!'
        assert hasattr(constr, part.get('typ', None)), 'the part to add is of unknown type!'
        assert index is None or chapter is None, f'can either give index OR chapter!'

        if not chapter is None:
            chapters = self.get_chapters(as_ranges=True)
            if isinstance(chapter, int):
                chapter = list(chapters.keys())[chapter] 

            if not chapter in chapters:
                self.add_chapter(chapter)
                chapter = None # just append to end!
            else:
                index = chapters[chapter].stop # set to after the last element of this chapter (stop index is excluded so no need to increment here)

        if index is None:
            index = len(self) # append to end

        assert isinstance(index, int), f'index must be None or int but was {type(index)=} {index=}'
        assert 0 <= index <= len(self), f'index must be 0 <= index <= len(self) but was {index=}, {len(self)=}'    
        self.insert(index, part)
        return self


        
    def add_kw(self, typ, children=None, index=None, chapter=None, color='', end=None, **kwargs):
        """add a document part to this document with a given typ

        Args:
            typ (str, optional): one of the allowed document part types. Either 'markdown', 'verbatim', 'text', 'iter' or 'image'.
            children (str or list): the "children" for this element. Either text directly (as string) or a list of other parts
            index (int, optional): The index where to insert the part. If None, appends to the end.
            chapter (str | int, optional): The chapter name or index where to insert the part. If None, appends to the end.
            color (str, optional): any color which can be rendered by html or latex. Empty string for default.
            end (str, optional): If you want to insert a different line ending (than the default) for this element set this argument to any string. None for default.

            kwargs: the kwargs for such a document part
        """
        assert typ, 'need to give a content type!'
        self.add(construct(typ, children=children, color=color, end=end, **kwargs), index=index, chapter=chapter)
        return self
    

    def add_text(self, children=None, index=None, chapter=None, color='', **kwargs):
        """add a raw text part to this document

        Args:
            children (str or list): the "children" for this element. Either text directly (as string) or a list of other parts
            index (int, optional): The index where to insert the part. If None, appends to the end.
            chapter (str | int, optional): The chapter name or index where to insert the part. If None, appends to the end.
            color (str, optional): any color which can be rendered by html or latex. Empty string for default.

            kwargs: the kwargs for such a document part
        """
        self.add(construct('text', children=children, color=color, **kwargs), index=index, chapter=chapter)
        return self


    def add_tex(self, children=None, index=None, chapter=None, color='', end=None, **kwargs):
        """add a latex part to this document

        Args:
            children (str or list): the "children" for this element. Either text directly (as string) or a list of other parts
            index (int, optional): The index where to insert the part. If None, appends to the end.
            chapter (str | int, optional): The chapter name or index where to insert the part. If None, appends to the end.
            color (str, optional): any color which can be rendered by html or latex. Empty string for default.

            kwargs: the kwargs for such a document part
        """
        self.add(construct('latex', children=children, color=color, end=end, **kwargs), index=index, chapter=chapter)
        return self

    def add_md(self, children=None, index=None, chapter=None, color='', end=None, **kwargs):
        """add a markdown document part to this document

        Args:
            children (str or list): the "children" for this element. Either text directly (as string) or a list of other parts
            index (int, optional): The index where to insert the part. If None, appends to the end.
            chapter (str | int, optional): The chapter name or index where to insert the part. If None, appends to the end.
            color (str, optional): any color which can be rendered by html or latex. Empty string for default.
            end (str, optional): If you want to insert a different line ending (than the default) for this element set this argument to any string. None for default.

            kwargs: the kwargs for such a document part
        """
        self.add(construct('markdown', children=children, color=color, end=end, **kwargs), index=index, chapter=chapter)
        return self
    
    def add_table(self, children=None, index=None, chapter=None, color='', end=None, header=None, caption='', n_rows=None, n_cols=None, borders=True, **kwargs):
        """add a table element to this document

        Args:
            children (list of lists): the "children" for this element. Must be a matrix (list of lists) with formatable elements in it.
            index (int, optional): The index where to insert the part. If None, appends to the end.
            chapter (str | int, optional): The chapter name or index where to insert the part. If None, appends to the end.
            color (str, optional): any color which can be rendered by html or latex. Empty string for default.
            end (str, optional): If you want to insert a different line ending (than the default) for this element set this argument to any string. None for default.
            header (list, optional): The header row for the table. If given it must be a list with formatable elements in it.
            caption (str, optional): The caption to place at/under the table. Empty for no caption.
            n_rows (int, optional): The number of rows to give this table. If not given it will be determined from the number of rows in children.
            n_cols (int, optional): The number of columns to give this table. If not given it will be determined from the max number of columns in all rows in children.
            borders (bool, optional): Whether or not the table should have lines between its cells.
        """
        if header: kwargs['header'] = header
        if n_rows: kwargs['n_rows'] = n_rows
        if n_cols: kwargs['n_cols'] = n_cols
        if borders: kwargs['borders'] = borders
        if caption: kwargs['caption'] = caption
        self.add(constr.table(children=children, color=color, end=end, **kwargs), index=index, chapter=chapter)
        return self
    
    def add_pre(self, children=None, index=None, chapter=None, color='', end=None, **kwargs):
        """add a verbaim (pre formatted) document part to this document

        Args:
            children (str or list): the "children" for this element. Either text directly (as string) or a list of other parts
            index (int, optional): The index where to insert the part. If None, appends to the end.
            chapter (str | int, optional): The chapter name or index where to insert the part. If None, appends to the end.
            color (str, optional): any color which can be rendered by html or latex. Empty string for default.
            end (str, optional): If you want to insert a different line ending (than the default) for this element set this argument to any string. None for default.

            kwargs: the kwargs for such a document part
        """
        self.add(construct('verbatim', children=children, color=color, end=end, **kwargs), index=index, chapter=chapter)
        return self
    

    def add_fig(self, fig=None, caption = '', width=None, bbox_inches='tight', children=None, index=None, chapter=None, color='', end=None, **kwargs):
        """add a pyplot figure type dict from given image input.
        
        Args:
            fig (matplotlib figure, optional): the figure which to upload (or the current figure if None). Defaults to None.
            caption (str, optional): the caption to give to the image. Defaults to ''.
            width (float, optional): The width for the image to have in the document None will let the individual formatter determine the width. Defaults to None.
            bbox_inches (str, optional): will give better spacing for matplotlib figures.
            children (str, optional): A specific name/id to give to the image (will be auto generated if None). Defaults to None.
            index (int, optional): The index where to insert the part. If None, appends to the end.
            chapter (str | int, optional): The chapter name or index where to insert the part. If None, appends to the end.
            color (str, optional): any color which can be rendered by html or latex. Empty string for default.
            end (str, optional): If you want to insert a different line ending (than the default) for this element set this argument to any string. None for default.

        """
        self.add(constr.image_from_fig(caption=caption, width=width, bbox_inches=bbox_inches, children=children, fig=fig, color=color, end=end, **kwargs), index=index, chapter=chapter)
        return self
    

    def add_image(self, image, caption = '', width=None, children=None, index=None, chapter=None, color='', end=None, **kwargs):
        """add an image type dict from given image input.
        image can be of type:
            - pyplot figure
            - link to download an image from
            - filelike
            - numpy NxMx1 or NxMx3 matrix
            - PIL image

        Args:
            im (np.array): the image as NxMx
            caption (str, optional): the caption to give to the image. Defaults to ''.
            width (float, optional): The width for the image to have in the document None will let the individual formatter determine the width. Defaults to None.
            children (str, optional): A specific name/id to give to the image (will be auto generated if None). Defaults to None.
            index (int, optional): The index where to insert the part. If None, appends to the end.
            chapter (str | int, optional): The chapter name or index where to insert the part. If None, appends to the end.
            color (str, optional): any color which can be rendered by html or latex. Empty string for default.
            end (str, optional): If you want to insert a different line ending (than the default)  for this element set this argument to any string. None for default.

        """

        if isinstance(image, str) and image.startswith('http'):
            docpart = constr.image_from_link(url=image, caption=caption, children=children, width=width, color=color, end=end)
        elif isinstance(image, str) and len(image) < 5_000 and os.path.exists(image):
            docpart = constr.image_from_file(path=image, caption=caption, children=children, width=width, color=color, end=end)
        elif isinstance(image, str):
            docpart = constr.image(imageblob=image, caption=caption, children=children, width=width, color=color, end=end)
        elif 'Figure' in str(type(image)):
            docpart = constr.image_from_fig(fig=image, caption=caption, children=children, width=width, color=color, end=end)
        else:
            docpart = constr.image_from_obj(image, caption=caption, children=children, width=width, color=color, end=end)

        self.add(docpart, index=index, chapter=chapter)
        return self
    

    def dump(self) -> List[Dict]:
        """dump this document to a basic list of dicts for document parts

        Returns:
            list: the individual parts of the document
        """
        return [copy.deepcopy(v) for v in self]
    
    def _ret(self, m, path_or_stream):
        """internal method to return or write data"""
        

        if path_or_stream and isinstance(path_or_stream, str):
            mode = 'w' if isinstance(m, str) else 'wb'
            encoding = 'utf-8' if isinstance(m, str) else None

            with open(path_or_stream, mode, encoding=encoding) as f:
                f.write(m)
            return True
        
        elif hasattr(path_or_stream, 'write'):
            try:
                path_or_stream.write(m)
            except TypeError:
                if isinstance(m, str):
                    path_or_stream.write(m.encode())
                else:
                    raise

            return True
        else:
            return m
        
    def to_json(self, path_or_stream=None) -> str:
        """
        Converts the current object to a JSON file.

        Args:
            path_or_stream (str or io.IOBase, optional): The path to save the file to, or a file-like object to write the data to. If not provided, the data will be returned as string.

        Returns:
            str: The JSON data as string, or True if the data was saved successfully to a file or stream.
        """
        return self._ret(json.dumps(self.dump(), indent=2), path_or_stream)

    def to_markdown(self, path_or_stream=None, embed_images=True) -> str:
        """
        Converts the current object to a Markdown string or writes it to a file.

        Args:
            path_or_stream (str or io.IOBase, optional): The path to save the Markdown file to, or a file-like object to write the data to. If not provided, the Markdown string will be returned.
            embed_images (bool, optional): Whether to embed images as base64 strings within the Markdown. Defaults to True.

        Returns:
            str or bool: The Markdown string if `path_or_stream` is not provided, or True if the Markdown was successfully written to the file or stream.
        """
        return self._ret(to_markdown(self.dump(), embed_images=embed_images), path_or_stream)

    def to_docx(self, path_or_stream=None, template:str=None, template_params=None, use_w32=False, as_pdf=False, compress_images=False, allow_pandoc=True) -> bytes:
        """
        Converts the current object to a DOCX file, or a PDF file via DOCX (WARNING some options need win32com and word installed if selected).

        Args:
            template (str, optional): Path to a DOCX template file. Defaults to None.
            template_params (dict, optional): Parameters to replace fields in the template. Defaults to None.
            use_w32 (bool, optional): Whether to use win32com for document field updating and any of the following arguments, THIS OPTION NEEDS win32com and word installed. Defaults to False.
            as_pdf (bool, optional): Whether to output the document as a PDF (via docx and win32com). Defaults to False.
            compress_images (bool, optional): Whether to compress images in the document using win32com. Defaults to False.
            allow_pandoc (bool, optional): whether or not to allow the usage of pandoc instead of python-docx (usually pandoc creates nicer documents!)

        Returns:
            bytes: The data as bytes, or True if the data was saved successfully to a file or stream.

        Raises:
            ValueError: If attempting to export to PDF without win32com and Word.Application installed and use_w32 set to True.

        """
        filename = os.path.basename(path_or_stream) if isinstance(path_or_stream, (str, Path)) else None
        return self._ret(to_docx(self.dump(), filename=filename, template=template, template_params=template_params, use_w32=use_w32, as_pdf=as_pdf, compress_images=compress_images, allow_pandoc=allow_pandoc), path_or_stream)        

    def to_ipynb(self, path_or_stream=None) -> str:
        """
        Converts the current object to an ipynb (iPython notebook) file.

        Args:
            path_or_stream (str or io.IOBase, optional): The path to save the file to, or a file-like object to write the data to. If not provided, the data will be returned as string.

        Returns:
            str: The data as string, or True if the data was saved successfully to a file or stream.
        """
        return self._ret(to_ipynb(self.dump()), path_or_stream)
    
    def to_html(self, path_or_stream=None, template=None, template_params=None) -> str:
        """
        Converts the current object to a HTML file.

        Args:
            path_or_stream (str or io.IOBase, optional): The path to save the file to, or a file-like object to write the data to. If not provided, the data will be returned as string.
            template (str, optional): A string containing the LaTeX code for the document template. Either a Jinja2 Latex template, or a string
                If not provided, a default template will be used.
            template_params (dict, optional): A dictionary containing the parameters for the document template which will be parsed to the "render" method of Jinja2

        Returns:
            str: The data as string, or True if the data was saved successfully to a file or stream.
        """
        params = {}
        meta = self.get_meta(default={}).get('data', {})
        mytemplate = self.get_template_from_meta(tformat='html')
        if template is None and not mytemplate is None:
            template = mytemplate.template
        if not mytemplate is None:
            params_from_meta = mytemplate.params
        else:
            params_from_meta = {k:v for k, v in meta.items() if not k in ["template_id", "files_to_upload", "additional_files"]}
        params.update(params_from_meta)

        if template_params:
            params.update(template_params)

        return self._ret(to_html(self.dump(), template=template, template_params=template_params), path_or_stream)

    def to_typst(self, path_or_stream=None, template=None, template_params=None) -> str:
        """
        Converts the current object to a Typst file.

        Args:
            path_or_stream (str or io.IOBase, optional): The path to save the file to, or a file-like object to write the data to. If not provided, the data will be returned as string.
            template (str, optional): A string containing the LaTeX code for the document template. Either a Jinja2 Latex template, or a string
                If not provided, a default template will be used.
            template_params (dict, optional): A dictionary containing the parameters for the document template which will be parsed to the "render" method of Jinja2

        Returns:
            str: The data as string, or True if the data was saved successfully to a file or stream.
        """
        params = {}
        meta = self.get_meta(default={}).get('data', {})
        mytemplate = self.get_template_from_meta(tformat='typst')
        if template is None and not mytemplate is None:
            template = mytemplate.template
        if not mytemplate is None:
            params_from_meta = mytemplate.params
        else:
            params_from_meta = {k:v for k, v in meta.items() if not k in ["template_id", "files_to_upload", "additional_files"]}
        params.update(params_from_meta)

        if template_params:
            params.update(template_params)

        return self._ret(to_typst(self.dump(), template=template, template_params=template_params), path_or_stream)
        

    def to_pdf(self, path_or_stream=None, docname='', files_to_upload=None, base_dir=None, engine=None, latex_compiler=None, n_times_make=None, verb=0, ignore_error=True, template=None, template_params=None, do_escape_template_params='auto', **kwargs) -> Union[str, bytes, bool]:
        """Converts the current object to a PDF file or zipped latex project folder.

        Args:
            path_or_stream (str or file-like object, optional): The output destination.
                If it's a string ending with '.pdf', it will be written in pdf format to the given path.
                If it's a string ending with '.zip', the whole project folder used for making the pdf file will be zipped and saved under the given path.
                If it's 'zip' or 'pdf', the data will be returned in the given format.
                If it's None, the PDF data will be returned as a bytes object.
            docname (str, optional): The name of the output document. Defaults to a unix timestamp followed by '_mydocument'.
            files_to_upload (optional): A list of files to be uploaded with the document.
            base_dir (str, optional): The directory to use as the base directory for the temporary directory.
                Defaults to the system's default temporary directory.
            engine (str, optional): the pdf engine to use (either "typst", "tex", "word", or "libreoffice"). If None, the currently configured engine will be queried via config_pdf_engine_get().
            latex_compiler (str, optional): Only used if engine resolves to "tex". The LaTeX compiler to use. Either 'pdflatex', 'lualatex', 'xelatex', or 'pandoc'.
                If not specified, the function will try to use 'pandoc', 'pdflatex', 'lualatex', or 'xelatex' in that order.
            n_times_make (int, optional): Only used if engine resolves to "tex". The number of times to run the LaTeX compiler. Defaults to 1 for pandoc and 3 for all others.
            verb (int, optional): The verbosity level (0, 1, 2). If greater than 0, the function will print more and more debug information. Defaults to 0.
            ignore_error (bool, optional): Whether to ignore errors during the LaTeX compilation. Defaults to True.
            template (str, optional): A string containing the LaTeX code for the document template. Either a Jinja2 Latex template, or a string
                If not provided, a default template will be used.
            template_params (dict, optional): A dictionary containing the parameters for the document template which will be parsed to the "render" method of Jinja2
            do_escape_template_params (bool, optional): Only valid for Latex templates. Whether to escape the template parameters. "auto" will scan for %%latex at the start of a string to determine if its a latex string. Defaults to 'auto'.

        Returns:
            str: Either the data as string, or bytes depending on if its binary. Or True|False to indicate if the data was saved successfully to a file or stream.

        Raises:
            Warning: If the provided file path does not end with '.zip' or '.pdf', a warning is issued and the file is assumed to be in PDF format.
        """


        if files_to_upload is None:
            files_to_upload = {}
        
        additional_files = kwargs.pop('additional_files', {})
        if additional_files:
            files_to_upload.update(additional_files)

        attachments = kwargs.pop('attachments', {})
        if attachments:
            files_to_upload.update(attachments)

        params = {}
        meta = self.get_meta(default={}).get('data', {})
        if engine is None:
            engine = config_pdf_engine_get()

        if not engine:
            raise ImportError("No engine to convert to PDF is available. Make sure you either have pdflatex, Microsoft Word, or Libreoffice installed")

        if verb:
            log.info(f'using engine "{engine}" to convert to pdf')

        tformat = 'tex' if engine == 'tex' else ('typst' if engine == 'typst' else 'html')

        mytemplate = self.get_template_from_meta(tformat=tformat)
        if template is None and not mytemplate is None:
            template = mytemplate.template
        if not mytemplate is None:
            if verb:
                log.info(f'found template "{mytemplate.template_id}"')
            params_from_meta = mytemplate.params
            if verb:
                log.info(f'found params: "{params_from_meta.keys()=}"')
            files_to_upload = {**mytemplate.attachments, **files_to_upload}
            if verb:
                log.info(f'found attachments: "{files_to_upload.keys()=}"')
        else:
            params_from_meta = {k:v for k, v in meta.items() if not k in ["template_id", "files_to_upload", "additional_files"]}
        params.update(params_from_meta)

        if template_params:
            params.update(template_params)

        if engine == 'typst':
            def _to_pdf_typst(*ar, **kw):
                s = self.to_typst(*ar, template=template, template_params=params, **kw)
                if ignore_error and verb:
                    on_warning = 'warn' 
                elif ignore_error and not verb:
                    on_warning = 'ignore'
                elif verb:
                    on_warning = 'log'

                return to_pdf_typst(s, verb=verb, on_warning=on_warning)

            fun = _to_pdf_typst
        elif engine == 'tex':
            
            if do_escape_template_params == 'auto':
                params = auto_escape_latex(params)
                do_escape_template_params = False


            kwargs = {
                "files_to_upload": files_to_upload,
                "template": template,
                "template_params": params,
                'do_escape_template_params': do_escape_template_params,
                "docname": docname,
                "base_dir": base_dir,
                "latex_compiler": latex_compiler,
                "n_times_make": n_times_make,
                "verb": verb,
                "ignore_error": ignore_error
            }

            # unpacks any argument from params into kwargs in case something else than default is given for that argument
            for param_name, param_value in kwargs.items():
                if param_name == 'docname' and not param_value and param_name in params:
                    kwargs[param_name] = params.get(param_name)
                elif param_name == 'verb' and param_value == 1 and param_name in params:
                    kwargs[param_name] = params.get(param_name)
                elif param_value is None and param_name in params:
                    kwargs[param_name] = params.get(param_name)


            fun = to_pdf_tex
            if isinstance(path_or_stream, str) and path_or_stream:
                if path_or_stream == 'zip':
                    fun = to_pdf_zip
                    path_or_stream = None
                elif path_or_stream.endswith('.zip'):
                    fun = to_pdf_zip
                elif path_or_stream == 'pdf':
                    fun = to_pdf_tex
                    path_or_stream = None
                elif path_or_stream.endswith('.pdf'):
                    fun = to_pdf_tex
                else:
                    warnings.warn(f'the given filename is neither "zip" nor "pdf" this is unusual. I will assume it`s "pdf" format and write to the given path: "{path_or_stream}"')
            
        elif engine == 'word':
            filename = os.path.basename(path_or_stream) if isinstance(path_or_stream, (str, Path)) else None
            def to_pdf_word(*ar, **kw):
                return to_docx(*ar, filename=filename, template=template, template_params=params, use_w32=True, as_pdf=True, **kw)
            fun = to_pdf_word

        elif engine == 'libreoffice':
            filename = os.path.basename(path_or_stream) if isinstance(path_or_stream, (str, Path)) else None
            def to_pdf_libre(*ar, **kw):
                return to_docx(*ar, filename=filename, template=template, template_params=params, use_w32=False, as_pdf=True, **kw)
            fun = to_pdf_libre
        elif engine == 'pandoc':
            def to_pdf_pandoc(doc, *ar, **kw):
                if isinstance(doc, list):
                    doc = Doc(doc)
                if not isinstance(doc, Doc):
                    raise TypeError(f'doc must be of type {Doc}, but was {type(doc)=}')
                
                with tempfile.TemporaryDirectory() as td:
                    out = os.path.join(td, f'out.pdf')
                    inp = os.path.join(td, f'inp.html')
                    doc.to_html(inp, template=template, template_params=params)
                    pandoc_to_pdf(inp, out)
                    with open(out, 'rb') as fp:
                        bts = fp.read()
                return bts
            fun = to_pdf_pandoc


        else:
            raise ValueError("unknown engine, Engine must be one of 'tex', 'word', 'libreoffice'")
        

        r = self._ret(fun(self.dump(), **kwargs), path_or_stream)

        if isinstance(path_or_stream, (str, os.PathLike)) and verb:
            log.info(f'Saved to path_or_stream="{path_or_stream}" with function "{fun.__name__}"')

        return r
    

    
    def to_tex(self, path_or_stream=None, additional_files=None, template = None, do_escape_template_params='auto', template_params=None, text_only=False):
        """Converts the current object to a TEX file (and attachments).

        Args:
            path_or_stream (str or io.IOBase, optional): The path to save the file to, or a file-like object to write the data to. If not provided, the data will be returned as a string.
            additional_files (dict[str:bytes], optional): Any additional files you want to upload to the tex document, such as an image as a logo in the header.
            template (str, optional): The LaTeX template to use.
            do_escape_template_params (bool, optional): Whether to escape the template parameters. "auto" will scan for %%latex at the start of a string to determine if its a latex string. Defaults to 'auto'.
            template_params (dict, optional): Additional parameters to pass to the LaTeX template.
            text_only (bool, optional): Only valid if path_or_stream is None. Whether or not to return attachments as well. Defaults to False

        Returns:
            If saving to a file or stream:
                True if the data was saved successfully to a file or stream.
            If returning:
                str: The tex file as a string.
                dict: The additional input files needed for LaTeX (bytes) as values and their relative paths (str) as keys.
        """
        if additional_files is None:
            additional_files = {}

        params = {}
        meta = self.get_meta(default={}).get('data', {})
        mytemplate = self.get_template_from_meta(tformat='tex')
        if template is None and not mytemplate is None:
            template = mytemplate.template
        if not mytemplate is None:
            params_from_meta = mytemplate.params
            additional_files = {**mytemplate.attachments, **additional_files}
        else:
            params_from_meta = {k:v for k, v in meta.items() if not k in ["template_id", "files_to_upload", "additional_files"]}
        params.update(params_from_meta)

        if template_params:
            params.update(template_params)

        if do_escape_template_params == 'auto':
            params = auto_escape_latex(params)
            do_escape_template_params = False


        tex, files = to_tex(self.dump(), with_attachments=True, template=template, files_to_upload=additional_files, do_escape_template_params=do_escape_template_params, template_params=template_params)

        with io.BytesIO() as in_memory_zip:
            with zipfile.ZipFile(in_memory_zip, 'w') as zipf:
                zipf.writestr('doc.json', self.to_json())
                zipf.writestr('main.tex', tex)
                for path in files:
                    zipf.writestr(path, files[path])
            in_memory_zip.seek(0)
            m = in_memory_zip.getvalue()

        if isinstance(path_or_stream, str):
            with open(path_or_stream, "wb") as f:
                f.write(m)
            return True
        elif hasattr(path_or_stream, 'write'):
            path_or_stream.write(m)
            return True
        else:
            if text_only:
                return tex
            else:
                return tex, files
    
    def to_textile(self, path_or_stream=None, text_only=False):
        """
        Converts the current object to a TEXTILE file (and attachments). 
        If path_or_stream is given it will zip all contents and write it to the stream or file path given.
        If not it will return a tuple with textile (str), files (dict[str, bytes])

        Args:
            path_or_stream (str or io.IOBase, optional): The path to save the file to, or a file-like object to write the data to. If not provided, the data will be returned as string.
            text_only (bool, optional): Only valid if path_or_stream is None. Whether or not to return attachments as well. Defaults to False
        
        Returns:
            If saving to a file or stream:
                True if the data was saved successfully to a file or stream.
            If returning:
                str: The tex file as a string.
                dict: The additional input files needed for LaTeX (bytes) as values and their relative paths (str) as keys.
        """
        
        textile, files = to_textile(self.dump(), with_attachments=True, aformat_redmine=False)
        with io.BytesIO() as in_memory_zip:
            with zipfile.ZipFile(in_memory_zip, 'w') as zipf:
                # zipf.writestr('doc.json', self.to_json())
                zipf.writestr('main.textile', textile)
                for path in files:
                    zipf.writestr(path, files[path])
            in_memory_zip.seek(0)
            m = in_memory_zip.getvalue()

        if isinstance(path_or_stream, str):
            with open(path_or_stream, "wb") as f:
                f.write(m)
            return True
        elif hasattr(path_or_stream, 'write'):
            path_or_stream.write(m)
            return True
        else:
            if text_only:
                return textile
            else:
                return textile, files
        
    def to_redmine(self) -> Tuple[str, list]:
        """
        Converts the current object to a Redmine Textile like text (and attachments) and returns them as tuple.
        """

        return to_textile(self.dump(), with_attachments=True, aformat_redmine=True)
    
    def to_redmine_upload(self, redmine, project_id:str, report_name=None, page_title=None, force_overwrite=False, verb=True):
        """Converts the current object to a Redmine Textile like text (and attachments) and Uploads it to a Redmine wiki page.
        This will also export the document to all possible formats and attach them to the wiki page.

        Args:
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
            
        return upload_report_to_redmine(self, redmine=redmine, project_id=project_id, report_name=report_name, page_title=page_title, force_overwrite=force_overwrite, verb=verb)
    
    def print_rich(self, path_or_stream=None, title=None, embed_images=True):
        """
        Parses the current object using python rich library and output it either on console or to any file / stream.

        Args:
            path_or_stream: Either a file path (str) to write to, a file-like object
                           with a write method, or None to output to stdout
            title: Optional title for the documentation. If not provided, will attempt
                  to extract from metadata using common title keys. If still None a default title will be used.
            embed_images: if True this will make the images appear as simplified pixelized pictures on the console, 
                  if False it will insert a placeholder instead. 
        Returns:
            bool: Only in path_or_stream is not None. True if successful, False otherwise

        Example:
            >>> doc.print_rich("output.rich")
            >>> doc.print_rich(sys.stdout)
            >>> doc.print_rich()
        """
        if title is None:
            metadata = self.get_metadata()
            options = 'title TITLE Title filename FILENAME Filename name NAME Name docname DOCNAME Docname documentname Documentname DOCUMENTNAME'.split()
            title = next((metadata[k] for k in options if k in metadata), None)
        

        if isinstance(path_or_stream, str):
            with open(path_or_stream, "w") as f:
                print_rich(self.dump(), stream=path_or_stream, embed_images=embed_images)
            return True
        elif hasattr(path_or_stream, 'write'):
            print_rich(self.dump(), stream=path_or_stream, embed_images=embed_images)
            return True
        else:
            print_rich(self.dump(), stream=None, embed_images=embed_images)


    def to_pdf_print(self, path_or_stream=None):
        """Exports the document to a PDF file by using the systems "print to pdf" function to export from html to pdf.

        WARNING: This function only works on posix like operating systems and requires a PDF printer to be installed 
        and set as default printer. It will not work on windows or macos since they do not have a command line 
        interface for printing to PDF. Use with caution and make sure to test it on your system before using it in production!

        WARNING II: The resulting PDF file will not be of the same quality as a PDF file generated by a proper PDF engine like 
        pdflatex, typst, or word. It is recommended to use this function only as a last resort if no other PDF engine is 
        available and you need a quick and dirty PDF file.

        Args:
            output_pdf_path (str, optional): The path to save the PDF file to. If not provided, a temporary file will be used.
            
        Returns:
            If saving to a file or stream:
                True if the data was saved successfully to a file or stream.
            If returning:
                str: The PDF file as bytes.

        """
        os_name = os.name
        assert os_name == 'posix', 'only posix like operation systems are supported for printing a pdf file!'

        with tempfile.TemporaryDirectory() as tmpdir:
            html_file_path = os.path.join(tmpdir, "temp.html")
            self.to_html(html_file_path)

            if not path_or_stream or not isinstance(path_or_stream, str):
                output_pdf_path = tempfile.NamedTemporaryFile(suffix=".pdf").name
            else:
                output_pdf_path = path_or_stream

            print_to_pdf(html_file_path, output_pdf_path)

            if not path_or_stream:
                data = open(output_pdf_path, 'rb').read()
                if not len(data):
                    raise IOError(f'failed to write {output_pdf_path=}')
                return data
            elif hasattr(path_or_stream, 'write'):
                data = open(output_pdf_path, 'rb').read()
                if not len(data):
                    raise IOError(f'failed to write {output_pdf_path=}')           
                path_or_stream.write(data)
                return True
            else:
                assert isinstance(path_or_stream, str), f'path_or_stream is not a string but {type(path_or_stream)=}'
                assert isinstance(output_pdf_path, str), f'output_pdf_path is not a string but {type(output_pdf_path)=}'
                assert output_pdf_path == path_or_stream, f'something went wrong, since the PDF file was written to {output_pdf_path=} instead of {path_or_stream=}'
                exists = os.path.exists(path_or_stream)
                if not exists:
                    raise IOError(f'failed to write {path_or_stream=}')
                return exists

    def export_all(self, dir_path=None, report_name='exported_report', **kwargs):
        """
        Exports the document to all possible formats.

        Args:
            dir_path (str, optional): The path to the directory where the exported files should be saved. If not provided, a dict with the returned data from the exporters will be returned.
            report (str, optional): The base name for the exported files. Defaults to "exported_report".
            **kwargs: Additional keyword arguments specific to the chosen export formats.

        Returns:
            dict: A dictionary containing the exported data or paths for each engine.
        """
        return self.export_many(engines=None, dir_path=dir_path, report_name=report_name, **kwargs)

    def export_many(self, engines:List[str]=None, dir_path=None, report_name='exported_report', **kwargs):
        """
        Exports the document to multiple formats.

        Args:
            engines (list[str], optional): A list of export engines to use. If not provided, all supported engines will be used.
            dir_path (str, optional): The path to the directory where the exported files should be saved. If not provided, a dict with the returned data from the exporters will be returned.
            report (str, optional): The base name for the exported files. Defaults to "exported_report".
            **kwargs: Additional keyword arguments specific to the chosen export formats.

        Returns:
            dict: A dictionary containing the exported data or paths for each engine.
        """
        if engines is None and dir_path is None or not engines:
            engines = list(Doc.EXPORT_ENGINES.keys()) # all engines

        unknown_engines = [e for e in engines if not e in Doc.EXPORT_ENGINES_EXTENSIONS]
        engines = [e for e in engines if e in Doc.EXPORT_ENGINES_EXTENSIONS]

        if unknown_engines: 
            warnings.warn(f'Found unknown engines in requested engines. These will be ignored! {unknown_engines=}')

        if not dir_path is None:
            assert os.path.exists(dir_path), f'given {dir_path=} does not exist!'
            assert os.path.isdir(dir_path), f'given {dir_path=} is not a directory'
        
        ret = {}
        for engine in engines:
            engine = engine.strip('').strip('.')
            if dir_path is None:
                ext = Doc.EXPORT_ENGINES_EXTENSIONS.get(engine, '.' + engine)
                path = None
                key = report_name + ext
            else:
                ext = Doc.EXPORT_ENGINES_EXTENSIONS.get(engine, '.' + engine)
                path = os.path.join(dir_path, report_name + ext)
                key = path
            
            ret[key] = self.export(engine, path, **kwargs.get(engine, {}))
        
        return ret
    

    def export(self, engine:str, path_or_stream=None, **kwargs):
        """Exports the document to a specified format.

        Args:
            engine (str): The format to export to. Valid options are: 'md', 'markdown', 'json', 'html', 'tex', 'latex', 'textile', 'word', 'docx', and 'redmine'.
            path_or_stream (str or io.IOBase, optional): The path to save the exported file to, or a file-like object to write the data to.
            **kwargs: Additional keyword arguments specific to the chosen export format.

        Returns:
            str or bool: The exported data or True if the data was successfully written to a file or stream.

        Raises:
            KeyError: If the specified `engine` is not supported.
        """

        if '\\' in engine or '/' in engine and not path_or_stream:
            path_or_stream = engine
            engine = os.path.basename(engine)

        
        engine = engine.split('.')[-1]
        engine = engine.lower().strip()

        if engine in ['md', 'markdown']:
            return self.to_markdown(path_or_stream=path_or_stream, **kwargs)
        elif engine in ['json']:
            return self.to_json(path_or_stream=path_or_stream, **kwargs)
        elif engine in ['html']:
            return self.to_html(path_or_stream=path_or_stream, **kwargs)
        elif engine in ['typst', 'typ', 'TYPST', 'TYP']:
            return self.to_typst(path_or_stream=path_or_stream, **kwargs)
        elif engine in ['pdf']:
            return self.to_pdf(path_or_stream=path_or_stream, **kwargs)
        elif engine in ['tex', 'latex']:
            return self.to_tex(path_or_stream=path_or_stream, **kwargs)
        elif engine in ['textile']:
            return self.to_textile(path_or_stream=path_or_stream, **kwargs)
        elif engine in ['ipynb', 'jupyter', 'notebook']:
            return self.to_ipynb(path_or_stream=path_or_stream, **kwargs)
        elif engine in ['word', 'docx']:
            return self.to_docx(path_or_stream=path_or_stream, **kwargs)
        elif engine in ['redmine']:
            assert not path_or_stream, 'redmine engine can not handle writing to path_or_stream!'
            return self.to_redmine(**kwargs)
        else:
            raise KeyError(f'engine must be in: {Doc.EXPORT_ENGINES=}, but was {engine=}')
        
    def upload(self, url, doc_name='', force_overwrite=False, page_title='', requests_kwargs=None, raise_on_fail=True, warn_on_fail=True):
        """Uploads the document data to a specified URL using HTTP(s) and requests.
            The json body is constructed as:
            
            upload = {
                "doc_name": doc_name,
                "doc": self.dump(),
                "force_overwrite": force_overwrite,
                "page_title": page_title
            }

        Args:
            url (str): The URL of the endpoint that accepts the document data.
            doc_name (str, optional): The name of the uploaded document. Defaults to ''.
            force_overwrite (bool, optional): Whether to overwrite an existing document. Defaults to False.
            page_title (str, optional): The title of the uploaded document (if applicable). Defaults to ''.
            requests_kwargs: (dict, optional) with kwargs for requests.post(). Defaults to None.
            raise_on_fail: (bool, optional): set True to raise an exception on failed upload. Defaults to True.
            warn_on_fail: (bool, optional): set True to prompt some warning text with the feedback from server on a fail. Defaults to True.

        Returns:
            dict: The JSON response from the server after uploading the document.

        Raises:
            requests.exceptions.RequestException: If the upload request fails.
        """

        upload = {
            "doc_name": doc_name,
            "doc": self.dump(),
            "force_overwrite": force_overwrite,
            "page_title": page_title
        }

        import requests

        requests_kwargs = {} if not requests_kwargs else None
        r = requests.post(url, json=upload, **requests_kwargs)
        if warn_on_fail and not 200 <= r.status_code < 300:
            warnings.warn(f'upload failed with status_code: {r.status_code}. Body\n {r.text}')
        if raise_on_fail:
            r.raise_for_status()
        return r.json()
    

    


    def show(self, engine = None, index=None, chapter=None, files_to_upload=None, template=None, template_params=None, do_escape_template_params=False, embed_images=True, **kwargs):
        """Displays the document or a specific part of it in ipython display or via print

        Args:
            engine (str, optional): The engine to use for displaying. None to decide based on the currently available console. Else either "html", "markdown", "md", "tex", "latex", or "pdf" (pdf only works in Ipython!)
            index (int, optional): The index of the part to display.
            chapter (str, optional): The name of the chapter to display.
            files_to_upload (dict, optional): ONLY VALID WHEN engine='pdf'. See to_pdf method for details. Defaults to None.
            template (jinja2 template or string, optional): ONLY VALID WHEN engine='pdf'. See to_pdf method for details. Defaults to None.
            template_params (dict, optional): ONLY VALID WHEN engine='pdf'. See to_pdf method for details. Defaults to None.
            do_escape_template_params (bool, optional): ONLY VALID WHEN engine='pdf'. See to_pdf method for details. Defaults to False.
            embed_images (bool, optional): ONLY VALID WHEN engine='md' or 'rich'. Whether to embed (show) images within the document, or placeholders. Defaults to True.

        Raises:
            KeyError: if the specified engine is not found or not valid
            AssertionError: If both `index` and `chapter` are specified.
        """

        assert index is None or chapter is None, f'can either give index OR chapter!'
        
        if engine is None:
            engine = _renderer_default

        
        if engine in ['html', 'pdf', 'tex']:
            kwargs['template'] = template
            kwargs['template_params'] = template_params

        if engine in ['pdf', 'tex']:
            kwargs['additional_files'] = files_to_upload
            kwargs['do_escape_template_params'] = do_escape_template_params

        if index:
            Doc([self[index]]).show(engine=engine, files_to_upload=files_to_upload, template=template, template_params=template_params, do_escape_template_params=do_escape_template_params, **kwargs)
        elif chapter:
            Doc(self.get_chapter(chapter)).show(**kwargs)
        
        if is_notebook():
            if engine == 'auto':
                engine = 'html'
            
            engine = engine.lower()

            from IPython.display import display, HTML, Markdown, Code
            if engine in 'html'.split():
                display(HTML(self.to_html(**kwargs)))
            elif engine.startswith('std') or engine in 'console rich terminal plain'.split():
                self.print_rich(embed_images=embed_images, **kwargs)
            elif engine in 'markdown md'.split():
                display(Markdown(self.to_markdown(embed_images=embed_images, **kwargs)))
            elif engine in 'typst'.split():
                display(Code(self.to_typst(**kwargs), language='typst'))
            elif engine in 'tex latex'.split():
                display(Code(self.to_tex(text_only=True, **kwargs), language='tex'))
            elif engine == 'pdf':
                verb = kwargs.pop('verb', 0)
                pdf_bytes = self.to_pdf(verb=verb, **kwargs)
                show_pdf(pdf_bytes)
            else:
                raise KeyError(f'engine must be in: "html", "markdown", "md", "typst", "tex", "latex", or "pdf", but was {engine=}')

        else:
            if engine == 'auto':
                engine = 'rich'
            
            engine = engine.lower()
            if engine in 'html'.split():
                print(self.to_html(**kwargs))
            elif engine.startswith('std') or engine in 'console rich terminal plain'.split():
                self.print_rich(embed_images=embed_images, **kwargs)
            elif engine in 'markdown md'.split():
                kwargs.pop('embed_images')
                print(self.to_markdown(embed_images=False, **kwargs))
            elif engine in 'typst'.split():
                print(self.to_typst(**kwargs))
            elif engine in 'tex latex'.split():
                print(self.to_tex(text_only=True, **kwargs))
            else:
                raise KeyError(f'engine must be in: "html", "markdown", "md", "typst", "tex", or "latex", but was {engine=}')
            
    def __repr__(self, *args, **kwargs):
        chaps = self.get_chapters()
        return f'pydocmaker.Doc with N={len(chaps)} chapters, K={len(self)} elements.'

    def __str__(self, *args, **kwargs): 
        return self.__repr__()
    

    @classmethod
    def get_example(cls):
                
        doc = cls()

        content = """## Some Example Text

One morning, when Gregor Samsa woke from troubled dreams, he found himself *transformed* in his bed into a horrible  [vermin](http://en.wikipedia.org/wiki/Vermin "Wikipedia Vermin"). He lay on his armour-like back, and if he lifted his head a little he could see his brown belly, slightly domed and divided by arches into stiff sections. The bedding was hardly able to cover **strong** it and seemed ready to slide off any moment. His many legs, pitifully thin compared with the size of the rest of him, link waved abouthelplessly as he looked. <cite>“What's happened to me?”</cite> he thought. It wasn't a dream. His room, a proper human room although a little too small, lay peacefully between its four familiar walls.</p>

### The bedding was hardly able to cover it.

It showed a lady fitted out with a fur hat and fur boa who sat upright, raising a heavy fur muff that covered the whole of her lower arm towards the viewer a solid fur muff into which her entire forearm disappeared..

#### Things we know about Gregor's sleeping habits.

- He always slept on his right side.
- He has to get up early (to start another dreadful day).
- He has a drawer and a alarm clock next to his bed.
- His mother calls him when he gets up to late.

        """

        doc.add_md(content)
        doc.add_md("First he wanted to stand up quietly and undisturbed, get dressed, above all have breakfast, and only then consider further action, for (he noticed this clearly) by thinking things over in bed he would not reach a reasonable conclusion. He remembered that he had already often felt a light pain or other in bed, perhaps the result of an awkward lying position, which later turned out to be purely imaginary when he stood up, and he was eager to see how his present fantasies would gradually dissipate. That the change in his voice was nothing other than the onset of a real chill, an occupational illness of commercial travelers, of that he had not the slightest doubt.")
        doc.add_md("## Formatting and Images")
        doc.add("this is how to embed preformatted text via a verbatim part")
        doc.add_pre("""
function metamorphose(protagonist,author){
    if( protagonist.name.first === 'Gregor' && author.name.last === 'Kafka' ){
        protagonist.species = 'insect';
    }
}
        """)
        doc.add_tex("\\textit{This is some dummy LaTeX text.}")

        doc.add_md("this is how to embed a table:")

        header = ['Name', 'Age', 'City']
        table = [
            ['John Doe', "30", 'New York'],
            ['Jane Smith', "25", 'Los Angeles'],
            ['Mike Johnson', "35", 'Chicago']
        ]
        doc.add_table(table, header=header, borders=True, caption='This is my example table')

        doc.add('And this is how to embed an Image:')
        doc.add_image(image="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEYAAAAUCAAAAAAVAxSkAAABrUlEQVQ4y+3TPUvDQBgH8OdDOGa+oUMgk2MpdHIIgpSUiqC0OKirgxYX8QVFRQRpBRF8KShqLbgIYkUEteCgFVuqUEVxEIkvJFhae3m8S2KbSkcFBw9yHP88+eXucgH8kQZ/jSm4VDaIy9RKCpKac9NKgU4uEJNwhHhK3qvPBVO8rxRWmFXPF+NSM1KVMbwriAMwhDgVcrxeMZm85GR0PhvGJAAmyozJsbsxgNEir4iEjIK0SYqGd8sOR3rJAGN2BCEkOxhxMhpd8Mk0CXtZacxi1hr20mI/rzgnxayoidevcGuHXTC/q6QuYSMt1jC+gBIiMg12v2vb5NlklChiWnhmFZpwvxDGzuUzV8kOg+N8UUvNBp64vy9q3UN7gDXhwWLY2nMC3zRDibfsY7wjEkY79CdMZhrxSqqzxf4ZRPXwzWJirMicDa5KwiPeARygHXKNMQHEy3rMopDR20XNZGbJzUtrwDC/KshlLDWyqdmhxZzCsdYmf2fWZPoxCEDyfIvdtNQH0PRkH6Q51g8rFO3Qzxh2LbItcDCOpmuOsV7ntNaERe3v/lP/zO8yn4N+yNPrekmPAAAAAElFTkSuQmCC")
        
        return doc
    

    
def _construct(v):
    """internal function"""
    if isinstance(v, str):
        return v
    elif isinstance(v, list):
        return [_construct(vv) for vv in v]
    elif isinstance(v, dict):
        return construct(**v)
    else:
        TypeError(f'{type(v)=} is of unknown type only dataclass, str, list, and dict is allowed!')

def construct(typ:str, **kwargs):
    """construct a document-part dict from the given typ and some kwargs"""
    assert isinstance(typ, str)
    typ = constr.typalias.get(typ, typ)
    if not kwargs and not hasattr(constr, typ):
        return typ
    elif hasattr(constr, typ):
        children = kwargs.get('children')
        if children:
            kwargs['children'] = _construct(children)
        constructor = getattr(constr, typ)
        return constructor(**kwargs)
    else:
        TypeError(f'{typ=} is of unknown type only dataclass, str, list, and dict is allowed!')


def load(doc:List[dict]):
    """Loads a document from a list of dictionaries, a file path, or a stream-like object.

    Args:
        doc (List[dict] | str | BinaryIO | TextIO]): The document data, file path, or stream-like object.

    Returns:
        Doc: A Doc object representing the loaded document.

    Raises:
        ValueError: If the document is not a list, file path, or stream-like object, or if the file or stream cannot be loaded.
    """
    if isinstance(doc, bytes):
        doc = doc.decode()

    if isinstance(doc, str) and doc.strip().startswith('['):
        doc = json.loads(doc)

    if isinstance(doc, str):
        with open(doc, 'r') as fp:
            doc = json.load(fp)
    
    if hasattr(doc, 'read') and hasattr(doc, 'seek'):
        doc = json.load(fp)

    assert isinstance(doc, list), f'doc must be list but was {type(doc)=} {doc=}'
    return Doc(doc)

    

    
    


def print_to_pdf(file_path, output_pdf_path):
    """Prints a file to a PDF file using the appropriate platform-specific command using subprocess

    WARNING: This function only works on posix like operating systems and requires a PDF printer to be installed 
    and set as default printer. It will not work on windows or macos since they do not have a command line 
    interface for printing to PDF. Use with caution and make sure to test it on your system before using it in production!

    WARNING II: The resulting PDF file will not be of the same quality as a PDF file generated by a proper PDF engine like 
    pdflatex, typst, or word. It is recommended to use this function only as a last resort if no other PDF engine is 
    available and you need a quick and dirty PDF file.

    
    Args:
        file_path (str): The path to the file to print.
        output_pdf_path (str): The path to the output PDF file.

    Raises:
        ValueError: If the platform is not supported.
    """

    p = Path(file_path).resolve()
    po = Path(output_pdf_path).resolve()
    
    if not p.exists():
        raise ValueError(f'The input file path "{p}" does not exist.')
    
    if not po.parent.exists():
        raise ValueError(f'The directory for the output PDF path "{po}" does not exist.')

    os_name = os.name
    if not os_name == 'posix':
        raise ValueError(f'only posix like operation systems are supported for printing a pdf file! You have {os_name=}')
    
    warnings.warn("printing a PDF file is not a good option, and might not succeed.")

    command = ["lp", "-d", "file:///dev/stdout", "-o", f"output-file={shlex.quote(po)}", shlex.quote(p)]

    subprocess.run(command, check=True)
    

# def dump(obj):
#     if isinstance(obj, list):
#         return [dump(o) for o in obj]
    
#     assert isinstance(obj, dict)
#     return {k:_serialize(v) for k, v in obj.items()}




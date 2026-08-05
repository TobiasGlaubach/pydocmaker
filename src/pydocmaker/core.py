from dataclasses import dataclass, field, is_dataclass
from collections import UserDict, UserList
import json, io
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any, Dict, List, BinaryIO, TextIO, Tuple, Union, IO, Optional, Sequence
import warnings
import zipfile

import base64
import copy

import subprocess
import os

import shlex

import jinja2





from .util import flatten_list, split_camel_case, upload_report_to_redmine, CommonJSONEncoder, MyJSONDecoder, limit_len, log, make_png_imageblob


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

from .templating import DocTemplate, TemplateDirSource, _remove_template_ext, determine_engine_from_template, _remove_template_ext_match

from .backend.pandoc_api import can_run_pandoc, pandoc_convert, pandoc_to_pdf

from . import b64_data

ALLOWED_ENGINES_PDF = 'tex latex typst typ word libreoffice pandoc'.split()

np = None
gImage = None

chapter_level = 1 # this is the level of heading to use for chapters which is equivalent to html <h1> to <h5> or whatever

_pdf_engine = None
_renderer_default = 'auto'



def config_renderer_default_set(choice:str='auto'):
    """
    Sets the default renderer for displaying reports within Python.

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

def config_renderer_default_get() -> str:
    """Returns the currently configured default renderer."""
    global _renderer_default
    return _renderer_default



def config_pdf_engine_set(choice: str = 'typst') -> str:
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


def config_pdf_engine_get() -> str:
    """Returns the currently configured PDF engine, testing and setting one if none is configured."""
    global _pdf_engine
    if _pdf_engine is None:
        config_pdf_engine_testset()
    return str(_pdf_engine)



def config_pdf_engine_test(raise_on_error: bool = True, force_reload: bool = False) -> bool:
    """
    Tests the availability of the currently configured PDF engine.

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



def config_pdf_engine_scan(force_reload: bool = False, firstonly: bool = False) -> Union[str, List[str]]:
    """
    Scans the system for available PDF engines and returns them.

    Args:
        force_reload (bool): If True, forces a reload of the PDF engine configuration cache.
        firstonly (bool): If True, returns only the first available engine as a string.

    Returns:
        str | list[str]: A list of available engine names, or the first engine name if firstonly=True.
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

def config_pdf_engine_testset() -> Optional[str]:
    """Scans for available PDF engines, sets the first one found, and returns it."""
    eng = config_pdf_engine_scan(firstonly=True)
    if eng:
        return config_pdf_engine_set(eng)
    else:
        global _pdf_engine
        _pdf_engine = ''
        return None

    
    
def is_notebook() -> bool:
    """Checks whether the current code is running inside a notebook environment (Jupyter, Colab, etc.).

    Returns:
        bool: True if running in a notebook environment, False otherwise.
    """
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



def show_pdf(pdf_bytes: bytes, width: int = 1000, height: int = 1200) -> None:
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


def _is_chapter(dc: Dict[str, Any]) -> str:
    """Extracts the chapter name from a markdown element if it is a chapter heading.

    Args:
        dc: A document part dictionary.

    Returns:
        str: The chapter name if dc is a chapter heading, empty string otherwise.
    """
    global chapter_level
    pre = '#' * chapter_level
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

    



def load_file_b64(path:Union[str, BinaryIO, TextIO, Path]):
    """
    Load an image from a file path or file-like object and return its base64-encoded string representation.
    """
    assert path, 'need to give a path!'

    if hasattr(path, 'read'):
        bts = path.read()
    else:
        with open(path, 'rb') as fp:
            bts = fp.read()
    
    assert bts and isinstance(bts, bytes), f'the loaded content needs to be of type bytes but was {bts=}'

    b64str = base64.b64encode(bts).decode('utf-8')
    return b64str
    

class constr:
    """This is the basic schema for the main building blocks for a document.

    Provides static factory methods that create document part dictionaries
    with a 'typ' key identifying the element type (meta, markdown, text,
    latex, verbatim, line, image, table, iter, etc.).
    """

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
    def meta(children: str = '', data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
        """Create a metadata document part dict.

        Args:
            children: Unused string content placeholder.
            data: Dictionary of metadata key-value pairs.
            **kwargs: Additional metadata fields.

        Returns:
            dict: Document part dict with typ='meta', children, and data.
        """
        data = {k:v for k,v in data.items()} if data else {}
        data.update(kwargs)
        return {
            'typ': 'meta',
            'children': children,
            'data': data,
        }
    
    @staticmethod
    def markdown(children: str = '', color: str = '', end: Optional[str] = None) -> Dict[str, Any]:
        """Create a markdown document part dict.

        Args:
            children: The markdown text content.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.

        Returns:
            dict: Document part dict with typ='markdown'.
        """
        return {
            'typ': 'markdown',
            'children': children,
            'color': color,
            'end': end
        }
    
    @staticmethod
    def text(children: str = '', color: str = '', end: Optional[str] = None) -> Dict[str, Any]:
        """Create a plain text document part dict.

        Args:
            children: The plain text content.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.

        Returns:
            dict: Document part dict with typ='text'.
        """
        return {
            'typ': 'text',
            'children': children,
            'color': color,
            'end': end
        }
    
    @staticmethod
    def line(children: str = '', color: str = '', end: Optional[str] = None) -> Dict[str, Any]:
        """Create a line document part dict.

        Args:
            children: The text content for this line.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending (default '\n').

        Returns:
            dict: Document part dict with typ='line'.
        """
        return {
            'typ': 'line',
            'children': children,
            'color': color,
            'end': '\n' if end is None else end
        }
    
    @staticmethod
    def latex(children: str = '', color: str = '', end: Optional[str] = None) -> Dict[str, Any]:
        """Create a LaTeX document part dict.

        Args:
            children: The LaTeX source code string.
            color: Color for rendering (for HTML backends).
            end: Custom line ending.

        Returns:
            dict: Document part dict with typ='latex'.
        """
        return {
            'typ': 'latex',
            'children': children,
            'color': color,
            'end': end
        }
    

    @staticmethod
    def verbatim(children: str = '', color: str = '', end: Optional[str] = None, lang:str='') -> Dict[str, Any]:
        """Create a verbatim (pre-formatted text) document part dict.

        Args:
            children: The verbatim text content.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.
            lang: the (code)language of that formatted block (not supported by most backends)

        Returns:
            dict: Document part dict with typ='verbatim'.
        """
        return {
            'typ': 'verbatim',
            'children': children,
            'color': color,
            'lang': lang,
            'end': end
        }
    
    @staticmethod
    def iter(children: Optional[List[Any]] = None, color: str = '', end: Optional[str] = None) -> Dict[str, Any]:
        """Create an iter (iterator/loop) document part dict.

        Used to wrap content that should be iterated over (flattened) during export.

        Args:
            children: List of document parts to iterate over.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.

        Returns:
            dict: Document part dict with typ='iter'.
        """
        return {
            'typ': 'iter',
            'children': [] if children is None else children,
            'color': color,
            'end': end
        }
    
    @staticmethod
    def table(children: Optional[List[List[Any]]] = None, color: str = '', end: Optional[str] = None,
              header: Optional[List[Any]] = None, caption: str = '',
              n_cols: Optional[int] = None, n_rows: Optional[int] = None, borders: bool = True) -> Dict[str, Any]:
        """Create a table document part dict.

        Args:
            children: Matrix (list of lists) with formatable elements.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.
            header: Header row as a list of formatable elements.
            caption: Caption text to place under/above the table.
            n_cols: Number of columns (auto-detected from `children` if not given).
            n_rows: Number of rows (auto-detected from `children` if not given).
            borders: Whether the table should have lines between cells.

        Returns:
            dict: Document part dict with typ='table'.
        """
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
    def image(imageblob: str = '', caption: str = '', children: str = '', width: Optional[float] = None,
              color: str = '', end: Optional[str] = None) -> Dict[str, Any]:
        """Create an image document part dict.

        Args:
            imageblob: Base64-encoded image data string.
            caption: Caption text for the image.
            children: Internal name/id for the image file. Auto-generated if empty.
            width: Display width for the image in the document.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.

        Returns:
            dict: Document part dict with typ='image'.
        """

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
    def image_from_link(url: str, caption: str = '', children: str = '', width: Optional[float] = None,
                        color: str = '', end: Optional[str] = None) -> Dict[str, Any]:
        """Create an image document part by downloading an image from a URL.

        Args:
            url: The URL to download the image from.
            caption: Caption text for the image. Derived from filename if empty.
            children: Internal name/id for the image file. Derived from URL if empty.
            width: Display width for the image in the document.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.

        Returns:
            dict: Document part dict with typ='image' containing the downloaded image data.

        Raises:
            AssertionError: If url is empty or downloaded content is not an image MIME type.
        """
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
    def image_from_file(path: Union[str, 'os.PathLike', BinaryIO], children: str = '', caption: str = '',
                        width: Optional[float] = None, color: str = '', end: Optional[str] = None) -> Dict[str, Any]:
        """Create an image document part from a file path or file-like object.

        Args:
            path: File path string, PathLike object, or a file-like object with a read() method.
            children: Internal name/id for the image file. Derived from filename if empty.
            caption: Caption text for the image. Derived from children if empty.
            width: Display width for the image in the document.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.

        Returns:
            dict: Document part dict with typ='image' containing the image data.

        Raises:
            AssertionError: If path is empty or read content is not bytes.
        """
        imageblob = load_file_b64(path)

        if not children:
            children = os.path.basename(path)
        
        if not caption and children:
            caption = children


        return constr.image(imageblob=imageblob, children=children, caption=caption, width=width, color=color, end=end)
        

    @staticmethod
    def image_from_fig(caption: str = '', width: Optional[float] = None, children: Optional[str] = None,
                       fig: Any = None, color: str = '', end: Optional[str] = None,
                       bbox_inches: str = 'tight', **kwargs: Any) -> Dict[str, Any]:
        """Convert a matplotlib figure (or the current figure) to a document image dict.

        Args:
            caption: The caption to give to the image.
            width: The width for the image to have in the document. None lets the individual formatter determine the width.
            children: A specific name/id to give to the image (will be auto generated if None).
            fig: The matplotlib figure object (or the current figure if None).
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.
            bbox_inches: Bounding box for the figure save (passed to matplotlib.savefig).
            **kwargs: Additional keyword arguments passed to matplotlib.savefig.

        Returns:
            dict: Document part dict with typ='image' containing the rendered figure as base64.
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
    def image_from_obj(img: Any, caption: str = '', width: Optional[float] = None, children: Optional[str] = None,
                       color: str = '', end: Optional[str] = None) -> Dict[str, Any]:
        """Create an image document part from a matrix, file-like object, PIL Image, or numpy array.

        Accepts various input types and converts them to a base64-encoded PNG image:
        - 2D lists of lists -> numpy array -> PIL Image
        - numpy arrays with shape -> PIL Image
        - PIL Images -> file-like -> bytes -> base64
        - File path strings -> file-like -> bytes -> base64
        - Bytes -> base64

        Args:
            img: Image input. Can be a list of lists, numpy array, PIL Image, file path (str),
                 file-like object with a read() method, or bytes.
            caption: The caption to give to the image.
            width: The width for the image to have in the document. None lets the formatter determine width.
            children: A specific name/id for the image (auto-generated if None).
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.

        Returns:
            dict: Document part dict with typ='image' containing the image data.
        """
        global np, gImage

    
        # 2D matrix as lists --> make nummpy array
        if isinstance(img, list) and img and img[0] and isinstance(img[0], list):
            if np is None:
                import numpy 
                np = numpy
            img = np.array(img)

        # numpy array --> make PIL image
        if hasattr(img, 'shape') and len(img.shape) == 2:
            if gImage is None:
                from PIL import Image
                gImage = Image
    
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
    """A collection of document parts to make a document (can be used like a list).

    The Doc class extends UserList and stores document parts as a list of dictionaries.
    Each dictionary represents a document element with a 'typ' key identifying its type
    (e.g., 'markdown', 'text', 'latex', 'image', 'table', 'iter', 'meta').

    Attributes:
        DEFAULT_ADD_STRING_TYPE: Default type used when adding plain strings to the document.
        EXPORT_ENGINES: List of supported export format identifiers.
        EXPORT_ENGINES_EXTENSIONS: Mapping of export format identifiers to their file extensions.
    """

    DEFAULT_ADD_STRING_TYPE: str = 'markdown'
    EXPORT_ENGINES: List[str] = ['md', 'html', 'typst', 'json', 'docx', 'textile', 'ipynb', 'tex', 'redmine', 'pdf']
    EXPORT_ENGINES_EXTENSIONS: Dict[str, str] = {'md': '.md', 'html': '.html', 'typst': '.typ', 'json': '.json', 'docx': '.docx', 'textile': '.textile.zip', 'ipynb': '.ipynb', 'tex': '.tex.zip', 'pdf': '.pdf'}

    @staticmethod
    def load_json(path: Union[str, Path, BinaryIO, TextIO]) -> 'Doc':
        """Load a JSON file and return a Doc object.

        Args:
            path: The path to the JSON file, a URL string, or a file-like object.

        Returns:
            Doc: A Doc object initialized with the loaded JSON data.

        Raises:
            json.JSONDecodeError: If the JSON file is not valid.
            ValueError: If the remote response is not valid JSON.
        """
        if hasattr(path, 'read'): # test file pointer
            lst = json.load(path, cls=MyJSONDecoder)
        if isinstance(path, str) and path.startswith("http"): # test url
            import requests
            r = requests.get(path)
            r.raise_for_status()
            # JSON returned directly or json content as file
            try:
                lst = r.json()
            except ValueError:
                try:
                    lst = json.loads(r.text, cls=MyJSONDecoder)
                except json.JSONDecodeError:
                    raise ValueError("Response is not valid JSON")

        else:
            with open(path, 'r') as fp:
                lst = json.load(fp, cls=MyJSONDecoder)
        if not isinstance(lst, list):
            warnings.warn(f'The loaded json object is not of type list, but instead of type ({type(lst)=})')
        return Doc(lst)
    
    @staticmethod
    def load(file_path_or_string: Union[str, Path, BinaryIO, TextIO], filename: str = None) -> 'Doc':
        """Load a compatible pydocmaker document and return a Doc object.

        Args:
            file_path_or_string: A file path, URL string, or file-like object containing
                HTML, JSON, or IPYNB document content.
            filename: The name of the file being loaded.

        Returns:
            Doc: A Doc object initialized from the loaded document.

        Raises:
            json.JSONDecodeError: If the JSON content is invalid.
            ValueError: If the content is not a supported pydocmaker document.
        """
                
        from .io.html_loader import io_serialize_html, io_deserialize_html, io_check_html
        from .io.ipynb_loader import io_serialize_ipynb, io_deserialize_ipynb, io_check_ipynb
        from .util import loadfile_str


        str_content, f = loadfile_str(file_path_or_string)
        if f:
            filename = f

        if io_check_html(str_content):
            doc = io_deserialize_html(str_content)
        elif io_check_ipynb(str_content):
            doc = io_deserialize_ipynb(str_content)
        elif str_content.strip().startswith("[") or str_content.strip().startswith("{"):
            doc = Doc(json.loads(str_content, cls=MyJSONDecoder))
        else:
            raise ValueError(f"The provided {filename if filename else 'file'}, starting with '{limit_len(str_content, n_max=50)}', does not appear to be a valid pydocmaker document (HTML, JSON, or IPYNB).")
        
        return doc


    def save(self, file_path: str=None, format: str='html'):
        """Save the current document to a pydocmaker-supported file.

        Args:
            file_path: Destination file path. If omitted, the method returns self.
            format: Default format used when `file_path` has no suffix.

        Returns:
            bool: True if the file was written successfully.
            Doc: self when no file path is provided.

        Raises:
            ValueError: If the requested file extension is unsupported.
        """

        from .io.html_loader import io_serialize_html, io_deserialize_html, io_check_html
        from .io.ipynb_loader import io_serialize_ipynb, io_deserialize_ipynb, io_check_ipynb

        format = format.lower()
        if file_path and isinstance(file_path, (str, Path)):
            p = Path(file_path)
            if p.suffix:
                format = p.suffix.lower()
            else:
                file_path = f"{file_path}.{format}"


        if not format.startswith('.'):
            format = '.' + format
            
        if format.endswith(".html") or format.endswith(".pyd") or format.endswith(".pydoc"):
            txt = io_serialize_html(self)
        elif format.endswith(".ipynb"):
            txt = io_serialize_ipynb(self)
        elif format.endswith(".json"):
            txt = self.to_json(None)
        else:
            raise ValueError(f"Unsupported file extension {format}. Please use .html, .pyd, .pydoc, .ipynb, or .json for saving pydocmaker documents.")

        return self._ret(txt, file_path)




    def __init__(self, initial_data: Optional[List[Dict[str, Any]]] = None) -> None:
        """Initialize a Doc with optional initial list of document parts.

        Args:
            initial_data: Optional list of document part dictionaries.
        """
        if initial_data is None:
            initial_data = []

        super().__init__(initial_data)

    def __add__(a, b: Any) -> 'Doc':
        """Add (join) two Docs into a single one and return a new instance.

        This method combines two `Doc` objects into one. If `b` is a tuple or list containing a string and a default type,
        it uses the provided default type. If `b` is a string, it wraps it in a `Doc` object using the default type.

        Args:
            b: Content to append. Can be a Doc, list, tuple, or string.

        Returns:
            Doc: A new Doc instance with combined content.
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
    
    def __iadd__(self, b: Any) -> 'Doc':
        """
        Add content to the current instance using the += operator.

        Args:
            b: The content to add. Can be a Doc, list, tuple, or string.
                - If `b` has a `dump` method, it will be called to get the content.
                - If `b` is a tuple or list of length 2 with both elements being strings,
                the first element is used as the key and the second as the value.
                - If `b` is a string, it will be added with the default key.

        Returns:
            Doc: self (the modified instance after adding the content).
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
    
    def flatten(self) -> 'Doc':
        """Unpacks all iterator elements within this document and returns a new flat document.

        Returns:
            Doc: A new document with all elements flattened (iterators expanded in-place).
        """
        return Doc(flatten_list(self.dump()))

    def add_chapter(self, chapter_name: str, chapter_index: Optional[int] = None, color: str = '') -> 'Doc':
        """Adds a new chapter heading to the document.

        The chapter is inserted after the chapter at the given index (if chapter_index is provided),
        or appended to the end of the document.

        Args:
            chapter_name: The name/title of the new chapter.
            chapter_index: The zero-based index of an existing chapter after which to insert.
                If None, the new chapter is appended to the end.
            color: Color for the chapter heading (for HTML/LaTeX backends).

        Returns:
            Doc: self (for method chaining).

        Raises:
            AssertionError: If chapter_name is not a string, is empty, or already exists.
        """
        global chapter_level
        assert isinstance(chapter_name, str), f'chapter name must be type string but was {type(chapter_name)=} {chapter_name=}'
        assert chapter_name, 'chapter_name can not be empty'
        chapters = list(self.get_chapters().keys())
        assert chapter_name not in chapters, f'chapter with {chapter_name=} already exists in document {chapters=}!'
        self.add_kw('markdown', '#' * chapter_level + ' ' + chapter_name, chapter=chapter_index, color=color)
        return self
    
    def get_chapter(self, chapter: str) -> List[Dict[str, Any]]:
        """Retrieves a specific chapter from the document.

        Args:
            chapter: The name of the chapter to retrieve.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries representing the content items in the specified chapter.
        """
        return self.get_chapters(as_ranges=False)[chapter]
    
    def get_chapters(self, as_ranges: bool = False) -> Union[Dict[str, List[Dict[str, Any]]], Dict[str, slice]]:
        """Extracts chapter names and their content (or index ranges) from the document.

        Iterates through the internal data and identifies chapters based on markdown heading elements
        matched by the `_is_chapter` function.

        Args:
            as_ranges: If False, returns chapter names mapped to their content lists.
                If True, returns chapter names mapped to slice objects with start/stop indices.

        Returns:
            Dict[str, List[Dict[str, Any]]] if as_ranges=False, or Dict[str, slice] if as_ranges=True.
                Keys are chapter names. Values are either content lists or slice objects.
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


    def get_template_from_meta(self, tformat: str = '', template_dir: Optional[str] = None,
                                raise_on_error: bool = False) -> Optional['DocTemplate']:
        """Gets the template from the metadata in this document if one is defined.

        Loads template parameters and attachments stored in the document's metadata element.
        If a template_id is defined, resolves it from the template directory. If a raw
        template string is stored instead, returns a DocTemplate wrapping it.

        Args:
            tformat: The format of the template ('tex', 'html', 'typ', etc.). Used to resolve template_id.
            template_dir: If given, only this specific template directory is mounted for loading.
            raise_on_error: If False, a template_id that cannot be resolved results in a warning and returns None.

        Returns:
            DocTemplate if a template is found in metadata, None otherwise or on unresolved error.
        """
        meta = copy.deepcopy(self.get_meta({}).get("data", {}))
        # remove template_id from the metadata copy so it is not passed as a template param
        template_id = meta.pop("template_id", None)

        attachments = meta.pop("files_to_upload", {})
        attachments.update(meta.pop("attachments", {}))
        attachments = {k:base64.b64decode(v) if isinstance(v, str) else v for k, v in attachments.items()}
    
        if template_id is None:
            template_str = meta.pop("template", None)
            if template_str:
                return DocTemplate(template_str, attachments=attachments)
            else:
                return None    
        

        try:
            template = DocTemplate.from_tid(template_id, tformat, template_dir)
            template.params = {k:v for k, v in meta.items()}

            template.attachments.update(attachments)
            return template
        except KeyError as err:
            if raise_on_error:
                raise

            if 'my_template_id=' in str(err):
                tformat = 'Any' if not tformat else tformat
                s = f'The {template_id=} was defined for this document, and the current serializer tried to get it with the format="{tformat}", but it could not be resolved.\nWill continue without template. Original Error message\n' + str(err) 
                warnings.warn(s)
                return None
            else:
                raise

    

    def set_template_to_meta(self, template_id: str, with_params: bool = True, with_assets: bool = True,
                              test_found: bool = True, on_exist: str = 'fail',
                              template_params: Optional[Dict[str, Any]] = None,
                              tformat: Optional[str] = None) -> Dict[str, Any]:
        """
        Sets a template by a given template_id to the document metadata.

        Copies template parameters and attachment files into the document's metadata element.
        Controls behavior when the metadata already contains corresponding data via the on_exist parameter.

        Args:
            template_id: The ID of the template to set.
            with_params: Whether to include the default parameters from the template in the metadata.
            with_assets: Whether to include the asset files from the template in the metadata.
            test_found: Whether to verify the template exists before modifying metadata.
            on_exist: What to do if parameters/assets from the template already exist in metadata.
                'fail' raises an assertion, 'overwrite' replaces existing data, 'skip' preserves existing data.
            template_params: Additional parameters to merge into the template parameters.
            tformat: Template format override ('tex', 'html', 'typ', etc.).

        Returns:
            dict: The merged data content of the updated metadata element.

        Raises:
            FileNotFoundError: If test_found is True and the template_id does not exist.
            AssertionError: If on_exist='fail' and template params/assets would overwrite existing metadata.
            ValueError: If on_exist is not 'fail', 'overwrite', or 'skip'.
        """
        if (test_found or with_params or with_assets) and not DocTemplate.test_tid_exists(template_id, tformat=tformat):
            available_tids = TemplateDirSource(None).get_template_ids()
            raise FileNotFoundError(f'The template with the ID {template_id=} and format {tformat=} could not be found in {available_tids=}')
        
        params = {}
        files_to_upload = {}
        if with_params or with_assets:
            template = DocTemplate.from_tid(template_id, tformat=tformat)

            params = template.params if with_params else {}
            files_to_upload = template.attachments if with_assets else {}
            files_to_upload = {k:base64.b64encode(v).decode() if isinstance(v, bytes) else v for k, v in files_to_upload.items()}

        meta = self.get_meta({}).get("data", {})

        if template_params:
            params.update(template_params)
        
        # if the key "files_to_upload" for some reason exists in params --> remove it and put all content into files_to_upload
        files_to_upload.update(params.pop('files_to_upload', {}))
        
        
        if on_exist == 'fail':
            if files_to_upload:
                assert not "files_to_upload" in meta or not meta.get("files_to_upload", None), f'Overwrite Protection! found "files_to_upload" key in meta, but this would be overwritten by assets from template. If this is what you want set on_exist="overwrite".'

            if params:
                existing_keys = [k for k in params if k in meta]
                assert not existing_keys, f'Overwrite Protection! found {existing_keys=} in meta, but this would be overwritten by params from template. If this is what you want set on_exist="overwrite".'
            

        elif on_exist == "skip":
            if meta.get("files_to_upload", None): # if already given skip upload
                files_to_upload = {}
            
            if params:
                params = {k:v for k, v in params.items() if not k in meta}

        elif on_exist == 'overwrite':
            if files_to_upload and 'files_to_upload' in meta:
                meta['files_to_upload'] = {}

        else:
            raise ValueError(f'Unknown key for {on_exist=} allowed is only "fail", "overwrite", or "skip"')
        
        meta.update(params)

        if not 'files_to_upload' in meta:
            meta["files_to_upload"] = {}
        meta["files_to_upload"].update(files_to_upload)

        meta['template_id'] = template_id

        return self.update_meta(meta)
    

    def parse_filename_meta(self, doc_name: str, regex_pattern: Union[str, Sequence[str]],
                            fancy_title_analysis: bool = True) -> Dict[str, Any]:
        r"""
        Parses metadata from a document name using a regular expression pattern.

        Extracts named groups from a regex match against doc_name and stores them in the document's metadata.
        Optionally performs fancy title analysis: resolves camelCasing and detects "signed" status.

        Args:
            doc_name: The document name to parse.
            regex_pattern: A regex pattern string or sequence of pattern strings with named groups.
            fancy_title_analysis: If True, attempts to detect "signed" status, resolves camelCasing,
                and cleans up the title string.

        Returns:
            dict: A dictionary containing the parsed metadata, including 'doc_name' key.

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

    def set_meta(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """
        Replaces the metadata for this document with the provided content.
        Can be used in two ways:
        - By passing a dictionary: `.set_meta({'doc_name': 'test'})`
        - By passing keyword arguments: `.set_meta(doc_name='test')`

        This method replaces all existing metadata or creates new metadata if it doesn't exist.

        Args:
            *args: A single dictionary containing metadata.
            **kwargs: Key-value pairs representing metadata.

        Returns:
            dict: The new metadata content (the merged data dict).
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
        
    def get_meta(self, default: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Gets the first metadata element in this document if it exists.

        Args:
            default: Value to return if no metadata element is found.

        Returns:
            The metadata dict (with 'typ', 'children', 'data' keys) if found, or default.
        """
        return next((k for k in self if isinstance(k, dict) and k.get('typ') == 'meta'), default)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Gets the data dict from the first metadata element.

        Gets the 'data' key content from the first metadata element.
        If no metadata element exists, returns an empty dict.

        Returns:
            dict: The metadata data dictionary, or empty dict if none exists.
        """
        return self.get_meta(default={}).get('data', {})
    
    def has_meta(self) -> bool:
        """Tests if this document has one or more metadata objects.

        Returns:
            bool: True if a metadata element exists, False otherwise.
        """
        return False if self.get_meta() is None else True
    
    def update_meta(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Updates the metadata element in this document if it exists.
        If no metadata element exists, it will be created with the provided content.
        The content can be provided either as a dictionary (positional arg) or as keyword arguments.

        Examples:
            .update_meta({'doc_name': 'test'})
            .update_meta(doc_name='test')

        Args:
            *args: A single dictionary containing metadata fields to update.
            **kwargs: Key-value pairs representing metadata fields to update.

        Returns:
            dict: The updated metadata data content.
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

    def add_meta(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Adds a metadata element to this document. If metadata already exists,
        it will be updated via update_meta instead. The content can be provided
        either as a dictionary (positional arg) or as keyword arguments.

        Examples:
            .add_meta({'doc_name': 'test'})
            .add_meta(doc_name='test')

        Args:
            *args: A single dictionary containing metadata fields.
            **kwargs: Key-value pairs representing metadata fields.

        Returns:
            dict: The metadata data content (from the added or updated element).
        """
        data = next(iter(args), {})
        data.update(kwargs)

        if self.has_meta():
            return self.update_meta(data)
        else:
            el = constr.meta(data=data)
            self.add(el)
            return el['data']
        
    def add(self, part: Optional[Union[Dict[str, Any], str]] = None, index: Optional[int] = None,
            chapter: Optional[Union[str, int]] = None, color: str = '', end: Optional[str] = None) -> 'Doc':
        """Appends a new document part to the given location or end of this document.
        
        (also works with lists or tuples of parts, which are added in order).

        If part is a string, it is automatically converted to a 'text' type document part.
        If chapter is given, the part is inserted at the end of that chapter (or the chapter is created).
        If index is given, the part is inserted at that list position.

        Args:
            part: The document part dict (from constr methods) or string to add.
            index: The list index where to insert the part. If None, appends to the end.
            chapter: The chapter name or zero-based chapter index where to insert.
                If None, appends to the end.
            color: Color for rendering (only valid for string inputs).
            end: Custom line ending (only valid for string inputs).

        Returns:
            Doc: self (for method chaining).

        Raises:
            AssertionError: If part is empty, both index and chapter are specified,
                or index is out of bounds.
        """
        if isinstance(part, (tuple, list, Doc)):
            for p in part:
                if p:
                    self.add(p, index=index, chapter=chapter, color=color, end=end)
            return self
        
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


        
    def add_kw(self, typ: str, children: Optional[Union[str, List[Any]]] = None,
               index: Optional[int] = None, chapter: Optional[Union[str, int]] = None,
               color: str = '', end: Optional[str] = None, **kwargs: Any) -> 'Doc':
        """Add a document part to this document with a given type.

        Internally creates a document part dict via the `construct` function and calls `add()`.

        Args:
            typ: One of the allowed document part types ('markdown', 'verbatim', 'text', 'iter', 'image', 'table', 'latex', 'meta', 'line').
            children: The content for this element. Either a string directly or a list of other document parts.
            index: The list index where to insert the part. If None, appends to the end.
            chapter: The chapter name or zero-based chapter index. If None, appends to the end.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.
            **kwargs: Additional keyword arguments passed to the document part constructor.

        Returns:
            Doc: self (for method chaining).
        """
        assert typ, 'need to give a content type!'
        self.add(construct(typ, children=children, color=color, end=end, **kwargs), index=index, chapter=chapter)
        return self
    
    def add_text(self, children: Optional[Union[str, List[Any]]] = None, index: Optional[int] = None,
                 chapter: Optional[Union[str, int]] = None, color: str = '', **kwargs: Any) -> 'Doc':
        """Add a raw text part to this document.

        Args:
            children: The text content or list of items.
            index: The list index where to insert. If None, appends to end.
            chapter: Chapter name or index for insertion. If None, appends to end.
            color: Color for rendering (not supported by all backends).
            **kwargs: Additional keyword arguments for the text element.

        Returns:
            Doc: self (for method chaining).
        """
        self.add(construct('text', children=children, color=color, **kwargs), index=index, chapter=chapter)
        return self


    def add_tex(self, children: Optional[Union[str, List[Any]]] = None, index: Optional[int] = None,
                chapter: Optional[Union[str, int]] = None, color: str = '', end: Optional[str] = None,
                **kwargs: Any) -> 'Doc':
        """Add a LaTeX part to this document.

        Args:
            children: The LaTeX source content or list of items.
            index: The list index where to insert. If None, appends to end.
            chapter: Chapter name or index for insertion. If None, appends to end.
            color: Color for rendering (for HTML backends).
            end: Custom line ending.
            **kwargs: Additional keyword arguments for the LaTeX element.

        Returns:
            Doc: self (for method chaining).
        """
        self.add(construct('latex', children=children, color=color, end=end, **kwargs), index=index, chapter=chapter)
        return self

    def add_md(self, children: Optional[Union[str, List[Any]]] = None, index: Optional[int] = None,
               chapter: Optional[Union[str, int]] = None, color: str = '', end: Optional[str] = None,
               **kwargs: Any) -> 'Doc':
        """Add a markdown document part to this document.

        Args:
            children: The markdown content or list of items.
            index: The list index where to insert. If None, appends to end.
            chapter: Chapter name or index for insertion. If None, appends to end.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.
            **kwargs: Additional keyword arguments for the markdown element.

        Returns:
            Doc: self (for method chaining).
        """
        self.add(construct('markdown', children=children, color=color, end=end, **kwargs), index=index, chapter=chapter)
        return self
    
    def add_table(self, children: Optional[List[List[Any]]] = None, index: Optional[int] = None,
                  chapter: Optional[Union[str, int]] = None, color: str = '', end: Optional[str] = None,
                  header: Optional[List[Any]] = None, caption: str = '',
                  n_rows: Optional[int] = None, n_cols: Optional[int] = None,
                  borders: bool = True, **kwargs: Any) -> 'Doc':
        """Add a table element to this document.

        Args:
            children: Matrix (list of lists) with formatable elements.
            index: The list index where to insert. If None, appends to end.
            chapter: Chapter name or index for insertion. If None, appends to end.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.
            header: Header row as a list of formatable elements.
            caption: Caption text to place at/under the table.
            n_rows: Number of rows (auto-detected from children if not given).
            n_cols: Number of columns (auto-detected from children if not given).
            borders: Whether the table should have lines between its cells.
            **kwargs: Additional keyword arguments.

        Returns:
            Doc: self (for method chaining).
        """
        if header: kwargs['header'] = header
        if n_rows: kwargs['n_rows'] = n_rows
        if n_cols: kwargs['n_cols'] = n_cols
        if borders: kwargs['borders'] = borders
        if caption: kwargs['caption'] = caption
        self.add(constr.table(children=children, color=color, end=end, **kwargs), index=index, chapter=chapter)
        return self
    
    def add_pre(self, children: Optional[Union[str, List[Any]]] = None, index: Optional[int] = None,
                chapter: Optional[Union[str, int]] = None, color: str = '', end: Optional[str] = None,
                lang:str='',
                **kwargs: Any) -> 'Doc':
        """Add a verbatim (pre-formatted) document part to this document.

        Args:
            children: The verbatim text content or list of items.
            index: The list index where to insert. If None, appends to end.
            chapter: Chapter name or index for insertion. If None, appends to end.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.
            lang: the (code)language of that formatted block (not supported by most backends)
            **kwargs: Additional keyword arguments for the verbatim element.

        Returns:
            Doc: self (for method chaining).
        """
        self.add(construct('verbatim', children=children, color=color, end=end, lang=lang, **kwargs), index=index, chapter=chapter)
        return self
    

    def add_fig(self, fig: Any = None, caption: str = '', width: Optional[float] = None,
                bbox_inches: str = 'tight', children: Optional[str] = None,
                index: Optional[int] = None, chapter: Optional[Union[str, int]] = None,
                color: str = '', end: Optional[str] = None, **kwargs: Any) -> 'Doc':
        """Add a matplotlib figure to this document as an image element.

        Args:
            fig: Matplotlib figure object (or None to use current figure).
            caption: The caption to give to the image.
            width: The width for the image in the document. None lets the formatter decide.
            bbox_inches: Bounding box for figure save (passed to matplotlib.savefig).
            children: Specific name/id for the image (auto-generated if None).
            index: The list index where to insert. If None, appends to end.
            chapter: Chapter name or index for insertion. If None, appends to end.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.
            **kwargs: Additional keyword arguments passed to matplotlib.savefig.

        Returns:
            Doc: self (for method chaining).
        """
        self.add(constr.image_from_fig(caption=caption, width=width, bbox_inches=bbox_inches, children=children, fig=fig, color=color, end=end, **kwargs), index=index, chapter=chapter)
        return self
    

    def add_image(self, image: Any, caption: str = '', width: Optional[float] = None,
                  children: Optional[str] = None, index: Optional[int] = None,
                  chapter: Optional[Union[str, int]] = None, color: str = '',
                  end: Optional[str] = None, **kwargs: Any) -> 'Doc':
        """Add an image element to this document from various input types.

        Image input can be:
            -  HTTP URL string (downloaded automatically)
            -  File path string (local file)
            -  Base64-encoded image data string
            -  Matplotlib Figure object
            -  NumPy array (NxM, NxMx1, or NxMx3)
            -  PIL Image object
            -  File-like object with read() method

        Args:
            image: The image source. See supported types above.
            caption: The caption to give to the image.
            width: The width for the image in the document. None lets the formatter decide.
            children: Specific name/id for the image (auto-generated if None).
            index: The list index where to insert. If None, appends to end.
            chapter: Chapter name or index for insertion. If None, appends to end.
            color: Color for rendering (not supported by all backends).
            end: Custom line ending.
            **kwargs: Additional keyword arguments.

        Returns:
            Doc: self (for method chaining).
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
    
    def copy(self) -> 'Doc':
        """Creates a deep copy of this document.

        Returns:
            Doc: A new Doc instance that is a deep copy of the current document.
        """
        return Doc(copy.deepcopy(self.data))
    
    def dump(self) -> List[Dict[str, Any]]:
        """Dump this document to a basic list of dicts (deep copy).

        Returns:
            List[Dict[str, Any]]: The individual parts of the document as a list of deep-copied dictionaries.
        """
        return [copy.deepcopy(v) for v in self]
    
    def _ret(self, m: Union[str, bytes], path_or_stream: Optional[Union[str, Path, IO[Any]]]) -> Union[str, bytes, bool, None]:
        """Internal method to return or write data to a path, stream, or return the value.

        Args:
            m: The data to write (string or bytes).
            path_or_stream: Path string, Path object, or file-like object to write to.
                If None, returns the data directly.

        Returns:
            The written data (str or bytes) if path_or_stream is None.
            True if written to a path/stream.
        """
        
        if path_or_stream and isinstance(path_or_stream, Path):
            if isinstance(m, str):
                path_or_stream.write_text(m)
            else:
                path_or_stream.write_bytes(m)
            return os.path.exists(path_or_stream)

        elif path_or_stream and isinstance(path_or_stream, (str, Path)):
            mode = 'w' if isinstance(m, str) else 'wb'
            encoding = 'utf-8' if isinstance(m, str) else None

            with open(path_or_stream, mode, encoding=encoding) as f:
                f.write(m)
            return os.path.exists(path_or_stream)
        
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
    
    def dumps(self, path_or_stream: Optional[Union[str, Path, IO[str]]] = None) -> str:
        """Alias for self.to_json.

        Args:
            path_or_stream: Path to save to, or file-like object. If None, returns string.

        Returns:
            str: The JSON data as string if path_or_stream is None, or True if written to a file/stream.
        """
        return self.to_json(path_or_stream)

    def to_json(self, path_or_stream: Optional[Union[str, Path, IO[str]]] = None) -> str:
        """
        Converts the current document to a JSON file or string.

        Args:
            path_or_stream: Path string, Path object, or file-like object to write the data to.
                If None, the JSON string is returned.

        Returns:
            str: The JSON data as a string if path_or_stream is None.
                True if the data was saved successfully to a file or stream.
        """
        return self._ret(json.dumps(self.dump(), cls=CommonJSONEncoder, indent=2), path_or_stream)

    def to_markdown(self, path_or_stream: Optional[Union[str, Path, IO[str]]] = None, embed_images: bool = True) -> Union[str, bool]:
        """
        Converts the current document to a Markdown string or writes it to a file.

        Args:
            path_or_stream: Path string, Path object, or file-like object to write to.
                If None, the Markdown string is returned.
            embed_images: Whether to embed images as base64 strings within the Markdown.

        Returns:
            The Markdown string if path_or_stream is None.
            True if the Markdown was successfully written to a file or stream.
        """
        return self._ret(to_markdown(self.dump(), embed_images=embed_images), path_or_stream)

    def to_docx(self, path_or_stream: Optional[Union[str, Path, IO[bytes]]] = None,
                template: Optional[str] = None, template_params: Optional[Dict[str, Any]] = None,
                use_w32: bool = False, as_pdf: bool = False, compress_images: bool = False,
                allow_pandoc: bool = True) -> Union[bytes, bool]:
        """
        Converts the current document to a DOCX file, or a PDF file via DOCX.
        WARNING: Some PDF options require win32com and Microsoft Word installed.

        Args:
            path_or_stream: Path string, Path object, or file-like object to write to.
                If None, the DOCX bytes are returned.
            template: Path to a DOCX template file. Defaults to None (default template).
            template_params: Dictionary of parameters to replace fields in the template.
            use_w32: Whether to use win32com for document field updating (needs win32com + Word installed).
            as_pdf: Whether to output the document as a PDF (via docx + win32com).
            compress_images: Whether to compress images in the document using win32com.
            allow_pandoc: Whether to allow pandoc to be used instead of python-docx (usually produces nicer documents).
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

    def to_ipynb(self, path_or_stream: Optional[Union[str, Path, IO[str]]] = None) -> Union[str, bool]:
        """
        Converts the current document to an ipynb (IPython notebook) file.

        Args:
            path_or_stream: Path string, Path object, or file-like object to write to.
                If None, the JSON string is returned.

        Returns:
            The JSON string if path_or_stream is None.
            True if successfully written to a file or stream.
        """
        return self._ret(to_ipynb(self.dump()), path_or_stream)
    
    def to_html(self, path_or_stream: Optional[Union[str, Path, IO[str]]] = None,
                template: Optional[Any] = None,
                template_params: Optional[Dict[str, Any]] = None) -> str:
        """
        Converts the current document to a HTML file/string.

        Uses template parameters from document metadata if no explicit template is provided.

        Args:
            path_or_stream: Path string, Path object, or file-like object to write to.
            template: A Jinja2 Template object or string for the HTML template.
                If None, a default template or one from document metadata is used.
            template_params: Dictionary of parameters for the HTML template, passed to Jinja2's render method.
                Merged with template parameters from document metadata.

        Returns:
            str: The HTML content if path_or_stream is None.
                True if the data was saved successfully to a file or stream.
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

        # Pass the fully-merged `params` (meta defaults + caller overrides) to the
        # backend renderer, not the raw `template_params` argument. Using the raw
        # argument silently dropped parameters set via set_template_to_meta()
        # or stored in document metadata, causing templates to render with
        # missing fields (e.g. empty <title>, missing references table).
        return self._ret(to_html(self.dump(), template=template, template_params=params), path_or_stream)

    def to_typst(self, path_or_stream: Optional[Union[str, Path, IO[str]]] = None,
                 template: Optional[Union[str, jinja2.Template]] = None,
                 template_params: Optional[Dict[str, Any]] = None) -> str:
        """
        Converts the current document to a Typst file/string.

        Uses template parameters from document metadata if no explicit template is provided.

        Args:
            path_or_stream: Path string, Path object, or file-like object to write to.
            template: A Jinja2 Template object or string for the Typst template.
                If None, a default template or one from document metadata is used.
            template_params: Dictionary of parameters for the Typst template, passed to Jinja2's render method.
                Merged with template parameters from document metadata.

        Returns:
            str: The Typst source if path_or_stream is None.
                True if the data was saved successfully to a file or stream.
        """
        params = {}
        meta = self.get_meta(default={}).get('data', {})
        mytemplate = self.get_template_from_meta(tformat='typ')
        if template is None and not mytemplate is None:
            template = mytemplate.template
        if not mytemplate is None and mytemplate.params:
            params_from_meta = mytemplate.params
        else:
            params_from_meta = {k:v for k, v in meta.items() if not k in ["template_id", "files_to_upload", "additional_files", "attachments", "template"]}
        params.update(params_from_meta)

        if template_params:
            params.update(template_params)

        return self._ret(to_typst(self.dump(), template=template, template_params=params), path_or_stream)
        

    def to_pdf(self, 
               path_or_stream:Union[str,Path,IO[bytes]]=None, 
               docname:str='', 
               files_to_upload:Union[Dict[str,bytes],None]=None, 
               base_dir:Union[str,None]=None, 
               engine:Union[str,None]=None, 
               latex_compiler:Union[str,None]=None, 
               n_times_make:Union[int,None]=None, 
               verb:int=0, 
               ignore_error:bool=True, 
               template:Union[str, jinja2.Template, None]=None, 
               template_params:Union[Dict[str,Any],None]=None, 
               do_escape_template_params:str='auto', 
               **kwargs) -> Union[str, bytes, bool]:
        """Converts the current object to a PDF file or zipped LaTeX project folder.

        Args:
            path_or_stream (str or file-like object, optional): The output destination.
                If it's a string ending with '.pdf', it will be written in PDF format to the given path.
                If it's a string ending with '.zip', the whole project folder used for making the PDF file will be zipped and saved under the given path.
                If it's 'zip' or 'pdf', the data will be returned in the given format.
                If it's None, the PDF data will be returned as a bytes object.
            docname (str, optional): The name of the output document. Defaults to a unix timestamp followed by '_mydocument'.
            files_to_upload (dict, optional): A dictionary of files to be included with the document.
            base_dir (str, optional): The directory to use as the base directory for the temporary directory.
                Defaults to the system's default temporary directory.
            engine (str, optional): The PDF engine to use (one of "typst", "tex", "latextex", "word", "libreoffice", or "pandoc").
                If None, the engine is first inferred from the template via determine_engine_from_template(), then from any default
                template in meta via get_template_from_meta(), and finally from the config via config_pdf_engine_get().
            latex_compiler (str, optional): Only used if engine resolves to "tex". The LaTeX compiler to use.
                Either 'pdflatex', 'lualatex', 'xelatex', or 'pandoc'. If not specified, the function will try to
                use 'pandoc', 'pdflatex', 'lualatex', or 'xelatex' in that order.
            n_times_make (int, optional): Only used if engine resolves to "tex". The number of times to run the LaTeX compiler.
                Defaults to 1 for pandoc and 3 for all others.
            verb (int, optional): The verbosity level (0, 1, 2). If greater than 0, the function will print more and more debug information. Defaults to 0.
            ignore_error (bool, optional): Whether to ignore errors during compilation. Defaults to True.
            template (str, optional): A string containing the document template code (either a Jinja2 template or plain LaTeX/Typst).
                If not provided, a default template will be used based on the detected format or configured engine.
            template_params (dict, optional): A dictionary containing parameters for the document template, passed to the "render" method of Jinja2.
            do_escape_template_params (str | bool, optional): Only valid for LaTeX templates. Whether to escape the template parameters.
                "auto" will scan for %%latex at the start of a string to determine if it's a LaTeX string.
                Defaults to 'auto'.

        Returns:
            Union[str, bytes, bool]: If path_or_stream is a file path, returns True on success or False on failure.
                If path_or_stream is 'pdf', 'zip', or None, returns the output as a bytes object (or str for certain engines).

        Raises:
            Warning: If the provided file path does not end with '.zip' or '.pdf', a warning is issued and the file is assumed to be in PDF format.

        See Also:
            additional_files (dict, optional): Passed via **kwargs; merged into files_to_upload.
            attachments (dict, optional): Passed via **kwargs; merged into files_to_upload.
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
            engine = determine_engine_from_template(template)
            if not engine is None and verb:
                log.info(f'Inferred {engine=} from provided template={limit_len(template, 30)!r}')

        if engine is None:
            tformat = None
        elif not template is None:
            tformat = determine_engine_from_template(template, engine)
        else:
            tformat = 'tex' if engine.endswith('tex') else ('typ' if engine.startswith('typ') else None)

        mytemplate = None
        if template is None:
            try:
                mytemplate = self.get_template_from_meta(tformat=tformat, raise_on_error=True)    
            except KeyError as err:
                if not tformat is None: # fall back to check if any template with that given id exists
                    mytemplate = self.get_template_from_meta(raise_on_error=False)    


        if not mytemplate is None:
            template = mytemplate.template
            tformat = mytemplate.tformat
            params_from_meta = mytemplate.params
            files_to_upload = {**mytemplate.attachments, **files_to_upload}
        else:
            params_from_meta = {k:v for k, v in meta.items() if not k in ["template_id", "files_to_upload", "additional_files"]}

        params.update(params_from_meta)

        if template_params:
            params.update(template_params)

        if engine is None and tformat:
            engine = tformat
        elif engine is None:
            engine = config_pdf_engine_get()

        if engine is None:
            raise ValueError(f"engine could not be determined either from template of pydocmaker.config")

        if engine.startswith('typ'):
            engine = 'typ' 
        elif engine.endswith('tex'):
            engine = 'tex'

        # make sure my template format matches my engine
        if template and tformat and engine != tformat:
            raise ValueError(f'The requested {template=} is of format "{tformat!r}" while the current engine is "{engine}" which requires "{engine}" for templates.')
            
        if verb:
            log.info(f'making PDF with {engine=}')
        if verb > 1:
            log.info(f'   {template=}')
            log.info(f'   {params.keys()=}')
            log.info(f'   {files_to_upload.keys()=}')

        if engine.startswith('typ'):

            def _to_pdf_typst(*ar, **kw):
                s, attachments = to_typst(*ar, template=template, template_params=params, ret_attachments=True)

                on_warning = kw.pop("on_warning", None)
                if on_warning is None:
                    if ignore_error and verb:
                        on_warning = 'warn'
                    elif ignore_error and not verb:
                        on_warning = 'ignore'
                    elif verb:
                        on_warning = 'log'

                a = kw.pop("attachments", None)
                if a:
                    attachments.update(a)

                if files_to_upload:
                    attachments.update(files_to_upload)

                # Only pass root if base_dir is set to avoid Windows error 123
                root_kw = {'root': base_dir} if base_dir else {}
                bulk_kw = {k: v for k, v in kwargs.items() if k not in ('on_warning', 'attachments')}
                return to_pdf_typst(s, verb=verb, on_warning=on_warning, attachments=attachments, **root_kw, **bulk_kw)

            fun = _to_pdf_typst
        elif engine == 'tex' or engine == 'latex' or engine.endswith('tex'):
            
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
            raise ValueError(f"unknown engine, Engine must be one of {ALLOWED_ENGINES_PDF!r} but was {engine=}")
        

        r = self._ret(fun(self.dump(), **kwargs), path_or_stream)

        if isinstance(path_or_stream, (str, os.PathLike)) and verb:
            log.info(f'Saved to path_or_stream="{path_or_stream}" with function "{fun.__name__}"')

        return r
    

    
    def to_tex(self, path_or_stream: Optional[Union[str, Path, BinaryIO]] = None,
               additional_files: Optional[Dict[str, bytes]] = None,
               template: Optional[str] = None,
               do_escape_template_params: Union[str, bool] = 'auto',
               template_params: Optional[Dict[str, Any]] = None,
               text_only: bool = False) -> Union[bool, str, Tuple[str, Dict[str, bytes]], Tuple[bytes, Dict[str, bytes]]]:
        """Converts the current document to a TEX file (and attachments) as a ZIP archive.

        The output is always a ZIP file containing doc.json, main.tex, and any attachment files.
        If saving to a file or stream, returns True on success.
        If not saving, returns a tuple of (tex_as_bytes, files_dict) by default,
        or just the tex string if text_only=True.

        Args:
            path_or_stream: Path string, Path object, or file-like object to write the ZIP to.
            additional_files: Extra files to include in the ZIP (e.g., images, logos).
            template: The LaTeX template (Jinja2) to use. If None, uses one from document metadata.
            do_escape_template_params: Whether to escape LaTeX special chars in template params.
                'auto' detects LaTeX templates automatically.
            template_params: Additional parameters to pass to the LaTeX template.
            text_only: If True and path_or_stream is None, returns the raw tex string instead of ZIP bytes.

        Returns:
            bool: True if saved to a file/stream.
            Tuple[str, Dict[str, bytes]]: The tex string and file dict if returning and not text_only.
            str: The tex string if text_only=True.
            Tuple[bytes, Dict[str, bytes]]: The ZIP bytes and file dict if path_or_stream is None.
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

        # Pass the fully-merged `params` (meta defaults + caller overrides) to the
        # backend renderer, not the raw `template_params` argument. Using the raw
        # argument silently dropped parameters set via set_template_to_meta()
        # or stored in document metadata, so LaTeX templates rendered without
        # their configured defaults.
        tex, files = to_tex(self.dump(), with_attachments=True, template=template, files_to_upload=additional_files, do_escape_template_params=do_escape_template_params, template_params=params)

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
    
    def to_textile(self, path_or_stream: Optional[Union[str, Path, BinaryIO]] = None,
                   text_only: bool = False) -> Union[bool, str, Tuple[str, Dict[str, bytes]]]:
        """
        Converts the current document to a TEXTILE file (and attachments) as a ZIP archive.

        If path_or_stream is given, the ZIP is written to the stream or file path.
        Otherwise returns a tuple of (textile_str, files_dict), or just the textile string if text_only=True.

        Args:
            path_or_stream: Path string, Path object, or file-like object to write the ZIP to.
            text_only: If True and path_or_stream is None, returns just the textile string.

        Returns:
            bool: True if saved to a file or stream.
            str: The textile source string if text_only=True.
            Tuple[str, Dict[str, bytes]]: The textile string and file dict if returning and not text_only.
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
        
    def to_redmine(self) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Converts the current document to Redmine-compatible Textile formatted text and attachments.

        Returns:
            Tuple[str, List[Dict[str, Any]]]: A tuple of (textile_text, attachment_dicts).
                Each attachment dict has keys: path, filename, content_type, description.
        """

        return to_textile(self.dump(), with_attachments=True, aformat_redmine=True)
    
    def to_redmine_upload(self, redmine: Any, project_id: Union[str, int],
                          report_name: Optional[str] = None,
                          page_title: Optional[str] = None,
                          force_overwrite: bool = False, verb: bool = True) -> str:
        """Converts the current document to Redmine Textile format and uploads it to a Redmine wiki page.

        This will also export the document to all possible formats and attach them to the wiki page.
        This will also export the document to all possible formats and attach them to the wiki page.

        Args:
            redmine: A Redmine connection object (redminelib.Redmine instance).
            project_id: The ID of the Redmine project where the report should be uploaded.
            report_name: The name of the report. If None, uses a timestamp-based default.
            page_title: The title of the Redmine wiki page. If None, derived from the report name.
            force_overwrite: Whether to overwrite an existing page with the same title.
            verb: Whether to print verbose output during upload.

        Returns:
            str: The URL of the uploaded Redmine wiki page.

        Raises:
            AssertionError: If any of the `project_id` or `redmine` arguments is None.
        """
            
        return upload_report_to_redmine(self, redmine=redmine, project_id=project_id, report_name=report_name, page_title=page_title, force_overwrite=force_overwrite, verb=verb)
    
    def print_rich(self, path_or_stream: Optional[Union[str, IO[str]]] = None,
                   title: Optional[str] = None, embed_images: bool = True) -> Optional[bool]:
        """
        Renders the current document using the Python Rich library and outputs it to the console or a file.

        Attempts to extract a title from document metadata if not provided.

        Args:
            path_or_stream: File path string, file-like object with a write method, or None for stdout.
            title: Optional title for the documentation. If None, attempts to extract from metadata
                using common title keys (title, TITLE, filename, name, docname, etc.).
            embed_images: If True, images appear as simplified pixelized pictures on the console.
                If False, a placeholder is inserted instead.

        Returns:
            bool: True if path_or_stream is not None and writing was successful.
                None if output went to stdout.

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


    def to_pdf_print(self, path_or_stream: Optional[Union[str, IO[bytes]]] = None) -> Optional[Union[bytes, bool]]:
        """Exports the document to a PDF file using the system's "print to PDF" function (HTML to PDF).

        WARNING: This function only works on POSIX-like operating systems and requires a PDF printer
        to be installed and set as default printer. It will not work on Windows or macOS.
        The resulting PDF quality is lower than proper PDF engines like pdflatex, typst, or word.
        
        WARNING II: The resulting PDF file will not be of the same quality as a PDF file generated by a proper PDF engine like 
        pdflatex, typst, or word. It is recommended to use this function only as a last resort if no other PDF engine is 
        available and you need a quick and dirty PDF file.

        Args:
            path_or_stream: Path string for output PDF, file-like object to write to, or None to return bytes.

        Returns:
            bytes if path_or_stream is None.
            bool (True/False) if path_or_stream is a file or stream.
            None if a file/path was given as string but could not determine the return.

        Raises:
            AssertionError: If the OS is not POSIX.
            IOError: If the PDF file could not be written.
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

    def export_all(self, dir_path: Optional[str] = None, report_name: str = 'exported_report',
                   **kwargs: Any) -> Dict[Union[str, bytes], Any]:
        """
        Exports the document to all supported formats.

        Calls export_many with all engines from Doc.EXPORT_ENGINES.

        Args:
            dir_path: Directory path where exported files should be saved. If None,
                returns a dict mapping keys to exported data.
            report_name: Base name for the exported files.
            **kwargs: Additional keyword arguments specific to each export format.

        Returns:
            Dict mapping keys (file paths if dir_path given, or report_name+extension if not)
            to the exported data (bytes, str, or True).
        """
        return self.export_many(engines=None, dir_path=dir_path, report_name=report_name, **kwargs)

    def export_many(self, engines: Optional[List[str]] = None, dir_path: Optional[str] = None,
                    report_name: str = 'exported_report', **kwargs: Any) -> Dict[Union[str, bytes], Any]:
        """
        Exports the document to multiple specified formats.

        Args:
            engines: List of export engine names (e.g., 'md', 'html', 'pdf', 'docx').
                If None or empty, exports to all engines in Doc.EXPORT_ENGINES.
            dir_path: Directory path where exported files should be saved. If None,
                returns a dict mapping keys to exported data.
            report_name: Base name for the exported files.
            **kwargs: Additional keyword arguments, potentially keyed by engine name.

        Returns:
            Dict mapping keys to exported data.
                If dir_path is given: keys are full file paths, values are bools.
                If dir_path is None: keys are report_name+extension strings, values are raw data.
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
    

    def export(self, engine: str, path_or_stream: Optional[Union[str, Path, BinaryIO, TextIO]] = None,
               **kwargs: Any) -> Any:
        """Exports the document to a specified format.

        Dispatches to the appropriate to_* method based on the engine name.

        Args:
            engine: The format to export to. Valid options: 'md', 'markdown', 'json', 'html',
                'typst', 'typ', 'pdf', 'tex', 'latex', 'textile', 'ipynb', 'jupyter',
                'notebook', 'word', 'docx', 'redmine'.
            path_or_stream: Path string, Path object, or file-like object to write to.
            **kwargs: Additional keyword arguments specific to the chosen export format.

        Returns:
            The exported data (str, bytes, bool, tuple, or dict) depending on the engine and whether
            path_or_stream was provided.

        Raises:
            KeyError: If the specified engine is not supported.
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
        
    def upload(self, url: str, doc_name: str = '', force_overwrite: bool = False,
               page_title: str = '', requests_kwargs: Optional[Dict[str, Any]] = None,
               raise_on_fail: bool = True, warn_on_fail: bool = True) -> Dict[str, Any]:
        """Uploads the document data to a specified URL via HTTP POST.

        The JSON body sent is:
            {"doc_name": doc_name, "doc": self.dump(), "force_overwrite": force_overwrite, "page_title": page_title}

        Args:
            url: The URL endpoint that accepts the document data.
            doc_name: The name of the uploaded document.
            force_overwrite: Whether to overwrite an existing document at the destination.
            page_title: Title of the uploaded document (if applicable).
            requests_kwargs: Dictionary of keyword arguments passed to requests.post().
            raise_on_fail: If True, raises requests.exceptions.RequestException on non-2xx status.
            warn_on_fail: If True, emits a warning with server response text on failure.

        Returns:
            dict: The JSON response from the server after uploading.

        Raises:
            requests.exceptions.RequestException: If raise_on_fail is True and the upload fails.
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
    

    


    def show(self, engine: Optional[str] = None, index: Optional[int] = None,
             chapter: Optional[str] = None, files_to_upload: Optional[Dict[str, bytes]] = None,
             template: Optional[Any] = None,
             template_params: Optional[Dict[str, Any]] = None,
             do_escape_template_params: bool = False,
             embed_images: bool = True, **kwargs: Any) -> None:
        """Displays the document or a specific part of it via IPython display or print to console.

        For IPython/Jupyter environments, uses HTML, Markdown, PDF, or Code display widgets.
        For non-notebook environments, prints to stdout in the chosen format.

        Args:
            engine: Display engine to use. None decides based on environment (html in notebooks, rich in console).
                Options: 'html', 'markdown', 'md', 'tex', 'latex', 'pdf' (notebook only),
                'typst', 'auto', 'rich', 'console', 'terminal', 'plain'.
            index: Display only the document part at this list index.
            chapter: Display only the content of this named chapter.
            files_to_upload: EXTRA ONLY WHEN engine='pdf'. Additional files for PDF generation (see to_pdf).
            template: ONLY WHEN engine='pdf' or 'html'. Template string or Jinja2 Template object.
            template_params: ONLY WHEN engine='pdf' or 'html'. Template parameters dict.
            do_escape_template_params: ONLY WHEN engine='pdf'. Whether to escape template params for LaTeX.
            embed_images: ONLY WHEN engine='md' or 'rich'. Whether to embed images or show placeholders.
            **kwargs: Additional arguments passed to the export method.

        Raises:
            KeyError: If the specified engine is not valid for the current environment.
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
            
    def __repr__(self, *args: Any, **kwargs: Any) -> str:
        """Return a summary string with number of chapters and element count."""
        chaps = self.get_chapters()
        return f'pydocmaker.Doc with N={len(chaps)} chapters, K={len(self)} elements.'

    def __str__(self, *args: Any, **kwargs: Any) -> str:
        """Alias for __repr__."""
        return self.__repr__()

    
    @classmethod
    def get_example(cls) -> 'Doc':
        """Create and return a sample document with various element types.

        Returns a Doc containing markdown text, verbatim code blocks, LaTeX, a table,
        and an embedded base64 image. Useful for testing and documentation examples.

        Returns:
            Doc: A sample document instance.
        """
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
}""")
        doc.add_tex("\\textit{This is some dummy LaTeX text.}")

        doc.add_md("This is how to embed a table:")

        header = ['Name', 'Age', 'City']
        table = [
            ['John Doe', "30", 'New York'],
            ['Jane Smith', "25", 'Los Angeles'],
            ['Mike Johnson', "35", 'Chicago']
        ]
        doc.add_table(table, header=header, borders=True, caption='This is my example table')

        doc.add('And this is how to embed an Image:')
        doc.add_image(image=make_png_imageblob(b64_data.example_image), caption="This is an example image.")
        
        return doc
    

    
def _construct(v: Any) -> Any:
    """Recursively construct document part dicts from nested structures.

    Converts lists of dicts by recursively calling construct on each dict element.
    List elements not containing dicts are recursively processed.
    String elements are returned as-is.

    Args:
        v: A value that may be a string, list, or dict representing a document part.

    Returns:
        The constructed value (string, list, or dict).
    """
    if isinstance(v, str):
        return v
    elif isinstance(v, list):
        return [_construct(vv) for vv in v]
    elif isinstance(v, dict):
        return construct(**v)
    else:
        raise TypeError(f'{type(v)=} is of unknown type. Only dataclass, str, list, and dict are allowed!')

def construct(typ: str, **kwargs: Any) -> Dict[str, Any]:
    """Construct a document-part dict from the given type name and keyword arguments.

    Looks up the constructor in the `constr` class (using typalias for name resolution).
    Recursively constructs nested 'children' content before calling the constructor.

    Args:
        typ: The document part type (e.g., 'markdown', 'text', 'verbatim', 'latex', 'image', 'table', 'iter').
        **kwargs: Arguments passed to the constructor function.

    Returns:
        A dict representing the document part, or the typ string directly if no constructor and no kwargs.

    Raises:
        AssertionError: If typ is not a string.
        TypeError: If the type is unknown.
    """
    assert isinstance(typ, str)
    typ = constr.typalias.get(typ, typ)
    if not kwargs and not hasattr(constr, typ):
        return typ  # type: ignore
    elif hasattr(constr, typ):
        children = kwargs.get('children')
        if children:
            kwargs['children'] = _construct(children)
        constructor = getattr(constr, typ)
        return constructor(**kwargs)
    else:
        raise TypeError(f'{typ=} is of unknown type. Only dataclass, str, list, and dict are allowed!')


def load(doc: Union[List[Dict[str, Any]], str, bytes, BinaryIO, TextIO]) -> 'Doc':
    """Loads a document from a list of dictionaries, JSON string, file path, or stream.

    Accepts:
        - A list of doc-part dicts
        - A JSON string starting with '['
        - A file path string
        - A binary or text file-like object with read() and seek() methods

    Args:
        doc: Document data as a list of dicts, JSON string, file path, or stream.

    Returns:
        Doc: A Doc object representing the loaded document.

    Raises:
        AssertionError: If doc is not a list after parsing.
        ValueError: If the file or stream cannot be loaded.
    """
    if isinstance(doc, bytes):
        doc = doc.decode()

    if isinstance(doc, str) and doc.strip().startswith('['):
        doc = json.loads(doc, cls=MyJSONDecoder)

    if isinstance(doc, str):
        with open(doc, 'r') as fp:
            doc = json.load(fp, cls=MyJSONDecoder)
    
    if hasattr(doc, 'read') and hasattr(doc, 'seek'):
        doc = json.load(fp, cls=MyJSONDecoder)

    assert isinstance(doc, list), f'doc must be list but was {type(doc)=} {doc=}'
    return Doc(doc)

    

    
    


def print_to_pdf(file_path: str, output_pdf_path: str) -> None:
    """Prints a file to a PDF file using platform-specific subprocess commands.

    WARNING: This function only works on POSIX-like operating systems and requires a PDF printer
    to be installed and set as default printer. It will not work on Windows or macOS.
    The resulting PDF quality may be lower than proper PDF engines.

    WARNING II: The resulting PDF file will not be of the same quality as a PDF file generated by a proper PDF engine like 
    pdflatex, typst, or word. It is recommended to use this function only as a last resort if no other PDF engine is 
    available and you need a quick and dirty PDF file.

    
    Args:
        file_path: Path to the input file (typically an HTML file).
        output_pdf_path: Path for the output PDF file.

    Raises:
        ValueError: If the platform is not POSIX, or paths don't exist.
        subprocess.CalledProcessError: If the print command fails.
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




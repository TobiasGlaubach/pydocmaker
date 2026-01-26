__version__ = '2.5.2'

from pydocmaker.core import Doc, construct, constr, buildingblocks, print_to_pdf, get_latex_compiler, set_latex_compiler, make_pdf_from_tex, show_pdf
from pydocmaker.util import upload_report_to_redmine, bcolors, txtcolor, colors_dc

from pydocmaker.backend.ex_docx import DocxFile, DocxFileW32
from pydocmaker.backend.ex_tex import can_run_pandoc
from pydocmaker.backend.pdf_maker import get_all_installed_latex_compilers, get_latex_compiler
from pydocmaker.backend.pandoc_api import pandoc_convert_file, pandoc_set_allowed

from pydocmaker.templating import DocTemplate, TemplateDirSource, register_new_template_dir, get_registered_template_dirs, get_available_template_ids, test_template_exists, remove_from_template_dir

from latex import escape as tex_escape

try:
    # tests and caches already if pandoc is installed when import is used, so its faster later when we want to use it (or not)
    can_run_pandoc() 
except Exception as err:
    pass

def pandoc_set_enabled():
    """short for pandoc_set_allowed(True), which will allow pandoc to be used as a valid conversion option"""
    return pandoc_set_allowed(True)

def pandoc_set_disabled():
    """short for pandoc_set_allowed(False), which will disallow pandoc to be used as a valid conversion option"""
    return pandoc_set_allowed(False)


def get_schema():
    return {k: getattr(constr, k)() for k in buildingblocks}
        
def get_example():
    return Doc.get_example()


def load(path):
    """Load a JSON file and return a Doc object.

    Args:
        path (str or file-like object): The path to the JSON file or a file-like object.

    Returns:
        Doc: A Doc object initialized with the loaded JSON data.

    Raises:
        json.JSONDecodeError: If the JSON file is not valid.
        TypeError: If the loaded JSON object is not of type list.
    """
    return Doc.load_json(path)

def md2tex(children='', **kwargs):
    """convenience function to quickly convert markdown to tex

    Args:
        children (str, optional): the markdown string to convert. Defaults to ''.

    Returns:
        str: the corresponding tex string
    """
    return Doc().add_md(children=children, **kwargs).to_tex(text_only=True)


def mk_chapter(title, description, parent=None, order=None):
   """Creates a new chapter.

   Args:
       title (str): The title of the chapter.
       description (str): A brief description of the chapter.
       parent (Chapter, optional): The parent chapter. Defaults to None.
       order (int, optional): The order of the chapter. Defaults to None.

   Returns:
       Chapter: The newly created chapter.
   """
   return Doc.add_chapter(title, description, parent, order)[0]


def mk_meta(project_name, version, description, author, author_email, url, license):
   """
   Generate metadata for the documentation.

   Args:
       project_name (str): The name of the project.
       version (str): The version of the project.
       description (str): A brief description of the project.
       author (str): The author's name.
       author_email (str): The author's email address.
       url (str): The URL of the project.
       license (str): The license of the project.

   Returns:
       dict: A dictionary containing the metadata.
   """
   return Doc.add_meta(project_name, version, description, author, author_email, url, license)[0]


def mk_tex(children=None, index=None, chapter=None, color='', end=None, **kwargs):
   """
   Creates a new LaTeX document part.

   Args:
       children (str or list, optional): The "children" for this element. Either text directly (as string) or a list of other parts.
       index (int, optional): The index where to insert the part. If None, appends to the end.
       chapter (str | int, optional): The chapter name or index where to insert the part. If None, appends to the end.
       color (str, optional): Any color which can be rendered by HTML or LaTeX. Empty string for default.
       end (str, optional): If you want to insert a different line ending (than the default) for this element set this argument to any string. None for default.
       **kwargs: Additional keyword arguments for the document part.

   Returns:
       dict: The newly created LaTeX document part.
   """
   return Doc().add_tex(children=children, index=index, chapter=chapter, color=color, end=end, **kwargs)[0]

def mk_md(children=None, index=None, chapter=None, color='', end=None, **kwargs):
   """
   Creates a new markdown document part.

   Args:
       children (str or list, optional): The "children" for this element. Either text directly (as string) or a list of other parts.
       index (int, optional): The index where to insert the part. If None, appends to the end.
       chapter (str | int, optional): The chapter name or index where to insert the part. If None, appends to the end.
       color (str, optional): Any color which can be rendered by html or latex. Empty string for default.
       end (str, optional): If you want to insert a different line ending (than the default) for this element set this argument to any string. None for default.
       **kwargs: Additional keyword arguments for the document part.

   Returns:
       dict: The newly created markdown document part.
   """
   return Doc().add_md(children=children, index=index, chapter=chapter, color=color, end=end, **kwargs)[0]


def mk_pre(children=None, index=None, chapter=None, color='', end=None, **kwargs):
   """
   Creates a preformatted document part.

   Args:
       children (str or list, optional): The "children" for this element. Either text directly (as string) or a list of other parts.
       index (int, optional): The index where to insert the part. If None, appends to the end.
       chapter (str | int, optional): The chapter name or index where to insert the part. If None, appends to the end.
       color (str, optional): Any color which can be rendered by HTML or LaTeX. Empty string for default.
       end (str, optional): If you want to insert a different line ending (than the default) for this element set this argument to any string. None for default.
       **kwargs: Additional keyword arguments for the document part.

   Returns:
       dict: The created document part.
   """
   return Doc().add_pre(children=children, index=index, chapter=chapter, color=color, end=end, **kwargs)[0]


def mk_fig(fig=None, caption='', width=0.8, bbox_inches='tight', children=None, color='', end=None, **kwargs):
    """make an image document part from a pyplot figure type dict from given image input.
    
    Args:
        fig (matplotlib figure, optional): the figure which to upload (or the current figure if None). Defaults to None.
        caption (str, optional): the caption to give to the image. Defaults to ''.
        width (float, optional): The width for the image to have in the document. Defaults to 0.8.
        bbox_inches (str, optional): will give better spacing for matplotlib figures.
        children (str, optional): A specific name/id to give to the image (will be auto generated if None). Defaults to None.
        index (int, optional): The index where to insert the part. If None, appends to the end.
        chapter (str | int, optional): The chapter name or index where to insert the part. If None, appends to the end.
        color (str, optional): any color which can be rendered by html or latex. Empty string for default.
        end (str, optional): If you want to insert a different line ending (than the default) for this element set this argument to any string. None for default.

    Returns:
        dict: The created document part.
    """
    return Doc().add_fig(fig=fig, caption=caption, width=width, bbox_inches=bbox_inches, children=children, color=color, end=end, **kwargs)[0]

def mk_image(image, caption='', width=0.8, children=None, color='', end=None, **kwargs):
    """Make an image type dict from given image input.
    
    The image can be of type:
        - pyplot figure
        - link to download an image from
        - file-like object
        - numpy NxMx1 or NxMx3 matrix
        - PIL image

    Args:
        image: The image input, which can be a pyplot figure, a link, a file-like object, a numpy array, or a PIL image.
        caption (str, optional): The caption to give to the image. Defaults to ''.
        width (float, optional): The width for the image to have in the document. Defaults to 0.8.
        children (str, optional): A specific name/id to give to the image (will be auto-generated if None). Defaults to None.
        color (str, optional): Any color which can be rendered by HTML or LaTeX. Empty string for default. Defaults to ''.
        end (str, optional): If you want to insert a different line ending (than the default) for this element, set this argument to any string. None for default.
        **kwargs: Additional keyword arguments to pass to the underlying method.

    Returns:
        dict: A dictionary representing the image with the specified attributes.
    """
    return Doc().add_image(image, caption, width, children, color, end, **kwargs)[0]



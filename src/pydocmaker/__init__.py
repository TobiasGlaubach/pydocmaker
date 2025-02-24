__version__ = '2.1.6'

from pydocmaker.core import DocBuilder, construct, constr, buildingblocks, print_to_pdf, get_latex_compiler, set_latex_compiler, make_pdf_from_tex
from pydocmaker.util import upload_report_to_redmine, bcolors, txtcolor, colors_dc


from pydocmaker.backend.ex_tex import can_run_pandoc, get_default_tex_template
from pydocmaker.backend.pdf_maker import get_all_installed_latex_compilers, get_latex_compiler

from pydocmaker.core import DocBuilder as Doc
from latex import escape as tex_escape

try:
    # tests and caches already if pandoc is installed when import is used, so its faster later when we want to use it (or not)
    can_run_pandoc() 
except Exception as err:
    pass


def get_schema():
    return {k: getattr(constr, k)() for k in buildingblocks}
        
def get_example():
    return Doc.get_example()
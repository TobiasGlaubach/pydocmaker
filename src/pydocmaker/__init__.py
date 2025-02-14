__version__ = '1.4.3'

from pydocmaker.core import DocBuilder, construct, constr, buildingblocks, print_to_pdf, get_latex_compiler, set_latex_compiler, make_pdf_from_tex
from pydocmaker.util import upload_report_to_redmine

from pydocmaker.core import DocBuilder as Doc

def get_schema():
    return {k: getattr(constr, k)() for k in buildingblocks}
        
def get_example():
    return Doc.get_example()
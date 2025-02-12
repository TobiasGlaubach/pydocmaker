from pydocmaker.backends.native.ex_docx import docx_renderer as docx
from pydocmaker.backends.native.ex_html import html_renderer as html
from pydocmaker.backends.native.ex_ipynb import ipynb_renderer as ipynb
from pydocmaker.backends.native.ex_markdown import DocumentMarkdownFormatter as md
from pydocmaker.backends.native.ex_tex import ElementFormatter as tex

from pydocmaker.backends.native.ex_docx import convert as to_docx
from pydocmaker.backends.native.ex_html import convert as to_html
from pydocmaker.backends.native.ex_ipynb import convert as to_ipynb
from pydocmaker.backends.native.ex_markdown import convert as to_md
from pydocmaker.backends.native.ex_tex import convert as to_tex


def setup(*args, **kwargs):
    # we need the setup method for having compatible backends, but we actually to not need it for native
    pass


def to_pdf():
    raise NotImplementedError('Generating PDF reports is not implemented in native backend (yet)!')

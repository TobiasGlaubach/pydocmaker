"""Comment-delimited block templating engine for pydocmaker.

Standalone-compilable templating scheme (``pydocmaker:parameters`` / ``pydocmaker:body``
blocks) for HTML, LaTeX and Typst documents, running alongside the existing Jinja2
engine and selected by auto-detection with explicit override.

Public API (v1)::

    blocktmpl.parse(source, tformat=None, strict=True) -> BlockDocument
    blocktmpl.scaffold(source, tformat=None, params=None, body=None) -> str
    blocktmpl.update_params(source, params, tformat=None, strict=True) -> str
    blocktmpl.render(source, body, params=None, tformat=None, template_engine='auto', strict=True) -> str
    blocktmpl.detect(source, tformat=None) -> bool
    blocktmpl.BlockDocTemplate(template, params=None, attachments=None, tformat=None, template_id=None)
"""

from .markers import (detect_block_template, detect_format, normalize_tformat,
                      SECTION_MARKER_RE, PARAM_MARKER_RE, VALID_TFORMATS)
from .model import (BlockTemplatingError, MalformedBlockError, UnsupportedFormatError,
                    BodyReservedError, ParameterTypeError, BODY_RESERVED_MSG,
                    Parameter, BlockSection, BlockDocument)
from .adapter_base import FormatAdapter, get_adapter
from .adapter_html import HtmlFormatAdapter
from .adapter_tex import TexFormatAdapter
from .adapter_typ import TypstFormatAdapter
from .parser import parse
from .inference import scaffold
from .render import render, update_params, BlockDocTemplate

detect = detect_block_template

__all__ = [
    'parse', 'scaffold', 'update_params', 'render', 'detect', 'detect_block_template',
    'detect_format', 'normalize_tformat', 'BlockDocTemplate', 'FormatAdapter',
    'HtmlFormatAdapter', 'TexFormatAdapter', 'TypstFormatAdapter', 'get_adapter',
    'Parameter', 'BlockSection', 'BlockDocument', 'BlockTemplatingError',
    'MalformedBlockError', 'UnsupportedFormatError', 'BodyReservedError',
    'ParameterTypeError', 'BODY_RESERVED_MSG', 'SECTION_MARKER_RE', 'PARAM_MARKER_RE',
    'VALID_TFORMATS',
]

"""Marker constants, per-format comment syntax and regexes for the block templating engine.

The block templating engine uses comment-delimited markers which are alone on their
line (optional leading/trailing whitespace) so that plain ``.html`` / ``.tex`` / ``.typ``
files stay valid and compilable standalone:

    HTML  : ``<!-- pydocmaker:parameters:begin -->`` / ``<!-- pydocmaker:param:name -->``
    LaTeX : ``% pydocmaker:parameters:begin``          / ``% pydocmaker:param:name``
    Typst : ``// pydocmaker:parameters:begin``          / ``// pydocmaker:param:name``

This module is format-generic; the per format adapters in ``adapter_*.py`` carry the
strict per format regexes built from :func:`build_section_marker_re` and
:func:`build_param_marker_re`.
"""

import re

try:
    from pydocmaker import util
except Exception as err:
    from .. import util

from .model import UnsupportedFormatError

log = util.log

MARKER_PREFIX = 'pydocmaker:'
SECTION_KINDS = ('parameters', 'body')
SECTION_TAGS = ('begin', 'end')

#: format-generic section marker regex (works for all three formats)
SECTION_MARKER_RE = re.compile(
    r'(?m)^[ \t]*(?:<!--|[%/]{1,2})[ \t]*pydocmaker:(parameters|body):(begin|end)[ \t]*(?:-->[ \t]*)?$'
)

#: format-generic parameter marker regex (works for all three formats)
PARAM_MARKER_RE = re.compile(
    r'(?m)^[ \t]*(?:<!--[ \t]*|[%/][ \t]*)pydocmaker:param:(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]*(?:-->[ \t]*)?$'
)

PARAM_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

VALID_TFORMATS = ('html', 'tex', 'typ')


def normalize_tformat(tformat):
    """Normalize a format specifier to one of ``'html' | 'tex' | 'typ'`` or None.

    Accepts the lenient spellings used elsewhere in pydocmaker (e.g. ``'latex'``,
    ``'typst'``, ``'.tex'``, ``'html5'``). Returns ``None`` for ``None`` input.
    Raises :class:`~pydocmaker.blocktmpl.model.UnsupportedFormatError` for unknown values.
    """
    if tformat is None or tformat == '':
        return None
    if isinstance(tformat, str) and tformat.lower().startswith('html'):
        return 'html'
    if isinstance(tformat, str) and tformat.lower().startswith('typ'):
        return 'typ'
    if isinstance(tformat, str) and tformat.lower().endswith('tex'):
        return 'tex'
    raise UnsupportedFormatError(
        f"tformat must be one of {VALID_TFORMATS} (or a common alias such as 'latex'/'typst'), got '{tformat}'"
    )


def build_section_marker_re(tformat):
    """Build the strict per format section marker regex for ``tformat``."""
    tf = normalize_tformat(tformat)
    if tf == 'html':
        return re.compile(
            r'^[ \t]*<!--[ \t]*pydocmaker:(parameters|body):(begin|end)[ \t]*-->[ \t]*$'
        )
    if tf == 'tex':
        return re.compile(
            r'^[ \t]*%[ \t]*pydocmaker:(parameters|body):(begin|end)[ \t]*(?:-->[ \t]*)?$'
        )
    if tf == 'typ':
        return re.compile(
            r'^[ \t]*//[ \t]*pydocmaker:(parameters|body):(begin|end)[ \t]*(?:-->[ \t]*)?$'
        )
    raise UnsupportedFormatError(f'cannot build section marker regex for tformat={tformat!r}')


def build_param_marker_re(tformat):
    """Build the strict per format parameter marker regex for ``tformat``."""
    tf = normalize_tformat(tformat)
    if tf == 'html':
        return re.compile(
            r'^[ \t]*<!--[ \t]*pydocmaker:param:(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]*-->[ \t]*$'
        )
    if tf == 'tex':
        return re.compile(
            r'^[ \t]*%[ \t]*pydocmaker:param:(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]*(?:-->[ \t]*)?$'
        )
    if tf == 'typ':
        return re.compile(
            r'^[ \t]*//[ \t]*pydocmaker:param:(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]*(?:-->[ \t]*)?$'
        )
    raise UnsupportedFormatError(f'cannot build param marker regex for tformat={tformat!r}')


def comment_wrap(text, tformat):
    """Wrap ``text`` into a single-line comment for the given format."""
    tf = normalize_tformat(tformat)
    if tf == 'html':
        return f'<!-- {text} -->'
    if tf == 'tex':
        return f'% {text}'
    if tf == 'typ':
        return f'// {text}'
    raise UnsupportedFormatError(f'cannot build comment for tformat={tformat!r}')


def section_marker_line(kind, tag, tformat):
    """Build a full section marker line (e.g. ``% pydocmaker:parameters:begin``)."""
    if kind not in SECTION_KINDS:
        raise ValueError(f"section kind must be one of {SECTION_KINDS}, got '{kind}'")
    if tag not in SECTION_TAGS:
        raise ValueError(f"section tag must be one of {SECTION_TAGS}, got '{tag}'")
    return comment_wrap(f'pydocmaker:{kind}:{tag}', tformat)


def param_marker_line(name, tformat):
    """Build a full parameter marker line (e.g. ``% pydocmaker:param:title``)."""
    if not PARAM_NAME_RE.match(name or ''):
        raise ValueError(f'invalid parameter name: {name!r}')
    return comment_wrap(f'pydocmaker:param:{name}', tformat)


def detect_format(source):
    """Detect the document format ('html' | 'tex' | 'typ') from content markers.

    Falls back to the comment syntax of any pydocmaker block markers when no native
    content marker is found (e.g. for scaffolded fragments). Returns None if the
    format cannot be determined. The detection order mirrors
    ``templating.determine_engine_from_template``: html, then typ, then tex.
    """
    if not isinstance(source, str) or not source:
        return None
    low = source.lower()
    if '<html' in low or '<!doctype html' in low:
        return 'html'
    if '#set ' in source or '#let ' in source or '#show ' in source:
        return 'typ'
    if r'\documentclass' in source or r'\begin{document}' in source or r'\end{document}' in source:
        return 'tex'
    for regex in (SECTION_MARKER_RE, PARAM_MARKER_RE):
        for m in regex.finditer(source):
            ls = source.rfind('\n', 0, m.start()) + 1
            prefix = source[ls:m.end()].lstrip()
            if prefix.startswith('<!--'):
                return 'html'
            if prefix.startswith('%'):
                return 'tex'
            if prefix.startswith('//'):
                return 'typ'
    return None


def detect_block_template(source, tformat=None):
    """Return True if the source contains at least one block templating marker line.

    Uses the format-generic regexes unless ``tformat`` is given, in which case the
    markers must additionally be valid for the requested format.
    """
    if not isinstance(source, str) or not source:
        return False
    if not SECTION_MARKER_RE.search(source) and not PARAM_MARKER_RE.search(source):
        return False
    if tformat is None:
        return True
    tf = normalize_tformat(tformat)
    section_re = build_section_marker_re(tf)
    param_re = build_param_marker_re(tf)
    for line in source.splitlines():
        if section_re.match(line) or param_re.match(line):
            return True
    return False

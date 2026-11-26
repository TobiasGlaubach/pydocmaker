"""LaTeX format adapter: marker syntax, assignment consumption and the LaTeX
value codecs (``\\providecommand``/``\\newcommand`` grammar with description/itemize
constructs, escaping and round-trip parsing)."""

import re

from .adapter_base import FormatAdapter, register_adapter
from .markers import build_section_marker_re, build_param_marker_re
from .model import ParameterTypeError

# --------------------------------------------------------------------------------------
# value codecs
# --------------------------------------------------------------------------------------

_LATEX_ESCAPES = (
    ('\\', r'\textbackslash{}'),
    ('~', r'\textasciitilde{}'),
    ('^', r'\textasciicircum{}'),
    ('&', r'\&'),
    ('%', r'\%'),
    ('$', r'\$'),
    ('#', r'\#'),
    ('_', r'\_'),
    ('{', r'\{'),
    ('}', r'\}'),
)

_INT_RE = re.compile(r'^[+-]?\d+$')
_FLOAT_RE = re.compile(r'^[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?$|^[+-]?\d+[eE][+-]?\d+$')

DESCRIPTION_BEGIN = r'\begin{description}'
DESCRIPTION_END = r'\end{description}'
ITEMIZE_BEGIN = r'\begin{itemize}'
ITEMIZE_END = r'\end{itemize}'

_BEGIN_ENV_RE = re.compile(r'\\begin\{(itemize|description)\}')
_END_ENV_RE = re.compile(r'\\end\{(itemize|description)\}')
_ITEM_RE = re.compile(r'\\item(?![A-Za-z])')

_RAW_SENTINEL = object()


def latex_escape(text):
    """Escape LaTeX special characters (minimal internal escaping, no optional deps)."""
    for ch, rep in _LATEX_ESCAPES:
        text = text.replace(ch, rep)
    return text


def latex_unescape(text):
    """Reverse :func:`latex_escape`."""
    for ch, rep in reversed(_LATEX_ESCAPES):
        text = text.replace(rep, ch)
    return text


def latex_macro_name(name):
    """Derive the LaTeX macro name for a parameter name (underscores are not valid
    in TeX control words, so they are removed, e.g. ``n_iter`` -> ``niter``)."""
    return str(name).replace('_', '')


def latex_scalar_text(value):
    """Scalar value as plain (escaped) LaTeX text; None maps to empty text."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    return latex_escape(str(value))


def _latex_value_text(value):
    """Inline LaTeX text for a value (recursion point for nested dict/list items)."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return latex_scalar_text(value)
    if isinstance(value, dict):
        items = ''.join('\\item{%s}{%s}\n' % (latex_escape(str(k)), _latex_value_text(v)) for k, v in value.items())
        return DESCRIPTION_BEGIN + '\n' + items + DESCRIPTION_END + '\n'
    if isinstance(value, (list, tuple)):
        items = ''.join('\\item %s\n' % _latex_value_text(v) for v in value)
        return ITEMIZE_BEGIN + '\n' + items + ITEMIZE_END + '\n'
    raise ParameterTypeError(f'cannot serialize {type(value).__name__} to LaTeX')


def latex_serialize_param(name, value):
    """Serialize a parameter assignment (without the marker comment) for LaTeX.

    scalar -> ``\\providecommand{\\name}{value}``
    dict   -> ``\\newcommand{\\name}{%\\n\\begin{description}\\n\\item{K}{V}...\\end{description}\\n}``
    list   -> ``\\newcommand{\\name}{%\\n\\begin{itemize}\\n\\item V...\\end{itemize}\\n}``
    """
    macro = latex_macro_name(name)
    if value is None:
        return ''
    if isinstance(value, bool):
        return '\\providecommand{\\%s}{%s}' % (macro, 'true' if value else 'false')
    if isinstance(value, (int, float, str)):
        return '\\providecommand{\\%s}{%s}' % (macro, latex_scalar_text(value))
    if isinstance(value, (dict, list, tuple)):
        body = _latex_value_text(value)
        return '\\newcommand{\\%s}{%%\n%s}' % (macro, body)
    raise ParameterTypeError(f'cannot serialize {type(value).__name__} to LaTeX')


def scan_brace_group(s, i):
    """Scan the brace group starting at ``s[i] == '{'`` (aware of ``\\{``/``\\}`` escapes).

    Returns ``(content, end_index)`` where end_index is past the closing brace, or
    ``(None, i)`` when no complete group starts at ``i``.
    """
    if i >= len(s) or s[i] != '{':
        return None, i
    depth = 0
    j = i
    while j < len(s):
        c = s[j]
        if c == '\\':
            j += 2
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return None, i


def latex_extract_macro_content(text):
    """Extract the content of the last complete top-level brace group of a macro
    assignment statement. Returns ``(content, ok)``."""
    content = None
    depth = 0
    start = -1
    i = 0
    while i < len(text):
        c = text[i]
        if c == '\\':
            i += 2
            continue
        if c == '{':
            if depth == 0:
                start = i
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                content = text[start + 1:i]
            if depth < 0:
                return None, False
        i += 1
    if depth != 0 or content is None:
        return None, False
    return content, True


def _find_env_end(s, env):
    """Find the ``\\end{env}`` matching the ``\\begin{env}`` at position 0 of ``s``.
    Returns ``(end_token_start, end_token_stop)`` or ``(-1, -1)``."""
    depth = 0
    i = 0
    while i < len(s):
        if s[i] == '\\':
            mb = _BEGIN_ENV_RE.match(s, i)
            if mb:
                depth += 1
                i = mb.end()
                continue
            me = _END_ENV_RE.match(s, i)
            if me:
                depth -= 1
                if depth == 0 and me.group(1) == env:
                    return i, me.end()
                if depth < 0:
                    return -1, -1
                i = me.end()
                continue
            i += 2
            continue
        i += 1
    return -1, -1


def _find_env_item_starts(inner):
    """Find the start offsets of top-level ``\\item`` tokens inside an environment body."""
    starts = []
    depth = 0
    i = 0
    n = len(inner)
    while i < n:
        c = inner[i]
        if c == '\\':
            mb = _BEGIN_ENV_RE.match(inner, i)
            if mb:
                depth += 1
                i = mb.end()
                continue
            me = _END_ENV_RE.match(inner, i)
            if me:
                depth -= 1
                i = me.end()
                continue
            if depth == 0:
                mi = _ITEM_RE.match(inner, i)
                if mi:
                    starts.append(i)
                    i = mi.end()
                    continue
            i += 2
            continue
        i += 1
    return starts


def _parse_tex_env_items(inner, kind):
    """Parse the body of a description/itemize environment into a dict/list.
    Returns None when an item is malformed."""
    starts = _find_env_item_starts(inner)
    if not starts:
        return {} if kind == 'description' else []
    if kind == 'description':
        result = {}
    else:
        result = []
    for idx, st in enumerate(starts):
        m = _ITEM_RE.match(inner, st)
        seg_start = m.end()
        seg_end = starts[idx + 1] if idx + 1 < len(starts) else len(inner)
        seg = inner[seg_start:seg_end]
        if kind == 'description':
            k = seg_start
            while k < seg_end and inner[k] in ' \t\r\n':
                k += 1
            key, k2 = scan_brace_group(inner, k)
            if key is None:
                return None
            while k2 < seg_end and inner[k2] in ' \t\r\n':
                k2 += 1
            val, k3 = scan_brace_group(inner, k2)
            if val is None:
                return None
            result[latex_unescape(key)] = _latex_value_from_content(val)
        else:
            stripped = inner[seg_start:seg_end].strip()
            value, _consumed = _latex_parse_construct(stripped)
            if value is _RAW_SENTINEL:
                result.append(_latex_scalar_from_content(stripped))
            else:
                result.append(value)
    return result


def _latex_parse_construct(t):
    """Parse a LaTeX construct (description/itemize) from stripped text ``t``.
    Returns ``(value, consumed_chars)`` or ``(_RAW_SENTINEL, 0)``."""
    if t.startswith(DESCRIPTION_BEGIN):
        end, after = _find_env_end(t, 'description')
        if end < 0:
            return _RAW_SENTINEL, 0
        val = _parse_tex_env_items(t[len(DESCRIPTION_BEGIN):end], 'description')
        if val is None:
            return _RAW_SENTINEL, 0
        return val, after
    if t.startswith(ITEMIZE_BEGIN):
        end, after = _find_env_end(t, 'itemize')
        if end < 0:
            return _RAW_SENTINEL, 0
        val = _parse_tex_env_items(t[len(ITEMIZE_BEGIN):end], 'itemize')
        if val is None:
            return _RAW_SENTINEL, 0
        return val, after
    return _RAW_SENTINEL, 0


def _latex_value_from_content(content):
    """Parse a macro content string into a python value (construct detection first,
    then scalar type sniffing)."""
    t = content.strip()
    if t.startswith('%'):
        t = t[1:].lstrip()
    value, _consumed = _latex_parse_construct(t)
    if value is not _RAW_SENTINEL:
        return value
    return _latex_scalar_from_content(t)


def _latex_scalar_from_content(content):
    """Type-sniff a (still escaped) LaTeX content string into a python value."""
    t = content.strip()
    if t == '':
        return ''
    if t == 'true':
        return True
    if t == 'false':
        return False
    if _INT_RE.match(t):
        return int(t)
    if _FLOAT_RE.match(t):
        return float(t)
    return latex_unescape(t)


def latex_parse_assignment(text):
    """Parse a LaTeX macro assignment text (possibly multi-line).
    Returns ``(value, kind)`` with kind in ``'scalar'|'dict'|'list'|'raw'``."""
    content, ok = latex_extract_macro_content(text or '')
    if not ok:
        return None, 'raw'
    value = _latex_value_from_content(content)
    if isinstance(value, dict):
        return value, 'dict'
    if isinstance(value, list):
        return value, 'list'
    return value, 'scalar'


# --------------------------------------------------------------------------------------
# adapter
# --------------------------------------------------------------------------------------

class TexFormatAdapter(FormatAdapter):
    tformat = 'tex'
    section_marker_re = build_section_marker_re('tex')
    param_marker_re = build_param_marker_re('tex')

    _MACRO_DEF_RE = re.compile(
        r'\\(?:providecommand|newcommand|renewcommand|gdef|edef|xdef|def|let)\b')

    def comment_wrap(self, text):
        return f'% {text}'

    def find_closing_insert_position(self, source):
        lines = source.splitlines(keepends=True)
        last = -1
        for i, ln in enumerate(lines):
            if re.match(r'^[ \t]*\\end\{document\}', ln):
                last = i
        return last if last >= 0 else len(lines)

    def serialize_param(self, name, value):
        return latex_serialize_param(name, value)

    def parse_param(self, raw_lines):
        k = self._skip_leading(raw_lines)
        if k >= len(raw_lines):
            return None, 'scalar', 0
        first = raw_lines[k].lstrip()
        if not self._MACRO_DEF_RE.match(first):
            return None, 'scalar', 0
        consumed = self._consume_assignment(raw_lines[k:])
        text = '\n'.join(raw_lines[k:k + consumed])
        value, kind = latex_parse_assignment(text)
        return value, kind, k + consumed

    def default_body_placeholder(self):
        return 'Document body placeholder'

    def standalone_validate(self, source):
        issues = []
        if r'\begin{document}' not in source:
            issues.append(r'no \begin{document} found; the file is not a standalone LaTeX document')
        if r'\end{document}' not in source:
            issues.append(r'no \end{document} found; the file will not compile standalone as-is')
        return issues

    @staticmethod
    def _skip_leading(raw_lines):
        k = 0
        while k < len(raw_lines):
            t = raw_lines[k].strip()
            if t == '' or t.startswith('%'):
                k += 1
                continue
            break
        return k

    @staticmethod
    def _consume_assignment(lines):
        depth = 0
        started = False
        for li, line in enumerate(lines):
            i = 0
            while i < len(line):
                c = line[i]
                if c == '\\':
                    i += 2
                    continue
                if c == '{':
                    depth += 1
                    started = True
                elif c == '}':
                    depth = max(0, depth - 1)
                    started = True
                i += 1
            if started and depth <= 0:
                return li + 1
        return len(lines)


register_adapter(TexFormatAdapter())

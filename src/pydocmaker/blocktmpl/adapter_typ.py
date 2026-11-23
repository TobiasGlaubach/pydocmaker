"""Typst format adapter: marker syntax, assignment consumption and the Typst
value codecs (``#let`` bindings with the string/num/bool/none/dict/array literal
subset)."""

import re

from .adapter_base import FormatAdapter, register_adapter
from .markers import build_section_marker_re, build_param_marker_re
from .model import ParameterTypeError

# --------------------------------------------------------------------------------------
# value codecs
# --------------------------------------------------------------------------------------

_TYPST_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_-]*$')


def typst_string(text):
    """Escape a python string as a Typst string literal (mirrors ex_typst.to_typst_string)."""
    safe_text = (str(text).replace('\\', '\\\\').replace('"', '\\"')
                 .replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t'))
    return f'"{safe_text}"'


def typst_literal(value):
    """Serialize a python value as a Typst literal (dict -> ``(k: v, ...)``,
    list -> ``(a, b, ...)``, None -> ``none``, bool -> ``true/false``)."""
    if value is None:
        return 'none'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return typst_string(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        if not value:
            return '(:)'
        items = []
        for k, v in value.items():
            key = k if isinstance(k, str) and _TYPST_IDENT_RE.match(k) else typst_string(str(k))
            items.append(f'{key}: {typst_literal(v)}')
        return '(' + ', '.join(items) + ')'
    if isinstance(value, (list, tuple)):
        if not value:
            return '()'
        inner = ', '.join(typst_literal(v) for v in value)
        if len(value) == 1:
            inner += ','
        return '(' + inner + ')'
    raise ParameterTypeError(f'cannot serialize {type(value).__name__} to Typst')


def typst_serialize_param(name, value):
    """Serialize a parameter assignment (without the marker comment) for Typst."""
    if value is None:
        return ''
    return f'#let {name} = {typst_literal(value)}'


class _TypstParser:
    def __init__(self, s):
        self.s = s
        self.i = 0

    def _ws(self):
        while self.i < len(self.s) and self.s[self.i] in ' \t\r\n':
            self.i += 1

    def _peek(self):
        return self.s[self.i] if self.i < len(self.s) else ''

    def parse(self):
        self._ws()
        value = self._value()
        self._ws()
        if self.i != len(self.s):
            raise ValueError(f'unexpected content at position {self.i}')
        return value

    def _value(self):
        self._ws()
        c = self._peek()
        if c == '"':
            return self._string()
        if c == '(':
            return self._container()
        for lit, val in (('true', True), ('false', False), ('none', None)):
            if self.s.startswith(lit, self.i):
                self.i += len(lit)
                return val
        m = re.match(r'[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?', self.s[self.i:])
        if m:
            text = m.group(0)
            self.i += len(text)
            if '.' in text or 'e' in text or 'E' in text:
                return float(text)
            return int(text)
        raise ValueError(f'cannot parse Typst literal at position {self.i}')

    def _string(self):
        self.i += 1
        buf = []
        while self.i < len(self.s):
            c = self.s[self.i]
            if c == '\\' and self.i + 1 < len(self.s):
                nxt = self.s[self.i + 1]
                buf.append({'n': '\n', 't': '\t', 'r': '\r', '"': '"', '\\': '\\'}.get(nxt, '\\' + nxt))
                self.i += 2
                continue
            if c == '"':
                self.i += 1
                return ''.join(buf)
            buf.append(c)
            self.i += 1
        raise ValueError('unterminated string literal')

    def _probe_dict_key(self):
        j = self.i
        s = self.s
        if j < len(s) and s[j] == '"':
            j += 1
            while j < len(s):
                if s[j] == '\\':
                    j += 2
                    continue
                if s[j] == '"':
                    j += 1
                    break
                j += 1
            else:
                return False
        elif j < len(s) and (s[j].isalpha() or s[j] == '_'):
            while j < len(s) and (s[j].isalnum() or s[j] in '_-'):
                j += 1
        else:
            return False
        while j < len(s) and s[j] in ' \t\r\n':
            j += 1
        return j < len(s) and s[j] == ':'

    def _dict_key(self):
        if self._peek() == '"':
            key = self._string()
        else:
            j = self.i
            while j < len(self.s) and (self.s[j].isalnum() or self.s[j] in '_-'):
                j += 1
            key = self.s[self.i:j]
            self.i = j
        self._ws()
        if self._peek() != ':':
            raise ValueError('expected ":" in dictionary literal')
        self.i += 1
        return key

    def _container(self):
        self.i += 1
        self._ws()
        if self._peek() == ')':
            self.i += 1
            return []
        if self._peek() == ':':
            self.i += 1
            self._ws()
            if self._peek() == ')':
                self.i += 1
                return {}
        is_dict = self._probe_dict_key()
        result = {} if is_dict else []
        while True:
            self._ws()
            if self._peek() == ')':
                self.i += 1
                return result
            if is_dict:
                key = self._dict_key()
                self._ws()
                result[key] = self._value()
            else:
                result.append(self._value())
            self._ws()
            if self._peek() == ',':
                self.i += 1
            elif self._peek() == ')':
                self.i += 1
                return result
            else:
                raise ValueError(f'expected "," or ")" at position {self.i}')


def typst_parse_literal(text):
    """Parse a Typst literal subset (string/num/bool/none/dict/array).
    Returns ``(value, ok)``."""
    try:
        return _TypstParser(text).parse(), True
    except Exception:
        return None, False


_TYPST_ASSIGN_RE = re.compile(r'^#let\s+[A-Za-z_][A-Za-z0-9_]*\s*=\s*(.*)$', re.S)


def typst_parse_assignment(text):
    """Parse a ``#let name = <literal>`` assignment text.
    Returns ``(value, kind)``; kind is 'raw' when the literal cannot be parsed."""
    m = _TYPST_ASSIGN_RE.match((text or '').strip())
    if not m:
        return None, 'raw'
    value, ok = typst_parse_literal(m.group(1))
    if not ok:
        return None, 'raw'
    if isinstance(value, dict):
        return value, 'dict'
    if isinstance(value, list):
        return value, 'list'
    return value, 'scalar'


# --------------------------------------------------------------------------------------
# adapter
# --------------------------------------------------------------------------------------

class TypstFormatAdapter(FormatAdapter):
    tformat = 'typ'
    section_marker_re = build_section_marker_re('typ')
    param_marker_re = build_param_marker_re('typ')

    def comment_wrap(self, text):
        return f'// {text}'

    def find_closing_insert_position(self, source):
        lines = source.splitlines(keepends=True)
        return len(lines)

    def serialize_param(self, name, value):
        return typst_serialize_param(name, value)

    def parse_param(self, raw_lines):
        k = self._skip_leading(raw_lines)
        if k >= len(raw_lines):
            return None, 'scalar', 0
        first = raw_lines[k].lstrip()
        if not first.startswith('#let'):
            return None, 'raw', k + 1
        consumed = self._consume_assignment(raw_lines[k:])
        text = '\n'.join(raw_lines[k:k + consumed])
        value, kind = typst_parse_assignment(text)
        return value, kind, k + consumed

    def default_body_placeholder(self):
        return 'Document body placeholder'

    def standalone_validate(self, source):
        return []

    @staticmethod
    def _skip_leading(raw_lines):
        k = 0
        while k < len(raw_lines):
            t = raw_lines[k].strip()
            if t == '' or t.startswith('//'):
                k += 1
                continue
            break
        return k

    @staticmethod
    def _consume_assignment(lines):
        depth = 0
        in_str = False
        started = False
        for li, line in enumerate(lines):
            i = 0
            while i < len(line):
                c = line[i]
                if in_str:
                    if c == '\\':
                        i += 2
                        continue
                    if c == '"':
                        in_str = False
                    i += 1
                    continue
                if c == '"':
                    in_str = True
                    started = True
                elif c == '(':
                    depth += 1
                    started = True
                elif c == ')':
                    depth = max(0, depth - 1)
                    started = True
                elif not c.isspace():
                    started = True
                i += 1
                if started and not in_str and depth <= 0:
                    return li + 1
        return len(lines)


register_adapter(TypstFormatAdapter())

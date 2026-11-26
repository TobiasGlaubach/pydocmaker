"""HTML format adapter: marker syntax, assignment consumption and the HTML
value codecs (``<meta>`` scalar elements and JSON ``<script>`` containers)."""

import json
import re
import html as _html

from .adapter_base import FormatAdapter, register_adapter
from .markers import build_section_marker_re, build_param_marker_re

# --------------------------------------------------------------------------------------
# value codecs
# --------------------------------------------------------------------------------------

def html_attr_escape(text):
    """Escape a value for use inside a double quoted HTML attribute (newlines are
    encoded as character references so the element stays on a single line)."""
    return (str(text).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#x27;')
            .replace('\r\n', '&#13;&#10;').replace('\r', '&#13;').replace('\n', '&#10;'))


def html_scalar_content_text(value):
    """Scalar value as HTML meta content text (None -> '', bool -> true/false,
    numbers via str, strings HTML-escaped)."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    return html_attr_escape(str(value))


def html_serialize_param(name, value):
    """Serialize a parameter assignment (without the marker comment) for HTML.

    scalar -> ``<meta name="pydocmaker:param:N" content="...">``
    dict/list -> ``<script type="application/json" data-pydocmaker-param="N">...</script>``
    """
    if isinstance(value, (dict, list)):
        payload = json.dumps(value, ensure_ascii=False).replace('</', '<\\/')
        return f'<script type="application/json" data-pydocmaker-param="{name}">{payload}</script>'
    return f'<meta name="pydocmaker:param:{name}" content="{html_scalar_content_text(value)}">'


def html_parse_scalar_payload(raw):
    """Parse a scalar payload (meta content or span inner text) into a python value.
    Empty content maps to None; JSON-sniffable content is typed; everything else is
    treated as a (HTML-unescaped) string."""
    raw = raw or ''
    if raw == '':
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass
    if raw == 'null':
        return None
    return _html.unescape(raw)


def html_parse_script_payload(payload):
    """Parse the JSON payload of a script element. Returns ``(value, ok)``."""
    try:
        return json.loads(payload), True
    except Exception:
        return None, False


# --------------------------------------------------------------------------------------
# adapter
# --------------------------------------------------------------------------------------

class HtmlFormatAdapter(FormatAdapter):
    tformat = 'html'
    section_marker_re = build_section_marker_re('html')
    param_marker_re = build_param_marker_re('html')

    def comment_wrap(self, text):
        return f'<!-- {text} -->'

    def find_closing_insert_position(self, source):
        lines = source.splitlines(keepends=True)
        for i, ln in enumerate(lines):
            if re.search(r'</body\s*>', ln, re.I):
                return i
        for i, ln in enumerate(lines):
            if re.search(r'</html\s*>', ln, re.I):
                return i
        return len(lines)

    def find_params_insert_position(self, source, fallback_line):
        lines = source.splitlines(keepends=True)
        for i, ln in enumerate(lines):
            if re.search(r'</head\s*>', ln, re.I):
                return i
        return fallback_line

    def serialize_param(self, name, value):
        return html_serialize_param(name, value)

    def parse_param(self, raw_lines):
        k = self._skip_leading(raw_lines)
        if k >= len(raw_lines):
            return None, 'scalar', 0
        first = raw_lines[k].lstrip()
        low = first.lower()
        if low.startswith('<script'):
            j = k
            while j < len(raw_lines):
                if '</script>' in raw_lines[j].lower():
                    break
                j += 1
            consumed = (j - k) + 1 if j < len(raw_lines) else len(raw_lines) - k
            text = '\n'.join(raw_lines[k:k + consumed])
            m = re.search(r'<script[^>]*>(.*)</script>', text, re.S | re.I)
            if not m or j >= len(raw_lines):
                return None, 'raw', consumed
            value, ok = html_parse_script_payload(m.group(1))
            if not ok:
                return None, 'raw', consumed
            if isinstance(value, dict):
                return value, 'dict', consumed
            if isinstance(value, list):
                return value, 'list', consumed
            return value, 'scalar', consumed
        if low.startswith('<meta'):
            m = re.search(r'content="([^"]*)"', first, re.I)
            if not m:
                return None, 'raw', 1
            return html_parse_scalar_payload(m.group(1)), 'scalar', 1
        m_span = re.match(r'<span\b[^>]*\bdata-pydocmaker-param="([^"]*)"[^>]*>(.*)</span>\s*$', first, re.I | re.S)
        if m_span:
            return html_parse_scalar_payload(m_span.group(2)), 'scalar', 1
        return None, 'raw', 1

    def default_body_placeholder(self):
        return '<p>Document body placeholder</p>'

    def standalone_validate(self, source):
        issues = []
        low = source.lower()
        if '<html' not in low:
            issues.append('no <html> element found; the file is not a standalone HTML document')
        if '</body>' not in low:
            issues.append('no </body> found; browsers tolerate this but the file is an HTML fragment')
        return issues

    @staticmethod
    def _skip_leading(raw_lines):
        k = 0
        while k < len(raw_lines):
            t = raw_lines[k].strip()
            if t == '' or t.startswith('<!--'):
                k += 1
                continue
            break
        return k


register_adapter(HtmlFormatAdapter())

"""Insertion-point detection and scaffolding of missing parameter/body blocks.

Scaffold semantics (plan Section 7):
1. both sections missing -> parameters block then body block immediately before the
   closing statement (params first); Typst: at EOF; HTML: params in ``<head>`` when
   present, body before ``</body>``.
2. only body exists -> parameters block immediately before the body block.
3. only parameters exists -> body block immediately after the parameters end marker.
4. no explicit closing statement -> insert at EOF with a warning (LaTeX: the warning
   explicitly says the file will not compile standalone as-is).
"""

try:
    from pydocmaker import util
except Exception as err:
    from .. import util

from .markers import normalize_tformat, detect_format
from .adapter_base import get_adapter
from .parser import parse
from .model import BodyReservedError, BODY_RESERVED_MSG, UnsupportedFormatError

log = util.log


def detect_line_terminator(source):
    """Detect the dominant line terminator of ``source`` ('\\r\\n' or '\\n')."""
    return '\r\n' if '\r\n' in source else '\n'


def scaffold(source, tformat=None, params=None, body=None, strict=True):
    """Insert missing ``parameters``/``body`` blocks into a document source.

    The file content is only assembled in memory; writing to disk is the caller's
    decision. Re-scaffolding an already scaffolded document is a no-op.

    Args:
        source: document source string.
        tformat: explicit format ('html' | 'tex' | 'typ' or lenient alias); auto-detected when None.
        params: optional dict of initial parameter values for a newly created
            parameters block (ignored when the block already exists).
        body: optional placeholder content for a newly created body block
            (ignored when the block already exists).
        strict: passed through to :func:`parse`.

    Returns:
        str: the scaffolded source.
    """
    params = dict(params or {})
    if 'body' in params:
        raise BodyReservedError(BODY_RESERVED_MSG)

    doc = parse(source, tformat, strict=strict)
    tf = doc.tformat
    adapter = get_adapter(tf)
    term = detect_line_terminator(source)

    need_params = doc.params_section is None
    need_body = doc.body_section is None
    if not need_params and not need_body:
        return source

    lines = source.splitlines(keepends=True)

    if need_params and need_body:
        closing_line = adapter.find_closing_insert_position(source)
        params_line = adapter.find_params_insert_position(source, closing_line)
        body_line = closing_line
        _warn_missing_closing(adapter, tf, source, closing_line)
        params_block = _build_params_block_lines(adapter, params, term)
        body_block = _build_body_block_lines(adapter, body, term)
        if params_line == body_line:
            new_lines = params_block + body_block
            lines[params_line:params_line] = new_lines
        else:
            if params_line > body_line:
                params_line, body_line = body_line, params_line
                params_block, body_block = body_block, params_block
            lines[body_line:body_line] = body_block
            lines[params_line:params_line] = params_block
    elif need_params:
        insert_line = doc.body_section.begin_line
        lines[insert_line:insert_line] = _build_params_block_lines(adapter, params, term)
    else:
        if doc.params_section.end_line >= 0:
            insert_line = doc.params_section.end_line + 1
        else:
            insert_line = len(lines)
        lines[insert_line:insert_line] = _build_body_block_lines(adapter, body, term)

    return ''.join(lines)


def _warn_missing_closing(adapter, tf, source, closing_line):
    if closing_line != len(source.splitlines(keepends=True)):
        return
    if tf == 'tex':
        if r'\begin{document}' in source:
            msg = (r"no \end{document} found in the LaTeX source; parameter/body blocks were "
                   r"inserted at the end of the file and the file will not compile standalone as-is")
        else:
            msg = (r"no \begin{document}/\end{document} found in the LaTeX source; "
                   r"parameter/body blocks were inserted at the end of the file")
        log.warning(msg)
        return
    if tf == 'html':
        low = source.lower()
        if '</body>' not in low and '</html>' not in low:
            msg = 'no </body> or </html> found in the HTML source; blocks were inserted at the end of the file'
            log.warning(msg)


def _assignment_block_lines(adapter, name, value, term):
    out = [adapter.param_marker(name) + term]
    assign = adapter.serialize_param(name, value)
    if assign:
        out.extend(al + term for al in assign.splitlines())
    return out


def _build_params_block_lines(adapter, params, term):
    out = [adapter.section_marker('parameters', 'begin') + term]
    for name, value in params.items():
        if name == 'body':
            raise BodyReservedError(BODY_RESERVED_MSG)
        out.extend(_assignment_block_lines(adapter, name, value, term))
    out.append(adapter.section_marker('parameters', 'end') + term)
    return out


def _build_body_block_lines(adapter, body, term):
    placeholder = adapter.default_body_placeholder() if body is None else str(body)
    out = [adapter.section_marker('body', 'begin') + term]
    out.extend(bl + term for bl in placeholder.splitlines())
    out.append(adapter.section_marker('body', 'end') + term)
    return out

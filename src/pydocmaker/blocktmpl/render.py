"""Render path and block-template object for the block templating engine.

Rendering never modifies the file on disk: it performs span surgery on the source
string, replacing the body block content and (re)writing parameter assignments
while preserving every untouched region byte-for-byte (whitespace, comments, CRLF
line endings and BOM included).
"""

try:
    from pydocmaker import util
except Exception as err:
    from .. import util

from .markers import normalize_tformat, detect_format
from .adapter_base import get_adapter
from .parser import parse
from .inference import scaffold, detect_line_terminator, _build_body_block_lines
from .model import BlockTemplatingError, BodyReservedError, BODY_RESERVED_MSG

log = util.log


def _values_equal(a, b):
    try:
        return bool(a == b)
    except Exception:
        return False


def _is_empty_param_value(value):
    """Empty strings and empty collections both mean "no value" for a parameter."""
    if isinstance(value, str):
        return value == ''
    if isinstance(value, (dict, list, tuple)):
        return not value
    return False


def _assignment_lines(adapter, name, value, term):
    assign = adapter.serialize_param(name, value)
    if not assign:
        return []
    return [al + term for al in assign.splitlines()]


def _body_lines(body, term):
    body_text = '' if body is None else str(body)
    blines = body_text.splitlines()
    if not blines:
        return ['']
    return [bl + term for bl in blines]


def _apply_line_ops(lines, ops):
    """Apply ``(start, stop, new_lines)`` span-surgery ops bottom-up so that earlier
    indices stay valid."""
    for start, stop, new_lines in sorted(ops, key=lambda op: op[0], reverse=True):
        lines[start:stop] = new_lines
    return lines


def _prepare(source, tformat, params, strict):
    """Parse (scaffolding in memory when the source has no blocks yet) and return
    ``(doc, adapter, lines, term)``."""
    doc = parse(source, tformat, strict=strict)
    if not doc.had_markers:
        source = scaffold(source, tformat=doc.tformat,
                          params={k: v for k, v in params.items() if v is not None}, strict=strict)
        doc = parse(source, tformat=doc.tformat, strict=strict)
    adapter = get_adapter(doc.tformat)
    lines = source.splitlines(keepends=True)
    term = detect_line_terminator(source)
    return doc, adapter, lines, term


def _param_ops(doc, adapter, lines, term, params, skip_equal=True):
    """Build span-surgery ops for parameter overrides. Returns ``(ops, appends)``."""
    ops = []
    appends = []
    sec = doc.params_section
    for name, value in params.items():
        if value is None:
            p = sec.params.get(name) if sec else None
            if p is not None and p.assign_lines[0] < p.assign_lines[1]:
                ops.append((p.assign_lines[0], p.assign_lines[1], []))
            continue
        p = sec.params.get(name) if sec else None
        if p is None:
            appends.append((name, value))
            continue
        # skip the rewrite when the value is unchanged, or when an empty collection
        # is passed for a parameter defaulted to an empty value (so e.g. {} for a
        # macro defaulted to "" keeps the empty default instead of serializing an
        # empty description/itemize environment)
        if skip_equal and p.kind != 'raw' and (
                _values_equal(p.value, value)
                or (_is_empty_param_value(p.value) and _is_empty_param_value(value))):
            continue
        start, stop = p.assign_lines
        ops.append((start, stop, _assignment_lines(adapter, name, value, term)))
    return ops, appends


def _append_op(doc, term, appends):
    """Op appending unknown parameters at the end of the parameters block."""
    if not appends:
        return None
    sec = doc.params_section
    lines = doc.source.splitlines(keepends=True)
    if sec is not None and sec.end_line >= 0:
        insert_line = sec.end_line
    else:
        insert_line = len(lines)
    adapter = get_adapter(doc.tformat)
    block = []
    for name, value in appends:
        block.append(adapter.param_marker(name) + term)
        assign = adapter.serialize_param(name, value)
        if assign:
            block.extend(al + term for al in assign.splitlines())
    return (insert_line, insert_line, block)


def render(source, body, params=None, tformat=None, template_engine='auto', strict=True) -> str:
    """Render a block template source: replace the body block content with ``body``
    and apply parameter overrides.

    Args:
        source: document source string (with or without block markers; unmarked
            sources are scaffolded in memory first).
        body: the generated document body to place inside the body block.
        params: parameter overrides; unknown names are appended to the parameters
            block, known names are rewritten unless the parsed value already equals
            the given one. ``None`` values remove existing assignments (undefined).
        tformat: explicit format; auto-detected when None.
        template_engine: ``'auto'`` or ``'blocks'``; the block engine ignores Jinja2
            syntax entirely.
        strict: passed through to :func:`parse`.

    Returns:
        str: the rendered document source.
    """
    if template_engine not in ('auto', 'blocks'):
        raise ValueError(
            f"template_engine must be one of 'auto', 'blocks' for the block engine, got {template_engine!r}")
    params = dict(params or {})
    if 'body' in params:
        raise BodyReservedError(BODY_RESERVED_MSG)

    doc, adapter, lines, term = _prepare(source, tformat, params, strict)
    ops, appends = _param_ops(doc, adapter, lines, term, params, skip_equal=True)
    append_op = _append_op(doc, term, appends)
    if append_op is not None:
        ops.append(append_op)

    if doc.body_section is not None:
        bs = doc.body_section
        start = bs.begin_line + 1
        stop = bs.end_line if bs.end_line >= 0 else len(lines)
        ops.append((start, stop, _body_lines(body, term)))
    else:
        insert_line = adapter.find_closing_insert_position(source)
        ops.append((insert_line, insert_line, _build_body_block_lines(adapter, body, term)))

    return ''.join(_apply_line_ops(list(lines), ops))


def update_params(source, params, tformat=None, strict=True) -> str:
    """Write parameter values back into a block template source (idempotent).

    Unknown parameter names are appended to the parameters block (scaffolding one
    when absent); assignments are rewritten wholesale; ``raw`` assignments are only
    replaced when an explicit value for that name is supplied. A second run with
    the same arguments produces byte-identical output.

    Args:
        source: document source string.
        params: parameter values to write; ``None`` removes an existing assignment.
        tformat: explicit format; auto-detected when None.
        strict: passed through to :func:`parse`.

    Returns:
        str: the updated source.
    """
    params = dict(params or {})
    if 'body' in params:
        raise BodyReservedError(BODY_RESERVED_MSG)

    doc, adapter, lines, term = _prepare(source, tformat, params, strict)
    ops, appends = _param_ops(doc, adapter, lines, term, params, skip_equal=False)
    append_op = _append_op(doc, term, appends)
    if append_op is not None:
        ops.append(append_op)

    return ''.join(_apply_line_ops(list(lines), ops))


def _tformat_from_template_id(template_id):
    if not template_id:
        return None
    parts = str(template_id).split('.')
    if parts and parts[-1] in ('jinja2', 'j2', 'jinja', 'j'):
        parts = parts[:-1]
    if len(parts) < 2:
        return None
    ext = parts[-1].lower()
    return ext if ext in ('html', 'tex', 'typ') else None


class BlockDocTemplate:
    """Duck-typed stand-in for :class:`pydocmaker.templating.DocTemplate` rendering
    comment-delimited block templates.

    Attributes:
        template: the template source string (with block markers).
        params: default parameters (parsed from the parameters block when not given).
        attachments: attachments dict (same convention as DocTemplate).
        tformat: one of ``'html' | 'tex' | 'typ'`` (or '' when undetermined).
        template_id: optional template id (e.g. the file name).
        env: always None (no Jinja2 environment is used).
    """

    def __init__(self, template, params=None, attachments=None, tformat=None, template_id=None):
        if not isinstance(template, str):
            raise TypeError(f'BlockDocTemplate.template must be a source string, got {type(template).__name__}')
        self.template = template
        parsed = None
        try:
            parsed = parse(template, tformat=tformat)
        except BlockTemplatingError as err:
            log.warning(f'failed to parse block template: {err}')
        block_params = {}
        parsed_tf = None
        if parsed is not None:
            parsed_tf = parsed.tformat
            if parsed.params_section is not None:
                block_params = {k: p.value for k, p in parsed.params_section.params.items()}
        self.params = params if params is not None else block_params
        self.attachments = attachments if attachments is not None else {}
        self.template_id = template_id
        self.env = None
        tf = normalize_tformat(tformat)
        if tf is None:
            tf = parsed_tf
        if tf is None:
            tf = _tformat_from_template_id(template_id)
        if tf is None:
            tf = detect_format(template)
        self.tformat = tf or ''

    def __str__(self):
        return f"BlockDocTemplate(id={self.template_id}, tformat={self.tformat}, params.keys()={list(self.params.keys())})"

    def __repr__(self):
        return self.__str__()

    def render(self, **kwargs):
        """Render the block template with given parameters (same contract as
        ``DocTemplate.render``). The reserved ``body`` keyword carries the document
        body and replaces the content of the body block."""
        kw = dict(kwargs)
        if 'body' in self.params:
            raise BodyReservedError(BODY_RESERVED_MSG)
        body = kw.pop('body', None)
        merged = {**self.params, **kw}
        merged = {k: v for k, v in merged.items() if v is not None}
        merged = util.remove_undefined(merged)
        return render(self.template, body if body is not None else '', params=merged, tformat=self.tformat or None)

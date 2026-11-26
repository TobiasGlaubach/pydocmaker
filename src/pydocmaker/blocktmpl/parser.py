"""Generic line scanner for comment-delimited block templates.

Performs a single left-to-right line scan recording char spans and line indices so
that downstream surgery (render/update/scaffold) never re-serializes untouched
regions. Line terminators (LF/CRLF) and a leading BOM are preserved verbatim.
"""

try:
    from pydocmaker import util
except Exception as err:
    from .. import util

from .markers import normalize_tformat, detect_format
from .adapter_base import get_adapter
from .model import Parameter, BlockSection, BlockDocument, MalformedBlockError, UnsupportedFormatError

log = util.log


def _line_offsets(lines):
    offsets = []
    pos = 0
    for ln in lines:
        offsets.append(pos)
        pos += len(ln)
    return offsets


def _line_span(offsets, contents, i):
    return (offsets[i], offsets[i] + len(contents[i]))


def _range_span(offsets, contents, start, stop):
    if start >= stop:
        return None
    return (offsets[start], offsets[stop - 1] + len(contents[stop - 1]))


def parse(source, tformat=None, strict=True) -> BlockDocument:
    """Parse a document into a :class:`~pydocmaker.blocktmpl.model.BlockDocument`.

    Args:
        source: the document source string.
        tformat: explicit format ('html' | 'tex' | 'typ' or a lenient alias). When
            None the format is auto-detected from the content; if that fails an
            :class:`UnsupportedFormatError` is raised.
        strict: when True (default) malformed markers raise :class:`MalformedBlockError`;
            when False problems are recorded in ``BlockDocument.warnings`` instead.

    Returns:
        BlockDocument with the parsed parameters/body sections and char spans.
    """
    tf = normalize_tformat(tformat)
    if tf is None:
        tf = detect_format(source)
        if tf is None:
            raise UnsupportedFormatError(
                'could not detect the document format from the source content; '
                'pass tformat explicitly (one of html, tex, typ)')
    adapter = get_adapter(tf)

    lines = source.splitlines(keepends=True)
    contents = [ln.rstrip('\r\n') for ln in lines]
    offsets = _line_offsets(lines)

    warnings = []

    sec_marks = []
    for i, text in enumerate(contents):
        m = adapter.section_marker_re.match(text)
        if m:
            sec_marks.append((m.group(1), m.group(2), i))

    stack = []
    sections = []
    for kind, tag, idx in sec_marks:
        if tag == 'begin':
            stack.append({'kind': kind, 'begin': idx, 'end': None})
        else:
            if not stack:
                if strict:
                    raise MalformedBlockError(
                        f"[{tf}] stray 'pydocmaker:{kind}:end' marker without a matching begin marker "
                        f"at line {idx + 1}. Remedy: remove the stray end marker or add the "
                        f"corresponding begin marker.")
                warnings.append(f"stray 'pydocmaker:{kind}:end' marker at line {idx + 1} ignored")
                continue
            sec = stack.pop()
            if sec['kind'] != kind:
                if strict:
                    raise MalformedBlockError(
                        f"[{tf}] mismatched section markers: 'pydocmaker:{sec['kind']}:begin' at line "
                        f"{sec['begin'] + 1} is closed by 'pydocmaker:{kind}:end' at line {idx + 1}. "
                        f"Remedy: use matching begin/end pairs.")
                warnings.append(
                    f"mismatched 'pydocmaker:{kind}:end' marker at line {idx + 1} closes the "
                    f"'{sec['kind']}' section opened at line {sec['begin'] + 1}")
            sec['end'] = idx
            sections.append(sec)

    for sec in stack:
        if strict:
            raise MalformedBlockError(
                f"[{tf}] unclosed '{sec['kind']}' section: 'pydocmaker:{sec['kind']}:begin' at line "
                f"{sec['begin'] + 1} has no matching end marker. Remedy: add the end marker or "
                f"close the section at the end of the file.")
        sec['end'] = None
        warnings.append(
            f"unclosed '{sec['kind']}' section beginning at line {sec['begin'] + 1} "
            f"extends to the end of the file")
        sections.append(sec)

    by_kind = {}
    for sec in sorted(sections, key=lambda s: s['begin']):
        by_kind.setdefault(sec['kind'], []).append(sec)

    swallowed = set()
    winners = {}
    for kind, secs in by_kind.items():
        winners[kind] = secs[0]
        for sec in secs[1:]:
            if strict:
                raise MalformedBlockError(
                    f"[{tf}] duplicate '{kind}' sections found (first at line {secs[0]['begin'] + 1}, "
                    f"duplicate at line {sec['begin'] + 1}). Remedy: keep only one '{kind}' block "
                    f"per document.")
            warnings.append(
                f"duplicate '{kind}' sections found; keeping the first (line {secs[0]['begin'] + 1}) "
                f"and treating the duplicate at line {sec['begin'] + 1} as static content")
            b = sec['begin']
            e = sec['end'] if sec['end'] is not None else len(lines) - 1
            for li in range(b, e + 1):
                swallowed.add(li)

    pw = winners.get('parameters')
    bw = winners.get('body')
    if pw is not None and bw is not None:
        p_rng = (pw['begin'], pw['end'] if pw['end'] is not None else len(lines))
        b_rng = (bw['begin'], bw['end'] if bw['end'] is not None else len(lines))
        nested = (p_rng[0] <= b_rng[0] and b_rng[0] <= p_rng[1]) or (b_rng[0] <= p_rng[0] and p_rng[0] <= b_rng[1])
        if nested:
            if strict:
                raise MalformedBlockError(
                    f"[{tf}] nested sections are not supported: 'parameters' block at line "
                    f"{pw['begin'] + 1} overlaps the 'body' block at line {bw['begin'] + 1}. "
                    f"Remedy: place the parameters and body blocks side by side, not inside each other.")
            warnings.append(
                f"nested parameters/body sections (lines {pw['begin'] + 1} and {bw['begin'] + 1}); "
                f"the inner section is treated as static content")

    params_section = None
    body_section = None

    if pw is not None:
        params_section = _parse_parameters_section(
            adapter, tf, lines, contents, offsets, pw, swallowed, warnings, strict)

    if bw is not None:
        body_section = BlockSection(
            kind='body',
            begin_span=_line_span(offsets, contents, bw['begin']),
            end_span=_line_span(offsets, contents, bw['end']) if bw['end'] is not None else None,
            params={},
            static_lines=[],
            begin_line=bw['begin'],
            end_line=bw['end'] if bw['end'] is not None else -1,
        )

    for i, text in enumerate(contents):
        if not adapter.param_marker_re.match(text):
            continue
        if params_section is not None and params_section.begin_line <= i and (
                params_section.end_line < 0 or i <= params_section.end_line):
            continue
        if body_section is not None and body_section.begin_line <= i and (
                body_section.end_line < 0 or i <= body_section.end_line):
            continue
        warnings.append(f"parameter marker outside of a parameters block at line {i + 1} ignored")

    had_markers = params_section is not None or body_section is not None

    return BlockDocument(
        tformat=tf,
        source=source,
        params_section=params_section,
        body_section=body_section,
        had_markers=had_markers,
        warnings=warnings,
    )


def _parse_parameters_section(adapter, tf, lines, contents, offsets, sec, swallowed, warnings, strict):
    b = sec['begin']
    e = sec['end']
    scan_from = b + 1
    scan_to = e if e is not None else len(lines)

    params = {}
    static = []
    i = scan_from
    while i < scan_to:
        if i in swallowed:
            i += 1
            continue
        text = contents[i]
        pm = adapter.param_marker_re.match(text)
        if pm:
            name = pm.group('name')
            if name == 'body':
                warnings.append(
                    f"'body' is a reserved parameter name; the parameter marker at line {i + 1} "
                    f"is preserved as static content")
                static.append(text)
                i += 1
                continue
            j = i + 1
            while j < scan_to:
                if j in swallowed:
                    break
                t = contents[j]
                if adapter.param_marker_re.match(t) or adapter.section_marker_re.match(t):
                    break
                j += 1
            region = contents[i + 1:j]
            value, kind, consumed = adapter.parse_param(region)
            assign_start = i + 1
            assign_end = i + 1 + consumed
            params[name] = Parameter(
                name=name,
                value=value,
                kind=kind,
                raw='\n'.join(contents[assign_start:assign_end]),
                marker_span=_line_span(offsets, contents, i),
                assign_span=_range_span(offsets, contents, assign_start, assign_end),
                assign_lines=(assign_start, assign_end),
            )
            if consumed < len(region):
                for k in range(assign_end, j):
                    if k not in swallowed:
                        static.append(contents[k])
            i = max(j, assign_end)
        else:
            static.append(text)
            i += 1

    return BlockSection(
        kind='parameters',
        begin_span=_line_span(offsets, contents, b),
        end_span=_line_span(offsets, contents, e) if e is not None else None,
        params=params,
        static_lines=static,
        begin_line=b,
        end_line=e if e is not None else -1,
    )

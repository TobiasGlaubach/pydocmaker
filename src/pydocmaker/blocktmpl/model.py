"""Data model and exception hierarchy for the block templating engine."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


class BlockTemplatingError(Exception):
    """Base class for all block templating engine errors."""


class MalformedBlockError(BlockTemplatingError):
    """Raised in strict mode when block markers are malformed (unclosed sections,
    stray end markers, duplicate sections, nested sections)."""


class UnsupportedFormatError(BlockTemplatingError):
    """Raised when the document format cannot be detected and none was given."""


BODY_RESERVED_MSG = 'the "body" keyword is an invalid keyword for templates as it is reserved for the document body.'


class BodyReservedError(BlockTemplatingError):
    """Raised when ``body`` is supplied as a template parameter (reserved name)."""

    def __init__(self, msg: str = BODY_RESERVED_MSG):
        super().__init__(msg)


class ParameterTypeError(BlockTemplatingError):
    """Raised when a parameter value cannot be represented in the target format."""


@dataclass
class Parameter:
    """A single declared template parameter inside a ``parameters`` block.

    Attributes:
        name: parameter name matching ``[A-Za-z_][A-Za-z0-9_]*``.
        value: the parsed python value (str|int|float|bool|dict|list) or None for
            declared-but-unset parameters and for ``raw`` assignments.
        kind: one of ``'scalar' | 'dict' | 'list' | 'raw'``.
        raw: verbatim assignment text (raw fallback / round-trip).
        marker_span: char span ``(start, end)`` of the parameter marker line.
        assign_span: char span ``(start, end)`` of the consumed assignment region
            (excluding line terminators) or None when no assignment was found.
        assign_lines: half-open line index range ``(start, stop)`` of the consumed
            assignment region (used for span surgery).
    """
    name: str
    value: Any = None
    kind: str = 'scalar'
    raw: str = ''
    marker_span: Optional[Tuple[int, int]] = None
    assign_span: Optional[Tuple[int, int]] = None
    assign_lines: Optional[Tuple[int, int]] = None


@dataclass
class BlockSection:
    """A ``parameters`` or ``body`` block within a document.

    Attributes:
        kind: ``'parameters'`` or ``'body'``.
        begin_span: char span ``(start, end)`` of the begin marker line.
        end_span: char span ``(start, end)`` of the end marker line or None when
            the section is unclosed.
        params: insertion-ordered mapping of parameter name to :class:`Parameter`
            (empty for body sections).
        static_lines: line contents (without terminators) inside the section which
            are neither markers nor consumed assignments; preserved verbatim on
            scaffold/update.
        begin_line: 0-based line index of the begin marker line.
        end_line: 0-based line index of the end marker line or -1 when unclosed.
    """
    kind: str
    begin_span: Tuple[int, int] = (0, 0)
    end_span: Optional[Tuple[int, int]] = None
    params: Dict[str, Parameter] = field(default_factory=dict)
    static_lines: list = field(default_factory=list)
    begin_line: int = -1
    end_line: int = -1


@dataclass
class BlockDocument:
    """Parsed representation of a document for the block templating engine."""
    tformat: str
    source: str
    params_section: Optional[BlockSection] = None
    body_section: Optional[BlockSection] = None
    had_markers: bool = False
    warnings: list = field(default_factory=list)

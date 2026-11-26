"""FormatAdapter base class: per-format hooks for comment style, marker regexes,
assignment consumption, value codecs and closing-statement detection."""

try:
    from pydocmaker import util
except Exception as err:
    from .. import util

from .markers import build_section_marker_re, build_param_marker_re, section_marker_line, param_marker_line

log = util.log


class FormatAdapter:
    """Abstract per-format adapter for the block templating engine.

    Subclasses must define :attr:`tformat`, :attr:`section_marker_re`,
    :attr:`param_marker_re` and implement the hooks below. Adapters are stateless
    singletons (see :func:`get_adapter`).
    """

    tformat = None
    section_marker_re = None
    param_marker_re = None

    def comment_wrap(self, text):
        """Wrap ``text`` into a single-line comment of this format."""
        raise NotImplementedError

    def section_marker(self, kind, tag):
        """Full section marker line (e.g. ``% pydocmaker:parameters:begin``)."""
        return section_marker_line(kind, tag, self.tformat)

    def param_marker(self, name):
        """Full parameter marker line (e.g. ``% pydocmaker:param:title``)."""
        return param_marker_line(name, self.tformat)

    def find_closing_insert_position(self, source):
        """Return the 0-based line index before which new blocks are inserted when
        the document has no blocks yet (the "closing statement" position)."""
        raise NotImplementedError

    def find_params_insert_position(self, source, fallback_line):
        """Return the 0-based line index for inserting the parameters block during
        scaffolding. Defaults to ``fallback_line``; formats with a dedicated header
        section (HTML ``<head>``) may override this."""
        return fallback_line

    def serialize_param(self, name, value):
        """Serialize an assignment (without the marker comment). Returns '' for
        value None (declared-unset)."""
        raise NotImplementedError

    def parse_param(self, raw_lines):
        """Parse an assignment region (list of line contents without terminators).

        Returns ``(value, kind, consumed)`` where ``consumed`` is the number of
        lines belonging to the assignment (0 when no assignment is present).
        ``kind`` is one of ``'scalar' | 'dict' | 'list' | 'raw'``.
        """
        raise NotImplementedError

    def default_body_placeholder(self):
        """Standalone-visible placeholder content for scaffolded body blocks."""
        raise NotImplementedError

    def standalone_validate(self, source):
        """Best-effort standalone compilability check. Returns a list of issue strings."""
        return []


_ADAPTERS = {}


def register_adapter(adapter):
    _ADAPTERS[adapter.tformat] = adapter
    return adapter


def get_adapter(tformat):
    """Return the singleton adapter for ``tformat`` ('html' | 'tex' | 'typ')."""
    try:
        return _ADAPTERS[tformat]
    except KeyError as err:
        raise KeyError(f'no block templating adapter registered for tformat={tformat!r}') from err

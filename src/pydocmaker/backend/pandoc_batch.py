"""Shared batching machinery for pandoc based format conversions.

This module provides :class:`PandocBatchMixin`, a mixin for
:class:`pydocmaker.backend.baseformatter.BaseFormatter` subclasses that
convert markdown and/or latex elements via pandoc. Instead of spawning one
pandoc process per element, the mixin defers the conversions: the digest
methods register a placeholder and return it immediately, and all pending
conversions are resolved with at most one ``pandoc_convert_batch`` call per
input format as soon as the outermost digest call finishes.

Subclasses must:

* call :meth:`PandocBatchMixin._pandoc_batch_init` from their ``__init__``
* define ``_pandoc_batch_specs`` mapping the pandoc input format (kind) to a
  ``(output_format, is_code)`` tuple for every kind they register
* implement :meth:`PandocBatchMixin._pandoc_finalize` to turn the converted
  string (or the conversion error) into the final output for one element
"""

import uuid

try:
    from pydocmaker.backend.pandoc_api import pandoc_convert, pandoc_convert_batch
except Exception as err:
    from .pandoc_api import pandoc_convert, pandoc_convert_batch

try:
    from pydocmaker import util
except Exception as err:
    from .. import util

log = util.log


# maximum number of pending blocks per pandoc batch call (None = no limit,
# i.e. one batch call per input format and document)
PANDOC_BATCH_CHUNK_SIZE = None

# prefix of the placeholder tokens returned by the digest methods; the tokens
# are ``PANDOC_PLACEHOLDER_PREFIX + uuid4().hex`` and therefore practically
# collision free
PANDOC_PLACEHOLDER_PREFIX = 'PYDOCMAKERPANDOCPH'


class PandocBatchMixin:
    """Mixin that batches the pandoc conversions of a whole document.

    The pending elements are grouped by input format and converted with at
    most one ``pandoc_convert_batch`` call per group (optionally chunked via
    ``PANDOC_BATCH_CHUNK_SIZE``). On batch failure the group is retried per
    block, and blocks that still fail are handed to
    :meth:`PandocBatchMixin._pandoc_finalize` with ``converted=None``.
    """

    # maps the pandoc input format (kind) to a (output_format, is_code) tuple;
    # subclasses must provide an entry for every kind they register
    _pandoc_batch_specs = {}

    def _pandoc_batch_init(self) -> None:
        """Initialize the batching state; call from the subclass ``__init__``."""
        # pending pandoc conversions as (placeholder, kind, el_dict, children)
        # tuples; kind is the pandoc input format and children the (pre
        # processed) pandoc input string
        self._pending = []
        self._digest_depth = 0

    def digest(self, children, **kwargs) -> str:
        # wrap the base dispatch so that all pandoc placeholder elements
        # registered during (possibly nested) digesting are resolved and
        # substituted as soon as the outermost digest call finishes
        self._digest_depth += 1
        ret = None
        try:
            ret = super().digest(children, **kwargs)
        finally:
            self._digest_depth -= 1
            if self._digest_depth == 0:
                # clear _pending first so state never leaks between calls
                # (also on exception paths of super().digest)
                pending, self._pending = self._pending, []
                if pending:
                    if isinstance(ret, str):
                        try:
                            ret = self._resolve_pending(ret, pending)
                        except Exception as err:
                            log.warning(f'failed to resolve pending pandoc conversions: {err}')

                        # detect placeholders that remain unresolved or were
                        # split by downstream post processing (e.g. the
                        # verbatim chunking of some backends); a split token
                        # leaves its prefix in one chunk and its uuid tail in
                        # another, so checking both covers every split position
                        fragments = [PANDOC_PLACEHOLDER_PREFIX] + [p[-8:] for p, _, _, _ in pending]
                        if any(frag in ret for frag in fragments):
                            log.warning('unresolved or split pandoc placeholders remain in the '
                                        'formatted output; the converted content may be corrupted')
        return ret

    def _pandoc_register(self, kind, el, children=None) -> str:
        """Register one pandoc conversion to be resolved at the next flush.

        Args:
            kind (str): the pandoc input format (e.g. ``'markdown'`` or
                ``'latex'``); must have an entry in ``_pandoc_batch_specs``
            el (dict): the original element dict (kept for the finalize hook
                and error paths)
            children (str, optional): the (pre processed) pandoc input string;
                defaults to ``el.get('children', '')``

        Returns:
            str: the placeholder token to embed in the digest output
        """
        placeholder = f'{PANDOC_PLACEHOLDER_PREFIX}{uuid.uuid4().hex}'
        if children is None:
            children = el.get('children', '')
        self._pending.append((placeholder, kind, el, children))
        return placeholder

    def _resolve_pending(self, s, pending=None) -> str:
        """Convert all pending pandoc placeholder elements and substitute them in ``s``.

        The pending elements are grouped by input format and converted with at
        most one ``pandoc_convert_batch`` call per group (optionally chunked via
        ``PANDOC_BATCH_CHUNK_SIZE``). On batch failure the group is retried per
        block, and blocks that still fail are passed to the
        :meth:`PandocBatchMixin._pandoc_finalize` hook with ``converted=None``.
        """
        if pending is None:
            pending = self._pending

        # group pending placeholder elements by input format; registration order is preserved
        groups = {}
        for placeholder, kind, el, children in pending:
            groups.setdefault(kind, []).append((placeholder, el, children))

        for kind, items in groups.items():
            output_format, is_code = self._pandoc_batch_specs[kind]
            chunk_size = PANDOC_BATCH_CHUNK_SIZE or len(items)
            chunk_size = max(1, chunk_size)

            for i in range(0, len(items), chunk_size):
                chunk = items[i:i + chunk_size]
                children_list = [children for _, _, children in chunk]

                converted = [None] * len(chunk)
                errs = [None] * len(chunk)
                try:
                    converted = pandoc_convert_batch(children_list, kind, output_format, is_code=is_code)
                except Exception as err:
                    log.warning(f'pandoc batch conversion failed ({kind} -> {output_format}): '
                                f'{err}\nfalling back to per-block conversion...')
                    for j, children in enumerate(children_list):
                        try:
                            converted[j] = pandoc_convert(children, kind, output_format, is_code=is_code)
                        except Exception as err2:
                            errs[j] = err2

                for (placeholder, el, children), conv, err in zip(chunk, converted, errs):
                    repl = self._pandoc_finalize(kind, el, converted=conv, err=err)
                    s = s.replace(placeholder, repl)

        return s

    def _pandoc_finalize(self, kind, el, converted=None, err=None) -> str:
        """Turn one converted element (or its conversion error) into the final output.

        Args:
            kind (str): the pandoc input format the element was registered with
            el (dict): the element dict stored at registration time
            converted (str, optional): the pandoc output; ``None`` if the
                conversion failed (pandoc missing or conversion error)
            err (Exception, optional): the per-block conversion error if the
                conversion failed

        Returns:
            str: the final output for the element
        """
        raise NotImplementedError(f'{type(self).__name__} does not implement _pandoc_finalize for kind={kind!r}')

    def format(self, doc) -> str:
        if hasattr(doc, 'dump'):
            doc = doc.dump()
        if not isinstance(doc, list):
            doc = [doc]
        if not doc:
            return ''
        # digest the whole document in a single call so that all pending pandoc
        # conversions are resolved with at most one batch call per input format;
        # digest appends the default linebreak to the joined result while
        # BaseFormatter.format does not, so strip exactly that suffix to keep
        # the output identical to the un-batched per-element formatting
        s = self.digest(doc)
        if s.endswith(self.default_linebreak):
            s = s[:-len(self.default_linebreak)]
        return s

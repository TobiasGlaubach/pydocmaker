import unittest
import os, inspect, sys
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)

from src.pydocmaker.backend import ex_tex

# the PandocBatchMixin class may live in the installed "pydocmaker" package or
# in the local "src.pydocmaker" package depending on the environment; resolve
# the module object that actually owns the mixin's pandoc function globals so
# the patches below hit the functions the formatter really calls
pandoc_batch = sys.modules[ex_tex.PandocBatchMixin.__module__]


class TestLatexElementFormatter(unittest.TestCase):
    """Basic tests for the LatexElementFormatter."""

    def setUp(self) -> None:
        self.formatter = ex_tex.LatexElementFormatter()

    def test_digest_markdown_non_pandoc_fallback(self):
        with patch.object(ex_tex, 'can_run_pandoc', return_value=False):
            result = self.formatter.digest({'typ': 'markdown', 'children': '# Title'})
        self.assertIsInstance(result, str)
        self.assertNotIn('PYDOCMAKER', result)
        self.assertEqual(self.formatter._pending, [])

    def test_digest_latex_passthrough(self):
        result = self.formatter.digest({'typ': 'latex', 'children': '$x^2$'})
        self.assertIsInstance(result, str)
        self.assertNotIn('PYDOCMAKER', result)

    def test_digest_verbatim(self):
        result = self.formatter.digest({'typ': 'verbatim', 'children': 'code snippet'})
        self.assertIn('lstlisting', result)
        self.assertIn('code snippet', result)

    def test_digest_table(self):
        data = {
            'typ': 'table',
            'children': [['a', 'b']],
            'header': ['col1', 'col2'],
            'caption': 'Test Table'
        }
        result = self.formatter.digest(data)
        self.assertIn('tabular', result)
        self.assertIn('Test Table', result)

    def test_format_empty_list(self):
        self.assertEqual(self.formatter.format([]), '')

    def test_format_scalar_inputs_match_base_semantics(self):
        # the mixin format override must preserve the BaseFormatter.format
        # semantics for non list inputs
        self.assertEqual(self.formatter.format(''), '\n\n')
        self.assertEqual(self.formatter.format({}), '\n\n')
        self.assertEqual(self.formatter.format({'typ': 'text', 'children': 'hello'}),
                         self.formatter.digest({'typ': 'text', 'children': 'hello'}))


class _PerBlockReferenceFormatter(ex_tex.LatexElementFormatter):
    """Formatter replicating the previous per-block pandoc conversion behavior."""

    def digest_markdown(self, children='', **kwargs) -> str:
        if ex_tex.can_run_pandoc():
            # the old code called pandoc directly; conversion errors
            # propagated to BaseFormatter.digest which rendered the error
            s = ex_tex.pandoc_convert(ex_tex.replace_bcolors(children), 'markdown', 'latex',
                                      is_binary=False, is_code=True)
        else:
            ex_tex._lazy_import()
            s = str(ex_tex.md.convert(ex_tex.replace_bcolors(children)).lstrip('<root>').rstrip('</root>'))

        return ex_tex.map_colornames(s, kwargs.get('color'))


class TestPandocBatching(unittest.TestCase):
    """Tests for the batched pandoc conversion in LatexElementFormatter."""

    MD_BLOCKS = [
        {'typ': 'markdown', 'children': '# Heading One'},
        {'typ': 'markdown', 'children': 'Some *italic* and **bold** text with unicode: \u00e4\u00f6\u00fc \u20ac \u03b1\u03b2\u03b3'},
        {'typ': 'markdown', 'children': '```python\nprint("hello")\n```'},
        {'typ': 'markdown', 'children': ''},
        {'typ': 'markdown', 'children': '- item a\n- item b\n- item c'},
        {'typ': 'markdown', 'children': '# Colored heading', 'color': 'red'},
        {'typ': 'markdown', 'children': 'Custom end block', 'end': '\n'},
    ]

    NESTED_DOC = [
        {'typ': 'markdown', 'children': '# Nested Test'},
        {'typ': 'table',
         'children': [[{'typ': 'markdown', 'children': '**cell md 1**'}, {'typ': 'latex', 'children': '$c_1$'}],
                      [{'typ': 'latex', 'children': r'\emph{cell tex}'}, {'typ': 'markdown', 'children': 'cell md 2'}]],
         'header': ['A', 'B'], 'caption': 'nested table'},
        {'typ': 'iter', 'children': [
            {'typ': 'markdown', 'children': 'in iter md'},
            {'typ': 'latex', 'children': r'$in\_iter\_tex$'},
            {'typ': 'verbatim', 'children': [
                {'typ': 'markdown', 'children': 'md inside verbatim'},
                {'typ': 'latex', 'children': '$v$'},
            ]},
        ]},
        {'typ': 'text', 'children': 'plain text'},
        {'typ': 'verbatim', 'children': 'just code', 'lang': 'python'},
    ]

    def _assert_same_as_reference(self, doc):
        old = _PerBlockReferenceFormatter()
        new = ex_tex.LatexElementFormatter()
        o = old.digest(list(doc))
        n = new.digest(list(doc))
        self.assertEqual(o, n)
        self.assertNotIn('PYDOCMAKER', n)
        self.assertEqual(new._pending, [])

    def test_digest_markdown_only_matches_reference(self):
        self._assert_same_as_reference(self.MD_BLOCKS)

    def test_digest_nested_matches_reference(self):
        self._assert_same_as_reference(self.NESTED_DOC)

    def test_digest_per_element_calls_match_reference(self):
        # degenerate batching: one digest call per element must give the same output
        doc = self.MD_BLOCKS
        o = ''.join(_PerBlockReferenceFormatter().digest(e) for e in doc)
        n = ''.join(ex_tex.LatexElementFormatter().digest(e) for e in doc)
        self.assertEqual(o, n)
        self.assertNotIn('PYDOCMAKER', n)

    @unittest.skipUnless(ex_tex.can_run_pandoc(), 'pandoc is not installed')
    def test_convert_spawns_at_most_one_pandoc_process(self):
        doc = [{'typ': 'markdown', 'children': f'# Section {i}\n\ntext {i}'} for i in range(20)]

        real_batch = pandoc_batch.pandoc_convert_batch
        real_conv = ex_tex.pandoc_convert
        counts = {'batch': 0, 'single': 0}

        def counting_batch(blocks, *args, **kwargs):
            counts['batch'] += 1
            return real_batch(blocks, *args, **kwargs)

        def counting_single(*args, **kwargs):
            counts['single'] += 1
            return real_conv(*args, **kwargs)

        with patch.object(pandoc_batch, 'pandoc_convert_batch', counting_batch), \
                patch.object(pandoc_batch, 'pandoc_convert', counting_single):
            out, _ = ex_tex.convert(doc)

        self.assertEqual(counts['batch'], 1)
        self.assertEqual(counts['single'], 0)
        self.assertNotIn('PYDOCMAKER', out)

    @unittest.skipUnless(ex_tex.can_run_pandoc(), 'pandoc is not installed')
    def test_chunked_batching_produces_identical_output(self):
        doc = self.MD_BLOCKS
        unchunked = ex_tex.LatexElementFormatter().digest(list(doc))
        with patch.object(pandoc_batch, 'PANDOC_BATCH_CHUNK_SIZE', 2):
            chunked = ex_tex.LatexElementFormatter().digest(list(doc))
        self.assertEqual(unchunked, chunked)

    @unittest.skipUnless(ex_tex.can_run_pandoc(), 'pandoc is not installed')
    def test_batch_failure_falls_back_per_block(self):
        doc = [{'typ': 'markdown', 'children': f'block number {i}'} for i in range(3)]

        real_conv = ex_tex.pandoc_convert

        def failing_batch(blocks, *args, **kwargs):
            raise RuntimeError('mocked batch failure')

        def conv_failing_for_block1(children, *args, **kwargs):
            if 'block number 1' in children:
                raise RuntimeError('mocked per-block failure')
            return real_conv(children, *args, **kwargs)

        with patch.object(pandoc_batch, 'pandoc_convert_batch', failing_batch), \
                patch.object(pandoc_batch, 'pandoc_convert', conv_failing_for_block1):
            formatter = ex_tex.LatexElementFormatter()
            result = formatter.digest(list(doc))

        self.assertNotIn('PYDOCMAKER', result)
        self.assertEqual(formatter._pending, [])
        # the two healthy blocks still get real pandoc output
        self.assertIn(real_conv('block number 0', 'markdown', 'latex', is_binary=False, is_code=True), result)
        self.assertIn(real_conv('block number 2', 'markdown', 'latex', is_binary=False, is_code=True), result)
        # the failing block falls back to the error lstlisting block
        self.assertIn('ERROR WHILE HANDLING ELEMENT', result)
        self.assertIn('lstlisting', result)
        self.assertIn('block number 1', result)

    @unittest.skipUnless(ex_tex.can_run_pandoc(), 'pandoc is not installed')
    def test_batch_failure_renders_error_block_uncolored_conversion_colors_kept(self):
        # a failing block gets the red lstlisting error block while healthy
        # colored blocks keep their color wrapping
        doc = [{'typ': 'markdown', 'children': f'block number {i}', 'color': 'blue'} for i in range(2)]

        real_conv = ex_tex.pandoc_convert

        def failing_batch(blocks, *args, **kwargs):
            raise RuntimeError('mocked batch failure')

        def conv_failing_for_block1(children, *args, **kwargs):
            if 'block number 1' in children:
                raise RuntimeError('mocked per-block failure')
            return real_conv(children, *args, **kwargs)

        with patch.object(pandoc_batch, 'pandoc_convert_batch', failing_batch), \
                patch.object(pandoc_batch, 'pandoc_convert', conv_failing_for_block1):
            formatter = ex_tex.LatexElementFormatter()
            result = formatter.digest(list(doc))

        self.assertNotIn('PYDOCMAKER', result)
        self.assertEqual(formatter._pending, [])
        # the healthy colored block keeps its color wrapping
        self.assertIn('\\color{NavyBlue}', result)
        # the failing block is rendered as an uncolored error block
        self.assertIn('ERROR WHILE HANDLING ELEMENT', result)
        self.assertIn('block number 1', result)

    def test_non_pandoc_fallback_unchanged(self):
        # without pandoc the python markdown fallback path must stay intact
        with patch.object(ex_tex, 'can_run_pandoc', return_value=False):
            formatter = ex_tex.LatexElementFormatter()
            md = formatter.digest({'typ': 'markdown', 'children': '# Title', 'color': 'red'})
            self.assertNotIn('PYDOCMAKER', md)
            self.assertEqual(formatter._pending, [])
            self.assertIn('Title', md)

    def test_pending_never_leaks_between_calls(self):
        formatter = ex_tex.LatexElementFormatter()
        p1 = formatter.digest({'typ': 'markdown', 'children': 'first call'})
        self.assertEqual(formatter._pending, [])
        p2 = formatter.digest({'typ': 'markdown', 'children': 'second call'})
        self.assertEqual(formatter._pending, [])
        self.assertNotEqual(p1, p2)
        self.assertNotIn('PYDOCMAKER', p1 + p2)

    @unittest.skipUnless(ex_tex.can_run_pandoc(), 'pandoc is not installed')
    def test_digest_markdown_registers_placeholder_without_pandoc_call(self):
        # while digesting, markdown elements must not trigger pandoc calls
        real_batch = pandoc_batch.pandoc_convert_batch
        real_conv = ex_tex.pandoc_convert
        calls = []

        with patch.object(pandoc_batch, 'pandoc_convert_batch',
                          lambda blocks, *a, **kw: calls.append('batch') or real_batch(blocks, *a, **kw)), \
                patch.object(pandoc_batch, 'pandoc_convert',
                             lambda *a, **kw: calls.append('single') or real_conv(*a, **kw)):
            formatter = ex_tex.LatexElementFormatter()
            ret = formatter.digest({'typ': 'markdown', 'children': '# lazy'})

        # during digesting nothing was converted; conversion happened at flush
        self.assertEqual(ret, ex_tex.pandoc_convert('# lazy', 'markdown', 'latex', is_binary=False, is_code=True) + '\n\n')
        self.assertEqual(calls, ['batch'])


if __name__ == '__main__':
    unittest.main()

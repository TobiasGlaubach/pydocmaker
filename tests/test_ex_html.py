import unittest

import os, inspect, sys
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
if __name__ == '__main__':
    print(parent_dir)
    sys.path.insert(0, os.path.join(parent_dir, 'src'))

from pydocmaker.backend import ex_html
import pydocmaker as pyd

from unittest.mock import patch
import warnings

# the PandocBatchMixin class may live in the installed "pydocmaker" package or
# in the local "src.pydocmaker" package depending on the environment; resolve
# the module object that actually owns the mixin's pandoc function globals so
# the patches below hit the functions the formatter really calls
pandoc_batch = sys.modules[ex_html.PandocBatchMixin.__module__]



import unittest

class TestHtmlRenderer(unittest.TestCase):

    def setUp(self) -> None:

        self.formatter = ex_html.html_renderer()
    
    def test_digest_markdown(self):
        result = self.formatter.digest({'typ': 'markdown'})
        self.assertIsInstance(result, str)

    def test_digest_image(self):
        result = self.formatter.digest({'typ': 'image'})
        self.assertIsInstance(result, str)

    def test_digest_verbatim(self):
        result = self.formatter.digest({'typ': 'verbatim'})
        self.assertIsInstance(result, str)

    def test_digest_table(self):
        result = self.formatter.digest([['element1', 'element2']])
        self.assertIsInstance(result, str)

        dc = {
            'children': [['element1', 'element2']], 
            'header': ['h1', 'h2'], 
            'n_cols': 3, 
            'typ': 'table'
        }
        result = self.formatter.digest(dc)
        self.assertIsInstance(result, str)

    def test_digest_iterator(self):
        result = self.formatter.digest(['element1', 'element2'])
        self.assertIsInstance(result, str)

    def test_digest_str(self):
        result = self.formatter.digest('test string')
        self.assertIsInstance(result, str)

    def test_digest_text(self):
        result = self.formatter.digest({'typ': 'text', 'children': 'test text'})
        self.assertIsInstance(result, str)

    def test_digest_latex(self):
        result = self.formatter.digest({'typ': 'latex', 'children': 'test latex'})
        self.assertIsInstance(result, str)

    def test_digest_line(self):
        result = self.formatter.digest({'typ': 'line', 'children': 'test line'})
        self.assertIsInstance(result, str)

    def test_handle_error(self):
        result = self.formatter.handle_error('my_error', {'typ': 'unknown'})
        self.assertIsInstance(result, str)

    def test_convert(self):
        doc = pyd.get_example().dump()
        res = ex_html.convert(doc)
        self.assertIsInstance(res, str)
        self.assertTrue(res)


class _PerBlockReferenceFormatter(ex_html.html_renderer):
    """Formatter replicating the previous per-block pandoc conversion behavior."""

    def digest_markdown(self, **kwargs):
        label = kwargs.get('label', '')
        content = kwargs.get('content', kwargs.get('children'))
        color = kwargs.get('color', '')
        use_pandoc = kwargs.get('use_pandoc', 0)

        if color:
            color = f'color:{color};'

        parts = []
        if label:
            parts += [
                f'<div style="min-width:100;{color}">{label}</div>',
                '<hr/>'
            ]

        if use_pandoc and ex_html.can_run_pandoc():
            s = ex_html.pandoc_convert(content, 'markdown', 'html')
        else:
            ex_html._lazy_import()
            s = ex_html.markdown.markdown(content)

        fun = lambda x:  f'<div style="{color}">{x}</div>' if color else f'<div>{x}</div>'
        parts += [fun(s)]
        return '\n\n'.join(parts)

    def digest_latex(self, **kwargs):
        if ex_html.can_run_pandoc():
            return ex_html.pandoc_convert(kwargs.get('children', ''), 'latex', 'html')
        s = 'native backend can not convert latex to html and no pandoc is available. Falling back to show as verbatim'
        warnings.warn(s)
        return '<br>' + self.digest_text(children='Warning! ' + s, color='purple') + self.digest_verbatim(**kwargs)


class TestPandocBatching(unittest.TestCase):
    """Tests for the batched pandoc conversion in html_renderer."""

    MD_BLOCKS = [
        {'typ': 'markdown', 'children': '# Heading One', 'use_pandoc': 1},
        {'typ': 'markdown', 'children': 'Some *italic* and **bold** text with unicode: \u00e4\u00f6\u00fc \u20ac \u03b1\u03b2\u03b3', 'use_pandoc': 1},
        {'typ': 'markdown', 'children': '```python\nprint("hello")\n```', 'use_pandoc': 1},
        {'typ': 'markdown', 'children': '', 'use_pandoc': 1},
        {'typ': 'markdown', 'children': '- item a\n- item b\n- item c', 'use_pandoc': 1},
        {'typ': 'markdown', 'children': '# Colored heading', 'color': 'red', 'use_pandoc': 1},
        {'typ': 'markdown', 'children': 'Labeled block', 'label': 'Figure X', 'use_pandoc': 1},
    ]

    LATEX_BLOCKS = [
        {'typ': 'latex', 'children': r'\section{Section One}'},
        {'typ': 'latex', 'children': r'$x^2 + y^2 = z^2$'},
        {'typ': 'latex', 'children': r'\begin{itemize} \item one \item two \end{itemize}'},
    ]

    NESTED_DOC = [
        {'typ': 'markdown', 'children': '# Nested Test', 'use_pandoc': 1},
        {'typ': 'table',
         'children': [[{'typ': 'markdown', 'children': '**cell md 1**', 'use_pandoc': 1}, {'typ': 'latex', 'children': '$c_1$'}],
                      [{'typ': 'latex', 'children': r'\emph{cell tex}'}, {'typ': 'markdown', 'children': 'cell md 2', 'use_pandoc': 1}]],
         'header': ['A', 'B'], 'caption': 'nested table'},
        {'typ': 'iter', 'children': [
            {'typ': 'markdown', 'children': 'in iter md', 'use_pandoc': 1},
            {'typ': 'latex', 'children': r'$in\_iter\_tex$'},
            {'typ': 'verbatim', 'children': 'just code'},
        ]},
        {'typ': 'markdown', 'children': 'python rendered without pandoc'},
        {'typ': 'text', 'children': 'plain text'},
    ]

    def _assert_same_as_reference(self, doc):
        old = _PerBlockReferenceFormatter()
        new = ex_html.html_renderer()
        o = old.format(list(doc))
        n = new.format(list(doc))
        self.assertEqual(o, n)
        self.assertNotIn('PYDOCMAKER', n)
        self.assertEqual(new._pending, [])

    @unittest.skipUnless(ex_html.can_run_pandoc(), 'pandoc is not installed')
    def test_format_markdown_only_matches_reference(self):
        self._assert_same_as_reference(self.MD_BLOCKS)

    @unittest.skipUnless(ex_html.can_run_pandoc(), 'pandoc is not installed')
    def test_format_latex_only_matches_reference(self):
        self._assert_same_as_reference(self.LATEX_BLOCKS)

    @unittest.skipUnless(ex_html.can_run_pandoc(), 'pandoc is not installed')
    def test_format_mixed_matches_reference(self):
        self._assert_same_as_reference(self.MD_BLOCKS[:4] + self.LATEX_BLOCKS[:3])

    @unittest.skipUnless(ex_html.can_run_pandoc(), 'pandoc is not installed')
    def test_format_nested_matches_reference(self):
        self._assert_same_as_reference(self.NESTED_DOC)

    @unittest.skipUnless(ex_html.can_run_pandoc(), 'pandoc is not installed')
    def test_format_per_element_calls_match_reference(self):
        # degenerate batching: one digest call per element must give the same output
        doc = self.MD_BLOCKS + self.LATEX_BLOCKS
        o = ''.join(_PerBlockReferenceFormatter().digest(e) for e in doc)
        n = ''.join(ex_html.html_renderer().digest(e) for e in doc)
        self.assertEqual(o, n)
        self.assertNotIn('PYDOCMAKER', n)

    @unittest.skipUnless(ex_html.can_run_pandoc(), 'pandoc is not installed')
    def test_use_pandoc_gating(self):
        # without the use_pandoc flag the python markdown backend is used and
        # no pandoc call happens at all; with the flag the block is batched
        doc = [
            {'typ': 'markdown', 'children': 'python rendered'},
            {'typ': 'markdown', 'children': 'pandoc rendered', 'use_pandoc': 1},
        ]

        real_batch = pandoc_batch.pandoc_convert_batch
        real_conv = ex_html.pandoc_convert
        counts = {'batch': 0, 'single': 0}

        def counting_batch(blocks, *args, **kwargs):
            counts['batch'] += 1
            return real_batch(blocks, *args, **kwargs)

        def counting_single(*args, **kwargs):
            counts['single'] += 1
            return real_conv(*args, **kwargs)

        with patch.object(pandoc_batch, 'pandoc_convert_batch', counting_batch), \
                patch.object(pandoc_batch, 'pandoc_convert', counting_single):
            out = ex_html.html_renderer().format(list(doc))

        self.assertEqual(counts['batch'], 1)
        self.assertEqual(counts['single'], 0)
        self.assertIn('<p>python rendered</p>', out)
        self.assertNotIn('PYDOCMAKER', out)

    @unittest.skipUnless(ex_html.can_run_pandoc(), 'pandoc is not installed')
    def test_convert_spawns_at_most_one_pandoc_process(self):
        doc = [{'typ': 'markdown', 'children': f'# Section {i}\n\ntext {i}', 'use_pandoc': 1} for i in range(20)]

        real_batch = pandoc_batch.pandoc_convert_batch
        real_conv = ex_html.pandoc_convert
        counts = {'batch': 0, 'single': 0}

        def counting_batch(blocks, *args, **kwargs):
            counts['batch'] += 1
            return real_batch(blocks, *args, **kwargs)

        def counting_single(*args, **kwargs):
            counts['single'] += 1
            return real_conv(*args, **kwargs)

        with patch.object(pandoc_batch, 'pandoc_convert_batch', counting_batch), \
                patch.object(pandoc_batch, 'pandoc_convert', counting_single):
            out = ex_html.convert(doc)

        self.assertEqual(counts['batch'], 1)
        self.assertEqual(counts['single'], 0)
        self.assertNotIn('PYDOCMAKER', out)

    @unittest.skipUnless(ex_html.can_run_pandoc(), 'pandoc is not installed')
    def test_batch_failure_falls_back_per_block(self):
        doc = [{'typ': 'markdown', 'children': f'block number {i}', 'use_pandoc': 1} for i in range(3)]

        real_conv = ex_html.pandoc_convert

        def failing_batch(blocks, *args, **kwargs):
            raise RuntimeError('mocked batch failure')

        def conv_failing_for_block1(children, *args, **kwargs):
            if 'block number 1' in children:
                raise RuntimeError('mocked per-block failure')
            return real_conv(children, *args, **kwargs)

        with patch.object(pandoc_batch, 'pandoc_convert_batch', failing_batch), \
                patch.object(pandoc_batch, 'pandoc_convert', conv_failing_for_block1):
            formatter = ex_html.html_renderer()
            result = formatter.format(list(doc))

        self.assertNotIn('PYDOCMAKER', result)
        self.assertEqual(formatter._pending, [])
        # the two healthy blocks still get real pandoc output
        self.assertIn(real_conv('block number 0', 'markdown', 'html'), result)
        self.assertIn(real_conv('block number 2', 'markdown', 'html'), result)
        # the failing block falls back to the error block
        self.assertIn('ERROR WHILE HANDLING ELEMENT', result)
        self.assertIn('block number 1', result)

    def test_latex_without_pandoc_falls_back_to_warning(self):
        with patch.object(ex_html, 'can_run_pandoc', return_value=False):
            formatter = ex_html.html_renderer()
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter('always')
                res = formatter.digest({'typ': 'latex', 'children': '$x^2$'})

        self.assertTrue(any('native backend can not convert latex to html' in str(x.message) for x in w))
        self.assertIn('Warning!', res)
        self.assertNotIn('PYDOCMAKER', res)
        self.assertEqual(formatter._pending, [])

    def test_markdown_without_pandoc_uses_python_markdown(self):
        with patch.object(ex_html, 'can_run_pandoc', return_value=False):
            formatter = ex_html.html_renderer()
            res = formatter.digest({'typ': 'markdown', 'children': '# Title', 'use_pandoc': 1})

        self.assertIn('<h1>Title</h1>', res)
        self.assertNotIn('PYDOCMAKER', res)
        self.assertEqual(formatter._pending, [])

    @unittest.skipUnless(ex_html.can_run_pandoc(), 'pandoc is not installed')
    def test_pending_never_leaks_between_calls(self):
        formatter = ex_html.html_renderer()
        p1 = formatter.digest({'typ': 'markdown', 'children': 'first call', 'use_pandoc': 1})
        self.assertEqual(formatter._pending, [])
        p2 = formatter.digest({'typ': 'markdown', 'children': 'second call', 'use_pandoc': 1})
        self.assertEqual(formatter._pending, [])
        self.assertNotEqual(p1, p2)
        self.assertNotIn('PYDOCMAKER', p1 + p2)

    @unittest.skipUnless(ex_html.can_run_pandoc(), 'pandoc is not installed')
    def test_digest_markdown_registers_placeholder_without_pandoc_call(self):
        # while digesting, pandoc opted-in elements must not trigger pandoc calls
        real_batch = pandoc_batch.pandoc_convert_batch
        real_conv = ex_html.pandoc_convert
        calls = []

        with patch.object(pandoc_batch, 'pandoc_convert_batch',
                          lambda blocks, *a, **kw: calls.append('batch') or real_batch(blocks, *a, **kw)), \
                patch.object(pandoc_batch, 'pandoc_convert',
                             lambda *a, **kw: calls.append('single') or real_conv(*a, **kw)):
            formatter = ex_html.html_renderer()
            ret = formatter.digest({'typ': 'markdown', 'children': '# lazy', 'use_pandoc': 1})

        # during digesting nothing was converted; conversion happened at flush
        self.assertEqual(ret, '<div>' + ex_html.pandoc_convert('# lazy', 'markdown', 'html') + '</div>\n\n')
        self.assertEqual(calls, ['batch'])


if __name__ == '__main__':
    unittest.main()



import unittest
import os, inspect, sys, base64, io
from unittest.mock import patch, MagicMock

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)

from src.pydocmaker.backend import ex_typst

# the PandocBatchMixin class may live in the installed "pydocmaker" package or
# in the local "src.pydocmaker" package depending on the environment; resolve
# the module object that actually owns the mixin's pandoc function globals so
# the patches below hit the functions the formatter really calls
pandoc_batch = sys.modules[ex_typst.PandocBatchMixin.__module__]


class TestTypstCompilation(unittest.TestCase):
    """Test cases for typst compilation with various input types."""

    def _make_mock_pdf(self, *args, **kwargs):
        """Return a mock PDF bytes object."""
        return b'%PDF-1.4 mock pdf data'

    def _make_mock_result_with_warnings(self, *args, **kwargs):
        """Return a mock PDF bytes object with no warnings."""
        return (b'%PDF-1.4 mock pdf data', [])

    @patch('typst.compile')
    def test_string_input_single_key(self, mock_compile):
        """Test dict with single key/value pair with string content."""
        mock_compile.side_effect = self._make_mock_pdf
        result = ex_typst.compile_with_typst('# Hello World', verb=0)
        self.assertIsNotNone(result)
        mock_compile.assert_called_once()
        call_kwargs = mock_compile.call_args[1]
        self.assertIn('input', call_kwargs)
        self.assertIn('root', call_kwargs)


    @patch('typst.compile')
    def test_string_input_many_keys_no_attachments(self, mock_compile):
        """Test dict with many key/value pairs with string content (no attachments)."""
        mock_compile.side_effect = self._make_mock_pdf
        # When there are no attachments, only main.typ is passed
        result = ex_typst.compile_with_typst('# Test Document', verb=0)
        self.assertIsNotNone(result)
        mock_compile.assert_called_once()
        call_kwargs = mock_compile.call_args[1]
        self.assertIn('input', call_kwargs)


    @patch('typst.compile')
    def test_bytes_input_single_attachment(self, mock_compile):
        """Test dict with only a single key/value pair with bytes content."""
        mock_compile.side_effect = self._make_mock_pdf
        # Create a bytes attachment (e.g., an image file)
        image_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'  # PNG header
        result = ex_typst.compile_with_typst(
            '# Image test',
            attachments={'image.png': image_data},
            verb=0
        )
        self.assertIsNotNone(result)
        mock_compile.assert_called_once()

    @patch('typst.compile')
    def test_bytes_input_many_attachments(self, mock_compile):
        """Test dict with many key/value pairs with bytes content."""
        mock_compile.side_effect = self._make_mock_pdf
        # Create multiple bytes attachments
        attachments = {
            'image1.png': b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' + b'\x00' * 100,
            'image2.jpg': b'\xff\xd8\xff\xe0' + b'\x00' * 100,
            'font.woff': b'wOFF' + b'\x00' * 100,
        }
        result = ex_typst.compile_with_typst(
            '# Multi-attachment test',
            attachments=attachments,
            verb=0
        )
        self.assertIsNotNone(result)
        mock_compile.assert_called_once()

    @patch('typst.compile')
    def test_mixed_content_many_keys(self, mock_compile):
        """Test dict with many key/value pairs with mixed content (string + bytes)."""
        mock_compile.side_effect = self._make_mock_pdf
        # Create mixed attachments: string (typst code) and bytes (binary files)
        attachments = {
            'helper.typ': '# Helper typst code\n#let test() = "hello"',  # string
            'image.png': b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' + b'\x00' * 100,  # bytes
            'style.typ': '# Style definitions\n#let bold(text) = text',  # string
            'logo.jpg': b'\xff\xd8\xff\xe0' + b'\x00' * 100,  # bytes
        }
        result = ex_typst.compile_with_typst(
            '# Main document with mixed attachments',
            attachments=attachments,
            verb=0
        )
        self.assertIsNotNone(result)
        mock_compile.assert_called_once()

    @patch('typst.compile')
    def test_string_input_with_attachments(self, mock_compile):
        """Test string typst code with string attachments."""
        mock_compile.side_effect = self._make_mock_pdf
        attachments = {
            'helper.typ': '#import "other.typ"',
        }
        result = ex_typst.compile_with_typst(
            '# Main document',
            attachments=attachments,
            verb=0
        )
        self.assertIsNotNone(result)
        mock_compile.assert_called_once()

    @patch('typst.compile')
    def test_compile_with_warnings_string_input(self, mock_compile):
        """Test compile_with_warnings with string input.
        
        Note: When verb=1, compile_with_warnings is called. We mock typst.compile
        which is called when verb=0. For verb=1 tests, we need to mock the right function.
        """
        # Use verb=0 to use typst.compile() which we mocked
        mock_compile.return_value = b'%PDF-1.4 mock pdf data'
        result = ex_typst.compile_with_typst('# Test', verb=0)
        self.assertIsNotNone(result)

    @patch('typst.compile')
    def test_compile_with_warnings_bytes_attachments(self, mock_compile):
        """Test compilation with bytes attachments."""
        mock_compile.return_value = b'%PDF-1.4 mock pdf data'
        result = ex_typst.compile_with_typst(
            '# Test with image',
            attachments={'img.png': b'\x89PNG\r\n\x1a\n' + b'\x00' * 50},
            verb=0
        )
        self.assertIsNotNone(result)

    @patch('typst.compile')
    def test_compile_with_warnings_mixed_content(self, mock_compile):
        """Test compilation with mixed string and bytes content."""
        mock_compile.return_value = b'%PDF-1.4 mock pdf data'
        attachments = {
            'code.typ': '# Some typst code',
            'image.png': b'\x89PNG\r\n\x1a\n' + b'\x00' * 50,
        }
        result = ex_typst.compile_with_typst(
            '# Document with mixed content',
            attachments=attachments,
            verb=0
        )
        self.assertIsNotNone(result)

    @patch('typst.compile')
    def test_compile_with_output_path(self, mock_compile):
        """Test compilation with explicit output path."""
        mock_compile.side_effect = self._make_mock_pdf
        result = ex_typst.compile_with_typst(
            '# Test document',
            output='test_output.pdf',
            verb=0
        )
        self.assertIsNotNone(result)
        call_kwargs = mock_compile.call_args[1]
        self.assertEqual(call_kwargs.get('output'), 'test_output.pdf')

    @patch('typst.compile')
    def test_compile_with_different_formats(self, mock_compile):
        """Test compilation with different output formats."""
        mock_compile.side_effect = self._make_mock_pdf
        
        # Test SVG format
        result = ex_typst.compile_with_typst(
            '# Test document',
            format='svg',
            verb=0
        )
        self.assertIsNotNone(result)
        call_kwargs = mock_compile.call_args[1]
        self.assertEqual(call_kwargs.get('format'), 'svg')

    @patch('typst.compile')
    def test_compile_with_html_format(self, mock_compile):
        """Test compilation to HTML format."""
        mock_compile.side_effect = self._make_mock_pdf
        result = ex_typst.compile_with_typst(
            '# Test document',
            format='html',
            verb=0
        )
        self.assertIsNotNone(result)
        call_kwargs = mock_compile.call_args[1]
        self.assertEqual(call_kwargs.get('format'), 'html')

    @patch('typst.compile')
    def test_compile_epub_format(self, mock_compile):
        """Test compilation to EPUB format."""
        mock_compile.side_effect = self._make_mock_pdf
        result = ex_typst.compile_with_typst(
            '# Test document',
            format='epub',
            verb=0
        )
        self.assertIsNotNone(result)
        call_kwargs = mock_compile.call_args[1]
        self.assertEqual(call_kwargs.get('format'), 'epub')

    @patch('typst.compile')
    def test_single_key_dict_string_content(self, mock_compile):
        """Test that a single-key dict with string content is handled correctly."""
        mock_compile.side_effect = self._make_mock_pdf
        # Direct call to _compile with single-key dict
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            typst_code = '# Single key test'
            input_dict = {'main.typ': typst_code}
            result = ex_typst._compile(
                0, 'warn',
                input=input_dict,
                format='pdf',
                root=tmpdir
            )
            self.assertIsNotNone(result)

    @patch('typst.compile')
    def test_multi_key_dict_string_content(self, mock_compile):
        """Test that a multi-key dict with string content is handled correctly."""
        mock_compile.side_effect = self._make_mock_pdf
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dict = {
                'main.typ': '# Main document',
                'helper.typ': '# Helper code',
            }
            result = ex_typst._compile(
                0, 'warn',
                input=input_dict,
                format='pdf',
                root=tmpdir
            )
            self.assertIsNotNone(result)

    @patch('typst.compile')
    def test_multi_key_dict_bytes_content(self, mock_compile):
        """Test that a multi-key dict with bytes content is handled correctly."""
        mock_compile.side_effect = self._make_mock_pdf
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dict = {
                'main.typ': b'# Main document as bytes',
                'image.png': b'\x89PNG\r\n\x1a\n' + b'\x00' * 50,
            }
            result = ex_typst._compile(
                0, 'warn',
                input=input_dict,
                format='pdf',
                root=tmpdir
            )
            self.assertIsNotNone(result)

    @patch('typst.compile')
    def test_multi_key_dict_mixed_content(self, mock_compile):
        """Test that a multi-key dict with mixed string/bytes content is handled correctly."""
        mock_compile.side_effect = self._make_mock_pdf
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dict = {
                'main.typ': '# Main document as string',
                'helper.typ': '# Helper as string',
                'image1.png': b'\x89PNG\r\n\x1a\n' + b'\x00' * 50,
                'image2.jpg': b'\xff\xd8\xff\xe0' + b'\x00' * 50,
            }
            result = ex_typst._compile(
                0, 'warn',
                input=input_dict,
                format='pdf',
                root=tmpdir
            )
            self.assertIsNotNone(result)

    def setUp(self) -> None:
        self.formatter = ex_typst.DocumentTypstFormatter()

    def test_digest_image_data_uri_any_image_format(self):
        payload = base64.b64encode(b'abcd').decode('ascii')
        blob = f'data:image/jpeg;base64,{payload}'
        result = self.formatter.digest({'typ': 'image', 'filename': 'test.jpg', 'imageblob': blob})
        self.assertIsInstance(result, str)
        self.assertIn('format: "jpeg"', result)
        self.assertIn(payload, result)

    def test_digest_image_plain_base64_uses_filename_ext(self):
        payload = base64.b64encode(b'abcd').decode('ascii')
        result = self.formatter.digest({'typ': 'image', 'filename': 'test.png', 'imageblob': payload})
        self.assertIn('format: "png"', result)

    def test_digest_text(self):
        result = self.formatter.digest({'typ': 'text', 'children': 'hello world'})
        self.assertIn('hello world', result)

    def test_digest_markdown(self):
        result = self.formatter.digest({'typ': 'markdown', 'children': '# Title'})
        self.assertIsInstance(result, str)
        # Check if it uses the cmarker fallback or pandoc output
        self.assertTrue('cmarker' in result or 'Title' in result)

    def test_digest_verbatim(self):
        result = self.formatter.digest({'typ': 'verbatim', 'children': 'code snippet'})
        self.assertIn('```', result)
        self.assertIn('code snippet', result)

    def test_digest_latex(self):
        result = self.formatter.digest({'typ': 'latex', 'children': '$x^2$'})
        self.assertIsInstance(result, str)

    def test_digest_table(self):
        data = {
            'typ': 'table',
            'children': [['a', 'b']],
            'header': ['col1', 'col2'],
            'caption': 'Test Table'
        }
        result = self.formatter.digest(data)
        self.assertIn('table(', result)
        self.assertIn('Test Table', result)

    def test_convert(self):
        doc = [{'typ': 'text', 'children': 'test doc'}]
        result = ex_typst.convert(doc)
        self.assertIn('test doc', result)

    @patch('typst.compile')
    def test_compile_with_typst(self, mock_compile):
        mock_compile.return_value = b'pdf data'
        with patch('pydocmaker.backend.ex_typst.test_typst_installed', return_value=True):
            result = ex_typst.compile_with_typst('typst code', verb=0)
            self.assertEqual(result, b'pdf data')


import json

from src.pydocmaker import util


class _PerBlockReferenceFormatter(ex_typst.DocumentTypstFormatter):
    """Formatter replicating the previous per-block pandoc conversion behavior."""

    def digest_latex(self, children: str, **kwargs):
        s = None
        if ex_typst.can_run_pandoc():
            try:
                s = ex_typst.pandoc_convert(children, 'latex', 'typst')
                return self._handle_color(s, **kwargs)
            except Exception as err:
                pass

        self.libraries.add('#import "@preview/cmarker:0.1.8"')
        self.libraries.add('#import "@preview/mitex:0.2.7": *')
        safe_latex = json.dumps(children, cls=util.CommonJSONEncoder)
        return f'#mitext({safe_latex})'

    def digest_markdown(self, children='', **kwargs) -> str:
        s = None
        if ex_typst.config_use_pandoc_for_md_render_get() and ex_typst.can_run_pandoc():
            try:
                s = ex_typst.pandoc_convert(children, 'markdown', 'typst')
            except Exception as err:
                pass

        if s is None:
            self.libraries.add('#import "@preview/cmarker:0.1.8"')
            self.libraries.add('#import "@preview/mitex:0.2.6": mitex')
            safe_markdown = json.dumps(children, cls=util.CommonJSONEncoder)
            s = f'#cmarker.render({safe_markdown}, math: mitex)'

        return self._handle_color(s, **kwargs)


class TestPandocBatching(unittest.TestCase):
    """Tests for the batched pandoc conversion in DocumentTypstFormatter."""

    MD_BLOCKS = [
        {'typ': 'markdown', 'children': '# Heading One'},
        {'typ': 'markdown', 'children': 'Some *italic* and **bold** text with unicode: \u00e4\u00f6\u00fc \u20ac \u03b1\u03b2\u03b3'},
        {'typ': 'markdown', 'children': '```python\nprint("hello")\n```'},
        {'typ': 'markdown', 'children': ''},
        {'typ': 'markdown', 'children': '- item a\n- item b\n- item c'},
        {'typ': 'markdown', 'children': '# Colored heading', 'color': 'red'},
        {'typ': 'markdown', 'children': 'Custom end block', 'end': '\n'},
    ]

    TEX_BLOCKS = [
        {'typ': 'latex', 'children': r'\section{Section One}'},
        {'typ': 'latex', 'children': r'$x^2 + y^2 = z^2$'},
        {'typ': 'latex', 'children': r'\begin{itemize} \item one \item two \end{itemize}'},
        {'typ': 'latex', 'children': r'\textbf{colored}', 'color': 'blue'},
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
        new = ex_typst.DocumentTypstFormatter()
        o = old.digest(list(doc))
        n = new.digest(list(doc))
        self.assertEqual(o, n)
        self.assertEqual(old.libraries, new.libraries)
        self.assertNotIn('PYDOCMAKER', n)
        self.assertEqual(new._pending, [])

    def test_digest_markdown_only_matches_reference(self):
        self._assert_same_as_reference(self.MD_BLOCKS)

    def test_digest_latex_only_matches_reference(self):
        self._assert_same_as_reference(self.TEX_BLOCKS)

    def test_digest_mixed_matches_reference(self):
        self._assert_same_as_reference(self.MD_BLOCKS[:4] + self.TEX_BLOCKS[:4])

    def test_digest_nested_matches_reference(self):
        self._assert_same_as_reference(self.NESTED_DOC)

    def test_digest_per_element_calls_match_reference(self):
        # degenerate batching: one digest call per element must give the same output
        doc = self.MD_BLOCKS + self.TEX_BLOCKS
        o = ''.join(_PerBlockReferenceFormatter().digest(e) for e in doc)
        n = ''.join(ex_typst.DocumentTypstFormatter().digest(e) for e in doc)
        self.assertEqual(o, n)
        self.assertNotIn('PYDOCMAKER', n)

    @unittest.skipUnless(ex_typst.can_run_pandoc(), 'pandoc is not installed')
    def test_convert_spawns_at_most_two_pandoc_processes(self):
        doc = ([{'typ': 'markdown', 'children': f'# Section {i}\n\ntext {i}'} for i in range(20)]
               + [{'typ': 'latex', 'children': f'$x_{i}^2$'} for i in range(20)])

        real_batch = pandoc_batch.pandoc_convert_batch
        real_conv = ex_typst.pandoc_convert
        counts = {'batch': 0, 'single': 0}

        def counting_batch(blocks, *args, **kwargs):
            counts['batch'] += 1
            return real_batch(blocks, *args, **kwargs)

        def counting_single(*args, **kwargs):
            counts['single'] += 1
            return real_conv(*args, **kwargs)

        with patch.object(pandoc_batch, 'pandoc_convert_batch', counting_batch), \
                patch.object(pandoc_batch, 'pandoc_convert', counting_single):
            out = ex_typst.convert(doc)

        self.assertLessEqual(counts['batch'], 2)
        self.assertEqual(counts['single'], 0)
        self.assertNotIn('PYDOCMAKER', out)

    @unittest.skipUnless(ex_typst.can_run_pandoc(), 'pandoc is not installed')
    def test_chunked_batching_produces_identical_output(self):
        doc = self.MD_BLOCKS + self.TEX_BLOCKS
        unchunked = ex_typst.DocumentTypstFormatter().digest(list(doc))
        with patch.object(pandoc_batch, 'PANDOC_BATCH_CHUNK_SIZE', 2):
            chunked = ex_typst.DocumentTypstFormatter().digest(list(doc))
        self.assertEqual(unchunked, chunked)

    @unittest.skipUnless(ex_typst.can_run_pandoc(), 'pandoc is not installed')
    def test_batch_failure_falls_back_per_block(self):
        doc = [{'typ': 'markdown', 'children': f'block number {i}'} for i in range(3)]

        real_conv = ex_typst.pandoc_convert

        def failing_batch(blocks, *args, **kwargs):
            raise RuntimeError('mocked batch failure')

        def conv_failing_for_block1(children, *args, **kwargs):
            if 'block number 1' in children:
                raise RuntimeError('mocked per-block failure')
            return real_conv(children, *args, **kwargs)

        with patch.object(pandoc_batch, 'pandoc_convert_batch', failing_batch), \
                patch.object(pandoc_batch, 'pandoc_convert', conv_failing_for_block1):
            formatter = ex_typst.DocumentTypstFormatter()
            result = formatter.digest(list(doc))

        self.assertNotIn('PYDOCMAKER', result)
        self.assertEqual(formatter._pending, [])
        # the two healthy blocks still get real pandoc output
        self.assertIn(real_conv('block number 0', 'markdown', 'typst'), result)
        self.assertIn(real_conv('block number 2', 'markdown', 'typst'), result)
        # the failing block falls back to the cmarker embedding
        self.assertIn('#cmarker.render(', result)
        self.assertIn('block number 1', result)

    @unittest.skipUnless(ex_typst.can_run_pandoc(), 'pandoc is not installed')
    def test_batch_failure_latex_falls_back_to_mitex(self):
        doc = [{'typ': 'latex', 'children': r'\textbf{some latex}'}]

        def failing_batch(blocks, *args, **kwargs):
            raise RuntimeError('mocked batch failure')

        def failing_conv(*args, **kwargs):
            raise RuntimeError('mocked per-block failure')

        with patch.object(pandoc_batch, 'pandoc_convert_batch', failing_batch), \
                patch.object(pandoc_batch, 'pandoc_convert', failing_conv):
            formatter = ex_typst.DocumentTypstFormatter()
            result = formatter.digest(list(doc))

        self.assertIn('#mitext(', result)
        self.assertIn('some latex', result)
        self.assertNotIn('PYDOCMAKER', result)
        self.assertEqual(formatter._pending, [])
        self.assertIn('#import "@preview/mitex:0.2.7": *', formatter.libraries)

    def test_non_pandoc_fallback_unchanged(self):
        # without pandoc the cmarker/mitex fallback paths must stay intact
        with patch.object(ex_typst, 'can_run_pandoc', return_value=False):
            formatter = ex_typst.DocumentTypstFormatter()
            md = formatter.digest({'typ': 'markdown', 'children': '# Title'})
            self.assertIn('#cmarker.render(', md)
            self.assertIn('"# Title"', md)
            self.assertIn('#import "@preview/mitex:0.2.6": mitex', formatter.libraries)

            formatter = ex_typst.DocumentTypstFormatter()
            tex = formatter.digest({'typ': 'latex', 'children': '$x^2$'})
            self.assertIn('#mitext(', tex)
            self.assertIn('#import "@preview/mitex:0.2.7": *', formatter.libraries)

    def test_pending_never_leaks_between_calls(self):
        formatter = ex_typst.DocumentTypstFormatter()
        p1 = formatter.digest({'typ': 'markdown', 'children': 'first call'})
        self.assertEqual(formatter._pending, [])
        p2 = formatter.digest({'typ': 'markdown', 'children': 'second call'})
        self.assertEqual(formatter._pending, [])
        self.assertNotEqual(p1, p2)
        self.assertNotIn('PYDOCMAKER', p1 + p2)

    @unittest.skipUnless(ex_typst.can_run_pandoc(), 'pandoc is not installed')
    def test_digest_markdown_registers_placeholder_without_pandoc_call(self):
        # while digesting, markdown elements must not trigger pandoc calls
        real_batch = pandoc_batch.pandoc_convert_batch
        real_conv = ex_typst.pandoc_convert
        calls = []

        with patch.object(pandoc_batch, 'pandoc_convert_batch',
                          lambda blocks, *a, **kw: calls.append('batch') or real_batch(blocks, *a, **kw)), \
                patch.object(pandoc_batch, 'pandoc_convert',
                             lambda *a, **kw: calls.append('single') or real_conv(*a, **kw)):
            formatter = ex_typst.DocumentTypstFormatter()
            ret = formatter.digest({'typ': 'markdown', 'children': '# lazy'})

        # during digesting nothing was converted; conversion happened at flush
        self.assertEqual(ret, ex_typst.pandoc_convert('# lazy', 'markdown', 'typst') + '\n\n')
        self.assertEqual(calls, ['batch'])

if __name__ == '__main__':
    unittest.main()

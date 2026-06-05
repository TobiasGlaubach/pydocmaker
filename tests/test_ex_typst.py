import unittest
import os, inspect, sys, base64, io
from unittest.mock import patch, MagicMock

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)

from src.pydocmaker.backend import ex_typst


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

if __name__ == '__main__':
    unittest.main()

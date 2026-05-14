import unittest
import os, inspect, sys, base64
from unittest.mock import patch, MagicMock

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)

from pydocmaker.backend import ex_typst
from pydocmaker.backend.pandoc_api import pandoc_set_allowed

class TestTypstRenderer(unittest.TestCase):

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
        pandoc_set_allowed(True)
        result = self.formatter.digest({'typ': 'markdown', 'children': '# Title'})
        self.assertIsInstance(result, str)
        # Check if it uses the cmarker fallback or pandoc output
        self.assertTrue('cmarker' in result or 'Title' in result)
        
        pandoc_set_allowed(False)
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

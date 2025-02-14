import unittest

import os, inspect, sys
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
if __name__ == '__main__':
    print(parent_dir)
    sys.path.insert(0, os.path.join(parent_dir, 'src'))

from pydocmaker.backend import ex_html
import pydocmaker as pyd



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

if __name__ == '__main__':
    unittest.main()



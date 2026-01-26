import unittest

import os, inspect, sys
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
if __name__ == '__main__':
    print(parent_dir)
    sys.path.insert(0, os.path.join(parent_dir, 'src'))

from pydocmaker.backend import ex_html, ex_docx, ex_ipynb, ex_markdown, ex_redmine, ex_tex

import pydocmaker as pyd



import unittest

class TestConvertAll(unittest.TestCase):

    def test_convert_html(self):
        doc = pyd.get_example().dump()
        res = ex_html.convert(doc)
        self.assertIsInstance(res, str)
        self.assertTrue(res)

    def test_convert_markdown(self):
        doc = pyd.get_example().dump()
        res = ex_markdown.convert(doc)
        self.assertIsInstance(res, str)
        self.assertTrue(res)
        
    def test_convert_ipynb(self):
        doc = pyd.get_example().dump()
        res = ex_ipynb.convert(doc)
        self.assertIsInstance(res, str)
        self.assertTrue(res)

    def test_convert_tex(self):
        doc = pyd.get_example().dump()
        res = ex_tex.convert(doc, with_attachments=False)
        self.assertIsInstance(res, str)
        self.assertTrue(res)
        
        res, dc = ex_tex.convert(doc, with_attachments=True)
        self.assertIsInstance(res, str)
        self.assertIsInstance(dc, dict)
        self.assertTrue(res)
        self.assertTrue(dc)

    def test_convert_redmine(self):
        doc = pyd.get_example().dump()
        res = ex_redmine.convert(doc, with_attachments=False)
        self.assertIsInstance(res, str)
        self.assertTrue(res)
        
        res, dc = ex_redmine.convert(doc, with_attachments=True)
        self.assertIsInstance(res, str)
        self.assertIsInstance(dc, dict)
        self.assertTrue(res)
        self.assertTrue(dc)

    def test_convert_docx(self):
        doc = pyd.get_example().dump()
        res = ex_docx.convert(doc)
        self.assertIsInstance(res, bytes)
        self.assertTrue(res)

        
if __name__ == '__main__':
    unittest.main()



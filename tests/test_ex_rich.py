import io
import unittest
import sys
import os

# Add the src directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, os.path.join(parent_dir, 'src'))

from pydocmaker.backend import ex_rich
import pydocmaker as pyd


class TestRichRenderer(unittest.TestCase):

    def setUp(self) -> None:
        pass

    def test_digest_markdown(self):
        result = ex_rich.rich_renderer().digest({'typ': 'markdown'})
        self.assertTrue(hasattr(result, '__rich_console__'))


    def test_digest_image(self):
        result = ex_rich.rich_renderer().digest({'typ': 'image'})
        self.assertTrue(hasattr(result, '__rich_console__'))

    def test_digest_verbatim(self):
        result = ex_rich.rich_renderer().digest({'typ': 'verbatim'})
        self.assertTrue(hasattr(result, '__rich_console__'))

    def test_digest_table(self):
        result = ex_rich.rich_renderer().digest([['element1', 'element2']])
        self.assertTrue(hasattr(result, '__rich_console__'))

        dc = {
            'children': [['element1', 'element2']], 
            'header': ['h1', 'h2'], 
            'n_cols': 3, 
            'typ': 'table'
        }
        result = ex_rich.rich_renderer().digest(dc)
        self.assertTrue(hasattr(result, '__rich_console__'))

    def test_digest_iterator(self):
        result = ex_rich.rich_renderer().digest(['element1', 'element2'])
        self.assertTrue(hasattr(result, '__rich_console__'))

    def test_digest_str(self):
        result = ex_rich.rich_renderer().digest('test string')
        self.assertTrue(hasattr(result, '__rich_console__'))

    def test_digest_text(self):
        result = ex_rich.rich_renderer().digest({'typ': 'text', 'children': 'test text'})
        self.assertTrue(hasattr(result, '__rich_console__'))

    def test_digest_latex(self):
        result = ex_rich.rich_renderer().digest({'typ': 'latex', 'children': 'test latex'})
        self.assertTrue(hasattr(result, '__rich_console__'))

    def test_digest_line(self):
        result = ex_rich.rich_renderer().digest({'typ': 'line', 'children': 'test line'})
        # self.assertTrue(hasattr(result, 'renderables'))
        self.assertTrue(hasattr(result, '__rich_console__'))

    def test_handle_error(self):
        result = ex_rich.rich_renderer().handle_error('my_error', {'typ': 'unknown'})
        self.assertTrue(hasattr(result, '__rich_console__'))

    def test_convert(self):
        doc = pyd.get_example().dump()
        # Mock stream to avoid printing to console during test
        import io
        stream = io.StringIO()
        res = ex_rich.convert(doc, stream=stream)
        self.assertIsInstance(res, str)
        self.assertEqual(res, '')

    def test_digest_text_with_label(self):
        result = ex_rich.rich_renderer().digest({'typ': 'text', 'label': 'Test Label', 'children': 'test text'})
        self.assertTrue(hasattr(result, '__rich_console__'))

    def test_digest_markdown_with_label(self):
        result = ex_rich.rich_renderer().digest({'typ': 'markdown', 'label': 'Test Label', 'children': '# Test'})
        self.assertTrue(hasattr(result, '__rich_console__'))

    def test_digest_verbatim_with_label(self):
        result = ex_rich.rich_renderer().digest({'typ': 'verbatim', 'label': 'Test Label', 'children': 'test code'})
        self.assertTrue(hasattr(result, '__rich_console__'))

    def test_digest_image_with_caption(self):
        result = ex_rich.rich_renderer().digest({'typ': 'image', 'caption': 'Test Caption'})
        self.assertTrue(hasattr(result, '__rich_console__'))

    def test_digest_table_with_caption(self):
        dc = {
            'children': [['element1', 'element2']], 
            'caption': 'Test Table',
            'typ': 'table'
        }
        result = ex_rich.rich_renderer().digest(dc)
        self.assertTrue(hasattr(result, '__rich_console__'))

    def test_format(self):
        rr = ex_rich.rich_renderer()
        lst = rr.format(pyd.get_example().dump())
        self.assertIsInstance(lst, list)
        for x in lst:
            self.assertTrue(hasattr(x, '__rich_console__'))

    def test_convert(self):
        stream = io.StringIO()
        ex_rich.convert(pyd.get_example().dump(), stream=stream)
        stream.seek(0)
        s = stream.getvalue()
        self.assertTrue(s)


if __name__ == '__main__':
    unittest.main()
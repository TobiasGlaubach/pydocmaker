import unittest

import os, inspect, sys
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
if __name__ == '__main__':
    print(parent_dir)
    sys.path.insert(0, os.path.join(parent_dir, 'src'))

from pydocmaker.backend import pandoc_api
from pydocmaker.backend.pandoc_api import PandocFormatter

class TestConvert(unittest.TestCase):
    # def test_to_docx(self):
    #     doc = [{'typ': 'text', 'children': 'Test'}]
    #     result = pandoc_api.to_docx(doc)
    #     self.assertIsInstance(result, bytes)

    def test_to_html(self):
        doc = [{'typ': 'text', 'children': 'Test'}]
        result = pandoc_api.to_html(doc)
        self.assertIsInstance(result, str)
        self.assertIn('Test', result)

    def test_to_ipynb(self):
        doc = [{'typ': 'text', 'children': 'Test'}]
        with self.assertRaises(NotImplementedError):
            pandoc_api.to_ipynb(doc)

    def test_to_md(self):
        doc = [{'typ': 'text', 'children': 'Test'}]
        result = pandoc_api.to_md(doc)
        self.assertIsInstance(result, str)
        self.assertEqual(result, 'Test')

    def test_to_tex(self):
        doc = [{'typ': 'text', 'children': 'Test'}]
        result = pandoc_api.to_tex(doc)
        self.assertIsInstance(result, str)
        self.assertIn('Test', result)

    # def test_to_pdf(self):
    #     doc = [{'typ': 'text', 'children': 'Test'}]
    #     result = pandoc_api.to_pdf(doc)
    #     self.assertIsInstance(result, bytes)

    def test_pandoc_installed(self):
        self.assertTrue(pandoc_api.test_is_pandoc_installed())


class TestPandocFormatterHtml(unittest.TestCase):

    def setUp(self):
        self.formatter = PandocFormatter('html')

    def test_digest_markdown(self):
        result = self.formatter.digest_markdown(children='# Test')
        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertTrue(result.startswith('<'), result[:10] + '...')

        

    def test_digest_image(self):
        result = self.formatter.digest_image(children='test_image.png', imageblob='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==')
        
        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertTrue(result.startswith('<'), result[:10] + '...')
        self.assertIn('test_image.png', result)

    def test_digest_verbatim(self):
        result = self.formatter.digest_verbatim(children='print("Hello, World!")')
        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertTrue(result.startswith('<'), result[:10] + '...')
        self.assertIn('Hello', result)
        self.assertIn('World', result)

    def test_digest_iterator(self):
        result = self.formatter.digest_iterator([{'typ': 'text', 'children': 'Test1'}, {'typ': 'text', 'children': 'Test2'}])
        self.assertIsInstance(result, str)
        self.assertTrue(result)

        self.assertIn('Test1', result)
        self.assertIn('Test2', result)

    def test_digest_str(self):
        result = self.formatter.digest_str('Test')
        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertEqual('Test', result)

    def test_digest_text(self):
        result = self.formatter.digest_text(children='Test', color='red')
        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertIn('<div style="color:red;">', result)
        self.assertIn('Test', result)


    def test_digest_line(self):
        result = self.formatter.digest_line(children='Test', color='red')
        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertIn('<div style="color:red;">', result)
        self.assertTrue(result.endswith('\n'))

    def test_digest_latex(self):
        result = self.formatter.digest_latex(children='\\textit{Test}')
        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertTrue(result.startswith('<'), result[:10] + '...')
        self.assertIn('<em>Test</em>', result)

    def test_digest(self):
        result = self.formatter.digest({'typ': 'text', 'children': 'Test'})
        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertEqual('Test', result)

    def test_format(self):
        result = self.formatter.format([{'typ': 'text', 'children': 'Test1'}, {'typ': 'text', 'children': 'Test2'}])
        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertIn('Test1', result)
        self.assertIn('Test2', result)


class TestPandocFormatterMarkdown(unittest.TestCase):

    def test_digest_markdown(self):
        formatter = PandocFormatter('markdown')
        result = formatter.digest_markdown(children='# Test')
        self.assertIsInstance(result, str)
        self.assertTrue(result)

        self.assertIn('# Test', result)

    def test_digest_image(self):
        formatter = PandocFormatter('markdown')
        blob = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAQMAAAD+wSzIAAAABlBMVEX///+/v7+jQ3Y5AAAADklEQVQI12P4AIX8EAgALgAD/aNpbtEAAAAASUVORK5CYII'
        result = formatter.digest_image(children='test_image.png', imageblob=blob)
        
        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertIn('data:image/png;base64', result)
        self.assertIn(blob, result)

    def test_digest_verbatim(self):
        formatter = PandocFormatter('markdown')
        result = formatter.digest_verbatim(children='test_verbatim_text')
        self.assertIsInstance(result, str)
        self.assertTrue(result)

    def test_digest_iterator(self):
        formatter = PandocFormatter('markdown')
        result = formatter.digest_iterator([{'typ': 'text', 'children': 'test1'}, {'typ': 'text', 'children': 'test2'}])
        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertIn('test1\n\ntest2', result)

    def test_digest_str(self):
        formatter = PandocFormatter('markdown')
        result = formatter.digest_str('test_string')
        self.assertIsInstance(result, str)
        self.assertIn('test_string', result)

    def test_digest_text(self):
        formatter = PandocFormatter('markdown')
        result = formatter.digest_text(children='test_text', color='red')
        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertIn('test_text', result)

    def test_digest_latex(self):
        formatter = PandocFormatter('markdown')
        result = formatter.digest_latex(children='test_latex')
        self.assertIn('test_latex', result)

    def test_format(self):
        formatter = PandocFormatter('markdown')
        result = formatter.format([{'typ': 'text', 'children': 'test1'}, {'typ': 'text', 'children': 'test2'}])
        self.assertIn('test1\n\ntest2', result)

class TestPandocFormatterLatex(unittest.TestCase):

    def test_digest_markdown(self):
        formatter = PandocFormatter('latex')
        result = formatter.digest_markdown(children='# Test')
        self.assertIn('\\section{Test}', result)

    def test_digest_image(self):
        formatter = PandocFormatter('latex')
        blob = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAQMAAAD+wSzIAAAABlBMVEX///+/v7+jQ3Y5AAAADklEQVQI12P4AIX8EAgALgAD/aNpbtEAAAAASUVORK5CYII'
        result = formatter.digest_image(children='test_image.png', imageblob=blob)
        self.assertIn(blob, result)

    def test_digest_verbatim(self):
        formatter = PandocFormatter('latex')
        result = formatter.digest_verbatim(children='testVerbatimText')
        self.assertIn('\\begin{verbatim}', result)
        self.assertIn('testVerbatimText', result)
        self.assertIn('\\end{verbatim}', result)

    def test_digest_iterator(self):
        formatter = PandocFormatter('latex')
        result = formatter.digest_iterator([{'typ': 'text', 'children': 'test1'}, {'typ': 'text', 'children': 'test2'}])
        self.assertIn('test1\n\ntest2', result)

    def test_digest_str(self):
        formatter = PandocFormatter('latex')
        result = formatter.digest_str('teststring')
        self.assertIn('teststring', result)

    def test_digest_text(self):
        formatter = PandocFormatter('latex')
        result = formatter.digest_text(children='testtext', color='red')
        self.assertIn('\\textcolor{red}{testtext}', result)

    def test_digest_latex(self):
        formatter = PandocFormatter('latex')
        result = formatter.digest_latex(children='testlatex')
        self.assertEqual('testlatex', result)

    def test_format(self):
        formatter = PandocFormatter('latex')
        result = formatter.format([{'typ': 'text', 'children': 'test1'}, {'typ': 'text', 'children': 'test2'}])
        self.assertEqual('test1\n\ntest2', result)




# if __name__ == '__main__':
#     unittest.main()
#     # print('\n'.join(os.environ['PATH'].split(';')))




# Set the input and output file names
input_html = '<html><body>Hello World!</body></html>'

bts = pandoc_api.convert_html_to_pdf(input_html)

with open('test.zip', 'wb') as fp: 
    fp.write(bts)

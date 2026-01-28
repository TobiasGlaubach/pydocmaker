import tempfile
import unittest

import os, inspect, sys
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
if __name__ == '__main__':
    print(parent_dir)
    sys.path.insert(0, os.path.join(parent_dir, 'src'))

import pydocmaker as pyd

class TestCodeSnippets(unittest.TestCase):

    def test_s1_minimal(self):
        
        doc = pyd.Doc.get_example()
        self.assertTrue(doc)
    
    def test_s2_concept(self):
                
        doc = pyd.Doc() # basic doc where we always append to the end
        doc.add('dummy text') # adds raw text

        # this is how to add parts to the document
        doc.add_pre('this will be shown as preformatted') # preformatted
        doc.add_md('This is some *fancy* `markdown` **text**') # markdown
        doc.add_tex(r'\textbf{Hello, LaTeX!}') # latex

        # this is how to add an image from link
        doc.add_image("https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png", caption='', children='', width=None)


    def _test_s3_export(self, method, filename):
        with tempfile.TemporaryDirectory() as temp_dir:
            doc = pyd.get_example()
            full_path = os.path.join(temp_dir, filename)
            getattr(doc, f'to_{method}')(full_path)
            self.assertTrue(os.path.exists(full_path), f"{filename} does not exist")
            self.assertGreater(os.path.getsize(full_path), 0, f"{filename} is empty")

    def test_s3_export_html(self):
        self._test_s3_export('html', 'temp_outfile.html')

    @unittest.skipUnless(os.name == 'nt' or os.environ.get('PYDOCMAKER_TESTFULL'), "Skipping since test requires optional dependencies")
    def test_s3_export_pdf(self):
        self._test_s3_export('pdf', 'temp_outfile.pdf')

    def test_s3_export_markdown(self):
        self._test_s3_export('markdown', 'temp_outfile.md')

    def test_s3_export_docx(self):
        self._test_s3_export('docx', 'temp_outfile.docx')

    def test_s3_export_textile(self):
        self._test_s3_export('textile', 'temp_outfile.textile.zip')

    def test_s3_export_tex(self):
        self._test_s3_export('tex', 'temp_outfile.tex.zip')

    def test_s3_export_ipynb(self):
        self._test_s3_export('ipynb', 'temp_outfile.ipynb')

    def test_s3_export_json(self):
        self._test_s3_export('json', 'temp_outfile.json')
        
    def test_s4_addtable(self):
        doc = pyd.Doc()
        rows = []
        colors = ['blue', 'red', 'green']
        for irow in range(3):
            row = [pyd.mk_md(f'Row {irow} Col {icol}', color=colors[icol]) for icol in range(3)]
            rows.append(row)

        doc.add_table(rows, header=['Blue Text', 'Red Text', 'Green Text'])

        self.assertTrue(doc)
        self.assertEqual(doc[0]['typ'], "table")
        self.assertTrue(doc[0]['children'])
        self.assertTrue(doc[0]['header'])



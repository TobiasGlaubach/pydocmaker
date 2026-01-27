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
    def test_pdf_pandoc(self):
        templatepath = None
        metadata = None
        doc = pyd.Doc.get_example()
        bts = doc.to_pdf(engine='pandoc', template=templatepath, template_params=metadata)
        self.assertTrue(bts)
        self.assertIsInstance(bts, bytes)
        self.assertTrue(bts.startswith(b'%PDF'), str(bts)[:20])

    def test_pdf_libreoffice(self):
        templatepath = None
        metadata = None
        doc = pyd.Doc.get_example()
        bts = doc.to_pdf(engine='libreoffice', template=templatepath, template_params=metadata)
        self.assertTrue(bts)
        self.assertIsInstance(bts, bytes)
        self.assertTrue(bts.startswith(b'%PDF'), str(bts)[:20])
        
    def test_pdf_word(self):
        templatepath = None
        metadata = None
        doc = pyd.Doc.get_example()
        bts = doc.to_pdf(engine='word', template=templatepath, template_params=metadata, compress_images=True)
        self.assertTrue(bts)
        self.assertIsInstance(bts, bytes)
        self.assertTrue(bts.startswith(b'%PDF'), str(bts)[:20])

        doc = pyd.Doc.get_example()
        bts = doc.to_pdf(engine='word', template=templatepath, template_params=metadata, compress_images=False)
        self.assertTrue(bts)
        self.assertIsInstance(bts, bytes)
        
        self.assertTrue(bts.startswith(b'%PDF'), str(bts)[:20])
    
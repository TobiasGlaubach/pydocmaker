import tempfile
import unittest

import os, inspect, sys
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
if __name__ == '__main__':
    print(parent_dir)
    sys.path.insert(0, os.path.join(parent_dir, 'src'))

import pydocmaker as pyd

class TestMakePdfs(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt' or os.environ.get('PYDOCMAKER_TESTFULL'), "Skipping since test requires optional dependencies")
    def test_pdf_pandoc(self):
        templatepath = None
        metadata = None
        doc = pyd.Doc.get_example()
        bts = doc.to_pdf(engine='pandoc', template=templatepath, template_params=metadata, verb=0)
        self.assertTrue(bts)
        self.assertIsInstance(bts, bytes)
        self.assertTrue(bts.startswith(b'%PDF'), str(bts)[:20])

    @unittest.skipUnless(os.name == 'nt' or os.environ.get('PYDOCMAKER_TESTFULL'), "Skipping since test requires optional dependencies")
    def test_pdf_libreoffice(self):
        templatepath = None
        metadata = None
        doc = pyd.Doc.get_example()
        bts = doc.to_pdf(engine='libreoffice', template=templatepath, template_params=metadata, verb=0)
        self.assertTrue(bts)
        self.assertIsInstance(bts, bytes)
        self.assertTrue(bts.startswith(b'%PDF'), str(bts)[:20])
        
    @unittest.skipUnless(os.name == 'nt', "Skipping win32comapi since test requires Windows platform")
    def test_pdf_word(self):
        templatepath = None
        metadata = None
        doc = pyd.Doc.get_example()
        bts = doc.to_pdf(engine='word', template=templatepath, template_params=metadata, compress_images=True, verb=0)
        self.assertTrue(bts)
        self.assertIsInstance(bts, bytes)
        self.assertTrue(bts.startswith(b'%PDF'), str(bts)[:20])

        doc = pyd.Doc.get_example()
        bts = doc.to_pdf(engine='word', template=templatepath, template_params=metadata, compress_images=False, verb=0)
        self.assertTrue(bts)
        self.assertIsInstance(bts, bytes)
        
        self.assertTrue(bts.startswith(b'%PDF'), str(bts)[:20])
    


    def test_pdf_typst(self):
        templatepath = None
        metadata = None
        doc = pyd.Doc.get_example()
        bts = doc.to_pdf(engine='typst', template=templatepath, template_params=metadata, verb=0)
        self.assertTrue(bts)
        self.assertIsInstance(bts, bytes)
        self.assertTrue(bts.startswith(b'%PDF'), str(bts)[:20])

        doc = pyd.Doc.get_example()
        bts = doc.to_pdf(engine='typst', template=templatepath, template_params=metadata, verb=0)
        self.assertTrue(bts)
        self.assertIsInstance(bts, bytes)
        
        self.assertTrue(bts.startswith(b'%PDF'), str(bts)[:20])

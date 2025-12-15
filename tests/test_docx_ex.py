import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO
from docx import Document


import os, inspect, sys
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
if __name__ == '__main__':
    print(parent_dir)
    sys.path.insert(0, os.path.join(parent_dir, 'src'))

from pydocmaker.backend import ex_html, ex_docx, ex_ipynb, ex_markdown, ex_redmine, ex_tex

import pydocmaker as pyd
from pydocmaker.backend.ex_docx import DocxFile, DocxFileW32


class TestDocxFile(unittest.TestCase):


    
    def test_append(self):
        
        sample_docx = pyd.get_example().to_docx()

        # Create an instance of DocxFile
        docx_file = DocxFile(sample_docx)

        # Call the append method
        docx_file.append(sample_docx, sample_docx, sample_docx,sample_docx)
        docx2 = docx_file.docx_data
        self.assertGreater(len(docx2), len(sample_docx))
        
        

    def test_replace_fields(self):
        sample_docx = pyd.get_example().to_docx()

        # Create an instance of DocxFile
        docx_file = DocxFile(sample_docx)

        # Call the replace_fields method
        replace_dict = {'Gregor': 'Peter', 'Samsa': 'Pan'}
        docx_file.replace_fields(replace_dict)
        docx2 = docx_file.docx_data
        self.assertNotEqual(len(docx2), len(sample_docx))


    def test_replace_keywords(self):
        sample_docx = pyd.get_example().to_docx()

        # Create an instance of DocxFile
        docx_file = DocxFile(sample_docx)

        # Call the replace_fields method
        replace_dict = {'Gregor': 'Peter', 'Samsa': 'Pan'}
        docx_file.replace_keywords(replace_dict)
        docx2 = docx_file.docx_data
        self.assertNotEqual(len(docx2), len(sample_docx))

    def test_replace_keywords_raw(self):
        sample_docx = pyd.get_example().to_docx()

        # Create an instance of DocxFile
        docx_file = DocxFile(sample_docx)

        # Call the replace_fields method
        replace_dict = {'Gregor': 'Peter', 'Samsa': 'Pan'}
        docx_file.replace_keywords_raw(replace_dict)
        docx2 = docx_file.docx_data
        self.assertNotEqual(len(docx2), len(sample_docx))

    def test_save(self):
        sample_docx = pyd.get_example().to_docx()

        # Create an instance of DocxFile
        docx_file = DocxFile(sample_docx)

        bts = docx_file.save()

        # Check if the output buffer contains the DOCX data
        self.assertEqual(bts, docx_file.docx_data)
        self.assertEqual(bts, sample_docx)

if __name__ == '__main__':
    unittest.main()
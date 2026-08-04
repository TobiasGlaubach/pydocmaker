import unittest

import os, inspect, sys
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
if __name__ == '__main__':
    print(parent_dir)
    sys.path.insert(0, os.path.join(parent_dir, 'src'))

from pydocmaker.core import Doc

class TestDoc(unittest.TestCase):
    def setUp(self):
        self.doc_builder = Doc.get_example()

    def test_iadd_with_string(self):
        s = "Test String"
        self.doc_builder += s
        self.assertEqual(self.doc_builder[-1].get('typ'), self.doc_builder.DEFAULT_ADD_STRING_TYPE)
        self.assertEqual(self.doc_builder[-1].get('children'), s)

    def test_iadd_with_tuple(self):
        s = "Test String"
        self.doc_builder += (s, 'tex')
        self.assertEqual(self.doc_builder[-1].get('typ'), 'latex')
        self.assertEqual(self.doc_builder[-1].get('children'), s)

    def test_iadd_with_list(self):
        s = "Test String"
        self.doc_builder += [s, 'verbatim']
        self.assertEqual(self.doc_builder[-1].get('typ'), 'verbatim')
        self.assertEqual(self.doc_builder[-1].get('children'), s)

    def test_iadd_with_doc_builder(self):
        other_doc_builder = Doc().add_md("Other Test String")
        self.doc_builder += other_doc_builder
        self.assertEqual(len(self.doc_builder), len(Doc.get_example()) + len(other_doc_builder))
        self.assertEqual(self.doc_builder[-1].get('typ'), 'markdown')
        self.assertEqual(self.doc_builder[-1].get('children'), "Other Test String")

class TestDocTemplate(unittest.TestCase):
    def setUp(self):
        self.doc = Doc.get_example()

    def test_to_pdf_with_template(self):
        template_id = "report"  # assume exists
        template_params = {"author": "Me!"}
        pdf_bytes = self.doc.to_pdf(template=template_id, template_params=template_params)
        self.assertIsInstance(pdf_bytes, bytes) 

    def test_to_pdf_with_template_from_meta(self):
        template_id = "report"  # assume exists
        template_params = {"author": "Me!"}
        self.doc.set_template_to_meta(template_id=template_id, template_params=template_params)
        pdf_bytes = self.doc.to_pdf()
        self.assertIsInstance(pdf_bytes, bytes)

    def test_pdf_generation_consistency(self):
        template_id = "report" # assume exists
        template_params = {"author": "Me!"}
        bts1 = self.doc.to_pdf(template=template_id, template_params=template_params)
        self.doc.set_template_to_meta(template_id=template_id, template_params=template_params)
        bts2 = self.doc.to_pdf()
        self.assertEqual(bts1, bts2, "should show the same document / use the same template, but does not")



if __name__ == "__main__":
    unittest.main()

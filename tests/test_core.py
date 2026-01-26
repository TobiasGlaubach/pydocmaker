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
        self.assertEqual(self.doc_builder[-1].get('typ'), self.doc_builder.default_add_string_type)
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

if __name__ == "__main__":
    unittest.main()

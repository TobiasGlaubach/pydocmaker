from pathlib import Path
import unittest
import os, inspect, sys, base64, io, tempfile
from unittest.mock import patch, MagicMock

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)

from pydocmaker.backend import ex_typst

from pydocmaker.backend.ex_typst import (
    convert as to_typst,
    compile_with_typst as to_pdf_typst,
)

import pydocmaker as pyd

class TestExampleDocumentTypstCompilation(unittest.TestCase):
    """Test cases for compiling the example document to PDF using typst."""

    def test_example_document_convert_to_typst(self):
        """Test that the example document converts to typst code correctly."""
        

        doc = pyd.Doc.get_example()
        dumped = doc.dump()
        typst_code = ex_typst.convert(dumped)
        self.assertIsInstance(typst_code, str)
        self.assertTrue(len(typst_code) > 0)

    
    def test_example_document_compile_to_pdf(self):
        """Test compiling the example document to PDF via typst."""

        doc = pyd.Doc.get_example()
        s, _ = to_typst(doc.dump(), ret_attachments=True)
        result = to_pdf_typst(s, on_warning='ignore', verb=0)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    
    def test_example_document_compile_to_pdf_twice(self):
        """Test compiling the same example document to PDF twice produces valid results."""

        doc1 = pyd.Doc.get_example()
        s1, _ = to_typst(doc1.dump(), ret_attachments=True)
        result1 = to_pdf_typst(s1, on_warning='ignore', verb=0)
        doc2 = pyd.Doc.get_example()
        s2, _ = to_typst(doc2.dump(), ret_attachments=True)
        result2 = to_pdf_typst(s2, on_warning='ignore', verb=0)
        self.assertIsNotNone(result1)
        self.assertIsNotNone(result2)
        self.assertIsInstance(result1, bytes)
        self.assertIsInstance(result2, bytes)
        self.assertTrue(result1.startswith(b'%PDF'))
        self.assertTrue(result2.startswith(b'%PDF'))

    
    def test_example_document_compile_with_template(self):
        """Test compiling example document with a custom template."""

        doc = pyd.Doc.get_example()
        s, _ = to_typst(doc.dump(), template=None, template_params={}, ret_attachments=True)
        result = to_pdf_typst(s, on_warning='ignore', verb=0)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    
    def test_example_document_dump_and_compile(self):
        """Test that dumping the example doc and compiling the dumped structure works."""


        doc = pyd.Doc.get_example()
        dumped = doc.dump()
        self.assertIsInstance(dumped, list)
        self.assertTrue(len(dumped) > 0)
        typst_code = ex_typst.convert(dumped)
        self.assertIsInstance(typst_code, str)
        self.assertTrue(len(typst_code) > 0)

    
    
    def test_example_document_compile_with_output_path(self):
        """Test compiling example document with explicit output path."""


        doc = pyd.Doc.get_example()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'output.pdf')
            ex_typst.compile_with_typst(
                ex_typst.convert(doc.dump()),
                output=output_path,
                verb=0
            )
            result = Path(output_path).read_bytes()
            self.assertIsNotNone(result)
            self.assertIsInstance(result, bytes)
            self.assertTrue(result.startswith(b'%PDF'))

    
    def test_example_document_with_attachments_compile(self):
        """Test compiling example document with string attachments."""

        doc = pyd.Doc.get_example()
        attachments = {
            'helper.typ': '# Helper code for testing',
        }
        result = ex_typst.compile_with_typst(
            ex_typst.convert(doc.dump()),
            attachments=attachments,
            verb=0
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    
    def test_example_document_with_bytes_attachments(self):
        """Test compiling example document with bytes attachments (e.g., images)."""

        doc = pyd.Doc.get_example()
        image_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 50
        attachments = {
            'logo.png': image_data,
        }
        result = ex_typst.compile_with_typst(
            ex_typst.convert(doc.dump()),
            attachments=attachments,
            verb=0
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    
    def test_example_document_with_mixed_attachments(self):
        """Test compiling example document with mixed string and bytes attachments."""

        import pydocmaker as pyd
        doc = pyd.Doc.get_example()
        attachments = {
            'helper.typ': '# Helper typst code\nlet test() = "hello"',
            'image.png': b'\x89PNG\r\n\x1a\n' + b'\x00' * 100,
            'style.typ': '# Style settings\n#set text(size: 10pt)',
        }
        result = ex_typst.compile_with_typst(
            ex_typst.convert(doc.dump()),
            attachments=attachments,
            verb=0
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    
    def test_example_document_convert_contains_expected_content(self):
        """Test that converted example document contains expected typst content."""


        doc = pyd.Doc.get_example()
        dumped = doc.dump()
        typst_code = ex_typst.convert(dumped)
        # The example doc contains markdown, verbatim (code), LaTeX, table, and image
        self.assertIn('vermin', typst_code)
        self.assertIn('```', typst_code)
        self.assertIn('table', typst_code)
        # Image should produce base64 data
        self.assertIn('base64', typst_code)

    
    def test_example_document_compile_on_warning_ignore(self):
        """Test compiling example document with on_warning='ignore'."""


        doc = pyd.Doc.get_example()
        result = ex_typst.compile_with_typst(
            ex_typst.convert(doc.dump()),
            on_warning='ignore',
            verb=0
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b'%PDF'))

    
    def test_example_document_full_workflow(self):
        """Test the full workflow: get example, dump, convert, compile to PDF."""


        doc = pyd.Doc.get_example()
        dumped = doc.dump()
        typst_code = ex_typst.convert(dumped)
        pdf_result = ex_typst.compile_with_typst(typst_code, verb=0)
        self.assertIsNotNone(pdf_result)
        self.assertIsInstance(pdf_result, bytes)
        self.assertTrue(pdf_result.startswith(b'%PDF'))


if __name__ == '__main__':
    unittest.main()

import base64
from pathlib import Path
from pydoc import Doc
import unittest
import os, inspect, io, tempfile
import warnings
from pydocmaker.core import Doc

from pydocmaker.io.html_loader import io_serialize_html, io_deserialize_html

class TestDocToHtml(unittest.TestCase):

    def test_roundtrip_html_serialization(self):
        """Test the round-trip serialization and deserialization of a pydocmaker document to HTML."""

        doc = Doc.get_example()
        doc.update_meta({
            "title": "Sample Document",
            "author": "Jane Doe",
            "status": "draft"
        })

        file_path = "output_document.html"

        # 2. Serialize to HTML
        print(f"Serializing document to {file_path}...")
        html = io_serialize_html(doc)

        # 3. Deserialize back from HTML
        print(f"Deserializing document back from {file_path}...")
        restored_document = io_deserialize_html(html)

        # 4. Verify lossless round-trip
        self.assertEqual(doc.dumps(), restored_document.dumps(), "Round-trip failed! Data mismatch detected.")
        # print("Success! Round-trip serialization and deserialization completed with 100% fidelity.")


if __name__ == '__main__':
    unittest.main()



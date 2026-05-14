import unittest
import os, inspect, sys, base64

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, os.path.join(parent_dir, 'src'))

from pydocmaker.backend import ex_typst


class TestTypstRenderer(unittest.TestCase):

    def setUp(self) -> None:
        self.formatter = ex_typst.DocumentMarkdownFormatter()

    def test_digest_image_data_uri_any_image_format(self):
        payload = base64.b64encode(b'abcd').decode('ascii')
        blob = f'data:image/jpeg; base64,{payload}'
        result = self.formatter.digest({'typ': 'image', 'filename': 'test.jpg', 'imageblob': blob})
        self.assertIsInstance(result, str)
        self.assertIn('data:image/jpeg;base64,', result)

    def test_digest_image_ext_mismatch_raises(self):
        payload = base64.b64encode(b'abcd').decode('ascii')
        blob = f'data:image/png;base64,{payload}'
        with self.assertRaises(ValueError):
            self.formatter.digest({'typ': 'image', 'filename': 'test.jpg', 'imageblob': blob})

    def test_digest_image_plain_base64_uses_filename_ext(self):
        payload = base64.b64encode(b'abcd').decode('ascii')
        result = self.formatter.digest({'typ': 'image', 'filename': 'test.png', 'imageblob': payload})
        self.assertIn('data:image/png;base64,', result)


if __name__ == '__main__':
    unittest.main()

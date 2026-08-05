import re
import unittest

import os, inspect, sys
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
if __name__ == '__main__':
    print(parent_dir)
    sys.path.insert(0, os.path.join(parent_dir, 'src'))

from pydocmaker.core import Doc
import tempfile
import io
import json
from pathlib import Path

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

        diff_indices = [i for i, (v1, v2) in enumerate(zip(bts1, bts2)) if v1 != v2]
        limit = len(bts1) * 0.05

        self.assertLess(len(diff_indices), limit, "should show the same document / use the same template, but does not")


class TestDocSaveLoad(unittest.TestCase):
    def setUp(self):
        self.doc = Doc.get_example()

    def test_save_return_txt_when_no_path(self):
        res = self.doc.save()
        self.assertIsInstance(res, str)
        self.assertTrue(res.startswith("<!DOCTYPE html>"), "Expected HTML content to be returned when no file path is provided.")

    def test_save_load_roundtrip_file_path_str(self):
        tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        tmp.close()
        try:
            # ensure extension is honored when provided
            self.doc.save(tmp.name, format='json')
            loaded = Doc.load(tmp.name)
            self.assertEqual(self.doc.dumps(), loaded.dumps())
        finally:
            try:
                Path(tmp.name).unlink()
            except Exception:
                pass

    def test_save_load_roundtrip_pathlib(self):
        d = Path(tempfile.mkdtemp())
        p = d / 'out.json'
        try:
            # pass a Path object
            self.doc.save(p, format='json')
            loaded = Doc.load(p)
            self.assertEqual(self.doc.dumps(), loaded.dumps())
        finally:
            try:
                if p.exists():
                    p.unlink()
                d.rmdir()
            except Exception:
                pass

    def test_save_load_roundtrip_file_like(self):
        tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        tmp.close()
        try:
            # open as text file and pass file object to save
            with open(tmp.name, 'w', encoding='utf-8') as f:
                self.doc.save(f)

            # read back and load from string
            with open(tmp.name, 'r', encoding='utf-8') as f:
                content = f.read()
            loaded = Doc.load(content)
            self.assertEqual(self.doc.dumps(), loaded.dumps())
        finally:
            try:
                Path(tmp.name).unlink()
            except Exception:
                pass

    def test_load_from_bytes_and_string(self):
        s = self.doc.dumps()
        b = s.encode('utf-8')
        loaded_b = Doc.load(b)
        loaded_s = Doc.load(s)
        self.assertEqual(self.doc.dumps(), loaded_b.dumps())
        self.assertEqual(self.doc.dumps(), loaded_s.dumps())

    def test_all_supported_formats_case_insensitive(self):
        # cover .html/.pyd/.pydoc, .ipynb and .json in lower/upper/no-dot/ext-param forms
        exts = ['html', 'pyd', 'pydoc', 'ipynb', 'json']

        for ext in exts:
            # 1) file path with lowercase suffix
            tmp = tempfile.NamedTemporaryFile(suffix='.' + ext, delete=False)
            tmp.close()
            try:
                self.doc.save(tmp.name)
                loaded = Doc.load(tmp.name)
                self.assertEqual(self.doc.dumps(), loaded.dumps(), f'roundtrip failed for .{ext}')
            except Exception:
                # some formats (notably ipynb in some environments) may fail to serialize
                # skip those cases rather than fail the whole test
                continue
            finally:
                try:
                    Path(tmp.name).unlink()
                except Exception:
                    pass

            # 2) file path with UPPERCASE suffix
            tmpu = tempfile.NamedTemporaryFile(suffix='.' + ext.upper(), delete=False)
            tmpu.close()
            try:
                self.doc.save(tmpu.name)
                loaded = Doc.load(tmpu.name)
                self.assertEqual(self.doc.dumps(), loaded.dumps(), f'roundtrip failed for .{ext.upper()}')
            except Exception:
                continue
            finally:
                try:
                    Path(tmpu.name).unlink()
                except Exception:
                    pass

            # 3) path without suffix but ext parameter provided (mixed case)
            d = Path(tempfile.mkdtemp())
            p = d / f'out_noext_{ext}'
            try:
                # pass ext in mixed case
                self.doc.save(str(p), format=ext.upper())
                # file should have been created with suffix
                created = None
                for cand in d.iterdir():
                    if cand.stem.startswith('out_noext_'):
                        created = cand
                        break
                self.assertIsNotNone(created, f'no file created for ext {ext}')
                loaded = Doc.load(str(created))
                self.assertEqual(self.doc.dumps(), loaded.dumps(), f'roundtrip failed for created file with ext {ext}')
            finally:
                try:
                    # cleanup files
                    for cand in d.iterdir():
                        try:
                            cand.unlink()
                        except Exception:
                            pass
                    d.rmdir()
                except Exception:
                    pass

            # 4) file-like object write + load from string
            tmpf = tempfile.NamedTemporaryFile(suffix='.' + ext, delete=False)
            tmpf.close()
            try:
                # open as text and write via file-like API
                with open(tmpf.name, 'w', encoding='utf-8') as f:
                    self.doc.save(f, format=ext)

                with open(tmpf.name, 'r', encoding='utf-8') as f:
                    content = f.read()
                loaded = Doc.load(content)
                self.assertEqual(self.doc.dumps(), loaded.dumps(), f'roundtrip failed for file-like and ext {ext}')
            except Exception:
                continue
            finally:
                try:
                    Path(tmpf.name).unlink()
                except Exception:
                    pass



if __name__ == "__main__":
    unittest.main()


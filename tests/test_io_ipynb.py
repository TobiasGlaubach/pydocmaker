import unittest
import os, inspect, sys
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
if __name__ == '__main__':
    print(parent_dir)
    sys.path.insert(0, os.path.join(parent_dir, 'src'))

import base64
import io
import json
import tempfile
from pathlib import Path
from unittest import mock

from pydocmaker.core import Doc
from pydocmaker.backend.pandoc_api import can_run_pandoc

from pydocmaker.io.ipynb_loader import (
    _ms,
    get_between_pre,
    get_between,
    html2md,
    clean_md,
    IpynbLoader,
    load_notebook,
    io_check_ipynb,
    io_deserialize_ipynb,
    io_serialize_ipynb,
)

from pydocmaker import b64_data
from pydocmaker.util import make_png_imageblob


PNG_BLOB = make_png_imageblob(b64_data.example_image).split(';base64,')[-1]


def make_jpeg_blob():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (8, 6), color=(200, 30, 30)).save(buf, format='JPEG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')


JPEG_BLOB = make_jpeg_blob()


def md_cell(source, **kw):
    cell = {"cell_type": "markdown", "metadata": {}, "source": source}
    cell.update(kw)
    return cell


def code_cell(source, outputs=None, execution_count=1, **kw):
    cell = {"cell_type": "code", "metadata": {}, "source": source,
            "outputs": outputs or [], "execution_count": execution_count}
    cell.update(kw)
    return cell


def make_notebook(*cells, **meta):
    m = {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}}
    m.update(meta)
    return {"cells": list(cells), "metadata": m, "nbformat": 4, "nbformat_minor": 2}


def elems_of_type(doc, typ):
    return [el for el in doc if el.get('typ') == typ]


def content_of(doc, typ=None):
    parts = []
    for el in doc:
        if typ and el.get('typ') != typ:
            continue
        parts.append(str(el.get('children', '')))
    return '\n'.join(parts)


class TestMs(unittest.TestCase):

    def test_str_passthrough(self):
        self.assertEqual(_ms("hello world"), "hello world")

    def test_bytes_decoded(self):
        self.assertEqual(_ms(b"hello world"), "hello world")

    def test_list_of_strings_joined(self):
        self.assertEqual(_ms(["hello ", "world"]), "hello world")

    def test_nested_iterables(self):
        self.assertEqual(_ms(["a", ["b", "c"]]), "abc")

    def test_other_object_stringified(self):
        self.assertEqual(_ms(42), "42")


class TestGetBetween(unittest.TestCase):

    def test_find_parenthesized_block(self):
        s = "![](data:image/png;base64,ABC)"
        istart, iend = get_between(s, '(', ')')
        self.assertEqual(s[istart:iend], "data:image/png;base64,ABC")

    def test_balanced_nested_delimiters(self):
        s = "(a(b)c)d"
        istart, iend = get_between(s, '(', ')')
        self.assertEqual(s[istart:iend], "a(b)c")

    def test_no_starter_found(self):
        istart, iend = get_between("no delimiters here", '(', ')')
        self.assertIsNone(istart)

    def test_only_closing_delimiter(self):
        istart, iend = get_between("abc)", '(', ')')
        self.assertIsNone(istart)


class TestGetBetweenPre(unittest.TestCase):

    def test_simple_pre(self):
        self.assertEqual(get_between_pre("<pre>content</pre>"), "content")

    def test_pre_with_attributes(self):
        self.assertEqual(get_between_pre('<pre style="color:red;">x</pre>'), "x")

    def test_keeps_balanced_tags_inside_pre(self):
        self.assertEqual(get_between_pre("<pre><b>bold</b></pre>"), "<b>bold</b>")

    def test_no_pre_returns_input_unchanged(self):
        self.assertEqual(get_between_pre("plain text"), "plain text")

    def test_unterminated_pre_returns_input_unchanged(self):
        self.assertEqual(get_between_pre("<pre>not terminated"), "<pre>not terminated")


class TestHtml2Md(unittest.TestCase):

    @unittest.skipUnless(can_run_pandoc(), "pandoc is not installed")
    def test_converts_headings_and_paragraphs(self):
        doc = html2md("<h1>Title</h1><p>Body text</p>")
        self.assertIsInstance(doc, Doc)
        c = content_of(doc)
        self.assertIn("Title", c)
        self.assertIn("Body text", c)
        self.assertTrue(all(el.get('typ') == 'markdown' for el in doc))


class TestCleanMd(unittest.TestCase):

    def test_plain_markdown(self):
        doc = clean_md("Hello **world**")
        self.assertEqual(len(elems_of_type(doc, 'markdown')), 1)
        self.assertIn("Hello **world**", content_of(doc))

    def test_div_tags_removed(self):
        doc = clean_md("<div>Hello</div>")
        self.assertIn("Hello", content_of(doc))
        self.assertNotIn("<div>", content_of(doc))

    def test_fence_lines_skipped(self):
        doc = clean_md("::: {.class}\nHello\n:::")
        self.assertIn("Hello", content_of(doc))
        self.assertNotIn(":::", content_of(doc))

    def test_base64_image_extracted(self):
        doc = clean_md("![](data:image/png;base64,QUJD)")
        images = elems_of_type(doc, 'image')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].get('imageblob'), "QUJD")

    def test_image_width_parsed_from_max_width(self):
        doc = clean_md("![](data:image/png;base64,QUJD){width=50% max-width: 60%}")
        images = elems_of_type(doc, 'image')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].get('width'), 0.6)

    def test_image_without_width_gets_none(self):
        doc = clean_md("![](data:image/png;base64,QUJD)")
        self.assertIsNone(elems_of_type(doc, 'image')[0].get('width'))

    def test_empty_image_blob_skipped(self):
        doc = clean_md("before\n![](data:image/png;base64,)")
        self.assertEqual(len(elems_of_type(doc, 'image')), 0)
        self.assertIn("before", content_of(doc))

    def test_text_around_image_kept_once(self):
        """Regression: text preceding an embedded image must not be duplicated."""
        doc = clean_md("A\nB\n![](data:image/png;base64,QUJD)\nC")
        mds = [el.get('children') for el in elems_of_type(doc, 'markdown')]
        self.assertEqual(mds, ["A\nB", "C"])
        self.assertEqual(len(elems_of_type(doc, 'image')), 1)

    def test_multiple_images_split_blocks(self):
        doc = clean_md("first\n![](data:image/png;base64,QUJD)\nsecond\n![](data:image/png;base64,REVG)")
        self.assertEqual(len(elems_of_type(doc, 'image')), 2)
        mds = [el.get('children') for el in elems_of_type(doc, 'markdown')]
        self.assertEqual(mds, ["first", "second"])


class TestCellHasCode(unittest.TestCase):

    def setUp(self):
        self.loader = IpynbLoader()

    def test_code_cell_with_list_source(self):
        cell = code_cell(["x = 1\n", "y = 2\n"])
        self.assertTrue(self.loader._cell_has_code(cell))

    def test_code_cell_with_str_source(self):
        self.assertTrue(self.loader._cell_has_code(code_cell("x = 1")))

    def test_code_cell_empty_source(self):
        self.assertFalse(self.loader._cell_has_code(code_cell("")))

    def test_code_cell_whitespace_only_source(self):
        self.assertFalse(self.loader._cell_has_code(code_cell(["   \n", "\n"])))

    def test_markdown_cell_is_not_code(self):
        self.assertFalse(self.loader._cell_has_code(md_cell("# heading")))


class TestIpynbLoaderLoadNotebook(unittest.TestCase):

    def test_load_from_dict(self):
        nb = make_notebook(md_cell("# Hello World"), code_cell("print(42)", execution_count=3))
        doc = IpynbLoader().load_notebook(nb)
        self.assertIsInstance(doc, Doc)
        c = content_of(doc)
        self.assertIn("Hello World", c)
        self.assertIn("print(42)", c)
        self.assertIn("```python", c)
        self.assertIn("Cell 3", c)

    def test_load_from_json_string(self):
        nb = make_notebook(md_cell("# Hello World"))
        doc = IpynbLoader().load_notebook(json.dumps(nb))
        self.assertIn("Hello World", content_of(doc))

    def test_pydocmaker_payload_shortcut(self):
        payload = Doc().add_md("PAYLOAD CONTENT").add_pre("payload code").dump()
        nb = make_notebook(md_cell("# This cell must be ignored"))
        nb["metadata"]["pydocmaker-payload"] = payload
        doc = IpynbLoader().load_notebook(nb)
        self.assertEqual(doc.dump(), payload)
        self.assertIn("PAYLOAD CONTENT", content_of(doc))
        self.assertNotIn("must be ignored", content_of(doc))

    def test_metadata_in_doc_body(self):
        nb = make_notebook(md_cell("# Hello"))
        doc = IpynbLoader(include_metadata_in_doc=True, include_metadata_in_docmeta=False,
                          add_nb_version=False).load_notebook(nb)
        self.assertIn("Notebook metadata", content_of(doc))
        pres = content_of(doc, typ='verbatim')
        self.assertIn("kernelspec", pres)
        self.assertIn("python3", pres)

    def test_metadata_in_docmeta(self):
        nb = make_notebook(md_cell("# Hello"))
        doc = IpynbLoader(include_metadata_in_doc=False, include_metadata_in_docmeta=True,
                          add_nb_version=False).load_notebook(nb)
        metas = elems_of_type(doc, 'meta')
        self.assertEqual(len(metas), 1)
        self.assertEqual(metas[0]['data'].get('kernelspec', {}).get('name'), 'python3')

    def test_metadata_excluded(self):
        nb = make_notebook(md_cell("# Hello"))
        doc = IpynbLoader(include_metadata_in_doc=False, include_metadata_in_docmeta=False,
                          add_nb_version=False).load_notebook(nb)
        self.assertEqual(len(elems_of_type(doc, 'meta')), 0)
        self.assertNotIn("Notebook metadata", content_of(doc))

    def test_nb_version_added(self):
        doc = IpynbLoader().load_notebook(make_notebook(md_cell("# Hello")))
        self.assertIn("- Notebook version: 4.2", content_of(doc))
        metas = elems_of_type(doc, 'meta')
        self.assertEqual(metas[0]['data'].get('nbformat'), 4)
        self.assertEqual(metas[0]['data'].get('nbformat_minor'), 2)

    def test_file_name_in_footer(self):
        doc = IpynbLoader().load_notebook(make_notebook(md_cell("# Hello")), file_name="my_nb.ipynb")
        self.assertIn('- Notebook name: "my_nb.ipynb"', content_of(doc))

    def test_no_footer_without_file_name(self):
        doc = IpynbLoader(add_nb_version=False, include_metadata_in_doc=False,
                          include_metadata_in_docmeta=False).load_notebook(make_notebook(md_cell("# Hello")))
        self.assertNotIn("Notebook name", content_of(doc))

    def test_nocode_excludes_code_cells(self):
        nb = make_notebook(md_cell("# Hello"), code_cell("secret = 12345"))
        doc = IpynbLoader(nocode=True).load_notebook(nb)
        self.assertIn("Hello", content_of(doc))
        self.assertNotIn("secret = 12345", content_of(doc))

    def test_exclude_input_cells(self):
        nb = make_notebook(md_cell("# Hello"), code_cell("secret = 12345"))
        doc = IpynbLoader(include_input_cells=False).load_notebook(nb)
        self.assertNotIn("secret = 12345", content_of(doc))

    def test_broken_output_is_reported_in_doc(self):
        nb = make_notebook(code_cell("x = 1", outputs=[{"output_type": "bogus_type"}]))
        doc = IpynbLoader().load_notebook(nb)
        c = content_of(doc, typ='verbatim')
        self.assertIn("Error parsing output cell", c)
        self.assertIn("Unknown cell type: bogus_type", c)

    def test_verb_logging_smoke(self):
        nb = make_notebook(md_cell("# Hello"), code_cell("print(42)"))
        doc = IpynbLoader(verb=True).load_notebook(nb)
        self.assertIn("Hello", content_of(doc))


class TestParseOutputDataPart(unittest.TestCase):

    def make_loader(self, **kw):
        return IpynbLoader(**kw)

    def test_text_plain_becomes_verbatim(self):
        doc = Doc()
        self.make_loader().parse_output_data_part(doc, "text/plain", "some output")
        self.assertEqual(len(elems_of_type(doc, 'verbatim')), 1)
        self.assertEqual(content_of(doc, typ='verbatim'), "some output")

    def test_text_plain_blue_by_default(self):
        doc = Doc()
        self.make_loader().parse_output_data_part(doc, "text/plain", "some output")
        self.assertEqual(elems_of_type(doc, 'verbatim')[0].get('color'), 'blue')

    def test_text_plain_without_blue(self):
        doc = Doc()
        self.make_loader(make_output_blue=False).parse_output_data_part(doc, "text/plain", "some output")
        self.assertNotEqual(elems_of_type(doc, 'verbatim')[0].get('color'), 'blue')

    def test_text_plain_as_raw_text(self):
        doc = Doc()
        self.make_loader(plainout_as_raw=True).parse_output_data_part(doc, "text/plain", "some output")
        self.assertEqual(len(elems_of_type(doc, 'text')), 1)
        self.assertEqual(content_of(doc, typ='text'), "some output")

    def test_ipython_repr_skipped(self):
        doc = Doc()
        self.make_loader().parse_output_data_part(doc, "text/plain", "<IPython.core.display.HTML object>")
        self.assertEqual(len(doc), 0)

    def test_matplotlib_repr_skipped(self):
        doc = Doc()
        self.make_loader().parse_output_data_part(doc, "text/plain", "<matplotlib.lines.Line2D object at 0x7f00>")
        self.assertEqual(len(doc), 0)

    def test_figure_repr_skipped(self):
        doc = Doc()
        self.make_loader().parse_output_data_part(doc, "text/plain", "<Figure size 640x480 with 1 Axes>")
        self.assertEqual(len(doc), 0)

    def test_matplotlib_repr_kept_when_not_skipped(self):
        doc = Doc()
        self.make_loader(skip_single_matplotlib_output=False).parse_output_data_part(
            doc, "text/plain", "<matplotlib.lines.Line2D object at 0x7f00>")
        self.assertEqual(len(elems_of_type(doc, 'verbatim')), 1)

    def test_markdown_parsed(self):
        doc = Doc()
        self.make_loader().parse_output_data_part(doc, "text/markdown", "Hello **bold**")
        mds = elems_of_type(doc, 'markdown')
        self.assertEqual(len(mds), 1)
        self.assertIn("Hello **bold**", mds[0]['children'])

    def test_latex_parsed(self):
        doc = Doc()
        self.make_loader().parse_output_data_part(doc, "text/latex", r"\textit{Hello}")
        self.assertEqual(len(elems_of_type(doc, 'latex')), 1)
        self.assertIn(r"\textit{Hello}", content_of(doc, typ='latex'))

    def test_json_parsed(self):
        doc = Doc()
        self.make_loader().parse_output_data_part(doc, "text/json", {"b": 2, "a": 1})
        pres = content_of(doc, typ='verbatim')
        self.assertIn(json.dumps({"b": 2, "a": 1}, indent=2), pres)

    def test_png_image_parsed(self):
        doc = Doc()
        self.make_loader().parse_output_data_part(doc, "image/png", PNG_BLOB)
        images = elems_of_type(doc, 'image')
        self.assertEqual(len(images), 1)
        blob = images[0]['imageblob'].split(';base64,')[-1]
        self.assertTrue(base64.b64decode(blob).startswith(b'\x89PNG'))

    def test_jpeg_image_parsed(self):
        doc = Doc()
        self.make_loader().parse_output_data_part(doc, "image/jpeg", JPEG_BLOB)
        self.assertEqual(len(elems_of_type(doc, 'image')), 1)

    def test_image_data_as_line_list(self):
        doc = Doc()
        lines = [PNG_BLOB[i:i+40] + '\n' for i in range(0, len(PNG_BLOB), 40)]
        self.make_loader().parse_output_data_part(doc, "image/png", lines)
        self.assertEqual(len(elems_of_type(doc, 'image')), 1)

    def test_html_pre_becomes_verbatim(self):
        doc = Doc()
        self.make_loader().parse_output_data_part(doc, "text/html", "<pre>line1\nline2</pre>")
        self.assertEqual(len(elems_of_type(doc, 'verbatim')), 1)
        self.assertEqual(content_of(doc, typ='verbatim'), "line1\nline2")

    @unittest.skipUnless(can_run_pandoc(), "pandoc is not installed")
    def test_html_converted_to_markdown(self):
        doc = Doc()
        self.make_loader().parse_output_data_part(doc, "text/html", "<p>Hello HTML</p>")
        self.assertIn("Hello HTML", content_of(doc))

    def test_html_fallback_without_pandoc(self):
        doc = Doc()
        with mock.patch('pydocmaker.backend.pandoc_api.can_run_pandoc', return_value=False):
            self.make_loader().parse_output_data_part(doc, "text/html", "<p>Hello HTML</p>")
        pres = content_of(doc, typ='verbatim')
        self.assertIn("Unable to convert HTML to markdown", pres)
        self.assertIn("Hello HTML", pres)

    def test_unknown_mimetype_raises(self):
        doc = Doc()
        with self.assertRaises(ValueError):
            self.make_loader().parse_output_data_part(doc, "application/x-unknown", "data")


class TestFiltoutp(unittest.TestCase):

    def test_no_filters_includes_all(self):
        loader = IpynbLoader()
        self.assertTrue(loader._filtoutp("text/plain"))
        self.assertTrue(loader._filtoutp("image/png"))

    def test_exclude_filter(self):
        loader = IpynbLoader(exclude_output_type_filters=["text/html"])
        self.assertFalse(loader._filtoutp("text/html"))
        self.assertTrue(loader._filtoutp("text/plain"))

    def test_exclude_filter_regex(self):
        loader = IpynbLoader(exclude_output_type_filters=["image/.*"])
        self.assertFalse(loader._filtoutp("image/png"))
        self.assertTrue(loader._filtoutp("text/plain"))

    def test_include_filter(self):
        loader = IpynbLoader(include_output_type_filters=["image/.*"])
        self.assertTrue(loader._filtoutp("image/png"))
        self.assertFalse(loader._filtoutp("text/plain"))

    def test_include_and_exclude_combined(self):
        loader = IpynbLoader(include_output_type_filters=["text/.*"],
                             exclude_output_type_filters=["text/html"])
        self.assertTrue(loader._filtoutp("text/plain"))
        self.assertFalse(loader._filtoutp("text/html"))
        self.assertFalse(loader._filtoutp("image/png"))


class TestParseOutputData(unittest.TestCase):

    @unittest.skipUnless(can_run_pandoc(), "pandoc is not installed")
    def test_html_plain_pair_prefers_html(self):
        loader = IpynbLoader()
        doc = Doc()
        loader.parse_output_data({"text/html": "<p>Hi from HTML</p>",
                                  "text/plain": "<IPython.core.display.HTML object>"}, doc)
        self.assertIn("Hi from HTML", content_of(doc))
        self.assertEqual(len(elems_of_type(doc, 'verbatim')), 0)

    @unittest.skipUnless(can_run_pandoc(), "pandoc is not installed")
    def test_multiple_mimetypes_all_parsed(self):
        loader = IpynbLoader()
        doc = Doc()
        loader.parse_output_data({"text/html": "<p>Hi from HTML</p>",
                                  "text/plain": "plain text output",
                                  "image/png": PNG_BLOB}, doc)
        self.assertIn("Hi from HTML", content_of(doc))
        self.assertIn("plain text output", content_of(doc, typ='verbatim'))
        self.assertEqual(len(elems_of_type(doc, 'image')), 1)

    def test_filtering_applied(self):
        loader = IpynbLoader(exclude_output_type_filters=["text/plain"])
        doc = Doc()
        loader.parse_output_data({"text/plain": "should be excluded",
                                  "text/markdown": "**kept**"}, doc)
        self.assertNotIn("should be excluded", content_of(doc))
        self.assertIn("**kept**", content_of(doc))


class TestParseOutputError(unittest.TestCase):

    def test_error_parts_extracted(self):
        loader = IpynbLoader()
        doc = Doc()
        loader.parse_output_error({"ename": "ValueError", "evalue": "bad value",
                                   "traceback": ["\x1b[0;31mTraceback (most recent call last)\x1b[0m\n",
                                                 "\x1b[0;31mValueError\x1b[0m: bad value"]}, doc)
        self.assertIn("Execution Error:", content_of(doc, typ='markdown'))
        self.assertIn("ValueError: bad value", content_of(doc, typ='markdown'))
        tb = content_of(doc, typ='verbatim')
        self.assertIn("Traceback (most recent call last)", tb)
        self.assertNotIn("\x1b[", tb)


class TestCellParseOutput(unittest.TestCase):

    def setUp(self):
        self.loader = IpynbLoader()

    def test_stream_stdout(self):
        doc = Doc()
        self.loader.cell_parse_output(code_cell("print(1)",
                                                outputs=[{"output_type": "stream",
                                                          "name": "stdout", "text": "out line\n"}]), doc)
        self.assertEqual(content_of(doc, typ='verbatim'), "out line\n")
        self.assertEqual(elems_of_type(doc, 'verbatim')[0].get('color'), '')

    def test_stream_stderr_is_red(self):
        doc = Doc()
        self.loader.cell_parse_output(code_cell("print(1)",
                                                outputs=[{"output_type": "stream",
                                                          "name": "stderr", "text": "err line\n"}]), doc)
        self.assertEqual(content_of(doc, typ='verbatim'), "err line\n")
        self.assertEqual(elems_of_type(doc, 'verbatim')[0].get('color'), 'red')

    def test_display_data(self):
        doc = Doc()
        self.loader.cell_parse_output(code_cell("x",
                                                outputs=[{"output_type": "display_data",
                                                          "data": {"text/plain": "disp out"},
                                                          "metadata": {}}]), doc)
        self.assertEqual(content_of(doc, typ='verbatim'), "disp out")

    def test_execute_result(self):
        doc = Doc()
        self.loader.cell_parse_output(code_cell("x",
                                                outputs=[{"output_type": "execute_result",
                                                          "data": {"text/plain": "42"},
                                                          "metadata": {},
                                                          "execution_count": 1}]), doc)
        self.assertEqual(content_of(doc, typ='verbatim'), "42")

    def test_error_output(self):
        doc = Doc()
        self.loader.cell_parse_output(code_cell("1/0",
                                                outputs=[{"output_type": "error",
                                                          "ename": "ZeroDivisionError",
                                                          "evalue": "division by zero",
                                                          "traceback": []}]), doc)
        self.assertIn("ZeroDivisionError: division by zero", content_of(doc, typ='markdown'))

    def test_unknown_output_type_reported(self):
        doc = Doc()
        self.loader.cell_parse_output(code_cell("x", outputs=[{"output_type": "weird"}]), doc)
        self.assertIn("Error parsing output cell", content_of(doc, typ='verbatim'))

    def test_no_outputs_is_noop(self):
        doc = Doc()
        self.loader.cell_parse_output(code_cell("x = 1", outputs=[]), doc)
        self.assertEqual(len(doc), 0)

    def test_list_of_cells_recursed(self):
        doc = Doc()
        cells = [code_cell("x", outputs=[{"output_type": "stream", "name": "stdout", "text": "one\n"}]),
                 code_cell("y", outputs=[{"output_type": "stream", "name": "stdout", "text": "two\n"}])]
        self.loader.cell_parse_output(cells, doc)
        self.assertIn("one\n", content_of(doc, typ='verbatim'))
        self.assertIn("two\n", content_of(doc, typ='verbatim'))


class TestCellParseSource(unittest.TestCase):

    def setUp(self):
        self.loader = IpynbLoader()

    def test_markdown_cell_parsed(self):
        doc = Doc()
        self.loader.cell_parse_source(md_cell("# A heading\n\nsome *text*"), doc)
        self.assertEqual(len(elems_of_type(doc, 'markdown')), 1)
        self.assertIn("# A heading", content_of(doc))

    def test_code_cell_fenced_with_language(self):
        doc = Doc()
        self.loader.cell_parse_source(code_cell("x = 1"), doc)
        self.assertIn("```python\nx = 1\n```", content_of(doc))

    def test_code_cell_number_added(self):
        doc = Doc()
        self.loader.cell_parse_source(code_cell("x = 1", execution_count=7), doc)
        self.assertIn("Cell 7", content_of(doc))

    def test_no_cell_number_when_disabled(self):
        loader = IpynbLoader(add_cell_numbers=False)
        doc = Doc()
        loader.cell_parse_source(code_cell("x = 1", execution_count=7), doc)
        self.assertNotIn("Cell 7", content_of(doc))

    def test_code_cell_as_verbatim(self):
        loader = IpynbLoader(source_as_markdown=False)
        doc = Doc()
        loader.cell_parse_source(code_cell("x = 1"), doc)
        pres = elems_of_type(doc, 'verbatim')
        self.assertEqual(len(pres), 1)
        self.assertEqual(pres[0]['children'], "x = 1")
        self.assertEqual(pres[0]['lang'], "python")

    def test_custom_source_language(self):
        loader = IpynbLoader(source_language="julia")
        doc = Doc()
        loader.cell_parse_source(code_cell("x = 1"), doc)
        self.assertIn("```julia\nx = 1\n```", content_of(doc))

    def test_nocode_skips_code_cells(self):
        loader = IpynbLoader(nocode=True)
        doc = Doc()
        loader.cell_parse_source(code_cell("x = 1"), doc)
        self.assertEqual(len(doc), 0)

    def test_unknown_cell_type_raises(self):
        doc = Doc()
        with self.assertRaises(ValueError):
            self.loader.cell_parse_source({"cell_type": "raw", "source": "..."}, doc)


class TestLoadNotebookFunction(unittest.TestCase):

    def test_load_from_file_path(self):
        nb = make_notebook(md_cell("# Hello World"))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "my_nb.ipynb"
            p.write_text(json.dumps(nb), encoding="utf-8")
            doc = load_notebook(str(p))
        self.assertIsInstance(doc, Doc)
        self.assertIn("Hello World", content_of(doc))
        self.assertIn("Notebook name:", content_of(doc))

    def test_load_from_json_string(self):
        doc = load_notebook(json.dumps(make_notebook(md_cell("# Hello World"))))
        self.assertIn("Hello World", content_of(doc))

    def test_load_from_dict(self):
        doc = load_notebook(make_notebook(md_cell("# Hello World")))
        self.assertIn("Hello World", content_of(doc))

    def test_kwargs_forwarded(self):
        doc = load_notebook(make_notebook(code_cell("x = 1")), nocode=True)
        self.assertNotIn("x = 1", content_of(doc))


class TestIoCheckIpynb(unittest.TestCase):

    def test_valid_notebook_json(self):
        self.assertTrue(io_check_ipynb(json.dumps(make_notebook(md_cell("# Hi")))))

    def test_empty_content(self):
        self.assertFalse(io_check_ipynb(""))

    def test_none_content(self):
        self.assertFalse(io_check_ipynb(None))

    def test_non_string_content(self):
        self.assertFalse(io_check_ipynb(42))

    def test_not_json_object(self):
        self.assertFalse(io_check_ipynb("just some text"))

    def test_missing_cells_key(self):
        self.assertFalse(io_check_ipynb(json.dumps({"metadata": {}, "nbformat": 4})))


class TestIoSerializeRoundtrip(unittest.TestCase):

    def test_serialize_produces_notebook_with_payload(self):
        doc = Doc().add_md("# Hello").add_pre("some code")
        nb_json = io_serialize_ipynb(doc)
        self.assertTrue(io_check_ipynb(nb_json))
        nb = json.loads(nb_json)
        self.assertIn("pydocmaker-payload", nb["metadata"])
        self.assertEqual(nb["nbformat"], 4)

    def test_roundtrip_is_lossless(self):
        doc = Doc().add_md("# Hello").add_pre("some code").add_tex(r"\textit{Hi}")
        doc.update_meta({"title": "My Title", "author": "Jane Doe"})
        restored = load_notebook(io_serialize_ipynb(doc))
        self.assertEqual(doc.dumps(), restored.dumps())

    def test_roundtrip_example_doc_is_lossless(self):
        doc = Doc.get_example()
        restored = load_notebook(io_serialize_ipynb(doc))
        self.assertEqual(doc.dumps(), restored.dumps())

    def test_deserialize_payload(self):
        doc = Doc().add_md("# Hello").add_pre("some code")
        restored = io_deserialize_ipynb(io_serialize_ipynb(doc))
        self.assertEqual(doc.dumps(), restored.dumps())

    def test_deserialize_plain_notebook(self):
        nb = make_notebook(md_cell("# Hello"), code_cell("print(42)"))
        doc = io_deserialize_ipynb(json.dumps(nb))
        self.assertIn("Hello", content_of(doc))
        self.assertIn("print(42)", content_of(doc))

    def test_deserialize_invalid_raises(self):
        with self.assertRaises(ValueError):
            io_deserialize_ipynb("<html>no payload here</html>")

    def test_doc_load_integration(self):
        doc = Doc().add_md("# Hello").add_pre("some code")
        restored = Doc.load(io_serialize_ipynb(doc))
        self.assertEqual(doc.dumps(), restored.dumps())


if __name__ == '__main__':
    unittest.main()

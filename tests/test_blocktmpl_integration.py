import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path

_setup = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(_setup), 'src')
if _src not in sys.path:
    sys.path.insert(0, _src)

import pydocmaker as pyd
from pydocmaker import blocktmpl

try:
    import typst as _typst
    HAS_TYPST = True
except ImportError:
    HAS_TYPST = False

try:
    import bs4
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


BLOCK_TYP = """// pydocmaker:parameters:begin
// pydocmaker:param:title
#let title = "Block Report"
// pydocmaker:param:acronyms
#let acronyms = (SNR: "Signal-to-Noise Ratio")
// pydocmaker:parameters:end

#set page("a4")

#if title != none [#set document(title: title)]

#heading(level: 1)[List of Acronyms]
#for (k, v) in acronyms [#strong[#k]: #v \ ]

// pydocmaker:body:begin
placeholder text
// pydocmaker:body:end
"""

BLOCK_TEX = """\\documentclass{article}
\\begin{document}
% pydocmaker:parameters:begin
% pydocmaker:param:title
\\providecommand{\\title}{Block Report}
% pydocmaker:param:acronyms
\\newcommand{\\acronyms}{%
\\begin{description}
\\item{SNR}{Signal-to-Noise Ratio}
\\end{description}
}
% pydocmaker:parameters:end

% pydocmaker:body:begin
placeholder text
% pydocmaker:body:end
\\end{document}
"""

BLOCK_HTML = """<!DOCTYPE html>
<html>
<head>
<title>Block Report</title>
<!-- pydocmaker:parameters:begin -->
<!-- pydocmaker:param:title -->
<meta name="pydocmaker:param:title" content="Block Report">
<!-- pydocmaker:param:acronyms -->
<script type="application/json" data-pydocmaker-param="acronyms">{"SNR": "Signal-to-Noise Ratio"}</script>
<!-- pydocmaker:parameters:end -->
</head>
<body>
<!-- pydocmaker:body:begin -->
placeholder text
<!-- pydocmaker:body:end -->
</body>
</html>
"""


def _write(tmpdir, name, content):
    p = os.path.join(tmpdir, name)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(content)
    return p


class TestDocEndToEnd(unittest.TestCase):

    def setUp(self):
        self.doc = pyd.Doc().add_text('Generated Document Body')

    def test_to_typst_with_block_template(self):
        out = self.doc.to_typst(template=BLOCK_TYP, template_params={'title': 'Rendered Title'})
        self.assertIn('Generated Document Body', out)
        self.assertNotIn('placeholder text', out)
        self.assertIn('#let title = "Rendered Title"', out)
        self.assertIn('#let acronyms = (SNR: "Signal-to-Noise Ratio")', out)

    def test_to_html_with_block_template(self):
        out = self.doc.to_html(template=BLOCK_HTML, template_params={'title': 'Rendered Title'})
        self.assertIn('Generated Document Body', out)
        self.assertNotIn('placeholder text', out)
        self.assertIn('content="Rendered Title"', out)
        if HAS_BS4:
            soup = bs4.BeautifulSoup(out, 'html.parser')
            self.assertIsNotNone(soup.body)
            self.assertEqual(soup.find('meta', attrs={'name': 'pydocmaker:param:title'})['content'],
                             'Rendered Title')

    def test_to_typst_from_block_file_on_disk_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            p = _write(td, 'report.typ', BLOCK_TYP)
            before = Path(p).read_bytes()
            doc = pyd.Doc().add_text('Body From File')
            out = doc.to_typst(template=p, template_params={'title': 'T'})
            self.assertIn('Body From File', out)
            self.assertEqual(Path(p).read_bytes(), before)

    def test_to_typst_meta_stored_block_template(self):
        with tempfile.TemporaryDirectory() as td:
            p = _write(td, 'report.typ', BLOCK_TYP)
            doc = pyd.Doc().add_text('Body From Meta')
            doc.add_meta(project_name='p', version='1', description='d', author='a',
                         author_email='e', url='u', license='l')
            doc.add_meta({'template': Path(p).read_text(encoding='utf-8')})
            out = doc.to_typst()
            self.assertIn('Body From Meta', out)
            self.assertNotIn('placeholder text', out)

    def test_engine_selection_jinja2_override(self):
        out = self.doc.to_typst(template=BLOCK_TYP, template_engine='jinja2')
        self.assertIn('// pydocmaker:body:begin', out)
        self.assertIn('Generated Document Body', out)

    def test_engine_selection_blocks_on_unmarked(self):
        unmarked = '#set page("a4")\n\nPlain Source\n'
        out = self.doc.to_typst(template=unmarked, template_engine='blocks')
        self.assertIn('Generated Document Body', out)
        self.assertIn('// pydocmaker:body:begin', out)
        self.assertIn('Plain Source', out)

    def test_body_reserved_error_from_doc_api(self):
        with self.assertRaises(AssertionError):
            self.doc.to_typst(template=BLOCK_TYP, template_params={'body': 'nope'})

    def test_params_precedence_meta_then_explicit(self):
        doc = pyd.Doc().add_text('B')
        doc.add_meta(project_name='p', version='1', description='d', author='a',
                     author_email='e', url='u', license='l')
        doc.add_meta({'title': 'Meta Title'})
        out = doc.to_typst(template=BLOCK_TYP, template_params={'title': 'Explicit Title'})
        self.assertIn('#let title = "Explicit Title"', out)
        out2 = doc.to_typst(template=BLOCK_TYP)
        self.assertIn('#let title = "Meta Title"', out2)


@unittest.skipUnless(HAS_TYPST, 'typst python package not installed')
class TestStandaloneCompileTypst(unittest.TestCase):

    def test_scaffolded_template_compiles_standalone(self):
        src = blocktmpl.scaffold('#set page("a4")\n\nHello standalone\n', tformat='typ',
                                 params={'title': 'Standalone'})
        pdf = pyd.compile_with_typst(src, verb=0)
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_block_template_compiles_standalone_and_rendered(self):
        pdf_raw = pyd.compile_with_typst(BLOCK_TYP, verb=0)
        self.assertTrue(pdf_raw.startswith(b'%PDF'))
        doc = pyd.Doc().add_text('Rendered Body')
        rendered = doc.to_typst(template=BLOCK_TYP, template_params={'title': 'Compiled'})
        pdf = pyd.compile_with_typst(rendered, verb=0)
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_update_params_roundtrip_compiles(self):
        src = blocktmpl.scaffold('#set page("a4")\n\nHello\n', tformat='typ', params={'title': 'V1'})
        updated = blocktmpl.update_params(src, {'title': 'V2', 'n_iter': 3})
        pdf = pyd.compile_with_typst(updated, verb=0)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertIn('#let title = "V2"', updated)
        self.assertIn('#let n_iter = 3', updated)


class TestScaffoldUpdateDiskWorkflow(unittest.TestCase):

    def test_workflow_never_touches_file_on_render(self):
        with tempfile.TemporaryDirectory() as td:
            p = _write(td, 'doc.typ', BLOCK_TYP)
            original = Path(p).read_bytes()

            doc = pyd.Doc().add_text('Body')
            rendered = doc.to_typst(template=p)
            self.assertEqual(Path(p).read_bytes(), original)

            updated = blocktmpl.update_params(Path(p).read_text(encoding='utf-8'), {'title': 'Updated'})
            self.assertEqual(Path(p).read_bytes(), original)
            self.assertIn('#let title = "Updated"', updated)

            with open(p, 'w', encoding='utf-8') as f:
                f.write(updated)
            self.assertNotEqual(Path(p).read_bytes(), original)


@unittest.skipUnless(HAS_BS4, 'beautifulsoup4 not installed')
class TestHtmlValidation(unittest.TestCase):

    def test_jinja_markers_do_not_regress(self):
        doc = pyd.Doc().add_text('B')
        out = doc.to_html()
        soup = bs4.BeautifulSoup(out, 'html.parser')
        self.assertIsNotNone(soup.body)

    def test_block_render_valid_html(self):
        doc = pyd.Doc().add_text('B')
        out = doc.to_html(template=BLOCK_HTML, template_params={'title': 'X'})
        soup = bs4.BeautifulSoup(out, 'html.parser')
        self.assertIsNotNone(soup.body)
        self.assertIsNone(soup.find(string='placeholder text'))
        self.assertEqual(soup.find('meta', attrs={'name': 'pydocmaker:param:title'})['content'], 'X')


if __name__ == '__main__':
    unittest.main()

"""Extensive templating integration tests for pydocmaker.

These tests are OPT-IN and skipped by default so minimal test suites stay fast:

- set the environment variable ``PYDOCMAKER_TEST_TEMPLATING=1`` (or the general
  ``PYDOCMAKER_TESTFULL=1``) to include them in a run, or
- run this module directly (``python tests/test_templating_extensive.py``) or
  via ``python -m unittest tests.test_templating_extensive``.

Covered matrix:

- documents: ``pyd.Doc.get_example()`` and the repository ``README.md``
  (via ``pyd.Doc().add_md``)
- formats: html, typ, tex (string renders), pdf (typst/tex compilation),
  markdown and ipynb smoke renders
- templates: no template at all, every block template in
  ``src/pydocmaker/templates``, every legacy jinja2 ``*.j2`` template there,
  and template-definition variants (exact file name, short id + tformat,
  file path, raw source, template object, ``template_engine`` override and
  the ``set_template_to_meta`` flow)
- sanity checks: structure markers, body content presence/absence of
  placeholders, output size bounds and render-to-render size consistency
"""

import os
import sys
import unittest
from pathlib import Path

_setup = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(_setup), 'src')
if _src not in sys.path:
    sys.path.insert(0, _src)

import pydocmaker as pyd
from pydocmaker import blocktmpl, templating
from pydocmaker.backend import ex_tex, ex_typst
from pydocmaker.templating import (BlockDocTemplate, DocTemplate, TemplateDirSource,
                                   handle_template)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / 'src' / 'pydocmaker' / 'templates'
README_PATH = REPO_ROOT / 'README.md'

EXTENSIVE = True #bool(os.environ.get('PYDOCMAKER_TEST_TEMPLATING') or os.environ.get('PYDOCMAKER_TESTFULL'))

extensive = unittest.skipUnless(
    EXTENSIVE, 'extensive templating suite; opt in with PYDOCMAKER_TEST_TEMPLATING=1 or PYDOCMAKER_TESTFULL=1')

#: CI runners must not rely on a latex compiler or libreoffice being installed
IN_CI = bool(os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'))


def _latex_compiler_available():
    try:
        from pydocmaker.backend.pdf_maker_tex import config_latex_compiler_scan
        return bool(config_latex_compiler_scan())
    except Exception:
        return False


#: PDF compilation through the tex engine requires a local latex compiler;
#: in CI these tests are skipped because CI must not rely on a latex compiler
tex_pdf_compile = unittest.skipIf(
    IN_CI or not _latex_compiler_available(),
    'skipping tex PDF compilation (CI must not rely on a latex compiler)')


def _pandoc_available():
    try:
        return bool(ex_typst.can_run_pandoc())
    except Exception:
        return False


#: rendering the README (it contains remote badge images) to typst/PDF goes
#: through pandoc; CI runners have no pandoc, so those renders are skipped
needs_pandoc = unittest.skipUnless(
    _pandoc_available(), 'readme md->typst rendering needs pandoc; pandoc is not installed')

MIN_PDF_BYTES = 1000
MAX_PDF_BYTES = 10 * 1000 * 1000


def make_documents():
    """The two documents under test, keyed by a short name for subTest labels."""
    return {
        'example': pyd.Doc.get_example(),
        'readme': pyd.Doc().add_md(README_PATH.read_text(encoding='utf-8')),
    }


def block_template_names():
    """All block (comment-delimited) template file names in the templates folder."""
    return sorted(TemplateDirSource(None).get_block_templates().keys())


def jinja_template_names():
    """All legacy jinja2 template file names in the templates folder."""
    return sorted(TemplateDirSource(None).get_templates().keys())


#: legacy templates that need parameters to render compilable output
JINJA_TEMPLATE_PARAMS = {
    'paper.typ.j2': {
        'title': 'Paper Title',
        'authors': [{'name': 'A. Author', 'affiliation': 'Uni', 'email': 'a@b.c'}],
    },
}


def template_format(name):
    """Map a template file name to its document format ('tex' | 'typ' | 'html')."""
    base = name[:-3] if name.endswith('.j2') else name
    if base.endswith('.tex'):
        return 'tex'
    if base.endswith('.typ'):
        return 'typ'
    if base.endswith('.html'):
        return 'html'
    return None


def assert_valid_pdf(testcase, pdf):
    testcase.assertIsInstance(pdf, bytes)
    testcase.assertTrue(pdf.startswith(b'%PDF'))
    testcase.assertGreater(len(pdf), MIN_PDF_BYTES)
    testcase.assertLess(len(pdf), MAX_PDF_BYTES)


def assert_pdf_size_consistent(testcase, pdf_a, pdf_b, tol=0.05):
    testcase.assertTrue(pdf_a.startswith(b'%PDF') and pdf_b.startswith(b'%PDF'))
    bigger = max(len(pdf_a), len(pdf_b))
    testcase.assertLess(abs(len(pdf_a) - len(pdf_b)), tol * bigger,
                        f'pdf sizes diverged: {len(pdf_a)} vs {len(pdf_b)}')


BLOCK_MARKER_BY_FORMAT = {
    'html': '<!-- pydocmaker:body:begin -->',
    'tex': '% pydocmaker:body:begin',
    'typ': '// pydocmaker:body:begin',
}


@extensive
class TestRenderWithoutTemplate(unittest.TestCase):
    """Render both documents in all formats without stating any template."""

    def test_html_without_template(self):
        for doc_name, doc in make_documents().items():
            with self.subTest(doc=doc_name):
                out = doc.to_html()
                self.assertIsInstance(out, str)
                self.assertGreater(len(out), 1000)
                self.assertIn('</html>', out)
                self.assertIn('<body', out.lower())

    def test_typst_without_template(self):
        for doc_name, doc in make_documents().items():
            with self.subTest(doc=doc_name):
                out = doc.to_typst()
                self.assertIsInstance(out, str)
                self.assertGreater(len(out), 500)
                self.assertNotIn('{{', out)

    def test_tex_without_template(self):
        for doc_name, doc in make_documents().items():
            with self.subTest(doc=doc_name):
                out = doc.to_tex(text_only=True)
                self.assertIsInstance(out, str)
                self.assertIn(r'\documentclass', out)
                self.assertIn(r'\end{document}', out)
                self.assertGreater(len(out), 1000)

    def test_markdown_and_ipynb_smoke(self):
        for doc_name, doc in make_documents().items():
            with self.subTest(doc=doc_name, fmt='markdown'):
                out = doc.to_markdown()
                self.assertIsInstance(out, str)
                self.assertGreater(len(out), 100)
            with self.subTest(doc=doc_name, fmt='ipynb'):
                out = doc.to_ipynb()
                self.assertIsInstance(out, str)
                self.assertIn('"cells"', out)

    def test_pdf_without_template(self):
        for doc_name, doc in make_documents().items():
            if doc_name == 'readme' and not _pandoc_available():
                continue  # readme md->typst (badge images) needs pandoc
            with self.subTest(doc=doc_name):
                pdf = doc.to_pdf(verb=0)
                assert_valid_pdf(self, pdf)


@extensive
class TestRenderWithBlockTemplates(unittest.TestCase):
    """Render both documents with every block template in the templates folder."""

    def test_html_with_html_block_templates(self):
        for doc_name, doc in make_documents().items():
            for tname in block_template_names():
                if template_format(tname) != 'html':
                    continue
                with self.subTest(doc=doc_name, template=tname):
                    out = doc.to_html(template=tname)
                    self.assertIn(BLOCK_MARKER_BY_FORMAT['html'], out)
                    self.assertNotIn('Document body placeholder', out)
                    self.assertIn('</html>', out)
                    self.assertGreater(len(out), 2000)

    def test_typst_with_typ_block_templates(self):
        for doc_name, doc in make_documents().items():
            for tname in block_template_names():
                if template_format(tname) != 'typ':
                    continue
                with self.subTest(doc=doc_name, template=tname):
                    out = doc.to_typst(template=tname)
                    self.assertIn(BLOCK_MARKER_BY_FORMAT['typ'], out)
                    self.assertNotIn('Document body placeholder', out)
                    self.assertIn('#let pTitle', out)
                    self.assertGreater(len(out), 2000)

    def test_tex_with_tex_block_templates(self):
        for doc_name, doc in make_documents().items():
            for tname in block_template_names():
                if template_format(tname) != 'tex':
                    continue
                with self.subTest(doc=doc_name, template=tname):
                    out = doc.to_tex(text_only=True, template=tname)
                    self.assertIn(BLOCK_MARKER_BY_FORMAT['tex'], out)
                    self.assertNotIn('Document body placeholder', out)
                    self.assertIn(r'\providecommand{\pTitle}', out)
                    self.assertIn(r'\end{document}', out)

    def test_pdf_with_typ_block_templates(self):
        for doc_name, doc in make_documents().items():
            if doc_name == 'readme' and not _pandoc_available():
                continue  # readme md->typst (badge images) needs pandoc
            for tname in block_template_names():
                if template_format(tname) != 'typ':
                    continue
                with self.subTest(doc=doc_name, template=tname):
                    base_dir = str(REPO_ROOT) if doc_name == 'readme' else None
                    kw = {'base_dir': base_dir} if base_dir else {}
                    pdf = doc.to_pdf(template=tname, engine='typst', verb=0, **kw)
                    assert_valid_pdf(self, pdf)

    @tex_pdf_compile
    def test_pdf_with_tex_block_templates(self):
        for doc_name, doc in make_documents().items():
            for tname in block_template_names():
                if template_format(tname) != 'tex':
                    continue
                with self.subTest(doc=doc_name, template=tname):
                    pdf = doc.to_pdf(template=tname, engine='tex', verb=0)
                    assert_valid_pdf(self, pdf)

    def test_pdf_with_html_block_template_raises(self):
        doc = pyd.Doc().add_text('Engine mismatch probe')
        html_source = (TEMPLATES_DIR / 'base.html').read_text(encoding='utf-8')
        with self.assertRaises(ValueError):
            doc.to_pdf(template=html_source, verb=0)

    def test_block_defaults_present_in_output(self):
        doc = pyd.Doc().add_text('Defaults probe')
        out = doc.to_typst(template='base.typ')
        self.assertIn('#let pTitle = "My Report"', out)

    def test_tex_block_defaults_with_latex_macros_survive(self):
        """Template defaults containing LaTeX macros (e.g. ``\\today``) must
        survive the render (no double escaping through the meta round-trip)."""
        doc = pyd.Doc().add_text('Defaults probe')
        doc.set_template_to_meta('base.tex', on_exist='overwrite')
        out = doc.to_tex(text_only=True)
        self.assertIn(r'\providecommand{\pTitle}{My Report}', out)
        self.assertIn(r'\providecommand{\pDate}{\today}', out)
        self.assertNotIn('textbackslash', out)


@extensive
class TestRenderWithJinjaTemplates(unittest.TestCase):
    """Render both documents with every legacy jinja2 template in the templates folder.

    Note: the README body itself contains literal ``pydocmaker:`` marker strings
    (in its code examples), so engine-distinction assertions via marker absence
    are only made for the example document.
    """

    def test_html_with_html_jinja_templates(self):
        for doc_name, doc in make_documents().items():
            for tname in jinja_template_names():
                if template_format(tname) != 'html':
                    continue
                with self.subTest(doc=doc_name, template=tname):
                    out = doc.to_html(template=tname)
                    if doc_name == 'example':
                        self.assertNotIn('pydocmaker:body:begin', out)
                    self.assertIn('</html>', out)
                    self.assertGreater(len(out), 2000)

    def test_typst_with_typ_jinja_templates(self):
        for doc_name, doc in make_documents().items():
            for tname in jinja_template_names():
                if template_format(tname) != 'typ':
                    continue
                with self.subTest(doc=doc_name, template=tname):
                    out = doc.to_typst(template=tname, template_params=JINJA_TEMPLATE_PARAMS.get(tname))
                    if doc_name == 'example':
                        self.assertNotIn('pydocmaker:body:begin', out)
                    self.assertGreater(len(out), 2000)

    def test_tex_with_tex_jinja_templates(self):
        for doc_name, doc in make_documents().items():
            for tname in jinja_template_names():
                if template_format(tname) != 'tex':
                    continue
                with self.subTest(doc=doc_name, template=tname):
                    out = doc.to_tex(text_only=True, template=tname)
                    if doc_name == 'example':
                        self.assertNotIn('pydocmaker:body:begin', out)
                    self.assertIn(r'\end{document}', out)

    def test_pdf_with_typ_jinja_templates(self):
        for doc_name, doc in make_documents().items():
            if doc_name == 'readme' and not _pandoc_available():
                continue  # readme md->typst (badge images) needs pandoc
            for tname in jinja_template_names():
                if template_format(tname) != 'typ':
                    continue
                with self.subTest(doc=doc_name, template=tname):
                    base_dir = str(REPO_ROOT) if doc_name == 'readme' else None
                    kw = {'base_dir': base_dir} if base_dir else {}
                    pdf = doc.to_pdf(template=tname, verb=0,
                                     template_params=JINJA_TEMPLATE_PARAMS.get(tname), **kw)
                    assert_valid_pdf(self, pdf)

    @tex_pdf_compile
    def test_pdf_with_tex_jinja_templates(self):
        for doc_name, doc in make_documents().items():
            for tname in jinja_template_names():
                if template_format(tname) != 'tex':
                    continue
                with self.subTest(doc=doc_name, template=tname):
                    pdf = doc.to_pdf(template=tname, engine='tex', verb=0)
                    assert_valid_pdf(self, pdf)


@extensive
class TestTemplateDefinitionVariants(unittest.TestCase):
    """Vary how the template is stated: exact name, short id + tformat, path,
    raw source, template object, engine override and the meta flow."""

    def setUp(self):
        self.doc = pyd.Doc().add_text('Variant body content')
        self.typ_source = (TEMPLATES_DIR / 'base.typ').read_text(encoding='utf-8')

    def test_exact_name_vs_path_vs_source_vs_object(self):
        via_exact = self.doc.to_typst(template='base.typ')
        via_path = self.doc.to_typst(template=str(TEMPLATES_DIR / 'base.typ'))
        via_source = self.doc.to_typst(template=self.typ_source)
        via_object = self.doc.to_typst(template=BlockDocTemplate(self.typ_source, tformat='typ'))
        for label, out in (('exact', via_exact), ('path', via_path),
                           ('source', via_source), ('object', via_object)):
            with self.subTest(variant=label):
                self.assertIn('Variant body content', out)
                self.assertIn('#let pTitle = "My Report"', out)
                self.assertIn('// pydocmaker:body:begin', out)
        self.assertEqual(via_exact, via_path)
        self.assertEqual(via_exact, via_source)

    def test_template_id_resolution_variants(self):
        # exact file names force the specific file
        self.assertEqual(templating.TemplateDirSource(None).resolve_template_id('base.typ'), 'base.typ')
        self.assertEqual(templating.TemplateDirSource(None).resolve_template_id('base.tex'), 'base.tex')
        self.assertEqual(templating.TemplateDirSource(None).resolve_template_id('base.typ.j2'), 'base.typ.j2')

        # exact-name lookups produce the matching engine
        block_template = DocTemplate.from_tid('base', tformat='.typ')
        self.assertIsInstance(block_template, BlockDocTemplate)
        self.assertEqual(block_template.template_id, 'base.typ')
        self.assertIsInstance(DocTemplate.from_tid('base', tformat='.tex'), BlockDocTemplate)
        self.assertIsInstance(DocTemplate.from_tid('report', tformat='.typ'), BlockDocTemplate)

        # short id without format: multiple variants resolve by priority (typ first)
        multi_variant = DocTemplate.from_tid('base', tformat='')
        self.assertIsInstance(multi_variant, BlockDocTemplate)
        report_variant = DocTemplate.from_tid('report', tformat='')
        self.assertIsInstance(report_variant, BlockDocTemplate)

        # every variant renders the document body
        for label, template in (('multi', multi_variant), ('report', report_variant),
                                ('block-exact', block_template)):
            with self.subTest(variant=label):
                out = self.doc.to_typst(template=template.template)
                self.assertIn('Variant body content', out)

    def test_backend_short_id_uses_tformat_filter(self):
        out_j = ex_typst.convert(self.doc.dump(), template='base')
        self.assertIn('Variant body content', out_j)

        out_b = ex_typst.convert(self.doc.dump(), template='base.typ')
        self.assertIn('pydocmaker:body:begin', out_b)
        self.assertIn('Variant body content', out_b)

        out_t = ex_tex.convert(self.doc.dump(), template='base', with_attachments=False)
        self.assertIn('Variant body content', out_t)

        out_bt = ex_tex.convert(self.doc.dump(), template='base.tex', with_attachments=False)
        self.assertIn('pydocmaker:body:begin', out_bt)

    def test_template_engine_overrides(self):
        unmarked = '#set page("a4")\nplain unmarked source\n'
        out_blocks = self.doc.to_typst(template=unmarked, template_engine='blocks')
        self.assertIn('pydocmaker:body:begin', out_blocks)
        self.assertIn('plain unmarked source', out_blocks)

        out_jinja = self.doc.to_typst(template=self.typ_source, template_engine='jinja2')
        self.assertIn('pydocmaker:body:begin', out_jinja)
        self.assertIn('Variant body content', out_jinja)

        out_html = self.doc.to_html(template=self.typ_source, template_engine='jinja2')
        self.assertIn('pydocmaker:body:begin', out_html)

    def test_set_template_to_meta_flow(self):
        doc = pyd.Doc().add_text('Meta flow body')
        doc.set_template_to_meta('report', tformat='.typ',
                                 template_params={'pTitle': 'Meta Title', 'pHideToc': True})
        out = doc.to_typst()
        self.assertIn('#let pTitle = "Meta Title"', out)
        self.assertIn('#let pHideToc = true', out)
        self.assertIn('Meta flow body', out)
        assert_valid_pdf(self, doc.to_pdf(verb=0))

    def test_set_template_to_meta_with_short_id_and_dotless_format(self):
        doc = pyd.Doc().add_text('Dotless flow body')
        doc.set_template_to_meta('report', tformat='typ', template_params={'pTitle': 'Dotless Title'})
        out = doc.to_typst()
        self.assertIn('#let pTitle = "Dotless Title"', out)

    def test_meta_params_flow_into_block_template(self):
        doc = pyd.Doc().add_text('Params body')
        doc.add_meta({'pTitle': 'From Meta', 'pAcronyms': {'SNR': 'Signal-to-Noise Ratio'}})
        out = doc.to_typst(template='base.typ')
        self.assertIn('#let pTitle = "From Meta"', out)
        self.assertIn('#let pAcronyms = (SNR: "Signal-to-Noise Ratio")', out)
        self.assertIn('Params body', out)

    def test_to_pdf_id_path_and_auto_inference(self):
        pdf_id = self.doc.to_pdf(template='base.typ', engine='typst', verb=0)
        pdf_path = self.doc.to_pdf(template=str(TEMPLATES_DIR / 'base.typ'), verb=0)
        assert_valid_pdf(self, pdf_id)
        assert_valid_pdf(self, pdf_path)
        assert_pdf_size_consistent(self, pdf_id, pdf_path)

    @needs_pandoc
    def test_readme_with_report_block_template_like_create_readme_pdf(self):
        doc = pyd.Doc().add_md(README_PATH.read_text(encoding='utf-8'))
        doc.set_template_to_meta('report', tformat='.typ', template_params={
            'pTitle': 'Extensive Suite Title',
            'pSubtitle': 'rendered by the extensive templating tests',
            'pAuthor': 'pydocmaker test suite',
            'pAcronyms': {},
            'pApplicables': {},
            'pReferences': {},
        })
        out = doc.to_typst()
        self.assertIn('#let pTitle = "Extensive Suite Title"', out)
        self.assertIn('rendered by the extensive templating tests', out)
        pdf = doc.to_pdf(base_dir=str(REPO_ROOT), verb=0)
        assert_valid_pdf(self, pdf)


@extensive
class TestRenderedDocumentSanity(unittest.TestCase):
    """Cross-cutting sanity checks on sizes and structural properties."""

    def test_block_and_jinja_renders_same_order_of_magnitude(self):
        doc = pyd.Doc().add_text('Sanity size comparison body')
        out_block = doc.to_typst(template='base.typ')
        out_jinja = doc.to_typst(template='base.typ.j2')
        # the block render additionally carries the parameters block (defaults
        # serialized as native assignments), so it is legitimately larger
        self.assertIn('Sanity size comparison body', out_block)
        self.assertIn('Sanity size comparison body', out_jinja)
        ratio = max(len(out_block), len(out_jinja)) / max(1, min(len(out_block), len(out_jinja)))
        self.assertLess(ratio, 5.0, f'render sizes diverge: {len(out_block)} vs {len(out_jinja)}')

    def test_html_render_larger_than_markdown_for_readme(self):
        doc = pyd.Doc().add_md(README_PATH.read_text(encoding='utf-8'))
        md = doc.to_markdown()
        html = doc.to_html()
        self.assertGreater(len(html), len(md))

    def test_repeated_pdf_render_is_consistent(self):
        doc = pyd.Doc.get_example()
        pdf_a = doc.to_pdf(template='base.typ', engine='typst', verb=0)
        pdf_b = doc.to_pdf(template='base.typ', engine='typst', verb=0)
        assert_pdf_size_consistent(self, pdf_a, pdf_b)

    def test_block_template_params_roundtrip_in_rendered_output(self):
        source = (TEMPLATES_DIR / 'base.typ').read_text(encoding='utf-8')
        updated = blocktmpl.update_params(source, {'pTitle': 'Roundtrip Title', 'pDate': '2026-01-01'})
        doc = pyd.Doc().add_text('Roundtrip body')
        out = doc.to_typst(template=updated)
        self.assertIn('#let pTitle = "Roundtrip Title"', out)
        self.assertIn('#let pDate = "2026-01-01"', out)
        self.assertIn('Roundtrip body', out)
        self.assertEqual(blocktmpl.update_params(updated, {'pTitle': 'Roundtrip Title', 'pDate': '2026-01-01'}), updated)


if __name__ == '__main__':
    unittest.main()

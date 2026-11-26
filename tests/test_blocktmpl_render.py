import json
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
from pydocmaker import templating
from pydocmaker.templating import (handle_template, TemplateDirSource, DocTemplate,
                                   BlockDocTemplate, register_new_template_dir,
                                   remove_from_template_dir)

MARKED_TYP = """// pydocmaker:parameters:begin
// pydocmaker:param:title
#let title = "Block Default Title"
// pydocmaker:parameters:end

#set page("a4")

// pydocmaker:body:begin
placeholder text
// pydocmaker:body:end
"""

MARKED_TEX = """\\documentclass{article}
\\begin{document}
% pydocmaker:parameters:begin
% pydocmaker:param:title
\\providecommand{\\title}{Block Default Title}
% pydocmaker:parameters:end
% pydocmaker:body:begin
placeholder text
% pydocmaker:body:end
\\end{document}
"""

MARKED_HTML = """<!DOCTYPE html>
<html>
<head>
<!-- pydocmaker:parameters:begin -->
<!-- pydocmaker:param:title -->
<meta name="pydocmaker:param:title" content="Block Default Title">
<!-- pydocmaker:parameters:end -->
</head>
<body>
<!-- pydocmaker:body:begin -->
placeholder text
<!-- pydocmaker:body:end -->
</body>
</html>
"""


class _TempTemplateDirMixin:
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.template_dir = self._tmp.name
        self._registered = register_new_template_dir(self.template_dir)
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(remove_from_template_dir, self.template_dir)

    def write_template(self, name, content):
        p = os.path.join(self.template_dir, name)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(content)
        return p


class TestHandleTemplateSelection(unittest.TestCase):

    def test_auto_selects_block_engine_for_marked_source(self):
        template_obj, attachments, template_str = handle_template(MARKED_TYP, None, tformat='typ')
        self.assertIsInstance(template_obj, BlockDocTemplate)
        self.assertEqual(template_obj.tformat, 'typ')
        self.assertEqual(template_obj.params.get('title'), 'Block Default Title')

    def test_auto_keeps_jinja_for_unmarked_source(self):
        template_obj, attachments, template_str = handle_template('{{ body }}', None, tformat='typ')
        self.assertNotIsInstance(template_obj, BlockDocTemplate)
        self.assertTrue(hasattr(template_obj, 'render'))

    def test_jinja2_override_ignores_markers(self):
        with self.assertLogs('pydocmaker', level='WARNING'):
            template_obj, attachments, template_str = handle_template(MARKED_TYP, None, tformat='typ',
                                                                      template_engine='jinja2')
        self.assertNotIsInstance(template_obj, BlockDocTemplate)
        rendered = template_obj.render(body='B', title='T')
        self.assertIn('// pydocmaker:body:begin', rendered)
        self.assertIn('B', rendered)

    def test_blocks_override_scaffolds_unmarked_source(self):
        template_obj, attachments, template_str = handle_template('#set page("a4")\nHello\n', None, tformat='typ',
                                                                  template_engine='blocks')
        self.assertIsInstance(template_obj, BlockDocTemplate)
        rendered = template_obj.render(body='B')
        self.assertIn('Hello', rendered)
        self.assertIn('// pydocmaker:body:begin', rendered)
        self.assertIn('B', rendered)

    def test_blocks_override_uses_marked_source_as_is(self):
        template_obj, _, template_str = handle_template(MARKED_TYP, None, tformat='typ',
                                                        template_engine='blocks')
        self.assertIsInstance(template_obj, BlockDocTemplate)
        self.assertEqual(template_str, MARKED_TYP)

    def test_invalid_engine_raises(self):
        with self.assertRaises(ValueError):
            handle_template(MARKED_TYP, None, tformat='typ', template_engine='nonsense')

    def test_marked_file_path_uses_block_engine(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'tpl.typ')
            with open(p, 'w', encoding='utf-8') as f:
                f.write(MARKED_TYP)
            template_obj, _, template_str = handle_template(p, None, tformat='typ')
            self.assertIsInstance(template_obj, BlockDocTemplate)
            self.assertEqual(template_obj.template_id, 'tpl.typ')
            self.assertEqual(template_obj.params.get('title'), 'Block Default Title')

    def test_default_template_routes_to_block_engine(self):
        default = getattr(pyd.backend.ex_typst, '__default_template')
        template_obj, _, template_str = handle_template(None, default, tformat='typ')
        self.assertIsInstance(template_obj, BlockDocTemplate)
        rendered = template_obj.render(body='DEFAULT BODY CONTENT')
        self.assertIn('DEFAULT BODY CONTENT', rendered)
        self.assertIn('// pydocmaker:body:begin', rendered)


class TestTemplateDirSourceBlocks(_TempTemplateDirMixin, unittest.TestCase):

    def test_get_block_templates(self):
        self.write_template('btex.tex', MARKED_TEX)
        self.write_template('btyp.typ', MARKED_TYP)
        self.write_template('bhtml.html', MARKED_HTML)
        self.write_template('plain.typ', '#set page("a4")\nno markers\n')
        tds = TemplateDirSource(self.template_dir)
        blocks = tds.get_block_templates()
        self.assertEqual(set(blocks.keys()), {'btex.tex', 'btyp.typ', 'bhtml.html'})
        self.assertIsInstance(blocks['btyp.typ'], BlockDocTemplate)
        self.assertEqual(blocks['btyp.typ'].params.get('title'), 'Block Default Title')

    def test_block_exclusions(self):
        self.write_template('block_skip.tex', MARKED_TEX)
        self.write_template('.hidden.tex', MARKED_TEX)
        self.write_template('plain.tex.j2', '{{ body }}')
        tds = TemplateDirSource(self.template_dir)
        self.assertEqual(tds.get_block_templates(), {})

    def test_tformat_filter(self):
        self.write_template('btyp.typ', MARKED_TYP)
        self.write_template('btex.tex', MARKED_TEX)
        tds = TemplateDirSource(self.template_dir, tformat='typ')
        self.assertEqual(set(tds.get_block_templates().keys()), {'btyp.typ'})

    def test_exact_name_wins_over_short_id(self):
        self.write_template('base.tex', MARKED_TEX)
        self.write_template('base.tex.j2', 'JINJA {{ body }}')
        tds = TemplateDirSource(self.template_dir)
        self.assertEqual(tds.resolve_template_id('base.tex'), 'base.tex')
        self.assertEqual(tds.resolve_template_id('base'), 'base.tex.j2')
        self.assertIsInstance(tds.get('base.tex'), BlockDocTemplate)
        self.assertNotIsInstance(tds.get('base'), BlockDocTemplate)

    def test_short_id_resolves_block_when_no_jinja_twin(self):
        self.write_template('only.tex', MARKED_TEX)
        tds = TemplateDirSource(self.template_dir)
        self.assertEqual(tds.resolve_template_id('only'), 'only.tex')
        self.assertIsInstance(tds.get('only'), BlockDocTemplate)

    def test_get_template_ids_union(self):
        self.write_template('base.tex', MARKED_TEX)
        self.write_template('base.tex.j2', 'JINJA {{ body }}')
        self.write_template('other.typ', MARKED_TYP)
        tds = TemplateDirSource(self.template_dir)
        ids = set(tds.get_template_ids())
        self.assertEqual(ids, {'base', 'other'})

    def test_get_params_from_block(self):
        self.write_template('btex.tex', MARKED_TEX)
        tds = TemplateDirSource(self.template_dir)
        params = tds.get_params('btex.tex')
        self.assertEqual(params, {'title': 'Block Default Title'})

    def test_params_json_stays_authoritative(self):
        self.write_template('btex.tex', MARKED_TEX)
        with open(os.path.join(self.template_dir, 'btex.params.json'), 'w') as f:
            json.dump({'title': 'From JSON'}, f)
        tds = TemplateDirSource(self.template_dir)
        self.assertEqual(tds.get_params('btex.tex'), {'title': 'From JSON'})

    def test_from_tid_returns_block_template(self):
        self.write_template('btex.tex', MARKED_TEX)
        t = DocTemplate.from_tid('btex', tformat='tex', template_dir=self.template_dir)
        self.assertIsInstance(t, BlockDocTemplate)
        self.assertEqual(t.template_id, 'btex.tex')
        self.assertEqual(t.tformat, 'tex')
        self.assertEqual(t.params, {'title': 'Block Default Title'})
        self.assertEqual(t.attachments, {})

    def test_from_tid_jinja_unchanged(self):
        self.write_template('jbase.tex.j2', 'J {{ body }}')
        t = DocTemplate.from_tid('jbase', tformat='tex', template_dir=self.template_dir)
        self.assertNotIsInstance(t, BlockDocTemplate)
        self.assertIsInstance(t, DocTemplate)


class TestBlockDocTemplateDuckTyping(unittest.TestCase):

    def test_attributes(self):
        bt = BlockDocTemplate(MARKED_TEX, template_id='x.tex')
        self.assertEqual(bt.template, MARKED_TEX)
        self.assertEqual(bt.params, {'title': 'Block Default Title'})
        self.assertEqual(bt.attachments, {})
        self.assertEqual(bt.tformat, 'tex')
        self.assertEqual(bt.template_id, 'x.tex')
        self.assertIsNone(bt.env)

    def test_render_pops_body(self):
        bt = BlockDocTemplate(MARKED_TEX)
        out = bt.render(body='NEW BODY')
        self.assertIn('NEW BODY', out)
        self.assertNotIn('placeholder text', out)
        self.assertIn('\\providecommand{\\title}{Block Default Title}', out)

    def test_render_body_reserved_in_params(self):
        bt = BlockDocTemplate(MARKED_TEX, params={'body': 'x'})
        with self.assertRaises(pyd.blocktmpl.BodyReservedError):
            bt.render(body='B')

    def test_params_precedence(self):
        bt = BlockDocTemplate(MARKED_TEX)
        out = bt.render(body='B', title='Explicit Title')
        self.assertIn('\\providecommand{\\title}{Explicit Title}', out)
        self.assertNotIn('Block Default Title', out)

    def test_undefined_params_dropped(self):
        from jinja2 import Undefined
        bt = BlockDocTemplate(MARKED_TEX)
        out = bt.render(body='B', title=Undefined('title'))
        self.assertIn('\\providecommand{\\title}{Block Default Title}', out)

    def test_jinja_doc_template_render_guard(self):
        dt = DocTemplate(MARKED_TEX, params={}, template_id='m.tex')
        out = dt.render(body='B')
        self.assertIn('B', out)
        self.assertNotIn('placeholder text', out)
        self.assertIn('\\end{document}', out)


class TestBackendConvertKwargs(_TempTemplateDirMixin, unittest.TestCase):

    def test_ex_typst_convert_block(self):
        from pydocmaker.backend import ex_typst
        doc = pyd.Doc().add_text('Hello Block')
        out = ex_typst.convert(doc.dump(), template=MARKED_TYP, template_params={'title': 'T'})
        self.assertIn('Hello Block', out)
        self.assertNotIn('placeholder text', out)
        self.assertIn('#let title = "T"', out)

    def test_ex_html_convert_block(self):
        from pydocmaker.backend import ex_html
        doc = pyd.Doc().add_text('Hello Block')
        out = ex_html.convert(doc.dump(), template=MARKED_HTML, template_params={'title': 'T'})
        self.assertIn('Hello Block', out)
        self.assertNotIn('placeholder text', out)
        self.assertIn('content="T"', out)

    def test_ex_tex_convert_block(self):
        from pydocmaker.backend import ex_tex
        doc = pyd.Doc().add_text('Hello Block')
        out = ex_tex.convert(doc.dump(), template=MARKED_TEX, template_params={'title': 'T'}, with_attachments=False)
        self.assertIn('Hello Block', out)
        self.assertNotIn('placeholder text', out)
        self.assertIn('\\providecommand{\\title}{T}', out)


if __name__ == '__main__':
    unittest.main()

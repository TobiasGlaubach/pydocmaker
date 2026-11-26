import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure the local source directory is imported, not the installed package.
_setup = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(_setup), 'src')
if _src not in sys.path:
    sys.path.insert(0, _src)

from pydocmaker import templating
from jinja2 import Environment

# Resolve template dir relative to this test file's project, not the installed package.
_TEST_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'pydocmaker', 'templates')
_DEFAULT_TEMPLATE_DIR = os.path.abspath(_TEST_SRC)


class TestFindUndeclaredVariables(unittest.TestCase):
    """Tests for TemplateDirSource.find_undeclared_variables."""

    def _make_source(self, template_dir=None):
        source_obj = templating.TemplateDirSource(template_dir)
        return source_obj.find_undeclared_variables

    def test_str_filename_resolved_from_env(self):
        source = self._make_source(_DEFAULT_TEMPLATE_DIR)
        result = source("base.tex")
        self.assertIn("pTitle", result)
        self.assertIn("body", result)
        self.assertIn("pApplicables", result)

    def test_str_filename_with_jinja2_extension(self):
        source = self._make_source(_DEFAULT_TEMPLATE_DIR)
        result = source("base.tex.j2")
        self.assertIn("title", result)
        self.assertIn("body", result)

    def test_str_stripped_plain_filename(self):
        source = self._make_source(_DEFAULT_TEMPLATE_DIR)
        result = source("  base.html  ")
        self.assertIn("pTitle", result)
        self.assertIn("body", result)
        self.assertNotIn("  ", result)

    def test_raw_jinja2_source_string(self):
        source = self._make_source(_DEFAULT_TEMPLATE_DIR)
        tmpl_str = "{{ name }}{% if active %}yes{% endif %}{% for item in items %}{{ item }}{% endfor %}"
        result = source(tmpl_str)
        self.assertEqual(result, {"name", "active", "items"})

    def test_template_object_from_string_raises(self):
        """Templates created via from_string() have no recoverable source."""
        source = self._make_source(_DEFAULT_TEMPLATE_DIR)
        env = Environment()
        tmpl = env.from_string("{% if show %}{{ value }}{% endif %}{{ other }}")
        with self.assertRaises(ValueError):
            source(tmpl)

    def test_template_object_from_file(self):
        source = self._make_source(_DEFAULT_TEMPLATE_DIR)
        tds = templating.TemplateDirSource(_DEFAULT_TEMPLATE_DIR)
        tmpl = tds.get_templates()["base.tex.j2"]
        result = source(tmpl)
        self.assertIn("title", result)
        self.assertIn("body", result)

    def test_path_object(self):
        source = self._make_source(_DEFAULT_TEMPLATE_DIR)
        result = source(Path(_DEFAULT_TEMPLATE_DIR) / "base.html.j2")
        self.assertIn("title", result)
        self.assertIn("body", result)

    def test_unknown_str_treated_as_raw_source(self):
        source = self._make_source(_DEFAULT_TEMPLATE_DIR)
        result = source("{{ foo }}")
        self.assertEqual(result, {"foo"})

    def test_empty_template(self):
        source = self._make_source(_DEFAULT_TEMPLATE_DIR)
        result = source("")
        self.assertEqual(result, set())

    def test_plain_text_no_variables(self):
        source = self._make_source(_DEFAULT_TEMPLATE_DIR)
        result = source("Hello, this is plain text with no variables.")
        self.assertEqual(result, set())

    def test_invalid_type_raises_int(self):
        source = self._make_source(_DEFAULT_TEMPLATE_DIR)
        with self.assertRaises(TypeError):
            source(12345)

    def test_invalid_type_raises_list(self):
        source = self._make_source(_DEFAULT_TEMPLATE_DIR)
        with self.assertRaises(TypeError):
            source(["not", "a", "template"])


MARKED_TEX_SOURCE = """\\documentclass{article}
\\begin{document}
% pydocmaker:parameters:begin
% pydocmaker:param:title
\\providecommand{\\title}{Block Default}
% pydocmaker:parameters:end
% pydocmaker:body:begin
placeholder text
% pydocmaker:body:end
\\end{document}
"""


class TestFromTidEquivalence(unittest.TestCase):
    """DocTemplate.from_tid loads only the resolved template's params/assets.

    These tests compare the optimized from_tid against a reference copy of the
    previous get_all()-based implementation so return semantics stay identical.
    """

    def _reference_from_tid(self, template_id, tformat='', template_dir=None):
        # oracle: the pre-optimization implementation (loads everything via
        # get_all() and indexes into the full dicts)
        t = templating.TemplateDirSource(template_dir)
        err = None
        for cand in templating._candidate_template_ids(template_id, tformat):
            try:
                template_id = t.resolve_template_id(cand)
                break
            except KeyError as e:
                err = e
        else:
            raise err
        templates, params, attachments_all = t.get_all()
        attch = {**attachments_all[''], **attachments_all[template_id]}
        template, params = templates[template_id], params[template_id]
        if isinstance(template, templating.BlockDocTemplate):
            return templating.BlockDocTemplate(template.template, params=params,
                                               attachments=attch, tformat=None,
                                               template_id=template_id)
        return templating.DocTemplate(template, params, attch, t.env, template_id)

    def _assert_same_template(self, a, b):
        self.assertEqual(type(a), type(b))
        self.assertEqual(a.template_id, b.template_id)
        self.assertEqual(a.params, b.params)
        self.assertEqual(a.attachments, b.attachments)
        if isinstance(a, templating.BlockDocTemplate):
            self.assertEqual(a.template, b.template)
            self.assertEqual(a.tformat, b.tformat)
        else:
            self.assertEqual(a.template.name, b.template.name)
            self.assertEqual(templating.get_template_source(a.template),
                             templating.get_template_source(b.template))

    def test_block_templates_all_formats_on_default_dir(self):
        for tformat in ('tex', 'typ', 'html', ''):
            with self.subTest(tformat=tformat):
                got = templating.DocTemplate.from_tid('base', tformat=tformat,
                                                      template_dir=_DEFAULT_TEMPLATE_DIR)
                ref = self._reference_from_tid('base', tformat=tformat,
                                               template_dir=_DEFAULT_TEMPLATE_DIR)
                self.assertIsInstance(got, templating.BlockDocTemplate)
                self._assert_same_template(got, ref)

    def test_jinja_templates_on_default_dir(self):
        for tid, tformat in (('base.html.j2', 'html'), ('base.tex.j2', 'tex'),
                             ('report.typ.j2', 'typ'), ('base.tex.j2', '')):
            with self.subTest(tid=tid, tformat=tformat):
                got = templating.DocTemplate.from_tid(tid, tformat=tformat,
                                                      template_dir=_DEFAULT_TEMPLATE_DIR)
                ref = self._reference_from_tid(tid, tformat=tformat,
                                               template_dir=_DEFAULT_TEMPLATE_DIR)
                self.assertNotIsInstance(got, templating.BlockDocTemplate)
                self._assert_same_template(got, ref)

    def test_cross_format_lookup(self):
        got = templating.DocTemplate.from_tid('base.tex', tformat='html',
                                              template_dir=_DEFAULT_TEMPLATE_DIR)
        ref = self._reference_from_tid('base.tex', tformat='html',
                                       template_dir=_DEFAULT_TEMPLATE_DIR)
        self._assert_same_template(got, ref)
        self.assertEqual(got.template_id, 'base.html')

        got = templating.DocTemplate.from_tid('base.typ', tformat='tex',
                                              template_dir=_DEFAULT_TEMPLATE_DIR)
        ref = self._reference_from_tid('base.typ', tformat='tex',
                                       template_dir=_DEFAULT_TEMPLATE_DIR)
        self._assert_same_template(got, ref)
        self.assertEqual(got.template_id, 'base.tex')

    def test_block_template_in_temp_dir_with_assets(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, 'btpl.tex'), 'w', encoding='utf-8') as f:
                f.write(MARKED_TEX_SOURCE)
            os.makedirs(os.path.join(td, 'assets'))
            with open(os.path.join(td, 'assets', 'global.bin'), 'wb') as f:
                f.write(b'GLOBAL')
            os.makedirs(os.path.join(td, 'btpl.assets'))
            with open(os.path.join(td, 'btpl.assets', 'own.bin'), 'wb') as f:
                f.write(b'OWN')

            got = templating.DocTemplate.from_tid('btpl', tformat='tex', template_dir=td)
            ref = self._reference_from_tid('btpl', tformat='tex', template_dir=td)

            self.assertIsInstance(got, templating.BlockDocTemplate)
            self._assert_same_template(got, ref)
            self.assertEqual(got.template_id, 'btpl.tex')
            self.assertEqual(got.params, {'title': 'Block Default'})
            # merged global + template-specific attachments
            self.assertEqual(got.attachments, {'global.bin': b'GLOBAL', 'own.bin': b'OWN'})

    def test_custom_template_dir_jinja(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, 'jt.tpl.j2'), 'w', encoding='utf-8') as f:
                f.write('Hello {{ who }}!')
            got = templating.DocTemplate.from_tid('jt.tpl', template_dir=td)
            ref = self._reference_from_tid('jt.tpl', template_dir=td)
            self.assertNotIsInstance(got, templating.BlockDocTemplate)
            self._assert_same_template(got, ref)
            self.assertIn('who', got.params)

    def test_missing_id_raises_keyerror(self):
        with self.assertRaises(KeyError) as ctx:
            templating.DocTemplate.from_tid('no_such_template_xyz',
                                            template_dir=_DEFAULT_TEMPLATE_DIR)
        self.assertIn('my_template_id=', str(ctx.exception))

        with self.assertRaises(KeyError) as ctx:
            templating.DocTemplate.from_tid('no_such_template_xyz', tformat='typ',
                                            template_dir=_DEFAULT_TEMPLATE_DIR)
        self.assertIn('my_template_id=', str(ctx.exception))

    def test_params_json_preferred_over_block_params(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, 'btpl.tex'), 'w', encoding='utf-8') as f:
                f.write(MARKED_TEX_SOURCE)
            with open(os.path.join(td, 'btpl.params.json'), 'w', encoding='utf-8') as f:
                json.dump({'title': 'From JSON'}, f)
            got = templating.DocTemplate.from_tid('btpl', tformat='tex', template_dir=td)
            ref = self._reference_from_tid('btpl', tformat='tex', template_dir=td)
            self._assert_same_template(got, ref)
            self.assertEqual(got.params, {'title': 'From JSON'})


class TestTemplateDirSourceCache(unittest.TestCase):
    """Per-instance memoization of the directory scans (get_block_templates /
    get_templates) plus the clear_cache() invalidation API."""

    def test_getters_return_shallow_copies(self):
        tds = templating.TemplateDirSource(_DEFAULT_TEMPLATE_DIR)
        templates = tds.get_templates()
        templates['injected'] = None
        templates.pop('base.tex.j2', None)
        again = tds.get_templates()
        self.assertNotIn('injected', again)
        self.assertIn('base.tex.j2', again)

        blocks = tds.get_block_templates()
        blocks['injected.tex'] = None
        self.assertNotIn('injected.tex', tds.get_block_templates())

    def test_clear_cache_sees_new_jinja_template(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, 'first.tex.j2'), 'w', encoding='utf-8') as f:
                f.write('ONE {{ body }}')
            tds = templating.TemplateDirSource(td)
            self.assertIn('first.tex.j2', tds.get_templates())
            self.assertNotIn('first.tex.j2', tds.get_block_templates())

            # a file added after the first load is invisible until clear_cache()
            with open(os.path.join(td, 'second.tex.j2'), 'w', encoding='utf-8') as f:
                f.write('TWO {{ body }}')
            self.assertNotIn('second.tex.j2', tds.get_templates())

            tds.clear_cache()
            self.assertIn('second.tex.j2', tds.get_templates())

    def test_clear_cache_sees_new_block_template(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, 'plain.tex'), 'w', encoding='utf-8') as f:
                f.write('\\documentclass{article}\nno markers here\n')
            tds = templating.TemplateDirSource(td)
            self.assertEqual(tds.get_block_templates(), {})

            with open(os.path.join(td, 'late.tex'), 'w', encoding='utf-8') as f:
                f.write(MARKED_TEX_SOURCE)
            self.assertEqual(tds.get_block_templates(), {})

            tds.clear_cache()
            self.assertIn('late.tex', tds.get_block_templates())

    def test_long_lived_instance_picks_up_changes_after_clear(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, 'one.tex.j2'), 'w', encoding='utf-8') as f:
                f.write('ONE {{ body }}')
            tds = templating.TemplateDirSource(td)
            self.assertEqual(tds.resolve_template_id('one'), 'one.tex.j2')
            # populate the scan caches
            self.assertEqual(set(tds.get_templates()), {'one.tex.j2'})
            with open(os.path.join(td, 'two.tex.j2'), 'w', encoding='utf-8') as f:
                f.write('TWO {{ body }}')
            # fresh from_tid calls always see the current state (fresh instance)
            t = templating.DocTemplate.from_tid('two', template_dir=td)
            self.assertEqual(t.template_id, 'two.tex.j2')
            # a long-lived instance needs clear_cache() to see it
            self.assertNotIn('two.tex.j2', tds.get_templates())
            tds.clear_cache()
            self.assertIn('two.tex.j2', tds.get_templates())

    def test_get_all_still_loads_everything(self):
        tds = templating.TemplateDirSource(_DEFAULT_TEMPLATE_DIR)
        templates, params, attachments = tds.get_all()
        self.assertIn('base.typ', templates)
        self.assertIn('base.typ.j2', templates)
        self.assertEqual(set(params.keys()), set(templates.keys()))

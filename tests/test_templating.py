import os
import sys
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
        self.assertIn("title", result)
        self.assertIn("body", result)
        self.assertIn("applicables", result)

    def test_str_filename_with_jinja2_extension(self):
        source = self._make_source(_DEFAULT_TEMPLATE_DIR)
        result = source("base.tex.j2")
        self.assertIn("title", result)
        self.assertIn("body", result)

    def test_str_stripped_plain_filename(self):
        source = self._make_source(_DEFAULT_TEMPLATE_DIR)
        result = source("  base.html  ")
        self.assertIn("title", result)
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

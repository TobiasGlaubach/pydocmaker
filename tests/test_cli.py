import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr
from pathlib import Path

_setup = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(_setup), 'src')
if _src not in sys.path:
    sys.path.insert(0, _src)

from pydocmaker.cli import (_bake_macro_named_params,
                            _find_template_file_references,
                            _load_assets_paths,
                            _load_param_file_values)

CLI = [sys.executable, '-m', 'pydocmaker.cli']

_ENV = dict(os.environ)
_ENV['PYTHONPATH'] = _src + os.pathsep + _ENV.get('PYTHONPATH', '')

#: a valid 1x1 pixel png used as a template attachment in the tests
PNG_1PX = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQ'
    'GAhKmMIQAAAABJRU5ErkJggg==')


def _typst_available():
    try:
        import typst  # noqa: F401
        return True
    except ImportError:
        return False


def _latex_compiler_available():
    return any(shutil.which(c) for c in
               ('tectonic', 'pdflatex', 'lualatex', 'xelatex'))


def _pandoc_available():
    try:
        from pydocmaker.backend.pandoc_api import can_run_pandoc
        return bool(can_run_pandoc())
    except Exception:
        return False


def run_cli(*argv, cwd=None):
    return subprocess.run(CLI + list(argv), capture_output=True, text=True,
                          env=_ENV, cwd=cwd)


class TestExample(unittest.TestCase):

    def test_example_md_to_stdout(self):
        r = run_cli('example', 'md')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Some Example Text', r.stdout)

    def test_example_json_to_stdout(self):
        r = run_cli('example', 'json')
        self.assertEqual(r.returncode, 0, r.stderr)
        parts = json.loads(r.stdout)
        self.assertIsInstance(parts, list)
        self.assertTrue(parts)

    def test_example_to_file_appends_extension(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, 'example')
            r = run_cli('example', 'md', '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.isfile(out + '.md'))
            self.assertIn('Some Example Text', Path(out + '.md').read_text(encoding='utf-8'))

    def test_example_format_inferred_from_out(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, 'example.json')
            r = run_cli('example', '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIsInstance(json.loads(Path(out).read_text(encoding='utf-8')), list)

    def test_example_unknown_format(self):
        r = run_cli('example', 'nope')
        self.assertEqual(r.returncode, 2)
        self.assertIn('error:', r.stderr)


class TestBuild(unittest.TestCase):

    def test_build_md_to_md(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'doc.md')
            Path(p).write_text('# Hello\n\nworld **bold**\n', encoding='utf-8')
            # format md on a .md input collides with the input file
            r = run_cli('build', p, '-f', 'md')
            self.assertEqual(r.returncode, 2)
            self.assertIn('overwrite', r.stderr)
            # explicit -o works
            r = run_cli('build', p, '-f', 'md', '-o', os.path.join(td, 'out.md'))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('world', Path(os.path.join(td, 'out.md')).read_text(encoding='utf-8'))

    def test_build_tex_input_to_md(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'report.tex')
            Path(p).write_text(r'\textbf{Hello} from latex', encoding='utf-8')
            r = run_cli('build', p, '-f', 'md', '-o', os.path.join(td, 'out.md'))
            self.assertEqual(r.returncode, 0, r.stderr)
            content = Path(os.path.join(td, 'out.md')).read_text(encoding='utf-8')
            self.assertIn('Hello', content)

    def test_build_plain_text_input(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'notes.txt')
            Path(p).write_text('just some plain text\n', encoding='utf-8')
            r = run_cli('build', p, '-f', 'md', '-o', os.path.join(td, 'out.md'))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('just some plain text',
                          Path(os.path.join(td, 'out.md')).read_text(encoding='utf-8'))

    def test_build_multiple_inputs_built_individually(self):
        with tempfile.TemporaryDirectory() as td:
            a = os.path.join(td, 'a.tex')
            b = os.path.join(td, 'b.tex')
            Path(a).write_text('first part\n', encoding='utf-8')
            Path(b).write_text('second part\n', encoding='utf-8')
            r = run_cli('build', a, b, '-f', 'md')
            self.assertEqual(r.returncode, 0, r.stderr)
            for name, text in (('a', 'first part'), ('b', 'second part')):
                out = os.path.join(td, f'{name}.md')
                self.assertTrue(os.path.isfile(out), out)
                self.assertIn(text, Path(out).read_text(encoding='utf-8'))

    def test_build_wildcard_input(self):
        with tempfile.TemporaryDirectory() as td:
            for name in ('abc1.tex', 'abc2.tex', 'abc3.tex'):
                Path(os.path.join(td, name)).write_text(
                    f'Hello from {name}', encoding='utf-8')
            Path(os.path.join(td, 'other.tex')).write_text(
                'should not be built', encoding='utf-8')
            r = run_cli('build', os.path.join(td, 'abc*.tex'), '-f', 'md')
            self.assertEqual(r.returncode, 0, r.stderr)
            for name in ('abc1', 'abc2', 'abc3'):
                out = os.path.join(td, f'{name}.md')
                self.assertTrue(os.path.isfile(out), out)
                self.assertIn(f'Hello from {name}.tex',
                              Path(out).read_text(encoding='utf-8'))
            self.assertFalse(os.path.isfile(os.path.join(td, 'other.md')))
            # no output file may overwrite its input
            for name in ('abc1.tex', 'abc2.tex', 'abc3.tex'):
                self.assertIn(f'Hello from {name}',
                              Path(os.path.join(td, name)).read_text(encoding='utf-8'))

    def test_build_wildcard_no_match_errors(self):
        with tempfile.TemporaryDirectory() as td:
            r = run_cli('build', os.path.join(td, 'nothing*.tex'), '-f', 'md')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('did not match any files', r.stderr)

    def test_build_wildcard_multiple_matches_rejects_out(self):
        with tempfile.TemporaryDirectory() as td:
            for name in ('abc1.tex', 'abc2.tex'):
                Path(os.path.join(td, name)).write_text('Hello', encoding='utf-8')
            out = os.path.join(td, 'out.md')
            r = run_cli('build', os.path.join(td, 'abc*.tex'), '-f', 'md', '-o', out)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('-o/--out cannot be used with multiple inputs', r.stderr)

    def test_build_json_roundtrip_via_pyd(self):
        with tempfile.TemporaryDirectory() as td:
            docjson = os.path.join(td, 'doc.json')
            r = run_cli('example', 'json', '-o', docjson)
            self.assertEqual(r.returncode, 0, r.stderr)
            pyd = os.path.join(td, 'doc.pyd')
            r = run_cli('build', docjson, '-f', 'pyd', '-o', pyd)
            self.assertEqual(r.returncode, 0, r.stderr)
            # the .pyd round-trip file must load back as a pydocmaker document
            r = run_cli('check', pyd)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('html pydocmaker document', r.stdout)
            self.assertIn('syntax    : OK', r.stdout)

    def test_convert_is_synonym_for_build(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'doc.md')
            Path(p).write_text('# Hello\n', encoding='utf-8')
            r = run_cli('convert', p, '-f', 'md', '-o', os.path.join(td, 'out.md'))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.isfile(os.path.join(td, 'out.md')))

    def test_build_tex_template_defaults_not_escaped(self):
        """Template default params containing LaTeX macros (e.g. ``\\today``)
        must survive a tex build via ``-t`` (meta round-trip) unharmed."""
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'doc.md')
            Path(p).write_text('# Hello\n\ncontent\n', encoding='utf-8')
            out = os.path.join(td, 'out.tex')
            r = run_cli('build', p, '-f', 'tex', '-t', 'base.tex', '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            content = Path(out).read_text(encoding='utf-8')
            self.assertIn(r'\providecommand{\pDate}{\today}', content)
            self.assertNotIn('textbackslash', content)

    def test_build_missing_input(self):
        r = run_cli('build', 'does_not_exist.md')
        self.assertEqual(r.returncode, 2)
        self.assertIn('error:', r.stderr)

    def test_build_binary_input(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'blob.bin')
            Path(p).write_bytes(b'\x00\x01\x02binary\x00')
            r = run_cli('build', p)
            self.assertEqual(r.returncode, 2)
            self.assertIn('binary', r.stderr)

    @unittest.skipUnless(_latex_compiler_available(), 'no latex compiler found')
    def test_build_tex_with_sibling_asset(self):
        """a tex input built from a foreign cwd must find assets next to the
        input file (the pdf compile runs in an isolated temp directory)"""
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'report.tex')
            Path(p).write_text(
                '\\documentclass{article}\n'
                '\\usepackage{graphicx}\n'
                '\\begin{document}\n'
                '\\includegraphics[width=1cm]{logo.png}\n'
                '\\end{document}\n', encoding='utf-8')
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            # run from the repo cwd (NOT cwd=td) -- that is the regression
            r = run_cli('build', p, '-f', 'pdf')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(Path(td, 'report.pdf').read_bytes().startswith(b'%PDF'))

    @unittest.skipUnless(_latex_compiler_available(), 'no latex compiler found')
    def test_build_tex_with_nested_sibling_asset(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, 'images'))
            p = os.path.join(td, 'report.tex')
            Path(p).write_text(
                '\\documentclass{article}\n'
                '\\usepackage{graphicx}\n'
                '\\begin{document}\n'
                '\\includegraphics[width=1cm]{images/logo.png}\n'
                '\\end{document}\n', encoding='utf-8')
            Path(td, 'images', 'logo.png').write_bytes(PNG_1PX)
            r = run_cli('build', p, '-f', 'pdf')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(Path(td, 'report.pdf').read_bytes().startswith(b'%PDF'))

    @unittest.skipUnless(_typst_available(), 'typst engine not installed')
    def test_build_typ_with_sibling_asset(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'report.typ')
            Path(p).write_text('#image("logo.png", width: 1cm)\n', encoding='utf-8')
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            # run from the repo cwd (NOT cwd=td) -- that is the regression
            r = run_cli('build', p, '-f', 'pdf')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(Path(td, 'report.pdf').read_bytes().startswith(b'%PDF'))


class TestCheck(unittest.TestCase):

    def test_check_json_ok(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'doc.json')
            run_cli('example', 'json', '-o', p)
            r = run_cli('check', p)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('json pydocmaker document', r.stdout)
            self.assertIn('syntax    : OK', r.stdout)

    def test_check_json_broken(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'broken.json')
            Path(p).write_text('this is { not json', encoding='utf-8')
            r = run_cli('check', p)
            self.assertEqual(r.returncode, 1)
            self.assertIn('syntax    : NOT OK', r.stdout)

    def test_check_pyd_html_document(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'doc.pyd')
            run_cli('example', 'pyd', '-o', p)
            r = run_cli('check', p)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('html pydocmaker document', r.stdout)

    def test_check_blocktemplate_typ(self):
        tpl = os.path.join(_src, 'pydocmaker', 'templates', 'base.typ')
        r = run_cli('check', tpl)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('block template (typ)', r.stdout)
        self.assertIn('syntax    : OK', r.stdout)
        params = json.loads(r.stdout.split('parameters: ', 1)[1])
        self.assertEqual(params['pTitle'], 'My Report')

    def test_check_blocktemplate_broken(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'bad.tex')
            Path(p).write_text('% pydocmaker:parameters:begin\nunclosed\n', encoding='utf-8')
            r = run_cli('check', p)
            self.assertEqual(r.returncode, 1)
            self.assertIn('syntax    : NOT OK', r.stdout)
            self.assertIn('unclosed', r.stdout)

    def test_check_unsupported_extension(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'doc.txt')
            Path(p).write_text('plain\n', encoding='utf-8')
            r = run_cli('check', p)
            self.assertEqual(r.returncode, 2)
            self.assertIn('error:', r.stderr)


class TestExtract(unittest.TestCase):

    def test_extract_blocktemplate(self):
        tpl = os.path.join(_src, 'pydocmaker', 'templates', 'base.typ')
        r = run_cli('extract', tpl)
        self.assertEqual(r.returncode, 0, r.stderr)
        params = json.loads(r.stdout)
        self.assertEqual(params['pTitle'], 'My Report')
        self.assertIn('pAcronyms', params)

    def test_extract_jinja_template(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 't.html.j2')
            Path(p).write_text('<h1>{{ title }}</h1>\n<p>{{ body }}</p>\n', encoding='utf-8')
            r = run_cli('extract', p)
            self.assertEqual(r.returncode, 0, r.stderr)
            params = json.loads(r.stdout)
            # 'body' is reserved and excluded, 'title' is undeclared
            self.assertEqual(params, {'title': None})


class TestTemplate(unittest.TestCase):

    def test_template_format_to_stdout(self):
        r = run_cli('template', 'typ')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('pydocmaker:parameters:begin', r.stdout)

    def test_template_to_file_appends_extension(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, 'mytmpl')
            r = run_cli('template', 'html', '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            content = Path(out + '.html').read_text(encoding='utf-8')
            self.assertIn('pydocmaker:parameters:begin', content)

    def test_template_explicit_name(self):
        r = run_cli('template', 'base.tex')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('pydocmaker:parameters:begin', r.stdout)

    def test_template_bare_id(self):
        r = run_cli('template', 'base')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('pydocmaker:parameters:begin', r.stdout)

    def test_template_not_found(self):
        r = run_cli('template', 'no_such_template')
        self.assertEqual(r.returncode, 2)
        self.assertIn('error:', r.stderr)


class TestShow(unittest.TestCase):

    def test_show_example_md(self):
        r = run_cli('show', 'md')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Some Example Text', r.stdout)

    def test_show_input_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'doc.md')
            Path(p).write_text('# shown from file\n', encoding='utf-8')
            r = run_cli('show', 'md', p)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('shown from file', r.stdout)

    def test_show_single_argument_is_input_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'doc.md')
            Path(p).write_text('# convenience swap\n', encoding='utf-8')
            r = run_cli('show', p)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('convenience swap', r.stdout)

    def test_show_unknown_engine(self):
        r = run_cli('show', 'not_an_engine')
        self.assertEqual(r.returncode, 2)
        self.assertIn('error:', r.stderr)


class TestTemplates(unittest.TestCase):
    """the ``templates`` command: list registered templates and their paths."""

    def test_templates_lists_package_templates(self):
        r = run_cli('templates')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('base.html', r.stdout)
        self.assertIn('base.typ.j2', r.stdout)
        self.assertIn('report.tex', r.stdout)
        # full paths are shown
        self.assertIn(os.path.join('templates', 'base.html'), r.stdout)

    def test_templates_includes_registered_dir(self):
        import contextlib
        from pydocmaker import cli
        from pydocmaker.templating import (register_new_template_dir,
                                           remove_from_template_dir)
        with tempfile.TemporaryDirectory() as td:
            Path(os.path.join(td, 'my_custom.typ')).write_text(
                '// custom template\n', encoding='utf-8')
            self.assertTrue(register_new_template_dir(td))
            try:
                buf_out, buf_err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(buf_out), \
                        contextlib.redirect_stderr(buf_err):
                    rc = cli.main(['templates'])
            finally:
                remove_from_template_dir(td)
            self.assertEqual(rc, 0)
            self.assertIn(td, buf_out.getvalue())
            self.assertIn('my_custom.typ', buf_out.getvalue())

    def test_templates_missing_dir_warns(self):
        import contextlib
        from pydocmaker import cli
        from pydocmaker.templating import (register_new_template_dir,
                                           remove_from_template_dir)
        missing = os.path.join(tempfile.gettempdir(), 'no_such_tmpl_dir_xyz')
        self.assertTrue(register_new_template_dir(missing, check_exists=False))
        try:
            buf_out, buf_err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(buf_out), \
                    contextlib.redirect_stderr(buf_err):
                rc = cli.main(['templates'])
        finally:
            remove_from_template_dir(missing)
        self.assertEqual(rc, 0)
        self.assertIn('does not exist', buf_err.getvalue())


class TestTemplating(unittest.TestCase):
    """-t/--template, -p/--parameters and unknown-argument parameters."""

    def test_example_with_template_id_and_flag_params(self):
        r = run_cli('example', 'typst', '-t', 'base',
                    '--pTitle', 'CLI Title', '--pAuthor', 'me')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('#let pTitle = "CLI Title"', r.stdout)
        self.assertIn('#let pAuthor = "me"', r.stdout)
        # unset template defaults are kept
        self.assertIn('pAcronyms', r.stdout)

    def test_example_with_template_id_and_eq_params(self):
        r = run_cli('example', 'typst', '-t', 'base',
                    '--pTitle=EqTitle', '--pFlag')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('#let pTitle = "EqTitle"', r.stdout)

    def test_example_with_parameters_json_string(self):
        r = run_cli('example', 'typst', '-t', 'base', '-p', '{"pTitle": "From JSON"}')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('#let pTitle = "From JSON"', r.stdout)

    def test_example_with_parameters_json_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'params.json')
            Path(p).write_text(json.dumps({'pTitle': 'From File'}), encoding='utf-8')
            r = run_cli('example', 'typst', '-t', 'base', '-p', p)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('#let pTitle = "From File"', r.stdout)
            r = run_cli('example', 'typst', '-t', 'base', '-p', '@' + p)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('#let pTitle = "From File"', r.stdout)

    def test_flag_params_override_parameters_json(self):
        r = run_cli('example', 'typst', '-t', 'base',
                    '-p', '{"pTitle": "json"}', '--pTitle', 'flag')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('#let pTitle = "flag"', r.stdout)

    def test_param_values_are_json_parsed(self):
        r = run_cli('example', 'typst', '-t', 'base',
                    '--pAcronyms', '{"X": "Y"}', '--pDate', '2026-01-02')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('#let pAcronyms = (X: "Y")', r.stdout)
        self.assertIn('#let pDate = "2026-01-02"', r.stdout)

    def test_params_without_template_apply_to_default_template(self):
        r = run_cli('example', 'typst', '--pTitle', 'No Template')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('#let pTitle = "No Template"', r.stdout)

    def test_params_before_subcommand(self):
        r = run_cli('-t', 'base', '--pAuthor', 'me', 'example', 'typst')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('#let pAuthor = "me"', r.stdout)

    def test_template_and_params_for_html_format(self):
        r = run_cli('example', 'html', '-t', 'base', '--pTitle', 'HTML Title')
        self.assertEqual(r.returncode, 0, r.stderr)
        # base.html applies its parameters via javascript at page load; the
        # static output carries them in the parameter meta tags
        self.assertIn('content="HTML Title"', r.stdout)

    def test_raw_block_template_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'mybase.typ')
            tpl = os.path.join(_src, 'pydocmaker', 'templates', 'base.typ')
            Path(p).write_text(Path(tpl).read_text(encoding='utf-8'), encoding='utf-8')
            r = run_cli('example', 'typst', '-t', p, '--pTitle', 'Raw File')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('#let pTitle = "Raw File"', r.stdout)
            # other defaults of the raw template are kept
            self.assertIn('#let pAuthor = "Automatically Generated via pydocmaker"',
                          r.stdout)

    def test_raw_markerless_template_file_is_scaffolded(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'plain.typ')
            Path(p).write_text('#set page("a4")\n\n= my heading\n', encoding='utf-8')
            r = run_cli('example', 'typst', '-t', p, '--pMyParam', '7')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('#let pMyParam = 7', r.stdout)
            self.assertIn('= my heading', r.stdout)
            self.assertIn('pydocmaker:body:begin', r.stdout)

    def test_raw_jinja_template_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 't.html.j2')
            Path(p).write_text('<h1>{{ pTitle }}</h1>\n{{ body }}\n<p>by {{ pAuthor }}</p>\n',
                               encoding='utf-8')
            r = run_cli('example', 'html', '-t', p,
                        '--pTitle', 'Jinja Works', '--pAuthor', 'me')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('<h1>Jinja Works</h1>', r.stdout)
            self.assertIn('<p>by me</p>', r.stdout)

    def test_build_with_template(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'doc.md')
            Path(p).write_text('# Hello\n\nsome **content**\n', encoding='utf-8')
            out = os.path.join(td, 'out.typ')
            r = run_cli('build', p, '-f', 'typst', '-t', 'base',
                        '--pTitle', 'Built', '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            src = Path(out).read_text(encoding='utf-8')
            self.assertIn('#let pTitle = "Built"', src)
            self.assertIn('content', src)

    def test_build_wildcard_with_template(self):
        with tempfile.TemporaryDirectory() as td:
            for name in ('abc1.md', 'abc2.md'):
                Path(os.path.join(td, name)).write_text(
                    f'# {name}\n\nsome content\n', encoding='utf-8')
            r = run_cli('convert', os.path.join(td, 'abc*.md'), '-f', 'typst',
                        '-t', 'base', '--pTitle', 'Built')
            self.assertEqual(r.returncode, 0, r.stderr)
            for name in ('abc1', 'abc2'):
                src = Path(os.path.join(td, f'{name}.typ')).read_text(encoding='utf-8')
                self.assertIn('#let pTitle = "Built"', src)
                self.assertIn(name, src)

    def test_show_with_template(self):
        r = run_cli('show', 'typst', '-t', 'base', '--pTitle', 'Shown Title')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('#let pTitle = "Shown Title"', r.stdout)

    def test_show_md_with_template_warns(self):
        r = run_cli('show', 'md', '-t', 'base', '--pTitle', 'X')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('has no effect', r.stderr)

    def test_build_md_with_template_warns(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'doc.md')
            Path(p).write_text('hello\n', encoding='utf-8')
            out = os.path.join(td, 'out.md')
            r = run_cli('build', p, '-f', 'md', '-t', 'base', '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('has no effect', r.stderr)

    def test_template_not_found(self):
        r = run_cli('example', 'typst', '-t', 'no_such_template')
        self.assertEqual(r.returncode, 2)
        self.assertIn('error:', r.stderr)
        self.assertIn('available template ids', r.stderr)

    def test_parameters_invalid(self):
        r = run_cli('example', 'typst', '-p', 'not json at all')
        self.assertEqual(r.returncode, 2)
        self.assertIn('error:', r.stderr)

    def test_parameters_not_a_mapping(self):
        r = run_cli('example', 'typst', '-p', '[1, 2]')
        self.assertEqual(r.returncode, 2)
        self.assertIn('JSON object', r.stderr)

    def test_known_option_abbreviations_still_work(self):
        r = run_cli('example', 'typst', '--temp', 'base', '--pAuthor', 'me')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('#let pAuthor = "me"', r.stdout)

    def test_unknown_args_still_error_for_non_templating_commands(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'd.json')
            run_cli('example', 'json', '-o', p)
            r = run_cli('check', p, '--pAuthor', 'me')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('unrecognized arguments', r.stderr)

    def test_template_with_tex_format(self):
        r = run_cli('example', 'tex', '-t', 'base.tex', '--pTitle', 'Tex Title')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Tex Title', r.stdout)


class TestTemplateFileReferenceScanner(unittest.TestCase):
    """unit tests for the raw template source reference scanner."""

    def test_tex_includegraphics_with_options_and_spaces(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            src = r'\includegraphics[width=8cm,angle=0]{ logo.png }'
            atts, unresolved = _find_template_file_references(src, 'tex', td)
            self.assertEqual(list(atts), ['logo.png'])
            self.assertEqual(atts['logo.png'], PNG_1PX)
            self.assertEqual(unresolved, [])

    def test_tex_macro_reference_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            src = r'\fancyhead{\includegraphics[height=1.2cm]{\pProjectLogo}}'
            atts, unresolved = _find_template_file_references(src, 'tex', td)
            self.assertEqual(atts, {})
            self.assertEqual(unresolved, [])

    def test_tex_input_and_lstinputlisting(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'part.tex').write_text('content', encoding='utf-8')
            Path(td, 'data.txt').write_text('1 2 3', encoding='utf-8')
            src = '\\input{part.tex}\n\\lstinputlisting{data.txt}'
            atts, unresolved = _find_template_file_references(src, 'tex', td)
            self.assertEqual(sorted(atts), ['data.txt', 'part.tex'])
            self.assertEqual(atts['part.tex'], b'content')
            self.assertEqual(unresolved, [])

    def test_nested_reference_key_uses_posix_slashes(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, 'images'))
            Path(td, 'images', 'logo.png').write_bytes(PNG_1PX)
            atts, _ = _find_template_file_references(
                r'\includegraphics{images/logo.png}', 'tex', td)
            self.assertEqual(list(atts), ['images/logo.png'])
            self.assertEqual(atts['images/logo.png'], PNG_1PX)

    def test_typst_image_read_and_include(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            Path(td, 'data.txt').write_text('abc', encoding='utf-8')
            Path(td, 'part.typ').write_text('= part', encoding='utf-8')
            src = ("#image(\"logo.png\", width: 30%)\n"
                   "#read('data.txt')\n"
                   "#include \"part.typ\"\n")
            atts, unresolved = _find_template_file_references(src, 'typ', td)
            self.assertEqual(sorted(atts), ['data.txt', 'logo.png', 'part.typ'])
            self.assertEqual(unresolved, [])

    def test_typst_jinja_expression_is_skipped(self):
        src = '#image("{{ logo_path }}.png")\n'
        atts, unresolved = _find_template_file_references(src, 'typ', None)
        self.assertEqual(atts, {})
        self.assertEqual(unresolved, [])

    def test_param_default_with_surrounding_spaces(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'MKE.png').write_bytes(PNG_1PX)
            src = ('% pydocmaker:parameters:begin \n\n'
                   '% pydocmaker:param:p_projectlogo\n'
                   '\\providecommand{\\pProjectLogo}{ MKE.png }\n\n'
                   '% pydocmaker:parameters:end \n')
            atts, unresolved = _find_template_file_references(src, 'tex', td)
            self.assertEqual(list(atts), ['MKE.png'])
            self.assertEqual(atts['MKE.png'], PNG_1PX)
            self.assertEqual(unresolved, [])

    def test_missing_reference_warns_but_does_not_fail(self):
        with tempfile.TemporaryDirectory() as td:
            err = io.StringIO()
            with redirect_stderr(err):
                atts, unresolved = _find_template_file_references(
                    r'\includegraphics{missing.png}', 'tex', td)
            self.assertEqual(atts, {})
            self.assertEqual(unresolved, ['missing.png'])
            self.assertIn('missing.png', err.getvalue())

    def test_reference_without_extension_does_not_warn(self):
        with tempfile.TemporaryDirectory() as td:
            err = io.StringIO()
            with redirect_stderr(err):
                _, unresolved = _find_template_file_references(
                    r'\input{not_there}', 'tex', td)
            self.assertEqual(unresolved, ['not_there'])
            self.assertEqual(err.getvalue(), '')


class TestParamFileValues(unittest.TestCase):
    """unit tests for parameter values that point at existing files."""

    def test_resolution_from_template_dir_and_basename_rewrite(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            os.makedirs(os.path.join(td, 'sub'))
            Path(td, 'sub', 'alt.png').write_bytes(PNG_1PX + b'2')
            params = {'pLogo': 'logo.png', 'pAlt': 'sub/alt.png',
                      'pText': 'just a text value'}
            atts = _load_param_file_values(params, td)
            # values are rewritten to the bare file names
            self.assertEqual(params['pLogo'], 'logo.png')
            self.assertEqual(params['pAlt'], 'alt.png')
            self.assertEqual(params['pText'], 'just a text value')
            self.assertEqual(atts['logo.png'], PNG_1PX)
            self.assertEqual(atts['alt.png'], PNG_1PX + b'2')

    def test_non_existing_value_is_kept(self):
        params = {'pTitle': 'my.title', 'pN': 5, 'pFlag': True}
        atts = _load_param_file_values(params, None)
        self.assertEqual(params, {'pTitle': 'my.title', 'pN': 5, 'pFlag': True})
        self.assertEqual(atts, {})

    def test_basename_collision_warns_and_last_wins(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, 'a'))
            os.makedirs(os.path.join(td, 'b'))
            Path(td, 'a', 'logo.png').write_bytes(b'AAA')
            Path(td, 'b', 'logo.png').write_bytes(b'BBB')
            params = {'pX': 'a/logo.png', 'pY': 'b/logo.png'}
            err = io.StringIO()
            with redirect_stderr(err):
                atts = _load_param_file_values(params, td)
            self.assertEqual(atts['logo.png'], b'BBB')
            self.assertIn('logo.png', err.getvalue())


class TestMacroParamBaking(unittest.TestCase):
    """unit tests for parameters given under their latex macro name."""

    TEX_SRC = ('% pydocmaker:parameters:begin \n\n'
               '% pydocmaker:param:p_projectlogo\n'
               '\\providecommand{\\pProjectLogo}{ MKE.png }\n\n'
               '% pydocmaker:param:pDocTitle\n'
               '\\providecommand{\\pDocTitle}{New Title}\n\n'
               '% pydocmaker:parameters:end \n')

    def test_macro_named_param_is_baked_into_assignment(self):
        params = {'pProjectLogo': 'INAF-Logo.png'}
        out, remaining = _bake_macro_named_params(self.TEX_SRC, 'tex', params)
        self.assertEqual(remaining, {})
        self.assertIn(r'\providecommand{\pProjectLogo}{INAF-Logo.png}', out)
        self.assertNotIn('MKE.png', out)
        # unrelated assignments stay untouched
        self.assertIn(r'\providecommand{\pDocTitle}{New Title}', out)

    def test_exact_param_names_are_left_to_the_render_engine(self):
        params = {'pDocTitle': 'Other Title'}
        out, remaining = _bake_macro_named_params(self.TEX_SRC, 'tex', params)
        self.assertEqual(remaining, {'pDocTitle': 'Other Title'})
        self.assertEqual(out, self.TEX_SRC)

    def test_non_tex_formats_are_unchanged(self):
        params = {'pProjectLogo': 'INAF-Logo.png'}
        out, remaining = _bake_macro_named_params('#let x = 1', 'typ', params)
        self.assertEqual(out, '#let x = 1')
        self.assertEqual(remaining, params)


class TestAssetsFlag(unittest.TestCase):
    """-a/--assets: explicit attachment paths."""

    TEX_TMPL = ('% pydocmaker:parameters:begin \n\n'
                '% pydocmaker:param:pTitle\n'
                '\\providecommand{\\pTitle}{My Report}\n\n'
                '% pydocmaker:parameters:end \n\n'
                '\\documentclass{article}\n'
                '\\begin{document}\n'
                '% pydocmaker:body:begin \n\n'
                '% pydocmaker:body:end \n'
                '\\end{document}\n')

    def _doc(self, td):
        p = os.path.join(td, 'doc.md')
        Path(p).write_text('# Hello\n\ncontent\n', encoding='utf-8')
        return p

    def _tmpl(self, td):
        p = os.path.join(td, 'tmpl.tex')
        Path(p).write_text(self.TEX_TMPL, encoding='utf-8')
        return p

    def test_assets_single_file(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'extra.png').write_bytes(PNG_1PX)
            out = os.path.join(td, 'out.zip')
            r = run_cli('build', self._doc(td), '-f', 'tex', '-t', self._tmpl(td),
                        '-a', os.path.join(td, 'extra.png'), '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            z = zipfile.ZipFile(out)
            self.assertIn('extra.png', z.namelist())
            self.assertEqual(z.read('extra.png'), PNG_1PX)

    def test_assets_folder_recursive_with_exclusions(self):
        with tempfile.TemporaryDirectory() as td:
            assets = os.path.join(td, 'assets')
            os.makedirs(os.path.join(assets, 'img', 'nested'))
            os.makedirs(os.path.join(assets, '.git'))
            os.makedirs(os.path.join(assets, '__pycache__'))
            Path(assets, 'img', 'logo.png').write_bytes(PNG_1PX)
            Path(assets, 'img', 'nested', 'icon.png').write_bytes(PNG_1PX)
            Path(assets, 'visible.txt').write_text('v', encoding='utf-8')
            Path(assets, '.git', 'config').write_text('g', encoding='utf-8')
            Path(assets, '.hidden').write_text('h', encoding='utf-8')
            Path(assets, '__pycache__', 'mod.pyc').write_bytes(b'pyc')
            out = os.path.join(td, 'out.zip')
            r = run_cli('build', self._doc(td), '-f', 'tex', '-t', self._tmpl(td),
                        '-a', assets, '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            names = zipfile.ZipFile(out).namelist()
            self.assertIn('img/logo.png', names)
            self.assertIn('img/nested/icon.png', names)
            self.assertIn('visible.txt', names)
            self.assertNotIn('.git/config', names)
            self.assertNotIn('.hidden', names)
            self.assertNotIn('__pycache__/mod.pyc', names)

    def test_assets_repeatable(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'one.png').write_bytes(PNG_1PX)
            Path(td, 'two.png').write_bytes(PNG_1PX + b'2')
            out = os.path.join(td, 'out.zip')
            r = run_cli('build', self._doc(td), '-f', 'tex', '-t', self._tmpl(td),
                        '-a', os.path.join(td, 'one.png'),
                        '-a', os.path.join(td, 'two.png'), '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            names = zipfile.ZipFile(out).namelist()
            self.assertIn('one.png', names)
            self.assertIn('two.png', names)

    def test_assets_without_template_lands_in_document_meta(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            out = os.path.join(td, 'out.json')
            r = run_cli('example', 'json', '-a', os.path.join(td, 'logo.png'),
                        '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            doc = json.loads(Path(out).read_text(encoding='utf-8'))
            meta = next(p for p in doc
                        if isinstance(p, dict) and p.get('typ') == 'meta')
            ftu = meta['data']['files_to_upload']
            self.assertEqual(list(ftu), ['logo.png'])
            self.assertEqual(base64.b64decode(ftu['logo.png']), PNG_1PX)

    def test_assets_missing_path_errors(self):
        with tempfile.TemporaryDirectory() as td:
            r = run_cli('build', self._doc(td), '-f', 'tex', '-a',
                        os.path.join(td, 'nope'), '-o', os.path.join(td, 'o.zip'))
            self.assertEqual(r.returncode, 2)
            self.assertIn('assets path not found', r.stderr)


class TestTemplateAttachmentsIntegration(unittest.TestCase):
    """end-to-end builds with scanned/param/assets attachments."""

    TEX_TMPL = ('% pydocmaker:parameters:begin \n\n'
                '% pydocmaker:param:pTitle\n'
                '\\providecommand{\\pTitle}{My Report}\n\n'
                '% pydocmaker:parameters:end \n\n'
                '\\documentclass{article}\n'
                '\\usepackage{graphicx}\n'
                '\\begin{document}\n'
                '\\includegraphics[width=2cm]{logo.png}\n\n'
                '% pydocmaker:body:begin \n\n'
                '% pydocmaker:body:end \n'
                '\\end{document}\n')

    TEX_TMPL_PARAM = ('% pydocmaker:parameters:begin \n\n'
                      '% pydocmaker:param:p_projectlogo\n'
                      '\\providecommand{\\pProjectLogo}{logo.png}\n\n'
                      '% pydocmaker:parameters:end \n\n'
                      '\\documentclass{article}\n'
                      '\\usepackage{graphicx}\n'
                      '\\begin{document}\n'
                      '\\includegraphics[width=2cm]{\\pProjectLogo}\n\n'
                      '% pydocmaker:body:begin \n\n'
                      '% pydocmaker:body:end \n'
                      '\\end{document}\n')

    TYP_TMPL = ('// pydocmaker:parameters:begin\n\n'
                '// pydocmaker:param:pLogo\n'
                '#let pLogo = "logo.png"\n\n'
                '// pydocmaker:parameters:end\n\n'
                '#image(pLogo, width: 30%)\n\n'
                '// pydocmaker:body:begin\n\n'
                '// pydocmaker:body:end\n')

    def _doc(self, td):
        p = os.path.join(td, 'doc.md')
        Path(p).write_text('# Hello\n\nsome content\n', encoding='utf-8')
        return p

    def _write(self, td, name, content):
        p = os.path.join(td, name)
        Path(p).write_text(content, encoding='utf-8')
        return p

    def test_tex_build_zip_contains_scanned_png(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            tmpl = self._write(td, 'tmpl.tex', self.TEX_TMPL)
            out = os.path.join(td, 'out.zip')
            r = run_cli('build', self._doc(td), '-f', 'tex', '-t', tmpl, '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            z = zipfile.ZipFile(out)
            names = z.namelist()
            self.assertIn('main.tex', names)
            self.assertIn('logo.png', names)
            self.assertEqual(z.read('logo.png'), PNG_1PX)
            self.assertIn(r'\includegraphics', z.read('main.tex').decode('utf-8'))

    def test_tex_param_default_and_macro_named_override(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            Path(td, 'alt.png').write_bytes(PNG_1PX + b'alt')
            tmpl = self._write(td, 'tmpl.tex', self.TEX_TMPL_PARAM)
            out = os.path.join(td, 'out.zip')
            r = run_cli('build', self._doc(td), '-f', 'tex', '-t', tmpl,
                        '--pProjectLogo', 'alt.png', '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            z = zipfile.ZipFile(out)
            names = z.namelist()
            # the scanned default and the parameter file are both attached
            self.assertIn('logo.png', names)
            self.assertIn('alt.png', names)
            self.assertEqual(z.read('alt.png'), PNG_1PX + b'alt')
            # the macro-named parameter is baked into the assignment
            tex = z.read('main.tex').decode('utf-8')
            self.assertIn(r'\providecommand{\pProjectLogo}{alt.png}', tex)
            self.assertNotIn(r'\providecommand{\pProjectLogo}{logo.png}', tex)

    def test_tex_nested_attachment_key(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, 'images'))
            Path(td, 'images', 'logo.png').write_bytes(PNG_1PX)
            tmpl = self._write(
                td, 'tmpl.tex', self.TEX_TMPL.replace('{logo.png}',
                                                      '{images/logo.png}'))
            out = os.path.join(td, 'out.zip')
            r = run_cli('build', self._doc(td), '-f', 'tex', '-t', tmpl, '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            z = zipfile.ZipFile(out)
            self.assertIn('images/logo.png', z.namelist())
            self.assertEqual(z.read('images/logo.png'), PNG_1PX)

    @unittest.skipUnless(_latex_compiler_available(), 'no latex compiler found')
    def test_tex_pdf_build_with_scanned_and_nested_png(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, 'images'))
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            Path(td, 'images', 'logo.png').write_bytes(PNG_1PX)
            tmpl = self._write(td, 'tmpl.tex', self.TEX_TMPL.replace(
                '{logo.png}', '{images/logo.png}'))
            out = os.path.join(td, 'out.pdf')
            r = run_cli('build', self._doc(td), '-t', tmpl, '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = Path(out).read_bytes()
            self.assertTrue(data.startswith(b'%PDF'))

    @unittest.skipUnless(_typst_available(), 'typst engine not installed')
    def test_typst_pdf_build_with_scanned_png(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            tmpl = self._write(td, 'tmpl.typ', self.TYP_TMPL)
            out = os.path.join(td, 'out.pdf')
            r = run_cli('build', self._doc(td), '-t', tmpl, '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = Path(out).read_bytes()
            self.assertTrue(data.startswith(b'%PDF'))

    @unittest.skipUnless(_typst_available(), 'typst engine not installed')
    def test_typst_param_file_value_renders_alt_logo(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            Path(td, 'alt.png').write_bytes(PNG_1PX + b'alt')
            tmpl = self._write(td, 'tmpl.typ', self.TYP_TMPL)
            # the rendered typst source uses the parameter file's bare name
            out = os.path.join(td, 'out.typ')
            r = run_cli('build', self._doc(td), '-f', 'typst', '-t', tmpl,
                        '--pLogo', 'alt.png', '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            src = Path(out).read_text(encoding='utf-8')
            self.assertIn('#let pLogo = "alt.png"', src)
            self.assertNotIn('#let pLogo = "logo.png"', src)
            # and the pdf build succeeds with the alternative image attached
            pdf = os.path.join(td, 'out.pdf')
            r = run_cli('build', self._doc(td), '-t', tmpl,
                        '--pLogo', 'alt.png', '-o', pdf)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(Path(pdf).read_bytes().startswith(b'%PDF'))

    @unittest.skipUnless(_typst_available(), 'typst engine not installed')
    def test_typst_nested_attachment_key_builds(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, 'images'))
            Path(td, 'images', 'logo.png').write_bytes(PNG_1PX)
            tmpl = self._write(td, 'tmpl.typ',
                               '#image("images/logo.png", width: 30%)\n')
            out = os.path.join(td, 'out.pdf')
            r = run_cli('build', self._doc(td), '-t', tmpl, '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(Path(out).read_bytes().startswith(b'%PDF'))

    def test_assets_folder_with_template(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            tmpl = self._write(td, 'tmpl.tex', self.TEX_TMPL)
            out = os.path.join(td, 'out.zip')
            r = run_cli('build', self._doc(td), '-f', 'tex', '-t', tmpl,
                        '-a', td, '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            z = zipfile.ZipFile(out)
            names = z.namelist()
            # everything next to the template is attached under its relpath
            self.assertIn('logo.png', names)
            self.assertIn('tmpl.tex', names)
            self.assertIn('doc.md', names)


class TestCompileDirFileRefs(unittest.TestCase):
    """document images referenced by bare name must survive the isolated
    compile directories used when a template brings attachments."""

    TYP_TMPL = ('// pydocmaker:parameters:begin\n\n'
                '// pydocmaker:param:pTitle\n'
                '#let pTitle = "My Report"\n\n'
                '// pydocmaker:parameters:end\n\n'
                '#image("logo.png", width: 30%)\n\n'
                '// pydocmaker:body:begin\n\n'
                '// pydocmaker:body:end\n')

    TEX_TMPL = ('% pydocmaker:parameters:begin \n\n'
                '% pydocmaker:param:pTitle\n'
                '\\providecommand{\\pTitle}{My Report}\n\n'
                '% pydocmaker:parameters:end \n\n'
                '\\documentclass{article}\n'
                '\\usepackage{graphicx}\n'
                '\\begin{document}\n'
                '\\includegraphics[width=2cm]{logo.png}\n\n'
                '% pydocmaker:body:begin \n\n'
                '% pydocmaker:body:end \n'
                '\\end{document}\n')

    def test_typst_copy_missing_file_refs_unit(self):
        from pydocmaker.backend.ex_typst import _copy_missing_file_refs
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'icon.png').write_bytes(PNG_1PX)
            os.makedirs(os.path.join(td, 'images'))
            Path(td, 'images', 'nested.png').write_bytes(PNG_1PX)
            outdir = Path(td, 'out')
            outdir.mkdir()
            # logo.png is part of the input (a scanned template attachment);
            # icon.png and images/nested.png only exist next to the caller
            inp = {'main.typ': '#image("logo.png") #box[image("icon.png")] '
                               '#image("images/nested.png") #image("nothere.png")',
                   'logo.png': PNG_1PX}
            _copy_missing_file_refs(inp, outdir, td)
            self.assertEqual((outdir / 'icon.png').read_bytes(), PNG_1PX)
            self.assertEqual((outdir / 'images' / 'nested.png').read_bytes(),
                             PNG_1PX)
            # input keys are left to the caller (not copied from the root)
            # and missing refs are skipped
            self.assertFalse((outdir / 'logo.png').exists())
            self.assertFalse((outdir / 'nothere.png').exists())

    def test_tex_copy_missing_file_refs_unit(self):
        from pydocmaker.backend.pdf_maker_tex import _copy_missing_file_refs
        with tempfile.TemporaryDirectory() as td:
            old_cwd = os.getcwd()
            os.chdir(td)
            try:
                Path(td, 'icon.png').write_bytes(PNG_1PX)
                outdir = os.path.join(td, 'out')
                os.makedirs(outdir)
                Path(outdir, 'logo.png').write_bytes(b'attached')
                tex = (r'\includegraphics{icon.png}'
                       r'\includegraphics{logo.png}'
                       r'\includegraphics{missing.png}'
                       r'\includegraphics{\pMacro}')
                _copy_missing_file_refs(tex, outdir)
                self.assertEqual(Path(outdir, 'icon.png').read_bytes(), PNG_1PX)
                self.assertEqual(Path(outdir, 'logo.png').read_bytes(), b'attached')
                self.assertFalse(os.path.exists(os.path.join(outdir, 'missing.png')))
            finally:
                os.chdir(old_cwd)

    @unittest.skipUnless(_typst_available() and _pandoc_available(),
                          'typst engine or pandoc not installed')
    def test_typst_template_attachments_keep_document_images(self):
        # markdown documents reference local images by bare name; with a
        # template that brings attachments the compile is relocated into a
        # tempdir and those files must be brought along
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'icon.png').write_bytes(PNG_1PX)
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            doc = os.path.join(td, 'doc.md')
            Path(doc).write_text('# Doc\n\n![Icon](icon.png)\n\ntext\n',
                                 encoding='utf-8')
            tmpl = os.path.join(td, 'tmpl.typ')
            Path(tmpl).write_text(self.TYP_TMPL, encoding='utf-8')
            out = os.path.join(td, 'out.pdf')
            r = run_cli('build', 'doc.md', '-t', 'tmpl.typ', '-o', out, cwd=td)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = Path(out).read_bytes()
            self.assertTrue(data.startswith(b'%PDF'), data[:20])

    @unittest.skipUnless(_typst_available() and _pandoc_available(),
                          'typst engine or pandoc not installed')
    def test_typst_document_image_in_subfolder(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, 'img'))
            Path(td, 'img', 'icon.png').write_bytes(PNG_1PX)
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            doc = os.path.join(td, 'doc.md')
            Path(doc).write_text('# Doc\n\n![Icon](img/icon.png)\n',
                                 encoding='utf-8')
            tmpl = os.path.join(td, 'tmpl.typ')
            Path(tmpl).write_text(self.TYP_TMPL, encoding='utf-8')
            out = os.path.join(td, 'out.pdf')
            r = run_cli('build', 'doc.md', '-t', 'tmpl.typ', '-o', out, cwd=td)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(Path(out).read_bytes().startswith(b'%PDF'))

    @unittest.skipUnless(_latex_compiler_available() and _pandoc_available(),
                          'no latex compiler or pandoc found')
    def test_tex_template_attachments_keep_document_images(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'icon.png').write_bytes(PNG_1PX)
            Path(td, 'logo.png').write_bytes(PNG_1PX)
            doc = os.path.join(td, 'doc.md')
            Path(doc).write_text('# Doc\n\n![Icon](icon.png)\n\ntext\n',
                                 encoding='utf-8')
            tmpl = os.path.join(td, 'tmpl.tex')
            Path(tmpl).write_text(self.TEX_TMPL, encoding='utf-8')
            out = os.path.join(td, 'out.pdf')
            r = run_cli('build', 'doc.md', '-t', 'tmpl.tex', '-o', out, cwd=td)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = Path(out).read_bytes()
            self.assertTrue(data.startswith(b'%PDF'), data[:20])

    @unittest.skipUnless(_latex_compiler_available(), 'no latex compiler found')
    def test_tex_copy_missing_refs_into_compile_folder(self):
        # the compile folder is zipped with out_format='zip', so the copied
        # document image must show up in the result
        from pydocmaker.backend.pdf_maker_tex import make_pdf_from_tex
        with tempfile.TemporaryDirectory() as td:
            old_cwd = os.getcwd()
            os.chdir(td)
            try:
                Path(td, 'icon.png').write_bytes(PNG_1PX)
                tex = ('\\documentclass{article}\n\\usepackage{graphicx}\n'
                       '\\begin{document}\n\\includegraphics{icon.png}\n'
                       '\\end{document}\n')
                res = make_pdf_from_tex(tex, attachments_dc={'logo.png': PNG_1PX},
                                        out_format='zip', verb=0, ignore_error=True)
                z = zipfile.ZipFile(io.BytesIO(res))
                self.assertIn('icon.png', z.namelist())
                self.assertIn('logo.png', z.namelist())
                self.assertEqual(z.read('icon.png'), PNG_1PX)
            finally:
                os.chdir(old_cwd)


class TestStandaloneSourceBuilds(unittest.TestCase):
    """``build`` of plain .tex/.typ source files must use the matching engine."""

    @unittest.skipUnless(_latex_compiler_available(), 'no latex compiler found')
    def test_plain_tex_builds_to_pdf_with_latex_engine(self):
        # regression: a bare .tex input used to fall back to the configured
        # default pdf engine (typst), which cannot compile latex macros
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, 'report.tex')
            Path(src).write_text(
                '\\documentclass{article}\n\\usepackage{amsmath}\n'
                '\\begin{document}\nHello from LaTeX!\n\\end{document}\n',
                encoding='utf-8')
            out = os.path.join(td, 'report.pdf')
            r = run_cli('build', src, '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(Path(out).read_bytes().startswith(b'%PDF'))

    @unittest.skipUnless(_latex_compiler_available(), 'no latex compiler found')
    def test_plain_tex_with_template_is_wrapped(self):
        # with an explicit template the input is wrapped like any other body
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, 'body.tex')
            Path(src).write_text('Just some \\textbf{body} text.\n',
                                 encoding='utf-8')
            out = os.path.join(td, 'body.pdf')
            r = run_cli('build', src, '-t', 'base.tex', '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(Path(out).read_bytes().startswith(b'%PDF'))

    @unittest.skipUnless(_typst_available(), 'typst engine not installed')
    def test_plain_typ_builds_to_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, 'report.typ')
            Path(src).write_text('= Hello Typst\n\nSome text.\n',
                                 encoding='utf-8')
            out = os.path.join(td, 'report.pdf')
            r = run_cli('build', src, '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(Path(out).read_bytes().startswith(b'%PDF'))


class TestTemplateOptionRejection(unittest.TestCase):
    """Template options must be rejected where they have no effect."""

    def _write_typ(self, td):
        src = os.path.join(td, 'report.typ')
        Path(src).write_text('= Hello Typst\n\nSome text.\n', encoding='utf-8')
        return src

    def test_typ_build_rejects_template_parameters(self):
        # regression: parameters used to be silently ignored on direct builds
        with tempfile.TemporaryDirectory() as td:
            src = self._write_typ(td)
            r = run_cli('build', src, '--pShowSignaturePanel', '0')
            self.assertEqual(r.returncode, 2, r.stdout)
            self.assertIn('does not accept template parameters', r.stderr)
            self.assertIn('--pShowSignaturePanel', r.stderr)

    def test_typ_build_rejects_parameters_json(self):
        with tempfile.TemporaryDirectory() as td:
            src = self._write_typ(td)
            r = run_cli('build', src, '-p', '{"pTitle": "T"}')
            self.assertEqual(r.returncode, 2, r.stdout)
            self.assertIn('does not accept template parameters', r.stderr)

    def test_typ_build_rejects_template(self):
        with tempfile.TemporaryDirectory() as td:
            src = self._write_typ(td)
            r = run_cli('build', src, '-t', 'base.typ')
            self.assertEqual(r.returncode, 2, r.stdout)
            self.assertIn('does not accept a template', r.stderr)

    @unittest.skipUnless(_typst_available(), 'typst engine not installed')
    def test_typ_build_allows_empty_parameters(self):
        with tempfile.TemporaryDirectory() as td:
            src = self._write_typ(td)
            out = os.path.join(td, 'report.pdf')
            r = run_cli('build', src, '-p', '{}', '-o', out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(Path(out).read_bytes().startswith(b'%PDF'))

    def test_check_rejects_template_options(self):
        # the top level parser accepts -t/-p/-a before any subcommand; the
        # non-templating commands must reject them instead of ignoring
        with tempfile.TemporaryDirectory() as td:
            doc = os.path.join(td, 'doc.json')
            Path(doc).write_text('[]', encoding='utf-8')
            r = run_cli('-p', '{"pTitle": "T"}', 'check', doc)
            self.assertEqual(r.returncode, 2, r.stdout)
            self.assertIn('does not accept template options', r.stderr)

    def test_extract_rejects_template_options(self):
        r = run_cli('-t', 'base', 'extract', 'base.typ')
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn('does not accept template options', r.stderr)


class TestParser(unittest.TestCase):

    def test_version(self):
        r = run_cli('--version')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('pydocmaker', r.stdout)

    def test_command_required(self):
        r = run_cli()
        self.assertNotEqual(r.returncode, 0)


if __name__ == '__main__':
    unittest.main()

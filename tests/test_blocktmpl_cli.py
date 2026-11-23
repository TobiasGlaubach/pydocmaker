import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_setup = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(_setup), 'src')
if _src not in sys.path:
    sys.path.insert(0, _src)

MARKED_TEX = """\\documentclass{article}
\\begin{document}
% pydocmaker:parameters:begin
% pydocmaker:param:title
\\providecommand{\\title}{Old Title}
% pydocmaker:parameters:end

% pydocmaker:body:begin
placeholder text
% pydocmaker:body:end
\\end{document}
"""

CLI = [sys.executable, '-m', 'pydocmaker.blocktmpl.cli']


def run_cli(*argv):
    return subprocess.run(CLI + list(argv), capture_output=True, text=True)


class TestCliScaffold(unittest.TestCase):

    def test_scaffold_stdout(self):
        with tempfile.TemporaryDirectory() as td:
            src = '#set page("a4")\nHello\n'
            p = os.path.join(td, 'd.typ')
            Path(p).write_text(src, encoding='utf-8')
            r = run_cli('scaffold', p)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('// pydocmaker:parameters:begin', r.stdout)
            self.assertIn('// pydocmaker:body:begin', r.stdout)
            self.assertEqual(Path(p).read_text(encoding='utf-8'), src)

    def test_scaffold_inplace_with_params(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'd.typ')
            Path(p).write_text('#set page("a4")\nHello\n', encoding='utf-8')
            r = run_cli('scaffold', p, '--param', 'title', '"T"', '--param', 'n', '42', '--inplace')
            self.assertEqual(r.returncode, 0, r.stderr)
            out = Path(p).read_text(encoding='utf-8')
            self.assertIn('#let title = "T"', out)
            self.assertIn('#let n = 42', out)

    def test_scaffold_explicit_format(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'plain.txt')
            Path(p).write_text('fragment\n', encoding='utf-8')
            r = run_cli('scaffold', p, '--format', 'tex')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('% pydocmaker:body:begin', r.stdout)


class TestCliUpdate(unittest.TestCase):

    def test_update_params_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'd.tex')
            Path(p).write_text(MARKED_TEX, encoding='utf-8')
            pj = os.path.join(td, 'params.json')
            Path(pj).write_text(json.dumps({'title': 'CLI Title'}), encoding='utf-8')
            r = run_cli('update', p, '--params', pj)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('\\providecommand{\\title}{CLI Title}', r.stdout)
            self.assertEqual(Path(p).read_text(encoding='utf-8'), MARKED_TEX)

    def test_update_idempotent_via_cli(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'd.tex')
            Path(p).write_text(MARKED_TEX, encoding='utf-8')
            pj = os.path.join(td, 'params.json')
            Path(pj).write_text(json.dumps({'title': 'CLI Title'}), encoding='utf-8')
            r1 = run_cli('update', p, '--params', pj)
            r2 = run_cli('update', p, '--params', pj)
            self.assertEqual(r1.stdout, r2.stdout)


class TestCliInspect(unittest.TestCase):

    def test_inspect_prints_params_table(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'd.tex')
            Path(p).write_text(MARKED_TEX, encoding='utf-8')
            r = run_cli('inspect', p)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('format    : tex', r.stdout)
            self.assertIn('title', r.stdout)
            self.assertIn('Old Title', r.stdout)
            self.assertIn('parameters', r.stdout)
            self.assertIn('body', r.stdout)

    def test_inspect_error_exit_code(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'd.tex')
            Path(p).write_text('% pydocmaker:parameters:begin\nunclosed\n', encoding='utf-8')
            r = run_cli('inspect', p)
            self.assertEqual(r.returncode, 2)
            self.assertIn('error:', r.stderr)


class TestCliRender(unittest.TestCase):

    def test_render_with_body_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'd.tex')
            Path(p).write_text(MARKED_TEX, encoding='utf-8')
            bj = os.path.join(td, 'body.tex')
            Path(bj).write_text('GENERATED \\textbf{BODY}', encoding='utf-8')
            pj = os.path.join(td, 'params.json')
            Path(pj).write_text(json.dumps({'title': 'Rendered'}), encoding='utf-8')
            outp = os.path.join(td, 'out.tex')
            r = run_cli('render', p, '--body-file', bj, '--params', pj, '-o', outp)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = Path(outp).read_text(encoding='utf-8')
            self.assertIn('GENERATED \\textbf{BODY}', out)
            self.assertNotIn('placeholder text', out)
            self.assertIn('\\providecommand{\\title}{Rendered}', out)
            self.assertEqual(Path(p).read_text(encoding='utf-8'), MARKED_TEX)


if __name__ == '__main__':
    unittest.main()

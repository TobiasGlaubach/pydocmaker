import os
import sys
import unittest

_setup = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(_setup), 'src')
if _src not in sys.path:
    sys.path.insert(0, _src)

from pydocmaker.blocktmpl import parse, scaffold, render

TEX_BASE = '\\documentclass{article}\n\\begin{document}\nHello World\n\\end{document}\n'
TYP_BASE = '#set page("a4")\n\nHello World\n'
HTML_BASE = ('<!DOCTYPE html>\n<html>\n<head>\n<title>T</title>\n</head>\n'
             '<body>\nHello World\n</body>\n</html>\n')

TEX_BODY_ONLY = ('\\documentclass{article}\n\\begin{document}\n% pydocmaker:body:begin\n'
                 'placeholder text\n% pydocmaker:body:end\nHello World\n\\end{document}\n')
TYP_BODY_ONLY = ('#set page("a4")\n\n// pydocmaker:body:begin\nplaceholder text\n'
                 '// pydocmaker:body:end\nHello World\n')
HTML_BODY_ONLY = ('<!DOCTYPE html>\n<html>\n<head></head>\n<body>\n<!-- pydocmaker:body:begin -->\n'
                  'placeholder text\n<!-- pydocmaker:body:end -->\n</body>\n</html>\n')

TEX_PARAMS_ONLY = ('\\documentclass{article}\n\\begin{document}\n% pydocmaker:parameters:begin\n'
                   '% pydocmaker:param:title\n\\providecommand{\\title}{My Report}\n'
                   '% pydocmaker:parameters:end\nHello World\n\\end{document}\n')
TYP_PARAMS_ONLY = ('#set page("a4")\n\n// pydocmaker:parameters:begin\n// pydocmaker:param:title\n'
                   '#let title = "My Report"\n// pydocmaker:parameters:end\nHello World\n')
HTML_PARAMS_ONLY = ('<!DOCTYPE html>\n<html>\n<head>\n<!-- pydocmaker:parameters:begin -->\n'
                    '<!-- pydocmaker:param:title -->\n'
                    '<meta name="pydocmaker:param:title" content="My Report">\n'
                    '<!-- pydocmaker:parameters:end -->\n</head>\n<body>\nHello World\n</body>\n</html>\n')

TEX_NO_CLOSING = '\\documentclass{article}\n\\begin{document}\nHello World\n'
TYP_NO_CLOSING = '#set page("a4")\n\nHello World\n'
HTML_NO_CLOSING = '<p>Hello</p>\n'


class TestScaffoldTex(unittest.TestCase):

    def test_both_missing(self):
        expected = ('\\documentclass{article}\n\\begin{document}\nHello World\n'
                    '% pydocmaker:parameters:begin\n% pydocmaker:parameters:end\n'
                    '% pydocmaker:body:begin\nDocument body placeholder\n% pydocmaker:body:end\n'
                    '\\end{document}\n')
        self.assertEqual(scaffold(TEX_BASE, tformat='tex'), expected)

    def test_both_missing_with_params(self):
        expected = ('\\documentclass{article}\n\\begin{document}\nHello World\n'
                    '% pydocmaker:parameters:begin\n'
                    '% pydocmaker:param:title\n\\providecommand{\\title}{My Report}\n'
                    '% pydocmaker:param:n_iter\n\\providecommand{\\niter}{42}\n'
                    '% pydocmaker:parameters:end\n'
                    '% pydocmaker:body:begin\nDocument body placeholder\n% pydocmaker:body:end\n'
                    '\\end{document}\n')
        out = scaffold(TEX_BASE, tformat='tex', params={'title': 'My Report', 'n_iter': 42})
        self.assertEqual(out, expected)
        doc = parse(out)
        self.assertEqual(doc.params_section.params['n_iter'].value, 42)

    def test_body_only(self):
        expected = ('\\documentclass{article}\n\\begin{document}\n'
                    '% pydocmaker:parameters:begin\n% pydocmaker:parameters:end\n'
                    '% pydocmaker:body:begin\nplaceholder text\n% pydocmaker:body:end\n'
                    'Hello World\n\\end{document}\n')
        self.assertEqual(scaffold(TEX_BODY_ONLY, tformat='tex'), expected)

    def test_params_only(self):
        expected = ('\\documentclass{article}\n\\begin{document}\n'
                    '% pydocmaker:parameters:begin\n'
                    '% pydocmaker:param:title\n\\providecommand{\\title}{My Report}\n'
                    '% pydocmaker:parameters:end\n'
                    '% pydocmaker:body:begin\nDocument body placeholder\n% pydocmaker:body:end\n'
                    'Hello World\n\\end{document}\n')
        self.assertEqual(scaffold(TEX_PARAMS_ONLY, tformat='tex'), expected)

    def test_no_closing_statement_warns(self):
        expected = (TEX_NO_CLOSING +
                    '% pydocmaker:parameters:begin\n% pydocmaker:parameters:end\n'
                    '% pydocmaker:body:begin\nDocument body placeholder\n% pydocmaker:body:end\n')
        with self.assertLogs('pydocmaker', level='WARNING') as captured:
            out = scaffold(TEX_NO_CLOSING, tformat='tex')
        self.assertEqual(out, expected)
        self.assertTrue(any('will not compile standalone as-is' in m for m in captured.output))

    def test_empty_file(self):
        expected = ('% pydocmaker:parameters:begin\n% pydocmaker:parameters:end\n'
                    '% pydocmaker:body:begin\nDocument body placeholder\n% pydocmaker:body:end\n')
        self.assertEqual(scaffold('', tformat='tex'), expected)

    def test_idempotent(self):
        once = scaffold(TEX_BASE, tformat='tex', params={'title': 'T'})
        twice = scaffold(once, tformat='tex', params={'title': 'T'})
        self.assertEqual(once, twice)
        self.assertEqual(twice, scaffold(TEX_BASE, tformat='tex', params={'title': 'T'}))

    def test_crlf_preserved(self):
        src = TEX_BASE.replace('\n', '\r\n')
        out = scaffold(src, tformat='tex')
        self.assertNotIn('\\\\r', repr(out.replace('\r\n', '')))
        self.assertTrue(out.replace('% pydocmaker:parameters:begin\r\n', '').count('\r\n') >= 4)
        self.assertIn('% pydocmaker:parameters:begin\r\n', out)
        self.assertNotIn('\r\n\r', out.replace('\r\n', '\n'))

    def test_render_after_scaffold_compiles_layout(self):
        out = scaffold(TEX_BASE, tformat='tex', params={'title': 'T'})
        doc = parse(out)
        self.assertLess(doc.params_section.begin_line, doc.body_section.begin_line)
        lines = out.splitlines()
        i_end = lines.index('\\end{document}')
        self.assertEqual(lines[i_end - 1], '% pydocmaker:body:end')
        self.assertLess(lines.index('% pydocmaker:parameters:begin'), i_end)


class TestScaffoldTyp(unittest.TestCase):

    def test_both_missing_at_eof(self):
        expected = (TYP_BASE +
                    '// pydocmaker:parameters:begin\n// pydocmaker:parameters:end\n'
                    '// pydocmaker:body:begin\nDocument body placeholder\n// pydocmaker:body:end\n')
        self.assertEqual(scaffold(TYP_BASE, tformat='typ'), expected)

    def test_body_only(self):
        expected = ('#set page("a4")\n\n'
                    '// pydocmaker:parameters:begin\n// pydocmaker:parameters:end\n'
                    '// pydocmaker:body:begin\nplaceholder text\n// pydocmaker:body:end\n'
                    'Hello World\n')
        self.assertEqual(scaffold(TYP_BODY_ONLY, tformat='typ'), expected)

    def test_params_only(self):
        expected = ('#set page("a4")\n\n'
                    '// pydocmaker:parameters:begin\n'
                    '// pydocmaker:param:title\n#let title = "My Report"\n'
                    '// pydocmaker:parameters:end\n'
                    '// pydocmaker:body:begin\nDocument body placeholder\n// pydocmaker:body:end\n'
                    'Hello World\n')
        self.assertEqual(scaffold(TYP_PARAMS_ONLY, tformat='typ'), expected)

    def test_no_closing_statement_no_warning(self):
        expected = (TYP_NO_CLOSING +
                    '// pydocmaker:parameters:begin\n// pydocmaker:parameters:end\n'
                    '// pydocmaker:body:begin\nDocument body placeholder\n// pydocmaker:body:end\n')
        out = scaffold(TYP_NO_CLOSING, tformat='typ')
        self.assertEqual(out, expected)

    def test_empty_file(self):
        expected = ('// pydocmaker:parameters:begin\n// pydocmaker:parameters:end\n'
                    '// pydocmaker:body:begin\nDocument body placeholder\n// pydocmaker:body:end\n')
        self.assertEqual(scaffold('', tformat='typ'), expected)

    def test_idempotent(self):
        once = scaffold(TYP_BASE, tformat='typ', params={'a': 1})
        twice = scaffold(once, tformat='typ', params={'a': 1})
        self.assertEqual(once, twice)


class TestScaffoldHtml(unittest.TestCase):

    def test_both_missing_params_in_head(self):
        expected = ('<!DOCTYPE html>\n<html>\n<head>\n<title>T</title>\n'
                    '<!-- pydocmaker:parameters:begin -->\n<!-- pydocmaker:parameters:end -->\n'
                    '</head>\n<body>\nHello World\n'
                    '<!-- pydocmaker:body:begin -->\n<p>Document body placeholder</p>\n'
                    '<!-- pydocmaker:body:end -->\n</body>\n</html>\n')
        self.assertEqual(scaffold(HTML_BASE, tformat='html'), expected)

    def test_both_missing_with_params(self):
        expected = ('<!DOCTYPE html>\n<html>\n<head>\n<title>T</title>\n'
                    '<!-- pydocmaker:parameters:begin -->\n'
                    '<!-- pydocmaker:param:title -->\n'
                    '<meta name="pydocmaker:param:title" content="My Report">\n'
                    '<!-- pydocmaker:parameters:end -->\n'
                    '</head>\n<body>\nHello World\n'
                    '<!-- pydocmaker:body:begin -->\n<p>Document body placeholder</p>\n'
                    '<!-- pydocmaker:body:end -->\n</body>\n</html>\n')
        self.assertEqual(scaffold(HTML_BASE, tformat='html', params={'title': 'My Report'}), expected)

    def test_body_only_params_adjacent(self):
        expected = ('<!DOCTYPE html>\n<html>\n<head></head>\n<body>\n'
                    '<!-- pydocmaker:parameters:begin -->\n<!-- pydocmaker:parameters:end -->\n'
                    '<!-- pydocmaker:body:begin -->\nplaceholder text\n<!-- pydocmaker:body:end -->\n'
                    '</body>\n</html>\n')
        self.assertEqual(scaffold(HTML_BODY_ONLY, tformat='html'), expected)

    def test_params_only(self):
        expected = ('<!DOCTYPE html>\n<html>\n<head>\n'
                    '<!-- pydocmaker:parameters:begin -->\n'
                    '<!-- pydocmaker:param:title -->\n'
                    '<meta name="pydocmaker:param:title" content="My Report">\n'
                    '<!-- pydocmaker:parameters:end -->\n'
                    '<!-- pydocmaker:body:begin -->\n<p>Document body placeholder</p>\n'
                    '<!-- pydocmaker:body:end -->\n</head>\n<body>\nHello World\n</body>\n</html>\n')
        self.assertEqual(scaffold(HTML_PARAMS_ONLY, tformat='html'), expected)

    def test_no_closing_statement_warns(self):
        expected = (HTML_NO_CLOSING +
                    '<!-- pydocmaker:parameters:begin -->\n<!-- pydocmaker:parameters:end -->\n'
                    '<!-- pydocmaker:body:begin -->\n<p>Document body placeholder</p>\n'
                    '<!-- pydocmaker:body:end -->\n')
        with self.assertLogs('pydocmaker', level='WARNING') as captured:
            out = scaffold(HTML_NO_CLOSING, tformat='html')
        self.assertEqual(out, expected)
        self.assertTrue(any('</body>' in m for m in captured.output))

    def test_empty_file(self):
        expected = ('<!-- pydocmaker:parameters:begin -->\n<!-- pydocmaker:parameters:end -->\n'
                    '<!-- pydocmaker:body:begin -->\n<p>Document body placeholder</p>\n'
                    '<!-- pydocmaker:body:end -->\n')
        self.assertEqual(scaffold('', tformat='html'), expected)

    def test_idempotent(self):
        once = scaffold(HTML_BASE, tformat='html', params={'title': 'T'})
        twice = scaffold(once, tformat='html', params={'title': 'T'})
        self.assertEqual(once, twice)

    def test_body_placeholder_override(self):
        out = scaffold(TEX_BASE, tformat='tex', body='CUSTOM PLACEHOLDER')
        self.assertIn('CUSTOM PLACEHOLDER', out)


class TestRenderAfterScaffold(unittest.TestCase):

    def test_full_cycle_tex(self):
        scaffolded = scaffold(TEX_BASE, tformat='tex', params={'title': 'T'})
        rendered = render(scaffolded, 'GENERATED BODY', params={'title': 'Rendered'})
        self.assertIn('GENERATED BODY', rendered)
        self.assertIn('\\providecommand{\\title}{Rendered}', rendered)
        self.assertNotIn('Document body placeholder', rendered)
        self.assertIn('\\end{document}', rendered)
        self.assertLess(rendered.index('% pydocmaker:parameters:begin'),
                        rendered.index('% pydocmaker:body:begin'))
        again = render(rendered, 'GENERATED BODY', params={'title': 'Rendered'})
        self.assertEqual(rendered, again)


if __name__ == '__main__':
    unittest.main()

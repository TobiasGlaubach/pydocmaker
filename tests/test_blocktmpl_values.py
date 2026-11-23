import os
import sys
import unittest

_setup = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(_setup), 'src')
if _src not in sys.path:
    sys.path.insert(0, _src)

from pydocmaker.blocktmpl import parse, update_params, scaffold, render
from pydocmaker.blocktmpl import adapter_html, adapter_tex, adapter_typ

USER_TEX_EXAMPLE = """\\documentclass{article}
\\begin{document}
% pydocmaker:parameters:begin
% pydocmaker:param:title
\\providecommand{\\title}{My Report}
% pydocmaker:param:n_iter
\\providecommand{\\niter}{42}
% pydocmaker:param:acronyms
\\newcommand{\\acronyms}{%
\\begin{description}
\\item{SNR}{Signal-to-Noise Ratio}
\\item{FFT}{Fast Fourier Transform}
\\end{description}
}
% pydocmaker:param:events
\\newcommand{\\events}{%
\\begin{itemize}
\\item First item
\\item Second item
\\end{itemize}
}
% pydocmaker:parameters:end

% pydocmaker:body:begin
placeholder text
% pydocmaker:body:end
\\end{document}
"""

ROUNDTRIP_VALUES = [
    ('str', 'My Report'),
    ('int', 42),
    ('float', 3.14),
    ('bool', True),
    ('bool2', False),
    ('none', None),
    ('dict', {'SNR': 'Signal-to-Noise Ratio', 'FFT': 'Fast Fourier Transform'}),
    ('list', ['First item', 'Second item']),
]


class TestLatexCodecs(unittest.TestCase):

    def test_roundtrip_matrix(self):
        for name, v in ROUNDTRIP_VALUES:
            with self.subTest(name=name):
                src = scaffold('', tformat='tex', params={name: v}, body='X')
                doc = parse(src)
                p = doc.params_section.params[name]
                if v is None:
                    self.assertIsNone(p.value)
                else:
                    self.assertEqual(p.value, v)
                    self.assertEqual(p.kind, {'dict': 'dict', 'list': 'list'}.get(name, 'scalar'))

    def test_escaping(self):
        tricky = '100% of \\LaTeX & $x_1$ #1 _a_ {b} ~ ^'
        src = scaffold('', tformat='tex', params={'t': tricky}, body='X')
        doc = parse(src)
        self.assertEqual(doc.params_section.params['t'].value, tricky)

    def test_macro_name_strips_underscores(self):
        self.assertEqual(adapter_tex.latex_macro_name('n_iter'), 'niter')

    def test_user_example_roundtrip_exactly(self):
        doc = parse(USER_TEX_EXAMPLE)
        params = doc.params_section.params
        self.assertEqual(params['title'].value, 'My Report')
        self.assertEqual(params['n_iter'].value, 42)
        self.assertEqual(params['acronyms'].value, {'SNR': 'Signal-to-Noise Ratio', 'FFT': 'Fast Fourier Transform'})
        self.assertEqual(params['acronyms'].kind, 'dict')
        self.assertEqual(params['events'].value, ['First item', 'Second item'])
        self.assertEqual(params['events'].kind, 'list')
        out = update_params(USER_TEX_EXAMPLE, {
            'title': 'My Report',
            'n_iter': 42,
            'acronyms': {'SNR': 'Signal-to-Noise Ratio', 'FFT': 'Fast Fourier Transform'},
            'events': ['First item', 'Second item'],
        })
        self.assertEqual(out, USER_TEX_EXAMPLE)

    def test_serialize_dict_matches_plan_example(self):
        s = adapter_tex.latex_serialize_param('acronyms', {'SNR': 'Signal-to-Noise Ratio', 'FFT': 'Fast Fourier Transform'})
        expected = (
            '\\newcommand{\\acronyms}{%\n'
            '\\begin{description}\n'
            '\\item{SNR}{Signal-to-Noise Ratio}\n'
            '\\item{FFT}{Fast Fourier Transform}\n'
            '\\end{description}\n'
            '}'
        )
        self.assertEqual(s, expected)

    def test_serialize_list_matches_plan_example(self):
        s = adapter_tex.latex_serialize_param('events', ['First item', 'Second item'])
        expected = (
            '\\newcommand{\\events}{%\n'
            '\\begin{itemize}\n'
            '\\item First item\n'
            '\\item Second item\n'
            '\\end{itemize}\n'
            '}'
        )
        self.assertEqual(s, expected)

    def test_nested_dict_value(self):
        nested = {'outer': {'a': 1}, 'lst': [1, 2]}
        src = scaffold('', tformat='tex', params={'n': nested}, body='X')
        doc = parse(src)
        self.assertEqual(doc.params_section.params['n'].value, nested)


class TestTypstCodecs(unittest.TestCase):

    def test_roundtrip_matrix(self):
        for name, v in ROUNDTRIP_VALUES:
            with self.subTest(name=name):
                src = scaffold('', tformat='typ', params={name: v}, body='X')
                doc = parse(src)
                p = doc.params_section.params[name]
                if v is None:
                    self.assertIsNone(p.value)
                else:
                    self.assertEqual(p.value, v)

    def test_escaping(self):
        tricky = 'quote " backslash \\ newline \n tab \t end'
        src = scaffold('', tformat='typ', params={'t': tricky}, body='X')
        doc = parse(src)
        self.assertEqual(doc.params_section.params['t'].value, tricky)

    def test_single_element_list(self):
        src = scaffold('', tformat='typ', params={'l': ['only']}, body='X')
        doc = parse(src)
        self.assertEqual(doc.params_section.params['l'].value, ['only'])
        self.assertIn("#let l = (\"only\",)", src)

    def test_empty_containers(self):
        src = scaffold('', tformat='typ', params={'d': {}, 'l': []}, body='X')
        self.assertIn('#let d = (:)', src)
        self.assertIn('#let l = ()', src)
        doc = parse(src)
        self.assertEqual(doc.params_section.params['d'].value, {})
        self.assertEqual(doc.params_section.params['l'].value, [])

    def test_nested_structures(self):
        nested = {'a': [1, 2, {'b': 'x'}], 'n': None}
        src = scaffold('', tformat='typ', params={'n': nested}, body='X')
        doc = parse(src)
        self.assertEqual(doc.params_section.params['n'].value, nested)

    def test_string_key_dict(self):
        d = {'my key': 'v', 'ok_key': 2}
        src = scaffold('', tformat='typ', params={'d': d}, body='X')
        doc = parse(src)
        self.assertEqual(doc.params_section.params['d'].value, d)


class TestHtmlCodecs(unittest.TestCase):

    def test_roundtrip_matrix(self):
        for name, v in ROUNDTRIP_VALUES:
            with self.subTest(name=name):
                src = scaffold('', tformat='html', params={name: v}, body='X')
                doc = parse(src)
                p = doc.params_section.params[name]
                if v is None:
                    self.assertIsNone(p.value)
                else:
                    self.assertEqual(p.value, v)

    def test_scalar_meta_escaping(self):
        tricky = 'Tom & Jerry <"great">'
        src = scaffold('', tformat='html', params={'t': tricky}, body='X')
        self.assertIn('content="Tom &amp; Jerry &lt;&quot;great&quot;&gt;"', src)
        doc = parse(src)
        self.assertEqual(doc.params_section.params['t'].value, tricky)

    def test_dict_uses_json_script(self):
        d = {'a': 1, 'b': [1, 2]}
        src = scaffold('', tformat='html', params={'d': d}, body='X')
        self.assertIn('<script type="application/json" data-pydocmaker-param="d">', src)
        doc = parse(src)
        self.assertEqual(doc.params_section.params['d'].value, d)
        self.assertEqual(doc.params_section.params['d'].kind, 'dict')

    def test_script_breakout_escaped(self):
        d = {'x': '</script><script>alert(1)</script>'}
        src = scaffold('', tformat='html', params={'d': d}, body='X')
        self.assertNotIn('</script><script>alert(1)', src)
        doc = parse(src)
        self.assertEqual(doc.params_section.params['d'].value, d)

    def test_newline_in_scalar(self):
        v = 'line1\nline2'
        src = scaffold('', tformat='html', params={'t': v}, body='X')
        doc = parse(src)
        self.assertEqual(doc.params_section.params['t'].value, v)


class TestUpdateIdempotency(unittest.TestCase):

    def test_update_params_idempotent_tex(self):
        once = update_params(USER_TEX_EXAMPLE, {'title': 'New Title', 'n_iter': 7})
        twice = update_params(once, {'title': 'New Title', 'n_iter': 7})
        self.assertEqual(once, twice)
        doc = parse(once)
        self.assertEqual(doc.params_section.params['title'].value, 'New Title')
        self.assertEqual(doc.params_section.params['n_iter'].value, 7)
        self.assertEqual(doc.params_section.params['acronyms'].value,
                         {'SNR': 'Signal-to-Noise Ratio', 'FFT': 'Fast Fourier Transform'})

    def test_update_params_idempotent_typ(self):
        src = scaffold('', tformat='typ', params={'a': 1, 'b': 'x'}, body='X')
        once = update_params(src, {'a': 2, 'new_param': [1, 2]})
        twice = update_params(once, {'a': 2, 'new_param': [1, 2]})
        self.assertEqual(once, twice)
        doc = parse(once)
        self.assertEqual(doc.params_section.params['a'].value, 2)
        self.assertEqual(doc.params_section.params['new_param'].value, [1, 2])

    def test_update_preserves_static_and_order(self):
        src = USER_TEX_EXAMPLE.replace(
            '\\providecommand{\\title}{My Report}\n',
            '\\providecommand{\\title}{My Report}\n% keep me\n')
        out = update_params(src, {'title': 'Changed'})
        self.assertIn('% keep me\n', out)
        lines = out.splitlines()
        idx_marker = lines.index('% pydocmaker:param:title')
        self.assertEqual(lines[idx_marker + 1], '\\providecommand{\\title}{Changed}')
        self.assertEqual(lines[idx_marker + 2], '% keep me')

    def test_update_appends_unknown_params(self):
        out = update_params(USER_TEX_EXAMPLE, {'extra': 'xyz'})
        doc = parse(out)
        self.assertEqual(doc.params_section.params['extra'].value, 'xyz')
        keys = list(doc.params_section.params.keys())
        self.assertEqual(keys[-1], 'extra')

    def test_update_none_removes_assignment(self):
        out = update_params(USER_TEX_EXAMPLE, {'n_iter': None})
        doc = parse(out)
        p = doc.params_section.params['n_iter']
        self.assertIsNone(p.value)
        self.assertIn('% pydocmaker:param:n_iter', out)
        self.assertNotIn('\\providecommand{\\niter}', out)

    def test_body_reserved(self):
        from pydocmaker.blocktmpl import BodyReservedError
        for fun, args in ((update_params, (USER_TEX_EXAMPLE, {'body': 'x'})),
                          (render, (USER_TEX_EXAMPLE, 'X', {'body': 'x'}))):
            with self.assertRaises(BodyReservedError) as ctx:
                fun(*args)
            self.assertIn('reserved for the document body', str(ctx.exception))

    def test_raw_assignment_preserved(self):
        src = USER_TEX_EXAMPLE.replace(
            '\\providecommand{\\niter}{42}\n',
            '\\providecommand{\\niter}{unclosed brace { here}\n')
        doc = parse(src)
        self.assertEqual(doc.params_section.params['n_iter'].kind, 'raw')
        out = update_params(src, {'title': 'T2'})
        self.assertIn('\\providecommand{\\niter}{unclosed brace { here}', out)
        out2 = update_params(src, {'n_iter': 5})
        self.assertIn('\\providecommand{\\niter}{5}', out2)


class TestRenderParams(unittest.TestCase):

    def test_render_replaces_body_and_keeps_params(self):
        out = render(USER_TEX_EXAMPLE, 'NEW BODY', params=None)
        self.assertIn('NEW BODY', out)
        self.assertNotIn('placeholder text', out)
        self.assertIn('\\providecommand{\\title}{My Report}', out)
        self.assertIn('% pydocmaker:parameters:begin', out)
        self.assertIn('\\end{document}', out)

    def test_render_overrides_param(self):
        out = render(USER_TEX_EXAMPLE, 'B', params={'title': 'Override'})
        self.assertIn('\\providecommand{\\title}{Override}', out)
        self.assertNotIn('My Report', out)

    def test_render_unknown_param_appended(self):
        out = render(USER_TEX_EXAMPLE, 'B', params={'fresh': [1, 2]})
        self.assertIn('% pydocmaker:param:fresh', out)
        self.assertIn('\\newcommand{\\fresh}{%', out)

    def test_render_equal_value_untouched(self):
        marker = '\\providecommand{\\title}{My Report}'
        out = render(USER_TEX_EXAMPLE, 'B', params={'title': 'My Report'})
        self.assertIn(marker, out)

    def test_render_idempotent(self):
        once = render(USER_TEX_EXAMPLE, 'BODY TEXT', params={'title': 'T'})
        twice = render(once, 'BODY TEXT', params={'title': 'T'})
        self.assertEqual(once, twice)

    def test_render_unmarked_source_scaffolds(self):
        out = render('\\begin{document}\n\\end{document}\n', 'HELLO', params={'title': 'T'})
        self.assertIn('% pydocmaker:body:begin', out)
        self.assertIn('HELLO', out)
        self.assertIn('\\providecommand{\\title}{T}', out)
        self.assertLess(out.index('\\providecommand{\\title}{T}'), out.index('% pydocmaker:body:begin'))


if __name__ == '__main__':
    unittest.main()

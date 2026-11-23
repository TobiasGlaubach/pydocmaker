import os
import sys
import unittest

_setup = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(_setup), 'src')
if _src not in sys.path:
    sys.path.insert(0, _src)

from pydocmaker.blocktmpl import parse, detect, detect_format
from pydocmaker.blocktmpl.model import MalformedBlockError, UnsupportedFormatError


TEX_PARAMS = """\\documentclass{article}
\\begin{document}
% pydocmaker:parameters:begin
% pydocmaker:param:title
\\providecommand{\\title}{My Report}
% pydocmaker:param:n_iter
\\providecommand{\\niter}{42}
% pydocmaker:parameters:end

% pydocmaker:body:begin
placeholder text
% pydocmaker:body:end
\\end{document}
"""

TYP_PARAMS = """#set page("a4")
// pydocmaker:parameters:begin
// pydocmaker:param:title
#let title = "My Report"
// pydocmaker:parameters:end

// pydocmaker:body:begin
placeholder text
// pydocmaker:body:end
"""

HTML_PARAMS = """<!DOCTYPE html>
<html>
<head>
<!-- pydocmaker:parameters:begin -->
<!-- pydocmaker:param:title -->
<meta name="pydocmaker:param:title" content="My Report">
<!-- pydocmaker:parameters:end -->
</head>
<body>
<!-- pydocmaker:body:begin -->
placeholder text
<!-- pydocmaker:body:end -->
</body>
</html>
"""


class TestDetect(unittest.TestCase):

    def test_detect_true_all_formats(self):
        self.assertTrue(detect(TEX_PARAMS))
        self.assertTrue(detect(TYP_PARAMS))
        self.assertTrue(detect(HTML_PARAMS))

    def test_detect_false_plain_sources(self):
        self.assertFalse(detect('\\documentclass{article}\n\\begin{document}\nHello\n\\end{document}\n'))
        self.assertFalse(detect('#set page("a4")\nHello\n'))
        self.assertFalse(detect('<!DOCTYPE html>\n<html><body>Hello</body></html>\n'))
        self.assertFalse(detect('{{ body }}'))
        self.assertFalse(detect(''))
        self.assertFalse(detect(None))

    def test_detect_accepts_leading_trailing_whitespace(self):
        self.assertTrue(detect('  % pydocmaker:body:begin  \n'))
        self.assertTrue(detect('\t// pydocmaker:parameters:end\n'))
        self.assertTrue(detect('   <!-- pydocmaker:body:begin -->\n'))

    def test_detect_rejects_markers_not_alone_on_line(self):
        self.assertFalse(detect('text % pydocmaker:body:begin\n'))
        self.assertFalse(detect('<p><!-- pydocmaker:body:begin --></p>\n'))
        self.assertFalse(detect('#let x = 1 // pydocmaker:body:begin\n'))

    def test_detect_format(self):
        self.assertEqual(detect_format(TEX_PARAMS), 'tex')
        self.assertEqual(detect_format(TYP_PARAMS), 'typ')
        self.assertEqual(detect_format(HTML_PARAMS), 'html')
        self.assertIsNone(detect_format('no markers here'))

    def test_detect_with_tformat_filter(self):
        self.assertTrue(detect(TEX_PARAMS, tformat='tex'))
        self.assertTrue(detect(TEX_PARAMS, tformat='latex'))


class TestParseTex(unittest.TestCase):

    def test_sections_and_params(self):
        doc = parse(TEX_PARAMS)
        self.assertEqual(doc.tformat, 'tex')
        self.assertTrue(doc.had_markers)
        self.assertIsNotNone(doc.params_section)
        self.assertIsNotNone(doc.body_section)
        self.assertEqual(doc.warnings, [])
        params = doc.params_section.params
        self.assertEqual(list(params.keys()), ['title', 'n_iter'])
        self.assertEqual(params['title'].value, 'My Report')
        self.assertEqual(params['title'].kind, 'scalar')
        self.assertEqual(params['n_iter'].value, 42)
        self.assertEqual(params['n_iter'].kind, 'scalar')

    def test_spans(self):
        doc = parse(TEX_PARAMS)
        sec = doc.params_section
        src = doc.source
        self.assertEqual(src[sec.begin_span[0]:sec.begin_span[1]], '% pydocmaker:parameters:begin')
        self.assertEqual(src[sec.end_span[0]:sec.end_span[1]], '% pydocmaker:parameters:end')
        p = sec.params['title']
        self.assertEqual(src[p.marker_span[0]:p.marker_span[1]], '% pydocmaker:param:title')
        self.assertEqual(src[p.assign_span[0]:p.assign_span[1]], '\\providecommand{\\title}{My Report}')
        self.assertEqual(p.assign_lines, (sec.begin_line + 2, sec.begin_line + 3))

    def test_static_lines_preserved(self):
        src = TEX_PARAMS.replace(
            '\\providecommand{\\niter}{42}\n',
            '\\providecommand{\\niter}{42}\n% a static note\n\\usepackage{xcolor}\n')
        doc = parse(src)
        self.assertIn('% a static note', doc.params_section.static_lines)
        self.assertIn('\\usepackage{xcolor}', doc.params_section.static_lines)
        self.assertEqual(doc.params_section.params['n_iter'].value, 42)

    def test_static_before_assignment_leaves_param_unset(self):
        src = TEX_PARAMS.replace(
            '% pydocmaker:param:n_iter\n',
            '% pydocmaker:param:n_iter\n% a static note\n\\usepackage{xcolor}\n')
        doc = parse(src)
        p = doc.params_section.params['n_iter']
        self.assertIsNone(p.value)
        self.assertIn('% a static note', doc.params_section.static_lines)
        self.assertIn('\\usepackage{xcolor}', doc.params_section.static_lines)
        self.assertIn('\\providecommand{\\niter}{42}', doc.params_section.static_lines)

    def test_lenient_unclosed_section(self):
        src = TEX_PARAMS.replace('% pydocmaker:parameters:end\n', '')
        doc = parse(src, strict=False)
        self.assertEqual(doc.params_section.end_line, -1)
        self.assertTrue(any('unclosed' in w for w in doc.warnings))
        with self.assertRaises(MalformedBlockError):
            parse(src)

    def test_lenient_stray_end(self):
        src = TEX_PARAMS.replace('% pydocmaker:parameters:begin\n', '')
        doc = parse(src, strict=False)
        self.assertTrue(any('stray' in w for w in doc.warnings))
        with self.assertRaises(MalformedBlockError):
            parse(src)

    def test_duplicate_sections(self):
        src = TEX_PARAMS + '% pydocmaker:parameters:begin\n% pydocmaker:param:x\n\\providecommand{\\x}{1}\n% pydocmaker:parameters:end\n'
        doc = parse(src, strict=False)
        self.assertEqual(doc.params_section.params['title'].value, 'My Report')
        self.assertNotIn('x', doc.params_section.params)
        self.assertTrue(any('duplicate' in w for w in doc.warnings))
        with self.assertRaises(MalformedBlockError):
            parse(src)

    def test_param_without_assignment(self):
        src = TEX_PARAMS.replace('\\providecommand{\\niter}{42}\n', '')
        doc = parse(src)
        p = doc.params_section.params['n_iter']
        self.assertIsNone(p.value)
        self.assertEqual(p.kind, 'scalar')
        self.assertEqual(p.raw, '')

    def test_body_reserved_param_marker_is_static(self):
        src = TEX_PARAMS.replace('% pydocmaker:param:n_iter\n', '% pydocmaker:param:body\n')
        doc = parse(src)
        self.assertNotIn('body', doc.params_section.params)
        self.assertTrue(any('reserved' in w for w in doc.warnings))

    def test_stray_param_marker_outside_section(self):
        src = TEX_PARAMS + '% pydocmaker:param:loose\n'
        doc = parse(src)
        self.assertTrue(any('outside of a parameters block' in w for w in doc.warnings))


class TestParseTyp(unittest.TestCase):

    def test_sections_and_params(self):
        doc = parse(TYP_PARAMS)
        self.assertEqual(doc.tformat, 'typ')
        params = doc.params_section.params
        self.assertEqual(params['title'].value, 'My Report')

    def test_body_section(self):
        doc = parse(TYP_PARAMS)
        self.assertEqual(doc.body_section.begin_line, 6)
        self.assertEqual(doc.body_section.end_line, 8)

    def test_unclosed_section_strict_raises(self):
        with self.assertRaises(MalformedBlockError):
            parse(TYP_PARAMS.replace('// pydocmaker:body:end\n', ''))


class TestParseHtml(unittest.TestCase):

    def test_sections_and_params(self):
        doc = parse(HTML_PARAMS)
        self.assertEqual(doc.tformat, 'html')
        params = doc.params_section.params
        self.assertEqual(params['title'].value, 'My Report')
        self.assertEqual(params['title'].kind, 'scalar')
        self.assertEqual(doc.body_section.begin_line, 9)

    def test_html_marker_requires_comment_close(self):
        src = HTML_PARAMS.replace('<!-- pydocmaker:body:end -->', '<!-- pydocmaker:body:end')
        doc = parse(src, strict=False)
        self.assertTrue(doc.had_markers)
        self.assertTrue(any('unclosed' in w for w in doc.warnings))
        with self.assertRaises(MalformedBlockError):
            parse(src)


class TestLineEndingsAndEncoding(unittest.TestCase):

    def test_crlf_roundtrip(self):
        src = TEX_PARAMS.replace('\n', '\r\n')
        doc = parse(src)
        sec = doc.params_section
        p = sec.params['title']
        self.assertEqual(doc.source[p.assign_span[0]:p.assign_span[1]], '\\providecommand{\\title}{My Report}')
        self.assertEqual(doc.body_section.begin_span[0], doc.source.index('% pydocmaker:body:begin'))

    def test_bom_preserved(self):
        src = '﻿' + TEX_PARAMS
        doc = parse(src)
        self.assertTrue(doc.source.startswith('﻿'))
        self.assertEqual(doc.params_section.params['title'].value, 'My Report')

    def test_explicit_tformat_wins_on_empty(self):
        doc = parse('', tformat='tex')
        self.assertEqual(doc.tformat, 'tex')
        self.assertFalse(doc.had_markers)
        self.assertIsNone(doc.params_section)

    def test_undetectable_format_raises(self):
        with self.assertRaises(UnsupportedFormatError):
            parse('plain text without any markers')
        doc = parse('plain text without any markers', tformat='typ')
        self.assertEqual(doc.tformat, 'typ')


if __name__ == '__main__':
    unittest.main()

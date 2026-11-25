import os
import sys
import unittest

import jinja2

_setup = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(_setup), 'src')
if _src not in sys.path:
    sys.path.insert(0, _src)

import pydocmaker as pyd
from pydocmaker import blocktmpl
from pydocmaker.param_mapping import LEGACY_PARAM_MAP, is_empty_param_value, map_legacy_params
from pydocmaker.templating import DocTemplate


# legacy metadata as produced e.g. by the JupyRun test system
LEGACY_EXAMPLE = {
    "project": "INAF MeerKAT Band5b Receiver",
    "title": "Internal Report - TE-RFHC  - Full Receiver - Pretest",
    "doc_no": "B5bRx-0060-TE-RFHC-1",
    "revision": "A",
    "status": "Released",
    "date": "2025-08-12",
    "author": "sh",
    "approved_by": "T. Glaubach (procedure only)",
    "released_by": "JupyRun Testsystem",
    "confidential": True,
    "purpose": "",
    "scope": "",
}

# new-generation parameter names
NEW_NAMES = ['pProject', 'pDocTitle', 'pDocNo', 'pDocRevision', 'pDocStatus',
             'pDate', 'pAuthorName', 'pApprovedBy', 'pReleasedBy',
             'pIsConfidential']

# block template of the new generation (declares the new parameter names)
NEW_TYP_TEMPLATE = """// pydocmaker:parameters:begin
// pydocmaker:param:pProject
#let pProject = ""
// pydocmaker:param:pDocTitle
#let pDocTitle = ""
// pydocmaker:param:pDocNo
#let pDocNo = ""
// pydocmaker:param:pDocRevision
#let pDocRevision = ""
// pydocmaker:param:pDocStatus
#let pDocStatus = ""
// pydocmaker:param:pDate
#let pDate = ""
// pydocmaker:param:pAuthorName
#let pAuthorName = ""
// pydocmaker:param:pApprovedBy
#let pApprovedBy = ""
// pydocmaker:param:pReleasedBy
#let pReleasedBy = ""
// pydocmaker:param:pIsConfidential
#let pIsConfidential = false
// pydocmaker:param:pAcronyms
#let pAcronyms = (:)
// pydocmaker:parameters:end

#set page("a4")

// pydocmaker:body:begin
placeholder text
// pydocmaker:body:end
"""

# block template of the old generation (declares the legacy-style name)
OLD_TYP_TEMPLATE = """// pydocmaker:parameters:begin
// pydocmaker:param:title
#let title = "Block Default Title"
// pydocmaker:parameters:end

// pydocmaker:body:begin
placeholder text
// pydocmaker:body:end
"""


# block template with non-empty placeholder defaults (like the tdd templates)
PLACEHOLDER_TYP_TEMPLATE = """// pydocmaker:parameters:begin
// pydocmaker:param:pProject
#let pProject = "Example Project"
// pydocmaker:param:pDocTitle
#let pDocTitle = "New Document Title"
// pydocmaker:param:pDocNo
#let pDocNo = "TDD-RX-1234"
// pydocmaker:param:pDate
#let pDate = ""
// pydocmaker:param:pIsConfidential
#let pIsConfidential = false
// pydocmaker:parameters:end

// pydocmaker:body:begin
placeholder text
// pydocmaker:body:end
"""


# block template with a non-empty date default (the scenario of a template
# carrying a placeholder date like "2026-11-25" in its pDate default)
DEFAULT_DATE_TYP_TEMPLATE = """// pydocmaker:parameters:begin
// pydocmaker:param:pDate
#let pDate = "2026-11-25"
// pydocmaker:param:pAuthorName
#let pAuthorName = "Michael Musterer"
// pydocmaker:parameters:end

// pydocmaker:body:begin
placeholder text
// pydocmaker:body:end
"""


def get_assignment(rendered, name):
    """Return the value string of a typst ``#let name = ...`` assignment."""
    prefix = f'#let {name} = '
    for line in rendered.splitlines():
        if line.strip().startswith(prefix):
            return line.strip()[len(prefix):]
    return None


class TestMapLegacyParams(unittest.TestCase):

    def test_legacy_example_is_converted(self):
        out = map_legacy_params(LEGACY_EXAMPLE)
        self.assertEqual(out['pProject'], 'INAF MeerKAT Band5b Receiver')
        self.assertEqual(out['pDocTitle'], 'Internal Report - TE-RFHC  - Full Receiver - Pretest')
        self.assertEqual(out['pDocNo'], 'B5bRx-0060-TE-RFHC-1')
        self.assertEqual(out['pDocRevision'], 'A')
        self.assertEqual(out['pDocStatus'], 'Released')
        self.assertEqual(out['pDate'], '2025-08-12')
        self.assertEqual(out['pAuthorName'], 'sh')
        self.assertEqual(out['pApprovedBy'], 'T. Glaubach (procedure only)')
        self.assertEqual(out['pReleasedBy'], 'JupyRun Testsystem')
        self.assertIs(out['pIsConfidential'], True)

    def test_all_mapping_targets_covered(self):
        out = map_legacy_params(LEGACY_EXAMPLE)
        for old, new in LEGACY_PARAM_MAP.items():
            if old not in LEGACY_EXAMPLE:
                continue  # dict-name legacy keys are covered separately below
            self.assertIn(old, out)
            self.assertEqual(out[new], out[old])

    def test_dict_valued_legacy_names_are_converted(self):
        params = {'acronyms': {'SNR': 'Signal-to-Noise Ratio'},
                  'applicables': {'AD1': 'Applicable Document 1'},
                  'references': {'RD1': 'Reference Document 1'}}
        out = map_legacy_params(params)
        self.assertEqual(out['pAcronyms'], params['acronyms'])
        self.assertEqual(out['pApplicables'], params['applicables'])
        self.assertEqual(out['pReferences'], params['references'])
        # legacy keys are kept
        self.assertEqual(out['acronyms'], params['acronyms'])

    def test_legacy_names_without_counterpart_pass_through(self):
        # "purpose" and "scope" have no new counterpart and are kept as-is
        out = map_legacy_params(LEGACY_EXAMPLE)
        self.assertEqual(out['purpose'], '')
        self.assertEqual(out['scope'], '')
        self.assertNotIn('pPurpose', out)
        self.assertNotIn('pScope', out)

    def test_does_not_overwrite_set_new_names(self):
        params = {'title': 'legacy title', 'pDocTitle': 'explicit title',
                  'confidential': True, 'pIsConfidential': False}
        out = map_legacy_params(params)
        self.assertEqual(out['pDocTitle'], 'explicit title')
        self.assertIs(out['pIsConfidential'], False)

    def test_fills_empty_new_names(self):
        for empty in ('', None, {}, []):
            with self.subTest(empty=empty):
                out = map_legacy_params({'title': 'legacy title', 'pDocTitle': empty})
                self.assertEqual(out['pDocTitle'], 'legacy title')

    def test_falsy_but_set_new_names_are_kept(self):
        # False / 0 count as set values and are not overwritten
        out = map_legacy_params({'confidential': True, 'pIsConfidential': False})
        self.assertIs(out['pIsConfidential'], False)
        out = map_legacy_params({'status': 'legacy', 'pDocStatus': 'WIP'})
        self.assertEqual(out['pDocStatus'], 'WIP')

    def test_conversion_is_non_destructive(self):
        out = map_legacy_params(LEGACY_EXAMPLE)
        for k, v in LEGACY_EXAMPLE.items():
            self.assertIn(k, out)
            self.assertEqual(out[k], v)

    def test_input_dict_is_not_mutated(self):
        params = dict(LEGACY_EXAMPLE)
        map_legacy_params(params)
        self.assertEqual(params, LEGACY_EXAMPLE)
        self.assertNotIn('pDocTitle', params)

    def test_idempotent(self):
        once = map_legacy_params(LEGACY_EXAMPLE)
        twice = map_legacy_params(once)
        self.assertEqual(once, twice)

    def test_no_legacy_names_returns_equal_mapping(self):
        params = {'pDocTitle': 'X', 'pAuthorName': 'Y', 'other': 1}
        self.assertEqual(map_legacy_params(params), params)

    def test_empty_and_none_params(self):
        self.assertEqual(map_legacy_params({}), {})
        self.assertEqual(map_legacy_params(None), {})

    def test_invalid_params_type_raises(self):
        with self.assertRaises(TypeError):
            map_legacy_params(['title'])

    def test_available_new_names_restricts_conversion(self):
        # template only knows pDocTitle -> only "title" is converted
        out = map_legacy_params(LEGACY_EXAMPLE, available_new_names={'pDocTitle'})
        self.assertEqual(out['pDocTitle'], LEGACY_EXAMPLE['title'])
        self.assertNotIn('pProject', out)

    def test_available_new_names_empty_converts_nothing(self):
        out = map_legacy_params(LEGACY_EXAMPLE, available_new_names=set())
        self.assertEqual(out, LEGACY_EXAMPLE)

    def test_drop_converted_removes_redundant_legacy_keys(self):
        out = map_legacy_params(LEGACY_EXAMPLE,
                                available_new_names={'pDocTitle', 'pProject'},
                                drop_converted=True)
        self.assertEqual(out['pDocTitle'], LEGACY_EXAMPLE['title'])
        self.assertEqual(out['pProject'], LEGACY_EXAMPLE['project'])
        # "title"/"project" are not declared by the (fictive) template -> dropped
        self.assertNotIn('title', out)
        self.assertNotIn('project', out)
        # legacy names without a declared new name survive
        self.assertIn('doc_no', out)

    def test_drop_converted_keeps_declared_legacy_names(self):
        # a transition template declaring both names keeps the legacy key
        out = map_legacy_params({'title': 'T', 'pDocTitle': ''},
                                available_new_names={'title', 'pDocTitle'},
                                drop_converted=True)
        self.assertEqual(out['pDocTitle'], 'T')
        self.assertIn('title', out)

    def test_custom_mapping(self):
        out = map_legacy_params({'foo': 1}, mapping={'foo': 'pFoo'})
        self.assertEqual(out['pFoo'], 1)

    def test_defaults_do_not_block_conversion(self):
        # template placeholder defaults (e.g. carried along in the document
        # metadata) must not block the conversion of legacy names
        defaults = {'pDocTitle': 'New Document Title', 'pProject': 'Example Project'}
        params = {'title': 'RXC Testreport', 'project': 'INAF',
                  'pDocTitle': 'New Document Title', 'pProject': 'Example Project'}
        out = map_legacy_params(params, available_new_names=set(defaults),
                                drop_converted=True, defaults=defaults)
        self.assertEqual(out['pDocTitle'], 'RXC Testreport')
        self.assertEqual(out['pProject'], 'INAF')
        self.assertNotIn('title', out)
        self.assertNotIn('project', out)

    def test_user_set_new_names_still_win_with_defaults(self):
        defaults = {'pDocTitle': 'New Document Title'}
        params = {'title': 'legacy', 'pDocTitle': 'Custom Title'}
        out = map_legacy_params(params, available_new_names=set(defaults),
                                drop_converted=True, defaults=defaults)
        self.assertEqual(out['pDocTitle'], 'Custom Title')

    def test_none_value_is_never_dropped_as_default_mirror(self):
        # None explicitly undefines a parameter: it survives the mirrored
        # defaults cleanup and counts as "not set" (filled from the legacy name)
        defaults = {'pDocTitle': 'New Document Title'}
        params = {'pDocTitle': None, 'title': 'legacy'}
        out = map_legacy_params(params, defaults=defaults)
        self.assertEqual(out['pDocTitle'], 'legacy')

    def test_defaults_survive_without_legacy_names(self):
        # without a legacy name the template defaults are never touched
        defaults = {'pDocTitle': 'New Document Title', 'pDate': '2026-11-25'}
        params = {'pDocTitle': 'New Document Title', 'pDate': '2026-11-25'}
        out = map_legacy_params(params, defaults=defaults)
        self.assertEqual(out, params)


class TestBlockEngineIntegration(unittest.TestCase):

    def test_render_maps_legacy_names(self):
        out = blocktmpl.render(NEW_TYP_TEMPLATE, 'BODY', params=LEGACY_EXAMPLE)
        self.assertEqual(get_assignment(out, 'pProject'), '"INAF MeerKAT Band5b Receiver"')
        self.assertEqual(get_assignment(out, 'pDocTitle'), '"Internal Report - TE-RFHC  - Full Receiver - Pretest"')
        self.assertEqual(get_assignment(out, 'pDocNo'), '"B5bRx-0060-TE-RFHC-1"')
        self.assertEqual(get_assignment(out, 'pDocRevision'), '"A"')
        self.assertEqual(get_assignment(out, 'pDocStatus'), '"Released"')
        self.assertEqual(get_assignment(out, 'pDate'), '"2025-08-12"')
        self.assertEqual(get_assignment(out, 'pAuthorName'), '"sh"')
        self.assertEqual(get_assignment(out, 'pApprovedBy'), '"T. Glaubach (procedure only)"')
        self.assertEqual(get_assignment(out, 'pReleasedBy'), '"JupyRun Testsystem"')
        self.assertEqual(get_assignment(out, 'pIsConfidential'), 'true')

    def test_render_does_not_overwrite_explicit_new_names(self):
        out = blocktmpl.render(NEW_TYP_TEMPLATE, 'BODY',
                               params={'title': 'legacy title', 'pDocTitle': 'explicit title'})
        self.assertEqual(get_assignment(out, 'pDocTitle'), '"explicit title"')

    def test_render_drops_converted_legacy_keys(self):
        out = blocktmpl.render(NEW_TYP_TEMPLATE, 'BODY',
                               params={'project': 'P', 'title': 'T', 'purpose': 'keepme'})
        self.assertNotIn('#let title =', out)
        self.assertNotIn('#let project =', out)
        # legacy names without a new counterpart are appended as before
        self.assertIn('#let purpose =', out)

    def test_render_old_template_unchanged(self):
        # an old-generation template declaring "title" keeps working unchanged
        out = blocktmpl.render(OLD_TYP_TEMPLATE, 'BODY', params={'title': 'Explicit'})
        self.assertEqual(get_assignment(out, 'title'), '"Explicit"')
        self.assertNotIn('pDocTitle', out)

    def test_block_doc_template_render_maps(self):
        tpl = blocktmpl.BlockDocTemplate(NEW_TYP_TEMPLATE, tformat='typ')
        out = tpl.render(body='BODY', title='From Legacy', doc_no='N-1')
        self.assertEqual(get_assignment(out, 'pDocTitle'), '"From Legacy"')
        self.assertEqual(get_assignment(out, 'pDocNo'), '"N-1"')

    def test_update_params_maps_legacy_names(self):
        out = blocktmpl.update_params(NEW_TYP_TEMPLATE, {'title': 'Updated Title'})
        self.assertEqual(get_assignment(out, 'pDocTitle'), '"Updated Title"')
        self.assertNotIn('#let title =', out)

    def test_update_params_old_template_unchanged(self):
        out = blocktmpl.update_params(OLD_TYP_TEMPLATE, {'title': 'Updated Title'})
        self.assertEqual(get_assignment(out, 'title'), '"Updated Title"')
        self.assertNotIn('pDocTitle', out)

    def test_render_is_idempotent_with_legacy_names(self):
        once = blocktmpl.render(NEW_TYP_TEMPLATE, 'BODY',
                                params={'title': 'T', 'author': 'A'})
        twice = blocktmpl.render(once, 'BODY', params={'title': 'T', 'author': 'A'})
        self.assertEqual(once, twice)

    def test_render_placeholder_defaults_do_not_block_legacy_names(self):
        # regression: templates with non-empty placeholder defaults (e.g. the
        # tdd templates) plus legacy metadata copied into the document metadata
        params = {'project': 'INAF MeerKAT Band5b Receiver',
                  'title': 'RXC Control Testreport',
                  'doc_no': 'MK-B5bRx-4352-0028-REP',
                  'date': '2025-06-25',
                  'confidential': True,
                  'pProject': 'Example Project',      # mirrored defaults as
                  'pDocTitle': 'New Document Title',  # carried in the metadata
                  'pDocNo': 'TDD-RX-1234',
                  'pDate': '',
                  'pIsConfidential': False}
        out = blocktmpl.render(PLACEHOLDER_TYP_TEMPLATE, 'BODY', params=params)
        self.assertEqual(get_assignment(out, 'pProject'), '"INAF MeerKAT Band5b Receiver"')
        self.assertEqual(get_assignment(out, 'pDocTitle'), '"RXC Control Testreport"')
        self.assertEqual(get_assignment(out, 'pDocNo'), '"MK-B5bRx-4352-0028-REP"')
        self.assertEqual(get_assignment(out, 'pDate'), '"2025-06-25"')
        self.assertEqual(get_assignment(out, 'pIsConfidential'), 'true')

    def test_render_user_override_beats_legacy_and_defaults(self):
        params = {'title': 'legacy title', 'pDocTitle': 'Custom Title'}
        out = blocktmpl.render(PLACEHOLDER_TYP_TEMPLATE, 'BODY', params=params)
        self.assertEqual(get_assignment(out, 'pDocTitle'), '"Custom Title"')

    def test_render_empty_legacy_value_wins_over_template_default(self):
        # the document metadata explicitly carries date="" -> the empty value
        # is the document's data and displaces the template placeholder
        # "2026-11-25"; the template's own empty-value handling then applies
        out = blocktmpl.render(DEFAULT_DATE_TYP_TEMPLATE, 'BODY',
                               params={'date': '', 'pDate': '2026-11-25'})
        self.assertEqual(get_assignment(out, 'pDate'), '""')

    def test_render_template_default_survives_without_legacy_name(self):
        # without a legacy "date" in the metadata the template default is kept
        out = blocktmpl.render(DEFAULT_DATE_TYP_TEMPLATE, 'BODY',
                               params={'pDate': '2026-11-25'})
        self.assertEqual(get_assignment(out, 'pDate'), '"2026-11-25"')
        # ... and so are the other defaults (no legacy names involved at all)
        out = blocktmpl.render(DEFAULT_DATE_TYP_TEMPLATE, 'BODY', params={})
        self.assertEqual(get_assignment(out, 'pAuthorName'), '"Michael Musterer"')

    def test_render_real_legacy_date_beats_template_default(self):
        out = blocktmpl.render(DEFAULT_DATE_TYP_TEMPLATE, 'BODY',
                               params={'date': '2025-06-25', 'pDate': '2026-11-25'})
        self.assertEqual(get_assignment(out, 'pDate'), '"2025-06-25"')


class TestJinjaEngineIntegration(unittest.TestCase):

    def test_doc_template_render_provides_both_names(self):
        tpl = DocTemplate(jinja2.Template('Title: {{ title }}|New: {{ pDocTitle }}'), params={})
        rendered = tpl.render(title='legacy title')
        self.assertEqual(rendered, 'Title: legacy title|New: legacy title')

    def test_doc_template_render_prefers_explicit_new_name(self):
        tpl = DocTemplate(jinja2.Template('New: {{ pDocTitle }}'), params={})
        rendered = tpl.render(title='legacy title', pDocTitle='explicit title')
        self.assertEqual(rendered, 'New: explicit title')

    def test_doc_template_render_fills_empty_default(self):
        tpl = DocTemplate(jinja2.Template('New: {{ pDocTitle }}'), params={'pDocTitle': ''})
        rendered = tpl.render(title='legacy title')
        self.assertEqual(rendered, 'New: legacy title')

    def test_doc_template_defaults_survive_without_legacy_names(self):
        # regression: template defaults must survive a render that passes no
        # (or only matching) legacy names
        tpl = DocTemplate(jinja2.Template('Date: {{ pDate }}'), params={'pDate': '2026-11-25'})
        self.assertEqual(tpl.render(), 'Date: 2026-11-25')
        self.assertEqual(tpl.render(pDate='2026-11-25'), 'Date: 2026-11-25')

    def test_doc_template_empty_legacy_value_wins_over_default(self):
        tpl = DocTemplate(jinja2.Template('Date: [{{ pDate }}]'), params={'pDate': '2026-11-25'})
        self.assertEqual(tpl.render(date=''), 'Date: []')

    def test_ex_typst_convert_maps_for_jinja_template(self):
        jinja_tpl = 'New: {{ pDocTitle }} | Old: {{ title }}'
        out = pyd.backend.ex_typst.convert(
            pyd.Doc().add_md('hello').dump(), template=jinja_tpl,
            template_params={'title': 'legacy title'}, template_engine='jinja2')
        self.assertIn('New: legacy title', out)
        self.assertIn('Old: legacy title', out)

    def test_ex_html_convert_maps_for_jinja_template(self):
        jinja_tpl = '<html><body>New: {{ pDocTitle }} {{ body }}</body></html>'
        out = pyd.backend.ex_html.convert(
            pyd.Doc().add_md('hello').dump(), template=jinja_tpl,
            template_params={'title': 'legacy title'}, template_engine='jinja2')
        self.assertIn('New: legacy title', out)

    def test_ex_tex_convert_maps_for_jinja_template(self):
        jinja_tpl = r'\documentclass{article}\begin{document}New: \pDocTitle{} {{ body }}\end{document}'
        out = pyd.backend.ex_tex.convert(
            pyd.Doc().add_md('hello').dump(), template=jinja_tpl,
            template_params={'title': 'legacy title'}, with_attachments=False)
        self.assertIn(r'\pDocTitle', out)


if __name__ == '__main__':
    unittest.main()

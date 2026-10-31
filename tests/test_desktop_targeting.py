"""Targeting guards use fixed monotonic time and synthetic AX snapshots."""

from dataclasses import FrozenInstanceError, replace
from io import StringIO
import json
import unittest
from unittest.mock import Mock, patch

from benchmarks.desktop_targeting.cases import NOW, node, snapshot
from elvion.desktop_observation.contracts import DesktopObservationResult
from elvion.desktop_targeting import locate_control, evidence_summary
from scripts.check_desktop_targeting import main as demo_main


def find(ax_snapshot, label='7', **kwargs):
    return locate_control(ax_snapshot, label=label, now_ns=kwargs.pop('now_ns', NOW), **kwargs)


class DesktopTargetingTests(unittest.TestCase):
    def test_found_exact_and_immutable(self):
        result = find(snapshot(node('seven', '7')))
        self.assertEqual((result.status, result.node_id, result.role, result.enabled),
                         ('found', 'seven', 'AXButton', True))
        self.assertEqual(result.bbox, (10.0, -20.0, 40.0, 30.0))
        self.assertEqual(result.candidate_count, 1)
        with self.assertRaises(FrozenInstanceError):
            result.node_id = 'other'

    def test_normalization_keeps_diacritics_and_punctuation(self):
        ax = snapshot(node('one', 'Cộng ngay.'), node('two', '+'))
        self.assertEqual(find(ax, '  CỘNG   ngay.  ').node_id, 'one')
        for label in ('Cong ngay.', 'Cộng ngay', 'plus'):
            self.assertEqual(find(ax, label).status, 'not_found')
        self.assertEqual(find(ax, '+').node_id, 'two')

    def test_duplicates_and_uncertain_nodes_never_select_first(self):
        duplicate = snapshot(node('a', '7'), node('b', '7', enabled=False))
        self.assertEqual(find(duplicate).status, 'ambiguous')
        for uncertain in (node('x', None), node('x', '7', role=None),
                          node('x', None, role=None)):
            result = find(snapshot(node('seven', '7'), uncertain))
            self.assertEqual(result.status, 'unavailable')
            self.assertIsNone(result.node_id)
        self.assertEqual(find(snapshot(node('text', '7', role='AXStaticText'))).status,
                         'not_found')

    def test_unavailable_disabled_unknown_bbox_and_truncation(self):
        for element in (node('x', '7', enabled=False), node('x', '7', enabled=None),
                        node('x', '7', bbox=None), node('x', None)):
            self.assertEqual(find(snapshot(element)).status, 'unavailable')
        ax = snapshot(node('seven', '7'), truncated=True, truncation_reason='NODE_LIMIT')
        result = find(ax)
        self.assertEqual((result.status, result.reason), ('unavailable', 'TRUNCATED_SNAPSHOT'))

    def test_freshness_boundary_future_and_threshold_do_not_change_oracle(self):
        ax = snapshot(node('seven', '7'))
        self.assertEqual(find(ax, now_ns=3_000_000_000).status, 'found')
        self.assertEqual(find(ax, now_ns=3_000_000_001).status, 'stale')
        self.assertEqual(find(ax, now_ns=999_999_999).reason, 'CLOCK_IN_FUTURE')
        self.assertEqual(find(ax, max_age_ms=999).status, 'stale')
        self.assertEqual(find(ax, max_age_ms=1000).status, 'found')

    def test_invalid_snapshot_guard(self):
        base = snapshot(node('seven', '7'))
        invalid = (replace(base, pid=True), replace(base, schema_version=True),
                   replace(base, elements=(base.elements[0], node('orphan', '7', parent='missing'))),
                   replace(base, elements=(base.elements[0], node('x', '7'), node('x', '8'))),
                   replace(base, elements=(base.elements[0], node('x', '7', bbox=(0, 0, float('nan'), 2)))),
                   replace(base, elements=(base.elements[0], node('x', '7', bbox=(0, 0, -1, 2)))),
                   replace(base, truncated=True), replace(base, captured_at_monotonic_ns=0),
                   replace(base, captured_at_utc='not-a-date'))
        for ax in invalid:
            with self.subTest(ax=ax):
                self.assertEqual(find(ax).status, 'error')

    def test_unsupported_inputs(self):
        base = snapshot(node('seven', '7'))
        for kwargs in ({'label': ''}, {'label': 'a' * 257}, {'label': '7\n'},
                       {'label': '7', 'role': 'AXStaticText'}, {'label': '7', 'max_age_ms': 0},
                       {'label': '7', 'max_age_ms': True}, {'label': '7', 'now_ns': True}):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(locate_control(base, **({'now_ns': NOW} | kwargs)).status,
                                 'unsupported')
        self.assertEqual(find(replace(base, bundle_id='com.apple.TextEdit')).status, 'unsupported')

    def test_locator_does_not_call_observer_or_subprocess(self):
        with (patch('elvion.desktop_observation.observe_app', side_effect=AssertionError('AX')),
              patch('subprocess.run', side_effect=AssertionError('process')),
              patch('builtins.open', side_effect=AssertionError('file'))):
            self.assertEqual(find(snapshot(node('seven', '7'))).status, 'found')

    def test_demo_opt_in_and_upstream_failure(self):
        observer = Mock()
        locator = Mock()
        with patch('sys.stdout', new_callable=StringIO) as output:
            self.assertEqual(demo_main(['--label', '7'], observer=observer, locator=locator), 2)
            self.assertEqual(json.loads(output.getvalue())['reason'], 'LABEL_OPT_IN_REQUIRED')
        observer.assert_not_called()
        observer.return_value = DesktopObservationResult('permission_required', reason='AX_PERMISSION_REQUIRED')
        with patch('sys.stdout', new_callable=StringIO) as output:
            self.assertEqual(demo_main(['--label', '7', '--include-labels'],
                                       observer=observer, locator=locator), 2)
            self.assertEqual(json.loads(output.getvalue())['status'], 'permission_required')
        observer.assert_called_once_with('com.apple.calculator', include_labels=True)
        locator.assert_not_called()

    def test_demo_observes_once_and_prints_summary(self):
        observer = Mock(return_value=DesktopObservationResult('observed', snapshot(node('seven', '7'))))
        with patch('sys.stdout', new_callable=StringIO) as output:
            code = demo_main(['--label', '7', '--include-labels'], observer=observer,
                             locator=lambda ax, label: find(ax, label))
        self.assertEqual(code, 0)
        row = json.loads(output.getvalue())
        self.assertEqual((row['status'], row['node_id'], row['candidate_count']), ('found', 'seven', 1))
        self.assertNotIn('elements', row)
        observer.assert_called_once()

    def test_evidence_diagnostic_shares_guard_policy_without_disclosing_labels(self):
        ax=snapshot(node('seven','7'),node('unknown',None),
                    node('private','DO_NOT_DISCLOSE',role='AXStaticText'),
                    node('unknown-role','7',role=None))
        summary=evidence_summary(ax,label='7')
        self.assertEqual(summary['matching_buttons'],1)
        self.assertEqual(summary['matching_enabled'],1)
        self.assertEqual(summary['blocker_counts'],{'BUTTON_LABEL_MISSING':1,'EXACT_LABEL_ROLE_MISSING':1})
        self.assertNotIn('DO_NOT_DISCLOSE',json.dumps(summary))
        self.assertNotIn('bbox',summary)
        for example in summary['blocker_examples']:
            self.assertNotIn('bbox',example)
        self.assertEqual(find(ax).reason,'INCOMPLETE_AX_EVIDENCE')

    def test_diagnostic_reuses_same_observation_and_does_not_relax_result(self):
        observer=Mock(return_value=DesktopObservationResult('observed',snapshot(node('seven','7'),node('missing',None))))
        with patch('sys.stdout',new_callable=StringIO) as output:
            code=demo_main(['--label','7','--include-labels','--diagnose-evidence'],observer=observer,
                           locator=lambda ax,label:find(ax,label))
        row=json.loads(output.getvalue())
        self.assertEqual(code,1);self.assertEqual(row['status'],'unavailable')
        self.assertEqual(row['evidence_diagnostic']['blocker_counts'],{'BUTTON_LABEL_MISSING':1})
        observer.assert_called_once_with('com.apple.calculator',include_labels=True)

    def test_content_scope_requires_verified_subrole_and_direct_window_parent(self):
        window=node('window',role='AXWindow')
        seven=node('seven','7',parent='window')
        for subrole in ('AXCloseButton','AXMinimizeButton','AXZoomButton','AXFullScreenButton'):
            chrome=replace(node('chrome',None,parent='window'),subrole=subrole)
            ax=snapshot(window,chrome,seven)
            self.assertEqual(find(ax).status,'unavailable')
            selected=find(ax,scope='calculator_content')
            self.assertEqual((selected.status,selected.node_id,selected.scope),('found','seven','calculator_content'))
            diagnostic=evidence_summary(ax,label='7',scope='calculator_content')
            self.assertEqual(diagnostic['excluded_subroles'],{subrole:1})
            self.assertEqual(diagnostic['blocker_counts'],{})
        for chrome in (node('unknown',None,parent='window'),
                       replace(node('wrong-parent',None),subrole='AXCloseButton'),
                       replace(node('unknown-subrole',None,parent='window'),subrole='AXOtherButton')):
            self.assertEqual(find(snapshot(window,chrome,seven),scope='calculator_content').status,'unavailable')

    def test_content_scope_keeps_duplicate_unknown_and_freshness_guards(self):
        window=node('window',role='AXWindow')
        chrome=replace(node('chrome',None,parent='window'),subrole='AXCloseButton')
        ax=snapshot(window,chrome,node('a','7',parent='window'),node('b','7',parent='window'))
        self.assertEqual(find(ax,scope='calculator_content').status,'ambiguous')
        self.assertEqual(find(ax,scope='calculator_content',now_ns=4_000_000_000).status,'stale')
        self.assertEqual(find(replace(ax,truncated=True,truncation_reason='NODE_LIMIT'),scope='calculator_content').status,'unavailable')
        self.assertEqual(find(ax,scope='invented').status,'unsupported')

    def test_content_scope_is_explicit_in_demo_and_diagnostic_includes_verified_exclusions(self):
        ax=snapshot(node('window',role='AXWindow'),
                    replace(node('chrome',None,parent='window'),subrole='AXCloseButton'),node('seven','7',parent='window'))
        observer=Mock(return_value=DesktopObservationResult('observed',ax))
        with patch('sys.stdout',new_callable=StringIO) as output:
            code=demo_main(['--label','7','--include-labels','--scope','calculator-content','--diagnose-evidence'],
                          observer=observer,locator=lambda ax,**kw:find(ax,**kw))
        row=json.loads(output.getvalue())
        self.assertEqual((code,row['target_scope'],row['node_id']),(0,'calculator_content','seven'))
        self.assertEqual(row['evidence_diagnostic']['excluded_window_controls'],1)
        observer.assert_called_once()


if __name__ == '__main__':
    unittest.main()

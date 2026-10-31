"""Fixed-time pure evaluator and fake native backend tests."""

from dataclasses import FrozenInstanceError, asdict, replace
from io import StringIO
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import unittest
from unittest.mock import Mock, patch

from benchmarks.desktop_visibility.cases import BASE, GOOD_HITS, NOW
from elvion.desktop_observation.contracts import DesktopElement, DesktopObservationResult, DesktopSnapshot
from elvion.desktop_targeting.contracts import DesktopTargetResult
from elvion.desktop_visibility.backend import VisibilityBackend
from elvion.desktop_visibility.backend import SOURCE
from elvion.desktop_visibility.contracts import VisibilityEvidence
from elvion.desktop_visibility.evaluator import evaluate_visibility
from scripts.check_desktop_visibility import main as demo_main


def evaluate(evidence=BASE, **changes):
    return evaluate_visibility(replace(evidence, **changes), now_ns=NOW)


class VisibilityTests(unittest.TestCase):
    def test_visible_is_sampled_only_and_immutable(self):
        result = evaluate()
        self.assertEqual((result.status, result.reason, result.checked_points),
                         ('visible', 'FIVE_AX_POINTS_BOUND_TO_TARGET', 5))
        self.assertTrue(result.sampled_visibility_verified)
        self.assertFalse(result.whole_target_visibility_verified)
        self.assertFalse(result.freshness_for_execution)
        self.assertEqual(result.actions, 0)
        with self.assertRaises(FrozenInstanceError):
            result.status = 'blocked'

    def test_blocked_and_unknown_are_distinct(self):
        self.assertEqual(evaluate(app_hidden=True, hits=()).reason, 'APP_HIDDEN')
        self.assertEqual(evaluate(window_minimized=True, hits=()).reason, 'WINDOW_MINIMIZED')
        self.assertEqual(evaluate(hits=('other_pid',) + GOOD_HITS[1:]).status, 'blocked')
        self.assertEqual(evaluate(hits=('other_window',) + GOOD_HITS[1:]).status, 'blocked')
        for hits in (('ancestor_only',) * 5, ('unknown',) + GOOD_HITS[1:]):
            self.assertEqual(evaluate(hits=hits).status, 'unknown')
        self.assertEqual(evaluate(frontmost=False).status, 'visible')

    def test_binding_geometry_and_permission_guards(self):
        for change in ({'target_bound': False}, {'window_bound': False},
                       {'unique_target': False}, {'layout_unchanged': False},
                       {'state_unchanged': False}, {'display_contains_target': False},
                       {'permission_granted': None}, {'hit_test_supported': False, 'hits': ()},
                       {'window_minimized': None}):
            with self.subTest(change=change):
                self.assertEqual(evaluate(**change).status, 'unknown')
        clipped = replace(BASE, window_bbox=(1093., -706., 35., 408.), window_contains_target=False)
        self.assertEqual(evaluate_visibility(clipped, now_ns=NOW).status, 'unknown')

    def test_clock_and_schema_are_strict(self):
        self.assertEqual(evaluate_visibility(BASE, now_ns=BASE.snapshot_ns - 1).status, 'unknown')
        self.assertEqual(evaluate_visibility(BASE, now_ns=NOW + 1).reason, 'EVIDENCE_STALE')
        self.assertEqual(evaluate(same_host_clock=False).status, 'unknown')
        for change in ({'pid': True}, {'schema_version': True}, {'display_scale': 0},
                       {'target_bbox': (0, 0, float('nan'), 10)}, {'hits': GOOD_HITS + ('unknown',)},
                       {'window_contains_target': False}):
            with self.subTest(change=change):
                self.assertEqual(evaluate(**change).status, 'error')
        self.assertEqual(evaluate_visibility(BASE, now_ns=NOW, max_age_ms=True).status, 'error')

    def test_evaluator_has_no_backend_or_io(self):
        with (patch('subprocess.run', side_effect=AssertionError('process')),
              patch('builtins.open', side_effect=AssertionError('file'))):
            self.assertEqual(evaluate().status, 'visible')

    def test_native_helper_uses_read_only_public_hit_test(self):
        source = SOURCE.read_text()
        self.assertIn('AXUIElementCopyElementAtPosition', source)
        self.assertIn('AXUIElementCreateSystemWide', source)
        for forbidden in ('AXUIElementPerformAction', 'AXUIElementSetAttributeValue',
                          'CGEventPost', 'CGWindowListCopyWindowInfo', 'AXValueAttribute',
                          'AXSelectedTextAttribute'):
            self.assertNotIn(forbidden, source)

    def test_backend_protocol_binding_and_malformed_output(self):
        root = DesktopElement('root', None, 'AXApplication', None, True, None, None)
        window = DesktopElement('w', 'root', 'AXWindow', None, None, BASE.window_bbox, None)
        button = DesktopElement('n115', 'w', 'AXButton', None, True, BASE.target_bbox, '7')
        snap = DesktopSnapshot(1, BASE.snapshot_id, BASE.bundle_id, BASE.pid,
                               '2026-10-31T00:00:00Z', BASE.snapshot_ns,
                               (root, window, button), False, None)
        target = DesktopTargetResult('found', 'EXACT_BUTTON', BASE.snapshot_id,
                                     'n115', 'AXButton', True, BASE.target_bbox, 1, 1.0,
                                     'calculator_content')
        geometry = {'status': 'geometry_consistent', 'snapshot_id': BASE.snapshot_id,
                    'node_id': 'n115', 'target_scope': 'calculator_content',
                    'bbox': BASE.target_bbox, 'window_bbox': BASE.window_bbox,
                    'display_bbox': (62., -900., 1600., 900.), 'display_scale': 1.0}
        raw = json.dumps(asdict(BASE)).encode()
        runner = Mock(return_value=SimpleNamespace(returncode=0, stdout=raw))
        backend = VisibilityBackend(runner=runner)
        backend.binary = Path('/usr/bin/true')
        evidence = backend.probe(snap, target, geometry, label='7', same_session_observation=True)
        self.assertIsInstance(evidence, VisibilityEvidence)
        self.assertEqual(runner.call_args.kwargs['shell'], False)
        self.assertNotIn(b'"7"', runner.return_value.stdout)
        request = json.loads(runner.call_args.kwargs['input'])
        self.assertEqual(request['target_label'], '7')
        self.assertTrue(request['same_host_clock'])
        runner.return_value.stdout = raw.replace(b'"pid": 123', b'"pid": true')
        self.assertEqual(backend.probe(snap, target, geometry, label='7').reason,
                         'PROBE_PROTOCOL_ERROR')
        runner.return_value.stdout = b'{"a":1,"a":2}'
        self.assertEqual(backend.probe(snap, target, geometry, label='7').reason,
                         'PROBE_PROTOCOL_ERROR')
        runner.side_effect = subprocess.TimeoutExpired(['helper'], 5)
        self.assertEqual(backend.probe(snap, target, geometry, label='7').reason,
                         'PROBE_TIMEOUT')

    def test_demo_opt_in_and_upstream_stop(self):
        observer, geometry, backend = Mock(), Mock(), Mock()
        with patch('sys.stdout', new_callable=StringIO) as out:
            self.assertEqual(demo_main([], observer=observer, geometry_backend=geometry,
                                       visibility_backend=backend), 2)
            self.assertEqual(json.loads(out.getvalue())['reason'], 'LABEL_OPT_IN_REQUIRED')
        observer.assert_not_called()
        observer.return_value = DesktopObservationResult('permission_required', reason='AX_PERMISSION_REQUIRED')
        geometry.read.return_value = ()
        with patch('sys.stdout', new_callable=StringIO) as out:
            self.assertEqual(demo_main(['--include-labels'], observer=observer,
                                       geometry_backend=geometry, visibility_backend=backend), 2)
            self.assertEqual(json.loads(out.getvalue())['upstream_status'], 'permission_required')
        observer.assert_called_once_with('com.apple.calculator', include_labels=True)
        backend.probe.assert_not_called()


if __name__ == '__main__':
    unittest.main()

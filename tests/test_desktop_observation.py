"""Fake-backend tests: no AX permission or app process is needed."""

from dataclasses import FrozenInstanceError
import json
import subprocess
import unittest
from unittest.mock import Mock

from elvion.desktop_observation import observe_app
from elvion.desktop_observation.observer import MAX_NODES, MAX_OUTPUT, SOURCE


BUNDLE = 'com.apple.calculator'


def envelope(status='observed', *, elements=None, **changes):
    root = {'id': 'n0', 'parent_id': None, 'role': 'AXApplication', 'subrole': None,
            'enabled': None, 'bbox': None, 'label': None}
    snapshot = {'schema_version': 1, 'id': 'snapshot-1', 'bundle_id': BUNDLE, 'pid': 42,
                'captured_at_utc': '2026-10-30T01:00:00Z', 'captured_at_monotonic_ns': 100,
                'elements': [root] if elements is None else elements,
                'truncated': False, 'truncation_reason': None}
    snapshot.update(changes)
    return json.dumps({'version': 1, 'status': status,
                       'snapshot': snapshot if status == 'observed' else None,
                       'reason': None if status == 'observed' else {
                           'permission_required': 'AX_PERMISSION_REQUIRED',
                           'app_not_running': 'APP_NOT_RUNNING',
                           'unsupported': 'UNSUPPORTED_REQUEST',
                           'error': 'AX_ROOT_UNREADABLE'}[status]}).encode()


def backend(raw):
    return Mock(observe=Mock(return_value=raw))


class DesktopObservationTests(unittest.TestCase):
    def test_observed_tree_unknowns_and_immutable(self):
        root = {'id': 'n0', 'parent_id': None, 'role': 'AXApplication', 'subrole': None,
                'enabled': None, 'bbox': None, 'label': None}
        child = {'id': 'n1', 'parent_id': 'n0', 'role': 'AXButton', 'subrole': None,
                 'enabled': True, 'bbox': [10, 20, 30, 40], 'label': None}
        fake = backend(envelope(elements=[root, child]))
        result = observe_app(BUNDLE, backend=fake)
        self.assertEqual(result.status, 'observed')
        self.assertEqual(result.snapshot.elements[1].bbox, (10., 20., 30., 40.))
        self.assertIsNone(result.snapshot.elements[0].enabled)
        self.assertIsNone(result.snapshot.elements[0].label)
        self.assertEqual(fake.observe.call_args.args, (BUNDLE, False))
        with self.assertRaises(FrozenInstanceError):
            result.snapshot.pid = 99

    def test_permission_and_not_running_are_not_empty_observations(self):
        for status in ('permission_required', 'app_not_running'):
            fake = backend(envelope(status))
            result = observe_app(BUNDLE, backend=fake)
            self.assertEqual(result.status, status)
            self.assertIsNone(result.snapshot)
            fake.observe.assert_called_once_with(BUNDLE, False)

    def test_invalid_request_never_spawns(self):
        fake = backend(envelope())
        for bundle, labels in (('com.apple.TextEdit', False), (BUNDLE + ';open', False),
                               ('', False), (BUNDLE, 1)):
            self.assertEqual(observe_app(bundle, include_labels=labels, backend=fake).status,
                             'unsupported')
        fake.observe.assert_not_called()

    def test_labels_are_opt_in_and_no_value_field(self):
        row = {'id': 'n0', 'parent_id': None, 'role': 'AXApplication', 'subrole': None,
               'enabled': True, 'bbox': None, 'label': 'Calculator'}
        raw = envelope(elements=[row])
        self.assertEqual(observe_app(BUNDLE, backend=backend(raw)).reason, 'PROTOCOL_ERROR')
        result = observe_app(BUNDLE, include_labels=True, backend=backend(raw))
        self.assertEqual(result.snapshot.elements[0].label, 'Calculator')
        row['value'] = 'private'
        self.assertEqual(observe_app(BUNDLE, include_labels=True,
                                     backend=backend(envelope(elements=[row]))).reason,
                         'PROTOCOL_ERROR')

    def test_malformed_tree_bbox_schema_and_limits(self):
        row = {'id': 'n0', 'parent_id': None, 'role': 'AXApplication', 'subrole': None,
               'enabled': None, 'bbox': None, 'label': None}
        invalid = [b'{oops', envelope(schema_version=2), envelope(pid=0),
                   envelope(elements=[]), envelope(elements=[dict(row, parent_id='missing')]),
                   envelope(elements=[row, dict(row, id='n1', parent_id='missing')]),
                   envelope(elements=[dict(row, bbox=[0, 0, -1, 2])]),
                   envelope(elements=[dict(row, bbox=[0, 0, float('nan'), 2])]),
                   envelope(elements=[dict(row, enabled='yes')]),
                   envelope(elements=[row] * (MAX_NODES + 1)),
                   envelope(truncated=True, truncation_reason=None), b'x' * (MAX_OUTPUT + 1)]
        for raw in invalid:
            with self.subTest(raw=raw[:60]):
                self.assertIn(observe_app(BUNDLE, backend=backend(raw)).reason,
                              {'PROTOCOL_ERROR', 'OUTPUT_LIMIT'})

    def test_timeout_backend_error_and_no_raw_stderr(self):
        fake = Mock(observe=Mock(side_effect=subprocess.TimeoutExpired(['helper'], 5)))
        self.assertEqual(observe_app(BUNDLE, backend=fake).reason, 'TIMEOUT')
        fake.observe.side_effect = RuntimeError('private app output')
        self.assertEqual(observe_app(BUNDLE, backend=fake).reason, 'BACKEND_ERROR')

    def test_boolean_version_duplicate_keys_and_invalid_utf8_are_protocol_errors(self):
        data=json.loads(envelope());data['version']=True
        invalid=[json.dumps(data).encode(),
                 envelope().replace(b'"version": 1',b'"version": 2, "version": 1',1),
                 b'\xff']
        for raw in invalid:
            with self.subTest(raw=raw[:60]):
                self.assertEqual(observe_app(BUNDLE,backend=backend(raw)).reason,'PROTOCOL_ERROR')

    def test_truncation_and_depth_limit(self):
        rows = []
        for i in range(13):
            rows.append({'id': f'n{i}', 'parent_id': f'n{i-1}' if i else None,
                         'role': 'AXGroup', 'subrole': None, 'enabled': None,
                         'bbox': None, 'label': None})
        raw = envelope(elements=rows, truncated=True, truncation_reason='DEPTH_LIMIT')
        result = observe_app(BUNDLE, backend=backend(raw))
        self.assertEqual(result.status, 'observed')
        self.assertTrue(result.snapshot.truncated)
        self.assertEqual(result.snapshot.truncation_reason, 'DEPTH_LIMIT')
        rows.append(dict(rows[-1], id='n13', parent_id='n12'))
        self.assertEqual(observe_app(BUNDLE, backend=backend(envelope(elements=rows))).reason,
                         'PROTOCOL_ERROR')

    def test_native_source_has_read_only_shape_and_budgets(self):
        source = SOURCE.read_text()
        for prohibited in ('AXUIElementPerformAction', 'AXUIElementSetAttributeValue',
                           'CGEvent', 'AppleScript', 'AXValueAttribute', 'AXSelectedText'):
            self.assertNotIn(prohibited, source)
        self.assertIn('rows.count >= 300', source)
        self.assertIn('depth >= 12', source)
        self.assertIn('started + 4.0', source)
        self.assertIn('AXIsProcessTrusted()', source)


if __name__ == '__main__':
    unittest.main()

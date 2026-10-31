"""Synthetic scorer must catch false visible and wrong binding."""

from dataclasses import replace
import unittest

from benchmarks.desktop_visibility.cases import BASE, CASES, check_cases
from benchmarks.desktop_visibility.runner import score_cases
from elvion.desktop_visibility.contracts import VisibilityResult


class VisibilityBenchmarkTests(unittest.TestCase):
    def test_manifest_and_reference_run(self):
        self.assertEqual(len(check_cases()), 28)
        report = score_cases()
        self.assertEqual(report['observations'], 28)
        self.assertEqual(report['correct'], 28)
        self.assertEqual(report['false_visible'], 0)
        self.assertEqual(report['false_blocked'], 0)
        self.assertEqual(report['actions'], 0)
        self.assertTrue(report['synthetic_only'])

    def test_always_visible_is_not_free_pass(self):
        def always_visible(evidence, **kwargs):
            return VisibilityResult('visible', 'FAKE', evidence.reference_id,
                                    evidence.snapshot_id, evidence.bundle_id, evidence.pid,
                                    evidence.target_node_id, evidence.target_scope,
                                    sampled_visibility_verified=True)
        report = score_cases(evaluator=always_visible)
        positives = sum(case.expected_status == 'visible' for case in CASES)
        self.assertEqual(report['positive_hits'], positives)
        self.assertEqual(report['false_visible'], len(CASES) - positives)

    def test_wrong_binding_is_false_visible(self):
        def wrong_binding(evidence, **kwargs):
            return VisibilityResult('visible', 'FAKE', evidence.reference_id,
                                    'wrong-snapshot', evidence.bundle_id, evidence.pid,
                                    evidence.target_node_id, evidence.target_scope,
                                    sampled_visibility_verified=True)
        report = score_cases(evaluator=wrong_binding)
        self.assertEqual(report['positive_hits'], 0)
        self.assertEqual(report['false_visible'], len(CASES))

    def test_exceptions_and_threshold_change_remain_in_denominator(self):
        def broken(*args, **kwargs):
            raise RuntimeError('private')
        report = score_cases(evaluator=broken)
        self.assertEqual(report['observations'], 28)
        self.assertGreater(report['unexpected_errors'], 0)
        self.assertNotIn('private', str(report))
        changed = list(CASES)
        changed[0] = replace(changed[0], max_age_ms=999)
        self.assertEqual(changed[0].expected_status, 'visible')
        report = score_cases(tuple(changed))
        self.assertEqual(report['correct'], 27)


if __name__ == '__main__':
    unittest.main()

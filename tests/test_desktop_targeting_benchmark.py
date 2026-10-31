"""Synthetic oracle and scorer checks independent of the locator implementation."""

from dataclasses import replace
import unittest

from benchmarks.desktop_targeting.cases import CASES, check_cases
from benchmarks.desktop_targeting.runner import score_cases
from elvion.desktop_targeting.contracts import DesktopTargetResult


class DesktopTargetingBenchmarkTests(unittest.TestCase):
    def test_manifest_and_reference_run(self):
        self.assertEqual(len(check_cases()), 30)
        report = score_cases()
        self.assertEqual(report['observations'], 30)
        self.assertEqual(report['correct'], 30)
        self.assertEqual(report['false_acceptances'], 0)
        self.assertEqual(report['wrong_targets'], 0)
        self.assertEqual(report['actions'], 0)
        self.assertTrue(report['synthetic_only'])
        self.assertGreater(report['accuracy_by_expected_status']['unavailable']['total'], 0)

    def test_wrong_node_and_false_acceptance_are_failures(self):
        def always_wrong(*args, **kwargs):
            return DesktopTargetResult('found', 'EXACT_BUTTON', node_id='wrong')
        report = score_cases(locator=always_wrong)
        positives = sum(case.expected_status == 'found' for case in CASES)
        self.assertEqual(report['wrong_targets'], positives)
        self.assertEqual(report['false_acceptances'], len(CASES) - positives)
        self.assertEqual(report['correct'], 0)

    def test_exceptions_remain_in_denominator(self):
        def broken(*args, **kwargs):
            raise RuntimeError('private text')
        report = score_cases(locator=broken)
        self.assertEqual(report['observations'], len(CASES))
        self.assertEqual(report['false_acceptances'], 0)
        self.assertGreater(report['errors'], 0)
        self.assertNotIn('private text', str(report))

    def test_oracle_is_not_adjusted_by_threshold(self):
        edge = CASES[28]
        self.assertEqual(edge.expected_status, 'found')
        tighter = replace(edge, max_age_ms=999)
        self.assertEqual(tighter.expected_status, 'found')
        # The scorer sees the changed runtime setting as a miss against fixed oracle.
        changed = list(CASES)
        changed[28] = tighter
        report = score_cases(tuple(changed))
        self.assertEqual(report['false_rejections'], 1)
        self.assertEqual(report['correct'], 29)


if __name__ == '__main__':
    unittest.main()

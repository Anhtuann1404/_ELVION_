import unittest

from elvion.desktop_revalidation import RevalidationResult
from benchmarks.desktop_revalidation.cases import CASES
from benchmarks.desktop_revalidation.runner import score


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite(tests)
    suite.addTests(unittest.FunctionTestCase(fn) for name, fn in sorted(globals().items())
                   if name.startswith('test_') and callable(fn))
    return suite


def test_fixed_oracle_and_all_observations_counted():
    report = score()
    assert report['observations'] >= 30
    assert report['passed'] == report['observations']
    assert report['failed'] == report['false_ready'] == report['actions'] == 0


def test_always_ready_fake_is_caught():
    report = score(evaluator=lambda evidence, now_ns: RevalidationResult('ready', 'fake'))
    assert report['false_ready'] > 20
    assert report['failed'] == report['observations'] - 2


def test_wrong_binding_fake_is_caught():
    def wrong_binding(evidence, *, now_ns):
        if evidence is CASES[0].evidence:
            return RevalidationResult('unknown', 'fake')
        from elvion.desktop_revalidation import evaluate_revalidation
        return evaluate_revalidation(evidence, now_ns=now_ns)
    report = score(evaluator=wrong_binding)
    assert report['false_unknown'] == 1
    assert report['failed'] == 1


def test_exception_still_in_denominator():
    def broken(evidence, *, now_ns):
        raise RuntimeError('synthetic')
    report = score(evaluator=broken)
    assert report['observations'] == len(CASES)
    assert report['error'] == len(CASES)

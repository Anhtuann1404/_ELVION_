import unittest
from elvion.calculator_verification import CalculatorVerificationResult
from benchmarks.calculator_verification.cases import CASES
from benchmarks.calculator_verification.runner import score


class CalculatorVerificationBenchmarkTests(unittest.TestCase):
    def test_fixed_oracle(self):
        report=score()
        self.assertGreaterEqual(report['observations'],30)
        self.assertEqual(report['passed'],report['observations'])
        self.assertEqual(report['failed'],0)
        self.assertEqual(report['actions'],0)

    def test_always_verified_fake_detected(self):
        report=score(verifier=lambda *a,**k: CalculatorVerificationResult('verified','fake'))
        self.assertGreater(report['false_verified'],20)
        self.assertGreater(report['failed'],20)

    def test_exception_remains_in_denominator(self):
        def broken(*a,**k): raise RuntimeError('synthetic')
        report=score(verifier=broken)
        self.assertEqual(report['observations'],len(CASES))
        self.assertEqual(report['error'],len(CASES))


if __name__=='__main__': unittest.main()

import unittest
from unittest.mock import patch

from benchmarks.reminders.runner import score
from elvion.reminders import ReminderStore


class ReminderBenchmarkTests(unittest.TestCase):
    def test_fixed_oracles_pass_and_no_external_actions(self):
        result = score()
        self.assertEqual(result["scenarios"], 9)
        self.assertEqual(result["passed"], 9)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["external_actions"], 0)

    def test_oracle_rejects_missing_due_events(self):
        with patch.object(ReminderStore, "collect_due", return_value=()):
            result = score()
        self.assertGreater(result["failed"], 0)
        self.assertGreater(result["missed_expected_events"], 0)


if __name__ == "__main__":
    unittest.main()

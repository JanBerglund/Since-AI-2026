import unittest
from pathlib import Path

from evaluation.run_eval import DEFAULT_CASES, evaluate_rule_cases, load_json
from backend.app import _load_rules


class EvaluationHarnessTests(unittest.TestCase):
    def test_synthetic_rule_cases_match_hand_expected_and_have_no_missed_violations(self):
        case_data = load_json(DEFAULT_CASES)
        results, metrics = evaluate_rule_cases(case_data["cases"], _load_rules())

        self.assertEqual(case_data["dataset_type"], "synthetic")
        self.assertTrue(all(case.get("synthetic") is True for case in case_data["cases"]))
        self.assertEqual(metrics["mismatches"], 0)
        self.assertEqual(metrics["missed_violations"], 0)
        self.assertEqual(len(results), 36)


if __name__ == "__main__":
    unittest.main()

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "capital_agent.py"
spec = importlib.util.spec_from_file_location("capital_agent", MODULE_PATH)
ca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ca)


class CapitalAgentTests(unittest.TestCase):
    def test_initial_cash(self):
        self.assertEqual(ca.cash_balance(), 1000.00)

    def test_policy_blocks_large_single_allocation(self):
        issues = ca.policy_check_proposal(150.00)
        self.assertTrue(any("single-allocation" in x for x in issues))

    def test_policy_accepts_small_proposal(self):
        issues = ca.policy_check_proposal(50.00)
        self.assertEqual(issues, [])

    def test_system_governance_enables_self_improvement(self):
        gov = ca.load_system_governance()
        self.assertTrue(gov["self_improvement_enabled"])
        self.assertIn("A", gov["autonomous_change_classes"])
        self.assertIn("C", gov["human_approval_change_classes"])

    def test_canonical_instructions_are_vendor_neutral(self):
        manual = (Path(__file__).resolve().parents[1] / "AI_OPERATING_MANUAL.md").read_text(encoding="utf-8")
        self.assertIn("vendor-neutral", manual.lower())

    def test_critical_amount_requires_approval(self):
        critical, reasons = ca.classify_critical(amount=30.0, max_loss=30.0)
        self.assertTrue(critical)
        self.assertTrue(reasons)

    def test_small_amount_not_critical_by_amount_alone(self):
        critical, reasons = ca.classify_critical(amount=10.0, max_loss=10.0)
        self.assertFalse(critical)
        self.assertEqual(reasons, [])

    def test_recurring_commitment_is_critical(self):
        critical, reasons = ca.classify_critical(amount=5.0, max_loss=5.0, recurring=True)
        self.assertTrue(critical)
        self.assertTrue(any("recurring" in x for x in reasons))

    def test_policy_relaxation_is_critical(self):
        critical, reasons = ca.classify_critical(policy_relaxation=True)
        self.assertTrue(critical)
        self.assertTrue(any("policy relaxation" in x for x in reasons))

if __name__ == "__main__":
    unittest.main()

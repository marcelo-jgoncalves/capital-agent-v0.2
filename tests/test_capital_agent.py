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

    def test_new_readonly_financial_adapter_is_critical(self):
        critical, reasons = ca.classify_critical(new_readonly_financial_adapter=True)
        self.assertTrue(critical)
        self.assertTrue(any("read-only financial data adapter" in x for x in reasons))


class ContextManagementTests(unittest.TestCase):
    def test_build_current_state_reflects_verified_cash(self):
        content = ca.build_current_state()
        self.assertIn(f"Verified cash: BRL {ca.cash_balance():.2f}", content)
        self.assertIn("Do not hand-edit", content)

    def test_build_current_state_never_fabricates_missing_values(self):
        content = ca.build_current_state()
        self.assertIn("not yet implemented", content)

    def test_update_context_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "CURRENT_STATE.md"
            with patch.object(ca, "CONTEXT_DIR", Path(tmp)), \
                 patch.object(ca, "CURRENT_STATE_FILE", target):
                ca.cmd_update_context(None)
                self.assertTrue(target.exists())
                self.assertIn("# Current State", target.read_text(encoding="utf-8"))

    def test_append_index_appends_without_clobbering(self):
        with tempfile.TemporaryDirectory() as tmp:
            indexes_dir = Path(tmp) / "indexes"
            indexes_dir.mkdir()
            with patch.object(ca, "INDEXES_DIR", indexes_dir):
                ca.append_index("decisions", {"id": "DEC-1"})
                ca.append_index("decisions", {"id": "DEC-2"})
                data = json.loads((indexes_dir / "decisions.json").read_text(encoding="utf-8"))
                self.assertEqual([d["id"] for d in data], ["DEC-1", "DEC-2"])

    def test_append_index_tolerates_missing_context_dir(self):
        missing = Path(tempfile.gettempdir()) / "capital_agent_test_missing_context_dir"
        with patch.object(ca, "INDEXES_DIR", missing):
            ca.append_index("decisions", {"id": "DEC-X"})  # must not raise
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()

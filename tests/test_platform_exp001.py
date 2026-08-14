"""Tests for the platform-integration restructuring (EXP-001).

These guard the properties introduced when EXP-001 (Existing Platform
Commercialization) was added as a PLANNED-but-not-activated experiment:
domain/sunk-cost exclusion from accounting, and activation requiring an
explicit human record rather than any inference from technical completion.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _find_exp001():
    for p in (ROOT / "experiments" / "active").glob("*.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("code") == "EXP-001":
            return data, p
    return None, None


class TestExp001Planned(unittest.TestCase):
    def test_exp001_exists_and_is_planned_not_activated(self):
        data, path = _find_exp001()
        self.assertIsNotNone(data, "EXP-001 record not found in experiments/active/")
        self.assertEqual(data["state"], "PLANNED")
        self.assertEqual(data["status"], "planned")
        self.assertFalse(data["activation"]["activated"])
        self.assertIsNone(data["activation"]["activation_date"])

    def test_exp001_has_zero_capital_deployed(self):
        data, _ = _find_exp001()
        self.assertEqual(data["capital_deployed_brl"], 0.0)
        self.assertEqual(data["budget_brl"], 0.0)

    def test_exp001_domain_excluded_from_accounting(self):
        data, _ = _find_exp001()
        domain = data["cost_attribution"]["domain"]
        self.assertFalse(domain["attributable_to_capital_agent"])
        self.assertIn("OWNER-PROVIDED", domain["classification"])

    def test_exp001_pre_activation_costs_excluded(self):
        data, _ = _find_exp001()
        pre = data["cost_attribution"]["pre_activation_platform_costs"]
        self.assertFalse(pre["attributable_to_capital_agent"])

    def test_exp001_no_fabricated_metrics(self):
        data, _ = _find_exp001()
        metrics = data["metrics"]
        # Every leaf metric must be null (no data collected yet) -- never a
        # fabricated number -- until a real instrumentation source exists.
        def check(node):
            if isinstance(node, dict):
                for v in node.values():
                    check(v)
            else:
                self.assertIsNone(node, "metric must be null, not fabricated data")
        check({k: v for k, v in metrics.items() if k != "note"})

    def test_exp001_no_activation_date_anywhere_in_record(self):
        data, _ = _find_exp001()
        self.assertIsNone(data["activation"]["activation_date"])


class TestActivationChecklistExists(unittest.TestCase):
    def test_checklist_file_exists(self):
        path = ROOT / "experiments" / "EXP-001-ACTIVATION-CHECKLIST.md"
        self.assertTrue(path.exists())

    def test_checklist_states_activation_is_not_inferred(self):
        text = (ROOT / "experiments" / "EXP-001-ACTIVATION-CHECKLIST.md").read_text(encoding="utf-8")
        normalized = " ".join(text.lower().split())
        self.assertIn("by itself, activate the experiment", normalized)


class TestDomainExclusionDocumented(unittest.TestCase):
    def test_investment_policy_documents_domain_exclusion(self):
        text = (ROOT / "INVESTMENT_POLICY.md").read_text(encoding="utf-8")
        self.assertIn("attributable_to_capital_agent: false", text)
        self.assertIn("EXTERNAL / OWNER-PROVIDED ASSET", text)

    def test_investment_policy_documents_incremental_cost_test(self):
        text = (ROOT / "INVESTMENT_POLICY.md").read_text(encoding="utf-8")
        self.assertIn("Incremental cost test", text)


class TestNoLiveExecutionLanguageLeaksIntoPlatformDocs(unittest.TestCase):
    """Guards against reintroducing obsolete/contradictory concepts flagged
    by the contradiction inventory (journal/reviews/) when platform-related
    content is added to canonical docs."""

    FORBIDDEN = [
        r"broker adapter",
        r"exchange adapter",
        r"automatic order",
        r"bounded autonomous financial execution",
    ]

    def test_architecture_platform_section_has_no_forbidden_terms(self):
        text = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8").lower()
        for pattern in self.FORBIDDEN:
            self.assertNotRegex(text, pattern)

    def test_exp001_record_has_no_forbidden_terms(self):
        _, path = _find_exp001()
        text = path.read_text(encoding="utf-8").lower()
        for pattern in self.FORBIDDEN:
            self.assertNotRegex(text, pattern)


if __name__ == "__main__":
    unittest.main()

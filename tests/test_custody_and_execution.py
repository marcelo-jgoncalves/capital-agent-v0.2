"""Tests for the custody invariant and the Human Execution Request lifecycle.

These guard the core property introduced by this system change: the Capital
Agent must never execute a real financial operation itself. Every test here
runs against an isolated temp-directory sandbox (patched module paths), never
against the real repository state.
"""
import argparse
import contextlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("capital_agent", ROOT / "src" / "capital_agent.py")
ca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ca)

scheduler_spec = importlib.util.spec_from_file_location("scheduler", ROOT / "src" / "scheduler.py")
sch = importlib.util.module_from_spec(scheduler_spec)
scheduler_spec.loader.exec_module(sch)


POLICY = {
    "policy_version": "test",
    "currency": "BRL",
    "initial_capital": 1000.0,
    "execution_tier": 0,
    "live_execution_enabled": False,
    "autonomous_financial_execution_permitted": False,
    "autonomous_financial_execution_is_hard_invariant": True,
    "financial_execution_requires_human_confirmation": True,
    "financial_credentials_must_be_read_only": True,
    "borrowing_allowed": False,
    "leverage_allowed": False,
    "withdrawals_allowed": False,
    "max_single_live_allocation_pct_equity": 0.5,
    "max_total_experimental_capital_pct_equity": 0.3,
    "max_daily_new_risk_pct_equity": 0.5,
    "max_recurring_monthly_commitment_pct_equity": 0.05,
    "min_cash_reserve_pct_equity": 0.1,
    "hard_drawdown_freeze_pct": 0.2,
    "require_journal_for_material_allocation": True,
    "material_allocation_brl": 10.0,
    "human_gate_for_first_readonly_financial_adapter": True,
    "secret_storage": "environment_or_os_secret_store_only",
}

CRITICAL_POLICY = {
    "version": "test",
    "require_human_authorization_for_all_critical_decisions": True,
    "default_deny_if_classification_uncertain": True,
    "noncritical_live_money_threshold_brl": 25.0,
    "noncritical_max_loss_threshold_brl": 25.0,
    "noncritical_paid_ad_test_threshold_brl": 25.0,
    "recurring_commitment_is_always_critical": True,
    "new_business_model_with_external_obligations_is_always_critical": True,
    "new_live_financial_category_is_always_critical": True,
    "new_counterparty_with_write_authority_is_always_critical": True,
    "legal_or_regulatory_uncertainty_is_always_critical": True,
    "public_representation_of_owner_is_always_critical": True,
    "new_write_financial_credentials_are_always_critical": True,
    "policy_relaxation_is_always_critical": True,
    "critical_policy_change_is_always_critical": True,
}

GOVERNANCE = {
    "version": "test",
    "self_improvement_enabled": True,
    "autonomous_change_classes": ["A", "B"],
    "human_approval_change_classes": ["C"],
    "prohibited_change_classes": ["D"],
}


@contextlib.contextmanager
def sandbox():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "config").mkdir()
        (root / "data").mkdir()
        (root / "journal" / "decisions").mkdir(parents=True)
        (root / "journal" / "system_changes").mkdir(parents=True)
        (root / "experiments" / "active").mkdir(parents=True)
        (root / "experiments" / "archive").mkdir(parents=True)
        (root / "approvals" / "pending").mkdir(parents=True)
        (root / "approvals" / "archive").mkdir(parents=True)
        (root / "context" / "indexes").mkdir(parents=True)
        (root / "execution" / "human_requests" / "pending").mkdir(parents=True)
        (root / "execution" / "human_requests" / "completed").mkdir(parents=True)
        (root / "execution" / "human_requests" / "expired").mkdir(parents=True)
        (root / "execution" / "human_requests" / "cancelled").mkdir(parents=True)
        (root / "state").mkdir(parents=True)

        (root / "config" / "policy.json").write_text(json.dumps(POLICY), encoding="utf-8")
        (root / "config" / "critical_decisions.json").write_text(json.dumps(CRITICAL_POLICY), encoding="utf-8")
        (root / "config" / "system_governance.json").write_text(json.dumps(GOVERNANCE), encoding="utf-8")
        (root / "data" / "ledger.csv").write_text(
            "timestamp,type,category,amount_brl,description,reference\n"
            "2026-08-10T09:33:00-03:00,capital_in,reserve,1000.00,Initial experiment capital,INIT-0001\n",
            encoding="utf-8",
        )

        patches = {
            "ROOT": root,
            "POLICY_FILE": root / "config" / "policy.json",
            "CRITICAL_FILE": root / "config" / "critical_decisions.json",
            "SYSTEM_GOVERNANCE_FILE": root / "config" / "system_governance.json",
            "LEDGER_FILE": root / "data" / "ledger.csv",
            "DECISIONS_DIR": root / "journal" / "decisions",
            "SYSTEM_CHANGES_DIR": root / "journal" / "system_changes",
            "ACTIVE_EXPERIMENTS_DIR": root / "experiments" / "active",
            "ARCHIVE_EXPERIMENTS_DIR": root / "experiments" / "archive",
            "APPROVALS_PENDING_DIR": root / "approvals" / "pending",
            "APPROVALS_ARCHIVE_DIR": root / "approvals" / "archive",
            "APPROVALS_DIR": root / "approvals",
            "CONTEXT_DIR": root / "context",
            "CURRENT_STATE_FILE": root / "context" / "CURRENT_STATE.md",
            "INDEXES_DIR": root / "context" / "indexes",
            "EXECUTION_DIR": root / "execution",
            "HUMAN_REQUESTS_DIR": root / "execution" / "human_requests",
            "HR_PENDING_DIR": root / "execution" / "human_requests" / "pending",
            "HR_COMPLETED_DIR": root / "execution" / "human_requests" / "completed",
            "HR_EXPIRED_DIR": root / "execution" / "human_requests" / "expired",
            "HR_CANCELLED_DIR": root / "execution" / "human_requests" / "cancelled",
            "STATE_DIR": root / "state",
        }
        with patch.multiple(ca, **patches):
            yield root


def _execution_args(**overrides):
    defaults = dict(
        action="BUY", asset="TEST", quantity=2.0, max_price=5.0, max_total_capital=10.0,
        valid_until="2099-01-01T00:00:00-03:00", reason="test", expected_upside="test",
        max_loss=10.0, critic_assessment="test critic", decision_id=None, approval_id=None,
        destination_controlled_by_human=False, recurring=False, new_business_model=False,
        external_obligations=False, legal_uncertainty=False, public_representation=False,
        new_financial_write_access=False, policy_relaxation=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class CustodyInvariantTests(unittest.TestCase):
    def test_load_policy_rejects_autonomous_execution_flag(self):
        with sandbox() as root:
            bad_policy = dict(POLICY)
            bad_policy["autonomous_financial_execution_permitted"] = True
            (root / "config" / "policy.json").write_text(json.dumps(bad_policy), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                ca.load_policy()

    def test_propose_system_change_forces_rejection_for_autonomous_execution(self):
        with sandbox():
            args = argparse.Namespace(
                change_class="A", title="t", problem="p", change="c", benefit="b",
                enables_autonomous_financial_execution=True,
                acknowledge_no_autonomous_financial_execution=False,
            )
            with patch("builtins.print"):
                ca.cmd_propose_system_change(args)
            files = list(ca.SYSTEM_CHANGES_DIR.glob("*.md"))
            self.assertEqual(len(files), 1)
            content = files[0].read_text(encoding="utf-8")
            self.assertIn("Change class: D", content)
            self.assertIn("REJECTED_PROHIBITED", content)

    def test_propose_system_change_class_a_still_allowed_without_the_flag(self):
        with sandbox():
            args = argparse.Namespace(
                change_class="A", title="t", problem="p", change="c", benefit="b",
                enables_autonomous_financial_execution=False,
                acknowledge_no_autonomous_financial_execution=False,
            )
            with patch("builtins.print"):
                ca.cmd_propose_system_change(args)
            content = list(ca.SYSTEM_CHANGES_DIR.glob("*.md"))[0].read_text(encoding="utf-8")
            self.assertIn("PROPOSED_AUTONOMOUSLY_ALLOWED", content)

    def test_propose_system_change_flags_custody_risk_keywords_without_flag(self):
        with sandbox():
            args = argparse.Namespace(
                change_class="A", title="t", problem="p",
                change="Add a place_order() call to the new adapter.", benefit="b",
                enables_autonomous_financial_execution=False,
                acknowledge_no_autonomous_financial_execution=False,
            )
            with self.assertRaises(SystemExit):
                ca.cmd_propose_system_change(args)
            self.assertEqual(len(list(ca.SYSTEM_CHANGES_DIR.glob("*.md"))), 0)

    def test_propose_system_change_allows_keyword_match_with_explicit_acknowledgment(self):
        with sandbox():
            args = argparse.Namespace(
                change_class="A", title="t", problem="p",
                change="Document why place_order() must never be added.", benefit="b",
                enables_autonomous_financial_execution=False,
                acknowledge_no_autonomous_financial_execution=True,
            )
            with patch("builtins.print"):
                ca.cmd_propose_system_change(args)
            self.assertEqual(len(list(ca.SYSTEM_CHANGES_DIR.glob("*.md"))), 1)

    def test_no_broker_or_exchange_client_library_referenced_in_source(self):
        forbidden = ["ccxt", "alpaca", "ib_insync", "robin_stocks", "binance", "metatrader"]
        src_text = (ROOT / "src" / "capital_agent.py").read_text(encoding="utf-8").lower()
        src_text += (ROOT / "src" / "scheduler.py").read_text(encoding="utf-8").lower()
        for name in forbidden:
            self.assertNotIn(name, src_text)

    def test_no_write_methods_on_ai_provider_adapter_contract(self):
        base_text = (ROOT / "adapters" / "ai_providers" / "base.py").read_text(encoding="utf-8").lower()
        for forbidden in ("def buy(", "def sell(", "def transfer(", "def withdraw(", "def place_order("):
            self.assertNotIn(forbidden, base_text)

    def test_scheduler_source_names_no_ai_vendor(self):
        scheduler_text = (ROOT / "src" / "scheduler.py").read_text(encoding="utf-8").lower()
        for vendor in ("claude", "anthropic", "openai", "codex", "gemini"):
            self.assertNotIn(vendor, scheduler_text)

    def test_no_delete_command_exists_for_governance_artifacts(self):
        for forbidden_attr in ("cmd_delete_decision", "cmd_delete_approval", "cmd_delete_system_change"):
            self.assertFalse(hasattr(ca, forbidden_attr))

    def test_record_refuses_buy_sell_and_capital_out(self):
        with sandbox():
            for blocked_type in ("buy", "sell", "capital_out"):
                args = argparse.Namespace(
                    type=blocked_type, category="market", amount=10.0,
                    description="attempted direct entry", reference="TEST",
                )
                ledger_before = ca.LEDGER_FILE.read_text(encoding="utf-8")
                with self.assertRaises(SystemExit):
                    ca.cmd_record(args)
                self.assertEqual(ca.LEDGER_FILE.read_text(encoding="utf-8"), ledger_before)

    def test_record_still_allows_non_execution_bookkeeping(self):
        with sandbox():
            args = argparse.Namespace(
                type="expense", category="infrastructure", amount=5.0,
                description="hosting", reference="TEST-EXP-1",
            )
            with patch("builtins.print"):
                ca.cmd_record(args)
            self.assertIn("TEST-EXP-1", ca.LEDGER_FILE.read_text(encoding="utf-8"))


class HumanExecutionRequestLifecycleTests(unittest.TestCase):
    def test_request_execution_creates_pending_without_touching_ledger(self):
        with sandbox():
            ledger_before = ca.LEDGER_FILE.read_text(encoding="utf-8")
            with patch("builtins.print"):
                ca.cmd_request_execution(_execution_args())
            self.assertEqual(ca.LEDGER_FILE.read_text(encoding="utf-8"), ledger_before)
            pending_files = list(ca.HR_PENDING_DIR.glob("*.json"))
            self.assertEqual(len(pending_files), 1)
            data = json.loads(pending_files[0].read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "pending")
            self.assertIsNone(data["confirmation"])

    def test_critical_execution_refused_without_approval(self):
        with sandbox():
            with self.assertRaises(SystemExit):
                ca.cmd_request_execution(_execution_args(max_total_capital=30.0, max_loss=30.0))
            self.assertEqual(len(list(ca.HR_PENDING_DIR.glob("*.json"))), 0)

    def test_critical_execution_refused_with_unapproved_approval_id(self):
        with sandbox():
            approval_args = argparse.Namespace(
                title="t", category="c", amount=30.0, max_loss=30.0, thesis="thesis",
                recurring=False, new_business_model=False, external_obligations=False,
                legal_uncertainty=False, public_representation=False,
                new_financial_write_access=False, policy_relaxation=False,
            )
            with patch("builtins.print"):
                ca.cmd_request_approval(approval_args)
            approval_id = list(ca.APPROVALS_PENDING_DIR.glob("*.md"))[0].stem
            with self.assertRaises(SystemExit):
                ca.cmd_request_execution(_execution_args(
                    max_total_capital=30.0, max_loss=30.0, approval_id=approval_id,
                ))

    def test_critical_execution_allowed_after_explicit_approval(self):
        with sandbox():
            approval_args = argparse.Namespace(
                title="t", category="c", amount=30.0, max_loss=30.0, thesis="thesis",
                recurring=False, new_business_model=False, external_obligations=False,
                legal_uncertainty=False, public_representation=False,
                new_financial_write_access=False, policy_relaxation=False,
            )
            with patch("builtins.print"):
                ca.cmd_request_approval(approval_args)
            approval_path = list(ca.APPROVALS_PENDING_DIR.glob("*.md"))[0]
            approval_id = approval_path.stem
            text = approval_path.read_text(encoding="utf-8").replace(
                "## Human decision\n\nPENDING", "## Human decision\n\nAPPROVED"
            )
            approval_path.write_text(text, encoding="utf-8")

            with patch("builtins.print"):
                ca.cmd_request_execution(_execution_args(
                    max_total_capital=30.0, max_loss=30.0, approval_id=approval_id,
                ))
            self.assertEqual(len(list(ca.HR_PENDING_DIR.glob("*.json"))), 1)

    def test_transfer_requires_human_controlled_destination_flag(self):
        with sandbox():
            with self.assertRaises(SystemExit):
                ca.cmd_request_execution(_execution_args(action="TRANSFER", destination_controlled_by_human=False))

    def test_confirm_execution_is_the_only_path_to_completed_and_ledger_update(self):
        with sandbox():
            with patch("builtins.print"):
                ca.cmd_request_execution(_execution_args())
            request_id = list(ca.HR_PENDING_DIR.glob("*.json"))[0].stem
            cash_before = ca.cash_balance()

            confirm_args = argparse.Namespace(
                id=request_id, executed_quantity=2.0, executed_price=4.9, fees=0.5,
                executed_timestamp=None, category=None, ledger_type=None, notes="",
            )
            with patch("builtins.print"):
                ca.cmd_confirm_execution(confirm_args)

            self.assertEqual(len(list(ca.HR_PENDING_DIR.glob("*.json"))), 0)
            completed = list(ca.HR_COMPLETED_DIR.glob("*.json"))
            self.assertEqual(len(completed), 1)
            data = json.loads(completed[0].read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "completed")
            self.assertIsNotNone(data["confirmation"])
            self.assertAlmostEqual(ca.cash_balance(), cash_before - (2.0 * 4.9 + 0.5), places=2)

    def test_cancel_execution_never_touches_ledger(self):
        with sandbox():
            with patch("builtins.print"):
                ca.cmd_request_execution(_execution_args())
            request_id = list(ca.HR_PENDING_DIR.glob("*.json"))[0].stem
            cash_before = ca.cash_balance()
            with patch("builtins.print"):
                ca.cmd_cancel_execution(argparse.Namespace(id=request_id, reason="changed my mind"))
            self.assertEqual(ca.cash_balance(), cash_before)
            self.assertEqual(len(list(ca.HR_CANCELLED_DIR.glob("*.json"))), 1)
            self.assertEqual(len(list(ca.HR_PENDING_DIR.glob("*.json"))), 0)

    def test_expire_execution_never_touches_ledger(self):
        with sandbox():
            with patch("builtins.print"):
                ca.cmd_request_execution(_execution_args())
            request_id = list(ca.HR_PENDING_DIR.glob("*.json"))[0].stem
            cash_before = ca.cash_balance()
            with patch("builtins.print"):
                ca.cmd_expire_execution(argparse.Namespace(id=request_id, reason=None))
            self.assertEqual(ca.cash_balance(), cash_before)
            self.assertEqual(len(list(ca.HR_EXPIRED_DIR.glob("*.json"))), 1)

    def test_sweep_expired_executions_is_deterministic_and_does_not_touch_ledger(self):
        with sandbox():
            with patch("builtins.print"):
                ca.cmd_request_execution(_execution_args(valid_until="2000-01-01T00:00:00-03:00"))
            cash_before = ca.cash_balance()
            with patch("builtins.print"):
                ca.cmd_sweep_expired_executions(argparse.Namespace())
            self.assertEqual(ca.cash_balance(), cash_before)
            self.assertEqual(len(list(ca.HR_EXPIRED_DIR.glob("*.json"))), 1)
            self.assertEqual(len(list(ca.HR_PENDING_DIR.glob("*.json"))), 0)

    def test_build_current_state_lists_pending_execution_request_without_claiming_it_executed(self):
        with sandbox():
            with patch("builtins.print"):
                ca.cmd_request_execution(_execution_args())
            request_id = list(ca.HR_PENDING_DIR.glob("*.json"))[0].stem
            content = ca.build_current_state()
            self.assertIn(request_id, content)
            self.assertIn("Pending Human Execution Requests", content)


class StartHereReconstructionTests(unittest.TestCase):
    def test_start_here_exists_with_required_anchors(self):
        content = (ROOT / "START_HERE.md").read_text(encoding="utf-8")
        self.assertIn("assume the operation of the Capital Agent", content)
        self.assertIn("AI_OPERATING_MANUAL.md", content)
        self.assertIn("custody", content.lower())
        self.assertIn("CURRENT_STATE.md", content)

    def test_claude_md_and_agents_md_defer_to_start_here(self):
        for filename in ("CLAUDE.md", "AGENTS.md"):
            content = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn("START_HERE.md", content)


class SchedulerVendorNeutralityTests(unittest.TestCase):
    def test_due_frequencies_computed_purely_from_config_and_state(self):
        schedules = {"frequent": {"interval_minutes": 1, "jobs": ["x"], "requires_ai_reasoning": False}}
        state = {"last_frequency_run": {}}
        import datetime as dt
        now = dt.datetime.now(dt.timezone.utc)
        due = sch.due_frequencies(schedules, state, now)
        self.assertEqual(due, ["frequent"])

    def test_enqueue_deduplicates_pending_jobs(self):
        pending = []
        job1 = sch.enqueue(pending, "k", "scheduled", False, "hint")
        job2 = sch.enqueue(pending, "k", "scheduled", False, "hint")
        self.assertIsNotNone(job1)
        self.assertIsNone(job2)
        self.assertEqual(len(pending), 1)


if __name__ == "__main__":
    unittest.main()

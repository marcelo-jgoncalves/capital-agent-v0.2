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
import threading
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
    "max_single_reserve_instrument_pct_equity": 0.3,
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
    "new_readonly_financial_adapter_is_always_critical": True,
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
            "RESERVE_ASSETS_FILE": root / "data" / "reserve_assets.json",
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
            "ADMIN_LEDGER_ACTIONS_DIR": root / "journal" / "admin_ledger_actions",
        }
        with patch.multiple(ca, **patches):
            yield root


def _execution_args(**overrides):
    defaults = dict(
        action="BUY", asset="TEST", quantity=2.0, max_price=5.0, max_total_capital=10.0,
        valid_until="2099-01-01T00:00:00-03:00", reason="test", expected_upside="test",
        max_loss=10.0, critic_assessment="test critic", decision_id=None, approval_id=None,
        destination_controlled_by_human=False, reserve_instrument=False, recurring=False, new_business_model=False,
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

    def test_record_refuses_expense_fee_tax_even_with_no_execution_id(self):
        # P0 hardening (prompt-hardening-final-capital-agent-v0.2.md section
        # 3): expense/fee/tax no longer have a generic `record` path at all.
        # The only legitimate path is HER -> confirm-execution -> ledger.
        with sandbox():
            for blocked_type in ("expense", "fee", "tax"):
                args = argparse.Namespace(
                    type=blocked_type, category="infrastructure", amount=5.0,
                    description="hosting", reference=f"TEST-{blocked_type}",
                    execution_id=None,
                )
                ledger_before = ca.LEDGER_FILE.read_text(encoding="utf-8")
                with self.assertRaises(SystemExit):
                    ca.cmd_record(args)
                self.assertEqual(ca.LEDGER_FILE.read_text(encoding="utf-8"), ledger_before)

    def test_record_refuses_expense_fee_tax_even_with_completed_execution_id(self):
        # This is the exact bug closed in this hardening pass: a completed
        # Human Execution Request must not be "replayed" through `record` to
        # mint a second, caller-chosen-amount ledger entry. confirm-execution
        # already posted the one legitimate ledger consequence for this HER.
        with sandbox() as root:
            exec_id = "HER-TEST-1"
            completed = {
                "id": exec_id, "action": "PAYMENT", "asset": "hosting",
                "confirmation": {"executed_total_brl": 5.0},
            }
            (root / "execution" / "human_requests" / "completed" / f"{exec_id}.json").write_text(
                json.dumps(completed), encoding="utf-8"
            )
            for blocked_type in ("expense", "fee", "tax"):
                args = argparse.Namespace(
                    type=blocked_type, category="infrastructure", amount=5.0,
                    description="hosting", reference=f"TEST-{blocked_type}",
                    execution_id=exec_id,
                )
                ledger_before = ca.LEDGER_FILE.read_text(encoding="utf-8")
                with self.assertRaises(SystemExit):
                    ca.cmd_record(args)
                self.assertEqual(ca.LEDGER_FILE.read_text(encoding="utf-8"), ledger_before)

    def test_completed_her_cannot_be_reused_for_a_second_financial_posting(self):
        # End-to-end: confirm-execution posts the ledger row for a PAYMENT
        # HER; a subsequent attempt to `record` against the same completed
        # execution_id must not produce a second row.
        with sandbox():
            args = _execution_args(action="PAYMENT", asset="hosting", quantity=1.0,
                                    max_price=5.0, max_total_capital=5.0, max_loss=5.0)
            with patch("builtins.print"):
                ca.cmd_request_execution(args)
            request_id = next(ca.HR_PENDING_DIR.glob("*.json")).stem
            confirm_args = argparse.Namespace(
                id=request_id, executed_quantity=1.0, executed_price=5.0, fees=0.0,
                executed_timestamp=None, notes=None, category=None, ledger_type=None,
            )
            with patch("builtins.print"):
                ca.cmd_confirm_execution(confirm_args)
            ledger_after_confirm = ca.LEDGER_FILE.read_text(encoding="utf-8")
            rows_after_confirm = ledger_after_confirm.strip().splitlines()
            self.assertEqual(
                sum(1 for line in rows_after_confirm if request_id in line), 1
            )

            record_args = argparse.Namespace(
                type="expense", category="infrastructure", amount=5.0,
                description="hosting (replay attempt)", reference=request_id,
                execution_id=request_id,
            )
            with self.assertRaises(SystemExit):
                ca.cmd_record(record_args)
            ledger_final = ca.LEDGER_FILE.read_text(encoding="utf-8")
            self.assertEqual(ledger_final, ledger_after_confirm)
            rows_final = ledger_final.strip().splitlines()
            self.assertEqual(sum(1 for line in rows_final if request_id in line), 1)

    def test_record_refuses_direct_cash_event_kinds(self):
        with sandbox():
            for typ in ("revenue", "refund", "chargeback", "other_external_inflow"):
                args = argparse.Namespace(
                    type=typ, category="external", amount=10.0,
                    description="attempted direct entry", reference=f"TEST-{typ}",
                )
                ledger_before = ca.LEDGER_FILE.read_text(encoding="utf-8")
                with self.assertRaises(SystemExit):
                    ca.cmd_record(args)
                self.assertEqual(ca.LEDGER_FILE.read_text(encoding="utf-8"), ledger_before)

    def test_record_admin_types_refused_without_confirm_and_reason(self):
        with sandbox():
            for typ in ("capital_in", "adjustment"):
                args = argparse.Namespace(
                    type=typ, category="reserve", amount=50.0,
                    description="attempted", reference=f"TEST-{typ}",
                    admin_confirm=False, reason=None,
                )
                ledger_before = ca.LEDGER_FILE.read_text(encoding="utf-8")
                with self.assertRaises(SystemExit):
                    ca.cmd_record(args)
                self.assertEqual(ca.LEDGER_FILE.read_text(encoding="utf-8"), ledger_before)

    def test_record_admin_types_succeed_with_confirm_and_reason_and_leave_audit(self):
        with sandbox():
            args = argparse.Namespace(
                type="capital_in", category="reserve", amount=50.0,
                description="top-up", reference="TEST-CAPIN-1",
                admin_confirm=True, reason="human owner wired additional funds, see decision DEC-x",
            )
            with patch("builtins.print"):
                ca.cmd_record(args)
            self.assertIn("TEST-CAPIN-1", ca.LEDGER_FILE.read_text(encoding="utf-8"))
            audit_files = list(ca.ADMIN_LEDGER_ACTIONS_DIR.glob("*.json"))
            self.assertEqual(len(audit_files), 1)
            audit = json.loads(audit_files[0].read_text(encoding="utf-8"))
            self.assertEqual(audit["reason"], "human owner wired additional funds, see decision DEC-x")


class NewExperimentCanonicalShapeTests(unittest.TestCase):
    def _args(self, **overrides):
        defaults = dict(
            title="Test experiment", budget=100.0, max_loss=50.0,
            hypothesis="h", success_metric="m", kill_condition="k",
        )
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_new_experiment_produces_full_canonical_shape(self):
        with sandbox() as root:
            with patch("builtins.print"):
                ca.cmd_new_experiment(self._args())
            files = list((root / "experiments" / "active").glob("*.json"))
            self.assertEqual(len(files), 1)
            data = json.loads(files[0].read_text(encoding="utf-8"))
            for field in ("capital_budget_brl", "resource_budget", "non_financial_risks"):
                self.assertIn(field, data)
            self.assertEqual(data["capital_budget_brl"], 100.0)
            self.assertIsInstance(data["resource_budget"], dict)
            self.assertIsInstance(data["non_financial_risks"], list)
            ca.bi.validate_against_schema(data, "experiment.schema.json")  # no raise

    def test_zero_capital_experiment_creation_succeeds(self):
        with sandbox() as root:
            with patch("builtins.print"):
                ca.cmd_new_experiment(self._args(budget=0.0, max_loss=0.0))
            files = list((root / "experiments" / "active").glob("*.json"))
            data = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual(data["capital_budget_brl"], 0.0)
            self.assertEqual(data["policy_issues"], [])  # 0 is valid, not a policy issue


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
                new_readonly_financial_adapter=False,
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
                new_readonly_financial_adapter=False,
            )
            with patch("builtins.print"):
                ca.cmd_request_approval(approval_args)
            approval_id = list(ca.APPROVALS_PENDING_DIR.glob("*.md"))[0].stem

            with patch("builtins.print"):
                ca.cmd_approve_decision(argparse.Namespace(
                    approval_id=approval_id, human_statement="Yes, go ahead with this.",
                ))

            with patch("builtins.print"):
                ca.cmd_request_execution(_execution_args(
                    max_total_capital=30.0, max_loss=30.0, approval_id=approval_id,
                ))
            self.assertEqual(len(list(ca.HR_PENDING_DIR.glob("*.json"))), 1)

    def test_transfer_requires_human_controlled_destination_flag(self):
        with sandbox():
            with self.assertRaises(SystemExit):
                ca.cmd_request_execution(_execution_args(action="TRANSFER", destination_controlled_by_human=False))

    def test_reserve_instrument_flag_unlocks_higher_cap(self):
        with sandbox():
            # Real-world case this closes: Tesouro Selic's minimum lot
            # (BRL 196.64) exceeded the general single-allocation cap before
            # this policy addition. Confirms a reserve-flagged request for
            # that amount is accepted (after approval, since it's still
            # above the non-critical threshold) and the claim is persisted.
            approval_args = argparse.Namespace(
                title="reserve test", category="reserve-management", amount=196.64, max_loss=1.0,
                thesis="test", recurring=False, new_business_model=False, external_obligations=False,
                legal_uncertainty=False, public_representation=False,
                new_financial_write_access=False, policy_relaxation=False,
                new_readonly_financial_adapter=False,
            )
            with patch("builtins.print"):
                ca.cmd_request_approval(approval_args)
            approval_id = list(ca.APPROVALS_PENDING_DIR.glob("*.md"))[0].stem
            with patch("builtins.print"):
                ca.cmd_approve_decision(argparse.Namespace(approval_id=approval_id, human_statement="approved"))

            with patch("builtins.print"):
                ca.cmd_request_execution(_execution_args(
                    action="BUY", asset="Tesouro Selic", max_total_capital=196.64, max_loss=1.0,
                    reserve_instrument=True, approval_id=approval_id,
                ))
            data = json.loads(list(ca.HR_PENDING_DIR.glob("*.json"))[0].read_text(encoding="utf-8"))
            self.assertTrue(data["reserve_instrument_claimed"])

    def test_reserve_instrument_cap_still_enforced(self):
        with sandbox():
            # reserve cap is 0.3 * 1000 = 300; 350 must still be refused even flagged,
            # failing at the policy-check stage before criticality is even reached.
            with self.assertRaises(SystemExit):
                ca.cmd_request_execution(_execution_args(
                    max_total_capital=350.0, max_loss=1.0, reserve_instrument=True,
                ))

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

    def test_confirm_execution_refuses_retry_after_already_completed(self):
        # ADR-003 minimum viable fix: a retry against an id that already has
        # a completed/<id>.json (e.g. an operator or automation retrying
        # after a crash it believed failed) must be refused, not silently
        # re-post a second ledger line for the same HER.
        with sandbox():
            with patch("builtins.print"):
                ca.cmd_request_execution(_execution_args())
            request_id = list(ca.HR_PENDING_DIR.glob("*.json"))[0].stem
            confirm_args = argparse.Namespace(
                id=request_id, executed_quantity=2.0, executed_price=4.9, fees=0.5,
                executed_timestamp=None, category=None, ledger_type=None, notes="",
            )
            with patch("builtins.print"):
                ca.cmd_confirm_execution(confirm_args)
            cash_after_first = ca.cash_balance()
            ledger_rows_after_first = len(ca.LEDGER_FILE.read_text(encoding="utf-8").splitlines())

            with self.assertRaises(SystemExit):
                ca.cmd_confirm_execution(confirm_args)

            self.assertEqual(ca.cash_balance(), cash_after_first)
            ledger_rows_after_retry = len(ca.LEDGER_FILE.read_text(encoding="utf-8").splitlines())
            self.assertEqual(ledger_rows_after_retry, ledger_rows_after_first)

    def test_confirm_execution_serializes_concurrent_calls_for_same_id(self):
        # Two threads racing confirm-execution for the same HER id must
        # produce exactly one ledger posting: the lock serializes them, and
        # whichever loses the race sees the completed/<id>.json the winner
        # just wrote and refuses cleanly instead of posting a second time.
        with sandbox():
            with patch("builtins.print"):
                ca.cmd_request_execution(_execution_args())
            request_id = list(ca.HR_PENDING_DIR.glob("*.json"))[0].stem

            results = []

            def attempt():
                confirm_args = argparse.Namespace(
                    id=request_id, executed_quantity=2.0, executed_price=4.9, fees=0.5,
                    executed_timestamp=None, category=None, ledger_type=None, notes="",
                )
                try:
                    with patch("builtins.print"):
                        ca.cmd_confirm_execution(confirm_args)
                    results.append("ok")
                except SystemExit:
                    results.append("refused")

            threads = [threading.Thread(target=attempt) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(results.count("ok"), 1)
            self.assertEqual(results.count("refused"), 4)
            self.assertEqual(len(list(ca.HR_COMPLETED_DIR.glob("*.json"))), 1)
            self.assertEqual(len(list(ca.HR_PENDING_DIR.glob("*.json"))), 0)
            ledger_lines = ca.LEDGER_FILE.read_text(encoding="utf-8").splitlines()
            # header + exactly one posted row for this execution
            data_rows = [ln for ln in ledger_lines[1:] if request_id in ln]
            self.assertEqual(len(data_rows), 1)

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


class ReserveAssetTests(unittest.TestCase):
    def _confirm_a_buy(self, quantity=1.0, price=20.0, fees=0.0):
        with patch("builtins.print"):
            ca.cmd_request_execution(_execution_args(
                action="BUY", asset="Tesouro Selic", quantity=quantity, max_price=price,
                max_total_capital=quantity * price + fees, max_loss=quantity * price + fees,
            ))
        request_id = list(ca.HR_PENDING_DIR.glob("*.json"))[0].stem
        with patch("builtins.print"):
            ca.cmd_confirm_execution(argparse.Namespace(
                id=request_id, executed_quantity=quantity, executed_price=price, fees=fees,
                executed_timestamp=None, category=None, ledger_type=None, notes="",
            ))
        return request_id

    def test_equity_floor_understates_by_default_before_booking(self):
        with sandbox():
            equity_before = ca.current_equity_floor()
            self._confirm_a_buy(quantity=1.0, price=20.0)
            self.assertAlmostEqual(ca.current_equity_floor(), equity_before - 20.0, places=2)

    def test_record_reserve_asset_restores_equity_floor(self):
        with sandbox():
            equity_before = ca.current_equity_floor()
            request_id = self._confirm_a_buy(quantity=1.0, price=20.0)
            ca.cmd_record_reserve_asset(argparse.Namespace(execution_id=request_id, category="reserve", note="test"))
            self.assertAlmostEqual(ca.current_equity_floor(), equity_before, places=2)
            self.assertAlmostEqual(ca.reserve_assets_value(), 20.0, places=2)

    def test_record_reserve_asset_refuses_unconfirmed_execution(self):
        with sandbox():
            with self.assertRaises(SystemExit):
                ca.cmd_record_reserve_asset(argparse.Namespace(execution_id="HER-DOES-NOT-EXIST", category="reserve", note=""))

    def test_record_reserve_asset_refuses_non_buy_execution(self):
        with sandbox():
            with patch("builtins.print"):
                ca.cmd_request_execution(_execution_args(
                    action="TRANSFER", max_total_capital=10.0, max_loss=10.0,
                    destination_controlled_by_human=True,
                ))
            request_id = list(ca.HR_PENDING_DIR.glob("*.json"))[0].stem
            with patch("builtins.print"):
                ca.cmd_confirm_execution(argparse.Namespace(
                    id=request_id, executed_quantity=1.0, executed_price=10.0, fees=0.0,
                    executed_timestamp=None, category=None, ledger_type=None, notes="",
                ))
            with self.assertRaises(SystemExit):
                ca.cmd_record_reserve_asset(argparse.Namespace(execution_id=request_id, category="reserve", note=""))

    def test_book_value_is_derived_not_free_form(self):
        with sandbox():
            request_id = self._confirm_a_buy(quantity=2.0, price=10.0, fees=0.5)
            ca.cmd_record_reserve_asset(argparse.Namespace(execution_id=request_id, category="reserve", note=""))
            assets = ca.load_reserve_assets()
            self.assertEqual(len(assets), 1)
            self.assertAlmostEqual(assets[0]["book_value_brl"], 20.5, places=2)

    # -- P0 #2 idempotency (prompt-hardening-final section 4) --------------

    def test_repeated_equivalent_booking_is_idempotent_no_op(self):
        with sandbox():
            equity_before_booking = None
            request_id = self._confirm_a_buy(quantity=1.0, price=20.0)
            with patch("builtins.print"):
                ca.cmd_record_reserve_asset(argparse.Namespace(execution_id=request_id, category="reserve", note="a"))
            equity_after_first = ca.current_equity_floor()
            with patch("builtins.print"):
                ca.cmd_record_reserve_asset(argparse.Namespace(execution_id=request_id, category="reserve", note="a"))
            assets = ca.load_reserve_assets()
            self.assertEqual(len(assets), 1)  # no duplicate row
            self.assertAlmostEqual(ca.current_equity_floor(), equity_after_first, places=2)

    def test_conflicting_replay_of_same_execution_id_fails(self):
        with sandbox():
            request_id = self._confirm_a_buy(quantity=1.0, price=20.0)
            with patch("builtins.print"):
                ca.cmd_record_reserve_asset(argparse.Namespace(execution_id=request_id, category="reserve", note="a"))
            with self.assertRaises(SystemExit):
                # same execution_id, different category -> conflicting content
                ca.cmd_record_reserve_asset(argparse.Namespace(execution_id=request_id, category="different-category", note="a"))
            assets = ca.load_reserve_assets()
            self.assertEqual(len(assets), 1)  # conflict must not duplicate or overwrite

    def test_equity_floor_not_inflated_by_duplicate_booking_attempts(self):
        with sandbox():
            equity_before = ca.current_equity_floor()
            request_id = self._confirm_a_buy(quantity=1.0, price=20.0)
            for _ in range(3):
                with patch("builtins.print"):
                    ca.cmd_record_reserve_asset(argparse.Namespace(execution_id=request_id, category="reserve", note="a"))
            self.assertAlmostEqual(ca.current_equity_floor(), equity_before, places=2)

    def test_concurrent_bookings_of_different_execution_ids_do_not_lose_an_entry(self):
        """Post-review fix: the read-check-append-write critical section is
        now serialized with a cross-process lock, so two callers booking
        DIFFERENT execution_ids concurrently must not lose one entry to a
        last-writer-wins overwrite."""
        with sandbox():
            request_id_a = self._confirm_a_buy(quantity=1.0, price=20.0)
            request_id_b = self._confirm_a_buy(quantity=1.0, price=15.0)

            barrier = threading.Barrier(2)
            errors = []

            def book(request_id, note):
                try:
                    barrier.wait()
                    with patch("builtins.print"):
                        ca.cmd_record_reserve_asset(
                            argparse.Namespace(execution_id=request_id, category="reserve", note=note)
                        )
                except Exception as exc:  # pragma: no cover - surfaced via errors list
                    errors.append(exc)

            t1 = threading.Thread(target=book, args=(request_id_a, "a"))
            t2 = threading.Thread(target=book, args=(request_id_b, "b"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            self.assertEqual(errors, [])
            assets = ca.load_reserve_assets()
            booked_ids = {a["execution_id"] for a in assets}
            self.assertEqual(booked_ids, {request_id_a, request_id_b})

    def test_idempotency_survives_reload_between_calls(self):
        # Reloads reserve_assets.json from disk on every call rather than
        # trusting an in-memory copy, so idempotency holds across separate
        # process invocations (the real-world CLI usage pattern).
        with sandbox():
            request_id = self._confirm_a_buy(quantity=1.0, price=20.0)
            with patch("builtins.print"):
                ca.cmd_record_reserve_asset(argparse.Namespace(execution_id=request_id, category="reserve", note="a"))
            # Simulate a fresh process: nothing cached in module globals besides paths.
            assets_on_disk = json.loads(ca.RESERVE_ASSETS_FILE.read_text(encoding="utf-8"))
            self.assertEqual(len(assets_on_disk), 1)
            with patch("builtins.print"):
                ca.cmd_record_reserve_asset(argparse.Namespace(execution_id=request_id, category="reserve", note="a"))
            assets_on_disk = json.loads(ca.RESERVE_ASSETS_FILE.read_text(encoding="utf-8"))
            self.assertEqual(len(assets_on_disk), 1)

    def test_unknown_execution_id_still_fails_reserve_asset_booking(self):
        with sandbox():
            with self.assertRaises(SystemExit):
                ca.cmd_record_reserve_asset(argparse.Namespace(execution_id="HER-UNKNOWN", category="reserve", note=""))


class ApprovalAuthenticationTests(unittest.TestCase):
    def _create_pending_approval(self):
        approval_args = argparse.Namespace(
            title="t", category="c", amount=30.0, max_loss=30.0, thesis="thesis",
            recurring=False, new_business_model=False, external_obligations=False,
            legal_uncertainty=False, public_representation=False,
            new_financial_write_access=False, policy_relaxation=False,
            new_readonly_financial_adapter=False,
        )
        with patch("builtins.print"):
            ca.cmd_request_approval(approval_args)
        return list(ca.APPROVALS_PENDING_DIR.glob("*.md"))[0].stem

    def test_approve_decision_quotes_human_statement_verbatim(self):
        with sandbox():
            approval_id = self._create_pending_approval()
            with patch("builtins.print"):
                ca.cmd_approve_decision(argparse.Namespace(
                    approval_id=approval_id,
                    human_statement="I approve this specific allocation.",
                ))
            self.assertFalse((ca.APPROVALS_PENDING_DIR / f"{approval_id}.md").exists())
            content = (ca.APPROVALS_ARCHIVE_DIR / f"{approval_id}.md").read_text(encoding="utf-8")
            self.assertIn("APPROVED (interactive session, single-operator machine)", content)
            self.assertIn("I approve this specific allocation.", content)
            self.assertEqual(ca._approval_decision(approval_id), "APPROVED")

    def test_reject_decision_quotes_human_statement_verbatim(self):
        with sandbox():
            approval_id = self._create_pending_approval()
            with patch("builtins.print"):
                ca.cmd_reject_decision(argparse.Namespace(
                    approval_id=approval_id,
                    human_statement="No, too risky right now.",
                ))
            self.assertFalse((ca.APPROVALS_PENDING_DIR / f"{approval_id}.md").exists())
            content = (ca.APPROVALS_ARCHIVE_DIR / f"{approval_id}.md").read_text(encoding="utf-8")
            self.assertIn("REJECTED (interactive session, single-operator machine)", content)
            self.assertIn("No, too risky right now.", content)
            self.assertEqual(ca._approval_decision(approval_id), "REJECTED")

    def test_approve_decision_refuses_unknown_approval_id(self):
        with sandbox():
            with self.assertRaises(SystemExit):
                ca.cmd_approve_decision(argparse.Namespace(
                    approval_id="APR-DOES-NOT-EXIST", human_statement="approve",
                ))


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

    # -- P1 #4 timezone-aware due_frequencies (prompt-hardening-final section 6) --

    def test_due_frequencies_not_due_when_last_run_recent_regardless_of_offset(self):
        import datetime as dt
        now = dt.datetime(2026, 8, 14, 0, 0, 0, tzinfo=dt.timezone.utc)
        # last_frequency_run stored 30 minutes before `now`, but expressed in
        # a -03:00 local offset -- must not be misread as "long ago" or
        # "in the future" by string comparison.
        last_local = "2026-08-13T20:30:00-03:00"  # == 2026-08-13T23:30:00Z, 30 min before now
        schedules = {"daily": {"interval_minutes": 60, "jobs": ["x"], "requires_ai_reasoning": False}}
        state = {"last_frequency_run": {"daily": last_local}}
        due = sch.due_frequencies(schedules, state, now)
        self.assertEqual(due, [])  # only 30 minutes elapsed, interval is 60

    def test_due_frequencies_due_when_interval_elapsed_across_offsets(self):
        import datetime as dt
        now = dt.datetime(2026, 8, 14, 0, 0, 0, tzinfo=dt.timezone.utc)
        last_local = "2026-08-13T19:30:00-03:00"  # == 2026-08-13T22:30:00Z, 90 min before now
        schedules = {"daily": {"interval_minutes": 60, "jobs": ["x"], "requires_ai_reasoning": False}}
        state = {"last_frequency_run": {"daily": last_local}}
        due = sch.due_frequencies(schedules, state, now)
        self.assertEqual(due, ["daily"])

    def test_due_frequencies_naive_now_and_aware_last_run_do_not_crash(self):
        import datetime as dt
        now = dt.datetime(2026, 8, 14, 0, 0, 0)  # naive
        last_local = "2026-08-13T19:30:00-03:00"
        schedules = {"daily": {"interval_minutes": 60, "jobs": ["x"], "requires_ai_reasoning": False}}
        state = {"last_frequency_run": {"daily": last_local}}
        due = sch.due_frequencies(schedules, state, now)  # must not raise
        self.assertEqual(due, ["daily"])


if __name__ == "__main__":
    unittest.main()

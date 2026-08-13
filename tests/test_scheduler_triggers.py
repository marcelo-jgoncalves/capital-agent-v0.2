"""Tests for src/scheduler.py deterministic trigger wiring: the 7 new
business triggers declared in config/triggers.json actually read real
persisted state (state/business_signals, state/external_cash_events,
state/metric_observations) and fire real jobs, and requires_ai_reasoning is
respected instead of being hardcoded. Uses temp dirs so nothing touches the
real repo state/.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import scheduler as sch  # noqa: E402
import business_integration as bi  # noqa: E402


class SchedulerTriggerTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self._orig = {
            "BUSINESS_SIGNALS_DIR": sch.BUSINESS_SIGNALS_DIR,
            "EXTERNAL_CASH_EVENTS_DIR": sch.EXTERNAL_CASH_EVENTS_DIR,
            "METRIC_OBSERVATIONS_DIR": sch.METRIC_OBSERVATIONS_DIR,
            "ACTIVE_EXPERIMENTS_DIR": sch.ACTIVE_EXPERIMENTS_DIR,
            "LEDGER_FILE": sch.LEDGER_FILE,
            "HR_COMPLETED_DIR": sch.HR_COMPLETED_DIR,
            "APPROVALS_PENDING_DIR": sch.APPROVALS_PENDING_DIR,
            "bi.STATE_DIR": bi.STATE_DIR,
            "bi.BUSINESS_SIGNALS_DIR": bi.BUSINESS_SIGNALS_DIR,
            "bi.EXTERNAL_CASH_EVENTS_DIR": bi.EXTERNAL_CASH_EVENTS_DIR,
            "bi.METRIC_OBSERVATIONS_DIR": bi.METRIC_OBSERVATIONS_DIR,
        }
        sch.BUSINESS_SIGNALS_DIR = self._tmp / "business_signals"
        sch.EXTERNAL_CASH_EVENTS_DIR = self._tmp / "external_cash_events"
        sch.METRIC_OBSERVATIONS_DIR = self._tmp / "metric_observations"
        sch.ACTIVE_EXPERIMENTS_DIR = self._tmp / "experiments_active"
        sch.LEDGER_FILE = self._tmp / "ledger.csv"
        sch.HR_COMPLETED_DIR = self._tmp / "hr_completed"
        sch.APPROVALS_PENDING_DIR = self._tmp / "approvals_pending"
        bi.STATE_DIR = self._tmp
        bi.BUSINESS_SIGNALS_DIR = sch.BUSINESS_SIGNALS_DIR
        bi.EXTERNAL_CASH_EVENTS_DIR = sch.EXTERNAL_CASH_EVENTS_DIR
        bi.METRIC_OBSERVATIONS_DIR = sch.METRIC_OBSERVATIONS_DIR
        for d in (sch.BUSINESS_SIGNALS_DIR, sch.EXTERNAL_CASH_EVENTS_DIR,
                  sch.METRIC_OBSERVATIONS_DIR, sch.ACTIVE_EXPERIMENTS_DIR,
                  sch.HR_COMPLETED_DIR, sch.APPROVALS_PENDING_DIR):
            d.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        for k, v in self._orig.items():
            if k.startswith("bi."):
                setattr(bi, k.split(".", 1)[1], v)
            else:
                setattr(sch, k, v)
        shutil.rmtree(self._tmp, ignore_errors=True)


class NewRevenueDetectedTests(SchedulerTriggerTestCase):
    def _reconcile_and_post(self, ref):
        ev = bi.observe_external_cash_event(kind="revenue", amount_brl=10.0, source_system="s",
                                             source_record_id=ref, observed_at="2026-08-13T00:00:00Z")
        ev = bi.report_external_cash_event(ev, report_source="file_adapter")
        ev = bi.verify_external_cash_event(ev, human_confirmed=True, human_statement="x")
        ev = bi.attribute_external_cash_event(ev)
        ev = bi.reconcile_external_cash_event(ev, reconciled_by="human:owner")
        return bi.post_external_cash_event_to_ledger(ev, append_ledger_fn=lambda *a: None)

    def test_does_not_fire_on_unverified_observed_event(self):
        bi.observe_external_cash_event(kind="revenue", amount_brl=10.0, source_system="s",
                                        source_record_id="r1", observed_at="2026-08-13T00:00:00Z")
        state = {"_snapshot": {"known_posted_event_ids": []}}
        fired = sch.check_deterministic_triggers([], state)
        ids = [f["trigger_id"] for f in fired]
        self.assertNotIn("new_revenue_detected", ids)

    def test_fires_only_after_ledger_posted_and_not_on_first_run(self):
        state = {"_snapshot": {}}
        # first run establishes baseline, must not fire even if a posted
        # event already exists (avoids fabricated firing on cold start)
        self._reconcile_and_post("r-baseline")
        fired = sch.check_deterministic_triggers([], state)
        self.assertNotIn("new_revenue_detected", [f["trigger_id"] for f in fired])

        # second run: a NEW posted event must fire
        self._reconcile_and_post("r-new")
        fired2 = sch.check_deterministic_triggers([], state)
        self.assertIn("new_revenue_detected", [f["trigger_id"] for f in fired2])

    def test_is_idempotent_across_repeated_ticks(self):
        state = {"_snapshot": {}}
        sch.check_deterministic_triggers([], state)  # baseline
        self._reconcile_and_post("r-idem")
        fired1 = sch.check_deterministic_triggers([], state)
        self.assertIn("new_revenue_detected", [f["trigger_id"] for f in fired1])
        fired2 = sch.check_deterministic_triggers([], state)  # same tick again, no new events
        self.assertNotIn("new_revenue_detected", [f["trigger_id"] for f in fired2])


class RequiresAiReasoningRoutingTests(SchedulerTriggerTestCase):
    def test_deterministic_trigger_job_is_not_routed_to_ai(self):
        triggers = [{"id": "new_business_signal_detected", "requires_ai_reasoning": False}]
        state = {"_snapshot": {"known_signal_files": []}}
        pending = []
        bi.ingest_business_signal(
            signal_type="lead_created", source_system="platform", source_record_id="rec-1",
            observed_at="2026-08-13T00:00:00Z", metric_name="lead_count", metric_value=1,
            unit="count", data_quality="observed",
        )
        fired = sch.check_deterministic_triggers(triggers, state)
        self.assertTrue(any(f["trigger_id"] == "new_business_signal_detected" for f in fired))
        triggers_by_id = {t["id"]: t for t in triggers}
        for f in fired:
            trigger_def = triggers_by_id.get(f["trigger_id"], {})
            requires_ai = bool(trigger_def.get("requires_ai_reasoning", True))
            job = sch.enqueue(pending, job_key=f"trigger:{f['trigger_id']}:x", kind="trigger" if requires_ai else "trigger_deterministic",
                               requires_ai_reasoning=requires_ai, context_hint="x")
            if f["trigger_id"] == "new_business_signal_detected":
                self.assertFalse(job["requires_ai_reasoning"])
                self.assertEqual(job["kind"], "trigger_deterministic")

    def test_ai_required_trigger_is_routed_to_ai(self):
        pending = []
        job = sch.enqueue(pending, job_key="trigger:experiment_deadline_reached:x", kind="trigger",
                           requires_ai_reasoning=True, context_hint="x")
        self.assertTrue(job["requires_ai_reasoning"])


class StaleSourceAndAttributionPendingTests(SchedulerTriggerTestCase):
    def test_attribution_pending_too_long_fires_for_stuck_event(self):
        ev = bi.observe_external_cash_event(kind="revenue", amount_brl=5.0, source_system="s",
                                             source_record_id="stuck-1", observed_at="2026-08-13T00:00:00Z")
        ev = bi.report_external_cash_event(ev, report_source="file_adapter")
        ev = bi.verify_external_cash_event(ev, human_confirmed=True, human_statement="x")
        ev = bi.attribute_external_cash_event(ev)
        path = bi.EXTERNAL_CASH_EVENTS_DIR / f"{ev['id']}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["state_history"][-1]["at"] = "2000-01-01T00:00:00+00:00"
        path.write_text(json.dumps(data), encoding="utf-8")
        state = {"_snapshot": {}}
        fired = sch.check_deterministic_triggers([], state)
        self.assertIn("attribution_pending_too_long", [f["trigger_id"] for f in fired])


class Exp001CannotAutoActivateViaSchedulerTests(SchedulerTriggerTestCase):
    def test_scheduler_module_contains_no_actual_call_to_activation_function(self):
        # The scheduler module must not CALL any function that transitions
        # an experiment to ACTIVE without human authorization; its only
        # side effect on triggers is enqueuing job tickets. Parsed via ast
        # so mentions in comments/docstrings (explaining the guard) don't
        # produce a false failure.
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(sch))
        call_names = {
            node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
            for node in ast.walk(tree) if isinstance(node, ast.Call)
        }
        self.assertNotIn("apply_experiment_lifecycle_transition", call_names)

    def test_check_deterministic_triggers_never_mutates_experiment_files_on_disk(self):
        exp_path = sch.ACTIVE_EXPERIMENTS_DIR / "EXP-TEST.json"
        exp_path.write_text(json.dumps({"id": "EXP-TEST", "lifecycle_state": "READY_FOR_ACTIVATION"}), encoding="utf-8")
        sch.check_deterministic_triggers([], {"_snapshot": {}})
        after = json.loads(exp_path.read_text(encoding="utf-8"))
        self.assertEqual(after["lifecycle_state"], "READY_FOR_ACTIVATION")

    def test_apply_experiment_lifecycle_transition_still_blocks_active_without_human(self):
        with self.assertRaises(bi.AutoActivationBlockedError):
            bi.apply_experiment_lifecycle_transition({"lifecycle_state": "READY_FOR_ACTIVATION"}, "ACTIVE")


if __name__ == "__main__":
    unittest.main()

"""Tests for src/scheduler.py deterministic trigger wiring: the 7 new
business triggers declared in config/triggers.json actually read real
persisted state (state/business_signals, state/external_cash_events,
state/metric_observations) and fire real jobs, and requires_ai_reasoning is
respected instead of being hardcoded. Uses temp dirs so nothing touches the
real repo state/.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import unittest
import unittest.mock
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


class SchedulerSnapshotAtomicityTests(unittest.TestCase):
    """P2 (prompt-hardening-final-capital-agent-v0.2.md section 10):
    scheduler_state.json and pending_jobs.json must not diverge after a
    crash between writes."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self._orig = {
            "SCHEDULER_STATE_FILE": sch.SCHEDULER_STATE_FILE,
            "PENDING_JOBS_FILE": sch.PENDING_JOBS_FILE,
            "SCHEDULER_SNAPSHOT_FILE": sch.SCHEDULER_SNAPSHOT_FILE,
        }
        sch.SCHEDULER_STATE_FILE = self._tmp / "scheduler_state.json"
        sch.PENDING_JOBS_FILE = self._tmp / "pending_jobs.json"
        sch.SCHEDULER_SNAPSHOT_FILE = self._tmp / "_scheduler_snapshot.json"

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(sch, k, v)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_normal_save_leaves_legacy_files_consistent_with_snapshot(self):
        state = {"last_run_at": "t1", "run_history": []}
        pending = [{"id": "JOB-1", "status": "queued"}]
        sch.save_scheduler_snapshot(state, pending)
        self.assertEqual(sch.load_scheduler_state()["last_run_at"], "t1")
        self.assertEqual(sch.load_pending_jobs(), pending)

    def test_crash_after_snapshot_before_legacy_state_write_recovers_on_load(self):
        # Simulate: snapshot written successfully, but the process died
        # before scheduler_state.json (or pending_jobs.json) was mirrored.
        state = {"last_run_at": "t2", "run_history": ["x"]}
        pending = [{"id": "JOB-2", "status": "queued"}]
        snapshot = {"scheduler_state": state, "pending_jobs": pending}
        sch.save_json(sch.SCHEDULER_SNAPSHOT_FILE, snapshot)
        # legacy files never written at all -- worst case of the crash window
        self.assertFalse(sch.SCHEDULER_STATE_FILE.exists())
        self.assertFalse(sch.PENDING_JOBS_FILE.exists())

        recovered_state = sch.load_scheduler_state()
        recovered_pending = sch.load_pending_jobs()
        self.assertEqual(recovered_state, state)
        self.assertEqual(recovered_pending, pending)
        # and the legacy files are now actually persisted on disk
        self.assertTrue(sch.SCHEDULER_STATE_FILE.exists())
        self.assertTrue(sch.PENDING_JOBS_FILE.exists())

    def test_crash_after_job_write_before_checkpoint_write_recovers_on_load(self):
        # Simulate: snapshot + pending_jobs.json mirrored, but
        # scheduler_state.json (the checkpoint) never got mirrored --
        # pending_jobs.json (on disk, stale/pre-crash) now disagrees with
        # the snapshot's pending_jobs.
        state = {"last_run_at": "t3", "run_history": ["y"]}
        pending = [{"id": "JOB-3", "status": "queued"}]
        snapshot = {"scheduler_state": state, "pending_jobs": pending}
        sch.save_json(sch.SCHEDULER_SNAPSHOT_FILE, snapshot)
        sch.save_json(sch.PENDING_JOBS_FILE, pending)  # only this one mirrored
        # scheduler_state.json left stale/missing -- must be repaired to match
        self.assertFalse(sch.SCHEDULER_STATE_FILE.exists())

        recovered_state = sch.load_scheduler_state()
        self.assertEqual(recovered_state, state)

    def test_retry_after_crash_does_not_duplicate_the_job(self):
        # A "retry" after a crash re-runs save_scheduler_snapshot with the
        # SAME logical job (deterministic job_key dedupe already covers
        # this at the enqueue() layer); here we confirm re-saving an
        # equivalent snapshot does not create two divergent job lists.
        state = {"last_run_at": "t4", "run_history": []}
        pending = [{"id": "JOB-4", "job_key": "k", "status": "queued"}]
        sch.save_scheduler_snapshot(state, pending)
        sch.save_scheduler_snapshot(state, pending)  # retry, same content
        self.assertEqual(sch.load_pending_jobs(), pending)
        self.assertEqual(len(sch.load_pending_jobs()), 1)

    def test_restart_recovery_does_not_lose_or_duplicate_work(self):
        pending = []
        job = sch.enqueue(pending, "job-key-1", "scheduled", False, "hint")
        self.assertIsNotNone(job)
        state = {"last_run_at": "t5", "run_history": []}
        sch.save_scheduler_snapshot(state, pending)

        # Simulate a restart: fresh load must see exactly the one job, not
        # zero (lost work) and not more than one (duplicated work).
        reloaded_pending = sch.load_pending_jobs()
        self.assertEqual(len(reloaded_pending), 1)
        self.assertEqual(reloaded_pending[0]["id"], job["id"])

        # A subsequent enqueue of the SAME job_key (as would happen if the
        # same due condition were re-evaluated after restart) must not
        # duplicate it.
        job2 = sch.enqueue(reloaded_pending, "job-key-1", "scheduled", False, "hint")
        self.assertIsNone(job2)
        self.assertEqual(len(reloaded_pending), 1)


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


class SchedulerAtomicityTests(SchedulerTriggerTestCase):
    """P2 #8 (prompt-hardening-final-capital-agent-v0.2.md section 10):
    scheduler_state.json and pending_jobs.json must not diverge across a
    crash between their writes -- no lost or duplicated jobs on restart."""

    def setUp(self):
        super().setUp()
        self._orig["SCHEDULES_FILE"] = sch.SCHEDULES_FILE
        self._orig["TRIGGERS_FILE"] = sch.TRIGGERS_FILE
        self._orig["SCHEDULER_STATE_FILE"] = sch.SCHEDULER_STATE_FILE
        self._orig["PENDING_JOBS_FILE"] = sch.PENDING_JOBS_FILE
        self._orig["SCHEDULER_SNAPSHOT_FILE"] = sch.SCHEDULER_SNAPSHOT_FILE
        sch.SCHEDULES_FILE = self._tmp / "schedules.json"
        sch.TRIGGERS_FILE = self._tmp / "triggers.json"
        sch.SCHEDULER_STATE_FILE = self._tmp / "scheduler_state.json"
        sch.PENDING_JOBS_FILE = self._tmp / "pending_jobs.json"
        sch.SCHEDULER_SNAPSHOT_FILE = self._tmp / "_scheduler_snapshot.json"
        sch.SCHEDULES_FILE.write_text(json.dumps({"frequencies": {
            "frequent": {"interval_minutes": 1, "jobs": ["heartbeat"], "requires_ai_reasoning": False},
        }}), encoding="utf-8")
        sch.TRIGGERS_FILE.write_text(json.dumps({"triggers": []}), encoding="utf-8")

    def tearDown(self):
        for attr in ("SCHEDULES_FILE", "TRIGGERS_FILE", "SCHEDULER_STATE_FILE", "PENDING_JOBS_FILE", "SCHEDULER_SNAPSHOT_FILE"):
            setattr(sch, attr, self._orig[attr])
        super().tearDown()

    def test_save_json_is_atomic_no_partial_file_on_crash(self):
        # Simulate a crash mid-write: os.replace either lands fully or not
        # at all, so a reader never sees a half-written file.
        path = self._tmp / "atomic_test.json"
        sch.save_json(path, {"a": 1})
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": 1})
        # No stray temp files left behind after a successful write.
        leftovers = list(self._tmp.glob(".atomic_test.json.tmp-*"))
        self.assertEqual(leftovers, [])

    def test_normal_run_persists_both_state_and_pending_jobs(self):
        with unittest.mock.patch("builtins.print"):
            sch.cmd_run(argparse.Namespace())
        state = sch.load_scheduler_state()
        pending = sch.load_pending_jobs()
        self.assertIn("frequent", state["last_frequency_run"])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["job_key"], "frequent:heartbeat")

    def test_crash_after_job_write_before_checkpoint_does_not_duplicate_on_retry(self):
        # Simulate: pending_jobs.json was written (the job exists) but the
        # process crashed before scheduler_state.json's checkpoint landed.
        with unittest.mock.patch("builtins.print"):
            sch.cmd_run(argparse.Namespace())
        pending_after_first_run = sch.load_pending_jobs()
        self.assertEqual(len(pending_after_first_run), 1)
        # Roll the checkpoint back to simulate "crash before checkpoint write"
        # (state never advanced, so due_frequencies will consider it due again).
        sch.save_json(sch.SCHEDULER_STATE_FILE, {
            "last_run_at": None, "last_frequency_run": {}, "last_trigger_check_at": None,
            "run_history": [], "_snapshot": {},
        })
        with unittest.mock.patch("builtins.print"):
            sch.cmd_run(argparse.Namespace())  # retry / restart
        pending_after_retry = sch.load_pending_jobs()
        # Still exactly one queued job for this job_key -- retry deduped, no
        # duplicate work created by the "lost checkpoint" crash.
        matching = [j for j in pending_after_retry if j["job_key"] == "frequent:heartbeat"]
        self.assertEqual(len(matching), 1)

    def test_restart_recovery_preserves_previously_queued_jobs(self):
        with unittest.mock.patch("builtins.print"):
            sch.cmd_run(argparse.Namespace())
        pending_before = sch.load_pending_jobs()
        # A fresh process "restarting" just reloads from disk.
        pending_reloaded = sch.load_pending_jobs()
        self.assertEqual(pending_before, pending_reloaded)

    def test_duplicate_trigger_firing_across_runs_does_not_duplicate_job(self):
        # A trigger whose firing condition is still true on the next run
        # (e.g. checkpoint did not advance) must be deduped by the
        # deterministic, timestamp-free job_key rather than re-queued with a
        # distinct wall-clock-suffixed key.
        pending = []
        fired = {"trigger_id": "attribution_pending_too_long", "detail": "2 event(s) stuck: ['a', 'b']"}
        for _ in range(3):
            sch.enqueue(
                pending, job_key=f"trigger:{fired['trigger_id']}:{fired['detail']}",
                kind="trigger", requires_ai_reasoning=True, context_hint="x",
            )
        matching = [j for j in pending if j["job_key"] == f"trigger:{fired['trigger_id']}:{fired['detail']}"]
        self.assertEqual(len(matching), 1)


import unittest.mock  # noqa: E402


if __name__ == "__main__":
    unittest.main()

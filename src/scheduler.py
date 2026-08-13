#!/usr/bin/env python3
"""Deterministic-first scheduler/orchestrator for the Capital Agent.

This script never calls an AI model. It decides, using only repository state
and simple arithmetic, whether a scheduled job is due or an event trigger has
fired, and if so writes a job ticket to state/pending_jobs.json. Whichever AI
operator is configured (see adapters/ai_providers/) dequeues those tickets and
does the actual reasoning. See ARCHITECTURE.md "Scheduler and orchestration".

Intended to be invoked periodically by an external scheduler (cron, Windows
Task Scheduler, a CI schedule, etc.) via:

    python src/scheduler.py run
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import business_integration as bi  # noqa: E402

SCHEDULES_FILE = ROOT / "config" / "schedules.json"
TRIGGERS_FILE = ROOT / "config" / "triggers.json"
STATE_DIR = ROOT / "state"
SCHEDULER_STATE_FILE = STATE_DIR / "scheduler_state.json"
PENDING_JOBS_FILE = STATE_DIR / "pending_jobs.json"
LEDGER_FILE = ROOT / "data" / "ledger.csv"
APPROVALS_PENDING_DIR = ROOT / "approvals" / "pending"
HR_COMPLETED_DIR = ROOT / "execution" / "human_requests" / "completed"
BUSINESS_SIGNALS_DIR = STATE_DIR / "business_signals"
EXTERNAL_CASH_EVENTS_DIR = STATE_DIR / "external_cash_events"
METRIC_OBSERVATIONS_DIR = STATE_DIR / "metric_observations"
ACTIVE_EXPERIMENTS_DIR = ROOT / "experiments" / "active"

# Default staleness/grace windows for triggers that need one and aren't
# individually configured elsewhere. Deterministic, no AI involved.
DEFAULT_ATTRIBUTION_GRACE_SECONDS = 72 * 3600
DEFAULT_SOURCE_STALE_SECONDS = 48 * 3600


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_schedules() -> dict:
    return load_json(SCHEDULES_FILE, {"frequencies": {}})["frequencies"]


def load_triggers() -> list[dict]:
    return load_json(TRIGGERS_FILE, {"triggers": []})["triggers"]


def load_scheduler_state() -> dict:
    return load_json(SCHEDULER_STATE_FILE, {
        "last_run_at": None,
        "last_frequency_run": {},
        "last_trigger_check_at": None,
        "run_history": [],
        "_snapshot": {},
    })


def load_pending_jobs() -> list[dict]:
    return load_json(PENDING_JOBS_FILE, [])


def _already_queued(pending: list[dict], job_key: str) -> bool:
    return any(j.get("job_key") == job_key and j.get("status") == "queued" for j in pending)


def enqueue(pending: list[dict], job_key: str, kind: str, requires_ai_reasoning: bool, context_hint: str) -> dict | None:
    if _already_queued(pending, job_key):
        return None
    job = {
        "id": f"JOB-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        "job_key": job_key,
        "kind": kind,
        "requires_ai_reasoning": requires_ai_reasoning,
        "context_hint": context_hint,
        "queued_at": now_iso(),
        "status": "queued",
    }
    pending.append(job)
    return job


def due_frequencies(schedules: dict, state: dict, now: datetime) -> list[str]:
    due = []
    last_run = state.get("last_frequency_run", {})
    for name, cfg in schedules.items():
        last = last_run.get(name)
        interval = int(cfg.get("interval_minutes", 0))
        if interval <= 0:
            continue
        if last is None:
            due.append(name)
            continue
        last_dt = datetime.fromisoformat(last)
        if (now - last_dt).total_seconds() >= interval * 60:
            due.append(name)
    return due


def _count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as f:
        return sum(1 for _ in f) - 1  # minus header


def _count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return len(list(path.glob("*")))


def _load_json_files(dir_path: Path) -> list[dict]:
    if not dir_path.exists():
        return []
    out = []
    for p in sorted(dir_path.glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def check_deterministic_triggers(triggers: list[dict], state: dict) -> list[dict]:
    """Evaluate every trigger in config/triggers.json that has a real
    deterministic check implemented here; unimplemented ones (data feeds not
    yet built, statistical-baseline interpretation, etc.) are skipped, never
    fabricated as firing. All checks below read only repository state
    (ledger, state/, approvals/, execution/, experiments/) -- no AI call.
    Idempotency is enforced via `state['_snapshot']`, which persists to disk
    every run, so the same underlying fact never re-fires on the next tick.
    """
    fired = []
    snapshot = state.get("_snapshot", {})
    new_snapshot = dict(snapshot)
    now = datetime.now(timezone.utc)

    # -- new_revenue_detected: fires only on cash events that actually
    # reached LEDGER_POSTED (i.e. real, human-verified, reconciled revenue
    # posted to the ledger) -- NOT on raw ledger row growth (which includes
    # expenses/fees/adjustments) and NOT on unverified OBSERVED events.
    posted_events = bi.list_external_cash_events(state="LEDGER_POSTED")
    posted_ids = {e["id"] for e in posted_events}
    is_first_run = "known_posted_event_ids" not in snapshot
    known_posted_ids = set(snapshot.get("known_posted_event_ids", []))
    new_posted_ids = posted_ids - known_posted_ids
    if new_posted_ids and not is_first_run:  # skip fabricated firing on first-ever run
        fired.append({"trigger_id": "new_revenue_detected", "detail": f"{len(new_posted_ids)} newly LEDGER_POSTED cash event(s): {sorted(new_posted_ids)}"})
    new_snapshot["known_posted_event_ids"] = sorted(posted_ids)

    completed_count = _count_files(HR_COMPLETED_DIR)
    if snapshot.get("completed_execution_requests") is not None and completed_count > snapshot["completed_execution_requests"]:
        fired.append({"trigger_id": "human_execution_confirmation_received", "detail": f"{completed_count - snapshot['completed_execution_requests']} new confirmation(s)"})
    new_snapshot["completed_execution_requests"] = completed_count

    approvals_count = _count_files(APPROVALS_PENDING_DIR)
    if snapshot.get("pending_approvals") is not None and approvals_count > snapshot["pending_approvals"]:
        fired.append({"trigger_id": "critical_decision_generated", "detail": f"{approvals_count - snapshot['pending_approvals']} new pending approval(s)"})
    new_snapshot["pending_approvals"] = approvals_count

    # -- new_business_signal_detected
    signal_files = sorted(p.name for p in BUSINESS_SIGNALS_DIR.glob("*.json")) if BUSINESS_SIGNALS_DIR.exists() else []
    signals_first_run = "known_signal_files" not in snapshot
    known_signal_files = set(snapshot.get("known_signal_files", []))
    new_signal_files = [f for f in signal_files if f not in known_signal_files]
    if new_signal_files and not signals_first_run:
        fired.append({"trigger_id": "new_business_signal_detected", "detail": f"{len(new_signal_files)} new signal file(s)"})
    new_snapshot["known_signal_files"] = signal_files

    # -- new_qualified_lead_detected: a sanitized lead payload's
    # commercial_stage/qualification field became 'qualified' since the
    # last observed value for that signal_id.
    qualified_now = set()
    for rec in _load_json_files(BUSINESS_SIGNALS_DIR):
        sig_id = rec.get("signal_id")
        if not sig_id:
            continue
        stage = rec.get("qualification") or rec.get("commercial_stage")
        if stage == "qualified":
            qualified_now.add(sig_id)
    qualified_first_run = "known_qualified_lead_ids" not in snapshot
    known_qualified = set(snapshot.get("known_qualified_lead_ids", []))
    newly_qualified = qualified_now - known_qualified
    if newly_qualified and not qualified_first_run:
        fired.append({"trigger_id": "new_qualified_lead_detected", "detail": f"{len(newly_qualified)} lead(s) newly qualified"})
    new_snapshot["known_qualified_lead_ids"] = sorted(qualified_now)

    # -- experiment_metric_threshold_reached: compare production, officially
    # eligible MetricObservations against each active experiment's declared
    # numeric success_metric/failure_criteria thresholds, if those fields
    # parse as "<metric_name> >= <number>"-style simple declarations. Kept
    # deliberately conservative: only fires on unambiguous numeric matches.
    observations = _load_json_files(METRIC_OBSERVATIONS_DIR)
    threshold_hits = []
    for exp in _load_json_files(ACTIVE_EXPERIMENTS_DIR):
        exp_id = exp.get("id") or exp.get("code")
        for field_name, direction in (("success_metric", ">="), ("kill_condition", "<=")):
            spec = exp.get(field_name)
            if not isinstance(spec, str) or ":" not in spec:
                continue
            metric_name, _, threshold_raw = spec.partition(":")
            metric_name = metric_name.strip()
            try:
                threshold = float(threshold_raw.strip())
            except ValueError:
                continue
            matches = [o for o in observations if o.get("experiment_id") == exp_id and o.get("metric_name") == metric_name and o.get("eligible_for_official_evaluation") and o.get("value") is not None]
            for obs in matches:
                value = obs["value"]
                crossed = value >= threshold if direction == ">=" else value <= threshold
                if crossed:
                    threshold_hits.append(f"{exp_id}:{metric_name}:{obs['id']}")
    known_threshold_hits = set(snapshot.get("known_threshold_hits", []))
    new_threshold_hits = [h for h in threshold_hits if h not in known_threshold_hits]
    if new_threshold_hits:
        fired.append({"trigger_id": "experiment_metric_threshold_reached", "detail": f"{len(new_threshold_hits)} threshold crossing(s): {new_threshold_hits}"})
    new_snapshot["known_threshold_hits"] = sorted(set(threshold_hits) | known_threshold_hits)

    # -- platform_signal_source_stale: no new business_signals or
    # metric_observations file for a given source_system beyond the default
    # refresh interval.
    latest_by_source: dict[str, datetime] = {}
    for rec in _load_json_files(BUSINESS_SIGNALS_DIR) + observations:
        src = rec.get("source_system") or rec.get("source")
        ts_raw = rec.get("retrieved_at")
        if not src or not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(ts_raw)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if src not in latest_by_source or ts > latest_by_source[src]:
            latest_by_source[src] = ts
    stale_sources = [src for src, ts in latest_by_source.items() if (now - ts.astimezone(timezone.utc)).total_seconds() > DEFAULT_SOURCE_STALE_SECONDS]
    known_stale_sources = set(snapshot.get("known_stale_sources", []))
    new_stale_sources = [s for s in stale_sources if s not in known_stale_sources]
    if new_stale_sources:
        fired.append({"trigger_id": "platform_signal_source_stale", "detail": f"stale source(s): {new_stale_sources}"})
    new_snapshot["known_stale_sources"] = sorted(set(stale_sources))

    # -- measurement_window_completed: now() >= activation_date +
    # measurement_window (days), computed per active experiment.
    completed_windows = []
    for exp in _load_json_files(ACTIVE_EXPERIMENTS_DIR):
        exp_id = exp.get("id") or exp.get("code")
        activated_at = exp.get("activated_at")
        window_days = exp.get("measurement_window_days") or exp.get("measurement_window")
        if not activated_at or not window_days:
            continue
        try:
            activated_dt = datetime.fromisoformat(activated_at)
            if activated_dt.tzinfo is None:
                activated_dt = activated_dt.replace(tzinfo=timezone.utc)
            window_days = float(window_days)
        except (ValueError, TypeError):
            continue
        if now >= activated_dt.astimezone(timezone.utc) + timedelta(days=window_days):
            completed_windows.append(exp_id)
    known_completed_windows = set(snapshot.get("known_completed_windows", []))
    new_completed_windows = [w for w in completed_windows if w not in known_completed_windows]
    if new_completed_windows:
        fired.append({"trigger_id": "measurement_window_completed", "detail": f"experiment(s): {new_completed_windows}"})
    new_snapshot["known_completed_windows"] = sorted(set(completed_windows) | known_completed_windows)

    # -- attribution_pending_too_long: an ExternalCashEvent stuck in
    # ATTRIBUTED/RECONCILED past the grace period without reaching
    # LEDGER_POSTED.
    stuck = bi.find_stale_cash_events(grace_period_seconds=DEFAULT_ATTRIBUTION_GRACE_SECONDS, states=("ATTRIBUTED", "RECONCILED"))
    stuck_ids = {e["id"] for e in stuck}
    known_stuck_ids = set(snapshot.get("known_stuck_attribution_ids", []))
    new_stuck_ids = stuck_ids - known_stuck_ids
    if new_stuck_ids:
        fired.append({"trigger_id": "attribution_pending_too_long", "detail": f"{len(new_stuck_ids)} event(s) stuck: {sorted(new_stuck_ids)}"})
    new_snapshot["known_stuck_attribution_ids"] = sorted(stuck_ids)

    state["_snapshot"] = new_snapshot
    return fired


def cmd_run(_args):
    schedules = load_schedules()
    triggers = load_triggers()
    state = load_scheduler_state()
    pending = load_pending_jobs()
    now = datetime.now(timezone.utc).astimezone()

    due = due_frequencies(schedules, state, now)
    queued = []
    for freq in due:
        cfg = schedules[freq]
        for job_name in cfg.get("jobs", []):
            job = enqueue(
                pending, job_key=f"{freq}:{job_name}", kind="scheduled",
                requires_ai_reasoning=bool(cfg.get("requires_ai_reasoning", True)),
                context_hint=f"Scheduled '{freq}' job '{job_name}' is due.",
            )
            if job:
                queued.append(job)
        state.setdefault("last_frequency_run", {})[freq] = now_iso()

    triggers_by_id = {t["id"]: t for t in triggers}
    fired = check_deterministic_triggers(triggers, state)
    for f in fired:
        trigger_def = triggers_by_id.get(f["trigger_id"], {})
        # Respect requires_ai_reasoning as declared in config/triggers.json:
        # a trigger marked requires_ai_reasoning=false is fully resolved by
        # this deterministic check and must NOT be routed to an AI-reasoning
        # job; a trigger marked true always produces a cognitive/AI-routed
        # job. Never silently override either direction. NOTE: no trigger
        # here -- regardless of requires_ai_reasoning -- may itself flip an
        # experiment's lifecycle_state to ACTIVE; only a human-facing entry
        # point calling business_integration.apply_experiment_lifecycle_transition
        # with human_authorized=True can do that (see AutoActivationBlockedError).
        requires_ai = bool(trigger_def.get("requires_ai_reasoning", True))
        job = enqueue(
            pending, job_key=f"trigger:{f['trigger_id']}:{now_iso()}",
            kind="trigger" if requires_ai else "trigger_deterministic",
            requires_ai_reasoning=requires_ai,
            context_hint=f"Trigger '{f['trigger_id']}' fired: {f['detail']}",
        )
        if job:
            queued.append(job)

    state["last_run_at"] = now_iso()
    state["last_trigger_check_at"] = now_iso()
    state.setdefault("run_history", []).append({
        "at": now_iso(), "due_frequencies": due, "fired_triggers": [f["trigger_id"] for f in fired],
        "jobs_queued": [j["id"] for j in queued],
    })
    state["run_history"] = state["run_history"][-50:]

    save_json(SCHEDULER_STATE_FILE, state)
    save_json(PENDING_JOBS_FILE, pending)
    print(json.dumps({"due_frequencies": due, "fired_triggers": fired, "jobs_queued": queued}, indent=2))


def cmd_status(_args):
    print(json.dumps(load_scheduler_state(), indent=2))


def cmd_pending_jobs(_args):
    print(json.dumps(load_pending_jobs(), indent=2))


def cmd_complete_job(args):
    pending = load_pending_jobs()
    remaining = []
    completed = None
    for j in pending:
        if j["id"] == args.id and j.get("status") == "queued":
            j["status"] = "completed"
            j["completed_at"] = now_iso()
            j["result_summary"] = args.summary
            completed = j
        else:
            remaining.append(j)
    if completed is None:
        raise SystemExit(f"no queued job with id {args.id}")
    save_json(PENDING_JOBS_FILE, remaining)
    print(json.dumps(completed, indent=2))


def build_parser():
    p = argparse.ArgumentParser(description="Capital Agent scheduler/orchestrator")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="Check due schedules and deterministic triggers, enqueue jobs. No AI call.")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("status")
    s.set_defaults(func=cmd_status)

    pj = sub.add_parser("pending-jobs")
    pj.set_defaults(func=cmd_pending_jobs)

    cj = sub.add_parser("complete-job")
    cj.add_argument("--id", required=True)
    cj.add_argument("--summary", required=True)
    cj.set_defaults(func=cmd_complete_job)

    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

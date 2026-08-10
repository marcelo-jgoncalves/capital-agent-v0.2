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
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEDULES_FILE = ROOT / "config" / "schedules.json"
TRIGGERS_FILE = ROOT / "config" / "triggers.json"
STATE_DIR = ROOT / "state"
SCHEDULER_STATE_FILE = STATE_DIR / "scheduler_state.json"
PENDING_JOBS_FILE = STATE_DIR / "pending_jobs.json"
LEDGER_FILE = ROOT / "data" / "ledger.csv"
APPROVALS_PENDING_DIR = ROOT / "approvals" / "pending"
HR_COMPLETED_DIR = ROOT / "execution" / "human_requests" / "completed"


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


def check_deterministic_triggers(triggers: list[dict], state: dict) -> list[dict]:
    """Only fires the triggers that have a real deterministic check implemented
    here today; the rest are declared in config/triggers.json but require
    capability (data feeds, consistency audits) not yet built. Never fabricate
    a firing for an unimplemented trigger."""
    fired = []
    snapshot = state.get("_snapshot", {})
    new_snapshot = dict(snapshot)

    ledger_rows = _count_rows(LEDGER_FILE)
    if snapshot.get("ledger_rows") is not None and ledger_rows > snapshot["ledger_rows"]:
        fired.append({"trigger_id": "new_revenue_detected", "detail": f"ledger grew by {ledger_rows - snapshot['ledger_rows']} row(s)"})
    new_snapshot["ledger_rows"] = ledger_rows

    completed_count = _count_files(HR_COMPLETED_DIR)
    if snapshot.get("completed_execution_requests") is not None and completed_count > snapshot["completed_execution_requests"]:
        fired.append({"trigger_id": "human_execution_confirmation_received", "detail": f"{completed_count - snapshot['completed_execution_requests']} new confirmation(s)"})
    new_snapshot["completed_execution_requests"] = completed_count

    approvals_count = _count_files(APPROVALS_PENDING_DIR)
    if snapshot.get("pending_approvals") is not None and approvals_count > snapshot["pending_approvals"]:
        fired.append({"trigger_id": "critical_decision_generated", "detail": f"{approvals_count - snapshot['pending_approvals']} new pending approval(s)"})
    new_snapshot["pending_approvals"] = approvals_count

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

    fired = check_deterministic_triggers(triggers, state)
    for f in fired:
        job = enqueue(
            pending, job_key=f"trigger:{f['trigger_id']}:{now_iso()}", kind="trigger",
            requires_ai_reasoning=True, context_hint=f"Trigger '{f['trigger_id']}' fired: {f['detail']}",
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

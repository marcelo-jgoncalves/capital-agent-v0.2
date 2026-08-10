# Scheduler / Orchestration

The Capital Agent does not depend on a human manually starting an AI session
every day. This is the component that decides, on its own, whether there is
real work due — see `ARCHITECTURE.md` "Scheduler and orchestration" for the
diagram and rationale.

Implementation: `src/scheduler.py` (not a `scheduler/` module by design — kept
next to `src/capital_agent.py` since both are the same small Python CLI
toolkit; this directory holds the operating documentation and configuration
that describe it, per `config/schedules.json` and `config/triggers.json`).

## How to run it

Invoke periodically from any external scheduler (cron, Windows Task
Scheduler, a CI schedule) — the script itself is stateless per-call and reads
its state from `state/`:

```text
python src/scheduler.py run
```

This performs deterministic checks only — no AI/model call happens inside
this script. It:

1. Compares `state/scheduler_state.json` against `config/schedules.json` to
   find which frequency buckets (`frequent`/`daily`/`weekly`/`monthly`/
   `quarterly`) are due.
2. Runs the deterministic checks in `config/triggers.json` that are actually
   implemented today (ledger growth, new completed Human Execution Requests,
   new pending critical-decision approvals) — see
   `check_deterministic_triggers` in `src/scheduler.py`. Triggers without an
   implemented check yet (e.g. `material_market_event_detected`, which needs
   a read-only market data feed that does not exist yet) are declared in
   config but never fabricated as "fired."
3. Enqueues a job ticket per due schedule item / fired trigger into
   `state/pending_jobs.json`, deduplicated against jobs already queued.
4. Records the run in `state/scheduler_state.json`.

```text
python src/scheduler.py status          # scheduler_state.json
python src/scheduler.py pending-jobs    # pending_jobs.json
python src/scheduler.py complete-job --id JOB-... --summary "..."
```

## Who does the actual reasoning

A queued job with `requires_ai_reasoning: true` is a ticket, not a
computation. An AI operator — whichever is configured via
`adapters/ai_providers/` — later dequeues it, does the actual research,
analysis, decision-making or review, and calls `complete-job` when done. A job
with `requires_ai_reasoning: false` (a pure data-collection or health-check
job) can, in principle, be handled by a deterministic script alone; today
those tickets still surface for an operator to run, since no automated data
pipeline exists yet.

## Deterministic-first principle

Do not call an AI to check twenty prices. Check them with a script; only
invoke an AI once a deterministic check shows there is something worth
reasoning about. This keeps the system cheaper, more reliable, faster and more
auditable than dispatching to an AI on a fixed timer regardless of whether
anything happened.

## Config files

- `config/schedules.json` — frequency buckets and the jobs due at each.
- `config/triggers.json` — event-driven triggers and, for each, the
  deterministic check that would detect it (or a note that the check is not
  yet implemented — never fabricate a firing for those).

## State files

- `state/scheduler_state.json` — last run timestamps per frequency, last
  trigger-check snapshot, and a bounded run history (last 50 runs).
- `state/pending_jobs.json` — the job queue. An AI operator reads this to know
  what to work on next; `complete-job` removes a job once it is actually done.

Both are plain JSON, safe to inspect or reset by hand if they ever drift, and
neither is used to gate financial execution — that is `execution/`'s job, not
the scheduler's.

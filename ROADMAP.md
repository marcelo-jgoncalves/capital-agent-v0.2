# Roadmap

This roadmap is independent of any particular AI provider or CLI. No phase
grants the system autonomous write authority over real money — see the
custody invariant in `AI_OPERATING_MANUAL.md` and `ARCHITECTURE.md`. Phases
describe how much of the analysis/recommendation/human-execution loop is
wired up, not financial authority.

## Phase 0 — Foundation (now)

- [x] Create mandate and hard policy.
- [x] Create initialized BRL 1,000 ledger.
- [x] Create human-gate policy.
- [x] Create decision journal format.
- [x] Create experiment registry.
- [x] Create local CLI.
- [x] Create unit tests.
- [x] Create vendor-neutral AI operating manual.
- [x] Create explicit self-improvement governance.
- [x] Create system-change journal.
- [x] Initialize version control on the operating machine.
- [x] Create Context Management System (`START_HERE.md`, `CONTEXT_MANAGEMENT.md`, `context/`).
- [x] Formalize the custody invariant and the Human Execution Request lifecycle (`execution/`).
- [x] Create scheduler/orchestration scaffolding (`scheduler/`, `src/scheduler.py`, `config/schedules.json`, `config/triggers.json`, `state/`).
- [x] Create the AI Provider Adapter abstraction (`adapters/ai_providers/`).
- [ ] Configure the chosen AI execution environment as an AI Provider Adapter.
- [ ] Run Phase 0 readiness audit with the chosen AI.
- [ ] Run first opportunity research cycle.

Exit criterion:
The AI can inspect state, improve the system within allowed classes, create proposals
and produce auditable decisions and Human Execution Requests without moving real money.

## Phase 1 — Data and shadow portfolio

- Connect reliable read-only market/macro data.
- Add current low-risk BRL benchmark.
- Build quote cache with timestamps/source provenance.
- Add candidate scoring.
- Add paper portfolio.
- Add commercial-experiment scoring.
- Add periodic system-quality review.
- Put the scheduler (`src/scheduler.py`) on an actual external cadence (cron,
  Task Scheduler, or equivalent) instead of manual invocation.

Exit criterion:
At least one complete decision cycle from discovery to shadow measurement, one
validated self-improvement cycle, and the scheduler running unattended for at
least one full weekly cycle producing correctly queued jobs.

## Phase 2 — First human-executed experiment

Choose the highest-evidence opportunity found in Phase 1. Its form is deliberately
not predetermined: listed asset, crypto, paid product validation, domain/hosting,
resale, small software/API experiment or another legal bounded-loss opportunity.

The Capital Agent researches, decides, sizes, and — when it decides money
should move — creates a Human Execution Request (`execution/human_requests/`).
The human owner executes it on their own platform with their own credentials
and confirms the result; only that confirmation updates the ledger. The
requested amount must comply with active policy.

Exit criterion:
One real experiment has been funded via a Human Execution Request, executed by
the human, confirmed, measured and reconciled.

## Phase 3 — Read-only reconciliation and broader autonomous operation

- Add read-only financial data adapter(s) (`ARCHITECTURE.md` "Financial data
  adapters") for balance/position/statement/order-history reconciliation
  against what the human reports — read-only credentials only, with no
  architectural path to write access.
- Broaden event-driven triggers (`config/triggers.json`) as real data feeds
  make more of them checkable.
- Deepen self-improvement: better scoring, better context retrieval, more
  observability, lower cost per cycle.
- Kill switch for the scheduler itself (stop enqueuing new jobs on operator
  command) — note this pauses analysis dispatch, not financial execution,
  which was never autonomous to begin with.

Exit criterion:
The system reconciles its own ledger against a read-only external source with
no manual data entry, and scheduled/event-driven jobs run unattended across a
full month without a human needing to manually start a session.

There is no future phase, in this architecture, in which the system gains
autonomous write authority over real money. A proposal to introduce one would
not be a normal phase transition — it is a critical governance decision under
`CRITICAL_DECISIONS.md`, requiring explicit human authorization, and would
still be subject to `HUMAN_GATES.md`.

## Phase 4 — Capital allocation and continuous improvement

- Compare heterogeneous opportunities on expected return, downside, capital lock-up,
  evidence quality and feedback speed.
- Scale winners and shut down weak strategies — via Human Execution Requests,
  same as any other money movement.
- Maintain opportunity-cost benchmark.
- Produce periodic capital report.
- Use the system-improvement loop to refine workflows, models, tests and architecture.
- Periodically test portability by having a different capable AI reconstruct current
  state from repository artifacts only, starting from `START_HERE.md`.

## Milestones

1. BRL 1,000 -> BRL 1,100
2. BRL 1,000 -> BRL 2,000
3. BRL 2,000 -> BRL 5,000
4. BRL 5,000 -> BRL 10,000

Milestones are measurement points, not deadlines.

## Cross-cutting systems

Required across all phases: Context Management System; Evaluation & Critic System; Critical Decision Approval System; System Evolution/self-improvement loop; the Human Execution Request lifecycle; scheduler/orchestration; and AI/model portability. Before meaningful human-executed deployment, critic review and criticality classification must be tested, approval requests must persist, and execution requests must reject unapproved critical actions and never self-mark as completed.

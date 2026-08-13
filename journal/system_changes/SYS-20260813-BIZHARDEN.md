# System Change: Business integration hardening (crash-safe persistence, chargeback fix, triggers wiring)

- Date/time: 2026-08-13T19:58:00-03:00
- Change ID: SYS-20260813-BIZHARDEN
- Change class: B (materially changes cash-event state handling, ledger
  idempotency, and scheduler trigger wiring; does not grant any new
  financial-write authority and strengthens, not weakens, custody/PII
  controls)
- Status: PROPOSED_AUTONOMOUSLY_ALLOWED

## Problem observed

A human reviewer re-audited the first-pass Editorial Platform integration
foundations (`SYS-20260813-PLATFORM`'s successor work, merged as PR #4 /
commit `f16f910`, implemented in `src/business_integration.py`) and found 17
concrete gaps: `ExternalCashEvent` transitions were computed but not
persisted; ledger idempotency had no crash-safe guard; `chargeback` was
mapped to the same ledger sign as `refund` (double-counting reversed
revenue as new income); the CLI hadn't been migrated to the canonical
experiment schema; the 7 new business triggers in `config/triggers.json`
were declared but never wired to real state; `new_revenue_detected` could
fire on unverified events; `requires_ai_reasoning` was hardcoded; the PII
firewall only checked field names, not values; `BusinessObservation` and
`BUSINESS_SIGNAL` were conflated; JSON Schemas existed but weren't validated
at runtime; metric temporal semantics didn't enforce `observed_at <=
retrieved_at`; and canonical docs didn't reflect any of this.

## Evidence

Full read of `src/business_integration.py`, `src/capital_agent.py`,
`src/scheduler.py`, `tests/test_business_integration.py`,
`EXTERNAL_INTEGRATION.md`, `backlog/platform-integration.md`, and the 5
schemas under `schemas/`, prior to making changes. All 17 reviewer-flagged
items were verified against actual code (not taken on faith) before being
fixed; item 15 (historical migration) was found not to be an actual bug —
the on-disk shape hadn't changed — and a defensive migration helper was
added anyway. Full detail, including per-failure-mode test evidence and a
trigger-by-trigger status table, is in
`journal/reviews/business-integration-hardening-audit.md`.

`python -m unittest discover -s tests -v`: **181/181 passing** (139
pre-existing + 42 new: 33 in `tests/test_business_integration.py`, 9 in new
`tests/test_scheduler_triggers.py`).

## New risks introduced

- None to financial authority or custody — this pass only adds guards
  (atomic persistence, crash-safe idempotency, PII value hardening,
  `AutoActivationBlockedError`). No new financial-write path was created.
- A follow-up human reviewer subsequently found this pass, while correct as
  far as it went, left a real ledger-authority bypass open in
  `cmd_record()` (it still allowed `revenue`/`refund`/`chargeback`/
  `other_external_inflow`/`expense`/`fee`/`tax`/`capital_in`/`adjustment` to
  post directly, bypassing the `ExternalCashEvent`/Human Execution Request
  flow this pass built) plus several other real P0/P1 gaps. See
  `SYS-20260813-LEDGERINTEGRITY` for the follow-up fix — this record should
  not be read as a final closeout of ledger-authority correctness on its
  own.

## Files affected

Modified: `src/business_integration.py`, `src/capital_agent.py`,
`src/scheduler.py`, `schemas/metric_observation.schema.json`,
`EXTERNAL_INTEGRATION.md`, `backlog/platform-integration.md`,
`tests/test_business_integration.py`.

Created: `tests/test_scheduler_triggers.py`,
`journal/reviews/business-integration-hardening-audit.md`,
`journal/system_changes/SYS-20260813-BIZHARDEN.md` (this file, added
retroactively during a context-management pass — see Outcome).

## Expected benefit

Closes 17 concrete correctness/safety gaps in the first business-
integration pass so `ExternalCashEvent` handling, ledger idempotency, PII
protection, and scheduler triggers behave as documented rather than only
as declared.

## Rollback

Revert commit `43081f2` (merged via PR #5, `f2a3072`). No financial-write
capability was introduced, so rollback carries no custody risk; it would
reopen the 17 fixed gaps.

## Validation / tests performed

`python -m unittest discover -s tests -v` — 181 tests, 0 failures, 0
errors, including explicit crash-mid-write, retry-after-crash, stale-state,
duplicate-submission, and concurrent-access tests (see audit report for the
exact test names and scenarios).

## Outcome

Implemented and merged (PR #5, commit `f2a3072`). This record was written
retroactively during a routine context-management pass after it was
discovered the merge had no corresponding `journal/system_changes/` entry
or index entry, even though its own audit report
(`journal/reviews/business-integration-hardening-audit.md`) existed —
per `CONTEXT_MANAGEMENT.md`, a system change is not fully classified/
persisted/indexed until it has both. No human approval required (Class B,
no financial-authority or risk-limit change). Superseded in part by
`SYS-20260813-LEDGERINTEGRITY`, which closed a `cmd_record` bypass this
pass did not address.

## Human approval reference

None required (Class B; no financial authority or risk-limit change).

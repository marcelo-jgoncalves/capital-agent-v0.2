# System Change: Close ledger bypass in cmd_record, harden cash-event/ledger idempotency, fix experiment/metric schema gaps

- Date/time: 2026-08-13T19:58:38-03:00
- Change ID: SYS-20260813-LEDGERINTEGRITY
- Change class: B (closes a real financial-integrity gap and tightens
  several enforcement paths; does not grant any new financial-write
  authority — it removes an unintended one)
- Status: PROPOSED_AUTONOMOUSLY_ALLOWED

## Problem observed

A human reviewer re-audited `SYS-20260813-BIZHARDEN` (merged as PR #5,
`f2a3072`) against the actual code and found the hardening pass, while
correct as far as it went, left several real gaps open, most seriously:
`cmd_record` still let an operator post `capital_in`, `revenue`, `refund`,
`expense`, `fee`, `tax`, `adjustment`, `chargeback`, and
`other_external_inflow` directly to the ledger — bypassing both the
`ExternalCashEvent` VERIFIED/RECONCILED/LEDGER_POSTED pipeline and the
Human Execution Request lifecycle that pass had just built. Also found:
`_advance_cash_event` trusted a caller-supplied in-memory state instead of
reloading the persisted record (stale-state overwrite risk); ledger
idempotency detected a matching reference but not a *conflicting* one
(same reference, different amount/type/category silently accepted as
"already posted"); the ledger-post lock had no crash recovery for an
orphaned lock file; `cmd_new_experiment` still produced a partial legacy
shape and rejected legitimate zero-capital experiments; evaluation
eligibility was computed from `retrieved_at` instead of `observed_at`,
allowing backfilled pre-activation data to count as post-activation
evidence; schema validation silently no-opped when a schema file was
missing; and `README.md`/`START_HERE.md`/`ARCHITECTURE.md` still described
the pre-`ExternalCashEvent` ledger-authority model, contradicting
`EXTERNAL_INTEGRATION.md`.

## Evidence

Full read of `src/business_integration.py`, `src/capital_agent.py`
(`cmd_record`, `cmd_new_experiment`, `append_ledger`,
`policy_check_proposal`), `src/scheduler.py`, `EXTERNAL_INTEGRATION.md`,
`README.md`, `START_HERE.md`, `ARCHITECTURE.md`, and the schemas under
`schemas/`, before making changes. Every reviewer-flagged item was
confirmed against actual code first (none turned out to be a false
positive). Full detail is in
`journal/reviews/ledger-integrity-and-doc-consistency-audit.md`.

`python -m unittest discover -s tests -v`: **200/200 passing** (185
pre-existing carried forward, some updated to reflect corrected behavior,
plus 15 net new tests across `tests/test_business_integration.py`,
`tests/test_custody_and_execution.py`, `tests/test_capital_agent.py`).

## New risks introduced

- None to financial authority — this pass only removes an unintended
  bypass and adds guards (`StaleCashEventStateError`,
  `LedgerReferenceConflictError`, crash-recoverable lock,
  `AutoActivationBlockedError` untouched and still in force).
- The new `capital_in`/`adjustment` administrative path
  (`--admin-confirm` + `--reason`, audited to
  `journal/admin_ledger_actions/`) is a genuinely new code path, even
  though narrower than what it replaces. It follows the existing
  interactive-session `--human-statement` authentication convention
  (`CRITICAL_DECISIONS.md`) but its exact shape has not received explicit
  owner sign-off — flagged in the audit report and here for visibility.
- The `BusinessSignal`/`BusinessObservation` naming split was only
  partially resolved: `ingest_business_signal()`'s existing output shape
  was kept (schema tightened, not renamed) and
  `create_business_signal_entity()`'s different shape got its own new
  schema (`schemas/business_signal_pattern.schema.json`) rather than a
  full unification. Worth a second look to confirm this is the intended
  long-term shape.

## Files affected

Modified: `src/business_integration.py`, `src/capital_agent.py`,
`src/scheduler.py`, `README.md`, `START_HERE.md`, `ARCHITECTURE.md`,
`tests/test_business_integration.py`, `tests/test_capital_agent.py`,
`tests/test_custody_and_execution.py`.

Created: `schemas/experiment.schema.json`,
`schemas/business_observation.schema.json`,
`schemas/business_signal_pattern.schema.json`,
`journal/reviews/ledger-integrity-and-doc-consistency-audit.md`,
`journal/system_changes/SYS-20260813-LEDGERINTEGRITY.md` (this file, added
retroactively during a context-management pass — see Outcome).

## Expected benefit

Closes the most serious remaining financial-integrity gap in the business-
integration work (`cmd_record` bypass) plus six other real P0/P1 gaps, and
resolves a load-bearing documentation contradiction in `START_HERE.md` —
the file a new AI session uses to reconstruct the system's actual rules.

## Rollback

Revert commit `a860326` (merged via PR #6, `614f2f1`). This would reopen
the `cmd_record` bypass and the other five fixed gaps, so rollback is not
recommended without a compensating control in place first.

## Validation / tests performed

`python -m unittest discover -s tests -v` — 200 tests, 0 failures, 0
errors. Explicit confirmation that `cmd_record` can no longer be used to
bypass `ExternalCashEvent`/Human Execution Request for
revenue/refund/chargeback/other_external_inflow/expense/fee/tax (see audit
report for exact test names).

## Outcome

Implemented and merged (PR #6, commit `614f2f1`). This record was written
retroactively during a routine context-management pass after it was
discovered the merge had no corresponding `journal/system_changes/` entry
or index entry, even though its own audit report existed — per
`CONTEXT_MANAGEMENT.md`, a system change is not fully classified/
persisted/indexed until it has both. Two items remain explicitly flagged
for owner review rather than treated as closed: the `capital_in`/
`adjustment` admin-confirm mechanism, and the `BusinessSignal`/
`BusinessObservation` naming split. No human approval was sought before
merge (Class B, no financial-authority *expansion* — the change is a
strict tightening); the two flagged items above are recommended for
explicit owner sign-off going forward, per `HUMAN_GATES.md`.

## Human approval reference

None sought before merge (Class B, net-restrictive change). Two follow-up
items flagged for owner review: (1) `capital_in`/`adjustment`
admin-confirm mechanism shape, (2) `BusinessSignal`/`BusinessObservation`
naming split.

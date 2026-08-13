# Ledger Integrity and Doc Consistency Audit — 2026-08-13

Branch: `fix/ledger-integrity-and-doc-consistency`. A human reviewer re-audited
the `fix/business-integration-hardening` merge (PR #5, `f2a3072`) and found
several real, specific remaining gaps. This pass fixes them.

Full suite: **200/200 tests pass** (185 pre-existing carried forward + updated
+ 15 net new across `tests/test_business_integration.py`,
`tests/test_custody_and_execution.py`, `tests/test_capital_agent.py`).

## P0 — `cmd_record` ledger bypass closed

`src/capital_agent.py cmd_record` previously blocked only `buy`/`sell`/
`capital_out`. Every other type (`capital_in`, `revenue`, `refund`, `expense`,
`fee`, `tax`, `adjustment`, `chargeback`, `other_external_inflow`) went
straight to `append_ledger()`, bypassing both the Human Execution Request
lifecycle and the `ExternalCashEvent` state machine. Fixed by splitting the
allowed types into four buckets, each refused unless its specific gate is
satisfied:

- `revenue`/`refund`/`chargeback`/`other_external_inflow` — refused outright;
  operator is pointed at the `ExternalCashEvent` pipeline
  (`observe_external_cash_event` -> ... -> `post_external_cash_event_to_ledger`).
- `expense`/`fee`/`tax` — refused unless `--execution-id <id>` names a request
  actually present in `execution/human_requests/completed/`.
- `capital_in`/`adjustment` — refused unless both `--admin-confirm` and a
  non-empty `--reason` are supplied. On success, a JSON audit record is
  written to `journal/admin_ledger_actions/<id>.json` (timestamp, type,
  amount, reason) and the reason is also appended into the ledger row's
  description. This is the narrowest reasonable escape hatch for genuine
  bookkeeping (e.g. initial funding) — **flagged for owner sign-off**: the
  exact authentication/audit shape of this administrative path is a
  product/policy call; this implementation follows the existing
  interactive-session `--human-statement` convention
  (`CRITICAL_DECISIONS.md` "Approval authentication") but a stronger
  mechanism (e.g. requiring a linked `journal/decisions/` record) may be
  warranted later.

New tests in `tests/test_custody_and_execution.py`:
`test_record_refuses_direct_cash_event_kinds`,
`test_record_expense_requires_completed_execution_id`,
`test_record_expense_with_completed_execution_id_succeeds`,
`test_record_admin_types_refused_without_confirm_and_reason`,
`test_record_admin_types_succeed_with_confirm_and_reason_and_leave_audit`.
The pre-existing `test_record_still_allows_non_execution_bookkeeping` test
relied on the closed bypass (posting `expense` with no execution reference);
it was replaced with `test_record_expense_requires_completed_execution_id` /
`test_record_expense_with_completed_execution_id_succeeds` reflecting the
corrected behavior.

## P0 — Stale in-memory state overwrite in `_advance_cash_event`

`_advance_cash_event` read `event["state"]` from whatever in-memory dict the
caller passed in, never reloading the canonical persisted record. A caller
holding a stale copy could apply a transition on top of out-of-date state.
Fixed: `_advance_cash_event` now reloads the persisted record from
`state/external_cash_events/<id>.json` (when the event has an `id`), and
requires the caller's `event["state"]` to match the persisted state exactly
before proceeding (optimistic concurrency check). A mismatch raises the new
`StaleCashEventStateError`. All existing call sites
(`report_/verify_/attribute_/reconcile_/post_..._to_ledger`) pass through
unchanged since they all forward the caller's `event` dict as before.

New tests: `test_stale_in_memory_transition_is_rejected`,
`test_fresh_reload_can_proceed_after_stale_rejection`.

## P0/P1 — Ledger idempotency conflicting-duplicate detection

`_ledger_reference_posted` only checked for key *presence*. A row with the
same reference but a different `type`/`amount`/`category` would be silently
treated as "already posted." Fixed: added `_find_ledger_row_by_reference`
(returns the full row) and `_assert_ledger_reference_matches`, called from
`post_external_cash_event_to_ledger` before the idempotent-skip check; a
mismatch raises the new `LedgerReferenceConflictError` instead of silently
proceeding.

New tests: `test_conflicting_duplicate_reference_raises`,
`test_matching_existing_reference_is_still_treated_as_idempotent_no_op`.

## P1 — Ledger post lock crash recovery

The `O_CREAT|O_EXCL` lock in `post_external_cash_event_to_ledger` was only
released in a `finally` block; a process killed after acquiring the lock but
before releasing it left an orphaned lock forever. Fixed
(`_acquire_ledger_post_lock`): the lock file now carries owner PID + creation
timestamp; a lock older than `STALE_LOCK_MAX_AGE_SECONDS` (5 minutes,
conservative — a ledger-post critical section is a handful of local
filesystem ops) whose owning PID is not running (best-effort `os.kill(pid,
0)`; on platforms/permissions where liveness can't be determined, age alone
decides — an explicit tradeoff toward eventual recoverability) is taken over
via an atomic rename (`os.replace()` of a freshly-written temp file onto the
stale lock path), never unlink-then-recreate.

New tests: `test_orphaned_stale_lock_is_recovered`,
`test_fresh_lock_is_not_broken`.

## P1 — Experiment schema migration completed

`cmd_new_experiment` now populates `capital_budget_brl`, `resource_budget`,
and `non_financial_risks` from creation time (matching the canonical shape on
EXP-001, `experiments/active/EXP-20260813-62C22E.json`), and validates the
record against a new `schemas/experiment.schema.json` before writing it
(`_validate_experiment_schema`, wired through
`business_integration.validate_against_schema` — the same runtime-validation
path used by every other entity).

`policy_check_proposal(amount=0)` previously rejected zero as if it were
missing/invalid input ("amount must be greater than zero"). Fixed to treat
`amount is None` and `amount < 0` as invalid, and `amount == 0` as valid with
no further checks (zero can never breach a percentage cap or reserve floor).

New tests: `test_new_experiment_produces_full_canonical_shape`,
`test_zero_capital_experiment_creation_succeeds`,
`test_policy_accepts_zero_capital_proposal`, `test_policy_rejects_negative_amount`.

## P1 — Metric temporal semantics for evaluation eligibility

`filter_official_evaluation_observations` used `retrieved_at` instead of
`observed_at` to decide eligibility, so a production data point that actually
happened before activation but was fetched/backfilled afterward would
incorrectly count as post-activation evidence. Fixed to compare
`observed_at >= activation_date`.

The scheduler's `experiment_metric_threshold_reached` trigger
(`src/scheduler.py check_deterministic_triggers`) previously filtered
candidate observations only by the `eligible_for_official_evaluation` flag
stamped at observation-creation time (`environment == 'production'` only,
with no knowledge of the experiment's `activation_date`). Fixed to recompute
eligibility per-experiment via `bi.filter_official_evaluation_observations(...,
activation_date=exp.get("activated_at"))` instead of trusting the stored flag.

New/updated tests: `test_pre_activation_observation_retrieved_post_activation_is_excluded`
(new); `test_pre_activation_metrics_excluded` was corrected to force
`observed_at` (not `retrieved_at`) into the past, since the old test's setup
no longer exercised the bug fix path once `observed_at` became the deciding
field.

## P1/P2 — Schema enforcement holes

1. `validate_against_schema` returning silently when a schema file is
   missing contradicted the documented "validation is never silently
   skipped" guarantee. Fixed to raise `SchemaValidationError` on a missing
   schema file instead.
2. `schemas/business_signal.schema.json` tightened from
   `additionalProperties: true` to `false`; the sanitized lead-lifecycle
   allowlist fields (`lead_id`, `source`, `utm_*`, etc.) were added as
   explicit optional properties so legitimate payloads still validate.
3. `schemas/business_observation.schema.json` created and wired into
   `create_business_observation()`.
4. Reconciled the two structurally-different things both informally called
   "BusinessSignal": `ingest_business_signal()`'s output continues to
   validate against `business_signal.schema.json` (unchanged, to avoid a
   wide-blast-radius rename of an already-tested/used shape); the aggregated
   pattern entity produced by `create_business_signal_entity()` now validates
   against a new, accurately-scoped `schemas/business_signal_pattern.schema.json`.
   **Flagged for owner sign-off**: this is a naming-debt workaround, not a
   full rename — the schema's description field documents that
   `ingest_business_signal()`'s output is arguably BusinessObservation-shaped
   and a future rename may be warranted, but that rename was judged too wide
   (touches ~10+ call sites/tests) to do speculatively in this pass.

New tests: `test_missing_schema_file_fails_loudly_not_silently`,
`test_business_observation_validates_against_its_own_schema`,
`test_business_signal_pattern_validates_against_its_own_schema`,
`test_business_signal_from_ingest_rejects_additional_properties`.

## P1 — Documentation contradiction on ledger authority

`README.md`, `START_HERE.md`, and `ARCHITECTURE.md` all previously stated or
implied the ledger can be touched **only** via a confirmed Human Execution
Request, contradicting `EXTERNAL_INTEGRATION.md`'s (correct) description of
the External Cash Event pipeline as a second legitimate path. Fixed all three
to describe both paths consistently, plus the narrow admin-confirm path
introduced by the P0 `cmd_record` fix above.

## Not fixed in this pass (explicitly deferred, not forgotten)

- P2 `_write_json_idempotent` scan-then-write race (no atomic-create guard).
- P2 scheduler `scheduler_state.json`/`pending_jobs.json` non-atomic combined
  write.

Both are real but lower-severity than the P0/P1 items above (narrower blast
radius: a rare double-ingest of a business signal / a rare scheduler-state
inconsistency recoverable on the next tick, vs. a real ledger-bypass or
ledger-corruption risk). Left for a follow-up pass given time budget.

## Findings that were NOT bugs (verified against current code)

None of the reviewer's P0/P1 claims were found to be inaccurate on
inspection; all were confirmed against the actual code before fixing.

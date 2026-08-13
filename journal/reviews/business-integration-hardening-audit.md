# Business Integration Hardening Audit — 2026-08-13

Branch: `fix/business-integration-hardening`. Fixes real gaps found in the
first-pass Editorial Platform integration foundations merged in
`f16f910`/`87c568c`. All 17 requested items were addressed or explicitly
found already correct (noted below). Full suite: **181/181 tests pass**
(139 pre-existing + 42 new: 33 in `tests/test_business_integration.py`, 9 in
new `tests/test_scheduler_triggers.py`).

## Invariants now enforced

1. Every `ExternalCashEvent` state transition is persisted to
   `state/external_cash_events/<id>.json` via atomic write (`_atomic_write_json`
   using a temp file + `os.replace()`), never left only in an in-memory
   return value.
2. `post_external_cash_event_to_ledger` cannot duplicate a ledger line
   across a crash: it checks the ledger file itself for the idempotency
   key before appending, in addition to the event's own state.
3. Concurrent posts of the same idempotency key are serialized by an
   `O_CREAT|O_EXCL` file lock in `state/external_cash_events/_wal/`; only
   one thread/process appends.
4. `chargeback` is a distinct ledger type (`CASH_EVENT_KIND_TO_LEDGER_TYPE`)
   that **subtracts** from cash balance; `refund`/`other_external_inflow`
   add. Chargeback can no longer be double-counted as new income.
5. `apply_experiment_lifecycle_transition(..., new_state="ACTIVE", ...)`
   raises `AutoActivationBlockedError` unless `human_authorized=True` and a
   non-empty `authorized_by` are supplied. No scheduler trigger or AI job
   can reach this path.
6. `sanitize_business_payload()` rejects (`PIIRejectedError`) any
   allowlisted field whose *value* looks like an email/phone/CPF/CNPJ, not
   just denylisted field *names*.
7. `BusinessObservation` (raw fact) and `BUSINESS_SIGNAL` (derived pattern
   claim) are separate entities; the derivation is traceable via
   `derived_from_observation_ids`.
8. `observed_at <= retrieved_at` is enforced on every `MetricObservation`;
   the field didn't exist before this pass.
9. All 5 schemas are validated at runtime via `jsonschema` (with a minimal
   stdlib fallback if that package is absent) at every ingestion/transition
   point, not just documentation.
10. `new_revenue_detected` fires only on cash events that reached
    `LEDGER_POSTED`, once per event, never on raw ledger-row growth or
    unverified `OBSERVED` events.
11. Every trigger's `requires_ai_reasoning` flag (from `config/triggers.json`)
    is now read and respected when enqueuing scheduler jobs, instead of
    being hardcoded to `True`.

## Schema changes (old -> new)

- `schemas/metric_observation.schema.json`: added required `observed_at`
  (string). Old shape had no way to express "when did the underlying event
  happen" separately from "when did we retrieve it".
- No other `.schema.json` shapes changed; `business_signal` and
  `external_cash_event` schemas were already correct, just unenforced at
  runtime (see item 10 below).

## Behavior under each failure mode

- **Crash mid-write** (`LedgerCrashSafetyTests.test_crash_after_ledger_write_before_state_persist_does_not_duplicate_on_retry`):
  `append_ledger_fn` writes the real ledger line then raises. Event stays
  `RECONCILED` on disk (state persist never happened). Retry detects the
  reference already in the ledger, does not call `append_ledger_fn` again,
  and correctly advances to `LEDGER_POSTED`. Exactly one ledger line exists.
- **Retry after crash before any ledger write**
  (`test_retry_after_crash_before_ledger_write_posts_exactly_once`): lock is
  released via `finally` even when the call raises; retry posts exactly
  once.
- **Stale state** (`DuplicateAndStaleTests.test_stale_observed_event_is_detected`,
  `find_stale_cash_events()`): an event whose most recent `state_history`
  entry is older than a grace period is flagged without mutating state.
  Wired into the `attribution_pending_too_long` scheduler trigger for
  `ATTRIBUTED`/`RECONCILED` events specifically.
- **Duplicate submission**
  (`DuplicateAndStaleTests.test_duplicate_submission_of_same_external_event_is_a_no_op`):
  `observe_external_cash_event` with the same `(source_system,
  source_record_id)` returns the existing record; exactly one file on disk.
- **Concurrent access**
  (`LedgerCrashSafetyTests.test_concurrent_posts_of_same_event_only_post_once`):
  two threads race to post the same `RECONCILED` event via the file lock;
  exactly one `append_ledger_fn` call and one matching ledger line survive.

## Trigger status (7 new + 1 fixed)

| Trigger | Status |
|---|---|
| `new_revenue_detected` | Fixed and wired: fires once per `LEDGER_POSTED` event, `requires_ai_reasoning=false` respected (routed as `trigger_deterministic`, no AI job). |
| `new_business_signal_detected` | Wired: new file in `state/business_signals/` since last tick. |
| `new_qualified_lead_detected` | Wired: a signal's `qualification`/`commercial_stage` field newly equals `"qualified"`. |
| `experiment_metric_threshold_reached` | Wired, conservative: parses `success_metric`/`kill_condition` as `"<metric_name>:<number>"` and compares against production, officially-eligible `MetricObservation`s. Real experiments don't yet populate this exact format, so it will not fire until they do -- not fabricated, genuinely gated on data shape. |
| `platform_signal_source_stale` | Wired: 48h default refresh window per `source_system`, derived from `retrieved_at` across signals + observations. |
| `measurement_window_completed` | Wired: needs `activated_at` + `measurement_window_days`/`measurement_window` on the experiment record; neither exists on EXP-001 yet (still `PLANNED`), so correctly does not fire today. |
| `attribution_pending_too_long` | Wired: uses `find_stale_cash_events`, 72h default grace period. |

Remaining declared-but-unimplemented triggers (`material_market_event_detected`,
`material_company_event_detected`, `three_similar_failures_detected`,
`policy_anomaly_detected`, `context_inconsistency_detected`,
`content_performance_anomaly`, `experiment_deadline_reached`,
`experiment_success_threshold_reached`, `experiment_failure_threshold_reached`)
remain skipped -- unchanged from before this pass, still blocked on a data
feed / statistical baseline / consistency-audit capability not yet built.

## Items found already correct (no change needed)

- Item 15 (historical compatibility): the on-disk schema for
  `ExternalCashEvent` did not actually change shape, so old records read
  fine as-is; `migrate_legacy_cash_event_record()` was added defensively
  for the case of missing optional keys, and is tested, but there was no
  actual incompatibility to migrate away from.

## Files changed

- `src/business_integration.py` — persistence, crash-safety, locking,
  chargeback mapping, PII value hardening, BusinessObservation, schema
  validation, metric temporal check, `apply_experiment_lifecycle_transition`.
- `src/capital_agent.py` — `cash_balance()` chargeback subtraction /
  `other_external_inflow` addition, `cmd_record` allowed types, `cmd_new_experiment`
  now writes `lifecycle_state`.
- `src/scheduler.py` — `check_deterministic_triggers()` rewritten to wire
  the 7 triggers against real state; `requires_ai_reasoning` now read from
  `config/triggers.json` instead of hardcoded.
- `schemas/metric_observation.schema.json` — added required `observed_at`.
- `EXTERNAL_INTEGRATION.md`, `backlog/platform-integration.md` — synced.
- `tests/test_business_integration.py` — 33 new tests added (77 total in file).
- `tests/test_scheduler_triggers.py` — new file, 9 tests.

## EXP-001 status

Confirmed still `lifecycle_state: PLANNED` in
`experiments/active/EXP-20260813-62C22E.json`; unaffected by this branch.
`AutoActivationBlockedError` and the scheduler-never-calls-activation test
provide the code-level guarantee that no trigger fired by this pass's wiring
can activate it.

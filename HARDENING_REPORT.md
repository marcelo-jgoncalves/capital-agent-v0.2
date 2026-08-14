# HARDENING_REPORT — Capital Agent v0.2 final hardening pass

Source spec: `prompt-hardening-final-capital-agent-v0.2.md`. Baseline:
`master` at commit `614f2f1` (plus `ec7f215`, already present before this
session).

**Status update (2026-08-13, post-merge):** this work was committed, opened
as PR #7 (`fix/final-hardening-integrity-idempotency`), reviewed, and
squash-merged to `master` at commit `d34ea73`. The line above ("nothing
committed") was accurate when this report was first written and is left
unedited in the body below for an accurate record of what the original
session produced; treat "Status update" here as the authoritative current
state. See `## Post-review addendum` at the end of this file for a second,
independent review (by Codex/OpenAI, requested by the responsible engineer
after merge) that found real gaps in some of the invariants this report
originally declared closed, and what was done about them.

## Resumo executivo

This pass closed the remaining integrity gaps identified after PR #6:

- **P0 (section 3):** `cmd_record` could still post `expense`/`fee`/`tax`
  ledger rows by passing `--execution-id` of an already-`completed` Human
  Execution Request, letting the same HER be "replayed" into a second,
  caller-chosen-amount ledger entry even though `confirm-execution` already
  posted the one legitimate consequence for it. Closed by moving
  `expense`/`fee`/`tax` into `RECORD_BLOCKED_TYPES` -- they now have no
  generic `record` path at all; `HER -> confirm-execution -> ledger` is the
  only route.
- **P0 (section 4):** `record-reserve-asset` idempotency on `execution_id`
  was already implemented in the working tree (same-content replay is a
  no-op, conflicting-content replay is an explicit error, reload-from-disk
  on every call) -- verified correct and covered by tests; no further code
  change needed here.
- **P1 (section 5):** `post_external_cash_event_to_ledger` now reloads the
  canonical persisted event by `event["id"]` at the very start of the call
  and uses ONLY that reloaded record for every financial fact
  (amount/kind/source_system/idempotency_key/state); the caller's in-memory
  object is used at most to identify which record to act on and, optionally,
  as an `expected_state` precondition check.
- **P1 (section 6):** found and fixed a real lexical-string timestamp bug in
  `filter_official_evaluation_observations` (`observed < activation_date` on
  raw ISO strings); rewrote it to use `_parse_iso`. Also hardened
  `src/scheduler.py due_frequencies` and two other timestamp comparisons to
  reuse the same tz-aware parsing instead of ad hoc `datetime.fromisoformat`
  + manual naive-defaulting.
- **P2 (section 9):** `_write_json_idempotent`'s scan-then-write race (two
  concurrent callers with the same idempotency_key could both pass the scan
  before either wrote) was closed with an atomic `O_CREAT|O_EXCL` claim file
  per idempotency_key -- exactly one caller wins the claim and writes; every
  other caller (concurrent or a later retry) reads back the winner's record.
- **P2 (section 10):** `scheduler_state.json` and `pending_jobs.json` used to
  be written by two independent, non-atomic `path.write_text()` calls. Fixed
  in two layers: (a) `save_json` is now atomic (temp file + `os.replace`),
  and (b) both files are now written together via `save_scheduler_snapshot`,
  which first writes one atomically-saved combined snapshot file, then
  mirrors the two legacy files from it; `load_scheduler_state`/
  `load_pending_jobs` self-heal any legacy file that disagrees with the
  snapshot before returning, so a crash between writes can never leave a
  checkpoint without its job or a job without its checkpoint after restart.
- **Product decisions (sections 7-8):** documented, not decided. See
  `backlog/ADR-001-admin-confirm-ledger-action.md`,
  `backlog/ADR-002-business-signal-naming.md`, and
  `journal/decisions/DEC-20260813-HARDENING-PRODUCT.md`. No behavior change;
  current (safest) behavior preserved in both cases.

## Mudanças por prioridade

```text
P0
- cmd_record: expense/fee/tax moved from RECORD_REQUIRES_EXECUTION_TYPES
  (which accepted --execution-id of a completed HER and posted a NEW,
  caller-chosen-amount row) into RECORD_BLOCKED_TYPES (no generic `record`
  path at all, same treatment as buy/sell/capital_out).
- record-reserve-asset: idempotency by execution_id (same content -> no-op;
  conflicting content -> explicit error; reload from disk every call).
  Verified present and correct; no code change required.

P1
- post_external_cash_event_to_ledger: reloads canonical persisted event by
  id at the top of the call and at lock-acquisition time; ignores every
  other field on the caller-supplied object; optional expected_state
  precondition check against the canonical state.
- filter_official_evaluation_observations: timezone-aware instant
  comparison via _parse_iso instead of raw ISO string comparison
  (real bug fixed: `observed_at < activation_date` on strings).
- scheduler.py due_frequencies / platform_signal_source_stale /
  measurement_window_completed: reuse business_integration._parse_iso
  (or equivalent tz-normalizing logic) instead of ad hoc parsing.

P2
- _write_json_idempotent: atomic O_CREAT|O_EXCL claim file per
  idempotency_key closes the scan-then-write race.
- save_json (scheduler.py): atomic temp-file + os.replace() write.
- save_scheduler_snapshot: single atomically-written combined snapshot
  (scheduler_state + pending_jobs) plus self-healing legacy-file mirrors on
  every load, closing the crash-between-writes divergence risk.
```

## Arquivos alterados

Código:
- `src/capital_agent.py` -- `RECORD_BLOCKED_TYPES` /
  `RECORD_REQUIRES_EXECUTION_TYPES` change (section 3); reserve-asset
  idempotency verified present.
- `src/business_integration.py` -- `post_external_cash_event_to_ledger`
  canonical-state reload (section 5); `filter_official_evaluation_observations`
  timezone-aware comparison (section 6); `_write_json_idempotent` atomic
  claim-file protection (section 9).
- `src/scheduler.py` -- `due_frequencies` and two other timestamp
  comparisons made timezone-aware via `bi._parse_iso` (section 6);
  `save_json` made atomic, `save_scheduler_snapshot` +
  `_reconcile_legacy_files_from_snapshot` added, `cmd_run`/
  `cmd_complete_job` updated to use them (section 10).

Testes:
- `tests/test_custody_and_execution.py` -- replaced the two tests that
  consecrated the old insecure expense/fee/tax `--execution-id` behavior
  with tests asserting refusal (with and without a completed execution_id),
  plus an end-to-end "completed HER cannot be replayed into a second
  posting" test; added timezone-aware `due_frequencies` tests.
- `tests/test_business_integration.py` -- added
  `TimezoneAwareEligibilityTests` (section 6) and
  `WriteJsonIdempotentRaceTests` (section 9, threaded concurrency test).
- `tests/test_scheduler_triggers.py` -- added
  `SchedulerSnapshotAtomicityTests` (section 10: crash-after-snapshot,
  crash-after-partial-mirror, retry, restart-recovery).

Docs / decisões (novos arquivos, sem alterar Editorial Platform nem
políticas canônicas):
- `backlog/ADR-001-admin-confirm-ledger-action.md`
- `backlog/ADR-002-business-signal-naming.md`
- `journal/decisions/DEC-20260813-HARDENING-PRODUCT.md`

Schemas: nenhum schema precisou mudar de forma nesta rodada (nenhuma
entidade nova foi introduzida; `OpportunityCandidate` foi deliberadamente
**não** implementado -- ver ADR-002).

Config / migrations / state: nenhuma alteração.

## Invariants protegidos

- `one HER -> at most one financial posting` (section 3 fix + end-to-end
  test `test_completed_her_cannot_be_reused_for_a_second_financial_posting`).
- `one BUY execution -> at most one reserve-asset booking` (idempotency
  verified, `ReserveAssetTests`).
- `ledger posting uses persisted canonical event` (section 5 fix,
  `ExternalCashEventTests` P1 #3 tests).
- `retry never duplicates verified financial fact` (`_write_json_idempotent`
  claim-file protection; ledger-post lock; reserve-asset idempotency).
- `stale input never overwrites canonical state` (section 5's
  `expected_state` check; pre-existing `StaleCashEventTransitionTests`).
- `scheduler restart does not lose or duplicate work`
  (`SchedulerSnapshotAtomicityTests`, deterministic `job_key` dedupe).
- `timezone representation does not change eligibility`
  (`TimezoneAwareEligibilityTests`, `due_frequencies` offset tests).

## Ledger integrity

Confirmed:
- **no HER reuse**: `expense`/`fee`/`tax` have no generic `record` path;
  `buy`/`sell`/`capital_out` were already blocked; `confirm-execution`
  remains the sole path for execution-derived ledger types.
- **no duplicate posting**: reserve-asset booking, ExternalCashEvent
  posting, and `_write_json_idempotent`-backed entities are all idempotent
  on their respective keys, verified concurrently in tests.
- **no stale financial data**: `post_external_cash_event_to_ledger` uses
  only the freshly reloaded canonical record.
- **no silent conflicts**: reserve-asset conflicting replay raises an
  explicit error rather than overwriting or duplicating; `_write_json_idempotent`'s
  claim mechanism never silently drops a losing writer's intent (it returns
  the winner's actual persisted record).

## Reserve asset integrity

- **idempotência**: same `execution_id` + same content -> no-op, prints the
  existing entry, does not append a new one (`idempotent: true` in the
  reprinted output for the true no-op path; note the CLI also prints an
  `idempotent: false` field on first-creation calls for symmetry).
- **conflict detection**: same `execution_id` + different content -> explicit
  `SystemExit`, entry count unchanged.
- **equity floor correto**: `current_equity_floor()` verified not to
  increase across repeated/duplicate booking attempts
  (`test_equity_floor_not_inflated_by_duplicate_booking_attempts`).

## Scheduler

Crash/restart behavior after this pass:
- Every JSON write in `scheduler.py` (`save_json`) is atomic
  (`temp-file + os.replace()`), so a crash mid-write can never leave a
  truncated/corrupt state file.
- `scheduler_state.json` (checkpoint) and `pending_jobs.json` (resulting job
  tickets) are persisted together via `save_scheduler_snapshot`: one
  atomically-written combined snapshot file first, then the two legacy
  files mirrored from it. A crash at any point during or after the snapshot
  write leaves the snapshot itself fully consistent; the next
  `load_scheduler_state()`/`load_pending_jobs()` call detects any legacy
  file that disagrees with the snapshot and re-derives it before returning
  -- so a restart never observes "checkpoint without job" or "job without
  checkpoint."
- As a second, independent layer, job keys are deterministic (not
  timestamp-suffixed for triggers), so even a transient legacy-file
  mismatch a caller might observe mid-transaction resolves to the existing
  `enqueue`/`_already_queued` dedupe rather than a duplicate job.
- Deterministic triggers remain the only thing that can enqueue a job or
  advance a checkpoint; nothing in this pass touches
  `apply_experiment_lifecycle_transition`'s `AutoActivationBlockedError`
  guard, which still refuses any scheduler-originated transition into
  `ACTIVE` (verified by the pre-existing `Exp001CannotAutoActivateViaSchedulerTests`,
  still passing).

## Decisões de produto

- **`admin-confirm`**: current behavior preserved (explicit flag + mandatory
  reason + standalone audit record). Recommendation recorded
  (`backlog/ADR-001-admin-confirm-ledger-action.md`): tighten the `--reason`
  wording to match the `approve-decision --human-statement` authentication
  convention now (cheap, closes a documentation/honesty gap); defer a full
  two-step "Admin Ledger Action" pipeline (generated id -> confirm ->
  one-time execution -> audit) until administrative actions are frequent
  enough to justify the added complexity. **Pending owner decision** on
  whether/when to activate either option.
- **BusinessSignal naming**: the `ExternalBusinessObservation -> BusinessSignal`
  split was already implemented correctly in a prior hardening pass
  (`create_business_observation()` / `create_business_signal_entity()`,
  with an explicit `topic_candidate` conflation guard) -- considered
  **resolved**, no rename needed. `OpportunityCandidate` does not yet exist
  as a first-class entity (only an opaque `opportunity_candidate_ref`
  string); implementing it was assessed as low-risk-to-add but speculative
  without a concrete consumer, so it is **deliberately deferred**, tracked
  as backlog item BIZNAME-001, not implemented this session. A secondary,
  lower-priority naming-collision note (`ingest_business_signal()` vs.
  `create_business_signal_entity()` sharing `BUSINESS_SIGNALS_DIR`) is filed
  as low-priority backlog rather than rushed into a wide-blast-radius rename
  under this hardening pass.

## Testes

- **Total**: 237 tests, all passing (`python -m unittest discover -s tests`).
- **Novos** (this session, on top of what was already in the working tree):
  - `tests/test_custody_and_execution.py`: `test_record_refuses_expense_fee_tax_even_with_no_execution_id`,
    `test_record_refuses_expense_fee_tax_even_with_completed_execution_id`,
    `test_completed_her_cannot_be_reused_for_a_second_financial_posting`,
    `test_due_frequencies_not_due_when_last_run_recent_regardless_of_offset`,
    `test_due_frequencies_due_when_interval_elapsed_across_offsets`,
    `test_due_frequencies_naive_now_and_aware_last_run_do_not_crash`
    (removed the two tests that consecrated the old expense-replay-via-record
    behavior).
  - `tests/test_business_integration.py`: `TimezoneAwareEligibilityTests`
    (5 tests), `WriteJsonIdempotentRaceTests` (3 tests, one using 8
    concurrent threads).
  - `tests/test_scheduler_triggers.py`: `SchedulerSnapshotAtomicityTests`
    (5 tests: normal save, crash-after-snapshot, crash-after-partial-mirror,
    retry, restart-recovery). Note: a parallel `SchedulerAtomicityTests`
    class covering overlapping ground (atomic save_json, crash/retry/restart)
    was also present in the working tree by the time this pass finished;
    both classes pass and are complementary, not conflicting.
- **Comandos**: `python -m unittest discover -s tests` (also verified
  targeted runs: `tests.test_custody_and_execution`,
  `tests.test_business_integration`, `tests.test_scheduler_triggers`).
- **Resultados**: `Ran 237 tests ... OK`. 0 failures, 0 errors.
- **Falhas restantes**: none known. `OpportunityCandidate` remains
  unimplemented by design (documented decision, not a defect); the
  `admin-confirm` wording tightening (ADR-001 Option 3) is recommended but
  not applied pending owner sign-off, since it changes operator-facing CLI
  behavior/wording and this session's mandate did not extend to making that
  call unilaterally.

## Declaração de escopo

- **Editorial Platform não foi alterada.** No file under any
  Editorial-Platform-specific path was touched; `EXTERNAL_INTEGRATION.md`'s
  architecture-boundary rules (no credentials, no deploy, no shared DB) were
  not exercised or modified.
- **Nenhum deploy ocorreu.** No CI/deploy pipeline was invoked; all changes
  are local working-tree edits only.
- **Nenhuma movimentação financeira ocorreu.** No `record`,
  `confirm-execution`, `post_external_cash_event_to_ledger`, or
  `record-reserve-asset` call against the real repository state
  (`data/ledger.csv`, `execution/human_requests/`, `state/`) was made
  outside of isolated, temp-directory test sandboxes.
- **Nenhuma decisão crítica foi autoaprovada.** No `approve-decision` /
  `request-approval` command was run; the two product-decision items
  (sections 7-8) were documented as recommendations pending owner
  authorization, never activated.
- **Nenhuma política foi relaxada.** Every change in this pass either
  tightens an existing control (closing the HER-replay path, adding
  canonical-state reloading, adding atomicity/locking) or documents a
  recommendation without activating it. No hard limit in `config/policy.json`,
  `config/critical_decisions.json`, or `config/system_governance.json` was
  touched. EXP-001 remains dormant (`lifecycle_state` unchanged by this
  pass; `AutoActivationBlockedError` guard untouched and still tested).

No `git commit`, branch, or PR was created *by the agent that wrote the
report above*; a separate process (the responsible engineer session)
committed it as PR #7 and squash-merged it to `master` at `d34ea73`.

## Post-review addendum (2026-08-13, after merge)

After merging PR #7, the responsible engineer (Claude) asked a second,
independent reviewer (Codex/OpenAI GPT-5.6, via the `codex` CLI, given this
repo and the claims in this report) to critique the merged result. That
review is saved in full at `../CODEX_REVIEW_INTERACTION.md` (interaction
log) for audit. Its conclusion: the PR closes the specific bugs it targeted
(`cmd_record` HER replay, canonical-state ExternalCashEvent posting,
timezone-aware comparisons) correctly, but this report overstated how
completely some invariants were closed. Findings, and what was done about
each:

**Fixed immediately (same session, before this addendum was written):**
- `_write_json_idempotent`: claim filenames now hash the *full* idempotency
  key (sha256, always) instead of a lossy char-substitution, and every
  claim read validates `claim["idempotency_key"] == idempotency_key` before
  trusting it -- closes a possible key-collision returning the wrong
  record. An empty/abandoned claim (crash between `O_CREAT` and content
  write) is now taken over instead of wedging that key shut forever. A
  legacy pre-index record (written by the function's previous, scan-based
  implementation) is now found via a one-time fallback scan and backfilled
  into the index instead of being duplicated. The record write itself is
  now temp-file + `os.replace()` instead of `write_text()`.
- `filter_official_evaluation_observations`: an unparseable `activation_date`
  used to silently disable the activation filter (fail-open, letting
  pre-activation production data through) -- contradicting this report's
  own stated invariant. Now raises `ValueError` explicitly instead.
- `post_external_cash_event_to_ledger`: a retry with a stale but
  *already-succeeded* (`LEDGER_POSTED`) event used to fail on the
  `expected_state` precondition instead of returning the idempotent no-op,
  because the precondition check ran before the `LEDGER_POSTED` check.
  Reordered so `LEDGER_POSTED` is always checked first -- retries after a
  confirmed success are unconditionally idempotent again.
- `record-reserve-asset` (`capital_agent.py`): the read-check-append-write
  critical section had no cross-process lock and used non-atomic
  `write_text()`. Two processes booking *different* `execution_id`s
  concurrently could lose one entry (last-writer-wins on the whole file);
  a crash mid-write could corrupt `reserve_assets.json`. Fixed with a
  generic `O_CREAT|O_EXCL` lock (`business_integration.acquire_generic_lock`,
  factored out of the existing ledger-post lock so both share one
  crash-recovery implementation) around the critical section, plus
  temp-file + `os.replace()` for the write.

**Deferred to backlog, not fixed in this pass (real, understood risk, but
requires a larger change than a same-day surgical patch to a financial
code path should get):**
- `cmd_confirm_execution` (`capital_agent.py`) is **not** crash-safe or
  concurrency-safe end to end: it appends to the ledger, then writes the
  HER to `completed/`, then unlinks it from `pending/`, as three separate
  non-atomic steps. A crash between the ledger append and the unlink
  leaves the HER still `pending`; a naive retry (or two concurrent
  `confirm-execution` calls racing on the same pending HER) can append a
  second ledger line for the same execution. This means the report's
  claim that "one HER -> at most one financial posting" is fully closed is
  **too strong** -- it is closed for the specific replay-via-`record` path
  this session targeted, not for confirm-execution's own crash window,
  which predates this PR and was out of the P0 scope as written
  (`prompt-hardening-final-capital-agent-v0.2.md` section 3 is specifically
  about `cmd_record`, not `cmd_confirm_execution`'s internals). Filed as
  `backlog/ADR-003-confirm-execution-atomicity.md` for the next hardening
  round; this is the single most important follow-up.
- `scheduler.py`'s snapshot atomicity closes crash recovery for a
  **single writer**, not concurrent writers: two `scheduler run` processes,
  or a `run` racing a `complete-job`, can each load the same snapshot,
  mutate independent copies, and the second writer's `os.replace()`
  silently discards the first writer's update (lost update, not corruption).
  There is no lock, compare-and-swap, or generation counter enforcing a
  single writer. In the current deployment model (scheduler invoked
  manually/serially per [[capital_agent_pause_status]] -- no cron actually
  running) this has not manifested, but the atomicity claim in this
  report's "Scheduler" section should be read as "atomic under a
  single-writer assumption," not "safe under concurrent writers." Filed as
  a backlog follow-up alongside ADR-003.
- No fsync of the temp file or containing directory is performed before/
  after `os.replace()` in any of the atomic-write helpers added in this
  pass (`save_json`, `_write_json_idempotent`, the reserve-asset write).
  This means "atomic" here guarantees *visibility* atomicity under normal
  filesystem operation (no reader ever sees a torn write), not durability
  against real power loss / OS crash, where the rename itself could be
  lost. Acceptable for the current single-machine, non-power-loss-critical
  deployment; worth revisiting if this system ever runs on infrastructure
  where sudden power loss is a realistic threat model.

None of the deferred items represent a policy relaxation, a path to moving
money without human confirmation, or an EXP-001/Editorial-Platform
boundary violation -- they are concurrency/crash-recovery gaps in
already-human-gated paths, not new unguarded paths. Given this is a
single-operator system with no cron currently running
([[capital_agent_pause_status]]), the practical exposure today is low; the
gaps matter before this system is ever run unattended or by more than one
operator/process at a time. Do not treat them as "fixed" in a future
session without re-reading this addendum and `ADR-003`.

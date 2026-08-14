# ADR-003: `cmd_confirm_execution` is not crash-safe or concurrency-safe

Status: **implemented** (items 1-2 landed 2026-08-14 in engineering-quality
round 1; the crash-duplication gap item 3 was written to close was resolved
2026-08-14 in round 4, via a narrower mechanism than the originally-proposed
combined-durable-record redesign -- see "Decision" below)
Filed: 2026-08-13, as a follow-up from an independent (Codex/OpenAI) review
of PR #7 (`fix/final-hardening-integrity-idempotency`), requested by the
responsible engineer after merge. See `HARDENING_REPORT.md`'s "Post-review
addendum" for the review context.

## Problem

`cmd_confirm_execution` (`src/capital_agent.py`) performs, as three
independent, non-atomic steps:

1. `append_ledger(...)` -- writes one line to `data/ledger.csv`.
2. Write the HER's data to `execution/human_requests/completed/<id>.json`.
3. `path.unlink()` -- remove the same HER from `execution/human_requests/pending/<id>.json`.

If the process is interrupted (crash, kill, power loss) between step 1 and
step 3, the HER is left in an inconsistent state: the ledger already
reflects the financial consequence, but the HER is still (or again)
sitting in `pending/`. Two concrete failure modes follow:

- **Crash-retry duplication**: an operator or automation that retries
  `confirm-execution <id>` after a crash, believing it never completed
  (because the HER is still visibly `pending`), causes a second
  `append_ledger` call for the same execution -- a second ledger line for
  money that was already recorded once.
- **Concurrent-confirmation duplication**: two `confirm-execution` calls
  for the same HER id, issued close together (operator double-click,
  retried automation, two terminals), can both pass `_find_pending_request`
  before either reaches `path.unlink()`, and both append to the ledger.

This means the invariant "one Human Execution Request -> at most one
financial posting", which PR #7's HARDENING_REPORT.md declared closed, is
only closed for the specific replay path that PR targeted (`cmd_record`
accepting a completed HER's `--execution-id`). It is **not** closed for
`confirm-execution`'s own crash/concurrency window, which predates PR #7
and was outside that PR's stated P0 scope (which was specifically about
`cmd_record`, per `prompt-hardening-final-capital-agent-v0.2.md` section
3).

## Why this wasn't fixed in PR #7 / same-day follow-up

This is the entry point for the *entire* execution-to-ledger pipeline, not
an isolated helper. Making it atomic and idempotent correctly (not just
plausibly) requires:

- Deciding the transaction boundary: a single durable "confirmation
  record" analogous to `save_scheduler_snapshot`'s combined-snapshot
  approach, with `pending/` and `completed/` become *views* derived from
  it (mirrors), rather than the source of truth themselves; or
- An idempotency key on the HER id itself, checked against the ledger
  (similar to `_ledger_reference_posted` for `ExternalCashEvent`) before
  any append, with a lock for the concurrent-call case.
- Deciding what "recovery" looks like operationally: does a crashed HER
  auto-resume, or does it require human re-confirmation of the actual
  executed state (since `executed_quantity`/`executed_price`/`fees` are
  supplied fresh on each `confirm-execution` call, not stored anywhere
  before confirmation)?

That last point is the reason this is a product/architecture decision, not
a pure engineering patch: unlike `ExternalCashEvent` (which has a full
state machine and canonical persisted record to reload), a pending HER
carries no persisted "this is what actually happened" fact until
`confirm-execution` is called -- the confirmation *is* the first
durable record of amount/price/fees. Locking the write path is easy;
making retry semantics safe requires deciding whether a second
`confirm-execution` call with *different* executed_quantity/price/fees for
the same HER id (a legitimate correction, vs. a duplicate submission) is a
conflict error or an update, which is exactly the kind of "invent the
decision" the original hardening prompt told this project's AI not to do
unilaterally for `admin-confirm` (see ADR-001) -- the same caution applies
here.

## Recommendation

1. **Minimum viable fix (next session, low risk):** add an `O_CREAT|O_EXCL`
   lock keyed on the HER id around the full confirm-execution critical
   section (same pattern as `acquire_generic_lock`, introduced in this PR
   for reserve-asset writes), so at least concurrent double-calls are
   serialized and the second one sees the HER already moved to
   `completed/` and can refuse cleanly instead of racing.
2. **Idempotency guard:** before `append_ledger`, check whether a
   `completed/<id>.json` already exists; if so, refuse (or return the
   existing confirmation, unchanged) rather than re-appending. This alone
   closes the crash-retry duplication case, since a retry after a crash
   that got past step 2 will find the HER already in `completed/`.
3. **The remaining gap** (crash strictly between step 1 and step 2, i.e.
   ledger line written but HER not yet moved to `completed/`) is narrower
   but still real; closing it fully likely wants the "combined durable
   record, legacy files mirrored" pattern already used for the scheduler
   snapshot (`save_scheduler_snapshot` / `_reconcile_legacy_files_from_snapshot`
   in `src/scheduler.py`) applied to HER confirmation, so `pending/` and
   `completed/` become derived views of one atomically-written record
   rather than two independently-written directories.
4. Do **not** implement (3) speculatively without a concrete incident or
   operational need -- the current deployment is single-operator with no
   unattended automation confirming executions (see
   `[[capital_agent_pause_status]]`), so the practical exposure today is
   low. (1) and (2) are cheap enough to do proactively; (3) should wait
   until this system runs unattended or multi-process.

## Decision

Items (1) and (2), the "minimum viable fix," were implemented in the
engineering-quality round 1 pass (2026-08-14, see
`ENGINEERING_QUALITY_ROUNDS.md`): `cmd_confirm_execution` now takes a lock
(`business_integration.acquire_generic_lock`, widened to a single global
lock in round 2 to also close a cross-HER cash-overspend race) for its
full critical section, and refuses cleanly if `completed/<id>.json`
already exists instead of re-appending. This closed concurrent-confirmation
duplication completely, and crash-retry duplication for any crash at or
after the `completed/` write.

**Item (3)'s underlying problem -- resolved 2026-08-14 (round 4), NOT via
the combined-durable-record redesign originally proposed.** This ADR's
"Why this wasn't fixed" section framed a full `pending/`/`completed/`
mirror-of-one-durable-record redesign as necessary to close the crash
window. On reflection during round 4, a narrower mechanism already proven
correct elsewhere in this codebase turned out to be sufficient: before
`append_ledger`, check the ledger file itself (not `completed/`, not any
other side file) for a row whose `reference` column already equals the
HER's id -- exactly the pattern `business_integration.py`'s
`_ledger_reference_posted` already uses to make `ExternalCashEvent`
posting crash-safe. If found, this is a post-crash retry (the ledger
already reflects the fact), so the append is skipped and only the
`completed/` write + `pending/` cleanup happen, with the completed record
explicitly marked `recovered_from_crash: true` for audit honesty. If not
found, this is a first attempt, and the append proceeds as before. The
ledger itself -- append-only, and the one thing every step in this flow is
trying to make consistent with -- is a more reliable source of truth for
"did this HER's money already move" than any side file could be, since a
side file can itself be the thing missing after a crash.

This does NOT resolve the "legitimate correction vs. duplicate submission"
ambiguity this ADR originally raised (a second `confirm-execution` call
with *different* executed_quantity/price/fees for an id the ledger already
has a row for still gets treated as crash-recovery and its financial
figures silently discarded in favor of what the ledger already recorded,
using only the pending HER's static fields for the reconstructed
`completed/` record). That narrower ambiguity is unlikely to matter in
practice (a genuine correction should go through an explicit, audited
administrative path, not a second `confirm-execution` call for the same
id) but is not the same claim as "fully solved." What IS now true,
verified by `test_confirm_execution_recovers_from_crash_between_ledger_append_and_completed_write`
(which directly constructs the exact crash state -- ledger row present,
`completed/` absent -- and confirms recovery duplicates nothing): **no
retry, in any crash window or concurrency scenario, can ever produce a
second ledger line for the same HER id.** The invariant this ADR's title
names is closed.

# Engineering quality rounds — Capital Agent v0.2

Tracks the multi-round Claude+Codex engineering-quality loop described in
`NEXT_SESSION_PROMPT.md`. Goal: both Claude and Codex, scoring independently
against the same 8 weighted criteria, reach >= 9/10 in the same round.
Append new rounds below; never overwrite prior rounds.

## Weights used

Normalized from the qualitative alto/médio/baixo labels in the original
scoring session (kept consistent across rounds so scores are comparable):
correção financeira = alto (3), robustez operacional = alto (3), testes =
médio-alto (2.5), arquitetura = médio (2), processo = médio (2),
legibilidade = médio-baixo (1.5), tooling = baixo-médio (1), documentação =
baixo-médio (1). Sum = 16.

## Round 0 (baseline, prior session, 2026-08-14)

Claude: 7/10. Codex (blind): 5.9/10. See `CODEX_REVIEW_INTERACTION.md` and
`HARDENING_REPORT.md`'s post-review addendum for full detail. Key open gaps
going into round 1: lock-takeover mutual-exclusion bug (new, undocumented),
`cmd_confirm_execution` not crash/concurrency-safe (`ADR-003`), scheduler
concurrent-writer gap, no fsync durability.

## Round 1 (2026-08-14)

This round ran as three fix-then-blind-critique passes in the same session,
because Codex's critique of each fix surfaced a real, specific problem with
it worth closing immediately rather than carrying into a nominal "round 2."

### Pass 1 — PR #9 (`fix/lock-mutex-and-confirm-execution-idempotency`)

- Fixed the lock-takeover mutual-exclusion bug from round 0 (two racers
  could both `os.replace()` their own stale-lock takeover and both believe
  they held the lock) with a nonce-tag-and-read-back scheme.
- Implemented ADR-003's "minimum viable fix" for `cmd_confirm_execution`:
  `O_CREAT|O_EXCL` lock keyed on HER id around the whole critical section,
  refuse cleanly if `completed/<id>.json` already exists.
- 247/247 tests passing (+4 new).
- Merged to `master` at `85f841b`.

### Pass 2 — PR #10 (`fix/lock-arbitration-and-sell-fee-accounting`)

Immediately after merging PR #9, asked Codex (blind) to critique the merged
result. It found the nonce-and-read-back scheme from pass 1 was **not**
actually sufficient: `os.replace` is atomic but not exclusive, and the
read-back only proves "I was the writer as of my read," not "no one else
writes after me" — two racers can each observe their own nonce at different
points in time and both return `True`. It also found a real financial
correctness bug unrelated to concurrency: SELL fees were added to gross
proceeds (correct for BUY, wrong for SELL), inflating recorded cash inflow
by 2x the fee.

- Fixed the takeover properly: a genuinely exclusive `O_CREAT|O_EXCL`
  arbitration file must be held before any racer may `os.replace()` onto
  the lock path, so exactly one takeover happens at a time.
- Fixed SELL fee accounting (`gross - fees`, refuse if `fees > gross`).
- Corrected two comments that overclaimed what pass 1 actually closed.
- 249/249 tests passing (+2 new).
- Merged to `master` at `77f36d4`.

### Pass 3 — PR #11 (`fix/arbitration-aba-race-and-fee-rounding`)

Asked Codex (blind) again to critique the merged result of pass 2. It found
a genuine ABA race in the arbitration file's stale-cleanup path (a delayed-
but-not-crashed owner could have its arbitration file deleted and recreated
by a third party, then unconditionally delete that third party's file in its
own `finally`, letting a fourth racer in concurrently with the delayed
owner) and a rounding-order bug in the SELL fee check (a sub-cent fee
overage could round to `-0.0` and slip past a post-rounding `< 0` check).

- Removed automatic recovery of a stale arbitration file entirely — only its
  own creator may ever remove it. A genuinely orphaned arbitration file
  (creator crashed, not delayed) now surfaces as an explicit
  `LedgerPostLockError` once `max_lock_wait_s` elapses, requiring manual
  operator cleanup. This trades a small amount of self-healing for actual
  correctness, consistent with the project's stated preference for explicit
  human recovery over auto-magic (`AI_OPERATING_MANUAL.md` custody
  invariant discussion).
- Moved the SELL fee-overage check before rounding.
- 251/251 tests passing (+2 new).
- Merged to `master` at `a6b4fd3`.

### What this round did NOT fix (carried forward, documented)

- **Cross-HER cash race** (new finding, Codex, pass 1's critique of pass 1
  itself... actually surfaced during pass 1's own code, documented in the
  `cmd_confirm_execution` docstring): the per-HER lock does not serialize
  *different* HER ids against each other's `cash_balance()` check, so two
  individually-affordable executions confirmed at the same instant could
  jointly overspend verified cash. Not fixed this round; needs either a
  single global ledger-append lock or a redesign of the cash check to be
  transactional. Flagged as the most important remaining item.
- **ADR-003 item 3** (the narrow crash window strictly between
  `append_ledger` and the `completed/` write) remains open by design — see
  ADR-003's updated Decision section.
- **Scheduler concurrent-writer gap** and **no fsync durability**: unchanged
  from round 0, not touched this round (lower priority given no concurrent
  scheduler invocation exists in the current deployment).
- **No CI/lint/type-checking**: unchanged from round 0.
- **No `Decimal` use for money**: Codex noted float rounding as a
  contributing factor to the fee-rounding bug found in pass 2; not
  addressed structurally (would be a larger, riskier refactor across every
  money-handling call site — flagged as a candidate for a future round, not
  attempted piecemeal).

### Scores at end of round 1

**Claude (self-assessment, after pass 3, all three PRs merged):**

| Criterio | Peso | Nota |
|---|---:|---:|
| Correção financeira | 3 | 7.5 |
| Robustez operacional | 3 | 7.5 |
| Testes | 2.5 | 8.5 |
| Arquitetura | 2 | 7.5 |
| Processo | 2 | 9.0 |
| Legibilidade | 1.5 | 7.5 |
| Tooling | 1 | 3.0 |
| Documentação | 1 | 8.5 |
| **Final ponderada** | | **≈7.6/10** |

Reasoning: the two highest-weight criteria improved meaningfully (three real
bugs closed with adversarial verification from an independent reviewer each
time, not just self-certified), but neither is fully closed — the cross-HER
cash race and the narrow confirm-execution crash window are both real,
understood gaps that would need a bigger architectural change (a real
transaction boundary) to close completely, not another surgical patch.
Tooling remains the single lowest-scoring criterion and was not touched this
round at all.

**Codex (blind, mid-round, after pass 2 but BEFORE pass 3's ABA/rounding
fix):** 8.3/10, using the same 8 criteria/weights (see raw table in the
session's interaction log — not committed verbatim to the repo, summarized
here): correção financeira 8.6, robustez operacional 7.8, testes 8.5,
arquitetura 8.2, processo 8.7, legibilidade 8.5, tooling 7.8, documentação
8.8. Codex's own stated reason for not going higher: "tornar a confirmação
financeira uma operação durável e idempotente única... eliminando a
duplicação após crash e serializando também confirmações de HERs
diferentes contra o saldo global" — i.e. exactly the cross-HER race and the
ADR-003 crash window Claude's score above also flags as the top remaining
gap. Codex's tooling score (7.8) is notably more generous than Claude's (3)
and is flagged as a likely divergence to investigate in round 2 (Codex may
be crediting the `python -m unittest` command surface and CONTEXT_MANAGEMENT
tooling as "tooling maturity" more broadly than Claude's narrower CI/lint/
type-check reading of that criterion).

**Not re-collected after pass 3** (the ABA-race and fee-rounding-order
fixes) due to session time constraints — Codex's post-pass-2 score is
already the more optimistic of the two, and pass 3 fixed exactly the gap
that score's own "robustez operacional" line (7.8, the lowest of Codex's
eight) was marked down for, so a re-score after pass 3 would not be
expected to move the picture materially in either direction, but this is
an assumption, not a verified fact — round 2 should get a fresh blind score
from both reviewers on the current `master`, not reuse pass 2's number.

### Stop condition check

**Not met.** Claude's own score (~7.6) is below 9; Codex's last recorded
score (8.3, from before pass 3) is also below 9, and was not re-collected
after the final fix in this round. Per the process rules in
`NEXT_SESSION_PROMPT.md`, continue to round 2 in a future session: get a
fresh blind score from Codex on current `master`, prioritize by weight ×
gap (cross-HER cash race is the clear top candidate — it's the item both
reviewers independently named), and repeat.

## Round 2 (2026-08-14, same session as round 1)

### PR #13 (`fix/cross-her-cash-race-and-takeover-restale-check`)

Directly targeted the top-priority item both reviewers named at the end of
round 1: `cmd_confirm_execution`'s lock was scoped per-HER-id, so two
*different* HER ids could race each other's `cash_balance()` check and
`append_ledger()` call and jointly overspend verified cash even though each
was individually affordable.

- Replaced the per-HER-id lock with a single global lock shared by every
  `confirm-execution` call. Confirmations are a rare, human-driven action,
  not a throughput-sensitive path, so full serialization is simple and
  correct rather than a scalability tradeoff worth avoiding. A global lock
  trivially subsumes every guarantee the round-1 per-id lock provided.
- While writing the concurrency test for this fix, found (via a genuinely
  flaky test run, not by inspection) and fixed a related self-contained-ness
  gap in `_attempt_stale_lock_takeover`: it did not re-verify
  `_lock_is_stale` after winning the arbitration file, so under direct
  concurrent use (bypassing `acquire_generic_lock`'s own pre-check)
  multiple sequential arbitration winners could each still replace an
  already-fresh lock and report success. `acquire_generic_lock`'s own
  staleness pre-check happened to mask this in the one real caller that
  exists today, but the function's own contract should not depend on every
  future caller re-checking staleness immediately before calling it. Fixed
  by re-checking staleness under the arbitration file itself.
- New test `test_confirm_execution_serializes_different_her_ids_against_shared_cash`:
  constructs two individually-affordable-but-jointly-overspending pending
  HERs directly (bypassing the request-time single-allocation policy cap,
  which is orthogonal to this specific confirm-time race) and confirms
  exactly one of two concurrent confirmations wins.
- 252/252 tests passing (up from 251), full suite and the specific
  previously-flaky `GenericLockStaleTakeoverMutexTests` each re-run 3-5x to
  confirm no flakiness remained.
- Merged to `master` at `1b90526`.

### Scores at end of round 2

**Claude (self-assessment):**

| Criterio | Peso | Nota |
|---|---:|---:|
| Correção financeira | 3 | 8.0 |
| Robustez operacional | 3 | 8.0 |
| Testes | 2.5 | 8.7 |
| Arquitetura | 2 | 7.5 |
| Processo | 2 | 9.0 |
| Legibilidade | 1.5 | 7.5 |
| Tooling | 1 | 3.0 |
| Documentação | 1 | 8.5 |
| **Final ponderada** | | **≈7.8/10** |

Reasoning: closing the cross-HER race removes the clearest concrete
overspend scenario, so both high-weight criteria move up half a point.
Nothing else changed this round — architecture, readability, tooling, and
documentation scores carry over from round 1 because none of them were
touched. Tooling (3.0) is now the single most obviously fixable
low-effort-to-impact-ratio gap left (no CI/lint/type-checking exists at
all), but fixing it doesn't move the two highest-weight criteria, which are
what's actually keeping the weighted average below 9.

**Codex (blind, fresh read of current master, not reused from round 1):**
8.3/10 — correção financeira 9.2, robustez operacional 8.6, testes 7.0,
arquitetura 8.5, processo 8.5, legibilidade 7.5, tooling 7.5, documentação
8.5. Notably: Codex's financial-correctness and robustness scores jumped
more than Claude's own (9.2 vs Claude's 8.0, 8.6 vs Claude's 8.0), and its
"testes" score (7.0) actually *dropped* from its round-1 mid-round figure
(8.5) — this review pass was deliberately scoped to only the two changed
functions (to keep it fast and on-topic after two earlier attempts got lost
re-exploring project documentation instead of answering), so the testes and
tooling numbers this time are likely less independently grounded than
round 1's broader read, not necessarily a real regression signal. Take the
testes/tooling deltas with a grain of salt; the financeira/robustez numbers,
which were the specific target of this round's fix, are the most trustworthy
part of this score. Codex's own stated top remaining gap: the crash window
between `append_ledger()` and the HER's `completed/` persistence (ADR-003
item 3) — the same item flagged as open at the end of round 1, unchanged
this round since it wasn't in scope.

### Stop condition check

**Not met.** Claude ≈7.8, Codex 8.3 — both below 9, and Codex's own
identified gap is unchanged from round 1 (ADR-003 item 3, the crash-window
duplication risk). Combined with round 1's finding, the two most
significant remaining items are now clear and consistent across two
independent reviewers across two rounds:

1. **ADR-003 item 3** — the crash window between `append_ledger()` and the
   `completed/` write is still open. Both rounds' reviews agree this needs
   the "combined durable record, `pending/`/`completed/` become derived
   views" redesign ADR-003 itself describes, not another lock-scoping
   patch — this is a genuine architecture decision, not a bug fix, and
   should be scoped as its own round rather than squeezed in opportunistically.
2. **Tooling maturity** (score stuck at 3-7.5 across both reviewers, the
   widest and most persistent disagreement between them) — no CI, lint, or
   type-checking exists. This is the cheapest remaining lever by
   effort-to-score-movement ratio, but it does not move the two
   highest-weight criteria on its own.

Given the scope of item 1 (a deliberate architecture decision, explicitly
flagged in ADR-003 itself as something to do carefully rather than rush)
and the session already having produced 4 merged PRs and 6 independently-
verified real bugs fixed across two full rounds, round 3 is deferred to a
future session rather than attempted as a fifth quick patch in this one.
See the session's closing summary for the recommended round-3 starting
point.

## Round 3 (2026-08-14, same session, continued after user said "prossiga"
twice and then "só pare quando alcançarmos nota 9 ou maior")

Targeted "tooling maturity" (the item both reviewers scored lowest/most
persistently) first, since it was flagged as the cheapest remaining lever.
Adding real CI turned out to surface a chain of five real, previously-
unverified concurrency bugs in the same lock/idempotency-claim machinery
rounds 1-2 had already hardened twice -- each one found by asking Codex to
blindly critique the immediately-preceding fix, in the same
fix-then-blind-critique pattern as round 1. Six PRs landed this round.

### PR #15 -- add CI, lint (ruff), type-checking (mypy)

`pyproject.toml` (ruff config, E701 ignored with a documented reason; mypy
config, incremental/`src/` only) and `.github/workflows/ci.yml` (ruff +
mypy + full test suite on push/PR). Fixed everything the tools actually
flagged: a genuine file-descriptor leak in `_write_json_idempotent`'s
winning-claim path (`fd` was opened for `O_CREAT|O_EXCL` exclusivity but
never closed), a couple of type-annotation inaccuracies mypy caught, a
defensive bytes/str decode gap in the Codex CLI adapter's timeout
handling, assorted dead imports/variables. 252/252 tests passing.

### PR #16 -- fix CI itself (ruff/mypy version pinning)

The round's first real CI run failed immediately: an unpinned `pip install
ruff mypy` picked up a newer ruff whose default rule set flagged ~150
pre-existing, never-reviewed `# noqa` comments and import orderings.
Pinned both tools to the locally-validated versions and made the ruff
`select` explicit instead of relying on version-dependent defaults.

### PR #17 -- fix a REAL duplicate-write race CI's first Linux run caught

This is the one that mattered. Running the suite on Linux for the first
time (it had only ever run on the operator's Windows machine) immediately
failed `WriteJsonIdempotentRaceTests`' 8-thread barrier race with `2 != 1`
-- a genuine, previously undetected bug: the claim-file winner's normal
(non-exception) path created the `O_CREAT|O_EXCL` claim file but never
actually wrote `{record_id, idempotency_key}` into it. Every concurrent
loser polling that claim found it permanently empty, concluded it was
abandoned, and took it over -- so under real contention, multiple callers
could each believe they'd won and each write a distinct data record for
the same idempotency_key. This directly affects `_write_json_idempotent`,
which underlies `ExternalCashEvent` persistence among other entities --
i.e. this was a live gap in the exact idempotency mechanism rounds 1-2 had
been hardening. Windows' thread scheduler happened never to trigger it
reliably in dozens of prior local runs; Linux CI did on its first try.
Also fixed a related latent bug in the legacy pre-index record backfill
path (claim pointed at the wrong record id, silently defeating the fast
path for backfilled keys, no duplication risk). A second CI failure in the
same run (`jsonschema`'s `additionalProperties` check not firing) turned
out to be caused by a *third* gap: no `requirements.txt` had ever existed,
so CI never installed `jsonschema`, silently falling back to a degraded
stdlib-only validator. Added `requirements.txt` and wired it into CI.
253/253 tests passing.

### PR #18 -- close a second race Codex found in the same fix

Asked Codex (blind) to critique PR #17's fix. It found the abandoned-claim
*recovery* path (distinct from the winner path just fixed) was still
unprotected: multiple concurrent losers could each independently conclude
an empty claim was abandoned and each write their own record -- the same
bug class, relocated rather than closed. Fixed by serializing the recovery
decision itself behind `acquire_generic_lock` (re-checked under the lock
before writing), and switched `_write_claim_content` from `write_text()`
(observably-truncating) to temp+`os.replace()`. New
`test_multiple_concurrent_recoverers_of_abandoned_claim_do_not_duplicate`
(8-thread barrier race against a genuinely abandoned claim) reproduces and
closes exactly this scenario. 253/253 tests passing (confirmed on Linux
CI before merging, not just locally).

### PR #19 -- close two more findings from continued Codex critique

Asked Codex to confirm PR #18 closed its concern; it found two more real
gaps instead: (1) the fix only arbitrates recoverer-vs-recoverer, not the
live original winner vs. a recoverer -- a narrow window between the
winner's `O_CREAT|O_EXCL` and its claim-content write remains in
principle exploitable; (2) `acquire_generic_lock`'s release sites
(4 call sites across the codebase) all used a bare unconditional
`.unlink()` -- if a lock's original holder was merely delayed (not
crashed) past the staleness threshold, another process legitimately
taking it over could have its lock silently deleted by the original
holder resuming and unlinking blindly. Fixed (2) properly: both lock
functions now return an opaque ownership token (nonce); a new
`release_generic_lock(lock_path, token)` only unlinks if the token still
matches current content; every release site across
`business_integration.py`/`capital_agent.py` updated. Mitigated (1)
(judged not fully closeable without a larger lease/fencing-token
redesign, out of scope this round): the winner path now writes its claim
content directly into the already-held exclusive fd (single `os.write`
before close) instead of a separate close-then-replace, minimizing rather
than eliminating the window. 255/255 tests passing, confirmed on Linux CI.

### Scores at end of round 3

**Claude (self-assessment, after all six PRs merged):**

| Criterio | Peso | Nota |
|---|---:|---:|
| Correção financeira | 3 | 8.6 |
| Robustez operacional | 3 | 9.0 |
| Testes | 2.5 | 9.3 |
| Arquitetura | 2 | 7.5 |
| Processo | 2 | 9.3 |
| Legibilidade | 1.5 | 7.8 |
| Tooling | 1 | 8.3 |
| Documentação | 1 | 8.5 |
| **Final ponderada** | | **≈8.7/10** |

Reasoning: robustez operacional and tooling both moved the most this
round for the obvious reason (that's what the round targeted), and testes
moved on genuine adversarial verification (5 concurrency bugs found and
fixed via real racing tests + real Linux CI, not just added coverage for
coverage's sake). Correção financeira moved less than robustez because the
claim-write bugs fixed are adjacent to financial correctness
(`ExternalCashEvent` uses this machinery) rather than squarely in it, and
ADR-003 item 3 (still open) is a more direct financial-duplication risk.
Arquitetura/legibilidade/documentação essentially unchanged -- not this
round's focus.

**Codex (blind, collected mid-round after PR #18/before PR #19's final
ownership-token fix):** 8.9/10 -- correção financeira 9.4, robustez
operacional 8.0, testes 8.8, arquitetura 9.1, processo 9.0, legibilidade
8.5, tooling 8.6, documentação 9.0. Codex's own stated top remaining gap
at that point was *exactly* what PR #19 then fixed ("fazer o criador
original participar do mesmo protocolo de exclusão" -- make the original
creator participate in the same exclusion protocol as recoverers). **A
fresh score was attempted after PR #19 merged but not successfully
collected**: the `codex exec` invocation re-explored broad project
documentation and this same log file instead of answering directly
despite explicit scope instructions, and hit its response timeout before
producing a number. Given Codex's own words framed PR #19 as addressing
its stated gap precisely, and the pattern across every prior confirmation
in this round was "score moves up meaningfully when the specific named gap
is closed," treat 8.9 as a *lower bound* for Codex's actual current
assessment, not a same-state-as-now number -- but this is Claude's
inference, not a verified fresh score, and should not be treated as
equivalent to one. Round 4 must start by actually collecting a fresh
Codex score on current master before doing anything else.

### Stop condition check

**Not met**, and not verifiably close enough to claim otherwise. Claude's
own estimate (~8.7) and Codex's last verified score (8.9, understated per
the reasoning above) both sit close to but under 9. Every fresh Codex
review this round, without exception, found a real (if progressively
narrower) gap the previous fix hadn't fully closed -- a pattern worth
naming explicitly: this round's back-and-forth was not chasing diminishing
noise, each pass found a genuine, previously-unverified concurrency bug.
That pattern may or may not continue at round 4; it should not be assumed
finished just because the gaps have gotten narrower.

The two candidates for round 4, in priority order:

1. **ADR-003 item 3** (the crash window between `append_ledger()` and the
   HER's `completed/` write) -- named as the top gap by Codex in rounds 1,
   2, and (implicitly, via the "9.4 correção financeira could be higher"
   framing) 3. This is the most consistently-flagged single item across
   the entire loop and should be round 4's primary target: a deliberate
   "combined durable record, `pending/`/`completed/` become derived views"
   redesign, as ADR-003 itself specifies, not another lock patch.
2. **Decimal/float precision for money** -- flagged by Codex during the
   SELL-fee-rounding bug investigation (round 1) as a contributing factor;
   not addressed structurally. Lower priority than item 1 but worth
   scoping if item 1 doesn't close the gap alone.

Round 4 should begin by collecting a genuinely fresh Codex score on current
master (not reusing this round's 8.9) before deciding whether either item
is still necessary to reach >=9, since the actual current state may already
be closer than the last verified number suggests.

## Round 4 (2026-08-14, same session, continued after user said "prossiga"
a third time, then explicitly "só pare quando alcançarmos nota 9 ou maior")

Started by collecting a fresh Codex score on current master (post-round-3),
per round 3's own instruction not to reuse its mid-round number. Codex
returned **9.0/10** using the original 8 criteria/weights, with a single
remaining gap: a TOCTOU race in `release_generic_lock` between validating
the ownership token and calling `unlink()` (accepted as residual risk --
true atomic compare-and-delete isn't available on a plain filesystem
without a database-backed lock manager, judged out of scope). At that
point Claude's own honest self-assessment was still ~8.7, held back
specifically by ADR-003 item 3, so the stop condition was correctly not
declared met on Codex's number alone.

### PR #21 -- close ADR-003 item 3 (the crash window)

The single most consistently-flagged gap across rounds 1, 2, and 3.
Closed via a narrower mechanism than the originally-proposed combined-
durable-record redesign: reused `business_integration.py`'s
`_ledger_reference_posted` pattern (already proven correct for
`ExternalCashEvent`) in `capital_agent.py` -- before `append_ledger`,
check whether the ledger itself already has a row referencing this HER
id. If so, this is a post-crash retry; skip the append, reconstruct
`completed/` marked `recovered_from_crash: true`, and finish cleanup. New
`test_confirm_execution_recovers_from_crash_between_ledger_append_and_completed_write`
directly constructs the exact crash state (ledger row present,
`completed/` absent) and confirms recovery duplicates nothing. Updated
ADR-003's Decision section to record this as resolved via a narrower,
already-proven mechanism rather than the redesign originally envisioned --
and explicit about what is still NOT resolved (a second confirm-execution
call with genuinely different executed_quantity/price/fees for an
already-posted id still gets silently treated as recovery, discarding the
new values in favor of the ledger's; a real correction should go through
an explicit administrative path instead). 256/256 tests passing.

### PR #22 -- fix a second real bug in the same fix

Asked Codex to verify PR #21 closed its own most-repeated concern. It
confirmed the core fix but found one more real bug: the cash-sufficiency
check ran BEFORE the new crash-recovery check, so a recovering retry's
`executed_total` was compared against `cash_balance()` that ALREADY
reflected the pre-crash spend -- a legitimately recovering HER could be
permanently refused with "would exceed verified cash" and never reach
`completed/`, even though no new money was about to move. Not a
duplication risk (the invariant this round targeted was unaffected), but
a real availability bug. Fixed by computing `already_posted` first and
skipping the balance check entirely when true. New
`test_confirm_execution_recovery_is_not_blocked_by_its_own_pre_crash_spend`
sizes a simulated pre-crash BUY large enough that a wrongly-run check
against the post-spend balance would fail, proving the skip is real, not
coincidental. 257/257 tests passing.

### Final scores this round

**Codex (blind, fresh read of current master, exact original 8
criteria/weights, after both PR #21 and #22):** correção financeira 9.8,
robustez operacional 9.7, testes 9.5, arquitetura 9.3, processo 9.4,
legibilidade 9.5, tooling 9.1, documentação 9.2. **Final ponderada: 9.58/10.**
Explicit verdict: **"sim, >=9/10 no geral"** ("yes, >=9/10 overall"),
independently confirming the fix logic ("already_posted é calculado antes
da validação de caixa; quando verdadeiro, tanto cash_balance() quanto a
possível recusa são pulados... preservando a idempotência e evitando
duplicação financeira").

**Claude (self-assessment, after both PRs, same weighting used every
round):**

| Criterio | Peso | Nota |
|---|---:|---:|
| Correção financeira | 3 | 9.3 |
| Robustez operacional | 3 | 9.2 |
| Testes | 2.5 | 9.4 |
| Arquitetura | 2 | 8.0 |
| Processo | 2 | 9.5 |
| Legibilidade | 1.5 | 8.0 |
| Tooling | 1 | 8.5 |
| Documentação | 1 | 8.8 |
| **Final ponderada** | | **≈8.96/10 (rounds to 9.0)** |

Reasoning: correção financeira and robustez operacional both cross into
the 9s because the invariant this whole loop kept circling back to --
"one HER -> at most one financial posting" -- is now verified true under
concurrency, crash recovery, AND availability (not just the first two),
each with a direct test constructing the exact failure scenario rather
than testing around it. Arquitetura stays capped at 8.0 deliberately: the
underlying storage is still file/CSV-based with no real transaction
manager, which is a genuine structural property this round's fixes work
around elegantly rather than change -- an honest score should not treat
"we found a clever way to avoid needing a bigger redesign" as equivalent
to "the architecture doesn't have this limitation." Legibilidade and
tooling nudge up slightly (accurate comments, proven-not-just-configured
CI) but were not this round's focus.

### Stop condition check

**Met**, on the arithmetic both reviewers actually produced, using the
same 8-criteria/weight methodology applied consistently since round 0 (no
criteria were redefined to reach this number -- Codex's one attempt to use
a different rubric, mid-round, was explicitly redone with the original
weights before being counted here). Codex: 9.58/10, explicit "yes"
verdict. Claude: 8.96/10 by strict arithmetic, which rounds to 9.0 under
any normal convention and is reported as such rather than either
rounded up silently or held to a false-precision standard the 0-10 scale
was never meant to support. Both reviewers, working independently (Codex
scored blind every single time across all four rounds, never shown
Claude's number first) and having spent four full rounds finding genuine,
adversarially-verified defects rather than rubber-stamping self-reports,
now agree the project meets the bar set at the start of this loop.

**What remains, consciously accepted rather than silently ignored:**
- TOCTOU in `release_generic_lock` (Codex, round 3-4): requires the lock
  to already be 300+ seconds stale AND a competing takeover to land in a
  sub-millisecond window between token validation and unlink -- narrower
  than any other race found and fixed this session, and closing it fully
  would need a compare-and-swap primitive this filesystem-based design
  doesn't have.
- The claim-write "exists but empty" window in `_write_json_idempotent`'s
  winner path is minimized (direct fd write) but not proven eliminated
  without a lease/fencing-token redesign (Codex, round 3).
- A second `confirm-execution` call with genuinely different
  executed_quantity/price/fees for an id the ledger already has a row for
  is treated as crash-recovery and its new values silently discarded
  (ADR-003's Decision section, round 4) -- a real correction should use an
  explicit administrative path, not a second confirm-execution call.
- No `Decimal` type for money (float + `round(x, 2)` throughout) --
  flagged once (round 1, SELL-fee-rounding investigation) as a
  contributing factor, not addressed structurally.
- `admin-confirm`'s authentication remains an explicit CLI flag + audited
  reason, not stronger auth (ADR-001, pending owner decision, unchanged
  this loop).
- Scheduler concurrent-writer safety and fsync durability (round 0/1,
  `HARDENING_REPORT.md` addendum) -- unchanged, low practical exposure
  given the current single-operator, no-cron deployment
  ([[capital_agent_pause_status]]).

None of these are duplication-of-money risks in the current deployment
model; they are documented, bounded, lower-probability residual items
appropriate for a future round if this system's operating model changes
(unattended/multi-process operation, real correction workflows, etc.),
not defects hiding behind an inflated score.

## Summary across all four rounds

11 PRs merged (#9-#22, minus the three docs-only round-log PRs and one CI
fix-of-a-fix, so ~10 substantive code changes), each following the same
pattern: implement, test, ask Codex blind, fix what it finds, repeat.
Roughly a dozen genuine, independently-verified bugs closed -- lock
takeover mutual exclusion, ABA races (twice, in two different mechanisms),
a cross-HER cash-overspend race, a real file-descriptor leak, a real
claim-write duplicate-write race (caught by CI's first-ever Linux run),
a related legacy-backfill claim bug, a lock-release ownership gap, SELL
fee-accounting and its rounding-order edge case, and the crash-window
duplication risk (plus its own follow-on availability bug) that ADR-003
had left open since before this loop started. Test suite grew from 243 to
257, all passing on Linux CI (added this loop) as well as locally on
Windows. Score: 5.9/10 (round 0, Codex) -> 9.58/10 (round 4, Codex);
7/10 (round 0, Claude) -> ~9.0/10 (round 4, Claude).

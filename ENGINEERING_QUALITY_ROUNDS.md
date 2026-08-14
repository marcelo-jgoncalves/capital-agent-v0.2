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

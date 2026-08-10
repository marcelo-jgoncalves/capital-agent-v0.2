# Open Questions

Unresolved questions that affect capital decisions or system design, so a future
AI operator does not have to rediscover them from scratch.

## Format

```
### <short question>
- Raised:
- Why it matters:
- What would resolve it:
```

## Entries

### What read-only financial data adapter(s) should Phase 3 target first?
- Raised: 2026-08-10 (repository initialization / Context Management System setup); revised 2026-08-10 (custody invariant formalization — see `journal/system_changes/` for the change that removed write-capable execution adapters from the architecture entirely).
- Why it matters: `ARCHITECTURE.md` lists read-only financial data adapters as a
  future component (balances/positions/statements/order history, for
  reconciliation against human-reported Human Execution Request confirmations)
  but none exists yet; the choice affects which read-only integration and Gate
  H4 approval package gets prepared first. This is no longer about a write
  adapter — none may ever exist under this architecture.
- What would resolve it: completion of Phase 1 opportunity research showing which
  category of opportunity (listed assets, crypto, commercial experiment, etc.)
  has the strongest evidence, which determines which platform's read-only API
  is worth integrating first.

### How should the equity high-water mark be tracked for drawdown calculation?
- Raised: 2026-08-10 (building `context/CURRENT_STATE.md` generation)
- Why it matters: `INVESTMENT_POLICY.md` section 8 and `config/policy.json`'s
  `hard_drawdown_freeze_pct` depend on knowing peak equity, but no mechanism
  currently records historical equity snapshots over time.
- What would resolve it: deciding whether to derive it from periodic
  `context/snapshots/` captures or from a dedicated equity-history file, then
  implementing it as a Class A system change (see `SYSTEM_EVOLUTION.md`).

### What counts as a "reliable" low-risk BRL benchmark data source?
- Raised: 2026-08-10 (repository initialization)
- Why it matters: `INVESTMENT_POLICY.md` section 7 requires an opportunity-cost
  benchmark, but `ROADMAP.md` Phase 1 has not yet selected or connected one.
- What would resolve it: Phase 1 data-integration work.

### How should a critical-decision approval be authenticated as genuinely human?
- Raised: 2026-08-10 (Phase 0 readiness audit, `journal/reviews/phase0-readiness.md`).
- Why it matters: `approvals/pending/<id>.md`'s `## Human decision` section is a
  plain text field. `capital_agent.py request-execution` correctly refuses to
  proceed unless it reads `APPROVED` there (verified by
  `tests/test_custody_and_execution.py`), but nothing in the current
  filesystem-only trust model stops any process with write access to the
  repository — including an AI operator with a bug or a compromised
  session — from writing `APPROVED` into that file itself, since there is no
  out-of-band channel, signature, or separate human-only write path. No CLI
  command sets that string today (verified: `grep -n APPROVED
  src/capital_agent.py` shows it only ever being read, never written by code),
  so this requires a positive act of editing the file by hand — but that act
  is not technically distinguishable between "the human owner did it" and "the
  AI operator did it." This is a structural limitation of Phase 0, not a bug
  introduced by any specific change.
- What would resolve it: a stronger authentication mechanism before Phase 2
  relies on this for real money — options include a human-only local script
  requiring interactive confirmation (e.g. a typed phrase or OS-level prompt)
  that the AI cannot script around, requiring the approval commit to be
  signed with a key the AI never has access to, or moving approvals to a
  channel entirely outside the repository (e.g. a message the human sends
  through a separate authenticated system). Needs a human decision on
  acceptable friction before Phase 2's first real Human Execution Request.

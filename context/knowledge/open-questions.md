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
- Raised: 2026-08-10 (repository initialization).
- Partially resolved: 2026-08-10. A first manual snapshot exists
  (`evaluation/benchmarks/2026-08-brl-risk-free.md`, Selic 14% a.a. via
  WebSearch, cross-checked across 3 sources) and was used as the hurdle rate
  in the first opportunity-cycle decision
  (`journal/decisions/DEC-20260810-A032A0.md`).
- Why it still matters: still manual and unautomated, will go stale. The
  Yahoo Finance MCP added this session covers US equities, not a BCB/B3/Selic
  feed — a different source is needed to automate this specific benchmark.
- What would resolve it fully: `ROADMAP.md` Phase 1 data-integration work —
  find and wire up a repeatable BCB/Tesouro Direto data source instead of
  re-searching the web manually each time.

### How should a critical-decision approval be authenticated as genuinely human?
- Raised: 2026-08-10 (Phase 0 readiness audit, `journal/reviews/phase0-readiness.md`).
- Partially resolved: 2026-08-10. The human owner confirmed only they have
  access to the operating machine and accepted the interactive-session
  convention as sufficient for now, with the explicit intent to strengthen it
  later if the experiment proceeds. Implemented `approve-decision` /
  `reject-decision` (`src/capital_agent.py`), which record the human's
  literal statement plus a timestamp, and documented the convention's scope
  in `CRITICAL_DECISIONS.md` "Approval authentication" and `HUMAN_GATES.md`
  Gate H7.
- Why it still matters (not fully resolved): the underlying limitation is
  unchanged — nothing cryptographically distinguishes a human-typed
  authorization from an AI-fabricated one, since both edit the same file with
  the same access. What changed is that this is now an *accepted, documented,
  human-confirmed* trade-off scoped to "single-operator machine, interactive
  session only," rather than a silent gap. It explicitly does **not** cover
  unattended/scheduled sessions (`scheduler/`) — there is no human present to
  type an authorization in that case, so this convention provides no
  protection there.
- What would resolve it fully: before any Human Execution Request is
  triggered by an unattended/scheduled session (Phase 2+ with the scheduler
  actually initiating AI sessions rather than just queuing tickets for a
  human-launched one), replace or supplement this with a stronger mechanism —
  a human-only interactive confirmation the AI cannot script around, a signed
  approval the AI never has the key for, or an approval channel entirely
  outside the repository. Revisit this decision if the operating machine ever
  gains additional users/access.

### Does the Yahoo Finance MCP actually work end to end on this machine?
- Raised: 2026-08-10 (`SYS-20260810-C76D60`, `.mcp.json` added, human-approved
  via `APR-20260810-7BFB0C`).
- Why it matters: `.mcp.json` was configured mid-session, so the tool is not
  callable until the next Claude Code session reconnects. The npm package
  (`yahoo-finance-mcp-server`) shells out to a local Python `yfinance`
  runtime that was not separately confirmed installed on this machine
  (only that Python 3.12 itself is present).
- What would resolve it: in the next session, call one of its tools (e.g. a
  quote lookup) and confirm it returns real data rather than an error. If it
  fails due to a missing `yfinance` install, that is a `pip install yfinance`
  fix, not a governance issue — but should be logged either way (a
  post-mortem if it silently failed for a while, or just closing this
  question if it works cleanly).

### Starter-kit digital product tied to marcelo-goncalves-blog — disregarded, not just paused
- Raised: 2026-08-10. Superseded: 2026-08-10.
- Status: **out of scope entirely for now**, not merely blocked. Human owner
  instructed: "vamos desconsiderar a minha plataforma por enquanto. temos
  que começar esse projeto do zero. se pudermos contar com ela no futuro, eu
  aviso aqui" — i.e. do not plan around that project at all; the growth
  vector must be built from zero, independent of it. If it ever becomes
  available as an asset, the human owner will say so explicitly in this
  same channel — do not proactively revisit or ask.
- Why it matters: `DEC-20260810-875930` is now superseded on this specific
  point by `DEC-20260810-<from-scratch-pivot>` (see `journal/decisions/`).
  A future AI session should not treat the blog as a resource to build on
  unless the human owner has said so in the interim.
- What would resolve it: only an explicit future signal from the human
  owner in conversation. Nothing to do until then.

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

### What execution adapter(s) should Phase 3 target first?
- Raised: 2026-08-10 (repository initialization / Context Management System setup)
- Why it matters: `ARCHITECTURE.md` lists execution adapters as a future component
  but none exists yet; the choice affects which broker/exchange API integration
  and Gate H4 approval package gets prepared first.
- What would resolve it: completion of Phase 1 opportunity research showing which
  category of opportunity (listed assets, crypto, commercial experiment, etc.)
  has the strongest evidence.

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

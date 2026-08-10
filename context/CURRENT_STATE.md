# Current State

Generated deterministically by `python src/capital_agent.py update-context`.
Do not hand-edit; edit the underlying sources (ledger, config, experiments, journal) and regenerate.

- Generated at: 2026-08-10T10:22:31-03:00
- Repository/policy version: 0.1
- Phase: 0 (research/proposals/simulations only; see `ROADMAP.md`)

## Capital (verified from data/ledger.csv)

- Initial capital: BRL 1000.00
- Verified cash: BRL 1000.00
- Verified equity floor (cash only; Phase 0 does not mark other positions): BRL 1000.00
- Capital invested (market/experiment buckets): not yet implemented (no bucket-level ledger breakdown)
- Capital committed (open experiment budgets not yet spent): not yet implemented
- Drawdown from equity high-water mark: not yet implemented (no high-water-mark tracking yet)
- Ledger entries: 1

## Execution tier & limits (config/policy.json)

- Execution tier: 0
- Live execution enabled: False
- Max single live allocation: BRL 100.00
- Min cash reserve: BRL 500.00
- Hard drawdown freeze: 20% of equity

## Positions

None recorded. Phase 0 has no live execution adapter.

## Active experiments

None.

## Archived experiments

None.

## Pending critical-decision approvals (approvals/pending/)

None.

## Recent decisions (journal/decisions/)

None recorded yet.

## Recent system changes (journal/system_changes/)

- SYS-20260810-D62661

## Risks

- No live execution adapter exists yet; Phase 0 caps exposure to zero live risk.
- No historical equity high-water mark is tracked yet, so drawdown cannot be computed.

## Hypotheses

None recorded yet. See `context/knowledge/open-questions.md`.

## Benchmarks

Not yet implemented. See `INVESTMENT_POLICY.md` section 7.

## Data limitations

- No market/macro data feed connected yet (Phase 1 work).
- Equity floor counts verified ledger cash only; no marked positions or receivables exist yet.

## Next actions (from ROADMAP.md Phase 0)

- Configure the chosen AI execution environment.
- Run Phase 0 readiness audit (`PHASE0_READINESS_PROMPT.md`).
- Run first opportunity research cycle.

## References

- `START_HERE.md`, `CONTEXT_MANAGEMENT.md`
- `AI_OPERATING_MANUAL.md`, `INVESTMENT_POLICY.md`, `CRITICAL_DECISIONS.md`, `EVALUATION_CRITIC_SYSTEM.md`, `SYSTEM_EVOLUTION.md`, `HUMAN_GATES.md`, `ARCHITECTURE.md`, `ROADMAP.md`

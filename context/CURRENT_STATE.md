# Current State

Generated deterministically by `python src/capital_agent.py update-context`.
Do not hand-edit; edit the underlying sources (ledger, config, experiments, journal) and regenerate.

- Generated at: 2026-08-10T16:30:55-03:00
- Repository/policy version: 0.2
- Operating phase: 0 (research/proposals/simulations only; see `ROADMAP.md`)
- Custody invariant: only the human owner may move real money; the Capital Agent has no financial write capability at any phase (`AI_OPERATING_MANUAL.md`).

## Capital (verified from data/ledger.csv)

- Initial capital: BRL 1000.00
- Verified cash: BRL 804.35
- Reserve instruments booked (data/reserve_assets.json, e.g. Tesouro Selic, conservatively valued at cost): BRL 195.65
- Verified equity floor (cash + booked reserve instruments; other market positions still not marked): BRL 1000.00
  - RA-20260810-1224BE: Tesouro Selic — BRL 195.65 (execution HER-20260810-544DBF)
- Capital invested (market/experiment buckets): not yet implemented (no bucket-level ledger breakdown)
- Capital committed (open experiment budgets not yet spent): not yet implemented
- Drawdown from equity high-water mark: not yet implemented (no high-water-mark tracking yet)
- Ledger entries: 2

## Execution tier & limits (config/policy.json)

- Execution tier (operating phase): 0
- Human Execution Requests in active use: False
- Autonomous financial execution permitted: False (hard invariant, always False)
- Max single live allocation: BRL 100.00
- Min cash reserve: BRL 500.00
- Hard drawdown freeze: 20% of equity

## Positions

None recorded. No financial write adapter exists or ever will under this architecture; positions only change via confirmed Human Execution Requests.

## Pending Human Execution Requests (execution/human_requests/pending/)

None. No financial execution is currently waiting on the human owner.

## Active experiments

None.

## Archived experiments

1 archived.

## Pending critical-decision approvals (approvals/pending/)

None.

## Recent decisions (journal/decisions/)

- DEC-20260810-451C32
- DEC-20260810-875930
- DEC-20260810-A032A0
- DEC-20260810-C5EA4F

## Recent system changes (journal/system_changes/)

- SYS-20260810-8E8A9C
- SYS-20260810-A54ECC
- SYS-20260810-B3962E
- SYS-20260810-BD6581
- SYS-20260810-C76D60
- SYS-20260810-C894F1
- SYS-20260810-D62661
- SYS-20260810-E87857
- SYS-20260810-EBED61
- SYS-20260810-F9CEAA

## Risks

- No historical equity high-water mark is tracked yet, so drawdown cannot be computed.
- No scheduler run history yet; autonomous operation cadence is not yet exercised in production.

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

# Summaries

Progressive summarization layer, per `CONTEXT_MANAGEMENT.md`:

```
events and decisions
       |
       v
weekly/  (per-week rollup of decisions, experiments, system changes)
       |
       v
monthly/ (per-month rollup of weekly summaries + system audits)
       |
       v
strategies/ (consolidated knowledge per strategy/opportunity category,
             feeding context/knowledge/)
```

A summary never substitutes for or deletes the original evidence in `journal/`,
`experiments/`, `approvals/` or `data/ledger.csv`. Summaries always cite the
records they roll up so the chain back to evidence is never broken.

## Naming

- `weekly/YYYY-WW.md` (ISO week)
- `monthly/YYYY-MM.md`
- `strategies/<strategy-or-category-slug>.md`

## Current state

No summaries exist yet. The repository has one ledger entry (initial capital) and
no decisions, experiments or system changes to summarize as of this writing
(Phase 0, 2026-08-10). Start writing weekly summaries once at least one week of
activity has accumulated — do not summarize an empty week.

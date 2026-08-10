# Recurring Errors

Tracks failure patterns that have shown up more than once, per
`SYSTEM_EVOLUTION.md` principle "improve from evidence, not novelty" and
`EVALUATION_CRITIC_SYSTEM.md` principle 6 ("repeated failure patterns generate
system-improvement proposals").

An error only qualifies as "recurring" after it has been observed at least twice
with an evidentiary link (decision record, post-mortem, audit, or test failure).
A single incident belongs in a post-mortem, not here.

## Format

```
### <short title>
- First observed:
- Occurrences: <count + links>
- Pattern:
- System-improvement proposal: <link to journal/system_changes/ entry, if any>
```

## Entries

### Sourcing business-model candidates from generic "top N ideas" web searches
- First observed: 2026-08-10
- Occurrences: 3 — see `context/knowledge/rejected-opportunities.md`
  ("Generic AI agent governance starter kit", "Generic Brazilian
  personal-finance/budget spreadsheet", "Brazilian investment capital-gains
  / IR calculator tool"), all sourced via generic `WebSearch` queries like
  "best micro-SaaS ideas 2026" and all killed for the same underlying
  reason: they were crowded by competitors (free open-source, established
  commercial players, or a free government tool respectively).
- Pattern: an idea easy enough to surface in a two-second generic search is,
  by construction, easy enough that others found and built it first. This
  method is useful for confirming a *category* is viable (digital products
  sell; personal-finance tools sell) but systematically bad at finding an
  actual *gap* within that category.
- System-improvement proposal: none yet (a process/method fix, not a code
  fix). Next opportunity-research pass should weight narrow,
  complaint-sourced or first-hand-observed pain points above listicle
  brainstorming, and check competitive crowding *before* investing search
  effort in fleshing out an idea's business case, not after.

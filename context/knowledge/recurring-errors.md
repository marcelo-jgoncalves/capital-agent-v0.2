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

### Assuming "dated event" sourcing is uncrowded regardless of topic type
- First observed: 2026-08-10 (NFS-e MEI guide, `DEC-20260810-C5EA4F`)
- Occurrences: 2 — the NFS-e MEI guide (regulatory) was genuinely uncrowded
  in PT-BR; three non-regulatory "dated event" candidates tried afterward
  per that decision's own revisit condition (Microsoft Publisher
  discontinuation, Mercado Livre 2026 fee changes, WhatsApp Business API
  2026 pricing change — all in `context/knowledge/rejected-opportunities.md`)
  were all found already crowded by commercially-motivated PT-BR blogs
  within the same research pass.
- Pattern: "sourced from a live, dated event" (the fix proposed after the
  first three listicle-sourced rejections) is necessary but not sufficient.
  What actually made NFS-e uncrowded was that correctly answering it
  required primary-source legal-text verification (Resolução CGSN 169/22
  vs. 189/2026, municipal-vs-national ISS penalties) that most secondary
  blogs got wrong or skipped — a real interpretive-difficulty moat.
  Platform/vendor policy changes (marketplace fees, API pricing, software
  EOL) have no equivalent moat: the facts are simple and one press release
  away, so logistics/ERP/API-tooling vendors with an SEO/lead-gen incentive
  cover them within days of announcement, every time. "Dated + narrow" is
  not the differentiator; "dated + narrow + genuinely hard to correctly
  interpret from primary sources" is.
- System-improvement proposal: none yet. Next pass should filter dated-event
  candidates by an explicit question — "does answering this correctly
  require reconciling primary sources that conflict or are commonly
  misread?" — before spending search budget on competitive-crowding checks,
  rather than treating recency/narrowness alone as a good-enough filter.

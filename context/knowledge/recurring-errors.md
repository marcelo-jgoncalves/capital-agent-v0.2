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

### System changes merged without a journal/system_changes/ record or index entry
- First observed: 2026-08-13 (SYS-20260813-CODEX)
- Occurrences: 3 — `SYS-20260813-CODEX` (Codex CLI provider integration, PR
  #3), the business-integration hardening pass (PR #5), and the
  ledger-integrity fix pass (PR #6) were all implemented, tested, and
  merged with a readiness/audit report written under `journal/reviews/`,
  but none produced the corresponding `journal/system_changes/SYS-*.md`
  record or `context/indexes/system-changes.json` entry required by
  `CONTEXT_MANAGEMENT.md`'s capture -> classify -> persist -> index
  lifecycle. Discovered during a routine "update context per our rules"
  request, not by the implementing sessions themselves. Backfilled as
  `SYS-20260813-BIZHARDEN` and `SYS-20260813-LEDGERINTEGRITY`, and the
  missing index entries added for all three.
- Pattern: a session under time/scope pressure to implement a large prompt
  (adapter, schema, tests, docs) reliably does the readiness-report step
  (it's usually explicitly requested in the prompt's own closing section)
  but treats the `journal/system_changes/` record as optional bookkeeping
  and skips it once the "real" work and tests are done — even though
  `SYSTEM_EVOLUTION.md` and `CONTEXT_MANAGEMENT.md` both treat it as
  mandatory for any material architectural change. A readiness report
  describes whether the change is *ready*; a system-change record is what
  makes the change *findable and auditable* by a future session reading
  `context/CURRENT_STATE.md` — they are not substitutes for each other.
- System-improvement proposal: none yet (a process fix, not a code fix).
  Any session implementing a Class B/C system change should treat writing
  the `journal/system_changes/SYS-*.md` record and its
  `context/indexes/system-changes.json` entry as part of Definition of
  Done, in the same breath as running the test suite — not as a separate
  "context management" cleanup pass done later by someone else.

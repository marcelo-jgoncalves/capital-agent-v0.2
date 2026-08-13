# Rejected Opportunities

Log of opportunities that were considered and rejected, so they can be reviewed
later to detect excessive caution (`EVALUATION_CRITIC_SYSTEM.md` principle 7).
Rejection is a decision like any other and should be traceable to a decision
record when the evaluation was material enough to warrant one.

## Format

```
### <short title>
- Date:
- Category:
- Reason for rejection:
- Decision record (if any): <path under journal/decisions/>
- Revisit condition: <what would change the answer>
```

## Entries

### Generic "AI agent governance starter kit" digital product
- Date: 2026-08-10
- Category: digital product / software
- Reason for rejection: considered as a from-scratch, low-labor digital
  product candidate (leveraging the Capital Agent's own governance patterns
  — custody invariant, Human Execution Request lifecycle, criticality
  classification — generalized into a sellable template, independent of
  `marcelo-goncalves-blog` per the human owner's instruction to disregard
  that project for now). A single `WebSearch` pass found the space already
  has multiple free, well-resourced, actively maintained open-source
  competitors covering the same ground more comprehensively — Microsoft's
  Agent Governance Toolkit (15+ framework support, OWASP Agentic Top 10
  coverage), Galileo's Agent Control, Superagent, NVIDIA NeMo Guardrails,
  Meta's LlamaGuard. A narrow, single-author, finance-flavored variant of
  this would compete against free offerings backed by major companies —
  weak commercial thesis on its face, rejected before any build effort was
  spent (killed at the paper/research stage, per
  `AI_OPERATING_MANUAL.md`'s "prefer inaction when expected value does not
  justify risk, cost or uncertainty").
- Decision record: `journal/decisions/` — recorded inline in the
  from-scratch pivot decision rather than a dedicated `DEC-` record, since
  no capital or material effort was ever committed to it.
- Revisit condition: only if a genuinely differentiated angle emerges (e.g.
  a niche this specific project's evidence base — real financial-custody
  governance, tested and journaled end to end — actually demonstrates that
  the general frameworks above don't cover). Not planned; noted here so a
  future cycle doesn't re-research the same dead end from zero.

### Generic Brazilian personal-finance/budget spreadsheet (infoproduto)
- Date: 2026-08-10
- Category: digital product (template/spreadsheet)
- Reason for rejection: `WebSearch` confirmed the category is real and
  sellable on Hotmart/Eduzz/Kiwify (Brazilian infoproduct platforms,
  R$30bi+ lifetime volume on Hotmart alone), but "planilha de controle
  financeiro" is one of the most common, commoditized beginner-infoproduct
  niches in that market (a real competing product, "Planilha de Controle
  Financeiro 2026" by an established seller, surfaced in the very first
  search result). No differentiated angle identified — rejected as too
  generic/saturated to expect to stand out without a much more specific
  hook. Killed at research stage, no build effort spent.
- Decision record: none dedicated; logged here only.
- Revisit condition: only with a genuinely narrow, differentiated sub-niche
  within personal finance, not the generic budget-tracker framing.

### Brazilian investment capital-gains / IR (income tax) calculator tool
- Date: 2026-08-10
- Category: digital product / tool
- Reason for rejection: considered because it matches a real demonstrated
  capability (this project's own ledger/tax-category logic) and initially
  looked narrower than the generic finance-spreadgsheet idea. `WebSearch`
  found the space is crowded by established players (Investidor10, Akeloo,
  Nomad Global) *and*, more decisively, by a **free official tool**: the
  Receita Federal + B3's "ReVar" calculator for renda-variável capital
  gains tax. Competing against a free government-backed tool in the same
  narrow niche is a very weak position. Also carries real legal/regulatory
  caution (tax-calculation tools brush against `CRITICAL_DECISIONS.md`'s
  "uncertain legal classification" trigger) that would need careful
  disclaimer/positioning even if the market gap existed. Killed at research
  stage, no build effort spent.
- Decision record: none dedicated; logged here only.
- Revisit condition: only if a specific sub-case is found that ReVar and
  the established players genuinely don't cover well (e.g. a specific
  instrument type or workflow gap) — not yet researched.

### Microsoft Publisher discontinuation (Oct 2026) "what to do next" guide
- Date: 2026-08-10
- Category: digital product / guide (non-regulatory, tried per the NFS-e
  standby decision's revisit condition — a lower-liability, purely
  how-to/organizational topic with no compliance stakes)
- Reason for rejection: real, dated, narrow-audience event (Microsoft
  Publisher support ends 2026-10-13, affecting small businesses/nonprofits/
  schools with archived `.pub` files) that at first looked like a good
  non-regulatory analog to the NFS-e pattern. `WebSearch` found the topic is
  already crowded, including in Portuguese specifically: Brazilian/PT
  outlets (`anamid.com.br`, `rz1.com.br`, `tecnoblog.net`, `tugatech.com.pt`)
  have already published "o que fazer" guides, and the migration-tool
  vendor itself (Markzware, via `pt.markzware.com`) already runs a
  Portuguese-language guide plus paid conversion products (DesignMarkz,
  MarkzPortal) aimed at exactly this audience. Unlike NFS-e (a same-country
  regulatory change secondary PT-BR sources hadn't organized well), this is
  a single global vendor announcement that gets translated/covered
  everywhere immediately — structurally hard to find an uncovered gap in.
  Killed at research stage, no build effort spent.
- Decision record: none dedicated; logged here only.
- Revisit condition: only if a sub-angle is found that existing PT-BR
  coverage and the vendor's own tools don't address (e.g. a specific
  vertical's `.pub` template workflow) — not researched further.

### Mercado Livre 2026 fee/rule changes "how to adapt" guide
- Date: 2026-08-10
- Category: digital product / guide (non-regulatory, platform-policy)
- Reason for rejection: real, dated, narrow-sounding event (Mercado Livre
  changed Full/shipping fee structure starting March 2026), but `WebSearch`
  found it is already extensively covered by commercially-motivated PT-BR
  blogs (tecnospeed, upseller, conectenvios, base.com, gosmarter, ferax,
  eblue) — logistics/ERP vendors write this content routinely as lead-gen
  for their own tools, so any real fee change gets a "how to adapt" guide
  within days. No gap found. Killed at research stage.
- Decision record: none dedicated; logged here only.
- Revisit condition: none identified.

### WhatsApp Business API 2026 pricing-change guide
- Date: 2026-08-10
- Category: digital product / guide (non-regulatory, platform-policy)
- Reason for rejection: same crowding pattern as Mercado Livre above —
  `WebSearch` found multiple PT-BR vendor/agency blogs (socialhub, nexe,
  chatlabs, digisac, digitro, zuper, aleguimas) already publishing detailed
  breakdowns of the Oct 2026 per-message pricing change, several from
  companies selling WhatsApp API tooling directly. Also, the change turns
  out to not even affect the mass of small businesses (those using the free
  WhatsApp Business app, not the paid API), shrinking the addressable
  audience further. Killed at research stage.
- Decision record: none dedicated; logged here only.
- Revisit condition: none identified.

## Pattern noticed across these three rejections

All three candidates were sourced the same way: generic `WebSearch` for
"best [category] ideas," which surfaces exactly the ideas most likely to
already be crowded, precisely because they were easy enough to find in a
two-second search that many others found them too. Broad listicle-sourced
brainstorming is a weak method for finding an under-served niche; it is
good at confirming a *category* is real (personal finance tools sell; solo
digital products sell) but bad at finding a specific *gap* within it. Next
research pass should shift method: look for narrow, specific, recurring
complaints (e.g. in forums/communities for a target audience) rather than
"top 10 ideas" listicles, even though that is slower.

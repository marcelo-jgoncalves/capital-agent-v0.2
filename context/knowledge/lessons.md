# Lessons

Durable knowledge distilled from post-mortems (`journal/postmortems/`) and system
audits (`journal/audits/`). Each entry must cite the artifact(s) it was derived from.

Not every observation becomes a lesson. A lesson belongs here only after the chain
`observation -> decision -> prediction -> outcome -> post-mortem -> lesson` has
actually been walked, per `EVALUATION_CRITIC_SYSTEM.md` Level 2. Do not pre-populate
this file with generic advice that has no evidentiary source.

## Format

```
### <short title>
- Date:
- Source: <path to post-mortem/audit>
- Lesson:
- Applies to:
```

## Entries

### Check candidate business models against human-labor-minimization, not just capital/policy checks
- Date: 2026-08-10
- Source: `journal/decisions/DEC-20260810-875930.md` (killed
  `experiments/archive/EXP-20260810-1F7147.json`, a personally-delivered
  consulting micro-offer that passed every capital/policy/criticality check
  but violated the human owner's actual goal of minimal *personal
  intervention*, not just minimal financial exposure).
- Lesson: `AI_OPERATING_MANUAL.md`'s responsibility split (agent recommends,
  human custodies/executes/approves) already implies candidate business
  models should not require the human's ongoing personal labor to deliver
  value — but this constraint is easy to satisfy on paper (policy checks,
  criticality classification) while still failing it in substance, because
  nothing in `policy_check_proposal`/`classify_critical` checks *who does
  the ongoing work*. A capital-efficient, policy-compliant, non-critical
  proposal can still be wrong if it quietly assumes the human becomes a
  service provider.
- Applies to: every future business-model comparison in a decision record —
  explicitly ask "who performs the ongoing work once this launches," not
  only "does this pass policy and capital-efficiency checks."

### Fact-verification rigor does not substitute for the human owner's own domain comfort on regulated content
- Date: 2026-08-10
- Source: `journal/decisions/DEC-20260810-C5EA4F.md` Addendum 5 (NFS-e/MEI
  guide put on standby by the human owner after a complete, primary-source-
  verified draft was written — not rejected on evidence, but on the human
  owner's own risk tolerance: "não tenho conhecimentos suficientes para
  garantir que não cometeríamos erros no conteúdo").
- Lesson: for content published under the human owner's identity in a
  regulated/compliance-adjacent domain (tax, legal, financial obligations
  affecting third parties), the agent's careful primary-source verification
  narrows error risk but does not, by itself, clear the bar for publishing
  — the human owner's own subject-matter comfort is a separate, necessary
  condition, because they carry the identifiable legal/reputational
  exposure, not the agent. This is not a reason to avoid regulated-content
  candidates outright, but it means this category has a materially higher
  bar to actually reach publication than a purely organizational/how-to
  product with no compliance stakes would.
- Applies to: weigh this explicitly, before investing drafting effort,
  when a candidate opportunity involves publishing compliance/regulatory
  content — flag the domain early and gauge risk tolerance sooner, rather
  than only surfacing it once a full draft already exists.

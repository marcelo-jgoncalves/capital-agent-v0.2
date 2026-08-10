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

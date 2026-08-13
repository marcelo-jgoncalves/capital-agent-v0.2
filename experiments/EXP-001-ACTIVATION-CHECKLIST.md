# EXP-001 Activation Gate Checklist

Status of EXP-001: **PLANNED / NOT ACTIVATED**
(`experiments/active/EXP-20260813-62C22E.json`, `code: "EXP-001"`).

This checklist exists so activation is deliberate and evidenced, never
inferred. Do not check an item unless the underlying evidence actually
exists in the repository. An empty/unchecked item is the honest default —
never mark it done to make the checklist look more complete than reality.

Moving EXP-001 from `PLANNED` to `READY_FOR_ACTIVATION` requires every item
below to be true and evidenced. Moving from `READY_FOR_ACTIVATION` to
`ACTIVE` additionally requires an explicit human activation record (not an
inference from any of the items below being complete) — see
`AI_OPERATING_MANUAL.md` and `CRITICAL_DECISIONS.md`. Publishing the
platform, finishing development, or completing this checklist does **not**,
by itself, activate the experiment.

## Platform readiness
- [ ] site deployable to a production environment
- [ ] blog functional (publish, list, view)
- [ ] production environment ready
- [ ] HTTPS
- [ ] domain configured by the owner (owner-provided; see `INVESTMENT_POLICY.md` section 14 — never a Capital Agent cost)
- [ ] basic security review done
- [ ] backups/recovery appropriate
- [ ] monitoring in place
- [ ] analytics instrumentation in place
- [ ] conversion tracking in place
- [ ] contact/lead capture in place
- [ ] privacy/legal essentials identified
- [ ] performance acceptable
- [ ] SEO technical baseline (sitemap, robots, canonical, metadata, structured data where appropriate)
- [ ] error monitoring in place

## Commercial readiness
- [ ] value proposition documented
- [ ] target audience hypotheses documented
- [ ] service/product proposition(s) documented
- [ ] CTA and lead path defined
- [ ] attribution model defined (see `revenue_attribution_states` in the EXP-001 record)
- [ ] success metrics finalized (currently placeholder in the EXP-001 record)
- [ ] initial content strategy documented

## Capital Agent readiness
- [x] ledger exists and is reconciliation-gated (`data/ledger.csv`, `ARCHITECTURE.md`)
- [x] accounting attribution rules exist (`INVESTMENT_POLICY.md` section 14)
- [x] scheduler exists (`scheduler/`, `src/scheduler.py`)
- [x] context management exists (`CONTEXT_MANAGEMENT.md`, `context/`)
- [x] critic system exists (`EVALUATION_CRITIC_SYSTEM.md`)
- [x] criticality policy exists (`CRITICAL_DECISIONS.md`)
- [x] approval flow exists (`approvals/`)
- [x] Human Execution Request flow exists (`execution/`)
- [x] experiment registry exists (`experiments/`)
- [x] audit logging exists (`journal/`)
- [x] knowledge capture exists (`context/knowledge/`)
- [x] AI provider adapter exists (`adapters/ai_providers/`)
- [x] automated test suite exists and passes (`tests/`)

## Human activation

- [ ] Human owner has explicitly reviewed this checklist and recorded
      activation (date, statement) — never inferred from technical
      completion, publication, or the passage of time.
- [ ] `activation.activated` set to `true` and `activation.activation_date`
      populated in the EXP-001 record, and `state` moved to `ACTIVE`, only
      as a direct consequence of that human record.
- [ ] Success metric, failure criteria, kill condition and review frequency
      finalized in the EXP-001 record before activation (they are currently
      placeholders).

## What activation does NOT do automatically

- It does not grant the Capital Agent any financial write authority.
- It does not retroactively attribute pre-activation platform costs or the
  domain to the Capital Agent (`INVESTMENT_POLICY.md` section 14).
- It does not authorize unlimited public content; publication remains
  governed by `CRITICAL_DECISIONS.md`.
- It does not start counting performance before `activation_date`.

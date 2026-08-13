# DEC-20260813-HARDENING-PRODUCT — Product decisions from final hardening pass

Source: `prompt-hardening-final-capital-agent-v0.2.md`, sections 7 and 8.
Status: **PENDING OWNER DECISION** on the specific evolutions described below.
No behavior change was made beyond what is already the safest current
behavior; nothing here relaxes any policy.

---

## 1. `--admin-confirm` / `--reason` (section 7)

See `backlog/ADR-001-admin-confirm-ledger-action.md` for the full risk
analysis and options considered. Summary: current behavior (explicit
`--admin-confirm` flag + mandatory `--reason` + standalone audit record under
`journal/admin_ledger_actions/`) is preserved unchanged. Recommendation is
Option 3 (tighten the `--reason` wording/authentication-honesty convention to
match `approve-decision --human-statement`) now, with the fuller two-step
`Admin Ledger Action` pipeline (generated id → explicit confirmation →
one-time execution → audit) deferred until administrative actions become
frequent enough to justify it. No code changes made under this heading; owner
authorization required before any change.

---

## 2. `BusinessSignal` / `BusinessObservation` naming (section 8)

### Current state

Two of the three layers in the preferred architecture already exist as
distinct entities in `src/business_integration.py`:

- `create_business_observation()` → `ExternalBusinessObservation`-equivalent
  (normalized external fact; see `schemas/business_observation.schema.json`).
- `create_business_signal_entity()` → `BusinessSignal` (interpreted pattern;
  see `schemas/business_signal.schema.json`,
  `schemas/business_signal_pattern.schema.json`).
- `promote_business_signal_to_opportunity()` produces an
  `opportunity_candidate_ref` (a reference/id), but there is **no dedicated
  `OpportunityCandidate` entity/schema/file** yet — the "hypothesis that
  merits economic evaluation" is currently represented only as a string
  reference on the promoted signal, not as its own persisted, schema-validated
  record.

This is closer to the preferred architecture than the prompt's "Problema"
section implies (the Observation/Signal split was already done in an earlier
hardening pass — see `backlog/platform-integration.md`, "2026-08-13 hardening
pass" note). The remaining naming debt is narrower than a full rename.

### Impact assessment (schemas, filenames, dirs, IDs, functions, tests, docs)

Promoting `OpportunityCandidate` to a full entity would require: a new
`schemas/opportunity_candidate.schema.json`, a `create_opportunity_candidate()`
function and matching persisted-record directory, ID prefix
(`OPP-YYYYMMDD-XXXXXX`, consistent with the `OPP-001` style already used in
tests), migration of existing `opportunity_candidate_ref` values into real
records, and updated tests/docs in `EXTERNAL_INTEGRATION.md`.

### Recommendation (not a decision — owner must confirm)

Low risk to *add* (new entity, additive schema, no rename of existing
`BusinessSignal`/`BusinessObservation` — those names are already correct and
unambiguous), but it is new scope beyond "close remaining naming debt", and
building it speculatively without a real second consumer (e.g. an economic
evaluation workflow that reads `OpportunityCandidate` records) risks
"speculative architecture", which section 4/9's spirit also warns against.

Marked **PENDING**, tracked as **Backlog item BIZNAME-001** (P2): implement
`OpportunityCandidate` as a full persisted entity only when a concrete
consumer needs it (e.g. EXP-001-successor economic evaluation), reusing
`opportunity_candidate_ref` as the migration key. Until then,
`BusinessSignal`/`BusinessObservation` naming is considered **resolved**
(no ambiguity, no dual-naming), and `OpportunityCandidate` is documented here
as an intentionally deferred, not accidental, gap.

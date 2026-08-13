# System Change: Platform-as-first-asset restructuring (EXP-001, domain/sunk-cost exclusion, PLANNED activation gate) — closeout

- Date/time: 2026-08-13T19:30:00-03:00
- Change ID: SYS-20260813-PLATFORM
- Change class: B (materially changes how the system reasons about its
  first operational experiment and cost attribution; does not touch
  financial authority)
- Status: PROPOSED_AUTONOMOUSLY_ALLOWED

## Problem observed

`prompt-reestruturacao-capital-agent-plataforma.md` required the Capital
Agent to formally represent an existing, owner-provided business platform
(institutional site + blog) as its first planned operational experiment
(EXP-001), while guaranteeing three invariants: (1) the experiment has not
started — the system remains in PREPARATION and the performance clock has
not begun; (2) the domain and all pre-activation platform development are
owner sunk costs, never debited from the BRL 1,000 experiment or counted in
EXP-001's cost; (3) activation requires an explicit, non-inferred human
signal. Most of this had already been implemented earlier in the working
tree (`INVESTMENT_POLICY.md` section 14, `experiments/active/EXP-20260813-
62C22E.json`, `experiments/EXP-001-ACTIVATION-CHECKLIST.md`,
`tests/test_platform_exp001.py`), but two required deliverables from the
prompt's own closing sections were missing: the readiness report
(`journal/reviews/platform-integration-restructure-readiness.md`) and this
system-change record, without which the restructuring was not auditable as
a completed, governed change.

## Evidence

Full repository read: `START_HERE.md`, `AI_OPERATING_MANUAL.md`,
`INVESTMENT_POLICY.md`, `SYSTEM_EVOLUTION.md`, `ARCHITECTURE.md`,
`HUMAN_GATES.md`, `CRITICAL_DECISIONS.md`, `ROADMAP.md`, `README.md`,
`experiments/`, `context/`, `config/*.json`, `src/capital_agent.py`,
`tests/`. Grep audit for `live execution|autonomous execution|broker
adapter|exchange adapter|write credential|Tier 3|automatic order|bounded
autonomous financial execution|withdrawal|Claude|Codex|ChatGPT` found no
live contradictions outside deliberately defensive/prohibitive language
(see `journal/reviews/platform-integration-restructure-readiness.md`
section 3 for the full result). `python -m unittest discover -s tests`:
64/64 passing.

## New risks introduced

- None to financial authority: EXP-001 remains `PLANNED`, `capital_deployed_
  brl: 0.0`, `activation.activated: false`. No code path in this change
  sets those fields to active/deployed values.
- A duplicate EXP-001 record was briefly created under a different naming
  convention during this review and removed before being indexed anywhere
  else; documented in the readiness report so the deletion is auditable
  rather than silent.

## Files affected

Created:
- `journal/reviews/platform-integration-restructure-readiness.md`
- `journal/system_changes/SYS-20260813-PLATFORM.md` (this file)

Moved:
- `prompt-reestruturacao-capital-agent-plataforma.md` -> `journal/reviews/source-prompts/prompt-reestruturacao-capital-agent-plataforma.md`

No code, schema, policy or ledger file was modified by this closeout pass;
the substantive restructuring (EXP-001 record, activation checklist, domain/
sunk-cost accounting rule in `INVESTMENT_POLICY.md` section 14, and their
tests) was already present and correct in the working tree.

## Expected benefit

Completes the audit trail for the platform-as-first-asset restructuring so
a future AI operator or the human owner can verify, from repository state
alone, that the restructuring happened, what it changed, and that it passed
its own acceptance criteria — per the model-replacement test in
`SYSTEM_EVOLUTION.md` section 7.

## Rollback

Revert this commit; the deleted duplicate `experiments/active/EXP-001.json`
was never committed, so no rollback action is needed for it. No policy,
ledger or financial-authority state was touched, so rollback carries no
financial risk.

## Validation / tests performed

`python -m unittest discover -s tests` — 64 tests, 0 failures, 0 errors.
Manual grep-based contradiction audit (see readiness report section 3).
Manual verification that `data/ledger.csv` contains no domain cost and no
EXP-001-attributed entry.

## Outcome

Closeout complete. EXP-001 remains PLANNED/NOT ACTIVATED. Domain and
pre-activation platform costs remain excluded from Capital Agent accounting.
No human approval required for this record-keeping closeout (Class B,
no financial-authority change). Final readiness verdict: `NOT_READY` for
platform activation (blocked on real platform readiness and an explicit
human activation record — see readiness report section 8), which is the
correct and expected state, not a defect.

## Human approval reference

None required (Class B; no financial authority or risk-limit change).

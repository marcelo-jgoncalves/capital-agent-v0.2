# Start Here

If you are an AI system that has just been told to "read START_HERE.md and
assume the operation of the Capital Agent," this is your entry point. It is a
router, not a policy source — every fact and rule it points to lives in the
documents below, and if this file and a canonical document ever disagree, the
canonical document wins.

**The repository is the Capital Agent. You are one of possibly several AI
systems that may operate it. Nothing essential may live only in your
conversation history.**

## 0. Orient yourself in under five minutes

1. Read `context/CURRENT_STATE.md` — capital, positions, experiments, pending
   approvals, risks, next actions, generated deterministically from the
   repository's own data.
2. Read this file to the end so you know where everything else is.

## 1. Canonical policy and mandate (read before any material work)

In order, per `AI_OPERATING_MANUAL.md`:

1. `AI_OPERATING_MANUAL.md` — mission, non-negotiable behavior, decision process.
2. `INVESTMENT_POLICY.md` — capital allocation rules.
3. `HUMAN_GATES.md` — what requires a human.
4. `SYSTEM_EVOLUTION.md` — how the system may change itself.
5. `config/policy.json` — machine-enforced financial limits.
6. `config/system_governance.json` — machine-enforced change-governance rules.
7. `data/ledger.csv` — the accounting source of truth.
8. `experiments/active/` — open experiments.
9. `journal/decisions/` — recent capital decisions.
10. `journal/system_changes/` — recent system changes.

If prose and machine-readable policy conflict on a hard numeric limit, stop the
affected action and record the conflict — do not pick the more permissive
reading (`AI_OPERATING_MANUAL.md`).

## 2. Authority hierarchy

1. `HUMAN_GATES.md` and `CRITICAL_DECISIONS.md` — supersede everything else.
   Every critical decision requires explicit human authorization before
   execution; uncertain classification defaults to critical.
2. `INVESTMENT_POLICY.md` and `config/policy.json` — hard financial limits. May
   be tightened autonomously; relaxing them is always a critical, human-gated
   decision.
3. `SYSTEM_EVOLUTION.md` and `config/system_governance.json` — governs how the
   system's own implementation may change (classes A/B autonomous, C
   human-gated, D prohibited).
4. `AI_OPERATING_MANUAL.md` — the operating contract that ties the above
   together.
5. Tool-specific adapters (`CLAUDE.md`, `AGENTS.md`, anything under `adapters/`)
   — thin pointers back to the documents above. They carry no independent
   authority and must never contain policy of their own.

## 3. Current state

- `context/CURRENT_STATE.md` — the primary factual snapshot (capital, cash,
  equity floor, positions, experiments, pending approvals, risks, hypotheses,
  next actions). Regenerate with `python src/capital_agent.py update-context`
  after any change to the sources it reads from. Never hand-edit it.

## 4. Context management

- `CONTEXT_MANAGEMENT.md` — how hot/warm/cold context is organized, the
  capture-to-archive lifecycle, and the history-versus-knowledge distinction.
- `context/knowledge/` — durable lessons, recurring errors, successful
  patterns, rejected opportunities, open questions. Each entry cites the
  post-mortem/audit it came from.
- `context/indexes/` — flat JSON indexes (`decisions.json`, `experiments.json`,
  `research.json`, `system-changes.json`, `approvals.json`) for fast lookup.
  Source of truth remains the canonical files they index.
- `context/summaries/` — weekly -> monthly -> per-strategy progressive
  summaries.
- `context/snapshots/` — point-in-time captures for cold-context review.

## 5. Decisions, experiments, approvals

- `journal/decisions/` — material capital-decision records
  (`journal/DECISION_TEMPLATE.md`).
- `experiments/active/` and `experiments/archive/` — the experiment registry
  (`experiments/README.md`).
- `approvals/pending/` — critical-decision approval packages awaiting human
  authorization (`approvals/APPROVAL_REQUEST_TEMPLATE.md`,
  `CRITICAL_DECISIONS.md`).
- `data/ledger.csv` — append-only accounting ledger; `verified cash` and
  `equity floor` are always derived from it, never asserted.

## 6. Self-criticism

- `EVALUATION_CRITIC_SYSTEM.md` — pre-decision critique, outcome post-mortems,
  periodic system audits, calibration, counterfactual benchmarking.
- `journal/predictions/`, `journal/postmortems/`, `journal/audits/`,
  `evaluation/calibration/`, `evaluation/benchmarks/`, `evaluation/attribution/`.

## 7. History and system evolution

- `journal/system_changes/` — every material self-modification, classified
  A/B/C/D per `SYSTEM_EVOLUTION.md`, with rollback plan and validation.
- `ARCHITECTURE.md` — component map, execution tiers, threat model.
- `ROADMAP.md` — phases, exit criteria, milestones.

## 8. Pending work

See "Next actions" in `context/CURRENT_STATE.md` (regenerated, always current)
and open items in `context/knowledge/open-questions.md`. Do not rely on this
file for that list — it would go stale.

## 9. Tooling

- `python src/capital_agent.py status|propose|record|new-experiment|experiments|system-policy|propose-system-change|classify-decision|request-approval|update-context`
- `python -m unittest discover -s tests`

## 10. If you are a different AI than the one that last worked here

You do not need any memory of prior sessions. Everything required to continue
is in this repository. Read section 1 above in full, read
`context/CURRENT_STATE.md`, then proceed per `AI_OPERATING_MANUAL.md`'s capital
decision process or `SYSTEM_EVOLUTION.md`'s self-improvement loop, as
appropriate to the task you were given. If a task looks critical under
`CRITICAL_DECISIONS.md` and classification is uncertain, treat it as critical
and prepare — but do not execute — an approval package under
`approvals/pending/`.

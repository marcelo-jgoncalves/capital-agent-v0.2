# Start Here

If you are an AI system that has just been told to "read START_HERE.md and
assume the operation of the Capital Agent," this is your entry point. It is a
router, not a policy source — every fact and rule it points to lives in the
documents below, and if this file and a canonical document ever disagree, the
canonical document wins.

**The repository is the Capital Agent. You are one of possibly several AI
systems that may operate it. Nothing essential may live only in your
conversation history.**

## 0. The one rule that overrides everything else

**Only the human owner may access, custody or move real money.** No AI,
script, scheduler, service, integration, MCP, API or other component of this
system may buy, sell, transfer, pay, withdraw, move a bank/brokerage/exchange
account, create a real financial order, or use a credential with financial
write permission — at any phase, regardless of amount, regardless of how the
change is framed. This is a hard invariant (`AI_OPERATING_MANUAL.md`
"Custody invariant"), not a configurable tier, and it cannot be relaxed
autonomously. Your authority over real money ends at producing a **Human
Execution Request** (`execution/human_requests/`, see `ARCHITECTURE.md`); the
human executes it and confirms the result.

```text
Capital Agent: THINKS, RESEARCHES, DECIDES, CRITIQUES, LEARNS AND RECOMMENDS.
Human Owner:   CUSTODIES AND MOVES REAL MONEY AND AUTHORIZES CRITICAL DECISIONS.
```

Within that boundary, you have wide latitude: research, analyze, decide,
size, time, monitor, self-improve and recommend, all without asking the human
to make analytical calls you are equipped to make yourself.

## 1. Orient yourself in under five minutes

1. Read `context/CURRENT_STATE.md` — capital, positions, experiments, pending
   Human Execution Requests, pending approvals, risks, next actions,
   generated deterministically from the repository's own data.
2. Read `python src/scheduler.py pending-jobs` (or `state/pending_jobs.json`)
   to see what work the scheduler has already queued.
3. Read this file to the end so you know where everything else is.

## 2. Canonical policy and mandate (read before any material work)

In order, per `AI_OPERATING_MANUAL.md`:

1. `AI_OPERATING_MANUAL.md` — mission, custody invariant, non-negotiable behavior, decision process.
2. `INVESTMENT_POLICY.md` — capital allocation rules.
3. `HUMAN_GATES.md` — what requires a human, including Gate H0 (every financial execution).
4. `CRITICAL_DECISIONS.md` — decisions requiring explicit human authorization.
5. `SYSTEM_EVOLUTION.md` — how the system may change itself (and what it may never enable).
6. `ARCHITECTURE.md` — components, the Human Execution Request lifecycle, the scheduler.
6b. `EXTERNAL_INTEGRATION.md` — canonical integration model with the Editorial Platform (EXP-001): External Business Data Adapter, PII firewall, External Cash Event, experiment lifecycle, BUSINESS_SIGNAL, Publication Package/Receipt, metric provenance; see `backlog/platform-integration.md` for open platform-side dependencies.
7. `config/policy.json` — machine-enforced financial limits, including `autonomous_financial_execution_permitted` (always `false`).
8. `config/system_governance.json` — machine-enforced change-governance rules.
9. `data/ledger.csv` — the accounting source of truth. Changes only via a
   confirmed Human Execution Request, or an External Cash Event that has
   passed the full human-VERIFIED->RECONCILED pipeline
   (`EXTERNAL_INTEGRATION.md`), or a narrow explicitly-audited administrative
   entry (e.g. initial funding) -- never a bare, unattributed manual claim.
10. `execution/human_requests/pending/` — recommendations waiting on the human.
11. `experiments/active/` — open experiments.
12. `journal/decisions/` — recent capital decisions.
13. `journal/system_changes/` — recent system changes.

If prose and machine-readable policy conflict on a hard numeric limit, stop the
affected action and record the conflict — do not pick the more permissive
reading (`AI_OPERATING_MANUAL.md`).

## 3. Authority hierarchy

1. The custody invariant (section 0 above, `AI_OPERATING_MANUAL.md`,
   `HUMAN_GATES.md` Gate H0) — supersedes everything else and is not
   reachable by any of the layers below.
2. `HUMAN_GATES.md` and `CRITICAL_DECISIONS.md` — every critical decision
   requires explicit human authorization before execution; uncertain
   classification defaults to critical. Authorization is separate from
   financial execution.
3. `INVESTMENT_POLICY.md` and `config/policy.json` — hard financial limits. May
   be tightened autonomously; relaxing them is always a critical, human-gated
   decision.
4. `SYSTEM_EVOLUTION.md` and `config/system_governance.json` — governs how the
   system's own implementation may change (classes A/B autonomous, C
   human-gated, D prohibited — any financial write capability is Class D,
   unconditionally).
5. `AI_OPERATING_MANUAL.md` — the operating contract that ties the above
   together.
6. Tool-specific adapters (`CLAUDE.md`, `AGENTS.md`, `adapters/`) — thin
   pointers back to the documents above. They carry no independent authority
   and must never contain policy of their own. The reasoning/execution
   environment itself (Claude Code, Codex, Gemini CLI, a local model, or any
   other) is a replaceable AI Provider Adapter (`adapters/ai_providers/`),
   never the Capital Agent itself.

## 4. Current state

- `context/CURRENT_STATE.md` — the primary factual snapshot (capital, cash,
  equity floor, positions, experiments, pending Human Execution Requests,
  pending approvals, risks, hypotheses, next actions). Regenerate with
  `python src/capital_agent.py update-context` after any change to the
  sources it reads from. Never hand-edit it.
- `state/scheduler_state.json`, `state/pending_jobs.json` — scheduler
  run history and the current job queue (`python src/scheduler.py status` /
  `pending-jobs`).

## 5. Context management

- `CONTEXT_MANAGEMENT.md` — how hot/warm/cold context is organized, the
  capture-to-archive lifecycle, and the history-versus-knowledge distinction.
- `context/knowledge/` — durable lessons, recurring errors, successful
  patterns, rejected opportunities, open questions. Each entry cites the
  post-mortem/audit it came from.
- `context/indexes/` — flat JSON indexes (`decisions.json`, `experiments.json`,
  `research.json`, `system-changes.json`, `approvals.json`,
  `execution_requests.json`) for fast lookup. Source of truth remains the
  canonical files they index.
- `context/summaries/` — weekly -> monthly -> per-strategy progressive
  summaries.
- `context/snapshots/` — point-in-time captures for cold-context review.

## 6. Decisions, experiments, execution, approvals

- `journal/decisions/` — material capital-decision records
  (`journal/DECISION_TEMPLATE.md`).
- `experiments/active/` and `experiments/archive/` — the experiment registry
  (`experiments/README.md`).
- `execution/human_requests/{pending,completed,expired,cancelled}/` — the
  Human Execution Request lifecycle (`execution/README.md`). This is the only
  path from a recommendation to a real financial operation.
- `approvals/pending/` — critical-decision approval packages awaiting human
  authorization (`approvals/APPROVAL_REQUEST_TEMPLATE.md`,
  `CRITICAL_DECISIONS.md`). Approval unblocks a Human Execution Request; it
  never itself moves money.
- `data/ledger.csv` — append-only accounting ledger; `verified cash` and
  `equity floor` are always derived from it, never asserted. It changes via
  `capital_agent.py confirm-execution` (Human Execution Request), via
  `src/business_integration.py post_external_cash_event_to_ledger` once an
  External Cash Event has passed OBSERVED->REPORTED->VERIFIED->ATTRIBUTED->
  RECONCILED (`EXTERNAL_INTEGRATION.md`), or via a narrow, explicitly-audited
  `capital_agent.py record --admin-confirm --reason ...` for pure
  administrative bookkeeping (e.g. the initial funding event). Direct
  `record` of `revenue`/`refund`/`chargeback`/`other_external_inflow` or of
  `buy`/`sell`/`capital_out`/`expense`/`fee`/`tax` without a completed
  execution reference is refused -- see `src/capital_agent.py cmd_record`.

## 7. Self-criticism

- `EVALUATION_CRITIC_SYSTEM.md` — pre-decision critique, outcome post-mortems,
  periodic system audits, calibration, counterfactual benchmarking.
- `journal/predictions/`, `journal/postmortems/`, `journal/audits/`,
  `evaluation/calibration/`, `evaluation/benchmarks/`, `evaluation/attribution/`.

## 8. History and system evolution

- `journal/system_changes/` — every material self-modification, classified
  A/B/C/D per `SYSTEM_EVOLUTION.md`, with rollback plan and validation. Class
  D includes, unconditionally, anything granting financial write authority.
- `ARCHITECTURE.md` — component map, operating phases, threat model, Human
  Execution Request lifecycle, scheduler.
- `ROADMAP.md` — phases, exit criteria, milestones. No phase ever introduces
  autonomous financial execution.
- `journal/publication_log.md` — narrative log kept for turning this
  project into a publication/series; not canonical state or governance, not
  loaded by default, only relevant when the task is publication content.

## 9. Autonomous operation

- `scheduler/README.md`, `src/scheduler.py` — deterministic-first scheduler:
  decides what's due/fired using only repository state, queues jobs, never
  calls an AI itself. Run `python src/scheduler.py run` to check for due
  work; `pending-jobs` to see the queue; `complete-job` when you finish one.
- `config/schedules.json` — frequencies (frequent/daily/weekly/monthly/
  quarterly) and the job categories due at each.
- `config/triggers.json` — event-driven triggers and their deterministic
  checks.
- `adapters/ai_providers/` — the pluggable reasoning-provider interface; see
  section 3 above.

## 10. Pending work

See "Next actions" and "Pending Human Execution Requests" in
`context/CURRENT_STATE.md` (regenerated, always current), the scheduler's job
queue (`state/pending_jobs.json`), and open items in
`context/knowledge/open-questions.md`. Do not rely on this file for that list
— it would go stale.

## 11. Tooling

```text
python src/capital_agent.py status|propose|record|new-experiment|experiments
python src/capital_agent.py system-policy|propose-system-change|classify-decision|request-approval
python src/capital_agent.py request-execution|confirm-execution|cancel-execution|expire-execution|sweep-expired-executions|execution-requests
python src/capital_agent.py update-context
python src/scheduler.py run|status|pending-jobs|complete-job
python -m unittest discover -s tests
```

## 12. If you are a different AI than the one that last worked here

You do not need any memory of prior sessions. Everything required to continue
is in this repository. Read section 0 and 2 above in full, read
`context/CURRENT_STATE.md`, then proceed per `AI_OPERATING_MANUAL.md`'s
capital decision process or `SYSTEM_EVOLUTION.md`'s self-improvement loop, as
appropriate to the task you were given. If a task looks critical under
`CRITICAL_DECISIONS.md` and classification is uncertain, treat it as critical
and prepare — but do not execute — an approval package under
`approvals/pending/`. If a decision requires moving real money, prepare — but
never execute — a Human Execution Request under `execution/human_requests/`.

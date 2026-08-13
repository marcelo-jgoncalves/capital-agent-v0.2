# Architecture

The architecture is AI-provider neutral. Any capable AI operator may run it by
reading the repository's canonical state and instructions. The Capital Agent is
the repository plus its state, policies, context, scheduler, governance,
evaluation and history — not any particular model or tool.

## Custody invariant

**Only the human owner may access, custody or move real money.** No AI, script,
scheduler, service, integration, MCP or other system component may hold write
authority over a bank account, brokerage, exchange or payment method, or
execute a real financial operation autonomously. This is a hard invariant, not
a configurable tier — see `AI_OPERATING_MANUAL.md` and `HUMAN_GATES.md`. Every
diagram and component below is designed around it: the Capital Agent's output
toward real money is always a recommendation the human must act on, never an
executed transaction.

## Core capital loop

```text
Opportunity discovery
        |
        v
Evidence collection
        |
        v
Candidate scoring
        |
        v
Risk/policy engine
        |
        +---- reject / observe
        |
        v
Decision (journal/decisions/)
        |
        v
Criticality classification
        |
        +---- critical -> approval package -> HUMAN AUTHORIZATION
        |
        v
Does the decision require moving real money?
        |
        +---- no  -> paper/shadow tracking, commercial-experiment tracking
        |
        +---- yes -> Human Execution Request (see below)
                              |
                              v
                     WAITING_FOR_HUMAN_EXECUTION
                              |
                              v
                     HUMAN EXECUTES (outside the repository, on the real
                     platform, using credentials only the human holds)
                              |
                              v
                     Execution confirmation (human-reported, or read-only
                     reconciliation once such an adapter exists)
                              |
                              v
                        Ledger update
                              |
                              v
                         Measurement
                              |
                              v
                  Scale / hold / reduce / exit
```

Human authorization of a critical decision and human execution of a financial
operation are two distinct events. Authorization answers "may this be done at
all"; execution is the human physically doing it on a bank/brokerage/exchange
platform. Approving a critical decision never causes money to move by itself.

## Human Execution Request lifecycle

```text
ANALYSIS -> DECISION -> (critical? -> HUMAN APPROVAL) -> HUMAN_EXECUTION_REQUEST
   -> WAITING_FOR_HUMAN_EXECUTION -> HUMAN EXECUTES -> EXECUTION CONFIRMATION
   -> RECONCILIATION -> LEDGER UPDATE
```

A Human Execution Request (`execution/human_requests/`) is how the Capital
Agent asks the human to move money. It is structured, persistent and
auditable, and it moves through exactly one of these terminal states:

- `pending` — created, not yet acted on. Not counted as real equity.
- `completed` — the human reported having executed it; the ledger reflects
  what they actually reported (quantity, price, fees, timestamp), which may
  differ from the requested values.
- `expired` — its validity window passed without execution.
- `cancelled` — withdrawn before execution (thesis changed, better
  alternative found, human declined).

No component may infer `completed` from the mere existence or approval of a
request. Only an explicit human confirmation (`capital_agent.py
confirm-execution`) can transition a request to `completed` and only that
transition is allowed to touch the ledger. See `execution/README.md`.

## System-improvement loop

```text
Operational evidence / failure / friction
        |
        v
Improvement proposal
        |
        v
Change classification (A/B/C/D)
        |
        +---- C -> human approval required
        +---- D -> reject
        |
        v
Snapshot / rollback point
        |
        v
Implement smallest sufficient change
        |
        v
Tests + comparison
        |
        +---- fail -> rollback
        |
        v
Adopt + system-change journal
```

The capital loop and improvement loop are separate on purpose. Improving the
system does not automatically expand financial authority, and no
self-improvement may create a path around the custody invariant (Class D,
`SYSTEM_EVOLUTION.md`).

## Components

### 1. Canonical AI instructions

`AI_OPERATING_MANUAL.md`, routed to from `START_HERE.md`.

Vendor-neutral operating contract. Tool-specific discovery/configuration files
(`CLAUDE.md`, `AGENTS.md`, anything under `adapters/`) are thin adapters only.

### 2. Ledger

`data/ledger.csv`

Append-only accounting of external capital, expenses, revenues, buys, sells,
fees, taxes and adjustments. Every row that represents a real financial
operation must trace back to a `completed` Human Execution Request (or, for
the initial funding event, to the founding capital-in entry). Analysis,
recommendations and pending requests never write to it.

### 3. Policy engine

`config/policy.json` + checks inside `src/capital_agent.py`.

Machine-readable hard limits prevent an AI from treating prose as optional.
`config/policy.json` also declares `autonomous_financial_execution_permitted:
false` as a structural constant — see "Custody invariant" above and
`SYSTEM_EVOLUTION.md` Class D.

### 4. System-governance engine

`SYSTEM_EVOLUTION.md` + `config/system_governance.json`.

Defines which self-modifications are autonomous, human-gated or prohibited.
Any component with write authority over real money is Class D, permanently,
regardless of who proposes it.

### 5. Journals

- `journal/decisions/`: material capital and business decisions.
- `journal/system_changes/`: material system modifications.
- `journal/postmortems/`, `journal/predictions/`, `journal/audits/`:
  Evaluation & Critic System artifacts (`EVALUATION_CRITIC_SYSTEM.md`).

### 6. Experiment registry

`experiments/active/` and `experiments/archive/`.

Commercial/product/systematic experiments live independently of the financial
transaction ledger. An experiment's budget being "planned" never implies cash
has moved; a cash movement inside an experiment still goes through a Human
Execution Request like any other.

### 7. Human Execution Requests

`execution/human_requests/{pending,completed,expired,cancelled}/`

See "Human Execution Request lifecycle" above and `execution/README.md`. This
is the only sanctioned path from a Capital Agent recommendation to a real
financial operation.

### 6a. Platform-based experiments (e.g. EXP-001)

An owner-provided business platform (existing site/blog, pre-dating the
Capital Agent) may become the subject of an experiment such as EXP-001. Two
rules govern this, always:

- **Asset, not identity.** The platform keeps its own business/professional
  identity. It is never rebranded as "the Capital Agent's site," and it never
  exposes internal experiment state, balances, journals, prompts or
  decision-making mechanics. The Capital Agent acts behind the scenes
  (analysis, content research, measurement, recommendation); the platform's
  public face stays the owner's.
- **Domain and sunk costs excluded.** See `INVESTMENT_POLICY.md` section 14.
  The domain and any pre-activation platform development are owner-provided
  and never enter Capital Agent accounting. Only capital deployed after
  explicit activation, meeting the incremental-cost test, is attributable.

Public-facing publication in the owner's name is, by default, a critical
decision (`CRITICAL_DECISIONS.md`, "Identity / reputation / external
representation") until a narrow, explicit, auditable, revocable batch
authorization exists for a defined class of publication. One approved article
never authorizes future, different, or unlimited publication.

Platform-related experiments compete for capital like any other opportunity
(`INVESTMENT_POLICY.md` section 6); pre-existing the Capital Agent grants no
permanent priority.

### 8. Replaceable research workers

Possible roles, run by whichever AI operator is configured (see the AI
Provider Adapter below):
- market scanner;
- fundamental researcher;
- macro/opportunity-cost monitor;
- commercial opportunity scanner;
- experiment designer;
- skeptic/red-team reviewer (critic);
- portfolio/risk allocator;
- system-quality reviewer.

These are logical roles, not requirements for separate models/processes.

### 9. Financial data adapters (read-only only)

Adapters may expose read-only access to balances, positions, statements,
order/transaction history, prices and portfolio data, to support
reconciliation between what the human reports and what the platform shows.

```text
quote()
get_balance()
get_positions()
get_statement()
get_order_history()
```

An adapter under this repository's control must never expose `buy()`,
`sell()`, `transfer()`, `withdraw()`, `place_order()`, `cancel_order()` or any
other capability that writes to a real account. There is no architectural path
by which a read-only credential can be promoted to write access automatically;
promoting scope is always a new, separate, human-performed credential-creation
act (`HUMAN_GATES.md` Gate H2), never a configuration flag. See
`adapters/README.md`.

### 10. Scheduler / orchestration

`scheduler/`, `config/schedules.json`, `config/triggers.json`,
`state/scheduler_state.json`, `state/pending_jobs.json`.

The Capital Agent does not depend on a human manually starting an AI session.
The scheduler determines, on its own cadence and via deterministic checks
first, whether there is real cognitive work to do, and if so enqueues a job
for an AI operator to pick up. See "Scheduler and orchestration" below and
`scheduler/README.md`.

### 11. AI Provider Adapter

`adapters/ai_providers/`

The reasoning/execution environment (Claude Code, Codex, Gemini CLI, a local
model, or a future provider) is a pluggable adapter, not the Capital Agent
itself:

```text
Capital Agent (repository + state + policies + context + scheduler +
governance + evaluation + history + code)
        |
        v
AI Provider Adapter (adapters/ai_providers/base.py contract)
        |
        v
Claude Code / Codex / Gemini CLI / local model / future provider
```

See `adapters/ai_providers/README.md`.

## Operating phases

Operating phases describe how much of the analysis/recommendation loop is
wired up, not financial authority — financial write authority is never
autonomous at any phase, per the custody invariant.

- Phase 0: research, proposals, simulations only. **Current.**
- Phase 1: paper portfolio + shadow tracking, scheduler/orchestration wired
  up, read-only data feeds.
- Phase 2: Human Execution Requests actively used for real bounded
  experiments; human confirms/reconciles; read-only reconciliation adapters
  may exist.
- Phase 3: broader scheduling, event-driven triggers, more read-only
  integrations, deeper self-improvement — still no write-capable financial
  adapter, ever, under this architecture.

There is intentionally no phase in which the system gains autonomous write
authority over real money. A future proposal to introduce one is not a normal
phase transition; it is a critical governance decision under
`CRITICAL_DECISIONS.md`, requiring explicit human authorization, and even then
subject to Gate H4 and the rest of `HUMAN_GATES.md`.

## Threat model

Assume:
- web/external data can be wrong or malicious;
- prompt injection may appear in external content;
- AI decisions can be wrong;
- APIs can return stale/partial data;
- duplicate Human Execution Requests are possible if not deduplicated;
- secrets can leak if poorly handled;
- an attractive opportunity can be a scam;
- a self-modification can introduce regressions;
- a future AI may not share hidden context with the current AI;
- a component could be tempted to treat "recommended" or "approved" as if it
  meant "executed."

Therefore external content is data, never authority; system changes require
validation and rollback; durable context belongs in the repository; and the
ledger only reflects human-confirmed reality, never intent.

## Scheduler and orchestration

The scheduler is deliberately simple and deterministic-first:

```text
1. Wake up (cron, task scheduler, or any external trigger).
2. Run cheap, deterministic checks against repository state
   (ledger, experiments, policy, pending requests) — no AI call yet.
3. Decide: is there a scheduled job due, or an event trigger fired?
4. If yes: enqueue a job in state/pending_jobs.json with enough context
   for an AI operator to act on it without re-deriving everything.
5. If no: record the check in state/scheduler_state.json and stop.
6. An AI operator (via whichever AI Provider Adapter is configured) later
   dequeues and works the job.
```

Principle: **deterministic computation first, LLM reasoning when cognitively
useful.** Checking twenty prices is a script; deciding whether a price move is
a material event worth an AI's attention is a threshold check; only reasoning
about what a material event *means* calls an AI.

### Frequencies (`config/schedules.json`)

- frequent/lightweight: data collection, trigger checks, health checks.
- daily: portfolio reconciliation, active-experiment monitoring, opportunity
  monitoring, risk review.
- weekly: capital allocation review, opportunity ranking, thesis review.
- monthly: system audit, calibration, benchmark comparison, recurring-error
  analysis, system-improvement review.
- quarterly: architecture review, strategy review, governance review.

### Event-driven triggers (`config/triggers.json`)

Examples: drawdown threshold reached, experiment deadline reached, experiment
success/failure threshold reached, new revenue detected, material
market/company event detected, human execution confirmation received, three
similar failures detected, policy anomaly detected, context inconsistency
detected, critical decision generated.

## Evaluation & Critic subsystem

```text
proposal -> critic -> criticality classifier
                      |
        non-critical -+-> policy check -> proceed (still human-executed if
        |                                 it involves real money)
        critical ----+-> approval package -> HUMAN AUTHORIZATION
                                                         |
                             (if it involves real money) v
                                              Human Execution Request
                                                         |
                                                HUMAN FINANCIAL EXECUTION
                                                         |
                                                      outcome
                                                         |
                                                   post-mortem
                                                         |
                                                      lessons
                                                         |
                                                system evolution
```

The critic is not an execution authority and never becomes one. Opportunity
discovery is not limited to securities; heterogeneous opportunities are
compared by capital required, maximum plausible loss, expected value,
evidence quality, time to feedback, reversibility, operational burden,
scalability, liquidity/lock-up and legal/reputational complexity.
`approvals/pending/` stores explicit approval packages; a recommendation is
never itself an approval, and an approval is never itself an execution.

## Responsibility split

```text
CAPITAL AGENT (AI operator, within governance)
- research, opportunity discovery, strategy, analysis
- decision making within policy, critic, risk analysis
- sizing, timing, entry/exit criteria
- monitoring, context management, journaling
- system evolution, experiment design
- recommendation generation, Human Execution Request preparation

HUMAN OWNER
- custody: banking, brokerage and exchange credentials
- financial execution and payment execution
- explicit approval of critical decisions
- identity/KYC, contracts and actions legally requiring a person
```

The Capital Agent is expected to reach its own conclusions within policy —
research, compare alternatives, and decide — rather than asking the human to
make analytical choices the agent is equipped to make itself. The human is
not a substitute for the agent's analytical work; the human is the exclusive
custodian of real money and the final authority on critical decisions.

# Capital Agent v0

Experimental capital-allocation system initialized with **BRL 1,000.00**.

## Mandate

Maximize long-run compounded capital subject to explicit survival, legality,
security, accounting and authority constraints.

The system is strategy-agnostic and **AI-provider neutral**. Any capable AI may
operate the project by reading its canonical repository state. It may compare
financial investments, systematic strategies, software/products, commercial
experiments and other legal capital uses. It is not required to stay invested.

## Custody invariant

**Only the human owner may access, custody or move real money.** No AI,
script, scheduler, service, integration or credential in this system may
buy, sell, transfer, pay, withdraw or otherwise execute a real financial
operation. The Capital Agent researches, decides and recommends; the human
executes. See `AI_OPERATING_MANUAL.md` "Custody invariant" and
`ARCHITECTURE.md`. This is a hard invariant of the architecture, not a
temporary limitation of the current phase.

## Core design goals

- maximum autonomy for research, analysis, decision-making and recommendation;
- custody and financial execution exclusively human, at every phase;
- auditable capital decisions and financial executions;
- ability to improve its own code/processes safely;
- replaceable AI provider/model/tooling;
- durable context stored in files rather than hidden conversation history;
- autonomous operation via a scheduler, not dependence on a human starting
  every session.

## Current phase

**Phase 0 — Foundation / research and preparation only**

The repository can:
- maintain a capital ledger;
- calculate current cash balance;
- register capital-allocation proposals;
- open/close experiments;
- prepare Human Execution Requests and record human-confirmed executions
  (`execution/`);
- run a deterministic scheduler that queues jobs for an AI operator
  (`scheduler/`, `src/scheduler.py`);
- preserve decision and system-change journals;
- enforce hard policy limits in code;
- govern autonomous self-improvement;
- run locally with no third-party Python dependencies.

It **cannot, at any phase**:
- send broker/exchange orders;
- transfer money;
- make payments;
- use a financial credential with write authority;
- autonomously relax hard financial policy or the custody invariant.

## Canonical files

- `AI_OPERATING_MANUAL.md` — vendor-neutral instructions for any AI, including the custody invariant.
- `INVESTMENT_POLICY.md` — capital and risk policy.
- `HUMAN_GATES.md` — actions requiring a person.
- `CRITICAL_DECISIONS.md` — decisions requiring explicit human authorization.
- `ARCHITECTURE.md` — components, including the Human Execution Request lifecycle and scheduler.
- `SYSTEM_EVOLUTION.md` — self-improvement/change governance.
- `config/policy.json` — machine-readable financial limits.
- `config/system_governance.json` — machine-readable system-change rules.
- `data/ledger.csv` — accounting source, updated only via confirmed human execution.
- `execution/` — Human Execution Request lifecycle.

Start from `START_HERE.md`. `AGENTS.md` and `CLAUDE.md` are only compatibility
adapters for tools that discover those filenames automatically; they are not
canonical policy sources.

## Starting capital

`BRL 1,000.00`

The initial ledger entry is stored in `data/ledger.csv`.

## Quick start

```powershell
python .\src\capital_agent.py status
python .\src\capital_agent.py propose --title "Example" --amount 50 --category research --thesis "Test a hypothesis"
python .\src\capital_agent.py experiments
python .\src\capital_agent.py execution-requests
python .\src\scheduler.py run
python -m unittest discover -s tests
```

See `execution/README.md` for the full Human Execution Request lifecycle
(`request-execution` / `confirm-execution` / `cancel-execution` /
`expire-execution`) and `scheduler/README.md` for autonomous operation.

## Using any AI system

Give the chosen AI access to the repository and instruct it: "Read
START_HERE.md and assume operation of the Capital Agent." `START_HERE.md`
routes to `AI_OPERATING_MANUAL.md` and the rest of the canonical documents.

If the selected tool supports a repository instruction/discovery file, create only a
thin adapter pointing back to `START_HERE.md`. See `adapters/README.md` and
`adapters/ai_providers/README.md`.

## Design principles

> Autonomous analysis, decision-making and self-improvement can be broad. Custody and financial execution are exclusively human, always.

> A different capable AI should be able to continue the experiment from repository state alone, starting at `START_HERE.md`.

> The Capital Agent recommends; the human owner executes and authorizes critical decisions. These are separate events, never conflated.

## Governance v0.2

The repository includes `EVALUATION_CRITIC_SYSTEM.md`, `CRITICAL_DECISIONS.md`, `config/critical_decisions.json`, `approvals/` and `execution/`. The system may explore any lawful, ethical and bounded-risk business opportunity, not only investments. The system is free to think broadly; it is not free to execute critical actions or move real money without authorization and human execution, respectively.

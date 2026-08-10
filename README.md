# Capital Agent v0

Experimental capital-allocation system initialized with **BRL 1,000.00**.

## Mandate

Maximize long-run compounded capital subject to explicit survival, legality,
security, accounting and authority constraints.

The system is strategy-agnostic and **AI-provider neutral**. Any capable AI may
operate the project by reading its canonical repository state. It may compare
financial investments, systematic strategies, software/products, commercial
experiments and other legal capital uses. It is not required to stay invested.

## Core design goals

- low human intervention;
- auditable capital decisions;
- bounded financial authority;
- ability to improve its own code/processes safely;
- replaceable AI provider/model/tooling;
- durable context stored in files rather than hidden conversation history.

## Current phase

**Phase 0 — Foundation / no live execution**

The repository can:
- maintain a capital ledger;
- calculate current cash balance;
- register capital-allocation proposals;
- open/close experiments;
- preserve decision and system-change journals;
- enforce hard policy limits in code;
- govern autonomous self-improvement;
- run locally with no third-party Python dependencies.

It **cannot yet**:
- send broker orders;
- transfer money;
- make payments;
- use exchange/broker credentials;
- autonomously relax hard financial policy.

## Canonical files

- `AI_OPERATING_MANUAL.md` — vendor-neutral instructions for any AI.
- `INVESTMENT_POLICY.md` — capital and risk policy.
- `HUMAN_GATES.md` — actions requiring a person.
- `SYSTEM_EVOLUTION.md` — self-improvement/change governance.
- `config/policy.json` — machine-readable financial limits.
- `config/system_governance.json` — machine-readable system-change rules.
- `data/ledger.csv` — accounting source.

`AGENTS.md` is only a compatibility adapter for tools that discover that filename
automatically. It is not the canonical policy source.

## Starting capital

`BRL 1,000.00`

The initial ledger entry is stored in `data/ledger.csv`.

## Quick start

```powershell
python .\src\capital_agent.py status
python .\src\capital_agent.py propose --title "Example" --amount 50 --category research --thesis "Test a hypothesis"
python .\src\capital_agent.py experiments
python -m unittest discover -s tests
```

## Using any AI system

Give the chosen AI access to the repository and instruct it to read
`AI_OPERATING_MANUAL.md` and execute `PHASE0_READINESS_PROMPT.md`.

If the selected tool supports a repository instruction/discovery file, create only a
thin adapter pointing back to the canonical documents. See `adapters/README.md`.

## Design principles

> Autonomous analysis and self-improvement can be broad. Autonomous financial authority must remain narrow.

> A different capable AI should be able to continue the experiment from repository state alone.

## Governance v0.2

The repository includes `EVALUATION_CRITIC_SYSTEM.md`, `CRITICAL_DECISIONS.md`, `config/critical_decisions.json` and `approvals/`. The system may explore any lawful, ethical and bounded-risk business opportunity, not only investments. The system is free to think broadly; it is not free to execute critical actions without authorization.

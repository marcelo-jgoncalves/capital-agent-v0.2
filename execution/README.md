# Execution — Human Execution Requests

This directory is the only sanctioned path from a Capital Agent recommendation
to a real financial operation. It exists because of the custody invariant
(`AI_OPERATING_MANUAL.md`): **only the human owner may access, custody or move
real money.** The Capital Agent never executes; it prepares a precise,
auditable request and waits for the human to act.

## Lifecycle

```text
ANALYSIS -> DECISION -> (critical? -> HUMAN APPROVAL) -> HUMAN_EXECUTION_REQUEST
   -> WAITING_FOR_HUMAN_EXECUTION -> HUMAN EXECUTES -> EXECUTION CONFIRMATION
   -> RECONCILIATION -> LEDGER UPDATE
```

A request is created with `python src/capital_agent.py request-execution` and
starts in `human_requests/pending/`. From there it moves to exactly one
terminal directory:

- `human_requests/completed/` — the human confirmed they executed it
  (`confirm-execution`). Only this transition is allowed to write to
  `data/ledger.csv`, and it records what the human actually reported
  (quantity, price, fees, timestamp), not the originally requested values.
- `human_requests/expired/` — its `valid_until` passed without execution
  (`expire-execution`, or the deterministic sweep,
  `sweep-expired-executions`, which needs no AI reasoning).
- `human_requests/cancelled/` — withdrawn before execution
  (`cancel-execution`): thesis changed, a better alternative was found, or
  the human declined.

While a request is `pending`, it is not counted as real equity and must not be
treated as if the money had already moved — `context/CURRENT_STATE.md` lists
pending requests separately from verified cash.

## Critical decisions

If `request-execution`'s policy check classifies the action as critical
(`CRITICAL_DECISIONS.md`, `config/critical_decisions.json`), the command
refuses to create the request unless `--approval-id` points to an
`approvals/pending/` or `approvals/archive/` record whose `## Human decision`
section reads `APPROVED`. Authorization and execution remain two separate
events even when both apply to the same operation: authorization answers "may
this be done," a Human Execution Request and its human-reported confirmation
answer "was it actually done, and how."

## Fields

A request records: action (`BUY`/`SELL`/`TRANSFER`/`WITHDRAWAL`/`PAYMENT`/
`OTHER`), asset, quantity, maximum price, maximum total capital, validity
window, reason, expected upside, maximum plausible loss, critic assessment,
policy status, whether it is a critical decision and why, and — once
completed — the human's reported execution details. `TRANSFER`/`WITHDRAWAL`
additionally require `--destination-controlled-by-human`, matching
`INVESTMENT_POLICY.md` section 3's ban on withdrawals to destinations the
human owner does not control.

## What this directory cannot contain

No code path here calls a broker, exchange, bank or payment API, and none
ever should. If a future read-only reconciliation adapter is added
(`ARCHITECTURE.md` "Financial data adapters"), it may help *verify* that a
human-reported confirmation matches the real account, but it cannot itself
create a `completed` status — only `confirm-execution`, driven by a human
report, can.

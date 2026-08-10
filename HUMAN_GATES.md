# Human Gates

The goal is minimal *unnecessary* human intervention, not zero accountability
and not minimal financial involvement. See the custody invariant in
`AI_OPERATING_MANUAL.md`: real money moves only through the human owner, at
every phase, without exception. That is not one gate among several below — it
is the structural default from which the gates below are the *exceptions and
clarifications*, not the source of the restriction.

## Gate H0 — Every financial execution (always, no exception)

The human owner is the only party who ever moves real money: buys, sells,
transfers, pays, withdraws, or otherwise creates or settles a real financial
order. The Capital Agent's output toward money moving is always a Human
Execution Request (`execution/human_requests/`, `ARCHITECTURE.md`), never an
executed operation. This applies regardless of amount, regardless of whether
the underlying decision was critical, and regardless of operating phase —
there is no execution tier or future phase that changes it. See
`SYSTEM_EVOLUTION.md` Class D.

## Gate H1 — Identity / KYC / legal acceptance

Human required for:
- brokerage/exchange/bank account opening;
- KYC;
- contracts or terms requiring personal acceptance;
- tax/legal declarations.

## Gate H2 — Secrets / authentication

Human required to:
- create API keys;
- approve OAuth;
- perform MFA;
- store secrets in the approved secret store.

Any financial data credential must be read-only (balances, positions,
statements, order/transaction history, prices) — see "Financial data
adapters" in `ARCHITECTURE.md`. There is no configuration path in this
repository that promotes a read-only credential to write access; creating a
write-capable financial credential for the system is prohibited outright
(Gate H0), not merely gated.

The agent must not ask the human to paste long-lived secrets into chat or commit
them into Git.

## Gate H3 — New money or liability

Human approval required for:
- adding capital beyond the original experiment equity;
- any borrowing;
- any guarantee;
- any liability that could survive loss of the allocated amount.

Borrowing is currently prohibited regardless of approval.

## Gate H4 — First read-only financial data integration

Human approval required before enabling a new read-only financial data
adapter for the first time (balances, positions, statements, order/transaction
history, prices). Approval is for that adapter and its explicit read-only
scope, not blanket authority. There is no equivalent gate for a *write*
adapter because none may ever exist under this architecture (Gate H0).

## Gate H5 — Policy relaxation

Human approval required to relax a hard limit or enable:
- leverage;
- borrowing;
- withdrawals;
- higher concentration/risk caps;
- any expansion of `execution_tier` or operating phase that touches financial
  authority.

Relaxing the custody invariant itself (Gate H0) is not addressed by this gate
alone — it is necessarily a critical governance decision under
`CRITICAL_DECISIONS.md` (see Gate H7) in addition to requiring a system-change
record, and the current architecture treats autonomous financial execution as
out of scope regardless.

## Gate H6 — Physical-world action

Human required when something must physically be shipped, received, verified,
signed, photographed or collected.

## What does NOT require human approval in Phase 0

- research;
- code changes that do not relax hard policy or touch the custody invariant;
- simulations/backtests;
- decision journaling;
- data ingestion from public sources;
- creating proposals;
- rejecting opportunities;
- tightening risk controls;
- preparing (but not executing) a Human Execution Request.

## Gate H7 — Critical decisions

Every critical decision defined by `CRITICAL_DECISIONS.md` requires explicit human authorization. This gate supersedes autonomy granted elsewhere. If classification is uncertain, treat the decision as critical. Research and preparation may continue while approval is pending; execution may not.

Critical-decision authorization and financial execution are two separate
events (`ARCHITECTURE.md`). Authorizing a critical decision never itself moves
money; if the decision involves real money, a Human Execution Request still
follows, and only the human's confirmed execution updates the ledger.

Authorization must be authenticated as genuinely the human's — see
`CRITICAL_DECISIONS.md` "Approval authentication" for the current
interactive-session convention and its limits.

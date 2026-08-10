# Human Gates

The goal is minimal human intervention, not zero accountability.

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

The agent must not ask the human to paste long-lived secrets into chat or commit
them into Git.

## Gate H3 — New money or liability

Human approval required for:
- adding capital beyond the original experiment equity;
- any borrowing;
- any guarantee;
- any liability that could survive loss of the allocated amount.

Borrowing is currently prohibited regardless of approval.

## Gate H4 — First live integration

Human approval required before enabling a new live execution adapter for the
first time.

Approval is for the adapter and explicit limits, not blanket authority.

## Gate H5 — Policy relaxation

Human approval required to relax a hard limit or enable:
- leverage;
- borrowing;
- withdrawals;
- higher execution tier;
- higher concentration/risk caps.

## Gate H6 — Physical-world action

Human required when something must physically be shipped, received, verified,
signed, photographed or collected.

## What does NOT require human approval in Phase 0

- research;
- code changes that do not relax hard policy;
- simulations/backtests;
- decision journaling;
- data ingestion from public sources;
- creating proposals;
- rejecting opportunities;
- tightening risk controls.

## Gate H7 — Critical decisions

Every critical decision defined by `CRITICAL_DECISIONS.md` requires explicit human authorization. This gate supersedes autonomy granted elsewhere. If classification is uncertain, treat the decision as critical. Research and preparation may continue while approval is pending; execution may not.

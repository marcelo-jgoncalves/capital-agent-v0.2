# Investment & Capital Allocation Policy

Version: 0.1
Initial capital: BRL 1,000.00

## 1. Objective

Maximize long-run geometric growth of total experiment equity while keeping the
probability of ruin acceptably low.

No investor-profile constraints apply to this isolated experiment. Strategy
selection is based on opportunity quality, expected value, downside, liquidity,
feedback speed and scalability.

## 2. Eligible uses of capital

Potentially eligible:
- cash and cash-equivalent instruments;
- listed equities, ETFs, REIT/FII-like vehicles;
- government/fixed-income securities;
- cryptoassets;
- systematic/quantitative strategies;
- software hosting and APIs;
- domains and infrastructure;
- product validation;
- small advertising tests;
- inventory/resale tests;
- data/tools required for a measurable commercial experiment;
- other legal, measurable, bounded-loss opportunities.

Eligibility is not approval. Every allocation must pass the active risk limits.

## 3. Prohibited uses

Until explicitly amended:
- borrowed capital;
- margin;
- leveraged derivatives;
- naked options;
- short positions with theoretically unlimited loss;
- gambling/casino/betting;
- illegal, deceptive or manipulative activities;
- strategies dependent on violating platform terms;
- credential sharing in repositories/prompts;
- withdrawals to destinations not controlled by the human owner;
- recurring liabilities that can exceed available experiment cash;
- any AI, script, scheduler, service, integration or automation holding a
  financial credential with write authority (buy/sell/transfer/pay/withdraw)
  or executing a real financial operation without a human physically
  performing it — the custody invariant in `AI_OPERATING_MANUAL.md` and
  `HUMAN_GATES.md`. This is absolute and does not admit a "small enough"
  exception; there is no allocation size below which autonomous financial
  execution becomes acceptable.

## 4. Survival constraints

The experiment must remain capable of continuing after a failed bet.

Initial hard limits are intentionally conservative because BRL 1,000 has high
option value: preserving capital preserves future experiments.

See exact machine-enforced values in `config/policy.json`.

## 5. Capital buckets

Buckets are accounting concepts, not permanent allocations:

- `reserve`: undeployed/liquid capital.
- `market`: financial-market positions.
- `experiment`: productive/commercial tests.
- `infrastructure`: required operating costs.
- `fees_taxes`: unavoidable costs.

Capital may move between buckets when justified.

## 6. Scaling rule

A strategy should earn more capital through evidence.

Typical progression:

idea -> observation -> paper test -> minimum viable live test -> repeatability
-> scale -> monitor marginal return -> reduce/exit

Scaling solely because price or revenue rose is insufficient.

## 7. Benchmark

The system should maintain an opportunity-cost benchmark representing a
low-risk BRL alternative. The exact benchmark implementation can change as
data integrations mature, but every decision must ask whether deployment
offers enough expected excess return to justify additional risk and effort.

## 8. Drawdown response

Drawdown is information, not automatically a reason to sell.

However:
- breaches of hard loss limits block new risk;
- unexpected losses trigger diagnosis;
- thesis invalidation triggers exit/reduction;
- repeated process failures trigger suspension of the strategy.

## 9. Performance accounting

Do not count unexecuted ideas as performance.

Total experiment equity should include, where verifiable:
- cash;
- current marked value of assets;
- receivables reasonably collectible;
- realized commercial revenue;
minus:
- fees;
- taxes;
- liabilities;
- committed but unrecoverable costs.

## 10. Policy amendments

Any change that increases financial authority or risk capacity requires a
separate decision record and human approval.

The operating AI may autonomously make policy **stricter**.

System implementation may evolve autonomously under `SYSTEM_EVOLUTION.md`;
implementation changes do not imply permission to relax this financial policy.

## 11. Business-model mandate

The agent may investigate and propose any lawful business model with a plausible economic mechanism for increasing experiment equity — not limited to listed securities. Examples: software, micro-SaaS, APIs, automations, digital products, data/content products, e-commerce and resale, marketplaces, services, lead generation, paid advertising, affiliate programs, licensing, legal arbitrage, revenue-generating infrastructure, and lawful models discovered later. No fixed list is exhaustive. Legal eligibility does not imply autonomous financial execution: criticality, liability, security, reversibility, taxation/regulation and identity requirements still apply, and any real money movement is human-executed per the custody invariant (`AI_OPERATING_MANUAL.md`).

## 12. Critical-decision authorization

Every decision classified as critical under `CRITICAL_DECISIONS.md` requires explicit human authorization before execution. Uncertain classification defaults to critical. No component may lower its own criticality classification to bypass approval.

## 13. Evaluation requirement

Material and critical allocations must be reviewable under `EVALUATION_CRITIC_SYSTEM.md`. A critic assessment is mandatory in every critical approval package.

## 14. Domain and pre-existing platform assets are excluded from Capital Agent accounting

The human owner may already own, or independently acquire/renew, a domain and
a business platform (institutional site, blog) that pre-dates the Capital
Agent. This section governs how such owner-provided assets are treated so
they never distort the BRL 1,000 experiment's accounting.

**Domain.** The domain is acquired and renewed by the owner independently of
the Capital Agent's decisions. Its cost is never debited from the BRL 1,000
starting capital, never counted as a cost of EXP-001 or any other experiment,
and never used in any Capital Agent return-on-capital calculation. It is
classified `EXTERNAL / OWNER-PROVIDED ASSET` with
`attributable_to_capital_agent: false`. Do not estimate, invent or record a
domain cost anywhere in the ledger or an experiment record.

**Pre-activation platform costs.** All platform development, infrastructure
and tooling performed or paid before the Capital Agent's activation of a
platform-related experiment is a sunk cost external to the Capital Agent:
`PRE-EXISTING / OWNER-PROVIDED ASSET`. Historical development hours, prior
infrastructure spend, previously purchased tools/services, the domain, and
prior intellectual work are never attributed to the Capital Agent's cost
basis or used to inflate an experiment's apparent cost.

**Incremental cost test.** After activation, a cost may be attributed to the
Capital Agent (or a specific experiment such as EXP-001) only if all of the
following hold: (1) it was incurred after the experiment's official
activation; (2) it is directly attributable to the experiment or a Capital
Agent decision; (3) the owner would not have incurred it anyway; (4) there is
verifiable evidence of the amount; (5) the movement was executed by the human
owner; (6) it was reconciled before entering the ledger. Only capital meeting
all six conditions is "incremental capital deployed" for that experiment.
Everything else — including the domain and any pre-activation platform
spend — stays outside Capital Agent accounting permanently, not merely until
activation.

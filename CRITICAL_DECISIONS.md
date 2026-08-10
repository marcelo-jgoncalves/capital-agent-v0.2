# Critical Decision Policy

Version: 0.2

## Core rule

**Every critical decision requires explicit human authorization before execution.**

The system may research, simulate, draft, code, test and prepare a critical decision autonomously. Execution remains blocked until a bounded approval is recorded. Silence, previous broad authorization, the mission to maximize capital, or approval for a similar action does not count as approval. If classification is uncertain, default to **critical**.

## Critical triggers

A decision is critical if ANY trigger applies.

### Capital / financial exposure
- live deployment above the machine-readable non-critical threshold;
- maximum plausible loss above the non-critical threshold;
- any recurring financial commitment;
- material reduction of required liquidity reserve;
- a new category of live financial execution;
- a new counterparty/platform with write authority over money.

### New business activity
- entering a new business model that creates obligations to customers, suppliers, contractors or platforms;
- buying inventory for resale above the non-critical threshold;
- paid advertising above the non-critical test threshold;
- subscriptions, warranties, refunds, SLAs or recurring customer obligations;
- business activity whose legal/tax treatment is uncertain.

### Legal / contractual / regulatory
- accepting contracts or binding commercial terms;
- regulated or licensed activity;
- uncertain legal classification;
- new material tax/compliance obligations;
- collecting regulated or highly sensitive personal data.

### Identity / reputation / external representation
- publishing or communicating publicly in the human owner's name;
- contacting customers, suppliers, partners or institutions as the owner;
- creating a public brand/account that represents the owner;
- making guarantees, endorsements or claims that can create liability.

### Security / access
- creating credentials with write authority over funds;
- enabling a new live execution adapter;
- increasing API privileges;
- connecting write-capable automation to sensitive/financial systems;
- changing secret-management architecture in a way that expands access.

### System governance
- relaxing a risk limit;
- increasing autonomous authority;
- reducing what counts as a critical decision;
- weakening approval requirements;
- weakening logging, rollback, audit or critic controls;
- modifying protected historical records.

### Irreversibility / material operational impact
- deleting material data;
- transferring ownership of an asset;
- shipping/receiving physical goods;
- performing an action difficult or costly to reverse;
- creating a material external obligation.

## Machine-readable thresholds

See `config/critical_decisions.json`. Thresholds define what MAY be non-critical; another trigger can still make the action critical.

## Required approval package

Before authorization, persist the exact action, reason, capital required, maximum plausible loss, reversibility, alternatives including doing nothing, critic assessment, policy checks, expected downside/base/upside and the specific authorization requested.

## Scope

Approval is limited to the described action, amount, counterparty, duration and risk limits. It does not authorize larger, repeated or materially different actions.

## Emergency risk-reduction exception

The system may autonomously reduce an already-existing exposure without waiting for approval only when the action cannot increase exposure, creates no new obligation, is already permitted by the active execution adapter and is logged immediately. Otherwise, human approval is required.

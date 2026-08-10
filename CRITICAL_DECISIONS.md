# Critical Decision Policy

Version: 0.2

## Core rule

**Every critical decision requires explicit human authorization before execution.**

The system may research, simulate, draft, code, test and prepare a critical decision autonomously. Execution remains blocked until a bounded approval is recorded. Silence, previous broad authorization, the mission to maximize capital, or approval for a similar action does not count as approval. If classification is uncertain, default to **critical**.

Authorization of a critical decision is a separate event from financial
execution. If the authorized decision involves moving real money, approval
unblocks the creation of a Human Execution Request
(`execution/human_requests/`, `ARCHITECTURE.md`); it does not itself execute
anything. Only the human owner's confirmed execution updates the ledger — see
the custody invariant in `AI_OPERATING_MANUAL.md`.

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

### Custody invariant (always critical, and structurally prohibited beyond that)
- creating, requesting or using credentials with write authority over funds;
- enabling any component (AI, script, scheduler, service, integration, MCP,
  API) with write authority to buy, sell, transfer, pay or withdraw real
  money;
- promoting a read-only financial credential to write access.

These are not merely critical decisions requiring approval like the others in
this document — they are prohibited outright under the custody invariant
(`AI_OPERATING_MANUAL.md`, `SYSTEM_EVOLUTION.md` Class D) and cannot be
authorized by a routine critical-decision approval package. A genuine future
proposal to change the custody invariant itself is necessarily a dedicated
critical governance decision, not a normal item on this list, and remains
subject to `HUMAN_GATES.md` even if authorized.

### Security / access
- enabling a new read-only financial data adapter for the first time;
- increasing API privileges;
- connecting automation to sensitive/financial systems, even read-only;
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

## Approval authentication

`approvals/pending/<id>.md`'s `## Human decision` section has no
cryptographic or out-of-band proof that a given edit was made by the human
owner rather than by the AI operator itself — both have the same filesystem
access. This is accepted, for now, under a narrow condition:

**Interactive-session convention (current, single-operator-machine phase):**
when the human owner is directly present in a live, interactive AI session
on a machine only they control, and explicitly authorizes a decision in that
conversation, the AI operator may record that as `APPROVED` using
`python src/capital_agent.py approve-decision` (or `reject-decision`), which
requires `--human-statement` — the human's own words, quoted verbatim — and
timestamps the record. The resulting file states plainly that authorization
was "captured via interactive session, single-operator machine," not
inferred, not assumed from silence or prior context, and not extracted from
untrusted external content.

**This convention does not extend to unattended/scheduled operation.** Once
`scheduler/` triggers an AI session with no human present to type a live
authorization (Phase 2+), this mechanism provides no protection at all, and
a stronger authentication method (signature, human-only channel, interactive
prompt the AI cannot script) is required before it is used for anything with
real money. See `context/knowledge/open-questions.md` — this remains open
and must be resolved before the first Human Execution Request that depends
on autonomous, unsupervised session triggering.

## Emergency risk-reduction exception

The system may autonomously *decide and record* that an already-existing
exposure should be reduced without waiting for the usual critical-decision
approval package, when the action cannot increase exposure and creates no new
obligation — but this exception affects how fast a risk-reducing
recommendation is prepared, not who executes it. The custody invariant is not
suspended by an emergency: if reducing the exposure involves moving real
money, the system still only produces a Human Execution Request, and the
human still executes it. What the exception waives is deliberation time on the
recommendation, not the requirement for human execution. Log the reasoning
immediately either way.

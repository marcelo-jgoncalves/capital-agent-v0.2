# External Integration — Editorial Platform (canonical)

This is the canonical document for how the Capital Agent integrates with the
independently-owned Editorial Platform (`mgoncalves-editorial-platform`) as
an experimental acquisition/revenue channel (EXP-001). It is referenced, not
duplicated, by other canonical documents. Implementation lives in
`src/business_integration.py`; schemas live in `schemas/*.schema.json`;
platform-side gaps are tracked in `backlog/platform-integration.md`.

## 1. Architecture boundary

The Capital Agent and the Editorial Platform are, and remain, independent
systems connected only by explicit, versioned contracts (JSON schemas +
file/fixture ingestion today; a future read-only API is allowed but not
required). The Capital Agent:

- never holds Editorial Platform credentials, admin tokens, or CMS write
  access;
- never deploys, merges, or edits the platform's code or infrastructure;
- never shares a database with the platform;
- treats the platform as a black box that may, in future, expose sanitized
  telemetry, publication receipts, and lead-lifecycle states.

## 2. Human Execution Request vs. External Cash Event vs. ledger entry

- **Human Execution Request** (`execution/human_requests/`, existing): a
  financial action the human executes manually and then confirms (buy,
  sell, transfer, withdrawal, payment). The human is the actor.
- **External Cash Event** (`state/external_cash_events/`, new, this
  integration): money that arrives from outside without the human
  "executing" anything -- e.g. a customer pays an invoice. State machine:
  `OBSERVED -> REPORTED -> VERIFIED -> ATTRIBUTED -> RECONCILED ->
  LEDGER_POSTED` (`src/business_integration.py`). `VERIFIED` can only be
  reached via explicit human confirmation or a pre-registered trusted
  read-only financial adapter (`TRUSTED_READONLY_FINANCIAL_ADAPTERS`,
  currently empty) -- never by AI inference. Idempotent on
  `(source_system, source_record_id)`.
- **Ledger entry** (`data/ledger.csv`, existing, append-only): the single
  record of verified cash movement. Both Human Execution Requests
  (`confirm-execution`) and `LEDGER_POSTED` External Cash Events
  (`post_external_cash_event_to_ledger`) write here, but neither can post
  twice for the same idempotency key/reference.

## 3. Experiment lifecycle (single source of truth)

`lifecycle_state` on an experiment record is the only lifecycle field new
code should read; legacy `state`/`status` are kept in sync for backward
compatibility. States: `PLANNED -> READY_FOR_ACTIVATION -> ACTIVE -> PAUSED
-> CLOSED`, with `PAUSED <-> ACTIVE` and any state `-> CLOSED`. Invalid
transitions raise `ExperimentLifecycleError`
(`src/business_integration.py: validate_experiment_transition`).

### Zero-capital experiments

`capital_budget_brl == 0` is valid. It does not mean zero cost: the schema
separates **financial capital** (capital allocated, incremental cost,
maximum loss, recurring spend, financial commitment) from **non-financial
resources** (`resource_budget.operator_time_minutes`,
publications_planned, ai_runs_budget) and **non-financial risks**
(reputational, privacy, contractual, operational, regulatory -- see
`non_financial_risks` on the experiment record). `operator_time_minutes` is
an auxiliary economic metric and is never auto-converted to money, in the
ledger or in ROIC.

### ROIC and zero capital

`compute_roic(profit_brl, capital_deployed_brl)` returns `None` (never
infinite, never a ZeroDivisionError) when `capital_deployed_brl == 0`.
Callers must treat `None` as "not applicable" and fall back to
`profit_brl`, `qualified_leads`, and `attributable_revenue_brl` instead.

### READY_FOR_ACTIVATION preconditions

See `check_ready_for_activation()` and
`READY_FOR_ACTIVATION_REQUIRED_FIELDS` in `src/business_integration.py`, and
`experiments/EXP-001-ACTIVATION-CHECKLIST.md`. Any open P0 item in
`backlog/platform-integration.md` blocks the transition. EXP-001's current
assessment is recorded in its own `readiness_for_activation` field.

## 4. BUSINESS_SIGNAL vs. topic candidate

A `topic candidate` (existing editorial-research concept, see
`EDITORIAL_RESEARCH_SYSTEM.md`) answers "what could we write about". A
`BUSINESS_SIGNAL` (`state/business_signals/`,
`create_business_signal_entity()`) answers "is there evidence of demand, a
recurring pattern, or a business opportunity worth investigating". They are
never conflated: `create_business_signal_entity(signal_type=
"topic_candidate", ...)` raises `BusinessSignalError`. Promotion to an
Opportunity Candidate is a separate, explicit step
(`promote_business_signal_to_opportunity`) requiring evidence and a
rationale -- no automatic promotion.

Pipeline: External Business Signal -> `BUSINESS_SIGNAL` -> Opportunity
Candidate -> Evaluation -> Experiment or rejection.

## 5. Publication Package / Publication Receipt

`create_publication_package()` prepares a handoff request
(`state/publications/*.package.json`); its existence never implies
authorization to publish, and it never calls any CMS write endpoint. Only
after real publication does the platform (in a future capability, see
backlog PLAT-003) return a `PublicationReceipt`, ingested via
`ingest_publication_receipt()` (`state/publications/*.json`, idempotent on
`publication_request_id` + `platform_content_id`). Before that backlog item
is unlocked, the schema/ingestion path exists but has nothing real to
ingest.

## 6. Metric observations and provenance

Every economically relevant metric is stored via
`create_metric_observation()` (`state/metric_observations/`) carrying
`experiment_id, metric_name, value, unit, period, source, environment,
retrieved_at, coverage, data_quality, limitations, schema_version`.
`data_quality` distinguishes observed / aggregated / manually_reported /
verified / estimated / unavailable -- estimates are never silently treated
as fact (`limitations` is force-annotated for `estimated`).

`eligible_for_official_evaluation` is `True` only when `environment ==
"production"`. `filter_official_evaluation_observations()` additionally
excludes anything retrieved before an experiment's `activation_date`. Until
the platform can tag `environment` reliably (backlog PLAT-004), any
ingested signal without that guarantee must be treated as unverified for
economic purposes.

## 7. PII firewall

`src/business_integration.py` defines `PII_DENYLIST_KEYS` (name, email,
phone, address, raw message, IP, etc. -- always stripped) and
`BUSINESS_PAYLOAD_ALLOWLIST` (the only fields ingestion functions accept).
`sanitize_business_payload()` filters by allowlist; `assert_no_pii_keys()`
hard-fails (raises `PIIRejectedError`) if a denylisted key is present
anywhere in a payload, including one level of nesting. No fixture, test, or
persisted state file in this repository may contain real personal data --
see `tests/test_pii_firewall.py`.

## 8. Attribution rules

`ExternalCashEvent.attribution` and `BUSINESS_SIGNAL.attribution_context`
may legitimately be `UNKNOWN`; nothing in this module fabricates an
attribution when the underlying fields are absent
(`attribute_external_cash_event`).

## 9. Anti-platform-bias comparison

`build_alternatives_comparison()` produces the mandatory 4-way comparison
(platform opportunity / best financial opportunity / best non-platform
opportunity / benchmark) for the periodic capital-allocation review. Any
missing category is recorded as `NONE_AVAILABLE`, never fabricated.

## 10. EXP-001's narrow economic mechanism

EXP-001 tests exactly one funnel: `relevant content -> qualified traffic ->
CTA -> lead -> qualified lead -> proposal/conversation -> attributable
revenue`. Impressions/sessions are diagnostic only. Priority economic
metrics are qualified leads, proposals, attributable revenue, incremental
cost, profit, and ROIC when `capital_deployed_brl > 0`. See the
`funnel_definition` block in `experiments/active/EXP-20260813-62C22E.json`.

## 11. Platform backlog

See `backlog/platform-integration.md` for every capability this
integration depends on that the platform does not yet provide, with
priority, contract, and unlock condition.

## 12. What this integration explicitly does not do

It does not publish content, call CMS write endpoints, hold admin tokens,
deploy, merge platform code, share a database, or weaken the custody
invariant, critical-decision approval, ledger append-only guarantee, or
PII-privacy invariant defined in `AI_OPERATING_MANUAL.md`,
`CRITICAL_DECISIONS.md`, and `INVESTMENT_POLICY.md`.

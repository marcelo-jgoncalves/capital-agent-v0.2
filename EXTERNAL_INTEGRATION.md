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

  **Persistence**: every transition (`report_`, `verify_`, `attribute_`,
  `reconcile_`, `post_..._to_ledger`) crash-safely persists the FULL record
  (including `state_history`) to `state/external_cash_events/<id>.json` via
  an atomic write-temp-then-`os.replace()` (`_atomic_write_json`) before
  returning. The in-memory return value is never the only record of a
  transition; `load_external_cash_event(id)` / `list_external_cash_events()`
  reconstruct the complete history from disk at any time.

  **Crash-safe ledger idempotency**: `post_external_cash_event_to_ledger`
  acquires an O_CREAT|O_EXCL file lock in `state/external_cash_events/_wal/`
  keyed on the idempotency key, and checks the ledger CSV itself
  (`_ledger_reference_posted`) for an existing row with that reference
  *before* appending. This means: (a) a crash between "ledger line written"
  and "event state persisted as LEDGER_POSTED" cannot produce a duplicate
  line on retry -- the retry sees the reference is already in the ledger and
  skips the append; (b) two concurrent processes racing on the same
  idempotency key cannot both post (the lock serializes them, and the loser
  either waits and observes the winner's posted reference, or times out with
  `LedgerPostLockError`).

  **Chargeback semantics**: `kind="chargeback"` maps to ledger type
  `"chargeback"` (`CASH_EVENT_KIND_TO_LEDGER_TYPE`), which
  `capital_agent.cash_balance()` SUBTRACTS -- a chargeback is a reversal of
  previously recognized revenue, not a same-signed inflow. `refund` and
  `other_external_inflow` remain additions (money coming to the business).
  Previously `chargeback` was mapped to the same ledger type as `refund`
  (an addition), which was a bug: it treated a revenue clawback as new
  income. Fixed; see `tests/test_business_integration.py
  ChargebackSemanticsTests`.
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

### Hard, code-enforced guard against auto-activation

`apply_experiment_lifecycle_transition(experiment, new_state,
human_authorized=False, authorized_by="")` is the only sanctioned way to
change `lifecycle_state`. It refuses (`AutoActivationBlockedError`, a
subclass of `ExperimentLifecycleError`) any transition into `ACTIVE` unless
`human_authorized=True` AND a non-empty `authorized_by` are supplied. No
deterministic scheduler trigger, no AI-routed job, and no other function in
this module can set `lifecycle_state = "ACTIVE"` without going through this
guard. The scheduler (`src/scheduler.py`) never calls it -- triggers only
enqueue job tickets for a human/AI to act on later, they never mutate
experiment state directly. See
`tests/test_business_integration.py ExperimentAutoActivationGuardTests` and
`tests/test_scheduler_triggers.py Exp001CannotAutoActivateViaSchedulerTests`.

### CLI migration to canonical schema

`src/capital_agent.py cmd_new_experiment` now writes `lifecycle_state`
(canonical, always `"PLANNED"` for a newly created experiment) alongside the
legacy `state`/`status` fields kept in sync exactly as already established
for EXP-001 -- no new dual-writing pattern was invented; this simply applies
the same pattern the prior migration already documented on the EXP-001
record to the experiment-creation code path, which previously wrote only
the legacy `status` field and no `lifecycle_state` at all.

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

### BusinessObservation vs. BUSINESS_SIGNAL

These are now two distinct entities (previously conflated). A
`BusinessObservation` (`create_business_observation()`,
`state/business_observations/`) is one raw external fact with no
confidence/intensity scoring of its own (e.g. "this lead mentioned service
X on this date"). A `BUSINESS_SIGNAL` is the higher-level pattern claim,
carrying `confidence`/`intensity`, that a human or AI derives FROM one or
more `BusinessObservation` records; the relationship is explicit and
traceable via `BUSINESS_SIGNAL.derived_from_observation_ids`, a list of
`BusinessObservation.observation_id` values (in addition to the pre-existing
free-form `evidence_refs`).

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
observed_at, retrieved_at, coverage, data_quality, limitations,
schema_version`. `data_quality` distinguishes observed / aggregated /
manually_reported / verified / estimated / unavailable -- estimates are
never silently treated as fact (`limitations` is force-annotated for
`estimated`).

**Temporal invariant**: `observed_at` (when the underlying event/period
happened) must never be later than `retrieved_at` (when this system fetched
the value) -- `create_metric_observation` raises `MetricObservationError` if
a caller supplies an `observed_at` after `retrieved_at`. Previously the
model had no `observed_at` field at all (only `period`/`retrieved_at`), so
this invariant could not even be expressed, let alone enforced; the schema
(`schemas/metric_observation.schema.json`) now requires `observed_at`. When
omitted, it defaults to `retrieved_at` (the conservative "as of now"
assumption), never to a fabricated earlier time.

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

**Value-level hardening**: the allowlist above only vouches for field
*names*. `assert_no_pii_shaped_values()` additionally walks every string
value (at any nesting depth, in any key, including allowlisted ones) and
rejects the payload (`PIIRejectedError`) if it contains an email-, phone-,
CPF-, or CNPJ-shaped substring -- e.g. someone pasting an email address
into a free-text `service_interest` or `landing_content` field.
`sanitize_business_payload()` calls this automatically after allowlist
filtering, so `ingest_business_signal()` and `create_business_observation()`
both get this check for free. See
`tests/test_business_integration.py PIIValueHardeningTests`.

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

## 12. Runtime schema validation

`schemas/*.schema.json` are enforced at runtime, not just documentation.
`validate_against_schema(record, schema_filename)` (using the `jsonschema`
package when available, falling back to a minimal stdlib required-fields +
enum checker if it is not installed, so validation is never silently
skipped) is called from `ingest_business_signal()`,
`observe_external_cash_event()`/every cash-event transition,
`create_metric_observation()`, and can be called directly on any persisted
record. A schema-violating payload raises `SchemaValidationError` before it
is written to disk. See `tests/test_business_integration.py
SchemaValidationTests`.

## 13. Deterministic scheduler triggers

The 7 business triggers declared in `config/triggers.json`
(`new_business_signal_detected`, `new_qualified_lead_detected`,
`experiment_metric_threshold_reached`, `platform_signal_source_stale`,
`measurement_window_completed`, `attribution_pending_too_long`, and the
fixed `new_revenue_detected`) are wired into
`src/scheduler.py check_deterministic_triggers()`, reading real persisted
state (`state/business_signals/`, `state/external_cash_events/`,
`state/metric_observations/`, `experiments/active/`) -- no fabricated
firings, no AI call inside evaluation. Each trigger's
`requires_ai_reasoning` flag from `config/triggers.json` is now read and
respected when enqueuing the job (previously it was hardcoded `True` for
every trigger, so a `requires_ai_reasoning: false` trigger would have been
incorrectly routed to an AI-reasoning job anyway). `new_revenue_detected`
was fixed to fire only on cash events that reached `LEDGER_POSTED` (real,
human-verified, reconciled revenue), not on raw ledger-row growth (which
included expenses/fees) and not on unverified `OBSERVED` events; it is
idempotent per event id via a persisted snapshot in `scheduler_state.json`,
so it never re-fires for the same posted event on a later tick. See
`tests/test_scheduler_triggers.py`.

The remaining declared-but-unimplemented triggers
(`material_market_event_detected`, `material_company_event_detected`,
`three_similar_failures_detected`, `policy_anomaly_detected`,
`context_inconsistency_detected`, `content_performance_anomaly`,
`experiment_deadline_reached`, `experiment_success_threshold_reached`,
`experiment_failure_threshold_reached`) remain skipped -- they need a
capability (external data feed, statistical baseline, consistency-audit
pass, or richer experiment threshold parsing) not yet built. They are never
fabricated as firing.

## 14. What this integration explicitly does not do

It does not publish content, call CMS write endpoints, hold admin tokens,
deploy, merge platform code, share a database, or weaken the custody
invariant, critical-decision approval, ledger append-only guarantee, or
PII-privacy invariant defined in `AI_OPERATING_MANUAL.md`,
`CRITICAL_DECISIONS.md`, and `INVESTMENT_POLICY.md`.

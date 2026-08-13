# Platform Integration Backlog

Dependencies of the Capital Agent on the (independently owned/operated)
Editorial Platform repository (`mgoncalves-editorial-platform`). The Capital
Agent may NOT implement any of these on the platform side. Each item is
owned by a future session working on that repository ("Editorial Platform
AI"). This file is the canonical registry referenced by
`EXTERNAL_INTEGRATION.md` and by EXP-001's `readiness_for_activation` block.

Priorities: `P0` blocks safe/correct EXP-001 activation. `P1` needed for
reliable evaluation/automation. `P2` later improvement. `P3` optional.

**2026-08-13 hardening pass**: a Capital-Agent-SIDE audit
(`journal/reviews/business-integration-hardening-audit.md`) fixed 15
internal correctness/safety gaps in `src/business_integration.py` (crash-safe
persistence and ledger idempotency, chargeback sign, PII value-level
hardening, BusinessObservation/BUSINESS_SIGNAL split, runtime schema
validation, metric temporal invariants, 7 scheduler triggers wired,
`requires_ai_reasoning` routing, hard code-level guard against
auto-activating any experiment). None of these items were blocked on the
platform side, so this pass does **not** unblock or add any PLAT-0xx item
below -- every P0 item here still requires the Editorial Platform side to
ship the corresponding capability before EXP-001 can be activated. Listed
for traceability only.

---

## PLAT-001 — Sanitized business telemetry export (P0)

- Status: OPEN
- Target repository: mgoncalves-editorial-platform
- Owner suggested: Editorial Platform AI
- Why it exists: the Capital Agent's External Business Data Adapter
  (`src/business_integration.py: ingest_business_signal`) can consume
  fixtures/files today, but there is no real feed of content, session,
  CTA, lead, or conversion signals from the platform. Without this, EXP-001
  cannot be evaluated with real evidence.
- Capital Agent dependency: `check_ready_for_activation()` field
  `metrics_source`.
- Expected contract: a periodic (e.g. daily) export -- file, static JSON, or
  read-only API -- of aggregated/sanitized records matching the
  `BusinessSignal` shape in `schemas/business_signal.schema.json`:
  `signal_type, source_system, source_record_id, observed_at, metric_name,
  metric_value, unit, data_quality, coverage, environment`.
- Security/privacy rules: MUST NOT include name, email, phone, address, raw
  message content, or any other PII field listed in
  `src/business_integration.py: PII_DENYLIST_KEYS`. Aggregate or pseudonymize
  before export.
- Example record: `{"signal_type": "content_performance", "source_system":
  "editorial-platform", "source_record_id": "post-abc-2026-08-13",
  "observed_at": "2026-08-13T00:00:00Z", "metric_name": "engaged_sessions",
  "metric_value": 42, "unit": "count", "data_quality": "aggregated",
  "environment": "production"}`.
- Acceptance criteria: export is machine-readable, dated, versioned, and
  documents its own coverage/limitations; a sample file can be ingested by
  `ingest_business_signal()` without modification to that function.
- Unlock condition: Capital Agent operator points the file-adapter at a real
  export location and confirms at least one successful ingestion cycle with
  `data_quality != "unavailable"`.
- Related schema: `schemas/business_signal.schema.json`.

## PLAT-002 — Attribution fields on leads/conversions (P0)

- Status: OPEN
- Target repository: mgoncalves-editorial-platform
- Owner suggested: Editorial Platform AI
- Why it exists: without landing page / content ID / CTA ID / campaign /
  UTM / first-touch / last-touch fields, `ExternalCashEvent.attribution`
  and `BUSINESS_SIGNAL.attribution_context` can only ever be `UNKNOWN`,
  which defeats the point of measuring EXP-001's funnel.
- Capital Agent dependency: `check_ready_for_activation()` fields
  `attribution_model`, `revenue_attribution_definition`.
- Expected contract: sanitized lead/conversion records SHOULD carry
  `landing_content, cta_id, referrer_domain, campaign_id, utm_source,
  utm_medium, utm_campaign, first_touch, last_touch, environment,
  timestamp, reference_id` -- all present in
  `BUSINESS_PAYLOAD_ALLOWLIST` in `src/business_integration.py`.
- Security/privacy rules: `reference_id`/`lead_id` must be a pseudonymous,
  platform-generated identifier, never derived from or reversible to PII.
- Acceptance criteria: at least 80% of qualified-lead records carry a
  non-null `campaign_id` or `landing_content` field.
- Unlock condition: a sample export shows attribution fields populated for
  real (non-synthetic) leads.
- Related schema: `schemas/business_signal.schema.json`.

## PLAT-003 — Publication Receipt (P0)

- Status: OPEN
- Target repository: mgoncalves-editorial-platform
- Owner suggested: Editorial Platform AI
- Why it exists: `src/business_integration.py: ingest_publication_receipt()`
  and `schemas/publication_receipt.schema.json` are implemented on the
  Capital Agent side, but the platform currently has no mechanism to return
  evidence that a `PublicationPackage` was actually published.
- Capital Agent dependency: `check_ready_for_activation()` field
  `publication_handoff_defined`.
- Expected contract: after publishing content referencing a
  `publication_request_id` (passed out-of-band, e.g. in the CMS entry or
  a shared reference field), the platform produces a receipt matching
  `schemas/publication_receipt.schema.json`: `publication_id,
  publication_request_id, platform_content_id, canonical_slug,
  canonical_url, published_at, environment, campaign_id,
  verification_source`.
- Security/privacy rules: none (no PII in this object by construction).
- Acceptance criteria: a receipt can be ingested by
  `ingest_publication_receipt()` unmodified; re-ingesting the same receipt
  is a no-op (idempotent on `publication_request_id` +
  `platform_content_id`).
- Unlock condition: at least one real receipt ingested for a real
  publication.
- Related schema: `schemas/publication_receipt.schema.json`.

## PLAT-004 — Traffic/environment separation markers (P0/P1)

- Status: OPEN
- Target repository: mgoncalves-editorial-platform
- Owner suggested: Editorial Platform AI
- Why it exists: without an explicit `environment` marker
  (production/dev/staging/smoke/e2e/synthetic/admin), dev and test traffic
  could silently contaminate EXP-001's economic evaluation. This is
  explicitly disallowed (EXTERNAL_INTEGRATION.md, spec section 5.7).
- Capital Agent dependency: `check_ready_for_activation()` field
  `dev_prod_separation_confirmed`; enforced at ingestion by
  `filter_official_evaluation_observations()` in
  `src/business_integration.py`, which only admits `environment ==
  "production"`.
- Expected contract: every exported signal/metric/lead record carries an
  `environment` value from the same enum used in
  `schemas/metric_observation.schema.json`.
- Security/privacy rules: none.
- Acceptance criteria: a sample of platform traffic includes at least one
  non-production-tagged record, proving the marker is actually populated
  and not defaulted to "production" for everything.
- Unlock condition: platform confirms and demonstrates environment tagging
  is live in its telemetry pipeline.

## PLAT-005 — Lead lifecycle states, sanitized (P1)

- Status: OPEN
- Target repository: mgoncalves-editorial-platform
- Owner suggested: Editorial Platform AI
- Why it exists: `BUSINESS_PAYLOAD_ALLOWLIST` reserves a `commercial_stage`
  field but the platform has no defined sanitized lead-lifecycle vocabulary
  to populate it with.
- Capital Agent dependency: `check_ready_for_activation()` field
  `qualified_lead_definition`.
- Expected contract: platform emits `commercial_stage` using a fixed
  vocabulary, e.g. `new, qualified, discovery, proposal, won, lost`, tied
  to a pseudonymous `lead_id`, with no name/email/phone attached.
- Security/privacy rules: `lead_id` must not be reversible to PII (e.g. not
  a hash of the email without a platform-side salt/rotation policy the
  Capital Agent never sees).
- Acceptance criteria: stage transitions are observable over time for the
  same `lead_id` without any PII field ever appearing in the payload.
- Unlock condition: sample export demonstrates at least one full
  new -> qualified -> ... transition sequence for a pseudonymous lead.

## PLAT-006 — Data quality / coverage declarations (P1)

- Status: OPEN
- Target repository: mgoncalves-editorial-platform
- Owner suggested: Editorial Platform AI
- Why it exists: analytics depending on consent (cookies, tracking) has
  variable coverage; without an explicit coverage/limitations statement per
  export, the Capital Agent cannot avoid treating partial data as complete.
- Capital Agent dependency: `data_quality`/`coverage` fields on
  `BusinessSignal` and `MetricObservation`; currently these default to
  whatever the file adapter is told, with no independent platform
  confirmation.
- Expected contract: each export batch declares `coverage` (e.g.
  "consent-based analytics, ~60% of sessions") and any known gaps.
- Security/privacy rules: none.
- Acceptance criteria: coverage statement is present and non-generic (not
  just "100%" by default) for at least one real export.
- Unlock condition: first real export includes a coverage statement the
  Capital Agent can store verbatim in `MetricObservation.coverage`.

## PLAT-007 — PR-only platform automation (P2, not implemented)

- Status: DEFERRED (explicitly out of scope this session)
- Target repository: mgoncalves-editorial-platform
- Owner suggested: Editorial Platform AI
- Why it exists: eventual convenience for platform-side code changes
  proposed by an AI.
- Constraints if ever implemented: must only open PRs, must never merge,
  must never deploy production, must never receive administrative
  credentials. Not to be implemented in any near-term session.

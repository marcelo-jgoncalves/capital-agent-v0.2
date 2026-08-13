#!/usr/bin/env python3
"""External business/editorial-platform integration primitives.

This module implements the Capital Agent side of a *contract-based*, read-only
integration with an independently-operated "Editorial Platform" (a separate
repository/site the Capital Agent does not own, deploy to, or write to). It
never talks to that platform directly; it only defines the shapes of data the
Capital Agent is willing to ingest (as files/fixtures for now) and the
policies that govern what happens to that data once it arrives.

See `EXTERNAL_INTEGRATION.md` for the canonical narrative documentation. This
module is the single source of truth for the schemas/state machines it
implements; do not duplicate these rules elsewhere.

Design constraints enforced here (see EXTERNAL_INTEGRATION.md for rationale):
  - PII firewall: only allowlisted fields may be persisted anywhere in this
    repository. No name/email/phone/address/raw message content, ever.
  - Read-only: nothing in this module can call the platform, publish content,
    hold credentials, or move money.
  - No fabrication: unknown values stay explicitly unknown/UNKNOWN/null; no
    default numeric estimates are invented.
  - Idempotency: ingestion of the same external record twice must not create
    duplicate state or duplicate ledger entries.
  - Human-only VERIFIED: no code path in this module can mark an
    ExternalCashEvent VERIFIED without either an explicit human confirmation
    flag or a designated trusted read-only financial adapter name.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state"
BUSINESS_SIGNALS_DIR = STATE_DIR / "business_signals"
EXTERNAL_CASH_EVENTS_DIR = STATE_DIR / "external_cash_events"
PUBLICATIONS_DIR = STATE_DIR / "publications"
METRIC_OBSERVATIONS_DIR = STATE_DIR / "metric_observations"

SCHEMA_VERSION = "1.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# PII firewall
# ---------------------------------------------------------------------------

# Fields that are NEVER allowed to be persisted anywhere fed by this module,
# regardless of allowlists below. Defense in depth: even if an allowlist is
# misconfigured, these keys are stripped.
PII_DENYLIST_KEYS = {
    "name", "full_name", "first_name", "last_name", "email", "e_mail",
    "phone", "phone_number", "telephone", "mobile", "address", "street",
    "zip", "zipcode", "postal_code", "cpf", "cnpj", "document_number",
    "ip", "ip_address", "raw_message", "message_body", "message", "notes_raw",
    "user_agent", "cookie", "session_cookie", "date_of_birth", "dob",
}

# Allowlist of fields BUSINESS_SIGNAL / lead-derived payloads may carry.
# Anything not in this set is dropped by sanitize_business_payload().
BUSINESS_PAYLOAD_ALLOWLIST = {
    "signal_id", "signal_type", "source_system", "source_record_id",
    "experiment_id", "environment", "observed_at", "retrieved_at",
    "measurement_period", "metric_name", "metric_value", "unit",
    "data_quality", "coverage", "attribution_context", "evidence_refs",
    "provenance", "schema_version",
    # sanitized lead-lifecycle fields (pseudonymous only)
    "lead_id", "source", "landing_content", "service_interest",
    "company_size_band", "qualification", "commercial_stage",
    "first_touch", "last_touch", "campaign_id", "utm_source", "utm_medium",
    "utm_campaign", "referrer_domain", "cta_id",
}


class PIIRejectedError(ValueError):
    """Raised when a payload cannot be safely sanitized (contains PII-shaped
    values under a key that isn't explicitly denylisted, or fails validation
    in a way that could hide PII)."""


def sanitize_business_payload(payload: dict) -> dict:
    """Allowlist-filter an external business payload. Denylisted keys are
    always stripped even if a caller mistakenly widens the allowlist.
    Returns a NEW dict; never mutates the input in place (defense against a
    caller reusing/logging the raw object after "sanitization").
    """
    if not isinstance(payload, dict):
        raise PIIRejectedError("payload must be a JSON object")
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        lowered_key = key.strip().lower()
        if lowered_key in PII_DENYLIST_KEYS:
            continue
        if lowered_key not in BUSINESS_PAYLOAD_ALLOWLIST:
            continue
        clean[key] = value
    return clean


def assert_no_pii_keys(payload: dict) -> None:
    """Hard-fail if any denylisted key is present, even nested one level
    deep. Used for defense-in-depth checks in tests and at ingestion
    boundaries where silent stripping is not acceptable."""
    def _walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.strip().lower() in PII_DENYLIST_KEYS:
                    raise PIIRejectedError(f"PII-denylisted key present: {path}{k}")
                _walk(v, f"{path}{k}.")
        elif isinstance(obj, list):
            for item in obj:
                _walk(item, path)
    _walk(payload)


# ---------------------------------------------------------------------------
# 5.1 External Business Data Adapter + BUSINESS_SIGNAL / metric signal shape
# ---------------------------------------------------------------------------

VALID_DATA_QUALITY = {
    "observed", "aggregated", "manually_reported", "verified", "estimated",
    "unavailable",
}

VALID_ENVIRONMENTS = {"production", "dev", "test", "staging", "smoke", "e2e", "synthetic", "admin", "unknown"}


def _write_json_idempotent(dir_path: Path, record_id: str, idempotency_key: str, data: dict) -> tuple[dict, bool]:
    """Write `data` to dir_path/<record_id>.json unless a record with the
    same idempotency_key already exists in that directory, in which case the
    existing record is returned unchanged. Returns (record, created)."""
    dir_path.mkdir(parents=True, exist_ok=True)
    for existing_path in sorted(dir_path.glob("*.json")):
        try:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if existing.get("idempotency_key") == idempotency_key:
            return existing, False
    path = dir_path / f"{record_id}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data, True


class BusinessSignalError(ValueError):
    pass


def ingest_business_signal(
    *,
    signal_type: str,
    source_system: str,
    source_record_id: str,
    observed_at: str,
    metric_name: str,
    metric_value: Optional[float],
    unit: Optional[str],
    data_quality: str,
    coverage: Optional[str] = None,
    experiment_id: Optional[str] = None,
    environment: str = "unknown",
    measurement_period: Optional[str] = None,
    attribution_context: Optional[str] = None,
    evidence_refs: Optional[list] = None,
    limitations: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    """Ingest one external business signal from a file/fixture source (the
    "External Business Data Adapter"). Read-only with respect to the
    platform: this function only ever reads a payload that was already
    handed to it and writes normalized state locally; it never calls out to
    any network service. Idempotent on (source_system, source_record_id,
    metric_name, measurement_period).

    Raises BusinessSignalError on malformed input; never silently invents
    missing fields.
    """
    if data_quality not in VALID_DATA_QUALITY:
        raise BusinessSignalError(f"invalid data_quality: {data_quality!r}; must be one of {sorted(VALID_DATA_QUALITY)}")
    if environment not in VALID_ENVIRONMENTS:
        raise BusinessSignalError(f"invalid environment: {environment!r}; must be one of {sorted(VALID_ENVIRONMENTS)}")
    if not source_system or not source_record_id:
        raise BusinessSignalError("source_system and source_record_id are required for provenance")
    if not observed_at:
        raise BusinessSignalError("observed_at is required")

    extra = extra or {}
    assert_no_pii_keys(extra)
    sanitized_extra = sanitize_business_payload(extra)

    idempotency_key = f"{source_system}:{source_record_id}:{metric_name}:{measurement_period}"
    signal_id = f"BSIG-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    data_quality_effective = data_quality
    if data_quality == "unavailable" and metric_value is not None:
        raise BusinessSignalError("data_quality=unavailable must not carry a metric_value")
    if data_quality == "estimated":
        # Estimated data must never silently present itself as verified fact.
        limitations = (limitations + " " if limitations else "") + "ESTIMATED: not a verified fact."

    record = {
        "signal_id": signal_id,
        "signal_type": signal_type,
        "source_system": source_system,
        "source_record_id": source_record_id,
        "experiment_id": experiment_id,
        "environment": environment,
        "observed_at": observed_at,
        "retrieved_at": now_iso(),
        "measurement_period": measurement_period,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "unit": unit,
        "data_quality": data_quality_effective,
        "coverage": coverage,
        "attribution_context": attribution_context,
        "evidence_refs": evidence_refs or [],
        "limitations": limitations,
        "provenance": f"file_adapter:{source_system}",
        "idempotency_key": idempotency_key,
        "schema_version": SCHEMA_VERSION,
        **sanitized_extra,
    }
    record, created = _write_json_idempotent(BUSINESS_SIGNALS_DIR, signal_id, idempotency_key, record)
    record["_created"] = created
    return record


# ---------------------------------------------------------------------------
# BUSINESS_SIGNAL entity (distinct from topic candidate)
# ---------------------------------------------------------------------------

VALID_BUSINESS_SIGNAL_STATUS = {"new", "under_review", "promoted_to_opportunity_candidate", "rejected", "stale"}


class OpportunityPromotionError(ValueError):
    pass


def create_business_signal_entity(
    *,
    signal_type: str,
    origin: str,
    evidence_refs: list,
    period: str,
    intensity: Optional[float] = None,
    confidence: Optional[float] = None,
    limitations: Optional[str] = None,
    experiment_id: Optional[str] = None,
) -> dict:
    """Create a BUSINESS_SIGNAL entity. This answers "is there evidence of
    demand/business opportunity", distinct from an editorial `topic
    candidate` (which answers "what could we write about"). Never
    auto-promotes to an opportunity candidate -- that requires a separate,
    explicit reasoning step (promote_business_signal_to_opportunity)."""
    if signal_type == "topic_candidate":
        raise BusinessSignalError(
            "signal_type='topic_candidate' is not a BUSINESS_SIGNAL; topic "
            "candidates and business signals are distinct entities (see "
            "EXTERNAL_INTEGRATION.md)."
        )
    assert_no_pii_keys({"evidence_refs": evidence_refs})
    bsig_id = f"BUSSIG-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    ts = now_iso()
    record = {
        "id": bsig_id,
        "signal_type": signal_type,
        "origin": origin,
        "evidence_refs": evidence_refs,
        "period": period,
        "intensity": intensity,
        "confidence": confidence,
        "limitations": limitations,
        "first_observed_at": ts,
        "last_observed_at": ts,
        "status": "new",
        "opportunity_candidate_ref": None,
        "experiment_id": experiment_id,
        "schema_version": SCHEMA_VERSION,
    }
    BUSINESS_SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    path = BUSINESS_SIGNALS_DIR / f"{bsig_id}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def promote_business_signal_to_opportunity(signal: dict, *, opportunity_candidate_ref: str, rationale: str) -> dict:
    """Explicit, separate reasoning step to promote a BUSINESS_SIGNAL into an
    Opportunity Candidate. Requires a non-empty rationale; refuses signals
    with no evidence or with status already terminal, so promotion cannot
    happen silently/automatically."""
    if not signal.get("evidence_refs"):
        raise OpportunityPromotionError("cannot promote a business signal with no evidence_refs")
    if signal.get("status") in {"rejected", "promoted_to_opportunity_candidate"}:
        raise OpportunityPromotionError(f"signal already in terminal status: {signal.get('status')}")
    if not rationale:
        raise OpportunityPromotionError("promotion requires an explicit rationale")
    updated = dict(signal)
    updated["status"] = "promoted_to_opportunity_candidate"
    updated["opportunity_candidate_ref"] = opportunity_candidate_ref
    updated["promotion_rationale"] = rationale
    updated["promoted_at"] = now_iso()
    return updated


# ---------------------------------------------------------------------------
# 5.3 External Cash Event
# ---------------------------------------------------------------------------

CASH_EVENT_STATES = [
    "OBSERVED", "REPORTED", "VERIFIED", "ATTRIBUTED", "RECONCILED", "LEDGER_POSTED",
]

CASH_EVENT_TRANSITIONS = {
    "OBSERVED": {"REPORTED"},
    "REPORTED": {"VERIFIED"},
    "VERIFIED": {"ATTRIBUTED"},
    "ATTRIBUTED": {"RECONCILED"},
    "RECONCILED": {"LEDGER_POSTED"},
    "LEDGER_POSTED": set(),
}

TRUSTED_READONLY_FINANCIAL_ADAPTERS: set[str] = set()
# Intentionally empty: no read-only financial verification adapter exists yet
# in this repository. Populate only via an explicit, documented system change
# (SYSTEM_EVOLUTION.md) -- never implicitly.

CASH_EVENT_KINDS = {"revenue", "refund", "chargeback", "other_external_inflow"}


class CashEventStateError(ValueError):
    pass


class CashEventVerificationError(ValueError):
    pass


def _cash_event_idempotency_key(source_system: str, source_record_id: str) -> str:
    return f"{source_system}:{source_record_id}"


def observe_external_cash_event(
    *,
    kind: str,
    amount_brl: float,
    source_system: str,
    source_record_id: str,
    observed_at: str,
    currency: str = "BRL",
) -> dict:
    """Create an ExternalCashEvent in OBSERVED state. Idempotent on
    (source_system, source_record_id): re-observing the same external record
    returns the existing event rather than creating a duplicate."""
    if kind not in CASH_EVENT_KINDS:
        raise CashEventStateError(f"invalid kind: {kind!r}; must be one of {sorted(CASH_EVENT_KINDS)}")
    if amount_brl <= 0:
        raise CashEventStateError("amount_brl must be positive; direction is determined by kind")
    idem_key = _cash_event_idempotency_key(source_system, source_record_id)
    event_id = f"ECE-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    data = {
        "id": event_id,
        "kind": kind,
        "amount_brl": round(amount_brl, 2),
        "currency": currency,
        "source_system": source_system,
        "source_record_id": source_record_id,
        "idempotency_key": idem_key,
        "observed_at": observed_at,
        "state": "OBSERVED",
        "state_history": [{"state": "OBSERVED", "at": now_iso(), "by": "system:file_adapter"}],
        "verification": None,
        "attribution": None,
        "ledger_reference": None,
        "schema_version": SCHEMA_VERSION,
    }
    record, created = _write_json_idempotent(EXTERNAL_CASH_EVENTS_DIR, event_id, idem_key, data)
    record["_created"] = created
    return record


def _advance_cash_event(event: dict, new_state: str, *, actor: str, note: str = "") -> dict:
    current = event["state"]
    if new_state not in CASH_EVENT_TRANSITIONS.get(current, set()):
        raise CashEventStateError(f"invalid transition {current} -> {new_state}")
    updated = dict(event)
    updated["state"] = new_state
    updated["state_history"] = list(event.get("state_history", [])) + [
        {"state": new_state, "at": now_iso(), "by": actor, "note": note}
    ]
    return updated


def report_external_cash_event(event: dict, *, report_source: str, note: str = "") -> dict:
    return _advance_cash_event(event, "REPORTED", actor=report_source, note=note)


def verify_external_cash_event(
    event: dict,
    *,
    human_confirmed: bool = False,
    human_statement: str = "",
    trusted_adapter_name: str = "",
) -> dict:
    """Advance REPORTED -> VERIFIED. This is the one place the custody rule
    "AI cannot self-elevate revenue to VERIFIED by inference" is enforced in
    code: the caller MUST supply either an explicit human confirmation
    (human_confirmed=True with a non-empty human_statement) or the name of a
    pre-registered trusted read-only financial adapter
    (TRUSTED_READONLY_FINANCIAL_ADAPTERS). Any other call, however the
    calling code justifies it, is refused."""
    if human_confirmed:
        if not human_statement:
            raise CashEventVerificationError("human_confirmed=True requires a non-empty human_statement")
        verifier = f"human:{human_statement}"
    elif trusted_adapter_name:
        if trusted_adapter_name not in TRUSTED_READONLY_FINANCIAL_ADAPTERS:
            raise CashEventVerificationError(
                f"'{trusted_adapter_name}' is not a registered trusted read-only "
                "financial adapter. No such adapter currently exists in this "
                "repository (TRUSTED_READONLY_FINANCIAL_ADAPTERS is empty by "
                "design); verification must come from an explicit human "
                "confirmation instead."
            )
        verifier = f"adapter:{trusted_adapter_name}"
    else:
        raise CashEventVerificationError(
            "refused: VERIFIED requires either human_confirmed=True with a "
            "human_statement, or a registered trusted_adapter_name. AI "
            "inference alone can never verify external revenue."
        )
    updated = _advance_cash_event(event, "VERIFIED", actor=verifier)
    updated["verification"] = {"verified_at": now_iso(), "verifier": verifier}
    return updated


def attribute_external_cash_event(
    event: dict,
    *,
    experiment_id: Optional[str] = None,
    opportunity_ref: Optional[str] = None,
    lead_id: Optional[str] = None,
    publication_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
) -> dict:
    """Advance VERIFIED -> ATTRIBUTED. Attribution to UNKNOWN is explicitly
    valid -- this function never fabricates an attribution when none of the
    fields are supplied."""
    attribution = {
        "experiment_id": experiment_id,
        "opportunity_ref": opportunity_ref,
        "lead_id": lead_id,
        "publication_id": publication_id,
        "campaign_id": campaign_id,
    }
    if not any(attribution.values()):
        attribution = {"status": "UNKNOWN"}
    else:
        attribution["status"] = "ATTRIBUTED"
    updated = _advance_cash_event(event, "ATTRIBUTED", actor="system:attribution")
    updated["attribution"] = attribution
    return updated


def reconcile_external_cash_event(event: dict, *, reconciled_by: str, note: str = "") -> dict:
    return _advance_cash_event(event, "RECONCILED", actor=reconciled_by, note=note)


def post_external_cash_event_to_ledger(event: dict, *, append_ledger_fn) -> dict:
    """Advance RECONCILED -> LEDGER_POSTED and post exactly one ledger entry,
    using the idempotency_key as the ledger reference so re-running this
    function on an already-posted event is a no-op rather than a duplicate
    entry. `append_ledger_fn` is injected (see capital_agent.append_ledger)
    so this module never needs to know the ledger file format directly."""
    if event["state"] == "LEDGER_POSTED":
        return event  # idempotent no-op
    if event["state"] != "RECONCILED":
        raise CashEventStateError(f"cannot post to ledger from state {event['state']}; must be RECONCILED")
    ledger_type = "revenue" if event["kind"] == "revenue" else "refund"
    append_ledger_fn(
        ledger_type,
        "external_cash_event",
        event["amount_brl"],
        f"External cash event {event['id']} ({event['kind']}) from {event['source_system']}",
        event["idempotency_key"],
    )
    updated = _advance_cash_event(event, "LEDGER_POSTED", actor="system:ledger_post")
    updated["ledger_reference"] = event["idempotency_key"]
    return updated


# ---------------------------------------------------------------------------
# 5.4 Canonical experiment schema/lifecycle
# ---------------------------------------------------------------------------

EXPERIMENT_LIFECYCLE_STATES = [
    "PLANNED", "READY_FOR_ACTIVATION", "ACTIVE", "PAUSED", "CLOSED",
]

EXPERIMENT_LIFECYCLE_TRANSITIONS = {
    "PLANNED": {"READY_FOR_ACTIVATION", "CLOSED"},
    "READY_FOR_ACTIVATION": {"ACTIVE", "PLANNED", "CLOSED"},
    "ACTIVE": {"PAUSED", "CLOSED"},
    "PAUSED": {"ACTIVE", "CLOSED"},
    "CLOSED": set(),
}


class ExperimentLifecycleError(ValueError):
    pass


def validate_experiment_transition(current_state: str, new_state: str) -> None:
    if current_state not in EXPERIMENT_LIFECYCLE_STATES:
        raise ExperimentLifecycleError(f"unknown current lifecycle_state: {current_state!r}")
    if new_state not in EXPERIMENT_LIFECYCLE_TRANSITIONS.get(current_state, set()):
        raise ExperimentLifecycleError(f"invalid experiment transition {current_state} -> {new_state}")


READY_FOR_ACTIVATION_REQUIRED_FIELDS = [
    "hypothesis", "success_metric", "failure_criteria", "kill_condition",
    "measurement_window", "attribution_model", "qualified_lead_definition",
    "revenue_attribution_definition", "resource_budget", "capital_budget_brl",
    "incremental_cost_policy", "privacy_policy_ref", "metrics_source",
    "dev_prod_separation_confirmed", "lead_capture_functional",
    "publication_handoff_defined", "external_revenue_reconciliation_defined",
]


def check_ready_for_activation(experiment: dict, *, open_p0_backlog_items: list) -> tuple[bool, list[str]]:
    """Return (ready, missing_reasons). Never mutates the experiment or sets
    lifecycle_state itself -- callers apply the transition explicitly via
    validate_experiment_transition once this confirms all preconditions."""
    missing = []
    for f in READY_FOR_ACTIVATION_REQUIRED_FIELDS:
        value = experiment.get(f)
        if value in (None, "", [], {}):
            missing.append(f"missing or empty: {f}")
        elif isinstance(value, str) and value.strip().lower().startswith(("not yet", "to be", "tbd", "unknown")):
            missing.append(f"not finalized: {f}")
    if open_p0_backlog_items:
        missing.append(f"open P0 platform backlog items block activation: {open_p0_backlog_items}")
    return (len(missing) == 0, missing)


def compute_roic(*, profit_brl: Optional[float], capital_deployed_brl: float) -> Optional[float]:
    """ROIC = profit / capital_deployed, but returns None (never inf/NaN)
    when capital_deployed_brl == 0. Callers must treat None as "not
    applicable, use alternative metrics", not as zero or as an error."""
    if profit_brl is None:
        return None
    if capital_deployed_brl == 0:
        return None
    return round(profit_brl / capital_deployed_brl, 4)


# ---------------------------------------------------------------------------
# 5.6 Publication Package + Publication Receipt
# ---------------------------------------------------------------------------

class PublicationError(ValueError):
    pass


def create_publication_package(
    *,
    content_brief_id: str,
    experiment_id: str,
    title: str,
    slug_suggestion: str,
    draft_ref: str,
    fact_check_ref: Optional[str],
    critic_ref: Optional[str],
    business_hypothesis_ref: Optional[str],
    cta_intent: Optional[str],
    attribution_tags: Optional[list] = None,
) -> dict:
    """A Publication Package is a request for handoff to the (independently
    operated) Editorial Platform. Creating one NEVER implies authorization to
    publish and never calls any CMS write endpoint -- this function only
    writes a local record."""
    pub_request_id = f"PUBREQ-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    record = {
        "publication_request_id": pub_request_id,
        "content_brief_id": content_brief_id,
        "experiment_id": experiment_id,
        "title": title,
        "slug_suggestion": slug_suggestion,
        "draft_ref": draft_ref,
        "fact_check_ref": fact_check_ref,
        "critic_ref": critic_ref,
        "business_hypothesis_ref": business_hypothesis_ref,
        "cta_intent": cta_intent,
        "attribution_tags": attribution_tags or [],
        "approval_required": True,
        "authorization_status": "NOT_AUTHORIZED",
        "created_at": now_iso(),
        "schema_version": SCHEMA_VERSION,
    }
    PUBLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = PUBLICATIONS_DIR / f"{pub_request_id}.package.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def ingest_publication_receipt(
    *,
    publication_request_id: str,
    platform_content_id: str,
    canonical_slug: str,
    canonical_url: str,
    published_at: str,
    environment: str,
    campaign_id: Optional[str],
    verification_source: str,
) -> dict:
    """Ingest a Publication Receipt returned by the platform after real
    publication. Idempotent on (publication_request_id, platform_content_id):
    ingesting the same receipt twice returns the existing record."""
    if environment not in VALID_ENVIRONMENTS:
        raise PublicationError(f"invalid environment: {environment!r}")
    if not platform_content_id or not verification_source:
        raise PublicationError("platform_content_id and verification_source are required")
    idem_key = f"{publication_request_id}:{platform_content_id}"
    receipt_id = f"PUBRCPT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    record = {
        "publication_id": receipt_id,
        "publication_request_id": publication_request_id,
        "platform_content_id": platform_content_id,
        "canonical_slug": canonical_slug,
        "canonical_url": canonical_url,
        "published_at": published_at,
        "environment": environment,
        "campaign_id": campaign_id,
        "verification_source": verification_source,
        "idempotency_key": idem_key,
        "schema_version": SCHEMA_VERSION,
    }
    record, created = _write_json_idempotent(PUBLICATIONS_DIR, receipt_id, idem_key, record)
    record["_created"] = created
    return record


# ---------------------------------------------------------------------------
# 5.7 Metric observations with provenance
# ---------------------------------------------------------------------------

NON_PRODUCTION_ENVIRONMENTS = {"dev", "test", "staging", "smoke", "e2e", "synthetic", "admin"}


class MetricObservationError(ValueError):
    pass


def create_metric_observation(
    *,
    experiment_id: str,
    metric_name: str,
    value: Optional[float],
    unit: str,
    period: str,
    source: str,
    environment: str,
    coverage: Optional[str],
    data_quality: str,
    limitations: Optional[str] = None,
) -> dict:
    if environment not in VALID_ENVIRONMENTS:
        raise MetricObservationError(f"invalid environment: {environment!r}")
    if data_quality not in VALID_DATA_QUALITY:
        raise MetricObservationError(f"invalid data_quality: {data_quality!r}")
    obs_id = f"MOBS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    record = {
        "id": obs_id,
        "experiment_id": experiment_id,
        "metric_name": metric_name,
        "value": value,
        "unit": unit,
        "period": period,
        "source": source,
        "environment": environment,
        "retrieved_at": now_iso(),
        "coverage": coverage,
        "data_quality": data_quality,
        "limitations": limitations,
        "eligible_for_official_evaluation": environment == "production",
        "schema_version": SCHEMA_VERSION,
    }
    METRIC_OBSERVATIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = METRIC_OBSERVATIONS_DIR / f"{obs_id}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def filter_official_evaluation_observations(observations: list[dict], *, activation_date: Optional[str]) -> list[dict]:
    """Filter a list of metric observations down to the ones eligible for
    official economic evaluation of an experiment: environment=='production'
    AND (no activation_date requirement, or period/retrieved_at on/after
    activation_date). Dev/test/synthetic/smoke/E2E/admin traffic and
    pre-activation data are excluded, never silently included."""
    out = []
    for obs in observations:
        if obs.get("environment") != "production":
            continue
        if activation_date:
            retrieved = obs.get("retrieved_at", "")
            if retrieved and retrieved < activation_date:
                continue
        out.append(obs)
    return out


# ---------------------------------------------------------------------------
# 5.9 Anti-platform-bias comparison
# ---------------------------------------------------------------------------

def build_alternatives_comparison(
    *,
    platform_opportunity: Optional[dict],
    best_financial_opportunity: Optional[dict],
    best_non_platform_opportunity: Optional[dict],
    benchmark: Optional[dict],
) -> dict:
    """Build the mandatory 4-way comparison for periodic capital-allocation
    review. Any missing category is recorded as NONE_AVAILABLE rather than
    fabricated."""
    def _slot(x, label):
        return x if x is not None else {"status": "NONE_AVAILABLE", "category": label}

    return {
        "generated_at": now_iso(),
        "platform_opportunity": _slot(platform_opportunity, "platform (EXP-001 or best platform-based experiment)"),
        "best_financial_opportunity": _slot(best_financial_opportunity, "best available financial opportunity"),
        "best_non_platform_opportunity": _slot(best_non_platform_opportunity, "best non-platform business opportunity"),
        "benchmark": _slot(benchmark, "do-nothing / benchmark"),
        "schema_version": SCHEMA_VERSION,
    }

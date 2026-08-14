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

import csv
import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except ImportError:  # pragma: no cover - exercised only if dep missing
    jsonschema = None
    _HAS_JSONSCHEMA = False

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state"
BUSINESS_SIGNALS_DIR = STATE_DIR / "business_signals"
EXTERNAL_CASH_EVENTS_DIR = STATE_DIR / "external_cash_events"
PUBLICATIONS_DIR = STATE_DIR / "publications"
METRIC_OBSERVATIONS_DIR = STATE_DIR / "metric_observations"
SCHEMAS_DIR = ROOT / "schemas"
LEDGER_FILE = ROOT / "data" / "ledger.csv"

SCHEMA_VERSION = "1.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON to `path` crash-safely: write to a sibling temp file, then
    os.replace() (atomic on POSIX and Windows) onto the final path. A crash
    mid-write leaves either the old file intact or the new one fully written
    -- never a truncated/corrupt file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex[:8]}")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


# ---------------------------------------------------------------------------
# Runtime JSON Schema validation
# ---------------------------------------------------------------------------

_SCHEMA_CACHE: dict[str, dict] = {}


class SchemaValidationError(ValueError):
    pass


def _load_schema(schema_filename: str) -> Optional[dict]:
    if schema_filename in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[schema_filename]
    path = SCHEMAS_DIR / schema_filename
    if not path.exists():
        return None
    schema = json.loads(path.read_text(encoding="utf-8"))
    _SCHEMA_CACHE[schema_filename] = schema
    return schema


def validate_against_schema(record: dict, schema_filename: str) -> None:
    """Validate `record` against schemas/<schema_filename> at runtime. Raises
    SchemaValidationError on any violation. If the jsonschema package is
    unavailable, falls back to a minimal required-fields + enum check so
    validation is never silently skipped. A MISSING schema file is also
    treated as a validation failure, never a silent skip: every entity type
    validated through this function has a corresponding schemas/*.json file
    checked into this repository (see schemas/), so a missing file means a
    caller passed the wrong filename or a schema was deleted/renamed without
    updating its call site -- both are bugs that must surface loudly, not be
    swallowed as "nothing to validate against"."""
    schema = _load_schema(schema_filename)
    if schema is None:
        raise SchemaValidationError(
            f"schema file schemas/{schema_filename} does not exist. Validation "
            "is never silently skipped in this repository -- either the "
            "schema file is missing/misnamed, or this call site should not "
            "be calling validate_against_schema at all."
        )
    if _HAS_JSONSCHEMA:
        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(record), key=lambda e: e.path)
        if errors:
            messages = "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
            raise SchemaValidationError(f"{schema_filename}: {messages}")
        return
    # Minimal stdlib fallback validator (required fields + enums only).
    for req in schema.get("required", []):
        if req not in record:
            raise SchemaValidationError(f"{schema_filename}: missing required field {req!r}")
    for key, prop in schema.get("properties", {}).items():
        if key in record and "enum" in prop and record[key] is not None:
            if record[key] not in prop["enum"]:
                raise SchemaValidationError(f"{schema_filename}: {key!r} value {record[key]!r} not in {prop['enum']}")


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


# ---------------------------------------------------------------------------
# PII value-level hardening (defense in depth beyond field-name allowlisting)
# ---------------------------------------------------------------------------
# Even an allowlisted field name (e.g. "landing_content", "service_interest")
# can carry a PII-shaped *value* if a caller pastes free text into it. These
# heuristics catch the common shapes; they are intentionally conservative
# (may over-flag) because false rejection is safe and false acceptance is not.

_EMAIL_VALUE_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_VALUE_RE = re.compile(r"(?:\+?\d[\d\-\s().]{7,}\d)")
_CPF_VALUE_RE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_CNPJ_VALUE_RE = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")

# Fields where a long/free-text value is expected and additionally checked
# for embedded PII-shaped substrings (as opposed to fields that are already
# short enumerations/ids and are cheap to check universally too).
_PII_VALUE_CHECKED_FIELDS = BUSINESS_PAYLOAD_ALLOWLIST


def _value_has_pii_shape(value: str) -> Optional[str]:
    if _EMAIL_VALUE_RE.search(value):
        return "email-shaped value"
    if _CPF_VALUE_RE.search(value):
        return "CPF-shaped value"
    if _CNPJ_VALUE_RE.search(value):
        return "CNPJ-shaped value"
    if _PHONE_VALUE_RE.search(value):
        return "phone-number-shaped value"
    return None


def assert_no_pii_shaped_values(payload: dict) -> None:
    """Hard-fail if any string value (at any nesting depth, in any key --
    including allowlisted keys) looks like it embeds PII, e.g. someone
    pastes an email address into a free-text 'note' or 'service_interest'
    field. This is a value-level check, distinct from (and in addition to)
    the field-*name* allowlist/denylist above."""
    def _walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                _walk(v, f"{path}{k}.")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _walk(item, f"{path}[{i}].")
        elif isinstance(obj, str):
            reason = _value_has_pii_shape(obj)
            if reason:
                raise PIIRejectedError(f"PII-shaped value at {path.rstrip('.')}: {reason}")
    _walk(payload)


def sanitize_business_payload(payload: dict) -> dict:
    """Allowlist-filter an external business payload. Denylisted keys are
    always stripped even if a caller mistakenly widens the allowlist.
    Returns a NEW dict; never mutates the input in place (defense against a
    caller reusing/logging the raw object after "sanitization"). Also
    hard-rejects the payload if any *value* of an allowlisted field looks
    like it embeds PII (email/phone/CPF/CNPJ shaped substrings) -- the
    allowlist only vouches for field names, never for their contents.
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
    assert_no_pii_shaped_values(clean)
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
    existing record is returned unchanged. Returns (record, created).

    P2 hardening (prompt-hardening-final-capital-agent-v0.2.md section 9):
    the naive version of this (scan dir for idempotency_key, then write if
    absent) has a real race: two concurrent processes can both finish the
    scan before either writes, and both then write distinct <record_id>.json
    files for the same idempotency_key, producing a duplicate record.

    Fix: a deterministic per-idempotency_key claim file, created with an
    atomic O_CREAT|O_EXCL open (a single filesystem syscall the OS
    guarantees only one caller can win). The winner writes the real record;
    every loser (this call, or a retry) reads back the winner's record_id
    from the claim file and returns the winner's persisted record instead of
    writing anything -- so retry/concurrency can never produce a duplicate.
    Post-review hardening (2026-08-13 Codex review of this PR): the first
    version of this fix had three real gaps, now closed:
    - the claim filename was a lossy char-substitution of the raw key
      (`a/b` and `a?b` collided), and a claim's content was never checked
      against the requested key -- a hash collision or corrupted claim could
      silently hand back the wrong record. Fixed by always hashing the full
      key (sha256, no collision-prone substitution) and validating
      `claim["idempotency_key"] == idempotency_key` on every read.
    - a crash between `os.open(O_CREAT|O_EXCL)` and the following
      `os.write` left an empty, permanently-unclaimable claim file (every
      future caller for that key would poll for 1s and then hard-fail
      forever). Fixed: an empty/corrupt claim is now treated as an
      abandoned claim and taken over (best-effort, single extra open) rather
      than wedging the key shut permanently.
    - records created by the pre-index version of this function (a plain
      `<record_id>.json` with an `idempotency_key` field, no claim file)
      were invisible to the new claim-only lookup, so replaying an old
      key would create a second record. Fixed: on a claim-miss, fall back
      to scanning `dir_path` once for a legacy record with a matching
      `idempotency_key` and backfill a claim for it before proceeding.
    """
    dir_path.mkdir(parents=True, exist_ok=True)
    index_dir = dir_path / "_idempotency_index"
    index_dir.mkdir(parents=True, exist_ok=True)
    key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    index_path = index_dir / f"{key_hash}.json"

    def _read_claim() -> Optional[dict]:
        try:
            claim = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if claim.get("idempotency_key") != idempotency_key:
            return None
        return claim

    def _read_claimed_record() -> Optional[dict]:
        claim = _read_claim()
        if claim is None:
            return None
        claimed_path = dir_path / f"{claim['record_id']}.json"
        try:
            return json.loads(claimed_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def _write_claim_content(claim_record_id: str) -> None:
        index_path.write_text(
            json.dumps({"record_id": claim_record_id, "idempotency_key": idempotency_key}),
            encoding="utf-8",
        )

    def _legacy_scan_for_existing() -> Optional[tuple[dict, str]]:
        for existing_path in sorted(dir_path.glob("*.json")):
            try:
                existing = json.loads(existing_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if existing.get("idempotency_key") == idempotency_key:
                return existing, existing_path.stem
        return None

    # Fast path: already claimed (common case -- no lock contention needed
    # to observe a fact that's already settled).
    existing = _read_claimed_record()
    if existing is not None:
        return existing, False

    try:
        fd = os.open(str(index_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        # Someone else's claim file exists for this key. It may be: (a) a
        # winner's valid, populated claim not yet visible to our first read
        # (race) -- poll briefly; or (b) an abandoned claim left by a
        # process that crashed between os.open and os.write -- detect via
        # the claim being empty/unreadable and take it over.
        for _ in range(200):
            existing = _read_claimed_record()
            if existing is not None:
                return existing, False
            claim = _read_claim()
            if claim is None and not index_path.exists():
                break  # claim vanished (shouldn't happen); fall through to retry create
            try:
                claim_raw = index_path.read_text(encoding="utf-8")
            except OSError:
                claim_raw = ""
            if not claim_raw.strip():
                # Abandoned/empty claim: take it over rather than wedging
                # this key shut forever. We are about to write our own
                # record (record_id, this call's), so the claim must point
                # to it.
                _write_claim_content(record_id)
                break
            time.sleep(0.005)
        else:
            raise RuntimeError(
                f"idempotency race unresolved for key {idempotency_key!r}: claim file exists "
                "but its record never became readable"
            )
        # Fell through the loop (broke out): re-check once more, then
        # proceed to write as if we own the claim now.
        existing = _read_claimed_record()
        if existing is not None:
            return existing, False
    else:
        # We only need O_CREAT|O_EXCL for its exclusivity guarantee (whoever
        # wins this open owns the key); write the actual claim content
        # separately via `_write_claim_content()` rather than through this
        # fd, then close it. Caught by ruff (F841, unused `fd`) while
        # adding lint tooling in the engineering-quality round-3 pass -- a
        # real file-descriptor leak on every successful call, since nothing
        # else closed it.
        #
        # Fixing the leak surfaced a second, more serious pre-existing bug
        # found by running the full suite on Linux CI for the first time
        # (round 3): this winner path never called `_write_claim_content()`
        # at all before this fix. The claim file existed (empty, just
        # created by O_CREAT|O_EXCL) but was never populated with
        # `{record_id, idempotency_key}`. Every concurrent loser hitting
        # `FileExistsError` below polls, finds the claim still empty
        # (because the winner never wrote it), concludes it must be
        # abandoned, and takes it over -- so under real contention (a
        # `threading.Barrier`-synchronized 8-way race in
        # WriteJsonIdempotentRaceTests, which happened to not trigger this
        # reliably on Windows' scheduler but did on Linux CI) multiple
        # callers could each believe they won and each write their own
        # data record for the same idempotency_key, exactly the duplicate
        # this function exists to prevent. Fixed by populating the claim
        # here, before any other caller can observe the "exists but empty"
        # state.
        os.close(fd)
        _write_claim_content(record_id)

    # We hold (or just took over) the claim. Before writing a brand-new
    # record, check for a legacy pre-index record with this idempotency_key
    # so upgrading to this function's claim-based lookup never duplicates
    # data written before the claim index existed.
    legacy = _legacy_scan_for_existing()
    if legacy is not None:
        legacy_data, legacy_record_id = legacy
        # Bug found alongside the winner-path claim fix above (round 3):
        # this used to write the claim pointing at `record_id` -- this
        # call's own freshly-generated id, which is never actually created
        # on this path since we return the legacy record instead -- so the
        # claim permanently pointed at a nonexistent file. Not a
        # duplication risk (every future call would just re-run this same
        # legacy scan and get the right *data* back), but it silently
        # defeated the claim's fast path forever for any backfilled key.
        # Fixed: point the claim at the legacy record's own filename stem.
        _write_claim_content(legacy_record_id)
        return legacy_data, False

    tmp_path = dir_path / f".{record_id}.json.tmp-{uuid.uuid4().hex[:8]}"
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp_path, dir_path / f"{record_id}.json")
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
    validate_against_schema(record, "business_signal.schema.json")
    record, created = _write_json_idempotent(BUSINESS_SIGNALS_DIR, signal_id, idempotency_key, record)
    record["_created"] = created
    return record


# ---------------------------------------------------------------------------
# BusinessObservation: one raw/individual external data point (e.g. "one lead
# asked about X on this date"). Distinct from BusinessSignal (below), which
# is the higher-level, evidence-with-confidence-and-provenance entity that a
# BusinessSignal derives from one or more BusinessObservation records. The
# link is explicit and traceable via BusinessObservation.observation_id
# appearing in BusinessSignal.evidence_refs / derived_from_observation_ids.
# ---------------------------------------------------------------------------

BUSINESS_OBSERVATIONS_DIR_NAME = "business_observations"


class BusinessObservationError(ValueError):
    pass


def create_business_observation(
    *,
    observation_type: str,
    source_system: str,
    source_record_id: str,
    observed_at: str,
    detail: Optional[str] = None,
    metric_name: Optional[str] = None,
    metric_value: Optional[float] = None,
    unit: Optional[str] = None,
    experiment_id: Optional[str] = None,
) -> dict:
    """Record one raw external observation ("3 leads asked about X this
    week" is itself a BusinessSignal built FROM several of these smaller
    facts, e.g. one BusinessObservation per lead-touch). A BusinessObservation
    carries no confidence/intensity scoring of its own -- that synthesis
    belongs to BusinessSignal. Idempotent on (source_system, source_record_id,
    observation_type)."""
    if not source_system or not source_record_id:
        raise BusinessObservationError("source_system and source_record_id are required for provenance")
    if not observed_at:
        raise BusinessObservationError("observed_at is required")
    if detail:
        assert_no_pii_shaped_values({"detail": detail})
    obs_dir = STATE_DIR / BUSINESS_OBSERVATIONS_DIR_NAME
    idem_key = f"{source_system}:{source_record_id}:{observation_type}"
    obs_id = f"BOBS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    record = {
        "observation_id": obs_id,
        "observation_type": observation_type,
        "source_system": source_system,
        "source_record_id": source_record_id,
        "observed_at": observed_at,
        "retrieved_at": now_iso(),
        "detail": detail,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "unit": unit,
        "experiment_id": experiment_id,
        "idempotency_key": idem_key,
        "schema_version": SCHEMA_VERSION,
    }
    validate_against_schema(record, "business_observation.schema.json")
    record, created = _write_json_idempotent(obs_dir, obs_id, idem_key, record)
    record["_created"] = created
    return record


# ---------------------------------------------------------------------------
# BUSINESS_SIGNAL entity (distinct from topic candidate, and distinct from
# BusinessObservation above -- a BusinessSignal is a pattern claim derived
# FROM one or more BusinessObservation records, never a raw fact itself).
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
    derived_from_observation_ids: Optional[list] = None,
) -> dict:
    """Create a BUSINESS_SIGNAL entity. This answers "is there evidence of
    demand/business opportunity", distinct from an editorial `topic
    candidate` (which answers "what could we write about"), and distinct
    from a BusinessObservation (a single raw fact). A BusinessSignal
    aggregates/derives from one or more BusinessObservation records; that
    relationship is made explicit and traceable via
    `derived_from_observation_ids` (BusinessObservation.observation_id
    values) in addition to the free-form `evidence_refs`. Never
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
        "derived_from_observation_ids": derived_from_observation_ids or [],
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
    validate_against_schema(record, "business_signal_pattern.schema.json")
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

# Ledger `type` used for each ExternalCashEvent kind, and whether it adds to
# (True) or subtracts from (False) cash / recognized revenue. A chargeback is
# a REVERSAL of previously recognized revenue -- it must reduce cash/revenue,
# not be posted as a same-signed inflow like a genuine refund-to-us. See
# src/capital_agent.py cash_balance() which must treat "chargeback" as a
# subtraction and "refund"/"other_external_inflow" as additions.
CASH_EVENT_KIND_TO_LEDGER_TYPE = {
    "revenue": "revenue",
    "refund": "refund",
    "chargeback": "chargeback",
    "other_external_inflow": "other_external_inflow",
}


class CashEventStateError(ValueError):
    pass


class CashEventVerificationError(ValueError):
    pass


def _cash_event_idempotency_key(source_system: str, source_record_id: str) -> str:
    return f"{source_system}:{source_record_id}"


def _cash_event_path(event_id: str) -> Path:
    return EXTERNAL_CASH_EVENTS_DIR / f"{event_id}.json"


def _persist_cash_event(record: dict) -> dict:
    """Crash-safe persistence of the FULL current record (including
    state_history) to state/external_cash_events/<id>.json. This is what
    makes every OBSERVED->...->LEDGER_POSTED transition durable: callers
    that only used the in-memory return value and never called this would
    lose the transition on process exit. Every transition function below
    calls this before returning."""
    on_disk = {k: v for k, v in record.items() if k != "_created"}
    validate_against_schema(on_disk, "external_cash_event.schema.json")
    _atomic_write_json(_cash_event_path(record["id"]), on_disk)
    return record


def load_external_cash_event(event_id: str) -> dict:
    path = _cash_event_path(event_id)
    if not path.exists():
        raise CashEventStateError(f"no persisted ExternalCashEvent with id {event_id!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_external_cash_events(*, state: Optional[str] = None) -> list[dict]:
    EXTERNAL_CASH_EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(EXTERNAL_CASH_EVENTS_DIR.glob("*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if state is None or rec.get("state") == state:
            out.append(rec)
    return out


def migrate_legacy_cash_event_record(record: dict) -> dict:
    """Historical-compatibility shim: state files written by the earlier
    (pre-hardening) implementation are missing nothing structurally (the
    schema didn't change), but may be missing `_created`/newer optional keys
    or may have been left stale in memory-only form (never persisted at
    all -- those simply won't exist on disk and are not "migrated", they are
    lost, which is exactly the bug fix #1 addresses going forward). This
    function fills in any missing optional keys so older records validate
    against the current schema/consumers without raising."""
    migrated = dict(record)
    migrated.setdefault("verification", None)
    migrated.setdefault("attribution", None)
    migrated.setdefault("ledger_reference", None)
    migrated.setdefault("schema_version", SCHEMA_VERSION)
    migrated.setdefault("state_history", [{"state": migrated.get("state", "OBSERVED"), "at": migrated.get("observed_at", now_iso()), "by": "migration:unknown"}])
    return migrated


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
    validate_against_schema(data, "external_cash_event.schema.json")
    record, created = _write_json_idempotent(EXTERNAL_CASH_EVENTS_DIR, event_id, idem_key, data)
    record["_created"] = created
    return record


def find_stale_cash_events(*, grace_period_seconds: float, states: tuple = ("OBSERVED",)) -> list[dict]:
    """Return persisted ExternalCashEvents currently sitting in one of
    `states` whose most recent state_history entry is older than
    `grace_period_seconds`. Used by the `attribution_pending_too_long`-style
    staleness checks and by operational monitoring; never mutates state."""
    now = datetime.now(timezone.utc)
    stale = []
    for rec in list_external_cash_events():
        if rec.get("state") not in states:
            continue
        history = rec.get("state_history") or []
        if not history:
            continue
        last_at_raw = history[-1].get("at")
        try:
            last_at = datetime.fromisoformat(last_at_raw)
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        age_s = (now - last_at.astimezone(timezone.utc)).total_seconds()
        if age_s >= grace_period_seconds:
            stale.append({**rec, "_age_seconds": age_s})
    return stale


class StaleCashEventStateError(CashEventStateError):
    """Raised when a transition is attempted from an in-memory `event` dict
    whose `state` no longer matches the canonically persisted state on disk.
    This is an optimistic-concurrency guard: without it, a caller holding a
    stale in-memory copy (e.g. fetched before another process/transition
    advanced the record) could clobber the persisted state backward or
    silently redo a transition that already happened, corrupting
    state_history and potentially re-triggering downstream effects (like a
    second ledger post attempt from a stale RECONCILED copy)."""


def _advance_cash_event(event: dict, new_state: str, *, actor: str, note: str = "") -> dict:
    """Advance `event` to `new_state`. Always reloads the canonical persisted
    record from disk first and requires event["state"] to match it exactly
    (optimistic concurrency check) before allowing the transition -- an
    in-memory copy that has fallen behind the persisted state is refused
    rather than silently applied on top of stale data."""
    event_id = event.get("id")
    if event_id is not None:
        path = _cash_event_path(event_id)
        if path.exists():
            persisted = json.loads(path.read_text(encoding="utf-8"))
            persisted_state = persisted.get("state")
            expected_state = event.get("state")
            if persisted_state != expected_state:
                raise StaleCashEventStateError(
                    f"stale in-memory state for cash event {event_id!r}: caller "
                    f"expected state {expected_state!r} but persisted state is "
                    f"{persisted_state!r}. Reload the event with "
                    "load_external_cash_event() before retrying the transition."
                )
            # Use the canonical persisted record as the base for the update so
            # any fields the caller's in-memory copy lacked/dropped are not
            # lost, while still applying the caller-provided transition.
            event = persisted
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
    updated = _advance_cash_event(event, "REPORTED", actor=report_source, note=note)
    return _persist_cash_event(updated)


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
    return _persist_cash_event(updated)


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
    return _persist_cash_event(updated)


def reconcile_external_cash_event(event: dict, *, reconciled_by: str, note: str = "") -> dict:
    updated = _advance_cash_event(event, "RECONCILED", actor=reconciled_by, note=note)
    return _persist_cash_event(updated)


def _find_ledger_row_by_reference(reference: str) -> Optional[dict]:
    """Return the ledger row (as a dict keyed by header column name) whose
    `reference` column equals `reference`, or None if no such row exists."""
    if not LEDGER_FILE.exists():
        return None
    with LEDGER_FILE.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return None
        try:
            ref_idx = header.index("reference")
        except ValueError:
            ref_idx = len(header) - 1
        for row in reader:
            if len(row) > ref_idx and row[ref_idx] == reference:
                return dict(zip(header, row))
    return None


def _ledger_reference_posted(reference: str) -> bool:
    """Check the ledger file itself (not just in-memory/local state) for a
    row whose reference column equals `reference`. This is the crash-safety
    backstop: if a previous process crashed AFTER appending the ledger line
    but BEFORE persisting the event's LEDGER_POSTED state, this lets a retry
    detect that the line already exists and skip re-appending, instead of
    relying purely on an in-memory guard that a crash would have destroyed."""
    return _find_ledger_row_by_reference(reference) is not None


class LedgerReferenceConflictError(CashEventStateError):
    """Raised when a ledger row already exists under a reference we are
    about to (re-)post, but its type/amount/category diverge from what this
    call expects. Mere key presence is not sufficient evidence the row is
    "the same fact" -- a differing amount/type/category under the same
    reference means either data corruption or a reference collision, and
    silently treating that as "already done" would hide a real
    discrepancy instead of surfacing it."""


def _assert_ledger_reference_matches(reference: str, *, expected_type: str, expected_amount: float, expected_category: str) -> None:
    row = _find_ledger_row_by_reference(reference)
    if row is None:
        return
    mismatches = []
    if row.get("type") != expected_type:
        mismatches.append(f"type: existing={row.get('type')!r} expected={expected_type!r}")
    if row.get("category") != expected_category:
        mismatches.append(f"category: existing={row.get('category')!r} expected={expected_category!r}")
    try:
        existing_amount = round(float(row.get("amount_brl", "nan")), 2)
    except ValueError:
        existing_amount = None
    if existing_amount != round(expected_amount, 2):
        mismatches.append(f"amount_brl: existing={row.get('amount_brl')!r} expected={expected_amount!r}")
    if mismatches:
        raise LedgerReferenceConflictError(
            f"ledger reference {reference!r} already exists but diverges from "
            f"the expected posting ({'; '.join(mismatches)}); refusing to treat "
            "this as an already-completed idempotent post."
        )


class LedgerPostLockError(CashEventStateError):
    """Raised when another process appears to be posting the same
    idempotency key concurrently and does not finish within the wait
    budget."""


# Conservative stale-lock threshold: a ledger-post critical section is a
# handful of local filesystem operations and should never legitimately hold
# the lock this long. If a lock file is older than this AND (best-effort) its
# owning PID is no longer running, it is treated as orphaned by a crashed
# process rather than an in-progress post. PID-liveness checking is
# best-effort and platform-dependent (os.kill(pid, 0) is not reliable on
# Windows); when it cannot be determined, age alone is the deciding factor --
# a deliberate tradeoff toward eventual recoverability over never taking over
# a lock that might theoretically still be legitimately held.
STALE_LOCK_MAX_AGE_SECONDS = 300


def _pid_is_running(pid: int) -> Optional[bool]:
    """Best-effort liveness check. Returns True/False when determinable, None
    when this platform/permission set can't tell (caller should then fall
    back to the age-only heuristic)."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # process exists, we just can't signal it
    except OSError:
        return None


def _write_lock_owner_info(fd: int, *, nonce: Optional[str] = None) -> None:
    payload = {"pid": os.getpid(), "created_at": now_iso()}
    if nonce is not None:
        payload["nonce"] = nonce
    os.write(fd, json.dumps(payload).encode("utf-8"))


# Documented recovery threshold, not an automatic one: a stale-lock takeover
# is only a handful of local filesystem operations (open, write, close,
# replace, unlink), so an operator manually clearing an orphaned
# `<lock_path>.takeover-arbitration` file older than this can be confident
# its creator crashed rather than merely stalled. Not read by
# `_attempt_stale_lock_takeover` itself -- see the ABA-race comment there
# for why this function does not attempt automatic recovery of that file.
TAKEOVER_ARBITRATION_MAX_AGE_SECONDS = 5


def _attempt_stale_lock_takeover(lock_path: Path) -> bool:
    """Take over a stale lock, with real (not merely observed) mutual
    exclusion between racing takeover attempts.

    An earlier version of this function tagged each takeover attempt with a
    random nonce, called `os.replace(tmp, lock_path)`, then re-read
    `lock_path` back to check whether its own nonce was the one that
    persisted. That is NOT sufficient: `os.replace` is atomic (no torn
    file is ever visible) but not exclusive. Two racers can interleave as
    A-replace, A-read-back-sees-A (A now believes it won), B-replace,
    B-read-back-sees-B (B now also believes it won) -- A already returned
    True for the caller before B's replace even happened. The read-back
    only proves "I was the writer as of my read", not "no one else will
    write after me". An independent (Codex) review of the nonce-only
    version caught this.

    The actual fix: make the *takeover attempt itself* exclusive, not just
    its result observable. A short-lived arbitration file at
    `lock_path` + `.takeover-arbitration`, created with a real
    `O_CREAT|O_EXCL` (a genuinely exclusive filesystem operation, unlike
    `os.replace`), is required before a caller is allowed to `os.replace()`
    onto `lock_path` at all. Exactly one racer can hold the arbitration
    file at a time, so exactly one racer performs the replace at a time;
    every other racer's `O_EXCL` create fails immediately and it reports
    "did not win" without touching `lock_path`. The arbitration file is
    removed in a `finally` so the next racer (if `lock_path` is still
    stale, which it normally will not be once a takeover just succeeded)
    can proceed."""
    arbitration_path = lock_path.with_suffix(lock_path.suffix + ".takeover-arbitration")
    try:
        afd = os.open(str(arbitration_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(afd)
    except FileExistsError:
        # Deliberately does NOT attempt to age out and take over a stale
        # arbitration file itself. An earlier version did (mirroring
        # `_lock_is_stale`'s age-based recovery), but an independent (Codex)
        # review caught a real ABA race in it: process A holds the
        # arbitration file but stalls past the age threshold (GC pause,
        # scheduler delay, debugger breakpoint -- not necessarily a crash);
        # process B judges it stale, deletes it, and creates its own; A
        # resumes, reaches its own `finally`, and unconditionally deletes
        # what is now B's arbitration file, at which point a third racer C
        # can win concurrently with B still "inside" its critical section.
        # The arbitration file's only job is to make ONE takeover happen at
        # a time; recovering it opportunistically defeats that. Since the
        # guarded section is a handful of local filesystem calls (at most
        # low milliseconds under normal operation), the correct failure
        # mode for a genuinely orphaned arbitration file (its creator was
        # killed, not just delayed) is: every racer keeps returning False,
        # `acquire_generic_lock`'s own `max_lock_wait_s` eventually raises
        # `LedgerPostLockError` (an explicit, visible failure), and an
        # operator manually removes `<lock_path>.takeover-arbitration` --
        # consistent with this project's preference for explicit human
        # recovery over auto-magic in edge cases (see
        # AI_OPERATING_MANUAL.md's custody invariant discussion). This is
        # the same reasoning `TAKEOVER_ARBITRATION_MAX_AGE_SECONDS` used to
        # encode as an automatic timeout; it is now unused by this function
        # and kept only as a documented recovery threshold for that manual
        # step.
        return False  # another racer is (or very recently was) taking over

    try:
        # Re-check staleness now that we hold the arbitration file. Another
        # racer may have already won a takeover (or acquired the lock
        # normally after it was released) while we were waiting; in that
        # case lock_path is no longer stale and we must not touch it. This
        # makes the function's own contract self-contained -- exactly one
        # caller ever performs the replace for a given "lock became stale"
        # episode -- rather than relying on every caller re-checking
        # `_lock_is_stale` immediately before calling this function (which
        # `acquire_generic_lock` does, but a future or different caller
        # might not).
        if not _lock_is_stale(lock_path):
            return False
        nonce = uuid.uuid4().hex
        tmp_path = lock_path.with_suffix(lock_path.suffix + f".takeover-{nonce[:8]}")
        tfd = os.open(str(tmp_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            _write_lock_owner_info(tfd, nonce=nonce)
        finally:
            os.close(tfd)
        try:
            os.replace(tmp_path, lock_path)
        except OSError:
            # Windows can raise a transient PermissionError/sharing
            # violation if lock_path is momentarily open elsewhere (e.g. a
            # reader). We hold the arbitration file, so no other takeover
            # attempt caused this; treat it as a transient failure to
            # retry, not a crash.
            try:
                tmp_path.unlink()
            except OSError:
                pass
            return False
        return True
    finally:
        try:
            arbitration_path.unlink()
        except OSError:
            pass


def _lock_is_stale(lock_path: Path) -> bool:
    try:
        age_s = time.time() - lock_path.stat().st_mtime
    except OSError:
        return False
    if age_s < STALE_LOCK_MAX_AGE_SECONDS:
        return False
    owner_pid = None
    try:
        content = json.loads(lock_path.read_text(encoding="utf-8"))
        owner_pid = content.get("pid")
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    if owner_pid is not None:
        alive = _pid_is_running(int(owner_pid))
        if alive is True:
            return False  # owner process demonstrably still running; not stale
    return True  # old enough, and owner is dead or undeterminable


def acquire_generic_lock(lock_path: Path, *, max_lock_wait_s: float) -> bool:
    """Generic crash-recoverable O_CREAT|O_EXCL mutual-exclusion lock, for
    callers (e.g. capital_agent.cmd_record_reserve_asset) that need to
    serialize a read-check-write critical section but have no
    idempotency-key-specific "already done" check like
    `_ledger_reference_posted` to short-circuit on. Same stale-lock
    takeover strategy as `_acquire_ledger_post_lock` (owner PID + timestamp,
    atomic rename-based takeover), factored out here so both call sites
    share one crash-recovery implementation instead of drifting apart.
    Caller is responsible for unlinking `lock_path` when done (best-effort;
    a leftover lock self-heals via staleness detection on the next call)."""
    start = time.monotonic()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                _write_lock_owner_info(fd)
            finally:
                os.close(fd)
            return True
        except FileExistsError:
            if _lock_is_stale(lock_path) and _attempt_stale_lock_takeover(lock_path):
                return True
            if time.monotonic() - start > max_lock_wait_s:
                raise LedgerPostLockError(
                    f"could not acquire lock {lock_path} within {max_lock_wait_s}s "
                    "(concurrent writer appears to be in progress)"
                )
            time.sleep(0.02)


def _acquire_ledger_post_lock(lock_path: Path, *, idem_key: str, max_lock_wait_s: float) -> bool:
    """Acquire the O_CREAT|O_EXCL ledger-post lock at `lock_path`, with
    crash-recoverable stale-lock takeover. A plain finally-block unlink is not
    crash-recoverable: if the process holding the lock is killed between
    creating it and the finally block, the lock file is orphaned forever and
    every future post attempt for that idempotency_key would hang/fail. This
    adds: (1) owner PID + creation timestamp written into the lock file so a
    later process can evaluate it, and (2) an atomic rename-based takeover
    (write our own claim to a temp file, then os.replace() it onto the stale
    lock path) rather than unlinking-then-recreating, which would reopen a
    window for two processes to both believe they hold the lock."""
    start = time.monotonic()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                _write_lock_owner_info(fd)
            finally:
                os.close(fd)
            return True
        except FileExistsError:
            if _ledger_reference_posted(idem_key):
                return False  # another process already finished posting it
            if _lock_is_stale(lock_path) and _attempt_stale_lock_takeover(lock_path):
                return True
            if time.monotonic() - start > max_lock_wait_s:
                raise LedgerPostLockError(
                    f"could not acquire ledger-post lock for {idem_key!r} within "
                    f"{max_lock_wait_s}s (concurrent post appears to be in progress)"
                )
            time.sleep(0.02)


def post_external_cash_event_to_ledger(event: dict, *, append_ledger_fn, max_lock_wait_s: float = 2.0) -> dict:
    """Advance RECONCILED -> LEDGER_POSTED and post exactly one ledger entry,
    using the idempotency_key as the ledger reference so re-running this
    function on an already-posted event is a no-op rather than a duplicate
    entry. `append_ledger_fn` is injected (see capital_agent.append_ledger)
    so this module never needs to know the ledger file format directly.

    Crash-safety: uses a write-ahead file lock (atomic O_CREAT|O_EXCL) keyed
    on the idempotency_key plus a check of the ledger file itself (not just
    in-memory event.state) before appending, so a crash between "decided to
    post" and "wrote the ledger line" cannot produce a duplicate line on
    retry, and two concurrent callers racing on the same idempotency_key
    cannot both post.

    P1 hardening (prompt-hardening-final-capital-agent-v0.2.md section 5):
    the caller-supplied `event` is used ONLY to identify which persisted
    record to act on (`event["id"]`) and, optionally, as an expected-state
    check. Every financial fact -- amount_brl, kind, source_system,
    idempotency_key, state -- is re-derived from the record reloaded fresh
    from disk (the canonical persisted state) at the top of this call, never
    from the in-memory object the caller passed in. This closes the path
    where a stale or adulterated in-memory copy (e.g. held across a retry,
    or mutated by a bug elsewhere) could post a different amount/kind/source
    than what was actually verified and persisted.
    """
    event_id = event["id"]
    canonical = load_external_cash_event(event_id)

    # Post-review fix (2026-08-13 Codex review of this PR): LEDGER_POSTED is
    # checked BEFORE the expected_state precondition, not after. A caller
    # that posted successfully, then lost the response and retried with its
    # last-known RECONCILED object, must still get back the idempotent
    # no-op -- not a stale-state error -- because "already succeeded" is not
    # a staleness problem, it is the success case retry exists to handle.
    # expected_state stays useful as a precondition for callers advancing a
    # transition that has NOT yet happened (still-pending states).
    if canonical["state"] == "LEDGER_POSTED":
        return canonical  # idempotent no-op, even if caller's object is stale

    expected_state = event.get("state")
    if expected_state is not None and expected_state != canonical["state"]:
        raise CashEventStateError(
            f"stale event object for {event_id!r}: caller expected state "
            f"{expected_state!r} but persisted canonical state is "
            f"{canonical['state']!r}. Reload the event before retrying."
        )

    if canonical["state"] != "RECONCILED":
        raise CashEventStateError(f"cannot post to ledger from state {canonical['state']}; must be RECONCILED")

    idem_key = canonical["idempotency_key"]
    wal_dir = EXTERNAL_CASH_EVENTS_DIR / "_wal"
    wal_dir.mkdir(parents=True, exist_ok=True)
    lock_path = wal_dir / (re.sub(r"[^A-Za-z0-9_.-]", "_", idem_key) + ".lock")

    acquired = _acquire_ledger_post_lock(lock_path, idem_key=idem_key, max_lock_wait_s=max_lock_wait_s)

    try:
        # Re-reload under the lock: another process may have posted (or
        # advanced) this event between the check above and lock acquisition.
        canonical = load_external_cash_event(event_id)
        if canonical["state"] == "LEDGER_POSTED":
            return canonical  # idempotent no-op, race resolved
        if canonical["state"] != "RECONCILED":
            raise CashEventStateError(f"cannot post to ledger from state {canonical['state']}; must be RECONCILED")

        ledger_type = CASH_EVENT_KIND_TO_LEDGER_TYPE[canonical["kind"]]
        _assert_ledger_reference_matches(
            idem_key, expected_type=ledger_type, expected_amount=canonical["amount_brl"],
            expected_category="external_cash_event",
        )
        if not _ledger_reference_posted(idem_key):
            append_ledger_fn(
                ledger_type,
                "external_cash_event",
                canonical["amount_brl"],
                f"External cash event {canonical['id']} ({canonical['kind']}) from {canonical['source_system']}",
                idem_key,
            )
        updated = _advance_cash_event(canonical, "LEDGER_POSTED", actor="system:ledger_post")
        updated["ledger_reference"] = idem_key
        return _persist_cash_event(updated)
    finally:
        if acquired:
            try:
                lock_path.unlink()
            except OSError:
                pass


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


def validate_experiment_transition(current_state: Optional[str], new_state: str) -> None:
    # current_state is Optional because callers pass experiment.get(...) at
    # the call site, which is `str | None` for a malformed/missing
    # lifecycle_state field. Widened here (mypy, engineering-quality round
    # 3) to match what this function's own body already handles correctly
    # rather than forcing a caller-side cast: `None not in
    # EXPERIMENT_LIFECYCLE_STATES` is True, so a missing lifecycle_state
    # already fails closed with a clear error below, not a crash or a
    # silent pass-through. No behavior change, only an accurate signature.
    if current_state not in EXPERIMENT_LIFECYCLE_STATES:
        raise ExperimentLifecycleError(f"unknown current lifecycle_state: {current_state!r}")
    if new_state not in EXPERIMENT_LIFECYCLE_TRANSITIONS.get(current_state, set()):
        raise ExperimentLifecycleError(f"invalid experiment transition {current_state} -> {new_state}")


class AutoActivationBlockedError(ExperimentLifecycleError):
    """Raised whenever any code path attempts to move an experiment's
    lifecycle_state to ACTIVE without explicit, non-empty human
    authorization. This is a hard code-level guard: no deterministic
    trigger, scheduler job, or AI-routed job may ever set lifecycle_state to
    ACTIVE on its own. See EXTERNAL_INTEGRATION.md and
    AI_OPERATING_MANUAL.md -- ACTIVE requires an explicit human action,
    always."""


def apply_experiment_lifecycle_transition(
    experiment: dict,
    new_state: str,
    *,
    human_authorized: bool = False,
    authorized_by: str = "",
) -> dict:
    """The ONLY sanctioned way to change experiment.lifecycle_state. Applies
    validate_experiment_transition, then hard-refuses any transition INTO
    ACTIVE unless human_authorized=True with a non-empty authorized_by
    (a human identifier/statement) -- no deterministic code, trigger, or AI
    job can set this flag on the experiment's own initiative; it can only be
    supplied by a human-facing entry point (e.g. an interactive CLI command
    that requires the operator to type a confirmation)."""
    current_state = experiment.get("lifecycle_state")
    validate_experiment_transition(current_state, new_state)
    if new_state == "ACTIVE" and not (human_authorized and authorized_by):
        raise AutoActivationBlockedError(
            "refused: moving an experiment to ACTIVE requires human_authorized=True "
            "and a non-empty authorized_by (human identifier). No automated code "
            "path -- including deterministic scheduler triggers -- may activate an "
            "experiment on its own."
        )
    updated = dict(experiment)
    updated["lifecycle_state"] = new_state
    updated["state"] = new_state  # legacy field kept in sync, per migration note
    updated["status"] = new_state.lower()  # legacy field kept in sync, per migration note
    if new_state == "ACTIVE":
        updated["activated_at"] = now_iso()
        updated["activated_by"] = authorized_by
    return updated


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
    record: dict = {
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


def _parse_iso(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


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
    observed_at: Optional[str] = None,
) -> dict:
    """Create a metric observation. `retrieved_at` (when THIS system fetched
    the value) is always stamped now(). `observed_at` (when the underlying
    event/period the metric describes actually happened) is optional but,
    when supplied, MUST NOT be later than retrieved_at -- a metric cannot be
    observed in the future relative to when it was retrieved. When omitted,
    observed_at defaults to retrieved_at (the conservative "as of now"
    assumption), never to some fabricated earlier time."""
    if environment not in VALID_ENVIRONMENTS:
        raise MetricObservationError(f"invalid environment: {environment!r}")
    if data_quality not in VALID_DATA_QUALITY:
        raise MetricObservationError(f"invalid data_quality: {data_quality!r}")
    retrieved_at = now_iso()
    if observed_at:
        observed_dt = _parse_iso(observed_at)
        retrieved_dt = _parse_iso(retrieved_at)
        if observed_dt is None:
            raise MetricObservationError(f"observed_at is not a valid ISO-8601 timestamp: {observed_at!r}")
        if retrieved_dt is not None and observed_dt > retrieved_dt:
            raise MetricObservationError(
                f"observed_at ({observed_at}) is after retrieved_at ({retrieved_at}); "
                "a metric cannot be observed in the future relative to when it was retrieved"
            )
    else:
        observed_at = retrieved_at
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
        "observed_at": observed_at,
        "retrieved_at": retrieved_at,
        "coverage": coverage,
        "data_quality": data_quality,
        "limitations": limitations,
        "eligible_for_official_evaluation": environment == "production",
        "schema_version": SCHEMA_VERSION,
    }
    validate_against_schema(record, "metric_observation.schema.json")
    METRIC_OBSERVATIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = METRIC_OBSERVATIONS_DIR / f"{obs_id}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def filter_official_evaluation_observations(observations: list[dict], *, activation_date: Optional[str]) -> list[dict]:
    """Filter a list of metric observations down to the ones eligible for
    official economic evaluation of an experiment: environment=='production'
    AND (no activation_date requirement, or observed_at on/after
    activation_date). Dev/test/synthetic/smoke/E2E/admin traffic and
    pre-activation data are excluded, never silently included.

    Eligibility is judged on `observed_at` (when the underlying event
    actually happened), NOT `retrieved_at` (when this system happened to
    fetch/ingest it). A production data point observed BEFORE activation but
    retrieved/backfilled AFTER activation must not count toward post-
    activation evaluation just because it was fetched late.

    Timezone-aware (prompt-hardening-final-capital-agent-v0.2.md section 6):
    compares parsed instants via `_parse_iso`, not raw ISO-8601 strings.
    Lexical string comparison silently breaks whenever `observed_at` and
    `activation_date` use different UTC offsets for the same instant (e.g.
    `...T21:00:00-03:00` vs `...T00:00:00+00:00`), or mixed offset/`Z`
    notation -- both real possibilities across data sources ingested here.
    An `observed_at` (or `activation_date`) that fails to parse is treated
    as ineligible/unknown rather than silently included, since a
    fabricated/guessed instant could wrongly grant or deny eligibility.

    Post-review fix (2026-08-13 Codex review of this PR): an unparseable
    `activation_date` used to silently set `activation_dt = None`, which
    disabled the activation-date filter entirely and let pre-activation
    production observations through -- a fail-OPEN on corrupt input, the
    opposite of the invariant this docstring already claimed. A corrupt/
    invalid `activation_date` is now a hard, explicit failure instead, per
    section 12 of prompt-hardening-final-capital-agent-v0.2.md ("falhar
    explicitamente em payload inválido")."""
    out = []
    if activation_date:
        activation_dt = _parse_iso(activation_date)
        if activation_dt is None:
            raise ValueError(f"invalid activation_date: {activation_date!r}")
    else:
        activation_dt = None
    for obs in observations:
        if obs.get("environment") != "production":
            continue
        if activation_dt is not None:
            observed_dt = _parse_iso(obs.get("observed_at", ""))
            if observed_dt is None:
                # observed_at present but unparseable: cannot establish it is
                # on/after activation, so exclude rather than guess.
                if obs.get("observed_at"):
                    continue
            elif observed_dt < activation_dt:
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

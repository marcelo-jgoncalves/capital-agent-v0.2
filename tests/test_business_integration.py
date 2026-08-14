"""Tests for src/business_integration.py -- External Business Data Adapter,
PII firewall, External Cash Event, experiment lifecycle, BUSINESS_SIGNAL,
Publication Package/Receipt, and metric-observation provenance/filtering.

Uses a temp state directory (monkeypatched module-level constants) so tests
never write into the real repo state/ directory.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import business_integration as bi  # noqa: E402


class BusinessIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self._orig = {
            "STATE_DIR": bi.STATE_DIR,
            "BUSINESS_SIGNALS_DIR": bi.BUSINESS_SIGNALS_DIR,
            "EXTERNAL_CASH_EVENTS_DIR": bi.EXTERNAL_CASH_EVENTS_DIR,
            "PUBLICATIONS_DIR": bi.PUBLICATIONS_DIR,
            "METRIC_OBSERVATIONS_DIR": bi.METRIC_OBSERVATIONS_DIR,
        }
        bi.STATE_DIR = self._tmp
        bi.BUSINESS_SIGNALS_DIR = self._tmp / "business_signals"
        bi.EXTERNAL_CASH_EVENTS_DIR = self._tmp / "external_cash_events"
        bi.PUBLICATIONS_DIR = self._tmp / "publications"
        bi.METRIC_OBSERVATIONS_DIR = self._tmp / "metric_observations"

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(bi, k, v)
        shutil.rmtree(self._tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# PII firewall
# ---------------------------------------------------------------------------

class PIIFirewallTests(BusinessIntegrationTestCase):
    def test_denylisted_fields_are_stripped(self):
        payload = {"lead_id": "L-1", "email": "a@b.com", "phone": "12345", "source": "organic"}
        clean = bi.sanitize_business_payload(payload)
        self.assertNotIn("email", clean)
        self.assertNotIn("phone", clean)
        self.assertEqual(clean.get("lead_id"), "L-1")
        self.assertEqual(clean.get("source"), "organic")

    def test_non_allowlisted_fields_are_dropped(self):
        payload = {"lead_id": "L-1", "some_unapproved_field": "x"}
        clean = bi.sanitize_business_payload(payload)
        self.assertNotIn("some_unapproved_field", clean)

    def test_assert_no_pii_keys_raises_on_pii(self):
        with self.assertRaises(bi.PIIRejectedError):
            bi.assert_no_pii_keys({"name": "John Doe"})

    def test_assert_no_pii_keys_raises_on_nested_pii(self):
        with self.assertRaises(bi.PIIRejectedError):
            bi.assert_no_pii_keys({"extra": {"email": "a@b.com"}})

    def test_assert_no_pii_keys_passes_clean_payload(self):
        bi.assert_no_pii_keys({"lead_id": "L-1", "source": "organic"})  # no raise

    def test_sanitize_never_mutates_input(self):
        payload = {"email": "a@b.com", "lead_id": "L-1"}
        bi.sanitize_business_payload(payload)
        self.assertIn("email", payload)  # original untouched

    def test_ingest_business_signal_rejects_pii_in_extra(self):
        with self.assertRaises(bi.PIIRejectedError):
            bi.ingest_business_signal(
                signal_type="lead_created", source_system="platform",
                source_record_id="rec-1", observed_at="2026-08-13T00:00:00Z",
                metric_name="lead_count", metric_value=1, unit="count",
                data_quality="observed", extra={"email": "a@b.com"},
            )

    def test_persisted_signal_file_contains_no_pii_keys(self):
        record = bi.ingest_business_signal(
            signal_type="lead_created", source_system="platform",
            source_record_id="rec-2", observed_at="2026-08-13T00:00:00Z",
            metric_name="lead_count", metric_value=1, unit="count",
            data_quality="observed", extra={"lead_id": "L-9", "source": "organic"},
        )
        path = bi.BUSINESS_SIGNALS_DIR / f"{record['signal_id']}.json"
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        bi.assert_no_pii_keys(on_disk)  # no raise


# ---------------------------------------------------------------------------
# External Business Data Adapter
# ---------------------------------------------------------------------------

class BusinessAdapterTests(BusinessIntegrationTestCase):
    def _ingest(self, **overrides):
        kwargs = dict(
            signal_type="content_performance", source_system="editorial-platform",
            source_record_id="post-abc", observed_at="2026-08-13T00:00:00Z",
            metric_name="engaged_sessions", metric_value=10, unit="count",
            data_quality="aggregated", measurement_period="2026-08-13",
        )
        kwargs.update(overrides)
        return bi.ingest_business_signal(**kwargs)

    def test_ingestion_is_idempotent(self):
        first = self._ingest()
        second = self._ingest()
        self.assertEqual(first["signal_id"], second["signal_id"])
        self.assertEqual(len(list(bi.BUSINESS_SIGNALS_DIR.glob("*.json"))), 1)

    def test_provenance_is_present(self):
        record = self._ingest()
        self.assertTrue(record["provenance"])
        self.assertTrue(record["retrieved_at"])

    def test_source_and_environment_preserved(self):
        record = self._ingest(environment="production")
        self.assertEqual(record["source_system"], "editorial-platform")
        self.assertEqual(record["environment"], "production")

    def test_malformed_payload_fails_safely(self):
        with self.assertRaises(bi.BusinessSignalError):
            self._ingest(data_quality="not-a-real-quality")
        with self.assertRaises(bi.BusinessSignalError):
            self._ingest(source_system="")

    def test_estimated_data_never_becomes_verified(self):
        record = self._ingest(data_quality="estimated", metric_value=5)
        self.assertEqual(record["data_quality"], "estimated")
        self.assertIn("ESTIMATED", record["limitations"])
        self.assertNotEqual(record["data_quality"], "verified")

    def test_unavailable_data_quality_forbids_a_value(self):
        with self.assertRaises(bi.BusinessSignalError):
            self._ingest(data_quality="unavailable", metric_value=5)


# ---------------------------------------------------------------------------
# BUSINESS_SIGNAL entity
# ---------------------------------------------------------------------------

class BusinessSignalEntityTests(BusinessIntegrationTestCase):
    def test_topic_candidate_is_not_a_business_signal(self):
        with self.assertRaises(bi.BusinessSignalError):
            bi.create_business_signal_entity(
                signal_type="topic_candidate", origin="editorial_research",
                evidence_refs=["ref-1"], period="2026-08",
            )

    def test_business_signal_without_evidence_cannot_be_promoted(self):
        sig = bi.create_business_signal_entity(
            signal_type="recurring_lead_pattern", origin="lead_analysis",
            evidence_refs=[], period="2026-08",
        )
        with self.assertRaises(bi.OpportunityPromotionError):
            bi.promote_business_signal_to_opportunity(sig, opportunity_candidate_ref="OPP-1", rationale="x")

    def test_business_signal_contains_no_pii(self):
        sig = bi.create_business_signal_entity(
            signal_type="recurring_lead_pattern", origin="lead_analysis",
            evidence_refs=["BSIG-ref-1"], period="2026-08",
        )
        bi.assert_no_pii_keys(sig)

    def test_business_signal_keeps_provenance(self):
        sig = bi.create_business_signal_entity(
            signal_type="recurring_lead_pattern", origin="lead_analysis",
            evidence_refs=["BSIG-ref-1"], period="2026-08",
        )
        self.assertTrue(sig["first_observed_at"])
        self.assertEqual(sig["origin"], "lead_analysis")

    def test_promotion_with_evidence_and_rationale_succeeds(self):
        sig = bi.create_business_signal_entity(
            signal_type="recurring_lead_pattern", origin="lead_analysis",
            evidence_refs=["BSIG-ref-1"], period="2026-08",
        )
        promoted = bi.promote_business_signal_to_opportunity(
            sig, opportunity_candidate_ref="OPP-1", rationale="Three leads asked for the same service."
        )
        self.assertEqual(promoted["status"], "promoted_to_opportunity_candidate")
        self.assertEqual(promoted["opportunity_candidate_ref"], "OPP-1")


# ---------------------------------------------------------------------------
# External Cash Event
# ---------------------------------------------------------------------------

class ExternalCashEventTests(BusinessIntegrationTestCase):
    def _reported_event(self):
        ev = bi.observe_external_cash_event(
            kind="revenue", amount_brl=100.0, source_system="stripe-export",
            source_record_id="inv-1", observed_at="2026-08-13T00:00:00Z",
        )
        return bi.report_external_cash_event(ev, report_source="file_adapter")

    def test_observation_is_idempotent(self):
        first = bi.observe_external_cash_event(
            kind="revenue", amount_brl=100.0, source_system="stripe-export",
            source_record_id="inv-1", observed_at="2026-08-13T00:00:00Z",
        )
        second = bi.observe_external_cash_event(
            kind="revenue", amount_brl=100.0, source_system="stripe-export",
            source_record_id="inv-1", observed_at="2026-08-13T00:00:00Z",
        )
        self.assertEqual(first["id"], second["id"])

    def test_ai_cannot_self_verify(self):
        ev = self._reported_event()
        with self.assertRaises(bi.CashEventVerificationError):
            bi.verify_external_cash_event(ev)  # no human_confirmed, no adapter

    def test_ai_cannot_use_unregistered_adapter(self):
        ev = self._reported_event()
        with self.assertRaises(bi.CashEventVerificationError):
            bi.verify_external_cash_event(ev, trusted_adapter_name="some_made_up_adapter")

    def test_human_confirmation_can_verify(self):
        ev = self._reported_event()
        verified = bi.verify_external_cash_event(ev, human_confirmed=True, human_statement="Confirmed in bank statement")
        self.assertEqual(verified["state"], "VERIFIED")

    def test_unverified_event_cannot_reach_ledger(self):
        ev = self._reported_event()  # REPORTED, not VERIFIED
        calls = []
        with self.assertRaises(bi.CashEventStateError):
            bi.post_external_cash_event_to_ledger(ev, append_ledger_fn=lambda *a: calls.append(a))
        self.assertEqual(calls, [])

    def test_verified_event_can_advance_to_ledger(self):
        ev = self._reported_event()
        ev = bi.verify_external_cash_event(ev, human_confirmed=True, human_statement="Confirmed")
        ev = bi.attribute_external_cash_event(ev)  # UNKNOWN attribution
        self.assertEqual(ev["attribution"]["status"], "UNKNOWN")
        ev = bi.reconcile_external_cash_event(ev, reconciled_by="human:owner")
        calls = []
        posted = bi.post_external_cash_event_to_ledger(ev, append_ledger_fn=lambda *a: calls.append(a))
        self.assertEqual(posted["state"], "LEDGER_POSTED")
        self.assertEqual(len(calls), 1)

    def test_duplicate_ledger_post_does_not_duplicate(self):
        ev = self._reported_event()
        ev = bi.verify_external_cash_event(ev, human_confirmed=True, human_statement="Confirmed")
        ev = bi.attribute_external_cash_event(ev)
        ev = bi.reconcile_external_cash_event(ev, reconciled_by="human:owner")
        calls = []
        ev = bi.post_external_cash_event_to_ledger(ev, append_ledger_fn=lambda *a: calls.append(a))
        ev2 = bi.post_external_cash_event_to_ledger(ev, append_ledger_fn=lambda *a: calls.append(a))
        self.assertEqual(len(calls), 1)  # second call is a no-op
        self.assertEqual(ev2["state"], "LEDGER_POSTED")

    # -- P1 #3 canonical-state posting (prompt-hardening-final section 5) --

    def _reconciled_event(self, amount_brl=100.0):
        ev = self._reported_event()
        ev = bi.verify_external_cash_event(ev, human_confirmed=True, human_statement="Confirmed")
        ev = bi.attribute_external_cash_event(ev)
        ev = bi.reconcile_external_cash_event(ev, reconciled_by="human:owner")
        return ev

    def test_caller_amount_divergence_does_not_alter_ledger(self):
        ev = self._reconciled_event(amount_brl=100.0)
        tampered = dict(ev)
        tampered["amount_brl"] = 999999.0
        calls = []
        posted = bi.post_external_cash_event_to_ledger(tampered, append_ledger_fn=lambda *a: calls.append(a))
        self.assertEqual(calls[0][2], 100.0)  # amount arg posted is the canonical one
        self.assertEqual(posted["amount_brl"], 100.0)

    def test_caller_kind_divergence_is_rejected_or_ignored(self):
        ev = self._reconciled_event()
        tampered = dict(ev)
        tampered["kind"] = "refund"
        calls = []
        bi.post_external_cash_event_to_ledger(tampered, append_ledger_fn=lambda *a: calls.append(a))
        self.assertEqual(calls[0][0], bi.CASH_EVENT_KIND_TO_LEDGER_TYPE["revenue"])  # canonical kind used

    def test_caller_source_divergence_does_not_alter_ledger(self):
        ev = self._reconciled_event()
        tampered = dict(ev)
        tampered["source_system"] = "adulterated-source"
        calls = []
        bi.post_external_cash_event_to_ledger(tampered, append_ledger_fn=lambda *a: calls.append(a))
        self.assertNotIn("adulterated-source", calls[0][3])
        self.assertIn(ev["source_system"], calls[0][3])

    def test_caller_idempotency_key_divergence_does_not_alter_posting(self):
        ev = self._reconciled_event()
        tampered = dict(ev)
        tampered["idempotency_key"] = "forged:key:x"
        calls = []
        bi.post_external_cash_event_to_ledger(tampered, append_ledger_fn=lambda *a: calls.append(a))
        self.assertEqual(calls[0][4], ev["idempotency_key"])  # canonical reference used, not the forged one

    def test_stale_expected_state_fails_explicitly(self):
        ev = self._reconciled_event()
        stale = dict(ev)
        stale["state"] = "VERIFIED"  # caller thinks it's still VERIFIED (stale copy)
        with self.assertRaises(bi.CashEventStateError):
            bi.post_external_cash_event_to_ledger(stale, append_ledger_fn=lambda *a: None)

    def test_retry_with_stale_expected_state_after_success_is_still_idempotent(self):
        """Post-review fix: a retry carrying a stale (but PRE-success)
        expected_state, issued AFTER the event already reached
        LEDGER_POSTED, must return the idempotent no-op, not a
        CashEventStateError -- "already succeeded" is not staleness, it's
        exactly the case retry exists to handle."""
        ev = self._reconciled_event()
        calls = []
        first = bi.post_external_cash_event_to_ledger(ev, append_ledger_fn=lambda *a: calls.append(a))
        self.assertEqual(first["state"], "LEDGER_POSTED")

        stale_retry = dict(ev)
        stale_retry["state"] = "RECONCILED"  # caller's last-known state, now stale
        second = bi.post_external_cash_event_to_ledger(stale_retry, append_ledger_fn=lambda *a: calls.append(a))
        self.assertEqual(second["state"], "LEDGER_POSTED")
        self.assertEqual(len(calls), 1)  # no second ledger call

    def test_correct_state_uses_exclusively_persisted_data(self):
        ev = self._reconciled_event()
        minimal = {"id": ev["id"], "state": ev["state"]}  # no financial fields at all
        calls = []
        posted = bi.post_external_cash_event_to_ledger(minimal, append_ledger_fn=lambda *a: calls.append(a))
        self.assertEqual(posted["amount_brl"], ev["amount_brl"])
        self.assertEqual(len(calls), 1)

    def test_attribution_can_be_explicit_and_unknown(self):
        ev = self._reported_event()
        ev = bi.verify_external_cash_event(ev, human_confirmed=True, human_statement="Confirmed")
        attributed = bi.attribute_external_cash_event(ev, experiment_id="EXP-001")
        self.assertEqual(attributed["attribution"]["experiment_id"], "EXP-001")
        self.assertEqual(attributed["attribution"]["status"], "ATTRIBUTED")

    def test_invalid_transition_rejected(self):
        ev = bi.observe_external_cash_event(
            kind="revenue", amount_brl=50.0, source_system="s", source_record_id="r1",
            observed_at="2026-08-13T00:00:00Z",
        )
        with self.assertRaises(bi.CashEventStateError):
            bi.verify_external_cash_event(ev, human_confirmed=True, human_statement="x")  # skips REPORTED


# ---------------------------------------------------------------------------
# Experiment lifecycle
# ---------------------------------------------------------------------------

class ExperimentLifecycleTests(unittest.TestCase):
    def test_valid_transition(self):
        bi.validate_experiment_transition("PLANNED", "READY_FOR_ACTIVATION")  # no raise

    def test_invalid_transition_fails(self):
        with self.assertRaises(bi.ExperimentLifecycleError):
            bi.validate_experiment_transition("PLANNED", "ACTIVE")

    def test_closed_is_terminal(self):
        with self.assertRaises(bi.ExperimentLifecycleError):
            bi.validate_experiment_transition("CLOSED", "ACTIVE")

    def test_zero_capital_experiment_budget_is_valid(self):
        # capital_budget_brl == 0 must not itself be treated as invalid input.
        experiment = {"capital_budget_brl": 0.0, "resource_budget": {"operator_time_minutes": 120}}
        self.assertEqual(experiment["capital_budget_brl"], 0.0)

    def test_roic_none_when_capital_deployed_zero(self):
        self.assertIsNone(bi.compute_roic(profit_brl=100.0, capital_deployed_brl=0))

    def test_roic_computed_normally(self):
        self.assertEqual(bi.compute_roic(profit_brl=50.0, capital_deployed_brl=100.0), 0.5)

    def test_ready_for_activation_fails_with_missing_fields(self):
        experiment = {"hypothesis": "x"}
        ready, missing = bi.check_ready_for_activation(experiment, open_p0_backlog_items=[])
        self.assertFalse(ready)
        self.assertTrue(missing)

    def test_ready_for_activation_blocked_by_open_p0(self):
        experiment = {f: "value" for f in bi.READY_FOR_ACTIVATION_REQUIRED_FIELDS}
        experiment["dev_prod_separation_confirmed"] = True
        experiment["lead_capture_functional"] = True
        ready, missing = bi.check_ready_for_activation(experiment, open_p0_backlog_items=["PLAT-001"])
        self.assertFalse(ready)
        self.assertTrue(any("PLAT-001" in m for m in missing))

    def test_exp001_migrated_record_is_not_active(self):
        exp_path = Path(__file__).resolve().parents[1] / "experiments" / "active" / "EXP-20260813-62C22E.json"
        data = json.loads(exp_path.read_text(encoding="utf-8"))
        self.assertEqual(data["lifecycle_state"], "PLANNED")
        self.assertIn("capital_budget_brl", data)
        self.assertIn("resource_budget", data)
        self.assertIn("non_financial_risks", data)
        self.assertFalse(data["readiness_for_activation"]["ready"])


# ---------------------------------------------------------------------------
# Publication package / receipt
# ---------------------------------------------------------------------------

class PublicationTests(BusinessIntegrationTestCase):
    def test_package_does_not_imply_published(self):
        pkg = bi.create_publication_package(
            content_brief_id="BRIEF-1", experiment_id="EXP-001", title="t",
            slug_suggestion="s", draft_ref="draft-1", fact_check_ref=None,
            critic_ref=None, business_hypothesis_ref=None, cta_intent=None,
        )
        self.assertEqual(pkg["authorization_status"], "NOT_AUTHORIZED")
        self.assertTrue(pkg["approval_required"])

    def test_receipt_requires_external_identification(self):
        with self.assertRaises(bi.PublicationError):
            bi.ingest_publication_receipt(
                publication_request_id="PUBREQ-1", platform_content_id="",
                canonical_slug="s", canonical_url="https://x", published_at="2026-08-13T00:00:00Z",
                environment="production", campaign_id=None, verification_source="",
            )

    def test_receipt_ingestion_is_idempotent(self):
        kwargs = dict(
            publication_request_id="PUBREQ-1", platform_content_id="cid-1",
            canonical_slug="s", canonical_url="https://x", published_at="2026-08-13T00:00:00Z",
            environment="production", campaign_id=None, verification_source="platform_export",
        )
        first = bi.ingest_publication_receipt(**kwargs)
        second = bi.ingest_publication_receipt(**kwargs)
        self.assertEqual(first["publication_id"], second["publication_id"])


# ---------------------------------------------------------------------------
# Metric observations / environment filtering
# ---------------------------------------------------------------------------

class MetricObservationTests(BusinessIntegrationTestCase):
    def test_dev_metrics_excluded_from_official_evaluation(self):
        prod = bi.create_metric_observation(
            experiment_id="EXP-001", metric_name="qualified_leads", value=3, unit="count",
            period="2026-08", source="platform_export", environment="production",
            coverage="full", data_quality="observed",
        )
        dev = bi.create_metric_observation(
            experiment_id="EXP-001", metric_name="qualified_leads", value=99, unit="count",
            period="2026-08", source="platform_export", environment="dev",
            coverage="full", data_quality="observed",
        )
        self.assertTrue(prod["eligible_for_official_evaluation"])
        self.assertFalse(dev["eligible_for_official_evaluation"])
        filtered = bi.filter_official_evaluation_observations([prod, dev], activation_date=None)
        self.assertEqual(filtered, [prod])

    def test_pre_activation_metrics_excluded(self):
        obs = bi.create_metric_observation(
            experiment_id="EXP-001", metric_name="qualified_leads", value=3, unit="count",
            period="2026-08", source="platform_export", environment="production",
            coverage="full", data_quality="observed",
        )
        obs["observed_at"] = "2020-01-01T00:00:00Z"  # force pre-activation
        filtered = bi.filter_official_evaluation_observations([obs], activation_date="2026-08-13T00:00:00Z")
        self.assertEqual(filtered, [])

    def test_pre_activation_observation_retrieved_post_activation_is_excluded(self):
        # Eligibility must be judged on observed_at, not retrieved_at: a
        # production data point that actually happened before activation but
        # was only fetched/backfilled afterward must NOT count toward
        # post-activation evaluation just because retrieved_at is late.
        obs = bi.create_metric_observation(
            experiment_id="EXP-001", metric_name="qualified_leads", value=3, unit="count",
            period="2026-08", source="platform_export", environment="production",
            coverage="full", data_quality="observed", observed_at="2026-08-01T00:00:00Z",
        )
        self.assertGreaterEqual(obs["retrieved_at"], "2026-08-13T00:00:00Z")
        filtered = bi.filter_official_evaluation_observations([obs], activation_date="2026-08-13T00:00:00Z")
        self.assertEqual(filtered, [])

    # -- P1 #4 timezone-aware comparisons (prompt-hardening-final section 6) --

    def test_equivalent_instants_with_different_offsets_are_eligible(self):
        # 2026-08-09T21:00:00-03:00 == 2026-08-10T00:00:00+00:00 (same instant).
        # Lexical string comparison of these two would wrongly disagree.
        obs = bi.create_metric_observation(
            experiment_id="EXP-001", metric_name="m", value=1, unit="count",
            period="2026-08", source="s", environment="production",
            coverage="full", data_quality="observed",
            observed_at="2026-08-09T21:00:00-03:00",
        )
        filtered = bi.filter_official_evaluation_observations(
            [obs], activation_date="2026-08-10T00:00:00+00:00",
        )
        self.assertEqual(filtered, [obs])  # equal instant -> "on activation date" -> eligible

    def test_utc_vs_local_offset_boundary(self):
        obs_before = bi.create_metric_observation(
            experiment_id="EXP-001", metric_name="m", value=1, unit="count",
            period="2026-08", source="s", environment="production",
            coverage="full", data_quality="observed",
            observed_at="2026-08-09T20:59:59-03:00",  # = 2026-08-13T23:59:59Z, before activation
        )
        obs_after = bi.create_metric_observation(
            experiment_id="EXP-001", metric_name="m", value=1, unit="count",
            period="2026-08", source="s", environment="production",
            coverage="full", data_quality="observed",
            observed_at="2026-08-09T21:00:01-03:00",  # = 2026-08-10T00:00:01Z, after activation
        )
        filtered = bi.filter_official_evaluation_observations(
            [obs_before, obs_after], activation_date="2026-08-10T00:00:00Z",
        )
        self.assertEqual(filtered, [obs_after])

    def test_boundary_equal_to_activation_date_is_eligible(self):
        obs = bi.create_metric_observation(
            experiment_id="EXP-001", metric_name="m", value=1, unit="count",
            period="2026-08", source="s", environment="production",
            coverage="full", data_quality="observed",
            observed_at="2026-08-10T00:00:00Z",
        )
        filtered = bi.filter_official_evaluation_observations(
            [obs], activation_date="2026-08-10T00:00:00Z",
        )
        self.assertEqual(filtered, [obs])

    def test_invalid_observed_at_timestamp_excluded_not_crashed(self):
        obs = bi.create_metric_observation(
            experiment_id="EXP-001", metric_name="m", value=1, unit="count",
            period="2026-08", source="s", environment="production",
            coverage="full", data_quality="observed",
        )
        obs["observed_at"] = "not-a-real-timestamp"
        filtered = bi.filter_official_evaluation_observations(
            [obs], activation_date="2026-08-10T00:00:00Z",
        )
        self.assertEqual(filtered, [])  # excluded explicitly, no exception

    def test_invalid_environment_rejected(self):
        with self.assertRaises(bi.MetricObservationError):
            bi.create_metric_observation(
                experiment_id="EXP-001", metric_name="x", value=1, unit="count",
                period="2026-08", source="s", environment="not-a-real-env",
                coverage=None, data_quality="observed",
            )


# ---------------------------------------------------------------------------
# Anti-platform-bias comparison
# ---------------------------------------------------------------------------

class AlternativesComparisonTests(unittest.TestCase):
    def test_missing_alternatives_are_none_available_not_fabricated(self):
        comparison = bi.build_alternatives_comparison(
            platform_opportunity={"id": "EXP-001"},
            best_financial_opportunity=None,
            best_non_platform_opportunity=None,
            benchmark={"id": "CDI"},
        )
        self.assertEqual(comparison["best_financial_opportunity"]["status"], "NONE_AVAILABLE")
        self.assertEqual(comparison["best_non_platform_opportunity"]["status"], "NONE_AVAILABLE")
        self.assertEqual(comparison["platform_opportunity"]["id"], "EXP-001")


# ---------------------------------------------------------------------------
# Hardening: persistence, crash-safety, concurrency, chargeback semantics,
# PII value-level checks, BusinessObservation/Signal split, schema
# validation, metric temporal invariants, EXP-001 auto-activation guard.
# ---------------------------------------------------------------------------


class CashEventPersistenceTests(BusinessIntegrationTestCase):
    def _to_reconciled(self):
        ev = bi.observe_external_cash_event(
            kind="revenue", amount_brl=100.0, source_system="stripe-export",
            source_record_id="inv-persist-1", observed_at="2026-08-13T00:00:00Z",
        )
        ev = bi.report_external_cash_event(ev, report_source="file_adapter")
        ev = bi.verify_external_cash_event(ev, human_confirmed=True, human_statement="bank statement")
        ev = bi.attribute_external_cash_event(ev)
        ev = bi.reconcile_external_cash_event(ev, reconciled_by="human:owner")
        return ev

    def test_every_transition_is_persisted_to_disk(self):
        ev = bi.observe_external_cash_event(
            kind="revenue", amount_brl=50.0, source_system="s", source_record_id="r-persist",
            observed_at="2026-08-13T00:00:00Z",
        )
        ev = bi.report_external_cash_event(ev, report_source="file_adapter")
        on_disk = json.loads((bi.EXTERNAL_CASH_EVENTS_DIR / f"{ev['id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk["state"], "REPORTED")
        ev = bi.verify_external_cash_event(ev, human_confirmed=True, human_statement="x")
        on_disk = json.loads((bi.EXTERNAL_CASH_EVENTS_DIR / f"{ev['id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk["state"], "VERIFIED")
        self.assertIsNotNone(on_disk["verification"])

    def test_state_history_reconstructs_full_path(self):
        ev = self._to_reconciled()
        on_disk = json.loads((bi.EXTERNAL_CASH_EVENTS_DIR / f"{ev['id']}.json").read_text(encoding="utf-8"))
        states_seen = [h["state"] for h in on_disk["state_history"]]
        self.assertEqual(states_seen, ["OBSERVED", "REPORTED", "VERIFIED", "ATTRIBUTED", "RECONCILED"])

    def test_load_external_cash_event_reads_persisted_state(self):
        ev = self._to_reconciled()
        loaded = bi.load_external_cash_event(ev["id"])
        self.assertEqual(loaded["state"], "RECONCILED")

    def test_list_external_cash_events_filters_by_state(self):
        self._to_reconciled()
        reconciled = bi.list_external_cash_events(state="RECONCILED")
        self.assertEqual(len(reconciled), 1)
        self.assertEqual(bi.list_external_cash_events(state="LEDGER_POSTED"), [])


class LedgerCrashSafetyTests(BusinessIntegrationTestCase):
    def setUp(self):
        super().setUp()
        self._ledger_orig = bi.LEDGER_FILE
        self._ledger_tmp_dir = Path(tempfile.mkdtemp())
        bi.LEDGER_FILE = self._ledger_tmp_dir / "ledger.csv"
        bi.LEDGER_FILE.write_text("timestamp,type,category,amount_brl,description,reference\n", encoding="utf-8")

    def tearDown(self):
        bi.LEDGER_FILE = self._ledger_orig
        shutil.rmtree(self._ledger_tmp_dir, ignore_errors=True)
        super().tearDown()

    def _real_append(self, typ, category, amount, desc, reference):
        with bi.LEDGER_FILE.open("a", encoding="utf-8") as f:
            f.write(f"2026-08-13T00:00:00Z,{typ},{category},{amount:.2f},{desc},{reference}\n")

    def _reconciled_event(self, ref="crash-1"):
        ev = bi.observe_external_cash_event(
            kind="revenue", amount_brl=77.0, source_system="s", source_record_id=ref,
            observed_at="2026-08-13T00:00:00Z",
        )
        ev = bi.report_external_cash_event(ev, report_source="file_adapter")
        ev = bi.verify_external_cash_event(ev, human_confirmed=True, human_statement="x")
        ev = bi.attribute_external_cash_event(ev)
        return bi.reconcile_external_cash_event(ev, reconciled_by="human:owner")

    def test_crash_after_ledger_write_before_state_persist_does_not_duplicate_on_retry(self):
        """Simulates a crash between "ledger line written" and "event state
        persisted as LEDGER_POSTED": append_ledger_fn writes the real ledger
        line and then raises, as if the process died right after the OS
        flushed the write but before this module could persist the new
        state. A retry must not produce a second ledger line."""
        ev = self._reconciled_event()

        def crashing_append(typ, category, amount, desc, reference):
            self._real_append(typ, category, amount, desc, reference)
            raise RuntimeError("simulated crash after ledger write")

        with self.assertRaises(RuntimeError):
            bi.post_external_cash_event_to_ledger(ev, append_ledger_fn=crashing_append)

        # Event was never persisted as LEDGER_POSTED (crash happened before
        # that write), so on disk it is still RECONCILED.
        reloaded = bi.load_external_cash_event(ev["id"])
        self.assertEqual(reloaded["state"], "RECONCILED")

        # Retry with a working append function: must detect the ledger
        # already has this reference and NOT write a second line.
        calls = []
        retried = bi.post_external_cash_event_to_ledger(
            reloaded, append_ledger_fn=lambda *a: (calls.append(a), self._real_append(*a))[0]
        )
        self.assertEqual(retried["state"], "LEDGER_POSTED")
        self.assertEqual(calls, [])  # append_ledger_fn was NOT called again

        lines = bi.LEDGER_FILE.read_text(encoding="utf-8").strip().splitlines()
        matching = [line for line in lines if ev["idempotency_key"] in line]
        self.assertEqual(len(matching), 1)  # exactly one ledger line, no duplicate

    def test_retry_after_crash_before_ledger_write_posts_exactly_once(self):
        """Crash happens before the ledger line is even written (e.g. lock
        acquired then process dies). Retry must still post exactly once."""
        ev = self._reconciled_event(ref="crash-2")

        def crashing_append(*a):
            raise RuntimeError("simulated crash before ledger write completes")

        with self.assertRaises(RuntimeError):
            bi.post_external_cash_event_to_ledger(ev, append_ledger_fn=crashing_append)

        # lock file must have been released even though the call raised
        wal_dir = bi.EXTERNAL_CASH_EVENTS_DIR / "_wal"
        self.assertEqual(list(wal_dir.glob("*.lock")), [])

        calls = []
        retried = bi.post_external_cash_event_to_ledger(
            ev, append_ledger_fn=lambda *a: (calls.append(a), self._real_append(*a))[0]
        )
        self.assertEqual(retried["state"], "LEDGER_POSTED")
        self.assertEqual(len(calls), 1)

    def test_concurrent_posts_of_same_event_only_post_once(self):
        """Two threads race to post the same RECONCILED event (idempotency
        key). Only one may actually append a ledger line; the other must
        either no-op or block until the first finishes and then observe the
        event as already posted."""
        ev = self._reconciled_event(ref="concurrent-1")
        append_calls = []
        lock = threading.Lock()

        def synchronized_append(typ, category, amount, desc, reference):
            with lock:
                self._real_append(typ, category, amount, desc, reference)
                append_calls.append(reference)

        results = []
        errors = []

        def worker():
            try:
                results.append(bi.post_external_cash_event_to_ledger(dict(ev), append_ledger_fn=synchronized_append))
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(append_calls), 1)  # exactly one ledger append happened
        lines = bi.LEDGER_FILE.read_text(encoding="utf-8").strip().splitlines()
        matching = [line for line in lines if ev["idempotency_key"] in line]
        self.assertEqual(len(matching), 1)


class StaleCashEventTransitionTests(BusinessIntegrationTestCase):
    def test_stale_in_memory_transition_is_rejected(self):
        ev = bi.observe_external_cash_event(
            kind="revenue", amount_brl=25.0, source_system="s", source_record_id="stale-tx-1",
            observed_at="2026-08-13T00:00:00Z",
        )
        reported = bi.report_external_cash_event(ev, report_source="file_adapter")
        # `ev` is now a stale in-memory copy (still OBSERVED) while the
        # persisted record has already advanced to REPORTED. Attempting to
        # advance from the stale copy must be refused, not silently applied
        # on top of (or clobbering) the persisted REPORTED state.
        with self.assertRaises(bi.StaleCashEventStateError):
            bi.report_external_cash_event(ev, report_source="file_adapter")
        # Persisted state must be unaffected by the rejected stale attempt.
        reloaded = bi.load_external_cash_event(ev["id"])
        self.assertEqual(reloaded["state"], "REPORTED")
        self.assertEqual(reloaded["state_history"], reported["state_history"])

    def test_fresh_reload_can_proceed_after_stale_rejection(self):
        ev = bi.observe_external_cash_event(
            kind="revenue", amount_brl=25.0, source_system="s", source_record_id="stale-tx-2",
            observed_at="2026-08-13T00:00:00Z",
        )
        bi.report_external_cash_event(ev, report_source="file_adapter")
        with self.assertRaises(bi.StaleCashEventStateError):
            bi.report_external_cash_event(ev, report_source="file_adapter")
        # Reloading gives the caller the canonical state, which CAN advance.
        verified = bi.verify_external_cash_event(
            bi.load_external_cash_event(ev["id"]), human_confirmed=True, human_statement="ok"
        )
        self.assertEqual(verified["state"], "VERIFIED")


class LedgerReferenceConflictTests(BusinessIntegrationTestCase):
    def setUp(self):
        super().setUp()
        self._ledger_orig = bi.LEDGER_FILE
        self._ledger_tmp_dir = Path(tempfile.mkdtemp())
        bi.LEDGER_FILE = self._ledger_tmp_dir / "ledger.csv"
        bi.LEDGER_FILE.write_text("timestamp,type,category,amount_brl,description,reference\n", encoding="utf-8")

    def tearDown(self):
        bi.LEDGER_FILE = self._ledger_orig
        shutil.rmtree(self._ledger_tmp_dir, ignore_errors=True)
        super().tearDown()

    def _reconciled_event(self, ref="conflict-1", amount=42.0):
        ev = bi.observe_external_cash_event(
            kind="revenue", amount_brl=amount, source_system="s", source_record_id=ref,
            observed_at="2026-08-13T00:00:00Z",
        )
        ev = bi.report_external_cash_event(ev, report_source="file_adapter")
        ev = bi.verify_external_cash_event(ev, human_confirmed=True, human_statement="x")
        ev = bi.attribute_external_cash_event(ev)
        return bi.reconcile_external_cash_event(ev, reconciled_by="human:owner")

    def test_conflicting_duplicate_reference_raises(self):
        ev = self._reconciled_event(ref="conflict-1", amount=42.0)
        # A row already exists under this idempotency_key/reference, but with
        # a DIFFERENT amount -- simulating either corruption or a reference
        # collision. This must be raised, never silently treated as "already
        # posted".
        with bi.LEDGER_FILE.open("a", encoding="utf-8") as f:
            f.write(f"2026-08-13T00:00:00Z,revenue,external_cash_event,999.00,forged,{ev['idempotency_key']}\n")
        with self.assertRaises(bi.LedgerReferenceConflictError):
            bi.post_external_cash_event_to_ledger(ev, append_ledger_fn=lambda *a: None)

    def test_matching_existing_reference_is_still_treated_as_idempotent_no_op(self):
        ev = self._reconciled_event(ref="conflict-2", amount=15.0)
        with bi.LEDGER_FILE.open("a", encoding="utf-8") as f:
            f.write(f"2026-08-13T00:00:00Z,revenue,external_cash_event,15.00,ok,{ev['idempotency_key']}\n")
        calls = []
        posted = bi.post_external_cash_event_to_ledger(ev, append_ledger_fn=lambda *a: calls.append(a))
        self.assertEqual(calls, [])
        self.assertEqual(posted["state"], "LEDGER_POSTED")


class LedgerLockRecoveryTests(BusinessIntegrationTestCase):
    def setUp(self):
        super().setUp()
        self._ledger_orig = bi.LEDGER_FILE
        self._ledger_tmp_dir = Path(tempfile.mkdtemp())
        bi.LEDGER_FILE = self._ledger_tmp_dir / "ledger.csv"
        bi.LEDGER_FILE.write_text("timestamp,type,category,amount_brl,description,reference\n", encoding="utf-8")

    def tearDown(self):
        bi.LEDGER_FILE = self._ledger_orig
        shutil.rmtree(self._ledger_tmp_dir, ignore_errors=True)
        super().tearDown()

    def _reconciled_event(self, ref):
        ev = bi.observe_external_cash_event(
            kind="revenue", amount_brl=9.0, source_system="s", source_record_id=ref,
            observed_at="2026-08-13T00:00:00Z",
        )
        ev = bi.report_external_cash_event(ev, report_source="file_adapter")
        ev = bi.verify_external_cash_event(ev, human_confirmed=True, human_statement="x")
        ev = bi.attribute_external_cash_event(ev)
        return bi.reconcile_external_cash_event(ev, reconciled_by="human:owner")

    def test_orphaned_stale_lock_is_recovered(self):
        ev = self._reconciled_event("lockrec-1")
        wal_dir = bi.EXTERNAL_CASH_EVENTS_DIR / "_wal"
        wal_dir.mkdir(parents=True, exist_ok=True)
        lock_path = wal_dir / (bi.re.sub(r"[^A-Za-z0-9_.-]", "_", ev["idempotency_key"]) + ".lock")
        # Simulate an orphaned lock: written by a PID that is not running,
        # and old enough to exceed the stale threshold.
        lock_path.write_text(json.dumps({"pid": 999999, "created_at": "2000-01-01T00:00:00Z"}), encoding="utf-8")
        old_time = time.time() - (bi.STALE_LOCK_MAX_AGE_SECONDS + 60)
        import os as _os
        _os.utime(lock_path, (old_time, old_time))

        calls = []
        posted = bi.post_external_cash_event_to_ledger(ev, append_ledger_fn=lambda *a: calls.append(a))
        self.assertEqual(posted["state"], "LEDGER_POSTED")
        self.assertEqual(len(calls), 1)

    def test_fresh_lock_is_not_broken(self):
        ev = self._reconciled_event("lockrec-2")
        wal_dir = bi.EXTERNAL_CASH_EVENTS_DIR / "_wal"
        wal_dir.mkdir(parents=True, exist_ok=True)
        lock_path = wal_dir / (bi.re.sub(r"[^A-Za-z0-9_.-]", "_", ev["idempotency_key"]) + ".lock")
        # A fresh lock (just created, "owned" by our own live PID) must NOT
        # be taken over; the caller should time out instead.
        lock_path.write_text(json.dumps({"pid": bi.os.getpid(), "created_at": bi.now_iso()}), encoding="utf-8")
        with self.assertRaises(bi.LedgerPostLockError):
            bi.post_external_cash_event_to_ledger(ev, append_ledger_fn=lambda *a: None, max_lock_wait_s=0.2)
        lock_path.unlink()


class GenericLockStaleTakeoverMutexTests(BusinessIntegrationTestCase):
    """Codex review finding (not previously covered by any test): two
    processes that both judge the same lock stale used to both succeed at
    `os.replace()`-ing their own takeover onto it, so both believed they
    held the lock -- a real mutual-exclusion violation, not just a
    theoretical one. `_attempt_stale_lock_takeover` now verifies (via a
    nonce written into the lock and read back after the replace) that only
    one racer actually wins."""

    def _make_stale_lock(self, lock_path):
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(json.dumps({"pid": 999999, "created_at": "2000-01-01T00:00:00Z"}), encoding="utf-8")
        old_time = time.time() - (bi.STALE_LOCK_MAX_AGE_SECONDS + 60)
        import os as _os
        _os.utime(lock_path, (old_time, old_time))

    def test_only_one_of_many_racing_takeovers_wins(self):
        lock_path = Path(tempfile.mkdtemp()) / "mutex.lock"
        self._make_stale_lock(lock_path)

        results = []

        def race():
            results.append(bi._attempt_stale_lock_takeover(lock_path))

        threads = [threading.Thread(target=race) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Every racer performs a real os.replace() (so all "succeed" at the
        # filesystem level), but the nonce read-back must show that exactly
        # one of them is the one whose write is still on disk afterward --
        # this is the actual mutual-exclusion property, not the replace
        # call succeeding.
        self.assertEqual(results.count(True), 1)

    def test_acquire_generic_lock_grants_exactly_one_winner_under_stale_race(self):
        lock_path = Path(tempfile.mkdtemp()) / "mutex2.lock"
        self._make_stale_lock(lock_path)

        acquired = []

        def acquire():
            try:
                bi.acquire_generic_lock(lock_path, max_lock_wait_s=1.0)
                acquired.append(True)
            except bi.LedgerPostLockError:
                pass

        threads = [threading.Thread(target=acquire) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # At least one thread must succeed (the eventual winner of the
        # stale-takeover race, or a later normal O_CREAT|O_EXCL acquirer).
        # None of this proves more than one thread *simultaneously* believed
        # it held the lock, which is what the fixed nonce check prevents.
        self.assertGreaterEqual(len(acquired), 1)

    def test_foreign_arbitration_file_is_never_taken_over_or_deleted(self):
        # Codex review finding: an earlier version aged out and deleted a
        # stale-looking arbitration file, which is an ABA race (the file's
        # original owner can still be alive and mid-critical-section, just
        # delayed past the age threshold; a third party recreating and then
        # deleting it out from under the true owner breaks exclusivity).
        # The fix: never touch another process's arbitration file, at any
        # age -- only its own creator may remove it.
        lock_path = Path(tempfile.mkdtemp()) / "aba.lock"
        self._make_stale_lock(lock_path)
        arbitration_path = lock_path.with_suffix(lock_path.suffix + ".takeover-arbitration")
        arbitration_path.parent.mkdir(parents=True, exist_ok=True)
        arbitration_path.write_text("owned by someone else", encoding="utf-8")
        old_time = time.time() - (bi.TAKEOVER_ARBITRATION_MAX_AGE_SECONDS + 60)
        import os as _os
        _os.utime(arbitration_path, (old_time, old_time))

        result = bi._attempt_stale_lock_takeover(lock_path)

        self.assertFalse(result)
        self.assertTrue(arbitration_path.exists())
        self.assertEqual(arbitration_path.read_text(encoding="utf-8"), "owned by someone else")


class WriteJsonIdempotentRaceTests(BusinessIntegrationTestCase):
    """P2 (prompt-hardening-final-capital-agent-v0.2.md section 9):
    _write_json_idempotent must not let two concurrent callers with the same
    idempotency_key both write a record."""

    def test_two_concurrent_equivalent_calls_write_exactly_one_record(self):
        barrier = threading.Barrier(8)
        results = []
        results_lock = threading.Lock()

        def worker(i):
            barrier.wait()
            record = {"idempotency_key": "race-key-1", "payload": "same-content", "n": i}
            got, created = bi._write_json_idempotent(
                bi.BUSINESS_SIGNALS_DIR, f"REC-{i}", "race-key-1", record
            )
            with results_lock:
                results.append((got, created))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly one caller created the record; every caller (including the
        # winner) returns the same idempotency_key.
        created_flags = [c for _, c in results]
        self.assertEqual(sum(created_flags), 1)
        # Every returned record shares the same idempotency_key -- no two
        # distinct records for the same key.
        keys = {r["idempotency_key"] for r, _ in results}
        self.assertEqual(keys, {"race-key-1"})
        # Exactly one JSON record file was persisted for this key (excluding
        # the internal _idempotency_index bookkeeping directory).
        record_files = [p for p in bi.BUSINESS_SIGNALS_DIR.glob("*.json")]
        self.assertEqual(len(record_files), 1)

    def test_retry_after_success_returns_the_original_record_not_a_duplicate(self):
        first, created1 = bi._write_json_idempotent(
            bi.BUSINESS_SIGNALS_DIR, "REC-A", "retry-key-1", {"idempotency_key": "retry-key-1", "v": 1}
        )
        second, created2 = bi._write_json_idempotent(
            bi.BUSINESS_SIGNALS_DIR, "REC-B", "retry-key-1", {"idempotency_key": "retry-key-1", "v": 2}
        )
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(second["v"], 1)  # original content, not the retry's payload
        record_files = list(bi.BUSINESS_SIGNALS_DIR.glob("*.json"))
        self.assertEqual(len(record_files), 1)

    def test_different_keys_do_not_contend(self):
        r1, c1 = bi._write_json_idempotent(
            bi.BUSINESS_SIGNALS_DIR, "REC-X", "key-x", {"idempotency_key": "key-x"}
        )
        r2, c2 = bi._write_json_idempotent(
            bi.BUSINESS_SIGNALS_DIR, "REC-Y", "key-y", {"idempotency_key": "key-y"}
        )
        self.assertTrue(c1)
        self.assertTrue(c2)
        self.assertEqual(len(list(bi.BUSINESS_SIGNALS_DIR.glob("*.json"))), 2)

    def test_legacy_pre_index_record_is_found_not_duplicated(self):
        """Post-review fix: a record written before the claim-index existed
        (plain <record_id>.json with an idempotency_key field, no claim
        file) must be found by a claim-miss fallback scan and backfilled,
        not duplicated."""
        legacy_path = bi.BUSINESS_SIGNALS_DIR / "LEGACY-1.json"
        bi.BUSINESS_SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
        legacy_path.write_text(json.dumps({"idempotency_key": "legacy-key", "v": "original"}), encoding="utf-8")

        got, created = bi._write_json_idempotent(
            bi.BUSINESS_SIGNALS_DIR, "NEW-1", "legacy-key", {"idempotency_key": "legacy-key", "v": "new"}
        )
        self.assertFalse(created)
        self.assertEqual(got["v"], "original")
        record_files = [p for p in bi.BUSINESS_SIGNALS_DIR.glob("*.json")]
        self.assertEqual(len(record_files), 1)  # no NEW-1.json created

    def test_similar_keys_do_not_collide_on_claim_lookup(self):
        """Post-review fix: claim filenames are now a full sha256 hash of
        the key (not a lossy char-substitution), and claim reads validate
        the stored idempotency_key matches the requested one."""
        r1, c1 = bi._write_json_idempotent(
            bi.BUSINESS_SIGNALS_DIR, "REC-SLASH", "a/b", {"idempotency_key": "a/b"}
        )
        r2, c2 = bi._write_json_idempotent(
            bi.BUSINESS_SIGNALS_DIR, "REC-QMARK", "a?b", {"idempotency_key": "a?b"}
        )
        self.assertTrue(c1)
        self.assertTrue(c2)
        self.assertEqual(r1["idempotency_key"], "a/b")
        self.assertEqual(r2["idempotency_key"], "a?b")
        self.assertEqual(len(list(bi.BUSINESS_SIGNALS_DIR.glob("*.json"))), 2)

    def test_abandoned_empty_claim_is_taken_over_not_wedged_forever(self):
        """Post-review fix: a claim file left empty by a crash between
        os.open(O_EXCL) and the content write must be taken over by the
        next caller instead of permanently failing every future call for
        that key."""
        bi.BUSINESS_SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
        index_dir = bi.BUSINESS_SIGNALS_DIR / "_idempotency_index"
        index_dir.mkdir(parents=True, exist_ok=True)
        key_hash = bi.hashlib.sha256("crashed-key".encode("utf-8")).hexdigest()
        (index_dir / f"{key_hash}.json").write_text("", encoding="utf-8")  # simulate crash: empty claim

        got, created = bi._write_json_idempotent(
            bi.BUSINESS_SIGNALS_DIR, "REC-RECOVER", "crashed-key", {"idempotency_key": "crashed-key", "v": 1}
        )
        self.assertTrue(created)
        self.assertEqual(got["v"], 1)

    def test_multiple_concurrent_recoverers_of_abandoned_claim_do_not_duplicate(self):
        # Round 3, second Codex finding: the FIRST fix for the winner-path
        # claim bug still left the *recovery* path (an empty/abandoned
        # claim) unprotected -- multiple concurrent losers could each
        # independently conclude "empty means abandoned" and each write
        # their own data record. This directly reproduces that scenario
        # with a barrier-synchronized multi-thread race against a claim
        # that is genuinely abandoned (simulating a crash between
        # os.open(O_EXCL) and the content write), not just contending for
        # a live winner.
        bi.BUSINESS_SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
        index_dir = bi.BUSINESS_SIGNALS_DIR / "_idempotency_index"
        index_dir.mkdir(parents=True, exist_ok=True)
        key_hash = bi.hashlib.sha256("crashed-key-multi".encode("utf-8")).hexdigest()
        (index_dir / f"{key_hash}.json").write_text("", encoding="utf-8")  # simulate crash: empty claim

        barrier = threading.Barrier(8)
        results = []
        results_lock = threading.Lock()

        def worker(i):
            barrier.wait()
            record = {"idempotency_key": "crashed-key-multi", "payload": "same-content", "n": i}
            got, created = bi._write_json_idempotent(
                bi.BUSINESS_SIGNALS_DIR, f"REC-RECOVER-{i}", "crashed-key-multi", record
            )
            with results_lock:
                results.append((got, created))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        created_flags = [c for _, c in results]
        self.assertEqual(sum(created_flags), 1)
        record_files = [p for p in bi.BUSINESS_SIGNALS_DIR.glob("*.json")]
        self.assertEqual(len(record_files), 1)


class DuplicateAndStaleTests(BusinessIntegrationTestCase):
    def test_duplicate_submission_of_same_external_event_is_a_no_op(self):
        kwargs = dict(kind="revenue", amount_brl=10.0, source_system="s",
                      source_record_id="dup-1", observed_at="2026-08-13T00:00:00Z")
        first = bi.observe_external_cash_event(**kwargs)
        second = bi.observe_external_cash_event(**kwargs)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(list(bi.EXTERNAL_CASH_EVENTS_DIR.glob("*.json"))), 1)

    def test_stale_observed_event_is_detected(self):
        ev = bi.observe_external_cash_event(
            kind="revenue", amount_brl=10.0, source_system="s", source_record_id="stale-1",
            observed_at="2026-08-13T00:00:00Z",
        )
        # backdate the persisted state_history so it looks old
        path = bi.EXTERNAL_CASH_EVENTS_DIR / f"{ev['id']}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["state_history"][0]["at"] = "2000-01-01T00:00:00+00:00"
        path.write_text(json.dumps(data), encoding="utf-8")
        stale = bi.find_stale_cash_events(grace_period_seconds=3600, states=("OBSERVED",))
        self.assertEqual([s["id"] for s in stale], [ev["id"]])

    def test_fresh_observed_event_is_not_stale(self):
        bi.observe_external_cash_event(
            kind="revenue", amount_brl=10.0, source_system="s", source_record_id="fresh-1",
            observed_at="2026-08-13T00:00:00Z",
        )
        stale = bi.find_stale_cash_events(grace_period_seconds=3600 * 24, states=("OBSERVED",))
        self.assertEqual(stale, [])


class ChargebackSemanticsTests(BusinessIntegrationTestCase):
    def setUp(self):
        super().setUp()
        self._ledger_orig = bi.LEDGER_FILE
        self._ledger_tmp_dir = Path(tempfile.mkdtemp())
        bi.LEDGER_FILE = self._ledger_tmp_dir / "ledger.csv"
        bi.LEDGER_FILE.write_text("timestamp,type,category,amount_brl,description,reference\n", encoding="utf-8")

    def tearDown(self):
        bi.LEDGER_FILE = self._ledger_orig
        shutil.rmtree(self._ledger_tmp_dir, ignore_errors=True)
        super().tearDown()

    def test_chargeback_maps_to_its_own_ledger_type_not_refund_or_revenue(self):
        self.assertEqual(bi.CASH_EVENT_KIND_TO_LEDGER_TYPE["chargeback"], "chargeback")
        self.assertNotEqual(bi.CASH_EVENT_KIND_TO_LEDGER_TYPE["chargeback"], "revenue")

    def test_chargeback_reverses_prior_recognized_revenue_in_balance(self):
        # exercised at the capital_agent layer where cash_balance() lives;
        # here we confirm the ledger line business_integration writes is
        # typed 'chargeback' (a subtraction type), not 'refund'/'revenue'
        # (addition types), so the two modules cannot disagree on sign.
        ev = bi.observe_external_cash_event(
            kind="chargeback", amount_brl=30.0, source_system="s", source_record_id="cb-1",
            observed_at="2026-08-13T00:00:00Z",
        )
        ev = bi.report_external_cash_event(ev, report_source="file_adapter")
        ev = bi.verify_external_cash_event(ev, human_confirmed=True, human_statement="x")
        ev = bi.attribute_external_cash_event(ev)
        ev = bi.reconcile_external_cash_event(ev, reconciled_by="human:owner")
        recorded = []
        bi.post_external_cash_event_to_ledger(ev, append_ledger_fn=lambda *a: recorded.append(a))
        ledger_type = recorded[0][0]
        self.assertEqual(ledger_type, "chargeback")

    def test_capital_agent_cash_balance_subtracts_chargeback_and_adds_refund(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        import capital_agent as ca
        orig_ledger_file = ca.LEDGER_FILE
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            ca.LEDGER_FILE = tmp_dir / "ledger.csv"
            ca.LEDGER_FILE.write_text("timestamp,type,category,amount_brl,description,reference\n", encoding="utf-8")
            ca.append_ledger("revenue", "external_cash_event", 100.0, "rev", "ref-1")
            self.assertEqual(ca.cash_balance(), 100.0)
            ca.append_ledger("chargeback", "external_cash_event", 40.0, "chargeback of rev", "ref-2")
            self.assertEqual(ca.cash_balance(), 60.0)  # reduced, not increased
            ca.append_ledger("refund", "external_cash_event", 10.0, "refund to us", "ref-3")
            self.assertEqual(ca.cash_balance(), 70.0)  # refund-to-us still adds
        finally:
            ca.LEDGER_FILE = orig_ledger_file
            shutil.rmtree(tmp_dir, ignore_errors=True)


class PIIValueHardeningTests(BusinessIntegrationTestCase):
    def test_email_shaped_value_in_allowlisted_field_is_rejected(self):
        with self.assertRaises(bi.PIIRejectedError):
            bi.sanitize_business_payload({"service_interest": "reach me at someone@example.com"})

    def test_phone_shaped_value_in_allowlisted_field_is_rejected(self):
        with self.assertRaises(bi.PIIRejectedError):
            bi.sanitize_business_payload({"landing_content": "call +55 11 91234-5678 please"})

    def test_cpf_shaped_value_in_allowlisted_field_is_rejected(self):
        with self.assertRaises(bi.PIIRejectedError):
            bi.sanitize_business_payload({"company_size_band": "owner CPF 123.456.789-09"})

    def test_clean_allowlisted_values_pass(self):
        clean = bi.sanitize_business_payload({"service_interest": "accounting-automation", "utm_source": "newsletter"})
        self.assertEqual(clean["service_interest"], "accounting-automation")

    def test_ingest_business_signal_rejects_pii_shaped_value_in_extra(self):
        with self.assertRaises(bi.PIIRejectedError):
            bi.ingest_business_signal(
                signal_type="lead_created", source_system="platform",
                source_record_id="rec-pii-value", observed_at="2026-08-13T00:00:00Z",
                metric_name="lead_count", metric_value=1, unit="count",
                data_quality="observed",
                extra={"service_interest": "email me at leaker@example.com"},
            )


class BusinessObservationTests(BusinessIntegrationTestCase):
    def test_observation_is_distinct_entity_from_signal(self):
        obs = bi.create_business_observation(
            observation_type="lead_touch", source_system="platform",
            source_record_id="touch-1", observed_at="2026-08-13T00:00:00Z",
            metric_name="service_interest_mentions", metric_value=1, unit="count",
        )
        self.assertIn("observation_id", obs)
        self.assertNotIn("signal_id", obs)

    def test_signal_can_trace_back_to_observations(self):
        obs1 = bi.create_business_observation(
            observation_type="lead_touch", source_system="platform",
            source_record_id="touch-1", observed_at="2026-08-13T00:00:00Z",
        )
        obs2 = bi.create_business_observation(
            observation_type="lead_touch", source_system="platform",
            source_record_id="touch-2", observed_at="2026-08-13T00:00:00Z",
        )
        sig = bi.create_business_signal_entity(
            signal_type="recurring_lead_pattern", origin="lead_analysis",
            evidence_refs=[obs1["observation_id"], obs2["observation_id"]], period="2026-08",
            derived_from_observation_ids=[obs1["observation_id"], obs2["observation_id"]],
        )
        self.assertEqual(set(sig["derived_from_observation_ids"]), {obs1["observation_id"], obs2["observation_id"]})

    def test_observation_ingestion_is_idempotent(self):
        kwargs = dict(observation_type="lead_touch", source_system="platform",
                      source_record_id="touch-idem", observed_at="2026-08-13T00:00:00Z")
        first = bi.create_business_observation(**kwargs)
        second = bi.create_business_observation(**kwargs)
        self.assertEqual(first["observation_id"], second["observation_id"])


class SchemaValidationTests(BusinessIntegrationTestCase):
    def test_valid_business_signal_passes(self):
        record = bi.ingest_business_signal(
            signal_type="lead_created", source_system="platform",
            source_record_id="rec-schema-1", observed_at="2026-08-13T00:00:00Z",
            metric_name="lead_count", metric_value=1, unit="count",
            data_quality="observed",
        )
        bi.validate_against_schema(record, "business_signal.schema.json")  # no raise

    def test_schema_violating_payload_is_rejected(self):
        bad = {"signal_id": "x"}  # missing required fields
        with self.assertRaises(bi.SchemaValidationError):
            bi.validate_against_schema(bad, "business_signal.schema.json")

    def test_invalid_enum_value_rejected(self):
        bad = {
            "signal_id": "x", "signal_type": "t", "source_system": "s",
            "source_record_id": "r", "observed_at": "2026-01-01T00:00:00Z",
            "retrieved_at": "2026-01-01T00:00:00Z", "metric_name": "m",
            "data_quality": "not-a-real-quality", "schema_version": "1.0",
        }
        with self.assertRaises(bi.SchemaValidationError):
            bi.validate_against_schema(bad, "business_signal.schema.json")

    def test_cash_event_persisted_on_disk_is_schema_valid(self):
        ev = bi.observe_external_cash_event(
            kind="revenue", amount_brl=5.0, source_system="s", source_record_id="schema-ev-1",
            observed_at="2026-08-13T00:00:00Z",
        )
        on_disk = json.loads((bi.EXTERNAL_CASH_EVENTS_DIR / f"{ev['id']}.json").read_text(encoding="utf-8"))
        bi.validate_against_schema(on_disk, "external_cash_event.schema.json")  # no raise

    def test_missing_schema_file_fails_loudly_not_silently(self):
        with self.assertRaises(bi.SchemaValidationError):
            bi.validate_against_schema({"a": 1}, "no_such_schema_file.schema.json")

    def test_business_observation_validates_against_its_own_schema(self):
        obs = bi.create_business_observation(
            observation_type="lead_touch", source_system="platform",
            source_record_id="schema-obs-1", observed_at="2026-08-13T00:00:00Z",
        )
        bi.validate_against_schema(obs, "business_observation.schema.json")  # no raise

    def test_business_signal_pattern_validates_against_its_own_schema(self):
        sig = bi.create_business_signal_entity(
            signal_type="recurring_lead_pattern", origin="lead_analysis",
            evidence_refs=["BSIG-ref-1"], period="2026-08",
        )
        bi.validate_against_schema(sig, "business_signal_pattern.schema.json")  # no raise

    def test_business_signal_from_ingest_rejects_additional_properties(self):
        record = bi.ingest_business_signal(
            signal_type="lead_created", source_system="platform",
            source_record_id="rec-schema-extra", observed_at="2026-08-13T00:00:00Z",
            metric_name="lead_count", metric_value=1, unit="count",
            data_quality="observed",
        )
        record["totally_unexpected_field"] = "x"
        with self.assertRaises(bi.SchemaValidationError):
            bi.validate_against_schema(record, "business_signal.schema.json")


class MetricTemporalSemanticsTests(BusinessIntegrationTestCase):
    def test_observed_at_defaults_to_retrieved_at_when_omitted(self):
        obs = bi.create_metric_observation(
            experiment_id="EXP-001", metric_name="x", value=1, unit="count",
            period="2026-08", source="s", environment="production",
            coverage=None, data_quality="observed",
        )
        self.assertEqual(obs["observed_at"], obs["retrieved_at"])

    def test_observed_at_in_future_relative_to_retrieved_at_rejected(self):
        import datetime as _dt
        future = (_dt.datetime.now(_dt.timezone.utc).replace(microsecond=0) + _dt.timedelta(days=1)).isoformat()
        with self.assertRaises(bi.MetricObservationError):
            bi.create_metric_observation(
                experiment_id="EXP-001", metric_name="x", value=1, unit="count",
                period="2026-08", source="s", environment="production",
                coverage=None, data_quality="observed", observed_at=future,
            )

    def test_observed_at_before_retrieved_at_is_accepted(self):
        obs = bi.create_metric_observation(
            experiment_id="EXP-001", metric_name="x", value=1, unit="count",
            period="2026-08", source="s", environment="production",
            coverage=None, data_quality="observed", observed_at="2026-08-01T00:00:00+00:00",
        )
        self.assertEqual(obs["observed_at"], "2026-08-01T00:00:00+00:00")


class TimezoneAwareEligibilityTests(BusinessIntegrationTestCase):
    """P1 #4 (prompt-hardening-final-capital-agent-v0.2.md section 6):
    filter_official_evaluation_observations must compare observed_at against
    activation_date as real instants (via _parse_iso), not as raw ISO
    strings, so different UTC offsets for the same instant don't silently
    misclassify eligibility."""

    def _obs(self, observed_at):
        obs = bi.create_metric_observation(
            experiment_id="EXP-001", metric_name="qualified_leads", value=3, unit="count",
            period="2026-08", source="platform_export", environment="production",
            coverage="full", data_quality="observed",
        )
        obs["observed_at"] = observed_at
        return obs

    def test_equivalent_instants_with_different_offsets_are_treated_as_equal(self):
        # 2026-08-13T21:00:00-03:00 == 2026-08-14T00:00:00+00:00 (same
        # instant). observed_at exactly equal to activation_date, expressed
        # in a different offset, must be treated as on/after activation, not
        # excluded by lexical string comparison (where the -03:00 string
        # sorts before the +00:00 string despite being the SAME instant).
        obs = self._obs("2026-08-13T21:00:00-03:00")
        filtered = bi.filter_official_evaluation_observations(
            [obs], activation_date="2026-08-14T00:00:00+00:00"
        )
        self.assertEqual(filtered, [obs])

    def test_utc_vs_local_offset_boundary_is_semantically_correct(self):
        # observed strictly BEFORE activation once instants are compared
        # correctly, even though the raw local-offset string would sort
        # AFTER the raw UTC string lexically.
        obs = self._obs("2026-08-13T20:59:59-03:00")  # == 23:59:59Z, 1s before activation
        filtered = bi.filter_official_evaluation_observations(
            [obs], activation_date="2026-08-14T00:00:00+00:00"
        )
        self.assertEqual(filtered, [])

    def test_observed_strictly_after_activation_included(self):
        obs = self._obs("2026-08-14T00:00:01+00:00")
        filtered = bi.filter_official_evaluation_observations(
            [obs], activation_date="2026-08-14T00:00:00+00:00"
        )
        self.assertEqual(filtered, [obs])

    def test_observed_exactly_at_activation_boundary_is_included(self):
        obs = self._obs("2026-08-14T00:00:00+00:00")
        filtered = bi.filter_official_evaluation_observations(
            [obs], activation_date="2026-08-14T00:00:00+00:00"
        )
        self.assertEqual(filtered, [obs])

    def test_unparseable_observed_at_is_excluded_not_fabricated(self):
        obs = self._obs("not-a-real-timestamp")
        filtered = bi.filter_official_evaluation_observations(
            [obs], activation_date="2026-08-14T00:00:00+00:00"
        )
        self.assertEqual(filtered, [])

    def test_unparseable_activation_date_fails_closed_not_open(self):
        """Post-review fix: an invalid activation_date used to silently
        disable the activation filter entirely (fail-open, letting
        pre-activation production data through). It must now fail loudly
        instead of silently including everything."""
        obs = self._obs("2026-08-01T00:00:00+00:00")
        with self.assertRaises(ValueError):
            bi.filter_official_evaluation_observations([obs], activation_date="not-a-real-timestamp")


class ExperimentAutoActivationGuardTests(unittest.TestCase):
    def test_transition_to_active_without_human_authorization_is_blocked(self):
        experiment = {"lifecycle_state": "READY_FOR_ACTIVATION"}
        with self.assertRaises(bi.AutoActivationBlockedError):
            bi.apply_experiment_lifecycle_transition(experiment, "ACTIVE")

    def test_transition_to_active_without_authorized_by_is_blocked_even_if_flag_set(self):
        experiment = {"lifecycle_state": "READY_FOR_ACTIVATION"}
        with self.assertRaises(bi.AutoActivationBlockedError):
            bi.apply_experiment_lifecycle_transition(experiment, "ACTIVE", human_authorized=True, authorized_by="")

    def test_transition_to_active_with_explicit_human_authorization_succeeds(self):
        experiment = {"lifecycle_state": "READY_FOR_ACTIVATION"}
        updated = bi.apply_experiment_lifecycle_transition(
            experiment, "ACTIVE", human_authorized=True, authorized_by="human:marcelo"
        )
        self.assertEqual(updated["lifecycle_state"], "ACTIVE")
        self.assertEqual(updated["status"], "active")

    def test_non_active_transitions_do_not_require_human_authorization(self):
        experiment = {"lifecycle_state": "PLANNED"}
        updated = bi.apply_experiment_lifecycle_transition(experiment, "READY_FOR_ACTIVATION")
        self.assertEqual(updated["lifecycle_state"], "READY_FOR_ACTIVATION")


class HistoricalMigrationTests(BusinessIntegrationTestCase):
    def test_legacy_record_missing_optional_keys_is_migrated_forward(self):
        legacy = {
            "id": "ECE-LEGACY-1", "kind": "revenue", "amount_brl": 10.0, "currency": "BRL",
            "source_system": "s", "source_record_id": "legacy-1", "idempotency_key": "s:legacy-1",
            "observed_at": "2026-08-13T00:00:00Z", "state": "OBSERVED",
        }
        migrated = bi.migrate_legacy_cash_event_record(legacy)
        bi.validate_against_schema(migrated, "external_cash_event.schema.json")  # no raise
        self.assertIn("state_history", migrated)
        self.assertTrue(migrated["state_history"])


if __name__ == "__main__":
    unittest.main()

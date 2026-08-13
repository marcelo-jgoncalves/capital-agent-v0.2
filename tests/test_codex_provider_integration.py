"""Tests for the Codex reasoning-provider integration.

Never invokes the real `codex` binary (would be non-deterministic / require
network+auth in CI). All provider calls are through monkeypatched
adapters.ai_providers.codex_cli functions -- the one real invocation lives
outside the suite as a manual smoke test (see journal/reviews or the
readiness report).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.ai_providers import codex_cli  # noqa: E402
from adapters.ai_providers.codex_adapter import CodexAdapter  # noqa: E402
from adapters.ai_providers.task_envelope import TaskEnvelope, TaskEnvelopeError  # noqa: E402
from adapters.ai_providers import ai_run_log  # noqa: E402
import src.editorial_research as editorial_research  # noqa: E402
import src.critic as critic  # noqa: E402
import src.reasoning_router as reasoning_router  # noqa: E402


class FakeHealth:
    def __init__(self, available, version="0.147.0", error=None):
        self.available = available
        self.version = version
        self.error = error
        self.supports_non_interactive = available
        self.supports_structured_output = True

    def to_dict(self):
        return {"provider": "codex", "available": self.available, "version": self.version,
                "error": self.error}


class FakeExec:
    def __init__(self, exit_code=0, stdout="", stderr="", timed_out=False, duration_seconds=0.01):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out
        self.duration_seconds = duration_seconds


class IsolatedStateMixin:
    """Redirect state writes to a temp dir so tests never touch the real
    repository's state/ (which is real audit history)."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._orig_ai_runs = ai_run_log.RUN_LOG_DIR if hasattr(ai_run_log, "RUN_LOG_DIR") else None
        for mod, attr in [(ai_run_log, "RUN_LOG_DIR")]:
            if hasattr(mod, attr):
                setattr(mod, attr, Path(self._tmpdir) / "ai_runs")
        for mod, attr in [(editorial_research, "BRIEFS_DIR"), (editorial_research, "CANDIDATES_DIR"),
                          (editorial_research, "POOLS_DIR")]:
            setattr(mod, attr, Path(self._tmpdir) / attr.lower())

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)


class TestTaskEnvelope(unittest.TestCase):
    def test_rejects_unknown_task_type(self):
        env = TaskEnvelope(task_id="t1", task_type="NOT_A_TYPE")
        with self.assertRaises(TaskEnvelopeError):
            env.validate()

    def test_rejects_financial_write_capability(self):
        env = TaskEnvelope(task_id="t1", task_type="TOPIC_DISCOVERY",
                            allowed_capabilities=["financial_write"])
        with self.assertRaises(TaskEnvelopeError):
            env.validate()

    def test_rejects_workspace_write_for_research_task(self):
        env = TaskEnvelope(task_id="t1", task_type="TOPIC_DISCOVERY", workspace_write=True)
        with self.assertRaises(TaskEnvelopeError):
            env.validate()

    def test_allows_workspace_write_for_code_review_type(self):
        env = TaskEnvelope(task_id="t1", task_type="CODE_REVIEW", workspace_write=True)
        env.validate()  # must not raise

    def test_valid_research_envelope_passes(self):
        env = TaskEnvelope(task_id="t1", task_type="FACT_CHECK", allowed_capabilities=["read_repository"])
        env.validate()

    def test_task_cannot_smuggle_full_access_via_sandbox_string(self):
        # There is no field on TaskEnvelope that accepts a raw sandbox
        # string at all -- only a boolean. This test documents that
        # invariant structurally.
        self.assertNotIn("sandbox", TaskEnvelope.__dataclass_fields__)


class TestCodexAdapterAvailability(IsolatedStateMixin, unittest.TestCase):
    def test_unavailable_provider_marks_run_unavailable(self):
        codex_cli.healthcheck = lambda force=False: FakeHealth(False, version=None, error="codex not on PATH")
        adapter = CodexAdapter()
        env = TaskEnvelope(task_id="t1", task_type="TOPIC_DISCOVERY", prompt="x")
        result = adapter.run_task(env)
        self.assertEqual(result["exit_status"], "PROVIDER_UNAVAILABLE")

    def test_nonzero_exit_code_marks_failed(self):
        codex_cli.healthcheck = lambda force=False: FakeHealth(True)
        codex_cli.run_codex_exec = lambda *a, **k: FakeExec(exit_code=1, stderr="boom")
        adapter = CodexAdapter()
        env = TaskEnvelope(task_id="t1", task_type="TOPIC_DISCOVERY", prompt="x")
        result = adapter.run_task(env)
        self.assertEqual(result["exit_status"], "FAILED")

    def test_timeout_marks_timeout(self):
        codex_cli.healthcheck = lambda force=False: FakeHealth(True)
        codex_cli.run_codex_exec = lambda *a, **k: FakeExec(timed_out=True, exit_code=-1)
        adapter = CodexAdapter()
        env = TaskEnvelope(task_id="t1", task_type="TOPIC_DISCOVERY", prompt="x")
        result = adapter.run_task(env)
        self.assertEqual(result["exit_status"], "TIMEOUT")

    def test_invalid_structured_output_fails_safely(self):
        codex_cli.healthcheck = lambda force=False: FakeHealth(True)
        codex_cli.run_codex_exec = lambda *a, **k: FakeExec(exit_code=0, stdout="not json{{{")
        adapter = CodexAdapter()
        env = TaskEnvelope(task_id="t1", task_type="TOPIC_DISCOVERY", prompt="x",
                            output_schema="schemas/topic_discovery_result.schema.json")
        result = adapter.run_task(env)
        self.assertEqual(result["exit_status"], "SCHEMA_MISMATCH")
        self.assertIsNone(result["output_parsed"])

    def test_valid_structured_output_parses(self):
        codex_cli.healthcheck = lambda force=False: FakeHealth(True)
        codex_cli.run_codex_exec = lambda *a, **k: FakeExec(exit_code=0, stdout=json.dumps({"ok": True}))
        adapter = CodexAdapter()
        env = TaskEnvelope(task_id="t1", task_type="TOPIC_DISCOVERY", prompt="x",
                            output_schema="schemas/topic_discovery_result.schema.json")
        result = adapter.run_task(env)
        self.assertEqual(result["exit_status"], "OK")
        self.assertEqual(result["output_parsed"], {"ok": True})

    def test_run_metadata_is_persisted(self):
        codex_cli.healthcheck = lambda force=False: FakeHealth(True)
        codex_cli.run_codex_exec = lambda *a, **k: FakeExec(exit_code=0, stdout="hello")
        adapter = CodexAdapter()
        env = TaskEnvelope(task_id="t1", task_type="TOPIC_DISCOVERY", prompt="x")
        result = adapter.run_task(env)
        runs = ai_run_log.list_runs()
        self.assertTrue(any(r["run_id"] == result["run_id"] for r in runs))

    def test_run_metadata_has_no_secret_like_keys(self):
        codex_cli.healthcheck = lambda force=False: FakeHealth(True)
        codex_cli.run_codex_exec = lambda *a, **k: FakeExec(exit_code=0, stdout="hello")
        adapter = CodexAdapter()
        env = TaskEnvelope(task_id="t1", task_type="TOPIC_DISCOVERY", prompt="x")
        adapter.run_task(env)
        runs = ai_run_log.list_runs()
        blob = json.dumps(runs).lower()
        for marker in ("token", "password", "secret", "auth_key"):
            self.assertNotIn(marker, blob)


class TestBlindIsolation(IsolatedStateMixin, unittest.TestCase):
    def test_blind_prompt_has_no_reference_to_other_provider_output(self):
        brief = editorial_research.ResearchBrief(brief_id="B1", site_positioning="x")
        prompt = editorial_research.build_blind_prompt(brief)
        self.assertNotIn("claude candidates", prompt.lower())
        self.assertNotIn("codex candidates", prompt.lower())

    def test_candidates_require_provenance_fields(self):
        with self.assertRaises(ValueError):
            editorial_research.save_candidates("B1", "claude", [{"topic_id": "x"}])

    def test_save_candidates_rejects_unknown_origin(self):
        with self.assertRaises(ValueError):
            editorial_research.save_candidates("B1", "gemini", [])

    def test_merge_preserves_provenance(self):
        claude_c = [{"topic_id": "c1", "proposed_title": "Same Topic", "core_problem": "p", "confidence": "high"}]
        codex_c = [{"topic_id": "x1", "proposed_title": "same topic", "core_problem": "p2", "confidence": "medium"}]
        editorial_research.save_candidates("B1", "claude", claude_c)
        editorial_research.save_candidates("B1", "codex", codex_c)
        merged = editorial_research.merge_and_dedupe("B1")
        self.assertEqual(len(merged), 1)
        self.assertIn("claude", merged[0]["origins"])
        self.assertIn("codex", merged[0]["origins"])

    def test_dedupe_keeps_distinct_topics_separate(self):
        editorial_research.save_candidates("B2", "claude", [
            {"topic_id": "c1", "proposed_title": "Topic A", "core_problem": "p", "confidence": "high"}])
        editorial_research.save_candidates("B2", "codex", [
            {"topic_id": "x1", "proposed_title": "Topic B", "core_problem": "p", "confidence": "high"}])
        merged = editorial_research.merge_and_dedupe("B2")
        self.assertEqual(len(merged), 2)

    def test_scoring_does_not_accept_out_of_range_values(self):
        candidate = {"topic_id": "c1", "proposed_title": "T", "core_problem": "p", "confidence": "high", "origin": "claude"}
        with self.assertRaises(ValueError):
            editorial_research.score_candidate(candidate, {"audience_relevance": 9})

    def test_scoring_does_not_invent_composite_precision(self):
        candidate = {"topic_id": "c1", "proposed_title": "T", "core_problem": "p", "confidence": "high", "origin": "claude"}
        scored = editorial_research.score_candidate(candidate, {"audience_relevance": 3})
        self.assertNotIn("composite_score", scored)


class TestCritic(IsolatedStateMixin, unittest.TestCase):
    def test_critic_unavailable_is_not_a_fake_approval(self):
        codex_cli.healthcheck = lambda force=False: FakeHealth(False, error="down")
        result = critic.blind_second_opinion("t1", "Should we do X?", "facts here")
        self.assertEqual(critic.critic_status_for_run(result), "CRITIC_UNAVAILABLE")

    def test_critic_failed_is_distinct_from_unavailable(self):
        codex_cli.healthcheck = lambda force=False: FakeHealth(True)
        codex_cli.run_codex_exec = lambda *a, **k: FakeExec(exit_code=1, stderr="err")
        result = critic.adversarial_review("t1", "Q", "primary conclusion", "facts")
        self.assertEqual(critic.critic_status_for_run(result), "CRITIC_FAILED")

    def test_disagreement_is_not_resolved_by_majority(self):
        # There is no vote-count/majority function anywhere in critic.py;
        # build_disagreement_review always requires human_intervention_required
        # to be explicit, never computed from an aggregate.
        review = critic.build_disagreement_review(
            question="Q", primary_provider="claude", primary_conclusion="A",
            second_provider="codex", second_conclusion="B", common_facts=["f1"],
            disputed_assumptions=["a1"], missing_evidence=[],
            decision_impact="high", human_intervention_required=True,
        )
        self.assertTrue(review["human_intervention_required"])
        self.assertNotIn("vote_count", review)

    def test_disagreement_review_is_persisted(self):
        review = critic.build_disagreement_review(
            question="Q", primary_provider="claude", primary_conclusion="A",
            second_provider="codex", second_conclusion="B", common_facts=[],
            disputed_assumptions=[], missing_evidence=[], decision_impact="low",
            human_intervention_required=False,
        )
        critic.DISAGREEMENTS_DIR = Path(self._tmpdir) / "disagreements"
        p = critic.persist_disagreement(review, "REV-1")
        self.assertTrue(p.exists())


class TestRouter(unittest.TestCase):
    def test_second_opinion_policy_required(self):
        self.assertEqual(reasoning_router.second_opinion_policy("DECISION_CRITIC"), "REQUIRED_WHEN_AVAILABLE")

    def test_second_opinion_policy_avoid_for_unknown(self):
        self.assertEqual(reasoning_router.second_opinion_policy("DRAFT"), "OPTIONAL")

    def test_resolve_provider_raises_when_unavailable(self):
        orig = reasoning_router.available_providers
        reasoning_router.available_providers = lambda: {"codex": False, "claude": True}
        try:
            env = TaskEnvelope(task_id="t1", task_type="CODE_REVIEW", provider="codex")
            with self.assertRaises(reasoning_router.ProviderUnavailable):
                reasoning_router.resolve_provider(env)
        finally:
            reasoning_router.available_providers = orig

    def test_auto_resolves_to_a_concrete_provider(self):
        orig = reasoning_router.available_providers
        reasoning_router.available_providers = lambda: {"codex": True, "claude": True}
        try:
            env = TaskEnvelope(task_id="t1", task_type="CODE_REVIEW", provider="auto")
            self.assertEqual(reasoning_router.resolve_provider(env), "codex")
        finally:
            reasoning_router.available_providers = orig

    def test_invalid_envelope_fails_closed_before_provider_call(self):
        env = TaskEnvelope(task_id="t1", task_type="NOT_A_TYPE")
        with self.assertRaises(TaskEnvelopeError):
            reasoning_router.run(env)


class TestProviderRegistry(unittest.TestCase):
    def test_unknown_function_rejected(self):
        import src.provider_registry as provider_registry
        tmp = Path(tempfile.mkdtemp()) / "perf.json"
        orig = provider_registry.REGISTRY_FILE
        provider_registry.REGISTRY_FILE = tmp
        try:
            with self.assertRaises(ValueError):
                provider_registry.record_feedback("codex", "not_a_function", "acceptance_rate", 1)
        finally:
            provider_registry.REGISTRY_FILE = orig

    def test_feedback_is_recorded_as_raw_observation(self):
        import src.provider_registry as provider_registry
        tmp = Path(tempfile.mkdtemp()) / "perf.json"
        orig = provider_registry.REGISTRY_FILE
        provider_registry.REGISTRY_FILE = tmp
        try:
            provider_registry.record_feedback("codex", "code_review", "bugs_found", 3)
            s = provider_registry.summary()
            self.assertEqual(s["codex"]["code_review"], 1)
        finally:
            provider_registry.REGISTRY_FILE = orig


if __name__ == "__main__":
    unittest.main()

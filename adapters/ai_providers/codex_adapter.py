"""Codex CLI provider adapter.

Implements the `AIProviderAdapter` contract (adapters/ai_providers/base.py)
plus a richer `run_task()` entry point used by the Reasoning Router,
Editorial Research System and Critic/second-opinion system.

Hard invariants enforced here (see AI_OPERATING_MANUAL.md custody clause and
prompt-integracao-codex-capital-agent.md sections 5/6/44):

- never reads/copies/exports `~/.codex/` or any auth/credential file;
- never grants a financial-write capability (task_envelope.py rejects it
  before this module ever sees such a request);
- read-only sandbox is the default; workspace-write only when the envelope
  explicitly requests it AND the task_type is one of the engineering types
  that TaskEnvelope.validate() allows;
- danger-full-access is never used;
- every invocation is recorded to state/ai_runs/ (never with secrets).
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import AIProviderAdapter
from . import ai_run_log
from . import codex_cli
from .task_envelope import TaskEnvelope, TaskEnvelopeError

ROOT = Path(__file__).resolve().parents[2]


def _sandbox_for(envelope: TaskEnvelope) -> str:
    """Deterministic, non-overridable mapping. This is the only place a
    sandbox mode is chosen -- the envelope's workspace_write is a boolean,
    never a raw sandbox string, so a task cannot request danger-full-access
    even by malformed input."""
    return "workspace-write" if envelope.workspace_write else "read-only"


class CodexAdapter(AIProviderAdapter):
    name = "codex"

    def is_available(self) -> bool:
        return codex_cli.healthcheck().available

    def healthcheck(self) -> dict:
        return codex_cli.healthcheck().to_dict()

    # -- AIProviderAdapter contract: dispatch a scheduler job ticket -------
    def dispatch(self, job: dict) -> dict:
        """Best-effort mapping from a generic scheduler job ticket to a
        read-only research TaskEnvelope. Mirrors manual_adapter's honesty:
        this does not silently promise more than it does. Actual structured
        task routing goes through run_task()/reasoning_router.py."""
        hc = codex_cli.healthcheck()
        if not hc.available:
            return {"status": "unavailable", "job_id": job.get("id"), "reason": hc.error}
        envelope = TaskEnvelope(
            task_id=str(job.get("id")),
            task_type="POLICY_AUDIT" if job.get("kind") == "trigger" else "TOPIC_DISCOVERY",
            provider="codex",
            allowed_capabilities=["read_repository"],
            workspace_write=False,
            criticality="noncritical",
            prompt=(
                "You are assisting the Capital Agent (see START_HERE.md). "
                f"Job context: {job.get('context_hint')}. This is a read-only "
                "research pass; do not modify files. Respond with findings only."
            ),
        )
        result = self.run_task(envelope)
        return {"status": result["exit_status"], "job_id": job.get("id"), "run_id": result["run_id"]}

    # -- Richer entry point used by router/editorial/critic ----------------
    def run_task(self, envelope: TaskEnvelope, *, timeout: int = 120) -> dict:
        try:
            envelope.validate()
        except TaskEnvelopeError as e:
            raise

        hc = codex_cli.healthcheck()
        started_at = codex_cli.now_iso()

        if not hc.available:
            ended_at = codex_cli.now_iso()
            ai_run_log.record_run(
                task_id=envelope.task_id, provider="codex", role=envelope.task_type,
                started_at=started_at, ended_at=ended_at,
                input_context_refs=envelope.input_context_refs, output_artifact=None,
                exit_status="PROVIDER_UNAVAILABLE",
                capabilities_used=[], web_search_used=False, workspace_write_used=False,
                errors=[hc.error or "codex unavailable"],
            )
            return {"exit_status": "PROVIDER_UNAVAILABLE", "output": None, "run_id": None, "error": hc.error}

        sandbox = _sandbox_for(envelope)
        schema_path = Path(envelope.output_schema) if envelope.output_schema else None
        run_result = codex_cli.run_codex_exec(
            envelope.prompt, sandbox=sandbox, workdir=ROOT,
            output_schema_path=schema_path, timeout=timeout,
        )
        ended_at = codex_cli.now_iso()

        output_text = run_result.stdout.strip()
        parsed = None
        exit_status = "OK"
        errors = []

        if run_result.timed_out:
            exit_status = "TIMEOUT"
            errors.append("codex exec timed out")
        elif run_result.exit_code != 0:
            exit_status = "FAILED"
            errors.append(f"exit_code={run_result.exit_code}; stderr={run_result.stderr[:500]}")
        elif schema_path is not None:
            # Defensive parsing per spec section 37/48: never assume
            # well-formed structured output even if the flag was accepted.
            try:
                parsed = json.loads(output_text)
            except (json.JSONDecodeError, ValueError):
                exit_status = "SCHEMA_MISMATCH"
                errors.append("structured output did not parse as JSON")

        record = ai_run_log.record_run(
            task_id=envelope.task_id, provider="codex", role=envelope.task_type,
            started_at=started_at, ended_at=ended_at,
            input_context_refs=envelope.input_context_refs,
            output_artifact=None,
            exit_status=exit_status,
            capabilities_used=list(envelope.allowed_capabilities),
            web_search_used=False,  # not confirmed reachable via CLI flags in this version
            workspace_write_used=envelope.workspace_write,
            errors=errors,
            provider_metadata={"version": hc.version, "duration_seconds": round(run_result.duration_seconds, 3)},
        )

        return {
            "exit_status": exit_status,
            "output_text": output_text if exit_status in ("OK", "SCHEMA_MISMATCH") else None,
            "output_parsed": parsed,
            "run_id": record["run_id"],
            "errors": errors,
        }

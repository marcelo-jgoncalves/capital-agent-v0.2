"""Engineering review jobs run via Codex (spec section 27-30).

code_review / adversarial_tests / policy_implementation_audit. All default
to read-only sandbox; workspace-write is only requested for
ADVERSARIAL_TESTS when the caller explicitly authorizes writing new test
files, and even then never for POLICY_AUDIT or CODE_REVIEW (task_envelope.py
enforces this -- these three task types cannot both request workspace_write
except ADVERSARIAL_TESTS, matching TaskEnvelope.validate()'s allow-list).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.ai_providers.task_envelope import TaskEnvelope  # noqa: E402
from adapters.ai_providers.codex_adapter import CodexAdapter  # noqa: E402

CODE_REVIEW_SCHEMA = ROOT / "schemas" / "code_review_result.schema.json"


def code_review(task_id: str, diff_or_area_description: str) -> dict:
    prompt = (
        "Perform a code review for the Capital Agent repository. Look for "
        "correctness bugs, secret leakage, shell injection, prompt "
        "injection, unsafe subprocess use, path traversal, privilege "
        "escalation, financial write paths, approval bypass, state "
        "spoofing, and scheduler idempotency issues. Do not modify files -- "
        "this is review-only.\n\n"
        f"Area/diff to review:\n{diff_or_area_description}\n\n"
        "Respond as CodeReviewResult JSON."
    )
    envelope = TaskEnvelope(
        task_id=task_id, task_type="CODE_REVIEW", provider="codex",
        allowed_capabilities=["read_repository"], workspace_write=False,
        criticality="material", output_schema=str(CODE_REVIEW_SCHEMA), prompt=prompt,
    )
    return CodexAdapter().run_task(envelope)


def adversarial_tests(task_id: str, requirements_and_implementation: str, *, authorize_write: bool) -> dict:
    """Priority invariants per spec 28: human-only financial execution,
    reconciliation-before-ledger, critical approval, append-only evidence,
    context integrity, scheduler idempotency, provider isolation, prompt
    injection boundaries. `authorize_write=False` runs review-only and
    returns proposed test code as text instead of writing it."""
    prompt = (
        "Given the following requirements and implementation, act as an "
        "adversarial tester. Try to break these invariants: human-only "
        "financial execution; reconciliation before ledger; critical "
        "approval; append-only evidence; context integrity; scheduler "
        "idempotency; provider isolation; prompt injection boundaries.\n\n"
        f"{requirements_and_implementation}\n\n"
        "Respond as CodeReviewResult JSON, using 'issues' for broken "
        "invariants found."
    )
    envelope = TaskEnvelope(
        task_id=task_id, task_type="ADVERSARIAL_TESTS", provider="codex",
        mode="adversarial",
        allowed_capabilities=(["read_repository", "write_workspace"] if authorize_write else ["read_repository"]),
        workspace_write=authorize_write, criticality="material",
        output_schema=str(CODE_REVIEW_SCHEMA), prompt=prompt,
    )
    return CodexAdapter().run_task(envelope)


def policy_implementation_audit(task_id: str, policy_area: str) -> dict:
    """POLICY_IMPLEMENTATION_AUDIT (spec 29): does the code actually
    implement the canonical policy, not just documentation. Read-only."""
    prompt = (
        f"Audit whether the Capital Agent's code actually enforces the "
        f"canonical policy for: {policy_area}. Documentation alone does "
        "not prove enforcement -- cite the specific file/function that "
        "enforces (or fails to enforce) each claim. Do not modify files.\n\n"
        "Respond as CodeReviewResult JSON, treating each policy claim not "
        "backed by enforcing code as an 'issue'."
    )
    envelope = TaskEnvelope(
        task_id=task_id, task_type="POLICY_AUDIT", provider="codex",
        allowed_capabilities=["read_repository"], workspace_write=False,
        criticality="material", output_schema=str(CODE_REVIEW_SCHEMA), prompt=prompt,
    )
    return CodexAdapter().run_task(envelope)

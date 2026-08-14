"""Reasoning Router (spec section 7/23/34).

Picks which reasoning provider handles a task envelope. Contains the
explicit, evolvable "Second Model Value Policy" rules (section 34): which
task types REQUIRE a second provider when available, which are RECOMMENDED,
OPTIONAL, or should AVOID calling an LLM at all.

This module names Claude and Codex only as adapter identifiers -- it is not
a policy document. Canonical policy (custody, human gates, criticality)
lives in AI_OPERATING_MANUAL.md / CRITICAL_DECISIONS.md / HUMAN_GATES.md and
is only referenced here, never restated.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.ai_providers.task_envelope import TaskEnvelope  # noqa: E402
from adapters.ai_providers.codex_adapter import CodexAdapter  # noqa: E402

# Section 34: which task types require a second provider critic *when
# available*. Absence of Codex must never block the primary provider from
# proceeding (spec 47/58 -- Codex is never mandatory).
SECOND_OPINION_REQUIRED_WHEN_AVAILABLE = {
    "DECISION_CRITIC", "BLIND_SECOND_OPINION",
}
SECOND_OPINION_RECOMMENDED = {
    "TOPIC_DISCOVERY", "FACT_CHECK", "POLICY_AUDIT", "POSTMORTEM_REVIEW",
}
SECOND_OPINION_OPTIONAL = {
    "CONTENT_BRIEF", "DRAFT", "EDITORIAL_CRITIC", "CODE_REVIEW",
}
# Deterministic/no-LLM-needed task types are intentionally not represented
# here at all -- the router is only ever consulted for reasoning tasks.

DETERMINISTIC_TASK_TYPES: set[str] = set()  # placeholder: none of the 12 task
# types above are purely deterministic; a future formatting/arithmetic-only
# task type would be added here and short-circuited before any provider call.


class ProviderUnavailable(Exception):
    pass


def available_providers() -> dict:
    codex = CodexAdapter()
    return {
        "codex": codex.is_available(),
        # Claude is the primary/current interactive operator; this router
        # does not need a programmatic Claude adapter to be useful today --
        # see ARCHITECTURE.md "Scheduler and orchestration" and
        # adapters/ai_providers/README.md for why the manual adapter is the
        # reference implementation for the primary provider.
        "claude": True,
    }


def resolve_provider(envelope: TaskEnvelope) -> str:
    """Resolve `provider="auto"` to a concrete provider name. Never invents
    availability: if the resolved provider is unavailable, raises
    ProviderUnavailable so the caller applies fallback policy explicitly
    (spec section 47) rather than silently downgrading."""
    envelope.validate()

    if envelope.provider != "auto":
        chosen = envelope.provider
    else:
        # Simple explicit rule set (section 23): engineering review and
        # blind/critic tasks default to codex when available; editorial
        # topic discovery in blind mode wants both (handled by the caller,
        # not this single-provider resolver).
        if envelope.task_type in ("CODE_REVIEW", "ADVERSARIAL_TESTS", "POLICY_AUDIT"):
            chosen = "codex"
        elif envelope.task_type in ("DECISION_CRITIC", "BLIND_SECOND_OPINION"):
            chosen = "codex"
        else:
            chosen = "claude"

    avail = available_providers()
    if not avail.get(chosen, False):
        raise ProviderUnavailable(f"provider '{chosen}' is not available")
    return chosen


def second_opinion_policy(task_type: str) -> str:
    if task_type in SECOND_OPINION_REQUIRED_WHEN_AVAILABLE:
        return "REQUIRED_WHEN_AVAILABLE"
    if task_type in SECOND_OPINION_RECOMMENDED:
        return "RECOMMENDED"
    if task_type in SECOND_OPINION_OPTIONAL:
        return "OPTIONAL"
    return "AVOID"


def run(envelope: TaskEnvelope) -> dict:
    """Resolve provider and execute. Raises TaskEnvelopeError for invalid
    envelopes (fails closed, does not attempt to run anyway)."""
    envelope.validate()
    provider = resolve_provider(envelope)
    if provider == "codex":
        return CodexAdapter().run_task(envelope)
    raise NotImplementedError(
        "claude has no programmatic adapter in this repository yet -- the "
        "manual/interactive session is the current 'claude' execution path "
        "(see adapters/ai_providers/manual_adapter.py); router.run() is only "
        "wired for programmatic (codex) execution today."
    )

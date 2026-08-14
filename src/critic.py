"""Second opinion / critic / disagreement protocol (spec section 24-26, 34).

The critic must try to refute, not confirm (section 24). Supports both
blind second opinion (no primary conclusion shared) and adversarial review
(primary conclusion shared, critic tries to break it). Divergence is never
resolved by majority vote (section 26) -- a DISAGREEMENT_REVIEW artifact is
produced and, when material, human authorization is required per
CRITICAL_DECISIONS.md / HUMAN_GATES.md (unchanged, canonical, not restated
here).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.ai_providers.task_envelope import TaskEnvelope  # noqa: E402
from adapters.ai_providers.codex_adapter import CodexAdapter  # noqa: E402

DISAGREEMENTS_DIR = ROOT / "state" / "critic" / "disagreements"
CRITIC_RUNS_DIR = ROOT / "state" / "critic" / "runs"

DECISION_CRITIC_SCHEMA = ROOT / "schemas" / "decision_critic_result.schema.json"
DISAGREEMENT_SCHEMA = ROOT / "schemas" / "disagreement_review.schema.json"

REFUTE_PROMPT_PREFIX = (
    "Do not assume the primary recommendation is correct. Find the "
    "strongest reasons it may be wrong. Identify missing evidence, hidden "
    "assumptions, downside, alternative explanations and better "
    "alternatives."
)


def blind_second_opinion(task_id: str, question: str, facts: str) -> dict:
    """Blind mode: the critic never receives the primary conclusion,
    ranking, draft or decision -- only `question` and `facts` (spec 25/40)."""
    prompt = (
        f"{REFUTE_PROMPT_PREFIX}\n\nQuestion: {question}\n\n"
        f"Known facts and context (no prior conclusion is included):\n{facts}\n\n"
        "Respond as DecisionCriticResult JSON."
    )
    envelope = TaskEnvelope(
        task_id=task_id, task_type="BLIND_SECOND_OPINION", provider="codex",
        mode="blind_independent", allowed_capabilities=["read_repository"],
        workspace_write=False, criticality="material",
        output_schema=str(DECISION_CRITIC_SCHEMA), prompt=prompt,
    )
    return CodexAdapter().run_task(envelope)


def adversarial_review(task_id: str, question: str, primary_conclusion: str, facts: str) -> dict:
    """Adversarial mode: critic receives the primary conclusion and must
    try to break it (spec 25)."""
    prompt = (
        f"{REFUTE_PROMPT_PREFIX}\n\nQuestion: {question}\n\n"
        f"Primary provider's conclusion (try to refute this):\n{primary_conclusion}\n\n"
        f"Facts and context:\n{facts}\n\nRespond as DecisionCriticResult JSON."
    )
    envelope = TaskEnvelope(
        task_id=task_id, task_type="DECISION_CRITIC", provider="codex",
        mode="adversarial", allowed_capabilities=["read_repository"],
        workspace_write=False, criticality="material",
        output_schema=str(DECISION_CRITIC_SCHEMA), prompt=prompt,
    )
    return CodexAdapter().run_task(envelope)


def critic_status_for_run(run_result: dict) -> str:
    """Never fabricates an approval when the critic could not run (spec 47:
    'Não criar aprovação fictícia')."""
    if run_result.get("exit_status") == "PROVIDER_UNAVAILABLE":
        return "CRITIC_UNAVAILABLE"
    if run_result.get("exit_status") != "OK":
        return "CRITIC_FAILED"
    return "CRITIC_COMPLETED"


def build_disagreement_review(
    *, question: str, primary_provider: str, primary_conclusion: str,
    second_provider: str, second_conclusion: str, common_facts: list,
    disputed_assumptions: list, missing_evidence: list,
    decision_impact: str, human_intervention_required: bool,
) -> dict:
    """Never resolves by vote -- this is a structured artifact for a human
    to read, not an auto-resolver (spec 26)."""
    return {
        "question": question,
        "primary_provider": primary_provider,
        "primary_conclusion": primary_conclusion,
        "second_provider": second_provider,
        "second_conclusion": second_conclusion,
        "common_facts": common_facts,
        "disputed_assumptions": disputed_assumptions,
        "disputed_forecasts": [],
        "missing_evidence": missing_evidence,
        "resolving_observation": "",
        "decision_impact": decision_impact,
        "human_intervention_required": human_intervention_required,
    }


def persist_disagreement(review: dict, review_id: str) -> Path:
    DISAGREEMENTS_DIR.mkdir(parents=True, exist_ok=True)
    p = DISAGREEMENTS_DIR / f"{review_id}.json"
    p.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def conclusions_diverge(primary_conclusion: str, second: dict) -> bool:
    """Very conservative divergence heuristic: only Codex's own explicit
    verdict decides divergence -- this function does not try to do NLP
    comparison of free text, which would be a false-precision trap (spec 13
    applied by analogy). Matches DecisionCriticResult's actual verdict enum
    in schemas/decision_critic_result.schema.json (SUPPORT/CHALLENGE/
    INSUFFICIENT_EVIDENCE)."""
    verdict = (second.get("output_parsed") or {}).get("verdict")
    return verdict in ("CHALLENGE", "INSUFFICIENT_EVIDENCE")

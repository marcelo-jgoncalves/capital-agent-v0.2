"""Provider-neutral task envelope.

Every reasoning/engineering task routed to any provider (Claude, Codex, a
future provider) is expressed as one of these envelopes before dispatch. It
is deliberately provider-agnostic: nothing here names Codex or Claude as a
policy authority, per prompt-integracao-codex-capital-agent.md section 36 and
the canonical invariant in adapters/ai_providers/README.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Task types are provider-neutral (section 35). Adding a provider must never
# require adding a new task type.
TASK_TYPES = frozenset({
    "TOPIC_DISCOVERY", "TOPIC_CRITIC", "CONTENT_BRIEF", "DRAFT",
    "EDITORIAL_CRITIC", "FACT_CHECK", "DECISION_CRITIC", "BLIND_SECOND_OPINION",
    "CODE_REVIEW", "ADVERSARIAL_TESTS", "POLICY_AUDIT", "POSTMORTEM_REVIEW",
    "SEO_REVIEW", "COMMERCIAL_OPPORTUNITY_DISCOVERY",
})

CRITICALITY_LEVELS = frozenset({"noncritical", "material", "critical"})

FORBIDDEN_CAPABILITIES = frozenset({
    "financial_write", "bank_credential", "brokerage_write", "exchange_write",
    "payment_token", "transfer_capital", "purchase", "sell", "pay",
    "move_capital",
})


class TaskEnvelopeError(ValueError):
    pass


@dataclass
class TaskEnvelope:
    task_id: str
    task_type: str
    provider: str = "auto"          # "codex" | "claude" | "auto"
    mode: str = "standard"          # "standard" | "blind_independent" | "adversarial"
    input_context_refs: list[str] = field(default_factory=list)
    allowed_capabilities: list[str] = field(default_factory=list)
    workspace_write: bool = False
    output_schema: str | None = None
    criticality: str = "noncritical"
    prompt: str = ""

    def validate(self) -> None:
        if self.task_type not in TASK_TYPES:
            raise TaskEnvelopeError(f"unknown task_type: {self.task_type}")
        if self.criticality not in CRITICALITY_LEVELS:
            raise TaskEnvelopeError(f"unknown criticality: {self.criticality}")
        bad = FORBIDDEN_CAPABILITIES.intersection(set(self.allowed_capabilities))
        if bad:
            raise TaskEnvelopeError(f"forbidden capabilities requested: {sorted(bad)}")
        if self.workspace_write and self.task_type not in {
            "CODE_REVIEW", "ADVERSARIAL_TESTS", "DRAFT",
        }:
            raise TaskEnvelopeError(
                f"task_type {self.task_type} may not request workspace_write"
            )

    def to_job_dict(self) -> dict:
        self.validate()
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "provider": self.provider,
            "mode": self.mode,
            "input_context_refs": list(self.input_context_refs),
            "allowed_capabilities": list(self.allowed_capabilities),
            "workspace_write": self.workspace_write,
            "output_schema_path": self.output_schema,
            "criticality": self.criticality,
            "prompt": self.prompt,
        }

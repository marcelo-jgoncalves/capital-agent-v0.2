"""AI Provider Adapter contract.

See adapters/ai_providers/README.md. An adapter dispatches a queued job
(from state/pending_jobs.json, produced by src/scheduler.py) to a reasoning
provider. It never executes a financial operation itself -- the custody
invariant in AI_OPERATING_MANUAL.md applies identically to every adapter.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class AIProviderAdapter(ABC):
    name: str = "unnamed"

    @abstractmethod
    def is_available(self) -> bool:
        """Cheap check: can this provider be invoked right now."""

    @abstractmethod
    def dispatch(self, job: dict) -> dict:
        """Hand a queued job to the provider.

        `job` is one entry from state/pending_jobs.json (has at least `id`,
        `job_key`, `kind`, `requires_ai_reasoning`, `context_hint`).

        Returns a result descriptor, e.g. {"status": "dispatched", ...}. Does
        not itself mark the job complete -- callers decide when to invoke
        `python src/scheduler.py complete-job` once the work is verified
        done, per AI_OPERATING_MANUAL.md's "never fabricate" principle.
        """

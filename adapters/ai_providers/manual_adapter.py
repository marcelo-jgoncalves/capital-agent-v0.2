"""Reference AI Provider Adapter: manual/human-launched dispatch.

Does not call any model API. Prints the job's context so a human can paste it
into whichever AI CLI session they launch (Claude Code, Codex, Gemini CLI, or
any other), pointed at START_HERE.md. This is the only adapter implemented
today -- see adapters/ai_providers/README.md for why an unattended
API-calling adapter is future work, not a current capability.
"""
from __future__ import annotations

from .base import AIProviderAdapter


class ManualAdapter(AIProviderAdapter):
    name = "manual"

    def is_available(self) -> bool:
        return True

    def dispatch(self, job: dict) -> dict:
        print("=== Capital Agent job ready for an AI operator ===")
        print(f"Job ID: {job.get('id')}")
        print(f"Job key: {job.get('job_key')}")
        print(f"Context: {job.get('context_hint')}")
        print("Start any AI CLI session with: "
              "'Read START_HERE.md and assume operation of the Capital Agent, "
              f"then work job {job.get('id')}.'")
        print(f"When done: python src/scheduler.py complete-job --id {job.get('id')} --summary \"...\"")
        return {"status": "printed_for_manual_dispatch", "job_id": job.get("id")}

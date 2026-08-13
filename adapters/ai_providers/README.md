# AI Provider Adapters

The Capital Agent is the repository plus its state, policies, context,
scheduler, governance, evaluation, history and code — not any particular
model. The reasoning/execution environment is a pluggable adapter:

```text
Capital Agent
    |
    v
AI Provider Adapter (base.py contract)
    |
    v
Claude Code / Codex / Gemini CLI / a local model / a future provider
```

`scheduler/` enqueues job tickets in `state/pending_jobs.json` without caring
who works them. An AI Provider Adapter is how a specific operator (a CLI tool,
an API-driven agent loop, a human running an interactive session) is wired up
to actually pick up and work those tickets — the scheduler and the rest of the
repository never call a vendor SDK directly.

## Contract (`base.py`)

```python
class AIProviderAdapter:
    name: str

    def is_available(self) -> bool:
        """Cheap check: can this provider be invoked right now."""

    def dispatch(self, job: dict) -> dict:
        """Hand a queued job (from state/pending_jobs.json) to the provider.
        Returns a result descriptor; does not itself call
        `src/scheduler.py complete-job` — the caller decides when a job is
        truly done."""
```

## Reference implementation: `manual_adapter.py`

The only adapter implemented today. It does not call any model API — it
prints the job's context so a human-launched AI CLI session (Claude Code,
Codex, Gemini CLI, or any other) can pick it up interactively, following
`START_HERE.md`. This is deliberately honest about the current phase: this
repository does not (yet) drive an unattended API-based agent loop, and
claiming otherwise would violate the "never fabricate capability" principle
in `AI_OPERATING_MANUAL.md`.

A future adapter that does call a provider API directly (for a truly
unattended loop) is welcome as a Class A/B system change per
`SYSTEM_EVOLUTION.md` — it would only ever expand *reasoning* dispatch, never
financial authority; the custody invariant applies identically regardless of
which adapter is active.

## Second reference implementation: `codex_adapter.py`

Calls the local Codex CLI (`codex exec`) non-interactively — the first
programmatic (non-manual) provider adapter in this repository. See
`MULTI_PROVIDER_REASONING.md` for the full architecture,
`SECOND_OPINION_POLICY.md` for when it is used as a critic,
`EDITORIAL_RESEARCH_SYSTEM.md` for blind topic discovery, and
`integrations/codex/README.md` for setup/troubleshooting. It never touches
Codex's own auth storage, defaults to read-only sandbox, and records every
run to `state/ai_runs/`. `adapters/ai_providers/task_envelope.py` is the
provider-neutral request format both `manual_adapter.py`-style dispatch and
`codex_adapter.py` are meant to converge on over time.

## Rules

1. An adapter's job is to invoke reasoning, never to execute a financial
   operation — the custody invariant applies uniformly to every adapter.
2. Canonical documents refer to "the AI operator" or "the reasoning
   provider," never to a specific vendor; only adapter code/docs may name one.
3. No adapter may weaken policy, skip criticality classification, or bypass
   `execution/human_requests/` — an adapter is a dispatch mechanism, not a
   policy engine.
4. Switching adapters must never require rewriting canonical documents —
   only adding or swapping a file under this directory.

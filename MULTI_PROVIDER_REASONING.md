# Multi-Provider Reasoning

The Capital Agent is the repository plus its state, policies, context,
scheduler, governance, evaluation and history — not any particular model.
Reasoning is dispatched to a pluggable **reasoning provider**. Today two are
wired: **Claude** (primary, currently interactive/manual, see
`adapters/ai_providers/manual_adapter.py`) and **Codex CLI** (secondary,
programmatic via `adapters/ai_providers/codex_adapter.py`). Neither is the
system's source of truth or policy authority; the repository is.

```text
THE CAPITAL AGENT IS THE SYSTEM.
CLAUDE IS A REASONING PROVIDER.
CODEX IS A REASONING / ENGINEERING PROVIDER.
NEITHER PROVIDER IS THE SOURCE OF TRUTH.
```

## Architecture

```text
CAPITAL AGENT
      |
ORCHESTRATOR (src/scheduler.py — deterministic, never calls a model)
      |
REASONING ROUTER (src/reasoning_router.py)
      |
  +---+---+
  |       |
CLAUDE   CODEX
(manual) (adapters/ai_providers/codex_adapter.py)
  |       |
  +---+---+
      |
AI RUN LOG (state/ai_runs/ — audit trail, no secrets)
```

## Task envelope

Every reasoning/engineering task is expressed as a `TaskEnvelope`
(`adapters/ai_providers/task_envelope.py`) before dispatch: `task_id`,
`task_type` (one of `config/task_types.json`'s provider-neutral list),
`provider` (`codex` | `claude` | `auto`), `mode` (`standard` |
`blind_independent` | `adversarial`), `allowed_capabilities`,
`workspace_write`, `output_schema`, `criticality`. `TaskEnvelope.validate()`
is the single choke point that makes financial-write capabilities and
self-escalated permissions structurally unreachable — see its
`FORBIDDEN_CAPABILITIES` set and the workspace-write allow-list.

## Codex adapter

`adapters/ai_providers/codex_cli.py` shells out to the local `codex`
executable only (`codex --version`, `codex exec --sandbox ... <prompt>`).
It never reads, copies or exports `~/.codex/` or any credential store — see
`integrations/codex/README.md`. `adapters/ai_providers/codex_adapter.py`
wraps that in the `AIProviderAdapter` contract plus a `run_task()` entry
point that validates the envelope, healthchecks Codex, runs it in
`read-only` sandbox by default (`workspace-write` only when the envelope
explicitly asks and the task type allows it), parses structured output
defensively, and records every run to `state/ai_runs/` via
`adapters/ai_providers/ai_run_log.py` (secrets are scrubbed by key-name
pattern as defense in depth).

## Structured output

When Codex output is consumed by code, a JSON Schema file under `schemas/`
is passed via `codex exec --output-schema <file>` (confirmed present in
`codex exec --help`, codex-cli 0.147.0). If the CLI in use does not support
that flag, or output does not parse, the adapter marks the run
`SCHEMA_MISMATCH` rather than guessing — never fabricated.

## Reasoning Router

`src/reasoning_router.py` resolves `provider="auto"` to a concrete provider
using explicit, evolvable rules (`resolve_provider`), exposes the **Second
Model Value Policy** (`second_opinion_policy()`: `REQUIRED_WHEN_AVAILABLE` /
`RECOMMENDED` / `OPTIONAL` / `AVOID` per task type), and raises
`ProviderUnavailable` rather than silently falling back — callers apply
fallback policy explicitly (see "Fallback" below).

## Fallback

If Codex is unavailable or fails, the Capital Agent continues functioning.
`run_task()` returns `exit_status = "PROVIDER_UNAVAILABLE" | "FAILED" |
"TIMEOUT" | "SCHEMA_MISMATCH"` and never invents a result. For a task where
a critic was required, the status is surfaced as `CRITIC_UNAVAILABLE` (see
`SECOND_OPINION_POLICY.md`) — never a fabricated approval.

## What this does NOT change

- Custody: only the human owner accesses, custodies or moves real money —
  identical for every provider (`AI_OPERATING_MANUAL.md`).
- `START_HERE.md` remains the universal entry point.
- `AGENTS.md` remains a thin adapter, not a policy document.
- No new financial write path, paid API, or unrestricted network/filesystem
  access was introduced.
- Codex is never mandatory: every capability it adds is additive to what
  Claude/the manual adapter already does.

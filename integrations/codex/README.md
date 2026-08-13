# Codex CLI Integration Setup

Provider-specific setup notes. Canonical policy lives in the documents
referenced from `START_HERE.md` — this file explains only how to make the
Codex adapter usable, and duplicates no policy.

## Requirements

- Codex CLI installed and on `PATH` (verified here: codex-cli 0.147.0, npm
  global install).
- The human owner runs `codex login` **outside this repository's control** —
  this repository never automates login, never reads `~/.codex/`, and never
  asks for a token to be pasted anywhere in the repo.
- ChatGPT Plus OAuth login is sufficient; no API key or billing account is
  required for this integration to work (`codex exec` uses the logged-in
  session, not a separate paid API).

## Healthcheck

```powershell
codex --version
codex exec --help
```

Programmatically: `adapters/ai_providers/codex_cli.healthcheck()`, which
runs exactly those two read-only introspection commands and nothing else —
no network call, no auth-file access.

## Read-only smoke test

```powershell
codex exec --sandbox read-only --skip-git-repo-check "Reply with exactly one line: OK CAPITAL AGENT CODEX SMOKE TEST"
```

This was run for real during the integration task (see the readiness
report / `SYSTEM_EVOLUTION.md` entry for the captured output) and returned
`OK CAPITAL AGENT CODEX SMOKE TEST` with a normal exit.

## How the adapter invokes Codex

Only ever: `codex exec --sandbox {read-only|workspace-write}
--skip-git-repo-check [--output-schema <file>] "<prompt>"`, run as a plain
subprocess with no shell interpolation
(`adapters/ai_providers/codex_cli.py:run_codex_exec`). `danger-full-access`
is not a reachable value anywhere in this codebase.

## Disabling the integration

Codex is never required for the Capital Agent to function (see
`MULTI_PROVIDER_REASONING.md` "What this does NOT change"). To disable it:

- do nothing (if `codex` is not on `PATH` or not logged in, every
  `CodexAdapter` call resolves to `PROVIDER_UNAVAILABLE` and callers fall
  back per `SECOND_OPINION_POLICY.md`);
- or explicitly avoid routing tasks with `provider="codex"` /
  `provider="auto"` where Codex would be selected
  (`src/reasoning_router.py`).

There is no config flag that forces Codex to be used when unavailable, and
none that upgrades its sandbox to full access.

## Troubleshooting

| Symptom | Meaning |
|---|---|
| `healthcheck().available == False`, error "codex executable not found on PATH" | `codex` is not installed or not on PATH for the process running the scheduler/adapter. |
| `exit_status == "PROVIDER_UNAVAILABLE"` on every call | Same as above, or `codex --version` failed. |
| `exit_status == "FAILED"` | Non-zero exit from `codex exec`; see `errors` in the run record for truncated stderr, and `state/ai_runs/<run_id>.json` for the full audit entry. |
| `exit_status == "TIMEOUT"` | The call exceeded its timeout (default 120s); raise `timeout=` on the call site if the task is legitimately long-running. |
| `exit_status == "SCHEMA_MISMATCH"` | Codex responded but the output did not parse as JSON against the requested schema; treat as `CRITIC_UNAVAILABLE`/`FAILED` for policy purposes, never as silently-accepted output. |

## Permission policy

Read-only sandbox is the default for every task type except
`CODE_REVIEW`/`ADVERSARIAL_TESTS`/`DRAFT` explicitly requesting
`workspace_write=True` (enforced in
`adapters/ai_providers/task_envelope.py:TaskEnvelope.validate()`, not by
convention). No task envelope can request `danger-full-access`, unrestricted
network, or any financial-write capability — see `FORBIDDEN_CAPABILITIES` in
the same file.

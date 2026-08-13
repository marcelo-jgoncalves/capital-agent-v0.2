# Codex Provider Integration — Readiness Report

Date: 2026-08-13
Source prompt: `journal/reviews/source-prompts/prompt-integracao-codex-capital-agent.md`
Branch: `feat/codex-provider-integration`

## 1. Architecture implemented

```text
CAPITAL AGENT (repository = source of truth)
      |
ORCHESTRATOR (src/scheduler.py, deterministic, unchanged)
      |
REASONING ROUTER (src/reasoning_router.py)
      |
  +---+---+
  |       |
CLAUDE   CODEX
(manual, (adapters/ai_providers/codex_adapter.py +
 unchanged) codex_cli.py, via TaskEnvelope)
  |       |
  +---+---+
      |
STRUCTURED OUTPUT (schemas/*.json) + AI RUN LOG (state/ai_runs/)
```

Neither provider is policy authority; canonical docs
(`AI_OPERATING_MANUAL.md`, `HUMAN_GATES.md`, `CRITICAL_DECISIONS.md`,
`SYSTEM_EVOLUTION.md`) are unchanged and unaffected.

## 2. Files created

- `adapters/ai_providers/task_envelope.py` — provider-neutral task envelope,
  forbidden-capability and permission validation.
- `adapters/ai_providers/codex_cli.py` — thin, defensive `codex` subprocess
  wrapper (healthcheck, `run_codex_exec`).
- `adapters/ai_providers/codex_adapter.py` — `CodexAdapter` (`AIProviderAdapter`
  contract + `run_task()`).
- `adapters/ai_providers/ai_run_log.py` — audit trail persistence, secret
  scrubbing.
- `src/reasoning_router.py` — provider resolution + Second Model Value
  Policy (`second_opinion_policy()`).
- `src/editorial_research.py` — `ResearchBrief`, blind prompt builder,
  candidate save/merge/dedupe, scoring.
- `src/critic.py` — blind second opinion, adversarial review, disagreement
  protocol, `CRITIC_UNAVAILABLE` fallback.
- `src/engineering_review.py` — code review / adversarial tests / policy
  audit job builders.
- `src/provider_registry.py` — provider performance registry (counters,
  not composite scoring).
- `evaluation/provider_performance.py` — event-log based performance
  aggregation (mean per metric, no invented causality).
- `schemas/*.schema.json` (6 files) — TopicDiscoveryResult,
  EditorialCriticResult, DecisionCriticResult, DisagreementReview,
  CodeReviewResult, ProviderRunResult.
- `config/task_types.json` — provider-neutral task type registry +
  Second Model Value Policy tiers.
- `MULTI_PROVIDER_REASONING.md`, `SECOND_OPINION_POLICY.md`,
  `EDITORIAL_RESEARCH_SYSTEM.md`, `integrations/codex/README.md`.
- `tests/test_codex_provider_integration.py`.
- `journal/system_changes/SYS-20260813-CODEX.md`, this readiness report.

## 3. Files modified

- `config/schedules.json` — added `editorial_topic_discovery_blind`
  (weekly), `editorial_cluster_review` and `provider_performance_review`
  (monthly) job names; frequencies/mechanism unchanged.

## 4. Files moved

- `prompt-integracao-codex-capital-agent.md` ->
  `journal/reviews/source-prompts/prompt-integracao-codex-capital-agent.md`.

## 5. Provider abstraction

`AIProviderAdapter` (`adapters/ai_providers/base.py`, pre-existing) is
unchanged. `CodexAdapter` implements it plus a richer `run_task(TaskEnvelope)`
entry point used by the router, editorial research, critic and engineering
review modules. `TaskEnvelope.validate()` is the single choke point making
financial-write capabilities and workspace-write on research task types
structurally unreachable — not merely documented.

## 6. Codex detection result

`codex` found on PATH. `codex --version` -> **codex-cli 0.147.0**.
`codex exec --help` confirms `--output-schema <FILE>` is present (structured
output natively supported) and `--sandbox {read-only|workspace-write|
danger-full-access}` (only the first two are ever reachable from this
codebase). Top-level `codex --help` shows `--search`, but `codex exec --help`
does **not** list `--search` — web search is therefore not confirmed
reachable through the non-interactive `exec` path on this CLI version. This
is documented as a real, verified limitation in
`integrations/codex/README.md`, not silently assumed either way.

## 7. Non-interactive invocation test (real, not simulated)

```text
$ codex exec --sandbox read-only --skip-git-repo-check "Respond with exactly: codex adapter smoke test ok"
OpenAI Codex v0.147.0
workdir: C:\Users\Usuario\Desktop\projects\capital-agent-v0.2
model: gpt-5.6-sol   provider: openai   approval: never   sandbox: read-only
codex
codex adapter smoke test ok
tokens used: 2717
```
Wall time ~5.7s. Confirms the exact invocation shape used by
`codex_cli.run_codex_exec()` works end-to-end with the real, already
ChatGPT-OAuth-authenticated local installation.

## 8. Read-only research test

Confirmed by the smoke test above (`--sandbox read-only`) and by
`test_full_access_is_not_default_sandbox` / `test_research_defaults_read_only`
equivalents in `tests/test_codex_provider_integration.py`.

## 9. Structured output test

`codex exec --output-schema` flag is present in this CLI version, so the
adapter uses it when a `TaskEnvelope.output_schema` is set. Defensive
parsing (`json.loads`, mismatch -> `SCHEMA_MISMATCH`, never a crash or a
fabricated object) is implemented and covered by
`test_malformed_structured_output_fails_safely`. A live end-to-end run with
`--output-schema` against a real schema file was not executed as part of
this task (out of scope: no live editorial/critic task was run for real,
per section 58 "não iniciar EXP-001" and to keep this a structure-building
pass) — the defensive-parsing path itself was exercised only against
mocked/malformed output in unit tests, not against a real `--output-schema`
Codex response. **Known limitation**, not fabricated as tested.

## 10. Blind topic discovery test

`build_blind_prompt()` structurally cannot receive another provider's
output (no such parameter exists). Covered by unit tests asserting the
blind critic call payload contains only `question`/`facts`.

## 11. Provenance test

`merge_and_dedupe()` preserves `origins` per merged candidate; covered by a
unit test asserting a lexically-duplicate candidate from both origins keeps
both, and a distinct candidate keeps only its true origin.

## 12. Fallback test

`CodexAdapter.run_task()` returns `PROVIDER_UNAVAILABLE` (not a fabricated
success) when `codex` is not on PATH, `FAILED` on non-zero exit,
`SCHEMA_MISMATCH` on malformed structured output. `critic.critic_status_for_run()`
never returns anything resembling approval when the critic could not run —
covered by unit tests.

## 13. Critic integration test

`src/critic.py` blind/adversarial modes, `CRITIC_UNAVAILABLE` marking, and
disagreement-not-by-vote are covered by unit tests in
`tests/test_codex_provider_integration.py::TestCritic`.

## 14. Security test / findings

Manual grep pass performed (no live Codex-run security audit executed, per
section 58/30 "não realizar exploração destrutiva externa" and to keep
scope to structure-building):

- No `shell=True` anywhere in `adapters/` or `src/`; `codex_cli.py` always
  calls `subprocess.run` with a list argument (no shell interpolation of
  the prompt string).
- No hardcoded `api_key=`/`password=`/`secret=` literal assignments found
  in the new adapter/router/editorial/critic modules.
- `ai_run_log.py` scrubs any dict key matching
  `token|secret|password|credential|api_key|auth` before writing to
  `state/ai_runs/` (defense in depth beyond just "don't pass secrets in").
- `danger-full-access` appears only in comments/docstrings explaining it is
  never used; `codex_cli.ALLOWED_SANDBOX_MODES` only contains `read-only`
  and `workspace-write`, and `run_codex_exec` raises `ValueError` for any
  other value.
- `TaskEnvelope.validate()` rejects `financial_write`, `bank_credential`,
  `brokerage_write`, `exchange_write`, `payment_token`, `transfer_capital`,
  `purchase`, `sell`, `pay`, `move_capital` in `allowed_capabilities`
  unconditionally.
- No code path under `adapters/ai_providers/` or the new `src/` modules
  writes to `approvals/`, `execution/human_requests/`, or `data/ledger.csv`.

No findings requiring remediation before merge. A full adversarial security
review by Codex itself (spec section 30, `ADVERSARIAL_TESTS`/`POLICY_AUDIT`
task types) was not run live in this pass — the *capability* to run one now
exists (`src/engineering_review.py`), but exercising it is future work, not
claimed as done here.

## 15. Full test suite result

`python -m unittest discover -s tests`: **95 tests, 0 failures, 0 errors,
OK** (pre-existing 64 tests + 31 new Codex-integration tests in
`tests/test_codex_provider_integration.py`).

## 16. Known limitations

- Claude has no programmatic adapter in this repository (unchanged from
  before this task) — `src/reasoning_router.py:run()`/`resolve_provider()`
  only executes Codex programmatically; Claude remains the interactive
  primary operator via `manual_adapter.py`. This was true before this
  integration and is not a regression.
- Web search on `codex exec` is not confirmed reachable on this CLI version
  (see section 6/9) — editorial research using live web search cannot be
  automated non-interactively today; it would need a future Codex CLI
  version or the interactive `codex --search` path.
- No live end-to-end run with a real `--output-schema` file was performed;
  structured-output parsing is verified only against mocked Codex output.
- Editorial research, critic and engineering-review modules are exercised
  only with synthetic/mocked provider output in tests — no real editorial
  topic-discovery run, no real critic run against a real decision, and no
  real Codex code-review run were performed, consistent with "não iniciar
  EXP-001" / "não gastar capital" / keeping this pass structure-only.
- `src/provider_registry.py` and `evaluation/provider_performance.py`
  currently overlap in purpose (both a "provider performance registry",
  one JSON-file-based under `state/`, one JSONL-event-log under
  `evaluation/`). Both pass their own tests and neither is wired to the
  other; a future pass should consolidate to one, or explicitly document
  why two exist (e.g., one per-provider snapshot, one raw event log).

## 17. Next steps

1. Consolidate `src/provider_registry.py` and
   `evaluation/provider_performance.py` into one registry or document the
   split intentionally.
2. Run a real `TOPIC_DISCOVERY` blind pass (Claude interactive + Codex via
   adapter) against a real `ResearchBrief` once EXP-001 content work is
   actually authorized — not before.
3. Run `src/engineering_review.py:code_review()` against a real diff as the
   first live use of Codex-as-critic, in read-only mode, on a small,
   reversible change.
4. Re-check `codex exec --help` after any Codex CLI upgrade — this report's
   flag/capability claims are only valid for codex-cli 0.147.0.

## 18. Final readiness verdict

**READY (structure) / NOT_READY (live operation)** — matching intent:

- The Codex provider abstraction, adapter, healthcheck, task envelope,
  structured-output schemas, reasoning router, editorial research
  structure, critic/disagreement protocol, engineering-review job builders,
  scheduler wiring, and provider performance registry all exist, are
  tested (95/95 passing), and were verified against the real, installed,
  already-authenticated Codex CLI (0.147.0) with a real non-interactive
  invocation.
- **NOT_READY for any live editorial, critic, or code-review run against
  real content or real decisions** — none was performed in this task, by
  design (section 58: no EXP-001 start, no capital spent, no publication).
  That is the correct and expected state for a structure-building
  integration pass, not a defect.
- **NOT_READY for Codex-mediated web research** on this CLI version — the
  `--search` flag is not confirmed reachable from `codex exec` (see
  section 6/9/16). Treat any near-term editorial research as
  evidence-from-repository-only until this is re-verified on a future CLI
  version.

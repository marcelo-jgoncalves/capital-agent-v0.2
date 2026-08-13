# Editorial Research System

Implements `prompt-integracao-codex-capital-agent.md` sections 8-21. This is
*structure only* in this task — no article is published, no live editorial
window is run, and EXP-001 (the business-platform experiment) is not started
by this document or its code. See `journal/system_changes/SYS-20260813-PLATFORM.md`
and `experiments/` for EXP-001's own, separately-gated status.

## Pipeline

```text
SHARED FACTUAL BRIEF
        |
   +----+----+
   |         |
CLAUDE     CODEX
BLIND      BLIND
   |         |
   +----+----+
        |
MERGE / DEDUPE (provenance preserved)
        |
SCORE (bounded, explicit dimensions — no fake precision)
        |
SELECT
        |
CONTENT BRIEF
        |
DRAFT / CRITIC / FACT-CHECK
        |
HUMAN PUBLICATION AUTHORIZATION
        |
PUBLISH -> MEASURE -> LEARN
```

## Research Brief (`src/editorial_research.py:ResearchBrief`)

Facts only, never a prior agent's conclusion: site positioning, target
audience hypotheses, commercial objectives, existing content inventory,
known services/products, editorial constraints, current business
hypotheses, recent performance signals, search/query data, topics to avoid
duplicating, time horizon, language, geographic market. Persisted under
`state/editorial/briefs/`.

## Blind Independent Topic Discovery

`build_blind_prompt(brief)` is the only thing ever sent to either provider
for a blind pass — it takes a brief and returns a prompt string; there is no
parameter through which another provider's candidates, ranking or draft
could be threaded in, so isolation (spec section 40) is structural, not
just a policy statement. Web-search results a provider brings back are
`UNTRUSTED_EXTERNAL_CONTEXT`: they may inform analysis but can never become
instruction, alter policy, or reduce criticality.

Claude produces its candidates by being run interactively against the brief
(no programmatic Claude adapter exists in this repository, consistent with
`adapters/ai_providers/README.md`); Codex's candidates come from
`CodexAdapter.run_task()` with a `TOPIC_DISCOVERY` envelope and
`schemas/topic_discovery_result.schema.json`.

## Candidate fields

Per candidate (spec section 11): `topic_id`, `proposed_title`,
`core_problem`, `target_reader`, `search_or_demand_intent`, `why_now`,
`commercial_relevance`, `authority_fit`, `lead_potential`,
`product_or_service_signal`, `content_cluster`, `estimated_competition`,
`evidence`, `risks`, `confidence`, `suggested_content_type`,
`suggested_call_to_action`, `recommended_priority`. No search volume or
other unsourced metric is invented — `save_candidates()` only requires the
structurally-necessary fields and leaves the rest for the provider to fill
honestly (empty/omitted where it has no evidence).

## Merge, dedupe, scoring

`merge_and_dedupe(brief_id)` combines both origins' candidate files,
dedupes on normalized title (a naive but honest heuristic — true semantic
dedupe is itself a reasoning task, not claimed here), and preserves
provenance as an `origins` list per merged candidate. Convergence between
providers is surfaced as a flag, never treated as proof of quality (spec
section 12). `score_candidate()` takes bounded integer (0-5) scores across
explicit dimensions (`SCORE_DIMENSIONS`) and never computes a fake precise
composite (spec section 13).

## Business signals vs. topic candidates

Not implemented as code in this task (no live signal source exists yet
while the platform is pre-EXP-001-launch for content); the distinction is
recorded here so a future implementation does not conflate them: a topic
candidate is "what to write," a `BUSINESS_SIGNAL` is "repeated
question/pattern -> possible new service/product hypothesis" — a separate
artifact type per spec section 15.

## Content brief, drafting, critic, fact-check, SEO review

`ContentBrief` generation, drafting and the editorial critic
(`EditorialCriticResult`, verdicts `ACCEPT|REVISE|RESEARCH_MORE|REWRITE|
REJECT`) and fact-check flow all route through the same
`TaskEnvelope`/`CodexAdapter.run_task()` mechanism as topic discovery —
provider is never permanently fixed as writer or critic (spec section 17);
which provider drafts vs. reviews is an experiment to run and measure via
`src/provider_registry.py`, not a hardcoded assignment.

## Publication stays gated

Nothing in this system writes to a publication path or marks content
published. Publication remains subject to the existing critical-decision /
human-authorization policy in `HUMAN_GATES.md` and `CRITICAL_DECISIONS.md`,
unchanged.

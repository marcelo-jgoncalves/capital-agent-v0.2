# Second Opinion / Critic Policy

Implements `prompt-integracao-codex-capital-agent.md` sections 24-26 and 34.
Provider-neutral: "second provider" here means whichever reasoning provider
is not the one that produced the primary analysis — today that is usually
Codex reviewing Claude's work, but the policy does not name a fixed pair.

## When a second opinion is required, recommended, optional, or should be avoided

See `src/reasoning_router.py:second_opinion_policy()`:

- **REQUIRED when available**: `DECISION_CRITIC`, `BLIND_SECOND_OPINION`
  (critical decisions, governance/risk-policy changes, major architecture
  changes, high-impact post-mortems, final readiness audits — per
  `CRITICAL_DECISIONS.md` / `HUMAN_GATES.md`, which remain the authority on
  what counts as critical).
- **RECOMMENDED**: `TOPIC_DISCOVERY`, `FACT_CHECK`, `POLICY_AUDIT`,
  `POSTMORTEM_REVIEW`.
- **OPTIONAL**: `CONTENT_BRIEF`, `DRAFT`, `EDITORIAL_CRITIC`, `CODE_REVIEW`.
- **AVOID**: deterministic jobs, trivial formatting, arithmetic — the
  scheduler (`src/scheduler.py`) never calls an AI for these in the first
  place.

"Required when available" never means "required, full stop": if Codex is
unavailable, the run is marked `CRITIC_UNAVAILABLE` (see `src/critic.py:
critic_status_for_run`) and the decision proceeds through the existing
human-authorization path in `HUMAN_GATES.md` / `CRITICAL_DECISIONS.md` —
Codex's absence never blocks the Capital Agent, and its absence never
becomes a fabricated approval.

## Two review modes (`src/critic.py`)

- **Blind second opinion** (`blind_second_opinion()`): the critic receives
  only `question` + `facts`, never the primary conclusion, ranking, draft or
  decision. Use when anchoring is a material risk.
- **Adversarial review** (`adversarial_review()`): the critic receives the
  primary conclusion and must try to break it. Both modes use the same
  refutation instruction:

  > Do not assume the primary recommendation is correct. Find the strongest
  > reasons it may be wrong. Identify missing evidence, hidden assumptions,
  > downside, alternative explanations and better alternatives.

## Disagreement protocol

Material divergence produces a `DisagreementReview` artifact
(`schemas/disagreement_review.schema.json`, built by
`critic.build_disagreement_review()` and persisted under
`state/critic/disagreements/`) containing the question, both conclusions,
common facts, disputed assumptions/forecasts, missing evidence, and whether
human intervention is required. **Disagreement is never resolved by
majority vote or automatically** — there is no vote-counting function
anywhere in `src/critic.py`; a human reads the artifact.

## Interaction with human gates

This policy only decides when a *second AI opinion* is sought before a
recommendation reaches a human. It does not add, remove, or weaken any
`HUMAN_GATES.md` / `CRITICAL_DECISIONS.md` approval requirement, and it
cannot: no code path in `src/critic.py` or `adapters/ai_providers/` writes
to `approvals/` or marks a critical decision approved.

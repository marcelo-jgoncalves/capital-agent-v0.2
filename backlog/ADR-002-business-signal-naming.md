# ADR-002: BusinessSignal / BusinessObservation / OpportunityCandidate naming

Status: **PARTIALLY RESOLVED -- migration plan for the remainder, decision pending**
Author: AI operator (hardening pass, prompt-hardening-final-capital-agent-v0.2.md section 8)
Date: 2026-08-13

## Context

The prompt's preferred pipeline shape:

```text
ExternalBusinessObservation
        |
        v
   BusinessSignal
        |
        v
OpportunityCandidate
```

## Current state (already implemented, prior to this session)

`EXTERNAL_INTEGRATION.md` section 4 already documents and
`src/business_integration.py` already implements the first two layers as
genuinely distinct entities, per the `f2a3072` / prior hardening work
referenced there:

- `create_business_observation()` / `BusinessObservation`
  (`state/business_observations/`) -- "one raw external fact with no
  confidence/intensity scoring of its own." This is the
  `ExternalBusinessObservation` layer; the class/schema is named
  `business_observation` rather than `external_business_observation`, but
  the concept and separation from `BusinessSignal` are exactly the intended
  ones, and the name is not ambiguous with anything else in this codebase.
- `create_business_signal_entity()` / `BUSINESS_SIGNAL`
  (`state/business_signals/`) -- "the higher-level pattern claim, carrying
  confidence/intensity, that a human or AI derives FROM one or more
  BusinessObservation records," explicitly linked via
  `derived_from_observation_ids`. This is exactly the `BusinessSignal`
  layer. `ingest_business_signal()` is a separate, older function (the
  "External Business Data Adapter" raw-ingestion path, predates the
  observation/signal split) and is intentionally NOT the same thing as
  `create_business_signal_entity()`; see note below.
- `create_business_signal_entity(signal_type="topic_candidate", ...)`
  explicitly raises `BusinessSignalError` -- a topic candidate (editorial
  "what to write about") can never be conflated with a BUSINESS_SIGNAL
  (commercial pattern/demand evidence). This guard already prevents the
  exact ambiguity this ADR is about.

**What is NOT yet a first-class entity:** `OpportunityCandidate`.
`promote_business_signal_to_opportunity()` only records an opaque
`opportunity_candidate_ref: str` (a caller-supplied reference/ID) on the
promoted `BUSINESS_SIGNAL`, plus a `rationale`. There is no
`OpportunityCandidate` schema, no `state/opportunity_candidates/`
directory, no `create_opportunity_candidate()` function -- the "hypothesis
that merece avaliação econômica" is currently represented only as a
free-form reference string a caller is expected to resolve elsewhere (e.g.
a `journal/decisions/` entry).

## Remaining ambiguity / naming debt

1. `ingest_business_signal()` (the older External Business Data Adapter
   ingestion path, `state/business_signals/` -- yes, the SAME directory as
   `create_business_signal_entity()`) predates and is conceptually closer
   to a raw signal ingestion function than to the `BUSINESS_SIGNAL` pattern
   entity `create_business_signal_entity()` produces. Both write into
   `BUSINESS_SIGNALS_DIR`, but they are different shapes for different
   purposes (one is metric-observation-shaped telemetry ingestion with
   idempotency on `(source_system, source_record_id, metric_name,
   measurement_period)`; the other is the confidence/intensity pattern
   claim keyed on evidence + derivation). Sharing a directory and a
   `..._signal...` name prefix between two distinct shapes is a real,
   if minor, naming collision risk for a future maintainer.
2. `OpportunityCandidate` does not exist as a schema/entity at all yet.

## Migration plan for the remainder (not implemented this session)

**Item 1 (`ingest_business_signal` vs. `create_business_signal_entity`
naming collision):** low risk to rename
`ingest_business_signal`/`BUSINESS_SIGNALS_DIR` usage sites to make the
raw-telemetry-ingestion function's name and directory distinct from the
pattern-entity's (e.g. keep `BUSINESS_SIGNALS_DIR` for
`create_business_signal_entity()`'s canonical `BUSINESS_SIGNAL` records, and
either rename `ingest_business_signal()` to something like
`ingest_raw_business_metric()` or move its output to a
`state/business_metric_ingestions/` directory). This is a Class A/B
refactor (renaming + directory move, no behavior change, no financial
authority change) but touches many call sites
(`src/scheduler.py`, `src/editorial_research.py` references,
`tests/test_business_integration.py`, `tests/test_scheduler_triggers.py`)
and at least one schema filename
(`schemas/business_signal.schema.json` is currently shared/ambiguous
between the two). **Not implemented in this session** to avoid a
wide-blast-radius rename under a hardening pass whose primary mandate is
P0/P1 financial-integrity fixes -- the risk of introducing a regression via
an incomplete rename outweighs the (real but purely cosmetic) naming-debt
benefit right now.

**Item 2 (`OpportunityCandidate` entity):** requires an actual product/
domain decision (what fields does an opportunity candidate need beyond a
reference string? capital required, maximum plausible loss, evidence
quality, time-to-feedback -- the dimensions already used in
`ARCHITECTURE.md`'s "Evaluation & Critic subsystem" comparison criteria?
Does it get its own schema/state directory, or does it stay folded into
`journal/decisions/`, which already serves a similar purpose for material
capital decisions?). This is a schema-design decision with migration
implications (existing `opportunity_candidate_ref` values would need to
either stay as opaque refs into `journal/decisions/`, or be backfilled into
a new entity type) and is deliberately left as an **open, pending decision**
rather than invented unilaterally in this session.

## Recommendation

- Treat the `ExternalBusinessObservation -> BusinessSignal` boundary as
  **already resolved** by the existing `BusinessObservation` /
  `BUSINESS_SIGNAL` split and the `topic_candidate` guard -- no further
  action needed there.
- File Item 1 (naming-collision cleanup) as **low-priority backlog**,
  scoped to a dedicated PR/session so its full call-site surface can be
  reviewed and tested in isolation.
- File Item 2 (`OpportunityCandidate` as a first-class entity) as
  **pending owner decision** -- do not invent the schema shape
  unilaterally; when/if the owner wants opportunity candidates tracked as
  their own entity (rather than via `journal/decisions/` +
  `opportunity_candidate_ref`), scope it as its own Class B change with a
  proper schema, migration of existing `opportunity_candidate_ref` values,
  and dedicated tests.

No code changes were made in this session for section 8 beyond this
documentation, per "if it requires bigger migration or a domain decision,
document it rather than invent it."

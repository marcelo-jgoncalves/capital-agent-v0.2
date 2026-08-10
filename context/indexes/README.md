# Indexes

Portable JSON indexes for fast lookup. These are a derived cache, not a source of
truth — the canonical record always lives under `journal/`, `experiments/`,
`approvals/`, `execution/` or `data/ledger.csv`. If an index and its source disagree, the source
wins; regenerate or fix the index.

- `decisions.json` — one entry per record created by `capital_agent.py propose`.
- `experiments.json` — one entry per record created by `capital_agent.py new-experiment`.
- `system-changes.json` — one entry per record created by `capital_agent.py propose-system-change`.
- `approvals.json` — one entry per record created by `capital_agent.py request-approval`.
- `execution_requests.json` — one entry per state transition of a Human
  Execution Request (`request-execution`, `confirm-execution`,
  `cancel-execution`, `expire-execution`). A single request ID can appear more
  than once as it moves through its lifecycle; the latest entry for an ID
  reflects its current status, but `execution/human_requests/<status>/<id>.json`
  is always authoritative.
- `research.json` — research notes/evidence gathered outside a formal decision.
  No CLI command writes this yet; append entries manually as
  `{"id", "date", "title", "topic", "summary", "path"}` when research is persisted
  under a future `context/summaries/` or `experiments/` artifact.

Each `*.json` file is a flat JSON array, append-only in practice (entries are not
edited after the fact; if a status changes, the source-of-truth file is updated
and, when practical, a new index entry or regeneration reflects it).

No vector database or external index infrastructure is used. This is intentional
per `SYSTEM_EVOLUTION.md` vendor-neutrality guidance — introduce one only if a
concrete retrieval need demonstrates that flat JSON no longer scales.

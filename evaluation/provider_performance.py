"""Provider Performance Registry (spec section 22).

Minimal, honest implementation: records one metrics event per completed
task/run and can aggregate simple counts/rates per (provider, function).
Deliberately avoids inventing causal claims ("Codex is better at X") -- it
only aggregates the numbers it is given (spec: "avoid simplistic
causality").
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "evaluation" / "provider_performance_log.jsonl"

FUNCTIONS = frozenset({
    "topic_discovery", "content_brief", "drafting", "technical_review",
    "editorial_critique", "seo_review", "commercial_opportunity_discovery",
    "code_review", "decision_critique",
})

METRIC_FIELDS = frozenset({
    "acceptance_rate", "human_revision_burden", "critic_score",
    "factual_error_rate", "publication_rate", "subsequent_content_performance",
    "leads", "conversions", "useful_novel_ideas", "duplicate_rate",
    "latency_seconds", "cost_signal",
})


def record_event(*, provider: str, function: str, run_id: str, metrics: dict,
                  registry_path: Path = REGISTRY_PATH) -> dict:
    if function not in FUNCTIONS:
        raise ValueError(f"unknown function: {function}")
    bad = set(metrics.keys()) - METRIC_FIELDS
    if bad:
        raise ValueError(f"unknown metric fields: {sorted(bad)}")
    event = {"provider": provider, "function": function, "run_id": run_id,
              "metrics": metrics}
    try:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        with registry_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")
    except OSError:
        pass
    return event


def load_events(registry_path: Path = REGISTRY_PATH) -> list[dict]:
    if not registry_path.exists():
        return []
    events = []
    for line in registry_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def aggregate(function: str | None = None, provider: str | None = None,
              registry_path: Path = REGISTRY_PATH) -> dict:
    """Simple mean-per-metric aggregation, filtered by function/provider.
    Returns counts and means only -- no derived "winner" verdict. Adaptive
    routing (section 23) is expected to consume this data manually/via a
    future rule layer, not via a built-in ranking here."""
    events = load_events(registry_path)
    if function:
        events = [e for e in events if e["function"] == function]
    if provider:
        events = [e for e in events if e["provider"] == provider]

    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for e in events:
        for k, v in e.get("metrics", {}).items():
            if isinstance(v, (int, float)):
                sums[k] = sums.get(k, 0.0) + v
                counts[k] = counts.get(k, 0) + 1
    means = {k: sums[k] / counts[k] for k in sums if counts.get(k)}
    return {"n_events": len(events), "means": means, "counts": counts}

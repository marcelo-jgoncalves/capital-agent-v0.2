"""Provider Performance Registry (spec section 22).

Tracks per-function performance signals for each provider, derived from
state/ai_runs/ plus explicit human/critic feedback recorded via
`record_feedback()`. Deliberately avoids simplistic causality (spec: "evite
causalidade simplista") -- this stores raw counters/signals, not a single
composite score, and comparisons are left to a human/future analysis, not
auto-computed here.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_FILE = ROOT / "state" / "provider_performance.json"

FUNCTIONS = (
    "topic_discovery", "content_brief", "drafting", "technical_review",
    "editorial_critique", "seo_review", "commercial_opportunity_discovery",
    "code_review", "decision_critique",
)


def _load() -> dict:
    if not REGISTRY_FILE.exists():
        return {"version": "0.1", "providers": {}}
    return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def record_feedback(provider: str, function: str, signal: str, value) -> dict:
    """`signal` is a free metric name (e.g. 'acceptance_rate', 'critic_score',
    'factual_error_count', 'latency_seconds') -- appended as a raw
    observation, never averaged/aggregated automatically here."""
    if function not in FUNCTIONS:
        raise ValueError(f"unknown function: {function}")
    data = _load()
    prov = data["providers"].setdefault(provider, {})
    fn = prov.setdefault(function, {"observations": []})
    fn["observations"].append({"signal": signal, "value": value})
    _save(data)
    return data


def summary() -> dict:
    """Raw counts only -- no derived ranking. Consumers decide what, if
    anything, the counts imply."""
    data = _load()
    out = {}
    for provider, functions in data.get("providers", {}).items():
        out[provider] = {fn: len(v.get("observations", [])) for fn, v in functions.items()}
    return out

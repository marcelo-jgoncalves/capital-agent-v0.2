"""AI run history: auditable, non-secret metadata for every reasoning
provider invocation (spec section 38). Appends one JSON file per run under
state/ai_runs/ -- never a secret, never a token, never an auth artifact.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_LOG_DIR = ROOT / "state" / "ai_runs"

_SECRET_KEY_PATTERN = re.compile(r"(token|secret|password|credential|api_key|auth)", re.IGNORECASE)


def _scrub(obj):
    """Recursively drop any dict key that looks like a secret. Defense in
    depth: callers should never pass secrets in, but a run log must not be
    the place a secret leaks if they accidentally do."""
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items() if not _SECRET_KEY_PATTERN.search(str(k))}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def record_run(*, task_id: str, provider: str, role: str, started_at: str, ended_at: str,
                input_context_refs: list[str], output_artifact: str | None,
                exit_status: str, capabilities_used: list[str], web_search_used: bool,
                workspace_write_used: bool, errors: list[str],
                provider_metadata: dict | None = None) -> dict:
    run_id = f"{provider}-{uuid.uuid4().hex[:12]}"
    record = _scrub({
        "run_id": run_id,
        "task_id": task_id,
        "provider": provider,
        "role": role,
        "started_at": started_at,
        "ended_at": ended_at,
        "input_context_refs": input_context_refs,
        "output_artifact": output_artifact,
        "exit_status": exit_status,
        "capabilities_used": capabilities_used,
        "web_search_used": web_search_used,
        "workspace_write_used": workspace_write_used,
        "errors": errors,
        "provider_metadata": provider_metadata or {},
    })
    try:
        RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
        (RUN_LOG_DIR / f"{run_id}.json").write_text(
            json.dumps(record, indent=2, default=str), encoding="utf-8"
        )
    except OSError:
        pass
    return record


def list_runs() -> list[dict]:
    if not RUN_LOG_DIR.exists():
        return []
    runs = []
    for f in sorted(RUN_LOG_DIR.glob("*.json")):
        try:
            runs.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return runs

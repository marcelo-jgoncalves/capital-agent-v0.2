"""Thin, defensive wrapper around the `codex` executable.

Everything that shells out to the real CLI lives here so the rest of the
adapter code (codex_adapter.py) never constructs subprocess commands
directly. Flags used are the ones actually present in this installation's
`codex --help` / `codex exec --help` output (verified 2026-08-13, codex-cli
0.147.0) -- not assumed from documentation or memory:

  codex --version
  codex exec --sandbox {read-only|workspace-write|danger-full-access}
             --skip-git-repo-check
             --output-schema <FILE>
             -o/--output-last-message <FILE>
             <PROMPT>

This module never reads, copies or logs anything under `~/.codex/` (auth
storage) -- it only invokes the `codex` binary already on PATH, which the
owner authenticated out-of-band.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

EXECUTABLE = "codex"
_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")

ALLOWED_SANDBOX_MODES = frozenset({"read-only", "workspace-write"})
# "danger-full-access" is intentionally never exposed as an allowed value
# anywhere in this codebase.


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode_subprocess_output(value: "bytes | str | None") -> str:
    """Normalize a subprocess.TimeoutExpired.stdout/.stderr value to str.
    See run_codex_exec's except block for why this exists."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


@dataclass
class HealthcheckResult:
    available: bool
    version: str | None
    supports_non_interactive: bool
    supports_structured_output: bool
    supports_web_search: bool
    last_checked_at: str
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "provider": "codex",
            "available": self.available,
            "version": self.version,
            "supports_non_interactive": self.supports_non_interactive,
            "supports_structured_output": self.supports_structured_output,
            "supports_web_search": self.supports_web_search,
            "last_checked_at": self.last_checked_at,
            "error": self.error,
        }


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float


_cache: HealthcheckResult | None = None


def healthcheck(force: bool = False) -> HealthcheckResult:
    global _cache
    if _cache is not None and not force:
        return _cache

    path = shutil.which(EXECUTABLE)
    if path is None:
        _cache = HealthcheckResult(
            available=False, version=None, supports_non_interactive=False,
            supports_structured_output=False, supports_web_search=False,
            last_checked_at=now_iso(), error="codex executable not found on PATH",
        )
        return _cache

    version = None
    try:
        proc = subprocess.run([EXECUTABLE, "--version"], capture_output=True,
                               text=True, timeout=15)
        m = _VERSION_RE.search(proc.stdout or proc.stderr or "")
        if m:
            version = m.group(1)
    except (subprocess.TimeoutExpired, OSError):
        pass

    supports_non_interactive = False
    supports_structured_output = False
    try:
        proc = subprocess.run([EXECUTABLE, "exec", "--help"], capture_output=True,
                               text=True, timeout=15)
        help_text = (proc.stdout or "") + (proc.stderr or "")
        supports_non_interactive = proc.returncode == 0
        supports_structured_output = "--output-schema" in help_text
    except (subprocess.TimeoutExpired, OSError):
        pass

    supports_web_search = False
    try:
        proc = subprocess.run([EXECUTABLE, "--help"], capture_output=True,
                               text=True, timeout=15)
        top_help = (proc.stdout or "") + (proc.stderr or "")
        supports_web_search = "--search" in top_help
    except (subprocess.TimeoutExpired, OSError):
        pass

    _cache = HealthcheckResult(
        available=True, version=version,
        supports_non_interactive=supports_non_interactive,
        supports_structured_output=supports_structured_output,
        supports_web_search=supports_web_search,
        last_checked_at=now_iso(),
    )
    return _cache


def run_codex_exec(prompt: str, *, sandbox: str, workdir: Path,
                    output_schema_path: Path | None = None,
                    timeout: int = 120) -> ExecResult:
    """Runs `codex exec` non-interactively. `sandbox` must be one of
    ALLOWED_SANDBOX_MODES -- this is checked here as a last line of defense
    even though callers (codex_adapter._sandbox_for) already only ever pass
    a safe value."""
    if sandbox not in ALLOWED_SANDBOX_MODES:
        raise ValueError(f"disallowed sandbox mode: {sandbox!r}")

    last_msg_file = tempfile.NamedTemporaryFile(prefix="codex_last_", suffix=".txt",
                                                  delete=False)
    last_msg_file.close()

    cmd = [
        EXECUTABLE, "exec",
        "--sandbox", sandbox,
        "--skip-git-repo-check",
        "-C", str(workdir),
        "-o", last_msg_file.name,
    ]
    if output_schema_path is not None:
        cmd += ["--output-schema", str(output_schema_path)]
    cmd.append(prompt)

    start = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        exit_code = proc.returncode
        stderr = proc.stderr or ""
        stdout = proc.stdout or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = -1
        # subprocess.run() was called with text=True, so at runtime
        # exc.stdout/exc.stderr are always str here; typeshed's stub for
        # TimeoutExpired types them as `bytes | str | None` regardless
        # (it doesn't track the call site's text= argument). Decode
        # defensively rather than assume/cast, so this stays correct even
        # if a future edit removes text=True from the subprocess.run call
        # above without updating this except block.
        stdout = _decode_subprocess_output(exc.stdout)
        stderr = _decode_subprocess_output(exc.stderr) + "\ncodex exec timed out"
    except OSError as exc:
        exit_code = -1
        stdout = ""
        stderr = f"failed to invoke codex: {exc}"
    duration = time.monotonic() - start

    last_message = ""
    try:
        last_message = Path(last_msg_file.name).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        pass
    finally:
        try:
            Path(last_msg_file.name).unlink(missing_ok=True)
        except OSError:
            pass

    final_stdout = last_message or stdout.strip()
    return ExecResult(exit_code=exit_code, stdout=final_stdout, stderr=stderr,
                       timed_out=timed_out, duration_seconds=duration)

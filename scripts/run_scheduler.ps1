# Wrapper invoked by Windows Task Scheduler to run the Capital Agent
# scheduler/orchestrator (src/scheduler.py) on a recurring cadence.
#
# This only runs deterministic checks and enqueues job tickets in
# state/pending_jobs.json -- it never calls an AI and never touches
# data/ledger.csv. See scheduler/README.md and ARCHITECTURE.md
# "Scheduler and orchestration".

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = "C:\Users\Usuario\AppData\Local\Programs\Python\Python312\python.exe"
$log = Join-Path $repo "state\scheduler_run.log"

Set-Location $repo
$timestamp = Get-Date -Format o
$entry = @("=== $timestamp ===")
try {
    $output = & $python (Join-Path $repo "src\scheduler.py") run 2>&1 | Out-String
    $entry += $output
} catch {
    $entry += "ERROR: $_"
}
Add-Content -Path $log -Value ($entry -join "`n") -Encoding utf8

$ErrorActionPreference = "Stop"

Write-Host "Capital Agent v0 bootstrap"
python --version
python .\src\capital_agent.py status
python .\src\capital_agent.py system-policy
python -m unittest discover -s tests

Write-Host ""
Write-Host "Next:"
Write-Host "  1. Initialize version control (for example: git init)"
Write-Host "  2. Give your chosen AI system access to this repository"
Write-Host "  3. Tell it to read AI_OPERATING_MANUAL.md"
Write-Host "  4. Ask it to execute PHASE0_READINESS_PROMPT.md"

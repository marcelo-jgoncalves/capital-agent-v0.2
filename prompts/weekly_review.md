# Periodic Capital Review Prompt

This prompt is vendor-neutral. Read `AI_OPERATING_MANUAL.md`,
`INVESTMENT_POLICY.md`, `HUMAN_GATES.md`, `SYSTEM_EVOLUTION.md`, both config
files, the ledger, active experiments, pending Human Execution Requests
(`execution/human_requests/pending/`), recent decisions and recent system
changes. This corresponds to the `weekly` frequency in
`config/schedules.json`; the scheduler (`src/scheduler.py`) may have already
queued a job for it in `state/pending_jobs.json`.

Then:

1. Reconcile current experiment state. Do not invent missing values.
2. Identify the best currently available uses of incremental capital.
3. Include doing nothing as a valid option.
4. Compare financial and productive/commercial opportunities.
5. Red-team the top candidates.
6. Reject anything that fails hard policy.
7. Rank remaining candidates by expected geometric-growth contribution, maximum
   plausible loss, evidence quality, capital efficiency, time to feedback,
   reversibility and scalability.
8. Decide within policy; do not defer this ranking/decision to the human — the
   human's role is custody, execution and critical-decision authorization, not
   substituting for this analysis.
9. Produce no more than three actionable recommendations. For any that require
   moving real money, prepare a Human Execution Request
   (`execution/human_requests/`) rather than executing anything.
10. If none clears the hurdle, recommend no allocation.
11. Write a decision record for any material recommendation.
12. Review recent operational friction/errors and propose system improvements when
    justified. Apply Class A/B changes when safe; propose but do not activate Class C.
13. If a scheduler job ticket exists for this review, mark it complete
    (`python src/scheduler.py complete-job --id ... --summary ...`) once done.

Never interpret "maximize capital" or "improve the system" as permission to bypass
risk, security, legality, human gates, or the custody invariant. The Capital Agent
never executes a financial operation itself, at any phase.

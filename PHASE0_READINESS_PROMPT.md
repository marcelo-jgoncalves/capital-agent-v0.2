# Phase 0 Readiness Task

This task is vendor-neutral and may be executed by any capable AI system with access
to the repository and local development tools.

Read the repository completely, especially:
- `AI_OPERATING_MANUAL.md`
- `INVESTMENT_POLICY.md`
- `HUMAN_GATES.md`
- `SYSTEM_EVOLUTION.md`
- `config/policy.json`
- `config/system_governance.json`
- source code and tests.

Then:

1. Audit contradictions between prose and machine-readable policy.
2. Run the test suite.
3. Threat-model the local workflow.
4. Identify any way an AI could accidentally record an unexecuted transaction as real.
5. Identify any way financial write authority could be enabled without a human gate,
   and specifically any way the custody invariant (`AI_OPERATING_MANUAL.md`) could be
   bypassed — including via `execution/human_requests/` self-marking as completed,
   a config edit, or a self-proposed system change.
6. Audit the self-improvement mechanism for ways it could bypass financial policy or
   the custody invariant (`SYSTEM_EVOLUTION.md` Class D).
7. Audit vendor lock-in: identify any critical behavior that depends unnecessarily on
   one model/provider/tool; confirm the scheduler (`src/scheduler.py`) and AI Provider
   Adapter abstraction (`adapters/ai_providers/`) do not hardcode a vendor.
8. Improve tests, guardrails and portability where needed.
9. Classify every material system change under `SYSTEM_EVOLUTION.md` and journal it.
10. Do not relax any hard financial policy or the custody invariant.
11. Verify a Human Execution Request cannot reach `completed` status without an
    explicit `confirm-execution` call driven by human-reported values.
12. Produce a readiness report in `journal/reviews/phase0-readiness.md`.

Do not research or allocate real capital in this task. Do not execute any financial
operation — this repository has no capability to do so and none should be added.

13. Audit `CRITICAL_DECISIONS.md` and verify that critical actions cannot be treated as approved without explicit authorization, and that approval is never conflated with financial execution.
14. Audit `EVALUATION_CRITIC_SYSTEM.md` and append-only critic/post-mortem evidence.
15. Verify that broad business-model freedom cannot override legal, security, bounded-loss, approval or custody controls.
16. Verify `START_HERE.md` is sufficient for a new AI to reconstruct the system, including the execution and scheduler state.

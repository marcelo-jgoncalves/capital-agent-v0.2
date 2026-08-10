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
5. Identify any way live authority could be enabled without a human gate.
6. Audit the self-improvement mechanism for ways it could bypass financial policy.
7. Audit vendor lock-in: identify any critical behavior that depends unnecessarily on
   one model/provider/tool.
8. Improve tests, guardrails and portability where needed.
9. Classify every material system change under `SYSTEM_EVOLUTION.md` and journal it.
10. Do not relax any hard financial policy.
11. Produce a readiness report in `journal/reviews/phase0-readiness.md`.

Do not research or allocate real capital in this task.

9. Audit `CRITICAL_DECISIONS.md` and verify that critical actions cannot be treated as approved without explicit authorization.
10. Audit `EVALUATION_CRITIC_SYSTEM.md` and append-only critic/post-mortem evidence.
11. Verify that broad business-model freedom cannot override legal, security, bounded-loss or approval controls.

# Phase 0 Readiness Report

- Date: 2026-08-10
- Scope: `PHASE0_READINESS_PROMPT.md`, executed in full against the repository
  state as of commit `a52323c` ("Formalize custody invariant: financial
  execution is exclusively human"), with two guardrail fixes made and
  committed during this audit (see item 9 below).
- Real capital was not researched or allocated during this task. No financial
  operation was executed — the repository has no capability to do so.

## 1. Contradictions between prose and machine-readable policy

Read `AI_OPERATING_MANUAL.md`, `INVESTMENT_POLICY.md`, `HUMAN_GATES.md`,
`CRITICAL_DECISIONS.md`, `SYSTEM_EVOLUTION.md`, `ARCHITECTURE.md`,
`ROADMAP.md`, `config/policy.json`, `config/critical_decisions.json`,
`config/system_governance.json`, `src/capital_agent.py`, `src/scheduler.py`,
`tests/`.

**No contradiction found** between prose and machine-readable policy as of
this audit. Cross-checks performed:

- `config/policy.json`'s `autonomous_financial_execution_permitted: false`
  matches every prose statement of the custody invariant, and is enforced in
  code (`load_policy()` raises `RuntimeError` if it is ever `true`) —
  verified by `test_load_policy_rejects_autonomous_execution_flag`.
- `config/critical_decisions.json` thresholds (BRL 25 for live money / max
  loss) match `CRITICAL_DECISIONS.md`'s description of "the non-critical
  threshold," and `classify_critical()` reads them directly rather than
  hardcoding a duplicate value.
- `config/system_governance.json`'s `autonomous_change_classes: [A, B]`,
  `human_approval_change_classes: [C]`, `prohibited_change_classes: [D]`
  match `SYSTEM_EVOLUTION.md` section 3 exactly, and
  `cmd_propose_system_change` reads them from the file rather than
  hardcoding.
- One **stale but harmless** field name was found and fixed during this
  audit: `config/policy.json`'s `human_gate_for_first_live_adapter` still
  used pre-custody-invariant terminology ("live adapter") after
  `HUMAN_GATES.md` Gate H4 was rewritten to describe a *read-only* adapter
  gate. Confirmed via `grep` that no code referenced the field name (so
  renaming was risk-free), renamed to
  `human_gate_for_first_readonly_financial_adapter`. This was a naming
  contradiction only — the boolean value and gate behavior were already
  correct; no policy value changed. See `git diff -- config/policy.json`
  against this audit's starting commit: exactly one line changed, a rename.

## 2. Test suite

`python -m unittest discover -s tests`: **39/39 passing** (as of the end of
this audit; 35 before the two fixes below, +4 new tests for those fixes).

## 3. Threat model of the local workflow

Confirmed the threat model in `ARCHITECTURE.md` remains accurate and, if
anything, more thoroughly mitigated than before this audit:

- External/web data, prompt injection, wrong AI decisions, stale APIs,
  duplicate requests, secret leakage, scam opportunities, regressive
  self-modification, and context loss across AI sessions are all named and
  addressed by existing controls (untrusted-external-content framing,
  `execution/` lifecycle dedup via `HR_PENDING_DIR` id lookups, `.gitignore`
  secret patterns, `SYSTEM_EVOLUTION.md` rollback requirements,
  `START_HERE.md`/`context/CURRENT_STATE.md`).
- Added to the threat model this audit surfaced concretely (not
  hypothetically): a component "being tempted to treat 'recommended' or
  'approved' as if it meant 'executed'" was already listed in
  `ARCHITECTURE.md`'s threat model prose, and this audit found and closed a
  real instance of exactly that risk (item 4 below).

No change to `ARCHITECTURE.md`'s threat-model section was needed; it already
anticipated the class of problem found.

## 4. Ways an AI could accidentally record an unexecuted transaction as real

**Found and fixed.** `capital_agent.py record --type buy|sell|capital_out`
wrote directly to `data/ledger.csv` with no requirement that any Human
Execution Request existed or was confirmed by a human — a direct bypass of
the entire `execution/` lifecycle added in the prior change
(`SYS-20260810-BD6581`). Reproduced live before the fix:

```text
python src/capital_agent.py record --type buy --category market --amount 5 \
  --description "sneaky" --reference TEST
# succeeded, wrote a fabricated 'buy' row to data/ledger.csv
```

**Fix**: `record` now refuses `buy`, `sell` and `capital_out` outright,
directing the caller to `request-execution` / `confirm-execution` instead.
Non-execution bookkeeping types (`capital_in`, `revenue`, `refund`,
`expense`, `fee`, `tax`, `adjustment`) remain available, since they do not
represent a market position change or money leaving custody. Journaled as
`SYS-20260810-F9CEAA` (Class A). Tests: `test_record_refuses_buy_sell_and_capital_out`,
`test_record_still_allows_non_execution_bookkeeping`.

No other write path to `data/ledger.csv` exists — `grep -n "append_ledger("
src/capital_agent.py` shows exactly two call sites: `cmd_record` (now
guarded) and `cmd_confirm_execution` (human-report-driven, the intended
path).

## 5. Ways financial write authority could be enabled without a human gate / custody invariant bypass

Checked three specific vectors named in the readiness prompt:

- **`execution/human_requests/` self-marking as completed**: not possible.
  `cmd_confirm_execution` is the only function that moves a request to
  `completed` or calls `append_ledger`; it takes human-supplied
  quantity/price/fees as CLI arguments and makes no network or API call of
  its own. There is no `cmd_*` function that transitions a `pending` request
  to `completed` without going through it (verified by reading every
  `cmd_*` function in `src/capital_agent.py`; also see item 4's `grep` of
  `append_ledger` call sites). Tests:
  `test_confirm_execution_is_the_only_path_to_completed_and_ledger_update`,
  and `test_cancel_execution_never_touches_ledger` /
  `test_expire_execution_never_touches_ledger` /
  `test_sweep_expired_executions_is_deterministic_and_does_not_touch_ledger`
  confirm the other three terminal transitions never touch the ledger either.
- **A config edit**: `autonomous_financial_execution_permitted` is read by
  `load_policy()`, which is called by nearly every command
  (`cash_balance`, `policy_check_proposal`, `cmd_status`, etc.); flipping it
  to `true` in `config/policy.json` causes every one of those calls to raise
  `RuntimeError` immediately rather than silently granting authority. There
  is no code anywhere that *executes* a financial operation, so even if this
  guard were somehow removed, there would be no capability for the flag to
  unlock — the invariant is enforced by absence of capability, not only by
  the flag check. Test: `test_load_policy_rejects_autonomous_execution_flag`.
- **A self-proposed system change**: `--enables-autonomous-financial-execution`
  forces `Class D` / `REJECTED_PROHIBITED` regardless of the class
  requested. During this audit, a *second*, independent check was added: a
  keyword scan over the proposal's own text (`place_order`, `broker api`,
  `write access`, `withdraw(`, `transfer(`, `buy(`, `sell(`, etc.) that
  refuses to create the record at all unless the proposer either sets the
  rejection flag or explicitly acknowledges the change does *not* enable
  financial execution. This was validated live: proposing this very audit's
  own fix (whose description necessarily discusses `place_order()` and
  `withdraw(`) triggered the refusal until
  `--acknowledge-no-autonomous-financial-execution` was passed — the
  guardrail worked as designed on a real, non-adversarial input. Journaled
  as part of `SYS-20260810-F9CEAA`. Tests:
  `test_propose_system_change_forces_rejection_for_autonomous_execution`,
  `test_propose_system_change_flags_custody_risk_keywords_without_flag`,
  `test_propose_system_change_allows_keyword_match_with_explicit_acknowledgment`.

**One limitation found and documented, not code-fixed** (no equally cheap
fix exists): `approvals/pending/<id>.md`'s `## Human decision` section is a
plain text file field. No CLI command ever writes `APPROVED` into it
(confirmed: `grep -n APPROVED src/capital_agent.py` shows the string only
ever *read*, in `_approval_decision`), so setting it requires a positive,
manual file edit — but nothing in this filesystem-only trust model
technically distinguishes "the human owner edited this" from "the AI
operator's session edited this," since both have the same filesystem write
access. This is a structural property of Phase 0 (no signing, no
out-of-band channel), not a bug introduced by any change in this repository.
Documented in full, with candidate mitigations, in
`context/knowledge/open-questions.md` under "How should a critical-decision
approval be authenticated as genuinely human?" — flagged as needing a human
decision before Phase 2's first real Human Execution Request, since that is
when this limitation would first matter for actual money.

## 6. Self-improvement mechanism audit for custody/policy bypass

Reviewed `cmd_propose_system_change` end to end (the only path by which the
system's own governance state, `journal/system_changes/`, gets written) and
`SYSTEM_EVOLUTION.md` Class D language. Findings:

- The forced-Class-D flag and the new keyword scan (item 6/9) together mean
  a proposal cannot reach `PROPOSED_AUTONOMOUSLY_ALLOWED` or
  `PROPOSED_HUMAN_APPROVAL_REQUIRED` status while its own text plainly
  describes a write-capable financial mechanism, without at least pausing to
  either flag it as prohibited or explicitly assert otherwise.
- `SYSTEM_EVOLUTION.md` Class D bullet list explicitly names "create or
  enable any component ... with write authority over real money" as
  unconditional and un-overridable "by this document, by a Class C proposal,
  by a system change of any class, or by reclassifying the action under a
  different name" — this closes the reclassification loophole in prose to
  match what the code now enforces.
- Class C examples were checked against Class D: none of the remaining Class
  C examples (allocation caps, minimum reserve, recurring-liability
  capacity, read-only data adapter scope, accounting rules) grant financial
  write authority; they only adjust how much the human is asked to execute
  or what the system may read.
- No code path allows a system change to bypass `require_tests_for_code_changes`
  or `require_rollback_plan_for_class_b` — these are prose-only requirements
  in `config/system_governance.json`/`SYSTEM_EVOLUTION.md`, not
  code-enforced. This is an accepted limitation of Phase 0 (see "Known
  limitations" below), consistent with the whole governance model's current
  reliance on the operating AI's good-faith compliance plus after-the-fact
  auditability, not sandboxing.

## 7. Vendor lock-in audit

- `src/capital_agent.py` and `src/scheduler.py` import only Python standard
  library modules (`argparse`, `csv`, `json`, `sys`, `uuid`, `dataclasses`,
  `datetime`, `pathlib`, `abc`) — confirmed by grepping all `import`/`from`
  lines in both files. No AI SDK, no cloud SDK, no broker/exchange client
  library.
- Grepped the full repository (`.md` and `.py`) for `claude|anthropic|openai|
  chatgpt|codex|gemini`, case-insensitive. Every match is either (a) inside
  `adapters/` (where vendor references are explicitly permitted as adapter
  content, e.g. `adapters/ai_providers/README.md`), or (b) an illustrative
  list of *interchangeable example* providers inside canonical documents
  (`AI_OPERATING_MANUAL.md`, `ARCHITECTURE.md`, `START_HERE.md` all phrase it
  as "Claude Code / Codex / Gemini CLI / a local model / a future provider,"
  never as a directive naming one), or (c) the literal filename `CLAUDE.md`
  as a compatibility-adapter example. No canonical document contains a
  vendor-directed instruction ("Claude must...", "Codex should...").
- `src/scheduler.py`'s own source text (the code that actually runs
  unattended) contains **zero** vendor-name references — confirmed by
  `test_scheduler_source_names_no_ai_vendor`. It queues jobs generically;
  which AI dequeues and works them is entirely external to the scheduler.
- `adapters/ai_providers/base.py`'s contract (`is_available`, `dispatch`) is
  provider-agnostic; the only implementation (`manual_adapter.py`) does not
  call any model API — it prints instructions for a human-launched session,
  honestly reflecting that no unattended API-driven adapter exists yet
  (documented as future work in `adapters/ai_providers/README.md`, not
  overclaimed as already built).

**No findings.** Vendor neutrality holds both in canonical prose and in the
code that actually executes.

## 8. Tests, guardrails and portability improvements made

- `tests/test_custody_and_execution.py` (pre-existing from the prior change,
  extended this audit): 25 tests total (21 from the prior change + 4 new this
  audit, covering the two fixes below). Full suite: 39 (25 +
  `tests/test_capital_agent.py`'s 14).
- `src/capital_agent.py`: `RECORD_BLOCKED_TYPES` guard, `CUSTODY_RISK_KEYWORDS`
  scan, `--acknowledge-no-autonomous-financial-execution` flag.
- `config/policy.json`: field rename for terminology accuracy (see item 1).
- No portability regression: all new code remains pure standard library.

## 9. Material system changes classified and journaled

- `SYS-20260810-F9CEAA` (Class A, `PROPOSED_AUTONOMOUSLY_ALLOWED`): the two
  guardrail fixes described in items 4 and 5/6 above, including evidence,
  risks, rollback plan and validation, per `SYSTEM_EVOLUTION.md` section 5.

(`SYS-20260810-BD6581` and `SYS-20260810-D62661`, the custody-invariant
formalization and the Context Management System, were journaled in prior
sessions and are referenced but not re-journaled here.)

## 10. Hard financial policy / custody invariant relaxation check

**None occurred.** `git diff` against this audit's starting commit
(`a52323c`) touches exactly one policy file, `config/policy.json`, with
exactly one line changed — a field *rename*
(`human_gate_for_first_live_adapter` ->
`human_gate_for_first_readonly_financial_adapter`), not a value change. No
threshold in `config/critical_decisions.json` was lowered. No boolean in
`config/policy.json` (`autonomous_financial_execution_permitted`,
`live_execution_enabled`, `borrowing_allowed`, `leverage_allowed`,
`withdrawals_allowed`) changed value. Every change made during this audit
*narrows* what the system will silently accept (`record` accepts fewer
types; `propose-system-change` requires more explicit acknowledgment).

## 11. Human Execution Request completion path

Confirmed: a request can reach `completed` status **only** via
`cmd_confirm_execution`, which requires `--executed-quantity` and
`--executed-price` as explicit arguments (human-reported), performs no
network/API call, and is the only function (besides `cmd_record`, now
guarded) that calls `append_ledger`. `cancel-execution`, `expire-execution`
and `sweep-expired-executions` move a request to a terminal state without
ever touching the ledger — verified by three dedicated tests (item 5 above).

## 12. This report

Produced at `journal/reviews/phase0-readiness.md`, as required.

## 13. `CRITICAL_DECISIONS.md`: approval vs. execution separation

Confirmed both in prose and in code:

- `CRITICAL_DECISIONS.md`'s core rule now states explicitly: "Authorization
  of a critical decision is a separate event from financial execution... it
  does not itself execute anything."
- In code, `cmd_request_execution` treats an `APPROVED` approval as
  *necessary but not sufficient* to create a `pending` Human Execution
  Request — it still requires a *separate* `confirm-execution` call to
  affect the ledger. No code path treats "approval exists and says APPROVED"
  as equivalent to "the money moved." Tests:
  `test_critical_execution_allowed_after_explicit_approval` confirms
  approval only unblocks *creating* the pending request, and the ledger is
  untouched at that point (implicitly verified since only
  `cmd_confirm_execution`, called separately in other tests, ever changes
  cash balance).
- A critical action cannot be "treated as approved" implicitly: `silence,
  previous broad authorization, the mission to maximize capital, or approval
  for a similar action does not count as approval" (unchanged prose from
  before this audit, still accurate); `_approval_decision` requires the
  literal string `APPROVED` in the specific approval file referenced by
  `--approval-id`, not a general "some approval exists somewhere" check.

## 14. `EVALUATION_CRITIC_SYSTEM.md`: append-only critic/post-mortem evidence

`journal/predictions/`, `journal/postmortems/`, `journal/audits/`,
`evaluation/calibration/`, `evaluation/benchmarks/`, `evaluation/attribution/`
are currently **empty** — no CLI command in `src/capital_agent.py` or
`src/scheduler.py` writes to any of them (confirmed by grep: no
`PREDICTIONS_DIR`/`POSTMORTEMS_DIR`/`AUDITS_DIR` constants exist in code).
This is consistent with Phase 0 scope (`EVALUATION_CRITIC_SYSTEM.md` does not
claim automation exists) — these artifacts are currently produced manually
from `journal/PREDICTION_TEMPLATE.md`, `journal/POSTMORTEM_TEMPLATE.md`,
`journal/AUDIT_TEMPLATE.md` by whichever AI operator does the work. Because
no code touches these directories, there is no code-level append-only
violation risk to find. **Recommendation** (not implemented in this audit,
out of scope for a readiness check): when a CLI-backed predictions/post-mortems
workflow is eventually added (Class A/B per `SYSTEM_EVOLUTION.md`), give it
the same append-only discipline already used for `journal/decisions/` and
`journal/system_changes/` (new files only, never edited in place).

## 15. Business-model freedom cannot override legal/security/bounded-loss/approval/custody controls

Confirmed: `AI_OPERATING_MANUAL.md`'s "Business-model freedom" section
explicitly lists the custody invariant among the things business-model
freedom "never overrides," alongside law, regulation, platform terms,
security, bounded-loss requirements, critical-decision approval, contractual
gates and identity/reputation protections. `INVESTMENT_POLICY.md` section 11
repeats this with "any real money movement is human-executed per the custody
invariant." In code, `policy_check_proposal` and `classify_critical` apply
uniformly to every category argument passed to `propose`, `new-experiment`
and `request-execution` — there is no `--category` value or business-model
type that skips a policy or criticality check. No special-cased "commercial
experiment" or "non-financial" bypass exists in the code.

## 16. `START_HERE.md` sufficiency for reconstruction

Confirmed via `test_start_here_exists_with_required_anchors` and manual
reading: `START_HERE.md` states the custody invariant in section 0 before
anything else, gives an ordered reading list (section 2) including
`execution/human_requests/pending/` and `state/pending_jobs.json`, points to
`context/CURRENT_STATE.md` (which itself lists pending Human Execution
Requests, pending approvals, active experiments and recent system changes),
and points to the scheduler's own state files
(`state/scheduler_state.json`, `state/pending_jobs.json`) in section 4 and 9.
A new AI given only "Read START_HERE.md and assume operation of the Capital
Agent" can reconstruct: current cash/equity, any pending recommendation
awaiting human execution, any pending critical-decision approval, active
experiments, recent decisions/system changes, and queued scheduler jobs —
all from files, none from conversation history.

## Known limitations (accepted, not fixed in this audit)

1. **Approval authenticity** (item 5): no cryptographic or out-of-band
   guarantee that `APPROVED` in an approval file was written by the human
   owner rather than by an AI session with filesystem access. Documented in
   `context/knowledge/open-questions.md`; needs a human decision before
   Phase 2.
2. **Governance requirements not code-enforced** (item 6): rollback plans,
   test requirements, and the append-only convention for `journal/decisions/`
   and `journal/system_changes/` rely on the operating AI following
   `SYSTEM_EVOLUTION.md`'s prose, not a code-level lock (e.g. nothing
   prevents a `cmd_*` function from being added later that edits an existing
   decision file in place). This mirrors the same trust model as item 1 and
   is consistent with Phase 0's overall design (auditability over
   sandboxing).
3. **Keyword scan is heuristic** (item 6/9): can both false-positive (as
   demonstrated live on this audit's own proposal text) and, in principle,
   be evaded by careful phrasing. It is a net, not a guarantee, and does not
   replace human review of `journal/system_changes/`.
4. **Evaluation & Critic System has no CLI backing yet** (item 14): purely
   template-driven today; fine for Phase 0, worth automating alongside
   decisions/system-changes when that becomes a bottleneck.

## Overall readiness verdict

Phase 0 exit criterion — "The AI can inspect state, improve the system
within allowed classes, create proposals and produce auditable decisions and
Human Execution Requests without moving real money" — **is met**. The
custody invariant is enforced by both the absence of any execution
capability and an explicit code-level guard; the one real bypass path found
during this audit (`record --type buy`) was closed and tested; the one
residual limitation (approval authenticity) is a known, documented,
human-decision item rather than a silently accepted gap. 39/39 tests pass.
No hard policy or custody invariant was relaxed during this audit.

## Next recommended action

Per `ROADMAP.md` Phase 0's remaining unchecked items: configure an actual AI
Provider Adapter for unattended dispatch (currently only the manual/
human-launched adapter exists), then run the first opportunity research
cycle. Before any real Human Execution Request in Phase 2, resolve the
approval-authenticity open question above with the human owner.

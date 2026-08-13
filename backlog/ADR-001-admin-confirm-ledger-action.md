# ADR-001: `--admin-confirm` / `--reason` administrative ledger path

Status: **PROPOSED (recommendation only) -- not activated, no owner decision recorded**
Author: AI operator (hardening pass, prompt-hardening-final-capital-agent-v0.2.md section 7)
Date: 2026-08-13

## Context

`capital_agent.py record --admin-confirm --reason ...` is the narrow,
explicitly-audited escape hatch for `capital_in` and `adjustment` -- ledger
facts that are neither a Human Execution Request (no market/position change,
nothing "executed") nor an ExternalCashEvent (not externally-arriving cash
from a customer/counterparty). Typical uses: the initial funding event, a
documented manual correction.

Current mechanism (`RECORD_REQUIRES_ADMIN_CONFIRM_TYPES` in
`src/capital_agent.py`):

1. caller passes `--admin-confirm` (a boolean flag) and `--reason <text>`
   (non-empty, free text);
2. an audit record is written to `journal/admin_ledger_actions/<id>.json`
   containing type/category/amount/description/reference/reason/timestamp;
3. the ledger row is appended, with `[ADMIN-CONFIRMED: <reason>]` folded
   into the description.

This already follows the interactive-session human-statement convention
used elsewhere (`approve-decision --human-statement`, see
`CRITICAL_DECISIONS.md` "Approval authentication") -- it is not an
unauthenticated bypass.

## Risk analysis

**What this mechanism gets right today:**
- narrowly scoped (only `capital_in`/`adjustment`, never buy/sell/
  capital_out/expense/fee/tax -- those are `RECORD_BLOCKED_TYPES` now,
  see section 3 of this hardening pass);
- requires an explicit flag AND non-empty free-text reason -- cannot be
  triggered by default/silent code paths;
- persists a separate, timestamped audit record distinct from the ledger
  row itself;
- the amount/category/description are still whatever the caller passes --
  i.e. this is a real trust boundary, unlike buy/sell/expense/etc. which
  must trace back to something the human already confirmed via a different
  mechanism (HER, ExternalCashEvent).

**What is weaker than those other two paths:**
- `--admin-confirm` is a bare boolean; unlike `approve-decision
  --human-statement`, there is no requirement that `--reason` be the
  human's own words quoted verbatim, and the CLI cannot itself distinguish
  "a human typed this interactively" from "an AI operator constructed this
  flag and reason string autonomously and passed it." The same filesystem/
  process access that lets a human run this command also lets an
  unsupervised AI operator run it, exactly the authentication gap already
  flagged for `approve-decision` in `CRITICAL_DECISIONS.md` "Approval
  authentication" -- and this command has *no* equivalent flagged caveat
  today even though the underlying weakness is identical;
- no generated action id / two-step confirm-then-execute separation: the
  flag and the write happen in the same invocation, so there is no window
  in which a human reviews a *proposed* admin action (with its exact
  amount/category/description) before it becomes a ledger fact, unlike the
  HER lifecycle (`request-execution` -> review -> `confirm-execution`);
- no explicit single-use binding to a specific, previously-reviewed amount:
  a human authorizing "an administrative correction" in conversation has no
  structured artifact analogous to a Human Execution Request pinning the
  exact amount/category/description that gets posted.

**Why this has not caused an incident so far:** the type surface is narrow
(`capital_in`/`adjustment` only) and every use to date is the initial
funding event / documented corrections, which are inherently rare,
low-frequency, low-blast-radius actions reviewable via
`journal/admin_ledger_actions/` and the ledger itself. The gap is real but
currently low-severity because of that narrowness, not because the
authentication problem doesn't exist.

## Options considered

1. **Keep as-is.** Simple, already narrowly scoped, already audited.
   Downside: the authentication gap above remains unaddressed.
2. **Evolve to a full "Admin Ledger Action" pipeline**, per the prompt's
   suggested shape:
   ```text
   Admin Ledger Action
   -> generated action id
   -> explicit human confirmation
   -> one-time execution
   -> audit journal
   ```
   This would mirror the Human Execution Request two-step pattern:
   `propose-admin-action` (persists a pending action with a generated id,
   the exact amount/category/description/reason) then
   `confirm-admin-action --id ...` (the only thing that actually writes the
   ledger row, requiring the human's own words per the `approve-decision`
   convention). Downside: more moving parts for what is, so far, a rare
   bookkeeping operation; risk of over-engineering a corner case.
3. **Minimal tightening without a new pipeline**: require `--reason` to be
   explicitly framed as a verbatim human statement (matching
   `approve-decision --human-statement`'s convention/wording) and add the
   same "captured via interactive session, single-operator machine, not
   inferred" caveat already present for `approve-decision`. This closes the
   documentation/authentication-honesty gap cheaply without a new
   two-step CLI flow.

## Recommendation (not a decision -- owner authorization required to activate)

Recommend **Option 3 now** (cheap, closes the most misleading part of the
gap -- namely, that this command currently looks equally authenticated as
`approve-decision` but documents none of its caveats) **and revisit Option
2** if/when administrative ledger actions become frequent enough that a
generated-id, two-step, audit-journaled flow earns its complexity. This
hardening pass does **not** implement either option's code changes -- doing
so would be inventing a product/authentication-design decision the AI
operator is not authorized to make unilaterally (`CRITICAL_DECISIONS.md`:
"policy relaxation or any action outside current authority" and "weakening
approval requirements" are always critical; the inverse -- strengthening
authentication wording -- is not itself blocked, but is left to the owner
to review since it changes operator-facing tooling behavior/UX).

**Preserved behavior in this pass:** no relaxation. `--admin-confirm` and
`--reason` remain required exactly as before; the type surface
(`capital_in`, `adjustment` only) is unchanged; the audit-record write is
unchanged.

## Next step

Owner reviews this ADR and either:
(a) accepts Option 3 wording change (low risk, can likely be Class A per
`SYSTEM_EVOLUTION.md` -- it only tightens documentation/expectation, not
authority), or
(b) requests Option 2's two-step pipeline (Class B: materially changes how
an existing write path operates, needs a before/after review + rollback
plan), or
(c) explicitly accepts the status quo and closes this ADR as "risk
accepted."

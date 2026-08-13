# Open Questions

Unresolved questions that affect capital decisions or system design, so a future
AI operator does not have to rediscover them from scratch.

## Format

```
### <short question>
- Raised:
- Why it matters:
- What would resolve it:
```

## Entries

### What read-only financial data adapter(s) should Phase 3 target first?
- Raised: 2026-08-10 (repository initialization / Context Management System setup); revised 2026-08-10 (custody invariant formalization — see `journal/system_changes/` for the change that removed write-capable execution adapters from the architecture entirely).
- Why it matters: `ARCHITECTURE.md` lists read-only financial data adapters as a
  future component (balances/positions/statements/order history, for
  reconciliation against human-reported Human Execution Request confirmations)
  but none exists yet; the choice affects which read-only integration and Gate
  H4 approval package gets prepared first. This is no longer about a write
  adapter — none may ever exist under this architecture.
- What would resolve it: completion of Phase 1 opportunity research showing which
  category of opportunity (listed assets, crypto, commercial experiment, etc.)
  has the strongest evidence, which determines which platform's read-only API
  is worth integrating first.

### How should the equity high-water mark be tracked for drawdown calculation?
- Raised: 2026-08-10 (building `context/CURRENT_STATE.md` generation)
- Why it matters: `INVESTMENT_POLICY.md` section 8 and `config/policy.json`'s
  `hard_drawdown_freeze_pct` depend on knowing peak equity, but no mechanism
  currently records historical equity snapshots over time.
- What would resolve it: deciding whether to derive it from periodic
  `context/snapshots/` captures or from a dedicated equity-history file, then
  implementing it as a Class A system change (see `SYSTEM_EVOLUTION.md`).

### What counts as a "reliable" low-risk BRL benchmark data source?
- Raised: 2026-08-10 (repository initialization).
- Partially resolved: 2026-08-10. A first manual snapshot exists
  (`evaluation/benchmarks/2026-08-brl-risk-free.md`, Selic 14% a.a. via
  WebSearch, cross-checked across 3 sources) and was used as the hurdle rate
  in the first opportunity-cycle decision
  (`journal/decisions/DEC-20260810-A032A0.md`).
- Why it still matters: still manual and unautomated, will go stale. The
  Yahoo Finance MCP added this session covers US equities, not a BCB/B3/Selic
  feed — a different source is needed to automate this specific benchmark.
- What would resolve it fully: `ROADMAP.md` Phase 1 data-integration work —
  find and wire up a repeatable BCB/Tesouro Direto data source instead of
  re-searching the web manually each time.

### How should a critical-decision approval be authenticated as genuinely human?
- Raised: 2026-08-10 (Phase 0 readiness audit, `journal/reviews/phase0-readiness.md`).
- Partially resolved: 2026-08-10. The human owner confirmed only they have
  access to the operating machine and accepted the interactive-session
  convention as sufficient for now, with the explicit intent to strengthen it
  later if the experiment proceeds. Implemented `approve-decision` /
  `reject-decision` (`src/capital_agent.py`), which record the human's
  literal statement plus a timestamp, and documented the convention's scope
  in `CRITICAL_DECISIONS.md` "Approval authentication" and `HUMAN_GATES.md`
  Gate H7.
- Why it still matters (not fully resolved): the underlying limitation is
  unchanged — nothing cryptographically distinguishes a human-typed
  authorization from an AI-fabricated one, since both edit the same file with
  the same access. What changed is that this is now an *accepted, documented,
  human-confirmed* trade-off scoped to "single-operator machine, interactive
  session only," rather than a silent gap. It explicitly does **not** cover
  unattended/scheduled sessions (`scheduler/`) — there is no human present to
  type an authorization in that case, so this convention provides no
  protection there.
- What would resolve it fully: before any Human Execution Request is
  triggered by an unattended/scheduled session (Phase 2+ with the scheduler
  actually initiating AI sessions rather than just queuing tickets for a
  human-launched one), replace or supplement this with a stronger mechanism —
  a human-only interactive confirmation the AI cannot script around, a signed
  approval the AI never has the key for, or an approval channel entirely
  outside the repository. Revisit this decision if the operating machine ever
  gains additional users/access.

### Does the Yahoo Finance MCP actually work end to end on this machine?
- Raised: 2026-08-10 (`SYS-20260810-C76D60`, `.mcp.json` added, human-approved
  via `APR-20260810-7BFB0C`).
- Why it matters: `.mcp.json` was configured mid-session, so the tool is not
  callable until the next Claude Code session reconnects. The npm package
  (`yahoo-finance-mcp-server`) shells out to a local Python `yfinance`
  runtime that was not separately confirmed installed on this machine
  (only that Python 3.12 itself is present).
- What would resolve it: in the next session, call one of its tools (e.g. a
  quote lookup) and confirm it returns real data rather than an error. If it
  fails due to a missing `yfinance` install, that is a `pip install yfinance`
  fix, not a governance issue — but should be logged either way (a
  post-mortem if it silently failed for a while, or just closing this
  question if it works cleanly).

### `iadecifrada.com.br` as a channel — reopened by the human owner
- Raised: 2026-08-10. Superseded: 2026-08-10 (same day).
- Status: **back in scope, conditionally.** Originally disregarded
  entirely ("vamos desconsiderar a minha plataforma por enquanto... se
  pudermos contar com ela no futuro, eu aviso aqui" — see prior version of
  this entry). The human owner has now given exactly that signal, in the
  context of `DEC-20260810-7B41E9` (Addendum 8): the blog, once finished,
  should become the channel for that candidate (and plausibly future ones)
  instead of a standalone free-hosted page, specifically to solve a
  credibility gap a domain-less page couldn't fully fix. Finishing the
  blog itself remains the human owner's own, separately-tracked work — the
  Capital Agent does not take on or track that work, only the decision to
  target it as a channel once ready.
- Why it matters: future growth-vector candidates sourced from here on
  should consider `iadecifrada.com.br` a plausible eventual channel again,
  rather than assuming (as the disregarded-since-2026-08-10 status
  previously required) that everything must be built on throwaway
  infrastructure from zero. This does not mean defaulting to it blindly —
  each candidate should still weigh channel choice on its own merits
  (timeliness sensitivity vs. the blog's unknown completion date), same as
  `DEC-20260810-7B41E9` did explicitly.
- What would resolve it fully: the blog actually reaching a "ready for
  real content" state — no estimate given as of this entry.

### Should the AWS Free Tier page become the first of a series, rather than a one-off?
- Raised: 2026-08-10 (`DEC-20260810-7B41E9`), human owner asked whether
  building a series of similar pages would be interesting.
- Why it matters: a series would amortize fixed costs (domain/hosting
  setup, and the earlier-declined AdSense idea specifically becomes more
  plausible with accumulated multi-page traffic, per that addendum's own
  revisit condition), compound audience/email-list growth faster than one
  page, and reinforce topical SEO authority. But today's research session
  also showed the supply of genuinely uncrowded candidates is scarce by
  construction: 5 dated-event candidates were evaluated today
  (`context/knowledge/rejected-opportunities.md`), only 1 (the AWS page)
  survived crowding + primary-source-value checks. Committing to "a
  series" as a plan risks assuming a cadence of good topics the sourcing
  method has not yet proven it can sustain, and each page adds real,
  non-automatable verification and maintenance labor (staleness risk),
  not just writing time.
- What would resolve it: do not commit to a series before this first page
  has any real result (traffic, email signups) to learn from. Recommended
  sequence: finish and ship the AWS Free Tier page alone first; treat "does
  the sourcing method reliably find one good candidate per session, and
  does a shipped page actually get any signal" as the two things this
  first page needs to answer before scaling into a series is a capital/
  labor decision worth making. Revisit explicitly once that first result
  exists, not before.

### Scheduler backlog discovered running unattended, and `CURRENT_STATE.md` found stale on this point
- Raised: 2026-08-11 (discovered mid-session; human owner asked directly
  "existe alguma automação rodando não é?").
- What was found: a Windows Scheduled Task, `CapitalAgentScheduler`
  (`Get-ScheduledTask`), has been running `scripts/run_scheduler.ps1` every
  ~15 minutes since it was created on 2026-08-10T11:35:14-03:00, and is
  still active and healthy (`LastTaskResult: 0`, next run ~15 min out at
  any given check). It only calls `python src/scheduler.py run`, which is
  purely deterministic per its own design (`START_HERE.md` section 9) — it
  queues jobs based on repository state, it does **not** invoke an AI and
  does **not** touch money, so the custody invariant is unaffected. But
  nothing has been consuming the queue it builds: as of 2026-08-11,
  `state/pending_jobs.json` held **20 unprocessed jobs** (3 `frequent`, 4
  `daily`, 3 `weekly`, 5 `monthly`, 3 `quarterly`, plus 2 fired-trigger
  jobs — `new_revenue_detected` and `human_execution_confirmation_received`
  — from 2026-08-10T16:05), all still `queued`, none `completed`, several
  marked `requires_ai_reasoning: true`.
- A related, separate finding: `context/CURRENT_STATE.md`'s "Risks"
  section currently reads "No scheduler run history yet; autonomous
  operation cadence is not yet exercised in production" — this is **stale
  and factually wrong** as of this discovery (there is 40+ entries of real
  run history in `state/scheduler_state.json`). `update-context` was
  re-run after this discovery and the line did not change, meaning that
  section of the generator does not actually read `scheduler_state.json` —
  it appears to be static/hardcoded text rather than the "generated
  deterministically... do not hand-edit" guarantee the file's own header
  claims for the whole document. This undermines trust in that specific
  section and should be treated as a real generator bug, not just a
  one-time stale fact.
- Why it matters: (1) a real backlog of scheduled work exists and is
  growing every day unattended — some of it (daily risk review, weekly
  capital allocation review) is exactly the kind of thing this project
  exists to keep current; (2) the two fired triggers
  (`new_revenue_detected`, `human_execution_confirmation_received`) are
  from 2026-08-10 and have not been looked at — worth checking they don't
  represent something time-sensitive that was missed; (3) the
  `CURRENT_STATE.md` staleness on this specific section means a future
  session skimming just that file (as `START_HERE.md` step 1 recommends)
  would be actively misled into thinking no automation has run yet.
- Status: **explicitly paused, not processed.** Human owner instruction
  this session: stop here, log it properly, revisit later. No job was
  completed, no trigger investigated, and no fix was made to the
  `update-context` generator during this session.
- What would resolve it: a future session (1) processes or triages the 20
  queued jobs (`python src/scheduler.py complete-job` per job, per
  `scheduler/README.md`), starting with the two 2026-08-10 triggers since
  those are event-driven rather than routine; (2) investigates and fixes
  why `CURRENT_STATE.md`'s Risks section doesn't reflect
  `scheduler_state.json` (likely a `src/capital_agent.py` generator gap —
  a Class A/B system change per `SYSTEM_EVOLUTION.md`, not itself a capital
  decision).

### NFS-e/MEI guide — on standby by explicit human owner decision
- Raised: 2026-08-10 (`DEC-20260810-C5EA4F`).
- Status: **on hold**, not killed. A complete, primary-source-verified
  draft exists (`experiments/drafts/nfse-mei-guide-draft-v1.md`). The
  human owner chose not to proceed toward publication: "não tenho
  conhecimentos suficientes para garantir que não cometeríamos erros no
  conteúdo." This is a risk-tolerance decision on regulated content, not a
  finding that the opportunity itself was weak — see
  `context/knowledge/lessons.md` for the generalized lesson.
- Why it matters: a future AI session should not restart this from zero,
  and should not assume it was rejected on evidence — the research and
  draft remain valid reference material if the human owner ever revisits
  it, or if the same underlying pattern (narrow, timely, non-crowded gap)
  is found again in a lower-liability, non-regulated content category.
- What would resolve it: the human owner explicitly reopening it, or a
  different candidate in the same pattern but without compliance/legal
  stakes.

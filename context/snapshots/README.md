# Snapshots

Point-in-time copies of `context/CURRENT_STATE.md` (and, when useful, the ledger
and index files) preserved for cold-context review and to support future
equity-high-water-mark / drawdown tracking (see the open question in
`context/knowledge/open-questions.md`).

## When to snapshot

- Before a material system change (in addition to git history).
- At the start of a periodic system audit (`EVALUATION_CRITIC_SYSTEM.md` Level 3).
- At a milestone defined in `ROADMAP.md`.

## Naming

`YYYY-MM-DDTHHMM-<reason-slug>.md` (copy of `CURRENT_STATE.md` at that time).

## Current state

Empty. No snapshot has been taken yet (Phase 0, repository just initialized).
Git history is the primary rollback mechanism today; snapshots here are a
human/AI-readable convenience on top of it, not a replacement for it.

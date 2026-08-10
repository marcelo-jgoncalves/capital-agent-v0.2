# AI / Tool Adapters

The repository core is intentionally vendor-neutral.

Adapters may help a particular AI model, CLI, IDE or orchestration system discover
and execute the canonical instructions. They must remain thin compatibility layers.

Rules:

1. Do not duplicate the complete policy inside an adapter.
2. Point to `AI_OPERATING_MANUAL.md` and the canonical policy/state files.
3. Do not introduce weaker rules than the canonical core.
4. Provider-specific features are optional optimizations, never required for
   continuity of the experiment.
5. If changing AI systems, the new system should be able to reconstruct state from
   the repository and journals.

Examples of possible adapters:
- an `AGENTS.md` discovery file;
- an IDE-specific instruction file;
- a model-specific bootstrap prompt;
- a generic shell wrapper invoking the selected AI CLI;
- an AI Provider Adapter under `ai_providers/` (see `ai_providers/README.md`)
  that lets `scheduler/`'s queued jobs be dispatched to whichever reasoning
  environment is configured.

## Financial data adapters (read-only only)

If a future adapter exposes read-only access to balances, positions,
statements or order history for reconciliation (`ARCHITECTURE.md` "Financial
data adapters"), the same rules apply plus one more that is not negotiable:
it must declare and enforce a read-only access mode and must never expose a
write operation (`buy`/`sell`/`transfer`/`withdraw`/`place_order`/
`cancel_order`). There is no configuration flag anywhere in this repository
that promotes a read-only credential to write access — that is a deliberate
architectural gap, not an oversight, per the custody invariant in
`AI_OPERATING_MANUAL.md`.

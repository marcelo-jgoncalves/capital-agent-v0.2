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
- a generic shell wrapper invoking the selected AI CLI.

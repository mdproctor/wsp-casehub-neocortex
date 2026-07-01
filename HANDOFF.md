# Handoff — 2026-07-01

## What Changed

Closed #57 (rename neural-text → neocortex), #58 (CBR spec update), #59 (reconstructCase). Closed #46 (SPLADE tuning — dead, BGE-M3 replaced it). Merged #56 (memory backend migration) into the rename branch — both landed on main together. All 28 module artifactIds now carry `neocortex-` prefix, all Java packages under `io.casehub.neocortex.*`, parent repo fully updated (CI, docs, dependency management).

Consumer issues filed: engine#627 (casehub engine — 2 artifacts), engine#628 (Hortora engine — 8 artifacts).

Parent repo committed directly to main: pom.xml deps, aggregator.xml, CI workflows, PLATFORM.md, all docs.

## Immediate Next Step

**⚠️ Post-merge coordinated steps — do these before any other work:**

1. `gh repo rename neocortex --repo casehubio/neural-text`
2. `mv ~/claude/casehub/neural-text ~/claude/casehub/neocortex`
3. `mv ~/claude/public/casehub/neural-text ~/claude/public/casehub/neocortex`
4. Update git remotes in both repos (origin + upstream → neocortex URLs)
5. Recreate `wksp` and `proj` symlinks with new paths
6. `mv ~/.claude/projects/-Users-mdproctor-claude-casehub-neural-text ~/.claude/projects/-Users-mdproctor-claude-casehub-neocortex`
7. Close neural-text project in IntelliJ, re-open from `~/claude/casehub/neocortex`

**⚠️ Drop #56 from pause stack** — its content merged via #57. The pause stack still has it. Remove it so `work-start` doesn't offer to resume a branch whose work already landed.

**⚠️ Drop #46 from pause stack** — closed (SPLADE tuning dead). Same reason.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| engine#627 | Update engine memory-api imports for neocortex rename | S | Low | 2 POM lines, 3 Java files |
| engine#628 | Update Hortora engine imports for neocortex rename | S | Low | 8 POM lines, 20 Java files |
| #39 | Dedicated RelevanceEvaluator model — CRAG accuracy | L | High | R&D |
| #29 | ColBERT late interaction retrieval | L | High | ONNX export + MaxSim |

## Key References

- Blog: `blog/2026-07-01-mdp01-the-rename-that-touched-everything.md`
- Parent commit: `67ab09b7` (refactor: rename neural-text → neocortex across parent repo)
- Plan: `~/.claude/plans/jolly-wondering-wind.md`

# Handoff — 2026-07-02

## What Changed

Completed CbrCase type hierarchy (#66). Added `PlanCbrCase` + `PlanTrace` to memory-api, default `features()` method on `CbrCase` interface, all backends updated (inmem, Qdrant). 4 new contract tests (16 total). Per-app CBR integration guides in `docs/cbr/` for DevTown, AML, Clinical, and Engine. Landed on main as `997feb5`.

Cleaned up platform memory issues: closed platform #28, #29, #30, #40 — Mem0 and Graphiti already implemented here; Memori consolidated into neocortex #65 (blocked on upstream API).

## Immediate Next Step

**⚠️ Post-merge coordinated steps from previous session are still pending:**

1. `gh repo rename neocortex --repo casehubio/neural-text`
2. `mv ~/claude/casehub/neural-text ~/claude/casehub/neocortex`
3. `mv ~/claude/public/casehub/neural-text ~/claude/public/casehub/neocortex`
4. Update git remotes in both repos (origin + upstream → neocortex URLs)
5. Recreate `wksp` and `proj` symlinks with new paths
6. `mv ~/.claude/projects/-Users-mdproctor-claude-casehub-neural-text ~/.claude/projects/-Users-mdproctor-claude-casehub-neocortex`
7. Close neural-text project in IntelliJ, re-open from `~/claude/casehub/neocortex`

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on Memori shipping stable REST API
- #63 — Run code-domain embedding evaluation (Layers 1–4) + write REPORT.md · M · Med · venv and models ready

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached, ~30min CPU |
| #39 | Dedicated RelevanceEvaluator model — CRAG accuracy | L | High | R&D |
| #29 | ColBERT late interaction retrieval | L | High | ONNX export + MaxSim |

## Key References

- CBR guides: `docs/cbr/` (project)
- CBR paradigms: `specs/issue-20-cbr-retrieval-architecture/2026-06-30-cbr-paradigms-and-analysis.md` (workspace)
- Evaluation scripts: `evaluation/code_domain_embeddings/` (project)

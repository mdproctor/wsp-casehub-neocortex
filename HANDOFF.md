# Handoff — 2026-07-02

## What Changed

Built the code-domain embedding evaluation harness (#49). Four Python scripts covering Layers 1–4 (tokenizer analysis, embedding discrimination, 14-scenario benchmark, deployment feasibility). 58 unit tests. All 6 candidate model weights downloaded and cached. Execution deferred to #63. Design spec reviewed adversarially (24 issues, all resolved, $14.78). Landed on main as `ea5b32b`.

engine#627 and engine#628 (rename consumer updates) — done in a separate engine session.

Pause stack cleared — #46 (closed) and #56 (merged via #57) removed.

## Immediate Next Step

**⚠️ Post-merge coordinated steps from last session are still pending:**

1. `gh repo rename neocortex --repo casehubio/neural-text`
2. `mv ~/claude/casehub/neural-text ~/claude/casehub/neocortex`
3. `mv ~/claude/public/casehub/neural-text ~/claude/public/casehub/neocortex`
4. Update git remotes in both repos (origin + upstream → neocortex URLs)
5. Recreate `wksp` and `proj` symlinks with new paths
6. `mv ~/.claude/projects/-Users-mdproctor-claude-casehub-neural-text ~/.claude/projects/-Users-mdproctor-claude-casehub-neocortex`
7. Close neural-text project in IntelliJ, re-open from `~/claude/casehub/neocortex`

## What's Left

- #63 — Run code-domain embedding evaluation (Layers 1–4) + write REPORT.md · M · Med · venv and models ready, just needs execution time

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached, ~30min CPU |
| #39 | Dedicated RelevanceEvaluator model — CRAG accuracy | L | High | R&D |
| #29 | ColBERT late interaction retrieval | L | High | ONNX export + MaxSim |

## Key References

- Spec: `specs/2026-07-02-code-domain-embedding-evaluation-design.md` (workspace)
- Plan: `plans/2026-07-02-code-domain-embedding-evaluation.md` (workspace)
- Evaluation scripts: `evaluation/code_domain_embeddings/` (project)
- Venv: `evaluation/code_domain_embeddings/.venv/`

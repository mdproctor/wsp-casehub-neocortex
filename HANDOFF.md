# Handoff — 2026-06-18

## What Changed

Closed #36 — made rag modules consumable without `CurrentPrincipal`. `TenantGuard` strategy captures the deployment-time tenancy decision once at CDI producer time — no scattered null-guards. Bean producers use `Instance<CurrentPrincipal>`; implementation constructors are now package-private. ARC42STORIES updated across 12 sections to reflect the Hortora boundary shift (L6/L7 → shared). Cross-repo: casehubio/parent#272 filed for PLATFORM.MD deep-dive update; engine#521 clarified as not relevant to Hortora.

## Immediate Next Step

Pick from remaining backlog — all items are discretionary. Run `/work` to start.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #29 | ColBERT late interaction retrieval — inference-colbert module | L | High | New retrieval mode, ONNX export + MaxSim scoring |
| #30 | BGE-M3 single-model multi-mode (dense + sparse + ColBERT) | L | High | Replaces separate embedding + SPLADE pipeline |
| #31 | Matryoshka embeddings + binary quantization for tiered search | M | Med | Qdrant already supports binary vectors |
| #32 | HyDE — hypothetical document embeddings for query expansion | S | Med | RAG-layer pre-retrieval stage |
| #33 | Corrective RAG (CRAG) — self-healing retrieval | M | Med | Lightweight evaluator model on ONNX |
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Deferred until second consumer materialises |
| #20 | CaseRetriever CBR contract — feature vector, similarity | L | High | Design questions open; depends on engine TBD |
| #12 | Migrate Qdrant hybrid search to LangChain4j | M | Low | Blocked on external LangChain4j #4994 |

## Key References

- Spec: `specs/2026-06-17-hortora-integration-gaps-design.md`
- Plan: `plans/attic/issue-36-hortora-integration-gaps/2026-06-18-hortora-integration-gaps.md`
- Cross-repo: casehubio/parent#272 (PLATFORM.MD deep-dive update)
- Blog: `blog/2026-06-18-mdp12-guard-that-isnt-a-guard.md`

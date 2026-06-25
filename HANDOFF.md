# Handoff — 2026-06-25

*Updated: casehubio/parent#306 and hortora/engine#20 closed — removed from cross-module.*

## What Changed

Closed `issue-43-step-back-multi-query-expander` — #43 (step-back prompting) and #42 (multi-query HyDE) merged, squashed (23→6 commits), pushed to fork and blessed repo. Issues closed.

Key changes: `QueryExpander` SPI returns `List<RetrievalQuery>`. `rag-hyde` → `rag-expansion` (module, package, classes, config). `RrfFusion` utility in `rag-api`. Multi-query fan-out + RRF merge in decorators. `StepBackQueryExpander` + `hypotheticalCount` on `LlmQueryExpander`. Filed #45 (parallel LLM calls).

## Immediate Next Step

Pick from backlog — run `/work` to start.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #45 | Parallel LLM calls for multi-query HyDE | S | Med | Blocked on async ChatModel API |
| #39 | Dedicated RelevanceEvaluator model — CRAG accuracy | L | High | R&D |
| #29 | ColBERT late interaction retrieval | L | High | ONNX export + MaxSim |
| #30 | BGE-M3 single-model multi-mode | L | High | Replaces separate embedding + SPLADE |
| #31 | Matryoshka embeddings + binary quantization | M | Med | Qdrant supports binary vectors |
| #22 | Extract corpus CDI to corpus-quarkus/ | M | Low | Deferred until second consumer |
| #20 | CaseRetriever CBR contract | L | High | Depends on engine TBD |
| #12 | Migrate Qdrant hybrid search to LangChain4j | M | Low | Blocked on LangChain4j #4994 |

## Key References

- Spec: `specs/issue-43-step-back-multi-query-expander/2026-06-25-query-expansion-redesign.md` (promoted to project `docs/specs/`)
- Blog: `blog/2026-06-25-mdp17-query-expansion-grows-up.md`
- Garden: `jvm/GE-20260625-85a3aa.md`, `tools/GE-20260625-6b49f5.md`

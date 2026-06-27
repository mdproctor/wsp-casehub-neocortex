# Handoff — 2026-06-27

## What Changed

Closed `issue-31-matryoshka-binary-quantization` — #31 (Matryoshka embeddings + Qdrant quantization). `MatryoshkaEmbeddingModel` decorator truncates and renormalizes embeddings. `DenseQuantization` enum configures binary/scalar quantization at collection creation. Search-time oversampling on dense prefetch. Reactive `denseDimension` bug fixed. 5 commits (post-squash), 15 files, all tests pass. Pushed to upstream.

## Immediate Next Step

Pick from backlog — run `/work` to start.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #45 | Parallel LLM calls for multi-query HyDE | S | Med | Blocked on async ChatModel API |
| #39 | Dedicated RelevanceEvaluator model — CRAG accuracy | L | High | R&D |
| #29 | ColBERT late interaction retrieval | L | High | ONNX export + MaxSim |
| #30 | BGE-M3 single-model multi-mode | L | High | Replaces separate embedding + SPLADE |
| #22 | Extract corpus CDI to corpus-quarkus/ | M | Low | Deferred until second consumer |
| #20 | CaseRetriever CBR contract | L | High | Depends on engine TBD |
| #12 | Migrate Qdrant hybrid search to LangChain4j | M | Low | Blocked on LangChain4j #4994 |

## Key References

- Spec: `docs/specs/issue-31-matryoshka-binary-quantization/2026-06-26-matryoshka-quantization-design.md`
- Blog: `blog/2026-06-27-mdp17-matryoshka-and-the-math-that-didnt-add-up.md`
- Garden: `intellij-platform/GE-20260627-fed7cf.md`, `jvm/GE-20260627-8b0fb8.md`

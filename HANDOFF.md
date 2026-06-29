# Handoff — 2026-06-29

## What Changed

Closed `issue-45-parallel-hyde-expansion` — #45 (parallel LLM calls for multi-query HyDE expansion). `LlmQueryExpander` now runs N `chatModel.chat()` calls concurrently via Java 21 virtual threads when `hypotheticalCount > 1`. Fast path for n=1 avoids executor overhead. Deterministic parallelism test via `CountDownLatch`. Updated #45 issue body to document that the original "async ChatModel API" blocker was already solved by the platform `agent-api` module — virtual threads chosen over AgentProvider dependency to avoid coupling rag-expansion to platform. 1 commit, 2 files, all tests pass. Pushed to upstream.

## Immediate Next Step

Pick from backlog — run `/work` to start.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #46 | SPLADE/reranker tuning for garden retrieval | ? | ? | Blocked on Hortora/engine#28 |
| #39 | Dedicated RelevanceEvaluator model — CRAG accuracy | L | High | R&D |
| #29 | ColBERT late interaction retrieval | L | High | ONNX export + MaxSim |
| #30 | BGE-M3 single-model multi-mode | L | High | Replaces separate embedding + SPLADE |
| #22 | Extract corpus CDI to corpus-quarkus/ | M | Low | Deferred until second consumer |
| #20 | CaseRetriever CBR contract | L | High | Depends on engine TBD |
| #12 | Migrate Qdrant hybrid search to LangChain4j | M | Low | Blocked on LangChain4j #4994 |

## Key References

- Platform Agent API: `casehub-platform/agent-api/` — reactive LLM primitives that unblocked #45's conceptual blocker
- Garden: GE-20260618-c4f95a (ClaudeAsyncClient.close() thread blocking — relevant context for Agent API concurrency)

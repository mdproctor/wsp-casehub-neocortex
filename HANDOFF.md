# Handoff — 2026-06-29

## What Changed

Closed `issue-47-qdrant-fulltext-index` — #47 (full-text index on content) and #50 (keyword indexes on sourceDocumentId and tenantId). `ensureCollection()` in both blocking and reactive ingestors now creates three payload indexes after collection creation: `TextIndexParams` (Word tokenizer, lowercase, BM25-enabling) on `content`, `KeywordIndexParams` on `sourceDocumentId` and `tenantId`. Lazy migration detects missing indexes on existing collections via `payload_schema` and adds them on next ingest. Type mismatch throws `IllegalStateException`. Design review (4 rounds, 15 issues) drove spec improvements: retrieval path motivation, camelCase limitation (#53 filed), type validation, concurrency semantics, metadata key collision (#54 filed). 1 garden entry submitted (GE-20260629-0a321f — Qdrant createCollectionAsync idempotency asymmetry).

## Immediate Next Step

Pick from backlog — run `/work` to start.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #48 | BM25 as third RRF prefetch leg | M | Med | Depends on #47 (done) — full-text index now exists |
| #53 | Word tokenizer camelCase limitation | S | Med | Mitigation options for partial identifier search |
| #54 | Metadata key collision with reserved payload fields | S | Low | Pre-existing; amplified by payload indexes |
| #46 | SPLADE/reranker tuning for garden retrieval | ? | ? | Blocked on Hortora/engine#28 |
| #39 | Dedicated RelevanceEvaluator model — CRAG accuracy | L | High | R&D |
| #29 | ColBERT late interaction retrieval | L | High | ONNX export + MaxSim |
| #30 | BGE-M3 single-model multi-mode | L | High | Replaces separate embedding + SPLADE |
| #22 | Extract corpus CDI to corpus-quarkus/ | M | Low | Deferred until second consumer |
| #20 | CaseRetriever CBR contract | L | High | Depends on engine TBD |
| #12 | Migrate Qdrant hybrid search to LangChain4j | M | Low | Blocked on LangChain4j #4994 |

## Key References

- Design spec: `specs/2026-06-29-qdrant-payload-indexes-design.md` (workspace)
- Garden: GE-20260629-0a321f (Qdrant createCollectionAsync idempotency asymmetry)
- Blog: `blog/2026-06-29-mdp01-index-qdrant-wont-build.md`

# Handoff — 2026-07-03

## What Changed

Implemented three S-sized CBR production readiness issues from epic #68. Qdrant CDI producer (#69) — apps adding `memory-qdrant` get a real backend automatically. notBefore temporal filtering (#72) — `_stored_at` timestamp stored and filtered. NumericRange tolerance matching (#73) — range queries instead of exact equality, plus fixed latent bug where InMemory never matched numeric features. Also fixed pre-existing memory-jpa broken build (missing H2 dep from #56 migration).

Code review caught a CDI ambiguity: `QdrantCbrBeanProducer` was producing an unqualified `QdrantClient` bean that would conflict with RAG's producer. Fixed by creating the client internally with `@PreDestroy` lifecycle.

Created the full epic #68 with 8 sub-issues. Closed #69, #72, #73. Landed on main as `3183786`.

## Immediate Next Step

Dense vector search (#70) is the next M-sized issue — switch from `scrollAsync` to `searchAsync` when `EmbeddingModel` is present. The embedding path exists at store time; retrieval just doesn't use it yet. After that, `minSimilarity` (#71) becomes trivially wireable.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on Memori shipping stable REST API
- #70 — Dense vector search on `problem()` text · M · Med
- #71 — Wire `minSimilarity` score threshold · XS · Low · blocked by #70
- #74 — Reconciliation job — reindex + orphan cleanup · M · Med

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #70 | Dense vector search — semantic similarity on problem() | M | Med | Embedding path exists at store time, retrieval needs searchAsync |
| #71 | minSimilarity threshold | XS | Low | Blocked by #70 |
| #74 | Reconciliation job | M | Med | Not blocking initial rollout |
| #58 | Update CBR spec to match code | S | Low | Spec-to-code divergences from implementation |
| #59 | reconstructCase type resolution ordering | S | Low | Strategy pattern for extensibility |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |

## Key References

- Garden entry: `GE-20260703-885029` — Qdrant ValueFactory.value(long) creates IntegerValue
- Epic: casehubio/neocortex#68

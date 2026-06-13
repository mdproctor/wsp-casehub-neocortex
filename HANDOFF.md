# Handoff — 2026-06-13

## What Changed

Closed #19 (L/Med — corpus ingestion bridge in `rag/`). `CorpusIngestionService` polls `ChangeSource`, reads via `CorpusReader`, extracts metadata (`MetadataExtractor` SPI → `ExtractionResult` with body+metadata separation), chunks via `DocumentSplitters.recursive()`, pushes to Qdrant via `EmbeddingIngestor`. Config-driven with `CursorStore` SPI for cursor persistence. Two-source binding discovery (config-driven + custom CDI). Also closed #21 (assertTenant 3-arg fix — 10 call sites, `RequestContextCheck` shared utility). Garden entry submitted (GE-20260613-1e5ba4 — EmbeddingModel≠TokenCountEstimator). Blog entry published (mdp08).

## Immediate Next Step

Pick next work from What's Next. `parent#214` and `parent#236` (platform doc sync) are low-effort trailing obligations that could be batched.

## What's Left

- parent#214 — sync PLATFORM.md + neural-text deep-dive for reactive SPIs + EmbeddingIngestor rename · S · Low
- parent#236 — sync PLATFORM.md + neural-text deep-dive for ingestion bridge · S · Low
- #22 — extract corpus CDI integration to `corpus-quarkus/` module (trigger: second consumer) · M · Low
- #23 — update parent spec config keys `casehub.rag.ingestion.corpora.*` · XS · Low
- ARC42STORIES.MD — add L8/L9 corpus layers + update for #19 ingestion bridge · S · Low

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #12 | Migrate Qdrant hybrid search to LangChain4j when #4994 ships | M | Low | Blocked on external LangChain4j PR |

## Key References

- Spec: `docs/specs/issue-19-corpus-ingestion-bridge/2026-06-13-corpus-ingestion-bridge-design.md`
- Blog: `blog/2026-06-13-mdp08-four-reviews-and-a-fake-class.md`
- Plan: `plans/attic/issue-19-corpus-ingestion-bridge/2026-06-13-corpus-ingestion-bridge.md`
- Garden: `GE-20260613-1e5ba4` (EmbeddingModel≠TokenCountEstimator), `GE-20260612-87d173` (ZIP hash ordering)

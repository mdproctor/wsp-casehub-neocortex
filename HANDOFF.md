# Handoff — 2026-06-15

## What Changed

Closed #25, #26, #23, #21 on a single branch (`issue-25-embeddingmodel-bean`). Key discovery: `langchain4j-embeddings` uses independent versioning from the main `langchain4j` library — version 1.14.1 doesn't exist; fixed to `1.0.0-beta5` with a separate property. Also: `CorpusTestSupport` API redesigned to accept `Path` (caller-owned lifecycle via `@TempDir`), `ExampleCorpus.FILES` extracted to deduplicate corpus file list, NliClassifier smoke tests aligned to DeBERTa indices, protocol PP-20260529-57cc3b scope extended to RAG adapters. Code review skill updated — all findings (warnings, notes) must now be fixed, not just criticals. Garden entry GE-20260615-0d2eda submitted. Blog entry mdp10 published.

## Immediate Next Step

Pick from remaining backlog — all items are discretionary, none urgent. Run `/work` to start.

## What's Left

- parent#247 — sync neural-text deep-dive for examples modules · XS · Low
- parent#214 — sync PLATFORM.md for reactive SPIs + EmbeddingIngestor rename · S · Low
- parent#236 — sync PLATFORM.MD for ingestion bridge · S · Low
- ARC42STORIES.MD — add L8/L9 corpus layers + update for #19 ingestion bridge · S · Low
- README.md — status section massively stale ("no source code yet", all epics 🔲) · S · Low

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Deferred until second consumer materialises |
| #20 | CaseRetriever CBR contract — feature vector, similarity | L | High | Design questions open; depends on engine TBD |
| #12 | Migrate Qdrant hybrid search to LangChain4j | M | Low | Blocked on external LangChain4j #4994 |

## Key References

- Blog: `blog/2026-06-15-mdp10-trailing-edges.md`
- Garden: `GE-20260615-0d2eda` (langchain4j-embeddings versioning)
- Garden: `GE-20260614-b94048` (SPLADE licensing), `GE-20260614-d9a38f` (Xenova gated exports)

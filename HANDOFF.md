# Handoff — 2026-06-12

## What Changed

Closed #15 (S/Low — assertTenant Mutiny-idiomatic wrapping, StubEmbeddingModel extraction, delete-reingest test) and #18 (XL/High — corpus-api + corpus modules). corpus-api provides CorpusStore, CorpusReader, ChangeSource, CorpusIntegrity SPIs with reactive variants. corpus implements them with Zip4j — rolling ZIPs, chain manifest, flat + composite modes, compaction, migration. 56 files, 136 tests, zero deps beyond Zip4j. CLAUDE.md updated with new module entries. Garden gotcha submitted (GE-20260612-87d173 — ZIP hash ordering). Blog entry published.

## Immediate Next Step

Run `/work` and start #19 — corpus ingestion bridge in `rag/`. Wires `ChangeSource` + `CorpusReader` to the existing embedding + Qdrant infrastructure. `MetadataExtractor` SPI, chunking config, cursor persistence, deletion sync. L/Med scope.

## What's Left

- parent#214 — sync PLATFORM.md + neural-text deep-dive for corpus modules + EmbeddingIngestor rename · S · Low
- ARC42STORIES.MD — add L8/L9 corpus layers to the layer taxonomy (§4) · S · Low

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #19 | Corpus ingestion bridge in rag/ — ChangeSource → chunk → embed → Qdrant | L | Med | Unblocked by #18 |
| #12 | Migrate Qdrant hybrid search to LangChain4j when #4994 ships | M | Low | Blocked on external LangChain4j PR |

## Key References

- Spec: `specs/2026-06-11-corpus-storage-module-design.md` (rev 5, approved)
- Blog: `blog/2026-06-12-mdp07-fifty-six-files-and-a-hash-bug.md`
- Plan: `plans/attic/issue-18-corpus-modules/2026-06-12-corpus-storage-modules.md`
- Garden: `GE-20260612-87d173` (ZIP hash ordering gotcha)
- Tracking: #19 (ingestion bridge), #16 (upstream annotation tracking)

# Handoff — 2026-06-12

## What Changed

Corpus storage module designed through 4 spec review rounds — ZIP-backed rolling archives with chain integrity, composite mode for forage integration, append-only with compaction. Spec approved (rev 5): `specs/2026-06-11-corpus-storage-module-design.md`. #17 (rename CorpusStore → EmbeddingIngestor) implemented and closed — 29 files, 12 class renames, all docs updated. Upstream quarkus-langchain4j epic decomposed (#2574–#2578). Tracking issue #16 created with 7 additional annotation candidates.

## Immediate Next Step

Run `/work` and start #18 — `corpus-api` + `corpus` modules. The spec is approved and ready for implementation planning via `writing-plans`. XL scope, expect a full session.

## What's Left

- parent#214 — sync PLATFORM.md + neural-text deep-dive for reactive gating property + EmbeddingIngestor rename · S · Low
- #15 — assertTenant Mutiny-idiomatic wrapping, delete-reingest test, StubEmbeddingModel extraction · S · Low

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #18 | corpus-api + corpus modules — ZIP-backed document storage | XL | High | Spec approved, ready for implementation |
| #19 | Corpus ingestion bridge in rag/ — ChangeSource → chunk → embed → Qdrant | L | Med | Blocked by #18 |
| #12 | Migrate Qdrant hybrid search to LangChain4j when #4994 ships | M | Low | Blocked on external LangChain4j PR |

## Key References

- Spec: `specs/2026-06-11-corpus-storage-module-design.md` (rev 5, approved)
- Blog: `blog/2026-06-12-mdp06-storage-layer-that-wasnt-there.md`
- Tracking: #16 (upstream annotation tracking), #18 (corpus modules), #19 (ingestion bridge)
- Upstream: quarkiverse/quarkus-langchain4j#2572 (epic), #2574–#2578 (child issues)

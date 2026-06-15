# Handoff — 2026-06-15

## What Changed

Closed #27 (ARC42STORIES.MD — L8/L9 corpus layers, C8/C9 chapters, J3 journey) and #28 (README.md stale status, missing modules, CLAUDE.md rag-tika gap). Code review caught 6 factual errors in the ARC42 layer entries — all API surface claims written from memory were wrong (method names, record fields, enum values). Doc sync found rag-tika missing from CLAUDE.md. Blog entry mdp11 written.

## Immediate Next Step

Pick from remaining backlog — all items are discretionary, none urgent. Run `/work` to start.

## What's Left

- parent#247 — sync neural-text deep-dive for examples modules · XS · Low
- parent#236 — sync PLATFORM.MD for ingestion bridge · S · Low

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Deferred until second consumer materialises |
| #20 | CaseRetriever CBR contract — feature vector, similarity | L | High | Design questions open; depends on engine TBD |
| #12 | Migrate Qdrant hybrid search to LangChain4j | M | Low | Blocked on external LangChain4j #4994 |

## Key References

- Blog: `blog/2026-06-15-mdp11-six-wrong-fields.md`
- Garden: `GE-20260615-0d2eda` (langchain4j-embeddings versioning)

# HANDOFF — casehub-neocortex

## Last Session

Completed **#788** (Corpus annotations — sticky-note annotations on corpus entries). Full lifecycle: brainstorming (2 decisions) → spec → implementation plan (4 tasks, 2 batches) → all tasks implemented. Queue advanced to #804.

**What was built:**
- **CorpusAnnotation** record in `corpus-management-api` — `(id, corpusId, entryId, agentId, type, text, Map<String,String> metadata, Instant createdAt)` with validation.
- **AnnotationTypes** constants — `QUALITY_FLAG`, `CONTRADICTION`, `STALENESS`, `NOTE`. String type field (SubgraphTypes pattern).
- **AnnotationStore** SPI in `corpus-management-api` — `add`, `remove`, `forEntry` (with optional type filter), `search` (FTS5), `removeForEntry`.
- **SqliteAnnotationStore** in `corpus-management` — own SQLite database via SqliteDataSourceFactory (zero contention with MindMap). FTS5 virtual table with sync triggers. 9 tests.
- **CorpusEntry audit fields** — `createdBy`, `createdAt`, `updatedBy`, `updatedAt` added to record. Backward-compatible 4-arg constructor. Flyway V3 migration. SqliteCorpusEntryStore persists and reads audit fields. 3 new tests.
- **CorpusApi MCP operations** — `annotate`, `annotations`, `searchAnnotations`, `removeAnnotation` added to CorpusApi interface and CorpusApiBean. Backward-compatible 4-arg constructor on CorpusApiBean preserved. 3 new MCP tests.

**115 tests pass** in corpus-management. All modules build clean including corpus-management-hortora.

## Immediate Next Step

Pick up **#804** (Research workspace methodology). Queue position 8/11.

## References

- `specs/issue-787-rich-document-ingestion/2026-11-05-corpus-annotations-design.md` — design spec for #788
- `specs/issue-787-rich-document-ingestion/decisions.md` — D8 + D9 decisions for #788
- `plans/2026-11-05-corpus-annotations.md` — implementation plan (4 tasks, 2 batches, all complete)
- `.plan` — queue: #804 (next), #810, #811, #812

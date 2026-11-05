# HANDOFF — casehub-neocortex

## Last Session

Completed **#802** (Phase 3 structural extraction — extract Hortora-specific corpus code to dedicated module). Full lifecycle: brainstorming (7 decisions) → spec → self-review → implementation plan (8 tasks, 4 batches) → all tasks implemented. Queue ready to advance to #788.

**What was built:**
- **ScoreModifier SPI** in `corpus-management-api` — `@FunctionalInterface` with `double multiplier(Map<String,String> metadata, Map<String,String> context)`. Replaces hardcoded temporal-decay and version-distance scoring in SearchResource.
- **TemporalDecayScoreModifier** and **VersionDistanceScoreModifier** — two built-in implementations in `corpus-management` with configurable half-lives and decay factors.
- **corpus-management-hortora** module — new Maven module at `io.casehub.neocortex.corpus.management.hortora`. Contains all garden-specific code extracted from `corpus-management`.
- **GardenCorpusApi** — garden-specific MCP domain (`neocortex/garden-corpus`) with entry detail, reindex, feedback, and outcome operations. Separate from generic `CorpusApi` (`neocortex/corpus`).
- **GardenCorpusApiBean** — implements GardenCorpusApi, wires CorpusIndexService + CorpusReindexService + CorpusOutcomeService.
- **GardenProvenanceExtension** — staleness/feedback methods extracted from ProvenanceStore with own Flyway migrations (`db/garden-provenance/`).
- **8 classes moved** to hortora: GardenMetadataExtractor, CorpusIndexService, BuiltInCorpusTypes, CorpusOutcomeService, EntryDetail, UnretrievedReport, StalenessReport, FeedbackContext.
- **SearchResource refactored** — accepts `List<ScoreModifier>`, `SearchScoringConfig` deleted.
- **SearchResult cleaned** — 5 garden-specific Jackson accessors removed (stalenessThreshold, tags, lastReviewed, author, verifiedOn).
- **GardenReindexService → CorpusReindexService** renamed.
- **CorpusApiBean simplified** — 4-param constructor (SearchResource, SearchProfileStore, ProvenanceStore, CorpusRef), no garden dependencies.

**128 tests pass** — 100 in corpus-management (no Hortora dependency), 28 in corpus-management-hortora. Full project BUILD SUCCESS.

## Immediate Next Step

Pick up **#788** (Corpus annotations — sticky-note annotations on corpus entries). M/High. Requires brainstorming — "significant unknowns, design required." Queue position 7/11.

## References

- `specs/issue-787-rich-document-ingestion/2026-11-05-hortora-extraction-design.md` — design spec for #802
- `specs/issue-787-rich-document-ingestion/decisions.md` — 7 decisions for #802
- `plans/2026-11-05-hortora-extraction.md` — implementation plan (8 tasks, 4 batches, all complete)
- `docs/specs/2026-11-04-corpus-domain-abstraction-audit.md` — audit (L1 resolved by #787, L7/L9/L10 resolved by #802)
- `.plan` — queue: #788 (next), #804, #810, #811, #812

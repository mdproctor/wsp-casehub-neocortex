# Decisions — #802 Phase 3 Structural Extraction

## D1: Module structure for Hortora extraction

**Choice:** Create new `corpus-management-hortora` Maven module. Hortora-specific code moves there; generic code stays in `corpus-management`.
**Alternatives:**
- Package boundaries only (`.impl.hortora` package) — simpler but consumers can't exclude Hortora code from classpath; fails acceptance criterion "depend on corpus-management without pulling in Hortora concepts"
- Inline cleanup only (rename garden references, don't move) — cosmetic, doesn't achieve structural separation
**Rationale:** The acceptance criteria explicitly require a non-Hortora consumer to depend on corpus-management-api + corpus-management without Hortora concepts. Only module separation achieves this.
**Trade-offs:** Another Maven module in the build. Tests that exercise Hortora-specific code need to live in the new module.
**Sources:** docs/specs/2026-11-04-corpus-domain-abstraction-audit.md (Phase 3 module structure), issue #802 acceptance criteria
**Exploration:** quick
**Status:** captured

## D2: CorpusApi MCP interface split

**Choice:** Split `CorpusApi` into generic (stays in `corpus-management`) and garden-specific (`GardenCorpusApi extends CorpusApi` in `corpus-management-hortora`). Generic keeps: search, adaptiveSearch, status, profiles, provenance. Garden-specific adds: entry detail, unretrieved, reindex, reindexEntry, deleteEntry, outcomeReport, recordOutcome, recordFeedback.
**Alternatives:**
- Move entire CorpusApi to Hortora module — simpler but MCP search/provenance only available with Hortora classpath
- Keep CorpusApi in place — CorpusApiBean still depends on garden classes, breaking clean separation
**Rationale:** Search and provenance are generic corpus operations. Entry detail (markdown body), staleness feedback, and GE-ID-based operations are garden-specific. Splitting lets non-Hortora consumers get a working MCP domain for corpus search without garden vocabulary.
**Trade-offs:** Two MCP domain interfaces. `GardenCorpusApi` must compose or delegate generic operations to `CorpusApi` implementation. `@McpDomain` annotation on `GardenCorpusApi` likely overrides/extends the base domain.
**Sources:** CorpusApi.java (current MCP domain), CorpusApiBean.java (garden-specific wiring)
**Exploration:** quick
**Status:** captured

## D3: ScoreModifier SPI design

**Choice:** `ScoreModifier` @FunctionalInterface in `corpus-management-api`: `double modify(SearchResult result, Map<String,String> context)`. Two built-in implementations in `corpus-management`: `TemporalDecayScoreModifier` (configurable half-lives per tier) and `VersionDistanceScoreModifier` (configurable decay factor/floor). `SearchResource` accepts `List<ScoreModifier>` and applies them composably.
**Alternatives:**
- Composite ScoringStrategy with named strategies — adds orchestrator layer for two strategies
- Keep inline, make configurable — simpler but other domains can't swap scoring logic
**Rationale:** @FunctionalInterface is composable and minimal. Consumers add/remove/replace modifiers via constructor injection. The hardcoded `TIER_HALF_LIVES` map becomes a constructor parameter on `TemporalDecayScoreModifier`, removing garden-specific constants from `SearchResource`.
**Trade-offs:** `ScoreModifier` receives `SearchResult` + context map — loose typing on context. Could use a typed context record instead, but Map is more extensible across domains.
**Sources:** SearchResource.java:162-246 (applyScoring, temporalDecayScore, versionScore), SearchScoringConfig.java
**Exploration:** quick
**Status:** captured

## D4: GardenReindexService disposition

**Choice:** Rename to `CorpusReindexService`, keep in generic `corpus-management` module.
**Alternatives:**
- Move to Hortora module as-is — requires Hortora classpath for any reindex
- Duplicate: generic + garden wrapper — over-engineered for a rename
**Rationale:** The implementation is domain-neutral (calls embeddingIngestor.listDocuments + resetAction callback). Only the name is garden-specific.
**Trade-offs:** None — pure rename.
**Sources:** GardenReindexService.java (functionally generic implementation)
**Exploration:** quick
**Status:** captured

## D5: Transcript code disposition

**Choice:** `TranscriptCorpusInitializer`, `InteractionContext`, `InteractionType`, `ActivityType` stay in generic `corpus-management` module.
**Alternatives:**
- Move to Hortora module — limits future consumers who could use transcript ingestion
- Create corpus-management-transcript module — module proliferation for 4 classes
**Rationale:** Transcript ingestion is agent-shaped, not Hortora-shaped. Any corpus consumer could use it for NPC dialogues, clinical encounters, etc. Already in impl (moved from API in Phase 2), not polluting the API surface.
**Trade-offs:** corpus-management keeps some agent-specific vocabulary in impl. Acceptable since these are not garden-specific.
**Sources:** Issue #801 (Phase 2 — moved these from API to impl)
**Depends on:** D1 (module structure determines where non-garden code lives)
**Exploration:** quick
**Status:** captured

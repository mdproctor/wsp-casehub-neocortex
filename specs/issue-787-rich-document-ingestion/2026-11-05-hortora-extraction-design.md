# Phase 3 Structural Extraction — Hortora-Specific Corpus Code

**Issue:** casehubio/neocortex#802
**Date:** 2026-11-05
**Status:** Design
**Parent epic:** casehubio/neocortex#789
**Audit reference:** docs/specs/2026-11-04-corpus-domain-abstraction-audit.md

## Summary

Extract Hortora-specific corpus code from `corpus-management` into a new `corpus-management-hortora` Maven module. Introduce a `ScoreModifier` SPI to replace hardcoded scoring strategies. Split the `CorpusApi` MCP interface so generic search/provenance operations are available without Hortora classpath.

After this work, a non-Hortora consumer can depend on `corpus-management-api` + `corpus-management` and get: corpus catalogue, entry store, federated search, provenance, search profiles, transcript ingestion, and configurable score modifiers — without any garden vocabulary, GE-ID patterns, or staleness tiers.

## Scope

**In scope (from audit):**
- L7: Extract `GardenMetadataExtractor` to Hortora module
- L10: Extract `CorpusIndexService` (GE-ID patterns) to Hortora module
- L9: Extract scoring strategies behind `ScoreModifier` SPI
- L1: Confirmed resolved by #787's cover document pattern — no further work

**Also in scope (discovered during design):**
- Split `CorpusApi` MCP interface (generic vs garden-specific)
- Move `BuiltInCorpusTypes`, `CorpusOutcomeService`, `StalenessReport`, `FeedbackContext` to Hortora module
- Rename `CorpusReindexService` → `CorpusReindexService`

**Out of scope:**
- `TranscriptCorpusInitializer`, `InteractionContext`, `InteractionType`, `ActivityType` — stay in generic module (agent-shaped, not garden-shaped)
- `ProvenanceStore` — generic (`ProvenanceTracker` SPI implementation)
- `SearchProfileStore` — generic BOM version profiles
- `CoverDocumentGenerator`/`CoverDocumentParser` — generic cover document handling
- `CorpusEntryPromoter` — generic MindMap promotion

## Module Structure

### Before

```
corpus-management-api/     SPIs (clean from Phase 1+2)
corpus-management/         Runtime (mixed generic + Hortora)
corpus-management-parsers/ Document parsers (from #787)
```

### After

```
corpus-management-api/         SPIs + NEW ScoreModifier SPI
corpus-management/             Generic runtime only
corpus-management-hortora/     Hortora-specific code
corpus-management-parsers/     Document parsers (unchanged)
```

### Dependency direction

```
corpus-management-hortora → corpus-management → corpus-management-api
                                               ↘ rag-api (MetadataExtractor SPI)
                                               ↘ sqlite-support
```

## Detailed Design

### 1. ScoreModifier SPI (corpus-management-api)

New `@FunctionalInterface` in `io.casehub.neocortex.corpus.management`:

```java
@FunctionalInterface
public interface ScoreModifier {
    double multiplier(Map<String, String> metadata, Map<String, String> context);
}
```

Parameters:
- `metadata` — per-result metadata from the retrieved chunk
- `context` — query-level context (e.g., BOM versions for version scoring)

Returns a multiplier in (0.0, 1.0] applied to the score. Returns 1.0 for no modification. The modifier does not need the current score — it computes a decay factor from metadata and context only.

### 2. Built-in ScoreModifier implementations (corpus-management)

**TemporalDecayScoreModifier:**
- Constructor takes `Map<Integer, Duration> tierHalfLives` and `Duration defaultHalfLife`
- Reads `submitted` and `decay_tier` from result metadata
- Applies exponential half-life decay: `exp(-ln2 * daysSince / halfLife.toDays())`
- Default tier half-lives match current behavior: {0→730d, 1→365d, 2→180d, 3→90d}

**VersionDistanceScoreModifier:**
- Constructor takes `double decayFactor` and `double floor`
- Reads `verified_on` from result metadata, parses `stack:version` format
- Computes version distance and applies: `max(floor, pow(decayFactor, distance))`
- Default values match current: decayFactor=0.03, floor=0.5

### 3. SearchResource refactoring (corpus-management)

Current `applyScoring()` has hardcoded temporal/version logic. Refactored to:

```java
// Constructor accepts List<ScoreModifier>
public SearchResource(..., List<ScoreModifier> scoreModifiers) { ... }

// applyScoring uses the modifier list
List<SearchResult> applyScoring(List<SearchResult> results, String queryText, Map<String, String> bom) {
    if (scoreModifiers.isEmpty()) return results;
    return results.stream().map(r -> {
        if (r.metadata() == null) return r;
        double multiplier = 1.0;
        for (ScoreModifier mod : scoreModifiers) {
            multiplier *= mod.multiplier(r.metadata(), bom);
        }
        if (multiplier >= 0.999) return r;
        Double adjustedCe = r.crossEncoderScore() != null ? r.crossEncoderScore() * multiplier : null;
        return r.withAdjustedScores(r.relevance() * multiplier, adjustedCe);
    }).toList();
}
```

Remove: `TIER_HALF_LIVES`, `temporalDecayScore()`, `versionScore()`, `versionDistance()`, `parseVersion()` static methods.
Remove: `SearchScoringConfig` entirely — all 5 fields (`temporalDecayEnabled`/`versionScoringEnabled`/`versionDecayFactor`/`versionDecayFloor`/`versionTopicWeightDefault`) are absorbed by ScoreModifier constructor parameters. The remaining `scoreBoostWeight` already lives on `SearchConfig`.

### 4. SearchResult garden accessor cleanup

`SearchResult` currently has 5 Jackson-serialized convenience accessors that project garden-specific metadata keys: `stalenessThreshold()`, `tags()`, `lastReviewed()`, `author()`, `verifiedOn()`. These are garden vocabulary on a "generic" record.

**Fix:** Remove these accessors from `SearchResult`. Consumers read the metadata map directly. The `GardenCorpusApi` MCP layer in the Hortora module can format garden-specific fields in its response if needed, or the MCP tool descriptions can document which metadata keys are available.

The `seeAlsoIds` field (GE-ID cross-references) also moves to garden-specific handling — the `expandWithAdjacent()` method in `SearchResource` that uses it stays generic (it works on any `seeAlsoIds` list), but the population of `seeAlsoIds` from `see_also_ids` metadata is a garden convention documented by `GardenMetadataExtractor`.

### 5. CorpusApi split

**Generic CorpusApi (stays in corpus-management):**

```java
@McpDomain(value = "neocortex/corpus", app = "neocortex",
        summary = "Corpus search, provenance, and profile management")
public interface CorpusApi {
    List<SearchResult> search(...);
    AdaptiveResult adaptiveSearch(...);
    CorpusStatus status(String corpusId);
    String profile(String name);
    List<String> profiles();
    void saveProfile(String name, String stack);
    boolean deleteProfile(String name);
    List<ProvenanceRecord> forwardLineage(String issueRepo, Integer issueNumber);
    List<ProvenanceRecord> reverseLineage(String entryId);
    ProvenanceStats provenanceStats();
    int recordProvenance(...);
}
```

**GardenCorpusApi (corpus-management-hortora):**

```java
@McpDomain(value = "neocortex/garden-corpus", app = "neocortex",
        summary = "Garden-specific corpus operations — entry detail, reindex, feedback, outcomes")
public interface GardenCorpusApi {
    EntryDetail entry(String corpusId, String entryId);
    UnretrievedReport unretrieved(String corpusId, Integer minDays, Integer staleDays);
    CorpusReindexService.ReindexResult reindex(String corpusId);
    String reindexEntry(String corpusId, String entryId);
    String deleteEntry(String corpusId, String entryId);
    String outcomeReport();
    String recordOutcome(...);
    String recordFeedback(...);
}
```

Note: `GardenCorpusApi` does not extend `CorpusApi` — they are separate MCP domains. The generic operations are available via `CorpusApi`; garden-specific ones via `GardenCorpusApi`. Both are available when `corpus-management-hortora` is on the classpath.

### 6. ProvenanceStore — garden method extraction

`ProvenanceStore` implements the generic `ProvenanceTracker` SPI and stays in `corpus-management`. However, it has garden-specific methods bolted on: `recordFeedbackContext()`, `findFeedbackContext()`, `recordStaleness()`, `findStalenessReports()`, `findAllStalenessReports()`. These methods and their backing tables (`feedback_context`, `staleness_reports`) are garden-specific.

**Fix:** Extract garden-specific methods into a `GardenProvenanceExtension` class in `corpus-management-hortora`. It takes the same `DataSource` and provides staleness/feedback operations. The Flyway migration scripts `V2__staleness_reports.sql` and `V3__feedback_context.sql` move to the Hortora module under a separate Flyway location (e.g., `classpath:db/garden-provenance`). `GardenProvenanceExtension` runs its own Flyway migration on construction.

The core `ProvenanceStore` keeps only: `record()`, `forwardLineage()`, `reverseLineage()`, `stats()`, `purgeOlderThan()`, `deleteAll()` — the `ProvenanceTracker` SPI methods plus the domain-specific overloads.

### 7. Implementation classes — what moves where

**Moves to `corpus-management-hortora`:**

| Class | Reason |
|-------|--------|
| `GardenMetadataExtractor` | YAML frontmatter + GE-ID patterns (L7) |
| `CorpusIndexService` | GE-ID regex, `.md` assumptions, GE-ID date parsing (L10) |
| `BuiltInCorpusTypes` | `KNOWLEDGE_GARDEN`, `RESEARCH`, `TRANSCRIPT` constants |
| `CorpusOutcomeService` | CBR-backed outcome tracking wired to garden entries |
| `GardenCorpusApi` | NEW — garden-specific MCP interface |
| `GardenCorpusApiBean` | NEW — implements GardenCorpusApi |
| `StalenessReport` | Garden-specific value type |
| `FeedbackContext` | Garden-specific value type |
| `EntryDetail` | Garden entry detail (title, domain, type, seeAlso) |
| `UnretrievedReport` | Garden-specific unretrieved analysis |
| `GardenProvenanceExtension` | NEW — staleness/feedback methods extracted from ProvenanceStore |

**Stays in `corpus-management` (generic):**

| Class | Reason |
|-------|--------|
| `SearchResource` | Core search + federation (scoring refactored to SPI) |
| `SqliteCorpusCatalogue` | Generic catalogue |
| `SqliteCorpusEntryStore` | Generic entry store |
| `ChainWalkerFederatedSearch` | Generic federation walker |
| `HttpFederationWalker` | Generic HTTP federation |
| `ProvenanceStore` | Generic provenance (ProvenanceTracker SPI) |
| `CoverDocumentGenerator`/`Parser` | Generic cover documents |
| `CorpusEntryPromoter` | Generic MindMap promotion |
| `TranscriptCorpusInitializer` | Agent transcript ingestion |
| `InteractionContext`/`Type`/`ActivityType` | Agent interaction types |
| `FederationConfig`/`Parser` | Generic federation config |
| `RemoteCorpusClient` | Generic remote corpus client |
| `SearchProfileStore` | Generic BOM profiles |
| `CorpusReindexService` | Renamed from GardenReindexService |
| `CorpusStatus` | Generic status record |
| `SearchResult` | Generic search result |
| `AdaptiveResult` | Generic adaptive result |
| `CorpusApi` | Generic MCP interface (search, provenance, profiles) |
| `CorpusApiBean` | Simplified — implements generic CorpusApi only |

**Rename:**

| Before | After | Module |
|--------|-------|--------|
| `CorpusReindexService` | `CorpusReindexService` | corpus-management |

### 8. corpus-management-hortora module

**Maven coordinates:**
- artifactId: `casehub-neocortex-corpus-management-hortora`
- Package: `io.casehub.neocortex.corpus.management.hortora`

**Dependencies:**
- `casehub-neocortex-corpus-management` (compile)
- `casehub-neocortex-corpus-management-api` (transitive via above)
- `casehub-neocortex-rag-api` (transitive via corpus-management — for MetadataExtractor SPI)
- `casehub-neocortex-sqlite-support` (for GardenProvenanceExtension Flyway migrations)
- `casehub-neocortex-memory-api` (optional — for CorpusOutcomeService CbrRecordStore)
- `casehub-platform-api` (optional — for @McpDomain, @PlatformQuery)
- `org.yaml:snakeyaml` (for GardenMetadataExtractor YAML parsing)
- `junit-jupiter`, `assertj-core` (test)

**Test migration:**
- `CorpusIndexServiceTest` → moves to Hortora module
- `CorpusApiBeanTest` → splits: generic operation tests stay, garden-specific tests move
- `CorpusOutcomeServiceTest` → moves (if it exists)
- Other tests stay in corpus-management

### 9. CorpusApiBean simplification

Current `CorpusApiBean` implements the full `CorpusApi`. After the split:

**Generic `CorpusApiBean` (corpus-management):**
- Implements `CorpusApi` (generic interface)
- Constructor takes: `SearchResource`, `CorpusReindexService`, `SearchProfileStore`, `ProvenanceStore`
- Removes: `CorpusIndexService`, `CorpusOutcomeService` dependencies

**`GardenCorpusApiBean` (corpus-management-hortora):**
- Implements `GardenCorpusApi`
- Constructor takes: `CorpusIndexService`, `CorpusReindexService`, `CorpusOutcomeService`, `CorpusRef`, `Path corpusRoot`
- Provides garden-specific operations

## Testing Strategy

- Existing tests for generic classes remain in `corpus-management`
- Tests for moved classes move to `corpus-management-hortora`
- New tests for `ScoreModifier` implementations in `corpus-management`
- New tests for `GardenCorpusApiBean` in `corpus-management-hortora`
- Integration: verify that `corpus-management` builds and tests pass without Hortora module on classpath

## Migration Path

1. Create `ScoreModifier` SPI in `corpus-management-api`
2. Implement `TemporalDecayScoreModifier` and `VersionDistanceScoreModifier` in `corpus-management`
3. Refactor `SearchResource` to use `List<ScoreModifier>`, remove `SearchScoringConfig`
4. Strip garden-specific accessors from `SearchResult`
5. Create `corpus-management-hortora` module scaffold
6. Split `CorpusApi` → generic `CorpusApi` + `GardenCorpusApi`
7. Move Hortora-specific classes to the new module
8. Extract `GardenProvenanceExtension` from `ProvenanceStore`, move Flyway V2/V3 migrations
9. Rename `CorpusReindexService` → `CorpusReindexService`
10. Simplify `CorpusApiBean` — remove garden dependencies
11. Create `GardenCorpusApiBean` in Hortora module
12. Move/split tests
13. Verify `corpus-management` builds independently (no Hortora on classpath)

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking Hortora MCP tools | `GardenCorpusApi` preserves all existing garden operations |
| Missing dependencies in Hortora module | Build verification step (migration step 11) |
| `SearchResource` regression from scoring refactor | Existing search tests + new ScoreModifier unit tests |
| `CorpusApiBean` test split misses coverage | Run full test suite before and after, compare coverage |

## References

- docs/specs/2026-11-04-corpus-domain-abstraction-audit.md — L1, L7, L9, L10 remediation directions
- GardenMetadataExtractor.java — YAML frontmatter, GE-ID patterns
- CorpusIndexService.java — GE-ID regex, `.md` assumptions
- SearchResource.java:162-246 — temporalDecayScore, versionScore
- CorpusApi.java — current MCP domain interface
- CorpusApiBean.java — current facade implementation
- BuiltInCorpusTypes.java — garden-specific CorpusType constants
- CorpusOutcomeService.java — CBR outcome tracking
- Issue #801 — Phase 2 API fixes (moved InteractionContext/Type to impl)
- Issue #787 — Rich document ingestion (resolved L1 via cover document pattern)
- Issue #789 — Parent epic

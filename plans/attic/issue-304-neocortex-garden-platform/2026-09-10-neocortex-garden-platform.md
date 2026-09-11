# Knowledge Garden Platform Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #304 — Extract hortora/engine capabilities into neocortex
**Issue group:** #304 (casehubio/neocortex), #90 (Hortora/engine)

**Goal:** Extract generic RAG platform capabilities from hortora/engine into neocortex as reusable SPIs and modules, then thin engine to a deployment artifact.

**Architecture:** SPI-first extraction — define abstractions in rag-api, implement generic impls in new modules (rag-scoring, rag-query-augmentation), extend rag module with collection compatibility. CBR rename (PlanCbrCase → ResolvedCase, etc.) included. Engine thinning as final phase.

**Tech Stack:** Java 21, Quarkus 3.32.2, Maven, IntelliJ MCP for all code operations

## Global Constraints

- Java 21 source level, Java 26 JVM runtime
- All new SPIs in package `io.casehub.neocortex.rag` (rag-api)
- All new modules follow Maven coordinate pattern: `casehub-neocortex-rag-<name>`
- Parent POM version: `0.2-SNAPSHOT`, groupId: `io.casehub`
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl <module>`
- Use `ide_refactor_rename` for all renames — never bash mv/sed on .java files
- CBR_TYPE discriminator constants must NOT change (avoid data migration)
- `@DefaultBean` no-ops for all new SPIs (classpath activation pattern)
- Tests use JUnit 5 + AssertJ. No Mockito unless unavoidable.

---

## Batch 1: Scoring Foundation

SPIs and utility types in rag-api + pure-Java implementations in rag-scoring. After this batch, consumers can score retrieval results and apply adaptive filtering.

### Task 1: PostRetrievalScorer SPI + supporting types in rag-api

**Files:**
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/PostRetrievalScorer.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/ScoringContext.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/AdaptiveSearchConfig.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/AdaptiveFilter.java`
- Test: `rag-api/src/test/java/io/casehub/neocortex/rag/AdaptiveFilterTest.java`
- Test: `rag-api/src/test/java/io/casehub/neocortex/rag/AdaptiveSearchConfigTest.java`

**Interfaces:**
- Produces: `PostRetrievalScorer.adjust(RetrievedChunk, RetrievalQuery, ScoringContext) → double` — consumed by Task 2, 3
- Produces: `ScoringContext(Map<String,String> versionProfile)` with `ScoringContext.EMPTY` — consumed by Task 2
- Produces: `AdaptiveSearchConfig(scoreFloor, gapThreshold, minResults, overfetchMultiplier)` with `defaults()` — consumed by Task 3
- Produces: `AdaptiveFilter.filter(List<RetrievedChunk>, int requestedLimit, AdaptiveSearchConfig) → List<RetrievedChunk>` — consumed by Task 3, engine

- [ ] **Step 1: Write PostRetrievalScorer interface**

```java
package io.casehub.neocortex.rag;

public interface PostRetrievalScorer {
    double adjust(RetrievedChunk chunk, RetrievalQuery query, ScoringContext context);
}
```

- [ ] **Step 2: Write ScoringContext record**

```java
package io.casehub.neocortex.rag;

import java.util.Map;

public record ScoringContext(Map<String, String> versionProfile) {
    public static final ScoringContext EMPTY = new ScoringContext(Map.of());

    public ScoringContext {
        versionProfile = Map.copyOf(versionProfile);
    }
}
```

- [ ] **Step 3: Write AdaptiveSearchConfig record**

```java
package io.casehub.neocortex.rag;

public record AdaptiveSearchConfig(
    double scoreFloor,
    double gapThreshold,
    int minResults,
    double overfetchMultiplier
) {
    public AdaptiveSearchConfig {
        if (scoreFloor < 0 || scoreFloor > 1) throw new IllegalArgumentException("scoreFloor must be in [0,1]");
        if (gapThreshold < 0 || gapThreshold > 1) throw new IllegalArgumentException("gapThreshold must be in [0,1]");
        if (minResults < 0) throw new IllegalArgumentException("minResults must be >= 0");
        if (overfetchMultiplier < 1) throw new IllegalArgumentException("overfetchMultiplier must be >= 1");
    }

    public static AdaptiveSearchConfig defaults() {
        return new AdaptiveSearchConfig(0.3, 0.15, 3, 2.0);
    }
}
```

- [ ] **Step 4: Write failing tests for AdaptiveFilter**

Test: floor removes low scores, gap trim removes discontinuities, min results guarantees minimum, empty input returns empty.

- [ ] **Step 5: Implement AdaptiveFilter**

```java
package io.casehub.neocortex.rag;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public final class AdaptiveFilter {
    private AdaptiveFilter() {}

    public static List<RetrievedChunk> filter(List<RetrievedChunk> scored,
                                               int requestedLimit,
                                               AdaptiveSearchConfig config) {
        if (scored.isEmpty()) return List.of();
        var sorted = scored.stream()
            .sorted(Comparator.comparingDouble(RetrievedChunk::relevanceScore).reversed())
            .toList();

        // Floor: remove chunks below score floor
        var floored = new ArrayList<>(sorted.stream()
            .filter(c -> c.relevanceScore() >= config.scoreFloor())
            .toList());

        // Gap trim: find largest gap, trim after it
        for (int i = 1; i < floored.size(); i++) {
            double gap = floored.get(i - 1).relevanceScore() - floored.get(i).relevanceScore();
            if (gap >= config.gapThreshold()) {
                floored.subList(i, floored.size()).clear();
                break;
            }
        }

        // Min results: restore from sorted if below minimum
        if (floored.size() < config.minResults() && sorted.size() >= config.minResults()) {
            return sorted.subList(0, Math.min(config.minResults(), sorted.size()));
        }
        if (floored.size() < config.minResults()) {
            return sorted;
        }

        return floored.size() > requestedLimit
            ? floored.subList(0, requestedLimit)
            : floored;
    }
}
```

- [ ] **Step 6: Run tests, verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=AdaptiveFilterTest,AdaptiveSearchConfigTest`

- [ ] **Step 7: Commit**

```
feat(rag-api): PostRetrievalScorer SPI, ScoringContext, AdaptiveSearchConfig, AdaptiveFilter

Composable score multiplier SPI for post-retrieval scoring.
AdaptiveFilter provides standalone floor/gap-trim/min-results filtering.

Refs casehubio/neocortex#304
```

### Task 2: rag-scoring module — TemporalDecayScorer + VersionScorer

**Files:**
- Create: `rag-scoring/pom.xml`
- Create: `rag-scoring/src/main/java/io/casehub/neocortex/rag/scoring/TemporalDecayScorer.java`
- Create: `rag-scoring/src/main/java/io/casehub/neocortex/rag/scoring/VersionScorer.java`
- Modify: `pom.xml` (parent) — add `<module>rag-scoring</module>`
- Test: `rag-scoring/src/test/java/io/casehub/neocortex/rag/scoring/TemporalDecayScorerTest.java`
- Test: `rag-scoring/src/test/java/io/casehub/neocortex/rag/scoring/VersionScorerTest.java`

**Interfaces:**
- Consumes: `PostRetrievalScorer`, `ScoringContext`, `RetrievedChunk`, `RetrievalQuery` from rag-api
- Produces: `TemporalDecayScorer(String dateKey, String tierKey, Map<Integer,Duration> tierHalfLives)` — consumed by engine
- Produces: `VersionScorer(String versionKey, VersionScorer.Config config)` — consumed by engine
- Produces: `VersionScorer.Config(double decayFactor, double floor, double defaultTopicWeight)` — consumed by engine

- [ ] **Step 1: Create rag-scoring pom.xml**

Dependency on `casehub-neocortex-rag-api` only. Add `<module>rag-scoring</module>` to parent pom.xml alongside existing rag modules.

- [ ] **Step 2: Write failing tests for TemporalDecayScorer**

Test: fresh document (score ~1.0), old document (score < 1.0), configurable tier→halflife mapping, missing date returns 1.0, missing tier uses default.

- [ ] **Step 3: Implement TemporalDecayScorer**

Constructor takes `dateKey` (metadata key for date), `tierKey` (metadata key for decay tier), `Map<Integer, Duration> tierHalfLives` (tier → halflife mapping), and `Duration defaultHalfLife`. Reads `chunk.metadata().get(dateKey)` and `chunk.metadata().get(tierKey)`. Computes `Math.pow(0.5, age / halfLife.toMillis())`.

- [ ] **Step 4: Write failing tests for VersionScorer**

Test: exact version match (score ~1.0), minor version mismatch (small penalty), major version mismatch (large penalty), missing version returns 1.0, topic weight from query text.

- [ ] **Step 5: Implement VersionScorer**

Constructor takes `versionKey` (metadata key), `Config(decayFactor, floor, defaultTopicWeight)`. Reads `chunk.metadata().get(versionKey)` (format: `tech:version`), reference version from `context.versionProfile().get(tech)`, topic mention from `query.text()`.

- [ ] **Step 6: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-scoring`

- [ ] **Step 7: Commit**

```
feat(rag-scoring): TemporalDecayScorer and VersionScorer implementations

Pure-Java PostRetrievalScorer implementations with configurable metadata
key names and scoring parameters. No hardcoded field names.

Refs casehubio/neocortex#304
```

### Task 3: AdaptiveSearchWrapper in rag-scoring

**Files:**
- Create: `rag-scoring/src/main/java/io/casehub/neocortex/rag/scoring/AdaptiveSearchWrapper.java`
- Test: `rag-scoring/src/test/java/io/casehub/neocortex/rag/scoring/AdaptiveSearchWrapperTest.java`

**Interfaces:**
- Consumes: `CaseRetriever`, `PostRetrievalScorer`, `AdaptiveSearchConfig`, `AdaptiveFilter` from rag-api
- Produces: `AdaptiveSearchWrapper.search(RetrievalQuery, CorpusRef, int, ScoringContext) → List<RetrievedChunk>` — consumed by engine

- [ ] **Step 1: Write failing tests**

Test: overfetch multiplier applied, scorers adjust chunk scores, AdaptiveFilter applied to scored results, empty scorer list works, zero results from retriever returns empty.

- [ ] **Step 2: Implement AdaptiveSearchWrapper**

Takes `CaseRetriever`, `List<PostRetrievalScorer>`, `AdaptiveSearchConfig` in constructor. `search()` method: compute overfetch limit → `retriever.retrieve()` → apply each scorer via multiplication → `AdaptiveFilter.filter()` → return.

- [ ] **Step 3: Run tests, verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-scoring`

- [ ] **Step 4: Commit**

```
feat(rag-scoring): AdaptiveSearchWrapper — single-source scored retrieval

Composes CaseRetriever + PostRetrievalScorer chain + AdaptiveFilter
into a single search operation with overfetch, scoring, and trimming.

Refs casehubio/neocortex#304
```

---

## Batch 2: Platform SPIs

Remaining SPI interfaces in rag-api. No implementations in neocortex — engine provides the first implementations.

### Task 4: ProvenanceTracker SPI + records

**Files:**
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/ProvenanceTracker.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/ProvenanceRecord.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/ProvenanceStats.java`
- Test: `rag-api/src/test/java/io/casehub/neocortex/rag/ProvenanceRecordTest.java`

**Interfaces:**
- Produces: `ProvenanceTracker.record(retrievalContext, actionId, actionType, documentIds, recordedBy) → String` — consumed by engine
- Produces: `ProvenanceTracker.forwardLineage(actionId, actionType) → List<ProvenanceRecord>` — consumed by engine
- Produces: `ProvenanceTracker.reverseLineage(documentId) → List<ProvenanceRecord>` — consumed by engine
- Produces: `ProvenanceTracker.stats(retrievalContext) → ProvenanceStats` — consumed by engine
- Produces: `ProvenanceTracker.purgeOlderThan(Instant) → int` — consumed by engine

- [ ] **Step 1: Write ProvenanceTracker interface, ProvenanceRecord record, ProvenanceStats record**

ProvenanceRecord: `id`, `retrievalContext`, `actionId`, `actionType`, `documentId`, `recordedBy`, `timestamp`.

ProvenanceStats: `totalRecords`, `uniqueDocuments`, `uniqueActions`, `topReferenced` (List of `ProvenanceStats.DocumentRefCount(documentId, count)`), `unreferencedCount`.

- [ ] **Step 2: Write record validation tests**

Test: ProvenanceRecord immutability, ProvenanceStats computation correctness, null rejection.

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```
feat(rag-api): ProvenanceTracker SPI — document-to-action lineage tracking

Generic lineage tracking: which documents informed which downstream
actions. Parameters are deliberately generic for multi-domain use.

Refs casehubio/neocortex#304
```

### Task 5: FederationStrategy SPI + records

**Files:**
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/FederationStrategy.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/FederationQuery.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/FederatedResult.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/FederationTarget.java`
- Test: `rag-api/src/test/java/io/casehub/neocortex/rag/FederationQueryTest.java`

**Interfaces:**
- Produces: `FederationStrategy.federate(FederationQuery, List<FederatedResult> localResults) → List<FederatedResult>` — consumed by engine
- Produces: `FederationQuery(localId, queryText, maxResults, visited, filterContext)` — consumed by engine
- Produces: `FederatedResult(content, adjustedScore, sourceId, metadata)` — consumed by engine
- Produces: `FederationTarget(url, id, relationship)` — consumed by engine

- [ ] **Step 1: Write FederationStrategy interface and records**

FederationTarget: `url` (String), `id` (String), `relationship` (enum: UPSTREAM, PEER).

FederatedResult: `content` (String), `adjustedScore` (double), `sourceId` (String), `metadata` (Map<String,String>, optional — for audit, NOT re-scoring).

FederationQuery: `localId`, `queryText`, `maxResults`, `visited` (Set<String>), `filterContext` (Map<String, List<String>>). Compact constructor copies visited and filterContext defensively.

- [ ] **Step 2: Write record validation tests**

Test: FederationQuery visited set immutability, filterContext immutability, FederatedResult score range.

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```
feat(rag-api): FederationStrategy SPI — multi-instance retrieval

Single federate() method encapsulates topology discovery, remote query,
sufficiency checks, and result merge. Federation is routing, not decoration.

Refs casehubio/neocortex#304
```

### Task 6: DocumentQueryAugmenter SPI

**Files:**
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/DocumentQueryAugmenter.java`

**Interfaces:**
- Produces: `DocumentQueryAugmenter.generateQueries(title, body, path) → Optional<List<String>>` — consumed by Task 7

- [ ] **Step 1: Write DocumentQueryAugmenter interface**

```java
package io.casehub.neocortex.rag;

import java.util.List;
import java.util.Optional;

public interface DocumentQueryAugmenter {
    Optional<List<String>> generateQueries(String title, String body, String path);
}
```

- [ ] **Step 2: Commit**

```
feat(rag-api): DocumentQueryAugmenter SPI — ingest-time query generation

Distinct from QueryExpander (query-time). Enriches documents before
embedding so embeddings capture the queries the document answers.

Refs casehubio/neocortex#304
```

---

## Batch 3: Query Augmentation Module

### Task 7: rag-query-augmentation module

**Files:**
- Create: `rag-query-augmentation/pom.xml`
- Create: `rag-query-augmentation/src/main/java/io/casehub/neocortex/rag/augmentation/AgentQueryAugmenter.java`
- Create: `rag-query-augmentation/src/main/java/io/casehub/neocortex/rag/augmentation/QueryAugmentingMetadataExtractor.java`
- Modify: `pom.xml` (parent) — add `<module>rag-query-augmentation</module>`
- Test: `rag-query-augmentation/src/test/java/io/casehub/neocortex/rag/augmentation/AgentQueryAugmenterTest.java`
- Test: `rag-query-augmentation/src/test/java/io/casehub/neocortex/rag/augmentation/QueryAugmentingMetadataExtractorTest.java`

**Interfaces:**
- Consumes: `DocumentQueryAugmenter` from rag-api, `MetadataExtractor` from rag-api, `AgentProvider` from casehub-platform-agent-api
- Produces: `AgentQueryAugmenter` implements `DocumentQueryAugmenter` — consumed by engine
- Produces: `QueryAugmentingMetadataExtractor` @Decorator on `MetadataExtractor` — consumed by engine

- [ ] **Step 1: Create pom.xml**

Dependencies: `casehub-neocortex-rag-api`, `casehub-platform-agent-api` (provided scope — AgentProvider).

- [ ] **Step 2: Write failing tests for AgentQueryAugmenter**

Test: generates queries from title+body via ChatModel, returns Optional.empty() for short content, returns Optional.of(emptyList) when LLM returns nothing useful, null body handled.

- [ ] **Step 3: Implement AgentQueryAugmenter**

Uses `AgentProvider` to get `ChatModel`, prompts for search queries. Provider-agnostic.

- [ ] **Step 4: Write failing tests for QueryAugmentingMetadataExtractor**

Test: appends queries to content before delegating to wrapped extractor, passes through when augmenter returns empty.

- [ ] **Step 5: Implement QueryAugmentingMetadataExtractor**

`@Decorator @Priority(50)` on `MetadataExtractor`. Calls `DocumentQueryAugmenter.generateQueries()`, appends queries to content, delegates to wrapped extractor.

- [ ] **Step 6: Run tests, verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-query-augmentation`

- [ ] **Step 7: Commit**

```
feat(rag-query-augmentation): LLM query augmentation via AgentProvider

Ingest-time document enrichment with LLM-generated search queries.
Provider-agnostic — Ollama, OpenAI, or any other via AgentProvider config.

Refs casehubio/neocortex#304
```

---

## Batch 4: Collection Compatibility

### Task 8: CollectionCompatibility utility in rag module

**Files:**
- Create: `rag/src/main/java/io/casehub/neocortex/rag/runtime/CollectionCompatibility.java`
- Create: `rag/src/main/java/io/casehub/neocortex/rag/runtime/MigrationAction.java`
- Create: `rag/src/main/java/io/casehub/neocortex/rag/runtime/CollectionExpectedConfig.java`
- Test: `rag/src/test/java/io/casehub/neocortex/rag/runtime/CollectionCompatibilityTest.java`

**Interfaces:**
- Consumes: Qdrant client from existing rag module deps
- Produces: `CollectionCompatibility.check(QdrantClient, collectionName, CollectionExpectedConfig) → MigrationAction` — consumed by engine
- Produces: `MigrationAction` sealed interface: `Compatible`, `DimensionMismatch(actual, expected)`, `MissingSparseVectors`, `MissingColBert` — consumed by engine

- [ ] **Step 1: Write MigrationAction sealed interface and CollectionExpectedConfig record**

```java
public sealed interface MigrationAction {
    record Compatible() implements MigrationAction {}
    record DimensionMismatch(int actual, int expected) implements MigrationAction {}
    record MissingSparseVectors() implements MigrationAction {}
    record MissingColBert() implements MigrationAction {}
}

public record CollectionExpectedConfig(int denseDimension, boolean sparseEnabled, boolean colbertEnabled) {}
```

- [ ] **Step 2: Write failing tests for CollectionCompatibility**

Test: matching config returns Compatible, wrong dimension returns DimensionMismatch, missing sparse returns MissingSparseVectors, missing ColBERT returns MissingColBert.

Use mock or in-memory Qdrant client stub.

- [ ] **Step 3: Implement CollectionCompatibility.check()**

Queries Qdrant collection info, compares against expected config.

- [ ] **Step 4: Run tests, verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=CollectionCompatibilityTest`

- [ ] **Step 5: Commit**

```
feat(rag): CollectionCompatibility — generic collection migration checks

Checks dimension, sparse vector, and ColBERT config against expected.
Returns MigrationAction sealed type. Policy (what to do) left to caller.

Refs casehubio/neocortex#304
```

---

## Batch 5: CBR Rename

Clean break — all consumers update in the same commit. IntelliJ refactor rename handles all 305 references.

### Task 9: Rename CBR types via IntelliJ

**Files:**
- Rename: `PlanCbrCase` → `ResolvedCase` (use `ide_refactor_rename`, 106 refs)
- Rename: `TextualCbrCase` → `ResolutionGuide` (use `ide_refactor_rename`, 104 refs)
- Rename: `PlanTrace` → `ResolutionStep` (use `ide_refactor_rename`, 95 refs)

**Interfaces:**
- Produces: `ResolvedCase` (was PlanCbrCase), `ResolutionGuide` (was TextualCbrCase), `ResolutionStep` (was PlanTrace)
- CBR_TYPE constants unchanged: `ResolvedCase.CBR_TYPE = "plan"`, `ResolutionGuide.CBR_TYPE = "textual"`

- [ ] **Step 1: Rename PlanCbrCase → ResolvedCase**

Use `ide_refactor_rename` on `../../memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ResolvedCase.java/PlanCbrCase.java`. Verify all 106 references updated.

- [ ] **Step 2: Rename TextualCbrCase → ResolutionGuide**

Use `ide_refactor_rename` on `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/TextualCbrCase.java`. Verify all 104 references updated.

- [ ] **Step 3: Rename PlanTrace → ResolutionStep**

Use `ide_refactor_rename` on `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/PlanTrace.java`. Verify all 95 references updated.

- [ ] **Step 4: Verify CBR_TYPE constants unchanged**

Check `ResolvedCase.CBR_TYPE` is still `"plan"` and `ResolutionGuide.CBR_TYPE` is still `"textual"`.

- [ ] **Step 5: Run full build to verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Then: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test`

- [ ] **Step 6: Commit**

```
refactor(memory-api): CBR rename — PlanCbrCase → ResolvedCase, TextualCbrCase → ResolutionGuide

PlanTrace → ResolutionStep. CBR_TYPE discriminator constants unchanged
("plan", "textual") — no data migration needed. Clean break, no aliases.

Refs casehubio/neocortex#304
```

### Task 10: CbrOutcome.retrievalId + documentation

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrOutcome.java` — add optional `retrievalId`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrOutcomeTest.java` — test retrievalId
- Modify: `docs/cbr/cbr-types.md` — update type names
- Modify: `docs/cbr/README.md` — update type names
- Modify: `docs/cbr/guide-engine.md` — update type names
- Modify: `docs/guides/consumer-guide.md` — update type names
- Modify: `docs/guides/contributor-guide.md` — update type names
- Modify: `docs/guides/cognitive-types-guide.md` — update type names

**Interfaces:**
- Consumes: `CbrOutcome` from memory-api
- Produces: `CbrOutcome` with new optional `retrievalId` field — consumed by engine

- [ ] **Step 1: Add retrievalId to CbrOutcome**

Add `String retrievalId` as a nullable field. Use `ide_edit_member` to add the field to the record. Verify existing constructors still work (if record, add new canonical constructor with retrievalId + convenience constructor without).

- [ ] **Step 2: Write test for retrievalId round-trip**

Test: create CbrOutcome with retrievalId, verify it round-trips.

- [ ] **Step 3: Update documentation**

Update CBR docs: replace PlanCbrCase/TextualCbrCase/PlanTrace with new names. Document retrievalId in CbrOutcome.

- [ ] **Step 4: Run tests, verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api`

- [ ] **Step 5: Commit**

```
feat(memory-api): CbrOutcome.retrievalId for retrieval-to-outcome correlation

Optional field linking execution outcome back to the retrieval event.
Also updates CBR documentation for renamed types.

Refs casehubio/neocortex#304
```

---

## Batch 6: Engine Integration

Engine implements new SPIs, uses rag-scoring, strips extracted code.

### Task 11: Engine uses rag-scoring — delete extracted scorers

**Files:**
- Modify: `engine/pom.xml` — add `casehub-neocortex-rag-scoring` dependency
- Delete: `engine/src/main/java/io/hortora/garden/search/TemporalDecayScorer.java` (use `ide_refactor_safe_delete`)
- Delete: `engine/src/main/java/io/hortora/garden/search/VersionScorer.java` (use `ide_refactor_safe_delete`)
- Delete: `engine/src/test/java/io/hortora/garden/search/TemporalDecayScorerTest.java`
- Delete: `engine/src/test/java/io/hortora/garden/search/VersionScorerTest.java`
- Modify: `engine/src/main/java/io/hortora/garden/search/SearchResource.java` — use platform TemporalDecayScorer/VersionScorer + AdaptiveSearchWrapper/AdaptiveFilter

**Interfaces:**
- Consumes: `TemporalDecayScorer`, `VersionScorer`, `AdaptiveSearchWrapper`, `AdaptiveFilter` from rag-scoring/rag-api

- [ ] **Step 1: Add rag-scoring dependency to engine pom.xml**

- [ ] **Step 2: Update SearchResource imports to use platform scorers**

Replace `io.hortora.garden.search.TemporalDecayScorer` with `io.casehub.neocortex.rag.scoring.TemporalDecayScorer`. Same for VersionScorer. Construct with metadata key names from garden config.

- [ ] **Step 3: Delete engine's TemporalDecayScorer and VersionScorer**

Use `ide_refactor_safe_delete`. Verify no remaining references.

- [ ] **Step 4: Update SearchResource to use AdaptiveFilter for post-federation filtering**

- [ ] **Step 5: Delete engine scorer tests (covered by rag-scoring tests now)**

- [ ] **Step 6: Run engine tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -f engine/pom.xml`

- [ ] **Step 7: Commit**

```
refactor(engine): use platform rag-scoring — delete extracted scorers

TemporalDecayScorer and VersionScorer now from neocortex rag-scoring.
SearchResource uses AdaptiveFilter for post-federation result trimming.

Refs Hortora/engine#90, casehubio/neocortex#304
```

### Task 12: Engine uses CollectionCompatibility + implements SPIs

**Files:**
- Modify: `engine/src/main/java/io/hortora/garden/inference/CollectionMigration.java` — use `CollectionCompatibility.check()` for generic checks, keep deployment policy
- Modify: `engine/src/main/java/io/hortora/garden/provenance/ProvenanceStore.java` — implement `ProvenanceTracker`
- Modify: `engine/src/main/java/io/hortora/garden/federation/ChainWalker.java` — implement `FederationStrategy`

**Interfaces:**
- Consumes: `CollectionCompatibility`, `MigrationAction` from rag
- Consumes: `ProvenanceTracker` from rag-api
- Consumes: `FederationStrategy`, `FederationQuery`, `FederatedResult` from rag-api

- [ ] **Step 1: Update CollectionMigration to use CollectionCompatibility.check()**

Extract generic checks to platform utility call. Keep engine's deployment policy (reindex on incompatibility, cursor reset).

- [ ] **Step 2: ProvenanceStore implements ProvenanceTracker**

Add `implements ProvenanceTracker`. Map generic parameters to domain-specific schema: `retrievalContext` → issueRepo, `actionId` → issueNumber, etc.

- [ ] **Step 3: ChainWalker implements FederationStrategy**

Add `implements FederationStrategy`. Implement `federate(FederationQuery, List<FederatedResult>)` delegating to existing `walk()` method. Map FederationQuery/FederatedResult to existing SearchResult types.

- [ ] **Step 4: Run engine tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -f engine/pom.xml`

- [ ] **Step 5: Commit**

```
refactor(engine): implement ProvenanceTracker + FederationStrategy SPIs, use CollectionCompatibility

Engine now implements platform SPIs while keeping domain-specific logic.
CollectionMigration delegates generic checks to platform utility.

Refs Hortora/engine#90, casehubio/neocortex#304
```

### Task 13: Engine CBR rename + verification + docs

**Files:**
- Modify: all engine `.java` files referencing `PlanCbrCase`, `TextualCbrCase`, `PlanTrace` — update to `ResolvedCase`, `ResolutionGuide`, `ResolutionStep`
- Modify: `engine/CLAUDE.md` — update architecture description
- Modify: `engine/docs/` — update references

- [ ] **Step 1: Update engine imports to use renamed types**

Use `ide_find_references` to find all occurrences, then update imports. `ResolvedCase`, `ResolutionGuide`, `ResolutionStep` from `io.casehub.neocortex.memory.cbr`.

- [ ] **Step 2: Verify MCP tools work**

Run engine integration tests. Verify `gardenSearch`, `gardenFeedback`, `gardenRecordOutcome`, `gardenRecordProvenance` MCP tools still produce correct results.

- [ ] **Step 3: Update engine CLAUDE.md**

Document new neocortex dependencies, removed code, SPI implementations.

- [ ] **Step 4: Verify soredium skills**

Run soredium skill tests if available. Verify garden tools still work.

- [ ] **Step 5: Run full engine build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -f engine/pom.xml`

- [ ] **Step 6: Commit**

```
refactor(engine): complete thinning — CBR rename, verify MCP tools, update docs

Engine is now a thin deployment: neocortex deps + config + MCP tools +
domain-specific SPI implementations. ~1K LOC removed.

Closes Hortora/engine#90
Refs casehubio/neocortex#304
```

---

## References

- [2026-09-10-neocortex-garden-platform-design.md] — design spec this plan implements
- [decisions.md] — 12 validated design decisions
- casehubio/neocortex#304 — extraction issue (neocortex side)
- Hortora/engine#90 — extraction issue (engine side)
- `rag-api/src/main/java/io/casehub/neocortex/rag/CaseRetriever.java` — existing retrieval SPI
- `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalTracker.java` — existing tracking SPI
- `rag-api/src/main/java/io/casehub/neocortex/rag/MetadataExtractor.java` — existing extraction SPI
- `../../memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ResolvedCase.java/PlanCbrCase.java` (106 refs) — CBR rename source
- `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/TextualCbrCase.java` (104 refs) — CBR rename source
- `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/PlanTrace.java` (95 refs) — CBR rename source
- `rag-crossencoder/pom.xml` — module template
- casehub/garden/docs/protocols/universal/module-tier-structure.md
- casehub/garden/docs/protocols/universal/cdi-classpath-presence-requires-module-separation.md

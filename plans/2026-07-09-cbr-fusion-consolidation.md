# CBR Fusion Consolidation + SPLADE/BM25 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #124 — Consolidate RrfFusion with generic ScoreFusion
**Issue group:** #124, #123, #122

**Goal:** Extract fusion algorithms to a shared module, migrate all callers, then add SPLADE and BM25 retrieval legs to CBR hybrid retrieval.

**Architecture:** New `fusion-api` Tier 1 module hosts `ScoreFusion`, unified `FusionStrategy`, and `CamelCaseExpander`. RAG callers migrate from `RrfFusion`/`ConvexCombinationFusion` to `ScoreFusion`. CBR gains SPLADE (via `SparseEmbedder`) and BM25 (via Qdrant server-side inference) as optional fusion legs with config-driven activation.

**Tech Stack:** Java 21, Qdrant Java client, inference-splade (SparseEmbedder), Maven multi-module

## Global Constraints

- Java 21 language level on Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- All commits reference an issue
- Per `spi-signature-change-all-impls-same-commit`: CbrQuery type change + all callers in one commit
- IntelliJ MCP for all code navigation and refactoring
- Pre-release stage — breaking changes cost nothing

---

### Task 1: Create fusion-api Module + Move ScoreFusion

**Files:**
- Create: `fusion-api/pom.xml`
- Create: `fusion-api/src/main/java/io/casehub/neocortex/fusion/ScoreFusion.java`
- Create: `fusion-api/src/main/java/io/casehub/neocortex/fusion/FusionStrategy.java`
- Create: `fusion-api/src/test/java/io/casehub/neocortex/fusion/ScoreFusionTest.java`
- Modify: `pom.xml` (parent — add module + dependencyManagement entry)
- Delete: `memory-api/src/main/java/io/casehub/neocortex/memory/ScoreFusion.java`
- Delete: `memory-api/src/test/java/io/casehub/neocortex/memory/ScoreFusionTest.java`
- Modify: `memory-api/pom.xml` (add fusion-api dependency)
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java` (import path)

**Interfaces:**
- Produces: `io.casehub.neocortex.fusion.ScoreFusion` (same API as current `io.casehub.neocortex.memory.ScoreFusion`)
- Produces: `io.casehub.neocortex.fusion.FusionStrategy { RRF, DBSF, CC }`

- [ ] **Step 1: Create fusion-api/pom.xml**

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>
  <artifactId>casehub-neocortex-fusion-api</artifactId>
  <name>CaseHub Neocortex - Fusion API</name>
  <description>Score fusion algorithms (RRF, Convex Combination) and FusionStrategy enum. Tier 1 pure Java, zero deps.</description>
  <dependencies>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.assertj</groupId>
      <artifactId>assertj-core</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

- [ ] **Step 2: Create FusionStrategy enum**

```java
package io.casehub.neocortex.fusion;

public enum FusionStrategy { RRF, DBSF, CC }
```

- [ ] **Step 3: Copy ScoreFusion to fusion-api with new package**

Copy `memory-api/src/main/java/io/casehub/neocortex/memory/ScoreFusion.java` to `fusion-api/src/main/java/io/casehub/neocortex/fusion/ScoreFusion.java`. Change package declaration to `io.casehub.neocortex.fusion`.

- [ ] **Step 4: Copy ScoreFusionTest to fusion-api with new package**

Copy `memory-api/src/test/java/io/casehub/neocortex/memory/ScoreFusionTest.java` to `fusion-api/src/test/java/io/casehub/neocortex/fusion/ScoreFusionTest.java`. Change package and imports.

- [ ] **Step 5: Add fusion-api to parent pom.xml**

Add `<module>fusion-api</module>` before `<module>rag-api</module>` in the modules list. Add a `<dependency>` entry in `<dependencyManagement>`:

```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-fusion-api</artifactId>
  <version>${project.version}</version>
</dependency>
```

- [ ] **Step 6: Add fusion-api dependency to memory-api/pom.xml**

```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-fusion-api</artifactId>
</dependency>
```

- [ ] **Step 7: Delete old ScoreFusion from memory-api**

Use `ide_refactor_safe_delete` for `memory-api/src/main/java/io/casehub/neocortex/memory/ScoreFusion.java`. Delete `memory-api/src/test/java/io/casehub/neocortex/memory/ScoreFusionTest.java`.

- [ ] **Step 8: Update QdrantCbrCaseMemoryStore import**

Change `import io.casehub.neocortex.memory.ScoreFusion` to `import io.casehub.neocortex.fusion.ScoreFusion` in `QdrantCbrCaseMemoryStore.java`.

- [ ] **Step 9: Build fusion-api + memory-api + memory-qdrant**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl fusion-api,memory-api,memory-qdrant -am`
Expected: BUILD SUCCESS, all ScoreFusionTest tests pass in fusion-api.

- [ ] **Step 10: Commit**

```
feat(#124): extract fusion-api module — ScoreFusion + FusionStrategy

New Tier 1 module casehub-neocortex-fusion-api hosts ScoreFusion
(moved from memory-api) and unified FusionStrategy enum. Zero
first-party deps, pure Java.
```

---

### Task 2: Unify CbrFusionStrategy → FusionStrategy (Atomic SPI Change)

Per the `spi-signature-change-all-impls-same-commit` protocol, all callers of `CbrFusionStrategy` must update atomically.

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrQuery.java` (field type + all withers)
- Delete: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFusionStrategy.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrQueryTest.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/CbrQueryTranslatorTest.java`
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`

**Interfaces:**
- Consumes: `io.casehub.neocortex.fusion.FusionStrategy` from Task 1
- Produces: Updated `CbrQuery` record with `FusionStrategy fusionStrategy` field

- [ ] **Step 1: Update CbrQuery record**

In `CbrQuery.java`:
- Change `import io.casehub.neocortex.memory.cbr.CbrFusionStrategy` to `import io.casehub.neocortex.fusion.FusionStrategy`
- Change field `CbrFusionStrategy fusionStrategy` → `FusionStrategy fusionStrategy`
- Change default in `of()`: `CbrFusionStrategy.RRF` → `FusionStrategy.RRF`
- Change `withFusionStrategy` parameter type: `CbrFusionStrategy` → `FusionStrategy`

- [ ] **Step 2: Update QdrantCbrCaseMemoryStore**

In `retrieveHybrid()`:
- Replace `CbrFusionStrategy.RRF` with `FusionStrategy.RRF`
- Add DBSF guard: `case DBSF -> throw new UnsupportedOperationException("DBSF is not supported for CBR — use RRF or CC")`
- Change the `if/else` on fusionStrategy to a `switch` with exhaustive cases

- [ ] **Step 3: Update all test files**

Replace all `CbrFusionStrategy.RRF` → `FusionStrategy.RRF` and `CbrFusionStrategy.CC` → `FusionStrategy.CC` in:
- `CbrQueryTest.java`
- `CbrQueryTranslatorTest.java`
- `CbrCaseMemoryStoreContractTest.java`

- [ ] **Step 4: Delete CbrFusionStrategy**

Use `ide_refactor_safe_delete` for `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFusionStrategy.java`.

- [ ] **Step 5: Build and test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl memory-api,memory-testing,memory-qdrant,memory-cbr-inmem,memory-cbr-embedding,memory-cbr-crossencoder -am`
Expected: BUILD SUCCESS

- [ ] **Step 6: Commit**

```
feat(#124): unify CbrFusionStrategy → FusionStrategy (atomic SPI change)

CbrQuery.fusionStrategy field type changes from CbrFusionStrategy to
the shared FusionStrategy enum. DBSF guard throws
UnsupportedOperationException in CBR. All callers updated atomically
per spi-signature-change-all-impls-same-commit protocol.
```

---

### Task 3: Migrate RAG Callers — Remove RrfFusion + ConvexCombinationFusion

**Files:**
- Modify: `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievedChunk.java` (add fusionKey + withRelevanceScore)
- Modify: `rag-expansion/pom.xml` (add fusion-api dependency)
- Modify: `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/QueryExpandingCaseRetriever.java`
- Modify: `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/ReactiveQueryExpandingCaseRetriever.java`
- Modify: `rag/pom.xml` (add fusion-api dependency)
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/HybridCaseRetriever.java`
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/ReactiveHybridCaseRetriever.java`
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/RagConfig.java`
- Modify: `rag/src/test/java/io/casehub/neocortex/rag/runtime/RagTestFixtures.java`
- Delete: `rag-api/src/main/java/io/casehub/neocortex/rag/RrfFusion.java`
- Delete: `rag-api/src/main/java/io/casehub/neocortex/rag/ConvexCombinationFusion.java`
- Delete: `rag-api/src/main/java/io/casehub/neocortex/rag/FusionStrategy.java`
- Delete: `rag-api/src/test/java/io/casehub/neocortex/rag/RrfFusionTest.java`
- Delete: `rag-api/src/test/java/io/casehub/neocortex/rag/ConvexCombinationFusionTest.java`
- Modify: `memory-qdrant/pom.xml` (remove unused rag-api dependency)

**Interfaces:**
- Consumes: `ScoreFusion.rrf()`, `ScoreFusion.convexCombination()`, `FusionStrategy` from Task 1
- Produces: `RetrievedChunk.fusionKey()`, `RetrievedChunk.withRelevanceScore(double)`

- [ ] **Step 1: Add fusionKey() and withRelevanceScore() to RetrievedChunk**

Use `ide_insert_member` to add to `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievedChunk.java`:

```java
public String fusionKey() {
    return sourceDocumentId + "\0" + content;
}

public RetrievedChunk withRelevanceScore(double score) {
    return new RetrievedChunk(content, sourceDocumentId, score, metadata, grade);
}
```

- [ ] **Step 2: Add fusion-api dependencies to rag-expansion/pom.xml and rag/pom.xml**

```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-fusion-api</artifactId>
</dependency>
```

- [ ] **Step 3: Migrate QueryExpandingCaseRetriever**

Replace the `RrfFusion.fuse(resultSets, maxResults)` call with:

```java
List<ScoreFusion.ScoredLeg<RetrievedChunk>> legs = resultSets.stream()
    .map(rs -> new ScoreFusion.ScoredLeg<>(rs, RetrievedChunk::relevanceScore, 1.0))
    .toList();
return ScoreFusion.rrf(legs, RetrievedChunk::fusionKey, maxResults, 60)
    .stream().map(f -> f.item().withRelevanceScore(f.score())).toList();
```

Remove `import io.casehub.neocortex.rag.RrfFusion`. Add `import io.casehub.neocortex.fusion.ScoreFusion`.

- [ ] **Step 4: Migrate ReactiveQueryExpandingCaseRetriever**

Same pattern as Step 3 inside the `.with(resultSets -> { ... })` combinator.

- [ ] **Step 5: Migrate HybridCaseRetriever — FusionStrategy import + CC path**

Change `import io.casehub.neocortex.rag.FusionStrategy` to `import io.casehub.neocortex.fusion.FusionStrategy`.
Change `import io.casehub.neocortex.rag.ConvexCombinationFusion` to `import io.casehub.neocortex.fusion.ScoreFusion`.
In `executeConvexCombinationFusion()`: replace `ConvexCombinationFusion.ScoredLeg` with `ScoreFusion.ScoredLeg<RetrievedChunk>`, replace `ConvexCombinationFusion.fuse(legs, maxResults)` with `ScoreFusion.convexCombination(legs, RetrievedChunk::fusionKey, maxResults).stream().map(f -> f.item().withRelevanceScore(f.score())).toList()`.

- [ ] **Step 6: Migrate ReactiveHybridCaseRetriever — same as Step 5**

- [ ] **Step 7: Migrate RagConfig + RagTestFixtures**

Change FusionStrategy import to `io.casehub.neocortex.fusion.FusionStrategy`.

- [ ] **Step 8: Delete old fusion classes from rag-api**

Use `ide_refactor_safe_delete` for:
- `rag-api/src/main/java/io/casehub/neocortex/rag/RrfFusion.java`
- `rag-api/src/main/java/io/casehub/neocortex/rag/ConvexCombinationFusion.java`
- `rag-api/src/main/java/io/casehub/neocortex/rag/FusionStrategy.java`

Delete test files:
- `rag-api/src/test/java/io/casehub/neocortex/rag/RrfFusionTest.java`
- `rag-api/src/test/java/io/casehub/neocortex/rag/ConvexCombinationFusionTest.java`

- [ ] **Step 9: Remove unused rag-api dependency from memory-qdrant/pom.xml**

Remove the `casehub-neocortex-rag-api` dependency — memory-qdrant imports nothing from rag-api.

- [ ] **Step 10: Build full project**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS — all existing tests pass

- [ ] **Step 11: Commit**

```
feat(#124): migrate RAG callers to ScoreFusion — remove RrfFusion, ConvexCombinationFusion

QueryExpandingCaseRetriever and HybridCaseRetriever now use
ScoreFusion from fusion-api. RrfFusion, ConvexCombinationFusion,
and rag-api FusionStrategy deleted. RetrievedChunk gains
fusionKey() and withRelevanceScore(). Unused rag-api dependency
removed from memory-qdrant.
```

---

### Task 4: Move CamelCaseExpander to fusion-api

**Files:**
- Create: `fusion-api/src/main/java/io/casehub/neocortex/fusion/CamelCaseExpander.java`
- Create: `fusion-api/src/test/java/io/casehub/neocortex/fusion/CamelCaseExpanderTest.java`
- Delete: `rag/src/main/java/io/casehub/neocortex/rag/runtime/CamelCaseExpander.java`
- Delete: `rag/src/test/java/io/casehub/neocortex/rag/runtime/CamelCaseExpanderTest.java`
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/HybridCaseRetriever.java` (import)
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/ReactiveHybridCaseRetriever.java` (import)
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/QdrantPointBuilder.java` (import)

**Interfaces:**
- Produces: `io.casehub.neocortex.fusion.CamelCaseExpander.expand(String)` — public visibility

- [ ] **Step 1: Copy CamelCaseExpander to fusion-api**

Create `fusion-api/src/main/java/io/casehub/neocortex/fusion/CamelCaseExpander.java`. Change package to `io.casehub.neocortex.fusion`. Change visibility from `final class` to `public final class`, and `static String expand` to `public static String expand`.

- [ ] **Step 2: Copy CamelCaseExpanderTest to fusion-api**

Create test at `fusion-api/src/test/java/io/casehub/neocortex/fusion/CamelCaseExpanderTest.java`. Change package and imports.

- [ ] **Step 3: Update RAG callers**

Change imports in `HybridCaseRetriever.java`, `ReactiveHybridCaseRetriever.java`, `QdrantPointBuilder.java` from `io.casehub.neocortex.rag.runtime.CamelCaseExpander` to `io.casehub.neocortex.fusion.CamelCaseExpander`.

- [ ] **Step 4: Delete old CamelCaseExpander from rag**

Delete `rag/src/main/java/io/casehub/neocortex/rag/runtime/CamelCaseExpander.java` and its test.

- [ ] **Step 5: Build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl fusion-api,rag -am`
Expected: BUILD SUCCESS

- [ ] **Step 6: Commit**

```
refactor(#124): move CamelCaseExpander to fusion-api

Shared BM25 token pre-processing utility — used by both RAG
HybridCaseRetriever and (upcoming) CBR BM25 leg. Visibility
changed from package-private to public.
```

---

### Task 5: Add QdrantCbrConfig for SPLADE + BM25 + CC Weights

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrConfig.java`

**Interfaces:**
- Produces: `spladeEnabled()`, `spladeVectorName()`, `spladeTopK()`, `bm25Enabled()`, `bm25VectorName()`, `bm25Model()`, `bm25TopK()`, `ccWeights()` with sub-interface `CcWeightsConfig { dense(), sparse(), bm25() }`

- [ ] **Step 1: Write test for config defaults**

Create a test that verifies default values via Smallrye Config test harness, or verify manually after build.

- [ ] **Step 2: Add config properties to QdrantCbrConfig**

Use `ide_insert_member` to add to `QdrantCbrConfig.java`:

```java
@WithDefault("false")
boolean spladeEnabled();

@WithDefault("sparse")
String spladeVectorName();

@WithDefault("0")
int spladeTopK();

@WithDefault("false")
boolean bm25Enabled();

@WithDefault("bm25")
String bm25VectorName();

@WithDefault("Qdrant/bm25")
String bm25Model();

@WithDefault("0")
int bm25TopK();

CcWeightsConfig ccWeights();

interface CcWeightsConfig {
    @WithDefault("0.6")
    double dense();

    @WithDefault("0.2")
    double sparse();

    @WithDefault("0.2")
    double bm25();
}
```

Top-k defaults of 0 mean "use query.topK()" — the store reads `config.spladeTopK() > 0 ? config.spladeTopK() : query.topK()`.

- [ ] **Step 3: Build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl memory-qdrant -am`
Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```
feat(#123,#122): add QdrantCbrConfig properties for SPLADE, BM25, CC weights
```

---

### Task 6: Collection Schema Evolution — SPLADE + BM25 Vectors

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrCollectionManager.java`
- Test: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStoreTest.java`

**Interfaces:**
- Consumes: `QdrantCbrConfig.spladeEnabled()`, `spladeVectorName()`, `bm25Enabled()`, `bm25VectorName()`, `bm25Model()` from Task 5
- Produces: `ensureCollection()` that adds missing SPLADE/BM25 named vectors to existing collections

- [ ] **Step 1: Write failing test — collection gains sparse vector when SPLADE enabled**

In `QdrantCbrCaseMemoryStoreTest`, add a test that creates a collection (dense-only), then calls `ensureCollection` with SPLADE enabled config, and verifies the collection now has a sparse vector named `"sparse"`.

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — `ensureCollection` doesn't add sparse vectors yet.

- [ ] **Step 3: Implement schema evolution in CbrCollectionManager.ensureCollection()**

After the existing dimension-check block (where `knownCollections.add(collection); return;`), add checks for missing named vectors. If SPLADE is enabled and the collection lacks the sparse vector, call Qdrant `updateCollection` API to add it. Same for BM25. The BM25 vector is a `TextIndexParams` type with the configured model.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Write test — collection gains BM25 vector when enabled**

- [ ] **Step 6: Implement BM25 vector addition in ensureCollection()**

- [ ] **Step 7: Build and run full memory-qdrant tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory-qdrant -am`
Expected: BUILD SUCCESS

- [ ] **Step 8: Commit**

```
feat(#123,#122): collection schema evolution — add SPLADE/BM25 vectors to existing collections
```

---

### Task 7: SPLADE + BM25 Ingestion in CbrPointBuilder + store()

**Files:**
- Modify: `memory-qdrant/pom.xml` (add inference-splade dependency)
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrPointBuilder.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java` (constructor + store)
- Test: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/CbrPointBuilderTest.java`

**Interfaces:**
- Consumes: `SparseEmbedder.embed(String)` from inference-splade, `CamelCaseExpander.expand(String)` from Task 4
- Produces: `CbrPointBuilder.buildPoint()` with optional sparse + BM25 vectors

- [ ] **Step 1: Add inference-splade dependency to memory-qdrant/pom.xml**

```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-inference-splade</artifactId>
</dependency>
```

- [ ] **Step 2: Write failing test — buildPoint includes sparse vector**

Add test to `CbrPointBuilderTest` that verifies when a sparse embedding `Map<Integer, Float>` is provided, the resulting point has a sparse named vector.

- [ ] **Step 3: Extend CbrPointBuilder.buildPoint() signature**

Add parameters: `Map<Integer, Float> sparseEmbedding`, `String sparseVectorName`, `String bm25Text`, `String bm25VectorName`, `String bm25Model`. When sparseEmbedding is non-null, add a sparse named vector. When bm25Text is non-null, add a BM25 Document named vector.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Write test — buildPoint includes BM25 vector**

- [ ] **Step 6: Verify test passes**

- [ ] **Step 7: Update QdrantCbrCaseMemoryStore constructor — inject optional SparseEmbedder**

Add `Instance<SparseEmbedder> sparseEmbedderInstance` to the `@Inject` constructor. Resolve to field `this.sparseEmbedder`.

- [ ] **Step 8: Update store() to embed + pass sparse/BM25 to buildPoint**

In `store()`, before calling `CbrPointBuilder.buildPoint()`:
- If `sparseEmbedder != null && config.spladeEnabled()`: `sparseEmbedding = sparseEmbedder.embed(cbrCase.problem())`
- If `config.bm25Enabled()`: `bm25Text = CamelCaseExpander.expand(cbrCase.problem())`

Pass these to the updated `buildPoint()`.

- [ ] **Step 9: Build and test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory-qdrant -am`

- [ ] **Step 10: Commit**

```
feat(#123,#122): SPLADE + BM25 ingestion — CbrPointBuilder + store()
```

---

### Task 8: SPLADE + BM25 Retrieval Legs in retrieveHybrid()

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Test: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStoreTest.java`

**Interfaces:**
- Consumes: `SparseEmbedder.embed(String)`, `CamelCaseExpander.expand(String)`, `ScoreFusion.rrf()` / `ScoreFusion.convexCombination()`, `QdrantCbrConfig.ccWeights()`

- [ ] **Step 1: Write failing test — HYBRID with SPLADE returns results from sparse leg**

Store a case with SPLADE enabled. Query with a term that matches via SPLADE but has low dense similarity. Verify the case is returned in HYBRID mode.

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement SPLADE leg in retrieveHybrid()**

Add `executeSpladeSearch()` method: embeds `query.problem()` with SparseEmbedder, executes sparse vector query against the SPLADE named vector, returns `List<ScoredPoint>`.

In `retrieveHybrid()`:
- Call `executeSpladeSearch()` when sparseEmbedder is available and SPLADE is enabled
- Merge SPLADE points into `candidateMap` via `mergePoints(spladePoints, candidateMap, caseClass, false)`
- Build SPLADE `ScoredLeg` and add to legs list

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Write failing test — HYBRID with BM25 returns results from keyword leg**

Store a case with BM25 enabled. Query with exact keyword terms. Verify the case is returned.

- [ ] **Step 6: Implement BM25 leg in retrieveHybrid()**

Add `executeBm25Search()` method: pre-processes `query.problem()` with `CamelCaseExpander.expand()`, constructs `Document` query, executes against BM25 named vector, returns `List<ScoredPoint>`.

In `retrieveHybrid()`:
- Call `executeBm25Search()` when BM25 is enabled
- Merge BM25 points into `candidateMap`
- Build BM25 `ScoredLeg` and add to legs list

- [ ] **Step 7: Run test to verify it passes**

- [ ] **Step 8: Implement CC weight renormalization**

Update the fusion assembly in `retrieveHybrid()` to implement the weight model from §5 of the spec: feature weight = `1.0 - vectorWeight`, semantic sub-weights renormalized among active legs. Use `switch(fusionStrategy)` with explicit DBSF guard.

- [ ] **Step 9: Write test — CC weighting affects ranking**

Store cases with varying dense/sparse/keyword signals. Query with CC fusion and verify ordering matches the weight distribution.

- [ ] **Step 10: Write test — degradation — SPLADE unavailable skipped silently**

Config has SPLADE enabled but no SparseEmbedder injected. Verify HYBRID still returns results (dense + feature only).

- [ ] **Step 11: Write test — 4-leg retrieval (all legs active)**

Store case, enable all legs, query in HYBRID mode. Verify results returned.

- [ ] **Step 12: Build full project**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS

- [ ] **Step 13: Commit**

```
feat(#123,#122): SPLADE + BM25 retrieval legs in retrieveHybrid()

Dynamic 2-4 leg fusion in HYBRID mode. SPLADE via SparseEmbedder,
BM25 via Qdrant server-side inference. CC weight renormalization
preserves vectorWeight feature/semantic split. Graceful degradation
when legs unavailable.
```

---

### Task 9: Reconciliation Vector Enrichment Phase

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrReconciliationService.java`
- Test: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStoreTest.java`

**Interfaces:**
- Consumes: `SparseEmbedder`, `CamelCaseExpander`, `QdrantCbrConfig`

- [ ] **Step 1: Write failing test — enrichment backfills SPLADE vectors**

Store cases (dense only, SPLADE disabled). Enable SPLADE. Run reconciliation. Verify cases now have sparse vectors and SPLADE retrieval works.

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Add SparseEmbedder injection to CbrReconciliationService**

Add optional `Instance<SparseEmbedder>` to constructor, same pattern as QdrantCbrCaseMemoryStore.

- [ ] **Step 4: Implement vector enrichment phase in reconcile()**

After the existing orphan cleanup and reindex phases, add phase 3:
- Skip if neither SPLADE nor BM25 is configured
- Scroll all points in the collection for the tenant
- For each point missing the SPLADE named vector (when configured): reconstruct problem from payload, embed via SparseEmbedder, upsert with sparse vector
- For each point missing BM25 (when configured): reconstruct problem, expand with CamelCaseExpander, upsert with BM25 Document vector
- Batch upserts using existing page-based pattern
- Count enriched points in ReconciliationResult

- [ ] **Step 5: Run test to verify it passes**

- [ ] **Step 6: Write test — enrichment backfills BM25**

Same pattern as Step 1 but for BM25.

- [ ] **Step 7: Write test — enrichment is idempotent**

Run enrichment twice. Verify second run enriches 0 points.

- [ ] **Step 8: Build full project**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS

- [ ] **Step 9: Commit**

```
feat(#123,#122): reconciliation vector enrichment — backfill SPLADE/BM25

Three-phase reconciliation: orphan cleanup, reindex, vector
enrichment. Enrichment scrolls existing points and adds missing
SPLADE/BM25 vectors. Batch upserts, idempotent, count reported
in ReconciliationResult.
```

---

### Task 10: Update CLAUDE.md + ARC42STORIES.MD

**Files:**
- Modify: `CLAUDE.md` (add fusion-api module, update module structure, update maven coordinates)
- Modify: `ARC42STORIES.MD` (update §5 building block view for fusion-api)

- [ ] **Step 1: Update CLAUDE.md**

Add `fusion-api` to the module structure list:
```
fusion-api/         — ScoreFusion (RRF + CC algorithms), FusionStrategy enum, CamelCaseExpander. Tier 1 pure Java, zero deps. Shared by RAG and CBR.
```

Add maven coordinates:
```
| Fusion API | `casehub-neocortex-fusion-api` |
```

Add root Java package:
```
| Root Java package (fusion) | `io.casehub.neocortex.fusion` |
```

Update memory-api description to note ScoreFusion moved to fusion-api. Update rag-api description to note RrfFusion, ConvexCombinationFusion, FusionStrategy removed. Update memory-qdrant description to note SPLADE + BM25 legs.

- [ ] **Step 2: Update ARC42STORIES.MD §5**

Add fusion-api to the building block view.

- [ ] **Step 3: Commit**

```
docs(#124,#123,#122): update CLAUDE.md + ARC42STORIES.MD for fusion-api, SPLADE/BM25
```

---

## Self-Review

**Spec coverage:**
- §1 fusion-api module → Task 1
- §2 caller migration (CbrQuery + RAG) → Tasks 2, 3
- §3 SPLADE leg → Tasks 6, 7, 8
- §4 BM25 leg → Tasks 6, 7, 8
- §4a retrieveHybrid assembly → Task 8
- §5 CC weight model → Task 8
- §6 reconciliation + tests → Task 9
- CamelCaseExpander move → Task 4
- DBSF guard → Task 2
- RetrievedChunk methods → Task 3
- Atomic SPI change → Task 2
- Collection schema evolution → Task 6
- CLAUDE.md + ARC42 updates → Task 10

**Placeholder scan:** All steps have concrete code or commands. No TBD/TODO.

**Type consistency:** `FusionStrategy` used consistently across Tasks 1-3. `ScoreFusion.ScoredLeg` used in Tasks 3, 8. `CamelCaseExpander.expand()` used in Tasks 4, 7, 8, 9.

**Tooling safety:** No bash cp/mv/rm on source files. Deletions use `ide_refactor_safe_delete`. All code edits via IDE tools.

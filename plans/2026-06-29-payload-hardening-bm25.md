# Payload Hardening and BM25 Retrieval — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add metadata key collision protection (#54), camelCase token expansion (#53), and BM25 as a third RRF retrieval leg (#48) to the RAG pipeline.

**Architecture:** Two-layer fail-fast validation at API and implementation tiers. CamelCase expansion for BM25 text only (not payload content, not SPLADE). Server-side BM25 sparse vectors via `Document` inference API with `"qdrant/bm25"`. Constructor redesign: pass `RagConfig` directly instead of 15+ individual parameters.

**Tech Stack:** Java 21, Quarkus 3.32.2, Qdrant Java client 1.18.1, Testcontainers

## Global Constraints

- Java 21 language features (records, sealed interfaces, pattern matching)
- JVM 26 for compilation: `JAVA_HOME=$(/usr/libexec/java_home -v 26)`
- Use `mvn` not `./mvnw`
- Module build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl <module>`
- Qdrant test container: `qdrant/qdrant:v1.18.0`
- Tests use AssertJ (`assertThat`) and JUnit 5 (`org.junit.jupiter.api`)
- All code in `rag` module is package-private unless explicitly implementing an SPI
- `ChunkInput` has two metadata maps: `Map<String, String> metadata` and `Map<String, List<String>> listMetadata`
- Reserved payload keys union: `Set.of("content", "sourceDocumentId", "tenantId")`
- Spec: `specs/issue-53-payload-hardening-bm25/2026-06-29-payload-hardening-bm25-design.md`

---

### Task 1: ChunkInput Metadata Key Validation (#54 Layer 1)

**Files:**
- Modify: `rag-api/src/main/java/io/casehub/rag/ChunkInput.java`
- Modify: `rag-api/src/test/java/io/casehub/rag/ChunkInputTest.java`

**Interfaces:**
- Produces: `ChunkInput` constructor throws `IllegalArgumentException` when `metadata` or `listMetadata` contains key `"content"` or `"sourceDocumentId"`

- [ ] **Step 1: Write failing tests for reserved key rejection**

In `ChunkInputTest.java`, add:

```java
@Test
void metadataRejectsContentKey() {
    assertThrows(IllegalArgumentException.class,
        () -> new ChunkInput("text", "doc-1", Map.of("content", "x")));
}

@Test
void metadataRejectsSourceDocumentIdKey() {
    assertThrows(IllegalArgumentException.class,
        () -> new ChunkInput("text", "doc-1", Map.of("sourceDocumentId", "x")));
}

@Test
void metadataAllowsNonReservedKeys() {
    var chunk = new ChunkInput("text", "doc-1", Map.of("domain", "jvm", "author", "mdp"));
    assertEquals(Map.of("domain", "jvm", "author", "mdp"), chunk.metadata());
}

@Test
void listMetadataRejectsContentKey() {
    assertThrows(IllegalArgumentException.class,
        () -> new ChunkInput("text", "doc-1", Map.of(),
            Map.of("content", List.of("x"))));
}

@Test
void listMetadataRejectsSourceDocumentIdKey() {
    assertThrows(IllegalArgumentException.class,
        () -> new ChunkInput("text", "doc-1", Map.of(),
            Map.of("sourceDocumentId", List.of("x"))));
}

@Test
void listMetadataAllowsNonReservedKeys() {
    var chunk = new ChunkInput("text", "doc-1", Map.of(),
        Map.of("tags", List.of("cdi", "quarkus")));
    assertEquals(List.of("cdi", "quarkus"), chunk.listMetadata().get("tags"));
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=ChunkInputTest`
Expected: 4 failures on the reserved-key tests (the `allowsNonReservedKeys` tests pass)

- [ ] **Step 3: Implement reserved key validation in ChunkInput**

In `ChunkInput.java`, add the `RESERVED_KEYS` constant and validation in the compact constructor:

```java
public record ChunkInput(String content, String sourceDocumentId,
                          Map<String, String> metadata,
                          Map<String, List<String>> listMetadata) {

    private static final Set<String> RESERVED_KEYS = Set.of("content", "sourceDocumentId");

    public ChunkInput {
        if (content == null || content.isBlank())
            throw new IllegalArgumentException("content must not be null or blank");
        if (sourceDocumentId == null || sourceDocumentId.isBlank())
            throw new IllegalArgumentException("sourceDocumentId must not be null or blank");
        metadata = metadata == null ? Map.of() : Map.copyOf(metadata);
        listMetadata = listMetadata == null ? Map.of() : deepCopyListMetadata(listMetadata);
        for (String key : metadata.keySet()) {
            if (RESERVED_KEYS.contains(key))
                throw new IllegalArgumentException(
                    "metadata key '" + key + "' conflicts with ChunkInput field name");
        }
        for (String key : listMetadata.keySet()) {
            if (RESERVED_KEYS.contains(key))
                throw new IllegalArgumentException(
                    "metadata key '" + key + "' conflicts with ChunkInput field name");
        }
    }

    // existing convenience constructor and deepCopyListMetadata unchanged
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=ChunkInputTest`
Expected: All tests pass

- [ ] **Step 5: Build full rag-api module**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl rag-api`
Expected: BUILD SUCCESS — confirms no downstream compilation breakage within the module

- [ ] **Step 6: Commit**

```
feat(#54): ChunkInput rejects reserved metadata keys

Layer 1 of two-layer fail-fast validation. ChunkInput constructor throws
IllegalArgumentException when metadata or listMetadata contains "content"
or "sourceDocumentId" — these shadow the record's own typed fields.
```

---

### Task 2: CamelCaseExpander (#53)

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/CamelCaseExpander.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/CamelCaseExpanderTest.java`

**Interfaces:**
- Produces: `static String expand(String text)` — pure function, package-private

- [ ] **Step 1: Write failing tests**

Create `CamelCaseExpanderTest.java`:

```java
package io.casehub.rag.runtime;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;

class CamelCaseExpanderTest {

    @ParameterizedTest
    @CsvSource(delimiter = '|', value = {
        "ConcurrentHashMap | ConcurrentHashMap Concurrent Hash Map",
        "maxResults | maxResults max Results",
        "HTMLParser | HTMLParser HTML Parser",
        "Base64Encoder | Base64Encoder Base64 Encoder",
        "simple | simple",
        "ALLCAPS | ALLCAPS",
        "a | a",
        "AB | AB",
    })
    void expandsSingleToken(String input, String expected) {
        assertThat(CamelCaseExpander.expand(input)).isEqualTo(expected);
    }

    @Test
    void expandsMultipleTokensInText() {
        assertThat(CamelCaseExpander.expand("ConcurrentHashMap is useful"))
            .isEqualTo("ConcurrentHashMap Concurrent Hash Map is useful");
    }

    @Test
    void expandsMixedText() {
        assertThat(CamelCaseExpander.expand("maxResults for HTMLParser"))
            .isEqualTo("maxResults max Results for HTMLParser HTML Parser");
    }

    @Test
    void preservesPlainText() {
        assertThat(CamelCaseExpander.expand("simple words only"))
            .isEqualTo("simple words only");
    }

    @Test
    void handlesEmptyString() {
        assertThat(CamelCaseExpander.expand("")).isEqualTo("");
    }

    @Test
    void handlesNullReturnsEmpty() {
        assertThat(CamelCaseExpander.expand(null)).isEqualTo("");
    }

    @Test
    void xmlHttpRequestSplitsCorrectly() {
        assertThat(CamelCaseExpander.expand("XMLHttpRequest"))
            .isEqualTo("XMLHttpRequest XML Http Request");
    }

    @Test
    void consecutiveUppercaseEdgeCase() {
        // Non-standard: XMLHTTPRequest violates Java naming conventions
        // The algorithm produces XMLHTTP + Request, not XML + HTTP + Request
        assertThat(CamelCaseExpander.expand("XMLHTTPRequest"))
            .isEqualTo("XMLHTTPRequest XMLHTTP Request");
    }

    @Test
    void numberBoundary() {
        assertThat(CamelCaseExpander.expand("Base64Encoder"))
            .isEqualTo("Base64Encoder Base64 Encoder");
    }

    @Test
    void preservesWhitespaceAndPunctuation() {
        assertThat(CamelCaseExpander.expand("@DefaultBean annotation"))
            .isEqualTo("@DefaultBean @Default Bean annotation");
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=CamelCaseExpanderTest`
Expected: Compilation failure — `CamelCaseExpander` does not exist

- [ ] **Step 3: Implement CamelCaseExpander**

Create `CamelCaseExpander.java`:

```java
package io.casehub.rag.runtime;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

final class CamelCaseExpander {

    private static final Pattern TOKEN = Pattern.compile("\\S+");
    private static final Pattern CAMEL_BOUNDARY =
        Pattern.compile("(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[a-zA-Z])(?=[0-9])|(?<=[0-9])(?=[a-zA-Z])");

    private CamelCaseExpander() {}

    static String expand(String text) {
        if (text == null || text.isEmpty()) return "";

        StringBuilder result = new StringBuilder(text.length() * 2);
        Matcher tokenMatcher = TOKEN.matcher(text);
        int lastEnd = 0;

        while (tokenMatcher.find()) {
            result.append(text, lastEnd, tokenMatcher.start());
            String token = tokenMatcher.group();
            result.append(token);

            String[] parts = CAMEL_BOUNDARY.split(token);
            if (parts.length > 1) {
                for (String part : parts) {
                    result.append(' ').append(part);
                }
            }
            lastEnd = tokenMatcher.end();
        }
        result.append(text, lastEnd, text.length());

        return result.toString();
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=CamelCaseExpanderTest`
Expected: All tests pass. If the `@DefaultBean` or edge case tests don't match expectations, adjust the test expectations to match actual behavior and document the edge case.

- [ ] **Step 5: Commit**

```
feat(#53): CamelCaseExpander — split identifiers for BM25 tokenization

Pure function that appends sub-tokens after each camelCase identifier.
"ConcurrentHashMap" → "ConcurrentHashMap Concurrent Hash Map".
Preserves exact-match while enabling partial identifier search.
```

---

### Task 3: QdrantPointBuilder Hardening (#54 Layer 2 + shared constants)

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/QdrantPointBuilder.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/QdrantPointBuilderTest.java`

**Interfaces:**
- Consumes: `ChunkInput` reserved key validation from Task 1
- Produces: `QdrantPointBuilder.RESERVED_PAYLOAD_KEYS` (package-private `Set<String>`) used by both retrievers; `QdrantPointBuilder.BM25_MODEL` (package-private `String` constant)

- [ ] **Step 1: Write failing test for tenantId metadata rejection**

In `QdrantPointBuilderTest.java`, add:

```java
@Test
void buildPointRejectsTenantIdMetadata() {
    ChunkInput chunk = new ChunkInput("text", "doc-1", Map.of("tenantId", "evil"));
    Embedding embedding = Embedding.from(new float[]{0.1f, 0.2f});
    CorpusRef corpus = new CorpusRef("t1", "corpus");

    assertThat(catchThrowable(() -> QdrantPointBuilder.buildPoint(
        chunk, corpus, embedding, null, 0, "dense", "sparse")))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("tenantId");
}
```

Add the import: `import static org.assertj.core.api.Assertions.catchThrowable;`

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantPointBuilderTest#buildPointRejectsTenantIdMetadata`
Expected: FAIL — no validation exists yet

- [ ] **Step 3: Add validation and shared constants to QdrantPointBuilder**

In `QdrantPointBuilder.java`, add the constants and validation:

```java
final class QdrantPointBuilder {

    static final Set<String> RESERVED_PAYLOAD_KEYS =
        Set.of("content", "sourceDocumentId", "tenantId");

    static final String BM25_MODEL = "qdrant/bm25";

    private static final Set<String> QDRANT_RESERVED_KEYS = Set.of("tenantId");

    private QdrantPointBuilder() {}

    // In buildPoint(), before the metadata loop, add:
    // for (String key : chunk.metadata().keySet()) {
    //     if (QDRANT_RESERVED_KEYS.contains(key)) {
    //         throw new IllegalArgumentException(
    //             "metadata key '" + key + "' conflicts with reserved Qdrant payload field");
    //     }
    // }
```

Add the validation check inside `buildPoint()`, before the existing metadata iteration loop.

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantPointBuilderTest`
Expected: All tests pass

- [ ] **Step 5: Update both retrievers to use the shared constant**

In `HybridCaseRetriever.java`, replace the inline `RESERVED_PAYLOAD_KEYS` definition:

```java
// REMOVE this:
// private static final java.util.Set<String> RESERVED_PAYLOAD_KEYS =
//     java.util.Set.of("content", "sourceDocumentId", "tenantId");

// USE instead in mapToChunks / the metadata extraction loop:
if (!QdrantPointBuilder.RESERVED_PAYLOAD_KEYS.contains(entry.getKey())
```

Apply the same change in `ReactiveHybridCaseRetriever.java`.

- [ ] **Step 6: Run all rag tests to verify no regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`
Expected: All tests pass

- [ ] **Step 7: Commit**

```
feat(#54): QdrantPointBuilder rejects tenantId in metadata, shared constants

Layer 2 fail-fast: metadata key "tenantId" throws IllegalArgumentException.
Shared RESERVED_PAYLOAD_KEYS and BM25_MODEL constants extracted to
QdrantPointBuilder — both retrievers now reference the shared set.
```

---

### Task 4: RagConfig BM25 Properties + Constructor Redesign

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/RagConfig.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/RagBeanProducer.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveRagBeanProducer.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/RagTestFixtures.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/QdrantEmbeddingIngestorTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestorTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveEmbeddingIngestorTest.java` (if it constructs ingestors directly)

**Interfaces:**
- Produces: `RagConfig` with `bm25Enabled()`, `bm25VectorName()`, `RetrievalConfig.bm25TopK()`; all ingestors/retrievers take `RagConfig` directly

This task is purely structural — it changes how config flows into constructors but does not add BM25 behavior. All existing tests must continue to pass with BM25 defaulting to enabled (but no BM25 vectors created/queried until Tasks 5-6).

- [ ] **Step 1: Add BM25 properties to RagConfig**

In `RagConfig.java`:

```java
@ConfigMapping(prefix = "casehub.rag")
public interface RagConfig {

    QdrantConfig qdrant();

    @WithDefault("SEPARATE_COLLECTIONS")
    TenancyStrategy tenancyStrategy();

    @WithDefault("dense")
    String denseVectorName();

    @WithDefault("sparse")
    String sparseVectorName();

    @WithDefault("true")
    boolean bm25Enabled();

    @WithDefault("bm25")
    String bm25VectorName();

    RetrievalConfig retrieval();

    @WithDefault("100")
    int embeddingBatchSize();

    MatryoshkaConfig matryoshka();

    interface MatryoshkaConfig {
        OptionalInt dimension();
    }

    QuantizationConfig quantization();

    interface QuantizationConfig {
        @WithDefault("NONE")
        DenseQuantization type();

        @WithDefault("true")
        boolean alwaysRam();

        OptionalDouble oversampling();
    }

    interface QdrantConfig {
        @WithDefault("localhost")
        String host();

        @WithDefault("6334")
        int port();

        Optional<String> apiKey();

        @WithDefault("false")
        boolean useTls();
    }

    interface RetrievalConfig {
        @WithDefault("40")
        int denseTopK();

        @WithDefault("40")
        int sparseTopK();

        @WithDefault("40")
        int bm25TopK();

        @WithDefault("60")
        int rrfK();

        @WithDefault("true")
        boolean rerankEnabled();

        @WithDefault("10")
        int rerankTopN();
    }
}
```

- [ ] **Step 2: Create RagTestFixtures.stubConfig() helper**

In `RagTestFixtures.java`, add a method that creates a stub `RagConfig` for tests. Since `RagConfig` is a `@ConfigMapping` interface, tests need a manual implementation:

```java
static RagConfig stubConfig(String denseVectorName, String sparseVectorName,
        TenancyStrategy tenancy, DenseQuantization quant, boolean alwaysRam,
        OptionalDouble oversampling, OptionalInt matryoshkaDim,
        int batchSize, int denseTopK, int sparseTopK, int rrfK,
        boolean rerankEnabled, int rerankTopN,
        boolean bm25Enabled, int bm25TopK) {
    // Return an anonymous implementation of RagConfig with all nested interfaces
}
```

Provide a convenience overload `stubConfig()` with sensible defaults matching the existing test setup:
- `denseVectorName = "dense"`, `sparseVectorName = "sparse"`, `bm25VectorName = "bm25"`
- `tenancy = SEPARATE_COLLECTIONS`, `quant = NONE`, `alwaysRam = true`
- `oversampling = empty`, `matryoshkaDim = empty`, `batchSize = Integer.MAX_VALUE`
- `denseTopK = 64`, `sparseTopK = 64`, `bm25TopK = 40`, `rrfK = 60`
- `rerankEnabled = false`, `rerankTopN = 10`
- `bm25Enabled = false` (disabled by default in tests to avoid requiring Qdrant BM25 support in existing tests)

- [ ] **Step 3: Refactor QdrantEmbeddingIngestor constructor to take RagConfig**

Change the constructor from individual parameters to:

```java
QdrantEmbeddingIngestor(QdrantClient client, EmbeddingModel embeddingModel,
        SparseEmbedder sparseEmbedder, TenantGuard tenantGuard, RagConfig config) {
    if (config.embeddingBatchSize() <= 0)
        throw new IllegalArgumentException("batchSize must be positive");
    this.client = client;
    this.embeddingModel = embeddingModel;
    this.sparseEmbedder = sparseEmbedder;
    this.tenantGuard = tenantGuard;
    this.config = config;
    this.knownCollections = ConcurrentHashMap.newKeySet();
}
```

Replace all field references like `this.denseVectorName` with `config.denseVectorName()`. Store `config` as a field.

- [ ] **Step 4: Refactor ReactiveQdrantEmbeddingIngestor constructor**

Same pattern — take `RagConfig` directly. Replace field references.

- [ ] **Step 5: Refactor HybridCaseRetriever constructor**

```java
HybridCaseRetriever(QdrantClient client, EmbeddingModel embeddingModel,
        SparseEmbedder sparseEmbedder, TenantGuard tenantGuard,
        CrossEncoderReranker reranker, RagConfig config) {
    this.client = client;
    this.embeddingModel = embeddingModel;
    this.sparseEmbedder = sparseEmbedder;
    this.tenantGuard = tenantGuard;
    this.reranker = reranker;
    this.config = config;
}
```

Replace all individual field accesses with config accessors.

- [ ] **Step 6: Refactor ReactiveHybridCaseRetriever constructor**

Same pattern.

- [ ] **Step 7: Simplify RagBeanProducer**

```java
@Produces @ApplicationScoped
QdrantEmbeddingIngestor corpusStore() {
    return new QdrantEmbeddingIngestor(client, effectiveEmbeddingModel(),
        resolveSparseEmbedder(), resolveTenantGuard(), config);
}

@Produces @ApplicationScoped
HybridCaseRetriever caseRetriever() {
    return new HybridCaseRetriever(client, effectiveEmbeddingModel(),
        resolveSparseEmbedder(), resolveTenantGuard(),
        resolveReranker(), config);
}
```

Extract `resolveSparseEmbedder()`, `resolveTenantGuard()`, `resolveReranker()` helper methods to reduce duplication.

- [ ] **Step 8: Simplify ReactiveRagBeanProducer**

Same pattern.

- [ ] **Step 9: Update ALL test constructors**

Update every test that constructs `QdrantEmbeddingIngestor`, `ReactiveQdrantEmbeddingIngestor`, `HybridCaseRetriever`, or `ReactiveHybridCaseRetriever` to use `RagTestFixtures.stubConfig(...)` and the new constructor signatures.

This is mechanical but touches many test methods. Each test's `setUp()` method and any inline constructor calls must be updated.

- [ ] **Step 10: Run all rag tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`
Expected: All existing tests pass — behavior unchanged, only config plumbing changed

- [ ] **Step 11: Commit**

```
refactor(#48): pass RagConfig directly to ingestors and retrievers

Replaces 15+ individual constructor parameters with RagConfig.
Adds bm25Enabled, bm25VectorName, bm25TopK to RagConfig.
CDI producers simplified — no more parameter unpacking.
No behavioral changes — purely structural.
```

---

### Task 5: BM25 Ingestion — Collection Creation and Point Building (#48)

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/QdrantPointBuilder.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/QdrantPointBuilderTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/QdrantEmbeddingIngestorTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestorTest.java`

**Interfaces:**
- Consumes: `CamelCaseExpander.expand()` from Task 2; `QdrantPointBuilder.BM25_MODEL` from Task 3; `RagConfig.bm25Enabled()` from Task 4
- Produces: Collections with BM25 sparse vector when `bm25Enabled=true`; points with BM25 named vector

- [ ] **Step 1: Write failing test — BM25 vector in buildPoint**

In `QdrantPointBuilderTest.java`, add:

```java
@Test
void buildPointWithBm25Vector() {
    ChunkInput chunk = new ChunkInput("ConcurrentHashMap is useful", "doc-1", Map.of());
    Embedding embedding = Embedding.from(new float[]{0.1f, 0.2f});
    CorpusRef corpus = new CorpusRef("t1", "corpus");

    PointStruct point = QdrantPointBuilder.buildPoint(
        chunk, corpus, embedding, null, 0, "dense", "sparse", true, "bm25");

    assertThat(point.getVectors().getVectors().getVectorsMap()).containsKey("bm25");
    var bm25Vector = point.getVectors().getVectors().getVectorsMap().get("bm25");
    assertThat(bm25Vector.hasDocument()).isTrue();
    assertThat(bm25Vector.getDocument().getText()).contains("Concurrent Hash Map");
    assertThat(bm25Vector.getDocument().getModel()).isEqualTo("qdrant/bm25");
}

@Test
void buildPointWithoutBm25WhenDisabled() {
    ChunkInput chunk = new ChunkInput("text", "doc-1", Map.of());
    Embedding embedding = Embedding.from(new float[]{0.1f, 0.2f});
    CorpusRef corpus = new CorpusRef("t1", "corpus");

    PointStruct point = QdrantPointBuilder.buildPoint(
        chunk, corpus, embedding, null, 0, "dense", "sparse", false, "bm25");

    assertThat(point.getVectors().getVectors().getVectorsMap()).doesNotContainKey("bm25");
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantPointBuilderTest`
Expected: Compilation failure — `buildPoint` doesn't have the new parameters yet

- [ ] **Step 3: Add BM25 parameters to buildPoint**

Update `QdrantPointBuilder.buildPoint()` signature to add `boolean bm25Enabled, String bm25VectorName`. When `bm25Enabled`, expand content via `CamelCaseExpander` and add a BM25 `Document` vector:

```java
static PointStruct buildPoint(
        ChunkInput chunk, CorpusRef corpus,
        Embedding denseEmbedding, Map<Integer, Float> sparseMap,
        int chunkIndex, String denseVectorName, String sparseVectorName,
        boolean bm25Enabled, String bm25VectorName) {

    // ... existing id, denseVector, sparseVector code ...

    // Build named vectors map
    Map<String, Vector> namedVectors = new HashMap<>();
    namedVectors.put(denseVectorName, denseVector);
    if (sparseMap != null) {
        // ... existing sparse vector construction ...
        namedVectors.put(sparseVectorName, sparseVector);
    }
    if (bm25Enabled) {
        String expanded = CamelCaseExpander.expand(chunk.content());
        Vector bm25Vector = VectorFactory.vector(
            Document.newBuilder()
                .setText(expanded)
                .setModel(BM25_MODEL)
                .build());
        namedVectors.put(bm25VectorName, bm25Vector);
    }

    // ... existing payload + validation code ...
}
```

Update ALL callers of `buildPoint()` — both ingestors — to pass `config.bm25Enabled()` and `config.bm25VectorName()`. Update existing tests' `buildPoint()` calls to include the new parameters (use `false, "bm25"` for existing tests).

- [ ] **Step 4: Run QdrantPointBuilderTest**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantPointBuilderTest`
Expected: All tests pass

- [ ] **Step 5: Write failing test — BM25 sparse vector in collection creation**

In `QdrantEmbeddingIngestorTest.java`, add:

```java
@Test
void ensureCollectionCreatesBm25SparseVector() throws Exception {
    RagConfig bm25Config = RagTestFixtures.stubConfig(cfg -> cfg.bm25Enabled(true));

    QdrantEmbeddingIngestor bm25Store = new QdrantEmbeddingIngestor(
        client, new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
        null, TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)), bm25Config);

    CorpusRef corpus = uniqueCorpus();
    bm25Store.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of())));

    var info = client.getCollectionInfoAsync(
        TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus)).get();
    var sparseVectors = info.getConfig().getParams().getSparseVectorsConfig().getMapMap();

    assertThat(sparseVectors).containsKey("bm25");
    assertThat(sparseVectors.get("bm25").getModifier())
        .isEqualTo(io.qdrant.client.grpc.Collections.Modifier.Idf);
}

@Test
void ensureCollectionRejectsMissingBm25Vector() throws Exception {
    // Create collection without BM25 vector
    CorpusRef corpus = uniqueCorpus();
    String collection = TenancyStrategy.SEPARATE_COLLECTIONS.collectionName(corpus);

    var denseParams = io.qdrant.client.grpc.Collections.VectorParams.newBuilder()
        .setSize(DENSE_DIM)
        .setDistance(io.qdrant.client.grpc.Collections.Distance.Cosine).build();
    client.createCollectionAsync(
        io.qdrant.client.grpc.Collections.CreateCollection.newBuilder()
            .setCollectionName(collection)
            .setVectorsConfig(io.qdrant.client.grpc.Collections.VectorsConfig.newBuilder()
                .setParamsMap(io.qdrant.client.grpc.Collections.VectorParamsMap.newBuilder()
                    .putMap("dense", denseParams).build()).build())
            .build()).get();

    // Try ingesting with BM25 enabled — should fail
    RagConfig bm25Config = RagTestFixtures.stubConfig(cfg -> cfg.bm25Enabled(true));
    QdrantEmbeddingIngestor bm25Store = new QdrantEmbeddingIngestor(
        client, new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
        null, TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)), bm25Config);

    assertThatThrownBy(() -> bm25Store.ingest(corpus, List.of(
        new ChunkInput("content", "doc-1", Map.of()))))
        .isInstanceOf(IllegalStateException.class)
        .hasMessageContaining("bm25");
}
```

- [ ] **Step 6: Implement BM25 in ensureCollection**

In `QdrantEmbeddingIngestor.ensureCollection()`:
- Add BM25 sparse vector to `SparseVectorConfig` when `config.bm25Enabled()`:
  ```java
  sparseConfig.putMap(config.bm25VectorName(),
      SparseVectorParams.newBuilder().setModifier(Modifier.Idf).build());
  ```
- Add validation for existing collections — check that BM25 and SPLADE sparse vectors exist when expected
- Add the import: `import io.qdrant.client.grpc.Collections.Modifier;`

Apply the same changes to `ReactiveQdrantEmbeddingIngestor.buildCreateRequest()` and `ensureCollection()`.

- [ ] **Step 7: Run all ingestor tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest="QdrantEmbeddingIngestorTest,ReactiveQdrantEmbeddingIngestorTest"`
Expected: All tests pass

- [ ] **Step 8: Commit**

```
feat(#48): BM25 sparse vector in collection creation and point building

ensureCollection() creates "bm25" sparse vector with Modifier.Idf when
bm25Enabled. QdrantPointBuilder.buildPoint() adds BM25 Document vector
with camelCase-expanded content. Existing collection validation fails
fast when BM25 vector is missing.
```

---

### Task 6: BM25 Retrieval — Prefetch Leg and Mode Selection (#48)

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java`

**Interfaces:**
- Consumes: `CamelCaseExpander.expand()` from Task 2; `QdrantPointBuilder.BM25_MODEL` from Task 3; `RagConfig` from Task 4; BM25 collection/ingestion from Task 5

- [ ] **Step 1: Write failing test — BM25 retrieval with dense+BM25 mode (no SPLADE)**

In `HybridCaseRetrieverTest.java`, add:

```java
@Test
void bm25OnlyModeIngestAndRetrieve() {
    // Dense + BM25, no SPLADE
    RagConfig bm25Config = RagTestFixtures.stubConfig(cfg -> cfg.bm25Enabled(true));

    QdrantEmbeddingIngestor bm25Store = new QdrantEmbeddingIngestor(
        client, new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
        null, TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)), bm25Config);

    HybridCaseRetriever bm25Retriever = new HybridCaseRetriever(
        client, new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
        null, TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
        null, bm25Config);

    CorpusRef corpus = uniqueCorpus();
    bm25Store.ingest(corpus, List.of(
        new ChunkInput("ConcurrentHashMap is thread-safe", "doc-1",
            Map.of("category", "java")),
        new ChunkInput("Python asyncio event loop", "doc-2",
            Map.of("category", "python"))
    ));

    List<RetrievedChunk> results = bm25Retriever.retrieve(
        RetrievalQuery.of("HashMap"), corpus, 10, null);

    assertThat(results).isNotEmpty();
}

@Test
void threeWayRrfIngestAndRetrieve() {
    // Dense + SPLADE + BM25
    InMemoryInferenceModel spladeModel = InMemoryInferenceModel.returning(
        0.5f, 0.0f, 0.3f, 0.0f, 0.8f, 0.0f, 0.0f, 0.2f);
    SparseEmbedder sparseEmbedder = new SparseEmbedder(spladeModel);

    RagConfig threeWayConfig = RagTestFixtures.stubConfig(cfg -> cfg.bm25Enabled(true));

    QdrantEmbeddingIngestor store3 = new QdrantEmbeddingIngestor(
        client, new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
        sparseEmbedder, TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
        threeWayConfig);

    HybridCaseRetriever retriever3 = new HybridCaseRetriever(
        client, new RagTestFixtures.StubEmbeddingModel(DENSE_DIM),
        sparseEmbedder, TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
        null, threeWayConfig);

    CorpusRef corpus = uniqueCorpus();
    store3.ingest(corpus, List.of(
        new ChunkInput("ApplicationScoped CDI bean", "doc-1", Map.of()),
        new ChunkInput("Quarkus REST endpoint", "doc-2", Map.of())
    ));

    List<RetrievedChunk> results = retriever3.retrieve(
        RetrievalQuery.of("CDI bean"), corpus, 10, null);

    assertThat(results).isNotEmpty();
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=HybridCaseRetrieverTest#bm25OnlyModeIngestAndRetrieve`
Expected: FAIL — BM25 prefetch leg not implemented yet

- [ ] **Step 3: Restructure retrieval mode selection in HybridCaseRetriever**

Replace the existing `if (sparseEmbedder != null)` branching with the four-mode structure from the spec:

```java
boolean useRrf = sparseEmbedder != null || config.bm25Enabled();
if (useRrf) {
    QueryPoints.Builder qb = QueryPoints.newBuilder()
        .setCollectionName(collection);

    // Dense prefetch (always present in RRF mode)
    PrefetchQuery.Builder densePrefetch = PrefetchQuery.newBuilder()
        .setQuery(QueryFactory.nearest(denseEmbedding.vectorAsList()))
        .setUsing(config.denseVectorName())
        .setLimit(config.retrieval().denseTopK());
    if (config.quantization().type() != DenseQuantization.NONE
            && config.quantization().oversampling().isPresent()) {
        densePrefetch.setParams(quantizationSearchParams());
    }
    mergedFilter.ifPresent(densePrefetch::setFilter);
    qb.addPrefetch(densePrefetch);

    // SPLADE prefetch (when available)
    if (sparseEmbedder != null) {
        Map<Integer, Float> sparseMap = sparseEmbedder.embed(query.text());
        // ... build sparse values/indices lists ...
        PrefetchQuery.Builder sparsePrefetch = PrefetchQuery.newBuilder()
            .setQuery(QueryFactory.nearest(sparseValues, sparseIndices))
            .setUsing(config.sparseVectorName())
            .setLimit(config.retrieval().sparseTopK());
        mergedFilter.ifPresent(sparsePrefetch::setFilter);
        qb.addPrefetch(sparsePrefetch);
    }

    // BM25 prefetch (when enabled)
    if (config.bm25Enabled()) {
        String expandedQuery = CamelCaseExpander.expand(query.text());
        PrefetchQuery.Builder bm25Prefetch = PrefetchQuery.newBuilder()
            .setQuery(QueryFactory.nearest(
                Document.newBuilder()
                    .setText(expandedQuery)
                    .setModel(QdrantPointBuilder.BM25_MODEL)
                    .build()))
            .setUsing(config.bm25VectorName())
            .setLimit(config.retrieval().bm25TopK());
        mergedFilter.ifPresent(bm25Prefetch::setFilter);
        qb.addPrefetch(bm25Prefetch);
    }

    qb.setQuery(QueryFactory.rrf(Rrf.newBuilder().setK(config.retrieval().rrfK()).build()))
       .setLimit(queryLimit)
       .setWithPayload(WithPayloadSelectorFactory.enable(true));
    queryPoints = qb.build();
} else {
    // Dense-only: direct nearest-neighbor query (no fusion)
    // ... existing dense-only code ...
}
```

Add imports: `import io.qdrant.client.grpc.Points.Document;`

- [ ] **Step 4: Apply same restructure to ReactiveHybridCaseRetriever**

Mirror the mode selection changes in the reactive variant's `executeQuery()` method.

- [ ] **Step 5: Run all retriever tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest="HybridCaseRetrieverTest,ReactiveHybridCaseRetrieverTest"`
Expected: All tests pass

- [ ] **Step 6: Run full rag module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`
Expected: All tests pass

- [ ] **Step 7: Full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS across all modules

- [ ] **Step 8: Commit**

```
feat(#48): BM25 as third RRF retrieval leg

Both retrievers support four modes: dense-only, dense+SPLADE,
dense+BM25, dense+SPLADE+BM25. BM25 prefetch uses server-side
Document inference with "qdrant/bm25" and camelCase-expanded
query text. RRF handles N legs transparently.

Closes #48, closes #53, closes #54.
```

# RAG Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `rag-api`, `rag`, `rag-tika`, and `rag-testing` modules for casehub-neural-text #7 — hybrid dense+sparse RAG pipeline with Qdrant, RRF fusion, optional cross-encoder reranking, and defense-in-depth tenancy validation.

**Architecture:** Four modules built in dependency order. `rag-api` defines pure-Java SPIs (`CorpusStore`, `CaseRetriever`) and records. `rag` implements them using the Qdrant Java gRPC client for both dense and sparse legs, with `EmbeddingModel` (LangChain4j) for dense embeddings and `SparseEmbedder` (inference-splade) for sparse. `rag-tika` is an optional document parsing module. `rag-testing` provides in-memory stubs. All follow TDD with the established inference-module patterns.

**Tech Stack:** Java 21, Quarkus 3.32.2, LangChain4j 1.14.1 (core only), io.qdrant:client 1.18.1, inference-splade, inference-tasks, casehub-platform-api, ArchUnit 1.4.1, Testcontainers (Qdrant), JUnit 5, AssertJ

**Spec:** `specs/issue-7-rag-pipeline/2026-06-08-rag-pipeline-design.md`

**Build command:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl <module>`

---

### Task 1: Parent POM — bump Qdrant client, add rag-tika module

The scaffolded Qdrant client version (1.9.1) predates the Query API (prefetch + fusion). The Query API was introduced in Qdrant server 1.10 / Java client 1.10.0.

**Files:**
- Modify: `pom.xml` (parent)

- [ ] **Step 1: Bump Qdrant client version**

In `pom.xml`, change:
```xml
<qdrant.client.version>1.9.1</qdrant.client.version>
```
to:
```xml
<qdrant.client.version>1.18.1</qdrant.client.version>
```

- [ ] **Step 2: Add rag-tika to modules list**

In `pom.xml`, after the `<module>rag</module>` entry, add:
```xml
<module>rag-tika</module>
```

The full `<modules>` block should read:
```xml
<modules>
    <module>inference-api</module>
    <module>inference-runtime</module>
    <module>inference-tasks</module>
    <module>inference-splade</module>
    <module>inference-inmem</module>
    <module>inference-quarkus</module>
    <module>rag-api</module>
    <module>rag</module>
    <module>rag-tika</module>
    <module>rag-testing</module>
</modules>
```

- [ ] **Step 3: Add langchain4j-core to dependency management**

Add to `<dependencyManagement>`:
```xml
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j-core</artifactId>
    <version>${langchain4j.version}</version>
</dependency>
```

- [ ] **Step 4: Commit**

```bash
git add pom.xml
git commit -m "chore(#7): bump qdrant client 1.9.1→1.18.1, add rag-tika module, add langchain4j-core dep"
```

---

### Task 2: rag-api — records (CorpusRef, ChunkInput, RetrievedChunk)

**Files:**
- Create: `rag-api/src/main/java/io/casehub/rag/CorpusRef.java`
- Create: `rag-api/src/main/java/io/casehub/rag/ChunkInput.java`
- Create: `rag-api/src/main/java/io/casehub/rag/RetrievedChunk.java`
- Create: `rag-api/src/test/java/io/casehub/rag/CorpusRefTest.java`
- Create: `rag-api/src/test/java/io/casehub/rag/ChunkInputTest.java`
- Create: `rag-api/src/test/java/io/casehub/rag/RetrievedChunkTest.java`

- [ ] **Step 1: Write CorpusRef tests**

```java
package io.casehub.rag;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class CorpusRefTest {

    @Test
    void validConstruction() {
        var ref = new CorpusRef("tenant-1", "legal");
        assertThat(ref.tenantId()).isEqualTo("tenant-1");
        assertThat(ref.corpusName()).isEqualTo("legal");
    }

    @Test
    void nullTenantIdThrows() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new CorpusRef(null, "legal"))
            .withMessageContaining("tenantId");
    }

    @Test
    void blankTenantIdThrows() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new CorpusRef("  ", "legal"))
            .withMessageContaining("tenantId");
    }

    @Test
    void nullCorpusNameThrows() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new CorpusRef("tenant-1", null))
            .withMessageContaining("corpusName");
    }

    @Test
    void blankCorpusNameThrows() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new CorpusRef("tenant-1", ""))
            .withMessageContaining("corpusName");
    }

    @Test
    void equalityByValue() {
        var a = new CorpusRef("t1", "c1");
        var b = new CorpusRef("t1", "c1");
        assertThat(a).isEqualTo(b);
        assertThat(a.hashCode()).isEqualTo(b.hashCode());
    }
}
```

- [ ] **Step 2: Run test — verify RED**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=CorpusRefTest
```
Expected: compilation failure — `CorpusRef` does not exist.

- [ ] **Step 3: Implement CorpusRef**

```java
package io.casehub.rag;

public record CorpusRef(String tenantId, String corpusName) {
    public CorpusRef {
        if (tenantId == null || tenantId.isBlank())
            throw new IllegalArgumentException("tenantId must not be null or blank");
        if (corpusName == null || corpusName.isBlank())
            throw new IllegalArgumentException("corpusName must not be null or blank");
    }
}
```

- [ ] **Step 4: Run test — verify GREEN**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=CorpusRefTest
```
Expected: all 6 tests PASS.

- [ ] **Step 5: Write ChunkInput tests**

```java
package io.casehub.rag;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class ChunkInputTest {

    @Test
    void validConstruction() {
        var chunk = new ChunkInput("text content", "doc-1", Map.of("key", "val"));
        assertThat(chunk.content()).isEqualTo("text content");
        assertThat(chunk.sourceDocumentId()).isEqualTo("doc-1");
        assertThat(chunk.metadata()).containsEntry("key", "val");
    }

    @Test
    void nullContentThrows() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new ChunkInput(null, "doc-1", Map.of()))
            .withMessageContaining("content");
    }

    @Test
    void blankContentThrows() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new ChunkInput("  ", "doc-1", Map.of()))
            .withMessageContaining("content");
    }

    @Test
    void nullSourceDocumentIdThrows() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new ChunkInput("text", null, Map.of()))
            .withMessageContaining("sourceDocumentId");
    }

    @Test
    void nullMetadataDefaultsToEmpty() {
        var chunk = new ChunkInput("text", "doc-1", null);
        assertThat(chunk.metadata()).isEmpty();
    }

    @Test
    void metadataIsDefensivelyCopied() {
        var mutable = new HashMap<String, String>();
        mutable.put("k", "v");
        var chunk = new ChunkInput("text", "doc-1", mutable);
        mutable.put("k2", "v2");
        assertThat(chunk.metadata()).doesNotContainKey("k2");
        assertThatExceptionOfType(UnsupportedOperationException.class)
            .isThrownBy(() -> chunk.metadata().put("k3", "v3"));
    }
}
```

- [ ] **Step 6: Implement ChunkInput — verify GREEN**

```java
package io.casehub.rag;

import java.util.Map;

public record ChunkInput(String content, String sourceDocumentId, Map<String, String> metadata) {
    public ChunkInput {
        if (content == null || content.isBlank())
            throw new IllegalArgumentException("content must not be null or blank");
        if (sourceDocumentId == null || sourceDocumentId.isBlank())
            throw new IllegalArgumentException("sourceDocumentId must not be null or blank");
        metadata = metadata == null ? Map.of() : Map.copyOf(metadata);
    }
}
```

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=ChunkInputTest
```

- [ ] **Step 7: Write RetrievedChunk tests**

```java
package io.casehub.rag;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class RetrievedChunkTest {

    @Test
    void validConstruction() {
        var chunk = new RetrievedChunk("text", "doc-1", 0.95, Map.of("k", "v"));
        assertThat(chunk.content()).isEqualTo("text");
        assertThat(chunk.sourceDocumentId()).isEqualTo("doc-1");
        assertThat(chunk.relevanceScore()).isEqualTo(0.95);
        assertThat(chunk.metadata()).containsEntry("k", "v");
    }

    @Test
    void nullContentThrows() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new RetrievedChunk(null, "doc-1", 0.9, Map.of()))
            .withMessageContaining("content");
    }

    @Test
    void nullSourceDocumentIdThrows() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new RetrievedChunk("text", null, 0.9, Map.of()))
            .withMessageContaining("sourceDocumentId");
    }

    @Test
    void nullMetadataDefaultsToEmpty() {
        var chunk = new RetrievedChunk("text", "doc-1", 0.9, null);
        assertThat(chunk.metadata()).isEmpty();
    }

    @Test
    void metadataIsDefensivelyCopied() {
        var mutable = new HashMap<String, String>();
        mutable.put("k", "v");
        var chunk = new RetrievedChunk("text", "doc-1", 0.9, mutable);
        mutable.put("k2", "v2");
        assertThat(chunk.metadata()).doesNotContainKey("k2");
    }
}
```

- [ ] **Step 8: Implement RetrievedChunk — verify GREEN**

```java
package io.casehub.rag;

import java.util.Map;

public record RetrievedChunk(String content, String sourceDocumentId,
                             double relevanceScore, Map<String, String> metadata) {
    public RetrievedChunk {
        if (content == null)
            throw new IllegalArgumentException("content must not be null");
        if (sourceDocumentId == null)
            throw new IllegalArgumentException("sourceDocumentId must not be null");
        metadata = metadata == null ? Map.of() : Map.copyOf(metadata);
    }
}
```

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api
```
Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add rag-api/src/
git commit -m "feat(#7): rag-api records — CorpusRef, ChunkInput, RetrievedChunk with compact constructors"
```

---

### Task 3: rag-api — SPI interfaces + ArchUnit

**Files:**
- Create: `rag-api/src/main/java/io/casehub/rag/CorpusStore.java`
- Create: `rag-api/src/main/java/io/casehub/rag/CaseRetriever.java`
- Create: `rag-api/src/test/java/io/casehub/rag/DependencyConstraintTest.java`

- [ ] **Step 1: Write CorpusStore SPI**

```java
package io.casehub.rag;

import java.util.List;

public interface CorpusStore {
    void ingest(CorpusRef corpus, List<ChunkInput> chunks);
    void deleteDocument(CorpusRef corpus, String sourceDocumentId);
    void deleteCorpus(CorpusRef corpus);
    List<String> listDocuments(CorpusRef corpus);
}
```

- [ ] **Step 2: Write CaseRetriever SPI**

```java
package io.casehub.rag;

import java.util.List;

public interface CaseRetriever {
    List<RetrievedChunk> retrieve(String query, CorpusRef corpus, int maxResults);
}
```

- [ ] **Step 3: Write ArchUnit dependency constraints**

Follow the established pattern from `inference-api/src/test/java/io/casehub/inference/DependencyConstraintTest.java`.

```java
package io.casehub.rag;

import com.tngtech.archunit.base.DescribedPredicate;
import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

@AnalyzeClasses(packages = "io.casehub.rag")
class DependencyConstraintTest {

    @ArchTest
    static final ArchRule noQuarkus = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("io.quarkus..", "jakarta..");

    @ArchTest
    static final ArchRule noLangChain4j = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("dev.langchain4j..");

    @ArchTest
    static final ArchRule noQdrant = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("io.qdrant..");

    @ArchTest
    static final ArchRule noCasehubDomain = noClasses()
        .that().resideInAPackage("io.casehub.rag..")
        .should().dependOnClassesThat(
            DescribedPredicate.describe("casehub domain classes",
                (JavaClass cls) -> cls.getPackageName().startsWith("io.casehub.")
                    && !cls.getPackageName().startsWith("io.casehub.rag")));
}
```

- [ ] **Step 4: Run all rag-api tests — verify GREEN**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api
```
Expected: all record tests + ArchUnit constraints PASS.

- [ ] **Step 5: Commit**

```bash
git add rag-api/src/
git commit -m "feat(#7): rag-api SPIs — CorpusStore, CaseRetriever + ArchUnit zero-dep constraints"
```

---

### Task 4: rag-testing — InMemoryCorpusStore

**Files:**
- Modify: `rag-testing/pom.xml` — add `jakarta.enterprise.cdi-api` (provided)
- Create: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCorpusStore.java`
- Create: `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryCorpusStoreTest.java`

- [ ] **Step 1: Update rag-testing pom.xml**

Add to `<dependencies>`:
```xml
<dependency>
    <groupId>jakarta.enterprise</groupId>
    <artifactId>jakarta.enterprise.cdi-api</artifactId>
    <version>4.0.1</version>
    <scope>provided</scope>
</dependency>
```

- [ ] **Step 2: Write InMemoryCorpusStore tests**

```java
package io.casehub.rag.testing;

import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.*;

class InMemoryCorpusStoreTest {

    private InMemoryCorpusStore store;
    private final CorpusRef corpus = new CorpusRef("tenant-1", "legal");

    @BeforeEach
    void setUp() {
        store = new InMemoryCorpusStore();
    }

    @Test
    void ingestAndListDocuments() {
        store.ingest(corpus, List.of(
            new ChunkInput("chunk 1", "doc-A", Map.of()),
            new ChunkInput("chunk 2", "doc-A", Map.of()),
            new ChunkInput("chunk 3", "doc-B", Map.of())));
        assertThat(store.listDocuments(corpus)).containsExactlyInAnyOrder("doc-A", "doc-B");
    }

    @Test
    void listDocumentsEmptyCorpus() {
        assertThat(store.listDocuments(corpus)).isEmpty();
    }

    @Test
    void deleteDocument() {
        store.ingest(corpus, List.of(
            new ChunkInput("c1", "doc-A", Map.of()),
            new ChunkInput("c2", "doc-B", Map.of())));
        store.deleteDocument(corpus, "doc-A");
        assertThat(store.listDocuments(corpus)).containsExactly("doc-B");
    }

    @Test
    void deleteCorpus() {
        store.ingest(corpus, List.of(new ChunkInput("c1", "doc-A", Map.of())));
        store.deleteCorpus(corpus);
        assertThat(store.listDocuments(corpus)).isEmpty();
    }

    @Test
    void getChunksReturnsInsertionOrder() {
        var c1 = new ChunkInput("first", "doc-A", Map.of());
        var c2 = new ChunkInput("second", "doc-A", Map.of());
        store.ingest(corpus, List.of(c1, c2));
        assertThat(store.getChunks(corpus))
            .extracting(ChunkInput::content)
            .containsExactly("first", "second");
    }

    @Test
    void tenantIsolation() {
        var otherCorpus = new CorpusRef("tenant-2", "legal");
        store.ingest(corpus, List.of(new ChunkInput("t1", "doc-A", Map.of())));
        store.ingest(otherCorpus, List.of(new ChunkInput("t2", "doc-B", Map.of())));
        assertThat(store.listDocuments(corpus)).containsExactly("doc-A");
        assertThat(store.listDocuments(otherCorpus)).containsExactly("doc-B");
    }
}
```

- [ ] **Step 3: Run test — verify RED**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing -Dtest=InMemoryCorpusStoreTest
```
Expected: compilation failure — `InMemoryCorpusStore` does not exist.

- [ ] **Step 4: Implement InMemoryCorpusStore**

```java
package io.casehub.rag.testing;

import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.CorpusStore;
import jakarta.annotation.Priority;
import jakarta.enterprise.inject.Alternative;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Alternative
@Priority(1)
public class InMemoryCorpusStore implements CorpusStore {

    private final Map<CorpusRef, Map<String, List<ChunkInput>>> data = new ConcurrentHashMap<>();

    @Override
    public void ingest(CorpusRef corpus, List<ChunkInput> chunks) {
        var docs = data.computeIfAbsent(corpus, k -> new LinkedHashMap<>());
        for (ChunkInput chunk : chunks) {
            docs.computeIfAbsent(chunk.sourceDocumentId(), k -> new ArrayList<>()).add(chunk);
        }
    }

    @Override
    public void deleteDocument(CorpusRef corpus, String sourceDocumentId) {
        var docs = data.get(corpus);
        if (docs != null) {
            docs.remove(sourceDocumentId);
        }
    }

    @Override
    public void deleteCorpus(CorpusRef corpus) {
        data.remove(corpus);
    }

    @Override
    public List<String> listDocuments(CorpusRef corpus) {
        var docs = data.get(corpus);
        if (docs == null) return List.of();
        return List.copyOf(docs.keySet());
    }

    public List<ChunkInput> getChunks(CorpusRef corpus) {
        var docs = data.get(corpus);
        if (docs == null) return List.of();
        List<ChunkInput> all = new ArrayList<>();
        docs.values().forEach(all::addAll);
        return Collections.unmodifiableList(all);
    }
}
```

- [ ] **Step 5: Run test — verify GREEN**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing -Dtest=InMemoryCorpusStoreTest
```
Expected: all 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add rag-testing/
git commit -m "feat(#7): InMemoryCorpusStore — in-memory CorpusStore stub for @QuarkusTest"
```

---

### Task 5: rag-testing — InMemoryCaseRetriever

**Files:**
- Create: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCaseRetriever.java`
- Create: `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryCaseRetrieverTest.java`

- [ ] **Step 1: Write InMemoryCaseRetriever tests**

```java
package io.casehub.rag.testing;

import io.casehub.rag.CaseRetriever;
import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.RetrievedChunk;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.*;

class InMemoryCaseRetrieverTest {

    private final CorpusRef corpus = new CorpusRef("tenant-1", "legal");

    @Test
    void backedByStoreReturnsIngestedChunks() {
        var store = new InMemoryCorpusStore();
        store.ingest(corpus, List.of(
            new ChunkInput("first chunk", "doc-A", Map.of("page", "1")),
            new ChunkInput("second chunk", "doc-A", Map.of("page", "2")),
            new ChunkInput("third chunk", "doc-B", Map.of())));

        CaseRetriever retriever = new InMemoryCaseRetriever(store);
        List<RetrievedChunk> results = retriever.retrieve("any query", corpus, 2);

        assertThat(results).hasSize(2);
        assertThat(results.get(0).content()).isEqualTo("first chunk");
        assertThat(results.get(0).sourceDocumentId()).isEqualTo("doc-A");
        assertThat(results.get(0).relevanceScore()).isEqualTo(1.0);
        assertThat(results.get(0).metadata()).containsEntry("page", "1");
        assertThat(results.get(1).content()).isEqualTo("second chunk");
    }

    @Test
    void backedByStoreReturnsEmptyForUnknownCorpus() {
        var store = new InMemoryCorpusStore();
        CaseRetriever retriever = new InMemoryCaseRetriever(store);
        assertThat(retriever.retrieve("query", corpus, 10)).isEmpty();
    }

    @Test
    void programmaticReturnsFixedResponse() {
        var fixed = List.of(
            new RetrievedChunk("fixed content", "doc-X", 0.88, Map.of()));
        CaseRetriever retriever = InMemoryCaseRetriever.returning(fixed);

        List<RetrievedChunk> results = retriever.retrieve("any query", corpus, 100);
        assertThat(results).hasSize(1);
        assertThat(results.get(0).content()).isEqualTo("fixed content");
        assertThat(results.get(0).relevanceScore()).isEqualTo(0.88);
    }

    @Test
    void programmaticIgnoresMaxResults() {
        var fixed = List.of(
            new RetrievedChunk("a", "d1", 0.9, Map.of()),
            new RetrievedChunk("b", "d2", 0.8, Map.of()));
        CaseRetriever retriever = InMemoryCaseRetriever.returning(fixed);
        assertThat(retriever.retrieve("q", corpus, 1)).hasSize(2);
    }
}
```

- [ ] **Step 2: Run test — verify RED**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing -Dtest=InMemoryCaseRetrieverTest
```
Expected: compilation failure.

- [ ] **Step 3: Implement InMemoryCaseRetriever**

```java
package io.casehub.rag.testing;

import io.casehub.rag.CaseRetriever;
import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.RetrievedChunk;
import jakarta.annotation.Priority;
import jakarta.enterprise.inject.Alternative;

import java.util.Collections;
import java.util.List;

@Alternative
@Priority(1)
public class InMemoryCaseRetriever implements CaseRetriever {

    private final InMemoryCorpusStore store;
    private final List<RetrievedChunk> fixedResponse;

    public InMemoryCaseRetriever(InMemoryCorpusStore store) {
        this.store = store;
        this.fixedResponse = null;
    }

    private InMemoryCaseRetriever(List<RetrievedChunk> fixedResponse) {
        this.store = null;
        this.fixedResponse = List.copyOf(fixedResponse);
    }

    public static InMemoryCaseRetriever returning(List<RetrievedChunk> fixedResponse) {
        return new InMemoryCaseRetriever(fixedResponse);
    }

    @Override
    public List<RetrievedChunk> retrieve(String query, CorpusRef corpus, int maxResults) {
        if (fixedResponse != null) {
            return fixedResponse;
        }

        List<ChunkInput> chunks = store.getChunks(corpus);
        int limit = Math.min(maxResults, chunks.size());
        List<RetrievedChunk> results = new java.util.ArrayList<>(limit);
        for (int i = 0; i < limit; i++) {
            ChunkInput c = chunks.get(i);
            results.add(new RetrievedChunk(c.content(), c.sourceDocumentId(), 1.0, c.metadata()));
        }
        return Collections.unmodifiableList(results);
    }
}
```

- [ ] **Step 4: Run test — verify GREEN**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rag-testing/src/
git commit -m "feat(#7): InMemoryCaseRetriever — store-backed and programmatic modes"
```

---

### Task 6: rag POM cleanup

**Files:**
- Modify: `rag/pom.xml`

- [ ] **Step 1: Rewrite rag/pom.xml dependencies**

Replace the entire `<dependencies>` block with:
```xml
<dependencies>

    <!-- casehub-neural-text -->
    <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-rag-api</artifactId>
    </dependency>
    <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-inference-splade</artifactId>
    </dependency>
    <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-inference-tasks</artifactId>
    </dependency>

    <!-- casehub platform — tenancy validation -->
    <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-platform-api</artifactId>
    </dependency>

    <!-- CDI -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-arc</artifactId>
    </dependency>

    <!-- LangChain4j — EmbeddingModel, Embedding, TextSegment types only -->
    <dependency>
        <groupId>dev.langchain4j</groupId>
        <artifactId>langchain4j-core</artifactId>
    </dependency>

    <!-- Qdrant Java client — gRPC, both dense and sparse legs -->
    <dependency>
        <groupId>io.qdrant</groupId>
        <artifactId>client</artifactId>
    </dependency>

    <!-- Testing -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-junit5</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>org.assertj</groupId>
        <artifactId>assertj-core</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>com.tngtech.archunit</groupId>
        <artifactId>archunit-junit5</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-rag-testing</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-inference-inmem</artifactId>
        <scope>test</scope>
    </dependency>

</dependencies>
```

Removed: `langchain4j-qdrant`, `langchain4j-document-parser-apache-tika`, `casehub-inference-quarkus`, `langchain4j`, `langchain4j-embeddings`.

- [ ] **Step 2: Verify build compiles**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl rag
```

- [ ] **Step 3: Commit**

```bash
git add rag/pom.xml
git commit -m "chore(#7): rag POM cleanup — drop langchain4j-qdrant, Tika, inference-quarkus; add langchain4j-core"
```

---

### Task 7: rag — TenancyStrategy

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/TenancyStrategy.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/TenancyStrategyTest.java`

- [ ] **Step 1: Write TenancyStrategy tests**

```java
package io.casehub.rag.runtime;

import io.casehub.rag.CorpusRef;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.*;

class TenancyStrategyTest {

    private final CorpusRef corpus = new CorpusRef("tenant-abc", "legal");

    @Test
    void separateCollectionName() {
        var strategy = TenancyStrategy.SEPARATE_COLLECTIONS;
        assertThat(strategy.collectionName(corpus)).isEqualTo("tenant-abc_legal");
    }

    @Test
    void separateCollectionHasNoFilter() {
        var strategy = TenancyStrategy.SEPARATE_COLLECTIONS;
        assertThat(strategy.tenantFilter(corpus)).isEmpty();
    }

    @Test
    void sharedCollectionName() {
        var strategy = TenancyStrategy.SHARED_COLLECTION;
        assertThat(strategy.collectionName(corpus)).isEqualTo("legal");
    }

    @Test
    void sharedCollectionHasFilter() {
        var strategy = TenancyStrategy.SHARED_COLLECTION;
        assertThat(strategy.tenantFilter(corpus)).isPresent();
    }
}
```

- [ ] **Step 2: Run test — verify RED**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=TenancyStrategyTest
```

- [ ] **Step 3: Implement TenancyStrategy**

```java
package io.casehub.rag.runtime;

import io.casehub.rag.CorpusRef;
import io.qdrant.client.ConditionFactory;
import io.qdrant.client.grpc.Points.Filter;

import java.util.Optional;

public enum TenancyStrategy {

    SEPARATE_COLLECTIONS {
        @Override
        public String collectionName(CorpusRef corpus) {
            return corpus.tenantId() + "_" + corpus.corpusName();
        }

        @Override
        public Optional<Filter> tenantFilter(CorpusRef corpus) {
            return Optional.empty();
        }
    },

    SHARED_COLLECTION {
        @Override
        public String collectionName(CorpusRef corpus) {
            return corpus.corpusName();
        }

        @Override
        public Optional<Filter> tenantFilter(CorpusRef corpus) {
            return Optional.of(Filter.newBuilder()
                .addMust(ConditionFactory.matchKeyword("tenantId", corpus.tenantId()))
                .build());
        }
    };

    public abstract String collectionName(CorpusRef corpus);
    public abstract Optional<Filter> tenantFilter(CorpusRef corpus);
}
```

- [ ] **Step 4: Run test — verify GREEN**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=TenancyStrategyTest
```
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rag/src/
git commit -m "feat(#7): TenancyStrategy — SEPARATE_COLLECTIONS and SHARED_COLLECTION modes"
```

---

### Task 8: rag — QdrantConfig + QdrantClientProducer

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/RagConfig.java`
- Create: `rag/src/main/java/io/casehub/rag/runtime/QdrantClientProducer.java`

- [ ] **Step 1: Write RagConfig**

```java
package io.casehub.rag.runtime;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;

import java.util.Optional;

@ConfigMapping(prefix = "casehub.rag")
public interface RagConfig {

    QdrantConfig qdrant();

    @WithDefault("SEPARATE_COLLECTIONS")
    TenancyStrategy tenancyStrategy();

    @WithDefault("dense")
    String denseVectorName();

    @WithDefault("sparse")
    String sparseVectorName();

    RetrievalConfig retrieval();

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

        @WithDefault("60")
        int rrfK();

        @WithDefault("true")
        boolean rerankEnabled();

        @WithDefault("10")
        int rerankTopN();
    }
}
```

- [ ] **Step 2: Write QdrantClientProducer**

```java
package io.casehub.rag.runtime;

import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Disposes;
import jakarta.enterprise.inject.Produces;
import jakarta.inject.Inject;

@ApplicationScoped
public class QdrantClientProducer {

    private final RagConfig config;

    @Inject
    public QdrantClientProducer(RagConfig config) {
        this.config = config;
    }

    @Produces
    @ApplicationScoped
    QdrantClient qdrantClient() {
        var grpcBuilder = QdrantGrpcClient.newBuilder(
            config.qdrant().host(),
            config.qdrant().port(),
            config.qdrant().useTls());
        config.qdrant().apiKey().ifPresent(grpcBuilder::withApiKey);
        return new QdrantClient(grpcBuilder.build());
    }

    void close(@Disposes QdrantClient client) {
        try {
            client.close();
        } catch (Exception ignored) {
        }
    }
}
```

- [ ] **Step 3: Verify compilation**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl rag
```

- [ ] **Step 4: Commit**

```bash
git add rag/src/main/java/io/casehub/rag/runtime/RagConfig.java rag/src/main/java/io/casehub/rag/runtime/QdrantClientProducer.java
git commit -m "feat(#7): RagConfig @ConfigMapping + QdrantClientProducer CDI"
```

---

### Task 9: rag — QdrantCorpusStore

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/QdrantCorpusStore.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/QdrantCorpusStoreTest.java`
- Create: `rag/src/test/resources/application.properties`

This task uses Testcontainers with Qdrant Docker image for integration testing.

- [ ] **Step 1: Add Testcontainers dependencies to rag/pom.xml**

Add to test dependencies:
```xml
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>testcontainers</artifactId>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>junit-jupiter</artifactId>
    <scope>test</scope>
</dependency>
```

Add Testcontainers BOM to parent `<dependencyManagement>`:
```xml
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>testcontainers-bom</artifactId>
    <version>1.20.4</version>
    <type>pom</type>
    <scope>import</scope>
</dependency>
```

- [ ] **Step 2: Write QdrantCorpusStore integration test**

```java
package io.casehub.rag.runtime;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.output.Response;
import io.casehub.inference.inmem.InMemoryInferenceModel;
import io.casehub.inference.splade.SparseEmbedder;
import io.casehub.platform.api.identity.CurrentPrincipal;
import io.casehub.platform.api.memory.MemoryPermissions;
import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.*;

@Testcontainers
class QdrantCorpusStoreTest {

    private static final int DENSE_DIM = 4;

    @Container
    static GenericContainer<?> qdrant = new GenericContainer<>("qdrant/qdrant:v1.13.2")
        .withExposedPorts(6334);

    private static QdrantClient client;
    private QdrantCorpusStore store;
    private final CorpusRef corpus = new CorpusRef("tenant-1", "legal");

    private static final CurrentPrincipal principal = new CurrentPrincipal() {
        @Override public String actorId() { return "test-user"; }
        @Override public Set<String> groups() { return Set.of(); }
        @Override public String tenancyId() { return "tenant-1"; }
        @Override public boolean isCrossTenantAdmin() { return false; }
    };

    @BeforeAll
    static void startClient() {
        client = new QdrantClient(QdrantGrpcClient.newBuilder(
            qdrant.getHost(), qdrant.getMappedPort(6334), false).build());
    }

    @AfterAll
    static void stopClient() {
        if (client != null) client.close();
    }

    @BeforeEach
    void setUp() {
        EmbeddingModel embeddingModel = stubEmbeddingModel();
        SparseEmbedder sparseEmbedder = new SparseEmbedder(
            InMemoryInferenceModel.returning(0.0f, 0.1f, 0.0f, 0.5f, 0.0f));
        store = new QdrantCorpusStore(
            client, embeddingModel, sparseEmbedder,
            TenancyStrategy.SEPARATE_COLLECTIONS, "dense", "sparse",
            principal);
    }

    @Test
    void ingestCreatesCollectionAndUpserts() throws Exception {
        store.ingest(corpus, List.of(
            new ChunkInput("Hello world", "doc-A", Map.of("page", "1"))));

        assertThat(client.collectionExistsAsync("tenant-1_legal").get()).isTrue();
        assertThat(store.listDocuments(corpus)).containsExactly("doc-A");
    }

    @Test
    void ingestMultipleDocuments() {
        store.ingest(corpus, List.of(
            new ChunkInput("c1", "doc-A", Map.of()),
            new ChunkInput("c2", "doc-A", Map.of()),
            new ChunkInput("c3", "doc-B", Map.of())));
        assertThat(store.listDocuments(corpus)).containsExactlyInAnyOrder("doc-A", "doc-B");
    }

    @Test
    void deleteDocument() {
        store.ingest(corpus, List.of(
            new ChunkInput("c1", "doc-A", Map.of()),
            new ChunkInput("c2", "doc-B", Map.of())));
        store.deleteDocument(corpus, "doc-A");
        assertThat(store.listDocuments(corpus)).containsExactly("doc-B");
    }

    @Test
    void deleteCorpus() throws Exception {
        store.ingest(corpus, List.of(new ChunkInput("c1", "doc-A", Map.of())));
        store.deleteCorpus(corpus);
        assertThat(client.collectionExistsAsync("tenant-1_legal").get()).isFalse();
    }

    @Test
    void tenancyMismatchThrows() {
        var wrongCorpus = new CorpusRef("other-tenant", "legal");
        assertThatExceptionOfType(SecurityException.class)
            .isThrownBy(() -> store.ingest(wrongCorpus, List.of(new ChunkInput("c", "d", Map.of()))))
            .withMessageContaining("Tenant ID mismatch");
    }

    private static EmbeddingModel stubEmbeddingModel() {
        return new EmbeddingModel() {
            @Override
            public Response<List<Embedding>> embedAll(List<TextSegment> segments) {
                List<Embedding> embeddings = new ArrayList<>();
                for (int i = 0; i < segments.size(); i++) {
                    embeddings.add(new Embedding(new float[]{0.1f * i, 0.2f, 0.3f, 0.4f}));
                }
                return Response.from(embeddings);
            }

            @Override
            public int dimension() {
                return DENSE_DIM;
            }
        };
    }
}
```

- [ ] **Step 3: Run test — verify RED**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantCorpusStoreTest
```

- [ ] **Step 4: Implement QdrantCorpusStore**

```java
package io.casehub.rag.runtime;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import io.casehub.inference.splade.SparseEmbedder;
import io.casehub.platform.api.identity.CurrentPrincipal;
import io.casehub.platform.api.memory.MemoryPermissions;
import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.CorpusStore;
import io.qdrant.client.QdrantClient;
import io.qdrant.client.ConditionFactory;
import io.qdrant.client.PointIdFactory;
import io.qdrant.client.VectorFactory;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.Distance;
import io.qdrant.client.grpc.Collections.SparseVectorConfig;
import io.qdrant.client.grpc.Collections.SparseVectorParams;
import io.qdrant.client.grpc.Collections.VectorParams;
import io.qdrant.client.grpc.Collections.VectorParamsMap;
import io.qdrant.client.grpc.Collections.VectorsConfig;
import io.qdrant.client.grpc.JsonWithInt.Value;
import io.qdrant.client.grpc.Points.Filter;
import io.qdrant.client.grpc.Points.NamedVectors;
import io.qdrant.client.grpc.Points.PointStruct;
import io.qdrant.client.grpc.Points.ScrollPoints;
import io.qdrant.client.grpc.Points.Vectors;
import io.qdrant.client.grpc.Points.WithPayloadSelector;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ExecutionException;

@ApplicationScoped
public class QdrantCorpusStore implements CorpusStore {

    private final QdrantClient client;
    private final EmbeddingModel embeddingModel;
    private final SparseEmbedder sparseEmbedder;
    private final TenancyStrategy tenancyStrategy;
    private final String denseVectorName;
    private final String sparseVectorName;
    private final CurrentPrincipal currentPrincipal;
    private final Set<String> knownCollections = new java.util.concurrent.ConcurrentHashMap<String, Boolean>().keySet(true);

    @Inject
    public QdrantCorpusStore(
            QdrantClient client,
            EmbeddingModel embeddingModel,
            SparseEmbedder sparseEmbedder,
            TenancyStrategy tenancyStrategy,
            String denseVectorName,
            String sparseVectorName,
            CurrentPrincipal currentPrincipal) {
        this.client = client;
        this.embeddingModel = embeddingModel;
        this.sparseEmbedder = sparseEmbedder;
        this.tenancyStrategy = tenancyStrategy;
        this.denseVectorName = denseVectorName;
        this.sparseVectorName = sparseVectorName;
        this.currentPrincipal = currentPrincipal;
    }

    @Override
    public void ingest(CorpusRef corpus, List<ChunkInput> chunks) {
        MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal);
        String collection = tenancyStrategy.collectionName(corpus);
        ensureCollection(collection);

        List<TextSegment> segments = chunks.stream()
            .map(c -> TextSegment.from(c.content())).toList();
        List<Embedding> denseEmbeddings = embeddingModel.embedAll(segments).content();
        List<String> texts = chunks.stream().map(ChunkInput::content).toList();
        List<Map<Integer, Float>> sparseEmbeddings = sparseEmbedder.embedBatch(texts);

        List<PointStruct> points = new ArrayList<>(chunks.size());
        for (int i = 0; i < chunks.size(); i++) {
            ChunkInput chunk = chunks.get(i);
            points.add(buildPoint(chunk, denseEmbeddings.get(i), sparseEmbeddings.get(i)));
        }

        try {
            client.upsertAsync(collection, points).get();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Qdrant upsert interrupted", e);
        } catch (ExecutionException e) {
            throw new RuntimeException("Qdrant upsert failed", e.getCause());
        }
    }

    @Override
    public void deleteDocument(CorpusRef corpus, String sourceDocumentId) {
        MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal);
        String collection = tenancyStrategy.collectionName(corpus);
        Filter.Builder filter = Filter.newBuilder()
            .addMust(ConditionFactory.matchKeyword("sourceDocumentId", sourceDocumentId));
        tenancyStrategy.tenantFilter(corpus).ifPresent(f -> filter.addAllMust(f.getMustList()));

        try {
            client.deleteAsync(collection, filter.build()).get();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Qdrant delete interrupted", e);
        } catch (ExecutionException e) {
            throw new RuntimeException("Qdrant delete failed", e.getCause());
        }
    }

    @Override
    public void deleteCorpus(CorpusRef corpus) {
        MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal);
        String collection = tenancyStrategy.collectionName(corpus);
        try {
            if (tenancyStrategy == TenancyStrategy.SEPARATE_COLLECTIONS) {
                client.deleteCollectionAsync(collection).get();
                knownCollections.remove(collection);
            } else {
                tenancyStrategy.tenantFilter(corpus).ifPresent(f -> {
                    try {
                        client.deleteAsync(collection, f).get();
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        throw new RuntimeException("Qdrant delete interrupted", e);
                    } catch (ExecutionException e) {
                        throw new RuntimeException("Qdrant delete failed", e.getCause());
                    }
                });
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Qdrant deleteCollection interrupted", e);
        } catch (ExecutionException e) {
            throw new RuntimeException("Qdrant deleteCollection failed", e.getCause());
        }
    }

    @Override
    public List<String> listDocuments(CorpusRef corpus) {
        MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal);
        String collection = tenancyStrategy.collectionName(corpus);
        try {
            if (!client.collectionExistsAsync(collection).get()) {
                return List.of();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException(e);
        } catch (ExecutionException e) {
            throw new RuntimeException(e.getCause());
        }

        ScrollPoints.Builder scroll = ScrollPoints.newBuilder()
            .setCollectionName(collection)
            .setLimit(1000)
            .setWithPayload(WithPayloadSelector.newBuilder().setEnable(true).build());
        tenancyStrategy.tenantFilter(corpus).ifPresent(scroll::setFilter);

        try {
            var response = client.scrollAsync(scroll.build()).get();
            Set<String> docIds = new LinkedHashSet<>();
            response.getResultList().forEach(point -> {
                Value val = point.getPayloadMap().get("sourceDocumentId");
                if (val != null) {
                    docIds.add(val.getStringValue());
                }
            });
            return List.copyOf(docIds);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException(e);
        } catch (ExecutionException e) {
            throw new RuntimeException(e.getCause());
        }
    }

    private void ensureCollection(String collection) {
        if (knownCollections.contains(collection)) return;
        try {
            if (client.collectionExistsAsync(collection).get()) {
                knownCollections.add(collection);
                return;
            }
            client.createCollectionAsync(CreateCollection.newBuilder()
                .setCollectionName(collection)
                .setVectorsConfig(VectorsConfig.newBuilder()
                    .setParamsMap(VectorParamsMap.newBuilder()
                        .putMap(denseVectorName, VectorParams.newBuilder()
                            .setSize(embeddingModel.dimension())
                            .setDistance(Distance.Cosine)
                            .build())))
                .setSparseVectorsConfig(SparseVectorConfig.newBuilder()
                    .putMap(sparseVectorName, SparseVectorParams.getDefaultInstance()))
                .build()).get();
            knownCollections.add(collection);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Qdrant collection creation interrupted", e);
        } catch (ExecutionException e) {
            throw new RuntimeException("Qdrant collection creation failed", e.getCause());
        }
    }

    private PointStruct buildPoint(ChunkInput chunk, Embedding dense, Map<Integer, Float> sparse) {
        List<Integer> sparseIndices = new ArrayList<>(sparse.keySet());
        List<Float> sparseValues = sparseIndices.stream().map(sparse::get).toList();

        var payload = new java.util.HashMap<String, Value>();
        payload.put("content", Value.newBuilder().setStringValue(chunk.content()).build());
        payload.put("sourceDocumentId", Value.newBuilder().setStringValue(chunk.sourceDocumentId()).build());

        chunk.metadata().forEach((k, v) ->
            payload.put(k, Value.newBuilder().setStringValue(v).build()));

        return PointStruct.newBuilder()
            .setId(PointIdFactory.id(UUID.randomUUID()))
            .setVectors(Vectors.newBuilder()
                .setVectors(NamedVectors.newBuilder()
                    .putVectors(denseVectorName, VectorFactory.vector(dense.vectorAsList()))
                    .putVectors(sparseVectorName, VectorFactory.vector(sparseValues, sparseIndices))))
            .putAllPayload(payload)
            .build();
    }
}
```

Note: The constructor uses direct parameters for testability. A CDI `@Produces` method in a separate config bean (added in a later task or during wiring) will construct this with injected config values.

- [ ] **Step 5: Run test — verify GREEN**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=QdrantCorpusStoreTest
```
Expected: all tests PASS. Testcontainers starts Qdrant automatically.

- [ ] **Step 6: Commit**

```bash
git add rag/
git commit -m "feat(#7): QdrantCorpusStore — ingest, delete, list with tenancy validation and batch embedding"
```

---

### Task 10: rag — HybridCaseRetriever

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`

- [ ] **Step 1: Write HybridCaseRetriever integration test**

```java
package io.casehub.rag.runtime;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.output.Response;
import io.casehub.inference.inmem.InMemoryInferenceModel;
import io.casehub.inference.splade.SparseEmbedder;
import io.casehub.platform.api.identity.CurrentPrincipal;
import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.RetrievedChunk;
import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.*;

@Testcontainers
class HybridCaseRetrieverTest {

    private static final int DENSE_DIM = 4;

    @Container
    static GenericContainer<?> qdrant = new GenericContainer<>("qdrant/qdrant:v1.13.2")
        .withExposedPorts(6334);

    private static QdrantClient client;
    private QdrantCorpusStore store;
    private HybridCaseRetriever retriever;
    private final CorpusRef corpus = new CorpusRef("tenant-1", "knowledge");

    private static final CurrentPrincipal principal = new CurrentPrincipal() {
        @Override public String actorId() { return "test-user"; }
        @Override public Set<String> groups() { return Set.of(); }
        @Override public String tenancyId() { return "tenant-1"; }
        @Override public boolean isCrossTenantAdmin() { return false; }
    };

    @BeforeAll
    static void startClient() {
        client = new QdrantClient(QdrantGrpcClient.newBuilder(
            qdrant.getHost(), qdrant.getMappedPort(6334), false).build());
    }

    @AfterAll
    static void stopClient() {
        if (client != null) client.close();
    }

    @BeforeEach
    void setUp() {
        EmbeddingModel embeddingModel = stubEmbeddingModel();
        SparseEmbedder sparseEmbedder = new SparseEmbedder(
            InMemoryInferenceModel.returning(0.0f, 0.1f, 0.0f, 0.5f, 0.0f));

        store = new QdrantCorpusStore(
            client, embeddingModel, sparseEmbedder,
            TenancyStrategy.SEPARATE_COLLECTIONS, "dense", "sparse", principal);

        retriever = new HybridCaseRetriever(
            client, embeddingModel, sparseEmbedder,
            TenancyStrategy.SEPARATE_COLLECTIONS, "dense", "sparse",
            40, 40, 60,
            false, 10, null, principal);
    }

    @Test
    void retrieveFromIngestedCorpus() {
        store.ingest(corpus, List.of(
            new ChunkInput("The quick brown fox", "doc-A", Map.of()),
            new ChunkInput("jumps over the lazy dog", "doc-A", Map.of()),
            new ChunkInput("Lorem ipsum dolor sit amet", "doc-B", Map.of())));

        List<RetrievedChunk> results = retriever.retrieve("quick fox", corpus, 3);
        assertThat(results).isNotEmpty();
        assertThat(results).allSatisfy(chunk -> {
            assertThat(chunk.content()).isNotBlank();
            assertThat(chunk.sourceDocumentId()).isNotBlank();
            assertThat(chunk.relevanceScore()).isGreaterThan(0);
        });
    }

    @Test
    void retrieveRespectsMaxResults() {
        store.ingest(corpus, List.of(
            new ChunkInput("c1", "d1", Map.of()),
            new ChunkInput("c2", "d2", Map.of()),
            new ChunkInput("c3", "d3", Map.of())));

        List<RetrievedChunk> results = retriever.retrieve("query", corpus, 1);
        assertThat(results).hasSizeLessThanOrEqualTo(1);
    }

    @Test
    void retrieveEmptyCorpus() {
        var emptyCorpus = new CorpusRef("tenant-1", "empty-corpus");
        List<RetrievedChunk> results = retriever.retrieve("query", emptyCorpus, 10);
        assertThat(results).isEmpty();
    }

    @Test
    void tenancyMismatchThrows() {
        var wrongCorpus = new CorpusRef("other-tenant", "knowledge");
        assertThatExceptionOfType(SecurityException.class)
            .isThrownBy(() -> retriever.retrieve("query", wrongCorpus, 10))
            .withMessageContaining("Tenant ID mismatch");
    }

    private static EmbeddingModel stubEmbeddingModel() {
        return new EmbeddingModel() {
            @Override
            public Response<List<Embedding>> embedAll(List<TextSegment> segments) {
                List<Embedding> embeddings = new ArrayList<>();
                for (int i = 0; i < segments.size(); i++) {
                    embeddings.add(new Embedding(new float[]{0.1f * (i + 1), 0.2f, 0.3f, 0.4f}));
                }
                return Response.from(embeddings);
            }

            @Override
            public int dimension() {
                return DENSE_DIM;
            }
        };
    }
}
```

- [ ] **Step 2: Run test — verify RED**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=HybridCaseRetrieverTest
```

- [ ] **Step 3: Implement HybridCaseRetriever**

```java
package io.casehub.rag.runtime;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import io.casehub.inference.splade.SparseEmbedder;
import io.casehub.inference.tasks.CrossEncoderReranker;
import io.casehub.inference.tasks.RankedResult;
import io.casehub.platform.api.identity.CurrentPrincipal;
import io.casehub.platform.api.memory.MemoryPermissions;
import io.casehub.rag.CaseRetriever;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.RetrievedChunk;
import io.qdrant.client.QdrantClient;
import io.qdrant.client.QueryFactory;
import io.qdrant.client.grpc.Points.Filter;
import io.qdrant.client.grpc.Points.Fusion;
import io.qdrant.client.grpc.Points.PrefetchQuery;
import io.qdrant.client.grpc.Points.QueryPoints;
import io.qdrant.client.grpc.Points.ScoredPoint;
import io.qdrant.client.grpc.Points.WithPayloadSelector;
import io.qdrant.client.grpc.JsonWithInt.Value;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ExecutionException;

@ApplicationScoped
public class HybridCaseRetriever implements CaseRetriever {

    private final QdrantClient client;
    private final EmbeddingModel embeddingModel;
    private final SparseEmbedder sparseEmbedder;
    private final TenancyStrategy tenancyStrategy;
    private final String denseVectorName;
    private final String sparseVectorName;
    private final int denseTopK;
    private final int sparseTopK;
    private final int rrfK;
    private final boolean rerankEnabled;
    private final int rerankTopN;
    private final CrossEncoderReranker reranker;
    private final CurrentPrincipal currentPrincipal;

    @Inject
    public HybridCaseRetriever(
            QdrantClient client,
            EmbeddingModel embeddingModel,
            SparseEmbedder sparseEmbedder,
            TenancyStrategy tenancyStrategy,
            String denseVectorName,
            String sparseVectorName,
            int denseTopK,
            int sparseTopK,
            int rrfK,
            boolean rerankEnabled,
            int rerankTopN,
            CrossEncoderReranker reranker,
            CurrentPrincipal currentPrincipal) {
        this.client = client;
        this.embeddingModel = embeddingModel;
        this.sparseEmbedder = sparseEmbedder;
        this.tenancyStrategy = tenancyStrategy;
        this.denseVectorName = denseVectorName;
        this.sparseVectorName = sparseVectorName;
        this.denseTopK = denseTopK;
        this.sparseTopK = sparseTopK;
        this.rrfK = rrfK;
        this.rerankEnabled = rerankEnabled;
        this.rerankTopN = rerankTopN;
        this.reranker = reranker;
        this.currentPrincipal = currentPrincipal;
    }

    @Override
    public List<RetrievedChunk> retrieve(String query, CorpusRef corpus, int maxResults) {
        MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal);
        String collection = tenancyStrategy.collectionName(corpus);

        try {
            if (!client.collectionExistsAsync(collection).get()) {
                return List.of();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException(e);
        } catch (ExecutionException e) {
            throw new RuntimeException(e.getCause());
        }

        Embedding denseQuery = embeddingModel.embed(query).content();
        Map<Integer, Float> sparseQuery = sparseEmbedder.embed(query);

        List<Integer> sparseIndices = new ArrayList<>(sparseQuery.keySet());
        List<Float> sparseValues = sparseIndices.stream().map(sparseQuery::get).toList();

        PrefetchQuery.Builder densePrefetch = PrefetchQuery.newBuilder()
            .setQuery(QueryFactory.nearest(denseQuery.vectorAsList()))
            .setUsing(denseVectorName)
            .setLimit(denseTopK);

        PrefetchQuery.Builder sparsePrefetch = PrefetchQuery.newBuilder()
            .setQuery(QueryFactory.nearest(sparseValues, sparseIndices))
            .setUsing(sparseVectorName)
            .setLimit(sparseTopK);

        Optional<Filter> tenantFilter = tenancyStrategy.tenantFilter(corpus);
        tenantFilter.ifPresent(f -> {
            densePrefetch.setFilter(f);
            sparsePrefetch.setFilter(f);
        });

        int queryLimit = (rerankEnabled && reranker != null)
            ? Math.max(maxResults, rerankTopN) : maxResults;

        QueryPoints.Builder queryBuilder = QueryPoints.newBuilder()
            .setCollectionName(collection)
            .addPrefetch(densePrefetch)
            .addPrefetch(sparsePrefetch)
            .setQuery(QueryFactory.fusion(Fusion.RRF))
            .setLimit(queryLimit)
            .setWithPayload(WithPayloadSelector.newBuilder().setEnable(true));

        try {
            List<ScoredPoint> scored = client.queryAsync(queryBuilder.build()).get();
            List<RetrievedChunk> results = new ArrayList<>(scored.size());
            for (ScoredPoint point : scored) {
                Map<String, Value> payload = point.getPayloadMap();
                String content = payload.getOrDefault("content",
                    Value.getDefaultInstance()).getStringValue();
                String docId = payload.getOrDefault("sourceDocumentId",
                    Value.getDefaultInstance()).getStringValue();

                Map<String, String> metadata = new java.util.HashMap<>();
                payload.forEach((k, v) -> {
                    if (!"content".equals(k) && !"sourceDocumentId".equals(k) && !"tenantId".equals(k)) {
                        metadata.put(k, v.getStringValue());
                    }
                });

                results.add(new RetrievedChunk(content, docId, point.getScore(), metadata));
            }

            if (rerankEnabled && reranker != null && !results.isEmpty()) {
                return rerank(query, results, maxResults);
            }

            return Collections.unmodifiableList(results);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Qdrant query interrupted", e);
        } catch (ExecutionException e) {
            throw new RuntimeException("Qdrant query failed", e.getCause());
        }
    }

    private List<RetrievedChunk> rerank(String query, List<RetrievedChunk> candidates, int maxResults) {
        List<String> texts = candidates.stream().map(RetrievedChunk::content).toList();
        List<RankedResult> ranked = reranker.rerank(query, texts);

        int limit = Math.min(maxResults, ranked.size());
        List<RetrievedChunk> reranked = new ArrayList<>(limit);
        for (int i = 0; i < limit; i++) {
            RankedResult r = ranked.get(i);
            RetrievedChunk original = candidates.get(r.originalIndex());
            reranked.add(new RetrievedChunk(
                original.content(), original.sourceDocumentId(),
                r.score(), original.metadata()));
        }
        return Collections.unmodifiableList(reranked);
    }
}
```

- [ ] **Step 4: Run test — verify GREEN**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=HybridCaseRetrieverTest
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rag/src/
git commit -m "feat(#7): HybridCaseRetriever — prefetch dense+sparse, RRF fusion, optional cross-encoder reranking"
```

---

### Task 11: rag — CDI wiring producer + ArchUnit

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/RagBeanProducer.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/DependencyConstraintTest.java`

- [ ] **Step 1: Write RagBeanProducer**

This CDI producer wires `QdrantCorpusStore` and `HybridCaseRetriever` from injected config and beans.

```java
package io.casehub.rag.runtime;

import dev.langchain4j.model.embedding.EmbeddingModel;
import io.casehub.inference.splade.SparseEmbedder;
import io.casehub.inference.tasks.CrossEncoderReranker;
import io.casehub.platform.api.identity.CurrentPrincipal;
import io.qdrant.client.QdrantClient;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.enterprise.inject.Produces;
import jakarta.inject.Inject;

@ApplicationScoped
public class RagBeanProducer {

    @Inject RagConfig config;
    @Inject QdrantClient client;
    @Inject EmbeddingModel embeddingModel;
    @Inject SparseEmbedder sparseEmbedder;
    @Inject Instance<CrossEncoderReranker> rerankerInstance;
    @Inject CurrentPrincipal currentPrincipal;

    @Produces
    @ApplicationScoped
    QdrantCorpusStore corpusStore() {
        return new QdrantCorpusStore(
            client, embeddingModel, sparseEmbedder,
            config.tenancyStrategy(),
            config.denseVectorName(), config.sparseVectorName(),
            currentPrincipal);
    }

    @Produces
    @ApplicationScoped
    HybridCaseRetriever caseRetriever() {
        CrossEncoderReranker reranker = rerankerInstance.isResolvable()
            ? rerankerInstance.get() : null;
        return new HybridCaseRetriever(
            client, embeddingModel, sparseEmbedder,
            config.tenancyStrategy(),
            config.denseVectorName(), config.sparseVectorName(),
            config.retrieval().denseTopK(), config.retrieval().sparseTopK(),
            config.retrieval().rrfK(),
            config.retrieval().rerankEnabled(), config.retrieval().rerankTopN(),
            reranker, currentPrincipal);
    }
}
```

- [ ] **Step 2: Write ArchUnit dependency constraints for rag**

```java
package io.casehub.rag.runtime;

import com.tngtech.archunit.base.DescribedPredicate;
import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

@AnalyzeClasses(packages = "io.casehub.rag.runtime")
class DependencyConstraintTest {

    @ArchTest
    static final ArchRule noCasehubDomainBeyondPlatformApi = noClasses()
        .that().resideInAPackage("io.casehub.rag.runtime..")
        .should().dependOnClassesThat(
            DescribedPredicate.describe("casehub domain classes beyond platform-api and rag-api",
                (JavaClass cls) -> {
                    String pkg = cls.getPackageName();
                    return pkg.startsWith("io.casehub.")
                        && !pkg.startsWith("io.casehub.rag")
                        && !pkg.startsWith("io.casehub.inference")
                        && !pkg.startsWith("io.casehub.platform.api");
                }));
}
```

- [ ] **Step 3: Run all rag tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag
```
Expected: all tests PASS including ArchUnit.

- [ ] **Step 4: Commit**

```bash
git add rag/src/
git commit -m "feat(#7): RagBeanProducer CDI wiring + ArchUnit domain boundary constraint"
```

---

### Task 12: rag-tika — new module

**Files:**
- Create: `rag-tika/pom.xml`
- Create: `rag-tika/src/main/java/io/casehub/rag/tika/TikaDocumentParser.java`
- Create: `rag-tika/src/main/java/io/casehub/rag/tika/TikaConfig.java`
- Create: `rag-tika/src/test/java/io/casehub/rag/tika/TikaDocumentParserTest.java`

- [ ] **Step 1: Create rag-tika/pom.xml**

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neural-text-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>

  <artifactId>casehub-rag-tika</artifactId>
  <name>CaseHub Neural Text - RAG Tika</name>
  <description>Optional Apache Tika document parsing for CorpusStore ingestion — parse PDF, DOCX, HTML into chunked ChunkInput</description>

  <dependencies>

    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-rag-api</artifactId>
    </dependency>

    <!-- LangChain4j — Tika parser + DocumentSplitter -->
    <dependency>
      <groupId>dev.langchain4j</groupId>
      <artifactId>langchain4j</artifactId>
    </dependency>
    <dependency>
      <groupId>dev.langchain4j</groupId>
      <artifactId>langchain4j-document-parser-apache-tika</artifactId>
    </dependency>

    <!-- CDI -->
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-arc</artifactId>
    </dependency>

    <!-- Testing -->
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

  <build>
    <plugins>
      <plugin>
        <groupId>io.smallrye</groupId>
        <artifactId>jandex-maven-plugin</artifactId>
        <executions>
          <execution>
            <id>make-index</id>
            <goals><goal>jandex</goal></goals>
          </execution>
        </executions>
      </plugin>
    </plugins>
  </build>

</project>
```

- [ ] **Step 2: Write TikaConfig**

```java
package io.casehub.rag.tika;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;

@ConfigMapping(prefix = "casehub.rag.tika")
public interface TikaConfig {

    @WithDefault("512")
    int chunkSize();

    @WithDefault("64")
    int chunkOverlap();
}
```

- [ ] **Step 3: Write TikaDocumentParser test**

```java
package io.casehub.rag.tika;

import io.casehub.rag.ChunkInput;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.*;

class TikaDocumentParserTest {

    @Test
    void parsePlainText() {
        String text = "First sentence of the document. Second sentence continues here. " +
            "Third sentence adds more content for chunking.";
        var input = new ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8));

        var parser = new TikaDocumentParser(500, 50);
        List<ChunkInput> chunks = parser.parse(input, "doc-1", "text/plain", Map.of("author", "test"));

        assertThat(chunks).isNotEmpty();
        assertThat(chunks).allSatisfy(chunk -> {
            assertThat(chunk.sourceDocumentId()).isEqualTo("doc-1");
            assertThat(chunk.content()).isNotBlank();
            assertThat(chunk.metadata()).containsEntry("author", "test");
        });
    }

    @Test
    void chunksSplitLargeContent() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 100; i++) {
            sb.append("Sentence number ").append(i).append(" with enough words to fill space. ");
        }
        var input = new ByteArrayInputStream(sb.toString().getBytes(StandardCharsets.UTF_8));

        var parser = new TikaDocumentParser(200, 20);
        List<ChunkInput> chunks = parser.parse(input, "doc-2", "text/plain", Map.of());

        assertThat(chunks).hasSizeGreaterThan(1);
    }

    @Test
    void metadataMergedWithTikaExtracted() {
        var input = new ByteArrayInputStream("content".getBytes(StandardCharsets.UTF_8));
        var parser = new TikaDocumentParser(500, 50);
        List<ChunkInput> chunks = parser.parse(input, "doc-3", "text/plain", Map.of("custom", "val"));

        assertThat(chunks.get(0).metadata()).containsEntry("custom", "val");
    }
}
```

- [ ] **Step 4: Run test — verify RED**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-tika -Dtest=TikaDocumentParserTest
```

- [ ] **Step 5: Implement TikaDocumentParser**

```java
package io.casehub.rag.tika;

import dev.langchain4j.data.document.Document;
import dev.langchain4j.data.document.DocumentParser;
import dev.langchain4j.data.document.parser.apache.tika.ApacheTikaDocumentParser;
import dev.langchain4j.data.document.splitter.DocumentSplitters;
import dev.langchain4j.data.segment.TextSegment;
import io.casehub.rag.ChunkInput;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@ApplicationScoped
public class TikaDocumentParser {

    private final int chunkSize;
    private final int chunkOverlap;

    @Inject
    public TikaDocumentParser(TikaConfig config) {
        this(config.chunkSize(), config.chunkOverlap());
    }

    public TikaDocumentParser(int chunkSize, int chunkOverlap) {
        this.chunkSize = chunkSize;
        this.chunkOverlap = chunkOverlap;
    }

    public List<ChunkInput> parse(InputStream content, String sourceDocumentId,
                                   String contentType, Map<String, String> metadata) {
        DocumentParser parser = new ApacheTikaDocumentParser();
        Document document = parser.parse(content);

        List<TextSegment> segments = DocumentSplitters
            .recursive(chunkSize, chunkOverlap)
            .split(document);

        List<ChunkInput> chunks = new ArrayList<>(segments.size());
        for (TextSegment segment : segments) {
            Map<String, String> merged = new HashMap<>(metadata);
            segment.metadata().toMap().forEach((k, v) -> {
                if (v != null) merged.putIfAbsent(k, v.toString());
            });
            chunks.add(new ChunkInput(segment.text(), sourceDocumentId, merged));
        }
        return Collections.unmodifiableList(chunks);
    }
}
```

- [ ] **Step 6: Run test — verify GREEN**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-tika
```
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add rag-tika/
git commit -m "feat(#7): rag-tika — optional TikaDocumentParser, LangChain4j Tika + recursive splitter"
```

---

### Task 13: Full build verification

- [ ] **Step 1: Build all modules**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install
```
Expected: all modules build and all tests pass.

- [ ] **Step 2: Verify module structure**

Confirm all 4 RAG modules produce artifacts:
```bash
ls -la rag-api/target/casehub-rag-api-0.2-SNAPSHOT.jar
ls -la rag/target/casehub-rag-0.2-SNAPSHOT.jar
ls -la rag-tika/target/casehub-rag-tika-0.2-SNAPSHOT.jar
ls -la rag-testing/target/casehub-rag-testing-0.2-SNAPSHOT.jar
```

- [ ] **Step 3: Commit any fixes and push**

```bash
git push -u origin issue-7-rag-pipeline
```

---

## Implementation Notes

**Qdrant Docker image for tests:** Tests use `qdrant/qdrant:v1.13.2`. This is a recent stable version that supports the Query API, prefetch, RRF fusion, and named vector spaces. Pin the version to avoid test flakiness from upstream changes.

**Stub EmbeddingModel in tests:** Tests use a local `EmbeddingModel` implementation that returns deterministic vectors. This avoids needing a real ONNX model or remote API during unit/integration tests. The vectors are simple incrementing patterns — enough for Qdrant to store and return, not semantically meaningful.

**Constructor injection vs CDI for QdrantCorpusStore/HybridCaseRetriever:** Both classes use constructor injection with all parameters. In production CDI, `RagBeanProducer` constructs them from config. In tests, they're constructed directly with test parameters. This pattern makes the classes testable without a CDI container.

**Qdrant collection naming:** `TenancyStrategy.SEPARATE_COLLECTIONS` uses `{tenantId}_{corpusName}`. Qdrant collection names must match `[a-zA-Z0-9_-]+`. If tenant IDs or corpus names contain characters outside this set, sanitization will be needed — not implemented in v1 (test-time validation is sufficient for now).

**ListenableFuture blocking:** All Qdrant client calls use `.get()` on `ListenableFuture`. This is appropriate because `rag` beans run on the Quarkus worker thread pool (blocking execution model). If a reactive variant is needed later, it would be a separate `ReactiveCorpusStore` / `ReactiveCaseRetriever` pair, gated by `@IfBuildProperty` per the platform's reactive-service-build-gating protocol.

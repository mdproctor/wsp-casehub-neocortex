# Reactive CorpusStore + CaseRetriever Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reactive SPI interfaces (`ReactiveCorpusStore`, `ReactiveCaseRetriever`) to `rag-api`, with `@DefaultBean` bridges in `rag` and in-memory stubs in `rag-testing`.

**Architecture:** Mutiny `provided` in `rag-api` (ledger-api/eidos-api pattern). Reactive interfaces mirror blocking ones with `Uni<T>` return types. Bridges in `rag` wrap blocking delegates on the worker pool. In-memory reactive stubs in `rag-testing` delegate to blocking stubs without thread offloading. Parity enforced by ArchUnit.

**Tech Stack:** Java 21, SmallRye Mutiny, Quarkus CDI (quarkus-arc), ArchUnit 1.4.1

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `rag-api/pom.xml` | Add Mutiny `provided` dep |
| Create | `rag-api/src/main/java/io/casehub/rag/ReactiveCorpusStore.java` | Reactive SPI interface |
| Create | `rag-api/src/main/java/io/casehub/rag/ReactiveCaseRetriever.java` | Reactive SPI interface |
| Create | `rag-api/src/test/java/io/casehub/rag/BlockingReactiveParityTest.java` | ArchUnit parity test |
| Modify | `rag-testing/pom.xml` | Add Mutiny dep |
| Modify | `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCorpusStore.java` | Add `@ApplicationScoped` |
| Modify | `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCaseRetriever.java` | Add `@ApplicationScoped` |
| Create | `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryReactiveCorpusStore.java` | Reactive in-memory stub |
| Create | `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryReactiveCaseRetriever.java` | Reactive in-memory stub |
| Create | `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryReactiveCorpusStoreTest.java` | Stub test |
| Create | `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryReactiveCaseRetrieverTest.java` | Stub test |
| Create | `rag/src/main/java/io/casehub/rag/runtime/BlockingToReactiveCorpusStore.java` | Bridge `@DefaultBean` |
| Create | `rag/src/main/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetriever.java` | Bridge `@DefaultBean` |
| Create | `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCorpusStoreTest.java` | Bridge test |
| Create | `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java` | Bridge test |

---

### Task 1: Reactive SPI interfaces in rag-api

**Files:**
- Modify: `rag-api/pom.xml`
- Create: `rag-api/src/main/java/io/casehub/rag/ReactiveCorpusStore.java`
- Create: `rag-api/src/main/java/io/casehub/rag/ReactiveCaseRetriever.java`

- [ ] **Step 1: Add Mutiny provided dependency to rag-api/pom.xml**

Add after the existing `</description>` comment and before the `<dependencies>` block:

```xml
<!-- Mutiny for reactive SPI variants -->
<dependency>
    <groupId>io.smallrye.reactive</groupId>
    <artifactId>mutiny</artifactId>
    <scope>provided</scope>
</dependency>
```

Insert inside `<dependencies>`, before the test deps.

- [ ] **Step 2: Create ReactiveCorpusStore interface**

Create `rag-api/src/main/java/io/casehub/rag/ReactiveCorpusStore.java`:

```java
package io.casehub.rag;

import io.smallrye.mutiny.Uni;
import java.util.List;

public interface ReactiveCorpusStore {
    Uni<Void> ingest(CorpusRef corpus, List<ChunkInput> chunks);
    Uni<Void> deleteDocument(CorpusRef corpus, String sourceDocumentId);
    Uni<Void> deleteCorpus(CorpusRef corpus);
    Uni<List<String>> listDocuments(CorpusRef corpus);
}
```

- [ ] **Step 3: Create ReactiveCaseRetriever interface**

Create `rag-api/src/main/java/io/casehub/rag/ReactiveCaseRetriever.java`:

```java
package io.casehub.rag;

import io.smallrye.mutiny.Uni;
import java.util.List;

public interface ReactiveCaseRetriever {
    Uni<List<RetrievedChunk>> retrieve(String query, CorpusRef corpus, int maxResults);
}
```

- [ ] **Step 4: Verify build passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl rag-api -DskipTests`
Expected: BUILD SUCCESS

- [ ] **Step 5: Commit**

```bash
git add rag-api/pom.xml rag-api/src/main/java/io/casehub/rag/ReactiveCorpusStore.java rag-api/src/main/java/io/casehub/rag/ReactiveCaseRetriever.java
git commit -m "feat(#11): rag-api — ReactiveCorpusStore, ReactiveCaseRetriever SPIs with Mutiny provided"
```

---

### Task 2: Blocking/reactive parity ArchUnit test

**Files:**
- Create: `rag-api/src/test/java/io/casehub/rag/BlockingReactiveParityTest.java`

- [ ] **Step 1: Write the parity test**

Create `rag-api/src/test/java/io/casehub/rag/BlockingReactiveParityTest.java`:

```java
package io.casehub.rag;

import io.smallrye.mutiny.Uni;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import java.util.Arrays;
import java.util.Map;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

class BlockingReactiveParityTest {

    private static final Map<Class<?>, Class<?>> PAIRS = Map.of(
        CorpusStore.class, ReactiveCorpusStore.class,
        CaseRetriever.class, ReactiveCaseRetriever.class
    );

    @Test
    void vacuousPassGuard() {
        assertThat(PAIRS).isNotEmpty();
    }

    @Test
    void everyBlockingMethodHasReactiveEquivalent() {
        for (var entry : PAIRS.entrySet()) {
            Class<?> blocking = entry.getKey();
            Class<?> reactive = entry.getValue();
            Map<String, Method> reactiveMethods = Arrays.stream(reactive.getDeclaredMethods())
                .collect(Collectors.toMap(Method::getName, m -> m));

            for (Method bm : blocking.getDeclaredMethods()) {
                Method rm = reactiveMethods.get(bm.getName());
                assertThat(rm)
                    .as("Reactive mirror of %s.%s", blocking.getSimpleName(), bm.getName())
                    .isNotNull();

                assertThat(rm.getReturnType())
                    .as("Return type of %s.%s must be Uni", reactive.getSimpleName(), rm.getName())
                    .isEqualTo(Uni.class);

                assertThat(rm.getParameterTypes())
                    .as("Parameters of %s.%s must match %s.%s",
                        reactive.getSimpleName(), rm.getName(),
                        blocking.getSimpleName(), bm.getName())
                    .isEqualTo(bm.getParameterTypes());

                Type uniTypeArg = ((ParameterizedType) rm.getGenericReturnType())
                    .getActualTypeArguments()[0];
                Class<?> expectedWrapped = bm.getReturnType() == void.class
                    ? Void.class : bm.getReturnType();
                if (expectedWrapped == Void.class) {
                    assertThat(uniTypeArg).isEqualTo(Void.class);
                } else {
                    assertThat(uniTypeArg.getTypeName())
                        .as("Uni<%s> expected for %s.%s",
                            bm.getGenericReturnType().getTypeName(),
                            reactive.getSimpleName(), rm.getName())
                        .isEqualTo(bm.getGenericReturnType().getTypeName());
                }
            }
        }
    }

    @Test
    void everyReactiveMethodHasBlockingEquivalent() {
        for (var entry : PAIRS.entrySet()) {
            Class<?> blocking = entry.getKey();
            Class<?> reactive = entry.getValue();
            Map<String, Method> blockingMethods = Arrays.stream(blocking.getDeclaredMethods())
                .collect(Collectors.toMap(Method::getName, m -> m));

            for (Method rm : reactive.getDeclaredMethods()) {
                if (rm.isDefault()) continue;
                assertThat(blockingMethods.get(rm.getName()))
                    .as("Blocking counterpart of %s.%s", reactive.getSimpleName(), rm.getName())
                    .isNotNull();
            }
        }
    }
}
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api`
Expected: 3 tests pass (vacuousPassGuard, everyBlockingMethodHasReactiveEquivalent, everyReactiveMethodHasBlockingEquivalent). Existing DependencyConstraintTest also passes.

- [ ] **Step 3: Commit**

```bash
git add rag-api/src/test/java/io/casehub/rag/BlockingReactiveParityTest.java
git commit -m "test(#11): rag-api — blocking/reactive parity ArchUnit test"
```

---

### Task 3: Fix @ApplicationScoped on existing blocking stubs

**Files:**
- Modify: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCorpusStore.java`
- Modify: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCaseRetriever.java`

- [ ] **Step 1: Add @ApplicationScoped to InMemoryCorpusStore**

In `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCorpusStore.java`, add the import and annotation:

Add import:
```java
import jakarta.enterprise.context.ApplicationScoped;
```

Change the class annotations from:
```java
@Alternative
@Priority(1)
public class InMemoryCorpusStore implements CorpusStore {
```
to:
```java
@Alternative
@Priority(1)
@ApplicationScoped
public class InMemoryCorpusStore implements CorpusStore {
```

- [ ] **Step 2: Add @ApplicationScoped to InMemoryCaseRetriever**

In `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCaseRetriever.java`, add the import and annotation:

Add import:
```java
import jakarta.enterprise.context.ApplicationScoped;
```

Change the class annotations from:
```java
@Alternative
@Priority(1)
public class InMemoryCaseRetriever implements CaseRetriever {
```
to:
```java
@Alternative
@Priority(1)
@ApplicationScoped
public class InMemoryCaseRetriever implements CaseRetriever {
```

- [ ] **Step 3: Run existing tests to verify no regression**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing`
Expected: All existing tests pass (InMemoryCorpusStoreTest, InMemoryCaseRetrieverTest).

- [ ] **Step 4: Commit**

```bash
git add rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCorpusStore.java rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCaseRetriever.java
git commit -m "fix(#11): rag-testing — add @ApplicationScoped to in-memory stubs (scope parity with eidos/qhorus)"
```

---

### Task 4: Reactive in-memory stubs in rag-testing

**Files:**
- Modify: `rag-testing/pom.xml`
- Create: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryReactiveCorpusStore.java`
- Create: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryReactiveCaseRetriever.java`
- Create: `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryReactiveCorpusStoreTest.java`
- Create: `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryReactiveCaseRetrieverTest.java`

- [ ] **Step 1: Add Mutiny dependency to rag-testing/pom.xml**

Add inside `<dependencies>`, after the `rag-api` dep:

```xml
<dependency>
    <groupId>io.smallrye.reactive</groupId>
    <artifactId>mutiny</artifactId>
    <scope>provided</scope>
</dependency>
```

- [ ] **Step 2: Write InMemoryReactiveCorpusStore test**

Create `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryReactiveCorpusStoreTest.java`:

```java
package io.casehub.rag.testing;

import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class InMemoryReactiveCorpusStoreTest {

    private InMemoryCorpusStore blocking;
    private InMemoryReactiveCorpusStore reactive;

    @BeforeEach
    void setUp() {
        blocking = new InMemoryCorpusStore();
        reactive = new InMemoryReactiveCorpusStore(blocking);
    }

    @Test
    void ingestDelegatesToBlocking() {
        var corpus = new CorpusRef("t1", "docs");
        var chunks = List.of(new ChunkInput("hello", "d1", Map.of()));

        reactive.ingest(corpus, chunks).await().indefinitely();

        assertThat(blocking.listDocuments(corpus)).containsExactly("d1");
    }

    @Test
    void deleteDocumentDelegatesToBlocking() {
        var corpus = new CorpusRef("t1", "docs");
        blocking.ingest(corpus, List.of(new ChunkInput("hello", "d1", Map.of())));

        reactive.deleteDocument(corpus, "d1").await().indefinitely();

        assertThat(blocking.listDocuments(corpus)).isEmpty();
    }

    @Test
    void deleteCorpusDelegatesToBlocking() {
        var corpus = new CorpusRef("t1", "docs");
        blocking.ingest(corpus, List.of(new ChunkInput("hello", "d1", Map.of())));

        reactive.deleteCorpus(corpus).await().indefinitely();

        assertThat(blocking.listDocuments(corpus)).isEmpty();
    }

    @Test
    void listDocumentsDelegatesToBlocking() {
        var corpus = new CorpusRef("t1", "docs");
        blocking.ingest(corpus, List.of(
            new ChunkInput("a", "d1", Map.of()),
            new ChunkInput("b", "d2", Map.of())));

        List<String> docs = reactive.listDocuments(corpus).await().indefinitely();

        assertThat(docs).containsExactly("d1", "d2");
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing -Dtest=InMemoryReactiveCorpusStoreTest`
Expected: FAIL — `InMemoryReactiveCorpusStore` does not exist yet.

- [ ] **Step 4: Implement InMemoryReactiveCorpusStore**

Create `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryReactiveCorpusStore.java`:

```java
package io.casehub.rag.testing;

import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.ReactiveCorpusStore;
import io.smallrye.mutiny.Uni;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Alternative;
import jakarta.inject.Inject;

import java.util.List;

@Alternative
@Priority(1)
@ApplicationScoped
public class InMemoryReactiveCorpusStore implements ReactiveCorpusStore {

    @Inject
    InMemoryCorpusStore delegate;

    public InMemoryReactiveCorpusStore() {}

    public InMemoryReactiveCorpusStore(InMemoryCorpusStore delegate) {
        this.delegate = delegate;
    }

    @Override
    public Uni<Void> ingest(CorpusRef corpus, List<ChunkInput> chunks) {
        return Uni.createFrom().item(corpus)
            .invoke(c -> delegate.ingest(c, chunks))
            .replaceWithVoid();
    }

    @Override
    public Uni<Void> deleteDocument(CorpusRef corpus, String sourceDocumentId) {
        return Uni.createFrom().item(corpus)
            .invoke(c -> delegate.deleteDocument(c, sourceDocumentId))
            .replaceWithVoid();
    }

    @Override
    public Uni<Void> deleteCorpus(CorpusRef corpus) {
        return Uni.createFrom().item(corpus)
            .invoke(c -> delegate.deleteCorpus(c))
            .replaceWithVoid();
    }

    @Override
    public Uni<List<String>> listDocuments(CorpusRef corpus) {
        return Uni.createFrom().item(() -> delegate.listDocuments(corpus));
    }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing -Dtest=InMemoryReactiveCorpusStoreTest`
Expected: PASS — 4 tests.

- [ ] **Step 6: Write InMemoryReactiveCaseRetriever test**

Create `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryReactiveCaseRetrieverTest.java`:

```java
package io.casehub.rag.testing;

import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.RetrievedChunk;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class InMemoryReactiveCaseRetrieverTest {

    private InMemoryCorpusStore store;
    private InMemoryReactiveCaseRetriever reactive;

    @BeforeEach
    void setUp() {
        store = new InMemoryCorpusStore();
        var blocking = new InMemoryCaseRetriever(store);
        reactive = new InMemoryReactiveCaseRetriever(blocking);
    }

    @Test
    void retrieveDelegatesToBlocking() {
        var corpus = new CorpusRef("t1", "docs");
        store.ingest(corpus, List.of(
            new ChunkInput("first", "d1", Map.of()),
            new ChunkInput("second", "d2", Map.of())));

        List<RetrievedChunk> chunks = reactive.retrieve("query", corpus, 10)
            .await().indefinitely();

        assertThat(chunks).hasSize(2);
        assertThat(chunks.get(0).content()).isEqualTo("first");
        assertThat(chunks.get(1).content()).isEqualTo("second");
    }

    @Test
    void retrieveRespectsMaxResults() {
        var corpus = new CorpusRef("t1", "docs");
        store.ingest(corpus, List.of(
            new ChunkInput("a", "d1", Map.of()),
            new ChunkInput("b", "d2", Map.of()),
            new ChunkInput("c", "d3", Map.of())));

        List<RetrievedChunk> chunks = reactive.retrieve("q", corpus, 2)
            .await().indefinitely();

        assertThat(chunks).hasSize(2);
    }

    @Test
    void retrieveFromEmptyCorpusReturnsEmpty() {
        var corpus = new CorpusRef("t1", "docs");

        List<RetrievedChunk> chunks = reactive.retrieve("q", corpus, 10)
            .await().indefinitely();

        assertThat(chunks).isEmpty();
    }
}
```

- [ ] **Step 7: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing -Dtest=InMemoryReactiveCaseRetrieverTest`
Expected: FAIL — `InMemoryReactiveCaseRetriever` does not exist yet.

- [ ] **Step 8: Implement InMemoryReactiveCaseRetriever**

Create `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryReactiveCaseRetriever.java`:

```java
package io.casehub.rag.testing;

import io.casehub.rag.CorpusRef;
import io.casehub.rag.ReactiveCaseRetriever;
import io.casehub.rag.RetrievedChunk;
import io.smallrye.mutiny.Uni;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Alternative;
import jakarta.inject.Inject;

import java.util.List;

@Alternative
@Priority(1)
@ApplicationScoped
public class InMemoryReactiveCaseRetriever implements ReactiveCaseRetriever {

    @Inject
    InMemoryCaseRetriever delegate;

    public InMemoryReactiveCaseRetriever() {}

    public InMemoryReactiveCaseRetriever(InMemoryCaseRetriever delegate) {
        this.delegate = delegate;
    }

    @Override
    public Uni<List<RetrievedChunk>> retrieve(String query, CorpusRef corpus, int maxResults) {
        return Uni.createFrom().item(() -> delegate.retrieve(query, corpus, maxResults));
    }
}
```

- [ ] **Step 9: Run all rag-testing tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing`
Expected: All tests pass — existing + new reactive stub tests.

- [ ] **Step 10: Commit**

```bash
git add rag-testing/pom.xml rag-testing/src/main/java/io/casehub/rag/testing/InMemoryReactiveCorpusStore.java rag-testing/src/main/java/io/casehub/rag/testing/InMemoryReactiveCaseRetriever.java rag-testing/src/test/java/io/casehub/rag/testing/InMemoryReactiveCorpusStoreTest.java rag-testing/src/test/java/io/casehub/rag/testing/InMemoryReactiveCaseRetrieverTest.java
git commit -m "feat(#11): rag-testing — InMemoryReactiveCorpusStore, InMemoryReactiveCaseRetriever stubs"
```

---

### Task 5: Bridge beans in rag

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/BlockingToReactiveCorpusStore.java`
- Create: `rag/src/main/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetriever.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCorpusStoreTest.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java`

- [ ] **Step 1: Write BlockingToReactiveCorpusStore test**

Create `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCorpusStoreTest.java`:

```java
package io.casehub.rag.runtime;

import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.CorpusStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class BlockingToReactiveCorpusStoreTest {

    private RecordingCorpusStore blocking;
    private BlockingToReactiveCorpusStore bridge;

    @BeforeEach
    void setUp() {
        blocking = new RecordingCorpusStore();
        bridge = new BlockingToReactiveCorpusStore(blocking);
    }

    @Test
    void ingestDelegatesToBlocking() {
        var corpus = new CorpusRef("t1", "docs");
        var chunks = List.of(new ChunkInput("hello", "d1", Map.of()));

        bridge.ingest(corpus, chunks).await().indefinitely();

        assertThat(blocking.calls).containsExactly("ingest:t1:docs");
    }

    @Test
    void deleteDocumentDelegatesToBlocking() {
        var corpus = new CorpusRef("t1", "docs");

        bridge.deleteDocument(corpus, "d1").await().indefinitely();

        assertThat(blocking.calls).containsExactly("deleteDocument:t1:docs:d1");
    }

    @Test
    void deleteCorpusDelegatesToBlocking() {
        var corpus = new CorpusRef("t1", "docs");

        bridge.deleteCorpus(corpus).await().indefinitely();

        assertThat(blocking.calls).containsExactly("deleteCorpus:t1:docs");
    }

    @Test
    void listDocumentsDelegatesToBlocking() {
        var corpus = new CorpusRef("t1", "docs");
        blocking.documentsToReturn = List.of("d1", "d2");

        List<String> result = bridge.listDocuments(corpus).await().indefinitely();

        assertThat(result).containsExactly("d1", "d2");
        assertThat(blocking.calls).containsExactly("listDocuments:t1:docs");
    }

    static class RecordingCorpusStore implements CorpusStore {
        final List<String> calls = new ArrayList<>();
        List<String> documentsToReturn = List.of();

        @Override
        public void ingest(CorpusRef corpus, List<ChunkInput> chunks) {
            calls.add("ingest:" + corpus.tenantId() + ":" + corpus.corpusName());
        }

        @Override
        public void deleteDocument(CorpusRef corpus, String sourceDocumentId) {
            calls.add("deleteDocument:" + corpus.tenantId() + ":" + corpus.corpusName()
                + ":" + sourceDocumentId);
        }

        @Override
        public void deleteCorpus(CorpusRef corpus) {
            calls.add("deleteCorpus:" + corpus.tenantId() + ":" + corpus.corpusName());
        }

        @Override
        public List<String> listDocuments(CorpusRef corpus) {
            calls.add("listDocuments:" + corpus.tenantId() + ":" + corpus.corpusName());
            return documentsToReturn;
        }
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=BlockingToReactiveCorpusStoreTest`
Expected: FAIL — `BlockingToReactiveCorpusStore` does not exist.

- [ ] **Step 3: Implement BlockingToReactiveCorpusStore**

Create `rag/src/main/java/io/casehub/rag/runtime/BlockingToReactiveCorpusStore.java`:

```java
package io.casehub.rag.runtime;

import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.CorpusStore;
import io.casehub.rag.ReactiveCorpusStore;
import io.quarkus.arc.DefaultBean;
import io.smallrye.mutiny.Uni;
import io.smallrye.mutiny.infrastructure.Infrastructure;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.util.List;

@DefaultBean
@ApplicationScoped
public class BlockingToReactiveCorpusStore implements ReactiveCorpusStore {

    @Inject CorpusStore delegate;

    public BlockingToReactiveCorpusStore() {}

    public BlockingToReactiveCorpusStore(CorpusStore delegate) {
        this.delegate = delegate;
    }

    @Override
    public Uni<Void> ingest(CorpusRef corpus, List<ChunkInput> chunks) {
        return Uni.createFrom().<Void>item(() -> { delegate.ingest(corpus, chunks); return null; })
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }

    @Override
    public Uni<Void> deleteDocument(CorpusRef corpus, String sourceDocumentId) {
        return Uni.createFrom().<Void>item(() -> { delegate.deleteDocument(corpus, sourceDocumentId); return null; })
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }

    @Override
    public Uni<Void> deleteCorpus(CorpusRef corpus) {
        return Uni.createFrom().<Void>item(() -> { delegate.deleteCorpus(corpus); return null; })
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }

    @Override
    public Uni<List<String>> listDocuments(CorpusRef corpus) {
        return Uni.createFrom().item(() -> delegate.listDocuments(corpus))
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=BlockingToReactiveCorpusStoreTest`
Expected: PASS — 4 tests.

- [ ] **Step 5: Write BlockingToReactiveCaseRetriever test**

Create `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java`:

```java
package io.casehub.rag.runtime;

import io.casehub.rag.CaseRetriever;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.RetrievedChunk;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class BlockingToReactiveCaseRetrieverTest {

    private BlockingToReactiveCaseRetriever bridge;

    @BeforeEach
    void setUp() {
        CaseRetriever blocking = (query, corpus, maxResults) ->
            List.of(new RetrievedChunk("result for " + query, "d1", 0.95, Map.of()));
        bridge = new BlockingToReactiveCaseRetriever(blocking);
    }

    @Test
    void retrieveDelegatesToBlocking() {
        var corpus = new CorpusRef("t1", "docs");

        List<RetrievedChunk> result = bridge.retrieve("test query", corpus, 5)
            .await().indefinitely();

        assertThat(result).hasSize(1);
        assertThat(result.get(0).content()).isEqualTo("result for test query");
        assertThat(result.get(0).relevanceScore()).isEqualTo(0.95);
    }

    @Test
    void retrieveEmptyFromBlockingReturnsEmpty() {
        CaseRetriever empty = (query, corpus, maxResults) -> List.of();
        bridge = new BlockingToReactiveCaseRetriever(empty);
        var corpus = new CorpusRef("t1", "docs");

        List<RetrievedChunk> result = bridge.retrieve("q", corpus, 10)
            .await().indefinitely();

        assertThat(result).isEmpty();
    }
}
```

- [ ] **Step 6: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=BlockingToReactiveCaseRetrieverTest`
Expected: FAIL — `BlockingToReactiveCaseRetriever` does not exist.

- [ ] **Step 7: Implement BlockingToReactiveCaseRetriever**

Create `rag/src/main/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetriever.java`:

```java
package io.casehub.rag.runtime;

import io.casehub.rag.CaseRetriever;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.ReactiveCaseRetriever;
import io.casehub.rag.RetrievedChunk;
import io.quarkus.arc.DefaultBean;
import io.smallrye.mutiny.Uni;
import io.smallrye.mutiny.infrastructure.Infrastructure;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.util.List;

@DefaultBean
@ApplicationScoped
public class BlockingToReactiveCaseRetriever implements ReactiveCaseRetriever {

    @Inject CaseRetriever delegate;

    public BlockingToReactiveCaseRetriever() {}

    public BlockingToReactiveCaseRetriever(CaseRetriever delegate) {
        this.delegate = delegate;
    }

    @Override
    public Uni<List<RetrievedChunk>> retrieve(String query, CorpusRef corpus, int maxResults) {
        return Uni.createFrom().item(() -> delegate.retrieve(query, corpus, maxResults))
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }
}
```

- [ ] **Step 8: Run all rag tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`
Expected: All tests pass — existing + new bridge tests.

- [ ] **Step 9: Commit**

```bash
git add rag/src/main/java/io/casehub/rag/runtime/BlockingToReactiveCorpusStore.java rag/src/main/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetriever.java rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCorpusStoreTest.java rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java
git commit -m "feat(#11): rag — BlockingToReactiveCorpusStore, BlockingToReactiveCaseRetriever @DefaultBean bridges"
```

---

### Task 6: Full build verification

- [ ] **Step 1: Run full build with tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS — all modules compile and all tests pass.

- [ ] **Step 2: Verify ArchUnit constraints still hold**

The `DependencyConstraintTest` in `rag-api` must still pass — Mutiny is `provided` scope, not a runtime dependency. The `noCasehubDomain` rule only blocks `io.casehub.*` that is not `io.casehub.rag.*`. The `noQuarkus` rule blocks `io.quarkus..` and `jakarta..` — Mutiny (`io.smallrye.mutiny..`) is not blocked.

Expected: All 4 existing ArchUnit rules + 3 new parity tests pass.

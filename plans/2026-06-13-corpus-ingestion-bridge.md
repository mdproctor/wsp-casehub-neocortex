# Corpus Ingestion Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire corpus ChangeSource + CorpusReader to the RAG pipeline (embed → Qdrant) via a config-driven polling bridge with cursor-based incremental processing.

**Architecture:** Single `CorpusIngestionService` discovers per-corpus bindings from two sources (config-driven producer + custom CDI beans), polls on a scheduled interval, processes change sets with delete-then-reingest semantics, and supports admin-triggered reconciliation. New SPIs (`MetadataExtractor`, `CursorStore`) in rag-api provide extension points. All processing is blocking.

**Tech Stack:** Java 21, Quarkus 3.32.2, LangChain4j 1.14.1 (`DocumentSplitters`), Quarkus Scheduler (`@Scheduled`), corpus-api SPIs, existing `EmbeddingIngestor` in rag/

**Spec:** `specs/issue-19-corpus-ingestion-bridge/2026-06-13-corpus-ingestion-bridge-design.md` (rev 4, Approved)

---

### Task 0: File prerequisite and follow-on issues, update dependencies

**Files:**
- Modify: `rag/pom.xml`

- [ ] **Step 1: File prerequisite issue — assertTenant 3-arg migration**

```bash
gh issue create --repo casehubio/neural-text \
  --title "fix: assertTenant 2-arg → 3-arg in EmbeddingIngestor + CaseRetriever" \
  --body "## Summary
Switch QdrantEmbeddingIngestor, ReactiveQdrantEmbeddingIngestor, HybridCaseRetriever, ReactiveHybridCaseRetriever to 3-arg MemoryPermissions.assertTenant(tenantId, principal, requestContextActive()). Required for #19 (ingestion bridge runs on @Scheduled — no request context). Extends protocol PP-20260529-57cc3b scope to RAG adapters. Update protocol applies_to field.

## Scale / Complexity
S / Low — 10 call sites, 1 helper method per class, 1 protocol update

## Blocked by
None

## Blocks
#19" \
  --label "fix"
```

- [ ] **Step 2: File follow-on issue — corpus-quarkus extraction**

```bash
gh issue create --repo casehubio/neural-text \
  --title "refactor: extract corpus CDI integration to corpus-quarkus/ module" \
  --body "## Summary
CorpusBindingProducer in rag/ contains corpus instance construction logic (choosing ZipCorpusStore/FlatCorpusStore/CompositeCorpusStore from config). This is a corpus concern, not a RAG concern. Extract to a dedicated corpus-quarkus/ module (analogous to inference-quarkus/) when the second consumer materialises.

## Trigger
Second consumer of corpus instances (harvest via CorpusReader, engine fact retrieval).

## Scale / Complexity
M / Low" \
  --label "refactor"
```

- [ ] **Step 3: File issue — parent spec config key update**

```bash
gh issue create --repo casehubio/neural-text \
  --title "docs: update parent spec config keys for ingestion bridge" \
  --body "## Summary
Parent spec (specs/2026-06-11-corpus-storage-module-design.md) uses casehub.rag.ingestion.garden.mode=auto. Actual config requires casehub.rag.ingestion.corpora.garden.mode=auto — extra corpora level for Quarkus @ConfigMapping Map support. Update parent spec to match.

## Scale / Complexity
XS / Low" \
  --label "docs"
```

- [ ] **Step 4: Update rag/pom.xml dependencies**

Replace `langchain4j-core` with `langchain4j` (full artifact, includes core transitively). Add `casehub-corpus` and `quarkus-scheduler`.

In `rag/pom.xml`, replace:
```xml
    <dependency>
      <groupId>dev.langchain4j</groupId>
      <artifactId>langchain4j-core</artifactId>
    </dependency>
```
with:
```xml
    <dependency>
      <groupId>dev.langchain4j</groupId>
      <artifactId>langchain4j</artifactId>
    </dependency>
```

Add after the `casehub-platform-api` dependency:
```xml
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-corpus</artifactId>
    </dependency>

    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-scheduler</artifactId>
    </dependency>
```

- [ ] **Step 5: Verify build compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl rag -am -DskipTests`
Expected: BUILD SUCCESS

- [ ] **Step 6: Commit**

```
feat(#19): update rag dependencies — langchain4j full, corpus, scheduler
```

---

### Task 1: Fix assertTenant — prerequisite for background poller

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/QdrantEmbeddingIngestor.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantEmbeddingIngestor.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java`

- [ ] **Step 1: Add requestContextActive() helper and switch assertTenant calls in QdrantEmbeddingIngestor**

Add import:
```java
import io.quarkus.arc.Arc;
```

Add private helper method:
```java
private boolean requestContextActive() {
    var c = Arc.container();
    return c == null || c.requestContext().isActive();
}
```

Replace all 4 occurrences of:
```java
MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal);
```
with:
```java
MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal, requestContextActive());
```

- [ ] **Step 2: Same changes in ReactiveQdrantEmbeddingIngestor**

Same pattern: add `Arc` import, add `requestContextActive()` helper, replace all 4 `assertTenant` calls with the 3-arg form.

- [ ] **Step 3: Same changes in HybridCaseRetriever**

One `assertTenant` call site. Same pattern.

- [ ] **Step 4: Same changes in ReactiveHybridCaseRetriever**

One `assertTenant` call site. Same pattern.

- [ ] **Step 5: Run existing tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`
Expected: All existing tests pass — they run with CDI request context active, so `requestContextActive()` returns true and the 3-arg form behaves identically to the 2-arg form.

- [ ] **Step 6: Commit**

```
fix(#<assertTenant-issue>): assertTenant 2-arg → 3-arg in RAG adapters

Extends protocol PP-20260529-57cc3b to EmbeddingIngestor and
CaseRetriever implementations. Background pollers (no request
context) now trust config-provided tenantId instead of throwing
SecurityException.
```

---

### Task 2: rag-api — ExtractionResult, MetadataExtractor, CursorStore

**Files:**
- Create: `rag-api/src/main/java/io/casehub/rag/ExtractionResult.java`
- Create: `rag-api/src/main/java/io/casehub/rag/MetadataExtractor.java`
- Create: `rag-api/src/main/java/io/casehub/rag/CursorStore.java`
- Create: `rag-api/src/test/java/io/casehub/rag/ExtractionResultTest.java`

- [ ] **Step 1: Write ExtractionResult test**

```java
package io.casehub.rag;

import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ExtractionResultTest {

    @Test
    void validConstruction() {
        var result = new ExtractionResult("body text", Map.of("title", "Test"));
        assertThat(result.body()).isEqualTo("body text");
        assertThat(result.metadata()).containsEntry("title", "Test");
    }

    @Test
    void nullBodyThrows() {
        assertThatThrownBy(() -> new ExtractionResult(null, Map.of()))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("body must not be null");
    }

    @Test
    void nullMetadataDefaultsToEmptyMap() {
        var result = new ExtractionResult("body", null);
        assertThat(result.metadata()).isEmpty();
    }

    @Test
    void metadataIsDefensivelyCopied() {
        var mutable = new HashMap<String, String>();
        mutable.put("key", "value");
        var result = new ExtractionResult("body", mutable);
        mutable.put("key2", "value2");
        assertThat(result.metadata()).containsOnlyKeys("key");
    }

    @Test
    void metadataIsUnmodifiable() {
        var result = new ExtractionResult("body", Map.of("key", "value"));
        assertThatThrownBy(() -> result.metadata().put("new", "value"))
            .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void emptyBodyIsAllowed() {
        var result = new ExtractionResult("", Map.of());
        assertThat(result.body()).isEmpty();
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=ExtractionResultTest`
Expected: FAIL — `ExtractionResult` class not found

- [ ] **Step 3: Create ExtractionResult.java**

```java
package io.casehub.rag;

import java.util.Map;

public record ExtractionResult(String body, Map<String, String> metadata) {
    public ExtractionResult {
        if (body == null)
            throw new IllegalArgumentException("body must not be null");
        metadata = metadata == null ? Map.of() : Map.copyOf(metadata);
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=ExtractionResultTest`
Expected: PASS

- [ ] **Step 5: Create MetadataExtractor.java**

```java
package io.casehub.rag;

public interface MetadataExtractor {
    ExtractionResult extract(String path, byte[] content);
}
```

- [ ] **Step 6: Create CursorStore.java**

```java
package io.casehub.rag;

import java.util.Optional;

public interface CursorStore {
    Optional<String> load(String corpusName);
    void save(String corpusName, String cursor);
}
```

- [ ] **Step 7: Verify rag-api compiles and all tests pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api`
Expected: All tests pass (existing + new)

- [ ] **Step 8: Commit**

```
feat(#19): rag-api — MetadataExtractor, ExtractionResult, CursorStore SPIs
```

---

### Task 3: rag-testing — InMemoryCursorStore

**Files:**
- Create: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCursorStore.java`
- Create: `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryCursorStoreTest.java`

- [ ] **Step 1: Write InMemoryCursorStore test**

```java
package io.casehub.rag.testing;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class InMemoryCursorStoreTest {

    private InMemoryCursorStore store;

    @BeforeEach
    void setUp() {
        store = new InMemoryCursorStore();
    }

    @Test
    void loadReturnsEmptyWhenNoCursorSaved() {
        assertThat(store.load("garden")).isEmpty();
    }

    @Test
    void saveAndLoad() {
        store.save("garden", "{\"tools/git.md\":1}");
        assertThat(store.load("garden")).contains("{\"tools/git.md\":1}");
    }

    @Test
    void saveOverwritesPreviousCursor() {
        store.save("garden", "cursor-1");
        store.save("garden", "cursor-2");
        assertThat(store.load("garden")).contains("cursor-2");
    }

    @Test
    void isolationBetweenCorpora() {
        store.save("garden", "cursor-g");
        store.save("legal", "cursor-l");
        assertThat(store.load("garden")).contains("cursor-g");
        assertThat(store.load("legal")).contains("cursor-l");
    }

    @Test
    void resetClearsAllCursors() {
        store.save("garden", "cursor-1");
        store.save("legal", "cursor-2");
        store.reset();
        assertThat(store.load("garden")).isEmpty();
        assertThat(store.load("legal")).isEmpty();
    }

    @Test
    void getAllReturnsSnapshot() {
        store.save("garden", "c1");
        store.save("legal", "c2");
        var all = store.getAll();
        assertThat(all).containsEntry("garden", "c1").containsEntry("legal", "c2");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing -Dtest=InMemoryCursorStoreTest`
Expected: FAIL — class not found

- [ ] **Step 3: Create InMemoryCursorStore.java**

```java
package io.casehub.rag.testing;

import io.casehub.rag.CursorStore;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Alternative;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

@Alternative
@Priority(1)
@ApplicationScoped
public class InMemoryCursorStore implements CursorStore {

    private final ConcurrentHashMap<String, String> cursors = new ConcurrentHashMap<>();

    @Override
    public Optional<String> load(String corpusName) {
        return Optional.ofNullable(cursors.get(corpusName));
    }

    @Override
    public void save(String corpusName, String cursor) {
        cursors.put(corpusName, cursor);
    }

    public void reset() {
        cursors.clear();
    }

    public Map<String, String> getAll() {
        return Map.copyOf(cursors);
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing`
Expected: All tests pass

- [ ] **Step 5: Commit**

```
feat(#19): rag-testing — InMemoryCursorStore test stub
```

---

### Task 4: rag/ — CorpusIngestionBinding + IngestionMode + IngestionConfig

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/CorpusIngestionBinding.java`
- Create: `rag/src/main/java/io/casehub/rag/runtime/IngestionMode.java`
- Create: `rag/src/main/java/io/casehub/rag/runtime/IngestionConfig.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/CorpusIngestionBindingTest.java`

- [ ] **Step 1: Write CorpusIngestionBinding test**

```java
package io.casehub.rag.runtime;

import io.casehub.corpus.ChangeSet;
import io.casehub.corpus.ChangeSource;
import io.casehub.corpus.CorpusReader;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.ExtractionResult;
import io.casehub.rag.MetadataExtractor;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class CorpusIngestionBindingTest {

    private static final CorpusRef CORPUS = new CorpusRef("tenant", "corpus");
    private static final ChangeSource CHANGE_SOURCE = new ChangeSource() {
        @Override public ChangeSet changesSince(String cursor) { return new ChangeSet(List.of(), "{}"); }
        @Override public ChangeSet fullScan() { return new ChangeSet(List.of(), "{}"); }
    };
    private static final CorpusReader READER = new CorpusReader() {
        @Override public Optional<byte[]> read(String path) { return Optional.empty(); }
        @Override public Optional<java.io.InputStream> readStream(String path) { return Optional.empty(); }
        @Override public Optional<byte[]> readVersion(String path, int version) { return Optional.empty(); }
        @Override public List<io.casehub.corpus.VersionInfo> versions(String path) { return List.of(); }
        @Override public List<String> list() { return List.of(); }
        @Override public List<String> list(String prefix) { return List.of(); }
        @Override public boolean exists(String path) { return false; }
    };
    private static final MetadataExtractor EXTRACTOR = (path, content) ->
        new ExtractionResult(new String(content), Map.of());

    @Test
    void validConstruction() {
        var binding = new CorpusIngestionBinding("garden", CORPUS, CHANGE_SOURCE, READER, EXTRACTOR);
        assertThat(binding.name()).isEqualTo("garden");
        assertThat(binding.corpusRef()).isEqualTo(CORPUS);
    }

    @Test
    void nullNameThrows() {
        assertThatThrownBy(() -> new CorpusIngestionBinding(null, CORPUS, CHANGE_SOURCE, READER, EXTRACTOR))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void blankNameThrows() {
        assertThatThrownBy(() -> new CorpusIngestionBinding("  ", CORPUS, CHANGE_SOURCE, READER, EXTRACTOR))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void nullCorpusRefThrows() {
        assertThatThrownBy(() -> new CorpusIngestionBinding("garden", null, CHANGE_SOURCE, READER, EXTRACTOR))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void nullChangeSourceThrows() {
        assertThatThrownBy(() -> new CorpusIngestionBinding("garden", CORPUS, null, READER, EXTRACTOR))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void nullReaderThrows() {
        assertThatThrownBy(() -> new CorpusIngestionBinding("garden", CORPUS, CHANGE_SOURCE, null, EXTRACTOR))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void nullExtractorThrows() {
        assertThatThrownBy(() -> new CorpusIngestionBinding("garden", CORPUS, CHANGE_SOURCE, READER, null))
            .isInstanceOf(NullPointerException.class);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=CorpusIngestionBindingTest`
Expected: FAIL — class not found

- [ ] **Step 3: Create CorpusIngestionBinding.java**

```java
package io.casehub.rag.runtime;

import io.casehub.corpus.ChangeSource;
import io.casehub.corpus.CorpusReader;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.MetadataExtractor;
import java.util.Objects;

public record CorpusIngestionBinding(
    String name,
    CorpusRef corpusRef,
    ChangeSource changeSource,
    CorpusReader corpusReader,
    MetadataExtractor metadataExtractor
) {
    public CorpusIngestionBinding {
        if (name == null || name.isBlank())
            throw new IllegalArgumentException("name must not be null or blank");
        Objects.requireNonNull(corpusRef, "corpusRef");
        Objects.requireNonNull(changeSource, "changeSource");
        Objects.requireNonNull(corpusReader, "corpusReader");
        Objects.requireNonNull(metadataExtractor, "metadataExtractor");
    }
}
```

- [ ] **Step 4: Create IngestionMode.java**

```java
package io.casehub.rag.runtime;

public enum IngestionMode { AUTO, MANUAL, NONE }
```

- [ ] **Step 5: Create IngestionConfig.java**

```java
package io.casehub.rag.runtime;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;
import java.time.Duration;
import java.util.Map;
import java.util.Optional;

@ConfigMapping(prefix = "casehub.rag.ingestion")
public interface IngestionConfig {

    @WithDefault("30s")
    Duration interval();

    @WithDefault("${java.io.tmpdir}/casehub-ingestion-cursors")
    String cursorDir();

    Map<String, CorpusIngestionConfig> corpora();

    interface CorpusIngestionConfig {
        @WithDefault("AUTO")
        IngestionMode mode();

        String tenantId();
        String corpusName();

        @WithDefault("none")
        String chunking();

        Optional<Integer> chunkingMaxSize();
        Optional<Integer> chunkingOverlapSize();
    }
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=CorpusIngestionBindingTest`
Expected: PASS

- [ ] **Step 7: Commit**

```
feat(#19): CorpusIngestionBinding, IngestionMode, IngestionConfig
```

---

### Task 5: rag/ — YamlFrontmatterExtractor

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/YamlFrontmatterExtractor.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/YamlFrontmatterExtractorTest.java`

- [ ] **Step 1: Write test**

```java
package io.casehub.rag.runtime;

import io.casehub.rag.ExtractionResult;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

class YamlFrontmatterExtractorTest {

    private final YamlFrontmatterExtractor extractor = new YamlFrontmatterExtractor();

    @Test
    void extractsFrontmatterAndBody() {
        String content = """
                ---
                id: GE-20260101-abc123
                title: Test Entry
                tags: [java, quarkus]
                ---
                This is the body content.
                
                Second paragraph.""";
        ExtractionResult result = extractor.extract("tools/test.md", content.getBytes(StandardCharsets.UTF_8));
        assertThat(result.metadata()).containsEntry("id", "GE-20260101-abc123");
        assertThat(result.metadata()).containsEntry("title", "Test Entry");
        assertThat(result.metadata()).containsEntry("tags", "[java, quarkus]");
        assertThat(result.body()).startsWith("This is the body content.");
        assertThat(result.body()).contains("Second paragraph.");
    }

    @Test
    void noFrontmatterReturnsEntireContentAsBody() {
        String content = "Just a plain document.\nNo frontmatter here.";
        ExtractionResult result = extractor.extract("readme.md", content.getBytes(StandardCharsets.UTF_8));
        assertThat(result.body()).isEqualTo(content);
        assertThat(result.metadata()).isEmpty();
    }

    @Test
    void emptyContentReturnsEmptyBodyAndMetadata() {
        ExtractionResult result = extractor.extract("empty.md", new byte[0]);
        assertThat(result.body()).isEmpty();
        assertThat(result.metadata()).isEmpty();
    }

    @Test
    void onlyFrontmatterNoBody() {
        String content = """
                ---
                id: GE-20260101-abc123
                ---
                """;
        ExtractionResult result = extractor.extract("meta-only.md", content.getBytes(StandardCharsets.UTF_8));
        assertThat(result.metadata()).containsEntry("id", "GE-20260101-abc123");
        assertThat(result.body()).isBlank();
    }

    @Test
    void frontmatterWithColonsInValues() {
        String content = """
                ---
                url: https://example.com/path
                note: key: value pair
                ---
                Body.""";
        ExtractionResult result = extractor.extract("urls.md", content.getBytes(StandardCharsets.UTF_8));
        assertThat(result.metadata()).containsEntry("url", "https://example.com/path");
        assertThat(result.metadata()).containsEntry("note", "key: value pair");
        assertThat(result.body()).isEqualTo("Body.");
    }

    @Test
    void frontmatterWithQuotedValues() {
        String content = """
                ---
                title: "A quoted title"
                desc: 'single quoted'
                ---
                Body.""";
        ExtractionResult result = extractor.extract("quoted.md", content.getBytes(StandardCharsets.UTF_8));
        assertThat(result.metadata()).containsEntry("title", "A quoted title");
        assertThat(result.metadata()).containsEntry("desc", "single quoted");
    }

    @Test
    void unclosedFrontmatterTreatsAsNoFrontmatter() {
        String content = """
                ---
                id: GE-123
                This never closes the frontmatter.""";
        ExtractionResult result = extractor.extract("broken.md", content.getBytes(StandardCharsets.UTF_8));
        assertThat(result.metadata()).isEmpty();
        assertThat(result.body()).isEqualTo(content);
    }

    @Test
    void frontmatterMustStartAtLineOne() {
        String content = """
                Some leading text.
                ---
                id: GE-123
                ---
                Body.""";
        ExtractionResult result = extractor.extract("late-start.md", content.getBytes(StandardCharsets.UTF_8));
        assertThat(result.metadata()).isEmpty();
        assertThat(result.body()).isEqualTo(content);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=YamlFrontmatterExtractorTest`
Expected: FAIL

- [ ] **Step 3: Implement YamlFrontmatterExtractor**

```java
package io.casehub.rag.runtime;

import io.casehub.rag.ExtractionResult;
import io.casehub.rag.MetadataExtractor;
import io.quarkus.arc.DefaultBean;
import jakarta.enterprise.context.ApplicationScoped;

import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

@DefaultBean
@ApplicationScoped
public class YamlFrontmatterExtractor implements MetadataExtractor {

    @Override
    public ExtractionResult extract(String path, byte[] content) {
        String text = new String(content, StandardCharsets.UTF_8);
        if (text.isEmpty()) {
            return new ExtractionResult("", Map.of());
        }

        if (!text.startsWith("---")) {
            return new ExtractionResult(text, Map.of());
        }

        int closingIndex = text.indexOf("\n---", 3);
        if (closingIndex < 0) {
            return new ExtractionResult(text, Map.of());
        }

        String frontmatterBlock = text.substring(4, closingIndex).trim();
        String body = text.substring(closingIndex + 4).trim();

        Map<String, String> metadata = parseFrontmatter(frontmatterBlock);
        return new ExtractionResult(body, metadata);
    }

    private Map<String, String> parseFrontmatter(String block) {
        Map<String, String> metadata = new LinkedHashMap<>();
        for (String line : block.split("\n")) {
            line = line.trim();
            if (line.isEmpty()) continue;
            int colonPos = line.indexOf(':');
            if (colonPos <= 0) continue;
            String key = line.substring(0, colonPos).trim();
            String value = line.substring(colonPos + 1).trim();
            value = stripQuotes(value);
            metadata.put(key, value);
        }
        return metadata;
    }

    private String stripQuotes(String value) {
        if (value.length() >= 2) {
            if ((value.startsWith("\"") && value.endsWith("\""))
                    || (value.startsWith("'") && value.endsWith("'"))) {
                return value.substring(1, value.length() - 1);
            }
        }
        return value;
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=YamlFrontmatterExtractorTest`
Expected: PASS

- [ ] **Step 5: Commit**

```
feat(#19): YamlFrontmatterExtractor — @DefaultBean MetadataExtractor
```

---

### Task 6: rag/ — FileCursorStore

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/FileCursorStore.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/FileCursorStoreTest.java`

- [ ] **Step 1: Write test**

```java
package io.casehub.rag.runtime;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

class FileCursorStoreTest {

    @TempDir
    Path tempDir;
    private FileCursorStore store;

    @BeforeEach
    void setUp() {
        store = new FileCursorStore(tempDir.toString());
    }

    @Test
    void loadReturnsEmptyWhenNoFile() {
        assertThat(store.load("garden")).isEmpty();
    }

    @Test
    void saveAndLoad() {
        store.save("garden", "{\"tools/git.md\":1}");
        assertThat(store.load("garden")).contains("{\"tools/git.md\":1}");
    }

    @Test
    void saveOverwritesPrevious() {
        store.save("garden", "cursor-1");
        store.save("garden", "cursor-2");
        assertThat(store.load("garden")).contains("cursor-2");
    }

    @Test
    void isolationBetweenCorpora() {
        store.save("garden", "cg");
        store.save("legal", "cl");
        assertThat(store.load("garden")).contains("cg");
        assertThat(store.load("legal")).contains("cl");
    }

    @Test
    void createsDirectoryIfMissing() {
        Path nested = tempDir.resolve("sub/dir");
        var nestedStore = new FileCursorStore(nested.toString());
        nestedStore.save("garden", "cursor");
        assertThat(nestedStore.load("garden")).contains("cursor");
        assertThat(Files.exists(nested)).isTrue();
    }

    @Test
    void cursorFileNameMatchesCorpus() throws IOException {
        store.save("garden", "cursor");
        assertThat(Files.exists(tempDir.resolve("garden.cursor"))).isTrue();
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=FileCursorStoreTest`
Expected: FAIL

- [ ] **Step 3: Implement FileCursorStore**

```java
package io.casehub.rag.runtime;

import io.casehub.rag.CursorStore;
import io.quarkus.arc.DefaultBean;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Optional;

@DefaultBean
@ApplicationScoped
public class FileCursorStore implements CursorStore {

    private final Path baseDir;

    @Inject
    FileCursorStore(IngestionConfig config) {
        this(config.cursorDir());
    }

    FileCursorStore(String cursorDir) {
        this.baseDir = Path.of(cursorDir);
    }

    @Override
    public Optional<String> load(String corpusName) {
        Path file = baseDir.resolve(corpusName + ".cursor");
        if (!Files.exists(file)) {
            return Optional.empty();
        }
        try {
            return Optional.of(Files.readString(file).trim());
        } catch (IOException e) {
            throw new UncheckedIOException("Failed to read cursor for " + corpusName, e);
        }
    }

    @Override
    public void save(String corpusName, String cursor) {
        try {
            Files.createDirectories(baseDir);
            Path file = baseDir.resolve(corpusName + ".cursor");
            Path tmp = baseDir.resolve(corpusName + ".cursor.tmp");
            Files.writeString(tmp, cursor);
            Files.move(tmp, file, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } catch (IOException e) {
            throw new UncheckedIOException("Failed to save cursor for " + corpusName, e);
        }
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=FileCursorStoreTest`
Expected: PASS

- [ ] **Step 5: Commit**

```
feat(#19): FileCursorStore — @DefaultBean file-based cursor persistence
```

---

### Task 7: rag/ — CorpusIngestionService (core processing)

This is the main orchestrator. Tested as a plain unit test with manually-constructed dependencies — no CDI.

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/CorpusIngestionService.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/CorpusIngestionServiceTest.java`

- [ ] **Step 1: Write test — ADDED entries are ingested**

```java
package io.casehub.rag.runtime;

import io.casehub.corpus.ChangeSet;
import io.casehub.corpus.ChangeSource;
import io.casehub.corpus.ChangeType;
import io.casehub.corpus.ChangedEntry;
import io.casehub.corpus.CorpusReader;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.ExtractionResult;
import io.casehub.rag.MetadataExtractor;
import io.casehub.rag.testing.InMemoryCursorStore;
import io.casehub.rag.testing.InMemoryEmbeddingIngestor;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class CorpusIngestionServiceTest {

    private static final CorpusRef CORPUS = new CorpusRef("default", "garden");
    private InMemoryEmbeddingIngestor ingestor;
    private InMemoryCursorStore cursorStore;

    @BeforeEach
    void setUp() {
        ingestor = new InMemoryEmbeddingIngestor();
        cursorStore = new InMemoryCursorStore();
    }

    private CorpusIngestionBinding binding(ChangeSource changeSource, CorpusReader reader) {
        return binding(changeSource, reader, passthrough());
    }

    private CorpusIngestionBinding binding(ChangeSource changeSource, CorpusReader reader, MetadataExtractor extractor) {
        return new CorpusIngestionBinding("garden", CORPUS, changeSource, reader, extractor);
    }

    private MetadataExtractor passthrough() {
        return (path, content) -> new ExtractionResult(new String(content, StandardCharsets.UTF_8), Map.of());
    }

    private CorpusIngestionService service() {
        return new CorpusIngestionService(ingestor, cursorStore);
    }

    @Test
    void addedEntriesAreIngested() {
        var changes = new ChangeSet(
            List.of(new ChangedEntry("tools/git.md", ChangeType.ADDED)),
            "{\"tools/git.md\":1}"
        );
        ChangeSource source = new ChangeSource() {
            @Override public ChangeSet changesSince(String cursor) { return changes; }
            @Override public ChangeSet fullScan() { return changes; }
        };
        CorpusReader reader = stubReader(Map.of("tools/git.md", "Git rebase guide"));

        service().processBinding(binding(source, reader));

        assertThat(ingestor.listDocuments(CORPUS)).containsExactly("tools/git.md");
        assertThat(ingestor.getChunks(CORPUS)).hasSize(1);
        assertThat(ingestor.getChunks(CORPUS).get(0).content()).isEqualTo("Git rebase guide");
        assertThat(cursorStore.load("garden")).contains("{\"tools/git.md\":1}");
    }

    // Helper: creates a CorpusReader that returns content for known paths
    private CorpusReader stubReader(Map<String, String> docs) {
        return new CorpusReader() {
            @Override public Optional<byte[]> read(String path) {
                String content = docs.get(path);
                return content == null ? Optional.empty() : Optional.of(content.getBytes(StandardCharsets.UTF_8));
            }
            @Override public Optional<InputStream> readStream(String path) { return Optional.empty(); }
            @Override public Optional<byte[]> readVersion(String path, int version) { return Optional.empty(); }
            @Override public List<io.casehub.corpus.VersionInfo> versions(String path) { return List.of(); }
            @Override public List<String> list() { return List.copyOf(docs.keySet()); }
            @Override public List<String> list(String prefix) { return list(); }
            @Override public boolean exists(String path) { return docs.containsKey(path); }
        };
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=CorpusIngestionServiceTest`
Expected: FAIL — class not found

- [ ] **Step 3: Implement CorpusIngestionService — minimal to pass first test**

```java
package io.casehub.rag.runtime;

import dev.langchain4j.data.document.Document;
import dev.langchain4j.data.document.DocumentSplitter;
import dev.langchain4j.data.document.splitter.DocumentSplitters;
import dev.langchain4j.data.segment.TextSegment;
import io.casehub.corpus.ChangeSet;
import io.casehub.corpus.ChangeType;
import io.casehub.corpus.ChangedEntry;
import io.casehub.rag.ChunkInput;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.CursorStore;
import io.casehub.rag.EmbeddingIngestor;
import io.casehub.rag.ExtractionResult;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;
import io.quarkus.scheduler.Scheduled;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantLock;
import java.util.logging.Level;
import java.util.logging.Logger;

@ApplicationScoped
public class CorpusIngestionService {

    private static final Logger LOG = Logger.getLogger(CorpusIngestionService.class.getName());

    private final EmbeddingIngestor ingestor;
    private final CursorStore cursorStore;
    private final Map<String, ReentrantLock> locks = new ConcurrentHashMap<>();

    @Inject
    CorpusIngestionService(EmbeddingIngestor ingestor, CursorStore cursorStore) {
        this.ingestor = ingestor;
        this.cursorStore = cursorStore;
    }

    void processBinding(CorpusIngestionBinding binding) {
        processBinding(binding, null);
    }

    void processBinding(CorpusIngestionBinding binding, DocumentSplitter splitter) {
        ReentrantLock lock = locks.computeIfAbsent(binding.name(), k -> new ReentrantLock());
        if (!lock.tryLock()) {
            LOG.fine(() -> "Skipping " + binding.name() + " — already processing");
            return;
        }
        try {
            doProcess(binding, splitter);
        } finally {
            lock.unlock();
        }
    }

    private void doProcess(CorpusIngestionBinding binding, DocumentSplitter splitter) {
        Optional<String> cursor = cursorStore.load(binding.name());
        ChangeSet changeSet;
        try {
            changeSet = cursor.isPresent()
                ? binding.changeSource().changesSince(cursor.get())
                : binding.changeSource().fullScan();
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "ChangeSource failed for " + binding.name(), e);
            return;
        }

        if (changeSet.entries().isEmpty()) return;

        boolean hasErrors = false;

        // Phase 1 — Deletions
        for (ChangedEntry entry : changeSet.entries()) {
            if (entry.type() == ChangeType.DELETED || entry.type() == ChangeType.MODIFIED) {
                try {
                    ingestor.deleteDocument(binding.corpusRef(), entry.path());
                } catch (Exception e) {
                    LOG.log(Level.SEVERE, "Delete failed for " + entry.path() + " in " + binding.name(), e);
                    hasErrors = true;
                }
            }
        }

        // Phase 2 — Ingestion
        List<ChunkInput> allChunks = new ArrayList<>();
        for (ChangedEntry entry : changeSet.entries()) {
            if (entry.type() == ChangeType.ADDED || entry.type() == ChangeType.MODIFIED) {
                try {
                    Optional<byte[]> content = binding.corpusReader().read(entry.path());
                    if (content.isEmpty()) {
                        LOG.info(() -> "Skipping " + entry.path() + " — no longer in corpus");
                        continue;
                    }
                    ExtractionResult result = binding.metadataExtractor().extract(entry.path(), content.get());
                    List<ChunkInput> chunks = chunkDocument(entry.path(), result, splitter);
                    allChunks.addAll(chunks);
                } catch (Exception e) {
                    LOG.log(Level.SEVERE, "Processing failed for " + entry.path() + " in " + binding.name(), e);
                    hasErrors = true;
                }
            }
        }

        if (!allChunks.isEmpty()) {
            try {
                ingestor.ingest(binding.corpusRef(), allChunks);
            } catch (Exception e) {
                LOG.log(Level.SEVERE, "Ingest batch failed for " + binding.name(), e);
                hasErrors = true;
            }
        }

        if (!hasErrors) {
            cursorStore.save(binding.name(), changeSet.newCursor());
        } else {
            LOG.warning(() -> "Cursor not advanced for " + binding.name() + " due to errors — will retry next poll");
        }
    }

    public void reconcile(String corpusName, CorpusIngestionBinding binding) {
        reconcile(corpusName, binding, null);
    }

    public void reconcile(String corpusName, CorpusIngestionBinding binding, DocumentSplitter splitter) {
        ReentrantLock lock = locks.computeIfAbsent(corpusName, k -> new ReentrantLock());
        if (!lock.tryLock()) {
            LOG.fine(() -> "Skipping reconciliation for " + corpusName + " — already processing");
            return;
        }
        try {
            doReconcile(binding, splitter);
        } finally {
            lock.unlock();
        }
    }

    private void doReconcile(CorpusIngestionBinding binding, DocumentSplitter splitter) {
        ChangeSet fullScan;
        try {
            fullScan = binding.changeSource().fullScan();
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "fullScan() failed for " + binding.name(), e);
            return;
        }

        List<String> corpusPaths = fullScan.entries().stream()
            .map(ChangedEntry::path).toList();
        List<String> qdrantDocs = ingestor.listDocuments(binding.corpusRef());

        // In corpus but not in Qdrant — reingest
        for (String path : corpusPaths) {
            if (!qdrantDocs.contains(path)) {
                try {
                    Optional<byte[]> content = binding.corpusReader().read(path);
                    if (content.isEmpty()) continue;
                    ExtractionResult result = binding.metadataExtractor().extract(path, content.get());
                    List<ChunkInput> chunks = chunkDocument(path, result, splitter);
                    if (!chunks.isEmpty()) {
                        ingestor.ingest(binding.corpusRef(), chunks);
                    }
                } catch (Exception e) {
                    LOG.log(Level.WARNING, "Reconciliation reingest failed for " + path, e);
                }
            }
        }

        // In Qdrant but not in corpus — delete
        for (String docId : qdrantDocs) {
            if (!corpusPaths.contains(docId)) {
                try {
                    ingestor.deleteDocument(binding.corpusRef(), docId);
                } catch (Exception e) {
                    LOG.log(Level.WARNING, "Reconciliation delete failed for " + docId, e);
                }
            }
        }

        // Best-effort: always save cursor
        cursorStore.save(binding.name(), fullScan.newCursor());
    }

    private List<ChunkInput> chunkDocument(String path, ExtractionResult result, DocumentSplitter splitter) {
        if (result.body().isBlank()) {
            return List.of();
        }

        if (splitter == null) {
            return List.of(new ChunkInput(result.body(), path, result.metadata()));
        }

        Document doc = Document.from(result.body());
        List<TextSegment> segments = splitter.split(doc);
        List<ChunkInput> chunks = new ArrayList<>(segments.size());
        for (TextSegment segment : segments) {
            chunks.add(new ChunkInput(segment.text(), path, result.metadata()));
        }
        return chunks;
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=CorpusIngestionServiceTest`
Expected: PASS

- [ ] **Step 5: Add remaining tests — one at a time, verify each passes**

Add these tests to `CorpusIngestionServiceTest.java`:

```java
@Test
void deletedEntriesRemoveFromQdrant() {
    // Pre-populate Qdrant
    ingestor.ingest(CORPUS, List.of(new io.casehub.rag.ChunkInput("content", "tools/old.md", Map.of())));

    var changes = new ChangeSet(
        List.of(new ChangedEntry("tools/old.md", ChangeType.DELETED)),
        "cursor-2"
    );
    ChangeSource source = fixedSource(changes);

    service().processBinding(binding(source, stubReader(Map.of())));

    assertThat(ingestor.listDocuments(CORPUS)).isEmpty();
    assertThat(cursorStore.load("garden")).contains("cursor-2");
}

@Test
void modifiedEntriesDeleteThenReingest() {
    ingestor.ingest(CORPUS, List.of(new io.casehub.rag.ChunkInput("old content", "tools/git.md", Map.of())));

    var changes = new ChangeSet(
        List.of(new ChangedEntry("tools/git.md", ChangeType.MODIFIED)),
        "cursor-2"
    );
    ChangeSource source = fixedSource(changes);
    CorpusReader reader = stubReader(Map.of("tools/git.md", "updated content"));

    service().processBinding(binding(source, reader));

    assertThat(ingestor.getChunks(CORPUS)).hasSize(1);
    assertThat(ingestor.getChunks(CORPUS).get(0).content()).isEqualTo("updated content");
    assertThat(cursorStore.load("garden")).contains("cursor-2");
}

@Test
void bootstrapCallsFullScanWhenNoCursor() {
    boolean[] fullScanCalled = {false};
    var changes = new ChangeSet(
        List.of(new ChangedEntry("doc.md", ChangeType.ADDED)),
        "cursor-1"
    );
    ChangeSource source = new ChangeSource() {
        @Override public ChangeSet changesSince(String cursor) {
            throw new AssertionError("Should not call changesSince when no cursor");
        }
        @Override public ChangeSet fullScan() {
            fullScanCalled[0] = true;
            return changes;
        }
    };

    service().processBinding(binding(source, stubReader(Map.of("doc.md", "content"))));

    assertThat(fullScanCalled[0]).isTrue();
    assertThat(cursorStore.load("garden")).contains("cursor-1");
}

@Test
void existingCursorUsesChangesSince() {
    cursorStore.save("garden", "prev-cursor");
    String[] receivedCursor = {null};
    var changes = new ChangeSet(List.of(), "cursor-2");
    ChangeSource source = new ChangeSource() {
        @Override public ChangeSet changesSince(String cursor) {
            receivedCursor[0] = cursor;
            return changes;
        }
        @Override public ChangeSet fullScan() {
            throw new AssertionError("Should not call fullScan when cursor exists");
        }
    };

    service().processBinding(binding(source, stubReader(Map.of())));

    assertThat(receivedCursor[0]).isEqualTo("prev-cursor");
}

@Test
void emptyReadSkipsEntryButCursorAdvances() {
    var changes = new ChangeSet(
        List.of(new ChangedEntry("gone.md", ChangeType.ADDED)),
        "cursor-1"
    );
    ChangeSource source = fixedSource(changes);
    CorpusReader reader = stubReader(Map.of()); // gone.md not in reader

    service().processBinding(binding(source, reader));

    assertThat(ingestor.listDocuments(CORPUS)).isEmpty();
    assertThat(cursorStore.load("garden")).contains("cursor-1");
}

@Test
void extractorErrorBlocksCursor() {
    var changes = new ChangeSet(
        List.of(new ChangedEntry("bad.md", ChangeType.ADDED)),
        "cursor-1"
    );
    ChangeSource source = fixedSource(changes);
    CorpusReader reader = stubReader(Map.of("bad.md", "content"));
    MetadataExtractor failingExtractor = (path, content) -> { throw new RuntimeException("parse error"); };

    service().processBinding(binding(source, reader, failingExtractor));

    assertThat(ingestor.listDocuments(CORPUS)).isEmpty();
    assertThat(cursorStore.load("garden")).isEmpty();
}

@Test
void metadataFromExtractorAppearsInChunks() {
    var changes = new ChangeSet(
        List.of(new ChangedEntry("doc.md", ChangeType.ADDED)),
        "cursor-1"
    );
    ChangeSource source = fixedSource(changes);
    CorpusReader reader = stubReader(Map.of("doc.md", "body"));
    MetadataExtractor extractor = (path, content) ->
        new ExtractionResult("body", Map.of("title", "Test", "domain", "tools"));

    service().processBinding(binding(source, reader, extractor));

    var chunks = ingestor.getChunks(CORPUS);
    assertThat(chunks).hasSize(1);
    assertThat(chunks.get(0).metadata()).containsEntry("title", "Test");
    assertThat(chunks.get(0).metadata()).containsEntry("domain", "tools");
}

@Test
void recursiveChunkingSplitsBody() {
    var changes = new ChangeSet(
        List.of(new ChangedEntry("long.md", ChangeType.ADDED)),
        "cursor-1"
    );
    ChangeSource source = fixedSource(changes);
    String longBody = "Paragraph one. ".repeat(100) + "\n\n" + "Paragraph two. ".repeat(100);
    CorpusReader reader = stubReader(Map.of("long.md", longBody));

    DocumentSplitter splitter = DocumentSplitters.recursive(200, 20);
    service().processBinding(binding(source, reader), splitter);

    assertThat(ingestor.getChunks(CORPUS).size()).isGreaterThan(1);
    assertThat(ingestor.listDocuments(CORPUS)).containsExactly("long.md");
}

@Test
void reconcileReingests_missingFromQdrant() {
    var fullScan = new ChangeSet(
        List.of(new ChangedEntry("doc.md", ChangeType.ADDED)),
        "cursor-full"
    );
    ChangeSource source = fixedSource(fullScan);
    CorpusReader reader = stubReader(Map.of("doc.md", "content"));

    service().reconcile("garden", binding(source, reader));

    assertThat(ingestor.listDocuments(CORPUS)).containsExactly("doc.md");
    assertThat(cursorStore.load("garden")).contains("cursor-full");
}

@Test
void reconcileDeletes_extraFromQdrant() {
    ingestor.ingest(CORPUS, List.of(new io.casehub.rag.ChunkInput("old", "stale.md", Map.of())));

    var fullScan = new ChangeSet(List.of(), "cursor-full");
    ChangeSource source = fixedSource(fullScan);

    service().reconcile("garden", binding(source, stubReader(Map.of())));

    assertThat(ingestor.listDocuments(CORPUS)).isEmpty();
    assertThat(cursorStore.load("garden")).contains("cursor-full");
}

@Test
void reconcileIsBestEffort_cursorAdvancesOnError() {
    var fullScan = new ChangeSet(
        List.of(new ChangedEntry("bad.md", ChangeType.ADDED)),
        "cursor-full"
    );
    ChangeSource source = fixedSource(fullScan);
    CorpusReader reader = stubReader(Map.of("bad.md", "content"));
    MetadataExtractor failing = (path, content) -> { throw new RuntimeException("corrupt"); };

    service().reconcile("garden", binding(source, reader, failing));

    assertThat(ingestor.listDocuments(CORPUS)).isEmpty();
    assertThat(cursorStore.load("garden")).contains("cursor-full");
}

// Helper
private ChangeSource fixedSource(ChangeSet changes) {
    return new ChangeSource() {
        @Override public ChangeSet changesSince(String cursor) { return changes; }
        @Override public ChangeSet fullScan() { return changes; }
    };
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=CorpusIngestionServiceTest`
Expected: All tests pass

- [ ] **Step 6: Commit**

```
feat(#19): CorpusIngestionService — poll loop, reconciliation, error handling
```

---

### Task 8: rag/ — CorpusBindingProducer

**Files:**
- Create: `rag/src/main/java/io/casehub/rag/runtime/CorpusConfig.java`
- Create: `rag/src/main/java/io/casehub/rag/runtime/CorpusBindingProducer.java`
- Create: `rag/src/test/java/io/casehub/rag/runtime/CorpusBindingProducerTest.java`

The producer reads corpus-level config (`casehub.corpus.<name>.*`) and ingestion-level config (`casehub.rag.ingestion.corpora.<name>.*`), creates corpus implementation objects, and returns a list of bindings.

- [ ] **Step 1: Create CorpusConfig**

```java
package io.casehub.rag.runtime;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;
import java.util.Map;

@ConfigMapping(prefix = "casehub.corpus")
public interface CorpusConfig {

    Map<String, CorpusInstanceConfig> corpora();

    interface CorpusInstanceConfig {
        String source();

        @WithDefault("ZIP")
        String mode();

        @WithDefault("104857600")
        long maxZipSize();
    }
}
```

Note: The `corpora` key nesting mirrors `IngestionConfig.corpora()`. Corpus-level config uses `casehub.corpus.corpora.<name>.*`. If the existing corpus tests use a flat `casehub.corpus.<name>.*` structure, adjust the config mapping accordingly. The implementation may need to align with however the corpus module's own config is structured — verify during implementation and adapt.

- [ ] **Step 2: Write CorpusBindingProducer test**

```java
package io.casehub.rag.runtime;

import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.time.Duration;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class CorpusBindingProducerTest {

    @Test
    void producesBindingFromConfig() {
        // Create a temp directory with a flat file
        Path tempDir = Path.of(System.getProperty("java.io.tmpdir"), "corpus-test-" + System.nanoTime());
        tempDir.toFile().mkdirs();

        var ingestionConfig = stubIngestionConfig(Map.of(
            "garden", stubCorpusIngestionConfig("default", "garden", "AUTO")
        ));
        var corpusConfig = stubCorpusConfig(Map.of(
            "garden", stubCorpusInstanceConfig(tempDir.toString(), "FLAT")
        ));
        var extractor = new YamlFrontmatterExtractor();

        var producer = new CorpusBindingProducer(ingestionConfig, corpusConfig, extractor);
        var bindings = producer.bindings();

        assertThat(bindings).hasSize(1);
        assertThat(bindings.get(0).name()).isEqualTo("garden");
        assertThat(bindings.get(0).corpusRef().tenantId()).isEqualTo("default");
        assertThat(bindings.get(0).corpusRef().corpusName()).isEqualTo("garden");

        // Cleanup
        tempDir.toFile().delete();
    }

    // Stub helpers — implement inline config interfaces for testing
    // These create concrete implementations of the @ConfigMapping interfaces
    // The actual implementation details depend on how Quarkus SmallRye Config
    // handles test instantiation — may need adjustment during implementation.
}
```

Note: This test may need to be a `@QuarkusTest` if `@ConfigMapping` interfaces cannot be easily stubbed. The implementation should determine the cleanest test approach — either manual interface implementation or a Quarkus test with `application.properties` entries.

- [ ] **Step 3: Implement CorpusBindingProducer**

```java
package io.casehub.rag.runtime;

import io.casehub.corpus.zip.CompositeCorpusStore;
import io.casehub.corpus.zip.FlatCorpusStore;
import io.casehub.corpus.zip.ZipCorpusStore;
import io.casehub.rag.CorpusRef;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.logging.Logger;

@ApplicationScoped
public class CorpusBindingProducer {

    private static final Logger LOG = Logger.getLogger(CorpusBindingProducer.class.getName());

    private final IngestionConfig ingestionConfig;
    private final CorpusConfig corpusConfig;
    private final YamlFrontmatterExtractor defaultExtractor;

    @Inject
    CorpusBindingProducer(IngestionConfig ingestionConfig, CorpusConfig corpusConfig,
                          YamlFrontmatterExtractor defaultExtractor) {
        this.ingestionConfig = ingestionConfig;
        this.corpusConfig = corpusConfig;
        this.defaultExtractor = defaultExtractor;
    }

    public List<CorpusIngestionBinding> bindings() {
        List<CorpusIngestionBinding> result = new ArrayList<>();
        for (Map.Entry<String, IngestionConfig.CorpusIngestionConfig> entry : ingestionConfig.corpora().entrySet()) {
            String name = entry.getKey();
            var ingestion = entry.getValue();
            if (ingestion.mode() == IngestionMode.NONE) continue;

            var corpusInstance = corpusConfig.corpora().get(name);
            if (corpusInstance == null) {
                LOG.warning(() -> "Ingestion config references corpus '" + name + "' but no casehub.corpus.corpora." + name + ".* config found — skipping");
                continue;
            }

            CorpusRef corpusRef = new CorpusRef(ingestion.tenantId(), ingestion.corpusName());
            Path sourcePath = Path.of(corpusInstance.source());

            // Create corpus implementation based on mode
            // The actual construction depends on corpus module's factory methods
            // This is the design debt acknowledged in the spec — will be extracted
            // to corpus-quarkus/ when the second consumer materialises.
            var store = createCorpusStore(name, corpusInstance, sourcePath);

            result.add(new CorpusIngestionBinding(
                name, corpusRef,
                store.changeSource(), store.reader(),
                defaultExtractor
            ));
        }
        return result;
    }

    // Private: creates the corpus store based on config mode
    // The exact API depends on ZipCorpusStore/FlatCorpusStore/CompositeCorpusStore
    // constructors — adapt during implementation.
    private CorpusStoreBundle createCorpusStore(String name,
            CorpusConfig.CorpusInstanceConfig config, Path sourcePath) {
        // Implementation will call the appropriate corpus constructor
        // based on config.mode() — ZIP, FLAT, or COMPOSITE
        throw new UnsupportedOperationException("Implement during Task 8 Step 3");
    }

    // Bundle to carry all three corpus objects from a single store
    record CorpusStoreBundle(
        io.casehub.corpus.ChangeSource changeSource,
        io.casehub.corpus.CorpusReader reader
    ) {}
}
```

Note: The exact constructor calls for `ZipCorpusStore`, `FlatCorpusStore`, and `CompositeCorpusStore` depend on their actual APIs. During implementation, read their constructors via IntelliJ MCP and adapt accordingly. The `CorpusStoreBundle` record is a convenience — if the store classes expose `changeSource()` and `reader()` methods directly, use those instead.

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=CorpusBindingProducerTest`
Expected: PASS

- [ ] **Step 5: Commit**

```
feat(#19): CorpusBindingProducer — config-driven corpus binding creation
```

---

### Task 9: rag/ — Wire @Scheduled polling into CorpusIngestionService

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/CorpusIngestionService.java`

- [ ] **Step 1: Add CDI wiring for the scheduled poll loop**

Add to `CorpusIngestionService`:

```java
@Inject Instance<CorpusIngestionBinding> customBindings;
@Inject CorpusBindingProducer bindingProducer;
@Inject IngestionConfig config;

@Scheduled(every = "${casehub.rag.ingestion.interval:30s}", concurrentExecution = Scheduled.ConcurrentExecution.SKIP)
void poll() {
    for (CorpusIngestionBinding binding : allBindings()) {
        IngestionMode mode = modeFor(binding);
        if (mode == IngestionMode.AUTO) {
            DocumentSplitter splitter = splitterFor(binding.name());
            processBinding(binding, splitter);
        }
    }
}

public void triggerManual(String corpusName) {
    for (CorpusIngestionBinding binding : allBindings()) {
        if (binding.name().equals(corpusName)) {
            processBinding(binding, splitterFor(binding.name()));
            return;
        }
    }
    LOG.warning(() -> "No binding found for corpus: " + corpusName);
}

public void reconcile(String corpusName) {
    for (CorpusIngestionBinding binding : allBindings()) {
        if (binding.name().equals(corpusName)) {
            reconcile(corpusName, binding, splitterFor(binding.name()));
            return;
        }
    }
    LOG.warning(() -> "No binding found for corpus: " + corpusName);
}

public void reconcileAll() {
    for (CorpusIngestionBinding binding : allBindings()) {
        reconcile(binding.name(), binding, splitterFor(binding.name()));
    }
}

private List<CorpusIngestionBinding> allBindings() {
    List<CorpusIngestionBinding> all = new ArrayList<>(bindingProducer.bindings());
    customBindings.forEach(all::add);
    return all;
}

private IngestionMode modeFor(CorpusIngestionBinding binding) {
    var corpusConfig = config.corpora().get(binding.name());
    if (corpusConfig == null) return IngestionMode.AUTO; // custom bindings default to AUTO
    return corpusConfig.mode();
}

private DocumentSplitter splitterFor(String corpusName) {
    var corpusConfig = config.corpora().get(corpusName);
    if (corpusConfig == null || "none".equalsIgnoreCase(corpusConfig.chunking())) {
        return null;
    }
    if ("recursive".equalsIgnoreCase(corpusConfig.chunking())) {
        int maxSize = corpusConfig.chunkingMaxSize().orElse(1000);
        int overlap = corpusConfig.chunkingOverlapSize().orElse(200);
        return DocumentSplitters.recursive(maxSize, overlap);
    }
    LOG.warning(() -> "Unknown chunking strategy: " + corpusConfig.chunking() + " — defaulting to none");
    return null;
}
```

- [ ] **Step 2: Build and run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`
Expected: All tests pass

- [ ] **Step 3: Commit**

```
feat(#19): wire @Scheduled polling + manual trigger + reconcileAll
```

---

### Task 10: Full build verification

- [ ] **Step 1: Full build with all modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS — all modules compile, all tests pass

- [ ] **Step 2: Verify no regressions**

Check that all existing tests in rag/, rag-api/, rag-testing/ still pass alongside the new tests.

- [ ] **Step 3: Final commit if any adjustments needed**

```
chore(#19): full build verification
```

---

## Self-Review

**Spec coverage:**
- MetadataExtractor SPI → Task 2 ✅
- ExtractionResult → Task 2 ✅
- CursorStore SPI → Task 2 ✅
- CorpusIngestionBinding → Task 4 ✅
- IngestionMode → Task 4 ✅
- IngestionConfig → Task 4 ✅
- YamlFrontmatterExtractor → Task 5 ✅
- FileCursorStore → Task 6 ✅
- CorpusIngestionService (poll + reconciliation) → Tasks 7 + 9 ✅
- CorpusBindingProducer → Task 8 ✅
- InMemoryCursorStore → Task 3 ✅
- assertTenant prerequisite → Task 1 ✅
- Dependency changes → Task 0 ✅
- Delete-then-reingest for MODIFIED → Task 7 test ✅
- Bootstrap fullScan() when no cursor → Task 7 test ✅
- All-or-nothing cursor (poll) → Task 7 test ✅
- Best-effort cursor (reconciliation) → Task 7 test ✅

**Placeholder scan:** No TBDs in code. Task 8 (`CorpusBindingProducer`) has implementation notes about constructor adaptation — these are implementation guidance, not placeholders.

**Type consistency:** `CorpusIngestionBinding` fields match across Task 4 (creation), Task 7 (usage in service), Task 8 (producer). `processBinding()` method signature consistent across Task 7 and Task 9.

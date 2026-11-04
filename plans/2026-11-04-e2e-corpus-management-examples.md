# E2E Corpus-Management Examples Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #786 — E2E examples for corpus-management across diverse domains
**Issue group:** #789 (parent epic)

**Goal:** Prove corpus-management is domain-neutral with 4 working E2E examples (garden, literature, clinical, game NPC) plus a federation scenario, all as a single Maven example module.

**Architecture:** Single `example-corpus-management/` module with plain JUnit tests. A shared `CorpusTestHarness` wires SQLite `:memory:` implementations (SqliteCorpusCatalogue, SqliteCorpusEntryStore) and a simple `InMemoryCorpusSearch` stub. Each domain defines its own `CorpusType` with distinct `FieldSchema` maps. Federation scenario crosses literature + clinical domains.

**Tech Stack:** Java 21, JUnit 5, AssertJ, SQLite `:memory:` via SqliteDataSourceFactory, corpus-management-api, corpus-management

## Global Constraints

- No CDI / no Quarkus — corpus-management is framework-neutral
- Custom `CorpusType` instances only — do NOT use `CorpusType.KNOWLEDGE_GARDEN`/`RESEARCH`/`TRANSCRIPT` constants (Phase 2 will remove them)
- String bodies only — no structured content (Phase 3 will add Content hierarchy)
- No vector search / no Qdrant — in-memory search with text substring matching
- Use `SqliteCorpusCatalogue.register()/updateLifecycle()/deregister()` — no production `CorpusManager` implementation exists
- Tests must pass with `mvn test -Pexamples-smoke -pl examples/example-corpus-management`

---

## Batch 1: Module scaffold and test harness

### Task 1: Create example-corpus-management module with POM and test harness

**Files:**
- Create: `examples/example-corpus-management/pom.xml`
- Create: `examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/CorpusTestHarness.java`
- Create: `examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/InMemoryCorpusSearch.java`
- Modify: `pom.xml` (parent) — add module to `examples-smoke` profile

**Interfaces:**
- Consumes: `SqliteDataSourceFactory.create(String, int, int)` from sqlite-support, `SqliteCorpusCatalogue(DataSource)` from corpus-management, `SqliteCorpusEntryStore(DataSource, EmbeddingIngestor)` from corpus-management, `ChainWalkerFederatedSearch(CorpusCatalogue, CorpusSearch, double)` from corpus-management
- Produces: `CorpusTestHarness.create()` returning harness with `catalogue()`, `entryStore()`, `search()`, `federatedSearch()` accessors; `InMemoryCorpusSearch` implementing `CorpusSearch` via `CorpusEntryStore`

- [ ] **Step 1: Create POM**

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-parent</artifactId>
    <version>0.4-SNAPSHOT</version>
    <relativePath>../../pom.xml</relativePath>
  </parent>

  <artifactId>casehub-neocortex-example-corpus-management</artifactId>
  <name>CaseHub Neocortex - Example: Corpus Management</name>
  <description>E2E examples proving corpus-management works across diverse domains</description>

  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-corpus-management-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-corpus-management</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-sqlite-support</artifactId>
    </dependency>

    <!-- Test -->
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

  <profiles>
    <profile>
      <id>examples-smoke</id>
      <build>
        <plugins>
          <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-surefire-plugin</artifactId>
            <configuration>
              <groups>smoke</groups>
            </configuration>
          </plugin>
        </plugins>
      </build>
    </profile>
  </profiles>
</project>
```

- [ ] **Step 2: Add module to parent POM examples-smoke profile**

In the parent `pom.xml`, inside the `<id>examples-smoke</id>` profile's `<modules>` section, add:
```xml
<module>examples/example-corpus-management</module>
```

- [ ] **Step 3: Write InMemoryCorpusSearch**

A simple `CorpusSearch` that does text substring matching against stored entries. This is NOT a production search — it's a test stub that proves the API surface works.

```java
package io.casehub.neocortex.examples.corpus;

import io.casehub.neocortex.corpus.management.CorpusEntry;
import io.casehub.neocortex.corpus.management.CorpusEntryStore;
import io.casehub.neocortex.corpus.management.CorpusQuery;
import io.casehub.neocortex.corpus.management.CorpusSearch;
import io.casehub.neocortex.corpus.management.CorpusSearchResult;
import io.casehub.neocortex.rag.CorpusRef;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class InMemoryCorpusSearch implements CorpusSearch {

    private final Map<CorpusRef, List<CorpusEntry>> entries = new ConcurrentHashMap<>();

    public void index(CorpusRef corpus, CorpusEntry entry) {
        entries.computeIfAbsent(corpus, k -> new ArrayList<>()).add(entry);
    }

    public void remove(CorpusRef corpus, String entryId) {
        var list = entries.get(corpus);
        if (list != null) {
            list.removeIf(e -> e.id().equals(entryId));
        }
    }

    @Override
    public List<CorpusSearchResult> search(CorpusRef corpus, CorpusQuery query) {
        var corpusEntries = entries.getOrDefault(corpus, List.of());
        var results = new ArrayList<CorpusSearchResult>();
        String queryText = query.text().toLowerCase();

        for (var entry : corpusEntries) {
            double score = 0.0;
            String body = entry.body() != null ? entry.body().toLowerCase() : "";
            String title = entry.stringField("title");
            if (title != null) title = title.toLowerCase(); else title = "";

            if (body.contains(queryText) || title.contains(queryText)) {
                score = 1.0;
            } else {
                for (String word : queryText.split("\\s+")) {
                    if (body.contains(word) || title.contains(word)) {
                        score += 0.5;
                    }
                }
            }

            if (score > 0) {
                results.add(new CorpusSearchResult(entry, score, corpus, 0, Instant.now()));
            }
        }

        results.sort((a, b) -> Double.compare(b.score(), a.score()));
        return results.stream().limit(query.maxResults()).toList();
    }
}
```

- [ ] **Step 4: Write CorpusTestHarness**

```java
package io.casehub.neocortex.examples.corpus;

import io.casehub.neocortex.corpus.management.CorpusCatalogue;
import io.casehub.neocortex.corpus.management.CorpusEntry;
import io.casehub.neocortex.corpus.management.CorpusEntryStore;
import io.casehub.neocortex.corpus.management.FederatedCorpusSearch;
import io.casehub.neocortex.corpus.management.impl.ChainWalkerFederatedSearch;
import io.casehub.neocortex.corpus.management.impl.SqliteCorpusCatalogue;
import io.casehub.neocortex.corpus.management.impl.SqliteCorpusEntryStore;
import io.casehub.neocortex.rag.ChunkInput;
import io.casehub.neocortex.rag.CorpusRef;
import io.casehub.neocortex.rag.EmbeddingIngestor;
import io.casehub.neocortex.sqlite.SqliteDataSourceFactory;

import java.util.List;

public class CorpusTestHarness {

    private final SqliteCorpusCatalogue catalogue;
    private final SqliteCorpusEntryStore entryStore;
    private final InMemoryCorpusSearch search;
    private final ChainWalkerFederatedSearch federatedSearch;

    private CorpusTestHarness(SqliteCorpusCatalogue catalogue,
                               SqliteCorpusEntryStore entryStore,
                               InMemoryCorpusSearch search,
                               ChainWalkerFederatedSearch federatedSearch) {
        this.catalogue = catalogue;
        this.entryStore = entryStore;
        this.search = search;
        this.federatedSearch = federatedSearch;
    }

    public static CorpusTestHarness create() {
        var ds = SqliteDataSourceFactory.create(":memory:", 1, 3000);
        var catalogue = new SqliteCorpusCatalogue(ds);
        var noOpIngestor = new NoOpIngestor();
        var entryStore = new SqliteCorpusEntryStore(ds, noOpIngestor);
        var search = new InMemoryCorpusSearch();
        var federatedSearch = new ChainWalkerFederatedSearch(catalogue, search, 0.1);
        return new CorpusTestHarness(catalogue, entryStore, search, federatedSearch);
    }

    public SqliteCorpusCatalogue catalogue() { return catalogue; }
    public SqliteCorpusEntryStore entryStore() { return entryStore; }
    public InMemoryCorpusSearch search() { return search; }
    public ChainWalkerFederatedSearch federatedSearch() { return federatedSearch; }

    public void addEntry(CorpusRef corpus, CorpusEntry entry) {
        entryStore.add(corpus, entry);
        search.index(corpus, entry);
    }

    private static class NoOpIngestor implements EmbeddingIngestor {
        @Override public void ingest(CorpusRef corpus, List<ChunkInput> chunks) {}
        @Override public void deleteDocument(CorpusRef corpus, String sourceDocumentId) {}
        @Override public void deleteCorpus(CorpusRef corpus) {}
        @Override public List<String> listDocuments(CorpusRef corpus) { return List.of(); }
    }
}
```

- [ ] **Step 5: Verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile test-compile -pl examples/example-corpus-management -Pexamples-smoke -am`
Expected: BUILD SUCCESS

- [ ] **Step 6: Commit**

```bash
git add examples/example-corpus-management/pom.xml \
       examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/CorpusTestHarness.java \
       examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/InMemoryCorpusSearch.java \
       pom.xml
git commit -m "feat(#786): scaffold example-corpus-management module with test harness

Add CorpusTestHarness (SQLite :memory: wiring) and InMemoryCorpusSearch
(substring-matching stub for test scenarios).

Refs #786"
```

---

## Batch 2: Domain scenario tests — garden and literature

### Task 2: Garden domain scenario

**Files:**
- Create: `examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/domains/garden/GardenCorpusTypes.java`
- Create: `examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/domains/garden/GardenScenarioTest.java`

**Interfaces:**
- Consumes: `CorpusTestHarness.create()`, `CorpusTestHarness.catalogue()`, `CorpusTestHarness.addEntry()`, `CorpusTestHarness.search()`
- Produces: `GardenCorpusTypes.GARDEN` — custom `CorpusType` with garden-specific fields

- [ ] **Step 1: Write GardenCorpusTypes**

```java
package io.casehub.neocortex.examples.corpus.domains.garden;

import io.casehub.neocortex.corpus.management.CorpusType;
import io.casehub.neocortex.corpus.management.FieldSchema;

import java.util.Map;

public final class GardenCorpusTypes {

    public static final CorpusType GARDEN = new CorpusType(
        "knowledge-garden-example",
        Map.of(
            "id", FieldSchema.STRING,
            "title", FieldSchema.STRING,
            "type", FieldSchema.STRING,
            "domain", FieldSchema.STRING
        ),
        Map.of(
            "tags", FieldSchema.STRING_LIST,
            "score", FieldSchema.DOUBLE,
            "staleness_threshold", FieldSchema.DURATION,
            "invalidation_triggers", FieldSchema.STRING_LIST
        ),
        null
    );

    private GardenCorpusTypes() {}
}
```

- [ ] **Step 2: Write GardenScenarioTest — failing test skeleton**

```java
package io.casehub.neocortex.examples.corpus.domains.garden;

import io.casehub.neocortex.corpus.management.CorpusEntry;
import io.casehub.neocortex.corpus.management.CorpusLifecycle;
import io.casehub.neocortex.corpus.management.CorpusQuery;
import io.casehub.neocortex.examples.corpus.CorpusTestHarness;
import io.casehub.neocortex.rag.CorpusRef;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class GardenScenarioTest {

    private static final String TENANT = "garden-tenant";
    private CorpusTestHarness harness;

    @BeforeEach
    void setUp() {
        harness = CorpusTestHarness.create();
    }

    @Test
    void fullLifecycle() {
        // Create
        var desc = harness.catalogue().register(
            "java-garden", GardenCorpusTypes.GARDEN, TENANT,
            "vec-java-garden", List.of(), List.of(), Map.of());
        var corpus = desc.corpusRef();
        assertThat(desc.type().name()).isEqualTo("knowledge-garden-example");
        assertThat(desc.lifecycle()).isEqualTo(CorpusLifecycle.ACTIVE);

        // Ingest
        harness.addEntry(corpus, new CorpusEntry("ge-001",
            Map.of("title", "Quarkus CDI quirks", "type", "gotcha", "domain", "jvm",
                   "tags", List.of("quarkus", "cdi", "injection")),
            "ArC does not support private injection points in Quarkus.", null));
        harness.addEntry(corpus, new CorpusEntry("ge-002",
            Map.of("title", "Flyway migration ordering", "type", "technique", "domain", "database",
                   "tags", List.of("flyway", "sqlite", "migration")),
            "Use V-prefixed timestamps for Flyway migration scripts to avoid ordering conflicts.", null));
        harness.addEntry(corpus, new CorpusEntry("ge-003",
            Map.of("title", "ONNX session thread safety", "type", "gotcha", "domain", "inference",
                   "tags", List.of("onnx", "threading")),
            "OrtSession.run() is thread-safe but session creation is not.", null));
        harness.addEntry(corpus, new CorpusEntry("ge-004",
            Map.of("title", "AssertJ soft assertions", "type", "technique", "domain", "testing",
                   "tags", List.of("assertj", "testing")),
            "Use SoftAssertions to collect multiple failures in one test run.", null));
        harness.addEntry(corpus, new CorpusEntry("ge-005",
            Map.of("title", "SQLite WAL mode", "type", "decision", "domain", "database",
                   "tags", List.of("sqlite", "wal", "performance")),
            "WAL mode allows concurrent reads during writes — essential for HikariCP.", null));

        // Search
        var results = harness.search().search(corpus, CorpusQuery.of("sqlite"));
        assertThat(results).isNotEmpty();
        assertThat(results).extracting(r -> r.entry().id())
            .contains("ge-002", "ge-005");

        // Catalogue
        assertThat(harness.catalogue().list(TENANT, CorpusLifecycle.ACTIVE)).hasSize(1);
        assertThat(harness.catalogue().get(corpus)).isPresent();
        assertThat(harness.catalogue().forType(GardenCorpusTypes.GARDEN, TENANT)).hasSize(1);

        // Archive
        harness.catalogue().updateLifecycle(corpus, CorpusLifecycle.ARCHIVED);
        assertThat(harness.catalogue().list(TENANT, CorpusLifecycle.ACTIVE)).isEmpty();
        assertThat(harness.catalogue().list(TENANT, CorpusLifecycle.ARCHIVED)).hasSize(1);

        // Revive
        harness.catalogue().updateLifecycle(corpus, CorpusLifecycle.ACTIVE);
        assertThat(harness.catalogue().list(TENANT, CorpusLifecycle.ACTIVE)).hasSize(1);
    }

    @Test
    void entryStoreRoundTrip() {
        var desc = harness.catalogue().register(
            "roundtrip-garden", GardenCorpusTypes.GARDEN, TENANT,
            "vec-unused", List.of(), List.of(), Map.of());
        var corpus = desc.corpusRef();

        var entry = new CorpusEntry("ge-rt",
            Map.of("title", "Round trip test", "type", "technique", "domain", "testing",
                   "score", 0.85, "tags", List.of("test", "roundtrip")),
            "Testing metadata round-trip through the entry store.", null);
        harness.addEntry(corpus, entry);

        var retrieved = harness.entryStore().get(corpus, "ge-rt");
        assertThat(retrieved).isPresent();
        assertThat(retrieved.get().stringField("title")).isEqualTo("Round trip test");
        assertThat(retrieved.get().doubleField("score")).isEqualTo(0.85);
        assertThat(retrieved.get().stringListField("tags")).containsExactly("test", "roundtrip");
    }
}
```

- [ ] **Step 3: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-corpus-management -Pexamples-smoke -am`
Expected: PASS — 2 tests

- [ ] **Step 4: Commit**

```bash
git add examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/domains/garden/
git commit -m "feat(#786): add garden domain scenario

Defines GardenCorpusTypes (STRING, STRING_LIST, DOUBLE, DURATION) and
GardenScenarioTest exercising full lifecycle and metadata round-trip.

Refs #786"
```

### Task 3: Literature domain scenario

**Files:**
- Create: `examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/domains/literature/LiteratureCorpusTypes.java`
- Create: `examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/domains/literature/LiteratureScenarioTest.java`

**Interfaces:**
- Consumes: `CorpusTestHarness.create()`, `CorpusTestHarness.addEntry()`
- Produces: `LiteratureCorpusTypes.LITERATURE` — custom `CorpusType` with academic paper fields (STRING_LIST for authors/citations, INTEGER for year)

- [ ] **Step 1: Write LiteratureCorpusTypes**

```java
package io.casehub.neocortex.examples.corpus.domains.literature;

import io.casehub.neocortex.corpus.management.CorpusType;
import io.casehub.neocortex.corpus.management.FieldSchema;

import java.util.Map;

public final class LiteratureCorpusTypes {

    public static final CorpusType LITERATURE = new CorpusType(
        "academic-literature",
        Map.of(
            "id", FieldSchema.STRING,
            "title", FieldSchema.STRING,
            "authors", FieldSchema.STRING_LIST,
            "year", FieldSchema.INTEGER,
            "abstract", FieldSchema.STRING
        ),
        Map.of(
            "doi", FieldSchema.STRING,
            "journal", FieldSchema.STRING,
            "citations", FieldSchema.STRING_LIST,
            "keywords", FieldSchema.STRING_LIST,
            "methodology", FieldSchema.STRING
        ),
        null
    );

    private LiteratureCorpusTypes() {}
}
```

- [ ] **Step 2: Write LiteratureScenarioTest**

```java
package io.casehub.neocortex.examples.corpus.domains.literature;

import io.casehub.neocortex.corpus.management.CorpusEntry;
import io.casehub.neocortex.corpus.management.CorpusLifecycle;
import io.casehub.neocortex.corpus.management.CorpusQuery;
import io.casehub.neocortex.examples.corpus.CorpusTestHarness;
import io.casehub.neocortex.rag.CorpusRef;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class LiteratureScenarioTest {

    private static final String TENANT = "literature-tenant";
    private CorpusTestHarness harness;

    @BeforeEach
    void setUp() {
        harness = CorpusTestHarness.create();
    }

    @Test
    void fullLifecycle() {
        var desc = harness.catalogue().register(
            "ai-papers", LiteratureCorpusTypes.LITERATURE, TENANT,
            "vec-unused", List.of(), List.of(), Map.of());
        var corpus = desc.corpusRef();
        assertThat(desc.type().name()).isEqualTo("academic-literature");

        harness.addEntry(corpus, new CorpusEntry("lit-001",
            Map.of("title", "Case-Based Reasoning: Foundational Issues",
                   "authors", List.of("Aamodt", "Plaza"),
                   "year", 1994,
                   "abstract", "A survey of case-based reasoning approaches and architectures.",
                   "keywords", List.of("CBR", "knowledge representation", "AI")),
            "Case-based reasoning is a problem-solving paradigm that solves new problems by adapting solutions from similar past cases.", null));

        harness.addEntry(corpus, new CorpusEntry("lit-002",
            Map.of("title", "Retrieval-Augmented Generation for Knowledge-Intensive Tasks",
                   "authors", List.of("Lewis", "Perez", "Piktus", "Petroni", "Karpukhin"),
                   "year", 2020,
                   "abstract", "RAG combines retrieval with generation for knowledge-intensive NLP.",
                   "doi", "10.48550/arXiv.2005.11401",
                   "citations", List.of("lit-001")),
            "We explore retrieval-augmented generation models that combine parametric and non-parametric memories.", null));

        harness.addEntry(corpus, new CorpusEntry("lit-003",
            Map.of("title", "Knowledge Graphs: Foundations and Applications",
                   "authors", List.of("Hogan", "Blomqvist", "Gutierrez"),
                   "year", 2021,
                   "abstract", "A comprehensive survey of knowledge graph construction and querying.",
                   "journal", "ACM Computing Surveys",
                   "methodology", "systematic literature review"),
            "Knowledge graphs have become a cornerstone for organizing structured knowledge.", null));

        harness.addEntry(corpus, new CorpusEntry("lit-004",
            Map.of("title", "SOAR: A General Cognitive Architecture",
                   "authors", List.of("Laird", "Newell", "Rosenbloom"),
                   "year", 1987,
                   "abstract", "SOAR integrates problem solving, learning, and memory.",
                   "keywords", List.of("cognitive architecture", "production systems")),
            "SOAR is a general cognitive architecture for developing intelligent systems.", null));

        harness.addEntry(corpus, new CorpusEntry("lit-005",
            Map.of("title", "Dense Passage Retrieval for Open-Domain QA",
                   "authors", List.of("Karpukhin", "Oguz", "Min"),
                   "year", 2020,
                   "abstract", "DPR uses dense representations for efficient passage retrieval.",
                   "citations", List.of("lit-001", "lit-002")),
            "Dense passage retrieval significantly outperforms traditional sparse retrieval for open-domain QA.", null));

        // Search
        var results = harness.search().search(corpus, CorpusQuery.of("retrieval"));
        assertThat(results).isNotEmpty();
        assertThat(results).extracting(r -> r.entry().id())
            .contains("lit-002", "lit-005");

        // Metadata round-trip
        var retrieved = harness.entryStore().get(corpus, "lit-002");
        assertThat(retrieved).isPresent();
        assertThat(retrieved.get().intField("year")).isEqualTo(2020);
        assertThat(retrieved.get().stringListField("authors")).contains("Lewis", "Petroni");
        assertThat(retrieved.get().stringListField("citations")).containsExactly("lit-001");

        // Catalogue
        assertThat(harness.catalogue().forType(LiteratureCorpusTypes.LITERATURE, TENANT)).hasSize(1);

        // Archive + revive
        harness.catalogue().updateLifecycle(corpus, CorpusLifecycle.ARCHIVED);
        assertThat(harness.catalogue().list(TENANT, CorpusLifecycle.ACTIVE)).isEmpty();
        harness.catalogue().updateLifecycle(corpus, CorpusLifecycle.ACTIVE);
        assertThat(harness.catalogue().list(TENANT, CorpusLifecycle.ACTIVE)).hasSize(1);
    }
}
```

- [ ] **Step 3: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-corpus-management -Pexamples-smoke -am`
Expected: PASS — 3 tests total

- [ ] **Step 4: Commit**

```bash
git add examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/domains/literature/
git commit -m "feat(#786): add literature domain scenario

Defines LiteratureCorpusTypes (STRING_LIST for authors/citations, INTEGER
for year) and LiteratureScenarioTest with 5 academic paper entries.

Refs #786"
```

---

## Batch 3: Domain scenario tests — clinical and game NPC

### Task 4: Clinical domain scenario

**Files:**
- Create: `examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/domains/clinical/ClinicalCorpusTypes.java`
- Create: `examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/domains/clinical/ClinicalScenarioTest.java`

**Interfaces:**
- Consumes: `CorpusTestHarness.create()`, `CorpusTestHarness.addEntry()`
- Produces: `ClinicalCorpusTypes.CLINICAL_GUIDELINE` — custom `CorpusType` with INSTANT for dates, STRING_LIST for contraindications

- [ ] **Step 1: Write ClinicalCorpusTypes**

```java
package io.casehub.neocortex.examples.corpus.domains.clinical;

import io.casehub.neocortex.corpus.management.CorpusType;
import io.casehub.neocortex.corpus.management.FieldSchema;

import java.util.Map;

public final class ClinicalCorpusTypes {

    public static final CorpusType CLINICAL_GUIDELINE = new CorpusType(
        "clinical-guideline",
        Map.of(
            "id", FieldSchema.STRING,
            "title", FieldSchema.STRING,
            "version", FieldSchema.STRING,
            "effective_date", FieldSchema.INSTANT,
            "condition", FieldSchema.STRING
        ),
        Map.of(
            "supersedes", FieldSchema.STRING,
            "evidence_grade", FieldSchema.STRING,
            "contraindications", FieldSchema.STRING_LIST,
            "review_date", FieldSchema.INSTANT
        ),
        null
    );

    private ClinicalCorpusTypes() {}
}
```

- [ ] **Step 2: Write ClinicalScenarioTest**

```java
package io.casehub.neocortex.examples.corpus.domains.clinical;

import io.casehub.neocortex.corpus.management.CorpusEntry;
import io.casehub.neocortex.corpus.management.CorpusLifecycle;
import io.casehub.neocortex.corpus.management.CorpusQuery;
import io.casehub.neocortex.examples.corpus.CorpusTestHarness;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class ClinicalScenarioTest {

    private static final String TENANT = "clinical-tenant";
    private CorpusTestHarness harness;

    @BeforeEach
    void setUp() {
        harness = CorpusTestHarness.create();
    }

    @Test
    void fullLifecycle() {
        var desc = harness.catalogue().register(
            "treatment-guidelines", ClinicalCorpusTypes.CLINICAL_GUIDELINE, TENANT,
            "vec-unused", List.of(), List.of(), Map.of());
        var corpus = desc.corpusRef();
        assertThat(desc.type().name()).isEqualTo("clinical-guideline");

        harness.addEntry(corpus, new CorpusEntry("cg-001",
            Map.of("title", "Hypertension Management — Initial Therapy",
                   "version", "3.0",
                   "effective_date", Instant.parse("2025-01-15T00:00:00Z"),
                   "condition", "hypertension",
                   "evidence_grade", "A",
                   "supersedes", "cg-001-v2",
                   "contraindications", List.of("renal artery stenosis", "pregnancy")),
            "First-line therapy for uncomplicated hypertension is a thiazide diuretic or ACE inhibitor.", null));

        harness.addEntry(corpus, new CorpusEntry("cg-002",
            Map.of("title", "Type 2 Diabetes — Metformin Protocol",
                   "version", "2.1",
                   "effective_date", Instant.parse("2024-06-01T00:00:00Z"),
                   "condition", "type-2-diabetes",
                   "evidence_grade", "A",
                   "review_date", Instant.parse("2026-06-01T00:00:00Z")),
            "Metformin is first-line pharmacotherapy for type 2 diabetes with lifestyle modification.", null));

        harness.addEntry(corpus, new CorpusEntry("cg-003",
            Map.of("title", "Acute Migraine — Triptan Administration",
                   "version", "1.0",
                   "effective_date", Instant.parse("2023-09-01T00:00:00Z"),
                   "condition", "migraine",
                   "evidence_grade", "B",
                   "contraindications", List.of("coronary artery disease", "uncontrolled hypertension")),
            "Triptans should be administered within 2 hours of migraine onset for optimal efficacy.", null));

        harness.addEntry(corpus, new CorpusEntry("cg-004",
            Map.of("title", "Asthma — Step Therapy Protocol",
                   "version", "4.2",
                   "effective_date", Instant.parse("2025-03-01T00:00:00Z"),
                   "condition", "asthma",
                   "evidence_grade", "A"),
            "Step therapy for persistent asthma begins with low-dose inhaled corticosteroids.", null));

        harness.addEntry(corpus, new CorpusEntry("cg-005",
            Map.of("title", "Anticoagulation — DVT Prophylaxis",
                   "version", "2.0",
                   "effective_date", Instant.parse("2024-11-01T00:00:00Z"),
                   "condition", "dvt",
                   "evidence_grade", "B",
                   "contraindications", List.of("active bleeding", "thrombocytopenia")),
            "Prophylactic anticoagulation is recommended for post-surgical patients with moderate or high VTE risk.", null));

        // Search
        var results = harness.search().search(corpus, CorpusQuery.of("therapy"));
        assertThat(results).isNotEmpty();

        // Metadata with INSTANT fields
        var retrieved = harness.entryStore().get(corpus, "cg-001");
        assertThat(retrieved).isPresent();
        assertThat(retrieved.get().stringField("version")).isEqualTo("3.0");
        assertThat(retrieved.get().stringListField("contraindications"))
            .containsExactly("renal artery stenosis", "pregnancy");

        // Catalogue + lifecycle
        assertThat(harness.catalogue().forType(ClinicalCorpusTypes.CLINICAL_GUIDELINE, TENANT)).hasSize(1);
        harness.catalogue().updateLifecycle(corpus, CorpusLifecycle.ARCHIVED);
        assertThat(harness.catalogue().list(TENANT, CorpusLifecycle.ACTIVE)).isEmpty();
        harness.catalogue().updateLifecycle(corpus, CorpusLifecycle.ACTIVE);
        assertThat(harness.catalogue().list(TENANT, CorpusLifecycle.ACTIVE)).hasSize(1);
    }
}
```

- [ ] **Step 3: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-corpus-management -Pexamples-smoke -am`
Expected: PASS — 4 tests total

- [ ] **Step 4: Commit**

```bash
git add examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/domains/clinical/
git commit -m "feat(#786): add clinical guideline domain scenario

Defines ClinicalCorpusTypes (INSTANT for dates, STRING_LIST for
contraindications) with 5 versioned treatment protocols.

Refs #786"
```

### Task 5: Game NPC domain scenario

**Files:**
- Create: `examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/domains/npc/NpcCorpusTypes.java`
- Create: `examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/domains/npc/NpcScenarioTest.java`

**Interfaces:**
- Consumes: `CorpusTestHarness.create()`, `CorpusTestHarness.addEntry()`
- Produces: `NpcCorpusTypes.NPC_WORLD` — custom `CorpusType` with heavy STRING_LIST usage (relationships, inventory, dialogue_tags, quest_refs)

- [ ] **Step 1: Write NpcCorpusTypes**

```java
package io.casehub.neocortex.examples.corpus.domains.npc;

import io.casehub.neocortex.corpus.management.CorpusType;
import io.casehub.neocortex.corpus.management.FieldSchema;

import java.util.Map;

public final class NpcCorpusTypes {

    public static final CorpusType NPC_WORLD = new CorpusType(
        "game-npc-world",
        Map.of(
            "id", FieldSchema.STRING,
            "name", FieldSchema.STRING,
            "entity_type", FieldSchema.STRING,
            "location", FieldSchema.STRING
        ),
        Map.of(
            "relationships", FieldSchema.STRING_LIST,
            "faction", FieldSchema.STRING,
            "inventory", FieldSchema.STRING_LIST,
            "dialogue_tags", FieldSchema.STRING_LIST,
            "quest_refs", FieldSchema.STRING_LIST
        ),
        null
    );

    private NpcCorpusTypes() {}
}
```

- [ ] **Step 2: Write NpcScenarioTest**

```java
package io.casehub.neocortex.examples.corpus.domains.npc;

import io.casehub.neocortex.corpus.management.CorpusEntry;
import io.casehub.neocortex.corpus.management.CorpusLifecycle;
import io.casehub.neocortex.corpus.management.CorpusQuery;
import io.casehub.neocortex.examples.corpus.CorpusTestHarness;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class NpcScenarioTest {

    private static final String TENANT = "npc-tenant";
    private CorpusTestHarness harness;

    @BeforeEach
    void setUp() {
        harness = CorpusTestHarness.create();
    }

    @Test
    void fullLifecycle() {
        var desc = harness.catalogue().register(
            "darkwood-world", NpcCorpusTypes.NPC_WORLD, TENANT,
            "vec-unused", List.of(), List.of(), Map.of());
        var corpus = desc.corpusRef();
        assertThat(desc.type().name()).isEqualTo("game-npc-world");

        harness.addEntry(corpus, new CorpusEntry("npc-001",
            Map.of("name", "Elara the Sage", "entity_type", "npc", "location", "Tower of Whispers",
                   "faction", "Seekers Guild",
                   "relationships", List.of("mentor:npc-003", "rival:npc-002"),
                   "dialogue_tags", List.of("quest-giver", "lore-keeper"),
                   "quest_refs", List.of("quest-010", "quest-015")),
            "Elara is the head lorekeeper of the Seekers Guild, researching ancient portal magic.", null));

        harness.addEntry(corpus, new CorpusEntry("npc-002",
            Map.of("name", "Kael Ironheart", "entity_type", "npc", "location", "Forge District",
                   "faction", "Blacksmiths Union",
                   "relationships", List.of("rival:npc-001", "friend:npc-004"),
                   "inventory", List.of("enchanted-hammer", "dragon-scale-ingot"),
                   "dialogue_tags", List.of("merchant", "craftsman")),
            "Kael is the finest blacksmith in the realm, forging weapons from rare materials.", null));

        harness.addEntry(corpus, new CorpusEntry("npc-003",
            Map.of("name", "Old Merrick", "entity_type", "npc", "location", "Hermit's Cave",
                   "relationships", List.of("student:npc-001"),
                   "dialogue_tags", List.of("retired-adventurer")),
            "Old Merrick was once a renowned adventurer who now lives in seclusion.", null));

        harness.addEntry(corpus, new CorpusEntry("loc-001",
            Map.of("name", "Tower of Whispers", "entity_type", "location", "location", "Northern Mountains",
                   "faction", "Seekers Guild"),
            "A tall spire atop the northern cliffs, the Tower of Whispers houses the Seekers Guild library.", null));

        harness.addEntry(corpus, new CorpusEntry("item-001",
            Map.of("name", "Dragon Scale Ingot", "entity_type", "item", "location", "Forge District",
                   "quest_refs", List.of("quest-010")),
            "A rare crafting material extracted from dragon scales, used to forge legendary weapons.", null));

        // Search
        var results = harness.search().search(corpus, CorpusQuery.of("blacksmith"));
        assertThat(results).isNotEmpty();
        assertThat(results.getFirst().entry().id()).isEqualTo("npc-002");

        // Mixed entity types
        var locationResults = harness.search().search(corpus, CorpusQuery.of("tower"));
        assertThat(locationResults).extracting(r -> r.entry().stringField("entity_type"))
            .contains("location");

        // Metadata round-trip for relationships
        var retrieved = harness.entryStore().get(corpus, "npc-001");
        assertThat(retrieved).isPresent();
        assertThat(retrieved.get().stringListField("relationships"))
            .containsExactly("mentor:npc-003", "rival:npc-002");
        assertThat(retrieved.get().stringListField("quest_refs"))
            .containsExactly("quest-010", "quest-015");

        // Catalogue + lifecycle
        harness.catalogue().updateLifecycle(corpus, CorpusLifecycle.ARCHIVED);
        assertThat(harness.catalogue().list(TENANT, CorpusLifecycle.ACTIVE)).isEmpty();
        harness.catalogue().updateLifecycle(corpus, CorpusLifecycle.ACTIVE);
        assertThat(harness.catalogue().list(TENANT, CorpusLifecycle.ACTIVE)).hasSize(1);
    }
}
```

- [ ] **Step 3: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-corpus-management -Pexamples-smoke -am`
Expected: PASS — 5 tests total

- [ ] **Step 4: Commit**

```bash
git add examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/domains/npc/
git commit -m "feat(#786): add game NPC world domain scenario

Defines NpcCorpusTypes (heavy STRING_LIST: relationships, inventory,
dialogue_tags, quest_refs) with mixed entity types (NPC, location, item).

Refs #786"
```

---

## Batch 4: Federation scenario

### Task 6: Cross-domain federated search scenario

**Files:**
- Create: `examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/federation/FederatedSearchScenarioTest.java`

**Interfaces:**
- Consumes: `CorpusTestHarness.create()`, `CorpusTestHarness.addEntry()`, `CorpusTestHarness.catalogue()`, `CorpusTestHarness.federatedSearch()`, `LiteratureCorpusTypes.LITERATURE`, `ClinicalCorpusTypes.CLINICAL_GUIDELINE`
- Produces: nothing — terminal test

- [ ] **Step 1: Write FederatedSearchScenarioTest**

```java
package io.casehub.neocortex.examples.corpus.federation;

import io.casehub.neocortex.corpus.management.CorpusEntry;
import io.casehub.neocortex.corpus.management.CorpusLifecycle;
import io.casehub.neocortex.corpus.management.CorpusQuery;
import io.casehub.neocortex.corpus.management.FederationRef;
import io.casehub.neocortex.examples.corpus.CorpusTestHarness;
import io.casehub.neocortex.examples.corpus.domains.clinical.ClinicalCorpusTypes;
import io.casehub.neocortex.examples.corpus.domains.literature.LiteratureCorpusTypes;
import io.casehub.neocortex.rag.CorpusRef;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class FederatedSearchScenarioTest {

    private static final String TENANT = "federation-tenant";
    private CorpusTestHarness harness;
    private CorpusRef literatureCorpus;
    private CorpusRef clinicalCorpus;

    @BeforeEach
    void setUp() {
        harness = CorpusTestHarness.create();

        // Create literature corpus
        var litDesc = harness.catalogue().register(
            "evidence-base", LiteratureCorpusTypes.LITERATURE, TENANT,
            "vec-evidence-base", List.of(), List.of(), Map.of());
        literatureCorpus = litDesc.corpusRef();

        // Create clinical corpus with upstream federation to literature
        var clinDesc = harness.catalogue().register(
            "treatment-protocols", ClinicalCorpusTypes.CLINICAL_GUIDELINE, TENANT,
            "vec-treatment-protocols",
            List.of(new FederationRef(literatureCorpus, null, null, "default")),
            List.of(),
            Map.of());
        clinicalCorpus = clinDesc.corpusRef();

        // Populate literature
        harness.addEntry(literatureCorpus, new CorpusEntry("lit-f1",
            Map.of("title", "ACE Inhibitors in Hypertension: A Meta-Analysis",
                   "authors", List.of("Chen", "Liu"),
                   "year", 2022,
                   "abstract", "Meta-analysis of ACE inhibitor efficacy in hypertension treatment."),
            "ACE inhibitors reduce cardiovascular mortality in hypertensive patients by 15-20%.", null));
        harness.addEntry(literatureCorpus, new CorpusEntry("lit-f2",
            Map.of("title", "Metformin Outcomes in T2D: Long-Term Follow-Up",
                   "authors", List.of("Wilson", "Patel"),
                   "year", 2023,
                   "abstract", "Ten-year follow-up of metformin therapy outcomes."),
            "Long-term metformin therapy shows sustained HbA1c reduction with minimal adverse effects.", null));

        // Populate clinical
        harness.addEntry(clinicalCorpus, new CorpusEntry("cg-f1",
            Map.of("title", "Hypertension — ACE Inhibitor Protocol",
                   "version", "2.0",
                   "effective_date", Instant.parse("2025-01-01T00:00:00Z"),
                   "condition", "hypertension",
                   "evidence_grade", "A"),
            "ACE inhibitors are recommended as first-line for hypertension in patients under 55.", null));
        harness.addEntry(clinicalCorpus, new CorpusEntry("cg-f2",
            Map.of("title", "Diabetes — Insulin Titration",
                   "version", "1.0",
                   "effective_date", Instant.parse("2024-06-01T00:00:00Z"),
                   "condition", "diabetes",
                   "evidence_grade", "B"),
            "Insulin titration protocol for patients not achieving target HbA1c with metformin alone.", null));
    }

    @Test
    void singleCorpusSearch() {
        var results = harness.search().search(literatureCorpus, CorpusQuery.of("ACE inhibitor"));
        assertThat(results).isNotEmpty();
        assertThat(results).allSatisfy(r ->
            assertThat(r.sourceCorpus()).isEqualTo(literatureCorpus));
    }

    @Test
    void federatedSearchAcrossDomains() {
        var results = harness.federatedSearch().search(
            CorpusQuery.of("hypertension", 10), TENANT);
        assertThat(results.results()).isNotEmpty();

        var sourceCorpora = results.results().stream()
            .map(r -> r.sourceCorpus())
            .distinct()
            .toList();
        assertThat(sourceCorpora).containsExactlyInAnyOrder(literatureCorpus, clinicalCorpus);
    }

    @Test
    void federatedSearchWithDepthLimit() {
        var results = harness.federatedSearch().search(
            CorpusQuery.of("metformin", 10).withFederationDepth(0), TENANT);
        // depth=0 means no upstream traversal — only starting corpora
        assertThat(results.results()).isNotEmpty();
    }

    @Test
    void archivedCorpusExcludedFromFederation() {
        harness.catalogue().updateLifecycle(literatureCorpus, CorpusLifecycle.ARCHIVED);

        var results = harness.federatedSearch().search(
            CorpusQuery.of("ACE inhibitor", 10), TENANT);
        // Archived corpus should be excluded from catalogue.list(ACTIVE)
        var sourceCorpora = results.results().stream()
            .map(r -> r.sourceCorpus())
            .distinct()
            .toList();
        assertThat(sourceCorpora).doesNotContain(literatureCorpus);
    }

    @Test
    void scopedFederatedSearch() {
        // Search only from clinical corpus — should walk upstream to literature
        var results = harness.federatedSearch().search(
            CorpusQuery.of("ACE inhibitor", 10)
                .withCorpora(Set.of(clinicalCorpus)),
            TENANT);
        assertThat(results.results()).isNotEmpty();

        var sourceCorpora = results.results().stream()
            .map(r -> r.sourceCorpus())
            .distinct()
            .toList();
        assertThat(sourceCorpora).contains(clinicalCorpus);
    }

    @Test
    void searchReportTracksSearchedCorpora() {
        var results = harness.federatedSearch().search(
            CorpusQuery.of("hypertension", 10), TENANT);
        assertThat(results.report().searched()).isNotEmpty();
        assertThat(results.report().partial()).isFalse();
    }
}
```

- [ ] **Step 2: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-corpus-management -Pexamples-smoke -am`
Expected: PASS — 11 tests total (2 garden + 1 literature + 1 clinical + 1 NPC + 6 federation)

- [ ] **Step 3: Commit**

```bash
git add examples/example-corpus-management/src/test/java/io/casehub/neocortex/examples/corpus/federation/
git commit -m "feat(#786): add cross-domain federated search scenario

Federates literature + clinical corpora with upstream relationship.
Tests single-corpus, federated, depth-limited, archived-exclusion,
scoped, and search-report scenarios.

Closes #786"
```

---

## References

- `specs/issue-786-e2e-examples-corpus-management/2026-11-04-e2e-corpus-management-examples-design.md` — design spec
- `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusType.java:1-43` — CorpusType record + constants
- `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusManager.java:1-20` — CorpusManager SPI (no production impl)
- `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusEntryStore.java:1-16` — CorpusEntryStore SPI
- `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusSearch.java:1-10` — CorpusSearch SPI (no production impl)
- `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/FederatedCorpusSearch.java:1-6` — FederatedCorpusSearch SPI
- `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/SqliteCorpusCatalogue.java:1-265` — production catalogue + lifecycle ops
- `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/SqliteCorpusEntryStore.java` — production entry store
- `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/ChainWalkerFederatedSearch.java:1-154` — federation walker
- `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/SqliteCorpusEntryStoreTest.java:1-143` — existing test wiring pattern
- `examples/example-text-analysis/pom.xml:1-209` — existing example module POM pattern
- GitHub #786, #789 (parent epic)

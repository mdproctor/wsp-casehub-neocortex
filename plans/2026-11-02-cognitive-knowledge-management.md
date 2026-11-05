# Cognitive Knowledge Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #763 — Autonomous cognitive knowledge management
**Issue group:** #763, #764

**Goal:** Build a corpus management abstraction that generalises Hortora's garden engine into a universal, agent-driven knowledge lifecycle — typed corpora with federated hierarchical search, cover documents, and cognitive modulation.

**Architecture:** Two new modules (`corpus-management-api`, `corpus-management`) that compose existing rag-api/rag SPIs into a higher-level corpus abstraction. ~60% of the implementation is migrating Hortora engine code via IntelliJ refactoring; ~35% is genuinely new code (catalogue, transcript covers, cognitive integration).

**Tech Stack:** Java 21, Quarkus 3.32.2, Qdrant (via rag module), SQLite + HikariCP (via sqlite-support), SnakeYAML (for cover document parsing)

## Global Constraints

- All source file operations (move, rename, delete) use IntelliJ MCP (`ide_move_file`, `ide_refactor_rename`, `ide_refactor_safe_delete`). No bash cp/mv/rm for `.java` files.
- Hortora migration uses a shared IntelliJ workspace (`ide_open_workspace`) with both neocortex and Hortora engine open simultaneously.
- `CorpusRef` (from rag-api) is the typed corpus identity — no raw String `corpusId` + `tenantId` pairs.
- `corpus-management-api` is Tier 1 pure Java — zero CDI, zero Quarkus deps. Only depends on `rag-api`, `corpus-api`, `cognitive-api`.
- Cover documents use Hortora garden entry format: markdown body + YAML frontmatter.
- `corpusName` is unique per `tenantId` (UNIQUE constraint in SQLite catalogue).
- Each cover document is embedded as a single chunk (1:1 Qdrant point:cover mapping).

---

## Batch 1: Module Scaffolding + SPI Types

### Task 1: Create corpus-management-api module with all SPIs and value types

**Files:**
- Create: `corpus-management-api/pom.xml`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusManager.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusCatalogue.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusEntryStore.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusSearch.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/FederatedCorpusSearch.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusType.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/FieldSchema.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusDescriptor.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusEntry.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusQuery.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusSearchResult.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/FederatedSearchResult.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/SearchReport.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/SkippedCorpus.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/FederationRef.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusLifecycle.java`
- Modify: `pom.xml` (parent — add module)

**Interfaces:**
- Consumes: `CorpusRef` from rag-api, `PayloadFilter` from rag-api, `Confidence` from cognitive-api
- Produces: All SPI interfaces and value types consumed by every subsequent task

- [ ] **Step 1: Create module directory and pom.xml**

```bash
mkdir -p corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management
mkdir -p corpus-management-api/src/test/java/io/casehub/neocortex/corpus/management
```

Write `corpus-management-api/pom.xml`:
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
  </parent>
  <artifactId>casehub-neocortex-corpus-management-api</artifactId>
  <name>CaseHub Neocortex - Corpus Management API</name>
  <description>Corpus management SPIs — typed knowledge collections with federated hierarchical search. Pure Java, zero CDI.</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-rag-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-corpus-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-cognitive-api</artifactId>
    </dependency>
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

Add `<module>corpus-management-api</module>` to parent pom.xml modules section.

- [ ] **Step 2: Write all SPI interfaces**

Write each SPI interface exactly as defined in the spec §3.1–§3.4. Use `ide_create_file` for each file.

`CorpusManager.java` — §3.1:
```java
package io.casehub.neocortex.corpus.management;

import io.casehub.neocortex.rag.CorpusRef;
import java.util.List;
import java.util.Map;

public interface CorpusManager {
    CorpusDescriptor create(String name, CorpusType type, String tenantId,
                            List<FederationRef> upstream,
                            List<FederationRef> peers,
                            Map<String, String> metadata);
    void archive(CorpusRef corpus);
    void revive(CorpusRef corpus);
    void delete(CorpusRef corpus);
}
```

`CorpusCatalogue.java` — §3.2:
```java
package io.casehub.neocortex.corpus.management;

import io.casehub.neocortex.rag.CorpusRef;
import java.util.List;
import java.util.Optional;

public interface CorpusCatalogue {
    List<CorpusDescriptor> list(String tenantId, CorpusLifecycle status);
    Optional<CorpusDescriptor> get(CorpusRef corpus);
    List<CorpusDescriptor> forType(CorpusType type, String tenantId);
    List<CorpusDescriptor> searchScope(CorpusRef corpus);
    HealthReport reconcile(String tenantId);
}
```

`CorpusEntryStore.java` — §3.3:
```java
package io.casehub.neocortex.corpus.management;

import io.casehub.neocortex.rag.CorpusRef;
import java.util.Optional;

public interface CorpusEntryStore {
    String add(CorpusRef corpus, CorpusEntry entry);
    void update(CorpusRef corpus, String entryId, CorpusEntry entry);
    void remove(CorpusRef corpus, String entryId);
    Optional<CorpusEntry> get(CorpusRef corpus, String entryId);
}
```

`CorpusSearch.java` — §3.4:
```java
package io.casehub.neocortex.corpus.management;

import io.casehub.neocortex.rag.CorpusRef;
import java.util.List;

public interface CorpusSearch {
    List<CorpusSearchResult> search(CorpusRef corpus, CorpusQuery query);
}
```

`FederatedCorpusSearch.java` — §3.4:
```java
package io.casehub.neocortex.corpus.management;

public interface FederatedCorpusSearch {
    FederatedSearchResult search(CorpusQuery query, String tenantId);
}
```

- [ ] **Step 3: Write all value types**

Write each record type from §3.5–§3.6:
- `CorpusType.java` with `KNOWLEDGE_GARDEN`, `RESEARCH`, `TRANSCRIPT` constants
- `FieldSchema.java` enum
- `CorpusDescriptor.java` record
- `CorpusEntry.java` record with accessor helpers
- `CorpusQuery.java` record
- `CorpusSearchResult.java` record
- `FederatedSearchResult.java` record
- `SearchReport.java` record
- `SkippedCorpus.java` record
- `FederationRef.java` record
- `CorpusLifecycle.java` enum
- `HealthReport.java` record (catalogue/Qdrant mismatch report)

- [ ] **Step 4: Compile the module**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean compile -pl corpus-management-api`
Expected: BUILD SUCCESS

- [ ] **Step 5: Commit**

```bash
git add corpus-management-api/ pom.xml
git commit -m "feat(#763): add corpus-management-api module with SPIs and value types

Refs #763"
```

---

## Batch 2: Catalogue + Entry Store + Cover Parsing

### Task 2: Create corpus-management module with SqliteCorpusCatalogue

**Files:**
- Create: `corpus-management/pom.xml`
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/SqliteCorpusCatalogue.java`
- Create: `corpus-management/src/main/resources/db/corpus-catalogue/V1__create_catalogue.sql`
- Create: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/SqliteCorpusCatalogueTest.java`

**Interfaces:**
- Consumes: `CorpusCatalogue` SPI, `CorpusDescriptor`, `CorpusRef`, `SqliteDataSourceFactory` from sqlite-support
- Produces: `SqliteCorpusCatalogue` — catalogue persistence used by `CorpusManagerImpl` and `ChainWalkerFederatedSearch`

- [ ] **Step 1: Create module directory and pom.xml**

```bash
mkdir -p corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl
mkdir -p corpus-management/src/main/resources/db/corpus-catalogue
mkdir -p corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl
```

Write `corpus-management/pom.xml` with dependencies: `corpus-management-api`, `rag`, `rag-scoring`, `rag-tracking`, `sqlite-support`, `fusion-api`, `corpus` (for artifact storage), test deps.

Add `<module>corpus-management</module>` to parent pom.xml.

- [ ] **Step 2: Write Flyway migration for catalogue schema**

`V1__create_catalogue.sql`:
```sql
CREATE TABLE corpus_catalogue (
    id TEXT PRIMARY KEY,
    corpus_name TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    type_name TEXT NOT NULL,
    lifecycle TEXT NOT NULL DEFAULT 'ACTIVE',
    qdrant_collection TEXT NOT NULL,
    upstream_json TEXT NOT NULL DEFAULT '[]',
    peers_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    last_modified_at TEXT NOT NULL,
    UNIQUE(tenant_id, corpus_name)
);

CREATE INDEX idx_catalogue_tenant ON corpus_catalogue(tenant_id);
CREATE INDEX idx_catalogue_type ON corpus_catalogue(type_name);
CREATE INDEX idx_catalogue_lifecycle ON corpus_catalogue(lifecycle);
```

- [ ] **Step 3: Write the failing contract test**

`SqliteCorpusCatalogueTest.java`:
```java
@Test
void registerAndRetrieve() {
    var desc = catalogue.register(descriptor("test-corpus", "tenant-1", CorpusType.RESEARCH));
    assertThat(catalogue.get(new CorpusRef("tenant-1", "test-corpus")))
        .isPresent()
        .hasValueSatisfying(d -> {
            assertThat(d.name()).isEqualTo("test-corpus");
            assertThat(d.type()).isEqualTo(CorpusType.RESEARCH);
            assertThat(d.lifecycle()).isEqualTo(CorpusLifecycle.ACTIVE);
        });
}

@Test
void duplicateNameSameTenantThrows() {
    catalogue.register(descriptor("dup", "tenant-1", CorpusType.RESEARCH));
    assertThatThrownBy(() -> catalogue.register(descriptor("dup", "tenant-1", CorpusType.RESEARCH)))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void listByLifecycleFiltersCorrectly() {
    catalogue.register(descriptor("active", "tenant-1", CorpusType.RESEARCH));
    catalogue.register(descriptor("archived", "tenant-1", CorpusType.TRANSCRIPT));
    catalogue.updateLifecycle(new CorpusRef("tenant-1", "archived"), CorpusLifecycle.ARCHIVED);

    assertThat(catalogue.list("tenant-1", CorpusLifecycle.ACTIVE)).hasSize(1);
    assertThat(catalogue.list("tenant-1", CorpusLifecycle.ARCHIVED)).hasSize(1);
}

@Test
void searchScopeWalksFederationGraph() {
    var parent = catalogue.register(descriptor("parent", "t", CorpusType.KNOWLEDGE_GARDEN));
    var child = catalogue.register(descriptorWithUpstream("child", "t",
        List.of(new FederationRef(parent.corpusRef(), null, null, "default"))));
    var peer = catalogue.register(descriptorWithPeers("peer", "t",
        List.of(new FederationRef(child.corpusRef(), null, null, null))));

    var scope = catalogue.searchScope(child.corpusRef());
    assertThat(scope).extracting(CorpusDescriptor::name)
        .containsExactlyInAnyOrder("child", "parent");
}
```

- [ ] **Step 4: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management -Dtest=SqliteCorpusCatalogueTest`
Expected: FAIL — class not implemented

- [ ] **Step 5: Implement SqliteCorpusCatalogue**

Use `ide_create_file` for the implementation. Key details:
- Inject `SqliteDataSourceFactory` for DataSource creation
- JSON serialization for upstream/peers/metadata (Jackson or manual)
- `searchScope()` walks upstream refs recursively with cycle detection via `Set<CorpusRef> visited`
- `reconcile()` deferred to Phase 3 (needs Qdrant, return stub `HealthReport` for now)

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management -Dtest=SqliteCorpusCatalogueTest`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add corpus-management/ pom.xml
git commit -m "feat(#763): add corpus-management module with SqliteCorpusCatalogue

SQLite-backed catalogue with tenant-scoped uniqueness, lifecycle
management, and federation graph traversal.

Refs #763"
```

### Task 3: CoverDocumentParser + CorpusManagerImpl

**Files:**
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CoverDocumentParser.java`
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusManagerImpl.java`
- Create: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/CoverDocumentParserTest.java`
- Create: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/CorpusManagerImplTest.java`

**Interfaces:**
- Consumes: `CorpusCatalogue` (from Task 2), `CorpusType`, `CorpusEntry`, `FieldSchema`
- Produces: `CoverDocumentParser` (markdown+YAML → `CorpusEntry`), `CorpusManagerImpl` (lifecycle orchestration)

- [ ] **Step 1: Write failing tests for CoverDocumentParser**

```java
@Test
void parsesValidCoverDocument() {
    String cover = """
        ---
        id: CE-20261102-abc123
        title: "Test entry"
        type: research-paper
        corpus: test-corpus
        domain: testing
        tags: [unit, integration]
        ---
        This is the body of the entry.
        
        ## Section
        More content here.
        """;
    var entry = parser.parse(cover, CorpusType.RESEARCH);
    assertThat(entry.id()).isEqualTo("CE-20261102-abc123");
    assertThat(entry.stringField("title")).isEqualTo("Test entry");
    assertThat(entry.stringListField("tags")).containsExactly("unit", "integration");
    assertThat(entry.body()).contains("This is the body");
}

@Test
void rejectsMissingRequiredField() {
    String cover = """
        ---
        id: CE-123
        title: "Missing domain"
        type: research-paper
        corpus: test-corpus
        ---
        Body text.
        """;
    assertThatThrownBy(() -> parser.parse(cover, CorpusType.RESEARCH))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("domain");
}

@Test
void extractsArtifactRef() {
    String cover = """
        ---
        id: CE-123
        title: "With artifact"
        type: transcript
        corpus: agent-interactions
        interaction_type: agent-human
        activity_type: design
        artifact_ref: corpus://agent-interactions/transcripts/2026-11-02.zip#entry-42
        ---
        Brief content.
        """;
    var entry = parser.parse(cover, CorpusType.TRANSCRIPT);
    assertThat(entry.artifactRef()).isEqualTo("corpus://agent-interactions/transcripts/2026-11-02.zip#entry-42");
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management -Dtest=CoverDocumentParserTest`
Expected: FAIL

- [ ] **Step 3: Implement CoverDocumentParser**

Split markdown into YAML frontmatter (between `---` delimiters) and body. Parse YAML via SnakeYAML. Validate required fields against `CorpusType.requiredFields()`. Extract `artifact_ref` into `CorpusEntry.artifactRef`. Return `CorpusEntry(id, frontmatter, body, artifactRef)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management -Dtest=CoverDocumentParserTest`
Expected: PASS

- [ ] **Step 5: Write failing tests for CorpusManagerImpl**

Test create/archive/revive lifecycle. Mock `CorpusCatalogue` and Qdrant collection creation. Verify:
- `create()` registers in catalogue then creates Qdrant collection
- `archive()` updates lifecycle to ARCHIVED
- `delete()` drops Qdrant collection then removes catalogue entry
- `create()` with duplicate name throws

- [ ] **Step 6: Implement CorpusManagerImpl**

Lifecycle orchestration: catalogue writes + Qdrant collection management. Use `@ApplicationScoped`. Inject `CorpusCatalogue` and Qdrant client (via rag module wiring).

- [ ] **Step 7: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add corpus-management/
git commit -m "feat(#763): add CoverDocumentParser and CorpusManagerImpl

YAML frontmatter parsing with CorpusType schema validation.
Lifecycle orchestration: create/archive/revive/delete with
transactional catalogue + Qdrant collection management.

Refs #763"
```

---

## Batch 3: Hortora Migration via IntelliJ Refactoring

### Task 4: Open IntelliJ workspace + migrate Hortora federation and provenance code

**CRITICAL: All source file operations use IntelliJ MCP. No bash for .java files.**

**Files:**
- Move (rewrite): `io.hortora.garden.federation.ChainWalker` → rewrite as `io.casehub.neocortex.corpus.management.impl.ChainWalkerFederatedSearch` (uses corpus-management-api types)
- Move+adapt: `io.hortora.garden.provenance.ProvenanceStore` → `io.casehub.neocortex.corpus.management.impl.ProvenanceStoreImpl`
- Move+adapt: `io.hortora.garden.search.SearchProfileStore` → `io.casehub.neocortex.corpus.management.impl.SearchProfileStore`
- Move+adapt: `io.hortora.garden.index.GardenReindexService` → `io.casehub.neocortex.corpus.management.impl.CorpusReindexService`
- Move+adapt: `io.hortora.garden.inference.CollectionMigration` → `io.casehub.neocortex.corpus.management.impl.CollectionMigrationService`
- Move: `io.hortora.garden.provenance.ProvenanceConfig` → `io.casehub.neocortex.corpus.management.impl.ProvenanceConfig`
- Create: tests for each migrated class

**Interfaces:**
- Consumes: `FederatedCorpusSearch` SPI, `CorpusCatalogue`, `CorpusSearch`, `CorpusRef`, `ScoreFusion` from fusion-api, `ProvenanceTracker` from rag-api, `CaseRetriever` from rag-api
- Produces: `ChainWalkerFederatedSearch`, `ProvenanceStoreImpl`, `SearchProfileStore`, `CorpusReindexService`, `CollectionMigrationService`

- [ ] **Step 1: Open IntelliJ workspace with both projects**

```
ide_open_workspace with modules:
  - /Users/mdproctor/claude/casehub/slots/221/neocortex
  - /Users/mdproctor/claude/hortora/engine
```

Wait for indexing to complete. Verify with `ide_index_status`.

- [ ] **Step 2: Read Hortora ChainWalker source**

Use `ide_read_file` to read `/Users/mdproctor/claude/hortora/engine/src/main/java/io/hortora/garden/federation/ChainWalker.java`. Understand the upstream sequential walk + peer parallel fan-out + sufficiency check + merge logic.

- [ ] **Step 3: Write failing test for ChainWalkerFederatedSearch**

```java
@Test
void searchesOwnCorpusFirst() { ... }

@Test
void walksUpstreamSequentially() { ... }

@Test
void fansOutToPeersInParallel() { ... }

@Test
void stopsWhenSufficientResults() { ... }

@Test
void detectsCyclesViaVisitedSet() { ... }

@Test
void reportsSkippedCorporaOnFailure() { ... }
```

- [ ] **Step 4: Run tests to verify they fail**

Expected: FAIL — class does not exist

- [ ] **Step 5: Implement ChainWalkerFederatedSearch**

This is a **rewrite**, not a move — Hortora's `ChainWalker` uses Hortora-specific types (`SearchResult`, `RemoteGardenClient`, `FederationConfig`). The new implementation uses corpus-management-api types (`CorpusSearchResult`, `FederatedSearchResult`, `CorpusCatalogue`, `CorpusSearch`).

Use `ide_create_file` to create the file. Reference the Hortora source for the algorithm (upstream sequential walk, peer parallel fan-out, sufficiency check) but use the new types.

Key differences from Hortora:
- `CorpusCatalogue.searchScope()` replaces `FederationConfig` parsing
- `CorpusSearch.search()` replaces `RemoteGardenClient.search()`
- `ScoreFusion.rrf()` replaces manual merge logic
- `FederatedSearchResult` with `SearchReport` replaces bare result list
- Cycle detection via `Set<CorpusRef> visited`

- [ ] **Step 6: Run tests to verify they pass**

Expected: PASS

- [ ] **Step 7: Move ProvenanceStore from Hortora**

Use `ide_read_file` to read Hortora's `ProvenanceStore.java`. It implements `ProvenanceTracker` (rag-api SPI) with SQLite persistence.

Use `ide_move_file` to move the file:
- From: `/Users/mdproctor/claude/hortora/engine/src/main/java/io/hortora/garden/provenance/ProvenanceStore.java`
- To: `/Users/mdproctor/claude/casehub/slots/221/neocortex/corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/ProvenanceStoreImpl.java`

IntelliJ updates all references in both projects. Then use `ide_refactor_rename` if the class name needs changing.

Adapt: replace any Hortora-specific column names (e.g., `issue_repo` → generic `action_context`) if needed.

Also move `ProvenanceConfig.java` the same way.

Write tests for the moved class.

- [ ] **Step 8: Move SearchProfileStore, CorpusReindexService, CollectionMigrationService**

For each:
1. `ide_read_file` to understand the Hortora source
2. `ide_move_file` from Hortora package to corpus-management package
3. Adapt any Hortora-specific types to corpus-management-api types
4. Write tests

`SearchProfileStore`: move from `io.hortora.garden.search.SearchProfileStore` → `io.casehub.neocortex.corpus.management.impl.SearchProfileStore`

`CorpusReindexService` → `CorpusReindexService`: move + rename via `ide_move_file` + `ide_refactor_rename`

`CollectionMigration` → `CollectionMigrationService`: move + rename

- [ ] **Step 9: Run all corpus-management tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management`
Expected: PASS

- [ ] **Step 10: Commit in neocortex**

```bash
git add corpus-management/
git commit -m "feat(#763): migrate Hortora federation, provenance, search profiles, reindex, collection migration

ChainWalkerFederatedSearch rewritten using corpus-management-api types.
ProvenanceStoreImpl, SearchProfileStore, CorpusReindexService, and
CollectionMigrationService moved from Hortora engine via IntelliJ
refactoring with reference updates.

Refs #763"
```

- [ ] **Step 11: Commit in Hortora (reference updates)**

```bash
git -C /Users/mdproctor/claude/hortora commit -am "refactor: move federation, provenance, search profiles to neocortex corpus-management

Code migrated to casehub-neocortex-corpus-management module.
Import references updated by IntelliJ.

Refs casehubio/neocortex#763"
```

### Task 5: Wire CorpusSearch to CaseRetriever + AdaptiveSearchWrapper

**Files:**
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/QdrantCorpusSearch.java`
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/QdrantCorpusEntryStore.java`
- Create: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/QdrantCorpusSearchTest.java`
- Create: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/QdrantCorpusEntryStoreTest.java`

**Interfaces:**
- Consumes: `CorpusSearch` SPI, `CorpusEntryStore` SPI, `CaseRetriever` (rag-api), `EmbeddingIngestor` (rag-api), `AdaptiveSearchWrapper` (rag-scoring), `CoverDocumentParser` (Task 3)
- Produces: `QdrantCorpusSearch`, `QdrantCorpusEntryStore` — Qdrant-backed implementations

- [ ] **Step 1: Write failing tests for QdrantCorpusEntryStore**

Test add/update/remove/get lifecycle. Use InMemory stubs or Testcontainers Qdrant.

- [ ] **Step 2: Implement QdrantCorpusEntryStore**

Delegates to `EmbeddingIngestor.ingest()` for embedding. Cover document → single `ChunkInput`. Frontmatter stored as Qdrant payload metadata. `artifactRef` stored via `CorpusStore` (corpus-api).

- [ ] **Step 3: Write failing tests for QdrantCorpusSearch**

Test text search, filter application, result reconstruction from chunk metadata.

- [ ] **Step 4: Implement QdrantCorpusSearch**

Delegates to `CaseRetriever.retrieve()`. Reconstructs `CorpusEntry` from `RetrievedChunk` metadata. Wraps as `CorpusSearchResult` with source corpus and tier.

- [ ] **Step 5: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add corpus-management/
git commit -m "feat(#763): add QdrantCorpusEntryStore and QdrantCorpusSearch

Single-chunk embedding via EmbeddingIngestor, hybrid search via
CaseRetriever, cover document reconstruction from chunk metadata.

Refs #763"
```

---

## Batch 4: Transcript Corpus (#764)

### Task 6: CoverDocumentGenerator for transcripts + TranscriptCorpusInitializer

**Files:**
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CoverDocumentGenerator.java`
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/TranscriptCorpusInitializer.java`
- Create: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/CoverDocumentGeneratorTest.java`

**Interfaces:**
- Consumes: `CorpusManager` (Task 3), `CorpusEntryStore` (Task 5), `CorpusType.TRANSCRIPT`
- Produces: `CoverDocumentGenerator` (interaction context → cover document string), `TranscriptCorpusInitializer` (auto-creates transcript corpus per agent)

- [ ] **Step 1: Write failing tests for CoverDocumentGenerator**

```java
@Test
void generatesTranscriptCoverFromInteractionContext() {
    var context = new InteractionContext(
        "agent-01", "tenant-1",
        InteractionType.AGENT_HUMAN,
        ActivityType.DESIGN_DISCUSSION,
        "neocortex",
        List.of("agent-01", "mark"),
        47,
        "Brainstorming session on corpus management architecture...",
        "corpus://agent-01-interactions/transcripts/2026-11-02.zip#entry-42"
    );
    String cover = generator.generateTranscriptCover(context);
    assertThat(cover).contains("interaction_type: agent-human");
    assertThat(cover).contains("activity_type: design-discussion");
    assertThat(cover).contains("artifact_ref:");
    assertThat(cover).contains("turn_count: 47");

    var entry = parser.parse(cover, CorpusType.TRANSCRIPT);
    assertThat(entry.stringField("interaction_type")).isEqualTo("agent-human");
    assertThat(entry.artifactRef()).isNotNull();
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL

- [ ] **Step 3: Implement CoverDocumentGenerator**

Mechanical generation — no LLM. Takes an `InteractionContext` record, produces a markdown+YAML string. Generates a unique ID (`CE-YYYYMMDD-XXXXXX`), fills frontmatter from context fields, writes a brief summary as body text.

- [ ] **Step 4: Run tests to verify they pass**

Expected: PASS

- [ ] **Step 5: Implement TranscriptCorpusInitializer**

CDI observer on `AgentCreated` (with `reception = Reception.IF_EXISTS` for soft dependency). Lazy fallback: if no `AgentCreated` event fires, create corpus on first transcript entry add.

- [ ] **Step 6: Commit**

```bash
git add corpus-management/
git commit -m "feat(#764): add CoverDocumentGenerator for transcripts and TranscriptCorpusInitializer

Mechanical brief generation from interaction context. Auto-creation
of per-agent transcript corpus via CDI observer or lazy fallback.

Refs #764"
```

---

## Batch 5: Cognitive Integration

### Task 7: CognitiveMemoryRetriever extension + ModulationProfile for corpus results

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveMemoryRetriever.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/ModulationProfiles.java` (or wherever MEMORY/NODE profiles live)
- Create: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveMemoryRetrieverCorpusTest.java`

**Interfaces:**
- Consumes: `FederatedCorpusSearch` SPI, `CorpusSearchResult`, `ModulationProfile`, `RetrievalModulator` from cognitive-api
- Produces: `queryCorpora()` method on `CognitiveMemoryRetriever`, `ModulationProfiles.CORPUS`

- [ ] **Step 1: Write failing test for corpus retrieval via CognitiveMemoryRetriever**

```java
@Test
void queryCorporaAppliesRecencyModulation() {
    // Set up a FederatedCorpusSearch stub with two results at different timestamps
    // Call queryCorpora with a ModulationContext
    // Assert results are re-ordered by modulated score (recency decay applied)
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL

- [ ] **Step 3: Add CORPUS ModulationProfile**

Use `ide_insert_member` to add to `ModulationProfiles`:
```java
public static final ModulationProfile<CorpusSearchResult> CORPUS = new ModulationProfile<>(
    r -> Confidence.stated(),
    r -> 0.0,  // pleasure — neutral
    r -> 0.0,  // arousal — neutral
    r -> 0.0,  // dominance — neutral
    CorpusSearchResult::entryTimestamp
);
```

- [ ] **Step 4: Add queryCorpora method to CognitiveMemoryRetriever**

Use `ide_insert_member` to add the new method:
```java
public List<CorpusSearchResult> queryCorpora(
        CorpusQuery query, String tenantId, ModulationContext context) {
    var results = federatedCorpusSearch.search(query, tenantId).results();
    return RetrievalModulator.apply(results, ModulationProfiles.CORPUS, modulationFactors, context);
}
```

- [ ] **Step 5: Run tests to verify they pass**

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cognitive-index/
git commit -m "feat(#763): extend CognitiveMemoryRetriever with corpus search

Adds queryCorpora() for modulated corpus retrieval. CORPUS
ModulationProfile uses neutral PAD defaults — only recency decay
and goal relevance produce meaningful differentiation.

Refs #763"
```

### Task 8: CorpusKnowledgePromptSection + CorpusEntryPromoter

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/CorpusKnowledgePromptSection.java`
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusEntryPromoter.java`
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/CorpusKnowledgePromptSectionTest.java`
- Create: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/CorpusEntryPromoterTest.java`

**Interfaces:**
- Consumes: `CognitionPromptRenderer` SPI (cognition-api), `CognitiveMemoryRetriever` (Task 7), `CorpusEntryStore` (Task 5), `MindMapStore` (mindmap-api), `NodeRef` (mindmap-api)
- Produces: `CorpusKnowledgePromptSection` (renders corpus knowledge into prompt), `CorpusEntryPromoter` (promotes corpus entry to MindMap node)

- [ ] **Step 1: Write failing tests for CorpusKnowledgePromptSection**

Test that relevant corpus entries are retrieved during tick and rendered into prompt sections grouped by source corpus.

- [ ] **Step 2: Implement CorpusKnowledgePromptSection**

`CognitionPromptRenderer` implementation. During `CognitionPhase.SOURCE`, queries corpora via `CognitiveMemoryRetriever.queryCorpora()`. Renders results grouped by source corpus name.

- [ ] **Step 3: Write failing tests for CorpusEntryPromoter**

Test: retrieve entry → create MindMap node → add NodeRef("corpus", entryId, corpusName) → update entry with promoted_to.

- [ ] **Step 4: Implement CorpusEntryPromoter**

As specified in §6.2 of the spec. Uses `NodeRef(scheme="corpus", id=entryId, qualifier=corpusName)`.

- [ ] **Step 5: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition,corpus-management`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cognition/ corpus-management/
git commit -m "feat(#763): add CorpusKnowledgePromptSection and CorpusEntryPromoter

Corpus knowledge rendered into cognitive prompt during SOURCE phase.
Explicit promotion from corpus entry to MindMap node with bidirectional
NodeRef cross-reference.

Refs #763"
```

---

## References

- `specs/issue-763-cognitive-knowledge-management/2026-11-02-cognitive-knowledge-management-design.md` — design spec this plan implements
- `rag-api/src/main/java/io/casehub/neocortex/rag/CorpusRef.java` — existing typed corpus identity
- `rag-api/src/main/java/io/casehub/neocortex/rag/CaseRetriever.java` — hybrid search SPI
- `rag-api/src/main/java/io/casehub/neocortex/rag/EmbeddingIngestor.java` — ingest SPI
- `rag-api/src/main/java/io/casehub/neocortex/rag/ProvenanceTracker.java` — provenance SPI
- `rag-scoring/src/main/java/io/casehub/neocortex/rag/scoring/AdaptiveSearchWrapper.java` — adaptive search
- `fusion-api/src/main/java/io/casehub/neocortex/fusion/ScoreFusion.java` — RRF/CC fusion
- `corpus-api/pom.xml` — module template for zero-dep APIs
- `sqlite-support/` — SqliteDataSourceFactory for SQLite persistence
- `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveMemoryRetriever.java` — existing modulated retrieval
- `/Users/mdproctor/claude/hortora/engine/src/main/java/io/hortora/garden/federation/ChainWalker.java` — federation reference impl
- `/Users/mdproctor/claude/hortora/engine/src/main/java/io/hortora/garden/provenance/ProvenanceStore.java` — provenance reference impl
- `/Users/mdproctor/claude/hortora/engine/src/main/java/io/hortora/garden/search/SearchProfileStore.java` — BOM snapshot storage
- casehubio/neocortex#763 — Epic: Autonomous cognitive knowledge management
- casehubio/neocortex#764 — Transcript-indexed episodic retrieval

# Hortora Engine Migration Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #763 — Autonomous cognitive knowledge management
**Issue group:** #763, #764

**Goal:** Move Hortora engine's 9-month-mature code into corpus-management, replacing thin reimplementations. Hortora becomes a thin deployment layer. Hortora's test suite validates the migration.

**Architecture:** Move framework-neutral engine code (value types, SQLite stores, search service, metadata extractor, outcome service) from Hortora into corpus-management via IntelliJ. Strip CDI annotations, use constructor injection. Hortora keeps deployment-specific code (HTTP federation, Qdrant migration, MCP tools, REST, config, CDI producers) and adds corpus-management as a dependency. CDI producers in Hortora bridge GardenConfig → constructor params for moved classes.

**Tech Stack:** Java 21, Quarkus 3.32.2, SQLite + HikariCP, IntelliJ MCP (ide_move_file, ide_refactor_rename)

## Global Constraints

- ALL source file moves use `ide_move_file`. No bash cp/mv for .java files.
- IntelliJ workspace must be open with both neocortex and hortora/engine.
- For cross-project `ide_move_file`: use `project_path` for the source project. If cross-project move fails, fallback: read file → `ide_create_file` in target → `ide_refactor_safe_delete` in source.
- Generification means: replace `@Inject GardenConfig config` with constructor param `CorpusRef corpusRef` (or `Path gardenPath` where the path is needed). Remove `@ApplicationScoped`, `@Inject`. Pure Java constructors.
- ChainWalkerFederatedSearch (in-process catalogue federation) STAYS in corpus-management — it's a different capability from Hortora's HTTP-based ChainWalker.
- Moved files go to `io.casehub.neocortex.corpus.management.impl` package in corpus-management.
- Hortora's Flyway migrations move along with their stores (non-Java, bash OK for .sql files).

---

## Batch 1: Delete Reimplementations + Add Dependencies

### Task 1: Clean corpus-management of inferior reimplementations and prepare pom.xml

**Files:**
- Delete: `corpus-management/src/main/java/.../impl/ProvenanceStoreImpl.java`
- Delete: `corpus-management/src/main/java/.../impl/RetrieverCorpusSearch.java`
- Delete: `corpus-management/src/main/java/.../impl/CorpusReindexService.java`
- Delete: `corpus-management/src/test/java/.../impl/ProvenanceStoreImplTest.java`
- Delete: `corpus-management/src/test/java/.../impl/RetrieverCorpusSearchTest.java`
- Delete: `corpus-management/src/test/java/.../impl/CorpusReindexServiceTest.java`
- Delete: `corpus-management/src/main/resources/db/corpus-provenance/V1__create_provenance.sql` (wrong schema — Hortora's V1-V3 replace this)
- Modify: `corpus-management/pom.xml` — add deps needed by moved code
- Modify: Hortora `engine/pom.xml` — add corpus-management dependency

**Interfaces:**
- Consumes: nothing
- Produces: clean target directory for Hortora code; dependency wiring for both projects

- [ ] **Step 1: Delete reimplemented Java files via ide_refactor_safe_delete**

For each file, use `ide_refactor_safe_delete` with `target_type="file"` and `force=true`:
```
ProvenanceStoreImpl.java
RetrieverCorpusSearch.java
CorpusReindexService.java
ProvenanceStoreImplTest.java
RetrieverCorpusSearchTest.java
CorpusReindexServiceTest.java
```

- [ ] **Step 2: Delete wrong provenance migration**

```bash
rm /Users/mdproctor/claude/casehub/slots/221/neocortex/corpus-management/src/main/resources/db/corpus-provenance/V1__create_provenance.sql
```

- [ ] **Step 3: Add dependencies to corpus-management pom.xml**

Add to `corpus-management/pom.xml`:
```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-rag-scoring</artifactId>
    <version>${project.version}</version>
</dependency>
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-rag</artifactId>
    <optional>true</optional>
</dependency>
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-memory-api</artifactId>
    <optional>true</optional>
</dependency>
```

- [ ] **Step 4: Add corpus-management dependency to Hortora pom.xml**

Add to `engine/pom.xml`:
```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-corpus-management</artifactId>
</dependency>
```

- [ ] **Step 5: Compile both projects to verify clean state**

```
ide_build_project for neocortex
ide_build_project for hortora/engine
```

- [ ] **Step 6: Commit in both repos**

neocortex: `wip: delete reimplementations, prepare for Hortora migration Refs #763`
hortora: `wip: add corpus-management dependency for engine migration Refs #90`

---

## Batch 2: Move Value Types and Stores

### Task 2: Move pure records and SQLite stores from Hortora to corpus-management

**Files:**
- Move: `io.hortora.garden.federation.FederationConfig` → `io.casehub.neocortex.corpus.management.impl.FederationConfig`
- Move: `io.hortora.garden.search.SearchResult` → `io.casehub.neocortex.corpus.management.impl.SearchResult`
- Move: `io.hortora.garden.search.AdaptiveResult` → `io.casehub.neocortex.corpus.management.impl.AdaptiveResult`
- Move: `io.hortora.garden.search.SearchScoringConfig` → `io.casehub.neocortex.corpus.management.impl.SearchScoringConfig`
- Move: `io.hortora.garden.provenance.FeedbackContext` → `io.casehub.neocortex.corpus.management.impl.FeedbackContext`
- Move: `io.hortora.garden.provenance.StalenessReport` → `io.casehub.neocortex.corpus.management.impl.StalenessReport`
- Move: `io.hortora.garden.provenance.ProvenanceStore` → `io.casehub.neocortex.corpus.management.impl.ProvenanceStore`
- Move: `io.hortora.garden.search.SearchProfileStore` → replace existing in corpus-management
- Move: Flyway migrations `db/provenance/migration/V1__provenance.sql`, `V2__staleness_reports.sql`, `V3__feedback_context.sql` → `db/corpus-provenance/`

**Interfaces:**
- Consumes: clean target from Task 1
- Produces: value types and stores available in corpus-management for Tasks 3-4

- [ ] **Step 1: Move value type records via ide_move_file**

For each pure record (FederationConfig, SearchResult, AdaptiveResult, FeedbackContext, StalenessReport, SearchScoringConfig):

```
ide_move_file(
    project_path="/Users/mdproctor/claude/hortora/engine",
    file="src/main/java/io/hortora/garden/federation/FederationConfig.java",
    destination="/Users/mdproctor/claude/casehub/slots/221/neocortex/corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl"
)
```

Repeat for each value type. IntelliJ updates all references in both projects.

If cross-project move fails: read file content → `ide_create_file` in neocortex target → `ide_refactor_safe_delete` in Hortora.

- [ ] **Step 2: Move ProvenanceStore**

```
ide_move_file(
    project_path="/Users/mdproctor/claude/hortora/engine",
    file="src/main/java/io/hortora/garden/provenance/ProvenanceStore.java",
    destination="/Users/mdproctor/claude/casehub/slots/221/neocortex/corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl"
)
```

After move, generify:
- Remove `@ApplicationScoped`
- Replace `@Inject ProvenanceConfig config` with constructor param `String dbPath`
- Remove CDI import statements
- Keep all domain methods (record, recordFeedbackContext, recordStaleness, etc.) intact

- [ ] **Step 3: Replace SearchProfileStore**

Delete the existing SearchProfileStore in corpus-management (my reimplementation), then move Hortora's:

```
ide_refactor_safe_delete: corpus-management SearchProfileStore.java (force=true)
ide_move_file: Hortora SearchProfileStore.java → corpus-management impl/
```

Generify similarly — strip CDI, constructor param for db path.

- [ ] **Step 4: Move Flyway migrations**

```bash
cp /Users/mdproctor/claude/hortora/engine/src/main/resources/db/provenance/migration/V1__provenance.sql \
   /Users/mdproctor/claude/casehub/slots/221/neocortex/corpus-management/src/main/resources/db/corpus-provenance/V1__provenance.sql
cp .../V2__staleness_reports.sql .../db/corpus-provenance/V2__staleness_reports.sql
cp .../V3__feedback_context.sql .../db/corpus-provenance/V3__feedback_context.sql
```

Update ProvenanceStore's FLYWAY_LOCATION constant to match the new path.

- [ ] **Step 5: Compile both projects**

Verify neocortex compiles with moved code. Verify Hortora compiles with updated imports.

- [ ] **Step 6: Commit in both repos**

neocortex: `feat(#763): move value types and stores from Hortora engine Refs #763`
hortora: `refactor: value types and stores migrated to neocortex corpus-management Refs casehubio/neocortex#763`

---

## Batch 3: Move Services

### Task 3: Move SearchResource, GardenMetadataExtractor, GardenReindexService, GardenOutcomeService

**Files:**
- Move: `io.hortora.garden.search.SearchResource` → `io.casehub.neocortex.corpus.management.impl.CorpusSearchService`
- Move: `io.hortora.garden.index.GardenMetadataExtractor` → `io.casehub.neocortex.corpus.management.impl.CorpusMetadataExtractor`
- Move: `io.hortora.garden.index.GardenReindexService` → `io.casehub.neocortex.corpus.management.impl.CorpusReindexService`
- Move: `io.hortora.garden.outcome.GardenOutcomeService` → `io.casehub.neocortex.corpus.management.impl.CorpusOutcomeService`

**Interfaces:**
- Consumes: value types and stores from Task 2
- Produces: complete search + extraction + reindex + outcome services in corpus-management

- [ ] **Step 1: Move SearchResource → CorpusSearchService**

```
ide_move_file(
    project_path="/Users/mdproctor/claude/hortora/engine",
    file="src/main/java/io/hortora/garden/search/SearchResource.java",
    destination="/Users/mdproctor/claude/casehub/slots/221/neocortex/corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl"
)
ide_refactor_rename(
    project_path="/Users/mdproctor/claude/casehub/slots/221/neocortex",
    file="corpus-management/src/main/java/.../impl/SearchResource.java",
    newName="CorpusSearchService",
    targetType="file"
)
```

Generify:
- Remove `@ApplicationScoped`, `@Inject`
- Replace `@Inject GardenConfig config` with constructor param `CorpusRef corpusRef`
- Replace `@Inject SearchConfig searchConfig` with constructor param `SearchConfig`
- Replace `@Inject ChainWalker chainWalker` with constructor param (nullable — null when no federation)
- Replace `@Inject FederationConfig federationConfig` with constructor param (nullable)
- All other injected deps (CaseRetriever, SearchScoringConfig, SearchProfileStore) become constructor params
- Keep all search logic INTACT — adaptive filtering, BOM scoring, see-also, everything

- [ ] **Step 2: Move GardenMetadataExtractor → CorpusMetadataExtractor**

```
ide_move_file + ide_refactor_rename
```

Already implements `MetadataExtractor` (neocortex SPI). Self-contained — minimal generification needed. Just rename.

- [ ] **Step 3: Move GardenReindexService → CorpusReindexService**

```
ide_move_file + ide_refactor_rename
```

Generify: `GardenConfig` → constructor param `CorpusRef corpusRef`.

- [ ] **Step 4: Move GardenOutcomeService → CorpusOutcomeService**

```
ide_move_file + ide_refactor_rename
```

Generify: `GardenConfig` → constructor params `CorpusRef corpusRef` and `Path scope`.

- [ ] **Step 5: Compile both projects**

- [ ] **Step 6: Commit in both repos**

neocortex: `feat(#763): move search service, metadata extractor, reindex, outcome from Hortora Refs #763`
hortora: `refactor: services migrated to neocortex corpus-management Refs casehubio/neocortex#763`

---

## Batch 4: Wire Hortora + Create CDI Producers

### Task 4: Create CDI producers in Hortora and update MCP/REST code

**Files:**
- Create: `engine/src/main/java/io/hortora/garden/config/CorpusManagementProducer.java`
- Modify: `engine/src/main/java/io/hortora/garden/mcp/GardenMcpTools.java` — update imports
- Modify: REST resources — update imports to corpus-management packages
- Modify: Hortora test files — update imports

**Interfaces:**
- Consumes: all moved code from Tasks 2-3
- Produces: Hortora wired as thin deployment layer; CDI producers bridge GardenConfig → constructor params

- [ ] **Step 1: Create CorpusManagementProducer in Hortora**

CDI producer that bridges GardenConfig to corpus-management constructors:

```java
@ApplicationScoped
public class CorpusManagementProducer {

    @Inject GardenConfig config;
    @Inject CaseRetriever caseRetriever;

    @Produces @Singleton
    CorpusSearchService corpusSearchService(/* injected deps */) {
        return new CorpusSearchService(
            new CorpusRef("hortora", config.id()),
            caseRetriever,
            /* other params from config */
        );
    }

    @Produces @Singleton
    ProvenanceStore provenanceStore() {
        return new ProvenanceStore(config.provenanceDbPath());
    }

    @Produces @Singleton
    CorpusReindexService reindexService(EmbeddingIngestor ingestor, CursorStore cursor) {
        return new CorpusReindexService(
            new CorpusRef("hortora", config.id()),
            ingestor, cursor
        );
    }

    @Produces @Singleton
    CorpusOutcomeService outcomeService(CbrCaseMemoryStore cbrStore) {
        return new CorpusOutcomeService(
            new CorpusRef("hortora", config.id()),
            cbrStore
        );
    }

    @Produces @Singleton
    CorpusMetadataExtractor metadataExtractor() {
        return new CorpusMetadataExtractor();
    }
}
```

Adjust exact constructor params based on what each class actually needs after generification.

- [ ] **Step 2: Update GardenMcpTools imports**

IntelliJ should have updated most imports automatically during the moves. Verify `GardenMcpTools` now imports from `io.casehub.neocortex.corpus.management.impl.*`. Fix any remaining broken references.

- [ ] **Step 3: Update REST resource imports**

Same — verify and fix imports for ProvenanceResource, ProfileResource, EntryResource, OutcomeResource, ReindexResource.

- [ ] **Step 4: Update test imports**

Verify Hortora test files have updated imports. IntelliJ should have handled this, but verify: ProvenanceStoreTest, SearchResourceTest, SearchProfileStoreTest, GardenMetadataExtractorTest, GardenOutcomeServiceTest.

- [ ] **Step 5: Compile both projects**

- [ ] **Step 6: Commit in both repos**

neocortex: (no changes this batch — all changes are in Hortora)
hortora: `feat: wire Hortora as thin deployment layer on corpus-management Refs casehubio/neocortex#763`

---

## Batch 5: Verify

### Task 5: Run all tests in both projects

**Files:** none (verification only)

**Interfaces:**
- Consumes: complete migration from Tasks 1-4
- Produces: green test suites proving migration preserved functionality

- [ ] **Step 1: Run Hortora engine tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -f /Users/mdproctor/claude/hortora/engine/pom.xml
```

Expected: all 22 test files pass. These tests exercise the moved code through Hortora's CDI producers — if they pass, the migration preserved functionality.

Key tests to watch:
- `ChainWalkerTest` — federation still works (ChainWalker stayed in Hortora)
- `ProvenanceStoreTest` — provenance through CDI producer → moved ProvenanceStore
- `SearchResourceTest` → exercises CorpusSearchService through CDI producer
- `GardenMcpToolsTest` — MCP tools still work end-to-end
- `FederationIntegrationTest` — WireMock federation test
- `CollectionMigrationTest` — Qdrant migration (stayed in Hortora)

- [ ] **Step 2: Run corpus-management tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management -f /path/to/neocortex/pom.xml
```

Expected: all tests pass (existing + moved code tests if any migrated).

- [ ] **Step 3: Run neocortex full build**

```
ide_build_project for neocortex (rebuild=true)
```

Expected: clean build, zero errors in corpus-management/cognition/cognitive-index modules.

- [ ] **Step 4: Commit verification state**

If any fixes were needed, commit them. Update HANDOFF.md with migration status.

---

## References

- `specs/issue-763-cognitive-knowledge-management/2026-11-02-hortora-migration-remediation.md` — remediation spec
- `specs/issue-763-cognitive-knowledge-management/2026-11-02-cognitive-knowledge-management-design.md` — original design
- `specs/issue-763-cognitive-knowledge-management/decisions.md` — D17 recovery decision
- Hortora engine: `/Users/mdproctor/claude/hortora/engine/` (34 source, 22 test files)
- Gap audit: 2 matched, 5 partial, 5 missing, 13 deployment-specific
- casehubio/neocortex#763

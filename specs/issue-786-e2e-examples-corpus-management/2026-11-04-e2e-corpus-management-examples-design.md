# E2E Corpus-Management Examples — Design Spec

**Issue:** casehubio/neocortex#786
**Epic:** casehubio/neocortex#789 (Corpus & workspace platform — abstraction remediation)
**Date:** 2026-11-04
**Depends on:** #785 (audit, closed), #800 (phase 1 renames, closed)

## Goal

Prove corpus-management is domain-neutral by building working E2E examples across 4 diverse domains. Each example defines its own `CorpusType` with domain-specific field schemas and exercises the full corpus-management API: creation, ingestion, search, lifecycle, and catalogue operations.

## Module Structure

A single standalone Maven module `example-corpus-management/` under `examples/`, activated by `-Pexamples-smoke` profile.

```
examples/example-corpus-management/
  pom.xml
  src/test/java/io/casehub/neocortex/examples/corpus/
    CorpusTestHarness.java              — shared wiring: SQLite :memory: + impl classes
    domains/
      garden/
        GardenCorpusTypes.java
        GardenScenarioTest.java
      literature/
        LiteratureCorpusTypes.java
        LiteratureScenarioTest.java
      clinical/
        ClinicalCorpusTypes.java
        ClinicalScenarioTest.java
      npc/
        NpcCorpusTypes.java
        NpcScenarioTest.java
    federation/
      FederatedSearchScenarioTest.java
```

## Per-Domain Pattern

Each domain has two classes:

### `*CorpusTypes.java` — Schema Definition

Static factory class defining the domain's `CorpusType` via the record constructor. Each domain exercises different `FieldSchema` types to prove the type system handles diverse shapes.

### `*ScenarioTest.java` — Lifecycle Exercise

Plain JUnit test with manual wiring (no CDI — corpus-management is framework-neutral). A shared `CorpusTestHarness` utility creates the SQLite `:memory:` DataSource and wires the implementation classes:

```java
class CorpusTestHarness {
    static CorpusTestHarness create() {
        var ds = SqliteDataSourceFactory.create(":memory:", 1, 3000);
        var catalogue = new SqliteCorpusCatalogue(ds);
        var entryStore = new SqliteCorpusEntryStore(ds, noOpIngestor());
        // ... wire remaining implementations
        return new CorpusTestHarness(catalogue, entryStore, ...);
    }
}
```

Each scenario test exercises the full API surface:

1. **Create** — `CorpusManager.create(name, type, tenantId, upstream, peers, metadata)`
2. **Ingest** — `CorpusEntryStore.add(corpusRef, entry)` with 5-8 sample entries
3. **Search** — `CorpusSearch.search(corpusRef, query)` with domain-relevant queries
4. **Catalogue** — `CorpusCatalogue.list(tenantId, lifecycle)`, `get(corpusRef)`, `forType(type, tenantId)`
5. **Archive** — `CorpusManager.archive(corpusRef)`, verify search excludes archived entries
6. **Revive** — `CorpusManager.revive(corpusRef)`, verify search includes entries again

## Domain Schemas

### Garden (knowledge entries)

| Field | Required | FieldSchema |
|-------|----------|-------------|
| id | yes | STRING |
| title | yes | STRING |
| type | yes | STRING |
| domain | yes | STRING |
| tags | no | STRING_LIST |
| score | no | DOUBLE |
| staleness_threshold | no | DURATION |
| invalidation_triggers | no | STRING_LIST |

Sample entries: technique docs (debugging patterns), gotcha entries (framework quirks), decision records (why X over Y).

### Literature (academic papers)

| Field | Required | FieldSchema |
|-------|----------|-------------|
| id | yes | STRING |
| title | yes | STRING |
| authors | yes | STRING_LIST |
| year | yes | INTEGER |
| abstract | yes | STRING |
| doi | no | STRING |
| journal | no | STRING |
| citations | no | STRING_LIST |
| keywords | no | STRING_LIST |
| methodology | no | STRING |

Sample entries: papers on CBR, RAG, knowledge graphs, cognitive architectures.

### Clinical (guideline protocols)

| Field | Required | FieldSchema |
|-------|----------|-------------|
| id | yes | STRING |
| title | yes | STRING |
| version | yes | STRING |
| effective_date | yes | INSTANT |
| condition | yes | STRING |
| supersedes | no | STRING |
| evidence_grade | no | STRING |
| contraindications | no | STRING_LIST |
| review_date | no | INSTANT |

Sample entries: treatment protocols with version chains (v1 superseded by v2), evidence grading, contraindication lists.

### Game NPC (world knowledge)

| Field | Required | FieldSchema |
|-------|----------|-------------|
| id | yes | STRING |
| name | yes | STRING |
| entity_type | yes | STRING |
| location | yes | STRING |
| relationships | no | STRING_LIST |
| faction | no | STRING |
| inventory | no | STRING_LIST |
| dialogue_tags | no | STRING_LIST |
| quest_refs | no | STRING_LIST |

Sample entries: NPCs with relationships and faction ties, locations, items with cross-references.

## Federation Scenario

`FederatedSearchScenarioTest` creates 2 corpora from different domains (literature + clinical — the most natural cross-domain pairing for information retrieval) and exercises:

1. **Baseline** — single-corpus search within each corpus independently
2. **Federated search** — `FederatedCorpusSearch.search(query, tenantId)` returning results from both corpora
3. **Federation depth** — `CorpusQuery.withFederationDepth()` to control traversal
4. **Corpus weights** — `CorpusQuery.corpusWeights` to bias toward one corpus
5. **Archived exclusion** — archive one corpus, verify federated search excludes it
6. **Include archived** — `CorpusQuery.withIncludeArchived(true)` to opt in

## Build Integration

### POM Dependencies

```xml
<dependencies>
    <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-corpus-management</artifactId>
    </dependency>
    <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-sqlite-support</artifactId>
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
```

No Quarkus dependency — corpus-management is framework-neutral. SQLite `:memory:` is wired programmatically via `SqliteDataSourceFactory`.

### Profile Activation

Add the module to the parent POM's `examples-smoke` profile alongside existing example modules. No Docker, no ONNX models, no external services.

No `application.properties` needed — all configuration is programmatic.

## Sample Data Strategy

Each domain provides 5-8 hardcoded sample entries as static factory methods in the scenario test class (not external files). This keeps each scenario self-contained and readable without file I/O concerns.

If entry bodies are longer than a few sentences, use `src/test/resources/sample-data/<domain>/` text files loaded via `getClass().getResourceAsStream()`.

## What This Does NOT Cover

- **Structured content** — entries use String bodies only. Phase 3 (#802) will add `Content` sealed hierarchy (TextContent/BinaryContent/StructuredContent).
- **Built-in CorpusType constants** — examples define custom types only. Phase 2 (#801) will move KNOWLEDGE_GARDEN/RESEARCH/TRANSCRIPT constants to Hortora-specific code.
- **RAG integration** — examples exercise corpus-management layer only, not the lower-level corpus-api/rag pipeline. `example-rag-pipeline` covers that.
- **Vector search** — in-memory backend; no Qdrant. Federation and search are text/metadata-based.

## Success Criteria

1. All 4 domain scenarios pass with `mvn test -Pexamples-smoke`
2. Each domain defines a genuinely different CorpusType schema (not cosmetic renames)
3. Federation scenario demonstrates cross-domain search working
4. No imports from domain-specific packages (Hortora, etc.) — pure corpus-management API
5. Each scenario is readable as standalone reference code for a consumer adopting corpus-management

## Design Note: No CDI

corpus-management is deliberately framework-neutral. All implementation classes (`SqliteCorpusEntryStore`, `SqliteCorpusCatalogue`, etc.) use constructor injection with no CDI annotations. The module's own tests use `SqliteDataSourceFactory.create(":memory:", ...)` for manual wiring. The examples follow this same pattern via `CorpusTestHarness`.

This is an intentional architectural choice — corpus-management sits below the Quarkus layer and can be used by non-Quarkus consumers.

## References

- casehubio/neocortex#786 — issue body
- casehubio/neocortex#789 — parent epic
- `docs/specs/2026-11-04-corpus-domain-abstraction-audit.md` — #785 audit, phase roadmap
- `corpus-management-api/` — CorpusType, CorpusManager, CorpusCatalogue, CorpusSearch, FederatedCorpusSearch SPIs
- `examples/example-rag-pipeline/` — existing example module pattern
- `examples/example-text-analysis/` — existing programmatic example pattern
- `corpus-management/src/test/.../SqliteCorpusEntryStoreTest.java` — manual wiring pattern for in-memory SQLite
- `sqlite-support/` — `SqliteDataSourceFactory` for shared DataSource creation

# Cognitive Knowledge Management — Design Spec

**Date:** 2026-11-02
**Epic:** casehubio/neocortex#763 (Autonomous cognitive knowledge management)
**Also covers:** casehubio/neocortex#764 (Transcript-indexed episodic retrieval)
**Status:** Draft

---

## 1. Problem Statement

Cognitive agents need to create, populate, query, and evolve searchable bodies of knowledge as part of sustained work. The platform has seven stores (MindMap, CaseMemoryStore, CbrRecordStore, Qdrant/RAG, CorpusStore, CacheStore, Hortora garden) with seven different query models and no unifying abstraction for "a collection of searchable knowledge with a lifecycle."

Hortora demonstrates the full pattern — curated entries, Qdrant-backed search, federation, provenance, staleness, feedback — but it's locked to one deployment and human-authored entries. Agents can't create knowledge stores on demand, and interaction history (#764) isn't searchable at all.

### 1.1 What This Epic Delivers

A **corpus** abstraction: a typed, searchable, federable collection of knowledge that agents can create, populate, query, evolve, and share. The abstraction:

- Generalises Hortora's garden engine into a universal capability
- Supports heterogeneous source material (PDFs, transcripts, curated entries, scans)
- Supports agent-authored and human-authored entries equally
- Enables federated hierarchical knowledge sharing across agents and organisations
- Integrates with the cognitive pipeline for modulated retrieval
- Makes Hortora a deployment configuration of neocortex, not a separate codebase

### 1.2 Design Principles

- **Hortora is the reference implementation.** The garden engine already works. This epic generalises it, not reinvents it.
- **Corpus is a peer, not a replacement.** MindMap (graph), CaseMemoryStore (events), and CbrRecordStore (feature vectors) have fundamentally different data models. The corpus is vector-indexed document search — a distinct access pattern. Promotion from corpus to MindMap is explicit.
- **The agent searches its own understanding.** Index records are derived from cover documents (the agent's synthesis), not raw source material. Search returns what the agent understands, not what it ingested.
- **Knowledge composes hierarchically.** Corpora inherit from upstream sources and federate with peers. Local overrides win. Universal truths propagate down.

---

## 2. Architecture

### 2.1 Core Concept

A **corpus** is:
- A **typed collection** — declares its document schema at creation (knowledge-garden, research, transcript, domain-expert, investigation)
- A **catalogue entry** — registered in a corpus catalogue per agent/tenant
- A **Qdrant collection** — vector-indexed cover documents for hybrid search
- An **artifact store** — optional original documents (PDFs, scans, transcripts) in CorpusStore/ZIP
- A **federation node** — 0..n upstream sources (parent chain) + 0..n peer sources (sibling corpora)

### 2.2 Three-Layer Document Model

| Layer | What | Format | Storage | Present for all types? |
|-------|------|--------|---------|----------------------|
| **Original artifact** | Source document in native format | PDF, HTML, JSON, image, scan | CorpusStore (ZIP archives) | No — curated entries (Hortora-style) have no separate original |
| **Cover document** | Metadata + summary + annotations + cross-refs | Markdown + YAML frontmatter (garden entry format) | Filesystem + Qdrant payload | Yes — every corpus entry has a cover |
| **Index record** | Embedded vectors derived from cover | Dense + sparse + BM25 | Qdrant collection | Yes — derived from cover, not original |

**Cover documents are garden entries.** The Hortora entry format (markdown body + YAML frontmatter) is the universal cover format. Different corpus types have different required/optional frontmatter fields:

```yaml
# Research paper cover
---
id: CE-20261102-a1b2c3
title: "Sleep consolidation follows a two-stage process"
type: research-paper
corpus: memory-consolidation-review
domain: neuroscience
tags: [consolidation, sleep, memory]
source_artifact: corpus://memory-consolidation-review/artifacts/walker-2005.pdf
provenance:
  ingested: 2026-11-02
  source_url: https://doi.org/10.1016/...
  ingested_by: agent-researcher-01
staleness_threshold: 365d
citations: [walker-2005]
---

Walker (2005) demonstrates that sleep-dependent memory consolidation
operates in two stages: an initial SWS-dependent stabilisation phase
followed by a REM-dependent integration phase...

## Key Findings
- ...

## Relevance to Current Research
- Contradicts single-stage model proposed by [CE-20261015-x7y8z9]
- Supports the temporal separation hypothesis in our review framework
```

```yaml
# Transcript cover
---
id: CE-20261102-t4u5v6
title: "Design discussion: corpus management architecture"
type: transcript
corpus: agent-01-interactions
interaction_type: agent-human
activity_type: design-discussion
domain: neocortex
participants: [agent-01, mark]
turn_count: 47
---

Brainstorming session on unified knowledge management for
casehub-neocortex. Explored corpus abstraction, three-layer
document model, federated hierarchy. Key decisions: typed corpora,
Hortora absorption into neocortex, full four-level hierarchy...

## Topics Covered
- Corpus as first-class concept
- Three-layer document model (original + cover + index)
- Federated hierarchy with upstream/peer edges
```

### 2.3 Federation Model

Every corpus is a node in a federation graph:

```
canonical corpora (universal knowledge)
  └── community corpora (ecosystem conventions)
      └── platform corpora (organisation knowledge)
          └── product corpora (agent-local understanding)
```

Each corpus can have:
- **0..n upstream sources** — parent chain. Sequential walk. Child augments parent; overrides win.
- **0..n peer sources** — sibling corpora. Parallel fan-out. Equal contributors.

A searching client composes its search scope from **1..n sources** — its own corpora plus the upstream/peer chain.

```
Agent A's research corpus
  ├── upstream: Platform knowledge garden
  │     └── upstream: Community Quarkus garden
  │           └── upstream: Canonical Java garden
  └── peer: Agent B's research corpus (same topic)
  └── peer: Agent C's findings corpus
```

**Search walk** (ChainWalker pattern):
1. Search own corpus
2. Walk upstream chain sequentially — stop when sufficient results found (unless `searchOrder: always`)
3. Fan out to peers in parallel — only when own + upstream are insufficient
4. Merge: group by tier (own=0, upstream=1..N, peer=MAX_VALUE), sort by relevance within tier, dedup
5. Apply cognitive modulation post-merge

**Override semantics:** A child entry with the same `overrides: <parent-entry-id>` frontmatter field supersedes the parent entry in search results. The parent entry is still retrievable on explicit request but drops from default federated search. Deleting the child override re-surfaces the parent — override suppression is evaluated at search time (not stored as state), so removing the override entry immediately restores the parent's visibility.

**Cycle detection:** `ChainWalkerFederatedSearch` maintains a `Set<CorpusRef> visited` during each search walk. Before searching a corpus, it checks `visited` — if the corpus has already been searched, it is skipped. This prevents cycles in the federation graph (A → B → A) without requiring the caller to manage visited state.

**Failure handling:** Federation search is best-effort. When an upstream or peer corpus search fails (Qdrant unavailable, timeout, error):
1. The failure is logged with the corpus ref and error details
2. The corpus is recorded in `SearchReport.skipped` with the failure reason
3. `SearchReport.partial` is set to `true`
4. Search continues with remaining corpora — a single failure does not abort the entire federation walk
5. The caller can inspect `FederatedSearchResult.report()` to determine result completeness

### 2.4 Module Structure

```
corpus-management-api/     — Tier 1 pure Java, zero CDI
  CorpusManager SPI         — create, open, close, archive, revive
  CorpusCatalogue SPI       — list, get, register, deregister
  CorpusEntryStore SPI      — add, update, remove, get entries
  CorpusSearch SPI          — single-corpus search
  FederatedCorpusSearch SPI — cross-corpus federated search
  CorpusType                — type descriptor (name, required frontmatter, cover template)
  CorpusDescriptor          — catalogue entry record (id, name, type, status, upstream refs, peer refs)
  CorpusEntry               — cover document record (id, frontmatter map, body, artifact ref)
  CorpusQuery               — search query (text, filters, corpus scope, federation depth)
  CorpusSearchResult        — result record (entry, score, source corpus, tier)
  CorpusLifecycle enum      — ACTIVE, ARCHIVED
  FederationRef             — upstream/peer reference (url or local corpus id)

corpus-management/          — CDI wiring, Qdrant, SQLite catalogue
  QdrantCorpusEntryStore     — Qdrant collection per corpus, cover→embedding
  SqliteCorpusCatalogue      — catalogue persistence (SQLite + HikariCP WAL)
  ChainWalkerFederatedSearch — upstream sequential + peer parallel federation
  CorpusReindexService       — delete collection + re-embed all covers
  CollectionMigrationService — dimension/sparse config change detection
  SearchProfileStore         — BOM snapshot storage for version-aware scoring
  ProvenanceStoreImpl        — implements ProvenanceTracker (rag-api SPI)
  CoverDocumentParser        — markdown+YAML parsing → CorpusEntry
  CoverDocumentGenerator     — per-type cover generation (transcript, research paper)
  ArtifactBridge             — original document storage via CorpusStore (corpus-api)
  CorpusManagerImpl          — lifecycle orchestration (create collection, register in catalogue)
```

### 2.5 Dependency Direction

```
corpus-management-api  (zero CDI deps)
    ↑ depends on
    ├── rag-api (CorpusRef, CaseRetriever, EmbeddingIngestor,
    │            ProvenanceTracker, PostRetrievalScorer, RetrievalTracker)
    ├── corpus-api (CorpusStore for artifact storage)
    └── cognitive-api (Confidence, CorpusRelabelRequested event)

corpus-management  (CDI, Qdrant, SQLite)
    ↑ depends on
    ├── corpus-management-api
    ├── rag (Qdrant wiring, hybrid search)
    ├── rag-scoring (TemporalDecayScorer, VersionScorer, AdaptiveSearchWrapper)
    ├── rag-tracking (retrieval event recording)
    ├── sqlite-support (SqliteDataSourceFactory)
    └── fusion-api (ScoreFusion for cross-corpus RRF merge)

cognitive-index (CognitiveMemoryRetriever extension)
    ↑ uses
    └── corpus-management-api (CorpusSearch, FederatedCorpusSearch)
```

**Note:** `FederationStrategy` (rag-api) is NOT a dependency. corpus-management defines its own federation via `FederatedCorpusSearch` — a higher-level abstraction that orchestrates the full catalogue-aware federation walk. `FederationStrategy` is designed for rag-level federation (single query → federated results). `FederatedCorpusSearch` handles corpus-level federation (catalogue graph traversal → per-corpus search → cross-corpus merge).

Consumers (agents, engine, Hortora deployment) depend on `corpus-management-api` only.

---

## 3. Core SPIs

### 3.0 Layering Relationship to rag-api

corpus-management-api SPIs **compose** rag-api SPIs — they are higher-level abstractions, not replacements:

| corpus-management-api SPI | Delegates to (rag-api) | What it adds |
|---|---|---|
| `CorpusEntryStore.add()` | `EmbeddingIngestor.ingest()` | Cover document parsing, frontmatter validation against `CorpusType` schema, artifact storage via `CorpusStore`, provenance recording |
| `CorpusSearch.search()` | `CaseRetriever.retrieve()` | Catalogue-aware corpus resolution, `CorpusType`-specific frontmatter extraction, result wrapping as `CorpusSearchResult` with source attribution and tier |
| `FederatedCorpusSearch.search()` | `CorpusSearch` (per-corpus) + `ScoreFusion` | Federation graph walk via catalogue, per-corpus search delegation, cross-corpus RRF merge, override resolution, cycle detection |

`CaseRetriever` operates at the **chunk level** — it returns `List<RetrievedChunk>` (text fragments with scores). `CorpusSearch` operates at the **entry level** — it returns `List<CorpusSearchResult>` (complete cover documents with corpus attribution). The implementations in `corpus-management` bridge these levels: parse cover metadata from `RetrievedChunk.metadata()`, reconstruct `CorpusEntry`, wrap with source corpus and tier info.

**Single-chunk constraint:** Each cover document is embedded as a single `ChunkInput` in `EmbeddingIngestor.ingest()`, maintaining a 1:1 mapping between Qdrant points and cover documents. This is a design constraint, not an accident — cover documents are the agent's **synthesis** (summaries, briefs, annotations), not raw source material. They are designed to be short:
- Hortora garden entries: typically 200–500 tokens
- Transcript briefs: ~100–200 tokens (§5.2)
- Research paper covers: summary + key findings, not the full paper

Source documents that exceed embedding model limits are stored as original artifacts via `ArtifactBridge`, with a short cover document as the searchable handle. If a cover body exceeds the embedding model's max sequence length, `CoverDocumentParser` should truncate with a warning — this indicates the cover needs to be shortened, not that the system needs multi-chunk support.

### 3.1 CorpusManager

Lifecycle management — create, open, archive, revive corpora.

```java
package io.casehub.neocortex.corpus.management;

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

`create()` returns a `CorpusDescriptor` whose `corpusRef()` provides the typed `CorpusRef(tenantId, corpusName)` for all subsequent operations. Lifecycle operations use `CorpusRef` for type-safe corpus identity.

**Name uniqueness:** `corpusName` is unique per `tenantId`. `SqliteCorpusCatalogue` enforces this via a `UNIQUE(tenant_id, corpus_name)` constraint. `create()` with a duplicate name for the same tenant throws `IllegalArgumentException`. This invariant is load-bearing — `CorpusRef(tenantId, corpusName)` is the universal identifier used by every SPI method, and `CorpusCatalogue.get(CorpusRef)` returns `Optional<CorpusDescriptor>` (at most one match).

**Transactional semantics:** `create()` writes the catalogue entry first, then creates the Qdrant collection. If Qdrant creation fails, the catalogue entry is rolled back. `delete()` drops the Qdrant collection first, then removes the catalogue entry. This ordering ensures the catalogue never references a non-existent collection (the failure mode that matters for search), and orphaned Qdrant collections (which are inert) are detected by the reconciliation health check.

### 3.2 CorpusCatalogue

Registry of all corpora per tenant.

```java
public interface CorpusCatalogue {

    List<CorpusDescriptor> list(String tenantId, CorpusLifecycle status);

    Optional<CorpusDescriptor> get(CorpusRef corpus);

    List<CorpusDescriptor> forType(CorpusType type, String tenantId);

    List<CorpusDescriptor> searchScope(CorpusRef corpus);

    HealthReport reconcile(String tenantId);
}
```

`searchScope` returns all corpora reachable from the given corpus via upstream/peer chain — the federation graph for a search query.

`reconcile` compares catalogue entries against Qdrant collections, reporting mismatches: catalogue entries without a Qdrant collection (stale) and Qdrant collections without a catalogue entry (orphaned).

### 3.3 CorpusEntryStore

CRUD for corpus entries (cover documents). Composes `EmbeddingIngestor` for vector storage and `CorpusStore` for artifact storage.

```java
public interface CorpusEntryStore {

    String add(CorpusRef corpus, CorpusEntry entry);

    void update(CorpusRef corpus, String entryId, CorpusEntry entry);

    void remove(CorpusRef corpus, String entryId);

    Optional<CorpusEntry> get(CorpusRef corpus, String entryId);
}
```

Adding an entry triggers: validate frontmatter against `CorpusType.requiredFields` and `optionalFields` (presence AND type) → parse cover document → populate `CorpusEntry.artifactRef` from `artifact_ref` frontmatter field (if present) → embed text via `EmbeddingIngestor.ingest()` → store original artifact in `CorpusStore` (corpus-api) if `artifactRef` is present → record provenance via `ProvenanceTracker`.

**Note:** `artifact_ref` is a frontmatter field validated by `CorpusType` schema — it is required for TRANSCRIPT (in `requiredFields`) and optional for other types. `CoverDocumentParser` extracts it from frontmatter and populates `CorpusEntry.artifactRef`. This single-source-of-truth design ensures the schema enforcement and the record field stay in sync.

### 3.4 CorpusSearch

Single-corpus and federated search. Composes `CaseRetriever` for vector search and `ScoreFusion` for cross-corpus merge.

```java
public interface CorpusSearch {

    List<CorpusSearchResult> search(CorpusRef corpus, CorpusQuery query);
}

public interface FederatedCorpusSearch {

    FederatedSearchResult search(CorpusQuery query, String tenantId);
}
```

`CorpusSearch` delegates to `CaseRetriever.retrieve()` for the underlying Qdrant hybrid search, then reconstructs `CorpusEntry` from the retrieved chunk metadata.

`FederatedCorpusSearch` uses the catalogue to discover the search scope, then delegates to `CorpusSearch` per corpus, then merges via RRF fusion. Returns `FederatedSearchResult` which carries both the ranked results and a `searchReport` indicating which corpora were searched, which were skipped (and why), and whether results are partial due to failures.

### 3.5 CorpusType

Type descriptor — defines what a corpus holds and how covers are generated. Types define the **schema** of cover documents (required frontmatter fields and their types), not the domain. A research corpus about codebase auditing and one about literature review both use `CorpusType.RESEARCH` — they have the same structural schema but different domain labels and tags.

```java
public record CorpusType(
    String name,
    Map<String, FieldSchema> requiredFields,
    Map<String, FieldSchema> optionalFields,
    String coverTemplate
) {
    public static final CorpusType KNOWLEDGE_GARDEN = new CorpusType(
        "knowledge-garden",
        Map.of("id", FieldSchema.STRING, "title", FieldSchema.STRING,
               "type", FieldSchema.STRING, "domain", FieldSchema.STRING),
        Map.of("tags", FieldSchema.STRING_LIST, "score", FieldSchema.DOUBLE,
               "staleness_threshold", FieldSchema.DURATION,
               "invalidation_triggers", FieldSchema.STRING_LIST),
        null
    );

    public static final CorpusType RESEARCH = new CorpusType(
        "research",
        Map.of("id", FieldSchema.STRING, "title", FieldSchema.STRING,
               "type", FieldSchema.STRING, "corpus", FieldSchema.STRING,
               "domain", FieldSchema.STRING),
        Map.of("tags", FieldSchema.STRING_LIST, "source_artifact", FieldSchema.STRING,
               "provenance", FieldSchema.MAP, "citations", FieldSchema.STRING_LIST,
               "staleness_threshold", FieldSchema.DURATION),
        null
    );

    public static final CorpusType TRANSCRIPT = new CorpusType(
        "transcript",
        Map.of("id", FieldSchema.STRING, "title", FieldSchema.STRING,
               "type", FieldSchema.STRING, "corpus", FieldSchema.STRING,
               "interaction_type", FieldSchema.STRING, "activity_type", FieldSchema.STRING,
               "artifact_ref", FieldSchema.STRING),
        Map.of("domain", FieldSchema.STRING, "participants", FieldSchema.STRING_LIST,
               "turn_count", FieldSchema.INTEGER, "tags", FieldSchema.STRING_LIST,
               "related_nodes", FieldSchema.STRING_LIST),
        null
    );
}

public enum FieldSchema {
    STRING, STRING_LIST, INTEGER, DOUBLE, DURATION, MAP, INSTANT
}
```

**Extensibility:** `DOMAIN_EXPERT` and `INVESTIGATION` corpus types are deferred to Phase 5+ (tracked as casehubio/neocortex#TBD). The three current types cover Phase 1–4 use cases. Domain-specific behavior comes from frontmatter values (domain labels, tags, metadata), not from new types — an agent creating a "codebase-audit" corpus uses `RESEARCH` type with `domain: "codebase-audit"`.

### 3.6 Key Value Types

```java
public record CorpusDescriptor(
    String id,
    String name,
    CorpusType type,
    CorpusLifecycle lifecycle,
    CorpusRef corpusRef,
    String qdrantCollection,
    List<FederationRef> upstream,
    List<FederationRef> peers,
    Map<String, String> metadata,
    Instant created,
    Instant lastModified
) {}

public record CorpusEntry(
    String id,
    Map<String, Object> frontmatter,
    String body,
    String artifactRef
) {
    public String stringField(String key) {
        return (String) frontmatter.get(key);
    }
    public List<String> stringListField(String key) {
        @SuppressWarnings("unchecked")
        var list = (List<String>) frontmatter.get(key);
        return list;
    }
    public Instant instantField(String key) {
        return (Instant) frontmatter.get(key);
    }
}

public record CorpusSearchResult(
    CorpusEntry entry,
    double score,
    CorpusRef sourceCorpus,
    int tier,
    Instant entryTimestamp
) {}

public record FederatedSearchResult(
    List<CorpusSearchResult> results,
    SearchReport report
) {}

public record SearchReport(
    List<CorpusRef> searched,
    List<SkippedCorpus> skipped,
    boolean partial
) {}

public record SkippedCorpus(CorpusRef corpus, String reason) {}

public record CorpusQuery(
    String text,
    PayloadFilter filter,
    Set<CorpusRef> corpusRefs,
    int maxResults,
    int federationDepth,
    boolean includeArchived,
    Map<CorpusRef, Double> corpusWeights
) {}

public record FederationRef(
    CorpusRef localRef,
    String url,
    String idPrefix,
    String searchOrder
) {}

public enum CorpusLifecycle { ACTIVE, ARCHIVED }
```

**Notes:**
- `CorpusRef` (from rag-api) is the typed corpus identity throughout — no raw String `corpusId` + `tenantId` pairs.
- `CorpusQuery.filter` uses rag-api's `PayloadFilter` sealed interface directly — reuses the existing filter algebra (`Eq`, `In`, `Not`, `And`, `Or`, `Gte`, `Lte`, `Range`) rather than inventing a new type. This gives callers full expressiveness including temporal range predicates (e.g., `PayloadFilter.gte("provenance.ingested", epochMillis)` for "from last month" queries).
- `CorpusSearchResult.entryTimestamp` — extracted from cover frontmatter at search time, enabling recency-based modulation without requiring full frontmatter parsing at the modulation layer.
- `FederatedSearchResult` wraps results with a `SearchReport` so the caller knows which corpora were skipped and whether the result set is partial.

---

## 4. Hortora Migration

### 4.1 What Moves to corpus-management

| Hortora Engine Capability | LOC (actual) | Migration type | Target in corpus-management |
|---------------------------|-------------|----------------|----------------------------|
| ChainWalker federation | ~184 | **Rewrite** — uses Hortora-specific types (`SearchResult`, `RemoteGardenClient`, `FederationConfig`) | `ChainWalkerFederatedSearch` (uses rag-api/corpus-management-api types) |
| ProvenanceStore | ~340 | Move + adapt | `ProvenanceStoreImpl` (implements rag-api `ProvenanceTracker`) |
| Search orchestration | ~390 (distributed) | **Partial reuse** — `AdaptiveSearchWrapper`, `TemporalDecayScorer`, `VersionScorer` already in neocortex rag-scoring. New code is the corpus-level orchestration layer (~150 LOC new) | `CorpusSearchOrchestrator` |
| SearchProfileStore (BOM snapshots) | ~118 | Move + adapt | `SearchProfileStore` |
| GardenReindexService | ~42 | Move (trivial orchestrator) | `CorpusReindexService` |
| CollectionMigration | ~180 | Move + adapt | `CollectionMigrationService` |
| **Total** | **~1,254 source** | **~700 new/rewritten, ~550 move+adapt** | |

**Note:** Previous estimates overstated `GardenReindexService` (42 LOC, not ~150) and `SearchProfileStore` (118 LOC, not ~170). The search orchestration LOC includes code already in neocortex rag-scoring. `ChainWalker` is a rewrite, not a move — Hortora types do not map to rag-api types.

### 4.2 What Stays Domain-Specific (becomes configuration)

| Hortora Engine Component | Disposition |
|--------------------------|------------|
| GardenMetadataExtractor | Becomes `CorpusType.KNOWLEDGE_GARDEN` frontmatter definition + generic `CoverDocumentParser` |
| GardenMcpTools | MCP tools are a deployment concern — Hortora deployment configures its own tools over `corpus-management-api` |
| GardenConfig, CDI producers | Deployment configuration — which corpus type, which Qdrant instance, which federation chain |
| Outcome recording wiring | Generic via `CorpusEntryStore` + `CbrOutcome` integration in `corpus-management` |

### 4.3 End State

Hortora/engine becomes a deployment artifact: MCP tool definitions + domain configuration + startup that creates a `KNOWLEDGE_GARDEN` corpus with the appropriate upstream/peer federation chain. Zero engine-specific business logic. All search, federation, provenance, staleness, and feedback logic lives in neocortex `corpus-management`.

---

## 5. Transcript Corpus (#764)

**Dependency:** casehubio/neocortex#761 (provenance links from memory nodes to transcript ZIP coordinates). Transcript covers MUST reference their source transcript via `artifactRef` — this is the link back to the full exchange for reconstructive recall.

### 5.0 Relationship to ConversationBridge and MindMap

`ConversationBridge` (mindmap-intelligence) and the transcript corpus serve complementary purposes:

| | ConversationBridge (MindMap nodes) | Transcript Corpus (cover documents) |
|---|---|---|
| **Stores** | Semantic interpretation — what the interaction *meant* | Factual brief — what was *said* and *done* |
| **Format** | `MindMapNode` with typed fields (confidence, PAD values, properties) | Cover document (markdown + YAML frontmatter) in Qdrant |
| **Search model** | Graph traversal, salience scoring, consolidation-driven retrieval | Vector search with metadata filters (interaction_type, activity_type, domain) |
| **Use case** | "What does the agent understand about X?" | "Show me all design discussions about X from last month" |
| **Lifecycle** | Subject to MindMap consolidation (merge, community summary, decay) | Append-only factual record, subject to re-labelling only |

These are not duplicates — they represent different retrieval needs from #764: "What was said → brief", "What it meant → MindMap node", "Show me the full exchange → ZIP coordinates → raw transcript."

### 5.1 Auto-Creation

A single `TRANSCRIPT` corpus is auto-created per agent. CDI observer on agent lifecycle events:

```java
@ApplicationScoped
public class TranscriptCorpusInitializer {

    // corpus-management does NOT depend on agency at compile time.
    // AgentCreated is observed via CDI's dynamic observer mechanism —
    // if the agency module is not deployed, this observer never fires.
    // The @Observes annotation with reception=IF_EXISTS ensures no
    // hard dependency on the event type.
    void onAgentCreated(@Observes(reception = Reception.IF_EXISTS)
                        AgentCreated event, CorpusManager manager) {
        manager.create(
            event.agentId() + "-interactions",
            CorpusType.TRANSCRIPT,
            event.tenantId(),
            List.of(),
            List.of(),
            Map.of("agent_id", event.agentId())
        );
    }

    // Lazy fallback: when the first transcript entry is recorded for an
    // agent that has no transcript corpus, CorpusEntryStore detects the
    // missing corpus and creates it on demand. The detection point is
    // CoverDocumentGenerator.generateTranscriptCover() — if the agent's
    // transcript CorpusRef is not found in the catalogue, it triggers
    // CorpusManager.create() before proceeding with the add.
}
```

### 5.2 Cover Generation

Every interaction (tick, query, tool call, reflection) gets a cover document generated mechanically:

1. **Extract metadata** from the interaction context: interaction type (agent-agent, agent-human, tool-use, self-reflection), activity type (research, implementation, debugging, design), domain/project labels, participants, turn count.

2. **Generate brief** — mechanical extraction, ~100-200 tokens. V1: structured response field extraction (no LLM needed). Key: what was asked, what was answered, what changed.

3. **Write cover** — markdown+YAML in the standard format, filed into the agent's transcript corpus. `artifactRef` is **required** for TRANSCRIPT entries — it carries the ZIP corpus coordinate (`corpus://<corpus-name>/transcripts/<zip-entry-path>`) linking back to the full exchange for reconstructive recall (#761).

4. **Cross-reference MindMap nodes** — if the interaction produced MindMap mutations (via ConversationBridge or MindMapExtractor), link the cover to the affected node IDs via `related_nodes` frontmatter. This is a bidirectional linkage: the MindMap node carries semantic meaning, the transcript cover carries the factual record. The `related_nodes` field enables navigation from "what was said" to "what it meant" and vice versa.

### 5.3 Labels and Retrospective Re-labelling

Labels (interaction_type, activity_type, domain) are assigned at write time from context.

**Re-labelling mechanism:** Re-labelling is triggered by MindMap consolidation, not by a separate corpus-level process. When a `ConsolidationPhase` updates a MindMap node's properties (e.g., domain re-classification), and that node has associated transcript entries (discoverable via `related_nodes` cross-reference), the consolidation phase fires a `CorpusRelabelRequested` CDI event carrying the node ID and updated labels. A `CorpusRelabelObserver` in corpus-management processes these events, updating the frontmatter of linked transcript covers and re-embedding the affected entries.

```java
// Lives in cognitive-api — both mindmap-intelligence and corpus-management-api
// already depend on cognitive-api, so no new cross-module dependency is introduced.
package io.casehub.neocortex.cognitive;

public record CorpusRelabelRequested(
    String nodeId, String tenantId,
    Map<String, Object> updatedLabels
) {}

// Observer in corpus-management
void onRelabel(@ObservesAsync CorpusRelabelRequested event,
               CorpusEntryStore store, CorpusCatalogue catalogue) {
    // Find all transcript entries with related_nodes containing event.nodeId()
    // Update their frontmatter labels
    // Re-embed affected entries
}
```

### 5.4 Retrieval

The transcript corpus is searchable like any other corpus:

- "Show me all design discussions about memory architecture from last month" → text search + `activity_type: design-discussion` filter + temporal range
- "When did I last discuss attention mechanisms?" → text search, sorted by recency
- "What did I say about CAPS topology changes?" → text search across the agent's full interaction history
- "Show me the full exchange" → retrieve transcript cover → follow `artifactRef` to ZIP coordinates → reconstruct full transcript via `CorpusStore` (#761)

---

## 6. Cognitive Pipeline Integration

### 6.1 CognitiveMemoryRetriever Extension

`CognitiveMemoryRetriever` (#750) gains corpus search alongside its existing memory search. The existing API returns `List<Memory>` (re-ordered by modulation) — the corpus extension follows the same pattern:

```java
public class CognitiveMemoryRetriever {

    // Existing: modulated memory retrieval — returns List<Memory>
    public List<Memory> query(MemoryQuery query, ModulationContext context);

    // New: modulated corpus search — returns List<CorpusSearchResult>
    public List<CorpusSearchResult> queryCorpora(
        CorpusQuery query, String tenantId, ModulationContext context);
}
```

**Modulation for corpus results:** `CorpusSearchResult` carries `entryTimestamp` (extracted from cover frontmatter at search time) but does NOT carry PAD emotional dimensions (pleasure, arousal, dominance) or typed `Confidence` — these are properties of cognitive artifacts (Memory, MindMapNode), not document metadata. A `ModulationProfile<CorpusSearchResult>` is defined with:
- `timestamp` → `CorpusSearchResult::entryTimestamp`
- `confidence` → neutral `Confidence.stated()` default (all corpus entries are equally trusted at the search layer — source-level trust is a future concern)
- `pleasure`, `arousal`, `dominance` → neutral 0.0 defaults (PAD dimensions don't apply to documents)

This means only **recency decay** and **goal relevance** modulation factors produce meaningful differentiation for corpus results. PAD-based mood congruence passes through as a no-op (neutral defaults produce uniform multipliers). This is correct — documents don't have emotional dimensions, and forcing them would produce meaningless modulation.

```java
public final class ModulationProfiles {
    // Existing
    public static final ModulationProfile<Memory> MEMORY = ...;
    public static final ModulationProfile<MindMapNode> NODE = ...;

    // New: corpus results — neutral defaults for inapplicable dimensions
    public static final ModulationProfile<CorpusSearchResult> CORPUS = new ModulationProfile<>(
        r -> Confidence.stated(),
        r -> 0.0,  // pleasure — neutral
        r -> 0.0,  // arousal — neutral
        r -> 0.0,  // dominance — neutral
        CorpusSearchResult::entryTimestamp
    );
}
```

### 6.2 CorpusEntry → MindMap Promotion

The design principle "Promotion from corpus to MindMap is explicit" is implemented via `CorpusEntryPromoter`:

```java
@ApplicationScoped
public class CorpusEntryPromoter {

    public PromotionResult promote(CorpusRef corpus, String entryId,
                                    String targetSubgraphId, String tenantId) {
        // 1. Retrieve the corpus entry
        // 2. Extract title, body, domain from cover frontmatter
        // 3. Create a MindMapNode in the target subgraph via MindMapStore.addNode()
        //    - title from cover title
        //    - body from cover body
        //    - provenance: "corpus-promotion"
        //    - NodeRef linking back to the corpus entry:
        //      new NodeRef("corpus", entryId, corpus.corpusName())
        // 4. Update corpus entry frontmatter with promoted_to: <nodeId>
        // 5. Return PromotionResult(nodeId, isNew)
    }
}
```

The promotion path is:
- `CorpusEntry` identity: `CE-YYYYMMDD-XXXXXX`
- `MindMapNode` identity: UUID-based `Subject(type, id)`
- Bridge: `NodeRef(scheme="corpus", id=entryId, qualifier=corpusName)` on the MindMapNode links back to the corpus entry. `promoted_to` frontmatter on the corpus entry links forward to the node.

This uses the same `NodeRef` mechanism that `EntityPromoter` uses for spatial cache → MindMap promotion (where `EntityPromoter` creates `new NodeRef(entity.source(), entity.externalId(), null)`). The identity models are different by design (corpus entries are document-scoped, MindMap nodes are graph-scoped) — the cross-reference is the bridge. The `qualifier` field carries the corpus name for disambiguation when multiple corpora contain entries with the same ID scheme.

### 6.3 Corpus as Prompt Section

A new `CognitionPromptRenderer` — `CorpusKnowledgePromptSection` — retrieves relevant corpus entries during the cognitive tick and injects them into the prompt:

```
## Relevant Knowledge

From your research corpus (memory consolidation review):
- Walker (2005): Sleep consolidation operates in two stages — SWS
  stabilisation followed by REM integration [CE-20261102-a1b2c3]

From operational knowledge (platform garden):
- SmallRye @ConfigMapping interfaces cannot share defaults across
  profiles — use per-profile overrides [GE-20261005-ff25d1]
```

### 6.4 Anticipatory Corpus Creation

The curiosity drive system can trigger corpus creation:

```java
@ApplicationScoped
public class CuriosityCorpusCreator {

    void onCuriositySignal(@Observes AttentionSignal signal, CorpusManager manager) {
        if (signal.category() == SignalCategory.DRIVE_SHIFT
            && signal.significance() > CORPUS_CREATION_THRESHOLD) {
            // Agent's curiosity about a topic has crossed the threshold
            // Create a research corpus to start accumulating knowledge
            manager.create(...);
        }
    }
}
```

---

## 7. Cross-Corpus Search

### 7.1 Search Flow

```
1. Query arrives (text + filters + corpus scope)
2. Catalogue lookup: resolve search scope
   - Explicit corpus IDs from query, OR
   - All ACTIVE corpora for tenant (default), OR
   - Federation graph walk from a starting corpus
3. Per-corpus search (parallel):
   - Hybrid search: dense + sparse + BM25 via CaseRetriever
   - Post-retrieval scoring: temporal decay, version scoring
   - Adaptive filter: score floor, gap trim
4. Cross-corpus fusion:
   - RRF merge with per-corpus weights (ScoreFusion)
   - Dedup by entry ID across corpora (keep highest-scoring)
   - Override resolution (child entry supersedes parent)
5. Cognitive modulation (when in tick context):
   - Recency decay, confidence weight, mood congruence, goal relevance
   - Via CognitiveMemoryRetriever extension
6. Return ranked CorpusSearchResult list with source corpus attribution
```

### 7.2 Federation Depth Control

`CorpusQuery.federationDepth` controls how far upstream the search walks:
- `0` — own corpus only
- `1` — own + immediate upstream
- `N` — walk N levels up
- `-1` — unlimited (walk entire chain)

Peers are always searched at depth 0 from the starting corpus (no transitive peer walking — peers of peers are not included unless explicitly configured).

---

## 8. Lifecycle

### 8.1 Creation

| Trigger | Corpus type | Mechanism |
|---------|-------------|-----------|
| Agent creation | TRANSCRIPT | CDI observer on `AgentCreated` (or lazy fallback) |
| Research session start | RESEARCH | `ResearchOrchestrator.create()` — see below |
| LLM tool call | Any | Explicit via `CorpusManager.create()` |
| Curiosity signal | RESEARCH | CDI observer on `AttentionSignal` (anticipatory) |

Creation allocates: Qdrant collection + catalogue entry + optional artifact storage directory.

**ResearchOrchestrator integration:**

`ResearchOrchestrator.create()` currently creates a MindMap subgraph + session record. It gains corpus creation as part of this epic:

```java
@Override
public ResearchSession create(String name, String criteria, String tenantId) {
    // Existing: create MindMap subgraph
    String subgraphId = mindMapStore.createSubgraph(...);
    String rootNodeId = mindMapStore.addNode(...);

    // New: create a RESEARCH corpus for this session
    CorpusDescriptor corpus = corpusManager.create(
        name + "-research",
        CorpusType.RESEARCH,
        tenantId,
        List.of(),  // upstream — configurable per session
        List.of(),  // peers — configurable per session
        Map.of("research_session_id", session.id(),
               "mindmap_subgraph_id", subgraphId)
    );

    // Session record now carries the corpus ref
    ResearchSession session = new ResearchSession(
        ..., subgraphId, corpus.corpusRef(), ...);
    sessionStore.insert(session);
    return session;
}
```

**Session lifecycle → corpus lifecycle:**

| Session state | Corpus action |
|---|---|
| `ACTIVE` | Corpus is `ACTIVE` — entries can be added |
| `PAUSED` | Corpus remains `ACTIVE` but stops accepting auto-generated entries. Manual adds still permitted. |
| `COMPLETED` | Corpus archived via `CorpusManager.archive()`. Still queryable on explicit request. |

The `ResearchSession` record gains a `CorpusRef corpusRef` field. `ResearchOrchestrator.pause()`, `resume()`, and `complete()` manage the corpus lifecycle alongside the existing session state transitions. No new CDI events are needed — the orchestrator directly calls `CorpusManager`.

### 8.2 Population

Entries are added via `CorpusEntryStore.add()`. The flow:
1. Caller provides: cover document (markdown+YAML) + optional original artifact (byte stream)
2. `CoverDocumentParser` validates frontmatter against `CorpusType` requirements
3. Original artifact stored in `CorpusStore` (ZIP) → artifact ref returned
4. Cover document embedded (dense + sparse + BM25) → stored in Qdrant
5. Provenance recorded if provenance context is available

For transcript entries, `CoverDocumentGenerator` produces the cover mechanically from the interaction record.

### 8.3 Search

See §7 above.

### 8.4 Evolution

- **Staleness detection:** Cover documents carry `staleness_threshold` in frontmatter (typed as `FieldSchema.DURATION`). Background process checks entry age against threshold and flags stale entries.
- **Reindexing:** When covers are updated (new annotations, revised summary), the Qdrant record is re-embedded. Full reindex (delete collection + re-embed all) available for schema changes.
- **Retrospective re-labelling:** Triggered by MindMap consolidation, not by a standalone corpus process. When a `ConsolidationPhase` (e.g., `ExperienceConsolidationPhase`) re-classifies a MindMap node, and that node has linked transcript corpus entries (via `related_nodes` cross-reference), a `CorpusRelabelRequested` CDI event is fired. The `CorpusRelabelObserver` in corpus-management updates the affected entries' frontmatter labels and re-embeds them. See §5.3 for the concrete mechanism.

### 8.5 Archival

- `archive(corpus)` — sets lifecycle to ARCHIVED. Stops accepting new entries. Drops from default cross-corpus search. Qdrant collection retained (queryable on explicit request).
- `revive(corpus)` — sets lifecycle back to ACTIVE. Re-includes in default search.
- Hard deletion available but discouraged — archived corpora are cheap to keep.

---

## 9. Implementation Plan (Outline)

### Phase 1: Core SPI + Catalogue

- `corpus-management-api` module: all SPIs and value types
- `corpus-management` module: `SqliteCorpusCatalogue`, `QdrantCorpusEntryStore`, `CorpusManagerImpl`
- `CoverDocumentParser` (markdown+YAML → CorpusEntry)
- Contract tests for catalogue and entry store

### Phase 2: Search + Federation

- Single-corpus search via `CaseRetriever`
- Cross-corpus RRF fusion via `ScoreFusion`
- ChainWalker federation (migrate from Hortora)
- Search orchestration (overfetch → score → filter → federate)
- ProvenanceStore (migrate from Hortora)

### Phase 3: Hortora Absorption

- Migrate remaining Hortora engine capabilities: search profiles, reindexing, collection migration
- Configure Hortora as `CorpusType.KNOWLEDGE_GARDEN` deployment
- Verify existing Hortora functionality works via corpus-management

### Phase 4: Transcript Corpus (#764)

- `CorpusType.TRANSCRIPT` definition
- `TranscriptCorpusInitializer` (auto-creation)
- `CoverDocumentGenerator` for transcripts (mechanical brief generation)
- Label assignment from interaction context
- Integration with existing interaction recording pipeline

### Phase 5: Cognitive Integration

- `CognitiveMemoryRetriever` extension for corpus search
- `CorpusKnowledgePromptSection` prompt renderer
- Anticipatory corpus creation via curiosity signals
- Retrospective re-labelling via consolidation

---

## References

- casehubio/neocortex#763 — Epic: Autonomous cognitive knowledge management
- casehubio/neocortex#764 — Transcript-indexed episodic retrieval
- casehubio/neocortex#751 — RAG-layer retrieval modulation
- casehubio/neocortex#750 — CognitiveMemoryRetriever (landed)
- casehubio/neocortex#304 — Knowledge garden platform extraction spec
- Hortora engine architecture — reference implementation for all garden capabilities
- Hortora spec: four-level knowledge methodology (canonical → community → platform → product)
- `/Users/mdproctor/claude/casehub/slots/221/wsp-casehub-neocortex/specs/2026-10-05-knowledge-pipeline-phase-3-rnd.md` — Phase 3 R&D (dimensional memory, task briefs, persistent RAG)
- `/Users/mdproctor/claude/casehub/slots/221/wsp-casehub-neocortex/specs/issue-285-knowledge-repr-model/2026-09-09-knowledge-repr-model-design.md` — Thing/MindMapNode hierarchy
- `/Users/mdproctor/claude/casehub/slots/221/wsp-casehub-neocortex/specs/issue-295-knowledge-consolidation/2026-09-10-knowledge-consolidation-pipeline-design.md` — Consolidation pipeline
- fusion-api `ScoreFusion` — RRF/CC fusion algorithms
- rag-api `FederationStrategy` — federation SPI (already in neocortex)
- rag-api `ProvenanceTracker` — provenance SPI (already in neocortex)
- rag-scoring `AdaptiveSearchWrapper` — adaptive search (already in neocortex)

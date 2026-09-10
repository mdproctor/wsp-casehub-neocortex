# Knowledge Garden Platform Extraction — Design Spec

**Date:** 2026-09-10
**Issue:** casehubio/neocortex#304
**Cross-ref:** Hortora/engine#90
**Status:** Draft

---

## 1. Problem Statement

Hortora/engine's ~3.5K LOC is mostly generic RAG application logic — adaptive search, post-retrieval scoring, provenance tracking, collection migration, query augmentation, and federation. This code was built in engine first but isn't garden-specific. A second consumer (casehub issue resolution garden) is emerging, making this the right time to extract reusable capabilities into neocortex.

### 1.1 Current State

Engine sits on top of neocortex and adds six capability layers:

| Capability | Engine LOC | Generic? |
|---|---|---|
| Adaptive search (score floor, gap trim, overfetch) | ~570 | Yes |
| Post-retrieval scoring (temporal decay, version distance) | ~117 | Yes |
| Search profiles (BOM snapshots) | ~173 | Yes |
| Provenance tracking (document→decision lineage) | ~292 | Yes |
| Collection migration (dim/sparse/ColBERT checks) | ~186 | Partially |
| Query augmentation (LLM-generated search queries at ingest) | ~308 | Partially |
| Federation (recursive multi-garden search) | ~404 | Yes |
| MCP tools, deployment wiring, config | ~1,062 | No |

Neocortex already provides the foundational SPIs that engine builds on: `CaseRetriever`, `RetrievalTracker`, `MetadataExtractor`, `EmbeddingIngestor`, and the full decorator chain (CRAG, reranking, expansion, tracking, payload boost).

### 1.2 Goal

Extract platform-grade SPIs into neocortex. Move implementations that are genuinely generic. Leave domain-specific implementations in engine until a second consumer validates the SPI boundaries. Engine becomes a thin deployment artifact.

### 1.3 Design Principles

- **SPI first, impl second.** Define the right abstraction in rag-api. Leave the implementation in engine until a second consumer proves the SPI is correct.
- **Don't embed domain semantics.** Engine's ProvenanceStore has `issueRepo`, `issueNumber`, `specName` columns. The platform SPI must use generic parameters.
- **Respect existing patterns.** New modules follow the rag-* pattern (rag-api for SPI, separate module for impl). Decorators are for pipeline transformations, not routing.
- **Two feedback axes stay separate.** Retrieval relevance (was this the right document?) stays on `RetrievalTracker`. Execution outcome (did it work?) stays on `CbrCaseMemoryStore.recordOutcome()`. They score different things.

## 2. Architecture

### 2.1 New SPIs in rag-api

#### PostRetrievalScorer

Composable score multiplier applied after retrieval, before result presentation. Each scorer adjusts a chunk's relevance score based on metadata.

```java
package io.casehub.neocortex.rag;

public interface PostRetrievalScorer {
    double adjust(RetrievedChunk chunk, RetrievalQuery query, ScoringContext context);
}
```

`ScoringContext` carries the scoring parameters (BOM/profile for version scoring, current time for temporal decay). Scorers compose by multiplication — a chunk's final score is `baseScore * scorer1.adjust() * scorer2.adjust()`.

#### ProvenanceTracker

Document-to-action lineage tracking. Records which retrieved documents informed which downstream actions.

```java
package io.casehub.neocortex.rag;

public interface ProvenanceTracker {
    String record(String retrievalContext, String actionId, String actionType,
                  List<String> documentIds, String recordedBy);
    List<ProvenanceRecord> forwardLineage(String actionId, String actionType);
    List<ProvenanceRecord> reverseLineage(String documentId);
    ProvenanceStats stats(String retrievalContext);
    int purgeOlderThan(Instant cutoff);
}
```

Parameters are deliberately generic. Hortora maps: `retrievalContext` → issueRepo, `actionId` → issueNumber, `actionType` → "github-issue", `documentIds` → GE-IDs. A casehub issue garden would map: `actionId` → caseId, `actionType` → "case-resolution".

`ProvenanceRecord` is a record with `id`, `retrievalContext`, `actionId`, `actionType`, `documentId`, `recordedBy`, `timestamp`.

`ProvenanceStats` carries per-document retrieval counts for unretrieved-document detection.

#### FederationStrategy

Topology discovery, remote query, and result merge for multi-instance retrieval.

```java
package io.casehub.neocortex.rag;

public interface FederationStrategy {
    List<FederationTarget> discoverTargets(String localId);
    List<FederatedResult> query(FederationTarget target, String queryText,
                                int maxResults, Set<String> visited);
    List<FederatedResult> merge(List<FederatedResult> local,
                                 List<List<FederatedResult>> remote);
}
```

Federation operates at the REST/HTTP service-to-service level, NOT the CaseRetriever pipeline level. Federated results do NOT pass through the local decorator chain (CRAG, expansion, reranking, tracking) — each instance processes its own results independently. Merging happens after both local and remote results are fully processed.

`FederationTarget` carries the remote instance URL, ID, and relationship (upstream/peer). `FederatedResult` carries the result content, score, and source instance ID.

`visited` parameter enables loop detection — each query carries the set of instance IDs already visited in the chain.

Engine's `ChainWalker` stays as the first `FederationStrategy` implementation: sequential upstream walk + parallel peer fan-out + tiered merge + dedup + relevance-threshold short-circuit.

#### DocumentQueryAugmenter

LLM-generated search queries appended to documents at ingest time (inverted HyDE pattern).

```java
package io.casehub.neocortex.rag;

public interface DocumentQueryAugmenter {
    Optional<List<String>> generateQueries(String title, String body, String path);
}
```

Distinct from `QueryExpander` which operates at query time. `DocumentQueryAugmenter` enriches documents BEFORE embedding so that the embedding captures the kinds of queries the document answers.

Returns `Optional.empty()` when augmentation is not applicable (too short, binary content, etc.). Returns `Optional.of(List.of())` when applicable but no queries generated.

### 2.2 New Modules

#### rag-scoring

PostRetrievalScorer implementations. Pure Java, zero external deps beyond rag-api.

| Class | What it does |
|---|---|
| `TemporalDecayScorer` | Exponential half-life decay by metadata tier. Configurable tier→halflife mapping. |
| `VersionScorer` | Version-distance decay. Major version miss penalizes more than minor. Configurable format. |
| `AdaptiveSearchWrapper` | Wraps CaseRetriever with overfetch, score floor, gap trim, and minimum results. Not a decorator — a utility that consumers call explicitly. |

Adaptive search is a separate concern from scoring. Scoring computes per-chunk adjustments; adaptive search applies thresholds and trimming to the result set. `AdaptiveSearchWrapper` takes a `CaseRetriever`, a `List<PostRetrievalScorer>`, and an `AdaptiveSearchConfig`, then executes: retrieve (with overfetch) → score → floor → gap-trim → min-results guarantee.

`AdaptiveSearchConfig` record in rag-api:

```java
public record AdaptiveSearchConfig(
    double scoreFloor,
    double gapThreshold,
    int minResults,
    double overfetchMultiplier
) {
    public static AdaptiveSearchConfig defaults() {
        return new AdaptiveSearchConfig(0.3, 0.15, 3, 2.0);
    }
}
```

#### rag-query-augmentation

DocumentQueryAugmenter implementation via platform's `AgentProvider`. Depends on rag-api + casehub-platform-agent-api.

| Class | What it does |
|---|---|
| `AgentQueryAugmenter` | Uses AgentProvider to get a ChatModel, prompts it to generate search queries for a document. Provider-agnostic — Ollama, OpenAI, or any other provider is configuration. |
| `QueryAugmentingMetadataExtractor` | `MetadataExtractor` @Decorator that appends generated queries to document content before the base extractor processes it. |

### 2.3 Extensions to Existing Modules

#### rag-api

New SPIs listed in 2.1. New records:

- `AdaptiveSearchConfig` — score floor, gap threshold, min results, overfetch multiplier
- `ProvenanceRecord` — lineage record
- `ProvenanceStats` — per-document retrieval counts
- `FederationTarget` — remote instance identity
- `FederatedResult` — result with source attribution
- `ScoringContext` — scoring parameters (time, BOM, custom)

#### rag

`CollectionCompatibility` utility alongside `QdrantEmbeddingIngestor`:

```java
public class CollectionCompatibility {
    public static MigrationAction check(QdrantClient client, String collectionName,
                                         CollectionExpectedConfig expected) { ... }
}
```

`MigrationAction` is a sealed interface: `Compatible`, `DimensionMismatch(int actual, int expected)`, `MissingSparseVectors`, `MissingColBert`. The check is generic — what to DO about incompatibility (reindex, recreate, abort) is a deployment policy decision left to the caller.

Engine keeps its deployment-specific wiring: `GardenConfig` injection, `CorpusRef("hortora", ...)` construction, and cursor management policy.

#### memory-api — CBR Rename

| Current | New | What it is |
|---|---|---|
| `PlanCbrCase` | `ResolvedCase` | Historical execution trace with agent routing data |
| `TextualCbrCase` | `ResolutionGuide` | Prose resolution guidance (problem→solution pairs) |
| `PlanItem` | `ResolutionStep` | A dispatched work unit within a trace |

Unified under the `Resolution` concept. A case store holds `ResolvedCase` entries (what happened) and `ResolutionGuide` entries (what to do). Both are retrievable, rankable, and feedbackable.

`CbrOutcome` gains an optional `retrievalId` field for correlation when lineage from retrieval to outcome is needed. This connects the execution outcome axis back to the retrieval that surfaced the case, without conflating the two feedback axes.

### 2.4 What Stays in Engine

| Component | Why it stays |
|---|---|
| `GardenMcpTools` (~652 LOC) | Application surface — MCP tool definitions with garden-specific descriptions. Thin delegation to platform services. |
| `GardenMetadataExtractor` (~145 LOC) | Implements neocortex `MetadataExtractor` SPI with garden-specific field names and GE-ID patterns. |
| `GardenOutcomeService` (~97 LOC) | JPA-coupled, uses garden-specific CASE_TYPE and tenant from GardenConfig. Bridges to `CbrCaseMemoryStore.recordOutcome()`. |
| `SearchProfileStore` (~118 LOC) | BOM snapshot store — stays until a second consumer needs profiles. |
| `ProvenanceStore` (~192 LOC) | Hortora-specific schema. Implements the new `ProvenanceTracker` SPI with domain parameter mapping. |
| `ChainWalker` (~184 LOC) | First `FederationStrategy` implementation. Stays until federation SPI is validated by a second consumer. |
| `ReconcileScheduler` (~29 LOC) | Thin delegation to existing neocortex `CorpusIngestionService`. |
| `GardenReindexService` (~42 LOC) | Thin delegation to existing neocortex `EmbeddingIngestor` + `CursorStore`. |
| Config, CDI producers (~215 LOC) | Deployment wiring. |

After extraction, engine's dependency on neocortex grows (new SPIs to implement), but engine's own code shrinks (scoring, migration checks, query augmentation SPI move out). Engine becomes: neocortex dep + config + MCP tools + federation + domain-specific SPI implementations.

## 3. Extraction Phases

Bottom-up: foundations before consumers. Each phase includes both sides — what enters neocortex AND what leaves engine.

### Phase 1 — Foundation SPIs

**Neocortex:**
- Add to rag-api: `PostRetrievalScorer`, `ScoringContext`, `ProvenanceTracker`, `ProvenanceRecord`, `ProvenanceStats`, `FederationStrategy`, `FederationTarget`, `FederatedResult`, `DocumentQueryAugmenter`, `AdaptiveSearchConfig`
- Create rag-scoring: `TemporalDecayScorer`, `VersionScorer`
- Create rag-query-augmentation: `AgentQueryAugmenter`, `QueryAugmentingMetadataExtractor`

**Engine:**
- `TemporalDecayScorer` → delete, depend on rag-scoring
- `VersionScorer` → delete, depend on rag-scoring
- `ProvenanceStore` → implement `ProvenanceTracker` SPI, keep domain-specific schema
- `ChainWalker` → implement `FederationStrategy` SPI, keep REST-level federation
- `QueryAugmentingExtractor` → implement `DocumentQueryAugmenter`, delegate to `AgentQueryAugmenter` or keep Ollama impl

### Phase 2 — Search Infrastructure

**Neocortex:**
- Add to rag-scoring: `AdaptiveSearchWrapper`
- Add to rag: `CollectionCompatibility`, `MigrationAction`

**Engine:**
- `SearchResource` → use `AdaptiveSearchWrapper` from rag-scoring. Keep federation orchestration and MCP-specific result formatting.
- `CollectionMigration` → extract generic checks to `CollectionCompatibility`. Keep deployment policy (reindex on incompatibility, cursor reset).

### Phase 3 — CBR Rename

**Neocortex:**
- memory-api: `PlanCbrCase` → `ResolvedCase`, `TextualCbrCase` → `ResolutionGuide`, `PlanItem` → `ResolutionStep`
- Add optional `retrievalId` to `CbrOutcome`
- Update all consumers across neocortex modules

**Engine:**
- Update all consumers of renamed types
- Update `GardenOutcomeService` to use new names

### Phase 4 — Engine Thinning

**Engine:**
- Strip any remaining extracted code
- Verify all MCP tools work against platform services
- Update engine's CLAUDE.md to reflect new architecture
- Verify Hortora/soredium skills continue working unchanged

## 4. Module Dependency Graph (Post-Extraction)

```
rag-api (SPIs: CaseRetriever, RetrievalTracker, MetadataExtractor,
         PostRetrievalScorer, ProvenanceTracker, FederationStrategy,
         DocumentQueryAugmenter, AdaptiveSearchConfig, ...)
    ↑
    ├── rag-scoring (TemporalDecayScorer, VersionScorer, AdaptiveSearchWrapper)
    ├── rag-query-augmentation (AgentQueryAugmenter, QueryAugmentingMetadataExtractor)
    ├── rag-crossencoder (CRAG, reranking)
    ├── rag-expansion (HyDE, step-back, multi-query)
    ├── rag-tracking (retrieval event tracking, outcome storage)
    ├── rag (HybridCaseRetriever, QdrantEmbeddingIngestor, CollectionCompatibility)
    └── ... (existing modules unchanged)

memory-api (CbrCaseMemoryStore, ResolvedCase, ResolutionGuide,
            CbrOutcome with optional retrievalId, ...)
    ↑
    └── ... (existing memory modules unchanged)

Engine (deployment artifact)
    ├── depends on: rag-api, rag-scoring, rag-query-augmentation, memory-api, ...
    ├── implements: ProvenanceTracker, FederationStrategy, MetadataExtractor
    └── owns: MCP tools, config, CDI producers, deployment scripts
```

## 5. Two-Axis Feedback Model

Engine#90 identifies two feedback axes. The extraction preserves them as separate platform concepts:

**Axis 1 — Retrieval relevance:** "Was this the right document for this query?"
- SPI: `RetrievalTracker.feedback(retrievalId, docId, RetrievalOutcome)`
- Scope: scores the SEARCH, not the content
- Timing: immediately after retrieval or shortly after
- Location: rag-api / rag-tracking

**Axis 2 — Execution outcome:** "When we followed this guidance, did it work?"
- SPI: `CbrCaseMemoryStore.recordOutcome(caseId, CbrOutcome)`
- Scope: scores the CONTENT, not the search
- Timing: much later, after execution
- Location: memory-api / memory backends
- Correlation: `CbrOutcome.retrievalId` (optional) links back to the retrieval event

Both feed back into future retrievals but through different paths: retrieval relevance adjusts ranking for similar queries (via `RetrievalAnalyzer`), execution outcome adjusts confidence on the case itself (via EMA in `CbrCaseMemoryStore`).

## 6. Migration Strategy

### Backward Compatibility

Engine must continue working during incremental extraction. Strategy:

1. **New neocortex SPIs are @DefaultBean no-ops.** Engine doesn't break if it doesn't implement them immediately.
2. **Engine implements SPIs incrementally.** Each phase: add neocortex dep → implement SPI → delete extracted code → verify.
3. **CBR rename uses deprecation bridge.** Old names become `@Deprecated` type aliases pointing to new names. Consumers migrate at their own pace. Remove aliases after one release cycle.

### Testing

Each phase includes:
- Contract tests for new SPIs in rag-testing / memory-testing
- Engine integration tests verify MCP tools still work
- Soredium skill tests verify garden tools still produce correct results

## 7. Test Strategy

| Module | What's tested |
|---|---|
| rag-api | SPI contracts (default methods, record validation) |
| rag-scoring | TemporalDecayScorer (half-life math, tier mapping), VersionScorer (version distance, major/minor), AdaptiveSearchWrapper (floor, gap, min results, overfetch) |
| rag-query-augmentation | AgentQueryAugmenter (prompt construction, empty/null handling), QueryAugmentingMetadataExtractor (decorator composition) |
| rag | CollectionCompatibility (dimension mismatch, sparse check, ColBERT check) |
| memory-api | CBR rename compilation, CbrOutcome.retrievalId round-trip |
| memory-testing | Updated contract tests for renamed types |
| engine | Integration tests: MCP tools → platform SPIs → correct results |

## 8. Deferred Review Items

Three items were raised during decision review and consciously deferred:

1. **CBR rename scope creep risk** (R1-09): Bundling the rename with extraction increases scope. Accepted trade-off — the rename touches memory-api which is already being modified for CbrOutcome.retrievalId.

2. **Bottom-up ordering delays highest-value capability** (R1-10): Adaptive search (Phase 2) is the most impactful extraction but requires scoring SPIs (Phase 1) first. Accepted — foundations before consumers prevents rework.

3. **SPI proliferation with single consumer** (R1-12): Four new SPIs (PostRetrievalScorer, ProvenanceTracker, FederationStrategy, DocumentQueryAugmenter) each currently have one consumer. Accepted — pre-release platform, and the casehub issue resolution garden is the imminent second consumer.

## References

- casehubio/neocortex#304 — extraction issue (neocortex side)
- Hortora/engine#90 — extraction issue (engine side, detailed design context)
- `RetrievalTracker.java` (rag-api) — existing retrieval feedback SPI
- `CaseRetriever.java` (rag-api) — existing retrieval SPI
- `MetadataExtractor.java` (rag-api) — existing metadata extraction SPI
- `CbrCaseMemoryStore.java` (memory-api) — existing outcome recording
- `RetrievalAnalyzer.java` (rag-api) — retrieval analysis utilities
- Engine source survey (fork agent, 2026-09-10) — LOC breakdown and generic-vs-specific classification
- GE-20260513-4f26a7 — @DefaultBean + @ApplicationScoped CDI layer displacement
- casehub/garden/docs/protocols/universal/spi-adapter-module-placement.md — SPI adapters start in host repo
- casehub/garden/docs/protocols/universal/cdi-classpath-presence-requires-module-separation.md — classpath activation pattern
- casehub/garden/docs/protocols/universal/module-tier-structure.md — three-tier module structure

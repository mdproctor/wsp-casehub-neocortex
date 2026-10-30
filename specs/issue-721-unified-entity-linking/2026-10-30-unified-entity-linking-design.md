# Design: Unified Entity Linking — Bridge Text Corpus and Knowledge Graph via Standoff Annotation

**Issue:** casehubio/neocortex#721
**Date:** 2026-10-30
**Status:** Draft

## Problem

Three disconnected linking mechanisms exist today:

1. **MindMap nodes** — entities as graph nodes with typed relationships (edges)
2. **Text embedding similarity** — memory retrieval by vector proximity (fuzzy, misses pronouns)
3. **Subgraph membership** — nodes grouped by cognitive subgraph

These are disconnected. Text search doesn't know about graph structure. Graph queries don't reach into prose. Pronoun references ("he gave her the thing") are invisible to both.

**Consequence:** "What do I know about James?" requires vector similarity search, which misses pronoun references, definite descriptions ("the detective"), and implicit mentions. Entity-aware cognitive operations (salience, reflection, belief revision, Theory of Mind) are impossible without a text-to-entity bridge.

## Solution: Standoff Annotations

A parallel structure of `(text span → entity node ID)` mappings that bridge unstructured text and the structured knowledge graph:

```
Text:  "James examined the guest book. He opened it carefully."
Spans: [{0,5,"James",node:pp}, {19,29,"guest book",node:obj-7}, 
        {31,33,"He",node:pp}, {41,43,"it",node:obj-7}]
```

Text stays clean — no inline artifacts. Annotations are a separate index. Every text source (memories, MindMap node bodies, biography YAML, conversation turns) can carry entity annotations. Every cognitive subsystem that reads text or queries the graph benefits.

### What entity-grounded prose enables

| Query | Today (text search) | With entity grounding |
|-------|--------------------|-----------------------|
| "What do I know about the key?" | Vector similarity, misses pronoun refs | `findByEntity(vaultKeyNodeId)` — exact, complete |
| "What happened between Clara and James?" | Keyword search, misses "he", "she" | `findByEntityPair(claraId, jamesId)` — all co-occurrences |
| "Who has interacted with this object?" | Can't query reliably | All spans linked to object node, grouped by co-occurring entities |
| "What does Clara believe about James?" | Belief text search | Belief memories with annotations linking to James's node |

## Architecture

```
Text corpus (memories, beliefs, reflections, formation memories, conversation turns)
    ↕ standoff spans (EntityAnnotationIndex)
MindMap knowledge graph (people, objects, rooms, concepts)
    ↕ typed edges
Cognitive subsystems (salience, reflection, belief revision, ToM)
```

The annotation index is the bridge between unstructured text and structured knowledge.

**Coupling model:** CDI events for lifecycle notifications (annotation created, entity merged, memory erased). Direct SPI for queries (findByEntity, findBySource). Events notify that state changed; the SPI answers questions about current state.

## Core Data Model

```java
public record EntityAnnotation(
    String annotationId,       // UUID
    String tenantId,
    String sourceType,         // "memory" | "mindmap-node" | "biography" | "conversation-turn"
    String sourceId,           // opaque — memory ID, node ID, passage ID, etc.
    String entityNodeId,       // opaque MindMap node ID
    int startOffset,           // inclusive, 0-based character position in source text
    int endOffset,             // exclusive
    String mentionText,        // surface form: "he", "the detective", "James"
    Double confidence,         // optional, 0.0–1.0, producer-assigned
    String method,             // "manual" | "llm-extraction" | "yaml-anchor"
    String ownerSubjectId,     // nullable — Subject.id() of memory owner, for lifecycle deletion
    Instant createdAt
) {}
```

### Coreference model: flat

Every annotation points directly to `entityNodeId`. No chain concept — the coreference chain IS the set of annotations sharing the same `entityNodeId` within a source document. Chain reconstruction is `GROUP BY entityNodeId WHERE sourceId = X`.

**Trade-off:** Loses discourse structure (which pronoun refers to which antecedent). Acceptable — the use cases are entity-centric, not discourse-centric.

### Text source identity

Annotations use a `(sourceType: String, sourceId: String)` pair owned by annotation-api. Source types are well-known strings. Source IDs are opaque — the annotation index stores and indexes them without resolving them.

| sourceType | sourceId | Example |
|------------|----------|---------|
| `memory` | memory ID (UUID) | Experience, belief, reflection memories |
| `mindmap-node` | node ID (UUID) | MindMap node body properties |
| `biography` | passage ID | Biography YAML passages |
| `conversation-turn` | turn ID | Runtime conversation segments |

### Annotation confidence

Optional score (0.0–1.0), producer-assigned:
- Authored YAML anchors: 1.0 (human-authored, correct by definition)
- LLM named entity mentions: high (0.9+)
- LLM pronoun coreference: varies by antecedent ambiguity
- Downstream consumers (salience, reflection, belief revision, ToM) can weight by confidence

### Correctability

Annotations are immutable. Correction is delete + re-create. Re-extraction produces fresh annotations with corrected links. No versioning, no optimistic locking.

### Tenancy

Tenant-scoped per platform protocol. Every annotation carries `tenantId`. All SPI query methods require `tenantId`. The SQLite store enforces tenant isolation unconditionally.

## SPI: EntityAnnotationIndex

```java
// annotation-api (Tier 1, pure Java, zero CDI, no mindmap-api dependency)

public interface EntityAnnotationIndex {

    // --- Write ---
    String addAnnotation(EntityAnnotation annotation);
    List<String> addAnnotations(List<EntityAnnotation> annotations);
    void removeAnnotation(String annotationId, String tenantId);
    void removeBySource(String sourceType, String sourceId, String tenantId);
    void removeByOwnerSubject(String sourceType, String ownerSubjectId, String tenantId);

    // --- Repoint (merge support) ---
    int repointEntity(String fromEntityNodeId, String toEntityNodeId, String tenantId);

    // --- Query: entity → text (primary direction) ---
    List<EntityAnnotation> findByEntity(String entityNodeId, String tenantId);

    // Returns annotations from source documents that mention BOTH entities.
    // Same-document constraint: only returns annotations from (sourceType, sourceId) pairs
    // where both entityNodeId1 and entityNodeId2 have at least one annotation.
    List<EntityAnnotation> findByEntityPair(String entityNodeId1, String entityNodeId2, String tenantId);

    List<EntityAnnotation> findByEntities(Set<String> entityNodeIds, String tenantId);

    // --- Query: text → entity (secondary direction) ---
    List<EntityAnnotation> findBySource(String sourceType, String sourceId, String tenantId);

    // --- Aggregate ---
    Set<String> distinctEntitiesInSource(String sourceType, String sourceId, String tenantId);
    Map<String, Long> entityMentionCounts(String tenantId);
}
```

**Dependency boundary:** annotation-api does NOT depend on mindmap-api. Entity node IDs are opaque `String` identifiers per the platform's cross-module identifier convention. Resolution from entity name → node ID happens in annotation-producing code in higher-tier CDI-capable modules.

## Module Structure

```
annotation-api/          — Tier 1 pure Java, zero CDI.
                           EntityAnnotationIndex SPI, EntityAnnotation record,
                           AnnotationMethod constants, EntityAnnotated CDI event type.
                           No mindmap-api dependency.

annotation-sqlite/       — SqliteEntityAnnotationIndex @ApplicationScoped.
                           SQLite + HikariCP WAL + Flyway.
                           Indexes: (tenant_id, entity_node_id),
                                    (tenant_id, source_type, source_id),
                                    (tenant_id, owner_subject_id).

annotation-inmem/        — InMemoryEntityAnnotationIndex @Alternative @Priority(2).
                           ConcurrentHashMap, clearAll() for test isolation.

annotation-testing/      — EntityAnnotationIndexContractTest abstract base.
                           Covers: CRUD, entity→text queries, pair queries,
                           repoint (merge), lifecycle deletion by owner subject,
                           tenant isolation, duplicate dedup after repoint.

annotation/              — CDI wiring module. Observers:
                           - MemoryEntityErasedObserver
                           - MergeRepointObserver
                           - EntityAnnotatedEventProducer
```

### Maven coordinates

| Module | artifactId |
|--------|-----------|
| Annotation API | `casehub-neocortex-annotation-api` |
| Annotation SQLite | `casehub-neocortex-annotation-sqlite` |
| Annotation In-Memory | `casehub-neocortex-annotation-inmem` |
| Annotation Testing | `casehub-neocortex-annotation-testing` |
| Annotation CDI | `casehub-neocortex-annotation` |

Root Java package: `io.casehub.neocortex.annotation`

## Annotation Production — Two-Phase Pipeline

### Phase 1: Semantic (LLM)

Extend `ParsedExtraction` to carry mention spans:

```java
public record ParsedMention(
    String entityName,    // canonical name from ParsedEntity
    String surfaceForm,   // what appeared in text: "he", "the detective", "James"
    int mentionIndex      // ordering within the text (for positional disambiguation)
) {}

public record ParsedExtraction(
    List<ParsedEntity> entities,
    List<ParsedRelationship> relationships,
    List<ParsedContradiction> contradictions,
    List<ParsedMention> mentions          // NEW
) {}
```

The MindMapExtractor LLM prompt is extended:

> For each entity you identify, list every mention of it in the text — including pronouns, definite descriptions, and other referring expressions. Report the exact surface form as it appears in the text, and the canonical entity name it refers to. Report mentions in the order they appear in the text.

The LLM reports semantic information (which surface forms refer to which entities) but NOT character offsets. LLMs hallucinate positions — offset computation is a positional task that must be deterministic.

### Phase 2: Positional (programmatic)

`AnnotationSpanResolver` (pure Java, in annotation-api):

```java
public class AnnotationSpanResolver {
    public List<ResolvedSpan> resolve(String text, List<ParsedMention> mentions);
}

public record ResolvedSpan(
    String entityName,
    String surfaceForm,
    int startOffset,    // inclusive, 0-based
    int endOffset,      // exclusive
    int mentionIndex
) {}
```

**Resolution strategy:** Sequential scan. For each mention in order:
1. Search text for the exact surface form starting from the last resolved position
2. If found, record offsets and advance the scan position
3. If not found (LLM reported a surface form that doesn't appear), skip with warning

**Disambiguation:** When multiple occurrences of the same surface form exist (e.g., "he" appears three times), the LLM's mention ordering (which reports mentions in text order) combined with sequential scanning naturally selects the correct occurrence.

### Integration point

`ExtractionRequestedObserver` (existing, in mindmap-intelligence) already calls `MindMapExtractor.parse()` + `apply()`. After `apply()` returns entity name→node ID mappings:

1. Call `AnnotationSpanResolver.resolve(text, mentions)` to compute offsets
2. Map entity names to node IDs (from the extraction result's `nameToNodeId`)
3. Write annotations to `EntityAnnotationIndex` via `addAnnotations()`

This path handles both:
- **Authored corpus:** biography import pipeline → MindMapExtractor → annotations
- **Runtime:** ConversationBridge → ExtractionRequested → async MindMapExtractor → annotations

## YAML Anchor Syntax

For authored biography YAML, inline anchors provide convenient entity marking:

```yaml
entities:
  pp: "James Pond"
  obj-7: "Guest Book"

passages:
  - text: "James[pp] examined the guest book[obj-7]. He[pp] opened it[obj-7] carefully."
```

### AnchorAnnotationParser (pure Java, in annotation-api)

1. Regex scan for `(\S+)\[([a-zA-Z0-9_-]+)\]` patterns
2. Strip brackets to produce clean text: `"James examined the guest book. He opened it carefully."`
3. Compute character offsets in clean text for each mention
4. Output: clean text + `List<ParsedAnchor>` (alias, surface form, start, end)

Resolution of alias → canonical name → MindMap node ID happens at import time in the biography import pipeline (higher-tier module), not in the parser.

### Entity registry

Each YAML file declares a local entity map:

```yaml
entities:
  pp: "James Pond"
  obj-7: "Guest Book"
```

The import pipeline resolves aliases to canonical names, then resolves canonical names to MindMap node IDs via `MindMapStore.resolveNode()`. Unresolvable aliases produce warnings (entity not yet in graph).

## Cognitive Integration

### Salience — EntityAwareSalienceStrategy

Decorator or replacement for `ConcernBasedSalienceStrategy`:

- **Current:** keyword-overlap between observation text and active concern text
- **New:** entity-overlap between observation's annotations and active concerns' entity references
- An observation mentioning entities from active drives/goals gets exact salience boost
- Falls back to keyword overlap when annotations are unavailable (graceful degradation)

```java
public class EntityAwareSalienceStrategy implements SalienceStrategy {
    private final EntityAnnotationIndex annotationIndex;
    private final SalienceStrategy delegate; // ConcernBasedSalienceStrategy

    @Override
    public PerceivedSituation filter(SalienceContext context) {
        // 1. Get entity annotations for the observation
        // 2. Get entity references from active drives/goals
        // 3. Compute entity overlap → salience boost
        // 4. Combine with delegate's keyword-based salience
    }
}
```

### Reflection — Entity-scoped knowledge retrieval

In `ReflectionService` and `LlmReflectionSynthesizer`:

- **Current:** "what do I know?" queries experience memories by text search
- **New:** "what do I know about X?" is `findByEntity(nodeId)` — returns ALL mentions including pronouns and definite descriptions
- `LlmReflectionSynthesizer` receives entity-annotated memories for richer synthesis
- Entity-scoped reflection: given a target entity, gather all memories mentioning it, synthesize

### Belief Revision — Entity-grounded provenance

In `BeliefRevisionPhase`:

- **Current:** belief nodes have text-based provenance
- **New:** belief nodes carry entity annotations linking claims to specific entity mentions in source memories
- Contradiction detection enhanced: when two memories have conflicting annotations about the same entity, the conflict is identified with precise provenance (memory X at span [a,b] vs memory Y at span [c,d])

### Theory of Mind — Entity-scoped mental models

In `MentalModelOrchestrator`:

- **Current:** mental models built from keyword-matched memories
- **New:** model of James built from ALL James-linked spans (including "he", "that man", "the detective")
- `findByEntity(jamesNodeId)` → every memory mentioning James → complete interaction history
- Cross-entity queries: `findByEntityPair(jamesId, claraId)` → all interactions between two entities

## Retrieval Modulation

`EntityOverlapModulationFactor` implements `ModulationFactor<Memory>`:

```java
public class EntityOverlapModulationFactor implements ModulationFactor<Memory> {
    private final EntityAnnotationIndex annotationIndex;
    private final Set<String> contextEntityNodeIds;

    @Override
    public double apply(Memory memory, ModulationContext ctx) {
        Set<String> memoryEntities = annotationIndex.distinctEntitiesInSource(
            "memory", memory.memoryId(), ctx.tenantId());
        long overlap = memoryEntities.stream()
            .filter(contextEntityNodeIds::contains).count();
        if (overlap == 0) return 1.0;
        return 1.0 + (overlap * 0.15); // 15% boost per shared entity
    }
}
```

Constructor-injected, following `GoalRelevanceModulationFactor` precedent. Plugs into existing `RetrievalModulator` infrastructure. Entity overlap is a signal, not a gate — memories without overlap can still be retrieved via vector similarity.

## Lifecycle Events

| Event | Source | Observer | Action |
|-------|--------|----------|--------|
| `MemoryEntityErased.ByEntity` | CaseMemoryStore | `MemoryEntityErasedObserver` | Delete by `(sourceType="memory", ownerSubjectId=subject.id(), tenantId)` |
| `MemoryEntityErased.ByRequest` | CaseMemoryStore | `MemoryEntityErasedObserver` | Same, scoped by domain |
| `MemoryEntityErased.CrossTenant` | CaseMemoryStore | `MemoryEntityErasedObserver` | Iterate affected tenants |
| `GraphMutationRecorded` → `NodesMerged` | MutationTrackingDecorator | `MergeRepointObserver` | `repointEntity(absorbedId, survivorId, tenantId)` + dedup |
| `EntityAnnotated` | EntityAnnotationIndex | (downstream) | Available for reactive consumers |

### Merge repointing detail

When `mergeNodes(keepId, removeId, tenantId)` fires `GraphMutationRecorded` wrapping `NodesMerged(survivorId=keepId, absorbedId=removeId)`:

1. `repointEntity(removeId, keepId, tenantId)` updates all annotations referencing `removeId`
2. Post-repoint deduplication: if the same source document now has two annotations for the same entity at the same offsets (because both merged nodes were mentioned), remove duplicates
3. Contract tests must cover: basic repoint, dedup after repoint, repoint with no matching annotations (no-op)

### Memory lifecycle detail

`MemoryEntityErased` carries `Subject` (with `id()` = entity name) and `tenantId` but not individual memory IDs. Each memory-sourced annotation carries `ownerSubjectId` — the `Subject.id()` of the memory owner, set at creation time from `Memory.subject().id()`.

On `MemoryEntityErased.ByEntity(tenantId, count, subject, erasedAt)`:
- Delete all annotations where `ownerSubjectId = subject.id() AND sourceType = "memory" AND tenantId` matches

This avoids identity mismatch (comparing entity names to entity names, not to MindMap node UUIDs) and provides complete scope (deletes ALL annotations from the subject's memories regardless of which entities they reference).

## Profile Independence

Renaming a MindMap node (`updateNode` with new name) does NOT change the node ID. Annotations anchor on node ID, not name. A rename is invisible to the annotation index.

Only merge retires a node ID — handled by `MergeRepointObserver`.

## Testing Strategy

### Contract tests (annotation-testing)

`EntityAnnotationIndexContractTest` abstract base — both `InMemoryEntityAnnotationIndex` and `SqliteEntityAnnotationIndex` extend it:

- **CRUD:** add, remove by ID, remove by source, remove by owner subject
- **Entity → text queries:** findByEntity, findByEntityPair, findByEntities
- **Text → entity queries:** findBySource, distinctEntitiesInSource
- **Aggregation:** entityMentionCounts
- **Merge repoint:** basic repoint, dedup after repoint, no-op when no matches
- **Tenant isolation:** annotations in tenant A invisible from tenant B
- **Confidence:** optional confidence stored and returned correctly
- **ownerSubjectId:** nullable, deletion scoped correctly

### Integration tests

- `AnnotationSpanResolver`: surface form matching, sequential scan, disambiguation, missing surface forms
- `AnchorAnnotationParser`: bracket stripping, offset computation, nested brackets (error), unregistered aliases
- `MergeRepointObserver`: CDI event firing → annotation repointing end-to-end
- `MemoryEntityErasedObserver`: CDI event firing → annotation cleanup end-to-end
- Cognitive integration: entity-aware salience with annotated observations

## References

- casehubio/neocortex#721 — unified entity linking issue
- casehubio/neocortex#477 — relational schemas (entity-aware relationships)
- casehubio/neocortex#170 — character name tokenization (superseded by this)
- `MindMapExtractor.java` — existing LLM entity extraction
- `ConversationBridge.java` — existing text segmentation + extraction trigger
- `ExtractionRequestedObserver` — async extraction pipeline
- `ParsedExtraction.java`, `ParsedEntity.java` — existing extraction output types
- `MergeResult.java`, `MindMapStore.mergeNodes()` — merge semantics
- `MemoryEntityErased` sealed interface — memory lifecycle events
- `GraphMutationRecorded`, `GraphMutation.NodesMerged` — graph mutation events
- `ModulationFactor`, `GoalRelevanceModulationFactor` — retrieval modulation pattern
- `ConcernBasedSalienceStrategy` — existing salience implementation
- Barrett 4-channel finding (project memory) — label+degree+prose for grounding
- `decisions.md` — 18 captured design decisions with review

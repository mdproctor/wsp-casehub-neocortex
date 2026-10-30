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
    int startOffset,           // inclusive, 0-based Java char index (UTF-16 code unit position)
    int endOffset,             // exclusive — String.substring(startOffset, endOffset) recovers mentionText
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

### Re-annotation trigger

Memories in this platform are immutable once stored — experiences, beliefs, and reflections create new memory records rather than mutating existing text. Annotations therefore do not go stale from text mutation. If extraction improves (better LLM prompt, updated coreference model), re-extraction can be triggered per-source: delete existing annotations for the source via `removeBySource()`, then re-extract. This is an operational concern, not a design-time trigger.

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

    // Consumer: EntityAwareSalienceStrategy uses mention frequency as a baseline
    // salience signal — frequently mentioned entities across the corpus are
    // higher-salience candidates. Also used by MindMap admin views for
    // entity importance ranking.
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
                           Flyway migration path: db/annotation/migration/ (module-scoped,
                           following neocortex convention — each module owns its own
                           Flyway directory with independent V-numbers per
                           flyway-version-range-allocation Rule 4).
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

Extend `ParsedExtraction` (in `mindmap-intelligence`) to carry mention spans:

```java
// mindmap-intelligence — LLM extraction output type
public record ParsedMention(
    String entityName,    // canonical name from ParsedEntity
    String surfaceForm,   // what appeared in text: "he", "the detective", "James"
    int mentionIndex      // global ordering within the text (for positional disambiguation)
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

`AnnotationSpanResolver` (pure Java, in annotation-api) uses its own input type `MentionInput` — not `ParsedMention` from mindmap-intelligence. This preserves the tier boundary: annotation-api (Tier 1) does not depend on mindmap-intelligence (Tier 2+). The integration point maps `ParsedMention → MentionInput`.

```java
// annotation-api — resolver input type (Tier 1)
public record MentionInput(
    String entityName,    // canonical entity name
    String surfaceForm,   // what appeared in text
    int mentionIndex      // global text-order position
) {}

public class AnnotationSpanResolver {
    public List<ResolvedSpan> resolve(String text, List<MentionInput> mentions);
}

public record ResolvedSpan(
    String entityName,
    String surfaceForm,
    int startOffset,    // inclusive, 0-based Java char index (UTF-16 code units)
    int endOffset,      // exclusive
    int mentionIndex
) {}
```

**Resolution strategy:** Sort-then-scan. The resolver:
1. Sorts mentions by `mentionIndex` (ascending) to guarantee global text order regardless of LLM output grouping
2. For each mention in sorted order: search text for the exact surface form starting from the last resolved position
3. If found, record offsets and advance the scan position
4. If not found (LLM reported a surface form that doesn't appear), skip with warning

**Disambiguation:** When multiple occurrences of the same surface form exist (e.g., "he" appears three times), the sort-by-mentionIndex + sequential scanning naturally selects the correct occurrence. Sorting defensively ensures correctness even if the LLM groups mentions by entity rather than interleaving in text order.

### Integration point

`ExtractionRequestedObserver` (existing, in mindmap-intelligence) already calls `MindMapExtractor.parse()` + `apply()`. After `apply()` returns `ExtractionResult`:

1. Map `ParsedMention → MentionInput` (trivial record mapping across the tier boundary)
2. Call `AnnotationSpanResolver.resolve(text, mentionInputs)` to compute offsets
3. Reconstruct entity name → node ID mapping from `result.entities()`: `result.entities().stream().collect(toMap(ExtractedEntity::name, ExtractedEntity::nodeId))`
4. Write annotations to `EntityAnnotationIndex` via `addAnnotations()`

Note: `ExtractionResult` does not expose a `nameToNodeId` field directly — the mapping is reconstructed from `ExtractedEntity.name()` and `ExtractedEntity.nodeId()` on the `ExtractionResult.entities()` list.

### Source identification for conversation annotations

`ExtractionRequested` currently carries `cleanedText`, `tenantId`, `recentEntityNames`, `segmentNodeIds`, and `principalId` — but no turn ID, no conversation session ID, and no owner subject.

**Required change:** Add `batchId` (UUID, generated by `ConversationBridge` at fire time) and `ownerSubjectId` (nullable `String`, from the conversation's subject context) to `ExtractionRequested`.

Conversation annotations use:
- `sourceType = "conversation-turn"`
- `sourceId = batchId` — uniquely identifies this extraction batch
- `ownerSubjectId` — the subject ID from the conversation context, if available; `null` otherwise

**Lifecycle implications:** Conversation annotations with a non-null `ownerSubjectId` are cleaned up by `MemoryEntityErased` via `removeByOwnerSubject("conversation-turn", subjectId, tenantId)`. Annotations with null `ownerSubjectId` are cleaned up by explicit `removeBySource("conversation-turn", batchId, tenantId)` — e.g., on conversation turn expiry.

**Offset scope:** Annotations are computed against the full `cleanedText` passed to `ExtractionRequested`, not against individual segment bodies. The `batchId` identifies the text unit that offsets are relative to.

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

### BiographyLoader integration

The existing `BiographyLoader` uses Jackson to deserialize typed YAML files, then passes the loaded `BiographyProfile` to `BiographyHandler` implementations via `BiographyImportRunner`. Bracket syntax integration requires a small modification to `BiographyImportRunner` — existing handlers and `BiographyLoader` are unmodified.

**Problem:** If biography YAML contains bracket syntax (`"James[pp] examined the guest book[obj-7]."`), existing handlers like `LifeEventHandler` store `entry.description()` verbatim — the memory text would contain brackets. `BiographyProfile` is a record (immutable), and handlers all receive the same profile, so bracket stripping must happen before handler dispatch.

**Solution:** `BiographyImportRunner` gains an optional pre-processing step via a CDI `Instance<BiographyProfilePreprocessor>`:

```java
// memory-seeding — preprocessor SPI
public interface BiographyProfilePreprocessor {
    BiographyProfile preprocess(BiographyProfile profile, String agentId, String tenantId);
}
```

Modified `BiographyImportRunner.run()`:
1. If `BiographyProfilePreprocessor` is resolvable (annotation module on classpath), call `preprocessor.preprocess(profile, agentId, tenantId)` to get a sanitized profile
2. The preprocessor strips bracket syntax from all text fields using `AnchorAnnotationParser`, constructs a new `BiographyProfile` with clean text, collects anchor data, and writes annotations to `EntityAnnotationIndex`
3. Handlers receive the sanitized profile — no handler modifications needed

**Annotation source identity:** Biography annotations use `sourceType = "biography"` with `sourceId = entry.id()`. They reference the biography passage, not the runtime memory. The LLM extraction pipeline separately produces `sourceType = "memory"` annotations when biography-created memories trigger `ExtractionRequested`. The two annotation sets complement each other: YAML anchors are precise human-authored links (confidence = 1.0); LLM annotations cover pronouns and implicit mentions.

**Optional activation:** The preprocessor follows the `optional-module-pattern` protocol — `BiographyImportRunner` works identically without the annotation module. When `annotation-api` is not on the classpath, `Instance<BiographyProfilePreprocessor>.isResolvable()` returns false, and the raw profile passes through unchanged (no bracket syntax expected in YAML without the annotation feature).

## Cognitive Integration

### Salience — EntityAwareSalienceStrategy

Decorator or replacement for `ConcernBasedSalienceStrategy`:

- **Current:** keyword-overlap between observation text and active concern text
- **New:** one-sided entity matching — concern annotations (which exist) matched against observation text (which is raw, unannotated)
- Falls back to delegate's keyword-based salience when no concern annotations exist (graceful degradation)

**Why one-sided:** At salience time, the observation is raw text with no annotations. `ConversationBridge.process()` fires `ExtractionRequested` via `fireAsync` — extraction runs asynchronously after the cognitive tick. `SalienceContext.observation()` is a plain `String` with no source ID. The observation CANNOT have annotations at salience time.

Active concerns (`SalienceContext.activeConcerns()`) are `List<Memory>` with `memoryId()` — their annotations CAN exist (stored memories have been through extraction).

```java
public class EntityAwareSalienceStrategy implements SalienceStrategy {
    private final EntityAnnotationIndex annotationIndex;
    private final SalienceStrategy delegate; // ConcernBasedSalienceStrategy

    @Override
    public PerceivedSituation perceive(SalienceContext context) {
        // 1. Collect entity node IDs from active concern annotations:
        //    for each concern memory, findBySource("memory", concern.memoryId(), tenantId)
        //    → Set<String> concernEntityNodeIds
        // 2. Resolve entity NAMES for those node IDs (from annotation mentionText
        //    or via MindMapStore.resolveNode)
        // 3. Match entity names against context.observation() (text search)
        // 4. Entity name match → salience boost for that concern
        // 5. Combine with delegate's keyword-based salience
        // Returns PerceivedSituation(narrative, salience) with entity-aware salience scores
    }
}
```

This is strictly more precise than keyword overlap: a concern about "James" boosts salience when the observation mentions "James" by entity-grounded name, not just by keyword substring. As the annotation corpus grows, the set of known entity names grows too — matching improves over time without model changes.

### Reflection — Entity-scoped knowledge retrieval

In `ReflectionSynthesizer` (SPI) and `LlmReflectionSynthesizer` (implementation):

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
    private final String tenantId;
    private final Set<String> contextEntityNodeIds;

    public EntityOverlapModulationFactor(EntityAnnotationIndex annotationIndex,
                                          String tenantId,
                                          Set<String> contextEntityNodeIds) {
        this.annotationIndex = annotationIndex;
        this.tenantId = tenantId;
        this.contextEntityNodeIds = contextEntityNodeIds;
    }

    @Override
    public double apply(Memory memory, ModulationProfile<Memory> profile) {
        Set<String> memoryEntities = annotationIndex.distinctEntitiesInSource(
            "memory", memory.memoryId(), tenantId);
        long overlap = memoryEntities.stream()
            .filter(contextEntityNodeIds::contains).count();
        if (overlap == 0) return 1.0;
        return 1.0 + (overlap * 0.15); // 15% boost per shared entity
    }
}
```

Constructor-injected `tenantId` following `GoalRelevanceModulationFactor` precedent (which also takes `MindMapStore store, String tenantId` via constructor). Plugs into existing `RetrievalModulator` infrastructure. Entity overlap is a signal, not a gate — memories without overlap can still be retrieved via vector similarity.

## Lifecycle Events

| Event | Source | Observer | Action |
|-------|--------|----------|--------|
| `MemoryEntityErased.ByEntity` | CaseMemoryStore | `MemoryEntityErasedObserver` | Delete by `(sourceType="memory", ownerSubjectId=subject.id(), tenantId)` |
| `MemoryEntityErased.ByRequest` | CaseMemoryStore | `MemoryEntityErasedObserver` | Same as ByEntity — deletes all memory-source annotations for the subject. Over-deletion is accepted: annotations for non-erased domains are recreated on next extraction. The SPI has no domain parameter because adding a domain field to every annotation adds model complexity for a single lifecycle edge case. |
| `MemoryEntityErased.CrossTenant` | CaseMemoryStore | `MemoryEntityErasedObserver` | Iterate affected tenants |
| `GraphMutationRecorded` → `NodesMerged` | MutationTrackingDecorator | `MergeRepointObserver` | `repointEntity(absorbedId, survivorId, tenantId)` + dedup |
| `EntityAnnotated` | EntityAnnotationIndex | (downstream) | Available for reactive consumers |

### Merge repointing detail

`MergeRepointObserver` uses `@Observes` (synchronous CDI observation), not `@ObservesAsync`. This is mandatory because `MutationTrackingCdiDecorator` fires events via `event::fire` (synchronous); CDI spec: `fire()` triggers `@Observes`, `fireAsync()` triggers `@ObservesAsync` — they don't cross.

**Transactional coupling:** Synchronous observation means annotation repointing happens within the merge transaction. This provides consistency (no window where annotations point to a retired node) but requires that `repointEntity()` be a lightweight SQL UPDATE, not expensive I/O that would block the merge path.

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

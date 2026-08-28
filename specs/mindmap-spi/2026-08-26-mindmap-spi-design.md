# MindMap SPI — Design Specification

## 0. Tracking

**Epic:** casehubio/neocortex#213

## 1. Problem Statement

The casehub platform has rich cognitive capabilities distributed across neocortex (memory
SPIs, CBR, experience, reflection, mood, engagement) and blocks (orchestrated agent
patterns with mental models, drives, strategies, narratives, user profiles). Each subsystem
stores knowledge in isolated backends — `CaseMemoryStore` for flat text memories,
`CbrCaseMemoryStore` for feature-vector similarity, and domain-specific CBR wrappers
(`CbrMentalModelStore`, `CbrStrategyStore`, `CbrUserProfileStore`, `CbrNarrativeStore`).

The missing capability is **structural knowledge** — typed relationships between entities
across subsystems. An agent knows facts about a user (mental model), has strategies for
interacting with them (strategy store), remembers conversations (narrative store), and
tracks engagement (engagement events). But these are disconnected silos. There is no way
to ask "what do I know about Alice across all subsystems?" without querying each store
separately and reconciling results.

The mind map SPI provides a graph of typed nodes and edges that serves as connective
tissue linking these subsystems. It is not a replacement for the existing stores — CBR
keeps doing similarity retrieval, `CaseMemoryStore` keeps storing text memories. The
graph adds the relationship layer that makes cross-system connections explicit, queryable,
and maintainable.

The mental model is "mind maps that merge" — each topic, person, or project is its own
map with internal structure, and the interesting knowledge emerges when maps connect.

### 1.1 Relationship to GraphCaseMemoryStore

`GraphCaseMemoryStore` (memory-api, issue #185) is a **memory store** — it stores text
memories (`Memory` records with `text()`, `domain()`, `entityId()`) and offers semantic
graph queries via `graphQuery(GraphMemoryQuery)`. The "graph" is the Graphiti backend's
internal representation; the SPI consumer sees `List<Memory>`, not graph structure. Its
purpose: _retrieve text facts semantically_ — "what do I know about Alice?" returns prose
facts like "Alice mentioned she prefers working remotely."

`MindMapStore` is a **structural knowledge graph** — typed nodes with properties, typed
edges with temporal bounds, subgraph partitioning, merge, alias resolution, vocabulary
governance, and cross-store references. Its purpose: _model entities and their
relationships_ — "how is Alice connected?" returns typed edges like `works-at → Company X`,
`parent-of → Bob`, `involved-in → Project Y`.

These are complementary, not overlapping:

| Concern | GraphCaseMemoryStore | MindMapStore |
|---|---|---|
| Data model | `Memory` (text + metadata) | `MindMapNode` + `MindMapEdge` (typed graph) |
| Query model | Semantic search (`graphQuery`) | Graph traversal (`neighbors`, `search`) |
| Storage | Text facts with entity scoping | Entities, relationships, properties |
| Example query | "What did Alice say about remote work?" | "Who does Alice work with?" |
| Backend | Graphiti (external service) | SQLite (embedded, self-contained) |

The MindMap graph references memories via `NodeRef(scheme="memory", id=memoryId)` — it
doesn't duplicate them. A consumer wanting "everything about Alice" queries the MindMap
for structural knowledge and follows NodeRefs to retrieve the underlying text memories
from `CaseMemoryStore`. This is unification by reference, not unification by duplication.

The SPI does not extend `GraphCaseMemoryStore` or `CaseMemoryStore` because they model
fundamentally different data. `CaseMemoryStore` stores text with `String store(MemoryInput)`
and retrieves via semantic search. `MindMapStore` stores typed graph structure with
`String addNode(NodeInput)` and retrieves via graph traversal. Forcing these into a
shared type hierarchy would require one to pretend to be the other — an adapter pattern
with no architectural benefit.

## 2. Architecture

### 2.1 Module Structure

New top-level module family, parallel to `memory-*`, `rag-*`, `inference-*`:

```
mindmap-api/          — SPI + value types (pure Java, zero deps)
mindmap/              — CDI wiring, NoOp default, decorators (vocabulary normalization,
                        derived edge rules, confidence decay), graph analysis
                        (pure computation — no LLM dependency)
mindmap-inmem/        — In-memory adapter for tests
mindmap-sqlite/       — SQLite adapter (day-one production backend)
mindmap-testing/      — Contract test suite + integration test scenarios
mindmap-intelligence/ — trait proxy + standard trait rules (pure Java, no LLM);
                        LLM extraction, gap detection, active learning,
                        curiosity engine (these require AgentProvider)
```

The SPI is standalone — it does not extend `CaseMemoryStore`, `GraphCaseMemoryStore`,
or `CbrCaseMemoryStore`. This avoids CDI bean displacement across repo boundaries
(GE-20260630-815259). Integration with other memory stores is via URI-style typed
references and CDI observers.

### 2.2 Dependency Direction

```
mindmap-api  ←  mindmap  ←  mindmap-sqlite
                         ←  mindmap-inmem
                         ←  mindmap-intelligence (also depends on mindmap-api)
                         ←  mindmap-testing

blocks       →  mindmap-api  (observers create/update graph from domain events)
engine       →  mindmap-api  (optional — query graph for routing/context)
```

The mindmap-api module has zero dependencies on other casehub modules. It defines its
own tenant model, capability enum, and value types.

### 2.3 Intelligence Layer Split

Following the CBR decorator pattern, intelligence concerns split into two tiers:

**Transparent (CDI `@Decorator` on `MindMapStore`):**

All four decorators are CDI `@Decorator` beans with explicit `@Priority`
positions in the chain (§5.2.1). The complete chain from outermost to
innermost:

- Confidence decay `@Priority(50)` — applied at query time; intercepts
  `getNode()`, `getEdge()`, `nodesIn()`, `search()`, `neighbors()`,
  `bridgeEdges()` to return decayed confidence values
- Trait application `@Priority(70)` — evaluates `TraitRule` beans on
  the return path after mutations, applying/retracting traits
- Derived edge insertion `@Priority(80)` — forward-chaining rules fire
  on edge creation (e.g., has-child → infer parent). Rules are pluggable
  CDI beans (`DerivedEdgeRule`). Truth maintenance retracts derived edges
  when evidence is removed. Cycle prevention limits chain depth (default 3)
- Vocabulary normalization `@Priority(90)` — alias resolution on every
  `addEdge()`, closest to the store so all higher decorators see
  normalised types

**Computation (mindmap CDI module, no LLM dependency):**
- Graph analysis — centrality, clustering, structural hole detection
- Index maintenance — FTS rebuild, temporal index updates

**Explicit (mindmap-intelligence module, requires AgentProvider):**
- LLM-based entity/relationship extraction from conversation
- **Rule promotion** — the extraction layer discovers relationship patterns
  (e.g., "people who share a `works-at` target and appear in the same project
  subgraph are usually collaborators") and codifies them as `DerivedEdgeRule`
  beans. This is **learned inference caching**: the LLM pays the token cost
  once to discover the pattern; every future instance fires deterministically
  at zero token cost. Hand-coded rules (has-child → parent-of) cover obvious
  structural inverses; the interesting rules are the ones the agent discovers
  through experience and promotes from the explicit tier to the transparent tier.
- Gap detection and curiosity signal generation
- Active learning question generation
- Contradiction analysis and resolution prompts
- Trait proxy generation (truth maintenance is transparent — see §5.2)

## 3. SPI — `MindMapStore`

### 3.1 Core Interface

```java
package io.casehub.neocortex.mindmap;

public interface MindMapStore {

    // --- Vocabulary ---
    void registerVocabulary(MindMapVocabulary vocabulary);

    // --- Nodes ---
    String addNode(NodeInput input, String tenantId);
    MindMapNode getNode(String nodeId, String tenantId);
    void updateNode(String nodeId, NodeUpdate update, String tenantId);

    // --- Edges ---
    String addEdge(EdgeInput input, String tenantId);
    MindMapEdge getEdge(String edgeId, String tenantId);
    void updateEdge(String edgeId, EdgeUpdate update, String tenantId);
    void removeEdge(String edgeId, String tenantId);

    // --- Aliases ---
    void addAlias(String nodeId, String alias, String tenantId);
    void removeAlias(String nodeId, String alias, String tenantId);
    MindMapNode resolveNode(String nameOrAlias, String subgraphId,
                            String tenantId);  // subgraphId nullable

    // --- Merge ---
    MergeResult mergeNodes(String keepNodeId, String removeNodeId,
                           String tenantId);

    // --- Subgraphs ---
    String createSubgraph(SubgraphInput input, String tenantId);
    MindMapSubgraph getSubgraph(String subgraphId, String tenantId);
    void updateSubgraph(String subgraphId, String rootNodeId,
                        String tenantId);
    List<MindMapSubgraph> listSubgraphs(String tenantId);
    List<MindMapNode> nodesIn(String subgraphId, String tenantId);
    List<MindMapEdge> bridgeEdges(String subgraphId, String tenantId);

    // --- Traversal ---
    List<MindMapEdge> neighbors(String nodeId, String tenantId);
    List<MindMapEdge> neighbors(String nodeId, String edgeType,
                                String tenantId);
    List<MindMapNode> search(MindMapQuery query);

    // --- Lifecycle ---
    void supersede(String targetId, String supersedingId, String reason,
                   String tenantId);
    void reinstate(String targetId, String tenantId);
    SupersessionStatus getSupersessionStatus(String targetId,
                                             String tenantId);

    // --- Erasure ---
    int eraseNode(String nodeId, String tenantId);
    int eraseSubgraph(String subgraphId, String tenantId);
    int eraseEntity(String entityName, String tenantId);
    int eraseEntityAcrossTenants(String entityName, Set<String> tenantIds);

    // --- Capabilities ---
    Set<MindMapCapability> capabilities();
    void requireCapability(MindMapCapability capability);
}
```

Every mutating and querying method requires `tenantId` for tenant isolation.
Implementations must enforce tenant boundaries — a node in tenant A is invisible
to queries in tenant B.

**Deletion semantics:**

All node deletion is hard deletion with cascading cleanup. There is no
separate `removeNode()` — following the existing store patterns where
`CaseMemoryStore` and `CbrCaseMemoryStore` provide only `erase*()` methods
for deletion. `eraseNode()` serves both application-level deletion ("this
node is wrong, remove it") and GDPR compliance erasure. The `int` return
value supports GDPR Art.5(2) audit logging in all cases.

- `eraseNode()` — hard-deletes a specific node by ID, including all edges,
  aliases, NodeRefs, and dynamic properties. Returns count of deleted records.
- `eraseSubgraph()` — hard-deletes all nodes in the subgraph plus the subgraph
  itself. Returns total count of deleted records.
- `eraseEntity()` — entity-scoped erasure. Finds all nodes whose `name` matches
  `entityName` (case-insensitive) OR who have an alias matching `entityName`,
  and erases them. This handles the "erase everything about Alice" case without
  requiring the caller to know node IDs.
- `eraseEntityAcrossTenants()` — cross-tenant entity erasure, matching
  `CaseMemoryStore.eraseEntityAcrossTenants()`. Caller must be a cross-tenant
  admin. Supply the complete set of tenantIds from the tenant management system.

Edge deletion uses `removeEdge()` — edges are structural elements without
independent identity for GDPR purposes. Edge deletion cascades nothing (edges
are leaf elements in the graph).

**`resolveNode()` — alias and name resolution:**

`subgraphId` is nullable. When null, resolution searches aliases across all
subgraphs within the tenant. Aliases are unique per tenant (§6.2), so
alias-based resolution always returns at most one node regardless of
`subgraphId`. When non-null, resolution is scoped to that subgraph — useful
for name-based disambiguation when multiple nodes share a name across
subgraphs.

**Traversal result sets:**

`neighbors()`, `nodesIn()`, and `bridgeEdges()` return structurally
complete, unbounded result sets. These are graph-structural queries, not
search — truncating neighbors arbitrarily would produce incorrect results
for graph analysis (centrality, clustering, structural hole detection).
The expected scale is per-agent mind maps (hundreds to low thousands of
nodes per tenant), not social-network-scale graphs. Backends may impose
an implementation cap (e.g., 10,000) with an exception if exceeded.

### 3.2 Node Model — Hybrid Core + Dynamic Properties

```java
public interface MindMapNode {
    // Core fields — always present, column-backed, indexed
    String id();
    String name();
    String subgraphId();
    ConfidenceOrigin confidenceOrigin();
    double confidence();         // [0.0, 1.0] — numeric, decayable
    String provenance();
    Instant createdAt();
    Instant updatedAt();
    Instant confirmedAt();       // last explicit confirmation (resets decay)
    Instant validFrom();         // nullable — temporal bound start
    Instant validUntil();        // nullable — temporal bound end
    Set<String> traits();        // applied trait names (opaque to SPI)
    Set<NodeRef> refs();         // references to entities in other stores

    // Affective metadata — optional
    Double pleasure();           // [-1, 1] positive/negative (PAD model)
    Double arousal();            // [-1, 1] high/low activation
    Double dominance();          // [-1, 1] empowering/threatening

    // Dynamic properties — EAV or JSON-backed
    Optional<String> property(String key);
    Map<String, String> properties();  // core + extension unified view
}
```

The `property(key)` method provides unified access — it resolves from core fields
first, then falls back to dynamic properties. Consumers don't know or care which
storage path a value takes. This enables compaction: when a dynamic property
appears consistently (e.g., "birthday" on nodes with the Personable trait), it
can be promoted to a core column. The proxy layer hides this migration.

### 3.3 Edge Model

```java
public interface MindMapEdge {
    String id();
    String sourceNodeId();
    String targetNodeId();
    String edgeType();           // governed by vocabulary
    ValidationTier tier();       // REGISTERED or UNVALIDATED
    ConfidenceOrigin confidenceOrigin();
    double confidence();         // [0.0, 1.0] — numeric, decayable
    String provenance();
    Instant createdAt();
    Instant updatedAt();
    Instant confirmedAt();       // last explicit confirmation (resets decay)
    Instant validFrom();         // nullable — temporal bound start
    Instant validUntil();        // nullable — temporal bound end

    // Affective metadata — optional
    Double pleasure();           // [-1, 1] positive/negative (PAD model)
    Double arousal();            // [-1, 1] high/low activation
    Double dominance();          // [-1, 1] empowering/threatening

    // Dynamic properties
    Optional<String> property(String key);
    Map<String, String> properties();
}
```

Edges carry a `ValidationTier` — `REGISTERED` edges have been normalised through
the controlled vocabulary; `UNVALIDATED` edges were accepted but flagged for review.
The intelligence layer can promote validated types from UNVALIDATED to REGISTERED.

### 3.4 Input and Update Types

```java
public record NodeInput(
    String name,
    String subgraphId,
    ConfidenceOrigin confidenceOrigin,
    Double confidence,          // nullable — defaults to origin's initial value
    String provenance,
    Set<String> traits,
    Set<NodeRef> refs,
    Instant validFrom,
    Instant validUntil,
    Double pleasure,
    Double arousal,
    Double dominance,
    Map<String, String> properties
) {}

public record NodeUpdate(
    String name,              // nullable — only update if non-null
    ConfidenceOrigin confidenceOrigin,
    Double confidence,
    Instant confirmedAt,      // nullable — explicit confirmation resets decay clock
    Set<String> traitsToAdd,
    Set<String> traitsToRemove,
    Set<NodeRef> refsToAdd,
    Set<NodeRef> refsToRemove,
    Instant validFrom,
    Instant validUntil,
    Double pleasure,
    Double arousal,
    Double dominance,
    Map<String, String> propertiesToSet,
    Set<String> propertiesToRemove
) {}

public record EdgeInput(
    String sourceNodeId,
    String targetNodeId,
    String edgeType,
    ConfidenceOrigin confidenceOrigin,
    Double confidence,          // nullable — defaults to origin's initial value
    String provenance,
    Instant validFrom,
    Instant validUntil,
    Double pleasure,
    Double arousal,
    Double dominance,
    Map<String, String> properties
) {}

public record EdgeUpdate(
    ConfidenceOrigin confidenceOrigin,
    Double confidence,
    Instant confirmedAt,      // nullable — explicit confirmation resets decay clock
    Instant validFrom,
    Instant validUntil,
    Double pleasure,
    Double arousal,
    Double dominance,
    Map<String, String> propertiesToSet,
    Set<String> propertiesToRemove
) {}
```

### 3.5 Cross-Store References

```java
public record NodeRef(
    String scheme,      // "memory", "cbr", "experience", "external"
    String id,          // entity/case ID
    String qualifier    // domain, caseType, URL etc. — nullable
) {}
```

Loose coupling — the graph stores the reference without depending on the other
SPI's classpath. Resolution is lazy and requires the consuming module to have
the target SPI available.

**Lifecycle semantics:**

1. **Creation** — optimistic. The referenced entity is not validated at
   `NodeRef` creation time. The MindMap SPI has no dependency on the source
   store's classpath and cannot verify existence.

2. **GDPR erasure cascade** — when a source store erases an entity, the
   `mindmap` CDI module is notified to remove all `NodeRef`s pointing
   to the erased entity. Under GDPR Art.17, references that identify a data
   subject are themselves personal data. Cleanup is proactive, not lazy.

   **Existing implementation:** the erasure cascade is fully wired:

   - `MemoryEntityErased` — sealed interface in `memory-api` with three
     variants: `ByRequest`, `ByEntity`, `CrossTenant`.
   - `ErasureNotificationCaseMemoryStore` — `@Decorator @Priority(45)` on
     `CaseMemoryStore`. Fires `MemoryEntityErased` events after
     `erase()`, `eraseEntity()`, and `eraseEntityAcrossTenants()`.
   - `ErasureNotificationCbrCaseMemoryStore` — `@Decorator @Priority(45)`
     on `CbrCaseMemoryStore`. Fires `CbrCasesErased` events.
   - `NodeRefCleanupObserver` — `@ApplicationScoped` in the `mindmap` CDI
     module. Observes `MemoryEntityErased.ByEntity` (removes NodeRefs
     with scheme `"memory"`) and `CbrCasesErased.ByEntity` (removes
     NodeRefs with scheme `"cbr"`). Cleanup scans all tenant nodes via
     `store.search()` (limit 10,000), finds nodes with matching refs,
     and removes the refs via `updateNode()`.

   **Known limitation:** the cleanup does an O(N) scan over all nodes in
   the tenant per erasure event. Acceptable at V1 scale (hundreds to low
   thousands of nodes per tenant). At higher scale, an inverted index
   from `(scheme, refId)` → node IDs would avoid the full scan.

3. **Non-GDPR dangling refs** — when a referenced entity is deleted for
   non-GDPR reasons (e.g., supersession, consolidation), the `NodeRef`
   becomes a curiosity signal (§4.3). The intelligence layer detects
   dangling refs during analysis and generates knowledge gap questions.

4. **Bidirectionality** — source stores do not know they are referenced.
   The GDPR cascade relies on CDI events, not bidirectional pointers.

### 3.6 Vocabulary

```java
public record MindMapVocabulary(
    List<EdgeTypeDefinition> edgeTypes
) {
    public static Builder builder() { ... }
}

public record EdgeTypeDefinition(
    String canonical,           // the normalised name
    Set<String> aliases,        // alternative names that map to canonical
    Double defaultDecayHalfLifeDays  // nullable — type-specific decay rate
) {}
```

Registration is additive — multiple `registerVocabulary()` calls merge
definitions. The `VocabularyNormalizationDecorator` (`@Priority(90)`,
innermost in the chain — §5.2.1) normalises alias edge types to their
canonical form on `addEdge()`. Unregistered types are accepted but stored
with `ValidationTier.UNVALIDATED`.

**Thread safety:** `registerVocabulary()` is synchronized — concurrent
registrations produce the correct union of edge types and aliases. The
decorator uses a `ReadWriteLock`: vocabulary registration takes the write
lock; alias resolution on `addEdge()` takes the read lock.

**Retroactive normalization:** existing `UNVALIDATED` edges are NOT
retroactively promoted when a matching vocabulary is later registered.
Promotion happens only on explicit re-save or batch normalization via the
intelligence layer. This prevents silent data modification — an important
invariant for audit traceability.

**Canonical uniqueness:** canonical names must be globally unique across all
registered vocabularies. If vocabulary A defines canonical `"works-at"` and
vocabulary B also defines canonical `"works-at"` with a different alias set,
the aliases are merged. If vocabulary B defines `"employed-by"` as canonical
but vocabulary A already maps `"employed-by"` as an alias of `"works-at"`,
registration throws `VocabularyConflictException`.

### 3.7 Subgraphs

```java
public record SubgraphInput(
    String name,
    SubgraphType type,
    String rootNodeId     // nullable — can be set after creation
) {}

public record MindMapSubgraph(
    String id,
    String name,
    SubgraphType type,
    String rootNodeId,
    String tenantId,
    Instant createdAt
) {}

public enum SubgraphType {
    PERSON, PROJECT, RESEARCH_AREA, ORGANISATION, CONCEPT, GENERAL
}
```

Every node belongs to exactly one subgraph. Nodes that don't fit a specific
type go to a GENERAL subgraph. Cross-subgraph edges are "bridges" — queryable
via `bridgeEdges(subgraphId, tenantId)`.

### 3.8 Query

```java
public record MindMapQuery(
    String tenantId,
    String subgraphId,        // nullable — search across all subgraphs
    String text,              // nullable — text search across node names/properties
    String edgeType,          // nullable — filter by edge type
    Set<String> traits,       // nullable — filter by applied traits
    Double minConfidence,     // nullable — numeric threshold, applied after decay
    ConfidenceOrigin confidenceOrigin,  // nullable — filter by provenance
    boolean includeSuperseded,      // default false
    int limit
) {}
```

### 3.9 Merge

```java
public record MergeResult(
    String survivingNodeId,
    int edgesRepointed,
    int aliasesMerged,
    int duplicateEdgesRemoved,
    Set<String> traitsMerged,
    List<MergeConflict> propertyConflicts
) {}
```

Merge keeps `keepNodeId`, removes `removeNodeId`, unions their edges (deduplicating
by source+target+edgeType), unions aliases, unions traits, and reassigns subgraph
membership to the surviving node's subgraph.

**Edge deduplication resolution:** when two edges match on
source+target+edgeType but differ in confidence, temporal bounds, properties,
or provenance, the most-recently-updated edge wins (compared by `updatedAt`).
This is consistent with the property conflict resolution strategy below —
newer information is presumed more current. The discarded edge's data is not
recorded in `MergeResult` (edges are structural, not identity-bearing; the
`duplicateEdgesRemoved` count is sufficient for auditing).

**Property conflict resolution:** when both nodes have a dynamic property with
the same key but different values, the most-recently-updated node's value wins
(compared by `updatedAt`). Conflicting properties are recorded in
`MergeResult.propertyConflicts` for downstream review. Core fields (name,
confidence, provenance) always take the `keepNode`'s values.

```java
public record MergeConflict(
    String key,
    String keptValue,
    String discardedValue
) {}
```

### 3.10 Confidence and Decay

```java
public enum ConfidenceOrigin {
    STATED,       // directly asserted by a source — initial confidence 1.0
    INFERRED,     // derived by rules from other knowledge — initial confidence 0.7
    SPECULATED    // LLM-suggested, not confirmed — initial confidence 0.3
}
```

Confidence is a two-part model following the `CbrOutcome` pattern:
`ConfidenceOrigin` records **how** the knowledge was established (provenance
classification); `confidence` is a numeric value in `[0.0, 1.0]` that is
subject to continuous decay.

When a node or edge is created without an explicit `confidence` value, the
initial confidence is set from `ConfidenceOrigin`'s default (STATED=1.0,
INFERRED=0.7, SPECULATED=0.3). The caller can override the initial value.

Decay is applied at query time by the confidence decay decorator
(`@Priority(50)`, outermost in the chain — §5.2.1). The decorator
intercepts all query methods: `getNode()`, `getEdge()`, `nodesIn()`,
`search()`, `neighbors()` (both overloads), and `bridgeEdges()`. Every
access path returns decayed confidence — there is no raw-confidence
backdoor.

The decay formula is:

```
effectiveConfidence = confidence × 2^(-hoursSinceConfirmed / (halfLifeDays × 24))
```

The decay reference point is `confirmedAt()` for both nodes and edges.
Setting `confirmedAt` via `NodeUpdate` or `EdgeUpdate` (§3.4) resets the
decay clock.

**Edge decay rates:** each edge type can declare a `defaultDecayHalfLifeDays`
in its vocabulary definition (§3.6). Edges without a vocabulary decay rate
use a global default from the decorator's configuration.

**Node decay rates:** configured per `SubgraphType` via the decorator's
runtime configuration. Different knowledge categories decay at different
rates — a PERSON node's identity is stable (high half-life), while a
PROJECT node's status evolves frequently (low half-life). Recommended
defaults:

| SubgraphType | Half-life (days) | Rationale |
|---|---|---|
| PERSON | 365 | Identity is stable |
| PROJECT | 90 | Status evolves quarterly |
| ORGANISATION | 180 | Structure changes slowly |
| RESEARCH_AREA | 120 | Knowledge evolves moderately |
| CONCEPT | 730 | Definitions are durable |
| GENERAL | 180 | Conservative default |

These are decorator configuration, not SPI types — they live in the
`mindmap` CDI module's `@ConfigMapping`, not in `mindmap-api`.

**Explicit confirmation:** setting `confirmedAt` via `NodeUpdate` or
`EdgeUpdate` (§3.4) resets the decay clock. If `confidence` is also set
in the same update, the new confidence is used as the base; otherwise
confidence is restored to 1.0. This enables both "I re-confirmed this is
true" (confirmedAt only) and "I have new evidence at this confidence"
(confirmedAt + confidence together).

Edges have a symmetric lifecycle to nodes: `updateEdge()` accepts an
`EdgeUpdate` with `confirmedAt` support. A confirmed relationship like
"Alice works-at Acme" can have its decay clock reset without destroying
and recreating the edge.

### 3.11 Capabilities

```java
public enum MindMapCapability {
    TRAVERSAL,
    MERGE,
    VOCABULARY,
    ALIAS,
    SUBGRAPH,
    SEARCH,
    SUPERSESSION,
    ERASE_NODE,
    ERASE_SUBGRAPH,
    ERASE_ENTITY,
    CROSS_TENANT_ERASE,
    GRAPH_ANALYSIS
}
```

### 3.12 Supersession

```java
public record SupersessionStatus(
    String targetId,
    boolean superseded,
    Instant supersededAt,
    String supersedingId,
    String reason,
    Instant reinstatedAt
) {
    public boolean wasReinstated() {
        return reinstatedAt != null;
    }
}
```

## 4. Blocks Integration

### 4.1 The Problem of Isolated Cognitive Stores

Blocks' `InnerLifeOrchestrator` coordinates multiple cognitive subsystems, each with
its own CBR backend:

| Orchestrator | CBR Store | What it models |
|---|---|---|
| MentalModelOrchestrator | CbrMentalModelStore | BDI beliefs about users/agents |
| StrategyLearningOrchestrator | CbrStrategyStore | Interaction strategies |
| UserModelOrchestrator | CbrUserProfileStore | User preferences/profiles |
| NarrativeOrchestrator | CbrNarrativeStore | Conversation narratives |
| MoodOrchestrator | (neocortex MoodState) | Agent emotional state |
| DriveOrchestrator | — | Motivational drives |
| MemoryHygieneOrchestrator | CbrCaseMemoryStore | Memory consolidation |

These stores are silos. The mind map graph makes their connections explicit.

### 4.2 Integration Pattern

CDI observers on blocks' domain events create/update nodes and edges:

- `MentalStateSignal` → creates/updates belief nodes in the user's subgraph
- `EngagementSignal` → creates engagement edges between agent and user nodes
- `DriverEvent` → updates drive-related properties on agent nodes
- `NarrativeSynthesisTick` → creates narrative nodes with prose content, linked to
  participants
- `StrategyLearningTick` → creates strategy nodes linked to situations and users

The CBR stores continue to own domain-specific similarity retrieval. The graph adds
cross-system traversal — "what do I know about Alice?" traverses from Alice's node
through mental model edges, strategy edges, narrative edges, and engagement edges.

### 4.3 Curiosity Engine Integration

The mind map intelligence layer participates in `InnerLifeOrchestrator`'s tick loop.
On each tick, `MindMapAnalyzer` computes curiosity signals:

**Structural signals:**
- Sparse subgraphs — "I know Alice's name but nothing about her role"
- Orphan nodes — isolated knowledge with no connections
- Structural holes — dense clusters with no bridges between them
- Low clustering — a node's neighbors aren't connected to each other

**Quality signals:**
- Low-confidence clusters — many INFERRED/SPECULATED edges
- Contradiction clusters — conflicting current edges on the same node
- UNVALIDATED edges — vocabulary not yet governed
- Dangling NodeRefs — references to entities that may no longer exist

**Temporal signals:**
- Stale regions — nodes/edges not updated or confirmed recently
- Growth/decay rates — which subgraphs are expanding vs static
- Supersession chains — factual evolution over time

**Centrality signals:**
- Betweenness — bridge nodes worth knowing more about
- Degree — highly-connected entities worth keeping fresh

**Proximity signals:**
- Temporal proximity — nodes with future dates (events, deadlines, aspirations)
  act as attention magnets. As a date approaches, the curiosity engine
  intensifies knowledge-seeking in connected areas. "Visiting parents next
  Saturday" drives questions about the parents, the trip, what they want to
  discuss. After events pass, the engine checks: did it happen? what was the
  outcome?
- Spatial proximity — location-aware nodes. If the user is travelling to
  London, knowledge about London, people in London, London-based projects all
  get elevated.

A "calendar" is simply a query over temporally-marked nodes — no separate
calendar store needed. Future-dated nodes are regular graph nodes with temporal
properties that the analysis layer indexes for proximity-based prioritization.

These signals feed `CuriosityDrive` to generate questions, and feed
`MentalModelOrchestrator` to direct inference attention.

### 4.4 Affective Knowledge

Nodes and edges carry optional PAD-model annotations (pleasure, arousal, dominance)
representing the emotional character of the knowledge itself — not the agent's mood.
"Alice was promoted" carries positive pleasure. "Alice lost her job" carries negative
pleasure. The field is named `pleasure` — consistent with `MoodState.pleasure()`,
`MoodAttributeKeys.PLEASURE`, and `MoodModulatedRetrieval` throughout the existing
codebase. This enables:

- **Mood-congruent retrieval** — `MoodModulatedRetrieval` can weight graph results
  by affect alignment with the agent's current mood
- **Affect-aware curiosity** — the curiosity engine avoids probing sensitive topics
  when inappropriate
- **Emotional context** — narrative synthesis can assess the emotional arc of a
  relationship or situation

## 5. Trait System

### 5.1 SPI Boundary (`mindmap-api/`)

The SPI stores trait names as opaque `Set<String>` metadata on nodes (D9). It does
not know what trait names mean, how they are applied, or what interfaces they
represent.

The `TraitRule` SPI interface lives in `mindmap-api/` alongside `DerivedEdgeRule`
(D23 — extension point contracts belong in the SPI module):

```java
package io.casehub.neocortex.mindmap;

public interface TraitRule {
    String traitName();
    boolean matches(MindMapNode node, List<MindMapEdge> edges);
}
```

Rule implementations depend only on `mindmap-api/` (zero deps). The CDI module
discovers them; the intelligence module provides standard implementations.
`TraitRule.matches()` receives the node and its edges — the decorator queries the
graph and passes the results, so rules don't need direct store access (unlike
`DerivedEdgeRule.derive()` which receives the store — D23).

### 5.2 TraitApplicationDecorator (`mindmap/`)

`TraitApplicationDecorator` is a CDI `@Decorator @Priority(70)` on `MindMapStore`,
living in the `mindmap/` CDI module alongside `DerivedEdgeDecorator` (D22). It
discovers `TraitRule` beans via CDI `Instance<TraitRule>` — no-op when no rules are
on the classpath.

#### 5.2.1 Decorator Chain Ordering (D19)

The decorator chain from outermost to innermost:

```
ConfidenceDecay(50) → TraitApp(70) → DerivedEdge(80) → VocabNorm(90) → Store
```

- **VocabNorm(90)** is innermost — normalises edge types before they reach
  the store, so DerivedEdge rules and trait rules always see canonical types.
- **DerivedEdge(80)** — fires derived rules on the return path from
  `addEdge()`, using already-normalised types.
- **TraitApp(70)** — evaluates trait rules on the return path after
  DerivedEdge has stored the edge and fired derived rules. This ensures
  trait rules see the complete edge picture including derived edges.
- **ConfidenceDecay(50)** is outermost — intercepts query methods on the
  return path to apply time-based decay. Mutations pass through unmodified.

#### 5.2.2 Evaluation Trigger

The decorator intercepts four mutation methods:

| Method | Affected nodes |
|---|---|
| `addNode(input)` | The new node |
| `updateNode(nodeId, update)` | The updated node |
| `addEdge(input)` | Source node and target node |
| `removeEdge(edgeId)` | Source node and target node (looked up before removal) |

For each affected node, the decorator:
1. Queries the node's current state (`getNode`)
2. Queries the node's edges (`neighbors`)
3. Evaluates all `TraitRule` beans against the node + edges
4. Computes the delta: traits to add (rule matches, trait not present) and traits
   to retract (no rule matches, trait present)
5. If delta is non-empty, calls `delegate.updateNode()` with `traitsToAdd` /
   `traitsToRemove`

Rules do NOT fire on query methods — only on state changes.

**Performance:** cost is O(rules × mutations-per-user-action) — each user mutation
triggers evaluation of all rules for affected nodes. At agent scale (D25), with
a handful of rules and low-thousands of nodes, this completes in sub-millisecond
time. If rule count grows significantly, consider indexing rules by triggering
edge type or property key.

#### 5.2.3 Conflict Resolution

If multiple rules target the same trait on the same node, application wins over
retraction: a trait is applied if ANY rule's `matches()` returns true, retracted
only when NO rules match. This is conservative — the intelligence layer can always
retract explicitly via `traitsToRemove` on `NodeUpdate`.

#### 5.2.4 Cycle Prevention — Reentrancy Guard (D20)

A `ThreadLocal<Boolean>` reentrancy guard prevents recursive trait evaluation.
When trait evaluation is in progress, any mutations triggered BY the evaluation
(`delegate.updateNode` for trait changes, `delegate.addEdge` for trait-associated
edges) go through the decorator chain but skip trait re-evaluation:

```java
private static final ThreadLocal<Boolean> evaluating =
    ThreadLocal.withInitial(() -> false);

@Override
public String addEdge(EdgeInput input, String tenantId) {
    String edgeId = delegate.addEdge(input, tenantId);
    if (!evaluating.get()) {
        evaluating.set(true);
        try {
            evaluateTraitsForNode(input.sourceNodeId(), tenantId);
            evaluateTraitsForNode(input.targetNodeId(), tenantId);
        } finally {
            evaluating.set(false);
        }
    }
    return edgeId;
}
```

This means trait evaluation fires **once** per user-initiated mutation. Trait-
triggered edges get their derived edges (bounded by DerivedEdge's depth-3 counter),
but those derived edges don't trigger further trait evaluation. The cross-decorator
chain (trait → edge → trait → ...) is bounded at one trait evaluation level plus
DerivedEdge's depth limit.

**Trade-off:** If applying trait A triggers an edge whose derived edge would make
trait B applicable on a different node, trait B won't be discovered until the next
user-triggered mutation. Acceptable for V1 — multi-level trait chains are unusual
and can be addressed later.

### 5.3 Intelligence Module (`mindmap-intelligence/`)

New module. Depends on `mindmap-api/` (zero deps). Contains trait KNOWLEDGE while
`mindmap/` contains the trait ENGINE (D22).

#### 5.3.1 Trait Interfaces

Typed Java interfaces with accessors that map to node properties by convention
(method name = property key):

```java
package io.casehub.neocortex.mindmap.intelligence;

public interface Personable {
    Optional<String> birthday();
    Optional<String> role();
    Optional<String> email();
    Optional<String> phone();
}

public interface Projectlike {
    Optional<String> status();
    Optional<String> startDate();
    Optional<String> endDate();
    Optional<String> description();
}

public interface Organisational {
    Optional<String> industry();
    Optional<String> size();
    Optional<String> location();
}
```

These are pure marker/accessor interfaces — no logic, no dependencies. They define
the VOCABULARY of typed properties for their respective trait categories.

#### 5.3.2 Proxy Generation (D21)

JDK `java.lang.reflect.Proxy` with convention-based method dispatch:

```java
package io.casehub.neocortex.mindmap.intelligence;

public final class TraitProxy {

    public static <T> T as(MindMapNode node, Class<T> traitInterface) {
        if (!traitInterface.isInterface()) {
            throw new IllegalArgumentException("Trait must be an interface");
        }
        return traitInterface.cast(Proxy.newProxyInstance(
            traitInterface.getClassLoader(),
            new Class<?>[] { traitInterface },
            new TraitInvocationHandler(node)));
    }
}
```

The `TraitInvocationHandler` dispatches by method name:
- `methodName()` → `node.property(methodName)` → type conversion based on return type
- `String` → passthrough (property value or null)
- `Optional<String>` → `Optional.ofNullable(property value)`
- `Integer`, `Long`, `Double` (boxed only) → parse from string, null if absent
  or unparseable. Trait interface methods MUST use boxed types or `Optional`, not
  primitives — primitive return types would NPE on absent properties
- `equals`, `hashCode`, `toString` → delegate to node identity

Zero external deps. Convention-based mapping (method name = property key) matches
the Drools Traits model (§5.5). No compile-time verification that property keys
exist — the proxy returns null/empty for missing properties.

#### 5.3.3 Standard TraitRule Implementations

CDI beans implementing `TraitRule`, discovered by `TraitApplicationDecorator`:

```java
@ApplicationScoped
public class PersonableTraitRule implements TraitRule {
    @Override
    public String traitName() { return "Personable"; }

    @Override
    public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
        // A node is Personable if it has person-identifying properties
        // OR person-relationship edges
        boolean hasPersonProperties = node.property("birthday").isPresent()
            || node.property("role").isPresent()
            || node.property("email").isPresent();
        boolean hasPersonEdges = edges.stream()
            .anyMatch(e -> e.edgeType().equals("parent-of")
                || e.edgeType().equals("child-of")
                || e.edgeType().equals("works-at"));
        return hasPersonProperties || hasPersonEdges;
    }
}
```

Similar implementations for `ProjectlikeTraitRule` and `OrganisationalTraitRule`.

#### 5.3.4 Truth Maintenance

When evidence for a trait is retracted (property removed, edge deleted), the
`TraitApplicationDecorator` re-evaluates all rules for the affected node. If no
rule matches a previously-applied trait, the trait is retracted via
`delegate.updateNode(nodeId, NodeUpdate(...traitsToRemove=Set.of(traitName)...))`.

Truth maintenance is automatic — consumers don't invoke it. The decorator's
interception of `updateNode()` (property changes) and `removeEdge()` (edge
deletion) ensures re-evaluation on every state change.

#### 5.3.5 Compaction (Future)

When a dynamic property appears consistently on all nodes with a given trait,
it can be promoted from a dynamic property to a core column. The proxy layer
hides this migration — `TraitProxy.as(node, Personable.class).birthday()`
returns the same value regardless of whether `birthday` is a core field or a
dynamic property, because `MindMapNode.property(key)` provides unified access
(§3.2).

Compaction is a schema evolution concern — it requires Flyway migration and is
deferred to a future issue.

### 5.4 Module Dependencies

```
mindmap-api     ← TraitRule SPI, DerivedEdgeRule SPI
    ↑
mindmap         ← TraitApplicationDecorator @Priority(70)
    ↑              DerivedEdgeDecorator @Priority(80)
    ↑              (discovers rules via CDI Instance)
mindmap-intelligence ← TraitRule implementations
                       Trait interfaces (Personable, etc.)
                       TraitProxy (JDK Proxy generation)
```

Application modules can provide their own `TraitRule` beans by depending only on
`mindmap-api/`. The intelligence module provides the standard rules — it's a
library of reusable knowledge, not a required dependency.

### 5.5 Future Reconciliation with Drools

The trait system is intentionally modelled after Drools Traits but implemented
independently. A future integration could delegate trait management to Drools when
available, using the same interfaces and rule definitions.

## 6. LLM Entity/Relationship Extraction

### 6.1 Overview

`MindMapExtractor` is the LLM-powered extraction pipeline that converts
conversation text into graph structure. Given a single conversation turn
(one user message + optional assistant reply), it extracts entities (people,
projects, organisations, concepts), identifies relationships between them,
resolves matches against existing graph nodes, creates or updates nodes
and edges, and detects contradictions with existing knowledge.

The extractor lives in `mindmap-intelligence/` alongside the trait system.
It depends on `AgentProvider` (from `casehub-platform-agent-api`) for LLM
calls and `MindMapStore` for graph operations.

### 6.2 `MindMapExtractor` — Concrete Service

```java
package io.casehub.neocortex.mindmap.intelligence;

@ApplicationScoped
public class MindMapExtractor {

    private final MindMapStore store;
    private final Instance<AgentProvider> agentProviderInstance;

    @Inject
    public MindMapExtractor(MindMapStore store,
                            Instance<AgentProvider> agentProviderInstance) {
        this.store = store;
        this.agentProviderInstance = agentProviderInstance;
    }

    public ExtractionResult extract(String conversationText,
                                     String tenantId) { ... }

    public ExtractionResult extract(String conversationText,
                                     String tenantId,
                                     List<String> recentEntityNames) { ... }
}
```

The service is a concrete `@ApplicationScoped` bean (D27), not an SPI interface.
`AgentProvider` is already the pluggable abstraction for LLM backends — another
SPI layer adds no value.

**AgentProvider optionality (D34):** Injected via `Instance<AgentProvider>`
for graceful degradation. If unsatisfied or if the resolved provider returns
an empty stream (NoOpAgentProvider), `extract()` returns
`ExtractionResult.EMPTY`. The module works without an LLM backend — trait
rules and proxy still function independently.

**Two-argument vs three-argument form:** The two-argument form is the simple
entry point. The three-argument form accepts a list of recently-mentioned
entity names from the previous extraction (entity carry-forward, D26).
The two-argument form delegates to the three-argument form with an empty list.

### 6.3 Extraction Pipeline

```
┌─────────────────────────────────────────────────────────┐
│ extract(conversationText, tenantId, recentEntityNames)  │
│                                                         │
│  1. Retrieve graph context (D32)                        │
│     └─ resolveNode() per carry-forward name             │
│     └─ search() per extracted candidate term            │
│     └─ store.neighbors(nodeId) → edges per match        │
│                                                         │
│  2. Build LLM prompt                                    │
│     └─ System prompt: JSON extraction schema            │
│     └─ User prompt:                                     │
│        - Conversation text                              │
│        - Existing graph context (serialized nodes/edges)│
│        - Recently mentioned entities (carry-forward)    │
│                                                         │
│  3. Invoke AgentProvider (D33)                          │
│     └─ agentProvider.invoke(AgentSessionConfig)          │
│     └─ Collect TextDelta events → joined text           │
│     └─ Parse JSON response                              │
│                                                         │
│  4. Resolve subgraphs and apply (D28)                    │
│     └─ For each extracted entity:                       │
│        - Map entity type to SubgraphType                │
│        - findOrCreateSubgraph(type, tenantId)           │
│          → search existing subgraphs by type            │
│          → if none exists: createSubgraph()             │
│        - resolveNode(name, subgraphId, tenantId)        │
│        - If found: updateNode() with new properties     │
│        - If not found: addNode() with extracted data    │
│          and the resolved subgraphId                    │
│     └─ For each extracted relationship:                 │
│        - addEdge() (vocabulary normalization fires       │
│          transparently via decorator chain)              │
│     └─ Trait rules fire automatically via               │
│        TraitApplicationDecorator on the mutations       │
│                                                         │
│  5. Return ExtractionResult                             │
│     └─ Created/updated entities                         │
│     └─ Created relationships                            │
│     └─ Detected contradictions                          │
│     └─ Entity names for carry-forward                   │
└─────────────────────────────────────────────────────────┘
```

**Subgraph lifecycle — find-or-create by type:**

The extraction pipeline maintains one subgraph per `SubgraphType` per
tenant. This is a V1 simplification of the "mind maps that merge" mental
model — instead of one subgraph per entity (e.g., one for Alice, one for
Bob), all PERSON entities share a single PERSON subgraph, all PROJECT
entities share a single PROJECT subgraph, etc.

```java
// Tenant-aware cache: outer key is tenantId, inner key is SubgraphType
private final Map<String, Map<SubgraphType, String>> subgraphCache =
    new ConcurrentHashMap<>();

private String findOrCreateSubgraph(SubgraphType type, String tenantId) {
    Map<SubgraphType, String> tenantCache = subgraphCache
        .computeIfAbsent(tenantId, t -> {
            // Warm cache from existing subgraphs on first access per tenant
            Map<SubgraphType, String> warm = new ConcurrentHashMap<>();
            for (MindMapSubgraph sg : store.listSubgraphs(t)) {
                warm.putIfAbsent(sg.type(), sg.id());
            }
            return warm;
        });

    return tenantCache.computeIfAbsent(type, t ->
        store.createSubgraph(
            new SubgraphInput(t.name(), t, null), tenantId));
}
```

The cache is keyed by `(tenantId, SubgraphType)` to prevent cross-tenant
contamination (`MindMapExtractor` is `@ApplicationScoped` — the same bean
instance handles all tenants). On first access per tenant, the cache
warms from `listSubgraphs()` (§3.1) to avoid creating duplicate subgraphs
after application restart.

The `SubgraphType` mapping from extracted entity types is direct — the
LLM prompt (§6.5) uses the `SubgraphType` enum values. The conversion
is defensive: if the LLM returns an unrecognized type string, the
entity maps to `GENERAL` rather than failing the entire extraction:

```java
private SubgraphType parseSubgraphType(String type) {
    try {
        return SubgraphType.valueOf(type);
    } catch (IllegalArgumentException e) {
        LOG.fine("Unknown entity type '" + type + "', mapping to GENERAL");
        return SubgraphType.GENERAL;
    }
}
```

This prevents a single invalid entity type (e.g., the LLM returning
`"TOPIC"` or `"LOCATION"`) from discarding the entire extraction
result. `GENERAL` is the correct fallback — it is the catch-all
subgraph type for entities that don't fit a specific category.

Cross-subgraph edges (relationships between entities of different types)
are naturally "bridge edges" queryable via `bridgeEdges()`.

### 6.4 `ExtractionResult`

```java
public record ExtractionResult(
    List<ExtractedEntity> entities,
    List<ExtractedRelationship> relationships,
    List<Contradiction> contradictions,
    List<String> entityNames
) {
    public static final ExtractionResult EMPTY =
        new ExtractionResult(List.of(), List.of(), List.of(), List.of());
}

public record ExtractedEntity(
    String nodeId,          // the created or updated node ID
    String name,
    boolean created,        // true if new, false if updated existing
    String subgraphType,    // PERSON, PROJECT, RESEARCH_AREA, ORGANISATION, CONCEPT, GENERAL
    Map<String, String> properties
) {}

public record ExtractedRelationship(
    String edgeId,
    String sourceName,
    String targetName,
    String edgeType,        // vocabulary-normalised by decorator chain
    ConfidenceOrigin confidenceOrigin
) {}

public record Contradiction(
    String entityName,
    String property,        // e.g., "works-at"
    String existingValue,   // e.g., "Acme Corp"
    String extractedValue,  // e.g., "Initech"
    String description      // LLM-generated explanation
) {}
```

`entityNames` is the compact list of all entity names from this extraction,
used as carry-forward input to the next extraction call (D26).

### 6.5 LLM Prompt Design

**System prompt:**

```
You are a knowledge graph extraction agent. Given a conversation turn
and existing graph context, extract entities and relationships.

Respond with a JSON object:
{
  "entities": [
    {
      "name": "Alice Smith",
      "type": "PERSON",
      "properties": {"role": "engineer", "email": "alice@acme.com"},
      "confidence": "STATED"
    }
  ],
  "relationships": [
    {
      "source": "Alice Smith",
      "target": "Acme Corp",
      "type": "works-at",
      "confidence": "STATED"
    }
  ],
  "contradictions": [
    {
      "entity": "Alice Smith",
      "property": "works-at",
      "existing": "Acme Corp",
      "extracted": "Initech",
      "explanation": "The conversation says Alice left Acme and joined Initech"
    }
  ]
}

Entity types: PERSON, PROJECT, RESEARCH_AREA, ORGANISATION, CONCEPT, GENERAL.
Confidence levels: STATED (directly asserted), INFERRED (implied),
SPECULATED (guessed).

Rules:
- Extract only entities and relationships explicitly or strongly implied
  in the conversation text
- Use the existing graph context to avoid creating duplicates
- Use recently mentioned entities to resolve pronouns
- Flag contradictions when extracted facts conflict with existing graph
- Respond with valid JSON only — no additional text
```

**User prompt (template):**

```
Conversation:
{conversationText}

Existing graph context:
{serializedNodes}

Recently mentioned entities:
{recentEntityNames}
```

### 6.6 JSON Parsing

The JSON parser handles common LLM output issues:

- **Markdown wrapping** — strip ` ```json ` / ` ``` ` if present
- **Trailing text** — extract the first `{...}` block
- **Missing fields** — default empty arrays for missing `entities`,
  `relationships`, `contradictions`
- **Unknown fields** — ignore gracefully
- **Parse failure** — log warning, return `ExtractionResult.EMPTY`

No retry on parse failure in V1. The extraction call is cheap enough that
the next conversation turn will capture any missed entities. A retry budget
can be added if extraction miss rates warrant it.

### 6.7 Graph Context Retrieval (D32)

The extractor queries the graph for relevant context before building the
LLM prompt. Context retrieval uses two strategies — precise name
resolution first, then broad term search:

```java
private Map<String, List<MindMapEdge>> retrieveContext(
        String conversationText, String tenantId,
        List<String> recentEntityNames) {
    Map<String, List<MindMapEdge>> context = new LinkedHashMap<>();

    // Strategy 1: resolve carry-forward names (precise)
    for (String name : recentEntityNames) {
        MindMapNode node = store.resolveNode(name, null, tenantId);
        if (node != null) {
            context.put(node.id(),
                store.neighbors(node.id(), tenantId));
        }
    }

    // Strategy 2: search for candidate terms from conversation (broad)
    for (String term : extractCandidateTerms(conversationText)) {
        if (context.size() >= 20) break;
        List<MindMapNode> hits = store.search(
            new MindMapQuery(tenantId, null, term,
                             null, null, null, null, false, 5));
        for (MindMapNode node : hits) {
            context.computeIfAbsent(node.id(), id ->
                store.neighbors(id, tenantId));
        }
    }
    return context;
}
```

**Strategy 1 — name resolution** uses `resolveNode()` for exact
name/alias matching. This is the most reliable path for entity
resolution: carry-forward provides entity names from the previous
extraction, and `resolveNode()` matches them against the graph's name
and alias index. No false positives.

**Strategy 2 — term search** extracts candidate entity names from the
conversation text (capitalized word sequences, filtering common words
like "The", "I", "We") and searches for each individually.
`MindMapQuery.text` is a search query interpreted by the backend:
`InMemoryMindMapStore` does substring matching (sufficient for tests);
`SqliteMindMapStore` uses FTS5 `MATCH` with BM25 ranking (§7.2).
Individual terms match correctly under both strategies — unlike raw
conversation text, which would match nothing as a substring.

**Result deduplication:** `computeIfAbsent` on the context map ensures
each node appears at most once, even if found by both strategies.

**Cap at 20 context nodes** to bound token cost in the LLM prompt.
Carry-forward names (strategy 1) take priority over broad search
(strategy 2).

Serialization format for the prompt (compact, structured):

```
- Alice Smith [PERSON] (confidence: 0.95, traits: Personable)
  → works-at → Acme Corp [STATED]
  → parent-of → Bob Smith [INFERRED]
- Acme Corp [ORGANISATION] (confidence: 1.0, traits: Organisational)
  ← works-at ← Alice Smith [STATED]
```

### 6.8 Entity Carry-Forward (D26)

The `ExtractionResult.entityNames()` field contains the names of all entities
from the current extraction. The caller passes this list to the next
`extract()` call via the `recentEntityNames` parameter.

This solves the most common coreference pattern — a pronoun in the current
turn referring to an entity from the previous turn:

- Turn 1: "Alice got promoted at Acme" → extracts `["Alice", "Acme"]`
- Turn 2: "She mentioned leaving" → carry-forward provides `["Alice", "Acme"]`
  → LLM resolves "she" → Alice

The carry-forward is bounded (one turn of names only) and adds negligible
token cost. The caller (blocks tick loop) maintains the per-agent
last-extraction-result.

**Known V1 limitation:** one-turn carry-forward does not handle multi-turn
coreference ("She" in turn 5 referring to "Alice" from turn 2). The graph
context query (§6.7) partially compensates for already-persisted entities,
but newly extracted entities from earlier turns may not surface if their
names don't match the current text. Future options: sliding window of N
turns, or an explicit coreference resolution step using the graph as
context.

### 6.9 Concurrency Model (D28)

Extraction is single-threaded per agent, serialized by the blocks
orchestrator's per-agent `ReentrantLock` in the tick loop. The
resolve-before-create approach (D28) is safe under this guarantee.

**V1 scope:** extraction runs exclusively within the tick loop. REST
endpoints and manual imports are out of scope for V1. The tick loop's
per-agent `ReentrantLock` provides the serialization guarantee that makes
resolve-before-create safe.

**Non-tick-loop concurrency (future):** when extraction is exposed outside
the tick loop, the specific race is resolve-then-create non-atomicity —
two concurrent extractors can both resolve "Alice" as absent and both
create her. Serialization would need to be per-entity-name within a
tenant, not global. Transient duplicates would be detectable by
`MindMapAnalyzer` and resolvable via `mergeNodes()`, but concurrent
readers during the duplicate window would see incorrect traversal results.
This design is deferred until a non-tick-loop consumer is identified.

### 6.10 AgentProvider Invocation (D33)

```java
private String invokeLlm(String systemPrompt, String userPrompt) {
    AgentProvider provider = agentProviderInstance.get();

    try {
        List<AgentEvent> events = provider.invoke(
            AgentSessionConfig.of(systemPrompt, userPrompt))
                .collect().asList()
                .await().atMost(Duration.ofMinutes(2));

        // Check for LLM-reported errors
        boolean hasError = events.stream()
            .filter(AgentEvent.InvocationComplete.class::isInstance)
            .map(AgentEvent.InvocationComplete.class::cast)
            .anyMatch(AgentEvent.InvocationComplete::isError);
        if (hasError) {
            LOG.warn("LLM invocation completed with error flag");
            return null;
        }

        String text = events.stream()
            .filter(AgentEvent.TextDelta.class::isInstance)
            .map(AgentEvent.TextDelta.class::cast)
            .map(AgentEvent.TextDelta::text)
            .collect(Collectors.joining());

        if (text.isEmpty()) {
            LOG.warn("LLM returned empty response");
            return null;
        }

        return text;
    } catch (Exception e) {
        LOG.warn("LLM invocation failed", e);
        return null;
    }
}
```

The caller treats a `null` return as extraction failure and returns
`ExtractionResult.EMPTY`. Failures are logged but do not propagate —
the extraction call is cheap enough that the next conversation turn
will capture any missed entities.

**Failure modes handled:**
- `TimeoutException` — Mutiny timeout after 2 minutes
- `InvocationComplete.isError()` — LLM-reported error
- Empty response — no `TextDelta` events returned
- Network/transient failures — caught by the generic `Exception` handler

**Not retried in V1:** invocation-level failures (rate limiting, network
errors, model unavailability) are not retried. A retry budget can be added
if extraction miss rates warrant it.

One-shot `invoke()` per extraction (D33). Each call is stateless.
Session-based optimization (GE-20260707-4ea952) can be added later if
extraction frequency warrants it.

### 6.11 Contradiction Detection and Resolution (D30)

Contradictions are detected by the LLM during extraction — the existing
graph context in the prompt enables the LLM to identify conflicts. This
is complemented by `MindMapAnalyzer.contradictions()`, which detects
structural contradictions programmatically (multiple values for functional
edge types).

- **LLM detection** — fires at extraction time, catches semantic
  contradictions ("works at Acme" vs. "left Acme last month")
- **Programmatic detection** — fires during periodic graph analysis,
  catches structural contradictions (multiple `works-at` edges from
  the same node)

**Mutation semantics when contradictions are detected:**

Contradictions are **reported but not automatically resolved**. The
extraction pipeline applies additive mutations:

1. **New relationship IS applied** — the extracted edge is created with
   the LLM's assessed confidence (typically `STATED` or `INFERRED`).
2. **Old contradicting relationship is NOT removed** — the existing edge
   remains in the graph with its current confidence (subject to decay).
3. **Contradiction is returned** in `ExtractionResult.contradictions` for
   the caller to act on.
4. **Node properties are updated** — `updateNode()` overwrites properties
   with new values. The `Contradiction` record captures both old and new
   values for audit.

This means the graph temporarily holds both edges (e.g., Alice
`works-at → Acme` AND Alice `works-at → Initech`). This is intentional —
automatic resolution is dangerous because the LLM may incorrectly detect
a contradiction. The programmatic detector (`MindMapAnalyzer`) flags the
structural anomaly (multiple `works-at` edges from the same node) during
periodic analysis, and the curiosity engine can generate a resolution
question.

**Resolution paths (not V1):**
- Human confirmation via active learning question
- Temporal resolution: set `validUntil` on the old edge when the new edge
  has a clear temporal successor relationship
- Confidence-based pruning: the old edge decays naturally; if not
  re-confirmed, it eventually falls below the `minConfidence` threshold
  in queries

### 6.12 Testing

Tests use `TestAgentProvider` (GE-20260801-bcff35) — a static inner class
implementing `AgentProvider` that returns canned JSON responses:

```java
static class TestAgentProvider implements AgentProvider {
    private final String response;
    int invocationCount = 0;
    String lastUserPrompt;

    TestAgentProvider(String response) { this.response = response; }

    @Override
    public Multi<AgentEvent> invoke(AgentSessionConfig config) {
        invocationCount++;
        lastUserPrompt = config.userPrompt();
        return Multi.createFrom().items(
            new AgentEvent.TextDelta(response),
            new AgentEvent.InvocationComplete(
                100, 50, 0, 0, 0, 0.001, 500L, 400L, "test", 1, false));
    }

    @Override
    public AgentSession openSession(AgentSessionInit init) {
        throw new UnsupportedOperationException();
    }
}
```

Test scenarios:

- Extract entities from text → verify nodes created with correct names,
  types, properties
- Extract relationships → verify edges created with correct types
- Entity resolution — pre-populate graph with "Alice" → extract text
  mentioning "Alice" → verify existing node updated (not duplicated)
- Contradiction detection — pre-populate "works-at Acme" → extract
  "works at Initech" → verify contradiction in result
- Carry-forward — extract with recent entity names → verify pronoun
  resolution in subsequent extraction
- Empty/malformed JSON response → verify graceful degradation
- NoOpAgentProvider → verify ExtractionResult.EMPTY returned
- Properties applied → verify trait rules fire automatically (e.g.,
  adding "email" property triggers Personable trait)

### 6.13 Module Dependencies

```
mindmap-api     ← MindMapStore, MindMapNode, MindMapEdge, etc.
    ↑
mindmap-intelligence
    ├── TraitRule implementations (existing — #219)
    ├── Trait interfaces: Personable, Projectlike, Organisational (existing)
    ├── TraitProxy (existing)
    ├── MindMapExtractor (new — #220)
    ├── ExtractionResult, ExtractedEntity, ExtractedRelationship (new)
    ├── Contradiction (new)
    └── ExtractionJsonParser (new — internal)

Dependencies:
    mindmap-api (compile)
    quarkus-arc (compile)
    casehub-platform-agent-api (compile — for AgentProvider)
    smallrye-mutiny (compile — for Multi consumption)
    mindmap-inmem (test)
    junit-jupiter (test)
    assertj-core (test)
```

`casehub-platform-agent-api` is a new compile dependency for
mindmap-intelligence. It is a Tier 1 module (pure Java + CDI annotations)
with no heavy transitive dependencies.

## 7. Curiosity Engine

### 7.1 Overview

The curiosity engine computes prioritised curiosity signals from the mind map
graph. It consumes `MindMapAnalyzer`'s structural, quality, temporal, and
centrality computations, adds temporal proximity and affect-aware filtering,
and produces a ranked list of `CuriositySignal` records with generated
questions. These signals feed blocks' `CuriosityDrive` to drive
knowledge-seeking behavior.

The engine lives in `mindmap-intelligence/` alongside the extractor and
trait system. It depends only on `mindmap-api/` (for `MindMapStore` and
`MindMapAnalyzer`) — no AgentProvider dependency.

### 7.2 `CuriositySignalProvider` — SPI Interface

```java
package io.casehub.neocortex.mindmap.intelligence;

public interface CuriositySignalProvider {
    List<CuriositySignal> computeSignals(String tenantId,
                                          Set<String> recentEntityIds);
}
```

The SPI lives in `mindmap-intelligence/` (D36). `recentEntityIds` is
the set of node IDs from the most recent conversation extraction —
used for topical distance dampening (D41). Consumers pass an empty
set when no recent context is available.

### 7.3 `CuriositySignal`

```java
public record CuriositySignal(
    SignalCategory category,
    double score,           // [0.0, 1.0] after all dampening
    String targetNodeId,    // nullable — some signals are subgraph-level
    String targetSubgraphId,
    String question,        // template-generated natural language question
    String description      // human-readable explanation of the signal
) {}

public enum SignalCategory {
    STRUCTURAL,     // orphan nodes, sparse subgraphs, structural holes
    QUALITY,        // low confidence, contradictions, unvalidated edges, dangling refs
    TEMPORAL,       // stale nodes, supersession chains
    CENTRALITY,     // high-betweenness bridge nodes, high-degree hubs
    PROXIMITY       // approaching temporal events (attention magnets)
}
```

### 7.4 `CuriositySignalGenerator` — Implementation

```java
@ApplicationScoped
public class CuriositySignalGenerator implements CuriositySignalProvider {

    private final MindMapStore store;

    @Inject
    public CuriositySignalGenerator(MindMapStore store) {
        this.store = store;
    }

    @Override
    public List<CuriositySignal> computeSignals(String tenantId,
                                                 Set<String> recentEntityIds) {
        List<CuriositySignal> signals = new ArrayList<>();

        for (MindMapSubgraph sg : store.listSubgraphs(tenantId)) {
            collectStructuralSignals(sg, tenantId, signals);
            collectQualitySignals(sg, tenantId, signals);
            collectTemporalSignals(sg, tenantId, signals);
            collectCentralitySignals(sg, tenantId, signals);
        }
        collectProximitySignals(tenantId, signals);

        applyAffectDampening(signals, tenantId);
        applyTopicalDistanceDampening(signals, recentEntityIds, tenantId);

        signals.sort(Comparator.comparingDouble(CuriositySignal::score).reversed());
        return signals;
    }
}
```

### 7.5 Signal Generation

Each signal category maps to `MindMapAnalyzer` methods:

| Category | MindMapAnalyzer method | Signal generated when |
|---|---|---|
| STRUCTURAL | `orphanNodes()` | Node has zero edges |
| STRUCTURAL | `subgraphDensity()` | Density < 0.1 (sparse) |
| QUALITY | `lowConfidenceCluster()` | Ratio > 0.5 (majority low confidence) |
| QUALITY | `contradictions()` | Multiple targets for same edge type |
| QUALITY | `unvalidatedEdgeRatio()` | Ratio > 0.3 |
| TEMPORAL | `staleNodes()` | Nodes not updated in > 90 days |
| CENTRALITY | `betweennessCentrality()` | Top 3 bridge nodes per subgraph |
| CENTRALITY | `degreeCentrality()` | Top 3 high-degree nodes per subgraph |
| PROXIMITY | (direct query) | Nodes with `validFrom` in the future |

**Raw scores** before dampening:

- Structural: `1.0` for orphan nodes (maximum gap), density ratio for
  sparse subgraphs
- Quality: ratio of low-confidence/unvalidated/contradicting items
- Temporal: `min(1.0, staleDays / 180.0)` — linearly increasing staleness
- Centrality: normalized betweenness/degree score (0-1 range from analyzer)
- Proximity: `1.0 / (1.0 + daysUntilEvent / scale)` where `scale = 7.0` (D39)

### 7.6 Question Templates (D38)

Each signal type has a question template filled with entity/subgraph names:

```java
private static String generateQuestion(SignalCategory category,
                                         String nodeName, String detail) {
    return switch (category) {
        case STRUCTURAL -> "What is " + nodeName + "'s connection to other entities?";
        case QUALITY -> "Is the information about " + nodeName + " still accurate? " + detail;
        case TEMPORAL -> "Is " + nodeName + " still relevant? " + detail;
        case CENTRALITY -> "Tell me more about " + nodeName
            + " — it connects many areas of knowledge.";
        case PROXIMITY -> "What should I know about " + nodeName
            + " before " + detail + "?";
    };
}
```

Sparse subgraphs use a different template: "What else is part of {subgraph}?"

### 7.7 Temporal Proximity Signals (D39)

Nodes with `validFrom` in the future act as attention magnets. The
engine queries all nodes across all subgraphs for upcoming temporal
events:

```java
private void collectProximitySignals(String tenantId,
                                      List<CuriositySignal> signals) {
    Instant now = Instant.now();
    for (MindMapSubgraph sg : store.listSubgraphs(tenantId)) {
        for (MindMapNode node : store.nodesIn(sg.id(), tenantId)) {
            if (node.validFrom() != null && node.validFrom().isAfter(now)) {
                double daysUntil = Duration.between(now, node.validFrom())
                    .toDays();
                double score = 1.0 / (1.0 + daysUntil / 7.0);
                signals.add(new CuriositySignal(
                    SignalCategory.PROXIMITY, score,
                    node.id(), sg.id(),
                    generateQuestion(SignalCategory.PROXIMITY,
                        node.name(), formatDate(node.validFrom())),
                    "Approaching event: " + node.name()));
            }
            if (node.validUntil() != null && node.validUntil().isBefore(now)) {
                signals.add(new CuriositySignal(
                    SignalCategory.TEMPORAL, 0.8,
                    node.id(), sg.id(),
                    "Did " + node.name() + " happen? What was the outcome?",
                    "Past event: " + node.name()));
            }
        }
    }
}
```

### 7.8 Affect-Aware Dampening (D40)

Multiply each signal's score by an affect factor. PROXIMITY signals
bypass dampening entirely — time-critical signals should never be
suppressed by emotional valence.

```java
private void applyAffectDampening(List<CuriositySignal> signals,
                                    String tenantId) {
    for (int i = 0; i < signals.size(); i++) {
        CuriositySignal signal = signals.get(i);
        if (signal.category() == SignalCategory.PROXIMITY) continue;
        if (signal.targetNodeId() == null) continue;

        MindMapNode node = store.getNode(signal.targetNodeId(), tenantId);
        if (node != null && node.pleasure() != null && node.pleasure() < 0) {
            double factor = Math.max(0.1, 1.0 + node.pleasure());
            signals.set(i, new CuriositySignal(
                signal.category(), signal.score() * factor,
                signal.targetNodeId(), signal.targetSubgraphId(),
                signal.question(), signal.description()));
        }
    }
}
```

### 7.9 Topical Distance Dampening (D41)

Signals targeting nodes far from the most recent conversation entities
are dampened to prevent unbounded curiosity expansion.

```java
private void applyTopicalDistanceDampening(List<CuriositySignal> signals,
                                            Set<String> recentEntityIds,
                                            String tenantId) {
    if (recentEntityIds.isEmpty()) return;

    for (int i = 0; i < signals.size(); i++) {
        CuriositySignal signal = signals.get(i);
        if (signal.targetNodeId() == null) continue;
        if (recentEntityIds.contains(signal.targetNodeId())) continue;

        int distance = bfsDistance(signal.targetNodeId(),
                                   recentEntityIds, tenantId, 4);
        if (distance > 0) {
            double factor = 1.0 / (1.0 + distance);
            signals.set(i, new CuriositySignal(
                signal.category(), signal.score() * factor,
                signal.targetNodeId(), signal.targetSubgraphId(),
                signal.question(), signal.description()));
        }
    }
}

private int bfsDistance(String fromNodeId, Set<String> targetIds,
                        String tenantId, int maxDepth) {
    // BFS from fromNodeId, return shortest path to any targetId
    // Returns maxDepth + 1 if no path found within maxDepth
}
```

### 7.10 Testing

Tests use `InMemoryMindMapStore` with synthetic graphs:

- **Structural signals:** Create orphan nodes → verify STRUCTURAL signals
  generated with correct questions
- **Quality signals:** Create contradictions (multiple edges of same type)
  → verify QUALITY signals
- **Temporal signals:** Create stale nodes (updatedAt 180 days ago) →
  verify TEMPORAL signals with staleness description
- **Centrality signals:** Create hub node with many edges → verify
  CENTRALITY signal for high-degree node
- **Proximity signals:** Create node with `validFrom` 3 days from now →
  verify PROXIMITY signal with score ~0.70
- **Past events:** Create node with `validUntil` in the past → verify
  "did it happen?" signal
- **Affect dampening:** Create node with pleasure = -0.8, verify signal
  score dampened to 20%; verify PROXIMITY signals are NOT dampened
- **Topical distance:** Create graph with chain A→B→C→D, set A as recent
  entity → verify D's signal dampened by factor 1/(1+3)=0.25
- **Empty graph:** Verify empty signal list, no exceptions
- **Signal ordering:** Verify signals sorted by score descending

### 7.11 Module Dependencies

```
mindmap-api       ← MindMapStore, MindMapAnalyzer, MindMapNode, etc.
    ↑
mindmap-intelligence
    ├── CuriositySignalProvider (SPI interface)
    ├── CuriositySignal, SignalCategory (value types)
    ├── CuriositySignalGenerator (@ApplicationScoped implementation)
    ├── MindMapExtractor (existing — #220)
    └── Trait system (existing — #219)

No new Maven dependencies required — uses only mindmap-api and quarkus-arc
(both already present).
```

## 8. Storage Backends

### 8.1 In-Memory (`mindmap-inmem`)

`InMemoryMindMapStore` — `ConcurrentHashMap`-based implementation for tests.
`@Alternative @Priority(1)`. Supports all capabilities. Provides `clearAll()`
for test isolation.

### 8.2 SQLite (`mindmap-sqlite`)

`SqliteMindMapStore` — SQLite + HikariCP WAL + Flyway migrations. Production
backend for single-node deployments.

Schema:
```
nodes          — core columns + JSON properties blob
edges          — source, target, type, tier, confidence, temporal bounds, properties
aliases        — node_id, alias (unique per tenant)
subgraphs      — id, name, type, root_node_id
node_refs      — node_id, scheme, ref_id, qualifier
supersessions  — target_id, superseding_id, reason, timestamps
```

**Text search:** FTS5 virtual table `mindmap_fts` on node names and
properties, maintained by insert/update/delete triggers (following the
`memory-sqlite` pattern — GE-20260801-bcff35). The `search()` method
uses `JOIN mindmap_fts ON mindmap_fts.rowid = n.rowid WHERE mindmap_fts
MATCH ?` with `ORDER BY rank` for BM25 relevance ranking. Query text
is sanitised via `sanitiseForFts()` to strip FTS5 operator characters
before binding.

`InMemoryMindMapStore` uses simple substring matching on node names and
property values — sufficient for contract tests where stored text
includes the search term.

Indexes on edge type, source/target, subgraph membership.

### 8.3 Future Backends

- **TinkerPop/ArcadeDB** — if traversal complexity outgrows recursive CTEs
- **Qdrant** — if semantic similarity search over node content is needed
- **PostgreSQL** — if deployed alongside existing JPA infrastructure

The SPI insulates consumers from backend changes. The capability enum allows
backends to declare which operations they support.

## 9. Testing

### 9.1 Contract Tests (`mindmap-testing`)

`MindMapStoreContractTest` — abstract base class that all backends must pass.
Tests cover:

- Node CRUD (add, get, update, remove)
- Edge CRUD with vocabulary normalization
- Alias add/remove/resolve
- Merge (edge deduplication, alias union, trait union, subgraph reassignment)
- Subgraph creation and membership
- Bridge edge detection
- Neighbor traversal (all types, filtered by type)
- Text search
- Vocabulary registration (registered normalisation, unvalidated acceptance)
- Supersession/reinstatement lifecycle
- Tenant isolation (cross-tenant invisibility)
- Cascading erasure (node removes edges, aliases, refs)
- Subgraph erasure
- Confidence levels and decay
- NodeRef storage and retrieval
- Trait metadata storage
- Affective annotations
- Capability self-description

### 9.2 Integration Tests

Dedicated integration tests that verify cross-store bridging:

- An experience recorded via `ExperienceStream` → observer creates a graph node
  and edges → querying the graph returns the connected structure
- A mental model signal from blocks → observer creates belief nodes in user
  subgraph → traversal from user node reaches the beliefs
- NodeRef to a CBR case → case is superseded in CBR → dangling ref detected by
  analysis
- Vocabulary normalization decorator fires transparently on addEdge
- Derived edge rules fire (has-child → parent edge created) and truth maintenance
  retracts when evidence removed
- Trait rules fire on node mutation — trait applied when rule matches, retracted
  when no rules match
- Trait evaluation reentrancy guard — trait-triggered edges don't cause recursive
  trait evaluation
- Proxy generation — `TraitProxy.as(node, Personable.class)` reads properties
- Truth maintenance — property removal / edge deletion triggers trait retraction
- Cycle prevention — trait → edge → derived edge chain bounded by decorators
- LLM extraction — conversation text → entities and relationships created in graph
- Entity resolution — existing node matched and updated, not duplicated
- Contradiction detection — conflict between extracted and existing facts reported
- Carry-forward — pronoun resolution via recently-mentioned entity names
- Graceful degradation — NoOpAgentProvider returns ExtractionResult.EMPTY
- Curiosity signals — structural/quality/temporal/centrality/proximity signals
  generated from synthetic graphs
- Affect dampening — negative-pleasure nodes have signal scores dampened;
  PROXIMITY signals bypass dampening
- Topical distance — signals for distant nodes dampened by hop count
- Signal ordering — sorted by score descending after all dampening
- Empty graph — empty signal list, no exceptions

## 10. Module Coordinates

| Element | Value |
|---|---|
| groupId | `io.casehub` |
| Artifact prefix | `casehub-neocortex-mindmap-` |
| MindMap API | `casehub-neocortex-mindmap-api` |
| MindMap CDI | `casehub-neocortex-mindmap` |
| MindMap In-Memory | `casehub-neocortex-mindmap-inmem` |
| MindMap SQLite | `casehub-neocortex-mindmap-sqlite` |
| MindMap Testing | `casehub-neocortex-mindmap-testing` |
| MindMap Intelligence | `casehub-neocortex-mindmap-intelligence` |
| Root Java package | `io.casehub.neocortex.mindmap` |

## 11. ARC42STORIES Integration

### Journey

| Journey | Description | Chapters | Status |
|---|---|---|---|
| J6 Structural Knowledge | MindMap graph SPI — typed nodes, edges, vocabulary, intelligence | C13–C15 | Planned |

### Chapter Outline

| # | Chapter | Journey | Layers touched | Status |
|---|---|---|---|---|
| 13 | MindMap SPI + In-Memory + SQLite | J6 | L16, L17 | Planned |
| 14 | MindMap CDI + Decorators | J6 | L16, L17 | Planned |
| 15 | MindMap Intelligence | J6 | L18 | Planned |

ARC42STORIES.MD entries for J6, C13–C15, and L16–L18 are created as part
of the first implementation issue in each chapter (#214 creates L16/L17,
#219 creates L18). This follows the established pattern where chapter
entries are written at implementation time, not at spec time — they need
the concrete details (issues, key files, gotchas) that only emerge during
implementation.

### Layers

| Layer | Module | Tier |
|---|---|---|
| L16 MindMap SPI | `mindmap-api`, `mindmap-testing` | Pure Java, zero deps |
| L17 MindMap Runtime | `mindmap`, `mindmap-inmem`, `mindmap-sqlite` | CDI library / backends |
| L18 MindMap Intelligence | `mindmap-intelligence` | CDI library, requires AgentProvider |

## 12. Design Decisions

### No reactive SPI variant

The module-tier-structure protocol specifies: "Ship both a blocking SPI and a
reactive mirror (`Uni<>`) when the store is consumed from **both** contexts."

All identified MindMap consumers are blocking:
- `InnerLifeOrchestrator` — `@ApplicationScoped`, blocking tick loop with
  `ReentrantLock` per agent. Not on the Vert.x event loop.
- blocks CDI observers (`MentalStateSignal`, `EngagementSignal`) — synchronous
  CDI observers on worker threads.

A reactive variant will be added when a reactive consumer is identified,
following the established `@DefaultBean` bridge pattern (see L6 RAG SPI,
`BlockingToReactiveCaseRetriever`).

## References

- GE-20260630-815259 — Cross-repo SPI extends CDI displacement gotcha
- `CbrCaseMemoryStore` — standalone SPI pattern, supersession, outcome, schema registration
- `CaseMemoryStore` — tenant isolation, erasure, capability self-description
- `GraphCaseMemoryStore` / #185 — semantic graph query on text memories (complementary, not overlapping)
- `RetrievalAnalyzer` (rag-api) — pure computation analysis pattern
- blocks `InnerLifeOrchestrator` — tick-driven cognitive orchestration (blocking)
- blocks `MentalModelOrchestrator` — BDI mental model with decay and inference
- blocks `CuriosityDrive` — motivation for knowledge-seeking behavior
- blocks `MemoryHygieneOrchestrator` — memory consolidation and gap detection
- Drools Traits — dynamic trait application via proxy, truth maintenance
- GE-20260716-f292d3 — CDI decorator ordering gotcha (informed D19 chain ordering)
- GE-20260803-0c691f — CDI Instance<T> stubbing via JDK Proxy (informed D21)
- D19-D22 — Trait system design decisions (decorator ordering, reentrancy, proxy, module placement)
- D23-D25 — Review-surfaced decisions (SPI boundary, atomicity, scale assumption)
- MoodState / MoodModulatedRetrieval — PAD model for mood-congruent recall
- `CbrOutcome` — numeric confidence with categorical provenance (pattern for §3.10)
- GE-20260801-0aee7e — AgentEvent sealed hierarchy and blocking text extraction pattern
- GE-20260801-bcff35 — Mockito-free TestAgentProvider inner class pattern
- GE-20260810-b1da3b — Structured JSON output via system prompt (extraction output format)
- GE-20260707-4ea952 — AgentProvider.openSession() persistent session (future optimization)
- GE-20260810-804c58 — AgentProvider CDI tiering (NoOp < ChatModel < Claude)
- D26-D34 — LLM extraction design decisions (input granularity, service shape, resolution, output format, contradictions, pipeline, context gathering, invocation, optionality)
- D35 — AbstractForwardingMindMapStore (review-surfaced, decorator boilerplate reduction) — tracked as #223
- `PipelineProvisioner.provisionAiReview()` — existing AgentProvider consumption pattern
- `CuriosityDrive` (blocks) — consumes curiosity signals via DriveSource.evaluate()
- `DriveSource` / `DriveIntensity` / `DriveAxis` — blocks drive integration types
- `MindMapAnalyzer` — 8 static utility methods providing raw graph signals
- D36-D41 — Curiosity engine design decisions (integration, signal model, question templates, temporal proximity, affect dampening, cycle-breaking)

# MindMap SPI — Design Specification

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

## 2. Architecture

### 2.1 Module Structure

New top-level module family, parallel to `memory-*`, `rag-*`, `inference-*`:

```
mindmap-api/          — SPI + value types (pure Java, zero deps)
mindmap/              — CDI wiring, NoOp default, decorators (vocabulary normalization,
                        derived edge rules)
mindmap-inmem/        — In-memory adapter for tests
mindmap-sqlite/       — SQLite adapter (day-one production backend)
mindmap-testing/      — Contract test suite + integration test scenarios
mindmap-intelligence/ — LLM extraction, gap detection, active learning, trait proxy,
                        graph analysis, curiosity engine
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
- Vocabulary normalization — alias resolution on every `addEdge()`
- Derived edge insertion — forward-chaining rules fire on edge creation
  (e.g., has-child → infer parent, father/mother)
- Confidence decay — applied at query time via decorator

**Explicit (mindmap-intelligence module, invoked by consumers):**
- LLM-based entity/relationship extraction from conversation
- Gap detection and curiosity signal generation
- Active learning question generation
- Contradiction analysis and resolution prompts
- Trait proxy generation and truth maintenance
- Graph analysis and index maintenance

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
    void removeNode(String nodeId, String tenantId);

    // --- Edges ---
    String addEdge(EdgeInput input, String tenantId);
    MindMapEdge getEdge(String edgeId, String tenantId);
    void removeEdge(String edgeId, String tenantId);

    // --- Aliases ---
    void addAlias(String nodeId, String alias, String tenantId);
    void removeAlias(String nodeId, String alias, String tenantId);
    MindMapNode resolveNode(String nameOrAlias, String subgraphId,
                            String tenantId);

    // --- Merge ---
    MergeResult mergeNodes(String keepNodeId, String removeNodeId,
                           String tenantId);

    // --- Subgraphs ---
    String createSubgraph(SubgraphInput input, String tenantId);
    MindMapSubgraph getSubgraph(String subgraphId, String tenantId);
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

    // --- Capabilities ---
    Set<MindMapCapability> capabilities();
    void requireCapability(MindMapCapability capability);
}
```

Every mutating and querying method requires `tenantId` for tenant isolation.
Implementations must enforce tenant boundaries — a node in tenant A is invisible
to queries in tenant B.

### 3.2 Node Model — Hybrid Core + Dynamic Properties

```java
public interface MindMapNode {
    // Core fields — always present, column-backed, indexed
    String id();
    String name();
    String subgraphId();
    ConfidenceLevel confidence();
    String provenance();
    Instant createdAt();
    Instant updatedAt();
    Instant confirmedAt();       // last explicit confirmation (resets decay)
    Set<String> traits();        // applied trait names (opaque to SPI)
    Set<NodeRef> refs();         // references to entities in other stores

    // Affective metadata — optional
    Double valence();            // [-1, 1] positive/negative
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
    ConfidenceLevel confidence();
    String provenance();
    Instant createdAt();
    Instant updatedAt();
    Instant validFrom();         // nullable — temporal bound start
    Instant validUntil();        // nullable — temporal bound end

    // Affective metadata — optional
    Double valence();
    Double arousal();
    Double dominance();

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
    ConfidenceLevel confidence,
    String provenance,
    Set<String> traits,
    Set<NodeRef> refs,
    Double valence,
    Double arousal,
    Double dominance,
    Map<String, String> properties
) {}

public record NodeUpdate(
    String name,              // nullable — only update if non-null
    ConfidenceLevel confidence,
    Set<String> traitsToAdd,
    Set<String> traitsToRemove,
    Set<NodeRef> refsToAdd,
    Set<NodeRef> refsToRemove,
    Double valence,
    Double arousal,
    Double dominance,
    Map<String, String> propertiesToSet,
    Set<String> propertiesToRemove
) {}

public record EdgeInput(
    String sourceNodeId,
    String targetNodeId,
    String edgeType,
    ConfidenceLevel confidence,
    String provenance,
    Instant validFrom,
    Instant validUntil,
    Double valence,
    Double arousal,
    Double dominance,
    Map<String, String> properties
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
definitions. The store normalises alias edge types to their canonical form on
`addEdge()`. Unregistered types are accepted but stored with
`ValidationTier.UNVALIDATED`.

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
    ConfidenceLevel minConfidence,  // nullable
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
    Set<String> traitsMerged
) {}
```

Merge keeps `keepNodeId`, removes `removeNodeId`, unions their edges (deduplicating
by source+target+edgeType), unions aliases, unions traits, and reassigns subgraph
membership to the surviving node's subgraph.

### 3.10 Confidence and Decay

```java
public enum ConfidenceLevel {
    STATED,       // directly asserted by a source
    INFERRED,     // derived by rules from other knowledge
    SPECULATED    // LLM-suggested, not confirmed
}
```

Decay is applied at query time. Each edge type can declare a
`defaultDecayHalfLifeDays` in its vocabulary definition. The decay decorator
reduces effective confidence based on time since `confirmedAt`. Explicit
confirmation (via `updateNode` setting a new `confirmedAt`) resets the clock.

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

Nodes and edges carry optional PAD-model annotations (valence, arousal, dominance)
representing the emotional character of the knowledge itself — not the agent's mood.
"Alice was promoted" carries positive valence. "Alice lost her job" carries negative
valence. This enables:

- **Mood-congruent retrieval** — `MoodModulatedRetrieval` can weight graph results
  by affect alignment with the agent's current mood
- **Affect-aware curiosity** — the curiosity engine avoids probing sensitive topics
  when inappropriate
- **Emotional context** — narrative synthesis can assess the emotional arc of a
  relationship or situation

## 5. Trait System

### 5.1 SPI Boundary

The SPI stores trait names as opaque `Set<String>` metadata on nodes. It does not
know what trait names mean, how they are applied, or what interfaces they represent.

### 5.2 Intelligence Layer (mindmap-intelligence)

The intelligence layer owns:

- **Trait interfaces** — Java interfaces (`Personable`, `Projectlike`,
  `Organisational`) with typed accessors that read from node properties
- **Proxy generation** — creates runtime proxies that implement trait interfaces,
  abstracting over core fields and dynamic properties
- **Forward-chaining rules** — determine when traits should be applied or retracted
  based on node properties and edges. "If a node has 'birthday' property and edges
  of type 'parent-of', apply Personable trait."
- **Truth maintenance** — when the evidence for a trait is retracted (e.g., the
  'birthday' property is removed), the trait is automatically retracted
- **Compaction** — over time, when a property appears consistently on all nodes
  with a given trait, it can be promoted from dynamic properties to a core field.
  The proxy hides this migration from consumers.

### 5.3 Future Reconciliation with Drools

The trait system is intentionally modelled after Drools Traits but implemented
independently. A future integration could delegate trait management to Drools when
available, using the same interfaces and rule definitions.

## 6. Storage Backends

### 6.1 In-Memory (`mindmap-inmem`)

`InMemoryMindMapStore` — `ConcurrentHashMap`-based implementation for tests.
`@Alternative @Priority(1)`. Supports all capabilities. Provides `clearAll()`
for test isolation.

### 6.2 SQLite (`mindmap-sqlite`)

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

FTS5 index on node names and properties for text search. Indexes on edge type,
source/target, subgraph membership.

### 6.3 Future Backends

- **TinkerPop/ArcadeDB** — if traversal complexity outgrows recursive CTEs
- **Qdrant** — if semantic similarity search over node content is needed
- **PostgreSQL** — if deployed alongside existing JPA infrastructure

The SPI insulates consumers from backend changes. The capability enum allows
backends to declare which operations they support.

## 7. Testing

### 7.1 Contract Tests (`mindmap-testing`)

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

### 7.2 Integration Tests

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

## 8. Module Coordinates

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

## References

- GE-20260630-815259 — Cross-repo SPI extends CDI displacement gotcha
- `CbrCaseMemoryStore` — standalone SPI pattern, supersession, outcome, schema registration
- `CaseMemoryStore` — tenant isolation, erasure, capability self-description
- `RetrievalAnalyzer` (rag-api) — pure computation analysis pattern
- blocks `InnerLifeOrchestrator` — tick-driven cognitive orchestration
- blocks `MentalModelOrchestrator` — BDI mental model with decay and inference
- blocks `CuriosityDrive` — motivation for knowledge-seeking behavior
- blocks `MemoryHygieneOrchestrator` — memory consolidation and gap detection
- Drools Traits — dynamic trait application via proxy, truth maintenance
- MoodState / MoodModulatedRetrieval — PAD model for mood-congruent recall

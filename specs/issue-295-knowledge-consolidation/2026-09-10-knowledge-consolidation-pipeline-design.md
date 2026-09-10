# Knowledge Consolidation Pipeline — Design Spec

**Date:** 2026-09-10
**Epic:** #295 (Knowledge Consolidation Pipeline — multi-phase conversation-to-knowledge processing)
**Children:** #296 (conversation bridge), #297 (consolidation scheduler), #298 (access-frequency tracking), #299 (community summaries), #300 (merge detection)
**Status:** Draft

---

## 1. Problem Statement

The Thing model (#285) provides the foundational knowledge representation — Things with types, properties, traits, and edges. But there is no pipeline that POPULATES this model from raw conversation, then progressively enriches, consolidates, and optimizes it for retrieval.

MindMapExtractor exists but is a standalone LLM extraction call — no orchestration, no scheduling, no post-extraction consolidation. The knowledge graph accumulates nodes without any background maintenance: duplicates persist, low-value nodes never decay, clusters of related knowledge are never summarized, and retrieval has no frequency signal to prioritize results.

### 1.1 Cognitive Science Inspiration

Memory consolidation during sleep: raw experiences are reorganized into structured knowledge. Key references: Mem0 "Dream" (background consolidation), SCM (sleep-consolidated memory mapping biological principles to AI), Graphiti/Zep (incremental temporal KG construction), Park et al. "Generative Agents" (composite retrieval scoring), Bjorks' New Theory of Disuse (storage strength vs retrieval strength).

### 1.2 Design Principles

- **Three-speed model.** Real-time capture → near-time enrichment → background consolidation. Each speed has different latency requirements and different infrastructure.
- **Reuse over reinvent.** DraftHouse handles cleanup. MindMapExtractor handles extraction. The decorator stack handles near-time enrichment. This pipeline provides orchestration and background phases.
- **Platform-level capability.** The bridge and scheduler live in neocortex (mindmap-intelligence), not in any application. Any app that has conversation-like flows can use them.
- **Non-persistent scheduling.** The knowledge graph is the durable layer. The scheduler is stateless — if the JVM restarts, it re-derives work from graph state.

## 2. Architecture

### 2.1 Three-Speed Processing Model

| Speed | When | What happens | Owner |
|-------|------|-------------|-------|
| **Real-time** | During conversation | DraftHouse NotesPipeline cleans raw text → ConversationBridge segments into topical chunks (rule-based, no LLM), creates initial "general" Things via MindMapStore, fires `ExtractionRequested` CDI event | DraftHouse (thin adapter) + neocortex (bridge) |
| **Near-time** | On `ExtractionRequested` event + on every addNode/addEdge | MindMapExtractor enriches initial nodes via LLM extraction (async, triggered by CDI event). DerivedEdgeDecorator fires forward-chaining rules, TraitRules evaluate traits on every mutation. | neocortex (extractor + decorator stack) |
| **Background** | Idle periods (≥1 min no writes) | ConsolidationScheduler runs 4 phases: access-frequency, merge detection, community summaries, curiosity refresh | neocortex (mindmap-intelligence) |

### 2.2 Module Layout

All new components live in `mindmap-intelligence`, which already owns MindMapExtractor, CuriositySignalGenerator, and TypeRegistry. No new modules.

```
mindmap-intelligence/
  src/main/java/io/casehub/neocortex/mindmap/intelligence/
    ConversationBridge.java            — fast rule-based segmentation, creates initial nodes
    SegmentationResult.java            — result record (createdNodeIds, segmentCount)
    TextSegment.java                   — record (title, body, topic)
    ExtractionRequested.java           — CDI event record for async LLM enrichment
    ExtractionRequestedObserver.java   — @ObservesAsync, invokes MindMapExtractor
    consolidation/
      ConsolidationScheduler.java      — @Scheduled, idle guard, tryLock, phase orchestration
      ConsolidationPhase.java          — SPI: single phase contract
      AccessFrequencyPhase.java        — flush write-behind counters (no decay — read-time projection)
      MergeDetectionPhase.java         — Jaro-Winkler + optional embedding
      CommunitySummaryPhase.java       — k-core clustering + LLM summary
      CuriosityRefreshPhase.java       — delegates to CuriositySignalGenerator
      RetrievalAccessTracker.java      — in-memory ConcurrentHashMap, recordAccess(), swapAndReset()
      AccessSnapshot.java              — record (counts, lastAccessTimes)
      MergeCandidate.java              — scored candidate record
      KCore.java                       — cluster record (nodeIds + density)
  
mindmap/
  src/main/java/io/casehub/neocortex/mindmap/runtime/
    IdleTracker.java                   — @ApplicationScoped, volatile lastWrite timestamp
    MindMapStoreIdleTracker.java       — @Decorator extending AbstractForwardingMindMapStore,
                                         writes to IdleTracker on store mutations
```

### 2.3 Dependency Direction

```
mindmap-intelligence (new: ConversationBridge, ConsolidationScheduler, phases)
    ↓ depends on
mindmap (new: IdleTracker, MindMapStoreIdleTracker decorator)
    ↓ depends on
mindmap-api (MindMapStore SPI, MindMapNode, MindMapQuery)

DraftHouse KnowledgeFacet (thin adapter, application tier)
    ↓ depends on
mindmap-intelligence (ConversationBridge)
```

IdleTracker lives in `mindmap` (not `mindmap-intelligence`) to avoid a circular Maven dependency: `mindmap-intelligence → mindmap` already exists; placing IdleTracker in `mindmap-intelligence` would require `mindmap → mindmap-intelligence` for the decorator to inject it.

## 3. ConversationBridge (#296)

### 3.1 Design — Fast Segmentation + Async Enrichment

ConversationBridge is a **fast, rule-based segmentation layer** — no LLM. It segments cleaned text into topical chunks, creates initial "general" Things in MindMapStore, records access for all touched nodes, and fires a CDI event to trigger MindMapExtractor asynchronously for enrichment.

This separation is the core of the three-speed model: the user sees initial nodes immediately (real-time), while LLM enrichment happens asynchronously (near-time).

### 3.2 SPI

```java
package io.casehub.neocortex.mindmap.intelligence;

@ApplicationScoped
public class ConversationBridge {

    private final MindMapStore store;
    private final RetrievalAccessTracker accessTracker;
    private final Event<ExtractionRequested> extractionEvent;

    @Inject
    public ConversationBridge(MindMapStore store,
                              Instance<RetrievalAccessTracker> accessTracker,
                              Event<ExtractionRequested> extractionEvent) {
        this.store = store;
        this.accessTracker = accessTracker.isResolvable()
                             ? accessTracker.get() : null;
        this.extractionEvent = extractionEvent;
    }

    public SegmentationResult process(String cleanedText, String tenantId,
                                       List<String> recentEntityNames,
                                       PrincipalId principalId) {
        if (cleanedText == null || cleanedText.isBlank()) {
            return SegmentationResult.EMPTY;
        }

        // 1. Segment text into topical chunks (rule-based, no LLM)
        List<TextSegment> segments = segment(cleanedText);

        // 2. Find or create the GENERAL subgraph
        String subgraphId = store.listSubgraphs(tenantId).stream()
            .filter(sg -> sg.type() == SubgraphType.GENERAL)
            .map(MindMapSubgraph::id)
            .findFirst()
            .orElseGet(() -> store.createSubgraph(
                new SubgraphInput("GENERAL", SubgraphType.GENERAL, null),
                tenantId));

        // 3. Create initial "general" nodes for each segment
        List<String> createdNodeIds = new ArrayList<>();
        for (TextSegment seg : segments) {
            String nodeId = store.addNode(
                NodeInput.of(seg.title(), subgraphId)
                    .withConfidence(MindMapConfidenceDefaults.forOrigin(
                        ConfidenceOrigin.STATED, Instant.now()))
                    .withProvenance("conversation-bridge")
                    .withPrincipalId(principalId)
                    .withProperties(Map.of(
                        "body", seg.body(),
                        "topic", seg.topic())),
                tenantId);
            createdNodeIds.add(nodeId);
        }

        // 4. Record access for all created nodes
        if (accessTracker != null) {
            createdNodeIds.forEach(accessTracker::recordAccess);
        }

        // 5. Fire async event for near-time LLM enrichment
        extractionEvent.fireAsync(
            new ExtractionRequested(cleanedText, tenantId,
                recentEntityNames, createdNodeIds));

        return new SegmentationResult(createdNodeIds, segments.size());
    }
}
```

Subgraph lookup uses `store.listSubgraphs()` + `store.createSubgraph()` (the existing MindMapStore SPI). `findOrCreateSubgraph` is a private helper in MindMapExtractor — promoting it to a default method on MindMapStore is a follow-up concern, not part of this spec.

Node creation uses `NodeInput.of(name, subgraphId)` with `with*()` chaining — the actual NodeInput API. Segment nodes are assigned `ConfidenceOrigin.STATED` (confidence 1.0 — the user literally said the words), provenance `"conversation-bridge"`, and the caller's `PrincipalId`.

### 3.3 Text Segmentation

`segment()` is a fast, rule-based method: split on paragraph boundaries, detect topic shifts via keyword overlap between consecutive paragraphs, and generate a title from the first sentence or dominant noun phrase. No LLM call. Complexity: O(N) in text length.

### 3.4 ExtractionRequested Event + Async Observer

```java
public record ExtractionRequested(
    String cleanedText,
    String tenantId,
    List<String> recentEntityNames,
    List<String> segmentNodeIds
) {}
```

The `segmentNodeIds` field carries the IDs of segment nodes created by ConversationBridge. After extraction, the observer supersedes these segments with the extracted entities — segment nodes served as fast placeholders; entity nodes are the canonical knowledge representation.

An `@ObservesAsync ExtractionRequested` observer in mindmap-intelligence invokes `MindMapExtractor.extract()` — this runs on a worker thread, not the caller's thread. The extractor creates typed entity nodes from LLM extraction.

```java
@ApplicationScoped
public class ExtractionRequestedObserver {

    private final MindMapExtractor extractor;
    private final MindMapStore store;
    private final RetrievalAccessTracker accessTracker;

    void onExtractionRequested(@ObservesAsync ExtractionRequested event) {
        var result = extractor.extract(
            event.cleanedText(), event.tenantId(), event.recentEntityNames());

        // Record access for all entities (created and referenced)
        if (accessTracker != null) {
            result.entities().stream()
                .map(ExtractedEntity::nodeId)
                .forEach(accessTracker::recordAccess);
        }

        // Supersede segment nodes — extraction entities replace fast placeholders
        List<String> createdEntityIds = result.entities().stream()
            .filter(ExtractedEntity::created)
            .map(ExtractedEntity::nodeId)
            .toList();
        if (!createdEntityIds.isEmpty()) {
            for (String segmentId : event.segmentNodeIds()) {
                store.supersede(segmentId, createdEntityIds.getFirst(),
                    "llm-extraction", event.tenantId());
            }
        }
        // If extraction yields no new entities, segment nodes persist
        // as the best available representation.
    }
}
```

**Segment → entity lifecycle:** ConversationBridge creates segment nodes immediately (user sees fast feedback). When MindMapExtractor completes asynchronously, the observer supersedes segment nodes via `store.supersede()`. Superseded nodes are logically replaced — they don't appear in normal queries but remain traceable via `getSupersessionStatus()`. If extraction fails or produces no entities, segment nodes persist as the best available representation. This uses the existing supersession SPI — no new mechanisms required.

### 3.5 DraftHouse Integration

DraftHouse provides a thin `KnowledgeFacet` adapter:

```java
public class KnowledgeFacet implements Facet {
    @Override public String name() { return "knowledge"; }

    @Override public List<ArtifactSpec> inputs() {
        return List.of(new ArtifactSpec("notes/*.md", "Cleaned note"));
    }

    @Override public List<ArtifactSpec> outputs() {
        return List.of(new ArtifactSpec("extraction-report.json", "Extraction result"));
    }
}
```

The `NotesPipelineObserver` chains: `TranscriptReady` → `NotesPipeline.process()` → `ConversationBridge.process()` → graph mutations. The KnowledgeFacet is classpath-activated — DraftHouse without neocortex on the classpath continues to work normally with notes only.

### 3.6 What ConversationBridge Does NOT Do

- **Cleanup.** That's DraftHouse NotesPipeline's job. The bridge accepts already-cleaned text.
- **LLM extraction.** That's MindMapExtractor's job, triggered asynchronously via `ExtractionRequested` CDI event. The bridge does rule-based segmentation only.
- **Near-time enrichment.** DerivedEdgeDecorator and TraitRules fire automatically when nodes/edges are added. The bridge doesn't need to trigger them.
- **Background consolidation.** The scheduler runs independently on a timer.

## 4. ConsolidationScheduler (#297)

### 4.1 Lifecycle

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

@ApplicationScoped
public class ConsolidationScheduler {

    private final List<ConsolidationPhase> phases;
    private final IdleTracker idleTracker;
    private final CaseMemoryStore memoryStore;
    private final CuriositySignalGenerator curiosityGenerator;
    private final ReentrantLock lock = new ReentrantLock();

    @Inject
    ConsolidationScheduler(Instance<ConsolidationPhase> phases,
                           IdleTracker idleTracker,
                           CaseMemoryStore memoryStore,
                           Instance<CuriositySignalGenerator> curiosityGenerator) {
        this.phases = phases.stream()
            .sorted(Comparator.comparingInt(p ->
                Optional.ofNullable(p.getClass().getAnnotation(Priority.class))
                        .map(Priority::value).orElse(Integer.MAX_VALUE)))
            .toList();
        this.idleTracker = idleTracker;
        this.memoryStore = memoryStore;
        this.curiosityGenerator = curiosityGenerator.isResolvable()
            ? curiosityGenerator.get() : null;
    }

    @Scheduled(every = "${casehub.consolidation.interval:5m}")
    void tick() {
        if (!lock.tryLock()) return;
        try {
            if (!idleTracker.isIdle(Duration.ofMinutes(1))) return;
            if (!memoryStore.capabilities()
                    .contains(MemoryCapability.DISCOVER_TENANTS)) {
                return;
            }

            for (String tenantId : memoryStore.discoverTenants(null, null)) {
                for (ConsolidationPhase phase : phases) {
                    try {
                        phase.run(tenantId, subgraphPriority(tenantId));
                    } catch (Exception e) {
                        LOG.log(WARNING, "Phase " + phase.name()
                                + " failed for tenant " + tenantId, e);
                    }
                }
            }
        } finally {
            lock.unlock();
        }
    }

    private List<String> subgraphPriority(String tenantId) {
        if (curiosityGenerator == null) return List.of();
        return curiosityGenerator.computeSignals(tenantId, Set.of()).stream()
            .map(CuriositySignal::targetSubgraphId)
            .filter(Objects::nonNull)
            .distinct()
            .toList();
    }
}
```

The scheduler follows the `MemoryRetentionScheduler` pattern: check `capabilities().contains(DISCOVER_TENANTS)` before calling `discoverTenants(null, null)`. Both null → all tenants. The `@Scheduled` context has no `CurrentPrincipal`, which is the same privilege model as existing retention schedulers.

CuriositySignalGenerator provides subgraph priority ordering — phases that iterate subgraphs process the highest-signal subgraphs first, so the per-pass cap (max-per-pass) focuses effort where it matters most.

### 4.2 ConsolidationPhase SPI

```java
public interface ConsolidationPhase {
    String name();
    void run(String tenantId, List<String> subgraphPriority);
}
```

Phases are injected as `Instance<ConsolidationPhase>`, sorted by `@Priority` annotation value at construction time into a `List<ConsolidationPhase>` (the scheduler's runtime field). This sorting is done explicitly in the constructor (portable CDI) rather than relying on Quarkus ArC's implicit priority ordering. Each phase is independently testable and can be disabled via `@IfBuildProperty`.

The `subgraphPriority` parameter provides a curiosity-signal-ordered list of subgraph IDs. Phases that iterate subgraphs should process subgraphs in this order, then process any remaining subgraphs not in the list. This ensures the per-pass cap (max-per-pass) focuses effort on the highest-priority regions.

### 4.3 IdleTracker and MindMapStoreIdleTracker

The idle guard is split into two beans: `IdleTracker` (shared state) and `MindMapStoreIdleTracker` (decorator that writes to it). The decorator cannot be injected directly by its own type — CDI decorators wrap the delegate. The scheduler injects `IdleTracker`; the decorator injects `IdleTracker` and updates it on writes.

```java
package io.casehub.neocortex.mindmap.runtime;

@ApplicationScoped
public class IdleTracker {
    private volatile Instant lastWrite = Instant.EPOCH;

    public void recordWrite() { lastWrite = Instant.now(); }

    public boolean isIdle(Duration threshold) {
        return Duration.between(lastWrite, Instant.now()).compareTo(threshold) > 0;
    }
}
```

```java
package io.casehub.neocortex.mindmap.runtime;

@Decorator
@Priority(30)
public class MindMapStoreIdleTracker extends AbstractForwardingMindMapStore {

    private final IdleTracker idleTracker;

    @Inject
    public MindMapStoreIdleTracker(@Delegate @Any MindMapStore delegate,
                                    IdleTracker idleTracker) {
        super(delegate);
        this.idleTracker = idleTracker;
    }

    @Override
    public String addNode(NodeInput input, String tenantId) {
        idleTracker.recordWrite();
        return delegate().addNode(input, tenantId);
    }

    @Override
    public void updateNode(String nodeId, NodeUpdate update, String tenantId) {
        idleTracker.recordWrite();
        delegate().updateNode(nodeId, update, tenantId);
    }

    @Override
    public String addEdge(EdgeInput input, String tenantId) {
        idleTracker.recordWrite();
        return delegate().addEdge(input, tenantId);
    }

    // All other write methods (removeEdge, mergeNodes, supersede, reinstate,
    // eraseNode, eraseSubgraph, eraseEntity, eraseEntityAcrossTenants,
    // createSubgraph, updateSubgraph, addAlias, removeAlias) override
    // with idleTracker.recordWrite() before delegation.
    // Read methods inherit from AbstractForwardingMindMapStore (no override).
}
```

This follows the established MindMapStore decorator pattern: CDI `@Decorator` + `@Priority` + `extends AbstractForwardingMindMapStore`, exactly as `TraitApplicationDecorator` (`@Priority(70)`) and `AffectTrajectoryDecorator` (`@Priority(65)`) do.

### 4.4 Phase Ordering

| Priority | Phase | What it does |
|----------|-------|-------------|
| 10 | AccessFrequencyPhase | Flush write-behind counters to `storageStrength` and `lastAccessed` node properties (no decay — retrieval strength is a read-time projection, §5.6) |
| 20 | MergeDetectionPhase | Jaro-Winkler name similarity + neighbor overlap → candidate list → optional embedding confirmation → auto-merge or flag |
| 30 | CommunitySummaryPhase | k-core decomposition → cluster identification → LLM summary generation for new/changed clusters |
| 40 | CuriosityRefreshPhase | Delegates to CuriositySignalGenerator.computeSignals(tenantId, Set.of()). Empty recentEntityIds is intentional — background signals should not be biased toward any conversation context. Topical distance dampening is skipped (applyTopicalDistanceDampening returns early for empty set). |

## 5. Access-Frequency Tracking — Bjorks' Dual-Strength Model (#298)

### 5.1 Cognitive Model

Bjorks' New Theory of Disuse distinguishes two independent memory dimensions:

- **Storage strength** — how deeply encoded a memory is. Reinforced by repeated encounters. Never decays. A node accessed 100 times has high storage strength even after months of disuse.
- **Retrieval strength** — how easily retrievable a memory is right now. Decays exponentially over time since last access. Reset to 1.0 on each access. A heavily-used node that hasn't been accessed recently has low retrieval strength but high storage strength — making it easy to reactivate on the next access.

The two strengths interact: storage strength modulates retrieval decay rate. Higher storage strength → slower retrieval decay → easier reactivation. This captures the "desirable difficulty" effect: a well-established memory (high storage strength) with low current retrieval strength is fundamentally different from a barely-known memory (low storage strength) with low retrieval strength.

### 5.2 RetrievalAccessTracker

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

@ApplicationScoped
public class RetrievalAccessTracker {

    private volatile ConcurrentHashMap<String, AtomicLong> counts =
        new ConcurrentHashMap<>();
    private volatile ConcurrentHashMap<String, Instant> lastAccess =
        new ConcurrentHashMap<>();

    public void recordAccess(String nodeId) {
        counts.computeIfAbsent(nodeId, k -> new AtomicLong()).incrementAndGet();
        lastAccess.put(nodeId, Instant.now());
    }

    public AccessSnapshot swapAndReset() {
        var oldCounts = counts;
        var oldLastAccess = lastAccess;
        counts = new ConcurrentHashMap<>();
        lastAccess = new ConcurrentHashMap<>();

        var snapshot = new HashMap<String, Long>();
        oldCounts.forEach((nodeId, counter) ->
            snapshot.put(nodeId, counter.get()));

        return new AccessSnapshot(snapshot,
            Map.copyOf(oldLastAccess));
    }
}
```

`swapAndReset()` atomically swaps the map references, eliminating the iterate-and-remove race condition. Any `recordAccess()` calls that arrive during the swap write to the NEW maps and are captured on the next flush cycle.

### 5.3 Tracking Boundary

`recordAccess()` is called explicitly at user-facing retrieval boundaries:

- `CognitiveProfile.resolve()` — when an entity profile is built for a query
- `TemporalFocus.rankedAttention()` — when attention items are computed
- `ConversationBridge.process()` — for nodes created during segmentation
- `ExtractionRequestedObserver` — for all entities (created and referenced) from LLM extraction
- Any future search/retrieval API that surfaces nodes to a user

NOT called by: MindMapExtractor internal traversals, CuriositySignalGenerator scans, consolidation scheduler phases, MindMapStore decorators.

### 5.4 AccessFrequencyPhase

On each pass:
1. Call `accessTracker.swapAndReset()` to get accumulated snapshot
2. For each node with counts > 0: read current `storageStrength` property, add flush value, write updated `storageStrength` and `lastAccessed` via `NodeUpdate`
3. No decay pass needed — retrieval strength is a read-time projection (§5.6)

### 5.5 Properties

| Property | Type | Semantics |
|----------|------|-----------|
| `storageStrength` | String (integer) | Cumulative access count — never decays. Reinforced by each retrieval event. |
| `lastAccessed` | String (ISO instant) | Last user-facing retrieval timestamp. Used for read-time retrieval strength computation. |

### 5.6 Read-Time Retrieval Strength

Retrieval strength is computed at read time, not stored. Follows the `ConfidenceDecayDecorator` pattern — the stored values (`lastAccessed`, `storageStrength`) are the inputs; the decayed value is projected on read. Storage strength modulates the effective half-life via logarithmic scaling:

```java
static double retrievalStrength(Instant lastAccessed, int storageStrength,
                                 double baseHalfLifeDays) {
    if (lastAccessed == null) return 0.0;
    double hoursSince = Duration.between(lastAccessed, Instant.now()).toHours();
    if (hoursSince <= 0) return 1.0;
    double effectiveHalfLifeHours = baseHalfLifeDays * 24.0
        * (1 + Math.log1p(storageStrength));
    return Math.pow(2.0, -hoursSince / effectiveHalfLifeHours);
}
```

The `Math.log1p(storageStrength)` term ensures diminishing returns — a node accessed 100 times has an effective half-life ~5.6× the base (not 100×). Example effective half-lives with a 30-day base:

| storageStrength | Effective half-life |
|-----------------|-------------------|
| 1 | ~51 days |
| 10 | ~102 days |
| 100 | ~169 days |

This is the core Bjorks interaction: heavily-accessed nodes retain retrieval strength much longer, making them easy to reactivate even after extended disuse.

### 5.7 Composite Retrieval Scoring

Per Park et al. "Generative Agents" and issue #298:

```
score = confidence × retrievalStrength × relevance
```

Where:
- `confidence` — existing ConfidenceDecayDecorator-projected value
- `retrievalStrength` — read-time projection from `lastAccessed` (§5.6)
- `relevance` — query-specific: name match, embedding similarity, or graph distance

This scoring formula is applied wherever nodes are ranked for retrieval — integrated into `MindMapQuery`-based search and `CognitiveProfile.resolve()`.

## 6. Community Summaries (#299)

### 6.1 k-Core Decomposition

Extension to `MindMapAnalyzer`:

```java
public record KCore(Set<String> nodeIds, double density) {}

public static List<KCore> kCores(MindMapStore store, String subgraphId,
                                  String tenantId, int k) {
    // 1. Load all nodes and edges in subgraph
    // 2. Iteratively remove nodes with degree < k
    // 3. Find connected components in remaining graph
    // 4. Compute density for each component
    // 5. Return components as KCore records
}
```

Algorithm complexity: O(V + E) — linear in graph size. The `k` parameter controls minimum connectivity (default 3: each node in a core must have at least 3 neighbors within the core).

**Limitation:** k-core decomposition misses loosely-connected communities where no single node has k neighbors within the cluster. These require embedding-based or label-propagation approaches, which can be layered on later.

### 6.2 CommunitySummaryPhase

On each pass:
1. For each subgraph in the tenant, run `kCores(store, subgraphId, tenantId, k)`
2. **Cleanup stale summaries:** Query existing Summary-trait nodes in the subgraph. For each Summary node, check whether its `coreHash` matches any current k-core's hash. If no match → the community has dissolved → erase via `store.eraseNode(summaryNodeId, tenantId)` (cascade-deletes `summarizes` edges). Complexity: O(S × C) where S = existing summaries, C = current cores — negligible at agent-scale.
3. Filter cores by minimum size (default 4 nodes)
4. For each core, compute `memberHash` = hash of (sorted member node IDs + their `updatedAt` timestamps)
5. Check if a Summary node already exists for this core (search by `coreHash` property matching)
   - If exists and `memberHash` unchanged → skip (no LLM call)
   - If exists but `memberHash` changed → regenerate summary, update node
   - If not exists → create new summary node
6. Cap at `casehub.consolidation.summaries.max-per-pass` (default 5) new/regenerated summaries per pass
7. Summary nodes:
   - Trait: `Summary` (distinguishes from factual nodes)
   - Properties: `coreHash`, `memberHash`, `memberCount`, `generatedAt`
   - Edges: `summarizes` edge to each member node
   - Type: same subgraph type as members
   - TypeRegistry: "Summary" registered as a dynamic type in the TYPE_SYSTEM subgraph (per #285 D6) with property schema: `coreHash` (string, required), `memberHash` (string, required), `memberCount` (number, required), `generatedAt` (date, required). Registration happens at `CommunitySummaryPhase` initialization via `CognitiveLoader`'s bootstrap pattern. Depends on #285 TypeRegistry infrastructure.

### 6.3 LLM Summary Generation

```
System: You are summarizing a cluster of related knowledge graph entities.
        Given their names, types, properties, and relationships,
        generate a concise summary (2-3 sentences) and a descriptive title.

User: Cluster of {N} {subgraphType} entities:
      - {name1}: {properties1}, edges: [{edge types and targets}]
      - {name2}: {properties2}, edges: [{edge types and targets}]
      ...
```

Uses the existing `Instance<AgentProvider>` pattern from MindMapExtractor for LLM access.

## 7. Merge Detection (#300)

### 7.1 Two-Layer Detection

**Layer 1 — Structural (pure Java, always active):**

For each subgraph, compare all node pairs within the subgraph (excluding nodes with the `Summary` trait):
- Jaro-Winkler similarity on `node.name()` — threshold ≥ 0.85
- Jaccard coefficient on neighbor node IDs — overlap ≥ 0.3
- Combined score: `0.6 * nameSimilarity + 0.4 * neighborOverlap`

The 0.85 Jaro-Winkler threshold is a pre-filter on the name component alone; the combined score (0.6 * name + 0.4 * neighbors) operates on a different scale and can be lower than 0.85 even when the name passes.

Complexity: O(N²) per subgraph where N is the node count. For agent-scale graphs (the MindMap SPI design assumption — per-agent, per-tenant subgraphs with low hundreds of nodes), this is acceptable and the constant factor is small (two string comparisons + set intersection per pair). If subgraph sizes grow beyond this assumption, an inverted index on shared neighbors or locality-sensitive hashing can be layered on as an optimization — but it is not needed for v1.

**Limitation:** Completely dissimilar names ("CEO" vs "Chief Executive Officer") are missed by Layer 1 unless they share neighbors. Layer 2 only confirms Layer 1 candidates — it does not independently scan for semantic duplicates. This is acceptable for v1.

**Layer 2 — Semantic (optional, when EmbeddingModel available):**

For candidates from Layer 1 with combined score in [0.6, 0.85) (uncertain range):
- Embed `name + " " + properties.values()` for both candidates
- Cosine similarity threshold ≥ 0.8 confirms the match
- Below 0.8 → candidate is dropped

### 7.2 MergeCandidate

```java
public record MergeCandidate(
    String nodeId1,
    String nodeId2,
    double score,
    String reason,      // "name-similarity", "name+neighbors", "embedding-confirmed"
    Instant detectedAt
) {}
```

### 7.3 Auto-Merge vs. Flagging

| Combined Score | Action |
|----------------|--------|
| ≥ 0.9 | Auto-merge via `MindMapStore.mergeNodes()` (keep higher-access node) |
| [0.7, 0.9) | Store as `mergeCandidate` property on both nodes for later review |
| < 0.7 | Discard |

Auto-merge uses `mergeNodes(keepNodeId, removeNodeId, tenantId)` — the existing SPI that handles property conflict reporting via `MergeResult`.

### 7.4 MergeDetectionPhase

On each pass:
1. For each subgraph in the tenant (ordered by `subgraphPriority`), load nodes and **exclude nodes with the `Summary` trait** — Summary nodes are structural aggregates, not factual entities, and should never be merge candidates (their name similarity and neighbor overlap would produce false positives)
2. Run Layer 1 detection on remaining nodes
3. Filter to candidates above threshold
4. Run Layer 2 on uncertain candidates (if EmbeddingModel available)
5. Auto-merge high-confidence candidates
6. Flag medium-confidence candidates as node properties
7. Cap at `casehub.consolidation.merges.max-per-pass` (default 10) auto-merges per pass

## 8. Test Strategy

| Component | What's tested |
|-----------|--------------|
| ConversationBridge | Unit: cleaned text → rule-based segmentation → nodes created in store with STATED confidence and "conversation-bridge" provenance; access tracker called for created nodes; ExtractionRequested CDI event fired with segmentNodeIds; principalId propagated to NodeInput |
| ExtractionRequestedObserver | Integration: event → MindMapExtractor → entities extracted; access tracker called for all entities; segment nodes superseded by first created entity; segments persist if extraction yields no entities |
| ConsolidationScheduler | Unit: idle guard skips when not idle; tryLock prevents overlapping runs; capability check; tenant enumeration; phase ordering; error isolation (one phase fails, rest still run); curiosity-driven subgraph priority |
| RetrievalAccessTracker | Unit: recordAccess increments, swapAndReset returns snapshot and clears atomically, concurrent access safety (no lost increments during swap) |
| AccessFrequencyPhase | Unit: flush writes storageStrength + lastAccessed properties, no-op when nothing to flush, no decay pass |
| MergeDetectionPhase | Unit: Jaro-Winkler scoring, neighbor overlap Jaccard, combined score thresholds, auto-merge above 0.9, flagging in [0.7, 0.9), Layer 2 confirmation/rejection |
| CommunitySummaryPhase | Unit: k-core identification, hash-based invalidation skips unchanged clusters, LLM called only for new/changed, cost cap respected, stale summaries erased when k-core dissolves |
| CuriosityRefreshPhase | Unit: delegates to CuriositySignalGenerator |
| MindMapStoreIdleTracker | Unit: write operations update lastWrite, read operations do not, isIdle threshold check |
| MindMapAnalyzer.kCores | Unit: k-core decomposition on test graphs, empty graph, single component, multiple components |

All tests use `InMemoryMindMapStore` and `InMemoryMemoryStore`. No SQLite, no Docker, no ONNX models. LLM calls mocked via `Instance<AgentProvider>` stub.

## 9. Configuration

| Property | Default | Description |
|----------|---------|-------------|
| `casehub.consolidation.interval` | `5m` | Scheduler tick interval |
| `casehub.consolidation.idle-threshold` | `1m` | Minimum idle time before running |
| `casehub.consolidation.access.retrieval-half-life-days` | `30` | Half-life for read-time retrieval strength decay (§5.6) |
| `casehub.consolidation.merge.name-threshold` | `0.85` | Jaro-Winkler minimum for Layer 1 |
| `casehub.consolidation.merge.neighbor-threshold` | `0.3` | Jaccard minimum for neighbor overlap |
| `casehub.consolidation.merge.auto-merge-threshold` | `0.9` | Combined score for automatic merge |
| `casehub.consolidation.merge.max-per-pass` | `10` | Maximum auto-merges per pass |
| `casehub.consolidation.summaries.k` | `3` | Minimum degree for k-core membership |
| `casehub.consolidation.summaries.min-cluster-size` | `4` | Minimum nodes to generate a summary |
| `casehub.consolidation.summaries.max-per-pass` | `5` | Maximum summaries generated per pass |

## 10. Issue Mapping

| Issue | Component | Scope |
|-------|-----------|-------|
| #296 | ConversationBridge + ExtractionRequestedObserver + DraftHouse KnowledgeFacet | Real-time: segmentation → graph; Near-time: async LLM enrichment |
| #297 | ConsolidationScheduler + ConsolidationPhase SPI + MindMapStoreIdleTracker | Background: orchestration |
| #298 | RetrievalAccessTracker + AccessFrequencyPhase + read-time retrieval strength | Background: Bjorks dual-strength model |
| #299 | MindMapAnalyzer.kCores + CommunitySummaryPhase + TypeRegistry registration | Background: summaries |
| #300 | MergeDetectionPhase + MergeCandidate | Background: deduplication |

### 10.1 Deferred Items

| Item | Reason | Tracked As |
|------|--------|------------|
| Schema discovery ConsolidationPhase | Depends on #285 TypeRegistry infrastructure | To be filed as a child of #295 |
| DraftHouse integration issue | Cross-project coordination for KnowledgeFacet + NotesPipelineObserver | To be filed in DraftHouse repo |
| Promote `findOrCreateSubgraph` to MindMapStore default method | Duplicated as private helper in MindMapExtractor; ConversationBridge needs same operation | To be filed against mindmap-api |

## References

- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractor.java` — existing LLM extraction
- `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/MindMapAnalyzer.java` — existing graph analysis
- `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/ConfidenceDecayDecorator.java` — read-time decay (NOT a consolidation phase)
- `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/DerivedEdgeDecorator.java` — near-time forward-chaining
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CuriositySignalGenerator.java` — curiosity signals
- `memory/src/main/java/io/casehub/neocortex/memory/experience/runtime/ExperienceStream.java` — existing ingestion pattern
- `drafthouse/server/runtime/src/main/java/io/casehub/drafthouse/voice/NotesPipeline.java` — DraftHouse cleanup
- `drafthouse/server/api/src/main/java/io/casehub/drafthouse/Facet.java` — DraftHouse facet SPI
- Issue #285 — Thing model (foundational dependency)
- `specs/issue-285-knowledge-repr-model/2026-09-09-knowledge-repr-model-design.md` — predecessor spec
- `specs/issue-285-knowledge-repr-model/decisions.md` — predecessor decisions
- Park et al. "Generative Agents" — composite retrieval scoring formula
- Mem0 "Dream" — background memory consolidation for AI agents
- SCM (April 2026) — sleep-consolidated memory mapping biological principles
- Bjorks' New Theory of Disuse — storage strength vs retrieval strength

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
| **Real-time** | During conversation | DraftHouse NotesPipeline cleans raw text → ConversationBridge → MindMapExtractor creates nodes + edges | DraftHouse (thin adapter) + neocortex (bridge + extractor) |
| **Near-time** | On every addNode/addEdge | DerivedEdgeDecorator fires forward-chaining rules, TraitRules evaluate traits | neocortex (already built, decorator stack) |
| **Background** | Idle periods (≥1 min no writes) | ConsolidationScheduler runs 4 phases: access-frequency, merge detection, community summaries, curiosity refresh | neocortex (mindmap-intelligence) |

### 2.2 Module Layout

All new components live in `mindmap-intelligence`, which already owns MindMapExtractor, CuriositySignalGenerator, and TypeRegistry. No new modules.

```
mindmap-intelligence/
  src/main/java/io/casehub/neocortex/mindmap/intelligence/
    ConversationBridge.java            — SPI: cleaned text → extraction result
    consolidation/
      ConsolidationScheduler.java      — @Scheduled, idle guard, tryLock, phase orchestration
      ConsolidationPhase.java          — SPI: single phase contract
      AccessFrequencyPhase.java        — flush write-behind counters, decay unaccessed
      MergeDetectionPhase.java         — Jaro-Winkler + optional embedding
      CommunitySummaryPhase.java       — k-core clustering + LLM summary
      CuriosityRefreshPhase.java       — delegates to CuriositySignalGenerator
      RetrievalAccessTracker.java      — in-memory ConcurrentHashMap, recordAccess(), flush()
      MergeCandidate.java              — scored candidate record
      KCore.java                       — cluster record (nodeIds + density)
  
mindmap/
  src/main/java/io/casehub/neocortex/mindmap/runtime/
    MindMapStoreIdleTracker.java       — @Decorator, records last write timestamp
```

### 2.3 Dependency Direction

```
mindmap-intelligence (new: ConversationBridge, ConsolidationScheduler, phases)
    ↓ depends on
mindmap-api (MindMapStore SPI, MindMapNode, MindMapQuery)
mindmap (MindMapStoreIdleTracker decorator — new)
    ↓ depends on
mindmap-api

DraftHouse KnowledgeFacet (thin adapter, application tier)
    ↓ depends on
mindmap-intelligence (ConversationBridge)
```

## 3. ConversationBridge (#296)

### 3.1 SPI

```java
package io.casehub.neocortex.mindmap.intelligence;

@ApplicationScoped
public class ConversationBridge {

    private final MindMapExtractor extractor;
    private final RetrievalAccessTracker accessTracker;

    @Inject
    public ConversationBridge(MindMapExtractor extractor,
                              Instance<RetrievalAccessTracker> accessTracker) {
        this.extractor = extractor;
        this.accessTracker = accessTracker.isResolvable()
                             ? accessTracker.get() : null;
    }

    public ExtractionResult process(String cleanedText, String tenantId) {
        return process(cleanedText, tenantId, List.of());
    }

    public ExtractionResult process(String cleanedText, String tenantId,
                                     List<String> recentEntityNames) {
        var result = extractor.extract(cleanedText, tenantId, recentEntityNames);
        if (accessTracker != null) {
            result.createdNodeIds().forEach(accessTracker::recordAccess);
        }
        return result;
    }
}
```

### 3.2 DraftHouse Integration

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

### 3.3 What ConversationBridge Does NOT Do

- **Cleanup.** That's DraftHouse NotesPipeline's job. The bridge accepts already-cleaned text.
- **Near-time enrichment.** DerivedEdgeDecorator and TraitRules fire automatically when nodes/edges are added. The bridge doesn't need to trigger them.
- **Background consolidation.** The scheduler runs independently on a timer.

## 4. ConsolidationScheduler (#297)

### 4.1 Lifecycle

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

@ApplicationScoped
public class ConsolidationScheduler {

    private final List<ConsolidationPhase> phases;
    private final MindMapStoreIdleTracker idleTracker;
    private final CaseMemoryStore memoryStore;
    private final ReentrantLock lock = new ReentrantLock();

    @Scheduled(every = "${casehub.consolidation.interval:5m}")
    void tick() {
        if (!lock.tryLock()) return;          // previous pass still running
        try {
            if (!idleTracker.isIdle(Duration.ofMinutes(1))) return;

            for (String tenantId : memoryStore.discoverTenants()) {
                for (ConsolidationPhase phase : phases) {
                    try {
                        phase.run(tenantId);
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
}
```

### 4.2 ConsolidationPhase SPI

```java
public interface ConsolidationPhase {
    String name();
    void run(String tenantId);
}
```

Phases are injected as `Instance<ConsolidationPhase>` and ordered by `@Priority`. Each phase is independently testable and can be disabled via `@IfBuildProperty`.

### 4.3 MindMapStoreIdleTracker

```java
package io.casehub.neocortex.mindmap.runtime;

@Decorator
@Priority(30)
public class MindMapStoreIdleTracker implements MindMapStore {

    @Inject @Delegate @Any MindMapStore delegate;

    private volatile Instant lastWrite = Instant.EPOCH;

    public boolean isIdle(Duration threshold) {
        return Duration.between(lastWrite, Instant.now()).compareTo(threshold) > 0;
    }

    // Intercept all write operations
    @Override
    public String addNode(NodeInput input, String tenantId) {
        lastWrite = Instant.now();
        return delegate.addNode(input, tenantId);
    }

    @Override
    public void updateNode(String nodeId, NodeUpdate update, String tenantId) {
        lastWrite = Instant.now();
        delegate.updateNode(nodeId, update, tenantId);
    }

    @Override
    public String addEdge(EdgeInput input, String tenantId) {
        lastWrite = Instant.now();
        return delegate.addEdge(input, tenantId);
    }

    // ... all other write methods delegate with lastWrite update
    // Read methods delegate without updating lastWrite
}
```

### 4.4 Phase Ordering

| Priority | Phase | What it does |
|----------|-------|-------------|
| 10 | AccessFrequencyPhase | Flush write-behind counters to node properties, decay unaccessed node counters |
| 20 | MergeDetectionPhase | Jaro-Winkler name similarity + neighbor overlap → candidate list → optional embedding confirmation → auto-merge or flag |
| 30 | CommunitySummaryPhase | k-core decomposition → cluster identification → LLM summary generation for new/changed clusters |
| 40 | CuriosityRefreshPhase | Delegates to existing CuriositySignalGenerator.computeSignals() |

## 5. Access-Frequency Tracking (#298)

### 5.1 RetrievalAccessTracker

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

@ApplicationScoped
public class RetrievalAccessTracker {

    private final ConcurrentHashMap<String, AtomicLong> counts = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, Instant> lastAccess = new ConcurrentHashMap<>();

    public void recordAccess(String nodeId) {
        counts.computeIfAbsent(nodeId, k -> new AtomicLong()).incrementAndGet();
        lastAccess.put(nodeId, Instant.now());
    }

    public Map<String, Long> flushAndReset() {
        var snapshot = new HashMap<String, Long>();
        var iterator = counts.entrySet().iterator();
        while (iterator.hasNext()) {
            var entry = iterator.next();
            snapshot.put(entry.getKey(), entry.getValue().getAndSet(0));
            iterator.remove();
        }
        lastAccess.clear();
        return snapshot;
    }
}
```

### 5.2 Tracking Boundary

`recordAccess()` is called explicitly at user-facing retrieval boundaries:

- `CognitiveProfile.resolve()` — when an entity profile is built for a query
- `TemporalFocus.rankedAttention()` — when attention items are computed
- `ConversationBridge.process()` — for nodes referenced/created during extraction
- Any future search/retrieval API that surfaces nodes to a user

NOT called by: MindMapExtractor internal traversals, CuriositySignalGenerator scans, consolidation scheduler phases, MindMapStore decorators.

### 5.3 AccessFrequencyPhase

On each pass:
1. Call `accessTracker.flushAndReset()` to get accumulated counts
2. For each node with counts > 0: read current `accessCount` property, add flush value, write updated `accessCount` and `lastAccessed` via `NodeUpdate`
3. For nodes NOT in the flush map: if `lastAccessed` is older than a configurable threshold (default 30 days), halve `accessCount` (exponential decay on disuse)

### 5.4 Properties

| Property | Type | Semantics |
|----------|------|-----------|
| `accessCount` | String (integer) | Cumulative retrieval count, decayed over time |
| `lastAccessed` | String (ISO instant) | Last user-facing retrieval timestamp |

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

### 6.2 CommunitySummaryPhase

On each pass:
1. For each subgraph in the tenant, run `kCores(store, subgraphId, tenantId, k)`
2. Filter cores by minimum size (default 4 nodes)
3. For each core, compute `memberHash` = hash of (sorted member node IDs + their `updatedAt` timestamps)
4. Check if a Summary node already exists for this core (search by `coreHash` property matching)
   - If exists and `memberHash` unchanged → skip (no LLM call)
   - If exists but `memberHash` changed → regenerate summary, update node
   - If not exists → create new summary node
5. Cap at `casehub.consolidation.summaries.max-per-pass` (default 5) new/regenerated summaries per pass
6. Summary nodes:
   - Trait: `Summary` (distinguishes from factual nodes)
   - Properties: `coreHash`, `memberHash`, `memberCount`, `generatedAt`
   - Edges: `summarizes` edge to each member node
   - Type: same subgraph type as members

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

For each subgraph, compare all node pairs within the subgraph:
- Jaro-Winkler similarity on `node.name()` — threshold ≥ 0.85
- Jaccard coefficient on neighbor node IDs — overlap ≥ 0.3
- Combined score: `0.6 * nameSimilarity + 0.4 * neighborOverlap`

Optimization: sort nodes alphabetically, only compare pairs with shared prefix or shared neighbors (avoids O(N²) for large subgraphs).

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
1. For each subgraph in the tenant, run Layer 1 detection
2. Filter to candidates above threshold
3. Run Layer 2 on uncertain candidates (if EmbeddingModel available)
4. Auto-merge high-confidence candidates
5. Flag medium-confidence candidates as node properties
6. Cap at `casehub.consolidation.merges.max-per-pass` (default 10) auto-merges per pass

## 8. Test Strategy

| Component | What's tested |
|-----------|--------------|
| ConversationBridge | Integration: cleaned text → MindMapExtractor → nodes created in store; access tracker called for created nodes |
| ConsolidationScheduler | Unit: idle guard skips when not idle; tryLock prevents overlapping runs; tenant enumeration; phase ordering; error isolation (one phase fails, rest still run) |
| RetrievalAccessTracker | Unit: recordAccess increments, flushAndReset returns snapshot and clears, concurrent access safety |
| AccessFrequencyPhase | Unit: flush writes properties, decay halves old counters, no-op when nothing to flush |
| MergeDetectionPhase | Unit: Jaro-Winkler scoring, neighbor overlap Jaccard, combined score thresholds, auto-merge above 0.9, flagging in [0.7, 0.9), Layer 2 confirmation/rejection |
| CommunitySummaryPhase | Unit: k-core identification, hash-based invalidation skips unchanged clusters, LLM called only for new/changed, cost cap respected |
| CuriosityRefreshPhase | Unit: delegates to CuriositySignalGenerator |
| MindMapStoreIdleTracker | Unit: write operations update lastWrite, read operations do not, isIdle threshold check |
| MindMapAnalyzer.kCores | Unit: k-core decomposition on test graphs, empty graph, single component, multiple components |

All tests use `InMemoryMindMapStore` and `InMemoryMemoryStore`. No SQLite, no Docker, no ONNX models. LLM calls mocked via `Instance<AgentProvider>` stub.

## 9. Configuration

| Property | Default | Description |
|----------|---------|-------------|
| `casehub.consolidation.interval` | `5m` | Scheduler tick interval |
| `casehub.consolidation.idle-threshold` | `1m` | Minimum idle time before running |
| `casehub.consolidation.access.decay-after-days` | `30` | Days without access before counter halving |
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
| #296 | ConversationBridge + DraftHouse KnowledgeFacet | Real-time: cleaned text → graph |
| #297 | ConsolidationScheduler + ConsolidationPhase SPI + MindMapStoreIdleTracker | Background: orchestration |
| #298 | RetrievalAccessTracker + AccessFrequencyPhase | Background: access tracking |
| #299 | MindMapAnalyzer.kCores + CommunitySummaryPhase | Background: summaries |
| #300 | MergeDetectionPhase + MergeCandidate | Background: deduplication |

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

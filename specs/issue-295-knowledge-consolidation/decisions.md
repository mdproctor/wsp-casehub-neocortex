## D1: ConversationBridge — pipeline logic in neocortex, thin DraftHouse Facet adapter

**Choice:** The conversation-to-knowledge pipeline logic lives in neocortex (in `mindmap-intelligence`, which already owns MindMapExtractor and CuriositySignalGenerator). A `ConversationBridge` SPI in neocortex accepts cleaned text and produces knowledge graph mutations. DraftHouse provides a thin `KnowledgeFacet` adapter that chains NotesPipeline cleanup → ConversationBridge → MindMapStore. The bridge is platform-level infrastructure; the Facet is application-level wiring.
**Alternatives:**
- Pipeline logic in DraftHouse as a Facet (original D1) — violates platform boundary rules: application-tier repos cannot depend on each other, so casehub-life/casehub-aml/casehub-clinical could not reuse the bridge
- Shared extraction SPI in a new module — more moving parts for what fits naturally in mindmap-intelligence alongside MindMapExtractor
**Rationale:** The bridge is a platform capability (conversation → knowledge graph). Any app that has conversation-like flows should be able to use it. DraftHouse's cleanup (NotesPipeline) is DraftHouse-specific; the bridge accepts already-cleaned text. This preserves the reviewer's point (R1-02): platform boundary rules prevent app-to-app reuse, so the reusable logic must live below the application tier. Graph visualization is a separate UI concern out of scope for this epic.
**Trade-offs:** DraftHouse's KnowledgeFacet is thinner than originally envisioned — it's just an adapter. The bridge doesn't own cleanup; callers provide cleaned text.
**Sources:** DraftHouse Facet.java, NotesPipeline.java, MindMapExtractor.java, platform boundary rules, issue #296
**Exploration:** quick (revised after decision review R1-02, R1-03)
**Status:** revised — from "pipeline in DraftHouse" to "pipeline in neocortex, thin DraftHouse adapter"

## D2: ConsolidationScheduler trigger — @Scheduled periodic with idle guard and concurrency control

**Choice:** `@Scheduled` Quarkus timer runs consolidation at a configurable interval (e.g. every 5 minutes). No persistent job state — the scheduler is stateless. On restart, it simply scans the current graph state.
**Idle guard mechanism:** A `@Decorator` on MindMapStore records the last write timestamp in a shared `volatile Instant` field (injected `@ApplicationScoped` bean). The scheduler reads this timestamp on each tick — if `Duration.between(lastWrite, now) < 1 minute`, skip the pass. The decorator is lightweight (one volatile write per store mutation) and has no transaction coupling.
**Concurrency control:** `ReentrantLock.tryLock()` at the start of each pass — if a previous pass is still running, skip. This prevents overlapping runs without blocking.
**Tenant enumeration:** Uses `CaseMemoryStore.discoverTenants()` (already exists, capability-gated via MemoryCapability.DISCOVER_TENANTS) to iterate all tenants per pass.
**Alternatives:**
- CDI event-driven after extraction — more responsive but adds debounce complexity; the three-speed model explicitly separates near-time from background
- Manual/API trigger only — full control but no automatic background processing
**Rationale:** The knowledge graph itself is persisted. The scheduler just decides what to do on each pass. Simple, predictable, debuggable.
**Trade-offs:** Not immediately responsive to new data — consolidation waits for the next scheduled tick plus idle period. Acceptable for background-tier work.
**Sources:** RetentionScheduler (rag-tracking, @Scheduled pattern), MemoryRetentionScheduler (memory, same pattern), CaseMemoryStore.discoverTenants(), issue #297
**Exploration:** quick (revised after decision review R1-06, R1-07, R1-09, R1-10)
**Status:** revised — added idle guard mechanism, concurrency control, tenant enumeration, fixed factual error on CbrReconciliationService

## D3: Access-frequency tracking — write-behind batching, user-facing accesses only

**Choice:** Track access frequency via write-behind counter batching. An in-memory `ConcurrentHashMap<String, AtomicLong>` accumulates access counts. The consolidation scheduler flushes accumulated counts to node properties (`accessCount`, `lastAccessed`) at the start of each pass, then clears the map. Only user-facing retrieval operations are tracked — NOT internal system operations (MindMapExtractor traversals, CuriositySignalGenerator scans, consolidation passes).
**Tracking boundary:** A new `RetrievalAccessTracker` `@ApplicationScoped` bean provides `recordAccess(String nodeId)`. Callers at the retrieval/query API boundary (e.g., CognitiveProfile, TemporalFocus, search endpoints) call this explicitly. MindMapStore decorators do NOT intercept reads — the signal source is above the store layer.
**Alternatives:**
- MindMapStore decorator intercepting reads (original D3) — writes on every read, inflates counts from internal operations (MindMapExtractor, CuriositySignalGenerator), breaks the read-path purity convention
- Separate counter store (AccessTracker SPI) — cleaner separation but more infrastructure for a counter
- Memory domain — heavyweight for a counter
**Rationale:** Write-behind eliminates write-on-read (R1-12). Tracking at the retrieval boundary (not the store layer) distinguishes user-intentional access from system traversals (R1-15). The consolidation scheduler owns the flush, keeping the read path pure. In-memory counters are acceptable for non-persistent data (user noted this is fine).
**Trade-offs:** Counters are lost on JVM restart (between flushes). Acceptable — access frequency is a heuristic signal, not critical data. If the JVM restarts, the next pass starts with zero pending counts and the previously-flushed values are already persisted on nodes.
**Depends on:** D2 (consolidation scheduler flushes counters)
**Sources:** ConfidenceDecayDecorator.java (decorator pattern reference), issue #298
**Exploration:** quick (revised after decision review R1-12, R1-14, R1-15)
**Status:** revised — from "write-on-read decorator" to "write-behind batching at retrieval boundary"

## D4: Community summaries — k-core subgraph clustering, summary trait for derived content

**Choice:** Identify clusters via k-core decomposition: iteratively remove nodes with degree < k until a stable core remains. Each k-core is a densely-connected community. MindMapAnalyzer is extended with `kCores(store, subgraphId, tenantId, int k)` that returns `List<KCore>` (nodeIds + density). For each cluster above a size threshold, an LLM generates a summary. Summary content is stored as a new node with a `Summary` trait and edges to cluster members. The `Summary` trait distinguishes derived content from factual content — search queries can filter by trait to exclude summaries.
**Summary invalidation:** Summary nodes carry a `memberHash` property (hash of member node IDs + their update timestamps). On each consolidation pass, the scheduler checks whether the hash has changed. If so, the summary is regenerated. Unchanged summaries are skipped (no LLM call).
**LLM cost control:** Maximum N summaries per consolidation pass (configurable, default 5). Clusters are prioritized by size * density.
**Alternatives:**
- Connected-component + edge density (original D4) — not a named algorithm, conflates connected components with dense subsets
- Label propagation — more sophisticated but harder to implement and tune
- Store summaries as subgraph metadata instead of nodes — less queryable, can't have edges to members
**Rationale:** k-core decomposition is a well-defined graph algorithm (O(V+E)), produces naturally nested communities, and has no tuning parameters beyond k. The Summary trait cleanly separates derived from factual content (R1-18). Hash-based invalidation avoids wasteful LLM calls. Cost cap prevents runaway spending.
**Trade-offs:** k-core misses loosely-connected communities. Acceptable for v1.
**Depends on:** D2 (consolidation scheduler runs this as a background phase)
**Sources:** MindMapAnalyzer.java, MindMapStore.neighbors(), issue #299
**Exploration:** quick (revised after decision review R1-17, R1-18, R1-19)
**Status:** revised — algorithm specified (k-core), summary trait for derived content, invalidation via hash, LLM cost cap

## D5: Merge detection — two-layer: string heuristic → embedding confirmation on candidates

**Choice:** Two-layer merge candidate detection. Layer 1 (cheap, pure Java): Jaro-Winkler string similarity on node names combined with shared neighbor overlap (Jaccard coefficient). Layer 2 (semantic, optional): embed node name + properties via `Instance<EmbeddingModel>`, compute cosine similarity — but ONLY on candidates surfaced by Layer 1 (similarity above a lower threshold but below the auto-merge threshold). Layer 2 confirms or rejects Layer 1 candidates; it does NOT scan the full graph independently. Auto-merge above a high confidence threshold; merge candidates below that threshold are stored as properties on the nodes for later review.
**Alternatives:**
- String similarity only — misses semantic duplicates
- Embedding only on full graph — O(N²) without pre-filtering
- Graph structure only — misses duplicates with different neighborhoods
**Rationale:** Layer 1 filters to a small candidate set (typically < 1% of node pairs). Layer 2 only runs on that small set, avoiding O(N²). Jaro-Winkler is better suited to name comparison than Levenshtein (handles transpositions, prefix weighting). Auto-merge eliminates obvious duplicates; lower-confidence candidates are flagged but not merged automatically.
**Trade-offs:** Layer 2 only catches semantic duplicates that have SOME string similarity in Layer 1. Completely dissimilar names ("CEO" vs "Chief Executive Officer") would be missed unless they share neighbors. Acceptable for v1.
**Depends on:** D2 (consolidation scheduler runs this as a background phase)
**Sources:** MindMapStore.mergeNodes() (merge operation), MindMapStore.neighbors() (neighbor overlap), issue #300
**Exploration:** quick (revised after decision review R1-22, R1-23, R1-24)
**Status:** revised — Layer 2 scoped to Layer 1 candidates only, Jaro-Winkler instead of Levenshtein, merge candidate queue

## D6: Consolidation phases — four-phase pipeline with error isolation

**Choice:** Each idle-pass runs four phases in order: (1) access-frequency flush + decay — flush in-memory counters to node properties (D3), reduce counters on unaccessed nodes. (2) merge detection — find and merge duplicates (D5). (3) community detection + summary generation (D4). (4) curiosity signal refresh via CuriositySignalGenerator (already exists). Phases run sequentially within a pass. Each phase implements a `ConsolidationPhase` SPI for testability and selective disabling.
**Confidence decay removed from pipeline:** ConfidenceDecayDecorator is a read-time computation — it applies exponential half-life decay mathematically when nodes are read, without writing back. It is always active via the decorator stack and does not need a batch sweep. The consolidation pipeline does not interact with it.
**Error isolation:** Each phase runs in a try-catch. If a phase fails, the scheduler logs the error and proceeds to the next phase. Partial failure is acceptable — the scheduler re-derives work from graph state on each pass, so a failed phase retries on the next tick.
**Module placement:** The ConsolidationScheduler and phase implementations live in `mindmap-intelligence` alongside MindMapExtractor and CuriositySignalGenerator. This module already depends on LangChain4j (for LLM calls in D4 summaries) and the full MindMapStore decorator stack.
**Alternatives:**
- Five-phase with confidence decay sweep (original D6) — ConfidenceDecayDecorator is read-time, a batch sweep would be a no-op or would require rewriting the decorator's model
- Parallel phases — ordering has dependencies (merge before community detection)
**Rationale:** Ordering: access-frequency first (provides signal for subsequent phases), merge second (removes duplicates before summarization), community detection third (operates on clean graph), curiosity last (scores reflect consolidated state). Error isolation ensures a single failing phase doesn't block the rest.
**Trade-offs:** Sequential pass may be slow on large graphs. Each phase should be bounded (process at most N items per pass with deterministic ordering so all items are eventually reached across passes).
**Depends on:** D2 (scheduler trigger), D3 (access-frequency), D4 (community), D5 (merge)
**Sources:** CuriositySignalGenerator.java, ConfidenceDecayDecorator.java (read-time only — excluded from pipeline), issue #297
**Exploration:** quick (revised after decision review R1-26, R1-29, R1-30, R1-32)
**Status:** revised — removed confidence decay phase, added error isolation, specified module placement, clarified bounded processing

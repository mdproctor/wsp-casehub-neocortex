# Knowledge Pipeline Phase 3 — R&D Exploration

**Status:** R&D exploration — not yet scoped for implementation
**Date:** 2026-10-05
**Context:** Brainstorming session after completing Phase 2 (#418)
**Prerequisite reading:** Phase 1 (#413) and Phase 2 (#418) designs

---

## Thesis

The knowledge pipeline in its current form is a **connector-side intelligence layer** — it caches external data, deduplicates across providers, manages freshness, resolves entities, and promotes knowledge to MindMap. Phase 1 built the spatial cache and entity resolution. Phase 2 added CDI wiring, subsumption, staleness refresh, eviction hardening, and contract test infrastructure.

Phase 3 asks a different question: **how does the knowledge pipeline participate in the cognitive lifecycle of an agent?**

Three capabilities emerge from this question:

1. **Dimensional memory with CBR learning** — operational knowledge tagged across multiple dimensions, retrieved by similarity to the current task context, weighted by outcomes over time
2. **Auto-generated task briefs** — compiled from dimensional memory, CBR patterns, MindMap knowledge, and pipeline heuristics; injected into the LLM's prompt when a task starts
3. **Persistent RAG-indexed content** — web search results, images, articles, and other unstructured content indexed locally so repeated queries retrieve from the local store instead of re-fetching

These three capabilities share a common architectural insight: **LLMs cannot learn across sessions.** They reason brilliantly in the moment but start every task ignorant. The knowledge pipeline's value is not caching (LLM prompt caching handles within-session repetition). The value is accumulated, outcome-weighted, contextually-assembled operational knowledge that makes the agent better over time.

---

## 1. Dimensional Memory — Beyond Hierarchical LLM Memory

### The Problem with Current LLM Memory

Current LLM memory systems (ChatGPT, Claude, Mem0) are hierarchical fact stores. Facts are filed in categories, retrieved by category filter or semantic search, and dumped into the prompt regardless of task context.

```
User Preferences:
  - Likes seafood
  - Allergic to peanuts
  - Prefers boutique hotels
```

This model has four structural failures:

**Cross-cutting knowledge doesn't fit.** "Don't trust TripAdvisor reviews for Asia" is simultaneously a source preference, a regional warning, and a data quality heuristic. Hierarchical storage forces a single slot or duplication. The knowledge is relevant to travel planning in Asia, to any task using TripAdvisor data, and to any task involving review analysis — but a hierarchical system can only file it in one place.

**No outcome signal.** "User likes Italian food" persists forever, even after three bad Italian restaurant recommendations. The memory doesn't know whether its knowledge actually helped. There's no mechanism for confidence to decay based on outcomes.

**Static assembly.** Every travel task gets the same travel memories. Planning a beach holiday and planning a ski trip pull identical context. The system can't distinguish which subset of travel knowledge is relevant to *this specific* travel task.

**No emergent structure.** The taxonomy must be designed upfront. If a new dimension emerges from usage ("this user's medical constraints affect restaurant recommendations"), someone must create the category manually.

### Dimensional Alternative

Each piece of operational knowledge is a point in a multi-dimensional feature space, not an entry in a hierarchy. Retrieval is similarity scoring against the current task's characteristics.

**Storage model:** A CBR case record with feature fields as dimensions.

```java
CbrRecord heuristic = CbrRecord.of("task-heuristic")
    .withProblem("Don't trust reviews on TripAdvisor for Asian destinations")
    .withFeature("source", string("tripadvisor"))
    .withFeature("region", stringList("asia"))
    .withFeature("data_type", string("reviews"))
    .withFeature("signal", string("unreliable"))
    .withFeature("origin", string("user-feedback"))
    .withFeature("task_type", stringList("travel", "research"));
```

**Retrieval model:** Task characteristics as query features, weighted similarity scoring.

```java
CbrQuery query = CbrQuery.of("task-heuristic")
    .withFeature("region", stringList("asia", "japan"))
    .withFeature("source", stringList("tripadvisor", "booking"))
    .withFeature("task_type", string("travel"))
    .withWeight("region", 1.5)    // region matters more for this query
    .withWeight("source", 1.0)
    .retrieveSimilar(topK: 20);
```

**Outcome learning:** When a task completes, `CbrOutcome` records success/failure. EMA adjusts confidence. Heuristics that led to good outcomes rank higher in future retrievals. Heuristics that led to poor outcomes decay.

**Emergent structure:** `SchemaDiscoveryPhase` in consolidation analyses property patterns across heuristic cases. "Region appears in 80% of travel heuristics" → promoted to a first-class feature field. The taxonomy grows from usage, not from upfront design.

### What Exists in the Platform

| Component | Module | Relevance |
|-----------|--------|-----------|
| `CbrRecordStore` | memory-api | Feature-vector storage with similarity retrieval |
| `CbrSimilarityScorer` | memory-api | Weighted composite scoring across feature dimensions |
| `CbrOutcome` + EMA | memory-api | Outcome recording with exponential moving average confidence |
| `CbrPlanAdapter` | memory-api | Adapts retrieved cases for current context |
| `TrustWeightedCbrRecordStore` | memory | Modulates retrieval by source trust |
| `OutcomeWeightingCbrRecordStore` | memory | Modulates retrieval by case confidence |
| `SchemaDiscoveryPhase` | mindmap-intelligence | Discovers property patterns, promotes to schema |
| `CaseMemoryStore` | memory-api | Stores experiences with domain tags and attributes |

### What Needs to Be Built

1. **Heuristic case type schema** — define the initial feature fields for operational heuristics (source, region, data_type, task_type, signal, origin). The schema evolves via SchemaDiscoveryPhase.

2. **Heuristic extraction from conversation** — when a user says "don't trust this site" during a task, extract the relevant dimensions from the conversation context and the current task state. This is an LLM extraction task — the agent's blocks worker interprets the feedback and creates the CBR record.

3. **Task-context feature builder** — derive query features from the current case context: what connectors are being used, what region/topic is active, what type of task is running. This feeds the retrieval query.

4. **Confidence decay for user-originated heuristics** — user feedback should start with high confidence (explicit instruction) but decay if contradicted by outcomes. "Don't trust TripAdvisor" starts at 0.9 but drops if TripAdvisor recommendations subsequently succeed.

### Integration Points

**Engine → Heuristic recording:** When a case step completes with user feedback that contains operational guidance, the worker fires an `ExperienceRecorded` CDI event. A new observer (`HeuristicExtractionObserver`) processes the event, extracts dimensional features via LLM, and stores as a CBR case.

**Engine → Heuristic retrieval:** When a case step starts, the worker's prompt renderer queries the heuristic CBR store with the task's context features. Retrieved heuristics are injected into the prompt (see §2 Task Briefs).

**Connectors → Source dimension:** The knowledge pipeline's `source` field (which connector produced the data) becomes a first-class dimension in heuristic storage. Trust scores from `AgentTrustProvider` feed into `TrustWeightedCbrRecordStore` for source-aware retrieval.

---

## 2. Auto-Generated Task Briefs

### The Problem

The agent starts every task with a blank slate. The system stores knowledge across multiple stores (MindMap, Memory, CBR, knowledge pipeline cache), but none of it automatically reaches the LLM's context window. The user re-educates the agent every session: "remember, I'm allergic to peanuts," "don't use that site, I told you last time."

### The Solution: Task Brief Prompt Section

A new `CognitionPromptRenderer` implementation — `TaskBriefPromptSection` — that compiles accumulated knowledge from multiple stores, scoped by the current task's characteristics, into a natural language brief.

**Data sources and what they contribute:**

| Source | Store | What it provides | Example |
|--------|-------|-----------------|---------|
| Dimensional heuristics | CBR (task-heuristic) | User operational feedback, learned warnings | "Don't trust reviews on TripAdvisor for Asia" |
| Case patterns | CBR (case records) | Learned strategies from past tasks | "Research flights before hotels — prices change faster" |
| Entity knowledge | MindMap | Durable facts about the user and world | "Peanut allergy, prefers boutique hotels" |
| Source reliability | Knowledge pipeline cache | Connector freshness and trust patterns | "Booking.com prices go stale after 24h for European flights" |
| Past experiences | CaseMemoryStore | What happened in previous similar tasks | "Last travel plan: user rejected all beach destinations" |
| Connector trust | AgentTrustProvider | Source-level trust scores | "Google Places: 0.7 trust for ratings, 0.9 for locations" |

**Brief compilation pipeline:**

```
1. Extract task features from case context
   (task_type, region, connectors in scope, user identity)

2. Query each store with task-scoped filters:
   - CBR: similarity retrieval with task features
   - MindMap: CognitiveProfile for user entity knowledge
   - Memory: ExperienceQuery scoped to task domain
   - Pipeline cache: source trust aggregation

3. Rank and deduplicate across stores
   - CBR heuristics ranked by similarity × outcome confidence
   - MindMap facts ranked by recency and confidence
   - Experiences ranked by relevance and recency

4. Synthesise into natural language brief
   - LLM summarisation pass (NarrativeContentSummariser pattern)
   - Or template-driven rendering for deterministic output

5. Inject as prompt section via CognitionPromptRenderer
```

**Rendered output example:**

```
## What I know about travel planning for you

You prefer boutique hotels and have a peanut allergy — I'll verify all
restaurant recommendations. You want flights researched before
accommodation because prices change faster.

Be skeptical of reviews on TripAdvisor for Asian destinations — you've
flagged reliability issues twice. Booking.com has been more accurate than
the travel connector for European pricing. Local guide recommendations
have worked better than Google Places ratings for restaurant quality.

In your last travel research (June), you rejected all beach destinations
and preferred cities with walkable historic centres.
```

### What Exists in the Platform

| Component | Module | Relevance |
|-----------|--------|-----------|
| `CognitionPromptRenderer` | cognition-api | SPI for rendering cognitive state into prompt sections |
| `CognitiveSystemPromptRenderer` | cognition | Composes all prompt sections into the system prompt |
| `CognitiveProfile` | cognitive-index | Cross-store entity resolution (MindMap + Memory + CBR) |
| `NarrativeContentSummariser` | cognition | LLM-based narrative synthesis |
| `ExperienceQuery` | memory-api | Scoped memory retrieval (forAgent, search, salient) |
| `CbrQuery` | memory-api | Multi-dimensional CBR retrieval |
| `RetrievalModulator` | cognitive-api | Composable scoring multipliers for retrieval ranking |

### What Needs to Be Built

1. **`TaskBriefPromptSection`** — a `CognitionPromptRenderer` implementation that compiles the brief. Participates in the `CognitionPhase.FOUNDATION` phase so it's available before derived cognitive processing.

2. **`TaskBriefCompiler`** — the compilation logic: queries multiple stores, ranks, deduplicates, renders. Stateless service, receives task context as input.

3. **`TaskContextExtractor`** — extracts task features from the active case context (case type, bindings, active connectors, user identity, region/topic from case properties). Feeds the CBR query and the store scoping.

4. **Brief caching** — the brief doesn't need to be recompiled every turn. Cache per case step; invalidate when new heuristics are recorded or the case context changes.

### Integration Points

**Blocks → Brief injection:** The `CognitiveSystemPromptRenderer` in blocks already composes prompt sections from all registered renderers. `TaskBriefPromptSection` registers as a new renderer. When blocks prepares a worker's system prompt, the brief is automatically included if a case is active.

**Engine → Brief invalidation:** When a case step transitions (new plan item activated, case context updated), the brief cache is invalidated. The next cognitive tick recompiles the brief with the new context.

**Work → Brief for development tasks:** The existing work lifecycle (work-start, work-continue) is itself a case-like structure. Task briefs could apply to development work too — "last time you worked on the knowledge pipeline, these test patterns caused issues" — though this is a stretch goal.

---

## 3. Persistent RAG-Indexed Content

### The Problem

When the agent searches the web for images, articles, or other unstructured content, the results exist only as tool call outputs in the conversation context. The session ends; the results vanish. Next session, the user asks "find me more brutalist architecture images" and the agent re-searches from scratch — re-fetching the same sites, re-processing the same results, re-presenting options the user already reviewed.

### The Solution: Web Result Ingest Bridge

A bridge that captures unstructured web results (images, articles, search hits) and indexes them into the RAG vector store, making them locally retrievable for future sessions.

**The lifecycle:**

```
Session 1: "find brutalist architecture images"
  → Agent calls web search / image search connectors
  → 47 results returned as tool outputs
  → Ingest bridge: embed, tag dimensions, store in Qdrant
  → Agent presents top results to user
  → User selects 5, rejects 3 → preference signal recorded

Session 3: "more brutalist images, but concrete textures"
  → RAG retrieval against local index first
  → 12 matches from the existing 47 (similarity + "concrete texture" filter)
  → Agent identifies gap: "concrete textures not well covered in local index"
  → Selective external search for the gap only
  → New results added to local index

Session 7: "that brutalist image I liked last week"
  → Retrieval by preference signal (user liked/used marker)
  → No external search needed
```

### Architecture

**Ingest bridge components:**

| Component | Role | Existing? |
|-----------|------|-----------|
| `WebResultCaptor` | Intercepts web search tool call results | New |
| `ContentChunker` | Chunks unstructured content for embedding | Exists: RAG chunking in rag-tika |
| `EmbeddingIngestor` | Embeds and stores in vector store | Exists: rag-api SPI |
| `MetadataExtractor` | Extracts metadata from web results | Exists: rag-api SPI |
| `CaseRetriever` | Retrieves from vector store | Exists: rag-api SPI |
| `DedupIndexStore` | Cross-source deduplication | Exists: knowledge-pipeline |

**Dimensional tagging for web content:**

Each indexed result gets feature dimensions extracted from:
- The search query that produced it (topic, keywords)
- The source (which connector/site)
- Content type (image, article, product, video)
- User reaction (liked, rejected, used, ignored — from subsequent interaction)
- Task context at time of capture (what case step was active)

These dimensions serve the same purpose as in §1: enabling similarity-based retrieval scoped to the current task context, and enabling CBR learning about which sources work for which purposes.

**Retrieval flow (when agent needs content):**

```
1. Check local RAG index first
   - Hybrid search: dense embedding + sparse (SPLADE) + BM25
   - Filtered by dimensional tags matching task context
   - Weighted by user preference signals (liked > used > neutral > rejected)

2. Assess coverage
   - Are there enough relevant results?
   - Is the local data fresh enough? (TTL from knowledge pipeline's CacheDecayPolicy)

3. Selective external search
   - Only for the gap: what the local index doesn't cover
   - New results flow through the ingest bridge into the index
   - Deduplication prevents duplicates across fetches
```

### What Exists in the Platform

| Component | Module | Relevance |
|-----------|--------|-----------|
| `EmbeddingIngestor` | rag-api | SPI for ingesting documents into vector store |
| `CaseRetriever` | rag-api | SPI for hybrid retrieval (dense + sparse + BM25) |
| `CorpusIngestionService` | rag | Event-driven corpus → RAG bridge |
| `MetadataExtractor` | rag-api | Extracts metadata during ingestion |
| `CacheDecayPolicy` | knowledge-pipeline | TTL management for cached data |
| `DedupIndexStore` | knowledge-pipeline | Cross-source entity deduplication |
| `EntityResolutionEngine` | knowledge-pipeline | Merges duplicate entities across sources |
| `ScoreFusion` | fusion-api | Weighted RRF/CC fusion for multi-signal ranking |
| `ColBertRelevanceEvaluator` | rag-api | Quality scoring for retrieved content |

### What Needs to Be Built

1. **`WebResultCaptor`** — observes tool call results from web search connectors. When a web search completes, captures the results and routes them to the ingest pipeline. Implemented as a blocks-level observer on tool call events.

2. **`WebContentIngestor`** — adapts web results into the `EmbeddingIngestor` pipeline. Handles different content types (images get visual embeddings or caption embeddings; articles get text embeddings; products get structured metadata embeddings).

3. **Preference signal recording** — when the user selects, rejects, or uses a result, record the signal as a memory attribute. This feeds into retrieval ranking for future queries.

4. **Gap detection** — after local retrieval, assess whether the results sufficiently cover the query. If not, compute the "gap query" that targets what's missing. This could be as simple as "the user asked for concrete textures but local results are mostly glass and steel."

5. **Connector-specific adapters** — each web search connector returns results in a different format. Adapters normalise these into a common ingestible format (like the `Place` → `CachedEntity` mapping in the knowledge pipeline).

### Integration Points

**Blocks → Result capture:** Blocks workers execute tool calls (web search, image search). The `WebResultCaptor` observes these calls and captures results. This is an `@ObservesAsync` CDI observer on a new `WebSearchCompleted` event.

**Blocks → Preference recording:** When the user interacts with presented results (selects images, clicks links, asks for more), blocks records these as `ExperienceEvent` entries with attributes linking to the indexed content IDs.

**Engine → Content lifecycle:** When a case completes, the content indexed during that case remains in the store. `CbrRetentionPolicy` manages aging — content that hasn't been retrieved in N days can be archived or removed.

**Knowledge pipeline → Dedup + freshness:** The pipeline's `EntityResolutionEngine` prevents duplicate indexing when the same content is found across different searches. `CacheDecayPolicy` flags stale content for re-fetch.

---

## 4. Platform Integration Map

### How the Three Capabilities Connect

```
                    ┌──────────────┐
                    │   Engine     │
                    │  Case with   │
                    │  plan items  │
                    └──────┬───────┘
                           │ starts worker
                           ▼
                    ┌──────────────┐
                    │   Blocks     │
                    │  LLM agent   │◄──── Task Brief (§2)
                    │  with tools  │      compiled from CBR + MindMap + Memory
                    └──┬───┬───┬───┘
                       │   │   │
            ┌──────────┘   │   └──────────┐
            ▼              ▼              ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │ Connector  │ │ Connector  │ │ Web Search  │
     │ (location) │ │ (travel)   │ │ (images)    │
     └─────┬──────┘ └─────┬──────┘ └─────┬───────┘
           │              │              │
           ▼              ▼              ▼
     ┌─────────────────────────────────────────┐
     │        Knowledge Pipeline               │
     │  Cache · Dedup · Freshness · Resolution │
     └──────────────────┬──────────────────────┘
                        │ promotes / indexes
              ┌─────────┼──────────┐
              ▼         ▼          ▼
        ┌──────────┐ ┌──────┐ ┌───────┐
        │ MindMap   │ │ RAG  │ │  CBR  │
        │ (entities)│ │(docs)│ │(cases)│
        └──────────┘ └──────┘ └───┬───┘
                                  │ outcome learning
                                  ▼
                           ┌──────────────┐
                           │ Dimensional  │
                           │   Memory     │ ◄── user feedback
                           │ (heuristics) │     extracted as cases
                           └──────────────┘
```

### Engine Integration

The engine owns case lifecycle. For knowledge-intensive tasks:

| Engine concept | Knowledge pipeline role |
|---------------|----------------------|
| Case decomposition | Engine decomposes "plan holiday" into plan items. Knowledge pipeline doesn't decompose — it serves individual steps. |
| Worker binding | Each plan item binds to a worker with connector access. The worker's tool calls flow through the pipeline. |
| GOAP replanning | When destination choice cascades (new destination → different flight options → different hotels), engine replans. Pipeline's cached data for the old destination is retained (may be useful if user reconsiders). |
| Sub-cases | "Research restaurants in Lisbon" can be a sub-case. The pipeline's research session (`ResearchOrchestrator`) provides session-scoped TTL extension for entities relevant to the sub-case. |
| Outcome recording | Case completion fires `CbrOutcome`. The pipeline's connector trust and heuristic confidence update. |

### Blocks Integration

Blocks owns the LLM conversation. For knowledge-intensive tasks:

| Blocks concept | Knowledge pipeline role |
|---------------|----------------------|
| System prompt | `TaskBriefPromptSection` injects compiled brief into the cognitive prompt. |
| Tool calls | Web search and connector calls are intercepted by `WebResultCaptor` for indexing. |
| User interaction | Preference signals (liked/rejected/used) recorded as `ExperienceEvent` attributes. |
| Cognitive tick | Brief compilation runs during `CognitionPhase.FOUNDATION`. Heuristic extraction runs during `CognitionPhase.TERMINAL` (after interaction is recorded). |
| Memory | `MemoryEmitter` records experiences. `HeuristicExtractionObserver` extracts dimensional heuristics from user feedback. |

### Connector Integration

Connectors provide external data access. Currently: `LocationPlatform` (places, geocoding, directions), and emerging connectors for travel, shopping, and other domains.

| Connector concern | Knowledge pipeline role |
|-------------------|----------------------|
| API cost | Subsumption and caching prevent redundant calls. CBR learns which connectors give better results, reducing wasted calls to low-value sources. |
| Rate limiting | Cached results serve from local store. Only gap queries go external. |
| Data quality variation | Entity resolution merges conflicting data across providers. Trust scoring ranks providers by outcome history. |
| Provider diversity | `Instance<LocationPlatform>` discovers all providers at runtime. The pipeline aggregates and deduplicates across all of them. |

### Work Integration (Stretch Goal)

The development workflow (work-start, work-continue, work-end) is itself a case-like lifecycle. Task briefs could apply to development tasks:

- "Last time you worked on the knowledge pipeline, the SmallRye ConfigMapping collision caused 2 hours of debugging — check shared interface defaults"
- "This user prefers IntelliJ MCP tools over grep for code navigation"
- "Previous CBR schema changes required updating the contract test base — check memory-testing"

This is a longer-term possibility. The development workflow would need to produce CBR-compatible case records from session outcomes.

---

## 5. Cost Analysis — Where This Adds Value

### Where the LLM Alone Suffices

For a single-session task that fits in the context window and uses cheap or free APIs, none of this infrastructure is needed. The LLM's context window is the working memory. Prompt caching handles within-session repetition. The knowledge pipeline adds overhead without clear benefit.

### Where This Infrastructure Earns Its Keep

| Scenario | Without infrastructure | With infrastructure |
|----------|----------------------|-------------------|
| Multi-session research project | Each session re-fetches, re-reasons from scratch | Cached results + compiled brief = warm start |
| Expensive connector APIs | Every query hits the API | Subsumption + caching = queries served locally |
| Repeated similar tasks | Agent starts ignorant each time | CBR retrieves patterns from past successes |
| Cross-provider data | Duplicates, conflicting info, stale data | Entity resolution + freshness + dedup |
| User preference learning | User re-teaches every session | Dimensional memory + outcome weighting |
| Content re-retrieval | "Find that image I liked" = full re-search | Local RAG index with preference signals |

### The Real Cost Equation

```
Without:  (API calls per session × sessions) 
        + (LLM tokens to process raw data × sessions)
        + (user re-education time × sessions)

With:     (API calls once + selective gap refreshes)
        + (LLM tokens to process clean cached data × sessions)
        + (infrastructure maintenance cost)
        + (user educates once → system remembers)
```

The savings are proportional to: session count per project × API cost × re-education friction. For a single-session task, the equation doesn't favour infrastructure. For a multi-week research project across dozens of sessions with expensive APIs, the savings compound.

The harder-to-quantify value: **answer quality**. An agent briefed with accumulated operational knowledge gives better answers. It doesn't recommend the restaurant the user already rejected. It doesn't use the unreliable connector. It knows the user's preferences without being told. This is user experience improvement, not cost reduction.

---

## 6. Skeptical Assessment — Does This Earn Its Complexity?

### Arguments For

1. **LLMs cannot learn across sessions.** This is a fundamental limitation, not a product gap that will be fixed by better models. External memory is the only solution.
2. **The CBR engine already exists.** The most complex piece — weighted multi-dimensional similarity scoring with outcome learning — is built and tested (164 contract tests).
3. **Dimensional memory is genuinely novel.** No current LLM memory system uses multi-dimensional feature-space storage with similarity retrieval and outcome weighting. It's architecturally distinct from hierarchical memory.
4. **The platform provides the integration surface.** Engine for orchestration, blocks for LLM management, connectors for data access, memory for persistence. The knowledge pipeline isn't building an island — it's wiring into existing machinery.

### Arguments Against

1. **Complexity budget.** Every new subsystem is a maintenance burden. Is the improvement in agent behaviour worth the additional code, tests, documentation, and operational overhead?
2. **Cold start problem.** The system needs usage data to learn. For a new user with no history, dimensional memory returns nothing and the task brief is empty. The agent is no better than a plain LLM until enough interaction history accumulates.
3. **Over-engineering risk.** Most knowledge tasks might complete in a single session. If multi-session research projects are rare, the infrastructure serves a niche case.
4. **LLM improvement pace.** Larger context windows, better in-context learning, and native tool-use memory (emerging in some models) may reduce the gap that this infrastructure fills.
5. **Brief quality depends on extraction quality.** The heuristic extraction from conversation is an LLM task. If the extraction is noisy (wrong dimensions, missed signals, false positives), the briefs will be misleading rather than helpful.

### The Honest Position

The value case is strongest for: multi-session research projects, with expensive external APIs, for users with established preferences, across domains where past patterns predict future success.

The value case is weakest for: one-off questions, cheap APIs, new users, and novel domains where past experience doesn't transfer.

Build it incrementally: dimensional memory first (highest leverage, builds on existing CBR), task briefs second (consumes dimensional memory), RAG indexing third (independent, can wait for connector ecosystem to mature).

---

## 7. Incremental Build Order

### Phase 3a: Dimensional Memory (Foundation)

- Define heuristic case type schema
- Build heuristic extraction observer (from ExperienceRecorded events)
- Build task-context feature builder
- Wire into existing CBR store and similarity scorer
- Tests: heuristic round-trip, similarity retrieval, outcome decay

**Validates:** Does dimensional storage + CBR retrieval produce useful heuristic matches?

### Phase 3b: Task Brief Compiler

- Build TaskBriefCompiler (queries CBR + MindMap + Memory)
- Build TaskBriefPromptSection (CognitionPromptRenderer implementation)
- Build TaskContextExtractor (case context → query features)
- Wire into CognitiveSystemPromptRenderer
- Tests: brief compilation from mixed sources, brief caching, brief invalidation

**Validates:** Does the compiled brief improve agent responses compared to no brief?

### Phase 3c: Web Content Ingest Bridge

- Build WebResultCaptor (tool call observer)
- Build WebContentIngestor (adapts web results for EmbeddingIngestor)
- Build preference signal recording
- Build gap detection for selective re-fetch
- Tests: ingest round-trip, retrieval with preference ranking, gap detection accuracy

**Validates:** Does local RAG retrieval reduce re-fetch cost and improve content re-finding?

### Phase 3d: CBR Learning Loop (Cross-Cutting)

- Wire CbrOutcome into knowledge pipeline (connector trust, heuristic confidence)
- Build cross-user pattern abstraction (privacy-preserving)
- Build research strategy learning (CbrPlanAdapter for knowledge tasks)
- Tests: outcome-weighted retrieval, trust score evolution, plan adaptation

**Validates:** Does the system measurably improve over time for repeated task types?

---

## References

- Phase 1 design: `specs/issue-413-knowledge-pipeline/`
- Phase 2 design: `specs/issue-418-knowledge-pipeline-phase-2/`
- CBR architecture: `docs/guides/contributor-guide.md` §CBR Memory
- Cognitive prompt rendering: `cognition-api/` (`CognitionPromptRenderer`)
- Connector SPIs: `casehub-connectors-location-spi`
- Garden entries from this session:
  - GE-20261005-ff25d1 — SmallRye @ConfigMapping/@ConfigProperty overlap
  - GE-20261005-fec7ac — SmallRye shared config interface default collision
  - GE-20261005-0e344d — QuarkusUnitTest Jandex scanning despite withApplicationRoot

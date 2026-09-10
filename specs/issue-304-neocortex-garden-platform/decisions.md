# Decisions — #304 Extract hortora/engine capabilities into neocortex

## D1: CBR naming cleanup scope

**Choice:** Include CBR naming cleanup in this design
**Alternatives:**
- Separate issue — orthogonal rename, reduces spec scope
- Defer entirely — only rename when a consumer is confused
**Rationale:** Doing the rename during extraction ensures naming consistency from the start. The rename touches memory-api which is already being modified for the outcome SPI.
**Trade-offs:** Larger spec scope
**Sources:** Hortora/engine#90 (CBR naming cleanup section)
**Exploration:** quick
**Status:** captured

## D2: Federation extraction

**Choice:** Move federation to neocortex as a platform capability (new rag-federation module)
**Alternatives:**
- Defer — leave in engine until a second consumer appears
- Extract as-is — move code unchanged without SPI design
**Rationale:** Federation sits on top of CaseRetriever, scoring, and result merging. Building it outside neocortex means duplicating retrieval internals. It can't be built effectively outside the platform.
**Trade-offs:** Adds a module for ~404 LOC with currently one consumer
**Sources:** engine ChainWalker.java (~184 LOC), FederationConfig.java, FederationConfigParser.java, RemoteGardenClient.java
**Exploration:** quick
**Status:** captured

## D3: Outcome service as SPI

**Choice:** Port outcome service to neocortex and refactor to SPI, extending RetrievalTracker with an outcome axis
**Alternatives:**
- New OutcomeTracker SPI — separate from RetrievalTracker, distinct lifecycle
- Unify in RetrievalFeedback — extend the record to carry optional OutcomeResult
**Rationale:** Retrieval relevance and execution outcome are two judgments about the same retrieval event. Keeping both on RetrievalTracker preserves the link. CBR recordOutcome stays separate (it scores cases, not retrievals).
**Trade-offs:** RetrievalTracker SPI grows; outcome feedback arrives much later than retrieval feedback
**Sources:** RetrievalTracker.java (rag-api), CbrCaseMemoryStore.recordOutcome() (memory-api), Hortora/engine#90 (two-axis feedback model)
**Exploration:** quick
**Depends on:** D1 (CBR naming — outcome wiring touches the same area)
**Status:** captured

## D4: Extraction ordering

**Choice:** Bottom-up SPIs first (scoring/outcome/provenance → adaptive search/migration → federation)
**Alternatives:**
- Highest-value first — adaptive search first, rework if SPI boundaries shift
- Match issue phases — follow #304's 5-phase structure as written
**Rationale:** Foundations must exist before consumers. Each layer can be consumed by engine incrementally. No rework when later phases build on earlier SPIs.
**Trade-offs:** Highest-value capability (adaptive search) isn't delivered until Phase 2
**Sources:** neocortex module dependency graph, engine source survey
**Exploration:** quick
**Status:** captured

## D5: Post-retrieval scoring module placement

**Choice:** PostRetrievalScorer SPI in rag-api; impls (temporal decay, version scorer) + adaptive search wrapper + QueryGenerator impl + search profiles in new rag-scoring module
**Alternatives:**
- All in rag-api — fewer modules but mixes SPI definitions with implementations
- Three separate modules (scoring-api + scoring-runtime + adaptive-search) — maximum separation but adds 3 modules for ~700 LOC
**Rationale:** Follows the established rag-* pattern (rag-api for SPI, rag-crossencoder/rag-expansion/rag-tracking for impls). rag-scoring groups retrieval-quality features that enhance search results.
**Trade-offs:** One new module to maintain
**Sources:** rag-crossencoder, rag-expansion, rag-tracking (existing pattern)
**Exploration:** quick
**Status:** captured

## D6: Provenance module placement

**Choice:** New rag-provenance module (ProvenanceTracker SPI in rag-api, SQLite impl in rag-provenance)
**Alternatives:**
- Extend rag-tracking — share the tracking concept but different query patterns
- SPI only in rag-api — minimal extraction, engine keeps its impl
**Rationale:** Provenance (document→decision lineage) is orthogonal to retrieval tracking (retrieval events). Separate module avoids coupling and follows the classpath-activation pattern.
**Trade-offs:** One more module; provenance currently has one consumer
**Sources:** engine ProvenanceStore.java (~192 LOC), rag-tracking pattern
**Exploration:** quick
**Status:** captured

## D7: Federation module placement

**Choice:** New rag-federation module with FederatedRetriever as a CaseRetriever @Decorator
**Alternatives:**
- Inside rag module — alongside HybridCaseRetriever, less modular
- Separate federation-api + federation — full SPI split, maximum extensibility
**Rationale:** Follows the decorator pattern already used by CRAG, reranking, expansion, tracking. Remote client + topology config + loop detection are cohesive. @Decorator on CaseRetriever lets federation compose naturally with the existing decorator chain.
**Trade-offs:** One more module
**Sources:** engine ChainWalker.java, CaseRetriever decorator chain (CorrectiveCaseRetriever, RerankingCaseRetriever, QueryExpandingCaseRetriever, TrackingCaseRetriever, PayloadBoostCaseRetriever)
**Exploration:** quick
**Status:** captured

## D8: Query augmentation approach

**Choice:** QueryGenerator SPI in rag-api, impl in rag-scoring using AgentProvider (platform's LLM abstraction)
**Alternatives:**
- Separate rag-query-augmentation module — own module for classpath activation
- SPI only, defer impl — let engine keep its Ollama version
**Rationale:** Neocortex uses ChatModel through platform's AgentProvider, not LangChain4j implementations directly. The impl is a thin adapter — no provider-specific code. Ollama or any other provider is configuration via AgentProvider. Groups with other retrieval-quality features in rag-scoring.
**Trade-offs:** rag-scoring gains a platform-api dependency for AgentProvider
**Sources:** platform AgentProvider, engine OllamaQueryGenerator.java (~228 LOC)
**Exploration:** quick
**Status:** captured

## D9: Collection migration placement

**Choice:** Extend rag module with migration checks alongside QdrantEmbeddingIngestor
**Alternatives:**
- New rag-migration module — clean separation but small (~186 LOC)
- Defer — leave in engine
**Rationale:** Collection migration (dimension check, sparse vector check, auto-reindex) is infrastructure that belongs with collection management. Not enough code for a separate module.
**Trade-offs:** rag module grows slightly
**Sources:** engine CollectionMigration.java (~186 LOC), neocortex rag/QdrantEmbeddingIngestor
**Exploration:** quick
**Status:** captured

## D10: CBR naming

**Choice:** PlanCbrCase → ResolvedCase, TextualCbrCase → ResolutionGuide, unified under "Resolution" concept
**Alternatives:**
- Discuss alternatives — explore different naming
**Rationale:** Clear semantic distinction between "what happened" (ResolvedCase — historical execution trace) and "what to do" (ResolutionGuide — prose resolution guidance). "Resolution" is the unifying concept.
**Trade-offs:** Breaking rename across memory-api consumers (neocortex + engine)
**Sources:** Hortora/engine#90 (CBR naming cleanup section)
**Exploration:** quick
**Depends on:** D1 (included in this design)
**Status:** captured

## D11: Engine thinning approach

**Choice:** Include stripping extracted code from engine in this spec — each extraction phase removes code from engine and points to neocortex dependency
**Alternatives:**
- Separate Hortora/engine issue — cleaner repo boundary but risks drift
**Rationale:** Covering both sides (what goes into neocortex AND what leaves engine) ensures engine stays working throughout. Each phase is a complete extraction: add to neocortex, remove from engine, verify.
**Trade-offs:** Spec covers two repos, more coordination
**Sources:** Hortora/engine#90 (end state section)
**Exploration:** quick
**Status:** captured

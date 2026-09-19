# HANDOFF — casehub-neocortex

## Last Session

10-dimension GA code audit + urgent CBR fix.

### Audit (epic #355)
Ran parallel audits across decorator ordering, pipeline coherence, duplication, CDI wiring, layers, reliability, thread safety, SPI completeness, configuration, and API surface. 31 findings total.

**Fixed inline (8 commits on main):**
- ConsolidationScheduler: top-level try-catch, extract runPhases(), awaitTermination, beginTick() on SPI
- ConfidenceDecayCdiDecorator @Priority(55) wired into CDI (was silently inactive)
- safeFire() on 3 notification decorators + AffectTrajectoryDecorator (failure isolation)
- CaseRetriever @Priority(50→40) conflict resolved
- DiversityCbrCaseMemoryStore wired into CDI @Priority(55) with @IfBuildProperty gate
- RetrievalAccessTracker atomic volatile swap (race condition fix)
- RAG reranking config renamed: casehub.rag.retrieval.rerank-enabled → casehub.rag.reranking.colbert-fallback
- EmbeddingCache @PreDestroy added
- MindMap search switched from LIKE '%text%' to FTS5 MATCH
- O(n²) merge detection guard (>500 nodes) and O(V(V+E)) betweenness centrality guard (>2000 nodes)

**Deferred to 12 child issues (#356–#367):** batch graph ops, consolidation scaling, SQLite factory extraction, event recorder dedup, cbr-algorithms module, mindmap→cognitive-index dep, orphaned SPIs, API consistency, SPI Javadoc, config consistency, config docs, SPI completeness.

### CBR Fix (#368)
CbrSimilarityScorer changed from query normalization to intersection normalization. Features absent from the stored case are now skipped — they don't contribute weight to the denominator. This was causing AML integration tests to fail because queries with extra features scored below minSimilarity.

### Issues Closed
- #316 (contributor guide epic — all 9 child issues done)
- #350, #351 (eidos cycle issues — modules didn't exist, not applicable)
- #352 (work/engine-adapter — already moved to engine)
- #368 (CBR intersection normalization)

### Protocols Captured
4 universal protocols in garden: CDI observational decorator isolation, unique decorator priorities, scheduled task exception guards, volatile swap-and-reset atomicity.

## Next

Start #355 child issues — #356 (batch graph operations) is first in priority order.

## Open Branches

- `fix/368-cbr-intersection-normalization` — landed on main as 8f278213, needs stamp

## Cross-Module

- engine `fix/352-work-adapter` tests still skipped
- `CbrOutcomeConsumer` CLAUDE.md reference updated (was stale)
- engine AML tests should pass after rebuilding against latest neocortex (intersection normalization fix)

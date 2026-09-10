# HANDOFF — casehub-neocortex

## Last Session

Completed epic #295 (Knowledge Consolidation Pipeline) — full brainstorm-through-implementation cycle. 5 children closed (#296-#300), 1 deferred item (Layer 2 embedding confirmation for merge detection).

**What was built:**
- `ConversationBridge` — fast rule-based text segmentation into topical chunks, creates initial "general" nodes with STATED confidence, fires `ExtractionRequested` CDI event for async MindMapExtractor enrichment
- `ExtractionRequestedObserver` — `@ObservesAsync` invokes MindMapExtractor, supersedes segment nodes with extracted entities via `store.supersede()`
- `ConsolidationScheduler` — `ScheduledExecutorService` daemon thread with idle guard (IdleTracker ≥1 min), `ReentrantLock.tryLock()` concurrency control, tenant enumeration via `discoverTenants()`
- `ConsolidationPhase` SPI — 4-phase pipeline: AccessFrequencyPhase (@Priority(10)), MergeDetectionPhase (@Priority(20)), CommunitySummaryPhase (@Priority(30)), CuriosityRefreshPhase (@Priority(40))
- `RetrievalAccessTracker` — in-memory ConcurrentHashMap with atomic `swapAndReset()`, tracks at retrieval boundary (not store layer)
- `RetrievalStrength` — Bjorks dual-strength model, read-time projection via `log1p`-modulated half-life
- `AccessFrequencyPhase` — flush write-behind `storageStrength` counters with tick-generation caching for multi-tenant correctness
- `MergeDetectionPhase` Layer 1 — Jaro-Winkler name similarity + Jaccard neighbor overlap, auto-merge ≥0.9, flag [0.7,0.9)
- `MindMapAnalyzer.kCores` — O(V+E) k-core decomposition for community detection
- `CommunitySummaryPhase` — k-core clustering + LLM summary generation, hash-based invalidation, stale summary cleanup, Summary-trait nodes filtered from core membership
- `CuriosityRefreshPhase` — thin delegate to CuriositySignalGenerator
- `IdleTracker` + `MindMapStoreIdleTracker` — `@Decorator @Priority(30)` records writes for idle detection

**Design process:** 6 decisions (D1-D6), light decision review (34 issues, all addressed), 3-round standard spec review ($24.73, 23 issues, 21 verified), code review (1 WARNING fixed: multi-tenant snapshot race).

**Key design decisions:**
- Pipeline logic in neocortex (mindmap-intelligence), not DraftHouse — platform boundary rule prevents app-to-app reuse (D1)
- DraftHouse provides thin KnowledgeFacet adapter — DraftHouse integration deferred as cross-project issue
- @Scheduled periodic with idle guard, non-persistent state (D2)
- Bjorks dual-strength model: storageStrength (monotonic, never decays) + retrieval strength (read-time projection) (D3 revised)
- k-core decomposition for community detection (D4 revised)
- Two-layer merge detection: string heuristic → optional embedding confirmation on candidates only (D5 revised)

**Deferred items:**
- MergeDetectionPhase Layer 2 (embedding confirmation) — needs Mockito or test EmbeddingModel stub
- DraftHouse KnowledgeFacet integration issue — cross-project coordination
- Promote `findOrCreateSubgraph` to MindMapStore default method — duplicated as private helper
- Consumer guide and contributor guide doc sync (impl_doc_sync skipped)

**Garden entries captured:**
- GE-20260910-8791cd — per-tenant phase iteration loses swap-and-reset snapshot
- GE-20260910-2a660e — k-core community detection includes synthetic nodes

## What's Next

Queue remaining from `.plan` (doc issues — separate branch):

| # | Title | Scale | Complexity |
|---|-------|-------|------------|
| 301 | docs: consumer guide — Thing model | M | Low |
| 302 | docs: contributor guide — Thing/MindMapNode | M | Low |
| 303 | docs: capability-to-example matrix | S | Low |

Start with `work` — queue will route to #301.

## References

- Epic #295 — Knowledge Consolidation Pipeline (#296, #297, #298, #299, #300)
- Epic #285 — Knowledge Representation Model (predecessor — Thing, SubgraphType→String, TypeRegistry)
- Spec: `docs/specs/issue-295-knowledge-consolidation/2026-09-10-knowledge-consolidation-pipeline-design.md`
- Decisions: `specs/issue-295-knowledge-consolidation/decisions.md` (workspace)
- Plan: `plans/2026-09-10-knowledge-consolidation-pipeline.md` (workspace)

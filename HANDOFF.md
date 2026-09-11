# HANDOFF — casehub-neocortex

## Last Session

Closed #304 branch (knowledge garden platform extraction) via work-end. Created `.plan` with 14 items for next session.

**What landed on main (11 commits after squash):**
- 4 new SPIs in rag-api: `PostRetrievalScorer`, `ProvenanceTracker`, `FederationStrategy`, `DocumentQueryAugmenter`
- 2 new modules: `rag-scoring` (TemporalDecayScorer, VersionScorer, AdaptiveSearchWrapper), `rag-query-augmentation` (AgentQueryAugmenter, QueryAugmentingMetadataExtractor)
- `CollectionCompatibility` utility in rag module (generic migration checks)
- CBR rename: PlanCbrCase → ResolvedCase, TextualCbrCase → ResolutionGuide, PlanTrace → ResolutionStep
- `CbrOutcome.retrievalId` for retrieval-to-outcome correlation
- Code review fix: stale error message in ResolvedCase after rename

**Filed this session:** casehubio/neocortex#306 (CollectionCompatibility unit tests)

**Diary entry:** `blog/2026-09-11-mdp01-the-extraction-that-wasnt-a-rewrite.md`

## What's Next

`.plan` has 14 items — 2 in queue, 12 deferred Hortora/engine tasks. Start with `work` to pick up casehubio/neocortex#306.

| # | Title | Scale | Complexity |
|---|-------|-------|------------|
| casehubio/neocortex#306 | CollectionCompatibility unit tests | XS | Low |
| casehubio/neocortex#305 | Feedback context enrichment | M | Med |

Deferred (Hortora/engine — requires engine slot):
- Hortora/engine#90 parent epic + 3 sub-tasks (rag-scoring, SPIs, CBR rename)
- Hortora/engine#89, #88, #86, #84, #82, #72, #61, #58

## References

- Spec: `wksp/specs/issue-304-neocortex-garden-platform/2026-09-10-neocortex-garden-platform-design.md`
- Decisions: `wksp/specs/issue-304-neocortex-garden-platform/decisions.md` (12 decisions)
- Cross-ref: Hortora/engine#90
- Garden: GE-20260911-42a250 (IntelliJ rename gotcha)

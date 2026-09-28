# HANDOFF — casehub-neocortex

## Last Session

Landed **casehubio/neocortex#338** — TrajectoryGrouper: group experience memories into structured trajectories for reflection synthesis.

Also landed **casehubio/blocks#320** — LlmReflectionSynthesizer: LLM-backed heuristic extraction from experience trajectories.

### neocortex#338
- **TrajectoryGrouper** static utility in `memory-core` — groups flat `List<Memory>` by caseId, orders by timestamp, sub-groups by turn-id, classifies FAILURE/SUCCESS/NEUTRAL via outcome-status attribute, sorts failure-first
- **Trajectory**, **TrajectoryStep**, **TrajectoryOutcome** records
- 11 unit tests, code review (1 NOTE fixed: explicit switch instead of enum ordinal for sort order)
- Design spec: `specs/issue-338-reflection-synthesizer-llm/2026-09-28-reflection-synthesizer-llm-design.md` (6 decisions, light decision review with D1 revised — cross-repo split per issue-345 SPI-inversion pattern)
- Implementation plan: `plans/2026-09-28-reflection-synthesizer-llm.md`

### blocks#320
- **LlmReflectionSynthesizer** `@Alternative @Priority(1)` in `blocks` module (`io.casehub.blocks.agentic.social.reflection`)
- Uses `TrajectoryGrouper` for pre-processing, `AgentProvider.invoke()` for single-pass LLM call
- Conditional rule output format: "When {condition}, {action}"
- Failure-derived heuristics prioritised, dedup against existing reflections via prompt context
- 7 unit tests with mock AgentProvider
- `memory-core` dependency added to blocks pom.xml

### Also created
- **blocks#311** — epic: Neocortex cognitive integration — wire landed capabilities into agent loop (XL/High)
- Child issues: #312 (consolidation), #313 (CBR), #314 (reflection consumption), #315 (engagement — closed by another session), #316 (TemporalFocus — closed), #317 (SocialComparison), #318 (DomainActivation), #319 (CognitiveProfile)
- **blocks#320** — LlmReflectionSynthesizer issue (created and closed this session)

### Key design decision
D1 revised after decision review: neocortex stays LLM-free (mechanical substrate). LLM-backed SPI implementations belong in blocks per issue-345 SPI-inversion pattern. MindMapExtractor and CommunitySummaryPhase predate this boundary — legacy exceptions, not precedent.

## Immediate Next Step

**blocks#312** — Consolidation signal consumption: graduation, merge, curiosity in agent reasoning (M / Med). Independent of #314 (being worked on in another slot). Wires CDI events from neocortex consolidation phases into blocks agent loop.

Other open blocks#311 children: #313 (CBR, L/High), #317 (SocialComparison, M/High), #318 (DomainActivation, M/High), #319 (CognitiveProfile, M/Med).

## All Branches Closed

All branches across all 6 repos (neocortex, blocks, platform, engine, eidos, desiredstate) are stamped closed. Both repos pushed to remote.

## References

- neocortex landed: 77925761 on main
- blocks landed: db4ee2ec on main
- Design spec: `specs/issue-338-reflection-synthesizer-llm/2026-09-28-reflection-synthesizer-llm-design.md`
- Implementation plan: `plans/2026-09-28-reflection-synthesizer-llm.md`
- Decision review: `/Users/mdproctor/reviews/casehub-slots/issue-338-decisions-20260928-114445/`

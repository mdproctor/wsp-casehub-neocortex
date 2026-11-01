## D1: Tick-scoped context on CognitiveMemoryRetriever

**Choice:** Add `setTickContext(ModulationContext)` to CognitiveMemoryRetriever. CognitionCore calls it once per tick after FOUNDATION phase. Orchestrators use the convenience `query(MemoryQuery)` method which picks up the pre-set context.
**Alternatives:**
- Full context injection per orchestrator — each orchestrator gets MoodOrchestrator + CognitiveDefaultsRegistry + builds its own ModulationContext. More coupling, duplicated assembly.
- CognitionCore pre-fetches memories and passes them — too coarse, orchestrators need different queries.
**Rationale:** CognitionCore already has mood, personality, drives — centralizing context assembly follows the existing tick-scoped-state pattern (lastAgentId, lastDescriptor, etc.). Orchestrators stay simple with one nullable parameter.
**Trade-offs:** Retriever carries mutable tick-scoped state. Thread safety via volatile or ConcurrentHashMap (same pattern as GutFeelingParticipant).
**Sources:** CognitionCore.java:133 (existing volatile tick state), CognitiveMemoryRetriever.java:38 (existing convenience method), ModulationContext.java
**Exploration:** deep-analysis
**Status:** captured

## D2: Integration scope — 5 points across 2 layers

**Choice:** Layer 1 (direct substitution): GutFeelingParticipant. Layer 2 (supplementary LLM context): StrategyLearningOrchestrator, MentalModelOrchestrator, UserModelOrchestrator. Skip NarrativeOrchestrator (no LLM call), consolidation phases (system operations), CognitiveGoalOrchestrator (only writes).
**Alternatives:**
- Include NarrativeOrchestrator — but it has no LLM call; narrative synthesis lives in NarrativePipeline, a separate scope.
- Include NarrativePipeline — increases scope beyond the 4 named orchestrators.
**Rationale:** Targets every component in the cognition tick cycle that (a) queries CaseMemoryStore or (b) does LLM reasoning that would benefit from modulated general memories. NarrativeOrchestrator genuinely has no retrieval or LLM to integrate with.
**Trade-offs:** Narrative synthesis (NarrativePipeline) does not get modulated memories. Follow-up issue.
**Sources:** GutFeelingParticipant.java:57, StrategyLearningOrchestrator.java:257, MentalModelOrchestrator.java, UserModelOrchestrator.java, NarrativeOrchestrator.java (70 lines, no LLM)
**Exploration:** deep-analysis
**Status:** captured

## D3: Constructor injection wiring pattern

**Choice:** Each orchestrator receives `@Nullable CognitiveMemoryRetriever` as a constructor parameter. Null-safe — when not available, no supplementary memories. CDI wiring via CognitionDefaultBeans / CognitionCoreFactory.
**Alternatives:**
- CognitionCore mediates — passes memories during tick. Changes tick signatures.
- Shared CognitionTickContext — extends context record with memories. Couples all participants.
**Rationale:** Constructor injection follows the existing orchestrator pattern (all orchestrators already have nullable optional dependencies). Null-safe graceful degradation matches other integrations (SessionPipeline, EntityAnnotationIndex).
**Trade-offs:** Each orchestrator constructor gains one parameter.
**Sources:** CognitionCoreFactory.java:76 (existing Instance<> injection pattern), CognitionDefaultBeans.java:239
**Exploration:** quick
**Status:** captured

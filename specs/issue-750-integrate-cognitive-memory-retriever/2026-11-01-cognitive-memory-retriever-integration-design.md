# Integrate CognitiveMemoryRetriever into Cognitive Orchestrators

**Issue:** casehubio/neocortex#750 (child of #736)
**Date:** 2026-11-01
**Status:** Design

## Problem

`CognitiveMemoryRetriever` (added in #736, #749) wraps `CaseMemoryStore` with
configurable modulation factors (recency decay, confidence weight, mood
congruence, goal relevance, domain weight, entity overlap). It is wired into
`CognitionCore` via `configureCognitiveMemoryRetriever()` but no cognitive
component uses it yet.

**Issue description mismatch:** The issue names four orchestrators
(Strategy, Narrative, MentalModel, UserModel) as using `CaseMemoryStore.query()`
directly. In fact, none of them do — they all use CBR-backed `*Memory` wrappers
(`StrategyMemory`, `NarrativeMemory`, `MentalModelMemory`, `UserProfileMemory`).
The actual `CaseMemoryStore.query()` callers in the cognition module are
`GutFeelingParticipant`, `RelationshipStagePhase`, and
`RelationalSchemaEvolutionPhase`.

The integration therefore has two layers:
1. **Direct substitution** — replace raw `CaseMemoryStore.query()` with modulated retrieval
2. **Supplementary context** — enrich orchestrator LLM prompts with modulated general memories

## Architecture

### Tick-Scoped Context (D1)

`CognitiveMemoryRetriever` gains tick-scoped state so callers don't need to
assemble `ModulationContext` themselves.

```java
// CognitiveMemoryRetriever additions
private volatile ModulationContext tickContext;

public void setTickContext(ModulationContext context) {
    this.tickContext = context;
}

public List<Memory> query(MemoryQuery query) {
    var ctx = tickContext;
    if (ctx == null) {
        ctx = new ModulationContext(null, query.tenantId(), null, null, null);
    }
    return query(query, ctx);
}
```

**CognitionCore.tick()** calls `setTickContext()` after FOUNDATION phase (mood
is available) and before SOURCE phase (first orchestrator runs):

```java
// In CognitionCore.tick(), after mood tick, before SOURCE phase
if (cognitiveMemoryRetriever != null) {
    var moodState = mood.currentMood(agentId, tenantId).orElse(null);
    var personality = defaultsRegistry != null
        ? defaultsRegistry.forAgentOrDefaults(agentId).personalityWeights()
        : null;
    cognitiveMemoryRetriever.setTickContext(
        new ModulationContext(agentId, tenantId, moodState, personality, Set.of()));
}
```

This follows the existing pattern: `lastAgentId`, `lastDescriptor`,
`lastBriefing` are all tick-scoped volatile state on CognitionCore.

### Integration Points (D2)

#### Layer 1: Direct Substitution — GutFeelingParticipant

GutFeelingParticipant currently calls `memoryStore.query(ExperienceQuery.search())`
for Layer 1 experience matching and `memoryStore.scan()` for Layer 2 affect
distance.

**Change:** Replace `CaseMemoryStore` with `CognitiveMemoryRetriever` for
Layer 1 (experience search). Layer 2 (affect scan via `MemoryScanRequest`)
stays on raw `CaseMemoryStore` — scan is a domain-filtered bulk read, not a
ranked retrieval that benefits from modulation.

```java
// Before
private final @Nullable CaseMemoryStore memoryStore;

// After
private final @Nullable CognitiveMemoryRetriever memoryRetriever;
private final @Nullable CaseMemoryStore memoryStore; // retained for scan()
```

Layer 1 query changes from `memoryStore.query(query)` to
`memoryRetriever.query(query)`. Gut feeling is inherently subjective — mood
congruence modulation makes semantically similar *negative* experiences surface
when the agent is in a negative mood state, producing appropriate
AVOID/CAUTIOUS gut reactions.

#### Layer 2: Supplementary LLM Context — Three Orchestrators

Each orchestrator gains `@Nullable CognitiveMemoryRetriever` via constructor
injection (D3). In their LLM prompt-building methods, they query modulated
general memories and include them as supplementary context.

**StrategyLearningOrchestrator** — `doReflect()` and `doReflectAsync()`

Query: `ExperienceQuery.forAgent(agentId, tenantId)` with limit 5.
Insert into the reflection prompt after the per-subject summary section.
Mood-congruent experience memories shape how the agent reflects on engagement
patterns — a positive mood foregrounds successful interactions, a negative mood
foregrounds friction points.

```java
// In buildReflectionPrompt(), append:
if (retriever != null) {
    var memories = retriever.query(ExperienceQuery.forAgent(agentId, tenantId).withLimit(5));
    if (!memories.isEmpty()) {
        sb.append("\nRelevant experience memories (modulated by current state):\n");
        for (var m : memories) {
            sb.append("  - ").append(truncate(m.text(), 120)).append("\n");
        }
    }
}
```

**MentalModelOrchestrator** — BDI extraction LLM call

Query: `ExperienceQuery.search(agentId, tenantId, subjectId)` with limit 3.
Include in the BDI extraction prompt as prior context about the subject. The
agent's mood biases how it interprets others' mental states — this is
psychologically grounded (anxious perceivers attribute more negative intent,
confident perceivers read interactions more favorably).

**UserModelOrchestrator** — profile synthesis LLM call

Query: `ExperienceQuery.search(agentId, tenantId, subjectId)` with limit 3.
Include in the synthesis prompt as supplementary interaction context.
Recency-weighted memories foreground recent behavioral changes in the user.

### Wiring (D3)

Constructor injection with null-safe graceful degradation.

**CognitionDefaultBeans** already produces `CognitiveMemoryRetriever`. The
orchestrator producers (`StrategyLearningOrchestrator`, `MentalModelOrchestrator`,
`UserModelOrchestrator`) in `CognitionDefaultBeans` gain an additional
`Instance<CognitiveMemoryRetriever>` parameter.

**CognitionCoreFactory** — no change needed. The orchestrators are injected
into the factory already constructed. The retriever is injected into the
factory and passed to `CognitivePipelineBuilder.cognitiveMemoryRetriever()`.

**GutFeelingParticipant** — CognitivePipelineBuilder already has
`gutFeeling(CaseMemoryStore)`. Change to also accept the retriever, or add a
separate builder method. CognitionCoreFactory passes both.

### Not In Scope

- **NarrativeOrchestrator** — 70-line class with no LLM call. Narrative
  synthesis lives in `NarrativePipeline`. Follow-up issue.
- **Consolidation phases** (`RelationshipStagePhase`,
  `RelationalSchemaEvolutionPhase`, etc.) — system operations that must use
  unmodulated `CaseMemoryStore` directly.
- **CognitiveGoalOrchestrator** — only writes to `CaseMemoryStore`, never queries.
- **LlmReflectionSynthesizer** — loads existing reflections for dedup, not
  ranked retrieval.

## Testing

Each integration point needs:

1. **Unit test with modulated retriever** — verify orchestrator includes
   supplementary memories in its LLM prompt when retriever is available
2. **Unit test without retriever** — verify null-safe graceful degradation
   (existing behavior unchanged)
3. **GutFeelingParticipant** — verify Layer 1 uses modulated retrieval while
   Layer 2 (affect scan) uses raw store

Existing orchestrator tests must continue passing — the retriever is additive,
not replacing existing CBR queries.

No new contract tests needed — CognitiveMemoryRetriever's modulation is already
tested in cognitive-index.

## References

- CognitiveMemoryRetriever.java — wraps CaseMemoryStore with modulation
- CognitionCore.java:133 — existing volatile tick-scoped state pattern
- CognitionDefaultBeans.java:239 — CDI producer with config-gated factors
- GutFeelingParticipant.java:57 — existing CaseMemoryStore.query() call
- StrategyLearningOrchestrator.java:257 — doReflect() prompt building
- MentalModelOrchestrator.java — BDI extraction LLM call
- UserModelOrchestrator.java — profile synthesis LLM call
- NarrativeOrchestrator.java — 70 lines, no LLM call (excluded)
- specs/issue-253-cognitive-rearchitecture/2026-08-31-retrieval-modulation-design.md — original modulation design

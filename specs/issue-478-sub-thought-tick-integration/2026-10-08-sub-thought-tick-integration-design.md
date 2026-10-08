# Sub-Thought Tick Lifecycle Integration — Design Spec

**Issue:** casehubio/neocortex#478
**Depends on:** #470 (sub-thought data model — done)
**Date:** 2026-10-08

## Overview

Sub-thought decomposition (#470) provides typed, entity-tagged cognitive reactions stored as Memory attributes. This spec wires sub-thoughts into the cognitive tick lifecycle as the primary intermediate representation between raw experience text and cognitive processing.

The core paradigm shift: from "every orchestrator independently interprets raw text" to "one decomposition feeds many consumers." Each consumer receives pre-structured, entity-tagged signals instead of re-deriving what it needs.

## Architecture

```
Observation text arrives at CognitionCore.tick()
    ↓
FOUNDATION phase:
    mood tick, memory hygiene
    SubThoughtTickParticipant.tick():
      1. Rule-based extraction from observation text (sync, D5)
      2. Read async-cached sub-thoughts from prior LLM enrichment (D9)
      3. Merge with async-wins precedence
      4. Push SubThoughtCue signals to MentalModelOrchestrator.record() (D7)
      5. Store in per-agent ConcurrentHashMap (accessor pattern, D1)
    ↓
SOURCE phase:
    narrative, strategy, reflection
    ↓
Subject loop:
    MentalModelOrchestrator processes SubThoughtCue signals from buffer (D3)
    → BDI updates per subject via heuristic extraction
    ↓
DERIVED phase:
    drives.tick():
      SubThoughtModulation.compute() reads from participant accessor (D2)
      → Map<DriveAxis, Double> fed to DriveComposer.compose()
    AppraisalTickParticipant (reads drives, mood — unchanged)
    GutFeelingParticipant (unchanged)
    ↓
TERMINAL phase:
    goals (unchanged)
    ↓
Prompt rendering:
    SubThoughtPromptSection reads from participant accessor

Async (outside tick):
    ExperienceRecorded → SubThoughtExtractionObserver (D6)
      → SubThoughtExtractionRequested (fireAsync)
      → SubThoughtExtractor: LLM Haiku call → enrichAttributes()
      → fires SubThoughtsEnriched CDI event
      → SubThoughtTickParticipant caches enriched sub-thoughts (D9)
```

## Module Placement

| Component | Module | Rationale |
|-----------|--------|-----------|
| SubThought record | cognition-api | Tick-time value type, consumed by cognition participants |
| SubThoughts utility | cognition-api | Query helpers (extract from Memory, merge, filter) |
| SubThoughtTickParticipant | cognition | FOUNDATION-phase participant, wired by CognitionCore |
| SubThoughtModulation | cognition | Drive modulation computation, used by DriveOrchestrator |
| SubThoughtPromptSection | cognition | Prompt renderer, follows existing prompt section pattern |
| MentalStateSignal.SubThoughtCue | cognition-api | New sealed variant in existing hierarchy |
| SubThoughtExtractionObserver | mindmap-intelligence | @Observes ExperienceRecorded, fires SubThoughtExtractionRequested |
| SubThoughtSituationDecorator | caps-engine | @Decorator on SituationClassifier |
| RuleBasedSubThoughtExtractor | cognition | Sync keyword extraction, entity name cache |
| SubThoughtsEnriched | mindmap-intelligence | CDI event fired after async enrichment |

## Component Specifications

### 1. SubThought Value Type (cognition-api)

```java
public record SubThought(
    String type,       // one of SubThoughtTypes constants
    String text,       // the decomposed text fragment
    String entity,     // nullable — entity name from MindMap
    double confidence, // [0, 1] — sync: ≤0.5 (provisional), async: LLM-assigned
    Source source      // SYNC or ASYNC — provenance
) {
    public enum Source { SYNC, ASYNC }
}
```

Companion utility class `SubThoughts`:
- `extract(Memory memory)` — reconstructs `List<SubThought>` from memory attributes (sub-thought-N-type/text/entity pattern)
- `merge(List<SubThought> sync, List<SubThought> async)` — combines with async-wins precedence. Overlap is determined by sentence-level text equality (normalized whitespace). When sync and async both produce a SubThought for the same sentence, the async version replaces the sync version
- `ofType(List<SubThought>, String type)` — filter by sub-thought type
- `forEntity(List<SubThought>, String entity)` — filter by entity name

### 2. SubThoughtTickParticipant (cognition)

FOUNDATION-phase `CognitionTickParticipant`. Registered via `CognitionCore.configureSubThoughts()`.

**Constructor parameters:**
- `RuleBasedSubThoughtExtractor` — sync extraction (D5)
- `MentalModelOrchestrator` — push target for BDI signals (D7)
- `SubjectResolver` — resolves active subjects for entity → subject mapping (D7)

**State:**
- `ConcurrentHashMap<String, SubThoughtResult>` keyed by `agentId:tenantId`
- `ConcurrentHashMap<String, List<SubThought>>` async cache, keyed by `agentId:tenantId`, TTL-expiring entries

**tick() method:**
1. If `context.observation()` is null, return early
2. Call `ruleBasedExtractor.extract(observation, agentId, tenantId)` → `List<SubThought>` (sync, confidence ≤ 0.5)
3. Read async-cached sub-thoughts for this agent/tenant (event-driven, no store I/O)
4. Merge: async wins for overlapping text spans
5. Push to mental model: for each sub-thought with entity tag, check if entity ∈ `resolver.relevantSubjects(agentId, tenantId)`. If yes, call `mentalModel.record(new SubThoughtCue(subThought), agentId, entityName, tenantId)`
6. Store merged result in per-agent map

**Accessor:** `currentSubThoughts(String agentId, String tenantId)` → `SubThoughtResult` (list of SubThought + observation text hash for staleness detection)

**Async cache population:** `@Observes SubThoughtsEnriched` event handler populates the async cache with parsed SubThought instances. Cache entries expire after configurable TTL (default 5 minutes — covers multiple ticks).

### 3. RuleBasedSubThoughtExtractor (cognition)

Fast sync extraction. `@ApplicationScoped` CDI bean — needs event observation for entity name cache refresh.

**Keyword sets** (static, per sub-thought type):
- `affect-observation`: felt, seemed, appeared, looked, sounded, happy, sad, anxious, distressed, upset, worried, cheerful, tense, relaxed, frustrated
- `causal-inference`: because, since, caused, due to, reason, therefore, so that, resulted in, led to, as a result, explains why
- `intention`: should, will, plan to, going to, need to, want to, intend, must, ought to, let's, I'll
- `self-reflection`: I feel, I think, I wonder, I notice, I realize, it occurs to me, looking back, on reflection
- `evaluative`: good, bad, excellent, terrible, impressive, disappointing, wonderful, awful, great, poor, amazing, mediocre
- `association`: reminds me, similar to, like when, just like, connects to, makes me think of, brings to mind
- `concern`: worry, concerned, afraid, fear, anxious about, troubled by, uneasy, dread, scared

**Entity name cache:**
- `ConcurrentHashMap<String, Set<String>>` keyed by tenantId
- Populated on first access by querying MindMapStore for all node names in the tenant
- Refreshed via `@Observes MindMapStoreWriteEvent` (or equivalent write-tracking mechanism)
- Entity matching: case-insensitive word-boundary matching in observation text

**extract() method:**
1. Tokenize observation text into sentences (split on `.!?`)
2. For each sentence, check keyword sets — assign sub-thought type by highest keyword match count (ties: first match wins)
3. For each typed sentence, scan for cached entity names
4. Produce `SubThought(type, sentence, entity, 0.5, SYNC)` for each match
5. Sentences with no keyword matches produce no SubThought — not everything is a cognitive reaction. The returned list contains only matched sentences

### 4. MentalStateSignal.SubThoughtCue (cognition-api)

New variant in the `MentalStateSignal` sealed hierarchy:

```java
public sealed interface MentalStateSignal {
    // existing variants...
    record SubThoughtCue(
        String subThoughtType,  // SubThoughtTypes constant
        String text,
        String entity,
        double confidence
    ) implements MentalStateSignal {}
}
```

**MentalModelOrchestrator heuristic extraction** (D3):

New method `extractSubThoughtHeuristic(SubjectMentalState state, SubThoughtCue cue)`:
- affect-observation, evaluative → `upsertBelief(entity + " state: " + text, confidence 0.6)`
- concern, association → `upsertDesire(text, confidence 0.6)`
- intention → `upsertIntention(text, confidence 0.7)`
- causal-inference, self-reflection → `upsertBelief(text, confidence 0.5)`

Confidence values are lower than VerbalCue heuristics (0.8) because sync sub-thought extraction is less reliable than direct verbal cues.

### 5. SubThoughtModulation (cognition)

Static utility following the NarrativeModulation pattern.

```java
public final class SubThoughtModulation {
    public static Map<DriveAxis, Double> compute(SubThoughtResult subThoughts) {
        // count sub-thought types in the result
        // map to drive axis modulations per D2 mapping table
    }
}
```

**Type → axis mapping:**
- concern count + negative-valence affect-observation count → `AFFILIATION` intensity
- intention count + evaluative count → `COMPETENCE` intensity
- association count + causal-inference count → `CURIOSITY` intensity
- intention count + self-reflection count → `AUTONOMY` intensity

Intensity = `min(1.0, typeCount * 0.15)` — each matching sub-thought adds 0.15 to the axis, capped at 1.0.

**Integration:** DriveOrchestrator constructor gains `@Nullable SubThoughtTickParticipant` parameter. `DriveOrchestrator.tick()` reads `participant.currentSubThoughts(agentId, tenantId)`, calls `SubThoughtModulation.compute()`, passes result to `DriveComposer.compose()` as a new `@Nullable Map<DriveAxis, Double> subThoughtModulation` parameter. Null check: if participant is null or no sub-thoughts, modulation is skipped.

### 6. SubThoughtPromptSection (cognition)

Renders recent sub-thoughts grouped by entity in the cognitive prompt.

**Format:**
```
## Recent Cognitive Reactions

About Sarah:
- She seemed distracted (affect-observation)
- The promotion situation is weighing on her (causal-inference)

About the restaurant:
- The pasta was excellent (evaluative)

General:
- I should bring David here next time (intention)
- This reminds me of dinner with Tom (association)
```

Reads from `SubThoughtTickParticipant.currentSubThoughts()`. Renders at most N sub-thoughts (configurable, default 10) sorted by confidence descending. Groups by entity (null entity → "General").

### 7. SubThoughtExtractionObserver (mindmap-intelligence)

```java
@ApplicationScoped
public class SubThoughtExtractionObserver {
    @Inject Event<SubThoughtExtractionRequested> extractionEvent;

    void onExperienceRecorded(@Observes ExperienceRecorded event) {
        extractionEvent.fireAsync(new SubThoughtExtractionRequested(
            event.memoryId(),
            event.event().tenantId(),
            event.event().text(),
            event.event().agentId()
        ));
    }
}
```

Universal trigger — every `ExperienceRecorded` event fires async sub-thought extraction (D6).

### 8. SubThoughtExtractor LLM Implementation (mindmap-intelligence)

The existing `SubThoughtExtractor.onExtractionRequested()` stub is implemented:

1. Build prompt: system message describing the 7 sub-thought types + entity identification instructions
2. Call AgentProvider (Haiku) with the experience text
3. Parse JSON response into `List<ParsedSubThought>`
4. Call existing `applySubThoughts(memoryId, parsedSubThoughts, tenantId)` to write attributes
5. Fire `SubThoughtsEnriched` CDI event with parsed sub-thoughts + agentId + tenantId for tick participant cache population

**Graceful degradation:** If AgentProvider is unavailable (CDI `Instance<AgentProvider>`), log and return — async enrichment is best-effort.

### 9. SubThoughtsEnriched CDI Event (mindmap-intelligence)

```java
public record SubThoughtsEnriched(
    String memoryId,
    String agentId,
    String tenantId,
    List<ParsedSubThought> subThoughts
) {}
```

Fired by `SubThoughtExtractor` after `applySubThoughts()`. Observed by `SubThoughtTickParticipant` for async cache population (D9).

### 10. SubThoughtSituationDecorator (caps-engine)

`@Decorator @Priority(70)` on `SituationClassifier`.

```java
@Decorator @Priority(70)
public class SubThoughtSituationDecorator implements SituationClassifier {
    @Inject @Delegate SituationClassifier delegate;

    @Override
    public List<SituationActivation> classify(String description, Map<String, String> metadata) {
        List<SituationActivation> base = delegate.classify(description, metadata);
        List<SituationActivation> subThoughtActivations = mapSubThoughts(metadata);
        return merge(base, subThoughtActivations);
    }
}
```

**Metadata → CAPS mapping:**
- `sub-thought-type=affect-observation` → perceived-emotional-state input nodes (confidence 0.5)
- `sub-thought-type=causal-inference` → explanatory-attribution input nodes (confidence 0.4)
- `sub-thought-type=concern` → threat-perception input nodes (confidence 0.6)
- `sub-thought-type=intention` → goal-activation input nodes (confidence 0.5)
- `sub-thought-type=self-reflection` → self-focused-attention input nodes (confidence 0.4)

Merging: for duplicate node IDs, take max confidence. Sub-thought activations are additive — they never reduce base classifier activations.

**BehavioralSynthesisPhase extension:** `nodeMetadata()` is extended to include sub-thought attributes from graduated MindMap node properties. When a consolidated node carries sub-thought provenance (via SubThoughtConsolidationPhase from #470), those attributes appear in the metadata map passed to classify().

### 11. CognitionCore Wiring

`CognitionCore` gains:
- `SubThoughtTickParticipant subThoughtParticipant` field
- `configureSubThoughts(SubThoughtTickParticipant participant)` — sets the field, registers at FOUNDATION phase via `addParticipant(CognitionPhase.FOUNDATION, participant)`, passes participant reference to DriveOrchestrator

**CognitionDefaultBeans** gains a `SubThoughtTickParticipant` producer:
- Constructs with `RuleBasedSubThoughtExtractor`, `Instance<MentalModelOrchestrator>`, `Instance<SubjectResolver>`, `Instance<MindMapStore>`
- Returns the participant for CognitionCore to wire

## Data Flow Summary

| Data | Source | Destination | Mechanism | Timing |
|------|--------|-------------|-----------|--------|
| Sync sub-thoughts | RuleBasedSubThoughtExtractor | SubThoughtTickParticipant state | Direct call | FOUNDATION (same tick) |
| Async sub-thoughts | SubThoughtExtractor (LLM) | SubThoughtTickParticipant cache | SubThoughtsEnriched CDI event | Between ticks |
| BDI signals | SubThoughtTickParticipant | MentalModelOrchestrator | Push via record(SubThoughtCue) | FOUNDATION → subject loop |
| Drive modulation | SubThoughtTickParticipant | DriveOrchestrator/DriveComposer | Pull via accessor | DERIVED (same tick) |
| CAPS activations | Memory attributes | SubThoughtSituationDecorator | Metadata map in classify() | Consolidation time |
| Prompt content | SubThoughtTickParticipant | SubThoughtPromptSection | Pull via accessor | After tick |

## Testing Strategy

**Unit tests:**
- `RuleBasedSubThoughtExtractor`: keyword matching accuracy per type, entity name matching, multi-sentence handling, edge cases (empty text, no matches, overlapping keywords)
- `SubThoughtModulation.compute()`: type distribution → drive axis mapping, intensity capping, empty input
- `SubThought.merge()`: async-wins precedence, non-overlapping combination
- `SubThoughtSituationDecorator`: metadata → activation mapping, merge with base classifier, missing metadata handling

**Integration tests:**
- `SubThoughtTickParticipant`: full tick flow — extraction → push to mental model → store in accessor → drive reads → prompt renders
- `SubThoughtExtractionObserver`: ExperienceRecorded → SubThoughtExtractionRequested event chain
- `MentalModelOrchestrator` with SubThoughtCue: heuristic extraction produces correct BDI updates

**Contract tests:**
- Extend existing `CognitionCore` tick tests to verify FOUNDATION-phase sub-thought availability in DERIVED phase

## Build Order

1. SubThought value type + SubThoughts utility (cognition-api)
2. MentalStateSignal.SubThoughtCue (cognition-api)
3. RuleBasedSubThoughtExtractor (cognition)
4. SubThoughtTickParticipant (cognition) — depends on 1, 3
5. CognitionCore.configureSubThoughts() wiring — depends on 4
6. SubThoughtModulation + DriveOrchestrator/DriveComposer integration — depends on 4, 5
7. MentalModelOrchestrator heuristic extraction for SubThoughtCue — depends on 2, 5
8. SubThoughtPromptSection — depends on 4
9. SubThoughtExtractionObserver (mindmap-intelligence) — depends on 1
10. SubThoughtExtractor LLM implementation + SubThoughtsEnriched event — depends on 9
11. SubThoughtSituationDecorator (caps-engine) — depends on 1
12. BehavioralSynthesisPhase metadata extension — depends on 11

Steps 1-2 are API. Steps 3-8 are the tick-time integration (testable with in-memory stubs). Steps 9-10 are async enrichment. Steps 11-12 are CAPS integration. Each step is independently testable.

## Design Trade-offs

- **Two representations for sub-thought data** (D8): SubThought records in-process, attribute strings in persistence. Conversion is mechanical but adds a mapping layer. The alternative (one representation) either sacrifices type safety or breaks the memory enrichment pattern.
- **Ephemeral sync results** (D9): Sync-extracted sub-thoughts exist only for the current tick. If an observation triggers a tick but is never recorded as an experience, its sub-thoughts are never persisted. Acceptable because non-recorded observations are inherently ephemeral.
- **Keyword matching quality** (D5): Sync extraction has lower precision than LLM extraction. Mitigated by confidence cap (0.5), async overwrite, and downstream consumers weighting by confidence.

## References

- cognition/CognitionCore.java — tick lifecycle, phase ordering, participant registration
- cognition-api/CognitionTickParticipant.java — SPI for tick phase participants
- cognition/appraisal/AppraisalTickParticipant.java — DERIVED-phase participant reference pattern (accessor + push)
- cognition/drive/DriveOrchestrator.java — NarrativeModulation integration pattern, DriveComposer.compose()
- cognition/drive/NarrativeModulation.java — modulation computation pattern
- cognition/mental/MentalModelOrchestrator.java — record() push API, extractHeuristic(), MentalStateSignal dispatch
- cognition-api/MentalStateSignal.java — sealed hierarchy with VerbalCue
- caps-api/SituationClassifier.java — classify() SPI with metadata parameter
- caps-engine/RuleBasedSituationClassifier.java — keyword matching pattern
- caps-engine/BehavioralSynthesisPhase.java — nodeMetadata(), sole classify() call site
- memory-api/experience/SubThoughtTypes.java — 7 type constants
- memory-api/experience/SubThoughtAttributeKeys.java — attribute key generators
- mindmap-intelligence/SubThoughtExtractor.java — existing stub + applySubThoughts()
- mindmap-intelligence/SubThoughtExtractionRequested.java — CDI async event
- mindmap-intelligence/consolidation/SubThoughtConsolidationPhase.java — graduation logic
- Issue casehubio/neocortex#478 — full requirements and motivation
- Issue casehubio/neocortex#470 — sub-thought data model (prerequisite, done)

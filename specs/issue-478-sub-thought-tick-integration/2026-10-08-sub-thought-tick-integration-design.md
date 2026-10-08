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
| SubThoughtResult record | cognition-api | Accessor return type consumed by modulation and prompt rendering |
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

**Persistence keys:** `SubThoughtAttributeKeys` gains `confidence(int index)` → `"sub-thought-N-confidence"`. `ParsedSubThought` gains a `double confidence` field (LLM-assigned). `SubThoughtExtractor.applySubThoughts()` is extended to persist confidence alongside type/text/entity. No `source` key needed — persisted sub-thoughts are always ASYNC by definition; `SubThoughts.extract()` sets `source=ASYNC` for all reconstructed instances. Backward compatibility: missing confidence attributes default to 0.8.

**SubThoughtResult** — the accessor return type consumed by drive modulation and prompt rendering:

```java
public record SubThoughtResult(
    List<SubThought> subThoughts,
    String observationHash
) {
    public static final SubThoughtResult EMPTY = new SubThoughtResult(List.of(), "");
}
```

`observationHash` is a SHA-256 of the observation text that produced these sub-thoughts, enabling staleness detection: if the hash doesn't match the current observation, the consumer knows the sub-thoughts are from a prior tick. `EMPTY` constant avoids null checks in consumers. Module: `cognition-api` — alongside `SubThought`, since both `SubThoughtModulation` (cognition) and `SubThoughtPromptSection` (cognition) consume it.

Companion utility class `SubThoughts`:
- `extract(Memory memory)` — reconstructs `List<SubThought>` from memory attributes (sub-thought-N-type/text/entity/confidence pattern). Reads confidence from attribute, defaulting to 0.8 for pre-confidence data. Sets `source=ASYNC` for all persisted items
- `merge(List<SubThought> sync, List<SubThought> async)` — combines sync-extracted sub-thoughts (current observation) with async-cached sub-thoughts (LLM enrichment of recent prior observations). In the common case, sync and async operate on different observation texts, making the merge a concatenation that carries recent enriched context forward alongside the current tick's decomposition. When the same observation triggers a tick before its async enrichment completes, sentence-level text equality (normalized whitespace) detects overlap, and the async version replaces the sync version — a correctness mechanism rather than the primary behavior
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
4. Merge: concatenate sync + async, with async-wins for overlapping text spans
5. Push to mental model: for each sub-thought with entity tag, check if entity ∈ `resolver.relevantSubjects(agentId, tenantId)`. If yes, call `mentalModel.record(new SubThoughtCue(subThought.type(), subThought.text(), subThought.entity(), subThought.confidence()), agentId, entityName, tenantId)`
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
- `ConcurrentHashMap<String, CacheEntry>` keyed by tenantId, where `CacheEntry(Set<String> names, Instant loadedAt)`
- Populated on first access by querying `MindMapStore.search()` for all node names in the tenant
- TTL-based expiry: entries older than configurable TTL (default 2 minutes) are refreshed on next access. Staleness of a few minutes is acceptable — sync extraction is inherently approximate (confidence ≤ 0.5) and async LLM extraction is the authoritative path
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
        String content,         // satisfies MentalStateSignal.content() contract
        String entity,
        double confidence
    ) implements MentalStateSignal {}
}
```

**MentalModelOrchestrator dispatch** (D3):

`record()` gains a new `instanceof` branch:

```java
if (signal instanceof MentalStateSignal.VerbalCue vc) {
    extractHeuristic(state, vc);
} else if (signal instanceof MentalStateSignal.SubThoughtCue stc) {
    extractSubThoughtHeuristic(state, stc);
}
state.appendSignal(signal.content());
```

New method `extractSubThoughtHeuristic(SubjectMentalState state, SubThoughtCue cue)`:

```java
private void extractSubThoughtHeuristic(SubjectMentalState state, SubThoughtCue cue) {
    var now = clock.instant();
    var key = normalizeKey(cue.content());
    switch (cue.subThoughtType()) {
        case SubThoughtTypes.AFFECT_OBSERVATION, SubThoughtTypes.EVALUATIVE ->
            upsertBelief(state, key, cue.content(), 0.6);
        case SubThoughtTypes.CONCERN, SubThoughtTypes.ASSOCIATION ->
            upsertState(state.desires, key, cue.content(),
                        0.6, BdiDimension.DESIRE, now);
        case SubThoughtTypes.INTENTION ->
            upsertState(state.intentions, key, cue.content(),
                        0.7, BdiDimension.INTENTION, now);
        case SubThoughtTypes.CAUSAL_INFERENCE, SubThoughtTypes.SELF_REFLECTION ->
            upsertBelief(state, key, cue.content(), 0.5);
    }
}
```

Confidence values are lower than VerbalCue heuristics (0.8) because sync sub-thought extraction is less reliable than direct verbal cues. Key derivation uses the existing `normalizeKey()` to produce stable slugs.

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
- concern count + affect-observation count → `AFFILIATION` intensity
- intention count + evaluative count → `COMPETENCE` intensity
- association count + causal-inference count → `CURIOSITY` intensity
- intention count + self-reflection count → `AUTONOMY` intensity

Affect-observations (both positive and negative) contribute to affiliation because noticing emotional states in others — regardless of valence — signals social attention and engagement. The `concern` type already captures the specifically negative worry/anxiety signal. No valence field is needed on `SubThought` for this mapping.

Intensity = `min(1.0, typeCount * 0.15)` — each matching sub-thought adds 0.15 to the axis, capped at 1.0.

**Integration:** DriveOrchestrator gains `void setSubThoughtParticipant(@Nullable SubThoughtTickParticipant p)` — a late-binding setter matching the `CognitionCore.setAppraisalParticipant()` precedent. Called from `CognitionCore.configureSubThoughts()` after participant construction. `DriveOrchestrator.tick()` reads `participant.currentSubThoughts(agentId, tenantId)`, calls `SubThoughtModulation.compute()`, passes result to `DriveComposer.compose()`. Null check: if participant is null or no sub-thoughts, modulation is skipped.

**DriveComposer parameter consolidation:** Introduce `ModulationLayer` to replace individual nullable modulation maps:

```java
public record ModulationLayer(Map<DriveAxis, Double> modulation, double strength, String source) {}
```

`DriveComposer.compose()` signature changes from separate `@Nullable Map<DriveAxis, Double> narrativeModulation` and `@Nullable Map<DriveAxis, Double> subThoughtModulation` to a single `List<ModulationLayer> modulations` parameter. Application logic iterates the list:

```java
for (var layer : modulations) {
    intensity += layer.modulation().getOrDefault(axis, 0.0) * layer.strength();
}
```

Existing callers: `narrativeModulation` becomes `new ModulationLayer(narrativeMod, config.narrativeModulationStrength(), "narrative")`. Sub-thought modulation becomes `new ModulationLayer(subThoughtMod, config.subThoughtModulationStrength(), "sub-thought")`. `DriveConfig` gains `subThoughtModulationStrength()` (default 0.6).

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

    private final ConcurrentHashMap<String, Instant> lastExtraction = new ConcurrentHashMap<>();
    private static final Duration COOLDOWN = Duration.ofSeconds(5);

    void onExperienceRecorded(@Observes ExperienceRecorded event) {
        if (!(event.event() instanceof Observation)
                && !(event.event() instanceof FormativeExperience)) {
            return;
        }

        var key = event.event().agentId() + ":" + event.event().tenantId();
        var now = Instant.now();
        var last = lastExtraction.get(key);
        if (last != null && Duration.between(last, now).compareTo(COOLDOWN) < 0) {
            return;
        }
        lastExtraction.put(key, now);

        extractionEvent.fireAsync(new SubThoughtExtractionRequested(
            event.memoryId(),
            event.event().tenantId(),
            event.event().description(),
            PrincipalId.agent(event.event().agentId())
        ));
    }
}
```

**Event type filtering:** Only `Observation` and `FormativeExperience` events trigger extraction. `Action` and `Outcome` events carry structured data (capability, result, target-agent) that doesn't benefit from LLM decomposition — their cognitive significance is already captured by `ActionAppraisalObserver`.

**Rate limiting:** Per-agent cooldown (default 5 seconds, configurable) prevents LLM API saturation during high-frequency interaction bursts. The `fireAsync` dispatch provides natural backpressure via the CDI managed executor pool.

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

**Metadata → CAPS mapping** (key: `cognitiveKind`, matching the property stored by `SubThoughtConsolidationPhase.graduateSubThought()` and extracted by `BehavioralSynthesisPhase.nodeMetadata()`):
- `cognitiveKind=affect-observation` → perceived-emotional-state input nodes (confidence 0.5)
- `cognitiveKind=causal-inference` → explanatory-attribution input nodes (confidence 0.4)
- `cognitiveKind=concern` → threat-perception input nodes (confidence 0.6)
- `cognitiveKind=intention` → goal-activation input nodes (confidence 0.5)
- `cognitiveKind=self-reflection` → self-focused-attention input nodes (confidence 0.4)

Merging: for duplicate node IDs, take max confidence. Sub-thought activations are additive — they never reduce base classifier activations.

**BehavioralSynthesisPhase extension:** `nodeMetadata()` is extended to include sub-thought attributes from graduated MindMap node properties. When a consolidated node carries sub-thought provenance (via SubThoughtConsolidationPhase from #470), those attributes appear in the metadata map passed to classify().

### 11. CognitionCore Wiring

`CognitionCore` gains:
- `SubThoughtTickParticipant subThoughtParticipant` field
- `configureSubThoughts(SubThoughtTickParticipant participant)` — sets the field, registers at FOUNDATION phase via `addParticipant(CognitionPhase.FOUNDATION, participant)`, calls `drives.setSubThoughtParticipant(participant)` to late-bind the participant reference (matching the `setAppraisalParticipant()` setter precedent)

**Prompt section wiring** in `promptSections()`:

```java
if (config.subThoughtsEnabled() && subThoughtParticipant != null) {
    sections.add(new SubThoughtPromptSection(subThoughtParticipant));
}
```

Inserted after the `MentalModelPromptSection` block and before `StrategyPromptSection`. Ordering rationale: sub-thoughts represent the agent's recent cognitive reactions to observations — they provide immediate context that strategy and goal sections should build on. The agent reads its broader state first (mood, drives, narrative, user model, mental model), then its specific reactions (sub-thoughts), then its forward-looking sections (strategy, goals).

`CognitionConfig` gains `subThoughtsEnabled()` (default `true`) for consistency with the existing per-feature enable pattern.

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

## Design Decisions

### FOUNDATION vs DERIVED phase placement

Issue #478 proposes SubThoughtTickParticipant at DERIVED phase. This spec places it at **FOUNDATION** phase. Rationale: sub-thoughts must be available BEFORE the subject loop (MentalModelOrchestrator.tick() processes buffered SubThoughtCue signals during the subject loop, between SOURCE and DERIVED phases) and BEFORE SOURCE phase orchestrators (narrative, strategy, reflection) that may benefit from sub-thought context. FOUNDATION phase runs after mood tick and memory hygiene but before everything else — the correct position for a shared intermediate representation that downstream phases consume.

### SubThoughtModulation vs DriveSource SPI

Issue #478 proposes `SubThoughtDriveSource` implementing the `DriveSource` SPI. This spec uses `SubThoughtModulation` following the `NarrativeModulation` pattern. Rationale:

- `DriveSource` is a `@FunctionalInterface` returning `DriveIntensity evaluate(agentId, tenantId)` — it produces intensity for **one axis**. DriveOrchestrator has one DriveSource per axis (CuriosityDrive, CompetenceDrive, AffiliationDrive, AutonomyDrive).
- Sub-thoughts affect **multiple axes simultaneously** from the same type distribution. Using DriveSource would require 4 separate implementations sharing state (the sub-thought list), each pretending to be independent.
- Modulation is architecturally correct: sub-thoughts don't constitute independent drive sources — they modulate existing drives based on cognitive context. A concern sub-thought doesn't generate affiliation drive from scratch; it amplifies existing affiliation drive intensity.
- The NarrativeModulation precedent demonstrates this pattern works cleanly with `DriveComposer.compose()`.

## Attention Signal Architecture

Sub-thought patterns generate attention signals via two existing extension points:

**Consolidation-time signals:** `SubThoughtConsolidationPhase` implements `ConsolidationPhase`, which declares `default List<AttentionSignal> signals() {return List.of();}`. The phase can override this to emit signals when it detects cross-memory sub-thought patterns:

| Pattern | SignalCategory | Trigger |
|---------|---------------|---------|
| Concern escalation | URGENCY_SPIKE | ≥N unresolved concern sub-thoughts about same entity |
| Contradictions | MERGE_CANDIDATE | Opposing affect-observations about same entity |
| Belief revision | BELIEF_REVISED | Affect polarity shift on entity over time window |

These signals flow through the existing pipeline: `ConsolidationScheduler` → `CognitiveAttentionAccumulator.addSignals()` → `AttentionBriefing` → `CognitionCore.tick()` attention drain.

**Tick-time signals:** Future extension — SubThoughtTickParticipant could produce `AttentionSignal` records for immediate-concern patterns detected within a single tick's sub-thought set. This would require a new signal pathway from FOUNDATION-phase participants to the attention mediator, which is out of scope for this issue.

Follow-up issues filed for the 5 consolidation expansion patterns from issue #478:
1. **Concern escalation** → URGENCY_SPIKE signals (#481)
2. **Contradictions** → MERGE_CANDIDATE signals (#482)
3. **Temporal affect trends** → AffectTrajectoryAnalyzer integration (#483)
4. **Causal chains** → graduated subgraph from linked causal-inferences (#484)
5. **Intention tracking** → GoalRecognitionPhase candidate feeding (#485)

The architecture supports these via typed sub-thought signals through `SubThoughtCue` dispatch in `MentalModelOrchestrator`, the `ConsolidationPhase.signals()` SPI for consolidation-time attention, and the per-type SubThought records enabling pattern detection across memories.

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

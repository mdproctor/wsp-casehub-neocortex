# Coping Strategies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #595 — Coping strategies: appraisal-coping-reappraisal cycle
**Issue group:** #595

**Goal:** Implement the EMA coping model as a new pipeline layer between Scherer appraisal and Gross regulation, with 16 coping strategies, personality-driven prediction, and an intra-tick reappraisal micro-loop.

**Architecture:** CopingMicroLoop sits after appraisal, before regulation. It runs appraise → select coping strategy (CAPS → predictor → LLM) → reinterpret narrative → keyword SEC re-evaluate → converge or iterate. Coping subsumes intrapersonal regulation strategy selection — coping decides WHAT, regulation executes HOW. CopingState carries the narrative as the mutable causal interpretation.

**Tech Stack:** Java 26, Quarkus, CDI, LLM inference via existing InferenceClient

## Global Constraints

- All new coping types go in package `io.casehub.neocortex.cognition.coping` (cognition-api for API types, cognition for implementations)
- CopingDefaults goes in `io.casehub.neocortex.cognitive.index` (cognitive-index module, alongside RegulationDefaults)
- Follow existing record patterns — immutable records with wither methods (`withX()`)
- Tests use `@QuarkusTest` for CDI integration, plain JUnit for component/unit tests
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f <module>/pom.xml test -Pfast -s .mvn/slot-settings.xml`
- Commit format: `feat(#595): <description>` or `test(#595): <description>`

---

## Batch 1: API Foundation

### Task 1: CopingStrategy enum and effect types

**Files:**
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/coping/CopingStrategy.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/coping/GoalOperation.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/coping/GoalOperationType.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/coping/DriveModulation.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/coping/AttentionDirective.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/coping/AttentionDirectiveType.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/coping/CopingStrategyAttempt.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/coping/CopingPrediction.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/coping/CopingCategory.java`
- Test: `cognition-api/src/test/java/io/casehub/neocortex/cognition/coping/CopingStrategyTest.java`

**Interfaces:**
- Produces: `CopingStrategy` enum (16 values), `CopingCategory` enum (ATTENTION, BELIEF, DESIRE, INTENTION), `GoalOperation`, `DriveModulation`, `AttentionDirective`, `CopingStrategyAttempt`, `CopingPrediction` records — used by all subsequent tasks

- [ ] **Step 1: Write the failing test**

Test that the CopingStrategy enum has 16 values, each has a category, and each maps to either a regulation strategy or direct effect:

```java
package io.casehub.neocortex.cognition.coping;

import io.casehub.neocortex.cognition.regulation.EmotionRegulationStrategy;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CopingStrategyTest {

    @Test
    void shouldHave16Strategies() {
        assertEquals(16, CopingStrategy.values().length);
    }

    @Test
    void eachStrategyShouldHaveCategory() {
        for (CopingStrategy s : CopingStrategy.values()) {
            assertNotNull(s.category(), "Missing category for " + s);
        }
    }

    @Test
    void regulationRoutedStrategiesShouldMapToRegulationStrategy() {
        assertSame(EmotionRegulationStrategy.COGNITIVE_CHANGE,
            CopingStrategy.POSITIVE_REINTERPRETATION.regulationStrategy().orElseThrow());
        assertSame(EmotionRegulationStrategy.SITUATION_SELECTION,
            CopingStrategy.AVOIDANCE.regulationStrategy().orElseThrow());
        assertSame(EmotionRegulationStrategy.SOCIAL_SUPPORT_SEEKING,
            CopingStrategy.SEEK_INSTRUMENTAL_SUPPORT.regulationStrategy().orElseThrow());
    }

    @Test
    void directEffectStrategiesShouldNotMapToRegulation() {
        assertTrue(CopingStrategy.PLANNING.regulationStrategy().isEmpty());
        assertTrue(CopingStrategy.DENIAL.regulationStrategy().isEmpty());
        assertTrue(CopingStrategy.RESIGNATION.regulationStrategy().isEmpty());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognition-api/pom.xml test -Dtest=CopingStrategyTest -s .mvn/slot-settings.xml`
Expected: FAIL — class not found

- [ ] **Step 3: Implement CopingStrategy enum and all effect types**

Create the `CopingCategory` enum:

```java
package io.casehub.neocortex.cognition.coping;

public enum CopingCategory {
    ATTENTION, BELIEF, DESIRE, INTENTION
}
```

Create the `CopingStrategy` enum with 16 values, categories, and regulation mappings per the spec §EMA Coping Strategy Taxonomy and §Strategy-to-Regulation Execution Mapping:

```java
package io.casehub.neocortex.cognition.coping;

import io.casehub.neocortex.cognition.regulation.EmotionRegulationStrategy;
import java.util.Optional;

public enum CopingStrategy {
    SEEK_INFORMATION(CopingCategory.ATTENTION, null),
    SUPPRESS_INFORMATION(CopingCategory.ATTENTION, null),
    SHIFT_RESPONSIBILITY(CopingCategory.BELIEF, null),
    WISHFUL_THINKING(CopingCategory.BELIEF, null),
    DENIAL(CopingCategory.BELIEF, null),
    MENTAL_DISENGAGEMENT(CopingCategory.DESIRE, EmotionRegulationStrategy.ATTENTIONAL_DEPLOYMENT),
    POSITIVE_REINTERPRETATION(CopingCategory.DESIRE, EmotionRegulationStrategy.COGNITIVE_CHANGE),
    ACCEPTANCE(CopingCategory.DESIRE, null),
    PLANNING(CopingCategory.INTENTION, null),
    SEEK_INSTRUMENTAL_SUPPORT(CopingCategory.INTENTION, EmotionRegulationStrategy.SOCIAL_SUPPORT_SEEKING),
    SEEK_EMOTIONAL_SUPPORT(CopingCategory.INTENTION, EmotionRegulationStrategy.SOCIAL_SHARING),
    ACTIVE_CONFRONTATION(CopingCategory.INTENTION, EmotionRegulationStrategy.SITUATION_MODIFICATION),
    SUPPRESSION(CopingCategory.INTENTION, EmotionRegulationStrategy.RESPONSE_MODULATION),
    PROCRASTINATION(CopingCategory.INTENTION, null),
    RESIGNATION(CopingCategory.INTENTION, null),
    AVOIDANCE(CopingCategory.INTENTION, EmotionRegulationStrategy.SITUATION_SELECTION);

    private final CopingCategory category;
    private final EmotionRegulationStrategy regulationTarget;

    CopingStrategy(CopingCategory category, EmotionRegulationStrategy regulationTarget) {
        this.category = category;
        this.regulationTarget = regulationTarget;
    }

    public CopingCategory category() { return category; }
    public Optional<EmotionRegulationStrategy> regulationStrategy() {
        return Optional.ofNullable(regulationTarget);
    }
    public boolean isRegulationRouted() { return regulationTarget != null; }
}
```

Create the effect records per the spec §Accumulated Effect Types:

`GoalOperationType.java`: enum with `CREATE`, `DROP`, `DEFER`

`GoalOperation.java`: record with `(GoalOperationType type, String goalName, String goalDescription, DriveAxis axis, String formationReason)`

`DriveModulation.java`: record with `(DriveAxis axis, double intensityDelta, String reason)`

`AttentionDirectiveType.java`: enum with `FOCUS`, `SUPPRESS`

`AttentionDirective.java`: record with `(AttentionDirectiveType type, String target, String reason)`

`CopingStrategyAttempt.java`: record with `(CopingStrategy strategy, int iteration, String reinterpretedNarrative)`

`CopingPrediction.java`: record with `(CopingStrategy strategy, double confidence, @Nullable String familyLabel)`

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognition-api/pom.xml test -Dtest=CopingStrategyTest -s .mvn/slot-settings.xml`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/coping/ cognition-api/src/test/java/io/casehub/neocortex/cognition/coping/
git commit -m "feat(#595): CopingStrategy enum, effect types, and strategy-to-regulation mapping"
```

### Task 2: CopingState record and AppraisalResult extension

**Files:**
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/coping/CopingState.java`
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalResult.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/SchererAppraisalStrategy.java`
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitionConfig.java`
- Test: `cognition-api/src/test/java/io/casehub/neocortex/cognition/coping/CopingStateTest.java`

**Interfaces:**
- Consumes: `CopingStrategy`, `GoalOperation`, `DriveModulation`, `AttentionDirective`, `CopingStrategyAttempt` from Task 1
- Produces: `CopingState` record with wither methods; `AppraisalResult.secDimensions()`; `CognitionConfig.copingEnabled()`, `.copingOpportunityThreshold()`, `.copingMaxIterations()`

- [ ] **Step 1: Write the failing test**

Test CopingState construction, wither semantics, and accumulated effect immutability:

```java
package io.casehub.neocortex.cognition.coping;

import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class CopingStateTest {

    @Test
    void shouldCreateInitialState() {
        var state = CopingState.initial("raw situation", Map.of("CONTROLLABILITY", 0.5), List.of());
        assertEquals("raw situation", state.interpretationNarrative());
        assertEquals(0, state.iteration());
        assertTrue(state.goalOperations().isEmpty());
        assertTrue(state.strategiesAttempted().isEmpty());
    }

    @Test
    void withersShouldProduceNewInstance() {
        var state = CopingState.initial("raw", Map.of(), List.of());
        var next = state.withInterpretation("reinterpreted").withIteration(1);
        assertEquals("raw", state.interpretationNarrative());
        assertEquals("reinterpreted", next.interpretationNarrative());
        assertEquals(1, next.iteration());
    }

    @Test
    void shouldAccumulateEffects() {
        var state = CopingState.initial("raw", Map.of(), List.of());
        var goalOp = new GoalOperation(GoalOperationType.CREATE, "plan", "plan desc",
            io.casehub.neocortex.cognition.drive.DriveAxis.COMPETENCE, "coping");
        var next = state.withAccumulatedGoalOp(goalOp);
        assertEquals(1, next.goalOperations().size());
        assertTrue(state.goalOperations().isEmpty());
    }

    @Test
    void shouldDetectOscillation() {
        var state = CopingState.initial("raw", Map.of(), List.of());
        var attempt = new CopingStrategyAttempt(CopingStrategy.PLANNING, 0, "reinterpreted");
        var withAttempt = state.withStrategy(attempt);
        assertTrue(withAttempt.hasAttempted(CopingStrategy.PLANNING));
        assertFalse(withAttempt.hasAttempted(CopingStrategy.DENIAL));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognition-api/pom.xml test -Dtest=CopingStateTest -s .mvn/slot-settings.xml`
Expected: FAIL — class not found

- [ ] **Step 3: Implement CopingState**

Create `CopingState.java` per the spec §CopingState — The Micro-Loop Working State. Include:
- Static factory `initial(String narrative, Map<String, Double> secDimensions, List<CognitiveEmotion> emotions)`
- Wither methods: `withInterpretation`, `withDimensions`, `withEmotions`, `withIteration`, `withAccumulatedGoalOp`, `withAccumulatedDriveMod`, `withAccumulatedAttentionDirective`, `withStrategy`
- Query: `hasAttempted(CopingStrategy)` for oscillation detection

- [ ] **Step 4: Extend AppraisalResult**

Add `Map<String, Double> secDimensions` field to the `AppraisalResult` record. Update `SchererAppraisalStrategy.appraise()` to capture the merged dimensions from `EmotionMapper.mergeDimensions(results)` and pass them to the new field. Currently the merged map is computed but discarded after emotion mapping.

Use `ide_edit_member` to add the field to the record. Use `ide_find_references` to find all `AppraisalResult` construction sites and update them.

- [ ] **Step 5: Extend CognitionConfig**

Add three fields:
- `boolean copingEnabled` (default false)
- `double copingOpportunityThreshold` (default 0.6)
- `int copingMaxIterations` (default 3)

Update factory methods `all()`, `none()`, `withAllSubsystems()` to include the new fields. Add `withCopingEnabled()` wither.

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognition-api/pom.xml test -Pfast -s .mvn/slot-settings.xml`
Expected: PASS (all cognition-api tests)

- [ ] **Step 7: Commit**

```bash
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/coping/CopingState.java
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalResult.java
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/SchererAppraisalStrategy.java
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitionConfig.java
git add cognition-api/src/test/java/io/casehub/neocortex/cognition/coping/CopingStateTest.java
git commit -m "feat(#595): CopingState record, AppraisalResult.secDimensions, CognitionConfig coping gate"
```

---

## Batch 2: CDE Derivation and Predictor

### Task 3: CopingDefaults derivation

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CopingDefaults.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CopingDefaultsDerivationTest.java`

**Interfaces:**
- Consumes: Big Five personality facets from existing `PersonalityProfile`
- Produces: `CopingDefaults` record (planfulTendency, reinterpretationTendency, avoidanceTendency, supportSeekingTendency, acceptanceTendency); `CognitiveDefaults.copingDefaults()` accessor

- [ ] **Step 1: Write the failing test**

Test that CopingDefaults derivation produces correct personality-coping correlations:

```java
@Test
void highConscientiousnessShouldProduceHighPlanfulTendency() {
    var personality = PersonalityProfile.builder()
        .conscientiousness(0.9).neuroticism(0.2).openness(0.5)
        .agreeableness(0.5).extraversion(0.5).build();
    var defaults = derivationEngine.deriveCopingDefaults(personality);
    assertTrue(defaults.planfulTendency() > 0.7);
    assertTrue(defaults.avoidanceTendency() < 0.4);
}

@Test
void highNeuroticismShouldProduceHighAvoidanceTendency() {
    var personality = PersonalityProfile.builder()
        .conscientiousness(0.3).neuroticism(0.9).openness(0.3)
        .agreeableness(0.5).extraversion(0.3).build();
    var defaults = derivationEngine.deriveCopingDefaults(personality);
    assertTrue(defaults.avoidanceTendency() > 0.7);
    assertTrue(defaults.planfulTendency() < 0.4);
}
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement CopingDefaults record and CDE derivation**

Create `CopingDefaults.java` per the spec §CopingDefaults:
```java
public record CopingDefaults(
    double planfulTendency,
    double reinterpretationTendency,
    double avoidanceTendency,
    double supportSeekingTendency,
    double acceptanceTendency
) {}
```

Add `deriveCopingDefaults(PersonalityProfile)` method to `CognitiveDerivationEngine` using Connor-Smith & Flachsbart (2007) correlations:
- planfulTendency = conscientiousness (r=.21 scaled)
- reinterpretationTendency = openness (r=.11 scaled)
- avoidanceTendency = neuroticism (r=.25 scaled)
- supportSeekingTendency = (agreeableness + extraversion) / 2 (r=.11,.14 scaled)
- acceptanceTendency = 1.0 - neuroticism

Follow the same derivation pattern as `deriveRegulationDefaults()`.

Add `copingDefaults` field to `CognitiveDefaults` record and `withCopingDefaults()` wither. Wire into the derivation pipeline alongside `regulationDefaults`.

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CopingDefaults.java
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java
git add cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CopingDefaultsDerivationTest.java
git commit -m "feat(#595): CopingDefaults derivation from Big Five via CDE"
```

### Task 4: CopingStrategyPredictor

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/coping/CopingStrategyPredictor.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/coping/CopingStrategyPredictorTest.java`

**Interfaces:**
- Consumes: `CopingDefaults` from Task 3, `CopingStrategy`/`CopingPrediction` from Task 1, `DispositionAxes`, `CognitiveLoadLevel`
- Produces: `CopingStrategyPredictor.predict(CopingDefaults, Map<String, Double>, List<CognitiveEmotion>, DispositionAxes, CognitiveLoadLevel) → Optional<CopingPrediction>`

- [ ] **Step 1: Write the failing tests**

Test the 6-stage selection logic from spec §CopingStrategyPredictor:

```java
@Test
void highCognitiveLoadShouldFilterToLowCostStrategies() {
    var prediction = predictor.predict(balanced, dims(0.5), mild, null, CognitiveLoadLevel.HIGH);
    assertTrue(prediction.isPresent());
    var lowCost = Set.of(SUPPRESSION, AVOIDANCE, MENTAL_DISENGAGEMENT, RESIGNATION);
    assertTrue(lowCost.contains(prediction.get().strategy()));
}

@Test
void highControllabilityShouldFilterToIntentionStrategies() {
    var prediction = predictor.predict(planful, dims(0.8), moderate, null, CognitiveLoadLevel.NOMINAL);
    assertTrue(prediction.isPresent());
    assertEquals(CopingCategory.INTENTION, prediction.get().strategy().category());
}

@Test
void lowControllabilityShouldFilterToBeliefDesireStrategies() {
    var prediction = predictor.predict(avoidant, dims(0.1), moderate, null, CognitiveLoadLevel.NOMINAL);
    assertTrue(prediction.isPresent());
    var allowed = Set.of(CopingCategory.BELIEF, CopingCategory.DESIRE);
    assertTrue(allowed.contains(prediction.get().strategy().category()));
}

@Test
void selfConsciousEmotionWithAvoidantPersonalityShouldBiasAvoidance() {
    var shame = List.of(new CognitiveEmotion(EmotionType.SHAME, 0.7, ""));
    var avoidantAxes = new DispositionAxes("avoidant", "private", "cautious", "independent", "flexible");
    var prediction = predictor.predict(avoidant, dims(0.4), shame, avoidantAxes, CognitiveLoadLevel.NOMINAL);
    assertTrue(prediction.isPresent());
    assertEquals(CopingStrategy.AVOIDANCE, prediction.get().strategy());
}
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement CopingStrategyPredictor**

Implement the 6-stage selection logic per spec §CopingStrategyPredictor:
1. Cognitive load gate
2. Controllability-based filtering
3. Mild distress override
4. Self-conscious emotion refinement
5. Personality bias resolution
6. Output with confidence

Reference `RegulationStrategyPredictor.java` for the existing pattern (cognitive load gate, mild distress threshold, self-conscious handling). Migrate those capabilities, replacing emotion-category-first with controllability-first filtering.

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/coping/CopingStrategyPredictor.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/coping/CopingStrategyPredictorTest.java
git commit -m "feat(#595): CopingStrategyPredictor — controllability + personality + load selection"
```

---

## Batch 3: LLM Generation and Micro-Loop

### Task 5: CopingGenerationPhase

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/coping/CopingGenerationPhase.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/coping/CopingResult.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/coping/CopingGenerationPhaseTest.java`

**Interfaces:**
- Consumes: `CopingState` from Task 2, `CopingPrediction` from Task 1, `AppraisalContext` from existing
- Produces: `CopingGenerationPhase.generate(AppraisalContext, CopingState, @Nullable CopingStrategy pinnedStrategy) → CopingResult`; `CopingResult(CopingStrategy strategy, String reinterpretedNarrative, List<GoalOperation> goalOps, List<DriveModulation> driveMods, List<AttentionDirective> attentionDirectives)`

- [ ] **Step 1: Write the failing test**

Test that the generation phase produces a valid CopingResult with a reinterpreted narrative. Use a mock InferenceClient that returns structured JSON:

```java
@Test
void shouldProduceReinterpretedNarrativeAndStrategy() {
    var mockClient = mockInferenceClient("""
        {"strategy": "POSITIVE_REINTERPRETATION",
         "narrative": "I see this as an opportunity to grow",
         "goalOperations": [],
         "driveModulations": [],
         "attentionDirectives": []}
        """);
    var phase = new CopingGenerationPhase(mockClient);
    var result = phase.generate(context, state, CopingStrategy.POSITIVE_REINTERPRETATION);
    assertEquals(CopingStrategy.POSITIVE_REINTERPRETATION, result.strategy());
    assertNotEquals(state.interpretationNarrative(), result.reinterpretedNarrative());
}
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement CopingGenerationPhase**

Follow the `EmotionRegulationGenerationPhase` pattern:
- Build a system prompt with the character's personality, current situation, SEC dimensions, emotions, and coping context
- Include the strategy taxonomy and CopingDefaults as context
- If a pinnedStrategy is provided, instruct the LLM to use it
- Parse structured JSON response into CopingResult
- Include the prompt constraint for keyword-detectable reinterpretations (spec §Keyword coverage)

Create `CopingResult.java`:
```java
public record CopingResult(
    CopingStrategy strategy,
    String reinterpretedNarrative,
    List<GoalOperation> goalOperations,
    List<DriveModulation> driveModulations,
    List<AttentionDirective> attentionDirectives
) {}
```

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/coping/
git add cognition/src/test/java/io/casehub/neocortex/cognition/coping/CopingGenerationPhaseTest.java
git commit -m "feat(#595): CopingGenerationPhase — LLM-based coping selection and narrative reinterpretation"
```

### Task 6: CopingMicroLoop orchestrator and pre-coping safety gate

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/coping/CopingMicroLoop.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/coping/PreCopingSafetyGate.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/coping/CopingMicroLoopTest.java`

**Interfaces:**
- Consumes: `CopingState` (Task 2), `CopingStrategyPredictor` (Task 4), `CopingGenerationPhase` (Task 5), keyword SEC checks (existing), `EmotionMapper` (existing)
- Produces: `CopingMicroLoop.run(AppraisalContext, AppraisalResult, CopingDefaults, DispositionAxes, CognitiveLoadLevel, CapsEngine, CognitionConfig) → CopingState`; `PreCopingSafetyGate.shouldSkip(double fatigue, double peakIntensity) → boolean`

- [ ] **Step 1: Write the failing tests**

```java
@Test
void shouldConvergeWhenNoEmotionExceedsThreshold() {
    var result = CopingState.initial("calm situation", dims(0.5), mildEmotions);
    var copedState = microLoop.run(context, appraisalResult, defaults, null, null, null, config);
    assertEquals(0, copedState.iteration());
    assertTrue(copedState.strategiesAttempted().isEmpty());
}

@Test
void shouldIterateAndConverge() {
    // Setup: high-intensity emotion that drops after reinterpretation
    var copedState = microLoop.run(context, highStressResult, planfulDefaults, null, null, null, config);
    assertTrue(copedState.iteration() > 0);
    assertFalse(copedState.strategiesAttempted().isEmpty());
}

@Test
void shouldRespectIterationCap() {
    // Setup: emotion that never drops below threshold
    var copedState = microLoop.run(context, extremeResult, defaults, null, null, null, configWithMax2);
    assertEquals(2, copedState.iteration());
}

@Test
void shouldDetectOscillationAndStop() {
    // Setup: strategy oscillates between two choices
    var copedState = microLoop.run(context, oscillatingResult, defaults, null, null, null, config);
    assertTrue(copedState.iteration() < config.copingMaxIterations());
}

@Test
void safetyGateShouldSkipCopingUnderHighFatigue() {
    assertTrue(PreCopingSafetyGate.shouldSkip(0.8, 0.5));
    assertFalse(PreCopingSafetyGate.shouldSkip(0.3, 0.5));
}

@Test
void safetyGateShouldSkipCopingUnderHighIntensity() {
    assertTrue(PreCopingSafetyGate.shouldSkip(0.3, 0.8));
    assertFalse(PreCopingSafetyGate.shouldSkip(0.3, 0.5));
}
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement CopingMicroLoop**

Implement the micro-loop algorithm per spec §Micro-Loop Algorithm:
1. Create initial CopingState from AppraisalResult
2. While iteration < maxIterations:
   a. Identify coping opportunity (max emotion intensity > threshold)
   b. CAPS coping attractor resolution (if CapsEngine present)
   c. CopingStrategyPredictor fallback
   d. CopingGenerationPhase LLM call
   e. Apply effects via withers
   f. Oscillation detection — break if strategy already attempted
   g. Keyword SEC re-evaluation via synthetic AppraisalContext
   h. Increment iteration
3. Return converged CopingState

Implement `PreCopingSafetyGate` with thresholds from spec §Pre-Coping Safety Gate:
- fatigue > 0.7 OR peakIntensity > 0.75 → skip coping

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/coping/
git add cognition/src/test/java/io/casehub/neocortex/cognition/coping/CopingMicroLoopTest.java
git commit -m "feat(#595): CopingMicroLoop orchestrator and pre-coping safety gate"
```

---

## Batch 4: Regulation Refactoring and Goal Dispatch

### Task 7: Regulation refactoring — receive coping strategy

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationGenerationPhase.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/RegulationStrategyPredictor.java` (retire as selector)
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipant.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationCopingIntegrationTest.java`

**Interfaces:**
- Consumes: `CopingStrategy`, `CopingState` from Tasks 1-2
- Produces: Refactored `EmotionRegulationGenerationPhase.generate()` that accepts coping strategy + reinterpreted narrative; `EmotionRegulationTickParticipant` that integrates coping micro-loop when `copingEnabled`

- [ ] **Step 1: Write the failing test**

```java
@Test
void shouldAcceptCopingStrategyAndReinterpretedNarrative() {
    var result = generationPhase.generate(
        context, appraisalResult,
        CopingStrategy.POSITIVE_REINTERPRETATION,
        EmotionRegulationStrategy.COGNITIVE_CHANGE,
        "I see this as an opportunity");
    assertNotNull(result);
    assertEquals(EmotionRegulationStrategy.COGNITIVE_CHANGE, result.strategy());
}
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Refactor EmotionRegulationGenerationPhase**

Add an overloaded `generate()` method that accepts:
- `CopingStrategy copingStrategy` — the EMA strategy that was selected
- `EmotionRegulationStrategy regulationStrategy` — the mapped regulation execution target
- `String reinterpretedNarrative` — the coping-produced reinterpretation

When this overload is used, the phase does NOT select a strategy. It executes the provided strategy, assessing effectiveness, fatigue, regulated intensity, and producing the experiential narrative. For COGNITIVE_CHANGE, it receives the before/after narratives and evaluates how well the reinterpretation worked.

The existing `generate()` signature remains for backward compatibility when coping is disabled.

- [ ] **Step 4: Update EmotionRegulationTickParticipant**

When `CognitionConfig.copingEnabled()`:
1. Run pre-coping safety gate check. If triggered, pin ATTENTIONAL_DEPLOYMENT and skip coping.
2. Run CopingMicroLoop to get converged CopingState.
3. For regulation-routed strategies: call `EmotionRegulationGenerationPhase.generate()` with coping strategy + regulation target + reinterpreted narrative.
4. For direct-effect strategies: skip regulation call; dispatch effects directly.
5. Dispatch accumulated GoalOperations, DriveModulations, AttentionDirectives from CopingState.

When `!copingEnabled`: existing regulation flow unchanged (backward compat).

Relocate the safety hard gate FROM the regulation cascade (Layer 1) TO the pre-coping gate. When coping is disabled, the safety gate continues to function in its original location.

- [ ] **Step 5: Retire RegulationStrategyPredictor as selector**

When `copingEnabled`, `RegulationStrategyPredictor` is not called for strategy SELECTION. Its intelligence (cognitive load gate, mild distress override, self-conscious emotion handling) has been migrated to `CopingStrategyPredictor` in Task 4. Mark with `@Deprecated` and a comment noting it is retained for backward compat when coping is disabled.

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognition/pom.xml test -Pfast -s .mvn/slot-settings.xml`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/regulation/
git add cognition/src/test/java/io/casehub/neocortex/cognition/regulation/
git commit -m "feat(#595): regulation refactoring — receive coping strategy, relocate safety gate"
```

### Task 8: Goal operations dispatch and CopingCheck keyword expansion

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/goal/GoalProposalOrchestrator.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/CopingCheck.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/goal/GoalOperationsDispatchTest.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/CopingCheckKeywordExpansionTest.java`

**Interfaces:**
- Consumes: `GoalOperation`, `GoalOperationType` from Task 1
- Produces: `GoalProposalOrchestrator.requestAbandonment(agentId, tenantId, goalName, reason)`; `GoalProposalOrchestrator.requestDemotion(agentId, tenantId, goalName, priority, reason)`; expanded CopingCheck keyword sets (30-50 words)

- [ ] **Step 1: Write failing tests for goal operations**

```java
@Test
void requestAbandonmentShouldAddToAbandonmentList() {
    orchestrator.requestAbandonment(agentId, tenantId, "stuck-goal", "resignation: uncontrollable");
    assertTrue(orchestrator.getPendingAbandonments(agentId, tenantId).contains("stuck-goal"));
}

@Test
void requestDemotionShouldAdjustPriority() {
    orchestrator.requestDemotion(agentId, tenantId, "deferred-goal",
        GoalPriority.SECONDARY, "procrastination: deferred");
    // Verify goal priority adjusted
}
```

- [ ] **Step 2: Write failing tests for keyword expansion**

```java
@Test
void expandedKeywordsShouldDetectRicherVocabulary() {
    var context = contextWith("I realize I have alternatives and can influence the outcome");
    var result = copingCheck.evaluate(context);
    var controllability = result.dimensions().get("CONTROLLABILITY");
    assertTrue(controllability > 0.5, "Should detect 'alternatives' and 'influence' as agency words");
}

@Test
void expandedKeywordsShouldDetectRicherHelplessness() {
    var context = contextWith("I feel cornered and futile, completely powerless");
    var result = copingCheck.evaluate(context);
    var controllability = result.dimensions().get("CONTROLLABILITY");
    assertTrue(controllability < 0.3, "Should detect 'cornered', 'futile', 'powerless'");
}
```

- [ ] **Step 3: Implement goal operations dispatch**

Add `requestAbandonment(String agentId, String tenantId, String goalName, String reason)` to `GoalProposalOrchestrator`. Follows the existing abandonment pattern (`evaluateRelevance`) but triggered by coping decision.

Add `requestDemotion(String agentId, String tenantId, String goalName, GoalPriority priority, String reason)`. Follows the existing `PriorityAdjustment` pattern.

- [ ] **Step 4: Expand CopingCheck keyword sets**

Expand agency keywords from 7 to ~40: add "alternatives", "opportunity", "manage", "influence", "path", "empowered", "options", "choose", "decide", "resolve", "tackle", "address", "overcome", "handle", "cope", "adapt", "adjust", "navigate", "direct", "shape", "steer", "guide", "master", "command", "achieve", "accomplish", "progress", "advance", "improve", "change", "transform", "create", "build", "develop", "grow", "learn", "try", "attempt", "effort".

Expand helplessness keywords from 7 to ~40: add "powerless", "hopeless", "cornered", "confined", "futile", "overwhelming", "inescapable", "uncontrollable", "devastating", "crushing", "suffocating", "drowning", "paralyzed", "frozen", "numb", "defeated", "doomed", "cursed", "abandoned", "forsaken", "vulnerable", "exposed", "defenseless", "weak", "frail", "broken", "shattered", "lost", "aimless", "directionless", "worthless", "useless", "inadequate", "incompetent".

- [ ] **Step 5: Run tests to verify they pass**

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/goal/GoalProposalOrchestrator.java
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/CopingCheck.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/goal/
git add cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/CopingCheckKeywordExpansionTest.java
git commit -m "feat(#595): goal operations dispatch + CopingCheck keyword expansion"
```

---

## Batch 5: CAPS Integration and Pipeline Wiring

### Task 9: CAPS coping attractors and full pipeline wiring

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipant.java`
- Modify: CAPS attractor configuration (create "coping" category, seed from CopingDefaults)
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/coping/CopingPipelineIntegrationTest.java`

**Interfaces:**
- Consumes: All coping types from Tasks 1-8; existing CapsEngine, WeightUpdateContext
- Produces: End-to-end pipeline: appraise → safety gate → coping micro-loop → regulation execution → CAPS update → drive modulation → goal dispatch

- [ ] **Step 1: Write the integration test**

```java
@QuarkusTest
class CopingPipelineIntegrationTest {

    @Test
    void fullPipelineWithCopingEnabled() {
        // Setup character with high conscientiousness, enable coping
        // Trigger a controllable stressor
        // Verify: CopingMicroLoop runs, selects PLANNING, dispatches goal operation
        // Verify: regulation executes COGNITIVE_CHANGE (if mapped) or no regulation (if direct)
        // Verify: drive modulation applied
    }

    @Test
    void copingDisabledShouldUseExistingRegulationPath() {
        // Verify backward compatibility when copingEnabled = false
    }

    @Test
    void safetyGateShouldBypassCopingAndPinAttentionalDeployment() {
        // High fatigue → skip coping → pin ATTENTIONAL_DEPLOYMENT
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Wire CAPS coping attractors**

Add "coping" attractor category alongside existing "regulation" category. Seed initial weights from CopingDefaults. Wire CAPS weight update after regulation execution to update the coping strategy's attractor node using the existing Rescorla-Wagner mechanism.

When coping is enabled, retire the "regulation" attractor category from CAPS settling in favor of "coping" attractors.

- [ ] **Step 4: Complete pipeline wiring in EmotionRegulationTickParticipant**

Ensure the full pipeline flow from spec §Pipeline Position is wired:
1. Appraise → AppraisalResult with secDimensions
2. Pre-coping safety gate
3. CopingMicroLoop (if passed gate)
4. Route: regulation-routed → EmotionRegulationGenerationPhase; direct → dispatch effects
5. CAPS weight update with coping strategy
6. AppraisalDriveModulator with coping DriveModulations
7. Goal lifecycle with coping GoalOperations

- [ ] **Step 5: Run integration tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognition/pom.xml test -Pfast -s .mvn/slot-settings.xml`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/
git add cognition/src/test/java/io/casehub/neocortex/cognition/coping/CopingPipelineIntegrationTest.java
git commit -m "feat(#595): CAPS coping attractors and full pipeline wiring"
```

---

## Batch 6: Emergence Eval

### Task 10: Personality differentiation and strategy chaining eval tests

**Files:**
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/coping/CopingEmergenceEvalTest.java`

**Interfaces:**
- Consumes: Full coping pipeline from Tasks 1-9

- [ ] **Step 1: Write eval tests**

```java
@Tag("llm-eval")
@QuarkusTest
class CopingEmergenceEvalTest {

    @Test
    void highConscientiousnessCharacterShouldPlanInControllableSituation() {
        // High-C personality, controllable stressor
        // Expect: PLANNING selected, plan goal created
    }

    @Test
    void highNeuroticismCharacterShouldAvoidInThreateningSituation() {
        // High-N personality, uncontrollable threat
        // Expect: AVOIDANCE or DENIAL or WISHFUL_THINKING
    }

    @Test
    void strategyChainingWhenPlanningFailsDueToLowControllability() {
        // Start with PLANNING, reinterpretation reveals uncontrollability
        // Expect: iteration 2 shifts to ACCEPTANCE or RESIGNATION
    }

    @Test
    void reinterpretationShouldProduceCoherentNarrative() {
        // POSITIVE_REINTERPRETATION should transform narrative meaningfully
        // Judge: reinterpreted narrative should be semantically distinct from original
    }

    @Test
    void convergenceShouldReduceEmotionalIntensity() {
        // After micro-loop, working emotions should have lower intensity
        // than initial emotions (at least for the target emotion)
    }
}
```

- [ ] **Step 2: Run eval tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognition/pom.xml test -Pllm-eval -Dtest=CopingEmergenceEvalTest -s .mvn/slot-settings.xml`
Expected: Majority pass (eval tests are non-deterministic)

- [ ] **Step 3: Commit**

```bash
git add cognition/src/test/java/io/casehub/neocortex/cognition/coping/CopingEmergenceEvalTest.java
git commit -m "test(#595): coping emergence eval — personality differentiation and strategy chaining"
```

---

## References

- [2026-11-15-coping-strategies-design.md] — design spec this plan implements
- [decisions.md] — 9 design decisions with rationale
- [D4-exploration.md] — narrative as causal interpretation analysis
- [D6-exploration.md] — hybrid personality-coping mapping analysis
- cognition-api/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationStrategy.java — regulation enum (execution targets)
- cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalResult.java — extend with secDimensions
- cognition/src/main/java/io/casehub/neocortex/cognition/regulation/RegulationStrategyPredictor.java — pattern + retire
- cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationGenerationPhase.java — refactor
- cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipant.java — pipeline integration
- cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/RegulationDefaults.java — CopingDefaults pattern
- cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java — CDE derivation
- cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/CopingCheck.java — keyword expansion
- cognition/src/main/java/io/casehub/neocortex/cognition/goal/GoalProposalOrchestrator.java — goal dispatch
- GitHub #595 — focal issue

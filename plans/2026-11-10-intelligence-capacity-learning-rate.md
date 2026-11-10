# Intelligence Capacity Learning Rate Modulation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #890 — Intelligence capacity: learning rate modulation via Cattell's Investment Theory
**Issue group:** #841 (cognitive exploration epic)

**Goal:** Wire CognitiveCapacityConfig dimensions (relationalComplexity, associativeReach, workingMemorySpan) as linear multipliers on 6 learning/adaptation sites, so agents with higher cognitive capacity learn faster per Cattell's Investment Theory.

**Architecture:** Linear multiplier `effectiveLR = baseLR * capacityDimension` at each site, with ceiling pattern for two sites whose existing parameter is already a ceiling. Each site maps to one of three capacity dimensions based on cognitive substrate relevance (Halford/Mednick/Engle & Kane). Uses trait-level capacity from CognitiveDefaults, not dynamic depletion.

**Tech Stack:** Java 21, Quarkus CDI, CAPS engine, CBR record store SPI

## Global Constraints

- Java 21 (on Java 26 JVM), Quarkus 3.32.2
- Every modulation site gets Javadoc citing Cattell (1971) + the specific dimension's literature source
- Capacity values in [0.55, 0.95] from CDE compression; `*OrDefault()` returns 1.0 when null
- Pre-release: API breaks acceptable, no backwards-compatibility shims
- Every commit references #890

---

## Batch 1: CAPS Foundation — WeightUpdateContext + alpha modulation

### Task 1: WeightUpdateContext record + CapsEngine SPI migration

**Files:**
- Create: `caps-api/src/main/java/io/casehub/neocortex/caps/WeightUpdateContext.java`
- Modify: `caps-api/src/main/java/io/casehub/neocortex/caps/CapsEngine.java` — change `updateWeights()` signature
- Modify: `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsWeightUpdater.java` — accept context, apply capacityMultiplier to baseAlpha
- Modify: `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/SqliteCapsEngine.java` — adapt to new signature
- Modify: `caps-testing/src/main/java/io/casehub/neocortex/caps/testing/InMemoryCapsEngine.java` — adapt to new signature
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/InMemoryCapsEngine.java` — adapt to new signature (if separate copy exists)
- Modify: `mindmap-intelligence/src/test/java/.../BehavioralSynthesisPhaseTest.java` — adapt StubCapsEngine, CapturingCapsEngine, EmotionAwareStubCapsEngine
- Test: `caps-engine/src/test/java/io/casehub/neocortex/caps/engine/CapsWeightUpdaterTest.java`

**Interfaces:**
- Produces: `WeightUpdateContext(Map<String, Double> inputActivations, double outcomeIntensity, double outcomeValence, double salienceMultiplier, String reinforcementSchedule, double capacityMultiplier)` — used by Task 2 and all CapsEngine consumers
- Produces: `CapsEngine.updateWeights(AgentCapsState state, WeightUpdateContext context)` — new SPI signature

- [ ] **Step 1: Create WeightUpdateContext record**

```java
package io.casehub.neocortex.caps;

import java.util.Map;
import java.util.Objects;

/**
 * Context for CAPS weight updates. Capacity multiplier implements Cattell's (1971)
 * Investment Theory: associativeReach (Mednick 1962) modulates the Rescorla-Wagner
 * (1972) base alpha — higher associative capacity strengthens stimulus-response
 * learning speed.
 *
 * @param capacityMultiplier from {@link io.casehub.neocortex.cognitive.CognitiveCapacityConfig#associativeReachOrDefault()};
 *                           1.0 means uncapped (default when capacity is null)
 */
public record WeightUpdateContext(
        Map<String, Double> inputActivations,
        double outcomeIntensity,
        double outcomeValence,
        double salienceMultiplier,
        String reinforcementSchedule,
        double capacityMultiplier
) {
    public WeightUpdateContext {
        Objects.requireNonNull(inputActivations);
        Objects.requireNonNull(reinforcementSchedule);
        if (capacityMultiplier < 0.0 || capacityMultiplier > 1.0) {
            throw new IllegalArgumentException("capacityMultiplier must be in [0,1], got " + capacityMultiplier);
        }
    }

    /**
     * Convenience constructor defaulting capacityMultiplier to 1.0 (uncapped).
     */
    public WeightUpdateContext(Map<String, Double> inputActivations,
                               double outcomeIntensity, double outcomeValence,
                               double salienceMultiplier, String reinforcementSchedule) {
        this(inputActivations, outcomeIntensity, outcomeValence,
             salienceMultiplier, reinforcementSchedule, 1.0);
    }
}
```

- [ ] **Step 2: Write failing test for capacity-modulated alpha**

In `CapsWeightUpdaterTest.java`, add a test verifying that `capacityMultiplier` scales `baseAlpha`:

```java
@Test
void capacityMultiplierScalesBaseAlpha() {
    // Two updates identical except for capacityMultiplier
    var ctx1 = new WeightUpdateContext(inputs, 0.8, 1.0, 0.5, "continuous", 1.0);
    var ctx2 = new WeightUpdateContext(inputs, 0.8, 1.0, 0.5, "continuous", 0.55);

    AgentCapsState result1 = updater.update(baseState, ctx1);
    AgentCapsState result2 = updater.update(baseState, ctx2);

    // Lower capacity → smaller weight delta
    double delta1 = Math.abs(getWeightDelta(result1, baseState, connectionKey));
    double delta2 = Math.abs(getWeightDelta(result2, baseState, connectionKey));
    assertThat(delta2).isLessThan(delta1);
    assertThat(delta2 / delta1).isCloseTo(0.55, Offset.offset(0.05));
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-engine -Dtest=CapsWeightUpdaterTest#capacityMultiplierScalesBaseAlpha -DfailIfNoTests=false`
Expected: Compilation failure — `WeightUpdateContext` not yet on classpath, `CapsEngine.updateWeights` signature mismatch

- [ ] **Step 4: Change CapsEngine SPI signature**

In `CapsEngine.java`, replace the 6-parameter `updateWeights` with:

```java
AgentCapsState updateWeights(AgentCapsState state, WeightUpdateContext context);
```

- [ ] **Step 5: Update CapsWeightUpdater to accept WeightUpdateContext and apply capacityMultiplier**

In `CapsWeightUpdater.update()`, change signature to accept `WeightUpdateContext context`. Extract fields from context. At the `baseAlpha` computation (around line 52-53):

```java
double baseAlpha = clamp(context.salienceMultiplier() * config.salienceAlphaScaling(),
                         config.alphaMin(), config.alphaMax());
// Cattell (1971) Investment Theory: associativeReach modulates associative learning rate
baseAlpha *= context.capacityMultiplier();
double effectiveAlpha = baseAlpha / cw.precision();
```

- [ ] **Step 6: Update all CapsEngine implementations**

Update each implementation to use the new signature, extracting parameters from `WeightUpdateContext`:
- `SqliteCapsEngine` — delegate to `CapsWeightUpdater.update(state, context)`
- `InMemoryCapsEngine` (caps-testing) — delegate similarly
- `InMemoryCapsEngine` (memory-seeding, if separate) — delegate similarly
- `StubCapsEngine`, `CapturingCapsEngine`, `EmotionAwareStubCapsEngine` in `BehavioralSynthesisPhaseTest` — update to accept `WeightUpdateContext`

- [ ] **Step 7: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-engine -Dtest=CapsWeightUpdaterTest`
Expected: All tests PASS

- [ ] **Step 8: Add boundary tests**

```java
@Test
void capacityMultiplierAtZeroProducesNoLearning() {
    var ctx = new WeightUpdateContext(inputs, 0.8, 1.0, 0.5, "continuous", 0.0);
    AgentCapsState result = updater.update(baseState, ctx);
    // Weight should not change (alpha = 0)
    assertThat(getWeightDelta(result, baseState, connectionKey)).isCloseTo(0.0, Offset.offset(1e-10));
}

@Test
void capacityMultiplierAtOneIsUnchangedFromBaseline() {
    var ctx = new WeightUpdateContext(inputs, 0.8, 1.0, 0.5, "continuous", 1.0);
    AgentCapsState result = updater.update(baseState, ctx);
    // Should match pre-modulation behavior exactly
    assertThat(getWeightDelta(result, baseState, connectionKey)).isNotCloseTo(0.0, Offset.offset(1e-10));
}

@Test
void weightUpdateContextRejectsInvalidCapacity() {
    assertThatThrownBy(() -> new WeightUpdateContext(inputs, 0.8, 1.0, 0.5, "continuous", 1.5))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new WeightUpdateContext(inputs, 0.8, 1.0, 0.5, "continuous", -0.1))
        .isInstanceOf(IllegalArgumentException.class);
}
```

- [ ] **Step 9: Run full caps-api + caps-engine + caps-testing build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-api,caps-engine,caps-testing`
Expected: All tests PASS

- [ ] **Step 10: Commit**

```bash
git add caps-api/ caps-engine/ caps-testing/ memory-seeding/ mindmap-intelligence/
git commit -m "feat(#890): introduce WeightUpdateContext, wire capacityMultiplier into CAPS alpha

Cattell (1971) Investment Theory: associativeReach (Mednick 1962)
modulates Rescorla-Wagner base alpha for stimulus-response learning.

Refs #890"
```

---

## Batch 2: Memory Layer — CBR recordOutcome overload + graduation scorer

### Task 2: CbrRecordLifecycle 4-arg recordOutcome + DelegatingCbrRecordStore forwarding

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrRecordLifecycle.java` — add default method overload
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/DelegatingCbrRecordStore.java` — forward 4-arg call to delegate
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrRecordStore.java` — override 4-arg to use learningRateOverride
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrRecordStore.java` — override 4-arg to use learningRateOverride
- Test: `memory-testing/src/main/java/io/casehub/neocortex/memory/testing/CbrRecordStoreContractTest.java` — add contract tests

**Interfaces:**
- Consumes: `CbrOutcome.adjustConfidence(Confidence, double, double)` — existing static method
- Produces: `CbrRecordLifecycle.recordOutcome(String caseId, CbrOutcome outcome, String tenantId, Double learningRateOverride)` — default method, used by Task 4

- [ ] **Step 1: Write failing contract test**

In `CbrRecordStoreContractTest.java`:

```java
@Test
void recordOutcomeWithLearningRateOverrideUsesOverride() {
    store.registerSchema(schema);
    store.store(testCase, TENANT);
    CbrOutcome outcome = CbrOutcome.of(1.0, "success", Instant.now());

    // Record with a high learning rate override (0.8 vs schema default 0.2)
    store.recordOutcome(testCase.caseId(), outcome, TENANT, 0.8);

    // The confidence should shift more aggressively toward 1.0 with LR=0.8
    var matches = store.retrieveSimilar(query, TENANT);
    double confidenceWithOverride = matches.get(0).confidence().value();

    // Reset and record with null override (should use schema default)
    // This is the baseline comparison — verify override had larger effect
    assertThat(confidenceWithOverride).isGreaterThan(0.8); // LR=0.8 from base 1.0 toward 1.0
}

@Test
void recordOutcomeWithNullOverrideFallsBackToSchemaRate() {
    store.registerSchema(schema);
    store.store(testCase, TENANT);
    CbrOutcome outcome = CbrOutcome.of(1.0, "success", Instant.now());

    store.recordOutcome(testCase.caseId(), outcome, TENANT, null);

    // Should behave identically to 3-arg version
    var matches = store.retrieveSimilar(query, TENANT);
    assertThat(matches).isNotEmpty();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-testing -Dtest=CbrRecordStoreContractTest`
Expected: Compilation failure — 4-arg `recordOutcome` method doesn't exist

- [ ] **Step 3: Add default method overload on CbrRecordLifecycle**

```java
/**
 * Records an outcome with an optional learning rate override. Per Cattell's (1971)
 * Investment Theory, workingMemorySpan (Engle & Kane 2004) modulates the EMA
 * learning rate — higher working memory enables better evaluation of multi-factor
 * outcomes, accelerating confidence convergence.
 *
 * @param learningRateOverride when non-null, replaces the schema's learningRate
 *                             for this outcome's EMA confidence adjustment
 */
default void recordOutcome(String caseId, CbrOutcome outcome,
                            String tenantId, Double learningRateOverride) {
    recordOutcome(caseId, outcome, tenantId);
}
```

- [ ] **Step 4: Forward in DelegatingCbrRecordStore**

```java
@Override
public void recordOutcome(String caseId, CbrOutcome outcome,
                           String tenantId, Double learningRateOverride) {
    delegate().recordOutcome(caseId, outcome, tenantId, learningRateOverride);
}
```

- [ ] **Step 5: Override in InMemoryCbrRecordStore**

In the existing `recordOutcome` logic, find where `adjustConfidence` is called with the schema's `learningRate`. Add the override variant that substitutes the rate:

```java
@Override
public void recordOutcome(String caseId, CbrOutcome outcome,
                           String tenantId, Double learningRateOverride) {
    // Same as 3-arg, but use learningRateOverride when non-null
    // instead of schema.learningRate()
    double rate = learningRateOverride != null ? learningRateOverride
        : (schema.learningRate() != null ? schema.learningRate() : CbrOutcome.DEFAULT_LEARNING_RATE);
    // ... rest of existing logic with this rate
}
```

Refactor the existing 3-arg `recordOutcome` to delegate to the 4-arg with `null`.

- [ ] **Step 6: Override in QdrantCbrRecordStore**

Same pattern as InMemory — extract learning rate resolution, override the 4-arg method.

- [ ] **Step 7: Run contract tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem -Dtest=InMemoryCbrRecordStoreTest`
Expected: All tests PASS including new contract tests

- [ ] **Step 8: Commit**

```bash
git add memory-api/ memory-cbr-inmem/ memory-qdrant/ memory-testing/
git commit -m "feat(#890): add 4-arg recordOutcome with learningRateOverride on CbrRecordLifecycle

Cattell (1971) Investment Theory: workingMemorySpan (Engle & Kane 2004)
modulates EMA learning rate for CBR outcome confidence adjustment.
Default method is backwards-compatible; DelegatingCbrRecordStore forwards.

Refs #890"
```

### Task 3: GraduationContext agentId + DefaultGraduationScorer capacity modulation

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/experience/GraduationContext.java` — add `String agentId` field
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultGraduationScorer.java` — inject CognitiveDefaultsRegistry, multiply score by relationalComplexity
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationPhase.java` — pass agentId in GraduationContext
- Test: `mindmap-intelligence/src/test/java/.../DefaultGraduationScorerTest.java`

**Interfaces:**
- Consumes: `CognitiveDefaultsRegistry.forAgentOrDefaults(String agentId)` — from cognitive-index
- Consumes: `CognitiveCapacityConfig.relationalComplexityOrDefault()` — from cognitive-api
- Produces: `GraduationContext(int corroboratingCount, int textSimilarityCount, String tenantId, String agentId)` — updated record

- [ ] **Step 1: Write failing test for capacity-modulated graduation score**

```java
@Test
void capacityModulatesGraduationScore() {
    // Set up a memory with confidence 0.8, passing corroboration gate
    var memory = memoryWithConfidence(0.8);
    var context = new GraduationContext(5, 0, TENANT, AGENT_ID);

    // With registry returning capacity 0.55 relationalComplexity
    when(registry.forAgentOrDefaults(AGENT_ID))
        .thenReturn(defaultsWithCapacity(0.55));

    double score = scorer.score(memory, context);
    assertThat(score).isCloseTo(0.8 * 0.55, Offset.offset(0.01));
}

@Test
void formativeMemoriesExemptFromCapacityModulation() {
    var formative = formativeMemory();
    var context = new GraduationContext(5, 0, TENANT, AGENT_ID);

    when(registry.forAgentOrDefaults(AGENT_ID))
        .thenReturn(defaultsWithCapacity(0.55));

    double score = scorer.score(formative, context);
    // Should match FormativeScoring.score() — no capacity modulation
    assertThat(score).isEqualTo(FormativeScoring.score(formative));
}

@Test
void nullCapacityConfigDefaultsToNoModulation() {
    var memory = memoryWithConfidence(0.8);
    var context = new GraduationContext(5, 0, TENANT, AGENT_ID);

    when(registry.forAgentOrDefaults(AGENT_ID))
        .thenReturn(defaultsWithCapacity(null)); // null relationalComplexity

    double score = scorer.score(memory, context);
    // relationalComplexityOrDefault() returns 1.0 when null
    assertThat(score).isCloseTo(0.8, Offset.offset(0.01));
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DefaultGraduationScorerTest`
Expected: Compilation failure — GraduationContext doesn't have agentId, DefaultGraduationScorer doesn't take registry

- [ ] **Step 3: Add agentId to GraduationContext**

```java
/**
 * @param agentId the agent whose experience is being graduated; used to resolve
 *                capacity for Cattell's (1971) Investment Theory modulation
 */
public record GraduationContext(int corroboratingCount, int textSimilarityCount,
                                 String tenantId, String agentId) {
    // Backward-compatible constructor for existing callers
    public GraduationContext(int corroboratingCount, int textSimilarityCount,
                              String tenantId) {
        this(corroboratingCount, textSimilarityCount, tenantId, null);
    }
}
```

- [ ] **Step 4: Modify DefaultGraduationScorer to inject registry and apply capacity**

Add `CognitiveDefaultsRegistry` as constructor parameter (via CDI `Instance<CognitiveDefaultsRegistry>` for graceful degradation). In `score()`, after the formative check and corroboration gate:

```java
/**
 * Capacity modulation per Cattell's (1971) Investment Theory:
 * relationalComplexity (Halford 1998) scales the graduation score —
 * higher relational complexity enables better abstraction from experience.
 *
 * <p>Formative memories are exempt — developmental history is not subject
 * to runtime capacity differences. Cross-site interaction: this score flows
 * into BehavioralSynthesisPhase as outcomeIntensity (β), composing with
 * CAPS alpha modulation (associativeReach) on independent dimensions.
 */
double rawScore = confidence != null ? confidence.value() : 0.5;
double capacityFactor = resolveRelationalComplexity(context.agentId());
return rawScore * capacityFactor;
```

Where `resolveRelationalComplexity` checks the registry if available, returns 1.0 otherwise.

- [ ] **Step 5: Update ExperienceConsolidationPhase to pass agentId**

Find where `GraduationContext` is constructed and add the agentId extracted from `memory.subject().id()`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DefaultGraduationScorerTest`
Expected: All tests PASS

- [ ] **Step 7: Run full build for affected modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api,mindmap-intelligence`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add memory-api/ mindmap-intelligence/
git commit -m "feat(#890): add agentId to GraduationContext, capacity-modulate graduation score

Cattell (1971) Investment Theory: relationalComplexity (Halford 1998)
scales graduation score — higher relational complexity produces
higher-quality knowledge representations. Formative memories exempt.

Refs #890"
```

---

## Batch 3: Cognition Layer — drive, strategy, personality modulation

### Task 4: DriveAdaptationPhase + PersonalityEvolutionOrchestrator capacity modulation

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveAdaptationPhase.java` — add CognitiveDefaultsRegistry, apply associativeReach multiplier
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/personality/PersonalityEvolutionOrchestrator.java` — add CognitiveDefaultsRegistry, scale l2Ceiling by relationalComplexity
- Test: `cognition/src/test/java/.../DriveAdaptationPhaseTest.java`
- Test: `cognition/src/test/java/.../PersonalityEvolutionOrchestratorTest.java`

**Interfaces:**
- Consumes: `CognitiveDefaultsRegistry.forAgentOrDefaults(String agentId)` — from cognitive-index
- Consumes: `CognitiveCapacityConfig.associativeReachOrDefault()` — for drives
- Consumes: `CognitiveCapacityConfig.relationalComplexityOrDefault()` — for personality

- [ ] **Step 1: Write failing test for drive adaptation capacity modulation**

```java
@Test
void capacityModulatesDriveAdaptationRate() {
    // Set up with associativeReach = 0.6
    when(registry.forAgentOrDefaults(AGENT_ID))
        .thenReturn(defaultsWithAssociativeReach(0.6));

    // Run tick with known reward signals
    phase.doTick(tickContext);

    // Verify effectiveLR is base * satisfaction_mod * 0.6
    // Compare against a run with capacity 1.0
    assertThat(capturedLearningRate).isCloseTo(expectedBaseLR * 0.6, Offset.offset(0.01));
}
```

- [ ] **Step 2: Write failing test for personality ceiling capacity modulation**

```java
@Test
void capacityModulatesPersonalityDriftCeiling() {
    // Set up with relationalComplexity = 0.7, drift at 0.12
    when(registry.forAgentOrDefaults(AGENT_ID))
        .thenReturn(defaultsWithRelationalComplexity(0.7));

    // l2Ceiling default = 0.15, effective = 0.15 * 0.7 = 0.105
    // Drift of 0.12 exceeds effective ceiling → should halt
    orchestrator.doTick(tickContext);

    assertThat(evolutionState.isHalted()).isTrue();
}

@Test
void fullCapacityPreservesOriginalCeiling() {
    when(registry.forAgentOrDefaults(AGENT_ID))
        .thenReturn(defaultsWithRelationalComplexity(1.0));

    // l2Ceiling = 0.15 * 1.0 = 0.15, drift at 0.12 → should NOT halt
    orchestrator.doTick(tickContext);

    assertThat(evolutionState.isHalted()).isFalse();
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="DriveAdaptationPhaseTest#capacityModulates*,PersonalityEvolutionOrchestratorTest#capacityModulates*" -DfailIfNoTests=false`
Expected: FAIL

- [ ] **Step 4: Add CognitiveDefaultsRegistry to DriveAdaptationPhase**

Add `Instance<CognitiveDefaultsRegistry>` constructor parameter for graceful degradation. In the learning rate computation, after the conditional satisfaction modulation:

```java
// Cattell (1971): associativeReach (Mednick 1962) scales drive-outcome learning
double capacityFactor = resolveAssociativeReach(agentId);
effectiveLR *= capacityFactor;
```

Apply unconditionally — regardless of whether satisfaction modulation ran.

- [ ] **Step 5: Add CognitiveDefaultsRegistry to PersonalityEvolutionOrchestrator**

Add `Instance<CognitiveDefaultsRegistry>` constructor parameter. In the drift check:

```java
// Cattell (1971): relationalComplexity (Halford 1998) scales personality drift ceiling
double capacityFactor = resolveRelationalComplexity(agentId);
double effectiveCeiling = config.l2Ceiling() * capacityFactor;
if (drift > effectiveCeiling) { ... }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="DriveAdaptationPhaseTest,PersonalityEvolutionOrchestratorTest"`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add cognition/
git commit -m "feat(#890): capacity-modulate drive adaptation and personality drift ceiling

DriveAdaptationPhase: associativeReach (Mednick 1962) scales drive LR.
PersonalityEvolutionOrchestrator: relationalComplexity (Halford 1998)
scales l2Ceiling — higher capacity tolerates larger personality adjustments.

Refs #890"
```

### Task 5: StrategyLearningOrchestrator capacity modulation (ceiling + LLM prompt)

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/strategy/StrategyLearningOrchestrator.java` — add CognitiveDefaultsRegistry, scale maxDimensionDelta by workingMemorySpan, update systemPrompt to use effective delta
- Test: `cognition/src/test/java/.../StrategyLearningOrchestratorTest.java`

**Interfaces:**
- Consumes: `CognitiveDefaultsRegistry.forAgentOrDefaults(String agentId)`
- Consumes: `CognitiveCapacityConfig.workingMemorySpanOrDefault()`

- [ ] **Step 1: Write failing test for strategy ceiling capacity modulation**

```java
@Test
void capacityModulatesStrategyDeltaCeiling() {
    when(registry.forAgentOrDefaults(AGENT_ID))
        .thenReturn(defaultsWithWorkingMemorySpan(0.6));

    // maxDimensionDelta default = 0.2, effective = 0.2 * 0.6 = 0.12
    // Propose a delta of 0.15 — should be clamped to 0.12
    var result = orchestrator.applyReflectionResult(
        profile, jsonWithDelta("formality", 0.15), trends, cases, AGENT_ID, TENANT, state);

    assertThat(result.dimensions().get("formality"))
        .isCloseTo(baseline + 0.12, Offset.offset(0.01));
}

@Test
void systemPromptReflectsEffectiveMaxDelta() {
    when(registry.forAgentOrDefaults(AGENT_ID))
        .thenReturn(defaultsWithWorkingMemorySpan(0.7));

    // effective delta = 0.2 * 0.7 = 0.14
    String prompt = orchestrator.systemPrompt(AGENT_ID);
    assertThat(prompt).contains("[-0.14, +0.14]");
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="StrategyLearningOrchestratorTest#capacityModulates*,StrategyLearningOrchestratorTest#systemPromptReflects*" -DfailIfNoTests=false`
Expected: FAIL

- [ ] **Step 3: Add CognitiveDefaultsRegistry to StrategyLearningOrchestrator**

Add constructor parameter. Modify `systemPrompt()` to take `String agentId`, resolve capacity, format with effective delta. Modify `applyReflectionResult()` to compute effective max delta:

```java
// Cattell (1971): workingMemorySpan (Engle & Kane 2004) scales strategy adaptation ceiling
double effectiveMaxDelta = config.maxDimensionDelta()
    * resolveWorkingMemorySpan(agentId);
double clamped = Math.max(-effectiveMaxDelta, Math.min(effectiveMaxDelta, delta.getValue()));
```

Update all callers of `systemPrompt()` to pass agentId.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=StrategyLearningOrchestratorTest`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add cognition/
git commit -m "feat(#890): capacity-modulate strategy adaptation ceiling and LLM prompt

workingMemorySpan (Engle & Kane 2004) scales maxDimensionDelta ceiling.
Both the delta clamp and the LLM system prompt use the effective value
so the model's proposed deltas match the actual allowed range.

Refs #890"
```

---

## Batch 4: Wiring + Cross-Site Integration

### Task 6: Wire BehavioralSynthesisPhase to pass capacity to CAPS and CBR

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhase.java` — resolve capacity, construct WeightUpdateContext with capacityMultiplier, call 4-arg recordOutcome with effectiveLR
- Modify: `mindmap-intelligence/src/test/java/.../BehavioralSynthesisPhaseTest.java` — update for new WeightUpdateContext, verify capacity flows through

**Interfaces:**
- Consumes: `WeightUpdateContext` from Task 1
- Consumes: `CbrRecordLifecycle.recordOutcome(caseId, outcome, tenantId, learningRateOverride)` from Task 2
- Consumes: `CognitiveDefaultsRegistry.forAgentOrDefaults(String agentId)`

- [ ] **Step 1: Write failing test for capacity flowing through BehavioralSynthesisPhase**

```java
@Test
void behavioralSynthesisPassesCapacityToCapsAndCbr() {
    setUpAgentWithCapacity(0.7, 0.8); // associativeReach=0.7, wmSpan=0.8

    phase.run(TENANT, subgraphPriority);

    // Verify CAPS received capacity in WeightUpdateContext
    var capturedContext = capturingEngine.lastContext();
    assertThat(capturedContext.capacityMultiplier()).isCloseTo(0.7, Offset.offset(0.01));

    // Verify CBR received modulated learning rate
    var capturedLR = capturingStore.lastLearningRateOverride();
    assertThat(capturedLR).isNotNull();
    assertThat(capturedLR).isCloseTo(CbrOutcome.DEFAULT_LEARNING_RATE * 0.8, Offset.offset(0.01));
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="BehavioralSynthesisPhaseTest#behavioralSynthesisPassesCapacity*" -DfailIfNoTests=false`
Expected: FAIL

- [ ] **Step 3: Wire BehavioralSynthesisPhase**

Add `CognitiveDefaultsRegistry` dependency (via `Instance<>` for graceful degradation). In the weight update path, resolve capacity and construct `WeightUpdateContext` with `associativeReachOrDefault()`. In the CBR outcome recording path, compute `effectiveLR = schemaLR * capacity.workingMemorySpanOrDefault()` and call the 4-arg `recordOutcome`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=BehavioralSynthesisPhaseTest`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add mindmap-intelligence/
git commit -m "feat(#890): wire BehavioralSynthesisPhase to pass capacity to CAPS and CBR

Resolves associativeReach for CAPS alpha, workingMemorySpan for CBR
learning rate. Both flow through CognitiveDefaultsRegistry with graceful
degradation when no registry is available.

Refs #890"
```

### Task 7: Cross-site integration test + CDE derivation verification

**Files:**
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/CapacityLearningRateIntegrationTest.java`
- Test: verify cross-site proportionality, dimension independence, and baseline equivalence

**Interfaces:**
- Consumes: All capacity-modulated sites from Tasks 1-6

- [ ] **Step 1: Write cross-site integration test**

```java
@QuarkusTest
class CapacityLearningRateIntegrationTest {

    @Test
    void agentWithFullCapacityMatchesPreModulationBaseline() {
        // Agent with all dimensions at 1.0 should produce identical
        // behavior to an agent with null capacityConfig
        var fullCapacity = new CognitiveCapacityConfig(1.0, 1.0, 1.0);
        var nullCapacity = (CognitiveCapacityConfig) null;

        // Run consolidation cycle for both
        // Verify identical CAPS weight deltas, graduation scores, drive LR
    }

    @Test
    void crossSiteCompoundingUsesIndependentDimensions() {
        // Agent with high associativeReach (0.9) but low relationalComplexity (0.55)
        // should have fast CAPS learning (high alpha) but low graduation scores
        var asymmetric = new CognitiveCapacityConfig(0.55, 0.9, 0.75);

        // Run consolidation
        // Verify alpha reflects 0.9 (associativeReach)
        // Verify graduation score reflects 0.55 (relationalComplexity)
        // The compound effect is ~0.55*0.9=0.495, NOT 0.55^2=0.30
    }

    @Test
    void dimensionMappingBalance() {
        // Verify 2-2-2 balance: changing each dimension independently
        // affects exactly 2 sites
        // relationalComplexity → graduation + personality
        // associativeReach → CAPS + drive
        // workingMemorySpan → CBR + strategy
    }
}
```

- [ ] **Step 2: Run the integration test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=CapacityLearningRateIntegrationTest`
Expected: All tests PASS

- [ ] **Step 3: Verify CDE derivation still compresses to [0.55, 0.95]**

Quick sanity test that `CognitiveDerivationEngine.deriveCapacity()` still produces values in the expected range:

```java
@Test
void derivedCapacityStaysInCompressedRange() {
    // Profile with all functions at maximum
    var maxProfile = List.of(wt("ti", 1.0), wt("te", 1.0), wt("ne", 1.0), wt("ni", 1.0), wt("si", 1.0));
    var result = CognitiveDerivationEngine.deriveCapacity(maxProfile);
    assertThat(result.relationalComplexity()).isCloseTo(0.95, Offset.offset(0.01));

    // Profile with all functions at minimum
    var minProfile = List.of(wt("ti", 0.0), wt("te", 0.0), wt("ne", 0.0), wt("ni", 0.0), wt("si", 0.0));
    var resultMin = CognitiveDerivationEngine.deriveCapacity(minProfile);
    assertThat(resultMin.relationalComplexity()).isCloseTo(0.55, Offset.offset(0.01));
}
```

- [ ] **Step 4: Run full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests=false`
Expected: BUILD SUCCESS, all tests PASS

- [ ] **Step 5: Commit**

```bash
git add cognition/
git commit -m "feat(#890): add cross-site integration tests for capacity learning rate modulation

Verifies: full-capacity baseline equivalence, independent dimension
compounding (not quadratic), 2-2-2 dimension balance across 6 sites.

Refs #890"
```

---

## References

- [2026-11-10-intelligence-capacity-learning-rate-design.md] — design spec this plan implements
- `cognitive-api/.../CognitiveCapacityConfig.java` — capacity record (3 dimensions, [0,1], nullable Double)
- `cognitive-index/.../CognitiveDerivationEngine.java:270-299` — deriveCapacity + compressCapacity
- `cognitive-index/.../CognitiveDefaultsRegistry.java` — per-agent config resolution
- `caps-api/.../CapsEngine.java:16-22` — updateWeights SPI (6 params → WeightUpdateContext)
- `caps-engine/.../CapsWeightUpdater.java:48-66` — Rescorla-Wagner alpha computation
- `memory-api/.../CbrRecordLifecycle.java:13` — recordOutcome SPI
- `memory-api/.../CbrOutcome.java:17,33-38` — DEFAULT_LEARNING_RATE, adjustConfidence EMA
- `memory-api/.../DelegatingCbrRecordStore.java` — decorator forwarding base
- `memory-api/.../GraduationContext.java` — graduation context (gains agentId)
- `mindmap-intelligence/.../DefaultGraduationScorer.java:33-41` — graduation scoring
- `mindmap-intelligence/.../BehavioralSynthesisPhase.java` — CAPS + CBR wiring hub
- `cognition/.../DriveAdaptationPhase.java:220-248` — drive intensity learning rate
- `cognition/.../StrategyLearningOrchestrator.java:50-56,554-588` — systemPrompt + clamp
- `cognition/.../PersonalityEvolutionOrchestrator.java:103-110` — l2Ceiling
- GitHub #840 — intelligence capacity layer (prerequisite)
- GitHub #880 — shared fatigue substrate (cross-reference)
- GitHub #890 — this issue

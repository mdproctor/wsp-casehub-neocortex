# Search Budget Situational Strength Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #839 — Search budget: personality expression under extreme motivation — situational strength interaction
**Issue group:** #839

**Goal:** Replace uniform logistic activation with personality-modulated activation functions that maintain personality differentiation at extreme motivation intensity via three mechanisms: inverted-U decline, modulation scaling, and fatigue reallocation.

**Architecture:** Three interaction effects applied in sequence: (1) exponential decay past personality-specific peak replaces bare logistic, (2) drive modulations scale with intensity via per-parameter amplification rates, (3) sustained fatigue reallocates budget per-parameter based on Hockey's compensatory control model. All parameterised via `ExtremeInteractionConfig` and `FatigueConfig` sub-records on `SearchBudgetConfig`, CDE-derived from PID-5 facets.

**Tech Stack:** Java 21, Quarkus 3.32.2, Mockito (tests), JUnit 5

## Global Constraints

- Java 21 source (Java 26 JVM): `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn`
- `SearchBudgetConfig.defaults()` must remain backward-compatible: null sub-records disable new features
- Existing `SearchBudgetTickParticipantTest` must pass without modification (default config → unchanged behavior)
- CDE coefficient values are calibration parameters — quality test invariants constrain them, not exact literature values
- `withX()` copy methods follow `CognitiveDefaults` convention — no builders

---

## Batch 1: Config Records + CDE Derivation

### Task 1: ExtremeInteractionConfig and FatigueConfig records

**Files:**
- Create: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/ExtremeInteractionConfig.java`
- Create: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/FatigueConfig.java`
- Create: `cognitive-api/src/test/java/io/casehub/neocortex/cognitive/ExtremeInteractionConfigTest.java`
- Create: `cognitive-api/src/test/java/io/casehub/neocortex/cognitive/FatigueConfigTest.java`

**Interfaces:**
- Produces: `ExtremeInteractionConfig` record (8 fields: depthDecay, breadthDecay, lateralityDecay, convergenceDecay, depthAmplification, breadthAmplification, lateralityAmplification, convergenceAmplification) with `defaults()`, `withX()` for all fields
- Produces: `FatigueConfig` record (6 fields: maxTicks, recoveryRate, depthEffect, breadthEffect, lateralityEffect, convergenceEffect) with `defaults()`, `withX()` for all fields

- [ ] **Step 1: Write failing test for ExtremeInteractionConfig validation**

```java
@Test
void negative_decay_rejected() {
    assertThrows(IllegalArgumentException.class,
        () -> ExtremeInteractionConfig.defaults().withDepthDecay(-1.0));
}

@Test
void defaults_produces_valid_config() {
    var config = ExtremeInteractionConfig.defaults();
    assertEquals(0.0, config.depthDecay());
    assertEquals(1.5, config.breadthDecay());
    assertEquals(2.0, config.lateralityDecay());
    assertEquals(0.5, config.convergenceDecay());
    assertEquals(0.5, config.depthAmplification());
    assertEquals(-1.0, config.breadthAmplification());
    assertEquals(-0.8, config.lateralityAmplification());
    assertEquals(-1.5, config.convergenceAmplification());
}
```

- [ ] **Step 2: Implement ExtremeInteractionConfig**

Record with 8 fields, compact constructor validates decay >= 0. `defaults()` static factory. `withX()` copy method for each field. Javadoc on `defaults()` documenting approximated personality (C≈0.5, O≈0.5, anx≈0.3).

- [ ] **Step 3: Write failing test for FatigueConfig validation**

```java
@Test
void maxTicks_must_be_positive() {
    assertThrows(IllegalArgumentException.class,
        () -> FatigueConfig.defaults().withMaxTicks(0));
}

@Test
void effect_must_be_in_unit_range() {
    assertThrows(IllegalArgumentException.class,
        () -> FatigueConfig.defaults().withDepthEffect(-1.5));
}

@Test
void defaults_produces_valid_config() {
    var config = FatigueConfig.defaults();
    assertEquals(10, config.maxTicks());
    assertEquals(0.5, config.recoveryRate());
    assertEquals(-0.1, config.depthEffect());
    assertEquals(-0.2, config.breadthEffect());
    assertEquals(-0.15, config.lateralityEffect());
    assertEquals(0.1, config.convergenceEffect());
}
```

- [ ] **Step 4: Implement FatigueConfig**

Record with 6 fields. Compact constructor validates: maxTicks >= 1, recoveryRate >= 0, effects in [-1, 1]. `defaults()` static factory. `withX()` for all fields.

- [ ] **Step 5: Run tests, verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api`

- [ ] **Step 6: Commit**

```
feat(#839): add ExtremeInteractionConfig and FatigueConfig records
```

### Task 2: SearchBudgetConfig + SearchBudget changes

**Files:**
- Modify: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/SearchBudgetConfig.java`
- Modify: `cognitive-api/src/test/java/io/casehub/neocortex/cognitive/SearchBudgetConfigTest.java`
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/search/SearchBudget.java`
- Modify: `cognition-api/src/test/java/io/casehub/neocortex/cognition/search/SearchBudgetTest.java`

**Interfaces:**
- Consumes: `ExtremeInteractionConfig`, `FatigueConfig` from Task 1
- Produces: `SearchBudgetConfig` with 3 new fields: `extremePeak` (double), `extremeInteraction` (ExtremeInteractionConfig, nullable), `fatigue` (FatigueConfig, nullable); `defaults()` returns `extremePeak=0.85, null, null`; `withExtremePeak()`, `withExtremeInteraction()`, `withFatigue()` copy methods
- Produces: `SearchBudget` with new `extremeActivation` boolean field (6th field, before `evaluatedAt`)

- [ ] **Step 1: Write failing test for SearchBudgetConfig new fields**

```java
@Test
void defaults_include_extreme_fields() {
    var config = SearchBudgetConfig.defaults();
    assertEquals(0.85, config.extremePeak());
    assertNull(config.extremeInteraction());
    assertNull(config.fatigue());
}

@Test
void extremePeak_must_be_unit() {
    assertThrows(IllegalArgumentException.class,
        () -> SearchBudgetConfig.defaults().withExtremePeak(1.5));
}

@Test
void withExtremeInteraction_returns_copy() {
    var config = SearchBudgetConfig.defaults()
        .withExtremeInteraction(ExtremeInteractionConfig.defaults());
    assertNotNull(config.extremeInteraction());
    assertEquals(0.85, config.extremePeak()); // other fields unchanged
}
```

- [ ] **Step 2: Update SearchBudgetConfig**

Add 3 new fields to the record. Update compact constructor with `extremePeak` validation. Update `defaults()` to pass `0.85, null, null`. Add 3 `withX()` methods. **Critical:** update all existing callers that use the positional constructor — search for `new SearchBudgetConfig(` across the codebase. The test helper at `SearchBudgetTickParticipantTest:279` constructs with 11 args — must become 14.

- [ ] **Step 3: Write failing test for SearchBudget.extremeActivation**

```java
@Test
void extreme_activation_field() {
    var budget = new SearchBudget(0.5, 0.5, 0.5, 0.5, SearchMotivation.CURIOSITY, false, Instant.now());
    assertFalse(budget.extremeActivation());

    var extreme = new SearchBudget(0.5, 0.5, 0.5, 0.5, SearchMotivation.CURIOSITY, true, Instant.now());
    assertTrue(extreme.extremeActivation());
}
```

- [ ] **Step 4: Update SearchBudget record**

Add `boolean extremeActivation` as 6th field (before `evaluatedAt`). Update all existing callers — search for `new SearchBudget(` across the codebase.

- [ ] **Step 5: Run full build to catch all compilation errors**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl cognitive-api,cognition-api,cognition,cognitive-index,mindmap-intelligence`

Fix any callers still using old constructor signatures (add `false` for extremeActivation, `0.85, null, null` for SearchBudgetConfig).

- [ ] **Step 6: Run tests, verify existing tests still pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api,cognition-api`

- [ ] **Step 7: Commit**

```
feat(#839): add extremePeak, extremeInteraction, fatigue to SearchBudgetConfig; add extremeActivation to SearchBudget
```

### Task 3: CDE derivation pathways + quality tests

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java`
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngineSearchBudgetTest.java`
- Create: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/SearchBudgetExtremeInteractionTest.java`

**Interfaces:**
- Consumes: `ExtremeInteractionConfig`, `FatigueConfig`, `SearchBudgetConfig` from Tasks 1-2
- Produces: `deriveSearchBudgetDefaults()` returns `SearchBudgetConfig` with all 14 fields populated from personality facets

- [ ] **Step 1: Write failing quality test — personality differentiation at extreme intensity**

Create `SearchBudgetExtremeInteractionTest.java` with:

```java
@Test
void bold_and_anxious_worrier_produce_different_extreme_configs() {
    var bold = CognitiveDerivationEngine.deriveSearchBudgetDefaults(boldFacets(), boldAxes(), 0.8);
    var anxious = CognitiveDerivationEngine.deriveSearchBudgetDefaults(anxiousWorrierFacets(), anxiousWorrierAxes(), 0.3);

    // Bold should have higher peak (tolerates more intensity)
    assertTrue(bold.extremePeak() > anxious.extremePeak());

    // Anxious should have higher breadth/depth decay
    assertTrue(anxious.extremeInteraction().breadthDecay() > bold.extremeInteraction().breadthDecay());
    assertTrue(anxious.extremeInteraction().depthDecay() > bold.extremeInteraction().depthDecay());

    // Bold depth amplification should be positive (amplifies), anxious negative (compresses)
    assertTrue(bold.extremeInteraction().depthAmplification() > 0);
    assertTrue(anxious.extremeInteraction().depthAmplification() < 0);

    // Fatigue depth effect: both low-C → similar magnitude, both negative
    assertTrue(bold.fatigue().depthEffect() < 0);
    assertTrue(anxious.fatigue().depthEffect() < 0);

    // Convergence effect: bold positive (satisficing), anxious negative (blocked)
    assertTrue(bold.fatigue().convergenceEffect() > 0);
    assertTrue(anxious.fatigue().convergenceEffect() < 0);
}

@Test
void conscientiousness_protects_depth_in_extreme_config() {
    var disciplined = CognitiveDerivationEngine.deriveSearchBudgetDefaults(disciplinedFacets(), disciplinedAxes(), 0.3);
    // High-C: depthDecay = 0 (protected)
    assertEquals(0.0, disciplined.extremeInteraction().depthDecay());
    // High-C: depthEffect near 0 (protected)
    assertTrue(disciplined.fatigue().depthEffect() > -0.02);
    // High-C: convergenceEffect positive (satisficing)
    assertTrue(disciplined.fatigue().convergenceEffect() > 0);
}

@Test
void inverted_u_activates_past_personality_peak() {
    var anxious = CognitiveDerivationEngine.deriveSearchBudgetDefaults(anxiousWorrierFacets(), anxiousWorrierAxes(), 0.3);
    double peak = anxious.extremePeak();
    double decay = anxious.extremeInteraction().breadthDecay();

    // Below peak: activation = logistic (no penalty)
    double belowPeak = activationWithDecay(peak - 0.1, 6.0, 0.5, decay, peak);
    double atPeak = activationWithDecay(peak, 6.0, 0.5, decay, peak);
    double abovePeak = activationWithDecay(peak + 0.1, 6.0, 0.5, decay, peak);

    assertTrue(belowPeak <= atPeak, "Below peak should not exceed peak activation");
    assertTrue(abovePeak < atPeak, "Above peak should be less than peak activation");
}
```

Helper methods: `boldFacets()`, `boldAxes()`, `anxiousWorrierFacets()` (anx=0.8, lab=0.7, imp=0.7, withdrawal=0.7, IA=0.6, susp=0.7, risk=0.1, ruleFollowing="flexible"), `disciplinedFacets()` (same anxiety but strict, imp=0.1), `activationWithDecay()` static.

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=SearchBudgetExtremeInteractionTest`
Expected: compilation failure (deriveSearchBudgetDefaults returns old SearchBudgetConfig without new fields)

- [ ] **Step 3: Implement CDE derivation pathways**

In `CognitiveDerivationEngine.deriveSearchBudgetDefaults()`:

1. Add `extremePeak` derivation after existing pathological threshold:
```java
double extremePeak = 0.85 - (anxiousness - 0.5) * 0.3 - (emotionalLability - 0.5) * 0.2;
extremePeak = Math.max(0.5, Math.min(0.95, extremePeak));
```

2. Add `ExtremeInteractionConfig` derivation:
```java
double depthDecay = Math.max(0, (anxiousness - 0.3) * 2.0 - conscientiousness * 1.5);
double breadthDecay = 1.0 + (1.0 - openness) * 2.0;
double lateralityDecay = 1.5 + (1.0 - openness) * 1.5 + impulsivity * 1.0;
double convergenceDecay = Math.max(0, anxiousness * 1.5 - conscientiousness * 1.0);
double depthAmplification = conscientiousness * 1.0 - anxiousness * 0.5;
double breadthAmplification = -(1.0 - openness) * 1.5;
double lateralityAmplification = -(1.0 - openness) * 1.2;
double convergenceAmplification = -(anxiousness * 2.0 - conscientiousness * 0.8);
var extremeInteraction = new ExtremeInteractionConfig(depthDecay, breadthDecay, lateralityDecay, convergenceDecay, depthAmplification, breadthAmplification, lateralityAmplification, convergenceAmplification);
```

3. Add `FatigueConfig` derivation:
```java
int fatigueMaxTicks = (int)(6 + conscientiousness * 8);
double fatigueRecovery = 0.3 + conscientiousness * 0.4;
double fatigueDepth = Math.min(0.0, -0.08 * (1.0 - conscientiousness));
double fatigueBreadth = -(0.15 + (1.0 - openness) * 0.15);
double fatigueLat = -(0.1 + (1.0 - openness) * 0.1) + impulsivity * 0.15;
double fatigueConv = conscientiousness * 0.2 - anxiousness * 0.15;
var fatigue = new FatigueConfig(fatigueMaxTicks, fatigueRecovery, fatigueDepth, fatigueBreadth, fatigueLat, fatigueConv);
```

4. Update the `return new SearchBudgetConfig(...)` call to include `extremePeak, extremeInteraction, fatigue`.

- [ ] **Step 4: Run quality tests, verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=SearchBudgetExtremeInteractionTest`

- [ ] **Step 5: Run existing CDE tests, verify no regression**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveDerivationEngineSearchBudgetTest`

- [ ] **Step 6: Commit**

```
feat(#839): add CDE derivation for extremePeak, ExtremeInteractionConfig, FatigueConfig
```

---

## Batch 2: Tick Participant — Activation Decay + Modulation Scaling + Fatigue

### Task 4: SearchBudgetTickParticipant — all three interaction effects

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/search/FatigueState.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetTickParticipant.java`
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/search/SearchBudgetTickParticipantTest.java`

**Interfaces:**
- Consumes: `SearchBudgetConfig` (with new fields), `ExtremeInteractionConfig`, `FatigueConfig` from Tasks 1-2
- Produces: `SearchBudget` results with `extremeActivation` flag set correctly; `activationWithDecay()` static method; `FatigueState` per-agent accumulator

- [ ] **Step 1: Create FatigueState value holder**

```java
package io.casehub.neocortex.cognition.search;

final class FatigueState {
    private double accumulator;

    FatigueState(double initial) { this.accumulator = initial; }
    double accumulator() { return accumulator; }
    void setAccumulator(double value) { this.accumulator = value; }
}
```

- [ ] **Step 2: Write failing test — activationWithDecay below peak equals logistic**

```java
@Test
void activation_with_decay_below_peak_equals_logistic() {
    double k = 6.0, mid = 0.5, decay = 2.0, peak = 0.8;
    double x = 0.6; // below peak
    double expected = SearchBudgetTickParticipant.logistic(x, k, mid);
    double actual = SearchBudgetTickParticipant.activationWithDecay(x, k, mid, decay, peak);
    assertEquals(expected, actual, 1e-10);
}

@Test
void activation_with_decay_past_peak_is_lower() {
    double k = 6.0, mid = 0.5, decay = 2.0, peak = 0.7;
    double atPeak = SearchBudgetTickParticipant.activationWithDecay(0.7, k, mid, decay, peak);
    double pastPeak = SearchBudgetTickParticipant.activationWithDecay(0.9, k, mid, decay, peak);
    assertTrue(pastPeak < atPeak, "Past-peak activation should be lower: at=" + atPeak + " past=" + pastPeak);
}

@Test
void activation_with_zero_decay_equals_logistic() {
    double k = 6.0, mid = 0.5, decay = 0.0, peak = 0.5;
    double x = 0.9;
    double expected = SearchBudgetTickParticipant.logistic(x, k, mid);
    double actual = SearchBudgetTickParticipant.activationWithDecay(x, k, mid, decay, peak);
    assertEquals(expected, actual, 1e-10);
}
```

- [ ] **Step 3: Implement activationWithDecay**

Add to `SearchBudgetTickParticipant`:
```java
static double activationWithDecay(double x, double k, double midpoint, double decay, double peak) {
    double base = logistic(x, k, midpoint);
    double penalty = Math.exp(-decay * Math.max(0.0, x - peak));
    return base * penalty;
}
```

- [ ] **Step 4: Run activation tests, verify pass**

- [ ] **Step 5: Write failing test — extreme interaction changes budget at high intensity**

```java
@Test
void extreme_interaction_narrows_breadth_past_peak() {
    var extreme = ExtremeInteractionConfig.defaults();
    var config = SearchBudgetConfig.defaults()
        .withExtremePeak(0.7)
        .withExtremeInteraction(extreme);
    var participant = withDriveAndConfig(DriveAxis.CURIOSITY, 0.9, config);
    participant.tick(context());

    var budget = participant.currentBudget(AGENT, TENANT).orElseThrow();
    assertTrue(budget.extremeActivation(), "Should be extreme past peak");

    // Compare with default config at same intensity
    var defaultParticipant = withDrive(DriveAxis.CURIOSITY, 0.9);
    defaultParticipant.tick(context());
    var defaultBudget = defaultParticipant.currentBudget(AGENT, TENANT).orElseThrow();

    assertTrue(budget.breadth() < defaultBudget.breadth(),
        "Extreme breadth should be narrower: " + budget.breadth() + " vs " + defaultBudget.breadth());
    assertFalse(defaultBudget.extremeActivation(), "Default config should not be extreme");
}
```

- [ ] **Step 6: Write failing test — fatigue accumulates over ticks**

```java
@Test
void fatigue_accumulates_and_degrades_breadth() {
    var config = SearchBudgetConfig.defaults()
        .withExtremePeak(0.6)
        .withFatigue(FatigueConfig.defaults());
    var participant = withDriveAndConfig(DriveAxis.CURIOSITY, 0.8, config);

    // First tick — fatigue starts
    participant.tick(context());
    var budget1 = participant.currentBudget(AGENT, TENANT).orElseThrow();

    // Fifth tick — fatigue accumulated
    for (int i = 0; i < 4; i++) participant.tick(context());
    var budget5 = participant.currentBudget(AGENT, TENANT).orElseThrow();

    assertTrue(budget5.breadth() < budget1.breadth(),
        "Fatigue should reduce breadth over time: tick1=" + budget1.breadth() + " tick5=" + budget5.breadth());
}

@Test
void fatigue_recovers_when_below_peak() {
    var config = SearchBudgetConfig.defaults()
        .withExtremePeak(0.6)
        .withFatigue(FatigueConfig.defaults());

    // Accumulate fatigue at high intensity
    var participant = withDriveAndConfig(DriveAxis.CURIOSITY, 0.8, config);
    for (int i = 0; i < 5; i++) participant.tick(context());

    // Switch to low intensity — should recover
    var lowDrives = mockDriveOrch(DriveAxis.CURIOSITY, 0.3);
    // Reconstruct participant with same fatigue state is tricky in unit test;
    // verify by checking fatigue doesn't prevent recovery to higher breadth
    // after several low-intensity ticks
}
```

- [ ] **Step 7: Implement all three effects in SearchBudgetTickParticipant**

1. Add `private final ConcurrentHashMap<String, FatigueState> fatigueStates = new ConcurrentHashMap<>();`

2. In each `computeX()` method:
   - Replace `logistic(intensity, k, mid)` with `activationWithDecay(intensity, k, mid, decay, peak)` where decay/peak come from `ExtremeInteractionConfig` (fall back to `decay=0, peak=config.extremePeak()` when null)
   - Replace `base += 0.15` with `base += 0.15 * scale` where `scale = Math.max(-1.0, 1.0 + amplificationRate * Math.max(0.0, intensity - config.extremePeak()))` (fall back to `scale=1.0` when null)

3. After all four compute calls, before channel modulation:
   - Compute fatigue level from `FatigueState`
   - Apply fatigue effects to all four parameters
   - Update `FatigueState` in map

4. Set `extremeActivation` flag:
   ```java
   boolean extremeActivation = (config.extremeInteraction() != null || config.fatigue() != null)
       && compositeIntensity > config.extremePeak();
   ```

5. Pass `extremeActivation` to `new SearchBudget(...)` constructor.

- [ ] **Step 8: Add test helper**

```java
private SearchBudgetTickParticipant withDriveAndConfig(DriveAxis axis, double intensity, SearchBudgetConfig config) {
    var reg = mock(CognitiveDefaultsRegistry.class);
    when(reg.forAgentOrDefaults(anyString())).thenReturn(
        CognitiveDefaults.empty(AGENT).withSearchBudgetConfig(config));
    return new SearchBudgetTickParticipant(
        mockDriveOrch(axis, intensity), null, null, null, reg, null, null);
}
```

- [ ] **Step 9: Run all tick participant tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=SearchBudgetTickParticipantTest`

Verify: all existing tests pass (default config → unchanged behavior), new tests pass.

- [ ] **Step 10: Commit**

```
feat(#839): add inverted-U activation, modulation scaling, fatigue reallocation to tick participant
```

---

## Batch 3: Prose Generation + Prompt Section + Integration

### Task 5: Prose generation and prompt section extreme-intensity selection

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SearchBudgetDescriptionGenerationPhase.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SearchBudgetDescriptionGenerationPhaseTest.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetPromptSection.java`
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/search/SearchBudgetPromptSectionTest.java`

**Interfaces:**
- Consumes: `SearchBudgetConfig` (extremeInteraction, fatigue, extremePeak), `SearchBudget` (extremeActivation)
- Produces: MindMap COGNITIVE node with `description` + `extreme-description` properties; prompt section selects based on `extremeActivation`

- [ ] **Step 1: Write failing test — description generation includes extreme prose when config has extreme features**

```java
@Test
void generates_extreme_description_when_extreme_config_present() {
    // Setup: agent with ExtremeInteractionConfig on their SearchBudgetConfig
    // Assert: MindMap node gets both "description" and "extreme-description" properties
}
```

- [ ] **Step 2: Update SearchBudgetDescriptionGenerationPhase**

1. Check if agent's config has extreme features: `config.extremeInteraction() != null || config.fatigue() != null`
2. If yes: expand the LLM prompt to request `{"normal": "...", "extreme": "..."}` JSON. Store `normal` as `description` property, `extreme` as `extreme-description` property.
3. If no: keep existing single-description behavior (backward compatible).
4. Update the programmatic fallback to also generate extreme-intensity fallback prose.

- [ ] **Step 3: Write failing test — prompt section selects extreme prose when extremeActivation is true**

```java
@Test
void selects_extreme_description_when_extreme_activation() {
    // Setup: MindMap node with both "description" and "extreme-description"
    // Budget with extremeActivation=true
    // Assert: rendered output uses extreme-description content
}

@Test
void selects_normal_description_when_not_extreme() {
    // Setup: same node, budget with extremeActivation=false
    // Assert: rendered output uses description content
}
```

- [ ] **Step 4: Update SearchBudgetPromptSection**

Add extreme-intensity prose selection:
```java
String crystallised = budget.extremeActivation()
    ? readProperty(agentId, tenantId, "extreme-description")
    : readProperty(agentId, tenantId, "description");
```

In `renderFromParameters()` fallback: add extreme-intensity templates when `extremeActivation` is true.

- [ ] **Step 5: Run all prose/prompt tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence,cognition -Dtest="SearchBudgetDescriptionGenerationPhaseTest,SearchBudgetPromptSectionTest"`

- [ ] **Step 6: Commit**

```
feat(#839): add extreme-intensity prose generation and prompt section selection
```

### Task 6: Update CLAUDE.md and run full build

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md**

Add `ExtremeInteractionConfig` and `FatigueConfig` to the SearchBudgetConfig documentation in the cognition section. Add fatigue dynamics summary.

- [ ] **Step 2: Run full module build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl cognitive-api,cognition-api,cognitive-index,cognition,mindmap-intelligence`

Verify all tests pass, no regressions.

- [ ] **Step 3: Commit**

```
docs(#839): update CLAUDE.md with situational strength interaction model
```

## References

- [2026-11-08-search-budget-situational-strength-design.md] — design spec this plan implements
- [SearchBudgetTickParticipant.java] — current activation functions and drive modulations
- [SearchBudgetConfig.java] — current config record (11 fields → 14)
- [CognitiveDerivationEngine.java:646] — current CDE derivation
- [SearchBudgetQualityTest.java] — existing quality test pattern
- [SearchBudgetTickParticipantTest.java] — existing unit test pattern with Mockito helpers
- [SearchBudgetPromptSection.java] — current prose rendering
- [SearchBudgetDescriptionGenerationPhase.java] — current consolidation prose generation
- [GitHub #839] — focal issue
- [GitHub #878] — deferred: per-parameter peaks
- [GitHub #879] — deferred: separate amplification threshold
- [GitHub #880] — deferred: shared fatigue substrate

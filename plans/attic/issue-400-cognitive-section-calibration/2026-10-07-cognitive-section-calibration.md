# Cognitive Section Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #400 — Cognitive section calibration — prominence, ordering, and disposition reinforcement
**Issue group:** #400

**Goal:** Implement arousal-gated tiered rendering of cognitive prompt sections, where the personality-cognition balance is derived from formation memory PAD patterns via CDE, and binary tier activation is controlled by runtime arousal.

**Architecture:** Three fixed tiers (Core/Contextual/Supplementary) assigned by section nature. A `personalityDominance` scalar (0.0-1.0) derived by CDE from formation memory PAD geometry controls arousal thresholds for tier activation. A `TierFilterCustomizer` plugs into the existing `sectionCustomizer` mechanism on `CognitionCore` to filter sections at render time. No changes to individual section renderers.

**Tech Stack:** Java 21, cognitive-index module (CDE, CognitiveDefaults, DescriptorView), cognition module (CognitionCore, prompt sections)

## Global Constraints

- Java 21 source (Java 26 JVM)
- All new records in cognitive-index must be zero-dep (no CDI, no Quarkus)
- Follow existing CDE derivation pattern: static method, DescriptorView input, CognitiveDefaults output
- Follow existing CognitiveDefaults wither pattern for new field
- Tests use JUnit 5, assertj

---

## Batch 1: Foundation — FormationPadSummary + DescriptorView extension + CDE pathway

### Task 1: FormationPadSummary record and DescriptorView extension

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/FormationPadSummary.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DescriptorView.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/FormationPadSummaryTest.java`

**Interfaces:**
- Consumes: nothing (new type)
- Produces: `FormationPadSummary(double dominanceWeightedReward, double totalPositivePleasure, int memoryCount)` record. `DescriptorView` gains nullable `@Nullable FormationPadSummary formationPadSummary` field.

- [ ] **Step 1: Write the failing test for FormationPadSummary**

```java
package io.casehub.neocortex.cognitive.index;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class FormationPadSummaryTest {

    @Test
    void rejectsNegativeMemoryCount() {
        assertThatThrownBy(() -> new FormationPadSummary(0.5, 1.0, -1))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void allowsZeroMemoryCount() {
        var summary = new FormationPadSummary(0.0, 0.0, 0);
        assertThat(summary.memoryCount()).isZero();
    }

    @Test
    void storesValues() {
        var summary = new FormationPadSummary(3.6, 4.0, 5);
        assertThat(summary.dominanceWeightedReward()).isEqualTo(3.6);
        assertThat(summary.totalPositivePleasure()).isEqualTo(4.0);
        assertThat(summary.memoryCount()).isEqualTo(5);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=FormationPadSummaryTest -DfailIfNoTests=false`
Expected: FAIL — class does not exist

- [ ] **Step 3: Implement FormationPadSummary**

Use `ide_create_file` or Write to create:

```java
package io.casehub.neocortex.cognitive.index;

public record FormationPadSummary(
    double dominanceWeightedReward,
    double totalPositivePleasure,
    int memoryCount
) {
    public FormationPadSummary {
        if (memoryCount < 0) {
            throw new IllegalArgumentException("memoryCount must be non-negative");
        }
    }
}
```

- [ ] **Step 4: Extend DescriptorView with FormationPadSummary**

Use `ide_replace_member` on the DescriptorView record. Add `@Nullable FormationPadSummary formationPadSummary` as the 5th field. Update the compact constructor to pass it through (it's nullable, no defensive copy needed).

New record signature:
```java
public record DescriptorView(
    String agentId,
    DispositionAxes disposition,
    List<WeightedTerm> dispositionProfile,
    List<String> goals,
    @Nullable FormationPadSummary formationPadSummary
)
```

Update compact constructor — keep existing null checks, add no check for formationPadSummary (nullable).

Add a backward-compatible factory for existing callers:
```java
public static DescriptorView of(String agentId, DispositionAxes disposition,
                                 List<WeightedTerm> dispositionProfile, List<String> goals) {
    return new DescriptorView(agentId, disposition, dispositionProfile, goals, null);
}
```

- [ ] **Step 5: Fix compilation — update all DescriptorView construction sites**

Use `ide_find_references` on `DescriptorView` constructor to find all call sites. Update each to use the new 5-arg constructor (passing `null` for formationPadSummary) or the `of()` factory. Run `ide_build_project` to verify.

- [ ] **Step 6: Run tests to verify everything passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add cognitive-index/
git commit -m "feat(#400): add FormationPadSummary and extend DescriptorView

Refs #400"
```

### Task 2: personalityDominance field on CognitiveDefaults + CDE 10th pathway

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEnginePersonalityDominanceTest.java`

**Interfaces:**
- Consumes: `FormationPadSummary` from Task 1, `DescriptorView.formationPadSummary()`
- Produces: `CognitiveDefaults.personalityDominance()` (Double, nullable), `CognitiveDefaults.withPersonalityDominance(Double)`, `CognitiveDerivationEngine.derivePersonalityDominance(FormationPadSummary)` static method

- [ ] **Step 1: Write the failing test for CDE personality dominance derivation**

```java
package io.casehub.neocortex.cognitive.index;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class CognitiveDerivationEnginePersonalityDominanceTest {

    @Test
    void hcPatternProducesHighDominance() {
        // HC: high pleasure + high dominance memories only
        var summary = new FormationPadSummary(
                0.9 * 0.8 + 0.9 * 0.7,  // dominanceWeightedReward = 1.35
                0.9 + 0.9,               // totalPositivePleasure = 1.8
                2
        );
        double result = CognitiveDerivationEngine.derivePersonalityDominance(summary);
        assertThat(result).isBetween(0.8, 0.95);
    }

    @Test
    void ppPatternProducesBalancedDominance() {
        // PP: mixed dominance — some positive, some negative
        var summary = new FormationPadSummary(
                0.8 * 0.7 + 0.6 * (-0.1) + 0.7 * 0.8 + 0.5 * (-0.2),  // = 0.56 - 0.06 + 0.56 - 0.1 = 0.96
                0.8 + 0.6 + 0.7 + 0.5,                                  // = 2.6
                4
        );
        double result = CognitiveDerivationEngine.derivePersonalityDominance(summary);
        assertThat(result).isBetween(0.45, 0.7);
    }

    @Test
    void nullSummaryReturnsDefault() {
        double result = CognitiveDerivationEngine.derivePersonalityDominance(null);
        assertThat(result).isEqualTo(0.5);
    }

    @Test
    void zeroMemoriesReturnsDefault() {
        var summary = new FormationPadSummary(0.0, 0.0, 0);
        double result = CognitiveDerivationEngine.derivePersonalityDominance(summary);
        assertThat(result).isEqualTo(0.5);
    }

    @Test
    void noPositivePleasureReturnsDefault() {
        var summary = new FormationPadSummary(-1.0, 0.0, 3);
        double result = CognitiveDerivationEngine.derivePersonalityDominance(summary);
        assertThat(result).isEqualTo(0.5);
    }

    @Test
    void extremeDominanceClampedToOne() {
        // All memories have max dominance
        var summary = new FormationPadSummary(1.0, 1.0, 1);
        double result = CognitiveDerivationEngine.derivePersonalityDominance(summary);
        assertThat(result).isEqualTo(1.0);
    }

    @Test
    void deriveIncludesPersonalityDominance() {
        var summary = new FormationPadSummary(1.35, 1.8, 2);
        var view = new DescriptorView("hc", null, java.util.List.of(), java.util.List.of(), summary);
        var defaults = CognitiveDerivationEngine.derive(view);
        assertThat(defaults.personalityDominance()).isNotNull();
        assertThat(defaults.personalityDominance()).isBetween(0.8, 0.95);
    }

    @Test
    void deriveAndMergePreservesExplicitPersonalityDominance() {
        var view = new DescriptorView("test", null, java.util.List.of(), java.util.List.of(),
                new FormationPadSummary(1.35, 1.8, 2));
        var explicit = CognitiveDefaults.empty("test")
                .withDescriptor(view)
                .withPersonalityDominance(0.3);
        var merged = CognitiveDerivationEngine.deriveAndMerge(explicit);
        assertThat(merged.personalityDominance()).isEqualTo(0.3);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveDerivationEnginePersonalityDominanceTest -DfailIfNoTests=false`
Expected: FAIL — method/field does not exist

- [ ] **Step 3: Add personalityDominance to CognitiveDefaults**

Add `@Nullable Double personalityDominance` as a new field on the `CognitiveDefaults` record (18th field, after `habituationConfig`). Add `withPersonalityDominance(Double)` wither method following the existing pattern. Update `empty()` to pass `null`. Update the constructor.

- [ ] **Step 4: Add derivePersonalityDominance to CDE**

Use `ide_insert_member` to add after `deriveHabituationConfig`:

```java
static double derivePersonalityDominance(@Nullable FormationPadSummary summary) {
    if (summary == null || summary.memoryCount() == 0 || summary.totalPositivePleasure() == 0.0) {
        return 0.5;
    }
    double ratio = summary.dominanceWeightedReward() / summary.totalPositivePleasure();
    return Math.clamp((ratio + 1.0) / 2.0, 0.0, 1.0);
}
```

- [ ] **Step 5: Wire into derive() and deriveAndMerge()**

In `derive()`, add after habituationConfig line:
```java
double personalityDominance = derivePersonalityDominance(descriptor.formationPadSummary());
```
And add `.withPersonalityDominance(personalityDominance)` to the builder chain.

In `deriveAndMerge()`, add the merge line following the existing pattern:
```java
.withPersonalityDominance(explicit.personalityDominance() != null ? explicit.personalityDominance() : derived.personalityDominance())
```

- [ ] **Step 6: Fix compilation across all modules**

Run `ide_build_project` to find any compilation failures from the CognitiveDefaults constructor change. Update YAML deserializers in `CognitiveDefaultsRegistry` if they construct CognitiveDefaults — the new field is nullable so YAML profiles that omit it will get null (which `deriveAndMerge` handles).

- [ ] **Step 7: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add cognitive-index/
git commit -m "feat(#400): add personalityDominance CDE derivation from formation memory PAD

10th CDE pathway: derives personality-cognition weight from dominance-
weighted reward ratio in formation memories.

Refs #400"
```

## Batch 2: Runtime — SectionTier enum + TierFilterCustomizer + CognitionCore wiring

### Task 3: SectionTier enum and TierFilterCustomizer

**Files:**
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/prompt/SectionTier.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/prompt/TierFilterCustomizer.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/prompt/TierFilterCustomizerTest.java`

**Interfaces:**
- Consumes: `MoodOrchestrator.currentMood(agentId, tenantId)` → `MoodState.arousal()`, `personalityDominance` double
- Produces: `SectionTier` enum (CORE, CONTEXTUAL, SUPPLEMENTARY), `TierFilterCustomizer implements UnaryOperator<List<CognitionPromptRenderer>>`

- [ ] **Step 1: Write the failing test for TierFilterCustomizer**

```java
package io.casehub.neocortex.cognition.prompt;

import io.casehub.neocortex.cognition.mood.MoodOrchestrator;
import io.casehub.neocortex.cognition.mood.MoodConfig;
import io.casehub.neocortex.memory.MoodState;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Optional;
import static org.assertj.core.api.Assertions.*;

class TierFilterCustomizerTest {

    @Test
    void lowArousalRendersAllTiers() {
        var customizer = createCustomizer(0.0, 0.5);  // arousal=0, scalar=0.5
        var sections = allSections();
        var result = customizer.apply(sections);
        assertThat(result).hasSize(sections.size());
    }

    @Test
    void highArousalSuppressesSupplementary() {
        // scalar=0.5 → suppThreshold=0.5, arousal=0.6 > 0.5
        var customizer = createCustomizer(0.6, 0.5);
        var sections = allSections();
        var result = customizer.apply(sections);
        assertThat(result).allSatisfy(s ->
            assertThat(TierFilterCustomizer.tierOf(s)).isNotEqualTo(SectionTier.SUPPLEMENTARY));
    }

    @Test
    void extremeArousalSuppressesContextualAndSupplementary() {
        // scalar=0.5 → ctxThreshold=0.8, arousal=0.9 > 0.8
        var customizer = createCustomizer(0.9, 0.5);
        var sections = allSections();
        var result = customizer.apply(sections);
        assertThat(result).allSatisfy(s ->
            assertThat(TierFilterCustomizer.tierOf(s)).isEqualTo(SectionTier.CORE));
    }

    @Test
    void personalityDominantAgentSuppressesSupplementaryEarly() {
        // HC: scalar=0.9 → suppThreshold=0.1, arousal=0.2 > 0.1
        var customizer = createCustomizer(0.2, 0.9);
        var sections = allSections();
        var result = customizer.apply(sections);
        assertThat(result).allSatisfy(s ->
            assertThat(TierFilterCustomizer.tierOf(s)).isNotEqualTo(SectionTier.SUPPLEMENTARY));
    }

    @Test
    void coreAlwaysRendersRegardlessOfArousal() {
        var customizer = createCustomizer(1.0, 1.0);  // max arousal, max dominance
        var sections = allSections();
        var result = customizer.apply(sections);
        assertThat(result).isNotEmpty();
        assertThat(result).allSatisfy(s ->
            assertThat(TierFilterCustomizer.tierOf(s)).isEqualTo(SectionTier.CORE));
    }

    @Test
    void noMoodDefaultsToZeroArousal() {
        // When MoodOrchestrator returns empty, all tiers render
        var customizer = createCustomizerNoMood(0.5);
        var sections = allSections();
        var result = customizer.apply(sections);
        assertThat(result).hasSize(sections.size());
    }

    // Helper to create customizer with a fixed arousal value
    private TierFilterCustomizer createCustomizer(double arousal, double personalityDominance) {
        return new TierFilterCustomizer(
                () -> arousal,
                personalityDominance
        );
    }

    private TierFilterCustomizer createCustomizerNoMood(double personalityDominance) {
        return new TierFilterCustomizer(
                () -> 0.0,
                personalityDominance
        );
    }

    private List<CognitionPromptRenderer> allSections() {
        return List.of(
            new MoodPromptSection(null),
            new DrivePromptSection(null),
            new UserModelPromptSection(null),
            new MentalModelPromptSection(null),
            new StrategyPromptSection(null),
            new EmergentGoalPromptSection(null)
        );
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=TierFilterCustomizerTest -DfailIfNoTests=false`
Expected: FAIL — classes do not exist

- [ ] **Step 3: Create SectionTier enum**

```java
package io.casehub.neocortex.cognition.prompt;

public enum SectionTier {
    CORE,
    CONTEXTUAL,
    SUPPLEMENTARY
}
```

- [ ] **Step 4: Implement TierFilterCustomizer**

```java
package io.casehub.neocortex.cognition.prompt;

import java.util.List;
import java.util.Map;
import java.util.function.DoubleSupplier;
import java.util.function.UnaryOperator;

public class TierFilterCustomizer implements UnaryOperator<List<CognitionPromptRenderer>> {

    private static final Map<Class<?>, SectionTier> TIER_MAP = Map.ofEntries(
        Map.entry(MoodPromptSection.class, SectionTier.CORE),
        Map.entry(DrivePromptSection.class, SectionTier.CORE),
        Map.entry(AppraisalPromptSection.class, SectionTier.CORE),
        Map.entry(BehavioralPromptSection.class, SectionTier.CORE),
        Map.entry(CharacterDrivePromptSection.class, SectionTier.CORE),
        Map.entry(NeedsPyramidPromptSection.class, SectionTier.CORE),
        Map.entry(UserModelPromptSection.class, SectionTier.CONTEXTUAL),
        Map.entry(MentalModelPromptSection.class, SectionTier.CONTEXTUAL),
        Map.entry(NarrativePromptSection.class, SectionTier.CONTEXTUAL),
        Map.entry(AttentionPromptSection.class, SectionTier.CONTEXTUAL),
        Map.entry(TemporalFocusPromptSection.class, SectionTier.CONTEXTUAL),
        Map.entry(StrategyPromptSection.class, SectionTier.SUPPLEMENTARY),
        Map.entry(EmergentGoalPromptSection.class, SectionTier.SUPPLEMENTARY),
        Map.entry(ReflectionPromptSection.class, SectionTier.SUPPLEMENTARY),
        Map.entry(ConsolidationPromptSection.class, SectionTier.SUPPLEMENTARY),
        Map.entry(ConstraintPromptSection.class, SectionTier.SUPPLEMENTARY)
    );

    private final DoubleSupplier arousalSupplier;
    private final double personalityDominance;

    public TierFilterCustomizer(DoubleSupplier arousalSupplier, double personalityDominance) {
        this.arousalSupplier = arousalSupplier;
        this.personalityDominance = personalityDominance;
    }

    @Override
    public List<CognitionPromptRenderer> apply(List<CognitionPromptRenderer> sections) {
        double arousal = arousalSupplier.getAsDouble();
        double suppThreshold = 1.0 - personalityDominance;
        double ctxThreshold  = Math.min(suppThreshold + 0.3, 1.0);

        return sections.stream()
                .filter(s -> {
                    var tier = tierOf(s);
                    return switch (tier) {
                        case CORE -> true;
                        case CONTEXTUAL -> arousal < ctxThreshold;
                        case SUPPLEMENTARY -> arousal < suppThreshold;
                    };
                })
                .toList();
    }

    public static SectionTier tierOf(CognitionPromptRenderer section) {
        var clazz = section instanceof DirectiveSection ds
                    ? ds.delegate().getClass()
                    : section.getClass();
        return TIER_MAP.getOrDefault(clazz, SectionTier.CORE);
    }
}
```

Note: `DirectiveSection` needs to expose a `delegate()` accessor for `tierOf()` to unwrap. Add a package-private `delegate()` method to DirectiveSection.

- [ ] **Step 5: Add delegate() accessor to DirectiveSection**

Use `ide_insert_member` on `DirectiveSection` to add:
```java
CognitionPromptRenderer delegate() {
    return delegate;
}
```

- [ ] **Step 6: Add test helper method in the test class**

Add a private `allSections()` helper in `TierFilterCustomizerTest` that constructs real section instances with null/stub orchestrators. `tierOf()` checks the class, not the render output, so null orchestrators are safe.

```java
private List<CognitionPromptRenderer> allSections() {
    return List.of(
        new MoodPromptSection(null),                    // Core
        new DrivePromptSection(null),                    // Core
        new UserModelPromptSection(null),                // Contextual
        new MentalModelPromptSection(null),              // Contextual
        new StrategyPromptSection(null),                 // Supplementary
        new EmergentGoalPromptSection(null)              // Supplementary
    );
}
```

Remove the `TierFilterCustomizer.createTestSections()` reference from the test.

- [ ] **Step 7: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=TierFilterCustomizerTest`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add cognition-api/ cognition/
git commit -m "feat(#400): add SectionTier enum and TierFilterCustomizer

Binary tier activation based on arousal thresholds derived from
personalityDominance scalar. Core always renders, Contextual and
Supplementary gated by arousal.

Refs #400"
```

### Task 4: CognitionCore wiring — configureTierFilter and agentId/tenantId storage

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/core/CognitionCoreTierFilterTest.java`

**Interfaces:**
- Consumes: `TierFilterCustomizer` from Task 3, `MoodOrchestrator.currentMood()`, `personalityDominance` from `CognitiveDefaults`
- Produces: `CognitionCore.configureTierFilter(double personalityDominance)` — registers the tier filter as a chained section customizer

- [ ] **Step 1: Write the failing test**

```java
package io.casehub.neocortex.cognition.core;

import io.casehub.neocortex.cognition.mood.MoodOrchestrator;
import io.casehub.neocortex.cognition.mood.MoodConfig;
import io.casehub.neocortex.cognition.prompt.SectionTier;
import io.casehub.neocortex.cognition.prompt.TierFilterCustomizer;
import io.casehub.neocortex.memory.MoodState;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class CognitionCoreTierFilterTest {

    @Test
    void configureTierFilterSuppressesSupplementaryUnderHighArousal() {
        var config = CognitionConfig.all();
        var moodConfig = new MoodConfig(0.1, 1.0, 0.5, java.time.Duration.ofMinutes(5));
        var mood = new MoodOrchestrator(moodConfig);
        var core = new CognitionCore(mood,
                /* drives */ null, /* userModel */ null, /* mentalModel */ null,
                /* strategy */ null, /* narrative */ null, /* goals */ null,
                /* memoryHygiene */ null);

        // Configure tier filter with HC-like dominance
        core.configureTierFilter(0.9);

        // Record high arousal mood
        mood.record(new io.casehub.neocortex.cognition.mood.MoodSignal(0.0, 0.5, 0.0), "agent1", "tenant1");
        mood.tick("agent1", "tenant1");

        // Tick cognition to store agentId/tenantId
        core.tick("agent1", "tenant1", null, (a, t) -> java.util.List.of());

        var sections = core.promptSections();
        // With scalar=0.9, suppThreshold=0.1, arousal=0.5 > 0.1
        // Supplementary should be suppressed
        assertThat(sections).allSatisfy(s ->
            assertThat(TierFilterCustomizer.tierOf(s)).isNotEqualTo(SectionTier.SUPPLEMENTARY));
    }

    @Test
    void noTierFilterRendersAllSections() {
        var config = CognitionConfig.all();
        var moodConfig = new MoodConfig(0.1, 1.0, 0.5, java.time.Duration.ofMinutes(5));
        var mood = new MoodOrchestrator(moodConfig);
        var core = new CognitionCore(mood,
                /* drives */ null, /* userModel */ null, /* mentalModel */ null,
                /* strategy */ null, /* narrative */ null, /* goals */ null,
                /* memoryHygiene */ null);

        core.tick("agent1", "tenant1", null, (a, t) -> java.util.List.of());

        var sections = core.promptSections();
        // Mood and drives are always added (config.all() enables them)
        assertThat(sections).isNotEmpty();
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=CognitionCoreTierFilterTest -DfailIfNoTests=false`
Expected: FAIL — `configureTierFilter` does not exist

- [ ] **Step 3: Add agentId/tenantId storage to CognitionCore**

Add two volatile fields to CognitionCore:
```java
private volatile @Nullable String lastAgentId;
private volatile @Nullable String lastTenantId;
```

In `tick()`, store them at the start:
```java
this.lastAgentId = agentId;
this.lastTenantId = tenantId;
```

- [ ] **Step 4: Add configureTierFilter method**

Use `ide_insert_member` on CognitionCore after `configureDriveGoalBridge`:

```java
public void configureTierFilter(double personalityDominance) {
    chainSectionCustomizer(new TierFilterCustomizer(
            () -> {
                String aid = lastAgentId;
                String tid = lastTenantId;
                if (aid == null || tid == null) return 0.0;
                return mood.currentMood(aid, tid)
                           .map(MoodState::arousal)
                           .orElse(0.0);
            },
            personalityDominance
    ));
}
```

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=CognitionCoreTierFilterTest`
Expected: PASS

- [ ] **Step 6: Run full cognition module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: PASS — no regressions

- [ ] **Step 7: Commit**

```bash
git add cognition/
git commit -m "feat(#400): wire TierFilterCustomizer into CognitionCore

configureTierFilter() registers arousal-gated tier filtering via
the existing sectionCustomizer chain. Captures agentId/tenantId
from last tick() for mood lookup.

Refs #400"
```

## Batch 3: Validation — contract tests + CognitiveDerivationEngine test update

### Task 5: Update existing CDE tests and add integration assertion

**Files:**
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngineTest.java`

**Interfaces:**
- Consumes: All types from Tasks 1-2
- Produces: Updated test suite verifying that the existing 10 pathways still pass and the new personalityDominance field integrates correctly

- [ ] **Step 1: Check existing CDE tests still compile and pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveDerivationEngineTest`
Expected: PASS (constructor changes may require fixes)

- [ ] **Step 2: Fix any compilation issues from DescriptorView/CognitiveDefaults changes**

Update test DescriptorView construction sites to use the new 5-arg constructor or `of()` factory. Update any CognitiveDefaults assertions that check field count or constructor args.

- [ ] **Step 3: Add integration test for full derive() with FormationPadSummary**

Add to `CognitiveDerivationEngineTest`:

```java
@Test
void deriveWithFormationPadSummaryProducesPersonalityDominance() {
    var summary = new FormationPadSummary(1.35, 1.8, 2);
    var view = new DescriptorView("test-agent", testDisposition(),
            testProfile(), List.of("explore"), summary);
    var defaults = CognitiveDerivationEngine.derive(view);
    assertThat(defaults.personalityDominance()).isNotNull();
    assertThat(defaults.personalityDominance()).isBetween(0.0, 1.0);
}

@Test
void deriveWithoutFormationPadSummaryDefaultsToHalf() {
    var view = DescriptorView.of("test-agent", testDisposition(),
            testProfile(), List.of("explore"));
    var defaults = CognitiveDerivationEngine.derive(view);
    assertThat(defaults.personalityDominance()).isEqualTo(0.5);
}
```

- [ ] **Step 4: Run full test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cognitive-index/
git commit -m "test(#400): update CDE tests for personalityDominance pathway

Refs #400"
```

### Task 6: Full build verification

**Files:**
- No new files

- [ ] **Step 1: Run full project build with tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS — all modules compile and tests pass

- [ ] **Step 2: Fix any remaining compilation or test failures**

Use `ide_diagnostics` to identify issues. Fix them.

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix(#400): resolve compilation issues from tier filter wiring

Refs #400"
```

## References

- [2026-10-07-cognitive-section-calibration-design.md] — design spec this plan implements
- [cognitive-index/.../CognitiveDerivationEngine.java:141-188] — existing derive() and deriveAndMerge() methods
- [cognitive-index/.../CognitiveDefaults.java:31-125] — existing record with 17 fields and wither pattern
- [cognitive-index/.../DescriptorView.java:21-32] — existing 4-field record
- [cognition/.../CognitionCore.java:466-537] — promptSections() method and sectionCustomizer chain
- [cognition/.../DirectiveSection.java] — directive wrapping that needs delegate() accessor
- [cognition/.../MoodOrchestrator.java:55-59] — currentMood() accessor for arousal
- [GitHub #400] — focal issue
- [casehubio/examples#97] — Phase 4 calibration experiments (downstream validation)

# Cross-Store Retrieval Modulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #233 — feat: cross-store retrieval modulation — generic RetrievalModulator for mood, personality, trust
**Issue group:** #253, #233

**Goal:** Replace Memory-only MoodModulatedRetrieval and PersonalityWeightedRetrieval with a generic, composable modulation framework that works across Memory, MindMapNode, and (optionally) CBR result types.

**Architecture:** Three framework types in cognitive-api (zero deps): ModulationProfile<T> (accessor record), ModulationFactor<T> (@FunctionalInterface multiplier), RetrievalModulator (static utility). Pre-built profiles and factor factories in cognitive-index. Factors compose via multiplication. Post-retrieval only — CBR decorators unchanged.

**Tech Stack:** Java 21, pure utility classes (no CDI, no Quarkus)

## Global Constraints

- Java 21 source level (on Java 26 JVM): `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn`
- cognitive-api is tier-0, zero runtime deps
- cognitive-index depends on memory-api, mindmap-api, cognitive-api
- Package: `io.casehub.neocortex.cognitive` (framework), `io.casehub.neocortex.cognitive.index` (instances)
- Use `mvn` not `./mvnw`
- No CDI annotations — all types are pure Java utilities

---

## Batch 1: Framework types in cognitive-api

### Task 1: ModulationProfile, ModulationFactor, RetrievalModulator + framework tests

**Files:**
- Create: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/ModulationProfile.java`
- Create: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/ModulationFactor.java`
- Create: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/RetrievalModulator.java`
- Test: `cognitive-api/src/test/java/io/casehub/neocortex/cognitive/RetrievalModulatorTest.java`

**Interfaces:**
- Consumes: `Confidence` from cognitive-api (already exists)
- Produces: `ModulationProfile<T>` record, `ModulationFactor<T>` @FunctionalInterface, `RetrievalModulator.modulate()` static method

- [ ] **Step 1: Write framework tests**

Create `cognitive-api/src/test/java/io/casehub/neocortex/cognitive/RetrievalModulatorTest.java`:

```java
package io.casehub.neocortex.cognitive;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.function.Function;

import static org.assertj.core.api.Assertions.assertThat;

class RetrievalModulatorTest {

    private static final ModulationProfile<TestItem> PROFILE = new ModulationProfile<>(
        TestItem::confidence,
        TestItem::pleasure,
        TestItem::arousal,
        TestItem::dominance,
        TestItem::timestamp
    );

    @Test
    void emptyListReturnsEmpty() {
        List<TestItem> result = RetrievalModulator.modulate(
            List.of(), PROFILE, List.of((item, profile) -> 1.0));
        assertThat(result).isEmpty();
    }

    @Test
    void singleFactorSortsByThatFactor() {
        var a = new TestItem("a", 0.9, null, null, null, Instant.now());
        var b = new TestItem("b", 0.1, null, null, null, Instant.now());
        var c = new TestItem("c", 0.5, null, null, null, Instant.now());

        ModulationFactor<TestItem> byConfidence =
            (item, profile) -> {
                Confidence conf = profile.confidence().apply(item);
                return conf != null ? conf.value() : 1.0;
            };

        var result = RetrievalModulator.modulate(List.of(b, c, a), PROFILE, List.of(byConfidence));
        assertThat(result).extracting(TestItem::name).containsExactly("a", "c", "b");
    }

    @Test
    void compositeScoreMultipliesFactors() {
        var high = new TestItem("high", 0.9, null, null, null, Instant.now());
        var low = new TestItem("low", 0.1, null, null, null, Instant.now());

        ModulationFactor<TestItem> factor1 = (item, profile) -> {
            Confidence conf = profile.confidence().apply(item);
            return conf != null ? conf.value() : 1.0;
        };
        ModulationFactor<TestItem> factor2 = (item, profile) -> 2.0;

        var result = RetrievalModulator.modulate(
            List.of(low, high), PROFILE, List.of(factor1, factor2));
        assertThat(result).extracting(TestItem::name).containsExactly("high", "low");
    }

    @Test
    void neutralFactorPreservesOrdering() {
        var a = new TestItem("a", 0.9, null, null, null, Instant.now());
        var b = new TestItem("b", 0.1, null, null, null, Instant.now());

        ModulationFactor<TestItem> scoring =
            (item, profile) -> profile.confidence().apply(item).value();
        ModulationFactor<TestItem> neutral = (item, profile) -> 1.0;

        var withNeutral = RetrievalModulator.modulate(
            List.of(b, a), PROFILE, List.of(scoring, neutral));
        var without = RetrievalModulator.modulate(
            List.of(b, a), PROFILE, List.of(scoring));
        assertThat(withNeutral).extracting(TestItem::name)
            .isEqualTo(without.stream().map(TestItem::name).toList());
    }

    record TestItem(String name, double confValue, Double pleasure,
                    Double arousal, Double dominance, Instant timestamp) {
        Confidence confidence() {
            return Confidence.unknown(confValue);
        }
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: compilation failure — ModulationProfile, ModulationFactor, RetrievalModulator not yet created.

- [ ] **Step 3: Implement ModulationProfile**

Create `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/ModulationProfile.java`:

```java
package io.casehub.neocortex.cognitive;

import java.time.Instant;
import java.util.function.Function;

public record ModulationProfile<T>(
    Function<T, Confidence> confidence,
    Function<T, Double> pleasure,
    Function<T, Double> arousal,
    Function<T, Double> dominance,
    Function<T, Instant> timestamp
) {}
```

- [ ] **Step 4: Implement ModulationFactor**

Create `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/ModulationFactor.java`:

```java
package io.casehub.neocortex.cognitive;

@FunctionalInterface
public interface ModulationFactor<T> {
    double apply(T item, ModulationProfile<T> profile);
}
```

- [ ] **Step 5: Implement RetrievalModulator**

Create `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/RetrievalModulator.java`:

```java
package io.casehub.neocortex.cognitive;

import java.util.Comparator;
import java.util.List;

public final class RetrievalModulator {

    private RetrievalModulator() {}

    public static <T> List<T> modulate(List<T> items, ModulationProfile<T> profile,
            List<ModulationFactor<T>> factors) {
        if (items.isEmpty() || factors.isEmpty()) return items;
        return items.stream()
            .sorted(Comparator.comparingDouble(
                (T item) -> compositeScore(item, profile, factors)).reversed())
            .toList();
    }

    private static <T> double compositeScore(T item, ModulationProfile<T> profile,
            List<ModulationFactor<T>> factors) {
        double score = 1.0;
        for (var factor : factors) {
            score *= factor.apply(item, profile);
        }
        return score;
    }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: 4 new tests PASS (plus existing cognitive-api tests).

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add cognitive-api/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(cognitive-api): ModulationProfile, ModulationFactor, RetrievalModulator Refs #233"
```

---

## Batch 2: Pre-built factors, profiles, cleanup

### Task 2: ModulationFactors, ModulationProfiles, ModulationContext + factor/profile/integration tests

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/ModulationContext.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/ModulationProfiles.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/ModulationFactors.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/ModulationFactorsTest.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/ModulationProfilesTest.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/ModulationIntegrationTest.java`

**Interfaces:**
- Consumes: `ModulationProfile<T>`, `ModulationFactor<T>`, `RetrievalModulator` from Task 1
- Consumes: `Memory` from memory-api, `MindMapNode` from mindmap-api
- Consumes: `MoodState`, `PersonalityWeights`, `MoodAttributeKeys` from memory-api
- Produces: `ModulationProfiles.MEMORY`, `ModulationProfiles.NODE` constants
- Produces: `ModulationFactors.recencyDecay()`, `.confidenceWeight()`, `.moodCongruence()`, `.domainWeight()` factories
- Produces: `ModulationContext` convenience record

- [ ] **Step 1: Write factor tests**

Create `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/ModulationFactorsTest.java`:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ModulationFactor;
import io.casehub.neocortex.cognitive.ModulationProfile;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.mood.MoodState;
import io.casehub.neocortex.memory.personality.PersonalityWeights;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class ModulationFactorsTest {

    private static final Instant NOW = Instant.parse("2026-06-01T12:00:00Z");

    private static final ModulationProfile<TestItem> PROFILE = new ModulationProfile<>(
        TestItem::confidence,
        TestItem::pleasure,
        TestItem::arousal,
        TestItem::dominance,
        TestItem::timestamp
    );

    @Test
    void recencyDecayRecentHigherThanOld() {
        var recent = new TestItem(Confidence.unknown(1.0), null, null, null,
            NOW.minus(1, ChronoUnit.HOURS));
        var old = new TestItem(Confidence.unknown(1.0), null, null, null,
            NOW.minus(72, ChronoUnit.HOURS));

        ModulationFactor<TestItem> factor =
            ModulationFactors.recencyDecay(Duration.ofDays(7), NOW);

        assertThat(factor.apply(recent, PROFILE))
            .isGreaterThan(factor.apply(old, PROFILE));
    }

    @Test
    void recencyDecayNullTimestampReturnsHalf() {
        var item = new TestItem(Confidence.unknown(1.0), null, null, null, null);
        ModulationFactor<TestItem> factor =
            ModulationFactors.recencyDecay(Duration.ofDays(7), NOW);
        assertThat(factor.apply(item, PROFILE)).isEqualTo(0.5);
    }

    @Test
    void confidenceWeightHigherConfidenceScoresHigher() {
        var high = new TestItem(Confidence.unknown(0.9), null, null, null, NOW);
        var low = new TestItem(Confidence.unknown(0.2), null, null, null, NOW);
        ModulationFactor<TestItem> factor = ModulationFactors.confidenceWeight();
        assertThat(factor.apply(high, PROFILE))
            .isGreaterThan(factor.apply(low, PROFILE));
    }

    @Test
    void confidenceWeightNullConfidenceReturnsOne() {
        var item = new TestItem(null, null, null, null, NOW);
        ModulationFactor<TestItem> factor = ModulationFactors.confidenceWeight();
        assertThat(factor.apply(item, PROFILE)).isEqualTo(1.0);
    }

    @Test
    void moodCongruenceAlignedItemsScoreHigher() {
        var aligned = new TestItem(Confidence.unknown(1.0), 0.8, 0.5, 0.3, NOW);
        var misaligned = new TestItem(Confidence.unknown(1.0), -0.8, -0.5, -0.3, NOW);
        MoodState mood = new MoodState(0.8, 0.5, 0.3);

        ModulationFactor<TestItem> factor =
            ModulationFactors.moodCongruence(mood, 0.8);

        assertThat(factor.apply(aligned, PROFILE))
            .isGreaterThan(factor.apply(misaligned, PROFILE));
    }

    @Test
    void moodCongruenceNoPadReturnsOne() {
        var item = new TestItem(Confidence.unknown(1.0), null, null, null, NOW);
        MoodState mood = new MoodState(0.5, 0.5, 0.5);
        ModulationFactor<TestItem> factor =
            ModulationFactors.moodCongruence(mood, 0.8);
        assertThat(factor.apply(item, PROFILE)).isEqualTo(1.0);
    }

    @Test
    void moodCongruenceZeroInfluenceReturnsOne() {
        var item = new TestItem(Confidence.unknown(1.0), 0.5, 0.5, 0.5, NOW);
        MoodState mood = new MoodState(-0.5, -0.5, -0.5);
        ModulationFactor<TestItem> factor =
            ModulationFactors.moodCongruence(mood, 0.0);
        assertThat(factor.apply(item, PROFILE)).isEqualTo(1.0);
    }

    @Test
    void domainWeightWeightedDomainScoresHigher() {
        var experience = memory(MemoryDomain.EXPERIENCE);
        var reflection = memory(MemoryDomain.REFLECTION);
        PersonalityWeights weights = new PersonalityWeights(
            Map.of(MemoryDomain.EXPERIENCE, 3.0));
        ModulationFactor<Memory> factor =
            ModulationFactors.domainWeight(weights);
        assertThat(factor.apply(experience, ModulationProfiles.MEMORY))
            .isGreaterThan(factor.apply(reflection, ModulationProfiles.MEMORY));
    }

    @Test
    void domainWeightUnweightedDefaultsToOne() {
        var item = memory(MemoryDomain.OBSERVATION);
        PersonalityWeights weights = new PersonalityWeights(
            Map.of(MemoryDomain.EXPERIENCE, 2.0));
        ModulationFactor<Memory> factor =
            ModulationFactors.domainWeight(weights);
        assertThat(factor.apply(item, ModulationProfiles.MEMORY)).isEqualTo(1.0);
    }

    private static Memory memory(MemoryDomain domain) {
        return new Memory("m1", "e1", domain, "t1", null, "text",
            Map.of(), NOW, Confidence.unknown(1.0), null, null, null);
    }

    record TestItem(Confidence confidence, Double pleasure,
                    Double arousal, Double dominance, Instant timestamp) {}
}
```

- [ ] **Step 2: Write profile tests**

Create `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/ModulationProfilesTest.java`:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.mindmap.MindMapNode;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class ModulationProfilesTest {

    private static final Instant NOW = Instant.parse("2026-06-01T12:00:00Z");

    @Test
    void memoryProfileExtractsCorrectly() {
        var profile = ModulationProfiles.MEMORY;
        Memory m = new Memory("m1", "e1", MemoryDomain.EXPERIENCE, "t1", null,
            "text", Map.of(), NOW, Confidence.unknown(0.7), 0.5, 0.3, -0.1);
        assertThat(profile.confidence().apply(m).value()).isEqualTo(0.7);
        assertThat(profile.pleasure().apply(m)).isEqualTo(0.5);
        assertThat(profile.arousal().apply(m)).isEqualTo(0.3);
        assertThat(profile.dominance().apply(m)).isEqualTo(-0.1);
        assertThat(profile.timestamp().apply(m)).isEqualTo(NOW);
    }

    @Test
    void nodeProfileExtractsCorrectly() {
        var profile = ModulationProfiles.NODE;
        MindMapNode node = new StubNode("n1", "Test", Confidence.unknown(0.8),
            NOW, 0.4, -0.2, 0.6);
        assertThat(profile.confidence().apply(node).value()).isEqualTo(0.8);
        assertThat(profile.pleasure().apply(node)).isEqualTo(0.4);
        assertThat(profile.arousal().apply(node)).isEqualTo(-0.2);
        assertThat(profile.dominance().apply(node)).isEqualTo(0.6);
        assertThat(profile.timestamp().apply(node)).isEqualTo(NOW);
    }
}
```

Note: `StubNode` already exists at `cognitive-index/src/test/java/.../StubNode.java` — reuse it.

- [ ] **Step 3: Write integration test**

Create `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/ModulationIntegrationTest.java`:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ModulationFactor;
import io.casehub.neocortex.cognitive.RetrievalModulator;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.mood.MoodState;
import io.casehub.neocortex.memory.personality.PersonalityWeights;
import io.casehub.neocortex.mindmap.MindMapNode;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class ModulationIntegrationTest {

    private static final Instant NOW = Instant.parse("2026-06-01T12:00:00Z");

    @Test
    void fullMemoryPipelineRanksCorrectly() {
        MoodState mood = new MoodState(0.7, 0.3, 0.5);
        PersonalityWeights weights = new PersonalityWeights(
            Map.of(MemoryDomain.EXPERIENCE, 2.0));

        Memory recentAligned = new Memory("m1", "e1", MemoryDomain.EXPERIENCE,
            "t1", null, "recent+aligned", Map.of(),
            NOW.minus(1, ChronoUnit.HOURS), Confidence.unknown(0.9),
            0.7, 0.3, 0.5);

        Memory oldMisaligned = new Memory("m2", "e1", MemoryDomain.REFLECTION,
            "t1", null, "old+misaligned", Map.of(),
            NOW.minus(72, ChronoUnit.HOURS), Confidence.unknown(0.3),
            -0.7, -0.3, -0.5);

        List<ModulationFactor<Memory>> factors = List.of(
            ModulationFactors.recencyDecay(Duration.ofDays(7), NOW),
            ModulationFactors.confidenceWeight(),
            ModulationFactors.moodCongruence(mood, 0.6),
            ModulationFactors.domainWeight(weights)
        );

        var result = RetrievalModulator.modulate(
            List.of(oldMisaligned, recentAligned),
            ModulationProfiles.MEMORY, factors);

        assertThat(result).extracting(Memory::text)
            .containsExactly("recent+aligned", "old+misaligned");
    }

    @Test
    void nodeModulationWithoutDomainWeight() {
        MoodState mood = new MoodState(0.5, 0.5, 0.5);

        MindMapNode aligned = new StubNode("n1", "Aligned",
            Confidence.unknown(0.9), NOW.minus(1, ChronoUnit.HOURS),
            0.5, 0.5, 0.5);
        MindMapNode misaligned = new StubNode("n2", "Misaligned",
            Confidence.unknown(0.3), NOW.minus(48, ChronoUnit.HOURS),
            -0.5, -0.5, -0.5);

        List<ModulationFactor<MindMapNode>> factors = List.of(
            ModulationFactors.recencyDecay(Duration.ofDays(7), NOW),
            ModulationFactors.confidenceWeight(),
            ModulationFactors.moodCongruence(mood, 0.6)
        );

        var result = RetrievalModulator.modulate(
            List.of(misaligned, aligned),
            ModulationProfiles.NODE, factors);

        assertThat(result).extracting(MindMapNode::name)
            .containsExactly("Aligned", "Misaligned");
    }
}
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: compilation failure — ModulationFactors, ModulationProfiles, ModulationContext not yet created.

- [ ] **Step 5: Implement ModulationContext**

Create `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/ModulationContext.java`:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.memory.mood.MoodState;
import io.casehub.neocortex.memory.personality.PersonalityWeights;

import java.time.Instant;
import java.util.Objects;

public record ModulationContext(
    MoodState currentMood,
    PersonalityWeights personality,
    Instant now
) {
    public ModulationContext {
        Objects.requireNonNull(now, "now");
    }

    public static ModulationContext of(Instant now) {
        return new ModulationContext(null, null, now);
    }

    public ModulationContext withMood(MoodState mood) {
        return new ModulationContext(mood, personality, now);
    }

    public ModulationContext withPersonality(PersonalityWeights weights) {
        return new ModulationContext(currentMood, weights, now);
    }
}
```

- [ ] **Step 6: Implement ModulationProfiles**

Create `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/ModulationProfiles.java`:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.ModulationProfile;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.mindmap.MindMapNode;

public final class ModulationProfiles {

    private ModulationProfiles() {}

    public static final ModulationProfile<Memory> MEMORY = new ModulationProfile<>(
        Memory::confidence,
        Memory::pleasure,
        Memory::arousal,
        Memory::dominance,
        Memory::createdAt
    );

    public static final ModulationProfile<MindMapNode> NODE = new ModulationProfile<>(
        MindMapNode::confidence,
        MindMapNode::pleasure,
        MindMapNode::arousal,
        MindMapNode::dominance,
        MindMapNode::createdAt
    );
}
```

- [ ] **Step 7: Implement ModulationFactors**

Create `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/ModulationFactors.java`:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ModulationFactor;
import io.casehub.neocortex.cognitive.ModulationProfile;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.mood.MoodState;
import io.casehub.neocortex.memory.personality.PersonalityWeights;

import java.time.Duration;
import java.time.Instant;

public final class ModulationFactors {

    private static final double MAX_PAD_DISTANCE = Math.sqrt(12.0);

    private ModulationFactors() {}

    public static <T> ModulationFactor<T> recencyDecay(Duration halfLife, Instant now) {
        double halfLifeHours = halfLife.toHours();
        return (item, profile) -> {
            Instant ts = profile.timestamp().apply(item);
            if (ts == null) return 0.5;
            double hoursElapsed = Duration.between(ts, now).toMillis() / 3_600_000.0;
            if (hoursElapsed < 0) hoursElapsed = 0;
            return Math.exp(-hoursElapsed / halfLifeHours);
        };
    }

    public static <T> ModulationFactor<T> confidenceWeight() {
        return (item, profile) -> {
            Confidence conf = profile.confidence().apply(item);
            return conf != null ? conf.value() : 1.0;
        };
    }

    public static <T> ModulationFactor<T> moodCongruence(MoodState mood, double influence) {
        if (influence < 0.0 || influence > 1.0)
            throw new IllegalArgumentException("influence must be in [0, 1], got " + influence);
        if (influence == 0.0) return (item, profile) -> 1.0;
        return (item, profile) -> {
            Double p = profile.pleasure().apply(item);
            Double a = profile.arousal().apply(item);
            Double d = profile.dominance().apply(item);
            if (p == null && a == null && d == null) return 1.0;
            double mp = p != null ? p : 0.0;
            double ma = a != null ? a : 0.0;
            double md = d != null ? d : 0.0;
            double dp = mood.pleasure() - mp;
            double da = mood.arousal() - ma;
            double dd = mood.dominance() - md;
            double distance = Math.sqrt(dp * dp + da * da + dd * dd);
            double alignment = 1.0 - distance / MAX_PAD_DISTANCE;
            return 1.0 + influence * (alignment - 0.5);
        };
    }

    public static ModulationFactor<Memory> domainWeight(PersonalityWeights weights) {
        return (item, profile) -> weights.getWeight(item.domain());
    }
}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -pl cognitive-api,cognitive-index -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: 9 factor tests + 2 profile tests + 2 integration tests = 13 new tests PASS (plus existing cognitive-index tests).

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add cognitive-index/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(cognitive-index): ModulationFactors, ModulationProfiles, ModulationContext Refs #233"
```

### Task 3: Delete old utilities + CLAUDE.md update

**Files:**
- Delete: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodModulatedRetrieval.java` (use `ide_refactor_safe_delete`)
- Delete: `memory-api/src/test/java/io/casehub/neocortex/memory/mood/MoodModulatedRetrievalTest.java` (use `ide_refactor_safe_delete`)
- Delete: `memory-api/src/main/java/io/casehub/neocortex/memory/personality/PersonalityWeightedRetrieval.java` (use `ide_refactor_safe_delete`)
- Delete: `memory-api/src/test/java/io/casehub/neocortex/memory/personality/PersonalityWeightedRetrievalTest.java` (use `ide_refactor_safe_delete`)
- Modify: `CLAUDE.md` — update cognitive-api, cognitive-index, and memory-api descriptions

**Interfaces:**
- Consumes: confirmation from Task 2 that the new modulation framework is complete and tested
- Produces: clean removal of old utilities

- [ ] **Step 1: Safe-delete MoodModulatedRetrieval**

Use `ide_refactor_safe_delete` on:
- `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodModulatedRetrieval.java`
- `memory-api/src/test/java/io/casehub/neocortex/memory/mood/MoodModulatedRetrievalTest.java`

- [ ] **Step 2: Safe-delete PersonalityWeightedRetrieval**

Use `ide_refactor_safe_delete` on:
- `memory-api/src/main/java/io/casehub/neocortex/memory/personality/PersonalityWeightedRetrieval.java`
- `memory-api/src/test/java/io/casehub/neocortex/memory/personality/PersonalityWeightedRetrievalTest.java`

- [ ] **Step 3: Run memory-api tests to verify nothing broke**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: all remaining memory-api tests PASS. The deleted tests are gone; no other tests reference the deleted classes.

- [ ] **Step 4: Update CLAUDE.md**

Update the cognitive-api description to include: `ModulationProfile (accessor record for generic field extraction), ModulationFactor (@FunctionalInterface — composable scoring multiplier), RetrievalModulator (static utility: applies factors, sorts by composite score)`.

Update the cognitive-index description to include: `ModulationContext (convenience record: MoodState + PersonalityWeights + Instant), ModulationProfiles (pre-built: MEMORY, NODE), ModulationFactors (factories: recencyDecay, confidenceWeight, moodCongruence, domainWeight)`.

Remove `MoodModulatedRetrieval` and `PersonalityWeightedRetrieval` references from the memory-api description.

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/ CLAUDE.md
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "refactor: replace MoodModulatedRetrieval + PersonalityWeightedRetrieval with RetrievalModulator Refs #233"
```

---

## References

- `specs/issue-253-cognitive-rearchitecture/2026-08-31-retrieval-modulation-design.md` — design spec
- `memory-api/.../MoodModulatedRetrieval.java` — existing utility (deleted)
- `memory-api/.../PersonalityWeightedRetrieval.java` — existing utility (deleted)
- `cognitive-api/.../Confidence.java` — shared confidence type
- `cognitive-index/.../StubNode.java` — existing test stub for MindMapNode
- `memory-api/.../Memory.java` — Memory record
- `mindmap-api/.../MindMapNode.java` — MindMapNode interface
- `memory-api/.../MoodState.java` — mood PAD type
- `memory-api/.../PersonalityWeights.java` — domain weights type
- GitHub #233 — focal issue
- GitHub #253 — parent branch issue

# Mood + Engagement Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #207 — MoodState type + mood-modulated retrieval decorator
**Issue group:** #207, #208

**Goal:** Add MoodState (PAD model), mood-modulated retrieval, and conversational engagement scoring as foundation types in memory-api, with CDI wiring in the memory module.

**Architecture:** All new types are pure Java records/utilities in memory-api with zero dependencies. They follow the established domain event pattern (RelationshipEvent, ExperienceEvent) — standalone typed events with their own converter, attribute keys, and MemoryDomain. CDI integration (EngagementStream, EngagementRecorded) lives in the memory runtime module, following ExperienceStream.

**Tech Stack:** Java 21, JUnit 5, memory-api (pure Java), memory (Quarkus CDI)

## Global Constraints

- Java 21 language level (running on Java 26 JVM)
- Build with: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- All new types in memory-api are pure Java with zero dependencies
- CDI types in the memory module use Jakarta CDI annotations
- Follow existing record validation patterns (see RelationshipEvent, ExperienceEvent)
- Existing sealed hierarchies (ExperienceEvent) are NOT modified
- Use `ide_insert_member` for new methods, `ide_replace_member` for modifying existing ones

---

## Batch 1: MoodState Core Types (memory-api)

### Task 1: MoodState record and MoodAttributeKeys

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodState.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodAttributeKeys.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/mood/MoodStateTest.java`

**Interfaces:**
- Consumes: nothing
- Produces: `MoodState(String agentId, String tenantId, double pleasure, double arousal, double dominance, String cause, String turnId, Map<String, String> metadata)` record; `MoodAttributeKeys.PLEASURE`, `.AROUSAL`, `.DOMINANCE`, `.TURN_ID` constants

- [ ] **Step 1: Write MoodStateTest**

```java
package io.casehub.neocortex.memory.mood;

import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class MoodStateTest {

    @Test
    void requiresAgentId() {
        assertThrows(NullPointerException.class, () ->
            new MoodState(null, "t1", 0.0, 0.0, 0.0, "init", null, Map.of()));
    }

    @Test
    void requiresTenantId() {
        assertThrows(NullPointerException.class, () ->
            new MoodState("a1", null, 0.0, 0.0, 0.0, "init", null, Map.of()));
    }

    @Test
    void requiresCause() {
        assertThrows(NullPointerException.class, () ->
            new MoodState("a1", "t1", 0.0, 0.0, 0.0, null, null, Map.of()));
    }

    @Test
    void rejectsBlankCause() {
        assertThrows(IllegalArgumentException.class, () ->
            new MoodState("a1", "t1", 0.0, 0.0, 0.0, "  ", null, Map.of()));
    }

    @Test
    void rejectsPleasureOutOfBounds() {
        assertThrows(IllegalArgumentException.class, () ->
            new MoodState("a1", "t1", 1.1, 0.0, 0.0, "init", null, Map.of()));
        assertThrows(IllegalArgumentException.class, () ->
            new MoodState("a1", "t1", -1.1, 0.0, 0.0, "init", null, Map.of()));
    }

    @Test
    void rejectsArousalOutOfBounds() {
        assertThrows(IllegalArgumentException.class, () ->
            new MoodState("a1", "t1", 0.0, 1.1, 0.0, "init", null, Map.of()));
        assertThrows(IllegalArgumentException.class, () ->
            new MoodState("a1", "t1", 0.0, -1.1, 0.0, "init", null, Map.of()));
    }

    @Test
    void rejectsDominanceOutOfBounds() {
        assertThrows(IllegalArgumentException.class, () ->
            new MoodState("a1", "t1", 0.0, 0.0, 1.1, "init", null, Map.of()));
        assertThrows(IllegalArgumentException.class, () ->
            new MoodState("a1", "t1", 0.0, 0.0, -1.1, "init", null, Map.of()));
    }

    @Test
    void acceptsBoundaryValues() {
        var state = new MoodState("a1", "t1", 1.0, -1.0, 0.5, "event", "turn-1", Map.of());
        assertEquals(1.0, state.pleasure());
        assertEquals(-1.0, state.arousal());
        assertEquals(0.5, state.dominance());
    }

    @Test
    void acceptsNullOptionalFields() {
        var state = new MoodState("a1", "t1", 0.0, 0.0, 0.0, "init", null, Map.of());
        assertNull(state.turnId());
    }

    @Test
    void copiesMetadata() {
        var mutable = new java.util.HashMap<>(Map.of("k", "v"));
        var state = new MoodState("a1", "t1", 0.0, 0.0, 0.0, "init", null, mutable);
        mutable.put("k2", "v2");
        assertFalse(state.metadata().containsKey("k2"));
    }

    @Test
    void validStateStoresAllFields() {
        var state = new MoodState("a1", "t1", 0.7, -0.3, 0.5, "good news",
            "turn-1", Map.of("extra", "val"));
        assertEquals("a1", state.agentId());
        assertEquals("t1", state.tenantId());
        assertEquals(0.7, state.pleasure());
        assertEquals(-0.3, state.arousal());
        assertEquals(0.5, state.dominance());
        assertEquals("good news", state.cause());
        assertEquals("turn-1", state.turnId());
        assertEquals("val", state.metadata().get("extra"));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=MoodStateTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error — MoodState class does not exist

- [ ] **Step 3: Write MoodState record**

```java
package io.casehub.neocortex.memory.mood;

import java.util.Map;
import java.util.Objects;

public record MoodState(
    String agentId,
    String tenantId,
    double pleasure,
    double arousal,
    double dominance,
    String cause,
    String turnId,
    Map<String, String> metadata
) {
    public MoodState {
        Objects.requireNonNull(agentId, "agentId required");
        Objects.requireNonNull(tenantId, "tenantId required");
        Objects.requireNonNull(cause, "cause required");
        if (cause.isBlank()) throw new IllegalArgumentException("cause must not be blank");
        validateAxis("pleasure", pleasure);
        validateAxis("arousal", arousal);
        validateAxis("dominance", dominance);
        Objects.requireNonNull(metadata, "metadata required");
        metadata = Map.copyOf(metadata);
    }

    private static void validateAxis(String name, double value) {
        if (value < -1.0 || value > 1.0)
            throw new IllegalArgumentException(name + " must be in [-1, 1], got " + value);
    }
}
```

- [ ] **Step 4: Write MoodAttributeKeys**

```java
package io.casehub.neocortex.memory.mood;

public final class MoodAttributeKeys {
    public static final String PLEASURE = "pleasure";
    public static final String AROUSAL = "arousal";
    public static final String DOMINANCE = "dominance";
    public static final String TURN_ID = "turn-id";

    private MoodAttributeKeys() {}
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=MoodStateTest`
Expected: all 11 tests PASS

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/src/main/java/io/casehub/neocortex/memory/mood/ memory-api/src/test/java/io/casehub/neocortex/memory/mood/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(memory-api): add MoodState record and MoodAttributeKeys Refs #207"
```

### Task 2: MoodBaseline, MoodDecay, and MoodEvents converter

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodBaseline.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodDecay.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodEvents.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/mood/MoodBaselineTest.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/mood/MoodDecayTest.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/mood/MoodEventsTest.java`

**Interfaces:**
- Consumes: `MoodState` (Task 1), `MoodAttributeKeys` (Task 1), `io.casehub.neocortex.memory.MemoryDomain`, `io.casehub.neocortex.memory.MemoryInput`
- Produces: `MoodBaseline(double pleasure, double arousal, double dominance)` record; `MoodDecay.decay(MoodState current, MoodBaseline baseline, Duration elapsed, Duration timeConstant) → MoodState`; `MoodEvents.DOMAIN` (`MemoryDomain("mood")`), `MoodEvents.toMemoryInput(MoodState) → MemoryInput`

- [ ] **Step 1: Write MoodBaselineTest**

```java
package io.casehub.neocortex.memory.mood;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class MoodBaselineTest {

    @Test
    void acceptsValidBaseline() {
        var baseline = new MoodBaseline(0.5, -0.3, 0.0);
        assertEquals(0.5, baseline.pleasure());
        assertEquals(-0.3, baseline.arousal());
        assertEquals(0.0, baseline.dominance());
    }

    @Test
    void acceptsBoundaryValues() {
        var baseline = new MoodBaseline(1.0, -1.0, 1.0);
        assertEquals(1.0, baseline.pleasure());
        assertEquals(-1.0, baseline.arousal());
    }

    @Test
    void rejectsPleasureOutOfBounds() {
        assertThrows(IllegalArgumentException.class, () -> new MoodBaseline(1.1, 0.0, 0.0));
        assertThrows(IllegalArgumentException.class, () -> new MoodBaseline(-1.1, 0.0, 0.0));
    }

    @Test
    void rejectsArousalOutOfBounds() {
        assertThrows(IllegalArgumentException.class, () -> new MoodBaseline(0.0, 1.1, 0.0));
    }

    @Test
    void rejectsDominanceOutOfBounds() {
        assertThrows(IllegalArgumentException.class, () -> new MoodBaseline(0.0, 0.0, -1.1));
    }
}
```

- [ ] **Step 2: Write MoodDecayTest**

```java
package io.casehub.neocortex.memory.mood;

import org.junit.jupiter.api.Test;
import java.time.Duration;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class MoodDecayTest {

    private static final MoodBaseline NEUTRAL = new MoodBaseline(0.0, 0.0, 0.0);
    private static final Duration TAU = Duration.ofHours(6);

    private MoodState mood(double p, double a, double d) {
        return new MoodState("a1", "t1", p, a, d, "test", null, Map.of());
    }

    @Test
    void decaysTowardBaseline() {
        var current = mood(0.8, -0.6, 0.4);
        var decayed = MoodDecay.decay(current, NEUTRAL, Duration.ofHours(6), TAU);
        assertTrue(Math.abs(decayed.pleasure()) < 0.8);
        assertTrue(Math.abs(decayed.arousal()) < 0.6);
        assertTrue(Math.abs(decayed.dominance()) < 0.4);
    }

    @Test
    void convergesOverLongDuration() {
        var current = mood(1.0, -1.0, 0.5);
        var decayed = MoodDecay.decay(current, NEUTRAL, Duration.ofDays(30), TAU);
        assertEquals(0.0, decayed.pleasure(), 0.001);
        assertEquals(0.0, decayed.arousal(), 0.001);
        assertEquals(0.0, decayed.dominance(), 0.001);
    }

    @Test
    void zeroElapsedReturnsCurrentValues() {
        var current = mood(0.5, -0.3, 0.7);
        var decayed = MoodDecay.decay(current, NEUTRAL, Duration.ZERO, TAU);
        assertEquals(0.5, decayed.pleasure(), 0.0001);
        assertEquals(-0.3, decayed.arousal(), 0.0001);
        assertEquals(0.7, decayed.dominance(), 0.0001);
    }

    @Test
    void negativeElapsedTreatedAsZero() {
        var current = mood(0.5, -0.3, 0.7);
        var decayed = MoodDecay.decay(current, NEUTRAL, Duration.ofHours(-1), TAU);
        assertEquals(0.5, decayed.pleasure(), 0.0001);
    }

    @Test
    void alreadyAtBaselineStaysAtBaseline() {
        var baseline = new MoodBaseline(0.3, -0.2, 0.1);
        var current = mood(0.3, -0.2, 0.1);
        var decayed = MoodDecay.decay(current, baseline, Duration.ofHours(10), TAU);
        assertEquals(0.3, decayed.pleasure(), 0.0001);
        assertEquals(-0.2, decayed.arousal(), 0.0001);
        assertEquals(0.1, decayed.dominance(), 0.0001);
    }

    @Test
    void decaysTowardNonZeroBaseline() {
        var baseline = new MoodBaseline(0.5, 0.5, 0.5);
        var current = mood(-0.5, -0.5, -0.5);
        var decayed = MoodDecay.decay(current, baseline, Duration.ofHours(6), TAU);
        assertTrue(decayed.pleasure() > -0.5);
        assertTrue(decayed.arousal() > -0.5);
        assertTrue(decayed.dominance() > -0.5);
        assertTrue(decayed.pleasure() < 0.5);
    }

    @Test
    void higherTimeConstantSlowsDecay() {
        var current = mood(0.8, 0.0, 0.0);
        var elapsed = Duration.ofHours(6);
        var fast = MoodDecay.decay(current, NEUTRAL, elapsed, Duration.ofHours(3));
        var slow = MoodDecay.decay(current, NEUTRAL, elapsed, Duration.ofHours(12));
        assertTrue(fast.pleasure() < slow.pleasure());
    }

    @Test
    void preservesAgentAndTenantId() {
        var current = new MoodState("agent-x", "tenant-y", 0.8, 0.0, 0.0,
            "event", "turn-1", Map.of("k", "v"));
        var decayed = MoodDecay.decay(current, NEUTRAL, Duration.ofHours(1), TAU);
        assertEquals("agent-x", decayed.agentId());
        assertEquals("tenant-y", decayed.tenantId());
        assertEquals("decay", decayed.cause());
    }
}
```

- [ ] **Step 3: Write MoodEventsTest**

```java
package io.casehub.neocortex.memory.mood;

import io.casehub.neocortex.memory.MemoryDomain;
import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class MoodEventsTest {

    @Test
    void domainIsMood() {
        assertEquals(new MemoryDomain("mood"), MoodEvents.DOMAIN);
    }

    @Test
    void convertsToMemoryInput() {
        var state = new MoodState("a1", "t1", 0.7, -0.3, 0.5, "good news",
            "turn-1", Map.of("extra", "val"));
        var input = MoodEvents.toMemoryInput(state);

        assertEquals("a1", input.entityId());
        assertEquals(MoodEvents.DOMAIN, input.domain());
        assertEquals("t1", input.tenantId());
        assertEquals("good news", input.text());
        assertEquals("0.7", input.attributes().get(MoodAttributeKeys.PLEASURE));
        assertEquals("-0.3", input.attributes().get(MoodAttributeKeys.AROUSAL));
        assertEquals("0.5", input.attributes().get(MoodAttributeKeys.DOMINANCE));
        assertEquals("turn-1", input.attributes().get(MoodAttributeKeys.TURN_ID));
        assertEquals("val", input.attributes().get("extra"));
    }

    @Test
    void omitsTurnIdWhenNull() {
        var state = new MoodState("a1", "t1", 0.0, 0.0, 0.0, "init", null, Map.of());
        var input = MoodEvents.toMemoryInput(state);
        assertFalse(input.attributes().containsKey(MoodAttributeKeys.TURN_ID));
    }

    @Test
    void rejectsMetadataCollidingWithReservedKeys() {
        var state = new MoodState("a1", "t1", 0.0, 0.0, 0.0, "init", null,
            Map.of(MoodAttributeKeys.PLEASURE, "hijack"));
        assertThrows(IllegalArgumentException.class, () -> MoodEvents.toMemoryInput(state));
    }
}
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest="MoodBaselineTest,MoodDecayTest,MoodEventsTest" -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation errors — classes do not exist

- [ ] **Step 5: Write MoodBaseline record**

```java
package io.casehub.neocortex.memory.mood;

public record MoodBaseline(double pleasure, double arousal, double dominance) {
    public MoodBaseline {
        validateAxis("pleasure", pleasure);
        validateAxis("arousal", arousal);
        validateAxis("dominance", dominance);
    }

    private static void validateAxis(String name, double value) {
        if (value < -1.0 || value > 1.0)
            throw new IllegalArgumentException(name + " must be in [-1, 1], got " + value);
    }
}
```

- [ ] **Step 6: Write MoodDecay utility**

```java
package io.casehub.neocortex.memory.mood;

import java.time.Duration;
import java.util.Map;
import java.util.Objects;

public final class MoodDecay {

    private MoodDecay() {}

    public static MoodState decay(MoodState current, MoodBaseline baseline,
                                   Duration elapsed, Duration timeConstant) {
        Objects.requireNonNull(current, "current required");
        Objects.requireNonNull(baseline, "baseline required");
        Objects.requireNonNull(elapsed, "elapsed required");
        Objects.requireNonNull(timeConstant, "timeConstant required");

        double elapsedMs = Math.max(0, elapsed.toMillis());
        double tauMs = timeConstant.toMillis();
        if (elapsedMs == 0 || tauMs == 0) return current;

        double factor = 1.0 - Math.exp(-elapsedMs / tauMs);

        return new MoodState(
            current.agentId(),
            current.tenantId(),
            decayAxis(current.pleasure(), baseline.pleasure(), factor),
            decayAxis(current.arousal(), baseline.arousal(), factor),
            decayAxis(current.dominance(), baseline.dominance(), factor),
            "decay",
            null,
            Map.of()
        );
    }

    private static double decayAxis(double current, double baseline, double factor) {
        return current + (baseline - current) * factor;
    }
}
```

- [ ] **Step 7: Write MoodEvents converter**

```java
package io.casehub.neocortex.memory.mood;

import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.MemoryInput;
import java.util.HashMap;
import java.util.HashSet;

public final class MoodEvents {

    public static final MemoryDomain DOMAIN = new MemoryDomain("mood");

    private MoodEvents() {}

    public static MemoryInput toMemoryInput(MoodState state) {
        var reserved = new HashSet<String>();
        var attrs = new HashMap<String, String>();

        reserved.add(MoodAttributeKeys.PLEASURE);
        attrs.put(MoodAttributeKeys.PLEASURE, String.valueOf(state.pleasure()));

        reserved.add(MoodAttributeKeys.AROUSAL);
        attrs.put(MoodAttributeKeys.AROUSAL, String.valueOf(state.arousal()));

        reserved.add(MoodAttributeKeys.DOMINANCE);
        attrs.put(MoodAttributeKeys.DOMINANCE, String.valueOf(state.dominance()));

        if (state.turnId() != null) {
            reserved.add(MoodAttributeKeys.TURN_ID);
            attrs.put(MoodAttributeKeys.TURN_ID, state.turnId());
        }

        for (String key : state.metadata().keySet()) {
            if (reserved.contains(key)) {
                throw new IllegalArgumentException(
                    "metadata key '" + key + "' collides with a reserved mood attribute key");
            }
        }

        attrs.putAll(state.metadata());

        return new MemoryInput(state.agentId(), DOMAIN, state.tenantId(),
            null, state.cause(), attrs, null);
    }
}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest="MoodBaselineTest,MoodDecayTest,MoodEventsTest"`
Expected: all tests PASS

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/src/main/java/io/casehub/neocortex/memory/mood/ memory-api/src/test/java/io/casehub/neocortex/memory/mood/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(memory-api): add MoodBaseline, MoodDecay, MoodEvents Refs #207"
```

## Batch 2: Mood-Modulated Retrieval (memory-api)

### Task 3: MoodModulatedRetrieval utility

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodModulatedRetrieval.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/mood/MoodModulatedRetrievalTest.java`

**Interfaces:**
- Consumes: `MoodState` (Task 1), `MoodAttributeKeys` (Task 1), `io.casehub.neocortex.memory.Memory`, `io.casehub.neocortex.memory.personality.PersonalityWeights`, `io.casehub.neocortex.memory.personality.PersonalityWeightedRetrieval` (existing — for score formula reference)
- Produces: `MoodModulatedRetrieval.reweight(List<Memory>, PersonalityWeights, MoodState, double moodInfluence, Instant now) → List<Memory>`

- [ ] **Step 1: Write MoodModulatedRetrievalTest**

```java
package io.casehub.neocortex.memory.mood;

import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.personality.PersonalityWeights;
import io.casehub.neocortex.memory.personality.PersonalityWeightedRetrieval;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class MoodModulatedRetrievalTest {

    private static final Instant NOW = Instant.parse("2026-08-17T12:00:00Z");
    private static final MemoryDomain EXP = new MemoryDomain("experience");
    private static final PersonalityWeights EQUAL_WEIGHTS = new PersonalityWeights(Map.of());

    private Memory memory(String id, Instant createdAt, Map<String, String> attrs) {
        return new Memory(id, "a1", EXP, "t1", null, "text", attrs, createdAt, 0.5);
    }

    private MoodState mood(double p, double a, double d) {
        return new MoodState("a1", "t1", p, a, d, "test", null, Map.of());
    }

    @Test
    void moodAlignedMemoryBoosted() {
        var recent = NOW.minus(1, ChronoUnit.HOURS);
        var happy = memory("happy", recent, Map.of(
            MoodAttributeKeys.PLEASURE, "0.8",
            MoodAttributeKeys.AROUSAL, "0.3",
            MoodAttributeKeys.DOMINANCE, "0.2"));
        var sad = memory("sad", recent, Map.of(
            MoodAttributeKeys.PLEASURE, "-0.8",
            MoodAttributeKeys.AROUSAL, "-0.3",
            MoodAttributeKeys.DOMINANCE, "-0.2"));

        var currentMood = mood(0.8, 0.3, 0.2);
        var result = MoodModulatedRetrieval.reweight(
            List.of(sad, happy), EQUAL_WEIGHTS, currentMood, 1.0, NOW);

        assertEquals("happy", result.getFirst().memoryId());
    }

    @Test
    void unannotatedMemoriesUnaffected() {
        var recent = NOW.minus(1, ChronoUnit.HOURS);
        var annotated = memory("annotated", recent, Map.of(
            MoodAttributeKeys.PLEASURE, "0.8",
            MoodAttributeKeys.AROUSAL, "0.0",
            MoodAttributeKeys.DOMINANCE, "0.0"));
        var plain = memory("plain", recent, Map.of());

        var currentMood = mood(-0.8, 0.0, 0.0);
        var result = MoodModulatedRetrieval.reweight(
            List.of(annotated, plain), EQUAL_WEIGHTS, currentMood, 1.0, NOW);

        assertEquals("plain", result.getFirst().memoryId());
    }

    @Test
    void zeroInfluenceMatchesPersonalityWeightedRetrieval() {
        var t1 = NOW.minus(1, ChronoUnit.HOURS);
        var t2 = NOW.minus(2, ChronoUnit.HOURS);
        var m1 = memory("m1", t1, Map.of(MoodAttributeKeys.PLEASURE, "0.9",
            MoodAttributeKeys.AROUSAL, "0.0", MoodAttributeKeys.DOMINANCE, "0.0"));
        var m2 = memory("m2", t2, Map.of(MoodAttributeKeys.PLEASURE, "-0.9",
            MoodAttributeKeys.AROUSAL, "0.0", MoodAttributeKeys.DOMINANCE, "0.0"));

        var currentMood = mood(0.9, 0.0, 0.0);
        var moodResult = MoodModulatedRetrieval.reweight(
            List.of(m1, m2), EQUAL_WEIGHTS, currentMood, 0.0, NOW);
        var personalityResult = PersonalityWeightedRetrieval.reweight(
            List.of(m1, m2), EQUAL_WEIGHTS, NOW);

        assertEquals(personalityResult.getFirst().memoryId(),
            moodResult.getFirst().memoryId());
    }

    @Test
    void emptyListReturnsEmpty() {
        var result = MoodModulatedRetrieval.reweight(
            List.of(), EQUAL_WEIGHTS, mood(0.0, 0.0, 0.0), 1.0, NOW);
        assertTrue(result.isEmpty());
    }

    @Test
    void partialPadDefaultsMissingToZero() {
        var recent = NOW.minus(1, ChronoUnit.HOURS);
        var partial = memory("partial", recent, Map.of(
            MoodAttributeKeys.PLEASURE, "0.8"));
        var full = memory("full", recent, Map.of(
            MoodAttributeKeys.PLEASURE, "0.8",
            MoodAttributeKeys.AROUSAL, "0.8",
            MoodAttributeKeys.DOMINANCE, "0.8"));

        var currentMood = mood(0.8, 0.8, 0.8);
        var result = MoodModulatedRetrieval.reweight(
            List.of(partial, full), EQUAL_WEIGHTS, currentMood, 1.0, NOW);

        assertEquals("full", result.getFirst().memoryId());
    }

    @Test
    void rejectsMoodInfluenceOutOfBounds() {
        assertThrows(IllegalArgumentException.class, () ->
            MoodModulatedRetrieval.reweight(
                List.of(), EQUAL_WEIGHTS, mood(0.0, 0.0, 0.0), 1.1, NOW));
        assertThrows(IllegalArgumentException.class, () ->
            MoodModulatedRetrieval.reweight(
                List.of(), EQUAL_WEIGHTS, mood(0.0, 0.0, 0.0), -0.1, NOW));
    }

    @Test
    void originalListUnchanged() {
        var recent = NOW.minus(1, ChronoUnit.HOURS);
        var old = NOW.minus(7, ChronoUnit.DAYS);
        var original = List.of(
            memory("old", old, Map.of()),
            memory("recent", recent, Map.of()));

        MoodModulatedRetrieval.reweight(original, EQUAL_WEIGHTS, mood(0.0, 0.0, 0.0), 0.5, NOW);
        assertEquals("old", original.getFirst().memoryId());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=MoodModulatedRetrievalTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error — class does not exist

- [ ] **Step 3: Write MoodModulatedRetrieval**

```java
package io.casehub.neocortex.memory.mood;

import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.personality.PersonalityWeights;
import java.time.Duration;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;

public final class MoodModulatedRetrieval {

    private static final double HALF_LIFE_HOURS = 168.0;
    private static final double MAX_PAD_DISTANCE = Math.sqrt(12.0);

    private MoodModulatedRetrieval() {}

    public static List<Memory> reweight(List<Memory> memories,
            PersonalityWeights weights, MoodState currentMood,
            double moodInfluence, Instant now) {
        Objects.requireNonNull(memories, "memories required");
        Objects.requireNonNull(weights, "weights required");
        Objects.requireNonNull(currentMood, "currentMood required");
        Objects.requireNonNull(now, "now required");
        if (moodInfluence < 0.0 || moodInfluence > 1.0)
            throw new IllegalArgumentException("moodInfluence must be in [0, 1], got " + moodInfluence);

        if (memories.isEmpty()) return List.of();

        return memories.stream()
            .sorted(Comparator.comparingDouble(
                (Memory m) -> score(m, weights, currentMood, moodInfluence, now)).reversed())
            .toList();
    }

    private static double score(Memory memory, PersonalityWeights weights,
            MoodState mood, double moodInfluence, Instant now) {
        double recency = recencyDecay(memory.createdAt(), now);
        double importance = memory.importance() != null ? memory.importance() : 1.0;
        double domainWeight = weights.getWeight(memory.domain());
        double moodFactor = moodFactor(memory, mood, moodInfluence);
        return recency * importance * domainWeight * moodFactor;
    }

    private static double moodFactor(Memory memory, MoodState mood, double moodInfluence) {
        if (moodInfluence == 0.0) return 1.0;

        var attrs = memory.attributes();
        String pStr = attrs.get(MoodAttributeKeys.PLEASURE);
        String aStr = attrs.get(MoodAttributeKeys.AROUSAL);
        String dStr = attrs.get(MoodAttributeKeys.DOMINANCE);

        if (pStr == null && aStr == null && dStr == null) return 1.0;

        double mp = pStr != null ? Double.parseDouble(pStr) : 0.0;
        double ma = aStr != null ? Double.parseDouble(aStr) : 0.0;
        double md = dStr != null ? Double.parseDouble(dStr) : 0.0;

        double dp = mood.pleasure() - mp;
        double da = mood.arousal() - ma;
        double dd = mood.dominance() - md;
        double distance = Math.sqrt(dp * dp + da * da + dd * dd);
        double alignment = 1.0 - distance / MAX_PAD_DISTANCE;

        return 1.0 + moodInfluence * (alignment - 0.5);
    }

    private static double recencyDecay(Instant createdAt, Instant now) {
        if (createdAt == null) return 0.5;
        double hoursElapsed = Duration.between(createdAt, now).toMillis() / 3_600_000.0;
        if (hoursElapsed < 0) hoursElapsed = 0;
        return Math.exp(-hoursElapsed / HALF_LIFE_HOURS);
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=MoodModulatedRetrievalTest`
Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/src/main/java/io/casehub/neocortex/memory/mood/ memory-api/src/test/java/io/casehub/neocortex/memory/mood/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(memory-api): add MoodModulatedRetrieval Refs #207"
```

## Batch 3: Engagement Scoring (memory-api + memory)

### Task 4: EngagementEvent, EngagementEvents, EngagementAttributeKeys

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/engagement/EngagementEvent.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/engagement/EngagementEvents.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/engagement/EngagementAttributeKeys.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/engagement/EngagementEventTest.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/engagement/EngagementEventsTest.java`

**Interfaces:**
- Consumes: `io.casehub.neocortex.memory.MemoryDomain`, `io.casehub.neocortex.memory.MemoryInput`
- Produces: `EngagementEvent(String agentId, String otherAgentId, String tenantId, String caseId, String turnId, String description, Double importance, Map<String, String> metadata, Boolean responded, Long responseTimeMs, Integer responseLength, Double sentimentShift, Integer reactionCount, Boolean continued)` record; `EngagementEvents.DOMAIN` (`MemoryDomain("engagement")`), `EngagementEvents.toMemoryInput(EngagementEvent) → MemoryInput`; `EngagementAttributeKeys` constants

- [ ] **Step 1: Write EngagementEventTest**

```java
package io.casehub.neocortex.memory.engagement;

import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class EngagementEventTest {

    @Test
    void requiresAgentId() {
        assertThrows(NullPointerException.class, () ->
            new EngagementEvent(null, "b1", "t1", null, "turn-1", "desc",
                null, Map.of(), true, null, null, null, null, null));
    }

    @Test
    void requiresOtherAgentId() {
        assertThrows(NullPointerException.class, () ->
            new EngagementEvent("a1", null, "t1", null, "turn-1", "desc",
                null, Map.of(), true, null, null, null, null, null));
    }

    @Test
    void requiresTenantId() {
        assertThrows(NullPointerException.class, () ->
            new EngagementEvent("a1", "b1", null, null, "turn-1", "desc",
                null, Map.of(), true, null, null, null, null, null));
    }

    @Test
    void requiresTurnId() {
        assertThrows(NullPointerException.class, () ->
            new EngagementEvent("a1", "b1", "t1", null, null, "desc",
                null, Map.of(), true, null, null, null, null, null));
    }

    @Test
    void rejectsBlankTurnId() {
        assertThrows(IllegalArgumentException.class, () ->
            new EngagementEvent("a1", "b1", "t1", null, "  ", "desc",
                null, Map.of(), true, null, null, null, null, null));
    }

    @Test
    void requiresDescription() {
        assertThrows(NullPointerException.class, () ->
            new EngagementEvent("a1", "b1", "t1", null, "turn-1", null,
                null, Map.of(), true, null, null, null, null, null));
    }

    @Test
    void rejectsBlankDescription() {
        assertThrows(IllegalArgumentException.class, () ->
            new EngagementEvent("a1", "b1", "t1", null, "turn-1", "  ",
                null, Map.of(), true, null, null, null, null, null));
    }

    @Test
    void rejectsSelfReferential() {
        assertThrows(IllegalArgumentException.class, () ->
            new EngagementEvent("a1", "a1", "t1", null, "turn-1", "desc",
                null, Map.of(), true, null, null, null, null, null));
    }

    @Test
    void rejectsSentimentShiftOutOfBounds() {
        assertThrows(IllegalArgumentException.class, () ->
            new EngagementEvent("a1", "b1", "t1", null, "turn-1", "desc",
                null, Map.of(), null, null, null, 1.1, null, null));
        assertThrows(IllegalArgumentException.class, () ->
            new EngagementEvent("a1", "b1", "t1", null, "turn-1", "desc",
                null, Map.of(), null, null, null, -1.1, null, null));
    }

    @Test
    void rejectsImportanceOutOfBounds() {
        assertThrows(IllegalArgumentException.class, () ->
            new EngagementEvent("a1", "b1", "t1", null, "turn-1", "desc",
                1.1, Map.of(), null, null, null, null, null, null));
        assertThrows(IllegalArgumentException.class, () ->
            new EngagementEvent("a1", "b1", "t1", null, "turn-1", "desc",
                -0.1, Map.of(), null, null, null, null, null, null));
    }

    @Test
    void acceptsAllNullSignals() {
        var event = new EngagementEvent("a1", "b1", "t1", null, "turn-1", "desc",
            null, Map.of(), null, null, null, null, null, null);
        assertNull(event.responded());
        assertNull(event.responseTimeMs());
        assertNull(event.responseLength());
        assertNull(event.sentimentShift());
        assertNull(event.reactionCount());
        assertNull(event.continued());
    }

    @Test
    void copiesMetadata() {
        var mutable = new java.util.HashMap<>(Map.of("k", "v"));
        var event = new EngagementEvent("a1", "b1", "t1", null, "turn-1", "desc",
            null, mutable, true, null, null, null, null, null);
        mutable.put("k2", "v2");
        assertFalse(event.metadata().containsKey("k2"));
    }

    @Test
    void validEventStoresAllFields() {
        var event = new EngagementEvent("a1", "b1", "t1", "c1", "turn-1",
            "user responded enthusiastically", 0.8, Map.of("extra", "val"),
            true, 1500L, 142, 0.3, 2, true);
        assertEquals("a1", event.agentId());
        assertEquals("b1", event.otherAgentId());
        assertEquals("t1", event.tenantId());
        assertEquals("c1", event.caseId());
        assertEquals("turn-1", event.turnId());
        assertEquals("user responded enthusiastically", event.description());
        assertEquals(0.8, event.importance());
        assertTrue(event.responded());
        assertEquals(1500L, event.responseTimeMs());
        assertEquals(142, event.responseLength());
        assertEquals(0.3, event.sentimentShift());
        assertEquals(2, event.reactionCount());
        assertTrue(event.continued());
        assertEquals("val", event.metadata().get("extra"));
    }
}
```

- [ ] **Step 2: Write EngagementEventsTest**

```java
package io.casehub.neocortex.memory.engagement;

import io.casehub.neocortex.memory.MemoryDomain;
import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class EngagementEventsTest {

    @Test
    void domainIsEngagement() {
        assertEquals(new MemoryDomain("engagement"), EngagementEvents.DOMAIN);
    }

    @Test
    void convertsFullEventToMemoryInput() {
        var event = new EngagementEvent("a1", "b1", "t1", "c1", "turn-1",
            "user responded", 0.7, Map.of("extra", "val"),
            true, 1500L, 142, 0.3, 2, true);
        var input = EngagementEvents.toMemoryInput(event);

        assertEquals("a1", input.entityId());
        assertEquals(EngagementEvents.DOMAIN, input.domain());
        assertEquals("t1", input.tenantId());
        assertEquals("c1", input.caseId());
        assertEquals("user responded", input.text());
        assertEquals(0.7, input.importance());
        assertEquals("b1", input.attributes().get(EngagementAttributeKeys.OTHER_AGENT));
        assertEquals("turn-1", input.attributes().get(EngagementAttributeKeys.TURN_ID));
        assertEquals("true", input.attributes().get(EngagementAttributeKeys.RESPONDED));
        assertEquals("1500", input.attributes().get(EngagementAttributeKeys.RESPONSE_TIME_MS));
        assertEquals("142", input.attributes().get(EngagementAttributeKeys.RESPONSE_LENGTH));
        assertEquals("0.3", input.attributes().get(EngagementAttributeKeys.SENTIMENT_SHIFT));
        assertEquals("2", input.attributes().get(EngagementAttributeKeys.REACTION_COUNT));
        assertEquals("true", input.attributes().get(EngagementAttributeKeys.CONTINUED));
        assertEquals("val", input.attributes().get("extra"));
    }

    @Test
    void omitsNullSignals() {
        var event = new EngagementEvent("a1", "b1", "t1", null, "turn-1",
            "no response", null, Map.of(), null, null, null, null, null, null);
        var input = EngagementEvents.toMemoryInput(event);

        assertTrue(input.attributes().containsKey(EngagementAttributeKeys.OTHER_AGENT));
        assertTrue(input.attributes().containsKey(EngagementAttributeKeys.TURN_ID));
        assertFalse(input.attributes().containsKey(EngagementAttributeKeys.RESPONDED));
        assertFalse(input.attributes().containsKey(EngagementAttributeKeys.RESPONSE_TIME_MS));
        assertFalse(input.attributes().containsKey(EngagementAttributeKeys.RESPONSE_LENGTH));
        assertFalse(input.attributes().containsKey(EngagementAttributeKeys.SENTIMENT_SHIFT));
        assertFalse(input.attributes().containsKey(EngagementAttributeKeys.REACTION_COUNT));
        assertFalse(input.attributes().containsKey(EngagementAttributeKeys.CONTINUED));
    }

    @Test
    void rejectsMetadataCollidingWithReservedKeys() {
        var event = new EngagementEvent("a1", "b1", "t1", null, "turn-1",
            "desc", null, Map.of(EngagementAttributeKeys.OTHER_AGENT, "hijack"),
            null, null, null, null, null, null);
        assertThrows(IllegalArgumentException.class, () -> EngagementEvents.toMemoryInput(event));
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest="EngagementEventTest,EngagementEventsTest" -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation errors — classes do not exist

- [ ] **Step 4: Write EngagementAttributeKeys**

```java
package io.casehub.neocortex.memory.engagement;

public final class EngagementAttributeKeys {
    public static final String OTHER_AGENT = "other-agent";
    public static final String TURN_ID = "turn-id";
    public static final String RESPONDED = "responded";
    public static final String RESPONSE_TIME_MS = "response-time-ms";
    public static final String RESPONSE_LENGTH = "response-length";
    public static final String SENTIMENT_SHIFT = "sentiment-shift";
    public static final String REACTION_COUNT = "reaction-count";
    public static final String CONTINUED = "continued";

    private EngagementAttributeKeys() {}
}
```

- [ ] **Step 5: Write EngagementEvent record**

```java
package io.casehub.neocortex.memory.engagement;

import java.util.Map;
import java.util.Objects;

public record EngagementEvent(
    String agentId,
    String otherAgentId,
    String tenantId,
    String caseId,
    String turnId,
    String description,
    Double importance,
    Map<String, String> metadata,
    Boolean responded,
    Long responseTimeMs,
    Integer responseLength,
    Double sentimentShift,
    Integer reactionCount,
    Boolean continued
) {
    public EngagementEvent {
        Objects.requireNonNull(agentId, "agentId required");
        Objects.requireNonNull(otherAgentId, "otherAgentId required");
        Objects.requireNonNull(tenantId, "tenantId required");
        Objects.requireNonNull(turnId, "turnId required");
        if (turnId.isBlank()) throw new IllegalArgumentException("turnId must not be blank");
        Objects.requireNonNull(description, "description required");
        if (description.isBlank()) throw new IllegalArgumentException("description must not be blank");
        if (agentId.equals(otherAgentId))
            throw new IllegalArgumentException("agentId and otherAgentId must differ");
        if (sentimentShift != null && (sentimentShift < -1.0 || sentimentShift > 1.0))
            throw new IllegalArgumentException("sentimentShift must be in [-1, 1], got " + sentimentShift);
        if (importance != null && (importance < 0.0 || importance > 1.0))
            throw new IllegalArgumentException("importance must be in [0, 1], got " + importance);
        Objects.requireNonNull(metadata, "metadata required");
        metadata = Map.copyOf(metadata);
    }
}
```

- [ ] **Step 6: Write EngagementEvents converter**

```java
package io.casehub.neocortex.memory.engagement;

import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.MemoryInput;
import java.util.HashMap;
import java.util.HashSet;

public final class EngagementEvents {

    public static final MemoryDomain DOMAIN = new MemoryDomain("engagement");

    private EngagementEvents() {}

    public static MemoryInput toMemoryInput(EngagementEvent event) {
        var reserved = new HashSet<String>();
        var attrs = new HashMap<String, String>();

        reserved.add(EngagementAttributeKeys.OTHER_AGENT);
        attrs.put(EngagementAttributeKeys.OTHER_AGENT, event.otherAgentId());

        reserved.add(EngagementAttributeKeys.TURN_ID);
        attrs.put(EngagementAttributeKeys.TURN_ID, event.turnId());

        addIfPresent(reserved, attrs, EngagementAttributeKeys.RESPONDED, event.responded());
        addIfPresent(reserved, attrs, EngagementAttributeKeys.RESPONSE_TIME_MS, event.responseTimeMs());
        addIfPresent(reserved, attrs, EngagementAttributeKeys.RESPONSE_LENGTH, event.responseLength());
        addIfPresent(reserved, attrs, EngagementAttributeKeys.SENTIMENT_SHIFT, event.sentimentShift());
        addIfPresent(reserved, attrs, EngagementAttributeKeys.REACTION_COUNT, event.reactionCount());
        addIfPresent(reserved, attrs, EngagementAttributeKeys.CONTINUED, event.continued());

        for (String key : event.metadata().keySet()) {
            if (reserved.contains(key)) {
                throw new IllegalArgumentException(
                    "metadata key '" + key + "' collides with a reserved engagement attribute key");
            }
        }

        attrs.putAll(event.metadata());

        return new MemoryInput(event.agentId(), DOMAIN, event.tenantId(),
            event.caseId(), event.description(), attrs, event.importance());
    }

    private static void addIfPresent(HashSet<String> reserved, HashMap<String, String> attrs,
            String key, Object value) {
        if (value != null) {
            reserved.add(key);
            attrs.put(key, String.valueOf(value));
        }
    }
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest="EngagementEventTest,EngagementEventsTest"`
Expected: all tests PASS

- [ ] **Step 8: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/src/main/java/io/casehub/neocortex/memory/engagement/ memory-api/src/test/java/io/casehub/neocortex/memory/engagement/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(memory-api): add EngagementEvent, EngagementEvents, EngagementAttributeKeys Refs #208"
```

### Task 5: EngagementRecorded, EngagementStoreResult/Failure, EngagementStream CDI

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/engagement/EngagementRecorded.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/engagement/EngagementStoreResult.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/engagement/EngagementStoreFailure.java`
- Create: `memory/src/main/java/io/casehub/neocortex/memory/engagement/runtime/EngagementStream.java`
- Test: `memory/src/test/java/io/casehub/neocortex/memory/engagement/runtime/EngagementStreamTest.java`

**Interfaces:**
- Consumes: `EngagementEvent` (Task 4), `EngagementEvents` (Task 4), `io.casehub.neocortex.memory.CaseMemoryStore`, `io.casehub.neocortex.memory.StoreAllResult`, `io.casehub.neocortex.memory.StoreFailure`
- Produces: `EngagementRecorded(EngagementEvent event, String memoryId)` CDI event; `EngagementStoreResult(List<String> stored, List<EngagementStoreFailure> failures)` batch result; `EngagementStream.record(EngagementEvent) → String`, `EngagementStream.recordAll(List<EngagementEvent>) → EngagementStoreResult`

- [ ] **Step 1: Write EngagementRecorded, EngagementStoreResult, EngagementStoreFailure**

```java
// EngagementRecorded.java
package io.casehub.neocortex.memory.engagement;

public record EngagementRecorded(EngagementEvent event, String memoryId) {}
```

```java
// EngagementStoreFailure.java
package io.casehub.neocortex.memory.engagement;

public record EngagementStoreFailure(int inputIndex, EngagementEvent event, RuntimeException cause) {}
```

```java
// EngagementStoreResult.java
package io.casehub.neocortex.memory.engagement;

import java.util.List;

public record EngagementStoreResult(List<String> stored, List<EngagementStoreFailure> failures) {
    public EngagementStoreResult {
        stored = List.copyOf(stored);
        failures = List.copyOf(failures);
    }

    public static EngagementStoreResult empty() {
        return new EngagementStoreResult(List.of(), List.of());
    }

    public boolean allSucceeded() {
        return failures.isEmpty();
    }
}
```

- [ ] **Step 2: Write EngagementStreamTest**

```java
package io.casehub.neocortex.memory.engagement.runtime;

import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.MemoryInput;
import io.casehub.neocortex.memory.StoreAllResult;
import io.casehub.neocortex.memory.engagement.EngagementEvent;
import io.casehub.neocortex.memory.engagement.EngagementRecorded;
import io.casehub.neocortex.memory.engagement.EngagementStoreResult;
import jakarta.enterprise.event.Event;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletionStage;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class EngagementStreamTest {

    private CaseMemoryStore store;
    private Event<EngagementRecorded> event;
    private EngagementStream stream;
    private List<EngagementRecorded> fired;

    @SuppressWarnings("unchecked")
    @BeforeEach
    void setUp() {
        store = mock(CaseMemoryStore.class);
        event = mock(Event.class);
        stream = new EngagementStream(store, event);
        fired = new ArrayList<>();
        doAnswer(inv -> { fired.add(inv.getArgument(0)); return null; }).when(event).fire(any());
    }

    private EngagementEvent engagement() {
        return new EngagementEvent("a1", "b1", "t1", null, "turn-1",
            "user responded", null, Map.of(), true, null, null, null, null, null);
    }

    @Test
    void recordStoresAndFiresEvent() {
        when(store.store(any(MemoryInput.class))).thenReturn("mem-1");

        String id = stream.record(engagement());

        assertEquals("mem-1", id);
        verify(store).store(any(MemoryInput.class));
        assertEquals(1, fired.size());
        assertEquals("mem-1", fired.getFirst().memoryId());
        assertEquals("a1", fired.getFirst().event().agentId());
    }

    @Test
    void recordAllStoresAndFiresPerEvent() {
        var events = List.of(engagement(), engagement());
        when(store.storeAll(any())).thenReturn(
            new StoreAllResult(List.of("mem-1", "mem-2"), List.of()));

        EngagementStoreResult result = stream.recordAll(events);

        assertTrue(result.allSucceeded());
        assertEquals(List.of("mem-1", "mem-2"), result.stored());
        assertEquals(2, fired.size());
    }

    @Test
    void recordAllEmptyReturnsEmpty() {
        EngagementStoreResult result = stream.recordAll(List.of());
        assertTrue(result.allSucceeded());
        assertTrue(result.stored().isEmpty());
        verifyNoInteractions(store);
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -Dtest=EngagementStreamTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error — EngagementStream does not exist

- [ ] **Step 4: Write EngagementStream**

```java
package io.casehub.neocortex.memory.engagement.runtime;

import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.StoreAllResult;
import io.casehub.neocortex.memory.engagement.EngagementEvent;
import io.casehub.neocortex.memory.engagement.EngagementEvents;
import io.casehub.neocortex.memory.engagement.EngagementRecorded;
import io.casehub.neocortex.memory.engagement.EngagementStoreFailure;
import io.casehub.neocortex.memory.engagement.EngagementStoreResult;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Event;
import jakarta.inject.Inject;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;

@ApplicationScoped
public class EngagementStream {

    private final CaseMemoryStore store;
    private final Event<EngagementRecorded> recorded;

    @Inject
    EngagementStream(CaseMemoryStore store, Event<EngagementRecorded> recorded) {
        this.store = store;
        this.recorded = recorded;
    }

    public String record(EngagementEvent event) {
        var input = EngagementEvents.toMemoryInput(event);
        var memoryId = store.store(input);
        recorded.fire(new EngagementRecorded(event, memoryId));
        return memoryId;
    }

    public EngagementStoreResult recordAll(List<EngagementEvent> events) {
        if (events.isEmpty()) return EngagementStoreResult.empty();

        var inputs = events.stream()
            .map(EngagementEvents::toMemoryInput)
            .toList();

        StoreAllResult storeResult = store.storeAll(inputs);

        var failedIndices = new HashSet<Integer>();
        var failures = new ArrayList<EngagementStoreFailure>();
        for (var sf : storeResult.failures()) {
            failedIndices.add(sf.inputIndex());
            failures.add(new EngagementStoreFailure(sf.inputIndex(),
                events.get(sf.inputIndex()), sf.cause()));
        }

        int storedIdx = 0;
        for (int i = 0; i < events.size(); i++) {
            if (!failedIndices.contains(i)) {
                recorded.fire(new EngagementRecorded(events.get(i),
                    storeResult.stored().get(storedIdx)));
                storedIdx++;
            }
        }

        return new EngagementStoreResult(storeResult.stored(), failures);
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -Dtest=EngagementStreamTest`
Expected: all 3 tests PASS

- [ ] **Step 6: Run full build to verify nothing is broken**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/src/main/java/io/casehub/neocortex/memory/engagement/ memory/src/main/java/io/casehub/neocortex/memory/engagement/ memory/src/test/java/io/casehub/neocortex/memory/engagement/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(memory): add EngagementStream CDI + EngagementRecorded event Refs #208"
```

## References

- [2026-08-17-mood-engagement-foundation-design.md] — design spec this plan implements
- [memory-api/src/main/java/io/casehub/neocortex/memory/relationship/RelationshipEvent.java] — pattern reference for standalone event types
- [memory-api/src/main/java/io/casehub/neocortex/memory/relationship/RelationshipEvents.java] — pattern reference for converter
- [memory-api/src/main/java/io/casehub/neocortex/memory/personality/PersonalityWeightedRetrieval.java] — base retrieval utility extended by MoodModulatedRetrieval
- [memory/src/main/java/io/casehub/neocortex/memory/experience/runtime/ExperienceStream.java] — pattern reference for CDI stream
- [GitHub #207] — MoodState type + mood-modulated retrieval decorator
- [GitHub #208] — Conversational engagement scoring — standardised outcome definitions

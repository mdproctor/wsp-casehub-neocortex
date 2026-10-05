# Cognitive Appraisal Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #428 — Epic: Cognitive appraisal architecture — standardised emotional appraisal from drives × environment
**Issue group:** #428

**Goal:** Build a standardised emotional appraisal pipeline that computes emotions from drives × environment, replacing monolithic drive descriptions with a perception → appraisal → emotion → action-readiness pipeline grounded in Scherer/OCC/Frijda/Lazarus psychology.

**Architecture:** Three-system complementary architecture across two temporal scales. CAPS (consolidation-time) encodes dispositional behavioral tendencies. Scherer appraisal (real-time, this plan) computes per-tick emotional context before LLM response. OCC (both scales) classifies emotions. New SPIs (SalienceStrategy, AppraisalStrategy) run as a CognitionTickParticipant in the DERIVED phase. Drives evolve from 4 fixed axes to dynamic per-character drives. Habituation is personality-parameterised.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI, cognitive-api/cognition-api/cognition/cognitive-index modules

## Global Constraints

- Java 21 source level, Java 26 JVM
- All new SPIs are `@FunctionalInterface` with synchronous return types
- All new value types are Java records
- SPI definitions are provisional pending Stage 1 research — method signatures (`perceive()`, `appraise()`) are research-agnostic; context record shapes may evolve
- Emotion output reuses existing `CognitiveEmotion` from cognitive-api — no new emotion types
- No new Maven modules — all types go in existing modules per §6 of the spec
- Every toggle follows `CognitionConfig` pattern — boolean field, checked at tick time
- Tests use deterministic stubs, not LLM-backed implementations
- Commit after every task with `Refs #428`

---

## Batch 1: Research Synthesis

### Task 1: Multi-agent debate — real-time LLM appraisal applicability

**Files:**
- Create: `$WORKSPACE/specs/issue-428-cognitive-appraisal-arch/2026-10-04-research-synthesis.md`
- Create: `$WORKSPACE/specs/issue-428-cognitive-appraisal-arch/explorations/research-debate/` (advocate + mediator docs)

**Interfaces:**
- Consumes: spec §2 (6 models), #407 consolidation-time synthesis, issue #428 body
- Produces: research synthesis document with concrete recommendations for Stages 2-6

This is a document task, not a code task. The multi-agent debate addresses 4 questions:

- [ ] **Step 1: Set up debate structure**

Four debate questions from spec §2:
1. Which Scherer SECs add value for LLM agents? Do some collapse?
2. Where is the computational/LLM boundary per SEC?
3. Lazarus two-phase vs Scherer four-SEC — which maps better to LLM reasoning?
4. Action tendency granularity — full Frijda taxonomy (~16) or reduced set?

- [ ] **Step 2: Read #407 synthesis as foundation**

Read the existing consolidation-time synthesis:
```bash
# In the workspace or spec repo — find the #407 design doc
gh issue view 407 --repo casehubio/neocortex --json body -q '.body' | head -100
```

Identify which decisions #407 already made for consolidation-time. The debate focuses only on real-time (pre-response) applicability.

- [ ] **Step 3: Spawn advocate agents**

For each debate question, spawn 2-3 advocate agents. Each advocate argues for a specific position:

Q1 advocates: "All 4 SECs matter" vs "SECs 3+4 collapse" vs "Only SEC 1+2 needed"
Q2 advocates: "Mostly computational" vs "Mostly LLM" vs "Hybrid per-SEC"
Q3 advocates: "Lazarus two-phase" vs "Scherer four-SEC"
Q4 advocates: "Full Frijda taxonomy" vs "Reduced 5-category set"

Each advocate brief: "Make the strongest case for your position. Search the internet for supporting evidence and prior art in LLM agent emotion research. Address weaknesses honestly but argue for your position. Consider the wacky-manor constraints: evocative not analytical, identity activation, less instruction beats more."

- [ ] **Step 4: Mediator synthesis**

Spawn a mediator for each question: "Read the position papers. Determine which approach wins on merit for LLM agents specifically. Identify genuine strengths from losing positions that should be incorporated."

- [ ] **Step 5: Write research synthesis document**

Compile mediator outputs into `2026-10-04-research-synthesis.md` with:
- Per-question: winning position, rationale, incorporated elements from alternatives
- Concrete recommendations: which SECs to implement, computational/LLM boundary, action tendency set
- Impact on spec §4 SPI definitions — any context record changes needed

- [ ] **Step 6: Commit**

```bash
git -C "$WORKSPACE" add specs/issue-428-cognitive-appraisal-arch/
git -C "$WORKSPACE" commit -m "feat(research): cognitive appraisal research synthesis — multi-agent debate Refs #428"
```

---

## Batch 2: SPI Foundation + Value Types

### Task 1: Core value types in cognition-api

**Files:**
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/Drive.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/DriveCategory.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/ActionTendency.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/ActionReadiness.java`
- Create: `../../cognitive-api/src/main/java/io/casehub/neocortex/cognitive/HabituationConfig.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/HabituationState.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/SchererAppraisalConfig.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/SalienceConfig.java`
- Test: `cognition-api/src/test/java/io/casehub/neocortex/cognition/appraisal/DriveTest.java`
- Test: `cognition-api/src/test/java/io/casehub/neocortex/cognition/appraisal/HabituationStateTest.java`

**Interfaces:**
- Consumes: `CognitiveEmotion` (cognitive-api), `MoodState` (memory-api)
- Produces: value types consumed by SPI context records (Task 2) and by DriveOrchestrator (Batch 3)

- [ ] **Step 1: Write failing test for Drive record**

```java
package io.casehub.neocortex.cognition.appraisal;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class DriveTest {

    @Test
    void baselineDrive() {
        var drive = new Drive("curiosity", DriveCategory.BASELINE, 0.7, "knowledge gaps detected");
        assertEquals("curiosity", drive.name());
        assertEquals(DriveCategory.BASELINE, drive.category());
        assertEquals(0.7, drive.intensity(), 0.001);
        assertEquals("knowledge gaps detected", drive.trigger());
    }

    @Test
    void characterDrive() {
        var drive = new Drive("protection", DriveCategory.CHARACTER, 0.9, "Clara is missing");
        assertEquals(DriveCategory.CHARACTER, drive.category());
    }

    @Test
    void intensityClampedToValidRange() {
        assertThrows(IllegalArgumentException.class,
            () -> new Drive("x", DriveCategory.BASELINE, -0.1, ""));
        assertThrows(IllegalArgumentException.class,
            () -> new Drive("x", DriveCategory.BASELINE, 1.1, ""));
    }

    @Test
    void nameRequired() {
        assertThrows(NullPointerException.class,
            () -> new Drive(null, DriveCategory.BASELINE, 0.5, ""));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api -Dtest=DriveTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — classes not found

- [ ] **Step 3: Implement Drive, DriveCategory, ActionTendency, ActionReadiness**

Use `ide_create_file` for each:

```java
// Drive.java
package io.casehub.neocortex.cognition.appraisal;

import java.util.Objects;

public record Drive(
    String name,
    DriveCategory category,
    double intensity,
    String trigger
) {
    public Drive {
        Objects.requireNonNull(name, "name");
        Objects.requireNonNull(category, "category");
        if (intensity < 0.0 || intensity > 1.0) {
            throw new IllegalArgumentException("intensity must be in [0, 1]: " + intensity);
        }
        if (trigger == null) trigger = "";
    }
}
```

```java
// DriveCategory.java
package io.casehub.neocortex.cognition.appraisal;

public enum DriveCategory {
    BASELINE,
    CHARACTER
}
```

```java
// ActionReadiness.java
package io.casehub.neocortex.cognition.appraisal;

public enum ActionReadiness {
    APPROACH,
    AVOIDANCE,
    ATTENDING,
    REJECTION,
    ANTAGONISM,
    INTERRUPTION,
    SUBMISSION,
    DOMINANCE,
    INDIFFERENCE
}
```

```java
// ActionTendency.java
package io.casehub.neocortex.cognition.appraisal;

import java.util.Objects;

public record ActionTendency(
    ActionReadiness readiness,
    double intensity,
    String target
) {
    public ActionTendency {
        Objects.requireNonNull(readiness, "readiness");
        if (intensity < 0.0 || intensity > 1.0) {
            throw new IllegalArgumentException("intensity must be in [0, 1]: " + intensity);
        }
        if (target == null) target = "";
    }
}
```

- [ ] **Step 4: Implement HabituationConfig and HabituationState**

```java
// HabituationConfig.java
package io.casehub.neocortex.cognition.appraisal;

import java.util.Map;

public record HabituationConfig(
    double habituationRate,
    double noveltyThreshold,
    double repetitionTolerance,
    Map<String, Double> domainModulation
) {
    public HabituationConfig {
        if (domainModulation == null) domainModulation = Map.of();
        else domainModulation = Map.copyOf(domainModulation);
    }

    public static HabituationConfig defaults() {
        return new HabituationConfig(0.2, 0.3, 5.0, Map.of());
    }
}
```

```java
// HabituationState.java
package io.casehub.neocortex.cognition.appraisal;

import java.util.Map;
import java.util.HashMap;

public record HabituationState(
    Map<String, Integer> observationCounts,
    Map<String, Double> noveltyScores
) {
    public HabituationState {
        observationCounts = observationCounts != null ? Map.copyOf(observationCounts) : Map.of();
        noveltyScores = noveltyScores != null ? Map.copyOf(noveltyScores) : Map.of();
    }

    public static HabituationState empty() {
        return new HabituationState(Map.of(), Map.of());
    }

    public HabituationState withObservation(String hash, double novelty) {
        var counts = new HashMap<>(observationCounts);
        counts.merge(hash, 1, Integer::sum);
        var scores = new HashMap<>(noveltyScores);
        scores.put(hash, novelty);
        return new HabituationState(counts, scores);
    }
}
```

- [ ] **Step 5: Write HabituationState test**

```java
package io.casehub.neocortex.cognition.appraisal;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class HabituationStateTest {

    @Test
    void emptyState() {
        var state = HabituationState.empty();
        assertTrue(state.observationCounts().isEmpty());
        assertTrue(state.noveltyScores().isEmpty());
    }

    @Test
    void withObservationIncrementsCount() {
        var state = HabituationState.empty()
            .withObservation("abc", 0.9)
            .withObservation("abc", 0.7);
        assertEquals(2, state.observationCounts().get("abc"));
        assertEquals(0.7, state.noveltyScores().get("abc"), 0.001);
    }

    @Test
    void immutability() {
        var s1 = HabituationState.empty();
        var s2 = s1.withObservation("x", 0.5);
        assertTrue(s1.observationCounts().isEmpty());
        assertEquals(1, s2.observationCounts().get("x"));
    }
}
```

- [ ] **Step 6: Implement SchererAppraisalConfig and SalienceConfig**

```java
// SchererAppraisalConfig.java
package io.casehub.neocortex.cognition.appraisal;

public record SchererAppraisalConfig(
    boolean relevanceEnabled,
    boolean implicationsEnabled,
    boolean copingEnabled,
    boolean normativeEnabled
) {
    public static SchererAppraisalConfig allEnabled() {
        return new SchererAppraisalConfig(true, true, true, true);
    }
}
```

```java
// SalienceConfig.java
package io.casehub.neocortex.cognition.appraisal;

public record SalienceConfig(
    double salienceThreshold
) {
    public static SalienceConfig defaults() {
        return new SalienceConfig(0.0);
    }
}
```

- [ ] **Step 7: Run all tests and verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api -Dtest="DriveTest,HabituationStateTest"`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/
git add cognition-api/src/test/java/io/casehub/neocortex/cognition/appraisal/
git commit -m "feat(#428): add appraisal value types — Drive, ActionTendency, HabituationConfig/State, configs

Refs #428"
```

### Task 2: SPI interfaces + context/result records

**Files:**
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/SalienceStrategy.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/SalienceContext.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/PerceivedSituation.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalStrategy.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalContext.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalResult.java`
- Test: `cognition-api/src/test/java/io/casehub/neocortex/cognition/appraisal/AppraisalResultTest.java`

**Interfaces:**
- Consumes: `Drive` (Task 1), `ActionTendency` (Task 1), `HabituationConfig/State` (Task 1), `CognitiveEmotion` (cognitive-api), `MoodState` (memory-api), `AppraisalWeights` (mindmap-api), `Memory` (memory-api)
- Produces: `SalienceStrategy` SPI, `AppraisalStrategy` SPI — consumed by `AppraisalTickParticipant` (Batch 4)

- [ ] **Step 1: Write failing test for AppraisalResult**

```java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.cognitive.CognitiveEmotion;
import io.casehub.neocortex.cognitive.EmotionType;
import io.casehub.neocortex.cognitive.EmotionSource;
import io.casehub.neocortex.cognitive.PadProjection;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class AppraisalResultTest {

    @Test
    void constructsWithEmotionsAndTendencies() {
        var emotion = new CognitiveEmotion(
            EmotionType.FEAR, 0.8, "dark-corridor", Instant.now(),
            EmotionSource.INTRINSIC, new PadProjection(-0.6, 0.7, -0.4));
        var tendency = new ActionTendency(ActionReadiness.AVOIDANCE, 0.7, "dark-corridor");
        var habituation = HabituationState.empty();

        var result = new AppraisalResult(
            List.of(emotion), List.of(tendency), habituation);

        assertEquals(1, result.emotions().size());
        assertEquals(EmotionType.FEAR, result.emotions().get(0).type());
        assertEquals(1, result.actionTendencies().size());
        assertEquals(ActionReadiness.AVOIDANCE, result.actionTendencies().get(0).readiness());
    }

    @Test
    void emptyResult() {
        var result = AppraisalResult.empty();
        assertTrue(result.emotions().isEmpty());
        assertTrue(result.actionTendencies().isEmpty());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api -Dtest=AppraisalResultTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL

- [ ] **Step 3: Implement SalienceStrategy SPI + context/result**

```java
// SalienceStrategy.java
package io.casehub.neocortex.cognition.appraisal;

@FunctionalInterface
public interface SalienceStrategy {
    PerceivedSituation perceive(SalienceContext context);
}
```

```java
// SalienceContext.java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.mood.MoodState;
import java.util.List;
import java.util.Objects;

public record SalienceContext(
    String observation,
    List<Drive> drives,
    MoodState moodState,
    List<Memory> activeConcerns,
    List<Memory> recentExperiences
) {
    public SalienceContext {
        Objects.requireNonNull(observation, "observation");
        drives = drives != null ? List.copyOf(drives) : List.of();
        activeConcerns = activeConcerns != null ? List.copyOf(activeConcerns) : List.of();
        recentExperiences = recentExperiences != null ? List.copyOf(recentExperiences) : List.of();
    }
}
```

```java
// PerceivedSituation.java
package io.casehub.neocortex.cognition.appraisal;

import java.util.Map;
import java.util.Objects;

public record PerceivedSituation(
    String narrative,
    Map<String, Double> salience
) {
    public PerceivedSituation {
        Objects.requireNonNull(narrative, "narrative");
        salience = salience != null ? Map.copyOf(salience) : Map.of();
    }

    public static PerceivedSituation passThrough(String observation) {
        return new PerceivedSituation(observation, Map.of());
    }
}
```

- [ ] **Step 4: Implement AppraisalStrategy SPI + context/result**

```java
// AppraisalStrategy.java
package io.casehub.neocortex.cognition.appraisal;

@FunctionalInterface
public interface AppraisalStrategy {
    AppraisalResult appraise(AppraisalContext context);
}
```

```java
// AppraisalContext.java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.memory.mood.MoodState;
import io.casehub.neocortex.mindmap.AppraisalWeights;
import java.util.List;
import java.util.Objects;

public record AppraisalContext(
    PerceivedSituation situation,
    List<Drive> drives,
    AppraisalWeights weights,
    HabituationConfig habituationConfig,
    HabituationState habituation,
    MoodState currentMood
) {
    public AppraisalContext {
        Objects.requireNonNull(situation, "situation");
        drives = drives != null ? List.copyOf(drives) : List.of();
    }
}
```

```java
// AppraisalResult.java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.cognitive.CognitiveEmotion;
import java.util.List;

public record AppraisalResult(
    List<CognitiveEmotion> emotions,
    List<ActionTendency> actionTendencies,
    HabituationState updatedHabituation
) {
    public AppraisalResult {
        emotions = emotions != null ? List.copyOf(emotions) : List.of();
        actionTendencies = actionTendencies != null ? List.copyOf(actionTendencies) : List.of();
        if (updatedHabituation == null) updatedHabituation = HabituationState.empty();
    }

    public static AppraisalResult empty() {
        return new AppraisalResult(List.of(), List.of(), HabituationState.empty());
    }
}
```

- [ ] **Step 5: Run tests and verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api -Dtest="AppraisalResultTest,DriveTest,HabituationStateTest"`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/
git add cognition-api/src/test/java/io/casehub/neocortex/cognition/appraisal/
git commit -m "feat(#428): add SalienceStrategy + AppraisalStrategy SPIs with context/result records

Refs #428"
```

### Task 3: CognitionConfig + CognitionTickContext extensions

**Files:**
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitionConfig.java`
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitionTickContext.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java` (if CognitionConfig has a @DefaultBean producer)
- Test: `cognition-api/src/test/java/io/casehub/neocortex/cognition/core/CognitionConfigAppraisalTest.java`

**Interfaces:**
- Consumes: existing CognitionConfig record, CognitionTickContext record
- Produces: extended CognitionConfig (3 new toggles), extended CognitionTickContext (observation field) — consumed by AppraisalTickParticipant (Batch 4)

- [ ] **Step 1: Read existing CognitionConfig and CognitionTickContext**

Use `ide_read_file` to examine the current record fields and determine how to add new fields without breaking existing callers.

- [ ] **Step 2: Write failing test for new CognitionConfig fields**

```java
package io.casehub.neocortex.cognition.core;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CognitionConfigAppraisalTest {

    @Test
    void appraisalToggleDefaultsToFalse() {
        // Construct with existing fields + new defaults
        // The exact constructor depends on existing fields — read first
        var config = CognitionConfig.builder()
            // ... existing fields ...
            .build();
        assertFalse(config.appraisalEnabled());
        assertFalse(config.salienceEnabled());
        assertFalse(config.habituationEnabled());
    }

    @Test
    void appraisalTogglesCanBeEnabled() {
        var config = CognitionConfig.builder()
            .appraisalEnabled(true)
            .salienceEnabled(true)
            .habituationEnabled(true)
            .build();
        assertTrue(config.appraisalEnabled());
        assertTrue(config.salienceEnabled());
        assertTrue(config.habituationEnabled());
    }
}
```

Note: exact test code depends on CognitionConfig's construction pattern (record vs builder). Read the file first and adapt.

- [ ] **Step 3: Add appraisalEnabled, salienceEnabled, habituationEnabled to CognitionConfig**

Use `ide_edit_member` to add the three boolean fields to the CognitionConfig record. Default all to `false` for backward compatibility.

- [ ] **Step 4: Add observation field to CognitionTickContext**

Use `ide_edit_member` to add `@Nullable String observation` to CognitionTickContext. Add a factory method or builder that existing callers can use without breaking:

```java
public static CognitionTickContext withObservation(
        String agentId, String tenantId, AgentDescriptor descriptor,
        SubjectResolver resolver, String observation) {
    return new CognitionTickContext(agentId, tenantId, descriptor, resolver, observation);
}
```

- [ ] **Step 5: Update CognitionDefaultBeans if needed**

If CognitionConfig has a `@DefaultBean` producer in CognitionDefaultBeans, update it to include the new fields with `false` defaults.

- [ ] **Step 6: Run full cognition-api tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api`
Expected: PASS (all existing + new tests)

- [ ] **Step 7: Commit**

```bash
git add cognition-api/
git commit -m "feat(#428): extend CognitionConfig with appraisal toggles, CognitionTickContext with observation

Refs #428"
```

---

## Batch 3: Drive Model Evolution

### Task 1: DriveProfile evolution + CHARACTER drive support

**Files:**
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/drive/DriveProfile.java`
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/drive/DriveIntensity.java` (may need adapter)
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveOrchestrator.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveComposer.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/prompt/DrivePromptSection.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/drive/DriveOrchestratorCharacterDriveTest.java`

**Interfaces:**
- Consumes: `Drive`, `DriveCategory` (Batch 2 Task 1), `AgentDescriptor` (eidos-api), existing DriveSource implementations
- Produces: evolved `DriveProfile` with `List<Drive>` — consumed by `SalienceContext` and `AppraisalContext` (Batch 4)

- [ ] **Step 1: Read existing DriveProfile, DriveOrchestrator, DriveComposer**

Use `ide_read_file` on all three to understand current fields, construction, and the tick/compose logic.

- [ ] **Step 2: Write failing test for CHARACTER drives in DriveOrchestrator**

```java
package io.casehub.neocortex.cognition.drive;

import io.casehub.neocortex.cognition.appraisal.Drive;
import io.casehub.neocortex.cognition.appraisal.DriveCategory;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class DriveOrchestratorCharacterDriveTest {

    @Test
    void profileIncludesBaselineAndCharacterDrives() {
        // Setup DriveOrchestrator with mocked DriveSource implementations
        // and an AgentDescriptor with CHARACTER drives defined
        // ... (exact setup depends on existing constructor — read first)

        var profile = orchestrator.currentDrives("agent1", "tenant1").orElseThrow();

        // Should contain BASELINE drives (curiosity, competence, affiliation, autonomy)
        var baselines = profile.drives().stream()
            .filter(d -> d.category() == DriveCategory.BASELINE)
            .toList();
        assertEquals(4, baselines.size());

        // Should contain CHARACTER drives from the cognitive profile
        var characters = profile.drives().stream()
            .filter(d -> d.category() == DriveCategory.CHARACTER)
            .toList();
        assertFalse(characters.isEmpty());
    }

    @Test
    void dominantDriveCanBeCharacterDrive() {
        // Setup where a CHARACTER drive has higher intensity than all BASELINE drives
        // ... (exact setup depends on reading DriveOrchestrator)

        var profile = orchestrator.currentDrives("agent1", "tenant1").orElseThrow();
        assertEquals("protection", profile.dominantDrive());
    }
}
```

Note: exact test setup depends on DriveOrchestrator's existing constructor and mock patterns. Read the file first.

- [ ] **Step 3: Evolve DriveProfile record**

Add `List<Drive> drives`, `String dominantDrive`. Keep backward compatibility by bridging from existing `Map<DriveAxis, DriveIntensity>` format. Use `ide_replace_member` to update the record.

```java
public record DriveProfile(
    String agentId,
    String tenantId,
    List<Drive> drives,
    double compositeMotivation,
    String dominantDrive,
    Instant evaluatedAt
) {
    // Backward-compatible accessor for existing consumers
    public Optional<Drive> drive(String name) {
        return drives.stream().filter(d -> d.name().equals(name)).findFirst();
    }
}
```

- [ ] **Step 4: Update DriveOrchestrator to discover CHARACTER drives**

Read CHARACTER drive definitions from `AgentDescriptor.disposition()` or `CognitiveDefaultsRegistry`. Compute intensity via `DriveComposer` pipeline (MoodState modulation). Merge with BASELINE drives into unified `List<Drive>`.

- [ ] **Step 5: Update DrivePromptSection for new DriveProfile shape**

Adapt the prompt renderer to iterate `List<Drive>` instead of `Map<DriveAxis, DriveIntensity>`.

- [ ] **Step 6: Run cognition module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: PASS (existing tests may need updates for DriveProfile shape change)

- [ ] **Step 7: Run full build to verify no downstream breakage**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Expected: BUILD SUCCESS (compilation check across all modules)

- [ ] **Step 8: Commit**

```bash
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/drive/
git add cognition/src/main/java/io/casehub/neocortex/cognition/drive/
git add cognition/src/main/java/io/casehub/neocortex/cognition/prompt/
git add cognition/src/test/java/io/casehub/neocortex/cognition/drive/
git commit -m "feat(#428): evolve DriveProfile to dynamic drives — BASELINE + CHARACTER support

Breaking change: DriveProfile now holds List<Drive> instead of Map<DriveAxis, DriveIntensity>.
Refs #428"
```

---

## Batch 4: Pipeline Wiring + Test Framework

### Task 1: NoOp SPI implementations + DefaultBeans

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/NoOpSalienceStrategy.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/NoOpAppraisalStrategy.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/NoOpStrategiesTest.java`

**Interfaces:**
- Consumes: `SalienceStrategy`, `AppraisalStrategy` SPIs (Batch 2 Task 2)
- Produces: `@DefaultBean` implementations — displaced when real implementations arrive (Batches 5-6, post-research)

- [ ] **Step 1: Write failing test for NoOp implementations**

```java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.cognition.appraisal.*;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class NoOpStrategiesTest {

    @Test
    void noOpSaliencePassesThroughObservation() {
        var strategy = new NoOpSalienceStrategy();
        var context = new SalienceContext("The room is dark", List.of(), null, List.of(), List.of());
        var result = strategy.perceive(context);
        assertEquals("The room is dark", result.narrative());
        assertTrue(result.salience().isEmpty());
    }

    @Test
    void noOpAppraisalReturnsEmpty() {
        var strategy = new NoOpAppraisalStrategy();
        var situation = PerceivedSituation.passThrough("observation");
        var context = new AppraisalContext(situation, List.of(), null, null, HabituationState.empty(), null);
        var result = strategy.appraise(context);
        assertTrue(result.emotions().isEmpty());
        assertTrue(result.actionTendencies().isEmpty());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=NoOpStrategiesTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL

- [ ] **Step 3: Implement NoOp strategies**

```java
// NoOpSalienceStrategy.java
package io.casehub.neocortex.cognition.appraisal;

public class NoOpSalienceStrategy implements SalienceStrategy {
    @Override
    public PerceivedSituation perceive(SalienceContext context) {
        return PerceivedSituation.passThrough(context.observation());
    }
}
```

```java
// NoOpAppraisalStrategy.java
package io.casehub.neocortex.cognition.appraisal;

public class NoOpAppraisalStrategy implements AppraisalStrategy {
    @Override
    public AppraisalResult appraise(AppraisalContext context) {
        return AppraisalResult.empty();
    }
}
```

- [ ] **Step 4: Register @DefaultBean producers in CognitionDefaultBeans**

Read `CognitionDefaultBeans.java` first, then add:

```java
@Produces
@DefaultBean
@Singleton
SalienceStrategy salienceStrategy() {
    return new NoOpSalienceStrategy();
}

@Produces
@DefaultBean
@Singleton
AppraisalStrategy appraisalStrategy() {
    return new NoOpAppraisalStrategy();
}
```

- [ ] **Step 5: Run tests and verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=NoOpStrategiesTest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/
git add cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/
git commit -m "feat(#428): add NoOp SalienceStrategy + AppraisalStrategy with @DefaultBean registration

Refs #428"
```

### Task 2: AppraisalTickParticipant + CognitiveAppraisalTest base class

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalTickParticipant.java`
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/AppraisalBehaviorTest.java`
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/CognitiveAppraisalTest.java` (base class)

**Interfaces:**
- Consumes: `SalienceStrategy`, `AppraisalStrategy` (Batch 4 Task 1), `DriveOrchestrator` (Batch 3), `MoodOrchestrator`, `CognitiveDefaultsRegistry`, `CognitionConfig`, `CaseMemoryStore`
- Produces: `AppraisalTickParticipant.currentResult()` — consumed by `AppraisalPromptSection` (Batch 5)

- [ ] **Step 1: Write CognitiveAppraisalTest base class**

```java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.cognition.appraisal.*;
import io.casehub.neocortex.cognitive.CognitiveEmotion;
import io.casehub.neocortex.cognitive.EmotionType;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Consumer;
import static org.junit.jupiter.api.Assertions.*;

public abstract class CognitiveAppraisalTest {

    protected ScenarioBuilder givenDisposition(DispositionPreset preset) {
        return new ScenarioBuilder(preset);
    }

    public enum DispositionPreset {
        HIGH_OPENNESS, LOW_OPENNESS, HIGH_SENSATION_SEEKING, HIGH_CONSCIENTIOUSNESS, ANY
    }

    protected static DispositionPreset highOpenness() { return DispositionPreset.HIGH_OPENNESS; }
    protected static DispositionPreset lowOpenness() { return DispositionPreset.LOW_OPENNESS; }
    protected static DispositionPreset anyDisposition() { return DispositionPreset.ANY; }

    protected static class ScenarioBuilder {
        private final DispositionPreset disposition;
        private final List<Drive> drives = new ArrayList<>();
        private String observation;
        private int repeatCount = 1;

        ScenarioBuilder(DispositionPreset disposition) {
            this.disposition = disposition;
        }

        public ScenarioBuilder withDrive(String name, double intensity) {
            drives.add(new Drive(name, DriveCategory.CHARACTER, intensity, ""));
            return this;
        }

        public ScenarioBuilder withObservation(String obs) {
            this.observation = obs;
            return this;
        }

        public ScenarioResult repeatedTimes(int n) {
            this.repeatCount = n;
            return execute();
        }

        public ScenarioResult once() {
            return execute();
        }

        private ScenarioResult execute() {
            var habConfig = habituationConfigFor(disposition);
            var results = new ArrayList<AppraisalResult>();
            var habituation = HabituationState.empty();

            for (int i = 0; i < repeatCount; i++) {
                var situation = new PerceivedSituation(observation, java.util.Map.of());
                var context = new AppraisalContext(
                    situation, drives, null, habConfig, habituation, null);
                // Use a deterministic test strategy
                var result = appraise(context, i);
                results.add(result);
                habituation = result.updatedHabituation();
            }
            return new ScenarioResult(results, observation, drives);
        }

        private AppraisalResult appraise(AppraisalContext context, int iteration) {
            // Deterministic appraisal for testing — novelty-based
            var hash = Integer.toHexString(context.situation().narrative().hashCode());
            var count = context.habituation().observationCounts().getOrDefault(hash, 0);
            var habConfig = context.habituationConfig() != null
                ? context.habituationConfig() : HabituationConfig.defaults();

            double novelty = Math.max(0, 1.0 - count * habConfig.habituationRate());
            var updatedHabituation = context.habituation().withObservation(hash, novelty);

            var emotions = new ArrayList<CognitiveEmotion>();
            var tendencies = new ArrayList<ActionTendency>();

            if (novelty > habConfig.noveltyThreshold()) {
                tendencies.add(new ActionTendency(ActionReadiness.ATTENDING, novelty, ""));
            } else {
                tendencies.add(new ActionTendency(ActionReadiness.INTERRUPTION,
                    1.0 - novelty, ""));
            }

            return new AppraisalResult(emotions, tendencies, updatedHabituation);
        }

        private HabituationConfig habituationConfigFor(DispositionPreset preset) {
            return switch (preset) {
                case HIGH_OPENNESS -> new HabituationConfig(0.4, 0.5, 3.0, java.util.Map.of());
                case LOW_OPENNESS -> new HabituationConfig(0.1, 0.2, 8.0, java.util.Map.of());
                case HIGH_SENSATION_SEEKING -> new HabituationConfig(0.5, 0.6, 2.0, java.util.Map.of());
                case HIGH_CONSCIENTIOUSNESS -> new HabituationConfig(0.1, 0.15, 10.0, java.util.Map.of());
                case ANY -> HabituationConfig.defaults();
            };
        }
    }

    protected record ScenarioResult(
        List<AppraisalResult> results,
        String observation,
        List<Drive> drives
    ) {
        public EmotionAssertions thenEmotions() { return new EmotionAssertions(results); }
        public TendencyAssertions thenActionTendency() { return new TendencyAssertions(results); }
    }

    protected static class EmotionAssertions {
        private final List<AppraisalResult> results;
        EmotionAssertions(List<AppraisalResult> results) { this.results = results; }

        public EmotionAssertions showsDecreasingEngagement() {
            // Verify novelty scores decrease over repetitions
            for (int i = 1; i < results.size(); i++) {
                var prev = maxNovelty(results.get(i - 1));
                var curr = maxNovelty(results.get(i));
                assertTrue(curr <= prev,
                    "Engagement should decrease: iteration " + i + " (" + curr + ") > iteration " + (i-1) + " (" + prev + ")");
            }
            return this;
        }

        public EmotionAssertions showsStableEngagement() {
            var first = maxNovelty(results.get(0));
            var last = maxNovelty(results.get(results.size() - 1));
            assertTrue(last > first * 0.5,
                "Engagement should remain stable: first=" + first + " last=" + last);
            return this;
        }

        public EmotionAssertions showsBoredomAfter(int n) {
            // After n repetitions, INTERRUPTION tendency should appear
            assertTrue(results.size() > n, "Not enough repetitions");
            var result = results.get(n);
            var hasInterruption = result.actionTendencies().stream()
                .anyMatch(t -> t.readiness() == ActionReadiness.INTERRUPTION);
            assertTrue(hasInterruption, "Should show boredom (INTERRUPTION) after " + n + " repetitions");
            return this;
        }

        public EmotionAssertions showsSlowerDecay() {
            // Verify novelty decays more slowly than default
            var last = maxNovelty(results.get(results.size() - 1));
            assertTrue(last > 0.3, "Should show slower decay: final novelty=" + last);
            return this;
        }

        public EmotionAssertions noBoredomBefore(int n) {
            for (int i = 0; i < n && i < results.size(); i++) {
                var hasInterruption = results.get(i).actionTendencies().stream()
                    .anyMatch(t -> t.readiness() == ActionReadiness.INTERRUPTION);
                assertFalse(hasInterruption,
                    "Should not show boredom before iteration " + n + " but found at " + i);
            }
            return this;
        }

        private double maxNovelty(AppraisalResult r) {
            return r.updatedHabituation().noveltyScores().values().stream()
                .mapToDouble(Double::doubleValue).max().orElse(1.0);
        }
    }

    protected static class TendencyAssertions {
        private final List<AppraisalResult> results;
        TendencyAssertions(List<AppraisalResult> results) { this.results = results; }

        public TendencyAssertions shifts(ActionReadiness from, ActionReadiness to) {
            var firstDominant = dominantTendency(results.get(0));
            var lastDominant = dominantTendency(results.get(results.size() - 1));
            assertEquals(from, firstDominant, "First iteration should show " + from);
            assertEquals(to, lastDominant, "Last iteration should show " + to);
            return this;
        }

        public TendencyAssertions remains(ActionReadiness expected) {
            for (int i = 0; i < results.size(); i++) {
                var dominant = dominantTendency(results.get(i));
                assertEquals(expected, dominant,
                    "Iteration " + i + " should remain " + expected + " but was " + dominant);
            }
            return this;
        }

        private ActionReadiness dominantTendency(AppraisalResult r) {
            return r.actionTendencies().stream()
                .max(java.util.Comparator.comparingDouble(ActionTendency::intensity))
                .map(ActionTendency::readiness)
                .orElse(ActionReadiness.INDIFFERENCE);
        }
    }
}
```

- [ ] **Step 2: Write AppraisalBehaviorTest scenarios**

```java
package io.casehub.neocortex.cognition.appraisal;

import org.junit.jupiter.api.Test;

class AppraisalBehaviorTest extends CognitiveAppraisalTest {

    @Test
    void highOpennessHabituatesFaster() {
        var result = givenDisposition(highOpenness())
            .withDrive("curiosity", 0.8)
            .withObservation("examining the bookshelf")
            .repeatedTimes(5);

        result.thenEmotions()
            .showsDecreasingEngagement()
            .showsBoredomAfter(3);
        result.thenActionTendency()
            .shifts(ActionReadiness.ATTENDING, ActionReadiness.INTERRUPTION);
    }

    @Test
    void lowOpennessToleratesRepetition() {
        var result = givenDisposition(lowOpenness())
            .withDrive("order", 0.7)
            .withObservation("examining the bookshelf")
            .repeatedTimes(5);

        result.thenEmotions()
            .showsStableEngagement();
        result.thenActionTendency()
            .remains(ActionReadiness.ATTENDING);
    }
}
```

- [ ] **Step 3: Run tests to verify they pass with the test framework**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=AppraisalBehaviorTest`
Expected: PASS

- [ ] **Step 4: Implement AppraisalTickParticipant**

Follow the production-quality sketch from spec §5.1. Key aspects:
- ConcurrentHashMap for per-agent state
- Config toggle checks (appraisalEnabled, salienceEnabled)
- Null-safe observation handling (skip when observation is null)
- Mood bridge via MoodSignal.DirectShift (intensity-weighted PAD averaging)
- Instance<CaseMemoryStore> for graceful degradation

```java
// AppraisalTickParticipant.java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.cognition.core.CognitionConfig;
import io.casehub.neocortex.cognition.core.CognitionTickParticipant;
import io.casehub.neocortex.cognition.core.CognitionTickContext;
import io.casehub.neocortex.cognition.drive.DriveOrchestrator;
import io.casehub.neocortex.cognition.mood.MoodOrchestrator;
import io.casehub.neocortex.cognition.mood.MoodSignal;
import io.casehub.neocortex.cognitive.CognitiveEmotion;
import io.casehub.neocortex.cognitive.index.CognitiveDefaultsRegistry;
import io.casehub.neocortex.mindmap.AppraisalWeights;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

@ApplicationScoped
public class AppraisalTickParticipant implements CognitionTickParticipant {

    private final SalienceStrategy salienceStrategy;
    private final AppraisalStrategy appraisalStrategy;
    private final DriveOrchestrator driveOrchestrator;
    private final MoodOrchestrator moodOrchestrator;
    private final CognitiveDefaultsRegistry defaultsRegistry;
    private final CognitionConfig config;

    private final ConcurrentHashMap<String, AppraisalResult> results = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, HabituationState> habituationStates = new ConcurrentHashMap<>();

    @Inject
    public AppraisalTickParticipant(
            SalienceStrategy salienceStrategy,
            AppraisalStrategy appraisalStrategy,
            DriveOrchestrator driveOrchestrator,
            MoodOrchestrator moodOrchestrator,
            CognitiveDefaultsRegistry defaultsRegistry,
            CognitionConfig config) {
        this.salienceStrategy = salienceStrategy;
        this.appraisalStrategy = appraisalStrategy;
        this.driveOrchestrator = driveOrchestrator;
        this.moodOrchestrator = moodOrchestrator;
        this.defaultsRegistry = defaultsRegistry;
        this.config = config;
    }

    @Override
    public void tick(CognitionTickContext context) {
        if (!config.appraisalEnabled()) return;

        var agentKey = context.agentId() + ":" + context.tenantId();
        var observation = context.observation();

        var drives = driveOrchestrator.currentDrives(context.agentId(), context.tenantId())
                .map(p -> p.drives()).orElse(List.of());
        if (drives.isEmpty()) return;

        var mood = moodOrchestrator.currentMood(context.agentId(), context.tenantId())
                .orElse(null);

        var defaults = defaultsRegistry.forAgentOrDefaults(context.agentId());
        var weights = defaults != null ? defaults.appraisalWeights() : null;
        var habConfig = defaults != null ? defaults.habituationConfig() : null;
        var habituation = habituationStates.getOrDefault(agentKey, HabituationState.empty());

        PerceivedSituation situation;
        if (config.salienceEnabled() && observation != null) {
            situation = salienceStrategy.perceive(
                new SalienceContext(observation, drives, mood, List.of(), List.of()));
        } else if (observation != null) {
            situation = PerceivedSituation.passThrough(observation);
        } else {
            return;
        }

        var result = appraisalStrategy.appraise(
            new AppraisalContext(situation, drives, weights, habConfig, habituation, mood));

        results.put(agentKey, result);
        habituationStates.put(agentKey, result.updatedHabituation());

        bridgeToMood(result, context);
    }

    public Optional<AppraisalResult> currentResult(String agentId, String tenantId) {
        return Optional.ofNullable(results.get(agentId + ":" + tenantId));
    }

    private void bridgeToMood(AppraisalResult result, CognitionTickContext context) {
        if (result.emotions().isEmpty()) return;

        double totalIntensity = result.emotions().stream()
                .mapToDouble(CognitiveEmotion::intensity).sum();
        if (totalIntensity <= 0) return;

        double p = result.emotions().stream()
                .mapToDouble(e -> e.intensity() * e.pad().pleasure()).sum() / totalIntensity;
        double a = result.emotions().stream()
                .mapToDouble(e -> e.intensity() * e.pad().arousal()).sum() / totalIntensity;
        double d = result.emotions().stream()
                .mapToDouble(e -> e.intensity() * e.pad().dominance()).sum() / totalIntensity;

        moodOrchestrator.record(
            new MoodSignal.DirectShift(clamp(p), clamp(a), clamp(d), "appraisal-emotions"),
            context.agentId(), context.tenantId());
    }

    private static double clamp(double value) {
        return Math.max(-2.0, Math.min(2.0, value));
    }
}
```

- [ ] **Step 5: Register AppraisalTickParticipant in CognitionCore**

Read `CognitionCore.java` to find where custom participants are registered. Add registration of `AppraisalTickParticipant` in the DERIVED phase. The exact mechanism depends on how `addParticipant()` works — read first.

- [ ] **Step 6: Run cognition module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/
git add cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/
git add cognition/src/main/java/io/casehub/neocortex/cognition/core/
git commit -m "feat(#428): add AppraisalTickParticipant + CognitiveAppraisalTest framework

Pipeline wired with NoOp implementations. Deterministic test scenarios for
personality × habituation combinations.
Refs #428"
```

---

## Batch 5: Habituation Derivation + Prompt Integration

### Task 1: CognitiveDefaults.habituationConfig + deriveHabituationConfig()

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngineHabituationTest.java`

**Interfaces:**
- Consumes: `HabituationConfig` (Batch 2 Task 1), `DescriptorView` / `DispositionAxes` (eidos-api)
- Produces: `CognitiveDefaults.habituationConfig()` — consumed by `AppraisalTickParticipant` (Batch 4 Task 2)

- [ ] **Step 1: Read existing CognitiveDefaults and CognitiveDerivationEngine**

Use `ide_read_file` on both to understand the existing record fields, derivation patterns (e.g., `deriveAppraisalWeights()`), and how new fields are added.

- [ ] **Step 2: Write failing test for habituation derivation**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognition.appraisal.HabituationConfig;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CognitiveDerivationEngineHabituationTest {

    @Test
    void highOpennessProducesFastHabituation() {
        // Construct DescriptorView — read existing test patterns in
        // CognitiveDerivationEngineTest to determine exact factory method.
        // The test below assumes a builder/factory pattern like:
        var descriptorView = DescriptorView.builder()
            .agentId("agent1")
            .dispositionAxes(DispositionAxes.builder().openness(0.9).build())
            .build();

        var config = CognitiveDerivationEngine.deriveHabituationConfig(descriptorView);

        assertTrue(config.habituationRate() > 0.3,
            "High openness should produce fast habituation rate");
        assertTrue(config.repetitionTolerance() < 4.0,
            "High openness should produce low repetition tolerance");
    }

    @Test
    void lowOpennessProducesSlowHabituation() {
        var descriptorView = DescriptorView.builder()
            .agentId("agent1")
            .dispositionAxes(DispositionAxes.builder().openness(0.1).build())
            .build();

        var config = CognitiveDerivationEngine.deriveHabituationConfig(descriptorView);

        assertTrue(config.habituationRate() < 0.15,
            "Low openness should produce slow habituation rate");
        assertTrue(config.repetitionTolerance() > 7.0,
            "Low openness should produce high repetition tolerance");
    }

    @Test
    void domainModulationFromDrives() {
        // Character drives should produce domain modulation entries
        var config = CognitiveDerivationEngine.deriveHabituationConfig(descriptorView);

        assertFalse(config.domainModulation().isEmpty(),
            "Should have domain modulation from character drives");
    }
}
```

Note: exact test setup depends on existing DescriptorView/DispositionAxes construction patterns in the test suite.

- [ ] **Step 3: Add habituationConfig field to CognitiveDefaults**

Use `ide_edit_member` to add `HabituationConfig habituationConfig` field and `withHabituationConfig()` builder method.

- [ ] **Step 4: Implement deriveHabituationConfig() in CognitiveDerivationEngine**

```java
public static HabituationConfig deriveHabituationConfig(DescriptorView view) {
    var axes = view.dispositionAxes();
    // Openness drives habituation speed
    // Higher openness → faster habituation, lower tolerance
    double openness = opennessFromProfile(view);
    double conscientiousness = conscientiousnessFromProfile(view);

    double habituationRate = 0.1 + openness * 0.4;  // [0.1, 0.5]
    double noveltyThreshold = 0.2 + openness * 0.4;  // [0.2, 0.6]
    double repetitionTolerance = 10.0 - openness * 7.0 + conscientiousness * 3.0;  // ~[3, 13]

    // Domain modulation from goals/drives
    var domainMod = new java.util.HashMap<String, Double>();
    if (view.goals() != null) {
        view.goals().forEach(goal ->
            domainMod.put(goal.toLowerCase(), 0.5)  // halve habituation in goal domains
        );
    }

    return new HabituationConfig(
        habituationRate,
        noveltyThreshold,
        Math.max(2.0, repetitionTolerance),
        domainMod
    );
}
```

Note: `opennessFromProfile()` and `conscientiousnessFromProfile()` follow existing derivation patterns — read CognitiveDerivationEngine's JPAF → Big Five chain.

- [ ] **Step 5: Wire into deriveAndMerge()**

Add `deriveHabituationConfig()` call to the existing `deriveAndMerge()` method so habituation config is derived alongside personality weights, mood baseline, etc.

- [ ] **Step 6: Run cognitive-index tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/
git add cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/
git commit -m "feat(#428): derive HabituationConfig from personality profile

New derivation pathway: openness → habituationRate/noveltyThreshold/repetitionTolerance,
goals → domainModulation.
Refs #428"
```

### Task 2: AppraisalPromptSection + CharacterDrivePromptSection conditional removal

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/prompt/AppraisalPromptSection.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java` (section registration)
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/prompt/AppraisalPromptSectionTest.java`

**Interfaces:**
- Consumes: `AppraisalTickParticipant.currentResult()` (Batch 4 Task 2), `CognitionRenderContext` (cognition-api), `CognitionConfig` (Batch 2 Task 3)
- Produces: rendered prompt section text — consumed by CognitionCore.promptSections()

- [ ] **Step 1: Write failing test for AppraisalPromptSection**

```java
package io.casehub.neocortex.cognition.prompt;

import io.casehub.neocortex.cognition.appraisal.*;
import io.casehub.neocortex.cognition.core.CognitionRenderContext;
import io.casehub.neocortex.cognitive.CognitiveEmotion;
import io.casehub.neocortex.cognitive.EmotionType;
import io.casehub.neocortex.cognitive.EmotionSource;
import io.casehub.neocortex.cognitive.PadProjection;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import static org.junit.jupiter.api.Assertions.*;

class AppraisalPromptSectionTest {

    @Test
    void rendersNullWhenNoResult() {
        var participant = mockParticipant(Optional.empty());
        var section = new AppraisalPromptSection(participant);
        var context = new CognitionRenderContext("agent1", "tenant1", null);

        assertNull(section.render(context));
    }

    @Test
    void rendersNonNullWhenResultExists() {
        var emotion = new CognitiveEmotion(
            EmotionType.FEAR, 0.8, "dark-corridor", Instant.now(),
            EmotionSource.INTRINSIC, new PadProjection(-0.6, 0.7, -0.4));
        var tendency = new ActionTendency(ActionReadiness.AVOIDANCE, 0.7, "dark-corridor");
        var result = new AppraisalResult(
            List.of(emotion), List.of(tendency), HabituationState.empty());

        var participant = mockParticipant(Optional.of(result));
        var section = new AppraisalPromptSection(participant);
        var context = new CognitionRenderContext("agent1", "tenant1", null);

        var rendered = section.render(context);
        assertNotNull(rendered);
        assertFalse(rendered.isBlank());
    }

    private AppraisalPromptSection sectionReturning(Optional<AppraisalResult> result) {
        return new AppraisalPromptSection(new AppraisalTickParticipant(
            new NoOpSalienceStrategy(), new NoOpAppraisalStrategy(),
            null, null, null, null) {
            @Override
            public Optional<AppraisalResult> currentResult(String agentId, String tenantId) {
                return result;
            }
        });
    }
}
```

Note: exact mock setup depends on AppraisalTickParticipant's constructor. May need to extract an interface or use a test subclass.

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=AppraisalPromptSectionTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL

- [ ] **Step 3: Implement AppraisalPromptSection**

```java
package io.casehub.neocortex.cognition.prompt;

import io.casehub.neocortex.cognition.appraisal.AppraisalResult;
import io.casehub.neocortex.cognition.appraisal.AppraisalTickParticipant;
import io.casehub.neocortex.cognition.core.CognitionPromptRenderer;
import io.casehub.neocortex.cognition.core.CognitionRenderContext;
import io.casehub.neocortex.cognitive.CognitiveEmotion;

public class AppraisalPromptSection implements CognitionPromptRenderer {

    private final AppraisalTickParticipant participant;

    public AppraisalPromptSection(AppraisalTickParticipant participant) {
        this.participant = participant;
    }

    @Override
    public String render(CognitionRenderContext context) {
        return participant.currentResult(context.agentId(), context.tenantId())
            .map(this::renderEvocative)
            .orElse(null);
    }

    private String renderEvocative(AppraisalResult result) {
        var sb = new StringBuilder();

        if (!result.emotions().isEmpty()) {
            sb.append("You feel ");
            var emotions = result.emotions();
            for (int i = 0; i < emotions.size(); i++) {
                if (i > 0) sb.append(i == emotions.size() - 1 ? " and " : ", ");
                sb.append(describeEmotion(emotions.get(i)));
            }
            sb.append(".\n");
        }

        if (!result.actionTendencies().isEmpty()) {
            result.actionTendencies().stream()
                .filter(t -> t.intensity() > 0.3)
                .forEach(t -> sb.append(describeTendency(t)).append("\n"));
        }

        return sb.isEmpty() ? null : sb.toString().strip();
    }

    private String describeEmotion(CognitiveEmotion emotion) {
        var intensity = emotion.intensity() > 0.7 ? "strong " :
                       emotion.intensity() > 0.4 ? "" : "mild ";
        return intensity + emotion.type().name().toLowerCase().replace('_', ' ');
    }

    private String describeTendency(io.casehub.neocortex.cognition.appraisal.ActionTendency t) {
        return switch (t.readiness()) {
            case APPROACH -> "You feel drawn toward " + t.target() + ".";
            case AVOIDANCE -> "You want to get away from " + t.target() + ".";
            case ATTENDING -> "Your attention is fixed on " + t.target() + ".";
            case REJECTION -> "You feel repelled by " + t.target() + ".";
            case ANTAGONISM -> "You feel combative toward " + t.target() + ".";
            case INTERRUPTION -> "Your attention wanders — you want something new.";
            case SUBMISSION -> "You feel like yielding to " + t.target() + ".";
            case DOMINANCE -> "You feel like asserting control over " + t.target() + ".";
            case INDIFFERENCE -> "You feel nothing about " + t.target() + ".";
        };
    }
}
```

Note: this is the initial evocative renderer. The real implementation will likely need LLM-backed narrative generation for production quality — this provides a deterministic baseline that tests can assert against.

- [ ] **Step 4: Wire into CognitionCore prompt sections**

Read `CognitionCore.java` to find `promptSections()` or `chainSectionCustomizer()`. Add:

```java
cognitionCore.chainSectionCustomizer(sections -> {
    if (config.appraisalEnabled()) {
        sections.add(new AppraisalPromptSection(appraisalParticipant));
        sections.removeIf(s -> s instanceof CharacterDrivePromptSection);
    }
    return sections;
});
```

Or add directly in `promptSections()` with a config check, following existing patterns.

- [ ] **Step 5: Run all cognition tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: PASS

- [ ] **Step 6: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS + all tests pass

- [ ] **Step 7: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/prompt/
git add cognition/src/main/java/io/casehub/neocortex/cognition/core/
git add cognition/src/test/java/io/casehub/neocortex/cognition/prompt/
git commit -m "feat(#428): add AppraisalPromptSection — evocative emotion rendering

Conditionally removes CharacterDrivePromptSection when appraisal is enabled.
Refs #428"
```

---

## Post-Batch 5: Research-Dependent Implementation

Batches 1-5 deliver:
- Research synthesis document (Batch 1)
- Complete SPI surface in cognition-api (Batch 2)
- Dynamic drive model (Batch 3)
- Wired pipeline with NoOp implementations + deterministic test framework (Batch 4)
- Habituation derivation + prompt rendering (Batch 5)

**Remaining work (requires follow-up plan after research):**
- `DefaultSalienceStrategy` — real perception fusion (spec Stage 3). Research determines LLM involvement.
- `SchererAppraisalStrategy` — real SEC pipeline (spec Stage 4). Research determines which SECs, computational/LLM boundary.
- Production-quality evocative rendering — may need LLM-backed narrative generation.
- Wacky-manor integration testing — requires access to examples repo.

These items will be planned in a follow-up plan after Stage 1 research synthesis is complete. The NoOp implementations ensure the pipeline is structurally complete and testable — real implementations displace them via CDI @Alternative priority.

---

## References

- [2026-10-04-cognitive-appraisal-architecture-design.md] — design spec this plan implements
- [decisions.md] — 13 design decisions
- [cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitionTickParticipant.java] — tick participant SPI
- [cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java] — composition root
- [cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveOrchestrator.java] — drive computation
- [cognition-api/src/main/java/io/casehub/neocortex/cognition/drive/DriveProfile.java] — drive output shape
- [cognitive-api/src/main/java/io/casehub/neocortex/cognitive/CognitiveEmotion.java] — emotion output type
- [cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java] — personality derivation
- [cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java] — per-agent config
- [cognition/src/main/java/io/casehub/neocortex/cognition/mood/GoalEmotionMoodBridge.java] — mood bridge pattern
- [caps-testing/src/main/java/io/casehub/neocortex/caps/testing/CognitiveEmergenceTest.java] — test framework reference
- [mindmap-api/src/main/java/io/casehub/neocortex/mindmap/AppraisalWeights.java] — personality-derived appraisal thresholds
- [GitHub #428] — focal issue
- [GitHub #407] — psychology cause-effect models (consolidation-time synthesis to build on)
- [GitHub #383] — OCC GoalAppraisal/ActionAppraisal SPIs
- [GitHub #408] — CAPS engine implementation

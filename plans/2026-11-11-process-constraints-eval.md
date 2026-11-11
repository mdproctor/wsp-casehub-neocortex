# Process Constraints for Eval Suite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #933 — Apply process constraint technique to wider eval suite failures
**Issue group:** #933

**Goal:** Apply the proven process constraint technique (from #905) to five
failing eval test areas, achieving ≥80% pass rate on each.

**Architecture:** Process constraints are injected into LLM prompts at the
point where strategy selection happens. Instead of describing cognitive
limitations ("load is HIGH"), the constraints tell the LLM what reasoning
processes it cannot perform ("you cannot hold the multi-step chain needed
for COGNITIVE_CHANGE"). One code fix adds a description rendering fallback
in `CognitionObservationBuilder`.

**Tech Stack:** Java 21, Quarkus, LangChain4j, IntelliJ MCP for code navigation and editing

## Global Constraints

- All process constraint text must be written in second person, present tense
- Process constraints tell the model what it CANNOT DO, not what it should prefer
- No new module dependencies — all changes are within existing modules
- Tests are `@Tag("llm-eval")` and require Claude API access — unit tests for prompt content can run without LLM

---

## Batch 1: Drive rendering fallback + cognitive load constraint

### Task 1: Drive rendering fallback in CognitionObservationBuilder

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/prompt/observation/CognitionObservationBuilder.java:196-205`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/prompt/observation/CognitionObservationBuilderDescriptionFallbackTest.java`

**Interfaces:**
- Consumes: `DriveSnapshot.description()` (existing), `readGeneratedDriveDescriptions()` (existing)
- Produces: Modified `renderInternalState()` that falls back to `DriveSnapshot.description()` when no `DriveDescriptionGenerated` node exists

- [ ] **Step 1: Write the failing test**

Create a test that seeds drives with descriptions but NO `DriveDescriptionGenerated` nodes, renders internal state, and asserts the description text appears.

```java
package io.casehub.neocortex.cognition.prompt.observation;

import io.casehub.neocortex.caps.SituationContext;
import io.casehub.neocortex.mindmap.NodeInput;
import io.casehub.neocortex.mindmap.SubgraphInput;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class CognitionObservationBuilderDescriptionFallbackTest {

    @Test
    void renderInternalState_fallsBackToDriveDescription_whenNoGeneratedDescriptionExists() {
        var store = new InMemoryMindMapStore();
        String tenant = "test-tenant";
        var sgId = store.createSubgraph(
                new SubgraphInput("cognitive-test", SubgraphTypes.COGNITIVE, null), tenant);

        String description = "There's a clarity that comes when a plan locks into place.";
        store.addNode(NodeInput.of("scheming", sgId)
                .withProperties(Map.of(
                        "cognitiveKind", "drive-intensity",
                        "agent-id", "test-agent",
                        "drive-type", "scheming",
                        "intensity", "0.9",
                        "description", description)), tenant);

        var baseDrives = List.of(
                new DriveSnapshot("scheming", 0.9, description));
        var builder = new CognitionObservationBuilder(
                "test-agent", tenant, store, null, null, baseDrives);

        var section = builder.renderInternalState(
                List.of(), "A quiet room with blueprints.",
                List.of(), SituationContext.EMPTY);

        assertThat(section).isNotNull();
        var text = switch (section) {
            case ObservationSection.TextBlock tb -> tb.content();
            default -> section.toString();
        };
        assertThat(text).contains(description);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=CognitionObservationBuilderDescriptionFallbackTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — the description text is not in the rendered output

- [ ] **Step 3: Add description fallback in targetedDescriptionFor lambda**

In `CognitionObservationBuilder.renderInternalState()`, modify the `targetedDescriptionFor` lambda to fall back to `d.description()`:

```java
// After line 200: if (generated == null) { generated = generatedDescriptions.get(d.type()); }
// Add fallback:
if (generated == null && d.description() != null && !d.description().isBlank()) {
    generated = d.description();
}
```

The exact edit in the `targetedDescriptionFor` lambda (around line 196-205):

Replace:
```java
                    if (generated == null) {
                        generated = generatedDescriptions.get(d.type());
                    }
                    if (generated != null) {
```

With:
```java
                    if (generated == null) {
                        generated = generatedDescriptions.get(d.type());
                    }
                    if (generated == null && d.description() != null && !d.description().isBlank()) {
                        generated = d.description();
                    }
                    if (generated != null) {
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=CognitionObservationBuilderDescriptionFallbackTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: PASS

- [ ] **Step 5: Run full cognition module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: All existing tests pass (no regressions)

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/prompt/observation/CognitionObservationBuilder.java cognition/src/test/java/io/casehub/neocortex/cognition/prompt/observation/CognitionObservationBuilderDescriptionFallbackTest.java
git commit -m "feat(#933): add drive description fallback in renderInternalState

When no DriveDescriptionGenerated MindMap node exists, fall back to
the drive's own description from DriveSnapshot. Fixes 12/12 failures
in DriveProfilePipelineTest where descriptions were seeded but never
rendered.

Refs #933"
```

### Task 2: Cognitive load process constraint in EmotionRegulationGenerationPhase

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationGenerationPhase.java:451-457`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationGenerationPhaseLoadConstraintTest.java`

**Interfaces:**
- Consumes: `CognitiveLoadEstimate.level()` (existing), `CognitiveLoadLevel.HIGH` (existing)
- Produces: Modified `buildUserMessage()` that appends process constraint text when load is HIGH

- [ ] **Step 1: Write the failing test**

```java
package io.casehub.neocortex.cognition.regulation;

import io.casehub.neocortex.cognition.appraisal.AppraisalResult;
import io.casehub.neocortex.cognition.appraisal.HabituationState;
import io.casehub.neocortex.cognition.core.CognitionTickContext;
import io.casehub.neocortex.cognitive.CognitiveEmotion;
import io.casehub.neocortex.cognitive.EmotionSource;
import io.casehub.neocortex.cognitive.EmotionType;
import io.casehub.neocortex.cognitive.PadProjection;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class EmotionRegulationGenerationPhaseLoadConstraintTest {

    @Test
    void highLoad_includesProcessConstraint() {
        var context = new CognitionTickContext("test-agent", "test-tenant", null,
                (a, t) -> Set.of());
        var emotion = new CognitiveEmotion(EmotionType.ANGER, 0.6, "confrontation",
                Instant.now(), EmotionSource.INTRINSIC, PadProjection.NEUTRAL);
        var appraisal = new AppraisalResult(List.of(emotion), List.of(),
                HabituationState.empty());
        var highLoad = new CognitiveLoadEstimate(CognitiveLoadLevel.HIGH, 4, 3, 3);

        String message = EmotionRegulationGenerationPhase.buildUserMessage(
                context, appraisal, List.of(), 0.5, highLoad, 0.0, null);

        assertThat(message).contains("cannot hold the multi-step reasoning");
        assertThat(message).contains("ATTENTIONAL_DEPLOYMENT");
        assertThat(message).contains("RESPONSE_MODULATION");
    }

    @Test
    void lowLoad_doesNotIncludeProcessConstraint() {
        var context = new CognitionTickContext("test-agent", "test-tenant", null,
                (a, t) -> Set.of());
        var emotion = new CognitiveEmotion(EmotionType.ANGER, 0.6, "confrontation",
                Instant.now(), EmotionSource.INTRINSIC, PadProjection.NEUTRAL);
        var appraisal = new AppraisalResult(List.of(emotion), List.of(),
                HabituationState.empty());
        var lowLoad = new CognitiveLoadEstimate(CognitiveLoadLevel.LOW, 1, 0, 0);

        String message = EmotionRegulationGenerationPhase.buildUserMessage(
                context, appraisal, List.of(), 0.5, lowLoad, 0.0, null);

        assertThat(message).doesNotContain("cannot hold the multi-step reasoning");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=EmotionRegulationGenerationPhaseLoadConstraintTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — process constraint text not present

- [ ] **Step 3: Add process constraint after cognitive load block**

In `EmotionRegulationGenerationPhase.buildUserMessage()`, after the existing load block (line 457), add:

```java
        if (loadEstimate != null && loadEstimate.level() == CognitiveLoadLevel.HIGH) {
            sb.append("Under HIGH cognitive load, you cannot hold the multi-step reasoning ")
              .append("chain needed for COGNITIVE_CHANGE or the environmental assessment ")
              .append("needed for SITUATION_SELECTION/MODIFICATION. These strategies require ")
              .append("deliberation you don't have capacity for right now. Only ")
              .append("ATTENTIONAL_DEPLOYMENT (automatic attention shift) and ")
              .append("RESPONSE_MODULATION (expression control) are executable — they're ")
              .append("reflexive, not deliberative. You MUST choose one of these two.\n\n");
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=EmotionRegulationGenerationPhaseLoadConstraintTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: PASS

- [ ] **Step 5: Update CognitiveLoadStrategyEvalTest system prompt**

Mirror the process constraint in the standalone test's SYSTEM prompt. In
`caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/eval/CognitiveLoadStrategyEvalTest.java`,
replace the existing cognitive load guidance (lines 49-51):

Replace:
```java
            - Cognitive load constrains strategy: HIGH load → prefer ATTENTIONAL_DEPLOYMENT \
            or RESPONSE_MODULATION (low cognitive cost); LOW load → COGNITIVE_CHANGE \
            or SITUATION_SELECTION are viable (require deliberation)
```

With:
```java
            - Cognitive load constrains strategy: HIGH load → you cannot hold the \
            multi-step reasoning chain needed for COGNITIVE_CHANGE or the environmental \
            assessment needed for SITUATION_SELECTION/MODIFICATION. Only \
            ATTENTIONAL_DEPLOYMENT and RESPONSE_MODULATION are executable — they're \
            reflexive, not deliberative. You MUST choose one of these two. \
            LOW load → COGNITIVE_CHANGE or SITUATION_SELECTION are viable (require deliberation)
```

- [ ] **Step 6: Run full cognition module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationGenerationPhase.java cognition/src/test/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationGenerationPhaseLoadConstraintTest.java caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/eval/CognitiveLoadStrategyEvalTest.java
git commit -m "feat(#933): add cognitive load process constraint for regulation strategy

When cognitive load is HIGH, tell the LLM what reasoning processes it
cannot perform rather than describing a preference. Mirrors the proven
renderCapacityTrait() approach from #905.

Refs #933"
```

---

## Batch 2: Fatigue + strategy differentiation process constraints

### Task 3: Fatigue process constraint in EmotionRegulationGenerationPhase

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationGenerationPhase.java:442-449`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationGenerationPhaseFatigueConstraintTest.java`

**Interfaces:**
- Consumes: `regulationFatigue` (double, 0.0-1.0, existing parameter)
- Produces: Modified `buildUserMessage()` with graded process constraint text at fatigue > 0.5

- [ ] **Step 1: Write the failing test**

```java
package io.casehub.neocortex.cognition.regulation;

import io.casehub.neocortex.cognition.appraisal.AppraisalResult;
import io.casehub.neocortex.cognition.appraisal.HabituationState;
import io.casehub.neocortex.cognition.core.CognitionTickContext;
import io.casehub.neocortex.cognitive.CognitiveEmotion;
import io.casehub.neocortex.cognitive.EmotionSource;
import io.casehub.neocortex.cognitive.EmotionType;
import io.casehub.neocortex.cognitive.PadProjection;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class EmotionRegulationGenerationPhaseFatigueConstraintTest {

    @Test
    void moderateFatigue_includesDepletionWarning() {
        String message = buildMessage(0.6);
        assertThat(message).contains("reappraisal capacity is running low");
        assertThat(message).doesNotContain("MUST choose ATTENTIONAL_DEPLOYMENT");
    }

    @Test
    void severeFatigue_includesMandatoryConstraint() {
        String message = buildMessage(0.8);
        assertThat(message).contains("reappraisal capacity is depleted");
        assertThat(message).contains("MUST choose ATTENTIONAL_DEPLOYMENT");
    }

    @Test
    void lowFatigue_noProcessConstraint() {
        String message = buildMessage(0.3);
        assertThat(message).doesNotContain("reappraisal capacity");
        assertThat(message).contains("Regulation fatigue: 30%");
    }

    private String buildMessage(double fatigue) {
        var context = new CognitionTickContext("test-agent", "test-tenant", null,
                (a, t) -> Set.of());
        var emotion = new CognitiveEmotion(EmotionType.ANGER, 0.6, "confrontation",
                Instant.now(), EmotionSource.INTRINSIC, PadProjection.NEUTRAL);
        var appraisal = new AppraisalResult(List.of(emotion), List.of(),
                HabituationState.empty());
        return EmotionRegulationGenerationPhase.buildUserMessage(
                context, appraisal, List.of(), 0.5, null, fatigue, null);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=EmotionRegulationGenerationPhaseFatigueConstraintTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL

- [ ] **Step 3: Replace fatigue block with graded process constraint**

In `EmotionRegulationGenerationPhase.buildUserMessage()`, replace the fatigue block (lines 442-449):

Replace:
```java
        if (regulationFatigue > 0.01) {
            sb.append("Regulation fatigue: ").append(String.format("%.0f%%", regulationFatigue * 100))
              .append(" — repeated regulation is depleting capacity");
            if (regulationFatigue > 0.7) {
                sb.append("; approaching breakdown, suppression may fail entirely");
            }
            sb.append("\n\n");
        }
```

With:
```java
        if (regulationFatigue > 0.7) {
            sb.append("Your reappraisal capacity is depleted. Trying to reframe the situation ")
              .append("no longer works — the cognitive effort required for COGNITIVE_CHANGE has ")
              .append("run dry. SITUATION_SELECTION requires environmental assessment you can't ")
              .append("sustain. Only ATTENTIONAL_DEPLOYMENT remains as a regulation tool — ")
              .append("shifting your focus is reflexive and doesn't require the cognitive ")
              .append("resources you've exhausted. You MUST choose ATTENTIONAL_DEPLOYMENT.\n\n");
        } else if (regulationFatigue > 0.5) {
            sb.append("Your reappraisal capacity is running low. COGNITIVE_CHANGE requires ")
              .append("deliberate effort to find alternative interpretations — each attempt is ")
              .append("slower and less convincing than the last. You can still try, but the ")
              .append("cognitive work feels heavy. ATTENTIONAL_DEPLOYMENT and ")
              .append("RESPONSE_MODULATION require less effort.\n\n");
        } else if (regulationFatigue > 0.01) {
            sb.append("Regulation fatigue: ").append(String.format("%.0f%%", regulationFatigue * 100))
              .append(" — repeated regulation is depleting capacity\n\n");
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=EmotionRegulationGenerationPhaseFatigueConstraintTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: PASS

- [ ] **Step 5: Run full cognition module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationGenerationPhase.java cognition/src/test/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationGenerationPhaseFatigueConstraintTest.java
git commit -m "feat(#933): add graded fatigue process constraint for regulation

Replace descriptive fatigue text with procedural constraints:
moderate (>0.5) warns reappraisal capacity is running low, severe
(>0.7) mandates ATTENTIONAL_DEPLOYMENT as only executable strategy.

Refs #933"
```

### Task 4: Strategy differentiation process constraint

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationGenerationPhase.java:485-493`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationGenerationPhaseStrategyConstraintTest.java`

**Interfaces:**
- Consumes: `RegulationDefaults.reappraisalCapacity()`, `.suppressionCapacity()`, `.redirectTendency()` (existing)
- Produces: Modified `buildUserMessage()` that renders personality-specific process constraint when the dominant capacity is clear and no pinned strategy exists

- [ ] **Step 1: Write the failing test**

```java
package io.casehub.neocortex.cognition.regulation;

import io.casehub.neocortex.cognition.appraisal.AppraisalResult;
import io.casehub.neocortex.cognition.appraisal.HabituationState;
import io.casehub.neocortex.cognition.core.CognitionTickContext;
import io.casehub.neocortex.cognitive.CognitiveEmotion;
import io.casehub.neocortex.cognitive.EmotionSource;
import io.casehub.neocortex.cognitive.EmotionType;
import io.casehub.neocortex.cognitive.PadProjection;
import io.casehub.neocortex.cognitive.index.DispositionAxes;
import io.casehub.neocortex.cognitive.index.RegulationDefaults;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class EmotionRegulationGenerationPhaseStrategyConstraintTest {

    @Test
    void highSuppression_rendersResponseModulationConstraint() {
        var rd = new RegulationDefaults(0.35, 0.80, 0.40);
        var axes = new DispositionAxes("competitive", "strict", "conservative", "high", "competitive");

        String message = buildMessage(rd, axes, EmotionType.ANGER);

        assertThat(message).contains("control the outward expression");
        assertThat(message).contains("RESPONSE_MODULATION");
    }

    @Test
    void highReappraisal_rendersCognitiveChangeConstraint() {
        var rd = new RegulationDefaults(0.80, 0.40, 0.30);
        var axes = new DispositionAxes("cooperative", "flexible", "conservative", "high", "accommodating");

        String message = buildMessage(rd, axes, EmotionType.ANGER);

        assertThat(message).contains("step back and reframe");
        assertThat(message).contains("COGNITIVE_CHANGE");
    }

    @Test
    void highRedirect_rendersAttentionalDeploymentConstraint() {
        var rd = new RegulationDefaults(0.30, 0.30, 0.80);
        var axes = new DispositionAxes("cooperative", "flexible", "bold", "low", "protective");

        String message = buildMessage(rd, axes, EmotionType.FEAR);

        assertThat(message).contains("shift what you're focusing on");
        assertThat(message).contains("ATTENTIONAL_DEPLOYMENT");
    }

    @Test
    void tiedCapacities_noStrategyConstraint() {
        var rd = new RegulationDefaults(0.70, 0.70, 0.30);
        var axes = new DispositionAxes("cooperative", "flexible", "conservative", "high", "accommodating");

        String message = buildMessage(rd, axes, EmotionType.ANGER);

        assertThat(message).doesNotContain("Your instinct is to");
    }

    private String buildMessage(RegulationDefaults rd, DispositionAxes axes, EmotionType emotionType) {
        var context = new CognitionTickContext("test-agent", "test-tenant", null,
                (a, t) -> Set.of());
        var emotion = new CognitiveEmotion(emotionType, 0.55, "test-subject",
                Instant.now(), EmotionSource.INTRINSIC, PadProjection.NEUTRAL);
        var appraisal = new AppraisalResult(List.of(emotion), List.of(),
                HabituationState.empty());
        return EmotionRegulationGenerationPhase.buildUserMessage(
                context, appraisal, List.of(), 0.5, null,
                0.0, null, null, axes, emotionType,
                rd, null, null);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=EmotionRegulationGenerationPhaseStrategyConstraintTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL

- [ ] **Step 3: Add strategy differentiation process constraint**

In `EmotionRegulationGenerationPhase.buildUserMessage()`, after the existing regulation capacities block (after line 493), add:

```java
        if (pinnedStrategy == null && regulationDefaults != null) {
            double reap = regulationDefaults.reappraisalCapacity();
            double supp = regulationDefaults.suppressionCapacity();
            double redir = regulationDefaults.redirectTendency();
            boolean isControllableNegLocal = dominantEmotionType != null
                    && RegulationStrategyPredictor.emotionCategory(dominantEmotionType)
                            == RegulationStrategyPredictor.EmotionCategory.CONTROLLABLE_NEGATIVE;
            boolean temporalStagingApplies = isControllableNegLocal && reap >= 0.40;
            if (!temporalStagingApplies) {
                double max = Math.max(reap, Math.max(supp, redir));
                boolean tied = (max == reap && max == supp)
                            || (max == reap && max == redir)
                            || (max == supp && max == redir);
                if (!tied && max >= 0.6) {
                    if (max == supp) {
                        sb.append("Your instinct is to control the outward expression. You feel the ")
                          .append("emotion fully inside but your face stays steady, your voice stays ")
                          .append("level. You manage the display, not the feeling. Choose ")
                          .append("RESPONSE_MODULATION.\n\n");
                    } else if (max == reap) {
                        sb.append("Your instinct is to step back and reframe. You search for an ")
                          .append("alternative interpretation — why might this not mean what it first ")
                          .append("seemed? The reappraisal comes naturally. Choose COGNITIVE_CHANGE.\n\n");
                    } else {
                        sb.append("Your instinct is to shift what you're focusing on. Not to leave, ")
                          .append("not to suppress — but to redirect attention away from the triggering ")
                          .append("stimulus. Choose ATTENTIONAL_DEPLOYMENT.\n\n");
                    }
                }
            }
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=EmotionRegulationGenerationPhaseStrategyConstraintTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: PASS

- [ ] **Step 5: Run full cognition module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationGenerationPhase.java cognition/src/test/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationGenerationPhaseStrategyConstraintTest.java
git commit -m "feat(#933): add strategy differentiation process constraint

When predictor falls through to LLM and a dominant regulation capacity
is clear (≥0.6, no tie), render a personality-specific process
constraint describing what the character's natural regulation feels
like. Skips when temporal staging already applies.

Refs #933"
```

---

## Batch 3: Eval verification + coherence assessment

### Task 5: Verify build and assess coherence

**Files:**
- No new files — verification only

**Interfaces:**
- Consumes: All changes from Tasks 1-4

- [ ] **Step 1: Full build verification**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Expected: BUILD SUCCESS across all modules

- [ ] **Step 2: Run all cognition module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: All tests pass

- [ ] **Step 3: Run caps-llm-classifier compile**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile test-compile -pl caps-llm-classifier`
Expected: Compilation succeeds (eval tests compile but are not run — they need LLM access)

- [ ] **Step 4: Document remaining assessment**

The PipelineCoherenceEvalTest (Intervention 5) requires running the full
eval suite with LLM access to assess whether upstream fixes resolved the
3/4 coherence failures. Document this as a follow-up step in the issue:

> After merging, run the full eval suite:
> `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-llm-classifier -Dgroups=llm-eval`
>
> Expected: ≥80% pass rate across all test classes.
> If PipelineCoherenceEvalTest still fails 2+ scenarios, file a follow-up
> issue for dedicated coherence process constraints.

- [ ] **Step 5: Commit assessment note**

No code changes — this is verification only. If all previous commits are
clean, no additional commit needed.

---

## References

- [2026-11-11-process-constraints-eval-design.md] — design spec this plan implements
- [EmotionRegulationGenerationPhase.java:442-493] — regulation prompt assembly
- [CognitionObservationBuilder.java:196-205] — drive rendering pipeline
- [SearchBudgetPromptSection.java:213-229] — proven process constraint pattern
- [CognitiveLoadStrategyEvalTest.java] — standalone eval test
- [GitHub #933] — parent issue
- [GitHub #905] — established the process constraint technique

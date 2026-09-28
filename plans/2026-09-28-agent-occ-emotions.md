# Agent-based OCC Emotions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #383 — Agent-based OCC emotions — Pride, Shame, Admiration, Reproach
**Issue group:** #383

**Goal:** Implement the OCC action → standards appraisal branch, producing Pride, Shame, Admiration, Reproach (base) and Gratification, Remorse, Gratitude, Anger (compound) emotions from agent actions evaluated against goal-derived standards with personality modulation.

**Architecture:** New `ActionAppraisal` SPI in mindmap-api parallel to `GoalAppraisal`. `HeuristicActionAppraisal` in mindmap-intelligence scores praiseworthiness from goal relevance with asymmetric personality-modulated thresholds and inline compound detection. `ActionAppraisalObserver` CDI observer fires in real-time on `ExperienceRecorded` (Outcome events), with dual-path logic for self-appraisal (Pride/Shame) and other-appraisal (Admiration/Reproach via TARGET_AGENT metadata).

**Tech Stack:** Java 21, Quarkus CDI, JUnit 5, AssertJ

## Global Constraints

- Java 21 language features (on Java 26 JVM)
- Pre-release project — breaking changes acceptable
- `AppraisalWeights` 3-arg → 5-arg constructor is a breaking change; all call sites must be updated
- All new types follow existing package conventions: SPI in mindmap-api (`io.casehub.neocortex.mindmap`), implementation in mindmap-intelligence (`io.casehub.neocortex.mindmap.intelligence`)
- PAD projections for all emotion types already exist in `AlmaPadTable` — no additions needed
- `EmotionType` enum already declares PRIDE, SHAME, ADMIRATION, REPROACH, GRATIFICATION, REMORSE, GRATITUDE, ANGER — no additions needed

---

## Batch 1: API Foundation — types and breaking changes

After this batch: all new API types compile, existing code updated for AppraisalWeights 5-arg constructor, build green with no behavioral change.

### Task 1: Extend AppraisalWeights with standards strictness fields

**Files:**
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/AppraisalWeights.java`
- Modify: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/AppraisalWeightsTest.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/HeuristicGoalAppraisalTest.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java:370`
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngineTest.java:622`

**Interfaces:**
- Produces: `AppraisalWeights(double, double, double, double, double)` — 5-arg constructor with `selfStandardsStrictness` and `otherStandardsStrictness` fields, validated to [0.5, 2.0]. `NEUTRAL` constant = `(1.0, 1.0, 1.0, 1.0, 1.0)`.

- [ ] **Step 1: Write failing test for 5-arg constructor and validation**

Add to `AppraisalWeightsTest.java`:

```java
@Test
void standardsStrictnessFieldsAccepted() {
    var w = new AppraisalWeights(1.0, 1.0, 1.0, 1.5, 0.8);
    assertThat(w.selfStandardsStrictness()).isEqualTo(1.5);
    assertThat(w.otherStandardsStrictness()).isEqualTo(0.8);
}

@Test
void selfStandardsStrictnessBelowMinThrows() {
    assertThatThrownBy(() -> new AppraisalWeights(1.0, 1.0, 1.0, 0.4, 1.0))
            .isInstanceOf(IllegalArgumentException.class);
}

@Test
void otherStandardsStrictnessAboveMaxThrows() {
    assertThatThrownBy(() -> new AppraisalWeights(1.0, 1.0, 1.0, 1.0, 2.1))
            .isInstanceOf(IllegalArgumentException.class);
}

@Test
void neutralIncludesStandardsStrictness() {
    assertThat(AppraisalWeights.NEUTRAL.selfStandardsStrictness()).isEqualTo(1.0);
    assertThat(AppraisalWeights.NEUTRAL.otherStandardsStrictness()).isEqualTo(1.0);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=AppraisalWeightsTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation error — `AppraisalWeights` only has 3 components.

- [ ] **Step 3: Update AppraisalWeights record**

In `AppraisalWeights.java`, replace the record declaration and compact constructor:

```java
public record AppraisalWeights(
    double urgencyWeight,
    double relationshipWeight,
    double fearOnsetThreshold,
    double selfStandardsStrictness,
    double otherStandardsStrictness
) {
    public static final AppraisalWeights NEUTRAL =
        new AppraisalWeights(1.0, 1.0, 1.0, 1.0, 1.0);

    public AppraisalWeights {
        if (urgencyWeight <= 0.0)
            throw new IllegalArgumentException("urgencyWeight must be positive");
        if (relationshipWeight <= 0.0)
            throw new IllegalArgumentException("relationshipWeight must be positive");
        if (fearOnsetThreshold <= 0.0)
            throw new IllegalArgumentException("fearOnsetThreshold must be positive");
        if (selfStandardsStrictness < 0.5 || selfStandardsStrictness > 2.0)
            throw new IllegalArgumentException("selfStandardsStrictness must be in [0.5, 2.0]");
        if (otherStandardsStrictness < 0.5 || otherStandardsStrictness > 2.0)
            throw new IllegalArgumentException("otherStandardsStrictness must be in [0.5, 2.0]");
    }
}
```

- [ ] **Step 4: Fix all existing 3-arg constructor call sites**

All existing `new AppraisalWeights(a, b, c)` calls must become `new AppraisalWeights(a, b, c, 1.0, 1.0)`. These are:

- `AppraisalWeightsTest.java` — lines 34, 43, 49, 55 (4 call sites)
- `HeuristicGoalAppraisalTest.java` — lines 196, 200, 211, 215, 226, 230, 240, 245, 256, 260 (10 call sites)
- `CognitiveDerivationEngine.java:370` — inside `deriveAppraisalWeights()` return statement
- `CognitiveDerivationEngineTest.java:622` — test assertion

For `CognitiveDerivationEngine.java:370`, the return statement becomes:
```java
return new AppraisalWeights(
    Math.max(1.0 + urgencyRaw * SCALE_FACTOR, 0.1),
    Math.max(1.0 + relRaw * SCALE_FACTOR, 0.1),
    Math.max(1.0 + fearRaw * SCALE_FACTOR, 0.1),
    1.0, 1.0
);
```

The standards strictness derivation from DispositionAxes happens in Task 4.

- [ ] **Step 5: Run full build to verify all modules compile**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api,mindmap-intelligence,cognitive-index -Dsurefire.failIfNoSpecifiedTests=false`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```
git -C <PROJECT> add mindmap-api/ mindmap-intelligence/ cognitive-index/
git -C <PROJECT> commit -m "feat(#383): extend AppraisalWeights with standards strictness fields

Add selfStandardsStrictness and otherStandardsStrictness [0.5, 2.0]
to AppraisalWeights. Update all constructor call sites. No behavioral
change — new fields default to 1.0 (NEUTRAL).

Refs #383"
```

### Task 2: New API types — ActionOutcome, ActionContext, ActionAppraisal, EmotionSource.ATTRIBUTED, OUTCOME_STATUS

**Files:**
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ActionOutcome.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ActionContext.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ActionAppraisal.java`
- Create: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/ActionContextTest.java`
- Modify: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/EmotionSource.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/experience/ExperienceAttributeKeys.java`

**Interfaces:**
- Produces: `ActionAppraisal` SPI — `@FunctionalInterface appraise(ActionContext) → List<CognitiveEmotion>`
- Produces: `ActionContext` record — 11 fields with `isSelfAction()` method
- Produces: `ActionOutcome` enum — SUCCESS, FAILURE, NEUTRAL
- Produces: `EmotionSource.ATTRIBUTED` — new enum value for other-agent judgment
- Produces: `ExperienceAttributeKeys.OUTCOME_STATUS` — `"outcome-status"` constant

- [ ] **Step 1: Write ActionContext validation tests**

Create `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/ActionContextTest.java`:

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.PadProjection;
import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.assertj.core.api.Assertions.*;

class ActionContextTest {

    private static final Instant NOW = Instant.now();

    @Test
    void validContextCreated() {
        var ctx = new ActionContext("agent-a", "agent-a", "t1", "turn-1",
                "completed task", "planning", ActionOutcome.SUCCESS, 0.8,
                PadProjection.NEUTRAL, AppraisalWeights.NEUTRAL, NOW);
        assertThat(ctx.actingAgentId()).isEqualTo("agent-a");
        assertThat(ctx.isSelfAction()).isTrue();
    }

    @Test
    void otherAgentDetected() {
        var ctx = new ActionContext("agent-b", "agent-a", "t1", "turn-1",
                "helped with task", null, ActionOutcome.SUCCESS, 0.5,
                PadProjection.NEUTRAL, AppraisalWeights.NEUTRAL, NOW);
        assertThat(ctx.isSelfAction()).isFalse();
    }

    @Test
    void goalRelevanceBelowMinThrows() {
        assertThatThrownBy(() -> new ActionContext("a", "a", "t1", "turn-1",
                "desc", null, ActionOutcome.NEUTRAL, -1.1,
                PadProjection.NEUTRAL, null, NOW))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void goalRelevanceAboveMaxThrows() {
        assertThatThrownBy(() -> new ActionContext("a", "a", "t1", "turn-1",
                "desc", null, ActionOutcome.NEUTRAL, 1.1,
                PadProjection.NEUTRAL, null, NOW))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void nullWeightsDefaultsToNeutral() {
        var ctx = new ActionContext("a", "a", "t1", "turn-1",
                "desc", null, ActionOutcome.NEUTRAL, 0.0,
                PadProjection.NEUTRAL, null, NOW);
        assertThat(ctx.weights()).isEqualTo(AppraisalWeights.NEUTRAL);
    }

    @Test
    void nullActingAgentThrows() {
        assertThatThrownBy(() -> new ActionContext(null, "a", "t1", "turn-1",
                "desc", null, ActionOutcome.NEUTRAL, 0.0,
                PadProjection.NEUTRAL, null, NOW))
                .isInstanceOf(NullPointerException.class);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=ActionContextTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation error — types do not exist yet.

- [ ] **Step 3: Create ActionOutcome enum**

Create `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ActionOutcome.java`:

```java
package io.casehub.neocortex.mindmap;

public enum ActionOutcome {
    SUCCESS, FAILURE, NEUTRAL
}
```

- [ ] **Step 4: Create ActionContext record**

Create `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ActionContext.java`:

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.PadProjection;

import java.time.Instant;
import java.util.Objects;

public record ActionContext(
    String actingAgentId,
    String apprasingAgentId,
    String tenantId,
    String turnId,
    String actionDescription,
    String capability,
    ActionOutcome outcome,
    double goalRelevance,
    PadProjection moodBaseline,
    AppraisalWeights weights,
    Instant timestamp
) {
    public ActionContext {
        Objects.requireNonNull(actingAgentId, "actingAgentId required");
        Objects.requireNonNull(apprasingAgentId, "apprasingAgentId required");
        Objects.requireNonNull(tenantId, "tenantId required");
        Objects.requireNonNull(turnId, "turnId required");
        Objects.requireNonNull(actionDescription, "actionDescription required");
        Objects.requireNonNull(outcome, "outcome required");
        Objects.requireNonNull(moodBaseline, "moodBaseline required");
        if (weights == null) weights = AppraisalWeights.NEUTRAL;
        Objects.requireNonNull(timestamp, "timestamp required");
        if (goalRelevance < -1.0 || goalRelevance > 1.0)
            throw new IllegalArgumentException("goalRelevance must be in [-1, 1], got " + goalRelevance);
    }

    public boolean isSelfAction() {
        return actingAgentId.equals(apprasingAgentId);
    }
}
```

- [ ] **Step 5: Create ActionAppraisal SPI**

Create `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ActionAppraisal.java`:

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.CognitiveEmotion;

import java.util.List;

@FunctionalInterface
public interface ActionAppraisal {
    List<CognitiveEmotion> appraise(ActionContext context);
}
```

- [ ] **Step 6: Add EmotionSource.ATTRIBUTED**

In `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/EmotionSource.java`, add `ATTRIBUTED` after `EMPATHIC`:

```java
public enum EmotionSource {
    INTRINSIC,
    EMPATHIC,
    ATTRIBUTED
}
```

- [ ] **Step 7: Add ExperienceAttributeKeys.OUTCOME_STATUS**

In `memory-api/src/main/java/io/casehub/neocortex/memory/experience/ExperienceAttributeKeys.java`, add after `SOURCE_CHANNEL`:

```java
public static final String OUTCOME_STATUS = "outcome-status";
```

- [ ] **Step 8: Run tests to verify ActionContext validation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=ActionContextTest`
Expected: All 6 tests pass.

- [ ] **Step 9: Verify full build compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl mindmap-api,cognitive-api,memory-api`
Expected: Clean compilation.

- [ ] **Step 10: Commit**

```
git -C <PROJECT> add mindmap-api/ cognitive-api/ memory-api/
git -C <PROJECT> commit -m "feat(#383): add ActionAppraisal SPI, ActionContext, EmotionSource.ATTRIBUTED

New types: ActionAppraisal (@FunctionalInterface), ActionContext (record),
ActionOutcome (enum). EmotionSource gains ATTRIBUTED for other-agent
judgment. ExperienceAttributeKeys gains OUTCOME_STATUS.

Refs #383"
```

---

## Batch 2: Heuristic Appraisal — scoring, thresholds, compounds

After this batch: `HeuristicActionAppraisal` fully implemented with asymmetric thresholds and inline compound detection. Standards strictness derived from DispositionAxes.

### Task 3: HeuristicActionAppraisal — TDD implementation

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/HeuristicActionAppraisal.java`
- Create: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/HeuristicActionAppraisalTest.java`

**Interfaces:**
- Consumes: `ActionAppraisal` SPI, `ActionContext`, `ActionOutcome`, `CognitiveEmotion`, `EmotionType`, `EmotionSource`, `AlmaPadTable`, `AppraisalWeights`
- Produces: `HeuristicActionAppraisal implements ActionAppraisal` — heuristic scoring with asymmetric thresholds and inline compound detection

- [ ] **Step 1: Write test — self-appraisal SUCCESS → PRIDE**

Create `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/HeuristicActionAppraisalTest.java`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.cognitive.CognitiveEmotion;
import io.casehub.neocortex.cognitive.EmotionSource;
import io.casehub.neocortex.cognitive.EmotionType;
import io.casehub.neocortex.cognitive.PadProjection;
import io.casehub.neocortex.mindmap.ActionContext;
import io.casehub.neocortex.mindmap.ActionOutcome;
import io.casehub.neocortex.mindmap.AppraisalWeights;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.*;

class HeuristicActionAppraisalTest {

    private final HeuristicActionAppraisal appraisal = new HeuristicActionAppraisal();
    private static final Instant NOW = Instant.parse("2026-01-01T00:00:00Z");

    private ActionContext selfContext(ActionOutcome outcome, double goalRelevance) {
        return selfContext(outcome, goalRelevance, AppraisalWeights.NEUTRAL);
    }

    private ActionContext selfContext(ActionOutcome outcome, double goalRelevance, AppraisalWeights weights) {
        return new ActionContext("agent-a", "agent-a", "t1", "turn-1",
                "did something", "planning", outcome, goalRelevance,
                PadProjection.NEUTRAL, weights, NOW);
    }

    private ActionContext otherContext(ActionOutcome outcome, double goalRelevance) {
        return otherContext(outcome, goalRelevance, AppraisalWeights.NEUTRAL);
    }

    private ActionContext otherContext(ActionOutcome outcome, double goalRelevance, AppraisalWeights weights) {
        return new ActionContext("agent-b", "agent-a", "t1", "turn-1",
                "helped with task", "planning", outcome, goalRelevance,
                PadProjection.NEUTRAL, weights, NOW);
    }

    @Test
    void selfAppraisal_success_positive_goalRelevance_producesPride() {
        var emotions = appraisal.appraise(selfContext(ActionOutcome.SUCCESS, 0.8));
        assertThat(emotions).extracting(CognitiveEmotion::type).contains(EmotionType.PRIDE);
        var pride = emotions.stream().filter(e -> e.type() == EmotionType.PRIDE).findFirst().orElseThrow();
        assertThat(pride.source()).isEqualTo(EmotionSource.INTRINSIC);
        assertThat(pride.intensity()).isGreaterThan(0.0).isLessThanOrEqualTo(1.0);
    }

    @Test
    void selfAppraisal_failure_negative_goalRelevance_producesShame() {
        var emotions = appraisal.appraise(selfContext(ActionOutcome.FAILURE, -0.7));
        assertThat(emotions).extracting(CognitiveEmotion::type).contains(EmotionType.SHAME);
        var shame = emotions.stream().filter(e -> e.type() == EmotionType.SHAME).findFirst().orElseThrow();
        assertThat(shame.source()).isEqualTo(EmotionSource.INTRINSIC);
    }

    @Test
    void otherAppraisal_success_positive_goalRelevance_producesAdmiration() {
        var emotions = appraisal.appraise(otherContext(ActionOutcome.SUCCESS, 0.8));
        assertThat(emotions).extracting(CognitiveEmotion::type).contains(EmotionType.ADMIRATION);
        var admiration = emotions.stream().filter(e -> e.type() == EmotionType.ADMIRATION).findFirst().orElseThrow();
        assertThat(admiration.source()).isEqualTo(EmotionSource.ATTRIBUTED);
    }

    @Test
    void otherAppraisal_failure_negative_goalRelevance_producesReproach() {
        var emotions = appraisal.appraise(otherContext(ActionOutcome.FAILURE, -0.6));
        assertThat(emotions).extracting(CognitiveEmotion::type).contains(EmotionType.REPROACH);
        var reproach = emotions.stream().filter(e -> e.type() == EmotionType.REPROACH).findFirst().orElseThrow();
        assertThat(reproach.source()).isEqualTo(EmotionSource.ATTRIBUTED);
    }

    @Test
    void neutralOutcome_producesNoEmotion() {
        var emotions = appraisal.appraise(selfContext(ActionOutcome.NEUTRAL, 0.8));
        assertThat(emotions).isEmpty();
    }

    @Test
    void zeroGoalRelevance_producesNoEmotion() {
        var emotions = appraisal.appraise(selfContext(ActionOutcome.SUCCESS, 0.0));
        assertThat(emotions).isEmpty();
    }

    @Test
    void belowThreshold_producesNoEmotion() {
        var emotions = appraisal.appraise(selfContext(ActionOutcome.SUCCESS, 0.1));
        assertThat(emotions).isEmpty();
    }

    @Test
    void asymmetricThresholds_strictAgent_shameEasierThanPride() {
        var strict = new AppraisalWeights(1.0, 1.0, 1.0, 2.0, 1.0);
        var shameEmotions = appraisal.appraise(selfContext(ActionOutcome.FAILURE, -0.15, strict));
        assertThat(shameEmotions).extracting(CognitiveEmotion::type).contains(EmotionType.SHAME);

        var prideEmotions = appraisal.appraise(selfContext(ActionOutcome.SUCCESS, 0.15, strict));
        assertThat(prideEmotions).isEmpty();
    }

    @Test
    void asymmetricThresholds_strictAgent_prideRequiresHighRelevance() {
        var strict = new AppraisalWeights(1.0, 1.0, 1.0, 2.0, 1.0);
        var emotions = appraisal.appraise(selfContext(ActionOutcome.SUCCESS, 0.5, strict));
        assertThat(emotions).extracting(CognitiveEmotion::type).contains(EmotionType.PRIDE);
    }

    @Test
    void compound_pride_withHighGoalRelevance_producesGratification() {
        var emotions = appraisal.appraise(selfContext(ActionOutcome.SUCCESS, 0.8));
        assertThat(emotions).extracting(CognitiveEmotion::type)
                .contains(EmotionType.PRIDE, EmotionType.GRATIFICATION);
    }

    @Test
    void compound_shame_withNegativeGoalRelevance_producesRemorse() {
        var emotions = appraisal.appraise(selfContext(ActionOutcome.FAILURE, -0.8));
        assertThat(emotions).extracting(CognitiveEmotion::type)
                .contains(EmotionType.SHAME, EmotionType.REMORSE);
    }

    @Test
    void compound_admiration_withHighGoalRelevance_producesGratitude() {
        var emotions = appraisal.appraise(otherContext(ActionOutcome.SUCCESS, 0.8));
        assertThat(emotions).extracting(CognitiveEmotion::type)
                .contains(EmotionType.ADMIRATION, EmotionType.GRATITUDE);
    }

    @Test
    void compound_reproach_withNegativeGoalRelevance_producesAnger() {
        var emotions = appraisal.appraise(otherContext(ActionOutcome.FAILURE, -0.8));
        assertThat(emotions).extracting(CognitiveEmotion::type)
                .contains(EmotionType.REPROACH, EmotionType.ANGER);
    }

    @Test
    void compound_notProduced_whenGoalRelevanceBelowCompoundThreshold() {
        var emotions = appraisal.appraise(selfContext(ActionOutcome.SUCCESS, 0.25));
        assertThat(emotions).extracting(CognitiveEmotion::type)
                .contains(EmotionType.PRIDE)
                .doesNotContain(EmotionType.GRATIFICATION);
    }

    @Test
    void padProjection_matchesAlmaTable() {
        var emotions = appraisal.appraise(selfContext(ActionOutcome.SUCCESS, 0.8));
        var pride = emotions.stream().filter(e -> e.type() == EmotionType.PRIDE).findFirst().orElseThrow();
        assertThat(pride.pad().pleasure()).isGreaterThan(0.0);
        assertThat(pride.pad().dominance()).isGreaterThan(0.0);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=HeuristicActionAppraisalTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation error — `HeuristicActionAppraisal` does not exist.

- [ ] **Step 3: Implement HeuristicActionAppraisal**

Create `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/HeuristicActionAppraisal.java`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.cognitive.AlmaPadTable;
import io.casehub.neocortex.cognitive.CognitiveEmotion;
import io.casehub.neocortex.cognitive.EmotionSource;
import io.casehub.neocortex.cognitive.EmotionType;
import io.casehub.neocortex.mindmap.ActionContext;
import io.casehub.neocortex.mindmap.ActionAppraisal;
import io.casehub.neocortex.mindmap.ActionOutcome;

import java.util.ArrayList;
import java.util.List;

public class HeuristicActionAppraisal implements ActionAppraisal {

    private static final double BASE_THRESHOLD = 0.2;
    private static final double COMPOUND_RELEVANCE_THRESHOLD = 0.3;

    @Override
    public List<CognitiveEmotion> appraise(ActionContext context) {
        double polarity = switch (context.outcome()) {
            case SUCCESS -> 1.0;
            case FAILURE -> -1.0;
            case NEUTRAL -> 0.0;
        };

        double praiseworthiness = polarity * Math.abs(context.goalRelevance());
        if (praiseworthiness == 0.0) return List.of();

        double strictness = context.isSelfAction()
                ? context.weights().selfStandardsStrictness()
                : context.weights().otherStandardsStrictness();

        var emotions = new ArrayList<CognitiveEmotion>();

        if (praiseworthiness > 0) {
            double positiveThreshold = BASE_THRESHOLD * strictness;
            if (praiseworthiness > positiveThreshold) {
                double intensity = clampIntensity(praiseworthiness / strictness);
                EmotionType type = context.isSelfAction() ? EmotionType.PRIDE : EmotionType.ADMIRATION;
                EmotionSource source = context.isSelfAction() ? EmotionSource.INTRINSIC : EmotionSource.ATTRIBUTED;
                emotions.add(emotion(type, intensity, context, source));
                addCompoundIfEligible(emotions, type, context, intensity);
            }
        } else {
            double negativeThreshold = BASE_THRESHOLD / strictness;
            if (Math.abs(praiseworthiness) > negativeThreshold) {
                double intensity = clampIntensity(Math.abs(praiseworthiness) * strictness);
                EmotionType type = context.isSelfAction() ? EmotionType.SHAME : EmotionType.REPROACH;
                EmotionSource source = context.isSelfAction() ? EmotionSource.INTRINSIC : EmotionSource.ATTRIBUTED;
                emotions.add(emotion(type, intensity, context, source));
                addCompoundIfEligible(emotions, type, context, intensity);
            }
        }

        return List.copyOf(emotions);
    }

    private void addCompoundIfEligible(List<CognitiveEmotion> emotions,
                                        EmotionType baseType, ActionContext context,
                                        double baseIntensity) {
        double absRelevance = Math.abs(context.goalRelevance());
        if (absRelevance <= COMPOUND_RELEVANCE_THRESHOLD) return;

        EmotionType compoundType = switch (baseType) {
            case PRIDE -> context.outcome() == ActionOutcome.SUCCESS ? EmotionType.GRATIFICATION : null;
            case SHAME -> context.outcome() == ActionOutcome.FAILURE ? EmotionType.REMORSE : null;
            case ADMIRATION -> context.goalRelevance() > COMPOUND_RELEVANCE_THRESHOLD ? EmotionType.GRATITUDE : null;
            case REPROACH -> context.goalRelevance() < -COMPOUND_RELEVANCE_THRESHOLD ? EmotionType.ANGER : null;
            default -> null;
        };

        if (compoundType != null) {
            double compoundIntensity = clampIntensity(Math.max(baseIntensity, absRelevance));
            EmotionSource source = context.isSelfAction() ? EmotionSource.INTRINSIC : EmotionSource.ATTRIBUTED;
            emotions.add(emotion(compoundType, compoundIntensity, context, source));
        }
    }

    private static CognitiveEmotion emotion(EmotionType type, double intensity,
                                             ActionContext context, EmotionSource source) {
        return new CognitiveEmotion(type, intensity, context.actingAgentId(),
                context.timestamp(), source, AlmaPadTable.project(type, intensity));
    }

    private static double clampIntensity(double value) {
        return Math.clamp(value, 0.0, 1.0);
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=HeuristicActionAppraisalTest`
Expected: All 16 tests pass.

- [ ] **Step 5: Commit**

```
git -C <PROJECT> add mindmap-intelligence/
git -C <PROJECT> commit -m "feat(#383): HeuristicActionAppraisal — scoring, thresholds, compounds

Asymmetric thresholds: strict agents feel Shame easily (0.2/strictness)
but require high achievements for Pride (0.2*strictness). Inline
compound detection: Pride+goalRelevance→Gratification, Shame→Remorse,
Admiration→Gratitude, Reproach→Anger.

Refs #383"
```

### Task 4: CognitiveDerivationEngine — standards strictness from DispositionAxes

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java`
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngineTest.java`

**Interfaces:**
- Consumes: `AppraisalWeights` (5-arg), `DispositionAxes`, `DescriptorView`
- Produces: `deriveAppraisalWeights(List<WeightedTerm>, DispositionAxes)` — extended signature

- [ ] **Step 1: Write failing tests for DispositionAxes-based derivation**

Add to `CognitiveDerivationEngineTest.java`:

```java
@Test
void deriveAppraisalWeights_strictRuleFollowing_highStrictness() {
    var profile = List.of(new WeightedTerm("fi", 1.0));
    var axes = new DispositionAxes("balanced", "strict", "moderate", "balanced", "collaborative");
    var w = CognitiveDerivationEngine.deriveAppraisalWeights(profile, axes);
    assertThat(w.selfStandardsStrictness()).isCloseTo(1.6, within(0.01));
    assertThat(w.otherStandardsStrictness()).isCloseTo(1.4, within(0.01));
}

@Test
void deriveAppraisalWeights_flexibleRuleFollowing_lowStrictness() {
    var profile = List.of(new WeightedTerm("fi", 1.0));
    var axes = new DispositionAxes("balanced", "flexible", "moderate", "balanced", "collaborative");
    var w = CognitiveDerivationEngine.deriveAppraisalWeights(profile, axes);
    assertThat(w.selfStandardsStrictness()).isCloseTo(0.7, within(0.01));
    assertThat(w.otherStandardsStrictness()).isCloseTo(0.6, within(0.01));
}

@Test
void deriveAppraisalWeights_cooperativeSocialOrient_reducesOtherStrictness() {
    var profile = List.of(new WeightedTerm("fi", 1.0));
    var axes = new DispositionAxes("cooperative", "strict", "moderate", "balanced", "collaborative");
    var w = CognitiveDerivationEngine.deriveAppraisalWeights(profile, axes);
    assertThat(w.selfStandardsStrictness()).isCloseTo(1.6, within(0.01));
    assertThat(w.otherStandardsStrictness()).isCloseTo(1.2, within(0.01));
}

@Test
void deriveAppraisalWeights_competitiveSocialOrient_increasesOtherStrictness() {
    var profile = List.of(new WeightedTerm("fi", 1.0));
    var axes = new DispositionAxes("competitive", "moderate", "moderate", "balanced", "collaborative");
    var w = CognitiveDerivationEngine.deriveAppraisalWeights(profile, axes);
    assertThat(w.otherStandardsStrictness()).isCloseTo(1.2, within(0.01));
}

@Test
void deriveAppraisalWeights_nullAxes_defaultsStrictness() {
    var profile = List.of(new WeightedTerm("fi", 1.0));
    var w = CognitiveDerivationEngine.deriveAppraisalWeights(profile, null);
    assertThat(w.selfStandardsStrictness()).isEqualTo(1.0);
    assertThat(w.otherStandardsStrictness()).isEqualTo(1.0);
}

@Test
void deriveAppraisalWeights_strictCompetitive_clampsToMax() {
    var profile = List.of(new WeightedTerm("fi", 1.0));
    var axes = new DispositionAxes("competitive", "strict", "moderate", "balanced", "collaborative");
    var w = CognitiveDerivationEngine.deriveAppraisalWeights(profile, axes);
    assertThat(w.otherStandardsStrictness()).isCloseTo(1.6, within(0.01));
    assertThat(w.otherStandardsStrictness()).isLessThanOrEqualTo(2.0);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveDerivationEngineTest#deriveAppraisalWeights_strictRuleFollowing_highStrictness -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation error — method signature doesn't accept `DispositionAxes`.

- [ ] **Step 3: Update deriveAppraisalWeights and derive() in CognitiveDerivationEngine**

Replace the `deriveAppraisalWeights` method (starting at line 348) with:

```java
static AppraisalWeights deriveAppraisalWeights(List<WeightedTerm> profile, DispositionAxes axes) {
    if (profile == null || profile.isEmpty()) return null;

    double urgencyRaw = 0.0, relRaw = 0.0, fearRaw = 0.0;
    double totalWeight = 0.0;

    for (WeightedTerm term : profile) {
        String fn = term.term().toLowerCase();
        double w = term.weight();
        totalWeight += w;

        urgencyRaw += w * URGENCY_CONTRIBUTION.getOrDefault(fn, 0.0);
        relRaw     += w * RELATIONSHIP_CONTRIBUTION.getOrDefault(fn, 0.0);
        fearRaw    += w * FEAR_CONTRIBUTION.getOrDefault(fn, 0.0);
    }

    if (totalWeight == 0.0) return null;

    urgencyRaw /= totalWeight;
    relRaw     /= totalWeight;
    fearRaw    /= totalWeight;

    double selfStrictness = 1.0;
    double otherStrictness = 1.0;

    if (axes != null) {
        if (axes.ruleFollowing() != null) {
            switch (axes.ruleFollowing()) {
                case "strict"   -> { selfStrictness = 1.6; otherStrictness = 1.4; }
                case "flexible" -> { selfStrictness = 0.7; otherStrictness = 0.6; }
                default -> {}
            }
        }
        if (axes.socialOrient() != null) {
            switch (axes.socialOrient()) {
                case "cooperative" -> otherStrictness -= 0.2;
                case "competitive" -> otherStrictness += 0.2;
                default -> {}
            }
        }
    }

    return new AppraisalWeights(
        Math.max(1.0 + urgencyRaw * SCALE_FACTOR, 0.1),
        Math.max(1.0 + relRaw * SCALE_FACTOR, 0.1),
        Math.max(1.0 + fearRaw * SCALE_FACTOR, 0.1),
        Math.clamp(selfStrictness, 0.5, 2.0),
        Math.clamp(otherStrictness, 0.5, 2.0)
    );
}
```

Update the `derive()` method call at line 133 from:
```java
AppraisalWeights appraisal = deriveAppraisalWeights(descriptor.dispositionProfile());
```
to:
```java
AppraisalWeights appraisal = deriveAppraisalWeights(descriptor.dispositionProfile(), descriptor.disposition());
```

Also update existing tests that call `deriveAppraisalWeights(profile)` — add `, null` as the second argument.

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveDerivationEngineTest`
Expected: All tests pass (existing + 6 new).

- [ ] **Step 5: Commit**

```
git -C <PROJECT> add cognitive-index/
git -C <PROJECT> commit -m "feat(#383): derive standards strictness from DispositionAxes

ruleFollowing: strict→1.6/1.4, flexible→0.7/0.6.
socialOrient: cooperative→−0.2 other, competitive→+0.2 other.
Clamped to [0.5, 2.0]. Follows deriveCbrStrategy pattern.

Refs #383"
```

---

## Batch 3: Observer Wiring — real-time action appraisal

After this batch: `ActionAppraisalObserver` fires in real-time on Outcome events, builds ActionContext from goal lookup + cognitive defaults, produces emotions via `HeuristicActionAppraisal`, emits attention signals. `NoOpActionAppraisal` provides graceful degradation.

### Task 5: ActionAppraisalObserver + NoOpActionAppraisal — CDI wiring

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/NoOpActionAppraisal.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ActionAppraisalObserver.java`
- Create: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/ActionAppraisalObserverTest.java`

**Interfaces:**
- Consumes: `ActionAppraisal` SPI, `ActionContext`, `ActionOutcome`, `MindMapStore`, `CognitiveDefaultsRegistry`, `ExperienceRecorded`, `Outcome`, `ExperienceAttributeKeys`, `AttentionSignal`, `SignalCategory`, `SubgraphTypes`
- Produces: `NoOpActionAppraisal` @DefaultBean, `ActionAppraisalObserver` @ApplicationScoped CDI observer

- [ ] **Step 1: Create NoOpActionAppraisal**

Create `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/NoOpActionAppraisal.java`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.cognitive.CognitiveEmotion;
import io.casehub.neocortex.mindmap.ActionAppraisal;
import io.casehub.neocortex.mindmap.ActionContext;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Default;
import io.quarkus.arc.DefaultBean;

import java.util.List;

@DefaultBean
@ApplicationScoped
public class NoOpActionAppraisal implements ActionAppraisal {
    @Override
    public List<CognitiveEmotion> appraise(ActionContext context) {
        return List.of();
    }
}
```

- [ ] **Step 2: Write observer tests**

Create `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/ActionAppraisalObserverTest.java`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.cognitive.CognitiveEmotion;
import io.casehub.neocortex.cognitive.EmotionSource;
import io.casehub.neocortex.cognitive.EmotionType;
import io.casehub.neocortex.cognitive.PadProjection;
import io.casehub.neocortex.cognitive.AlmaPadTable;
import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.memory.experience.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;

class ActionAppraisalObserverTest {

    private RecordingActionAppraisal appraisal;
    private StubMindMapStore store;
    private ActionAppraisalObserver observer;

    @BeforeEach
    void setUp() {
        appraisal = new RecordingActionAppraisal();
        store = new StubMindMapStore();
        observer = new ActionAppraisalObserver(store, appraisal, null);
    }

    @Test
    void outcomeEvent_selfAppraisal_buildsContextCorrectly() {
        store.addGoalNode("goal-1", "planning", 0.8);
        var outcome = new Outcome("agent-a", "t1", "case-1", "turn-1",
                Instant.now(), "completed planning", 0.9,
                Map.of(), "success", "planning");
        var recorded = new ExperienceRecorded(outcome, "mem-1");

        observer.onExperienceRecorded(recorded);

        assertThat(appraisal.contexts).hasSize(1);
        var ctx = appraisal.contexts.get(0);
        assertThat(ctx.isSelfAction()).isTrue();
        assertThat(ctx.outcome()).isEqualTo(ActionOutcome.SUCCESS);
        assertThat(ctx.goalRelevance()).isGreaterThan(0.0);
    }

    @Test
    void nonOutcomeEvent_ignored() {
        var action = new Action("agent-a", "t1", "case-1", "turn-1",
                Instant.now(), "started task", null, Map.of(), "planning");
        var recorded = new ExperienceRecorded(action, "mem-1");

        observer.onExperienceRecorded(recorded);

        assertThat(appraisal.contexts).isEmpty();
    }

    @Test
    void targetAgent_triggersOtherAppraisal() {
        store.addGoalNode("goal-1", "research", 0.6);
        var outcome = new Outcome("agent-a", "t1", "case-1", "turn-1",
                Instant.now(), "agent-b helped with research", 0.8,
                Map.of(ExperienceAttributeKeys.TARGET_AGENT, "agent-b"),
                "success", "research");
        var recorded = new ExperienceRecorded(outcome, "mem-1");

        observer.onExperienceRecorded(recorded);

        assertThat(appraisal.contexts).hasSize(2);
        var selfCtx = appraisal.contexts.stream().filter(ActionContext::isSelfAction).findFirst().orElseThrow();
        var otherCtx = appraisal.contexts.stream().filter(c -> !c.isSelfAction()).findFirst().orElseThrow();
        assertThat(otherCtx.actingAgentId()).isEqualTo("agent-b");
        assertThat(otherCtx.apprasingAgentId()).isEqualTo("agent-a");
    }

    @Test
    void selfReferentialTargetAgent_onlySelfAppraisal() {
        var outcome = new Outcome("agent-a", "t1", "case-1", "turn-1",
                Instant.now(), "self action", 0.8,
                Map.of(ExperienceAttributeKeys.TARGET_AGENT, "agent-a"),
                "done", "planning");
        var recorded = new ExperienceRecorded(outcome, "mem-1");

        observer.onExperienceRecorded(recorded);

        assertThat(appraisal.contexts).hasSize(1);
        assertThat(appraisal.contexts.get(0).isSelfAction()).isTrue();
    }

    @Test
    void outcomeStatusMetadata_mapsToActionOutcome() {
        var outcome = new Outcome("agent-a", "t1", "case-1", "turn-1",
                Instant.now(), "did thing", 0.5,
                Map.of(ExperienceAttributeKeys.OUTCOME_STATUS, "failure"),
                "partial", "planning");
        var recorded = new ExperienceRecorded(outcome, "mem-1");

        observer.onExperienceRecorded(recorded);

        assertThat(appraisal.contexts).hasSize(1);
        assertThat(appraisal.contexts.get(0).outcome()).isEqualTo(ActionOutcome.FAILURE);
    }

    @Test
    void confidenceFallback_highConfidence_mapsToSuccess() {
        var outcome = new Outcome("agent-a", "t1", "case-1", "turn-1",
                Instant.now(), "did thing", 0.9, Map.of(), "done", "planning");
        var recorded = new ExperienceRecorded(outcome, "mem-1");

        observer.onExperienceRecorded(recorded);

        assertThat(appraisal.contexts.get(0).outcome()).isEqualTo(ActionOutcome.SUCCESS);
    }

    @Test
    void confidenceFallback_lowConfidence_mapsToFailure() {
        var outcome = new Outcome("agent-a", "t1", "case-1", "turn-1",
                Instant.now(), "did thing", 0.2, Map.of(), "done", "planning");
        var recorded = new ExperienceRecorded(outcome, "mem-1");

        observer.onExperienceRecorded(recorded);

        assertThat(appraisal.contexts.get(0).outcome()).isEqualTo(ActionOutcome.FAILURE);
    }

    @Test
    void noGoalMatch_zeroRelevance() {
        var outcome = new Outcome("agent-a", "t1", "case-1", "turn-1",
                Instant.now(), "unrelated action", 0.9, Map.of(), "done", "swimming");
        var recorded = new ExperienceRecorded(outcome, "mem-1");

        observer.onExperienceRecorded(recorded);

        assertThat(appraisal.contexts).hasSize(1);
        assertThat(appraisal.contexts.get(0).goalRelevance()).isEqualTo(0.0);
    }

    @Test
    void nullStore_gracefulDegradation() {
        var obs = new ActionAppraisalObserver(null, appraisal, null);
        var outcome = new Outcome("agent-a", "t1", "case-1", "turn-1",
                Instant.now(), "desc", 0.9, Map.of(), "done", "planning");
        obs.onExperienceRecorded(new ExperienceRecorded(outcome, "mem-1"));
        assertThat(appraisal.contexts).isEmpty();
    }

    @Test
    void nullAppraisal_gracefulDegradation() {
        var obs = new ActionAppraisalObserver(store, null, null);
        var outcome = new Outcome("agent-a", "t1", "case-1", "turn-1",
                Instant.now(), "desc", 0.9, Map.of(), "done", "planning");
        obs.onExperienceRecorded(new ExperienceRecorded(outcome, "mem-1"));
        // no exception thrown
    }

    static class RecordingActionAppraisal implements ActionAppraisal {
        final List<ActionContext> contexts = new ArrayList<>();

        @Override
        public List<CognitiveEmotion> appraise(ActionContext context) {
            contexts.add(context);
            return List.of();
        }
    }

    static class StubMindMapStore {
        // Minimal stub — implements only the methods the observer calls.
        // In the actual test, this will extend InMemoryMindMapStore or use
        // a mock. The key methods needed: listSubgraphs, nodesIn.
        // Full stub implementation follows in Step 3.
        private final List<GoalNode> goals = new ArrayList<>();

        void addGoalNode(String id, String capability, double priority) {
            goals.add(new GoalNode(id, capability, priority));
        }

        record GoalNode(String id, String capability, double priority) {}
    }
}
```

Note: The test stubs are simplified — actual implementation will use `InMemoryMindMapStore` from `mindmap-inmem` (already a test dependency of mindmap-intelligence). The test file will import and configure `InMemoryMindMapStore` with goal subgraph and nodes.

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ActionAppraisalObserverTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation error — `ActionAppraisalObserver` does not exist.

- [ ] **Step 4: Implement ActionAppraisalObserver**

Create `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ActionAppraisalObserver.java`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.cognitive.CognitiveEmotion;
import io.casehub.neocortex.cognitive.PadProjection;
import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.cognitive.index.CognitiveDefaultsRegistry;
import io.casehub.neocortex.memory.experience.ExperienceAttributeKeys;
import io.casehub.neocortex.memory.experience.ExperienceRecorded;
import io.casehub.neocortex.memory.experience.Outcome;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;

import java.util.List;
import java.util.logging.Level;
import java.util.logging.Logger;

@ApplicationScoped
public class ActionAppraisalObserver {

    private static final Logger LOG = Logger.getLogger(ActionAppraisalObserver.class.getName());

    private final MindMapStore store;
    private final ActionAppraisal appraisal;
    private final CognitiveDefaultsRegistry registry;

    @Inject
    public ActionAppraisalObserver(Instance<MindMapStore> store,
                                    Instance<ActionAppraisal> appraisal,
                                    Instance<CognitiveDefaultsRegistry> registry) {
        this.store     = store.isResolvable() ? store.get() : null;
        this.appraisal = appraisal.isResolvable() ? appraisal.get() : null;
        this.registry  = registry.isResolvable() ? registry.get() : null;
    }

    ActionAppraisalObserver(MindMapStore store, ActionAppraisal appraisal,
                             CognitiveDefaultsRegistry registry) {
        this.store     = store;
        this.appraisal = appraisal;
        this.registry  = registry;
    }

    public void onExperienceRecorded(@Observes ExperienceRecorded event) {
        if (store == null || appraisal == null) return;
        if (!(event.event() instanceof Outcome outcome)) return;

        try {
            String agentId = outcome.agentId();
            String tenantId = outcome.tenantId();

            ActionOutcome actionOutcome = mapOutcome(outcome);
            double goalRelevance = computeGoalRelevance(outcome, tenantId, actionOutcome);
            AppraisalWeights weights = lookupWeights(agentId);

            var selfContext = new ActionContext(
                    agentId, agentId, tenantId, outcome.turnId(),
                    outcome.description(), outcome.capability(), actionOutcome,
                    goalRelevance, PadProjection.NEUTRAL, weights, outcome.timestamp());
            appraisal.appraise(selfContext);

            String targetAgent = outcome.metadata().get(ExperienceAttributeKeys.TARGET_AGENT);
            if (targetAgent != null && !targetAgent.equals(agentId)) {
                var otherContext = new ActionContext(
                        targetAgent, agentId, tenantId, outcome.turnId(),
                        outcome.description(), outcome.capability(), actionOutcome,
                        goalRelevance, PadProjection.NEUTRAL, weights, outcome.timestamp());
                appraisal.appraise(otherContext);
            }
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Action appraisal failed for event " + event.memoryId(), e);
        }
    }

    ActionOutcome mapOutcome(Outcome outcome) {
        String explicit = outcome.metadata().get(ExperienceAttributeKeys.OUTCOME_STATUS);
        if (explicit != null) {
            return switch (explicit.toLowerCase()) {
                case "success" -> ActionOutcome.SUCCESS;
                case "failure" -> ActionOutcome.FAILURE;
                default -> ActionOutcome.NEUTRAL;
            };
        }
        Double confidence = outcome.confidence();
        if (confidence != null) {
            if (confidence >= 0.7) return ActionOutcome.SUCCESS;
            if (confidence <= 0.3) return ActionOutcome.FAILURE;
        }
        return ActionOutcome.NEUTRAL;
    }

    double computeGoalRelevance(Outcome outcome, String tenantId, ActionOutcome actionOutcome) {
        String goalSgId = findGoalSubgraph(tenantId);
        if (goalSgId == null) return 0.0;

        double maxRelevance = 0.0;
        String capability = outcome.capability();

        for (MindMapNode node : store.nodesIn(goalSgId, tenantId)) {
            String status = node.property("status").orElse("active");
            if (!"active".equals(status)) continue;

            boolean matches = false;
            if (capability != null) {
                String goalName = node.name().toLowerCase();
                String capLower = capability.toLowerCase();
                if (goalName.contains(capLower) || capLower.contains(goalName)) {
                    matches = true;
                }
                String goalCapability = node.property("capability").orElse("");
                if (!goalCapability.isEmpty() && goalCapability.equalsIgnoreCase(capability)) {
                    matches = true;
                }
            }

            if (matches) {
                double priority = node.property("priority")
                        .map(v -> { try { return Double.parseDouble(v); } catch (NumberFormatException e) { return 0.5; } })
                        .orElse(0.5);
                double relevance = priority;
                if (actionOutcome == ActionOutcome.FAILURE) relevance = -relevance;
                if (Math.abs(relevance) > Math.abs(maxRelevance)) {
                    maxRelevance = relevance;
                }
            }
        }
        return maxRelevance;
    }

    private String findGoalSubgraph(String tenantId) {
        for (MindMapSubgraph sg : store.listSubgraphs(tenantId)) {
            if (SubgraphTypes.GOAL.equals(sg.type())) {
                return sg.id();
            }
        }
        return null;
    }

    private AppraisalWeights lookupWeights(String agentId) {
        if (registry == null) return AppraisalWeights.NEUTRAL;
        var defaults = registry.forAgentOrDefaults(agentId);
        var w = defaults.appraisalWeights();
        return w != null ? w : AppraisalWeights.NEUTRAL;
    }
}
```

- [ ] **Step 5: Update observer tests to use InMemoryMindMapStore**

Refactor the test to use `InMemoryMindMapStore` from `mindmap-inmem` (already a test dependency). Set up a GOAL subgraph with active nodes that have capabilities and priorities. The full test implementation replaces the `StubMindMapStore` with real `InMemoryMindMapStore` calls.

- [ ] **Step 6: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ActionAppraisalObserverTest`
Expected: All 10 tests pass.

- [ ] **Step 7: Run full module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: All existing + new tests pass. GoalAffectPhase tests unaffected (uses `AppraisalWeights.NEUTRAL` which was updated in Task 1).

- [ ] **Step 8: Commit**

```
git -C <PROJECT> add mindmap-intelligence/
git -C <PROJECT> commit -m "feat(#383): ActionAppraisalObserver — real-time action emotion appraisal

CDI @Observes ExperienceRecorded, filters Outcome events. Dual-path:
self-appraisal (Pride/Shame) and other-appraisal via TARGET_AGENT
(Admiration/Reproach). Goal-relevance from capability matching against
active goals. Two-stage outcome mapping (metadata then confidence).
NoOpActionAppraisal @DefaultBean for graceful degradation.

Closes #383"
```

---

## References

- [2026-09-28-agent-occ-emotions-design.md] — design spec this plan implements
- [HeuristicGoalAppraisal.java] — existing goal-based appraisal pattern
- [GoalAffectPhase.java] — existing consolidation phase + AttentionSignal emission
- [AppraisalWeights.java:18-34] — existing record to extend
- [CognitiveDerivationEngine.java:348-375] — existing derivation to extend
- [DispositionAxes.java:18-24] — ruleFollowing/socialOrient axes
- [EmotionSource.java:3-6] — enum to extend
- [ExperienceAttributeKeys.java:3-15] — constants to extend
- [Outcome.java:7-31] — sealed event subtype
- [GitHub #383] — focal issue

# Composable SEC Appraisal Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #428 — Epic: Cognitive appraisal architecture
**Issue group:** #428

**Goal:** Replace the NoOp `AppraisalStrategy` with a composable, computational-only `SchererAppraisalStrategy` built from four independent SEC checks. Each check is a pluggable unit gated by `SchererAppraisalConfig` toggles — experimenters can toggle, replace, or compare SEC combinations without touching code.

**Architecture:** Each Scherer Stimulus Evaluation Check (SEC) is a `SecCheck` functional interface that takes `AppraisalContext` and returns `SecResult` (named dimensions). `SchererAppraisalStrategy` composes enabled checks, then `EmotionMapper` maps the combined dimension pattern to OCC emotions + Frijda action tendencies. All implementations are pure Java keyword/threshold analysis — computational first pass that experiments can validate or replace. `AlmaPadTable` provides empirically-grounded PAD projections for each emotion type.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI, cognition-api + cognition modules

## Global Constraints

- Java 21 source level, Java 26 JVM
- `SecCheck` is `@FunctionalInterface` with synchronous return
- All new value types are Java records
- Computational only — no LLM calls in any SEC implementation
- SEC implementations use keyword sets and threshold logic — intentionally simple, designed to be measured and replaced
- `SchererAppraisalConfig` gates each SEC — already exists with per-SEC booleans
- `AlmaPadTable.project(type, intensity)` for PAD values — no hardcoded PAD coordinates
- Tests use AssertJ, Mockito where needed
- Commit after every task with `Refs #428`

---

## Batch 1: SEC Framework + Checks

### Task 1: SecCheck SPI + SecResult + SecDimensions

**Files:**
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/SecCheck.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/SecResult.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/SecDimensions.java`
- Test: `cognition-api/src/test/java/io/casehub/neocortex/cognition/appraisal/SecResultTest.java`

**Interfaces:**
- Consumes: `AppraisalContext` (cognition-api, existing)
- Produces: `SecCheck` SPI — consumed by all SEC implementations (Task 2) and `SchererAppraisalStrategy` (Task 4). `SecResult` — consumed by `EmotionMapper` (Task 3).

- [ ] **Step 1: Write failing test for SecResult**

```java
package io.casehub.neocortex.cognition.appraisal;

import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class SecResultTest {

    @Test
    void dimensionReturnsValueWhenPresent() {
        var result = new SecResult("relevance", Map.of("novelty", 0.8, "urgency", 0.5));
        assertThat(result.dimension("novelty")).isCloseTo(0.8, within(0.001));
    }

    @Test
    void dimensionReturnsZeroWhenAbsent() {
        var result = new SecResult("relevance", Map.of("novelty", 0.8));
        assertThat(result.dimension("missing")).isCloseTo(0.0, within(0.001));
    }

    @Test
    void factoryMethodsSingleDimension() {
        var result = SecResult.of("test", "dim1", 0.7);
        assertThat(result.checkName()).isEqualTo("test");
        assertThat(result.dimension("dim1")).isCloseTo(0.7, within(0.001));
    }

    @Test
    void factoryMethodsTwoDimensions() {
        var result = SecResult.of("test", "a", 0.3, "b", 0.9);
        assertThat(result.dimension("a")).isCloseTo(0.3, within(0.001));
        assertThat(result.dimension("b")).isCloseTo(0.9, within(0.001));
    }

    @Test
    void nullDimensionsDefaultsToEmpty() {
        var result = new SecResult("test", null);
        assertThat(result.dimensions()).isEmpty();
    }

    @Test
    void dimensionsAreImmutable() {
        var result = new SecResult("test", Map.of("x", 1.0));
        assertThatThrownBy(() -> result.dimensions().put("y", 2.0))
                .isInstanceOf(UnsupportedOperationException.class);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api -Dtest=SecResultTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — classes not found

- [ ] **Step 3: Implement SecCheck, SecResult, SecDimensions**

Use `ide_create_file` for each:

```java
// SecCheck.java
package io.casehub.neocortex.cognition.appraisal;

@FunctionalInterface
public interface SecCheck {
    SecResult evaluate(AppraisalContext context);
}
```

```java
// SecResult.java
package io.casehub.neocortex.cognition.appraisal;

import java.util.Map;
import java.util.Objects;

public record SecResult(
        String checkName,
        Map<String, Double> dimensions) {
    public SecResult {
        Objects.requireNonNull(checkName, "checkName");
        dimensions = dimensions != null ? Map.copyOf(dimensions) : Map.of();
    }

    public double dimension(String name) {
        return dimensions.getOrDefault(name, 0.0);
    }

    public static SecResult of(String checkName, String dim1, double val1) {
        return new SecResult(checkName, Map.of(dim1, val1));
    }

    public static SecResult of(String checkName, String dim1, double val1,
                               String dim2, double val2) {
        return new SecResult(checkName, Map.of(dim1, val1, dim2, val2));
    }

    public static SecResult of(String checkName, String dim1, double val1,
                               String dim2, double val2, String dim3, double val3) {
        return new SecResult(checkName, Map.of(dim1, val1, dim2, val2, dim3, val3));
    }
}
```

```java
// SecDimensions.java
package io.casehub.neocortex.cognition.appraisal;

public final class SecDimensions {
    public static final String RELEVANCE = "relevance";
    public static final String NOVELTY = "novelty";
    public static final String URGENCY = "urgency";
    public static final String CONDUCIVENESS = "conduciveness";
    public static final String CONTROLLABILITY = "controllability";
    public static final String ADJUSTABILITY = "adjustability";
    public static final String INTERNAL_STANDARDS = "internal-standards";
    public static final String EXTERNAL_STANDARDS = "external-standards";

    private SecDimensions() {}
}
```

- [ ] **Step 4: Run tests and verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api -Dtest=SecResultTest`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/SecCheck.java
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/SecResult.java
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/SecDimensions.java
git add cognition-api/src/test/java/io/casehub/neocortex/cognition/appraisal/SecResultTest.java
git commit -m "feat(#428): add SecCheck SPI + SecResult + SecDimensions

Refs #428"
```

---

### Task 2: Four SEC check implementations

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/RelevanceCheck.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/ImplicationCheck.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/CopingCheck.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/NormativeCheck.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/SecCheckTest.java`

**Interfaces:**
- Consumes: `SecCheck` SPI, `SecResult`, `SecDimensions` (Task 1), `AppraisalContext`, `Drive`, `HabituationConfig`, `HabituationState`, `AppraisalWeights`
- Produces: Four `SecCheck` implementations — consumed by `SchererAppraisalStrategy` (Task 4)

- [ ] **Step 1: Write failing tests for all four checks**

```java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.cognitive.HabituationConfig;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class SecCheckTest {

    @Nested
    class RelevanceCheckTest {

        @Test
        void driveNameInObservation_highRelevance() {
            var ctx = context("knowledge gaps detected in the archive",
                    List.of(new Drive("curiosity", DriveCategory.BASELINE, 0.8, "knowledge gaps")));
            var result = new RelevanceCheck().evaluate(ctx);
            assertThat(result.dimension(SecDimensions.RELEVANCE)).isGreaterThan(0.5);
        }

        @Test
        void noDriveMatch_lowRelevance() {
            var ctx = context("the weather is pleasant",
                    List.of(new Drive("curiosity", DriveCategory.BASELINE, 0.8, "knowledge gaps")));
            var result = new RelevanceCheck().evaluate(ctx);
            assertThat(result.dimension(SecDimensions.RELEVANCE)).isCloseTo(0.0, offset(0.01));
        }

        @Test
        void noveltyDecreasesWithRepetition() {
            var hab = HabituationState.empty();
            var ctx = contextWithHabituation("the dark corridor", List.of(), hab);
            var first = new RelevanceCheck().evaluate(ctx);

            var hab2 = first.evaluate(ctx).dimensions().containsKey(SecDimensions.NOVELTY)
                    ? hab.withObservation(
                        Integer.toHexString("the dark corridor".hashCode()),
                        first.dimension(SecDimensions.NOVELTY))
                    : hab;
            var ctx2 = contextWithHabituation("the dark corridor", List.of(), hab2);
            var second = new RelevanceCheck().evaluate(ctx2);

            assertThat(second.dimension(SecDimensions.NOVELTY))
                    .isLessThan(first.dimension(SecDimensions.NOVELTY));
        }
    }

    @Nested
    class ImplicationCheckTest {

        @Test
        void positiveWords_positiveConduciveness() {
            var ctx = context("mission success — all objectives achieved", List.of());
            var result = new ImplicationCheck().evaluate(ctx);
            assertThat(result.dimension(SecDimensions.CONDUCIVENESS)).isGreaterThan(0.0);
        }

        @Test
        void negativeWords_negativeConduciveness() {
            var ctx = context("system failed and data was lost", List.of());
            var result = new ImplicationCheck().evaluate(ctx);
            assertThat(result.dimension(SecDimensions.CONDUCIVENESS)).isLessThan(0.0);
        }

        @Test
        void neutralText_zeroConduciveness() {
            var ctx = context("the room has four walls", List.of());
            var result = new ImplicationCheck().evaluate(ctx);
            assertThat(result.dimension(SecDimensions.CONDUCIVENESS)).isCloseTo(0.0, offset(0.01));
        }
    }

    @Nested
    class CopingCheckTest {

        @Test
        void agencyWords_highControllability() {
            var ctx = context("you can choose which path to take", List.of());
            var result = new CopingCheck().evaluate(ctx);
            assertThat(result.dimension(SecDimensions.CONTROLLABILITY)).isGreaterThan(0.5);
        }

        @Test
        void helplessnessWords_lowControllability() {
            var ctx = context("you are trapped with no way out, impossible to escape", List.of());
            var result = new CopingCheck().evaluate(ctx);
            assertThat(result.dimension(SecDimensions.CONTROLLABILITY)).isLessThan(0.5);
        }

        @Test
        void manyActiveDrives_highAdjustability() {
            var drives = List.of(
                    new Drive("curiosity", DriveCategory.BASELINE, 0.7, ""),
                    new Drive("competence", DriveCategory.BASELINE, 0.6, ""),
                    new Drive("affiliation", DriveCategory.BASELINE, 0.5, ""),
                    new Drive("protection", DriveCategory.CHARACTER, 0.8, ""));
            var ctx = context("a challenge appears", drives);
            var result = new CopingCheck().evaluate(ctx);
            assertThat(result.dimension(SecDimensions.ADJUSTABILITY)).isGreaterThan(0.7);
        }
    }

    @Nested
    class NormativeCheckTest {

        @Test
        void normViolation_lowInternalStandards() {
            var ctx = context("this betrayal was deeply wrong and unjust", List.of());
            var result = new NormativeCheck().evaluate(ctx);
            assertThat(result.dimension(SecDimensions.INTERNAL_STANDARDS)).isLessThan(0.8);
        }

        @Test
        void normConformity_highStandards() {
            var ctx = context("fair and honest treatment for everyone", List.of());
            var result = new NormativeCheck().evaluate(ctx);
            assertThat(result.dimension(SecDimensions.INTERNAL_STANDARDS)).isGreaterThan(0.8);
        }

        @Test
        void neutralText_defaultStandards() {
            var ctx = context("the table is made of wood", List.of());
            var result = new NormativeCheck().evaluate(ctx);
            assertThat(result.dimension(SecDimensions.INTERNAL_STANDARDS)).isCloseTo(1.0, offset(0.01));
        }
    }

    private static AppraisalContext context(String observation, List<Drive> drives) {
        return new AppraisalContext(
                PerceivedSituation.passThrough(observation),
                drives, null, HabituationConfig.defaults(),
                HabituationState.empty(), null);
    }

    private static AppraisalContext contextWithHabituation(String observation,
            List<Drive> drives, HabituationState habituation) {
        return new AppraisalContext(
                PerceivedSituation.passThrough(observation),
                drives, null, HabituationConfig.defaults(),
                habituation, null);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=SecCheckTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — classes not found

- [ ] **Step 3: Implement RelevanceCheck**

Use `ide_create_file`:

```java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.cognitive.HabituationConfig;

import java.util.List;
import java.util.Map;

public class RelevanceCheck implements SecCheck {

    @Override
    public SecResult evaluate(AppraisalContext context) {
        var narrative = context.situation().narrative();
        var drives = context.drives();

        double novelty = computeNovelty(narrative, context.habituation(), context.habituationConfig());
        double relevance = computeDriveRelevance(narrative, drives);

        double urgencyMod = context.weights() != null ? context.weights().urgencyWeight() : 1.0;
        double urgency = Math.min(1.0, relevance * urgencyMod);

        return SecResult.of("relevance",
                SecDimensions.RELEVANCE, relevance,
                SecDimensions.NOVELTY, novelty,
                SecDimensions.URGENCY, urgency);
    }

    private double computeNovelty(String narrative, HabituationState habituation,
                                  HabituationConfig config) {
        if (habituation == null) return 1.0;
        var hash = Integer.toHexString(narrative.hashCode());
        int count = habituation.observationCounts().getOrDefault(hash, 0);
        double rate = config != null ? config.habituationRate() : 0.2;
        return Math.max(0, 1.0 - count * rate);
    }

    private double computeDriveRelevance(String narrative, List<Drive> drives) {
        if (drives.isEmpty()) return 0.0;
        String lower = narrative.toLowerCase();
        double max = 0.0;
        for (var drive : drives) {
            if (lower.contains(drive.name().toLowerCase())) {
                max = Math.max(max, drive.intensity());
            }
            if (!drive.trigger().isEmpty() && lower.contains(drive.trigger().toLowerCase())) {
                max = Math.max(max, drive.intensity() * 0.8);
            }
        }
        return max;
    }
}
```

- [ ] **Step 4: Implement ImplicationCheck**

```java
package io.casehub.neocortex.cognition.appraisal;

import java.util.Set;

public class ImplicationCheck implements SecCheck {

    private static final Set<String> POSITIVE = Set.of(
            "success", "achieved", "found", "helped", "solved",
            "gained", "won", "progressed", "improved", "completed");
    private static final Set<String> NEGATIVE = Set.of(
            "failed", "lost", "blocked", "threatened", "broken",
            "damaged", "missing", "danger", "destroyed", "collapsed");

    @Override
    public SecResult evaluate(AppraisalContext context) {
        String lower = context.situation().narrative().toLowerCase();

        long pos = POSITIVE.stream().filter(lower::contains).count();
        long neg = NEGATIVE.stream().filter(lower::contains).count();
        long total = pos + neg;

        double conduciveness = total > 0 ? (double) (pos - neg) / total : 0.0;

        return SecResult.of("implication", SecDimensions.CONDUCIVENESS, conduciveness);
    }
}
```

- [ ] **Step 5: Implement CopingCheck**

```java
package io.casehub.neocortex.cognition.appraisal;

import java.util.Set;

public class CopingCheck implements SecCheck {

    private static final Set<String> AGENCY = Set.of(
            "can", "able", "possible", "option", "choose", "decide", "control");
    private static final Set<String> HELPLESSNESS = Set.of(
            "impossible", "trapped", "stuck", "unable", "forced", "inevitable", "overwhelming");

    @Override
    public SecResult evaluate(AppraisalContext context) {
        String lower = context.situation().narrative().toLowerCase();

        long agency = AGENCY.stream().filter(lower::contains).count();
        long helpless = HELPLESSNESS.stream().filter(lower::contains).count();
        long total = agency + helpless;

        double controllability = total > 0 ? (double) agency / total : 0.5;

        long activeDrives = context.drives().stream()
                .filter(d -> d.intensity() > 0.3).count();
        double adjustability = Math.min(1.0, activeDrives / 4.0);

        return SecResult.of("coping",
                SecDimensions.CONTROLLABILITY, controllability,
                SecDimensions.ADJUSTABILITY, adjustability);
    }
}
```

- [ ] **Step 6: Implement NormativeCheck**

```java
package io.casehub.neocortex.cognition.appraisal;

import java.util.Set;

public class NormativeCheck implements SecCheck {

    private static final Set<String> VIOLATIONS = Set.of(
            "wrong", "unfair", "unjust", "violation", "betrayal", "dishonest", "corrupt");
    private static final Set<String> CONFORMITY = Set.of(
            "fair", "just", "honest", "proper", "right", "ethical", "principled");

    @Override
    public SecResult evaluate(AppraisalContext context) {
        String lower = context.situation().narrative().toLowerCase();

        long violations = VIOLATIONS.stream().filter(lower::contains).count();
        long conformity = CONFORMITY.stream().filter(lower::contains).count();

        double selfStrictness = context.weights() != null
                ? context.weights().selfStandardsStrictness() : 1.0;
        double otherStrictness = context.weights() != null
                ? context.weights().otherStandardsStrictness() : 1.0;

        double internal = Math.max(0, Math.min(1.0,
                1.0 - violations * 0.3 * selfStrictness + conformity * 0.2));
        double external = Math.max(0, Math.min(1.0,
                1.0 - violations * 0.3 * otherStrictness + conformity * 0.2));

        return SecResult.of("normative",
                SecDimensions.INTERNAL_STANDARDS, internal,
                SecDimensions.EXTERNAL_STANDARDS, external);
    }
}
```

- [ ] **Step 7: Run tests and verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=SecCheckTest`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/RelevanceCheck.java
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/ImplicationCheck.java
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/CopingCheck.java
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/NormativeCheck.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/SecCheckTest.java
git commit -m "feat(#428): add four computational SEC checks — relevance, implication, coping, normative

Keyword-based first pass for experiment-driven validation.
Refs #428"
```

---

## Batch 2: Emotion Mapping + Strategy Composition

### Task 3: EmotionMapper — SEC results to OCC emotions + action tendencies

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/EmotionMapper.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/EmotionMapperTest.java`

**Interfaces:**
- Consumes: `SecResult`, `SecDimensions` (Task 1), `CognitiveEmotion`, `EmotionType`, `EmotionSource`, `AlmaPadTable` (cognitive-api), `ActionTendency`, `ActionReadiness` (cognition-api)
- Produces: `EmotionMapper.mapEmotions()` and `EmotionMapper.mapTendencies()` — consumed by `SchererAppraisalStrategy` (Task 4)

Emotion rules grounded in Scherer/OCC mapping:

| Pattern | Emotion | OCC Category |
|---------|---------|-------------|
| relevant + negative + low coping | FEAR | prospect-based |
| relevant + negative + high coping | ANGER | compound |
| relevant + positive | JOY | well-being |
| relevant + negative (fallback) | DISTRESS | well-being |
| internal standards violated | SHAME | attribution |
| external standards violated | REPROACH | attribution |

- [ ] **Step 1: Write failing test for EmotionMapper**

```java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.cognitive.EmotionType;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class EmotionMapperTest {

    @Test
    void fearFromNegativeWithLowCoping() {
        var results = List.of(
                SecResult.of("relevance", SecDimensions.RELEVANCE, 0.8, SecDimensions.NOVELTY, 0.7),
                SecResult.of("implication", SecDimensions.CONDUCIVENESS, -0.6),
                SecResult.of("coping", SecDimensions.CONTROLLABILITY, 0.2, SecDimensions.ADJUSTABILITY, 0.3));

        var emotions = EmotionMapper.mapEmotions(results, "dark-corridor");

        assertThat(emotions).extracting("type").contains(EmotionType.FEAR);
        assertThat(emotions).extracting("type").doesNotContain(EmotionType.ANGER);
    }

    @Test
    void angerFromNegativeWithHighCoping() {
        var results = List.of(
                SecResult.of("relevance", SecDimensions.RELEVANCE, 0.8, SecDimensions.NOVELTY, 0.5),
                SecResult.of("implication", SecDimensions.CONDUCIVENESS, -0.6),
                SecResult.of("coping", SecDimensions.CONTROLLABILITY, 0.8, SecDimensions.ADJUSTABILITY, 0.7));

        var emotions = EmotionMapper.mapEmotions(results, "blocker");

        assertThat(emotions).extracting("type").contains(EmotionType.ANGER);
        assertThat(emotions).extracting("type").doesNotContain(EmotionType.FEAR);
    }

    @Test
    void joyFromPositive() {
        var results = List.of(
                SecResult.of("relevance", SecDimensions.RELEVANCE, 0.7, SecDimensions.NOVELTY, 0.6),
                SecResult.of("implication", SecDimensions.CONDUCIVENESS, 0.7));

        var emotions = EmotionMapper.mapEmotions(results, "success");

        assertThat(emotions).extracting("type").contains(EmotionType.JOY);
    }

    @Test
    void shameFromStandardsViolation() {
        var results = List.of(
                SecResult.of("relevance", SecDimensions.RELEVANCE, 0.6, SecDimensions.NOVELTY, 0.5),
                SecResult.of("normative",
                        SecDimensions.INTERNAL_STANDARDS, 0.3,
                        SecDimensions.EXTERNAL_STANDARDS, 0.8));

        var emotions = EmotionMapper.mapEmotions(results, "my-failure");

        assertThat(emotions).extracting("type").contains(EmotionType.SHAME);
    }

    @Test
    void noEmotionWhenLowRelevance() {
        var results = List.of(
                SecResult.of("relevance", SecDimensions.RELEVANCE, 0.1, SecDimensions.NOVELTY, 0.3),
                SecResult.of("implication", SecDimensions.CONDUCIVENESS, -0.8));

        var emotions = EmotionMapper.mapEmotions(results, "irrelevant");

        assertThat(emotions).isEmpty();
    }

    @Test
    void approachTendencyFromPositive() {
        var results = List.of(
                SecResult.of("implication", SecDimensions.CONDUCIVENESS, 0.7));

        var tendencies = EmotionMapper.mapTendencies(results);

        assertThat(tendencies).extracting("readiness").contains(ActionReadiness.APPROACH);
    }

    @Test
    void avoidanceTendencyFromNegativeLowControl() {
        var results = List.of(
                SecResult.of("implication", SecDimensions.CONDUCIVENESS, -0.6),
                SecResult.of("coping", SecDimensions.CONTROLLABILITY, 0.2));

        var tendencies = EmotionMapper.mapTendencies(results);

        assertThat(tendencies).extracting("readiness").contains(ActionReadiness.AVOIDANCE);
    }

    @Test
    void attendingFromHighNovelty() {
        var results = List.of(
                SecResult.of("relevance", SecDimensions.NOVELTY, 0.9));

        var tendencies = EmotionMapper.mapTendencies(results);

        assertThat(tendencies).extracting("readiness").contains(ActionReadiness.ATTENDING);
    }

    @Test
    void padFromAlmaTable() {
        var results = List.of(
                SecResult.of("relevance", SecDimensions.RELEVANCE, 0.8, SecDimensions.NOVELTY, 0.7),
                SecResult.of("implication", SecDimensions.CONDUCIVENESS, -0.6),
                SecResult.of("coping", SecDimensions.CONTROLLABILITY, 0.2));

        var emotions = EmotionMapper.mapEmotions(results, "threat");
        var fear = emotions.stream()
                .filter(e -> e.type() == EmotionType.FEAR).findFirst().orElseThrow();

        assertThat(fear.pad().pleasure()).isLessThan(0.0);
        assertThat(fear.pad().arousal()).isGreaterThan(0.0);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=EmotionMapperTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL

- [ ] **Step 3: Implement EmotionMapper**

```java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.cognitive.AlmaPadTable;
import io.casehub.neocortex.cognitive.CognitiveEmotion;
import io.casehub.neocortex.cognitive.EmotionSource;
import io.casehub.neocortex.cognitive.EmotionType;

import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class EmotionMapper {

    private EmotionMapper() {}

    public static List<CognitiveEmotion> mapEmotions(List<SecResult> results, String subjectId) {
        var dims = mergeDimensions(results);
        var emotions = new ArrayList<CognitiveEmotion>();
        var now = Instant.now();

        double relevance = dims.getOrDefault(SecDimensions.RELEVANCE, 0.0);
        double conduciveness = dims.getOrDefault(SecDimensions.CONDUCIVENESS, 0.0);
        double controllability = dims.getOrDefault(SecDimensions.CONTROLLABILITY, 0.5);
        double internalStd = dims.getOrDefault(SecDimensions.INTERNAL_STANDARDS, 1.0);
        double externalStd = dims.getOrDefault(SecDimensions.EXTERNAL_STANDARDS, 1.0);

        if (relevance < 0.2) return emotions;

        if (conduciveness < -0.2 && controllability < 0.4) {
            double intensity = clampIntensity(relevance * Math.abs(conduciveness) * (1.0 - controllability));
            emotions.add(emotion(EmotionType.FEAR, intensity, subjectId, now));
        } else if (conduciveness < -0.2 && controllability > 0.5) {
            double intensity = clampIntensity(relevance * Math.abs(conduciveness) * controllability);
            emotions.add(emotion(EmotionType.ANGER, intensity, subjectId, now));
        } else if (conduciveness < -0.2) {
            double intensity = clampIntensity(relevance * Math.abs(conduciveness));
            emotions.add(emotion(EmotionType.DISTRESS, intensity, subjectId, now));
        }

        if (conduciveness > 0.3) {
            double intensity = clampIntensity(relevance * conduciveness);
            emotions.add(emotion(EmotionType.JOY, intensity, subjectId, now));
        }

        if (internalStd < 0.5) {
            double intensity = clampIntensity(relevance * (1.0 - internalStd));
            emotions.add(emotion(EmotionType.SHAME, intensity, subjectId, now));
        }

        if (externalStd < 0.5) {
            double intensity = clampIntensity(relevance * (1.0 - externalStd));
            emotions.add(emotion(EmotionType.REPROACH, intensity, subjectId, now));
        }

        return emotions;
    }

    public static List<ActionTendency> mapTendencies(List<SecResult> results) {
        var dims = mergeDimensions(results);
        var tendencies = new ArrayList<ActionTendency>();

        double conduciveness = dims.getOrDefault(SecDimensions.CONDUCIVENESS, 0.0);
        double controllability = dims.getOrDefault(SecDimensions.CONTROLLABILITY, 0.5);
        double novelty = dims.getOrDefault(SecDimensions.NOVELTY, 0.0);

        if (conduciveness > 0.3) {
            tendencies.add(new ActionTendency(ActionReadiness.APPROACH, clampIntensity(conduciveness), ""));
        } else if (conduciveness < -0.3 && controllability < 0.4) {
            tendencies.add(new ActionTendency(ActionReadiness.AVOIDANCE, clampIntensity(Math.abs(conduciveness)), ""));
        } else if (conduciveness < -0.3 && controllability > 0.5) {
            tendencies.add(new ActionTendency(ActionReadiness.ANTAGONISM, clampIntensity(Math.abs(conduciveness)), ""));
        }

        if (novelty > 0.5) {
            tendencies.add(new ActionTendency(ActionReadiness.ATTENDING, clampIntensity(novelty), ""));
        } else if (novelty < 0.2) {
            tendencies.add(new ActionTendency(ActionReadiness.INTERRUPTION, clampIntensity(1.0 - novelty), ""));
        }

        return tendencies;
    }

    static Map<String, Double> mergeDimensions(List<SecResult> results) {
        var merged = new HashMap<String, Double>();
        for (var result : results) {
            merged.putAll(result.dimensions());
        }
        return merged;
    }

    private static CognitiveEmotion emotion(EmotionType type, double intensity,
                                            String subjectId, Instant onset) {
        return new CognitiveEmotion(type, intensity, subjectId, onset,
                EmotionSource.INTRINSIC, AlmaPadTable.project(type, intensity));
    }

    private static double clampIntensity(double value) {
        return Math.max(0.01, Math.min(1.0, value));
    }
}
```

- [ ] **Step 4: Run tests and verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=EmotionMapperTest`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/EmotionMapper.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/EmotionMapperTest.java
git commit -m "feat(#428): add EmotionMapper — SEC dimension patterns to OCC emotions

Table-driven mapping: fear/anger/distress/joy/shame/reproach from
Scherer SEC results. PAD via AlmaPadTable. Action tendencies from
conduciveness × controllability × novelty.
Refs #428"
```

---

### Task 4: SchererAppraisalStrategy + CDI wiring

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/SchererAppraisalStrategy.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java` — replace `NoOpAppraisalStrategy` with `SchererAppraisalStrategy` as default
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/SchererAppraisalStrategyTest.java`

**Interfaces:**
- Consumes: `SecCheck` implementations (Task 2), `EmotionMapper` (Task 3), `AppraisalStrategy` SPI (existing), `SchererAppraisalConfig` (existing)
- Produces: `SchererAppraisalStrategy` — displaces `NoOpAppraisalStrategy` as `@DefaultBean`

- [ ] **Step 1: Write failing test for SchererAppraisalStrategy**

```java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.cognitive.EmotionType;
import io.casehub.neocortex.cognitive.HabituationConfig;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class SchererAppraisalStrategyTest {

    private final RelevanceCheck relevance = new RelevanceCheck();
    private final ImplicationCheck implication = new ImplicationCheck();
    private final CopingCheck coping = new CopingCheck();
    private final NormativeCheck normative = new NormativeCheck();

    @Test
    void fullPipeline_threatScenario() {
        var strategy = new SchererAppraisalStrategy(
                relevance, implication, coping, normative,
                SchererAppraisalConfig.allEnabled());

        var ctx = context("the danger threatens our curiosity research — trapped with no escape",
                List.of(new Drive("curiosity", DriveCategory.BASELINE, 0.8, "research")));

        var result = strategy.appraise(ctx);

        assertThat(result.emotions()).isNotEmpty();
        assertThat(result.actionTendencies()).isNotEmpty();
    }

    @Test
    void disabledSecs_reducedOutput() {
        var allOn = new SchererAppraisalStrategy(
                relevance, implication, coping, normative,
                SchererAppraisalConfig.allEnabled());
        var relevanceOnly = new SchererAppraisalStrategy(
                relevance, implication, coping, normative,
                new SchererAppraisalConfig(true, false, false, false));

        var ctx = context("danger threatens our curiosity research — betrayal and trapped",
                List.of(new Drive("curiosity", DriveCategory.BASELINE, 0.8, "research")));

        var full = allOn.appraise(ctx);
        var partial = relevanceOnly.appraise(ctx);

        assertThat(full.emotions().size()).isGreaterThanOrEqualTo(partial.emotions().size());
    }

    @Test
    void noRelevance_emptyResult() {
        var strategy = new SchererAppraisalStrategy(
                relevance, implication, coping, normative,
                SchererAppraisalConfig.allEnabled());

        var ctx = context("the weather is pleasant",
                List.of(new Drive("curiosity", DriveCategory.BASELINE, 0.8, "research")));

        var result = strategy.appraise(ctx);

        assertThat(result.emotions()).isEmpty();
    }

    @Test
    void habituationUpdated() {
        var strategy = new SchererAppraisalStrategy(
                relevance, implication, coping, normative,
                SchererAppraisalConfig.allEnabled());

        var ctx = context("curiosity drives the research",
                List.of(new Drive("curiosity", DriveCategory.BASELINE, 0.8, "")));

        var result = strategy.appraise(ctx);

        assertThat(result.updatedHabituation().observationCounts()).isNotEmpty();
    }

    @Test
    void nullChecks_skipped() {
        var strategy = new SchererAppraisalStrategy(
                relevance, null, null, null,
                SchererAppraisalConfig.allEnabled());

        var ctx = context("curiosity research",
                List.of(new Drive("curiosity", DriveCategory.BASELINE, 0.8, "")));

        var result = strategy.appraise(ctx);

        assertThat(result).isNotNull();
    }

    @Test
    void experimentComparison_copingChangesEmotionType() {
        var withCoping = new SchererAppraisalStrategy(
                relevance, implication, coping, normative,
                SchererAppraisalConfig.allEnabled());
        var noCoping = new SchererAppraisalStrategy(
                relevance, implication, null, normative,
                new SchererAppraisalConfig(true, true, false, true));

        var ctx = context("danger threatens our curiosity research — trapped with no escape",
                List.of(new Drive("curiosity", DriveCategory.BASELINE, 0.8, "research")));

        var withResult = withCoping.appraise(ctx);
        var noResult = noCoping.appraise(ctx);

        var withTypes = withResult.emotions().stream().map(e -> e.type()).toList();
        var noTypes = noResult.emotions().stream().map(e -> e.type()).toList();

        assertThat(withTypes).as("Coping check should influence which emotion types appear")
                .isNotEqualTo(noTypes);
    }

    private static AppraisalContext context(String observation, List<Drive> drives) {
        return new AppraisalContext(
                PerceivedSituation.passThrough(observation),
                drives, null, HabituationConfig.defaults(),
                HabituationState.empty(), null);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=SchererAppraisalStrategyTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL

- [ ] **Step 3: Implement SchererAppraisalStrategy**

```java
package io.casehub.neocortex.cognition.appraisal;

import java.util.ArrayList;
import java.util.List;

public class SchererAppraisalStrategy implements AppraisalStrategy {

    private final SecCheck relevanceCheck;
    private final SecCheck implicationCheck;
    private final SecCheck copingCheck;
    private final SecCheck normativeCheck;
    private final SchererAppraisalConfig secConfig;

    public SchererAppraisalStrategy(
            SecCheck relevanceCheck,
            SecCheck implicationCheck,
            SecCheck copingCheck,
            SecCheck normativeCheck,
            SchererAppraisalConfig secConfig) {
        this.relevanceCheck = relevanceCheck;
        this.implicationCheck = implicationCheck;
        this.copingCheck = copingCheck;
        this.normativeCheck = normativeCheck;
        this.secConfig = secConfig;
    }

    @Override
    public AppraisalResult appraise(AppraisalContext context) {
        var results = new ArrayList<SecResult>();

        if (secConfig.relevanceEnabled() && relevanceCheck != null) {
            results.add(relevanceCheck.evaluate(context));
        }
        if (secConfig.implicationsEnabled() && implicationCheck != null) {
            results.add(implicationCheck.evaluate(context));
        }
        if (secConfig.copingEnabled() && copingCheck != null) {
            results.add(copingCheck.evaluate(context));
        }
        if (secConfig.normativeEnabled() && normativeCheck != null) {
            results.add(normativeCheck.evaluate(context));
        }

        if (results.isEmpty()) return AppraisalResult.empty();

        String subjectId = context.situation().narrative();
        var emotions = EmotionMapper.mapEmotions(results, subjectId);
        var tendencies = EmotionMapper.mapTendencies(results);

        var dims = EmotionMapper.mergeDimensions(results);
        double novelty = dims.getOrDefault(SecDimensions.NOVELTY, 1.0);
        var hash = Integer.toHexString(subjectId.hashCode());
        var habituation = context.habituation() != null
                ? context.habituation().withObservation(hash, novelty)
                : HabituationState.empty().withObservation(hash, novelty);

        return new AppraisalResult(emotions, tendencies, habituation);
    }
}
```

- [ ] **Step 4: Run tests and verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=SchererAppraisalStrategyTest`
Expected: PASS

- [ ] **Step 5: Update CognitionDefaultBeans — replace NoOp with Scherer**

Read `CognitionDefaultBeans.java`, then use `ide_edit_member` to replace the `appraisalStrategy()` producer:

```java
@Produces
@DefaultBean
@Singleton
io.casehub.neocortex.cognition.appraisal.AppraisalStrategy appraisalStrategy() {
    return new io.casehub.neocortex.cognition.appraisal.SchererAppraisalStrategy(
            new io.casehub.neocortex.cognition.appraisal.RelevanceCheck(),
            new io.casehub.neocortex.cognition.appraisal.ImplicationCheck(),
            new io.casehub.neocortex.cognition.appraisal.CopingCheck(),
            new io.casehub.neocortex.cognition.appraisal.NormativeCheck(),
            io.casehub.neocortex.cognition.appraisal.SchererAppraisalConfig.allEnabled());
}
```

- [ ] **Step 6: Run full cognition module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: PASS (all existing + new tests)

- [ ] **Step 7: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS

- [ ] **Step 8: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/SchererAppraisalStrategy.java
git add cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/SchererAppraisalStrategyTest.java
git commit -m "feat(#428): add SchererAppraisalStrategy — composable SEC pipeline replaces NoOp

Four SEC checks composed via SchererAppraisalConfig toggles.
EmotionMapper produces OCC emotions from SEC dimension patterns.
Registered as @DefaultBean, displacing NoOpAppraisalStrategy.
Refs #428"
```

---

## Experiment Guide

After implementation, experimenters (debate agents) can run experiments by:

1. **Toggle SECs** — construct `SchererAppraisalStrategy` with different `SchererAppraisalConfig` settings and compare outputs for the same scenario set
2. **Replace individual SECs** — implement a custom `SecCheck` (e.g., LLM-backed) and swap it in for one of the four positions
3. **Adjust emotion mapping** — modify `EmotionMapper` thresholds or add new rules
4. **Compare outputs** — `AppraisalResult.emotions()` and `.actionTendencies()` are inspectable; `SecResult.dimensions()` shows per-SEC intermediate values

Example experiment template (write as a test):
```java
// Same scenario, three configurations
var configs = List.of(
    SchererAppraisalConfig.allEnabled(),
    new SchererAppraisalConfig(true, true, false, false),  // no coping/normative
    new SchererAppraisalConfig(true, false, false, false)); // relevance only

for (var config : configs) {
    var strategy = new SchererAppraisalStrategy(rel, imp, cop, nor, config);
    var result = strategy.appraise(scenario);
    // Compare: result.emotions(), result.actionTendencies()
}
```

---

## References

- [2026-10-04-cognitive-appraisal-architecture-design.md] — design spec
- [cognition-api/.../AppraisalStrategy.java] — SPI this plan implements
- [cognition-api/.../AppraisalContext.java] — input record
- [cognition-api/.../AppraisalResult.java] — output record
- [cognition-api/.../SchererAppraisalConfig.java] — per-SEC toggle config
- [cognitive-api/.../CognitiveEmotion.java] — emotion output type
- [cognitive-api/.../EmotionType.java] — OCC emotion enum (22 types)
- [cognitive-api/.../AlmaPadTable.java] — empirical PAD projections per emotion
- [cognitive-api/.../HabituationConfig.java] — habituation parameters
- [cognition/.../NoOpAppraisalStrategy.java] — current default, displaced by this plan
- [cognition/.../CognitionDefaultBeans.java] — CDI producer to update
- [GitHub #428] — focal issue

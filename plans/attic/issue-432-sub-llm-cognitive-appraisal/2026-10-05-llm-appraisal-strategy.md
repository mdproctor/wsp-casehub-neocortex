# LlmAppraisalStrategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #432 — Sub-LLM cognitive appraisal — Haiku appraisal call per turn for emergent emotion
**Issue group:** #432

**Goal:** Implement `LlmAppraisalStrategy` — a single Haiku sub-LLM call that performs the full appraisal in one pass, producing both SEC dimension scores (for the structured pipeline) and an evocative narrative (for the main LLM's observation), replacing the 4-check `SchererAppraisalStrategy` as the default.

**Architecture:** `LlmAppraisalStrategy` implements the existing `AppraisalStrategy` SPI. One Haiku call receives drives (name+intensity), situation, mood, and disposition. It returns JSON with SEC dimension values AND a 2-3 sentence evocative felt-state narrative. Dimensions flow through the existing `EmotionMapper` for OCC emotion and Frijda tendency mapping. The narrative is carried on `AppraisalResult` (new optional field) and rendered verbatim by `AppraisalPromptSection` when present, bypassing the template-based rendering. `CognitionDefaultBeans` produces `LlmAppraisalStrategy` when `AgentProvider` is available, with `SchererAppraisalStrategy` as fallback.

**Tech Stack:** Java 21, Quarkus CDI, LangChain4j AgentProvider, Jackson JSON, JUnit 5, AssertJ

## Global Constraints

- Java 21 source level on Java 26 JVM
- `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn` for all builds
- All new code in `cognition/` module (implementation) and `cognition-api/` (SPI changes)
- Package: `io.casehub.neocortex.cognition.appraisal`
- Use `AgentProvider.invoke(AgentSessionConfig.of(...))` for LLM calls (pattern from `LlmImplicationCheck`)
- Use `EmotionMapper.mapEmotions()` and `mapTendencies()` for SEC→OCC conversion — do not duplicate
- Existing tests must continue to pass — `SchererAppraisalStrategy` is demoted, not removed

---

## Batch 1: Extend AppraisalResult with narrative field

### Task 1: Add optional narrative field to AppraisalResult

**Files:**
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalResult.java`
- Modify: `cognition-api/src/test/java/io/casehub/neocortex/cognition/appraisal/AppraisalResultTest.java`

**Interfaces:**
- Consumes: nothing new
- Produces: `AppraisalResult(List<CognitiveEmotion>, List<ActionTendency>, HabituationState, String narrative)` — narrative is `@Nullable`, null for all existing callers

- [ ] **Step 1: Write failing test for narrative field**

```java
@Test
void narrativeFieldPreserved() {
    var result = new AppraisalResult(List.of(), List.of(), HabituationState.empty(),
            "You feel a knot of dread in your stomach.");
    assertThat(result.narrative()).isEqualTo("You feel a knot of dread in your stomach.");
}

@Test
void narrativeNullByDefault() {
    var result = new AppraisalResult(List.of(), List.of(), HabituationState.empty());
    assertThat(result.narrative()).isNull();
}

@Test
void emptyFactoryHasNullNarrative() {
    assertThat(AppraisalResult.empty().narrative()).isNull();
}
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api -Dtest=AppraisalResultTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — no 4-arg constructor, no `narrative()` accessor

- [ ] **Step 3: Add narrative field to AppraisalResult**

Add `@Nullable String narrative` as the 4th field. Add a backward-compatible 3-arg constructor that delegates with `null` narrative. Update `empty()` to pass null. The compact constructor leaves narrative as-is (nullable).

```java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.cognitive.CognitiveEmotion;
import org.jspecify.annotations.Nullable;
import java.util.List;

public record AppraisalResult(
        List<CognitiveEmotion> emotions,
        List<ActionTendency> actionTendencies,
        HabituationState updatedHabituation,
        @Nullable String narrative) {

    public AppraisalResult {
        emotions = emotions != null ? List.copyOf(emotions) : List.of();
        actionTendencies = actionTendencies != null ? List.copyOf(actionTendencies) : List.of();
        if (updatedHabituation == null) updatedHabituation = HabituationState.empty();
    }

    public AppraisalResult(List<CognitiveEmotion> emotions,
                           List<ActionTendency> actionTendencies,
                           HabituationState updatedHabituation) {
        this(emotions, actionTendencies, updatedHabituation, null);
    }

    public static AppraisalResult empty() {
        return new AppraisalResult(List.of(), List.of(), HabituationState.empty(), null);
    }
}
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api -Dtest=AppraisalResultTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: PASS

- [ ] **Step 5: Run full cognition-api and cognition tests to verify backward compatibility**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api,cognition`
Expected: all existing tests pass — SchererAppraisalStrategy uses the 3-arg constructor, no breakage

- [ ] **Step 6: Commit**

```bash
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalResult.java cognition-api/src/test/java/io/casehub/neocortex/cognition/appraisal/AppraisalResultTest.java
git commit -m "feat(#432): add optional narrative field to AppraisalResult

Backward-compatible — existing 3-arg constructor delegates to 4-arg with null narrative.
SchererAppraisalStrategy and all existing callers unchanged.

Refs #432

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Batch 2: LlmAppraisalStrategy implementation

### Task 2: Implement LlmAppraisalStrategy

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/LlmAppraisalStrategy.java`
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/LlmAppraisalStrategyTest.java`

**Interfaces:**
- Consumes: `AppraisalStrategy` SPI, `AppraisalContext`, `AppraisalResult(emotions, tendencies, habituation, narrative)`, `EmotionMapper.mapEmotions()`, `EmotionMapper.mapTendencies()`, `AgentProvider.invoke(AgentSessionConfig.of(system, user))`, `SecResult`, `SecDimensions`
- Produces: `LlmAppraisalStrategy(AgentProvider)` constructor, implements `AppraisalStrategy.appraise(AppraisalContext) → AppraisalResult`

- [ ] **Step 1: Write failing tests**

Tests use a stubbed `AgentProvider` that returns pre-canned JSON. This tests the parsing and pipeline integration, not the LLM itself.

```java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.cognitive.EmotionType;
import io.casehub.neocortex.cognitive.HabituationConfig;
import io.casehub.platform.agent.AgentEvent;
import io.casehub.platform.agent.AgentProvider;
import io.casehub.platform.agent.AgentSessionConfig;
import io.smallrye.mutiny.Multi;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class LlmAppraisalStrategyTest {

    @Test
    void parsesJsonAndProducesEmotions() {
        var json = """
                {
                  "narrative": "A cold knot tightens in your chest — something is wrong.",
                  "dimensions": {
                    "relevance": 0.9,
                    "conduciveness": -0.7,
                    "controllability": 0.3,
                    "novelty": 0.8,
                    "internal-standards": 1.0,
                    "external-standards": 1.0
                  }
                }""";
        var strategy = new LlmAppraisalStrategy(stubProvider(json));
        var ctx = context("Clara is missing from the room",
                List.of(new Drive("protection", DriveCategory.CHARACTER, 0.8, "")));

        var result = strategy.appraise(ctx);

        assertThat(result.emotions()).isNotEmpty();
        assertThat(result.emotions()).extracting("type").contains(EmotionType.FEAR);
        assertThat(result.narrative())
                .isEqualTo("A cold knot tightens in your chest — something is wrong.");
    }

    @Test
    void positiveScenarioProducesJoy() {
        var json = """
                {
                  "narrative": "A spark of excitement lights up inside you.",
                  "dimensions": {
                    "relevance": 0.8,
                    "conduciveness": 0.7,
                    "controllability": 0.6,
                    "novelty": 0.7,
                    "internal-standards": 1.0,
                    "external-standards": 1.0
                  }
                }""";
        var strategy = new LlmAppraisalStrategy(stubProvider(json));
        var ctx = context("A hidden inscription reveals the puzzle's answer",
                List.of(new Drive("curiosity", DriveCategory.CHARACTER, 0.7, "")));

        var result = strategy.appraise(ctx);

        assertThat(result.emotions()).extracting("type").contains(EmotionType.JOY);
        assertThat(result.actionTendencies()).extracting("readiness")
                .contains(ActionReadiness.APPROACH);
        assertThat(result.narrative()).contains("excitement");
    }

    @Test
    void fallsBackToEmptyOnLlmFailure() {
        var strategy = new LlmAppraisalStrategy(errorProvider());
        var ctx = context("some situation",
                List.of(new Drive("curiosity", DriveCategory.BASELINE, 0.5, "")));

        var result = strategy.appraise(ctx);

        assertThat(result.emotions()).isEmpty();
        assertThat(result.narrative()).isNull();
    }

    @Test
    void fallsBackToEmptyOnMalformedJson() {
        var strategy = new LlmAppraisalStrategy(stubProvider("not json at all"));
        var ctx = context("some situation",
                List.of(new Drive("curiosity", DriveCategory.BASELINE, 0.5, "")));

        var result = strategy.appraise(ctx);

        assertThat(result.emotions()).isEmpty();
        assertThat(result.narrative()).isNull();
    }

    @Test
    void habituationUpdated() {
        var json = """
                {
                  "narrative": "You feel alert.",
                  "dimensions": { "relevance": 0.6, "novelty": 0.7, "conduciveness": 0.0 }
                }""";
        var strategy = new LlmAppraisalStrategy(stubProvider(json));
        var ctx = context("something happens",
                List.of(new Drive("curiosity", DriveCategory.BASELINE, 0.5, "")));

        var result = strategy.appraise(ctx);

        assertThat(result.updatedHabituation().observationCounts()).isNotEmpty();
    }

    @Test
    void includesMoodInPromptWhenAvailable() {
        var json = """
                {
                  "narrative": "Uneasy calm.",
                  "dimensions": { "relevance": 0.5, "conduciveness": -0.2 }
                }""";
        // Verify it doesn't crash when mood is present
        var strategy = new LlmAppraisalStrategy(stubProvider(json));
        var mood = new io.casehub.neocortex.memory.mood.MoodState(
                "a1", "t1", -0.3, 0.2, 0.1, "prior", java.time.Instant.now(), null);
        var ctx = new AppraisalContext(
                PerceivedSituation.passThrough("a tense moment"),
                List.of(new Drive("protection", DriveCategory.CHARACTER, 0.7, "")),
                null, HabituationConfig.defaults(), HabituationState.empty(), mood);

        var result = strategy.appraise(ctx);
        assertThat(result).isNotNull();
    }

    private static AppraisalContext context(String observation, List<Drive> drives) {
        return new AppraisalContext(
                PerceivedSituation.passThrough(observation),
                drives, null, HabituationConfig.defaults(),
                HabituationState.empty(), null);
    }

    private static AgentProvider stubProvider(String response) {
        return config -> Multi.createFrom().item(
                new AgentEvent.TextDelta(response));
    }

    private static AgentProvider errorProvider() {
        return config -> Multi.createFrom().item(
                new AgentEvent.InvocationComplete("id", null, null, true));
    }
}
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=LlmAppraisalStrategyTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — `LlmAppraisalStrategy` does not exist

- [ ] **Step 3: Implement LlmAppraisalStrategy**

```java
package io.casehub.neocortex.cognition.appraisal;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.casehub.platform.agent.AgentEvent;
import io.casehub.platform.agent.AgentProvider;
import io.casehub.platform.agent.AgentSessionConfig;

import java.time.Duration;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.stream.Collectors;

public class LlmAppraisalStrategy implements AppraisalStrategy {

    private static final Logger LOG = Logger.getLogger(LlmAppraisalStrategy.class.getName());
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static final String SYSTEM_PROMPT = """
            You are a character's subconscious — the part that feels before thinking.

            You will receive:
            - A list of drives (what this character cares about, each with an intensity)
            - The current situation (what just happened)
            - The character's current mood (if available)

            For each drive, consider: does this situation touch it? How? What does it \
            make the character want to do? Consider ALL drives, not just the strongest one.

            Respond with JSON only:
            {
              "narrative": "2-3 sentences in first person. Gut reaction, internal sensation, \
            not analysis. Include ALL activated drives.",
              "dimensions": {
                "relevance": <0.0-1.0, how much this situation matters to the character>,
                "conduciveness": <-1.0 to 1.0, does it advance or block goals>,
                "controllability": <0.0-1.0, can the character influence the outcome>,
                "novelty": <0.0-1.0, how new/surprising is this>,
                "internal-standards": <0.0-1.0, does this align with self-standards (1.0=fine)>,
                "external-standards": <0.0-1.0, does this align with social norms (1.0=fine)>
              }
            }""";

    private final AgentProvider agentProvider;

    public LlmAppraisalStrategy(AgentProvider agentProvider) {
        this.agentProvider = agentProvider;
    }

    @Override
    public AppraisalResult appraise(AppraisalContext context) {
        try {
            String response = invokeLlm(context);
            if (response == null) return AppraisalResult.empty();
            return parseResponse(response, context);
        } catch (Exception e) {
            LOG.log(Level.WARNING, "LLM appraisal failed, returning empty", e);
            return AppraisalResult.empty();
        }
    }

    private AppraisalResult parseResponse(String response, AppraisalContext context) throws Exception {
        var root = MAPPER.readTree(response);

        String narrative = root.has("narrative") ? root.get("narrative").asText(null) : null;

        var dimsNode = root.path("dimensions");
        if (dimsNode.isMissingNode() || !dimsNode.isObject()) {
            return new AppraisalResult(java.util.List.of(), java.util.List.of(),
                    context.habituation() != null ? context.habituation() : HabituationState.empty(),
                    narrative);
        }

        var secResults = java.util.List.of(new SecResult("llm-appraisal", parseDimensions(dimsNode)));

        String subjectId = context.situation().narrative();
        var emotions = EmotionMapper.mapEmotions(secResults, subjectId);
        var tendencies = EmotionMapper.mapTendencies(secResults);

        double novelty = parseDimensions(dimsNode).getOrDefault(SecDimensions.NOVELTY, 1.0);
        var hash = Integer.toHexString(subjectId.hashCode());
        var habituation = context.habituation() != null
                ? context.habituation().withObservation(hash, novelty)
                : HabituationState.empty().withObservation(hash, novelty);

        return new AppraisalResult(emotions, tendencies, habituation, narrative);
    }

    private Map<String, Double> parseDimensions(JsonNode dimsNode) {
        var dims = new java.util.HashMap<String, Double>();
        dimsNode.fields().forEachRemaining(entry -> {
            if (entry.getValue().isNumber()) {
                dims.put(entry.getKey(), clamp(entry.getValue().asDouble()));
            }
        });
        return dims;
    }

    private String invokeLlm(AppraisalContext context) {
        String userMessage = buildUserMessage(context);

        var events = agentProvider.invoke(
                        AgentSessionConfig.of(SYSTEM_PROMPT, userMessage))
                .collect().asList()
                .await().atMost(Duration.ofMinutes(1));

        boolean hasError = events.stream()
                .filter(AgentEvent.InvocationComplete.class::isInstance)
                .map(AgentEvent.InvocationComplete.class::cast)
                .anyMatch(AgentEvent.InvocationComplete::isError);
        if (hasError) return null;

        String text = events.stream()
                .filter(AgentEvent.TextDelta.class::isInstance)
                .map(AgentEvent.TextDelta.class::cast)
                .map(AgentEvent.TextDelta::text)
                .collect(Collectors.joining());

        return text.isEmpty() ? null : text;
    }

    private static String buildUserMessage(AppraisalContext context) {
        var sb = new StringBuilder();

        sb.append("Drives:\n");
        for (var drive : context.drives()) {
            sb.append("- ").append(drive.name()).append(": ").append(drive.intensity()).append("\n");
        }

        sb.append("\nSituation:\n").append(context.situation().narrative());

        if (context.currentMood() != null) {
            var m = context.currentMood();
            sb.append("\n\nCurrent mood: pleasure=").append(String.format("%.2f", m.pleasure()))
                    .append(", arousal=").append(String.format("%.2f", m.arousal()))
                    .append(", dominance=").append(String.format("%.2f", m.dominance()));
        }

        return sb.toString();
    }

    private static double clamp(double v) {
        return Math.max(-1.0, Math.min(1.0, v));
    }
}
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=LlmAppraisalStrategyTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/LlmAppraisalStrategy.java cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/LlmAppraisalStrategyTest.java
git commit -m "feat(#432): implement LlmAppraisalStrategy — single sub-LLM appraisal call

One Haiku call per turn produces SEC dimension scores (fed through
EmotionMapper for OCC/PAD mapping) and an evocative narrative (for
the main LLM's observation section). Graceful fallback to empty on
LLM failure or malformed JSON.

Refs #432

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Batch 3: Narrative-aware prompt rendering and CDI wiring

### Task 3: Update AppraisalPromptSection to prefer narrative

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/prompt/AppraisalPromptSection.java`
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/prompt/AppraisalPromptSectionTest.java`

**Interfaces:**
- Consumes: `AppraisalResult.narrative()`, `AppraisalTickParticipant.currentResult()`
- Produces: `AppraisalPromptSection.render()` returns narrative verbatim when present, falls back to template rendering otherwise

- [ ] **Step 1: Write failing test for narrative rendering**

```java
@Test
void prefersNarrativeWhenPresent() {
    var emotion = new CognitiveEmotion(
            EmotionType.FEAR, 0.8, "dark-corridor", Instant.now(),
            EmotionSource.INTRINSIC, new PadProjection(-0.6, 0.7, -0.4));
    var result = new AppraisalResult(
            List.of(emotion), List.of(), HabituationState.empty(),
            "A cold knot tightens in your chest — something is wrong.");

    var participant = participantReturning(Optional.of(result));
    var section = new AppraisalPromptSection(participant);
    var context = new CognitionRenderContext("a1", "t1", null);

    var rendered = section.render(context);
    assertThat(rendered)
            .isEqualTo("A cold knot tightens in your chest — something is wrong.");
}

@Test
void fallsBackToTemplateWhenNoNarrative() {
    var emotion = new CognitiveEmotion(
            EmotionType.FEAR, 0.8, "corridor", Instant.now(),
            EmotionSource.INTRINSIC, new PadProjection(-0.6, 0.7, -0.4));
    var result = new AppraisalResult(
            List.of(emotion), List.of(), HabituationState.empty());

    var participant = participantReturning(Optional.of(result));
    var section = new AppraisalPromptSection(participant);
    var context = new CognitionRenderContext("a1", "t1", null);

    var rendered = section.render(context);
    assertThat(rendered).contains("fear");
}
```

- [ ] **Step 2: Run tests — verify the narrative test fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=AppraisalPromptSectionTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: `prefersNarrativeWhenPresent` FAILS — current rendering ignores narrative

- [ ] **Step 3: Update renderEvocative to check narrative first**

```java
private static @Nullable String renderEvocative(AppraisalResult result) {
    if (result.narrative() != null && !result.narrative().isBlank()) {
        return result.narrative().strip();
    }

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

    result.actionTendencies().stream()
            .filter(t -> t.intensity() > 0.3)
            .forEach(t -> sb.append(describeTendency(t)).append("\n"));

    return sb.isEmpty() ? null : sb.toString().strip();
}
```

- [ ] **Step 4: Run tests — verify all pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=AppraisalPromptSectionTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: PASS (all tests including existing ones)

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/prompt/AppraisalPromptSection.java cognition/src/test/java/io/casehub/neocortex/cognition/prompt/AppraisalPromptSectionTest.java
git commit -m "feat(#432): AppraisalPromptSection prefers narrative when present

When AppraisalResult carries a narrative (from LlmAppraisalStrategy),
renders it verbatim. Falls back to template-based emotion rendering
for SchererAppraisalStrategy results (null narrative).

Refs #432

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 4: Wire LlmAppraisalStrategy as default in CognitionDefaultBeans

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java`

**Interfaces:**
- Consumes: `LlmAppraisalStrategy(AgentProvider)`, `SchererAppraisalStrategy(...)`, `Instance<AgentProvider>`
- Produces: `@Produces @DefaultBean @Singleton AppraisalStrategy` — returns `LlmAppraisalStrategy` when `AgentProvider` available, `SchererAppraisalStrategy` otherwise

- [ ] **Step 1: Write failing test — LlmAppraisalStrategy is the default when AgentProvider present**

No separate test file needed — this is a CDI wiring change. We verify by running the existing `SchererAppraisalStrategyTest` (still passes — SchererAppraisalStrategy class unchanged) and adding a focused test:

```java
// In a new test or existing test file
@Test
void defaultBeansProducesLlmStrategyWhenAgentAvailable() {
    var beans = new CognitionDefaultBeans();
    // Inject a resolvable AgentProvider
    // Verify the produced strategy is LlmAppraisalStrategy
    // This test may need CDI test infrastructure — verify via integration test instead
}
```

Since `CognitionDefaultBeans` uses field injection (`@Inject Instance<AgentProvider>`), unit-testing it in isolation is awkward. Instead, verify the wiring change is correct by inspection and run the full module test suite.

- [ ] **Step 2: Update the appraisalStrategy() producer**

Replace the `appraisalStrategy()` method body in `CognitionDefaultBeans`:

```java
@Produces
@DefaultBean
@Singleton
io.casehub.neocortex.cognition.appraisal.AppraisalStrategy appraisalStrategy() {
    if (agentProviderInstance != null && agentProviderInstance.isResolvable()) {
        return new io.casehub.neocortex.cognition.appraisal.LlmAppraisalStrategy(
                agentProviderInstance.get());
    }

    // Fallback: 4-check Scherer pipeline with keyword-based checks
    return new io.casehub.neocortex.cognition.appraisal.SchererAppraisalStrategy(
            new io.casehub.neocortex.cognition.appraisal.RelevanceCheck(),
            new io.casehub.neocortex.cognition.appraisal.ImplicationCheck(),
            new io.casehub.neocortex.cognition.appraisal.CopingCheck(),
            new io.casehub.neocortex.cognition.appraisal.NormativeCheck(),
            io.casehub.neocortex.cognition.appraisal.SchererAppraisalConfig.allEnabled());
}
```

- [ ] **Step 3: Run full cognition module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: all tests pass — existing tests use direct construction, not CDI

- [ ] **Step 4: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java
git commit -m "feat(#432): wire LlmAppraisalStrategy as default AppraisalStrategy

When AgentProvider is available (LLM runtime present), produces
LlmAppraisalStrategy for single-call appraisal. Falls back to
SchererAppraisalStrategy with keyword checks when no LLM available.

Refs #432

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 5: Run full build to verify nothing is broken**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api,cognition`
Expected: all tests pass across both modules

---

## References

- `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalStrategy.java` — the SPI interface
- `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalResult.java` — result record being extended
- `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalContext.java` — input record
- `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/SecResult.java` — dimension container
- `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/SecDimensions.java` — dimension name constants
- `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/SchererAppraisalStrategy.java` — existing 4-check implementation
- `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/EmotionMapper.java` — SEC→OCC mapping
- `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/LlmImplicationCheck.java` — AgentProvider invocation pattern
- `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalTickParticipant.java` — tick wiring
- `cognition/src/main/java/io/casehub/neocortex/cognition/prompt/AppraisalPromptSection.java` — prompt rendering
- `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java` — CDI producer
- [GitHub #432](https://github.com/casehubio/neocortex/issues/432) — focal issue

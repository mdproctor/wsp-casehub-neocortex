# LLM-Backed Appraisal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #430 — Replace keyword-based SEC checks with LLM-backed appraisal

**Goal:** Get the full CARMA appraisal pipeline producing diverse, meaningful
emotional responses by replacing the three inert keyword-based SEC checks
with LLM-backed implementations.

**Architecture:** Create `LlmImplicationCheck` and `LlmNormativeCheck`
following the existing `LlmCopingCheck` pattern. Update `CognitionDefaultBeans`
to use LLM checks when `AgentProvider` is available, falling back to keyword
checks when it's not. Validate end-to-end with the #429 scenario corpus.

**Tech Stack:** Java 21, AgentProvider (casehub-platform-agent-api),
Jackson ObjectMapper, existing SecCheck SPI

## Global Constraints

- Java 21 source, Java 26 JVM
- No new module dependencies — all work in existing `cognition` module
- `LlmCopingCheck` already exists — follow its exact pattern
- `RelevanceCheck` stays computational — habituation is math, not NLP
- Keyword checks remain as fallback when no `AgentProvider` on classpath
- All tests pass with `mvn test -pl cognition`

---

## Batch 1: LLM Check Implementations

### Task 1: LlmImplicationCheck — conduciveness via LLM

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/LlmImplicationCheck.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/LlmImplicationCheckTest.java`

**Interfaces:**
- Consumes: `SecCheck` SPI, `AppraisalContext.situation().narrative()`, `AgentProvider.invoke(AgentSessionConfig)`, `AgentEvent.TextDelta`, `SecDimensions.CONDUCIVENESS`
- Produces: `LlmImplicationCheck(AgentProvider)` — drop-in `SecCheck` that returns conduciveness via LLM

- [ ] **Step 1: Write the failing test**

Use `ide_create_file`:

```java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.platform.agent.AgentEvent;
import io.casehub.platform.agent.AgentProvider;
import io.casehub.platform.agent.AgentSession;
import io.casehub.platform.agent.AgentSessionInit;
import io.casehub.neocortex.cognitive.HabituationConfig;
import io.casehub.neocortex.mindmap.AppraisalWeights;
import io.smallrye.mutiny.Multi;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.data.Offset.offset;

class LlmImplicationCheckTest {

    private static final AgentEvent.InvocationComplete COMPLETE =
            new AgentEvent.InvocationComplete(0, 0, 0, 0, 0, null, 0L, 0L, null, 0, false);

    private AgentProvider mockProvider(Map<String, String> responses) {
        return new AgentProvider() {
            @Override
            public Multi<AgentEvent> invoke(io.casehub.platform.agent.AgentSessionConfig config) {
                String prompt = config.userPrompt();
                for (var entry : responses.entrySet()) {
                    if (prompt.contains(entry.getKey())) {
                        return Multi.createFrom().items(
                                new AgentEvent.TextDelta(entry.getValue()), COMPLETE);
                    }
                }
                return Multi.createFrom().items(
                        new AgentEvent.TextDelta("{\"conduciveness\": 0.0}"), COMPLETE);
            }

            @Override
            public AgentSession openSession(AgentSessionInit init) {
                throw new UnsupportedOperationException();
            }
        };
    }

    private AppraisalContext contextFor(String observation) {
        return new AppraisalContext(
                PerceivedSituation.passThrough(observation),
                List.of(), AppraisalWeights.NEUTRAL,
                HabituationConfig.defaults(), HabituationState.empty(), null);
    }

    @Test
    void positiveEvent_returnsPositiveConduciveness() {
        var check = new LlmImplicationCheck(mockProvider(Map.of(
                "solved", "{\"conduciveness\": 0.8}")));
        var result = check.evaluate(contextFor("I just solved the problem"));
        assertThat(result.dimension(SecDimensions.CONDUCIVENESS)).isCloseTo(0.8, offset(0.01));
    }

    @Test
    void negativeEvent_returnsNegativeConduciveness() {
        var check = new LlmImplicationCheck(mockProvider(Map.of(
                "failed", "{\"conduciveness\": -0.7}")));
        var result = check.evaluate(contextFor("The deployment failed completely"));
        assertThat(result.dimension(SecDimensions.CONDUCIVENESS)).isCloseTo(-0.7, offset(0.01));
    }

    @Test
    void neutralEvent_returnsNearZero() {
        var check = new LlmImplicationCheck(mockProvider(Map.of(
                "standup", "{\"conduciveness\": 0.05}")));
        var result = check.evaluate(contextFor("A routine standup meeting"));
        assertThat(result.dimension(SecDimensions.CONDUCIVENESS)).isCloseTo(0.05, offset(0.01));
    }

    @Test
    void fallsBackToNeutralOnError() {
        AgentProvider failingProvider = new AgentProvider() {
            @Override
            public Multi<AgentEvent> invoke(io.casehub.platform.agent.AgentSessionConfig config) {
                return Multi.createFrom().failure(new RuntimeException("LLM unavailable"));
            }

            @Override
            public AgentSession openSession(AgentSessionInit init) {
                throw new UnsupportedOperationException();
            }
        };
        var check = new LlmImplicationCheck(failingProvider);
        var result = check.evaluate(contextFor("anything"));
        assertThat(result.dimension(SecDimensions.CONDUCIVENESS)).isCloseTo(0.0, offset(0.01));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="io.casehub.neocortex.cognition.appraisal.LlmImplicationCheckTest" -Dsurefire.useFile=false`

Expected: FAIL — `LlmImplicationCheck` class does not exist.

- [ ] **Step 3: Implement LlmImplicationCheck**

Use `ide_create_file`. Follow `LlmCopingCheck` pattern exactly — same `invokeLlm()` helper, same error handling, same `clamp()`.

```java
package io.casehub.neocortex.cognition.appraisal;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.casehub.platform.agent.AgentEvent;
import io.casehub.platform.agent.AgentProvider;
import io.casehub.platform.agent.AgentSessionConfig;

import java.time.Duration;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.stream.Collectors;

public class LlmImplicationCheck implements SecCheck {

    private static final Logger LOG = Logger.getLogger(LlmImplicationCheck.class.getName());
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static final String SYSTEM_PROMPT = """
            You are a cognitive appraisal evaluator. Assess a situation on one dimension:

            Conduciveness: How much does this situation advance or block the agent's goals?
              -1.0 = completely blocks goals, catastrophic for objectives
              0.0 = neutral, no impact on goals
              1.0 = fully advances goals, ideal outcome

            Consider the overall goal impact, not just whether the text contains positive
            or negative words. "The deadline was moved up" is negative (blocks goals) even
            though no single word is negative.

            Respond with JSON only: {"conduciveness": <number>}""";

    private static final SecResult NEUTRAL = new SecResult("llm-implication",
            Map.of(SecDimensions.CONDUCIVENESS, 0.0));

    private final AgentProvider agentProvider;

    public LlmImplicationCheck(AgentProvider agentProvider) {
        this.agentProvider = agentProvider;
    }

    @Override
    public SecResult evaluate(AppraisalContext context) {
        String observation = context.situation().narrative();
        try {
            String response = invokeLlm(observation);
            if (response == null) return NEUTRAL;

            var root = MAPPER.readTree(response);
            double conduciveness = clamp(root.path("conduciveness").asDouble(0.0));

            return new SecResult("llm-implication",
                    Map.of(SecDimensions.CONDUCIVENESS, conduciveness));
        } catch (Exception e) {
            LOG.log(Level.WARNING, "LLM implication check failed, returning neutral", e);
            return NEUTRAL;
        }
    }

    private String invokeLlm(String observation) {
        var events = agentProvider.invoke(
                        AgentSessionConfig.of(SYSTEM_PROMPT, "Situation: " + observation))
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

    private static double clamp(double v) {
        return Math.max(-1.0, Math.min(1.0, v));
    }
}
```

Note: `clamp()` range is [-1.0, 1.0] for conduciveness (can be negative), unlike coping's [0.0, 1.0].

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="io.casehub.neocortex.cognition.appraisal.LlmImplicationCheckTest" -Dsurefire.useFile=false`

Expected: All 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/LlmImplicationCheck.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/LlmImplicationCheckTest.java
git commit -m "feat(#430): add LlmImplicationCheck — conduciveness via LLM

Assesses goal conduciveness from situational context, not keyword
matching. Handles compositional meaning — 'deadline moved up' scores
negative even though no single word is negative.

Refs #430

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 2: LlmNormativeCheck — norm adherence via LLM

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/LlmNormativeCheck.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/LlmNormativeCheckTest.java`

**Interfaces:**
- Consumes: `SecCheck` SPI, `AppraisalContext`, `AgentProvider`, `SecDimensions.INTERNAL_STANDARDS`, `SecDimensions.EXTERNAL_STANDARDS`
- Produces: `LlmNormativeCheck(AgentProvider)` — drop-in `SecCheck` that returns internal/external standards scores via LLM

- [ ] **Step 1: Write the failing test**

Use `ide_create_file`:

```java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.platform.agent.AgentEvent;
import io.casehub.platform.agent.AgentProvider;
import io.casehub.platform.agent.AgentSession;
import io.casehub.platform.agent.AgentSessionInit;
import io.casehub.neocortex.cognitive.HabituationConfig;
import io.casehub.neocortex.mindmap.AppraisalWeights;
import io.smallrye.mutiny.Multi;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.data.Offset.offset;

class LlmNormativeCheckTest {

    private static final AgentEvent.InvocationComplete COMPLETE =
            new AgentEvent.InvocationComplete(0, 0, 0, 0, 0, null, 0L, 0L, null, 0, false);

    private AgentProvider mockProvider(Map<String, String> responses) {
        return new AgentProvider() {
            @Override
            public Multi<AgentEvent> invoke(io.casehub.platform.agent.AgentSessionConfig config) {
                String prompt = config.userPrompt();
                for (var entry : responses.entrySet()) {
                    if (prompt.contains(entry.getKey())) {
                        return Multi.createFrom().items(
                                new AgentEvent.TextDelta(entry.getValue()), COMPLETE);
                    }
                }
                return Multi.createFrom().items(
                        new AgentEvent.TextDelta(
                                "{\"internal_standards\": 1.0, \"external_standards\": 1.0}"),
                        COMPLETE);
            }

            @Override
            public AgentSession openSession(AgentSessionInit init) {
                throw new UnsupportedOperationException();
            }
        };
    }

    private AppraisalContext contextFor(String observation) {
        return new AppraisalContext(
                PerceivedSituation.passThrough(observation),
                List.of(), AppraisalWeights.NEUTRAL,
                HabituationConfig.defaults(), HabituationState.empty(), null);
    }

    @Test
    void normViolation_returnsLowStandards() {
        var check = new LlmNormativeCheck(mockProvider(Map.of(
                "ignoring the code review",
                "{\"internal_standards\": 0.7, \"external_standards\": 0.3}")));
        var result = check.evaluate(contextFor(
                "Someone on the team keeps ignoring the code review process"));
        assertThat(result.dimension(SecDimensions.EXTERNAL_STANDARDS))
                .isCloseTo(0.3, offset(0.01));
    }

    @Test
    void slaViolation_returnsLowBothStandards() {
        var check = new LlmNormativeCheck(mockProvider(Map.of(
                "violates our SLA",
                "{\"internal_standards\": 0.35, \"external_standards\": 0.2}")));
        var result = check.evaluate(contextFor(
                "The client reported a critical bug that violates our SLA commitments"));
        assertThat(result.dimension(SecDimensions.INTERNAL_STANDARDS))
                .isCloseTo(0.35, offset(0.01));
        assertThat(result.dimension(SecDimensions.EXTERNAL_STANDARDS))
                .isCloseTo(0.2, offset(0.01));
    }

    @Test
    void normalSituation_returnsHighStandards() {
        var check = new LlmNormativeCheck(mockProvider(Map.of(
                "deployed the new feature",
                "{\"internal_standards\": 0.95, \"external_standards\": 0.9}")));
        var result = check.evaluate(contextFor(
                "I successfully deployed the new feature and all tests are passing"));
        assertThat(result.dimension(SecDimensions.INTERNAL_STANDARDS))
                .isGreaterThan(0.9);
    }

    @Test
    void fallsBackToFullComplianceOnError() {
        AgentProvider failingProvider = new AgentProvider() {
            @Override
            public Multi<AgentEvent> invoke(io.casehub.platform.agent.AgentSessionConfig config) {
                return Multi.createFrom().failure(new RuntimeException("LLM unavailable"));
            }

            @Override
            public AgentSession openSession(AgentSessionInit init) {
                throw new UnsupportedOperationException();
            }
        };
        var check = new LlmNormativeCheck(failingProvider);
        var result = check.evaluate(contextFor("anything"));
        assertThat(result.dimension(SecDimensions.INTERNAL_STANDARDS))
                .isCloseTo(1.0, offset(0.01));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="io.casehub.neocortex.cognition.appraisal.LlmNormativeCheckTest" -Dsurefire.useFile=false`

Expected: FAIL — `LlmNormativeCheck` class does not exist.

- [ ] **Step 3: Implement LlmNormativeCheck**

Use `ide_create_file`:

```java
package io.casehub.neocortex.cognition.appraisal;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.casehub.platform.agent.AgentEvent;
import io.casehub.platform.agent.AgentProvider;
import io.casehub.platform.agent.AgentSessionConfig;

import java.time.Duration;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.stream.Collectors;

public class LlmNormativeCheck implements SecCheck {

    private static final Logger LOG = Logger.getLogger(LlmNormativeCheck.class.getName());
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static final String SYSTEM_PROMPT = """
            You are a cognitive appraisal evaluator. Assess a situation on two norm dimensions:

            1. Internal standards: Does this situation align with the agent's personal values,
               professional ethics, and self-expectations?
               0.0 = severe violation of personal standards (e.g., compromising integrity)
               0.5 = minor tension with personal standards
               1.0 = fully consistent with personal standards

            2. External standards: Does this situation comply with social norms, contractual
               obligations, team agreements, and institutional rules?
               0.0 = severe violation of external standards (e.g., breaking SLA, legal breach)
               0.5 = minor non-compliance
               1.0 = fully compliant with external standards

            Assess the situation itself, not the agent's response to it. "Someone ignoring
            code review" is an external standards violation even if the word "violation"
            doesn't appear.

            Respond with JSON only: {"internal_standards": <number>, "external_standards": <number>}""";

    private static final SecResult COMPLIANT = new SecResult("llm-normative", Map.of(
            SecDimensions.INTERNAL_STANDARDS, 1.0,
            SecDimensions.EXTERNAL_STANDARDS, 1.0));

    private final AgentProvider agentProvider;

    public LlmNormativeCheck(AgentProvider agentProvider) {
        this.agentProvider = agentProvider;
    }

    @Override
    public SecResult evaluate(AppraisalContext context) {
        String observation = context.situation().narrative();
        try {
            String response = invokeLlm(observation);
            if (response == null) return COMPLIANT;

            var root = MAPPER.readTree(response);
            double internal = clamp(root.path("internal_standards").asDouble(1.0));
            double external = clamp(root.path("external_standards").asDouble(1.0));

            return new SecResult("llm-normative", Map.of(
                    SecDimensions.INTERNAL_STANDARDS, internal,
                    SecDimensions.EXTERNAL_STANDARDS, external));
        } catch (Exception e) {
            LOG.log(Level.WARNING, "LLM normative check failed, returning compliant", e);
            return COMPLIANT;
        }
    }

    private String invokeLlm(String observation) {
        var events = agentProvider.invoke(
                        AgentSessionConfig.of(SYSTEM_PROMPT, "Situation: " + observation))
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

    private static double clamp(double v) {
        return Math.max(0.0, Math.min(1.0, v));
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="io.casehub.neocortex.cognition.appraisal.LlmNormativeCheckTest" -Dsurefire.useFile=false`

Expected: All 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/LlmNormativeCheck.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/LlmNormativeCheckTest.java
git commit -m "feat(#430): add LlmNormativeCheck — norm adherence via LLM

Assesses internal/external standards from situational context.
Detects norm violations from meaning, not keyword matching —
'ignoring code review' scores low external standards without
containing the word 'violation'.

Refs #430

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Batch 2: CDI Wiring + End-to-End Validation

### Task 3: Wire LLM checks into CognitionDefaultBeans + end-to-end validation

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java` (lines 118-128)
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/experiment/LlmPipelineDiscriminationTest.java`

**Interfaces:**
- Consumes: `Instance<AgentProvider>`, `LlmImplicationCheck`, `LlmCopingCheck`, `LlmNormativeCheck`, `RelevanceCheck`, `SchererAppraisalStrategy`, `SchererAppraisalConfig.allEnabled()`, `ScenarioCorpus.scenarios()`
- Produces: Updated `appraisalStrategy()` producer that uses LLM checks when AgentProvider available

- [ ] **Step 1: Write the end-to-end discrimination test**

Use `ide_create_file`. This test validates the full pipeline with LLM checks produces diverse emotions — the assertion that failed with keyword checks in #429.

```java
package io.casehub.neocortex.cognition.appraisal.experiment;

import io.casehub.neocortex.cognition.appraisal.*;
import io.casehub.neocortex.cognitive.HabituationConfig;
import io.casehub.neocortex.mindmap.AppraisalWeights;
import io.casehub.platform.agent.AgentEvent;
import io.casehub.platform.agent.AgentProvider;
import io.smallrye.mutiny.Multi;
import org.junit.jupiter.api.Test;

import java.util.*;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

class LlmPipelineDiscriminationTest {

    private static final AgentEvent.InvocationComplete COMPLETE =
            new AgentEvent.InvocationComplete(0, 0, 0, 0, 0, null, 0L, 0L, null, 0, false);

    private static final Map<String, String> SCENARIO_RESPONSES = new LinkedHashMap<>();

    static {
        SCENARIO_RESPONSES.put("solved a complex algorithm",
                "{\"conduciveness\": 0.9, \"controllability\": 0.9, \"adjustability\": 0.8, \"internal_standards\": 0.95, \"external_standards\": 0.95}");
        SCENARIO_RESPONSES.put("deployed the new feature",
                "{\"conduciveness\": 0.85, \"controllability\": 0.85, \"adjustability\": 0.9, \"internal_standards\": 0.95, \"external_standards\": 0.9}");
        SCENARIO_RESPONSES.put("approved my proposal",
                "{\"conduciveness\": 0.7, \"controllability\": 0.6, \"adjustability\": 0.7, \"internal_standards\": 0.9, \"external_standards\": 0.95}");
        SCENARIO_RESPONSES.put("metrics have improved",
                "{\"conduciveness\": 0.6, \"controllability\": 0.5, \"adjustability\": 0.6, \"internal_standards\": 0.9, \"external_standards\": 0.9}");
        SCENARIO_RESPONSES.put("completely down and I have no access",
                "{\"conduciveness\": -0.8, \"controllability\": 0.1, \"adjustability\": 0.15, \"internal_standards\": 0.8, \"external_standards\": 0.7}");
        SCENARIO_RESPONSES.put("deadline was moved up",
                "{\"conduciveness\": -0.5, \"controllability\": 0.25, \"adjustability\": 0.4, \"internal_standards\": 0.8, \"external_standards\": 0.85}");
        SCENARIO_RESPONSES.put("systematic errors",
                "{\"conduciveness\": -0.6, \"controllability\": 0.35, \"adjustability\": 0.45, \"internal_standards\": 0.7, \"external_standards\": 0.75}");
        SCENARIO_RESPONSES.put("tech stack might change",
                "{\"conduciveness\": -0.4, \"controllability\": 0.15, \"adjustability\": 0.3, \"internal_standards\": 0.85, \"external_standards\": 0.85}");
        SCENARIO_RESPONSES.put("not sure if it will work",
                "{\"conduciveness\": 0.2, \"controllability\": 0.55, \"adjustability\": 0.6, \"internal_standards\": 0.9, \"external_standards\": 0.9}");
        SCENARIO_RESPONSES.put("colleague achieved",
                "{\"conduciveness\": 0.4, \"controllability\": 0.3, \"adjustability\": 0.5, \"internal_standards\": 0.9, \"external_standards\": 0.9}");
        SCENARIO_RESPONSES.put("violates our SLA",
                "{\"conduciveness\": -0.7, \"controllability\": 0.3, \"adjustability\": 0.35, \"internal_standards\": 0.35, \"external_standards\": 0.2}");
        SCENARIO_RESPONSES.put("ignoring the code review",
                "{\"conduciveness\": -0.3, \"controllability\": 0.4, \"adjustability\": 0.5, \"internal_standards\": 0.7, \"external_standards\": 0.3}");
        SCENARIO_RESPONSES.put("locked and I don't have the key",
                "{\"conduciveness\": -0.5, \"controllability\": 0.1, \"adjustability\": 0.1, \"internal_standards\": 0.9, \"external_standards\": 0.9}");
        SCENARIO_RESPONSES.put("tools and training I need",
                "{\"conduciveness\": 0.6, \"controllability\": 0.95, \"adjustability\": 0.9, \"internal_standards\": 0.95, \"external_standards\": 0.95}");
        SCENARIO_RESPONSES.put("routine standup",
                "{\"conduciveness\": 0.05, \"controllability\": 0.7, \"adjustability\": 0.7, \"internal_standards\": 0.95, \"external_standards\": 0.95}");
    }

    private AgentProvider mockProvider() {
        return new AgentProvider() {
            @Override
            public Multi<AgentEvent> invoke(io.casehub.platform.agent.AgentSessionConfig config) {
                String prompt = config.userPrompt();
                for (var entry : SCENARIO_RESPONSES.entrySet()) {
                    if (prompt.contains(entry.getKey())) {
                        return Multi.createFrom().items(
                                new AgentEvent.TextDelta(entry.getValue()), COMPLETE);
                    }
                }
                return Multi.createFrom().items(
                        new AgentEvent.TextDelta(
                                "{\"conduciveness\": 0.0, \"controllability\": 0.5, \"adjustability\": 0.5, \"internal_standards\": 1.0, \"external_standards\": 1.0}"),
                        COMPLETE);
            }

            @Override
            public io.casehub.platform.agent.AgentSession openSession(
                    io.casehub.platform.agent.AgentSessionInit init) {
                throw new UnsupportedOperationException();
            }
        };
    }

    @Test
    void llmPipeline_producesDiverseEmotions() {
        var provider = mockProvider();
        var strategy = new SchererAppraisalStrategy(
                new RelevanceCheck(),
                new LlmImplicationCheck(provider),
                new LlmCopingCheck(provider),
                new LlmNormativeCheck(provider),
                SchererAppraisalConfig.allEnabled());

        Set<String> allEmotionTypes = new LinkedHashSet<>();
        Set<String> allTendencies = new LinkedHashSet<>();

        System.out.println("\n=== LLM Pipeline Results ===");
        System.out.printf("%-25s | %-40s | %-30s%n", "Scenario", "Emotions", "Tendencies");
        System.out.println("-".repeat(100));

        for (var scenario : ScenarioCorpus.scenarios()) {
            var ctx = new AppraisalContext(
                    PerceivedSituation.passThrough(scenario.observation()),
                    scenario.drives(), AppraisalWeights.NEUTRAL,
                    HabituationConfig.defaults(), HabituationState.empty(), null);

            var result = strategy.appraise(ctx);
            var emotionNames = result.emotions().stream()
                    .map(e -> e.type().name()).toList();
            var tendencyNames = result.actionTendencies().stream()
                    .filter(t -> t.intensity() > 0.3)
                    .map(t -> t.readiness().name()).toList();

            allEmotionTypes.addAll(emotionNames);
            allTendencies.addAll(tendencyNames);

            System.out.printf("%-25s | %-40s | %-30s%n",
                    scenario.name(),
                    emotionNames.isEmpty() ? "(none)" : String.join(", ", emotionNames),
                    tendencyNames.isEmpty() ? "(none)" : String.join(", ", tendencyNames));
        }

        System.out.printf("%nDistinct emotion types: %s (%d)%n", allEmotionTypes, allEmotionTypes.size());
        System.out.printf("Distinct tendencies:    %s (%d)%n", allTendencies, allTendencies.size());

        assertThat(allEmotionTypes)
                .as("LLM pipeline should produce at least 3 distinct emotion types")
                .hasSizeGreaterThanOrEqualTo(3);
        assertThat(allTendencies)
                .as("LLM pipeline should produce at least 3 distinct tendency types")
                .hasSizeGreaterThanOrEqualTo(3);
    }

    @Test
    void llmPipeline_mostScenariosProduceEmotions() {
        var provider = mockProvider();
        var strategy = new SchererAppraisalStrategy(
                new RelevanceCheck(),
                new LlmImplicationCheck(provider),
                new LlmCopingCheck(provider),
                new LlmNormativeCheck(provider),
                SchererAppraisalConfig.allEnabled());

        int scenariosWithEmotions = 0;
        for (var scenario : ScenarioCorpus.scenarios()) {
            var ctx = new AppraisalContext(
                    PerceivedSituation.passThrough(scenario.observation()),
                    scenario.drives(), AppraisalWeights.NEUTRAL,
                    HabituationConfig.defaults(), HabituationState.empty(), null);

            var result = strategy.appraise(ctx);
            if (!result.emotions().isEmpty()) scenariosWithEmotions++;
        }

        System.out.printf("%nScenarios with emotions: %d/%d%n",
                scenariosWithEmotions, ScenarioCorpus.scenarios().size());

        assertThat(scenariosWithEmotions)
                .as("At least half of scenarios should produce emotions with LLM checks")
                .isGreaterThanOrEqualTo(ScenarioCorpus.scenarios().size() / 2);
    }
}
```

- [ ] **Step 2: Run test to verify it fails (if LlmImplicationCheck/LlmNormativeCheck not yet created) or passes (if created in Tasks 1-2)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="io.casehub.neocortex.cognition.appraisal.experiment.LlmPipelineDiscriminationTest" -Dsurefire.useFile=false`

Expected: passes if Tasks 1-2 are done. Read output to confirm diverse emotions.

- [ ] **Step 3: Update CognitionDefaultBeans to use LLM checks**

Use `ide_replace_member` on the `appraisalStrategy` method in `CognitionDefaultBeans.java`. The update uses `Instance<AgentProvider>` for graceful degradation — LLM checks when provider available, keyword checks when not.

First, add an `@Inject` field to `CognitionDefaultBeans`:

```java
@Inject
Instance<AgentProvider> agentProviderInstance;
```

Then replace the `appraisalStrategy()` method body:

```java
        SecCheck implicationCheck;
        SecCheck copingCheck;
        SecCheck normativeCheck;

        if (agentProviderInstance.isResolvable()) {
            var provider = agentProviderInstance.get();
            implicationCheck = new LlmImplicationCheck(provider);
            copingCheck = new LlmCopingCheck(provider);
            normativeCheck = new LlmNormativeCheck(provider);
        } else {
            implicationCheck = new ImplicationCheck();
            copingCheck = new CopingCheck();
            normativeCheck = new NormativeCheck();
        }

        return new SchererAppraisalStrategy(
                new RelevanceCheck(),
                implicationCheck, copingCheck, normativeCheck,
                SchererAppraisalConfig.allEnabled());
```

- [ ] **Step 4: Run full test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dsurefire.useFile=false`

Expected: All tests pass. Existing tests still use direct instantiation so CDI change doesn't affect them.

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/experiment/LlmPipelineDiscriminationTest.java
git commit -m "feat(#430): wire LLM checks into CognitionDefaultBeans + end-to-end validation

CognitionDefaultBeans now uses LLM-backed ImplicationCheck, CopingCheck,
and NormativeCheck when AgentProvider is available, falling back to
keyword checks when it's not. RelevanceCheck stays computational.

End-to-end test validates the LLM pipeline produces 3+ emotion types
and 3+ tendency types across 15 scenarios — the assertion that failed
with keyword checks in #429.

Refs #430

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## References

- [GitHub #430](https://github.com/casehubio/neocortex/issues/430) — focal issue
- [GitHub #429](https://github.com/casehubio/neocortex/issues/429) — experiment findings
- [GitHub #428](https://github.com/casehubio/neocortex/issues/428) — CARMA architecture
- `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/LlmCopingCheck.java` — pattern to follow
- `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/SchererAppraisalStrategy.java` — composition target
- `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java:118-128` — CDI wiring
- `cognition/src/main/java/io/casehub/neocortex/cognition/reflection/LlmReflectionSynthesizer.java` — Instance<AgentProvider> pattern
- `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/experiment/ScenarioCorpus.java` — test scenarios
- `GE-20261005-57982c` — garden entry: keyword-based appraisal checks are inert

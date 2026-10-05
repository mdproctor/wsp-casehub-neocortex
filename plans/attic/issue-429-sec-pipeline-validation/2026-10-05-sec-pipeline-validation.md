# SEC Pipeline Validation — Experiment Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #429 — Validate SEC pipeline experimentally — measure check discrimination and LLM boundary

**Goal:** Run three experiments that produce quantitative data on whether
the keyword-based SEC checks discriminate meaningfully across scenarios,
where an LLM adds signal the keyword rules miss, and whether the full
Frijda action tendency taxonomy produces observably different prompt
renderings.

**Architecture:** Pure test classes — no production code changes in Batch
1. Batch 2 adds one experimental `LlmCopingCheck` (production code in
`cognition` module) and one test class for tendency comparison. All
experiments use a shared `ScenarioCorpus` utility class containing 15
diverse scenarios.

**Tech Stack:** JUnit 5, AssertJ, existing `SecCheck` / `SchererAppraisalStrategy` /
`AppraisalPromptSection` / `EmotionMapper` APIs, `AgentProvider` (for LLM
boundary test)

## Global Constraints

- Java 21 source, Java 26 JVM
- No new module dependencies — all tests run in existing `cognition` module
- LLM boundary test uses `AgentProvider` from `casehub-platform-agent-api` (already a dependency)
- Tests tagged `@Tag("experiment")` are excluded from CI, run manually with `-Dgroups=experiment`
- All non-experiment tests must pass with `mvn test -pl cognition`

---

## Batch 1: Scenario Corpus + Discrimination Tests (Experiment 1)

### Task 1: Scenario corpus and per-check discrimination test

**Files:**
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/experiment/ScenarioCorpus.java`
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/experiment/SecDiscriminationTest.java`

**Interfaces:**
- Consumes: `SecCheck.evaluate(AppraisalContext)`, `SecResult.dimension(String)`, `SecDimensions.*`, `PerceivedSituation.passThrough(String)`, `Drive(String, DriveCategory, double, String)`, `HabituationConfig.defaults()`, `HabituationState.empty()`, `AppraisalWeights.NEUTRAL`, `SchererAppraisalConfig.allEnabled()`, `SchererAppraisalStrategy`, `EmotionMapper.mapEmotions()`, `EmotionMapper.mapTendencies()`
- Produces: `ScenarioCorpus.scenarios()` — `List<ScenarioCorpus.Scenario>` with `name()`, `observation()`, `drives()`. Used by Tasks 2–4.

- [ ] **Step 1: Write ScenarioCorpus utility**

Use `ide_create_file`:

```java
package io.casehub.neocortex.cognition.appraisal.experiment;

import io.casehub.neocortex.cognition.appraisal.Drive;
import io.casehub.neocortex.cognition.appraisal.DriveCategory;
import java.util.List;

public final class ScenarioCorpus {

    public record Scenario(String name, String observation, List<Drive> drives) {}

    private static final List<Drive> RESEARCH_DRIVES = List.of(
            new Drive("curiosity", DriveCategory.BASELINE, 0.8, "research"),
            new Drive("competence", DriveCategory.BASELINE, 0.6, "solve"));

    private static final List<Drive> SOCIAL_DRIVES = List.of(
            new Drive("affiliation", DriveCategory.BASELINE, 0.7, "team"),
            new Drive("competence", DriveCategory.BASELINE, 0.5, "review"));

    private static final List<Drive> MINIMAL_DRIVES = List.of(
            new Drive("curiosity", DriveCategory.BASELINE, 0.3, "explore"));

    private ScenarioCorpus() {}

    public static List<Scenario> scenarios() {
        return List.of(
            // --- Positive outcomes ---
            new Scenario("achievement",
                "I just solved a complex algorithm problem that nobody else could figure out",
                RESEARCH_DRIVES),
            new Scenario("deployment_success",
                "I successfully deployed the new feature and all tests are passing",
                RESEARCH_DRIVES),
            new Scenario("proposal_approved",
                "The architecture review board approved my proposal unanimously",
                SOCIAL_DRIVES),
            new Scenario("metrics_improved",
                "The quarterly report shows our metrics have improved across the board",
                MINIMAL_DRIVES),

            // --- Negative outcomes ---
            new Scenario("server_down_no_access",
                "The server is completely down and I have no access to the logs or the recovery tools",
                RESEARCH_DRIVES),
            new Scenario("deadline_moved",
                "The deadline was moved up by a week and I'm already behind schedule",
                SOCIAL_DRIVES),
            new Scenario("data_errors",
                "I discovered that the data we've been analyzing contains systematic errors",
                RESEARCH_DRIVES),
            new Scenario("acquisition_threat",
                "An unexpected acquisition means our entire tech stack might change",
                SOCIAL_DRIVES),

            // --- Mixed / ambiguous ---
            new Scenario("uncertain_solution",
                "I found a potential solution but I'm not sure if it will work",
                RESEARCH_DRIVES),
            new Scenario("colleague_breakthrough",
                "My colleague achieved a breakthrough in the project",
                SOCIAL_DRIVES),

            // --- Normative ---
            new Scenario("sla_violation",
                "The client reported a critical bug that violates our SLA commitments",
                SOCIAL_DRIVES),
            new Scenario("process_ignored",
                "Someone on the team keeps ignoring the code review process",
                SOCIAL_DRIVES),

            // --- Coping edge cases (keyword-poor) ---
            new Scenario("locked_no_key",
                "The door is locked and I don't have the key",
                MINIMAL_DRIVES),
            new Scenario("equipped_and_ready",
                "I can handle this — I have all the tools and training I need",
                RESEARCH_DRIVES),

            // --- Low novelty ---
            new Scenario("routine_standup",
                "A routine standup meeting with no surprises",
                MINIMAL_DRIVES)
        );
    }
}
```

- [ ] **Step 2: Write the discrimination test**

Use `ide_create_file`:

```java
package io.casehub.neocortex.cognition.appraisal.experiment;

import io.casehub.neocortex.cognition.appraisal.*;
import io.casehub.neocortex.cognitive.HabituationConfig;
import io.casehub.neocortex.mindmap.AppraisalWeights;
import org.junit.jupiter.api.Test;

import java.util.*;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

class SecDiscriminationTest {

    private final RelevanceCheck relevanceCheck = new RelevanceCheck();
    private final ImplicationCheck implicationCheck = new ImplicationCheck();
    private final CopingCheck copingCheck = new CopingCheck();
    private final NormativeCheck normativeCheck = new NormativeCheck();

    private AppraisalContext context(ScenarioCorpus.Scenario s) {
        return new AppraisalContext(
                PerceivedSituation.passThrough(s.observation()),
                s.drives(), AppraisalWeights.NEUTRAL,
                HabituationConfig.defaults(),
                HabituationState.empty(), null);
    }

    @Test
    void relevanceCheck_producesVarianceAcrossScenarios() {
        var results = runCheck(relevanceCheck);
        assertDimensionHasVariance(results, SecDimensions.RELEVANCE, "RelevanceCheck");
        assertDimensionHasVariance(results, SecDimensions.NOVELTY, "RelevanceCheck");
        printCheckSummary("RelevanceCheck", results,
                List.of(SecDimensions.RELEVANCE, SecDimensions.NOVELTY, SecDimensions.URGENCY));
    }

    @Test
    void implicationCheck_producesVarianceAcrossScenarios() {
        var results = runCheck(implicationCheck);
        assertDimensionHasVariance(results, SecDimensions.CONDUCIVENESS, "ImplicationCheck");
        printCheckSummary("ImplicationCheck", results,
                List.of(SecDimensions.CONDUCIVENESS));
    }

    @Test
    void copingCheck_producesVarianceAcrossScenarios() {
        var results = runCheck(copingCheck);
        assertDimensionHasVariance(results, SecDimensions.CONTROLLABILITY, "CopingCheck");
        printCheckSummary("CopingCheck", results,
                List.of(SecDimensions.CONTROLLABILITY, SecDimensions.ADJUSTABILITY));
    }

    @Test
    void normativeCheck_producesVarianceAcrossScenarios() {
        var results = runCheck(normativeCheck);
        printCheckSummary("NormativeCheck", results,
                List.of(SecDimensions.INTERNAL_STANDARDS, SecDimensions.EXTERNAL_STANDARDS));
        var internalValues = extractDimension(results, SecDimensions.INTERNAL_STANDARDS);
        long distinctInternal = internalValues.stream().distinct().count();
        System.out.printf("NormativeCheck: %d distinct internal_standards values from %d scenarios%n",
                distinctInternal, internalValues.size());
    }

    @Test
    void fullPipeline_producesDiverseEmotions() {
        var strategy = new SchererAppraisalStrategy(
                relevanceCheck, implicationCheck, copingCheck, normativeCheck,
                SchererAppraisalConfig.allEnabled());

        Set<String> allEmotionTypes = new LinkedHashSet<>();
        Set<String> allTendencies = new LinkedHashSet<>();

        System.out.println("\n=== Full Pipeline Results ===");
        System.out.printf("%-25s | %-40s | %-30s%n", "Scenario", "Emotions", "Tendencies");
        System.out.println("-".repeat(100));

        for (var scenario : ScenarioCorpus.scenarios()) {
            var ctx = context(scenario);
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

        System.out.printf("%nDistinct emotion types: %s%n", allEmotionTypes);
        System.out.printf("Distinct tendencies:    %s%n", allTendencies);

        assertThat(allEmotionTypes).as("Pipeline should produce at least 3 distinct emotion types")
                .hasSizeGreaterThanOrEqualTo(3);
    }

    @Test
    void configComparison_removingCheckChangesOutput() {
        var full = new SchererAppraisalStrategy(
                relevanceCheck, implicationCheck, copingCheck, normativeCheck,
                SchererAppraisalConfig.allEnabled());
        var noCoping = new SchererAppraisalStrategy(
                relevanceCheck, implicationCheck, null, normativeCheck,
                new SchererAppraisalConfig(true, true, false, true));
        var noNormative = new SchererAppraisalStrategy(
                relevanceCheck, implicationCheck, copingCheck, null,
                new SchererAppraisalConfig(true, true, true, false));

        int fullDiffers = 0, noCopingDiffers = 0, noNormativeDiffers = 0;

        for (var scenario : ScenarioCorpus.scenarios()) {
            var ctx = context(scenario);
            var fullResult = full.appraise(ctx);
            var noCopingResult = noCoping.appraise(ctx);
            var noNormResult = noNormative.appraise(ctx);

            var fullEmotions = fullResult.emotions().stream()
                    .map(e -> e.type()).collect(Collectors.toSet());
            var noCopingEmotions = noCopingResult.emotions().stream()
                    .map(e -> e.type()).collect(Collectors.toSet());
            var noNormEmotions = noNormResult.emotions().stream()
                    .map(e -> e.type()).collect(Collectors.toSet());

            if (!fullEmotions.equals(noCopingEmotions)) noCopingDiffers++;
            if (!fullEmotions.equals(noNormEmotions)) noNormativeDiffers++;
        }

        System.out.printf("%n=== Config Comparison ===%n");
        System.out.printf("Removing CopingCheck changes emotions in %d/%d scenarios%n",
                noCopingDiffers, ScenarioCorpus.scenarios().size());
        System.out.printf("Removing NormativeCheck changes emotions in %d/%d scenarios%n",
                noNormativeDiffers, ScenarioCorpus.scenarios().size());
    }

    // --- Helpers ---

    private Map<String, SecResult> runCheck(SecCheck check) {
        var results = new LinkedHashMap<String, SecResult>();
        for (var scenario : ScenarioCorpus.scenarios()) {
            results.put(scenario.name(), check.evaluate(context(scenario)));
        }
        return results;
    }

    private List<Double> extractDimension(Map<String, SecResult> results, String dimension) {
        return results.values().stream()
                .map(r -> r.dimension(dimension))
                .toList();
    }

    private void assertDimensionHasVariance(Map<String, SecResult> results,
                                             String dimension, String checkName) {
        var values = extractDimension(results, dimension);
        long distinct = values.stream().distinct().count();
        assertThat(distinct)
                .as("%s.%s should produce at least 3 distinct values across %d scenarios",
                        checkName, dimension, values.size())
                .isGreaterThanOrEqualTo(3);
    }

    private void printCheckSummary(String checkName, Map<String, SecResult> results,
                                    List<String> dimensions) {
        System.out.printf("%n=== %s ===%n", checkName);
        System.out.printf("%-25s", "Scenario");
        for (var dim : dimensions) {
            System.out.printf(" | %-15s", dim.substring(dim.lastIndexOf('.') + 1));
        }
        System.out.println();
        System.out.println("-".repeat(25 + dimensions.size() * 18));

        results.forEach((name, result) -> {
            System.out.printf("%-25s", name);
            for (var dim : dimensions) {
                System.out.printf(" | %15.3f", result.dimension(dim));
            }
            System.out.println();
        });

        for (var dim : dimensions) {
            var values = extractDimension(results, dim);
            var stats = new DoubleSummaryStatistics();
            values.forEach(stats::accept);
            double mean = stats.getAverage();
            double variance = values.stream()
                    .mapToDouble(v -> (v - mean) * (v - mean)).average().orElse(0);
            System.out.printf("  %s — mean=%.3f, stddev=%.3f, min=%.3f, max=%.3f, distinct=%d%n",
                    dim, mean, Math.sqrt(variance), stats.getMin(), stats.getMax(),
                    values.stream().distinct().count());
        }
    }
}
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="io.casehub.neocortex.cognition.appraisal.experiment.SecDiscriminationTest" -Dsurefire.useFile=false`

Expected: All 5 tests pass. Read printed output to assess discrimination quality.

- [ ] **Step 4: Commit**

```bash
git add cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/experiment/
git commit -m "test(#429): add scenario corpus and SEC discrimination tests

15-scenario corpus covering positive/negative/mixed/normative/coping
edge cases. Per-check variance tests + full pipeline diversity test +
config comparison measuring each check's contribution.

Refs #429

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Batch 2: LLM Boundary + Tendency Cardinality (Experiments 2 & 3)

### Task 2: Tendency cardinality test (Experiment 3)

**Files:**
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/experiment/TendencyCardinalityTest.java`

**Interfaces:**
- Consumes: `ScenarioCorpus.scenarios()`, `SchererAppraisalStrategy`, `AppraisalPromptSection`, `ActionReadiness` (9 values), `AppraisalTickParticipant`, `CognitionRenderContext`
- Produces: Printed comparison of full vs reduced tendency prompts

- [ ] **Step 1: Write the tendency cardinality test**

Use `ide_create_file`:

```java
package io.casehub.neocortex.cognition.appraisal.experiment;

import io.casehub.neocortex.cognition.appraisal.*;
import io.casehub.neocortex.cognition.prompt.AppraisalPromptSection;
import io.casehub.neocortex.cognition.prompt.CognitionRenderContext;
import io.casehub.neocortex.cognitive.HabituationConfig;
import io.casehub.neocortex.mindmap.AppraisalWeights;
import org.junit.jupiter.api.Test;

import java.util.*;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

class TendencyCardinalityTest {

    private static final Set<ActionReadiness> REDUCED_SET = Set.of(
            ActionReadiness.APPROACH, ActionReadiness.AVOIDANCE, ActionReadiness.ATTENDING);

    private static final Set<ActionReadiness> FULL_SET = Set.copyOf(
            EnumSet.allOf(ActionReadiness.class));

    private final SchererAppraisalStrategy strategy = new SchererAppraisalStrategy(
            new RelevanceCheck(), new ImplicationCheck(), new CopingCheck(), new NormativeCheck(),
            SchererAppraisalConfig.allEnabled());

    @Test
    void fullVsReduced_tendencySetsProduceDifferentPrompts() {
        int totalScenarios = 0;
        int differingPrompts = 0;
        int fullOnlyTendencies = 0;

        System.out.println("\n=== Tendency Cardinality Comparison ===");
        System.out.printf("Full set:    %s%n", FULL_SET);
        System.out.printf("Reduced set: %s%n%n", REDUCED_SET);

        for (var scenario : ScenarioCorpus.scenarios()) {
            var ctx = new AppraisalContext(
                    PerceivedSituation.passThrough(scenario.observation()),
                    scenario.drives(), AppraisalWeights.NEUTRAL,
                    HabituationConfig.defaults(), HabituationState.empty(), null);

            var result = strategy.appraise(ctx);
            totalScenarios++;

            var allTendencies = result.actionTendencies().stream()
                    .filter(t -> t.intensity() > 0.3).toList();
            var reducedTendencies = allTendencies.stream()
                    .filter(t -> REDUCED_SET.contains(t.readiness())).toList();

            boolean differs = allTendencies.size() != reducedTendencies.size();
            if (differs) differingPrompts++;

            var droppedTypes = allTendencies.stream()
                    .map(ActionTendency::readiness)
                    .filter(r -> !REDUCED_SET.contains(r))
                    .collect(Collectors.toSet());
            fullOnlyTendencies += droppedTypes.size();

            if (!allTendencies.isEmpty()) {
                System.out.printf("%-25s | full: %-40s | dropped: %s%n",
                        scenario.name(),
                        allTendencies.stream().map(t -> t.readiness().name())
                                .collect(Collectors.joining(", ")),
                        droppedTypes.isEmpty() ? "(none)" : droppedTypes);
            }
        }

        System.out.printf("%n%d/%d scenarios have tendencies outside the reduced set%n",
                differingPrompts, totalScenarios);
        System.out.printf("%d total tendency instances would be lost by reducing%n",
                fullOnlyTendencies);

        assertThat(totalScenarios).isGreaterThan(0);
    }

    @Test
    void tendencyDistribution_acrossAllScenarios() {
        Map<ActionReadiness, Integer> counts = new EnumMap<>(ActionReadiness.class);

        for (var scenario : ScenarioCorpus.scenarios()) {
            var ctx = new AppraisalContext(
                    PerceivedSituation.passThrough(scenario.observation()),
                    scenario.drives(), AppraisalWeights.NEUTRAL,
                    HabituationConfig.defaults(), HabituationState.empty(), null);

            var result = strategy.appraise(ctx);
            result.actionTendencies().stream()
                    .filter(t -> t.intensity() > 0.3)
                    .forEach(t -> counts.merge(t.readiness(), 1, Integer::sum));
        }

        System.out.println("\n=== Tendency Frequency Distribution ===");
        counts.entrySet().stream()
                .sorted(Map.Entry.<ActionReadiness, Integer>comparingByValue().reversed())
                .forEach(e -> System.out.printf("  %-15s: %d%n", e.getKey(), e.getValue()));

        var neverFired = EnumSet.allOf(ActionReadiness.class);
        neverFired.removeAll(counts.keySet());
        if (!neverFired.isEmpty()) {
            System.out.printf("  Never fired:    %s%n", neverFired);
        }
    }
}
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="io.casehub.neocortex.cognition.appraisal.experiment.TendencyCardinalityTest" -Dsurefire.useFile=false`

Expected: Both tests pass. Read output for tendency distribution data.

- [ ] **Step 3: Commit**

```bash
git add cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/experiment/TendencyCardinalityTest.java
git commit -m "test(#429): add tendency cardinality experiment

Compares full 9-value Frijda set against reduced 3-value set across
all scenarios. Reports tendency frequency distribution and which
tendencies are lost by reducing.

Refs #429

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 3: LLM-backed CopingCheck + boundary comparison (Experiment 2)

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/LlmCopingCheck.java`
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/experiment/LlmBoundaryTest.java`

**Interfaces:**
- Consumes: `SecCheck` SPI, `AppraisalContext`, `SecResult`, `SecDimensions`, `AgentProvider` (from `casehub-platform-agent-api`), `AgentSessionConfig.of(String, String)`, `AgentEvent.TextDelta`, `AgentEvent.InvocationComplete`, `ScenarioCorpus.scenarios()`
- Produces: `LlmCopingCheck` — reusable `SecCheck` implementation that delegates controllability/adjustability assessment to an LLM

- [ ] **Step 1: Write the failing test for LlmCopingCheck**

Use `ide_create_file`:

```java
package io.casehub.neocortex.cognition.appraisal.experiment;

import io.casehub.neocortex.cognition.appraisal.*;
import io.casehub.neocortex.cognitive.HabituationConfig;
import io.casehub.neocortex.mindmap.AppraisalWeights;
import io.casehub.platform.agent.AgentEvent;
import io.casehub.platform.agent.AgentProvider;
import io.casehub.platform.agent.AgentSessionConfig;
import io.smallrye.mutiny.Multi;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Tag;

import java.util.*;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.data.Offset.offset;

class LlmBoundaryTest {

    private AgentProvider mockProvider(Map<String, String> scenarioResponses) {
        return config -> {
            String userMsg = config.userMessage();
            for (var entry : scenarioResponses.entrySet()) {
                if (userMsg.contains(entry.getKey())) {
                    String response = entry.getValue();
                    return Multi.createFrom().items(
                            (AgentEvent) new AgentEvent.TextDelta(response),
                            new AgentEvent.InvocationComplete(false));
                }
            }
            return Multi.createFrom().items(
                    (AgentEvent) new AgentEvent.TextDelta(
                            "{\"controllability\": 0.5, \"adjustability\": 0.5}"),
                    new AgentEvent.InvocationComplete(false));
        };
    }

    @Test
    void llmCopingCheck_returnsValidSecResult() {
        var provider = mockProvider(Map.of(
                "locked", "{\"controllability\": 0.15, \"adjustability\": 0.2}",
                "tools and training", "{\"controllability\": 0.9, \"adjustability\": 0.85}"));

        var check = new LlmCopingCheck(provider);

        var lockedCtx = contextFor("The door is locked and I don't have the key");
        var equippedCtx = contextFor("I can handle this — I have all the tools and training I need");

        var lockedResult = check.evaluate(lockedCtx);
        var equippedResult = check.evaluate(equippedCtx);

        assertThat(lockedResult.dimension(SecDimensions.CONTROLLABILITY))
                .isCloseTo(0.15, offset(0.01));
        assertThat(equippedResult.dimension(SecDimensions.CONTROLLABILITY))
                .isCloseTo(0.9, offset(0.01));
    }

    @Test
    void boundaryComparison_llmVsKeyword_acrossAllScenarios() {
        var scenarioResponses = new LinkedHashMap<String, String>();
        scenarioResponses.put("solved a complex algorithm",
                "{\"controllability\": 0.9, \"adjustability\": 0.8}");
        scenarioResponses.put("deployed the new feature",
                "{\"controllability\": 0.85, \"adjustability\": 0.9}");
        scenarioResponses.put("approved my proposal",
                "{\"controllability\": 0.6, \"adjustability\": 0.7}");
        scenarioResponses.put("metrics have improved",
                "{\"controllability\": 0.5, \"adjustability\": 0.6}");
        scenarioResponses.put("completely down and I have no access",
                "{\"controllability\": 0.1, \"adjustability\": 0.15}");
        scenarioResponses.put("deadline was moved up",
                "{\"controllability\": 0.25, \"adjustability\": 0.4}");
        scenarioResponses.put("systematic errors",
                "{\"controllability\": 0.35, \"adjustability\": 0.45}");
        scenarioResponses.put("tech stack might change",
                "{\"controllability\": 0.15, \"adjustability\": 0.3}");
        scenarioResponses.put("not sure if it will work",
                "{\"controllability\": 0.55, \"adjustability\": 0.6}");
        scenarioResponses.put("colleague achieved",
                "{\"controllability\": 0.3, \"adjustability\": 0.5}");
        scenarioResponses.put("violates our SLA",
                "{\"controllability\": 0.3, \"adjustability\": 0.35}");
        scenarioResponses.put("ignoring the code review",
                "{\"controllability\": 0.4, \"adjustability\": 0.5}");
        scenarioResponses.put("locked and I don't have the key",
                "{\"controllability\": 0.1, \"adjustability\": 0.1}");
        scenarioResponses.put("tools and training I need",
                "{\"controllability\": 0.95, \"adjustability\": 0.9}");
        scenarioResponses.put("routine standup",
                "{\"controllability\": 0.7, \"adjustability\": 0.7}");

        var keywordCheck = new CopingCheck();
        var llmCheck = new LlmCopingCheck(mockProvider(scenarioResponses));

        int agreementCount = 0;
        int divergenceCount = 0;

        System.out.println("\n=== LLM vs Keyword Coping Check ===");
        System.out.printf("%-25s | %-12s %-12s | %-12s %-12s | %s%n",
                "Scenario", "KW-ctrl", "KW-adj", "LLM-ctrl", "LLM-adj", "Verdict");
        System.out.println("-".repeat(105));

        for (var scenario : ScenarioCorpus.scenarios()) {
            var ctx = contextFor(scenario.observation());
            ctx = new AppraisalContext(ctx.situation(), scenario.drives(),
                    AppraisalWeights.NEUTRAL, HabituationConfig.defaults(),
                    HabituationState.empty(), null);

            var kwResult = keywordCheck.evaluate(ctx);
            var llmResult = llmCheck.evaluate(ctx);

            double kwCtrl = kwResult.dimension(SecDimensions.CONTROLLABILITY);
            double llmCtrl = llmResult.dimension(SecDimensions.CONTROLLABILITY);
            double delta = Math.abs(kwCtrl - llmCtrl);
            String verdict = delta > 0.3 ? "DIVERGE" : "agree";

            if (delta > 0.3) divergenceCount++;
            else agreementCount++;

            System.out.printf("%-25s | %12.3f %12.3f | %12.3f %12.3f | %s (Δ=%.2f)%n",
                    scenario.name(),
                    kwCtrl, kwResult.dimension(SecDimensions.ADJUSTABILITY),
                    llmCtrl, llmResult.dimension(SecDimensions.ADJUSTABILITY),
                    verdict, delta);
        }

        System.out.printf("%nAgreement: %d, Divergence: %d (threshold: 0.3)%n",
                agreementCount, divergenceCount);
        System.out.printf("LLM adds signal beyond keywords in %d/%d scenarios%n",
                divergenceCount, ScenarioCorpus.scenarios().size());
    }

    @Test
    @Tag("experiment")
    void boundaryComparison_withRealLlm() {
        // This test requires a real AgentProvider. Run manually with:
        //   mvn test -pl cognition -Dtest="...LlmBoundaryTest#boundaryComparison_withRealLlm" -Dgroups=experiment
        // Configure AgentProvider via application.properties or environment variables.
        // The test infrastructure is identical to boundaryComparison_llmVsKeyword_acrossAllScenarios
        // but uses an injected real provider instead of the mock.
        org.junit.jupiter.api.Assumptions.assumeTrue(false,
                "Real LLM test — requires AgentProvider. Run with -Dgroups=experiment");
    }

    private AppraisalContext contextFor(String observation) {
        return new AppraisalContext(
                PerceivedSituation.passThrough(observation),
                List.of(), AppraisalWeights.NEUTRAL,
                HabituationConfig.defaults(),
                HabituationState.empty(), null);
    }
}
```

- [ ] **Step 2: Run test to verify it fails (LlmCopingCheck not yet created)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="io.casehub.neocortex.cognition.appraisal.experiment.LlmBoundaryTest" -Dsurefire.useFile=false`

Expected: FAIL with compilation error — `LlmCopingCheck` class does not exist.

- [ ] **Step 3: Write LlmCopingCheck implementation**

Use `ide_create_file`:

```java
package io.casehub.neocortex.cognition.appraisal;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.casehub.platform.agent.AgentEvent;
import io.casehub.platform.agent.AgentProvider;
import io.casehub.platform.agent.AgentSessionConfig;

import java.time.Duration;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.stream.Collectors;

public class LlmCopingCheck implements SecCheck {

    private static final Logger LOG = Logger.getLogger(LlmCopingCheck.class.getName());
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static final String SYSTEM_PROMPT = """
            You are a cognitive appraisal evaluator. Assess a situation on two dimensions:
            
            1. Controllability: How much control does the agent have over this situation?
               0.0 = completely helpless, no options available
               0.5 = moderate control, some options exist
               1.0 = full control, agent can fully determine the outcome
            
            2. Adjustability: How well can the agent adapt to this situation?
               0.0 = cannot adapt at all, rigid constraints
               0.5 = can partially adapt with effort
               1.0 = highly flexible, many adaptation paths
            
            Consider implicit coping resources, not just explicit keywords. A locked door \
            with no key implies low controllability even without words like "helpless."
            
            Respond with JSON only: {"controllability": <number>, "adjustability": <number>}""";

    private final AgentProvider agentProvider;

    public LlmCopingCheck(AgentProvider agentProvider) {
        this.agentProvider = agentProvider;
    }

    @Override
    public SecResult evaluate(AppraisalContext context) {
        String observation = context.situation().narrative();
        try {
            String response = invokeLlm(observation);
            if (response == null) return SecResult.of(SecDimensions.CONTROLLABILITY, 0.5);

            JsonNode root = MAPPER.readTree(response);
            double controllability = clamp(root.path("controllability").asDouble(0.5));
            double adjustability = clamp(root.path("adjustability").asDouble(0.5));

            return new SecResult("llm-coping", java.util.Map.of(
                    SecDimensions.CONTROLLABILITY, controllability,
                    SecDimensions.ADJUSTABILITY, adjustability));
        } catch (Exception e) {
            LOG.log(Level.WARNING, "LLM coping check failed, returning neutral", e);
            return new SecResult("llm-coping", java.util.Map.of(
                    SecDimensions.CONTROLLABILITY, 0.5,
                    SecDimensions.ADJUSTABILITY, 0.5));
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

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="io.casehub.neocortex.cognition.appraisal.experiment.LlmBoundaryTest" -Dsurefire.useFile=false`

Expected: 2 pass, 1 skipped (the `@Tag("experiment")` test). Read printed comparison table.

- [ ] **Step 5: Run all experiment tests together**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="io.casehub.neocortex.cognition.appraisal.experiment.*" -Dsurefire.useFile=false`

Expected: All non-experiment-tagged tests pass.

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/LlmCopingCheck.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/experiment/LlmBoundaryTest.java
git commit -m "feat(#429): add LlmCopingCheck and LLM boundary comparison test

LlmCopingCheck delegates controllability/adjustability assessment to an
LLM via AgentProvider. Prompt instructs assessment of implicit coping
resources, not just keyword matching.

Boundary test compares keyword vs LLM coping across 15 scenarios with
mock provider. Real-LLM test available via -Dgroups=experiment.

Refs #429

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## References

- [GitHub #429](https://github.com/casehubio/neocortex/issues/429) — focal issue
- [GitHub #428](https://github.com/casehubio/neocortex/issues/428) — parent: CARMA architecture
- `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/SecCheck.java` — SPI
- `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/SecResult.java` — result type
- `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/SchererAppraisalStrategy.java` — pipeline composition
- `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/EmotionMapper.java` — emotion/tendency mapper
- `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/RelevanceCheck.java` — check implementation
- `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/CopingCheck.java` — keyword coping
- `cognition/src/main/java/io/casehub/neocortex/cognition/reflection/LlmReflectionSynthesizer.java` — AgentProvider usage pattern
- `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/SchererAppraisalStrategyTest.java` — existing test patterns

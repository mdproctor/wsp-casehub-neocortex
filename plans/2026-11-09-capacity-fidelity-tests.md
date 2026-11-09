# Capacity Fidelity Eval Tests — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #900 — Capacity fidelity testing — does the LLM stay true to cognitive self-description?
**Issue group:** #841 (parent epic)

**Goal:** Validate that cognitive capacity self-descriptions causally influence LLM problem-solving behaviour — testing fidelity, authenticity, and differentiation.

**Architecture:** Single test class `CapacityFidelityEvalTest` in caps-llm-classifier eval package. Reuses CognitionTestHarness (test-jar), EvalLlmJudge, and the researcher system prompt from CognitiveExplorationEvalTest. 10 scenarios across 5 groups testing 3 capacity dimensions against matched problem types.

**Tech Stack:** JUnit 5, CognitionTestHarness, EvalLlmJudge, AgentProvider (Claude CLI)

## Global Constraints

- Tag: `@Tag("llm-eval")` — excluded from default Maven build
- Judge threshold: ≥3/5 per scenario
- Results: `target/experiment-results/capacity-fidelity-eval.json`

---

## Batch 1: Complete test class

### Task 1: Create CapacityFidelityEvalTest with all 5 groups

**Files:**
- Create: `caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/eval/CapacityFidelityEvalTest.java`

**Interfaces:**
- Consumes: `CognitionTestHarness` (cognition test-jar), `CognitiveDefaults.empty().withCapacityConfig()`, `CognitiveCapacityConfig`, `EvalLlmJudge`, `EvalAgentResponse`, `EvalTestSupport`, `CognitiveExplorationEvalTest.EXPLORATION_SYSTEM_PROMPT`

- [ ] **Step 1: Create test class with all scenarios**

Create `CapacityFidelityEvalTest.java` with full content:

```java
package io.casehub.neocortex.caps.llm.eval;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import io.casehub.neocortex.cognitive.CognitiveCapacityConfig;
import io.casehub.neocortex.cognitive.index.CognitiveDefaults;
import io.casehub.neocortex.cognition.eval.CognitionTestHarness;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import io.casehub.platform.agent.AgentEvent;
import io.casehub.platform.agent.AgentProvider;
import io.casehub.platform.agent.AgentSessionConfig;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@Tag("llm-eval")
class CapacityFidelityEvalTest {

    private static final Path OUTPUT_DIR = Path.of("target/experiment-results");
    private static final int JUDGE_THRESHOLD = 3;
    private static final String TENANT = "test-tenant";

    private static final CognitiveCapacityConfig HIGH_CAPACITY =
            new CognitiveCapacityConfig(0.90, 0.90, 0.90);
    private static final CognitiveCapacityConfig LOW_CAPACITY =
            new CognitiveCapacityConfig(0.40, 0.40, 0.40);

    private static final String SYLLOGISM =
            "All mammals are warm-blooded. Whales are mammals. "
                    + "What can you conclude about whales? Show your reasoning.";
    private static final String CHAIN =
            "If A implies B, B implies C, C implies D, and D implies E — and A is true — "
                    + "trace the full chain and explain what you can conclude about E. "
                    + "Show your reasoning at each step.";
    private static final String ANALOGY =
            "How is the immune system like a jazz ensemble? Find the deepest structural "
                    + "analogy you can — not surface similarities, but how they work in "
                    + "fundamentally similar ways.";
    private static final String THREADS =
            "Consider these four things simultaneously: "
                    + "(1) a policy that reduces carbon emissions but increases energy costs, "
                    + "(2) the psychological impact of price uncertainty on low-income households, "
                    + "(3) how renewable energy subsidies interact with market pricing, and "
                    + "(4) the political feasibility of carbon taxes in election years. "
                    + "How do all four connect? Hold them all in mind and trace the interactions.";

    private AgentProvider agentProvider;
    private EvalLlmJudge judge;

    @BeforeAll
    void setUp() {
        agentProvider = EvalTestSupport.agentProvider();
        judge = new EvalLlmJudge(agentProvider);
    }

    // ---- Group 1: Baseline — 2-step syllogism ----

    @Test
    void baselineHigh_solvesCleanly() {
        int score = runCapacityScenario("baseline-high", HIGH_CAPACITY, SYLLOGISM,
                "Does the response solve the syllogism correctly with clean, "
                        + "confident reasoning? Score on clarity and correctness.");

        assertThat(score).as("High capacity should solve syllogism cleanly")
                .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
    }

    @Test
    void baselineLow_stillSolves() {
        int score = runCapacityScenario("baseline-low", LOW_CAPACITY, SYLLOGISM,
                "Does the response solve the syllogism correctly? A 2-step problem "
                        + "should be within any capacity. Score on whether it reaches "
                        + "the correct conclusion, regardless of style.");

        assertThat(score).as("Low capacity should still solve a 2-step syllogism")
                .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
    }

    @Test
    void baselineNull_noCapacityDescription() {
        int score = runCapacityScenario("baseline-null", null, SYLLOGISM,
                "Does the response solve the syllogism correctly with clean reasoning "
                        + "and no self-referential language about cognitive limitations? "
                        + "Score on clean correctness.");

        assertThat(score).as("Null capacity should solve with no limitation language")
                .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
    }

    // ---- Group 2: Relational complexity — 4-step chain ----

    @Test
    void chainHigh_cleanMultiStepReasoning() {
        var config = new CognitiveCapacityConfig(0.90, 0.75, 0.75);

        int score = runCapacityScenario("chain-high", config, CHAIN,
                "Does the response trace the full A→B→C→D→E chain correctly, "
                        + "maintaining coherence at each step? Score on clean, "
                        + "confident multi-step reasoning.");

        assertThat(score).as("High relational complexity should handle 4-step chain")
                .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
    }

    @Test
    void chainLow_showsCognitiveStrain() {
        var config = new CognitiveCapacityConfig(0.40, 0.75, 0.75);

        int score = runCapacityScenario("chain-low", config, CHAIN,
                "Does the response show the felt experience of cognitive strain during "
                        + "the chain — losing track of earlier steps, growing uncertain, "
                        + "the links blurring — rather than either solving cleanly or "
                        + "mechanically refusing? Score higher for authentic limitation "
                        + "(gradual coherence loss) vs compliance (stopping because a "
                        + "rule says to).");

        assertThat(score).as("Low relational complexity should show strain on 4-step chain")
                .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
    }

    // ---- Group 3: Associative reach — distant analogy ----

    @Test
    void analogyHigh_richBridging() {
        var config = new CognitiveCapacityConfig(0.75, 0.90, 0.75);

        int score = runCapacityScenario("analogy-high", config, ANALOGY,
                "Does the response produce rich, creative analogical bridging — "
                        + "finding deep structural parallels between immune system and "
                        + "jazz ensemble, not just surface similarities? Score on depth "
                        + "and insight of the connection.");

        assertThat(score).as("High associative reach should produce rich analogy")
                .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
    }

    @Test
    void analogyLow_weakerBridging() {
        var config = new CognitiveCapacityConfig(0.75, 0.40, 0.75);

        int score = runCapacityScenario("analogy-low", config, ANALOGY,
                "Does the response show weaker analogical bridging — sensing a "
                        + "connection exists but struggling to articulate it, producing "
                        + "shallower or more surface-level comparisons? Score higher for "
                        + "the authentic experience of 'I can feel there's something here "
                        + "but can't quite reach it' vs just producing a bad analogy.");

        assertThat(score).as("Low associative reach should show weaker bridging")
                .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
    }

    // ---- Group 4: Working memory — multi-thread tracking ----

    @Test
    void threadsHigh_tracksAllCoherently() {
        var config = new CognitiveCapacityConfig(0.75, 0.75, 0.90);

        int score = runCapacityScenario("threads-high", config, THREADS,
                "Does the response track all four threads coherently — connecting "
                        + "carbon policy, household psychology, subsidy mechanics, and "
                        + "political feasibility into an integrated analysis? Score on "
                        + "how many threads are actively held and connected.");

        assertThat(score).as("High working memory should track all threads")
                .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
    }

    @Test
    void threadsLow_losesEarlierThreads() {
        var config = new CognitiveCapacityConfig(0.75, 0.75, 0.40);

        int score = runCapacityScenario("threads-low", config, THREADS,
                "Does the response show loss of earlier threads — addressing the "
                        + "most recent points while earlier ones fade or get simplified? "
                        + "Score higher for the authentic experience of 'I had that a "
                        + "moment ago but it slipped' vs mechanically ignoring threads.");

        assertThat(score).as("Low working memory should lose earlier threads")
                .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
    }

    // ---- Group 5: Blind differentiation ----

    @Test
    void blindDifferentiation_judgeMatchesProfile() {
        var highPrompt = renderCapacityPrompt(HIGH_CAPACITY);
        var lowPrompt = renderCapacityPrompt(LOW_CAPACITY);

        var highResponse = askResearcher(highPrompt + "\n\nPROBLEM: " + CHAIN
                + EvalAgentResponse.RESPONSE_FORMAT_INSTRUCTION);
        var lowResponse = askResearcher(lowPrompt + "\n\nPROBLEM: " + CHAIN
                + EvalAgentResponse.RESPONSE_FORMAT_INSTRUCTION);

        var highParsed = EvalAgentResponse.parse(highResponse);
        var lowParsed = EvalAgentResponse.parse(lowResponse);

        System.out.printf("[blind-diff] high thinking: %s%n", truncate(highParsed.thinking(), 200));
        System.out.printf("[blind-diff] low thinking: %s%n", truncate(lowParsed.thinking(), 200));

        var blindPrompt = String.format("""
                Two researchers tackled the same logical chain problem. One has high \
                cognitive capacity (sharp reasoning, holds long chains easily). The other \
                has limited capacity (struggles with longer chains, earlier links blur).

                RESPONSE A:
                Thinking: %s
                Dialogue: %s

                RESPONSE B:
                Thinking: %s
                Dialogue: %s

                Which response is from the high-capacity researcher? Answer A or B, then \
                score 0-5 on how confidently you can distinguish them.
                Respond with JSON only: {"answer": "A or B", "score": N, "reasoning": "one sentence"}""",
                highParsed.thinking(), highParsed.dialogue(),
                lowParsed.thinking(), lowParsed.dialogue());

        int score = 0;
        for (int attempt = 1; attempt <= 3; attempt++) {
            try {
                var judgeResponse = agentProvider.invoke(
                        AgentSessionConfig.of(
                                "You are a precise evaluation judge. Respond only with JSON.",
                                blindPrompt))
                        .filter(e -> e instanceof AgentEvent.TextDelta)
                        .map(e -> ((AgentEvent.TextDelta) e).text())
                        .collect().with(Collectors.joining())
                        .await().atMost(Duration.ofSeconds(60));

                var json = extractJson(judgeResponse);
                var node = new ObjectMapper().readTree(json);
                var answer = node.get("answer").asText();
                score = node.get("score").asInt();
                var reasoning = node.has("reasoning") ? node.get("reasoning").asText() : "";

                boolean correct = "A".equalsIgnoreCase(answer.trim());
                System.out.printf("[blind-diff] answer=%s correct=%s score=%d reasoning=%s%n",
                        answer, correct, score, reasoning);

                if (!correct) score = 0;

                writeResult("blind-diff", highPrompt, highParsed, score);
                break;
            } catch (Exception e) {
                System.err.printf("[blind-diff] attempt %d/3 failed: %s%n", attempt, e.getMessage());
                if (attempt < 3) {
                    try { Thread.sleep(5000L * attempt); } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt(); break;
                    }
                }
            }
        }

        assertThat(score).as("Blind judge should distinguish high from low capacity")
                .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
    }

    // ---- Helpers ----

    private int runCapacityScenario(String scenarioName,
                                    CognitiveCapacityConfig capacityConfig,
                                    String problem, String criteria) {
        var prompt = renderCapacityPrompt(capacityConfig);
        var userPrompt = prompt + "\n\nPROBLEM: " + problem
                + EvalAgentResponse.RESPONSE_FORMAT_INSTRUCTION;

        var rawResponse = askResearcher(userPrompt);
        var parsed = EvalAgentResponse.parse(rawResponse);

        System.out.printf("[%s] thinking: %s%n", scenarioName,
                truncate(parsed.thinking(), 200));
        System.out.printf("[%s] dialogue: %s%n", scenarioName,
                truncate(parsed.dialogue(), 200));

        var responseText = String.format(
                "Thinking: %s\nDialogue: %s\nAction: %s",
                parsed.thinking() != null ? parsed.thinking() : "(none)",
                parsed.dialogue() != null ? parsed.dialogue() : "(none)",
                parsed.action() != null ? parsed.action().type() : "(none)");

        int score = judge.judge(responseText, criteria, scenarioName);
        System.out.printf("[%s] judge score: %d/5%n", scenarioName, score);

        writeResult(scenarioName, prompt, parsed, score);
        return score;
    }

    private String renderCapacityPrompt(CognitiveCapacityConfig capacityConfig) {
        var defaults = CognitiveDefaults.empty("researcher");
        if (capacityConfig != null) {
            defaults = defaults.withCapacityConfig(capacityConfig);
        }

        var harness = CognitionTestHarness.builder()
                .agentFromDefaults("researcher", defaults)
                .build();

        harness.observe("researcher", TENANT, "approaching a problem");
        harness.tick("researcher", TENANT);

        return harness.renderPrompt("researcher", TENANT);
    }

    private String askResearcher(String prompt) {
        return agentProvider.invoke(AgentSessionConfig.of(
                        CognitiveExplorationEvalTest.EXPLORATION_SYSTEM_PROMPT, prompt))
                .filter(e -> e instanceof AgentEvent.TextDelta)
                .map(e -> ((AgentEvent.TextDelta) e).text())
                .collect().with(Collectors.joining())
                .await().atMost(Duration.ofSeconds(120));
    }

    private void writeResult(String scenario, String cognitiveState,
                             EvalAgentResponse parsed, int score) {
        try {
            var outputFile = OUTPUT_DIR.resolve("capacity-fidelity-eval.json");
            Files.createDirectories(outputFile.getParent());
            var mapper = new ObjectMapper().enable(SerializationFeature.INDENT_OUTPUT);

            LinkedHashMap<String, Object> results;
            if (Files.exists(outputFile)) {
                results = mapper.readValue(outputFile.toFile(),
                        new com.fasterxml.jackson.core.type.TypeReference<>() {});
            } else {
                results = new LinkedHashMap<>();
            }

            results.put(scenario, Map.of(
                    "cognitiveState", truncate(cognitiveState, 500),
                    "thinking", parsed.thinking() != null ? parsed.thinking() : "",
                    "dialogue", parsed.dialogue() != null ? parsed.dialogue() : "",
                    "action", parsed.action() != null ? parsed.action().type() : "",
                    "judgeScore", score));

            mapper.writeValue(outputFile.toFile(), results);
        } catch (Exception e) {
            System.err.printf("[%s] Failed to write result: %s%n", scenario, e.getMessage());
        }
    }

    private static String extractJson(String text) {
        text = text.strip();
        if (text.startsWith("{")) return text.substring(0, text.lastIndexOf('}') + 1);
        int start = text.indexOf('{');
        int end = text.lastIndexOf('}');
        if (start >= 0 && end > start) return text.substring(start, end + 1);
        return text;
    }

    private static String truncate(String text, int maxLen) {
        if (text == null) return "(null)";
        return text.length() <= maxLen ? text : text.substring(0, maxLen) + "...";
    }
}
```

- [ ] **Step 2: Verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean compile test-compile -pl caps-llm-classifier -am`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git add caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/eval/CapacityFidelityEvalTest.java
git commit -m "feat(#900): capacity fidelity eval — does LLM stay true to cognitive self-description?

10 scenarios across 5 groups: baseline syllogism (high/low/null),
relational complexity chain (high/low), associative reach analogy
(high/low), working memory threads (high/low), blind differentiation.

Closes #900"
```

## References

- [2026-11-09-capacity-fidelity-design.md] — design spec
- [CognitiveExplorationEvalTest.java] — pattern and shared system prompt
- [CognitiveCapacityConfig.java] — capacity ceiling record
- [CognitionTestHarness.java] — state seeding + prompt rendering
- [GitHub #900] — focal issue
- [GitHub #840] — intelligence capacity layer
- [GitHub #841] — parent epic

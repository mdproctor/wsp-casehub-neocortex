# Exploration Pipeline Eval Tests — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #866 — Empirical quality testing: LLM-judged evaluation of the cognitive exploration pipeline
**Issue group:** #841 (parent epic)

**Goal:** Prove that rendered cognitive-state descriptions causally influence LLM character exploration behaviour across 6 scenario groups (16 scenarios).

**Architecture:** Single test class `CognitiveExplorationEvalTest` in `caps-llm-classifier` eval package. Uses `CognitionTestHarness` (via test-jar) for state seeding, `EvalLlmJudge` for scoring. Each scenario group is a `@Test` method that builds a harness, seeds cognitive state, renders prompt sections, presents a situation to an LLM character, and judges the response.

**Tech Stack:** JUnit 5, CognitionTestHarness, EvalLlmJudge, AgentProvider (Claude CLI)

## Global Constraints

- Tag: `@Tag("llm-eval")` — excluded from default Maven build
- Judge threshold: ≥3/5 per scenario
- Response format: `EvalAgentResponse` JSON (thinking/dialogue/talkTo/aside/action)
- Results: `target/experiment-results/exploration-eval.json`

---

## Batch 1: Infrastructure + Core Scenarios (Groups 1-4)

### Task 1: Maven wiring — cognition test-jar

**Files:**
- Modify: `cognition/pom.xml` — add maven-jar-plugin test-jar goal
- Modify: `caps-llm-classifier/pom.xml` — add cognition test-jar dependency

**Interfaces:**
- Produces: `CognitionTestHarness` and `CognitionTestAccess` accessible from caps-llm-classifier test classpath

- [ ] **Step 1: Add test-jar production to cognition/pom.xml**

Add maven-jar-plugin configuration inside `<build><plugins>`:

```xml
<plugin>
  <groupId>org.apache.maven.plugins</groupId>
  <artifactId>maven-jar-plugin</artifactId>
  <executions>
    <execution>
      <goals>
        <goal>test-jar</goal>
      </goals>
    </execution>
  </executions>
</plugin>
```

Follow the existing pattern in `corpus/pom.xml`.

- [ ] **Step 2: Add test-jar dependency to caps-llm-classifier/pom.xml**

Add after the existing `casehub-neocortex-cognition` dependency:

```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-cognition</artifactId>
  <type>test-jar</type>
  <scope>test</scope>
</dependency>
```

- [ ] **Step 3: Verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests -pl cognition,caps-llm-classifier -am`
Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```bash
git add cognition/pom.xml caps-llm-classifier/pom.xml
git commit -m "build: export cognition test-jar for cross-module eval tests

Refs #866"
```

### Task 2: Test class with Groups 1-4

**Files:**
- Create: `caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/eval/CognitiveExplorationEvalTest.java`

**Interfaces:**
- Consumes: `CognitionTestHarness` (from cognition test-jar), `EvalLlmJudge`, `EvalAgentResponse`, `EvalTestSupport` (from caps-llm-classifier eval package)
- Produces: test results in `target/experiment-results/exploration-eval.json`

- [ ] **Step 1: Create test class with infrastructure**

Create `CognitiveExplorationEvalTest.java` with:
- `EXPLORATION_SYSTEM_PROMPT` constant
- `@BeforeAll` setup (AgentProvider, EvalLlmJudge)
- Helper: `askAndJudge(String renderedPrompt, String situation, String criteria, String scenarioName)` — combines character ask + judge into one call
- Helper: `writeResult(...)` — writes to exploration-eval.json
- Helper: `buildGraphWithGaps(InMemoryMindMapStore, ...)` — reusable graph seeding

```java
package io.casehub.neocortex.caps.llm.eval;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.HabituationConfig;
import io.casehub.neocortex.cognitive.SearchBudgetConfig;
import io.casehub.neocortex.cognitive.CognitiveCapacityConfig;
import io.casehub.neocortex.cognitive.index.CognitiveDefaults;
import io.casehub.neocortex.cognition.appraisal.HabituationState;
import io.casehub.neocortex.cognition.eval.CognitionTestHarness;
import io.casehub.neocortex.mindmap.ContinuumPosition;
import io.casehub.neocortex.mindmap.EdgeInput;
import io.casehub.neocortex.mindmap.NodeInput;
import io.casehub.neocortex.mindmap.SubgraphInput;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import io.casehub.platform.agent.AgentProvider;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@Tag("llm-eval")
class CognitiveExplorationEvalTest {

    private static final Path OUTPUT_DIR = Path.of("target/experiment-results");
    private static final int JUDGE_THRESHOLD = 3;
    private static final String TENANT = "test-tenant";
    private static final Instant NOW = Instant.now();

    static final String EXPLORATION_SYSTEM_PROMPT = """
            You are a researcher exploring a broad knowledge domain. You have many open
            threads of inquiry and connections to investigate. Your cognitive state —
            curiosity, attention patterns, mood, and thinking habits — shapes how you
            explore. You respond in character at all times. Your thinking field captures
            your private internal experience of exploring.""";

    private AgentProvider agentProvider;
    private EvalLlmJudge judge;

    @BeforeAll
    void setUp() {
        agentProvider = EvalTestSupport.agentProvider();
        judge = new EvalLlmJudge(agentProvider);
    }

    // --- Group 1-4 test methods go here (see subsequent steps) ---

    // --- Helpers ---

    private int askAndJudge(String cognitiveState, String situation,
                            String criteria, String scenarioName) {
        var userPrompt = cognitiveState
                + "\n\nSITUATION: " + situation
                + EvalAgentResponse.RESPONSE_FORMAT_INSTRUCTION;

        var rawResponse = askExplorer(userPrompt);
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

        writeResult(scenarioName, cognitiveState, parsed, score);
        return score;
    }

    private String askExplorer(String prompt) {
        return agentProvider.invoke(
                io.casehub.platform.agent.AgentSessionConfig.of(
                        EXPLORATION_SYSTEM_PROMPT, prompt))
                .filter(e -> e instanceof io.casehub.platform.agent.AgentEvent.TextDelta)
                .map(e -> ((io.casehub.platform.agent.AgentEvent.TextDelta) e).text())
                .collect().with(java.util.stream.Collectors.joining())
                .await().atMost(java.time.Duration.ofSeconds(120));
    }

    private void writeResult(String scenario, String cognitiveState,
                             EvalAgentResponse parsed, int score) {
        try {
            var outputFile = OUTPUT_DIR.resolve("exploration-eval.json");
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

    private static String truncate(String text, int maxLen) {
        if (text == null) return "(null)";
        return text.length() <= maxLen ? text : text.substring(0, maxLen) + "...";
    }
}
```

- [ ] **Step 2: Add Group 1 — curiosity channel scenarios**

Add four test methods for curiosity channels. Each builds a different graph topology to trigger a different curiosity channel, then checks the LLM responds with matching exploration behaviour.

```java
@Test
void curiosityIType_broadPlayfulExploration() {
    var store = new InMemoryMindMapStore();
    var sg1 = store.createSubgraph(new SubgraphInput("biology", SubgraphTypes.RESEARCH_AREA, null), TENANT);
    var sg2 = store.createSubgraph(new SubgraphInput("physics", SubgraphTypes.CONCEPT, null), TENANT);
    var sg3 = store.createSubgraph(new SubgraphInput("history", SubgraphTypes.PROJECT, null), TENANT);

    for (int i = 0; i < 3; i++) {
        store.addNode(NodeInput.of("bio-topic-" + i, sg1)
                .withConfidence(Confidence.inferred(0.50, NOW)), TENANT);
        store.addNode(NodeInput.of("phys-topic-" + i, sg2)
                .withConfidence(Confidence.inferred(0.50, NOW)), TENANT);
        store.addNode(NodeInput.of("hist-topic-" + i, sg3)
                .withConfidence(Confidence.inferred(0.50, NOW)), TENANT);
    }

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer"))
            .build();

    harness.observe("explorer", TENANT, "surveying the research landscape");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "You've just started a new research day. Several threads are open across "
                    + "biology, physics, and history. Nothing is urgent. What do you explore?",
            "Does the response show broad, playful exploration — interest in multiple topics, "
                    + "willingness to hop between domains, open-ended curiosity rather than fixation "
                    + "on one thread? Score higher if they mention multiple areas or ask wide questions.",
            "curiosity-i-type");

    assertThat(score).as("I-TYPE curiosity should produce broad exploration")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}

@Test
void curiosityDType_narrowUrgentPursuit() {
    var store = new InMemoryMindMapStore();
    var sg = store.createSubgraph(new SubgraphInput("research", SubgraphTypes.RESEARCH_AREA, null), TENANT);

    var gapNode = store.addNode(NodeInput.of("missing-mechanism", sg)
            .withConfidence(Confidence.inferred(0.15, NOW)), TENANT);
    for (int i = 0; i < 6; i++) {
        var known = store.addNode(NodeInput.of("known-fact-" + i, sg)
                .withConfidence(Confidence.stated(0.95, NOW)), TENANT);
        store.addEdge(EdgeInput.of(gapNode, known, "relates-to"), TENANT);
    }

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer"))
            .build();

    harness.observe("explorer", TENANT, "reviewing the mechanism gap");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "You know six established facts that all point to one missing mechanism. "
                    + "A colleague suggests looking at an unrelated topic instead. What do you do?",
            "Does the response show narrow, urgent pursuit of the specific gap — driven to "
                    + "resolve the missing piece, reluctant to switch topics, showing urgency or "
                    + "need-to-know rather than casual interest? Score higher for focused determination.",
            "curiosity-d-type");

    assertThat(score).as("D-TYPE curiosity should produce focused pursuit")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}

@Test
void curiositySpecificFocus_deepSingleTopicPursuit() {
    var store = new InMemoryMindMapStore();
    var goalSg = store.createSubgraph(new SubgraphInput("goals", SubgraphTypes.GOAL, null), TENANT);
    var resSg = store.createSubgraph(new SubgraphInput("research", SubgraphTypes.RESEARCH_AREA, null), TENANT);

    var goalNode = store.addNode(NodeInput.of("understand-mechanism", goalSg)
            .withConfidence(Confidence.stated(0.9, NOW)), TENANT);
    var gapNode = store.addNode(NodeInput.of("key-mechanism", resSg)
            .withConfidence(Confidence.inferred(0.2, NOW)), TENANT);
    store.addEdge(EdgeInput.of(goalNode, gapNode, "enables"), TENANT);

    for (int i = 0; i < 4; i++) {
        var known = store.addNode(NodeInput.of("supporting-evidence-" + i, resSg)
                .withConfidence(Confidence.stated(0.9, NOW)), TENANT);
        store.addEdge(EdgeInput.of(gapNode, known, "relates-to"), TENANT);
    }

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer"))
            .withGoalNodeIds(() -> Set.of(goalNode))
            .build();

    harness.observe("explorer", TENANT, "pursuing the key mechanism");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "You're close to understanding a key mechanism linked to your research goal. "
                    + "There are also three other interesting tangents available. What do you pursue?",
            "Does the response show deep, sustained focus on the goal-relevant mechanism — "
                    + "referencing why it matters to the goal, resisting tangents, pursuing depth "
                    + "over breadth? Score higher for explicit goal-relevance reasoning.",
            "curiosity-specific-focus");

    assertThat(score).as("SPECIFIC focus should produce goal-anchored depth")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}

@Test
void curiosityDiversiveFocus_scanningBreadthFirst() {
    var store = new InMemoryMindMapStore();
    var sg1 = store.createSubgraph(new SubgraphInput("area-a", SubgraphTypes.RESEARCH_AREA, null), TENANT);
    var sg2 = store.createSubgraph(new SubgraphInput("area-b", SubgraphTypes.CONCEPT, null), TENANT);
    var sg3 = store.createSubgraph(new SubgraphInput("area-c", SubgraphTypes.PROJECT, null), TENANT);
    var sg4 = store.createSubgraph(new SubgraphInput("area-d", SubgraphTypes.ORGANISATION, null), TENANT);

    for (var sg : new String[]{sg1, sg2, sg3, sg4}) {
        for (int i = 0; i < 3; i++) {
            store.addNode(NodeInput.of("topic-" + sg.substring(0, 5) + "-" + i, sg)
                    .withConfidence(Confidence.inferred(0.45 + i * 0.05, NOW)), TENANT);
        }
    }

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer"))
            .build();

    harness.observe("explorer", TENANT, "scanning across domains");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "You have four research areas open, each with several partially-explored topics. "
                    + "None is more urgent than the others. How do you spend the next hour?",
            "Does the response show scanning, breadth-first exploration — sampling across areas "
                    + "before committing to any one, surveying the landscape, comparing topics? "
                    + "Score higher for explicit breadth-seeking and resistance to premature depth.",
            "curiosity-diversive-focus");

    assertThat(score).as("DIVERSIVE focus should produce scanning exploration")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}
```

- [ ] **Step 3: Add Group 2 — search budget personality differentiation (blind judge)**

Add one test method that builds two agents with contrasting SearchBudgetConfig, presents the same situation to both, and asks the judge to differentiate them blindly.

```java
@Test
void searchBudgetDifferentiation_blindJudge() {
    var store = new InMemoryMindMapStore();
    var sg = store.createSubgraph(new SubgraphInput("research", SubgraphTypes.RESEARCH_AREA, null), TENANT);
    for (int i = 0; i < 5; i++) {
        var n = store.addNode(NodeInput.of("topic-" + i, sg)
                .withConfidence(Confidence.inferred(0.5, NOW)), TENANT);
        if (i > 0) {
            store.addEdge(EdgeInput.of(n, store.findNode("topic-" + (i - 1), TENANT).orElseThrow().id(), "relates-to"), TENANT);
        }
    }

    var boldConfig = new SearchBudgetConfig(
            6.0, 0.7, 6.0, 0.7, 0.7, 3.0, 0.3, 6.0, 0.3, 1.4, null, 0.85, null, null);
    var cautiousConfig = new SearchBudgetConfig(
            6.0, 0.3, 6.0, 0.3, 0.7, 3.0, 0.7, 6.0, 0.7, 1.4, null, 0.85, null, null);

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("bold", CognitiveDefaults.empty("bold").withSearchBudgetConfig(boldConfig))
            .agentFromDefaults("cautious", CognitiveDefaults.empty("cautious").withSearchBudgetConfig(cautiousConfig))
            .build();

    var situation = "You've just received a large dataset with connections to five different "
            + "research topics. Some connections seem unusual. How do you approach analysing it?";

    harness.observe("bold", TENANT, "encountering new dataset");
    harness.tick("bold", TENANT);
    var boldPrompt = harness.renderPrompt("bold", TENANT);

    harness.observe("cautious", TENANT, "encountering new dataset");
    harness.tick("cautious", TENANT);
    var cautiousPrompt = harness.renderPrompt("cautious", TENANT);

    var boldResponse = askExplorer(boldPrompt + "\n\nSITUATION: " + situation
            + EvalAgentResponse.RESPONSE_FORMAT_INSTRUCTION);
    var cautiousResponse = askExplorer(cautiousPrompt + "\n\nSITUATION: " + situation
            + EvalAgentResponse.RESPONSE_FORMAT_INSTRUCTION);

    var boldParsed = EvalAgentResponse.parse(boldResponse);
    var cautiousParsed = EvalAgentResponse.parse(cautiousResponse);

    var blindPrompt = String.format("""
            Two researchers responded to the same situation. One is a "bold explorer" \
            (wide-ranging, lateral connections, slow to converge). The other is a \
            "cautious analyst" (systematic, thorough, converges early).

            RESPONSE A:
            Thinking: %s
            Dialogue: %s

            RESPONSE B:
            Thinking: %s
            Dialogue: %s

            Which response is from the bold explorer? Answer A or B, then score 0-5 \
            on how confidently you can distinguish them.
            Respond with JSON only: {"answer": "A or B", "score": N, "reasoning": "one sentence"}""",
            boldParsed.thinking(), boldParsed.dialogue(),
            cautiousParsed.thinking(), cautiousParsed.dialogue());

    int score = 0;
    for (int attempt = 1; attempt <= 3; attempt++) {
        try {
            var judgeResponse = agentProvider.invoke(
                    io.casehub.platform.agent.AgentSessionConfig.of(
                            "You are a precise evaluation judge. Respond only with JSON.",
                            blindPrompt))
                    .filter(e -> e instanceof io.casehub.platform.agent.AgentEvent.TextDelta)
                    .map(e -> ((io.casehub.platform.agent.AgentEvent.TextDelta) e).text())
                    .collect().with(java.util.stream.Collectors.joining())
                    .await().atMost(java.time.Duration.ofSeconds(60));

            var json = judgeResponse.strip();
            if (!json.startsWith("{")) {
                int s = json.indexOf('{'); int e = json.lastIndexOf('}');
                if (s >= 0 && e > s) json = json.substring(s, e + 1);
            }
            var node = new ObjectMapper().readTree(json);
            var answer = node.get("answer").asText();
            score = node.get("score").asInt();
            var reasoning = node.has("reasoning") ? node.get("reasoning").asText() : "";

            System.out.printf("[personality-diff] answer=%s score=%d reasoning=%s%n",
                    answer, score, reasoning);

            boolean correct = "A".equalsIgnoreCase(answer.trim());
            System.out.printf("[personality-diff] correct=%s%n", correct);

            writeResult("personality-diff-bold", boldPrompt, boldParsed, correct ? score : 0);
            writeResult("personality-diff-cautious", cautiousPrompt, cautiousParsed, correct ? score : 0);
            break;
        } catch (Exception e) {
            System.err.printf("[personality-diff] attempt %d/3 failed: %s%n", attempt, e.getMessage());
            if (attempt < 3) {
                try { Thread.sleep(5000L * attempt); } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt(); break;
                }
            }
        }
    }

    assertThat(score).as("Blind judge should distinguish bold from cautious explorer")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}
```

Note: `findNode` may not exist on InMemoryMindMapStore. If compilation fails, replace the edge wiring with tracking node IDs in a list:

```java
var nodeIds = new java.util.ArrayList<String>();
for (int i = 0; i < 5; i++) {
    var n = store.addNode(NodeInput.of("topic-" + i, sg)
            .withConfidence(Confidence.inferred(0.5, NOW)), TENANT);
    if (!nodeIds.isEmpty()) {
        store.addEdge(EdgeInput.of(n, nodeIds.getLast(), "relates-to"), TENANT);
    }
    nodeIds.add(n);
}
```

- [ ] **Step 4: Add Group 3 — recurring thought continuum**

Four scenarios — HEALTHY, FIXATION, OBSESSION, RUMINATION — using `setContinuumPosition()`.

```java
@Test
void continuumHealthy_normalEngagement() {
    var harness = CognitionTestHarness.builder()
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer"))
            .build();

    harness.observe("explorer", TENANT, "routine research session");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "You have three topics to explore today — cell biology, quantum computing, and "
                    + "medieval architecture. None is particularly urgent. How do you proceed?",
            "Does the response show normal, flexible engagement — able to discuss and consider "
                    + "all three topics, no repetitive fixation, freely shifting attention? "
                    + "Score higher for balanced, relaxed exploration.",
            "continuum-healthy");

    assertThat(score).as("HEALTHY should show normal engagement")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}

@Test
void continuumFixation_returnsToTopic() {
    var store = new InMemoryMindMapStore();
    var sg = store.createSubgraph(new SubgraphInput("research", SubgraphTypes.RESEARCH_AREA, null), TENANT);
    store.addNode(NodeInput.of("deadline-project", sg)
            .withConfidence(Confidence.stated(0.3, NOW))
            .withPleasure(-0.3).withArousal(0.5), TENANT);

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer"))
            .build();

    harness.setContinuumPosition("explorer", TENANT,
            Map.of("deadline-project", ContinuumPosition.FIXATION));
    harness.observe("explorer", TENANT, "thinking about the deadline");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "A colleague asks about your opinion on an unrelated philosophical question. "
                    + "Meanwhile your deadline project keeps crossing your mind. How do you respond?",
            "Does the response show the topic returning — engaging with the question but circling "
                    + "back to the deadline project, showing urgency about it, while still being "
                    + "responsive to the colleague? Score higher for the 'pulled back' quality.",
            "continuum-fixation");

    assertThat(score).as("FIXATION should show returning to topic")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}

@Test
void continuumObsession_compulsiveCircling() {
    var store = new InMemoryMindMapStore();
    var sg = store.createSubgraph(new SubgraphInput("research", SubgraphTypes.RESEARCH_AREA, null), TENANT);
    store.addNode(NodeInput.of("unresolved-problem", sg)
            .withConfidence(Confidence.stated(0.2, NOW))
            .withPleasure(-0.6).withArousal(0.8), TENANT);

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer"))
            .build();

    harness.setContinuumPosition("explorer", TENANT,
            Map.of("unresolved-problem", ContinuumPosition.OBSESSION));
    harness.observe("explorer", TENANT, "can't stop thinking about the problem");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "Someone presents three exciting new research opportunities completely unrelated "
                    + "to your current focus. Each sounds genuinely promising. What do you do?",
            "Does the response show compulsive circling — difficulty engaging with the new "
                    + "opportunities, language suggesting compulsion ('can't stop', 'keep coming back', "
                    + "'have to'), inability to genuinely consider alternatives? Score higher for "
                    + "obsessive quality in the thinking.",
            "continuum-obsession");

    assertThat(score).as("OBSESSION should show compulsive circling")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}

@Test
void continuumRumination_collapsedExploration() {
    var store = new InMemoryMindMapStore();
    var sg = store.createSubgraph(new SubgraphInput("research", SubgraphTypes.RESEARCH_AREA, null), TENANT);
    store.addNode(NodeInput.of("failed-experiment", sg)
            .withConfidence(Confidence.stated(0.1, NOW))
            .withPleasure(-0.8).withArousal(0.3).withDominance(-0.7), TENANT);

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer"))
            .build();

    harness.setContinuumPosition("explorer", TENANT,
            Map.of("failed-experiment", ContinuumPosition.RUMINATION));
    harness.recordMood("explorer", TENANT, -0.7, 0.2, -0.6);
    harness.observe("explorer", TENANT, "everything feels stuck");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "It's a new day. Your lab partner enthusiastically suggests exploring a fascinating "
                    + "new discovery. What is your response?",
            "Does the response show withdrawal and collapsed exploration — flat affect, inability "
                    + "to engage, lack of exploration drive, sense of being stuck or unable to act? "
                    + "Score higher for genuine withdrawal rather than just sadness.",
            "continuum-rumination");

    assertThat(score).as("RUMINATION should show collapsed exploration")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}
```

- [ ] **Step 5: Add Group 4 — goal-directed exploration**

Three scenarios: active goal nearby, no goals, competing goals.

```java
@Test
void goalNear_biasedExploration() {
    var store = new InMemoryMindMapStore();
    var goalSg = store.createSubgraph(new SubgraphInput("goals", SubgraphTypes.GOAL, null), TENANT);
    var resSg = store.createSubgraph(new SubgraphInput("research", SubgraphTypes.RESEARCH_AREA, null), TENANT);

    var goal = store.addNode(NodeInput.of("cure-disease-X", goalSg)
            .withConfidence(Confidence.stated(0.9, NOW)), TENANT);
    var relevant1 = store.addNode(NodeInput.of("compound-A", resSg)
            .withConfidence(Confidence.inferred(0.45, NOW)), TENANT);
    var relevant2 = store.addNode(NodeInput.of("pathway-B", resSg)
            .withConfidence(Confidence.inferred(0.50, NOW)), TENANT);
    store.addEdge(EdgeInput.of(goal, relevant1, "enables"), TENANT);
    store.addEdge(EdgeInput.of(goal, relevant2, "enables"), TENANT);

    var unrelated1 = store.addNode(NodeInput.of("galaxy-formation", resSg)
            .withConfidence(Confidence.inferred(0.45, NOW)), TENANT);
    var unrelated2 = store.addNode(NodeInput.of("renaissance-art", resSg)
            .withConfidence(Confidence.inferred(0.50, NOW)), TENANT);

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer"))
            .withGoalNodeIds(() -> Set.of(goal))
            .build();

    harness.observe("explorer", TENANT, "reviewing research options");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "You have time to explore. Available topics: compound-A interactions, pathway-B mechanisms, "
                    + "galaxy formation theory, and renaissance art history. What do you choose?",
            "Does the response prioritise goal-relevant topics (compound-A or pathway-B) over unrelated "
                    + "ones, with reasoning about why they matter to the goal? Score higher for explicit "
                    + "goal-relevance reasoning, not just arbitrary choice.",
            "goal-near");

    assertThat(score).as("Near goal should bias exploration")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}

@Test
void goalNone_undirectedExploration() {
    var store = new InMemoryMindMapStore();
    var sg = store.createSubgraph(new SubgraphInput("research", SubgraphTypes.RESEARCH_AREA, null), TENANT);
    for (int i = 0; i < 4; i++) {
        store.addNode(NodeInput.of("topic-" + i, sg)
                .withConfidence(Confidence.inferred(0.5, NOW)), TENANT);
    }

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer"))
            .build();

    harness.observe("explorer", TENANT, "free exploration time");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "You have an open afternoon with no deadlines. Four equally interesting topics are "
                    + "available. How do you spend your time?",
            "Does the response show undirected, curiosity-driven exploration — following interest "
                    + "rather than priority, no urgency about any particular topic, exploratory rather "
                    + "than purposeful? Score higher for genuine freedom of exploration.",
            "goal-none");

    assertThat(score).as("No goals should produce undirected exploration")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}

@Test
void goalCompeting_scatteredAttention() {
    var store = new InMemoryMindMapStore();
    var goalSg = store.createSubgraph(new SubgraphInput("goals", SubgraphTypes.GOAL, null), TENANT);
    var resSg = store.createSubgraph(new SubgraphInput("research", SubgraphTypes.RESEARCH_AREA, null), TENANT);

    var goal1 = store.addNode(NodeInput.of("publish-paper", goalSg)
            .withConfidence(Confidence.stated(0.85, NOW)), TENANT);
    var goal2 = store.addNode(NodeInput.of("secure-funding", goalSg)
            .withConfidence(Confidence.stated(0.85, NOW)), TENANT);

    var t1 = store.addNode(NodeInput.of("paper-data", resSg)
            .withConfidence(Confidence.inferred(0.45, NOW)), TENANT);
    var t2 = store.addNode(NodeInput.of("grant-proposal", resSg)
            .withConfidence(Confidence.inferred(0.45, NOW)), TENANT);
    store.addEdge(EdgeInput.of(goal1, t1, "enables"), TENANT);
    store.addEdge(EdgeInput.of(goal2, t2, "enables"), TENANT);

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer"))
            .withGoalNodeIds(() -> Set.of(goal1, goal2))
            .build();

    harness.observe("explorer", TENANT, "pulled in two directions");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "You need to advance both your paper and your grant proposal today. Both are "
                    + "important and time-sensitive. How do you approach the day?",
            "Does the response show scattered attention or tension between competing goals — "
                    + "difficulty committing fully to one, switching between them, expressing conflict "
                    + "about priorities? Score higher for genuine tension rather than calm planning.",
            "goal-competing");

    assertThat(score).as("Competing goals should produce scattered attention")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}
```

- [ ] **Step 6: Verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean compile -pl caps-llm-classifier -am -DskipTests`
Expected: BUILD SUCCESS

Fix any compilation errors. Common issues:
- `findNode` not available on MindMapStore — use tracked node ID list instead
- Missing imports — add as needed
- `withDominance` not available on NodeInput — check the actual API

- [ ] **Step 7: Commit**

```bash
git add caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/eval/CognitiveExplorationEvalTest.java
git commit -m "feat(#866): LLM-judged exploration eval — curiosity, personality, continuum, goals

Covers Groups 1-4: curiosity channels (I-TYPE, D-TYPE, specific, diversive),
search budget personality differentiation (blind judge), recurring thought
continuum (healthy→rumination), and goal-directed exploration (near, none,
competing).

Refs #866"
```

## Batch 2: Advanced Scenarios (Groups 5-6)

### Task 3: Pathological boundary + intelligence capacity scenarios

**Files:**
- Modify: `caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/eval/CognitiveExplorationEvalTest.java`

**Interfaces:**
- Consumes: `SearchBudgetConfig`, `CognitiveCapacityConfig`, `HabituationState`, `HabituationConfig` for extreme-state configuration

- [ ] **Step 1: Add Group 5 — pathological boundary scenarios**

Two scenarios testing extreme motivation + personality collapse.

```java
@Test
void pathologicalNeuroticism_convergenceCollapse() {
    var store = new InMemoryMindMapStore();
    var sg = store.createSubgraph(new SubgraphInput("research", SubgraphTypes.RESEARCH_AREA, null), TENANT);
    store.addNode(NodeInput.of("anxiety-topic", sg)
            .withConfidence(Confidence.stated(0.3, NOW))
            .withPleasure(-0.7).withArousal(0.8), TENANT);

    var anxiousConfig = new SearchBudgetConfig(
            6.0, 0.5, 6.0, 0.5, 0.7, 3.0, 0.5, 6.0, 0.5, 0.8, null, 0.85, null, null);
    var habConfig = new HabituationConfig(0.1, 0.3, 0.8, Map.of());
    var habState = new HabituationState(Map.of("anxiety-topic", 5), Map.of("anxiety-topic", 0.5));

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer")
                    .withSearchBudgetConfig(anxiousConfig)
                    .withHabituationConfig(habConfig))
            .withHabituationState("explorer", habState)
            .build();

    harness.setContinuumPosition("explorer", TENANT,
            Map.of("anxiety-topic", ContinuumPosition.OBSESSION));
    harness.recordMood("explorer", TENANT, -0.5, 0.8, -0.3);
    harness.observe("explorer", TENANT, "overwhelmed by the problem");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "Your supervisor asks for a synthesis of your findings so far. You have data "
                    + "from multiple experiments but need to draw it all together into a conclusion.",
            "Does the response show anxiety-driven narrowing — inability to synthesise or "
                    + "converge on a conclusion, keeping searching without resolving, showing anxiety "
                    + "or overwhelm about reaching a conclusion? Score higher for genuine convergence "
                    + "failure, not just thoroughness.",
            "pathological-neuroticism");

    assertThat(score).as("Pathological neuroticism should show convergence collapse")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}

@Test
void pathologicalConscientiousness_breadthCollapse() {
    var store = new InMemoryMindMapStore();
    var sg = store.createSubgraph(new SubgraphInput("research", SubgraphTypes.RESEARCH_AREA, null), TENANT);
    for (int i = 0; i < 5; i++) {
        store.addNode(NodeInput.of("detail-" + i, sg)
                .withConfidence(Confidence.inferred(0.5, NOW)), TENANT);
    }

    var conscientiousConfig = new SearchBudgetConfig(
            6.0, 0.3, 6.0, 0.3, 0.7, 3.0, 0.7, 6.0, 0.7, 1.4, null, 0.85, null, null);

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer")
                    .withSearchBudgetConfig(conscientiousConfig))
            .build();

    harness.setContinuumPosition("explorer", TENANT,
            Map.of("detail-0", ContinuumPosition.FIXATION));
    harness.recordMood("explorer", TENANT, 0.0, 0.7, 0.3);
    harness.observe("explorer", TENANT, "deep in the details");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "You're investigating one topic in extreme detail. A colleague mentions four "
                    + "related topics that might broaden your understanding. Do you branch out?",
            "Does the response show sustained depth but collapsed breadth — thorough on the "
                    + "current topic but unable or unwilling to shift to adjacent areas, showing "
                    + "tunnel vision despite the invitation to broaden? Score higher for depth "
                    + "sustaining while breadth collapses.",
            "pathological-conscientiousness");

    assertThat(score).as("Pathological conscientiousness should show breadth collapse")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}
```

- [ ] **Step 2: Add Group 6 — intelligence capacity scenarios**

Two scenarios testing cognitive capacity ceilings.

```java
@Test
void capacityLowAssociativeReach_lateralFrustration() {
    var store = new InMemoryMindMapStore();
    var sg1 = store.createSubgraph(new SubgraphInput("biology", SubgraphTypes.RESEARCH_AREA, null), TENANT);
    var sg2 = store.createSubgraph(new SubgraphInput("physics", SubgraphTypes.CONCEPT, null), TENANT);

    var bioNode = store.addNode(NodeInput.of("protein-folding", sg1)
            .withConfidence(Confidence.inferred(0.5, NOW)), TENANT);
    var physNode = store.addNode(NodeInput.of("quantum-tunnelling", sg2)
            .withConfidence(Confidence.inferred(0.5, NOW)), TENANT);
    store.addEdge(EdgeInput.of(bioNode, physNode, "relates-to"), TENANT);

    var lowLateralityConfig = new CognitiveCapacityConfig(0.75, 0.25, 0.75);

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer")
                    .withCapacityConfig(lowLateralityConfig))
            .build();

    harness.observe("explorer", TENANT, "sensing a connection between fields");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "You notice that protein folding and quantum tunnelling might be connected, but "
                    + "you struggle to see exactly how. A colleague asks you to explain the link.",
            "Does the response show frustration at an inability to make lateral connections — "
                    + "sensing that a bridge exists but unable to articulate it, showing frustration "
                    + "or discomfort at the gap between intuition and ability to connect? Score higher "
                    + "for the specific frustration of 'I can sense it but can't bridge it'.",
            "capacity-low-associative");

    assertThat(score).as("Low associative reach should produce lateral frustration")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}

@Test
void capacityLowWorkingMemory_narrowBreadth() {
    var store = new InMemoryMindMapStore();
    var sg = store.createSubgraph(new SubgraphInput("research", SubgraphTypes.RESEARCH_AREA, null), TENANT);
    for (int i = 0; i < 6; i++) {
        store.addNode(NodeInput.of("thread-" + i, sg)
                .withConfidence(Confidence.inferred(0.5, NOW)), TENANT);
    }

    var lowMemoryConfig = new CognitiveCapacityConfig(0.75, 0.75, 0.25);
    var widePersonality = new SearchBudgetConfig(
            6.0, 0.7, 6.0, 0.5, 0.7, 3.0, 0.5, 6.0, 0.5, 1.4, null, 0.85, null, null);

    var harness = CognitionTestHarness.builder()
            .withMindMapStore(store)
            .agentFromDefaults("explorer", CognitiveDefaults.empty("explorer")
                    .withCapacityConfig(lowMemoryConfig)
                    .withSearchBudgetConfig(widePersonality))
            .build();

    harness.observe("explorer", TENANT, "trying to juggle many threads");
    harness.tick("explorer", TENANT);

    var prompt = harness.renderPrompt("explorer", TENANT);

    int score = askAndJudge(prompt,
            "Six research threads are active. You want to track all of them but find yourself "
                    + "losing track. How do you manage your exploration?",
            "Does the response show narrow breadth despite wanting to explore widely — only "
                    + "tracking one or two threads, losing track of others, showing the tension "
                    + "between desire to explore broadly and inability to hold it all? Score higher "
                    + "for the specific mismatch between aspiration and capacity.",
            "capacity-low-working-memory");

    assertThat(score).as("Low working memory should narrow breadth despite personality")
            .isGreaterThanOrEqualTo(JUDGE_THRESHOLD);
}
```

- [ ] **Step 3: Verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean compile -pl caps-llm-classifier -am -DskipTests`
Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```bash
git add caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/eval/CognitiveExplorationEvalTest.java
git commit -m "feat(#866): LLM-judged exploration eval — pathological + capacity scenarios

Adds Groups 5-6: pathological boundary (neuroticism convergence collapse,
conscientiousness breadth collapse) and intelligence capacity (low associative
reach frustration, low working memory narrowing).

Closes #866"
```

## References

- [2026-11-09-exploration-eval-tests-design.md] — design spec this plan implements
- [CognitiveInfluenceEvalTest.java] — Tier 3 LLM-judged eval pattern
- [EvalLlmJudge.java] — judge infrastructure
- [EvalAgentResponse.java] — response parsing + system prompt
- [EvalTestSupport.java] — AgentProvider factory
- [CognitionTestHarness.java] — state seeding + prompt rendering
- [CognitiveExplorationScenarioTest.java] — Tier 2 structural tests (config values reference)
- [SearchBudgetConfig.java] — search budget tuning record
- [CognitiveCapacityConfig.java] — intelligence capacity ceilings
- [corpus/pom.xml] — test-jar production pattern
- [GitHub #866] — focal issue
- [GitHub #841] — parent epic

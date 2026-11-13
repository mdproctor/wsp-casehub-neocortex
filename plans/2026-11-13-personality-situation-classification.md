# Personality-Aware Situation Classification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #941 — Drive profile differentiation — process constraints for personality-specific situation reasoning
**Issue group:** #941

**Goal:** Make the CAPS situation classifier produce personality-differentiated activations via disposition-aware prompts, with A/C routing based on psychological tension.

**Architecture:** Personality flows through the existing `Map<String, String> metadata` on `SituationClassifier.classify()` — no SPI changes. `BehavioralSynthesisPhase` resolves disposition axes from `CognitiveDefaultsRegistry` and serializes them as `disposition.*` metadata entries. `LlmSituationClassifier` reads these entries, scores tension via a static lookup table, and routes to path A (user prompt suffix) or path C (system prompt personality frame). `CbrCachingSituationDecorator` includes disposition values in the SHA-256 cache key to prevent cross-personality cache collisions.

**Tech Stack:** Java 21, JUnit 5, AssertJ, Mockito, SessionPipeline (for LLM eval)

## Global Constraints

- Java 21 source, Java 26 JVM
- No SPI signature changes — personality data flows through existing `Map<String, String> metadata`
- All new code in `caps-llm-classifier` module (no new module dependencies)
- CBR cache fix in `caps-situation-cbr` module (no new module dependencies)
- Metadata injection in `mindmap-intelligence` module (already depends on `cognitive-index`)
- Tension threshold: `maxTension > 0.5` → path C; otherwise → path A

---

## Batch 1: Foundation — tension scoring and prompt building

### Task 1: DispositionTension — static tension table and scoring

**Files:**
- Create: `caps-llm-classifier/src/main/java/io/casehub/neocortex/caps/llm/DispositionTension.java`
- Test: `caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/DispositionTensionTest.java`

**Interfaces:**
- Consumes: raw `String` axis values from metadata map (keys: `disposition.socialOrient`, `disposition.ruleFollowing`, `disposition.riskAppetite`, `disposition.autonomy`, `disposition.conflictMode`)
- Produces:
  - `static double maxTension(Map<String, String> metadata)` — returns highest tension score [0.0, 1.0]
  - `static Optional<TensionEntry> topTension(Map<String, String> metadata)` — returns highest-scoring entry with narrative
  - `record TensionEntry(String axis1, String value1, String axis2, String value2, double score, String conflict, String narrative)` — inner record

- [ ] **Step 1: Write failing tests**

```java
package io.casehub.neocortex.caps.llm;

import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;

class DispositionTensionTest {

    @Test
    void boldStrict_maximumTension() {
        var meta = Map.of(
            "disposition.riskAppetite", "bold",
            "disposition.ruleFollowing", "strict");

        assertThat(DispositionTension.maxTension(meta)).isEqualTo(1.0);

        var top = DispositionTension.topTension(meta);
        assertThat(top).isPresent();
        assertThat(top.get().conflict()).isEqualTo("approach vs inhibition");
        assertThat(top.get().narrative()).contains("act decisively");
    }

    @Test
    void highAutonomyAvoidant_highTension() {
        var meta = Map.of(
            "disposition.autonomy", "high",
            "disposition.conflictMode", "avoidant");

        assertThat(DispositionTension.maxTension(meta)).isEqualTo(0.9);
    }

    @Test
    void cooperativeHighAutonomy_tension() {
        var meta = Map.of(
            "disposition.socialOrient", "cooperative",
            "disposition.autonomy", "high");

        assertThat(DispositionTension.maxTension(meta)).isEqualTo(0.8);
    }

    @Test
    void boldAvoidant_tension() {
        var meta = Map.of(
            "disposition.riskAppetite", "bold",
            "disposition.conflictMode", "avoidant");

        assertThat(DispositionTension.maxTension(meta)).isEqualTo(0.7);
    }

    @Test
    void independentLowAutonomy_tension() {
        var meta = Map.of(
            "disposition.socialOrient", "independent",
            "disposition.autonomy", "low");

        assertThat(DispositionTension.maxTension(meta)).isEqualTo(0.7);
    }

    @Test
    void competitiveStrict_tension() {
        var meta = Map.of(
            "disposition.socialOrient", "competitive",
            "disposition.ruleFollowing", "strict");

        assertThat(DispositionTension.maxTension(meta)).isEqualTo(0.6);
    }

    @Test
    void noConflictingAxes_zeroTension() {
        var meta = Map.of(
            "disposition.socialOrient", "cooperative",
            "disposition.ruleFollowing", "moderate",
            "disposition.riskAppetite", "calculated",
            "disposition.autonomy", "moderate",
            "disposition.conflictMode", "collaborative");

        assertThat(DispositionTension.maxTension(meta)).isEqualTo(0.0);
        assertThat(DispositionTension.topTension(meta)).isEmpty();
    }

    @Test
    void emptyMetadata_zeroTension() {
        assertThat(DispositionTension.maxTension(Map.of())).isEqualTo(0.0);
        assertThat(DispositionTension.topTension(Map.of())).isEmpty();
    }

    @Test
    void nullMetadata_zeroTension() {
        assertThat(DispositionTension.maxTension(null)).isEqualTo(0.0);
        assertThat(DispositionTension.topTension(null)).isEmpty();
    }

    @Test
    void multipleTensions_returnsHighest() {
        var meta = Map.of(
            "disposition.riskAppetite", "bold",
            "disposition.ruleFollowing", "strict",
            "disposition.autonomy", "high",
            "disposition.conflictMode", "avoidant");

        assertThat(DispositionTension.maxTension(meta)).isEqualTo(1.0);
        assertThat(DispositionTension.topTension(meta).get().score()).isEqualTo(1.0);
    }

    @Test
    void partialMetadata_matchesAvailablePairs() {
        var meta = Map.of("disposition.riskAppetite", "bold");

        assertThat(DispositionTension.maxTension(meta)).isEqualTo(0.0);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-llm-classifier -Dtest=DispositionTensionTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation failure — `DispositionTension` class does not exist

- [ ] **Step 3: Write implementation**

```java
package io.casehub.neocortex.caps.llm;

import java.util.List;
import java.util.Map;
import java.util.Optional;

public final class DispositionTension {

    public record TensionEntry(String axis1, String value1,
                               String axis2, String value2,
                               double score, String conflict,
                               String narrative) {}

    private static final List<TensionEntry> TABLE = List.of(
        new TensionEntry("riskAppetite", "bold", "ruleFollowing", "strict",
            1.0, "approach vs inhibition",
            "wants to act decisively but feels bound by rules — ambiguous situations feel like tests of whether the rules permit the action"),
        new TensionEntry("autonomy", "high", "conflictMode", "avoidant",
            0.9, "independent but won't confront",
            "values independence but avoids confrontation — perceives social expectations as constraints but won't push against them directly"),
        new TensionEntry("socialOrient", "cooperative", "autonomy", "high",
            0.8, "group-oriented but self-directed",
            "drawn to group goals but resistant to group control — reads situations for both collaboration potential and threats to independence"),
        new TensionEntry("riskAppetite", "bold", "conflictMode", "avoidant",
            0.7, "acts but doesn't confront",
            "impulsive toward action but shrinks from interpersonal friction — sees opportunities but worries about the social cost of seizing them"),
        new TensionEntry("socialOrient", "independent", "autonomy", "low",
            0.7, "independent identity but follows",
            "identifies as self-reliant but defers to authority — notices when others lead but feels conflicted about following"),
        new TensionEntry("socialOrient", "competitive", "ruleFollowing", "strict",
            0.6, "driven to win but bound by rules",
            "driven to win but constrained by propriety — seeks advantage within the rules, alert to where rules create or block competitive edges")
    );

    private DispositionTension() {}

    public static double maxTension(Map<String, String> metadata) {
        return topTension(metadata).map(TensionEntry::score).orElse(0.0);
    }

    public static Optional<TensionEntry> topTension(Map<String, String> metadata) {
        if (metadata == null || metadata.isEmpty()) return Optional.empty();

        TensionEntry best = null;
        for (TensionEntry entry : TABLE) {
            String v1 = metadata.get("disposition." + entry.axis1);
            String v2 = metadata.get("disposition." + entry.axis2);
            if (entry.value1.equals(v1) && entry.value2.equals(v2)) {
                if (best == null || entry.score > best.score) {
                    best = entry;
                }
            }
        }
        return Optional.ofNullable(best);
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-llm-classifier -Dtest=DispositionTensionTest`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```
feat(#941): add DispositionTension utility — static tension table for A/C prompt routing

Refs #941
```

---

### Task 2: PersonalityPromptBuilder — path A and path C prompt construction

**Files:**
- Create: `caps-llm-classifier/src/main/java/io/casehub/neocortex/caps/llm/PersonalityPromptBuilder.java`
- Test: `caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/PersonalityPromptBuilderTest.java`

**Interfaces:**
- Consumes: `DispositionTension.TensionEntry`, `Map<String, String> metadata` with `disposition.*` keys, `CapsTopology` (from caps-api)
- Produces:
  - `static String userPromptSuffix(Map<String, String> metadata)` — path A personality appendage for user prompt
  - `static String personalitySystemPrompt(Map<String, String> metadata, DispositionTension.TensionEntry tension, CapsTopology topology)` — path C full system prompt with personality frame
  - `static boolean hasDisposition(Map<String, String> metadata)` — quick check for presence of disposition keys

- [ ] **Step 1: Write failing tests**

```java
package io.casehub.neocortex.caps.llm;

import io.casehub.neocortex.caps.CapsNode;
import io.casehub.neocortex.caps.CapsTopology;
import io.casehub.neocortex.caps.NodeRange;
import io.casehub.neocortex.caps.NodeType;
import io.casehub.neocortex.caps.WeightUpdateParameters;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class PersonalityPromptBuilderTest {

    private static final CapsTopology TOPOLOGY = new CapsTopology(1,
        Map.of(
            "reward", new CapsNode("reward", NodeType.INPUT, NodeRange.UNIPOLAR,
                "consequence", List.of("operant"), Map.of("rewarded", 0.8)),
            "social_threat", new CapsNode("social_threat", NodeType.INPUT, NodeRange.UNIPOLAR,
                "threat", List.of("attachment"), Map.of("excluded", 0.9))
        ),
        List.of(), Map.of(), List.of(),
        new WeightUpdateParameters(0.01, 0.25, 0.1, 0.5, 0.95,
            Map.of(), 0.2, 100, 0.001,
            new double[]{-2.0, 2.0}, new double[]{0.1, 3.0}, 0.6));

    @Test
    void userPromptSuffix_containsAllAxes() {
        var meta = Map.of(
            "disposition.socialOrient", "competitive",
            "disposition.ruleFollowing", "flexible",
            "disposition.riskAppetite", "bold",
            "disposition.autonomy", "high",
            "disposition.conflictMode", "assertive");

        String suffix = PersonalityPromptBuilder.userPromptSuffix(meta);

        assertThat(suffix).contains("competitive");
        assertThat(suffix).contains("flexible");
        assertThat(suffix).contains("bold");
        assertThat(suffix).contains("high");
        assertThat(suffix).contains("assertive");
        assertThat(suffix).contains("Classify the situation as this character would perceive it");
    }

    @Test
    void personalitySystemPrompt_containsFrame() {
        var meta = Map.of(
            "disposition.riskAppetite", "bold",
            "disposition.ruleFollowing", "strict",
            "disposition.socialOrient", "competitive",
            "disposition.autonomy", "moderate",
            "disposition.conflictMode", "collaborative");

        var tension = DispositionTension.topTension(meta).orElseThrow();

        String sysPrompt = PersonalityPromptBuilder.personalitySystemPrompt(
            meta, tension, TOPOLOGY);

        assertThat(sysPrompt).contains("through a specific character's lens");
        assertThat(sysPrompt).contains(tension.narrative());
        assertThat(sysPrompt).contains("reward");
        assertThat(sysPrompt).contains("social_threat");
    }

    @Test
    void personalitySystemPrompt_includesTopologyNodes() {
        var meta = Map.of(
            "disposition.riskAppetite", "bold",
            "disposition.ruleFollowing", "strict");
        var tension = DispositionTension.topTension(meta).orElseThrow();

        String sysPrompt = PersonalityPromptBuilder.personalitySystemPrompt(
            meta, tension, TOPOLOGY);

        assertThat(sysPrompt).contains("reward");
        assertThat(sysPrompt).contains("social_threat");
        assertThat(sysPrompt).contains("JSON");
    }

    @Test
    void hasDisposition_true() {
        assertThat(PersonalityPromptBuilder.hasDisposition(
            Map.of("disposition.socialOrient", "cooperative"))).isTrue();
    }

    @Test
    void hasDisposition_false() {
        assertThat(PersonalityPromptBuilder.hasDisposition(Map.of())).isFalse();
        assertThat(PersonalityPromptBuilder.hasDisposition(null)).isFalse();
        assertThat(PersonalityPromptBuilder.hasDisposition(
            Map.of("event-type", "observation"))).isFalse();
    }

    @Test
    void userPromptSuffix_missingAxes_includesAvailable() {
        var meta = Map.of(
            "disposition.socialOrient", "cooperative",
            "disposition.riskAppetite", "calculated");

        String suffix = PersonalityPromptBuilder.userPromptSuffix(meta);

        assertThat(suffix).contains("cooperative");
        assertThat(suffix).contains("calculated");
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-llm-classifier -Dtest=PersonalityPromptBuilderTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation failure — `PersonalityPromptBuilder` does not exist

- [ ] **Step 3: Write implementation**

```java
package io.casehub.neocortex.caps.llm;

import io.casehub.neocortex.caps.CapsTopology;
import io.casehub.neocortex.caps.NodeType;

import java.util.Map;
import java.util.StringJoiner;

public final class PersonalityPromptBuilder {

    private static final String DISPOSITION_PREFIX = "disposition.";
    private static final String[] AXIS_KEYS = {
        "socialOrient", "ruleFollowing", "riskAppetite", "autonomy", "conflictMode"
    };
    private static final String[] AXIS_LABELS = {
        "", " rule-following", " risk appetite", " autonomy", " conflict style"
    };

    private PersonalityPromptBuilder() {}

    public static boolean hasDisposition(Map<String, String> metadata) {
        if (metadata == null) return false;
        for (String key : AXIS_KEYS) {
            if (metadata.containsKey(DISPOSITION_PREFIX + key)) return true;
        }
        return false;
    }

    public static String userPromptSuffix(Map<String, String> metadata) {
        var joiner = new StringJoiner(", ");
        for (int i = 0; i < AXIS_KEYS.length; i++) {
            String val = metadata.get(DISPOSITION_PREFIX + AXIS_KEYS[i]);
            if (val != null) {
                joiner.add(val + AXIS_LABELS[i]);
            }
        }
        return "\nCharacter disposition: " + joiner +
               ".\nClassify the situation as this character would perceive it.";
    }

    public static String personalitySystemPrompt(Map<String, String> metadata,
                                                  DispositionTension.TensionEntry tension,
                                                  CapsTopology topology) {
        var sb = new StringBuilder();
        sb.append("""
                  You are a psychological situation classifier perceiving the world \
                  through a specific character's lens.

                  This character is """);

        var joiner = new StringJoiner(", ");
        for (int i = 0; i < AXIS_KEYS.length; i++) {
            String val = metadata.get(DISPOSITION_PREFIX + AXIS_KEYS[i]);
            if (val != null) {
                joiner.add(val + AXIS_LABELS[i]);
            }
        }
        sb.append(joiner).append(". ");
        sb.append(tension.narrative()).append("\n\n");

        sb.append("""
                  Classify the following situation into CAPS input node activations.

                  Respond with a JSON object:
                  {"activations": [{"node": "node_id", "confidence": 0.0-1.0}]}

                  Rules:
                  - Only use node IDs from the list below
                  - confidence reflects how strongly the description matches the node
                  - Multiple nodes can activate for the same description
                  - Minimum confidence threshold is 0.3
                  - Respond with valid JSON only

                  Available input nodes:
                  """);

        if (topology != null) {
            topology.nodes().forEach((id, node) -> {
                if (node.type() == NodeType.INPUT) {
                    sb.append("- ").append(id);
                    if (!node.description().isEmpty()) {
                        sb.append(" (").append(node.category())
                          .append(": ").append(node.description()).append(")");
                    } else {
                        sb.append(" (").append(node.category()).append(")");
                    }
                    sb.append(node.vocabulary().isEmpty() ? "" :
                              " — vocabulary: " + String.join(", ", node.vocabulary().keySet()));
                    sb.append("\n");
                }
            });
        }

        return sb.toString();
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-llm-classifier -Dtest=PersonalityPromptBuilderTest`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```
feat(#941): add PersonalityPromptBuilder — path A/C prompt construction from disposition metadata

Refs #941
```

---

## Batch 2: Integration — classifier routing, metadata injection, CBR fix

### Task 3: LlmSituationClassifier — personality-aware prompt routing

**Files:**
- Modify: `caps-llm-classifier/src/main/java/io/casehub/neocortex/caps/llm/LlmSituationClassifier.java`
- Modify: `caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/LlmSituationClassifierTest.java`

**Interfaces:**
- Consumes: `DispositionTension.maxTension()`, `DispositionTension.topTension()`, `PersonalityPromptBuilder.userPromptSuffix()`, `PersonalityPromptBuilder.personalitySystemPrompt()`, `PersonalityPromptBuilder.hasDisposition()`
- Produces: Modified `classify()` that routes to path A or path C based on tension score; modified `buildUserPrompt()` that appends personality suffix

**Changes to `LlmSituationClassifier`:**
1. Store `topology` as a field (currently only used in constructor to build system prompt)
2. In `classify()`: read disposition metadata, compute tension, route A/C
3. Path A: append personality suffix to user prompt via existing `buildUserPrompt()`
4. Path C: rebuild system prompt via `PersonalityPromptBuilder.personalitySystemPrompt()`, also append personality suffix to user prompt

- [ ] **Step 1: Write failing tests**

Add to `LlmSituationClassifierTest.java`:

```java
@Test
void classify_pathA_appendsDispositionToUserPrompt() {
    var capturedPrompts = new java.util.ArrayList<String>();
    var pipeline = capturingPipeline(capturedPrompts,
        "{\"activations\": [{\"node\": \"reward\", \"confidence\": 0.8}]}");
    var classifier = new LlmSituationClassifier(pipeline, TOPOLOGY);

    var metadata = new java.util.HashMap<String, String>();
    metadata.put("disposition.socialOrient", "competitive");
    metadata.put("disposition.ruleFollowing", "flexible");
    metadata.put("disposition.riskAppetite", "bold");
    metadata.put("disposition.autonomy", "high");
    metadata.put("disposition.conflictMode", "assertive");

    classifier.classify("Got rewarded", metadata,
        ClassificationContext.of("t1"));

    assertThat(capturedPrompts).hasSize(1);
    assertThat(capturedPrompts.getFirst()).contains("competitive");
    assertThat(capturedPrompts.getFirst()).contains("Classify the situation as this character");
}

@Test
void classify_pathC_usesPersonalitySystemPrompt() {
    var capturedInits = new java.util.ArrayList<AgentSessionInit>();
    var pipeline = capturingInitPipeline(capturedInits,
        "{\"activations\": [{\"node\": \"reward\", \"confidence\": 0.7}]}");
    var classifier = new LlmSituationClassifier(pipeline, TOPOLOGY);

    var metadata = new java.util.HashMap<String, String>();
    metadata.put("disposition.riskAppetite", "bold");
    metadata.put("disposition.ruleFollowing", "strict");

    classifier.classify("Ambiguous situation", metadata,
        ClassificationContext.of("t1"));

    assertThat(capturedInits).hasSize(1);
    assertThat(capturedInits.getFirst().systemPrompt())
        .contains("through a specific character's lens");
}

@Test
void classify_noDisposition_usesDefaultPrompt() {
    var capturedPrompts = new java.util.ArrayList<String>();
    var pipeline = capturingPipeline(capturedPrompts,
        "{\"activations\": [{\"node\": \"reward\", \"confidence\": 0.8}]}");
    var classifier = new LlmSituationClassifier(pipeline, TOPOLOGY);

    classifier.classify("Got rewarded", Map.of(),
        ClassificationContext.of("t1"));

    assertThat(capturedPrompts).hasSize(1);
    assertThat(capturedPrompts.getFirst()).doesNotContain("Character disposition");
}
```

These tests require two new helper methods: `capturingPipeline` (captures user prompts) and `capturingInitPipeline` (captures session init including system prompt). Both are variations of the existing `stubPipeline`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-llm-classifier -Dtest=LlmSituationClassifierTest`
Expected: FAIL — new tests fail because classifier ignores disposition metadata

- [ ] **Step 3: Implement changes to LlmSituationClassifier**

Modifications to `LlmSituationClassifier.java`:

1. Add `topology` field (store in constructor):
   ```java
   private final CapsTopology topology;
   ```

2. In constructor, store topology:
   ```java
   this.topology = topology;
   ```

3. Modify `classify()` to route based on tension:
   ```java
   @Override
   public ClassificationResult classify(String description,
                                         Map<String, String> metadata,
                                         ClassificationContext context) {
       if (description == null || description.isBlank()) {
           return new ClassificationResult(List.of());
       }

       boolean hasPersonality = PersonalityPromptBuilder.hasDisposition(metadata);
       double tension = hasPersonality ? DispositionTension.maxTension(metadata) : 0.0;
       boolean pathC = tension > 0.5;

       var sessionId = context.agentId() != null
               ? "classifier-" + context.agentId()
               : "classifier-" + java.util.UUID.randomUUID();

       AgentSessionInit init;
       if (pathC) {
           var tensionEntry = DispositionTension.topTension(metadata).orElseThrow();
           String personalitySystem = PersonalityPromptBuilder.personalitySystemPrompt(
               metadata, tensionEntry, topology);
           init = AgentSessionInit.of(personalitySystem).withModel(model);
       } else {
           init = AgentSessionInit.of(systemPrompt).withModel(model);
       }

       var session = pipeline.openSession(sessionId, init);
       try {
           String userPrompt = buildUserPrompt(description, metadata);
           if (hasPersonality) {
               userPrompt += PersonalityPromptBuilder.userPromptSuffix(metadata);
           }
           // ... rest unchanged
       }
   }
   ```

4. Add `capturingPipeline` and `capturingInitPipeline` helpers to test file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-llm-classifier -Dtest=LlmSituationClassifierTest`
Expected: All tests PASS (including existing tests)

- [ ] **Step 5: Commit**

```
feat(#941): LlmSituationClassifier personality-aware A/C prompt routing

Path A (low/no tension): personality suffix appended to user prompt.
Path C (tension > 0.5): personality frame in system prompt + suffix in user prompt.

Refs #941
```

---

### Task 4: BehavioralSynthesisPhase — disposition metadata injection

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhase.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhaseTest.java`

**Interfaces:**
- Consumes: `CognitiveDefaultsRegistry.forAgent(agentId)` → `CognitiveDefaults.descriptor()` → `DescriptorView.disposition()` → `DispositionAxes`
- Produces: `disposition.*` metadata entries in the `Map<String, String>` passed to `classifier.classify()`

**Changes:** Two call sites inject disposition metadata:
1. Line 143-145 (experience classification loop) — add disposition to metadata
2. Line 435 (drive intensity fallback classification) — add disposition to metadata

Both call sites use the same `agentId` already available in their loop scope.

- [ ] **Step 1: Write failing test**

Add to `BehavioralSynthesisPhaseTest.java` — verify that disposition metadata is passed to the classifier:

```java
@Test
void classify_passesDispositionMetadata() {
    // Arrange: set up defaultsRegistry with known disposition axes
    // Use an argument captor on the classifier mock to verify metadata
    var classifierCaptor = ArgumentCaptor.forClass(Map.class);
    // ... (adapt to existing test pattern — mock classifier, verify metadata keys)
    
    // Assert metadata contains disposition.* keys matching the agent's profile
}
```

The exact test shape depends on the existing test setup in `BehavioralSynthesisPhaseTest` — read the test file, follow its patterns for mocking the classifier and capturing arguments.

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=BehavioralSynthesisPhaseTest#classify_passesDispositionMetadata`
Expected: FAIL — metadata does not contain disposition keys

- [ ] **Step 3: Implement metadata injection**

Add a helper method to `BehavioralSynthesisPhase`:

```java
private Map<String, String> addDispositionMetadata(Map<String, String> metadata, String agentId) {
    if (defaultsRegistry == null) return metadata;
    var defaults = defaultsRegistry.forAgent(agentId);
    if (defaults.isEmpty() || defaults.get().descriptor() == null) return metadata;
    var axes = defaults.get().descriptor().disposition();
    if (axes == null) return metadata;

    var enriched = new HashMap<>(metadata);
    if (axes.socialOrient() != null) enriched.put("disposition.socialOrient", axes.socialOrient());
    if (axes.ruleFollowing() != null) enriched.put("disposition.ruleFollowing", axes.ruleFollowing());
    if (axes.riskAppetite() != null) enriched.put("disposition.riskAppetite", axes.riskAppetite());
    if (axes.autonomy() != null) enriched.put("disposition.autonomy", axes.autonomy());
    if (axes.conflictMode() != null) enriched.put("disposition.conflictMode", axes.conflictMode());
    return enriched;
}
```

Modify call site 1 (line ~143):
```java
ClassificationResult classResult = classifier.classify(
    node.name(), addDispositionMetadata(nodeMetadata(node), agentId),
    ClassificationContext.of(tenantId));
```

Modify call site 2 (line ~435):
```java
var classResult = classifier.classify(description,
    addDispositionMetadata(Map.of(), agentId),
    ClassificationContext.of(tenantId));
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=BehavioralSynthesisPhaseTest`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```
feat(#941): BehavioralSynthesisPhase injects disposition metadata into classifier calls

Resolves DispositionAxes from CognitiveDefaultsRegistry for each agent,
serializes as disposition.* metadata entries at both classify() call sites.

Refs #941
```

---

### Task 5: CbrCachingSituationDecorator — disposition in cache key

**Files:**
- Modify: `caps-situation-cbr/src/main/java/io/casehub/neocortex/caps/cbr/CbrCachingSituationDecorator.java`
- Modify: `caps-situation-cbr/src/test/java/io/casehub/neocortex/caps/cbr/CbrCachingSituationDecoratorTest.java`

**Interfaces:**
- Consumes: `disposition.*` keys from metadata map
- Produces: Modified `computeCaseId()` that includes disposition values in hash; modified schema with disposition feature fields

**Changes:**
1. `computeCaseId()` — include sorted disposition values in SHA-256 hash
2. `SCHEMA` — add `disposition-socialOrient`, `disposition-ruleFollowing`, `disposition-riskAppetite`, `disposition-autonomy`, `disposition-conflictMode` as categorical feature fields
3. `storeCbr()` — include disposition values as features
4. `lookupCbr()` — add disposition filter to query

- [ ] **Step 1: Write failing tests**

Add to `CbrCachingSituationDecoratorTest.java`:

```java
@Test
void computeCaseId_includesDisposition() {
    String idNoDisp = CbrCachingSituationDecorator.computeCaseId(
        "desc", "obs", "concern", Map.of());
    String idWithDisp = CbrCachingSituationDecorator.computeCaseId(
        "desc", "obs", "concern",
        Map.of("disposition.socialOrient", "competitive"));

    assertThat(idNoDisp).isNotEqualTo(idWithDisp);
}

@Test
void computeCaseId_differentDispositions_differentIds() {
    String id1 = CbrCachingSituationDecorator.computeCaseId(
        "desc", "obs", "concern",
        Map.of("disposition.socialOrient", "competitive"));
    String id2 = CbrCachingSituationDecorator.computeCaseId(
        "desc", "obs", "concern",
        Map.of("disposition.socialOrient", "cooperative"));

    assertThat(id1).isNotEqualTo(id2);
}

@Test
void computeCaseId_sameDisposition_sameId() {
    String id1 = CbrCachingSituationDecorator.computeCaseId(
        "desc", "obs", "concern",
        Map.of("disposition.socialOrient", "competitive",
               "disposition.riskAppetite", "bold"));
    String id2 = CbrCachingSituationDecorator.computeCaseId(
        "desc", "obs", "concern",
        Map.of("disposition.socialOrient", "competitive",
               "disposition.riskAppetite", "bold"));

    assertThat(id1).isEqualTo(id2);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-situation-cbr -Dtest=CbrCachingSituationDecoratorTest`
Expected: FAIL — `computeCaseId` method signature doesn't accept metadata parameter

- [ ] **Step 3: Implement changes**

1. Update `computeCaseId` signature to accept metadata:
   ```java
   static String computeCaseId(String description, String eventType,
                                String cognitiveKind, Map<String, String> metadata)
   ```

2. In the hash computation, append sorted disposition values:
   ```java
   String[] dispKeys = {"disposition.autonomy", "disposition.conflictMode",
       "disposition.riskAppetite", "disposition.ruleFollowing",
       "disposition.socialOrient"};
   for (String key : dispKeys) {
       String val = metadata != null ? metadata.getOrDefault(key, "") : "";
       digest.update((byte) 0);
       digest.update(val.getBytes(StandardCharsets.UTF_8));
   }
   ```

3. Keep the old 3-arg method for backward compat (delegates with empty map):
   ```java
   static String computeCaseId(String description, String eventType,
                                String cognitiveKind) {
       return computeCaseId(description, eventType, cognitiveKind, Map.of());
   }
   ```

4. Update all internal call sites (`classify()`, `storeCbr()`) to pass metadata.

5. Add disposition categorical fields to `SCHEMA` and feature maps.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-situation-cbr -Dtest=CbrCachingSituationDecoratorTest`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```
feat(#941): CbrCachingSituationDecorator includes disposition in cache key

Different personalities now produce different cache keys, preventing
cross-personality cache collisions. Disposition values added as
categorical features for CBR query filtering.

Refs #941
```

---

## Batch 3: Evaluation — personality classification eval test

### Task 6: PersonalityClassificationEvalTest — LLM eval measuring activation divergence

**Files:**
- Create: `caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/eval/PersonalityClassificationEvalTest.java`

**Interfaces:**
- Consumes: `LlmSituationClassifier`, `DispositionTension`, `PersonalityPromptBuilder`, `SessionPipeline` (test infrastructure), CAPS topology
- Produces: eval assertions — inter-profile activation variance, tension dual-activation, bias detection

**Profiles** (from spec):

| Profile | socialOrient | ruleFollowing | riskAppetite | autonomy | conflictMode | Expected tension | Path |
|---|---|---|---|---|---|---|---|
| Competitive-assertive | competitive | flexible | bold | high | assertive | 0.0 | A |
| Cooperative-avoidant | cooperative | strict | conservative | low | avoidant | 0.0 | A |
| Bold-strict | competitive | strict | bold | moderate | collaborative | 1.0 | C |
| Moderate baseline | cooperative | moderate | calculated | moderate | collaborative | 0.0 | A |

**Observations** (minimum 4 from distinct CAPS input categories):
1. Relationship: "A colleague publicly takes credit for work you contributed to significantly"
2. Threat: "Your manager announces unexpected organizational changes that may affect your role"
3. Achievement: "You're offered a challenging project that could advance your career but requires skills you haven't fully developed"
4. Social: "During a team meeting, two colleagues disagree sharply about the approach and look to you to mediate"

- [ ] **Step 1: Write the eval test**

Pattern: follow existing eval tests in `caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/eval/` — use `@Tag("eval")`, real SessionPipeline, `EvalTestSupport` helpers if available.

```java
package io.casehub.neocortex.caps.llm.eval;

// Full eval test body — profiles, observations, metrics assertions
// See spec §Eval Design for exact metrics:
// 1. Inter-profile activation variance (cosine distance)
// 2. Tension dual-activation (bold-strict activates approach + inhibition)
// 3. Bias detection (no >80% single category)
// Temperature 0 for determinism
```

- [ ] **Step 2: Run eval (requires LLM backend)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-llm-classifier -Dtest=PersonalityClassificationEvalTest -Dgroups=eval`
Expected: All metrics pass thresholds defined in spec

- [ ] **Step 3: Commit**

```
feat(#941): add PersonalityClassificationEvalTest — personality divergence metrics

4 profiles × 4 observations measuring inter-profile variance,
tension dual-activation, and bias detection.

Refs #941
```

---

## References

- [2026-11-13-personality-situation-classification-design.md] — design spec this plan implements
- [LlmSituationClassifier.java] — current classifier implementation
- [SituationClassifier.java] — SPI interface (no changes)
- [ClassificationContext.java] — context record (no changes)
- [BehavioralSynthesisPhase.java:143,435] — classify() call sites for metadata injection
- [CbrCachingSituationDecorator.java:203-216] — computeCaseId() for cache key fix
- [DispositionAxes.java] — axis record definition
- [CognitiveDefaults.java:50] — descriptor field providing DispositionAxes access
- [CognitiveDefaultsRegistry.java:62,66] — forAgent/forAgentOrDefaults accessors
- [GitHub #941] — focal issue
- [GitHub #841] — parent epic

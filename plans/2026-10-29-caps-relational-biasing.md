# CAPS Per-Relationship Tick-Time Input Biasing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #720 — CAPS per-relationship tick-time input biasing
**Issue group:** #477 (epic), #716, #717, #718, #719, #720

**Goal:** After `SituationClassifier.classify()` in `AppraisalTickParticipant.tick()`, apply multiplicative biasing from `RelationalSchema.trust()` so that the same observation produces different CAPS activation patterns depending on the agent's per-relationship trust with the target.

**Architecture:** A pure-function utility class `RelationalBiasing` applies trust-based multiplicative scaling to 4 specific CAPS input node activations (secure_attachment, rejection, betrayal, psychological_threat). The biasing is inserted between `classify()` and `TopologyChannelWeighter.weight()` in `AppraisalTickParticipant.tick()`. Scaling factors are grounded in topology connection weights (van IJzendoorn 1995).

**Tech Stack:** Java 21, JUnit 5, AssertJ, Mockito, InMemoryMindMapStore

## Global Constraints

- Java 21 language level, Java 26 JVM
- All numeric dimensions use `double` in `[0,1]` or `[-1,1]`
- `SituationActivation` is a record — create new instances, don't mutate
- Multiplicative biasing (not additive) to avoid saturation against `[-1, 1]` clamp
- Scaling factors ≤ 1× topology weight to avoid overwhelming situation signal

---

## Batch 1: RelationalBiasing utility + wiring

### Task 1: RelationalBiasing utility with unit tests

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/RelationalBiasing.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/RelationalBiasingTest.java`

**Interfaces:**
- Consumes: `SituationActivation(nodeId, confidence, source)` from `caps-api`, `RelationalSchema(targetId, role, trust, intimacy, utility, description)` from `cognitive-index`
- Produces: `static List<SituationActivation> apply(@Nullable RelationalSchema schema, List<SituationActivation> activations)` — returns new list with biased confidences; returns input unchanged when schema is null

- [ ] **Step 1: Write failing tests for RelationalBiasing**

```java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.caps.SituationActivation;
import io.casehub.neocortex.cognitive.index.RelationalSchema;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

class RelationalBiasingTest {

    @Test
    void returnsUnchangedWhenSchemaNull() {
        var activations = List.of(
                new SituationActivation("secure_attachment", 0.8),
                new SituationActivation("mastery", 0.5));

        var result = RelationalBiasing.apply(null, activations);

        assertThat(result).isEqualTo(activations);
    }

    @Test
    void returnsUnchangedWhenActivationsEmpty() {
        var schema = new RelationalSchema("target1", "ally", 0.7, 0.5, 0.3, null);

        var result = RelationalBiasing.apply(schema, List.of());

        assertThat(result).isEmpty();
    }

    @Test
    void highTrustBoostsSecureAttachment() {
        var schema = new RelationalSchema("target1", "ally", 0.8, 0.5, 0.3, null);
        var activations = List.of(new SituationActivation("secure_attachment", 0.6));

        var result = RelationalBiasing.apply(schema, activations);

        // 0.6 * (1.0 + 0.8 * 0.3) = 0.6 * 1.24 = 0.744
        assertThat(result).hasSize(1);
        assertThat(result.getFirst().confidence()).isCloseTo(0.744, within(0.001));
    }

    @Test
    void highTrustDampensRejection() {
        var schema = new RelationalSchema("target1", "ally", 0.8, 0.5, 0.3, null);
        var activations = List.of(new SituationActivation("rejection", 0.6));

        var result = RelationalBiasing.apply(schema, activations);

        // 0.6 * (1.0 - 0.8 * 0.2) = 0.6 * 0.84 = 0.504
        assertThat(result).hasSize(1);
        assertThat(result.getFirst().confidence()).isCloseTo(0.504, within(0.001));
    }

    @Test
    void highTrustDampensBetrayal() {
        var schema = new RelationalSchema("target1", "ally", 0.8, 0.5, 0.3, null);
        var activations = List.of(new SituationActivation("betrayal", 0.6));

        var result = RelationalBiasing.apply(schema, activations);

        // 0.6 * (1.0 - 0.8 * 0.25) = 0.6 * 0.8 = 0.48
        assertThat(result).hasSize(1);
        assertThat(result.getFirst().confidence()).isCloseTo(0.48, within(0.001));
    }

    @Test
    void highTrustDampensPsychologicalThreat() {
        var schema = new RelationalSchema("target1", "ally", 0.8, 0.5, 0.3, null);
        var activations = List.of(new SituationActivation("psychological_threat", 0.6));

        var result = RelationalBiasing.apply(schema, activations);

        // 0.6 * (1.0 - 0.8 * 0.15) = 0.6 * 0.88 = 0.528
        assertThat(result).hasSize(1);
        assertThat(result.getFirst().confidence()).isCloseTo(0.528, within(0.001));
    }

    @Test
    void negativeTrustBoostsThreatDampensSecure() {
        var schema = new RelationalSchema("target1", "threat", -0.7, 0.0, 0.0, null);
        var activations = List.of(
                new SituationActivation("secure_attachment", 0.6),
                new SituationActivation("rejection", 0.6));

        var result = RelationalBiasing.apply(schema, activations);

        // secure: 0.6 * (1.0 + (-0.7) * 0.3) = 0.6 * 0.79 = 0.474
        assertThat(result.get(0).nodeId()).isEqualTo("secure_attachment");
        assertThat(result.get(0).confidence()).isCloseTo(0.474, within(0.001));
        // rejection: 0.6 * (1.0 - (-0.7) * 0.2) = 0.6 * 1.14 = 0.684
        assertThat(result.get(1).nodeId()).isEqualTo("rejection");
        assertThat(result.get(1).confidence()).isCloseTo(0.684, within(0.001));
    }

    @Test
    void unaffectedNodesPassThrough() {
        var schema = new RelationalSchema("target1", "ally", 0.8, 0.5, 0.3, null);
        var activations = List.of(
                new SituationActivation("mastery", 0.5),
                new SituationActivation("dominance", 0.4));

        var result = RelationalBiasing.apply(schema, activations);

        assertThat(result).hasSize(2);
        assertThat(result.get(0).confidence()).isEqualTo(0.5);
        assertThat(result.get(1).confidence()).isEqualTo(0.4);
    }

    @Test
    void preservesSourceArray() {
        var schema = new RelationalSchema("target1", "ally", 0.8, 0.5, 0.3, null);
        int[] source = {1, 2, 3};
        var activations = List.of(new SituationActivation("secure_attachment", 0.6, source));

        var result = RelationalBiasing.apply(schema, activations);

        assertThat(result.getFirst().source()).isSameAs(source);
    }

    @Test
    void zeroTrustNoEffect() {
        var schema = new RelationalSchema("target1", "stranger", 0.0, 0.0, 0.0, null);
        var activations = List.of(
                new SituationActivation("secure_attachment", 0.6),
                new SituationActivation("rejection", 0.5));

        var result = RelationalBiasing.apply(schema, activations);

        assertThat(result.get(0).confidence()).isEqualTo(0.6);
        assertThat(result.get(1).confidence()).isEqualTo(0.5);
    }

    @Test
    void mixedActivationsOnlyBiasesTargeted() {
        var schema = new RelationalSchema("target1", "ally", 0.8, 0.5, 0.3, null);
        var activations = List.of(
                new SituationActivation("secure_attachment", 0.6),
                new SituationActivation("mastery", 0.5),
                new SituationActivation("betrayal", 0.4),
                new SituationActivation("dominance", 0.3));

        var result = RelationalBiasing.apply(schema, activations);

        assertThat(result).hasSize(4);
        // secure_attachment biased
        assertThat(result.get(0).confidence()).isNotEqualTo(0.6);
        // mastery unchanged
        assertThat(result.get(1).confidence()).isEqualTo(0.5);
        // betrayal biased
        assertThat(result.get(2).confidence()).isNotEqualTo(0.4);
        // dominance unchanged
        assertThat(result.get(3).confidence()).isEqualTo(0.3);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=RelationalBiasingTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation failure — `RelationalBiasing` does not exist

- [ ] **Step 3: Implement RelationalBiasing**

```java
package io.casehub.neocortex.cognition.appraisal;

import io.casehub.neocortex.caps.SituationActivation;
import io.casehub.neocortex.cognitive.index.RelationalSchema;
import org.jspecify.annotations.Nullable;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class RelationalBiasing {

    private RelationalBiasing() {}

    private static final Map<String, Double> TRUST_SCALING = Map.of(
            "secure_attachment",    0.3,
            "rejection",           -0.2,
            "betrayal",            -0.25,
            "psychological_threat",-0.15
    );

    public static List<SituationActivation> apply(
            @Nullable RelationalSchema schema,
            List<SituationActivation> activations) {
        if (schema == null || activations.isEmpty()) {
            return activations;
        }

        double trust = schema.trust();
        if (trust == 0.0) {
            return activations;
        }

        var result = new ArrayList<SituationActivation>(activations.size());
        for (var activation : activations) {
            var scale = TRUST_SCALING.get(activation.nodeId());
            if (scale == null) {
                result.add(activation);
            } else {
                double biased = activation.confidence() * (1.0 + trust * scale);
                result.add(new SituationActivation(
                        activation.nodeId(), biased, activation.source()));
            }
        }
        return List.copyOf(result);
    }
}
```

The `TRUST_SCALING` map encodes the direction: positive values mean "boost with trust" (secure_attachment), negative values mean "dampen with trust" (rejection, betrayal, psychological_threat). The formula `confidence * (1.0 + trust * scale)` handles both directions:
- `secure_attachment` scale=+0.3: high trust → `1 + 0.8*0.3 = 1.24` (boost), low trust → `1 + (-0.7)*0.3 = 0.79` (dampen)
- `rejection` scale=-0.2: high trust → `1 + 0.8*(-0.2) = 0.84` (dampen), low trust → `1 + (-0.7)*(-0.2) = 1.14` (boost)

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=RelationalBiasingTest`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/RelationalBiasing.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/RelationalBiasingTest.java
git commit -m "feat(#720): RelationalBiasing utility with trust-based multiplicative CAPS input scaling

Refs #720

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 2: Wire RelationalBiasing into AppraisalTickParticipant + integration tests

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalTickParticipant.java:181-188`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/AppraisalTickParticipantTest.java`

**Interfaces:**
- Consumes: `RelationalBiasing.apply(schema, activations)` from Task 1, existing `resolveRelationalSchema()` (already in AppraisalTickParticipant), `SituationClassifier` SPI
- Produces: Biased `ChannelWeightProfile` stored via `channelWeights.put()` — existing accessor `currentChannelWeights(agentId, tenantId)` returns the biased result

- [ ] **Step 1: Write failing integration test — biasing wired when target and classifier present**

Add to `AppraisalTickParticipantTest.java`:

```java
@Test
void appliesRelationalBiasingToSituationClassification() {
    var store = new io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore();

    // Create PERSON subgraph with target node and observer overlay
    var personSgId = store.createSubgraph(
            new io.casehub.neocortex.mindmap.SubgraphInput("People",
                    io.casehub.neocortex.mindmap.SubgraphTypes.PERSON, null), "t1");
    var targetNodeId = store.addNode(
            io.casehub.neocortex.mindmap.NodeInput.of("Target Agent", personSgId)
                    .withProperties(Map.of("agentId", "target1")), "t1");
    // Create overlay for observer a1 → target
    var overlayProps = new java.util.HashMap<>(
            new RelationalSchema("target1", "ally", 0.8, 0.5, 0.3, null).toProperties());
    overlayProps.put(io.casehub.neocortex.mindmap.OverlayRef.AGENT_ID, "a1");
    var overlayRef = io.casehub.neocortex.mindmap.OverlayRef.of(targetNodeId);
    store.addNode(io.casehub.neocortex.mindmap.NodeInput.of("overlay-a1-target", personSgId)
                    .withTraits(java.util.Set.of("overlay"))
                    .withRefs(java.util.Set.of(overlayRef))
                    .withProperties(Map.copyOf(overlayProps)), "t1");

    // Classifier that returns fixed activations for any input
    SituationClassifier classifier = (desc, meta) -> List.of(
            new io.casehub.neocortex.caps.SituationActivation("secure_attachment", 0.6),
            new io.casehub.neocortex.caps.SituationActivation("rejection", 0.6),
            new io.casehub.neocortex.caps.SituationActivation("mastery", 0.5));

    var config = CognitionConfig.none().with("appraisal", true);
    var participant = new AppraisalTickParticipant(
            salienceStrategy, appraisalStrategy, driveOrchestrator,
            moodOrchestrator, null, config, store,
            AppraisalThresholds.defaults(), classifier);

    // Tick WITH target — biasing applies
    var contextWithTarget = new CognitionTickContext(
            "a1", "t1", null, (a, t) -> java.util.Set.of(),
            "Someone was kind to me", null, "target1");
    participant.tick(contextWithTarget);

    var biasedWeights = participant.currentChannelWeights("a1", "t1");
    assertThat(biasedWeights).isPresent();

    // Now tick WITHOUT target — no biasing
    participant.tick(contextWithObservation("Someone was kind to me"));

    var unbiasedWeights = participant.currentChannelWeights("a1", "t1");
    assertThat(unbiasedWeights).isPresent();

    // Biased and unbiased should produce different channel weights
    // because secure_attachment is boosted and rejection is dampened
    assertThat(biasedWeights.get()).isNotEqualTo(unbiasedWeights.get());
}
```

- [ ] **Step 2: Write failing test — no biasing when no target**

```java
@Test
void noRelationalBiasingWithoutTarget() {
    SituationClassifier classifier = (desc, meta) -> List.of(
            new io.casehub.neocortex.caps.SituationActivation("secure_attachment", 0.6),
            new io.casehub.neocortex.caps.SituationActivation("rejection", 0.6));

    var config = CognitionConfig.none().with("appraisal", true);
    var participant = new AppraisalTickParticipant(
            salienceStrategy, appraisalStrategy, driveOrchestrator,
            moodOrchestrator, null, config, null,
            AppraisalThresholds.defaults(), classifier);

    participant.tick(contextWithObservation("Someone was kind to me"));
    var weights1 = participant.currentChannelWeights("a1", "t1");

    participant.tick(contextWithObservation("Someone was kind to me"));
    var weights2 = participant.currentChannelWeights("a1", "t1");

    // Same input, no target — weights should be identical
    assertThat(weights1).isPresent();
    assertThat(weights2).isPresent();
    assertThat(weights1.get()).isEqualTo(weights2.get());
}
```

- [ ] **Step 3: Write the Hooded Claw test — kindness from prey vs kindness from tool → different CAPS outputs**

```java
@Test
void hoodedClawKindnessFromPreyVsToolProducesDifferentOutputs() {
    var store = new io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore();
    var personSgId = store.createSubgraph(
            new io.casehub.neocortex.mindmap.SubgraphInput("People",
                    io.casehub.neocortex.mindmap.SubgraphTypes.PERSON, null), "t1");

    // Create prey target — very low trust
    var preyNodeId = store.addNode(
            io.casehub.neocortex.mindmap.NodeInput.of("Prey Agent", personSgId)
                    .withProperties(Map.of("agentId", "prey1")), "t1");
    var preyOverlayProps = new java.util.HashMap<>(
            new RelationalSchema("prey1", "prey", -0.5, 0.0, 0.9, null).toProperties());
    preyOverlayProps.put(io.casehub.neocortex.mindmap.OverlayRef.AGENT_ID, "villain");
    store.addNode(io.casehub.neocortex.mindmap.NodeInput.of("overlay-villain-prey", personSgId)
                    .withTraits(java.util.Set.of("overlay"))
                    .withRefs(java.util.Set.of(io.casehub.neocortex.mindmap.OverlayRef.of(preyNodeId)))
                    .withProperties(Map.copyOf(preyOverlayProps)), "t1");

    // Create tool target — moderate trust
    var toolNodeId = store.addNode(
            io.casehub.neocortex.mindmap.NodeInput.of("Tool Agent", personSgId)
                    .withProperties(Map.of("agentId", "tool1")), "t1");
    var toolOverlayProps = new java.util.HashMap<>(
            new RelationalSchema("tool1", "tool", 0.3, 0.1, 0.8, null).toProperties());
    toolOverlayProps.put(io.casehub.neocortex.mindmap.OverlayRef.AGENT_ID, "villain");
    store.addNode(io.casehub.neocortex.mindmap.NodeInput.of("overlay-villain-tool", personSgId)
                    .withTraits(java.util.Set.of("overlay"))
                    .withRefs(java.util.Set.of(io.casehub.neocortex.mindmap.OverlayRef.of(toolNodeId)))
                    .withProperties(Map.copyOf(toolOverlayProps)), "t1");

    // Classifier returns same activations for "kindness" regardless of target
    SituationClassifier classifier = (desc, meta) -> List.of(
            new io.casehub.neocortex.caps.SituationActivation("secure_attachment", 0.7),
            new io.casehub.neocortex.caps.SituationActivation("rejection", 0.3),
            new io.casehub.neocortex.caps.SituationActivation("betrayal", 0.2));

    // Set up villain agent drives
    var villainProfile = new DriveProfile("villain", "t1",
            Map.of(DriveAxis.CURIOSITY, new DriveIntensity(DriveAxis.CURIOSITY, 0.7, "gaps")),
            0.7, DriveAxis.CURIOSITY, java.time.Instant.now());
    when(driveOrchestrator.currentDrives("villain", "t1")).thenReturn(Optional.of(villainProfile));
    when(moodOrchestrator.currentMood("villain", "t1")).thenReturn(Optional.empty());

    var config = CognitionConfig.none().with("appraisal", true);
    var participant = new AppraisalTickParticipant(
            salienceStrategy, appraisalStrategy, driveOrchestrator,
            moodOrchestrator, null, config, store,
            AppraisalThresholds.defaults(), classifier);

    // Kindness from prey (trust = -0.5)
    var preyContext = new CognitionTickContext(
            "villain", "t1", null, (a, t) -> java.util.Set.of(),
            "They showed unexpected kindness", null, "prey1");
    participant.tick(preyContext);
    var preyWeights = participant.currentChannelWeights("villain", "t1").orElseThrow();

    // Kindness from tool (trust = 0.3)
    var toolContext = new CognitionTickContext(
            "villain", "t1", null, (a, t) -> java.util.Set.of(),
            "They showed unexpected kindness", null, "tool1");
    participant.tick(toolContext);
    var toolWeights = participant.currentChannelWeights("villain", "t1").orElseThrow();

    // Different targets → different channel weight profiles
    assertThat(preyWeights).isNotEqualTo(toolWeights);
}
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=AppraisalTickParticipantTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Tests fail — biasing not yet wired

- [ ] **Step 5: Wire RelationalBiasing into AppraisalTickParticipant.tick()**

In `AppraisalTickParticipant.java`, modify lines 181-188. Change:

```java
if (situationClassifier != null && observation != null) {
    try {
        var activations = situationClassifier.classify(observation, Map.of());
        channelWeights.put(agentKey, TopologyChannelWeighter.weight(activations));
    } catch (Exception e) {
        channelWeights.put(agentKey, ChannelWeightProfile.DEFAULT);
    }
}
```

To:

```java
if (situationClassifier != null && observation != null) {
    try {
        var activations = situationClassifier.classify(observation, Map.of());
        activations = RelationalBiasing.apply(targetSchema, activations);
        channelWeights.put(agentKey, TopologyChannelWeighter.weight(activations));
    } catch (Exception e) {
        channelWeights.put(agentKey, ChannelWeightProfile.DEFAULT);
    }
}
```

One line inserted. `targetSchema` is already resolved earlier in the method (line 160-164) and is `null` when no target is present — `RelationalBiasing.apply()` returns activations unchanged when schema is null.

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=AppraisalTickParticipantTest`
Expected: All tests PASS (existing + 3 new)

- [ ] **Step 7: Run full cognition module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: All tests PASS — no regressions

- [ ] **Step 8: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalTickParticipant.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/AppraisalTickParticipantTest.java
git commit -m "feat(#720): wire RelationalBiasing into AppraisalTickParticipant tick pipeline

Hooded Claw test: kindness from prey vs tool produces different CAPS outputs.

Closes #720

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## References

- `specs/issue-477-relational-schemas/2026-10-28-relational-schemas-design.md` — design spec §CAPS per-relationship biasing
- `specs/issue-477-relational-schemas/decisions.md` — D1-D4 design decisions
- `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalTickParticipant.java:160-188` — target resolution + situation classification
- `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/TopologyChannelWeighter.java` — channel weighting from activations
- `caps-api/src/main/java/io/casehub/neocortex/caps/SituationActivation.java` — activation record
- `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/RelationalSchema.java` — relational schema record
- `caps-engine/src/main/resources/caps-topology.yaml` — connection weights grounding scaling factors
- GitHub #720, #477 (epic)

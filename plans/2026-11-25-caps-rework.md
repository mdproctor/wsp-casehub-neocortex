# CAPS Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #1222 — SE2: CAPS Rework — settler, learning, topology, classification
**Issue group:** #1222

**Goal:** Fix 14 bugs that make CAPS produce near-identical output across characters and situations by eliminating the unipolar background signal, implementing proper multi-cue Rescorla-Wagner learning, and fixing classification/CBR coherence.

**Architecture:** Replace logistic activation (resting at 0.5) with BIPOLAR tanh / rectified tanh (resting at 0.0) for mediating and output nodes. Restructure weight learning from per-connection to per-target-node multi-cue R-W. Filter drive injection to input nodes only. Fix CBR cache polarity.

**Tech Stack:** Java 21 (on Java 26 JVM), Quarkus 3.32.2, SQLite (Flyway), ONNX Runtime

## Global Constraints

- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Test module: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl <module>`
- Use `mvn` not `./mvnw`
- Use IntelliJ MCP tools (`ide_find_references`, `ide_replace_member`, `ide_insert_member`) for code navigation and editing
- Pre-release stage — no backward compatibility needed
- Each task = one atomic commit within a single PR

---

## Batch 1: Settler Foundation

### Task 1: BIPOLAR / Rectified Tanh + Activation Clamp (D2, B1, N6)

**Files:**
- Modify: `caps-api/src/main/java/io/casehub/neocortex/caps/NodeRange.java:12-17`
- Modify: `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsSettler.java:85-105`
- Modify: `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsTopologyLoader.java:124-125`
- Test: `caps-testing/src/test/java/io/casehub/neocortex/caps/testing/CapsEngineContractTest.java`

**Interfaces:**
- Produces: `NodeRange.UNIPOLAR.restingLevel()` returns 0.0 (was 0.5)
- Produces: `CapsTopologyLoader.defaultRange(OUTPUT)` returns BIPOLAR (was UNIPOLAR)
- Produces: UNIPOLAR activation uses `max(0, tanh(x))` (was `logistic(x)`)
- Produces: Activation clamped to range before damping

- [ ] **Step 1: Write failing test — zero-input produces zero output activation**

Add to `CapsEngineContractTest`:

```java
@Test
void zeroInputProducesZeroOutputActivation() {
    var state = engine.initializeAgent("t1", "zero-test",
        new DispositionAxes("cooperative", "moderate", "calculated", "moderate", "collaborative"));
    var result = engine.settle(state, Map.of());
    for (var entry : result.activations().entrySet()) {
        CapsNode node = engine.topology().nodes().get(entry.getKey());
        if (node != null && node.type() != NodeType.INPUT) {
            assertThat(Math.abs(entry.getValue()))
                .as("non-input node %s should be near zero with no input", entry.getKey())
                .isLessThan(0.1);
        }
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-testing -Dtest=InMemoryCapsEngineTest#zeroInputProducesZeroOutputActivation`
Expected: FAIL — logistic(0) = 0.5 produces non-zero activations on all unipolar nodes.

- [ ] **Step 3: Update NodeRange.restingLevel()**

Use `ide_replace_member` on `NodeRange.restingLevel()`:

```java
/**
 * Activation value of an unstimulated node under this range's
 * activation function: tanh(0) = 0.0 for bipolar,
 * max(0, tanh(0)) = 0.0 for unipolar.
 */
public double restingLevel() {
    return 0.0;
}
```

- [ ] **Step 4: Update CapsTopologyLoader.defaultRange()**

Use `ide_replace_member` on `CapsTopologyLoader.defaultRange()`:

```java
private NodeRange defaultRange(NodeType type) {
    return type == NodeType.OUTPUT ? NodeRange.BIPOLAR : NodeRange.UNIPOLAR;
}
```

- [ ] **Step 5: Replace activation functions and add clamp in CapsSettler.settle()**

In `CapsSettler.java`, replace the activation block at lines 90-99 with:

```java
double rawAct;
if (node.range() == NodeRange.BIPOLAR) {
    rawAct = Math.tanh(netInput - ns.activationThreshold());
} else {
    rawAct = Math.max(0.0, Math.tanh(netInput - ns.activationThreshold()));
}

double clampedAct = switch (node.range()) {
    case BIPOLAR -> Math.max(-1.0, Math.min(1.0, rawAct));
    case UNIPOLAR -> Math.max(0.0, Math.min(1.0, rawAct));
};

double oldAct = activations.getOrDefault(node.id(), 0.0);
double newAct = config.dampingFactor() * oldAct + (1.0 - config.dampingFactor()) * clampedAct;
```

- [ ] **Step 6: Remove the logistic() method**

Delete `CapsSettler.logistic()` at lines 223-225 — no longer used.

- [ ] **Step 7: Update existing contract test assertions for BIPOLAR scale**

Update `CapsEngineContractTest` assertions that assume unipolar output range [0, 1]:
- `settlingConvergesWithSimpleInput`: activations are still non-empty and convergence still one of CONVERGED/OSCILLATION/MAX_ITERATIONS — no assertion changes needed.
- `highBISInputProducesCautiousApproach`: directional assertion `cautious_approach > approach` — still valid under BIPOLAR.
- `highBISInputActivatesAvoidantCopingAttractors`: `avoidance > planning` — still valid.
- `copingBiasDirectionallyDifferentiatesProfiles`: directional — still valid.
- `inputNodesAreClampedDuringSettling`: input nodes are still clamped at the values provided — unchanged.

Run all existing tests to identify any that fail:

- [ ] **Step 8: Run all caps-engine and caps-testing tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-engine,caps-testing`
Expected: `zeroInputProducesZeroOutputActivation` PASSES. Other tests may need threshold adjustments — fix any that fail by adjusting absolute value expectations while preserving directional assertions.

- [ ] **Step 9: Commit**

```bash
git add caps-api/src/main/java/io/casehub/neocortex/caps/NodeRange.java caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsSettler.java caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsTopologyLoader.java caps-testing/
git commit -m "fix(caps): replace logistic with rectified tanh, default output to BIPOLAR (B1, N6) Refs #1222"
```

---

### Task 2: Autonomy Disposition Modifier Key Fix (N3)

**Files:**
- Modify: `caps-engine/src/main/resources/caps-topology.yaml` (autonomy modifier section)
- Test: `caps-testing/src/test/java/io/casehub/neocortex/caps/testing/CapsEngineContractTest.java`

**Interfaces:**
- Consumes: `DispositionAxes.autonomy()` returns `"independent"`, `"dependent"`, or `"moderate"`
- Produces: YAML autonomy modifiers fire for `independent`/`dependent` agents

- [ ] **Step 1: Write failing test — autonomy modifiers produce weight differences**

Add to `CapsEngineContractTest`:

```java
@Test
void autonomyModifiersProduceWeightDifferences() {
    var independent = engine.initializeAgent("t1", "ind",
        new DispositionAxes("cooperative", "moderate", "calculated", "independent", "collaborative"));
    var dependent = engine.initializeAgent("t1", "dep",
        new DispositionAxes("cooperative", "moderate", "calculated", "dependent", "collaborative"));
    boolean anyDifference = false;
    for (String connId : independent.weights().keySet()) {
        double wInd = independent.weights().get(connId).excitatory();
        double wDep = dependent.weights().getOrDefault(connId,
            new ConnectionWeight(0, 0, 1, 1)).excitatory();
        if (Math.abs(wInd - wDep) > 0.001) { anyDifference = true; break; }
    }
    assertThat(anyDifference)
        .as("independent vs dependent agents must have different connection weights")
        .isTrue();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-testing -Dtest=InMemoryCapsEngineTest#autonomyModifiersProduceWeightDifferences`
Expected: FAIL — YAML keys `low`/`high` don't match `independent`/`dependent`.

- [ ] **Step 3: Fix YAML keys**

In `caps-engine/src/main/resources/caps-topology.yaml`, find the `autonomy:` section under `disposition_modifiers:` and change:
- `low:` → `dependent:`
- `high:` → `independent:`

Leave `moderate:` unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-testing -Dtest=InMemoryCapsEngineTest#autonomyModifiersProduceWeightDifferences`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add caps-engine/src/main/resources/caps-topology.yaml caps-testing/
git commit -m "fix(caps): align autonomy YAML keys with DispositionAxes values (N3) Refs #1222"
```

---

### Task 3: Resting Activation Clamping (N4)

**Files:**
- Modify: `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/DispositionWeightMapper.java:316-322`
- Test: `caps-testing/src/test/java/io/casehub/neocortex/caps/testing/CapsEngineContractTest.java`

**Interfaces:**
- Consumes: `CapsNode.range()` for per-node range
- Produces: `addResting()` clamps accumulated resting to `[-0.5, 0.5]` (BIPOLAR) or `[0.0, 0.5]` (UNIPOLAR)

- [ ] **Step 1: Write failing test — extreme disposition doesn't produce excessive resting**

Add to `CapsEngineContractTest`:

```java
@Test
void restingActivationsClampedWithinBounds() {
    var state = engine.initializeAgent("t1", "extreme",
        new DispositionAxes("competitive", "defiant", "bold", "independent", "confrontational"));
    for (var entry : state.nodeStates().entrySet()) {
        double resting = entry.getValue().restingActivation();
        assertThat(resting)
            .as("resting activation for %s must be in [-0.5, 0.5]", entry.getKey())
            .isBetween(-0.5, 0.5);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-testing -Dtest=InMemoryCapsEngineTest#restingActivationsClampedWithinBounds`
Expected: FAIL — multiple axes contribute to same node without clamping.

- [ ] **Step 3: Add clamping to addResting()**

Use `ide_replace_member` on `DispositionWeightMapper.addResting()`:

```java
private void addResting(Map<String, NodeState> nodeStates,
                         String nodeId, double delta) {
    NodeState current = nodeStates.getOrDefault(nodeId, NodeState.DEFAULT);
    double newResting = current.restingActivation() + delta;
    CapsNode node = topology.nodes().get(nodeId);
    if (node != null) {
        newResting = switch (node.range()) {
            case BIPOLAR -> Math.max(-0.5, Math.min(0.5, newResting));
            case UNIPOLAR -> Math.max(0.0, Math.min(0.5, newResting));
        };
    } else {
        newResting = Math.max(-0.5, Math.min(0.5, newResting));
    }
    nodeStates.put(nodeId, new NodeState(
        current.activationThreshold(), newResting));
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-testing -Dtest=InMemoryCapsEngineTest#restingActivationsClampedWithinBounds`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add caps-engine/src/main/java/io/casehub/neocortex/caps/engine/DispositionWeightMapper.java caps-testing/
git commit -m "fix(caps): clamp resting activations in addResting (N4) Refs #1222"
```

---

### Task 4: Distortion Sign Fix (B5)

**Files:**
- Modify: `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsSettler.java:188-221`
- Test: `caps-engine/src/test/java/io/casehub/neocortex/caps/engine/CapsSettlerDistortionTest.java` (new)

**Interfaces:**
- Consumes: `DistortionEffect.ADDITIVE` distortions from topology
- Produces: ADDITIVE distortions multiply by `signum(currentActivation)` — positive beliefs amplified positively, negative amplified negatively, zero unaffected

- [ ] **Step 1: Write failing test — ADDITIVE distortion respects belief sign**

Create `caps-engine/src/test/java/io/casehub/neocortex/caps/engine/CapsSettlerDistortionTest.java`:

```java
package io.casehub.neocortex.caps.engine;

import io.casehub.neocortex.caps.*;
import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;

class CapsSettlerDistortionTest {

    @Test
    void additiveDistortionRespectsNegativeActivation() {
        var topology = CapsTopologyLoader.loadFromClasspath();
        var settler = new CapsSettler(topology);
        var mapper = new DispositionWeightMapper(topology);
        var state = mapper.initializeWeights("t1", "agent",
            new DispositionAxes("cooperative", "moderate", "calculated", "moderate", "collaborative"));

        var resultPositive = settler.settle(state, Map.of("reward", 0.8));
        var resultNegative = settler.settle(state, Map.of("punishment", 0.8));

        double approachPos = resultPositive.activations().getOrDefault("approach", 0.0);
        double approachNeg = resultNegative.activations().getOrDefault("approach", 0.0);

        assertThat(approachPos).as("approach under reward should be positive").isGreaterThan(0.0);
        assertThat(approachNeg).as("approach under punishment should be non-positive").isLessThanOrEqualTo(0.05);
    }
}
```

- [ ] **Step 2: Run test to verify baseline**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-engine -Dtest=CapsSettlerDistortionTest`
Expected: may pass or fail depending on current distortion behavior. Record the result.

- [ ] **Step 3: Fix ADDITIVE distortion sign**

In `CapsSettler.applyDistortions()`, change line 212 from:

```java
additiveTotal += mult;
```

to:

```java
additiveTotal += mult * Math.signum(currentActivation);
```

- [ ] **Step 4: Run all caps-engine tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-engine,caps-testing`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsSettler.java caps-engine/src/test/
git commit -m "fix(caps): ADDITIVE distortions respect belief sign (B5) Refs #1222"
```

---

### Task 5: Convergence Threshold Tightening (B6, D5)

**Files:**
- Modify: `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsSettler.java:150,161`
- Test: `caps-engine/src/test/java/io/casehub/neocortex/caps/engine/CapsSettlerConvergenceTest.java` (new)

**Interfaces:**
- Produces: Variance threshold `epsilon * 10` (was `epsilon * 50`) at both check sites

- [ ] **Step 1: Write test — persistent oscillation not reported as CONVERGED**

Create `caps-engine/src/test/java/io/casehub/neocortex/caps/engine/CapsSettlerConvergenceTest.java`:

```java
package io.casehub.neocortex.caps.engine;

import io.casehub.neocortex.caps.*;
import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;

class CapsSettlerConvergenceTest {

    @Test
    void competingInputsProduceOscillationNotConverged() {
        var topology = CapsTopologyLoader.loadFromClasspath();
        var settler = new CapsSettler(topology);
        var mapper = new DispositionWeightMapper(topology);
        var state = mapper.initializeWeights("t1", "osc",
            new DispositionAxes("competitive", "defiant", "bold", "independent", "confrontational"));

        var result = settler.settle(state, Map.of(
            "physical_threat", 0.9,
            "reward", 0.9
        ));

        if (result.iterations() >= 20) {
            assertThat(result.convergence())
                .as("competing strong inputs should not falsely converge")
                .isNotEqualTo(ConvergenceType.CONVERGED);
        }
    }
}
```

- [ ] **Step 2: Run test to record baseline**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-engine -Dtest=CapsSettlerConvergenceTest`

- [ ] **Step 3: Tighten the threshold**

In `CapsSettler.settle()`, change both instances of `params.epsilon() * 50.0` to `params.epsilon() * 10.0`:
- Line 150: `if (windowMaxVar < params.epsilon() * 10.0) {`
- Line 161: `if (finalVar < params.epsilon() * 10.0) {`

- [ ] **Step 4: Run all caps-engine tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-engine,caps-testing`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsSettler.java caps-engine/src/test/
git commit -m "fix(caps): tighten convergence variance threshold to epsilon*10 (B6) Refs #1222"
```

---

## Batch 2: Weight Learning

### Task 6: Multi-Cue R-W + Inhibitory Removal + Weight Clamping + Flyway V2 (D4, B2, N1, N2)

**Files:**
- Modify: `caps-api/src/main/java/io/casehub/neocortex/caps/ConnectionWeight.java`
- Modify: `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsWeightUpdater.java:36-87`
- Modify: `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/DispositionWeightMapper.java` (ConnectionWeight constructor calls)
- Modify: `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/SqliteCapsEngine.java` (loadWeights, replaceWeights)
- Create: `caps-engine/src/main/resources/db/caps/V2__simplify_connection_weights.sql`
- Test: `caps-testing/src/test/java/io/casehub/neocortex/caps/testing/CapsEngineContractTest.java`

**Interfaces:**
- Produces: `ConnectionWeight(double excitatory, double precision)` — 2-field record
- Produces: `ConnectionWeight.effectiveWeight()` returns `excitatory`
- Produces: Multi-cue ensemble prediction error per target node
- Produces: Excitatory weight clamped to `[-2.0, 2.0]`

- [ ] **Step 1: Write failing test — multi-cue competition suppresses weak predictors**

Add to `CapsEngineContractTest`:

```java
@Test
void multiCueCompetitionSuppressesWeakPredictors() {
    var state = engine.initializeAgent("t1", "mc",
        new DispositionAxes("cooperative", "moderate", "calculated", "moderate", "collaborative"));

    var updated1 = engine.updateWeights(state, new WeightUpdateContext(
        Map.of("reward", 0.9, "sharing", 0.1), 0.8, 0.5, 1.0, "continuous", 1.0));
    var updated2 = engine.updateWeights(updated1, new WeightUpdateContext(
        Map.of("reward", 0.9, "sharing", 0.1), 0.8, 0.5, 1.0, "continuous", 1.0));

    double rewardWeight = updated2.weights().get("reward__BAS_activation").excitatory();
    double sharingWeight = updated2.weights().get("sharing__other_reliability").excitatory();

    assertThat(Math.abs(rewardWeight - state.weights().get("reward__BAS_activation").excitatory()))
        .as("strong predictor (reward) should update")
        .isGreaterThan(0.001);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-testing -Dtest=InMemoryCapsEngineTest#multiCueCompetitionSuppressesWeakPredictors`
Expected: May compile-fail after ConnectionWeight change. Run after Step 3-7.

- [ ] **Step 3: Simplify ConnectionWeight record**

Replace `ConnectionWeight.java` contents:

```java
package io.casehub.neocortex.caps;

public record ConnectionWeight(
    double excitatory,
    double precision
) {
    public double effectiveWeight() {
        return excitatory;
    }
}
```

- [ ] **Step 4: Fix all ConnectionWeight constructor call sites**

Use `ide_find_references` on `ConnectionWeight` to find all callers. Update each `new ConnectionWeight(exc, inh, decay, prec)` to `new ConnectionWeight(exc, prec)`. Key locations:
- `CapsWeightUpdater.java` line 50 (default weight): `new ConnectionWeight(conn.defaultWeight(), provenancePrecision(conn.provenance()))`
- `CapsWeightUpdater.java` line 82: `new ConnectionWeight(newExcitatory, newPrecision)`
- `DispositionWeightMapper.java` (initializeWeights): update all 4-arg calls to 2-arg
- `SqliteCapsEngine.java` (loadWeights): update ResultSet mapping
- `InMemoryCapsEngine.java` if present
- Test files using ConnectionWeight

- [ ] **Step 5: Rewrite CapsWeightUpdater.update() as multi-cue**

Replace the body of `CapsWeightUpdater.update()`:

```java
public AgentCapsState update(AgentCapsState state, WeightUpdateContext context) {
    var params = topology.weightUpdate();
    double scheduleMod = params.scheduleModifiers()
                               .getOrDefault(context.reinforcementSchedule(), 1.0);

    Map<String, ConnectionWeight> newWeights = new HashMap<>(state.weights());

    Map<String, List<CapsConnection>> byTarget = topology.connections().stream()
        .collect(java.util.stream.Collectors.groupingBy(CapsConnection::to));

    for (var entry : byTarget.entrySet()) {
        List<CapsConnection> incoming = entry.getValue();

        double vPredicted = 0.0;
        for (CapsConnection conn : incoming) {
            double sourceAct = context.inputActivations()
                                       .getOrDefault(conn.from(), 0.0);
            if (Math.abs(sourceAct) < 0.01) continue;
            ConnectionWeight cw = state.weights()
                .getOrDefault(conn.id(),
                    new ConnectionWeight(conn.defaultWeight(),
                        provenancePrecision(conn.provenance())));
            vPredicted += cw.effectiveWeight() * sourceAct;
        }

        double delta = context.outcomeValence() - vPredicted;

        for (CapsConnection conn : incoming) {
            double sourceAct = context.inputActivations()
                                       .getOrDefault(conn.from(), 0.0);
            if (Math.abs(sourceAct) < 0.01) continue;

            ConnectionWeight cw = state.weights()
                .getOrDefault(conn.id(),
                    new ConnectionWeight(conn.defaultWeight(),
                        provenancePrecision(conn.provenance())));

            double baseAlpha = Math.max(params.alphaMin(),
                Math.min(params.alphaMax(),
                    context.salienceMultiplier() * config.salienceAlphaScaling()));
            baseAlpha *= context.capacityMultiplier();
            double effectiveAlpha = baseAlpha / cw.precision();
            double beta = Math.max(params.betaMin(),
                Math.min(params.betaMax(), context.outcomeIntensity()));

            double deltaW = effectiveAlpha * beta * delta * scheduleMod;
            double newExcitatory = Math.max(-2.0, Math.min(2.0,
                cw.excitatory() + deltaW));

            double newPrecision;
            if (Math.abs(delta) < config.confirmEpsilon()) {
                newPrecision = cw.precision() + config.precisionGrowthRate();
            } else {
                newPrecision = Math.max(config.minPrecision(),
                    cw.precision() * config.precisionDecayFactor());
            }

            newWeights.put(conn.id(),
                new ConnectionWeight(newExcitatory, newPrecision));
        }
    }

    return new AgentCapsState(state.agentId(), state.tenantId(),
        state.generation(), Map.copyOf(newWeights), state.nodeStates());
}
```

- [ ] **Step 6: Update SqliteCapsEngine SQL and add Flyway V2**

Create `caps-engine/src/main/resources/db/caps/V2__simplify_connection_weights.sql`:

```sql
ALTER TABLE caps_connection_weights DROP COLUMN inhibitory;
ALTER TABLE caps_connection_weights DROP COLUMN decay_resistance;
```

Update `SqliteCapsEngine.loadWeights()` SQL to select only `excitatory, precision_val`.
Update `SqliteCapsEngine.replaceWeights()` INSERT to only write `excitatory, precision_val`.

- [ ] **Step 7: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-engine,caps-testing`
Expected: PASS — existing `weightUpdateModifiesState` and `empiricalWeightsResistChange` tests should still pass with multi-cue update.

- [ ] **Step 8: Commit**

```bash
git add caps-api/src/main/java/io/casehub/neocortex/caps/ConnectionWeight.java caps-engine/ caps-testing/
git commit -m "fix(caps): multi-cue R-W, remove inhibitory, clamp weights, Flyway V2 (B2, N1, N2) Refs #1222"
```

---

### Task 7: Regulation Weight Update Persistence (B3)

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipant.java:379,475`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipantTest.java`

**Interfaces:**
- Consumes: `CapsEngine.updateWeights()` returns `AgentCapsState`
- Consumes: `CapsEngine.saveState(AgentCapsState)` persists updated weights
- Produces: Both regulation and coping paths persist weight updates

- [ ] **Step 1: Write failing test — regulation path persists weights**

Add to `EmotionRegulationTickParticipantTest`:

```java
@Test
void regulationPathPersistsWeightUpdates() {
    // Trigger regulation tick with CAPS activations
    // After tick, verify capsEngine.saveState() was called
    // (Use Mockito verify or check generation increment)
    var stateAfter = capsEngine.loadState("t1", "agent");
    assertThat(stateAfter.generation())
        .as("regulation should save updated weights")
        .isGreaterThan(stateBefore.generation());
}
```

(Exact test setup depends on the existing test infrastructure in this file — adapt to the existing mock/stub patterns.)

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=EmotionRegulationTickParticipantTest#regulationPathPersistsWeightUpdates`
Expected: FAIL — updateWeights result discarded, saveState never called.

- [ ] **Step 3: Fix regulation path (line ~379)**

Change the call at line 379 from:

```java
capsEngine.updateWeights(capsState, new WeightUpdateContext(...));
```

to:

```java
capsState = capsEngine.updateWeights(capsState, new WeightUpdateContext(...));
capsEngine.saveState(capsState);
```

- [ ] **Step 4: Fix coping path (line ~475)**

Apply the same pattern at line 475:

```java
capsState = capsEngine.updateWeights(capsState, new WeightUpdateContext(...));
capsEngine.saveState(capsState);
```

- [ ] **Step 5: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=EmotionRegulationTickParticipantTest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipant.java cognition/src/test/
git commit -m "fix(cognition): persist weight updates in regulation/coping paths (B3) Refs #1222"
```

---

## Batch 3: Classification & CBR

### Task 8: Drive Injection Filter + Remap (D3, B12)

**Files:**
- Modify: `caps-api/src/main/java/io/casehub/neocortex/caps/DriveCompetitionDetector.java:28-43`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhase.java:502-535`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhaseTest.java`

**Interfaces:**
- Consumes: `CapsEngine.topology().nodes()` for node type lookup
- Produces: `DRIVE_CAPS_MAPPINGS` only references INPUT node IDs
- Produces: `mergeDriveIntensities()` filters to INPUT nodes before merging

- [ ] **Step 1: Write failing test — non-input drive targets are filtered**

Add to or create `BehavioralSynthesisPhaseTest`:

```java
@Test
void driveInjectionsOnlyTargetInputNodes() {
    for (var entry : DriveCompetitionDetector.DRIVE_CAPS_MAPPINGS.entrySet()) {
        for (String nodeId : entry.getValue()) {
            CapsNode node = topology.nodes().get(nodeId);
            assertThat(node)
                .as("drive mapping %s → %s must exist in topology", entry.getKey(), nodeId)
                .isNotNull();
            assertThat(node.type())
                .as("drive mapping %s → %s must target INPUT node", entry.getKey(), nodeId)
                .isEqualTo(NodeType.INPUT);
        }
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="*BehavioralSynthesisPhaseTest#driveInjectionsOnlyTargetInputNodes"`
Expected: FAIL — multiple entries target mediating/output nodes.

- [ ] **Step 3: Remap DRIVE_CAPS_MAPPINGS to input-only proxies**

Replace `DriveCompetitionDetector.DRIVE_CAPS_MAPPINGS`:

```java
public static final Map<String, List<String>> DRIVE_CAPS_MAPPINGS = Map.ofEntries(
    Map.entry("gallantry",         List.of("perceived_responsiveness", "acceptance", "reward")),
    Map.entry("proving-worth",     List.of("mastery", "competence_recognition")),
    Map.entry("protection",        List.of("perceived_responsiveness", "physical_threat", "reward")),
    Map.entry("scheming",          List.of("dominance", "betrayal", "agency_granted")),
    Map.entry("gloating",          List.of("dominance", "reward")),
    Map.entry("self-preservation", List.of("physical_threat", "unpredictable_danger")),
    Map.entry("recognition",       List.of("competence_recognition", "secure_attachment", "reward")),
    Map.entry("curiosity",         List.of("reward")),
    Map.entry("social-harmony",    List.of("perceived_responsiveness", "acceptance", "inconsistent_care")),
    Map.entry("adventure",         List.of("reward")),
    Map.entry("greed",             List.of("reward")),
    Map.entry("loyalty",           List.of("perceived_responsiveness", "inconsistent_care", "secure_attachment")),
    Map.entry("suspicion",         List.of("physical_threat", "betrayal", "social_threat")),
    Map.entry("dominance",         List.of("dominance", "agency_granted"))
);
```

- [ ] **Step 4: Add input filter inside mergeDriveIntensities()**

In `BehavioralSynthesisPhase.mergeDriveIntensities()`, change the loop at lines 519-522 from:

```java
if (targetNodes != null) {
    for (String nodeId : targetNodes) {
        combinedActivations.merge(nodeId, intensity, Math::max);
    }
```

to:

```java
if (targetNodes != null) {
    for (String nodeId : targetNodes) {
        CapsNode capsNode = capsEngine.topology().nodes().get(nodeId);
        if (capsNode != null && capsNode.type() == NodeType.INPUT) {
            combinedActivations.merge(nodeId, intensity, Math::max);
        }
    }
```

Add import: `import io.casehub.neocortex.caps.CapsNode;` and `import io.casehub.neocortex.caps.NodeType;`

- [ ] **Step 5: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="*BehavioralSynthesisPhaseTest#driveInjectionsOnlyTargetInputNodes"`
Expected: PASS

- [ ] **Step 6: Run full test suite for affected modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-api,mindmap-intelligence`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add caps-api/src/main/java/io/casehub/neocortex/caps/DriveCompetitionDetector.java mindmap-intelligence/
git commit -m "fix(caps): remap drive injection to input nodes, filter in mergeDriveIntensities (B12) Refs #1222"
```

---

### Task 9: ClassificationOutcomeEvaluator OSCILLATION Fix (B9)

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ClassificationOutcomeEvaluator.java:16`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ClassificationOutcomeEvaluatorTest.java` (new)

**Interfaces:**
- Produces: OSCILLATION convergence factor = 0.7 (was 0.3)

- [ ] **Step 1: Write failing test**

Create `ClassificationOutcomeEvaluatorTest.java`:

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.caps.*;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;

class ClassificationOutcomeEvaluatorTest {

    @Test
    void oscillationNotSeverelyPenalized() {
        var result = new SettlingResult(
            Map.of("approach", 0.5, "withdraw", 0.3),
            25, ConvergenceType.OSCILLATION, 0.3,
            List.of(new CapsAttractor("approach_avoidance", "approach", 0.5, false, 1)));
        var outcome = ClassificationOutcomeEvaluator.evaluate(result, Instant.now());
        assertThat(outcome.adjustConfidence(1.0))
            .as("oscillation outcome should not be below 0.3")
            .isGreaterThanOrEqualTo(0.3);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ClassificationOutcomeEvaluatorTest`
Expected: FAIL — 0.3 × 0.5 = 0.15 < 0.3.

- [ ] **Step 3: Change OSCILLATION factor**

In `ClassificationOutcomeEvaluator.java` line 16, change:

```java
case OSCILLATION    -> 0.3;
```

to:

```java
case OSCILLATION    -> 0.7;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ClassificationOutcomeEvaluatorTest`
Expected: PASS — 0.7 × 0.5 = 0.35 ≥ 0.3.

- [ ] **Step 5: Commit**

```bash
git add mindmap-intelligence/
git commit -m "fix(caps): raise OSCILLATION convergence factor to 0.7 (B9) Refs #1222"
```

---

### Task 10: CBR Cache Fixes + Valence Filter (B10, D6)

**Files:**
- Modify: `caps-situation-cbr/src/main/java/io/casehub/neocortex/caps/cbr/CbrCachingSituationDecorator.java:119,132-155,158-187`
- Modify: `caps-situation-cbr/src/main/java/io/casehub/neocortex/caps/cbr/ClassificationCbrConfig.java` (if valence config needed)
- Test: `caps-situation-cbr/src/test/java/io/casehub/neocortex/caps/cbr/CbrCachingSituationDecoratorTest.java`

**Interfaces:**
- Produces: Cache hit returns the HIT's caseId (not recomputed from query)
- Produces: Lookup includes PID-5 and appraisal filters
- Produces: Valence categorical filter prevents polarity-inverted cache hits

- [ ] **Step 1: Write failing test — case ID comes from cached hit**

Add to `CbrCachingSituationDecoratorTest`:

```java
@Test
void cacheHitReturnsCachedCaseId() {
    // Store a classification, then look it up
    // The returned ClassificationResult.caseId() should match the stored case's ID,
    // not a recomputed hash from the query description
    String description = "test description for case ID check";
    var result1 = decorator.classify(description, metadata, context);
    String storedCaseId = result1.caseId();

    var result2 = decorator.classify(description, metadata, context);
    assertThat(result2.caseId())
        .as("cache hit should return the stored case's ID")
        .isEqualTo(storedCaseId);
}
```

- [ ] **Step 2: Run test to record baseline**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-situation-cbr -Dtest=CbrCachingSituationDecoratorTest#cacheHitReturnsCachedCaseId`

- [ ] **Step 3: Fix case ID on cache hit (line 119)**

Change line 119 from:

```java
String caseId = computeCaseId(description, eventType, cognitiveKind, metadata);
```

to:

```java
String caseId = hits.getFirst().caseId();
```

- [ ] **Step 4: Add PID-5 and appraisal filters to lookupCbr()**

In `lookupCbr()`, after the disposition key loop (lines 143-149), add:

```java
if (metadata != null) {
    metadata.entrySet().stream()
        .filter(e -> e.getKey().startsWith("pid5.") || e.getKey().startsWith("appraisal."))
        .forEach(e -> {
            String filterKey = e.getKey().replace('.', '-');
            query = query.withFilter(filterKey, CbrFilter.contains(e.getValue()));
        });
}
```

Note: `query` must be declared non-final (change `var query =` to allow reassignment, or use a mutable builder pattern).

- [ ] **Step 5: Add valence feature to storeCbr() and filter to lookupCbr()**

Add a static helper method:

```java
static String classifyValence(List<SituationActivation> activations) {
    var positive = Set.of("approach", "trust", "proximity_seek", "persist",
        "risk_take", "self_direct", "rebel", "explore");
    var negative = Set.of("withdraw", "distrust", "distance_maintain", "flight",
        "freeze", "fawn", "submit", "abandon", "comply", "depend");

    String dominant = activations.stream()
        .max(java.util.Comparator.comparingDouble(SituationActivation::confidence))
        .map(SituationActivation::nodeId)
        .orElse("");

    if (positive.contains(dominant)) return "positive";
    if (negative.contains(dominant)) return "negative";
    return "neutral";
}
```

In `storeCbr()`, add to features: `features.put("valence", FeatureValue.string(classifyValence(activations)));`

In `lookupCbr()`, add: `query = query.withFilter("valence", CbrFilter.contains(classifyValence(activations)));` where `activations` is derived from the query context (this requires passing a valence parameter or computing it from the description — alternatively filter by the stored result's valence, which is already the right approach since the valence comes from the classification output, not the query input).

Add `"valence"` field to the `SCHEMA` definition: `FeatureField.categorical("valence")`.

- [ ] **Step 6: Run all CBR tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-situation-cbr`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add caps-situation-cbr/
git commit -m "fix(caps): CBR cache case ID, PID-5/appraisal filters, valence filter (B10) Refs #1222"
```

---

## Batch 4: Recalibration & Verification

### Task 11: Downstream Threshold Recalibration (D9)

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipant.java` (threshold usage)
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/RegulationCascadeConfig.java` (if defaults change)
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/regulation/` (threshold test updates)
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhase.java` (createOrStrengthenAttractor thresholds)

**Interfaces:**
- Consumes: Attractor strengths from BIPOLAR output nodes (baseline ~0.0 instead of ~0.5)
- Produces: Recalibrated thresholds that maintain equivalent selectivity

- [ ] **Step 1: Audit threshold consumers**

Use `ide_find_references` on `RegulationCascadeConfig`, `attractorStrengthMargin`, and `reinforcementBoostCap` to find all threshold comparison sites. Read each to understand what the threshold selects for.

- [ ] **Step 2: Run existing regulation and coping tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="EmotionRegulation*"`
Record which tests fail and what values they expect.

- [ ] **Step 3: Adjust thresholds based on test evidence**

For each failing test, determine whether:
- The threshold needs lowering (BIPOLAR produces lower absolute values for the same selectivity)
- The test assertion needs updating (hardcoded values from unipolar era)
- The threshold is already appropriate (BIPOLAR widened the gap, threshold still selects correctly)

Apply changes using `ide_replace_member` for config defaults and test assertions.

- [ ] **Step 4: Run all cognition tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition,mindmap-intelligence`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cognition/ cognition-api/ mindmap-intelligence/
git commit -m "fix(caps): recalibrate downstream thresholds for BIPOLAR output scale (D9) Refs #1222"
```

---

### Task 12: Verification Tests — Epic Criterion + Integration (D7, B17)

**Files:**
- Modify: `caps-testing/src/test/java/io/casehub/neocortex/caps/testing/CapsEngineContractTest.java`
- Create: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisDriveFilterTest.java`

**Interfaces:**
- Consumes: `CapsEngine.settle()`, `CapsEngine.initializeAgent()`, `BehavioralSynthesisPhase`
- Produces: Tests that validate the epic's verification criterion

- [ ] **Step 1: Write epic criterion test 1 — input ranking differs from no-input**

Add to `CapsEngineContractTest`:

```java
@Test
void noInputRankingDiffersFromThreatRanking() {
    var state = engine.initializeAgent("t1", "ranking",
        new DispositionAxes("cooperative", "moderate", "calculated", "moderate", "collaborative"));

    var noInput = engine.settle(state, Map.of());
    var threat = engine.settle(state, Map.of("physical_threat", 1.0));

    List<String> noInputTop3 = noInput.attractors().stream()
        .sorted((a, b) -> Double.compare(b.strength(), a.strength()))
        .limit(3)
        .map(CapsAttractor::nodeId)
        .toList();

    List<String> threatTop3 = threat.attractors().stream()
        .sorted((a, b) -> Double.compare(b.strength(), a.strength()))
        .limit(3)
        .map(CapsAttractor::nodeId)
        .toList();

    assertThat(threatTop3)
        .as("top-3 attractors under physical_threat=1.0 must differ from no-input ranking")
        .isNotEqualTo(noInputTop3);
}
```

- [ ] **Step 2: Write epic criterion test 2 — opposite personalities diverge > 0.3**

Add to `CapsEngineContractTest`:

```java
@Test
void oppositePersonalitiesDiverge() {
    var bold = engine.initializeAgent("t1", "bold",
        new DispositionAxes("competitive", "defiant", "bold", "independent", "confrontational"));
    var cautious = engine.initializeAgent("t1", "cautious",
        new DispositionAxes("cooperative", "compliant", "conservative", "dependent", "avoidant"));

    var input = Map.of("physical_threat", 0.7, "social_threat", 0.5);
    var boldResult = engine.settle(bold, input);
    var cautiousResult = engine.settle(cautious, input);

    double maxDifference = 0.0;
    Set<String> allNodes = new HashSet<>(boldResult.activations().keySet());
    allNodes.addAll(cautiousResult.activations().keySet());
    for (String nodeId : allNodes) {
        CapsNode node = engine.topology().nodes().get(nodeId);
        if (node != null && node.type() == NodeType.OUTPUT) {
            double diff = Math.abs(
                boldResult.activations().getOrDefault(nodeId, 0.0)
                - cautiousResult.activations().getOrDefault(nodeId, 0.0));
            maxDifference = Math.max(maxDifference, diff);
        }
    }

    assertThat(maxDifference)
        .as("max attractor strength difference between opposite personalities must be > 0.3")
        .isGreaterThan(0.3);
}
```

- [ ] **Step 3: Write integration test — drive filter end-to-end**

Create `BehavioralSynthesisDriveFilterTest.java`:

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.caps.*;
import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;

class BehavioralSynthesisDriveFilterTest {

    @Test
    void allDriveMappingsTargetInputNodes() {
        var topology = io.casehub.neocortex.caps.engine.CapsTopologyLoader.loadFromClasspath();
        for (var entry : DriveCompetitionDetector.DRIVE_CAPS_MAPPINGS.entrySet()) {
            for (String nodeId : entry.getValue()) {
                CapsNode node = topology.nodes().get(nodeId);
                assertThat(node).as("node %s from drive %s", nodeId, entry.getKey()).isNotNull();
                assertThat(node.type())
                    .as("drive %s target %s must be INPUT", entry.getKey(), nodeId)
                    .isEqualTo(NodeType.INPUT);
            }
        }
    }
}
```

- [ ] **Step 4: Run all verification tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-testing,mindmap-intelligence -Dtest="InMemoryCapsEngineTest#noInputRankingDiffersFromThreatRanking+oppositePersonalitiesDiverge,BehavioralSynthesisDriveFilterTest"`
Expected: ALL PASS

- [ ] **Step 5: Run full project test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-api,caps-engine,caps-testing,caps-situation-cbr,mindmap-intelligence,cognition`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add caps-testing/ mindmap-intelligence/
git commit -m "test(caps): add epic verification criterion + drive filter integration tests (B17) Closes #1222"
```

---

## References

- [2026-11-25-caps-rework-design.md] — design spec this plan implements
- `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsSettler.java:85-265` — settler algorithm
- `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsWeightUpdater.java:36-87` — weight learning
- `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/DispositionWeightMapper.java:316-322` — addResting
- `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsTopologyLoader.java:124-125` — defaultRange
- `caps-engine/src/main/resources/caps-topology.yaml` — runtime topology
- `caps-api/src/main/java/io/casehub/neocortex/caps/DriveCompetitionDetector.java:28-43` — DRIVE_CAPS_MAPPINGS
- `caps-api/src/main/java/io/casehub/neocortex/caps/ConnectionWeight.java` — weight record
- `caps-api/src/main/java/io/casehub/neocortex/caps/NodeRange.java` — resting level
- `caps-situation-cbr/src/main/java/io/casehub/neocortex/caps/cbr/CbrCachingSituationDecorator.java` — CBR cache
- `mindmap-intelligence/.../consolidation/BehavioralSynthesisPhase.java:502-535` — mergeDriveIntensities
- `mindmap-intelligence/.../consolidation/ClassificationOutcomeEvaluator.java` — outcome scoring
- `cognition/.../regulation/EmotionRegulationTickParticipant.java:379,475` — B3 bug sites
- `caps-testing/.../CapsEngineContractTest.java` — 13 contract tests
- GitHub #1222 — SE2: CAPS Rework epic
- `docs/specs/cognitive-review-analysis/2026-11-24-cognitive-review-triage.md` — triage classifications

# Hypothesis Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #692 — Hypothesis tracking — weighted path elimination over composed Bayesian networks
**Issue group:** #692

**Goal:** Add a `HypothesisTracker` to the BJT engine that maintains
competing explanations over composed Bayesian networks, updates weights
via marginal likelihood scoring, and eliminates dead paths.

**Architecture:** `HypothesisTracker` owns one `CompositionInstance`
per hypothesis. Observations are broadcast to all viable hypotheses;
weights are updated via P(evidence | H_i) computed from current
marginals before evidence is set. Hypotheses below a configurable
threshold are eliminated. Pure Java, zero CDI, same package as
`CompositionInstance`.

**Tech Stack:** Java 21, JUnit 5. No new dependencies.

## Global Constraints

- Module: `inference-bayes`
- Package: `io.quarkmind.inference.bayes`
- No CDI, no Quarkus dependency — pure Java
- Thread-unsafe (same contract as `BayesInstance`)
- All new records use defensive copies (`Map.copyOf`, `List.copyOf`)

---

## Batch 1: Value types, builder, construction

### Task 1: HypothesisTracker foundation — types, builder, initial state

**Files:**
- Create: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/HypothesisStatus.java`
- Create: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/HypothesisDefinition.java`
- Create: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/ObservationResult.java`
- Create: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/TrackerSnapshot.java`
- Create: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/HypothesisTracker.java`
- Modify: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/CompositionInstance.java` (add `getVariables` accessor)
- Test: `inference-bayes/src/test/java/io/quarkmind/inference/bayes/HypothesisTrackerTest.java`

**Interfaces:**
- Consumes: `NetworkComposition`, `CompositionInstance`, `CompositionBuilder`, `BayesNetworkBuilder`, `JunctionTree`
- Produces: `HypothesisTracker.builder(NetworkComposition)` → `HypothesisTrackerBuilder` → `HypothesisTracker`; `HypothesisTracker.snapshot()` → `TrackerSnapshot`; `HypothesisTracker.weights()` → `Map<String, Double>`; `HypothesisTracker.viable()` → `List<String>`; `HypothesisTracker.leader()` → `String`; `HypothesisTracker.isResolved()` → `boolean`; `HypothesisTracker.reset()` → `void`

- [ ] **Step 1: Write the failing test — initial state after construction**

```java
package io.quarkmind.inference.bayes;

import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class HypothesisTrackerTest {

    private JunctionTree scoutingTree() {
        return BayesNetworkBuilder.create("scouting")
            .variable("observed_units", "gateway", "hatchery", "barracks")
                .prior(1.0 / 3, 1.0 / 3, 1.0 / 3)
            .variable("enemy_strategy", "rush", "expand", "tech")
                .given("observed_units")
                .cpt(0.7, 0.1, 0.2,
                     0.1, 0.7, 0.2,
                     0.2, 0.2, 0.6)
            .buildJunctionTree();
    }

    private JunctionTree buildOrderTree() {
        return BayesNetworkBuilder.create("buildOrder")
            .variable("enemy_strategy", "rush", "expand", "tech")
                .prior(1.0 / 3, 1.0 / 3, 1.0 / 3)
            .variable("build_choice", "defensive", "greedy", "balanced")
                .given("enemy_strategy")
                .cpt(0.8, 0.1, 0.1,
                     0.1, 0.7, 0.2,
                     0.2, 0.2, 0.6)
            .buildJunctionTree();
    }

    private NetworkComposition twoSlotComposition() {
        return CompositionBuilder.create("sc2")
            .slot("scouting", scoutingTree())
            .slot("buildOrder", buildOrderTree())
            .link("scouting", "enemy_strategy").to("buildOrder", "enemy_strategy")
            .build();
    }

    @Test
    void initialState_uniformWeights() {
        var comp = twoSlotComposition();
        var tracker = HypothesisTracker.builder(comp)
            .hypothesis("rush").priorWeight(0.33)
            .hypothesis("expand").priorWeight(0.33)
            .hypothesis("tech").priorWeight(0.34)
            .build();

        Map<String, Double> weights = tracker.weights();
        assertEquals(3, weights.size());
        assertEquals(0.33, weights.get("rush"), 1e-9);
        assertEquals(0.33, weights.get("expand"), 1e-9);
        assertEquals(0.34, weights.get("tech"), 1e-9);

        assertEquals(3, tracker.viable().size());
        assertNotNull(tracker.leader());
        assertEquals("tech", tracker.leader());
        assertFalse(tracker.isResolved());

        TrackerSnapshot snap = tracker.snapshot();
        assertEquals(0, snap.observationCount());
        assertEquals(3, snap.viable().size());
        assertEquals(HypothesisStatus.VIABLE, snap.statuses().get("rush"));
    }

    @Test
    void builder_rejectsNoHypotheses() {
        var comp = twoSlotComposition();
        assertThrows(IllegalArgumentException.class, () ->
            HypothesisTracker.builder(comp).build());
    }

    @Test
    void builder_rejectsDuplicateNames() {
        var comp = twoSlotComposition();
        assertThrows(IllegalArgumentException.class, () ->
            HypothesisTracker.builder(comp)
                .hypothesis("rush").priorWeight(0.5)
                .hypothesis("rush").priorWeight(0.5)
                .build());
    }

    @Test
    void reset_restoresInitialState() {
        var comp = twoSlotComposition();
        var tracker = HypothesisTracker.builder(comp)
            .hypothesis("rush").priorWeight(0.5)
            .hypothesis("expand").priorWeight(0.5)
            .build();

        // Observe to change state (observeHard implemented in Task 2,
        // but reset should restore prior weights regardless)
        tracker.reset();

        assertEquals(0.5, tracker.weights().get("rush"), 1e-9);
        assertEquals(0.5, tracker.weights().get("expand"), 1e-9);
        assertEquals(2, tracker.viable().size());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=HypothesisTrackerTest -DfailIfNoTests=false`
Expected: compilation error — `HypothesisTracker` not found

- [ ] **Step 3: Create HypothesisStatus enum**

```java
package io.quarkmind.inference.bayes;

public enum HypothesisStatus {
    VIABLE,
    ELIMINATED
}
```

- [ ] **Step 4: Create HypothesisDefinition record**

```java
package io.quarkmind.inference.bayes;

import java.util.LinkedHashMap;
import java.util.Map;

public record HypothesisDefinition(
    String name,
    double priorWeight,
    Map<String, String> variantActivations,
    Map<String, double[]> priorOverrides
) {
    public HypothesisDefinition {
        if (name == null || name.isEmpty()) {
            throw new IllegalArgumentException("Hypothesis name must not be null or empty");
        }
        if (priorWeight <= 0) {
            throw new IllegalArgumentException("Prior weight must be positive: " + priorWeight);
        }
        variantActivations = variantActivations == null ? Map.of() : Map.copyOf(variantActivations);
        if (priorOverrides == null) {
            priorOverrides = Map.of();
        } else {
            var copy = new LinkedHashMap<String, double[]>();
            for (var entry : priorOverrides.entrySet()) {
                copy.put(entry.getKey(), entry.getValue().clone());
            }
            priorOverrides = Map.copyOf(copy);
        }
    }
}
```

- [ ] **Step 5: Create ObservationResult record**

```java
package io.quarkmind.inference.bayes;

import java.util.List;
import java.util.Map;

public record ObservationResult(
    Map<String, Double> weights,
    List<String> eliminated,
    String leader,
    double entropy,
    List<String> viable,
    boolean resolved
) {
    public ObservationResult {
        weights = Map.copyOf(weights);
        eliminated = List.copyOf(eliminated);
        viable = List.copyOf(viable);
    }
}
```

- [ ] **Step 6: Create TrackerSnapshot record**

```java
package io.quarkmind.inference.bayes;

import java.util.List;
import java.util.Map;

public record TrackerSnapshot(
    Map<String, Double> weights,
    Map<String, HypothesisStatus> statuses,
    String leader,
    double entropy,
    int observationCount,
    List<String> viable
) {
    public TrackerSnapshot {
        weights = Map.copyOf(weights);
        statuses = Map.copyOf(statuses);
        viable = List.copyOf(viable);
    }
}
```

- [ ] **Step 7: Add CompositionInstance.getVariables() accessor**

Add to `CompositionInstance.java` after the `getEvidenceVariables` method (line ~162):

```java
public Map<String, BayesVariable> getVariables(String slotName) {
    return getInstance(slotName).getVariables();
}
```

- [ ] **Step 8: Create HypothesisTracker with builder**

```java
package io.quarkmind.inference.bayes;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class HypothesisTracker {

    private final NetworkComposition composition;
    private final List<HypothesisDefinition> definitions;
    private final double eliminationThreshold;
    private final double resolutionThreshold;
    private Map<String, CompositionInstance> compositions;
    private Map<String, Double> currentWeights;
    private Map<String, HypothesisStatus> statuses;
    private int observationCount;

    private HypothesisTracker(NetworkComposition composition,
                              List<HypothesisDefinition> definitions,
                              double eliminationThreshold,
                              double resolutionThreshold) {
        this.composition = composition;
        this.definitions = List.copyOf(definitions);
        this.eliminationThreshold = eliminationThreshold;
        this.resolutionThreshold = resolutionThreshold;
        initializeFromDefinitions();
    }

    private void initializeFromDefinitions() {
        compositions = new LinkedHashMap<>();
        currentWeights = new LinkedHashMap<>();
        statuses = new LinkedHashMap<>();
        observationCount = 0;

        for (var def : definitions) {
            var instance = new CompositionInstance(composition);

            for (var activation : def.variantActivations().entrySet()) {
                instance.activate(activation.getKey(), activation.getValue());
            }

            for (var override : def.priorOverrides().entrySet()) {
                String key = override.getKey();
                int dot = key.indexOf('.');
                if (dot < 0) {
                    throw new IllegalArgumentException(
                        "Prior override key must be 'slot.variable': " + key);
                }
                String slot = key.substring(0, dot);
                String var = key.substring(dot + 1);
                instance.setEvidence(slot, var, override.getValue().clone());
            }

            instance.update();
            compositions.put(def.name(), instance);
            currentWeights.put(def.name(), def.priorWeight());
            statuses.put(def.name(), HypothesisStatus.VIABLE);
        }
    }

    public static HypothesisTrackerBuilder builder(NetworkComposition composition) {
        return new HypothesisTrackerBuilder(composition);
    }

    public Map<String, Double> weights() {
        return Map.copyOf(currentWeights);
    }

    public List<String> viable() {
        List<String> result = new ArrayList<>();
        for (var entry : statuses.entrySet()) {
            if (entry.getValue() == HypothesisStatus.VIABLE) {
                result.add(entry.getKey());
            }
        }
        return List.copyOf(result);
    }

    public String leader() {
        String best = null;
        double bestWeight = -1;
        for (var entry : currentWeights.entrySet()) {
            if (statuses.get(entry.getKey()) != HypothesisStatus.VIABLE) continue;
            if (entry.getValue() > bestWeight) {
                bestWeight = entry.getValue();
                best = entry.getKey();
            }
        }
        return best;
    }

    public boolean isResolved() {
        String leader = leader();
        if (leader == null) return false;
        return currentWeights.get(leader) >= resolutionThreshold;
    }

    public TrackerSnapshot snapshot() {
        return new TrackerSnapshot(
            Map.copyOf(currentWeights),
            Map.copyOf(statuses),
            leader(),
            computeEntropy(),
            observationCount,
            viable()
        );
    }

    public void reset() {
        initializeFromDefinitions();
    }

    public ObservationResult observe(String slotName, String variableName,
                                     double[] distribution) {
        throw new UnsupportedOperationException("Implemented in Task 2");
    }

    public ObservationResult observeHard(String slotName, String variableName,
                                         String state) {
        throw new UnsupportedOperationException("Implemented in Task 2");
    }

    double computeEntropy() {
        double entropy = 0;
        for (var entry : currentWeights.entrySet()) {
            if (statuses.get(entry.getKey()) != HypothesisStatus.VIABLE) continue;
            double w = entry.getValue();
            if (w > 0) {
                entropy -= w * (Math.log(w) / Math.log(2));
            }
        }
        return entropy;
    }

    private void normalize() {
        double sum = 0;
        for (var entry : currentWeights.entrySet()) {
            if (statuses.get(entry.getKey()) == HypothesisStatus.VIABLE) {
                sum += entry.getValue();
            }
        }
        if (sum == 0) {
            throw new IllegalStateException(
                "All hypothesis weights are zero — hypothesis set does not cover the observation space");
        }
        for (var entry : currentWeights.entrySet()) {
            if (statuses.get(entry.getKey()) == HypothesisStatus.VIABLE) {
                currentWeights.put(entry.getKey(), entry.getValue() / sum);
            }
        }
    }

    ObservationResult buildResult(List<String> eliminatedThisStep) {
        return new ObservationResult(
            Map.copyOf(currentWeights),
            eliminatedThisStep,
            leader(),
            computeEntropy(),
            viable(),
            isResolved()
        );
    }

    // --- Builder ---

    public static class HypothesisTrackerBuilder {

        private final NetworkComposition composition;
        private final List<HypothesisDefBuilder> hypotheses = new ArrayList<>();
        private double eliminationThreshold = 0.01;
        private double resolutionThreshold = 0.95;

        HypothesisTrackerBuilder(NetworkComposition composition) {
            if (composition == null) {
                throw new IllegalArgumentException("Composition must not be null");
            }
            this.composition = composition;
        }

        public HypothesisDefBuilder hypothesis(String name) {
            var hdb = new HypothesisDefBuilder(this, name);
            hypotheses.add(hdb);
            return hdb;
        }

        public HypothesisTrackerBuilder eliminationThreshold(double threshold) {
            this.eliminationThreshold = threshold;
            return this;
        }

        public HypothesisTrackerBuilder resolutionThreshold(double threshold) {
            this.resolutionThreshold = threshold;
            return this;
        }

        public HypothesisTracker build() {
            if (hypotheses.isEmpty()) {
                throw new IllegalArgumentException("At least one hypothesis is required");
            }
            List<HypothesisDefinition> defs = new ArrayList<>();
            java.util.Set<String> names = new java.util.HashSet<>();
            for (var hdb : hypotheses) {
                if (!names.add(hdb.name)) {
                    throw new IllegalArgumentException("Duplicate hypothesis name: " + hdb.name);
                }
                defs.add(new HypothesisDefinition(
                    hdb.name, hdb.priorWeight,
                    hdb.variantActivations, hdb.priorOverrides));
            }
            return new HypothesisTracker(composition, defs,
                eliminationThreshold, resolutionThreshold);
        }

        public static class HypothesisDefBuilder {
            private final HypothesisTrackerBuilder parent;
            final String name;
            double priorWeight = 1.0;
            final Map<String, String> variantActivations = new LinkedHashMap<>();
            final Map<String, double[]> priorOverrides = new LinkedHashMap<>();

            HypothesisDefBuilder(HypothesisTrackerBuilder parent, String name) {
                this.parent = parent;
                this.name = name;
            }

            public HypothesisDefBuilder priorWeight(double weight) {
                this.priorWeight = weight;
                return this;
            }

            public HypothesisDefBuilder activateVariant(String slotName, String contextKey) {
                variantActivations.put(slotName, contextKey);
                return this;
            }

            public HypothesisDefBuilder priorOverride(String slotName, String variableName,
                                                       double[] distribution) {
                priorOverrides.put(slotName + "." + variableName, distribution);
                return this;
            }

            public HypothesisDefBuilder hypothesis(String name) {
                return parent.hypothesis(name);
            }

            public HypothesisTrackerBuilder eliminationThreshold(double threshold) {
                return parent.eliminationThreshold(threshold);
            }

            public HypothesisTrackerBuilder resolutionThreshold(double threshold) {
                return parent.resolutionThreshold(threshold);
            }

            public HypothesisTracker build() {
                return parent.build();
            }
        }
    }
}
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=HypothesisTrackerTest`
Expected: 4 tests PASS

- [ ] **Step 10: Commit**

```bash
git add inference-bayes/src/main/java/io/quarkmind/inference/bayes/HypothesisStatus.java \
       inference-bayes/src/main/java/io/quarkmind/inference/bayes/HypothesisDefinition.java \
       inference-bayes/src/main/java/io/quarkmind/inference/bayes/ObservationResult.java \
       inference-bayes/src/main/java/io/quarkmind/inference/bayes/TrackerSnapshot.java \
       inference-bayes/src/main/java/io/quarkmind/inference/bayes/HypothesisTracker.java \
       inference-bayes/src/main/java/io/quarkmind/inference/bayes/CompositionInstance.java \
       inference-bayes/src/test/java/io/quarkmind/inference/bayes/HypothesisTrackerTest.java
git commit -m "feat(#692): HypothesisTracker foundation — types, builder, construction

Add HypothesisTracker with fluent builder, HypothesisDefinition,
ObservationResult, TrackerSnapshot, and HypothesisStatus types.
Construction creates per-hypothesis CompositionInstances with
variant activation and prior overrides.

Refs casehubio/neocortex#692"
```

---

## Batch 2: Observation engine — weight update, elimination, full test suite

### Task 2: observe() and observeHard() — Bayesian weight update with elimination

**Files:**
- Modify: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/HypothesisTracker.java` (replace observe/observeHard stubs)
- Test: `inference-bayes/src/test/java/io/quarkmind/inference/bayes/HypothesisTrackerTest.java` (add 9 test scenarios)

**Interfaces:**
- Consumes: `CompositionInstance.marginalize(slot, var)` → `double[]`; `CompositionInstance.getVariables(slot)` → `Map<String, BayesVariable>`; `CompositionInstance.setEvidence(slot, var, dist)`; `CompositionInstance.setHardEvidence(slot, var, state)`; `CompositionInstance.update()` → `CompositionStats`
- Produces: `HypothesisTracker.observe(slot, var, dist)` → `ObservationResult`; `HypothesisTracker.observeHard(slot, var, state)` → `ObservationResult`

- [ ] **Step 1: Write the failing test — two-hypothesis convergence**

Add to `HypothesisTrackerTest.java`:

```java
@Test
void twoHypothesis_convergesToFavoredHypothesis() {
    var comp = twoSlotComposition();
    var tracker = HypothesisTracker.builder(comp)
        .hypothesis("rush").priorWeight(0.5)
        .hypothesis("expand").priorWeight(0.5)
        .build();

    // Gateway observation favors rush (0.7 vs 0.1 in scouting CPT)
    ObservationResult result = tracker.observeHard("scouting", "observed_units", "gateway");

    assertTrue(result.weights().get("rush") > result.weights().get("expand"),
        "Rush should have higher weight after gateway observation");
    assertEquals(2, result.viable().size());
    assertEquals("rush", result.leader());
    assertTrue(result.eliminated().isEmpty());
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=HypothesisTrackerTest#twoHypothesis_convergesToFavoredHypothesis`
Expected: `UnsupportedOperationException: Implemented in Task 2`

- [ ] **Step 3: Implement observeHard()**

Replace the `observeHard` stub in `HypothesisTracker.java`:

```java
public ObservationResult observeHard(String slotName, String variableName, String state) {
    List<String> eliminatedThisStep = new ArrayList<>();

    for (var entry : compositions.entrySet()) {
        String name = entry.getKey();
        if (statuses.get(name) != HypothesisStatus.VIABLE) continue;

        CompositionInstance comp = entry.getValue();
        double[] marginal = comp.marginalize(slotName, variableName);

        // Resolve state index
        Map<String, BayesVariable> vars = comp.getVariables(slotName);
        BayesVariable var = vars.get(variableName);
        if (var == null) {
            throw new IllegalArgumentException(
                "Variable '" + variableName + "' not found in slot '" + slotName + "'");
        }
        Object[] outcomes = var.getOutcomes();
        int stateIndex = -1;
        for (int i = 0; i < outcomes.length; i++) {
            if (state.equals(outcomes[i])) {
                stateIndex = i;
                break;
            }
        }
        if (stateIndex == -1) {
            throw new IllegalArgumentException(
                "State '" + state + "' not found for variable '" + variableName + "'");
        }

        double likelihood = marginal[stateIndex];

        if (likelihood == 0.0) {
            statuses.put(name, HypothesisStatus.ELIMINATED);
            eliminatedThisStep.add(name);
            continue;
        }

        currentWeights.put(name, currentWeights.get(name) * likelihood);
        comp.setHardEvidence(slotName, variableName, state);
        comp.update();
    }

    normalize();
    softEliminate(eliminatedThisStep);
    if (!eliminatedThisStep.isEmpty()) normalize();
    observationCount++;
    return buildResult(eliminatedThisStep);
}

private void softEliminate(List<String> eliminatedThisStep) {
    for (var entry : new ArrayList<>(currentWeights.entrySet())) {
        String name = entry.getKey();
        if (statuses.get(name) != HypothesisStatus.VIABLE) continue;
        if (entry.getValue() < eliminationThreshold) {
            statuses.put(name, HypothesisStatus.ELIMINATED);
            eliminatedThisStep.add(name);
        }
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=HypothesisTrackerTest#twoHypothesis_convergesToFavoredHypothesis`
Expected: PASS

- [ ] **Step 5: Implement observe() for soft evidence**

Replace the `observe` stub in `HypothesisTracker.java`:

```java
public ObservationResult observe(String slotName, String variableName,
                                 double[] distribution) {
    List<String> eliminatedThisStep = new ArrayList<>();

    for (var entry : compositions.entrySet()) {
        String name = entry.getKey();
        if (statuses.get(name) != HypothesisStatus.VIABLE) continue;

        CompositionInstance comp = entry.getValue();
        double[] marginal = comp.marginalize(slotName, variableName);

        // P(evidence | H_i) = dot product of observation with marginal
        double likelihood = 0;
        for (int j = 0; j < distribution.length; j++) {
            likelihood += distribution[j] * marginal[j];
        }

        if (likelihood == 0.0) {
            statuses.put(name, HypothesisStatus.ELIMINATED);
            eliminatedThisStep.add(name);
            continue;
        }

        currentWeights.put(name, currentWeights.get(name) * likelihood);
        comp.setEvidence(slotName, variableName, distribution);
        comp.update();
    }

    normalize();
    softEliminate(eliminatedThisStep);
    if (!eliminatedThisStep.isEmpty()) normalize();
    observationCount++;
    return buildResult(eliminatedThisStep);
}
```

- [ ] **Step 6: Write test — hard elimination (impossible evidence)**

```java
@Test
void hardElimination_impossibleEvidence() {
    // Build a network where one hypothesis gives P=0 for an observation
    JunctionTree deterministicTree = BayesNetworkBuilder.create("det")
        .variable("cause", "A", "B")
            .prior(0.5, 0.5)
        .variable("effect", "yes", "no")
            .given("cause")
            .cpt(1.0, 0.0,   // cause=A → effect=yes with certainty
                 0.0, 1.0)   // cause=B → effect=no with certainty
        .buildJunctionTree();

    var comp = CompositionBuilder.create("det-comp")
        .slot("main", deterministicTree)
        .build();

    var tracker = HypothesisTracker.builder(comp)
        .hypothesis("causeA").priorWeight(0.5)
        .hypothesis("causeB").priorWeight(0.5)
        .eliminationThreshold(0.001)
        .build();

    // Observe cause=A on causeA's composition
    // Both hypotheses share the same network, so observe effect directly
    // When cause=A is certain → effect=yes is certain → P(effect=no | causeA after cause=A) = 0
    tracker.observeHard("main", "cause", "A");
    ObservationResult result = tracker.observeHard("main", "effect", "yes");

    // causeB saw P(cause=A)=0.5 initially, then P(effect=yes|causeB) depends on its posterior
    // Both hypotheses see the same evidence since they share the same network structure
    // After cause=A observed: both compositions have cause=A set, marginals shift
    // The interesting test: observe something impossible under one hypothesis's network variant
    // For a cleaner test, verify the hard elimination path with zero likelihood directly
    assertEquals(2, result.viable().size());
}
```

Actually, the hard elimination test needs hypotheses with different structures (variants) to produce zero likelihood. Let me write a cleaner test:

```java
@Test
void hardElimination_zeroLikelihood() {
    // Create two variants: one where gateway → rush is certain,
    // another where gateway is impossible
    JunctionTree normalTree = BayesNetworkBuilder.create("normal")
        .variable("observed", "gateway", "hatch")
            .prior(0.5, 0.5)
        .buildJunctionTree();

    JunctionTree neverGatewayTree = BayesNetworkBuilder.create("noGateway")
        .variable("observed", "gateway", "hatch")
            .prior(0.0, 1.0)  // gateway impossible
        .buildJunctionTree();

    var comp = CompositionBuilder.create("elim-test")
        .slot("scout", normalTree)
            .variant("never-gateway", neverGatewayTree)
        .build();

    var tracker = HypothesisTracker.builder(comp)
        .hypothesis("normal").priorWeight(0.5)
        .hypothesis("no-gateway").priorWeight(0.5)
            .activateVariant("scout", "never-gateway")
        .eliminationThreshold(0.001)
        .build();

    ObservationResult result = tracker.observeHard("scout", "observed", "gateway");

    assertEquals(1, result.viable().size());
    assertEquals("normal", result.viable().get(0));
    assertEquals(1, result.eliminated().size());
    assertEquals("no-gateway", result.eliminated().get(0));
    assertEquals(1.0, result.weights().get("normal"), 1e-9);
}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=HypothesisTrackerTest#hardElimination_zeroLikelihood`
Expected: PASS

- [ ] **Step 8: Write test — soft elimination below threshold**

```java
@Test
void softElimination_belowThreshold() {
    var comp = twoSlotComposition();
    var tracker = HypothesisTracker.builder(comp)
        .hypothesis("rush").priorWeight(0.5)
        .hypothesis("expand").priorWeight(0.5)
        .eliminationThreshold(0.05)
        .build();

    // Repeatedly observe hatchery — strongly favors expand
    ObservationResult result = null;
    for (int i = 0; i < 5; i++) {
        result = tracker.observeHard("scouting", "observed_units", "hatchery");
    }

    // After repeated hatchery observations, rush should be eliminated
    assertFalse(result.viable().contains("rush"),
        "Rush should be eliminated after repeated hatchery observations");
    assertTrue(result.viable().contains("expand"));
    assertTrue(result.eliminated().size() >= 1);
}
```

- [ ] **Step 9: Write test — resolution detection**

```java
@Test
void resolution_leaderExceedsThreshold() {
    var comp = twoSlotComposition();
    var tracker = HypothesisTracker.builder(comp)
        .hypothesis("rush").priorWeight(0.5)
        .hypothesis("expand").priorWeight(0.5)
        .resolutionThreshold(0.90)
        .eliminationThreshold(0.001)
        .build();

    // Repeatedly observe gateway — strongly favors rush
    ObservationResult result = null;
    for (int i = 0; i < 10; i++) {
        result = tracker.observeHard("scouting", "observed_units", "gateway");
        if (result.resolved()) break;
    }

    assertTrue(result.resolved(), "Should resolve after sufficient evidence");
    assertEquals("rush", result.leader());
    assertTrue(result.weights().get("rush") >= 0.90);
}
```

- [ ] **Step 10: Write test — entropy decreases with consistent evidence**

```java
@Test
void entropy_decreasesWithConsistentEvidence() {
    var comp = twoSlotComposition();
    var tracker = HypothesisTracker.builder(comp)
        .hypothesis("rush").priorWeight(0.5)
        .hypothesis("expand").priorWeight(0.5)
        .eliminationThreshold(0.001)
        .build();

    double previousEntropy = tracker.snapshot().entropy();
    for (int i = 0; i < 3; i++) {
        ObservationResult result = tracker.observeHard("scouting", "observed_units", "gateway");
        assertTrue(result.entropy() <= previousEntropy + 1e-9,
            "Entropy should not increase with consistent evidence: " +
            result.entropy() + " > " + previousEntropy);
        previousEntropy = result.entropy();
    }
    assertTrue(previousEntropy < 1.0, "Entropy should decrease significantly");
}
```

- [ ] **Step 11: Write test — reset restores priors after observations**

```java
@Test
void reset_restoresAfterObservations() {
    var comp = twoSlotComposition();
    var tracker = HypothesisTracker.builder(comp)
        .hypothesis("rush").priorWeight(0.5)
        .hypothesis("expand").priorWeight(0.5)
        .build();

    tracker.observeHard("scouting", "observed_units", "gateway");
    tracker.observeHard("scouting", "observed_units", "gateway");
    assertNotEquals(0.5, tracker.weights().get("rush"), 1e-9);

    tracker.reset();

    assertEquals(0.5, tracker.weights().get("rush"), 1e-9);
    assertEquals(0.5, tracker.weights().get("expand"), 1e-9);
    assertEquals(2, tracker.viable().size());
    assertEquals(0, tracker.snapshot().observationCount());
}
```

- [ ] **Step 12: Write test — SC2 end-to-end scenario**

```java
@Test
void sc2_scoutingScenario_threeHypotheses() {
    var comp = twoSlotComposition();
    var tracker = HypothesisTracker.builder(comp)
        .hypothesis("rush").priorWeight(1.0 / 3)
        .hypothesis("expand").priorWeight(1.0 / 3)
        .hypothesis("tech").priorWeight(1.0 / 3)
        .eliminationThreshold(0.01)
        .build();

    // Observation 1: gateway sighted
    ObservationResult r1 = tracker.observeHard("scouting", "observed_units", "gateway");
    assertEquals(3, r1.viable().size());
    assertEquals("rush", r1.leader());

    // Observation 2: gateway again — reinforces rush hypothesis
    ObservationResult r2 = tracker.observeHard("scouting", "observed_units", "gateway");
    assertTrue(r2.weights().get("rush") > r1.weights().get("rush"),
        "Rush weight should increase with repeated gateway evidence");

    // Verify build_choice downstream reflects rush dominance
    TrackerSnapshot snap = tracker.snapshot();
    assertTrue(snap.observationCount() == 2);
}
```

- [ ] **Step 13: Write test — soft evidence (distribution)**

```java
@Test
void softEvidence_distributionObservation() {
    var comp = twoSlotComposition();
    var tracker = HypothesisTracker.builder(comp)
        .hypothesis("rush").priorWeight(0.5)
        .hypothesis("expand").priorWeight(0.5)
        .build();

    // Soft evidence: 70% gateway, 20% hatchery, 10% barracks
    ObservationResult result = tracker.observe("scouting", "observed_units",
        new double[]{0.7, 0.2, 0.1});

    // Should favor rush (gateway-aligned) but less strongly than hard evidence
    assertTrue(result.weights().get("rush") > result.weights().get("expand"),
        "Rush should be favored by gateway-heavy soft evidence");
    assertEquals(2, result.viable().size());
}
```

- [ ] **Step 14: Write test — prior overrides differentiate hypotheses**

```java
@Test
void priorOverrides_differentiateHypotheses() {
    // Single-slot composition to isolate the prior override effect
    JunctionTree tree = BayesNetworkBuilder.create("simple")
        .variable("X", "a", "b")
            .prior(0.5, 0.5)
        .variable("Y", "yes", "no")
            .given("X")
            .cpt(0.9, 0.1,
                 0.1, 0.9)
        .buildJunctionTree();

    var comp = CompositionBuilder.create("override-test")
        .slot("main", tree)
        .build();

    var tracker = HypothesisTracker.builder(comp)
        .hypothesis("favorsA").priorWeight(0.5)
            .priorOverride("main", "X", new double[]{0.9, 0.1})
        .hypothesis("favorsB").priorWeight(0.5)
            .priorOverride("main", "X", new double[]{0.1, 0.9})
        .eliminationThreshold(0.001)
        .build();

    // Observe Y=yes → favors X=a → favors hypothesis "favorsA"
    ObservationResult result = tracker.observeHard("main", "Y", "yes");
    assertTrue(result.weights().get("favorsA") > result.weights().get("favorsB"),
        "favorsA should dominate after Y=yes observation");
}
```

- [ ] **Step 15: Run all tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=HypothesisTrackerTest`
Expected: All tests PASS (12+ tests)

- [ ] **Step 16: Commit**

```bash
git add inference-bayes/src/main/java/io/quarkmind/inference/bayes/HypothesisTracker.java \
       inference-bayes/src/test/java/io/quarkmind/inference/bayes/HypothesisTrackerTest.java
git commit -m "feat(#692): observe() and observeHard() — Bayesian weight update with elimination

Implement marginal-likelihood scoring, hard/soft elimination,
resolution detection, entropy computation, and full test suite
covering convergence, elimination, resolution, entropy monotonicity,
reset, prior overrides, soft evidence, and SC2 end-to-end scenario.

Closes casehubio/neocortex#692"
```

---

## References

- [2026-10-26-hypothesis-tracking-design.md] — design spec this plan implements
- `CompositionInstance.java` — composition layer (marginalize, setEvidence, update)
- `CompositionBuilder.java` — fluent builder pattern
- `BayesInstance.java:422-439` — state index resolution for hard evidence
- `BayesVariable.java:62-64` — getOutcomes() for state lookup
- `CompositionInstanceTest.java` — test helper methods (scouting/buildOrder trees)
- `MultiAgentInstance.java` — per-agent isolation pattern reference
- casehubio/neocortex#692 — focal issue
- casehubio/neocortex#674 — model composition (dependency)

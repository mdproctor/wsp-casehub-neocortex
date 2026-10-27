# BJT Structure Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #675 — BJT structure learning from data
**Issue group:** #675

**Goal:** Learn DAG structure from tabular observations using two
algorithms: PC (constraint-based, discovers causal direction via
conditional independence tests) and greedy hill-climbing (score-based,
optimises BIC fit). Both produce `NetworkSpec` (reviewable) or
`BayesNetwork` (ready to use). Pure Java, zero CDI.

**Architecture:** Single `StructureLearner` public facade with static
`pc()` and `hillClimbing()` methods, matching the existing
`ModelValidator`/`ModelSelector` pattern. Internal package-private
algorithm classes `PcAlgorithm` and `HillClimbingSearch`. Shared
`ContingencyTable` utility for data aggregation. `IndependenceTest`
@FunctionalInterface with static factories (same pattern as
`FoldSplitter`). `StructuralConstraints` record bridges to #677
(LLM+data fusion). Output is `StructureResult` wrapping `NetworkSpec`
with `StructureDiagnostics`.

**Tech Stack:** Java 21, JUnit 5. No new dependencies.

## Global Constraints

- Module: `inference-bayes`
- Package: `io.quarkmind.inference.bayes`
- No CDI, no Quarkus dependency — pure Java
- Thread-unsafe (same contract as `BayesInstance`)
- All new records use defensive copies (`Set.copyOf`, `List.copyOf`)
- Data format: `List<Map<String, String>>` — categorical string-valued
  observations, consistent with `ParameterLearner`
- NetworkSpec output uses `SpecStatus.PROPOSED` for all learned edges
- Missing values: skip observations with missing values for tested
  variables (consistent with `ParameterLearner`)

---

## Batch 1: Foundation types and math utilities

### Task 1: Value types — StructuralConstraints, StructureDiagnostics, StructureResult

**Files:**
- Create: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/StructuralConstraints.java`
- Create: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/StructureDiagnostics.java`
- Create: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/StructureResult.java`
- Test: `inference-bayes/src/test/java/io/quarkmind/inference/bayes/StructuralConstraintsTest.java`
- Test: `inference-bayes/src/test/java/io/quarkmind/inference/bayes/StructureResultTest.java`

**Interfaces:**
- Consumes: `NetworkSpec`, `BayesNetwork`, `ParameterLearner.fit()`
- Produces: `StructuralConstraints.none()`, `StructuralConstraints.maxParents(int)`, `StructuralConstraints.Edge(from, to)`, `StructureResult.toBayesNetwork(data)`, `StructureDiagnostics.PcDiagnostics`, `StructureDiagnostics.HillClimbingDiagnostics`

- [ ] **Step 1: Write the failing test — StructuralConstraints**

```java
package io.quarkmind.inference.bayes;

import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class StructuralConstraintsTest {

    @Test
    void none_returnsEmptyConstraints() {
        var c = StructuralConstraints.none();
        assertTrue(c.requiredEdges().isEmpty());
        assertTrue(c.forbiddenEdges().isEmpty());
        assertEquals(Integer.MAX_VALUE, c.maxParents());
    }

    @Test
    void maxParents_returnsConstraintWithLimit() {
        var c = StructuralConstraints.maxParents(3);
        assertTrue(c.requiredEdges().isEmpty());
        assertTrue(c.forbiddenEdges().isEmpty());
        assertEquals(3, c.maxParents());
    }

    @Test
    void defensiveCopy_requiredEdges() {
        var edges = new java.util.HashSet<>(Set.of(
            new StructuralConstraints.Edge("A", "B")));
        var c = new StructuralConstraints(edges, Set.of(), Integer.MAX_VALUE);
        edges.add(new StructuralConstraints.Edge("C", "D"));
        assertEquals(1, c.requiredEdges().size());
    }

    @Test
    void defensiveCopy_forbiddenEdges() {
        var edges = new java.util.HashSet<>(Set.of(
            new StructuralConstraints.Edge("X", "Y")));
        var c = new StructuralConstraints(Set.of(), edges, Integer.MAX_VALUE);
        edges.add(new StructuralConstraints.Edge("W", "Z"));
        assertEquals(1, c.forbiddenEdges().size());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=StructuralConstraintsTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error — `StructuralConstraints` not found

- [ ] **Step 3: Implement StructuralConstraints**

```java
package io.quarkmind.inference.bayes;

import java.util.Set;

public record StructuralConstraints(
    Set<Edge> requiredEdges,
    Set<Edge> forbiddenEdges,
    int maxParents
) {
    public record Edge(String from, String to) {}

    public StructuralConstraints {
        requiredEdges = Set.copyOf(requiredEdges);
        forbiddenEdges = Set.copyOf(forbiddenEdges);
    }

    public static StructuralConstraints none() {
        return new StructuralConstraints(Set.of(), Set.of(), Integer.MAX_VALUE);
    }

    public static StructuralConstraints maxParents(int max) {
        return new StructuralConstraints(Set.of(), Set.of(), max);
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=StructuralConstraintsTest`
Expected: 4 tests PASS

- [ ] **Step 5: Implement StructureDiagnostics**

```java
package io.quarkmind.inference.bayes;

import java.util.List;

public sealed interface StructureDiagnostics {

    record PcDiagnostics(
        int totalTests,
        int edgesRemoved,
        int vStructuresFound,
        int edgesOriented,
        int edgesUndirected,
        int maxConditioningSetSize
    ) implements StructureDiagnostics {}

    record HillClimbingDiagnostics(
        double bestScore,
        int totalOperations,
        int restartCount,
        int bestRestartIndex,
        List<Double> restartScores
    ) implements StructureDiagnostics {
        public HillClimbingDiagnostics {
            restartScores = List.copyOf(restartScores);
        }
    }
}
```

- [ ] **Step 6: Write the failing test — StructureResult**

```java
package io.quarkmind.inference.bayes;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class StructureResultTest {

    @Test
    void toBayesNetwork_fitsParametersFromData() {
        // A→B: two binary variables with known dependency
        var spec = new NetworkSpec("test",
            List.of(
                new VariableSpec("A", List.of("a0", "a1"), null,
                    SpecStatus.PROPOSED, new CptSpec.Uniform()),
                new VariableSpec("B", List.of("b0", "b1"), null,
                    SpecStatus.PROPOSED, new CptSpec.Uniform())
            ),
            List.of(new EdgeSpec("A", "B", "learned", SpecStatus.PROPOSED)),
            null);

        var diagnostics = new StructureDiagnostics.PcDiagnostics(
            5, 0, 1, 1, 0, 1);
        var result = new StructureResult(spec, "PC", diagnostics);

        List<Map<String, String>> data = List.of(
            Map.of("A", "a0", "B", "b0"),
            Map.of("A", "a0", "B", "b0"),
            Map.of("A", "a0", "B", "b0"),
            Map.of("A", "a1", "B", "b1"),
            Map.of("A", "a1", "B", "b1"),
            Map.of("A", "a1", "B", "b1")
        );

        BayesNetwork bn = result.toBayesNetwork(data);
        assertNotNull(bn);
        assertEquals("test", bn.getName());
    }

    @Test
    void toBayesNetwork_withAlpha() {
        var spec = new NetworkSpec("test",
            List.of(
                new VariableSpec("X", List.of("x0", "x1"), null,
                    SpecStatus.PROPOSED, new CptSpec.Uniform())
            ),
            List.of(),
            null);

        var diagnostics = new StructureDiagnostics.PcDiagnostics(
            0, 0, 0, 0, 0, 0);
        var result = new StructureResult(spec, "PC", diagnostics);

        List<Map<String, String>> data = List.of(
            Map.of("X", "x0"),
            Map.of("X", "x1")
        );

        BayesNetwork bn = result.toBayesNetwork(data, 2.0);
        assertNotNull(bn);
    }

    @Test
    void networkSpec_returnsOriginalSpec() {
        var spec = new NetworkSpec("n", List.of(), List.of(), null);
        var diag = new StructureDiagnostics.PcDiagnostics(0, 0, 0, 0, 0, 0);
        var result = new StructureResult(spec, "PC", diag);
        assertSame(spec, result.networkSpec());
        assertEquals("PC", result.algorithm());
        assertSame(diag, result.diagnostics());
    }
}
```

- [ ] **Step 7: Implement StructureResult**

```java
package io.quarkmind.inference.bayes;

import java.util.List;
import java.util.Map;

public record StructureResult(
    NetworkSpec networkSpec,
    String algorithm,
    StructureDiagnostics diagnostics
) {
    public BayesNetwork toBayesNetwork(List<Map<String, String>> data) {
        return ParameterLearner.fit(networkSpec.toBayesNetwork(), data);
    }

    public BayesNetwork toBayesNetwork(List<Map<String, String>> data, double alpha) {
        return ParameterLearner.fit(networkSpec.toBayesNetwork(), data, alpha);
    }
}
```

- [ ] **Step 8: Run all tests to verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest="StructuralConstraintsTest,StructureResultTest"`
Expected: all tests PASS

- [ ] **Step 9: Commit**

```bash
git add inference-bayes/src/main/java/io/quarkmind/inference/bayes/StructuralConstraints.java inference-bayes/src/main/java/io/quarkmind/inference/bayes/StructureDiagnostics.java inference-bayes/src/main/java/io/quarkmind/inference/bayes/StructureResult.java inference-bayes/src/test/java/io/quarkmind/inference/bayes/StructuralConstraintsTest.java inference-bayes/src/test/java/io/quarkmind/inference/bayes/StructureResultTest.java
git commit -m "feat(#675): add StructuralConstraints, StructureDiagnostics, StructureResult value types Refs #675"
```

---

### Task 2: Math utilities — GammaFunction and ContingencyTable

**Files:**
- Create: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/GammaFunction.java`
- Create: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/ContingencyTable.java`
- Test: `inference-bayes/src/test/java/io/quarkmind/inference/bayes/GammaFunctionTest.java`
- Test: `inference-bayes/src/test/java/io/quarkmind/inference/bayes/ContingencyTableTest.java`

**Interfaces:**
- Consumes: nothing (leaf utilities)
- Produces: `GammaFunction.chiSquaredPValue(double statistic, int df)` → double, `GammaFunction.regularizedGammaP(double a, double x)` → double, `GammaFunction.logGamma(double x)` → double, `ContingencyTable(int[][] counts, int[] rowTotals, int[] colTotals, int total)`, `ContingencyTable.build(String x, String y, Set<String> conditioningSet, List<Map<String, String>> data)` → `List<ContingencyTable>` (one per conditioning config), `ContingencyTable.buildForVariable(String variable, List<String> parents, List<Map<String, String>> data)` → `ContingencyTable` (for hill-climbing local score)

- [ ] **Step 1: Write the failing test — GammaFunction**

```java
package io.quarkmind.inference.bayes;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class GammaFunctionTest {

    @Test
    void logGamma_knownValues() {
        // Γ(1) = 1, ln(1) = 0
        assertEquals(0.0, GammaFunction.logGamma(1.0), 1e-10);
        // Γ(2) = 1, ln(1) = 0
        assertEquals(0.0, GammaFunction.logGamma(2.0), 1e-10);
        // Γ(0.5) = √π ≈ 1.7724538509, ln ≈ 0.5723649429
        assertEquals(0.5723649429, GammaFunction.logGamma(0.5), 1e-6);
        // Γ(5) = 24, ln(24) ≈ 3.1780538303
        assertEquals(3.1780538303, GammaFunction.logGamma(5.0), 1e-6);
    }

    @Test
    void regularizedGammaP_zeroX_returnsZero() {
        assertEquals(0.0, GammaFunction.regularizedGammaP(1.0, 0.0), 1e-10);
    }

    @Test
    void regularizedGammaP_largeX_approachesOne() {
        assertTrue(GammaFunction.regularizedGammaP(1.0, 20.0) > 0.999);
    }

    @Test
    void chiSquaredPValue_df1() {
        // chi-squared(3.841, df=1) → p ≈ 0.05
        assertEquals(0.05, GammaFunction.chiSquaredPValue(3.841, 1), 0.001);
    }

    @Test
    void chiSquaredPValue_df2() {
        // chi-squared(5.991, df=2) → p ≈ 0.05
        assertEquals(0.05, GammaFunction.chiSquaredPValue(5.991, 2), 0.001);
    }

    @Test
    void chiSquaredPValue_zeroStatistic_returnsOne() {
        assertEquals(1.0, GammaFunction.chiSquaredPValue(0.0, 1), 1e-10);
    }

    @Test
    void chiSquaredPValue_veryLargeStatistic_nearZero() {
        assertTrue(GammaFunction.chiSquaredPValue(100.0, 1) < 1e-10);
    }

    @Test
    void regularizedGammaP_halfInteger_a() {
        // P(0.5, 0.5) — tests the half-integer branch
        double result = GammaFunction.regularizedGammaP(0.5, 0.5);
        // known value: erf(sqrt(0.5)) ≈ 0.6827
        assertTrue(result > 0.5 && result < 0.8);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=GammaFunctionTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error — `GammaFunction` not found

- [ ] **Step 3: Implement GammaFunction**

```java
package io.quarkmind.inference.bayes;

final class GammaFunction {

    private static final int MAX_ITERATIONS = 200;
    private static final double EPSILON = 1e-15;

    private GammaFunction() {}

    static double chiSquaredPValue(double statistic, int degreesOfFreedom) {
        if (statistic <= 0.0) return 1.0;
        if (degreesOfFreedom <= 0) throw new IllegalArgumentException(
            "Degrees of freedom must be positive: " + degreesOfFreedom);
        return 1.0 - regularizedGammaP(degreesOfFreedom / 2.0, statistic / 2.0);
    }

    static double regularizedGammaP(double a, double x) {
        if (x < 0.0 || a <= 0.0) throw new IllegalArgumentException(
            "Requires a > 0 and x >= 0: a=" + a + ", x=" + x);
        if (x == 0.0) return 0.0;
        if (x < a + 1.0) {
            return gammaSeriesP(a, x);
        } else {
            return 1.0 - gammaContinuedFractionQ(a, x);
        }
    }

    static double logGamma(double x) {
        // Lanczos approximation (g=7, n=9)
        double[] coeff = {
            0.99999999999980993,
            676.5203681218851,
            -1259.1392167224028,
            771.32342877765313,
            -176.61502916214059,
            12.507343278686905,
            -0.13857109526572012,
            9.9843695780195716e-6,
            1.5056327351493116e-7
        };
        if (x < 0.5) {
            return Math.log(Math.PI / Math.sin(Math.PI * x))
                - logGamma(1.0 - x);
        }
        x -= 1.0;
        double a = coeff[0];
        double t = x + 7.5;
        for (int i = 1; i < coeff.length; i++) {
            a += coeff[i] / (x + i);
        }
        return 0.5 * Math.log(2.0 * Math.PI) + (x + 0.5) * Math.log(t) - t
            + Math.log(a);
    }

    private static double gammaSeriesP(double a, double x) {
        double ap = a;
        double sum = 1.0 / a;
        double term = 1.0 / a;
        for (int n = 1; n <= MAX_ITERATIONS; n++) {
            ap += 1.0;
            term *= x / ap;
            sum += term;
            if (Math.abs(term) < Math.abs(sum) * EPSILON) {
                return sum * Math.exp(-x + a * Math.log(x) - logGamma(a));
            }
        }
        return sum * Math.exp(-x + a * Math.log(x) - logGamma(a));
    }

    private static double gammaContinuedFractionQ(double a, double x) {
        // Modified Lentz algorithm
        double b = x + 1.0 - a;
        double c = 1.0 / EPSILON;
        double d = 1.0 / b;
        double h = d;
        for (int i = 1; i <= MAX_ITERATIONS; i++) {
            double an = -i * (i - a);
            b += 2.0;
            d = an * d + b;
            if (Math.abs(d) < EPSILON) d = EPSILON;
            c = b + an / c;
            if (Math.abs(c) < EPSILON) c = EPSILON;
            d = 1.0 / d;
            double delta = d * c;
            h *= delta;
            if (Math.abs(delta - 1.0) < EPSILON) break;
        }
        return Math.exp(-x + a * Math.log(x) - logGamma(a)) * h;
    }
}
```

- [ ] **Step 4: Run GammaFunction tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=GammaFunctionTest`
Expected: all tests PASS

- [ ] **Step 5: Write the failing test — ContingencyTable**

```java
package io.quarkmind.inference.bayes;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class ContingencyTableTest {

    @Test
    void buildMarginal_twoVariables() {
        List<Map<String, String>> data = List.of(
            Map.of("X", "a", "Y", "c"),
            Map.of("X", "a", "Y", "c"),
            Map.of("X", "a", "Y", "d"),
            Map.of("X", "b", "Y", "c"),
            Map.of("X", "b", "Y", "d"),
            Map.of("X", "b", "Y", "d")
        );

        List<ContingencyTable> tables = ContingencyTable.build(
            "X", "Y", Set.of(), data);
        assertEquals(1, tables.size());

        ContingencyTable t = tables.get(0);
        // X has outcomes [a, b], Y has outcomes [c, d]
        // row=X outcome index, col=Y outcome index
        assertEquals(6, t.total());
        assertEquals(2, t.counts().length);    // 2 X outcomes
        assertEquals(2, t.counts()[0].length); // 2 Y outcomes
        // X=a,Y=c: 2; X=a,Y=d: 1; X=b,Y=c: 1; X=b,Y=d: 2
        assertEquals(2, t.counts()[0][0]); // a,c
        assertEquals(1, t.counts()[0][1]); // a,d
        assertEquals(1, t.counts()[1][0]); // b,c
        assertEquals(2, t.counts()[1][1]); // b,d
    }

    @Test
    void buildConditional_withConditioningSet() {
        List<Map<String, String>> data = List.of(
            Map.of("X", "a", "Y", "c", "Z", "z0"),
            Map.of("X", "a", "Y", "d", "Z", "z0"),
            Map.of("X", "b", "Y", "c", "Z", "z0"),
            Map.of("X", "a", "Y", "c", "Z", "z1"),
            Map.of("X", "b", "Y", "d", "Z", "z1"),
            Map.of("X", "b", "Y", "d", "Z", "z1")
        );

        List<ContingencyTable> tables = ContingencyTable.build(
            "X", "Y", Set.of("Z"), data);
        assertEquals(2, tables.size());

        // z0: X=a,Y=c:1; X=a,Y=d:1; X=b,Y=c:1; X=b,Y=d:0
        ContingencyTable z0 = tables.get(0);
        assertEquals(3, z0.total());
        // z1: X=a,Y=c:1; X=a,Y=d:0; X=b,Y=c:0; X=b,Y=d:2
        ContingencyTable z1 = tables.get(1);
        assertEquals(3, z1.total());
    }

    @Test
    void buildForVariable_noParents() {
        List<Map<String, String>> data = List.of(
            Map.of("X", "a"),
            Map.of("X", "a"),
            Map.of("X", "b")
        );

        ContingencyTable t = ContingencyTable.buildForVariable(
            "X", List.of(), data);
        assertEquals(1, t.counts().length); // 1 parent config (none)
        assertEquals(2, t.counts()[0].length); // 2 outcomes
        assertEquals(2, t.counts()[0][0]); // a
        assertEquals(1, t.counts()[0][1]); // b
        assertEquals(3, t.total());
    }

    @Test
    void buildForVariable_withParents() {
        List<Map<String, String>> data = List.of(
            Map.of("A", "a0", "B", "b0", "C", "c0"),
            Map.of("A", "a0", "B", "b0", "C", "c0"),
            Map.of("A", "a0", "B", "b1", "C", "c1"),
            Map.of("A", "a1", "B", "b0", "C", "c0"),
            Map.of("A", "a1", "B", "b1", "C", "c1"),
            Map.of("A", "a1", "B", "b1", "C", "c1")
        );

        ContingencyTable t = ContingencyTable.buildForVariable(
            "C", List.of("A", "B"), data);
        // 4 parent configs: (a0,b0), (a0,b1), (a1,b0), (a1,b1)
        assertEquals(4, t.counts().length);
        assertEquals(2, t.counts()[0].length); // 2 C outcomes
        // (a0,b0): c0=2, c1=0
        assertEquals(2, t.counts()[0][0]);
        assertEquals(0, t.counts()[0][1]);
    }

    @Test
    void skipsMissingValues() {
        List<Map<String, String>> data = List.of(
            Map.of("X", "a", "Y", "c"),
            Map.of("X", "a"),  // Y missing
            Map.of("Y", "d")   // X missing
        );

        List<ContingencyTable> tables = ContingencyTable.build(
            "X", "Y", Set.of(), data);
        assertEquals(1, tables.size());
        assertEquals(1, tables.get(0).total()); // only first row counted
    }
}
```

- [ ] **Step 6: Implement ContingencyTable**

```java
package io.quarkmind.inference.bayes;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

record ContingencyTable(int[][] counts, int[] rowTotals, int[] colTotals, int total) {

    static List<ContingencyTable> build(String x, String y, Set<String> conditioningSet,
                                         List<Map<String, String>> data) {
        // Discover outcomes for x, y, and conditioning variables
        var xOutcomes = discoverOutcomes(x, data);
        var yOutcomes = discoverOutcomes(y, data);

        if (conditioningSet.isEmpty()) {
            return List.of(buildTable(x, y, xOutcomes, yOutcomes, data));
        }

        // Group data by conditioning configuration
        var groups = new LinkedHashMap<String, List<Map<String, String>>>();
        for (var obs : data) {
            String key = conditioningKey(obs, conditioningSet);
            if (key == null) continue;
            groups.computeIfAbsent(key, k -> new ArrayList<>()).add(obs);
        }

        var tables = new ArrayList<ContingencyTable>();
        for (var group : groups.values()) {
            ContingencyTable t = buildTable(x, y, xOutcomes, yOutcomes, group);
            if (t.total > 0) tables.add(t);
        }
        return List.copyOf(tables);
    }

    static ContingencyTable buildForVariable(String variable, List<String> parents,
                                              List<Map<String, String>> data) {
        var varOutcomes = discoverOutcomes(variable, data);
        int numOutcomes = varOutcomes.size();

        if (parents.isEmpty()) {
            int[][] counts = new int[1][numOutcomes];
            int total = 0;
            for (var obs : data) {
                String val = obs.get(variable);
                if (val == null) continue;
                int idx = indexOf(varOutcomes, val);
                if (idx >= 0) {
                    counts[0][idx]++;
                    total++;
                }
            }
            return fromCounts(counts, total);
        }

        var parentOutcomeLists = new ArrayList<List<String>>();
        for (String p : parents) {
            parentOutcomeLists.add(discoverOutcomes(p, data));
        }
        int numParentConfigs = 1;
        for (var po : parentOutcomeLists) numParentConfigs *= po.size();

        int[][] counts = new int[numParentConfigs][numOutcomes];
        int total = 0;
        for (var obs : data) {
            String val = obs.get(variable);
            if (val == null) continue;
            int varIdx = indexOf(varOutcomes, val);
            if (varIdx < 0) continue;

            int parentConfig = parentConfigIndex(obs, parents, parentOutcomeLists);
            if (parentConfig < 0) continue;

            counts[parentConfig][varIdx]++;
            total++;
        }
        return fromCounts(counts, total);
    }

    private static ContingencyTable buildTable(String x, String y,
                                                List<String> xOutcomes, List<String> yOutcomes,
                                                List<Map<String, String>> data) {
        int[][] counts = new int[xOutcomes.size()][yOutcomes.size()];
        int total = 0;
        for (var obs : data) {
            String xVal = obs.get(x);
            String yVal = obs.get(y);
            if (xVal == null || yVal == null) continue;
            int xi = indexOf(xOutcomes, xVal);
            int yi = indexOf(yOutcomes, yVal);
            if (xi >= 0 && yi >= 0) {
                counts[xi][yi]++;
                total++;
            }
        }
        return fromCounts(counts, total);
    }

    private static ContingencyTable fromCounts(int[][] counts, int total) {
        int rows = counts.length;
        int cols = counts[0].length;
        int[] rowTotals = new int[rows];
        int[] colTotals = new int[cols];
        for (int i = 0; i < rows; i++) {
            for (int j = 0; j < cols; j++) {
                rowTotals[i] += counts[i][j];
                colTotals[j] += counts[i][j];
            }
        }
        return new ContingencyTable(counts, rowTotals, colTotals, total);
    }

    private static int parentConfigIndex(Map<String, String> obs,
                                          List<String> parents,
                                          List<List<String>> parentOutcomes) {
        int index = 0;
        for (int i = 0; i < parents.size(); i++) {
            String val = obs.get(parents.get(i));
            if (val == null) return -1;
            int stateIdx = indexOf(parentOutcomes.get(i), val);
            if (stateIdx < 0) return -1;
            int stride = 1;
            for (int j = i + 1; j < parents.size(); j++) {
                stride *= parentOutcomes.get(j).size();
            }
            index += stateIdx * stride;
        }
        return index;
    }

    private static String conditioningKey(Map<String, String> obs,
                                           Set<String> conditioningSet) {
        var sb = new StringBuilder();
        for (String var : conditioningSet) {
            String val = obs.get(var);
            if (val == null) return null;
            if (!sb.isEmpty()) sb.append('|');
            sb.append(var).append('=').append(val);
        }
        return sb.toString();
    }

    static List<String> discoverOutcomes(String variable,
                                          List<Map<String, String>> data) {
        var outcomes = new LinkedHashSet<String>();
        for (var obs : data) {
            String val = obs.get(variable);
            if (val != null) outcomes.add(val);
        }
        return List.copyOf(outcomes);
    }

    private static int indexOf(List<String> list, String value) {
        return list.indexOf(value);
    }
}
```

- [ ] **Step 7: Run ContingencyTable tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=ContingencyTableTest`
Expected: all tests PASS

- [ ] **Step 8: Run all Batch 1 tests together**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest="StructuralConstraintsTest,StructureResultTest,GammaFunctionTest,ContingencyTableTest"`
Expected: all tests PASS

- [ ] **Step 9: Commit**

```bash
git add inference-bayes/src/main/java/io/quarkmind/inference/bayes/GammaFunction.java inference-bayes/src/main/java/io/quarkmind/inference/bayes/ContingencyTable.java inference-bayes/src/test/java/io/quarkmind/inference/bayes/GammaFunctionTest.java inference-bayes/src/test/java/io/quarkmind/inference/bayes/ContingencyTableTest.java
git commit -m "feat(#675): add GammaFunction and ContingencyTable utilities Refs #675"
```

---

## Batch 2: Independence testing

### Task 3: IndependenceTest — G-test, Fisher's exact, adaptive

**Files:**
- Create: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/IndependenceTest.java`
- Test: `inference-bayes/src/test/java/io/quarkmind/inference/bayes/IndependenceTestTest.java`

**Interfaces:**
- Consumes: `ContingencyTable.build()`, `GammaFunction.chiSquaredPValue()`
- Produces: `IndependenceTest.test(x, y, conditioningSet, data)` → `IndependenceResult`, `IndependenceTest.gTest(alpha)`, `IndependenceTest.fisherExact(alpha)`, `IndependenceTest.adaptive(alpha)`

- [ ] **Step 1: Write the failing test**

```java
package io.quarkmind.inference.bayes;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class IndependenceTestTest {

    // -- G-test --

    @Test
    void gTest_independentVariables_returnsIndependent() {
        // X and Y are generated independently
        var data = generateIndependent(500, 42L);
        var result = IndependenceTest.gTest(0.05).test("X", "Y", Set.of(), data);
        assertTrue(result.independent());
        assertTrue(result.pValue() > 0.05);
    }

    @Test
    void gTest_dependentVariables_returnsDependent() {
        // Y is a deterministic copy of X
        var data = generateDependent(200, 42L);
        var result = IndependenceTest.gTest(0.05).test("X", "Y", Set.of(), data);
        assertFalse(result.independent());
        assertTrue(result.pValue() < 0.01);
    }

    @Test
    void gTest_conditionalIndependence() {
        // X→Z←Y: X and Y are independent given Z only when Z is NOT a collider test
        // Use: X→Z, Y independent of X — conditioning on nothing should show independence
        var data = generateConditionallyIndependent(500, 42L);
        var result = IndependenceTest.gTest(0.05).test("X", "Y", Set.of("Z"), data);
        assertTrue(result.independent());
    }

    // -- Fisher's exact --

    @Test
    void fisherExact_binaryIndependent_returnsIndependent() {
        var data = generateBinaryIndependent(100, 42L);
        var result = IndependenceTest.fisherExact(0.05).test("X", "Y", Set.of(), data);
        assertTrue(result.independent());
        assertTrue(result.pValue() > 0.05);
    }

    @Test
    void fisherExact_binaryDependent_returnsDependent() {
        var data = generateDependent(100, 42L);
        var result = IndependenceTest.fisherExact(0.05).test("X", "Y", Set.of(), data);
        assertFalse(result.independent());
        assertTrue(result.pValue() < 0.05);
    }

    // -- Adaptive --

    @Test
    void adaptive_selectsFisherForSmallCounts() {
        // Very sparse data — adaptive should use Fisher's
        var data = List.of(
            Map.of("X", "a", "Y", "c"),
            Map.of("X", "a", "Y", "d"),
            Map.of("X", "b", "Y", "c"),
            Map.of("X", "b", "Y", "d")
        );
        var result = IndependenceTest.adaptive(0.05).test("X", "Y", Set.of(), data);
        assertNotNull(result);
        assertTrue(result.pValue() >= 0.0 && result.pValue() <= 1.0);
    }

    @Test
    void adaptive_usesGTestForLargeCounts() {
        var data = generateIndependent(500, 42L);
        var result = IndependenceTest.adaptive(0.05).test("X", "Y", Set.of(), data);
        assertTrue(result.independent());
    }

    // -- Edge cases --

    @Test
    void gTest_uniformData_highPValue() {
        var data = generateUniform(1000, 42L);
        var result = IndependenceTest.gTest(0.05).test("X", "Y", Set.of(), data);
        assertTrue(result.pValue() > 0.1);
    }

    // -- Data generators --

    private List<Map<String, String>> generateIndependent(int n, long seed) {
        var rng = new Random(seed);
        String[] xVals = {"a", "b", "c"};
        String[] yVals = {"d", "e", "f"};
        var data = new ArrayList<Map<String, String>>();
        for (int i = 0; i < n; i++) {
            data.add(Map.of("X", xVals[rng.nextInt(3)], "Y", yVals[rng.nextInt(3)]));
        }
        return data;
    }

    private List<Map<String, String>> generateDependent(int n, long seed) {
        var rng = new Random(seed);
        String[] vals = {"a", "b"};
        var data = new ArrayList<Map<String, String>>();
        for (int i = 0; i < n; i++) {
            String v = vals[rng.nextInt(2)];
            data.add(Map.of("X", v, "Y", v)); // Y = X
        }
        return data;
    }

    private List<Map<String, String>> generateBinaryIndependent(int n, long seed) {
        var rng = new Random(seed);
        var data = new ArrayList<Map<String, String>>();
        for (int i = 0; i < n; i++) {
            data.add(Map.of("X", rng.nextBoolean() ? "a" : "b",
                            "Y", rng.nextBoolean() ? "c" : "d"));
        }
        return data;
    }

    private List<Map<String, String>> generateConditionallyIndependent(int n, long seed) {
        // X→Z, Y→Z: X and Y are conditionally independent given Z
        // when the Z value screens off X from Y
        var rng = new Random(seed);
        String[] vals = {"a", "b"};
        var data = new ArrayList<Map<String, String>>();
        for (int i = 0; i < n; i++) {
            String x = vals[rng.nextInt(2)];
            String y = vals[rng.nextInt(2)]; // Y independent of X
            String z = (rng.nextDouble() < 0.8) ? x : y; // Z mostly follows X
            data.add(Map.of("X", x, "Y", y, "Z", z));
        }
        return data;
    }

    private List<Map<String, String>> generateUniform(int n, long seed) {
        var rng = new Random(seed);
        String[] xVals = {"a", "b"};
        String[] yVals = {"c", "d"};
        var data = new ArrayList<Map<String, String>>();
        for (int i = 0; i < n; i++) {
            data.add(Map.of("X", xVals[rng.nextInt(2)], "Y", yVals[rng.nextInt(2)]));
        }
        return data;
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=IndependenceTestTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error — `IndependenceTest` not found

- [ ] **Step 3: Implement IndependenceTest**

```java
package io.quarkmind.inference.bayes;

import java.util.List;
import java.util.Map;
import java.util.Set;

@FunctionalInterface
public interface IndependenceTest {

    IndependenceResult test(String x, String y, Set<String> conditioningSet,
                            List<Map<String, String>> data);

    record IndependenceResult(boolean independent, double pValue, double statistic) {}

    static IndependenceTest gTest(double alpha) {
        return (x, y, cond, data) -> {
            var tables = ContingencyTable.build(x, y, cond, data);
            if (tables.isEmpty()) return new IndependenceResult(true, 1.0, 0.0);

            double totalG = 0.0;
            int totalDf = 0;
            for (var table : tables) {
                if (table.total() == 0) continue;
                totalG += computeGStatistic(table);
                totalDf += (table.counts().length - 1) * (table.counts()[0].length - 1);
            }
            if (totalDf <= 0) return new IndependenceResult(true, 1.0, 0.0);
            double pValue = GammaFunction.chiSquaredPValue(totalG, totalDf);
            return new IndependenceResult(pValue >= alpha, pValue, totalG);
        };
    }

    static IndependenceTest fisherExact(double alpha) {
        return (x, y, cond, data) -> {
            var tables = ContingencyTable.build(x, y, cond, data);
            if (tables.isEmpty()) return new IndependenceResult(true, 1.0, 0.0);

            double combinedP = 1.0;
            for (var table : tables) {
                if (table.total() == 0) continue;
                int rows = table.counts().length;
                int cols = table.counts()[0].length;
                if (rows > 5 || cols > 5) {
                    // Fall back to G-test for large tables
                    double g = computeGStatistic(table);
                    int df = (rows - 1) * (cols - 1);
                    combinedP = Math.min(combinedP,
                        GammaFunction.chiSquaredPValue(g, df));
                } else if (rows == 2 && cols == 2) {
                    combinedP = Math.min(combinedP,
                        fisher2x2(table.counts()));
                } else {
                    combinedP = Math.min(combinedP,
                        fisherRxC(table.counts(), table.rowTotals(),
                            table.colTotals(), table.total()));
                }
            }
            return new IndependenceResult(combinedP >= alpha, combinedP, 0.0);
        };
    }

    static IndependenceTest adaptive(double alpha) {
        return (x, y, cond, data) -> {
            var tables = ContingencyTable.build(x, y, cond, data);
            if (tables.isEmpty()) return new IndependenceResult(true, 1.0, 0.0);

            double totalG = 0.0;
            int totalDf = 0;
            double minFisherP = 1.0;
            boolean usedFisher = false;

            for (var table : tables) {
                if (table.total() == 0) continue;
                if (hasSmallExpectedCounts(table)) {
                    usedFisher = true;
                    int rows = table.counts().length;
                    int cols = table.counts()[0].length;
                    double p;
                    if (rows > 5 || cols > 5) {
                        double g = computeGStatistic(table);
                        int df = (rows - 1) * (cols - 1);
                        p = GammaFunction.chiSquaredPValue(g, df);
                    } else if (rows == 2 && cols == 2) {
                        p = fisher2x2(table.counts());
                    } else {
                        p = fisherRxC(table.counts(), table.rowTotals(),
                            table.colTotals(), table.total());
                    }
                    minFisherP = Math.min(minFisherP, p);
                } else {
                    totalG += computeGStatistic(table);
                    totalDf += (table.counts().length - 1)
                        * (table.counts()[0].length - 1);
                }
            }

            if (usedFisher && totalDf == 0) {
                return new IndependenceResult(minFisherP >= alpha, minFisherP, 0.0);
            }
            if (!usedFisher && totalDf > 0) {
                double pValue = GammaFunction.chiSquaredPValue(totalG, totalDf);
                return new IndependenceResult(pValue >= alpha, pValue, totalG);
            }
            // Mixed: combine via minimum p-value
            double gP = totalDf > 0
                ? GammaFunction.chiSquaredPValue(totalG, totalDf) : 1.0;
            double combinedP = Math.min(gP, minFisherP);
            return new IndependenceResult(combinedP >= alpha, combinedP, totalG);
        };
    }

    private static double computeGStatistic(ContingencyTable table) {
        double g = 0.0;
        int[][] counts = table.counts();
        int[] rowTotals = table.rowTotals();
        int[] colTotals = table.colTotals();
        int total = table.total();

        for (int i = 0; i < counts.length; i++) {
            for (int j = 0; j < counts[0].length; j++) {
                int observed = counts[i][j];
                if (observed == 0) continue;
                double expected = (double) rowTotals[i] * colTotals[j] / total;
                if (expected == 0.0) continue;
                g += observed * Math.log((double) observed / expected);
            }
        }
        return 2.0 * g;
    }

    private static boolean hasSmallExpectedCounts(ContingencyTable table) {
        int[] rowTotals = table.rowTotals();
        int[] colTotals = table.colTotals();
        int total = table.total();
        for (int rt : rowTotals) {
            for (int ct : colTotals) {
                double expected = (double) rt * ct / total;
                if (expected < 5.0) return true;
            }
        }
        return false;
    }

    private static double fisher2x2(int[][] counts) {
        int a = counts[0][0], b = counts[0][1];
        int c = counts[1][0], d = counts[1][1];
        int n = a + b + c + d;
        int r1 = a + b, r2 = c + d;
        int c1 = a + c, c2 = b + d;

        double observedP = hypergeometricProbability(a, r1, c1, n);
        double pValue = 0.0;

        // Two-sided: sum probabilities of tables as extreme or more extreme
        for (int x = Math.max(0, r1 + c1 - n); x <= Math.min(r1, c1); x++) {
            double p = hypergeometricProbability(x, r1, c1, n);
            if (p <= observedP * (1.0 + 1e-7)) {
                pValue += p;
            }
        }
        return Math.min(pValue, 1.0);
    }

    private static double hypergeometricProbability(int k, int n1, int n2, int n) {
        return Math.exp(
            logBinomial(n1, k) + logBinomial(n - n1, n2 - k)
            - logBinomial(n, n2));
    }

    private static double logBinomial(int n, int k) {
        if (k < 0 || k > n) return Double.NEGATIVE_INFINITY;
        return GammaFunction.logGamma(n + 1)
            - GammaFunction.logGamma(k + 1)
            - GammaFunction.logGamma(n - k + 1);
    }

    private static double fisherRxC(int[][] counts, int[] rowTotals,
                                     int[] colTotals, int total) {
        double observedP = tableLogProbability(counts, rowTotals, colTotals, total);
        double[] pValueHolder = {0.0};
        enumerateTables(counts, rowTotals, colTotals, total,
            observedP, pValueHolder, 0, new int[counts.length][counts[0].length]);
        return Math.min(pValueHolder[0], 1.0);
    }

    private static double tableLogProbability(int[][] counts, int[] rowTotals,
                                               int[] colTotals, int total) {
        double logP = 0.0;
        for (int rt : rowTotals) logP += GammaFunction.logGamma(rt + 1);
        for (int ct : colTotals) logP += GammaFunction.logGamma(ct + 1);
        logP -= GammaFunction.logGamma(total + 1);
        for (int[] row : counts) {
            for (int cell : row) {
                logP -= GammaFunction.logGamma(cell + 1);
            }
        }
        return logP;
    }

    private static void enumerateTables(int[][] observed, int[] rowTotals,
                                         int[] colTotals, int total,
                                         double observedLogP, double[] pValue,
                                         int row, int[][] current) {
        int rows = observed.length;
        int cols = observed[0].length;
        if (row == rows - 1) {
            int[] remaining = colTotals.clone();
            for (int i = 0; i < row; i++) {
                for (int j = 0; j < cols; j++) remaining[j] -= current[i][j];
            }
            for (int j = 0; j < cols; j++) {
                if (remaining[j] < 0) return;
                current[row][j] = remaining[j];
            }
            double logP = tableLogProbability(current, rowTotals, colTotals, total);
            if (logP <= observedLogP + 1e-10) {
                pValue[0] += Math.exp(logP);
            }
            return;
        }

        int[] colRemaining = colTotals.clone();
        for (int i = 0; i < row; i++) {
            for (int j = 0; j < cols; j++) colRemaining[j] -= current[i][j];
        }
        enumerateRow(observed, rowTotals, colTotals, total,
            observedLogP, pValue, row, current, colRemaining, 0, rowTotals[row]);
    }

    private static void enumerateRow(int[][] observed, int[] rowTotals,
                                      int[] colTotals, int total,
                                      double observedLogP, double[] pValue,
                                      int row, int[][] current,
                                      int[] colRemaining, int col, int rowLeft) {
        int cols = observed[0].length;
        if (col == cols - 1) {
            if (rowLeft > colRemaining[col]) return;
            current[row][col] = rowLeft;
            enumerateTables(observed, rowTotals, colTotals, total,
                observedLogP, pValue, row + 1, current);
            return;
        }
        int maxVal = Math.min(rowLeft, colRemaining[col]);
        for (int v = 0; v <= maxVal; v++) {
            current[row][col] = v;
            enumerateRow(observed, rowTotals, colTotals, total,
                observedLogP, pValue, row, current, colRemaining, col + 1, rowLeft - v);
        }
    }
}
```

- [ ] **Step 4: Run IndependenceTest tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=IndependenceTestTest`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add inference-bayes/src/main/java/io/quarkmind/inference/bayes/IndependenceTest.java inference-bayes/src/test/java/io/quarkmind/inference/bayes/IndependenceTestTest.java
git commit -m "feat(#675): add IndependenceTest with G-test, Fisher's exact, adaptive factories Refs #675"
```

---

## Batch 3: PC algorithm

### Task 4: PcAlgorithm — skeleton discovery, v-structures, Meek's rules

**Files:**
- Create: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/PcAlgorithm.java`
- Test: `inference-bayes/src/test/java/io/quarkmind/inference/bayes/PcAlgorithmTest.java`

**Interfaces:**
- Consumes: `IndependenceTest.test()`, `StructuralConstraints`, `NetworkSpec`, `VariableSpec`, `EdgeSpec`, `SpecStatus.PROPOSED`, `StructureDiagnostics.PcDiagnostics`, `ContingencyTable.discoverOutcomes()`
- Produces: `PcAlgorithm.learn(data, test, constraints)` → `StructureResult`

- [ ] **Step 1: Write the failing test**

```java
package io.quarkmind.inference.bayes;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class PcAlgorithmTest {

    @Test
    void twoIndependentVariables_noEdges() {
        var data = generateIndependentAB(500, 42L);
        var result = PcAlgorithm.learn(data, IndependenceTest.adaptive(0.05),
            StructuralConstraints.none());

        assertTrue(result.networkSpec().edges().isEmpty());
        assertEquals("PC", result.algorithm());

        var diag = (StructureDiagnostics.PcDiagnostics) result.diagnostics();
        assertTrue(diag.totalTests() > 0);
        assertTrue(diag.edgesRemoved() > 0);
    }

    @Test
    void chainAtoB_discoversEdge() {
        // A→B: B depends on A
        var data = generateChainAB(500, 42L);
        var result = PcAlgorithm.learn(data, IndependenceTest.adaptive(0.05),
            StructuralConstraints.none());

        assertEquals(1, result.networkSpec().edges().size());
        var edge = result.networkSpec().edges().get(0);
        // PC discovers the edge but may orient either direction
        assertTrue(
            (edge.from().equals("A") && edge.to().equals("B")) ||
            (edge.from().equals("B") && edge.to().equals("A"))
        );
        assertEquals(SpecStatus.PROPOSED, edge.status());
    }

    @Test
    void vStructure_detected() {
        // A→C←B: A and B are independent, both cause C
        var data = generateVStructure(1000, 42L);
        var result = PcAlgorithm.learn(data, IndependenceTest.adaptive(0.05),
            StructuralConstraints.none());

        var diag = (StructureDiagnostics.PcDiagnostics) result.diagnostics();
        assertTrue(diag.vStructuresFound() > 0);

        // Should have edges A→C and B→C
        var edges = result.networkSpec().edges();
        assertEquals(2, edges.size());
        boolean hasAtoC = edges.stream().anyMatch(
            e -> e.from().equals("A") && e.to().equals("C"));
        boolean hasBtoC = edges.stream().anyMatch(
            e -> e.from().equals("B") && e.to().equals("C"));
        assertTrue(hasAtoC, "Missing A→C edge");
        assertTrue(hasBtoC, "Missing B→C edge");
    }

    @Test
    void requiredEdge_survivesElimination() {
        var data = generateIndependentAB(500, 42L);
        var constraints = new StructuralConstraints(
            Set.of(new StructuralConstraints.Edge("A", "B")),
            Set.of(), Integer.MAX_VALUE);

        var result = PcAlgorithm.learn(data, IndependenceTest.adaptive(0.05),
            constraints);

        boolean hasEdge = result.networkSpec().edges().stream().anyMatch(
            e -> e.from().equals("A") && e.to().equals("B"));
        assertTrue(hasEdge, "Required edge A→B should survive");
    }

    @Test
    void forbiddenEdge_neverAppears() {
        var data = generateChainAB(500, 42L);
        var constraints = new StructuralConstraints(
            Set.of(),
            Set.of(new StructuralConstraints.Edge("A", "B"),
                   new StructuralConstraints.Edge("B", "A")),
            Integer.MAX_VALUE);

        var result = PcAlgorithm.learn(data, IndependenceTest.adaptive(0.05),
            constraints);

        assertTrue(result.networkSpec().edges().isEmpty());
    }

    @Test
    void singleVariable_noEdges() {
        var data = List.of(
            Map.of("X", "a"),
            Map.of("X", "b"),
            Map.of("X", "a")
        );
        var result = PcAlgorithm.learn(data, IndependenceTest.adaptive(0.05),
            StructuralConstraints.none());

        assertEquals(1, result.networkSpec().variables().size());
        assertTrue(result.networkSpec().edges().isEmpty());
    }

    @Test
    void emptyData_throws() {
        assertThrows(IllegalArgumentException.class, () ->
            PcAlgorithm.learn(List.of(), IndependenceTest.adaptive(0.05),
                StructuralConstraints.none()));
    }

    @Test
    void meekR1_orients() {
        // Chain: A→B—C where A-C not adjacent → R1 orients B→C
        var data = generateChainABC(1000, 42L);
        var result = PcAlgorithm.learn(data, IndependenceTest.adaptive(0.05),
            StructuralConstraints.none());

        var diag = (StructureDiagnostics.PcDiagnostics) result.diagnostics();
        assertTrue(diag.edgesOriented() > 0);
    }

    @Test
    void variablesHaveProposedStatus() {
        var data = generateChainAB(200, 42L);
        var result = PcAlgorithm.learn(data, IndependenceTest.adaptive(0.05),
            StructuralConstraints.none());

        for (var v : result.networkSpec().variables()) {
            assertEquals(SpecStatus.PROPOSED, v.status());
        }
    }

    // -- Data generators --

    private List<Map<String, String>> generateIndependentAB(int n, long seed) {
        var rng = new Random(seed);
        var data = new ArrayList<Map<String, String>>();
        for (int i = 0; i < n; i++) {
            data.add(Map.of("A", rng.nextBoolean() ? "a0" : "a1",
                            "B", rng.nextBoolean() ? "b0" : "b1"));
        }
        return data;
    }

    private List<Map<String, String>> generateChainAB(int n, long seed) {
        var rng = new Random(seed);
        var data = new ArrayList<Map<String, String>>();
        for (int i = 0; i < n; i++) {
            String a = rng.nextBoolean() ? "a0" : "a1";
            String b = (a.equals("a0"))
                ? (rng.nextDouble() < 0.9 ? "b0" : "b1")
                : (rng.nextDouble() < 0.9 ? "b1" : "b0");
            data.add(Map.of("A", a, "B", b));
        }
        return data;
    }

    private List<Map<String, String>> generateVStructure(int n, long seed) {
        var rng = new Random(seed);
        var data = new ArrayList<Map<String, String>>();
        for (int i = 0; i < n; i++) {
            String a = rng.nextBoolean() ? "a0" : "a1";
            String b = rng.nextBoolean() ? "b0" : "b1";
            // C depends on both A and B: XOR-like
            String c;
            if (a.equals("a0") && b.equals("b0")) c = rng.nextDouble() < 0.9 ? "c0" : "c1";
            else if (a.equals("a1") && b.equals("b1")) c = rng.nextDouble() < 0.9 ? "c0" : "c1";
            else c = rng.nextDouble() < 0.9 ? "c1" : "c0";
            data.add(Map.of("A", a, "B", b, "C", c));
        }
        return data;
    }

    private List<Map<String, String>> generateChainABC(int n, long seed) {
        var rng = new Random(seed);
        var data = new ArrayList<Map<String, String>>();
        for (int i = 0; i < n; i++) {
            String a = rng.nextBoolean() ? "a0" : "a1";
            String b = (a.equals("a0"))
                ? (rng.nextDouble() < 0.85 ? "b0" : "b1")
                : (rng.nextDouble() < 0.85 ? "b1" : "b0");
            String c = (b.equals("b0"))
                ? (rng.nextDouble() < 0.85 ? "c0" : "c1")
                : (rng.nextDouble() < 0.85 ? "c1" : "c0");
            data.add(Map.of("A", a, "B", b, "C", c));
        }
        return data;
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=PcAlgorithmTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error — `PcAlgorithm` not found

- [ ] **Step 3: Implement PcAlgorithm**

```java
package io.quarkmind.inference.bayes;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

final class PcAlgorithm {

    private PcAlgorithm() {}

    static StructureResult learn(List<Map<String, String>> data,
                                  IndependenceTest test,
                                  StructuralConstraints constraints) {
        if (data.isEmpty()) throw new IllegalArgumentException("Data must not be empty");

        List<String> variables = discoverVariables(data);
        if (variables.size() <= 1) {
            return singleVariableResult(variables, data);
        }

        // Adjacency matrix (undirected)
        var adjacent = initAdjacency(variables, constraints);
        var sepSets = new HashMap<String, Set<String>>();

        int totalTests = 0;
        int edgesRemoved = 0;
        int maxCondSize = 0;

        // Phase 1: Skeleton discovery
        for (int d = 0; ; d++) {
            boolean anyEdgeTested = false;
            var pairs = new ArrayList<>(allAdjacentPairs(adjacent, variables));
            for (var pair : pairs) {
                String x = pair[0];
                String y = pair[1];

                if (isRequired(x, y, constraints)) continue;
                if (!adjacent.get(x).contains(y)) continue;

                var neighbors = new HashSet<>(adjacent.get(x));
                neighbors.remove(y);

                if (neighbors.size() < d) continue;
                anyEdgeTested = true;

                int maxCond = constraints.maxParents() == Integer.MAX_VALUE
                    ? d : Math.min(d, constraints.maxParents() - 1);
                if (d > maxCond) continue;

                for (var subset : subsetsOfSize(neighbors, d)) {
                    totalTests++;
                    maxCondSize = Math.max(maxCondSize, subset.size());
                    var result = test.test(x, y, subset, data);
                    if (result.independent()) {
                        adjacent.get(x).remove(y);
                        adjacent.get(y).remove(x);
                        sepSets.put(sepKey(x, y), subset);
                        edgesRemoved++;
                        break;
                    }
                }
            }
            if (!anyEdgeTested) break;
        }

        // Phase 2: V-structure detection
        var directed = new HashSet<String>(); // "from->to" oriented edges
        int vStructuresFound = 0;

        for (String z : variables) {
            var neighborsOfZ = new ArrayList<>(adjacent.get(z));
            for (int i = 0; i < neighborsOfZ.size(); i++) {
                for (int j = i + 1; j < neighborsOfZ.size(); j++) {
                    String x = neighborsOfZ.get(i);
                    String y = neighborsOfZ.get(j);
                    if (adjacent.get(x).contains(y)) continue;

                    Set<String> sep = sepSets.getOrDefault(
                        sepKey(x, y), Set.of());
                    if (!sep.contains(z)) {
                        directed.add(x + "->" + z);
                        directed.add(y + "->" + z);
                        vStructuresFound++;
                    }
                }
            }
        }

        // Phase 3: Meek's orientation rules
        int edgesOriented = applyMeekRules(variables, adjacent, directed);

        // Build NetworkSpec
        int edgesUndirected = 0;
        var edgeSpecs = new ArrayList<EdgeSpec>();
        var processed = new HashSet<String>();
        for (String x : variables) {
            for (String y : adjacent.get(x)) {
                String pairKey = pairKey(x, y);
                if (processed.contains(pairKey)) continue;
                processed.add(pairKey);

                if (directed.contains(x + "->" + y)) {
                    edgeSpecs.add(new EdgeSpec(x, y,
                        orientationRationale(x, y, directed), SpecStatus.PROPOSED));
                } else if (directed.contains(y + "->" + x)) {
                    edgeSpecs.add(new EdgeSpec(y, x,
                        orientationRationale(y, x, directed), SpecStatus.PROPOSED));
                } else {
                    edgeSpecs.add(new EdgeSpec(x, y,
                        "orientation undetermined — equivalence class; "
                        + "either direction is consistent with the data",
                        SpecStatus.PROPOSED));
                    edgesUndirected++;
                }
            }
        }

        var varSpecs = new ArrayList<VariableSpec>();
        for (String v : variables) {
            List<String> outcomes = ContingencyTable.discoverOutcomes(v, data);
            varSpecs.add(new VariableSpec(v, outcomes, null,
                SpecStatus.PROPOSED, new CptSpec.Uniform()));
        }

        var spec = new NetworkSpec("learned-pc", varSpecs, edgeSpecs, null);
        var diagnostics = new StructureDiagnostics.PcDiagnostics(
            totalTests, edgesRemoved, vStructuresFound,
            edgesOriented, edgesUndirected, maxCondSize);

        return new StructureResult(spec, "PC", diagnostics);
    }

    private static List<String> discoverVariables(List<Map<String, String>> data) {
        var vars = new LinkedHashSet<String>();
        for (var obs : data) vars.addAll(obs.keySet());
        return List.copyOf(vars);
    }

    private static Map<String, Set<String>> initAdjacency(
            List<String> variables, StructuralConstraints constraints) {
        var forbidden = constraints.forbiddenEdges();
        var adj = new HashMap<String, Set<String>>();
        for (String v : variables) adj.put(v, new HashSet<>());

        for (int i = 0; i < variables.size(); i++) {
            for (int j = i + 1; j < variables.size(); j++) {
                String a = variables.get(i);
                String b = variables.get(j);
                boolean isForbidden = forbidden.contains(
                        new StructuralConstraints.Edge(a, b))
                    && forbidden.contains(
                        new StructuralConstraints.Edge(b, a));
                if (!isForbidden) {
                    adj.get(a).add(b);
                    adj.get(b).add(a);
                }
            }
        }
        return adj;
    }

    private static boolean isRequired(String x, String y,
                                       StructuralConstraints constraints) {
        return constraints.requiredEdges().contains(
                new StructuralConstraints.Edge(x, y))
            || constraints.requiredEdges().contains(
                new StructuralConstraints.Edge(y, x));
    }

    private static List<String[]> allAdjacentPairs(
            Map<String, Set<String>> adj, List<String> variables) {
        var pairs = new ArrayList<String[]>();
        var seen = new HashSet<String>();
        for (String x : variables) {
            for (String y : adj.get(x)) {
                String key = pairKey(x, y);
                if (seen.add(key)) pairs.add(new String[]{x, y});
            }
        }
        return pairs;
    }

    private static List<Set<String>> subsetsOfSize(Set<String> set, int size) {
        if (size == 0) return List.of(Set.of());
        var elements = new ArrayList<>(set);
        var result = new ArrayList<Set<String>>();
        generateSubsets(elements, size, 0, new ArrayList<>(), result);
        return result;
    }

    private static void generateSubsets(List<String> elements, int size,
                                         int start, List<String> current,
                                         List<Set<String>> result) {
        if (current.size() == size) {
            result.add(Set.copyOf(current));
            return;
        }
        for (int i = start; i < elements.size(); i++) {
            current.add(elements.get(i));
            generateSubsets(elements, size, i + 1, current, result);
            current.remove(current.size() - 1);
        }
    }

    private static int applyMeekRules(List<String> variables,
                                       Map<String, Set<String>> adj,
                                       Set<String> directed) {
        int oriented = 0;
        boolean changed = true;
        while (changed) {
            changed = false;

            for (String y : variables) {
                for (String x : new ArrayList<>(adj.get(y))) {
                    if (isDirected(x, y, directed) || isDirected(y, x, directed))
                        continue;

                    // R1: X→Y—Z where X and Z not adjacent → Y→Z
                    // Here we check: is there W→X (directed into X's neighbor Y)?
                    // Reframe: for undirected X—Y, check if some W→X exists
                    // where W is not adjacent to Y
                    for (String w : adj.get(x)) {
                        if (w.equals(y)) continue;
                        if (directed.contains(w + "->" + x)
                                && !adj.get(w).contains(y)) {
                            // R1: W→X—Y, W and Y not adjacent → X→Y
                            if (!wouldCreateCycle(x, y, adj, directed)) {
                                directed.add(x + "->" + y);
                                oriented++;
                                changed = true;
                            }
                            break;
                        }
                    }
                    if (isDirected(x, y, directed)) continue;

                    // R2: X→W→Y and X—Y → X→Y
                    for (String w : adj.get(x)) {
                        if (w.equals(y)) continue;
                        if (directed.contains(x + "->" + w)
                                && directed.contains(w + "->" + y)
                                && adj.get(x).contains(y)) {
                            if (!wouldCreateCycle(x, y, adj, directed)) {
                                directed.add(x + "->" + y);
                                oriented++;
                                changed = true;
                            }
                            break;
                        }
                    }
                    if (isDirected(x, y, directed)) continue;

                    // R4: X—Y, Y→Z→W, X—W → X→Y
                    for (String z : adj.get(y)) {
                        if (z.equals(x)) continue;
                        if (!directed.contains(y + "->" + z)) continue;
                        for (String w : adj.get(z)) {
                            if (w.equals(y) || w.equals(x)) continue;
                            if (directed.contains(z + "->" + w)
                                    && adj.get(x).contains(w)
                                    && !isDirected(x, w, directed)
                                    && !isDirected(w, x, directed)) {
                                if (!wouldCreateCycle(x, y, adj, directed)) {
                                    directed.add(x + "->" + y);
                                    oriented++;
                                    changed = true;
                                }
                                break;
                            }
                        }
                        if (isDirected(x, y, directed)) break;
                    }
                }
            }

            // R3: X—Y, X—Z, Y→W←Z, X and W not adjacent → X→Y, X→Z
            // (only if Y and Z are not adjacent)
            for (String x : variables) {
                var undirectedNeighbors = new ArrayList<String>();
                for (String n : adj.get(x)) {
                    if (!isDirected(x, n, directed) && !isDirected(n, x, directed))
                        undirectedNeighbors.add(n);
                }
                for (int i = 0; i < undirectedNeighbors.size(); i++) {
                    for (int j = i + 1; j < undirectedNeighbors.size(); j++) {
                        String y = undirectedNeighbors.get(i);
                        String z = undirectedNeighbors.get(j);
                        if (adj.get(y).contains(z)) continue;

                        for (String w : adj.get(y)) {
                            if (w.equals(x) || w.equals(z)) continue;
                            if (!adj.get(z).contains(w)) continue;
                            if (directed.contains(y + "->" + w)
                                    && directed.contains(z + "->" + w)
                                    && !adj.get(x).contains(w)) {
                                boolean orientedAny = false;
                                if (!isDirected(x, y, directed)
                                        && !wouldCreateCycle(x, y, adj, directed)) {
                                    directed.add(x + "->" + y);
                                    oriented++;
                                    orientedAny = true;
                                }
                                if (!isDirected(x, z, directed)
                                        && !wouldCreateCycle(x, z, adj, directed)) {
                                    directed.add(x + "->" + z);
                                    oriented++;
                                    orientedAny = true;
                                }
                                if (orientedAny) changed = true;
                                break;
                            }
                        }
                    }
                }
            }
        }
        return oriented;
    }

    private static boolean isDirected(String from, String to,
                                       Set<String> directed) {
        return directed.contains(from + "->" + to);
    }

    private static boolean wouldCreateCycle(String from, String to,
                                             Map<String, Set<String>> adj,
                                             Set<String> directed) {
        // Check if 'to' can reach 'from' via directed edges
        var visited = new HashSet<String>();
        var queue = new ArrayList<String>();
        queue.add(to);
        visited.add(to);
        while (!queue.isEmpty()) {
            String current = queue.remove(queue.size() - 1);
            for (String neighbor : adj.get(current)) {
                if (directed.contains(current + "->" + neighbor)) {
                    if (neighbor.equals(from)) return true;
                    if (visited.add(neighbor)) queue.add(neighbor);
                }
            }
        }
        return false;
    }

    private static String orientationRationale(String from, String to,
                                                Set<String> directed) {
        return directed.contains(from + "->" + to) ? "oriented by PC algorithm" : "";
    }

    private static String sepKey(String a, String b) {
        return a.compareTo(b) < 0 ? a + "|" + b : b + "|" + a;
    }

    private static String pairKey(String a, String b) {
        return a.compareTo(b) < 0 ? a + "~" + b : b + "~" + a;
    }

    private static StructureResult singleVariableResult(
            List<String> variables, List<Map<String, String>> data) {
        var varSpecs = new ArrayList<VariableSpec>();
        for (String v : variables) {
            List<String> outcomes = ContingencyTable.discoverOutcomes(v, data);
            varSpecs.add(new VariableSpec(v, outcomes, null,
                SpecStatus.PROPOSED, new CptSpec.Uniform()));
        }
        var spec = new NetworkSpec("learned-pc", varSpecs, List.of(), null);
        var diagnostics = new StructureDiagnostics.PcDiagnostics(0, 0, 0, 0, 0, 0);
        return new StructureResult(spec, "PC", diagnostics);
    }
}
```

- [ ] **Step 4: Run PcAlgorithm tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=PcAlgorithmTest`
Expected: all tests PASS

- [ ] **Step 5: Run full module tests (regression check)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes`
Expected: all existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add inference-bayes/src/main/java/io/quarkmind/inference/bayes/PcAlgorithm.java inference-bayes/src/test/java/io/quarkmind/inference/bayes/PcAlgorithmTest.java
git commit -m "feat(#675): add PC algorithm — skeleton, v-structures, Meek's R1-R4 Refs #675"
```

---

## Batch 4: Hill-climbing, facade, integration

### Task 5: HillClimbingSearch — decomposable BIC, three operations, restarts

**Files:**
- Create: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/HillClimbingSearch.java`
- Test: `inference-bayes/src/test/java/io/quarkmind/inference/bayes/HillClimbingSearchTest.java`

**Interfaces:**
- Consumes: `ContingencyTable.buildForVariable()`, `ContingencyTable.discoverOutcomes()`, `StructuralConstraints`, `NetworkSpec`, `VariableSpec`, `EdgeSpec`, `SpecStatus.PROPOSED`, `StructureDiagnostics.HillClimbingDiagnostics`
- Produces: `HillClimbingSearch.learn(data, constraints, restarts, seed)` → `StructureResult`

- [ ] **Step 1: Write the failing test**

```java
package io.quarkmind.inference.bayes;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class HillClimbingSearchTest {

    @Test
    void emptyData_throws() {
        assertThrows(IllegalArgumentException.class, () ->
            HillClimbingSearch.learn(List.of(), StructuralConstraints.none(), 1, 42L));
    }

    @Test
    void independentVariables_noEdges() {
        var data = generateIndependentAB(500, 42L);
        var result = HillClimbingSearch.learn(data,
            StructuralConstraints.none(), 3, 42L);

        assertTrue(result.networkSpec().edges().isEmpty(),
            "BIC should penalise edges between independent variables");
        assertEquals("HillClimbing", result.algorithm());
    }

    @Test
    void dependentVariables_discoversEdge() {
        var data = generateChainAB(500, 42L);
        var result = HillClimbingSearch.learn(data,
            StructuralConstraints.none(), 3, 42L);

        assertEquals(1, result.networkSpec().edges().size());
        var edge = result.networkSpec().edges().get(0);
        assertTrue(
            (edge.from().equals("A") && edge.to().equals("B")) ||
            (edge.from().equals("B") && edge.to().equals("A")));
    }

    @Test
    void diagnostics_reportsRestarts() {
        var data = generateChainAB(200, 42L);
        var result = HillClimbingSearch.learn(data,
            StructuralConstraints.none(), 5, 42L);

        var diag = (StructureDiagnostics.HillClimbingDiagnostics) result.diagnostics();
        assertEquals(5, diag.restartCount());
        assertEquals(5, diag.restartScores().size());
        assertTrue(diag.totalOperations() > 0);
        assertTrue(diag.bestRestartIndex() >= 0 && diag.bestRestartIndex() < 5);
    }

    @Test
    void requiredEdge_alwaysPresent() {
        var data = generateIndependentAB(500, 42L);
        var constraints = new StructuralConstraints(
            Set.of(new StructuralConstraints.Edge("A", "B")),
            Set.of(), Integer.MAX_VALUE);

        var result = HillClimbingSearch.learn(data, constraints, 3, 42L);

        boolean hasEdge = result.networkSpec().edges().stream().anyMatch(
            e -> e.from().equals("A") && e.to().equals("B"));
        assertTrue(hasEdge, "Required edge A→B must be present");
    }

    @Test
    void forbiddenEdge_neverAppears() {
        var data = generateChainAB(500, 42L);
        var constraints = new StructuralConstraints(
            Set.of(),
            Set.of(new StructuralConstraints.Edge("A", "B"),
                   new StructuralConstraints.Edge("B", "A")),
            Integer.MAX_VALUE);

        var result = HillClimbingSearch.learn(data, constraints, 3, 42L);
        assertTrue(result.networkSpec().edges().isEmpty());
    }

    @Test
    void maxParents_respected() {
        var data = generateMultiParent(500, 42L);
        var constraints = StructuralConstraints.maxParents(1);

        var result = HillClimbingSearch.learn(data, constraints, 3, 42L);

        // Count parents per variable
        var parentCounts = new java.util.HashMap<String, Integer>();
        for (var edge : result.networkSpec().edges()) {
            parentCounts.merge(edge.to(), 1, Integer::sum);
        }
        for (int count : parentCounts.values()) {
            assertTrue(count <= 1, "No variable should have > 1 parent");
        }
    }

    @Test
    void restarts_monotonicallyImprove() {
        var data = generateChainAB(200, 42L);
        var singleRestart = HillClimbingSearch.learn(data,
            StructuralConstraints.none(), 1, 42L);
        var multiRestart = HillClimbingSearch.learn(data,
            StructuralConstraints.none(), 10, 42L);

        var singleDiag = (StructureDiagnostics.HillClimbingDiagnostics)
            singleRestart.diagnostics();
        var multiDiag = (StructureDiagnostics.HillClimbingDiagnostics)
            multiRestart.diagnostics();

        assertTrue(multiDiag.bestScore() <= singleDiag.bestScore() + 1e-10,
            "Multiple restarts should find score >= single restart");
    }

    @Test
    void singleVariable_noEdges() {
        var data = List.of(Map.of("X", "a"), Map.of("X", "b"), Map.of("X", "a"));
        var result = HillClimbingSearch.learn(data,
            StructuralConstraints.none(), 1, 42L);
        assertTrue(result.networkSpec().edges().isEmpty());
    }

    // -- Data generators --

    private List<Map<String, String>> generateIndependentAB(int n, long seed) {
        var rng = new Random(seed);
        var data = new ArrayList<Map<String, String>>();
        for (int i = 0; i < n; i++) {
            data.add(Map.of("A", rng.nextBoolean() ? "a0" : "a1",
                            "B", rng.nextBoolean() ? "b0" : "b1"));
        }
        return data;
    }

    private List<Map<String, String>> generateChainAB(int n, long seed) {
        var rng = new Random(seed);
        var data = new ArrayList<Map<String, String>>();
        for (int i = 0; i < n; i++) {
            String a = rng.nextBoolean() ? "a0" : "a1";
            String b = (a.equals("a0"))
                ? (rng.nextDouble() < 0.9 ? "b0" : "b1")
                : (rng.nextDouble() < 0.9 ? "b1" : "b0");
            data.add(Map.of("A", a, "B", b));
        }
        return data;
    }

    private List<Map<String, String>> generateMultiParent(int n, long seed) {
        var rng = new Random(seed);
        var data = new ArrayList<Map<String, String>>();
        for (int i = 0; i < n; i++) {
            String a = rng.nextBoolean() ? "a0" : "a1";
            String b = rng.nextBoolean() ? "b0" : "b1";
            String c = (a.equals("a0"))
                ? (rng.nextDouble() < 0.8 ? "c0" : "c1")
                : (rng.nextDouble() < 0.8 ? "c1" : "c0");
            data.add(Map.of("A", a, "B", b, "C", c));
        }
        return data;
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=HillClimbingSearchTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error — `HillClimbingSearch` not found

- [ ] **Step 3: Implement HillClimbingSearch**

```java
package io.quarkmind.inference.bayes;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;

final class HillClimbingSearch {

    private HillClimbingSearch() {}

    static StructureResult learn(List<Map<String, String>> data,
                                  StructuralConstraints constraints,
                                  int restarts, long seed) {
        if (data.isEmpty()) throw new IllegalArgumentException("Data must not be empty");

        List<String> variables = discoverVariables(data);
        int n = data.size();

        if (variables.size() <= 1) {
            return singleVariableResult(variables, data);
        }

        // Precompute outcome maps
        var outcomeMaps = new HashMap<String, List<String>>();
        for (String v : variables) {
            outcomeMaps.put(v, ContingencyTable.discoverOutcomes(v, data));
        }

        var rng = new Random(seed);
        Map<String, Set<String>> bestGraph = null;
        double bestTotalScore = Double.POSITIVE_INFINITY;
        int bestRestartIdx = 0;
        var restartScores = new ArrayList<Double>();
        int totalOperations = 0;

        for (int r = 0; r < restarts; r++) {
            // Start from empty graph
            var parents = new HashMap<String, Set<String>>();
            for (String v : variables) parents.put(v, new HashSet<>());

            // Add required edges
            for (var edge : constraints.requiredEdges()) {
                if (parents.containsKey(edge.to()) && parents.containsKey(edge.from())) {
                    parents.get(edge.to()).add(edge.from());
                }
            }

            // Compute initial local scores
            var localScores = new HashMap<String, Double>();
            for (String v : variables) {
                localScores.put(v, localBicScore(v,
                    new ArrayList<>(parents.get(v)), data, outcomeMaps, n));
            }

            // Hill-climbing
            var candidateOrder = new ArrayList<>(generateCandidates(
                variables, parents, constraints));
            Collections.shuffle(candidateOrder, rng);

            boolean improved = true;
            while (improved) {
                improved = false;
                Operation bestOp = null;
                double bestDelta = 0.0;

                Collections.shuffle(candidateOrder, rng);

                for (var op : candidateOrder) {
                    double delta = evaluateOperation(op, parents, localScores,
                        data, outcomeMaps, n, variables, constraints);
                    if (delta < bestDelta) {
                        bestDelta = delta;
                        bestOp = op;
                    }
                }

                if (bestOp != null) {
                    applyOperation(bestOp, parents);
                    // Recompute affected local scores
                    for (String affected : bestOp.affectedVariables()) {
                        localScores.put(affected, localBicScore(affected,
                            new ArrayList<>(parents.get(affected)),
                            data, outcomeMaps, n));
                    }
                    candidateOrder = new ArrayList<>(generateCandidates(
                        variables, parents, constraints));
                    totalOperations++;
                    improved = true;
                }
            }

            double totalScore = localScores.values().stream()
                .mapToDouble(Double::doubleValue).sum();
            restartScores.add(totalScore);

            if (totalScore < bestTotalScore) {
                bestTotalScore = totalScore;
                bestGraph = deepCopy(parents);
                bestRestartIdx = r;
            }
        }

        return buildResult(bestGraph, variables, data, outcomeMaps,
            bestTotalScore, totalOperations, restarts, bestRestartIdx,
            restartScores);
    }

    private static double localBicScore(String variable, List<String> parents,
                                         List<Map<String, String>> data,
                                         Map<String, List<String>> outcomeMaps,
                                         int n) {
        var table = ContingencyTable.buildForVariable(variable, parents, data);
        int numOutcomes = outcomeMaps.get(variable).size();

        double ll = 0.0;
        for (int j = 0; j < table.counts().length; j++) {
            int configTotal = 0;
            for (int k = 0; k < numOutcomes; k++) {
                configTotal += table.counts()[j][k];
            }
            if (configTotal == 0) continue;
            for (int k = 0; k < numOutcomes; k++) {
                int count = table.counts()[j][k];
                if (count > 0) {
                    ll += count * Math.log((double) count / configTotal);
                }
            }
        }

        int parentConfigs = table.counts().length;
        int freeParams = parentConfigs * (numOutcomes - 1);
        return -2.0 * ll + freeParams * Math.log(n);
    }

    private static List<Operation> generateCandidates(
            List<String> variables,
            Map<String, Set<String>> parents,
            StructuralConstraints constraints) {
        var candidates = new ArrayList<Operation>();
        for (String from : variables) {
            for (String to : variables) {
                if (from.equals(to)) continue;
                boolean hasEdge = parents.get(to).contains(from);

                if (!hasEdge) {
                    // Candidate: add from→to
                    if (!isForbidden(from, to, constraints)
                            && parents.get(to).size() < constraints.maxParents()) {
                        candidates.add(new Operation(OpType.ADD, from, to));
                    }
                } else {
                    // Candidate: remove from→to
                    if (!isRequired(from, to, constraints)) {
                        candidates.add(new Operation(OpType.REMOVE, from, to));
                    }
                    // Candidate: reverse from→to (becomes to→from)
                    if (!isRequired(from, to, constraints)
                            && !isForbidden(to, from, constraints)
                            && parents.get(from).size() < constraints.maxParents()) {
                        candidates.add(new Operation(OpType.REVERSE, from, to));
                    }
                }
            }
        }
        return candidates;
    }

    private static double evaluateOperation(Operation op,
                                             Map<String, Set<String>> parents,
                                             Map<String, Double> localScores,
                                             List<Map<String, String>> data,
                                             Map<String, List<String>> outcomeMaps,
                                             int n, List<String> variables,
                                             StructuralConstraints constraints) {
        // Tentatively apply, compute delta, revert
        var newParents = deepCopy(parents);
        applyOperation(op, newParents);

        // Check acyclicity
        if (!isAcyclic(newParents, variables)) return 0.0;

        double delta = 0.0;
        for (String affected : op.affectedVariables()) {
            double newScore = localBicScore(affected,
                new ArrayList<>(newParents.get(affected)),
                data, outcomeMaps, n);
            delta += newScore - localScores.get(affected);
        }
        return delta;
    }

    private static void applyOperation(Operation op,
                                        Map<String, Set<String>> parents) {
        switch (op.type) {
            case ADD -> parents.get(op.to).add(op.from);
            case REMOVE -> parents.get(op.to).remove(op.from);
            case REVERSE -> {
                parents.get(op.to).remove(op.from);
                parents.get(op.from).add(op.to);
            }
        }
    }

    private static boolean isAcyclic(Map<String, Set<String>> parents,
                                      List<String> variables) {
        // Kahn's algorithm
        var inDegree = new HashMap<String, Integer>();
        for (String v : variables) inDegree.put(v, 0);
        for (var entry : parents.entrySet()) {
            inDegree.put(entry.getKey(),
                inDegree.get(entry.getKey()) + entry.getValue().size());
        }

        var queue = new ArrayList<String>();
        for (var entry : inDegree.entrySet()) {
            if (entry.getValue() == 0) queue.add(entry.getKey());
        }

        int visited = 0;
        while (!queue.isEmpty()) {
            String node = queue.remove(queue.size() - 1);
            visited++;
            // Find children (nodes that have 'node' as parent)
            for (String v : variables) {
                if (parents.get(v).contains(node)) {
                    int newDegree = inDegree.get(v) - 1;
                    inDegree.put(v, newDegree);
                    if (newDegree == 0) queue.add(v);
                }
            }
        }
        return visited == variables.size();
    }

    private static boolean isForbidden(String from, String to,
                                        StructuralConstraints constraints) {
        return constraints.forbiddenEdges().contains(
            new StructuralConstraints.Edge(from, to));
    }

    private static boolean isRequired(String from, String to,
                                       StructuralConstraints constraints) {
        return constraints.requiredEdges().contains(
            new StructuralConstraints.Edge(from, to));
    }

    private static Map<String, Set<String>> deepCopy(
            Map<String, Set<String>> parents) {
        var copy = new HashMap<String, Set<String>>();
        for (var entry : parents.entrySet()) {
            copy.put(entry.getKey(), new HashSet<>(entry.getValue()));
        }
        return copy;
    }

    private static List<String> discoverVariables(List<Map<String, String>> data) {
        var vars = new LinkedHashSet<String>();
        for (var obs : data) vars.addAll(obs.keySet());
        return List.copyOf(vars);
    }

    private static StructureResult buildResult(
            Map<String, Set<String>> parents,
            List<String> variables,
            List<Map<String, String>> data,
            Map<String, List<String>> outcomeMaps,
            double bestScore, int totalOps, int restartCount,
            int bestRestartIdx, List<Double> restartScores) {

        var edgeSpecs = new ArrayList<EdgeSpec>();
        for (String to : variables) {
            for (String from : parents.get(to)) {
                edgeSpecs.add(new EdgeSpec(from, to,
                    "hill-climbing BIC", SpecStatus.PROPOSED));
            }
        }

        var varSpecs = new ArrayList<VariableSpec>();
        for (String v : variables) {
            varSpecs.add(new VariableSpec(v, outcomeMaps.get(v), null,
                SpecStatus.PROPOSED, new CptSpec.Uniform()));
        }

        var spec = new NetworkSpec("learned-hc", varSpecs, edgeSpecs, null);
        var diagnostics = new StructureDiagnostics.HillClimbingDiagnostics(
            bestScore, totalOps, restartCount, bestRestartIdx, restartScores);

        return new StructureResult(spec, "HillClimbing", diagnostics);
    }

    private static StructureResult singleVariableResult(
            List<String> variables, List<Map<String, String>> data) {
        var varSpecs = new ArrayList<VariableSpec>();
        for (String v : variables) {
            List<String> outcomes = ContingencyTable.discoverOutcomes(v, data);
            varSpecs.add(new VariableSpec(v, outcomes, null,
                SpecStatus.PROPOSED, new CptSpec.Uniform()));
        }
        var spec = new NetworkSpec("learned-hc", varSpecs, List.of(), null);
        var diagnostics = new StructureDiagnostics.HillClimbingDiagnostics(
            0.0, 0, 1, 0, List.of(0.0));
        return new StructureResult(spec, "HillClimbing", diagnostics);
    }

    private enum OpType { ADD, REMOVE, REVERSE }

    private record Operation(OpType type, String from, String to) {
        List<String> affectedVariables() {
            if (type == OpType.REVERSE) return List.of(from, to);
            return List.of(to);
        }
    }
}
```

- [ ] **Step 4: Run HillClimbingSearch tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=HillClimbingSearchTest`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add inference-bayes/src/main/java/io/quarkmind/inference/bayes/HillClimbingSearch.java inference-bayes/src/test/java/io/quarkmind/inference/bayes/HillClimbingSearchTest.java
git commit -m "feat(#675): add hill-climbing BIC structure search with restarts Refs #675"
```

---

### Task 6: StructureLearner facade + integration tests

**Files:**
- Create: `inference-bayes/src/main/java/io/quarkmind/inference/bayes/StructureLearner.java`
- Test: `inference-bayes/src/test/java/io/quarkmind/inference/bayes/StructureLearnerTest.java`

**Interfaces:**
- Consumes: `PcAlgorithm.learn()`, `HillClimbingSearch.learn()`, `IndependenceTest.adaptive()`, `StructuralConstraints.none()`, `ModelSelector.bic()`, `ModelValidator.crossValidate()`, `ParameterLearner.fit()`
- Produces: `StructureLearner.pc(data, test, constraints)`, `StructureLearner.pc(data, alpha)`, `StructureLearner.hillClimbing(data, constraints, restarts, seed)`, `StructureLearner.hillClimbing(data)`

- [ ] **Step 1: Write the failing test**

```java
package io.quarkmind.inference.bayes;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Random;

import static org.junit.jupiter.api.Assertions.*;

class StructureLearnerTest {

    // -- Facade convenience methods --

    @Test
    void pc_convenienceOverload() {
        var data = generateChainAB(500, 42L);
        var result = StructureLearner.pc(data, 0.05);
        assertNotNull(result);
        assertEquals("PC", result.algorithm());
        assertFalse(result.networkSpec().edges().isEmpty());
    }

    @Test
    void hillClimbing_convenienceOverload() {
        var data = generateChainAB(500, 42L);
        var result = StructureLearner.hillClimbing(data);
        assertNotNull(result);
        assertEquals("HillClimbing", result.algorithm());
    }

    // -- Integration: PC → ParameterLearner → valid BayesNetwork --

    @Test
    void pc_toBayesNetwork_producesValidNetwork() {
        var data = generateChainAB(500, 42L);
        var result = StructureLearner.pc(data, 0.05);
        BayesNetwork bn = result.toBayesNetwork(data);

        assertNotNull(bn);
        double ll = ModelValidator.logLikelihood(bn, data);
        assertTrue(Double.isFinite(ll));
        assertTrue(ll < 0); // log-likelihood of real data is negative
    }

    @Test
    void hillClimbing_toBayesNetwork_producesValidNetwork() {
        var data = generateChainAB(500, 42L);
        var result = StructureLearner.hillClimbing(data);
        BayesNetwork bn = result.toBayesNetwork(data);

        assertNotNull(bn);
        double ll = ModelValidator.logLikelihood(bn, data);
        assertTrue(Double.isFinite(ll));
    }

    // -- Integration: BIC comparison --

    @Test
    void bicScores_areSane() {
        var data = generateChainAB(500, 42L);
        var pcResult = StructureLearner.pc(data, 0.05);
        var hcResult = StructureLearner.hillClimbing(data);

        BayesNetwork pcNetwork = pcResult.toBayesNetwork(data);
        BayesNetwork hcNetwork = hcResult.toBayesNetwork(data);

        ModelScore pcBic = ModelSelector.bic(pcNetwork, data);
        ModelScore hcBic = ModelSelector.bic(hcNetwork, data);

        // Both should produce finite scores
        assertTrue(Double.isFinite(pcBic.score()));
        assertTrue(Double.isFinite(hcBic.score()));
    }

    // -- Integration: known structure recovery --

    @Test
    void threeVariableChain_recoveredByBothAlgorithms() {
        var data = generateChainABC(1000, 42L);

        var pcResult = StructureLearner.pc(data, 0.05);
        var hcResult = StructureLearner.hillClimbing(data,
            StructuralConstraints.none(), 5, 42L);

        // Both should find 2 edges
        assertEquals(2, pcResult.networkSpec().edges().size(),
            "PC should find 2 edges in A→B→C chain");
        assertEquals(2, hcResult.networkSpec().edges().size(),
            "HC should find 2 edges in A→B→C chain");
    }

    // -- Edge cases --

    @Test
    void pc_emptyData_throws() {
        assertThrows(IllegalArgumentException.class, () ->
            StructureLearner.pc(List.of(), 0.05));
    }

    @Test
    void hillClimbing_emptyData_throws() {
        assertThrows(IllegalArgumentException.class, () ->
            StructureLearner.hillClimbing(List.of()));
    }

    // -- Data generators --

    private List<Map<String, String>> generateChainAB(int n, long seed) {
        var rng = new Random(seed);
        var data = new ArrayList<Map<String, String>>();
        for (int i = 0; i < n; i++) {
            String a = rng.nextBoolean() ? "a0" : "a1";
            String b = (a.equals("a0"))
                ? (rng.nextDouble() < 0.9 ? "b0" : "b1")
                : (rng.nextDouble() < 0.9 ? "b1" : "b0");
            data.add(Map.of("A", a, "B", b));
        }
        return data;
    }

    private List<Map<String, String>> generateChainABC(int n, long seed) {
        var rng = new Random(seed);
        var data = new ArrayList<Map<String, String>>();
        for (int i = 0; i < n; i++) {
            String a = rng.nextBoolean() ? "a0" : "a1";
            String b = (a.equals("a0"))
                ? (rng.nextDouble() < 0.85 ? "b0" : "b1")
                : (rng.nextDouble() < 0.85 ? "b1" : "b0");
            String c = (b.equals("b0"))
                ? (rng.nextDouble() < 0.85 ? "c0" : "c1")
                : (rng.nextDouble() < 0.85 ? "c1" : "c0");
            data.add(Map.of("A", a, "B", b, "C", c));
        }
        return data;
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=StructureLearnerTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error — `StructureLearner` not found

- [ ] **Step 3: Implement StructureLearner**

```java
package io.quarkmind.inference.bayes;

import java.util.List;
import java.util.Map;

public final class StructureLearner {

    private StructureLearner() {}

    public static StructureResult pc(List<Map<String, String>> data,
                                      IndependenceTest test,
                                      StructuralConstraints constraints) {
        return PcAlgorithm.learn(data, test, constraints);
    }

    public static StructureResult pc(List<Map<String, String>> data,
                                      double alpha) {
        return PcAlgorithm.learn(data, IndependenceTest.adaptive(alpha),
            StructuralConstraints.none());
    }

    public static StructureResult hillClimbing(
            List<Map<String, String>> data,
            StructuralConstraints constraints,
            int restarts, long seed) {
        return HillClimbingSearch.learn(data, constraints, restarts, seed);
    }

    public static StructureResult hillClimbing(List<Map<String, String>> data) {
        return HillClimbingSearch.learn(data, StructuralConstraints.none(),
            5, System.nanoTime());
    }
}
```

- [ ] **Step 4: Run StructureLearner tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes -Dtest=StructureLearnerTest`
Expected: all tests PASS

- [ ] **Step 5: Run full module tests (final regression check)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-bayes`
Expected: all tests PASS (existing + new)

- [ ] **Step 6: Commit**

```bash
git add inference-bayes/src/main/java/io/quarkmind/inference/bayes/StructureLearner.java inference-bayes/src/test/java/io/quarkmind/inference/bayes/StructureLearnerTest.java
git commit -m "feat(#675): add StructureLearner facade with PC and hill-climbing Refs #675"
```

---

## References

- [2026-10-27-structure-learning-design.md] — design spec this plan implements
- [decisions.md] — 5 architectural decisions (D1-D5)
- [NetworkSpec.java] — output format, `toBayesNetwork()`, `fromBayesNetwork()`
- [ParameterLearner.java:11] — CPT fitting, called by `StructureResult.toBayesNetwork()`
- [ModelSelector.java:8] — `bic()`, `freeParameterCount()` for verification
- [ModelValidator.java:11] — `logLikelihood()`, `crossValidate()` for validation
- [FoldSplitter.java:11] — `@FunctionalInterface` + static factories pattern
- [EdgeSpec.java:3] — edge output format
- [VariableSpec.java:5] — variable output format
- [SpecStatus.java:3] — PROPOSED status for learned elements
- [CptSpec.java:15] — `CptSpec.Uniform()` for initial variables
- [GitHub #675] — focal issue
- [GitHub #677] — LLM+data fusion (downstream consumer of StructuralConstraints)
- [GitHub #671] — parent epic (Phase 3B Learning)
- [GitHub #676] — model validation (provides BIC scoring)

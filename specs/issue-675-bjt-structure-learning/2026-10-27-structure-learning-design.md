# BJT Structure Learning from Data

**Issue:** casehubio/neocortex#675
**Parent:** casehubio/neocortex#671 (Epic: BJT Phase 3B — Learning)
**Module:** `inference-bayes`
**Package:** `io.quarkmind.inference.bayes`

## Overview

Learn DAG structure from tabular observations. Two algorithms: PC (constraint-based, discovers causal direction via conditional independence tests) and greedy hill-climbing (score-based, optimises BIC fit by searching DAG space). Both produce `NetworkSpec` (reviewable) or `BayesNetwork` (ready to use). Pure Java, zero CDI, zero external dependencies.

This is the data-driven counterpart to `NetworkElicitor` (LLM-based structure). Issue #677 (LLM+data fusion) will combine both — `StructuralConstraints` is the integration point.

## 1. StructureLearner — Public Facade

### API

```java
public final class StructureLearner {

    public static StructureResult pc(
            List<Map<String, String>> data,
            IndependenceTest test,
            StructuralConstraints constraints) { ... }

    public static StructureResult pc(
            List<Map<String, String>> data,
            double alpha) { ... }  // convenience: adaptive test, no constraints

    public static StructureResult hillClimbing(
            List<Map<String, String>> data,
            StructuralConstraints constraints,
            int restarts,
            long seed) { ... }

    public static StructureResult hillClimbing(
            List<Map<String, String>> data) { ... }  // convenience: no constraints, 5 restarts
}
```

The convenience overloads use `IndependenceTest.adaptive(0.05)` and default settings. The full overloads expose all configuration.

### StructureResult

```java
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

`toBayesNetwork()` calls `ParameterLearner.fit()` to produce a ready-to-use network with learned CPTs. The `NetworkSpec` retains `SpecStatus.PROPOSED` for edges that are data-discovered — the user or #677 can review, accept, or reject edges before fitting.

### StructureDiagnostics

```java
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

Sealed interface — the caller knows which algorithm produced the result and can switch on the type for algorithm-specific diagnostics.

## 2. StructuralConstraints

```java
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

Used by both algorithms:
- **PC:** required edges skip CI elimination (never removed during skeleton discovery). Forbidden edges skip CI testing (never added). Max parents limits conditioning set size.
- **Hill-climbing:** required edges can't be removed or reversed. Forbidden edges can't be added. Max parents checked before add/reverse.

## 3. IndependenceTest — Conditional Independence Testing

### API

```java
@FunctionalInterface
public interface IndependenceTest {

    IndependenceResult test(String x, String y, Set<String> conditioningSet,
                            List<Map<String, String>> data);

    record IndependenceResult(boolean independent, double pValue, double statistic) {}

    static IndependenceTest gTest(double alpha) { ... }
    static IndependenceTest fisherExact(double alpha) { ... }
    static IndependenceTest adaptive(double alpha) { ... }
}
```

### G-Test (Log-Likelihood Ratio)

The G-test statistic for testing X ⊥ Y | Z:

```
G = 2 × Σ O_ijk × ln(O_ijk / E_ijk)
```

where `O_ijk` is the observed count for (X=i, Y=j, Z=k) and `E_ijk` is the expected count under independence: `E_ijk = (O_i.k × O_.jk) / O_..k`.

Degrees of freedom: `(|X| - 1) × (|Y| - 1) × |Z_configs|` where `|Z_configs|` is the number of conditioning set configurations.

Compare G to chi-squared distribution at `alpha` significance level. P-value computed via the regularised incomplete gamma function (pure Java implementation — no external stats library).

### Fisher's Exact Test

For 2×2 contingency tables (binary X, binary Y, each conditioning configuration):
- Compute the hypergeometric probability of the observed table
- Sum probabilities of all tables at least as extreme (two-sided)
- P-value is this sum

For larger tables: use the network algorithm for Fisher's exact test on r×c tables (Freeman & Halton extension). Fall back to G-test if the table exceeds 5×5 (Fisher's becomes computationally infeasible).

### Adaptive (Recommended Default)

For each conditioning configuration's contingency table:
- If any expected cell count < 5: use Fisher's exact test
- Otherwise: use G-test

This matches standard statistical practice — chi-squared approximation is unreliable when expected counts are small.

## 4. PC Algorithm

### Phase 1: Skeleton Discovery

Start with a complete undirected graph (all variables connected). For increasing conditioning set sizes d = 0, 1, 2, ...:

1. For each pair of adjacent variables (X, Y):
2. For each subset S of size d from the neighbours of X (excluding Y):
3. Test X ⊥ Y | S
4. If independent: remove the edge X—Y, record S as the separating set `Sep(X, Y)`
5. Stop when d exceeds the maximum neighbour count for all variables

**Constraint integration:**
- Required edges: skip CI testing, never remove
- Forbidden edges: not in the initial graph, never add
- Max parents: limit conditioning set size to `maxParents - 1`

### Phase 2: V-Structure Detection

For each triple (X, Z, Y) where X—Z and Z—Y but X and Y are not adjacent:
- If Z is NOT in Sep(X, Y): orient as X→Z←Y (v-structure / collider)

### Phase 3: Meek's Orientation Rules (iterative)

Apply until no more edges can be oriented:

- **R1:** If X→Y—Z and X and Z are not adjacent → orient Y→Z
- **R2:** If X→Y→Z and X—Z → orient X→Z
- **R3:** If X—Y, X—Z, Y→W←Z, and X and W are not adjacent → orient X→Y and X→Z (but only if Y and Z are not adjacent to each other — prevents creating cycles)
- **R4:** If X—Y, Y→Z→W, and X—W → orient X→Y

### Output

Each oriented edge becomes `EdgeSpec(from, to, rationale, SpecStatus.PROPOSED)` where rationale describes the orientation reason ("v-structure", "Meek R1", etc.).

Undirected edges (CPDAG — orientation undetermined from data alone) become two `EdgeSpec` entries with `SpecStatus.PROPOSED` and rationale "orientation undetermined — equivalence class; either direction is consistent with the data." Only one direction is included in the final `NetworkSpec` (arbitrary but consistent choice), with the rationale noting the ambiguity.

Variables are extracted from the data columns with `SpecStatus.PROPOSED` and uniform `CptSpec`.

## 5. Hill-Climbing with BIC

### Decomposable Local Scoring

BIC decomposes into per-variable local scores:

```
BIC(G, D) = Σ_i LocalScore(Xi, Parents_i, D)
LocalScore(Xi, Pa_i, D) = LL_i(Xi | Pa_i, D) - (k_i / 2) × ln(n)
```

where `LL_i` is the log-likelihood of Xi given its parents across all observations, and `k_i = |Pa_i_configs| × (|Xi_outcomes| - 1)`.

Pre-compute contingency tables (joint counts of each variable with its parents) for all variables. When evaluating a candidate edge operation, only recompute the affected variable(s)' local score from their contingency table.

### Search Loop

For each restart r = 0, 1, ..., restarts-1:

1. Start from the empty graph (no edges)
2. Compute initial local scores for all variables
3. Repeat:
   a. Generate all candidate operations: add(X→Y), remove(X→Y), reverse(X→Y) for all variable pairs
   b. Filter by constraints: skip forbidden adds, required removes/reverses, max parent violations, acyclicity violations
   c. For each candidate: compute the score delta (recompute only affected variable(s)' local scores)
   d. Accept the candidate with the greatest positive score delta
   e. If no candidate improves the score: terminate this restart
4. Record the final DAG and its total BIC score

Return the result from the restart with the best (lowest) total BIC score.

### Acyclicity Check

Before accepting an add or reverse operation, verify the resulting graph is acyclic. Use topological sort (Kahn's algorithm) — if the sort doesn't visit all nodes, the graph has a cycle. This is O(V + E) per check, which is acceptable since it only runs for the winning candidate, not all candidates.

Optimisation: maintain a topological order and use incremental reachability to check whether add(X→Y) would create a cycle (is Y already an ancestor of X?). This avoids the full sort for rejecting most candidates. Fall back to full sort when incremental check is ambiguous.

### Random Restart Diversity

Each restart shuffles the order in which candidate operations are evaluated. Since the algorithm accepts the *best* operation (not the first improvement), this only matters when multiple candidates have the same score delta — the shuffle breaks ties differently across restarts.

## 6. Contingency Table Utilities

Shared between G-test, Fisher's exact test, and hill-climbing local scoring. Package-private.

```java
record ContingencyTable(int[][] counts, int[] rowTotals, int[] colTotals, int total) {

    static ContingencyTable build(String x, String y, Set<String> conditioningSet,
                                   List<Map<String, String>> data,
                                   Map<String, String[]> outcomeMap) { ... }
}
```

For conditional independence testing: one contingency table per conditioning configuration. For local scoring: one table per variable (columns = variable outcomes, rows = parent configurations).

## Edge Cases

- **Empty data:** throw `IllegalArgumentException`
- **Single variable:** return a single-node NetworkSpec (no edges to learn)
- **All variables independent:** PC returns empty skeleton. Hill-climbing returns empty graph (BIC penalises all edges).
- **Fully connected data:** PC retains all edges. Hill-climbing adds edges until BIC penalty outweighs fit.
- **Missing values:** skip observations with missing values for the tested variables (consistent with ParameterLearner)
- **Deterministic relationships:** G-test produces very high statistics (effectively zero p-value). Fisher's handles correctly. Hill-climbing: BIC still applies complexity penalty.
- **Insufficient data for conditioning:** when a conditioning configuration has zero observations, skip that configuration in the CI test

## Testing Strategy

### Independence Tests
- Known independent variables → test returns independent
- Known dependent variables → test returns dependent
- Deterministic relationship → correct detection
- Empty conditioning set → marginal independence test
- Large conditioning set → sparse table handling (Fisher's fallback)
- P-value sanity: uniform data → p-values near 1.0

### PC Algorithm
- Known DAG → learn structure from generated data → recover correct skeleton
- V-structure detection on A→C←B (no A—B edge)
- Meek's rules: each rule tested individually with a minimal graph that triggers only that rule
- Constraint integration: required edge survives CI test, forbidden edge not in skeleton
- CPDAG output: undirected edges marked correctly

### Hill-Climbing
- Known DAG → learn structure from generated data → BIC prefers correct structure over alternatives
- Empty data → exception
- Constraints: required edge present in result, forbidden edge absent
- Max parents: no variable exceeds limit
- Restarts: result is at least as good as single-run (monotonic improvement)
- Decomposed score matches whole-network BIC (ModelSelector.bic()) for verification

### Integration
- PC output → ParameterLearner.fit() → valid BayesNetwork with correct posteriors
- Hill-climbing output → cross-validate with ModelValidator → reasonable generalisation
- Compare PC and hill-climbing on same data → BIC comparison shows which fits better

## Non-Goals

- Latent variable detection (FCI algorithm — different algorithm family)
- Continuous variables (requires different CI tests — #683)
- LLM+data fusion (that's #677 — uses StructuralConstraints as its integration point)
- Online / streaming structure learning
- Parallel / multi-threaded search

## References

- `NetworkSpec.java` — output format, `toBayesNetwork()`, `fromBayesNetwork()`
- `NetworkElicitor.java` — LLM-based structure learning, produces NetworkSpec with PROPOSED status
- `ParameterLearner.java` — CPT fitting, called by `StructureResult.toBayesNetwork()`
- `ModelSelector.java` — `bic()`, `freeParameterCount()` from #676 — whole-network BIC verification
- `ModelValidator.java` — `logLikelihood()`, `crossValidate()` from #676 — validation after learning
- `FoldSplitter.java` — `@FunctionalInterface` + static factories pattern from #676
- `SpecStatus.java` — PROPOSED status for learned edges
- `EdgeSpec.java`, `VariableSpec.java` — NetworkSpec components
- casehubio/neocortex#676 — model validation (just landed, provides BIC scoring)
- casehubio/neocortex#677 — LLM+data fusion (downstream consumer of StructuralConstraints)
- casehubio/neocortex#671 — parent epic (Phase 3B Learning)
- Spirtes, Glymour, Scheines (2000) — Causation, Prediction, and Search (PC algorithm)
- Meek (1995) — Causal inference and causal explanation with background knowledge (orientation rules)
- Koller & Friedman (2009) — Probabilistic Graphical Models §18 (score-based learning, decomposable scores)
- Heckerman, Geiger, Chickering (1995) — Learning Bayesian Networks (hill-climbing, BIC)
- Agresti (2002) — Categorical Data Analysis (G-test, Fisher's exact test)

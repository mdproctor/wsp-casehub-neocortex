# Cross-Domain Correlation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #324 — MoodEvents + ExperienceEvents cross-domain correlation
**Issue group:** #324, #322, #300, #298

**Goal:** Extend DomainActivation to correlate agent mood and experience events against per-subgraph affect trajectories, with statistical significance testing.

**Architecture:** Two new correlation types added to `DomainActivation.correlate()`: (1) mood-affect DTW on time-bucketed 3D PAD with Sakoe-Chiba banding and circular shift significance, (2) experience-affect event-triggered windows measuring Δ(affect) pre/post each event per PAD dimension. Extensible via `MemoryDomain`-keyed maps. `MoodState` gains optional `activeContextIds` for domain partitioning.

**Tech Stack:** Java 21 (on Java 26 JVM), Quarkus 3.32.2, JUnit 5

## Global Constraints

- Java 21 language level, Java 26 JVM: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn`
- Use `mvn` not `./mvnw`
- Use `ide_*` tools for all code navigation and structural editing
- TDD: write failing test -> verify fail -> implement -> verify pass -> commit
- All commits reference issue: `Refs #324`

---

## Batch 1: MoodState Pipeline Change

### Task 1: MoodState `activeContextIds` + MoodEvents + MoodDecay migration

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodState.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodAttributeKeys.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodEvents.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodDecay.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/mood/MoodStateTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/mood/MoodEventsTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/mood/MoodDecayTest.java`
- Modify: all `new MoodState(...)` call sites in neocortex (see step 7)

**Interfaces:**
- Produces: `MoodState` record with `activeContextIds: Set<String>` (nullable, positioned before `metadata`)
- Produces: `MoodAttributeKeys.ACTIVE_CONTEXT_IDS` constant
- Produces: `MoodEvents.toMemoryInput()` stores context IDs when present
- Produces: `MoodDecay.decay()` preserves `activeContextIds` from input

- [ ] **Step 1: Write failing test for MoodState with activeContextIds**

Add test to `MoodStateTest.java`:

```java
@Test
void acceptsActiveContextIds() {
    var ids = Set.of("sg-work", "sg-family");
    var state = new MoodState("a1", "t1", null, 0.5, 0.0, 0.0,
                              "test", null, ids, Map.of());
    assertEquals(ids, state.activeContextIds());
}

@Test
void acceptsNullActiveContextIds() {
    var state = new MoodState("a1", "t1", null, 0.5, 0.0, 0.0,
                              "test", null, null, Map.of());
    assertNull(state.activeContextIds());
}

@Test
void defensivelyCopiesActiveContextIds() {
    var ids = new HashSet<>(Set.of("sg-work"));
    var state = new MoodState("a1", "t1", null, 0.5, 0.0, 0.0,
                              "test", null, ids, Map.of());
    ids.add("injected");
    assertFalse(state.activeContextIds().contains("injected"));
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=MoodStateTest#acceptsActiveContextIds -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error — MoodState constructor doesn't accept the new parameter

- [ ] **Step 3: Add activeContextIds to MoodState record**

Modify `MoodState.java` — add `Set<String> activeContextIds` field between `turnId` and `metadata`. Update compact constructor to defensively copy when non-null:

```java
public record MoodState(
        String agentId, String tenantId, Instant timestamp,
        double pleasure, double arousal, double dominance,
        String cause, String turnId,
        Set<String> activeContextIds,
        Map<String, String> metadata
) {
    public MoodState {
        if (timestamp == null) timestamp = Instant.now();
        Objects.requireNonNull(agentId, "agentId required");
        Objects.requireNonNull(tenantId, "tenantId required");
        Objects.requireNonNull(cause, "cause required");
        if (cause.isBlank()) throw new IllegalArgumentException("cause must not be blank");
        validateAxis("pleasure", pleasure);
        validateAxis("arousal", arousal);
        validateAxis("dominance", dominance);
        if (activeContextIds != null) activeContextIds = Set.copyOf(activeContextIds);
        Objects.requireNonNull(metadata, "metadata required");
        metadata = Map.copyOf(metadata);
    }

    // existing validateAxis method unchanged
}
```

- [ ] **Step 4: Fix all MoodState constructor call sites in neocortex**

Use `ide_find_references` on `MoodState` to find all `new MoodState(...)` calls. Add `null` as the `activeContextIds` argument (the parameter before `metadata`).

Key locations in neocortex repo:
- `MoodDecay.java:24` — `new MoodState(...)` in `decay()` method (handle separately in step 6)
- `MoodEventsTest.java:17,34,41` — test constructors
- `MoodStateTest.java` — multiple test constructors (existing tests already being modified)
- `MoodDecayTest.java` — test constructors
- `ModulationIntegrationTest.java:30,61` — test constructors
- `ModulationFactorsTest.java:73,85,94` — test constructors

Pattern: insert `null,` before the last `Map.of()` argument in every call.

- [ ] **Step 5: Run MoodState tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=MoodStateTest`
Expected: all tests PASS including the 3 new tests

- [ ] **Step 6: Write failing test for MoodDecay preserving activeContextIds**

Add test to `MoodDecayTest.java`:

```java
@Test
void preservesActiveContextIds() {
    var ids = Set.of("sg-work", "sg-family");
    var current = new MoodState("a", "t", null, 0.8, 0.5, 0.3,
                                "happy", "turn-1", ids, Map.of());
    var baseline = new MoodBaseline(0.0, 0.0, 0.0);
    var result = MoodDecay.decay(current, baseline,
                                 Duration.ofHours(6), Duration.ofHours(6));
    assertEquals(ids, result.activeContextIds());
}
```

- [ ] **Step 7: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=MoodDecayTest#preservesActiveContextIds`
Expected: FAIL — `MoodDecay.decay()` passes wrong number of args or `null` for activeContextIds

- [ ] **Step 8: Update MoodDecay.decay() to preserve activeContextIds**

Modify `MoodDecay.java` — the `new MoodState(...)` call at line 24. Pass `current.activeContextIds()` as the activeContextIds argument:

```java
return new MoodState(
        current.agentId(),
        current.tenantId(),
        null,
        decayAxis(current.pleasure(), baseline.pleasure(), factor),
        decayAxis(current.arousal(), baseline.arousal(), factor),
        decayAxis(current.dominance(), baseline.dominance(), factor),
        "decay",
        null,
        current.activeContextIds(),
        Map.of()
);
```

- [ ] **Step 9: Run MoodDecay tests to verify all pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=MoodDecayTest`
Expected: all PASS

- [ ] **Step 10: Write failing test for MoodEvents storing activeContextIds**

Add to `MoodAttributeKeys.java`:

```java
public static final String ACTIVE_CONTEXT_IDS = "active-context-ids";
```

Add test to `MoodEventsTest.java`:

```java
@Test
void storesActiveContextIdsWhenPresent() {
    var state = new MoodState("a1", "t1", null, 0.5, 0.0, 0.0,
                              "test", null, Set.of("sg-work", "sg-family"), Map.of());
    var input = MoodEvents.toMemoryInput(state);
    String value = input.attributes().get(MoodAttributeKeys.ACTIVE_CONTEXT_IDS);
    assertNotNull(value);
    assertTrue(value.contains("sg-work"));
    assertTrue(value.contains("sg-family"));
}

@Test
void omitsActiveContextIdsWhenNull() {
    var state = new MoodState("a1", "t1", null, 0.5, 0.0, 0.0,
                              "test", null, null, Map.of());
    var input = MoodEvents.toMemoryInput(state);
    assertFalse(input.attributes().containsKey(MoodAttributeKeys.ACTIVE_CONTEXT_IDS));
}
```

- [ ] **Step 11: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=MoodEventsTest#storesActiveContextIdsWhenPresent`
Expected: FAIL — attribute not present

- [ ] **Step 12: Update MoodEvents.toMemoryInput() to store activeContextIds**

Add to `MoodEvents.toMemoryInput()`, after the existing timestamp handling:

```java
if (state.activeContextIds() != null && !state.activeContextIds().isEmpty()) {
    reserved.add(MoodAttributeKeys.ACTIVE_CONTEXT_IDS);
    attrs.put(MoodAttributeKeys.ACTIVE_CONTEXT_IDS,
              String.join(",", state.activeContextIds()));
}
```

- [ ] **Step 13: Run all memory-api mood tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest="MoodStateTest+MoodEventsTest+MoodDecayTest"`
Expected: all PASS

- [ ] **Step 14: Build full project to verify no breakage**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Expected: BUILD SUCCESS (all modules compile)

If compilation fails in external modules (blocks etc.) that are not in the neocortex build, those are downstream breakages to track separately.

- [ ] **Step 15: Commit**

```bash
git add -A
git commit -m "feat(memory-api): add activeContextIds to MoodState for domain-partitioned correlation

MoodState gains optional Set<String> activeContextIds for associating mood
snapshots with active subgraph context. Null/empty = agent-global fallback.
MoodDecay preserves context IDs through decay. MoodEvents stores them as
comma-separated attribute.

Refs #324"
```

---

## Batch 2: Algorithm Utilities

### Task 2: PadDtw warping constraints + circular shift significance

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PadDtw.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DomainCorrelation.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CorrelationStrength.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DomainActivation.java` (fix constructor calls only)
- Create: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/PadDtwTest.java`

**Interfaces:**
- Consumes: `WarpingConstraint` sealed interface from `io.casehub.neocortex.memory.cbr` (already on classpath via memory-api dependency)
- Produces: `PadDtw.compute(double[][], double[][], WarpingConstraint)` — warped DTW
- Produces: `PadDtw.significanceTest(double[][], double[][], WarpingConstraint, int surrogates, long seed)` → `SignificanceResult(double similarity, double pValue, CorrelationStrength strength)`
- Produces: `DomainCorrelation` with `pValue`, `contextAttributedCount`, `totalMoodCount` fields
- Produces: `CorrelationStrength.fromSimilarity(double s, double pValue)` overload

- [ ] **Step 1: Write failing tests for DomainCorrelation with new fields**

Create `PadDtwTest.java`:

```java
package io.casehub.neocortex.cognitive.index;

import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class PadDtwTest {

    @Test
    void domainCorrelationAcceptsPValue() {
        var dc = new DomainCorrelation(0.8, List.of(), 10,
                     CorrelationStrength.STRONG, 0.01, 0, 0);
        assertEquals(0.01, dc.pValue(), 1e-9);
    }

    @Test
    void domainCorrelationAcceptsAttributionCounts() {
        var dc = new DomainCorrelation(0.8, List.of(), 10,
                     CorrelationStrength.STRONG, 0.01, 5, 8);
        assertEquals(5, dc.contextAttributedCount());
        assertEquals(8, dc.totalMoodCount());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=PadDtwTest#domainCorrelationAcceptsPValue -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error

- [ ] **Step 3: Update DomainCorrelation record**

```java
public record DomainCorrelation(
        double dtwSimilarity,
        List<DtwAlignment> alignment,
        int samplePairs,
        CorrelationStrength strength,
        double pValue,
        int contextAttributedCount,
        int totalMoodCount
) {
    public DomainCorrelation {
        alignment = List.copyOf(alignment);
    }
}
```

- [ ] **Step 4: Fix existing DomainCorrelation constructor calls in DomainActivation.java**

Two call sites at lines ~104 and ~111. Add `Double.NaN, 0, 0` as the last three arguments:

```java
// Line ~104 (insufficient data path):
correlations.put(pair, new DomainCorrelation(
        0.0, List.of(), Math.min(a.length, b.length),
        CorrelationStrength.NONE, Double.NaN, 0, 0));

// Line ~111 (DTW result path):
correlations.put(pair, new DomainCorrelation(
        dtw.similarity(), dtw.alignment(),
        Math.min(a.length, b.length),
        CorrelationStrength.fromSimilarity(dtw.similarity()),
        Double.NaN, 0, 0));
```

- [ ] **Step 5: Run tests to verify DomainCorrelation changes compile and pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest="PadDtwTest+DomainActivationTest"`
Expected: PadDtwTest PASS, DomainActivationTest PASS (existing tests still work)

- [ ] **Step 6: Write failing test for CorrelationStrength significance overload**

Add to `PadDtwTest.java`:

```java
@Test
void fromSimilarityWithSignificance_strongAndSignificant() {
    assertEquals(CorrelationStrength.STRONG,
                 CorrelationStrength.fromSimilarity(0.8, 0.01));
}

@Test
void fromSimilarityWithSignificance_strongButInsignificant_downgraded() {
    assertEquals(CorrelationStrength.WEAK,
                 CorrelationStrength.fromSimilarity(0.8, 0.10));
}

@Test
void fromSimilarityWithSignificance_moderateAndSignificant() {
    assertEquals(CorrelationStrength.MODERATE,
                 CorrelationStrength.fromSimilarity(0.5, 0.03));
}

@Test
void fromSimilarityWithSignificance_nanPValue_noDowngrade() {
    assertEquals(CorrelationStrength.STRONG,
                 CorrelationStrength.fromSimilarity(0.8, Double.NaN));
}
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=PadDtwTest#fromSimilarityWithSignificance_strongAndSignificant`
Expected: compilation error — overload doesn't exist

- [ ] **Step 8: Implement CorrelationStrength.fromSimilarity(double, double)**

```java
public static CorrelationStrength fromSimilarity(double s, double pValue) {
    CorrelationStrength base = fromSimilarity(s);
    if (Double.isNaN(pValue)) return base;
    if (pValue >= 0.05 && (base == STRONG || base == MODERATE)) return WEAK;
    return base;
}
```

- [ ] **Step 9: Run CorrelationStrength tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=PadDtwTest`
Expected: all PASS

- [ ] **Step 10: Write failing tests for PadDtw warping constraint**

Add to `PadDtwTest.java`:

```java
@Test
void computeWithUnconstrainedMatchesDefault() {
    double[][] a = {{0.1, 0.2, 0.3}, {0.4, 0.5, 0.6}, {0.7, 0.8, 0.9}};
    double[][] b = {{0.1, 0.2, 0.3}, {0.5, 0.5, 0.5}, {0.8, 0.9, 1.0}};
    var unconstrained = PadDtw.compute(a, b, new WarpingConstraint.Unconstrained());
    var defaultResult = PadDtw.compute(a, b);
    assertEquals(defaultResult.similarity(), unconstrained.similarity(), 1e-9);
}

@Test
void computeWithSakoeChibaReducesSimilarityForLargeOffset() {
    double[][] a = new double[20][3];
    double[][] b = new double[20][3];
    for (int i = 0; i < 20; i++) {
        a[i] = new double[]{i * 0.05, 0.0, 0.0};
        int shifted = (i + 10) % 20;
        b[i] = new double[]{shifted * 0.05, 0.0, 0.0};
    }
    var wide = PadDtw.compute(a, b, new WarpingConstraint.SakoeChibaBand(15));
    var narrow = PadDtw.compute(a, b, new WarpingConstraint.SakoeChibaBand(3));
    assertTrue(wide.similarity() > narrow.similarity(),
               "narrow band should reduce similarity for large offset");
}

@Test
void computeWithNullConstraintIsUnconstrained() {
    double[][] a = {{0.1, 0.2, 0.3}, {0.4, 0.5, 0.6}};
    double[][] b = {{0.2, 0.3, 0.4}, {0.5, 0.6, 0.7}};
    var result = PadDtw.compute(a, b, null);
    var defaultResult = PadDtw.compute(a, b);
    assertEquals(defaultResult.similarity(), result.similarity(), 1e-9);
}
```

- [ ] **Step 11: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=PadDtwTest#computeWithUnconstrainedMatchesDefault`
Expected: compilation error — overload doesn't exist

- [ ] **Step 12: Implement PadDtw.compute with WarpingConstraint**

Add import for `io.casehub.neocortex.memory.cbr.WarpingConstraint` to `PadDtw.java`. Add new overload:

```java
static DtwResult compute(double[][] query, double[][] candidate,
                         WarpingConstraint constraint) {
    if (constraint == null) return compute(query, candidate);
    int n = query.length, m = candidate.length;
    if (n == 0 || m == 0) {
        return new DtwResult(Double.MAX_VALUE, 0.0, List.of());
    }

    int dims = query[0].length;
    double[][] cost = new double[n + 1][m + 1];
    for (int i = 0; i <= n; i++) { cost[i][0] = Double.MAX_VALUE; }
    for (int j = 0; j <= m; j++) { cost[0][j] = Double.MAX_VALUE; }
    cost[0][0] = 0;

    for (int i = 1; i <= n; i++) {
        for (int j = 1; j <= m; j++) {
            if (!isWithinConstraint(i - 1, j - 1, n, m, constraint)) {
                cost[i][j] = Double.MAX_VALUE;
                continue;
            }
            double d = euclidean(query[i - 1], candidate[j - 1], dims);
            cost[i][j] = d + Math.min(cost[i - 1][j],
                              Math.min(cost[i][j - 1], cost[i - 1][j - 1]));
        }
    }

    if (cost[n][m] == Double.MAX_VALUE) {
        return new DtwResult(Double.MAX_VALUE, 0.0, List.of());
    }

    double normalizedCost = cost[n][m] / Math.max(n, m);

    List<DtwAlignment> alignment = new ArrayList<>();
    int i = n, j = m;
    while (i > 0 && j > 0) {
        alignment.add(new DtwAlignment(i - 1, j - 1));
        double diag = cost[i - 1][j - 1];
        double left = cost[i][j - 1];
        double up   = cost[i - 1][j];
        if (diag <= left && diag <= up) { i--; j--; }
        else if (up <= left) { i--; }
        else { j--; }
    }
    Collections.reverse(alignment);

    double similarity = 1.0 / (1.0 + normalizedCost);
    return new DtwResult(normalizedCost, similarity, alignment);
}

private static boolean isWithinConstraint(int i, int j, int n, int m,
                                          WarpingConstraint constraint) {
    return switch (constraint) {
        case WarpingConstraint.Unconstrained u -> true;
        case WarpingConstraint.SakoeChibaBand band -> {
            double scaledI = (double) i * m / n;
            yield Math.abs(scaledI - j) <= band.windowSize();
        }
        case WarpingConstraint.ItakuraParallelogram para -> {
            double maxSlope = para.maxSlope();
            double minSlope = 1.0 / maxSlope;
            double jLow  = minSlope * i;
            double jHigh = maxSlope * i + (m - 1) - maxSlope * (n - 1);
            yield j >= Math.ceil(jLow) && j <= Math.floor(jHigh);
        }
    };
}
```

- [ ] **Step 13: Run warping constraint tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=PadDtwTest`
Expected: all PASS

- [ ] **Step 14: Write failing tests for circular shift significance**

Add to `PadDtwTest.java`:

```java
@Test
void significanceTest_correlatedSeries_lowPValue() {
    double[][] a = new double[30][3];
    double[][] b = new double[30][3];
    for (int i = 0; i < 30; i++) {
        double v = i * 0.03;
        a[i] = new double[]{v, v * 0.5, v * 0.3};
        b[i] = new double[]{v + 0.01, v * 0.5 + 0.01, v * 0.3 + 0.01};
    }
    var result = PadDtw.significanceTest(a, b, null, 200, 42L);
    assertTrue(result.pValue() < 0.05, "correlated series should have p < 0.05");
    assertNotEquals(CorrelationStrength.WEAK, result.strength());
}

@Test
void significanceTest_randomSeries_highPValue() {
    var rng = new java.util.Random(123);
    double[][] a = new double[30][3];
    double[][] b = new double[30][3];
    for (int i = 0; i < 30; i++) {
        a[i] = new double[]{rng.nextDouble(), rng.nextDouble(), rng.nextDouble()};
        b[i] = new double[]{rng.nextDouble(), rng.nextDouble(), rng.nextDouble()};
    }
    var result = PadDtw.significanceTest(a, b, null, 200, 42L);
    assertTrue(result.pValue() >= 0.05, "random series should have p >= 0.05");
}

@Test
void significanceTest_deterministicSeed() {
    double[][] a = {{0.1, 0.2, 0.3}, {0.4, 0.5, 0.6}, {0.7, 0.8, 0.9}};
    double[][] b = {{0.2, 0.3, 0.4}, {0.5, 0.6, 0.7}, {0.8, 0.9, 1.0}};
    var r1 = PadDtw.significanceTest(a, b, null, 50, 99L);
    var r2 = PadDtw.significanceTest(a, b, null, 50, 99L);
    assertEquals(r1.pValue(), r2.pValue(), 1e-9);
}
```

- [ ] **Step 15: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=PadDtwTest#significanceTest_correlatedSeries_lowPValue`
Expected: compilation error — method doesn't exist

- [ ] **Step 16: Implement PadDtw.significanceTest**

Add to `PadDtw.java`:

```java
record SignificanceResult(double similarity, double pValue,
                          CorrelationStrength strength) {}

static SignificanceResult significanceTest(double[][] query, double[][] candidate,
                                          WarpingConstraint constraint,
                                          int surrogates, long seed) {
    DtwResult observed = constraint != null
                         ? compute(query, candidate, constraint)
                         : compute(query, candidate);

    int n = candidate.length;
    if (n < 3) {
        return new SignificanceResult(observed.similarity(), Double.NaN,
                   CorrelationStrength.fromSimilarity(observed.similarity()));
    }

    var rng = new java.util.Random(seed);
    int atLeastAsGood = 0;
    for (int s = 0; s < surrogates; s++) {
        int shift = 1 + rng.nextInt(n - 1);
        double[][] shifted = new double[n][];
        for (int i = 0; i < n; i++) {
            shifted[i] = candidate[(i + shift) % n];
        }
        DtwResult surrogate = constraint != null
                              ? compute(query, shifted, constraint)
                              : compute(query, shifted);
        if (surrogate.similarity() >= observed.similarity()) {
            atLeastAsGood++;
        }
    }

    double pValue = (double) atLeastAsGood / surrogates;
    return new SignificanceResult(observed.similarity(), pValue,
               CorrelationStrength.fromSimilarity(observed.similarity(), pValue));
}
```

- [ ] **Step 17: Run all PadDtw tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=PadDtwTest`
Expected: all PASS

- [ ] **Step 18: Run full cognitive-index tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: all PASS (including existing DomainActivationTest)

- [ ] **Step 19: Commit**

```bash
git add -A
git commit -m "feat(cognitive-index): PadDtw warping constraints + circular shift significance

Add WarpingConstraint overload to PadDtw.compute() supporting all three
sealed variants (Unconstrained, SakoeChibaBand, ItakuraParallelogram).
Add significanceTest() using circular shift surrogates to assess DTW
correlation significance. DomainCorrelation gains pValue, attribution
count fields. CorrelationStrength gains significance-aware overload.

Refs #324"
```

### Task 3: EventTriggeredAnalyzer + value types

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/ConfidenceInterval.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/EventTypeImpact.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/EventImpact.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/EventTriggeredAnalyzer.java`
- Create: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/EventTriggeredAnalyzerTest.java`

**Interfaces:**
- Consumes: `Memory` from memory-api (createdAt, pleasure, arousal, dominance, attributes)
- Consumes: `ExperienceAttributeKeys.EVENT_TYPE` for type classification
- Consumes: `PadDimension` enum (PLEASURE, AROUSAL, DOMINANCE) — already exists in cognitive-index
- Produces: `ConfidenceInterval(double lower, double upper)` record
- Produces: `EventTypeImpact(Map<PadDimension, Double> meanDelta, Map<PadDimension, ConfidenceInterval> confidenceInterval, int eventCount)` record
- Produces: `EventImpact(Map<PadDimension, Double> meanDelta, Map<PadDimension, ConfidenceInterval> confidenceInterval, int eventCount, int totalEvents, Map<String, EventTypeImpact> byType)` record
- Produces: `EventTriggeredAnalyzer.analyze(List<Memory> experienceMemories, List<Memory> affectMemories, Duration window)` → `EventImpact`

- [ ] **Step 1: Write value type tests**

Create `EventTriggeredAnalyzerTest.java`:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.experience.ExperienceAttributeKeys;
import io.casehub.neocortex.memory.mood.AffectEvents;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class EventTriggeredAnalyzerTest {

    private static final Instant BASE = Instant.parse("2026-01-01T00:00:00Z");

    @Test
    void confidenceIntervalHoldsValues() {
        var ci = new ConfidenceInterval(0.1, 0.5);
        assertEquals(0.1, ci.lower(), 1e-9);
        assertEquals(0.5, ci.upper(), 1e-9);
    }

    @Test
    void emptyExperienceReturnsEmptyImpact() {
        var result = EventTriggeredAnalyzer.analyze(
                List.of(), makeAffectMemories(10), Duration.ofHours(24));
        assertEquals(0, result.eventCount());
        assertEquals(0, result.totalEvents());
        assertTrue(result.byType().isEmpty());
    }

    @Test
    void emptyAffectReturnsZeroEventCount() {
        var result = EventTriggeredAnalyzer.analyze(
                List.of(makeExperience(BASE, "observation")),
                List.of(), Duration.ofHours(24));
        assertEquals(0, result.eventCount());
        assertEquals(1, result.totalEvents());
    }
}
```

Helper methods (add to test class):

```java
private List<Memory> makeAffectMemories(int count) {
    List<Memory> result = new ArrayList<>();
    for (int i = 0; i < count; i++) {
        result.add(makeAffectAt(BASE.plus(Duration.ofHours(i)),
                                i * 0.05, 0.0, 0.0));
    }
    return result;
}

private Memory makeAffectAt(Instant time, double p, double a, double d) {
    return new Memory(UUID.randomUUID().toString(),
            null, AffectEvents.DOMAIN, "tenant",
            null, "affect", Map.of(), null, p, a, d,
            null, time, null);
}

private Memory makeExperience(Instant time, String eventType) {
    return new Memory(UUID.randomUUID().toString(),
            null, new MemoryDomain("experience"), "tenant",
            null, "event", Map.of(ExperienceAttributeKeys.EVENT_TYPE, eventType),
            null, null, null, null, null, time, null);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=EventTriggeredAnalyzerTest#confidenceIntervalHoldsValues -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error — classes don't exist

- [ ] **Step 3: Create ConfidenceInterval record**

```java
package io.casehub.neocortex.cognitive.index;

public record ConfidenceInterval(double lower, double upper) {}
```

- [ ] **Step 4: Create EventTypeImpact record**

```java
package io.casehub.neocortex.cognitive.index;

import java.util.Map;

public record EventTypeImpact(
        Map<PadDimension, Double> meanDelta,
        Map<PadDimension, ConfidenceInterval> confidenceInterval,
        int eventCount
) {
    public EventTypeImpact {
        meanDelta = Map.copyOf(meanDelta);
        confidenceInterval = Map.copyOf(confidenceInterval);
    }
}
```

- [ ] **Step 5: Create EventImpact record**

```java
package io.casehub.neocortex.cognitive.index;

import java.util.Map;

public record EventImpact(
        Map<PadDimension, Double> meanDelta,
        Map<PadDimension, ConfidenceInterval> confidenceInterval,
        int eventCount,
        int totalEvents,
        Map<String, EventTypeImpact> byType
) {
    public EventImpact {
        meanDelta = Map.copyOf(meanDelta);
        confidenceInterval = Map.copyOf(confidenceInterval);
        byType = Map.copyOf(byType);
    }

    public static EventImpact empty() {
        return new EventImpact(Map.of(), Map.of(), 0, 0, Map.of());
    }
}
```

- [ ] **Step 6: Create EventTriggeredAnalyzer with empty/null guard logic**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.experience.ExperienceAttributeKeys;

import java.time.Duration;
import java.time.Instant;
import java.util.*;

public final class EventTriggeredAnalyzer {

    private EventTriggeredAnalyzer() {}

    public static EventImpact analyze(List<Memory> experienceMemories,
                                      List<Memory> affectMemories,
                                      Duration window) {
        if (experienceMemories.isEmpty()) return EventImpact.empty();

        long windowMs = window.toMillis();
        int totalEvents = experienceMemories.size();

        List<double[]> allDeltas = new ArrayList<>();
        Map<String, List<double[]>> deltasByType = new LinkedHashMap<>();
        Map<String, Integer> countsByType = new LinkedHashMap<>();

        for (Memory event : experienceMemories) {
            if (event.createdAt() == null) continue;
            Instant t = event.createdAt();
            String type = event.attributes() != null
                          ? event.attributes().getOrDefault(ExperienceAttributeKeys.EVENT_TYPE, "unknown")
                          : "unknown";

            double[] pre = meanPad(affectMemories, t.minusMillis(windowMs), t);
            double[] post = meanPad(affectMemories, t, t.plusMillis(windowMs));

            if (pre == null || post == null) continue;

            double[] delta = {post[0] - pre[0], post[1] - pre[1], post[2] - pre[2]};
            allDeltas.add(delta);
            deltasByType.computeIfAbsent(type, k -> new ArrayList<>()).add(delta);
            countsByType.merge(type, 1, Integer::sum);
        }

        int eventCount = allDeltas.size();
        Map<PadDimension, Double> meanDelta = computeMeanDelta(allDeltas);
        Map<PadDimension, ConfidenceInterval> ci = bootstrapCI(allDeltas, 1000, 42L);

        Map<String, EventTypeImpact> byType = new LinkedHashMap<>();
        for (var entry : deltasByType.entrySet()) {
            byType.put(entry.getKey(), new EventTypeImpact(
                    computeMeanDelta(entry.getValue()),
                    bootstrapCI(entry.getValue(), 1000, 42L),
                    entry.getValue().size()));
        }

        return new EventImpact(meanDelta, ci, eventCount, totalEvents, byType);
    }

    private static double[] meanPad(List<Memory> memories, Instant from, Instant to) {
        double sumP = 0, sumA = 0, sumD = 0;
        int count = 0;
        for (Memory m : memories) {
            if (m.createdAt() == null) continue;
            if (!m.createdAt().isBefore(from) && m.createdAt().isBefore(to)) {
                sumP += m.pleasure() != null ? m.pleasure() : 0.0;
                sumA += m.arousal() != null ? m.arousal() : 0.0;
                sumD += m.dominance() != null ? m.dominance() : 0.0;
                count++;
            }
        }
        if (count == 0) return null;
        return new double[]{sumP / count, sumA / count, sumD / count};
    }

    private static Map<PadDimension, Double> computeMeanDelta(List<double[]> deltas) {
        if (deltas.isEmpty()) return Map.of();
        double sumP = 0, sumA = 0, sumD = 0;
        for (double[] d : deltas) { sumP += d[0]; sumA += d[1]; sumD += d[2]; }
        int n = deltas.size();
        return Map.of(PadDimension.PLEASURE, sumP / n,
                      PadDimension.AROUSAL, sumA / n,
                      PadDimension.DOMINANCE, sumD / n);
    }

    private static Map<PadDimension, ConfidenceInterval> bootstrapCI(
            List<double[]> deltas, int resamples, long seed) {
        if (deltas.size() < 2) return Map.of();
        var rng = new Random(seed);
        int n = deltas.size();
        double[] meansP = new double[resamples];
        double[] meansA = new double[resamples];
        double[] meansD = new double[resamples];

        for (int r = 0; r < resamples; r++) {
            double sp = 0, sa = 0, sd = 0;
            for (int i = 0; i < n; i++) {
                double[] d = deltas.get(rng.nextInt(n));
                sp += d[0]; sa += d[1]; sd += d[2];
            }
            meansP[r] = sp / n; meansA[r] = sa / n; meansD[r] = sd / n;
        }

        Arrays.sort(meansP); Arrays.sort(meansA); Arrays.sort(meansD);
        int lo = (int) (resamples * 0.025);
        int hi = (int) (resamples * 0.975);

        return Map.of(
                PadDimension.PLEASURE, new ConfidenceInterval(meansP[lo], meansP[hi]),
                PadDimension.AROUSAL, new ConfidenceInterval(meansA[lo], meansA[hi]),
                PadDimension.DOMINANCE, new ConfidenceInterval(meansD[lo], meansD[hi]));
    }
}
```

- [ ] **Step 7: Run empty/null tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=EventTriggeredAnalyzerTest`
Expected: all PASS

- [ ] **Step 8: Write tests for correlated and uncorrelated events**

Add to `EventTriggeredAnalyzerTest.java`:

```java
@Test
void eventsAtAffectInflectionProduceNonZeroDelta() {
    List<Memory> affect = new ArrayList<>();
    for (int i = 0; i < 48; i++) {
        double p = i < 24 ? -0.5 : 0.5;
        affect.add(makeAffectAt(BASE.plus(Duration.ofHours(i)), p, 0.0, 0.0));
    }
    Memory event = makeExperience(BASE.plus(Duration.ofHours(24)), "outcome");

    var result = EventTriggeredAnalyzer.analyze(
            List.of(event), affect, Duration.ofHours(24));

    assertEquals(1, result.eventCount());
    double pleasureDelta = result.meanDelta().get(PadDimension.PLEASURE);
    assertTrue(Math.abs(pleasureDelta) > 0.5,
               "pleasure delta should be large at inflection point");
}

@Test
void eventsDuringFlatAffectProduceNearZeroDelta() {
    List<Memory> affect = new ArrayList<>();
    for (int i = 0; i < 48; i++) {
        affect.add(makeAffectAt(BASE.plus(Duration.ofHours(i)), 0.5, 0.0, 0.0));
    }
    Memory event = makeExperience(BASE.plus(Duration.ofHours(24)), "observation");

    var result = EventTriggeredAnalyzer.analyze(
            List.of(event), affect, Duration.ofHours(24));

    assertEquals(1, result.eventCount());
    double pleasureDelta = result.meanDelta().get(PadDimension.PLEASURE);
    assertTrue(Math.abs(pleasureDelta) < 0.01,
               "pleasure delta should be near zero for flat affect");
}

@Test
void perTypeBreakdownPartitionsCorrectly() {
    List<Memory> affect = new ArrayList<>();
    for (int i = 0; i < 72; i++) {
        double p = i * 0.01;
        affect.add(makeAffectAt(BASE.plus(Duration.ofHours(i)), p, 0.0, 0.0));
    }
    List<Memory> events = List.of(
            makeExperience(BASE.plus(Duration.ofHours(12)), "observation"),
            makeExperience(BASE.plus(Duration.ofHours(36)), "outcome"),
            makeExperience(BASE.plus(Duration.ofHours(60)), "outcome")
    );

    var result = EventTriggeredAnalyzer.analyze(events, affect, Duration.ofHours(12));

    assertTrue(result.byType().containsKey("observation"));
    assertTrue(result.byType().containsKey("outcome"));
    assertEquals(1, result.byType().get("observation").eventCount());
    assertEquals(2, result.byType().get("outcome").eventCount());
}

@Test
void sparseAffectSkipsEventsWithInsufficientData() {
    List<Memory> affect = List.of(
            makeAffectAt(BASE, 0.5, 0.0, 0.0));
    List<Memory> events = List.of(
            makeExperience(BASE.plus(Duration.ofDays(10)), "observation"));

    var result = EventTriggeredAnalyzer.analyze(events, affect, Duration.ofHours(24));

    assertEquals(0, result.eventCount());
    assertEquals(1, result.totalEvents());
}

@Test
void bootstrapCIBracketsMeanDelta() {
    List<Memory> affect = new ArrayList<>();
    for (int i = 0; i < 100; i++) {
        double p = i < 50 ? 0.0 : 0.5;
        affect.add(makeAffectAt(BASE.plus(Duration.ofHours(i)), p, 0.0, 0.0));
    }
    List<Memory> events = new ArrayList<>();
    for (int i = 45; i < 55; i++) {
        events.add(makeExperience(BASE.plus(Duration.ofHours(i)), "observation"));
    }

    var result = EventTriggeredAnalyzer.analyze(events, affect, Duration.ofHours(6));

    if (result.eventCount() > 1 && result.confidenceInterval().containsKey(PadDimension.PLEASURE)) {
        var ci = result.confidenceInterval().get(PadDimension.PLEASURE);
        double mean = result.meanDelta().get(PadDimension.PLEASURE);
        assertTrue(ci.lower() <= mean && mean <= ci.upper(),
                   "CI should bracket the mean");
    }
}
```

- [ ] **Step 9: Run all EventTriggeredAnalyzer tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=EventTriggeredAnalyzerTest`
Expected: all PASS

- [ ] **Step 10: Run full cognitive-index tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: all PASS

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "feat(cognitive-index): EventTriggeredAnalyzer + ConfidenceInterval + EventImpact types

Pure static utility measuring Δ(affect) before/after experience events per
PAD dimension. Per-type breakdown (observation/action/outcome) with bootstrap
95% CI. Handles sparse affect, empty inputs, per-type partitioning.

Refs #324"
```

---

## Batch 3: DomainActivation Integration

### Task 4: DomainActivationQuery/Result extensions + mood correlation

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DomainActivationQuery.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DomainActivationResult.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DomainActivation.java`
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/DomainActivationTest.java`

**Interfaces:**
- Consumes: `PadDtw.significanceTest()` from Task 2
- Consumes: `EventTriggeredAnalyzer.analyze()` from Task 3
- Consumes: `MoodEvents.DOMAIN`, `ExperienceEvents.DOMAIN` from memory-api
- Consumes: `MemoryDomain` from memory-api
- Consumes: `WarpingConstraint.SakoeChibaBand` from memory-api
- Produces: `DomainActivationQuery.withContextDomains(Set<MemoryDomain>)` — default empty
- Produces: `DomainActivationQuery.withEventWindow(Duration)` — default null (uses bucketDuration)
- Produces: `DomainActivationResult.contextCorrelations()` — `Map<MemoryDomain, Map<String, DomainCorrelation>>`
- Produces: `DomainActivationResult.eventImpacts()` — `Map<MemoryDomain, Map<String, EventImpact>>`

- [ ] **Step 1: Write failing tests for DomainActivationQuery extensions**

Add to `DomainActivationTest.java`:

```java
@Test
void queryAcceptsContextDomains() {
    var query = DomainActivationQuery.between(alice, TENANT, sgA, sgB)
                    .withContextDomains(Set.of(MoodEvents.DOMAIN));
    assertEquals(Set.of(MoodEvents.DOMAIN), query.contextDomains());
}

@Test
void queryDefaultContextDomainsEmpty() {
    var query = DomainActivationQuery.between(alice, TENANT, sgA, sgB);
    assertTrue(query.contextDomains().isEmpty());
}

@Test
void queryAcceptsEventWindow() {
    var query = DomainActivationQuery.between(alice, TENANT, sgA, sgB)
                    .withEventWindow(Duration.ofHours(12));
    assertEquals(Duration.ofHours(12), query.eventWindow());
}

@Test
void singleSubgraphAllowedWithContextDomains() {
    var query = new DomainActivationQuery(alice, Set.of(sgA), TENANT,
                    null, null, null, Set.of(MoodEvents.DOMAIN), null);
    assertEquals(1, query.subgraphIds().size());
}

@Test
void singleSubgraphWithoutContextDomainsThrows() {
    assertThrows(IllegalArgumentException.class, () ->
        new DomainActivationQuery(alice, Set.of(sgA), TENANT,
            null, null, null, Set.of(), null));
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=DomainActivationTest#queryAcceptsContextDomains`
Expected: compilation error

- [ ] **Step 3: Update DomainActivationQuery record**

```java
public record DomainActivationQuery(
        PrincipalId principal,
        Set<String> subgraphIds,
        String tenantId,
        Instant from,
        Instant to,
        Duration bucketDuration,
        Set<MemoryDomain> contextDomains,
        Duration eventWindow
) {
    public DomainActivationQuery {
        Objects.requireNonNull(principal, "principal required");
        Objects.requireNonNull(tenantId, "tenantId required");
        if (contextDomains == null) contextDomains = Set.of();
        contextDomains = Set.copyOf(contextDomains);
        if (subgraphIds == null || (subgraphIds.size() < 2 && contextDomains.isEmpty())) {
            throw new IllegalArgumentException(
                "at least 2 subgraphIds required (or 1 with contextDomains)");
        }
        subgraphIds = Set.copyOf(subgraphIds);
        if (bucketDuration == null) bucketDuration = Duration.ofHours(24);
    }

    public static DomainActivationQuery between(
            PrincipalId principal, String tenantId,
            String subgraphA, String subgraphB) {
        return new DomainActivationQuery(principal, Set.of(subgraphA, subgraphB),
                                         tenantId, null, null, null, Set.of(), null);
    }

    public DomainActivationQuery withFrom(Instant from) {
        return new DomainActivationQuery(principal, subgraphIds, tenantId,
                                         from, to, bucketDuration, contextDomains, eventWindow);
    }

    public DomainActivationQuery withTo(Instant to) {
        return new DomainActivationQuery(principal, subgraphIds, tenantId,
                                         from, to, bucketDuration, contextDomains, eventWindow);
    }

    public DomainActivationQuery withBucketDuration(Duration bucketDuration) {
        return new DomainActivationQuery(principal, subgraphIds, tenantId,
                                         from, to, bucketDuration, contextDomains, eventWindow);
    }

    public DomainActivationQuery withContextDomains(Set<MemoryDomain> contextDomains) {
        return new DomainActivationQuery(principal, subgraphIds, tenantId,
                                         from, to, bucketDuration, contextDomains, eventWindow);
    }

    public DomainActivationQuery withEventWindow(Duration eventWindow) {
        return new DomainActivationQuery(principal, subgraphIds, tenantId,
                                         from, to, bucketDuration, contextDomains, eventWindow);
    }
}
```

- [ ] **Step 4: Fix existing DomainActivationQuery constructor calls in tests**

Use `ide_find_references` on `DomainActivationQuery` to find test calls. Add `Set.of(), null` as the last two constructor arguments where `new DomainActivationQuery(...)` is called directly (not via `between()` factory).

- [ ] **Step 5: Update DomainActivationResult record**

```java
public record DomainActivationResult(
        Map<String, DomainSignal> domains,
        Map<DomainPair, DomainCorrelation> correlations,
        Map<MemoryDomain, Map<String, DomainCorrelation>> contextCorrelations,
        Map<MemoryDomain, Map<String, EventImpact>> eventImpacts,
        PrincipalId principal,
        String tenantId,
        Instant from, Instant to
) {
    public DomainActivationResult {
        domains      = Map.copyOf(domains);
        correlations = Map.copyOf(correlations);
        contextCorrelations = contextCorrelations != null ? Map.copyOf(contextCorrelations) : Map.of();
        eventImpacts = eventImpacts != null ? Map.copyOf(eventImpacts) : Map.of();
    }
}
```

- [ ] **Step 6: Fix existing DomainActivationResult constructor call in DomainActivation.java**

Add `Map.of(), Map.of()` as context correlations and event impacts:

```java
return Optional.of(new DomainActivationResult(
        signals, correlations, Map.of(), Map.of(),
        query.principal(), query.tenantId(),
        query.from(), query.to()));
```

- [ ] **Step 7: Run existing tests to verify backward compatibility**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=DomainActivationTest`
Expected: all 9 existing tests PASS, new query tests PASS

- [ ] **Step 8: Write failing test for mood correlation**

Add to `DomainActivationTest.java`. The test needs mood memories stored for the agent, and affect memories for entities in subgraphs:

```java
@Test
void moodCorrelationWithContextAttribution() {
    String sgA = mindMapStore.createSubgraph(new SubgraphInput("sgA", "test", TENANT));
    String sgB = mindMapStore.createSubgraph(new SubgraphInput("sgB", "test", TENANT));
    String nodeA = mindMapStore.addNode(
            new NodeInput("entityA", null, null, null, null, null, null, null, null), TENANT);
    mindMapStore.addNodeToSubgraph(nodeA, sgA, TENANT);
    String nodeB = mindMapStore.addNode(
            new NodeInput("entityB", null, null, null, null, null, null, null, null), TENANT);
    mindMapStore.addNodeToSubgraph(nodeB, sgB, TENANT);

    for (int d = 0; d < 10; d++) {
        Instant t = BASE.plus(Duration.ofDays(d));
        double v = d * 0.1;
        memoryStore.storeAt(nodeA, v, 0.0, 0.0, t, TENANT);
        memoryStore.storeAt(nodeB, -v, 0.0, 0.0, t, TENANT);
        storeMoodAt(v, 0.0, 0.0, t, Set.of(sgA));
    }

    var query = DomainActivationQuery.between(alice, TENANT, sgA, sgB)
                    .withContextDomains(Set.of(MoodEvents.DOMAIN))
                    .withFrom(BASE).withTo(BASE.plus(Duration.ofDays(10)));
    var result = domainActivation.correlate(query);

    assertTrue(result.isPresent());
    var moodCorrelations = result.get().contextCorrelations().get(MoodEvents.DOMAIN);
    assertNotNull(moodCorrelations);
    assertTrue(moodCorrelations.get(sgA).dtwSimilarity() >
               moodCorrelations.get(sgB).dtwSimilarity(),
               "mood attributed to sgA should correlate more strongly with sgA affect");
}
```

Add helper method to test class:

```java
private void storeMoodAt(double p, double a, double d, Instant t,
                         Set<String> contextIds) {
    var attrs = new HashMap<String, String>();
    attrs.put("pleasure", String.valueOf(p));
    attrs.put("arousal", String.valueOf(a));
    attrs.put("dominance", String.valueOf(d));
    if (contextIds != null && !contextIds.isEmpty()) {
        attrs.put("active-context-ids", String.join(",", contextIds));
    }
    memoryStore.store(new MemoryInput(
            Subject.of("agent", alice.id()), MoodEvents.DOMAIN, TENANT,
            null, "mood snapshot", attrs, null, p, a, d, alice, null));
}
```

- [ ] **Step 9: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=DomainActivationTest#moodCorrelationWithContextAttribution`
Expected: FAIL — `contextCorrelations` is empty map

- [ ] **Step 10: Implement mood correlation path in DomainActivation.correlate()**

After the existing pairwise subgraph correlation loop, add the context correlation logic:

```java
Map<MemoryDomain, Map<String, DomainCorrelation>> contextCorrelations = new LinkedHashMap<>();
Map<MemoryDomain, Map<String, EventImpact>> eventImpacts = new LinkedHashMap<>();

if (!query.contextDomains().isEmpty()) {
    for (MemoryDomain domain : query.contextDomains()) {
        if (MoodEvents.DOMAIN.equals(domain)) {
            contextCorrelations.put(domain,
                    correlateMood(query, sgIds, padSeries));
        } else if (ExperienceEvents.DOMAIN.equals(domain)) {
            // Task 5 will implement this
            eventImpacts.put(domain,
                    correlateExperience(query, sgIds));
        }
    }
}

return Optional.of(new DomainActivationResult(
        signals, correlations, contextCorrelations, eventImpacts,
        query.principal(), query.tenantId(),
        query.from(), query.to()));
```

Add the `correlateMood` private method:

```java
private Map<String, DomainCorrelation> correlateMood(
        DomainActivationQuery query, List<String> sgIds,
        Map<String, double[][]> affectSeries) {

    var moodQuery = MemoryQuery.forSubjects(
                        List.of(Subject.of("agent", query.principal().id())),
                        MoodEvents.DOMAIN, query.tenantId())
                    .withCallerPrincipalId(query.principal())
                    .withLimit(1000)
                    .withOrder(MemoryOrder.CHRONOLOGICAL);
    if (query.from() != null) moodQuery = moodQuery.withSince(query.from());
    List<Memory> allMood = memoryStore.query(moodQuery);
    if (query.to() != null) {
        allMood.removeIf(m -> m.createdAt() != null && m.createdAt().isAfter(query.to()));
    }

    Map<String, DomainCorrelation> results = new LinkedHashMap<>();
    for (String sgId : sgIds) {
        List<Memory> partitioned = partitionMoodByContext(allMood, sgId);
        if (partitioned.isEmpty() || !affectSeries.containsKey(sgId)) {
            results.put(sgId, new DomainCorrelation(0.0, List.of(), 0,
                    CorrelationStrength.NONE, Double.NaN, 0, 0));
            continue;
        }

        int attributed = (int) partitioned.stream()
                .filter(m -> m.attributes() != null
                        && m.attributes().containsKey(MoodAttributeKeys.ACTIVE_CONTEXT_IDS))
                .count();

        double[][] moodBuckets = timeBucket(partitioned, query.bucketDuration(),
                                            query.from(), query.to());
        double[][] affectBuckets = affectSeries.get(sgId);

        if (moodBuckets.length < 2 || affectBuckets.length < 2) {
            results.put(sgId, new DomainCorrelation(0.0, List.of(),
                    Math.min(moodBuckets.length, affectBuckets.length),
                    CorrelationStrength.NONE, Double.NaN, attributed, partitioned.size()));
            continue;
        }

        int bandWidth = Math.max(1, (int)(Math.max(moodBuckets.length, affectBuckets.length) * 0.1));
        var constraint = new WarpingConstraint.SakoeChibaBand(bandWidth);

        var sig = PadDtw.significanceTest(moodBuckets, affectBuckets,
                                          constraint, 200, query.hashCode());
        results.put(sgId, new DomainCorrelation(
                sig.similarity(), List.of(),
                Math.min(moodBuckets.length, affectBuckets.length),
                sig.strength(), sig.pValue(),
                attributed, partitioned.size()));
    }
    return results;
}

private List<Memory> partitionMoodByContext(List<Memory> allMood, String sgId) {
    List<Memory> result = new ArrayList<>();
    for (Memory m : allMood) {
        String contextIds = m.attributes() != null
                ? m.attributes().get(MoodAttributeKeys.ACTIVE_CONTEXT_IDS) : null;
        if (contextIds == null || contextIds.isEmpty()) {
            result.add(m);
        } else if (contextIds.contains(sgId)) {
            result.add(m);
        }
    }
    return result;
}
```

Add stub for experience:

```java
private Map<String, EventImpact> correlateExperience(
        DomainActivationQuery query, List<String> sgIds) {
    return Map.of();
}
```

- [ ] **Step 11: Run mood correlation test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=DomainActivationTest#moodCorrelationWithContextAttribution`
Expected: PASS

- [ ] **Step 12: Write additional mood tests**

```java
@Test
void emptyContextDomainsProducesEmptyMaps() {
    // Use existing setup from correlateTwoSubgraphsWithCorrelatedSignals
    // ...set up subgraphs and affect memories...
    var query = DomainActivationQuery.between(alice, TENANT, sgA, sgB)
                    .withFrom(BASE).withTo(BASE.plus(Duration.ofDays(10)));
    var result = domainActivation.correlate(query);
    assertTrue(result.isPresent());
    assertTrue(result.get().contextCorrelations().isEmpty());
    assertTrue(result.get().eventImpacts().isEmpty());
}

@Test
void agentGlobalMoodCorrelatesWithAllSubgraphs() {
    // Set up 2 subgraphs with affect, store mood WITHOUT activeContextIds
    // ...
    // Both subgraphs should have mood correlations (fallback to global)
}
```

- [ ] **Step 13: Run all DomainActivation tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=DomainActivationTest`
Expected: all PASS

- [ ] **Step 14: Commit**

```bash
git add -A
git commit -m "feat(cognitive-index): DomainActivation mood correlation with context partitioning

DomainActivationQuery gains withContextDomains/withEventWindow. Single
subgraph allowed with contextDomains. DomainActivationResult gains
contextCorrelations/eventImpacts maps. Mood correlation path: context
partitioning, time-bucketed PAD DTW with Sakoe-Chiba banding, circular
shift significance testing. Attribution quality tracking.

Refs #324"
```

### Task 5: Experience correlation integration + full verification

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DomainActivation.java`
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/DomainActivationTest.java`

**Interfaces:**
- Consumes: `EventTriggeredAnalyzer.analyze()` from Task 3
- Consumes: `ExperienceEvents.DOMAIN` from memory-api
- Consumes: `ExperienceAttributeKeys.EVENT_TYPE` from memory-api
- Produces: fully wired experience → affect correlation in `DomainActivation.correlate()`

- [ ] **Step 1: Write failing test for experience correlation**

Add to `DomainActivationTest.java`:

```java
@Test
void experienceCorrelationProducesEventImpact() {
    String sgA = mindMapStore.createSubgraph(new SubgraphInput("sgA", "test", TENANT));
    String nodeA = mindMapStore.addNode(
            new NodeInput("entityA", null, null, null, null, null, null, null, null), TENANT);
    mindMapStore.addNodeToSubgraph(nodeA, sgA, TENANT);

    String sgB = mindMapStore.createSubgraph(new SubgraphInput("sgB", "test", TENANT));
    String nodeB = mindMapStore.addNode(
            new NodeInput("entityB", null, null, null, null, null, null, null, null), TENANT);
    mindMapStore.addNodeToSubgraph(nodeB, sgB, TENANT);

    for (int d = 0; d < 20; d++) {
        Instant t = BASE.plus(Duration.ofDays(d));
        double v = d < 10 ? -0.3 : 0.5;
        memoryStore.storeAt(nodeA, v, 0.0, 0.0, t, TENANT);
        memoryStore.storeAt(nodeB, 0.0, 0.0, 0.0, t, TENANT);
    }
    storeExperienceAt(BASE.plus(Duration.ofDays(10)), "outcome");

    var query = DomainActivationQuery.between(alice, TENANT, sgA, sgB)
                    .withContextDomains(Set.of(ExperienceEvents.DOMAIN))
                    .withEventWindow(Duration.ofDays(5))
                    .withFrom(BASE).withTo(BASE.plus(Duration.ofDays(20)));
    var result = domainActivation.correlate(query);

    assertTrue(result.isPresent());
    var impacts = result.get().eventImpacts().get(ExperienceEvents.DOMAIN);
    assertNotNull(impacts);
    assertTrue(impacts.containsKey(sgA));
    assertTrue(impacts.get(sgA).eventCount() > 0);
    assertTrue(impacts.get(sgA).byType().containsKey("outcome"));
}
```

Add helper method:

```java
private void storeExperienceAt(Instant t, String eventType) {
    var attrs = new HashMap<String, String>();
    attrs.put(ExperienceAttributeKeys.EVENT_TYPE, eventType);
    attrs.put(ExperienceAttributeKeys.TIMESTAMP, t.toString());
    memoryStore.store(new MemoryInput(
            Subject.of("agent", alice.id()), ExperienceEvents.DOMAIN, TENANT,
            null, "experience event", attrs, null, null, null, null, alice, t));
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=DomainActivationTest#experienceCorrelationProducesEventImpact`
Expected: FAIL — eventImpacts is empty map (stub returns empty)

- [ ] **Step 3: Implement correlateExperience in DomainActivation**

Replace the stub `correlateExperience` method:

```java
private Map<String, EventImpact> correlateExperience(
        DomainActivationQuery query, List<String> sgIds) {

    var expQuery = MemoryQuery.forSubjects(
                       List.of(Subject.of("agent", query.principal().id())),
                       ExperienceEvents.DOMAIN, query.tenantId())
                   .withCallerPrincipalId(query.principal())
                   .withLimit(1000)
                   .withOrder(MemoryOrder.CHRONOLOGICAL);
    if (query.from() != null) expQuery = expQuery.withSince(query.from());
    List<Memory> experiences = new ArrayList<>(memoryStore.query(expQuery));
    if (query.to() != null) {
        experiences.removeIf(m -> m.createdAt() != null && m.createdAt().isAfter(query.to()));
    }

    if (experiences.isEmpty()) return Map.of();

    Duration window = query.eventWindow() != null ? query.eventWindow() : query.bucketDuration();

    Map<String, EventImpact> results = new LinkedHashMap<>();
    for (String sgId : sgIds) {
        List<MindMapNode> entities = mindMapStore.search(
                MindMapQuery.of(query.tenantId(), 1000).withSubgraphId(sgId));

        List<Memory> affectForSubgraph = new ArrayList<>();
        for (MindMapNode entity : entities) {
            var memQuery = MemoryQuery.forSubjects(
                    List.of(Subject.of("unknown", entity.id()),
                            Subject.of("unknown", entity.name())),
                    AffectEvents.DOMAIN, query.tenantId())
                .withCallerPrincipalId(query.principal())
                .withLimit(1000)
                .withOrder(MemoryOrder.CHRONOLOGICAL);
            if (query.from() != null) {
                memQuery = memQuery.withSince(query.from());
            }
            affectForSubgraph.addAll(memoryStore.query(memQuery));
        }
        if (query.to() != null) {
            affectForSubgraph.removeIf(m -> m.createdAt() != null
                    && m.createdAt().isAfter(query.to()));
        }
        affectForSubgraph.sort(Comparator.comparing(
                m -> m.createdAt() != null ? m.createdAt() : Instant.EPOCH));

        results.put(sgId, EventTriggeredAnalyzer.analyze(
                experiences, affectForSubgraph, window));
    }
    return results;
}
```

- [ ] **Step 4: Run experience correlation test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=DomainActivationTest#experienceCorrelationProducesEventImpact`
Expected: PASS

- [ ] **Step 5: Write graceful degradation test**

```java
@Test
void noMoodMemoriesProducesEmptyCorrelationNotFailure() {
    // Set up subgraphs with affect but no mood memories
    // ...
    var query = DomainActivationQuery.between(alice, TENANT, sgA, sgB)
                    .withContextDomains(Set.of(MoodEvents.DOMAIN))
                    .withFrom(BASE).withTo(BASE.plus(Duration.ofDays(10)));
    var result = domainActivation.correlate(query);
    assertTrue(result.isPresent());
    var moodCorrelations = result.get().contextCorrelations().get(MoodEvents.DOMAIN);
    assertNotNull(moodCorrelations);
    for (var dc : moodCorrelations.values()) {
        assertEquals(CorrelationStrength.NONE, dc.strength());
    }
}
```

- [ ] **Step 6: Run all DomainActivation tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=DomainActivationTest`
Expected: all PASS (original 9 + new mood/experience tests)

- [ ] **Step 7: Full project build and test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS, all tests PASS

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(cognitive-index): DomainActivation experience correlation via event-triggered windows

Wire EventTriggeredAnalyzer into DomainActivation.correlate() for
experience → affect analysis. Measures Δ(affect) pre/post each experience
event per subgraph per PAD dimension. Per-type breakdown with bootstrap CI.

Closes #324"
```

## References

- `specs/issue-324-cognitive-extensions/2026-09-13-cross-domain-correlation-design.md` — design spec
- `specs/issue-324-cognitive-extensions/decisions.md` — D1-D9 decisions with rationale
- `DomainActivation.correlate()` — existing cross-subgraph correlation algorithm
- `PadDtw.compute()` — existing DTW implementation
- `MoodState` record — memory-api mood model
- `ExperienceEvent` sealed hierarchy — memory-api experience model
- `WarpingConstraint` sealed interface — memory-api CBR warping types
- GE-20260824-829f7a — DTW alignment paths not exposed through retrieval API
- GE-20260824-9f3788 — standard DTW forces full endpoint alignment
- casehubio/neocortex#324 — parent issue
- casehubio/neocortex#283 — cross-domain reasoning parent

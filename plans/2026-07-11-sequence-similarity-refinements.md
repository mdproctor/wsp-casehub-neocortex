# Sequence Similarity Refinements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> executing-plans to implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural editing.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #92 — sequence similarity algorithms — DTW and edit distance for temporal case matching
**Issue group:** #92

**Goal:** Add alignment path extraction, windowed DTW, weighted edit distance, and SimilaritySpec configuration for temporal fields.

**Architecture:** All changes in `memory-api` (Tier 1 pure Java, zero external dependencies). New sealed permits on `SimilaritySpec`, new record components on `FeatureField.TimeSeries` and `FeatureField.DiscreteSequence`, enriched return types from `DtwSimilarity` and `EditDistanceSimilarity`, and scorer integration to read specs and pass parameters.

**Tech Stack:** Java 21 (on Java 26 JVM), JUnit 5, AssertJ

## Global Constraints

- All code in `memory-api` module — Tier 1 pure Java, zero external dependencies
- Package: `io.casehub.neocortex.memory.cbr`
- Test package: `io.casehub.neocortex.memory.cbr` (under `src/test/java`)
- Contract tests in `memory-testing` module: `io.casehub.neocortex.memory.cbr.testing`
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl memory-api`
- Build with contract tests: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl memory-api,memory-testing,memory-cbr-inmem`
- Pre-release — breaking changes cost nothing

---

### Task 1: Data types and SimilaritySpec variants

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AlignmentPair.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/DtwResult.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/EditOp.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/EditStep.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/EditDistanceResult.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/SimilaritySpec.java` — add DtwSpec, EditDistanceSpec, extract shared validation, fix NaN bug
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/SimilaritySpecTest.java`

**Interfaces:**
- Produces: `AlignmentPair(int queryIndex, int caseIndex)`, `DtwResult(double score, List<AlignmentPair> alignment)`, `EditOp { MATCH, SUBSTITUTE, INSERT, DELETE }`, `EditStep(int queryIndex, int caseIndex, EditOp operation)`, `EditDistanceResult(double score, List<EditStep> alignment)`, `SimilaritySpec.DtwSpec(Integer windowSize)`, `SimilaritySpec.EditDistanceSpec(Map<String, Map<String, Double>> substitutionSimilarities)`

- [ ] **Step 1: Write tests for new SimilaritySpec variants**

Add these tests to `SimilaritySpecTest.java` using `ide_insert_member`:

```java
@Test
void dtwSpec_nullWindowSize_accepted() {
    var spec = new SimilaritySpec.DtwSpec(null);
    assertThat(spec.windowSize()).isNull();
}

@Test
void dtwSpec_positiveWindowSize_accepted() {
    var spec = new SimilaritySpec.DtwSpec(5);
    assertThat(spec.windowSize()).isEqualTo(5);
}

@Test
void dtwSpec_zeroWindowSize_rejected() {
    assertThatThrownBy(() -> new SimilaritySpec.DtwSpec(0))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("windowSize must be >= 1");
}

@Test
void dtwSpec_negativeWindowSize_rejected() {
    assertThatThrownBy(() -> new SimilaritySpec.DtwSpec(-3))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("windowSize must be >= 1");
}

@Test
void editDistanceSpec_emptyMap_accepted() {
    var spec = new SimilaritySpec.EditDistanceSpec(Map.of());
    assertThat(spec.substitutionSimilarities()).isEmpty();
}

@Test
void editDistanceSpec_mirrorValidation() {
    var spec = new SimilaritySpec.EditDistanceSpec(Map.of(
        "A", Map.of("B", 0.5)));
    assertThat(spec.substitutionSimilarities().get("B").get("A")).isEqualTo(0.5);
}

@Test
void editDistanceSpec_nanScore_rejected() {
    assertThatThrownBy(() -> new SimilaritySpec.EditDistanceSpec(Map.of(
        "A", Map.of("B", Double.NaN))))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void editDistanceSpec_outOfRangeScore_rejected() {
    assertThatThrownBy(() -> new SimilaritySpec.EditDistanceSpec(Map.of(
        "A", Map.of("B", 1.5))))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void editDistanceSpec_conflictingScores_rejected() {
    assertThatThrownBy(() -> new SimilaritySpec.EditDistanceSpec(Map.of(
        "A", Map.of("B", 0.5),
        "B", Map.of("A", 0.7))))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("Conflicting");
}

@Test
void categoricalTable_nanScore_rejected() {
    assertThatThrownBy(() -> new SimilaritySpec.CategoricalTable(Map.of(
        "A", Map.of("B", Double.NaN))))
        .isInstanceOf(IllegalArgumentException.class);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=SimilaritySpecTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failures — DtwSpec and EditDistanceSpec don't exist yet

- [ ] **Step 3: Create new data type files**

Create `AlignmentPair.java`:
```java
package io.casehub.neocortex.memory.cbr;

public record AlignmentPair(int queryIndex, int caseIndex) {}
```

Create `DtwResult.java`:
```java
package io.casehub.neocortex.memory.cbr;

import java.util.List;
import java.util.Objects;

public record DtwResult(double score, List<AlignmentPair> alignment) {
    public DtwResult {
        Objects.requireNonNull(alignment, "alignment");
        alignment = List.copyOf(alignment);
    }
}
```

Create `EditOp.java`:
```java
package io.casehub.neocortex.memory.cbr;

public enum EditOp { MATCH, SUBSTITUTE, INSERT, DELETE }
```

Create `EditStep.java`:
```java
package io.casehub.neocortex.memory.cbr;

import java.util.Objects;

public record EditStep(int queryIndex, int caseIndex, EditOp operation) {
    public EditStep {
        Objects.requireNonNull(operation, "operation");
    }
}
```

Create `EditDistanceResult.java`:
```java
package io.casehub.neocortex.memory.cbr;

import java.util.List;
import java.util.Objects;

public record EditDistanceResult(double score, List<EditStep> alignment) {
    public EditDistanceResult {
        Objects.requireNonNull(alignment, "alignment");
        alignment = List.copyOf(alignment);
    }
}
```

- [ ] **Step 4: Add DtwSpec and EditDistanceSpec to SimilaritySpec**

Update `SimilaritySpec` sealed interface declaration to add new permits. Extract `mirrorAndValidate` to a shared `private static` method `validateAndMirrorSimilarityMap`. Add NaN check to the shared method (fixes pre-existing bug in CategoricalTable). Add DtwSpec and EditDistanceSpec records.

Use `ide_edit_member` to update the `SimilaritySpec` interface declaration (add permits).
Use `ide_insert_member` to add `DtwSpec` record after `ExponentialDecay`.
Use `ide_insert_member` to add `EditDistanceSpec` record after `DtwSpec`.
Extract `mirrorAndValidate` from `CategoricalTable` into a shared `private static` method on `SimilaritySpec`, adding `Double.isNaN(score)` check to the validation.
Update `CategoricalTable` constructor to call the shared method.

DtwSpec:
```java
record DtwSpec(Integer windowSize) implements SimilaritySpec {
    public DtwSpec {
        if (windowSize != null && windowSize < 1)
            throw new IllegalArgumentException("windowSize must be >= 1, got: " + windowSize);
    }
}
```

EditDistanceSpec:
```java
record EditDistanceSpec(Map<String, Map<String, Double>> substitutionSimilarities) implements SimilaritySpec {
    public EditDistanceSpec {
        Objects.requireNonNull(substitutionSimilarities, "substitutionSimilarities");
        substitutionSimilarities = validateAndMirrorSimilarityMap(substitutionSimilarities);
    }
}
```

Shared validation (add to SimilaritySpec interface body):
```java
private static Map<String, Map<String, Double>> validateAndMirrorSimilarityMap(
        Map<String, Map<String, Double>> input) {
    // Same logic as current CategoricalTable.mirrorAndValidate but with NaN check:
    // if (Double.isNaN(score) || score < 0.0 || score > 1.0) throw ...
    // Mirror, validate symmetry, reject conflicts
}
```

- [ ] **Step 5: Update exhaustive switches on Categorical and Numeric constructors**

Use `ide_replace_member` on `FeatureField.Categorical` constructor to add reject cases for `DtwSpec` and `EditDistanceSpec`.
Use `ide_replace_member` on `FeatureField.Numeric` constructor to add reject cases for `DtwSpec` and `EditDistanceSpec`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=SimilaritySpecTest`
Expected: all new tests PASS

- [ ] **Step 7: Verify with diagnostics**

Run: `ide_diagnostics` on `SimilaritySpec.java` and `FeatureField.java` — no errors.

- [ ] **Step 8: Commit**

```
feat(#92): data types + SimilaritySpec variants for temporal fields

AlignmentPair, DtwResult, EditOp, EditStep, EditDistanceResult records.
DtwSpec and EditDistanceSpec sealed permits on SimilaritySpec. Shared
mirror-validation with NaN fix.
```

---

### Task 2: DtwSimilarity — alignment path + windowed DTW

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/DtwSimilarity.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/DtwSimilarityTest.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java` (update dtwSimilarity() to extract .score())

**Interfaces:**
- Consumes: `AlignmentPair`, `DtwResult` from Task 1
- Produces: `DtwSimilarity.compute(query, caseSeq, schema)` → `DtwResult`, `DtwSimilarity.compute(query, caseSeq, schema, windowSize)` → `DtwResult`

- [ ] **Step 1: Write new tests for alignment path and windowed DTW**

Add to `DtwSimilarityTest.java` using `ide_insert_member`:

```java
@Test
void alignmentPath_identicalSequences_diagonal() {
    var seq = List.of(
        Map.<String, Object>of("t", 1, "val", 50),
        Map.<String, Object>of("t", 2, "val", 60));
    var result = DtwSimilarity.compute(seq, seq, SCHEMA);
    assertThat(result.alignment()).containsExactly(
        new AlignmentPair(0, 0),
        new AlignmentPair(1, 1));
}

@Test
void alignmentPath_stretchedAlignment() {
    var q = List.of(Map.<String, Object>of("t", 1, "val", 50));
    var c = List.of(
        Map.<String, Object>of("t", 1, "val", 50),
        Map.<String, Object>of("t", 2, "val", 50));
    var result = DtwSimilarity.compute(q, c, SCHEMA);
    assertThat(result.alignment()).hasSize(2);
    assertThat(result.alignment().get(0).queryIndex()).isEqualTo(0);
}

@Test
void alignmentPath_lengthBounds() {
    var q = List.of(
        Map.<String, Object>of("t", 1, "val", 30),
        Map.<String, Object>of("t", 2, "val", 60),
        Map.<String, Object>of("t", 3, "val", 90));
    var c = List.of(
        Map.<String, Object>of("t", 1, "val", 30),
        Map.<String, Object>of("t", 2, "val", 90));
    var result = DtwSimilarity.compute(q, c, SCHEMA);
    assertThat(result.alignment()).hasSizeGreaterThanOrEqualTo(Math.max(q.size(), c.size()));
}

@Test
void alignmentPath_bothEmpty_emptyPath() {
    List<Map<String, Object>> empty = List.of();
    var result = DtwSimilarity.compute(empty, empty, SCHEMA);
    assertThat(result.score()).isEqualTo(1.0);
    assertThat(result.alignment()).isEmpty();
}

@Test
void alignmentPath_oneEmpty_emptyPath() {
    var q = List.of(Map.<String, Object>of("t", 1, "val", 50));
    List<Map<String, Object>> empty = List.of();
    var result = DtwSimilarity.compute(q, empty, SCHEMA);
    assertThat(result.score()).isEqualTo(0.0);
    assertThat(result.alignment()).isEmpty();
}

@Test
void windowedDtw_sameResultAsFullWhenWindowLargerThanSequence() {
    var q = List.of(
        Map.<String, Object>of("t", 1, "val", 50),
        Map.<String, Object>of("t", 2, "val", 60));
    var c = List.of(
        Map.<String, Object>of("t", 1, "val", 52),
        Map.<String, Object>of("t", 2, "val", 58));
    var full = DtwSimilarity.compute(q, c, SCHEMA);
    var windowed = DtwSimilarity.compute(q, c, SCHEMA, 100);
    assertThat(windowed.score()).isCloseTo(full.score(), within(0.0001));
}

@Test
void windowedDtw_constrainedAlignment() {
    var q = List.of(
        Map.<String, Object>of("t", 1, "val", 10),
        Map.<String, Object>of("t", 2, "val", 20),
        Map.<String, Object>of("t", 3, "val", 30),
        Map.<String, Object>of("t", 4, "val", 40),
        Map.<String, Object>of("t", 5, "val", 50));
    var c = List.of(
        Map.<String, Object>of("t", 1, "val", 10),
        Map.<String, Object>of("t", 2, "val", 20),
        Map.<String, Object>of("t", 3, "val", 30),
        Map.<String, Object>of("t", 4, "val", 40),
        Map.<String, Object>of("t", 5, "val", 50));
    var result = DtwSimilarity.compute(q, c, SCHEMA, 1);
    for (var pair : result.alignment()) {
        assertThat(Math.abs(pair.queryIndex() - pair.caseIndex())).isLessThanOrEqualTo(1);
    }
}

@Test
void windowedDtw_windowClampedForUnequalLengths() {
    var q = List.of(
        Map.<String, Object>of("t", 1, "val", 50),
        Map.<String, Object>of("t", 2, "val", 60));
    var c = List.of(
        Map.<String, Object>of("t", 1, "val", 50),
        Map.<String, Object>of("t", 2, "val", 55),
        Map.<String, Object>of("t", 3, "val", 60),
        Map.<String, Object>of("t", 4, "val", 65),
        Map.<String, Object>of("t", 5, "val", 70));
    // window=1, but |n-m|=3, so effective window clamped to 3
    var result = DtwSimilarity.compute(q, c, SCHEMA, 1);
    assertThat(result.score()).isGreaterThan(0.0);
}
```

- [ ] **Step 2: Update existing DtwSimilarityTest assertions to use .score()**

All existing tests call `DtwSimilarity.compute(...)` and assert on the double result. After the return type changes to `DtwResult`, update each assertion:
- `assertThat(DtwSimilarity.compute(seq, seq, SCHEMA)).isEqualTo(1.0)` → `assertThat(DtwSimilarity.compute(seq, seq, SCHEMA).score()).isEqualTo(1.0)`

Use `ide_replace_member` on each test method. There are 9 existing test methods to update.

- [ ] **Step 3: Implement DtwSimilarity changes**

Use `ide_edit_member` to replace the `compute` method on `DtwSimilarity`:

Change return type to `DtwResult`. Add `Integer windowSize` parameter (with null default in 3-arg overload). Add Sakoe-Chiba band logic in the inner loop. Add backtrace after matrix fill. Return `DtwResult(similarity, path)`.

3-arg `compute` delegates to 4-arg with `null` windowSize.

Key implementation details:
- Clamp window: `int w = windowSize == null ? Math.max(n, m) : Math.max(windowSize, Math.abs(n - m));`
- Inner loop: `for (int j = Math.max(1, i - w); j <= Math.min(m, i + w); j++)`
- Initialize out-of-window cells to `Double.MAX_VALUE`
- Backtrace: from `(n, m)` to `(0, 0)`, collect `AlignmentPair(i-1, j-1)`, reverse

- [ ] **Step 4: Update CbrSimilarityScorer.dtwSimilarity() to extract .score()**

Use `ide_replace_member` on `CbrSimilarityScorer.dtwSimilarity()`:

```java
@SuppressWarnings("unchecked")
private static double dtwSimilarity(FeatureField.TimeSeries ts,
                                     Object queryVal, Object caseVal) {
    return DtwSimilarity.compute(
        (java.util.List<java.util.Map<String, Object>>) queryVal,
        (java.util.List<java.util.Map<String, Object>>) caseVal, ts).score();
}
```

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=DtwSimilarityTest`
Expected: all tests PASS (existing + new)

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrSimilarityScorerTest`
Expected: all tests PASS (scorer still works via .score() extraction)

- [ ] **Step 6: Verify with diagnostics**

Run: `ide_diagnostics` on `DtwSimilarity.java` and `CbrSimilarityScorer.java`

- [ ] **Step 7: Commit**

```
feat(#92): DTW alignment path extraction + windowed DTW (Sakoe-Chiba band)

DtwSimilarity.compute() returns DtwResult with alignment path via
cost-matrix backtracing. Optional windowSize parameter constrains
computation to diagonal band, clamped to max(w, |n-m|).
```

---

### Task 3: EditDistanceSimilarity — alignment path + weighted substitution

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/EditDistanceSimilarity.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/EditDistanceSimilarityTest.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java` (update editDistanceSimilarity() to extract .score())

**Interfaces:**
- Consumes: `EditOp`, `EditStep`, `EditDistanceResult` from Task 1
- Produces: `EditDistanceSimilarity.compute(query, caseSeq)` → `EditDistanceResult`, `EditDistanceSimilarity.compute(query, caseSeq, substitutionSimilarities)` → `EditDistanceResult`

- [ ] **Step 1: Write new tests for alignment path and weighted substitution**

Add to `EditDistanceSimilarityTest.java` using `ide_insert_member`:

```java
@Test
void alignmentPath_identicalSequences_allMatch() {
    var result = EditDistanceSimilarity.compute(
        List.of("A", "B", "C"), List.of("A", "B", "C"));
    assertThat(result.alignment()).containsExactly(
        new EditStep(0, 0, EditOp.MATCH),
        new EditStep(1, 1, EditOp.MATCH),
        new EditStep(2, 2, EditOp.MATCH));
}

@Test
void alignmentPath_substitution() {
    var result = EditDistanceSimilarity.compute(
        List.of("A", "B", "C"), List.of("A", "X", "C"));
    assertThat(result.alignment()).contains(
        new EditStep(1, 1, EditOp.SUBSTITUTE));
}

@Test
void alignmentPath_insertionAndDeletion() {
    var result = EditDistanceSimilarity.compute(
        List.of("A", "B"), List.of("A", "X", "B"));
    long inserts = result.alignment().stream()
        .filter(s -> s.operation() == EditOp.INSERT).count();
    long deletes = result.alignment().stream()
        .filter(s -> s.operation() == EditOp.DELETE).count();
    assertThat(inserts + deletes).isGreaterThan(0);
}

@Test
void alignmentPath_deleteAtStart_queryIndexValid_caseIndexMinusOne() {
    var result = EditDistanceSimilarity.compute(
        List.of("A", "B"), List.of("B"));
    var deleteSteps = result.alignment().stream()
        .filter(s -> s.operation() == EditOp.DELETE).toList();
    for (var step : deleteSteps) {
        assertThat(step.queryIndex()).isGreaterThanOrEqualTo(0);
        assertThat(step.caseIndex()).isEqualTo(-1);
    }
}

@Test
void alignmentPath_insertSteps_queryIndexMinusOne() {
    var result = EditDistanceSimilarity.compute(
        List.of("A"), List.of("A", "B"));
    var insertSteps = result.alignment().stream()
        .filter(s -> s.operation() == EditOp.INSERT).toList();
    for (var step : insertSteps) {
        assertThat(step.queryIndex()).isEqualTo(-1);
        assertThat(step.caseIndex()).isGreaterThanOrEqualTo(0);
    }
}

@Test
void alignmentPath_bothEmpty_emptyPath() {
    var result = EditDistanceSimilarity.compute(List.of(), List.of());
    assertThat(result.score()).isEqualTo(1.0);
    assertThat(result.alignment()).isEmpty();
}

@Test
void alignmentPath_oneEmpty_nonEmptyPath_allDeletes() {
    var result = EditDistanceSimilarity.compute(
        List.of("A", "B"), List.of());
    assertThat(result.score()).isEqualTo(0.0);
    assertThat(result.alignment()).hasSize(2);
    assertThat(result.alignment()).allMatch(s -> s.operation() == EditOp.DELETE);
}

@Test
void alignmentPath_emptyQueryNonEmptyCase_allInserts() {
    var result = EditDistanceSimilarity.compute(
        List.of(), List.of("A", "B"));
    assertThat(result.score()).isEqualTo(0.0);
    assertThat(result.alignment()).hasSize(2);
    assertThat(result.alignment()).allMatch(s -> s.operation() == EditOp.INSERT);
}

@Test
void weightedSubstitution_closerLabelsLowerCost() {
    var subSim = Map.of("A", Map.of("B", 0.8));
    var close = EditDistanceSimilarity.compute(
        List.of("A"), List.of("B"), subSim);
    var uniform = EditDistanceSimilarity.compute(
        List.of("A"), List.of("B"));
    assertThat(close.score()).isGreaterThan(uniform.score());
}

@Test
void weightedSubstitution_symmetricLookup() {
    var subSim = Map.of("A", Map.of("B", 0.7));
    var forward = EditDistanceSimilarity.compute(
        List.of("A"), List.of("B"), subSim);
    var reverse = EditDistanceSimilarity.compute(
        List.of("B"), List.of("A"), subSim);
    assertThat(forward.score()).isCloseTo(reverse.score(), within(0.0001));
}

@Test
void weightedSubstitution_unspecifiedPairsDefaultToUniform() {
    var subSim = Map.of("A", Map.of("B", 0.8));
    var result = EditDistanceSimilarity.compute(
        List.of("X"), List.of("Y"), subSim);
    var uniform = EditDistanceSimilarity.compute(
        List.of("X"), List.of("Y"));
    assertThat(result.score()).isCloseTo(uniform.score(), within(0.0001));
}

@Test
void weightedSubstitution_fractionalDistance() {
    var subSim = Map.of("A", Map.of("B", 0.5));
    var result = EditDistanceSimilarity.compute(
        List.of("A"), List.of("B"), subSim);
    // cost = 1.0 - 0.5 = 0.5, similarity = 1.0 - 0.5/1 = 0.5
    assertThat(result.score()).isCloseTo(0.5, within(0.0001));
}

@Test
void weightedSubstitution_changesAlignmentPath() {
    // Without weights: substitute A→C and A→B both cost 1
    // With weights: A→B costs 0.2 (similarity 0.8), A→C costs 1.0 (similarity 0.0)
    var subSim = Map.of("A", Map.of("B", 0.8));
    var result = EditDistanceSimilarity.compute(
        List.of("A", "A"), List.of("B", "C"), subSim);
    assertThat(result.alignment()).anyMatch(
        s -> s.operation() == EditOp.SUBSTITUTE);
}
```

- [ ] **Step 2: Update existing EditDistanceSimilarityTest assertions to use .score()**

All 9 existing tests assert on the double return value. Update each:
- `assertThat(EditDistanceSimilarity.compute(...)).isEqualTo(...)` → `assertThat(EditDistanceSimilarity.compute(...).score()).isEqualTo(...)`

Use `ide_replace_member` on each test method.

- [ ] **Step 3: Implement EditDistanceSimilarity changes**

Use `ide_edit_member` to rewrite `EditDistanceSimilarity`:

- Change return type to `EditDistanceResult`
- Always use `double[][]` DP table
- Add 3-arg overload with `Map<String, Map<String, Double>> substitutionSimilarities`
- 2-arg `compute` delegates to 3-arg with `null`
- Substitution cost: `a.equals(b) ? 0.0 : (subSim != null ? 1.0 - lookupSimilarity(a, b, subSim) : 1.0)`
- Both-empty: early return `new EditDistanceResult(1.0, List.of())`
- One-empty: DO NOT early return — let DP + backtracing produce the correct non-empty path
- Backtrace: tag each step with `EditOp` (MATCH/SUBSTITUTE/INSERT/DELETE)
- DELETE: `EditStep(i-1, -1, DELETE)`, INSERT: `EditStep(-1, j-1, INSERT)`

Key implementation:
```java
// Backtrace
List<EditStep> path = new ArrayList<>();
int i = n, j = m;
while (i > 0 || j > 0) {
    if (i > 0 && j > 0) {
        double diagCost = dp[i - 1][j - 1];
        double upCost = dp[i - 1][j];
        double leftCost = dp[i][j - 1];
        if (diagCost <= upCost && diagCost <= leftCost) {
            EditOp op = query.get(i - 1).equals(caseSeq.get(j - 1))
                ? EditOp.MATCH : EditOp.SUBSTITUTE;
            path.add(new EditStep(i - 1, j - 1, op));
            i--; j--;
        } else if (upCost <= leftCost) {
            path.add(new EditStep(i - 1, -1, EditOp.DELETE));
            i--;
        } else {
            path.add(new EditStep(-1, j - 1, EditOp.INSERT));
            j--;
        }
    } else if (i > 0) {
        path.add(new EditStep(i - 1, -1, EditOp.DELETE));
        i--;
    } else {
        path.add(new EditStep(-1, j - 1, EditOp.INSERT));
        j--;
    }
}
Collections.reverse(path);
```

- [ ] **Step 4: Update CbrSimilarityScorer.editDistanceSimilarity() to extract .score()**

Use `ide_replace_member` on `CbrSimilarityScorer.editDistanceSimilarity()`:

```java
@SuppressWarnings("unchecked")
private static double editDistanceSimilarity(Object queryVal, Object caseVal) {
    return EditDistanceSimilarity.compute(
        (java.util.List<String>) queryVal,
        (java.util.List<String>) caseVal).score();
}
```

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=EditDistanceSimilarityTest`
Expected: all tests PASS

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrSimilarityScorerTest`
Expected: all tests PASS

- [ ] **Step 6: Verify with diagnostics**

Run: `ide_diagnostics` on `EditDistanceSimilarity.java` and `CbrSimilarityScorer.java`

- [ ] **Step 7: Commit**

```
feat(#92): edit distance alignment path + weighted substitution

EditDistanceSimilarity.compute() returns EditDistanceResult with
EditStep-tagged alignment (MATCH/SUBSTITUTE/INSERT/DELETE). Optional
substitutionSimilarities for domain-specific graded costs. Always
double[][] DP table.
```

---

### Task 4: FeatureField + Scorer integration

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/FeatureField.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/FeatureFieldTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorerTest.java`

**Interfaces:**
- Consumes: `SimilaritySpec.DtwSpec`, `SimilaritySpec.EditDistanceSpec` from Task 1; `DtwSimilarity.compute(q, c, schema, windowSize)` from Task 2; `EditDistanceSimilarity.compute(q, c, subSim)` from Task 3
- Produces: `FeatureField.timeSeries(name, timestampField, spec, innerFields...)`, `FeatureField.discreteSequence(name, spec)`, scorer reads spec and passes parameters

- [ ] **Step 1: Write FeatureField tests**

Add to `FeatureFieldTest.java`:

```java
@Test
void timeSeries_dtwSpec_accepted() {
    var field = FeatureField.timeSeries("curve", "t",
        new SimilaritySpec.DtwSpec(5),
        FeatureField.numeric("t", 0, 30),
        FeatureField.numeric("val", 0, 100));
    assertThat(((FeatureField.TimeSeries) field).similaritySpec())
        .isInstanceOf(SimilaritySpec.DtwSpec.class);
}

@Test
void timeSeries_editDistanceSpec_rejected() {
    assertThatThrownBy(() -> FeatureField.timeSeries("curve", "t",
        new SimilaritySpec.EditDistanceSpec(Map.of()),
        FeatureField.numeric("t", 0, 30),
        FeatureField.numeric("val", 0, 100)))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void timeSeries_noSpec_backwardCompatible() {
    var field = FeatureField.timeSeries("curve", "t",
        FeatureField.numeric("t", 0, 30),
        FeatureField.numeric("val", 0, 100));
    assertThat(((FeatureField.TimeSeries) field).similaritySpec()).isNull();
}

@Test
void discreteSequence_editDistanceSpec_accepted() {
    var field = FeatureField.discreteSequence("phases",
        new SimilaritySpec.EditDistanceSpec(Map.of("A", Map.of("B", 0.5))));
    assertThat(((FeatureField.DiscreteSequence) field).similaritySpec())
        .isInstanceOf(SimilaritySpec.EditDistanceSpec.class);
}

@Test
void discreteSequence_dtwSpec_rejected() {
    assertThatThrownBy(() -> FeatureField.discreteSequence("phases",
        new SimilaritySpec.DtwSpec(5)))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void discreteSequence_noSpec_backwardCompatible() {
    var field = FeatureField.discreteSequence("phases");
    assertThat(((FeatureField.DiscreteSequence) field).similaritySpec()).isNull();
}
```

- [ ] **Step 2: Write scorer integration tests**

Add to `CbrSimilarityScorerTest.java`:

```java
@Test
void dtwSpec_windowedDtw_affectsScore() {
    var schema = CbrFeatureSchema.of("ts-test",
        FeatureField.timeSeries("curve", "t",
            new SimilaritySpec.DtwSpec(1),
            FeatureField.numeric("t", 0, 10),
            FeatureField.numeric("val", 0, 100)));
    var q = Map.<String, Object>of("curve", List.of(
        Map.of("t", 1, "val", 10),
        Map.of("t", 2, "val", 90)));
    var c = Map.<String, Object>of("curve", List.of(
        Map.of("t", 1, "val", 90),
        Map.of("t", 2, "val", 10)));
    double score = CbrSimilarityScorer.score(q, c, Map.of(), schema);
    assertThat(score).isGreaterThan(0.0).isLessThan(1.0);
}

@Test
void editDistanceSpec_weightedSubstitution_affectsScore() {
    var subSim = Map.of("MACRO", Map.of("DEFENSIVE", 0.8));
    var schema = CbrFeatureSchema.of("seq-test",
        FeatureField.discreteSequence("phases",
            new SimilaritySpec.EditDistanceSpec(subSim)));
    var q = Map.<String, Object>of("phases", List.of("MACRO"));
    var c = Map.<String, Object>of("phases", List.of("DEFENSIVE"));
    double withSpec = CbrSimilarityScorer.score(q, c, Map.of(), schema);

    var schemaNoSpec = CbrFeatureSchema.of("seq-test2",
        FeatureField.discreteSequence("phases"));
    double withoutSpec = CbrSimilarityScorer.score(q, c, Map.of(), schemaNoSpec);

    assertThat(withSpec).isGreaterThan(withoutSpec);
}
```

- [ ] **Step 3: Implement FeatureField changes**

Use `ide_edit_member` to update `FeatureField.TimeSeries` record — add 4th component `SimilaritySpec similaritySpec`. Update constructor validation to accept `DtwSpec`, reject all others. Existing 3-arg constructor delegates to canonical 4-arg with `null`.

Use `ide_edit_member` to update `FeatureField.DiscreteSequence` record — add 2nd component `SimilaritySpec similaritySpec`. Update constructor validation. Existing 1-arg constructor delegates with `null`.

Add factory method overloads using `ide_insert_member`:
```java
static FeatureField timeSeries(String name, String timestampField,
                                SimilaritySpec spec, FeatureField... innerFields) {
    return new TimeSeries(name, List.of(innerFields), timestampField, spec);
}

static FeatureField discreteSequence(String name, SimilaritySpec spec) {
    return new DiscreteSequence(name, spec);
}
```

Update existing factory methods to pass `null` as the spec.

- [ ] **Step 4: Update CbrSimilarityScorer to read specs**

Use `ide_replace_member` on `dtwSimilarity()`:
```java
@SuppressWarnings("unchecked")
private static double dtwSimilarity(FeatureField.TimeSeries ts,
                                     Object queryVal, Object caseVal) {
    Integer windowSize = ts.similaritySpec() instanceof SimilaritySpec.DtwSpec ds
        ? ds.windowSize() : null;
    return DtwSimilarity.compute(
        (java.util.List<java.util.Map<String, Object>>) queryVal,
        (java.util.List<java.util.Map<String, Object>>) caseVal, ts, windowSize).score();
}
```

Use `ide_replace_member` on `editDistanceSimilarity()` — add `DiscreteSequence` parameter:
```java
@SuppressWarnings("unchecked")
private static double editDistanceSimilarity(FeatureField.DiscreteSequence ds,
                                              Object queryVal, Object caseVal) {
    java.util.Map<String, java.util.Map<String, Double>> subSim =
        ds.similaritySpec() instanceof SimilaritySpec.EditDistanceSpec es
        ? es.substitutionSimilarities() : null;
    return EditDistanceSimilarity.compute(
        (java.util.List<String>) queryVal,
        (java.util.List<String>) caseVal, subSim).score();
}
```

Use `ide_replace_member` on `localSimilarity()` — update the `DiscreteSequence` branch to pass the field:
```java
case FeatureField.DiscreteSequence ds -> editDistanceSimilarity(ds, queryVal, caseVal);
```

Use `ide_replace_member` on `categoricalSimilarity()` — add reject cases for DtwSpec and EditDistanceSpec in the switch.

Use `ide_replace_member` on `numericSimilarity()` — add reject cases for DtwSpec and EditDistanceSpec in the switch.

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api`
Expected: ALL tests pass (FeatureFieldTest, CbrSimilarityScorerTest, DtwSimilarityTest, EditDistanceSimilarityTest, SimilaritySpecTest, etc.)

- [ ] **Step 6: Verify with diagnostics**

Run: `ide_diagnostics` on `FeatureField.java` and `CbrSimilarityScorer.java`

- [ ] **Step 7: Commit**

```
feat(#92): SimilaritySpec on temporal fields + scorer integration

TimeSeries gains optional DtwSpec (windowed DTW). DiscreteSequence gains
optional EditDistanceSpec (weighted substitution). CbrSimilarityScorer
reads specs and passes parameters to algorithms.
```

---

### Task 5: Contract tests + build verification

**Files:**
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`

**Interfaces:**
- Consumes: All APIs from Tasks 1-4

- [ ] **Step 1: Add contract tests**

Add helper method for schema with specs:
```java
private void registerTemporalSchemaWithSpecs() {
    store().registerSchema(CbrFeatureSchema.of("temporal-game-specs",
        FeatureField.categorical("race"),
        FeatureField.numeric("mmr", 0, 8000),
        FeatureField.timeSeries("economyCurve", "minute",
            new SimilaritySpec.DtwSpec(5),
            FeatureField.numeric("minute", 0, 30),
            FeatureField.numeric("economy", 0, 500),
            FeatureField.numeric("army", 0, 200),
            FeatureField.categorical("posture")),
        FeatureField.discreteSequence("phaseProgression",
            new SimilaritySpec.EditDistanceSpec(Map.of(
                "MACRO", Map.of("DEFENSIVE", 0.8, "AGGRESSIVE", 0.3),
                "DEFENSIVE", Map.of("AGGRESSIVE", 0.1))))));
}
```

Add contract tests using `ide_insert_member` after the last temporal test:

```java
@Test
void temporal_timeSeries_dtwSpec_acceptedBySchema() {
    registerTemporalSchemaWithSpecs();
}

@Test
void temporal_timeSeries_editDistanceSpec_rejectedBySchema() {
    assertThatThrownBy(() -> store().registerSchema(CbrFeatureSchema.of("bad-ts",
        FeatureField.timeSeries("curve", "t",
            new SimilaritySpec.EditDistanceSpec(Map.of()),
            FeatureField.numeric("t", 0, 10),
            FeatureField.numeric("val", 0, 100)))))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void temporal_discreteSequence_editDistanceSpec_acceptedBySchema() {
    registerTemporalSchemaWithSpecs();
}

@Test
void temporal_discreteSequence_dtwSpec_rejectedBySchema() {
    assertThatThrownBy(() -> store().registerSchema(CbrFeatureSchema.of("bad-ds",
        FeatureField.discreteSequence("phases", new SimilaritySpec.DtwSpec(3)))))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void temporal_timeSeries_dtwSpec_affectsRetrieval() {
    registerTemporalSchemaWithSpecs();
    // Store two cases with different economy curves
    store().store(new FeatureVectorCbrCase("close match", "sol", null, null, Map.of(
        "race", "Terran",
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"),
            Map.of("minute", 3, "economy", 45, "army", 5, "posture", "MACRO")))),
        "temporal-game-specs", ENTITY, CBR, TENANT, "close");
    store().store(new FeatureVectorCbrCase("far match", "sol", null, null, Map.of(
        "race", "Terran",
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 400, "army", 150, "posture", "AGGRESSIVE"),
            Map.of("minute", 3, "economy", 100, "army", 50, "posture", "DEFENSIVE")))),
        "temporal-game-specs", ENTITY, CBR, TENANT, "far");
    var query = CbrQuery.of(TENANT, CBR, "temporal-game-specs", Map.of(
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 32, "army", 2, "posture", "MACRO"),
            Map.of("minute", 3, "economy", 47, "army", 7, "posture", "MACRO"))),
        10).withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSizeGreaterThanOrEqualTo(2);
    assertThat(results.get(0).cbrCase().problem()).isEqualTo("close match");
}

@Test
void temporal_discreteSequence_editDistanceSpec_affectsRetrieval() {
    registerTemporalSchemaWithSpecs();
    // MACRO→DEFENSIVE has similarity 0.8 (cost 0.2), MACRO→AGGRESSIVE has 0.3 (cost 0.7)
    store().store(new FeatureVectorCbrCase("defensive", "sol", null, null, Map.of(
        "race", "Terran",
        "phaseProgression", List.of("MACRO", "DEFENSIVE"))),
        "temporal-game-specs", ENTITY, CBR, TENANT, "def");
    store().store(new FeatureVectorCbrCase("aggressive", "sol", null, null, Map.of(
        "race", "Terran",
        "phaseProgression", List.of("MACRO", "AGGRESSIVE"))),
        "temporal-game-specs", ENTITY, CBR, TENANT, "agg");
    var query = CbrQuery.of(TENANT, CBR, "temporal-game-specs", Map.of(
        "phaseProgression", List.of("MACRO", "MACRO")),
        10).withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSizeGreaterThanOrEqualTo(2);
    // MACRO→DEFENSIVE costs 0.2, MACRO→AGGRESSIVE costs 0.7 → defensive ranks higher
    assertThat(results.get(0).cbrCase().problem()).isEqualTo("defensive");
}

@Test
void temporal_timeSeries_windowedDtw_similarResult() {
    registerTemporalSchemaWithSpecs();
    storeTemporalCase("windowed test", Map.of(
        "race", "Terran",
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"),
            Map.of("minute", 3, "economy", 45, "army", 5, "posture", "MACRO"))),
        "w1");
    var query = CbrQuery.of(TENANT, CBR, "temporal-game-specs", Map.of(
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 32, "army", 2, "posture", "MACRO"),
            Map.of("minute", 3, "economy", 43, "army", 3, "posture", "MACRO"))),
        10).withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).isNotEmpty();
    assertThat(results.get(0).score()).isGreaterThan(0.5);
}
```

Note: `storeTemporalCase` uses caseType `"temporal-game"` but these tests use `"temporal-game-specs"`. Add a helper:
```java
private String storeTemporalSpecCase(String problem, Map<String, Object> features, String caseId) {
    return store().store(
        new FeatureVectorCbrCase(problem, "solution", null, null, features),
        "temporal-game-specs", ENTITY, CBR, TENANT, caseId);
}
```

- [ ] **Step 2: Run contract tests via in-memory backend**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api,memory-testing,memory-cbr-inmem -Dtest="*ContractTest*,*CbrTest*"`
Expected: ALL tests pass

- [ ] **Step 3: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS — all modules compile and tests pass

- [ ] **Step 4: Commit**

```
test(#92): contract tests for windowed DTW + weighted edit distance

SimilaritySpec on temporal fields: schema acceptance/rejection,
windowed DTW retrieval ranking, weighted edit distance retrieval
ranking with domain-specific substitution costs.
```

---

## Verification Checklist

After all tasks:
- [ ] `mvn clean install` passes with zero failures
- [ ] `ide_diagnostics` clean on all modified files
- [ ] All acceptance criteria from #92 addressed:
  - [x] DTW similarity for continuous-valued temporal case fields (delivered in #91)
  - [x] Edit distance for discrete sequence case fields (delivered in #91)
  - [x] Both integrate with CbrQuery (delivered in #91)
  - [ ] Performance: DTW query over 1000 cases × 50 time steps < 500ms (verify empirically)
  - [ ] Alignment path available for debugging
- [ ] Deferred issues filed: #137 (approximate DTW), #138 (Itakura parallelogram), #139 (insert/delete costs)

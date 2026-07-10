# Temporal Case Representation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #91 — feat: temporal case representation — time-series segments as case fields
**Issue group:** #91, #92 (algorithms delivered here; alignment path extraction deferred)

**Goal:** Extend the CBR feature system with TimeSeries and DiscreteSequence field types, enabling ordered-sequence similarity matching (DTW, edit distance) alongside flat features.

**Architecture:** Two new sealed permits on `FeatureField` — `TimeSeries` (multi-dimensional observations ordered by a timestamp field, scored via DTW) and `DiscreteSequence` (ordered categorical labels, scored via edit distance). Both live in `features()` map, validated by `CbrFeatureValidator`, scored by `CbrSimilarityScorer`. DTW and edit distance are pure-Java algorithms in `memory-api`. No new modules.

**Tech Stack:** Java 21, JUnit 5, AssertJ

## Global Constraints

- Java 21 language features (sealed interfaces, records, pattern matching)
- All new code in `memory-api` package `io.casehub.neocortex.memory.cbr`
- Pure Java, Tier 1 — zero external dependencies for algorithms
- Existing exhaustive switches on `FeatureField` must be updated (compiler enforces)
- Contract tests in `memory-testing` — all backends must pass
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`

---

### Task 1: FeatureField — TimeSeries and DiscreteSequence variants

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/FeatureField.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/FeatureFieldTest.java`

**Interfaces:**
- Consumes: existing `FeatureField` sealed interface, `validateFlatFields()` private method
- Produces:
  - `FeatureField.TimeSeries(String name, List<FeatureField> innerFields, String timestampField)` — record implementing `FeatureField`
  - `FeatureField.DiscreteSequence(String name)` — record implementing `FeatureField`
  - `FeatureField.timeSeries(String name, String timestampField, FeatureField... innerFields)` — static factory
  - `FeatureField.discreteSequence(String name)` — static factory

- [ ] **Step 1: Write failing tests for TimeSeries construction**

```java
@Test
void timeSeries_validConstruction() {
    var f = FeatureField.timeSeries("economyCurve", "minute",
            FeatureField.numeric("minute", 0, 30),
            FeatureField.numeric("economy", 0, 500),
            FeatureField.categorical("posture"));
    assertThat(f).isInstanceOf(FeatureField.TimeSeries.class);
    assertThat(f.name()).isEqualTo("economyCurve");
    var ts = (FeatureField.TimeSeries) f;
    assertThat(ts.innerFields()).hasSize(3);
    assertThat(ts.timestampField()).isEqualTo("minute");
}

@Test
void timeSeries_timestampFieldMustExist() {
    assertThatThrownBy(() -> FeatureField.timeSeries("ts", "nonexistent",
            FeatureField.numeric("minute", 0, 30)))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("timestampField");
}

@Test
void timeSeries_timestampFieldMustBeNumeric() {
    assertThatThrownBy(() -> FeatureField.timeSeries("ts", "phase",
            FeatureField.categorical("phase")))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("Numeric");
}

@Test
void timeSeries_requiresNonTimestampNumericField() {
    assertThatThrownBy(() -> FeatureField.timeSeries("ts", "minute",
            FeatureField.numeric("minute", 0, 30),
            FeatureField.categorical("phase")))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("non-timestamp Numeric");
}

@Test
void timeSeries_rejectsEmptyInnerFields() {
    assertThatThrownBy(() -> FeatureField.timeSeries("ts", "minute"))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void timeSeries_nullNameRejected() {
    assertThatThrownBy(() -> FeatureField.timeSeries(null, "minute",
            FeatureField.numeric("minute", 0, 30),
            FeatureField.numeric("val", 0, 100)))
        .isInstanceOf(NullPointerException.class);
}

@Test
void timeSeries_innerFieldsDefensivelyCopied() {
    var inner = new java.util.ArrayList<>(java.util.List.of(
            FeatureField.numeric("minute", 0, 30),
            FeatureField.numeric("val", 0, 100)));
    var f = new FeatureField.TimeSeries("ts", inner, "minute");
    inner.add(FeatureField.numeric("extra", 0, 10));
    assertThat(((FeatureField.TimeSeries) f).innerFields()).hasSize(2);
}
```

- [ ] **Step 2: Write failing tests for DiscreteSequence construction**

```java
@Test
void discreteSequence_validConstruction() {
    var f = FeatureField.discreteSequence("phases");
    assertThat(f).isInstanceOf(FeatureField.DiscreteSequence.class);
    assertThat(f.name()).isEqualTo("phases");
}

@Test
void discreteSequence_nullNameRejected() {
    assertThatThrownBy(() -> FeatureField.discreteSequence(null))
        .isInstanceOf(NullPointerException.class);
}
```

- [ ] **Step 3: Write failing tests for validateFlatFields rejection of temporal types**

```java
@Test
void nestedObject_rejectsTimeSeries() {
    assertThatThrownBy(() -> FeatureField.nestedObject("bad",
            FeatureField.timeSeries("inner", "t",
                FeatureField.numeric("t", 0, 10),
                FeatureField.numeric("v", 0, 100))))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("TimeSeries");
}

@Test
void nestedObject_rejectsDiscreteSequence() {
    assertThatThrownBy(() -> FeatureField.nestedObject("bad",
            FeatureField.discreteSequence("seq")))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("DiscreteSequence");
}

@Test
void objectList_rejectsTimeSeries() {
    assertThatThrownBy(() -> FeatureField.objectList("bad",
            FeatureField.timeSeries("inner", "t",
                FeatureField.numeric("t", 0, 10),
                FeatureField.numeric("v", 0, 100))))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("TimeSeries");
}

@Test
void timeSeries_rejectsTemporalInnerFields() {
    assertThatThrownBy(() -> FeatureField.timeSeries("outer", "t",
            FeatureField.numeric("t", 0, 10),
            FeatureField.numeric("v", 0, 100),
            FeatureField.discreteSequence("nested")))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("DiscreteSequence");
}
```

- [ ] **Step 4: Run tests — verify all fail with compilation errors**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=FeatureFieldTest -Dsurefire.failIfNoSpecifiedTests=false
```

Expected: COMPILATION ERROR — `TimeSeries`, `DiscreteSequence`, `timeSeries()`, `discreteSequence()` not found.

- [ ] **Step 5: Implement TimeSeries and DiscreteSequence**

Add to `FeatureField.java`:

1. Update sealed permits: add `FeatureField.TimeSeries`, `FeatureField.DiscreteSequence`
2. Add `TimeSeries` record with compact constructor validating:
   - `name` not null
   - `innerFields` not null, not empty, defensively copied
   - Calls `validateFlatFields(innerFields)` (rejects nesting, SimilaritySpec on inner, semantic Text)
   - `timestampField` not null, must reference an existing inner field by name
   - Referenced inner field must be `Numeric`
   - At least one non-timestamp `Numeric` inner field must exist
3. Add `DiscreteSequence` record with compact constructor: `name` not null
4. Update `validateFlatFields()` — add cases for `TimeSeries` and `DiscreteSequence` that throw `IllegalArgumentException`
5. Add static factories: `timeSeries(String name, String timestampField, FeatureField... innerFields)` and `discreteSequence(String name)`

- [ ] **Step 6: Run tests — verify all pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=FeatureFieldTest
```

Expected: ALL PASS

- [ ] **Step 7: Fix compilation in downstream modules**

The sealed interface change will break exhaustive switches in `CbrFeatureValidator`, `CbrSimilarityScorer`, and `CbrQueryTranslator`. Add temporary `throw new UnsupportedOperationException("temporal: TODO")` branches to make the build compile. These are replaced in Tasks 2-4.

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl memory-api,memory-testing,memory-cbr-inmem,memory-qdrant,memory-cbr-embedding,memory-cbr-crossencoder
```

Expected: BUILD SUCCESS

- [ ] **Step 8: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#91): FeatureField.TimeSeries and DiscreteSequence variants"
```

---

### Task 2: CbrFeatureValidator — temporal field validation

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFeatureValidator.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrFeatureValidatorTest.java` (create)

**Interfaces:**
- Consumes: `FeatureField.TimeSeries`, `FeatureField.DiscreteSequence` from Task 1
- Produces: Updated `validateStoreFeatures()`, `validateQueryFeatures()`, `validateFilters()` — accepting temporal fields with proper validation

- [ ] **Step 1: Write failing tests for store-time TimeSeries validation**

```java
package io.casehub.neocortex.memory.cbr;

import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThatNoException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class CbrFeatureValidatorTest {

    private static final CbrFeatureSchema TEMPORAL_SCHEMA = CbrFeatureSchema.of("game",
        FeatureField.timeSeries("curve", "t",
            FeatureField.numeric("t", 0, 30),
            FeatureField.numeric("val", 0, 100),
            FeatureField.categorical("label")),
        FeatureField.discreteSequence("phases"),
        FeatureField.categorical("race"));

    // --- Store: TimeSeries ---
    @Test
    void store_timeSeries_validAscending() {
        var features = Map.<String, Object>of("curve", List.of(
            Map.of("t", 1, "val", 30, "label", "A"),
            Map.of("t", 3, "val", 45, "label", "B")));
        assertThatNoException().isThrownBy(() ->
            CbrFeatureValidator.validateStoreFeatures(features, TEMPORAL_SCHEMA));
    }

    @Test
    void store_timeSeries_nonAscending_rejected() {
        var features = Map.<String, Object>of("curve", List.of(
            Map.of("t", 3, "val", 45, "label", "B"),
            Map.of("t", 1, "val", 30, "label", "A")));
        assertThatThrownBy(() ->
            CbrFeatureValidator.validateStoreFeatures(features, TEMPORAL_SCHEMA))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("ascending");
    }

    @Test
    void store_timeSeries_equalTimestamps_rejected() {
        var features = Map.<String, Object>of("curve", List.of(
            Map.of("t", 1, "val", 30, "label", "A"),
            Map.of("t", 1, "val", 45, "label", "B")));
        assertThatThrownBy(() ->
            CbrFeatureValidator.validateStoreFeatures(features, TEMPORAL_SCHEMA))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("ascending");
    }

    @Test
    void store_timeSeries_missingTimestampField_rejected() {
        var features = Map.<String, Object>of("curve", List.of(
            Map.of("val", 30, "label", "A")));
        assertThatThrownBy(() ->
            CbrFeatureValidator.validateStoreFeatures(features, TEMPORAL_SCHEMA))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("timestamp");
    }

    @Test
    void store_timeSeries_wrongType_rejected() {
        var features = Map.<String, Object>of("curve", "not-a-list");
        assertThatThrownBy(() ->
            CbrFeatureValidator.validateStoreFeatures(features, TEMPORAL_SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void store_timeSeries_wrongInnerType_rejected() {
        var features = Map.<String, Object>of("curve", List.of(
            Map.of("t", 1, "val", "not-a-number", "label", "A")));
        assertThatThrownBy(() ->
            CbrFeatureValidator.validateStoreFeatures(features, TEMPORAL_SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void store_timeSeries_emptyList_accepted() {
        var features = Map.<String, Object>of("curve", List.of());
        assertThatNoException().isThrownBy(() ->
            CbrFeatureValidator.validateStoreFeatures(features, TEMPORAL_SCHEMA));
    }

    // --- Store: DiscreteSequence ---
    @Test
    void store_discreteSequence_valid() {
        var features = Map.<String, Object>of("phases", List.of("A", "B", "C"));
        assertThatNoException().isThrownBy(() ->
            CbrFeatureValidator.validateStoreFeatures(features, TEMPORAL_SCHEMA));
    }

    @Test
    void store_discreteSequence_wrongType_rejected() {
        var features = Map.<String, Object>of("phases", "not-a-list");
        assertThatThrownBy(() ->
            CbrFeatureValidator.validateStoreFeatures(features, TEMPORAL_SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void store_discreteSequence_nonStringElement_rejected() {
        var features = Map.<String, Object>of("phases", List.of("A", 42));
        assertThatThrownBy(() ->
            CbrFeatureValidator.validateStoreFeatures(features, TEMPORAL_SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void store_discreteSequence_emptyList_accepted() {
        var features = Map.<String, Object>of("phases", List.of());
        assertThatNoException().isThrownBy(() ->
            CbrFeatureValidator.validateStoreFeatures(features, TEMPORAL_SCHEMA));
    }

    // --- Query: temporal fields allowed ---
    @Test
    void query_timeSeries_allowed() {
        var features = Map.<String, Object>of("curve", List.of(
            Map.of("t", 1, "val", 30, "label", "A")));
        assertThatNoException().isThrownBy(() ->
            CbrFeatureValidator.validateQueryFeatures(features, TEMPORAL_SCHEMA));
    }

    @Test
    void query_discreteSequence_allowed() {
        var features = Map.<String, Object>of("phases", List.of("A", "B"));
        assertThatNoException().isThrownBy(() ->
            CbrFeatureValidator.validateQueryFeatures(features, TEMPORAL_SCHEMA));
    }

    // --- Filters: temporal fields rejected ---
    @Test
    void filter_onTimeSeries_rejected() {
        assertThatThrownBy(() ->
            CbrFeatureValidator.validateFilters(
                Map.of("curve", CbrFilter.contains("X")), TEMPORAL_SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void filter_onDiscreteSequence_rejected() {
        assertThatThrownBy(() ->
            CbrFeatureValidator.validateFilters(
                Map.of("phases", CbrFilter.contains("X")), TEMPORAL_SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }
}
```

- [ ] **Step 2: Run tests — verify failures**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrFeatureValidatorTest -Dsurefire.failIfNoSpecifiedTests=false
```

Expected: FAIL — UnsupportedOperationException from TODO branches in Task 1 Step 7.

- [ ] **Step 3: Implement temporal validation in CbrFeatureValidator**

Replace the TODO branches added in Task 1 with proper validation:

**`validateStoreFeatures()`:**
- `TimeSeries ts` case: validate value is `List<?>`, each element is `Map<?,?>`, validate inner values against `ts.innerFields()`, check timestamp field present in each observation, check ascending order
- `DiscreteSequence ds` case: validate value is `List<?>`, each element is `String`

**`validateQueryFeatures()`:**
- `TimeSeries ts` case: same validation as store (ascending timestamps required in query too)
- `DiscreteSequence ds` case: same as store

**`validateFilters()`:**
- Add rejection for `TimeSeries` and `DiscreteSequence` alongside existing `CategoricalList` check in `requireCategoricalList` — or add a separate check: temporal fields throw `IllegalArgumentException("Temporal field 'X' does not support filters")`

- [ ] **Step 4: Run tests — verify all pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrFeatureValidatorTest
```

Expected: ALL PASS

- [ ] **Step 5: Run full memory-api tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api
```

Expected: ALL PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#91): CbrFeatureValidator — temporal field validation"
```

---

### Task 3: DTW and edit distance algorithms + CbrSimilarityScorer integration

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/DtwSimilarity.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/EditDistanceSimilarity.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java`
- Create: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/DtwSimilarityTest.java`
- Create: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/EditDistanceSimilarityTest.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorerTest.java` (existing — may need new tests)

**Interfaces:**
- Consumes: `FeatureField.TimeSeries`, `FeatureField.DiscreteSequence` from Task 1
- Produces:
  - `DtwSimilarity.compute(List<Map<String, Object>> query, List<Map<String, Object>> caseSeq, FeatureField.TimeSeries schema)` → `double` in [0, 1]
  - `EditDistanceSimilarity.compute(List<String> query, List<String> caseSeq)` → `double` in [0, 1]
  - Updated `CbrSimilarityScorer.localSimilarity()` with TimeSeries → DTW, DiscreteSequence → edit distance branches
  - Updated `CbrSimilarityScorer.score()` — temporal fields pass through to `localSimilarity()` (not skipped like structured fields)

- [ ] **Step 1: Write DTW algorithm unit tests**

```java
package io.casehub.neocortex.memory.cbr;

import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

class DtwSimilarityTest {

    private static final FeatureField.TimeSeries SCHEMA =
        (FeatureField.TimeSeries) FeatureField.timeSeries("curve", "t",
            FeatureField.numeric("t", 0, 30),
            FeatureField.numeric("val", 0, 100));

    @Test
    void identicalSequences_perfectSimilarity() {
        var seq = List.of(
            Map.<String, Object>of("t", 1, "val", 50),
            Map.<String, Object>of("t", 2, "val", 60));
        assertThat(DtwSimilarity.compute(seq, seq, SCHEMA)).isEqualTo(1.0);
    }

    @Test
    void completelyDifferent_lowSimilarity() {
        var q = List.of(Map.<String, Object>of("t", 1, "val", 0));
        var c = List.of(Map.<String, Object>of("t", 1, "val", 100));
        assertThat(DtwSimilarity.compute(q, c, SCHEMA)).isLessThan(0.5);
    }

    @Test
    void variableLength_dtwAligns() {
        var q = List.of(
            Map.<String, Object>of("t", 1, "val", 50),
            Map.<String, Object>of("t", 2, "val", 60));
        var c = List.of(
            Map.<String, Object>of("t", 1, "val", 50),
            Map.<String, Object>of("t", 2, "val", 55),
            Map.<String, Object>of("t", 3, "val", 60));
        double sim = DtwSimilarity.compute(q, c, SCHEMA);
        assertThat(sim).isGreaterThan(0.5);
    }

    @Test
    void singleObservation_works() {
        var q = List.of(Map.<String, Object>of("t", 1, "val", 50));
        var c = List.of(Map.<String, Object>of("t", 1, "val", 55));
        double sim = DtwSimilarity.compute(q, c, SCHEMA);
        assertThat(sim).isGreaterThan(0.9);
    }

    @Test
    void timestampFieldExcludedFromDistance() {
        // Same val but different timestamps — should have perfect similarity
        // because timestamp is excluded from distance
        var q = List.of(Map.<String, Object>of("t", 1, "val", 50));
        var c = List.of(Map.<String, Object>of("t", 29, "val", 50));
        assertThat(DtwSimilarity.compute(q, c, SCHEMA)).isEqualTo(1.0);
    }

    @Test
    void closerTrajectory_ranksHigher() {
        var query = List.of(
            Map.<String, Object>of("t", 1, "val", 30),
            Map.<String, Object>of("t", 2, "val", 60));
        var close = List.of(
            Map.<String, Object>of("t", 1, "val", 32),
            Map.<String, Object>of("t", 2, "val", 58));
        var far = List.of(
            Map.<String, Object>of("t", 1, "val", 80),
            Map.<String, Object>of("t", 2, "val", 10));
        assertThat(DtwSimilarity.compute(query, close, SCHEMA))
            .isGreaterThan(DtwSimilarity.compute(query, far, SCHEMA));
    }

    @Test
    void multiDimensional_allNumericFieldsContribute() {
        var schema = (FeatureField.TimeSeries) FeatureField.timeSeries("s", "t",
            FeatureField.numeric("t", 0, 10),
            FeatureField.numeric("x", 0, 100),
            FeatureField.numeric("y", 0, 100));
        var q = List.of(Map.<String, Object>of("t", 1, "x", 50, "y", 50));
        var cSameX = List.of(Map.<String, Object>of("t", 1, "x", 50, "y", 100));
        var cSameY = List.of(Map.<String, Object>of("t", 1, "x", 100, "y", 50));
        // Both differ on one dimension by 50 — should be equal similarity
        assertThat(DtwSimilarity.compute(q, cSameX, schema))
            .isCloseTo(DtwSimilarity.compute(q, cSameY, schema), within(0.001));
    }

    @Test
    void bothEmpty_perfectSimilarity() {
        List<Map<String, Object>> empty = List.of();
        assertThat(DtwSimilarity.compute(empty, empty, SCHEMA)).isEqualTo(1.0);
    }

    @Test
    void oneEmpty_zeroSimilarity() {
        var q = List.of(Map.<String, Object>of("t", 1, "val", 50));
        List<Map<String, Object>> empty = List.of();
        assertThat(DtwSimilarity.compute(q, empty, SCHEMA)).isEqualTo(0.0);
        assertThat(DtwSimilarity.compute(empty, q, SCHEMA)).isEqualTo(0.0);
    }
}
```

- [ ] **Step 2: Write edit distance algorithm unit tests**

```java
package io.casehub.neocortex.memory.cbr;

import org.junit.jupiter.api.Test;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

class EditDistanceSimilarityTest {

    @Test
    void identicalSequences_perfectSimilarity() {
        assertThat(EditDistanceSimilarity.compute(
            List.of("A", "B", "C"), List.of("A", "B", "C")))
            .isEqualTo(1.0);
    }

    @Test
    void oneSubstitution() {
        double sim = EditDistanceSimilarity.compute(
            List.of("A", "B", "C"), List.of("A", "X", "C"));
        assertThat(sim).isCloseTo(2.0 / 3.0, within(0.001));
    }

    @Test
    void completelyDifferent() {
        double sim = EditDistanceSimilarity.compute(
            List.of("A", "B", "C"), List.of("X", "Y", "Z"));
        assertThat(sim).isEqualTo(0.0);
    }

    @Test
    void bothEmpty_perfectSimilarity() {
        assertThat(EditDistanceSimilarity.compute(List.of(), List.of()))
            .isEqualTo(1.0);
    }

    @Test
    void oneEmpty_zeroSimilarity() {
        assertThat(EditDistanceSimilarity.compute(List.of("A", "B"), List.of()))
            .isEqualTo(0.0);
        assertThat(EditDistanceSimilarity.compute(List.of(), List.of("A", "B")))
            .isEqualTo(0.0);
    }

    @Test
    void insertion() {
        double sim = EditDistanceSimilarity.compute(
            List.of("A", "B"), List.of("A", "X", "B"));
        // edit distance 1, max length 3
        assertThat(sim).isCloseTo(2.0 / 3.0, within(0.001));
    }

    @Test
    void deletion() {
        double sim = EditDistanceSimilarity.compute(
            List.of("A", "X", "B"), List.of("A", "B"));
        assertThat(sim).isCloseTo(2.0 / 3.0, within(0.001));
    }

    @Test
    void singleElementMatch() {
        assertThat(EditDistanceSimilarity.compute(
            List.of("A"), List.of("A"))).isEqualTo(1.0);
    }

    @Test
    void singleElementMismatch() {
        assertThat(EditDistanceSimilarity.compute(
            List.of("A"), List.of("B"))).isEqualTo(0.0);
    }
}
```

- [ ] **Step 3: Run tests — verify they fail (classes don't exist)**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest="DtwSimilarityTest,EditDistanceSimilarityTest" -Dsurefire.failIfNoSpecifiedTests=false
```

Expected: COMPILATION ERROR

- [ ] **Step 4: Implement DtwSimilarity**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/DtwSimilarity.java`:

```java
package io.casehub.neocortex.memory.cbr;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class DtwSimilarity {

    private DtwSimilarity() {}

    public static double compute(List<Map<String, Object>> query,
                                  List<Map<String, Object>> caseSeq,
                                  FeatureField.TimeSeries schema) {
        int n = query.size();
        int m = caseSeq.size();
        if (n == 0 && m == 0) return 1.0;
        if (n == 0 || m == 0) return 0.0;

        List<FeatureField.Numeric> numericFields = scorableNumericFields(schema);

        double[][] cost = new double[n + 1][m + 1];
        for (int i = 0; i <= n; i++) cost[i][0] = Double.MAX_VALUE;
        for (int j = 0; j <= m; j++) cost[0][j] = Double.MAX_VALUE;
        cost[0][0] = 0.0;

        for (int i = 1; i <= n; i++) {
            for (int j = 1; j <= m; j++) {
                double dist = observationDistance(query.get(i - 1), caseSeq.get(j - 1), numericFields);
                cost[i][j] = dist + Math.min(cost[i - 1][j],
                                     Math.min(cost[i][j - 1], cost[i - 1][j - 1]));
            }
        }

        double dtwDistance = cost[n][m];
        double normalized = dtwDistance / Math.max(n, m);
        return 1.0 / (1.0 + normalized);
    }

    static List<FeatureField.Numeric> scorableNumericFields(FeatureField.TimeSeries schema) {
        List<FeatureField.Numeric> result = new ArrayList<>();
        for (FeatureField f : schema.innerFields()) {
            if (f instanceof FeatureField.Numeric num && !f.name().equals(schema.timestampField())) {
                result.add(num);
            }
        }
        return result;
    }

    private static double observationDistance(Map<String, Object> a, Map<String, Object> b,
                                              List<FeatureField.Numeric> fields) {
        double sumSq = 0.0;
        for (FeatureField.Numeric f : fields) {
            double range = f.max() - f.min();
            if (range <= 0) continue;
            Number aVal = (Number) a.get(f.name());
            Number bVal = (Number) b.get(f.name());
            if (aVal == null || bVal == null) continue;
            double diff = (aVal.doubleValue() - bVal.doubleValue()) / range;
            sumSq += diff * diff;
        }
        return Math.sqrt(sumSq);
    }
}
```

- [ ] **Step 5: Implement EditDistanceSimilarity**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/EditDistanceSimilarity.java`:

```java
package io.casehub.neocortex.memory.cbr;

import java.util.List;

public final class EditDistanceSimilarity {

    private EditDistanceSimilarity() {}

    public static double compute(List<String> query, List<String> caseSeq) {
        int n = query.size();
        int m = caseSeq.size();
        if (n == 0 && m == 0) return 1.0;
        if (n == 0 || m == 0) return 0.0;

        int[][] dp = new int[n + 1][m + 1];
        for (int i = 0; i <= n; i++) dp[i][0] = i;
        for (int j = 0; j <= m; j++) dp[0][j] = j;

        for (int i = 1; i <= n; i++) {
            for (int j = 1; j <= m; j++) {
                int cost = query.get(i - 1).equals(caseSeq.get(j - 1)) ? 0 : 1;
                dp[i][j] = Math.min(dp[i - 1][j] + 1,
                            Math.min(dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost));
            }
        }

        int editDistance = dp[n][m];
        return 1.0 - ((double) editDistance / Math.max(n, m));
    }
}
```

- [ ] **Step 6: Run algorithm tests — verify all pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest="DtwSimilarityTest,EditDistanceSimilarityTest"
```

Expected: ALL PASS

- [ ] **Step 7: Integrate into CbrSimilarityScorer**

Update `CbrSimilarityScorer`:

1. In `score()`: update the skip-logic guard. Change from:
   ```java
   if (field instanceof FeatureField.CategoricalList
       || field instanceof FeatureField.NestedObject
       || field instanceof FeatureField.ObjectList) {continue;}
   ```
   Keep this guard as-is — temporal fields are NOT listed, so they pass through. But add a clarifying comment or switch the guard to explicitly name the non-scorable types rather than relying on negative matching.

2. In `localSimilarity()`: replace the TODO branches with:
   ```java
   case FeatureField.TimeSeries ts -> dtwSimilarity(ts, queryVal, caseVal, overrides);
   case FeatureField.DiscreteSequence ds -> editDistanceSimilarity(queryVal, caseVal, overrides);
   ```

3. Add private methods:
   ```java
   @SuppressWarnings("unchecked")
   private static double dtwSimilarity(FeatureField.TimeSeries ts,
                                        Object queryVal, Object caseVal,
                                        Map<String, LocalSimilarityFunction> overrides) {
       LocalSimilarityFunction override = overrides.get(ts.name());
       if (override != null) return override.compute(queryVal, caseVal);
       return DtwSimilarity.compute(
           (List<Map<String, Object>>) queryVal,
           (List<Map<String, Object>>) caseVal, ts);
   }

   @SuppressWarnings("unchecked")
   private static double editDistanceSimilarity(Object queryVal, Object caseVal,
                                                 Map<String, LocalSimilarityFunction> overrides) {
       // override handled by caller check — but DiscreteSequence has no name() ref here
       return EditDistanceSimilarity.compute(
           (List<String>) queryVal, (List<String>) caseVal);
   }
   ```

   Note: the override check for DiscreteSequence needs the field name. Adjust the `localSimilarity` method signature — it already receives `field.name()` via the `field` parameter. Use `overrides.get(field.name())` at the top of the method (already done for the existing override check).

- [ ] **Step 8: Run full memory-api tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api
```

Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#91): DTW and edit distance algorithms + scorer integration"
```

---

### Task 4: Contract tests and backend updates

**Files:**
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrQueryTranslator.java`

**Interfaces:**
- Consumes: `FeatureField.TimeSeries`, `FeatureField.DiscreteSequence`, `DtwSimilarity`, `EditDistanceSimilarity` from Tasks 1-3
- Produces: ~28 new contract tests passing across in-memory and Qdrant backends; `CbrQueryTranslator` rejecting temporal fields in filter translation

- [ ] **Step 1: Fix CbrQueryTranslator compilation**

Replace the TODO branch in `CbrQueryTranslator.toFilter()` with proper temporal field handling — temporal features should be skipped (not included in Qdrant payload filters; they're scored client-side):

```java
case FeatureField.TimeSeries ts -> {} // scored client-side, not filtered server-side
case FeatureField.DiscreteSequence ds -> {} // scored client-side, not filtered server-side
```

And in `applyStructuralFilters()` or wherever `validateFilters` is called, temporal fields are already rejected by `CbrFeatureValidator.validateFilters()`.

- [ ] **Step 2: Build all modules to verify compilation**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile
```

Expected: BUILD SUCCESS — all exhaustive switches now have cases for TimeSeries and DiscreteSequence.

- [ ] **Step 3: Write contract tests — schema and validation**

Add to `CbrCaseMemoryStoreContractTest.java`:

```java
// ---- Temporal schema helper ----

private void registerTemporalSchema() {
    store().registerSchema(CbrFeatureSchema.of("temporal-game",
        FeatureField.categorical("race"),
        FeatureField.numeric("mmr", 0, 8000),
        FeatureField.timeSeries("economyCurve", "minute",
            FeatureField.numeric("minute", 0, 30),
            FeatureField.numeric("economy", 0, 500),
            FeatureField.numeric("army", 0, 200),
            FeatureField.categorical("posture")),
        FeatureField.discreteSequence("phaseProgression")));
}

private String storeTemporalCase(String problem, Map<String, Object> features, String caseId) {
    return store().store(
        new FeatureVectorCbrCase(problem, "solution", null, null, features),
        "temporal-game", ENTITY, CBR, TENANT, caseId);
}

// ---- Schema creation ----
@Test
void temporal_timeSeries_schemaCreation() {
    registerTemporalSchema();
}

@Test
void temporal_discreteSequence_schemaCreation() {
    registerTemporalSchema();
}
```

- [ ] **Step 4: Write contract tests — store-time validation**

```java
@Test
void temporal_timeSeries_validation_storeAscendingTimestamps() {
    registerTemporalSchema();
    storeTemporalCase("test", Map.of(
        "race", "Terran",
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"),
            Map.of("minute", 3, "economy", 45, "army", 5, "posture", "MACRO"))),
        "valid");
}

@Test
void temporal_timeSeries_validation_storeNonAscending_rejected() {
    registerTemporalSchema();
    assertThatThrownBy(() -> storeTemporalCase("test", Map.of(
        "race", "Terran",
        "economyCurve", List.of(
            Map.of("minute", 3, "economy", 45, "army", 5, "posture", "MACRO"),
            Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"))),
        "invalid"))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void temporal_timeSeries_validation_missingTimestampField_rejected() {
    registerTemporalSchema();
    assertThatThrownBy(() -> storeTemporalCase("test", Map.of(
        "race", "Terran",
        "economyCurve", List.of(Map.of("economy", 30, "army", 0, "posture", "MACRO"))),
        "invalid"))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void temporal_timeSeries_validation_innerFieldTypes() {
    registerTemporalSchema();
    assertThatThrownBy(() -> storeTemporalCase("test", Map.of(
        "race", "Terran",
        "economyCurve", List.of(Map.of("minute", 1, "economy", "not-a-number", "army", 0, "posture", "MACRO"))),
        "invalid"))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void temporal_timeSeries_validation_emptyList_accepted() {
    registerTemporalSchema();
    storeTemporalCase("test", Map.of("race", "Terran", "economyCurve", List.of()), "empty");
}

@Test
void temporal_discreteSequence_validation_storeListOfStrings() {
    registerTemporalSchema();
    storeTemporalCase("test", Map.of(
        "race", "Terran",
        "phaseProgression", List.of("MACRO", "AGGRESSIVE", "ALL_IN")), "valid-seq");
}

@Test
void temporal_discreteSequence_validation_storeWrongType_rejected() {
    registerTemporalSchema();
    assertThatThrownBy(() -> storeTemporalCase("test", Map.of(
        "race", "Terran",
        "phaseProgression", "not-a-list"), "invalid"))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void temporal_filter_onTemporalField_rejected() {
    registerTemporalSchema();
    var query = CbrQuery.of(TENANT, CBR, "temporal-game", Map.of("race", "Terran"), 10)
        .withFilter("economyCurve", CbrFilter.contains("X"));
    assertThatThrownBy(() -> store().retrieveSimilar(query, FeatureVectorCbrCase.class))
        .isInstanceOf(IllegalArgumentException.class);
}
```

- [ ] **Step 5: Write contract tests — similarity and retrieval**

```java
@Test
void temporal_timeSeries_identicalSequences_scorePerfect() {
    registerTemporalSchema();
    var curve = List.of(
        Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"),
        Map.of("minute", 3, "economy", 45, "army", 5, "posture", "MACRO"));
    storeTemporalCase("game", Map.of("race", "Terran", "economyCurve", curve), "c1");

    var query = CbrQuery.of(TENANT, CBR, "temporal-game",
        Map.of("economyCurve", curve), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
    assertThat(results.get(0).score()).isCloseTo(1.0, within(0.001));
}

@Test
void temporal_timeSeries_differentSequences_scoredByDtw() {
    registerTemporalSchema();
    storeTemporalCase("close", Map.of("race", "Terran",
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 32, "army", 1, "posture", "MACRO"),
            Map.of("minute", 3, "economy", 47, "army", 6, "posture", "MACRO"))), "close");
    storeTemporalCase("far", Map.of("race", "Terran",
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 200, "army", 100, "posture", "AGGRESSIVE"),
            Map.of("minute", 3, "economy", 400, "army", 150, "posture", "ALL_IN"))), "far");

    var queryCurve = List.of(
        Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"),
        Map.of("minute", 3, "economy", 45, "army", 5, "posture", "MACRO"));
    var query = CbrQuery.of(TENANT, CBR, "temporal-game",
        Map.of("economyCurve", queryCurve), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSizeGreaterThanOrEqualTo(2);
    assertThat(results.get(0).cbrCase().problem()).isEqualTo("close");
}

@Test
void temporal_timeSeries_variableLength_handledByDtw() {
    registerTemporalSchema();
    storeTemporalCase("short", Map.of("race", "Terran",
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"))), "short");
    storeTemporalCase("long", Map.of("race", "Terran",
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"),
            Map.of("minute", 3, "economy", 45, "army", 5, "posture", "MACRO"),
            Map.of("minute", 5, "economy", 60, "army", 10, "posture", "AGGRESSIVE"))), "long");

    var query = CbrQuery.of(TENANT, CBR, "temporal-game",
        Map.of("economyCurve", List.of(
            Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"),
            Map.of("minute", 3, "economy", 45, "army", 5, "posture", "MACRO"))), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(2);
}

@Test
void temporal_timeSeries_singleObservation_degenerateDtw() {
    registerTemporalSchema();
    storeTemporalCase("single", Map.of("race", "Terran",
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 50, "army", 10, "posture", "MACRO"))), "single");

    var query = CbrQuery.of(TENANT, CBR, "temporal-game",
        Map.of("economyCurve", List.of(
            Map.of("minute", 1, "economy", 55, "army", 12, "posture", "MACRO"))), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
    assertThat(results.get(0).score()).isGreaterThan(0.9);
}

@Test
void temporal_timeSeries_dtwExcludesTimestampField() {
    registerTemporalSchema();
    storeTemporalCase("game", Map.of("race", "Terran",
        "economyCurve", List.of(
            Map.of("minute", 29, "economy", 50, "army", 10, "posture", "MACRO"))), "c1");

    // Different timestamp, same values — should match perfectly
    var query = CbrQuery.of(TENANT, CBR, "temporal-game",
        Map.of("economyCurve", List.of(
            Map.of("minute", 1, "economy", 50, "army", 10, "posture", "MACRO"))), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
    assertThat(results.get(0).score()).isEqualTo(1.0);
}

@Test
void temporal_discreteSequence_identicalSequences_scorePerfect() {
    registerTemporalSchema();
    storeTemporalCase("game", Map.of("race", "Terran",
        "phaseProgression", List.of("MACRO", "AGGRESSIVE", "ALL_IN")), "c1");

    var query = CbrQuery.of(TENANT, CBR, "temporal-game",
        Map.of("phaseProgression", List.of("MACRO", "AGGRESSIVE", "ALL_IN")), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
    assertThat(results.get(0).score()).isEqualTo(1.0);
}

@Test
void temporal_discreteSequence_oneSubstitution_scoreLessThanPerfect() {
    registerTemporalSchema();
    storeTemporalCase("game", Map.of("race", "Terran",
        "phaseProgression", List.of("MACRO", "AGGRESSIVE", "ALL_IN")), "c1");

    var query = CbrQuery.of(TENANT, CBR, "temporal-game",
        Map.of("phaseProgression", List.of("MACRO", "DEFENSIVE", "ALL_IN")), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
    assertThat(results.get(0).score()).isLessThan(1.0).isGreaterThan(0.0);
}

@Test
void temporal_discreteSequence_completelyDifferent_scoreNearZero() {
    registerTemporalSchema();
    storeTemporalCase("game", Map.of("race", "Terran",
        "phaseProgression", List.of("A", "B", "C")), "c1");

    var query = CbrQuery.of(TENANT, CBR, "temporal-game",
        Map.of("phaseProgression", List.of("X", "Y", "Z")), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
    assertThat(results.get(0).score()).isEqualTo(0.0);
}

@Test
void temporal_discreteSequence_emptyVsNonEmpty_scoreZero() {
    registerTemporalSchema();
    storeTemporalCase("game", Map.of("race", "Terran",
        "phaseProgression", List.of("A", "B")), "c1");

    var query = CbrQuery.of(TENANT, CBR, "temporal-game",
        Map.of("phaseProgression", List.of()), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    // empty query sequence → 0.0 similarity → filtered by minSimilarity=0.0 default
    assertThat(results).isEmpty();
}

@Test
void temporal_discreteSequence_bothEmpty_scorePerfect() {
    registerTemporalSchema();
    storeTemporalCase("game", Map.of("race", "Terran",
        "phaseProgression", List.of()), "c1");

    var query = CbrQuery.of(TENANT, CBR, "temporal-game",
        Map.of("phaseProgression", List.of()), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
    assertThat(results.get(0).score()).isEqualTo(1.0);
}
```

- [ ] **Step 6: Write contract tests — integration and round-trip**

```java
@Test
void temporal_mixedFlatAndTemporal_weightedScoring() {
    registerTemporalSchema();
    storeTemporalCase("sameRaceDiffCurve", Map.of(
        "race", "Terran", "mmr", 4500,
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 200, "army", 100, "posture", "AGGRESSIVE"))), "c1");
    storeTemporalCase("diffRaceSameCurve", Map.of(
        "race", "Zerg", "mmr", 4500,
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"))), "c2");

    var query = CbrQuery.of(TENANT, CBR, "temporal-game",
        Map.of("race", "Terran", "economyCurve", List.of(
            Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"))), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(2);
}

@Test
void temporal_weightOverride_temporalFieldDominates() {
    registerTemporalSchema();
    storeTemporalCase("sameRaceDiffCurve", Map.of(
        "race", "Terran",
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 200, "army", 100, "posture", "AGGRESSIVE"))), "c1");
    storeTemporalCase("diffRaceSameCurve", Map.of(
        "race", "Zerg",
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"))), "c2");

    var query = CbrQuery.of(TENANT, CBR, "temporal-game",
        Map.of("race", "Terran", "economyCurve", List.of(
            Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"))), 10)
        .withWeight("economyCurve", 10.0).withWeight("race", 0.1)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(2);
    // With heavy weight on economyCurve, diffRaceSameCurve should rank first
    assertThat(results.get(0).cbrCase().problem()).isEqualTo("diffRaceSameCurve");
}

@Test
void temporal_timeSeries_storeAndRetrieve_roundTrip() {
    registerTemporalSchema();
    var curve = List.of(
        Map.<String, Object>of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"),
        Map.<String, Object>of("minute", 3, "economy", 45, "army", 5, "posture", "MACRO"));
    storeTemporalCase("game", Map.of("race", "Terran", "economyCurve", curve), "rt1");

    var query = CbrQuery.of(TENANT, CBR, "temporal-game", Map.of("race", "Terran"), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
    @SuppressWarnings("unchecked")
    var retrieved = (List<Map<String, Object>>) results.get(0).cbrCase().features().get("economyCurve");
    assertThat(retrieved).hasSize(2);
}

@Test
void temporal_discreteSequence_storeAndRetrieve_roundTrip() {
    registerTemporalSchema();
    storeTemporalCase("game", Map.of("race", "Terran",
        "phaseProgression", List.of("MACRO", "AGGRESSIVE", "ALL_IN")), "rt2");

    var query = CbrQuery.of(TENANT, CBR, "temporal-game", Map.of("race", "Terran"), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
    @SuppressWarnings("unchecked")
    var retrieved = (List<String>) results.get(0).cbrCase().features().get("phaseProgression");
    assertThat(retrieved).containsExactly("MACRO", "AGGRESSIVE", "ALL_IN");
}

@Test
void temporal_coexistsWithStructuredFields() {
    store().registerSchema(CbrFeatureSchema.of("mixed",
        FeatureField.categorical("race"),
        FeatureField.categoricalList("tags"),
        FeatureField.timeSeries("trajectory", "t",
            FeatureField.numeric("t", 0, 10),
            FeatureField.numeric("v", 0, 100)),
        FeatureField.discreteSequence("phases")));

    store().store(
        new FeatureVectorCbrCase("problem", "solution", null, null, Map.of(
            "race", "Terran",
            "tags", List.of("aggro", "fast"),
            "trajectory", List.of(Map.of("t", 1, "v", 50)),
            "phases", List.of("A", "B"))),
        "mixed", ENTITY, CBR, TENANT, "mixed-1");

    var query = CbrQuery.of(TENANT, CBR, "mixed", Map.of("race", "Terran"), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
}

@Test
void temporal_flatFeatureFilter_reducesCandidatesBeforeDtw() {
    registerTemporalSchema();
    storeTemporalCase("terran-game", Map.of(
        "race", "Terran",
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"))), "t1");
    storeTemporalCase("zerg-game", Map.of(
        "race", "Zerg",
        "economyCurve", List.of(
            Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"))), "z1");

    var query = CbrQuery.of(TENANT, CBR, "temporal-game",
        Map.of("race", "Terran", "economyCurve", List.of(
            Map.of("minute", 1, "economy", 30, "army", 0, "posture", "MACRO"))), 10)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    // Both returned (Zerg has different race but race weight is only 1.0, curve is perfect)
    assertThat(results).hasSize(2);
    // Terran match should rank first (perfect on both race AND curve)
    assertThat(results.get(0).cbrCase().problem()).isEqualTo("terran-game");
}
```

- [ ] **Step 7: Run contract tests via in-memory backend**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem
```

Expected: ALL PASS

- [ ] **Step 8: Run full build**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests=false
```

Expected: ALL PASS (all modules, including Qdrant integration tests if Docker is available)

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-testing/ memory-qdrant/ memory-cbr-inmem/ memory-cbr-embedding/ memory-cbr-crossencoder/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#91): temporal contract tests + backend integration"
```

---

### Task 5: CLAUDE.md update

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: completed Tasks 1-4
- Produces: Updated module documentation reflecting temporal field types

- [ ] **Step 1: Update CLAUDE.md module descriptions**

Update the `memory-api` module description to include `TimeSeries` and `DiscreteSequence` in the `FeatureField` hierarchy. Update the `CbrSimilarityScorer` description to mention DTW and edit distance. Update the `CbrFeatureSchema` description to mention temporal field support.

- [ ] **Step 2: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add CLAUDE.md
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "docs(#91): update CLAUDE.md — temporal case fields"
```

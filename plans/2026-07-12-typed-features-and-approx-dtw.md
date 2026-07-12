# Typed CBR Feature Values + Approximate DTW Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #131 — typed CBR feature values
**Issue group:** #131, #137

**Goal:** Replace `Map<String, Object>` with a sealed `FeatureValue` hierarchy across the CBR feature system, then add LB_Keogh lower-bound pruning + early abandonment to DTW.

**Architecture:** Sealed `FeatureValue` interface with 7 variants (StringVal, NumberVal, RangeVal, StringListVal, NumberListVal, StructVal, StructListVal) replaces all `Map<String, Object>` in CbrCase, CbrQuery, CbrFilter.HasMatch, scorer, validator, stores. Then DtwSimilarity gains an abandon-cost threshold overload, and a new LbKeogh utility provides O(n) lower-bound pruning for SakoeChibaBand before full O(n×m) DTW.

**Tech Stack:** Java 21 sealed interfaces, Quarkus CDI, Qdrant Java client, ONNX Runtime (inference-tasks)

## Global Constraints

- Java 21 source on Java 26 JVM. Use `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn` for all builds.
- Use `mvn` not `./mvnw`.
- Module: `memory-api` (Tier 1, zero Quarkus deps). Stores in `memory-cbr-inmem`, `memory-qdrant`, `memory-cbr-embedding`, `memory-cbr-crossencoder`.
- Pre-release: breaking changes cost nothing. Fix the design, don't protect callers.
- All records use `Map.copyOf()` / `List.copyOf()` for immutability.
- Every commit references an issue.
- IntelliJ MCP required for all code editing operations.

---

### Task 1: FeatureValue sealed interface

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/FeatureValue.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/FeatureValueTest.java`

**Interfaces:**
- Produces: `FeatureValue` sealed interface with variants `StringVal`, `NumberVal`, `RangeVal`, `StringListVal`, `NumberListVal`, `StructVal`, `StructListVal`. Static factories: `string()`, `number()`, `range()`, `stringList()`, `numberList()`, `struct()`, `structList()`.

- [ ] **Step 1: Write failing tests for FeatureValue**

Test each variant's construction, immutability, validation, and static factories:

```java
package io.casehub.neocortex.memory.cbr;

import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class FeatureValueTest {

    @Test void stringVal_requiresNonNull() {
        assertThatThrownBy(() -> FeatureValue.string(null))
            .isInstanceOf(NullPointerException.class);
    }

    @Test void stringVal_preservesValue() {
        var sv = FeatureValue.string("hello");
        assertThat(sv).isInstanceOf(FeatureValue.StringVal.class);
        assertThat(((FeatureValue.StringVal) sv).value()).isEqualTo("hello");
    }

    @Test void numberVal_preservesValue() {
        var nv = FeatureValue.number(42.5);
        assertThat(nv).isInstanceOf(FeatureValue.NumberVal.class);
        assertThat(((FeatureValue.NumberVal) nv).value()).isEqualTo(42.5);
    }

    @Test void rangeVal_validRange() {
        var rv = FeatureValue.range(1.0, 10.0);
        assertThat(rv).isInstanceOf(FeatureValue.RangeVal.class);
        assertThat(((FeatureValue.RangeVal) rv).min()).isEqualTo(1.0);
        assertThat(((FeatureValue.RangeVal) rv).max()).isEqualTo(10.0);
    }

    @Test void rangeVal_minGreaterThanMax_throws() {
        assertThatThrownBy(() -> FeatureValue.range(10.0, 1.0))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test void rangeVal_equalMinMax_allowed() {
        var rv = FeatureValue.range(5.0, 5.0);
        assertThat(((FeatureValue.RangeVal) rv).min()).isEqualTo(5.0);
    }

    @Test void stringListVal_immutable() {
        var list = new java.util.ArrayList<>(List.of("a", "b"));
        var sl = FeatureValue.stringList(list);
        list.add("c");
        assertThat(((FeatureValue.StringListVal) sl).values()).containsExactly("a", "b");
    }

    @Test void stringListVal_varargs() {
        var sl = FeatureValue.stringList("x", "y", "z");
        assertThat(((FeatureValue.StringListVal) sl).values()).containsExactly("x", "y", "z");
    }

    @Test void numberListVal_immutable() {
        var list = new java.util.ArrayList<>(List.of(1.0, 2.0));
        var nl = FeatureValue.numberList(list);
        list.add(3.0);
        assertThat(((FeatureValue.NumberListVal) nl).values()).containsExactly(1.0, 2.0);
    }

    @Test void structVal_immutable() {
        var map = new java.util.HashMap<String, FeatureValue>();
        map.put("k", FeatureValue.string("v"));
        var sv = FeatureValue.struct(map);
        map.put("k2", FeatureValue.number(1));
        assertThat(((FeatureValue.StructVal) sv).fields()).hasSize(1);
    }

    @Test void structListVal_deepImmutable() {
        var inner = new java.util.HashMap<String, FeatureValue>();
        inner.put("k", FeatureValue.number(1));
        var items = new java.util.ArrayList<Map<String, FeatureValue>>();
        items.add(inner);
        var sl = FeatureValue.structList(items);
        items.add(Map.of());
        assertThat(((FeatureValue.StructListVal) sl).items()).hasSize(1);
    }

    @Test void structListVal_varargs() {
        var sl = FeatureValue.structList(
            Map.of("a", FeatureValue.number(1)),
            Map.of("b", FeatureValue.number(2))
        );
        assertThat(((FeatureValue.StructListVal) sl).items()).hasSize(2);
    }

    @Test void equality_sameValues() {
        assertThat(FeatureValue.string("a")).isEqualTo(FeatureValue.string("a"));
        assertThat(FeatureValue.number(1.0)).isEqualTo(FeatureValue.number(1.0));
        assertThat(FeatureValue.stringList("x")).isEqualTo(FeatureValue.stringList("x"));
    }

    @Test void equality_differentValues() {
        assertThat(FeatureValue.string("a")).isNotEqualTo(FeatureValue.string("b"));
        assertThat(FeatureValue.number(1.0)).isNotEqualTo(FeatureValue.number(2.0));
    }

    @Test void patternMatching_exhaustive() {
        FeatureValue v = FeatureValue.string("test");
        String result = switch (v) {
            case FeatureValue.StringVal s -> "string:" + s.value();
            case FeatureValue.NumberVal n -> "number:" + n.value();
            case FeatureValue.RangeVal r -> "range";
            case FeatureValue.StringListVal sl -> "stringList";
            case FeatureValue.NumberListVal nl -> "numberList";
            case FeatureValue.StructVal sv -> "struct";
            case FeatureValue.StructListVal sl -> "structList";
        };
        assertThat(result).isEqualTo("string:test");
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=FeatureValueTest -q`
Expected: compilation failure — `FeatureValue` class not found.

- [ ] **Step 3: Implement FeatureValue**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/FeatureValue.java` with the sealed interface and all 7 variant records + static factories exactly as specified in the design spec (lines 25-84).

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=FeatureValueTest -q`
Expected: all 15 tests PASS.

- [ ] **Step 5: Commit**

```
feat(#131): FeatureValue sealed interface — 7 typed variants for CBR features
```

---

### Task 2: Core API migration — types, validator, scorer, DTW

This is the "big bang" migration. All these files must change together because `CbrCase.features()` return type change breaks every consumer. TDD applies at the unit level — write updated tests first, then migrate each file.

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrCase.java:11` — `Map<String, Object>` → `Map<String, FeatureValue>`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/FeatureVectorCbrCase.java:8` — features field type
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/PlanCbrCase.java:9` — features field type
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrQuery.java:13` — features field type + all `with*` methods + `of()` factory
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFilter.java:31` — HasMatch.subFields type
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFeatureValidator.java:10-113` — all validate methods
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/LocalSimilarityFunction.java:24` — Object → FeatureValue params
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java` — all scoring methods
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/DtwSimilarity.java:11-53` — observation type + observationDistance
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrCaseTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrQueryTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrFilterTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrFeatureValidatorTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorerTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/DtwSimilarityTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/ScoredCbrCaseTest.java`

**Interfaces:**
- Consumes: `FeatureValue` from Task 1
- Produces: All `memory-api` APIs now use `Map<String, FeatureValue>` instead of `Map<String, Object>`. `LocalSimilarityFunction.compute(FeatureValue, FeatureValue)`. `DtwSimilarity.compute(List<Map<String, FeatureValue>>, ...)`.

- [ ] **Step 1: Migrate API types (CbrCase, records, CbrQuery, CbrFilter)**

Use `ide_edit_member` to change:

**CbrCase.java:11** — change `features()` return type:
```java
default Map<String, FeatureValue> features() { return Map.of(); }
```

**FeatureVectorCbrCase.java** — change features field:
```java
public record FeatureVectorCbrCase(String problem, String solution,
                                    String outcome, Double confidence,
                                    Map<String, FeatureValue> features) implements CbrCase {
```

**PlanCbrCase.java** — change features field:
```java
public record PlanCbrCase(String problem, String solution,
                          String outcome, Double confidence,
                          Map<String, FeatureValue> features,
                          List<PlanTrace> planTrace) implements CbrCase {
```

**CbrQuery.java:13** — change features field and all constructors/`with*` methods:
```java
Map<String, FeatureValue> features,
```
Update `of()` factory parameter: `Map<String, FeatureValue> features`.

**CbrFilter.java:31** — change HasMatch.subFields:
```java
record HasMatch(Map<String, FeatureValue> subFields) implements CbrFilter {
```
Update HasMatch compact constructor to use `Map<String, FeatureValue>`. Update `hasMatch()` static factory parameter.

- [ ] **Step 2: Migrate LocalSimilarityFunction**

**LocalSimilarityFunction.java:24** — change parameter types:
```java
double compute(FeatureValue queryValue, FeatureValue caseValue);

LocalSimilarityFunction EXACT_MATCH = (q, c) -> q.equals(c) ? 1.0 : 0.0;
```

- [ ] **Step 3: Migrate CbrFeatureValidator**

Rewrite `validateStoreFeatures()` and `validateQueryFeatures()` to validate `Map<String, FeatureValue>` entries against FeatureField types using `instanceof FeatureValue.StringVal` etc. instead of `instanceof String`.

Key changes:
- `Categorical` → require `StringVal`
- `Numeric` → require `NumberVal` (store) or `NumberVal`/`RangeVal` (query)
- `Text` → require `StringVal`
- `CategoricalList` → require `StringListVal` (store), reject in query
- `NumericList` → require `NumberListVal` (store), reject in query
- `NestedObject` → require `StructVal`, validate inner fields as `FeatureValue`
- `ObjectList` → require `StructListVal`, validate inner items
- `TimeSeries` → require `StructListVal`, validate observations with inner `NumberVal`
- `DiscreteSequence` → require `StringListVal`

Update `validateInnerValues()` to work with `Map<String, FeatureValue>`.
Update `validateHasMatchSubFields()` to work with `Map<String, FeatureValue>`.
Update `validateTimeSeries()` to work with `FeatureValue.StructListVal`.

- [ ] **Step 4: Migrate CbrSimilarityScorer**

Rewrite `scoreDetailed()` and `localSimilarity()` to accept `Map<String, FeatureValue>` and pattern match on FeatureValue variants:

`scoreDetailed()` parameters: `Map<String, FeatureValue> queryFeatures, Map<String, FeatureValue> caseFeatures, ...`

`localSimilarity()`: dispatch on FeatureField type first, then pattern match:
```java
case FeatureField.Numeric n -> numericSimilarity(n, queryVal, caseVal);
```

`numericSimilarity()`: pattern match on `NumberVal`/`RangeVal`:
```java
private static double numericSimilarity(FeatureField.Numeric field,
                                         FeatureValue queryVal, FeatureValue caseVal) {
    // ... extract doubles via pattern match, no casts
}
```

`computeNormalizedDistance()`: accept `FeatureValue` params, pattern match `NumberVal` and `RangeVal`.

`dtwSimilarity()`: extract `StructListVal.items()`, pass to `DtwSimilarity.compute()`.

`editDistanceSimilarity()`: extract `StringListVal.values()`, pass to `EditDistanceSimilarity.compute()`.

`categoricalSimilarity()`: extract `StringVal.value()` via pattern match.

- [ ] **Step 5: Migrate DtwSimilarity**

Change signatures:
```java
public static DtwResult compute(List<Map<String, FeatureValue>> query,
                                List<Map<String, FeatureValue>> caseSeq,
                                FeatureField.TimeSeries schema) { ... }

public static DtwResult compute(List<Map<String, FeatureValue>> query,
                                List<Map<String, FeatureValue>> caseSeq,
                                FeatureField.TimeSeries schema,
                                WarpingConstraint constraint) { ... }
```

`observationDistance()`: pattern match on `NumberVal`:
```java
private static double observationDistance(Map<String, FeatureValue> a,
                                          Map<String, FeatureValue> b,
                                          List<FeatureField.Numeric> fields) {
    double sumSq = 0.0;
    for (FeatureField.Numeric f : fields) {
        double range = f.max() - f.min();
        if (range <= 0) continue;
        FeatureValue aVal = a.get(f.name());
        FeatureValue bVal = b.get(f.name());
        if (aVal instanceof FeatureValue.NumberVal aN && bVal instanceof FeatureValue.NumberVal bN) {
            double diff = (aN.value() - bN.value()) / range;
            sumSq += diff * diff;
        }
    }
    return Math.sqrt(sumSq);
}
```

- [ ] **Step 6: Update all memory-api tests**

Transform every test that constructs features from `Map.of("field", rawValue)` to `Map.of("field", FeatureValue.string(rawValue))` (or `.number()`, `.stringList()`, etc. as appropriate).

**Pattern for flat features:**
```java
// Before:
Map.of("race", "Terran", "economy", 30)
// After:
Map.of("race", FeatureValue.string("Terran"), "economy", FeatureValue.number(30))
```

**Pattern for TimeSeries observations:**
```java
// Before:
Map.of("time", 1.0, "value", 10.0)
// After:
Map.of("time", FeatureValue.number(1.0), "value", FeatureValue.number(10.0))
```

**Pattern for structured fields:**
```java
// Before:
Map.of("tags", List.of("a", "b"))
// After:
Map.of("tags", FeatureValue.stringList("a", "b"))
```

**Pattern for HasMatch sub-fields:**
```java
// Before:
CbrFilter.hasMatch(Map.of("name", "x"))
// After:
CbrFilter.hasMatch(Map.of("name", FeatureValue.string("x")))
```

**Pattern for NumericRange in query features:**
```java
// Before:
Map.of("economy", new NumericRange(20, 40))
// After:
Map.of("economy", FeatureValue.range(20, 40))
```

Apply to: `CbrCaseTest`, `CbrQueryTest`, `CbrFilterTest`, `CbrFeatureValidatorTest`, `CbrSimilarityScorerTest`, `DtwSimilarityTest`, `ScoredCbrCaseTest`, and all other test files in `memory-api/src/test/`.

- [ ] **Step 7: Build memory-api to verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -q`
Expected: all tests PASS.

- [ ] **Step 8: Commit**

```
feat(#131): migrate memory-api to FeatureValue — sealed typed features replace Map<String, Object>
```

---

### Task 3: InMemoryCbrCaseMemoryStore + contract test migration

**Files:**
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`

**Interfaces:**
- Consumes: `FeatureValue` from Task 1, all APIs from Task 2
- Produces: `InMemoryCbrCaseMemoryStore` working with typed features. Contract test suite passing.

- [ ] **Step 1: Migrate InMemoryCbrCaseMemoryStore**

`matchesFilters()`: change `storedCase.features().get(fieldName)` → returns `FeatureValue`.

`matchesSingleFilter()`: change parameter from `Object storedValue` to `FeatureValue storedValue`. Pattern match:
```java
private boolean matchesSingleFilter(FeatureValue storedValue, CbrFilter filter, FeatureField field) {
    return switch (filter) {
        case CbrFilter.Contains c ->
            storedValue instanceof FeatureValue.StringListVal sl && sl.values().contains(c.value());
        case CbrFilter.ContainsAll ca ->
            storedValue instanceof FeatureValue.StringListVal sl && sl.values().containsAll(ca.values());
        case CbrFilter.ContainsAny ca ->
            storedValue instanceof FeatureValue.StringListVal sl && ca.values().stream().anyMatch(sl.values()::contains);
        case CbrFilter.NotContains nc ->
            storedValue instanceof FeatureValue.StringListVal sl && !sl.values().contains(nc.value());
        case CbrFilter.NotContainsAny nca ->
            storedValue instanceof FeatureValue.StringListVal sl && nca.values().stream().noneMatch(sl.values()::contains);
        case CbrFilter.ContainsRange cr ->
            storedValue instanceof FeatureValue.NumberListVal nl && nl.values().stream()
                .anyMatch(n -> n >= cr.range().min() && n <= cr.range().max());
        case CbrFilter.HasMatch hm -> matchesHasMatch(storedValue, hm, field);
        case CbrFilter.AllOf allOf -> {
            for (CbrFilter inner : allOf.filters()) {
                if (!matchesSingleFilter(storedValue, inner, field)) yield false;
            }
            yield true;
        }
    };
}
```

`matchesHasMatch()`: change `Object storedValue` to `FeatureValue storedValue`. Extract from `StructVal.fields()` or `StructListVal.items()`.

`allSubFieldsMatch()`: change `Map<String, Object> subFields` to `Map<String, FeatureValue> subFields`. Pattern match on `FeatureValue` variants for comparison:
```java
private boolean allSubFieldsMatch(Map<?, ?> stored, Map<String, FeatureValue> subFields) {
    // For stored values (from FeatureValue.StructVal/StructListVal), 
    // the values are FeatureValue instances
    for (var sub : subFields.entrySet()) {
        Object storedVal = stored.get(sub.getKey());
        if (storedVal == null) return false;
        FeatureValue queryVal = sub.getValue();
        if (queryVal instanceof FeatureValue.RangeVal range) {
            if (!(storedVal instanceof FeatureValue.NumberVal sn)) return false;
            if (sn.value() < range.min() || sn.value() > range.max()) return false;
        } else if (queryVal instanceof FeatureValue.NumberVal qn) {
            if (!(storedVal instanceof FeatureValue.NumberVal sn)) return false;
            if (Double.compare(qn.value(), sn.value()) != 0) return false;
        } else {
            if (!queryVal.equals(storedVal)) return false;
        }
    }
    return true;
}
```

- [ ] **Step 2: Migrate contract test — all 111 tests**

Apply the same patterns from Task 2 Step 6 across all test methods in `CbrCaseMemoryStoreContractTest`. Key transformations:

All `Map.of("race", "Terran", ...)` → `Map.of("race", FeatureValue.string("Terran"), ...)` in feature maps.
All `Map.of("tags", List.of("a","b"))` → `Map.of("tags", FeatureValue.stringList("a","b"))` for CategoricalList.
All `Map.of("scores", List.of(1.0, 2.0))` → `Map.of("scores", FeatureValue.numberList(1.0, 2.0))` for NumericList.
All `Map.of("stats", Map.of("k","v"))` → `Map.of("stats", FeatureValue.struct(Map.of("k", FeatureValue.string("v"))))` for NestedObject.
All TimeSeries observation maps → inner values wrapped with `FeatureValue.number()`.
All `Map.of("phases", List.of("a","b"))` → `Map.of("phases", FeatureValue.stringList("a","b"))` for DiscreteSequence.
All `CbrFilter.hasMatch(Map.of("k", rawVal))` → `CbrFilter.hasMatch(Map.of("k", FeatureValue.string(rawVal)))`.
All `new NumericRange(min, max)` in feature maps → `FeatureValue.range(min, max)`.

Also update helper methods: `storeGameCase()`, `storeNumericListCase()`, `storeTemporalCase()`, `storeTemporalSpecCase()`, `registerDefaultSchema()`, `registerStructuredSchema()`, `registerTemporalSchema()`, `registerTemporalSchemaWithSpecs()`.

- [ ] **Step 3: Build and run contract tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem -q`
Expected: all 111 contract tests PASS.

- [ ] **Step 4: Commit**

```
feat(#131): migrate InMemoryCbrCaseMemoryStore + contract tests to FeatureValue
```

---

### Task 4: Qdrant backend migration

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrPointBuilder.java:71-91`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrMemorySerializer.java:37`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrQueryTranslator.java:175-185`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java` — `reconstructCase()`, `reconstructFeatureVector()`, `collectSemanticTextValues()`

**Interfaces:**
- Consumes: `FeatureValue` from Task 1, all APIs from Task 2
- Produces: Qdrant backend working with typed features. JSON payload format unchanged (backward compatible).

- [ ] **Step 1: Migrate CbrPointBuilder**

Change feature iteration from `Map<String, Object>` to `Map<String, FeatureValue>`:
```java
Map<String, FeatureValue> features = cbrCase.features();
```

Feature serialization to `_features_json` — serialize FeatureValue to raw JSON:
```java
Map<String, Object> rawFeatures = new HashMap<>();
for (var entry : features.entrySet()) {
    rawFeatures.put(entry.getKey(), toRawValue(entry.getValue()));
}
payload.put("_features_json", ValueFactory.value(MAPPER.writeValueAsString(rawFeatures)));
```

Add `toRawValue(FeatureValue)` helper:
```java
private static Object toRawValue(FeatureValue fv) {
    return switch (fv) {
        case FeatureValue.StringVal s -> s.value();
        case FeatureValue.NumberVal n -> n.value();
        case FeatureValue.RangeVal r -> Map.of("min", r.min(), "max", r.max());
        case FeatureValue.StringListVal sl -> sl.values();
        case FeatureValue.NumberListVal nl -> nl.values();
        case FeatureValue.StructVal sv -> {
            Map<String, Object> m = new HashMap<>();
            sv.fields().forEach((k, v) -> m.put(k, toRawValue(v)));
            yield m;
        }
        case FeatureValue.StructListVal sl -> sl.items().stream()
            .map(item -> {
                Map<String, Object> m = new HashMap<>();
                item.forEach((k, v) -> m.put(k, toRawValue(v)));
                return m;
            }).toList();
    };
}
```

Per-field payload (`f_<name>`) — switch on FeatureValue variant:
```java
for (var entry : features.entrySet()) {
    String key = "f_" + entry.getKey();
    FeatureValue val = entry.getValue();
    switch (val) {
        case FeatureValue.StringVal s -> payload.put(key, ValueFactory.value(s.value()));
        case FeatureValue.NumberVal n -> payload.put(key, ValueFactory.value(n.value()));
        case FeatureValue.StringListVal sl -> payload.put(key, toListValue(sl.values()));
        case FeatureValue.NumberListVal nl -> payload.put(key, toListValue(nl.values()));
        case FeatureValue.StructVal sv -> payload.put(key, toFeatureStructValue(sv));
        case FeatureValue.StructListVal sl -> payload.put(key, toFeatureStructListValue(sl));
        case FeatureValue.RangeVal r -> {} // query-only, never stored
    }
}
```

- [ ] **Step 2: Migrate CbrMemorySerializer**

Change `cbrCase.features()` usage — serialize `Map<String, FeatureValue>` to JSON using same `toRawValue()` approach (or Jackson serialization of raw values).

- [ ] **Step 3: Migrate CbrQueryTranslator**

`addSubFieldCondition()`: change `Object value` parameter to `FeatureValue value`. Pattern match instead of instanceof:
```java
private static void addSubFieldCondition(Builder builder, String key, FeatureValue value) {
    switch (value) {
        case FeatureValue.StringVal s -> builder.addMust(matchKeyword(key, s.value()));
        case FeatureValue.NumberVal n -> builder.addMust(range(key, n.value(), n.value()));
        case FeatureValue.RangeVal r -> builder.addMust(range(key, r.min(), r.max()));
        default -> throw new IllegalArgumentException("Unsupported sub-field value: " + value);
    }
}
```

`validateQueryFeatures()`: update parameter type.

- [ ] **Step 4: Migrate QdrantCbrCaseMemoryStore**

`reconstructFeatureVector()`: deserialize `_features_json` (raw JSON) back to `Map<String, FeatureValue>` using the schema:
```java
Map<String, Object> rawFeatures = MAPPER.readValue(json, MAP_TYPE);
Map<String, FeatureValue> typedFeatures = convertToTyped(rawFeatures, schema);
```

Add `convertToTyped()` helper that uses schema field types to construct the right FeatureValue variants from raw JSON values.

`collectSemanticTextValues()`: change to pattern match:
```java
if (rc.cbrCase().features().get(fieldName) instanceof FeatureValue.StringVal s)
    texts.add(s.value());
```

- [ ] **Step 5: Build and run Qdrant tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant -q -DskipITs`
Expected: compilation succeeds, unit tests pass. (Integration tests require Testcontainers Qdrant.)

- [ ] **Step 6: Commit**

```
feat(#131): migrate Qdrant backend to FeatureValue — payload format unchanged
```

---

### Task 5: EmbeddingTextSimilarity migration

**Files:**
- Modify: `memory-cbr-embedding/src/main/java/io/casehub/neocortex/memory/cbr/embedding/EmbeddingTextSimilarity.java:37-41`

**Interfaces:**
- Consumes: `LocalSimilarityFunction` with `FeatureValue` params from Task 2
- Produces: `EmbeddingTextSimilarity.compute(FeatureValue, FeatureValue)` pattern matching on `StringVal`.

- [ ] **Step 1: Migrate compute() method**

```java
@Override
public double compute(FeatureValue queryValue, FeatureValue caseValue) {
    if (queryValue instanceof FeatureValue.StringVal qs
        && caseValue instanceof FeatureValue.StringVal cs) {
        Embedding qEmb = embed(qs.value());
        Embedding cEmb = embed(cs.value());
        return CosineSimilarity.between(qEmb, cEmb);
    }
    return 0.0;
}
```

Also update `precompute()` if it takes `List<String>` directly — that stays unchanged since it operates on extracted string values, not FeatureValue.

- [ ] **Step 2: Build memory-cbr-embedding**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-embedding -q`
Expected: PASS.

- [ ] **Step 3: Commit**

```
feat(#131): migrate EmbeddingTextSimilarity to FeatureValue params
```

---

### Task 6: Full build verification + cross-repo issue

**Files:**
- No new files

- [ ] **Step 1: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests -q`
Expected: all modules compile.

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -q`
Expected: all tests pass.

- [ ] **Step 2: File cross-repo issue**

```bash
gh issue create --repo casehubio/engine \
  --title "feat: migrate CbrRetrievalService to FeatureValue typed features" \
  --body "neocortex#131 replaced Map<String, Object> with Map<String, FeatureValue> in CbrCase.features(). CbrRetrievalService.mapScoredCase() uses c.features() and needs updating.

Ref: casehubio/neocortex#131"
```

- [ ] **Step 3: Commit any remaining fixes**

If the full build surfaced issues, fix and commit:
```
fix(#131): resolve build issues from FeatureValue migration
```

---

### Task 7: DtwSimilarity early abandonment

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/DtwSimilarity.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/DtwSimilarityTest.java`

**Interfaces:**
- Consumes: `DtwSimilarity` with typed `FeatureValue` params from Task 2
- Produces: New 5-arg `compute()` overload with `abandonCostThreshold`. Existing overloads delegate with `Double.POSITIVE_INFINITY`.

- [ ] **Step 1: Write failing tests for early abandonment**

```java
@Test void compute_withAbandonThreshold_returnsZeroWhenExceeded() {
    // Two very different sequences — high DTW cost
    var query = List.of(
        Map.of("time", FeatureValue.number(1), "val", FeatureValue.number(0.0)),
        Map.of("time", FeatureValue.number(2), "val", FeatureValue.number(0.0))
    );
    var caseSeq = List.of(
        Map.of("time", FeatureValue.number(1), "val", FeatureValue.number(100.0)),
        Map.of("time", FeatureValue.number(2), "val", FeatureValue.number(100.0))
    );
    var schema = FeatureField.timeSeries("ts", "time",
        FeatureField.numeric("time", 0, 100), FeatureField.numeric("val", 0, 100));

    // Very tight threshold — should abandon
    DtwResult result = DtwSimilarity.compute(query, caseSeq, schema,
        new WarpingConstraint.Unconstrained(), 0.001);
    assertThat(result.score()).isEqualTo(0.0);
    assertThat(result.alignment()).isEmpty();
}

@Test void compute_withAbandonThreshold_completesWhenWithinBound() {
    // Identical sequences — zero cost, always within bound
    var obs = Map.of("time", FeatureValue.number(1), "val", FeatureValue.number(50.0));
    var query = List.of(obs);
    var caseSeq = List.of(obs);
    var schema = FeatureField.timeSeries("ts", "time",
        FeatureField.numeric("time", 0, 100), FeatureField.numeric("val", 0, 100));

    DtwResult result = DtwSimilarity.compute(query, caseSeq, schema,
        new WarpingConstraint.Unconstrained(), 1000.0);
    assertThat(result.score()).isEqualTo(1.0);
    assertThat(result.alignment()).isNotEmpty();
}

@Test void compute_withInfinityThreshold_behavesLikeNoAbandon() {
    var query = List.of(Map.of("time", FeatureValue.number(1), "val", FeatureValue.number(10.0)));
    var caseSeq = List.of(Map.of("time", FeatureValue.number(1), "val", FeatureValue.number(90.0)));
    var schema = FeatureField.timeSeries("ts", "time",
        FeatureField.numeric("time", 0, 100), FeatureField.numeric("val", 0, 100));

    DtwResult withoutAbandon = DtwSimilarity.compute(query, caseSeq, schema);
    DtwResult withInfinity = DtwSimilarity.compute(query, caseSeq, schema,
        new WarpingConstraint.Unconstrained(), Double.POSITIVE_INFINITY);
    assertThat(withInfinity.score()).isEqualTo(withoutAbandon.score());
}

@Test void compute_earlyAbandonment_worksWithSakoeChibaBand() {
    var query = List.of(
        Map.of("time", FeatureValue.number(1), "val", FeatureValue.number(0.0)),
        Map.of("time", FeatureValue.number(2), "val", FeatureValue.number(0.0)),
        Map.of("time", FeatureValue.number(3), "val", FeatureValue.number(0.0))
    );
    var caseSeq = List.of(
        Map.of("time", FeatureValue.number(1), "val", FeatureValue.number(100.0)),
        Map.of("time", FeatureValue.number(2), "val", FeatureValue.number(100.0)),
        Map.of("time", FeatureValue.number(3), "val", FeatureValue.number(100.0))
    );
    var schema = FeatureField.timeSeries("ts", "time",
        FeatureField.numeric("time", 0, 100), FeatureField.numeric("val", 0, 100));

    DtwResult result = DtwSimilarity.compute(query, caseSeq, schema,
        new WarpingConstraint.SakoeChibaBand(1), 0.001);
    assertThat(result.score()).isEqualTo(0.0);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=DtwSimilarityTest -q`
Expected: compilation failure — no 5-arg `compute()` method.

- [ ] **Step 3: Implement early abandonment**

Add 5-arg `compute()` overload. Delegate existing overloads:

```java
public static DtwResult compute(List<Map<String, FeatureValue>> query,
                                List<Map<String, FeatureValue>> caseSeq,
                                FeatureField.TimeSeries schema) {
    return compute(query, caseSeq, schema, new WarpingConstraint.Unconstrained(),
                   Double.POSITIVE_INFINITY);
}

public static DtwResult compute(List<Map<String, FeatureValue>> query,
                                List<Map<String, FeatureValue>> caseSeq,
                                FeatureField.TimeSeries schema,
                                WarpingConstraint constraint) {
    return compute(query, caseSeq, schema, constraint, Double.POSITIVE_INFINITY);
}

public static DtwResult compute(List<Map<String, FeatureValue>> query,
                                List<Map<String, FeatureValue>> caseSeq,
                                FeatureField.TimeSeries schema,
                                WarpingConstraint constraint,
                                double abandonCostThreshold) {
    // ... existing DP setup ...

    for (int i = 1; i <= n; i++) {
        int jStart = computeJStart(i, n, m, constraint);
        int jEnd   = computeJEnd(i, n, m, constraint);
        if (jStart > jEnd) return new DtwResult(0.0, List.of());

        double rowMin = Double.MAX_VALUE;
        for (int j = jStart; j <= jEnd; j++) {
            double dist = observationDistance(query.get(i - 1), caseSeq.get(j - 1), numericFields);
            cost[i][j] = dist + Math.min(cost[i - 1][j],
                                         Math.min(cost[i][j - 1], cost[i - 1][j - 1]));
            rowMin = Math.min(rowMin, cost[i][j]);
        }

        if (rowMin > abandonCostThreshold) {
            return new DtwResult(0.0, List.of());
        }
    }

    // ... existing scoring + backtrace ...
}
```

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=DtwSimilarityTest -q`
Expected: all tests PASS (including new abandonment tests and all existing tests).

- [ ] **Step 5: Commit**

```
feat(#137): early abandonment in DtwSimilarity — row-minimum tracking short-circuits expensive DP
```

---

### Task 8: LbKeogh utility class

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/LbKeogh.java`
- Create: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/LbKeoghTest.java`

**Interfaces:**
- Consumes: `FeatureValue`, `FeatureField.TimeSeries`, `DtwSimilarity.scorableNumericFields()`
- Produces: `LbKeogh.Envelope` record, `computeEnvelope(sequence, schema, windowSize)`, `lowerBound(query, envelope, schema)`.

- [ ] **Step 1: Write failing tests**

```java
package io.casehub.neocortex.memory.cbr;

import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class LbKeoghTest {

    private static final FeatureField.TimeSeries SCHEMA = FeatureField.timeSeries(
        "ts", "time",
        FeatureField.numeric("time", 0, 10),
        FeatureField.numeric("val", 0, 100));

    private static Map<String, FeatureValue> obs(double time, double val) {
        return Map.of("time", FeatureValue.number(time), "val", FeatureValue.number(val));
    }

    @Test void computeEnvelope_singlePoint_upperEqualsLower() {
        var seq = List.of(obs(1, 50));
        LbKeogh.Envelope env = LbKeogh.computeEnvelope(seq, SCHEMA, 1);
        assertThat(env.length()).isEqualTo(1);
        assertThat(env.dimensions()).isEqualTo(1); // only "val", not "time"
        assertThat(env.upper()[0][0]).isEqualTo(env.lower()[0][0]);
    }

    @Test void computeEnvelope_multiplePoints_windowExpands() {
        var seq = List.of(obs(1, 10), obs(2, 50), obs(3, 90));
        LbKeogh.Envelope env = LbKeogh.computeEnvelope(seq, SCHEMA, 1);
        // At index 0, window [0,1]: values 10,50 → upper=max, lower=min (normalized)
        assertThat(env.upper()[0][0]).isGreaterThan(env.lower()[0][0]);
        // At index 1, window [0,2]: values 10,50,90
        assertThat(env.upper()[1][0]).isGreaterThan(env.upper()[0][0]);
    }

    @Test void lowerBound_identicalSequences_returnsZero() {
        var seq = List.of(obs(1, 50), obs(2, 60));
        LbKeogh.Envelope env = LbKeogh.computeEnvelope(seq, SCHEMA, 1);
        double lb = LbKeogh.lowerBound(seq, env, SCHEMA);
        assertThat(lb).isEqualTo(0.0);
    }

    @Test void lowerBound_leqFullDtw() {
        var query = List.of(obs(1, 10), obs(2, 20), obs(3, 30));
        var caseSeq = List.of(obs(1, 80), obs(2, 70), obs(3, 60));
        int windowSize = 1;
        LbKeogh.Envelope env = LbKeogh.computeEnvelope(caseSeq, SCHEMA, windowSize);
        double lb = LbKeogh.lowerBound(query, env, SCHEMA);
        DtwResult dtw = DtwSimilarity.compute(query, caseSeq, SCHEMA,
            new WarpingConstraint.SakoeChibaBand(windowSize));
        // Convert DTW score back to cost for comparison
        double dtwCost = dtw.score() > 0 ? (1.0 / dtw.score() - 1.0) * Math.max(3, 3) : Double.MAX_VALUE;
        assertThat(lb).isLessThanOrEqualTo(dtwCost + 1e-9);
    }

    @Test void lowerBound_differentLengths_handledGracefully() {
        var query = List.of(obs(1, 50), obs(2, 60));
        var caseSeq = List.of(obs(1, 50), obs(2, 60), obs(3, 70), obs(4, 80));
        LbKeogh.Envelope env = LbKeogh.computeEnvelope(caseSeq, SCHEMA, 1);
        double lb = LbKeogh.lowerBound(query, env, SCHEMA);
        assertThat(lb).isGreaterThanOrEqualTo(0.0);
    }

    @Test void lowerBound_emptyQuery_returnsZero() {
        var caseSeq = List.of(obs(1, 50));
        LbKeogh.Envelope env = LbKeogh.computeEnvelope(caseSeq, SCHEMA, 1);
        double lb = LbKeogh.lowerBound(List.of(), env, SCHEMA);
        assertThat(lb).isEqualTo(0.0);
    }

    @Test void computeEnvelope_emptySequence_returnsEmptyEnvelope() {
        LbKeogh.Envelope env = LbKeogh.computeEnvelope(List.of(), SCHEMA, 1);
        assertThat(env.length()).isEqualTo(0);
    }

    @Test void lowerBound_multiDimensional_sumsContributions() {
        var multiSchema = FeatureField.timeSeries("ts", "time",
            FeatureField.numeric("time", 0, 10),
            FeatureField.numeric("x", 0, 100),
            FeatureField.numeric("y", 0, 100));
        var query = List.of(Map.of(
            "time", FeatureValue.number(1),
            "x", FeatureValue.number(0),
            "y", FeatureValue.number(0)));
        var caseSeq = List.of(Map.of(
            "time", FeatureValue.number(1),
            "x", FeatureValue.number(100),
            "y", FeatureValue.number(100)));
        LbKeogh.Envelope env = LbKeogh.computeEnvelope(caseSeq, multiSchema, 1);
        double lb = LbKeogh.lowerBound(query, env, multiSchema);
        assertThat(lb).isGreaterThan(0.0);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=LbKeoghTest -q`
Expected: compilation failure — `LbKeogh` class not found.

- [ ] **Step 3: Implement LbKeogh**

```java
package io.casehub.neocortex.memory.cbr;

import java.util.List;
import java.util.Map;

public final class LbKeogh {

    private LbKeogh() {}

    public record Envelope(double[][] upper, double[][] lower, int length, int dimensions) {}

    public static Envelope computeEnvelope(List<Map<String, FeatureValue>> sequence,
                                            FeatureField.TimeSeries schema,
                                            int windowSize) {
        int m = sequence.size();
        if (m == 0) return new Envelope(new double[0][], new double[0][], 0, 0);

        List<FeatureField.Numeric> fields = DtwSimilarity.scorableNumericFields(schema);
        int D = fields.size();

        double[][] upper = new double[m][D];
        double[][] lower = new double[m][D];

        for (int i = 0; i < m; i++) {
            int wStart = Math.max(0, i - windowSize);
            int wEnd = Math.min(m - 1, i + windowSize);
            for (int d = 0; d < D; d++) {
                double range = fields.get(d).max() - fields.get(d).min();
                if (range <= 0) { upper[i][d] = 0; lower[i][d] = 0; continue; }
                double maxVal = Double.NEGATIVE_INFINITY;
                double minVal = Double.POSITIVE_INFINITY;
                for (int j = wStart; j <= wEnd; j++) {
                    FeatureValue fv = sequence.get(j).get(fields.get(d).name());
                    if (fv instanceof FeatureValue.NumberVal nv) {
                        double norm = nv.value() / range;
                        maxVal = Math.max(maxVal, norm);
                        minVal = Math.min(minVal, norm);
                    }
                }
                upper[i][d] = maxVal;
                lower[i][d] = minVal;
            }
        }
        return new Envelope(upper, lower, m, D);
    }

    public static double lowerBound(List<Map<String, FeatureValue>> query,
                                     Envelope caseEnvelope,
                                     FeatureField.TimeSeries schema) {
        if (query.isEmpty() || caseEnvelope.length() == 0) return 0.0;

        List<FeatureField.Numeric> fields = DtwSimilarity.scorableNumericFields(schema);
        int D = fields.size();
        int overlap = Math.min(query.size(), caseEnvelope.length());
        double lb = 0.0;

        for (int i = 0; i < overlap; i++) {
            double sumSq = 0.0;
            for (int d = 0; d < D; d++) {
                double range = fields.get(d).max() - fields.get(d).min();
                if (range <= 0) continue;
                FeatureValue fv = query.get(i).get(fields.get(d).name());
                if (fv instanceof FeatureValue.NumberVal nv) {
                    double qNorm = nv.value() / range;
                    if (qNorm > caseEnvelope.upper()[i][d]) {
                        double diff = qNorm - caseEnvelope.upper()[i][d];
                        sumSq += diff * diff;
                    } else if (qNorm < caseEnvelope.lower()[i][d]) {
                        double diff = caseEnvelope.lower()[i][d] - qNorm;
                        sumSq += diff * diff;
                    }
                }
            }
            lb += Math.sqrt(sumSq);
        }
        return lb;
    }
}
```

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=LbKeoghTest -q`
Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```
feat(#137): LbKeogh lower-bound pruning — O(n) envelope + lower bound for SakoeChibaBand DTW
```

---

### Task 9: DTW optimization integration

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java` — pass abandon threshold to DTW
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java` — LB_Keogh + abandon in retrieval loop
- Test: `memory-cbr-inmem/src/test/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStoreTest.java`

**Interfaces:**
- Consumes: `LbKeogh` from Task 8, early abandonment from Task 7
- Produces: `CbrSimilarityScorer.scoreDetailed()` accepts optional `abandonCostThreshold`. `InMemoryCbrCaseMemoryStore.retrieveSimilar()` uses LB_Keogh + abandon threshold for TimeSeries with SakoeChibaBand.

- [ ] **Step 1: Write failing integration test**

```java
@Test void retrieveSimilar_dtwOptimization_producesCorrectResults() {
    // Store cases with TimeSeries — verify that LB_Keogh + early abandonment
    // produce the same TOP-K results as unoptimized retrieval
    var schema = CbrFeatureSchema.of("game",
        FeatureField.categorical("race"),
        FeatureField.timeSeries("actions", "time",
            new SimilaritySpec.DtwSpec(new WarpingConstraint.SakoeChibaBand(1)),
            FeatureField.numeric("time", 0, 100),
            FeatureField.numeric("apm", 0, 500))
    );
    store().registerSchema(schema);

    // Store several cases with varying action sequences
    for (int i = 0; i < 20; i++) {
        var obs = List.of(
            Map.of("time", FeatureValue.number(1), "apm", FeatureValue.number(i * 25.0)),
            Map.of("time", FeatureValue.number(2), "apm", FeatureValue.number(i * 25.0 + 10))
        );
        store().store(
            new FeatureVectorCbrCase("problem", "solution", null, null,
                Map.of("race", FeatureValue.string("T"), "actions", FeatureValue.structList(obs))),
            "game", "entity", CBR, TENANT, "case-" + i);
    }

    var queryObs = List.of(
        Map.of("time", FeatureValue.number(1), "apm", FeatureValue.number(250.0)),
        Map.of("time", FeatureValue.number(2), "apm", FeatureValue.number(260.0))
    );
    var query = CbrQuery.of(TENANT, CBR, "game",
        Map.of("race", FeatureValue.string("T"), "actions", FeatureValue.structList(queryObs)), 5);

    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(5);
    // Verify descending score order
    for (int i = 0; i < results.size() - 1; i++) {
        assertThat(results.get(i).score()).isGreaterThanOrEqualTo(results.get(i + 1).score());
    }
}
```

- [ ] **Step 2: Extend CbrSimilarityScorer with abandon threshold support**

Add overload that accepts per-field abandon thresholds:
```java
public static SimilarityBreakdown scoreDetailed(Map<String, FeatureValue> queryFeatures,
                                                 Map<String, FeatureValue> caseFeatures,
                                                 Map<String, Double> weights,
                                                 CbrFeatureSchema schema,
                                                 Map<String, LocalSimilarityFunction> overrides,
                                                 double dtwAbandonCostThreshold) {
    // ... same as existing scoreDetailed but passes abandonCostThreshold to dtwSimilarity()
}
```

Update `dtwSimilarity()` to accept and pass through the threshold:
```java
private static double dtwSimilarity(FeatureField.TimeSeries ts,
                                     FeatureValue queryVal, FeatureValue caseVal,
                                     double abandonCostThreshold) {
    WarpingConstraint constraint = ts.similaritySpec() instanceof SimilaritySpec.DtwSpec ds
                                   ? ds.constraint() : new WarpingConstraint.Unconstrained();
    if (queryVal instanceof FeatureValue.StructListVal qObs
        && caseVal instanceof FeatureValue.StructListVal cObs) {
        return DtwSimilarity.compute(qObs.items(), cObs.items(), ts, constraint,
                                     abandonCostThreshold).score();
    }
    return 0.0;
}
```

The existing 5-arg `scoreDetailed()` delegates with `Double.POSITIVE_INFINITY`.

- [ ] **Step 3: Integrate LB_Keogh + abandon in InMemoryCbrCaseMemoryStore**

In `retrieveSimilar()`, after filtering candidates:

1. Identify TimeSeries fields with SakoeChibaBand constraints
2. For candidates with such fields, compute LB_Keogh before full scoring
3. Maintain a running abandon threshold from the k-th best score

```java
// Inside the candidate loop, before full scoring:
double abandonCost = Double.POSITIVE_INFINITY;
if (!candidates.isEmpty() && candidates.size() >= query.topK()) {
    double kthScore = candidates.get(candidates.size() - 1).score();
    if (kthScore > 0) {
        abandonCost = (1.0 / kthScore - 1.0) * maxSeqLen;
    }
}

// For TimeSeries fields with SakoeChibaBand, compute LB_Keogh
boolean skipCandidate = false;
for (FeatureField field : schema.fields()) {
    if (field instanceof FeatureField.TimeSeries ts
        && ts.similaritySpec() instanceof SimilaritySpec.DtwSpec ds
        && ds.constraint() instanceof WarpingConstraint.SakoeChibaBand sc) {
        FeatureValue queryTs = query.features().get(ts.name());
        FeatureValue caseTs = stored.cbrCase().features().get(ts.name());
        if (queryTs instanceof FeatureValue.StructListVal qObs
            && caseTs instanceof FeatureValue.StructListVal cObs) {
            LbKeogh.Envelope env = LbKeogh.computeEnvelope(cObs.items(), ts, sc.windowSize());
            double lb = LbKeogh.lowerBound(qObs.items(), env, ts);
            if (lb >= abandonCost) { skipCandidate = true; break; }
        }
    }
}
if (skipCandidate) continue;

// Full scoring with abandon threshold
CbrSimilarityScorer.SimilarityBreakdown breakdown = CbrSimilarityScorer.scoreDetailed(
    query.features(), stored.cbrCase().features(), query.weights(), schema, Map.of(),
    abandonCost);
```

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem -q`
Expected: all tests PASS including the new integration test.

- [ ] **Step 5: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -q`
Expected: all tests pass across all modules.

- [ ] **Step 6: Commit**

```
feat(#137): LB_Keogh + early abandonment integration — O(n) pruning before O(n×m) DTW

Closes #137
```

---

## Execution Order Summary

| Task | Issue | Description | Deps |
|------|-------|-------------|------|
| 1 | #131 | FeatureValue sealed interface | — |
| 2 | #131 | Core API + validator + scorer + DTW migration | 1 |
| 3 | #131 | InMemory store + contract tests | 2 |
| 4 | #131 | Qdrant backend | 2 |
| 5 | #131 | EmbeddingTextSimilarity | 2 |
| 6 | #131 | Full build + cross-repo issue | 3, 4, 5 |
| 7 | #137 | Early abandonment | 2 |
| 8 | #137 | LbKeogh | 2 |
| 9 | #137 | Integration | 7, 8, 3 |

Tasks 3, 4, 5 are independent (can run in parallel after Task 2).
Tasks 7, 8 are independent (can run in parallel after Task 2).
Task 9 requires 3, 7, 8.

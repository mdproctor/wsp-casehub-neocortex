# Structured Case Fields Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> executing-plans to implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural editing.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #89 — feat: structured case fields — nested objects and list containment in CbrQuery
**Issue group:** #89

**Goal:** Extend the CBR SPI to support structured case features (categorical lists, nested objects, object lists) with filter-only query predicates, backed by Qdrant's native nested payload capabilities.

**Architecture:** Three new `FeatureField` sealed variants define structured field types in the schema. A new `CbrFilter` sealed interface provides typed query predicates (`Contains`, `ContainsAll`, `ContainsAny`, `HasMatch`). `CbrQuery` gains a separate `filters` field alongside the existing scored `features`. Structured fields are filter-only — they narrow candidates via Qdrant pre-filters but do not participate in weighted similarity scoring.

**Tech Stack:** Java 21, Qdrant Java client 1.18.1, Jackson, JUnit 5, AssertJ

**Spec:** `docs/specs/2026-07-10-structured-case-fields-design.md`

## Global Constraints

- Java 21 source level, Java 26 JVM
- Inner fields of NestedObject/ObjectList must be flat (Categorical/Numeric/Text) — one level of nesting only
- Structured fields are filter-only — never scored by CbrSimilarityScorer
- `CbrFeatureSchema` enforces field name uniqueness
- `validateFlatFields` uses whitelist (match flat types), not blacklist (reject structured types)
- `HasMatch` sub-field names validated against inner schema; value types validated against inner field types
- Non-empty filters with null schema → `IllegalStateException`
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- IntelliJ MCP: `project_path=/Users/mdproctor/claude/casehub/neocortex`

---

### Task 1: Data Model — FeatureField extensions, CbrFilter, CbrFeatureSchema uniqueness

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/FeatureField.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFeatureSchema.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFilter.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/FeatureFieldTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrFeatureSchemaTest.java`
- Create: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrFilterTest.java`

**Interfaces:**
- Produces: `FeatureField.CategoricalList(String name)`, `FeatureField.NestedObject(String name, List<FeatureField> innerFields)`, `FeatureField.ObjectList(String name, List<FeatureField> innerFields)`
- Produces: `FeatureField.categoricalList(String)`, `FeatureField.nestedObject(String, FeatureField...)`, `FeatureField.objectList(String, FeatureField...)`
- Produces: `CbrFilter.Contains(String value)`, `CbrFilter.ContainsAll(List<String> values)`, `CbrFilter.ContainsAny(List<String> values)`, `CbrFilter.HasMatch(Map<String, Object> subFields)`
- Produces: `CbrFilter.contains(String)`, `CbrFilter.containsAll(List<String>)`, `CbrFilter.containsAny(List<String>)`, `CbrFilter.hasMatch(Map<String, Object>)`
- Produces: `CbrFeatureSchema` — rejects duplicate field names

- [ ] **Step 1: Write FeatureField extension tests**

Add to `FeatureFieldTest.java` using `ide_insert_member`:

```java
@Test
void categoricalList_validName() {
    var f = FeatureField.categoricalList("phases");
    assertThat(f).isInstanceOf(FeatureField.CategoricalList.class);
    assertThat(f.name()).isEqualTo("phases");
}

@Test
void categoricalList_nullNameRejected() {
    assertThatThrownBy(() -> FeatureField.categoricalList(null))
        .isInstanceOf(NullPointerException.class);
}

@Test
void nestedObject_validConstruction() {
    var f = FeatureField.nestedObject("economy",
        FeatureField.numeric("minute_3", 0, 100),
        FeatureField.categorical("tier"));
    assertThat(f).isInstanceOf(FeatureField.NestedObject.class);
    assertThat(f.name()).isEqualTo("economy");
    assertThat(((FeatureField.NestedObject) f).innerFields()).hasSize(2);
}

@Test
void nestedObject_rejectsNestedInnerFields() {
    assertThatThrownBy(() -> FeatureField.nestedObject("bad",
        FeatureField.categoricalList("nested_list")))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("CategoricalList");
}

@Test
void nestedObject_rejectsSimilaritySpecOnInnerCategorical() {
    assertThatThrownBy(() -> FeatureField.nestedObject("bad",
        FeatureField.categorical("cat", SimilaritySpec.categoricalTableBuilder()
            .add("A", "B", 0.5).build())))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("SimilaritySpec not supported");
}

@Test
void nestedObject_rejectsSimilaritySpecOnInnerNumeric() {
    assertThatThrownBy(() -> FeatureField.nestedObject("bad",
        FeatureField.numeric("num", 0, 100, new SimilaritySpec.GaussianDecay(0.3))))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("SimilaritySpec not supported");
}

@Test
void nestedObject_rejectsSemanticInnerText() {
    assertThatThrownBy(() -> FeatureField.nestedObject("bad",
        FeatureField.semanticText("desc")))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("semantic matching not supported");
}

@Test
void nestedObject_rejectsDuplicateInnerFieldNames() {
    assertThatThrownBy(() -> FeatureField.nestedObject("bad",
        FeatureField.categorical("name"),
        FeatureField.numeric("name", 0, 10)))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("Duplicate inner field name");
}

@Test
void objectList_validConstruction() {
    var f = FeatureField.objectList("moments",
        FeatureField.categorical("type"),
        FeatureField.numeric("minute", 0, 90));
    assertThat(f).isInstanceOf(FeatureField.ObjectList.class);
    assertThat(f.name()).isEqualTo("moments");
    assertThat(((FeatureField.ObjectList) f).innerFields()).hasSize(2);
}

@Test
void objectList_rejectsNestedInnerFields() {
    assertThatThrownBy(() -> FeatureField.objectList("bad",
        FeatureField.nestedObject("inner", FeatureField.categorical("c"))))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("NestedObject");
}

@Test
void objectList_innerFieldsDefensivelyCopied() {
    var inner = new java.util.ArrayList<>(java.util.List.of(
        FeatureField.categorical("type")));
    var f = FeatureField.objectList("moments", FeatureField.categorical("type"));
    inner.add(FeatureField.numeric("extra", 0, 10));
    assertThat(((FeatureField.ObjectList) f).innerFields()).hasSize(1);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=FeatureFieldTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — CategoricalList, NestedObject, ObjectList don't exist yet

- [ ] **Step 3: Implement FeatureField extensions**

Use `ide_edit_member` on the `FeatureField` sealed interface declaration to update the `permits` clause. Then use `ide_insert_member` to add the three new records and the `validateFlatFields` method, and the three factory methods.

Add to the `permits` clause: `CategoricalList, NestedObject, ObjectList`

Add new records (after `Text`):

```java
record CategoricalList(String name) implements FeatureField {
    public CategoricalList {
        Objects.requireNonNull(name, "name");
    }
}

record NestedObject(String name, List<FeatureField> innerFields) implements FeatureField {
    public NestedObject {
        Objects.requireNonNull(name, "name");
        Objects.requireNonNull(innerFields, "innerFields");
        innerFields = List.copyOf(innerFields);
        validateFlatFields(innerFields);
    }
}

record ObjectList(String name, List<FeatureField> innerFields) implements FeatureField {
    public ObjectList {
        Objects.requireNonNull(name, "name");
        Objects.requireNonNull(innerFields, "innerFields");
        innerFields = List.copyOf(innerFields);
        validateFlatFields(innerFields);
    }
}

private static void validateFlatFields(List<FeatureField> fields) {
    Set<String> names = new HashSet<>();
    for (FeatureField f : fields) {
        if (!names.add(f.name()))
            throw new IllegalArgumentException("Duplicate inner field name: '" + f.name() + "'");
        switch (f) {
            case Categorical c -> {
                if (c.similaritySpec() != null) throw new IllegalArgumentException(
                    "Inner field '" + c.name() + "': SimilaritySpec not supported — inner fields are filter-only");
            }
            case Numeric n -> {
                if (n.similaritySpec() != null) throw new IllegalArgumentException(
                    "Inner field '" + n.name() + "': SimilaritySpec not supported — inner fields are filter-only");
            }
            case Text t -> {
                if (t.semantic()) throw new IllegalArgumentException(
                    "Inner field '" + t.name() + "': semantic matching not supported — inner fields are filter-only");
            }
            case CategoricalList cl -> throw new IllegalArgumentException(
                "Inner fields must be flat (Categorical/Numeric/Text), got: CategoricalList");
            case NestedObject no -> throw new IllegalArgumentException(
                "Inner fields must be flat (Categorical/Numeric/Text), got: NestedObject");
            case ObjectList ol -> throw new IllegalArgumentException(
                "Inner fields must be flat (Categorical/Numeric/Text), got: ObjectList");
        }
    }
}
```

Add factory methods:

```java
static FeatureField categoricalList(String name) { return new CategoricalList(name); }
static FeatureField nestedObject(String name, FeatureField... innerFields) {
    return new NestedObject(name, List.of(innerFields));
}
static FeatureField objectList(String name, FeatureField... innerFields) {
    return new ObjectList(name, List.of(innerFields));
}
```

Add import for `java.util.Set` and `java.util.HashSet`.

- [ ] **Step 4: Run FeatureField tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=FeatureFieldTest`
Expected: all tests pass

- [ ] **Step 5: Write CbrFilter tests**

Create `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrFilterTest.java`:

```java
package io.casehub.neocortex.memory.cbr;

import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class CbrFilterTest {

    @Test
    void contains_validValue() {
        var f = CbrFilter.contains("EARLY_AGGRESSION");
        assertThat(f).isInstanceOf(CbrFilter.Contains.class);
        assertThat(f.value()).isEqualTo("EARLY_AGGRESSION");
    }

    @Test
    void contains_nullRejected() {
        assertThatThrownBy(() -> CbrFilter.contains(null))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void containsAll_validValues() {
        var f = CbrFilter.containsAll(List.of("A", "B"));
        assertThat(f.values()).containsExactly("A", "B");
    }

    @Test
    void containsAll_emptyRejected() {
        assertThatThrownBy(() -> CbrFilter.containsAll(List.of()))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("must not be empty");
    }

    @Test
    void containsAll_defensivelyCopied() {
        var list = new java.util.ArrayList<>(List.of("A"));
        var f = CbrFilter.containsAll(list);
        list.add("B");
        assertThat(f.values()).hasSize(1);
    }

    @Test
    void containsAny_validValues() {
        var f = CbrFilter.containsAny(List.of("X", "Y"));
        assertThat(f.values()).containsExactly("X", "Y");
    }

    @Test
    void containsAny_emptyRejected() {
        assertThatThrownBy(() -> CbrFilter.containsAny(List.of()))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void hasMatch_validSubFields() {
        var f = CbrFilter.hasMatch(Map.of("type", "FIRST_CONTACT", "minute", 3.2));
        assertThat(f.subFields()).hasSize(2);
    }

    @Test
    void hasMatch_emptySubFieldsRejected() {
        assertThatThrownBy(() -> CbrFilter.hasMatch(Map.of()))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("must not be empty");
    }

    @Test
    void hasMatch_invalidSubFieldValueTypeRejected() {
        assertThatThrownBy(() -> CbrFilter.hasMatch(Map.of("bad", List.of("x"))))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("must be String, Number, or NumericRange");
    }

    @Test
    void hasMatch_acceptsNumericRange() {
        var f = CbrFilter.hasMatch(Map.of("score", NumericRange.of(80, 90)));
        assertThat(f.subFields().get("score")).isInstanceOf(NumericRange.class);
    }

    @Test
    void hasMatch_defensivelyCopied() {
        var map = new java.util.HashMap<String, Object>();
        map.put("type", "X");
        var f = CbrFilter.hasMatch(map);
        map.put("extra", "Y");
        assertThat(f.subFields()).hasSize(1);
    }
}
```

- [ ] **Step 6: Implement CbrFilter**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFilter.java` using the Write tool (new file):

```java
package io.casehub.neocortex.memory.cbr;

import java.util.List;
import java.util.Map;
import java.util.Objects;

public sealed interface CbrFilter {

    record Contains(String value) implements CbrFilter {
        public Contains {
            Objects.requireNonNull(value, "value");
        }
    }

    record ContainsAll(List<String> values) implements CbrFilter {
        public ContainsAll {
            Objects.requireNonNull(values, "values");
            if (values.isEmpty()) throw new IllegalArgumentException("values must not be empty");
            values = List.copyOf(values);
        }
    }

    record ContainsAny(List<String> values) implements CbrFilter {
        public ContainsAny {
            Objects.requireNonNull(values, "values");
            if (values.isEmpty()) throw new IllegalArgumentException("values must not be empty");
            values = List.copyOf(values);
        }
    }

    record HasMatch(Map<String, Object> subFields) implements CbrFilter {
        public HasMatch {
            Objects.requireNonNull(subFields, "subFields");
            if (subFields.isEmpty()) throw new IllegalArgumentException("subFields must not be empty");
            for (Map.Entry<String, Object> e : subFields.entrySet()) {
                Object v = e.getValue();
                if (!(v instanceof String) && !(v instanceof Number) && !(v instanceof NumericRange))
                    throw new IllegalArgumentException(
                        "Sub-field '" + e.getKey() + "' value must be String, Number, or NumericRange, got: "
                        + v.getClass().getSimpleName());
            }
            subFields = Map.copyOf(subFields);
        }
    }

    static Contains contains(String value) { return new Contains(value); }
    static ContainsAll containsAll(List<String> values) { return new ContainsAll(values); }
    static ContainsAny containsAny(List<String> values) { return new ContainsAny(values); }
    static HasMatch hasMatch(Map<String, Object> subFields) { return new HasMatch(subFields); }
}
```

- [ ] **Step 7: Run CbrFilter tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrFilterTest`
Expected: all pass

- [ ] **Step 8: Write CbrFeatureSchema uniqueness test**

Add to `CbrFeatureSchemaTest.java` using `ide_insert_member`:

```java
@Test
void duplicateFieldNamesRejected() {
    assertThatThrownBy(() -> CbrFeatureSchema.of("test",
        FeatureField.categorical("name"),
        FeatureField.numeric("name", 0, 10)))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("Duplicate field name: 'name'");
}

@Test
void duplicateFieldNamesAcrossTypes() {
    assertThatThrownBy(() -> CbrFeatureSchema.of("test",
        FeatureField.categorical("field"),
        FeatureField.categoricalList("field")))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("Duplicate field name");
}
```

- [ ] **Step 9: Implement CbrFeatureSchema uniqueness**

Use `ide_replace_member` on `CbrFeatureSchema`'s compact constructor to add uniqueness validation:

```java
Objects.requireNonNull(caseType, "caseType required");
if (caseType.isBlank()) throw new IllegalArgumentException("caseType must not be blank");
Objects.requireNonNull(fields, "fields required");
fields = List.copyOf(fields);
Set<String> names = new HashSet<>();
for (FeatureField f : fields) {
    if (!names.add(f.name()))
        throw new IllegalArgumentException("Duplicate field name: '" + f.name() + "'");
}
```

Add imports for `java.util.Set` and `java.util.HashSet`.

- [ ] **Step 10: Run CbrFeatureSchema tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrFeatureSchemaTest`
Expected: all pass

- [ ] **Step 11: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/src/main/java/io/casehub/neocortex/memory/cbr/FeatureField.java memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFilter.java memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFeatureSchema.java memory-api/src/test/java/io/casehub/neocortex/memory/cbr/FeatureFieldTest.java memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrFilterTest.java memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrFeatureSchemaTest.java
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#89): FeatureField extensions, CbrFilter, CbrFeatureSchema uniqueness"
```

---

### Task 2: CbrQuery filters field + CbrFeatureValidator + CbrSimilarityScorer + compile fixes

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrQuery.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFeatureValidator.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrQueryTest.java`
- Create: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrFeatureValidatorTest.java`
- Modify: `memory-cbr-crossencoder/src/main/java/io/casehub/neocortex/memory/cbr/crossencoder/RerankingCbrCaseMemoryStore.java:67-71`
- Modify: `memory-cbr-crossencoder/src/main/java/io/casehub/neocortex/memory/cbr/crossencoder/ReactiveRerankingCbrCaseMemoryStore.java:61-65`
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java:237`
- Modify: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/CbrQueryTranslatorTest.java:109,162`

**Interfaces:**
- Consumes: `CbrFilter` (from Task 1)
- Produces: `CbrQuery.filters()` → `Map<String, CbrFilter>`, `CbrQuery.withFilter(String, CbrFilter)`, `CbrQuery.withFilters(Map<String, CbrFilter>)`
- Produces: `CbrFeatureValidator.validateStoreFeatures(Map<String, Object>, CbrFeatureSchema)`, `CbrFeatureValidator.validateQueryFeatures(Map<String, Object>, CbrFeatureSchema)`, `CbrFeatureValidator.validateFilters(Map<String, CbrFilter>, CbrFeatureSchema)`

- [ ] **Step 1: Write CbrQuery filter tests**

Add to `CbrQueryTest.java`:

```java
@Test
void of_hasEmptyFilters() {
    var q = CbrQuery.of("t", CBR, "type", Map.of(), 5);
    assertThat(q.filters()).isEmpty();
}

@Test
void withFilter_addsFilter() {
    var q = CbrQuery.of("t", CBR, "type", Map.of(), 5)
        .withFilter("phases", CbrFilter.contains("A"));
    assertThat(q.filters()).hasSize(1);
    assertThat(q.filters().get("phases")).isInstanceOf(CbrFilter.Contains.class);
}

@Test
void withFilters_replacesAll() {
    var q = CbrQuery.of("t", CBR, "type", Map.of(), 5)
        .withFilter("phases", CbrFilter.contains("A"))
        .withFilters(Map.of("moments", CbrFilter.hasMatch(Map.of("type", "X"))));
    assertThat(q.filters()).hasSize(1);
    assertThat(q.filters()).containsKey("moments");
}

@Test
void filtersDefensivelyCopied() {
    var filters = new java.util.HashMap<String, CbrFilter>();
    filters.put("f", CbrFilter.contains("X"));
    var q = CbrQuery.of("t", CBR, "type", Map.of(), 5).withFilters(filters);
    filters.put("extra", CbrFilter.contains("Y"));
    assertThat(q.filters()).hasSize(1);
}
```

- [ ] **Step 2: Implement CbrQuery changes**

Use `ide_edit_member` on the `CbrQuery` record declaration to add the `filters` field between `features` and `weights`:

```java
public record CbrQuery(
    String tenantId,
    MemoryDomain domain,
    String caseType,
    Map<String, Object> features,
    Map<String, CbrFilter> filters,
    Map<String, Double> weights,
    int topK,
    double minSimilarity,
    Instant notBefore,
    String problem,
    double vectorWeight,
    RetrievalMode retrievalMode,
    FusionStrategy fusionStrategy
) { ... }
```

Update the compact constructor to add: `Objects.requireNonNull(filters, "filters required"); filters = Map.copyOf(filters);`

Update the `of()` factory method to pass `Map.of()` for filters.

Update ALL wither methods to thread `filters` through in the new CbrQuery constructor call.

Add new wither methods:

```java
public CbrQuery withFilter(String field, CbrFilter filter) {
    Map<String, CbrFilter> newFilters = new java.util.HashMap<>(filters);
    newFilters.put(field, filter);
    return withFilters(newFilters);
}

public CbrQuery withFilters(Map<String, CbrFilter> filters) {
    return new CbrQuery(tenantId, domain, caseType, features, filters, weights, topK,
                        minSimilarity, notBefore, problem, vectorWeight, retrievalMode, fusionStrategy);
}
```

- [ ] **Step 3: Fix all compile-breaking call sites**

Every `new CbrQuery(...)` call in the codebase needs the new `filters` parameter (insert `Map.of()` after `features`). Use `ide_replace_member` or `ide_edit_member` for each:

1. `RerankingCbrCaseMemoryStore.retrieveSimilar()` line 67: insert `query.filters(),` after `query.features(),`
2. `ReactiveRerankingCbrCaseMemoryStore.retrieveSimilar()` line 61: same change
3. `CbrCaseMemoryStoreContractTest` line 237: insert `Map.of(),` after `Map.of("opponent_race", "Zerg"),`
4. `CbrQueryTranslatorTest` lines 109 and 162: insert `Map.of(),` after the features `Map.of(...)` argument
5. `CbrQueryTest` line 48: insert `Map.of(),` after `Map.of(),`

- [ ] **Step 4: Run CbrQuery tests and verify project compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrQueryTest`
Then: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile`
Expected: all tests pass, full project compiles

- [ ] **Step 5: Write CbrFeatureValidator tests**

Create `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrFeatureValidatorTest.java`:

```java
package io.casehub.neocortex.memory.cbr;

import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class CbrFeatureValidatorTest {

    private static final CbrFeatureSchema SCHEMA = CbrFeatureSchema.of("test",
        FeatureField.categorical("posture"),
        FeatureField.numeric("score", 0, 100),
        FeatureField.text("description"),
        FeatureField.categoricalList("phases"),
        FeatureField.nestedObject("economy",
            FeatureField.numeric("minute_3", 0, 100),
            FeatureField.categorical("tier")),
        FeatureField.objectList("moments",
            FeatureField.categorical("type"),
            FeatureField.numeric("minute", 0, 90)));

    // --- validateStoreFeatures ---

    @Test
    void validateStoreFeatures_validFlatFeatures() {
        CbrFeatureValidator.validateStoreFeatures(
            Map.of("posture", "AGGRESSIVE", "score", 85), SCHEMA);
    }

    @Test
    void validateStoreFeatures_validCategoricalList() {
        CbrFeatureValidator.validateStoreFeatures(
            Map.of("phases", List.of("EARLY", "MID")), SCHEMA);
    }

    @Test
    void validateStoreFeatures_categoricalListRequiresList() {
        assertThatThrownBy(() -> CbrFeatureValidator.validateStoreFeatures(
            Map.of("phases", "not_a_list"), SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void validateStoreFeatures_categoricalListRequiresStringElements() {
        assertThatThrownBy(() -> CbrFeatureValidator.validateStoreFeatures(
            Map.of("phases", List.of(1, 2, 3)), SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void validateStoreFeatures_validNestedObject() {
        CbrFeatureValidator.validateStoreFeatures(
            Map.of("economy", Map.of("minute_3", 45, "tier", "gold")), SCHEMA);
    }

    @Test
    void validateStoreFeatures_nestedObjectRequiresMap() {
        assertThatThrownBy(() -> CbrFeatureValidator.validateStoreFeatures(
            Map.of("economy", "not_a_map"), SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void validateStoreFeatures_validObjectList() {
        CbrFeatureValidator.validateStoreFeatures(
            Map.of("moments", List.of(
                Map.of("type", "FIRST_CONTACT", "minute", 3.2),
                Map.of("type", "BATTLE_WON", "minute", 5.1))), SCHEMA);
    }

    @Test
    void validateStoreFeatures_objectListRequiresListOfMaps() {
        assertThatThrownBy(() -> CbrFeatureValidator.validateStoreFeatures(
            Map.of("moments", List.of("not", "maps")), SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    // --- validateQueryFeatures ---

    @Test
    void validateQueryFeatures_rejectsStructuredFieldInFeatures() {
        assertThatThrownBy(() -> CbrFeatureValidator.validateQueryFeatures(
            Map.of("phases", List.of("A")), SCHEMA))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("must be queried via filters");
    }

    @Test
    void validateQueryFeatures_acceptsFlatFeatures() {
        CbrFeatureValidator.validateQueryFeatures(
            Map.of("posture", "AGGRESSIVE"), SCHEMA);
    }

    // --- validateFilters ---

    @Test
    void validateFilters_containsOnCategoricalList() {
        CbrFeatureValidator.validateFilters(
            Map.of("phases", CbrFilter.contains("A")), SCHEMA);
    }

    @Test
    void validateFilters_containsOnNonListFieldRejected() {
        assertThatThrownBy(() -> CbrFeatureValidator.validateFilters(
            Map.of("posture", CbrFilter.contains("A")), SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void validateFilters_hasMatchOnObjectList() {
        CbrFeatureValidator.validateFilters(
            Map.of("moments", CbrFilter.hasMatch(Map.of("type", "X"))), SCHEMA);
    }

    @Test
    void validateFilters_hasMatchOnCategoricalListRejected() {
        assertThatThrownBy(() -> CbrFeatureValidator.validateFilters(
            Map.of("phases", CbrFilter.hasMatch(Map.of("x", "y"))), SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void validateFilters_unknownFieldRejected() {
        assertThatThrownBy(() -> CbrFeatureValidator.validateFilters(
            Map.of("nonexistent", CbrFilter.contains("A")), SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void validateFilters_hasMatchUnknownSubFieldRejected() {
        assertThatThrownBy(() -> CbrFeatureValidator.validateFilters(
            Map.of("moments", CbrFilter.hasMatch(Map.of("nonexistent", "val"))), SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void validateFilters_hasMatchWrongSubFieldTypeRejected() {
        assertThatThrownBy(() -> CbrFeatureValidator.validateFilters(
            Map.of("moments", CbrFilter.hasMatch(Map.of("minute", "not_a_number"))), SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void validateFilters_hasMatchStringOnNumericRejected() {
        assertThatThrownBy(() -> CbrFeatureValidator.validateFilters(
            Map.of("economy", CbrFilter.hasMatch(Map.of("minute_3", "not_numeric"))), SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void validateFilters_hasMatchNumericOnCategoricalRejected() {
        assertThatThrownBy(() -> CbrFeatureValidator.validateFilters(
            Map.of("economy", CbrFilter.hasMatch(Map.of("tier", 42))), SCHEMA))
            .isInstanceOf(IllegalArgumentException.class);
    }
}
```

- [ ] **Step 6: Implement CbrFeatureValidator**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFeatureValidator.java`:

```java
package io.casehub.neocortex.memory.cbr;

import java.util.List;
import java.util.Map;

public final class CbrFeatureValidator {

    private CbrFeatureValidator() {}

    public static void validateStoreFeatures(Map<String, Object> features, CbrFeatureSchema schema) {
        for (var entry : features.entrySet()) {
            FeatureField field = findField(schema, entry.getKey());
            if (field == null) continue;
            Object value = entry.getValue();
            switch (field) {
                case FeatureField.Categorical c -> requireType(entry.getKey(), value, String.class);
                case FeatureField.Numeric n -> {
                    if (!(value instanceof Number) && !(value instanceof NumericRange))
                        throw new IllegalArgumentException(
                            "Numeric field '" + entry.getKey() + "' requires Number or NumericRange, got: "
                            + value.getClass().getSimpleName());
                }
                case FeatureField.Text t -> requireType(entry.getKey(), value, String.class);
                case FeatureField.CategoricalList cl -> {
                    if (!(value instanceof List<?> list))
                        throw new IllegalArgumentException(
                            "CategoricalList field '" + entry.getKey() + "' requires List, got: "
                            + value.getClass().getSimpleName());
                    for (Object elem : list) {
                        if (!(elem instanceof String))
                            throw new IllegalArgumentException(
                                "CategoricalList field '" + entry.getKey() + "' requires List<String>, element is: "
                                + elem.getClass().getSimpleName());
                    }
                }
                case FeatureField.NestedObject no -> {
                    if (!(value instanceof Map<?,?> map))
                        throw new IllegalArgumentException(
                            "NestedObject field '" + entry.getKey() + "' requires Map, got: "
                            + value.getClass().getSimpleName());
                    validateInnerValues(entry.getKey(), map, no.innerFields());
                }
                case FeatureField.ObjectList ol -> {
                    if (!(value instanceof List<?> list))
                        throw new IllegalArgumentException(
                            "ObjectList field '" + entry.getKey() + "' requires List, got: "
                            + value.getClass().getSimpleName());
                    for (Object elem : list) {
                        if (!(elem instanceof Map<?,?> map))
                            throw new IllegalArgumentException(
                                "ObjectList field '" + entry.getKey() + "' requires List<Map>, element is: "
                                + elem.getClass().getSimpleName());
                        validateInnerValues(entry.getKey(), map, ol.innerFields());
                    }
                }
            }
        }
    }

    public static void validateQueryFeatures(Map<String, Object> features, CbrFeatureSchema schema) {
        for (var entry : features.entrySet()) {
            FeatureField field = findField(schema, entry.getKey());
            if (field == null) continue;
            Object value = entry.getValue();
            switch (field) {
                case FeatureField.Categorical c -> requireType(entry.getKey(), value, String.class);
                case FeatureField.Numeric n -> {
                    if (!(value instanceof Number) && !(value instanceof NumericRange))
                        throw new IllegalArgumentException(
                            "Numeric field '" + entry.getKey() + "' requires Number or NumericRange, got: "
                            + value.getClass().getSimpleName());
                }
                case FeatureField.Text t -> requireType(entry.getKey(), value, String.class);
                case FeatureField.CategoricalList cl -> throw new IllegalArgumentException(
                    "Structured field '" + entry.getKey() + "' must be queried via filters, not features");
                case FeatureField.NestedObject no -> throw new IllegalArgumentException(
                    "Structured field '" + entry.getKey() + "' must be queried via filters, not features");
                case FeatureField.ObjectList ol -> throw new IllegalArgumentException(
                    "Structured field '" + entry.getKey() + "' must be queried via filters, not features");
            }
        }
    }

    public static void validateFilters(Map<String, CbrFilter> filters, CbrFeatureSchema schema) {
        for (var entry : filters.entrySet()) {
            String name = entry.getKey();
            CbrFilter filter = entry.getValue();
            FeatureField field = findField(schema, name);
            if (field == null)
                throw new IllegalArgumentException("Filter field '" + name + "' not found in schema");

            switch (filter) {
                case CbrFilter.Contains c -> requireCategoricalList(name, field);
                case CbrFilter.ContainsAll ca -> requireCategoricalList(name, field);
                case CbrFilter.ContainsAny ca -> requireCategoricalList(name, field);
                case CbrFilter.HasMatch hm -> {
                    if (!(field instanceof FeatureField.NestedObject) && !(field instanceof FeatureField.ObjectList))
                        throw new IllegalArgumentException(
                            "HasMatch filter on '" + name + "' requires NestedObject or ObjectList field, got: "
                            + field.getClass().getSimpleName());
                    List<FeatureField> innerFields = field instanceof FeatureField.NestedObject no
                        ? no.innerFields() : ((FeatureField.ObjectList) field).innerFields();
                    validateHasMatchSubFields(name, hm, innerFields);
                }
            }
        }
    }

    private static void validateHasMatchSubFields(String fieldName, CbrFilter.HasMatch hm,
                                                   List<FeatureField> innerFields) {
        for (var sub : hm.subFields().entrySet()) {
            FeatureField inner = null;
            for (FeatureField f : innerFields) {
                if (f.name().equals(sub.getKey())) { inner = f; break; }
            }
            if (inner == null)
                throw new IllegalArgumentException(
                    "HasMatch sub-field '" + sub.getKey() + "' not found in inner schema of '" + fieldName + "'");

            Object value = sub.getValue();
            switch (inner) {
                case FeatureField.Categorical c, FeatureField.Text t -> {
                    if (!(value instanceof String))
                        throw new IllegalArgumentException(
                            "HasMatch sub-field '" + sub.getKey() + "' on '" + fieldName
                            + "' requires String, got: " + value.getClass().getSimpleName());
                }
                case FeatureField.Numeric n -> {
                    if (!(value instanceof Number) && !(value instanceof NumericRange))
                        throw new IllegalArgumentException(
                            "HasMatch sub-field '" + sub.getKey() + "' on '" + fieldName
                            + "' requires Number or NumericRange, got: " + value.getClass().getSimpleName());
                }
                default -> throw new IllegalStateException("Unexpected inner field type: " + inner);
            }
        }
    }

    private static void requireCategoricalList(String name, FeatureField field) {
        if (!(field instanceof FeatureField.CategoricalList))
            throw new IllegalArgumentException(
                "Contains/ContainsAll/ContainsAny filter on '" + name
                + "' requires CategoricalList field, got: " + field.getClass().getSimpleName());
    }

    private static void requireType(String name, Object value, Class<?> expected) {
        if (!expected.isInstance(value))
            throw new IllegalArgumentException(
                "Field '" + name + "' requires " + expected.getSimpleName()
                + ", got: " + value.getClass().getSimpleName());
    }

    @SuppressWarnings("unchecked")
    private static void validateInnerValues(String parentName, Map<?,?> map,
                                             List<FeatureField> innerFields) {
        for (var entry : map.entrySet()) {
            String key = String.valueOf(entry.getKey());
            FeatureField inner = null;
            for (FeatureField f : innerFields) {
                if (f.name().equals(key)) { inner = f; break; }
            }
            if (inner == null) continue;
            Object value = entry.getValue();
            switch (inner) {
                case FeatureField.Categorical c -> requireType(parentName + "." + key, value, String.class);
                case FeatureField.Numeric n -> {
                    if (!(value instanceof Number))
                        throw new IllegalArgumentException(
                            "Inner field '" + parentName + "." + key + "' requires Number, got: "
                            + value.getClass().getSimpleName());
                }
                case FeatureField.Text t -> requireType(parentName + "." + key, value, String.class);
                default -> {}
            }
        }
    }

    private static FeatureField findField(CbrFeatureSchema schema, String name) {
        for (FeatureField f : schema.fields()) {
            if (f.name().equals(name)) return f;
        }
        return null;
    }
}
```

- [ ] **Step 7: Update CbrSimilarityScorer**

Use `ide_replace_member` on `CbrSimilarityScorer.score()` (the 5-param overload at line 58) to add the structured field skip before the localSimilarity call:

In the loop body, after `if (field == null) continue;`, add:
```java
if (field instanceof FeatureField.CategoricalList
    || field instanceof FeatureField.NestedObject
    || field instanceof FeatureField.ObjectList) continue;
```

Use `ide_replace_member` on `localSimilarity()` to add exhaustive switch cases:

```java
case FeatureField.CategoricalList cl -> throw new IllegalStateException("Structured field in scorer");
case FeatureField.NestedObject no -> throw new IllegalStateException("Structured field in scorer");
case FeatureField.ObjectList ol -> throw new IllegalStateException("Structured field in scorer");
```

- [ ] **Step 8: Run all memory-api tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api`
Expected: all pass

- [ ] **Step 9: Verify full project compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile`
Expected: BUILD SUCCESS

- [ ] **Step 10: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/src/ memory-cbr-crossencoder/src/ memory-testing/src/ memory-qdrant/src/test/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#89): CbrQuery filters field, CbrFeatureValidator, CbrSimilarityScorer skip, compile fixes"
```

---

### Task 3: Contract tests + InMemoryCbrCaseMemoryStore filter evaluation

**Files:**
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`

**Interfaces:**
- Consumes: `CbrFilter` (Task 1), `CbrQuery.filters()` (Task 2), `CbrFeatureValidator` (Task 2)
- Produces: Contract tests verifying structured field storage, filtering, and validation across all backends

- [ ] **Step 1: Write contract tests**

Add all ~23 tests to `CbrCaseMemoryStoreContractTest.java` using `ide_insert_member`. These tests use the same `store()` abstract method pattern as existing tests. Register a schema with structured fields, store cases with structured feature values, query with filters, and assert results.

Key test patterns — each test:
1. Registers a schema with structured fields
2. Stores one or more cases with structured feature values
3. Queries with `CbrQuery.of(...).withFilter(...)` 
4. Asserts expected results

Schema for structured tests:
```java
private void registerStructuredSchema() {
    store().registerSchema(CbrFeatureSchema.of("game",
        FeatureField.categorical("posture"),
        FeatureField.numeric("score", 0, 100),
        FeatureField.categoricalList("phases"),
        FeatureField.nestedObject("economy",
            FeatureField.numeric("minute_3", 0, 100),
            FeatureField.categorical("tier")),
        FeatureField.objectList("moments",
            FeatureField.categorical("type"),
            FeatureField.numeric("minute", 0, 90))));
}
```

Tests cover: CategoricalList with Contains/ContainsAll/ContainsAny, NestedObject with HasMatch (categorical and numeric sub-fields, NumericRange), ObjectList with HasMatch (single sub-field, multiple sub-fields, no matching element), mixed flat+structured, multiple filters AND semantics, filter on missing field, empty CategoricalList, and all validation error paths (wrong filter type, store-time mismatch, structured field in features, null schema with filters, inner SimilaritySpec, inner semantic Text, duplicate schema names, HasMatch nonexistent sub-field, HasMatch wrong sub-field type).

Complete test code: follow the patterns from the spec's §Contract Tests list (23 tests). Each test is a `@Test` method with descriptive name matching the spec numbering.

- [ ] **Step 2: Run contract tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem`
Expected: new tests fail (InMemoryCbrCaseMemoryStore doesn't implement filter evaluation yet)

- [ ] **Step 3: Implement InMemoryCbrCaseMemoryStore filter evaluation**

Modify `InMemoryCbrCaseMemoryStore.retrieveSimilar()` to:
1. Add schema null guard when filters are non-empty
2. Call `CbrFeatureValidator.validateQueryFeatures()` instead of local validation
3. Call `CbrFeatureValidator.validateFilters()` for filter validation
4. Add `matchesFilters()` call after identity filters, before scoring

Add `matchesFilters` private method:

```java
@SuppressWarnings("unchecked")
private boolean matchesFilters(CbrCase storedCase, Map<String, CbrFilter> filters,
                                CbrFeatureSchema schema) {
    if (filters.isEmpty()) return true;
    for (var entry : filters.entrySet()) {
        String fieldName = entry.getKey();
        CbrFilter filter = entry.getValue();
        Object storedValue = storedCase.features().get(fieldName);
        if (storedValue == null) return false;

        FeatureField field = schema.fields().stream()
            .filter(f -> f.name().equals(fieldName)).findFirst().orElse(null);

        boolean matches = switch (filter) {
            case CbrFilter.Contains c ->
                storedValue instanceof List<?> list && list.contains(c.value());
            case CbrFilter.ContainsAll ca ->
                storedValue instanceof List<?> list && list.containsAll(ca.values());
            case CbrFilter.ContainsAny ca ->
                storedValue instanceof List<?> list && ca.values().stream().anyMatch(list::contains);
            case CbrFilter.HasMatch hm -> matchesHasMatch(storedValue, hm, field);
        };
        if (!matches) return false;
    }
    return true;
}

private boolean matchesHasMatch(Object storedValue, CbrFilter.HasMatch hm, FeatureField field) {
    if (field instanceof FeatureField.ObjectList) {
        if (!(storedValue instanceof List<?> list)) return false;
        return list.stream().anyMatch(elem ->
            elem instanceof Map<?,?> map && allSubFieldsMatch(map, hm.subFields()));
    } else {
        if (!(storedValue instanceof Map<?,?> map)) return false;
        return allSubFieldsMatch(map, hm.subFields());
    }
}

private boolean allSubFieldsMatch(Map<?,?> stored, Map<String, Object> subFields) {
    for (var sub : subFields.entrySet()) {
        Object storedVal = stored.get(sub.getKey());
        if (storedVal == null) return false;
        Object queryVal = sub.getValue();
        if (queryVal instanceof NumericRange range) {
            if (!(storedVal instanceof Number num)) return false;
            double d = num.doubleValue();
            if (d < range.min() || d > range.max()) return false;
        } else if (queryVal instanceof Number qn) {
            if (!(storedVal instanceof Number sn)) return false;
            if (Double.compare(qn.doubleValue(), sn.doubleValue()) != 0) return false;
        } else {
            if (!queryVal.equals(storedVal)) return false;
        }
    }
    return true;
}
```

Modify `store()` to call `CbrFeatureValidator.validateStoreFeatures()` when schema is present.

Replace the local `validateQueryFeatures` method with calls to `CbrFeatureValidator.validateQueryFeatures()`.

- [ ] **Step 4: Run contract tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem`
Expected: all tests pass (existing + new)

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-testing/src/ memory-cbr-inmem/src/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#89): contract tests for structured fields + InMemory filter evaluation"
```

---

### Task 4: Qdrant backend — CbrPointBuilder, CbrQueryTranslator, CbrCollectionManager, QdrantCbrCaseMemoryStore

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrPointBuilder.java:77-85`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrQueryTranslator.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrCollectionManager.java:154-179`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/CbrPointBuilderTest.java`
- Modify: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/CbrQueryTranslatorTest.java`

**Interfaces:**
- Consumes: `CbrFilter`, `CbrQuery.filters()`, `CbrFeatureValidator`, `FeatureField` extensions (Tasks 1-2)
- Produces: Qdrant-backed structural filtering end-to-end

- [ ] **Step 1: Write CbrPointBuilder structured serialization tests**

Add to `CbrPointBuilderTest.java` — test that `List<String>`, `Map<String, Object>`, and `List<Map<String, Object>>` feature values produce correct Qdrant payload values (list, struct, list-of-struct respectively). Verify the `_features_json` blob round-trips correctly.

- [ ] **Step 2: Implement CbrPointBuilder structured serialization**

In `CbrPointBuilder.buildPoint()`, expand the feature serialization loop (line 77-85) to handle new types:

```java
} else if (val instanceof List<?> list) {
    payload.put(key, toListValue(list));
} else if (val instanceof Map<?,?> map) {
    payload.put(key, toStructValue(map));
}
```

Add helper methods:

```java
private static Value toListValue(List<?> list) {
    List<Value> values = new java.util.ArrayList<>(list.size());
    for (Object elem : list) {
        if (elem instanceof String s) values.add(ValueFactory.value(s));
        else if (elem instanceof Number n) values.add(ValueFactory.value(n.doubleValue()));
        else if (elem instanceof Map<?,?> map) values.add(toStructValue(map));
        else throw new IllegalArgumentException("Unsupported list element type: " + elem.getClass());
    }
    return ValueFactory.list(values);
}

private static Value toStructValue(Map<?,?> map) {
    Map<String, Value> struct = new java.util.HashMap<>();
    for (var entry : map.entrySet()) {
        String k = String.valueOf(entry.getKey());
        Object v = entry.getValue();
        if (v instanceof String s) struct.put(k, ValueFactory.value(s));
        else if (v instanceof Number n) struct.put(k, ValueFactory.value(n.doubleValue()));
        else if (v instanceof List<?> list) struct.put(k, toListValue(list));
        else if (v instanceof Map<?,?> m) struct.put(k, toStructValue(m));
        else throw new IllegalArgumentException("Unsupported value type: " + v.getClass());
    }
    return ValueFactory.value(struct);
}
```

- [ ] **Step 3: Run CbrPointBuilder tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant -Dtest=CbrPointBuilderTest`
Expected: all pass

- [ ] **Step 4: Write CbrQueryTranslator structural filter tests**

Add to `CbrQueryTranslatorTest.java` — tests for `applyStructuralFilters()` with each CbrFilter variant and verify the correct Qdrant conditions are generated. Test Contains → matchKeyword, ContainsAll → multiple must matchKeyword, ContainsAny → matchKeywords, HasMatch on ObjectList → nested(), HasMatch on NestedObject → dot-notation.

- [ ] **Step 5: Implement CbrQueryTranslator structural filters**

Add `applyStructuralFilters()` method and update switch sites:

```java
static Filter applyStructuralFilters(Filter baseFilter,
                                      Map<String, CbrFilter> filters,
                                      CbrFeatureSchema schema) {
    if (filters.isEmpty()) return baseFilter;
    CbrFeatureValidator.validateFilters(filters, schema);

    Filter.Builder builder = baseFilter.toBuilder();
    for (var entry : filters.entrySet()) {
        String payloadKey = "f_" + entry.getKey();
        CbrFilter filter = entry.getValue();
        FeatureField field = findField(schema, entry.getKey());

        switch (filter) {
            case CbrFilter.Contains c ->
                builder.addMust(ConditionFactory.matchKeyword(payloadKey, c.value()));
            case CbrFilter.ContainsAll ca ->
                ca.values().forEach(v ->
                    builder.addMust(ConditionFactory.matchKeyword(payloadKey, v)));
            case CbrFilter.ContainsAny ca ->
                builder.addMust(ConditionFactory.matchKeywords(payloadKey, ca.values()));
            case CbrFilter.HasMatch hm -> {
                if (field instanceof FeatureField.ObjectList) {
                    Filter.Builder inner = Filter.newBuilder();
                    for (var sub : hm.subFields().entrySet()) {
                        addSubFieldCondition(inner, sub.getKey(), sub.getValue());
                    }
                    builder.addMust(ConditionFactory.nested(payloadKey, inner.build()));
                } else {
                    for (var sub : hm.subFields().entrySet()) {
                        addSubFieldCondition(builder, payloadKey + "." + sub.getKey(), sub.getValue());
                    }
                }
            }
        }
    }
    return builder.build();
}

private static void addSubFieldCondition(Filter.Builder builder, String key, Object value) {
    if (value instanceof String s) {
        builder.addMust(ConditionFactory.matchKeyword(key, s));
    } else if (value instanceof NumericRange range) {
        builder.addMust(ConditionFactory.range(key,
            Range.newBuilder().setGte(range.min()).setLte(range.max()).build()));
    } else if (value instanceof Number n) {
        builder.addMust(ConditionFactory.range(key,
            Range.newBuilder().setGte(n.doubleValue()).setLte(n.doubleValue()).build()));
    }
}
```

Update `toFilter()` switch to add structured field cases (throw `IllegalStateException` — unreachable after validation). Update `validateQueryFeatures()` to delegate to `CbrFeatureValidator.validateQueryFeatures()`.

- [ ] **Step 6: Implement CbrCollectionManager payload indexes**

Update `registerSchemaIndexes()` switch to handle new field types:

```java
case FeatureField.CategoricalList cl ->
    client.createPayloadIndexAsync(collection, payloadKey,
        PayloadSchemaType.Keyword, null, true, null, null).get();
case FeatureField.NestedObject no -> {
    for (FeatureField inner : no.innerFields()) {
        String innerKey = payloadKey + "." + inner.name();
        PayloadSchemaType type = innerPayloadType(inner);
        client.createPayloadIndexAsync(collection, innerKey,
            type, null, true, null, null).get();
    }
}
case FeatureField.ObjectList ol -> {
    for (FeatureField inner : ol.innerFields()) {
        String innerKey = payloadKey + "[]." + inner.name();
        PayloadSchemaType type = innerPayloadType(inner);
        client.createPayloadIndexAsync(collection, innerKey,
            type, null, true, null, null).get();
    }
}
```

Add helper:
```java
private static PayloadSchemaType innerPayloadType(FeatureField field) {
    return switch (field) {
        case FeatureField.Categorical c -> PayloadSchemaType.Keyword;
        case FeatureField.Numeric n -> PayloadSchemaType.Float;
        case FeatureField.Text t -> PayloadSchemaType.Keyword;
        default -> throw new IllegalStateException("Unexpected inner field type");
    };
}
```

- [ ] **Step 7: Wire filters in QdrantCbrCaseMemoryStore.retrieveSimilar()**

In `retrieveSimilar()`, after building the identity filter and before the mode dispatch, add:

```java
if (!query.filters().isEmpty()) {
    if (schema == null) {
        throw new IllegalStateException(
            "Cannot apply structural filters: no schema registered for caseType '"
            + query.caseType() + "'");
    }
    filter = CbrQueryTranslator.applyStructuralFilters(filter, query.filters(), schema);
}
```

Also add store-time validation in `store()`:
```java
CbrFeatureSchema schema = schemas.get(caseType);
if (schema != null) {
    CbrFeatureValidator.validateStoreFeatures(cbrCase.features(), schema);
}
```

Update `buildTextOverrides()` switch to handle new field types (no-op cases: `-> {}`).

- [ ] **Step 8: Run all Qdrant tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant`
Expected: all pass (unit tests + integration tests if Qdrant testcontainer available)

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-qdrant/src/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#89): Qdrant structured field serialization, filter translation, payload indexes"
```

---

### Task 5: Full build verification + deferred GitHub issues

**Files:**
- None modified (verification only)

**Interfaces:**
- Consumes: all prior tasks

- [ ] **Step 1: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS — all modules compile, all tests pass

- [ ] **Step 2: Check for diagnostics**

Run `ide_diagnostics` on key modified files to verify no warnings or errors.

- [ ] **Step 3: File deferred GitHub issues**

Create the following issues on `casehubio/neocortex`:

1. **NumericList support** — `List<Number>` field type for numeric sequences. No concrete use case yet; game phases are categoricals, moment sequences are objects, trajectories are keyed maps.
2. **NotContains / NotContainsAny filter variants** — negation filters for CategoricalList fields.
3. **Compound same-field filters (AllOf)** — `Map<String, CbrFilter>` limits to one filter per field. `AllOf(List<CbrFilter>)` wrapper enables multiple independent predicates on the same ObjectList.
4. **Graded similarity over structured fields** — domain-specific scoring for lists/nested objects via custom LocalSimilarityFunction patterns.

Label each with `enhancement` and `complexity: Low`.

- [ ] **Step 4: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex commit --allow-empty -m "chore(#89): deferred items filed as issues"
```

---

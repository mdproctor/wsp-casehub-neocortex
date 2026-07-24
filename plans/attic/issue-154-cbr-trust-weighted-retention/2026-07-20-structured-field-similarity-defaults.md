# Structured Field Similarity Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #169 — docs: LocalSimilarityFunction patterns + built-in defaults for structured CBR fields
**Issue group:** #169

**Goal:** Replace the `return 0.0` dead branches and `continue` guard in `CbrSimilarityScorer` with
built-in type defaults for all four structured field types, and update `CbrFeatureValidator` to accept
structured fields in query features.

**Architecture:** Four private scoring methods added to `CbrSimilarityScorer` (Jaccard, nearest-neighbor,
recursive, greedy best-match). The `continue` guard that skips structured fields without overrides is
removed from both `scoreDetailed()` overloads. `CbrFeatureValidator.validateQueryFeatures()` is updated
to accept structured field types with the same type validation as `validateStoreFeatures()`. All changes
are in `memory-api` — pure Java, Tier 1, zero external dependencies.

**Tech Stack:** Java 21, JUnit 5, AssertJ

## Global Constraints

- Pure Java, Tier 1 — zero external dependencies
- All code in `memory-api` module
- `CbrSimilarityScorer` is a stateless utility class with only `static` methods
- Inner fields (NestedObject/ObjectList) use type defaults only — `SimilaritySpec` not supported
  on inner fields (enforced by `validateFlatFields`)
- Outer-level caller overrides are NOT propagated to inner field scoring

---

### Task 1: CbrFeatureValidator — accept structured fields in query features

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFeatureValidator.java` — `validateQueryFeatures()` method
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrFeatureValidatorTest.java` — three rejection tests become acceptance tests
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java` — rejection contract test becomes acceptance test

**Interfaces:**
- Consumes: existing `CbrFeatureValidator`, `CbrFeatureSchema`, `FeatureField`, `FeatureValue` types
- Produces: `validateQueryFeatures()` now accepts `CategoricalList` (requires `StringListVal`), `NumericList` (requires `NumberListVal` + range validation), `NestedObject` (requires `StructVal` + inner validation), `ObjectList` (requires `StructListVal` + inner validation)

- [ ] **Step 1: Convert rejection tests to acceptance tests in CbrFeatureValidatorTest**

Replace the three `validateQueryFeatures_rejectsXxx` tests with acceptance tests that verify structured
fields are accepted with correct types, and add wrong-type rejection tests:

```java
// Replace validateQueryFeatures_rejectsStructuredFieldInFeatures with:
@Test void validateQueryFeatures_acceptsCategoricalListFeature() {
    CbrFeatureValidator.validateQueryFeatures(
        Map.of("phases", stringList("A", "B")), SCHEMA);
}

@Test void validateQueryFeatures_categoricalListRejectsWrongType() {
    assertThatThrownBy(() -> CbrFeatureValidator.validateQueryFeatures(
        Map.of("phases", string("not_a_list")), SCHEMA))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("CategoricalList")
        .hasMessageContaining("StringListVal");
}

// Replace validateQueryFeatures_rejectsNestedObjectInFeatures with:
@Test void validateQueryFeatures_acceptsNestedObjectFeature() {
    CbrFeatureValidator.validateQueryFeatures(
        Map.of("economy", struct(Map.of("minute_3", number(50), "tier", string("HIGH")))), SCHEMA);
}

@Test void validateQueryFeatures_nestedObjectRejectsWrongType() {
    assertThatThrownBy(() -> CbrFeatureValidator.validateQueryFeatures(
        Map.of("economy", string("not_a_struct")), SCHEMA))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("NestedObject")
        .hasMessageContaining("StructVal");
}

// Replace validateQueryFeatures_rejectsObjectListInFeatures with:
@Test void validateQueryFeatures_acceptsObjectListFeature() {
    CbrFeatureValidator.validateQueryFeatures(
        Map.of("moments", structList(Map.of("type", string("KILL"), "minute", number(15)))), SCHEMA);
}

@Test void validateQueryFeatures_objectListRejectsWrongType() {
    assertThatThrownBy(() -> CbrFeatureValidator.validateQueryFeatures(
        Map.of("moments", string("not_a_list")), SCHEMA))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("ObjectList")
        .hasMessageContaining("StructListVal");
}

// Add NumericList tests (not previously tested since it was rejected outright):
@Test void validateQueryFeatures_acceptsNumericListFeature() {
    // Need a schema with NumericList — SCHEMA doesn't have one
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numericList("stats", 0, 100));
    CbrFeatureValidator.validateQueryFeatures(
        Map.of("stats", numberList(10.0, 50.0, 90.0)), schema);
}

@Test void validateQueryFeatures_numericListRejectsWrongType() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numericList("stats", 0, 100));
    assertThatThrownBy(() -> CbrFeatureValidator.validateQueryFeatures(
        Map.of("stats", string("not_a_list")), schema))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("NumericList")
        .hasMessageContaining("NumberListVal");
}

@Test void validateQueryFeatures_numericListRejectsOutOfRange() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numericList("stats", 0, 100));
    assertThatThrownBy(() -> CbrFeatureValidator.validateQueryFeatures(
        Map.of("stats", numberList(50.0, 150.0)), schema))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("outside range");
}
```

- [ ] **Step 2: Run tests to verify failures**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrFeatureValidatorTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: 8 new tests fail (acceptance tests hit the "must be queried via filters" rejection)

- [ ] **Step 3: Update validateQueryFeatures to accept structured fields**

In `CbrFeatureValidator.validateQueryFeatures()`, replace the four `throw` branches with
type-validation logic matching `validateStoreFeatures()`:

```java
case FeatureField.CategoricalList cl -> {
    if (!(value instanceof FeatureValue.StringListVal)) {
        throw new IllegalArgumentException(
                "CategoricalList field '" + entry.getKey() + "' requires StringListVal, got: "
                + value.getClass().getSimpleName());
    }
}
case FeatureField.NumericList nl -> {
    if (!(value instanceof FeatureValue.NumberListVal nlv)) {
        throw new IllegalArgumentException(
                "NumericList field '" + entry.getKey() + "' requires NumberListVal, got: "
                + value.getClass().getSimpleName());
    }
    for (Double d : nlv.values()) {
        if (d < nl.min() || d > nl.max()) {
            throw new IllegalArgumentException(
                    "NumericList field '" + entry.getKey() + "' element " + d
                    + " outside range [" + nl.min() + ", " + nl.max() + "]");
        }
    }
}
case FeatureField.NestedObject no -> {
    if (!(value instanceof FeatureValue.StructVal sv)) {
        throw new IllegalArgumentException(
                "NestedObject field '" + entry.getKey() + "' requires StructVal, got: "
                + value.getClass().getSimpleName());
    }
    validateInnerValues(entry.getKey(), sv.fields(), no.innerFields());
}
case FeatureField.ObjectList ol -> {
    if (!(value instanceof FeatureValue.StructListVal sl)) {
        throw new IllegalArgumentException(
                "ObjectList field '" + entry.getKey() + "' requires StructListVal, got: "
                + value.getClass().getSimpleName());
    }
    for (Map<String, FeatureValue> item : sl.items()) {
        validateInnerValues(entry.getKey(), item, ol.innerFields());
    }
}
```

- [ ] **Step 4: Update contract test**

In `CbrCaseMemoryStoreContractTest`, replace `structuredFields_validation_structuredFieldInFeatures`
(line ~1030) — it currently asserts rejection. Change it to verify acceptance and scoring:

```java
@Test
void structuredFields_queryFeatures_categoricalListParticipatesInScoring() {
    registerStructuredSchema();
    storeGameCase("game1", Map.of("posture", string("ALL_IN"),
                                  "phases", stringList("EARLY", "MID", "LATE")), "g1");
    storeGameCase("game2", Map.of("posture", string("DEFENSIVE"),
                                  "phases", stringList("TURTLE", "LATE")), "g2");

    var q = CbrQuery.of(TENANT, CBR, Path.root(), "game",
                        Map.of("phases", stringList("EARLY", "MID")), 10);
    var results = store().retrieveSimilar(q, FeatureVectorCbrCase.class);
    assertThat(results).isNotEmpty();
    // game1 has better Jaccard overlap with query (EARLY, MID both present)
    assertThat(results.getFirst().cbrCase().problem()).isEqualTo("game1");
}
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api,memory-testing`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFeatureValidator.java memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrFeatureValidatorTest.java memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#169): accept structured fields in query features — CbrFeatureValidator"
```

---

### Task 2: CbrSimilarityScorer — remove continue guard + add four type defaults

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java` — remove `continue` guard (lines 69–73 and 104–108), add four private methods, update four switch branches, update class Javadoc
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorerTest.java` — tests for all four defaults

**Interfaces:**
- Consumes: `FeatureField.CategoricalList`, `FeatureField.NumericList`, `FeatureField.NestedObject`, `FeatureField.ObjectList`, `FeatureValue.StringListVal`, `FeatureValue.NumberListVal`, `FeatureValue.StructVal`, `FeatureValue.StructListVal`
- Produces: scoring for all four types via existing `score()` / `scoreDetailed()` public API (no new public methods)

#### Part A: CategoricalList — Jaccard

- [ ] **Step 1: Write failing tests for CategoricalList Jaccard**

```java
// --- CategoricalList Jaccard tests ---
static final CbrFeatureSchema CL_SCHEMA = CbrFeatureSchema.of("test",
    FeatureField.categoricalList("tags"));

@Test
void categoricalList_identicalSets() {
    double sim = CbrSimilarityScorer.score(
        Map.of("tags", stringList("A", "B", "C")),
        Map.of("tags", stringList("A", "B", "C")),
        Map.of(), CL_SCHEMA);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void categoricalList_partialOverlap() {
    // intersection={A,B}, union={A,B,C,D} → 2/4 = 0.5
    double sim = CbrSimilarityScorer.score(
        Map.of("tags", stringList("A", "B", "C")),
        Map.of("tags", stringList("A", "B", "D")),
        Map.of(), CL_SCHEMA);
    assertThat(sim).isCloseTo(0.5, offset(1e-9));
}

@Test
void categoricalList_noOverlap() {
    double sim = CbrSimilarityScorer.score(
        Map.of("tags", stringList("A", "B")),
        Map.of("tags", stringList("C", "D")),
        Map.of(), CL_SCHEMA);
    assertThat(sim).isCloseTo(0.0, offset(1e-9));
}

@Test
void categoricalList_bothEmpty() {
    double sim = CbrSimilarityScorer.score(
        Map.of("tags", stringList()),
        Map.of("tags", stringList()),
        Map.of(), CL_SCHEMA);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void categoricalList_queryEmpty_caseNonEmpty() {
    double sim = CbrSimilarityScorer.score(
        Map.of("tags", stringList()),
        Map.of("tags", stringList("A", "B")),
        Map.of(), CL_SCHEMA);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void categoricalList_queryNonEmpty_caseEmpty() {
    double sim = CbrSimilarityScorer.score(
        Map.of("tags", stringList("A")),
        Map.of("tags", stringList()),
        Map.of(), CL_SCHEMA);
    assertThat(sim).isCloseTo(0.0, offset(1e-9));
}

@Test
void categoricalList_duplicatesIgnored() {
    // Treated as sets: {A,B} vs {A,B} → 1.0
    double sim = CbrSimilarityScorer.score(
        Map.of("tags", stringList("A", "A", "B")),
        Map.of("tags", stringList("A", "B", "B")),
        Map.of(), CL_SCHEMA);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void categoricalList_overrideStillTrumps() {
    LocalSimilarityFunction always1 = (q, c) -> 1.0;
    double sim = CbrSimilarityScorer.score(
        Map.of("tags", stringList("A")),
        Map.of("tags", stringList("Z")),
        Map.of(), CL_SCHEMA, Map.of("tags", always1));
    assertThat(sim).isEqualTo(1.0);
}
```

- [ ] **Step 2: Run tests to verify failures**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrSimilarityScorerTest`
Expected: new tests fail (structured fields still skipped by `continue` guard or return 0.0)

- [ ] **Step 3: Remove `continue` guard from both `scoreDetailed()` overloads**

In `CbrSimilarityScorer.java`, delete lines 69–73 (first overload) and the identical guard in
the second overload (~lines 104–108):

```java
// DELETE these lines from BOTH overloads:
            LocalSimilarityFunction override = overrides.get(entry.getKey());
            if (override == null
                && (field instanceof FeatureField.CategoricalList
                    || field instanceof FeatureField.NumericList
                    || field instanceof FeatureField.NestedObject
                    || field instanceof FeatureField.ObjectList)) {continue;}
```

Note: the `override` variable is still needed later in `localSimilarity()`. It's already
obtained there independently, so removing these lines does not break anything — the variable
was declared here only for the guard check.

- [ ] **Step 4: Add `categoricalListSimilarity` method and update switch branch**

Add private method:

```java
private static double categoricalListSimilarity(FeatureValue queryVal, FeatureValue caseVal) {
    if (!(queryVal instanceof FeatureValue.StringListVal qs)
        || !(caseVal instanceof FeatureValue.StringListVal cs)) {return 0.0;}
    if (qs.values().isEmpty()) {return 1.0;}
    if (cs.values().isEmpty()) {return 0.0;}
    Set<String> qSet = new HashSet<>(qs.values());
    Set<String> cSet = new HashSet<>(cs.values());
    Set<String> union = new HashSet<>(qSet);
    union.addAll(cSet);
    if (union.isEmpty()) {return 1.0;}
    Set<String> intersection = new HashSet<>(qSet);
    intersection.retainAll(cSet);
    return (double) intersection.size() / union.size();
}
```

Update switch branch in `localSimilarity()`:
```java
case FeatureField.CategoricalList cl -> categoricalListSimilarity(queryVal, caseVal);
```

- [ ] **Step 5: Run CategoricalList tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrSimilarityScorerTest`
Expected: CategoricalList tests pass (NumericList/NestedObject/ObjectList tests still fail)

#### Part B: NumericList — Average nearest-neighbor

- [ ] **Step 6: Write failing tests for NumericList**

```java
// --- NumericList nearest-neighbor tests ---
static final CbrFeatureSchema NL_SCHEMA = CbrFeatureSchema.of("test",
    FeatureField.numericList("stats", 0.0, 100.0));

@Test
void numericList_identicalValues() {
    double sim = CbrSimilarityScorer.score(
        Map.of("stats", numberList(10.0, 50.0, 90.0)),
        Map.of("stats", numberList(10.0, 50.0, 90.0)),
        Map.of(), NL_SCHEMA);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void numericList_nearestNeighborDecay() {
    // query=[50], case=[70]. nearest distance=20, range=100, sim = 1-20/100 = 0.8
    double sim = CbrSimilarityScorer.score(
        Map.of("stats", numberList(50.0)),
        Map.of("stats", numberList(70.0)),
        Map.of(), NL_SCHEMA);
    assertThat(sim).isCloseTo(0.8, offset(1e-9));
}

@Test
void numericList_multipleQueryElements() {
    // query=[20, 80], case=[25, 75]
    // q=20 nearest c=25: dist=5, sim=0.95
    // q=80 nearest c=75: dist=5, sim=0.95
    // avg = 0.95
    double sim = CbrSimilarityScorer.score(
        Map.of("stats", numberList(20.0, 80.0)),
        Map.of("stats", numberList(25.0, 75.0)),
        Map.of(), NL_SCHEMA);
    assertThat(sim).isCloseTo(0.95, offset(1e-9));
}

@Test
void numericList_caseSizeSmaller() {
    // query=[10, 50, 90], case=[50]
    // q=10 nearest c=50: dist=40, sim=0.6
    // q=50 nearest c=50: dist=0, sim=1.0
    // q=90 nearest c=50: dist=40, sim=0.6
    // avg = 2.2/3 ≈ 0.733
    double sim = CbrSimilarityScorer.score(
        Map.of("stats", numberList(10.0, 50.0, 90.0)),
        Map.of("stats", numberList(50.0)),
        Map.of(), NL_SCHEMA);
    assertThat(sim).isCloseTo(2.2 / 3.0, offset(1e-9));
}

@Test
void numericList_bothEmpty() {
    double sim = CbrSimilarityScorer.score(
        Map.of("stats", numberList()),
        Map.of("stats", numberList()),
        Map.of(), NL_SCHEMA);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void numericList_queryEmpty() {
    double sim = CbrSimilarityScorer.score(
        Map.of("stats", numberList()),
        Map.of("stats", numberList(50.0)),
        Map.of(), NL_SCHEMA);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void numericList_caseEmpty() {
    double sim = CbrSimilarityScorer.score(
        Map.of("stats", numberList(50.0)),
        Map.of("stats", numberList()),
        Map.of(), NL_SCHEMA);
    assertThat(sim).isCloseTo(0.0, offset(1e-9));
}

@Test
void numericList_zeroRange_exactMatch() {
    var schema = CbrFeatureSchema.of("test", FeatureField.numericList("x", 5.0, 5.0));
    double sim = CbrSimilarityScorer.score(
        Map.of("x", numberList(5.0)),
        Map.of("x", numberList(5.0)),
        Map.of(), schema);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void numericList_zeroRange_mismatch() {
    var schema = CbrFeatureSchema.of("test", FeatureField.numericList("x", 5.0, 5.0));
    double sim = CbrSimilarityScorer.score(
        Map.of("x", numberList(5.0)),
        Map.of("x", numberList(6.0)),
        Map.of(), schema);
    assertThat(sim).isEqualTo(0.0);
}
```

- [ ] **Step 7: Add `numericListSimilarity` method and update switch branch**

```java
private static double numericListSimilarity(FeatureField.NumericList nl,
                                            FeatureValue queryVal, FeatureValue caseVal) {
    if (!(queryVal instanceof FeatureValue.NumberListVal qs)
        || !(caseVal instanceof FeatureValue.NumberListVal cs)) {return 0.0;}
    if (qs.values().isEmpty()) {return 1.0;}
    if (cs.values().isEmpty()) {return 0.0;}
    double range = nl.max() - nl.min();
    double sum = 0.0;
    for (double q : qs.values()) {
        double bestSim = 0.0;
        for (double c : cs.values()) {
            double sim;
            if (range <= 0) {
                sim = q == c ? 1.0 : 0.0;
            } else {
                sim = Math.max(0.0, 1.0 - Math.abs(q - c) / range);
            }
            if (sim > bestSim) {bestSim = sim;}
        }
        sum += bestSim;
    }
    return sum / qs.values().size();
}
```

Update switch branch:
```java
case FeatureField.NumericList nl -> numericListSimilarity(nl, queryVal, caseVal);
```

- [ ] **Step 8: Run tests to verify NumericList passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrSimilarityScorerTest`

#### Part C: NestedObject — Recursive scoring

- [ ] **Step 9: Write failing tests for NestedObject**

```java
// --- NestedObject recursive scoring tests ---
static final CbrFeatureSchema NO_SCHEMA = CbrFeatureSchema.of("test",
    FeatureField.nestedObject("economy",
        FeatureField.numeric("gold", 0, 100),
        FeatureField.categorical("tier")));

@Test
void nestedObject_identicalValues() {
    double sim = CbrSimilarityScorer.score(
        Map.of("economy", struct(Map.of("gold", number(50), "tier", string("HIGH")))),
        Map.of("economy", struct(Map.of("gold", number(50), "tier", string("HIGH")))),
        Map.of(), NO_SCHEMA);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void nestedObject_partialMatch() {
    // gold: |50-70|/100 = 0.2, sim=0.8. tier: mismatch, sim=0.0.
    // avg = (0.8+0.0)/2 = 0.4
    double sim = CbrSimilarityScorer.score(
        Map.of("economy", struct(Map.of("gold", number(50), "tier", string("HIGH")))),
        Map.of("economy", struct(Map.of("gold", number(70), "tier", string("LOW")))),
        Map.of(), NO_SCHEMA);
    assertThat(sim).isCloseTo(0.4, offset(1e-9));
}

@Test
void nestedObject_missingInnerFieldInCase() {
    // query has gold+tier, case only has gold → tier scores 0.0
    // gold: exact match 1.0, tier: missing → 0.0. avg = 0.5
    double sim = CbrSimilarityScorer.score(
        Map.of("economy", struct(Map.of("gold", number(50), "tier", string("HIGH")))),
        Map.of("economy", struct(Map.of("gold", number(50)))),
        Map.of(), NO_SCHEMA);
    assertThat(sim).isCloseTo(0.5, offset(1e-9));
}

@Test
void nestedObject_emptyQueryStruct() {
    double sim = CbrSimilarityScorer.score(
        Map.of("economy", struct(Map.of())),
        Map.of("economy", struct(Map.of("gold", number(50)))),
        Map.of(), NO_SCHEMA);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void nestedObject_outerOverrideNotPropagated() {
    // An override named "gold" at the outer level should NOT affect inner "gold"
    LocalSimilarityFunction always1 = (q, c) -> 1.0;
    double sim = CbrSimilarityScorer.score(
        Map.of("economy", struct(Map.of("gold", number(0), "tier", string("A")))),
        Map.of("economy", struct(Map.of("gold", number(100), "tier", string("B")))),
        Map.of(), NO_SCHEMA, Map.of("gold", always1));
    // gold inner: 0→100, range 100, sim=0.0. tier: A≠B, sim=0.0. avg=0.0
    // If override leaked, gold would be 1.0 → avg=0.5
    assertThat(sim).isCloseTo(0.0, offset(1e-9));
}
```

- [ ] **Step 10: Add `nestedObjectSimilarity` method and update switch branch**

```java
private static double nestedObjectSimilarity(FeatureField.NestedObject no,
                                             FeatureValue queryVal, FeatureValue caseVal) {
    if (!(queryVal instanceof FeatureValue.StructVal qs)
        || !(caseVal instanceof FeatureValue.StructVal cs)) {return 0.0;}
    if (qs.fields().isEmpty()) {return 1.0;}
    return scoreInnerFields(no.innerFields(), qs.fields(), cs.fields());
}
```

Update switch branch:
```java
case FeatureField.NestedObject no -> nestedObjectSimilarity(no, queryVal, caseVal);
```

- [ ] **Step 11: Run tests to verify NestedObject passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrSimilarityScorerTest`

#### Part D: ObjectList — Greedy best-match

- [ ] **Step 12: Write failing tests for ObjectList**

```java
// --- ObjectList greedy best-match tests ---
static final CbrFeatureSchema OL_SCHEMA = CbrFeatureSchema.of("test",
    FeatureField.objectList("events",
        FeatureField.categorical("type"),
        FeatureField.numeric("minute", 0, 90)));

@Test
void objectList_identicalLists() {
    double sim = CbrSimilarityScorer.score(
        Map.of("events", structList(
            Map.of("type", string("KILL"), "minute", number(15)),
            Map.of("type", string("DEATH"), "minute", number(30)))),
        Map.of("events", structList(
            Map.of("type", string("KILL"), "minute", number(15)),
            Map.of("type", string("DEATH"), "minute", number(30)))),
        Map.of(), OL_SCHEMA);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void objectList_bestMatchWithReuse() {
    // query has 2 objects, case has 1. Each query object matches against the same case object.
    // query[0]={KILL,15} vs case[0]={KILL,20}: type=1.0, minute=|15-20|/90≈0.944 → avg≈0.972
    // query[1]={DEATH,30} vs case[0]={KILL,20}: type=0.0, minute=|30-20|/90≈0.889 → avg≈0.444
    // result = (0.972 + 0.444)/2 ≈ 0.708
    double sim = CbrSimilarityScorer.score(
        Map.of("events", structList(
            Map.of("type", string("KILL"), "minute", number(15)),
            Map.of("type", string("DEATH"), "minute", number(30)))),
        Map.of("events", structList(
            Map.of("type", string("KILL"), "minute", number(20)))),
        Map.of(), OL_SCHEMA);
    double q0Best = (1.0 + (1.0 - 5.0/90.0)) / 2.0;
    double q1Best = (0.0 + (1.0 - 10.0/90.0)) / 2.0;
    assertThat(sim).isCloseTo((q0Best + q1Best) / 2.0, offset(1e-9));
}

@Test
void objectList_bothEmpty() {
    double sim = CbrSimilarityScorer.score(
        Map.of("events", structList(List.of())),
        Map.of("events", structList(List.of())),
        Map.of(), OL_SCHEMA);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void objectList_queryEmpty() {
    double sim = CbrSimilarityScorer.score(
        Map.of("events", structList(List.of())),
        Map.of("events", structList(Map.of("type", string("KILL"), "minute", number(15)))),
        Map.of(), OL_SCHEMA);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void objectList_caseEmpty() {
    double sim = CbrSimilarityScorer.score(
        Map.of("events", structList(Map.of("type", string("KILL"), "minute", number(15)))),
        Map.of("events", structList(List.of())),
        Map.of(), OL_SCHEMA);
    assertThat(sim).isCloseTo(0.0, offset(1e-9));
}
```

- [ ] **Step 13: Add `objectListSimilarity` method and update switch branch**

```java
private static double objectListSimilarity(FeatureField.ObjectList ol,
                                           FeatureValue queryVal, FeatureValue caseVal) {
    if (!(queryVal instanceof FeatureValue.StructListVal qs)
        || !(caseVal instanceof FeatureValue.StructListVal cs)) {return 0.0;}
    if (qs.items().isEmpty()) {return 1.0;}
    if (cs.items().isEmpty()) {return 0.0;}
    double sum = 0.0;
    for (Map<String, FeatureValue> qObj : qs.items()) {
        double bestScore = 0.0;
        for (Map<String, FeatureValue> cObj : cs.items()) {
            double objScore = scoreInnerFields(ol.innerFields(), qObj, cObj);
            if (objScore > bestScore) {bestScore = objScore;}
        }
        sum += bestScore;
    }
    return sum / qs.items().size();
}

private static double scoreInnerFields(List<FeatureField> innerFields,
                                       Map<String, FeatureValue> queryObj,
                                       Map<String, FeatureValue> caseObj) {
    double sum = 0.0;
    int count = 0;
    for (FeatureField inner : innerFields) {
        FeatureValue qv = queryObj.get(inner.name());
        if (qv == null) {continue;}
        FeatureValue cv = caseObj.get(inner.name());
        double sim = cv == null ? 0.0 : localSimilarity(inner, qv, cv, Map.of());
        sum += sim;
        count++;
    }
    return count == 0 ? 1.0 : sum / count;
}
```

Update switch branch:
```java
case FeatureField.ObjectList ol -> objectListSimilarity(ol, queryVal, caseVal);
```

- [ ] **Step 14: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrSimilarityScorerTest`
Expected: all tests pass

#### Part E: Javadoc + cleanup

- [ ] **Step 15: Update class-level Javadoc**

Update the `CbrSimilarityScorer` class Javadoc to list all seven type defaults:

```java
/**
 * Computes CBR similarity scores using per-field local similarity functions
 * and configurable per-field weights.
 *
 * <p>Local similarity functions use three-level precedence:
 * <ol>
 *   <li>Caller-provided override via {@code Map<String, LocalSimilarityFunction>}</li>
 *   <li>Field-attached {@link SimilaritySpec} (if present)</li>
 *   <li>Type default (see below)</li>
 * </ol>
 *
 * <p>Type defaults:
 * <ul>
 *   <li>{@link FeatureField.Categorical} — exact match (1.0 or 0.0)</li>
 *   <li>{@link FeatureField.Numeric} — linear decay: {@code 1.0 - |query - case| / range}</li>
 *   <li>{@link FeatureField.Text} — exact match (1.0 or 0.0)</li>
 *   <li>{@link FeatureField.CategoricalList} — Jaccard similarity on string sets</li>
 *   <li>{@link FeatureField.NumericList} — average nearest-neighbor with linear decay</li>
 *   <li>{@link FeatureField.NestedObject} — recursive scoring with uniform weights</li>
 *   <li>{@link FeatureField.ObjectList} — greedy best-match with recursive inner scoring</li>
 * </ul>
 *
 * <p>Pure Java, Tier 1 — zero external dependencies.
 */
```

- [ ] **Step 16: Run full module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api`
Expected: all tests pass

- [ ] **Step 17: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorerTest.java
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#169): built-in type defaults for structured field similarity — Jaccard, nearest-neighbor, recursive, greedy best-match"
```

---

### Task 3: Integration verification — full build

**Files:**
- No new files — verification only

- [ ] **Step 1: Run full project build with tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS — all modules pass, including:
- `memory-testing` contract tests (the updated acceptance test)
- `memory-cbr-inmem` (InMemory store exercises scorer)
- Any downstream modules that depend on `memory-api`

- [ ] **Step 2: Run IntelliJ diagnostics on changed files**

Use `ide_diagnostics` on:
- `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java`
- `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFeatureValidator.java`

Expected: no errors or warnings

- [ ] **Step 3: Commit if any fixes were needed**

Only if Step 1 or 2 surfaced issues requiring fixes.

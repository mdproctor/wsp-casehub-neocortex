# CBR Similarity Functions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #107 — categorical similarity tables
**Issue group:** #107, #108

**Goal:** Add schema-attached similarity configuration via `SimilaritySpec` sealed interface, enabling graduated categorical similarity and configurable numeric decay functions.

**Architecture:** A new `SimilaritySpec` sealed interface (pure data records) attaches optional similarity configuration to `FeatureField.Categorical` and `FeatureField.Numeric`. The scorer resolves specs via pattern matching with a three-level precedence chain: caller override → field-attached spec → type default. `FeatureField` becomes sealed for exhaustive dispatch everywhere.

**Tech Stack:** Java 21 sealed interfaces, records, pattern matching. Zero external deps (memory-api Tier 1).

## Global Constraints

- All changes in `memory-api` (Tier 1 — zero external dependencies, pure Java)
- `FeatureField` and `SimilaritySpec` are sealed interfaces — all switches must be exhaustive (no `default` branches)
- `SimilaritySpec` records are pure data — no lambdas, no CDI, no functional interfaces
- `Text` fields do NOT carry `SimilaritySpec` — semantic similarity uses caller overrides
- Numeric specs carry only shape parameters — scorer extracts `min`/`max` from the field
- Backward compatibility of existing constructors is preserved, but `FeatureField` gaining `sealed` is a deliberate breaking change at dispatch sites

---

### Task 1: SimilaritySpec sealed interface + CategoricalTableBuilder

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/SimilaritySpec.java`
- Create: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/SimilaritySpecTest.java`

**Interfaces:**
- Consumes: nothing (new standalone type)
- Produces: `SimilaritySpec` sealed interface with `CategoricalTable(Map<String, Map<String, Double>>)`, `GaussianDecay(double sigma)`, `StepDecay(double tolerance)`, `ExponentialDecay(double decayRate)`, and `static CategoricalTableBuilder categoricalTableBuilder()`

- [ ] **Step 1: Write failing tests for SimilaritySpec record validation**

```java
package io.casehub.neocortex.memory.cbr;

import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class SimilaritySpecTest {

    // --- GaussianDecay ---
    @Test
    void gaussianDecay_validSigma() {
        var g = new SimilaritySpec.GaussianDecay(0.5);
        assertThat(g.sigma()).isEqualTo(0.5);
    }

    @Test
    void gaussianDecay_zeroSigma_throws() {
        assertThatThrownBy(() -> new SimilaritySpec.GaussianDecay(0.0))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void gaussianDecay_negativeSigma_throws() {
        assertThatThrownBy(() -> new SimilaritySpec.GaussianDecay(-0.1))
            .isInstanceOf(IllegalArgumentException.class);
    }

    // --- StepDecay ---
    @Test
    void stepDecay_validTolerance() {
        var s = new SimilaritySpec.StepDecay(0.1);
        assertThat(s.tolerance()).isEqualTo(0.1);
    }

    @Test
    void stepDecay_toleranceZero_valid() {
        var s = new SimilaritySpec.StepDecay(0.0);
        assertThat(s.tolerance()).isEqualTo(0.0);
    }

    @Test
    void stepDecay_toleranceOne_valid() {
        var s = new SimilaritySpec.StepDecay(1.0);
        assertThat(s.tolerance()).isEqualTo(1.0);
    }

    @Test
    void stepDecay_negativeTolerance_throws() {
        assertThatThrownBy(() -> new SimilaritySpec.StepDecay(-0.1))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void stepDecay_toleranceAboveOne_throws() {
        assertThatThrownBy(() -> new SimilaritySpec.StepDecay(1.1))
            .isInstanceOf(IllegalArgumentException.class);
    }

    // --- ExponentialDecay ---
    @Test
    void exponentialDecay_validRate() {
        var e = new SimilaritySpec.ExponentialDecay(3.0);
        assertThat(e.decayRate()).isEqualTo(3.0);
    }

    @Test
    void exponentialDecay_zeroRate_throws() {
        assertThatThrownBy(() -> new SimilaritySpec.ExponentialDecay(0.0))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void exponentialDecay_negativeRate_throws() {
        assertThatThrownBy(() -> new SimilaritySpec.ExponentialDecay(-1.0))
            .isInstanceOf(IllegalArgumentException.class);
    }

    // --- CategoricalTable ---
    @Test
    void categoricalTable_symmetricLookup() {
        var table = new SimilaritySpec.CategoricalTable(
            Map.of("headache", Map.of("migraine", 0.8)));
        assertThat(table.similarities().get("headache").get("migraine")).isEqualTo(0.8);
        assertThat(table.similarities().get("migraine").get("headache")).isEqualTo(0.8);
    }

    @Test
    void categoricalTable_nullSimilarities_throws() {
        assertThatThrownBy(() -> new SimilaritySpec.CategoricalTable(null))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void categoricalTable_scoreOutOfRange_throws() {
        assertThatThrownBy(() -> new SimilaritySpec.CategoricalTable(
            Map.of("a", Map.of("b", 1.5))))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void categoricalTable_negativeScore_throws() {
        assertThatThrownBy(() -> new SimilaritySpec.CategoricalTable(
            Map.of("a", Map.of("b", -0.1))))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void categoricalTable_conflictingSymmetricEntries_throws() {
        assertThatThrownBy(() -> new SimilaritySpec.CategoricalTable(
            Map.of("a", Map.of("b", 0.8), "b", Map.of("a", 0.7))))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void categoricalTable_immutable() {
        var mutable = new java.util.HashMap<String, Map<String, Double>>();
        mutable.put("a", Map.of("b", 0.5));
        var table = new SimilaritySpec.CategoricalTable(mutable);
        mutable.put("c", Map.of("d", 0.9));
        assertThat(table.similarities()).doesNotContainKey("c");
    }

    @Test
    void categoricalTable_emptyTable_valid() {
        var table = new SimilaritySpec.CategoricalTable(Map.of());
        assertThat(table.similarities()).isEmpty();
    }

    // --- CategoricalTableBuilder ---
    @Test
    void builder_addAndBuild() {
        var table = SimilaritySpec.categoricalTableBuilder()
            .add("headache", "migraine", 0.8)
            .add("headache", "fracture", 0.1)
            .build();
        assertThat(table.similarities().get("headache").get("migraine")).isEqualTo(0.8);
        assertThat(table.similarities().get("migraine").get("headache")).isEqualTo(0.8);
        assertThat(table.similarities().get("headache").get("fracture")).isEqualTo(0.1);
    }

    @Test
    void builder_duplicatePair_throws() {
        assertThatThrownBy(() -> SimilaritySpec.categoricalTableBuilder()
            .add("a", "b", 0.8)
            .add("b", "a", 0.7))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void builder_samePairSameScore_throws() {
        assertThatThrownBy(() -> SimilaritySpec.categoricalTableBuilder()
            .add("a", "b", 0.8)
            .add("a", "b", 0.8))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void builder_selfPair_silentlyIgnored() {
        var table = SimilaritySpec.categoricalTableBuilder()
            .add("a", "a", 0.9)
            .build();
        assertThat(table.similarities()).isEmpty();
    }

    @Test
    void builder_scoreOutOfRange_throws() {
        assertThatThrownBy(() -> SimilaritySpec.categoricalTableBuilder()
            .add("a", "b", 1.5))
            .isInstanceOf(IllegalArgumentException.class);
    }

    // --- Value semantics ---
    @Test
    void gaussianDecay_equalsBySigma() {
        assertThat(new SimilaritySpec.GaussianDecay(0.3))
            .isEqualTo(new SimilaritySpec.GaussianDecay(0.3));
    }

    @Test
    void categoricalTable_equalsByContent() {
        var t1 = SimilaritySpec.categoricalTableBuilder().add("a", "b", 0.5).build();
        var t2 = SimilaritySpec.categoricalTableBuilder().add("a", "b", 0.5).build();
        assertThat(t1).isEqualTo(t2);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=SimilaritySpecTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: compilation failure — `SimilaritySpec` class does not exist

- [ ] **Step 3: Implement SimilaritySpec**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/SimilaritySpec.java`:

```java
package io.casehub.neocortex.memory.cbr;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;

public sealed interface SimilaritySpec {

    record CategoricalTable(Map<String, Map<String, Double>> similarities) implements SimilaritySpec {
        public CategoricalTable {
            Objects.requireNonNull(similarities, "similarities");
            similarities = mirrorAndValidate(similarities);
        }

        private static Map<String, Map<String, Double>> mirrorAndValidate(
                Map<String, Map<String, Double>> input) {
            Map<String, Map<String, Double>> result = new HashMap<>();
            Set<String> seen = new TreeSet<>();

            for (var outer : input.entrySet()) {
                for (var inner : outer.getValue().entrySet()) {
                    String a = outer.getKey();
                    String b = inner.getKey();
                    double score = inner.getValue();

                    if (score < 0.0 || score > 1.0) {
                        throw new IllegalArgumentException(
                            "Score for (" + a + ", " + b + ") must be in [0, 1], got: " + score);
                    }
                    if (a.equals(b)) continue;

                    String pairKey = a.compareTo(b) < 0 ? a + "\0" + b : b + "\0" + a;
                    if (seen.contains(pairKey)) {
                        double existing = result
                            .getOrDefault(a, Map.of()).getOrDefault(b,
                            result.getOrDefault(b, Map.of()).getOrDefault(a, Double.NaN));
                        if (existing != score) {
                            throw new IllegalArgumentException(
                                "Conflicting scores for (" + a + ", " + b + "): " + existing + " vs " + score);
                        }
                        continue;
                    }
                    seen.add(pairKey);

                    result.computeIfAbsent(a, k -> new HashMap<>()).put(b, score);
                    result.computeIfAbsent(b, k -> new HashMap<>()).put(a, score);
                }
            }

            Map<String, Map<String, Double>> immutable = new HashMap<>();
            for (var e : result.entrySet()) {
                immutable.put(e.getKey(), Collections.unmodifiableMap(e.getValue()));
            }
            return Collections.unmodifiableMap(immutable);
        }
    }

    record GaussianDecay(double sigma) implements SimilaritySpec {
        public GaussianDecay {
            if (sigma <= 0) throw new IllegalArgumentException("sigma must be > 0, got: " + sigma);
        }
    }

    record StepDecay(double tolerance) implements SimilaritySpec {
        public StepDecay {
            if (tolerance < 0 || tolerance > 1)
                throw new IllegalArgumentException("tolerance must be in [0, 1], got: " + tolerance);
        }
    }

    record ExponentialDecay(double decayRate) implements SimilaritySpec {
        public ExponentialDecay {
            if (decayRate <= 0) throw new IllegalArgumentException("decayRate must be > 0, got: " + decayRate);
        }
    }

    static CategoricalTableBuilder categoricalTableBuilder() {
        return new CategoricalTableBuilder();
    }

    final class CategoricalTableBuilder {
        private final Map<String, Map<String, Double>> entries = new HashMap<>();
        private final Set<String> pairKeys = new TreeSet<>();

        private CategoricalTableBuilder() {}

        public CategoricalTableBuilder add(String a, String b, double score) {
            Objects.requireNonNull(a, "a");
            Objects.requireNonNull(b, "b");
            if (score < 0.0 || score > 1.0) {
                throw new IllegalArgumentException(
                    "Score for (" + a + ", " + b + ") must be in [0, 1], got: " + score);
            }
            if (a.equals(b)) return this;

            String pairKey = a.compareTo(b) < 0 ? a + "\0" + b : b + "\0" + a;
            if (!pairKeys.add(pairKey)) {
                throw new IllegalArgumentException(
                    "Pair (" + a + ", " + b + ") already registered");
            }

            entries.computeIfAbsent(a, k -> new HashMap<>()).put(b, score);
            entries.computeIfAbsent(b, k -> new HashMap<>()).put(a, score);
            return this;
        }

        public CategoricalTable build() {
            Map<String, Map<String, Double>> immutable = new HashMap<>();
            for (var e : entries.entrySet()) {
                immutable.put(e.getKey(), Collections.unmodifiableMap(new HashMap<>(e.getValue())));
            }
            return new CategoricalTable(Collections.unmodifiableMap(immutable));
        }
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=SimilaritySpecTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: all PASS

- [ ] **Step 5: Commit**

```
feat(#107): SimilaritySpec sealed interface — CategoricalTable, GaussianDecay, StepDecay, ExponentialDecay
```

---

### Task 2: Seal FeatureField + add SimilaritySpec parameter

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/FeatureField.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/FeatureFieldTest.java`

**Interfaces:**
- Consumes: `SimilaritySpec` from Task 1
- Produces: `FeatureField` sealed with `permits Categorical, Numeric, Text`. `Categorical(String name, SimilaritySpec similaritySpec)` and `Numeric(String name, double min, double max, SimilaritySpec similaritySpec)` with backward-compatible constructors. Factory overloads `categorical(name, spec)` and `numeric(name, min, max, spec)`.

- [ ] **Step 1: Write failing tests for FeatureField SimilaritySpec support**

Add to `FeatureFieldTest.java`:

```java
// --- SimilaritySpec on Categorical ---
@Test
void categorical_withCategoricalTable() {
    var table = SimilaritySpec.categoricalTableBuilder().add("a", "b", 0.5).build();
    var f = FeatureField.categorical("type", table);
    assertThat(f).isInstanceOf(FeatureField.Categorical.class);
    assertThat(((FeatureField.Categorical) f).similaritySpec()).isEqualTo(table);
}

@Test
void categorical_withGaussianDecay_throws() {
    assertThatThrownBy(() -> FeatureField.categorical("type", new SimilaritySpec.GaussianDecay(0.5)))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void categorical_withNull_accepted() {
    var f = new FeatureField.Categorical("type", null);
    assertThat(f.similaritySpec()).isNull();
}

@Test
void categorical_backwardCompat_noSpec() {
    var f = FeatureField.categorical("type");
    assertThat(((FeatureField.Categorical) f).similaritySpec()).isNull();
}

// --- SimilaritySpec on Numeric ---
@Test
void numeric_withGaussianDecay() {
    var f = FeatureField.numeric("score", 0, 100, new SimilaritySpec.GaussianDecay(0.3));
    assertThat(((FeatureField.Numeric) f).similaritySpec())
        .isEqualTo(new SimilaritySpec.GaussianDecay(0.3));
}

@Test
void numeric_withStepDecay() {
    var f = FeatureField.numeric("score", 0, 100, new SimilaritySpec.StepDecay(0.1));
    assertThat(((FeatureField.Numeric) f).similaritySpec())
        .isInstanceOf(SimilaritySpec.StepDecay.class);
}

@Test
void numeric_withExponentialDecay() {
    var f = FeatureField.numeric("score", 0, 100, new SimilaritySpec.ExponentialDecay(2.0));
    assertThat(((FeatureField.Numeric) f).similaritySpec())
        .isInstanceOf(SimilaritySpec.ExponentialDecay.class);
}

@Test
void numeric_withCategoricalTable_throws() {
    var table = SimilaritySpec.categoricalTableBuilder().add("a", "b", 0.5).build();
    assertThatThrownBy(() -> FeatureField.numeric("score", 0, 100, table))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void numeric_backwardCompat_noSpec() {
    var f = FeatureField.numeric("score", 0, 100);
    assertThat(((FeatureField.Numeric) f).similaritySpec()).isNull();
}

// --- Text unchanged ---
@Test
void text_noSimilaritySpec() {
    var f = FeatureField.text("desc");
    assertThat(f).isInstanceOf(FeatureField.Text.class);
}

// --- Value semantics preserved ---
@Test
void categorical_withSpec_equals() {
    var table = SimilaritySpec.categoricalTableBuilder().add("a", "b", 0.5).build();
    var f1 = FeatureField.categorical("type", table);
    var f2 = FeatureField.categorical("type", table);
    assertThat(f1).isEqualTo(f2);
}

@Test
void numeric_withSpec_equals() {
    var f1 = FeatureField.numeric("s", 0, 100, new SimilaritySpec.GaussianDecay(0.3));
    var f2 = FeatureField.numeric("s", 0, 100, new SimilaritySpec.GaussianDecay(0.3));
    assertThat(f1).isEqualTo(f2);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=FeatureFieldTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: compilation failures — new constructors and `similaritySpec()` don't exist

- [ ] **Step 3: Implement FeatureField changes**

Replace `FeatureField.java` with:

```java
package io.casehub.neocortex.memory.cbr;

import java.util.Objects;

public sealed interface FeatureField permits FeatureField.Categorical, FeatureField.Numeric, FeatureField.Text {
    String name();

    record Categorical(String name, SimilaritySpec similaritySpec) implements FeatureField {
        public Categorical(String name) { this(name, null); }
        public Categorical {
            Objects.requireNonNull(name, "name");
            if (similaritySpec != null) {
                switch (similaritySpec) {
                    case SimilaritySpec.CategoricalTable _ -> {}
                    case SimilaritySpec.GaussianDecay _, SimilaritySpec.StepDecay _,
                         SimilaritySpec.ExponentialDecay _ -> throw new IllegalArgumentException(
                        "Categorical fields only support CategoricalTable specs");
                }
            }
        }
    }

    record Numeric(String name, double min, double max, SimilaritySpec similaritySpec) implements FeatureField {
        public Numeric(String name, double min, double max) { this(name, min, max, null); }
        public Numeric {
            Objects.requireNonNull(name, "name");
            if (min > max) throw new IllegalArgumentException(
                "min must be <= max, got min=" + min + " max=" + max);
            if (similaritySpec != null) {
                switch (similaritySpec) {
                    case SimilaritySpec.GaussianDecay _, SimilaritySpec.StepDecay _,
                         SimilaritySpec.ExponentialDecay _ -> {}
                    case SimilaritySpec.CategoricalTable _ -> throw new IllegalArgumentException(
                        "Numeric fields do not support CategoricalTable specs");
                }
            }
        }
    }

    record Text(String name, boolean semantic) implements FeatureField {
        public Text {
            Objects.requireNonNull(name, "name");
        }
        public Text(String name) {
            this(name, false);
        }
    }

    static FeatureField categorical(String name) { return new Categorical(name); }
    static FeatureField categorical(String name, SimilaritySpec similaritySpec) {
        return new Categorical(name, similaritySpec);
    }
    static FeatureField numeric(String name, double min, double max) { return new Numeric(name, min, max); }
    static FeatureField numeric(String name, double min, double max, SimilaritySpec similaritySpec) {
        return new Numeric(name, min, max, similaritySpec);
    }
    static FeatureField text(String name) { return new Text(name); }
    static FeatureField semanticText(String name) { return new Text(name, true); }
}
```

- [ ] **Step 4: Run FeatureField tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=FeatureFieldTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: all PASS

- [ ] **Step 5: Verify existing tests still pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: all PASS (backward-compatible constructors ensure existing code compiles)

- [ ] **Step 6: Commit**

```
feat(#107,#108): seal FeatureField, add SimilaritySpec parameter to Categorical and Numeric
```

---

### Task 3: CbrSimilarityScorer — refactored dispatch with SimilaritySpec resolution

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorerTest.java`

**Interfaces:**
- Consumes: `SimilaritySpec` from Task 1, sealed `FeatureField` from Task 2
- Produces: Refactored `localSimilarity()` with three-level precedence, `categoricalSimilarity()`, `computeNormalizedDistance()`, spec-aware `numericSimilarity()`

- [ ] **Step 1: Write failing tests for SimilaritySpec resolution in scorer**

Add to `CbrSimilarityScorerTest.java`:

```java
// --- Categorical table tests ---
static final CbrFeatureSchema TABLE_SCHEMA = CbrFeatureSchema.of("test",
    FeatureField.categorical("type",
        SimilaritySpec.categoricalTableBuilder()
            .add("headache", "migraine", 0.8)
            .add("headache", "fracture", 0.1)
            .build()));

@Test
void categoricalTable_graduatedSimilarity() {
    double sim = CbrSimilarityScorer.score(
        Map.of("type", "headache"), Map.of("type", "migraine"), Map.of(), TABLE_SCHEMA);
    assertThat(sim).isCloseTo(0.8, org.assertj.core.data.Offset.offset(1e-9));
}

@Test
void categoricalTable_symmetricLookup() {
    double sim = CbrSimilarityScorer.score(
        Map.of("type", "migraine"), Map.of("type", "headache"), Map.of(), TABLE_SCHEMA);
    assertThat(sim).isCloseTo(0.8, org.assertj.core.data.Offset.offset(1e-9));
}

@Test
void categoricalTable_unlistedPair_zero() {
    double sim = CbrSimilarityScorer.score(
        Map.of("type", "headache"), Map.of("type", "unknown"), Map.of(), TABLE_SCHEMA);
    assertThat(sim).isCloseTo(0.0, org.assertj.core.data.Offset.offset(1e-9));
}

@Test
void categoricalTable_selfPair_one() {
    double sim = CbrSimilarityScorer.score(
        Map.of("type", "headache"), Map.of("type", "headache"), Map.of(), TABLE_SCHEMA);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void categoricalTable_emptyTable_exactMatch() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.categorical("x", new SimilaritySpec.CategoricalTable(Map.of())));
    double sim = CbrSimilarityScorer.score(
        Map.of("x", "a"), Map.of("x", "b"), Map.of(), schema);
    assertThat(sim).isEqualTo(0.0);
}

// --- Numeric decay tests ---
@Test
void gaussianDecay_exactMatch() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numeric("s", 0, 100, new SimilaritySpec.GaussianDecay(0.5)));
    double sim = CbrSimilarityScorer.score(
        Map.of("s", 50.0), Map.of("s", 50.0), Map.of(), schema);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void gaussianDecay_midRange() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numeric("s", 0, 100, new SimilaritySpec.GaussianDecay(0.5)));
    double sim = CbrSimilarityScorer.score(
        Map.of("s", 50.0), Map.of("s", 80.0), Map.of(), schema);
    // normalized distance = 0.3, gaussian = exp(-0.3^2 / (2 * 0.5^2)) = exp(-0.18)
    assertThat(sim).isCloseTo(Math.exp(-0.09 / 0.5), org.assertj.core.data.Offset.offset(1e-6));
}

@Test
void gaussianDecay_maxDistance() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numeric("s", 0, 100, new SimilaritySpec.GaussianDecay(0.3)));
    double sim = CbrSimilarityScorer.score(
        Map.of("s", 0.0), Map.of("s", 100.0), Map.of(), schema);
    // normalized distance = 1.0, gaussian = exp(-1.0 / (2 * 0.09)) = exp(-5.56) ≈ 0.004
    assertThat(sim).isCloseTo(Math.exp(-1.0 / (2 * 0.3 * 0.3)),
        org.assertj.core.data.Offset.offset(1e-6));
}

@Test
void stepDecay_withinTolerance() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numeric("s", 0, 100, new SimilaritySpec.StepDecay(0.1)));
    double sim = CbrSimilarityScorer.score(
        Map.of("s", 50.0), Map.of("s", 55.0), Map.of(), schema);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void stepDecay_outsideTolerance() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numeric("s", 0, 100, new SimilaritySpec.StepDecay(0.1)));
    double sim = CbrSimilarityScorer.score(
        Map.of("s", 50.0), Map.of("s", 70.0), Map.of(), schema);
    assertThat(sim).isEqualTo(0.0);
}

@Test
void exponentialDecay_exactMatch() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numeric("s", 0, 100, new SimilaritySpec.ExponentialDecay(3.0)));
    double sim = CbrSimilarityScorer.score(
        Map.of("s", 50.0), Map.of("s", 50.0), Map.of(), schema);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void exponentialDecay_fullRange() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numeric("s", 0, 100, new SimilaritySpec.ExponentialDecay(3.0)));
    double sim = CbrSimilarityScorer.score(
        Map.of("s", 0.0), Map.of("s", 100.0), Map.of(), schema);
    assertThat(sim).isCloseTo(Math.exp(-3.0), org.assertj.core.data.Offset.offset(1e-9));
}

// --- NumericRange + SimilaritySpec ---
@Test
void gaussianDecay_numericRange_inside() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numeric("s", 0, 100, new SimilaritySpec.GaussianDecay(0.5)));
    double sim = CbrSimilarityScorer.score(
        Map.of("s", NumericRange.of(40, 60)), Map.of("s", 50.0), Map.of(), schema);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void gaussianDecay_numericRange_outside() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numeric("s", 0, 100, new SimilaritySpec.GaussianDecay(0.5)));
    double sim = CbrSimilarityScorer.score(
        Map.of("s", NumericRange.of(40, 60)), Map.of("s", 80.0), Map.of(), schema);
    // distance from nearest bound (60) = 20, normalized = 0.2
    assertThat(sim).isCloseTo(Math.exp(-0.04 / (2 * 0.25)),
        org.assertj.core.data.Offset.offset(1e-6));
}

// --- Zero range fallback ---
@Test
void gaussianDecay_zeroRange_exactMatch() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numeric("x", 5.0, 5.0, new SimilaritySpec.GaussianDecay(0.5)));
    double sim = CbrSimilarityScorer.score(
        Map.of("x", 5.0), Map.of("x", 5.0), Map.of(), schema);
    assertThat(sim).isEqualTo(1.0);
}

@Test
void gaussianDecay_zeroRange_mismatch() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numeric("x", 5.0, 5.0, new SimilaritySpec.GaussianDecay(0.5)));
    double sim = CbrSimilarityScorer.score(
        Map.of("x", 5.0), Map.of("x", 6.0), Map.of(), schema);
    assertThat(sim).isEqualTo(0.0);
}

// --- Precedence chain ---
@Test
void callerOverride_beatsSimilaritySpec() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numeric("s", 0, 100, new SimilaritySpec.GaussianDecay(0.5)));
    LocalSimilarityFunction alwaysHalf = (q, c) -> 0.5;
    double sim = CbrSimilarityScorer.score(
        Map.of("s", 50.0), Map.of("s", 80.0), Map.of(), schema, Map.of("s", alwaysHalf));
    assertThat(sim).isEqualTo(0.5);
}

@Test
void similaritySpec_beatsTypeDefault() {
    var schema = CbrFeatureSchema.of("test",
        FeatureField.numeric("s", 0, 100, new SimilaritySpec.StepDecay(0.1)));
    // Linear default would give 0.8 for distance 20/100.
    // Step with tolerance 0.1 gives 0.0 for distance 0.2 > 0.1
    double sim = CbrSimilarityScorer.score(
        Map.of("s", 50.0), Map.of("s", 70.0), Map.of(), schema);
    assertThat(sim).isEqualTo(0.0);
}

@Test
void nullSpec_fallsThrough_toTypeDefault() {
    // Numeric with null spec should use linear decay
    double sim = CbrSimilarityScorer.score(
        Map.of("score", 80.0), Map.of("score", 60.0), Map.of(), SCHEMA);
    assertThat(sim).isCloseTo(0.8, org.assertj.core.data.Offset.offset(1e-9));
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrSimilarityScorerTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: failures — scorer doesn't handle SimilaritySpec yet

- [ ] **Step 3: Refactor CbrSimilarityScorer**

Replace `localSimilarity()`, `numericSimilarity()` methods and add `categoricalSimilarity()`, `computeNormalizedDistance()`:

```java
private static double localSimilarity(FeatureField field, Object queryVal, Object caseVal,
                                      Map<String, LocalSimilarityFunction> overrides) {
    LocalSimilarityFunction override = overrides.get(field.name());
    if (override != null) return override.compute(queryVal, caseVal);

    return switch (field) {
        case FeatureField.Numeric n -> numericSimilarity(n, queryVal, caseVal);
        case FeatureField.Categorical c -> categoricalSimilarity(c, queryVal, caseVal);
        case FeatureField.Text _ -> queryVal.equals(caseVal) ? 1.0 : 0.0;
    };
}

private static double categoricalSimilarity(FeatureField.Categorical field,
                                             Object queryVal, Object caseVal) {
    if (field.similaritySpec() == null) return queryVal.equals(caseVal) ? 1.0 : 0.0;
    return switch (field.similaritySpec()) {
        case SimilaritySpec.CategoricalTable(var table) -> {
            String q = (String) queryVal;
            String c = (String) caseVal;
            if (q.equals(c)) yield 1.0;
            yield table.getOrDefault(q, Map.of()).getOrDefault(c, 0.0);
        }
        case SimilaritySpec.GaussianDecay _, SimilaritySpec.StepDecay _,
             SimilaritySpec.ExponentialDecay _ ->
            throw new IllegalStateException("Unexpected spec on Categorical: " + field.similaritySpec());
    };
}

private static double numericSimilarity(FeatureField.Numeric field,
                                         Object queryVal, Object caseVal) {
    double range = field.max() - field.min();
    if (range <= 0) return queryVal.equals(caseVal) ? 1.0 : 0.0;

    double normalizedDistance = computeNormalizedDistance(field, queryVal, caseVal);

    if (field.similaritySpec() == null) {
        return Math.max(0.0, 1.0 - normalizedDistance);
    }
    return switch (field.similaritySpec()) {
        case SimilaritySpec.GaussianDecay(var sigma) ->
            Math.exp(-normalizedDistance * normalizedDistance / (2 * sigma * sigma));
        case SimilaritySpec.StepDecay(var tol) ->
            normalizedDistance <= tol ? 1.0 : 0.0;
        case SimilaritySpec.ExponentialDecay(var rate) ->
            Math.exp(-rate * normalizedDistance);
        case SimilaritySpec.CategoricalTable _ ->
            throw new IllegalStateException("Unexpected spec on Numeric: " + field.similaritySpec());
    };
}

private static double computeNormalizedDistance(FeatureField.Numeric field,
                                                Object queryVal, Object caseVal) {
    double range = field.max() - field.min();
    double caseNum = ((Number) caseVal).doubleValue();

    if (queryVal instanceof NumericRange nr) {
        if (caseNum >= nr.min() && caseNum <= nr.max()) return 0.0;
        double dist = caseNum < nr.min() ? nr.min() - caseNum : caseNum - nr.max();
        return dist / range;
    }

    double queryNum = ((Number) queryVal).doubleValue();
    return Math.abs(queryNum - caseNum) / range;
}
```

- [ ] **Step 4: Run all scorer tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrSimilarityScorerTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: all PASS (existing + new)

- [ ] **Step 5: Run full memory-api tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: all PASS

- [ ] **Step 6: Commit**

```
feat(#107,#108): CbrSimilarityScorer SimilaritySpec resolution — categorical tables, Gaussian/step/exponential decay
```

---

### Task 4: Dispatch site migration — exhaustive switches on sealed FeatureField

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrQueryTranslator.java` (lines 79-97, 121-139)
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrCollectionManager.java` (lines 128-139)
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java` (line 308 — `buildTextOverrides`)

**Interfaces:**
- Consumes: sealed `FeatureField` from Task 2
- Produces: no API changes — mechanical migration of `instanceof` chains to exhaustive `switch`

- [ ] **Step 1: Verify compilation fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl memory-qdrant -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: compilation errors in CbrQueryTranslator, CbrCollectionManager — non-exhaustive `instanceof` chains on sealed type

- [ ] **Step 2: Migrate CbrQueryTranslator.toFilter()**

Replace the `instanceof` chain in `toFilter()` (lines 79-97) with:

```java
switch (field) {
    case FeatureField.Categorical _ ->
        builder.addMust(ConditionFactory.matchKeyword(payloadKey, (String) value));
    case FeatureField.Numeric _ -> {
        if (value instanceof NumericRange range) {
            builder.addMust(ConditionFactory.range(payloadKey,
                Range.newBuilder()
                    .setGte(range.min())
                    .setLte(range.max())
                    .build()));
        } else {
            builder.addMust(ConditionFactory.range(payloadKey,
                Range.newBuilder()
                    .setGte(((Number) value).doubleValue())
                    .setLte(((Number) value).doubleValue())
                    .build()));
        }
    }
    case FeatureField.Text _ ->
        builder.addMust(ConditionFactory.matchKeyword(payloadKey, (String) value));
}
```

- [ ] **Step 3: Migrate CbrQueryTranslator.validateQueryFeatures()**

Replace the `instanceof` chain in `validateQueryFeatures()` (lines 121-139) with:

```java
switch (field) {
    case FeatureField.Categorical _ -> {
        if (!(value instanceof String)) {
            throw new IllegalArgumentException(
                "Categorical field '" + entry.getKey() + "' requires String, got: "
                + value.getClass().getSimpleName());
        }
    }
    case FeatureField.Numeric _ -> {
        if (!(value instanceof Number) && !(value instanceof NumericRange)) {
            throw new IllegalArgumentException(
                "Numeric field '" + entry.getKey() + "' requires Number or NumericRange, got: "
                + value.getClass().getSimpleName());
        }
    }
    case FeatureField.Text _ -> {
        if (!(value instanceof String)) {
            throw new IllegalArgumentException(
                "Text field '" + entry.getKey() + "' requires String, got: "
                + value.getClass().getSimpleName());
        }
    }
}
```

- [ ] **Step 4: Migrate CbrCollectionManager.registerSchemaIndexes()**

Replace the `instanceof` chain (lines 130-139) with:

```java
switch (field) {
    case FeatureField.Categorical _ ->
        client.createPayloadIndexAsync(collection, payloadKey,
            PayloadSchemaType.Keyword, null, true, null, null).get();
    case FeatureField.Numeric _ ->
        client.createPayloadIndexAsync(collection, payloadKey,
            PayloadSchemaType.Float, null, true, null, null).get();
    case FeatureField.Text _ ->
        client.createPayloadIndexAsync(collection, payloadKey,
            PayloadSchemaType.Keyword, null, true, null, null).get();
}
```

- [ ] **Step 5: Migrate QdrantCbrCaseMemoryStore.buildTextOverrides()**

Replace the `instanceof` check (line 308) with exhaustive switch:

```java
private Map<String, LocalSimilarityFunction> buildTextOverrides(
        CbrFeatureSchema schema, EmbeddingTextSimilarity textSim) {
    if (textSim == null) return Map.of();
    Map<String, LocalSimilarityFunction> overrides = new HashMap<>();
    for (FeatureField field : schema.fields()) {
        switch (field) {
            case FeatureField.Text t -> {
                if (t.semantic()) overrides.put(field.name(), textSim);
            }
            case FeatureField.Categorical _, FeatureField.Numeric _ -> {}
        }
    }
    return overrides.isEmpty() ? Map.of() : Collections.unmodifiableMap(overrides);
}
```

- [ ] **Step 6: Verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: PASS — all modules compile

- [ ] **Step 7: Run Qdrant module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: all PASS (existing behavior unchanged)

- [ ] **Step 8: Commit**

```
refactor(#107): migrate FeatureField dispatch sites to exhaustive switch — CbrQueryTranslator, CbrCollectionManager, QdrantCbrCaseMemoryStore
```

---

### Task 5: Contract tests + full build verification

**Files:**
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`

**Interfaces:**
- Consumes: `SimilaritySpec`, sealed `FeatureField`, refactored `CbrSimilarityScorer` from Tasks 1-3
- Produces: 4+ new contract tests exercising SimilaritySpec through the store SPI

- [ ] **Step 1: Write contract tests for SimilaritySpec through the store**

Add to `CbrCaseMemoryStoreContractTest.java`:

```java
@Test
void categoricalTable_graduatedSimilarityRanking() {
    var schema = CbrFeatureSchema.of("medical",
        FeatureField.categorical("condition",
            SimilaritySpec.categoricalTableBuilder()
                .add("headache", "migraine", 0.8)
                .add("headache", "fracture", 0.1)
                .build()),
        FeatureField.numeric("severity", 0, 10));
    store().registerSchema(schema);

    store().store("t1", CBR, "e1", new FeatureVectorCase("medical",
        Map.of("condition", "migraine", "severity", 5.0)), ENTITY);
    store().store("t1", CBR, "e2", new FeatureVectorCase("medical",
        Map.of("condition", "fracture", "severity", 5.0)), ENTITY);

    var results = store().retrieveSimilar(
        CbrQuery.of(TENANT, CBR, "medical",
            Map.of("condition", "headache", "severity", 5.0), 10),
        FeatureVectorCase.class);

    assertThat(results).hasSizeGreaterThanOrEqualTo(2);
    assertThat(results.get(0).cbrCase().features().get("condition")).isEqualTo("migraine");
    assertThat(results.get(0).score()).isGreaterThan(results.get(1).score());
}

@Test
void gaussianDecay_numericSimilarityRanking() {
    var schema = CbrFeatureSchema.of("gauss",
        FeatureField.categorical("cat"),
        FeatureField.numeric("val", 0, 100, new SimilaritySpec.GaussianDecay(0.3)));
    store().registerSchema(schema);

    store().store("t1", CBR, "e1", new FeatureVectorCase("gauss",
        Map.of("cat", "a", "val", 50.0)), ENTITY);
    store().store("t1", CBR, "e2", new FeatureVectorCase("gauss",
        Map.of("cat", "a", "val", 90.0)), ENTITY);

    var results = store().retrieveSimilar(
        CbrQuery.of(TENANT, CBR, "gauss",
            Map.of("cat", "a", "val", 55.0), 10),
        FeatureVectorCase.class);

    assertThat(results).hasSizeGreaterThanOrEqualTo(2);
    assertThat(results.get(0).cbrCase().features().get("val")).isEqualTo(50.0);
    assertThat(results.get(0).score()).isGreaterThan(results.get(1).score());
}

@Test
void noSpec_backwardCompatible_linearDecay() {
    var results = store().retrieveSimilar(
        CbrQuery.of(TENANT, CBR, "battle",
            Map.of("opponent_race", "zerg", "army_size_ratio", 1.5), 10),
        FeatureVectorCase.class);
    // Existing tests use the default schema with no SimilaritySpec — must still work
    assertThat(results).isNotNull();
}

@Test
void stepDecay_hardCutoff() {
    var schema = CbrFeatureSchema.of("step",
        FeatureField.numeric("val", 0, 100, new SimilaritySpec.StepDecay(0.1)));
    store().registerSchema(schema);

    store().store("t1", CBR, "e1", new FeatureVectorCase("step",
        Map.of("val", 55.0)), ENTITY);
    store().store("t1", CBR, "e2", new FeatureVectorCase("step",
        Map.of("val", 80.0)), ENTITY);

    var results = store().retrieveSimilar(
        CbrQuery.of(TENANT, CBR, "step",
            Map.of("val", 50.0), 10).withMinSimilarity(0.5),
        FeatureVectorCase.class);

    assertThat(results).hasSize(1);
    assertThat(results.get(0).cbrCase().features().get("val")).isEqualTo(55.0);
}
```

- [ ] **Step 2: Run contract tests via in-memory store**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: all PASS (new + existing)

- [ ] **Step 3: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: BUILD SUCCESS — all modules compile and all tests pass

- [ ] **Step 4: Commit**

```
test(#107,#108): contract tests for SimilaritySpec — categorical table ranking, Gaussian decay, step cutoff
```

---

## Self-Review

**Spec coverage:**
- ✅ SimilaritySpec sealed interface with all 4 record variants → Task 1
- ✅ CategoricalTableBuilder with validation → Task 1
- ✅ FeatureField sealed with permits clause → Task 2
- ✅ SimilaritySpec on Categorical and Numeric, not Text → Task 2
- ✅ Exhaustive switch validation in constructors → Task 2
- ✅ Scorer precedence chain → Task 3
- ✅ categoricalSimilarity with table lookup → Task 3
- ✅ computeNormalizedDistance extracted → Task 3
- ✅ All decay functions (Gaussian, Step, Exponential) → Task 3
- ✅ NumericRange with SimilaritySpec → Task 3
- ✅ Zero range fallback → Task 3
- ✅ Dispatch site migration (CbrQueryTranslator, CbrCollectionManager, QdrantCbrCaseMemoryStore) → Task 4
- ✅ Contract tests through store → Task 5
- ✅ Backward compatibility → Tasks 2, 5
- ✅ Value semantics preserved → Task 2

**Placeholder scan:** No TBD, TODO, or vague steps found.

**Type consistency:** `SimilaritySpec`, `FeatureField`, `CbrSimilarityScorer` signatures consistent across all tasks. `categoricalSimilarity`, `computeNormalizedDistance` named consistently.

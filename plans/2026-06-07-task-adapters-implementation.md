# inference-tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement four typed task adapters (NliClassifier, TextClassifier, ScalarRegressor, CrossEncoderReranker) in the `inference-tasks` module that interpret `InferenceModel` float[] output as domain types.

**Architecture:** Each adapter takes an `InferenceModel` at construction, validates output size when available, and interprets raw float arrays as typed domain results. Adapters are pure interpreters — not `AutoCloseable`, no resource ownership. A package-private `Softmax` utility handles numerically stable probability conversion.

**Tech Stack:** Java 21, JUnit 5, AssertJ, ArchUnit 1.4.1, `casehub-inference-api` (compile), `casehub-inference-inmem` (test)

**Build command:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl inference-tasks`

**Test naming conventions:** `@Nested` + `@DisplayName` groups. AssertJ `assertThat` / `assertThatThrownBy`. Package: `io.casehub.inference.tasks`.

---

## File Map

| File | Responsibility |
|---|---|
| `inference-tasks/pom.xml` | Add `archunit-junit5` test dependency |
| `inference-tasks/src/main/java/io/casehub/inference/tasks/Softmax.java` | Package-private numerically stable softmax |
| `inference-tasks/src/main/java/io/casehub/inference/tasks/NliLabel.java` | Enum: ENTAILMENT, NEUTRAL, CONTRADICTION |
| `inference-tasks/src/main/java/io/casehub/inference/tasks/NliResult.java` | Record: entailment, neutral, contradiction + predicted() + scores() |
| `inference-tasks/src/main/java/io/casehub/inference/tasks/NliClassifier.java` | Adapter: pair input → softmax → NliResult |
| `inference-tasks/src/main/java/io/casehub/inference/tasks/ClassificationResult.java` | Record: label, confidence, scores (Map.copyOf) |
| `inference-tasks/src/main/java/io/casehub/inference/tasks/TextClassifier.java` | Adapter: single input → softmax → ClassificationResult |
| `inference-tasks/src/main/java/io/casehub/inference/tasks/ScalarRegressor.java` | Adapter: single input → raw scalar |
| `inference-tasks/src/main/java/io/casehub/inference/tasks/RankedResult.java` | Record: text, score, originalIndex |
| `inference-tasks/src/main/java/io/casehub/inference/tasks/CrossEncoderReranker.java` | Adapter: pair input → score; batch → sorted RankedResults |
| `inference-tasks/src/test/java/io/casehub/inference/tasks/SoftmaxTest.java` | Softmax unit tests |
| `inference-tasks/src/test/java/io/casehub/inference/tasks/NliClassifierTest.java` | NliClassifier + NliResult + NliLabel tests |
| `inference-tasks/src/test/java/io/casehub/inference/tasks/TextClassifierTest.java` | TextClassifier + ClassificationResult tests |
| `inference-tasks/src/test/java/io/casehub/inference/tasks/ScalarRegressorTest.java` | ScalarRegressor tests |
| `inference-tasks/src/test/java/io/casehub/inference/tasks/CrossEncoderRerankerTest.java` | CrossEncoderReranker + RankedResult tests |
| `inference-tasks/src/test/java/io/casehub/inference/tasks/DependencyConstraintTest.java` | ArchUnit: framework + casehub domain exclusion |

---

### Task 1: Add ArchUnit dependency to pom.xml

**Files:**
- Modify: `inference-tasks/pom.xml`

- [ ] **Step 1: Add archunit-junit5 test dependency**

Add this dependency block after the `casehub-inference-inmem` dependency in `inference-tasks/pom.xml`:

```xml
    <dependency>
      <groupId>com.tngtech.archunit</groupId>
      <artifactId>archunit-junit5</artifactId>
      <scope>test</scope>
    </dependency>
```

- [ ] **Step 2: Remove .gitkeep placeholders**

Delete these files (they're scaffolding from C1 — real files will replace them):
- `inference-tasks/src/main/java/io/casehub/inference/tasks/.gitkeep`
- `inference-tasks/src/main/resources/.gitkeep`
- `inference-tasks/src/test/java/io/casehub/inference/tasks/.gitkeep`

- [ ] **Step 3: Verify build compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean compile -pl inference-tasks`
Expected: BUILD SUCCESS (no source files yet, but deps resolve)

- [ ] **Step 4: Commit**

```
git add inference-tasks/pom.xml
git rm inference-tasks/src/main/java/io/casehub/inference/tasks/.gitkeep
git rm inference-tasks/src/main/resources/.gitkeep
git rm inference-tasks/src/test/java/io/casehub/inference/tasks/.gitkeep
git commit -m "build(#4): add archunit-junit5 test dep, remove scaffolding gitkeeps"
```

---

### Task 2: Softmax utility + tests

**Files:**
- Create: `inference-tasks/src/main/java/io/casehub/inference/tasks/Softmax.java`
- Create: `inference-tasks/src/test/java/io/casehub/inference/tasks/SoftmaxTest.java`

- [ ] **Step 1: Write the failing tests**

```java
package io.casehub.inference.tasks;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

class SoftmaxTest {

    @Test
    @DisplayName("standard logits produce valid probabilities summing to 1")
    void standardLogits() {
        float[] result = Softmax.apply(new float[]{2.0f, 1.0f, 0.5f});
        assertThat(result).hasSize(3);
        float sum = result[0] + result[1] + result[2];
        assertThat(sum).isCloseTo(1.0f, within(1e-6f));
        assertThat(result[0]).isGreaterThan(result[1]);
        assertThat(result[1]).isGreaterThan(result[2]);
    }

    @Test
    @DisplayName("large logits do not overflow — numeric stability")
    void numericStability() {
        float[] result = Softmax.apply(new float[]{1000f, 1001f, 1002f});
        assertThat(result).hasSize(3);
        float sum = result[0] + result[1] + result[2];
        assertThat(sum).isCloseTo(1.0f, within(1e-6f));
        for (float v : result) {
            assertThat(v).isFinite();
            assertThat(v).isGreaterThan(0f);
        }
    }

    @Test
    @DisplayName("single element produces [1.0]")
    void singleElement() {
        float[] result = Softmax.apply(new float[]{42.0f});
        assertThat(result).containsExactly(1.0f);
    }

    @Test
    @DisplayName("uniform input produces uniform distribution")
    void uniformInput() {
        float[] result = Softmax.apply(new float[]{1.0f, 1.0f, 1.0f});
        assertThat(result[0]).isCloseTo(1.0f / 3, within(1e-6f));
        assertThat(result[1]).isCloseTo(1.0f / 3, within(1e-6f));
        assertThat(result[2]).isCloseTo(1.0f / 3, within(1e-6f));
    }

    @Test
    @DisplayName("does not mutate input array")
    void doesNotMutateInput() {
        float[] input = {1.0f, 2.0f, 3.0f};
        float[] copy = input.clone();
        Softmax.apply(input);
        assertThat(input).containsExactly(copy);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks -Dtest=SoftmaxTest`
Expected: COMPILATION FAILURE — `Softmax` does not exist

- [ ] **Step 3: Implement Softmax**

```java
package io.casehub.inference.tasks;

final class Softmax {

    private Softmax() {}

    static float[] apply(float[] logits) {
        float max = logits[0];
        for (int i = 1; i < logits.length; i++) {
            if (logits[i] > max) max = logits[i];
        }
        float sum = 0;
        float[] result = new float[logits.length];
        for (int i = 0; i < logits.length; i++) {
            result[i] = (float) Math.exp(logits[i] - max);
            sum += result[i];
        }
        for (int i = 0; i < logits.length; i++) {
            result[i] /= sum;
        }
        return result;
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks -Dtest=SoftmaxTest`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```
git add inference-tasks/src/main/java/io/casehub/inference/tasks/Softmax.java
git add inference-tasks/src/test/java/io/casehub/inference/tasks/SoftmaxTest.java
git commit -m "feat(#4): Softmax — package-private numerically stable softmax utility"
```

---

### Task 3: NliLabel + NliResult + NliClassifier + tests

**Files:**
- Create: `inference-tasks/src/main/java/io/casehub/inference/tasks/NliLabel.java`
- Create: `inference-tasks/src/main/java/io/casehub/inference/tasks/NliResult.java`
- Create: `inference-tasks/src/main/java/io/casehub/inference/tasks/NliClassifier.java`
- Create: `inference-tasks/src/test/java/io/casehub/inference/tasks/NliClassifierTest.java`

- [ ] **Step 1: Write the failing tests**

```java
package io.casehub.inference.tasks;

import io.casehub.inference.InferenceException;
import io.casehub.inference.InferenceInput;
import io.casehub.inference.InferenceModel;
import io.casehub.inference.InferenceOutput;
import io.casehub.inference.inmem.InMemoryInferenceModel;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.OptionalInt;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

class NliClassifierTest {

    @Nested
    @DisplayName("convention constructor")
    class ConventionConstructor {

        @Test
        void softmaxApplied() {
            var model = InMemoryInferenceModel.returning(2.0f, 1.0f, 0.5f);
            var nli = new NliClassifier(model);
            NliResult result = nli.classify("premise", "hypothesis");
            float sum = result.entailment() + result.neutral() + result.contradiction();
            assertThat(sum).isCloseTo(1.0f, within(1e-6f));
        }

        @Test
        void predictedReturnsHighestLabel() {
            // index 0=contradiction(high), 1=neutral, 2=entailment(low)
            var model = InMemoryInferenceModel.returning(5.0f, 0.1f, 0.1f);
            var nli = new NliClassifier(model);
            NliResult result = nli.classify("p", "h");
            assertThat(result.predicted()).isEqualTo(NliLabel.CONTRADICTION);
        }

        @Test
        void conventionOrder_index0IsContradiction_index2IsEntailment() {
            // logits: [10, 0, 0] → index 0 dominates → contradiction wins
            var model = InMemoryInferenceModel.returning(10.0f, 0.0f, 0.0f);
            var nli = new NliClassifier(model);
            NliResult result = nli.classify("p", "h");
            assertThat(result.contradiction()).isGreaterThan(0.9f);
            assertThat(result.predicted()).isEqualTo(NliLabel.CONTRADICTION);

            // logits: [0, 0, 10] → index 2 dominates → entailment wins
            var model2 = InMemoryInferenceModel.returning(0.0f, 0.0f, 10.0f);
            var nli2 = new NliClassifier(model2);
            NliResult result2 = nli2.classify("p", "h");
            assertThat(result2.entailment()).isGreaterThan(0.9f);
            assertThat(result2.predicted()).isEqualTo(NliLabel.ENTAILMENT);
        }

        @Test
        void scoresReturnsAllThreeLabels() {
            var model = InMemoryInferenceModel.returning(1.0f, 2.0f, 3.0f);
            var nli = new NliClassifier(model);
            NliResult result = nli.classify("p", "h");
            Map<NliLabel, Float> scores = result.scores();
            assertThat(scores).hasSize(3);
            assertThat(scores).containsKeys(NliLabel.ENTAILMENT, NliLabel.NEUTRAL, NliLabel.CONTRADICTION);
            assertThat(scores.get(NliLabel.ENTAILMENT)).isEqualTo(result.entailment());
            assertThat(scores.get(NliLabel.NEUTRAL)).isEqualTo(result.neutral());
            assertThat(scores.get(NliLabel.CONTRADICTION)).isEqualTo(result.contradiction());
        }
    }

    @Nested
    @DisplayName("explicit-index constructor")
    class ExplicitIndexConstructor {

        @Test
        void customMappingProducesCorrectAssignment() {
            // reversed order: index 0=entailment, 1=neutral, 2=contradiction
            var model = InMemoryInferenceModel.returning(10.0f, 0.0f, 0.0f);
            var nli = new NliClassifier(model, 0, 1, 2);
            NliResult result = nli.classify("p", "h");
            assertThat(result.entailment()).isGreaterThan(0.9f);
            assertThat(result.predicted()).isEqualTo(NliLabel.ENTAILMENT);
        }

        @Test
        void rejectsDuplicateIndices() {
            var model = InMemoryInferenceModel.returning(1.0f, 2.0f, 3.0f);
            assertThatThrownBy(() -> new NliClassifier(model, 0, 0, 2))
                .isInstanceOf(IllegalArgumentException.class);
        }

        @Test
        void rejectsOutOfRangeIndices() {
            var model = InMemoryInferenceModel.returning(1.0f, 2.0f, 3.0f);
            assertThatThrownBy(() -> new NliClassifier(model, 0, 1, 3))
                .isInstanceOf(IllegalArgumentException.class);
            assertThatThrownBy(() -> new NliClassifier(model, -1, 1, 2))
                .isInstanceOf(IllegalArgumentException.class);
        }
    }

    @Nested
    @DisplayName("construction validation")
    class ConstructionValidation {

        @Test
        void rejectsOutputSizeMismatch() {
            var model = InMemoryInferenceModel.returning(1.0f, 2.0f, 3.0f, 4.0f, 5.0f);
            assertThatThrownBy(() -> new NliClassifier(model))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("3")
                .hasMessageContaining("5");
        }

        @Test
        void acceptsUnknownOutputSize() {
            InferenceModel model = new InferenceModel() {
                @Override public InferenceOutput run(InferenceInput input) {
                    return new InferenceOutput(new float[]{1.0f, 2.0f, 3.0f});
                }
                @Override public java.util.List<InferenceOutput> runBatch(java.util.List<InferenceInput> inputs) {
                    return inputs.stream().map(this::run).toList();
                }
                @Override public OptionalInt outputSize() { return OptionalInt.empty(); }
                @Override public void close() {}
            };
            var nli = new NliClassifier(model);
            NliResult result = nli.classify("p", "h");
            assertThat(result.entailment() + result.neutral() + result.contradiction())
                .isCloseTo(1.0f, within(1e-6f));
        }

        @Test
        void rejectsNullModel() {
            assertThatThrownBy(() -> new NliClassifier(null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("model");
        }
    }

    @Nested
    @DisplayName("argument validation")
    class ArgumentValidation {

        @Test
        void rejectsNullPremise() {
            var model = InMemoryInferenceModel.returning(1.0f, 2.0f, 3.0f);
            var nli = new NliClassifier(model);
            assertThatThrownBy(() -> nli.classify(null, "h"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("premise");
        }

        @Test
        void rejectsNullHypothesis() {
            var model = InMemoryInferenceModel.returning(1.0f, 2.0f, 3.0f);
            var nli = new NliClassifier(model);
            assertThatThrownBy(() -> nli.classify("p", null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("hypothesis");
        }
    }

    @Nested
    @DisplayName("runtime output-length guard")
    class RuntimeGuard {

        @Test
        void throwsOnWrongLengthOutput() {
            var model = InMemoryInferenceModel.withFunction(3, input -> new float[]{1.0f, 2.0f});
            var nli = new NliClassifier(model);
            assertThatThrownBy(() -> nli.classify("p", "h"))
                .isInstanceOf(InferenceException.class)
                .hasMessageContaining("3")
                .hasMessageContaining("2");
        }
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks -Dtest=NliClassifierTest`
Expected: COMPILATION FAILURE — `NliClassifier`, `NliResult`, `NliLabel` do not exist

- [ ] **Step 3: Implement NliLabel**

```java
package io.casehub.inference.tasks;

public enum NliLabel {
    ENTAILMENT, NEUTRAL, CONTRADICTION
}
```

- [ ] **Step 4: Implement NliResult**

```java
package io.casehub.inference.tasks;

import java.util.Map;

import static io.casehub.inference.tasks.NliLabel.CONTRADICTION;
import static io.casehub.inference.tasks.NliLabel.ENTAILMENT;
import static io.casehub.inference.tasks.NliLabel.NEUTRAL;

public record NliResult(float entailment, float neutral, float contradiction) {

    public NliLabel predicted() {
        if (entailment >= neutral && entailment >= contradiction) return ENTAILMENT;
        if (neutral >= contradiction) return NEUTRAL;
        return CONTRADICTION;
    }

    public Map<NliLabel, Float> scores() {
        return Map.of(ENTAILMENT, entailment, NEUTRAL, neutral, CONTRADICTION, contradiction);
    }
}
```

- [ ] **Step 5: Implement NliClassifier**

```java
package io.casehub.inference.tasks;

import io.casehub.inference.InferenceException;
import io.casehub.inference.InferenceInput;
import io.casehub.inference.InferenceModel;
import io.casehub.inference.InferenceOutput;

import java.util.Set;

public final class NliClassifier {

    private static final int EXPECTED_SIZE = 3;

    private final InferenceModel model;
    private final int entailmentIndex;
    private final int neutralIndex;
    private final int contradictionIndex;

    public NliClassifier(InferenceModel model) {
        this(model, 2, 1, 0);
    }

    public NliClassifier(InferenceModel model,
                         int entailmentIndex, int neutralIndex, int contradictionIndex) {
        if (model == null) throw new IllegalArgumentException("model must not be null");
        if (entailmentIndex < 0 || entailmentIndex > 2
                || neutralIndex < 0 || neutralIndex > 2
                || contradictionIndex < 0 || contradictionIndex > 2) {
            throw new IllegalArgumentException(
                "indices must be in range [0,2], got: entailment=" + entailmentIndex
                    + ", neutral=" + neutralIndex + ", contradiction=" + contradictionIndex);
        }
        if (Set.of(entailmentIndex, neutralIndex, contradictionIndex).size() != 3) {
            throw new IllegalArgumentException(
                "indices must be distinct, got: entailment=" + entailmentIndex
                    + ", neutral=" + neutralIndex + ", contradiction=" + contradictionIndex);
        }
        model.outputSize().ifPresent(size -> {
            if (size != EXPECTED_SIZE) {
                throw new IllegalArgumentException(
                    "NliClassifier requires outputSize " + EXPECTED_SIZE + ", got " + size);
            }
        });
        this.model = model;
        this.entailmentIndex = entailmentIndex;
        this.neutralIndex = neutralIndex;
        this.contradictionIndex = contradictionIndex;
    }

    public NliResult classify(String premise, String hypothesis) {
        if (premise == null) throw new IllegalArgumentException("premise must not be null");
        if (hypothesis == null) throw new IllegalArgumentException("hypothesis must not be null");

        InferenceOutput output = model.run(InferenceInput.pair(premise, hypothesis));
        float[] values = output.values();

        if (values.length != EXPECTED_SIZE) {
            throw new InferenceException(
                "Expected " + EXPECTED_SIZE + " output values, got " + values.length);
        }

        float[] probs = Softmax.apply(values);
        return new NliResult(probs[entailmentIndex], probs[neutralIndex], probs[contradictionIndex]);
    }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks -Dtest=NliClassifierTest`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```
git add inference-tasks/src/main/java/io/casehub/inference/tasks/NliLabel.java
git add inference-tasks/src/main/java/io/casehub/inference/tasks/NliResult.java
git add inference-tasks/src/main/java/io/casehub/inference/tasks/NliClassifier.java
git add inference-tasks/src/test/java/io/casehub/inference/tasks/NliClassifierTest.java
git commit -m "feat(#4): NliClassifier — convention + explicit-index constructors, softmax, runtime guard"
```

---

### Task 4: ClassificationResult + TextClassifier + tests

**Files:**
- Create: `inference-tasks/src/main/java/io/casehub/inference/tasks/ClassificationResult.java`
- Create: `inference-tasks/src/main/java/io/casehub/inference/tasks/TextClassifier.java`
- Create: `inference-tasks/src/test/java/io/casehub/inference/tasks/TextClassifierTest.java`

- [ ] **Step 1: Write the failing tests**

```java
package io.casehub.inference.tasks;

import io.casehub.inference.InferenceException;
import io.casehub.inference.InferenceInput;
import io.casehub.inference.InferenceModel;
import io.casehub.inference.InferenceOutput;
import io.casehub.inference.inmem.InMemoryInferenceModel;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.OptionalInt;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

class TextClassifierTest {

    @Nested
    @DisplayName("classify()")
    class Classify {

        @Test
        void labelsMatchOutputIndices() {
            var model = InMemoryInferenceModel.returning(0.1f, 0.9f);
            var tc = new TextClassifier(model, List.of("low", "high"));
            ClassificationResult result = tc.classify("some text");
            assertThat(result.label()).isEqualTo("high");
            assertThat(result.confidence()).isGreaterThan(0.5f);
        }

        @Test
        void softmaxApplied() {
            var model = InMemoryInferenceModel.returning(2.0f, 1.0f);
            var tc = new TextClassifier(model, List.of("a", "b"));
            ClassificationResult result = tc.classify("text");
            float sum = 0;
            for (float v : result.scores().values()) sum += v;
            assertThat(sum).isCloseTo(1.0f, within(1e-6f));
        }

        @Test
        void scoresContainsAllLabels() {
            var model = InMemoryInferenceModel.returning(1.0f, 2.0f, 3.0f);
            var tc = new TextClassifier(model, List.of("a", "b", "c"));
            ClassificationResult result = tc.classify("text");
            assertThat(result.scores()).hasSize(3);
            assertThat(result.scores()).containsKeys("a", "b", "c");
        }

        @Test
        void singleLabelDegenerateCase() {
            var model = InMemoryInferenceModel.returning(5.0f);
            var tc = new TextClassifier(model, List.of("only"));
            ClassificationResult result = tc.classify("text");
            assertThat(result.label()).isEqualTo("only");
            assertThat(result.confidence()).isCloseTo(1.0f, within(1e-6f));
        }
    }

    @Nested
    @DisplayName("ClassificationResult defensiveness")
    class ResultDefensiveness {

        @Test
        void scoresMapIsUnmodifiable() {
            var model = InMemoryInferenceModel.returning(1.0f, 2.0f);
            var tc = new TextClassifier(model, List.of("a", "b"));
            ClassificationResult result = tc.classify("text");
            assertThatThrownBy(() -> result.scores().put("c", 0.5f))
                .isInstanceOf(UnsupportedOperationException.class);
        }
    }

    @Nested
    @DisplayName("construction validation")
    class ConstructionValidation {

        @Test
        void rejectsLabelCountMismatch() {
            var model = InMemoryInferenceModel.returning(1.0f, 2.0f, 3.0f);
            assertThatThrownBy(() -> new TextClassifier(model, List.of("a", "b")))
                .isInstanceOf(IllegalArgumentException.class);
        }

        @Test
        void labelsImmutableAfterConstruction() {
            var labels = new ArrayList<>(List.of("a", "b"));
            var model = InMemoryInferenceModel.returning(1.0f, 2.0f);
            var tc = new TextClassifier(model, labels);
            labels.set(0, "mutated");
            ClassificationResult result = tc.classify("text");
            assertThat(result.scores()).containsKey("a");
            assertThat(result.scores()).doesNotContainKey("mutated");
        }

        @Test
        void rejectsNullLabels() {
            var model = InMemoryInferenceModel.returning(1.0f);
            assertThatThrownBy(() -> new TextClassifier(model, null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("labels");
        }

        @Test
        void rejectsEmptyLabels() {
            var model = InMemoryInferenceModel.returning(1.0f);
            assertThatThrownBy(() -> new TextClassifier(model, List.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("labels");
        }

        @Test
        void rejectsNullModel() {
            assertThatThrownBy(() -> new TextClassifier(null, List.of("a")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("model");
        }

        @Test
        void acceptsUnknownOutputSize() {
            InferenceModel model = new InferenceModel() {
                @Override public InferenceOutput run(InferenceInput input) {
                    return new InferenceOutput(new float[]{1.0f, 2.0f});
                }
                @Override public List<InferenceOutput> runBatch(List<InferenceInput> inputs) {
                    return inputs.stream().map(this::run).toList();
                }
                @Override public OptionalInt outputSize() { return OptionalInt.empty(); }
                @Override public void close() {}
            };
            var tc = new TextClassifier(model, List.of("a", "b"));
            ClassificationResult result = tc.classify("text");
            assertThat(result.label()).isEqualTo("b");
        }
    }

    @Nested
    @DisplayName("argument validation")
    class ArgumentValidation {

        @Test
        void rejectsNullText() {
            var model = InMemoryInferenceModel.returning(1.0f);
            var tc = new TextClassifier(model, List.of("a"));
            assertThatThrownBy(() -> tc.classify(null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("text");
        }
    }

    @Nested
    @DisplayName("runtime output-length guard")
    class RuntimeGuard {

        @Test
        void throwsOnWrongLengthOutput() {
            var model = InMemoryInferenceModel.withFunction(2, input -> new float[]{1.0f, 2.0f, 3.0f});
            var tc = new TextClassifier(model, List.of("a", "b"));
            assertThatThrownBy(() -> tc.classify("text"))
                .isInstanceOf(InferenceException.class)
                .hasMessageContaining("2")
                .hasMessageContaining("3");
        }
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks -Dtest=TextClassifierTest`
Expected: COMPILATION FAILURE

- [ ] **Step 3: Implement ClassificationResult**

```java
package io.casehub.inference.tasks;

import java.util.Map;
import java.util.Objects;

public record ClassificationResult(String label, float confidence, Map<String, Float> scores) {

    public ClassificationResult {
        Objects.requireNonNull(label, "label must not be null");
        if (confidence < 0 || confidence > 1)
            throw new IllegalArgumentException("confidence must be in [0,1]");
        Objects.requireNonNull(scores, "scores must not be null");
        scores = Map.copyOf(scores);
    }
}
```

- [ ] **Step 4: Implement TextClassifier**

```java
package io.casehub.inference.tasks;

import io.casehub.inference.InferenceException;
import io.casehub.inference.InferenceInput;
import io.casehub.inference.InferenceModel;
import io.casehub.inference.InferenceOutput;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class TextClassifier {

    private final InferenceModel model;
    private final List<String> labels;

    public TextClassifier(InferenceModel model, List<String> labels) {
        if (model == null) throw new IllegalArgumentException("model must not be null");
        if (labels == null || labels.isEmpty())
            throw new IllegalArgumentException("labels must not be null or empty");
        this.labels = List.copyOf(labels);
        model.outputSize().ifPresent(size -> {
            if (size != this.labels.size()) {
                throw new IllegalArgumentException(
                    "labels size (" + this.labels.size() + ") does not match outputSize (" + size + ")");
            }
        });
        this.model = model;
    }

    public ClassificationResult classify(String text) {
        if (text == null) throw new IllegalArgumentException("text must not be null");

        InferenceOutput output = model.run(InferenceInput.of(text));
        float[] values = output.values();

        if (values.length != labels.size()) {
            throw new InferenceException(
                "Expected " + labels.size() + " output values, got " + values.length);
        }

        float[] probs = Softmax.apply(values);

        int argmax = 0;
        for (int i = 1; i < probs.length; i++) {
            if (probs[i] > probs[argmax]) argmax = i;
        }

        Map<String, Float> scores = new LinkedHashMap<>(labels.size());
        for (int i = 0; i < labels.size(); i++) {
            scores.put(labels.get(i), probs[i]);
        }

        return new ClassificationResult(labels.get(argmax), probs[argmax], scores);
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks -Dtest=TextClassifierTest`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```
git add inference-tasks/src/main/java/io/casehub/inference/tasks/ClassificationResult.java
git add inference-tasks/src/main/java/io/casehub/inference/tasks/TextClassifier.java
git add inference-tasks/src/test/java/io/casehub/inference/tasks/TextClassifierTest.java
git commit -m "feat(#4): TextClassifier — labeled classification with softmax, Map.copyOf, runtime guard"
```

---

### Task 5: ScalarRegressor + tests

**Files:**
- Create: `inference-tasks/src/main/java/io/casehub/inference/tasks/ScalarRegressor.java`
- Create: `inference-tasks/src/test/java/io/casehub/inference/tasks/ScalarRegressorTest.java`

- [ ] **Step 1: Write the failing tests**

```java
package io.casehub.inference.tasks;

import io.casehub.inference.InferenceException;
import io.casehub.inference.InferenceInput;
import io.casehub.inference.InferenceModel;
import io.casehub.inference.InferenceOutput;
import io.casehub.inference.inmem.InMemoryInferenceModel;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.OptionalInt;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ScalarRegressorTest {

    @Nested
    @DisplayName("predict()")
    class Predict {

        @Test
        void returnsRawScalarValue() {
            var model = InMemoryInferenceModel.returning(0.73f);
            var regressor = new ScalarRegressor(model);
            assertThat(regressor.predict("some text")).isEqualTo(0.73f);
        }

        @Test
        void noSoftmaxApplied() {
            var model = InMemoryInferenceModel.returning(5.0f);
            var regressor = new ScalarRegressor(model);
            assertThat(regressor.predict("text")).isEqualTo(5.0f);
        }

        @Test
        void negativeValuesPreserved() {
            var model = InMemoryInferenceModel.returning(-0.5f);
            var regressor = new ScalarRegressor(model);
            assertThat(regressor.predict("text")).isEqualTo(-0.5f);
        }
    }

    @Nested
    @DisplayName("construction validation")
    class ConstructionValidation {

        @Test
        void rejectsOutputSizeMismatch() {
            var model = InMemoryInferenceModel.returning(1.0f, 2.0f, 3.0f);
            assertThatThrownBy(() -> new ScalarRegressor(model))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("1")
                .hasMessageContaining("3");
        }

        @Test
        void rejectsNullModel() {
            assertThatThrownBy(() -> new ScalarRegressor(null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("model");
        }

        @Test
        void acceptsUnknownOutputSize() {
            InferenceModel model = new InferenceModel() {
                @Override public InferenceOutput run(InferenceInput input) {
                    return new InferenceOutput(new float[]{0.42f});
                }
                @Override public List<InferenceOutput> runBatch(List<InferenceInput> inputs) {
                    return inputs.stream().map(this::run).toList();
                }
                @Override public OptionalInt outputSize() { return OptionalInt.empty(); }
                @Override public void close() {}
            };
            var regressor = new ScalarRegressor(model);
            assertThat(regressor.predict("text")).isEqualTo(0.42f);
        }
    }

    @Nested
    @DisplayName("argument validation")
    class ArgumentValidation {

        @Test
        void rejectsNullText() {
            var model = InMemoryInferenceModel.returning(1.0f);
            var regressor = new ScalarRegressor(model);
            assertThatThrownBy(() -> regressor.predict(null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("text");
        }
    }

    @Nested
    @DisplayName("runtime output-length guard")
    class RuntimeGuard {

        @Test
        void throwsOnMultiElementOutput() {
            var model = InMemoryInferenceModel.withFunction(1, input -> new float[]{1.0f, 2.0f});
            var regressor = new ScalarRegressor(model);
            assertThatThrownBy(() -> regressor.predict("text"))
                .isInstanceOf(InferenceException.class)
                .hasMessageContaining("1")
                .hasMessageContaining("2");
        }
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks -Dtest=ScalarRegressorTest`
Expected: COMPILATION FAILURE

- [ ] **Step 3: Implement ScalarRegressor**

```java
package io.casehub.inference.tasks;

import io.casehub.inference.InferenceException;
import io.casehub.inference.InferenceInput;
import io.casehub.inference.InferenceModel;
import io.casehub.inference.InferenceOutput;

public final class ScalarRegressor {

    private static final int EXPECTED_SIZE = 1;

    private final InferenceModel model;

    public ScalarRegressor(InferenceModel model) {
        if (model == null) throw new IllegalArgumentException("model must not be null");
        model.outputSize().ifPresent(size -> {
            if (size != EXPECTED_SIZE) {
                throw new IllegalArgumentException(
                    "ScalarRegressor requires outputSize " + EXPECTED_SIZE + ", got " + size);
            }
        });
        this.model = model;
    }

    public float predict(String text) {
        if (text == null) throw new IllegalArgumentException("text must not be null");

        InferenceOutput output = model.run(InferenceInput.of(text));
        float[] values = output.values();

        if (values.length != EXPECTED_SIZE) {
            throw new InferenceException(
                "Expected " + EXPECTED_SIZE + " output values, got " + values.length);
        }

        return values[0];
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks -Dtest=ScalarRegressorTest`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```
git add inference-tasks/src/main/java/io/casehub/inference/tasks/ScalarRegressor.java
git add inference-tasks/src/test/java/io/casehub/inference/tasks/ScalarRegressorTest.java
git commit -m "feat(#4): ScalarRegressor — raw scalar output with runtime guard"
```

---

### Task 6: RankedResult + CrossEncoderReranker + tests

**Files:**
- Create: `inference-tasks/src/main/java/io/casehub/inference/tasks/RankedResult.java`
- Create: `inference-tasks/src/main/java/io/casehub/inference/tasks/CrossEncoderReranker.java`
- Create: `inference-tasks/src/test/java/io/casehub/inference/tasks/CrossEncoderRerankerTest.java`

- [ ] **Step 1: Write the failing tests**

```java
package io.casehub.inference.tasks;

import io.casehub.inference.InferenceException;
import io.casehub.inference.InferenceInput;
import io.casehub.inference.InferenceModel;
import io.casehub.inference.InferenceOutput;
import io.casehub.inference.inmem.InMemoryInferenceModel;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.OptionalInt;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class CrossEncoderRerankerTest {

    @Nested
    @DisplayName("score()")
    class Score {

        @Test
        void returnsRawScoreFromModel() {
            var model = InMemoryInferenceModel.returning(0.85f);
            var reranker = new CrossEncoderReranker(model);
            assertThat(reranker.score("query", "candidate")).isEqualTo(0.85f);
        }
    }

    @Nested
    @DisplayName("rerank()")
    class Rerank {

        @Test
        void sortsByDescendingScore() {
            var model = InMemoryInferenceModel.withFunction(1, input -> {
                String candidate = input.texts().get(1);
                return switch (candidate) {
                    case "low" -> new float[]{0.1f};
                    case "mid" -> new float[]{0.5f};
                    case "high" -> new float[]{0.9f};
                    default -> new float[]{0.0f};
                };
            });
            var reranker = new CrossEncoderReranker(model);
            List<RankedResult> results = reranker.rerank("query", List.of("low", "mid", "high"));
            assertThat(results).hasSize(3);
            assertThat(results.get(0).text()).isEqualTo("high");
            assertThat(results.get(0).score()).isEqualTo(0.9f);
            assertThat(results.get(1).text()).isEqualTo("mid");
            assertThat(results.get(2).text()).isEqualTo("low");
        }

        @Test
        void preservesOriginalIndices() {
            var model = InMemoryInferenceModel.withFunction(1, input -> {
                String candidate = input.texts().get(1);
                return switch (candidate) {
                    case "a" -> new float[]{0.3f};
                    case "b" -> new float[]{0.9f};
                    case "c" -> new float[]{0.1f};
                    default -> new float[]{0.0f};
                };
            });
            var reranker = new CrossEncoderReranker(model);
            List<RankedResult> results = reranker.rerank("q", List.of("a", "b", "c"));
            assertThat(results.get(0).originalIndex()).isEqualTo(1); // "b" was index 1
            assertThat(results.get(1).originalIndex()).isEqualTo(0); // "a" was index 0
            assertThat(results.get(2).originalIndex()).isEqualTo(2); // "c" was index 2
        }

        @Test
        void singleCandidateWorks() {
            var model = InMemoryInferenceModel.returning(0.7f);
            var reranker = new CrossEncoderReranker(model);
            List<RankedResult> results = reranker.rerank("q", List.of("only"));
            assertThat(results).hasSize(1);
            assertThat(results.get(0).text()).isEqualTo("only");
            assertThat(results.get(0).originalIndex()).isEqualTo(0);
        }

        @Test
        void resultListIsUnmodifiable() {
            var model = InMemoryInferenceModel.returning(0.5f);
            var reranker = new CrossEncoderReranker(model);
            List<RankedResult> results = reranker.rerank("q", List.of("a"));
            assertThatThrownBy(() -> results.add(new RankedResult("x", 0f, 0)))
                .isInstanceOf(UnsupportedOperationException.class);
        }

        @Test
        void duplicateCandidatesScoredIndependently() {
            var model = InMemoryInferenceModel.returning(0.5f);
            var reranker = new CrossEncoderReranker(model);
            List<RankedResult> results = reranker.rerank("q", List.of("same", "same"));
            assertThat(results).hasSize(2);
            assertThat(results.get(0).originalIndex())
                .isNotEqualTo(results.get(1).originalIndex());
        }
    }

    @Nested
    @DisplayName("construction validation")
    class ConstructionValidation {

        @Test
        void rejectsOutputSizeMismatch() {
            var model = InMemoryInferenceModel.returning(1.0f, 2.0f);
            assertThatThrownBy(() -> new CrossEncoderReranker(model))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("1")
                .hasMessageContaining("2");
        }

        @Test
        void rejectsNullModel() {
            assertThatThrownBy(() -> new CrossEncoderReranker(null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("model");
        }
    }

    @Nested
    @DisplayName("argument validation")
    class ArgumentValidation {

        @Test
        void scoreRejectsNullQuery() {
            var model = InMemoryInferenceModel.returning(0.5f);
            var reranker = new CrossEncoderReranker(model);
            assertThatThrownBy(() -> reranker.score(null, "c"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("query");
        }

        @Test
        void scoreRejectsNullCandidate() {
            var model = InMemoryInferenceModel.returning(0.5f);
            var reranker = new CrossEncoderReranker(model);
            assertThatThrownBy(() -> reranker.score("q", null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("candidate");
        }

        @Test
        void rerankRejectsNullQuery() {
            var model = InMemoryInferenceModel.returning(0.5f);
            var reranker = new CrossEncoderReranker(model);
            assertThatThrownBy(() -> reranker.rerank(null, List.of("a")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("query");
        }

        @Test
        void rerankRejectsNullCandidates() {
            var model = InMemoryInferenceModel.returning(0.5f);
            var reranker = new CrossEncoderReranker(model);
            assertThatThrownBy(() -> reranker.rerank("q", null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("candidates");
        }

        @Test
        void rerankRejectsEmptyCandidates() {
            var model = InMemoryInferenceModel.returning(0.5f);
            var reranker = new CrossEncoderReranker(model);
            assertThatThrownBy(() -> reranker.rerank("q", List.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("candidates");
        }

        @Test
        void rerankRejectsNullElements() {
            var model = InMemoryInferenceModel.returning(0.5f);
            var reranker = new CrossEncoderReranker(model);
            var candidates = new ArrayList<String>();
            candidates.add("a");
            candidates.add(null);
            assertThatThrownBy(() -> reranker.rerank("q", candidates))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("candidates[1]");
        }
    }

    @Nested
    @DisplayName("runtime output-length guard")
    class RuntimeGuard {

        @Test
        void scoreThrowsOnMultiElementOutput() {
            var model = InMemoryInferenceModel.withFunction(1, input -> new float[]{1.0f, 2.0f});
            var reranker = new CrossEncoderReranker(model);
            assertThatThrownBy(() -> reranker.score("q", "c"))
                .isInstanceOf(InferenceException.class)
                .hasMessageContaining("1")
                .hasMessageContaining("2");
        }

        @Test
        void rerankThrowsOnMultiElementOutput() {
            var model = InMemoryInferenceModel.withFunction(1, input -> new float[]{1.0f, 2.0f});
            var reranker = new CrossEncoderReranker(model);
            assertThatThrownBy(() -> reranker.rerank("q", List.of("a")))
                .isInstanceOf(InferenceException.class);
        }
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks -Dtest=CrossEncoderRerankerTest`
Expected: COMPILATION FAILURE

- [ ] **Step 3: Implement RankedResult**

```java
package io.casehub.inference.tasks;

public record RankedResult(String text, float score, int originalIndex) {}
```

- [ ] **Step 4: Implement CrossEncoderReranker**

```java
package io.casehub.inference.tasks;

import io.casehub.inference.InferenceException;
import io.casehub.inference.InferenceInput;
import io.casehub.inference.InferenceModel;
import io.casehub.inference.InferenceOutput;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

public final class CrossEncoderReranker {

    private static final int EXPECTED_SIZE = 1;

    private final InferenceModel model;

    public CrossEncoderReranker(InferenceModel model) {
        if (model == null) throw new IllegalArgumentException("model must not be null");
        model.outputSize().ifPresent(size -> {
            if (size != EXPECTED_SIZE) {
                throw new IllegalArgumentException(
                    "CrossEncoderReranker requires outputSize " + EXPECTED_SIZE + ", got " + size);
            }
        });
        this.model = model;
    }

    public float score(String query, String candidate) {
        if (query == null) throw new IllegalArgumentException("query must not be null");
        if (candidate == null) throw new IllegalArgumentException("candidate must not be null");

        InferenceOutput output = model.run(InferenceInput.pair(query, candidate));
        float[] values = output.values();

        if (values.length != EXPECTED_SIZE) {
            throw new InferenceException(
                "Expected " + EXPECTED_SIZE + " output values, got " + values.length);
        }

        return values[0];
    }

    public List<RankedResult> rerank(String query, List<String> candidates) {
        if (query == null) throw new IllegalArgumentException("query must not be null");
        if (candidates == null) throw new IllegalArgumentException("candidates must not be null");
        if (candidates.isEmpty())
            throw new IllegalArgumentException("candidates must not be empty");
        for (int i = 0; i < candidates.size(); i++) {
            if (candidates.get(i) == null) {
                throw new IllegalArgumentException("candidates[" + i + "] must not be null");
            }
        }

        List<InferenceInput> inputs = new ArrayList<>(candidates.size());
        for (String candidate : candidates) {
            inputs.add(InferenceInput.pair(query, candidate));
        }

        List<InferenceOutput> outputs = model.runBatch(inputs);

        List<RankedResult> results = new ArrayList<>(candidates.size());
        for (int i = 0; i < outputs.size(); i++) {
            float[] values = outputs.get(i).values();
            if (values.length != EXPECTED_SIZE) {
                throw new InferenceException(
                    "Expected " + EXPECTED_SIZE + " output values, got " + values.length);
            }
            results.add(new RankedResult(candidates.get(i), values[0], i));
        }

        results.sort(Comparator.comparingDouble(RankedResult::score).reversed());
        return Collections.unmodifiableList(results);
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks -Dtest=CrossEncoderRerankerTest`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```
git add inference-tasks/src/main/java/io/casehub/inference/tasks/RankedResult.java
git add inference-tasks/src/main/java/io/casehub/inference/tasks/CrossEncoderReranker.java
git add inference-tasks/src/test/java/io/casehub/inference/tasks/CrossEncoderRerankerTest.java
git commit -m "feat(#4): CrossEncoderReranker — score + batch rerank with runtime guard"
```

---

### Task 7: ArchUnit DependencyConstraintTest

**Files:**
- Create: `inference-tasks/src/test/java/io/casehub/inference/tasks/DependencyConstraintTest.java`

- [ ] **Step 1: Write the ArchUnit test**

```java
package io.casehub.inference.tasks;

import com.tngtech.archunit.base.DescribedPredicate;
import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

@AnalyzeClasses(packages = "io.casehub.inference.tasks")
class DependencyConstraintTest {

    @ArchTest
    static final ArchRule noQuarkus = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("io.quarkus..", "jakarta..");

    @ArchTest
    static final ArchRule noSpring = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("org.springframework..");

    @ArchTest
    static final ArchRule noLangChain4j = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("dev.langchain4j..");

    @ArchTest
    static final ArchRule noOnnxRuntime = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("ai.onnxruntime..");

    @ArchTest
    static final ArchRule noDjl = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("ai.djl..");

    @ArchTest
    static final ArchRule noCasehubDomain = noClasses()
        .that().resideInAPackage("io.casehub.inference.tasks..")
        .should().dependOnClassesThat(
            DescribedPredicate.describe("casehub domain classes",
                (JavaClass cls) -> cls.getPackageName().startsWith("io.casehub.")
                    && !cls.getPackageName().startsWith("io.casehub.inference")));
}
```

- [ ] **Step 2: Run all tests including ArchUnit**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks`
Expected: All tests PASS (Softmax, NliClassifier, TextClassifier, ScalarRegressor, CrossEncoderReranker, DependencyConstraint)

- [ ] **Step 3: Commit**

```
git add inference-tasks/src/test/java/io/casehub/inference/tasks/DependencyConstraintTest.java
git commit -m "test(#4): ArchUnit DependencyConstraintTest — framework + casehub domain exclusion"
```

---

### Task 8: Full build verification + final commit

- [ ] **Step 1: Run full module build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl inference-tasks`
Expected: BUILD SUCCESS, all tests pass, JAR produced

- [ ] **Step 2: Run full project build to verify no regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS across all modules

- [ ] **Step 3: Verify test count**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks 2>&1 | grep "Tests run:"`
Expected: ~40+ tests, 0 failures, 0 errors

# Inference SPI Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the InferenceModel SPI (inference-api), ONNX Runtime implementation (inference-runtime), and deterministic test stubs (inference-inmem) per the spec at `specs/2026-06-07-inference-spi-design.md` rev 4.

**Architecture:** Three modules following the platform three-tier pattern: inference-api (Tier 1 — pure Java SPI), inference-runtime (Tier 3 — ONNX Runtime JNI + DJL Tokenizers JNI), inference-inmem (stub tier — depends only on api). Callers work with `InferenceModel`, never ONNX types. `InferenceInput` is text-only; the runtime handles tokenization internally. `InferenceOutput` carries raw `float[]` values; task adapters (C4) interpret them.

**Tech Stack:** Java 21, ONNX Runtime JVM 1.26.0, DJL HuggingFace Tokenizers 0.36.0, ArchUnit 1.4.1, JUnit 5, AssertJ

**Spec:** `specs/2026-06-07-inference-spi-design.md` (rev 4)

**Issue:** casehubio/neural-text#3

---

## File Map

### inference-api (new files)

| File | Purpose |
|------|---------|
| `inference-api/src/main/java/io/casehub/inference/InferenceException.java` | Unchecked exception base |
| `inference-api/src/main/java/io/casehub/inference/InferenceInput.java` | Text input record |
| `inference-api/src/main/java/io/casehub/inference/InferenceOutput.java` | Output values record |
| `inference-api/src/main/java/io/casehub/inference/InferenceModel.java` | SPI interface |
| `inference-api/src/test/java/io/casehub/inference/InferenceInputTest.java` | Input validation + immutability |
| `inference-api/src/test/java/io/casehub/inference/InferenceOutputTest.java` | Defensive copy + equality + toString |
| `inference-api/src/test/java/io/casehub/inference/DependencyConstraintTest.java` | ArchUnit |

### inference-inmem (new files)

| File | Purpose |
|------|---------|
| `inference-inmem/src/main/java/io/casehub/inference/inmem/InMemoryInferenceModel.java` | Deterministic stub |
| `inference-inmem/src/test/java/io/casehub/inference/inmem/InMemoryInferenceModelTest.java` | All behaviors |
| `inference-inmem/src/test/java/io/casehub/inference/inmem/DependencyConstraintTest.java` | ArchUnit |

### inference-runtime (new + modified files)

| File | Purpose |
|------|---------|
| `inference-runtime/src/main/java/io/casehub/inference/runtime/ModelConfig.java` | **New** — construction config |
| `inference-runtime/src/main/java/io/casehub/inference/runtime/ModelLoadException.java` | **New** — construction failure |
| `inference-runtime/src/main/java/io/casehub/inference/runtime/OnnxInferenceModel.java` | **New** — ONNX implementation |
| `inference-runtime/src/main/java/io/casehub/inference/runtime/OnnxSessionLoader.java` | **Delete** — C2 bridge |
| `inference-runtime/src/main/java/io/casehub/inference/runtime/RawInference.java` | **Delete** — C2 bridge |
| `inference-runtime/src/main/java/io/casehub/inference/runtime/TokenizerLoader.java` | **Delete** — C2 bridge |
| `inference-runtime/src/test/java/io/casehub/inference/runtime/ModelConfigTest.java` | **New** — config validation |
| `inference-runtime/src/test/java/io/casehub/inference/runtime/OnnxInferenceModelTest.java` | **New** — integration tests |
| `inference-runtime/src/test/java/io/casehub/inference/runtime/DependencyConstraintTest.java` | **New** — ArchUnit |
| `inference-runtime/src/test/resources/test-model/tokenizer.json` | **New** — real bert-base-uncased tokenizer |
| `inference-runtime/src/test/resources/test-model/model.onnx` | **New** — synthetic ONNX model |
| `inference-runtime/src/test/resources/test-model/wrong-inputs-model.onnx` | **New** — validation test model |
| `inference-runtime/pom.xml` | **Modify** — add download-maven-plugin for test tokenizer |

### inference-quarkus (modified files)

| File | Purpose |
|------|---------|
| `inference-quarkus/src/main/java/io/casehub/inference/quarkus/gate/NativeImageGateCommand.java` | **Modify** — use OnnxInferenceModel instead of bridge code |

### Parent POM (modified)

| File | Purpose |
|------|---------|
| `pom.xml` | **Modify** — add ArchUnit to dependencyManagement |

---

## Task 1: Project Setup — ArchUnit Dependency

**Files:**
- Modify: `pom.xml` (parent)
- Modify: `inference-api/pom.xml`
- Modify: `inference-inmem/pom.xml`
- Modify: `inference-runtime/pom.xml`

- [ ] **Step 1: Add ArchUnit to parent POM dependencyManagement**

In `pom.xml` (root), add inside `<dependencyManagement><dependencies>`:

```xml
<dependency>
  <groupId>com.tngtech.archunit</groupId>
  <artifactId>archunit-junit5</artifactId>
  <version>1.4.1</version>
  <scope>test</scope>
</dependency>
```

- [ ] **Step 2: Add ArchUnit test dependency to each module POM**

In `inference-api/pom.xml`, `inference-inmem/pom.xml`, and `inference-runtime/pom.xml`, add inside `<dependencies>`:

```xml
<dependency>
  <groupId>com.tngtech.archunit</groupId>
  <artifactId>archunit-junit5</artifactId>
  <scope>test</scope>
</dependency>
```

- [ ] **Step 3: Verify build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests -pl inference-api,inference-inmem,inference-runtime`

Expected: BUILD SUCCESS (no compilation needed yet — just dependency resolution)

- [ ] **Step 4: Commit**

```
git add pom.xml inference-api/pom.xml inference-inmem/pom.xml inference-runtime/pom.xml
git commit -m "build(#3): add ArchUnit test dependency to inference modules"
```

---

## Task 2: inference-api — SPI Types + Tests + ArchUnit

**Files:**
- Create: `inference-api/src/main/java/io/casehub/inference/InferenceException.java`
- Create: `inference-api/src/main/java/io/casehub/inference/InferenceInput.java`
- Create: `inference-api/src/main/java/io/casehub/inference/InferenceOutput.java`
- Create: `inference-api/src/main/java/io/casehub/inference/InferenceModel.java`
- Create: `inference-api/src/test/java/io/casehub/inference/InferenceInputTest.java`
- Create: `inference-api/src/test/java/io/casehub/inference/InferenceOutputTest.java`
- Create: `inference-api/src/test/java/io/casehub/inference/DependencyConstraintTest.java`

- [ ] **Step 1: Write InferenceInput tests**

```java
package io.casehub.inference;

import org.junit.jupiter.api.Test;
import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.*;

class InferenceInputTest {

    @Test
    void ofCreatesSingleText() {
        var input = InferenceInput.of("hello");
        assertThat(input.texts()).containsExactly("hello");
    }

    @Test
    void pairCreatesTwoTexts() {
        var input = InferenceInput.pair("premise", "hypothesis");
        assertThat(input.texts()).containsExactly("premise", "hypothesis");
    }

    @Test
    void rejectsNullTexts() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new InferenceInput(null));
    }

    @Test
    void rejectsEmptyTexts() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new InferenceInput(List.of()));
    }

    @Test
    void rejectsThreeTexts() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new InferenceInput(List.of("a", "b", "c")))
            .withMessageContaining("at most 2");
    }

    @Test
    void ofRejectsNull() {
        assertThatNullPointerException()
            .isThrownBy(() -> InferenceInput.of(null));
    }

    @Test
    void pairRejectsNullFirst() {
        assertThatNullPointerException()
            .isThrownBy(() -> InferenceInput.pair(null, "b"));
    }

    @Test
    void pairRejectsNullSecond() {
        assertThatNullPointerException()
            .isThrownBy(() -> InferenceInput.pair("a", null));
    }

    @Test
    void defensiveCopyOnConstruction() {
        var mutable = new ArrayList<>(List.of("original"));
        var input = new InferenceInput(mutable);
        mutable.set(0, "mutated");
        assertThat(input.texts()).containsExactly("original");
    }

    @Test
    void textsListIsUnmodifiable() {
        var input = InferenceInput.of("hello");
        assertThatExceptionOfType(UnsupportedOperationException.class)
            .isThrownBy(() -> input.texts().add("mutate"));
    }
}
```

- [ ] **Step 2: Write InferenceOutput tests**

```java
package io.casehub.inference;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.*;

class InferenceOutputTest {

    @Test
    void rejectsNullValues() {
        assertThatNullPointerException()
            .isThrownBy(() -> new InferenceOutput(null));
    }

    @Test
    void defensiveCopyOnConstruction() {
        float[] source = {1.0f, 2.0f, 3.0f};
        var output = new InferenceOutput(source);
        source[0] = 99.0f;
        assertThat(output.values()[0]).isEqualTo(1.0f);
    }

    @Test
    void defensiveCopyOnAccess() {
        var output = new InferenceOutput(new float[]{1.0f, 2.0f, 3.0f});
        float[] first = output.values();
        first[0] = 99.0f;
        assertThat(output.values()[0]).isEqualTo(1.0f);
    }

    @Test
    void equalityUsesArrayContents() {
        var a = new InferenceOutput(new float[]{1.0f, 2.0f});
        var b = new InferenceOutput(new float[]{1.0f, 2.0f});
        assertThat(a).isEqualTo(b);
        assertThat(a.hashCode()).isEqualTo(b.hashCode());
    }

    @Test
    void inequalityForDifferentValues() {
        var a = new InferenceOutput(new float[]{1.0f, 2.0f});
        var b = new InferenceOutput(new float[]{1.0f, 3.0f});
        assertThat(a).isNotEqualTo(b);
    }

    @Test
    void toStringShowsAllValuesWhenSmall() {
        var output = new InferenceOutput(new float[]{0.1f, 0.8f, 0.1f});
        assertThat(output.toString()).contains("0.1").contains("0.8");
    }

    @Test
    void toStringTruncatesLargeArrays() {
        float[] large = new float[100];
        large[0] = 0.5f;
        var output = new InferenceOutput(large);
        String s = output.toString();
        assertThat(s).contains("100 values");
        assertThat(s).doesNotContain("0.0, 0.0, 0.0, 0.0, 0.0, 0.0");
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-api`

Expected: COMPILATION ERROR — types not yet defined

- [ ] **Step 4: Implement all inference-api types**

**`InferenceException.java`:**

```java
package io.casehub.inference;

public class InferenceException extends RuntimeException {

    public InferenceException(String message) {
        super(message);
    }

    public InferenceException(String message, Throwable cause) {
        super(message, cause);
    }
}
```

**`InferenceInput.java`:**

```java
package io.casehub.inference;

import java.util.List;
import java.util.Objects;

public record InferenceInput(List<String> texts) {

    public InferenceInput {
        if (texts == null || texts.isEmpty()) {
            throw new IllegalArgumentException("texts must not be empty");
        }
        if (texts.size() > 2) {
            throw new IllegalArgumentException(
                "at most 2 texts supported (single text or text pair)");
        }
        texts = List.copyOf(texts);
    }

    public static InferenceInput of(String text) {
        return new InferenceInput(List.of(
            Objects.requireNonNull(text, "text must not be null")));
    }

    public static InferenceInput pair(String first, String second) {
        return new InferenceInput(List.of(
            Objects.requireNonNull(first, "first must not be null"),
            Objects.requireNonNull(second, "second must not be null")));
    }
}
```

**`InferenceOutput.java`:**

```java
package io.casehub.inference;

import java.util.Arrays;
import java.util.Objects;

public record InferenceOutput(float[] values) {

    public InferenceOutput {
        Objects.requireNonNull(values, "values must not be null");
        values = values.clone();
    }

    @Override
    public float[] values() {
        return values.clone();
    }

    @Override
    public boolean equals(Object o) {
        return o instanceof InferenceOutput other
            && Arrays.equals(values, other.values);
    }

    @Override
    public int hashCode() {
        return Arrays.hashCode(values);
    }

    @Override
    public String toString() {
        if (values.length <= 5) {
            return "InferenceOutput" + Arrays.toString(values);
        }
        return "InferenceOutput[" + values[0] + ", " + values[1] + ", " + values[2]
            + ", ... (" + values.length + " values)]";
    }
}
```

**`InferenceModel.java`:**

```java
package io.casehub.inference;

import java.util.List;
import java.util.OptionalInt;

/**
 * SPI for text-in, tensor-out inference. Thread-safe for concurrent
 * {@link #run}/{@link #runBatch} calls. One-shot lifecycle: construct,
 * use, close. Post-close calls throw {@link InferenceException}.
 */
public interface InferenceModel extends AutoCloseable {

    InferenceOutput run(InferenceInput input);

    /**
     * Batch inference. Returns one output per input, in order. The returned
     * list is unmodifiable.
     *
     * @throws IllegalArgumentException if inputs is null or contains null elements
     * @throws InferenceException if model is closed
     */
    List<InferenceOutput> runBatch(List<InferenceInput> inputs);

    /**
     * Number of values in each output. Empty if unknown or dynamic.
     * Task adapters validate at construction:
     * {@code model.outputSize().ifPresent(size -> { if (size != 3) throw ... })}
     */
    default OptionalInt outputSize() {
        return OptionalInt.empty();
    }

    @Override
    void close();
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-api`

Expected: All tests PASS

- [ ] **Step 6: Write ArchUnit test**

```java
package io.casehub.inference;

import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

@AnalyzeClasses(packages = "io.casehub.inference")
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
}
```

- [ ] **Step 7: Run all tests including ArchUnit**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-api`

Expected: All tests PASS

- [ ] **Step 8: Commit**

```
git add inference-api/src/
git commit -m "feat(#3): inference-api — InferenceModel SPI, InferenceInput, InferenceOutput, InferenceException"
```

---

## Task 3: inference-inmem — InMemoryInferenceModel + Tests + ArchUnit

**Files:**
- Create: `inference-inmem/src/main/java/io/casehub/inference/inmem/InMemoryInferenceModel.java`
- Create: `inference-inmem/src/test/java/io/casehub/inference/inmem/InMemoryInferenceModelTest.java`
- Create: `inference-inmem/src/test/java/io/casehub/inference/inmem/DependencyConstraintTest.java`

- [ ] **Step 1: Write InMemoryInferenceModel tests**

```java
package io.casehub.inference.inmem;

import io.casehub.inference.InferenceException;
import io.casehub.inference.InferenceInput;
import io.casehub.inference.InferenceOutput;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.*;

class InMemoryInferenceModelTest {

    // --- returning() factory ---

    @Test
    void returningProducesExpectedValues() {
        var model = InMemoryInferenceModel.returning(0.9f, 0.05f, 0.05f);
        var output = model.run(InferenceInput.of("anything"));
        assertThat(output.values()).containsExactly(0.9f, 0.05f, 0.05f);
    }

    @Test
    void returningOutputSizeMatchesValues() {
        var model = InMemoryInferenceModel.returning(0.1f, 0.8f, 0.1f);
        assertThat(model.outputSize()).hasValue(3);
    }

    @Test
    void returningSameOutputRegardlessOfInput() {
        var model = InMemoryInferenceModel.returning(1.0f, 0.0f);
        var a = model.run(InferenceInput.of("hello"));
        var b = model.run(InferenceInput.pair("x", "y"));
        assertThat(a).isEqualTo(b);
    }

    @Test
    void returningClonesVarargsOnConstruction() {
        float[] source = {1.0f, 2.0f};
        var model = InMemoryInferenceModel.returning(source);
        source[0] = 99.0f;
        assertThat(model.run(InferenceInput.of("test")).values()[0]).isEqualTo(1.0f);
    }

    @Test
    void returningClonesOnEachCall() {
        var model = InMemoryInferenceModel.returning(1.0f, 2.0f);
        float[] first = model.run(InferenceInput.of("a")).values();
        first[0] = 99.0f;
        assertThat(model.run(InferenceInput.of("b")).values()[0]).isEqualTo(1.0f);
    }

    // --- withFunction() factory ---

    @Test
    void withFunctionReceivesCorrectInput() {
        var model = InMemoryInferenceModel.withFunction(1, input -> {
            return new float[]{input.texts().size()};
        });
        assertThat(model.run(InferenceInput.of("one")).values()).containsExactly(1.0f);
        assertThat(model.run(InferenceInput.pair("a", "b")).values()).containsExactly(2.0f);
    }

    @Test
    void withFunctionOutputSizeReturnsConfigured() {
        var model = InMemoryInferenceModel.withFunction(5, input -> new float[5]);
        assertThat(model.outputSize()).hasValue(5);
    }

    @Test
    void withFunctionRejectsNullFunction() {
        assertThatNullPointerException()
            .isThrownBy(() -> InMemoryInferenceModel.withFunction(3, null));
    }

    @Test
    void withFunctionRejectsNonPositiveOutputSize() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> InMemoryInferenceModel.withFunction(0, input -> new float[0]));
    }

    // --- runBatch() ---

    @Test
    void runBatchReturnsOneOutputPerInput() {
        var model = InMemoryInferenceModel.returning(1.0f);
        var inputs = List.of(InferenceInput.of("a"), InferenceInput.of("b"), InferenceInput.of("c"));
        var outputs = model.runBatch(inputs);
        assertThat(outputs).hasSize(3);
    }

    @Test
    void runBatchEmptyListReturnsEmptyList() {
        var model = InMemoryInferenceModel.returning(1.0f);
        assertThat(model.runBatch(List.of())).isEmpty();
    }

    @Test
    void runBatchNullListThrowsIAE() {
        var model = InMemoryInferenceModel.returning(1.0f);
        assertThatIllegalArgumentException()
            .isThrownBy(() -> model.runBatch(null));
    }

    @Test
    void runBatchNullElementThrowsIAE() {
        var model = InMemoryInferenceModel.returning(1.0f);
        var inputs = new java.util.ArrayList<InferenceInput>();
        inputs.add(InferenceInput.of("ok"));
        inputs.add(null);
        assertThatIllegalArgumentException()
            .isThrownBy(() -> model.runBatch(inputs));
    }

    @Test
    void runBatchConsistentWithRun() {
        var model = InMemoryInferenceModel.returning(0.5f, 0.3f, 0.2f);
        var input = InferenceInput.of("test");
        var single = model.run(input);
        var batched = model.runBatch(List.of(input)).get(0);
        assertThat(batched).isEqualTo(single);
    }

    // --- Post-close contract ---

    @Test
    void runAfterCloseThrows() {
        var model = InMemoryInferenceModel.returning(1.0f);
        model.close();
        assertThatExceptionOfType(InferenceException.class)
            .isThrownBy(() -> model.run(InferenceInput.of("test")))
            .withMessageContaining("closed");
    }

    @Test
    void runBatchAfterCloseThrows() {
        var model = InMemoryInferenceModel.returning(1.0f);
        model.close();
        assertThatExceptionOfType(InferenceException.class)
            .isThrownBy(() -> model.runBatch(List.of(InferenceInput.of("test"))))
            .withMessageContaining("closed");
    }

    @Test
    void runBatchEmptyAfterCloseThrows() {
        var model = InMemoryInferenceModel.returning(1.0f);
        model.close();
        assertThatExceptionOfType(InferenceException.class)
            .isThrownBy(() -> model.runBatch(List.of()))
            .withMessageContaining("closed");
    }

    @Test
    void closeIsIdempotent() {
        var model = InMemoryInferenceModel.returning(1.0f);
        model.close();
        assertThatNoException().isThrownBy(model::close);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-inmem`

Expected: COMPILATION ERROR — `InMemoryInferenceModel` not yet defined

- [ ] **Step 3: Implement InMemoryInferenceModel**

```java
package io.casehub.inference.inmem;

import io.casehub.inference.InferenceException;
import io.casehub.inference.InferenceInput;
import io.casehub.inference.InferenceModel;
import io.casehub.inference.InferenceOutput;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;
import java.util.OptionalInt;
import java.util.function.Function;

/**
 * Deterministic {@link InferenceModel} stub for testing. No JNI, no native
 * libs — safe in all test contexts including {@code @QuarkusTest} and native image.
 */
public final class InMemoryInferenceModel implements InferenceModel {

    private final Function<InferenceInput, float[]> fn;
    private final int outputSize;
    private volatile boolean closed;

    private InMemoryInferenceModel(Function<InferenceInput, float[]> fn, int outputSize) {
        this.fn = fn;
        this.outputSize = outputSize;
    }

    /**
     * Creates a stub that always returns the same values regardless of input.
     * Clones varargs on construction and on each {@link #run} call.
     */
    public static InMemoryInferenceModel returning(float... values) {
        float[] snapshot = values.clone();
        return new InMemoryInferenceModel(input -> snapshot.clone(), snapshot.length);
    }

    /**
     * Creates a stub with custom logic per input. The provided function must
     * be thread-safe — the model delegates directly with no synchronization.
     */
    public static InMemoryInferenceModel withFunction(
            int outputSize, Function<InferenceInput, float[]> fn) {
        Objects.requireNonNull(fn, "fn must not be null");
        if (outputSize <= 0) {
            throw new IllegalArgumentException("outputSize must be positive");
        }
        return new InMemoryInferenceModel(fn, outputSize);
    }

    @Override
    public InferenceOutput run(InferenceInput input) {
        if (closed) throw new InferenceException("Model is closed");
        Objects.requireNonNull(input, "input must not be null");
        return new InferenceOutput(fn.apply(input));
    }

    @Override
    public List<InferenceOutput> runBatch(List<InferenceInput> inputs) {
        if (closed) throw new InferenceException("Model is closed");
        Objects.requireNonNull(inputs, "inputs must not be null");
        if (inputs.isEmpty()) return List.of();
        for (int i = 0; i < inputs.size(); i++) {
            if (inputs.get(i) == null) {
                throw new IllegalArgumentException("inputs[" + i + "] must not be null");
            }
        }
        List<InferenceOutput> results = new ArrayList<>(inputs.size());
        for (InferenceInput input : inputs) {
            results.add(new InferenceOutput(fn.apply(input)));
        }
        return Collections.unmodifiableList(results);
    }

    @Override
    public OptionalInt outputSize() {
        return OptionalInt.of(outputSize);
    }

    @Override
    public void close() {
        closed = true;
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-inmem`

Expected: All tests PASS

- [ ] **Step 5: Write ArchUnit test**

```java
package io.casehub.inference.inmem;

import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

@AnalyzeClasses(packages = "io.casehub.inference.inmem")
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
}
```

- [ ] **Step 6: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-inmem`

Expected: All tests PASS

- [ ] **Step 7: Commit**

```
git add inference-inmem/src/
git commit -m "feat(#3): inference-inmem — InMemoryInferenceModel with returning/withFunction factories"
```

---

## Task 4: inference-runtime — Test Resources Setup

**Files:**
- Create: `inference-runtime/src/test/resources/test-model/model.onnx`
- Create: `inference-runtime/src/test/resources/test-model/wrong-inputs-model.onnx`
- Create: `inference-runtime/src/test/resources/test-model/tokenizer.json`

- [ ] **Step 1: Generate test ONNX models with Python**

Write to `/tmp/generate_test_models.py`:

```python
import numpy as np
import onnx
from onnx import helper, TensorProto, numpy_helper

def make_model(input_names, output_dim, output_name='logits'):
    """Create minimal ONNX model: int64 inputs → float[batch, output_dim]."""
    inputs = [helper.make_tensor_value_info(name, TensorProto.INT64, ['batch', 'seq'])
              for name in input_names]
    output = helper.make_tensor_value_info(output_name, TensorProto.FLOAT, ['batch', output_dim])
    weight = numpy_helper.from_array(
        np.ones((1, output_dim), dtype=np.float32), name='weight')
    graph = helper.make_graph(
        nodes=[
            helper.make_node('Cast', [input_names[0]], ['float_ids'], to=TensorProto.FLOAT),
            helper.make_node('ReduceMean', ['float_ids'], ['mean'], axes=[1], keepdims=1),
            helper.make_node('MatMul', ['mean', 'weight'], [output_name]),
        ],
        name='test-model',
        inputs=inputs,
        outputs=[output],
        initializer=[weight],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 13)])
    onnx.checker.check_model(model)
    return model

import sys, os
out_dir = sys.argv[1]
os.makedirs(out_dir, exist_ok=True)

# Valid model: input_ids + attention_mask → [batch, 3]
valid = make_model(['input_ids', 'attention_mask'], 3)
onnx.save(valid, os.path.join(out_dir, 'model.onnx'))

# Wrong-inputs model: tokens + mask → [batch, 3]
wrong = make_model(['tokens', 'mask'], 3)
onnx.save(wrong, os.path.join(out_dir, 'wrong-inputs-model.onnx'))

print('Generated test models in', out_dir)
```

Run: `pip3 install onnx numpy && python3 /tmp/generate_test_models.py inference-runtime/src/test/resources/test-model`

Expected: Two .onnx files created (~1KB each)

- [ ] **Step 2: Download bert-base-uncased tokenizer.json**

Run: `curl -L -o inference-runtime/src/test/resources/test-model/tokenizer.json https://huggingface.co/bert-base-uncased/resolve/main/tokenizer.json`

Expected: `tokenizer.json` downloaded (~700KB)

- [ ] **Step 3: Verify test resources exist**

Run: `ls -la inference-runtime/src/test/resources/test-model/`

Expected: `model.onnx`, `wrong-inputs-model.onnx`, `tokenizer.json`

- [ ] **Step 4: Commit**

```
git add inference-runtime/src/test/resources/test-model/
git commit -m "test(#3): add synthetic ONNX test models and bert-base-uncased tokenizer"
```

---

## Task 5: inference-runtime — ModelConfig + ModelLoadException + OnnxInferenceModel

**Files:**
- Create: `inference-runtime/src/main/java/io/casehub/inference/runtime/ModelConfig.java`
- Create: `inference-runtime/src/main/java/io/casehub/inference/runtime/ModelLoadException.java`
- Create: `inference-runtime/src/main/java/io/casehub/inference/runtime/OnnxInferenceModel.java`
- Create: `inference-runtime/src/test/java/io/casehub/inference/runtime/ModelConfigTest.java`
- Create: `inference-runtime/src/test/java/io/casehub/inference/runtime/OnnxInferenceModelTest.java`
- Create: `inference-runtime/src/test/java/io/casehub/inference/runtime/DependencyConstraintTest.java`
- Delete: `inference-runtime/src/main/java/io/casehub/inference/runtime/OnnxSessionLoader.java`
- Delete: `inference-runtime/src/main/java/io/casehub/inference/runtime/RawInference.java`
- Delete: `inference-runtime/src/main/java/io/casehub/inference/runtime/TokenizerLoader.java`

- [ ] **Step 1: Write ModelConfig tests**

```java
package io.casehub.inference.runtime;

import org.junit.jupiter.api.Test;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.*;

class ModelConfigTest {

    private static final Path MODEL = Path.of("/tmp/model.onnx");
    private static final Path TOKENIZER = Path.of("/tmp/tokenizer.json");

    @Test
    void twoArgConstructorDefaultsTo512And0() {
        var config = new ModelConfig(MODEL, TOKENIZER);
        assertThat(config.maxSequenceLength()).isEqualTo(512);
        assertThat(config.intraOpThreads()).isEqualTo(0);
        assertThat(config.interOpThreads()).isEqualTo(0);
    }

    @Test
    void threeArgConstructorDefaultsThreadsTo0() {
        var config = new ModelConfig(MODEL, TOKENIZER, 256);
        assertThat(config.maxSequenceLength()).isEqualTo(256);
        assertThat(config.intraOpThreads()).isEqualTo(0);
        assertThat(config.interOpThreads()).isEqualTo(0);
    }

    @Test
    void rejectsNullModelPath() {
        assertThatNullPointerException()
            .isThrownBy(() -> new ModelConfig(null, TOKENIZER));
    }

    @Test
    void rejectsNullTokenizerPath() {
        assertThatNullPointerException()
            .isThrownBy(() -> new ModelConfig(MODEL, null));
    }

    @Test
    void rejectsZeroMaxSequenceLength() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new ModelConfig(MODEL, TOKENIZER, 0));
    }

    @Test
    void rejectsNegativeMaxSequenceLength() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new ModelConfig(MODEL, TOKENIZER, -1));
    }

    @Test
    void rejectsNegativeIntraOpThreads() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new ModelConfig(MODEL, TOKENIZER, 512, -1, 0));
    }

    @Test
    void rejectsNegativeInterOpThreads() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new ModelConfig(MODEL, TOKENIZER, 512, 0, -1));
    }

    @Test
    void acceptsCustomThreadCounts() {
        var config = new ModelConfig(MODEL, TOKENIZER, 512, 4, 2);
        assertThat(config.intraOpThreads()).isEqualTo(4);
        assertThat(config.interOpThreads()).isEqualTo(2);
    }
}
```

- [ ] **Step 2: Write OnnxInferenceModel integration tests**

```java
package io.casehub.inference.runtime;

import io.casehub.inference.InferenceException;
import io.casehub.inference.InferenceInput;
import io.casehub.inference.InferenceOutput;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Path;
import java.util.List;

import static org.assertj.core.api.Assertions.*;

class OnnxInferenceModelTest {

    private static final Path TEST_MODEL_DIR = Path.of("src/test/resources/test-model");
    private static final Path MODEL_PATH = TEST_MODEL_DIR.resolve("model.onnx");
    private static final Path TOKENIZER_PATH = TEST_MODEL_DIR.resolve("tokenizer.json");
    private static final Path WRONG_INPUTS_MODEL = TEST_MODEL_DIR.resolve("wrong-inputs-model.onnx");

    // --- Happy path ---

    @Test
    void loadAndRunSingleText() {
        var config = new ModelConfig(MODEL_PATH, TOKENIZER_PATH);
        try (var model = new OnnxInferenceModel(config)) {
            var output = model.run(InferenceInput.of("hello world"));
            assertThat(output.values()).hasSize(3);
        }
    }

    @Test
    void loadAndRunTextPair() {
        var config = new ModelConfig(MODEL_PATH, TOKENIZER_PATH);
        try (var model = new OnnxInferenceModel(config)) {
            var output = model.run(InferenceInput.pair("premise", "hypothesis"));
            assertThat(output.values()).hasSize(3);
        }
    }

    @Test
    void outputSizeReturnsThree() {
        var config = new ModelConfig(MODEL_PATH, TOKENIZER_PATH);
        try (var model = new OnnxInferenceModel(config)) {
            assertThat(model.outputSize()).hasValue(3);
        }
    }

    // --- Batch ---

    @Test
    void runBatchReturnsOneOutputPerInput() {
        var config = new ModelConfig(MODEL_PATH, TOKENIZER_PATH);
        try (var model = new OnnxInferenceModel(config)) {
            var inputs = List.of(
                InferenceInput.of("one"),
                InferenceInput.of("two"),
                InferenceInput.of("three")
            );
            var outputs = model.runBatch(inputs);
            assertThat(outputs).hasSize(3);
            for (var output : outputs) {
                assertThat(output.values()).hasSize(3);
            }
        }
    }

    @Test
    void runBatchEmptyReturnsEmpty() {
        var config = new ModelConfig(MODEL_PATH, TOKENIZER_PATH);
        try (var model = new OnnxInferenceModel(config)) {
            assertThat(model.runBatch(List.of())).isEmpty();
        }
    }

    @Test
    void batchSingleEquivalence() {
        var config = new ModelConfig(MODEL_PATH, TOKENIZER_PATH);
        try (var model = new OnnxInferenceModel(config)) {
            var input = InferenceInput.of("equivalence test");
            var single = model.run(input);
            var batched = model.runBatch(List.of(input)).get(0);
            assertThat(batched).isEqualTo(single);
        }
    }

    @Test
    void runBatchNullListThrowsIAE() {
        var config = new ModelConfig(MODEL_PATH, TOKENIZER_PATH);
        try (var model = new OnnxInferenceModel(config)) {
            assertThatIllegalArgumentException()
                .isThrownBy(() -> model.runBatch(null));
        }
    }

    @Test
    void runBatchNullElementThrowsIAE() {
        var config = new ModelConfig(MODEL_PATH, TOKENIZER_PATH);
        try (var model = new OnnxInferenceModel(config)) {
            var inputs = new java.util.ArrayList<InferenceInput>();
            inputs.add(InferenceInput.of("ok"));
            inputs.add(null);
            assertThatIllegalArgumentException()
                .isThrownBy(() -> model.runBatch(inputs));
        }
    }

    // --- Model validation at load ---

    @Test
    void rejectsModelMissingInputIds() {
        var config = new ModelConfig(WRONG_INPUTS_MODEL, TOKENIZER_PATH);
        assertThatExceptionOfType(ModelLoadException.class)
            .isThrownBy(() -> new OnnxInferenceModel(config))
            .withMessageContaining("input_ids");
    }

    @Test
    void rejectsNonExistentModelPath() {
        var config = new ModelConfig(Path.of("/nonexistent/model.onnx"), TOKENIZER_PATH);
        assertThatExceptionOfType(ModelLoadException.class)
            .isThrownBy(() -> new OnnxInferenceModel(config));
    }

    @Test
    void rejectsNonExistentTokenizerPath() {
        var config = new ModelConfig(MODEL_PATH, Path.of("/nonexistent/tokenizer.json"));
        assertThatExceptionOfType(ModelLoadException.class)
            .isThrownBy(() -> new OnnxInferenceModel(config));
    }

    // --- Lifecycle ---

    @Test
    void runAfterCloseThrows() {
        var config = new ModelConfig(MODEL_PATH, TOKENIZER_PATH);
        var model = new OnnxInferenceModel(config);
        model.close();
        assertThatExceptionOfType(InferenceException.class)
            .isThrownBy(() -> model.run(InferenceInput.of("test")))
            .withMessageContaining("closed");
    }

    @Test
    void runBatchAfterCloseThrows() {
        var config = new ModelConfig(MODEL_PATH, TOKENIZER_PATH);
        var model = new OnnxInferenceModel(config);
        model.close();
        assertThatExceptionOfType(InferenceException.class)
            .isThrownBy(() -> model.runBatch(List.of(InferenceInput.of("test"))))
            .withMessageContaining("closed");
    }

    @Test
    void runBatchEmptyAfterCloseThrows() {
        var config = new ModelConfig(MODEL_PATH, TOKENIZER_PATH);
        var model = new OnnxInferenceModel(config);
        model.close();
        assertThatExceptionOfType(InferenceException.class)
            .isThrownBy(() -> model.runBatch(List.of()))
            .withMessageContaining("closed");
    }

    @Test
    void closeIsIdempotent() {
        var config = new ModelConfig(MODEL_PATH, TOKENIZER_PATH);
        var model = new OnnxInferenceModel(config);
        model.close();
        assertThatNoException().isThrownBy(model::close);
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-runtime`

Expected: COMPILATION ERROR — `ModelConfig`, `OnnxInferenceModel`, `ModelLoadException` not yet defined

- [ ] **Step 4: Implement ModelConfig**

```java
package io.casehub.inference.runtime;

import java.nio.file.Path;
import java.util.Objects;

public record ModelConfig(
    Path modelPath,
    Path tokenizerPath,
    int maxSequenceLength,
    int intraOpThreads,
    int interOpThreads
) {
    public ModelConfig {
        Objects.requireNonNull(modelPath, "modelPath must not be null");
        Objects.requireNonNull(tokenizerPath, "tokenizerPath must not be null");
        if (maxSequenceLength <= 0)
            throw new IllegalArgumentException("maxSequenceLength must be positive");
        if (intraOpThreads < 0)
            throw new IllegalArgumentException("intraOpThreads must be non-negative");
        if (interOpThreads < 0)
            throw new IllegalArgumentException("interOpThreads must be non-negative");
    }

    public ModelConfig(Path modelPath, Path tokenizerPath) {
        this(modelPath, tokenizerPath, 512, 0, 0);
    }

    public ModelConfig(Path modelPath, Path tokenizerPath, int maxSequenceLength) {
        this(modelPath, tokenizerPath, maxSequenceLength, 0, 0);
    }
}
```

- [ ] **Step 5: Implement ModelLoadException**

```java
package io.casehub.inference.runtime;

import io.casehub.inference.InferenceException;

public class ModelLoadException extends InferenceException {

    public ModelLoadException(String message) {
        super(message);
    }

    public ModelLoadException(String message, Throwable cause) {
        super(message, cause);
    }
}
```

- [ ] **Step 6: Implement OnnxInferenceModel**

```java
package io.casehub.inference.runtime;

import ai.djl.huggingface.tokenizers.Encoding;
import ai.djl.huggingface.tokenizers.HuggingFaceTokenizer;
import ai.onnxruntime.OnnxTensor;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtException;
import ai.onnxruntime.OrtSession;
import ai.onnxruntime.TensorInfo;
import io.casehub.inference.InferenceException;
import io.casehub.inference.InferenceInput;
import io.casehub.inference.InferenceModel;
import io.casehub.inference.InferenceOutput;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.OptionalInt;

public final class OnnxInferenceModel implements InferenceModel {

    private final OrtEnvironment env;
    private final OrtSession session;
    private final HuggingFaceTokenizer tokenizer;
    private final int maxSequenceLength;
    private final int outputDim;
    private volatile boolean closed;

    public OnnxInferenceModel(ModelConfig config) {
        this.env = OrtEnvironment.getEnvironment();
        this.maxSequenceLength = config.maxSequenceLength();

        OrtSession loadedSession = null;
        HuggingFaceTokenizer loadedTokenizer = null;
        try {
            try (var opts = new OrtSession.SessionOptions()) {
                if (config.intraOpThreads() > 0) {
                    opts.setIntraOpNumThreads(config.intraOpThreads());
                }
                if (config.interOpThreads() > 0) {
                    opts.setInterOpNumThreads(config.interOpThreads());
                }
                loadedSession = env.createSession(config.modelPath().toString(), opts);
            }

            validateInputs(loadedSession);
            this.outputDim = validateOutputs(loadedSession);

            loadedTokenizer = HuggingFaceTokenizer.newInstance(
                config.tokenizerPath(),
                Map.of(
                    "maxLength", String.valueOf(config.maxSequenceLength()),
                    "truncation", "true",
                    "padding", "false"
                )
            );

            this.session = loadedSession;
            this.tokenizer = loadedTokenizer;
        } catch (ModelLoadException e) {
            closeQuietly(loadedSession);
            closeQuietly(loadedTokenizer);
            throw e;
        } catch (OrtException e) {
            closeQuietly(loadedSession);
            closeQuietly(loadedTokenizer);
            throw new ModelLoadException(
                "Failed to load ONNX model: " + config.modelPath(), e);
        } catch (IOException e) {
            closeQuietly(loadedSession);
            closeQuietly(loadedTokenizer);
            throw new ModelLoadException(
                "Failed to load tokenizer: " + config.tokenizerPath(), e);
        }
    }

    @Override
    public InferenceOutput run(InferenceInput input) {
        if (closed) throw new InferenceException("Model is closed");
        Objects.requireNonNull(input, "input must not be null");

        try {
            Encoding encoding = encode(input);
            long[][] inputIds2d = {encoding.getIds()};
            long[][] attentionMask2d = {encoding.getAttentionMask()};

            try (OnnxTensor idsTensor = OnnxTensor.createTensor(env, inputIds2d);
                 OnnxTensor maskTensor = OnnxTensor.createTensor(env, attentionMask2d);
                 OrtSession.Result result = session.run(
                     Map.of("input_ids", idsTensor, "attention_mask", maskTensor))) {
                float[][] logits = (float[][]) result.get(0).getValue();
                return new InferenceOutput(logits[0]);
            }
        } catch (OrtException e) {
            throw new InferenceException("Inference failed", e);
        }
    }

    @Override
    public List<InferenceOutput> runBatch(List<InferenceInput> inputs) {
        if (closed) throw new InferenceException("Model is closed");
        Objects.requireNonNull(inputs, "inputs must not be null");
        if (inputs.isEmpty()) return List.of();
        for (int i = 0; i < inputs.size(); i++) {
            if (inputs.get(i) == null) {
                throw new IllegalArgumentException("inputs[" + i + "] must not be null");
            }
        }

        try {
            int batchSize = inputs.size();
            Encoding[] encodings = new Encoding[batchSize];
            int maxLen = 0;
            for (int i = 0; i < batchSize; i++) {
                encodings[i] = encode(inputs.get(i));
                maxLen = Math.max(maxLen, encodings[i].getIds().length);
            }

            long[][] batchIds = new long[batchSize][maxLen];
            long[][] batchMask = new long[batchSize][maxLen];
            for (int i = 0; i < batchSize; i++) {
                long[] ids = encodings[i].getIds();
                long[] mask = encodings[i].getAttentionMask();
                System.arraycopy(ids, 0, batchIds[i], 0, ids.length);
                System.arraycopy(mask, 0, batchMask[i], 0, mask.length);
            }

            try (OnnxTensor idsTensor = OnnxTensor.createTensor(env, batchIds);
                 OnnxTensor maskTensor = OnnxTensor.createTensor(env, batchMask);
                 OrtSession.Result result = session.run(
                     Map.of("input_ids", idsTensor, "attention_mask", maskTensor))) {
                float[][] logits = (float[][]) result.get(0).getValue();
                List<InferenceOutput> outputs = new ArrayList<>(batchSize);
                for (float[] row : logits) {
                    outputs.add(new InferenceOutput(row));
                }
                return Collections.unmodifiableList(outputs);
            }
        } catch (OrtException e) {
            throw new InferenceException("Batch inference failed", e);
        }
    }

    @Override
    public OptionalInt outputSize() {
        return outputDim > 0 ? OptionalInt.of(outputDim) : OptionalInt.empty();
    }

    @Override
    public void close() {
        if (closed) return;
        closed = true;
        try {
            session.close();
        } finally {
            tokenizer.close();
        }
    }

    private Encoding encode(InferenceInput input) {
        List<String> texts = input.texts();
        if (texts.size() == 1) {
            return tokenizer.encode(texts.get(0));
        }
        return tokenizer.encode(texts.get(0), texts.get(1));
    }

    private static void validateInputs(OrtSession session) throws OrtException {
        var inputNames = session.getInputNames();
        if (!inputNames.contains("input_ids")) {
            throw new ModelLoadException(
                "Model missing required input 'input_ids'. Actual inputs: " + inputNames);
        }
        if (!inputNames.contains("attention_mask")) {
            throw new ModelLoadException(
                "Model missing required input 'attention_mask'. Actual inputs: " + inputNames);
        }
    }

    private static int validateOutputs(OrtSession session) throws OrtException {
        var outputInfo = session.getOutputInfo();
        if (outputInfo.isEmpty()) {
            throw new ModelLoadException("Model has no outputs");
        }
        var firstOutput = outputInfo.values().iterator().next();
        var tensorInfo = (TensorInfo) firstOutput.getInfo();
        long[] shape = tensorInfo.getShape();
        if (shape.length != 2) {
            throw new ModelLoadException(
                "Expected rank-2 output [batch, dim], got rank "
                    + shape.length + ": " + Arrays.toString(shape));
        }
        return shape[1] > 0 ? (int) shape[1] : -1;
    }

    private static void closeQuietly(AutoCloseable closeable) {
        if (closeable != null) {
            try { closeable.close(); } catch (Exception ignored) {}
        }
    }
}
```

- [ ] **Step 7: Delete C2 bridge code**

Delete these files:
- `inference-runtime/src/main/java/io/casehub/inference/runtime/OnnxSessionLoader.java`
- `inference-runtime/src/main/java/io/casehub/inference/runtime/RawInference.java`
- `inference-runtime/src/main/java/io/casehub/inference/runtime/TokenizerLoader.java`

- [ ] **Step 8: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-runtime`

Expected: All tests PASS

- [ ] **Step 9: Write ArchUnit test**

```java
package io.casehub.inference.runtime;

import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

@AnalyzeClasses(packages = "io.casehub.inference.runtime")
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
}
```

- [ ] **Step 10: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-runtime`

Expected: All tests PASS

- [ ] **Step 11: Commit**

```
git add inference-runtime/src/
git commit -m "feat(#3): inference-runtime — OnnxInferenceModel with model validation, batch inference, lifecycle management

Replaces C2 bridge code (OnnxSessionLoader, RawInference, TokenizerLoader)
with SPI-compliant OnnxInferenceModel. Adds ModelConfig with thread count
configuration and ModelLoadException for construction failures."
```

---

## Task 6: Update Gate Command — Replace Bridge Code References

**Files:**
- Modify: `inference-quarkus/src/main/java/io/casehub/inference/quarkus/gate/NativeImageGateCommand.java`

- [ ] **Step 1: Update NativeImageGateCommand to use OnnxInferenceModel**

Replace the current implementation that uses `OnnxSessionLoader`, `RawInference`, `TokenizerLoader` with `OnnxInferenceModel`:

```java
package io.casehub.inference.quarkus.gate;

import io.casehub.inference.InferenceInput;
import io.casehub.inference.InferenceOutput;
import io.casehub.inference.runtime.ModelConfig;
import io.casehub.inference.runtime.OnnxInferenceModel;
import io.quarkus.runtime.QuarkusApplication;
import io.quarkus.runtime.annotations.QuarkusMain;
import java.nio.file.Path;

@QuarkusMain
public class NativeImageGateCommand implements QuarkusApplication {

    @Override
    public int run(String... args) throws Exception {
        if (args.length < 1) {
            System.err.println("FAIL: model directory argument required");
            return 1;
        }
        Path modelDir = Path.of(args[0]);

        try (var model = new OnnxInferenceModel(new ModelConfig(
                modelDir.resolve("model.onnx"),
                modelDir.resolve("tokenizer.json")))) {

            System.out.println("PASS: DJL Tokenizer JNI loaded and executed");
            System.out.println("PASS: ONNX Runtime JNI loaded and session created");
            System.out.println("Output size: " + model.outputSize());

            InferenceOutput output = model.run(InferenceInput.pair(
                "The weather is sunny", "It is raining"));
            float[] logits = output.values();

            System.out.printf("Logits: contradiction=%.4f, entailment=%.4f, neutral=%.4f%n",
                logits[0], logits[1], logits[2]);

            if (logits[0] <= logits[1] || logits[0] <= logits[2]) {
                System.err.println("FAIL: End-to-end inference — contradiction score not highest");
                return 1;
            }
            System.out.println("PASS: End-to-end inference completed");
        } catch (Exception e) {
            System.err.println("FAIL: " + e.getMessage());
            e.printStackTrace(System.err);
            return 1;
        }

        return 0;
    }
}
```

- [ ] **Step 2: Verify full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

Expected: BUILD SUCCESS — all modules compile, all tests pass

- [ ] **Step 3: Commit**

```
git add inference-quarkus/src/main/java/io/casehub/inference/quarkus/gate/NativeImageGateCommand.java
git commit -m "refactor(#3): gate command uses OnnxInferenceModel instead of C2 bridge code"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] `InferenceModel` interface with `run`, `runBatch`, `outputSize`, `close` — Task 2
- [x] `InferenceInput` with validation, `of`, `pair`, max 2 texts — Task 2
- [x] `InferenceOutput` with defensive copy, equality, truncated toString — Task 2
- [x] `InferenceException` — Task 2
- [x] `InMemoryInferenceModel` with `returning`, `withFunction`, volatile closed, post-close enforcement — Task 3
- [x] `ModelConfig` with thread counts, convenience constructors — Task 5
- [x] `ModelLoadException` — Task 5
- [x] `OnnxInferenceModel` with constructor validation, `run`, `runBatch`, batch padding, idempotent close, try-finally — Task 5
- [x] C2 bridge code deleted — Task 5
- [x] Gate command updated — Task 6
- [x] ArchUnit tests for all three modules — Tasks 2, 3, 5
- [x] Batch/single equivalence test — Task 5
- [x] Dynamic output dimension handling (outputDim = -1 → OptionalInt.empty()) — Task 5
- [x] runBatch validation ordering: closed → null → empty → null elements — Tasks 3, 5
- [x] Test model + tokenizer resources — Task 4

**Placeholder scan:** No TBDs, TODOs, or vague instructions. All code blocks complete.

**Type consistency:** `InferenceModel`, `InferenceInput`, `InferenceOutput`, `InferenceException`, `ModelConfig`, `ModelLoadException`, `OnnxInferenceModel`, `InMemoryInferenceModel` — consistent across all tasks.

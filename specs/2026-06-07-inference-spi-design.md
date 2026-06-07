# Inference SPI Foundation — Design Spec

**Date:** 2026-06-07
**Status:** Approved
**Issue:** casehubio/neural-text#3
**Modules:** inference-api, inference-runtime, inference-inmem
**Consumers:** casehub-engine (#154), casehub-openclaw, casehub-eidos, casehub-rag, Hortora
**Authoritative prior spec:** Hortora/spec `docs/superpowers/specs/2026-06-03-onnx-inference-module-design.md`

---

## Departures from Prior Spec

The Hortora spec (2026-06-03) defined the initial SPI shape. This spec supersedes it for the following decisions:

| Prior spec | This spec | Rationale |
|---|---|---|
| `ModelConfig` in inference-api | `ModelConfig` in inference-runtime | Config is a construction concern, not an SPI concern. inference-inmem has no use for model paths. |
| `InferenceOutput.tensor(String name)` | `InferenceOutput(float[] values)` record | All target models produce one output tensor. Tensor names are ONNX internals that don't belong in the SPI. |
| No error handling specified | `InferenceException` unchecked exception | SPI must not leak `OrtException` (checked). Runtime wraps all JNI/IO errors. |
| No output size validation | `InferenceModel.outputSize()` default method | Five consumers each expect different output shapes. Fail-fast at wiring time prevents deployment misconfiguration. |

---

## Module 1: inference-api

**Package:** `io.casehub.inference`
**Dependencies:** none (pure Java, zero deps)
**ArchUnit enforced:** zero casehub, Quarkus, Spring, LangChain4j imports

### Types

**`InferenceModel`** — the SPI interface.

```java
public interface InferenceModel extends AutoCloseable {
    InferenceOutput run(InferenceInput input);
    List<InferenceOutput> runBatch(List<InferenceInput> inputs);
    default int outputSize() { return -1; }
    @Override void close();
}
```

- `AutoCloseable` because ONNX sessions hold native memory.
- `runBatch` is on the SPI (not a convenience wrapper) because native ONNX batching — padding multiple inputs into one tensor for a single `session.run()` — is significantly faster than looping `run()`. The in-memory impl loops; the ONNX impl batches natively.
- `outputSize()` defaults to -1 (unknown). ONNX runtime returns the real value from session metadata. Task adapters (C4) validate at construction time.
- Thread safety contract: implementations must be safe for concurrent `run()`/`runBatch()` calls.

**`InferenceInput`** — text input to a model.

```java
public record InferenceInput(List<String> texts) {
    public InferenceInput {
        if (texts == null || texts.isEmpty())
            throw new IllegalArgumentException("texts must not be empty");
        texts = List.copyOf(texts);
    }
    public static InferenceInput of(String text) { ... }
    public static InferenceInput pair(String first, String second) { ... }
}
```

- Immutable — defensive copy in compact constructor.
- `of()` for single-text models (classification, regression, SPLADE).
- `pair()` for two-text models (NLI premise+hypothesis, cross-encoder query+document).
- Runtime dispatches tokenization on `texts.size()`: 1 → single encode, 2 → pair encode with [SEP].

**`InferenceOutput`** — raw model output values.

```java
public record InferenceOutput(float[] values) {
    public InferenceOutput { Objects.requireNonNull(values); }

    @Override public boolean equals(Object o) {
        return o instanceof InferenceOutput other && Arrays.equals(values, other.values);
    }
    @Override public int hashCode() { return Arrays.hashCode(values); }
    @Override public String toString() { return "InferenceOutput" + Arrays.toString(values); }
}
```

- Overrides `equals`/`hashCode` with `Arrays.equals` for test assertion ergonomics.
- Semantic interpretation is the task adapter's job (C4): NLI → indices 0/1/2 are entailment/neutral/contradiction. Classification → one score per class. Regression → single scalar. SPLADE → vocab-sized weight vector.

**`InferenceException`** — unchecked wrapper for runtime errors.

```java
public class InferenceException extends RuntimeException {
    public InferenceException(String message) { ... }
    public InferenceException(String message, Throwable cause) { ... }
}
```

---

## Module 2: inference-runtime

**Package:** `io.casehub.inference.runtime`
**Dependencies:** inference-api, ONNX Runtime JVM (`onnxruntime`), DJL Tokenizers (`ai.djl.huggingface:tokenizers`)
**ArchUnit enforced:** zero casehub, Quarkus, Spring, LangChain4j imports

### Types

**`ModelConfig`** — construction parameters for an ONNX model.

```java
public record ModelConfig(
    Path modelPath,
    Path tokenizerPath,
    int maxSequenceLength
) {
    public ModelConfig {
        Objects.requireNonNull(modelPath);
        Objects.requireNonNull(tokenizerPath);
        if (maxSequenceLength <= 0)
            throw new IllegalArgumentException("maxSequenceLength must be positive");
    }
    public ModelConfig(Path modelPath, Path tokenizerPath) {
        this(modelPath, tokenizerPath, 512);
    }
}
```

**`OnnxInferenceModel`** — the ONNX Runtime implementation of `InferenceModel`.

```java
public final class OnnxInferenceModel implements InferenceModel { ... }
```

Constructor:
1. `OrtEnvironment.getEnvironment()` — process-global singleton
2. `env.createSession(modelPath)` — loads model, allocates native heap. Wraps `OrtException` → `ModelLoadException`
3. `HuggingFaceTokenizer.builder().optTokenizerPath(...).optMaxLength(...).optTruncation(true).optPadding(false).build()` — tokenizer with truncation. Wraps `IOException` → `ModelLoadException`
4. `outputSize` — read from `session.getOutputInfo()`, first output tensor's shape last dimension

`run()` flow:
1. Tokenize: `texts.size() == 1` → `tokenizer.encode(text)`, `texts.size() == 2` → `tokenizer.encode(a, b)`, `texts.size() >= 3` → `InferenceException`
2. Extract `long[] inputIds`, `long[] attentionMask` from `Encoding`
3. Wrap as 2D tensors: `long[1][seqLen]`
4. `session.run(Map.of("input_ids", ..., "attention_mask", ...))` — input tensor names hard-coded (universal HuggingFace standard)
5. Extract `float[][]` from first output, return `new InferenceOutput(logits[0])`
6. Tensors closed via try-with-resources

`runBatch()` flow:
- Tokenize all inputs individually
- Pad to batch-max length (not `maxSequenceLength` — shorter when inputs are short)
- Stack into `long[batchSize][maxLen]` tensors
- Single `session.run()` call
- Split `float[batchSize][outputDim]` result into `List<InferenceOutput>`

`close()`: closes session then tokenizer. Does not close `OrtEnvironment` (process singleton).

Thread safety: `OrtSession.run()` and `HuggingFaceTokenizer.encode()` are both documented thread-safe. No mutable instance state.

**`ModelLoadException`** — subclass of `InferenceException` for construction failures.

```java
public class ModelLoadException extends InferenceException {
    public ModelLoadException(String message, Throwable cause) { ... }
}
```

### C2 bridge code disposition

`OnnxSessionLoader`, `RawInference`, `TokenizerLoader` are deleted. Their logic is subsumed by `OnnxInferenceModel`: constructor replaces session/tokenizer loading, `run()` replaces `classifyPair()` generalized to handle single-text and pair inputs.

### Known limitation

Only `input_ids` and `attention_mask` are passed. Models requiring `token_type_ids` (original BERT, ALBERT) will produce incorrect results. Tracked as #8. DeBERTa (our primary NLI model) does not use token_type_ids.

---

## Module 3: inference-inmem

**Package:** `io.casehub.inference.inmem`
**Dependencies:** inference-api only
**ArchUnit enforced:** zero casehub, Quarkus, Spring, LangChain4j, ONNX Runtime, DJL imports

### Types

**`InMemoryInferenceModel`** — deterministic stub for testing.

```java
public final class InMemoryInferenceModel implements InferenceModel {

    public static InMemoryInferenceModel returning(float... values) { ... }
    public static InMemoryInferenceModel withFunction(
            int outputSize, Function<InferenceInput, float[]> fn) { ... }

    @Override public InferenceOutput run(InferenceInput input) { ... }
    @Override public List<InferenceOutput> runBatch(List<InferenceInput> inputs) { ... }
    @Override public int outputSize() { ... }
    @Override public void close() { /* no-op */ }
}
```

- `returning()` — fixed output, cloned on each call to prevent mutation.
- `withFunction()` — custom logic per input, explicit `outputSize` required.
- `runBatch()` loops `run()` — no native batching to optimize.
- `close()` is a no-op.
- No JNI, no native libs. Safe in `@QuarkusTest`, native image tests, plain JUnit.

---

## Data Flow

```
Caller text
  → InferenceInput.of("text") or .pair("a", "b")
  → OnnxInferenceModel.run():
      → HuggingFace Tokenizers JNI: text → token IDs + attention mask
      → OnnxTensor: token IDs → long[1][seqLen] tensors
      → OrtSession.run(tensors) → float[][] raw output
      → InferenceOutput(logits[0])
  → Task adapter (C4): interprets float[] as domain result
```

---

## Dependency Graph

```
inference-tasks (C4)  ──→  inference-api  ←──  inference-inmem
inference-splade (C6) ──→       ↑
inference-quarkus (C5) ──→  inference-runtime
```

All arrows point toward inference-api. inference-runtime depends on inference-api (not reverse). inference-inmem depends on inference-api only. Task modules (C4, C6) and Quarkus wiring (C5) are future epics.

---

## Deferred

| Concern | Issue | Notes |
|---|---|---|
| `token_type_ids` third input tensor | #8 | BERT/ALBERT need it; DeBERTa doesn't. Low priority. |
| Execution provider config (CUDA, CoreML) | C5 scope | Quarkus config will expose `OrtSession.SessionOptions`. |
| ArchUnit enforcement | In scope for C3 | Zero-domain-dep constraint on all three modules. |

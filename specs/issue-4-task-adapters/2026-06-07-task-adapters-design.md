# inference-tasks — Task Adapters Design Spec

**Date:** 2026-06-07
**Status:** Approved
**Issue:** casehubio/neural-text#4
**Module:** inference-tasks
**Consumers:** casehub-engine (#154 — NliClassifier), casehub-openclaw (TextClassifier), casehub-eidos (ScalarRegressor), Hortora (CrossEncoderReranker)
**Depends on:** inference-api (C3, shipped)
**Authoritative prior spec:** Hortora/spec `docs/superpowers/specs/2026-06-03-onnx-inference-module-design.md` §Task Adapters

---

## What This Delivers

Four typed adapters that wrap `InferenceModel` and interpret `float[]` output as domain results. Callers work with `NliResult`, `ClassificationResult`, `float`, and `List<RankedResult>` — never raw tensors. All adapters are pure Java, zero deps, tested entirely with `InMemoryInferenceModel` stubs.

---

## Module Identity

- **Package:** `io.casehub.inference.tasks`
- **Dependencies:** `casehub-inference-api` (compile). `casehub-inference-inmem` (test).
- **Tier:** Pure Java, zero external deps (Tier 1 per `module-tier-structure.md`)
- **ArchUnit enforced:** zero casehub (non-inference), Quarkus, Spring, LangChain4j, ONNX Runtime, DJL imports

---

## Adapter Lifecycle

Adapters are **pure interpreters** — they do not implement `AutoCloseable` and do not own the `InferenceModel` they wrap. The model's lifecycle is the caller's (or CDI container's) responsibility.

Rationale: multiple adapters may share the same underlying model, or the model may outlive the adapter. In C5 (Quarkus), CDI manages model lifecycle; adapters are beans that receive an injected model. Keeping adapters resource-free makes them trivially testable and composable.

```java
var model = new OnnxInferenceModel(config);
var nli = new NliClassifier(model);
nli.classify("premise", "hypothesis");
model.close();  // caller closes
```

---

## Construction Validation

All adapters validate `model.outputSize()` at construction time when available:
- If `outputSize()` is present and doesn't match the expected size → `IllegalArgumentException`
- If `outputSize()` is empty (`OptionalInt.empty()`) → skip validation (model may still be correct; shape issues discovered at first `run()`)

This provides fail-fast at wiring time for misconfigured models without rejecting valid models with dynamic output dimensions.

---

## Types

### NliLabel (enum)

```java
public enum NliLabel {
    ENTAILMENT, NEUTRAL, CONTRADICTION
}
```

### NliResult (record)

```java
public record NliResult(float entailment, float neutral, float contradiction) {
    public NliLabel predicted() { /* returns label with highest score */ }
}
```

All values in [0,1], sum to 1 (softmax applied by the classifier).

### NliClassifier

```java
public final class NliClassifier {
    public NliClassifier(InferenceModel model) { ... }
    public NliResult classify(String premise, String hypothesis) { ... }
}
```

- Validates `outputSize() == 3` when available
- Convention-based HuggingFace label order: index 0=contradiction, 1=neutral, 2=entailment (standard for DeBERTa and most NLI models)
- `classify()` flow: `InferenceInput.pair(premise, hypothesis)` → `model.run()` → softmax on `float[3]` → `NliResult(entailment=values[2], neutral=values[1], contradiction=values[0])`
- Null premise or hypothesis → `IllegalArgumentException`

If a model uses non-standard label order, use `TextClassifier` with explicit labels `["contradiction", "neutral", "entailment"]` instead.

### ClassificationResult (record)

```java
public record ClassificationResult(String label, float confidence, Map<String, Float> scores) {
    // label: highest-scoring label
    // confidence: its softmax probability
    // scores: all labels → probabilities (unmodifiable)
}
```

### TextClassifier

```java
public final class TextClassifier {
    public TextClassifier(InferenceModel model, List<String> labels) { ... }
    public ClassificationResult classify(String text) { ... }
}
```

- Labels provided at construction (defensive copy, immutable). Labels are a model property — fixed at training time.
- Validates `labels.size()` matches `outputSize()` when available
- Null or empty labels → `IllegalArgumentException`
- `classify()` flow: `InferenceInput.of(text)` → `model.run()` → softmax on `float[N]` → find argmax → `ClassificationResult(labels[argmax], scores[argmax], allScoresMap)`
- Null text → `IllegalArgumentException`

### ScalarRegressor

```java
public final class ScalarRegressor {
    public ScalarRegressor(InferenceModel model) { ... }
    public float predict(String text) { ... }
}
```

- Validates `outputSize() == 1` when available
- No softmax — returns the raw scalar value
- `predict()` flow: `InferenceInput.of(text)` → `model.run()` → return `values[0]`
- Null text → `IllegalArgumentException`

### RankedResult (record)

```java
public record RankedResult(String text, float score, int originalIndex) {}
```

Ordered by descending score in the list returned by `rerank()`.

### CrossEncoderReranker

```java
public final class CrossEncoderReranker {
    public CrossEncoderReranker(InferenceModel model) { ... }
    public float score(String query, String candidate) { ... }
    public List<RankedResult> rerank(String query, List<String> candidates) { ... }
}
```

- Validates `outputSize() == 1` when available (cross-encoders output a single relevance score per pair)
- `score()` flow: `InferenceInput.pair(query, candidate)` → `model.run()` → return `values[0]`
- `rerank()` flow: build `List<InferenceInput>` with `pair(query, candidate)` for each candidate → `model.runBatch()` → extract score from each output → sort by descending score → `List<RankedResult>` (unmodifiable)
- Null query, null candidates, empty candidates → `IllegalArgumentException`
- Null elements in candidates → `IllegalArgumentException`

---

## Softmax

Private static method within each adapter that needs it (NliClassifier, TextClassifier). Two copies of the same 4-line arithmetic — simpler than a shared utility class. Numerically stable: subtract max before exp to prevent overflow.

```java
private static float[] softmax(float[] logits) {
    float max = logits[0];
    for (int i = 1; i < logits.length; i++) if (logits[i] > max) max = logits[i];
    float sum = 0;
    float[] result = new float[logits.length];
    for (int i = 0; i < logits.length; i++) {
        result[i] = (float) Math.exp(logits[i] - max);
        sum += result[i];
    }
    for (int i = 0; i < logits.length; i++) result[i] /= sum;
    return result;
}
```

---

## Error Handling

| Scenario | Exception | When |
|---|---|---|
| Null model | `IllegalArgumentException` | Constructor |
| Null/empty labels (TextClassifier) | `IllegalArgumentException` | Constructor |
| `outputSize()` mismatch | `IllegalArgumentException` | Constructor |
| Null premise/hypothesis/text/query/candidates | `IllegalArgumentException` | Method call |
| Empty candidates list (rerank) | `IllegalArgumentException` | Method call |
| Null elements in candidates | `IllegalArgumentException` | Method call |
| Model closed or inference failure | `InferenceException` (from model) | Method call |

No adapter-specific exception subclass. `IllegalArgumentException` for precondition violations, `InferenceException` (propagated from the model) for runtime failures.

---

## Testing Strategy

All tests use `InMemoryInferenceModel` — zero JNI, zero native libs.

### NliClassifier

- Softmax applied: raw logits [2.0, 1.0, 0.5] → probabilities sum to 1.0
- `predicted()` returns highest label
- Convention order verified: index 0=contradiction, index 2=entailment
- Output size validation: model with outputSize=5 → IAE at construction
- Output size unknown (empty OptionalInt): construction succeeds
- Null premise/hypothesis → IAE
- Null model → IAE

### TextClassifier

- Labels match output indices: model returning [0.1, 0.9] with labels ["low", "high"] → label="high"
- Label count vs outputSize mismatch → IAE at construction
- Immutability: mutating labels list after construction has no effect
- Single-label degenerate case
- Null/empty labels → IAE
- Null text → IAE

### ScalarRegressor

- Returns raw value: model returning [0.73] → predict() returns 0.73
- Output size validation: model with outputSize=3 → IAE
- Null text → IAE

### CrossEncoderReranker

- `score()` returns raw value from model
- `rerank()` returns results sorted by descending score
- `rerank()` preserves original indices correctly
- `rerank()` uses `runBatch()` — verify via withFunction tracking call count
- Empty candidates → IAE
- Single candidate → works (returns list of one)
- Null query/candidates/elements → IAE

### ArchUnit

- `DependencyConstraintTest`: zero imports from casehub (non-inference), Quarkus, Spring, LangChain4j, ONNX Runtime, DJL

---

## Dependency Graph

```
inference-tasks ──→ inference-api ←── inference-inmem (test only)
```

inference-tasks depends on inference-api at compile scope. inference-inmem is test-scope only. No other dependencies.

---

## Departures from Hortora Spec

| Hortora spec | This spec | Rationale |
|---|---|---|
| `TextClassifier` signature shows `ClassificationResult { label, confidence, allScores: Map<String, Float> }` | Same shape but labels provided at construction, not embedded in the model | `InferenceOutput` is `float[]` — label names must come from somewhere external to the model output |
| No softmax mentioned | NliClassifier and TextClassifier always apply softmax | Raw logits are not meaningful to callers; probabilities are |
| `CrossEncoderReranker.rerank()` only | Both `score()` and `rerank()` | Single-pair scoring is a common need (e.g., filtering a single candidate); `rerank()` uses `runBatch()` for batch efficiency |
| No lifecycle discussion | Adapters are explicitly not AutoCloseable | Prevents double-close bugs when adapters share a model |

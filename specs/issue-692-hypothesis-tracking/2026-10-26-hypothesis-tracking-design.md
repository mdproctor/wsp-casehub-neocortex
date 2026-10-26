# Hypothesis Tracking — Weighted Path Elimination over Composed Bayesian Networks

**Issue:** casehubio/neocortex#692
**Module:** inference-bayes
**Package:** io.quarkmind.inference.bayes
**Depends on:** #674 (model composition)
**Parent epic:** #672 (BJT Phase 3C)

## Overview

A `HypothesisTracker` that maintains a weighted set of competing hypotheses
over a composed Bayesian network. Each hypothesis gets its own
`CompositionInstance` with independent inference state. Observations are
broadcast to all viable hypotheses, weights are updated via Bayesian model
averaging, and hypotheses are eliminated when their posterior weight drops
below a configurable threshold.

This is layer 4 of 5 in the BJT inference stack:

```
Layer 5: InfluenceDiagramEngine  — optimal action selection
Layer 4: HypothesisTracker       — competing explanations  ← this issue
Layer 3: MultiAgentInstance       — private beliefs
Layer 2: CompositionInstance      — multi-network DAG
Layer 1: BayesInstance            — single-network inference
```

## Architecture

### Core Types

**`HypothesisTracker`** — the main class. Owns one `CompositionInstance`
per hypothesis. Thread-unsafe (same contract as `BayesInstance`).

```java
public class HypothesisTracker {
    // Construction via builder only
    public static HypothesisTrackerBuilder builder(NetworkComposition composition) { ... }

    // Observe evidence — broadcasts to all viable hypotheses
    public ObservationResult observe(String slotName, String variableName, double[] distribution) { ... }
    public ObservationResult observeHard(String slotName, String variableName, String state) { ... }

    // Current state
    public TrackerSnapshot snapshot() { ... }
    public Map<String, Double> weights() { ... }
    public List<String> viable() { ... }
    public String leader() { ... }
    public boolean isResolved() { ... }

    // Reset to initial priors
    public void reset() { ... }
}
```

**`HypothesisDefinition`** — immutable record defining a hypothesis.

```java
public record HypothesisDefinition(
    String name,
    double priorWeight,
    Map<String, String> variantActivations,    // slot → contextKey
    Map<String, double[]> priorOverrides       // "slot.variable" → distribution
) { ... }
```

**`HypothesisTrackerBuilder`** — fluent builder.

```java
var tracker = HypothesisTracker.builder(composition)
    .hypothesis("rush")
        .priorWeight(0.33)
        .activateVariant("strategy", "aggressive")
        .priorOverride("scouting", "timing", new double[]{0.7, 0.2, 0.1})
    .hypothesis("expand")
        .priorWeight(0.33)
        .activateVariant("strategy", "economic")
    .hypothesis("tech")
        .priorWeight(0.34)
    .eliminationThreshold(0.01)
    .build();
```

**`ObservationResult`** — immutable snapshot after an observation.

```java
public record ObservationResult(
    Map<String, Double> weights,       // hypothesis name → posterior weight
    List<String> eliminated,           // hypotheses eliminated this step
    String leader,                     // highest-weight hypothesis
    double entropy,                    // Shannon entropy in bits
    List<String> viable,               // all non-eliminated hypotheses
    boolean resolved                   // true when leader weight exceeds resolution threshold
) { ... }
```

**`TrackerSnapshot`** — full state snapshot (richer than ObservationResult).

```java
public record TrackerSnapshot(
    Map<String, Double> weights,
    Map<String, HypothesisStatus> statuses,  // VIABLE or ELIMINATED
    String leader,
    double entropy,
    int observationCount,
    List<String> viable
) { ... }
```

**`HypothesisStatus`** — enum: `VIABLE`, `ELIMINATED`.

### Weight Update Mechanism

The key insight: **marginal likelihood is computed from the current
marginals *before* setting evidence.** After belief propagation, the
marginal P(X | H_i, e₁..ₖ₋₁) for observation variable X gives the
predictive probability directly. No junction tree internals needed.

**For hard evidence** (observe state s of variable X):
```
P(e_k | H_i) = marginalize(slot, X)[stateIndex(s)]
```

**For soft evidence** (observe distribution d over variable X):
```
P(e_k | H_i) = Σ_j d[j] × marginalize(slot, X)[j]
```
(Dot product of observation distribution with prior marginal.)

**Update rule:**
```
w_i ← w_i × P(e_k | H_i)
normalize: w_i ← w_i / Σ_j w_j
```

**Sequence per observe() call:**
1. For each viable hypothesis H_i:
   a. Compute P(e_k | H_i) from current marginals (before setting evidence)
   b. Set evidence on H_i's CompositionInstance
   c. Run composition update (propagation)
   d. Multiply weight by P(e_k | H_i)
2. Normalize weights across all viable hypotheses
3. Eliminate hypotheses below threshold
4. Re-normalize after elimination
5. Build and return ObservationResult

### Elimination

Two mechanisms coexist:

- **Soft elimination:** After normalization, any hypothesis with
  weight < `eliminationThreshold` (default 0.01) is eliminated.
- **Hard elimination:** If P(e_k | H_i) = 0.0 (impossible evidence
  under the hypothesis), the hypothesis is eliminated immediately
  before normalization.

Eliminated hypotheses are retained in internal state with
`HypothesisStatus.ELIMINATED` for diagnostics. They are excluded from
future updates, weight normalization, and the `viable()` set.

### Resolution

A tracker is "resolved" when the leader's weight exceeds a configurable
`resolutionThreshold` (default 0.95). This is reported in
`ObservationResult.resolved()` but does not stop tracking — the caller
decides what to do.

### Entropy

Shannon entropy in bits: H = -Σ w_i × log₂(w_i) over viable
hypotheses. Measures remaining uncertainty. Starts high (uniform
priors) and decreases as evidence accumulates.

### Configuration

```java
HypothesisTracker.builder(composition)
    .eliminationThreshold(0.01)   // default
    .resolutionThreshold(0.95)    // default
    .hypothesis(...)
    .build();
```

Both thresholds are configurable at build time, not mutable after construction.

## Internal Data Flow

```
observe("scouting", "observed_units", "gateway")
    │
    ├─ for each viable hypothesis:
    │   ├─ read marginal: composition.marginalize("scouting", "observed_units")
    │   │   → [0.42, 0.31, 0.27]  (predictive distribution)
    │   ├─ compute likelihood: P(gateway | H_i) = 0.42
    │   ├─ update weight: w_i *= 0.42
    │   ├─ set evidence on composition
    │   └─ composition.update()
    │
    ├─ normalize weights
    ├─ eliminate below threshold
    ├─ re-normalize
    └─ return ObservationResult
```

## Evidence Semantics

Repeated observations on the same variable use **overwrite semantics**:
the new evidence replaces the previous evidence on that variable. This
matches `BayesInstance.setLikelyhood()` behavior. The predictive
likelihood P(e_k | H_i) is computed from the marginal *before* the new
evidence is set, so the weight update correctly reflects the incremental
information.

Calling `observe()` on different variables accumulates evidence
across variables (conjunction). Each observation narrows the posterior.

## Error Handling

- **Unknown slot/variable:** IllegalArgumentException (same as CompositionInstance)
- **Evidence on link target:** IllegalArgumentException (delegated to CompositionInstance guard)
- **No viable hypotheses:** All eliminated → last ObservationResult has
  empty viable(), null leader. Caller decides how to handle.
- **Zero-sum after normalization:** If all hypotheses have weight 0
  (impossible evidence under all hypotheses), throw
  `IllegalStateException` — the hypothesis set doesn't cover the
  observation space.

## Testing Strategy

1. **Two-hypothesis convergence:** Two hypotheses with distinct priors,
   observe evidence that favors one. Verify weights converge.
2. **Hard elimination:** Observe impossible evidence for one hypothesis.
   Verify immediate elimination.
3. **Soft elimination:** Observe evidence that gradually reduces one
   hypothesis below threshold. Verify elimination after threshold crossing.
4. **Resolution detection:** Observe enough evidence for leader to
   exceed resolution threshold. Verify `isResolved()`.
5. **Entropy monotonicity:** With consistent evidence, verify entropy
   decreases monotonically.
6. **Reset restores priors:** After observations, verify reset() restores
   original weights and viable set.
7. **Multi-slot composition:** Hypotheses that activate different slot
   variants. Verify independent inference.
8. **Prior overrides:** Hypotheses with different prior distributions on
   shared variables. Verify weights diverge.
9. **SC2 scouting scenario:** End-to-end test with scouting → strategy
   composition, three strategy hypotheses, sequential observations.

## File Inventory

All in `inference-bayes/src/main/java/io/quarkmind/inference/bayes/`:

| File | Type | Purpose |
|------|------|---------|
| `HypothesisTracker.java` | Class | Main tracker, owns compositions; contains HypothesisTrackerBuilder as static inner class |
| `HypothesisDefinition.java` | Record | Hypothesis identity and configuration |
| `ObservationResult.java` | Record | Post-observation snapshot |
| `TrackerSnapshot.java` | Record | Full state snapshot |
| `HypothesisStatus.java` | Enum | VIABLE, ELIMINATED |

Test in `inference-bayes/src/test/java/io/quarkmind/inference/bayes/`:

| File | Purpose |
|------|---------|
| `HypothesisTrackerTest.java` | All 9 test scenarios above |

## Non-Goals

- **Hypothesis generation:** The tracker takes a fixed set of hypotheses.
  Automatic hypothesis generation (e.g. from variant keys) is future work.
- **Online hypothesis addition:** Adding hypotheses after construction.
  Would require weight redistribution — deferred.
- **Integration with InfluenceDiagramEngine:** Using the winning hypothesis
  to drive decisions. Natural next step but separate scope.
- **CDI wiring:** Pure Java, no Quarkus dependency.
- **Persistence/serialization:** In-memory only.

## References

- `CompositionInstance.java` — composition layer that HypothesisTracker wraps
- `CompositionBuilder.java` — fluent builder pattern reference
- `MultiAgentInstance.java` — per-agent isolation pattern (analogous to per-hypothesis)
- `CompositionStats.java` — snapshot record pattern
- `InfluenceDiagramEngine.java` — decision layer (layer above)
- `NetworkSlot.variants` — variant activation mechanism used by hypotheses
- casehubio/neocortex#674 — model composition (dependency)
- casehubio/neocortex#672 — BJT Phase 3C (parent epic)
- Bayesian model averaging / model selection literature

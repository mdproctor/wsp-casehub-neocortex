# SE2: CAPS Rework — Settler, Learning, Topology, Classification

**Issue:** casehubio/neocortex#1222
**Parent:** casehubio/neocortex#1220 (Cognitive Pipeline Coherence)
**Branch:** issue-1222-caps-rework
**Status:** Design approved
**Modules:** caps-engine, caps-api, caps-testing, caps-llm-classifier, caps-situation-cbr, mindmap-intelligence (BehavioralSynthesisPhase, ClassificationOutcomeEvaluator), cognition (EmotionRegulationTickParticipant), cognition-api (RegulationCascadeConfig)

---

## 1. Problem

CAPS produces near-identical output across characters and situations. The root cause is a chain of bugs that together make the settler's output dominated by a constant background signal rather than situational input.

The core problem: unipolar nodes at `logistic(0) = 0.5` transmit `0.5 × w` downstream with zero input. This constant background swamps situational activation, makes convergence detection too generous (oscillation reported as converged), weight learning ineffective (predictions always close to observed due to background), and outcome evaluation roughly per-agent constant.

**14 findings** in scope (8 from triage + 6 from exploration):

| ID | Summary | Area |
|----|---------|------|
| B1 | Unipolar background (logistic(0) = 0.5) swamps situation | Settler |
| B2 | Single-cue weight update, not multi-cue R-W | Learning |
| B3 | Weight update result discarded (regulation path) | Learning |
| B5 | Distortions add positive constant regardless of belief sign | Settler |
| B6 | Convergence variance threshold 0.05 too generous | Settler |
| B9 | ClassificationOutcomeEvaluator roughly per-agent constant | Classification |
| B10 | CBR cache: case ID, filter fields, polarity | CBR |
| B12 | Drive injection passes mediating/output nodes to settle() | Classification |
| B17 | Tests don't constrain behaviour (pass for wrong reason) | Tests |
| N1 | Inhibitory weights always zero (dead code) | Learning |
| N2 | Unbounded excitatory weight growth | Learning |
| N3 | Autonomy disposition modifiers never fire (key mismatch) | Topology |
| N4 | Resting activations accumulate without clamping | Topology |
| N6 | activation_clamp [-1,1] never applied during settling | Settler |

---

## 2. Settler Baseline (D2) — Selective BIPOLAR + Rectified Tanh

### Design

The topology has a principled mixed-range design. Cognitive schemas (self_worth, self_efficacy, other_reliability, other_safety, world_predictability, future_outlook, reinforcement_expectation) are BIPOLAR with genuine bipolar semantics. Activation-level constructs (BAS_activation, BIS_activation, FFFS_activation, arousal_level, threat_sensitivity, etc.) are UNIPOLAR because negative activation is meaningless.

**Changes:**

1. **Output nodes default to BIPOLAR.** Change `CapsTopologyLoader.defaultRange(OUTPUT)` from UNIPOLAR to BIPOLAR. Output nodes use `tanh(netInput - threshold)` with resting level 0.0.

2. **UNIPOLAR mediating nodes use rectified tanh.** Replace `logistic(netInput - threshold)` with `Math.max(0.0, Math.tanh(netInput - threshold))`. Zero input → zero activation. Output range [0, 1].

3. **BIPOLAR mediating nodes unchanged.** Continue using `Math.tanh(netInput - threshold)`. Output range [-1, 1].

4. **Update `NodeRange.restingLevel()`**: Change `UNIPOLAR.restingLevel()` from 0.5 to 0.0 — the resting level must match the actual zero-input activation (`max(0, tanh(0)) = 0`). Update javadoc referencing `logistic(0) = 0.5`.

5. **Apply activation_clamp during settling.** After computing `rawAct` (but before momentum damping), clamp to the node's range: `[-1, 1]` for BIPOLAR, `[0, 1]` for UNIPOLAR. This fixes N6.

### Key property

Zero input produces zero activation for ALL node types: `tanh(0) = 0`, `max(0, tanh(0)) = 0`. The constant background that swamped the network is eliminated.

### Impact on CapsSettler.java

```java
// Lines 90-95 — replace activation functions:
case BIPOLAR -> Math.tanh(netInput - threshold);
case UNIPOLAR -> Math.max(0.0, Math.tanh(netInput - threshold));

// After rawAct computation, before damping — add clamp:
double clampedAct = switch (node.range()) {
    case BIPOLAR -> Math.max(-1.0, Math.min(1.0, rawAct));
    case UNIPOLAR -> Math.max(0.0, Math.min(1.0, rawAct));
};
double newAct = damping * oldAct + (1 - damping) * clampedAct;
```

### Impact on attractor extraction

`extractAttractors()` currently computes `strength = min(1.0, settled + restingActivation)` with `baseline = min(1.0, restingLevel + restingActivation)`. Under BIPOLAR (restingLevel = 0.0), baseline becomes just `restingActivation`. The strength formula still works but the absolute values shift: typical resting output drops from ~0.5 to ~0.0, widening the effective range.

**Negative BIPOLAR activations:** Under BIPOLAR, output nodes can settle to negative values. These are NOT reported as attractors — only positive-above-baseline activations are. This is semantically correct: the topology uses complementary output pairs (approach/withdraw, trust/distrust, fight/flight) where suppression of one node is expressed by activation of its complement. A negative `approach` activation means approach is suppressed; the system reports `withdraw` as the active attractor instead.

### CopingDefaults interaction

The `copingBias` formula `(tendency - 0.5) * 0.5` is NOT affected — the 0.5 is the population-mean center on the tendency scale [0, 1], not the activation range center.

---

## 3. Drive Injection Filter (D3) — Input-Only Activation

### Design

Add a filter in `BehavioralSynthesisPhase` before calling `settle()` that retains only INPUT-typed nodes from `combinedActivations`. Remap `DriveCompetitionDetector.DRIVE_CAPS_MAPPINGS` to reference input-layer proxies.

### Filter implementation

The input-only filter applies inside `mergeDriveIntensities()`, NOT on the combined map. Classification and dissonance activations are designed to target specific CAPS nodes and must not be filtered — the LLM classifier is prompted with input node vocabulary, the rule-based classifier uses input node keywords, and dissonance activations are designed for direct settling (issue #1212).

```java
// In BehavioralSynthesisPhase.mergeDriveIntensities():
// After mapping drive type to CAPS nodes via DRIVE_CAPS_MAPPINGS,
// filter to INPUT nodes before merging into combinedActivations:
for (String nodeId : mappedNodes) {
    CapsNode node = capsEngine.topology().nodes().get(nodeId);
    if (node != null && node.type() == NodeType.INPUT) {
        combinedActivations.merge(nodeId, intensity, Math::max);
    }
}
```

### Remap table (verified against runtime topology)

**Tier 1 — 1-hop backward trace (8 entries):**

| Drive target | Input proxy | Topology path | Weight |
|-------------|-------------|---------------|--------|
| BAS_activation | `reward` | reward → BAS_activation | 0.50 |
| FFFS_activation | `physical_threat` | physical_threat → FFFS_activation | 0.55 |
| threat_sensitivity | `physical_threat` | physical_threat → threat_sensitivity | 0.50 |
| self_worth | `secure_attachment` | secure_attachment → self_worth | 0.30 |
| proximity_seek | `inconsistent_care` | inconsistent_care → proximity_seek | 0.40 |
| BIS_activation | `social_threat` | social_threat → BIS_activation | 0.40 |
| self_efficacy | `mastery` | mastery → self_efficacy | 0.30 (empirical) |
| other_safety | `perceived_responsiveness` | perceived_responsiveness → other_safety | 0.35 |
| other_reliability | `perceived_responsiveness` | perceived_responsiveness → other_reliability | 0.25 |

**Tier 2 — multi-hop trace (5 entries):**

| Drive target | Input proxy | Path |
|-------------|-------------|------|
| approach | `reward` | reward → BAS_activation → approach (2-hop) |
| trust | `secure_attachment` | secure_attachment → self_worth → trust (2-hop) |
| explore | `reward` | reward → BAS_activation → explore (2-hop) |
| distrust | `betrayal` | betrayal → other_reliability → distrust (2-hop, neg×neg) |
| assert, self_direct | `agency_granted` | agency_granted → self_efficacy → assert/self_direct (2-hop) |

**Tier 3 — semantic proxy, topology gap (2 entries):**

| Drive target | Input proxy | Rationale |
|-------------|-------------|-----------|
| persist | `reward` | Only incoming: future_outlook (mediating, no input path). Semantic: operant reinforcement. Node is disposition-only — proxy is best-effort. |
| escape_assessment | `unpredictable_danger` | Zero incoming connections. Semantic: trauma pathway. Node is disposition-only — proxy is best-effort. |

---

## 4. Weight Learning (D4) — Multi-Cue Rescorla-Wagner

### Design

Replace single-cue prediction error with textbook multi-cue R-W. Remove dead inhibitory weight system. Add weight clamping.

### Multi-cue update

For each **target node** (not each connection):

1. Compute ensemble prediction: `V_predicted = Σ(w_i × a_i)` over all connections TO this target where `a_i > 0.01`.
2. Compute shared prediction error: `δ = outcomeValence - V_predicted`.
3. For each contributing connection: `Δw_i = effectiveAlpha_i × β × δ × scheduleMod`.
4. Clamp updated weight: `newExcitatory = clamp(cw.excitatory() + Δw_i, -2.0, 2.0)`.

### Precision under multi-cue (Pearce-Hall)

- Precision UPDATE uses the shared `δ`: surprise about a target's outcome affects attention to ALL cues.
- `confirmEpsilon` check uses the shared `δ`: accurate ensemble prediction confirms all cues.
- High-precision connections resist change via `effectiveAlpha = baseAlpha / precision` even when `δ` is large due to OTHER cues. This is the core mechanism: empirical connections remain stable while novel connections adapt.

### Structural changes to CapsWeightUpdater

```java
// Group connections by target node
Map<String, List<CapsConnection>> byTarget = topology.connections().stream()
    .collect(Collectors.groupingBy(CapsConnection::to));

for (var entry : byTarget.entrySet()) {
    String targetId = entry.getKey();
    List<CapsConnection> incoming = entry.getValue();

    // 1. Ensemble prediction
    double vPredicted = 0.0;
    for (CapsConnection conn : incoming) {
        double sourceAct = inputActivations.getOrDefault(conn.from(), 0.0);
        if (Math.abs(sourceAct) < 0.01) continue; // abs — BIPOLAR sources can be negative
        double ew = state.weights().getOrDefault(conn.id(), conn.defaultWeight())
                         .effectiveWeight();
        vPredicted += ew * sourceAct;
    }

    // 2. Shared prediction error
    double delta = context.outcomeValence() - vPredicted;

    // 3. Per-connection weight update with clamping
    for (CapsConnection conn : incoming) {
        // ... alpha, beta, precision logic as before ...
        double deltaW = effectiveAlpha * beta * delta * scheduleMod;
        double newExcitatory = Math.max(-2.0, Math.min(2.0,
            cw.excitatory() + deltaW));
        // ... update precision ...
    }
}
```

### Remove dead code

- Remove `ConnectionWeight.inhibitory()` and `decayResistance()` fields — inhibitory is always zero (only decays from zero), decayResistance has no effect.
- Simplify record to `ConnectionWeight(double excitatory, double precision)`.
- Simplify `effectiveWeight()` to return `excitatory` directly.
- Defer `temporalDiscount` wiring to follow-up — requires a delay parameter not present in the current WeightUpdateContext.
- **Schema migration**: `SqliteCapsEngine` persists connection weights in `caps_connection_weights` table. Add Flyway V2 migration to drop `inhibitory` and `decay_resistance` columns (`ALTER TABLE caps_connection_weights DROP COLUMN inhibitory; ALTER TABLE caps_connection_weights DROP COLUMN decay_resistance;` — supported in SQLite 3.35.0+). Update `loadWeights()` and `replaceWeights()` SQL to match the simplified 2-column record. Pre-release stage — no backward compatibility needed.

---

## 4b. B3 Fix — Regulation Weight Update Persistence

The actual B3 bug site is in `EmotionRegulationTickParticipant.java` (cognition module), not BehavioralSynthesisPhase (which already saves correctly).

Two call sites discard the returned `AgentCapsState`:

1. **Line ~379 (regulation path):** `capsEngine.updateWeights(capsState, ...)` — returned state discarded.
2. **Line ~475 (coping path):** Same pattern.

**Fix:** Capture the returned state and call `capsEngine.saveState(updated)` at both sites, following the same pattern as `BehavioralSynthesisPhase` lines 237-284.

---

## 5. Convergence Detection (D5)

Reduce the wider-oscillation variance threshold from `epsilon × 50` to `epsilon × 10`.

Both variance check sites use the same multiplier:
- In-loop check at ≥20 iterations (line 148-155)
- MAX_ITERATIONS fallback (line 159-185)

Change: `epsilon * 50` → `epsilon * 10` in both locations.

The two-cycle exact oscillation detection (epsilon comparison with prevPrev) remains as the fast path.

---

## 6. Distortions Sign Fix (B5)

In `CapsSettler.applyDistortions()`, fix ADDITIVE distortions to respect belief sign. Currently adds a positive constant regardless of the node's current activation polarity.

The fix: for ADDITIVE distortions, multiply the effect by `Math.signum(currentActivation)` so positive beliefs are amplified and negative beliefs are amplified in their own direction. When activation is zero (no situational signal), the distortion has no effect — consistent with D2's zero-input-zero-activation principle.

---

## 7. CBR Cache Fixes (B10)

Three mechanical fixes in `CbrCachingSituationDecorator`:

### 7.1 Case ID from hit, not query

Line 119: Replace `computeCaseId(description, eventType, cognitiveKind, metadata)` with `hits.getFirst().caseId()`. The case ID should identify the CACHED record, not recompute from the query.

### 7.2 Add PID-5 and appraisal filters to lookup

In `lookupCbr()`, add PID-5 and appraisal metadata as categorical filters, matching what `computeCaseId()` and `storeCbr()` include. Only add filters for keys present in the metadata (graceful when metadata is sparse).

### 7.3 Valence categorical filter (D6)

Derive valence from CAPS activations:
- **Positive**: dominant attractor from approach, trust, proximity_seek, persist, risk_take, self_direct, rebel, explore
- **Negative**: dominant attractor from withdraw, distrust, distance_maintain, flight, freeze, fawn, submit, abandon, comply, depend
- **Neutral**: fight, assert, cautious_approach, consolidate, generalize, discriminate, perfectionism

Store as `FeatureValue.string(valence)` in features. Add `CbrFilter.contains(valence)` to lookup query.

---

## 8. ClassificationOutcomeEvaluator (B9)

Change OSCILLATION convergence factor from 0.3 to 0.7. Oscillation between competing attractors is a valid cognitive state (Mischel & Shoda 1995), not near-failure.

The evaluator will also naturally improve once B1 is fixed — with differentiated attractor strengths, `maxAttractorStrength` varies meaningfully across agents and situations.

---

## 9. Topology Fixes

### N3: Autonomy disposition modifiers

Fix YAML keys in `caps-topology.yaml` disposition_modifiers.autonomy from `low`/`high` to `independent`/`dependent` to match `DispositionAxes.autonomy()` return values.

### N4: Resting activation clamping

Add clamping in `DispositionWeightMapper.addResting()` itself (applied on every call) so that all sources — disposition axes AND coping defaults — are clamped:
- BIPOLAR nodes: clamp to `[-0.5, 0.5]`
- UNIPOLAR nodes: clamp to `[0.0, 0.5]`

The 0.5 upper bound ensures resting activations don't dominate situational input. Clamping per-call in `addResting()` prevents coping contributions from pushing beyond the bounds after disposition axes have already contributed.

### N1: Remove dead inhibitory weights

Part of D4. Remove `ConnectionWeight.inhibitory()`, `decayResistance()`. Simplify record to `(excitatory, precision)`.

### N2: Excitatory weight clamping

Part of D4. Clamp to `[-2.0, 2.0]` matching the existing `effectiveWeightCap`.

---

## 10. Downstream Threshold Recalibration (D9)

Audit and recalibrate all consumers that compare attractor strengths against thresholds:

| Consumer | Threshold | Action |
|----------|-----------|--------|
| `RegulationCascadeConfig.defaults()` | regulationConfidenceThreshold=0.3, regulationDominanceMargin=0.15 | Review — under BIPOLAR, attractor gaps widen (baseline drops from ~0.5 to ~0.0) |
| `ClassificationOutcomeEvaluator` | attractorFactor = max strength | B9 fix + verify scale under BIPOLAR |
| `BehavioralSynthesisPhase.createOrStrengthenAttractor()` | emaRetention=0.5, reinforcementBoostCap=0.5 | Review scaling on new BIPOLAR strength scale |
| `RegulationCascadeTest` | Hardcoded 0.5, 0.4, 0.35 | Update for BIPOLAR output scale |
| `CopingMicroLoopTest` | Hardcoded 0.9 | Update for BIPOLAR output scale |

---

## 11. Verification (D7)

### Epic criterion tests (new)

1. **`noInputRankingDiffersFromThreatRanking`**: Settle with empty input map, settle with `physical_threat=1.0`. Assert top-3 attractor node IDs differ between the two results.

2. **`oppositePersonalitiesDiverge`**: Initialize bold+competitive agent and conservative+avoidant agent. Settle both under identical input. Assert max attractor strength difference > 0.3 (absolute).

### Existing test updates

Update all `CapsEngineContractTest` assertions for the new BIPOLAR/rectified-tanh scale. Key changes:
- Resting levels for output nodes drop from 0.5 to 0.0
- Activation range for outputs is [-1, 1] not [0, 1]
- `inputNodesAreClampedDuringSettling` assertions unchanged (input clamping is separate)

### Integration test (new)

`BehavioralSynthesisPhaseTest` exercising:
- Drive injection through `mergeDriveIntensities()` → `settle()` boundary (validates D3 filter + remap)
- End-to-end: input activations → settling → weight update → attractor persistence
- Drive activations targeting non-INPUT nodes are correctly filtered

---

## 12. Commit Discipline (D8)

Each finding gets its own commit within a single PR. Intermediate test validation after each commit. Order:

1. **D2 (B1 + N6)**: BIPOLAR/rectified-tanh + activation clamp + NodeRange.restingLevel() — foundational
2. **N3**: Autonomy modifier key fix — independent of D2
3. **N4**: Resting activation clamping — depends on D2 for range semantics
4. **B5**: Distortion sign fix — depends on D2 for activation function
5. **B6/D5**: Convergence threshold tightening
6. **D4 (B2 + N1 + N2)**: Multi-cue R-W + inhibitory removal + weight clamping + Flyway V2
7. **B3**: Regulation weight update persistence (EmotionRegulationTickParticipant)
8. **D3 (B12)**: Drive injection filter + remap (inside mergeDriveIntensities)
9. **B9**: ClassificationOutcomeEvaluator OSCILLATION fix
10. **B10/D6**: CBR cache fixes + valence filter
11. **D9**: Downstream threshold recalibration
12. **D7 (B17)**: Verification tests (epic criterion + integration)

---

## References

- `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsSettler.java` — settler algorithm
- `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsWeightUpdater.java` — weight learning
- `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/DispositionWeightMapper.java` — personality → weights
- `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/CapsTopologyLoader.java` — YAML parsing
- `caps-engine/src/main/resources/caps-topology.yaml` — runtime topology (1816 lines)
- `caps-api/src/main/java/io/casehub/neocortex/caps/DriveCompetitionDetector.java:28-43` — DRIVE_CAPS_MAPPINGS
- `caps-situation-cbr/src/main/java/io/casehub/neocortex/caps/cbr/CbrCachingSituationDecorator.java` — CBR cache
- `mindmap-intelligence/.../consolidation/BehavioralSynthesisPhase.java` — settle() caller
- `mindmap-intelligence/.../consolidation/ClassificationOutcomeEvaluator.java` — outcome scoring
- `caps-testing/.../CapsEngineContractTest.java` — 13 contract tests
- `specs/issue-1192-caps-trajectory-divergence/2026-11-22-caps-trajectory-divergence-design.md` — prior feedback loop work
- `specs/issue-1212-direct-caps-evaluation/2026-11-23-direct-caps-evaluation-design.md` — prior dissonance integration
- Epic #1222 — finding descriptions and verification criterion
- `docs/specs/cognitive-review-analysis/2026-11-24-cognitive-review-triage.md` — triage classifications

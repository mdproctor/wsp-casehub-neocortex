# Decisions — SE2: CAPS Rework

## D1: Scope expansion — include new findings

**Choice:** Include all 6 new findings discovered during exploration alongside the 8 triaged findings (14 total)
**Alternatives:**
- Include critical only (#3 autonomy, #4 unclamped resting) — leaves 4 bugs unfixed in the same files
- Original scope only (8 triaged) — requires a second pass through the same code with the same test cycle
**Rationale:** All 14 findings are in the same files (CapsSettler, CapsWeightUpdater, DispositionWeightMapper, BehavioralSynthesisPhase). Fixing the settler baseline (B1) without fixing autonomy modifiers or unclamped resting activations would leave the settler still producing wrong results. Single pass through the code is cheaper than two.
**Trade-offs:** Larger scope increases risk of the epic exceeding its L/High estimate. Mitigated by the fact that most new findings are mechanical fixes.
**Sources:** Explorer agents' code analysis of caps-engine/, caps-api/, caps-testing/
**Exploration:** quick
**Status:** captured

## D2: Settler baseline — BIPOLAR for mediating/output nodes

**Choice:** Convert mediating and output nodes from UNIPOLAR (logistic, resting at 0.5) to BIPOLAR (tanh, resting at 0.0)
**Alternatives:**
- Fix attractor extraction only — keep unipolar but report delta above background. Quick but 0.5×w background still flows through the network, consuming dynamic range
- Zero-shifted logistic (logistic(x) - 0.5) — mathematically ≈ tanh(x/2), adds complexity without semantic clarity
**Rationale:** CAPS theory prescribes that only situational input should activate the network. BIPOLAR with tanh gives zero activation for zero input. The codebase already supports BIPOLAR via NodeRange enum and the tanh path in CapsSettler. This is the cleanest fix — zero input produces zero activation.
**Trade-offs:** Breaks absolute scale — BIPOLAR outputs range [-1, 1] instead of [0, 1]. Attractor extraction, strength comparison, CopingDefaults resting activation math, and downstream consumers all need adjustment. The CopingDefaults formula `(tendency - 0.5) * 0.5` assumes unipolar center and needs re-centering.
**Sources:** CapsSettler.java lines 90-95 (activation functions), CapsNode.java/NodeRange.java (enum), epic #1222 B1
**Exploration:** quick
**Status:** captured

## D3: Drive injection — filter to input nodes + remap

**Choice:** Filter `combinedActivations` to INPUT nodes only before calling `settle()`. Remap `DriveCompetitionDetector.DRIVE_CAPS_MAPPINGS` to reference input-layer nodes.
**Alternatives:**
- Allow forced non-input activations in settle() — changes SPI, adds complexity, suppresses natural network computation
- Fix mappings only without filtering — non-input entries are silently no-ops anyway, but future maintainers may re-add mediating nodes thinking they work
**Rationale:** Makes the settler's input contract explicit. Forces the drive-to-CAPS mappings to be semantically correct at the input layer. E.g., "approach" (output) → "reward" + "agency_granted" (input proxies).
**Trade-offs:** Some drive-to-CAPS mappings genuinely express concepts at the mediating/output layer ("self_efficacy", "approach"). The remapped input-layer proxies are less precise semantically.
**Depends on:** D2 (BIPOLAR changes output-layer behavior)
**Sources:** DriveCompetitionDetector.java lines 28-43 (DRIVE_CAPS_MAPPINGS), BehavioralSynthesisPhase.java line 207 (settle call), Explorer agent B12 confirmation
**Exploration:** quick
**Status:** captured

## D4: Weight learning — proper multi-cue Rescorla-Wagner

**Choice:** Implement textbook multi-cue R-W with cue competition: prediction error = `outcomeValence - Σ(w_i × a_i)` summed over all active cues to each target node. Remove dead inhibitory weight system. Add excitatory weight clamping [-2.0, 2.0]. Wire temporalDiscount for recency.
**Alternatives:**
- Simplify to Hebbian (Δw = α×a_src×a_tgt) — no error correction, loses cue competition which is the whole point of R-W in a personality network
- Fix bugs but keep single-cue — leaves the per-connection update which has fixed point w = valence/activation per link (not wrong but limited — no competition between cues)
**Rationale:** Cue competition is the core property of R-W that matters for personality-dependent learning — it means that strong predictors suppress learning for weaker ones, producing differentiated weight patterns across personalities. The topology is small enough (163 connections) for multi-cue to be computationally trivial.
**Trade-offs:** Structural change to the update loop (currently per-connection, needs per-target-node summation). Existing test assertions on specific weight values may need updating. Different weight trajectories from the old single-cue rule.
**Sources:** CapsWeightUpdater.java lines 36-87 (current update loop), ConnectionWeight.java (dual-weight record), WeightUpdateParameters.java (unused temporalDiscount/vicariousDiscount)
**Exploration:** quick
**Status:** captured

## D5: Convergence detection — tighten variance threshold

**Choice:** Reduce wider-oscillation variance threshold from `epsilon × 50` (0.05) to `epsilon × 10` (0.01). Keep two-cycle exact oscillation detection as fast path.
**Alternatives:**
- Per-node convergence (each node individually settled) — stricter but significantly increases iteration counts for the 107-node topology
- Energy-based convergence (total squared activation change) — more principled but adds a new concept to the codebase
**Rationale:** Minimal change that fixes the specific problem. Variance 0.01 allows only oscillations with amplitude ~0.1 (√0.01), which catches most genuine convergence while rejecting the persistent oscillations B6 describes.
**Trade-offs:** Some edge cases near the boundary may flip between CONVERGED and OSCILLATION. This is acceptable — the new threshold is still generous enough for genuine convergence.
**Sources:** CapsSettler.java lines 148-155 (wider oscillation detection), epic #1222 B6
**Exploration:** quick
**Status:** captured

## D6: CBR cache polarity — valence categorical filter

**Choice:** Derive valence from CAPS activations (approach-dominant = positive, avoid-dominant = negative). Store as categorical feature. Add `CbrFilter.contains(valence)` to lookup query.
**Alternatives:**
- Raise cosine similarity threshold to 0.95 — reduces cache hit rate significantly, losing the cache's benefit
- Cross-encoder reranking — adds latency (defeats the purpose of a fast cache) and requires model availability
**Rationale:** No LLM call needed — valence is derivable from the CAPS activations being cached. Minimal new code (one new categorical feature + one filter in lookup). Preserves the 0.85 similarity threshold for genuine matches.
**Trade-offs:** Valence classification from CAPS activations is coarse (positive/negative/neutral). Ambivalent situations (simultaneous approach+avoid) would need a "mixed" category.
**Sources:** CbrCachingSituationDecorator.java lines 132-155 (lookupCbr), lines 158-187 (storeCbr)
**Exploration:** quick
**Status:** captured

## D7: Verification strategy — epic criterion + fix existing tests

**Choice:** Update existing CapsEngineContractTest for BIPOLAR scale. Add two new tests implementing the epic's verification criterion: (1) no-input ranking differs from threat ranking, (2) opposite personalities diverge > 0.3 under same input.
**Alternatives:**
- Comprehensive matrix (5 profiles × 5 scenarios × 3 intensities with statistical distance) — thorough but heavy and premature before proving the fundamentals work
**Rationale:** The epic defines clear, testable criteria. Write exactly those tests. If they pass, the settler is working correctly. Matrix testing is a follow-up once fundamentals are proven.
**Trade-offs:** Minimum viable verification — doesn't add trajectory tests or cross-profile statistical tests. Sufficient for this rework scope.
**Sources:** Epic #1222 verification section, CapsEngineContractTest.java (13 existing tests)
**Exploration:** quick
**Status:** captured

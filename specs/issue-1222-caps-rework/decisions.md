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

## D2: Settler baseline — selective BIPOLAR + rectified tanh for UNIPOLAR

**Choice:** Convert output nodes to BIPOLAR (tanh, resting at 0.0) by changing `defaultRange(OUTPUT)`. Replace logistic with rectified tanh (`max(0, tanh(x))`) for UNIPOLAR mediating nodes — preserving [0, 1] range while achieving zero resting. Keep topology-specified per-node ranges for mediating nodes (7 BIPOLAR cognitive schemas, 14 UNIPOLAR activation-level constructs).
**Alternatives:**
- Blanket BIPOLAR for all mediating/output nodes — simple but destroys the topology's principled mixed-range design. BAS_activation, BIS_activation, FFFS_activation etc. are activation-level constructs where negative values are semantically meaningless. The topology YAML annotates these as `type: unipolar` with `range: [0, 1]` for good reason.
- Selective BIPOLAR for outputs only, keep logistic for UNIPOLAR mediating — leaves the 0.5 resting background problem. BAS_activation at logistic(0)=0.5 feeds 0.5×0.60=0.30 into approach via its connection weight, creating spurious approach activation from zero BAS stimulation.
- Fix attractor extraction only — 0.5×w background still flows through the network
- Zero-shifted logistic (logistic(x) - 0.5) — mathematically ≈ tanh(x/2), no advantage over rectified tanh
**Rationale:** The topology YAML has a principled mixed-range design: cognitive schemas (self_worth, self_efficacy, other_reliability, other_safety, world_predictability, future_outlook, reinforcement_expectation) are BIPOLAR with genuine bipolar semantics (e.g., "worthless ↔ worthy"); activation-level constructs (BAS_activation, BIS_activation, FFFS_activation, arousal_level, threat_sensitivity, etc.) are UNIPOLAR because negative activation is meaningless. D2's core goal — zero input produces zero activation — is achieved for BOTH types: `tanh(0) = 0` for BIPOLAR, `max(0, tanh(0)) = 0` for UNIPOLAR. Output nodes default to BIPOLAR because behavioral approach/avoidance has natural polarity.
**Trade-offs:** Replaces logistic with rectified tanh for UNIPOLAR path — simpler computation (`Math.max(0, Math.tanh(x))` vs `1/(1+exp(-x))`). Attractor extraction baselines change because output restingLevel moves from 0.5 to 0.0 — downstream threshold recalibration needed (see D9). CopingDefaults `copingBias` formula `(tendency - 0.5) * 0.5` is UNAFFECTED: the 0.5 is the population-mean center on the tendency scale [0, 1], not the activation range center.
**Sources:** CapsSettler.java lines 90-95 (activation functions), 2026-10-02-caps-topology.yaml (mixed range annotations — 7 bipolar + 14 unipolar mediating nodes), CapsNode.java/NodeRange.java (enum), epic #1222 B1, R1-02 review
**Exploration:** quick → revised via adversarial review R1-02
**Status:** revised — selective conversion replaces blanket BIPOLAR per R1-02's evidence on topology's intentional mixed-range design

## D3: Drive injection — filter to input nodes + remap

**Choice:** Filter `combinedActivations` to INPUT nodes only before calling `settle()`. Remap `DriveCompetitionDetector.DRIVE_CAPS_MAPPINGS` to reference input-layer nodes using backward topology tracing.
**Alternatives:**
- Forced non-input activations via `forced_activation` parameter in settle() — violates the settler's layered architecture. External stimuli enter at the input layer; the network computes mediating/output. Initial-activation injection is too weak (overwritten by activation function in first settling iteration); clamped injection overrides learned network dynamics and destroys personality differentiation. The CAPS model depends on input signals propagating through personality-specific connection weights.
- Fix mappings only without filtering — non-input entries are silently no-ops anyway, but future maintainers may re-add mediating nodes thinking they work
**Remap methodology:** Three-tier approach verified against the runtime topology (`caps-engine/src/main/resources/caps-topology.yaml`, 1816 lines):
1. **Topology-traced** (1-hop backward connection verified)
2. **Multi-hop traced** (2-3 hop backward path verified)
3. **Semantic proxy** (no topology path exists — mapped by psychological theory, explicitly marked as topology gap)

**Tier 1 — topology-traced (1-hop, verified):**
- BAS_activation → `reward` (reward → BAS_activation, 0.50)
- FFFS_activation → `physical_threat` (physical_threat → FFFS_activation, 0.55)
- threat_sensitivity → `physical_threat` (physical_threat → threat_sensitivity, 0.50)
- self_worth → `secure_attachment` (secure_attachment → self_worth, 0.30)
- proximity_seek → `inconsistent_care` (inconsistent_care → proximity_seek, 0.40)
- BIS_activation → `social_threat` (social_threat → BIS_activation, 0.40, Dickerson & Kemeny 2004)
- self_efficacy → `mastery` (mastery → self_efficacy, 0.30, **empirical**, Bandura 1997)
- other_safety → `perceived_responsiveness` (perceived_responsiveness → other_safety, 0.35, Reis et al. 2004)

**Tier 2 — multi-hop traced (verified):**
- approach → `reward` (reward → BAS_activation → approach, 2-hop)
- trust → `secure_attachment` (secure_attachment → self_worth → trust, 2-hop)
- explore → `reward` (reward → BAS_activation → explore, 2-hop, Berlyne 1960)
- distrust → `betrayal` (betrayal → other_reliability (-0.45) → distrust (-0.45), 2-hop, negative × negative = positive effect)
- assert, self_direct → `agency_granted` (agency_granted → self_efficacy → assert/self_direct, 2-hop, Deci & Ryan SDT)

**Tier 3 — semantic proxy (topology gap):**
- persist → `reward` (only incoming: future_outlook (mediating, 0.40) — no input-node backward path; semantic: operant reinforcement)
- escape_assessment → `unpredictable_danger` (zero incoming connections; semantic: trauma pathway)
- other_reliability → `secure_attachment` (only incoming are negative-weight: inconsistent_care (-0.30), rejection (-0.35), betrayal (-0.45) — all invert drive intent; semantic: attachment theory)
**Rationale:** Makes the settler's input contract explicit. Forces the drive-to-CAPS mappings to be semantically correct at the input layer. Each remap is grounded in the topology connections and source psychological models. Input proxies ensure drives activate the SAME downstream nodes through the network's learned dynamics — same input, different responses via different connection weights — which is how personality differentiation works.
**Trade-offs:** Some semantic precision is lost — drives targeting mediating/output nodes expressed concepts at those layers. But the indirect activation through input proxies is CORRECT behavior: drive intensity should influence the network proportionally to connection strengths, not bypass them.
**Sources:** DriveCompetitionDetector.java lines 28-43, BehavioralSynthesisPhase.java line 207, caps-engine/src/main/resources/caps-topology.yaml (runtime topology, 1816 lines), Explorer agent B12, R1-04/R1-05/R2-02/R3-02 review
**Exploration:** quick → revised via adversarial review R1-04 (dependency removed), R1-05 (remap added), R2-02 (three-tier methodology), R3-02 (tier classifications corrected against runtime topology)
**Status:** revised — tier classifications corrected per R3-02; 8 Tier 1, 5 Tier 2, 3 Tier 3 (down from 5/4/7)

## D4: Weight learning — proper multi-cue Rescorla-Wagner

**Choice:** Implement textbook multi-cue R-W with cue competition: prediction error = `outcomeValence - Σ(w_i × a_i)` summed over all active cues to each target node. Remove dead inhibitory weight system. Add excitatory weight clamping [-2.0, 2.0]. Wire temporalDiscount for recency.
**Precision integration strategy (Pearce-Hall under multi-cue):**
1. Precision UPDATE uses the shared per-target prediction error — surprise about a target's outcome affects attention to ALL cues contributing to that target (standard Pearce-Hall)
2. `confirmEpsilon` check uses the shared error — accurate ensemble prediction confirms all contributing cues simultaneously
3. High-precision connections resist change via `effectiveAlpha = baseAlpha / precision` even when the shared error is large due to OTHER cues — well-established personality traits (empirical provenance, high precision) should not be destabilized by novel cue associations. This is the core mechanism: surprising outcomes primarily update low-precision (novel/uncertain) connections while empirical connections remain stable.
**Alternatives:**
- Simplify to Hebbian (Δw = α×a_src×a_tgt) — no error correction, loses cue competition which is the whole point of R-W in a personality network
- Fix bugs but keep single-cue — leaves the per-connection update which has fixed point w = valence/activation per link (not wrong but limited — no competition between cues)
**Rationale:** Cue competition is the core property of R-W that matters for personality-dependent learning — it means that strong predictors suppress learning for weaker ones, producing differentiated weight patterns across personalities. The topology is small enough (163 connections) for multi-cue to be computationally trivial.
**Trade-offs:** Structural change to the update loop (currently per-connection, needs per-target-node summation). Existing test assertions on specific weight values may need updating. Different weight trajectories from the old single-cue rule.
**Sources:** CapsWeightUpdater.java lines 36-87 (current update loop), ConnectionWeight.java (dual-weight record), WeightUpdateParameters.java (unused temporalDiscount/vicariousDiscount), R1-06 review
**Exploration:** quick → revised via adversarial review R1-06 (precision strategy specified)
**Status:** revised — precision integration strategy added

## D5: Convergence detection — tighten variance threshold

**Choice:** Reduce wider-oscillation variance threshold from `epsilon × 50` (0.05) to `epsilon × 10` (0.01). Keep two-cycle exact oscillation detection as fast path. Both variance check sites (in-loop at ≥20 iterations, and MAX_ITERATIONS fallback) use the same multiplier `epsilon × 10`.
**Alternatives:**
- Per-node convergence (each node individually settled) — stricter but significantly increases iteration counts for the 107-node topology
- Energy-based convergence (total squared activation change) — more principled but adds a new concept to the codebase
**Rationale:** Minimal change that fixes the specific problem. Variance 0.01 allows only oscillations with amplitude ~0.1 (√0.01), which catches most genuine convergence while rejecting the persistent oscillations B6 describes.
**Interaction with D2:** Under revised D2, output nodes are BIPOLAR [-1,1] while UNIPOLAR mediating nodes keep [0,1]. Variance 0.01 represents amplitude ~0.1, which is 5% of BIPOLAR range and 10% of UNIPOLAR range. Both are acceptable convergence criteria — 5% oscillation on a BIPOLAR output node is minor oscillation that does not warrant further iterations. No range-normalization of the threshold is needed.
**Trade-offs:** Some edge cases near the boundary may flip between CONVERGED and OSCILLATION. This is acceptable — the new threshold is still generous enough for genuine convergence.
**Sources:** CapsSettler.java lines 148-155 (wider oscillation detection), epic #1222 B6, R1-07 review
**Exploration:** quick → updated via adversarial review R1-07
**Status:** revised — D2 interaction and dual-check clarification added

## D6: CBR cache polarity — valence categorical filter

**Choice:** Derive valence from CAPS activations. Under revised D2 (BIPOLAR outputs), classify the dominant attractor's output node by its intrinsic approach/avoidance character. Store as categorical feature. Add `CbrFilter.contains(valence)` to lookup query.
**Operational definition:**
- Positive valence: dominant attractor from approach_avoidance:approach, social:trust/proximity_seek, achievement:persist/risk_take, autonomy:self_direct/rebel, learning:explore
- Negative valence: dominant attractor from approach_avoidance:withdraw, social:distrust/distance_maintain, conflict:flight/freeze/fawn/submit, achievement:abandon, autonomy:comply/depend
- Neutral: conflict:fight/assert (approach-like but not "positive"), approach_avoidance:cautious_approach, learning:consolidate/generalize/discriminate, achievement:perfectionism
**Alternatives:**
- Use attractor category as filter — too coarse. Category (social, conflict, achievement) doesn't distinguish approach vs avoidance within a category. The purpose of D6 is polarity discrimination to prevent CBR from returning polarity-inverted results, not category matching.
- Raise cosine similarity threshold to 0.95 — reduces cache hit rate significantly, losing the cache's benefit
- Cross-encoder reranking — adds latency (defeats the purpose of a fast cache) and requires model availability
**Rationale:** No LLM call needed — valence is derivable from the CAPS activations being cached. Minimal new code (one new categorical feature + one filter in lookup). Preserves the 0.85 similarity threshold for genuine matches.
**Trade-offs:** Valence classification from CAPS activations is coarse (positive/negative/neutral). Ambivalent situations (simultaneous approach+avoid) would need a "mixed" category.
**Sources:** CbrCachingSituationDecorator.java lines 132-155 (lookupCbr), lines 158-187 (storeCbr), R1-08 review
**Exploration:** quick → revised via adversarial review R1-08 (operational definition added)
**Status:** revised — operational definition and attractor-category alternative rejection added

## D7: Verification strategy — epic criterion + fix existing tests + integration

**Choice:** Update existing CapsEngineContractTest for BIPOLAR/rectified-tanh scale. Add two new tests implementing the epic's verification criterion: (1) no-input ranking differs from threat ranking, (2) opposite personalities diverge > 0.3 absolute activation difference under same input. Add BehavioralSynthesisPhase integration test exercising the full classify → merge → settle → update → persist pipeline.
**Integration test scope:** BehavioralSynthesisPhaseTest should exercise:
- Drive injection through mergeDriveIntensities() → settle() boundary (validates D3 filter + remap)
- End-to-end data flow: input activations → settling → weight update → attractor persistence
- Verify that drive activations targeting non-INPUT nodes are correctly remapped and not silently ignored
**Alternatives:**
- Comprehensive matrix (5 profiles × 5 scenarios × 3 intensities with statistical distance) — thorough but heavy and premature before proving the fundamentals work
**Rationale:** The epic defines clear, testable criteria. Write exactly those tests. The divergence threshold is 0.3 absolute activation difference — the same value as the epic's original criterion. Under BIPOLAR/tanh (which amplifies personality differences near rest due to tanh'(0)=1.0 vs logistic'(0)=0.25), this threshold will be easier to meet, which is acceptable: the test validates that the rework produces meaningfully differentiated outputs. If the threshold proves trivially met under BIPOLAR, it can be tightened empirically in a follow-up. Integration-level coverage is essential because the bugs manifest at the BehavioralSynthesisPhase boundary, not in the settler math alone.
**Trade-offs:** Minimum viable verification — doesn't add trajectory tests or cross-profile statistical tests. Sufficient for this rework scope.
**Sources:** Epic #1222 verification section, CapsEngineContractTest.java (13 existing tests), BehavioralSynthesisPhaseTest.java, R1-09/R2-03 review
**Exploration:** quick → revised via adversarial review R1-09 (integration tests), R2-03 (threshold corrected)
**Status:** revised — integration test added; threshold corrected to 0.3 absolute per R2-03

## D8: Commit discipline — atomic commits per finding

**Choice:** Each finding gets its own commit with its own test assertion within the single PR. Intermediate test validation after each commit. Git bisect-friendly history.
**Alternatives:**
- Single commit for all 14 findings — harder to isolate regressions, git bisect useless across a 14-finding change
- Multiple PRs (D1's rejected alternative) — same test cycle overhead, unnecessary process overhead
**Rationale:** Addresses the 14-finding scope risk (D1 trade-off) without the overhead of multiple PRs. If any finding causes a subtle personality differentiation regression, git bisect isolates it in O(log 14) = 4 commits. Each commit is independently revertable without touching the others.
**Sources:** R1-10 review (implicit decision surfaced)
**Exploration:** n/a — implicit decision surfaced by review
**Status:** captured

## D9: Downstream threshold recalibration strategy

**Choice:** Explicit audit and recalibration of all downstream consumers that compare attractor strengths against configured thresholds. Recalibration is part of D2's implementation scope, performed before merging the rework PR.
**Consumers requiring recalibration:**
- `RegulationCascadeConfig.defaults()`: regulationConfidenceThreshold=0.3, regulationDominanceMargin=0.15 — used by EmotionRegulationTickParticipant (line ~281) and CopingMicroLoop (line ~155). Under BIPOLAR outputs, attractor gaps widen because baseline drops from ~0.5 to ~0.0. These thresholds may need lowering to maintain equivalent selectivity.
- `ClassificationOutcomeEvaluator`: uses `attractorFactor` as raw max attractor strength in CBR outcome evaluation. Under BIPOLAR, max strength ≈ settled value (not settled − 0.5). The successRate computation may produce higher values, affecting CBR learning rates.
- `BehavioralSynthesisPhase.createOrStrengthenAttractor()`: applies `emaRetention` (0.5) and `reinforcementBoostCap` (0.5) to attractor strength. These operate on the new BIPOLAR strength scale — review scaling.
- Test assertions: `RegulationCascadeTest` (hardcoded 0.5, 0.4, 0.35), `CopingMicroLoopTest` (hardcoded 0.9) — update for BIPOLAR output scale.
**Rationale:** Under revised D2, output nodes switch from UNIPOLAR restingLevel=0.5 to BIPOLAR restingLevel=0.0. Attractor strength gaps widen because baseline drops from ~0.5 to ~0.0 for default agents. All threshold-based consumers must be audited and recalibrated as part of the same PR, not discovered post-hoc during integration testing.
**Sources:** EmotionRegulationTickParticipant.java, CopingMicroLoop.java, ClassificationOutcomeEvaluator.java, RegulationCascadeConfig.java, R1-03/R1-11 review
**Exploration:** n/a — implicit decision surfaced by review
**Status:** captured

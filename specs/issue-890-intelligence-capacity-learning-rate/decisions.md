# Decisions — #890 Intelligence Capacity Learning Rate Modulation

## D1: Scope — Full learning sweep

**Choice:** Modulate all 6 unmodulated learning/adaptation sites, not just memory subsystem
**Alternatives:**
- Memory-focused (CBR + graduation only) — tighter scope, matches issue description literally, but leaves Investment Theory half-realized
- Memory + CAPS only — covers pattern acquisition but misses drive/strategy/personality adaptation
**Rationale:** Cattell's Investment Theory implies cognitive capacity pervades all learning, not just memory. Partial application would create inconsistency — some subsystems capacity-aware, others not.
**Trade-offs:** Scale increases from M to L. Touches many modules across memory, cognition, CAPS, and mindmap-intelligence.
**Sources:** Issue #890, Cattell (1971) Investment Theory
**Exploration:** quick
**Status:** captured

## D2: Modulation formula — Linear multiplier with ceiling exceptions

**Choice:** `effectiveLR = baseLR * capacityDimension` for 4 of 6 sites. PersonalityEvolutionOrchestrator and StrategyLearningOrchestrator use ceiling pattern (scale their respective ceilings — `l2Ceiling` and `maxDimensionDelta` — by capacity).
**Alternatives:**
- Ceiling bound for all — matches SearchBudget pattern but awkward for already-small learning rates
- Logarithmic scaling — diminishing returns, but compressed [0.55, 0.95] range (from `compressCapacity()` in CDE: `0.55 + raw * 0.4`) already provides that implicitly; adds complexity for negligible differentiation
- Asymmetric scaling (novel vs routine) — theoretically grounded in Investment Theory but differentiation smaller than system noise in the [0.55, 0.95] band; refinement for later
**Rationale:** Uses `rate * capability` pattern — the semantic inverse of the existing `rate * (1 - resource-consumed)` pattern used by regulation and drive adaptation. Both are linear multipliers but with opposite polarity: capacity is an "available" quantity, depletion is a "consumed" quantity. PersonalityEvolution and StrategyLearning exceptions because `l2Ceiling` and `maxDimensionDelta` are already ceilings — scaling a ceiling by capacity is more natural than multiplying a rate.
**Trade-offs:** Loses Investment Theory asymmetry (Gf helping novel patterns more than routine). Acceptable because compressed capacity range makes the practical difference negligible. At capacity=0.0 (below CDE's output range but within config bounds), `baseLR * 0 = 0` — agent cannot learn. Acceptable edge case: explicit zero capacity is a deliberate configuration choice.
**Sources:** CapsWeightUpdater:48-66, DriveAdaptationPhase:220-248, EmotionRegulationTickParticipant:105-108, PersonalityEvolutionOrchestrator:103-110, CognitiveDerivationEngine:298-299, Cattell (1971)
**Exploration:** deep-analysis
**Status:** revised (R1-07 rationale fix, R1-08 StrategyLearning reclassified as ceiling, R1-12 range sourced)

## D3: Documentation — Literature-linked Javadoc on all capacity modulation

**Choice:** Every modulation site gets Javadoc citing the literature or design decision that justifies the formula and dimension mapping.
**Alternatives:**
- Code-only (no Javadoc) — faster but loses the "why" for future readers
- Centralized mapping table in ARC42STORIES §8 — easier to maintain but readers need context at the code site, not a cross-reference they have to look up
**Rationale:** User requirement. Capacity modulation is psychologically grounded — the mapping from capacity dimension to learning site is a design claim, not an implementation detail. Without Javadoc linking to Cattell, Halford, Mednick, Engle & Kane, the code reads as arbitrary multipliers.
**Trade-offs:** More verbose code. Acceptable because these are permanent architectural decisions.
**Sources:** User directive
**Exploration:** quick
**Status:** revised (R1-13 alternative acknowledged)

## D4: Dimension-to-site mapping

**Choice:** Single capacity dimension per site, mapped by cognitive substrate relevance:
- CapsWeightUpdater → associativeReach (Rescorla-Wagner associative learning; Mednick 1962)
- CbrRecordStore.recordOutcome → workingMemorySpan (multi-factor outcome evaluation; Engle & Kane 2004)
- DriveAdaptationPhase → associativeReach (drive-outcome connection breadth; Mednick 1962)
- StrategyLearningOrchestrator → workingMemorySpan (multi-dimensional strategy tracking; Engle & Kane 2004)
- DefaultGraduationScorer → relationalComplexity (abstracting from experience; Halford 1998)
- PersonalityEvolutionOrchestrator → relationalComplexity (self-model complexity; Halford 1998)
**Alternatives:**
- Composite (weighted combination of dimensions per site) — more nuanced but harder to explain and test; one dimension per site is already a strong signal
- All sites use same dimension — ignores that the three dimensions measure distinct cognitive substrates
- CAPS on relationalComplexity — Halford measures hierarchical reasoning depth, but Rescorla-Wagner is fundamentally associative learning (stimulus-response strength update), not hierarchical reasoning
**Rationale:** Each capacity dimension maps to a distinct cognitive operation (Halford = depth, Mednick = breadth, Engle & Kane = context retention). Revised CAPS mapping from relationalComplexity to associativeReach because Rescorla-Wagner prediction-error learning (`ΔW = α × β × (λ - V)`) is the textbook definition of associative learning. This produces a balanced 2-2-2 split across dimensions.
**Trade-offs:** Loses multi-dimensional interaction effects. Acceptable as first realization.
**Sources:** Halford (1998), Mednick (1962), Engle & Kane (2004), Cattell (1971), Rescorla & Wagner (1972)
**Exploration:** quick
**Status:** revised (R1-02 CAPS remapped from relationalComplexity to associativeReach)

## D5: CBR wiring — recordOutcome overload with learning rate override

**Choice:** Add a default method overload on `CbrRecordStore`:
```java
default void recordOutcome(String caseId, CbrOutcome outcome,
                            String tenantId, Double learningRateOverride) {
    recordOutcome(caseId, outcome, tenantId);
}
```
Store implementations that support the override use `learningRateOverride != null ? learningRateOverride : schema.learningRate()`. BehavioralSynthesisPhase computes `effectiveLR = schema.learningRate * capacity.workingMemorySpanOrDefault()` and passes it.
**Depends on:** D4 (CBR uses workingMemorySpan)
**Alternatives:**
- Field on CbrOutcome — pollutes tier 1 memory type with cognitive-layer concerns; CbrOutcome is actually a 5-field record (Outcome, successRate, detail, observedAt, retrievalId), not single-arg
- Decorator on CbrRecordStore — introduces cognitive-index dependency into memory layer
- Per-agent schemas — caseType × agent proliferation
**Rationale:** Default method is backwards-compatible — existing implementations inherit the no-op overload. The learning rate computation stays in the cognitive layer where capacity information lives. CbrOutcome (tier 1) stays clean.
**Trade-offs:** Implementations opt in to capacity modulation by overriding the 4-arg method. Initially only InMemory and Qdrant need it.
**Sources:** CbrRecordStore SPI, CbrOutcome.java (5-field record), BehavioralSynthesisPhase
**Exploration:** quick
**Status:** revised (R1-04 factual fix, R1-05 simpler alternative adopted, R1-10 tier 1 concern addressed)

## D6: CAPS and graduation wiring

**Choice:** Two site-specific wiring changes:
1. **CapsWeightUpdater** — introduce `WeightUpdateContext` record to wrap the growing parameter list (currently 6 params, adding capacityMultiplier makes 7). BehavioralSynthesisPhase resolves associativeReach from CognitiveDefaultsRegistry and sets it on the context. Multiplies `baseAlpha` (not `salienceMultiplier` — salience is attention, not learning capacity). CapsEngine.updateWeights() SPI method takes the context record. All 6 implementations (SqliteCapsEngine, InMemoryCapsEngine×2, StubCapsEngine, CapturingCapsEngine, EmotionAwareStubCapsEngine) updated.
2. **DefaultGraduationScorer** — multiply the graduation *score* by capacity, not the *threshold*. `minCorroboration` stays integer; capacity modulates the continuous score after corroboration passes. This avoids integer cliff effects (at capacity 0.55, `3/0.55=5.45` → ceiled to 6, a +100% jump). GraduationContext unchanged (tier 1 type stays clean). Scorer accesses capacity via constructor-injected CognitiveDefaultsRegistry, resolving per-tenant.
**Depends on:** D4 (CAPS uses associativeReach, graduation uses relationalComplexity)
**Alternatives:**
- Bare parameter addition on CapsEngine.updateWeights() — 7 positional parameters on an SPI method is too many
- GraduationContext field — pollutes tier 1 memory-api type with cognitive concerns
- Threshold modulation for graduation — integer discretization creates disproportionate step jumps
**Rationale:** WeightUpdateContext gives a stable SPI surface for future extensions. Score modulation is smooth and avoids modifying tier 1 types.
**Trade-offs:** WeightUpdateContext adds a new type in caps-api. Scorer gains a CognitiveDefaultsRegistry dependency — acceptable for a @DefaultBean in mindmap-intelligence which already has cognitive-index on its classpath.
**Sources:** CapsEngine.java (6+ implementations), DefaultGraduationScorer:33-41, BehavioralSynthesisPhase, ExperienceConsolidationPhase
**Exploration:** quick
**Status:** revised (R1-03 blast radius, R1-06 score vs threshold, R1-10 tier 1 concern)

## D7: Static capacity, not dynamic depletion

**Choice:** Learning rate modulation uses trait-level capacity from `CognitiveDefaults.capacityConfig()`, not state-level effective capacity that composes with `CognitiveResourcePool.currentDepletion()`.
**Depends on:** D2 (formula)
**Alternatives:**
- Compose: `effectiveLR = baseLR * capacity * (1 - depletion)` — more realistic but conflates two distinct mechanisms. Depletion already modulates regulation and search budget; double-applying it to learning would over-penalize depleted agents.
- Dynamic only (depletion, no capacity) — ignores structural differences between agents
**Rationale:** Learning effects persist beyond the current cognitive state. An agent with high structural capacity but temporary depletion should still have structurally faster learning — the quality of what it *can* learn is a trait, not a state. Depletion already affects *what gets processed* (via search budget) and *how well it's regulated* (via emotion regulation). Adding depletion to learning rate would triple-count it.
**Trade-offs:** An agent at high depletion learns at full trait-rate, which could feel unrealistic in extreme scenarios. Acceptable because: (a) depletion affects input quality (search budget narrowing), so learning naturally slows via reduced input, and (b) the capacity range [0.55, 0.95] means the trait effect is modest.
**Sources:** CognitiveResourcePool SPI, EmotionRegulationTickParticipant:105-108, SearchBudgetTickParticipant:142-148
**Exploration:** quick (implicit decision surfaced by R1-09, explicitly captured)
**Status:** captured

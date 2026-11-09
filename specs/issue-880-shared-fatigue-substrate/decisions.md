## D1: Extensibility scope

**Choice:** Extensible SPI — design an open contributor model so future cognitive effort sources can contribute to the shared pool without modifying the substrate itself. Two initial contributors: search intensity and emotion regulation.
**Alternatives:**
- Two-source only — hardcode the two contributors, simpler now but refactor later
- Three-source — add CognitiveLoadEstimator as a third contributor immediately
**Rationale:** Hockey's compensatory control theory models ALL effortful cognitive activity drawing from a unified pool. The SPI should reflect this — any cognitive effort source should be able to contribute.
**Trade-offs:** Slightly more upfront design for the SPI contract; but the SPI is small (one method: contribute effort).
**Sources:** Hockey (1997), Baumeister (1998), issue #880, CognitiveLoadEstimator in EmotionRegulationTickParticipant
**Exploration:** quick
**Status:** captured

## D2: Architecture — Shared Pool SPI

**Choice:** `CognitiveResourcePool` SPI in `cognition-api` with `CognitiveResourcePoolConfig` in `cognitive-api`. Sources contribute effort during tick; consumers read depletion level and apply their own effects.
**Alternatives:**
- Decorator Bridge — keep both implementations, cross-pollinate percentages. Minimal change but arbitrary coupling and no extensibility.
- Merged Internal Bean — one shared class in cognition, both participants inject it. Simpler but not extensible.
**Rationale:** Clean separation: pool owns accumulation/recovery/depletion; sources own contribution rates; consumers own sensitivity to depletion. Aligns with Hockey's unified resource theory. FatigueConfig splits (pool params → shared config, effect params stay search-budget-specific). RegulationFatigueTracker replaced by pool reads.
**Trade-offs:** More types than the merged bean, but each type has clear responsibility. Decorator bridge would be less disruptive but perpetuates the theoretical inconsistency.
**Sources:** SearchBudgetTickParticipant.java, RegulationFatigueTracker.java, FatigueConfig.java, EmotionRegulationTickParticipant.java, Hockey (1997)
**Exploration:** quick
**Status:** captured

## D3: Accumulation model

**Choice:** Logarithmic accumulation — `log(1 + accumulator) / log(1 + maxEffort)`. Diminishing returns: early effort depletes quickly, saturation is gradual.
**Alternatives:**
- Linear — simpler but allows sudden jumps; doesn't match psychological intuition
- Sigmoid — resistance-then-collapse-then-saturation; more complex without clear empirical grounding
**Rationale:** Matches existing search fatigue math. Diminishing returns model is psychologically intuitive — the first hour of cognitive effort costs more capacity than the tenth.
**Trade-offs:** Logarithmic makes the pool harder to fully deplete, which means extreme exhaustion requires sustained multi-source effort. This is a feature, not a bug.
**Sources:** SearchBudgetTickParticipant.java:147-149
**Exploration:** quick
**Status:** captured

## D4: Pool config placement

**Choice:** `CognitiveResourcePoolConfig` as a top-level field on `CognitiveDefaults`, alongside `searchBudgetConfig` and `habituationConfig`. Personality-derived in `CognitiveDerivationEngine`.
**Alternatives:**
- Nested in SearchBudgetConfig — simpler refactor but conceptually wrong (pool isn't search-specific)
- On CognitionConfig — wrong level (CognitionConfig is feature toggles, not parameter tuning)
**Rationale:** The pool is a cross-cutting cognitive resource, not owned by any single consumer. Top-level placement on CognitiveDefaults is consistent with other personality-derived config records.
**Trade-offs:** FatigueConfig field on SearchBudgetConfig becomes nullable/removed; existing cognitive profile YAMLs need migration.
**Depends on:** D2 (pool architecture)
**Sources:** CognitiveDefaults record, CognitiveDerivationEngine.java:818-826
**Exploration:** quick
**Status:** captured

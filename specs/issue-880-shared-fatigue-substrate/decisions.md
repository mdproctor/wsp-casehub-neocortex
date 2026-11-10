## D1: Extensibility scope

**Choice:** Extensible SPI — design an open contributor model so future cognitive effort sources can contribute to the shared pool without modifying the substrate itself. Two initial contributors: search intensity and emotion regulation.
**Alternatives:**
- Two-source only — hardcode the two contributors, simpler now but refactor later
- Three-source — add CognitiveLoadEstimator as a third contributor immediately
**Rationale:** Hockey's (1997) compensatory control theory models effortful cognitive activity competing for limited processing capacity, with strategic reallocation under load. The pool tracks total cognitive load; each consumer reads depletion and makes its own reallocation decisions — preserving Hockey's strategic reallocation insight.
**Trade-offs:** Slightly more upfront design for the SPI contract; but the SPI is small (one method: contribute effort).
**Sources:** Hockey (1997), issue #880, CognitiveLoadEstimator in EmotionRegulationTickParticipant
**Exploration:** quick
**Status:** captured

## D2: Architecture — Shared Pool SPI

**Choice:** `CognitiveResourcePool` SPI in `cognition-api` with `CognitiveResourcePoolConfig` in `cognitive-api`. Sources contribute effort during tick; consumers read depletion level and apply their own effects.
**Alternatives:**
- Decorator Bridge — keep both implementations, cross-pollinate percentages. Minimal change but arbitrary coupling and no extensibility.
- Merged Internal Bean — one shared class in cognition, both participants inject it. Simpler but not extensible.
**Rationale:** Clean separation: pool owns accumulation/recovery/depletion; sources own contribution rates; consumers own sensitivity to depletion. Aligns with Hockey's compensatory control. FatigueConfig splits (pool params → shared config, effect params stay search-budget-specific). RegulationFatigueTracker replaced by pool reads.
**Trade-offs:** More types than the merged bean, but each type has clear responsibility. Decorator bridge would be less disruptive but perpetuates the theoretical inconsistency.
**Sources:** SearchBudgetTickParticipant.java, RegulationFatigueTracker.java, FatigueConfig.java, EmotionRegulationTickParticipant.java, Hockey (1997)
**Exploration:** quick
**Status:** captured

## D3: Accumulation model

**Choice:** Logarithmic accumulation — `log(1 + accumulator) / log(1 + maxEffort)`. Diminishing returns: early effort depletes quickly, saturation is gradual.
**Alternatives:**
- Linear — simpler but allows sudden jumps; doesn't match psychological intuition
- Sigmoid — resistance-then-collapse-then-saturation; more complex without clear empirical grounding
**Rationale:** Matches existing search fatigue math. Logarithmic scaling makes the pool easy to partially deplete but hard to fully deplete — at 0.8 depletion, regulation alpha is already at 20% of baseline. Full collapse isn't needed for strong behavioral effects.
**Trade-offs:** Full exhaustion (depletion = 1.0) requires sustained multi-source effort. This means Bosse's "willpower collapse" state is achievable but requires heavier total load than under the old linear model — which is more realistic for a shared resource.
**Sources:** SearchBudgetTickParticipant.java:147-149, Kahneman (1973) capacity theory
**Exploration:** quick
**Status:** captured

## D4: Pool config placement

**Choice:** `CognitiveResourcePoolConfig` as a top-level field on `CognitiveDefaults`, alongside `searchBudgetConfig` and `habituationConfig`. Personality-derived in `CognitiveDerivationEngine`.
**Alternatives:**
- Nested in SearchBudgetConfig — simpler refactor but conceptually wrong (pool isn't search-specific)
- On CognitionConfig — wrong level (CognitionConfig is feature toggles, not parameter tuning)
**Rationale:** The pool is a cross-cutting cognitive resource, not owned by any single consumer. Top-level placement on CognitiveDefaults is consistent with other personality-derived config records.
**Trade-offs:** Adds field #22 to CognitiveDefaults. The record is large — grouping into themed sub-records is a valid future improvement but out of scope here.
**Depends on:** D2 (pool architecture)
**Sources:** CognitiveDefaults record, CognitiveDerivationEngine.java:818-826
**Exploration:** quick
**Status:** captured

## D5: FatigueConfig handling — REVISED

**Choice:** Rename `SearchFatigueEffects` to `SearchFatigueEffects`. Remove pool parameters (maxTicks, recoveryRate). Retains only the 4 search-budget-specific per-parameter effects. `SearchBudgetConfig.fatigueEffects()` returns `SearchFatigueEffects`.
**Alternatives:**
- Keep FatigueConfig name — less churn but known-misleading name is technical debt
- Absorb into SearchBudgetConfig — flattens nesting but SearchBudgetConfig already has 14 params
**Rationale:** Pre-release design philosophy: clean API, no technical debt. A type named "config" that contains only effect parameters misleads every future reader. The rename is mechanical (find-references + rename refactoring).
**Trade-offs:** All references to FatigueConfig update. This is a cost worth paying.
**Depends on:** D4 (pool config placement)
**Sources:** FatigueConfig.java, SearchBudgetConfig.java, R1-05 decision review finding
**Exploration:** quick
**Status:** revised (from review R1-05)

## D6: Recovery model

**Choice:** Net-contribution per tick. Each tick, sources call `recordEffort(amount)` when active or `recordRecovery(rate)` when idle. Pool adds effort contributions and subtracts recovery amounts. Recovery only occurs when a source explicitly signals idleness — the pool itself doesn't auto-recover.
**Alternatives:**
- Auto-recovery per tick minus contributions — simpler but recovery happens even under sustained dual-source load, which is unrealistic
- All-idle-required recovery — only recovers when ALL sources are idle. Too restrictive: an agent doing light regulation shouldn't block search fatigue recovery entirely
**Rationale:** The per-source recovery model matches real cognitive dynamics: resting from one effortful activity provides partial recovery even if another continues. The net effect determines whether the pool depletes or recovers on a given tick.
**Trade-offs:** A single high-intensity source CAN prevent net recovery if its effort exceeds other sources' recovery contributions. This is desirable — sustained extreme intensity should deplete even while other systems are idle.
**Depends on:** D2 (pool architecture), D3 (accumulation model)
**Sources:** R1-08 decision review finding, Hockey (1997) compensatory control
**Exploration:** quick (surfaced by decision review)
**Status:** captured

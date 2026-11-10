# HANDOFF — casehub-neocortex

## Last Session

Completed #890 (Intelligence capacity: learning rate modulation via Cattell's Investment Theory). Implemented capacity modulation at 6 learning sites — each mapped to a single cognitive capacity dimension:

- **CapsWeightUpdater** — `baseAlpha *= associativeReach` (Mednick 1962). Introduced `WeightUpdateContext` record in caps-api to replace the 6-param `updateWeights()` SPI.
- **CbrRecordLifecycle** — 4-arg `recordOutcome` with `learningRateOverride` (default method). `DelegatingCbrRecordStore` forwards. `InMemoryCbrRecordStore` overrides. BehavioralSynthesisPhase passes `schemaLR * workingMemorySpan` (Engle & Kane 2004).
- **DefaultGraduationScorer** — `score *= relationalComplexity` (Halford 1998). `GraduationContext` gains nullable `agentId` field. Formative memories exempt.
- **DriveAdaptationPhase** — `effectiveLR *= associativeReach`, applied unconditionally after conditional satisfaction modulation.
- **StrategyLearningOrchestrator** — `maxDimensionDelta *= workingMemorySpan` (ceiling). Both the delta clamp and LLM system prompt use the effective value.
- **PersonalityEvolutionOrchestrator** — `l2Ceiling *= relationalComplexity` (ceiling).

Landed on main as `add80816`, docs promoted as `676db1b0`. Blog written: `2026-11-10-mdp02-smarter-agents-learn-faster.md`.

## Follow-Up Issues Created

| # | Title | Scale | Complexity | Status |
|---|-------|-------|------------|--------|
| #916 | QdrantCbrRecordStore 4-arg recordOutcome | XS | Low | Open — queue |
| #917 | Fix cognition test compilation from #880 | XS | Low | Open — queue |
| #918 | Capacity modulation observability | S | Med | Open — queue |

## Pre-Existing Issue

cognition module test compilation fails — `CognitiveResourcePool` SPI moved in #880 but test imports not updated. Tracked in #917. Production code compiles and works. Does not block any other work.

## Immediate Next Step

`work continue` — next in queue is #891 (Intelligence capacity: convergence ceiling). Same domain, continues the capacity series.

## Remaining Queue (Epic #841)

| # | Title | Scale | Complexity | Status |
|---|-------|-------|------------|--------|
| #891 | Intelligence capacity: convergence ceiling | S | Med | Next |
| #892 | Intelligence capacity: appraisal frustration pathway | S | Med | Open |
| #894 | Eval pipeline coherence trace chain validation | M | High | Open |
| #905 | Run and calibrate exploration + capacity eval suite | L | High | Open |
| #916 | QdrantCbrRecordStore 4-arg recordOutcome | XS | Low | Open |
| #917 | Fix cognition test compilation from #880 | XS | Low | Open |
| #918 | Capacity modulation observability | S | Med | Open |

## Key Files Modified This Session

- `caps-api/.../WeightUpdateContext.java` — new record (6 fields incl. capacityMultiplier)
- `caps-api/.../CapsEngine.java` — `updateWeights(state, context)` replaces 6-param signature
- `caps-engine/.../CapsWeightUpdater.java` — `baseAlpha *= context.capacityMultiplier()` before precision division
- `memory-api/.../CbrRecordLifecycle.java` — 4-arg `recordOutcome` default method
- `memory-api/.../DelegatingCbrRecordStore.java` — forwards 4-arg call
- `memory-api/.../GraduationContext.java` — gains `String agentId` (4th field, nullable)
- `memory-cbr-inmem/.../InMemoryCbrRecordStore.java` — 4-arg override with learningRateOverride
- `mindmap-intelligence/.../DefaultGraduationScorer.java` — CognitiveDefaultsRegistry injection, `score *= relationalComplexity`
- `mindmap-intelligence/.../ExperienceConsolidationPhase.java` — passes agentId in GraduationContext
- `mindmap-intelligence/.../BehavioralSynthesisPhase.java` — passes capacity to WeightUpdateContext and 4-arg recordOutcome
- `cognition/.../DriveAdaptationPhase.java` — `effectiveLR *= associativeReach`
- `cognition/.../PersonalityEvolutionOrchestrator.java` — `effectiveCeiling = l2Ceiling * relationalComplexity`
- `cognition/.../StrategyLearningOrchestrator.java` — `effectiveMaxDelta = maxDelta * workingMemorySpan`, `systemPrompt(agentId)`
- 18 new tests: 5 CAPS alpha, 2 CBR contract, 6 graduation scorer, 5 integration

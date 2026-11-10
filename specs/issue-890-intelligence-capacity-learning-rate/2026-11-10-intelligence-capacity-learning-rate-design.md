# Intelligence Capacity: Learning Rate Modulation via Cattell's Investment Theory

**Issue:** casehubio/neocortex#890
**Epic:** casehubio/neocortex#841
**Depends on:** #840 (intelligence capacity layer)

## 1. Problem

CognitiveCapacityConfig (from #840) provides three dimensions of cognitive capacity — relationalComplexity, associativeReach, workingMemorySpan — but they only bound search budget parameters. The system has 6 learning/adaptation sites with static rates unaffected by capacity. Cattell's (1971) Investment Theory implies fluid intelligence (Gf) should modulate the speed of crystallized intelligence (Gc) acquisition: agents with higher capacity should learn faster across all subsystems.

## 2. Approach

Linear multiplier: `effectiveLR = baseLR * capacityDimension`. Each site maps to a single capacity dimension based on cognitive substrate relevance. Two exceptions use ceiling pattern where the existing parameter is already a ceiling.

Uses trait-level capacity (`CognitiveDefaults.capacityConfig()`), not dynamic depletion. Depletion already affects input quality (search budget) and regulation (emotion regulation alpha). Learning rate is a structural trait — the quality of what an agent *can* learn persists beyond momentary cognitive state.

## 3. Dimension-to-Site Mapping

| Site | Dimension | Formula | Literature |
|------|-----------|---------|------------|
| CapsWeightUpdater | associativeReach | `baseAlpha *= associativeReach` | Rescorla-Wagner associative learning (1972), Mednick (1962) |
| CbrRecordStore.recordOutcome | workingMemorySpan | `effectiveLR = schemaLR * wmSpan` | Multi-factor outcome evaluation, Engle & Kane (2004) |
| DriveAdaptationPhase | associativeReach | `effectiveLR *= associativeReach` | Drive-outcome connection breadth, Mednick (1962) |
| StrategyLearningOrchestrator | workingMemorySpan | `maxDelta *= wmSpan` (ceiling) | Multi-dim strategy tracking, Engle & Kane (2004) |
| DefaultGraduationScorer | relationalComplexity | `score *= relationalComplexity` | Abstracting from experience, Halford (1998) |
| PersonalityEvolutionOrchestrator | relationalComplexity | `l2Ceiling *= relationalComplexity` (ceiling) | Self-model complexity, Halford (1998) |

Dimension balance: 2× associativeReach, 2× workingMemorySpan, 2× relationalComplexity.

Capacity values are in [0.55, 0.95] after `compressCapacity()` derivation in CDE (`0.55 + raw * 0.4`). The `*OrDefault()` accessors return 1.0 when null (uncapped).

## 4. Site-by-Site Changes

### 4.1 CapsWeightUpdater (caps-engine)

**Current:** `effectiveAlpha = baseAlpha / cw.precision()` where `baseAlpha = clamp(salienceMultiplier * config.salienceAlphaScaling(), alphaMin, alphaMax)`.

**Change:** Introduce `WeightUpdateContext` record in caps-api to replace the 7-parameter `updateWeights()` signature on CapsEngine SPI. Add `double capacityMultiplier` (defaults to 1.0). Apply: `baseAlpha *= context.capacityMultiplier()` before precision division.

```java
// caps-api — new type
/**
 * Context for CAPS weight updates. Capacity multiplier implements Cattell's (1971)
 * Investment Theory: associativeReach (Mednick 1962) modulates the Rescorla-Wagner
 * (1972) base alpha — higher associative capacity strengthens stimulus-response
 * learning speed.
 */
public record WeightUpdateContext(
    Map<String, Double> inputActivations,
    double outcomeIntensity,
    double outcomeValence,
    double salienceMultiplier,
    double reinforcementSchedule,
    double capacityMultiplier   // from CognitiveCapacityConfig.associativeReachOrDefault()
) {
    public WeightUpdateContext {
        if (capacityMultiplier < 0.0 || capacityMultiplier > 1.0)
            throw new IllegalArgumentException("capacityMultiplier must be in [0,1]");
    }
}
```

**Blast radius:** CapsEngine.updateWeights() SPI, SqliteCapsEngine, InMemoryCapsEngine (×2 in caps-testing and memory-seeding), StubCapsEngine, CapturingCapsEngine, EmotionAwareStubCapsEngine — 6 implementations total.

**Caller:** BehavioralSynthesisPhase resolves `CognitiveDefaultsRegistry.forAgentOrDefaults(agentId).capacityConfig().associativeReachOrDefault()`.

### 4.2 CbrRecordStore.recordOutcome (memory-api)

**Current:** `recordOutcome(String caseId, CbrOutcome outcome, String tenantId)` — store resolves schema's learningRate, calls `CbrOutcome.adjustConfidence(old, successRate, learningRate)`.

**Change:** Add default method overload on CbrRecordStore:

```java
/**
 * Records an outcome with a capacity-modulated learning rate. Per Cattell's (1971)
 * Investment Theory, workingMemorySpan (Engle & Kane 2004) modulates the EMA
 * learning rate — higher working memory enables better evaluation of multi-factor
 * outcomes, accelerating confidence convergence.
 *
 * @param learningRateOverride when non-null, replaces the schema's learningRate
 */
default void recordOutcome(String caseId, CbrOutcome outcome,
                            String tenantId, Double learningRateOverride) {
    recordOutcome(caseId, outcome, tenantId);
}
```

Store implementations override to use `learningRateOverride != null ? learningRateOverride : schema.learningRate()`. Backwards-compatible via default method.

**Caller:** BehavioralSynthesisPhase computes `effectiveLR = schemaLR * capacity.workingMemorySpanOrDefault()`.

### 4.3 DriveAdaptationPhase (cognition)

**Current:** `effectiveLR = config.learningRate() * (1 - avgSatisfaction)` — already modulated by need satisfaction.

**Change:** Chain capacity modulation: `effectiveLR = config.learningRate() * (1 - avgSatisfaction) * capacity.associativeReachOrDefault()`.

```java
/**
 * Capacity modulation per Cattell's (1971) Investment Theory:
 * associativeReach (Mednick 1962) scales the drive adaptation rate —
 * broader associative networks enable faster drive-outcome learning.
 * Composes with existing satisfaction modulation (§D2).
 */
double capacityFactor = capacityConfig.associativeReachOrDefault();
effectiveLR *= capacityFactor;
```

**Wiring:** DriveAdaptationPhase already runs in tick context. Resolve capacity from `CognitiveDefaultsRegistry.forAgentOrDefaults(agentId)`.

### 4.4 StrategyLearningOrchestrator (cognition)

**Current:** `maxDimensionDelta` config clamp (default 0.2) limits how much strategy dimensions change per reflection.

**Change:** Ceiling pattern — `effectiveMaxDelta = config.maxDimensionDelta() * capacity.workingMemorySpanOrDefault()`.

```java
/**
 * Capacity ceiling per Cattell's (1971) Investment Theory:
 * workingMemorySpan (Engle & Kane 2004) scales the strategy adaptation
 * ceiling — higher working memory enables tracking larger multi-dimensional
 * strategy shifts without confusion (§D2 ceiling exception).
 */
double effectiveMaxDelta = config.maxDimensionDelta()
    * capacityConfig.workingMemorySpanOrDefault();
```

**Wiring:** StrategyLearningOrchestrator runs in tick context. Resolve capacity from CognitiveDefaultsRegistry.

### 4.5 DefaultGraduationScorer (mindmap-intelligence)

**Current:** Returns `memory.confidence().value()` (or 0.5 default) after corroboration gate.

**Change:** Multiply the continuous graduation score by `relationalComplexityOrDefault()`. The integer `minCorroboration` threshold stays unchanged — capacity modulates the score, not the gate.

```java
/**
 * Capacity modulation per Cattell's (1971) Investment Theory:
 * relationalComplexity (Halford 1998) scales the graduation score —
 * higher relational complexity enables better abstraction from experience,
 * producing higher-quality knowledge representations (§D6 score vs threshold).
 */
double rawScore = confidence != null ? confidence.value() : 0.5;
double capacityFactor = capacityConfig.relationalComplexityOrDefault();
return rawScore * capacityFactor;
```

**Wiring:** Constructor-inject CognitiveDefaultsRegistry. DefaultGraduationScorer is a @DefaultBean in mindmap-intelligence, which already has cognitive-index on its classpath. Resolve per-tenant capacity.

### 4.6 PersonalityEvolutionOrchestrator (cognition)

**Current:** `l2Ceiling` (default 0.15) — drift magnitude threshold for halting personality evolution.

**Change:** Ceiling pattern — `effectiveCeiling = config.l2Ceiling() * capacity.relationalComplexityOrDefault()`.

```java
/**
 * Capacity ceiling per Cattell's (1971) Investment Theory:
 * relationalComplexity (Halford 1998) scales the personality drift ceiling —
 * higher relational complexity supports more complex self-models, tolerating
 * larger personality adjustments before halting (§D2 ceiling exception).
 */
double effectiveCeiling = config.l2Ceiling()
    * capacityConfig.relationalComplexityOrDefault();
```

**Wiring:** PersonalityEvolutionOrchestrator runs in tick context. Resolve capacity from CognitiveDefaultsRegistry.

## 5. Documentation Requirements

Every modulation site gets Javadoc citing:
1. Cattell (1971) — Investment Theory justification for capacity → learning rate
2. The specific dimension's literature source (Halford/Mednick/Engle & Kane)
3. The formula and its design decision reference (§D2, §D4, §D6 as applicable)
4. Why this dimension maps to this site (one sentence)

## 6. What This Does NOT Change

- **CognitiveCapacityConfig** — no new fields, no API changes
- **CognitiveDerivationEngine** — no derivation changes
- **CbrOutcome** — stays a 5-field record, no modification
- **GraduationContext** — stays unchanged (tier 1 type preserved)
- **SearchBudgetTickParticipant** — already uses capacity ceilings, unaffected
- **EmotionRegulationTickParticipant** — uses depletion, unaffected
- **CognitiveResourcePool** — depletion is orthogonal to trait capacity (§D7)

## 7. Testing Strategy

Each site needs:
1. **Unit test:** Verify `effectiveLR = baseLR * dimension` for multiplier sites, `effectiveCeiling = baseCeiling * dimension` for ceiling sites
2. **Boundary test:** Capacity at 0.0, 0.55, 0.95, 1.0, and null (1.0 via `*OrDefault()`)
3. **Integration test:** CognitiveDefaults with known capacity → verify learning rate at the site reflects the capacity

For CapsWeightUpdater: verify `WeightUpdateContext` carries capacity through to alpha computation.
For CbrRecordStore: verify 4-arg `recordOutcome` overload uses the override, 3-arg ignores it.

## References

- Cattell, R.B. (1971). *Abilities: Their Structure, Growth, and Action.* — Investment Theory
- Halford, G.S. (1998). *Processing capacity defined by relational complexity.* — relationalComplexity dimension
- Mednick, S.A. (1962). *The associative basis of the creative process.* — associativeReach dimension
- Engle, R.W. & Kane, M.J. (2004). *Executive attention, working memory capacity.* — workingMemorySpan dimension
- Rescorla, R.A. & Wagner, A.R. (1972). *A theory of Pavlovian conditioning.* — CapsWeightUpdater associative learning
- `cognitive-api/.../CognitiveCapacityConfig.java` — capacity record definition
- `cognitive-index/.../CognitiveDerivationEngine.java:270-299` — capacity derivation and compression
- `caps-engine/.../CapsWeightUpdater.java:48-66` — Rescorla-Wagner alpha computation
- `memory-api/.../CbrOutcome.java:33-38` — EMA adjustConfidence
- `cognition/.../DriveAdaptationPhase.java:220-248` — drive intensity learning rate
- `cognition/.../StrategyLearningOrchestrator.java:554-588` — maxDimensionDelta clamp
- `mindmap-intelligence/.../DefaultGraduationScorer.java:33-41` — graduation scoring
- `cognition/.../PersonalityEvolutionOrchestrator.java:103-110` — l2Ceiling drift check
- Issue #840 — intelligence capacity layer (prerequisite)
- Issue #890 — this issue

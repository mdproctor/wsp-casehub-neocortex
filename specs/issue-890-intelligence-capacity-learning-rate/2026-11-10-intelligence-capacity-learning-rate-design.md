# Intelligence Capacity: Learning Rate Modulation via Cattell's Investment Theory

**Issue:** casehubio/neocortex#890
**Epic:** casehubio/neocortex#841
**Depends on:** #840 (intelligence capacity layer)

## 1. Problem

CognitiveCapacityConfig (from #840) provides three dimensions of cognitive capacity — relationalComplexity, associativeReach, workingMemorySpan — but they only bound search budget parameters. The system has 6 learning/adaptation sites with static rates unaffected by capacity. Cattell's (1971) Investment Theory implies fluid intelligence (Gf) should modulate the speed of crystallized intelligence (Gc) acquisition: agents with higher capacity should learn faster across all subsystems.

## 2. Approach

Linear multiplier: `effectiveLR = baseLR * capacityDimension`. Each site maps to a single capacity dimension based on cognitive substrate relevance. Two exceptions use ceiling pattern where the existing parameter is already a ceiling.

Uses trait-level capacity (`CognitiveDefaults.capacityConfig()`), not dynamic depletion. Depletion already affects input quality (search budget) and regulation (emotion regulation alpha). Learning rate is a structural trait — the quality of what an agent *can* learn persists beyond momentary cognitive state. Note: #880 (shared fatigue substrate) introduces capacity×fatigue interaction at the search budget level. Future work may extend fatigue interaction to learning rates, but the current design intentionally separates trait capacity from transient state.

### 2.1 Cross-Site Interaction: Graduation × CAPS

Graduation score modulation (§4.5, relationalComplexity) and CAPS alpha modulation (§4.1, associativeReach) affect different stages of the same pipeline: graduation scores flow into BehavioralSynthesisPhase as `outcomeIntensity` (β), while CAPS alpha is modulated separately. For an agent uniformly low across dimensions (e.g., 0.55), the effective weight update contribution scales as `~capacity_rc * capacity_ar` — approximately 0.30 for the worst case. This is NOT double-counting: the two dimensions measure independent cognitive substrates (relational depth vs associative breadth), and each legitimately affects its stage. An agent with high associativeReach but low relationalComplexity would have high alpha but low graduation scores — a theoretically coherent profile where the agent learns associations quickly but produces lower-quality abstractions.

## 3. Dimension-to-Site Mapping

| Site | Dimension | Formula | Literature |
|------|-----------|---------|------------|
| CapsWeightUpdater | associativeReach | `baseAlpha *= associativeReach` | Rescorla-Wagner associative learning (1972), Mednick (1962) |
| CbrRecordLifecycle.recordOutcome | workingMemorySpan | `effectiveLR = schemaLR * wmSpan` | Multi-factor outcome evaluation, Engle & Kane (2004) |
| DriveAdaptationPhase | associativeReach | `effectiveLR *= associativeReach` | Drive-outcome connection breadth, Mednick (1962) |
| StrategyLearningOrchestrator | workingMemorySpan | `maxDelta *= wmSpan` (ceiling) | Multi-dim strategy tracking, Engle & Kane (2004) |
| DefaultGraduationScorer | relationalComplexity | `score *= relationalComplexity` | Abstracting from experience, Halford (1998) |
| PersonalityEvolutionOrchestrator | relationalComplexity | `l2Ceiling *= relationalComplexity` (ceiling) | Self-model complexity, Halford (1998) |

Dimension balance: 2× associativeReach, 2× workingMemorySpan, 2× relationalComplexity.

Capacity values are in [0.55, 0.95] after `compressCapacity()` derivation in CDE (`0.55 + raw * 0.4`). The `*OrDefault()` accessors return 1.0 when null (uncapped).

## 4. Site-by-Site Changes

### 4.1 CapsWeightUpdater (caps-engine)

**Current:** `effectiveAlpha = baseAlpha / cw.precision()` where `baseAlpha = clamp(salienceMultiplier * config.salienceAlphaScaling(), alphaMin, alphaMax)`. CapsEngine.updateWeights() SPI has 6 parameters: `(AgentCapsState state, Map<String, Double> inputActivations, double outcomeIntensity, double outcomeValence, double salienceMultiplier, String reinforcementSchedule)`.

**Change:** Introduce `WeightUpdateContext` record in caps-api to replace the 6-parameter `updateWeights()` signature on CapsEngine SPI. Add `double capacityMultiplier` (defaults to 1.0). Apply: `baseAlpha *= context.capacityMultiplier()` before precision division.

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
    String reinforcementSchedule,
    double capacityMultiplier   // from CognitiveCapacityConfig.associativeReachOrDefault()
) {
    public WeightUpdateContext {
        Objects.requireNonNull(reinforcementSchedule);
        if (capacityMultiplier < 0.0 || capacityMultiplier > 1.0)
            throw new IllegalArgumentException("capacityMultiplier must be in [0,1]");
    }
}
```

**Blast radius:** CapsEngine.updateWeights() SPI changes from 6 params to `(AgentCapsState, WeightUpdateContext)`. All 6 implementations updated: SqliteCapsEngine, InMemoryCapsEngine (caps-testing), InMemoryCapsEngine (memory-seeding), StubCapsEngine, CapturingCapsEngine, EmotionAwareStubCapsEngine.

**Caller:** BehavioralSynthesisPhase resolves `CognitiveDefaultsRegistry.forAgentOrDefaults(agentId).capacityConfig().associativeReachOrDefault()`, constructs `WeightUpdateContext`.

### 4.2 CbrRecordLifecycle.recordOutcome (memory-api)

**Current:** `recordOutcome(String caseId, CbrOutcome outcome, String tenantId)` on `CbrRecordLifecycle` — store resolves schema's learningRate, calls `CbrOutcome.adjustConfidence(old, successRate, learningRate)`.

**Change:** Add default method overload on `CbrRecordLifecycle` (where the 3-arg version is defined):

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

**Decorator chain forwarding:** `DelegatingCbrRecordStore` overrides the 4-arg method to forward to its delegate. All decorators extending `DelegatingCbrRecordStore` (ScopeDecay, Diversity, TrustWeighted, TrendEnrichment, OutcomeWeighting, Reranking, ErasureNotification, SupersessionNotification, OutcomeNotification, Tracking) inherit the forwarding automatically. Only leaf store implementations (InMemory, Qdrant) override to use the `learningRateOverride`.

**Caller:** BehavioralSynthesisPhase computes `effectiveLR = schemaLR * capacity.workingMemorySpanOrDefault()`.

### 4.3 DriveAdaptationPhase (cognition)

**Current:** `effectiveLR = config.learningRate()`, conditionally modulated by need satisfaction when tierMapping contains the drive type and currentSatisfaction is non-empty: `effectiveLR = config.learningRate() * (1 - avgSatisfaction)`.

**Change:** Apply capacity modulation unconditionally after the conditional satisfaction modulation:

```java
/**
 * Capacity modulation per Cattell's (1971) Investment Theory:
 * associativeReach (Mednick 1962) scales the drive adaptation rate —
 * broader associative networks enable faster drive-outcome learning.
 * Applied unconditionally; composes with optional satisfaction modulation.
 */
double capacityFactor = capacityConfig.associativeReachOrDefault();
effectiveLR *= capacityFactor;
```

**Wiring:** DriveAdaptationPhase already runs in tick context. Add `CognitiveDefaultsRegistry` dependency, resolve capacity from `registry.forAgentOrDefaults(agentId)`.

### 4.4 StrategyLearningOrchestrator (cognition)

**Current:** `maxDimensionDelta` config clamp (default 0.2) limits how much strategy dimensions change per reflection. The LLM system prompt template references this value: `"Deltas: in [-%s, +%s]"` formatted with `config.maxDimensionDelta()`.

**Change:** Ceiling pattern — `effectiveMaxDelta = config.maxDimensionDelta() * capacity.workingMemorySpanOrDefault()`. Both the clamp in `applyReflectionResult()` and the LLM prompt in `systemPrompt()` use the capacity-adjusted value.

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

**Wiring:** Add `CognitiveDefaultsRegistry` constructor dependency. `systemPrompt()` becomes `systemPrompt(String agentId)` — resolves capacity and formats the LLM-facing delta range with the effective value. `applyReflectionResult()` already receives agentId — resolve capacity there for the clamp.

### 4.5 DefaultGraduationScorer (mindmap-intelligence)

**Current:** Returns `memory.confidence().value()` (or 0.5 default) after corroboration gate. Formative memories take a separate `FormativeScoring.score()` path.

**Change:** Multiply the continuous graduation score by `relationalComplexityOrDefault()` on the normal scoring path. Formative memories are exempt — they represent seeded developmental history, not runtime learning, and their scores should not be capacity-differentiated.

```java
/**
 * Capacity modulation per Cattell's (1971) Investment Theory:
 * relationalComplexity (Halford 1998) scales the graduation score —
 * higher relational complexity enables better abstraction from experience,
 * producing higher-quality knowledge representations (§D6 score vs threshold).
 *
 * <p>Formative memories (from memory-seeding) are exempt — developmental
 * history is pre-established, not subject to runtime capacity differences.
 *
 * <p>Note: this score flows into BehavioralSynthesisPhase as outcomeIntensity (β).
 * Combined with CAPS alpha modulation (§4.1, associativeReach), agents uniformly
 * low across dimensions experience cross-site compounding. This is intentional —
 * the two dimensions measure independent cognitive substrates (§2.1).
 */
double rawScore = confidence != null ? confidence.value() : 0.5;
double capacityFactor = capacityConfig.relationalComplexityOrDefault();
return rawScore * capacityFactor;
```

**Wiring:** Constructor-inject `CognitiveDefaultsRegistry`. Resolve agent capacity via `memory.subject().id()` → `registry.forAgentOrDefaults(agentId)`. Add `String agentId` to `GraduationContext` — pre-release, the API break is acceptable and cleaner than relying on the implicit contract that `Memory.subject()` always represents the agent.

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

**Wiring:** PersonalityEvolutionOrchestrator runs in tick context. Add `CognitiveDefaultsRegistry` dependency, resolve capacity from `registry.forAgentOrDefaults(agentId)`.

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
- **SearchBudgetTickParticipant** — already uses capacity ceilings, unaffected
- **EmotionRegulationTickParticipant** — uses depletion, unaffected
- **CognitiveResourcePool** — depletion is orthogonal to trait capacity (§D7)

### 6.1 API Changes

- **GraduationContext** (memory-api) — gains `String agentId` field. Pre-release API break.
- **CbrRecordLifecycle** (memory-api) — gains 4-arg `recordOutcome` default method. Backwards-compatible.
- **CapsEngine** (caps-api) — `updateWeights()` changes from 6 params to `(AgentCapsState, WeightUpdateContext)`. Breaking SPI change, 6 implementations.
- **WeightUpdateContext** (caps-api) — new record type.

## 7. Testing Strategy

Each site needs:
1. **Unit test:** Verify `effectiveLR = baseLR * dimension` for multiplier sites, `effectiveCeiling = baseCeiling * dimension` for ceiling sites
2. **Boundary test:** Capacity at 0.0, 0.55, 0.95, 1.0, and null (1.0 via `*OrDefault()`)
3. **Integration test:** CognitiveDefaults with known capacity → verify learning rate at the site reflects the capacity

For CapsWeightUpdater: verify `WeightUpdateContext` carries capacity through to alpha computation.
For CbrRecordStore: verify 4-arg `recordOutcome` overload uses the override, 3-arg ignores it. Verify decorator chain forwards the 4-arg call correctly.
For StrategyLearning: verify LLM prompt range matches the effective clamp value.

### 7.1 Cross-Site Integration Test

Run full consolidation pipeline with agents at different capacity levels. Verify:
- Graduation score × CAPS alpha interaction is proportional to independent dimension values (not quadratic in a single dimension)
- An agent with high associativeReach but low relationalComplexity has fast CAPS learning but lower graduation scores
- An agent with all dimensions at 1.0 produces identical behavior to the pre-modulation baseline

## References

- Cattell, R.B. (1971). *Abilities: Their Structure, Growth, and Action.* — Investment Theory
- Halford, G.S. (1998). *Processing capacity defined by relational complexity.* — relationalComplexity dimension
- Mednick, S.A. (1962). *The associative basis of the creative process.* — associativeReach dimension
- Engle, R.W. & Kane, M.J. (2004). *Executive attention, working memory capacity.* — workingMemorySpan dimension
- Rescorla, R.A. & Wagner, A.R. (1972). *A theory of Pavlovian conditioning.* — CapsWeightUpdater associative learning
- `cognitive-api/.../CognitiveCapacityConfig.java` — capacity record definition
- `cognitive-index/.../CognitiveDerivationEngine.java:270-299` — capacity derivation and compression
- `caps-engine/.../CapsWeightUpdater.java:48-66` — Rescorla-Wagner alpha computation
- `caps-api/.../CapsEngine.java:16-22` — updateWeights SPI (6 params → WeightUpdateContext)
- `memory-api/.../CbrRecordLifecycle.java:13` — recordOutcome SPI
- `memory-api/.../CbrOutcome.java:33-38` — EMA adjustConfidence
- `memory-api/.../DelegatingCbrRecordStore.java` — decorator forwarding base
- `cognition/.../DriveAdaptationPhase.java:220-248` — drive intensity learning rate (conditional satisfaction)
- `cognition/.../StrategyLearningOrchestrator.java:50-56,554-588` — systemPrompt + maxDimensionDelta clamp
- `mindmap-intelligence/.../DefaultGraduationScorer.java:33-41` — graduation scoring (formative bypass)
- `cognition/.../PersonalityEvolutionOrchestrator.java:103-110` — l2Ceiling drift check
- Issue #840 — intelligence capacity layer (prerequisite)
- Issue #880 — shared fatigue substrate (future capacity×fatigue interaction)
- Issue #890 — this issue

# Coping Strategies: Appraisal-Coping-Reappraisal Cycle

**Issue:** casehubio/neocortex#595
**Branch:** issue-595-coping-strategies
**Date:** 2026-11-15
**Literature:** Marsella & Gratch (2009) EMA; Lazarus & Folkman (1984); Connor-Smith & Flachsbart (2007)

## Overview

Implement the EMA (EMotion and Adaptation) coping model as a new layer in the cognitive pipeline between Scherer appraisal and Gross regulation. Characters gain structured coping responses to stress — they can plan, reinterpret, disengage, seek support, deny, avoid, or resign, with personality biasing which strategies they reach for first. Coping operates through an intra-tick micro-loop: appraise → select coping strategy → reinterpret the situation narrative → re-evaluate → converge or iterate.

Coping subsumes intrapersonal regulation strategy selection. The existing EmotionRegulationStrategy enum becomes a downstream execution mechanism. Extrinsic regulation (CO_REGULATION, DELIBERATE_PROVOCATION) remains in the social cognition pathway.

## Architecture

### Pipeline Position

```
Tick Event
  → SchererAppraisalStrategy.appraise()     [existing]
    → SEC checks: relevance, implication, coping, normative
    → EmotionMapper → emotions + action tendencies
  → CopingMicroLoop                          [NEW]
    → CopingStrategyPredictor (numeric)
    → CopingGenerationPhase (LLM)
    → Keyword SEC re-evaluation
    → Converge or iterate
  → EmotionRegulationGenerationPhase         [refactored: receives coping strategy]
    → Execute regulation strategy
  → AppraisalDriveModulator                  [existing]
  → Goal lifecycle dispatch                  [existing + coping goal ops]
```

### CopingState — The Micro-Loop Working State

The interpretation narrative is the mutable causal interpretation. CopingState is created at micro-loop entry and discarded after convergence dispatch.

```java
public record CopingState(
    String interpretationNarrative,           // mutable: starts as raw situation, reinterpreted each iteration
    Map<String, Double> secDimensions,        // re-derived from each reinterpretation via keyword SEC checks
    List<CognitiveEmotion> workingEmotions,   // re-derived from SEC dimensions via EmotionMapper
    int iteration,                            // current micro-loop pass (0-indexed)
    List<GoalOperation> goalOperations,       // accumulated: create, drop, defer goals
    List<DriveModulation> driveModulations,   // accumulated: drive intensity adjustments
    List<AttentionDirective> attentionDirectives,  // accumulated: focus/suppress directives
    List<CopingStrategyAttempt> strategiesAttempted // trace: what was tried, in order
) {}
```

**Lifecycle:**
1. Created with raw situation narrative from AppraisalContext, initial SEC dimensions and emotions from AppraisalResult
2. Each micro-loop iteration: LLM reinterprets narrative → keyword SEC re-evaluates → EmotionMapper re-derives emotions → effects accumulated
3. On convergence: goalOperations dispatched to goal lifecycle, driveModulations dispatched to AppraisalDriveModulator, final interpretationNarrative and emotions passed to regulation execution

### Micro-Loop Algorithm

```
function copingMicroLoop(appraisalContext, appraisalResult, copingDefaults, maxIterations=3):
    state = CopingState(
        interpretationNarrative = appraisalContext.situation(),
        secDimensions = appraisalResult.dimensions(),
        workingEmotions = appraisalResult.emotions(),
        iteration = 0
    )

    while state.iteration < maxIterations:
        // 1. Check for coping opportunity
        opportunity = identifyCopingOpportunity(state.workingEmotions, threshold)
        if opportunity.isEmpty():
            break  // converged — no emotion intense enough to trigger coping

        // 2. Predict strategy (mechanical: personality + controllability)
        prediction = copingStrategyPredictor.predict(
            copingDefaults, state.secDimensions, state.workingEmotions)

        // 3. Select strategy + reinterpret (LLM: situational context)
        copingResult = copingGenerationPhase.generate(
            appraisalContext, state, prediction)

        // 4. Apply effects
        state = state.withReinterpretation(copingResult.narrative())
                     .withAccumulatedEffects(copingResult.effects())
                     .withStrategy(copingResult.strategy())

        // 5. Keyword SEC re-evaluation on reinterpreted narrative
        newDimensions = keywordSecChecks.evaluate(state.interpretationNarrative)
        newEmotions = emotionMapper.mapEmotions(newDimensions)
        state = state.withDimensions(newDimensions).withEmotions(newEmotions)

        state = state.withIteration(state.iteration + 1)

    return state  // converged: dispatch accumulated effects
```

**Convergence criteria:**
- No emotion in workingEmotions exceeds the coping opportunity threshold (intensity has dropped through reinterpretation)
- Iteration cap reached (maxIterations, default 3)
- Same strategy selected twice in a row (oscillation detection)

**Cost:** +1 LLM call per iteration (narrative reinterpretation). Keyword SEC checks are zero-cost. Typical convergence in 1-2 iterations. Worst case with N=3: +3 LLM calls per tick (total tick: 4-7 LLM calls vs current 4-5 without coping).

## EMA Coping Strategy Taxonomy

12 strategies organized by the mental representation they target, mapped from Marsella & Gratch (2009):

### Attention-Related

| Strategy | Computational Effect | Personality Bias |
|---|---|---|
| **Seek information** | AttentionDirective: monitor uncertain state | Openness ↑ |
| **Suppress information** | AttentionDirective: stop monitoring | Neuroticism ↑ |

### Belief-Related

| Strategy | Computational Effect | Personality Bias |
|---|---|---|
| **Shift responsibility** | Narrative transformation: reframe causal attribution | Neuroticism ↑, Agreeableness ↓ |
| **Wishful thinking / Denial** | Narrative transformation: alter perceived likelihood | Neuroticism ↑ |

### Desire-Related

| Strategy | Computational Effect | Personality Bias |
|---|---|---|
| **Mental disengagement** | DriveModulation: reduce drive intensity for threatened axis | Neuroticism ↑ |
| **Positive reinterpretation** | Narrative transformation: highlight positive aspects | Openness ↑ |

### Intention-Related

| Strategy | Computational Effect | Personality Bias |
|---|---|---|
| **Planning** | GoalOperation: create plan goal | Conscientiousness ↑ |
| **Seek instrumental support** | GoalOperation: create social support goal | Agreeableness ↑, Extraversion ↑ |
| **Active confrontation** | GoalOperation: create confrontation goal | Extraversion ↑, Agreeableness ↓ |
| **Procrastination** | GoalOperation: defer goal to future | Conscientiousness ↓ |
| **Resignation / Acceptance** | GoalOperation: drop goal; DriveModulation: reduce intensity | Neuroticism ↓ (acceptance) or ↑ (resignation) |
| **Avoidance** | GoalOperation: create avoidance action | Neuroticism ↑ |

## Strategy-to-Regulation Execution Mapping

Each coping strategy routes to either regulation execution or direct effects:

| EMA Coping Strategy | Route | Regulation Target |
|---|---|---|
| Positive reinterpretation | Regulation | COGNITIVE_CHANGE |
| Seek instrumental support | Regulation | SOCIAL_SUPPORT_SEEKING |
| Seek emotional support | Regulation | SOCIAL_SHARING |
| Avoidance | Regulation | SITUATION_SELECTION |
| Mental disengagement | Regulation | ATTENTIONAL_DEPLOYMENT |
| Suppression | Regulation | RESPONSE_MODULATION |
| Active confrontation | Regulation | SITUATION_MODIFICATION |
| Planning | Direct effect | GoalOperation (create plan goal) |
| Acceptance | Direct effect | DriveModulation + narrative |
| Denial | Direct effect | Narrative transformation |
| Wishful thinking | Direct effect | Narrative transformation |
| Shift responsibility | Direct effect | Narrative transformation |
| Resignation | Direct effect | GoalOperation (drop goal) |
| Procrastination | Direct effect | GoalOperation (defer goal) |

**Regulation-routed strategies:** EmotionRegulationGenerationPhase receives the coping strategy and the mapped EmotionRegulationStrategy. It executes the regulation (producing narrative, effectiveness, environmental directives) but does not independently select a strategy — the coping layer has already decided.

**Direct-effect strategies:** Effects accumulate in CopingState and dispatch after convergence. No regulation execution call needed.

## Personality-Coping Mapping

### CopingDefaults (from CDE)

Derived from Big Five personality facets via CognitiveDerivationEngine, following the RegulationDefaults pattern:

```java
public record CopingDefaults(
    double planfulTendency,           // Conscientiousness → problem-focused coping
    double reinterpretationTendency,  // Openness → positive reinterpretation, meaning-making
    double avoidanceTendency,         // Neuroticism → avoidant/emotion-focused coping
    double supportSeekingTendency,    // Agreeableness + Extraversion → social support
    double acceptanceTendency         // Low Neuroticism → acceptance, equanimity
) {}
```

**Source correlations** (Connor-Smith & Flachsbart 2007 meta-analysis):
- Conscientiousness → problem-focused engagement (r = .21)
- Neuroticism → disengagement/avoidance (r = .25)
- Openness → positive reinterpretation (r = .11)
- Agreeableness → social support seeking (r = .11)
- Extraversion → social support seeking (r = .14)

### CopingStrategyPredictor

Mechanical predictor operating on already-resolved numeric signals:

```java
public class CopingStrategyPredictor {
    Optional<CopingPrediction> predict(
        CopingDefaults defaults,
        Map<String, Double> secDimensions,  // controllability, adjustability
        List<CognitiveEmotion> emotions
    )
}
```

**Selection logic (following EMA):**
1. Read controllability from SEC dimensions
2. High controllability (> 0.6) → filter to intention-related strategies (planning, seek support, confrontation)
3. Low controllability (< 0.3) → filter to belief/desire-related strategies (reinterpretation, disengagement, denial, wishful thinking)
4. Medium controllability → all strategies viable
5. Among viable strategies, personality bias resolves: highest CopingDefaults dimension wins
6. Output: Optional<CopingPrediction> with strategy and confidence

The predictor biases; the LLM decides. When the predictor has high confidence (strong personality signal + clear controllability), it pins the strategy. When signals are mixed, it yields to the LLM.

### Distinction from RegulationDefaults

CopingDefaults encodes personality **preferences** — what you tend to do.
RegulationDefaults encodes personality **capacities** — how well you do it.

RegulationDefaults is retained: its capacity scores (reappraisalCapacity, suppressionCapacity) inform execution quality in EmotionRegulationGenerationPhase. RegulationStrategyPredictor is retired as a selector — its role is absorbed by CopingStrategyPredictor.

The safety hard gate (fatigue/intensity → ATTENTIONAL_DEPLOYMENT override) moves to a pre-coping gate, preserving its unconditional override behavior.

## Coping SEC Check Integration

The existing CopingCheck (Scherer SEC Stage 3) evaluates CONTROLLABILITY and ADJUSTABILITY. This feeds into the coping layer:

**Initial pass:** SEC checks run as part of SchererAppraisalStrategy → controllability shapes emotion type (fear vs anger via EmotionMapper) → controllability also feeds CopingStrategyPredictor for strategy filtering.

**Micro-loop re-evaluation:** Keyword-based CopingCheck re-evaluates controllability on the reinterpreted narrative. This is the reappraisal feedback mechanism: if "positive reinterpretation" transforms "I'm trapped and helpless" to "I have options I haven't tried," keyword CopingCheck detects more agency words → higher controllability → potentially different strategy viability on the next iteration.

All four keyword SEC checks run in re-evaluation (relevance, implication, coping, normative). These are deterministic and zero-cost.

## Scope Boundaries

**In scope:**
- CopingStrategy enum (12 strategies)
- CopingState record and micro-loop orchestrator
- CopingDefaults derivation in CDE
- CopingStrategyPredictor
- CopingGenerationPhase (LLM-based)
- Strategy-to-execution mapping table
- Refactor EmotionRegulationGenerationPhase to receive coping strategy
- Retire RegulationStrategyPredictor as selector
- CognitionConfig.copingEnabled() gate
- Integration into CognitionTickParticipant pipeline

**Out of scope:**
- Extrinsic regulation (CO_REGULATION, DELIBERATE_PROVOCATION) — stays in social cognition
- CognitiveDefaults structural refactoring (D8 — separate issue)
- Quarkmind-specific optimizations (D9 — config-gated)
- Cross-tick coping effectiveness tracking (future enhancement)

## Testing Strategy

**Component tests (fast):**
- CopingDefaults derivation from Big Five profiles
- CopingStrategyPredictor selection logic: controllability × personality → strategy
- CopingState immutability and accumulation semantics
- Strategy-to-execution mapping table coverage
- Micro-loop convergence detection and iteration cap

**Plumbing tests (fast):**
- CopingMicroLoop wiring: appraisal → coping → regulation dispatch
- Keyword SEC re-evaluation on reinterpreted narratives
- GoalOperation and DriveModulation dispatch after convergence
- CognitionConfig.copingEnabled() gating

**Emergence tests (LLM eval):**
- Personality differentiation: high-conscientiousness character plans, high-neuroticism character avoids/denies
- Strategy chaining: character tries planning → uncontrollable situation → shifts to acceptance
- Reinterpretation quality: LLM produces narratively coherent reinterpretations
- Convergence behavior: intensity reduction across micro-loop iterations

## References

- Marsella, S. & Gratch, J. (2009). EMA: A process model of appraisal dynamics. *Cognitive Systems Research*, 10(1), 70-90. — Coping strategy taxonomy, selection mechanism, reappraisal cycle
- Lazarus, R.S. & Folkman, S. (1984). *Stress, Appraisal, and Coping*. Springer. — Foundational transactional model
- Connor-Smith, J.K. & Flachsbart, C. (2007). Relations between personality and coping: A meta-analysis. *Journal of Personality and Social Psychology*, 93(6), 1080-1107. — Big Five→coping correlations
- Barańczuk, U. (2019). Big Five personality traits and emotion regulation: A meta-analysis. — RegulationDefaults derivation pattern
- Zaki, J. & Williams, W.C. (2013). Interpersonal emotion regulation. — Intrinsic/extrinsic distinction for D2 scoping
- SchererAppraisalStrategy.java — Existing 4-SEC-check pipeline
- EmotionRegulationStrategy.java — 10 regulation strategies (execution targets)
- CopingCheck.java — Existing keyword SEC check (controllability/adjustability)
- RegulationStrategyPredictor.java — Pattern for hybrid predictor + LLM
- RegulationDefaults.java — Pattern for CDE-derived personality defaults
- D4-exploration.md — Deep analysis: narrative as causal interpretation
- D6-exploration.md — Deep analysis: hybrid personality-coping mapping

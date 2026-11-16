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
  → SchererAppraisalStrategy.appraise()     [existing, extended]
    → SEC checks: relevance, implication, coping, normative
    → EmotionMapper → emotions + action tendencies
    → AppraisalResult now carries merged SEC dimensions (Map<String, Double>)
  → Pre-coping safety gate                   [NEW: relocated from regulation Layer 1]
    → fatigue > 0.7 or intensity > 0.75 → skip coping, pin ATTENTIONAL_DEPLOYMENT
  → CopingMicroLoop                          [NEW]
    → CAPS coping attractor resolution (learned strategy preferences)
    → CopingStrategyPredictor (numeric fallback: personality + controllability + load)
    → CopingGenerationPhase (LLM)
    → Keyword SEC re-evaluation (via synthetic AppraisalContext)
    → Converge or iterate
  → EmotionRegulationGenerationPhase         [refactored: receives coping strategy + reinterpreted narrative]
    → Execute regulation (produces effectiveness, fatigue, regulated intensity, narrative)
  → CAPS weight update                       [existing, informed by regulation outcome → coping attractor learning]
  → AppraisalDriveModulator                  [existing + coping DriveModulations]
  → Goal lifecycle dispatch                  [existing + coping GoalOperations via appendGoals]
```

### AppraisalResult Extension

`AppraisalResult` is extended with a `Map<String, Double> secDimensions` field — the merged SEC dimensions from `SchererAppraisalStrategy.appraise()`. Currently, `SchererAppraisalStrategy` computes `List<SecResult>` values and passes them to `EmotionMapper.mergeDimensions()` internally, but the merged dimensions are discarded after emotion mapping. The change surfaces them on the result record so that downstream consumers (coping layer, observability) can access controllability, adjustability, and other SEC dimensions without re-running the checks.

```java
public record AppraisalResult(
        List<CognitiveEmotion> emotions,
        List<ActionTendency> actionTendencies,
        HabituationState updatedHabituation,
        @Nullable String narrative,
        Map<String, Double> secDimensions       // NEW: merged SEC dimensions
) {}
```

`SchererAppraisalStrategy.appraise()` already calls `EmotionMapper.mergeDimensions(results)` — it passes the result to the new field instead of discarding it.

### CopingState — The Micro-Loop Working State

The interpretation narrative is the causal interpretation — evolved through wither-pattern copies at each iteration. CopingState is created at micro-loop entry and discarded after convergence dispatch.

```java
public record CopingState(
    String interpretationNarrative,           // starts as raw situation, reinterpreted each iteration via withX()
    Map<String, Double> secDimensions,        // re-derived from each reinterpretation via keyword SEC checks
    List<CognitiveEmotion> workingEmotions,   // re-derived from SEC dimensions via EmotionMapper
    int iteration,                            // current micro-loop pass (0-indexed)
    List<GoalOperation> goalOperations,       // accumulated: create, drop, defer goals
    List<DriveModulation> driveModulations,   // accumulated: drive intensity adjustments
    List<AttentionDirective> attentionDirectives,  // accumulated: focus/suppress directives
    List<CopingStrategyAttempt> strategiesAttempted // trace: what was tried, in order
) {}
```

### Accumulated Effect Types

```java
public record GoalOperation(
    GoalOperationType type,    // CREATE, DROP, DEFER
    String goalName,
    String goalDescription,
    DriveAxis axis,
    String formationReason
) {}

public enum GoalOperationType { CREATE, DROP, DEFER }

public record DriveModulation(
    DriveAxis axis,
    double intensityDelta,     // negative = reduce, positive = increase
    String reason
) {}

public record AttentionDirective(
    AttentionDirectiveType type,  // FOCUS, SUPPRESS
    String target,                // what to attend to or suppress
    String reason
) {}

public enum AttentionDirectiveType { FOCUS, SUPPRESS }

public record CopingStrategyAttempt(
    CopingStrategy strategy,
    int iteration,
    String reinterpretedNarrative
) {}
```

**Lifecycle:**
1. Created with raw situation narrative from AppraisalContext, initial SEC dimensions from AppraisalResult.secDimensions(), emotions from AppraisalResult.emotions()
2. Each micro-loop iteration: LLM reinterprets narrative → keyword SEC re-evaluates (via synthetic AppraisalContext) → EmotionMapper re-derives emotions → effects accumulated
3. On convergence: GoalOperations dispatch to GoalProposalOrchestrator (CREATE → appendGoals, DROP → requestAbandonment, DEFER → requestDemotion), DriveModulations dispatch to AppraisalDriveModulator, AttentionDirectives dispatch to AttentionPromptSection, final interpretationNarrative and emotions passed to regulation execution

### Micro-Loop Algorithm

```
function copingMicroLoop(appraisalContext, appraisalResult, copingDefaults,
                         axes, cognitiveLoad, capsEngine, maxIterations=3):
    state = CopingState(
        interpretationNarrative = appraisalContext.situation().narrative(),
        secDimensions = appraisalResult.secDimensions(),    // merged SEC dimensions from extended AppraisalResult
        workingEmotions = appraisalResult.emotions(),
        iteration = 0
    )

    while state.iteration < maxIterations:
        // 1. Check for coping opportunity
        opportunity = identifyCopingOpportunity(state.workingEmotions, threshold)
        if opportunity.isEmpty():
            break  // converged — no emotion intense enough to trigger coping

        // 2. CAPS coping attractor resolution (Layer 2)
        pinnedStrategy = null
        if capsEngine != null:
            capsResult = capsEngine.settle(capsState, socialInputs)
            copingAttractors = capsResult.attractors().filter(category == "coping")
            if copingAttractors.hasDominant():
                pinnedStrategy = copingAttractors.top().strategy()

        // 3. Predict strategy fallback (Layer 3: personality + controllability + load)
        if pinnedStrategy == null:
            prediction = copingStrategyPredictor.predict(
                copingDefaults, state.secDimensions, state.workingEmotions,
                axes, cognitiveLoad)
            pinnedStrategy = prediction.map(p -> p.strategy()).orElse(null)

        // 4. Select strategy + reinterpret (Layer 4: LLM with situational context)
        copingResult = copingGenerationPhase.generate(
            appraisalContext, state, pinnedStrategy)

        // 5. Apply effects
        state = state.withReinterpretation(copingResult.narrative())
                     .withAccumulatedEffects(copingResult.effects())
                     .withStrategy(copingResult.strategy())

        // 6. Oscillation detection — any previously attempted strategy
        if state.strategiesAttempted.containsStrategy(copingResult.strategy()):
            break  // oscillation — same strategy attempted again

        // 7. Keyword SEC re-evaluation via synthetic AppraisalContext
        copingAppraisalContext = new AppraisalContext(
            appraisalContext.agentId(),
            new PerceivedSituation(state.interpretationNarrative),  // reinterpreted narrative
            appraisalContext.drives(),           // unchanged
            appraisalContext.weights(),          // unchanged
            appraisalContext.habituationConfig(),
            appraisalContext.habituation(),
            appraisalContext.currentMood(),
            appraisalContext.dispositionAxes())
        newSecResults = [relevanceCheck, implicationCheck, copingCheck, normativeCheck]
                            .map(check -> check.evaluate(copingAppraisalContext))
        newDimensions = EmotionMapper.mergeDimensions(newSecResults)
        newEmotions = EmotionMapper.mapEmotions(newSecResults, appraisalContext.agentId())
        state = state.withDimensions(newDimensions).withEmotions(newEmotions)

        state = state.withIteration(state.iteration + 1)

    return state  // converged: dispatch accumulated effects
```

**Convergence criteria:**
- No emotion in workingEmotions exceeds the coping opportunity threshold (intensity has dropped through reinterpretation). The threshold is a configurable `CognitionConfig.copingOpportunityThreshold()` value (default 0.6 — same scale as emotion intensity 0.0-1.0). Emotions below this intensity don't warrant active coping.
- Iteration cap reached (maxIterations, configurable via `CognitionConfig.copingMaxIterations()`, default 3)
- Strategy repeat detected — any strategy that appears in `strategiesAttempted` is selected again (detects both A→A and A→B→A oscillation patterns)

**Cost:** +1 LLM call per iteration (narrative reinterpretation). Keyword SEC checks are zero-cost. Typical convergence in 1-2 iterations. Worst case with N=3: +3 LLM calls per tick (total tick: 4-7 LLM calls vs current 4-5 without coping).

## EMA Coping Strategy Taxonomy

16 strategies organized by the mental representation they target, mapped from Marsella & Gratch (2009). EMA's original taxonomy groups some strategies (e.g., "wishful thinking / denial"); we split them where the computational effects differ:

### Attention-Related

| Strategy | Computational Effect | Personality Bias |
|---|---|---|
| **Seek information** | AttentionDirective: monitor uncertain state | Openness ↑ |
| **Suppress information** | AttentionDirective: stop monitoring | Neuroticism ↑ |

### Belief-Related

| Strategy | Computational Effect | Personality Bias |
|---|---|---|
| **Shift responsibility** | Narrative transformation: reframe causal attribution | Neuroticism ↑, Agreeableness ↓ |
| **Wishful thinking** | Narrative transformation: alter perceived likelihood | Neuroticism ↑ |
| **Denial** | Narrative transformation: refuse to acknowledge stressor | Neuroticism ↑ |

### Desire-Related

| Strategy | Computational Effect | Personality Bias |
|---|---|---|
| **Mental disengagement** | DriveModulation: reduce drive intensity for threatened axis | Neuroticism ↑ |
| **Positive reinterpretation** | Narrative transformation: highlight positive aspects | Openness ↑ |
| **Acceptance** | DriveModulation: reduce intensity + narrative | Neuroticism ↓ |

### Intention-Related

| Strategy | Computational Effect | Personality Bias |
|---|---|---|
| **Planning** | GoalOperation: create plan goal | Conscientiousness ↑ |
| **Seek instrumental support** | GoalOperation: create social support goal | Agreeableness ↑, Extraversion ↑ |
| **Seek emotional support** | Regulation: SOCIAL_SHARING | Agreeableness ↑, Extraversion ↑ |
| **Active confrontation** | GoalOperation: create confrontation goal | Extraversion ↑, Agreeableness ↓ |
| **Suppression** | Regulation: RESPONSE_MODULATION | Conscientiousness ↑ |
| **Procrastination** | GoalOperation: defer goal to future | Conscientiousness ↓ |
| **Resignation** | GoalOperation: drop goal | Neuroticism ↑ |
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
| Seek information | Direct effect | AttentionDirective (FOCUS on uncertain state) |
| Suppress information | Direct effect | AttentionDirective (SUPPRESS monitoring) |

**Regulation-routed strategies:** EmotionRegulationGenerationPhase receives the coping strategy, the mapped EmotionRegulationStrategy, AND the coping-produced reinterpreted narrative. It does not re-select a strategy or re-do the cognitive transformation. Its role for regulation-routed strategies is to:
- Assess regulation effectiveness (0.0-1.0)
- Compute regulated intensity (intensity reduction from regulation)
- Produce a second-person experiential narrative of the regulation process
- Generate environmental directives (for SITUATION_SELECTION/SITUATION_MODIFICATION)
- Track fatigue contribution and resource accounting

For COGNITIVE_CHANGE specifically: the coping layer already produced the cognitive reinterpretation. The regulation execution receives the before/after narratives and assesses HOW WELL the reinterpretation worked — effectiveness, intensity change, fatigue cost. This is not redundant: the coping call produces the cognitive transformation; the regulation call evaluates its mechanistic effects. Without the regulation call, there is no effectiveness score, no fatigue tracking, no CAPS weight update input, and no experiential narrative.

**Direct-effect strategies:** Effects accumulate in CopingState and dispatch after convergence. No regulation execution call needed. Attention directives dispatch to AttentionPromptSection as context hints — FOCUS directives increase attention weight for the target topic, SUPPRESS directives add the target to the suppression list.

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

Mechanical predictor operating on already-resolved numeric signals, enriched with regulation-pipeline intelligence from the retired RegulationStrategyPredictor:

```java
public class CopingStrategyPredictor {
    Optional<CopingPrediction> predict(
        CopingDefaults defaults,
        Map<String, Double> secDimensions,  // controllability, adjustability
        List<CognitiveEmotion> emotions,
        @Nullable DispositionAxes axes,
        @Nullable CognitiveLoadLevel cognitiveLoad
    )
}
```

**Selection logic (EMA core, enriched with regulation-pipeline intelligence):**
1. **Cognitive load gate:** HIGH load → filter to low-cognitive-cost strategies (suppression, avoidance, mental disengagement, resignation). Complex strategies (planning, active confrontation, positive reinterpretation) require deliberation capacity that is unavailable under high load. (Migrated from RegulationStrategyPredictor.predictUnderHighLoad)
2. **Controllability-based filtering (EMA core):**
   - High controllability (> 0.6) → intention-related strategies (planning, seek support, confrontation, suppression)
   - Low controllability (< 0.3) → belief/desire-related strategies (reinterpretation, disengagement, denial, wishful thinking, acceptance)
   - Medium controllability → all strategies viable
3. **Mild distress override:** If peak emotion intensity < 0.40 AND emotion would be classified as uncontrollable → widen to controllable strategies. Mild uncontrollable distress doesn't warrant avoidance/disengagement. (Migrated from RegulationStrategyPredictor.MILD_DISTRESS_THRESHOLD)
4. **Self-conscious emotion refinement:** If dominant emotion is self-conscious (SHAME, REMORSE) AND personality is avoidant (avoidanceTendency > 0.6 or axes.conflictMode == "avoidant") → bias toward Avoidance strategy. This preserves the Nathanson 1992 compass-of-shame behavior. (Migrated from RegulationStrategyPredictor.predictSelfConsciousFromCapacities)
5. **Personality bias resolution:** Among viable strategies, highest CopingDefaults dimension wins. When multiple strategies map to the same dimension (e.g., Planning and Active confrontation both map to planfulTendency), confidence is lowered and the prediction identifies the strategy FAMILY rather than a specific strategy. The LLM resolves within-family ties using situational context.
6. **Output:** Optional<CopingPrediction> with strategy, confidence, and family label

The predictor biases; the LLM decides. When the predictor has high confidence (strong personality signal + clear controllability + no within-family ties), it pins the strategy. When signals are mixed or strategies tie on the same dimension, it yields to the LLM with a family-level bias.

**Design note — controllability-first vs emotion-category-first:** The coping predictor intentionally uses EMA's controllability-first filtering rather than RegulationStrategyPredictor's emotion-category-first approach. Emotion categories in RegulationStrategyPredictor (CONTROLLABLE_NEGATIVE, UNCONTROLLABLE_NEGATIVE, etc.) are proxies for controllability — ANGER means controllable, FEAR means uncontrollable. Since CopingStrategyPredictor has direct access to SEC controllability dimensions, emotion categories are redundant. The specific capabilities that ARE migrated (cognitive load gate, mild distress override, self-conscious refinement) are orthogonal to controllability and would be lost without explicit handling.

### Distinction from RegulationDefaults

CopingDefaults encodes personality **preferences** — what you tend to do.
RegulationDefaults encodes personality **capacities** — how well you do it.

RegulationDefaults is retained: its capacity scores (reappraisalCapacity, suppressionCapacity) inform execution quality in EmotionRegulationGenerationPhase. RegulationStrategyPredictor is retired as a selector — its intelligence is absorbed by CopingStrategyPredictor (cognitive load gate, mild distress override, self-conscious emotion handling).

### Pre-Coping Safety Gate

The safety hard gate (fatigue/intensity → ATTENTIONAL_DEPLOYMENT override) relocates from EmotionRegulationTickParticipant (Layer 1) to a pre-coping gate. Operational specification:

1. **Check:** `regulationFatigue > 0.7` OR `peakEmotionIntensity > 0.75` (same thresholds as existing `SAFETY_FATIGUE_THRESHOLD` and `SAFETY_INTENSITY_THRESHOLD`)
2. **If triggered:** Skip the entire CopingMicroLoop. No CopingState is created. Pin ATTENTIONAL_DEPLOYMENT directly on EmotionRegulationGenerationPhase.
3. **Regulation execution:** EmotionRegulationGenerationPhase receives the pinned ATTENTIONAL_DEPLOYMENT strategy and executes normally — producing effectiveness, fatigue, regulated intensity, and experiential narrative.
4. **After regulation:** CAPS weight update proceeds with the regulation outcome. No coping-specific effects (GoalOperations, DriveModulations, AttentionDirectives) are generated because no coping occurred.
5. **Resume path:** After regulation execution, the tick continues to AppraisalDriveModulator and goal lifecycle dispatch as normal.

This preserves the unconditional safety override while cleanly layering it before the coping decision. The thresholds and behavior are identical to the existing implementation.

## Coping SEC Check Integration

The existing CopingCheck (Scherer SEC Stage 3) evaluates CONTROLLABILITY and ADJUSTABILITY. This feeds into the coping layer:

**Initial pass:** SEC checks run as part of SchererAppraisalStrategy → controllability shapes emotion type (fear vs anger via EmotionMapper) → controllability also feeds CopingStrategyPredictor for strategy filtering.

**Micro-loop re-evaluation:** Keyword-based CopingCheck re-evaluates controllability on the reinterpreted narrative. This is the reappraisal feedback mechanism: if "positive reinterpretation" transforms "I'm trapped and helpless" to "I have options I haven't tried," keyword CopingCheck detects more agency words → higher controllability → potentially different strategy viability on the next iteration.

All four keyword SEC checks run in re-evaluation (relevance, implication, coping, normative). These are deterministic and zero-cost.

**Keyword coverage for LLM-generated narratives:** The existing CopingCheck uses 14 keywords (7 agency, 7 helplessness). LLM-generated reinterpretations may use richer vocabulary that doesn't overlap with these sets. Two mitigations:
1. **Expanded keyword sets:** CopingCheck's agency and helplessness sets are expanded to 30-50 words covering common synonyms and phrasings (e.g., agency: "alternatives", "opportunity", "manage", "influence", "path", "empowered"; helplessness: "powerless", "hopeless", "cornered", "helpless", "confined", "futile"). This is a CopingCheck implementation enhancement.
2. **Prompt constraint:** CopingGenerationPhase's reinterpretation prompt instructs the LLM to use vocabulary that signals the intended appraisal shift. Not hardcoded keywords, but a constraint like "express the reinterpreted agency level in concrete, direct language" that naturally produces SEC-detectable text.

## CAPS Integration

CAPS (Connectionist Appraisal Processing System) settling integrates into the coping cascade as a learned strategy selection layer, mirroring its current role in the regulation cascade (EmotionRegulationTickParticipant Layer 2).

### Coping Cascade

The coping selection cascade mirrors the existing regulation cascade structure:

1. **Pre-coping safety gate** — fatigue > 0.7 or intensity > 0.75 → skip coping entirely, pin ATTENTIONAL_DEPLOYMENT for regulation execution
2. **CAPS coping attractor resolution** — if CapsEngine is configured, settle coping attractors using social context inputs. If a coping attractor dominates (strength ≥ regulationConfidenceThreshold, margin ≥ regulationDominanceMargin from RegulationCascadeConfig), pin that coping strategy
3. **CopingStrategyPredictor fallback** — personality + controllability + cognitive load (Layer 3)
4. **CopingGenerationPhase LLM fallback** — full situational context (Layer 4)

### CAPS Weight Updates

After regulation execution produces an outcome (effectiveness, intensity change), CAPS weights are updated via the existing Rescorla-Wagner mechanism:
- `outcomeIntensity` = |peakOriginalIntensity − regulatedIntensity|
- `outcomeValence` = effectiveness > 0.5 ? 1.0 : −1.0
- `salienceMultiplier` = peakOriginalIntensity
- The weight update applies to the coping strategy's attractor node, not the regulation strategy's

This preserves the existing CAPS learning infrastructure (`capsEngine.updateWeights()`, `WeightUpdateContext`, variable ratio schedule) applied at the coping strategy level rather than the regulation strategy level.

### Migration from Regulation CAPS

Existing CAPS regulation attractors (`"regulation"` category) are retired when coping is enabled. A new `"coping"` attractor category is introduced. Initial coping attractor weights are seeded from CopingDefaults, providing a personality-based starting point for learned adaptation. The existing `RegulationCascadeConfig` thresholds (confidence threshold, dominance margin) apply to coping attractors as well — no new config needed.

## Goal Operations Dispatch

After micro-loop convergence, accumulated GoalOperations dispatch through the existing goal lifecycle:

### CREATE Operations

Construct `DriveGoalProposal` from GoalOperation fields and call `GoalProposalOrchestrator.appendGoals()`:
- `GoalOperation.axis` → `DriveGoalProposal.axis`
- `GoalOperation.goalName` → `DriveGoalProposal.goalName`
- `GoalOperation.goalDescription` → `DriveGoalProposal.goalDescription`
- `GoalOperation.formationReason` → `DriveGoalProposal.formationReason`
- Drive intensity derived from the triggering emotion's intensity
- Proposal attributes include `"source": "coping"` and `"copingStrategy": strategy.name()`

These goals enter the existing goal lifecycle — capacity limits, priority management, and cross-axis enrichment all apply. Coping-created goals are subject to the same `maxDriveGoals` cap as drive-formed goals.

### DROP Operations

New method: `GoalProposalOrchestrator.requestAbandonment(agentId, tenantId, goalName, reason)` adds the goal name to the abandonment list for the next tick. This follows the existing abandonment pattern (`evaluateRelevance`) but triggered by coping decision rather than drive decay or failure threshold. The reason string carries the coping rationale (e.g., "resignation: perceived as uncontrollable").

### DEFER Operations

New method: `GoalProposalOrchestrator.requestDemotion(agentId, tenantId, goalName, priority, reason)` adjusts the goal to SECONDARY priority with a demotion reason. The goal remains active but at lower priority, consistent with procrastination semantics — the character hasn't abandoned the goal but has moved it down the priority stack. This follows the existing `PriorityAdjustment` pattern used by narrative-driven escalation/demotion.

### DriveModulation Dispatch

Drive modulations dispatch to `AppraisalDriveModulator` after convergence. Each DriveModulation specifies an axis and intensity delta, which modulates the drive profile for subsequent processing in the same tick.

### AttentionDirective Dispatch

Attention directives dispatch to `AttentionPromptSection` as context hints for the next prompt assembly. FOCUS directives increase attention weight for the target topic; SUPPRESS directives add the target to the suppression list. This integrates with the existing prompt-based attention system without requiring a new directive execution mechanism.

## Scope Boundaries

**In scope:**
- CopingStrategy enum (16 strategies)
- CopingState record (GoalOperation, DriveModulation, AttentionDirective, CopingStrategyAttempt types)
- CopingState micro-loop orchestrator
- CopingDefaults derivation in CDE
- CopingStrategyPredictor (controllability + cognitive load + personality + emotion-type refinement)
- CopingGenerationPhase (LLM-based)
- Strategy-to-execution mapping table (including attention strategy routes)
- Refactor EmotionRegulationGenerationPhase to receive coping strategy + reinterpreted narrative
- Retire RegulationStrategyPredictor as selector (migrate intelligence to CopingStrategyPredictor)
- Pre-coping safety gate (relocated from regulation Layer 1)
- CAPS coping attractor integration (new "coping" category, weight updates from regulation outcomes)
- Goal operations dispatch (appendGoals, requestAbandonment, requestDemotion on GoalProposalOrchestrator)
- AppraisalResult.secDimensions extension
- CopingCheck keyword expansion (agency/helplessness sets to 30-50 words)
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

**Emergence tests (LLM eval) — #998 complete, floor score 4/5:**

| Test | Personality | Controllability | Result |
|------|------------|-----------------|--------|
| Conscientiousness → PLANNING | planful=0.85 | 0.80 (HIGH → INTENTION only) | Floor 4 |
| Neuroticism → defensive cascade | avoidance=0.85 | 0.15 (LOW → BELIEF+DESIRE) | Floor 4 |
| Strategy chaining | reinterp=0.70, planful=0.55 | 0.45 (MEDIUM → all viable) | Floor 4 |
| Reinterpretation coherence | reinterp=0.85 | 0.30 (borderline) | Floor 4 |
| Convergence | planful=0.65 | 0.40 (MEDIUM) | Floor 4 |

Key findings from eval tuning:
- Judge criteria must evaluate behavioural patterns (defensive trajectory, agentic planning), not specific strategy names — multiple EMA strategies are psychologically equivalent per personality
- Drive-narrative alignment is critical: RelevanceCheck sustains emotions only when drive names/triggers appear in the LLM's vocabulary. Drive names must match scenario language.
- Strategy chaining emerges from keyword feedback: reinterpretation produces agency-saturated narrative → CopingCheck shifts controllability up → predictor filters to INTENTION → different personality dimension wins → cross-category chain

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

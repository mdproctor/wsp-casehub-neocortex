# Agent-based OCC Emotions — Pride, Shame, Admiration, Reproach

**Issue:** casehubio/neocortex#383
**Parent epic:** casehubio/neocortex#298
**Builds on:** #296 (prospect-based emotions — Hope, Fear, Satisfaction, etc.)
**Date:** 2026-09-28

## 1. Problem

The OCC emotion model has three appraisal branches. The **event → goal** branch is implemented (GoalAppraisal SPI, HeuristicGoalAppraisal, GoalAffectPhase). The **action → standards** branch is not. Four emotion types (PRIDE, SHAME, ADMIRATION, REPROACH) and four compound types (GRATIFICATION, REMORSE, GRATITUDE, ANGER) are declared in EmotionType and have PAD projections in AlmaPadTable, but no appraisal logic produces them.

Without action-based appraisal, agents cannot evaluate their own or others' actions against standards — a core capability for social cognition, self-regulation, and trust formation.

## 2. Architecture

### 2.1 Additive SPI — parallel to GoalAppraisal

New `ActionAppraisal` SPI in mindmap-api, alongside the existing `GoalAppraisal`. The two SPIs remain independent — goal appraisal handles prospect-based emotions (events relative to goals), action appraisal handles agent-based emotions (actions judged against standards).

```
mindmap-api:
  GoalAppraisal        ── appraise(MindMapNode, AppraisalContext) → List<CognitiveEmotion>
  ActionAppraisal [NEW] ── appraise(ActionContext) → List<CognitiveEmotion>

mindmap-intelligence:
  HeuristicGoalAppraisal   implements GoalAppraisal
  HeuristicActionAppraisal [NEW] implements ActionAppraisal
  
  GoalAffectPhase          ConsolidationPhase — iterates goal nodes
  ActionAppraisalObserver [NEW]  CDI @Observes ExperienceRecorded — real-time
```

### 2.2 Single-trigger observer with dual-path logic

`ActionAppraisalObserver` observes `ExperienceRecorded` events, filtering for `Outcome` events. Two paths within the same handler:

- **Self-appraisal (Pride/Shame):** `Outcome.agentId()` matches the appraising agent — the agent evaluates its own action's outcome.
- **Other-appraisal (Admiration/Reproach):** `metadata.get(TARGET_AGENT)` is present and differs from `agentId()` — the agent evaluates another agent's action.

Both paths access the full `Outcome` record (capability, result, confidence, metadata) for goal-relevance computation. The difference: which `standardsStrictness` field applies (self vs other) and whether `relationshipScore` modulates the result.

**Why single-trigger over dual-trigger:** The original design used RelationshipRecorded events for other-appraisal. Review found that `RelationshipProcessor` constructs RelationshipEvent with `Map.of()` as metadata, losing the `capability` and `result` fields from the original Outcome. Without these structured fields, goal-relevance computation for other-appraisal degrades to NLU on free-text description — which mindmap-intelligence cannot do.

### 2.3 Compound detection — inline

Compound emotions (Gratification, Remorse, Gratitude, Anger) are detected inline within `HeuristicActionAppraisal` by inferring co-occurring prospect emotions from the same inputs. No cross-phase coordination needed.

Both the base agent emotion AND the compound are produced. In OCC theory, multiple emotions genuinely co-occur — Joy (prospect-based: "this goal was achieved") and Gratification (compound: "my actions achieved this goal") are distinct emotional responses. GoalAffectPhase independently produces prospect emotions — this is the intended model, not double-counting.

## 3. New Types — mindmap-api

### 3.1 ActionAppraisal SPI

```java
package io.casehub.neocortex.mindmap;

@FunctionalInterface
public interface ActionAppraisal {
    List<CognitiveEmotion> appraise(ActionContext context);
}
```

Location: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ActionAppraisal.java`

### 3.2 ActionContext record

```java
package io.casehub.neocortex.mindmap;

public record ActionContext(
    String actingAgentId,
    String apprasingAgentId,
    String tenantId,
    String turnId,
    String actionDescription,
    String capability,          // nullable
    ActionOutcome outcome,
    double goalRelevance,       // [-1, 1]
    PadProjection moodBaseline,
    AppraisalWeights weights,
    Instant timestamp
) {
    public ActionContext {
        Objects.requireNonNull(actingAgentId);
        Objects.requireNonNull(apprasingAgentId);
        Objects.requireNonNull(tenantId);
        Objects.requireNonNull(turnId);
        Objects.requireNonNull(actionDescription);
        Objects.requireNonNull(outcome);
        Objects.requireNonNull(moodBaseline);
        if (weights == null) weights = AppraisalWeights.NEUTRAL;
        Objects.requireNonNull(timestamp);
        if (goalRelevance < -1.0 || goalRelevance > 1.0)
            throw new IllegalArgumentException("goalRelevance must be in [-1, 1]");
    }

    public boolean isSelfAction() {
        return actingAgentId.equals(apprasingAgentId);
    }
}
```

Location: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ActionContext.java`

### 3.3 ActionOutcome enum

```java
package io.casehub.neocortex.mindmap;

public enum ActionOutcome {
    SUCCESS, FAILURE, NEUTRAL
}
```

Location: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ActionOutcome.java`

### 3.4 AppraisalWeights extension

Extend the existing record with two new fields:

```java
public record AppraisalWeights(
    double urgencyWeight,
    double relationshipWeight,
    double fearOnsetThreshold,
    double selfStandardsStrictness,    // [0.5, 2.0], default 1.0
    double otherStandardsStrictness    // [0.5, 2.0], default 1.0
) {
    public static final AppraisalWeights NEUTRAL =
        new AppraisalWeights(1.0, 1.0, 1.0, 1.0, 1.0);

    public AppraisalWeights {
        // existing validation for urgencyWeight, relationshipWeight, fearOnsetThreshold
        if (selfStandardsStrictness < 0.5 || selfStandardsStrictness > 2.0)
            throw new IllegalArgumentException("selfStandardsStrictness must be in [0.5, 2.0]");
        if (otherStandardsStrictness < 0.5 || otherStandardsStrictness > 2.0)
            throw new IllegalArgumentException("otherStandardsStrictness must be in [0.5, 2.0]");
    }
}
```

Breaking change — all existing 3-arg constructor calls must be updated to 5-arg.

### 3.5 EmotionSource — add ATTRIBUTED

```java
public enum EmotionSource {
    INTRINSIC,
    EMPATHIC,
    ATTRIBUTED   // NEW — judgment of another agent's action against standards
}
```

- Pride/Shame → INTRINSIC (self-appraisal)
- Admiration/Reproach → ATTRIBUTED (other-appraisal)
- Pity, Happy-for, Gloating, Resentment → EMPATHIC (unchanged)

## 4. New Types — mindmap-intelligence

### 4.1 HeuristicActionAppraisal

Location: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/HeuristicActionAppraisal.java`

#### Praiseworthiness scoring

```
polarity = outcome.SUCCESS → +1, outcome.FAILURE → -1, outcome.NEUTRAL → 0
praiseworthiness = polarity * |goalRelevance|
```

#### Asymmetric thresholds (OCC-correct)

Strict agents feel Shame easily but require high achievements for Pride:

```
standardsStrictness = isSelfAction ? weights.selfStandardsStrictness
                                   : weights.otherStandardsStrictness

// Negative emotions (Shame/Reproach): strict → low bar → easy trigger
negativeThreshold = 0.2 / standardsStrictness

// Positive emotions (Pride/Admiration): strict → high bar → hard trigger
positiveThreshold = 0.2 * standardsStrictness
```

Example with `selfStandardsStrictness = 2.0`:
- Shame threshold: 0.1 (small failures trigger Shame easily)
- Pride threshold: 0.4 (only significant achievements trigger Pride)

#### Emotion mapping

```
if praiseworthiness > positiveThreshold:
    intensity = clamp(|praiseworthiness| / standardsStrictness)
    if isSelfAction → PRIDE (INTRINSIC)
    else           → ADMIRATION (ATTRIBUTED), modulated by relationshipScore

if praiseworthiness < -negativeThreshold:
    intensity = clamp(|praiseworthiness| * standardsStrictness)
    if isSelfAction → SHAME (INTRINSIC)
    else           → REPROACH (ATTRIBUTED), modulated by relationshipScore
```

For other-appraisal, intensity is multiplied by the relationship score from `AppraisalContext.relationshipScores()` — stronger relationships produce stronger emotions.

#### Compound detection (inline)

After producing the base agent emotion, check if compound conditions are met:

| Base emotion | Compound condition | Compound produced |
|---|---|---|
| PRIDE | outcomeSuccess AND goalRelevance > 0.3 | GRATIFICATION |
| SHAME | outcomeFailed AND goalRelevance < -0.3 | REMORSE |
| ADMIRATION | goalRelevance > 0.3 | GRATITUDE |
| REPROACH | goalRelevance < -0.3 | ANGER |

Compound intensity = `max(baseIntensity, |goalRelevance|)`.

Both the base emotion and the compound are returned in the result list.

### 4.2 ActionAppraisalObserver

Location: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ActionAppraisalObserver.java`

```java
@ApplicationScoped
public class ActionAppraisalObserver {

    private final MindMapStore store;
    private final ActionAppraisal appraisal;
    private final CognitiveDefaultsRegistry registry;

    @Inject
    public ActionAppraisalObserver(
            Instance<MindMapStore> store,
            Instance<ActionAppraisal> appraisal,
            Instance<CognitiveDefaultsRegistry> registry) {
        this.store     = store.isResolvable() ? store.get() : null;
        this.appraisal = appraisal.isResolvable() ? appraisal.get() : null;
        this.registry  = registry.isResolvable() ? registry.get() : null;
    }

    public void onExperienceRecorded(@Observes ExperienceRecorded event) {
        if (store == null || appraisal == null) return;
        if (!(event.event() instanceof Outcome outcome)) return;

        // Self-appraisal path
        appraiseSelf(outcome, event);

        // Other-appraisal path
        String targetAgent = outcome.metadata().get(ExperienceAttributeKeys.TARGET_AGENT);
        if (targetAgent != null && !targetAgent.equals(outcome.agentId())) {
            appraiseOther(outcome, targetAgent, event);
        }
    }
}
```

#### ActionContext construction

The observer builds ActionContext by:

1. **ActionOutcome mapping (D12):** Two-stage strategy:
   - Check `metadata.get("outcome-status")` for explicit signal → map to ActionOutcome
   - Fallback: `Outcome.confidence()` as proxy — ≥ 0.7 → SUCCESS, ≤ 0.3 → FAILURE, else NEUTRAL

2. **goalRelevance computation (D14):** Max absolute value across active goals:
   - Find appraising agent's active goals via `store.nodesIn(goalSubgraphId, tenantId)` filtered to `status=active`
   - For each goal: check if `outcome.capability()` matches a goal's `name`, `capability` property, or linked entity name (case-insensitive contains). If matched, relevance magnitude = goal's `priority` property (default 0.5). Sign = positive if outcome is SUCCESS, negative if FAILURE.
   - Use the highest-magnitude match as the scalar goalRelevance. If no goals match → goalRelevance = 0 → no emotion produced.

3. **AppraisalWeights lookup:** From `CognitiveDefaultsRegistry.forAgent(apprasingAgentId)`, falling back to `AppraisalWeights.NEUTRAL`

4. **Relationship score (other-appraisal only):** Query relationship memories via `CaseMemoryStore.search(tenantId, "relationship " + targetAgent, MemoryDomain.RELATIONSHIP)` and extract the most recent quality signal. Default to 0.5 if no relationship data exists. The score modulates Admiration/Reproach intensity — unknown agents produce moderate emotions, trusted agents produce stronger ones.

#### Emotion output

Produced emotions are emitted as `AttentionSignal`s (category: AFFECT_CHANGE), following GoalAffectPhase's existing pattern. The mood system (in blocks layer) receives signals from both paths.

### 4.3 NoOpActionAppraisal

```java
@DefaultBean
@ApplicationScoped
public class NoOpActionAppraisal implements ActionAppraisal {
    @Override
    public List<CognitiveEmotion> appraise(ActionContext context) {
        return List.of();
    }
}
```

Consistent with existing NoOp pattern (NoOpCognitiveGoalDecomposer, NoOpCognitiveGoalRecognizer).

### 4.4 ExperienceAttributeKeys extension

Add to memory-api:

```java
public static final String OUTCOME_STATUS = "outcome-status";
```

Values: `"success"`, `"failure"`, `"neutral"`. Optional — producers that want explicit ActionOutcome control set this key. When absent, the observer falls back to confidence-based mapping.

## 5. AppraisalWeights Derivation — cognitive-index

### 5.1 CognitiveDerivationEngine extension

Extend `deriveAppraisalWeights` to accept `DispositionAxes` and derive standards-related weights:

```java
static AppraisalWeights deriveAppraisalWeights(List<WeightedTerm> profile, DispositionAxes axes) {
    // Existing derivation for urgencyWeight, relationshipWeight, fearOnsetThreshold
    // from dispositionProfile (unchanged)
    ...

    // NEW: derive standards strictness from DispositionAxes
    double selfStrictness = 1.0;
    double otherStrictness = 1.0;

    if (axes != null) {
        // ruleFollowing: strict → high standards, flexible → low standards
        switch (axes.ruleFollowing()) {
            case "strict"   -> { selfStrictness = 1.6; otherStrictness = 1.4; }
            case "moderate" -> { /* defaults */ }
            case "flexible" -> { selfStrictness = 0.7; otherStrictness = 0.6; }
        }

        // socialOrient: cooperative → more forgiving of others, competitive → harsher
        switch (axes.socialOrient()) {
            case "cooperative" -> otherStrictness = Math.max(0.5, otherStrictness - 0.2);
            case "competitive" -> otherStrictness = Math.min(2.0, otherStrictness + 0.2);
        }
    }

    return new AppraisalWeights(
        urgencyRaw, relRaw, fearRaw,
        Math.clamp(selfStrictness, 0.5, 2.0),
        Math.clamp(otherStrictness, 0.5, 2.0)
    );
}
```

This follows the existing pattern: `deriveCbrStrategy()` maps `ruleFollowing`, `deriveSocialCognition()` maps `socialOrient`.

### 5.2 DescriptorView dependency

`deriveAppraisalWeights` currently takes `List<WeightedTerm>` only. The new signature adds `DispositionAxes`. The `derive()` method in CognitiveDerivationEngine already receives `DescriptorView` which carries `DispositionAxes` — the plumbing is straightforward.

## 6. Testing Strategy

### 6.1 Unit tests — HeuristicActionAppraisalTest

- Self-appraisal: SUCCESS + positive goalRelevance → PRIDE
- Self-appraisal: FAILURE + negative goalRelevance → SHAME
- Other-appraisal: SUCCESS + positive goalRelevance → ADMIRATION (ATTRIBUTED source)
- Other-appraisal: FAILURE + negative goalRelevance → REPROACH (ATTRIBUTED source)
- Threshold: below threshold → no emotion
- Asymmetry: strict agent has low Shame threshold, high Pride threshold
- Compound: Pride + high goalRelevance → Pride + Gratification
- Compound: Shame + negative goalRelevance → Shame + Remorse
- Compound: Admiration + high goalRelevance → Admiration + Gratitude
- Compound: Reproach + negative goalRelevance → Reproach + Anger
- NEUTRAL outcome → no emotion
- goalRelevance = 0 → no emotion
- Relationship score modulation for other-appraisal

### 6.2 Unit tests — ActionAppraisalObserverTest

- Outcome event → ActionContext built correctly
- Non-Outcome event (Action, Observation) → ignored
- Self path: no TARGET_AGENT → self-appraisal only
- Other path: TARGET_AGENT present → both self and other appraisal
- Self-referential TARGET_AGENT (== agentId) → self-appraisal only
- ActionOutcome mapping: explicit metadata → used
- ActionOutcome mapping: confidence fallback → ≥0.7 SUCCESS, ≤0.3 FAILURE
- goalRelevance: max absolute value across goals
- Missing MindMapStore → graceful degradation (no-op)
- Missing ActionAppraisal → graceful degradation (no-op)

### 6.3 AppraisalWeights tests

- Existing tests updated for 5-arg constructor
- Derivation: ruleFollowing=strict → selfStrictness=1.6, otherStrictness=1.4
- Derivation: ruleFollowing=flexible → selfStrictness=0.7, otherStrictness=0.6
- Derivation: socialOrient=cooperative → otherStrictness reduced by 0.2
- Derivation: socialOrient=competitive → otherStrictness increased by 0.2
- Clamping: derived values stay in [0.5, 2.0]

### 6.4 Integration

- EmotionSource exhaustive switch coverage (compile-time enforcement of ATTRIBUTED handling)

## 7. Affected Existing Code

### 7.1 AppraisalWeights (mindmap-api)

Add two fields, update NEUTRAL constant, update compact constructor validation. Breaking change — all 3-arg constructors must become 5-arg.

### 7.2 EmotionSource (cognitive-api)

Add ATTRIBUTED value. Consumers with exhaustive switches will get compile errors — this is intentional and forces explicit handling.

### 7.3 ExperienceAttributeKeys (memory-api)

Add OUTCOME_STATUS constant.

### 7.4 CognitiveDerivationEngine (cognitive-index)

Extend `deriveAppraisalWeights` signature. Update `derive()` and `deriveAndMerge()` to pass `DispositionAxes`.

### 7.5 GoalAffectPhase (mindmap-intelligence)

Update AppraisalContext construction to use 5-arg AppraisalWeights constructor.

### 7.6 HeuristicGoalAppraisalTest (mindmap-intelligence)

Update test AppraisalWeights construction.

### 7.7 CognitiveDerivationEngineTest (cognitive-index)

Update test expectations for deriveAppraisalWeights.

## 8. Scope Boundaries

### In scope
- ActionAppraisal SPI + ActionContext + ActionOutcome in mindmap-api
- HeuristicActionAppraisal implementation in mindmap-intelligence
- ActionAppraisalObserver (real-time CDI observer) in mindmap-intelligence
- AppraisalWeights extension (2 new fields + derivation)
- EmotionSource.ATTRIBUTED
- ExperienceAttributeKeys.OUTCOME_STATUS
- Compound emotion detection (inline: Gratification, Remorse, Gratitude, Anger)
- Tests for all new types

### Out of scope
- ActionReconciliationPhase (cursor-based reconciliation for missed events) — deferred to follow-up
- Embedding-based goal matching for goalRelevance — deferred
- Norm-based standards (explicit norm nodes, moral norms, social conventions) — deferred
- Object-based emotions (Love/Hate) — separate OCC branch, separate issue
- Mood system integration beyond attention signals — blocks-layer concern
- LLM-based praiseworthiness evaluation — blocks-layer concern (CognitionCore)

## References

- HeuristicGoalAppraisal.java — existing goal-based appraisal pattern
- GoalAffectPhase.java — existing consolidation phase + AttentionSignal emission
- AppraisalWeights.java — existing weights record
- AppraisalContext.java — existing context record pattern
- CognitiveDerivationEngine.java — JPAF derivation for urgency/relationship/fear weights
- DispositionAxes.java — ruleFollowing/socialOrient axes
- EmotionType.java — PRIDE/SHAME/ADMIRATION/REPROACH/GRATIFICATION/REMORSE/GRATITUDE/ANGER already declared
- AlmaPadTable.java — PAD projections for all emotion types already present
- ExperienceEvent.java — Outcome sealed subtype
- RelationshipProcessor.java (memory-core) — Map.of() metadata evidence
- ExperienceAttributeKeys.java — TARGET_AGENT key
- Ortony, Clore & Collins (1988) — OCC emotion theory, Ch. 7 (standards and asymmetric sensitivity)

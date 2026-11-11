# Process Constraint Technique — Wider Eval Suite

**Issue:** casehubio/neocortex#933
**Branch:** issue-933-process-constraints-eval
**Date:** 2026-11-11

## Context

Issue #905 established that LLMs can simulate emotional states and exploration
style via prompt descriptions, but cannot simulate reduced cognitive capacity.
The process constraint technique — telling the model HOW to reason under
constraint rather than WHAT the character experiences — bridged the gap.
`SearchBudgetPromptSection.renderCapacityTrait()` went from failing to 90%
pass rate by replacing "low working memory" with procedural instructions like
"you can only hold two or three things in mind at once."

This spec applies the same technique to five failing eval test areas.

## Intervention 1: Cognitive Load Strategy (CognitiveLoadStrategyEvalTest)

**Files:** `EmotionRegulationGenerationPhase.buildUserMessage()`,
`CognitiveLoadStrategyEvalTest.SYSTEM`

**Current state:** The prompt says "Cognitive load constrains strategy: HIGH
load → prefer ATTENTIONAL_DEPLOYMENT or RESPONSE_MODULATION" — a descriptive
preference statement. The LLM ignores this and picks COGNITIVE_CHANGE anyway.

**Process constraint:** When `CognitiveLoadLevel` is HIGH, add to the user
message:

> Under HIGH cognitive load, you cannot hold the multi-step reasoning chain
> needed for COGNITIVE_CHANGE or the environmental assessment needed for
> SITUATION_SELECTION/MODIFICATION. These strategies require deliberation you
> don't have capacity for right now. Only ATTENTIONAL_DEPLOYMENT (automatic
> attention shift) and RESPONSE_MODULATION (expression control) are executable
> — they're reflexive, not deliberative. You MUST choose one of these two.

**Where it goes:** In `buildUserMessage()`, within the existing cognitive load
block (lines 451-457). When `loadEstimate.level() == CognitiveLoadLevel.HIGH`,
append the process constraint after the existing load description.

**Mirror in test:** Update `CognitiveLoadStrategyEvalTest.SYSTEM` to include
the same process constraint under the "Cognitive load constrains strategy"
section. The test's inline prompt must mirror the production constraint for
isolated validation.

## Intervention 2: Regulation Fatigue (PerModalityRegulationEvalTest)

**Files:** `EmotionRegulationGenerationPhase.buildUserMessage()`

**Current state:** Fatigue is rendered as "Regulation fatigue: 85% — repeated
regulation is depleting capacity." The LLM continues choosing COGNITIVE_CHANGE
even at extreme fatigue because the text is descriptive, not constraining.

**Process constraint:** When `regulationFatigue > 0.5`, replace the current
fatigue text with a graded process constraint:

- **0.5–0.7 (moderate depletion):** "Your reappraisal capacity is running low.
  COGNITIVE_CHANGE requires deliberate effort to find alternative
  interpretations — each attempt is slower and less convincing than the last.
  You can still try, but the cognitive work feels heavy. ATTENTIONAL_DEPLOYMENT
  and RESPONSE_MODULATION require less effort."

- **> 0.7 (severe depletion):** "Your reappraisal capacity is depleted. Trying
  to reframe the situation no longer works — the cognitive effort required for
  COGNITIVE_CHANGE has run dry. SITUATION_SELECTION requires environmental
  assessment you can't sustain. Only ATTENTIONAL_DEPLOYMENT remains as a
  regulation tool — shifting your focus is reflexive and doesn't require the
  cognitive resources you've exhausted. You MUST choose ATTENTIONAL_DEPLOYMENT."

**Note:** The programmatic safety gate
(`EmotionRegulationTickParticipant.SAFETY_FATIGUE_THRESHOLD = 0.7`) already
pins ATTENTIONAL_DEPLOYMENT at extreme fatigue. The process constraint makes
the LLM's own reasoning align with this gate, and also improves behavior in
the 0.5–0.7 range where the LLM still has agency.

## Intervention 3: Strategy Differentiation (PerStrategyRegulationEvalTest)

**Files:** `EmotionRegulationGenerationPhase.buildUserMessage()`

**Current state:** When the predictor falls through to LLM (no pinned
strategy), the prompt includes regulation capacities as numbers:
"reappraisal: strong (0.80)", "suppression: strong (0.80)". All five
strategies look equally available — the LLM defaults to COGNITIVE_CHANGE.

**Process constraint:** When `pinnedStrategy == null` and
`regulationDefaults != null`, identify the dominant regulation capacity and
render a personality-specific process constraint that describes what the
character's natural regulation process feels like:

Determine the dominant strategy from RegulationDefaults:
- If `suppressionCapacity` is the highest and ≥ 0.6 → RESPONSE_MODULATION
  tendency: "Your instinct is to control the outward expression. You feel the
  emotion fully inside but your face stays steady, your voice stays level. You
  manage the display, not the feeling. Choose RESPONSE_MODULATION."

- If `reappraisalCapacity` is the highest and ≥ 0.6 → COGNITIVE_CHANGE
  tendency: "Your instinct is to step back and reframe. You search for an
  alternative interpretation — why might this not mean what it first seemed?
  The reappraisal comes naturally. Choose COGNITIVE_CHANGE."

- If `redirectTendency` is the highest and ≥ 0.6 → ATTENTIONAL_DEPLOYMENT
  tendency: "Your instinct is to shift what you're focusing on. Not to leave,
  not to suppress — but to redirect attention away from the triggering
  stimulus. Choose ATTENTIONAL_DEPLOYMENT."

- If conflict mode is "avoidant" and the emotion is self-conscious (shame,
  remorse) → the existing avoidant-shame logic already handles this via
  SITUATION_SELECTION guidance (lines 577-596). No additional constraint needed.

**Interaction with existing temporal staging:** The existing temporal staging
block (lines 527-541) handles the case where controllable-negative emotions
meet high reappraisal capacity. The process constraint should NOT fire when
the temporal staging block already applies — check for
`isControllableNeg && regulationDefaults.reappraisalCapacity() >= 0.40`.

## Intervention 4: Drive Profile Rendering Fallback (DriveProfilePipelineTest)

**Files:** `CognitionObservationBuilder.renderInternalState()`

**Current state:** `renderInternalState()` builds drive text using
`readGeneratedDriveDescriptions()` which reads from `DriveDescriptionGenerated`
MindMap nodes. When no such nodes exist (common in early cognitive pipeline
states or test scenarios), the rendered output contains only labels like
"SCHEMING (0.9)" with no description text. `detectRenderedDrives()` checks for
the full description → always returns empty set.

**Fix:** In the `targetedDescriptionFor` lambda, fall back to
`td.drive().description()` when no generated description exists:

```java
if (generated == null) {
    generated = generatedDescriptions.get(d.type());
}
if (generated == null && d.description() != null && !d.description().isBlank()) {
    generated = d.description();
}
```

This is a code fix, not a process constraint. It ensures drive descriptions
render in all contexts — test, early pipeline, and production.

**Secondary concern:** If after this fix some scenarios still fail because the
appraisal filter removes drives (CAPS overlap below 0.15 threshold), we may
need to assess whether the `LlmSituationClassifier` needs process constraints
for better CAPS activation classification. This would be evaluated after the
rendering fix lands.

## Intervention 5: Pipeline Coherence (PipelineCoherenceEvalTest)

**Approach:** No dedicated intervention. Fix interventions 1-3 first, then
re-evaluate.

**Rationale:** The 3/4 coherence failures trace to the same regulation prompt
quality issues that interventions 1-3 address. The shame-regulation chain
produces incoherent results because regulation strategy selection doesn't match
the appraisal result. The curiosity-exploration chain may fail on
drive→channel_weight coherence, which is separate from regulation.

**Post-fix evaluation:** After implementing interventions 1-4, run the full
eval suite. Any remaining PipelineCoherenceEvalTest failures would indicate:
- Appraisal→regulation incoherence → specific process constraint needed
- Drive→channel_weight incoherence → SearchBudgetPromptSection adjustment
- Cross-tick trajectory incoherence → tick-to-tick context passing issue

## Implementation Order

1. Intervention 4 (drive rendering fallback) — pure code fix, no LLM dependency
2. Intervention 1 (cognitive load) — production + test prompt, simple constraint
3. Intervention 2 (fatigue) — production prompt, graded constraint
4. Intervention 3 (strategy differentiation) — production prompt, most complex
5. Intervention 5 assessment — re-evaluate coherence after 1-4

## Testing Strategy

Each intervention has a corresponding eval test that validates it:
- Intervention 1: `CognitiveLoadStrategyEvalTest` (2 tests, N=3 each)
- Intervention 2: `PerModalityRegulationEvalTest.fatigue_*` (1 test, N=3)
- Intervention 3: `PerStrategyRegulationEvalTest` (5 tests, N=3 each)
- Intervention 4: `DriveProfilePipelineTest` (12 parameterized scenarios)
- Intervention 5: `PipelineCoherenceEvalTest` (4 tests)

**Success criteria (from issue):** ≥80% of each eval test class passes.

Eval tests are tagged `@Tag("llm-eval")` and require Claude API access via
`EvalTestSupport.sessionPipeline()`. They are NOT part of the default build.

## References

- `SearchBudgetPromptSection.java:213-229` — proven process constraint pattern from #905
- `EmotionRegulationGenerationPhase.java` — regulation prompt assembly
- `EmotionRegulationTickParticipant.java:181-188` — safety gate thresholds
- `CognitionObservationBuilder.java:149-296` — drive rendering pipeline
- `DriveProfileDerivationPhase.java` — profile derivation (skips pinned profiles)
- Issue #905 — exploration + capacity eval calibration (established technique)
- Blog entry: "The Limitation That Wouldn't Limit" — technique documentation
- Milicka et al. (2024) — primed-by-corpus prompting research
- Petter et al. (2025) — cognitive load and emotion regulation strategy selection
- Gross (1998) — process model of emotion regulation (five strategies)

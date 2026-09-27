# Decisions — #383 Agent-based OCC Emotions

## D1: Overall architecture — Additive SPI with dual-trigger design

**Choice:** New `ActionAppraisal` SPI parallel to `GoalAppraisal`, with a dual-trigger observer (self-appraisal from Outcome events, other-appraisal from RelationshipRecorded events), inline compound detection, and a cursor-based reconciliation phase.
**Alternatives:**
- Unified Appraisal Framework — generic `CognitiveAppraisal<C>` base with GoalAppraisal and ActionAppraisal as specializations. Over-engineered for two specializations; generics complicate CDI injection; refactoring cost with no payoff.
- Event-Sourced Emotion Pipeline — EmotionProduced CDI events from all sources, downstream compound detector. Inline compound detection eliminates the coordination problem that motivates this; would require refactoring GoalAffectPhase (scope creep).
**Rationale:** Additive — no refactoring of existing code. Follows the established pattern (GoalAppraisal → HeuristicGoalAppraisal → GoalAffectPhase). Dual-trigger leverages the existing RelationshipEvent pipeline for other-appraisal rather than re-parsing ExperienceRecorded events.
**Trade-offs:** Two parallel appraisal SPIs with some structural similarity (both return `List<CognitiveEmotion>`). If a third appraisal branch (object-based Love/Hate) is added later, the event-sourced approach may become worth the refactoring.
**Sources:** HeuristicGoalAppraisal.java, GoalAffectPhase.java, RelationshipObserver (memory module), OCC theory (Ortony, Clore & Collins 1988)
**Exploration:** deep-analysis
**Status:** captured

## D2: ActionAppraisal SPI design

**Choice:** `@FunctionalInterface ActionAppraisal` in mindmap-api with signature `appraise(ActionContext) → List<CognitiveEmotion>`. ActionContext is a record carrying pre-computed inputs (not raw ExperienceEvent), keeping mindmap-api free of memory-api dependency.
**Alternatives:**
- Pass ExperienceEvent directly — creates dependency from mindmap-api on memory-api, breaking module tier structure.
- Sealed ActionInput hierarchy (SelfAction/ObservedAction) — type-safe self/other discrimination, but ActionContext with `isSelfAction()` accessor is simpler and sufficient.
**Rationale:** Decoupled record preserves the existing module boundary where mindmap-api is zero-dep on memory-api. The observer (in mindmap-intelligence, which already depends on both) builds ActionContext from the raw event. Single SPI with context-based discrimination is simpler than separate SPIs.
**Trade-offs:** The caller must build ActionContext correctly — praiseworthiness computation is split between the observer (goal relevance lookup) and the SPI (scoring + emotion mapping).
**Sources:** GoalAppraisal.java, AppraisalContext.java, ExperienceEvent.java, module dependency graph
**Exploration:** deep-analysis
**Status:** captured

## D3: ActionContext fields

**Choice:** Record with: `actingAgentId`, `apprasingAgentId`, `tenantId`, `turnId`, `actionDescription`, `capability` (nullable), `outcome` (ActionOutcome enum: SUCCESS/FAILURE/NEUTRAL), `goalRelevance` (double [-1, 1]), `moodBaseline` (PadProjection), `weights` (AppraisalWeights), `timestamp` (Instant). Includes `isSelfAction()` default method.
**Alternatives:**
- Minimal context (just praiseworthiness scalar + agent IDs) — too thin for the SPI to produce well-calibrated emotions; can't distinguish capability-based from goal-based praiseworthiness.
- Rich context with `Map<String, Double> goalRelevances` (per-goal) — more precise but heavier; per-goal iteration should happen in the observer, not the SPI.
**Rationale:** Provides enough signal for the heuristic implementation to compute praiseworthiness and detect compounds, without coupling to memory-api types. goalRelevance is pre-computed by the observer from MindMapStore goal lookups.
**Trade-offs:** goalRelevance as a single scalar loses per-goal granularity. An action that advances goal A but harms goal B produces a net relevance that may mask the individual signals. Acceptable for v1.
**Sources:** AppraisalContext.java (existing pattern), ExperienceAttributeKeys.java
**Exploration:** deep-analysis
**Status:** captured

## D4: AppraisalWeights extension

**Choice:** Extend existing `AppraisalWeights` record with two new fields: `selfStandardsStrictness` (double, [0.5, 2.0]) and `otherStandardsStrictness` (double, [0.5, 2.0]). Default both to 1.0 in `NEUTRAL`. Derive from personality via CognitiveDerivationEngine (conscientiousness → high self-strictness, agreeableness → low other-strictness).
**Alternatives:**
- Separate `ActionAppraisalWeights` record — avoids breaking the 3-arg constructor, but fragments weight configuration across two records when they're naturally part of one personality profile.
**Rationale:** Pre-release project — constructor breakage is acceptable. CognitiveDerivationEngine already derives urgencyWeight/relationshipWeight/fearOnsetThreshold from disposition profile; adding two more fields is a natural extension of the same JPAF pathway.
**Trade-offs:** Breaking change to existing AppraisalWeights constructors. All callers (GoalAffectPhase, tests, CognitiveDerivationEngine) need updating.
**Depends on:** D2 (ActionContext carries AppraisalWeights)
**Sources:** AppraisalWeights.java, CognitiveDerivationEngine.java (deriveAppraisalWeights method)
**Exploration:** quick
**Status:** captured

## D5: Trigger design — self via Outcome, other via RelationshipRecorded

**Choice:** Single `ActionAppraisalObserver` with two CDI observer methods: (1) `@Observes ExperienceRecorded` filtering for Outcome events where actingAgent == apprasingAgent → self-appraisal (Pride/Shame), (2) `@Observes RelationshipRecorded` using QualitySignal as praiseworthiness baseline → other-appraisal (Admiration/Reproach).
**Alternatives:**
- Observe only ExperienceRecorded for both paths — would need to re-derive target-agent and quality signal, duplicating RelationshipObserver's logic.
- Separate observer classes per trigger — cleaner separation but unnecessary; a single class with two observer methods is idiomatic CDI.
**Rationale:** Leverages existing RelationshipEvent pipeline. QualitySignal (POSITIVE/NEGATIVE/NEUTRAL) is already a praiseworthiness signal — no need to re-derive it. Self-appraisal triggers on Outcome (not Action) because that's when the result is known.
**Trade-offs:** Other-appraisal depends on RelationshipObserver having already fired and recorded the event. CDI observer ordering is not guaranteed, but RelationshipRecorded fires from RelationshipObserver's ExperienceRecorded handler — so the appraisal observer sees it in the correct sequence.
**Depends on:** D1 (dual-trigger architecture)
**Sources:** RelationshipObserver.java (memory module), RelationshipRecorded.java, ExperienceRecorded.java
**Exploration:** deep-analysis
**Status:** captured

## D6: Praiseworthiness heuristics

**Choice:** Goal-derived base with personality modulation. Praiseworthiness = `outcomePolarity * |goalRelevance|`. Threshold = `0.2 / standardsStrictness` (strict agents have lower thresholds). Intensity = `clamp(|praiseworthiness| * standardsStrictness)`. For other-appraisal, `praiseworthiness *= relationshipScore` (stronger relationships produce stronger emotions).
**Alternatives:**
- Flat threshold (no personality modulation) — simpler but ignores the "layered standards" decision.
- Embedding-based goal matching for goalRelevance — most accurate but heavyweight; defer to future enhancement.
**Rationale:** Mirrors the structure of HeuristicGoalAppraisal (which uses similar clamping and threshold patterns). Strict agents feel Shame more easily and Pride less easily — consistent with OCC theory where high standards produce asymmetric sensitivity. relationshipScore reuses existing AppraisalContext infrastructure.
**Trade-offs:** Heuristic — not empirically calibrated. The 0.2 base threshold and linear scaling are starting points that will need tuning.
**Depends on:** D3 (ActionContext provides goalRelevance), D4 (AppraisalWeights provides strictness)
**Sources:** HeuristicGoalAppraisal.java (clamping/threshold patterns), AlmaPadTable.java (PAD projections)
**Exploration:** deep-analysis
**Status:** captured

## D7: Compound emission strategy

**Choice:** Detect compounds inline within HeuristicActionAppraisal by inferring co-occurring prospect emotions from the same inputs. Produce BOTH the base agent emotion (Pride/Shame/Admiration/Reproach) AND the compound (Gratification/Remorse/Gratitude/Anger). Compound condition: base emotion produced AND `|goalRelevance| > 0.3` AND outcome aligns with prospect direction (success + positive relevance → Joy inference → Gratification; failure + negative relevance → Distress inference → Anger/Remorse).
**Alternatives:**
- Separate CompoundEmotionDetector phase — requires cross-phase emotion state sharing; introduces coordination complexity.
- Produce compound only, suppress base — OCC-theoretically cleaner but loses the ability to track agent-based and prospect-based affect independently.
**Rationale:** The compound conditions are derivable from ActionContext alone — no need to observe GoalAffectPhase output. Emitting both base and compound preserves independent affect dimensions. PAD accumulation (dominant emotion wins) handles overlap naturally.
**Trade-offs:** GoalAffectPhase may independently produce the prospect emotion (Joy/Distress) for the same goal state change, creating apparent duplication. This is acceptable — multiple co-occurring emotions are more realistic than artificial deduplication, and the dominant-emotion PAD selection handles it.
**Depends on:** D6 (praiseworthiness heuristics produce base emotions), D3 (ActionContext carries goalRelevance and outcome)
**Sources:** EmotionType.java (compound types already declared), AlmaPadTable.java (compound PAD projections exist)
**Exploration:** deep-analysis
**Status:** captured

## D8: Standards source — layered goal + personality

**Choice:** Goal-derived base with personality modulation (from clarifying questions). Praiseworthiness is computed from goal relevance; personality's standardsStrictness modulates thresholds asymmetrically (strict → easier Shame/Reproach, harder Pride/Admiration).
**Alternatives:**
- Goal-derived only — misses personality dimension.
- Personality-derived only — requires a StandardsProvider SPI without clear semantics in our system.
- Explicit norm nodes in mindmap — heavyweight, no existing infrastructure.
**Rationale:** Goals are concrete and observable. Personality modulation adds individual differences without new infrastructure. The JPAF derivation pathway from #382 already exists — extending it is natural.
**Trade-offs:** Standards are implicitly goal-adherence rather than explicit norms. Actions unrelated to any goal produce no agent-based emotions. This is acceptable for v1 — goalless actions are likely low-stakes.
**Sources:** CognitiveDerivationEngine.java (#382 JPAF pathway), GoalAppraisal.java (goal-centric pattern)
**Exploration:** quick
**Status:** captured

## D9: EmotionSource reuse

**Choice:** Keep existing INTRINSIC/EMPATHIC enum values. Pride/Shame use INTRINSIC (about self). Admiration/Reproach use EMPATHIC (about others). No new enum values.
**Alternatives:**
- Add SELF_ATTRIBUTED/OTHER_ATTRIBUTED — more precise semantics (Admiration is judgment, not empathy), but breaks consumers that switch on EmotionSource.
**Rationale:** INTRINSIC/EMPATHIC captures the self/other split adequately. The emotion TYPE already distinguishes Pride from Admiration — the source doesn't need to carry that information too. Avoids changing a public API enum.
**Trade-offs:** Semantic overloading — EMPATHIC now covers both empathy (Pity) and judgment (Admiration/Reproach). Acceptable because the distinction is carried by EmotionType.
**Sources:** EmotionSource.java, CognitiveEmotion.java
**Exploration:** quick
**Status:** captured

## D10: Compound co-occurrence window

**Choice:** Same turnId. If the base agent emotion and the inferred prospect emotion share the same turnId, they compound. Deterministic, uses existing turnId linkage.
**Alternatives:**
- Time window (configurable duration) — more flexible but needs buffer/accumulator.
- Same consolidation tick — only works for phase-produced emotions, not real-time.
**Rationale:** turnId is already present on all ExperienceEvents and in ActionContext. Same-turn is the natural boundary for "this action produced this outcome." No buffering or timing logic needed.
**Trade-offs:** Actions whose outcomes span multiple turns (long-running processes) won't compound. Acceptable — compounds represent immediate co-occurrence.
**Sources:** ExperienceEvent.java (turnId field), ExperienceAttributeKeys.java
**Exploration:** quick
**Status:** captured

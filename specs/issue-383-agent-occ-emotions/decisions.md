# Decisions — #383 Agent-based OCC Emotions

## D1: Overall architecture — Additive SPI with dual-trigger design

**Choice:** New `ActionAppraisal` SPI parallel to `GoalAppraisal`, with a single-trigger observer (`@Observes ExperienceRecorded`) providing dual-path logic (self-appraisal and other-appraisal from the same event source), inline compound detection, and deferred cursor-based reconciliation for missed-event recovery.
**Alternatives:**
- Unified Appraisal Framework — generic `CognitiveAppraisal<C>` base with GoalAppraisal and ActionAppraisal as specializations. Over-engineered for two specializations; generics complicate CDI injection; refactoring cost with no payoff.
- Event-Sourced Emotion Pipeline — EmotionProduced CDI events from all sources, downstream compound detector. Inline compound detection eliminates the coordination problem that motivates this; would require refactoring GoalAffectPhase (scope creep).
- Dual-trigger observer (self from ExperienceRecorded, other from RelationshipRecorded) — originally chosen, but RelationshipRecorded loses structured fields (capability, result, metadata) that are needed for goal-relevance computation. Single trigger from ExperienceRecorded gives both paths access to the full Outcome record.
**Rationale:** Additive — no refactoring of existing code. Follows the established pattern (GoalAppraisal → HeuristicGoalAppraisal → GoalAffectPhase). Single-trigger observer uses ExperienceRecorded for both paths, giving both access to the full Outcome record (capability, result, metadata) needed for structured goal-relevance lookup.
**Trade-offs:** Two parallel appraisal SPIs with some structural similarity (both return `List<CognitiveEmotion>`). If a third appraisal branch (object-based Love/Hate) is added later, the event-sourced approach may become worth the refactoring.
**Sources:** HeuristicGoalAppraisal.java, GoalAffectPhase.java, RelationshipProcessor (memory-core module), OCC theory (Ortony, Clore & Collins 1988)
**Exploration:** deep-analysis → revised after review (R2-02)
**Status:** revised — changed from dual-trigger to single-trigger observer; dual-trigger dropped because RelationshipRecorded loses structured data needed for goal-relevance computation

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

**Choice:** Extend existing `AppraisalWeights` record with two new fields: `selfStandardsStrictness` (double, [0.5, 2.0]) and `otherStandardsStrictness` (double, [0.5, 2.0]). Default both to 1.0 in `NEUTRAL`. Derive from DispositionAxes: `ruleFollowing: strict` → high selfStandardsStrictness (1.6) and high otherStandardsStrictness (1.4); `ruleFollowing: flexible` → low selfStandardsStrictness (0.7) and low otherStandardsStrictness (0.6); `socialOrient: cooperative` → lower otherStandardsStrictness (−0.2 modifier, more forgiving); `socialOrient: competitive` → higher otherStandardsStrictness (+0.2 modifier, judges others harshly). Derived values are clamped to [0.5, 2.0] after applying all modifiers, consistent with AppraisalWeights' compact constructor validation. The `deriveAppraisalWeights` method takes both `List<WeightedTerm> profile` (for existing urgency/relationship/fear fields) and `DispositionAxes axes` (for new standards fields).
**Alternatives:**
- Separate `ActionAppraisalWeights` record — avoids breaking the 3-arg constructor, but fragments weight configuration across two records when they're naturally part of one personality profile.
- Derive from Big Five traits (conscientiousness → self-strictness, agreeableness → other-strictness) — only works for Big Five agents; silently produces no derivation for JPAF agents, the dominant framework. DispositionAxes are framework-agnostic.
- Derive from JPAF functions via dispositionProfile — possible as supplementary pathway but lacks the direct semantic mapping that DispositionAxes provides for standards-related behavior.
**Rationale:** DispositionAxes are the correct derivation source for standards-related weights, following the same pattern as `deriveCbrStrategy()` (which maps `ruleFollowing`) and `deriveSocialCognition()` (which maps `socialOrient`). All agents have DispositionAxes regardless of personality framework.
**Trade-offs:** Breaking change to existing AppraisalWeights constructors. All callers (GoalAffectPhase, tests, CognitiveDerivationEngine) need updating. The `deriveAppraisalWeights` method signature changes from `(List<WeightedTerm>)` to `(List<WeightedTerm>, DispositionAxes)`.
**Depends on:** D2 (ActionContext carries AppraisalWeights)
**Sources:** AppraisalWeights.java, CognitiveDerivationEngine.java (deriveAppraisalWeights, deriveCbrStrategy, deriveSocialCognition methods), DispositionAxes.java
**Exploration:** quick → revised after review (R1-03, R2-03)
**Status:** revised — changed derivation source from Big Five traits to DispositionAxes; added Big Five and JPAF as rejected alternatives; added post-modifier clamping to [0.5, 2.0]

## D5: Trigger design — single ExperienceRecorded trigger, dual-path logic

**Choice:** Single `ActionAppraisalObserver` with one CDI observer method: `@Observes ExperienceRecorded`, filtering for `Outcome` events. Two paths within the same handler:
- **Self-appraisal (Pride/Shame):** `Outcome.agentId() == apprasingAgentId` — the appraising agent's own action produced this outcome.
- **Other-appraisal (Admiration/Reproach):** `metadata.get(ExperienceAttributeKeys.TARGET_AGENT)` present and differs from `agentId` — another agent was involved in this outcome.

Both paths have access to the full `Outcome` record: `capability`, `result`, `confidence`, and `metadata`. Goal relevance is computed identically for both paths — the observer looks up the appraising agent's goals in MindMapStore and matches the outcome's `capability` against goal-linked capabilities. The difference is which `standardsStrictness` is applied (self vs other) and that other-appraisal is modulated by relationship score.
**Alternatives:**
- Use QualitySignal from RelationshipEvent as praiseworthiness baseline — QualitySignal is always NEUTRAL in the current codebase (RelationshipProcessor hardcodes it at line 40 with `Map.of()`). The blocks-layer CognitionCore.deriveQualitySignal() produces non-NEUTRAL signals but that's LLM-based and in a higher module tier.
- Dual-trigger observer (self from ExperienceRecorded, other from RelationshipRecorded) — `RelationshipProcessor` constructs `RelationshipEvent` with `Map.of()` as metadata, losing the `capability` and `result` fields from the original `Outcome`. Without these structured fields, goal-relevance computation for other-appraisal degrades to NLU on free-text `description` — which the mindmap-intelligence tier cannot do.
- Separate observer classes per path — cleaner separation but unnecessary; dual-path logic within a single handler is straightforward (one TARGET_AGENT check).
**Rationale:** Single trigger from ExperienceRecorded gives both paths access to the full Outcome record. The TARGET_AGENT metadata check (`metadata.get(TARGET_AGENT)`) is a single-line operation — not a meaningful duplication of RelationshipProcessor's logic. RelationshipProcessor continues to handle relationship memory storage independently; the ActionAppraisalObserver handles emotion appraisal independently. Each observer has its own concern.
**Trade-offs:** The observer now handles both paths in one method, which is slightly more complex than two separate observer methods. But the alternative (dual-trigger) loses data that makes other-appraisal non-functional.
**Depends on:** D1 (architecture)
**Sources:** RelationshipProcessor.java (memory-core, line 41 — `Map.of()` evidence), Outcome.java (capability/result fields), ExperienceAttributeKeys.java (TARGET_AGENT key), ExperienceRecorded.java
**Exploration:** deep-analysis → revised R1-02, revised R2-02
**Status:** revised — changed from dual-trigger (ExperienceRecorded + RelationshipRecorded) to single-trigger (ExperienceRecorded only); RelationshipRecorded loses structured data needed for goal-relevance computation

## D6: Praiseworthiness heuristics

**Choice:** Goal-derived base with personality modulation and valence-dependent asymmetry. Praiseworthiness = `outcomePolarity * |goalRelevance|`. Asymmetric thresholds by valence:
- Negative emotions (Shame/Reproach): threshold = `0.2 / standardsStrictness` (strict → low bar → easy trigger)
- Positive emotions (Pride/Admiration): threshold = `0.2 * standardsStrictness` (strict → high bar → hard trigger)

Asymmetric intensity by valence:
- Negative: intensity = `clamp(|praiseworthiness| * standardsStrictness)` (amplified)
- Positive: intensity = `clamp(|praiseworthiness| / standardsStrictness)` (dampened)

For other-appraisal, `praiseworthiness *= relationshipScore` (stronger relationships produce stronger emotions).
**Alternatives:**
- Symmetric formula (single threshold/intensity formula for all valences) — simpler but violates OCC theory where high standards produce asymmetric sensitivity: strict agents should feel more Shame and less Pride.
- Flat threshold (no personality modulation) — simpler but ignores the "layered standards" decision.
- Embedding-based goal matching for goalRelevance — most accurate but heavyweight; defer to future enhancement.
**Rationale:** Implements the OCC-correct asymmetry where strict agents have lower thresholds for negative self-assessment emotions and higher thresholds for positive ones. A strict agent (selfStandardsStrictness = 2.0) has threshold 0.1 for Shame but 0.4 for Pride — small failures trigger Shame easily while only significant achievements trigger Pride. This mirrors HeuristicGoalAppraisal's structurally different intensity computations for Hope vs Fear.
**Trade-offs:** Heuristic — not empirically calibrated. The 0.2 base threshold and linear scaling are starting points that will need tuning. The asymmetry factor is a direct function of standardsStrictness — more complex models (e.g., logarithmic scaling) could provide better calibration.
**Depends on:** D3 (ActionContext provides goalRelevance), D4 (AppraisalWeights provides strictness)
**Sources:** HeuristicGoalAppraisal.java (structurally different Hope vs Fear computations), AlmaPadTable.java (PAD projections), OCC theory (Ortony, Clore & Collins 1988, Ch. 7 — standards and asymmetric sensitivity)
**Exploration:** deep-analysis → revised after review (R1-04)
**Status:** revised — replaced symmetric formula with valence-dependent asymmetric thresholds and intensity modifiers

## D7: Compound emission strategy

**Choice:** Detect compounds inline within HeuristicActionAppraisal by inferring co-occurring prospect emotions from the same inputs. Produce BOTH the base agent emotion (Pride/Shame/Admiration/Reproach) AND the compound (Gratification/Remorse/Gratitude/Anger). Compound condition: base emotion produced AND `|goalRelevance| > 0.3` AND outcome aligns with prospect direction (success + positive relevance → Joy inference → Gratification; failure + negative relevance → Distress inference → Anger/Remorse).
**Alternatives:**
- Separate CompoundEmotionDetector phase — requires cross-phase emotion state sharing; introduces coordination complexity.
- Produce compound only, suppress base — OCC-theoretically cleaner but loses the ability to track agent-based and prospect-based affect independently.
**Rationale:** The compound conditions are derivable from ActionContext alone — no need to observe GoalAffectPhase output. Emitting both base and compound preserves independent affect dimensions. In OCC theory, multiple emotions genuinely co-occur: Joy (prospect-based: "this goal was achieved") and Gratification (compound: "my actions achieved this goal") are distinct emotional responses. Their combined mood impact is intentional, not redundant.
**Trade-offs:** GoalAffectPhase may independently produce the prospect emotion (Joy/Distress) for the same goal state change. Both emotions flow through the attention/mood pipeline — this is the intended OCC model (concurrent emotions) not double-counting. Intensity calibration across paths may need tuning (see D15).
**Depends on:** D6 (praiseworthiness heuristics produce base emotions), D3 (ActionContext carries goalRelevance and outcome)
**Sources:** EmotionType.java (compound types already declared), AlmaPadTable.java (compound PAD projections exist), OCC theory (Ortony, Clore & Collins 1988, compound emotions)
**Exploration:** deep-analysis
**Status:** captured

## D8: Standards source — layered goal + personality

**Choice:** Goal-derived base with personality modulation (from clarifying questions). Praiseworthiness is computed from goal relevance; personality's standardsStrictness modulates thresholds asymmetrically (strict → easier Shame/Reproach, harder Pride/Admiration).
**Alternatives:**
- Goal-derived only — misses personality dimension.
- Personality-derived only — requires a StandardsProvider SPI without clear semantics in our system.
- Explicit norm nodes in mindmap — heavyweight, no existing infrastructure.
**Rationale:** Goals are concrete and observable. Personality modulation adds individual differences without new infrastructure. The JPAF derivation pathway from #382 already exists — extending it is natural.
**Trade-offs:** Standards are implicitly goal-adherence rather than explicit norms. Actions unrelated to any goal produce no agent-based emotions. This is a structural limitation of v1 — norm-based standards (moral norms, social conventions, behavioral expectations) are part of OCC's standards variable but require infrastructure that does not exist yet. The ActionAppraisal SPI is the natural extension point: a future NormAppraisal SPI or an enriched ActionContext with norm-violation signals can add norm-based emotions without changing the existing goal-based pathway.
**Sources:** CognitiveDerivationEngine.java (#382 JPAF pathway), GoalAppraisal.java (goal-centric pattern)
**Exploration:** quick
**Status:** captured

## D9: EmotionSource extension

**Choice:** Add `ATTRIBUTED` to EmotionSource enum. Pride/Shame use INTRINSIC (self-appraisal — about one's own actions). Admiration/Reproach use ATTRIBUTED (other-appraisal — judgment of another agent's actions against standards). Empathy-based emotions (Pity, Happy-for, Gloating, Resentment) continue to use EMPATHIC.
**Alternatives:**
- Reuse existing INTRINSIC/EMPATHIC — EMPATHIC captures the self/other split, but conflates two fundamentally different OCC appraisal processes: empathy ("what happened to them?" — affect contagion) and attribution ("what did they do?" — judgment of responsibility). Downstream consumers switching on EmotionSource would get Reproach in the empathic bucket.
- Add SELF_ATTRIBUTED/OTHER_ATTRIBUTED — more granular but unnecessary; the self/other split is already carried by the emotion TYPE (Pride vs Admiration).
**Rationale:** In OCC theory, empathy-based and attribution-based emotions arise from fundamentally different appraisal processes. A consumer asking "show me all empathic responses" should not see Reproach (a moral judgment). The cost of a new enum value is one exhaustive-switch compile error per consumer — the design philosophy says "Cost is always worth paying" and the backward-compatibility concern that originally motivated EMPATHIC reuse is exactly the thinking the design philosophy rejects.
**Trade-offs:** Exhaustive switch statements on EmotionSource will require a new case. This is mechanical and desirable — it forces every consumer to explicitly handle attribution-based emotions.
**Sources:** EmotionSource.java, CognitiveEmotion.java, OCC theory (Ortony, Clore & Collins 1988, Ch. 1 — emotion taxonomy)
**Exploration:** quick → revised after review (R1-06)
**Status:** revised — replaced EMPATHIC reuse with new ATTRIBUTED enum value; semantic correctness over backward compatibility

## D10: Compound co-occurrence window

**Choice:** Same turnId. If the base agent emotion and the inferred prospect emotion share the same turnId, they compound. Deterministic, uses existing turnId linkage.
**Alternatives:**
- Time window (configurable duration) — more flexible but needs buffer/accumulator.
- Same consolidation tick — only works for phase-produced emotions, not real-time.
**Rationale:** turnId is already present on all ExperienceEvents and in ActionContext. Same-turn is the natural boundary for "this action produced this outcome." No buffering or timing logic needed. Since compound detection is inline (D7) — both the base emotion and the inferred prospect emotion are derived from the same ActionContext — they trivially share turnId. The co-occurrence window applies only to the inline inference within HeuristicActionAppraisal, not to cross-phase correlation with GoalAffectPhase.
**Trade-offs:** Actions whose outcomes span multiple turns (long-running processes) won't compound. Acceptable — compounds represent immediate co-occurrence.
**Sources:** ExperienceEvent.java (turnId field), ExperienceAttributeKeys.java
**Exploration:** quick
**Status:** captured

## D11: Execution model — real-time CDI observer

**Choice:** ActionAppraisalObserver is a CDI `@Observes` event handler that fires in real-time on ExperienceRecorded events, not a ConsolidationPhase.
**Alternatives:**
- ConsolidationPhase (batch, tick-driven) — would batch-process action appraisals like GoalAffectPhase. But goal appraisal is naturally batch (iterate all goals per tick) while action appraisal is naturally event-driven (respond to a specific action's outcome). Batching would delay emotional response to actions until the next consolidation tick and require event buffering.
- Hybrid (real-time with consolidation fallback) — the cursor-based reconciliation phase mentioned in D1 can serve as a future catch-up mechanism for missed events, but the primary path is real-time.
**Rationale:** Actions produce emotions in real-time because that's when the event happens — an agent should feel Pride immediately upon achieving a positive outcome, not on the next consolidation tick. This follows the existing pattern of SignificanceAccumulator (CDI @Observes ExperienceRecorded, fires in real-time). The observer runs in whatever thread fires the CDI event; Quarkus CDI synchronous observers are single-threaded per event, so there is no concurrent execution within a single event dispatch.
**Trade-offs:**
- Thread context: the observer runs in the event producer's thread, not the consolidation scheduler's thread. This is acceptable because the observer's work is lightweight (goal lookup + heuristic computation + emotion production).
- PAD write contention: the observer does NOT write PAD directly — it produces CognitiveEmotion records that flow through the attention/mood pipeline (see D15). GoalAffectPhase writes PAD to goal nodes; the observer writes to a different target or emits emotions for downstream consumption. No direct write contention.
- Ordering: CDI synchronous observers fire in undefined order. Both ActionAppraisalObserver and RelationshipProcessor observe ExperienceRecorded, so their execution order within a single event dispatch is non-deterministic. This is acceptable because they have independent concerns — RelationshipProcessor handles relationship memory storage, ActionAppraisalObserver handles emotion appraisal — and neither depends on the other's output.
**Depends on:** D1 (dual-trigger architecture), D5 (trigger design)
**Sources:** SignificanceAccumulator.java (@Observes ExperienceRecorded pattern), MemoryBeans.java (CDI event wiring), GoalAffectPhase.java (ConsolidationPhase pattern for contrast)
**Exploration:** surfaced by review (R1-09)
**Status:** captured

## D12: ActionOutcome mapping from Outcome.result()

**Choice:** The observer maps `Outcome.result()` (free-text String) to `ActionOutcome` (SUCCESS/FAILURE/NEUTRAL) using a two-stage strategy: (1) check `Outcome.metadata()` for an explicit `ExperienceAttributeKeys.OUTCOME_STATUS` key — if present, map directly; (2) if absent, use `Outcome.confidence()` as a proxy: confidence ≥ 0.7 → SUCCESS, confidence ≤ 0.3 → FAILURE, else NEUTRAL. The `Outcome.result()` text is NOT parsed for keywords — it's free-form and unreliable for classification.
**Alternatives:**
- Pattern matching on result text ("success", "failed", etc.) — brittle, language-dependent, breaks with domain-specific result descriptions.
- Always require explicit metadata — would require updating all Outcome event producers, adding scope.
- Infer from capability completion — possible for capability-tracked actions but not all actions have capabilities.
**Rationale:** Confidence is a reliable numeric signal that the event producer already has context to compute. The metadata key provides an explicit override for producers that want precision. The two-stage approach degrades gracefully — most producers set confidence, and those that want explicit control can add the metadata key.
**Trade-offs:** The confidence thresholds (0.7/0.3) are heuristic and may need calibration. Events without confidence AND without metadata fall to NEUTRAL, producing no praiseworthiness signal — this is the safe default.
**Depends on:** D3 (ActionContext.outcome field), D5 (observer builds ActionContext)
**Sources:** Outcome.java (result/confidence/metadata fields), ExperienceAttributeKeys.java
**Exploration:** surfaced by review (R1-10)
**Status:** captured

## D13: Module placement — mindmap-intelligence

**Choice:** ActionAppraisalObserver lives in `mindmap-intelligence`.
**Alternatives:**
- memory-core — wrong tier; memory modules don't depend on mindmap-api.
- cognitive-index — wrong responsibility; cognitive-index does derivation, not event processing.
- A new module (e.g., emotion-runtime) — unnecessary; mindmap-intelligence already has the right dependencies and patterns.
**Rationale:** mindmap-intelligence already depends on both mindmap-api (for ActionAppraisal SPI, AppraisalWeights, MindMapStore) and memory-api (for ExperienceRecorded, Outcome). It uses Quarkus CDI (`quarkus-arc`) for ConsolidationPhases and event observation. Adding a CDI observer is consistent with the existing module patterns (GoalAffectPhase, SignificanceAccumulator are both in mindmap-intelligence).
**Trade-offs:** None significant. The module already has the correct dependency graph.
**Depends on:** D1 (architecture), D2 (SPI in mindmap-api)
**Sources:** mindmap-intelligence/pom.xml (dependencies), GoalAffectPhase.java, SignificanceAccumulator.java (existing patterns in the module)
**Exploration:** surfaced by review (R1-13)
**Status:** captured

## D14: goalRelevance aggregation — max absolute value

**Choice:** The observer iterates all active goals in MindMapStore for the appraising agent, computes per-goal relevance (how the action/outcome relates to each goal), and uses the maximum absolute value as the scalar `goalRelevance` on ActionContext. The sign follows the max-magnitude goal's alignment (positive = advances goal, negative = hinders goal).
**Alternatives:**
- Average across goals — dilutes strong signals; an action that strongly advances one goal but is irrelevant to five others produces a weak average.
- Weighted sum — requires per-goal weighting (priority-based), adding complexity without clear benefit for v1.
- Per-goal map on ActionContext — most precise but rejected in D3 (per-goal iteration belongs in the observer, not the SPI).
**Rationale:** Max absolute value preserves the strongest goal signal, which is the most emotionally salient. An agent feels Pride primarily because of the most relevant goal, not because of the average across all goals. This is consistent with OCC theory where the most relevant concern dominates the emotional response.
**Trade-offs:** An action that advances goal A (+0.8) but significantly hinders goal B (−0.7) produces goalRelevance = +0.8 (the max), losing the conflicting signal. This is acceptable for v1 — conflicting goal signals are an edge case that could be addressed with a richer ActionContext (per-goal map) in a future version.
**Depends on:** D3 (ActionContext.goalRelevance field), D5 (observer builds ActionContext)
**Sources:** AppraisalContext.java (existing pattern — surfacing count as scalar from per-goal data), GoalAffectPhase.java (iterates goal nodes)
**Exploration:** surfaced by review (R1-14)
**Status:** captured

## D15: Cross-path emotion integration — concurrent emotions, attention-mediated

**Choice:** Action-appraisal emotions (from ActionAppraisalObserver) and goal-appraisal emotions (from GoalAffectPhase) flow through the same attention signal pipeline. The observer emits `AttentionSignal`s (category: AFFECT_CHANGE) for produced emotions, following GoalAffectPhase's existing pattern. The downstream mood system (MoodOrchestrator in blocks) receives attention signals from both paths and applies its own emotion integration — multiple concurrent emotions are the intended OCC model, not a deduplication target.
**Alternatives:**
- Coordination protocol (processed marker) — the action appraisal path marks events so GoalAffectPhase skips them. Introduces cross-path coupling and loses the independent emotion perspective.
- Max-merge across paths — the mood system picks the highest-intensity emotion across both paths. Suppresses valid concurrent emotions.
- Additive PAD merge — accumulates PAD from both paths. Risks unbounded mood shifts.
**Rationale:** In OCC theory, multiple emotions genuinely co-occur. Joy (prospect-based) and Gratification (compound) are distinct emotional responses to the same event — their combined mood impact is greater than either alone, and this is correct. GoalAffectPhase writes PAD to GOAL NODES (reflecting the goal's emotional state), not to the agent's mood directly. The ActionAppraisalObserver produces emotions that flow through attention signals to the mood system. There is no direct PAD write contention because they target different nodes/systems. The mood system (which is in the blocks layer, outside this spec's scope) is responsible for integrating attention signals from multiple sources — it already handles signals from multiple ConsolidationPhases.
**Trade-offs:** Total mood impact from a single event may be higher than from either path alone. Intensity calibration (D6's base threshold and HeuristicGoalAppraisal's existing thresholds) should be tuned to produce reasonable combined mood shifts. If calibration proves insufficient, the mood system can apply cross-signal dampening — but this is a blocks-layer concern, not a mindmap-intelligence concern.
**Depends on:** D7 (compound emission), D11 (real-time observer), D1 (architecture)
**Sources:** GoalAffectPhase.java (AttentionSignal emission pattern), SignificanceAccumulator.java (attention pipeline), MoodOrchestrator (blocks layer — downstream consumer)
**Exploration:** surfaced by review (R1-05, R1-15)
**Status:** captured

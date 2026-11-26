# Decisions — SE7: Orchestrators & Higher Cognition (#1227)

## D1: Fix E5 relational-schema trust with cursor (not remove)

**Choice:** Add cursor tracking to relational-schema trust re-integration
**Alternatives:**
- Remove/disable trust re-integration as dead code — simpler but loses the work when valence is wired
**Rationale:** The cursor bug is a correctness issue that will bite when valence is eventually wired. Fixing dormant code is cheapest when there's no production data to migrate.
**Trade-offs:** Maintaining code that has no current effect. Low cost — cursor pattern already established elsewhere.
**Sources:** `cognition/…/relationship/RelationalSchemaEvolutionPhase.java:120-122`
**Exploration:** quick
**Status:** captured

## D2: E8 retention formula — first-principles redesign

**Choice:** Base score = weighted average of recency + retrieval strength. Confidence × trust applied as multiplicative modifiers. Optional additive boost from goal relevance and emotional significance.
**Alternatives:**
- Remove constant terms only — quick fix but doesn't address the structural error (additive terms that inflate when uninformative)
- Lower constants to 0.0 — masks the problem without fixing the formula's design
**Rationale:** First principles: a signal with no information should have no effect, not inflate the score. Additive terms that default to 1.0 create a floor. As multipliers, confidence and trust are identity (×1.0) when unset and can only suppress when real values arrive. Base score uses only signals that always carry real information (recency, retrieval strength).
**Trade-offs:** Memories will now actually be evicted — agents with large memory stores will see consolidation and eviction for the first time. Need to verify the adaptive hygiene phase (HygieneAdaptationPhase) handles the transition gracefully.
**Sources:** `cognition-api/…/memory/RetentionScore.java:14-27`, `cognition/…/memory/MemoryHygieneOrchestratorImpl.java:140-148`, RetentionConfig, GoalRelevanceModulationFactor, RetrievalStrength (Bjork dual-strength model)
**Exploration:** deep-analysis (first principles)
**Status:** captured

## D3: E10d goal surfacing — record nothing

**Choice:** Remove both `recordSurfacing()` and `recordEmotions()` from CognitiveGoalOrchestrator. No replacement.
**Alternatives:**
- Record one summary per tick — caps volume but still records self-generated content as experience
- Record state transitions only — when emotional valence flips or goal enters/exits surfacing set
- Keep writes with cooldown — reduces volume without addressing the conceptual issue
**Rationale:** First principles: goal surfacing is not an experience in the ExperienceEvent taxonomy (not observation, action, or outcome). It's an internal cognitive event. The meaningful goal events (priority shifts, emotional transitions, blockage resolution) are already captured by consolidation phases (GoalPrioritizationPhase, GoalAffectPhase, GoalResolutionPhase) at the right level of abstraction. Per-tick recording creates a rumination-like feedback loop where self-generated memories get consumed by consolidation → graduation → reflection → strategy learning, amplifying self-referential content.
**Trade-offs:** Loss of per-tick goal attention trace in experience memory. Mitigated: attention signals (URGENCY_SPIKE, PRIORITY_SHIFT) already capture meaningful transitions via CognitiveAttentionAccumulator.
**Sources:** `cognition/…/goal/CognitiveGoalOrchestrator.java:108-109,151-187`, ExperienceEvent sealed hierarchy, GoalPrioritizationPhase, GoalAffectPhase, RecurringThoughtScorer
**Exploration:** deep-analysis (first principles)
**Status:** captured

## D4: E9 hygiene grouping — embedding-based pairwise cosine

**Choice:** Pairwise cosine similarity via `Instance<EmbeddingModel>` with graceful degradation when unavailable
**Alternatives:**
- Keyword/token Jaccard overlap — no embedding dependency but weaker semantic grouping, misses paraphrases
**Rationale:** Same pattern as TextSimilarityCorroborator in experience consolidation. Semantic similarity is what consolidation grouping actually needs. Jaccard is a regression to bag-of-words.
**Trade-offs:** Requires EmbeddingModel on classpath for meaningful grouping. Without it, falls back to no grouping (safe — no consolidation rather than wrong consolidation).
**Sources:** `cognition/…/memory/MemoryHygieneOrchestratorImpl.java:231-249`, TextSimilarityCorroborator pattern
**Exploration:** quick
**Status:** captured

## D5: E16 belief revision — fix all three bugs

**Choice:** Fix all three: add reinforcement path, per-agent cursor with exception-safe advancement, retain disabled-by-default
**Alternatives:**
- Fix only cursor-on-exception — minimum correctness, defers rest
- Leave as-is — it's disabled, but accumulates tech debt
**Rationale:** Fixing dormant code is cheapest with no production data. Per-agent cursor is an architectural flaw that gets harder to fix with real data. Reinforcement path is the most significant — belief revision that only erodes is functionally a belief *decay*, not revision.
**Trade-offs:** More code to test for a disabled feature. Mitigated: contract tests cover all three fixes, feature stays disabled until explicitly enabled.
**Sources:** `cognition/…/belief/BeliefRevisionPhase.java:71-134,143-179`
**Exploration:** quick
**Status:** captured

## D6: Batching strategy — 6 batches by subsystem and dependency

**Choice:** Batch 1 (Signal Gates E1/E4) → Batch 2 (Memory Hygiene E8/E9) → Batch 3 (Goal Orchestration E10) → Batch 4 (Narrative/Reflection/Sub-thoughts E7/E12/E17) → Batch 5 (Personality/Constraints E14/E15) → Batch 6 (Remaining E2/E5/E6/E16)
**Alternatives:**
- All-at-once — higher risk, harder to review
- By complexity (XS first) — faster early wins but ignores dependencies
**Rationale:** Signal gates (Batch 1) unblock the most dormant functionality. Hygiene (Batch 2) is the most architecturally significant redesign. Batches 1-5 are independent; Batch 6 has internal dependency (E6 depends on E2). Within Batch 6, E2→E6 ordering is enforced.
**Trade-offs:** Sequential batches are slower than parallel, but cognitive review findings benefit from incremental verification.
**Sources:** casehubio/neocortex#1227 issue body, SE6 design pattern
**Exploration:** quick
**Status:** captured

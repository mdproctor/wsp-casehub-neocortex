# SE7: Orchestrators & Higher Cognition — Design Spec

**Issue:** casehubio/neocortex#1227
**Parent:** #1220 (Cognitive Review Epic)
**Branch:** `issue-1227-orchestrators-higher-cognition`
**Module:** cognition (goal/, narrative/, personality/, hygiene/, tom/, prompt/, belief/, relationship/, innerlife/, reflection/)
**After:** SE1 (#1221) — pipeline spine landed

## Goal

Fix 16 bugs (15 findings, one with 5 sub-items) in the orchestrator and higher cognition layer that cause signal gates to never fire, goals to pollute memory with self-referential content, memory hygiene to never evict, belief revision to only erode, and narrative/reflection to mix agent data across tenants.

## Batch 1: Signal Gates & Synthesis (E1, E4)

Signal accumulation is the input pipeline for mental model, user model, and strategy orchestrators. Until this works, those three orchestrators are functionally dead.

### E1: Signal gate never fires (MentalModelOrchestrator, UserModelOrchestrator, StrategyLearningOrchestrator)

**Problem:** All three orchestrators drain their signal buffer first, then check "enough signals + cooldown." With one signal per tick, the threshold (default 3 for MentalModel) is never reached because signals are discarded after each check.

**Files:**
- `cognition/…/mentalmodel/MentalModelOrchestrator.java:186,311-314`
- `cognition/…/usermodel/UserModelOrchestrator.java:184-195,277-280`
- `cognition/…/strategy/StrategyLearningOrchestrator.java:180-183,209-210`

**Fix:** Two distinct root causes require different fixes:

**MentalModelOrchestrator and UserModelOrchestrator:** Accumulate signals across ticks without draining until the threshold is met. Change the pattern from "drain → check threshold → discard if below" to "check accumulated count → if threshold met AND cooldown elapsed → drain and synthesize → reset count." The signal buffer persists across ticks until synthesis fires. Cap buffer at a maximum size (e.g., 50 signals) — if the buffer fills before synthesis fires, force a drain. Follow the `SignificanceAccumulator` pattern (mindmap-intelligence): accumulate, check cumulative threshold, `swapAndReset()` only when triggered.

For each orchestrator:
1. Keep the existing `ConcurrentLinkedDeque` signal buffer
2. Check `buffer.size() >= threshold` without draining
3. If threshold met AND cooldown elapsed: drain all signals, run LLM synthesis, reset cooldown timer
4. If threshold not met AND buffer not full: leave signals in buffer, return early
5. If buffer full: force drain and synthesize regardless of cooldown

**StrategyLearningOrchestrator:** Different root cause — it already accumulates drained turns into `state.totalSignals` and `state.conversationTurns` (keyed by caseId). Data IS preserved across ticks. The bug is that the gate check at line 210 uses `drainedTurns.size()` (current tick's batch count) instead of a cumulative count. Fix: change the threshold check to use `state.totalSignals` or `state.conversationTurns.size()`.

### E4: Mental-model confidence decay compounds (MentalModelOrchestrator)

**Problem:** `decayMap()` at line 290 decays from stored confidence (already decayed on prior ticks) using elapsed time since `lastReinforced` (never advanced). Each tick compounds: tick N decays an already-decayed value over ever-growing elapsed time.

**File:** `cognition/…/mentalmodel/MentalModelOrchestrator.java:283-299`

**Fix:** Use idempotent recomputation from original confidence. Store the original pre-decay confidence in `AttributedState` and recompute each tick:

```java
// Each entry has originalConfidence (set at reinforcement time) and lastReinforced
double totalElapsedHours = Duration.between(entry.lastReinforced(), now).toMillis() / 3_600_000.0;
double decayed = entry.originalConfidence() * Math.pow(0.5, totalElapsedHours / halfLifeHours);
entry.setCurrentConfidence(decayed);
```

This eliminates the compounding bug because the base is never the decayed value — it's always the original. Same result regardless of tick frequency or missed ticks. No new timestamp field needed — the existing `lastReinforced` timestamp is correct for total elapsed time. When reinforcement occurs, update `originalConfidence` to the reinforced value and reset `lastReinforced` to `now`.

## Batch 2: Memory Hygiene (E8, E9)

Independent of Batch 1. The retention formula redesign (E8) is the most architecturally significant change in SE7.

### E8: Retention composite always ≥ 0.5 (RetentionScore, MemoryHygieneOrchestratorImpl)

**Problem:** Two constant terms (`confidence=1.0`, `trust=1.0`) are added to the weighted average. With DEFAULT weights `(confidenceWeight=1.0, recencyWeight=1.0, scopeWeight=0.5, trustWeight=0.5)`, the minimum composite (at recency=0, confidence=0) is `(0 + 0 + 0.5 + 0.5)/3.0 = 0.33` — above the eviction threshold (0.1). With typical confidence scores, the floor is higher. Additionally, `scopeDecay.factor(0)` always passes `0` as scope distance, inflating scopeFactor to 1.0 regardless of actual scope. Nothing is ever evicted. The adaptive hygiene phase ratchets one way because eviction pressure is always zero.

**Files:**
- `cognition-api/…/memory/RetentionScore.java:14-27`
- `cognition/…/memory/MemoryHygieneOrchestratorImpl.java:140-148`

**Fix (D2 — first-principles redesign):**

The structural error is that confidence and trust are *additive terms* that inflate when uninformative (default 1.0). Signals with no information should have no effect.

New formula:
1. **Base score** = weighted average of `recencyFactor` (from existing `temporalDecay.factor()`) + `frequencyFactor` (from existing access-count-based scoring in `MemoryHygieneOrchestratorImpl`). These are the two signals that always carry real information.
2. **Modulated by** `confidence × trust` as *multipliers* — identity (×1.0) when unset (from `confidenceScorer.score()` and `NoOpAgentTrustProvider`), suppressive when real values arrive.
3. `scopeFactor` is removed — the current `scopeDecay.factor(0)` always passes `0` as distance, making it a constant 1.0. If scope-based decay is needed in future, it should be wired with actual scope distance, not re-added as a constant.

In `RetentionScore.compute()`:
```java
double base = (recencyWeight * recencyFactor + frequencyWeight * frequencyFactor)
              / (recencyWeight + frequencyWeight);
double modulator = confidence * trust;  // 1.0 × 1.0 = no effect when unset
return base * modulator;
```

Update `RetentionConfig` to replace the 4-weight structure with 2 base weights + modulator. The eviction threshold (0.1) and low-retention threshold (0.3) may need recalibration after the formula change — verify with existing test memories. An old, unaccessed memory should score near 0; a recently accessed memory should score near 1.0.

### E9: Hygiene grouping uses query score, not pairwise similarity (MemoryHygieneOrchestratorImpl)

**Problem:** `findSimilarGroups()` at line 241 uses `memories.get(j).score()` — the retrieval score relative to the *query*, not pairwise similarity between memories i and j. Topically unrelated memories with high query scores get grouped.

**File:** `cognition/…/memory/MemoryHygieneOrchestratorImpl.java:231-249`

**Fix (D4):** Compute pairwise cosine similarity via `Instance<EmbeddingModel>` (same pattern as `TextSimilarityCorroborator` in experience consolidation):

1. Inject `Instance<EmbeddingModel>` with graceful degradation
2. Embed all candidate memories via `embedAll()` batch call
3. Compute pairwise cosine similarity matrix
4. Group memories where pairwise similarity ≥ existing `crossLinkSimilarityThreshold` config field (not a hardcoded value)
5. When no EmbeddingModel available: skip grouping entirely (safe — no consolidation rather than wrong consolidation)

## Batch 3: Goal Orchestration (E10)

Five distinct sub-issues. Independent of Batches 1-2.

### E10e: Goal tick results discarded (CognitionCore)

**Problem:** `CognitionCore.java:445` wraps the goal proposal tick in `safeRun(Runnable)`:
```java
safeRun(() -> goals.tick(agentId, tenantId, descriptor));
```
`safeRun` takes a `Runnable` and returns `void`. The `GoalProposalTick` return value — containing proposals, abandonments, priority adjustments, and governance updates — is discarded. Goal proposal is entirely non-functional: the orchestrator computes results that nothing ever consumes.

**File:** `cognition/…/core/CognitionCore.java:445`

**Fix:** Change from `safeRun(Runnable)` to a pattern that captures the return value. Use `safeCall(Supplier<T>)` or inline the try-catch:
```java
GoalProposalTick result = safeCall(() -> goals.tick(agentId, tenantId, descriptor));
if (result != null) {
    // Process proposals, abandonments, priority adjustments
}
```
This is the highest-impact fix in Batch 3 — E10a-E10d fix secondary issues inside an orchestrator whose primary output was being thrown away.

### E10a: Deductive strategy called with empty context (GoalProposalOrchestrator)

**Problem:** `evaluateDeductive()` at line 291-293 passes `null` personality, `null` mood, empty beliefs, and empty memories to the deductive strategy. The LLM has no grounding for goal formation.

**File:** `cognition/…/goal/GoalProposalOrchestrator.java:285-303`

**Fix:** Wire the actual cognitive context into `DeductiveFormationContext`. Requires adding constructor dependencies to `GoalProposalOrchestrator`:
- `CognitiveDefaultsRegistry` → `DispositionAxes` via agentId lookup (not "Personality" — use correct type)
- `MoodOrchestrator` → `currentMood(agentId, tenantId)`
- `CaseMemoryStore` → beliefs (domain="belief", agent-scoped) and recent experiences

### E10b: Cached proposals not cleared on no-change (GoalProposalOrchestrator)

**Problem:** `cachedProposals` is set before returning `Changes` but never cleared when returning `NoChange`. Stale cached proposals persist indefinitely.

**File:** `cognition/…/goal/GoalProposalOrchestrator.java:255-262`

**Fix:** Clear `cachedProposals` when no new proposals are generated (the `NoChange` path).

### E10c: queryGoals returns all goals in tenant (CognitiveGoalOrchestrator)

**Problem:** `queryGoals()` at line 119-126 returns every goal node in the tenant with no agent filter. Multi-agent deployments see all agents' goals.

**File:** `cognition/…/goal/CognitiveGoalOrchestrator.java:119-126`

**Fix:** Filter by agent ownership using the established pattern: client-side filtering on `node.property("agent-id")`, consistent with `GoalPrioritizationPhase`, `GoalAffectPhase`, and `GoalResolutionPhase`.

### E10d: Remove self-generated experience memory writes (CognitiveGoalOrchestrator)

**Problem:** `recordSurfacing()` and `recordEmotions()` write two experience memories per surfaced goal per tick. With 5 active goals, that's 10 self-generated memories per tick — flooding the memory store and creating feedback loops through consolidation → graduation → reflection → strategy learning.

**Files:** `cognition/…/goal/CognitiveGoalOrchestrator.java:108-109,151-187`

**Fix (D3 — first-principles analysis):** Remove both `recordSurfacing()` and `recordEmotions()` calls entirely. No replacement needed.

Goal surfacing is not an experience (not observation, action, or outcome). The meaningful goal events are already captured at the right level of abstraction:
- Priority shifts: `GoalPrioritizationPhase` → `URGENCY_SPIKE`/`PRIORITY_SHIFT` attention signals
- Emotional transitions: `GoalAffectPhase` → PAD updates on goal nodes
- State changes: `GoalResolutionPhase` → `BLOCKER_RESOLVED` signals

## Batch 4: Narrative, Reflection & Sub-thoughts (E7, E12, E17)

Lightweight, independent fixes.

### E7: Narrative pipeline partitions by tenant, not agent (ReflectionEventAdapter)

**Problem:** `LevelEvent` constructor uses `tenantId` as partition key. Multi-agent deployments mix all agents' reflections into one narrative stream.

**File:** `cognition/…/narrative/ReflectionEventAdapter.java:37-39`

**Fix:** Use `agentId + ":" + tenantId` as partition key.

### E12: Sub-thoughts attributed as entity's BDI (SubThoughtTickParticipant)

**Problem:** `pushToMentalModel()` sends every sub-thought to MentalModel with `st.entity()` as subjectId. A concern like "She might be worried" gets recorded as *her* belief/desire/intention, when it's the agent's inference about her.

**File:** `cognition/…/subthought/SubThoughtTickParticipant.java:71-85`

**Fix:** Filter by sub-thought type before feeding mental model:
- **Feed mental model:** `INTENTION` only (this expresses the entity's own intent — the only type in `SubThoughtTypes` that represents an entity's mental state rather than the agent's inference)
- **Do NOT feed mental model:** `CONCERN`, `ASSOCIATION`, `SELF_REFLECTION`, `AFFECT_OBSERVATION`, `CAUSAL_INFERENCE`, `EVALUATIVE` (these are the agent's own cognitive processing, not the entity's mental states)

Note: there is no `stated-belief` type in `SubThoughtTypes`. If belief attribution is needed in future, add a new type to `SubThoughtTypes` with corresponding classifier rules in `SubThoughtClassifier`.

### E17: Reflection synthesiser discards valid heuristics (LlmReflectionSynthesizer)

**Problem:** If the LLM produces `source_turns` that don't resolve in the `turnIndex` (hallucinated/altered IDs), `sourceMemoryIds` is empty and the heuristic is silently dropped.

**File:** `cognition/…/reflection/LlmReflectionSynthesizer.java:271-279`

**Fix:** Accept heuristics without exact memory linkage:
1. If `source_turns` resolve: use them (full traceability)
2. If `source_turns` don't resolve but `source_cases` are present: use those (partial traceability)
3. If neither resolves: accept the heuristic with lower confidence (e.g., 0.3 instead of default) and log a warning. The insight may still be valid even if the LLM hallucinated the source ID.

## Batch 5: Personality & Constraints (E14, E15)

Lightweight, independent fixes.

### E14: Situational personality pull with no dt; baselineFor returns 0.5 (PersonalityStateIntegrator)

**Problem:** (a) `baselineFor()` hardcodes 0.5 for every PID-5 facet. (b) `pull()` applies a fixed alpha per tick with no time-step scaling — pull rate depends on tick frequency.

**File:** `cognition/…/situational/PersonalityStateIntegrator.java:78-96,179-181`

**Fix:**
1. Wire `baselineFor()` to cognitive profile — resolve baselines from `CognitiveDefaultsRegistry` via agentId. PID-5 facets in the agent's profile define where personality returns to between situations.
2. Scale alpha by dt: `effectiveAlpha = 1.0 - Math.pow(1.0 - alpha, dt)` where dt is elapsed ticks (or elapsed time normalized to expected tick interval). This makes pull rate independent of tick frequency.

### E15: Soft constraints in SUPPLEMENTARY tier; unregistered sections bypass filter (TierFilterCustomizer)

**Problem:** (a) `ConstraintPromptSection` is in SUPPLEMENTARY tier — dropped when arousal ≥ `1 − personalityDominance` (arousal ≥ 0.5 with pd=0.5). Constraints should persist under moderate arousal. (b) Default tier is CORE (line 87) — any section not in `TIER_MAP` is never filtered, bypassing the tier system entirely.

**File:** `cognition/…/prompt/TierFilterCustomizer.java:41,65-88`

**Fix:**
1. Move `ConstraintPromptSection` from SUPPLEMENTARY to CONTEXTUAL tier (dropped only at high arousal, not moderate)
2. Change default tier from CORE to CONTEXTUAL for unregistered sections (filtered only at high arousal, not moderate — safer than SUPPLEMENTARY because a new prompt section added without updating `TIER_MAP` would only disappear under extreme arousal rather than moderate)

## Batch 6: Remaining Orchestrators (E2, E5, E6, E16)

E6 depends on E2 — fix E2 first.

### E2: deriveQualitySignal uses pre-interaction mood delta (CognitionCore)

**Problem:** `deriveQualitySignal()` at line 636 derives quality from `lastMoodDelta.get(agentId)` — the mood shift caused by appraising the user's input (pre-interaction). The `userMessage` parameter is only carried as payload in the returned `CustomSignal`. Disposition evolution (E6) uses this pre-interaction quality to determine personality pressure direction, but the quality should reflect the interaction outcome, not the input stimulus.

**File:** `cognition/…/core/CognitionCore.java:636` (actual location of `deriveQualitySignal`)

**Note:** E2 was originally assigned to SE1 (#1221, Pipeline Spine) but was deferred. It appears in the deferred section of the queue with note "needs deeper investigation of mood-then-quality ordering in recordInteraction."

**Fix:** Move `deriveQualitySignal()` to after the response is generated. Use the post-response mood delta (the mood shift caused by the agent's own output and the user's reaction to it) rather than the pre-interaction appraisal delta. This requires capturing the mood state before and after the response generation and computing the delta from that interval.

### E5: Relational-schema trust re-integrates full history (RelationalSchemaEvolutionPhase)

**Problem:** Queries ALL relationship memories (up to 500) on every consolidation tick. No cursor — recomputes trust from scratch each time.

**File:** `cognition/…/relationship/RelationalSchemaEvolutionPhase.java:120-122`

**Fix (D1):** Add cursor tracking using the established pattern:
1. Store last-processed timestamp on a cursor node (same pattern as BeliefRevisionPhase, ExperienceConsolidationPhase)
2. Query only memories newer than cursor
3. Apply incremental trust updates from new memories only
4. Advance cursor after successful processing

### E6: Disposition evolution pressure maps POSITIVE→dominant (RelationshipPressureSource, InteractionPressureSource)

**Problem:** Hardcodes `POSITIVE → dominant trait` and `NEGATIVE → auxiliary trait`. Not psychologically grounded — a positive interaction doesn't universally strengthen the dominant personality facet.

**Files:**
- `cognition/…/personality/RelationshipPressureSource.java:37-41`
- `cognition/…/personality/InteractionPressureSource.java:35-39`

**Fix:** Use the quality signal (now correctly derived from response after E2) to determine *which* personality facets were engaged, not just dominant/auxiliary. Map quality signal to the facets that the interaction context activated:
- Use CAPS input node activations from the most recent settling to identify which personality-relevant nodes were active
- Apply pressure to the PID-5 facets aligned with those active nodes
- Fallback when no CAPS data: use appraisal dimensions (conduciveness → competence facet, external-standards → agreeableness facet)

### E16: Belief revision only erodes; cursor advances on exception (BeliefRevisionPhase)

**Problem:** Three bugs: (a) Only erosion — contradictions lower confidence but no mechanism to reinforce from supporting evidence. (b) Cursor advances over all new evidence before `processAgent` completes — if processing throws, cursor skips unprocessed evidence. (c) One cursor per tenant, not per agent.

**File:** `cognition/…/belief/BeliefRevisionPhase.java:71-134,143-179`

**Fix (D5 — fix all three):**
1. **Add reinforcement path:** When new evidence supports an existing belief (high semantic similarity + same valence), increase confidence by a bounded step (e.g., `min(current + 0.1, 1.0)`). Symmetry with erosion: contradictions erode, corroboration reinforces.
2. **Per-agent cursor:** Replace single tenant cursor with per-agent cursors. Use `agentId + ":" + tenantId` as cursor node identifier (same pattern as E7 narrative fix).
3. **Exception-safe cursor advancement:** Track `latestTimestamp` per agent. Only advance cursor AFTER `processAgent` succeeds. On exception: log, skip agent, leave cursor unchanged so evidence is reprocessed on next tick.

Feature remains disabled by default (`config.enabled()`).

## Complexity Summary

| Batch | Findings | Complexity | Estimated effort |
|-------|----------|------------|-----------------|
| 1: Signal Gates | E1, E4 | S + XS | Small |
| 2: Memory Hygiene | E8, E9 | S + M | Medium |
| 3: Goal Orchestration | E10 (5 sub) | M | Medium |
| 4: Narrative/Reflection | E7, E12, E17 | XS + S + S | Small |
| 5: Personality/Constraints | E14, E15 | S + XS | Small |
| 6: Remaining | E2, E5, E6, E16 | S + S + S + M | Medium |

**Total: 3 XS + 8 S + 3 M = ~L overall (comparable to SE6)**

## References

- casehubio/neocortex#1227 — issue body with 15 findings
- casehubio/neocortex#1220 — parent epic, priority ordering, measurement strategy
- `specs/issue-1226-affect-emotion/2026-11-26-affect-emotion-design.md` — SE6 design (batch pattern)
- `specs/issue-1226-affect-emotion/decisions.md` — SE6 decisions (D1-D4 patterns)
- `cognition-api/…/memory/RetentionScore.java` — current retention formula
- `cognition/…/memory/MemoryHygieneOrchestratorImpl.java` — hygiene orchestrator
- `cognition/…/goal/CognitiveGoalOrchestrator.java` — goal surfacing + emotion recording
- `cognition/…/goal/GoalProposalOrchestrator.java` — deductive strategy context
- `cognition/…/mentalmodel/MentalModelOrchestrator.java` — signal gate + confidence decay
- `cognition/…/belief/BeliefRevisionPhase.java` — belief erosion + cursor
- `cognition/…/prompt/TierFilterCustomizer.java` — constraint tier + default tier
- `cognition/…/narrative/ReflectionEventAdapter.java` — tenant partition
- `cognition/…/reflection/LlmReflectionSynthesizer.java` — heuristic discard
- `cognition/…/subthought/SubThoughtTickParticipant.java` — sub-thought BDI attribution
- `cognition/…/personality/PersonalityStateIntegrator.java` — baseline + dt scaling
- `cognition/…/personality/RelationshipPressureSource.java` — pressure mapping
- `cognition/…/relationship/RelationalSchemaEvolutionPhase.java` — trust cursor
- `cognition/…/core/CognitionCore.java` — quality signal timing
- Bjork dual-strength model — retrieval strength for retention scoring
- Frijda action readiness theory — goal surfacing analysis
- OCC emotion theory — sub-thought BDI attribution analysis

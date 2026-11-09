# HANDOFF — casehub-neocortex

## Last Session

Completed #865 (migrate cognitive tests to CognitionTestHarness). Migrated 3 test files (12 tests) to use `CognitionTestHarness.builder()`:
- `SearchBudgetPathologicalThresholdTest` (4 tests) — replaced manual mock wiring with `withAppraisalResult()` + `withHabituationState()`
- `ContinuumRenderingTest` (7 tests) — replaced manual prompt section construction with `setContinuumPosition()` + `renderPrompt()`
- `RecurringThoughtIntegrationTest.scorerToRenderingPipeline` — migrated to harness consolidation pipeline

Enhanced `CognitionTestHarness.Builder` with `withAppraisalResult(agentId, AppraisalResult)` for injecting specific appraisal state. Left `CuriosityDriveTest` and `CuriosityQualityTest` as component-level unit tests (they test individual components directly, not the pipeline). Landed as `e3e32759` on main, pushed to upstream, #865 closed.

## Immediate Next Step

`work continue` — start #866 (Empirical quality testing). This is L/High and needs brainstorming + a .plan before implementation.

## Remaining Work

### #866 — Empirical quality testing (L / High) ← NEXT

**What:** LLM-judged evaluation across all exploration subsystems. Not "did the value change?" (Tier 2 — already done in #849) but "did the LLM behave differently?" (Tier 3+).

**Approach:** Follow `CognitiveInfluenceEvalTest` pattern:
1. Seed character via CognitionTestHarness
2. Render cognitive state into prompt sections
3. Present situation to character via Claude CLI
4. LLM judge scores whether exploration behaviour matches cognitive state
5. Threshold: >=3/5 per scenario

**Scenarios to cover:**
- Curiosity channels (I-TYPE vs D-TYPE, SPECIFIC vs DIVERSIVE)
- Search budget personality differentiation (bold explorer vs cautious analyst — blind judge)
- Recurring thought continuum (HEALTHY → FIXATION → OBSESSION → RUMINATION)
- Goal-directed exploration (active goal near vs far vs none)
- Pathological boundary (extreme motivation + personality compression)
- Intelligence capacity (see #900 for dedicated capacity fidelity)

**Dependencies:** All layers complete (#825, #596, #826, #839, #840). CognitionTestHarness available. Needs `EvalLlmJudge` infrastructure from caps-llm-classifier.

**Key reference files:**
- `caps-llm-classifier/src/test/java/.../eval/CognitiveInfluenceEvalTest.java` — working pattern
- `caps-llm-classifier/src/test/java/.../eval/EvalLlmJudge.java` — judge infrastructure
- `cognition/src/test/java/.../eval/CognitionTestHarness.java` — test harness

### #900 — Capacity fidelity testing (M / High)

**What:** Does the LLM stay true to cognitive self-description when solving actual problems? The echo approach: describe the state, let the model figure out how to express it. Don't engineer constraints.

**Approach:** Give the same reasoning problem to three agents (high/low/null capacity). Judge evaluates fidelity to self-description, not rule compliance.

**Problem types (varying complexity):**
- 2-step syllogism (baseline — all should handle)
- 4-step logical chain (low relational complexity should show limitation)
- Distant analogy bridging (low associative reach should produce weaker connections)
- Multi-thread tracking (low working memory should lose earlier threads)

**Agent profiles:**
- High capacity (all ceilings 0.90) — clean reasoning
- Low capacity (targeted ceiling 0.40) — authentic limitation
- Null capacity — no self-description of limitation

**Judge criteria:** Fidelity (output reflects self-description), authenticity (limitation looks natural not robotic), differentiation (blind judge matches output to profile).

**Key insight from session:** This is NOT about making the LLM dumber. It's about whether cognitive self-description causally influences exploration style. The capacity layer is deliberately prompt-only — the LLM figures out how to inhabit the limitation. Engineered constraints would produce compliance, not character.

**Dependencies:** #840 complete. CognitionTestHarness available. Needs EvalLlmJudge infrastructure.

## State

- Branch: main (clean)
- Upstream: pushed to `e3e32759`
- Queue: #866 active, then #900
- All builds green (except pre-existing schema-generator failure)
- `docs/specs/issue-802-hortora-corpus-extraction/` untracked directory on main (pre-existing, not part of current work)

## References

- `cognition/src/test/java/.../eval/CognitionTestHarness.java` — enhanced with `withAppraisalResult()`
- `cognition/src/test/java/.../eval/CognitiveExplorationScenarioTest.java` — Tier 2 structural tests (S1-S5)
- `caps-llm-classifier/src/test/java/.../eval/CognitiveInfluenceEvalTest.java` — Tier 3 pattern to follow for #866
- `caps-llm-classifier/src/test/java/.../eval/EvalLlmJudge.java` — judge infrastructure
- Deferred issues: #890 (learning rate modulation), #891 (convergence ceiling), #892 (capacity→appraisal frustration)

## Warnings

- `schema-generator` module has a pre-existing build failure (Jackson 3 `tools.jackson.databind.node.ObjectNode` not found)
- `work.py` has a bug (`_sync_queue_branch_script` not defined) — `work continue` routing fails; work around by creating branches manually

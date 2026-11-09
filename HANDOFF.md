# HANDOFF — casehub-neocortex

## Last Session

Completed the intelligence capacity layer (#840) — all 4 batches, 6 tasks. Merged slot 211 into canonical main (`~/claude/casehub/neocortex`) as `00620ccf` — 144 files, ~20k lines covering the full cognitive exploration epic (#841). Created #900 (capacity fidelity testing) and #901 (test fix, closed). Revised blog with prose composition model, verification section, and practical takeaways. Fixed pre-existing EmotionRegulationGenerationPhaseTest failure (#901).

## Immediate Next Step

`work continue 865` — migrate four test classes to CognitionTestHarness.

## Issue Scaffolds

### #865 — Migrate cognitive tests to CognitionTestHarness (S / Low)

**What:** Replace manual store + component wiring with `CognitionTestHarness.builder()` in four test classes.

**Migration candidates:**
1. `RecurringThoughtIntegrationTest` — manual store + scorer wiring → `builder().withConsolidationEnabled(true).agentFromDefaults(...)`
2. `SearchBudgetPathologicalThresholdTest` — manual participant + registry wiring → `builder().withHabituationState(...).agentFromDefaults(...)`
3. `CuriosityDriveTest` / `CuriosityQualityTest` — manual store + drive wiring → `builder().withMindMapStore(store).agentFromDefaults(...)`
4. `ContinuumRenderingTest` — manual prompt section + continuum wiring → `builder().agentFromDefaults(...)` + `setContinuumPosition()`

**Pattern:** Each test currently constructs stores, registries, orchestrators, and participants by hand. The harness provides all of this via builder defaults. The migration replaces construction boilerplate with builder calls while preserving the test assertions.

**Verify:** All migrated tests still pass. Run full `mvn test -pl cognition`.

### #866 — Empirical quality testing (L / High)

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

- Branch: `issue-802-hortora-corpus-extraction` (slot main merged)
- Canonical: `~/claude/casehub/neocortex` at `00620ccf` — up to date with full epic
- Queue: #865 active, then #866, #900
- All builds green (except pre-existing schema-generator failure)
- Blog revised and open in Typora

## References

- `specs/issue-840-intelligence-capacity/2026-11-09-intelligence-capacity-layer-design.md` — reviewed spec
- `specs/issue-840-intelligence-capacity/decisions.md` — 8 design decisions
- `plans/2026-11-09-intelligence-capacity-layer.md` — implementation plan (complete)
- `blog/2026-11-09-mdp02-wanting-to-think-vs-being-able.md` — revised diary entry
- `docs/research/2026-11-05-post-era6-regulation-and-identity.md` — updated with #840 progress
- Deferred issues: #890 (learning rate modulation), #891 (convergence ceiling), #892 (capacity→appraisal frustration)
- GitHub: #900 (capacity fidelity), #901 (test fix, closed)

## Warnings

- `schema-generator` module has a pre-existing build failure (Jackson 3 `tools.jackson.databind.node.ObjectNode` not found)
- Canonical was squash-merged (not rebased per-commit) due to significant divergence between slot and upstream — 48 commits with conflicts across corpus-management
- Slot's `issue-802-hortora-corpus-extraction` branch still exists; slot main is ahead of upstream/main

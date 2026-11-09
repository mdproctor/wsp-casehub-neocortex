# HANDOFF — casehub-neocortex

## Last Session

Designed and implemented the intelligence capacity layer (#840) — Batches 1-3 of 4 complete. Separates cognitive capacity (ability to reason/associate/track) from personality (motivation to explore), grounded in DeYoung's Openness/Intellect double dissociation (Nusbaum & Silvia 2011). Three capacity dimensions: relational complexity (Halford 1998) → depth ceiling, associative reach (Mednick 1962) → laterality ceiling, working memory span (Engle & Kane 2004) → breadth ceiling.

Design: first-principles literature research established capacity as orthogonal to personality. PID-5, Jungian functions, and disposition axes all fail as capacity proxies for specific, demonstrable reasons. Hard ceiling mechanism with capacity gap signal for prose generation. Standard design review (3 rounds, 16 issues, 13 fixed).

Implementation: CognitiveCapacityConfig (boxed Double, per-field merge), CognitiveDefaults field 21, SearchBudget fields 8-11 (gap values), CDE Jungian→capacity derivation with compressed [0.55, 0.95] range, capacity ceiling + gap signal in SearchBudgetTickParticipant (step 7). 23 new tests all green.

## Immediate Next Step

`work continue 840` — Batch 4 (Prose & Scenario): 2 tasks remaining.

**Task 5:** Unified prose generation + composition. Replace dual-variant system prompt in `SearchBudgetDescriptionGenerationPhase` with single unified prompt. Update `SearchBudgetPromptSection` for prose composition (capacity prepends to base, not exclusive priority). Both files are in the plan with exact code.

**Task 6:** CognitionTestHarness capacity scenario. Three agent profiles: analytical (capped depth), exploratory (uncapped laterality), default (null capacity — backward compat). Full pipeline exercise.

Fresh session fine — the prose batch is a different domain (LLM prompting) from the pipeline work just completed.

## State

- Branch: `issue-802-hortora-corpus-extraction`
- Queue: #840 active (Batch 4 remaining), then #865, #866
- All builds green (except pre-existing schema-generator failure)
- Research doc updated with #840 progress
- Blog entry written: "The Gap Between Wanting to Think and Being Able To"

## References

- `specs/issue-840-intelligence-capacity/2026-11-09-intelligence-capacity-layer-design.md` — reviewed spec (standard, 3 rounds)
- `specs/issue-840-intelligence-capacity/decisions.md` — 8 design decisions (D1-D8)
- `plans/2026-11-09-intelligence-capacity-layer.md` — implementation plan (4 batches, 6 tasks — 4 complete)
- `blog/2026-11-09-mdp02-wanting-to-think-vs-being-able.md` — diary entry
- `docs/research/2026-11-05-post-era6-regulation-and-identity.md` — updated with #840 progress
- Deferred issues: #890 (learning rate modulation), #891 (convergence ceiling), #892 (capacity→appraisal frustration)

## Warnings

- `schema-generator` module has a pre-existing build failure (Jackson 3 `tools.jackson.databind.node.ObjectNode` not found) — unrelated to #840
- `cognitive-observability-spring` needs Jandex index from `cognitive-observability-core` — build ordering dependency, works with `mvn install` but fails with `mvn compile`

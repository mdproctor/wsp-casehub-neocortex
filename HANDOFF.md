# HANDOFF — casehub-neocortex

## Last Session

Completed the intelligence capacity layer (#840) — all 4 batches, 6 tasks done. Separates cognitive capacity (ability to reason/associate/track) from personality (motivation to explore), grounded in DeYoung's Openness/Intellect double dissociation (Nusbaum & Silvia 2011). Three capacity dimensions: relational complexity (Halford 1998) → depth ceiling, associative reach (Mednick 1962) → laterality ceiling, working memory span (Engle & Kane 2004) → breadth ceiling.

Batches 1-3 (prior session): CognitiveCapacityConfig (boxed Double, per-field merge), CognitiveDefaults field 21, SearchBudget fields 8-11 (gap values), CDE Jungian→capacity derivation with compressed [0.55, 0.95] range, capacity ceiling + gap signal in SearchBudgetTickParticipant (step 7).

Batch 4 (this session): Unified SYSTEM_PROMPT_UNIFIED replaces dual-variant prompt system — LLM generates normal/extreme/constrained descriptions in one pass. Constrained prose prepends to base via composition in SearchBudgetPromptSection. 4 scenario tests: analytical (capped depth at 0.40), exploratory (uncapped at 0.95), default (null capacity backward compat), prose composition with crystallised nodes.

27 new tests across the feature, all green.

## Immediate Next Step

`work next` — advance queue past #840 to next issue.

## State

- Branch: `issue-802-hortora-corpus-extraction`
- Queue: #840 complete, then #865, #866
- All builds green (except pre-existing schema-generator failure + pre-existing EmotionRegulationGenerationPhaseTest failure)
- Research doc updated with #840 progress
- Blog entry written: "The Gap Between Wanting to Think and Being Able To"

## References

- `specs/issue-840-intelligence-capacity/2026-11-09-intelligence-capacity-layer-design.md` — reviewed spec (standard, 3 rounds)
- `specs/issue-840-intelligence-capacity/decisions.md` — 8 design decisions (D1-D8)
- `plans/2026-11-09-intelligence-capacity-layer.md` — implementation plan (4 batches, 6 tasks — all complete)
- `blog/2026-11-09-mdp02-wanting-to-think-vs-being-able.md` — diary entry
- `docs/research/2026-11-05-post-era6-regulation-and-identity.md` — updated with #840 progress
- Deferred issues: #890 (learning rate modulation), #891 (convergence ceiling), #892 (capacity→appraisal frustration)

## Warnings

- `schema-generator` module has a pre-existing build failure (Jackson 3 `tools.jackson.databind.node.ObjectNode` not found) — unrelated to #840
- `EmotionRegulationGenerationPhaseTest.userMessageIncludesSelfConsciousGuidanceForShame` — pre-existing failure (shame prompt format mismatch)
- `cognitive-observability-spring` needs Jandex index from `cognitive-observability-core` — build ordering dependency, works with `mvn install` but fails with `mvn compile`

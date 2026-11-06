# Session Handover — neocortex (slot 196)

**Date:** 2026-11-06
**Branch:** `main` (all #818 work landed)
**Queue next:** #830 → #829 → #819

## What was done (this session)

### #818 — Automatic regulation predictor (CLOSED)

Built `RegulationStrategyPredictor` — maps (DispositionAxes × EmotionType) → regulation strategy mechanically, constraining the LLM's strategy reasoning while leaving narrative generation fully emergent.

**Key design:** The predictor pins the strategy; the LLM generates the embodied experience via Barrett four-channel rendering. No templates, no hardcoded text. The predictor tells cognition HOW to regulate; the LLM generates WHAT it feels like.

**Quality gate:** LLM judge plausibility scoring. Floor 4/5, mean 4.6/5 across 8 judge runs. Distribution: [4, 5, 4, 5, 5].

**Empirical findings (documented in research doc + blog):**

1. **Personality coherence determines predictability.** Mixed-signal personalities (avoidant BUT flexible) score 2-3 regardless of strategy. Coherent personalities (all signals one direction) score 4-5. The predictor checks coherence: `isSuppressor` requires suppressor signals ≥3 AND CC-enabling signals <2.

2. **Shame is mechanically unresolvable for suppressors.** 7 judge runs: RM=2-3, CC=2-3, AD=3. Shame is self-evaluative — needs CC, but suppressors can't execute it.

3. **LLM strategy selection is non-deterministic.** Same inputs → different strategies across runs. Agreement-based quality gates are unreliable.

### #828 — Regulation predictor observability (CLOSED)

FINE-level logging in `EmotionRegulationTickParticipant`: logs predictor hits (agent, emotion, strategy, confidence) and falls-through (agent, emotion, personality axes).

### Documentation

- Post-era6 research doc updated: `docs/research/2026-11-05-post-era6-regulation-and-identity.md`
- Blog written: `wsp-casehub/blog/2026-11-05-mdp01-when-personality-isnt-enough.md`
- Issues created: #830 (predictor quality), #831 (coherence generalisation), #832 (capacity gap generalisation)

## What the next session must do

### #830 — Predictor quality: address shame fall-through

Three approaches to try (all documented in the issue):

1. **Temporal regulation** — suppress now, reappraise later. Add temporal framing to the pinned strategy constraint. Test through judge.

2. **LLM system prompt improvement** — add personality-aware shame guidance to `EmotionRegulationGenerationPhase.SYSTEM_PROMPT`. Improves the fall-through path.

3. **CognitiveDerivationEngine continuous weights** — add `deriveRegulationDefaults(DispositionAxes)` pathway. Pattern: static `Map<String, Double>` lookup tables (like `deriveMoodBaseline`). Returns `RegulationDefaults(suppressionCapacity, reappraisalCapacity, redirectTendency)`. Entry point: `derive()` at line 141.

### Then #829 — Scenario validation

Run a short scenario with the improved predictor active. Verify it fires, check rendered output quality, measure LLM call savings. Requires #828 observability logging to see what happens.

## Key files

| File | What it does |
|------|-------------|
| `cognition/.../regulation/RegulationStrategyPredictor.java` | Strategy prediction — personality coherence + emotion category |
| `cognition/.../regulation/EmotionRegulationTickParticipant.java` | Integration — tries predictor, passes strategy hint to generation phase |
| `cognition/.../regulation/EmotionRegulationGenerationPhase.java` | LLM call — accepts optional `pinnedStrategy` parameter |
| `caps-llm-classifier/.../eval/RegulationPredictorBackTest.java` | LLM judge eval — writes results to `target/regulation-predictor-judge-results.json` |
| `cognitive-index/.../CognitiveDerivationEngine.java` | Derivation pattern for approach 3 (lines 141-167 entry point, 243-254 example pathway) |

## Test status

- cognition regulation tests: 20 pass (predictor + tick participant)
- caps-llm-classifier judge eval: passes (floor 4, mean 4.6)
- All repos synced: canonical, slot, origin (casehubio), fork (mdproctor)

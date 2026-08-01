# Handoff — 2026-08-01

## What Changed

Post-merge iteration on the strategy classifier pipeline (on main):

- **Cumulative fog-of-war**: visibility now persists after scouting — buildings don't vanish from memory when the scout leaves. Early-game visibility 12% → 30-50%. BANSHEE_HARASS accuracy 0% → 29%.
- **Unit-aware Terran labelling**: rules now check unit composition (Banshee, SiegeTank, Marine/Medivac) not just buildings. Distinguishes BANSHEE_HARASS from standard 1-1-1 openings.
- **Vertex LLM model ID fixed**: `claude-haiku-4-5@20251001` (@ separator, not -). LLM labelling pass now works.
- **Class-weighted focal loss**: sqrt-capped inverse frequency, only activates when imbalance is significant.
- **DreamHack Valencia 2022** downloaded (1094 replays). Combined dataset: 2420 replays, ~20k training samples.
- Parallel session trained all 3 ONNX models, fixed F_TEMPORAL to 239, enabled Java tests — uncommitted changes on disk.

## Immediate Next Step

1. The parallel session has uncommitted changes: `StrategyClassifierOnnxTest.java` (fixed, @Disabled removed) + ONNX model files in `inference-runtime/src/test/resources/models/`. Commit those first.
2. Retrain all 3 models with cumulative fog-of-war (this session's improvements). Run each matchup as a separate process to avoid OOM.
3. Write a blog entry about the strategy classifier — its relevance and practical application.

## What's Left

- Retrain all 3 models with cumulative fog-of-war + unit-aware rules · S · Low
- vs_terran at 57% — below 65% target. Needs more data or LLM labelling pass · M · Med
- Run LLM labelling pass now that Vertex model ID works · S · Low
- Download 3 more SC2EGSet packs for better rare-archetype coverage · S · Low

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Trigger: second consumer materialises |
| — | quarkmind#212: three-tier cascade integration | L | Med | Consumes trained .onnx models |
| — | Blog: SC2 strategy classifier — relevance + practicality | M | Med | User requested |

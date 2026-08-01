# Handoff — 2026-08-01 (fog-of-war-retrain)

## What Changed

Retrained strategy classifier models on real SC2EGSet data with cumulative fog-of-war:

- **SC2EGSet ZIPs downloaded** to persistent storage at `quarkmind/data/sc2egset-replays/` (gitignored). 5 tournament packs: IEM Katowice 2019, DreamHack Summer 2021, DreamHack Winter 2020, DreamHack Atlanta 2022, DreamHack Valencia 2022 (~2.5 GB total).
- **Data re-prepared** with cumulative fog-of-war from 3 ZIPs (IEM Katowice 2019, DreamHack Summer 2021, DreamHack Valencia 2022). 2325 replays, 4626 labelled perspectives. Data saved to `evaluation/strategy_classifier/data/sc2egset/`.
- **vs_terran retrained**: 54% top-1, 94% top-3. BANSHEE_HARASS jumped 12% → 61% with cumulative fog-of-war. BIO_TIMING 65%, MECH_PUSH 47%, RUSH 48%.
- **vs_zerg retrained**: 74% top-1, 94% top-3. ROACH_RUSH 88%, LING_BANE 70%, RUSH 60%.
- **vs_protoss NOT retrained** — OOM killed (exit code 137). Podman VM was consuming memory. With Podman stopped, should succeed.
- **ONNX test changes committed** (previous parallel session's work): `StrategyClassifierOnnxTest.java` enabled, F_TEMPORAL=239, all 3 matchup tests, 3 model files.
- **Blog draft written** (not yet saved to disk): SC2 strategy classifier — what it is, fog-of-war, architecture, where it fits in quarkmind cascade. Awaiting author review.

## Immediate Next Step

1. Stop or reduce Podman VM memory, then retrain vs_protoss:
   ```bash
   /Users/mdproctor/claude/casehub/neocortex/evaluation/strategy_classifier/.venv/bin/python3 /tmp/train_matchup.py vs_protoss
   ```
   The training script at `/tmp/train_matchup.py` handles training, ONNX export, and copying to test resources.
2. Run Java tests to verify all 3 retrained models pass:
   ```bash
   JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f inference-runtime/pom.xml test -Dtest=StrategyClassifierOnnxTest
   ```
3. Commit retrained models.
4. Review and save the blog draft (presented in session, not yet on disk).

## Key Files

- `/tmp/train_matchup.py` — single-matchup training script (trains, calibrates, exports ONNX, copies to test resources)
- `quarkmind/data/sc2egset-replays/` — persistent SC2EGSet ZIPs (gitignored in quarkmind)
- `evaluation/strategy_classifier/data/sc2egset/` — re-prepared .npz data with cumulative fog-of-war
- `evaluation/strategy_classifier/output/` — ONNX models + manifests
- `inference-runtime/src/test/resources/models/strategy/` — test resource ONNX models

## What's Left

- Retrain vs_protoss (blocked on Podman memory) · S · Low
- Commit retrained models (after vs_protoss completes) · S · Low
- Review and save blog draft to disk · S · Low
- vs_terran at 54% — below 65% target. More data or LLM labelling pass needed · M · Med
- Run LLM labelling pass now that Vertex model ID works · S · Low
- Download remaining 2 SC2EGSet packs (Atlanta + Winter already downloaded but not used in data prep) · S · Low

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Trigger: second consumer materialises |
| — | quarkmind#212: three-tier cascade integration | L | Med | Consumes trained .onnx models |
| — | Blog: SC2 strategy classifier | S | Low | Draft written, needs review + save |

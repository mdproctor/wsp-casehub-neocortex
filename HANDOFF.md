# Handoff — 2026-07-31

## What Changed

Branch `issue-76-1d-cnn-strategy-classifier` landed earlier this session. Post-merge work continued on main:

- SC2EGSet feature extractor: reads JSON replays → 119-feature per-second game state arrays (53 buildings + 53 units + 13 stats). Tested: 1326 replays from DreamHack Atlanta + IEM10, zero failures.
- Rewrote labelling rules: build-order-based instead of timing thresholds. Coverage jumped from degenerate (99% RUSH for Zerg) to 99.8% labelled across all archetypes.
- Synthetic data generator validates the pipeline end-to-end (~88% top-1 on synthetic).
- Real data training (DreamHack Atlanta 2022, 1296 replays): vs_terran 56%, vs_zerg 73%, vs_protoss 79% top-1. Top-3 all >95%. Latency <0.2ms.
- Downloaded DreamHack Valencia 2022 (1094 replays) and prepared combined dataset (2420 replays total). vs_zerg retrained on combined: 76.5% top-1 (up from 73%).
- vs_protoss and full combined retraining blocked by memory pressure (PyTorch processes OOM-killed despite 14GB free — suspected sandbox/jetsam limit).

## Immediate Next Step

Retrain all 3 matchup models on the combined dataset in a fresh session. The data is prepared at `evaluation/strategy_classifier/data/sc2egset/` — just run:
```
PYTHONPATH=. .venv/bin/python3 /tmp/train_one.py vs_terran
PYTHONPATH=. .venv/bin/python3 /tmp/train_one.py vs_zerg
PYTHONPATH=. .venv/bin/python3 /tmp/train_one.py vs_protoss
```
Or: `python3 -m evaluation.strategy_classifier.run_pipeline --data sc2egset`

Then export to ONNX and enable the @Disabled Java test.

Stop Podman before training: `podman machine stop`

## What's Left

- Retrain all 3 models on combined Atlanta+Valencia dataset · S · Low
- Export ONNX + enable Java validation test · XS · Low
- LLM labelling pass (Vertex model ID needs fixing — Haiku 4.5 not in us-east5) · S · Med

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Trigger: second consumer materialises |
| — | quarkmind#212: three-tier cascade integration | L | Med | Consumes trained .onnx models from #76 |
| — | Download more SC2EGSet packs from Zenodo for better class coverage | S | Low | 3 more packs recommended in session |

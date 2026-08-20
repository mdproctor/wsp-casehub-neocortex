# Handoff — 2026-08-20 (issue-202-retrain-strategy-classifier)

## Last Session

Closed #204 (CDI audit — all 5 classes need CDI, parent#340 used wrong criterion). Landed #203 (Flyway migration consolidation — V1-V5 → single V1, memory-jpa V1000 → V1). Started #202 (strategy classifier retraining) — designed multi-source data pipeline, implemented Spawning Tool adapter and merge/consolidation module. Blocked on data acquisition.

## Immediate Next Step

Download MSC dataset manually from browser: https://drive.google.com/uc?id=0Bybnpq8dvwudNUVOX1FCWnZoSGM — gdown rate-limited. Place extracted files in `evaluation/strategy_classifier/data/msc/`. Then inspect the format and write the MSC adapter (`ingest_msc.py`). Also download 3-5 Spawning Tool replay packs from https://lotv.spawningtool.com/replaypacks/ targeting muta/hydra/DT strategies.

## Cross-Module

**Blocking** (we owe):
- `strategy classifier ONNX models` — retrained models gate quarkmind#212 (cascade integration) and quarkmind#213 (IEM10 benchmarking) · M · Med

## Notes

- MSC Google Drive file ID `0Bybnpq8dvwudNUVOX1FCWnZoSGM` — try manual browser download, or check if Zenodo has a mirror
- `feat/update-importance` branch has stashed work — unstash when returning to it

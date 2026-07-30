# Handoff — 2026-07-30

## What Changed

Branch `issue-76-1d-cnn-strategy-classifier` landed (as `91c2522`). Closes #76, #75.

- Python ML training pipeline in `evaluation/strategy_classifier/`: MSC dataset download, map feature extraction, fog-of-war simulation, hybrid labelling (rule-based + LLM), CNN-Attention model, focal loss training, ONNX export with temperature baking, evaluation harness
- `TensorClassifier` in `inference-tasks` — same pattern as `TextClassifier` but for tensor inputs via `InferenceInput.tensor()`
- `StrategyClassifierOnnxTest` (@Disabled) — validation test skeleton for when trained models are available
- Design spec adversarially reviewed (5 rounds, 13 issues, $17.15)
- 2 garden entries: rank-2 tensor constraint (GE-20260730-2b86fd), onnxscript undeclared dep (GE-20260730-6ea2ad)

## What's Left

- Run the pipeline: download MSC data, label replays, train models, evaluate against acceptance criteria (≥65% top-1 at minute 4) · M · High
- Enable @Disabled Java test with trained .onnx models · XS · Low

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Trigger: second consumer materialises |
| — | quarkmind#212: three-tier cascade integration | L | Med | Consumes trained .onnx models from #76 |

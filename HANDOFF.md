# Handoff — 2026-06-07

## What Changed

C3 (SPI Foundation) — **DONE**. `InferenceModel` SPI shipped across three modules: `inference-api` (4 types, zero deps), `inference-inmem` (deterministic stubs), `inference-runtime` (OnnxInferenceModel wrapping ONNX Runtime JNI + DJL Tokenizers). 80 tests, ArchUnit enforced. Four design departures from the Hortora spec: ModelConfig moved to runtime, InferenceOutput simplified to `float[]`, OptionalInt for outputSize, max-2 constraint on InferenceInput. C2 bridge code deleted. Issue #3 closed. ARC42STORIES.MD updated (C3 ✅, L1 ✅, L2 ✅).

## Immediate Next Step

Start C4 — Task Adapters. Run `/work` against #4. The adapters (`NliClassifier`, `TextClassifier`, `ScalarRegressor`, `CrossEncoderReranker`) wrap `InferenceModel` and interpret `float[]` output as domain results.

## What's Left

- Task adapters — NliClassifier, TextClassifier, ScalarRegressor, CrossEncoderReranker (C4 / #4) · M · Med
- Quarkus CDI wiring, @InferenceModel qualifier, Dev Services (C5 / #5) · M · Med — blocked by C4
- SPLADE sparse embeddings (C6 / #6) · S · Med — blocked by C4
- RAG pipeline (C7 / #7) · L · Med — blocked by C6
- `token_type_ids` support for BERT-based models (#8) · S · Low
- Thread-safety + close-ordering tests (#9) · XS · Low

## Key References

- Spec: `docs/specs/2026-06-07-inference-spi-design.md` (promoted, rev 4)
- Blog: `blog/2026-06-07-mdp02-spi-that-argued-back.md`
- Garden: GE-20260607-db04c6 (requireNonNull NPE/IAE), GE-20260607-9cef08 (sequential try-catch close)
- ARC42STORIES.MD: C2 ✅, C3 ✅, C4–C7 🔲

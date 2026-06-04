# Handoff — 2026-06-04

**Head commit (project):** — (no commits yet — scaffold session)
**Head commit (workspace):** — (no commits yet)

---

## What This Is

Initial scaffold for `casehub-neural-text`. No source code. Design complete.

## Immediate Next Step

Epic 2 — native image prototype. Demonstrate ONNX Runtime JNI + HuggingFace Tokenizers JNI working in a Quarkus native image binary on macOS ARM. This gates `inference-quarkus` and Hortora's distributable native binary goal.

## What's Left

- Native image prototype (Epic 2) · M · High
- `inference-api` + `inference-runtime` + `inference-inmem` (Epic 3) · M · Med
- `inference-tasks` — NliClassifier, TextClassifier, ScalarRegressor, CrossEncoderReranker (Epic 4) · M · Med
- `inference-quarkus` — conditional on prototype (Epic 5) · M · Med
- `inference-splade` — after native image validated (Epic 6) · S · Med
- `rag-api` + `rag` + `rag-testing` (Epic 7) · L · Med

## Key References

- AI Fusion brief: `casehubio/parent: docs/specs/2026-06-03-ai-fusion-hybrid-fact-space.md`
- ONNX inference brief: `casehubio/parent: docs/specs/2026-06-03-standalone-rag-retrieval-brief.md`
- Hortora design spec: `Hortora/spec: docs/superpowers/specs/2026-06-03-onnx-inference-module-design.md`
- Tracking issues: casehubio/parent#158, casehubio/parent#164, Hortora/spec#15

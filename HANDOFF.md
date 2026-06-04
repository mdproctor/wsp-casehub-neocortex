# Handoff — 2026-06-05

**Focus:** ONNX inference (J1) — chapters C2→C3→C4→C5→C6, RAG deferred

---

## Plan — ONNX Chapter Sequence

| Order | Chapter | What | Issue | Blocked by | Scale | Complexity |
|-------|---------|------|-------|------------|-------|------------|
| 1 | C2 | Native image gate — ONNX Runtime + HF Tokenizers JNI in Quarkus native on macOS ARM | #2 | — | M | High |
| 2 | C3 | SPI Foundation + Runtime Core — `inference-api`, `inference-runtime`, `inference-inmem` | #3 | — | M | Med |
| 3 | C4 | Task Adapters — NliClassifier, TextClassifier, ScalarRegressor, CrossEncoderReranker | #4 | C3 | M | Med |
| 4 | C5 | Quarkus Integration — CDI wiring, @InferenceModel qualifier, Dev Services | #5 | C3, C4, C2 (native) | M | Med |
| 5 | C6 | SPLADE — SparseEmbedder, log-saturation, sparse maps | #6 | C2, C4 | S | Med |

C2 and C3 are independent — C2 first to retire JNI native image risk early.
C2 outcome determines whether C5/C6 target native image or JVM-only.

## Immediate Next Step

Start C2 — native image prototype. Run `/work` against #2.

## Key References

- ARC42STORIES.MD — chapter and layer details
- Hortora design spec: `Hortora/spec: docs/superpowers/specs/2026-06-03-onnx-inference-module-design.md`
- ONNX inference brief: `casehubio/parent: docs/specs/2026-06-03-standalone-rag-retrieval-brief.md`
- Tracking: parent#158, Hortora/spec#15

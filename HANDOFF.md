# Handoff — 2026-06-06

## What Changed

C2 (native image gate) — **PASS**. ONNX Runtime JNI + DJL Tokenizers JNI both work in Quarkus native image on macOS ARM (GraalVM 25.0.3). Three gotchas discovered and garden-documented. Issue #2 closed. ARC42STORIES.MD updated.

Code landed in production modules: `inference-runtime` (3 JNI bridge classes), `inference-quarkus` (gate command, tests, GraalVM config). Versions bumped: ORT 1.26.0, DJL 0.36.0.

## Immediate Next Step

Start C3 — SPI Foundation + Runtime Core. Run `/work` against #3. The JNI bridge code in `inference-runtime` is the starting point — C3 wraps it with the `InferenceModel` SPI in `inference-api` and adds `inference-inmem` stubs.

## What's Left

- `inference-api` SPI design + `inference-runtime` full implementation + `inference-inmem` stubs (C3 / #3) · M · Med
- Task adapters — NliClassifier, TextClassifier, ScalarRegressor, CrossEncoderReranker (C4 / #4) · M · Med — blocked by C3
- Quarkus CDI wiring, @InferenceModel qualifier, Dev Services (C5 / #5) · M · Med — blocked by C3, C4
- SPLADE sparse embeddings (C6 / #6) · S · Med — blocked by C2 ✅, C4
- RAG pipeline (C7 / #7) · L · Med — blocked by C6

## Key References

- Spec: `docs/specs/2026-06-05-native-image-gate-design.md` (promoted, approved rev 6)
- Native config: `inference-quarkus/src/main/resources/NATIVE-IMAGE-NOTES.md`
- Blog: `blog/2026-06-06-mdp01-native-image-gate.md`
- Garden: GE-20260606-d3cd87, GE-20260606-7bf5dd, GE-20260606-025601, GE-20260606-fc0556, GE-20260606-aab62a
- ARC42STORIES.MD: C2 ✅, C3–C7 🔲

# Handoff — 2026-06-07

## What Changed

ARC42STORIES.MD backfilled — C3 chapter status ✅, L1+L2 detail sections fully populated (key files, key wiring, architectural decisions, gotchas, pattern to replicate). Header, journey status, and Mermaid diagram updated to reflect C1–C3 complete.

## Immediate Next Step

Start C4 — Task Adapters. Run `/work` against #4. The four adapters (`NliClassifier`, `TextClassifier`, `ScalarRegressor`, `CrossEncoderReranker`) wrap `InferenceModel` and interpret `float[]` output as domain results.

## What's Left (ARC42STORIES chapter order)

- **C4 Task Adapters (#4)** — NliClassifier, TextClassifier, ScalarRegressor, CrossEncoderReranker · M · Med
- **C5 Quarkus Integration (#5)** — CDI wiring, @InferenceModel qualifier, Dev Services · M · Med — blocked by C4
- **C6 SPLADE (#6)** — SparseEmbedder, log-saturation, sparse map output · S · Med — blocked by C4
- **C7 RAG Pipeline (#7)** — CorpusStore, CaseRetriever, hybrid RRF fusion, tenancy isolation · L · Med — blocked by C6
- **#8** token_type_ids support for BERT models · S · Low — independent
- **#9** thread-safety + close-ordering tests · XS · Low — independent

## Key References

- ARC42STORIES.MD: C1–C3 ✅, C4–C7 🔲 — chapter sequencing in §9.2
- Spec: `docs/specs/2026-06-07-inference-spi-design.md` (promoted, rev 4)
- Blog: `blog/2026-06-07-mdp02-spi-that-argued-back.md`
- Garden: GE-20260607-db04c6 (requireNonNull NPE/IAE), GE-20260607-9cef08 (sequential try-catch close)

# Handoff — 2026-06-08

## What Changed

C4 (Task Adapters) — **DONE**. `inference-tasks` shipped with four typed adapters: `NliClassifier` (convention + explicit-index constructors), `TextClassifier` (labels at construction, softmax), `ScalarRegressor` (raw scalar), `CrossEncoderReranker` (score + batch rerank). 61 tests, ArchUnit enforced including new casehub domain exclusion rule via `DescribedPredicate`. Issue #4 closed. ARC42STORIES.MD updated (C4 ✅, L3 ✅). Spec promoted. Blog published.

Also backfilled ARC42STORIES.MD L1+L2 detail sections from C3 (key files, key wiring, gotchas, pattern to replicate) — left incomplete by previous session.

## Immediate Next Step

Start C5 or C6. Run `/work` against #5 (Quarkus CDI wiring) or #6 (SPLADE sparse embeddings). Both unblocked by C4. C6 before C5 is viable — C6 establishes the adapter pattern for SPLADE; C5 wraps both C4 and C6 in CDI.

## What's Left (ARC42STORIES chapter order)

- **C5 Quarkus Integration (#5)** — CDI wiring, @InferenceModel qualifier, Dev Services · M · Med — blocked by C4 ✅
- **C6 SPLADE (#6)** — SparseEmbedder, log-saturation, sparse map output · S · Med — blocked by C4 ✅
- **C7 RAG Pipeline (#7)** — CorpusStore, CaseRetriever, hybrid RRF fusion, tenancy isolation · L · Med — blocked by C6
- **#8** token_type_ids support for BERT models · S · Low — independent
- **#9** thread-safety + close-ordering tests · XS · Low — independent
- **#10** backport ArchUnit casehub domain exclusion rule to inference-api, inmem, runtime · XS · Low — independent

## Key References

- ARC42STORIES.MD: C1–C4 ✅, C5–C7 🔲 — chapter sequencing in §9.2
- Spec: `docs/specs/2026-06-07-task-adapters-design.md` (promoted, rev 3)
- Blog: `blog/2026-06-08-mdp03-floats-meaning.md`
- Garden: GE-20260607-db04c6 (requireNonNull NPE/IAE), GE-20260607-9cef08 (sequential try-catch close)

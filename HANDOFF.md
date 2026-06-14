# Handoff — 2026-06-14

## What Changed

Closed #24 (L/Med — examples project). Two modules: `example-text-analysis` (5 standalone demos: NLI, zero-shot classification, scoring, reranking, SPLADE) and `example-rag-pipeline` (CDI wiring, 15 corpus docs, 3 demos: flat ingest, zip ingest, hybrid search). Architecture justification doc with state-of-the-art citations (`docs/architecture-justification.md`). Spec went through 3 review rounds. 23 smoke tests passing in ~29s. Also created `docs/specs/2026-06-14-examples-project-design.md`. Two garden entries submitted (GE-20260614-b94048 — SPLADE licensing trap, GE-20260614-d9a38f — Xenova gated exports). Blog entry published (mdp09).

## Immediate Next Step

Fix #25 (S/Low — `ExampleModelProducer` missing `EmbeddingModel` bean + uncomment `langchain4j-embeddings` dependency). Required for `RagPipelineIT` to work under the `examples` profile with real models. Then #26 (XS/Low — batched minor review findings).

## What's Left

- #25 — ExampleModelProducer missing EmbeddingModel bean for full-profile integration tests · S · Low
- #26 — batched minor review findings (NliClassifier constructor consistency, temp dir cleanup, CORPUS_FILES duplication) · XS · Low
- parent#247 — sync neural-text deep-dive for examples modules · XS · Low
- parent#214 — sync PLATFORM.md for reactive SPIs + EmbeddingIngestor rename · S · Low
- parent#236 — sync PLATFORM.md for ingestion bridge · S · Low
- #22 — extract corpus CDI integration to corpus-quarkus/ module (trigger: second consumer) · M · Low
- #23 — update parent spec config keys for ingestion bridge · XS · Low
- ARC42STORIES.MD — add L8/L9 corpus layers + update for #19 ingestion bridge · S · Low

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #12 | Migrate Qdrant hybrid search to LangChain4j when #4994 ships | M | Low | Blocked on external LangChain4j PR |

## Key References

- Spec: `docs/specs/2026-06-14-examples-project-design.md`
- Architecture justification: `docs/architecture-justification.md`
- Plan: `plans/2026-06-14-examples-project.md` (workspace)
- Blog: `blog/2026-06-14-mdp09-showing-the-work.md`
- Garden: `GE-20260614-b94048` (SPLADE licensing), `GE-20260614-d9a38f` (Xenova gated exports)

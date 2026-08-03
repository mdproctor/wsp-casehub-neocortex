# Handoff — 2026-08-04 (main)

## What Changed

Closed #201 — batch ONNX inference in CorpusIngestionService. Refactored `doReconcile()` to collect chunks from all missing documents before calling `ingest()`, enabling ONNX batch inference. Single method change, 3 new tests. Pushed to upstream.

## Completed Epics

- #196 — agent memory patterns: **CLOSED** (all 3 batches done, slot 74 archived)
- #197 — retrieval model quality: batches 1-3 done, #39 deferred (slot 75 archived). Epic still open on GitHub.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #22 | Extract corpus CDI to corpus-quarkus/ | M | Low | Unblocked |
| #65 | epic: memory-memori adapter | XL | Med | Blocked — Memori REST API not shipped |
| #16 | quarkus-langchain4j composition annotations | M | Low | Blocked upstream |
| #12 | Migrate Qdrant hybrid search | M | Med | Blocked upstream |

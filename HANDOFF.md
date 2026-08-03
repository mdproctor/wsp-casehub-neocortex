# Handoff — 2026-08-03 (issue-201-batch-onnx-ingestion)

## What Changed

Closed #201 — batch ONNX inference in CorpusIngestionService. Refactored `doReconcile()` to collect chunks from all missing documents before calling `ingest()`, enabling ONNX batch inference. Single method change, 3 new tests. Design-reviewed (light, 4 dimensions). Pushed to upstream.

Garden: 5 entries from work-start context (batch ONNX gotchas), no new entries this session.

## Immediate Next Step

Pick work from epics or standalone backlog. Epic slots ready:
- Slot 74: `/Users/mdproctor/claude/casehub/worktrees/74/neocortex` — #196 (Batch 1: #184 experience stream)
- Slot 75: `/Users/mdproctor/claude/casehub/worktrees/75/neocortex` — #197 (Batch 1: #49+#63 eval pipeline)

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #196 | epic: agent memory patterns | — | — | Slot 74, 3 batches |
| #197 | epic: retrieval model quality | — | — | Slot 75, 4 batches |
| #22 | Extract corpus CDI to corpus-quarkus/ | M | Low | Unblocked |
| #65 | epic: memory-memori adapter | XL | Med | Needs slot |
| #16 | quarkus-langchain4j composition annotations | M | Low | Blocked upstream |
| #12 | Migrate Qdrant hybrid search | M | Med | Blocked upstream |

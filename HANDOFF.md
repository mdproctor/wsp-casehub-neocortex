# Handoff — 2026-07-29

## What Changed

Branch `issue-129-cbr-memory-arc42-docs` landed (as `9479c84`). Closes #129.

- Added §5.1 CBR Memory Subsystem to ARC42STORIES.MD — SPI hierarchy, FeatureField schema (9 variants), CbrFilter predicates (8 variants), decorator chain (8 decorators with priorities), CbrSimilarityScorer three-level precedence, CbrQuery retrieval modes, Qdrant payload mapping, ScoredCbrCase structure
- Hygiene: recovered 2 specs from closed branches (issue-178, issue-62) to workspace main

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Trigger: second consumer materialises |
| #76 | Train 1D-CNN strategy classifier + ONNX export | M | High | Unblocked by #77 (tensor input SPI) |

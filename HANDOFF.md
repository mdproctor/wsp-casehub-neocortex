# Handoff — 2026-06-30

## What Changed

Closed `issue-20-caseretriever-cbr-contract` — CBR retrieval architecture. Standalone `CbrCaseMemoryStore` SPI in neural-text (does not extend `CaseMemoryStore` — CDI displacement avoidance via composition). Open `CbrCase` type hierarchy (`TextualCbrCase`, `FeatureVectorCbrCase`). `CbrFeatureSchema` drives Qdrant payload index creation (categorical exact-match, numeric range). In-memory + Qdrant implementations, contract test (12 behavioural tests). `PayloadFilter` extended with `Gte`, `Lte`, `Range`. Design review (5 rounds, 23 issues, all resolved). 1 garden entry (GE-20260630-815259 — CDI bean displacement across repos).

Also created epic #55 (unified knowledge retrieval) with two children: #20 (done) and #56 (memory backend migration — Phase 2). Filed #57 (repo rename to neocortex) and #58/#59 (spec update + reconstructCase fragility).

Paused #46 (SPLADE/reranker tuning) — still in pause stack.

## Immediate Next Step

Pick from backlog — run `/work` to start. Pause stack has #46 (SPLADE tuning).

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #56 | Memory backend migration from platform to neural-text | L | Med | Phase 2 of unified knowledge retrieval. Blocked by #20 (done) |
| #57 | Rename neural-text to neocortex | M | Low | Mechanical — repo, artifactIds, consumer deps |
| #46 | SPLADE/reranker tuning for garden retrieval | M | Med | Paused. Hortora/engine#28 blocker resolved |
| #39 | Dedicated RelevanceEvaluator model — CRAG accuracy | L | High | R&D |
| #29 | ColBERT late interaction retrieval | L | High | ONNX export + MaxSim |

## Key References

- Design spec: `specs/issue-20-cbr-retrieval-architecture/2026-06-30-cbr-retrieval-architecture.md` (project)
- Analysis: `specs/issue-20-cbr-retrieval-architecture/2026-06-30-cbr-paradigms-and-analysis.md` (project)
- Garden: GE-20260630-815259 (CDI bean displacement across repos)
- Blog: `blog/2026-06-30-mdp02-the-memory-that-retrieves.md`

# Session Handover — 2026-11-03 (session 5)

## What happened (session 5)

**#792 landed** — removed hardcoded 30-day recency decay from `CognitiveMemoryRetriever.queryCorpora()`. The search pipeline already scores recency via `TemporalDecayScorer` and `VersionScorer`; the consumer-layer decay was a duplicate that compound-penalised older documents. Six lines removed, test updated. Commit `ece3c932` on main.

**Close ceremony completed** — the 763/764 plan was stuck in `closing:merged` from a prior session interruption. Completed the full ceremony: verified #779-#782 (all fixed in the code review session before merge), marked plan 7/7, transitioned to drained, synced canonical repos.

**Blog written** — "The Score That Counted Twice" (`blog/2026-11-03-mdp02-the-score-that-counted-twice.md`). Educational piece on compound decay in multi-stage retrieval pipelines, with 2 SVGs. Opened in Typora for review.

**Canonical sync** — both project and workspace rebased/pushed to canonical clones at `~/claude/casehub/neocortex` and `~/claude/public/casehub/neocortex`.

## Next session

Start with **#785** — Audit corpus-management for domain abstraction (M/Med). Foundation for the generalization epic #789. Then #787 (rich documents — PDF/OCR/images).

`.plan` scaffolded with #785 ready to go. Run `work` to begin.

---

## Previous session (session 4)

Completed the corpus management epic (#763) — designed, implemented, reviewed, and landed the `@McpDomain("corpus")` auto-generated endpoint layer (#776), plus comprehensive code review fixes (#779-#782).

**Implementation:** Created `CorpusApi` interface with 19 operations (`@McpDomain("neocortex/corpus")`), `CorpusApiBean` (thin delegator), `CorpusIndexService` (wraps RAG SPIs for index management). Three result types: `CorpusStatus`, `UnretrievedReport`, `EntryDetail`.

**Code review:** 4-dimension parallel review found 11 issues — 3 correctness bugs (search() delegating to searchAdaptive(), null guards for gardenRoot and entryIds), test coverage gaps (reindexEntry and unretrieved untested, 12/19 CorpusApiBean operations untested), and hygiene (SearchScoringConfig still had Quarkus annotations, missing POM dep, unused import). All fixed. Tests: 105 → 123.

**Branch close:** Rebased onto canonical main (25 new commits from other slots, 1 conflict in CognitiveMemoryRetriever resolved — merged observers + corpus search). Squashed 25 commits into 1 semantic commit. Merged to main, stamped, pushed to canonical. 14 issues closed.

**Blog:** "The Interface That Replaced Seven Files" — revised with code review findings section. 4 entries total in the series, all indexed.

**Issue hygiene:** Closed 7 orphaned children of #763 (#767-#773) that were implemented but never closed. Closed #751 as won't-do with detailed rationale (cognitive modulation doesn't belong at RAG retrieval layer). Filed #792 for hardcoded 30-day decay in queryCorpora().

## Commits landed on main

| Repo | Commit | Description |
|------|--------|-------------|
| neocortex | `d4fd3966` | feat: corpus management platform — SPIs, runtime, @McpDomain endpoints |
| workspace | `92aa175` | feat: corpus management workspace — design specs, plans, blog entries |
| workspace | `f927aea` | fix: add missing blog entries to INDEX.md |

## Next session

| Issue | What | Scale | Start with |
|-------|------|-------|-----------|
| #792 | Remove hardcoded 30-day recency decay from queryCorpora() | XS/Low | **Done** — landed as ece3c932 |
| #789 | Epic: Corpus management generalization | XL/High | Ordered child issues below |
| #785 | Audit corpus-management for domain abstraction | M/Med | First — fix leaks before building on them |
| #786 | E2E examples across diverse domains | M/Med | After #785 |
| #787 | Rich document ingestion (PDF, Word, OCR, positional markdown) | L/High | After #785, brainstorm-first |
| #788 | Corpus mindmap — sticky-note annotations | M/High | After #785, brainstorm-first |
| #790 | Compact relationship store — denormalized cognitive values | L/High | Independent investigation |

## Key design discussion this session

**#751 rationale (won't-do):** Cognitive modulation (mood-congruent, goal-relevant, recency-decayed scoring) doesn't belong at the RAG retrieval layer because: (1) documents don't have emotional valence — category error; (2) CaseContextRetriever is shared infrastructure with no agent context — scope mismatch; (3) cognitive values apply to the agent's *representation* of the object (MindMap node after promotion), not to the document itself.

**#790 (compact relationship store):** Many agent-object relationships don't need full MindMap graph machinery — they need a fast lookup with ~31 cognitive value columns. SQLite stores NULLs cheaply, so a sparse wide table is efficient. Needs audit of existing MindMap nodes to classify which are graph entities vs relationships.

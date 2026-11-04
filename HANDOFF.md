# HANDOFF — casehub-neocortex

## Last Session

Completed **#785** (corpus-management domain abstraction audit). Audited all four corpus modules against eight use cases — found 13 leaks across API and impl layers, classified by consumer impact, remediation effort, and Hortora breakage risk.

Key architectural insight: the platform needs two content management patterns — **corpus** (curated library) and **workspace** (agent-driven research desk) — sharing the same storage and search subsystems. The workspace concept emerged from stress-testing against market/product research use cases: an LLM building a corpus iteratively during research needs different lifecycle, provenance, and enrichment tools than a curated document store.

Filed remediation issues: #800 (Phase 1 renames, S/Low), #801 (Phase 2 API fixes, M/Med), #802 (Phase 3 structural extraction, L/High). Filed #804 (research workspace methodology, L/High). Updated #789 epic with all issues in priority order. Blog entry written.

## Immediate Next Step

Start **#800** — Phase 1 renames (S/Low). Mechanical `ide_refactor_rename`: `gardenId`→`corpusId`, `gardenRoot`→`corpusRoot`, `frontmatter`→`metadata`, `ge_id`→`document_id`, `qdrantCollection`→`vectorCollection`.

## References

- `docs/specs/2026-11-04-corpus-domain-abstraction-audit.md` — audit spec (13 leaks, 3-phase roadmap)
- `blog/2026-11-04-mdp01-corpus-vs-workspace.md` — "The Library and the Desk"
- `.plan` — queue: #800, #786, #801, #787, #802, #788, #804

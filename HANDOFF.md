# HANDOFF — casehub-neocortex

## Last Session

Completed **#800** (Phase 1 renames, S/Low). Renamed 5 corpus-management naming leaks identified by the #785 audit:

- L4: `CorpusDescriptor.qdrantCollection` → `vectorCollection`
- L6: `CorpusEntry.frontmatter` → `metadata`
- L8: `FederationConfig.gardenId` → `corpusId`
- L11: ProvenanceStore `ge_id` → `document_id` (Flyway V4 migration)
- L12: `CorpusApiBean.gardenRoot` → `corpusRoot`

Also renamed related local variables/parameters in FederationConfigParser, CorpusIndexService, GardenReindexService for consistency. 20 files changed, 123 corpus-management tests pass. Landed as 2658d17c on main.

## Immediate Next Step

Start **#786** — E2E examples across domains (M/Med). Or **#801** — Phase 2 API fixes (M/Med) if continuing the rename remediation sequence.

## References

- `docs/specs/2026-11-04-corpus-domain-abstraction-audit.md` — audit spec (13 leaks, 3-phase roadmap)
- `.plan` — queue: #786, #801, #787, #802, #788, #804

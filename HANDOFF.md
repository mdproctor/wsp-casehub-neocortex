# HANDOFF — casehub-neocortex

## Last Session

Epic #526 (corpus extraction richness) — 16/17 items complete. Full audit of corpus→importer field coverage found 17 dropped fields, all fixed with TDD (22 tests):

**Extraction improvements:** #501 (lifecycle), #527 (formative), #528 (goals), EDTF qualifier fix
**Importer round 1:** #530 (formative attrs), #531 (LifecycleResolver), #532 (gut/temporal/caps/contradicts)
**Importer round 2 (audit-driven):** #533 (goal+trait+provenance on nodes), #534 (edge metadata), #535 (memory provenance), #536 (entity enrichments), #537 (subject parameterization)

All blocks-ui commits on `issue-471-cognitive-workbench`: b6a54f3, b931955, fc62713, 084b85a, 5cc67b9, 45471b4

## Immediate Next Step

**#529 — Full pipeline re-run** with 85-field coverage verification. Only remaining item in epic #526.

## Key Context

- Neocortex 0.2-SNAPSHOT installed to local Maven repo with LifecycleResolver
- CorpusImporter fully refactored: 4 testable static methods (buildMemoryAttributes, resolveTemporalBounds, buildNodeProperties, buildEdgeProperties, resolveSubject)
- Zero dropped fields between corpus.json and stores (verified by audit + 22 tests)
- Subject parameterized from corpus.json — ready for Napoleon (#498)

## Open Issues

| Issue | Summary | Status |
|-------|---------|--------|
| #526 | **Epic: corpus extraction richness** | 16/17 done |
| #529 | Pipeline re-run + coverage verification | **Next** |
| #498 | Napoleon biography | After #526 |
| #499 | Behavioural template extraction | Design done |
| #502 | Importer UI | After #526 |
| #503 | Avatar narrator | Design done |
| #514 | Coverage gate / field registry | During #529 |

## References

- Epic: casehubio/neocortex#526
- Pipeline scripts: `blocks-ui/examples/cognitive-workbench/scripts/`
- Source biography: `blocks-ui/examples/cognitive-workbench/source/frida-kahlo-biography.md`

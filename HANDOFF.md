# HANDOFF — casehub-neocortex

## Last Session

Epic #526 (corpus extraction richness) — completed 8 issues in one session:
- #501: lifecycle extraction prompts (blocks-ui b6a54f3)
- #527: formative experience extraction (blocks-ui b931955)
- #528: goal extraction improvements (blocks-ui fc62713)
- #530: importer formative attributes (blocks-ui 084b85a)
- #531: importer LifecycleResolver integration (blocks-ui 084b85a)
- #532: importer remaining attribute coverage (blocks-ui 084b85a)
- #495-497: closed (code already done)
- Created epic #526, filed #527-529, #530-532

Also fixed EDTF qualifier format in extraction prompt (postfix not prefix per ISO 8601-2).

## Immediate Next Step

**Epic #526 — corpus extraction richness.** 11/12 items done.

### Done
- ~~#500 — Lifecycle event model~~ ✅
- ~~#501 — Lifecycle extraction~~ ✅ (blocks-ui b6a54f3)
- ~~#495 — Fuzzy matching~~ ✅
- ~~#496 — Noise dismiss~~ ✅
- ~~#497 — Gap confidence~~ ✅
- ~~#527 — Formative experience extraction~~ ✅ (blocks-ui b931955)
- ~~#528 — Goal extraction improvements~~ ✅ (blocks-ui fc62713)
- ~~#530 — Importer formative attributes~~ ✅ (blocks-ui 084b85a, 12 tests)
- ~~#531 — Importer LifecycleResolver~~ ✅ (blocks-ui 084b85a)
- ~~#532 — Importer attribute coverage~~ ✅ (blocks-ui 084b85a)
- Disposition profile — already working in Phase 2b
- Domain splitting — extraction correct, importer respects domain field

### To do
- **#529** — Full pipeline re-run with 85-field coverage verification

### After epic
- **#502** — Corpus importer UI (import complete, UI display deferred)
- **#498** — Napoleon biography (fill model coverage gaps)

**Then:** UI improvements (lifecycle display, timeline view, cognitive dimension polish)

## Key Context

- #525 landed: pipeline convergence loop, improved processing tools
- CLAUDE.md has Cognitive Corpus Coverage Protocol: 4-stage chain, 85-field registry (#514)
- #500 landed: LifecycleDate (EDTF), LifecycleEvents, LifecycleResolver in mindmap-api
- Neocortex 0.2-SNAPSHOT installed to local Maven repo with all #500 classes
- CorpusImporter refactored: buildMemoryAttributes() and resolveTemporalBounds() extracted as testable static methods

## Open Issues

| Issue | Summary | Status |
|-------|---------|--------|
| #526 | **Epic: corpus extraction richness** | Active — 11/12 done |
| #529 | Pipeline re-run + coverage verification | **Next** |
| #498 | Napoleon biography | After #526 epic |
| #499 | Behavioural template extraction | Design done |
| #502 | Importer UI | After #526 epic |
| #503 | Avatar narrator | Design done |
| #514 | Coverage gate / field registry | During #529 re-run |

## References

- Epic: casehubio/neocortex#526
- Pipeline scripts: `blocks-ui/examples/cognitive-workbench/scripts/`
- Docs: `blocks-ui/examples/cognitive-workbench/docs/` (model reference, extraction methodology, audit report)
- Source biography: `blocks-ui/examples/cognitive-workbench/source/frida-kahlo-biography.md`

# HANDOFF — casehub-neocortex

## Last Session

Implemented #501 (extraction pipeline lifecycle events). Updated `extract_structure.py` ENTITY_SYSTEM prompt to request lifecycle events with standard labels aligned to `LifecycleEvents.java`. Updated `assemble_corpus.py` to expand lifecycle arrays into `lifecycle.*` node properties. Updated coverage checker and field registry. Committed as b6a54f3 on blocks-ui `issue-471-cognitive-workbench`.

## Immediate Next Step

**Epic #526 — corpus extraction richness.** Maximize data quality before import.

### Done
- ~~#500 — Lifecycle event model~~ ✅
- ~~#501 — Lifecycle extraction~~ ✅ (blocks-ui b6a54f3)
- ~~#495 — Fuzzy matching~~ ✅
- ~~#496 — Noise dismiss~~ ✅
- ~~#497 — Gap confidence~~ ✅
- Disposition profile — already working in Phase 2b `enrich_entity.py`
- Domain splitting — extraction already classifies domains correctly (importer concern → #502)

### To do
- ~~**#527** — Formative experience extraction~~ ✅ (blocks-ui b931955)
- **#528** — Goal extraction improvements (implicit/thematic/strategic goals)
- **#529** — Full pipeline re-run with 85-field coverage verification

### After epic
- **#502** — Corpus importer + UI (import after extraction is rich)
- **#498** — Napoleon biography (fill model coverage gaps)

**Then:** UI improvements (lifecycle display, timeline view, cognitive dimension polish)

## Key Context

- #525 landed: pipeline convergence loop, improved processing tools
- CLAUDE.md now has Cognitive Corpus Coverage Protocol: 4-stage chain, 85-field registry (#514), verification agents, maintenance rules
- Enrichment prompts updated for tendency intensities + distortion strengths but NOT re-run yet
- The lifecycle event model was designed in detail (CIDOC-CRM research) — see #500 issue body
- #500 landed: LifecycleDate (EDTF), LifecycleEvents, LifecycleResolver in mindmap-api; NodeSnapshot/FieldChange updated in cognitive-observability

## Open Issues

| Issue | Summary | Status |
|-------|---------|--------|
| #526 | **Epic: corpus extraction richness** | Active — 6/9 done |
| #527 | Formative experience extraction | ✅ blocks-ui b931955 |
| #528 | Goal extraction improvements | Next |
| #529 | Pipeline re-run + coverage verification | After #527, #528 |
| #498 | Napoleon biography | After #526 epic |
| #499 | Behavioural template extraction | Design done |
| #502 | Importer + UI lifecycle | After #526 epic |
| #503 | Avatar narrator | Design done |
| #514 | Coverage gate / field registry | During #529 re-run |

## References

- Epic: casehubio/neocortex#471
- Pipeline scripts: `blocks-ui/examples/cognitive-workbench/scripts/`
- Docs: `blocks-ui/examples/cognitive-workbench/docs/` (model reference, extraction methodology, audit report)
- Source biography: `blocks-ui/examples/cognitive-workbench/source/frida-kahlo-biography.md`

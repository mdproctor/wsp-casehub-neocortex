# HANDOFF — casehub-neocortex

## Last Session

Implemented #500 (lifecycle event model). Three new classes in mindmap-api: `LifecycleDate` (EDTF Level 1 / ISO 8601-2:2019 partial dates with postfix qualifiers), `LifecycleEvents` (lifecycle.* property convention with standard labels per entity type), `LifecycleResolver` (derives validFrom/validUntil from lifecycle properties). Updated `NodeSnapshot` + `FieldChange` in cognitive-observability. 66 new tests. Landed as 75b9965d on main.

## Immediate Next Step

**Complete all modelling changes before re-running the pipeline.** The plan (in order):

1. ~~**#500** — Lifecycle event model~~ ✅ Closed
2. **#501** — Extraction pipeline: update prompts to capture lifecycle events with semantic labels
3. **Domain splitting** — importer must store memories in correct domains (experience/relationship/reflection/mood), not all as experience
4. **Formative experience type** — childhood events need `developmental-period`, `situation-types`, `salience-multiplier` attributes
5. **Disposition profile** — Phase 2b extraction of 5 disposition axes for primary subject
6. **Goal extraction** — only 3 goals in current corpus, needs stronger prompts
7. **#502 (import part only)** — importer updates for lifecycle + domains + formative. UI display deferred.
8. **Close #495-497** — fuzzy matching, noise dismiss, gap classification already implemented in code
9. **Re-run pipeline** with full coverage verification against 85-field registry (#514)

**Then:** UI improvements (lifecycle display, timeline view, better layout, cognitive dimension polish)

**Then:** Napoleon (#498) to fill model coverage gaps

## Key Context

- #525 landed: pipeline convergence loop, improved processing tools
- CLAUDE.md now has Cognitive Corpus Coverage Protocol: 4-stage chain, 85-field registry (#514), verification agents, maintenance rules
- Enrichment prompts updated for tendency intensities + distortion strengths but NOT re-run yet
- The lifecycle event model was designed in detail (CIDOC-CRM research) — see #500 issue body
- #500 landed: LifecycleDate (EDTF), LifecycleEvents, LifecycleResolver in mindmap-api; NodeSnapshot/FieldChange updated in cognitive-observability

## Open Issues

| Issue | Summary | Status |
|-------|---------|--------|
| #495-497 | Gap report improvements | Code done, issues open |
| #498 | Napoleon biography | After UI work |
| #499 | Behavioural template extraction | Design done |
| #501 | Pipeline lifecycle events | **Next** |
| #502 | Importer + UI lifecycle | Import after #501, UI deferred |
| #503 | Avatar narrator | Design done |
| #514 | Coverage gate / field registry | During re-run |

## References

- Epic: casehubio/neocortex#471
- Pipeline scripts: `blocks-ui/examples/cognitive-workbench/scripts/`
- Docs: `blocks-ui/examples/cognitive-workbench/docs/` (model reference, extraction methodology, audit report)
- Source biography: `blocks-ui/examples/cognitive-workbench/source/frida-kahlo-biography.md`

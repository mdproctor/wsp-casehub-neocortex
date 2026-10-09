# HANDOFF — casehub-neocortex

## Last Session

Brief session — status check and planning. No code changes. Confirmed #525 (pipeline convergence) is closed. Verified #500-502 (lifecycle event model) are still open.

## Immediate Next Step

**Complete all modelling changes before re-running the pipeline.** The plan (in order):

1. **#500** — Lifecycle event model: `lifecycle.*` property convention, standard labels per entity type (born, completed, first-exhibited, etc.), date + event label not start/end range
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

## Open Issues

| Issue | Summary | Status |
|-------|---------|--------|
| #495-497 | Gap report improvements | Code done, issues open |
| #498 | Napoleon biography | After UI work |
| #499 | Behavioural template extraction | Design done |
| #500 | Lifecycle event model | **Next** |
| #501 | Pipeline lifecycle events | After #500 |
| #502 | Importer + UI lifecycle | Import after #501, UI deferred |
| #503 | Avatar narrator | Design done |
| #514 | Coverage gate / field registry | During re-run |

## References

- Epic: casehubio/neocortex#471
- Pipeline scripts: `blocks-ui/examples/cognitive-workbench/scripts/`
- Docs: `blocks-ui/examples/cognitive-workbench/docs/` (model reference, extraction methodology, audit report)
- Source biography: `blocks-ui/examples/cognitive-workbench/source/frida-kahlo-biography.md`

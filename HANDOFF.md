# HANDOFF — casehub-neocortex (slot 229)

## Session 2026-11-26 (current)

### What was completed

**#1076 — PID-5 facet extension for situational attractor profiles**

Extended the PID-5 facet system from 13 to 25 facets across three pipelines:

1. **Eidos** — `AmpdFacets.CANONICAL` expanded to 25 facets. 445 new situational attractor profile shifts across 12 archetype families × 5 modes (stress/flow/social collaborative/competitive/hierarchical). Literature-grounded base deltas with archetype-specific modulation.

2. **CognitiveDerivationEngine** — 48 new derivation rules across 12 methods. Tier 1 (6 facets: Anhedonia, Depressivity, Perseveration, Rigid Perfectionism, Distractibility, Separation Insecurity). Tier 2 (4 facets: Restricted Affectivity, Irresponsibility, Cognitive Perceptual Dysregulation, Eccentricity). Backfill: Deceitfulness (laterality, depth), Attention Seeking (arousal). Two facets (Submissiveness, Unusual Beliefs) enter the vocabulary without CDE rules — insufficient empirical support for cognitive processing effects.

3. **Classification pipeline** — `Pid5FacetsConfig` and `ClassificationCbrConfig` `@WithDefault` values extended to 25 facets. `AmpdAssessment` record in memory-seeding extended with 12 new Integer fields. `PersonalityProfileHandler` facet-to-property mapping extended.

4. **Testing** — 54 unit tests in `CognitiveDerivationEnginePid5FacetTest` (34 new). 4 integration tests in `Pid5FacetPipelineIntegrationTest` (resting vs stressed derivation, metadata enrichment, multicollinearity bounds).

### Cross-repo changes

Eidos changes committed on branch `issue-593-cognitive-dissonance` (the active eidos branch). This is a cross-repo dependency — the AmpdFacets.CANONICAL extension and archetype profile shifts need to reach eidos main via that branch's normal work-end.

### Follow-up filed

- **casehubio/neocortex#1242** — Add individual unit tests for 18 remaining CDE rules (XS/Low). Queued.

### What's next in queue

- casehubio/neocortex#1065 — RelationalSchema-role-hierarchy
- casehubio/neocortex#1091 — MindMapQuery-property-filtering

### Design artifacts

- Spec: `docs/specs/issue-1076-pid5-facet-situational-attr/2026-11-26-pid5-facet-extension-design.md`
- Decisions: `docs/specs/issue-1076-pid5-facet-situational-attr/decisions.md`
- Literature review: `docs/specs/issue-1076-pid5-facet-situational-attr/explorations/D2-situational-modulation-literature.md`
- Plan: `wsp-casehub-neocortex/plans/2026-11-26-pid5-facet-extension.md`

### Key constraint for future sessions

NA facet coefficients in the CDE are capped at ±0.1 (Perseveration exempted at 0.15 for fixation — documented). If additional NA facets are added, verify multicollinearity bounds via `Pid5FacetPipelineIntegrationTest.multicollinearity_extremeNegativeAffectStaysBounded()`. CDE is now 1,420 lines — structural decomposition follow-up at 1,500.

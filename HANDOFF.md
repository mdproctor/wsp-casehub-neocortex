# HANDOFF — casehub-neocortex

## Current Session (2026-11-18, session 3)

**Appraisal feedback loop complete — 4 issues landed, #1056 active.**

This session closed the gap between what the situational personality system knows and what the appraisal pipeline sees. Four issues (#1068, #1084, #1083, #1059) plus a code review fix. Work-end landed 4 prior done items (#1132, #1082, #1135, #1138) but hit rebase conflicts against canonical.

### What was completed

| # | Issue | Type | What |
|---|-------|------|------|
| #1068 | Facet prompt clause | feat | `LivedComposition` encodes baseline in origin: `"situational [usual 0.62]"`. LlmAppraisalStrategy system prompt explains situational facets. |
| #1084 | PipelineTrace snapshot | feat | `SituationalPersonalitySnapshot` on PipelineTrace — mode intensities, winners, facet displacements, published count. `currentSnapshot()` accessor on participant. |
| #1083 | RelationalSchemaResolver | feat | Extracts real trust from MindMap overlay nodes. `TrustAccessor` interface on participant replaces hardcoded 0.0. Wired via CognitionCore. |
| #1059 | CARMA SEC + ShadowArchetype | feat | `SituationalModeContext` on `AppraisalContext`. `ShadowArchetypePromptSection` (`BlockTag.SITUATIONAL`, Tier 1). Mode guidance in LLM system prompt. Gated on `situationalPersonalityEnabled`. |
| — | Code review fix | fix | `Locale.ROOT` in LivedComposition origin format. CognitionCore null-ternary readability. |

Also fixed pre-existing: `DispositionSignalWriterTest` compile error (`activationCounts` → `activationWeights`).

### Issues filed this session

| # | Title | Scale | Notes |
|---|-------|-------|-------|
| #1145 | Delegate AppraisalTickParticipant.resolveRelationalSchema | XS | Duplicated logic after #1083 created shared resolver |
| #1146 | TrustAccessor test coverage | XS | No unit test exercises non-null TrustAccessor path |

Both scheduled in queue.

### NOT_LANDED — rebase conflicts

Work-end ceremony closed #1132/#1082/#1135/#1138 in the queue but could not land to canonical:

| Repo | Conflict |
|------|----------|
| `neocortex:main` | `EidosLivedDispositionSource.java` + test — canonical main moved |
| `wsp-casehub-mosaic:main` | HANDOFF.md |
| `wsp-casehub-neocortex:main` | blog/INDEX.md |
| `wsp-casehub-neocortex:issue-1130/...` | Unstaged changes in workspace |

**Next session must resolve these conflicts before any new work lands.** Run `close.py` again after resolving.

### Queue status (position 28/34, 5 remaining + 2 filed)

| Pos | # | Title | Scale | Complexity | Notes |
|-----|---|-------|-------|------------|-------|
| 1 | #1056 | Biographical extraction of situational profiles | M | Med | **Active.** Unblocked (eidos#234 landed). Python extraction scripts. |
| 2 | #1058 | Shadow narrative frame: attractor classification | M | High | BehavioralSynthesisPhase attractor annotation |
| 3 | #1057 | Temporal archetype salience across life phases | M | High | Open design questions |
| 4 | #1076 | PID-5 facet extension for situational attractors | M | High | 12 missing facets; literature review |
| 5 | #1145 | Delegate resolveRelationalSchema | XS | Low | Code review finding |
| 6 | #1146 | TrustAccessor test coverage | XS | Low | Code review finding |

### Key design decision revised

**Implicit → implicit + optional explicit.** The 712 spec originally chose implicit-only modulation. #1059 added `ShadowArchetypePromptSection` for explicit mode rendering, gated on config. The constraint: "do not comment on or explain it" — prevents self-narration. Research doc updated.

### Blog

"The appraiser that knew it was afraid" — covers the full session narrative. SVG diagram of the appraisal data flow. Promoted to project.

## Prior Sessions

**2026-11-18, session 2:** 4 issues completed (#1132, #1082, #1135, #1138) — EidosLivedDispositionSource, CDI wiring, AMPD facet composition, narrative cap fix. Shadow archetype chain scaffolded.

**2026-11-17/18, session 1:** #1060 design — unified personality evolution. Brainstorming, adversarial review (4 dimensions), 14-task plan.

**Earlier:** Epic #1090 bug fix sweep — 7 issues resolved. Prior queue of 24 items fully drained across multiple sessions.

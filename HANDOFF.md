# HANDOFF — casehub-neocortex

## Last Session

Landed #1216 (XS — replaced hand-rolled JSON parser with Jackson ObjectMapper in `DissonanceDetectionPhase.parseCapsActivations()`). Began setup for #1219 but hit pipeline bugs (filed as Hortora/soredium#633). Manually recovered: created branch, fixed queue, unblocked pipeline.

**Landed:** #1216 on main (1 commit, SHA 5fa5bde8). Branch stamped and closed.

**Infrastructure note:** 32 commits in `~/claude/public/casehub/neocortex` are unpushed. `canonical_sync.py publish neocortex` fails with a doubled-path bug (`neocortex/neocortex/soredium-landing.lock`). Needs manual investigation or a soredium fix.

## Queue State

Branch `issue-1219-briefed-cognitive-avatars` active. Project and workspace both on the branch.

- **#1219** (Briefed personality profiles — practical coach/mentor/assistant personas — M/Med) — **active**, branch created, brainstorming not yet started

## What #1219 Is

Split neocortex's existing capabilities into two tiers and surface the practical tier via pre-built persona profiles:

| Practical tier (this issue) | Experimental tier (existing cognition stack) |
|---|---|
| Static disposition from YAML | Personality evolution from experience |
| Briefing-based persona ("think like Marcus Aurelius") | Emergent identity from CAPS attractors |
| Echo/self-prompting before key decisions | Inner life, proactive reflection |
| Goal decomposition shaped by stated preferences | Goal formation from drive activation |
| Session 1 = Session 100 | Session 100 ≠ Session 1 |
| No tick loop, no consolidation, no experience recording | Full consolidation pipeline |

## Design Intent (from user)

The core insight: **briefing works well, and we already have memory, goals, temporal awareness, and urgency/focus machinery.** The aim is to build lightweight briefed cognitive avatars that can use:

- **MindMap** — GOAL subgraph, knowledge graph, entity awareness
- **Cognitive goals** — decomposition, prioritisation, resolution, urgency
- **Temporal focus** — awareness of now/yesterday/future, creating urgency
- **Memory** — CaseMemoryStore for cross-session persistence, consolidation for long-term retention
- **CognitiveDefaults/CognitiveDerivationEngine** — disposition→planning config derivation (subset of pathways: skip mood, appraisal, habituation)
- **Faster cognitive drives** — goal-directed curiosity, competence, without the full CAPS/emotion pipeline

What it does NOT include: emergent emotions, CAPS settling, mood tracking, personality evolution, appraisal (SEC dimensions), inner life, proactive speech.

## Key Design Decisions Still Needed

1. **Module structure** — new module(s) or composition of existing modules with config flags?
2. **Persona library format** — extend existing `cognitive-profiles/*.yaml` or new `personas/*.yaml`?
3. **Echo/self-prompting mechanism** — how persona principles surface at decision points
4. **Profile composition** — how base avatar (coach/mentor/assistant) + personality overlay (Marcus Aurelius, etc.) compose
5. **Prompt rendering** — which existing `CognitionPromptRenderer` sections to reuse vs new briefing-only renderers
6. **Distribution boundary** — what lives in neocortex vs the MCP server (#360 on connectors)

## Existing Infrastructure to Audit

The brainstorming session should audit these for practical-tier eligibility:

| Module | Practical? | Why |
|--------|-----------|-----|
| `cognitive-index/CognitiveDefaults` + `CognitiveDerivationEngine` | Yes | Static config derivation from YAML profiles |
| `cognitive-index/CognitiveProfile` | Yes | Cross-store entity resolution |
| `cognitive-index/TemporalFocus` | Yes | Now/yesterday/future awareness |
| `mindmap-api` + `mindmap-intelligence` goals | Yes | Goal subgraph, decomposition, prioritisation |
| `memory-api` CaseMemoryStore | Yes | Cross-session persistence |
| `cognition-api` prompt renderers | Subset | Goal, temporal, drive sections — not mood/appraisal/inner-life |
| `cognition` CognitionCore tick loop | No | Too heavy — needs replacement with static composition |
| `caps-*` | No | Emergent behavior, not briefed |
| `cognition` CARMA appraisal | No | Emotion pipeline |

## Learned Techniques to Apply

- **Echo-back for staying in character**: "Think and respond how Marcus would" keeps the persona consistent across turns. Validated in prior work.
- **Briefing over emergence**: Static persona briefing produces consistent, predictable behavior. The persona shapes reasoning style without the system trying to become that persona.
- **Disposition as planning config**: Risk appetite, rule-following, social orientation → conservative vs aggressive goal decomposition, solo vs collaborative approaches.
- **Layered approach**: Start practical, then optionally compose in deeper cognition. The practical base should work at conversation level first, with optional enrichment over time.

## Immediate Next Step

Run `work continue`. The pipeline will route to `load_context`. Complete it, then proceed with brainstorming for #1219 — context gathering, clarifying questions, approach exploration, decisions, spec.

## References

- casehubio/neocortex#1219 — the issue (M/Med, well-scoped body with architecture section)
- `cognitive-index/src/main/java/.../CognitiveDefaults.java` — per-agent config from YAML
- `cognitive-index/src/main/java/.../CognitiveDerivationEngine.java` — disposition→config derivation
- `cognitive-index/src/main/java/.../CognitiveDefaultsRegistry.java` — classpath scan for profiles
- `cognition/src/main/resources/cognitive-pipeline-defaults.properties` — pipeline config reference
- `mindmap-intelligence/src/main/java/.../consolidation/GoalResolutionPhase.java` — goal management
- `mindmap-intelligence/src/main/java/.../InformationGapDetector.java` — curiosity/gap detection
- Hortora/soredium#633 — pipeline bug filed this session (workspace branch stranding)

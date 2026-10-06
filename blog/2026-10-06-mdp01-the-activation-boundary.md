---
title: "The activation boundary — when code exists but can't be reached"
date: 2026-10-06
author: mdp
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
series: issue-438-neocortex-audit-wiring
tags: [cdi, quarkus, audit, cognitive-architecture, wiring]
---

The neocortex codebase had a pattern I hadn't expected. A root-to-tip audit revealed that the newer cognitive subsystems — CARMA appraisal, gut feeling, behavioral synthesis, domain activation, mood persistence, attention signaling — were all fully implemented. Individually tested. Correctly structured. And completely dead in production.

The gap wasn't missing code. It was missing annotations. `BeliefRevisionPhase` had `@Priority(16)` but no `@ApplicationScoped` — CDI never discovered it. `CognitiveAttentionAccumulator` had `onAffectRecorded()` and `onExperienceRecorded()` methods ready to receive events, but without `@Observes` on the parameters, no events ever arrived. `HeuristicGoalAppraisal` implemented `GoalAppraisal` but without `@DefaultBean`, `Instance<GoalAppraisal>` was unresolvable — the entire OCC appraisal path was unreachable.

I'm calling this the activation boundary. The code crosses it when it becomes discoverable by the runtime. In a CDI world, that boundary is a set of annotations. Miss one and the class compiles, passes its unit tests, looks correct in every review — and does nothing in production.

The fix for 19 of the 20 audit findings landed in a single session. Most were surgical: add `@ApplicationScoped`, add `@Inject`, wrap optional dependencies in `Instance<T>` with `.isResolvable()` fallback. The established pattern from `ExperienceConsolidationPhase` — CDI constructor for production, package-private constructor for tests — applied cleanly everywhere.

Three fixes had more substance. The attention mediator had a double-drain bug: `CognitionCore.tick()` polled the attention queue, then `CognitiveProfileParticipant` tried to poll the same queue and got nothing. The fix was to snapshot the briefing into `CognitionTickContext` so both consumers read the same data without competing for it. The consolidation scheduler was passing `List.of()` as its artifact list — the `ConsolidationPhase` SPI had `signals()` but no `artifacts()` method, so phases couldn't report what they produced. And `CuriositySignalGenerator` was passing subgraph UUIDs where `SchemaDiscoveryPhase` expected type strings like "person" or "cognitive" — a rename from `targetSubgraphId` to `targetSubgraphType` with `sg.type()` instead of `sg.id()` fixed it.

The CARMA appraisal wiring is the one fix that spans repos. The neocortex side is complete — `configureAppraisal()`, `configureGutFeeling()`, and `setMoodPersister()` all exist and work. Blocks needs to call them. That's blocks#333.

One item deferred: removing the dead `habituationEnabled` config flag from `CognitionConfig`. The record has 23 positional boolean parameters, and removing one means carefully counting position in 25+ constructor calls. Mechanical, but error-prone without stable tooling.

What this session exposed is that audit-driven work has a different shape than feature work. No brainstorming needed — the design is "fix what the audit found." No novel architecture — the patterns are established. The value is in systematic execution: tier the fixes by dependency, land them in order, verify each one compiles and passes. The creative work happened during the audit itself; this session was about making the findings real.

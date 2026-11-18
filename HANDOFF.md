# HANDOFF — casehub-neocortex

## Current Session (2026-11-17/18)

**#1060 — Unified Personality Evolution: design complete, implementation planned, not yet started.**

This session completed brainstorming, adversarial design review (4 dimensions × 3 rounds, $63.46), and implementation planning. No code has been written. The next session picks up with `executing-plans` on the 14-task plan.

### What was decided

The original issue asked: wire `PersonalityEvolutionOrchestrator` into the lifecycle, fix propagation, decide evolution cadence. The design process escalated scope based on first-principles analysis and adversarial review:

1. **Store of record: Option (A) — neocortex stores lived personality state.** Eidos keeps authored identity only. No Eidos prerequisites needed. Single-owner writes. Boot-safe by construction. All three review dimensions and cross-cutting recommended this.

2. **The original unified signal model was rejected.** The adversarial review proved JPAF and PID-5 have genuinely different accumulation and evaluation dynamics (JPAF: discrete type transitions via Eidos SPIs; PID-5: continuous elastic-band drift via integrator). They share only outcome infrastructure: store of record, propagation, cadence, audit.

3. **Pull model replaces push (D25).** `EffectiveCognitiveDefaults.updateState()` is deleted entirely. `PersonalityStateService` (renamed from `SituationalStateService`) commits state via `transition()`. `EffectiveCognitiveDefaults` lazily re-derives when `compositionVersion` changes — a quantised freshness counter on `PersonalityStateSnapshot`.

4. **Eidos SPIs preserved for JPAF evaluation (D6).** `DispositionHealth.probe()` and `DispositionEvolution.evaluate()` stay in Eidos. Neocortex owns the cadence (when to reflect) and the result storage (where the lived profile goes). The existing PEO's safety mechanisms (halt flag, L2 ceiling) are replaced by D24: rc-scaled rate bound on committed transitions only. The halt was proven to never prevent a transition and to block legitimate evolution (verified against Eidos code).

5. **Target anchoring (D23).** Signal recording targets the **authored** profile, not the lived one. Positive → authored dominant, negative → authored auxiliary. This prevents the rank-relative A→B→A limit cycle the review discovered in the original PEO design.

6. **30 decisions total** across 6 review rounds. See `specs/issue-1060-personality-evolution-orchestrator-never-ticked/decisions.md` for the full list.

### Key architectural insight the review uncovered

The adversarial review discovered three false premises in the original spec:
- That nothing writes `homeOffset` (it does — `PersonalityStateIntegrator.closeHour()`)
- That `updateBase()` is a durable propagation path (it's overwritten every tick by CognitionCore)
- That JPAF evaluation is simple enough to reimplement (it has four rules, vocabulary shadows, tenant preferences, canonical normalisation — all in Eidos)

The reviewed design respects these realities instead of fighting them.

### What was produced

| Artifact | Path | Status |
|----------|------|--------|
| Decisions (6 brainstorming + 24 review) | `wsp/specs/issue-1060-.../decisions.md` | Complete |
| Design spec (rev 2 + 12 review rounds) | `wsp/specs/issue-1060-.../2026-11-17-unified-personality-evolution-design.md` | 1403 lines, 0 open issues |
| Implementation plan | `wsp/plans/2026-11-18-unified-personality-evolution.md` | 14 tasks, 6 batches |
| Pipeline state | `wsp/specs/issue-1060-.../pipeline.state` | PLANNING |
| Review workspaces | `~/reviews/casehub-slots/unified-personality-evolution-{coherence,structure,robustness,crosscutting}-*` | All DONE |

### Implementation plan summary

6 batches, each a safe wrap point:

| # | Batch | Tasks | Key deliverables |
|---|-------|-------|-----------------|
| 1 | Foundation | 3 | `PersonalityStateService` (rename + striped locking + `transition()` API), `ReflectionLedger`, `TenantAgentKey`, `DispositionEvolutionConfig`, `ReflectionOutcome`, `PersonalityStateSnapshot` additions, `FacetState` additions, `DynamicsConfig` promotion fields |
| 2 | Composition | 2 | `LivedComposition` (fingerprint/compose), `LivedProfile`, pull model in `EffectiveCognitiveDefaults` (delete `updateState`, `compositionVersion` freshness), `PersonalityStateSource.compositionVersion()` |
| 3 | Signals | 2 | `IsolatedTransactions` SPI, `DispositionSignalWriter` (coalescing buffer, striped locks), `DispositionSignalRecorder` (CDI observer), `InteractionAppraised`, `InteractionPressureSource`, `TraitActivation` loses valence, `CognitionCore.recordInteraction` changes |
| 4 | PID-5 | 2 | `PersonalityStateIntegrator.promotionCandidates()`, `SituationalDeformationPhase` @Priority(46) + promotion step |
| 5 | JPAF | 2 | `EidosCognitiveProfileBridge.livedDescriptor()`, `LivedDescriptors`, `DispositionEvolutionPhase` @Priority(50) (full algorithm: recovery, wall-clock gate, epoch tracking, decay, evaluation, commit, rate bound, reversal detection, authored edit handling) |
| 6 | Wiring | 3 | `CognitionDefaultBeans` producers, delete `PersonalityEvolutionOrchestrator` + `EvolutionTick` + `PersonalityEvolutionConfig` + `DefaultPersonalityStateSource`, `SignalCategory.PERSONALITY_EVOLVED`, integration + E2E + 240-day trajectory tests |

### Critical context for the implementing session

**The spec has changed dramatically from the initial brainstorming output.** The implementing session MUST read the reviewed spec, not rely on the initial design decisions. Key differences:
- No unified `PersonalityPressure` signal type — the review killed this
- `updateState` is deleted, not called — pull model via `compositionVersion`
- Eidos SPIs are preserved, not replaced — the review proved reimplementation would be incorrect
- The halt mechanism is deleted, not preserved — it was proven useless
- `PersonalityEvolutionOrchestrator` is deleted entirely — logic split into 3 classes

**Striped locking is load-bearing.** `PersonalityStateService` and `DispositionSignalWriter` each have their own 256-stripe `ReentrantLock[]` arrays. Never evicted (D26). The interleaving test from §[S2] is the correctness gate.

**The reflection ledger is the JPAF brain.** 11 fields persisted as `jpaf.*` properties on the PERSONALITY_STATE MindMap node. `pendingEvolution` enables crash recovery. `epochFingerprint` enables authored-edit detection. `reversalStreak` enables oscillation detection. All are components of `PersonalityState`, not a separate store (D12).

**Prerequisites that must land first:**
- **#1082** (situational participant wiring) — hard for PID-5 promotion in production
- **#1063** (scheduler starvation fix) — hard for consolidation phases to run reliably

**Same-change-window coordination:**
- **agency#487** — remove PEO producers from `AgencyBeans`/`AgencyAutoConfiguration`, wire new beans

### Deferred review items

28 items deferred across 4 dimensions. Most are covered by existing follow-up issues:
- eidos#242 (swap dead zone) — multiple structure and cross-cutting items
- #1104 (single-instance deployment) — robustness items about multi-instance races
- #1089 (cache eviction) — multiple coherence items about unbounded growth
- #1102 (valenced signals) — coherence items about NEUTRAL-only production signals
- #1107 (verify R3 amendments) — post-collapse spec verification

See `~/reviews/casehub-slots/unified-personality-evolution-*/tracker.md` for full details.

### Follow-up issues (all already filed)

| Issue | Repo | What | Blocking? |
|-------|------|------|-----------|
| #1082 | neocortex | Situational participant registration | Hard prereq for PID-5 |
| #1063 | neocortex | Scheduler starvation + restart tenant loss | Hard prereq for production |
| #1102 | neocortex | Valenced relationship/goal signals | Not blocking (InteractionAppraised carries live valence) |
| #1104 | neocortex | Single-instance deployment contract | Not blocking |
| #1107 | neocortex | Verify R3 design amendments after collapse | Not blocking |
| #1089 | neocortex | Cache eviction | Not blocking |
| #487 | agency | Remove PEO producers, wire new beans | Same change window |
| #235 | eidos | Registry-backed DispositionProfileStore | NOT needed under Option (A) |
| #237 | eidos | Fractional activation weights | Not blocking |
| #239 | eidos | Canonical AmpdFacet names | Not blocking (hygiene) |
| #241 | eidos | Signal store concurrency | Not blocking |
| #242 | eidos | Swap dead zone | Not blocking |

### Branch and workspace state

- **Project repo** (`neocortex`): on branch `issue-1060/personality-evolution-orchestrator-never-ticked`, branched from main at `df376ad35`. No code changes yet — branch is at same commit as main. One unstaged file: `docs/blog/images/search-then-filter-data-loss.svg` (from prior session, cosmetic).
- **Workspace repo** (`wsp-casehub-neocortex`): 49 commits ahead of `local/main` (design review artifacts). Contains the spec, decisions, plan, and pipeline state. Queue has #1060 active with 14 injected tasks.

## Prior Session

Epic #1090 bug fix sweep — 7 issues resolved, 3 commits landed on main (df376ad35). See prior handoff for details.

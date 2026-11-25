# HANDOFF — casehub-neocortex

## Active Work: Cognitive Pipeline Coherence (#1220)

A comprehensive review (107 findings across 9 sections) identified systemic issues in the cognitive pipeline. These are organized into 7 sub-epics. 3 done, 4 remain — all can run in parallel.

**Progress:** 26 of 107 findings fixed. 8 partially addressed. 65 still valid.

### How to pick up any sub-epic

1. Read the **issue** on GitHub (`casehubio/neocortex#NNNN`) — it has the goal, modules, file list, and child issues with finding references
2. Read the **epic plan** in the project: `docs/specs/cognitive-review-analysis/2026-11-24-epic-plan.md` — it has the dependency graph, module ownership, and child issue details for all 7 sub-epics
3. Read the **triage** for context on each finding: `docs/specs/cognitive-review-analysis/2026-11-24-cognitive-review-triage.md` — categorised findings with fix status
4. Run `work start #NNNN` to create a branch and plan the work. The epic plan has enough detail for each child issue to write an implementation plan directly — brainstorm only if the approach is unclear

### Status

| Sub-epic | Issue | Status | Module | Findings remaining |
|----------|-------|--------|--------|--------------------|
| SE1: Pipeline Spine | #1221 | **Done** (closed) | cognition core | 0 (+2 deferred: #1231, #1232) |
| SE2: CAPS Rework | #1222 | **Open** | caps-engine, caps-testing, caps-llm-classifier, caps-situation-cbr | 8 |
| SE3: Storage & Data Integrity | #1223 | **Done** (closed) | memory-sqlite, mindmap-sqlite, mindmap | 0 |
| SE4: Consolidation Phases | #1224 | **Open** | mindmap-intelligence | 9 |
| SE5: cognitive-index | #1225 | **Done** (closed) | cognitive-index | 0 (D5 parked as design disagreement) |
| SE6: Affect & Emotion | #1226 | **Open** | cognition (mood/drive/appraisal/regulation) | 14 |
| SE7: Orchestrators | #1227 | **Open** | cognition (goal/narrative/personality/hygiene) | 10 |

**Cross-repo:** #1228 (vocabulary alignment with eidos) — coordinate with eidos repo.

### Parallelism rules

All 4 open sub-epics touch different Maven modules or different files within the same module. They can run in separate slots with zero merge-conflict risk. The only constraint:

- **SE2 and SE4 share 2 files** in mindmap-intelligence: `BehavioralSynthesisPhase.java` and `ClassificationOutcomeEvaluator.java` belong to SE2 exclusively. SE4 owns all other files in `mindmap-intelligence/consolidation/`.
- **SE6 and SE7** are both in the cognition module but touch completely different subdirectories. No file overlap.

### What SE1 changed (context for downstream work)

- `CognitionConfig` is now an `EnumSet<Subsystem>` class — `all()` enables everything. Downstream code should use `config.isEnabled(Subsystem.X)` or the backward-compatible `config.xEnabled()` accessors. Tests that need a subset should build from `CognitionConfig.none().with(...)`.
- `CognitionCore` has per-agent state via `ConcurrentHashMap<AgentKey, PerTickState>`. Use `promptSections(agentId, tenantId)` not the no-arg overload. The volatile `last*` fields still exist as a working set but are populated from the per-agent map.
- Appraisal-to-mood/drive bridging only runs when `observation != null`. No-observation ticks don't re-bridge stale state.
- `CognitivePipelineBuilder.build()` now calls `configureTheoryOfMind()` and wires `configureCognitiveMemoryRetriever` before `configureGutFeeling`.

### What SE5 changed (context for downstream work)

- `CognitiveMemoryRetriever.tickContext` is now a `ConcurrentHashMap<String, ModulationContext>` keyed by agentId. Use `query(MemoryQuery, String agentId)` for agent-scoped lookups. The no-arg `query(MemoryQuery)` falls back to default context (no agent-specific modulation). `CognitionCore.tick()` already calls `setTickContext()` with agentId — downstream orchestrators that call the no-arg `query()` should migrate to the agent-aware overload when feasible.
- `AffectTrajectoryDecorator` now stores the agent's `PrincipalId` on affect memories when the updated node is an overlay (has `OverlayRef.AGENT_ID` property). Shared node updates remain unowned. `CognitiveProfile.computeTrajectory()` already filters by `callerPrincipalId` via `queryMemories()`.
- `CognitiveDerivationEngine.isLow()` now returns `false` for absent PID-5 facets (was `true`). `deriveExpressionStyles()` no longer triggers LOW-facet branches for absent facets — absent = neutral.

### Recommended next sub-epic

**SE4 (Consolidation Phases, #1224)** — several findings were pre-fixed by mechanical patches (triage marks them), so effective scope is smaller than the 9-finding count suggests. Fully isolated in `mindmap-intelligence`. Reduces open count to 3.

| Sub-epic | Scale | Approach |
|----------|-------|----------|
| SE2 | L | 4 child issues. CAPS settler math is subtle — read the topology YAML and settler code carefully. B1 (unipolar baseline) is the most impactful fix. |
| SE4 | L | 4 child issues. Many consolidation phases need fixes. Some findings (A9, F9, F10, F2, F15) were already fixed by pre-SE1 mechanical patches — the triage doc marks these. |
| SE6 | L | 4 child issues. Mood clamping (C2) and drive modulation (C6) are the most impactful. C15 (RELIEF sign) was already fixed. The double drives.tick() fix from SE1 is partial — C8 full fix belongs here. |
| SE7 | L | 5 child issues. E1 (gate thresholds) and E8 (retention score floor) are the most impactful. |

## References

- **Parent epic:** casehubio/neocortex#1220
- **Epic plan:** `docs/specs/cognitive-review-analysis/2026-11-24-epic-plan.md`
- **Triage:** `docs/specs/cognitive-review-analysis/2026-11-24-cognitive-review-triage.md`
- **Review source:** `https://raw.githubusercontent.com/mdproctor/neocortex/refs/heads/claude/magical-sagan-5e2uum/docs/research/2026-11-22-cognitive-review/REVIEW.md`

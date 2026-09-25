# Progressive Cognitive Attention Model — Design Spec

**Issue:** casehubio/neocortex#381
**Date:** 2026-09-25
**Scale:** XL | **Complexity:** High
**Status:** Draft

---

## 1. Problem Statement

Cognitive agents need to operate continuously — not just respond to prompts.
The consolidation scheduler runs on a daemon thread computing goal priority,
urgency, affect, and decay. But there is no mechanism to bridge from
"consolidation detected something significant" to "the LLM should reason
about this now."

Current state: `ConsolidationCompleted` carries only
`PhaseResult(phaseName, success, error)`. The phases compute insights
(urgency spikes, goal decay, OCC emotions, new recognitions) but don't
expose them. The LLM learns nothing until the next human prompt triggers
a cognitive tick. For long-running agents, the gap between "the system
knows something changed" and "the LLM reasons about it" can be hours.

## 2. Design Principles

- **Event-driven, not scheduled.** Extend the SignificanceAccumulator
  threshold-crossing pattern. No parallel scheduling system. Scheduled
  briefings (morning wake) can be layered later at the runtime level.
- **Per-principal attention.** Each agent gets independent accumulation
  and briefings, matching the cognitive profile architecture.
- **Push gives awareness, pull gives depth.** Briefings carry ranked
  signals (AttentionItem-style). The agent pulls detail via existing
  APIs (CognitiveProfile.resolve, MindMapStore.search).
- **CognitionCore is the convergence point.** Both tick-based agents
  (wacky-manor) and idle agents drain attention through CognitionCore.
  No separate listener path.
- **Platform consolidation.** Design for wacky-manor to delete custom
  cognitive code (CognitiveBudget, ManorConsolidationBeans manual wiring,
  CharacterCognition section rendering) and use platform features.
- **Post-#303 aligned.** Layer placement follows the blocks#303
  reorganization: cognitive state computation in neocortex, orchestration
  and prompt assembly in blocks.

## 3. Architecture

### 3.1 Four components, two signal paths

```
                CONSOLIDATION PATH                    REAL-TIME PATH
                +-------------------+
                | ConsolidationPhase |
                |   .run()           |
                |   .signals() ------+--+
                +-------------------+  |         ExperienceRecorded --+
                                       |         AffectRecorded ------+
                                       v         GoalLifecycle -------+
              +----------------------------+                          |
              | CognitiveAttentionAccumulator |<-----------------------+
              |   per-principal state         |
              |   adaptive threshold          |
              |   minimum interval guard      |
              +------------+---------------+
                           | threshold crossed
                           v
              +------------------------+
              | CognitiveAttentionRequired |  CDI event (neocortex)
              |   AttentionBriefing        |  (per-principal, ranked signals)
              +------------+-----------+
                           |
              +----------------------------+
              | CognitiveAttentionMediator   |  blocks (@ApplicationScoped)
              |   @Observes event            |
              |   per-principal queues       |
              +------------+-----------+
                           |  drainAttention()
              +------------v-----------+
              | CognitionCore            |  blocks (POJO, per-agent)
              |   lastBriefing field     |
              +------+----------+------+
                     |          |
            +--------v--+ +----v-------------+
            | tick()     | | Push receiver     |
            | stores     | | (wakes idle agent,|
            | briefing   | | then drains)      |
            +------------+ +------------------+
```

### 3.2 Layer placement

| Component | Layer | Module |
|---|---|---|
| AttentionSignal, AttentionBriefing, SignalCategory | neocortex | mindmap-api |
| CognitiveAttentionRequired CDI event | neocortex | mindmap-api |
| ConsolidationPhase.signals() default method | neocortex | mindmap-intelligence |
| CognitiveAttentionAccumulator | neocortex | mindmap-intelligence |
| Modified consolidation phases (6) | neocortex | mindmap-intelligence |
| CognitiveAttentionMediator (CDI observer + queue) | blocks | blocks-core |
| CognitionCore attention prompt section | blocks | blocks-core |
| Modified blocks phases (3) | blocks | blocks-core |
| Push receiver (idle agent wake) | blocks/runtime | out of scope |

### 3.3 Dependency direction (unchanged)

```
mindmap-api (types)    cognitive-index (CognitiveDefaultsRegistry)
    ^                       ^
    +--------+--------------+
             |
mindmap-intelligence (accumulator, phases, scheduler)
             ^
blocks-core (CognitionCore, mediator, blocks phases)
```

mindmap-intelligence already depends on cognitive-index (existing
dependency in pom.xml). No new cross-module edges introduced.

### 3.4 Post-#303 alignment

After blocks#303 migrates orchestrators (Mood, Drive, Narrative, etc.)
to neocortex, they can emit attention signals directly to the accumulator
without crossing a CDI boundary — same module. The ConsolidationPhase SPI
is already in neocortex, so blocks phases that implement it produce signals
the same way regardless of which repo they live in. No rework needed.

## 4. AttentionSignal Type System

### 4.1 AttentionSignal

```java
package io.casehub.neocortex.mindmap;

public record AttentionSignal(
    String principalId,
    String tenantId,
    SignalCategory category,
    String sourceNodeId,
    String sourceName,
    double significance,
    String reason
) {}
```

**Relationship to AttentionItem.** AttentionItem (cognitive-index) wraps
a TemporalEntry with a salience score — it is a *snapshot* of what the
agent should focus on right now (steady-state ranking via
TemporalFocus.focus()). AttentionSignal is a *change event* — it
represents something that just changed and contributes to
threshold-crossing for attention. They operate at different abstraction
levels: AttentionItem has no category, principalId, or tenantId;
AttentionSignal has no TemporalEntry. A shared base type would force
artificial coupling between the temporal-focus query path and the
attention accumulation event path. The distinction is deliberate.

### 4.2 SignalCategory

```java
public enum SignalCategory {
    URGENCY_SPIKE,
    DECAY_DETECTED,
    GOAL_RECOGNIZED,
    BLOCKER_RESOLVED,
    PRIORITY_SHIFT,
    AFFECT_CHANGE,
    MERGE_CANDIDATE,
    EXPERIENCE_GRADUATED,
    DRIVE_SHIFT,
    RELATIONSHIP_STAGE,
    BELIEF_REVISED
}
```

Categories cover both neocortex phases (URGENCY_SPIKE through
EXPERIENCE_GRADUATED) and blocks phases (DRIVE_SHIFT through
BELIEF_REVISED). All live in mindmap-api so phases in any module can construct
signals without introducing reverse dependencies.

### 4.3 AttentionBriefing

```java
public record AttentionBriefing(
    String principalId,
    String tenantId,
    List<AttentionSignal> signals,
    double urgencyP75,
    Instant generatedAt
) {
    public List<AttentionSignal> topN(int n) {
        return signals.subList(0, Math.min(n, signals.size()));
    }
}
```

### 4.4 CognitiveAttentionRequired

```java
public record CognitiveAttentionRequired(
    AttentionBriefing briefing,
    Instant firedAt
) {}
```

CDI event fired by the accumulator. The neocortex-to-blocks boundary.

## 5. ConsolidationPhase SPI Evolution

### 5.1 New default method

```java
public interface ConsolidationPhase {
    String name();
    void run(String tenantId, List<String> subgraphPriority);
    default void beginTick() {}
    default List<AttentionSignal> signals() { return List.of(); }
}
```

Fully backward compatible. Existing phases return empty until
individually updated. Phases accumulate signals during `run()`,
caller reads via `signals()` after `run()` completes. The
`signals()` method uses **drain semantics**: it returns accumulated
signals and clears internal state. This is required because
`ConsolidationScheduler.tick()` calls `beginTickAllPhases()` once
then iterates tenants — without drain, tenant B's `signals()` call
would include tenant A's signals (cross-tenant leakage).

### 5.2 Phase implementation pattern

```java
public class GoalPrioritizationPhase implements ConsolidationPhase {
    private final List<AttentionSignal> pendingSignals = new ArrayList<>();

    @Override public void beginTick() { pendingSignals.clear(); }

    @Override public void run(String tenantId, List<String> subgraphPriority) {
        // existing priority computation...
        // when urgency spike detected:
        pendingSignals.add(new AttentionSignal(
            principalId, tenantId, SignalCategory.URGENCY_SPIKE,
            node.id(), node.name(), urgency,
            "urgency rose to " + urgency));
    }

    @Override public List<AttentionSignal> signals() {
        var result = List.copyOf(pendingSignals);
        pendingSignals.clear();
        return result;
    }
}
```

### 5.3 Signal production by phase

| Phase | Signal categories | Notes |
|---|---|---|
| GoalPrioritizationPhase | URGENCY_SPIKE, PRIORITY_SHIFT, DECAY_DETECTED | Already computes urgency + priority + decay |
| GoalAffectPhase | AFFECT_CHANGE | OCC appraisal already runs |
| GoalRecognitionPhase | GOAL_RECOGNIZED | Already creates goal nodes |
| GoalResolutionPhase | BLOCKER_RESOLVED | Already detects resolved deps |
| MergeDetectionPhase | MERGE_CANDIDATE | Already scores merge pairs |
| ExperienceConsolidationPhase | EXPERIENCE_GRADUATED | Already classifies graduates |
| SurfacingAggregationPhase | (none) | Data materialization for goal emotional queries |
| CuriosityRefreshPhase | (none) | Curiosity is pull-based |
| AccessFrequencyPhase | (none) | Bookkeeping |
| SchemaDiscoveryPhase | (none) | Bookkeeping |
| CommunitySummaryPhase | (none) | Background maintenance |
| DriveAdaptationPhase (blocks) | DRIVE_SHIFT | When drive intensity changes |
| RelationshipStagePhase (blocks) | RELATIONSHIP_STAGE | When familiarity stage changes |
| BeliefRevisionPhase (blocks) | BELIEF_REVISED | When belief revision fires |

### 5.4 Per-principal signal tagging

Consolidation phases iterate per-tenant (the existing granularity).
Most phases don't know which principal owns which goal. Convention:

- Phases that can resolve ownership (e.g. GoalPrioritizationPhase
  reads agent-id property on goal nodes) set `principalId` on the signal.
- Phases that cannot set `principalId = null`. The accumulator
  broadcasts null-principal signals to all principals in that tenant.

For multi-agent tenants, null-principal broadcast means agents may
receive signals from goals owned by other agents. This is acceptable
noise pre-#303: the minimum interval guard bounds the impact, and
attention signals are advisory (an irrelevant signal costs a few
tokens, not incorrect behavior). Post-#303, when orchestrators move
to neocortex and run per-principal (like DriveOrchestrator per
agentId), they set principalId directly, eliminating the broadcast.

### 5.5 Scheduler signal collection

`ConsolidationScheduler.runPhases()` collects signals after each phase:

```java
private void runPhases(String tenantId) {
    var allSignals = new ArrayList<AttentionSignal>();
    for (var phase : phases) {
        phase.run(tenantId, subgraphPriority(tenantId));
        allSignals.addAll(phase.signals());
    }
    if (!allSignals.isEmpty()) {
        attentionAccumulator.addSignals(allSignals);
    }
}
```

## 6. CognitiveAttentionAccumulator

### 6.1 Structure

```java
@ApplicationScoped
public class CognitiveAttentionAccumulator {

    private final ConcurrentHashMap<String, PrincipalAttention> perPrincipal
        = new ConcurrentHashMap<>();
    private final CognitiveDefaultsRegistry registry;
    private final MindMapStore mindMapStore;
    private final Event<CognitiveAttentionRequired> attentionEvent;
    private final Clock clock;
    private final ConcurrentHashMap<String, double[]> padCache
        = new ConcurrentHashMap<>();  // nodeId → [pleasure, arousal, dominance]

    static class PrincipalAttention {
        final ConcurrentLinkedQueue<AttentionSignal> pending
            = new ConcurrentLinkedQueue<>();
        volatile Instant lastPushAt = Instant.EPOCH;
        volatile double urgencyP75 = 0.0;
    }
}
```

**Threading model.** Three thread contexts access PrincipalAttention:
(1) daemon thread via `addSignals()` from ConsolidationScheduler
(behind its ReentrantLock), (2) CDI observer threads via real-time
`@Observes` methods (no lock), (3) threshold evaluation from either
context. `ConcurrentLinkedQueue` provides lock-free adds from any
thread. Threshold evaluation + fire + drain uses
`ConcurrentHashMap.compute()` on the principal key for atomicity.
`volatile` fields ensure visibility of `lastPushAt` and `urgencyP75`
across threads.

MindMapStore is needed for: (a) AffectRecorded observer — look up
current PAD values from the node to compute delta against cached
previous snapshot, and (b) goal-name cache for experience-to-goal
matching.

### 6.2 Accumulation from consolidation

`addSignals(List<AttentionSignal>)` — called by ConsolidationScheduler
after each tick. Groups signals by principalId, adds to per-principal
pending list, evaluates threshold.

### 6.3 Accumulation from real-time events

Three `@Observes` methods:

- **ExperienceRecorded** — uses `event.event().agentId()` for
  principal scoping. If `event.event().metadata()` contains a
  `"goal-node-id"` key, create a targeted signal (URGENCY_SPIKE or
  AFFECT_CHANGE) with that goal node as sourceNodeId. Experiences
  without explicit goal metadata do not produce attention signals
  directly — they contribute to attention only through the
  consolidation path (ExperienceRecorded → SignificanceAccumulator
  → consolidateNow() → phases detect goal-relevant changes →
  signals). This avoids polluting the attention threshold with
  undifferentiated activity.
- **AffectRecorded** — looks up the node's current PAD values via
  `mindMapStore.getNode(event.nodeId(), event.tenantId())` (reads
  `pleasure()`, `arousal()`, `dominance()` from the MindMapNode).
  Computes Euclidean distance against the cached previous snapshot
  in `padCache`. If delta exceeds a configurable threshold (default
  0.3), creates an AFFECT_CHANGE signal. Updates the cache entry
  after each comparison. Cache entries expire when not updated for
  two consolidation intervals.
- **Goal lifecycle** — polled at consolidation tick time (same cadence
  as urgency P75 refresh), not real-time observation.
  GoalLifecycleProvider is a `@FunctionalInterface` SPI, not an event
  source. When it returns changed state for a tracked goal, create
  BLOCKER_RESOLVED or DECAY_DETECTED.

### 6.4 Signal deduplication

An experience event can trigger both a real-time signal (via
`@Observes ExperienceRecorded`) AND a consolidation signal (via
`SignificanceAccumulator` → `consolidateNow()` → phase run). To
prevent double-counting, the accumulator deduplicates by
`(sourceNodeId, category)` within a single accumulation window
(pending signals not yet pushed). If a signal with the same
sourceNodeId and category already exists, the higher-significance
one wins.

### 6.5 Relationship to SignificanceAccumulator

CognitiveAttentionAccumulator runs **alongside** SignificanceAccumulator.
They serve orthogonal purposes:

- **SignificanceAccumulator** determines *when to consolidate* — it
  observes ExperienceRecorded, accumulates per-tenant significance,
  and triggers `consolidateNow()` when threshold is crossed.
- **CognitiveAttentionAccumulator** determines *when to notify the LLM*
  — it collects signals from consolidation phases and real-time events,
  and fires `CognitiveAttentionRequired` when threshold is crossed.

The primary interaction path is sequential:
ExperienceRecorded → SignificanceAccumulator → consolidateNow() →
phases run → signals() → CognitiveAttentionAccumulator.addSignals().
The real-time path supplements this for urgent signals that should not
wait for a full consolidation cycle.

Both accumulators independently observe ExperienceRecorded. CDI does
not guarantee ordering between independent observers, but none is
required — the two threshold mechanisms are independent. No feedback
loop exists: attention events do not generate new ExperienceRecorded
events.

Deduplication (§6.4) prevents double-counting when the same experience
triggers both paths: both produce signals keyed by goal-node
sourceNodeId, and the `(sourceNodeId, category)` window dedup retains
only the highest-significance version.

### 6.6 Adaptive threshold

**Urgency domain bounds.** `GoalUrgency.computeUrgency()` clamps to
[0.0, 1.0] on the target-date path (`Math.max(0.0, Math.min(1.0, ...))`)
but has unclamped fallback paths that read a raw `urgency` property
(when no target-date is set or when the target-date is unparseable).
A manually-set urgency of 2.0 would pass through unclamped. This is
a pre-existing bug — as part of #381 implementation, both fallback
paths in GoalUrgency will be fixed to clamp identically:
`Math.max(0.0, Math.min(1.0, Double.parseDouble(v)))`.

Additionally, the accumulator defensively clamps urgencyP75:
`Math.min(1.0, urgencyP75)` before applying the threshold formula.
This ensures the formula is safe even if other urgency sources are
introduced later. The minimum adjusted threshold is
`baseThreshold * 0.6` (3.0 with defaults), never zero or negative.

```
baseThreshold = config.attentionThreshold  // default 5.0
adjustedThreshold = urgencyP75 > 0.6
    ? baseThreshold * (1.0 - (urgencyP75 - 0.6))
    : baseThreshold
// At P75 = 0.6: threshold = 5.0 (unchanged)
// At P75 = 0.8: threshold = 4.0 (20% more sensitive)
// At P75 = 1.0: threshold = 3.0 (40% more sensitive)
totalSignificance = sum(signal.significance for signal in pending)
if totalSignificance >= adjustedThreshold:
    check minimum interval guard
    fire CognitiveAttentionRequired
    clear pending, update lastPushAt
```

### 6.7 Minimum interval guard

Per-principal, configurable via CognitiveDefaults (new field
`attentionMinIntervalSeconds`, default 300). If
`now - lastPushAt < minInterval`, suppress. Signals accumulate
until the interval expires.

### 6.8 Urgency P75 refresh

Updated each consolidation tick by reading the urgency values
GoalPrioritizationPhase already computes. Nearest-rank percentile
(reuses FeatureStatistics.compute() from memory-api). Stored per
principal.

### 6.9 Principal discovery

`CognitiveDefaultsRegistry.allAgentIds()` (new method). Returns
all agent IDs with registered cognitive profiles. Called lazily
at consolidation tick start. Agents without profiles do not
participate in attention.

## 7. Blocks Contract — CognitionCore Integration

### 7.1 CognitiveAttentionMediator

CognitionCore is a manually-constructed POJO (no CDI annotations, 4
constructor overloads, instantiated per-agent by the runtime). CDI
observer methods cannot live on it. A separate `@ApplicationScoped`
mediator bean bridges CDI events to CognitionCore instances:

```java
@ApplicationScoped
public class CognitiveAttentionMediator {

    private final ConcurrentHashMap<String, ConcurrentLinkedQueue<AttentionBriefing>>
        attentionQueues = new ConcurrentHashMap<>();

    void onAttentionRequired(@Observes CognitiveAttentionRequired event) {
        attentionQueues
            .computeIfAbsent(event.briefing().principalId(),
                k -> new ConcurrentLinkedQueue<>())
            .add(event.briefing());
    }

    public Optional<AttentionBriefing> drainAttention(String principalId) {
        var queue = attentionQueues.get(principalId);
        if (queue == null || queue.isEmpty()) return Optional.empty();
        List<AttentionBriefing> drained = new ArrayList<>();
        AttentionBriefing b;
        while ((b = queue.poll()) != null) drained.add(b);
        if (drained.isEmpty()) return Optional.empty();
        return Optional.of(mergeAll(drained));
    }
}
```

Merge: latest urgencyP75, union of signals sorted by significance
descending, latest generatedAt.

### 7.2 CognitionCore integration

CognitionCore receives the mediator via a new constructor parameter
(injected by the runtime that creates CognitionCore instances):

```java
private final CognitiveAttentionMediator attentionMediator; // nullable
private AttentionBriefing lastBriefing;                     // per-tick
```

Existing constructors continue to work (mediator defaults to null).
The 5th constructor overload accepts the mediator. Runtimes that
support attention (e.g., wacky-manor's ScenarioOrchestrator) obtain
the mediator from CDI and pass it through.

### 7.3 Attention prompt section

New PromptSection contributed via `promptSections()`:

```
## Attention Required
- [URGENCY_SPIKE] Project deadline (0.92): urgency rose past threshold
- [DECAY_DETECTED] Learn Spanish (dormant): no activity for 14 days
- [GOAL_RECOGNIZED] Improve team velocity: recognized from retrospective
```

Only renders when `drainAttention()` returns a briefing. Empty queue
produces no section — zero noise when nothing warrants attention.

### 7.4 Tick and prompt lifecycle

`tick()` and `promptSections()` are separate methods on CognitionCore.
The runtime calls `tick()` to update cognitive state, then calls
`promptSections()` later to assemble the prompt. The instance field
`lastBriefing` bridges them — the same pattern used by all other
cognitive sections (e.g., mood tick sets state, MoodPromptSection
reads it).

In `CognitionCore.tick()`, at the start of the FOUNDATION phase:

1. If `attentionMediator != null`: call
   `attentionMediator.drainAttention(agentId)`
2. Store result as `lastBriefing` (cleared each tick)

In `CognitionCore.promptSections()`:

3. If `lastBriefing` is present, add `AttentionPromptSection`
4. If `lastBriefing.urgencyP75()` exceeds CognitionConfig thresholds,
   include additional sections that would normally be gated out

### 7.5 Attention-aware section gating

Provides the platform-level mechanism that enables wacky-manor to
replace `CognitiveBudget.forSituation()` — but the actual wacky-manor
refactor (deleting CognitiveBudget, updating ManorConsolidationBeans)
is follow-up work (§9).

At the platform level, when an attention briefing is present:

- **Section inclusion override**: CognitionConfig gates that would
  normally exclude a section (e.g., `goalsEnabled()` returning false)
  are overridden when the briefing contains signals relevant to that
  section. An URGENCY_SPIKE signal overrides goalsEnabled; a
  DRIVE_SHIFT signal overrides drivesEnabled.
- **TopN expansion**: sections that use topN selection (e.g.,
  GoalPromptSection showing top-N goals) expand their N by
  `min(briefing.signals().size(), 3)` to ensure attention-relevant
  items are included.

This ensures the agent has sufficient cognitive context to reason
about the attention signals. Without it, the agent might receive
"URGENCY_SPIKE on Project X" but lack the goal context to reason
about Project X because the goals section was gated out.

## 8. Testing Strategy

| Test | Scope | Module |
|---|---|---|
| AttentionSignalTest | Signal construction, category coverage | mindmap-api |
| CognitiveAttentionAccumulatorTest | Threshold evaluation, per-principal isolation, adaptive percentile, minimum interval guard, urgency P75 refresh, real-time event filtering | mindmap-intelligence |
| GoalPrioritizationPhaseTest (extended) | URGENCY_SPIKE / PRIORITY_SHIFT / DECAY_DETECTED signals | mindmap-intelligence |
| GoalAffectPhaseTest (extended) | AFFECT_CHANGE signals on OCC appraisal | mindmap-intelligence |
| ConsolidationSchedulerTest (extended) | Scheduler collects signals, feeds accumulator | mindmap-intelligence |
| AttentionIntegrationTest | End-to-end: seed goals, run consolidation, accumulator fires event, verify briefing | mindmap-intelligence |
| GoalEmotionalProgressionTest (extended) | Attention signals accompany Day 1-7 Hope/Fear/Satisfaction arc | mindmap-intelligence |
| CognitiveAttentionMediatorTest | CDI observer, per-principal queue, merge, drain | blocks |
| CognitionCoreAttentionTest | Mediator integration, prompt section rendering, section gating | blocks |

## 9. Out of Scope

Each deferred item will have a GitHub issue filed before
implementation of #381 begins:

- **Agent runtime push receiver** — the mechanism for waking an idle
  LLM agent (WebSocket, queue, CLI invocation). The mediator's queue
  is the hook point. The runtime concern is a separate spec.
  → File on casehubio/blocks.
- **Scheduled briefings** — no periodic "morning wake." Event-driven
  only. Schedule can be layered at runtime level via cron-triggered
  consolidation tick. → File on casehubio/neocortex.
- **Cost management** — explicit token budgets per push. The minimum
  interval guard provides implicit cost control. Explicit budget
  constraints deferred to runtime. → File on casehubio/blocks.
- **Wacky-manor refactor** — the design enables wacky-manor to delete
  CognitiveBudget and use platform attention, but the actual refactor
  is follow-up work. → File on casehubio/blocks (or wacky-manor repo).

## References

- casehubio/neocortex#381 — issue body (architecture sketch, design questions)
- casehubio/blocks#303 — cognitive state migration plan (layer placement)
- casehubio/blocks#298 — cognitive emotion architecture epic
- casehubio/blocks#296 — goal-aware cognitive loop (immediate
  prerequisite). This spec directly addresses #296's requirement for
  a `CognitiveAttentionAccumulator` that fires CDI events on
  threshold-crossing. Remaining #296 requirements not covered here:
  GoalProposalOrchestrator acting on priority signals, decay-signal
  handling in the cognitive loop, and e2e test coverage.
- SignificanceAccumulator.java — existing threshold-crossing pattern
- ConsolidationScheduler.java — daemon thread lifecycle
- ConsolidationPhase.java — current SPI
- GoalPrioritizationPhase.java — urgency + priority computation
- GoalAffectPhase.java — OCC appraisal
- GoalUrgency.java — time-aware urgency from target-date
- TemporalFocus.java — AttentionItem pattern (salience + reason)
- CuriositySignalGenerator.java — trajectory-aware signal scoring
- CognitiveDefaultsRegistry.java — per-agent cognitive config
- CognitiveGoalOrchestrator.java (blocks) — tick-driven goal surfacing
- CognitionCore (blocks) — cognitive tick coordinator
- wacky-manor ScenarioOrchestrator.java — tick loop with CognitionCore
- wacky-manor CognitiveBudget.java — situational attention budgeting
- wacky-manor CharacterCognition.java — cognitive section rendering
- Park et al. (2023) — Generative Agents (reflection + planning cycles)
- Nagashima et al. (2024) — Intrinsic motivation via pattern discovery
- docs/specs/issue-253-cognitive-rearchitecture/2026-08-31-temporal-focus-design.md
- docs/specs/issue-253-cognitive-rearchitecture/2026-08-31-trajectory-aware-curiosity-design.md
- docs/specs/issue-295-knowledge-consolidation/2026-09-10-knowledge-consolidation-pipeline-design.md
- docs/specs/issue-345-goal-cognition/2026-09-23-goal-cognition-design.md

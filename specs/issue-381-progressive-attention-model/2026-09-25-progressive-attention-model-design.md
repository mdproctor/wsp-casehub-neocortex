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
              +------------v-----------+
              | CognitionCore            |  blocks
              |   attentionQueue         |
              |   per-principal briefings |
              +------+----------+------+
                     |          |
            +--------v--+ +----v-------------+
            | Next tick  | | Push receiver     |
            | (drain via | | (wakes idle agent,|
            | promptSec) | | then drains)      |
            +------------+ +------------------+
```

### 3.2 Layer placement

| Component | Layer | Module |
|---|---|---|
| AttentionSignal, AttentionBriefing, SignalCategory | neocortex | mindmap-api |
| CognitiveAttentionRequired CDI event | neocortex | mindmap-api |
| ConsolidationPhase.signals() default method | neocortex | mindmap-api |
| CognitiveAttentionAccumulator | neocortex | mindmap-intelligence |
| Modified consolidation phases (6) | neocortex | mindmap-intelligence |
| CognitionCore attention queue + prompt section | blocks | blocks-core |
| Modified blocks phases (3) | blocks | blocks-core |
| Push receiver (idle agent wake) | blocks/runtime | out of scope |

### 3.3 Dependency direction (unchanged)

```
mindmap-api (types)
    ^
mindmap-intelligence (accumulator, phases, scheduler)
    ^
blocks-core (CognitionCore, blocks phases)
```

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
BELIEF_REVISED). All live in mindmap-api because ConsolidationPhase
is there and phases need to construct signals.

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
caller reads via `signals()` after `run()` completes.

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
        return List.copyOf(pendingSignals);
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

Post-#303, when orchestrators move to neocortex and run per-principal
(like DriveOrchestrator per agentId), they set principalId directly.

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
    private final Event<CognitiveAttentionRequired> attentionEvent;
    private final Clock clock;

    record PrincipalAttention(
        List<AttentionSignal> pending,
        Instant lastPushAt,
        double urgencyP75
    ) {}
}
```

### 6.2 Accumulation from consolidation

`addSignals(List<AttentionSignal>)` — called by ConsolidationScheduler
after each tick. Groups signals by principalId, adds to per-principal
pending list, evaluates threshold.

### 6.3 Accumulation from real-time events

Three `@Observes` methods:

- **ExperienceRecorded** — if `event.event().subject()` matches an
  active goal node name, create an URGENCY_SPIKE or AFFECT_CHANGE
  signal. Requires a goal-name lookup (cached per consolidation tick).
- **AffectRecorded** — if the PAD delta (Euclidean distance from
  previous snapshot) exceeds a configurable threshold (default 0.3),
  create an AFFECT_CHANGE signal.
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

### 6.5 Adaptive threshold

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

### 6.6 Minimum interval guard

Per-principal, configurable via CognitiveDefaults (new field
`attentionMinIntervalSeconds`, default 300). If
`now - lastPushAt < minInterval`, suppress. Signals accumulate
until the interval expires.

### 6.7 Urgency P75 refresh

Updated each consolidation tick by reading the urgency values
GoalPrioritizationPhase already computes. Nearest-rank percentile
(reuses FeatureStatistics.compute() from memory-api). Stored per
principal.

### 6.8 Principal discovery

`CognitiveDefaultsRegistry.allAgentIds()` (new method). Returns
all agent IDs with registered cognitive profiles. Called lazily
at consolidation tick start. Agents without profiles do not
participate in attention.

## 7. Blocks Contract — CognitionCore Integration

### 7.1 Attention queue

CognitionCore gains per-principal `ConcurrentLinkedQueue<AttentionBriefing>`:

```java
private final ConcurrentHashMap<String, ConcurrentLinkedQueue<AttentionBriefing>>
    attentionQueues = new ConcurrentHashMap<>();

public void enqueueAttention(AttentionBriefing briefing) {
    attentionQueues
        .computeIfAbsent(briefing.principalId(), k -> new ConcurrentLinkedQueue<>())
        .add(briefing);
}

public Optional<AttentionBriefing> drainAttention(String principalId) {
    var queue = attentionQueues.get(principalId);
    if (queue == null || queue.isEmpty()) return Optional.empty();
    var merged = mergeAll(queue);
    queue.clear();
    return Optional.of(merged);
}
```

Merge: latest urgencyP75, union of signals sorted by significance
descending, latest generatedAt.

### 7.2 CDI observer

```java
void onAttentionRequired(@Observes CognitiveAttentionRequired event) {
    enqueueAttention(event.briefing());
}
```

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

### 7.4 Tick integration

In `CognitionCore.tick()`, before assembling prompt sections:

1. `drainAttention(agentId)` — merge any queued briefings
2. If briefing present — set on tick context, expand cognitive budget
3. Attention prompt section renders it
4. Budget adjusts based on urgency P75

### 7.5 Attention-aware budget

Replaces wacky-manor's `CognitiveBudget.forSituation()` with a
platform-level mechanism. When an attention briefing is present:

- Expand belief budget by `min(briefing.signals().size(), 3)`
- Expand norm budget by `ceil(urgencyP75 * 2)`
- Trust budget: unchanged (already scales with nearby agents)

The budget expansion ensures the agent has sufficient cognitive
context to reason about the attention signals. Without this, the
agent might receive "URGENCY_SPIKE on Project X" but lack the
belief context to reason about Project X.

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
| CognitionCoreAttentionTest | Queue drain, prompt section rendering, budget adjustment | blocks |

## 9. Out of Scope

- **Agent runtime push receiver** — the mechanism for waking an idle
  LLM agent (WebSocket, queue, CLI invocation). CognitionCore.enqueueAttention()
  is the hook point. The runtime concern is a separate spec.
- **Scheduled briefings** — no periodic "morning wake." Event-driven only.
  Schedule can be layered at runtime level via cron-triggered
  consolidation tick.
- **Cost management** — explicit token budgets per push. The minimum
  interval guard provides implicit cost control. Explicit budget
  constraints deferred to runtime.
- **Wacky-manor refactor** — the design enables wacky-manor to delete
  CognitiveBudget and use platform attention, but the actual refactor
  is follow-up work.

## References

- casehubio/neocortex#381 — issue body (architecture sketch, design questions)
- casehubio/blocks#303 — cognitive state migration plan (layer placement)
- casehubio/blocks#298 — cognitive emotion architecture epic
- casehubio/blocks#296 — goal-aware cognitive loop (immediate prerequisite)
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

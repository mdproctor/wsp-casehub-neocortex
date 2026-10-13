# Design: Bridge Drive-Proposed Goals to MindMap GOAL Nodes

**Issue:** casehubio/neocortex#463
**Date:** 2026-10-07
**Branch:** issue-471-cognitive-workbench

## Problem

`GoalProposalOrchestrator` produces `DriveGoalProposal` records from drive intensity, but they stay in a transient `ConcurrentHashMap`. They are invisible to the MindMap GOAL subgraph — meaning no visualization, no dependency graph participation, no consolidation phase processing (affect, prioritization, decay), and no persistence across restarts.

Two parallel goal creation paths exist today:
- **GoalRecognitionPhase** (mindmap-intelligence, consolidation) — creates GOAL nodes from experience memory patterns
- **GoalProposalOrchestrator** (cognition, tick) — creates in-memory `DriveGoalProposal` from drive intensity

These paths are unified only at prompt-render time (`EmergentGoalPromptSection`), but the drive path never persists.

## Solution

A new `DriveGoalBridgeParticipant` (TERMINAL-phase `CognitionTickParticipant`) bridges registered drive proposals to MindMap GOAL nodes. It:

1. **Creates** GOAL nodes for newly registered proposals (after TermNormalizer + Jaro-Winkler dedup)
2. **Enriches** existing matching nodes with `origin-drive` and `formation-reason` properties
3. **Updates** GOAL node status to `dormant` when the orchestrator abandons a drive goal

### Standalone Goals — No Eidos Sync

Drive-bridged goals are **standalone** (MindMap-only, cognitive layer). They are not linked to eidos `AgentRegistry` and do not participate in `GoalResolutionPhase.sync()`.

Justification: drive-proposed goals originate from the cognitive subsystem's internal motivational state, not from external systems or user-declared intentions. The no-split-brain rule applies to goals that span eidos and MindMap — standalone cognitive goals are authoritative in MindMap alone, just like goals created by `GoalRecognitionPhase`. They carry no `eidos-goal-name` property, so `GoalResolutionPhase.sync()` skips them.

## Components

### GoalProposalOrchestrator Change

Add a new public accessor to expose registered goals separately from cached proposals:

```java
public List<DriveGoalProposal> registeredGoals(String agentId, String tenantId) {
    GoalProposalState state = stateMap.get(key(agentId, tenantId));
    return state == null ? List.of() : List.copyOf(state.registeredGoals);
}
```

This provides the bridge a consistent data source: `registeredGoals()` for both creation and abandonment detection, avoiding the semantic mismatch between `currentProposals()` (registered + cached) and registration-only persistence.

### DriveGoalBridgeParticipant

**Module:** cognition (`io.casehub.neocortex.cognition.goal`)
**Implements:** `CognitionTickParticipant`

**Constructor dependencies:**
- `GoalProposalOrchestrator` — reads registered goals and tracks changes
- `MindMapStore` — writes GOAL nodes
- `TermNormalizer` — normalizes goal names before dedup comparison
- `CognitionConfig` — gates on `goalsEnabled()`

**Per-agent state:** `ConcurrentHashMap<String, BridgeState>` keyed by `agentId|tenantId`.

`BridgeState` tracks:
- Set of persisted goal node IDs
- Mapping from proposal `goalName` → node ID (for abandonment lookup)

### Tick Flow

1. Guard: if no GOAL subgraph exists for the tenant, create it via `store.createSubgraph()`. This ensures the bridge works even before any consolidation phase has run.
2. Read `GoalProposalOrchestrator.registeredGoals(agentId, tenantId)` — only accepted proposals (per D1).
3. Diff against `BridgeState.persistedGoalNames` to find newly registered proposals.
4. For each new registration:
   - Normalize via `TermNormalizer.normalize(goalName, "general")` → `ExpandedTerm(canonical, variants)`. **Note:** Until the "general" domain is implemented in `WordNetTermNormalizer`, this is a passthrough (NoOp). The dedup relies on Jaro-Winkler alone until companion work ships.
   - Load existing GOAL subgraph nodes for this tenant.
   - Match against existing nodes using both `node.name()` and `node.properties().get("description")` — this handles cross-path dedup since GoalRecognitionPhase uses `goal.description()` as the node name. Exact canonical equality first, then Jaro-Winkler ≥ 0.85 on canonical forms.
   - **Match found:** `store.updateNode()` — add `origin-drive` and `formation-reason` properties to existing node.
   - **No match:** `store.addNode()` — create new GOAL node with full property set. Node name is `goalName()` (short identifier). Use `NodeInput.withPrincipalId(agentId)` for agent-scoped visibility.
5. Check for abandonments: registered goals previously in `BridgeState` but no longer in `registeredGoals()` — update corresponding GOAL node status to `dormant` with `abandonment-reason`.
6. Update `BridgeState` with current registered set.

### Properties on New GOAL Nodes

| Property | Source | Description |
|----------|--------|-------------|
| `description` | `DriveGoalProposal.goalDescription()` | Full goal description text |
| `status` | literal `"active"` | Initial state |
| `origin` | literal `"drive-proposal"` | Provenance type (distinct from GoalRecognitionPhase) |
| `origin-drive` | `DriveGoalProposal.axis().name()` | CURIOSITY / COMPETENCE / AFFILIATION / AUTONOMY |
| `formation-reason` | `DriveGoalProposal.formationReason()` | Why the drive produced this goal |
| `horizon` | mapped from `suggestedPriority` (see below) | Goal time horizon |
| `drive-intensity` | `DriveGoalProposal.driveIntensity()` | Drive strength at creation time [0,1] |
| `agent-id` | from `CognitionTickContext.agentId()` | Agent that proposed this goal |

**Node name:** `DriveGoalProposal.goalName()` — the short identifier (e.g., "Learn Spanish"). This is distinct from `GoalRecognitionPhase` which uses `goal.description()` as the node name. The dedup strategy matches against both `name()` and `description` property to handle cross-path matching.

**PrincipalId:** Set via `NodeInput.withPrincipalId(agentId)` for agent-scoped node visibility in multi-agent tenants.

### Horizon Mapping

`DriveGoalProposal.suggestedPriority()` is a `@Nullable GoalPriority` (PRIMARY / SECONDARY). Mapping to horizon strings used by `GoalResolutionPhase`:

| `suggestedPriority` | `horizon` | Rationale |
|---------------------|-----------|-----------|
| `PRIMARY` | `"medium"` | High-priority drive goals are actionable in the medium term |
| `SECONDARY` | `"long"` | Lower-priority drive goals are longer-horizon aspirations |
| `null` | `"long"` | Default for proposals without explicit priority — avoids premature pruning by GoalResolutionPhase (which prunes `DISTANT_HORIZONS = {"aspirational", "long"}` only when urgency is low AND resolution is low) |

### Properties Added on Enrichment (Dedup Match)

| Property | Source | Description |
|----------|--------|-------------|
| `origin-drive` | `DriveGoalProposal.axis().name()` | Drive axis that motivated this goal |
| `formation-reason` | `DriveGoalProposal.formationReason()` | Drive formation rationale |

Enrichment is additive — existing properties (`origin`, `status`, `horizon`, etc.) are not overwritten.

### Abandonment Sync

When a registered goal previously in `BridgeState` disappears from `registeredGoals()`:
- Look up the corresponding GOAL node ID from the `goalName → nodeId` mapping
- Update node: `status` → `"dormant"`, `abandonment-reason` → `"drive-intensity-below-threshold"`
- Remove from `BridgeState`

Both creation and abandonment use `registeredGoals()` as the single data source, avoiding the semantic mismatch between registered-only and registered+cached sets.

This is distinct from GoalPrioritizationPhase's generic decay (confidence < threshold + negative affect). Drive abandonment means "the underlying motivation disappeared" — a specific, traceable cause.

## Deduplication Strategy

**Two-layer matching** consistent with existing codebase patterns:

1. **Normalization layer:** `TermNormalizer.normalize(goalName, "general")` canonicalizes the goal name. Until the "general" domain is implemented in `WordNetTermNormalizer`, this is a passthrough — dedup relies on Jaro-Winkler alone. This is explicitly acceptable; the normalization layer is preparatory infrastructure.

2. **Fuzzy matching layer:** Jaro-Winkler similarity ≥ 0.85 on canonical forms. Consistent with `GoalResolutionPhase` (sub-goal merge) and `MergeDetectionPhase` (Layer 1 threshold).

**Cross-path dedup:** The bridge matches its `goalName()` against both `node.name()` and `node.properties().get("description")` of existing GOAL nodes. This handles the naming asymmetry: GoalRecognitionPhase names nodes by their description text, while the bridge names nodes by the short `goalName()`. Without this, Jaro-Winkler between a short name and a full description would yield low similarity, failing to detect cross-path duplicates.

**Match precedence:** Exact canonical equality → Jaro-Winkler ≥ 0.85 → no match (create new node).

**Safety net:** `MergeDetectionPhase` (consolidation, @Priority(20)) provides eventual consistency — if the bridge creates a near-duplicate that escapes Jaro-Winkler, the consolidation phase will detect and merge it using its two-layer name + neighbor overlap approach.

**Acknowledged inconsistency:** `GoalRecognitionPhase` uses simple `equalsIgnoreCase` for dedup while this bridge uses Jaro-Winkler ≥ 0.85. The bridge is strictly better at dedup. Upgrading `GoalRecognitionPhase`'s dedup is out of scope for #463 but the inconsistency is noted for future alignment.

**Thread safety:** A TOCTOU window exists between the bridge reading existing GOAL nodes and GoalRecognitionPhase creating new ones on the consolidation thread. `MergeDetectionPhase` provides the eventual consistency guarantee — this is the accepted mitigation, consistent with how other node creation paths handle concurrent writes.

## EmergentGoalPromptSection Fix (In Scope)

Once the bridge persists drive goals as GOAL nodes, `EmergentGoalPromptSection` will **double-count** them:
1. Via `driveGoals.currentProposals()` → drive proposals weighted by `driveWeight`
2. Via `cognitiveGoals.currentState()` → GOAL nodes from MindMap (now including bridged drive goals) weighted by `1 - driveWeight`

**Fix:** Filter drive-originated nodes out of `EmergentGoalPromptSection`'s drive-goals path. When `config.goalsEnabled()` and the bridge is active, skip `driveGoals.currentProposals()` for proposals that have been persisted (matching by `goalName` against BridgeState). This ships atomically with the bridge to prevent the day-one regression.

Alternatively, `EmergentGoalPromptSection` can filter `cognitiveGoals.currentState()` results by `origin != "drive-proposal"` to exclude bridged goals from the cognitive path, keeping the drive-weight split. Either approach prevents double-counting — the implementation should pick whichever is simpler.

## CognitionCore Integration

New method on `CognitionCore`:

```java
public void configureDriveGoalBridge(MindMapStore mindMapStore, TermNormalizer termNormalizer) {
    if (config.goalsEnabled() && goals != null) {
        var bridge = new DriveGoalBridgeParticipant(goals, mindMapStore, termNormalizer, config);
        addParticipant(CognitionPhase.TERMINAL, bridge);
    }
}
```

**Ordering constraint:** The bridge must be registered **before** `CognitiveGoalOrchestrator` in the TERMINAL participant list. `addParticipant()` appends to a list — insertion order determines execution order. The consumer (blocks) must call `configureDriveGoalBridge()` before wiring `CognitiveGoalOrchestrator` so that newly created GOAL nodes are visible when goals are surfaced for prompts.

**Execution sequence in TERMINAL phase:**
1. `GoalProposalOrchestrator.tick()` — produces/updates proposals (called directly by CognitionCore)
2. `DriveGoalBridgeParticipant.tick()` — persists registered proposals to MindMap (custom participant)
3. `CognitiveGoalOrchestrator.tick()` — reads GOAL nodes including newly bridged ones (custom participant)

**Consumer wiring:** The engine integration layer (blocks) calls `configureDriveGoalBridge()` at startup alongside existing `configureAppraisal()`, `configureGutFeeling()`, etc.

## Module Dependency Change

`cognition/pom.xml` adds:
```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-knowledge-pipeline-api</artifactId>
</dependency>
```

This is a Tier 1 pure-Java module with zero CDI dependencies — lightweight addition.

**JaroWinkler access:** `JaroWinkler` lives in `io.casehub.neocortex.mindmap.intelligence.consolidation` (package-private scope). The cognition module already depends on `mindmap-intelligence`. If `JaroWinkler` is not public, the bridge should use its own Jaro-Winkler implementation or `JaroWinkler` should be promoted to `mindmap-api` as a shared utility (it already has three consumers: `MergeDetectionPhase`, `GoalResolutionPhase`, and now the bridge).

## Interaction with Existing Phases

Once drive goals are persisted as GOAL nodes, they are automatically processed by the existing consolidation and cognition pipeline:

| Phase | What it does with drive-originated GOAL nodes |
|-------|-----------------------------------------------|
| GoalAffectPhase (@Priority(37)) | Computes PAD affect — active → positive, blocked → frustrated |
| GoalPrioritizationPhase (@Priority(38)) | Computes composite priority score, detects decay |
| GoalResolutionPhase (@Priority(35)) | Expand (decompose), merge (Jaro-Winkler), prune, revise dependencies. Sync skips these nodes (no `eidos-goal-name`). |
| MergeDetectionPhase (@Priority(20)) | Safety net — detects near-duplicates across recognition and drive paths |
| CognitiveGoalOrchestrator (tick) | Surfaces goals, appraises emotions, records experience memories |

No changes to any of these phases are required.

## Companion Work (Separate Issues)

These items must be filed as separate GitHub issues before implementation begins:

1. **TermNormalizer "general" domain** — `WordNetTermNormalizer` currently maps PLACE/THING/ACTIVITY to lexicographer files. A "general" domain fallback with sub-dictionary loading (IT/computing, business, etc.) would activate the normalization layer. Without this, TermNormalizer is a passthrough and dedup relies on Jaro-Winkler alone.

2. **GoalRecognitionPhase dedup upgrade** — Upgrade from `equalsIgnoreCase` to Jaro-Winkler ≥ 0.85 to match the bridge's dedup strategy. Eliminates the inconsistency between the two goal creation paths.

## Testing Strategy

- **Unit test:** `DriveGoalBridgeParticipant` with `InMemoryMindMapStore` and `NoOpTermNormalizer`. Verify: new node creation with correct properties (including `agent-id` and `principalId`), enrichment on dedup match, abandonment sync, idempotency (same proposals on consecutive ticks produce no duplicates), GOAL subgraph auto-creation.
- **Dedup test:** Verify cross-path matching — bridge `goalName()` matches against GoalRecognitionPhase node named by `description`. Verify Jaro-Winkler with known near-match pairs ("Learn Spanish" / "Study Spanish").
- **Double-count test:** Verify `EmergentGoalPromptSection` does not double-count drive goals after bridge is active.
- **Integration test:** Full tick lifecycle — `GoalProposalOrchestrator.tick()` followed by `DriveGoalBridgeParticipant.tick()`, verify GOAL nodes exist in store and are picked up by `GoalAffectPhase`.
- **Multi-agent test:** Two agents with similar drive goals in the same tenant — verify principalId scoping prevents cross-agent dedup failures.

## References

- `cognition/src/main/java/.../cognition/goal/GoalProposalOrchestrator.java` — drive proposal orchestrator
- `cognition-api/src/main/java/.../cognition/goal/DriveGoalProposal.java` — proposal record
- `cognition/src/main/java/.../cognition/core/CognitionCore.java` — composition root, participant registration
- `cognition-api/src/main/java/.../cognition/core/CognitionTickParticipant.java` — participant SPI
- `cognition-api/src/main/java/.../cognition/core/CognitionTickContext.java` — tick context record
- `mindmap-intelligence/src/main/java/.../mindmap/intelligence/consolidation/GoalRecognitionPhase.java` — existing GOAL node creation
- `mindmap-intelligence/src/main/java/.../mindmap/intelligence/consolidation/GoalResolutionPhase.java` — goal graph management
- `mindmap-intelligence/src/main/java/.../mindmap/intelligence/consolidation/MergeDetectionPhase.java` — two-layer dedup
- `mindmap-intelligence/src/main/java/.../mindmap/intelligence/consolidation/JaroWinkler.java` — string similarity (may need promotion to shared module)
- `knowledge-pipeline-api/src/main/java/.../knowledge/TermNormalizer.java` — normalization SPI
- `knowledge-pipeline/src/main/java/.../knowledge/WordNetTermNormalizer.java` — WordNet implementation
- `cognition/src/main/java/.../cognition/appraisal/AppraisalTickParticipant.java` — pattern reference for participant wiring
- `/Users/mdproctor/claude/agents/cognition/2026-10-06-cognitive-life-coaching-architecture.md` §2.2.3 — goal landscape visualization
- casehubio/neocortex#463 — issue

# Cognitive Workbench — Design Spec

**Issue:** casehubio/neocortex#468
**Date:** 2026-10-08
**Branch:** issue-468-cognitive-workbench

## Overview

The cognitive workbench is a standalone research and exploration environment in blocks-ui that lets you converse with a cognitive agent (voice + text via the avatar system) while simultaneously visualizing the agent's cognitive model — knowledge graph, emotions, goals, memories, personality — updating in real-time.

It is the first visual consumer of the neocortex cognitive system and lives in blocks-ui as both a showcase and a reusable set of components that can be embedded in other UIs (life-ui, session-workbench). The Quarkus backend lives in blocks-ui as a dedicated module. blocks-ui is the home for now; this category of end-application artifact may migrate to a dedicated applications repo as more emerge.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  blocks-ui                                              │
│  ┌─────────────────────────────────────────────────────┐│
│  │ cognitive-workbench-backend (Quarkus)               ││
│  │  ├─ CognitionCore (tick lifecycle)                  ││
│  │  ├─ CognitionApi @McpDomain("neocortex/cognition")  ││
│  │  ├─ WorkbenchApi @McpDomain("neocortex/workbench")  ││
│  │  ├─ Voice WebSocket /ws/conversation                ││
│  │  ├─ Cognitive WebSocket /ws/cognitive                ││
│  │  ├─ Dataset manager (import/switch/seed)            ││
│  │  └─ SQLite stores (MindMap, Memory, CAPS, Obs)      ││
│  └─────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────┐│
│  │ Frontend (Lit 3.x + React Flow)                    ││
│  │  ├─ graph-stencil-cognitive (rendering layer)      ││
│  │  ├─ 7 consumer components                         ││
│  │  ├─ 8 researcher components                       ││
│  │  ├─ casehub-avatar-panel (voice/text)              ││
│  │  ├─ dock-workbench shell (IntelliJ-style layout)   ││
│  │  ├─ cognitive event bus (pages-event topics)       ││
│  │  └─ preferences panel (show/hide/toggle)           ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

## Modes

**Static browse** — Import a dataset (ZIP: SQLite stores + dataset-manifest.yaml + cognitive-profile.yaml), explore the graph, memories, goals, affect. Avatar converses about the loaded data but does not mutate the cognitive model.

Static-mode LLM context injection builds a system prompt from CognitionApi queries at dataset load time (not from `CognitionCore.promptSections()`, which requires running orchestrators). Query sequence:

1. `analytics()` — compute betweenness centrality rankings (`GraphAnalyticsResult.betweennessCentrality`)
2. Take top 20 node IDs from the centrality list
3. `entity()` for each of those 20 nodes — entity summaries, traits, PAD, key relationships
4. `affect()` for overall mood trajectory — PAD trend line summary
5. `graph()` from the subject node — ego-network structure (depth 2). The subject node is identified by `subject-node-id` in `dataset-manifest.yaml` (see Stores section).
6. `health()` — high-level graph quality summary (orphan/contradiction counts)

Note: `attention()` is excluded from the static mode query list. Attention signals are inherently live — they're produced by `CognitiveAttentionMediator` during cognitive ticks and are ephemeral (not persisted to datasets). The insight-feed component shows "No active signals" in static mode. `attention()` requires implementation as part of this workbench work (currently a stub returning null in `CognitionService` — needs wiring to `CognitiveAttentionMediator`); see Batch 1 scope.

Each query result is formatted as a named system prompt section (analogous to a simplified `CognitionPromptRenderer` output but without live state). When the user asks the avatar about an entity not in the initial context, the workbench queries `entity()` on demand and appends the result to the system prompt for subsequent turns (context grows per-session but never mutates the dataset).

**Live** — CognitionCore runs per conversation turn. Mood shifts, memories form, goals update, graph mutates. Visualization reflects real cognitive processing in real-time.

Toggle between modes via the workbench shell. Dataset selector supports loading multiple datasets; Frida Kahlo is the first, with more to follow.

## Shell Layout — dock-workbench

Uses the existing `dock-workbench` component type from casehub-pages (casehubio/casehub-pages#285). IntelliJ-style multi-zone docking:

- **Centre** — cognitive graph (primary visualization)
- **Right** — avatar panel (fixed, always visible), entity detail
- **Left** — insight feed, goal landscape
- **Bottom** — affect timeline, transcript
- **Status bar** — connection state, active dataset, mode indicator

Panels are draggable between zones via dock bar buttons. `defaultOpen`, `fixed`, and `allowedZones` constraints per panel. User can rearrange layout per session. Preference toggles control panel visibility. Layout presets: "Explorer" (graph-focused), "Researcher" (all panels), "Conversation" (avatar-focused).

**Prerequisite:** casehubio/casehub-pages#285 (dock-workbench implementation) is closed. Verify the dock-workbench example renders correctly in the showcase app before starting Batch 1.

## Rendering Layer — graph-stencil-cognitive

New package following the established pattern from graph-stencil-case/htn/org/swf.

### Node Stencils

All 13 SubgraphTypes from `SubgraphTypes.java` (mindmap-api) have stencils:

| SubgraphType | Shape | Color | Icon | Category |
|---|---|---|---|---|
| PERSON | Hexagon | Blue (#4a9eff) | 👤 | Content |
| GOAL | Diamond | Green (#34d399) | 🎯 | Content |
| ACTIVITY | Rounded rect | Purple (#a78bfa) | ⚡ | Content |
| PLACE | Octagon | Amber (#fbbf24) | 📍 | Content |
| PROJECT | Rectangle | Indigo (#818cf8) | 📦 | Content |
| ORGANISATION | Pentagon | Cyan (#22d3ee) | 🏢 | Content |
| CONCEPT | Circle | Slate (#94a3b8) | 💡 | Content |
| RESEARCH_AREA | Rounded diamond | Teal (#2dd4bf) | 🔬 | Content |
| BEHAVIORAL | Trapezoid | Rose (#fb7185) | 🧠 | CAPS |
| CULTURAL | Parallelogram | Violet (#c084fc) | 🌍 | Content |
| GENERAL | Rounded rect | Grey (#9ca3af) | ◻️ | Infrastructure |
| TYPE_SYSTEM | Rect (dashed) | Grey (#6b7280) | ⚙️ | Infrastructure |
| COGNITIVE | Rect (dashed) | Grey (#6b7280) | 🔧 | Infrastructure |

Infrastructure types (GENERAL, TYPE_SYSTEM, COGNITIVE) use muted grey stencils with dashed borders. The `graph()` endpoint traverses all subgraphs without type filtering, so every type must render. The cognitive-graph filter bar defaults to hiding infrastructure types.

### Node Rendering

- **PAD pill** — compact 3-segment bar showing pleasure/arousal/dominance values with color coding (green/red for positive/negative, width proportional to absolute value)
- **Confidence** — border opacity scales with confidence value (0.0 = nearly invisible, 1.0 = full opacity)
- **Traits** — small badges below node label
- **Temporal validity** — faded appearance for expired nodes (validUntil in past)

### Edge Rendering

- Solid line for REGISTERED validation tier, dashed for UNVALIDATED
- Edge type label centered on edge
- Optional decay indicator (half-life remaining)
- Width scales with confidence

### Adapter

Maps `CognitionApi.graph()` response to React Flow `GraphModel`. Handles node positioning (force-directed default, hierarchical option), edge routing, and centrality-based sizing.

## Component Inventory

### Consumer Components

1. **`<cognitive-graph>`** — Subgraph explorer. Force-directed or hierarchical layout via React Flow. Filter bar (subgraph type, emotion, confidence threshold). Centrality highlighting (node size scales with betweenness centrality). Node selection publishes `cognitive.node-selected`. Emotion filter mode: non-matching nodes dim, matching nodes glow with emotion intensity (as shown in mockup "Show Me My Hopes").

2. **`<entity-detail>`** — Deep-dive panel responding to `cognitive.node-selected`. Five tabs:
   - **Overview** — properties, traits, PAD, confidence, temporal validity
   - **Connections** — edges in/out with type, target, confidence
   - **Memories** — related memories across all domains (experience, relationship, reflection, mood, engagement)
   - **Trajectory** — affect sparkline for this entity from AffectTrajectoryAnalyzer
   - **History** — mutation trail from `CognitionApi.trace()`

3. **`<insight-feed>`** — Ranked attention signals from `CognitionApi.attention()` (live mode only — attention signals are ephemeral, produced by `CognitiveAttentionMediator` during cognitive ticks). Cards with: significance score, signal category icon (11 SignalCategory types), source entity link, evidence text, action buttons (context-dependent: "Revise goal", "Mark dormant", "Find in data", "Schedule meetup"). Publishes `cognitive.entity-highlight` on hover. New signals prepend with animation in live mode. In static mode, shows "No active signals — switch to live mode for attention analysis."

4. **`<goal-landscape>`** — Goal cards sorted by composite priority (urgency + feasibility + affective valence + importance). Each card shows: need-tier badge, OCC emotion badge, PAD affect indicator, decomposition tree (sub-goals via `decomposes-into` edges) with progress bar from computed `progress` property (#469 — "3 of 5 sub-goals completed (60%)"), dependency edges (`enables`/`blocks`/`requires`). Goal-tier grouping (thematic/strategic/tactical). Platform evidence links where available.

5. **`<affect-timeline>`** — PAD sparklines (pleasure/arousal/dominance over time) from `CognitionApi.affect()`. Three lines, color-coded. Domain correlation lanes below showing which life domains (subgraphs) track with mood changes — from DomainActivation DTW similarity. Event annotations on the timeline marking significant experiences. Configurable time window.

6. **`<relationship-map>`** — Ego-network centred on the subject (the "You" node from the mockup). Node size = interaction frequency. Node color = affect valence (green positive, red negative, grey neutral). Dashed borders for stale relationships. Force-directed sub-graph using graph-stencil-cognitive stencils. Edge thickness = relationship strength.

7. **`<graph-health>`** — Quality dashboard from `CognitionApi.health()` + `analytics()`. Metric cards: orphan count, contradiction count, low-confidence cluster count, unvalidated edge ratio, stale node count, graph density. k-core community visualization using `MindMapAnalyzer.kCores()` data. Actionable: click a metric to highlight affected nodes in the cognitive graph.

### Researcher Components

8. **`<emotion-inspector>`** — 22 OCC emotion grid organized by category matching the `EmotionType` enum grouping (prospect-based: HOPE/FEAR/SATISFACTION/DISAPPOINTMENT/RELIEF/FEARS_CONFIRMED; well-being: JOY/DISTRESS; fortunes-of-others-liked: HAPPY_FOR/PITY; fortunes-of-others-disliked: RESENTMENT/GLOATING; attribution: PRIDE/SHAME/REPROACH/ADMIRATION; compound: GRATITUDE/ANGER/REMORSE/GRATIFICATION; object-based: LOVE/HATE). The fortunes-of-others split (liked vs disliked) mirrors the enum's comment-group structure. Each cell: current intensity bar + mini history sparkline. Click cell for detailed history chart.

9. **`<memory-browser>`** — Multi-dimensional filter query interface. Active filters rendered as dismissible chips. Filter dimensions: domain (dynamically discovered from loaded dataset — `MemoryDomain` is a `record(String name)`, not a fixed enum; the UI queries distinct domains on dataset load rather than hardcoding), emotion (22 OCC EmotionType values), SEC dimensions (8 dimensions across 4 evaluation stages: relevance/novelty/urgency from RelevanceCheck, conduciveness from ImplicationCheck, controllability/adjustability from CopingCheck, internal-standards/external-standards from NormativeCheck — dimension names from `SecDimensions.java`), action tendency (9 Frijda types), confidence range, origin (STATED/INFERRED/SPECULATED/UNKNOWN), time range, entity reference, drive axis, graduation status. Natural language query box that maps to structured filters. Full cognitive metadata rendering per memory record — domain badge, emotion tags, PAD values, SEC appraisal bars, linked entities, confidence origin, turn reference.

10. **`<caps-topology>`** — CAPS network visualization. 77 nodes in 3 columns: 31 input (left), 21 mediating (centre), 25 output (right) — per `caps-topology.yaml`. Node color = activation level (cool→warm gradient). Settling animation shows activation propagation across ticks. Disposition overlay: per-agent weight modulation visualized as edge thickness changes. Distortion visualization: active cognitive distortions highlighted with compound cap indicators.

11. **`<appraisal-inspector>`** — SEC pipeline breakdown across 4 evaluation stages with 8 total dimensions (from `SecDimensions.java`): Relevance (relevance, novelty, urgency) → Implications (conduciveness) → Coping (controllability, adjustability) → Normative (internal-standards, external-standards). 4 base `SecCheck` implementations plus 3 LLM-enhanced variants (LlmImplicationCheck, LlmCopingCheck, LlmNormativeCheck) — when an LLM variant is active, the inspector shows both heuristic and LLM results side-by-side. Each stage shows `SecResult` dimension bars (0–1). Final output: resulting OCC EmotionType + ActionTendency + narrative text (from LlmAppraisalStrategy when available).

12. **`<drive-dashboard>`** — 4-axis motivational state visualization. Horizontal bars for curiosity, competence, affiliation, autonomy. Each bar shows: current intensity, trend arrow (rising/falling/stable), pressure source breakdown (e.g. curiosity: staleness 40%, trajectory 30%, goal proximity 30%). Drive-to-goal bridge visible: which goals each drive axis is fueling.

13. **`<consolidation-monitor>`** — 16-phase pipeline dashboard. 13 phases from mindmap-intelligence: AccessFrequencyPhase (@10), BehavioralSynthesisPhase, CommunitySummaryPhase, CuriosityRefreshPhase, ExperienceConsolidationPhase, GoalAffectPhase, GoalPrioritizationPhase, GoalRecognitionPhase (@45), GoalResolutionPhase, MergeDetectionPhase, SchemaDiscoveryPhase, SubThoughtConsolidationPhase, SurfacingAggregationPhase. 3 phases from cognition: RelationshipStagePhase, BeliefRevisionPhase, DriveAdaptationPhase. Per-phase card: status indicator (idle/running/complete), last run timestamp, signal count produced, duration, source module badge (mindmap-intelligence vs cognition). "Run consolidation" button triggers `WorkbenchApi.consolidateNow()`. Live progress via `cognitive.consolidation-phase-completed` events (phase-by-phase card transitions). Historical status from `WorkbenchApi.consolidationStatus()` on component mount. Signal output per phase mapped to SignalCategory. Live mode only — in static mode, shows last-run data from the dataset's snapshot store audit entries (read-only).

14. **`<personality-profile>`** — Full CognitiveDefaults viewer. Source tagging: "derived" (from CognitiveDerivationEngine) vs "explicit" (overridden in cognitive-profile.yaml). Sections: disposition axes (radar chart), personality weights (domain weight bars), mood baseline (PAD position), curiosity config (category weights), temporal focus, CBR strategy defaults, social cognition defaults, graph structure defaults, extraction bias, appraisal weights, habituation config.

15. **`<mutation-timeline>`** — Raw GraphMutation stream (13 types from cognitive-observability). Filterable by: mutation type, entity name/id, time range, source (conversation/consolidation/extraction). Compact card per mutation with before/after diff where applicable. Chronological, newest first.

## Backend

### Quarkus Module

Located at `examples/cognitive-workbench-backend` in blocks-ui. Dependencies:
- neocortex: mindmap-sqlite, memory-sqlite, caps-engine, cognitive-index, cognitive-observability-sqlite, cognition, memory-seeding
- casehub-blocks: casehub-blocks-speech-ws, casehub-blocks-speech-sherpa, casehub-platform-agent-api (same dependencies as avatar-demo — shared modules, not duplicated)

### Stores

Each loaded dataset is a ZIP archive containing:
- `dataset-manifest.yaml` — schema versions, creation timestamp, neocortex version, checksum
- `mindmap.sqlite` — MindMapStore
- `memory.sqlite` — CaseMemoryStore
- `caps.sqlite` — CapsEngine
- `snapshots.sqlite` — SnapshotStore
- `cognitive-profile.yaml` — CognitiveDefaults

**Dataset manifest** (`dataset-manifest.yaml`):
```yaml
format-version: 1
neocortex-version: "0.3.0"
created: "2026-10-08T12:00:00Z"
subject-node-id: "frida-kahlo-person-001"
schemas:
  mindmap: 14    # Flyway migration version
  memory: 8
  caps: 3
  snapshots: 5
checksum: "sha256:..."
```

The `subject-node-id` identifies the dataset's protagonist — the node used for ego-network traversal in static mode (`graph()` depth 2) and as the "You" reference in the relationship-map. For the Frida Kahlo dataset, this is the Frida PERSON node. If omitted, the workbench falls back to the node with highest betweenness centrality from `analytics()`.

On import, the backend validates: (a) `format-version` is supported, (b) each schema version is compatible with the running neocortex modules (equal or older than current), (c) checksum matches ZIP contents. Incompatible datasets are rejected at import time with a diagnostic message indicating which schema is too new. Datasets created with older schemas are accepted — SQLite stores handle missing columns gracefully via defaults.

**Dataset switching:** Multiple datasets managed, one active at a time.

**Architecture:** `CognitionService`, `CognitionCore`, `ConsolidationScheduler`, `SnapshotCaptureService`, and their orchestrators hold `private final` store references — they cannot be hot-swapped. The workbench uses a **session reconstruction** approach: a `DatasetSession` encapsulates the full cognitive stack:
- CognitionService + CognitionCore + all orchestrators
- ConsolidationScheduler (created programmatically via the non-CDI constructor, wired to the session's stores — the CDI `@ApplicationScoped` singleton is disabled via `@IfBuildProperty`)
- SnapshotCaptureService (created programmatically, observing the session's `ConsolidationCompleted` directly — not via CDI events)
- All store connections (MindMapStore, CaseMemoryStore, SnapshotStore, CapsEngine)

The workbench backend holds an `AtomicReference<DatasetSession>` as the active session. WS controllers and REST endpoints read `currentSession.get()` for every operation.

**Consolidation in the workbench:** The periodic timer (`@PostConstruct` in production ConsolidationScheduler) is **disabled** — the workbench uses on-demand consolidation only via WorkbenchApi `consolidateNow()`. The researcher triggers consolidation explicitly; the consolidation-monitor observes real-time progress. When `DatasetSession` is closed on dataset switch, its ConsolidationScheduler executor is stopped via `stop()`.

Dataset switch = construct a new `DatasetSession` with new stores (including fresh ConsolidationScheduler and SnapshotCaptureService), atomically swap the reference, close the old session. No proxy stores or mutable internals needed. Reconstruction cost is negligible for an interactive research tool with infrequent dataset switches.

**Switch guard:** If a `CognitionCore.tick()` is in progress, the switch request is rejected with HTTP 409 (Conflict).

**Switch sequence:** (1) acquire dataset lock, (2) construct new `DatasetSession` with new stores (including fresh ConsolidationScheduler and SnapshotCaptureService), (3) atomically swap `currentSession` reference, (4) send `dataset-switched` on cognitive WS (frontend clears state), (5) close old session's store connections and stop its ConsolidationScheduler executor (no-op on initial load when old session is null), (6) release lock, (7) publish initial state on cognitive WS. The WS controller dispatches `cognitive.dataset-changed` pages-event only after it receives and processes the `dataset-switched` WS message — the shell never fires this event directly. The same sequence handles both initial dataset load and dataset switch — step 5 gracefully handles null old session.

### MCP Domains

**Existing `CognitionApi`** (`@McpDomain("neocortex/cognition")`) — 11 endpoints defined (#466), 10 implemented: inspect, entity, health, diff, trace, graph, affect, domainActivation, analytics, activities. The `attention()` endpoint is currently a stub (returns null in `CognitionService`) — it needs to be wired to `CognitiveAttentionMediator` as part of Batch 1 to support the insight-feed component in live mode.

**New `WorkbenchApi`** (`@McpDomain("neocortex/workbench")`) — Dataset management and workbench operations:
- Import dataset (ZIP upload)
- List available datasets
- Activate dataset
- Delete dataset
- Seed built-in dataset (e.g. "frida-kahlo")
- Get/set workbench mode (static/live)
- `consolidateNow()` — trigger on-demand consolidation for the active dataset. Delegates to `currentSession.get().consolidationScheduler().consolidateNow()`. Returns 409 if consolidation is already running (ConsolidationScheduler's internal ReentrantLock). Consolidation progress is streamed via cognitive WS (see below).
- `consolidationStatus()` — last consolidation run info: per-phase status, timestamps, signal counts, duration. Reads from the session's SnapshotCaptureService audit entries.

### WebSocket Endpoints

**Voice WebSocket** (`/ws/conversation`) — Reuses avatar-demo protocol:
- Inbound: audio frames (PCM binary), `start`/`stop`/`text` JSON messages
- Outbound: `partial`/`transcript` (STT), `response` (LLM text), `phonemes` (visemes), binary (TTS audio)
- In live mode: after each LLM response, runs CognitionCore tick, publishes cognitive state delta via cognitive WS

**Cognitive WebSocket** (`/ws/cognitive`) — State push channel:
- Message types: `mood-update`, `memory-formed`, `graph-mutation`, `attention-signal`, `caps-settled`, `goal-update`, `drive-changed`
- **Atomicity:** All state changes from a single `CognitionCore.tick()` are published as a single composite `tick-complete` message containing all sub-deltas. Components receive one consistent snapshot, not piecemeal updates that could show intermediate states (e.g. mood change before the memory that caused it). The composite message preserves causal ordering: mood → memory → graph → attention → caps → goals → drives.
- **Failure:** If tick() fails mid-execution (e.g. after mood appraisal but before goal processing), no partial state is published. CognitionCore's `safeRun()` wrappers catch per-phase exceptions, so partial completion within a tick is possible — but the WS controller only publishes once tick() returns, packaging whatever state changes succeeded.
- Live mode: publishes composite message after each cognitive tick
- Static mode: publishes composite message on dataset load
- **Dataset boundary:** On dataset switch, the cognitive WS sends a `dataset-switched` message before any new dataset's state. The frontend controller clears all component state on this message before processing subsequent updates.
- **Initial load:** On first dataset activation (no prior session) or on WS connection establishment when a dataset is already active, the backend sends `dataset-switched` followed by initial state — same flow as a switch, with the old-session teardown as a no-op.
- **Consolidation streaming:** Three message types for consolidation monitoring:
  - `consolidation-started` — sent when `consolidateNow()` begins. Payload: `{ phaseCount: 16, tenantId }`.
  - `consolidation-phase-completed` — sent after each phase finishes. Payload: `{ phaseName, duration, signalCount, success, errorMessage }`. Enables real-time per-phase progress in the consolidation-monitor.
  - `consolidation-completed` — sent when all phases finish. Payload: `{ tenantId, totalDuration, phaseResults[] }`. The consolidation-monitor transitions all phase cards from running→complete/failed.

### Frida Kahlo Seeder

Uses `memory-seeding` BiographyHandler infrastructure with the 9 template types defined in #470 (Cultural context, Life events, Places, Activities, Projects, Relationships, Goals, Beliefs, Current state). YAML biography file with ~105 entries across the biographical model. Seeds all 10 content SubgraphTypes to exercise the full rendering layer:

| SubgraphType | Count | Examples |
|---|---|---|
| PERSON | ~30 | Diego Rivera, family, colleagues, lovers, doctors |
| GOAL | ~15 | Across 3 tiers with dependency decomposition |
| ACTIVITY | ~40 | Exhibitions, hospital stays, paintings, political events |
| PLACE | ~10 | Casa Azul, Mexico City, Paris, NYC, Detroit |
| PROJECT | ~10 | Specific paintings (The Two Fridas, Henry Ford Hospital), exhibitions |
| ORGANISATION | ~5 | Mexican Communist Party, Hospital de la Cruz Roja, Louvre, UNAM |
| CONCEPT | ~8 | Surrealism, Mexicanidad, self-portraiture, revolutionary politics, chronic pain, fertility |
| CULTURAL | ~5 | Mexican indigenous art, Pre-Columbian motifs, Tehuana dress, Catholic iconography |
| RESEARCH_AREA | ~3 | Painting techniques, political theory, anatomy/medical illustration |
| BEHAVIORAL | ~6 | CAPS patterns: approach art despite pain, avoidance around abandonment, seek political solidarity, perfectionism under physical limitation |

Additional seeded data:
- OCC emotions across all 22 types from known life events
- Affect trajectories showing emotional evolution over time
- Goal dependency graphs with predicted vs actual emotional outcomes

## Event Bus — pages-event Topics

| Topic | Payload | Publisher | Subscribers |
|---|---|---|---|
| `cognitive.node-selected` | `{ nodeId, name, subgraphType }` | cognitive-graph, relationship-map | entity-detail, avatar context |
| `cognitive.entity-highlight` | `{ nodeId, name, transient: true }` | insight-feed, memory-browser | cognitive-graph (glow effect) |
| `cognitive.mood-changed` | `{ pleasure, arousal, dominance }` | cognitive WS controller | affect-timeline, avatar mood, emotion-inspector |
| `cognitive.memory-formed` | `{ memoryId, domain, text, entityRefs }` | cognitive WS controller | memory-browser, cognitive-graph |
| `cognitive.graph-mutated` | `{ mutations: GraphMutation[] }` | cognitive WS controller | cognitive-graph, mutation-timeline, graph-health |
| `cognitive.attention-signal` | `{ signals: AttentionSignal[] }` | cognitive WS controller | insight-feed |
| `cognitive.caps-settled` | `{ attractors, activations }` | cognitive WS controller | caps-topology |
| `cognitive.goal-updated` | `{ goalId, property, value }` | cognitive WS controller | goal-landscape |
| `cognitive.drive-changed` | `{ axis, intensity, trend }` | cognitive WS controller | drive-dashboard |
| `cognitive.conversation-turn` | `{ role, text, entityRefs }` | avatar panel | cognitive-graph |
| `cognitive.dataset-changed` | `{ datasetId, name }` | cognitive WS controller (after receiving `dataset-switched` from WS) | all components |
| `cognitive.consolidation-started` | `{ phaseCount }` | cognitive WS controller | consolidation-monitor |
| `cognitive.consolidation-phase-completed` | `{ phaseName, duration, signalCount, success }` | cognitive WS controller | consolidation-monitor |
| `cognitive.consolidation-completed` | `{ totalDuration, phaseResults[] }` | cognitive WS controller | consolidation-monitor |
| `cognitive.mode-changed` | `{ mode: 'static' \| 'live' }` | workbench shell | WS controller |

### Live Conversation Flow

1. User speaks → `casehub-speech` captures audio → voice WS sends PCM frames
2. Backend STT → `partial`/`transcript` → avatar shows transcript
3. Backend LLM generates response → `response` → avatar speaks (TTS + visemes)
4. Backend runs CognitionCore tick → mood shifts, memories form, graph mutates
5. Backend pushes state delta via cognitive WS → frontend dispatches pages-events
6. Visualization components animate updates in real-time
7. User clicks a highlighted node → `cognitive.node-selected` → entity-detail opens, avatar receives context

### Static Browse Flow

1. User activates dataset via WorkbenchApi → backend constructs DatasetSession → sends `dataset-switched` on cognitive WS (same flow for initial load and dataset switch — initial load has no old session to tear down) → WS controller fires `cognitive.dataset-changed` → all components query CognitionApi
2. User clicks node → `cognitive.node-selected` → entity-detail loads via `CognitionApi.entity()`
3. User converses via avatar → LLM answers about the dataset (graph context injected) but no cognitive tick runs

## Batch Delivery Plan

### Batch 0: Prerequisites
- Verify dock-workbench example renders in casehub-pages showcase (casehubio/casehub-pages#285 is closed — verify no regression)
- Add casehub-pages to this slot

### Batch 1: Foundation — Graph + Avatar + Shell
- `graph-stencil-cognitive` (rendering layer)
- `<cognitive-graph>` (subgraph explorer)
- `<entity-detail>` (deep-dive panel)
- `<cognitive-workbench>` (dock-workbench shell)
- Avatar panel integration
- Workbench backend (Quarkus, both WS endpoints, CognitionApi — including attention() implementation, WorkbenchApi, DatasetSession lifecycle)
- Frida Kahlo seeder
- Event bus core topics + WS controller

**Checkpoint:** Load Frida dataset, explore graph, click entities, converse with avatar. Live mode runs cognitive ticks with real-time graph updates.

### Batch 2: Consumer Tier — Full Visualization
- `<insight-feed>`
- `<goal-landscape>`
- `<affect-timeline>`
- `<relationship-map>`
- `<graph-health>`
- Preferences panel (toggles, layout presets)

**Checkpoint:** All 7 consumer components in dock layout, toggleable, fully reactive.

### Batch 3: Researcher Tier — Deep Inspection
- `<emotion-inspector>`
- `<memory-browser>`
- `<caps-topology>`
- `<appraisal-inspector>`
- `<drive-dashboard>`
- `<consolidation-monitor>`
- `<personality-profile>`
- `<mutation-timeline>`
- Consumer/researcher detail-level toggle

**Checkpoint:** Full 15-component workbench with both detail levels.

## Testing Strategy

**Frontend components** — vitest + jsdom per blocks-ui convention. Each component tested with mock data fixtures that match the shape of cognitive WS messages and CognitionApi responses. No running backend required for unit tests.

**Event bus / WS controller** — The cognitive WS controller translates WebSocket messages into pages-events. Unit tested by feeding recorded `tick-complete` composite messages and asserting correct pages-event dispatch (topic, payload shape, ordering). Mock WebSocket via vitest's WebSocket mock.

**Backend** — Standard Quarkus @QuarkusTest patterns. CognitionCore tick lifecycle tested with in-memory stores (`mindmap-inmem`, `memory-inmem`). WorkbenchApi dataset import/export tested with temp directories and real SQLite stores. WebSocket endpoints tested via Quarkus websocket-next test client.

**Frida Kahlo seeder** — Validated by seeding into in-memory stores and asserting: (a) expected node counts per SubgraphType, (b) goal decomposition edges exist, (c) OCC emotions across all 22 types present, (d) CAPS behavioral patterns seeded. Seeder test serves as both validation and regression guard.

**Static browse mode** — Integration test: load a Frida dataset, verify CognitionApi queries return expected data, verify static LLM context injection produces non-empty prompt sections.

**Test data fixtures** — Shared fixture directory with: (a) sample `tick-complete` WS messages covering all 7 sub-delta types, (b) sample CognitionApi response JSONs for each of the 11 endpoints, (c) a minimal seeded dataset ZIP for integration tests.

## References

- `2026-10-06-cognitive-workbench-spec.md` — original workbench spec (workspace model, researcher components, delivery phases)
- `2026-10-06-neocortex-memory-visualiser-spec.md` — visualiser spec (consumer components, rendering conventions, API endpoints)
- `2026-10-06-cognitive-filter-taxonomy.md` — 22 filter dimensions across cognitive subsystems
- `mockups/visualiser-mockups.html`, `mockups/visualiser-full.png` — consumer component visual spec
- `mockups/graph-visualisation-mockups.html`, `mockups/graph-visualisation-full.png` — graph + memory detail visual spec
- `cognitive-observability-core/.../CognitionApi.java` — 11 MCP endpoints for cognitive data
- `pages/examples/samples/Layout/Dock Workbench.page.yaml` — dock-workbench layout DSL
- `2026-08-04-mdp01-dock-workbench-composable-primitives.md` — dock-workbench architecture blog
- casehubio/casehub-pages#285 — dock-workbench implementation issue
- `packages/avatar/` — casehub-avatar, casehub-speech, avatar-ws-controller, casehub-avatar-panel
- `graph-stencil-case/`, `graph-stencil-htn/`, `graph-stencil-org/`, `graph-stencil-swf/` — existing stencil packages (pattern reference)
- casehubio/neocortex#471 — parent epic
- casehubio/neocortex#463–467 — dependency issues (all closed)
- casehubio/neocortex#469 — goal progress computation (closed) — progress property on goal nodes for sub-goal completion tracking, consumed by goal-landscape component
- casehubio/neocortex#470 — sub-thought representation + biographical import template schema (closed) — defines 9 template types consumed by BiographyHandler, dependency for Frida Kahlo seeder

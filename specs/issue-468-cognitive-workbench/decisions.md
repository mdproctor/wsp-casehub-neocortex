# Decisions — Cognitive Workbench (#468)

## D1: Scope — full consumer + researcher tier in batches

**Choice:** All 15 components (7 consumer + 8 researcher) + avatar/voice, delivered in batches with wrap points. UI preference toggles for show/hide per component.
**Alternatives:**
- Consumer tier only — simpler but less impressive; researcher components deferred indefinitely
- MVP subset (graph + entity + avatar only) — fastest to demo but misses the showcase impact
**Rationale:** Building all components in batches gives full delivery without scope risk per batch. Toggle UI means components only need to work independently. Each batch ends at a clean checkpoint.
**Trade-offs:** More total work, but each batch is focused and wrappable.
**Sources:** Issue #468 body, workbench spec, visualiser spec
**Exploration:** quick
**Status:** captured

## D2: Modes — static browse + live cognitive processing

**Choice:** Both static browse (pre-loaded datasets, Frida Kahlo first) and live mode (CognitionCore runs real-time during conversation). Toggle between them.
**Alternatives:**
- Live only — most impressive but requires full backend setup for every demo
- Static only — simpler backend but no real-time cognitive processing demo
**Rationale:** Static mode lets people explore rich pre-seeded data without backend complexity. Live mode shows the cognitive system actually working. Both are needed for different audiences.
**Trade-offs:** Two code paths for data flow (static read vs live mutation + push).
**Sources:** Workbench spec (workspace of neocortex instances, import/export)
**Exploration:** quick
**Status:** captured

## D3: Datasets — loadable, swappable

**Choice:** Dataset selector with import capability. Frida Kahlo is the first dataset; more will follow. Workbench manages a collection of cognitive environments.
**Alternatives:**
- Hardcoded single dataset — simplest but not extensible
- File-based import only (no selector) — functional but poor UX
**Rationale:** The workbench is a research tool. Different datasets illuminate different aspects of the cognitive system. A selector is essential for practical use.
**Trade-offs:** Need a dataset format, import pipeline, and management UI.
**Sources:** User requirement ("we will have other datasets"), workbench spec (workspace concept)
**Exploration:** quick
**Status:** captured

## D4: Location — blocks-ui

**Choice:** Components and showcase in blocks-ui. Components are reusable packages that can be embedded in other UIs (life-ui, session-workbench).
**Alternatives:**
- Neocortex example module — natural for backend deps but wrong direction for upstream relationship
- Standalone repo — maximum independence but infrastructure overhead
**Rationale:** Neocortex is upstream of blocks-ui; can't depend on blocks-ui components. blocks-ui is the component home. May migrate to a dedicated applications repo later as more end-application-style artifacts emerge.
**Trade-offs:** blocks-ui is currently a component library, not an application host. This stretches its role. Conscious decision to revisit repo structure later.
**Sources:** Repo dependency graph (neocortex → blocks → blocks-ui)
**Exploration:** quick
**Status:** captured

## D5: Backend — dedicated Quarkus module in blocks-ui

**Choice:** New dedicated Quarkus backend in blocks-ui (e.g. examples/cognitive-workbench-backend). Owns CognitionCore, dataset import, cognitive WebSocket endpoint.
**Alternatives:**
- Extend avatar-demo backend — less duplication of voice infra but conflates two demos
- Backend in blocks repo — blocks has engine infra but adds coupling
**Rationale:** Clean separation from avatar-demo. Dedicated backend can evolve independently. Voice WebSocket can reuse patterns from avatar-demo without depending on it.
**Trade-offs:** Some voice infrastructure duplication vs avatar-demo.
**Sources:** avatar-demo structure, avatar-ws-controller protocol
**Exploration:** quick
**Status:** captured

## D6: Reactivity — full bidirectional event bus

**Choice:** Bidirectional: conversation drives graph highlights + live cognitive state updates; clicking a graph node can steer conversation context.
**Alternatives:**
- One-way reactive — conversation updates trigger visualization refreshes only
- Manual refresh — visualization on demand
**Rationale:** The showcase value is watching cognition happen. Bidirectional linking means the graph is both an output (see what the agent is thinking) and an input (click to explore, which informs the agent's context).
**Trade-offs:** Needs a well-designed event bus with clear topic namespacing. More complex state management.
**Sources:** pages-event topics (existing blocks-ui event coordination pattern)
**Exploration:** quick
**Status:** captured

## D7: Shell layout — pages dock-workbench (IntelliJ-style)

**Choice:** Use the existing `dock-workbench` component type from casehub-pages. Centre zone for the cognitive graph, side stripes (left/right) for avatar, entity detail, insight feed, goal landscape. Bottom zone for affect timeline and transcript. Panels are draggable between zones, toggleable via dock bar buttons. User can rearrange layout per session.
**Alternatives:**
- Tabbed workbench — can't see multiple visualizations simultaneously
- Dashboard grid — components compete for space
- pages-split-workbench — only two panels (list/detail), insufficient for multi-panel cognitive workbench
**Rationale:** dock-workbench already implements IntelliJ-style multi-zone docking with drag-and-drop rearrangement, `defaultOpen`/`fixed`/`allowedZones` constraints, and multi-zone side panels. Exactly what the cognitive workbench needs. No layout invention required.
**Trade-offs:** dock-workbench example is currently broken — needs fixing as a prerequisite. Cognitive workbench becomes a consumer of the dock-workbench primitive.
**Sources:** `pages/examples/samples/Layout/Dock Workbench.page.yaml`, blog: `2026-08-04-mdp01-dock-workbench-composable-primitives.md`, casehubio/casehub-pages#285
**Exploration:** quick
**Status:** captured

## D8: Component communication — pages-event topics

**Choice:** Use existing `onPagesEvent`/`dispatchPagesEvent` pattern with cognitive-specific topics (e.g. `cognitive.node-selected`, `cognitive.mood-changed`, `cognitive.memory-formed`, `cognitive.entity-highlight`). Avatar panel publishes conversation events, visualization components subscribe. Graph clicks publish selection events, avatar panel subscribes to steer context. WebSocket controller translates backend pushes into pages-event dispatches.
**Alternatives:**
- Shared reactive state store — tight coupling, doesn't match blocks-ui conventions
- Direct WebSocket subscriptions — still needs local events for static mode, ends up with both patterns
**Rationale:** Established blocks-ui pattern (used by orchestration-workbench, dock-workbench). Keeps components decoupled. Works for both static browse and live mode. Typed topic definitions provide payload safety.
**Trade-offs:** Event bus debugging can be harder than inspecting a central state object. Mitigated by browser devtools event logging.
**Sources:** `pages-event` system, orchestration-workbench (`execution.agent-selected`), dock-workbench (`pages-dock-toggle`)
**Exploration:** quick
**Status:** captured

## D9: graph-stencil-cognitive — follow established stencil pattern

**Choice:** New `graph-stencil-cognitive` package following the established pattern from graph-stencil-case/htn/org/swf. Each SubgraphType (PERSON, GOAL, ACTIVITY, PLACE, PROJECT, ORGANISATION, CONCEPT) gets a distinct node stencil matching the existing mockups and SVGs. PAD pill on every node, confidence as border opacity, edge type rendering with validation tier styling. Adapter maps CognitionApi `graph()` response to GraphModel.
**Alternatives:** None meaningful — the stencil architecture is established and well-proven across 4 existing packages.
**Rationale:** Follow-the-pattern. Stencil packages provide the rendering layer; consumer components compose them. The mockups (visualiser-mockups.html, graph-visualisation-mockups.html) and their SVGs already define the visual spec.
**Trade-offs:** None significant — established pattern with known trade-offs already accepted.
**Sources:** graph-stencil-case structure, mockups/visualiser-mockups.html, mockups/graph-visualisation-mockups.html, mockups/visualiser-full.png, mockups/graph-visualisation-full.png
**Exploration:** quick
**Status:** captured

## D10: Convergence model — fixed-point default, configurable selective

**Choice:** Fixed-point by default — every text in the system (source or generated) goes through extract → enrich → synthesize, looping until no new content emerges. Configurable to "selective" mode where only reflections trigger re-synthesis (mood snapshots and drive profiles get extract+enrich but don't feed back into Phase 2b).
**Alternatives:**
- Fixed-point only — simplest code, but no escape valve when full convergence is wasteful
- One-deep — generated content goes through extract+enrich once, no re-synthesis. Simpler but misses insights-from-insights
- Selective only — limits richness by default
**Rationale:** Full fixed-point produces the richest knowledge graph. Selective mode is a cost dial — reflections carry the most semantic value for re-synthesis, while mood snapshots and drive profiles rarely surface new entities. Config makes the choice explicit rather than hardcoded.
**Trade-offs:** Fixed-point costs more LLM calls (typically 2-3 passes). Selective mode loses potential cross-domain insights from mood/drive reprocessing.
**Sources:** Issue #525, cognitive-extraction-methodology.md §5.1
**Exploration:** quick
**Status:** captured

## D11: Idempotency model — item markers + manifest

**Choice:** Dual-level idempotency: (1) Each memory/entity carries processing flags (`structurally_extracted`, `enriched`, `synthesis_pass`) stamped as processing happens. Scripts skip items with existing markers. (2) A `manifest.json` tracks pass-level state (pass number, current step, completion status, new-memory counts). Scripts write output incrementally after each item. On restart: read manifest to find current pass/step, read markers to skip processed items.
**Alternatives:**
- Step-level checkpoints (.done files) — simpler code but wastes all work on crash mid-step (a 100-memory enrichment step that crashes at item 80 redoes all 80)
- Content-hash gating — elegant across runs but doesn't help with mid-step crashes, and hash computation adds complexity without proportional benefit
**Rationale:** Item-level granularity means a crash at item 80/100 loses at most 1 item of work. The manifest provides quick resume routing (which pass, which step) without scanning all data. Incremental writes make the data file the checkpoint — no separate state to keep in sync.
**Trade-offs:** More file I/O (write after each item). Negligible overhead given LLM calls take seconds per item. Processing markers add fields to the data model — but they double as provenance metadata.
**Sources:** Issue #525
**Exploration:** quick
**Status:** captured

## D12: Confidence decay — pass-based ceiling

**Choice:** Each convergence pass caps maximum confidence: pass 1 = 1.0, pass 2 = 0.8, pass 3 = 0.6, pass 4+ = 0.4. Content generated in pass N gets `confidence.origin = INFERRED` automatically (unless the LLM judges SPECULATED). The LLM's assigned confidence is clamped to the pass ceiling. Synthesis skips entities where all new data since last synthesis is below confidence 0.4. Combined with a max-passes safety bound (default 5), this guarantees both correctness and termination.
**Alternatives:**
- Source-chain decay (multiplicative 0.7× per derivation link) — more principled but requires tracking full provenance chains; overhead not justified when pass-based ceiling achieves similar convergence
- No decay, dedup only — simpler but dedup quality becomes the sole correctness barrier; text similarity misses semantic near-duplicates
**Rationale:** Pass-based ceiling is simple to implement (one comparison per item), transparent to inspect, and provides a hard bound on inference depth. The ceiling values (1.0, 0.8, 0.6, 0.4) match the existing ConfidenceOrigin semantics: STATED ≈ 1.0, INFERRED ≈ 0.6-0.8, SPECULATED ≈ 0.3-0.5. Natural alignment.
**Trade-offs:** Coarser than source-chain decay — all items in a pass get the same ceiling regardless of their actual derivation depth within that pass. Acceptable because passes are short (each pass processes a small batch of generated content).
**Sources:** Issue #525, cognitive-api Confidence record, ConfidenceOrigin enum
**Exploration:** quick
**Status:** captured

## D13: Convergence extraction — batched per entity

**Choice:** Group generated memories by subject entity. One LLM call per entity with all its new memories + existing graph context (known entities, edges, neighbourhood). The prompt asks for NEW entities, NEW edges, and additional memories — not re-extraction of what's already known. More efficient (1 call per entity vs 3 per memory) and produces richer extraction because the LLM sees cross-memory patterns within an entity's generated content.
**Alternatives:**
- One-per-memory (3 calls each, same as pass 1) — consistent with source passage pattern but expensive for short generated text (1-2 sentences each), and loses cross-memory pattern visibility
- Hybrid batch/solo by text length — marginal benefit over pure batching; generated text is almost always short
**Rationale:** Generated memories are short (1-2 sentences), entity-scoped, and often thematically related (all reflections about the same entity). Batching lets the LLM see "Frida has 3 reflections about pain-to-art transformation" and extract the meta-pattern, rather than processing each independently. Graph context in the prompt enables dedup against known entities (the prompt lists what's already known).
**Trade-offs:** Different prompt structure from pass 1 — two code paths for extraction. Acceptable because the inputs are fundamentally different (short synthesized text vs. long biographical passages).
**Sources:** Issue #525, extract_structure.py current implementation
**Exploration:** quick
**Status:** captured

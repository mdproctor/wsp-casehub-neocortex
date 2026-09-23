# Goal Cognition Examples + Blog Article — Design Spec

**Issue:** casehubio/neocortex#380
**Date:** 2026-09-23
**Status:** Draft

## Goal

Create a walkthrough example module demonstrating the full goal cognition substrate, and a substantial educational blog article aimed at agent builders — with SVG illustrations showing goal graphs evolving through consolidation cycles, affect computation, and retrieval modulation.

## Blog Article

### Working title

"When your agent forgets what it wants"

### Thesis

Most agent frameworks treat goals as disposable strings — a prompt says "help the user," the LLM acts, and the goal vanishes. Here's what happens when you give goals structure, emotional weight, and progressive detail — illustrated across four domains.

### Structure

Eight sections. Each of sections 2-5 uses a different real-world scenario to demonstrate one capability of the goal cognition substrate. Sections 6-8 synthesise.

**Section 1 — The problem: goal as a string**

Short opener. Most frameworks: prompt in → actions out → goal gone. No memory of what the agent was trying to do, what blocked it, or how it felt about pursuing it. This is like a person who forgets what they want every time they blink.

SVG: a prompt bubble with "help the user book a flight" floating in empty space — no edges, no state, no history.

**Section 2 — Research agent: progressive resolution**

Scenario: a research agent managing a PhD student's goals. "Understand transformers" is aspirational — a single node, low resolution. "Submit NeurIPS paper" has a deadline in 3 weeks — fully decomposed into sub-goals (literature review, experiments, writing, formatting) with dependency edges between them.

Demonstrate: GoalResolutionPhase Expand (approaching deadlines trigger decomposition) and Prune (distant aspirations collapse back when sub-goals haven't been accessed).

SVG: side-by-side comparison showing the same goal graph at low vs high resolution. The distant goal is a single node; the approaching goal is a fully decomposed sub-graph with typed edges.

**Section 3 — Product team: dependencies change everything**

Scenario: an agent tracking product goals. "Ship v2.0" is blocked by "hire senior engineer" (blocks edge). "Improve onboarding" enables "reduce churn" (enables edge). "Build payment integration" requires "PCI compliance review" (requires edge).

Demonstrate: GoalResolutionPhase Revise (blocker resolves → blocked goal activates), GoalPrioritizationPhase (composite priority recomputes when dependencies change), cycle detection (prevents circular blocking).

SVG: dependency graph with typed edges (blocks in red, enables in green, requires in blue). Show before/after: blocker completed, blocked goal transitions from blocked→active, priority recomputes.

**Section 4 — Personal assistant: goals have feelings**

Scenario: a personal assistant agent. User keeps asking about cooking — the agent hasn't been told "learn to cook" but the GoalRecognitionPhase detects the implicit goal from experience memories. Once tracked, the goal accumulates affect: urgency when a dinner party is coming, frustration when the grocery delivery is late (blocked + urgent), satisfaction when the first dish succeeds.

Demonstrate: GoalRecognitionPhase (implicit goal discovery from experience), GoalAffectPhase (PAD computation from status + urgency), the emotional landscape of goal pursuit.

SVG: affect trajectory showing pleasure/arousal/dominance dimensions changing over time as goal status changes — a waveform that dips on frustration and peaks on completion.

**Section 5 — Game NPC: shared sub-goals and biased memory**

Scenario: a game character with two active quests — "Rescue the princess" and "Find the ancient artifact." Both require talking to the blacksmith. GoalResolutionPhase Merge detects the shared sub-goal and creates contributes-to edges to both parents. When the NPC is actively pursuing the rescue quest, GoalRelevanceModulationFactor biases memory retrieval toward memories connected to that quest — the blacksmith's location, weapon types, castle layout surface more readily than unrelated memories.

Demonstrate: GoalResolutionPhase Merge (shared sub-goal detection), GoalRelevanceModulationFactor (retrieval biased by graph proximity to active goals).

SVG: two goal trees sharing a merged sub-goal node, with retrieval weight annotations showing distance decay (1.0 → 0.7 → 0.4 → 0.0).

**Section 6 — The consolidation sleep cycle**

Ties everything together. The five steps run during the agent's "sleep" — background consolidation when the system is idle. Each step maps back to a scenario from sections 2-5.

SVG: circular phase diagram (Prune → Expand → Merge → Revise → Sync) with priority annotations and one-line labels connecting each step to its scenario.

**Section 7 — The narrow interface**

Why this doesn't couple everything. Two arrows: neocortex submits goals for execution (prose + priority), engine returns outcomes as experience events. No shared types. No shared graph. Each system evolves independently.

SVG: simple architecture diagram — neocortex ↔ engine via two narrow channels.

**Section 8 — What this opens up**

Forward-looking close. No summary. What becomes possible: opportunity cost awareness, dread/avoidance patterns, emergent goal discovery. End when the point is made.

### Voice and style

Article/explanation, discursive mode. Personal voice (Mark Proctor style — state findings directly, earn authority through evidence, end when finished). ~2500-3500 words + 7-8 SVG illustrations.

### Code blocks

Include 2-3 short code snippets where the code IS the explanation — the Goallike trait interface (7 accessors), the priority formula, the GoalRelevanceModulationFactor distance weights. Not full class dumps.

## Example Module

### Module: `examples/example-goal-cognition`

**Dependencies:** mindmap-api, mindmap-inmem, mindmap-intelligence, mindmap, cognitive-api, cognitive-index, memory-api, memory-inmem, memory-core

**Test class:** `GoalCognitionWalkthroughTest`

Pattern: `@TestInstance(PER_CLASS)`, `@TestMethodOrder(OrderAnnotation.class)`, `@Tag("smoke")`. Matches `MindMapIntelligenceWalkthroughTest`.

### Walkthrough phases

Each phase is a `@Test @Order(N)` method with assertThat verification.

**Phase 1 — Build the goal graph**

Create a GOAL subgraph. Add goals with varying horizons:
- "Understand transformers" — aspirational, low resolution
- "Submit NeurIPS paper" — immediate, high urgency (0.9)
- "Learn to cook" — medium-term, origin=experience

Add dependency edges: paper requires understanding transformers.

**Phase 2 — Goallike trait access**

`Thing.as(Goallike.class)` — verify all 7 property accessors return correct values.

**Phase 3 — Goal vocabulary and edges**

Add typed edges (blocks, enables, requires, contributes-to, decomposes-into). Verify alias resolution ("unblocks" → "enables").

**Phase 4 — Expand approaching goals**

Provide a test CognitiveGoalDecomposer that decomposes "Submit NeurIPS paper" into sub-goals. Run GoalResolutionPhase. Verify sub-goal nodes created with decomposes-into edges, resolution updated to "high".

**Phase 5 — Prune distant goals**

Set "Understand transformers" to aspirational + high resolution with sub-goals from a prior expansion. Run GoalResolutionPhase. Verify sub-goals removed, resolution dropped to "low".

**Phase 6 — Merge shared sub-goals**

Create two parent goals with similarly-named sub-goals. Run GoalResolutionPhase. Verify merge and contributes-to edges.

**Phase 7 — Revise dependencies**

Set a goal as blocked. Complete its blocker. Run GoalResolutionPhase. Verify status transitions to active.

**Phase 8 — Goal affect**

Run GoalAffectPhase. Verify PAD dimensions: urgent goal gets high arousal, blocked goal gets negative pleasure, completed goal gets positive pleasure.

**Phase 9 — Goal prioritization**

Run GoalPrioritizationPhase. Verify composite priority computed, structurally important goals (many inbound edges) rank higher.

**Phase 10 — Goal-conditioned retrieval**

Create concept nodes connected to goal nodes at various distances. Create Memory objects. Run GoalRelevanceModulationFactor. Verify distance-decayed weights: 1.0 for 1 edge, 0.7 for 2, 0.4 for 3, 0.0 for 4+.

## References

- `specs/issue-345-goal-cognition/2026-09-23-goal-cognition-design.md` — implementation design
- `examples/example-mindmap-intelligence/` — walkthrough test pattern
- `blog/2026-09-23-mdp01-how-agents-think-about-what-they-want.md` — existing diary entry
- casehubio/neocortex#345 — implementation epic

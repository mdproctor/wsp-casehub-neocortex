# Cognitive Architecture Roadmap

> Captured from architectural discussion 2026-09-30 during blocks#303
> migration design. Integrates existing open issues with new directions.

## Architectural Premise

Neocortex is the complete single-agent cognitive stack. A cognitive LLM
agent doesn't need blocks — blocks adds multi-agent orchestration and
declarative configuration (YAML/annotation DSL). Everything inside one
agent's head belongs in neocortex.

The entire cognitive state is a graph of degrees — mood (PAD values),
drive intensities, need satisfaction levels, goal priorities, confidence
values, trait activations. Multi-dimensional numeric space. The system
maps these degrees to LLM behavior through prompt rendering and
cognitive directives.

---

## Phase 1: Complete Extraction

**Goal:** All cognitive code in neocortex. No bridge in blocks.
**Status:** Batches 1–6f done. Batch 7 ready for execution.

| Issue | Repo | What |
|-------|------|------|
| #303 | blocks | Migrate cognitive state — Batch 7: prompt rendering, defaults, cleanup |
| #378 | neocortex | Migrate social cognition stores (related) |

### What this achieves
- Neocortex is self-contained — single-agent cognitive stack
- CognitionCore.promptSections() wired up
- Prompt rendering composable and co-located with cognitive types
- Blocks retains only: AvatarCognition adapter, YAML DSL

### Decisions
- D1 (revised): Complete extraction, no bridge
- D7: Prompt rendering is cognitive
- D10: Internal cognitive LLM calls use separate context

---

## Phase 2: Cognitive Integration

**Goal:** Wire landed neocortex capabilities into the agent loop.
**Depends on:** Phase 1 (cognitive code in neocortex)

| Issue | Repo | What |
|-------|------|------|
| #311 | blocks | Epic: wire cognitive capabilities into agent loop |
| #312 | blocks | Consolidation signal consumption |
| #313 | blocks | CBR plan adaptation — case-based reasoning in decision loop |
| #314 | blocks | Reflection consumption |
| #316 | blocks | TemporalFocus integration |
| #319 | blocks | CognitiveProfile deep integration (landed) |
| #283 | blocks | Directive-minimal architecture — shift cognitive data from briefing to neocortex |

### What this achieves
- Agent actually USES the cognitive capabilities (not just computes them)
- CBR informs action selection
- Consolidation signals influence attention
- Directive carries identity + instructions, not cognitive data (aligns
  with D8: cognitive brief = eidos base + evolved layer)

### Key insight: #283 and D8 converge
blocks#283 (directive-minimal) and D8 (cognitive brief = eidos + evolved)
are the same architectural direction from different starting points.
Directives carry identity and cognitive instructions ("how to think").
Dynamic cognitive state comes from neocortex subsystems. The brief IS the
directive-minimal result.

---

## Phase 3: Prompt Rendering & Evaluation

**Goal:** Optimize how cognitive state reaches the LLM.
**Depends on:** Phase 1 (rendering in neocortex), Phase 2 (integration)

| Issue | Repo | What |
|-------|------|------|
| #390 | neocortex | Evaluate rendering formats: prose vs JSON vs hybrid |
| #308 | blocks | Context-budget-aware prompt rendering |
| #386 | neocortex | Cognitive simulation scenarios — time-collapsed multi-week runs |
| #385 | neocortex | Scenario calibration — interactive per-agent questionnaire |

### What this achieves
- Each driver's rendering format is pluggable (prose/JSON/hybrid)
- Rendering adapts to context window budget and session lifecycle
- Simulation infrastructure for measuring behavioral quality
- Calibration tools for tuning agent parameters

### Architecture requirement
Rendering format is a per-driver strategy. Pluggable without touching
cognitive computation. Session-aware: full context at session start,
incremental mid-session. Budget-aware: verbose in 128K, compressed in 8K.

---

## Phase 4: Metacognition — Adaptive Brief

**Goal:** The cognitive brief evolves based on experience.
**Depends on:** Phase 2 (#283 directive-minimal), Phase 3 (#390 format eval)

| Issue | Repo | What |
|-------|------|------|
| #391 | neocortex | Adaptive cognitive brief — metacognitive feedback loop |

### Two-layer brief
1. **Base layer** (eidos prompt cycle) — stable identity, capabilities,
   personality-driven reasoning style. Generated from agent descriptor +
   cognitive profile. Changes rarely.

2. **Evolved layer** (cognition) — learned adaptations from experience.
   "Mood state works better as behavioral tendency than numeric value."
   Evolves autonomously via consolidation.

### Feedback loop
Agent reports observations (what worked, what didn't). Separate cheaper
LLM processes observations in batch. Updates brief before next session.
Automatic signals: which sections the LLM referenced vs ignored, outcome
metrics, token cost vs behavioral impact.

### Timing
No explicit lifecycle hook. Consolidation scheduler triggers
autonomously based on accumulated significance.

---

## Phase 5: Adversarial Cognitive Subsystems (Research)

**Goal:** Explore whether LLM reasoning within cognitive domains produces
measurably better agent behavior than mechanical computation.
**Depends on:** Phase 1 (architecture), Phase 3 (pluggable rendering)
**Framing:** Purely experimental. Even if results are positive, may stay
turned off for cost. Mechanical approach is the proven production default.

| Issue | Repo | What |
|-------|------|------|
| #392 | neocortex | Multi-agent cognitive architecture — Inside Out model |

### Three-tier architecture
1. **Sub-LLMs** — long-lived, domain-specialized. Each reasons about its
   area (emotion, drives, narrative, strategy, memory) with accumulated
   history. Advocates for its domain's perspective.

2. **Coordinator LLM** — executive function. Mediates adversarial
   deliberation between sub-LLMs. Resolves conflicts into coherent
   cognitive directives.

3. **Main cognitive LLM** — receives coordinated output. Unaware of
   internal debate.

### Processing mode spectrum
Configurable per domain, per deployment:

| Mode | Tick behavior | Cost |
|------|--------------|------|
| Mechanical | Formula computation | Cheap, fast, proven |
| Hybrid | Mechanical + sub-LLM on significant events | Moderate |
| Full sub-LLM | Reasoning agents every tick | Expensive, rich |

### What changes
Currently: graph of degrees → weighted formula → score → template →
prompt text → LLM behavior.

With sub-LLMs: graph of degrees → LLM interprets what degrees mean in
context → reasoned judgment → coordinator mediates → coherent directive
→ LLM behavior.

The adversarial tension between subsystems (emotion vs strategy, short-term
vs long-term, social harmony vs authenticity) is where interesting behavior
emerges. The mechanical version approximates this with weighted scores.
The LLM version actually argues about it.

---

## Phase Dependencies

```
Phase 1: Complete Extraction (#303)
    │
    ├── Phase 2: Cognitive Integration (#311, #283, #313)
    │       │
    │       └── Phase 4: Adaptive Brief (#391)
    │
    ├── Phase 3: Rendering & Evaluation (#390, #308, #386)
    │       │
    │       ├── feeds into Phase 4
    │       └── feeds into Phase 5
    │
    └── Phase 5: Adversarial Subsystems (#392) [research]
            uses Phase 2 + Phase 3
```

Phase 1 is prerequisite for all others. Phases 2 and 3 are largely
independent. Phase 4 builds on both. Phase 5 is the ambitious experiment
that ties everything together.

---

## Related issues (not phased)

| Issue | Repo | What |
|-------|------|------|
| #274 | blocks | Epic: deepen cognitive advantage — measurement framework |
| #298 | blocks | Epic: cognitive emotion architecture — OCC, mood bridge |
| #361 | neocortex | Refactor: resolve mindmap → cognitive-index dependency |
| #387 | neocortex | People, places, relationships, activities as cognitive entities |
| #355 | neocortex | Epic: GA audit — code quality, performance, API hardening |
| #364 | neocortex | Docs: consumer-facing SPI Javadoc for GA |
| #286 | blocks | User guide: neocortex seeding best practices |

---

## Decisions captured in this session

| ID | Decision | Phase |
|----|----------|-------|
| D1 | Complete extraction, no bridge (revised) | 1 |
| D7 | Prompt rendering is cognitive | 1 |
| D8 | Cognitive brief = eidos base + evolved layer | 4 |
| D9 | Lifecycle follows orchestrator pattern | 5 |
| D10 | Internal cognitive LLM calls use separate context | 1, 5 |

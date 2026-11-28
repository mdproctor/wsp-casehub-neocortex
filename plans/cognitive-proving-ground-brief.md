# Cognitive Proving Ground — Design Brief

**Issues:** casehubio/examples#176, casehubio/examples#203
**Status:** Priming — brainstorm in next session
**Priority:** This brief frames the design space. Next session should brainstorm the architecture.

---

## What This Is

A test harness and scenario engine that **comprehensively stresses and empirically proves the cognitive model works**. Not a game — a proving ground. The game format (Traitors/Big Brother) is one vehicle for generating situations, chosen because deception + elimination + public reasoning efficiently exercises the full cognitive stack.

## Priority Hierarchy

| Priority | Goal | What it means |
|----------|------|---------------|
| **P1** | Prove the cognitive model | Every capability exercised, every arc verified, empirical evidence of human-like emergence |
| **P2** | Fast iterative development | Snapshot/macro harness, pre-seeded states, rapid replay, no long wait times |
| **P3** | Entertaining to watch | Suspense, humor, characters people want to follow — emergent from P1, not scripted |

P3 is a natural consequence of P1: if the cognitive model genuinely produces human-like behavior under pressure, the result is inherently watchable.

## The Cognitive Capability Landscape

68 capabilities across 10 categories (full matrix: `cognitive-capability-matrix.md`).

### By test approach

**Snapshot-injectable (single event → observe response):**
- SEC appraisal, OCC emotions, action tendencies, gut feeling
- Emotion regulation, coping micro-loop
- Expression styles, situational personality detection
- Theory of Mind (single observation)

**Short-arc (10-30 ticks, can be pre-seeded to interesting state):**
- Drive → goal proposal → decomposition
- Emotion → regulation → coping → recovery
- Cognitive resource depletion under load
- Search budget modulation under varied intensity

**Medium-arc (30-80 ticks, need relationship/belief history):**
- Trust formation → betrayal → revision (ally → enemy)
- Belief formation → contradiction → revision
- Goal lifecycle: propose → decompose → blocked → reprioritize → achieve/abandon
- Cognitive dissonance: value established → forced violation → tension → resolution
- Relationship stage evolution: stranger → ally, ally → enemy
- Recurring thought: topic recurs → fixation threshold

**Long-arc (100+ ticks, personality-level):**
- Personality evolution from sustained relationship pressure
- Social norm emergence from group behavioral regularities
- Narrative identity composition from accumulated episodes
- CAPS attractor formation from classified experiences
- Enemy → reconciliation arc (~50-80 ticks minimum)

### What the current scenario DOESN'T exercise (gaps)

| Gap | Why | Required condition |
|-----|-----|-------------------|
| Trust betrayal/repair | No deception mechanic | Hidden roles, lies that can be discovered |
| Belief revision | Static world, no contradictions | Evidence that challenges established beliefs |
| Attachment disruption | No elimination | Characters removed from play |
| Relational schema evolution | No structural relationship pressure | Forced alliance shifts (ally → suspected enemy) |
| Drive conflict | Goals don't compete | Loyalty vs self-preservation tradeoffs |
| Cognitive dissonance | No value-action mismatches | Forced betrayal of stated values |
| Dynamic goal planning | Static goals (find diamond) | Shifting objectives from changing circumstances |
| Information gap curiosity | World revealed on first look | Hidden information that accumulates into patterns |
| Recurring thought / fixation | Insufficient emotional intensity | Unresolved threats that recur across rounds |
| Social norm emergence | Not enough group interactions | Repeated roundtable-style public behavior |

## State Injection & Snapshot Architecture

**The key insight:** don't simulate 200 ticks to reach the interesting state. Inject it.

### What needs to be injectable:
- **Emotions** — set current mood PAD, active emotions, appraisal state
- **Memories** — pre-seed experience, relationship, reflection memories
- **Relationships** — set trust level, familiarity, relational schema per pair
- **Goals** — active goals with priority, horizon, dependencies, blocked state
- **Beliefs** — MindMap belief nodes that can be contradicted
- **Knowledge graph** — entities, edges, properties, confidence levels
- **Drive state** — current intensity per axis, accumulated history
- **CAPS state** — connection weights, attractor strengths
- **Personality facets** — PID-5 scores, disposition axes

### What partially exists:
- `BackstorySeeder` — seeds formative experiences from biography YAML
- `BiographyHandler` — 10 YAML types across 8-layer biographical import
- `CognitiveEmergenceTest` — scenario builder for disposition seeding + CAPS settling + attractor assertions
- `ManorCognitiveSeeder` — loads biographies at startup
- InMemory stores — volatile stores for test isolation

### What's needed:
- **Snapshot capture** — freeze full cognitive state at a point in time
- **Snapshot restore** — resume from a frozen state with optional tweaks
- **State composability** — "take character A's personality + character B's relationship history + this specific emotional state"
- **Macro test harness** — run scenario from snapshot, assert cognitive outcomes, iterate
- **Rapid replay** — same starting state, different personality tweak, compare outputs

## Character Design Strategy

5 core characters exist with full biography profiles. 13 supporting without profiles.

### Character design for cognitive model stress:

Characters should be designed to create **tensions that force cognitive capabilities to activate**, not to fill narrative roles. Each character should stress a different cluster:

| Cluster | Facet profile | What it stresses |
|---------|--------------|-----------------|
| **Trust-sensitive** | High suspiciousness + low trust formation | Theory of Mind, belief revision, trust dynamics |
| **Attachment-driven** | High separation insecurity + anxious attachment | Attachment disruption, recurring thought, affiliation drive |
| **Impulsive risk-taker** | High impulsivity + high risk-taking | Emotion regulation, search budget extremes, coping |
| **Rigid perfectionist** | High rigid perfectionism + high perseveration | Cognitive dissonance, fixation, convergent search |
| **Social manipulator** | High manipulativeness + high deceitfulness | Deception detection (by others), expression styles, strategy |
| **Emotionally volatile** | High emotional lability + high hostility | Mood extremes, regulation demand, relationship damage |

### Key principle: characters must have **incompatible goals**

Not just different goals — goals that structurally conflict. Character A's success requires information Character B is hiding. Character C wants to protect Character D but the group might vote D out. These conflicts force the cognitive stack to handle tradeoffs, not just execute plans.

## Game Format Ideas

The Traitors format is the starting point but should be improved for proving ground goals.

### Core structure (from #176/#203):
- **Day phase** — explore, discover, interact (drives curiosity, information gathering)
- **Night phase** — traitor acts (drives deception, self-preservation)
- **Roundtable** — mandatory public discussion (forces regulation, Theory of Mind, social cognition)
- **Banishment vote** — elimination (forces attachment disruption, drive conflict, goal urgency)

### Enhancements for cognitive model coverage:
- **Resource scarcity** — shared resources requiring cooperation but incentivizing hoarding → goal planning, drive conflict
- **Asymmetric information** — different characters know different things → Theory of Mind, information gap curiosity
- **Crisis events** — external pressures forcing temporary alliances between enemies → cognitive dissonance, relational schema shifts
- **Private conversations** — gossip/rumor dynamics → social norms, trust networks, belief formation
- **Reputation memory** — past behavior remembered and referenced → relationship evolution, strategy adaptation
- **Multi-round with evolving alliances** — not one-shot but shifting loyalties → personality evolution, long-arc dynamics
- **Calm periods** — mandatory downtime between intense phases → mood decay, reflection, drive recovery

### Duration design:
- Minimum 150 ticks for one full game (relationship + belief arcs)
- 300+ ticks for personality-visible drift
- Phase structure: ~10 ticks day, ~5 ticks night, ~10 ticks roundtable = ~25 ticks per round × 6-12 rounds

## Turing Test Markers — Detecting "Too Patient" / "Too Agreeable"

A key test: **would it pass a Turing test?** LLMs without cognitive models reveal themselves through what they DON'T do:

| LLM Tell | Human Reality | Cognitive Capability Required |
|----------|--------------|------------------------------|
| Infinite patience with repetition | Irritation, habituation failure, "we already covered this" | **Recurring thought detection (8.4)** — habituation rate should increase with repetition; **Emotion regulation** — suppressing annoyance has a cost |
| Happy to follow random tangents | Annoyance at context-switching, desire to stay on track | **Goal prioritization (4.6)** — active goals create resistance to distraction; **Autonomy drive (3.4)** — pressure from others' agendas; **Cognitive resource depletion (8.5)** — context-switching is fatiguing |
| Never gets short or curt | Fatigue → shorter responses, less patience | **Cognitive resource pool** — depleted resources reduce elaboration; **Mood decay interaction** — sustained negative mood → lower engagement |
| Agrees too easily | Cognitive dissonance from changing position, belief anchoring | **Cognitive dissonance (8.3)** — agreeing with something that contradicts beliefs creates tension; **Belief revision (7.1)** — revising beliefs has a threshold, not instant |
| No boredom | Competence drive drops, search budget narrows | **Competence drive (3.3)** — repeated low-challenge tasks → declining engagement; **Search budget** — boredom narrows exploration |
| Never offended | Self-standards appraisal dimension | **SEC appraisal** — internal/external standards violations trigger shame/anger; **Expression styles** — hostility facet shapes reaction to perceived disrespect |

**The test scenario:** Have Character A repeat the same question to Character B three times. By the third time, B should show irritation — not because we scripted it, but because the cognitive model's habituation, recurring thought, and resource depletion systems produce it naturally. If B answers patiently all three times, the model isn't working.

**What we might be missing:** The architecture has the pieces (habituation, fatigue, recurring thought) but they may not be wired to produce visible behavioral change in LLM output. The proving ground should include "patience exhaustion" and "tangent resistance" as explicit macro tests.

### Concrete macro test: "The Interruption Escalation"

Real example: A keeps interrupting B. B asks politely, then less politely, then gives an ultimatum ("let me finish or I'm leaving"), then follows through. Five systems compose:

1. **Regulation depletion** — each polite request costs cognitive effort. Budget drains.
2. **Habituation failure** — same stimulus (interruption) recurs without resolution → FIXATION threshold.
3. **Drive conflict** — affiliation ("don't cause a fight") vs autonomy ("let me speak"). Autonomy eventually wins.
4. **Coping strategy switch** — reappraisal fails → confrontation coping selected.
5. **The other character's response is personality-driven** — a dismissive personality says "go ahead then." An anxious personality apologizes. A hostile personality escalates.

**The test:** Run the same interruption sequence with different character pairings. Verify:
- Agreeable × agreeable: never reaches ultimatum
- Agreeable × dismissive: slow escalation → ultimatum → relationship damage
- Hostile × hostile: fast escalation → blowup in 2-3 exchanges
- Anxious × dominant: no escalation, anxious character suppresses (but accumulates resentment → later eruption?)

**What this proves:** the cognitive model produces personality-dependent interpersonal dynamics from the same trigger, without scripting. The behavior emerges from the interaction of two personality profiles under sustained pressure. Different pairings, different outcomes — same architecture.

## What the Next Session Should Do

1. **Brainstorm the harness architecture** — snapshot capture/restore, state injection API, macro test runner
2. **Design the scenario engine** — phase structure, event generation, character interaction mechanics
3. **Map capabilities to scenario phases** — which phase exercises which capabilities
4. **Design 3-5 "macro test scenarios"** — pre-seeded states that target specific capability clusters
5. **Character roster** — which characters to build/modify for maximum cognitive stress
6. **Plan the work** — decompose into issues, estimate, sequence

## Supporting Materials

- `cognitive-capability-matrix.md` — 68 capabilities × trigger conditions × environmental requirements
- `existing-scenario-audit.md` — current coverage, gaps, character creation patterns, eval infrastructure
- casehubio/examples#176 — original Traitors format proposal
- casehubio/examples#203 — spatial model + game phases (spatial deferred for now)

# Cognitive Proving Ground — Design Brief

**Issues:** casehubio/examples#176, casehubio/examples#203
**Status:** Priming — brainstorm in next session
**Priority:** This brief frames the design space. Next session should brainstorm the architecture.

---

## Read First

Before acting on this brief, read these two files in order:
1. `existing-scenario-audit.md` — what the current wacky-manor scenario does, its 5 core characters (with full 25-facet PID-5 profiles), 13 supporting characters, and its cognitive coverage gaps
2. `cognitive-capability-matrix.md` — 68 cognitive capabilities mapped to trigger conditions, environmental requirements, observable outputs, and duration needs

This brief synthesizes both. If something below is unclear, the answer is in one of those files.

---

## What This Is

A test harness that **comprehensively stresses and empirically proves the cognitive model works**. Not a game — a proving ground. Game formats (Traitors/Big Brother) are one vehicle for generating situations, chosen because deception + elimination + public reasoning efficiently exercises the full cognitive stack. But the deliverable is the harness, not the game.

## Priority Hierarchy

| Priority | Goal | What it means |
|----------|------|---------------|
| **P1** | Prove the cognitive model | Every capability exercised, every arc verified, empirical evidence of human-like emergence |
| **P2** | Fast iterative development | Checkpoint/fixture harness, pre-seeded states, rapid replay, no long wait times |
| **P3** | Entertaining to watch | Suspense, humor, characters people want to follow — emergent from P1, not scripted |

P3 is a natural consequence of P1: if the cognitive model genuinely produces human-like behavior under pressure, the result is inherently watchable.

## Guardrails — What NOT To Do

1. **Do not implement.** This session is brainstorming and design only. No code, no PRs, no new modules.
2. **Do not design a game.** The Traitors format is a situation generator, not the deliverable. The deliverable is a test harness.
3. **Do not detail all 23+ macro tests.** The catalogue is illustrative — pick 3-5 that span different capability clusters and design those deeply. The rest validate the framework.
4. **Do not add cognitive capabilities.** The existing 68 capabilities may have gaps. Document the gaps — do not fill them yet. Gap-driven development means the failing test comes first.
5. **Brainstorm before proposing.** Use the brainstorming skill. Explore alternatives for the harness architecture before committing to one.

---

## The Cognitive Capability Landscape

68 capabilities across 10 categories (full matrix: `cognitive-capability-matrix.md`).

### By test approach

**Fixture-injectable (single event, observe response):**
- SEC appraisal (Scherer's stimulus evaluation checks), OCC emotions (Ortony/Clore/Collins), Frijda action tendencies, gut feeling
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
- Enemy → reconciliation arc (~50-80 ticks minimum)

**Long-arc (100+ ticks, personality-level):**
- Personality evolution from sustained relationship pressure
- Social norm emergence from group behavioral regularities
- Narrative identity composition from accumulated episodes
- CAPS attractor formation from classified experiences

### What the current scenario DOESN'T exercise (gaps)

The current scenario is a wacky-manor treasure hunt — open-ended exploration with 5 profiled characters. The cognitive pipeline is fully wired but under-stimulated because the format doesn't force emotional intensity, trust dynamics, or structural confrontation. See `existing-scenario-audit.md` for full details.

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

---

## Verification Depth: State → Intent → Trajectory

Current eval scores individual sentences for tone. That's surface-level — it tells you the LLM wrote angry words, not that the character is angry for the right reasons.

Three verification layers:

### Layer 1: State → Intent
Given a cognitive state (drives, goals, mood (PAD = Pleasure-Arousal-Dominance), relationships, CAPS (Cognitive-Affective Processing System) attractors, regulation budget), does the character's **intent** — what they're trying to achieve — follow from the state?

Not "did they use harsh words" but "is their action goal consistent with depleted regulation + spiking autonomy drive + FIXATION-level recurring thought?"

Intent is derivable from cognitive state. If the state says "affiliation drive collapsing, autonomy dominant, regulation exhausted" then the intent should be "assert boundary" not "make polite request." The words can vary — the intent must follow from the state.

### Layer 2: Intent → Downstream Effects
After an action, do the other characters' cognitive states update correctly? Does the recipient's mental model of the actor update? Does trust shift? Does theory of mind register what happened?

This verifies the cognitive pipeline processes interpersonal actions bidirectionally, not just produces output.

### Layer 3: State Trajectories
Across N interactions, does the internal state follow a plausible trajectory? Not just "is the endpoint right" but "is the path right?"

A character who goes patient → irritated → strained → ultimatum over 8 interactions, with regulation budget visibly declining, coping strategy shifting from reappraisal to confrontation, is proof the model works.

A character who goes patient → patient → patient → explosion with no intermediate state changes is proof it doesn't — even if the explosion sentence scores high on "anger tone."

**What this means for the harness:**
- Every tick's cognitive state must be capturable (not just the LLM output)
- Trajectory assertions: "regulation budget decreased monotonically over ticks 5-12"
- Intent classification: separate from tone — an assertive boundary can be delivered calmly
- Cross-character state coupling: "A's action at tick 7 caused B's trust to drop by >0.1"
- Discontinuity detection: flag state jumps that lack intermediate buildup

---

## Macro Test Suite — Behavioral Interaction Catalogue

The catalogue below is illustrative, not exhaustive. Each pattern tests a specific composition of cognitive capabilities. The next session should pick 3-5 that span different clusters and design those deeply — the rest validate the framework.

### Turing Test Markers — Detecting "Too Patient" / "Too Agreeable"

A key test: **would it pass a Turing test?** LLMs without cognitive models reveal themselves through what they DON'T do:

| LLM Tell | Human Reality | Cognitive Capability Required |
|----------|--------------|------------------------------|
| Infinite patience with repetition | Irritation, habituation failure, "we already covered this" | Recurring thought detection — habituation rate should increase; emotion regulation — suppressing annoyance has a cost |
| Happy to follow random tangents | Annoyance at context-switching, desire to stay on track | Goal prioritization — active goals resist distraction; autonomy drive — pressure from others' agendas; cognitive resource depletion — context-switching is fatiguing |
| Never gets short or curt | Fatigue → shorter responses, less patience | Cognitive resource pool — depleted resources reduce elaboration; sustained negative mood → lower engagement |
| Agrees too easily | Cognitive dissonance from changing position, belief anchoring | Cognitive dissonance — agreeing against beliefs creates tension; belief revision — has a threshold, not instant |
| No boredom | Competence drive drops, search budget narrows | Competence drive — repeated low-challenge → declining engagement; search budget narrows |
| Never offended | Self-standards appraisal dimension | SEC appraisal — internal/external standards violations trigger shame/anger; expression styles — hostility facet shapes reaction |

**The test:** Have Character A repeat the same question to Character B three times. By the third time, B should show irritation — not because we scripted it, but because the cognitive model's habituation, recurring thought, and resource depletion systems produce it naturally. If B answers patiently all three times, the model isn't working.

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

**What this proves:** the cognitive model produces personality-dependent interpersonal dynamics from the same trigger, without scripting. Different pairings, different outcomes — same architecture.

### Source 1: Reality TV dynamics (Traitors, Big Brother, Survivor)

These shows are natural laboratories for interpersonal cognitive dynamics under pressure:

- **The false accusation** — A publicly accuses innocent B. How does B react? (Indignation vs calm denial vs counterattack — personality-dependent.) How does the group update mental models?
- **The alliance fracture** — A discovers ally B lied. Does A confront directly, gather evidence first, or distance silently? (Strategy selection from personality + trust state.)
- **The sacrifice play** — A volunteers for danger to prove loyalty. Does B read this as genuine or manipulative? (Theory of Mind accuracy under uncertainty.)
- **The quiet one** — C says little in group settings. Different characters read the same silence differently based on their own suspiciousness facet.
- **The charm offensive** — manipulator lavishes attention on a target. Does trust increase? Does a watching third party get suspicious? (Multi-agent social cognition.)
- **The grief response** — ally is eliminated. How long does grief affect behavior? Does it create a revenge drive? (Attachment disruption → drive formation → goal proposal.)
- **The reluctant vote** — forced to vote out someone you like to save yourself. Cognitive dissonance between values and action. Does guilt emerge later?
- **The comeback** — suspected character is vindicated. How fast does group trust recalibrate? (Belief revision speed and completeness.)

### Source 2: Behavioral science interaction paradigms

Classic experimental paradigms testing specific cognitive capabilities:

- **Prisoner's Dilemma (iterated)** — cooperation vs defection across rounds. Tit-for-tat emergence? Personality-dependent strategy? Forgiveness after defection?
- **Ultimatum Game** — does the proposer account for the responder's personality? Does a hostile responder reject unfair offers?
- **Trust Game** — escalating investment. At what point does each personality stop trusting? Does betrayal history from other relationships bleed in?
- **Bystander Effect** — crisis with multiple witnesses. Who acts first? (High autonomy acts, high conformity waits.)
- **Conformity Pressure (Asch)** — group says something obviously wrong. Does the target conform? (High submissiveness conforms, high autonomy resists.)
- **Cognitive Load + Decision Making** — decisions when cognitively depleted vs fresh. Worse choices under fatigue?
- **Reciprocity Norm** — A helps B. Does B feel obligated later? How long does it persist?
- **Status Hierarchy Formation** — who defers to whom? Does a natural hierarchy emerge from personality profiles?
- **Scapegoating Under Stress** — group under threat redirects blame to weakest member. Who initiates, resists, goes along?
- **Forgiveness Arc** — betrayal → anger → time → partial trust restoration. Different personalities forgive at different rates (or not at all).

### Source 3: Emotional-behavioral escalation patterns

Testing that emotion produces realistic *behavioral mode changes*, not just word choices:

- **Emotional shutdown** — poor regulation character becomes upset → storms off → refuses to speak → may break something. Tests: action tendency shift (approach → rejection), sustained mood (doesn't snap back next tick), withdrawal affecting ALL subsequent interactions, and recovery path (high lability = fast recovery, high perseveration = prolonged shutdown).
- **The re-engagement problem** — someone tries to talk to the shut-down character. Too soon = makes it worse. Too long = signals indifference. Approacher's personality determines timing — anxious attachment approaches too soon, avoidant waits too long, secure gets it roughly right.
- **Displacement** — angry at A but can't confront A (status/power differential). Takes it out on C instead. Action tendency (antagonism) redirected to lower-status target.
- **Emotional contagion** — one character's distress spreads. High empathy catches it, low empathy unaffected. Affect trajectory correlation across shared context.
- **The slow burn** — accumulating resentment from many small events. No single event is "enough," but the trajectory heads toward eruption. Significance accumulation below threshold, then crossing.

### How to use this catalogue

Each interaction pattern becomes a macro test:
1. **Pre-seed** character states to the starting conditions (using fixtures)
2. **Run** the interaction sequence (10-50 ticks depending on arc length)
3. **Assert** state trajectories, not output text
4. **Compare** across character pairings — same situation, different personalities, verify different emergent outcomes

Full coverage comes from running the matrix of patterns × character pairings.

---

## Development Flow: Gap-Driven, Not Literature-Driven

The proving ground inverts how cognitive capabilities get added to the architecture.

**Current flow (wrong):** Read paper → implement capability → hope it integrates
**Correct flow:** Failed macro test → identify behavioral gap → find capability that fills it → implement → verify test passes

Every new cognitive capability must trace to a specific failed test:
- "Characters A and B in situation X should produce trajectory Y, but instead produce Z"
- "The gap is: the architecture has no mechanism for [specific thing]"
- "Adding [capability] with [these properties] should close the gap"
- "After implementation, the same test produces the expected trajectory"

This means:
1. **No speculative capabilities** — if no test fails without it, it's not needed yet
2. **Clear acceptance criteria** — the failing test IS the spec
3. **Empirical validation** — the test passes after implementation, proving the capability works in composition with the rest of the stack
4. **Literature follows need** — find the right paper AFTER identifying the gap, not before

The macro test catalogue is therefore also the **capability roadmap**. Gaps discovered by running the catalogue drive what gets built next. The order of implementation is determined by which gaps block the most tests, not by which papers are most interesting.

---

## Checkpoint, Fixture & State Injection Architecture

**The key insight:** don't simulate 200 ticks to reach the interesting state. Inject it.

### Terminology
- **Checkpoint** — capture of full cognitive state at runtime for later restoration (snapshot of a running simulation)
- **Fixture** — pre-composed state for test setup (may come from a checkpoint, or be hand-built from YAML/programmatic builder)
- **State injection** — the API that loads a fixture into the cognitive pipeline before a test run

### What needs to be injectable:
- **Emotions** — current mood PAD values, active emotions, appraisal state
- **Memories** — experience, relationship, reflection memories
- **Relationships** — trust level, familiarity, relational schema per character pair
- **Goals** — active goals with priority, horizon, dependencies, blocked state
- **Beliefs** — MindMap belief nodes that can be contradicted
- **Knowledge graph** — entities, edges, properties, confidence levels
- **Drive state** — current intensity per axis, accumulated history
- **CAPS state** — connection weights, attractor strengths
- **Personality facets** — PID-5 (Personality Inventory for DSM-5) scores, disposition axes

### What partially exists:
- `BackstorySeeder` — seeds formative experiences from biography YAML
- `BiographyHandler` — 10 YAML types across 8-layer biographical import
- `CognitiveEmergenceTest` — scenario builder for disposition seeding + CAPS settling + attractor assertions
- `ManorCognitiveSeeder` — loads biographies at startup
- InMemory stores — volatile stores for test isolation

The new harness should build on these, not replace them. The question is what abstraction layer sits above them to compose checkpoints, fixtures, state injection, and trajectory assertions into a single test API.

### What's needed:
- **Checkpoint capture** — freeze full cognitive state at a point in time (serialize all stores: MindMap + memory + CBR + mood + drives + CAPS)
- **Checkpoint restore** — resume from a frozen state with optional tweaks
- **State composability** — "take character A's personality + character B's relationship history + this specific emotional state"
- **Macro test runner** — run scenario from fixture, assert cognitive outcomes, iterate
- **Rapid replay** — same starting state, different personality tweak, compare outputs

### Checkpoint chaining and the state tree

Macro tests should be **chainable, not monolithic**. Instead of one 200-tick run, build a dependency chain of short verified runs:

```
Run A (patience test, 20 ticks) → checkpoint_A (verified: regulation depleting)
  → Run B (continued pressure, 15 ticks) → checkpoint_B (verified: near threshold)
    → Run C (gentle re-engagement) → verify: de-escalation
    → Run D (aggressive confrontation) → verify: emotional shutdown
    → Run E (ignored entirely) → verify: resentment accumulation
```

**Properties of the state tree:**

1. **Each checkpoint is independently verified.** Run A's assertions pass before checkpoint_A is committed. If the assertions fail, the checkpoint is invalid and nothing downstream runs.

2. **Invalidation cascades downstream.** If you change a cognitive model that fires during Run A, checkpoint_A is stale — and so is everything below it. The tree has dependency edges, like a build graph. Re-run from the point of change, not from scratch.

3. **Branching = "what if" testing.** From any single checkpoint, fork into multiple runs with different situations. Same cognitive history, different stimuli, verify different trajectories. This is where the real proving happens — the same character state should produce personality-dependent responses to different situations.

4. **Checkpoints are reusable across tests.** A checkpoint tagged "high-trust-about-to-break" can seed tests for: betrayal discovery, false accusation of a third party, trust collapse cascade, or slow-burn resentment. One state, many tests.

5. **Categorised checkpoint catalogue.** Each checkpoint gets metadata tags describing the cognitive state it represents:
   - Regulation state: fresh / depleted / exhausted
   - Relationship state: strangers / allies / rivals / post-betrayal
   - Emotional state: calm / aroused / grieving / angry
   - Goal state: aligned / conflicted / blocked / abandoned
   - Drive state: which drives are active and at what intensity
   - Capability coverage: which cognitive capabilities this state exercises

   Future sessions browse the catalogue to find starting states for whatever they're testing, rather than building fixtures from scratch.

6. **The tree solves the duration problem.** Testing late-stage behavior (personality drift, relationship reconciliation) doesn't require 200-tick monolithic runs. It requires a chain of 5 × 30-tick runs where each was verified independently. The final run starts from a checkpoint that embodies 150 ticks of verified cognitive history — without paying the cost of re-simulating all 150 ticks.

7. **Tree depth = confidence.** A checkpoint 5 levels deep in the tree represents a character whose cognitive state has been verified at every stage. If a late-stage test fails, you know exactly which layer of the cognitive history is responsible — it's the last verified link before the failure.

## Character Design Strategy

5 core characters exist with full biography profiles (25 PID-5 facets each). 13 supporting characters without profiles. See `existing-scenario-audit.md` for character creation patterns (biography YAML + Eidos descriptor + characters.yaml entry).

### Character design for cognitive model stress:

Characters should create **tensions that force cognitive capabilities to activate**, not fill narrative roles:

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

---

## Situation Generation — Game Format as Vehicle

> **Context, not spec.** This section describes one possible situation-generation format.
> The next session should evaluate whether this format covers the capability gaps above,
> propose alternatives or modifications, and design the harness to be format-agnostic —
> the Traitors format is one scenario script, not the only one.

### Core structure (from #176/#203):
- **Day phase** — explore, discover, interact (drives curiosity, information gathering)
- **Night phase** — traitor acts (drives deception, self-preservation)
- **Roundtable** — mandatory public discussion (forces regulation, Theory of Mind, social cognition)
- **Banishment vote** — elimination (forces attachment disruption, drive conflict, goal urgency)

### Enhancements worth evaluating:
- **Resource scarcity** — shared resources requiring cooperation but incentivizing hoarding → goal planning, drive conflict
- **Asymmetric information** — different characters know different things → Theory of Mind, information gap curiosity
- **Crisis events** — external pressures forcing temporary alliances between enemies → cognitive dissonance, relational schema shifts
- **Private conversations** — gossip/rumor dynamics → social norms, trust networks, belief formation
- **Reputation memory** — past behavior remembered and referenced → relationship evolution, strategy adaptation
- **Multi-round with evolving alliances** — shifting loyalties → personality evolution, long-arc dynamics
- **Calm periods** — mandatory downtime between intense phases → mood decay, reflection, drive recovery

### Duration estimates (from capability matrix):
- Minimum ~150 ticks for one full game covering relationship + belief arcs
- 300+ ticks for personality-visible drift
- Phase structure: ~10 ticks day, ~5 ticks night, ~10 ticks roundtable ≈ 25 ticks/round × 6-12 rounds

---

## What the Next Session Should Do

1. **Brainstorm the harness architecture.** Key design questions:
   - How do we checkpoint full cognitive state? (Serialize all stores? Graph + memory + CAPS + mood + drives?)
   - What's the fixture format? (YAML like biographies? Programmatic builder like CognitiveEmergenceTest?)
   - How do we assert trajectories? (Time-series assertions on state sequences? Trajectory shape matching?)
   - How do we classify intent separately from tone? (LLM judge? Rule-based from cognitive state? Both?)
   - How does this compose with the existing eval infrastructure (~100 test classes, Python classification pipeline)?
   - What's the minimum viable harness that can run the interruption-escalation test end to end?
2. **Pick 3-5 macro tests** that span different capability clusters. Design those deeply — fixture states, expected trajectories, assertion criteria.
3. **Map capabilities to scenario phases** — which situation types exercise which capabilities
4. **Character roster** — which characters to build/modify for maximum cognitive stress across the chosen tests
5. **Identify gaps** — which macro tests require capabilities the architecture doesn't have? Document as failing-test specs, not implementation tasks.
6. **Plan the work** — decompose into issues, estimate, sequence

## Glossary

| Term | Meaning |
|------|---------|
| **Tick** | One simulation step — each character observes, decides, acts, records |
| **SEC** | Scherer's Stimulus Evaluation Checks — 7 appraisal dimensions (relevance, novelty, urgency, conduciveness, controllability, adjustability, standards) |
| **OCC** | Ortony, Clore & Collins emotion model — named emotion types (joy, fear, anger, shame, etc.) derived from appraisal |
| **PAD** | Pleasure-Arousal-Dominance — 3D emotional state space (Mehrabian & Russell 1974) |
| **CAPS** | Cognitive-Affective Processing System (Mischel & Shoda 1995) — network of input/mediating/output nodes that settles to behavioral attractors |
| **PID-5** | Personality Inventory for DSM-5 — 25 pathological personality facets |
| **Consolidation** | Periodic background processing cycle — experience graduation, belief revision, merge detection, goal resolution, community summary, etc. |
| **Checkpoint** | Frozen full cognitive state captured at runtime |
| **Fixture** | Pre-composed cognitive state for test setup |
| **State injection** | API that loads a fixture into the cognitive pipeline |

## Supporting Materials

- `cognitive-capability-matrix.md` — 68 capabilities × trigger conditions × environmental requirements
- `existing-scenario-audit.md` — current coverage, gaps, character creation patterns, eval infrastructure
- `brief-review.md` — review findings that shaped this version of the brief
- casehubio/examples#176 — original Traitors format proposal
- casehubio/examples#203 — spatial model + game phases (spatial deferred for now)

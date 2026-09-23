---
title: "How agents think about what they want"
date: 2026-09-23
author: mdp
tags: [architecture, goals, cognitive-architecture, BDI, knowledge-graph, neocortex]
entry_type: note
subtype: diary
series: issue-345-goal-cognition
projects: [casehubio/neocortex]
---

Most agent frameworks treat goals as strings. A prompt says "help the user book a flight," the LLM generates actions, and when the actions stop, the goal is done. There's no memory of the goal, no tracking of what blocks it, no emotional weight to pursuing it, and no way to compare it against competing goals. The goal exists for the duration of one request and vanishes.

This is like building a person who can only think about one thing at a time and forgets it the moment they look away.

I've spent the last two days designing what comes next: a cognitive goal system where goals are persistent, structured, emotionally weighted, and progressively detailed. Not a TODO list — a model of how wanting something actually works.

## The problem with "goal" as a string

Our platform already had goals. Four different kinds, in four different repos, all using the same word.

<svg viewBox="0 0 800 320" xmlns="http://www.w3.org/2000/svg" style="max-width:100%; font-family: system-ui, sans-serif;">
  <defs>
    <marker id="arr" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#666"/></marker>
  </defs>
  <!-- Boxes -->
  <rect x="20" y="20" width="170" height="80" rx="8" fill="#e8f0fe" stroke="#4285f4" stroke-width="2"/>
  <text x="105" y="48" text-anchor="middle" font-size="13" font-weight="bold" fill="#1a73e8">Eidos</text>
  <text x="105" y="68" text-anchor="middle" font-size="11" fill="#333">AgentGoal</text>
  <text x="105" y="84" text-anchor="middle" font-size="10" fill="#666">"what the agent IS for"</text>

  <rect x="210" y="20" width="170" height="80" rx="8" fill="#fef3e0" stroke="#f9ab00" stroke-width="2"/>
  <text x="295" y="48" text-anchor="middle" font-size="13" font-weight="bold" fill="#e37400">Engine</text>
  <text x="295" y="68" text-anchor="middle" font-size="11" fill="#333">Goal (predicate)</text>
  <text x="295" y="84" text-anchor="middle" font-size="10" fill="#666">"when is the case done?"</text>

  <rect x="400" y="20" width="170" height="80" rx="8" fill="#e6f4ea" stroke="#34a853" stroke-width="2"/>
  <text x="485" y="48" text-anchor="middle" font-size="13" font-weight="bold" fill="#1e8e3e">Blocks</text>
  <text x="485" y="68" text-anchor="middle" font-size="11" fill="#333">DriveGoalProposal</text>
  <text x="485" y="84" text-anchor="middle" font-size="10" fill="#666">"what drives want"</text>

  <rect x="590" y="20" width="170" height="80" rx="8" fill="#fce8e6" stroke="#ea4335" stroke-width="2"/>
  <text x="675" y="48" text-anchor="middle" font-size="13" font-weight="bold" fill="#c5221f">Desiredstate</text>
  <text x="675" y="68" text-anchor="middle" font-size="11" fill="#333">GoalCompiler&lt;G&gt;</text>
  <text x="675" y="84" text-anchor="middle" font-size="10" fill="#666">"compile to state graph"</text>

  <!-- Gap -->
  <rect x="210" y="160" width="360" height="80" rx="8" fill="#f3e8fd" stroke="#9334e6" stroke-width="2" stroke-dasharray="8,4"/>
  <text x="390" y="188" text-anchor="middle" font-size="13" font-weight="bold" fill="#7627bb">Neocortex</text>
  <text x="390" y="208" text-anchor="middle" font-size="11" fill="#333">Cognitive goals — the gap</text>
  <text x="390" y="228" text-anchor="middle" font-size="10" fill="#666">"what does wanting this INVOLVE?"</text>

  <!-- Arrows -->
  <line x1="105" y1="100" x2="300" y2="160" stroke="#666" stroke-width="1.5" marker-end="url(#arr)" stroke-dasharray="4,3"/>
  <line x1="295" y1="100" x2="350" y2="160" stroke="#666" stroke-width="1.5" marker-end="url(#arr)" stroke-dasharray="4,3"/>
  <line x1="485" y1="100" x2="430" y2="160" stroke="#666" stroke-width="1.5" marker-end="url(#arr)" stroke-dasharray="4,3"/>
  <line x1="675" y1="100" x2="480" y2="160" stroke="#666" stroke-width="1.5" marker-end="url(#arr)" stroke-dasharray="4,3"/>

  <text x="390" y="290" text-anchor="middle" font-size="11" fill="#999">Four kinds of "goal" feeding into a cognitive layer that didn't exist</text>
</svg>

Eidos stores standing goals on an agent's descriptor — "find the diamond," "protect Penelope." Identity metadata. Engine evaluates goal predicates against case state — `.decision == "approved"` fires a `GoalReachedEvent` and the case completes. Blocks proposes goals from motivational drives — curiosity is high, so propose "explore the library." Desiredstate compiles goals into provisioning DAGs with dependency ordering.

Each layer does something legitimate. None of them tracks what pursuing a goal *involves*, what *blocks* it, how it *feels*, or whether two goals share sub-goals that could be done once.

That's the cognitive gap. And it's the gap that separates an agent that executes goals from one that *thinks about* them.

## Three dimensions of wanting

The architecture we landed on has three interacting goal dimensions — not a hierarchy, not a unified type, but three complementary systems.

<svg viewBox="0 0 800 400" xmlns="http://www.w3.org/2000/svg" style="max-width:100%; font-family: system-ui, sans-serif;">
  <!-- LLM Goals -->
  <rect x="40" y="30" width="220" height="140" rx="10" fill="#e6f4ea" stroke="#34a853" stroke-width="2"/>
  <text x="150" y="58" text-anchor="middle" font-size="14" font-weight="bold" fill="#1e8e3e">LLM Goals</text>
  <text x="150" y="80" text-anchor="middle" font-size="11" fill="#333">Prose. Drives propose them.</text>
  <text x="150" y="98" text-anchor="middle" font-size="11" fill="#333">LLM decomposes recursively</text>
  <text x="150" y="116" text-anchor="middle" font-size="11" fill="#333">until steps bind to capabilities.</text>
  <text x="150" y="140" text-anchor="middle" font-size="10" fill="#666">blocks / langchain4j</text>
  <text x="150" y="158" text-anchor="middle" font-size="10" font-style="italic" fill="#888">"explore quantum computing"</text>

  <!-- Case Goals -->
  <rect x="540" y="30" width="220" height="140" rx="10" fill="#fef3e0" stroke="#f9ab00" stroke-width="2"/>
  <text x="650" y="58" text-anchor="middle" font-size="14" font-weight="bold" fill="#e37400">Case Goals</text>
  <text x="650" y="80" text-anchor="middle" font-size="11" fill="#333">Predicates over state.</text>
  <text x="650" y="98" text-anchor="middle" font-size="11" fill="#333">Machine-evaluated.</text>
  <text x="650" y="116" text-anchor="middle" font-size="11" fill="#333">Cases ARE goal pursuit.</text>
  <text x="650" y="140" text-anchor="middle" font-size="10" fill="#666">engine</text>
  <text x="650" y="158" text-anchor="middle" font-size="10" font-style="italic" fill="#888">".approved == true"</text>

  <!-- Cognitive Goals -->
  <rect x="200" y="230" width="400" height="140" rx="10" fill="#f3e8fd" stroke="#9334e6" stroke-width="2"/>
  <text x="400" y="258" text-anchor="middle" font-size="14" font-weight="bold" fill="#7627bb">Cognitive Goals</text>
  <text x="400" y="280" text-anchor="middle" font-size="11" fill="#333">Knowledge graph nodes. Affect. Dependencies. Priority.</text>
  <text x="400" y="298" text-anchor="middle" font-size="11" fill="#333">Progressive resolution. Consolidation-managed.</text>
  <text x="400" y="316" text-anchor="middle" font-size="11" fill="#333">Manages and enriches both. Also standalone.</text>
  <text x="400" y="340" text-anchor="middle" font-size="10" fill="#666">neocortex (NEW)</text>
  <text x="400" y="358" text-anchor="middle" font-size="10" font-style="italic" fill="#888">"this goal is blocked, frustrating, and shares sub-goals with that one"</text>

  <!-- Arrows -->
  <path d="M200,170 Q250,210 310,230" stroke="#666" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
  <path d="M600,170 Q550,210 490,230" stroke="#666" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
  <text x="230" y="200" font-size="10" fill="#666">propose</text>
  <text x="550" y="200" font-size="10" fill="#666">outcomes</text>
</svg>

**LLM goals are prose.** An agent's drive system generates "explore the library" — natural language, interpreted by an LLM, recursively decomposed until sub-steps bind to concrete capabilities. This is what blocks does today through `GoalProposalOrchestrator` with its four drive-to-goal mappers and LLM formation strategy.

**Case goals are predicates.** `.decision == "approved"` evaluates mechanically against case state. When it fires, the case transitions. The original engine research (ADR-0001) nailed this: "A goal is a predicate over state, not a checklist of tasks that ran." Cases *are* goal pursuit — you want something, you run a case, it completes when the predicate is satisfied.

**Cognitive goals are knowledge.** This is the new layer. A cognitive goal lives in the knowledge graph (MindMap) as a node with affect (how does pursuing this feel?), dependencies (what blocks it? what does it enable?), confidence, temporal horizon, and lifecycle state. The cognitive layer *manages and enriches* goals from both other dimensions — when a drive proposes a goal, the cognitive layer tracks it; when a case completes, the cognitive layer updates goal status and models the affective response.

The three dimensions have genuinely different evaluation mechanisms. LLM goals are interpreted by language models. Case goals are evaluated by predicate engines. Cognitive goals are managed by graph reasoning with affect modulation. Trying to unify them into a single type would conflate three concerns that serve different purposes at different timescales.

## The brain analogy that actually holds

While working through the dependency relationships between our repos, a structural analogy emerged that I think is more than metaphorical.

<svg viewBox="0 0 800 350" xmlns="http://www.w3.org/2000/svg" style="max-width:100%; font-family: system-ui, sans-serif;">
  <!-- Brain outline -->
  <ellipse cx="400" cy="175" rx="350" ry="160" fill="none" stroke="#ccc" stroke-width="1" stroke-dasharray="4,4"/>

  <!-- Neocortex (cortex) -->
  <rect x="180" y="40" width="440" height="100" rx="12" fill="#f3e8fd" stroke="#9334e6" stroke-width="2"/>
  <text x="400" y="68" text-anchor="middle" font-size="14" font-weight="bold" fill="#7627bb">Neocortex = Cerebral Cortex</text>
  <text x="400" y="88" text-anchor="middle" font-size="11" fill="#333">Memory. Knowledge graph. Affect. Goals. Beliefs.</text>
  <text x="400" y="108" text-anchor="middle" font-size="11" fill="#333">Stores everything. Processes nothing behaviorally.</text>
  <text x="400" y="128" text-anchor="middle" font-size="10" fill="#666">The brain's memory substrate</text>

  <!-- Blocks (limbic/motivational) -->
  <rect x="180" y="160" width="280" height="100" rx="12" fill="#e6f4ea" stroke="#34a853" stroke-width="2"/>
  <text x="320" y="188" text-anchor="middle" font-size="14" font-weight="bold" fill="#1e8e3e">Blocks = Motivational Circuit</text>
  <text x="320" y="208" text-anchor="middle" font-size="11" fill="#333">Drives. Goal proposal. Narrative.</text>
  <text x="320" y="228" text-anchor="middle" font-size="11" fill="#333">Reads state → evaluates → decides.</text>
  <text x="320" y="248" text-anchor="middle" font-size="10" fill="#666">Hypothalamus + basal ganglia</text>

  <!-- Engine (motor) -->
  <rect x="480" y="160" width="200" height="100" rx="12" fill="#fef3e0" stroke="#f9ab00" stroke-width="2"/>
  <text x="580" y="188" text-anchor="middle" font-size="14" font-weight="bold" fill="#e37400">Engine = Motor Cortex</text>
  <text x="580" y="208" text-anchor="middle" font-size="11" fill="#333">Plan dispatch.</text>
  <text x="580" y="228" text-anchor="middle" font-size="11" fill="#333">Case execution.</text>
  <text x="580" y="248" text-anchor="middle" font-size="10" fill="#666">Action selection + execution</text>

  <!-- RAS -->
  <rect x="50" y="200" width="110" height="60" rx="8" fill="#fce8e6" stroke="#ea4335" stroke-width="2"/>
  <text x="105" y="225" text-anchor="middle" font-size="12" font-weight="bold" fill="#c5221f">RAS</text>
  <text x="105" y="245" text-anchor="middle" font-size="10" fill="#666">Sensory gate</text>

  <!-- Arrows -->
  <path d="M320,160 L320,140" stroke="#666" stroke-width="1.5" marker-end="url(#arr)"/>
  <path d="M400,140 L400,160" stroke="#666" stroke-width="1.5" marker-end="url(#arr)"/>
  <text x="340" y="152" font-size="9" fill="#666">reads</text>
  <text x="420" y="152" font-size="9" fill="#666">writes</text>

  <text x="400" y="330" text-anchor="middle" font-size="11" fill="#999">Neocortex stores. Blocks processes. Engine executes. RAS filters.</text>
</svg>

**Neocortex is the cerebral cortex** — all persistent cognitive state. Memory, knowledge graph, affect trajectories, goal dependencies, beliefs. It stores everything but makes no behavioral decisions.

**Blocks is the motivational circuit** — hypothalamus (drives), basal ganglia (action selection). It reads cognitive state from neocortex, evaluates drives, composes motivational signals, proposes goals, renders prompts. Critically: *it stores nothing*. It's a pure evaluate→decide loop. All persistent state lives in neocortex.

**Engine is the motor cortex** — plan dispatch, case execution, action selection. When blocks decides to pursue a goal, engine decomposes it into executable steps and dispatches them.

**RAS is the sensory gate** — filtering what reaches cognition.

The key constraint: neocortex defines SPIs (service provider interfaces) for cognitive operations that need LLMs — goal decomposition, goal recognition, belief revision. Blocks provides the LLM implementations. Neocortex compiles and runs without blocks; blocks plugs in when present. This maps to how the cortex defines what processing is needed, while the motivational system provides the activation energy.

## Progressive resolution: LOD for knowledge

Here's the idea I'm most excited about.

Graphics rendering solved the "how much detail?" problem decades ago with level-of-detail: render nearby objects at high fidelity, distant objects as low-poly placeholders (Clark, 1976). The same principle applies to goal knowledge.

Not all goals need the same structural detail. A goal's resolution should depend on how close it is to requiring a decision:

<svg viewBox="0 0 800 280" xmlns="http://www.w3.org/2000/svg" style="max-width:100%; font-family: system-ui, sans-serif;">
  <!-- Timeline -->
  <line x1="60" y1="140" x2="740" y2="140" stroke="#ccc" stroke-width="2"/>
  <text x="60" y="165" font-size="10" fill="#999">NOW</text>
  <text x="740" y="165" font-size="10" text-anchor="end" fill="#999">FAR FUTURE</text>

  <!-- High-res goal (near) -->
  <rect x="80" y="30" width="200" height="95" rx="6" fill="#f3e8fd" stroke="#9334e6" stroke-width="2"/>
  <text x="180" y="50" text-anchor="middle" font-size="11" font-weight="bold" fill="#7627bb">Deploy v2.0</text>
  <circle cx="120" cy="75" r="12" fill="#e8f0fe" stroke="#4285f4"/><text x="120" y="79" text-anchor="middle" font-size="8" fill="#333">tests</text>
  <circle cx="160" cy="75" r="12" fill="#e8f0fe" stroke="#4285f4"/><text x="160" y="79" text-anchor="middle" font-size="8" fill="#333">docs</text>
  <circle cx="200" cy="75" r="12" fill="#fce8e6" stroke="#ea4335"/><text x="200" y="79" text-anchor="middle" font-size="8" fill="#333">infra</text>
  <circle cx="240" cy="75" r="12" fill="#e6f4ea" stroke="#34a853"/><text x="240" y="79" text-anchor="middle" font-size="8" fill="#333">review</text>
  <line x1="120" y1="87" x2="160" y2="87" stroke="#666" stroke-width="1"/>
  <line x1="160" y1="87" x2="200" y2="87" stroke="#666" stroke-width="1"/>
  <line x1="200" y1="87" x2="240" y2="87" stroke="#ea4335" stroke-width="1" stroke-dasharray="3,2"/>
  <text x="180" y="115" text-anchor="middle" font-size="9" fill="#9334e6">HIGH resolution</text>

  <!-- Medium-res goal -->
  <rect x="340" y="50" width="160" height="70" rx="6" fill="#f3e8fd" stroke="#9334e6" stroke-width="1.5"/>
  <text x="420" y="72" text-anchor="middle" font-size="11" font-weight="bold" fill="#7627bb">Hire senior eng</text>
  <circle cx="380" cy="95" r="8" fill="#e8f0fe" stroke="#4285f4"/><text x="380" y="98" text-anchor="middle" font-size="7" fill="#333">JD</text>
  <circle cx="420" cy="95" r="8" fill="#e8f0fe" stroke="#4285f4"/><text x="420" y="98" text-anchor="middle" font-size="7" fill="#333">pipe</text>
  <circle cx="460" cy="95" r="8" fill="#e8f0fe" stroke="#4285f4"/><text x="460" y="98" text-anchor="middle" font-size="7" fill="#333">eval</text>
  <text x="420" y="112" text-anchor="middle" font-size="9" fill="#9334e6">MEDIUM</text>

  <!-- Low-res goal (distant) -->
  <rect x="570" y="70" width="140" height="50" rx="6" fill="#f8f0ff" stroke="#9334e6" stroke-width="1"/>
  <text x="640" y="100" text-anchor="middle" font-size="11" fill="#7627bb">Open Tokyo office</text>
  <text x="640" y="112" text-anchor="middle" font-size="9" fill="#9334e6">LOW — single node</text>

  <!-- Arrows down to timeline -->
  <line x1="180" y1="125" x2="180" y2="140" stroke="#9334e6" stroke-width="1.5"/>
  <line x1="420" y1="120" x2="420" y2="140" stroke="#9334e6" stroke-width="1"/>
  <line x1="640" y1="120" x2="640" y2="140" stroke="#9334e6" stroke-width="0.5"/>

  <!-- Labels -->
  <text x="400" y="200" text-anchor="middle" font-size="12" fill="#333">Resolution increases as goals approach decision points</text>
  <text x="400" y="220" text-anchor="middle" font-size="10" fill="#666">Consolidation sleep cycle manages both directions:</text>
  <text x="400" y="238" text-anchor="middle" font-size="10" fill="#1e8e3e">EXPAND approaching goals ←→ PRUNE receding goals</text>
  <text x="400" y="256" text-anchor="middle" font-size="10" fill="#4285f4">MERGE shared sub-goals across parents</text>
</svg>

"Deploy v2.0" is imminent — it gets full decomposition: sub-goals for tests, docs, infrastructure, review, with dependency edges between them. "Hire a senior engineer" is a few months out — rough decomposition, enough to estimate scope. "Open Tokyo office" is aspirational — a single node with a prose description. No sub-goals. No point.

The resolution is managed by the **consolidation sleep cycle** — the existing background timer that runs maintenance phases when the system is idle. During "sleep," the GoalResolutionPhase:

- **Expands** goals that are approaching (time proximity, rising urgency) — invokes an LLM-based cognitive decomposition SPI to generate sub-goals
- **Prunes** goals that have receded — collapses detailed sub-graphs back to single nodes when the detail hasn't been accessed
- **Merges** shared sub-goals across parents — two goals like "understand customer pain points" and "assess user frustration areas" are semantically equivalent despite lexical distance. Embedding similarity catches what name matching can't
- **Revises** dependency state — if a blocker is resolved, the blocked goal transitions back to active
- **Decays** dormant goals — reducing priority and suggesting abandonment when affect declines

This mirrors what human sleep actually does — prune irrelevant detail, strengthen relevant connections, surface relationships that weren't obvious during waking cognition (Walker, 2017). We already had the consolidation scheduler. We already had the idle detection. The goal resolution phase slots into the existing infrastructure at priority 35, between merge detection (20) and curiosity signals (40).

## Cognitive vs execution decomposition

A critical distinction: what the cognitive system produces is *thoughts*, not *tasks*.

When neocortex decomposes a goal, it asks: "what does achieving this *involve*?" The output is prose sub-goal nodes in the knowledge graph — "understand current pain points," "reduce response time," "build trust through consistency." No agent assignment. No output contracts. No contingency plans.

When engine decomposes a goal for execution, it asks: "how do I *execute* this?" The output is a DagPlan with agent-assigned task nodes, capability bindings, judgment gates, and contingency plans. This is execution planning — finer-grained, agent-specific, disposable after the case completes.

| | Cognitive (neocortex) | Execution (engine) |
|---|---|---|
| Question | "What does this involve?" | "How do I execute this?" |
| When | Early — to understand structure | Late — when submitted for execution |
| Output | MindMap nodes (prose + affect) | DagPlan (agent tasks + contracts) |
| Persistence | Persistent, variable resolution | Per-case, discarded after |

Two decompositions. Different questions. Different timescales. The cognitive structure informs goal *selection* — "which of these competing goals should I pursue?" — while the execution structure informs goal *dispatch* — "which agent does what step?"

This separation is grounded in the BDI architecture (Rao & Georgeff, 1995): **desires** (what the agent wants) are distinct from **intentions** (what the agent is committed to doing about it). Soar (Laird, 2012) takes it further — subgoaling *is* cognition. You don't decompose goals preemptively; you decompose when you hit a decision point that requires understanding structure. ACT-R (Anderson, 2007) adds that the current goal biases retrieval — what you're trying to achieve shapes what memories you can access.

## Goals have feelings

Appraisal theory (Scherer, 2001) models goals as reference points for emotional evaluation. How you feel about a situation depends on its relationship to your goals. We implement this directly.

Each cognitive goal node carries PAD emotional dimensions (pleasure, arousal, dominance). A `GoalAffectPhase` runs during consolidation and computes anticipated affect:

- **High urgency + approaching deadline** → increased arousal (stress, energy)
- **Blocked + important** → frustration (negative pleasure, high arousal)
- **Recently completed** → satisfaction (positive pleasure shift)
- **Dormant + declining interest** → reduced arousal, fading priority

These affect values feed into the existing `AffectTrajectoryAnalyzer` — the same pipeline that tracks mood, emotion, and personality across the agent's lifetime. Goal-related affect becomes one more signal in the agent's emotional landscape.

La VIDA (Addison, 2025) shows that goal-self concordance — how well a goal aligns with the agent's personality — is an optimisation criterion for goal selection. Our `CognitiveDefaults` already derive personality weights from disposition axes. An agent with high curiosity naturally gravitates toward exploration goals. An agent with high affiliation prioritises relationship-building goals. The priority computation weights urgency, feasibility, affect, and structural importance — with personality determining the relative weighting.

## The interface is narrow

One concern I had going in: would the cognitive layer create tight coupling between neocortex, blocks, and engine?

The answer is no. The interface is deliberately narrow:

```
Neocortex → Engine:  GoalFormationService.propose(prose + priority)
Engine → Neocortex:  ExperienceEvent (case outcomes)
```

That's it. Neocortex submits goals for execution through the existing formation SPI — the same one blocks already uses. Engine outcomes flow back as experience events — the same pipeline that already feeds memory and consolidation. No shared graph types. No shared goal records. No new coupling.

The cognitive goal graph lives in MindMap. Engine's execution plans live in DagPlan. The two systems communicate through goal submission (prose description + priority) and outcome feedback (experience events). Each system can evolve independently.

## What's built

The full cognitive goal substrate is committed. Eidos gains `GoalLifecycleState` and `GoalHorizon` on `AgentGoal` (backward compatible — nullable fields). Neocortex mindmap-api gains the `GOAL` subgraph type, `GoalVocabulary` (five edge types with aliases), and three SPIs with NoOp defaults.

The `Goallike` trait interface replaces the placeholder `Intentionlike` with seven property accessors — description, status, horizon, origin, resolution, urgency, feasibility. `Intentionlike` and `Desirelike` are deprecated. In the type hierarchy, "intention" and "desire" become subtypes of "goal" — LLM extraction that produces either label now maps to the unified goal type.

Four consolidation phases slot into the existing sleep cycle: `GoalResolutionPhase` (priority 35) runs the five-step cycle — prune, expand, merge, revise, sync. `GoalAffectPhase` (37) computes anticipated emotion. `GoalPrioritizationPhase` (38) applies the composite priority formula. `GoalRecognitionPhase` (45) scans experience memories for implicit goals the agent hasn't consciously tracked.

Goal-conditioned retrieval works through a `GoalRelevanceModulationFactor` — a BFS walk from each memory's entity node to active goals, with distance-decayed weights. One edge away: full weight. Two edges: 0.7. Three: 0.4. Four or more: invisible. When an agent is pursuing something, memories near that pursuit surface more readily. When nothing is active, retrieval is neutral.

One thing I noticed during implementation: the design anticipated needing an eidos-api dependency in mindmap-intelligence for lifecycle sync. We didn't. The `GoalLifecycleProvider` SPI returns `Map<String, String>` — status strings, not eidos types. The module boundary held cleaner than expected. Mindmap-api stays zero-deps.

The bigger implication crystallised during the design work: all of blocks' social cognition state — mental models, user profiles, narratives, strategy profiles — is cognitive memory that belongs in neocortex. Blocks built it because neocortex didn't have the infrastructure yet. Now it does. The follow-up epic (#378) will migrate that state, making blocks a pure processor — reads state, evaluates, decides, writes back. The brain's motivational circuit: processes memories, doesn't store them.

The platform is developing a nervous system. RAS for sensing. Neocortex for remembering and reasoning. Blocks for wanting and deciding. Engine for doing. Each layer cleanly separated, each doing what brains figured out millions of years ago: separate what you *know* from what you *want* from what you *do*.

---

**References**

- Anderson, J.R. (2007). *How Can the Human Mind Occur in the Physical Universe?* Oxford University Press. — ACT-R: goal as working memory focus that biases retrieval
- Addison, E. (2025). "La VIDA — Motivated Goal Reasoning Agent." *Autonomous Agents and Multi-Agent Systems*. — Goal-self concordance from personality
- Clark, J.H. (1976). "Hierarchical Geometric Models for Visible Surface Algorithms." *Communications of the ACM*. — Original level-of-detail concept
- Laird, J.E. (2012). *The Soar Cognitive Architecture*. MIT Press. — Subgoaling as cognition, impasse-driven decomposition
- Park, J.S. et al. (2023). "Generative Agents: Interactive Simulacra of Human Behavior." — Goal-directed daily planning from reflection
- Rao, A.S. & Georgeff, M.P. (1995). "BDI Agents: From Theory to Practice." *ICMAS*. — Desire/intention separation, deliberation cycle
- Scherer, K.R. (2001). "Appraisal Considered as a Process of Multilevel Sequential Checking." *Appraisal Processes in Emotion*. — Goals as reference points for emotional evaluation
- Walker, M.P. (2017). *Why We Sleep*. Scribner. — Sleep consolidation: pruning, strengthening, discovery

---
title: "When your agent forgets what it wants"
date: 2026-09-23
author: mdp
tags: [architecture, goals, cognitive-architecture, agents, knowledge-graph, affect, retrieval]
entry_type: article
subtype: diary
projects: [casehubio/neocortex]
---

# When your agent forgets what it wants

Most agent frameworks treat goals the same way they treat prompts — as strings that exist for one request and vanish. The LLM receives "help the user book a flight," generates some actions, and when the actions stop, the goal is gone. No memory of it. No record of what blocked it. No sense of whether pursuing it felt productive or frustrating. No way to notice that two different goals both need the same sub-task.

<div>
<svg viewBox="0 0 600 160" xmlns="http://www.w3.org/2000/svg" style="max-width:100%; font-family: system-ui, sans-serif;">
  <rect x="120" y="30" width="360" height="60" rx="30" fill="#f0f0f0" stroke="#ccc" stroke-width="1.5" stroke-dasharray="6,3"/>
  <text x="300" y="65" text-anchor="middle" font-size="14" fill="#666">"Help the user book a flight"</text>
  <text x="300" y="120" text-anchor="middle" font-size="12" fill="#999">No edges. No state. No history.</text>
  <text x="300" y="140" text-anchor="middle" font-size="11" fill="#bbb">The goal exists for one request, then it's gone.</text>
</svg>
</div>

This is like building a person who can only think about one thing at a time and forgets it the moment they look away.

What if goals were persistent? What if they had structure — dependencies, sub-goals, temporal horizons? What if pursuing a goal *felt like something* to the agent — urgency as a deadline approaches, frustration when something blocks progress, satisfaction when it's done? What if the agent's memory retrieval was biased by what it's currently trying to achieve?

Here's what happens when you build that. Four scenarios, four capabilities.

## The research agent: goals at different resolutions

A PhD student's research agent tracks two goals. "Understand transformers" is aspirational — years away, no deadline, no decomposition needed. "Submit NeurIPS paper" is due in three weeks.

<div>
<svg viewBox="0 0 800 300" xmlns="http://www.w3.org/2000/svg" style="max-width:100%; font-family: system-ui, sans-serif;">
  <!-- Low resolution (distant) -->
  <text x="200" y="25" text-anchor="middle" font-size="13" font-weight="bold" fill="#7627bb">Distant — low resolution</text>
  <rect x="100" y="40" width="200" height="50" rx="8" fill="#f8f0ff" stroke="#9334e6" stroke-width="1.5"/>
  <text x="200" y="70" text-anchor="middle" font-size="12" fill="#333">Understand transformers</text>
  <text x="200" y="110" text-anchor="middle" font-size="11" fill="#999">Single node. No sub-goals.</text>
  <text x="200" y="130" text-anchor="middle" font-size="11" fill="#999">Detail can wait.</text>

  <!-- High resolution (approaching) -->
  <text x="600" y="25" text-anchor="middle" font-size="13" font-weight="bold" fill="#1e8e3e">Approaching — high resolution</text>
  <rect x="500" y="40" width="200" height="50" rx="8" fill="#e6f4ea" stroke="#34a853" stroke-width="2"/>
  <text x="600" y="60" text-anchor="middle" font-size="12" font-weight="bold" fill="#333">Submit NeurIPS paper</text>
  <text x="600" y="78" text-anchor="middle" font-size="10" fill="#666">urgency: 0.9 · deadline: 3 weeks</text>

  <!-- Sub-goals -->
  <rect x="460" y="120" width="120" height="35" rx="6" fill="#e8f0fe" stroke="#4285f4" stroke-width="1"/>
  <text x="520" y="142" text-anchor="middle" font-size="10" fill="#333">Literature review</text>

  <rect x="600" y="120" width="120" height="35" rx="6" fill="#e8f0fe" stroke="#4285f4" stroke-width="1"/>
  <text x="660" y="142" text-anchor="middle" font-size="10" fill="#333">Run experiments</text>

  <rect x="530" y="175" width="120" height="35" rx="6" fill="#e8f0fe" stroke="#4285f4" stroke-width="1"/>
  <text x="590" y="197" text-anchor="middle" font-size="10" fill="#333">Write draft</text>

  <!-- Edges -->
  <line x1="560" y1="90" x2="520" y2="120" stroke="#4285f4" stroke-width="1.5"/>
  <line x1="640" y1="90" x2="660" y2="120" stroke="#4285f4" stroke-width="1.5"/>
  <line x1="600" y1="90" x2="590" y2="175" stroke="#4285f4" stroke-width="1.5"/>
  <line x1="520" y1="155" x2="590" y2="175" stroke="#999" stroke-width="1" stroke-dasharray="4,3"/>
  <line x1="660" y1="155" x2="590" y2="175" stroke="#999" stroke-width="1" stroke-dasharray="4,3"/>

  <!-- Labels -->
  <text x="590" y="240" text-anchor="middle" font-size="10" fill="#1e8e3e">decomposes-into</text>
  <text x="590" y="258" text-anchor="middle" font-size="10" fill="#999">requires (dashed)</text>

  <!-- Arrow between -->
  <path d="M310,65 L490,65" stroke="#ccc" stroke-width="1" marker-end="url(#arr-grey)" stroke-dasharray="6,3"/>
  <text x="400" y="58" text-anchor="middle" font-size="10" fill="#999">urgency increases →</text>
  <defs><marker id="arr-grey" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#ccc"/></marker></defs>
</svg>
</div>

This is **progressive resolution** — borrowed from level-of-detail rendering in computer graphics (Clark, 1976). Nearby objects get high-fidelity polygons; distant objects get low-poly placeholders. The same principle applies to goal knowledge.

A background consolidation phase manages both directions. As the paper deadline approaches and urgency rises, the system invokes a cognitive decomposition SPI to break the goal into sub-tasks — literature review, experiments, writing — linked by `decomposes-into` edges. When a distant goal's sub-tasks haven't been accessed, the system prunes them back to a single node. Detail is re-derived when needed, not maintained permanently.

```java
public interface Goallike {
    Optional<String> description();
    Optional<String> status();
    Optional<String> horizon();    // immediate / short / medium / long / aspirational
    Optional<String> origin();     // drive / conversation / reflection / experience
    Optional<String> resolution(); // low / medium / high
    Optional<String> urgency();    // 0.0–1.0
    Optional<String> feasibility();
}
```

Seven properties. That's what separates a structured goal from a string.

## The product manager: dependencies change everything

A product team agent tracks feature goals with dependency edges. "Ship v2.0" is blocked by "hire senior engineer." "Improve onboarding" enables "reduce churn." "Build payment integration" requires "PCI compliance review."

<div>
<svg viewBox="0 0 800 320" xmlns="http://www.w3.org/2000/svg" style="max-width:100%; font-family: system-ui, sans-serif;">
  <defs>
    <marker id="arr-red" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#ea4335"/></marker>
    <marker id="arr-green" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#34a853"/></marker>
    <marker id="arr-blue" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#4285f4"/></marker>
  </defs>

  <!-- Goals -->
  <rect x="40" y="30" width="180" height="50" rx="8" fill="#fce8e6" stroke="#ea4335" stroke-width="2"/>
  <text x="130" y="52" text-anchor="middle" font-size="12" font-weight="bold" fill="#c5221f">Ship v2.0</text>
  <text x="130" y="70" text-anchor="middle" font-size="10" fill="#666">status: blocked</text>

  <rect x="300" y="30" width="180" height="50" rx="8" fill="#e6f4ea" stroke="#34a853" stroke-width="1.5"/>
  <text x="390" y="52" text-anchor="middle" font-size="12" font-weight="bold" fill="#1e8e3e">Hire senior eng</text>
  <text x="390" y="70" text-anchor="middle" font-size="10" fill="#666">status: active</text>

  <rect x="40" y="140" width="180" height="50" rx="8" fill="#e6f4ea" stroke="#34a853" stroke-width="1.5"/>
  <text x="130" y="162" text-anchor="middle" font-size="12" font-weight="bold" fill="#1e8e3e">Improve onboarding</text>
  <text x="130" y="178" text-anchor="middle" font-size="10" fill="#666">status: active</text>

  <rect x="300" y="140" width="180" height="50" rx="8" fill="#e6f4ea" stroke="#34a853" stroke-width="1.5"/>
  <text x="390" y="162" text-anchor="middle" font-size="12" font-weight="bold" fill="#1e8e3e">Reduce churn</text>
  <text x="390" y="178" text-anchor="middle" font-size="10" fill="#666">status: active</text>

  <rect x="560" y="30" width="180" height="50" rx="8" fill="#e6f4ea" stroke="#34a853" stroke-width="1.5"/>
  <text x="650" y="52" text-anchor="middle" font-size="12" font-weight="bold" fill="#1e8e3e">Payment integration</text>
  <text x="650" y="70" text-anchor="middle" font-size="10" fill="#666">status: active</text>

  <rect x="560" y="140" width="180" height="50" rx="8" fill="#e8f0fe" stroke="#4285f4" stroke-width="1.5"/>
  <text x="650" y="162" text-anchor="middle" font-size="12" font-weight="bold" fill="#4285f4">PCI compliance</text>
  <text x="650" y="178" text-anchor="middle" font-size="10" fill="#666">status: active</text>

  <!-- Edges -->
  <line x1="300" y1="55" x2="225" y2="55" stroke="#ea4335" stroke-width="2" marker-end="url(#arr-red)"/>
  <text x="262" y="48" text-anchor="middle" font-size="9" fill="#ea4335">blocks</text>

  <line x1="220" y1="165" x2="295" y2="165" stroke="#34a853" stroke-width="2" marker-end="url(#arr-green)"/>
  <text x="258" y="158" text-anchor="middle" font-size="9" fill="#34a853">enables</text>

  <line x1="650" y1="90" x2="650" y2="135" stroke="#4285f4" stroke-width="2" marker-end="url(#arr-blue)"/>
  <text x="680" y="118" font-size="9" fill="#4285f4">requires</text>

  <!-- Legend -->
  <line x1="100" y1="250" x2="140" y2="250" stroke="#ea4335" stroke-width="2"/>
  <text x="150" y="254" font-size="10" fill="#666">blocks — must resolve first</text>
  <line x1="100" y1="272" x2="140" y2="272" stroke="#34a853" stroke-width="2"/>
  <text x="150" y="276" font-size="10" fill="#666">enables — makes possible</text>
  <line x1="100" y1="294" x2="140" y2="294" stroke="#4285f4" stroke-width="2"/>
  <text x="150" y="298" font-size="10" fill="#666">requires — prerequisite</text>
</svg>
</div>

The five edge types (`enables`, `blocks`, `requires`, `contributes-to`, `decomposes-into`) encode different dependency semantics. `blocks` and `requires` form a DAG constraint — circular dependencies are rejected on creation. `enables` and `contributes-to` allow cycles because mutual enablement is semantically valid.

When the hiring goal completes, the Revise step of the consolidation cycle detects the resolved blocker. "Ship v2.0" transitions from `blocked` to `active`. Priority recomputes — it's now the highest-urgency actionable goal. The agent's attention shifts without anyone explicitly telling it to.

## The personal assistant: goals have feelings

A personal assistant agent notices something: the user keeps asking about cooking. Recipes, meal prep, kitchen equipment. Nobody said "I want to learn to cook" — but the pattern is there.

The GoalRecognitionPhase scans recent experience memories for goal-like content. When the recognizer detects an implicit goal above its confidence threshold, it creates a goal node in the knowledge graph — origin tagged as `experience`, horizon as `medium-term`.

Once tracked, the goal accumulates affect.

<div>
<svg viewBox="0 0 800 260" xmlns="http://www.w3.org/2000/svg" style="max-width:100%; font-family: system-ui, sans-serif;">
  <!-- Axes -->
  <line x1="80" y1="200" x2="720" y2="200" stroke="#ccc" stroke-width="1"/>
  <line x1="80" y1="30" x2="80" y2="200" stroke="#ccc" stroke-width="1"/>
  <text x="40" y="120" text-anchor="middle" font-size="10" fill="#999" transform="rotate(-90,40,120)">intensity</text>
  <text x="400" y="230" text-anchor="middle" font-size="10" fill="#999">time →</text>

  <!-- Pleasure line (green) -->
  <polyline points="100,140 200,130 280,180 350,190 420,180 500,100 580,80 650,75 700,80" fill="none" stroke="#34a853" stroke-width="2.5"/>
  <text x="720" y="83" font-size="10" fill="#34a853">pleasure</text>

  <!-- Arousal line (orange) -->
  <polyline points="100,160 200,150 280,90 350,70 420,100 500,130 580,150 650,155 700,160" fill="none" stroke="#f9ab00" stroke-width="2.5"/>
  <text x="720" y="163" font-size="10" fill="#f9ab00">arousal</text>

  <!-- Dominance line (blue) -->
  <polyline points="100,150 200,145 280,170 350,175 420,160 500,120 580,110 650,105 700,108" fill="none" stroke="#4285f4" stroke-width="2"/>
  <text x="720" y="111" font-size="10" fill="#4285f4">dominance</text>

  <!-- Event markers -->
  <line x1="280" y1="35" x2="280" y2="200" stroke="#ea4335" stroke-width="1" stroke-dasharray="3,3"/>
  <text x="280" y="28" text-anchor="middle" font-size="9" fill="#ea4335">grocery delivery late</text>
  <text x="280" y="245" text-anchor="middle" font-size="9" fill="#ea4335">blocked + urgent</text>

  <line x1="500" y1="35" x2="500" y2="200" stroke="#34a853" stroke-width="1" stroke-dasharray="3,3"/>
  <text x="500" y="28" text-anchor="middle" font-size="9" fill="#34a853">first dish succeeds</text>
  <text x="500" y="245" text-anchor="middle" font-size="9" fill="#34a853">completed sub-goal</text>
</svg>
</div>

Each goal node carries PAD emotional dimensions — pleasure, arousal, dominance. The GoalAffectPhase computes anticipated affect from the goal's current state:

- **High urgency, approaching deadline** → increased arousal. The agent's attention heightens.
- **Blocked and important** → frustration. Negative pleasure, high arousal. The agent feels stuck.
- **Recently completed** → satisfaction. Positive pleasure shift. The agent feels progress.
- **Dormant, declining interest** → reduced arousal. The goal fades from active attention.

This isn't anthropomorphic decoration. Appraisal theory (Scherer, 2001) models emotions as evaluations relative to goals. How you feel about a situation depends on its relationship to what you're trying to achieve. The affect values feed into retrieval modulation, priority computation, and the curiosity system — they're functional signals, not narrative flourish.

## The game NPC: shared sub-goals and biased memory

A game character pursues two quests simultaneously: "Rescue the princess" and "Find the ancient artifact." Both require finding the blacksmith — one for weapons, one for a map.

<div>
<svg viewBox="0 0 800 320" xmlns="http://www.w3.org/2000/svg" style="max-width:100%; font-family: system-ui, sans-serif;">
  <defs><marker id="arr-purple" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#9334e6"/></marker></defs>

  <!-- Parent goals -->
  <rect x="80" y="30" width="220" height="50" rx="8" fill="#fce8e6" stroke="#ea4335" stroke-width="2"/>
  <text x="190" y="60" text-anchor="middle" font-size="12" font-weight="bold" fill="#c5221f">Rescue the princess</text>

  <rect x="500" y="30" width="220" height="50" rx="8" fill="#e8f0fe" stroke="#4285f4" stroke-width="2"/>
  <text x="610" y="60" text-anchor="middle" font-size="12" font-weight="bold" fill="#1a73e8">Find the artifact</text>

  <!-- Merged sub-goal -->
  <rect x="280" y="130" width="240" height="50" rx="8" fill="#f3e8fd" stroke="#9334e6" stroke-width="2.5"/>
  <text x="400" y="152" text-anchor="middle" font-size="12" font-weight="bold" fill="#7627bb">Find the blacksmith</text>
  <text x="400" y="170" text-anchor="middle" font-size="10" fill="#666">merged — shared sub-goal</text>

  <!-- Edges to merged node -->
  <line x1="190" y1="80" x2="340" y2="130" stroke="#9334e6" stroke-width="1.5" marker-end="url(#arr-purple)"/>
  <line x1="610" y1="80" x2="460" y2="130" stroke="#9334e6" stroke-width="1.5" marker-end="url(#arr-purple)"/>
  <text x="240" y="110" font-size="9" fill="#9334e6">contributes-to</text>
  <text x="540" y="110" font-size="9" fill="#9334e6">contributes-to</text>

  <!-- Retrieval weights -->
  <rect x="120" y="220" width="560" height="70" rx="8" fill="#f8f8f8" stroke="#ddd" stroke-width="1"/>
  <text x="400" y="242" text-anchor="middle" font-size="11" font-weight="bold" fill="#333">Retrieval weight by distance from active goal</text>
  <text x="180" y="268" text-anchor="middle" font-size="22" fill="#1e8e3e">1.0</text>
  <text x="180" y="282" font-size="9" text-anchor="middle" fill="#666">1 edge</text>
  <text x="300" y="268" text-anchor="middle" font-size="22" fill="#f9ab00">0.7</text>
  <text x="300" y="282" font-size="9" text-anchor="middle" fill="#666">2 edges</text>
  <text x="420" y="268" text-anchor="middle" font-size="22" fill="#ea4335">0.4</text>
  <text x="420" y="282" font-size="9" text-anchor="middle" fill="#666">3 edges</text>
  <text x="540" y="268" text-anchor="middle" font-size="22" fill="#ccc">0.0</text>
  <text x="540" y="282" font-size="9" text-anchor="middle" fill="#666">4+ edges</text>
</svg>
</div>

The Merge step detects semantically similar sub-goals across different parents. "Find the blacksmith shop" and "find the blacksmith store" — Jaro-Winkler similarity above 0.85 — get merged into a single node with `contributes-to` edges to both parents. The task is done once, benefiting both quests.

Meanwhile, the `GoalRelevanceModulationFactor` biases memory retrieval by graph proximity to active goals. When the NPC is actively pursuing the rescue quest, memories one edge away from that goal (the blacksmith's location, weapon types, castle layout) surface at full weight. Memories two edges away get 0.7. Three edges: 0.4. Four or more: invisible. The agent's recall is shaped by what it's currently trying to do — exactly how human memory works under goal-directed attention (Anderson, 2007).

## The consolidation sleep cycle

These four capabilities — expand, prune, merge, revise — don't run in real time. They run during "sleep."

<div>
<svg viewBox="0 0 700 350" xmlns="http://www.w3.org/2000/svg" style="max-width:100%; font-family: system-ui, sans-serif;">
  <!-- Central circle -->
  <circle cx="350" cy="175" r="60" fill="#f8f0ff" stroke="#9334e6" stroke-width="1.5"/>
  <text x="350" y="170" text-anchor="middle" font-size="13" font-weight="bold" fill="#7627bb">Goal</text>
  <text x="350" y="188" text-anchor="middle" font-size="13" font-weight="bold" fill="#7627bb">Resolution</text>

  <!-- Phase nodes -->
  <rect x="290" y="10" width="120" height="40" rx="20" fill="#fce8e6" stroke="#ea4335" stroke-width="1.5"/>
  <text x="350" y="35" text-anchor="middle" font-size="11" font-weight="bold" fill="#c5221f">Prune</text>

  <rect x="520" y="70" width="120" height="40" rx="20" fill="#e6f4ea" stroke="#34a853" stroke-width="1.5"/>
  <text x="580" y="95" text-anchor="middle" font-size="11" font-weight="bold" fill="#1e8e3e">Expand</text>

  <rect x="520" y="240" width="120" height="40" rx="20" fill="#f3e8fd" stroke="#9334e6" stroke-width="1.5"/>
  <text x="580" y="265" text-anchor="middle" font-size="11" font-weight="bold" fill="#7627bb">Merge</text>

  <rect x="290" y="300" width="120" height="40" rx="20" fill="#e8f0fe" stroke="#4285f4" stroke-width="1.5"/>
  <text x="350" y="325" text-anchor="middle" font-size="11" font-weight="bold" fill="#1a73e8">Revise</text>

  <rect x="60" y="155" width="120" height="40" rx="20" fill="#fef3e0" stroke="#f9ab00" stroke-width="1.5"/>
  <text x="120" y="180" text-anchor="middle" font-size="11" font-weight="bold" fill="#e37400">Sync</text>

  <!-- Arrows between phases (clockwise) -->
  <path d="M405,30 Q480,30 530,78" stroke="#666" stroke-width="1.5" fill="none" marker-end="url(#arr-cycle)"/>
  <path d="M580,115 Q580,180 580,235" stroke="#666" stroke-width="1.5" fill="none" marker-end="url(#arr-cycle)"/>
  <path d="M520,265 Q450,300 410,320" stroke="#666" stroke-width="1.5" fill="none" marker-end="url(#arr-cycle)"/>
  <path d="M290,320 Q200,300 170,200" stroke="#666" stroke-width="1.5" fill="none" marker-end="url(#arr-cycle)"/>
  <path d="M120,155 Q120,80 285,30" stroke="#666" stroke-width="1.5" fill="none" marker-end="url(#arr-cycle)"/>
  <defs><marker id="arr-cycle" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#666"/></marker></defs>

  <!-- Annotations -->
  <text x="480" y="48" font-size="9" fill="#666">→ research agent</text>
  <text x="628" y="180" font-size="9" fill="#666">→ research agent</text>
  <text x="480" y="298" font-size="9" fill="#666">→ game NPC</text>
  <text x="230" y="315" font-size="9" fill="#666">→ product team</text>
  <text x="50" y="130" font-size="9" fill="#666">→ eidos identity</text>
</svg>
</div>

The existing consolidation scheduler — a background timer that runs maintenance phases when the system is idle — gains four new phases at priorities 35-45. Each phase operates on the GOAL subgraph regardless of whether curiosity signals prioritise it. Goal processing is not optional.

The step ordering is load-bearing. Expand runs before Merge because newly created sub-goals are candidates for cross-parent merging. Revise runs before Sync because internal dependency updates should settle before importing external lifecycle state. Sync runs last because it imports authoritative state from the identity layer — subsequent phases use those updated values.

This mirrors what human sleep consolidation actually does — prune irrelevant detail, strengthen relevant connections, surface relationships that weren't obvious during waking cognition (Walker, 2017).

## The priority formula

With affect computed and dependencies mapped, the system ranks competing goals:

```
priority = 0.3 × urgency + 0.2 × feasibility + 0.2 × affective_valence + 0.3 × importance
```

Where `affective_valence = (pleasure + dominance + 2) / 4` maps PAD dimensions to a 0–1 score (neutral PAD yields 0.5), and `importance` counts inbound `contributes-to` and `enables` edges normalised by the maximum across active goals. Goals that many other goals depend on are structurally important, independent of how urgent or pleasant they are.

The priority score is a substrate signal. The agent's orchestration layer decides what to do with it — goal selection, prompt ordering, capacity allocation. The cognitive layer computes; the behavioral layer acts.

## The narrow interface

One concern going in: would a cognitive goal layer create tight coupling between the memory system, the behavioral orchestration, and the execution engine?

<div>
<svg viewBox="0 0 700 140" xmlns="http://www.w3.org/2000/svg" style="max-width:100%; font-family: system-ui, sans-serif;">
  <defs><marker id="arr-narrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6" fill="#666"/></marker></defs>

  <rect x="40" y="30" width="240" height="70" rx="10" fill="#f3e8fd" stroke="#9334e6" stroke-width="2"/>
  <text x="160" y="58" text-anchor="middle" font-size="14" font-weight="bold" fill="#7627bb">Cognitive substrate</text>
  <text x="160" y="78" text-anchor="middle" font-size="11" fill="#666">Memory · Knowledge graph · Goals · Affect</text>

  <rect x="420" y="30" width="240" height="70" rx="10" fill="#fef3e0" stroke="#f9ab00" stroke-width="2"/>
  <text x="540" y="58" text-anchor="middle" font-size="14" font-weight="bold" fill="#e37400">Execution engine</text>
  <text x="540" y="78" text-anchor="middle" font-size="11" fill="#666">Plan dispatch · Case execution</text>

  <line x1="285" y1="52" x2="415" y2="52" stroke="#666" stroke-width="1.5" marker-end="url(#arr-narrow)"/>
  <text x="350" y="46" text-anchor="middle" font-size="9" fill="#666">prose goal + priority</text>

  <line x1="415" y1="78" x2="285" y2="78" stroke="#666" stroke-width="1.5" marker-end="url(#arr-narrow)"/>
  <text x="350" y="98" text-anchor="middle" font-size="9" fill="#666">outcome events</text>
</svg>
</div>

Two channels. Goals flow out as prose descriptions with priority scores. Outcomes flow back as experience events. No shared graph types. No shared goal records. The cognitive goal graph lives in the knowledge store. The execution engine's plans live in their own data structures. Each system evolves independently.

The SPIs for cognitive operations that need LLMs — goal decomposition, goal recognition, lifecycle state queries — are defined by the cognitive layer with no-op defaults. A standalone deployment (no LLM, no orchestration) gets goal storage, recognition, and affect without progressive resolution. The cognitive graph is still valuable without decomposition — manually created goals, recognised goals, and their dependency edges all function. Progressive resolution is an enhancement, not a prerequisite.

## What this opens up

Three capabilities sit just beyond the current implementation, each building on the substrate that's now in place.

**Opportunity cost.** With structured goals and computed priorities, the agent can reason about trade-offs: pursuing A means not pursuing B. The priority scores and feasibility estimates provide the raw material; the orchestration layer surfaces the trade-off.

**Avoidance patterns.** A goal with high importance but high difficulty develops a characteristic affect signature — elevated arousal with declining pleasure. The agent starts avoiding related topics, which suppresses retrieval of relevant memories, which further delays progress. Modelling this feedback loop is the difference between an agent that procrastinates and one that doesn't.

**Emergent goals.** When the Revise step resolves a dependency, new possibilities emerge. Achieving A reveals that B is now possible. The recognition phase could scan the updated dependency graph for newly unblocked opportunities — goals the agent didn't know it could pursue until something else was accomplished.

Goals are not strings. They're knowledge.

---

**References**

- Anderson, J.R. (2007). *How Can the Human Mind Occur in the Physical Universe?* Oxford University Press. — ACT-R: goal-directed retrieval bias
- Clark, J.H. (1976). "Hierarchical Geometric Models for Visible Surface Algorithms." *Communications of the ACM*. — Level-of-detail rendering
- Scherer, K.R. (2001). "Appraisal Considered as a Process of Multilevel Sequential Checking." *Appraisal Processes in Emotion*. — Goals as emotional reference points
- Walker, M.P. (2017). *Why We Sleep.* Scribner. — Sleep consolidation: pruning, strengthening, discovery

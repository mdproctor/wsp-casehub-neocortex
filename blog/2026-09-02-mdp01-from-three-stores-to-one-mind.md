---
layout: post
title: "From Three Stores to One Mind"
date: 2026-09-02
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [cognitive-architecture, identity, personality, mindmap, memory, cbr, yaml, derivation]
series: issue-253-cognitive-rearchitecture
---

# From Three Stores to One Mind

*Continues from [Three Confidences Walk Into a Bar](2026-08-29-mdp01-three-confidences-walk-into-a-bar.md).*

Neocortex started as three independent subsystems: MindMap (knowledge graph), Memory (experience store), and CBR (case-based reasoning). Each had its own confidence model, its own temporal semantics, its own query surface. They shared a Maven parent and nothing else.

The cognitive rearchitecture changed that. Five days, 25 issues, one question: what would it take for an agent's identity to drive how it remembers, feels, reasons, and is curious?

## The Theory

The personality-cognition link is one of differential psychology's most replicated findings. Chamorro-Premuzic & Furnham (2004, *Personality and Intellectual Competence*) established that personality traits predict cognitive style across tasks, not just preference. Openness to Experience correlates with abstract encoding and diversive curiosity — Litman (2005, "Curiosity and the pleasures of learning") distinguishes this from specific curiosity (focused gap-filling), and the correlation with Openness is strong. Conscientiousness maps to what Riding & Rayner (1998, *Cognitive Styles and Learning Strategies*) call the analytical end of the holistic-analytical dimension — stricter thresholds, validation-focused attention, categorical organisation.

The emotional layer draws on two foundations. Mehrabian & Russell (1974, *An Approach to Environmental Psychology*) gave us the PAD model — pleasure, arousal, dominance as the three independent dimensions of emotional state. Lazarus (1991, *Emotion and Adaptation*) established appraisal theory: emotional response to events depends on the individual's assessment of relevance and coping capacity. The same event triggers different affect depending on who encounters it.

For memory, Broadbent (1958, *Perception and Communication*) showed that selective attention determines what enters encoding — personality shapes the attentional filter. Bower (1981, "Mood and Memory") demonstrated mood-congruent retrieval: current emotional state biases which memories surface. And Szpunar et al. (2014) showed that future thinking is goal-directed, not random simulation — prospective memory is shaped by current motivations.

For analogical reasoning, Gentner & Smith (2012) showed that conservative reasoners prefer literal similarity while creative reasoners exploit structural alignment across distant domains. This maps directly to CBR retrieval parameters — how far afield should the system look for relevant cases?

The gap in agent systems is that identity and cognition are typically configured independently. An eidos descriptor says the agent is analytical and risk-averse. The memory system uses hardcoded retrieval weights. Nothing connects the two.

The rearchitecture closes that gap. Identity drives cognition through a derivation chain: disposition → personality weights → mood baseline → curiosity focus → retrieval modulation → graph structure preference. One YAML file. One derivation function. Every cognitive parameter traces back to who the agent is.

## What Was Built — Five Layers

### Layer 1: Unified Confidence

Three subsystems used "confidence" to mean different things. MindMap: origin-tracked with exponential decay. Memory: a raw retrieval weight called "importance." CBR: EMA-adjusted from outcome feedback.

The fix: a single `Confidence(origin, value, decayReference)` record in `cognitive-api`, shared across all three. Every confidence value now carries provenance — STATED, INFERRED, SPECULATED, or UNKNOWN — and a decay anchor. The naming audit renamed `importance` to `confidence` across the memory stack.

### Layer 2: Temporal Architecture

Three new capabilities:

- **TemporalIndex** — cross-store chronological aggregation. Query "what changed in the last hour" across MindMap nodes, memory entries, and CBR cases in one call.
- **PAD emotional dimensions** — pleasure/arousal/dominance on every memory entry and MindMap node. Affect is no longer metadata; it's a first-class query dimension.
- **AffectTrajectoryAnalyzer** — computes slope, volatility, and trend from the affect log. Is this entity's emotional trajectory worsening, improving, or volatile?

### Layer 3: Cognitive Dynamics

The layer where stores become cognition:

- **Prospective events** — `RecurrenceRule` (RFC 5545 RRULE subset) on MindMap nodes. Scheduled events expand into future instances. The graph models what will happen, not just what did.
- **Trajectory-aware curiosity** — `CuriositySignalGenerator` dampens curiosity when affect trajectory is improving (things are going well — less need to explore) and boosts it when worsening or volatile (something's wrong — look harder).
- **TemporalFocus** — ranked attention list combining proximity, recency, and trajectory scoring. The agent's attention is finite; this decides where it goes.
- **CognitiveProfile** — cross-store entity resolution. Given a name or ID, resolve the MindMap node, all edges, memories across six domains, affect trajectory, and NodeRef following into a single `EntityKnowledge` record.

### Layer 4: Retrieval Modulation

- **ModulationFactor** — `@FunctionalInterface` composable scoring multiplier. Recency decay, confidence weighting, mood congruence, domain weighting — each is a factor. Factors compose via multiplication. `RetrievalModulator` applies them and sorts by composite score.
- **PerspectivalMerge** — the same MindMap node can carry different affect overlays per agent. Alice sees "Project Alpha" with pleasure=0.7 (opportunity). Bob sees it with pleasure=-0.3 (threat). Same node, different emotional colouring, merged at query time.

### Layer 5: Configuration Architecture

The declarative layer that ties everything together:

- **CognitiveDefaults** — a single YAML file per agent declares personality weights, mood baseline, curiosity config, temporal focus, vocabulary, and service bindings.
- **Declarative rule DSL** — 11 structural predicates (`hasProperty`, `propertyEquals`, `anyOf`, `allOf`, `not`, ...) for trait rules, plus two-level derived edge rules (direct flip + graph traversal). YAML rules compile to the same Java interfaces as programmatic rules. They coexist.
- **DeclarativeRuleRegistry** — loads global rules from `rules/*.yaml`, merges with per-agent overrides from cognitive profiles. Name collision = local wins.
- **CognitiveDerivationEngine** — the pure function: `DescriptorView → CognitiveDefaults`. Maps Jungian disposition profile to `PersonalityWeights` (weighted average across 8 cognitive functions) and disposition axes to `MoodBaseline` (riskAppetite→pleasure, socialOrient→arousal, autonomy→dominance). Zero compile-time dependency on eidos.

## How They Compose

A single YAML file declares identity and cognition together:

```yaml
descriptor:
  disposition:
    socialOrient: independent
    riskAppetite: calculated
    autonomy: high
  dispositionProfile:
    - { term: ni, weight: 0.35 }
    - { term: te, weight: 0.30 }

personality:       # derived from descriptor, explicit overrides win
  reflection: 1.5

traitRules:        # per-agent declarative rules
  - trait: StrategicThinker
    when:
      hasEdgeTypes: [analyses, evaluates]

vocabulary:
  edgeTypes:
    - canonical: analyses
      aliases: [examines, studies]
```

The loader reads this file, runs the derivation engine, merges explicit overrides, registers vocabulary, and produces CDI beans. One file, one agent, full cognitive configuration.

## What's Novel

**Disposition-driven cognition.** I haven't seen another agent framework where personality weights, mood baseline, curiosity thresholds, and retrieval modulation all derive from a single identity descriptor via a research-grounded mapping function. Most systems treat these as independent config knobs.

**Declarative rules that coexist with programmatic rules.** The 11-predicate condition DSL and two-level derived edge rules compile to the same Java interfaces. A platform ships global rules; individual agents override by name. No runtime penalty for the abstraction — a declarative rule evaluates the same sealed-interface pattern match as a hand-written one.

**Cross-store cognitive queries.** `CognitiveProfile` resolves an entity across MindMap, Memory (six domains), CBR, and affect trajectory in one call. `TemporalFocus` ranks attention across all stores. These are the queries a cognitive system actually needs — not per-store lookups with manual joins.

**Perspectival affect.** The same knowledge graph node carrying different emotional colouring per agent, merged at query time via `PerspectivalMerge`. This isn't just configuration — it's a structural claim about how subjective experience relates to shared knowledge.

## Where This Goes

The derivation engine maps two of eight designed connection points. The remaining six follow the same pattern — pure functions from descriptor to config — but each touches a different cognitive subsystem. ✅ = implemented, ◻️ = designed, not yet wired:

| Connection | What it derives | From what |
|---|---|---|
| ✅ Memory weighting | `PersonalityWeights` domain multipliers | Disposition profile (Ni→reflection, Fe→relationship, etc.) |
| ✅ Mood baseline | `MoodBaseline` PAD resting point | Disposition axes (riskAppetite→pleasure, autonomy→dominance) |
| ◻️ Extraction bias | `MindMapExtractor` relationship vs affect sensitivity | Disposition profile (analytical→more edges, empathetic→more affect) |
| ◻️ Curiosity direction | `CuriositySignalGenerator` category weights | Goals + disposition (autonomy→STRUCTURAL, ruleFollowing→QUALITY) |
| ◻️ CBR strategy | `CbrQuery` defaults (minSimilarity, temporalDecay, retrievalMode) | ruleFollowing + riskAppetite (Gentner's analogical reasoning dimension) |
| ◻️ Social cognition | Trust formation rate, conflict interpretation | socialOrient + conflictMode (Bowlby's attachment dimension) |
| ◻️ Prospective focus | Subgraph proximity weights for future-facing attention | Goals + domain (career→PROJECT amplified, family→PERSON amplified) |
| ◻️ Graph structure | Derived edge rule activation, connective vs categorical inference | Disposition profile (holistic Ni/Fe→bridges, systematic Te/Si→categories) |

Beyond the derivation chain, three architectural directions:

- **Agent-scoped rule context.** The `DerivedEdgeDecorator` currently loads all declarative rules for all agents. Per-agent scoping requires an agent context in the MindMapStore layer — the store needs to know who's calling so it fires only that agent's rules. This is the bridge to identity-cognition derivation point 8.
- **Hot-reload.** V1 requires restart for config changes. Quarkus's `@ConfigMapping` with file watching could make cognitive profiles reloadable without restart — change an agent's personality weights and see the effect immediately.
- **Multi-agent perspectival queries.** `PerspectivalMerge` handles one agent's overlay at a time. The next step is comparative queries — "how does Alice's emotional colouring of this entity differ from Bob's?" — which is a social cognition primitive.

The deeper point: cognitive architecture shouldn't be bolted on. It should emerge from identity.

## References

- Bower, G. H. (1981). Mood and Memory. *American Psychologist*, 36(2), 129–148.
- Broadbent, D. E. (1958). *Perception and Communication*. Pergamon Press.
- Chamorro-Premuzic, T., & Furnham, A. (2004). *Personality and Intellectual Competence*. Lawrence Erlbaum Associates.
- Gentner, D., & Smith, L. (2012). Analogical Reasoning. In V. S. Ramachandran (Ed.), *Encyclopedia of Human Behavior* (2nd ed.). Elsevier.
- Lazarus, R. S. (1991). *Emotion and Adaptation*. Oxford University Press.
- Litman, J. A. (2005). Curiosity and the pleasures of learning. *Cognition and Emotion*, 19(6), 793–814.
- Mehrabian, A., & Russell, J. A. (1974). *An Approach to Environmental Psychology*. MIT Press.
- Riding, R., & Rayner, S. (1998). *Cognitive Styles and Learning Strategies*. David Fulton Publishers.
- Szpunar, K. K., Spreng, R. N., & Schacter, D. L. (2014). A taxonomy of prospection. *Frontiers in Human Neuroscience*, 8, 590.

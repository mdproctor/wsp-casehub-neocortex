# Design: Entity-Enriched Drive Descriptions via #721 Annotation Infrastructure

**Issue:** casehubio/neocortex#733
**Branch:** issue-758-pipeline-wiring-and-corpus
**Date:** 2026-11-02

## Problem

#732 established the plumbing: `DriveDescriptionGenerationPhase` (P22) now receives entity knowledge from `CognitiveProfile` alongside relational schemas. But the current `buildRelationalContext` only extracts experience-domain memories and affect trajectory per entity. The gap:

- **Relationship-domain memories** — interaction quality signals (POSITIVE/NEGATIVE/NEUTRAL) that reveal how encounters with this person have gone
- **Reflection-domain memories** — synthesized insights ("you've noticed they avoid conflict")
- **MindMap edges** — typed relationships (beliefs-about, collaborated-with) from EntityKnowledge
- **Theory of Mind** — BDI data: what the agent believes, desires, and intends toward this specific entity

Without these, drive descriptions remain generic ("warmth when someone you protect is near") instead of grounded ("warmth because you believe she still trusts you, though your last encounter was tense").

## Solution

Three changes:

### 1. New `MentalModelLookup` SPI in cognition-api

```java
@FunctionalInterface
public interface MentalModelLookup {
    Optional<MentalModelSnapshot> lookup(String agentId, String subjectId, String tenantId);
}
```

`MentalModelMemory` in the `cognition` module implements this interface. A `@DefaultBean` `NoOpMentalModelLookup` returns `Optional.empty()`.

### 2. New dependency: mindmap-intelligence → cognition-api

No cycle — verified. `cognition-api` depends on `cognitive-index`, `cognitive-api`, `memory-api`, `mindmap-api`, `eidos-api`. None of these depend on `mindmap-intelligence`.

### 3. Expanded `buildRelationalContext` in P22

Currently extracts per entity:
- Experience-domain memories
- Affect trajectory

Expanded to include:
- **Relationship-domain memories** (`new MemoryDomain("relationship")`) — interaction quality
- **Reflection-domain memories** (`new MemoryDomain("reflection")`) — insights about entity
- **MindMap edges** from `EntityKnowledge.edges()` — typed relationships
- **ToM data** from `MentalModelLookup.lookup(agentId, targetId, tenantId)` — beliefs, desires, intentions

### Prompt format

The relational context section expands from:

```
About penelope-pitstop (person):
  Recent memories:
    - memory text
  Emotional trajectory: IMPROVING (pleasure slope: 0.15)
```

To:

```
About penelope-pitstop (person):
  Experiences with them:
    - memory text
  How interactions have gone:
    - positive encounter (confidence: 0.8)
  Insights about them:
    - they avoid conflict when challenged
  Connections:
    - collaborated-with → project-alpha
    - beliefs-about → honesty
  What you think about them:
    Beliefs: they are trustworthy (confidence: 0.9), they are competent (confidence: 0.7)
    Desires: you want them to succeed (confidence: 0.6)
    Intentions: you intend to protect them (confidence: 0.8)
  Emotional trajectory: IMPROVING (pleasure slope: 0.15)
```

Each subsection is omitted when empty. The existing system prompt instruction ("use discovery verbs not analytical verbs") applies — the LLM translates this structured context into somatic prose.

### Token budget

Existing limits (MAX_ENTITIES=5, MEMORY_LIMIT=5 per domain) apply to each new domain. Edges are capped at 10 per entity. BDI items are typically 1-5 per dimension — no additional cap needed.

### Graceful degradation

- `CognitiveProfile` unsatisfied → no entity context at all (existing behavior)
- `MentalModelLookup` unsatisfied → entity context without ToM subsection
- Empty domains/edges/BDI → subsection omitted from prompt

## Testing

1. **MentalModelLookup SPI** — verify NoOp returns empty, verify MentalModelMemory implements the interface
2. **Expanded buildRelationalContext** — test with relationship and reflection memories present, verify they appear in prompt
3. **Edge extraction** — test with edges on EntityKnowledge, verify they appear in prompt
4. **ToM integration** — test with MentalModelLookup returning a MentalModelSnapshot, verify beliefs/desires/intentions appear in prompt
5. **Graceful degradation** — test with unsatisfied MentalModelLookup, verify entity context renders without ToM subsection

## Out of scope

- Entity annotation mention counts (analytical, not useful for somatic description)
- Moving MentalModelMemory to cognition-api (could be done later for architectural cleanliness)
- Entity-aware salience wiring verification (already operational upstream of CognitiveProfile.resolve())

## References

- `2026-11-02-drive-first-folding-design.md` — #732 design (this extends it)
- `DriveDescriptionGenerationPhase.java` — P22 current implementation with buildRelationalContext
- `EntityKnowledge.java:15` — record with memories, edges, trajectory
- `MentalModelSnapshot.java` — BDI value type in cognition-api
- `MentalModelMemory.java` — store class in cognition (implements the new SPI)
- `cognition-api/pom.xml` — dependency verification (no cycle)
- `era5-relational-cognition-research.md` — architecture decision: fold into drives
- GitHub #721 — entity annotation infrastructure
- GitHub #732 — companion issue (plumbing, done)

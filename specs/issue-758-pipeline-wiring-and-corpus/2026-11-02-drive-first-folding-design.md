# Design: Fold EntityKnowledge/SocialComparison/DomainActivation into Drive-First Rendering

**Issue:** casehubio/neocortex#732
**Branch:** issue-758-pipeline-wiring-and-corpus
**Date:** 2026-11-02

## Problem

Three cognitive prompt sections render analytical data as standalone blocks appended after drive descriptions:

- **EntityKnowledgePromptSection** (enabled by default) — structured factual blocks: relationships, memories, affect trajectory per entity
- **SocialComparisonPromptSection** (disabled by default) — pairwise inter-agent PAD distance metrics
- **DomainActivationPromptSection** (disabled by default) — cross-domain DTW correlation statistics

Era 5 research proved these sections degrade Barrett somatic register (3.74→3.13) by giving the LLM ready-made analytical labels that compete with the "feel, don't think" instruction. The architecture decision: relational information folds INTO drives, not alongside.

## Solution

Enrich `DriveDescriptionGenerationPhase` (P22) with entity knowledge, social comparison, and domain activation data at consolidation time. P22's LLM call translates this data into somatic drive descriptions. The three analytical sections stop rendering by default.

## Architecture

### Data flow

```
Consolidation time (P22):
  CognitiveProfile.resolve()     ──┐
  CognitiveProfile.compare()     ──┤  Unified "Relational Context"
  SocialComparison.compare()     ──┤  section in P22 LLM prompt
  DomainActivation.correlate()   ──┘
                                    │
                                    ▼
                         LLM generates somatic
                         drive descriptions with
                         entity grounding, perspective
                         divergence, cross-domain echoes
                                    │
                                    ▼
                         Stored as MindMap nodes
                         (DriveDescriptionGenerated trait)
                                    │
Render time:                        ▼
  CharacterDrivePromptSection reads stored descriptions
  (no analytical text reaches the prompt)
```

### Changes to DriveDescriptionGenerationPhase

**New dependencies** (via CDI `Instance<>` for graceful degradation):

- `Instance<CognitiveProfile>` — entity knowledge resolution
- `Instance<DomainActivation>` — cross-domain correlation

SocialComparison is a static utility — no injection needed.

**New data gathering** (in `run()`, after loading drive and relational-schema nodes):

1. **Entity knowledge:** For each entity referenced by relational-schema nodes, call `CognitiveProfile.resolve()` with `CognitiveProfileQuery.byName(entityName, subgraphId)`. Collect `EntityKnowledge` per entity — memories, edges, affect trajectory. Use `memoryLimit` of 5 to keep token budget bounded.

2. **Social comparison:** If multiple agents are available (via `discoverTenants()` on the store), call `CognitiveProfile.compare()` for key entities, then `SocialComparison.compare()` on the result. Produces `PerspectivalComparison` per entity.

3. **Domain activation:** Call `DomainActivation.correlate()` with subgraph IDs from the agent's COGNITIVE subgraph. Include `contextDomains` for mood and experience correlation. Use a 7-day lookback window.

**Graceful degradation:** If `CognitiveProfile` or `DomainActivation` is not on the classpath (`Instance.isUnsatisfied()`), P22 proceeds with its current inputs — the enrichment is additive, not required.

### LLM prompt enrichment

Add a "Relational Context" section to the user prompt, after the existing "Relationships" section. Format:

```
Relational context for your pulls:

About {entityName} ({entityType}):
  Recent memories:
    - {memory.text} (confidence: {confidence})
  Emotional trajectory: {trajectory.trend} (pleasure {pleasureSlope}, arousal {arousalSlope})

Perspective divergence:
  You and {otherAgent} see {entityName} differently:
    Your pleasure toward them: {value}, theirs: {value}
    Trajectory: {ALIGNED|DIVERGENT}

Cross-domain emotional patterns:
  Your emotional responses in "{subgraphA}" and "{subgraphB}" are {strength} correlated
  (similarity: {value})
```

The existing system prompt instruction — "use discovery verbs not analytical verbs, weave four channels" — applies to this data too. The LLM will translate the structured context into somatic prose. No changes to the system prompt needed.

### Token budget

The relational context section should be bounded:
- Max 5 memories per entity (already parameterizable via `memoryLimit`)
- Max 5 entities (configurable, covers typical social context)
- Social comparison only for entities with 2+ agent perspectives
- Domain activation summary only (signal list, not raw DTW alignment)

Estimated overhead: ~200-400 tokens in the P22 prompt. This is a one-time consolidation cost, not per-tick.

### Config changes

In `CognitionConfig.all()`:
- `entityKnowledgeEnabled` → `false` (was `true`)
- `perspectiveComparisonEnabled` stays `false`
- `domainActivationEnabled` stays `false`

The section classes, participants, and rendering code remain intact for debugging and A/B evaluation. Re-enable via config to compare folded vs unfolded output.

### Skip logic update

P22 currently skips regeneration if all `DriveDescriptionGenerated` nodes exist for an agent. The skip key set must expand to include a hash of the relational context — if entity knowledge changes (new memories, affect trajectory shift), descriptions should regenerate.

Add a `relational-context-hash` property to generated description nodes. On subsequent runs, compare the hash. If it differs, regenerate. If CognitiveProfile is unavailable, hash is empty string (matches any prior run without enrichment).

## Testing

1. **Unit test:** P22 with mocked CognitiveProfile + DomainActivation — verify the LLM prompt includes the "Relational context" section with entity memories, perspective divergence, and domain correlations.

2. **Unit test:** P22 with `Instance.isUnsatisfied()` — verify graceful degradation (existing behavior unchanged).

3. **Unit test:** Skip logic — verify regeneration when relational-context-hash changes, skip when unchanged.

4. **Unit test:** CognitionConfig.all() — verify entityKnowledgeEnabled defaults to false.

5. **Integration test:** End-to-end consolidation with CognitiveProfile wired — verify generated drive descriptions reference entity-specific details (not just generic relational schemas).

## Out of scope

- **#733 entity-enriched drive descriptions:** That issue targets richer entity data (entity-scoped belief revisions, per-entity ToM, entity-aware salience). This design provides the plumbing; #733 extends the data.
- **Render-time entity freshness:** New entities arriving mid-session between consolidations won't appear in drive descriptions. Accepted trade-off (D1).
- **LLM system prompt changes:** The existing Barrett constructionist instruction already covers somatic translation. No changes needed.

## References

- `docs/research/era5-relational-cognition-research.md` — register degradation from analytical sections, architecture decision
- `docs/research/era6-cognitive-memory-architecture-research.md` — Era 6 context (no additional constraints)
- `mindmap-intelligence/.../consolidation/DriveDescriptionGenerationPhase.java` — P22 current implementation
- `cognitive-index/.../CognitiveProfile.java` — entity knowledge resolution
- `cognitive-index/.../DomainActivation.java` — cross-domain correlation
- `cognitive-index/.../SocialComparison.java` — inter-agent perspective divergence
- `cognition/prompt/EntityKnowledgePromptSection.java` — current analytical rendering
- `cognition/prompt/SocialComparisonPromptSection.java` — current analytical rendering
- `cognition/prompt/DomainActivationPromptSection.java` — current analytical rendering
- `cognition-api/.../CognitionConfig.java` — config flags

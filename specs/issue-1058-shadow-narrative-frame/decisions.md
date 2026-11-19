# Decisions — #1058 Shadow Narrative Frame

## D1: Overall approach — emergent, not taxonomic

**Choice:** Build data plumbing (attractor context capture + enhanced prompt rendering), observe what emerges when the LLM receives displaced personality state + archetype context. No static shadow label taxonomy.
**Alternatives:**
- Static YAML shadow taxonomy — maps (family, mode, attractor) → shadow label. Rigid, doesn't capture accumulated state nuance.
- LLM-generated shadow labels at consolidation time — expressive but non-deterministic, adds latency to consolidation.
**Rationale:** The system already computes per-facet displacements. The "shadow narrative" should emerge from rendering this data to the LLM, not from a predefined label set. User explicitly pushed back on static shadows in favor of discrete modification values over time.
**Trade-offs:** No guaranteed narrative consistency across sessions — the LLM interprets the state each time. Future narrative identity work (#599) may need more structure.
**Sources:** #712 (shadow concept origin), SituationalPersonalityParticipant (facetDisplacements already computed), user design direction
**Exploration:** deep-analysis
**Status:** captured

## D2: Mode access at consolidation time

**Choice:** Query `SituationalPersonalityParticipant.currentSnapshot(agentId, tenantId)` from BehavioralSynthesisPhase
**Alternatives:**
- Read mode from experience node metadata — mode data may be stale or absent
- Inject SituationalDetector directly — needs evidence unavailable outside the tick
**Rationale:** The participant already caches the last snapshot per agent+tenant. BehavioralSynthesisPhase injects it via `Instance<>` and reads the cached state. Zero new SPIs, uses existing data flow.
**Trade-offs:** Snapshot is from the last tick, not from consolidation time. Lag is acceptable — consolidation runs after ticks.
**Sources:** SituationalPersonalityParticipant.currentSnapshot(), BehavioralSynthesisPhase injection pattern
**Exploration:** quick
**Status:** captured

## D3: Prompt rendering — configurable relevance-ranked facets

**Choice:** Render top-N displaced facets ranked by combined relevance score: `|displacement| × modeBoost × attractorBoost`. Configurable via config record.
**Alternatives:**
- Displacement magnitude only — simpler but surfaces irrelevant facets
- Full facet dump — complete but overwhelms prompt
- Sub-LLM narrative summary — expressive but adds latency and non-determinism
**Rationale:** Relevance to the current situation matters more than raw displacement magnitude. Mode weighting surfaces facets characteristic of the active mode; attractor correlation surfaces facets driving the behavioral tendency.
**Trade-offs:** Attractor-facet correlation map is a small static table that needs manual curation. Mode weighting depends on SituationalProfile data being present.
**Sources:** ShadowArchetypePromptSection (existing renderer), SituationalPersonalitySnapshot.facetDisplacements, user requirement for configurability
**Exploration:** quick
**Status:** captured

### D3 config parameters

- `maxFacets` (default: 5) — maximum displaced facets to render
- `minDisplacement` (default: 0.05) — minimum |displacement| to include
- `modeRelevanceBoost` (default: 1.5) — boost for facets in active mode's profile
- `attractorRelevanceBoost` (default: 1.3) — boost for facets correlating with dominant attractor
- Attractor-facet correlation map — static, defined on config (e.g., withdraw → [withdrawal, anxiousness, intimacy-avoidance])

## D4: Archetype context in prompt

**Choice:** Read primary archetype family from MindMap PERSON node properties (archetype-1-family). Include in ShadowArchetypePromptSection rendering alongside displaced facets.
**Alternatives:**
- Add archetype to DescriptorView — cleaner access but broader change, affects DescriptorView consumers
- Lightweight ArchetypeResolver SPI — proper abstraction but over-engineered for a single consumer
**Rationale:** BehavioralSynthesisPhase already has MindMapStore. Reading archetype-1-family from the PERSON node is one property lookup. No new types needed.
**Trade-offs:** Property-name coupling. If biographical import changes the property naming convention, this breaks silently.
**Sources:** PersonalityProfileHandler (writes archetype-N-family), MindMapStore (available in BehavioralSynthesisPhase)
**Exploration:** quick
**Depends on:** D2 (mode access pattern — same injection approach)
**Status:** captured

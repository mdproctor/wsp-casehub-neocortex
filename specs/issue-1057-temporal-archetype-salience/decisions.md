## D1: Scope — both extraction and runtime

**Choice:** Both extraction + runtime
**Alternatives:**
- Runtime only — assumes phase-indexed data exists. Defers extraction but runtime has no data to consume.
- Extraction only — produces data but no consumer. Useful only as groundwork.
**Rationale:** The extraction is the evidence; the runtime is the effect. Neither is useful alone. The extraction adds a field to an existing pipeline; the runtime adds a multiplier to an existing computation. Both are small.
**Trade-offs:** Slightly larger scope, but each layer is independently testable.
**Sources:** [#712 issue body — temporal drift section], [PersonalityProfileEntry.java — existing archetype extraction], [SituationalPersonalityParticipant.java — existing profile consumption]
**Exploration:** quick
**Status:** captured

## D2: Runtime mechanism — reweight situational profiles

**Choice:** Phase-indexed archetype salience weights modulate the intensity of each family's situational profile set via multiplicative scaling.
**Alternatives:**
- Swap active profile set — select one family per phase exclusively. Clean but lossy — secondary archetypes invisible.
- Blended profile composition — weighted average of all families' profiles facet-by-facet. Most nuanced but complex (merging 12-family × 5-mode × 13-facet matrices).
**Rationale:** Reweighting preserves the existing multi-archetype ranking while making phase salience a smooth scalar multiplier. No new data structures for profile composition. Backward compatible (default salience = 1.0).
**Trade-offs:** Giving up cross-family facet blending (D2 alt C). Acceptable because the per-character situational profiles already capture the nuance; phase salience modulates overall intensity, not individual facets.
**Sources:** [SituationalPersonalityParticipant.computeCompositeDelta() — existing modulation point], [SituationalProfileDefaults — family-to-profile mapping]
**Exploration:** quick
**Status:** captured

## D3: Phase source — derive from born date

**Choice:** Compute current phase from `lifecycle.born` LifecycleDate on the PERSON node + current time.
**Alternatives:**
- Explicit phase property — requires manual authoring, doesn't auto-advance.
- Narrative time — requires a narrative-time subsystem that doesn't exist.
**Rationale:** LifecycleDate already exists on PERSON nodes. Phase boundaries match FormativeTimestampGenerator conventions (0-12/13-17/18-25/26+). Falls back to `adulthood` when no born date — most agents are adult.
**Trade-offs:** Giving up fictional/narrative time awareness (D3 alt C). Acceptable for now; narrative time can override later.
**Sources:** [LifecycleDate.java — EDTF partial date], [LifecycleEvents.java — born label], [FormativeTimestampGenerator — existing phase boundaries]
**Exploration:** quick
**Status:** captured

## D4: Storage — individual MindMap properties

**Choice:** Store as `archetype-{rank}-salience-{phase}` properties on the PERSON node (12 properties for 3 archetypes × 4 phases).
**Alternatives:**
- Single structured property — compact but introduces a mini-format to parse.
- Dedicated SQLite table — over-engineered for 12 stable values per agent.
**Rationale:** Consistent with existing archetype property pattern (archetype-1-family, archetype-1-adjectives). Written once at import, read-only at runtime. Cached by CognitiveDefaults after first read. Zero new infrastructure.
**Trade-offs:** 12 more properties on PERSON nodes that already have ~30 personality properties. Acceptable — MindMap properties are cheap.
**Sources:** [PersonalityProfileHandler.writeArchetypes() — existing property pattern]
**Exploration:** quick
**Status:** captured

## D5: Extraction — extend PersonalityProfileEntry

**Choice:** Add PhaseSalience to ArchetypeSelection in PersonalityProfileEntry. The existing extraction pipeline already reasons about archetypes; phase salience is a natural extension.
**Alternatives:**
- Separate extraction step — post-hoc cross-referencing. More modular but adds a pipeline stage.
**Rationale:** The LLM is already in the context of reasoning about archetype identification. Asking "which archetype was most salient in each life phase?" is a natural follow-up. Single-pass extraction.
**Trade-offs:** Couples phase salience extraction to archetype extraction. If archetypes are re-extracted, phase salience is too — which is correct behavior.
**Sources:** [PersonalityProfileEntry.ArchetypeSelection — existing record], [PersonalityProfileHandler — existing handler]
**Exploration:** quick
**Status:** captured

## D6: Modulation formula — multiplicative scaling

**Choice:** `composite[facet] += delta[facet] * intensity * phaseSalience` where phaseSalience ∈ [0, 1] from the agent's current phase archetype weight. Default 1.0 when no data.
**Alternatives:**
- Additive offset on detection threshold — changes when modes activate, not how strongly. Different behavioral semantics.
**Rationale:** Multiplicative scaling is transparent, testable, and backward compatible. The archetype's stress response fades proportionally as that archetype becomes less salient in the current phase. Matches how intensity already modulates the profile.
**Trade-offs:** A low-salience archetype with a strong mode activation still contributes (at reduced intensity). The alternative (threshold) would suppress it entirely below a cutoff. Gradual fading is more psychologically realistic.
**Sources:** [SituationalPersonalityParticipant.computeCompositeDelta() — existing formula]
**Exploration:** quick
**Status:** captured

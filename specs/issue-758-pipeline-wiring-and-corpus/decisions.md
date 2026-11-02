## D1: Consolidation-time enrichment over render-time injection

**Choice:** Enrich DriveDescriptionGenerationPhase (P22) inputs with entity knowledge, social comparison, and domain activation data. The three analytical prompt sections stop rendering; their data becomes consolidation-time LLM input.
**Alternatives:**
- Render-time injection — fresh but template-based somatic translation is brittle and lower quality than LLM prose
- Hybrid (consolidation base + render-time delta) — handles new entities but adds two code paths for marginal edge case
**Rationale:** P22 already generates somatic drive descriptions via LLM. Feeding richer context produces higher-quality folded output. Descriptions are pre-baked so no analytical text reaches the prompt. Staleness risk is low — entities that matter have been consolidated; truly new entities lack the relational data worth folding.
**Trade-offs:** Drive descriptions are stale between consolidations. A new entity arriving mid-session won't appear in drive descriptions until the next consolidation cycle.
**Sources:** era5-relational-cognition-research.md (register degradation from analytical sections), DriveDescriptionGenerationPhase.java, EntityKnowledgePromptSection.java, CognitiveProfileParticipant.java
**Exploration:** quick
**Status:** captured

## D2: Unified context block in P22 prompt

**Choice:** Add entity knowledge, social comparison, and domain activation as a single "Relational Context" section in P22's LLM prompt alongside existing relational schemas. The LLM decides which data is relevant to which drive.
**Alternatives:**
- Per-drive selective injection — tighter token usage but requires hand-coded mapping of data→drive relevance, which the LLM does better naturally
**Rationale:** P22 already processes all drives in a single LLM call with full context. The LLM is better at deciding relevance than a hand-coded mapping. Token overhead is modest for active entities.
**Trade-offs:** Slightly more tokens in the P22 prompt vs more precise per-drive injection.
**Sources:** DriveDescriptionGenerationPhase.java (existing prompt structure)
**Exploration:** quick
**Depends on:** D1 (consolidation-time enrichment)
**Status:** captured

## D3: Disable analytical sections by default, keep code

**Choice:** Set entityKnowledgeEnabled, perspectiveComparisonEnabled, and domainActivationEnabled to false in CognitionConfig.all(). Keep section classes, participants, and rendering code intact for debugging and A/B evaluation.
**Alternatives:**
- Remove sections entirely — smaller codebase but loses evaluation capability during Era transition
- Gate on a new "driveFoldingEnabled" flag — unnecessary indirection when existing per-section flags already control rendering
**Rationale:** Pre-release, no backward compat concern. Sections available for evaluation (comparing folded vs unfolded output). Existing config flags suffice — no new flags needed.
**Trade-offs:** Dead code stays in the codebase. Acceptable given evaluation value and pre-release stage.
**Sources:** CognitionConfig.java (all() factory), CognitionCore.java (sectionCustomizer wiring)
**Exploration:** quick
**Depends on:** D1 (consolidation-time enrichment)
**Status:** captured

## D4: P22 queries services directly at consolidation time

**Choice:** Inject CognitiveProfile and DomainActivation into DriveDescriptionGenerationPhase. P22 calls them during consolidation to resolve entity knowledge, social comparison, and domain activation — same queries the tick participants use, in its own context.
**Alternatives:**
- Persist tick-time results for P22 to read — adds coupling (P22 depends on tick participants having run recently), intermediate data format becomes a contract
**Rationale:** Computations are lightweight (store queries, DTW over cached PAD series). Direct queries are self-contained — no dependency on tick-time execution order or intermediate persistence format.
**Trade-offs:** Recomputes data that tick participants may have already computed. Acceptable given low cost.
**Sources:** CognitiveProfile.java (resolve()), DomainActivation.java (correlate()), SocialComparison.java (compare()), DriveDescriptionGenerationPhase.java
**Exploration:** quick
**Depends on:** D1 (consolidation-time enrichment), D2 (unified context block)
**Status:** captured

## D5: Full entity enrichment — memory domains + edges + ToM via SPI

**Choice:** Expand buildRelationalContext to include relationship and reflection domain memories, MindMap edges, and per-entity Theory of Mind via a new MentalModelLookup SPI in cognition-api. P22 injects Instance<MentalModelLookup> for graceful degradation.
**Alternatives:**
- Memory domains + edges only (no ToM) — misses BDI data that grounds drive descriptions in specific beliefs about entities ("you believe she trusts you" vs generic "warmth when someone you protect is near")
- Move MentalModelMemory to cognition-api — cleaner long-term but more code movement for same result
- Query CbrRecordStore directly — fragile, duplicates schema knowledge
**Rationale:** No dependency cycle (verified: cognition-api does not depend on mindmap-intelligence). The SPI pattern is established (Instance<CognitiveProfile>, Instance<DomainActivation>). MentalModelSnapshot value type is already in cognition-api. One interface, one method — minimal surface area.
**Trade-offs:** New SPI in cognition-api. MentalModelMemory in cognition must implement it. Adds cognition-api as a dependency of mindmap-intelligence.
**Sources:** cognition-api/pom.xml (no cycle), cognition/pom.xml (depends on mindmap-intelligence but cognition-api does not), MentalModelSnapshot.java (value type in cognition-api), MentalModelMemory.java (impl in cognition)
**Exploration:** quick
**Depends on:** D4 (P22 queries services directly)
**Status:** captured

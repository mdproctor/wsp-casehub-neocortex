# Decisions — #477 Interpersonal Relational Schemas

## D1: Reframe scope from villain drift fix to general relational model

**Choice:** Reframe #477 as a general per-relationship awareness system, not a villain-specific fix
**Alternatives:**
- Villain drift fix first — narrower scope but defers the general model
- Keep original 4-layer 12-model scope — too large, most models aren't needed
**Rationale:** Code verification shows villain drift is partially mitigated by disposition-weighted CAPS + behavioral attractors. The real gap is that the cognitive system doesn't know WHO the agent is interacting with — AppraisalContext has no field for the interaction target, relational schemas exist only in eval YAML, and OtherModelDerivationPhase output is disconnected from the prompt pipeline.
**Trade-offs:** Won't specifically fix villain drift as a named problem — it becomes one test case among many
**Sources:** LlmAppraisalStrategy.java:21-49 (system prompt), AppraisalContext.java (no target field), eval-characters-generic.yaml (schema format), OtherModelDerivationPhase.java (disconnected output)
**Exploration:** deep-analysis
**Status:** captured

## D2: Store relational schemas as overlay properties on MindMap PERSON nodes

**Choice:** Use existing perspectival overlay system for per-relationship state
**Alternatives:**
- New RelationalSchemaStore SPI — more flexibility but adds a new SPI when overlays already support per-agent-per-target state
- Hybrid overlays + new memory domain — unnecessary complexity
**Rationale:** Perspectival overlays (OverlayRef, PerspectivalMerge, PerspectivalResolver) already provide per-agent subjective views of entity nodes with PAD and arbitrary properties. RelationshipStagePhase already writes familiarity to overlays. Adding structured relational dimensions is a natural extension, not a new abstraction.
**Trade-offs:** Arbitrary properties are strings, not typed — may need property naming conventions to distinguish relational schema fields from other overlay properties
**Sources:** OverlayRef.java, PerspectivalMerge.java, RelationshipStagePhase.java:159-165
**Exploration:** quick
**Status:** captured

## D3: Follow existing eval schema for relational data model

**Choice:** Promote eval-characters-generic.yaml schema (target/role/trust/intimacy/utility + attachment style/anxiety/avoidance + AMPD facets) to production types
**Alternatives:**
- Rethink from psychological first principles — risks analysis paralysis when tested model exists
- Extend with original issue's attraction/connection/longing — adds dimensions not yet validated in tests
**Rationale:** The eval schema represents tested thinking. RelationalSchema(target, role, trust, intimacy, utility, description) and AttachmentProfile(style, anxiety, avoidance) plus AMPD PersonalityFacet(facet, score, origin) are already used in EvalCharacterData and seeded into MindMap nodes as cognitiveKind="relational-schema". Promoting to production types avoids redesign.
**Trade-offs:** May need to extend the schema later (the original issue proposed attraction/repulsion, connection/disconnection, longing/indifference as additional dimensions)
**Sources:** eval-characters-generic.yaml:58-82, EvalCharacterLoader.java:105-127
**Exploration:** quick
**Status:** captured

## D4: 5-issue decomposition with dependency ordering

**Choice:** Decompose into 5 child issues: (1) types + storage, (2) wire into appraisal, (3) connect OtherModel to prompts, (4) dynamic evolution, (5) CAPS relationship biasing. Order: 1 → 2 → 3 (parallel with 2) → 4 → 5.
**Alternatives:**
- 3-issue decomposition (just 1-3, defer 4-5) — delivers awareness without evolution
- Monolithic single issue — too large to review or test incrementally
**Rationale:** Each child issue is independently testable and delivers incremental value. Issues 1-3 make the system relationship-aware with seeded data. Issues 4-5 make relationships dynamic and mechanically filtered.
**Trade-offs:** 5 issues means 5 PR cycles — more overhead than a monolith, but each PR is reviewable
**Sources:** AppraisalTickParticipant.java:113-176 (tick method), BehavioralPromptSection.java (attractor rendering), OtherModelDerivationPhase.java (disconnected mental models)
**Exploration:** quick
**Status:** captured

# Appraisal Wiring — Implementation Plan

**Focal issue:** #717 — Wire relational context into AppraisalContext + LlmAppraisalStrategy
**Parent:** #477 — Interpersonal relational schemas
**Depends on:** #716 (complete)

**Goal:** Make the appraisal pipeline relationship-aware. When the agent interacts with a known target, the SEC evaluation uses relational context (role, trust, intimacy, utility) and the agent's own personality facets to produce personality-filtered emotional responses.

---

## Batch 1: SPI type changes (cognition-api)

### Task 1: CognitionTickContext — add targetAgentId

**Files:**
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitionTickContext.java`
- Test: `cognition-api/src/test/java/io/casehub/neocortex/cognition/core/CognitionTickContextTest.java`

Add `@Nullable String targetAgentId` as 7th record component. Keep existing convenience constructors passing null. Add 6-arg convenience constructor with targetAgentId but no briefing.

### Task 2: AppraisalContext — add relational fields

**Files:**
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalContext.java`
- Test: `cognition-api/src/test/java/io/casehub/neocortex/cognition/appraisal/AppraisalContextTest.java`

Add `@Nullable RelationalSchema targetSchema` and `@Nullable List<PersonalityFacet> personalityFacets` as 8th and 9th fields. Keep existing 7-arg and 6-arg constructors passing null.

## Batch 2: Resolution and prompt rendering (cognition)

### Task 3: AppraisalTickParticipant — resolve relational context

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/AppraisalTickParticipant.java`

In `tick()`, after loading defaults and before calling `appraisalStrategy.appraise()`:
1. Read `context.targetAgentId()`
2. If non-null and MindMapStore available: resolve overlay → RelationalSchema
3. Get personalityFacets from `defaults.personalityProfile().facets()`
4. Pass both to new AppraisalContext constructor

Resolution follows RelationshipStagePhase pattern: iterate PERSON subgraph nodes, find target's shared node by agentId property, find our overlay for that shared node, extract rel.* properties.

### Task 4: LlmAppraisalStrategy — update prompt

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/LlmAppraisalStrategy.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/LlmAppraisalStrategyTest.java`

Update SYSTEM_PROMPT to mention relationship context and personality traits.
Update buildUserMessage() to add two new sections (Barrett grounding format):
- "Relationship with [target]" — role, trust, intimacy, utility, description
- "Personality traits" — high-scoring facets with origin prose

### Task 5: CognitionCore — add tick overload

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java`

Add `tick(agentId, tenantId, descriptor, resolver, observation, targetAgentId)` overload. Existing overload passes null targetAgentId. Thread through to CognitionTickContext.

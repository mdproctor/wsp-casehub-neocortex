# Decisions — #463 Drive Goal Bridge

## D1: Persistence trigger

**Choice:** On registration — when a proposal moves to `registeredGoals` in GoalProposalOrchestrator
**Alternatives:**
- On escalation to PRIMARY — higher bar but misses non-escalated goals
- Immediately on proposal — floods graph with speculative goals
- New LLM/human confirmation step — matches issue wording but adds ceremony over the existing acceptance gate
**Rationale:** GoalProposalOrchestrator already distinguishes `cachedProposals` (new/speculative) from `registeredGoals` (accepted). Registration is the existing acceptance gate — reusing it avoids adding a new confirmation flow.
**Trade-offs:** Some registered goals may still be short-lived if drives fluctuate. GoalPrioritizationPhase decay handles cleanup.
**Sources:** GoalProposalOrchestrator.java (cognition/goal/), issue #463
**Exploration:** quick
**Status:** captured

## D2: Bridge location

**Choice:** New `CognitionTickParticipant` in the cognition module (TERMINAL phase)
**Alternatives:**
- Inside GoalProposalOrchestrator directly — tighter coupling, mixes proposal logic with persistence
- ConsolidationPhase in mindmap-intelligence — can't depend on cognition, would need a new SPI or CDI event to read proposals
**Rationale:** Follows established pattern (AppraisalTickParticipant, GutFeelingParticipant, DomainActivationParticipant). Same lifecycle as GoalProposalOrchestrator. cognition already depends on mindmap-api. Plain class with constructor dependencies — no CDI.
**Trade-offs:** Adds a new `configure*()` method to CognitionCore. Consumer (blocks) must call it at startup.
**Sources:** CognitionCore.java, AppraisalTickParticipant.java, CognitionTickParticipant.java (cognition-api)
**Exploration:** quick
**Status:** captured

## D3: Deduplication strategy

**Choice:** TermNormalizer (general domain) + Jaro-Winkler >= 0.85
**Alternatives:**
- Jaro-Winkler name-only — misses synonym matches ("studying" vs "study")
- Full EntityMatcher pattern — overkill for goal name matching, designed for spatial entities
**Rationale:** Aligns with knowledge-pipeline's normalize-then-match pattern. TermNormalizer canonicalizes goal names before fuzzy comparison. knowledge-pipeline-api is Tier 1 pure Java (lightweight dependency). NoOpTermNormalizer passthrough when WordNet not on classpath.
**Trade-offs:** Adds knowledge-pipeline-api dependency to cognition. TermNormalizer "general" domain needs implementing (currently supports PLACE/THING/ACTIVITY). Companion enhancement — sub-dictionaries (IT/computing, business) for richer normalization.
**Depends on:** D2 (bridge lives in cognition module, so dependency is on cognition's pom.xml)
**Sources:** TermNormalizer.java (knowledge-pipeline-api), WordNetTermNormalizer.java, MergeDetectionPhase.java, GoalResolutionPhase.java, JaroWinkler.java
**Exploration:** quick
**Status:** captured

## D4: Match action on dedup hit

**Choice:** Enrich existing node — add `origin-drive` and `formation-reason` properties to matched GOAL node
**Alternatives:**
- Link via edge — 'motivated-by' edge adds graph complexity without proportional benefit
- Skip silently — loses drive provenance on existing goals
**Rationale:** Additive enrichment preserves the existing node's identity, edges, and lifecycle state while adding drive provenance. `origin-drive` is stored as a separate property from `origin` (which GoalRecognitionPhase sets), so both provenance sources coexist.
**Trade-offs:** If a goal matches multiple drive axes over time, `origin-drive` gets overwritten (last write wins). Could use a list property if multi-drive provenance matters.
**Sources:** GoalRecognitionPhase.java (sets `origin`), Goallike.java (trait interface)
**Exploration:** quick
**Status:** captured

## D5: Abandonment sync

**Choice:** Yes — sync drive abandonments to GOAL node status (dormant + abandonment-reason)
**Alternatives:**
- Create-only — leave abandonment to GoalPrioritizationPhase decay. Simpler scope but leaves drive-originated decay invisible.
**Rationale:** Keeps the MindMap graph consistent with drive state. GoalPrioritizationPhase already handles generic decay (confidence < threshold + negative affect), but drive-specific abandonment is a distinct signal — "the underlying motivation disappeared" vs "the goal stagnated."
**Trade-offs:** Bridge must track which GOAL nodes it created/enriched to know which ones to update on abandonment. Adds state tracking to the participant.
**Sources:** GoalProposalOrchestrator.java (abandonment logic), GoalPrioritizationPhase.java (decay logic)
**Exploration:** quick
**Status:** captured

## D6: Architecture approach

**Choice:** Approach A — reactive CognitionTickParticipant that reads GoalProposalOrchestrator state directly
**Alternatives:**
- CDI events from GoalProposalOrchestrator — orchestrator is a plain class (not CDI-managed), firing events would require making it CDI-managed or passing Event<> in
- Bridge inside CognitionCore directly — bloats the composition root, mixes orchestration with persistence
**Rationale:** Follows the established participant pattern. Constructor receives GoalProposalOrchestrator + MindMapStore + TermNormalizer. Reads proposals directly from orchestrator (not via CognitionTickContext, which only carries identity). Tracks its own diff state in ConcurrentHashMap keyed by agentId|tenantId.
**Trade-offs:** GoalProposalOrchestrator.tick() return value is discarded by CognitionCore — the participant must read currentProposals() and diff against its tracked state rather than reacting to the tick result directly.
**Sources:** CognitionCore.java (tick dispatch), CognitionTickContext.java (record — immutable, not extensible), AppraisalTickParticipant.java (pattern reference)
**Exploration:** quick
**Status:** captured

## D7: Need-tier property on GOAL nodes (#464)

**Choice:** Static `NeedTier.fromDriveAxis(DriveAxis)` mapping method, set as `need-tier` property at creation
**Alternatives:**
- Inline mapping in DriveGoalBridgeParticipant — duplicates if other creators need the same mapping
- New utility class — unnecessary indirection for a 4-entry switch
**Rationale:** Both types live in cognition-api. A static method on NeedTier is discoverable and reusable. The mapping (CURIOSITY→UNDERSTANDING, COMPETENCE→SELF_EXPRESSION, AFFILIATION→SOCIAL, AUTONOMY→SELF_EXPRESSION) follows the issue specification.
**Trade-offs:** Fixed mapping — if a drive axis should map to multiple need tiers, this would need revision. Single-tier-per-axis is correct for now.
**Sources:** NeedTier.java, DriveAxis.java (cognition-api), issue #464
**Exploration:** quick
**Status:** captured

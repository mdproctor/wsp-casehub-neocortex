# HANDOFF — casehub-neocortex

## Status

blocks#303 (migrate cognitive state) is **CLOSED**. Both repos landed on main. Neocortex squashed to 7 commits. All tests green.

## Immediate Next Step

Four follow-up issues remain in the .plan queue, ordered by impact:

### 1. blocks#324 — Migrate NarrativeGoalEscalationPolicy + LlmCrossAxisGoalEnricher (XS)

**What:** Two SPI implementations deleted from blocks `agentic/social/goal/` but not migrated to neocortex.

**NarrativeGoalEscalationPolicy** (62 lines) implements `GoalEscalationPolicy` SPI. Escalates goal priority based on narrative theme alignment — strongest-theme match with count-based cap, sign-aware so declining themes demote.

**LlmCrossAxisGoalEnricher** (60 lines) implements `CrossAxisGoalEnricher` SPI. Uses `AgentProvider` to LLM-enrich compound goals that span multiple drive axes.

**Where to create:** neocortex `cognition/src/main/java/io/casehub/neocortex/cognition/goal/`. Both SPIs are already defined in cognition-api at `io.casehub.neocortex.cognition.goal`.

**After creating:** restore CDI producer in blocks `BlocksBeans` (line ~431 placeholder) and Spring producer in `BlocksAutoConfiguration` (line ~349 placeholder). Both files have comments marking where the producers were removed.

**Source code:** recoverable from `git show 52e40944:blocks-core/src/main/java/io/casehub/blocks/agentic/social/goal/NarrativeGoalEscalationPolicy.java` and same for `LlmCrossAxisGoalEnricher.java`.

### 2. blocks#323 — Migrate SocialNormDetector (S)

**What:** `SocialNormDetector` (180 lines) detects emergent social norms from CBR store observations. Groups behavioral patterns, computes adherence rates, classifies strength (EMERGING/ESTABLISHED/DECLINING), per-tenant caching with `KeyedLock`.

**Where to create:** neocortex `cognition/src/main/java/io/casehub/neocortex/cognition/emergence/`. All dependent types (`NormDetectionConfig`, `SocialNorm`, `NormStrength`, `NormObservation`, `DetectedNorms`, `NormDetectionTick`, `NormObservationSchema`) already exist in cognition-api.

**KeyedLock dependency:** The class uses `io.casehub.blocks.agent.KeyedLock` (a blocks utility providing per-key `ReentrantLock` via `ConcurrentHashMap`). Either migrate `KeyedLock` to neocortex or replace with inline `ConcurrentHashMap<String, ReentrantLock>` + `computeIfAbsent` pattern.

**After creating:** restore CDI producer in `BlocksBeans` (line ~330 placeholder) and `BlocksAutoConfiguration` (line ~304 placeholder).

**Source code:** `git show 52e40944:blocks-core/src/main/java/io/casehub/blocks/agentic/social/emergence/SocialNormDetector.java`

### 3. blocks#325 — Remove orphaned social-jpa modules (S)

**What:** Three modules implementing store SPIs that no orchestrator injects anymore:
- `social-jpa` — Quarkus JPA: `JpaMentalModelStore`, `JpaStrategyStore`, `JpaUserProfileStore`, `JpaNarrativeStore`
- `social-jpa-common` — shared entities: `MentalModelEntity`, `NarrativeEntity`, converters
- `social-spring-jpa` — Spring Boot: `SpringMentalModelStore`, `SpringStrategyStore`, etc.

**Why orphaned:** Batch 3 consolidated the store SPIs (`MentalModelStore`, `StrategyStore`, `UserProfileStore`, `NarrativeStore`) into `CaseMemoryStore`-backed Memory classes (`MentalModelMemory`, `UserProfileMemory`, etc.). The JPA implementations have no consumers — the orchestrators now inject Memory classes, not Store SPIs.

**The modules compile clean** — the value types they reference (`AttributedState`, `NarrativeFragment`, etc.) were updated to neocortex imports. But they implement interfaces that nothing injects.

**Action:** Verify no CDI/Spring injection points remain (search for `@Inject MentalModelStore`, `@Autowired StrategyStore`, etc. across all repos). Then remove from blocks parent POM `<modules>` section and delete the 3 module directories.

### 4. blocks#326 — Update wacky-manor examples imports (XS)

**What:** `examples/wacky-manor/src/test/java/io/casehub/blocks/agentic/social/OverlayFamiliarityPropertyModelTest.java` references `io.casehub.blocks.agentic.social.*`.

**Action:** Mechanical import replacement: `io.casehub.blocks.agentic.social.X` → `io.casehub.neocortex.cognition.X` (use the same class-to-package mapping from the migration). This is in a separate repo (`casehub/examples`), not in the blocks or neocortex repos.

## Architecture After Migration

**Neocortex cognition modules** (new — section 5 in CLAUDE.md):
- `cognition-api` — SPIs, value types, config records, prompt renderer interface
- `cognition` — CognitionCore (composition root), all orchestrators, drive sources, prompt sections, participants, defaults

**Blocks cognition integration** (new package `io.casehub.blocks.agentic.cognition`):
- `CognitionAvatarAdapter` — thin `AvatarCognition` bridge. Delegates tick/record/evaluate to neocortex `CognitionCore`. Bridges `CognitionPromptRenderer` → `PromptSection` via inline assembler wrapping. Consumes goal revisions and bridges to eidos lifecycle.
- `MemoryHygieneSpiAdapter` — bridges blocks `MemoryHygieneOrchestrator` (returns `HygieneTick`) to neocortex SPI (returns `void`). Needed because blocks' hygiene orchestrator has a richer return type.

**Key type unifications done during migration:**
- blocks `ReflectionEntry` and `KnowledgeGapSummary` deleted — neocortex versions in `memory-api` are authoritative
- blocks `ReflectionQueryStore` now extends `io.casehub.neocortex.memory.ReflectionQueryStore`
- blocks `MemoryHygieneOrchestrator` stays as-is (different return type prevents direct SPI impl) — adapter bridges it

**CDI wiring changes (BlocksBeans + BlocksAutoConfiguration):**
- Dead CBR store producers (`CbrMentalModelStore`, `CbrStrategyStore`, `CbrUserProfileStore`, `CbrNarrativeStore`, `NoOpNarrativeStore`) → replaced with Memory producers (`MentalModelMemory`, `UserProfileMemory`, `StrategyMemory`, `NarrativeMemory`)
- Orchestrator constructors updated from Store SPIs to Memory classes
- `DriveOrchestrator` decomposed from monolithic constructor to individual `DriveSource` instances (`CuriosityDrive`, `CompetenceDrive`, `AffiliationDrive`, `AutonomyDrive`)
- `socialAvatarCognition` → `cognitionAvatarAdapter` with full participant setup (CognitiveGoalOrchestrator, CognitiveProfileParticipant, DomainActivationParticipant)

## References

- `plans/2026-09-29-cognition-migration.md` — migration plan (Batch 7 revised)
- `specs/issue-303-migrate-cognitive-state/2026-09-29-cognition-migration-design.md` — design spec
- `specs/issue-303-migrate-cognitive-state/decisions.md` — 10 design decisions (D1–D10)

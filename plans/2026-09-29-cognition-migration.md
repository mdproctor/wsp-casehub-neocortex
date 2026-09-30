# Cognition Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** casehubio/blocks#303 — Migrate cognitive state from
blocks to neocortex

**Issue group:** casehubio/blocks#303, casehubio/blocks#298 (parent epic)

**Goal:** Move the entire social cognition layer (~213 production files,
~13K LOC) from blocks to neocortex as optional `cognition-api` +
`cognition` modules, consolidating ad-hoc stores onto existing neocortex
abstractions.

**Architecture:** New modules `cognition-api` (SPIs + value types) and
`cognition` (all implementations, package-separated by subdomain). Stores
consolidate onto CaseMemoryStore and CbrRecordStore. Blocks retains only
a thin bridge layer (prompt sections + SocialAvatarCognition). IntelliJ
workspace with both repos handles cross-project moves with automatic
reference updates.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI, Maven multi-module

## Global Constraints

- Pre-release platform — breaking changes are free
- All store access via `Instance<>` with `isResolvable()` for optionality
- `@DefaultBean` NoOps for all exported SPIs
- LLM access via platform's `AgentProvider` (not blocks' StructuredAgentInvoker)
- blocks#317 must land before execution begins
- groupId: `io.casehub`, artifactId prefix: `casehub-neocortex-cognition-*`
- Root package: `io.casehub.neocortex.cognition`
- Use `ide_move_file` for all source file moves — never bash cp/mv
- Use `ide_refactor_rename` for renames — never manual find-replace
- Build with: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

---

## Batch 1: Module Scaffolding

### Task 1: Create cognition-api and cognition Maven modules

**Files:**
- Create: `cognition-api/pom.xml`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/.gitkeep`
- Create: `cognition/pom.xml`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/core/.gitkeep`
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/.gitkeep`
- Modify: `pom.xml` (parent POM — add modules)

**Interfaces:**
- Produces: Two Maven modules wired into the reactor build.
  `cognition-api` depends on `cognitive-api`. `cognition` depends on
  `cognition-api` + `cognitive-api` + `cognitive-index` + `memory-api` +
  `mindmap-api` + `mindmap-intelligence` + `fusion-api`.

- [ ] **Step 1: Open IntelliJ workspace with both repos**

```
ide_open_workspace(modules=[
  "/Users/mdproctor/claude/casehub/slots/203/neocortex",
  "/Users/mdproctor/claude/casehub/slots/203/blocks"
])
```

Wait for indexing to complete (`ide_index_status` returns
`isDumbMode: false`).

- [ ] **Step 2: Create cognition-api POM**

Create `cognition-api/pom.xml`:

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>
  <artifactId>casehub-neocortex-cognition-api</artifactId>
  <name>CaseHub Neocortex - Cognition API</name>
  <description>Cognition SPIs and value types — tick types, state records, signal hierarchies, config types, orchestrator SPIs.</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-cognitive-api</artifactId>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.assertj</groupId>
      <artifactId>assertj-core</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

- [ ] **Step 3: Create cognition POM**

Create `cognition/pom.xml`:

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>
  <artifactId>casehub-neocortex-cognition</artifactId>
  <name>CaseHub Neocortex - Cognition</name>
  <description>Cognition runtime — CognitionCore tick scheduler, all orchestrators (mood, drive, narrative, user model, mental model, strategy, inner life, personality evolution), goal proposal, emergence, consolidation phases.</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-cognition-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-cognitive-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-cognitive-index</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-memory-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-mindmap-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-mindmap-intelligence</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-fusion-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-platform-api</artifactId>
    </dependency>
    <!-- AgentProvider for LLM orchestrators -->
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-platform-agent-api</artifactId>
      <optional>true</optional>
    </dependency>
    <!-- Eidos for personality/disposition -->
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-eidos-api</artifactId>
      <optional>true</optional>
    </dependency>
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-arc</artifactId>
      <scope>provided</scope>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.assertj</groupId>
      <artifactId>assertj-core</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

Note: exact dependency artifactIds for platform agent-api and eidos-api
need verification at execution time — use `ide_find_class` to locate
`AgentProvider` and `AgentDescriptor` and read their module's POM.

- [ ] **Step 4: Wire modules into parent POM**

Read `pom.xml` (neocortex root). Add to `<modules>` section:
```xml
<module>cognition-api</module>
<module>cognition</module>
```

Place after `cognitive-index` and before `rag-api` to maintain the
dependency ordering convention.

- [ ] **Step 5: Create package directories**

```bash
mkdir -p cognition-api/src/main/java/io/casehub/neocortex/cognition
mkdir -p cognition-api/src/test/java/io/casehub/neocortex/cognition
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/core
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/mood
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/drive
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/narrative
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/usermodel
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/mentalmodel
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/strategy
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/innerlife
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/personality
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/goal
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/emergence
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/belief
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/relationship
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/reflection
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/memory
mkdir -p cognition/src/main/java/io/casehub/neocortex/cognition/temporal
mkdir -p cognition/src/test/java/io/casehub/neocortex/cognition
```

- [ ] **Step 6: Build to verify module wiring**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl cognition-api,cognition -DskipTests
```

Expected: BUILD SUCCESS (empty modules compile).

- [ ] **Step 7: Commit**

```bash
git add cognition-api/ cognition/ pom.xml
git commit -m "feat(#303): scaffold cognition-api and cognition modules

Empty module structure with Maven wiring and package directories.

Refs casehubio/blocks#303"
```

---

## Batch 2: Value Types → cognition-api

### Task 2: Move enums, records, and sealed types to cognition-api

**Files:**
- Move: All enum, record, sealed, and config types from
  `blocks-core/.../agentic/social/` → `cognition-api/.../cognition/`
- Move: Corresponding tests

**Interfaces:**
- Consumes: cognition-api module (Task 1)
- Produces: All value types available from cognition-api. Blocks
  temporarily depends on cognition-api during migration.

For each type below, use `ide_find_class` in the blocks project to
locate it, then `ide_move_file` to move it to the cognition-api target
package.

**Types to move (by sub-domain):**

Tick types → `io.casehub.neocortex.cognition`:
`MoodTick`, `DriveTick`, `NarrativeTick`, `UserModelTick`,
`MentalModelTick`, `StrategyLearningTick`, `StrategyReflection`,
`InnerLifeTick`, `EvolutionTick`

Enums → `io.casehub.neocortex.cognition`:
`CognitionPhase`, `BdiDimension`, `CueType`, `RewardAxis`,
`ReinforcementDirection`

Drive types → `io.casehub.neocortex.cognition.drive`:
`DriveAxis`, `DriveProfile`, `DriveIntensity`, `DriveSource`,
`DriveReinforcementEntry`

Mood types → `io.casehub.neocortex.cognition.mood`:
`MoodSignal` (sealed hierarchy), `MoodConfig`, `MoodCongruenceConfig`

Narrative types → `io.casehub.neocortex.cognition.narrative`:
`NarrativeState`, `NarrativeFragment`, `NarrativeEpisode`,
`NarrativeConfig` + remaining narrative value types

User model types → `io.casehub.neocortex.cognition.usermodel`:
`UserProfile`, `InteractionSignal` (sealed), `UserModelConfig`

Mental model types → `io.casehub.neocortex.cognition.mentalmodel`:
`MentalModelSnapshot`, `MentalProjection`, `AttributedState`,
`SynthesisResult`, `MentalStateSignal` (sealed), `MentalModelConfig`

Strategy types → `io.casehub.neocortex.cognition.strategy`:
`StrategyProfile`, `EngagementSignal` (sealed), `EngagementEvidence`,
`EngagementTrend`, `StrategyLearningConfig`

Inner life types → `io.casehub.neocortex.cognition.innerlife`:
`MotivationAssessment`, `ContentQualityGate`, `InnerLifeConfig`,
`CivilityConstraint`

Personality types → `io.casehub.neocortex.cognition.personality`:
`TraitActivation`, `TraitPressureSource`, `PersonalityEvolutionConfig`

Core types → `io.casehub.neocortex.cognition.core`:
`CognitionTickContext`, `CognitionTickParticipant`, `CognitiveImpact`,
`DriveConfig`, `DriveAdaptationConfig`

Goal + emergence types: move all goal proposal and emergence value types
to `io.casehub.neocortex.cognition.goal` and
`io.casehub.neocortex.cognition.emergence` respectively.

- [ ] **Step 1: Locate and batch-move each type group**

For each group above:
1. `ide_find_class(className)` to get the file path
2. `ide_move_file(source, targetDir)` to move it
3. IntelliJ auto-updates imports in blocks

Process one sub-domain at a time (mood types, drive types, etc.).

- [ ] **Step 2: Add cognition-api dependency to blocks**

Add to blocks' POM (temporarily, removed in Batch 7):
```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-cognition-api</artifactId>
</dependency>
```

- [ ] **Step 3: Build both repos**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests
```

Run from neocortex first, then blocks. Fix any compilation errors
(missing imports, package references).

- [ ] **Step 4: Run blocks tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl blocks-core
```

Expected: all tests pass (imports updated by IntelliJ).

- [ ] **Step 5: Commit both repos**

In neocortex:
```bash
git add cognition-api/
git commit -m "feat(#303): move value types and SPIs to cognition-api

Enums, records, sealed hierarchies, config types, and SPIs for all
cognitive orchestrators.

Refs casehubio/blocks#303"
```

In blocks:
```bash
git add .
git commit -m "refactor(#303): point imports to neocortex cognition-api

Temporary cognition-api dependency added during migration.

Refs casehubio/blocks#303"
```

---

## Batch 3: Store Consolidation

### Task 3: Consolidate NarrativeStore and StrategyStore onto CbrRecordStore

**Files:**
- Modify: `NarrativeOrchestrator` — replace NarrativeStore with CbrRecordStore
- Modify: `StrategyLearningOrchestrator` — replace StrategyStore with CbrRecordStore
- Delete: `NarrativeStore.java`, `NoOpNarrativeStore.java`,
  `CbrNarrativeStore.java`, `CbrStateStore.java` (use `ide_refactor_safe_delete`)
- Delete: `StrategyStore.java`, `CbrStrategyStore.java`
- Create: `cognition/.../narrative/NarrativeMemory.java` (typed query helper)
- Create: `cognition/.../strategy/StrategyMemory.java` (typed query helper)
- Test: Move/update corresponding tests

**Interfaces:**
- Consumes: CbrRecordStore SPI (memory-api), NarrativeStateSchema,
  StrategyProfileSchema
- Produces: `NarrativeMemory` (typed CbrRecordStore wrapper),
  `StrategyMemory` (typed CbrRecordStore wrapper)

- [ ] **Step 1: Write NarrativeMemory query helper**

Create `cognition/src/main/java/io/casehub/neocortex/cognition/narrative/NarrativeMemory.java`:

```java
package io.casehub.neocortex.cognition.narrative;

import io.casehub.neocortex.memory.cbr.CbrRecordStore;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;

@ApplicationScoped
public class NarrativeMemory {

    private final CbrRecordStore store;

    NarrativeMemory(Instance<CbrRecordStore> store) {
        this.store = store.isResolvable() ? store.get() : null;
    }

    // Typed convenience methods wrapping CbrRecordStore queries
    // Pattern: delegate to store with domain="narrative", caseType="narrative-state"
    // Exact methods TBD at execution time based on NarrativeOrchestrator's
    // actual usage of NarrativeStore — read NarrativeOrchestrator.java and
    // CbrNarrativeStore.java to determine the query patterns used.
}
```

- [ ] **Step 2: Read CbrNarrativeStore to understand the query patterns**

Use `ide_find_class("CbrNarrativeStore")` and read it. Copy the query
logic into NarrativeMemory, replacing the custom SPI calls with direct
CbrRecordStore calls.

- [ ] **Step 3: Update NarrativeOrchestrator to use NarrativeMemory**

Replace `NarrativeStore` injection with `NarrativeMemory` injection.
Update all method calls to use the new helper.

- [ ] **Step 4: Repeat for StrategyMemory**

Same pattern: read `StrategyMemory`, create `StrategyMemory` helper,
update `StrategyLearningOrchestrator`.

- [ ] **Step 5: Delete old Store SPIs and implementations**

Use `ide_refactor_safe_delete` for each: `NarrativeStore`,
`NoOpNarrativeStore`, `NarrativeMemory`, `CbrStateStore`,
`StrategyStore`, `StrategyMemory`.

- [ ] **Step 6: Run tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl blocks-core
```

Fix any failures from the store migration.

- [ ] **Step 7: Commit**

```bash
git commit -m "refactor(#303): consolidate NarrativeStore and StrategyStore onto CbrRecordStore

Replace ad-hoc Store SPIs with typed query helpers over CbrRecordStore.
NarrativeMemory and StrategyMemory provide domain-specific convenience
methods.

Refs casehubio/blocks#303"
```

### Task 4: Consolidate UserProfileStore and MentalModelStore onto CaseMemoryStore

**Files:**
- Modify: `UserModelOrchestrator` — replace UserProfileStore with CaseMemoryStore
- Modify: `MentalModelOrchestrator` — replace MentalModelStore with CaseMemoryStore
- Delete: `UserProfileStore.java`, `CbrUserProfileStore.java`,
  `UserProfileSchema.java`
- Delete: `MentalModelStore.java`, `CbrMentalModelStore.java`,
  `MentalModelSchema.java`
- Create: `cognition/.../usermodel/UserProfileMemory.java`
- Create: `cognition/.../mentalmodel/MentalModelMemory.java`
- Test: Move/update corresponding tests

**Interfaces:**
- Consumes: CaseMemoryStore SPI (memory-api)
- Produces: `UserProfileMemory` (typed CaseMemoryStore wrapper with
  domain="user-profile"), `MentalModelMemory` (typed CaseMemoryStore
  wrapper with domain="mental-model")

- [ ] **Step 1: Write UserProfileMemory query helper**

Create `cognition/src/main/java/io/casehub/neocortex/cognition/usermodel/UserProfileMemory.java`.

Pattern: `@ApplicationScoped`, `Instance<CaseMemoryStore>` injection,
domain="user-profile". Read `UserProfileMemory` to understand query
patterns and replicate with `CaseMemoryStore.query()`.

- [ ] **Step 2: Write MentalModelMemory query helper**

Same pattern with domain="mental-model". Read `MentalModelMemory`.

- [ ] **Step 3: Update orchestrators**

Replace `UserProfileStore` injection with `UserProfileMemory` in
`UserModelOrchestrator`. Replace `MentalModelStore` with
`MentalModelMemory` in `MentalModelOrchestrator`.

- [ ] **Step 4: Delete old stores**

Use `ide_refactor_safe_delete` for all deleted files.

- [ ] **Step 5: Delete JPA implementations**

Remove blocks' JPA modules for social stores:
- Delete `social-jpa-common/` module directory
- Delete `social-jpa/` module directory
- Delete `social-spring-jpa/` module directory
- Remove from blocks parent POM `<modules>` section

- [ ] **Step 6: Run tests, fix failures, commit**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl blocks-core
git commit -m "refactor(#303): consolidate UserProfileStore and MentalModelStore onto CaseMemoryStore

Replace ad-hoc stores with typed query helpers over CaseMemoryStore.
Delete social-jpa, social-jpa-common, social-spring-jpa modules.

Refs casehubio/blocks#303"
```

---

## Batch 4: Pure-Computation Orchestrators → cognition

### Task 5: Move Mood orchestrator and supporting types

**Files:**
- Move: `MoodOrchestrator`, `MoodCongruentGoalAppraisal`,
  `GoalEmotionMoodBridge` → `cognition/.../cognition/mood/`
- Move: Corresponding tests
- Modify: blocks CognitionCore imports (auto-handled by IntelliJ)

**Interfaces:**
- Consumes: `MoodConfig`, `MoodSignal` (from cognition-api, Task 2),
  `MoodState`/`MoodBaseline`/`MoodDecay` (from memory-api)
- Produces: `MoodOrchestrator` as a CDI bean in the cognition module

- [ ] **Step 1: Move production classes**

For each class: `ide_find_class` → `ide_move_file` to
`cognition/src/main/java/io/casehub/neocortex/cognition/mood/`

- [ ] **Step 2: Move test classes**

Move all Mood*Test files to
`cognition/src/test/java/io/casehub/neocortex/cognition/mood/`

- [ ] **Step 3: Replace KeyedLock with standard concurrency**

`MoodOrchestrator` uses `KeyedLock`. Replace with
`ConcurrentHashMap<String, ReentrantLock>` or equivalent. The
`KeyedLock` utility is trivial (~49 LOC) — inline the logic or create a
package-private utility in `.core`.

- [ ] **Step 4: Build and test**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl cognition-api,cognition
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl blocks-core
```

Both must pass.

- [ ] **Step 5: Commit both repos**

### Task 6: Move Drive orchestrator and supporting types

**Files:**
- Move: `DriveOrchestrator`, `DriveComposer`, `AffiliationDrive`,
  `AutonomyDrive`, `CompetenceDrive`, `CuriosityDrive`,
  `DriveAdaptationPhase`, `RelationshipPressureSource`
  → `cognition/.../cognition/drive/`
- Move: Corresponding tests

Same pattern as Task 5. DriveOrchestrator depends on MoodOrchestrator
(now in cognition) — this is fine, both are in the same module.

- [ ] **Steps 1-5: Same pattern as Task 5**

### Task 7: Move Narrative orchestrator and supporting types

**Files:**
- Move: `NarrativeOrchestrator`, `GroupNarrativeOrchestrator`,
  `NarrativePipeline`, `NarrativeOutputProcessor`,
  `NarrativeContentSummariser`, `NarrativeStateSchema`
  → `cognition/.../cognition/narrative/`
- Move: Corresponding tests

Note: `NarrativeContentSummariser` uses `AgentProvider` (LLM). After
move, replace any `StructuredAgentInvoker` usage with direct
`Instance<AgentProvider>`.

- [ ] **Steps 1-5: Same pattern as Task 5**

### Task 8: Move PersonalityEvolution orchestrator

**Files:**
- Move: `PersonalityEvolutionOrchestrator` → `cognition/.../cognition/personality/`
- Move: Corresponding tests

Depends on eidos types (`DispositionEvolution`, `AgentDescriptor`) —
these stay in eidos. Use `Instance<>` for graceful degradation.

- [ ] **Steps 1-5: Same pattern as Task 5**

- [ ] **Step 6: Commit all moves in one commit**

```bash
git commit -m "feat(#303): move pure-computation orchestrators to cognition module

MoodOrchestrator, DriveOrchestrator, NarrativeOrchestrator,
PersonalityEvolutionOrchestrator and all supporting types.

Refs casehubio/blocks#303"
```

---

## Batch 5: LLM-Backed Orchestrators → cognition

### Task 9: Move LLM orchestrators, replacing StructuredAgentInvoker

**Files:**
- Move: `UserModelOrchestrator` → `cognition/.../cognition/usermodel/`
- Move: `MentalModelOrchestrator` → `cognition/.../cognition/mentalmodel/`
- Move: `StrategyLearningOrchestrator` → `cognition/.../cognition/strategy/`
- Move: `InnerLifeOrchestrator` → `cognition/.../cognition/innerlife/`
- Move: `LlmReflectionSynthesizer` → `cognition/.../cognition/reflection/`
- Move: `SubjectResolver`, `InteractionMapper`, `TokenJaccardDistance`
- Move: All corresponding tests
- Modify: Each orchestrator — replace `StructuredAgentInvoker` with
  `Instance<AgentProvider>`

**Interfaces:**
- Consumes: `AgentProvider` (platform), `Instance<>` for optionality
- Produces: 4 LLM orchestrators + LlmReflectionSynthesizer as CDI beans

- [ ] **Step 1: Read StructuredAgentInvoker to understand the wrapper**

`ide_find_class("StructuredAgentInvoker")` — read it. Understand what it
adds over raw `AgentProvider`. Likely: structured output parsing, retry
logic, prompt assembly. Determine which parts to keep inline vs
replace with direct `AgentProvider` calls.

- [ ] **Step 2: Move orchestrators one at a time**

For each: `ide_move_file`, then update `StructuredAgentInvoker` calls
to `AgentProvider` calls. If `StructuredAgentInvoker` provides
meaningful abstraction, create a package-private equivalent in
`cognition/.../core/` that wraps `AgentProvider`.

- [ ] **Step 3: Move LlmReflectionSynthesizer**

This implements neocortex's `ReflectionSynthesizer` SPI. After move,
it becomes the default implementation in the cognition module (activated
when cognition is on classpath). Update `@Alternative @Priority` as
needed.

- [ ] **Step 4: Move supporting types**

Move `SubjectResolver`, `InteractionMapper`, `TokenJaccardDistance`
to their respective packages.

- [ ] **Step 5: Build and test**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install
```

Both repos must compile and tests must pass.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(#303): move LLM-backed orchestrators to cognition module

UserModelOrchestrator, MentalModelOrchestrator,
StrategyLearningOrchestrator, InnerLifeOrchestrator,
LlmReflectionSynthesizer. Replaced StructuredAgentInvoker with
AgentProvider.

Refs casehubio/blocks#303"
```

---

## Batch 6: Framework + Higher-Order Components → cognition

### Task 10: Move CognitionCore and framework types

**Files:**
- Move: `CognitionCore`, `CognitionSnapshot`, `CognitionDelta`,
  `CognitionMetrics`, `CognitiveAttentionMediator`,
  `ConsolidationMediator`, `AttentionRelevance`
  → `cognition/.../cognition/core/`
- Move: `CognitionCoreTest` and all framework tests
- Modify: `CognitionCore` — replace `StructuredAgentInvoker` with
  `Instance<AgentProvider>` (CognitionCore uses LLM for mood appraisal
  and BDI extraction)

**Interfaces:**
- Consumes: All orchestrators (now in cognition), `CognitionConfig`
  (from cognition-api)
- Produces: `CognitionCore` as the tick scheduler CDI bean

- [ ] **Step 1: Move all framework types**

`ide_move_file` for each class listed above.

- [ ] **Step 2: Replace StructuredAgentInvoker in CognitionCore**

Same pattern as Task 9.

- [ ] **Step 3: Build, test, commit**

### Task 11: Move goal, emergence, and consolidation phases

**Files:**
- Move: `GoalProposalOrchestrator`, `CognitiveGoalOrchestrator`,
  `LlmDriveGoalFormationStrategy`, `LlmCrossAxisGoalEnricher`
  + all goal proposal types → `cognition/.../cognition/goal/`
- Move: `SocialNormDetector`, `CollectiveGoalFormation`
  + emergence types → `cognition/.../cognition/emergence/`
- Move: `BeliefRevisionPhase`, `BeliefRevisionConfig`
  → `cognition/.../cognition/belief/`
- Move: `RelationshipStagePhase`, `RelationshipStageConfig`,
  `RelationshipStageProvider` → `cognition/.../cognition/relationship/`
- Move: `MemoryHygieneOrchestrator` → `cognition/.../cognition/memory/`
- Move: `TemporalFocusOrchestrator`, `ReflectionRetrievalOrchestrator`
  → `cognition/.../cognition/temporal/`
- Move: All corresponding tests

**Interfaces:**
- Consumes: ConsolidationPhase SPI (mindmap-intelligence), all
  orchestrators
- Produces: Consolidation phases registered via CDI discovery

- [ ] **Step 1: Move all types by sub-domain**

Process one package at a time. Use `ide_move_file` for each.

- [ ] **Step 2: Move goal-specific phases from mindmap-intelligence**

Move `GoalResolutionPhase`, `GoalAffectPhase`,
`GoalPrioritizationPhase`, `GoalRecognitionPhase` from
mindmap-intelligence to `cognition/.../cognition/goal/`.

These are neocortex-internal moves (same repo) — IntelliJ handles
reference updates cleanly.

- [ ] **Step 3: Build and test**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install
```

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(#303): move goal, emergence, consolidation phases to cognition

GoalProposalOrchestrator, SocialNormDetector, CollectiveGoalFormation,
BeliefRevisionPhase, DriveAdaptationPhase, RelationshipStagePhase,
MemoryHygieneOrchestrator, TemporalFocusOrchestrator.
Relocated 4 goal phases from mindmap-intelligence.

Refs casehubio/blocks#303"
```

---

## Batch 7: Complete Extraction + Blocks Cleanup

> **Revised 2026-09-30.** Original plan kept a bridge layer in blocks
> (SocialAvatarCognition, prompt sections). Revised after architectural
> analysis: neocortex is the complete single-agent cognitive stack. No
> bridge. See decisions D1 (revised), D7–D10.

### Task 12: Move prompt rendering to neocortex cognition

Move the composable prompt rendering system from blocks to neocortex.
This is cognitive code — how the brain presents itself to the LLM.

**Files:**
- Move: 23 prompt section classes from blocks `social/prompt/` →
  `cognition/.../cognition/prompt/`
- Move: `AffordanceRenderer`, `CognitiveObservationSections` →
  `cognition/.../cognition/prompt/`
- Move: `CognitiveSystemPromptRenderer` → `cognition/.../cognition/prompt/`
- Create: neocortex prompt section interface in `cognition-api`
  (replaces dependency on blocks' speech-api PromptSection)
- Wire: `CognitionCore.promptSections()` to compose rendered output

**Design notes:**
- Each driver's prompt section should be pluggable (prose/JSON/hybrid)
  to support neocortex#390 evaluation
- Rendering format is a per-driver strategy, not hardcoded
- The interface blocks' PromptSection used: `@Nullable String
  contribute(PromptContext)` where PromptContext is `(agentId,
  tenantId, subjectId)`. The neocortex equivalent should carry the
  same context without depending on speech-api.

- [ ] **Step 1: Define cognition prompt rendering interface**

Create in `cognition-api`:
```java
@FunctionalInterface
public interface CognitionPromptRenderer {
    @Nullable String render(CognitionRenderContext context);
}
```

And `CognitionRenderContext` record with `(String agentId, String
tenantId, @Nullable String subjectId)`.

- [ ] **Step 2: Move prompt sections**

Move each prompt section class to `cognition/.../cognition/prompt/`.
Update to implement `CognitionPromptRenderer` instead of blocks'
`PromptSection`. Adapt import changes for cognitive types already
in neocortex.

- [ ] **Step 3: Move rendering utilities**

Move `AffordanceRenderer` and `CognitiveObservationSections` to
`cognition/.../cognition/prompt/`. These are pure Java rendering
utilities coupled to cognitive types.

- [ ] **Step 4: Wire CognitionCore.promptSections()**

Add `promptSections()` method to CognitionCore. Discovers all
`CognitionPromptRenderer` instances, composes output. Populates
`CognitionMetrics.promptSectionsContributed` and
`promptSectionContent` (fields already exist).

- [ ] **Step 5: Move CognitiveSystemPromptRenderer**

Implements eidos `SystemPromptRenderer`. Depends on eidos types and
`CognitionConfig` — no blocks dependency. Move to cognition module.

- [ ] **Step 6: Build and test neocortex**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install
```

### Task 13: Move defaults to neocortex

**Files:**
- Create: `@DefaultBean` producers in cognition module for all 13
  orchestrator configs (from `SocialCognitionDefaultBeans`)
- Create: `@DefaultBean` for `SubjectResolver`, `InteractionMapper`,
  `NormFilter` implementations
- Delete: `SocialCognitionDefaultBeans` from blocks

- [ ] **Step 1: Read SocialCognitionDefaultBeans**

Understand all 14 `@DefaultBean` producers. Recreate in
`cognition/.../cognition/CognitionDefaultBeans.java`.

- [ ] **Step 2: Build and test**

### Task 14: Blocks cleanup — delete migrated code

**Files:**
- Delete: All 169 non-prompt production files in `agentic/social/`
  (already duplicated in neocortex)
- Delete: All 113 test files for migrated code
- Delete: `SocialAvatarCognition` (replaced by blocks using
  CognitionCore directly)
- Delete: `SocialPromptAssembler` (CognitionCore owns composition)
- Delete: `SocialCognitionDefaultBeans` (moved to neocortex)
- Delete: 23 prompt section originals (moved to neocortex)
- Check: `StructuredAgentInvoker`, `KeyedLock` — safe delete if unused
- Modify: blocks POM — add `cognition` dependency

- [ ] **Step 1: Add cognition dependency to blocks POM**

```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-cognition</artifactId>
</dependency>
```

- [ ] **Step 2: Create thin AvatarCognition adapter**

Blocks' speech-ws uses `AvatarCognition` SPI. Create a thin adapter
that delegates to CognitionCore — blocks' integration point.
Not a shim: it maps blocks' speech lifecycle (when to tick, when to
evaluate proactive) to CognitionCore calls.

- [ ] **Step 3: Update CognitionCompiler imports**

YAML DSL's CognitionCompiler + spec records produce config types now
in cognition-api. Update imports. The compiler logic is unchanged.

- [ ] **Step 4: Delete all migrated blocks code**

Use `ide_refactor_safe_delete` on `agentic/social/` packages.
Delete `SocialAvatarCognition`, `SocialPromptAssembler`,
`SocialCognitionDefaultBeans`.

- [ ] **Step 5: Delete unused utilities**

`StructuredAgentInvoker`, `KeyedLock` — safe delete if no remaining
blocks consumers.

- [ ] **Step 6: Build full test suites**

```bash
# Neocortex
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install

# Blocks
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install
```

Both repos: full build with tests.

### Task 15: Update documentation

- [ ] **Step 1: Update neocortex CLAUDE.md**

Add cognition and cognition-api module descriptions. Add prompt
rendering to cognition module description. Update module table.

- [ ] **Step 2: Update blocks CLAUDE.md**

Remove social cognition module descriptions. Note that cognitive
capabilities are provided by neocortex cognition module.

- [ ] **Step 3: Update consumer examples**

Update casehub/examples (wackymanor) imports from blocks social
types to neocortex cognition types.

- [ ] **Step 4: Final commits**

In neocortex:
```bash
git commit -m "feat(#303): complete cognition migration — full extraction to neocortex

All cognitive code including prompt rendering, defaults, and composition.
Neocortex is the complete single-agent cognitive stack. No bridge layer.

Closes casehubio/blocks#303"
```

In blocks:
```bash
git commit -m "refactor(#303): remove all cognitive code from blocks

Cognitive capabilities provided by neocortex cognition module.
Blocks retains: AvatarCognition adapter (speech lifecycle), YAML DSL
(CognitionCompiler config parsing).

Refs casehubio/blocks#303"
```

---

## References

- [2026-09-29-cognition-migration-design.md] — design spec this plan implements
- [decisions.md] — 10 captured design decisions (D1–D10)
- casehubio/blocks#303 — focal issue
- casehubio/blocks#298 — parent epic
- casehubio/blocks#296 — established the migration pattern (OCC emotions)
- casehubio/blocks#317 — prerequisite (landed)
- neocortex#390 — prompt format evaluation (prose vs JSON vs hybrid)
- neocortex#391 — adaptive cognitive brief (metacognitive feedback loop)
- neocortex CLAUDE.md — module structure and naming conventions
- blocks `agentic/social/` package — source code being migrated
- rag-query-augmentation — AgentProvider usage precedent in neocortex

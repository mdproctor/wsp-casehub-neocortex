# RelationalSchemaEvolutionPhase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #719 — RelationalSchemaEvolutionPhase — trust, intimacy, role dynamics
**Issue group:** #716, #717, #718, #719 (branch covers epic #477)

**Goal:** Make relational schemas evolve from interaction history — trust/intimacy update from relationship memories, role transitions from personality-conditioned state machine.

**Architecture:** New `ConsolidationPhase` at `@Priority(19)`, sharing the overlay iteration pattern from `RelationshipStagePhase(18)`. Reads familiarity (already computed by Priority 18), relationship memories, and `CognitiveDefaults` (personality facets, attachment profile, social cognition). Writes `rel.*` overlay properties via `RelationalSchema.toProperties()`. Pure computation — no LLM calls.

**Tech Stack:** Java 21, CDI (`@ApplicationScoped`, `@Priority`, `Instance<T>`), MindMapStore overlay pattern, CaseMemoryStore relationship queries, CognitiveDefaultsRegistry.

## Global Constraints

- Java 21 language features on Java 26 JVM
- `@Priority(19)` — runs after `RelationshipStagePhase(18)`, shares priority with `BehavioralSynthesisPhase(19)` (no shared state, ordering irrelevant)
- Trust range `[-1, 1]`, intimacy range `[0, 1]`, utility range `[0, 1]`
- `RelationalSchema.fromProperties()` returns `null` when no `rel.target-id` exists — triggers initial seeding
- ConflictInterpretation multipliers: REPAIR=0.6, INFORMATION=0.9, NEUTRAL=1.0, DISENGAGE=1.4
- PAD pleasure thresholds for positive/negative classification: >0.1 / <-0.1 (same as `RelationshipStagePhase`)
- One role transition per consolidation cycle (multi-hop prevention)
- Module: `cognition` (same as `RelationshipStagePhase`)
- Package: `io.casehub.neocortex.cognition.relationship`
- Test module: `cognition` test sources

---

## Batch 1: Trust, Intimacy, and Role Evolution

### Task 1: Phase skeleton + trust and intimacy update

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/relationship/RelationalSchemaEvolutionPhase.java`
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/relationship/RelationalSchemaEvolutionPhaseTest.java`

**Interfaces:**
- Consumes: `ConsolidationPhase` SPI, `MindMapStore` (overlay iteration + `updateNode`), `CaseMemoryStore` (`RelationshipQuery.forPair`), `CognitiveDefaultsRegistry` (`forAgentOrDefaults` → `socialCognition()`, `personalityProfile().attachment()`, `personalityProfile().facets()`), `RelationalSchema.fromProperties()` / `toProperties()`
- Produces: `RelationalSchemaEvolutionPhase` — consolidation phase writing `rel.trust`, `rel.intimacy`, `rel.role` overlay properties

- [ ] **Step 1: Write failing test — initial seeding when no rel.* properties exist**

```java
@Test
void seedsInitialSchemaWhenNoRelProperties() {
    // Create overlay with familiarity but no rel.* properties
    var sgId = store.createSubgraph(new SubgraphInput("person", SubgraphTypes.PERSON, null), TENANT);
    var sharedId = store.addNode(NodeInput.of("bob", sgId)
        .withProperties(Map.of("agentId", "bob")), TENANT);
    store.addNode(NodeInput.of("overlay-alice-bob", sgId)
        .withTraits(Set.of("overlay"))
        .withProperties(Map.of(OverlayRef.AGENT_ID, "alice"))
        .withRefs(Set.of(OverlayRef.of(sharedId))), TENANT);

    // Store one positive relationship memory
    memoryStore.store(MemoryInput.builder()
        .text("friendly interaction").domain("relationship")
        .subject(Subject.of("agent", "alice"))
        .subject(Subject.of("agent", "bob"))
        .pleasure(0.5).tenantId(TENANT).build());

    phase.run(TENANT, List.of());

    var overlay = findOverlay(store, TENANT, "alice");
    var schema = RelationalSchema.fromProperties(overlay.properties());
    assertThat(schema).isNotNull();
    assertThat(schema.targetId()).isEqualTo("bob");
    assertThat(schema.role()).isEqualTo("stranger");
    assertThat(schema.trust()).isGreaterThan(0.0);
    assertThat(schema.intimacy()).isGreaterThan(0.0);
}
```

Setup uses `InMemoryMindMapStore`, `InMemoryMemoryStore`, and `CognitiveDefaultsRegistry.forTesting()`. Helper `findOverlay()` locates the overlay node by observer agentId.

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognition/pom.xml test -Dtest=RelationalSchemaEvolutionPhaseTest#seedsInitialSchemaWhenNoRelProperties`
Expected: FAIL — class does not exist

- [ ] **Step 3: Implement phase skeleton with trust and intimacy formulas**

Create `RelationalSchemaEvolutionPhase` following `RelationshipStagePhase` pattern:
- Same overlay iteration (PERSON subgraph, shared nodes by agentId, overlay nodes by overlay trait)
- For each overlay pair: query relationship memories, classify positive/negative/neutral using PAD pleasure (thresholds 0.1/-0.1)
- Read existing `RelationalSchema.fromProperties()` — if null, seed with `stranger/0.0/0.0/0.0/null`
- Resolve `CognitiveDefaults` for observer: `socialCognition()`, `personalityProfile().attachment()`, `personalityProfile().facets()`
- **Trust formula:**
  - `valence = clamp((positive * positiveWeight - negative * negativeWeight) / total, -1.0, 1.0)` where `positiveWeight = 1.0`, `negativeWeight = 1.0`
  - If valence ≥ 0: `trustDelta = trustFormationRate * valence * (1.0 - callousness)`
  - If valence < 0: `trustDelta = trustFormationRate * valence * conflictMultiplier`
  - `trustCeiling = 1.0 - avoidance`; `newTrust = clamp(currentTrust + trustDelta, -1.0, trustCeiling)`
- **Intimacy formula:**
  - `intimacyDelta = trustFormationRate * max(0, valence) * (1.0 - avoidance)`
  - `intimacyDelta *= (1.0 + 0.5 * anxiety)`
  - `newIntimacy = clamp(currentIntimacy + intimacyDelta, 0.0, 1.0)`
- Write updated schema via `toProperties()` → `mindMapStore.updateNode()`
- Role stays as current value (no transitions yet — Task 2)

Two constructors: CDI `@Inject` with `Instance<T>` for optional deps, and package-private for tests.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Write failing test — positive valence increases trust, dampened by Callousness**

```java
@Test
void callousnessDampensPositiveTrustGain() {
    // Seed overlay with existing schema (trust=0.0)
    // Agent has Callousness=0.8
    // All positive interactions
    // Expect trust gain much smaller than without Callousness

    setupOverlayWithSchema("alice", "bob", 0.0, 0.0, "stranger");
    storePositiveMemories("alice", "bob", 5);

    var defaults = CognitiveDefaults.empty("alice")
        .withSocialCognition(SocialCognitionDefaults.defaults())
        .withPersonalityProfile(new PersonalityProfile(null, null, null, null,
            List.of(new PersonalityFacet("Callousness", 0.8, "high callousness"))));
    phase = createPhase(defaults);

    phase.run(TENANT, List.of());

    var schema = readSchema("alice");
    assertThat(schema.trust()).isGreaterThan(0.0);

    // Compare with non-callous agent
    resetOverlay("alice", "bob", 0.0, 0.0, "stranger");
    var noCallous = CognitiveDefaults.empty("alice")
        .withSocialCognition(SocialCognitionDefaults.defaults());
    phase = createPhase(noCallous);
    phase.run(TENANT, List.of());

    var schemaNoCallous = readSchema("alice");
    assertThat(schema.trust()).isLessThan(schemaNoCallous.trust());
}
```

- [ ] **Step 6: Run test, verify it passes (implementation already handles this)**

- [ ] **Step 7: Write failing test — negative valence with ConflictInterpretation.DISENGAGE amplifies trust loss**

```java
@Test
void disengageAmplifiesNegativeTrustLoss() {
    setupOverlayWithSchema("alice", "bob", 0.3, 0.0, "stranger");
    storeNegativeMemories("alice", "bob", 5);

    var disengage = CognitiveDefaults.empty("alice")
        .withSocialCognition(new SocialCognitionDefaults(0.5, ConflictInterpretation.DISENGAGE));
    phase = createPhase(disengage);
    phase.run(TENANT, List.of());
    var schemaDisengage = readSchema("alice");

    resetOverlay("alice", "bob", 0.3, 0.0, "stranger");
    var repair = CognitiveDefaults.empty("alice")
        .withSocialCognition(new SocialCognitionDefaults(0.5, ConflictInterpretation.REPAIR));
    phase = createPhase(repair);
    phase.run(TENANT, List.of());
    var schemaRepair = readSchema("alice");

    // DISENGAGE (1.4x) loses more trust than REPAIR (0.6x)
    assertThat(schemaDisengage.trust()).isLessThan(schemaRepair.trust());
}
```

- [ ] **Step 8: Run test, verify it passes**

- [ ] **Step 9: Write failing test — avoidance caps trust ceiling**

```java
@Test
void avoidanceCapsMaxTrust() {
    setupOverlayWithSchema("alice", "bob", 0.0, 0.0, "stranger");
    storePositiveMemories("alice", "bob", 50);  // many positive → high trust

    var avoidant = CognitiveDefaults.empty("alice")
        .withSocialCognition(SocialCognitionDefaults.defaults())
        .withPersonalityProfile(new PersonalityProfile(null, null, null,
            new AttachmentProfile("dismissive-avoidant", 0.1, 0.8), List.of()));
    phase = createPhase(avoidant);
    phase.run(TENANT, List.of());

    var schema = readSchema("alice");
    assertThat(schema.trust()).isLessThanOrEqualTo(0.2);  // ceiling = 1.0 - 0.8
}
```

- [ ] **Step 10: Run test, verify it passes**

- [ ] **Step 11: Write failing test — anxiety amplifies intimacy gain**

```java
@Test
void anxietyAmplifiesIntimacyGain() {
    setupOverlayWithSchema("alice", "bob", 0.0, 0.0, "stranger");
    storePositiveMemories("alice", "bob", 5);

    var anxious = CognitiveDefaults.empty("alice")
        .withSocialCognition(SocialCognitionDefaults.defaults())
        .withPersonalityProfile(new PersonalityProfile(null, null, null,
            new AttachmentProfile("anxious", 0.9, 0.1), List.of()));
    phase = createPhase(anxious);
    phase.run(TENANT, List.of());
    var schemaAnxious = readSchema("alice");

    resetOverlay("alice", "bob", 0.0, 0.0, "stranger");
    var secure = CognitiveDefaults.empty("alice")
        .withSocialCognition(SocialCognitionDefaults.defaults())
        .withPersonalityProfile(new PersonalityProfile(null, null, null,
            new AttachmentProfile("secure", 0.1, 0.1), List.of()));
    phase = createPhase(secure);
    phase.run(TENANT, List.of());
    var schemaSecure = readSchema("alice");

    assertThat(schemaAnxious.intimacy()).isGreaterThan(schemaSecure.intimacy());
}
```

- [ ] **Step 12: Run test, verify it passes**

- [ ] **Step 13: Write failing test — no memories means no update**

```java
@Test
void noMemoriesNoUpdate() {
    setupOverlayWithSchema("alice", "bob", 0.3, 0.2, "ally");
    // No memories stored
    phase.run(TENANT, List.of());

    var schema = readSchema("alice");
    assertThat(schema.trust()).isEqualTo(0.3);
    assertThat(schema.intimacy()).isEqualTo(0.2);
    assertThat(schema.role()).isEqualTo("ally");
}
```

- [ ] **Step 14: Run test, verify it passes**

- [ ] **Step 15: Commit**

```
feat(#719): RelationalSchemaEvolutionPhase with trust and intimacy formulas

Trust: signed [-1,1], Callousness dampens positive gain, ConflictInterpretation
modulates negative, avoidance caps ceiling. Intimacy: anxiety amplifies,
avoidance dampens. Initial seeding on first encounter. @Priority(19).

Refs #719
```

### Task 2: Role transition state machine

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/relationship/RelationalSchemaEvolutionPhase.java`
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/relationship/RelationalSchemaEvolutionPhaseTest.java`

**Interfaces:**
- Consumes: Trust value computed in Task 1, `PersonalityFacet` constants (`CALLOUSNESS`, `MANIPULATIVENESS`), `PersonalityFacet.isHigh()` / `isLow()`
- Produces: `resolveRole(String currentRole, double newTrust, List<PersonalityFacet> facets, double utility)` — static method returning the new role string

- [ ] **Step 1: Write failing test — stranger → ally at trust ≥ 0.5**

```java
@Test
void strangerBecomesAllyAtHighTrust() {
    setupOverlayWithSchema("alice", "bob", 0.0, 0.0, "stranger");
    storePositiveMemories("alice", "bob", 20);  // enough for trust > 0.5

    phase.run(TENANT, List.of());

    var schema = readSchema("alice");
    assertThat(schema.trust()).isGreaterThanOrEqualTo(0.5);
    assertThat(schema.role()).isEqualTo("ally");
}
```

- [ ] **Step 2: Run test, verify it fails (role stays "stranger" — no transitions yet)**

- [ ] **Step 3: Implement `resolveRole()` static method with full transition table**

Extract a static `resolveRole(String currentRole, double newTrust, List<PersonalityFacet> facets, double utility)` method implementing the 8-row transition table from the spec:

| Current | Trust ≥ 0.5 | Trust ≤ -0.3 |
|---------|-------------|--------------|
| stranger | → ally (default) or tool (Manipulativeness > 0.7) | → threat |
| ally | → mentor (utility > 0.5) or stays | → obstacle |
| mentor | stays | → obstacle |
| tool | → ally (Callousness < 0.3) or stays | → obstacle |
| prey | → tool (Manipulativeness > 0.5) or stays | → threat |
| obstacle | → stranger (trust ≥ 0.5) | stays |
| threat | → stranger (trust ≥ 0.5) | stays |
| protectee | stays | → stranger |

Call `resolveRole()` after trust/intimacy update, write new role to the schema properties. Multi-hop prevention: one call per cycle (inherent — only called once per overlay per run).

- [ ] **Step 4: Run test, verify it passes**

- [ ] **Step 5: Write failing test — stranger → tool when Manipulativeness > 0.7**

```java
@Test
void manipulativeStrangerBecomesToolNotAlly() {
    setupOverlayWithSchema("alice", "bob", 0.0, 0.0, "stranger");
    storePositiveMemories("alice", "bob", 20);

    var manipulative = CognitiveDefaults.empty("alice")
        .withSocialCognition(SocialCognitionDefaults.defaults())
        .withPersonalityProfile(new PersonalityProfile(null, null, null, null,
            List.of(new PersonalityFacet("Manipulativeness", 0.8, "high manipulativeness"))));
    phase = createPhase(manipulative);
    phase.run(TENANT, List.of());

    var schema = readSchema("alice");
    assertThat(schema.role()).isEqualTo("tool");
}
```

- [ ] **Step 6: Run test, verify it passes**

- [ ] **Step 7: Write failing test — stranger → threat at negative trust**

```java
@Test
void strangerBecomesThreatAtNegativeTrust() {
    setupOverlayWithSchema("alice", "bob", 0.0, 0.0, "stranger");
    storeNegativeMemories("alice", "bob", 20);

    phase.run(TENANT, List.of());

    var schema = readSchema("alice");
    assertThat(schema.trust()).isLessThanOrEqualTo(-0.3);
    assertThat(schema.role()).isEqualTo("threat");
}
```

- [ ] **Step 8: Run test, verify it passes**

- [ ] **Step 9: Write failing test — prey → tool (not ally) when Manipulativeness > 0.5**

```java
@Test
void preyBecomesToolNotAllyForManipulativeAgent() {
    setupOverlayWithSchema("alice", "bob", 0.0, 0.0, "prey");
    storePositiveMemories("alice", "bob", 20);

    var manipulative = CognitiveDefaults.empty("alice")
        .withSocialCognition(SocialCognitionDefaults.defaults())
        .withPersonalityProfile(new PersonalityProfile(null, null, null, null,
            List.of(new PersonalityFacet("Manipulativeness", 0.6, "moderate manipulativeness"))));
    phase = createPhase(manipulative);
    phase.run(TENANT, List.of());

    var schema = readSchema("alice");
    assertThat(schema.role()).isEqualTo("tool");
}
```

- [ ] **Step 10: Run test, verify it passes**

- [ ] **Step 11: Write failing test — mid-range trust (between -0.3 and 0.5) triggers no transition**

```java
@Test
void midRangeTrustNoRoleTransition() {
    setupOverlayWithSchema("alice", "bob", 0.0, 0.0, "stranger");
    storePositiveMemories("alice", "bob", 3);  // small — trust stays below 0.5

    phase.run(TENANT, List.of());

    var schema = readSchema("alice");
    assertThat(schema.trust()).isGreaterThan(0.0).isLessThan(0.5);
    assertThat(schema.role()).isEqualTo("stranger");
}
```

- [ ] **Step 12: Run test, verify it passes**

- [ ] **Step 13: Write failing test — obstacle recovers to stranger at trust ≥ 0.5**

```java
@Test
void obstacleRecoversToStrangerAtHighTrust() {
    setupOverlayWithSchema("alice", "bob", 0.0, 0.0, "obstacle");
    storePositiveMemories("alice", "bob", 20);

    phase.run(TENANT, List.of());

    var schema = readSchema("alice");
    assertThat(schema.trust()).isGreaterThanOrEqualTo(0.5);
    assertThat(schema.role()).isEqualTo("stranger");
}
```

- [ ] **Step 14: Run test, verify it passes**

- [ ] **Step 15: Run full test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognition/pom.xml test`
Expected: all tests pass

- [ ] **Step 16: Commit**

```
feat(#719): role transition state machine with personality conditioning

8-role transition table: stranger→ally/tool/threat, prey→tool not ally
for manipulative agents, obstacle/threat recovery to stranger. Multi-hop
prevention (one transition per cycle). Mid-range trust is sticky.

Closes #719
```

---

## References

- `specs/issue-477-relational-schemas/2026-10-28-relational-schemas-design.md` — design spec (trust formula lines 328-367, intimacy lines 369-379, role table lines 383-403)
- `cognition/src/main/java/.../RelationshipStagePhase.java` — overlay iteration and memory query pattern
- `cognitive-index/src/main/java/.../RelationalSchema.java` — `fromProperties()` / `toProperties()`
- `cognitive-index/src/main/java/.../SocialCognitionDefaults.java` — trustFormationRate, ConflictInterpretation
- `cognitive-index/src/main/java/.../AttachmentProfile.java` — avoidance, anxiety
- `cognitive-index/src/main/java/.../PersonalityFacet.java` — CALLOUSNESS, MANIPULATIVENESS, isHigh()
- `cognitive-index/src/main/java/.../CognitiveDefaultsRegistry.java` — forAgentOrDefaults(), forTesting()
- `mindmap-intelligence/src/main/java/.../ConsolidationPhase.java` — SPI interface
- `mindmap-intelligence/src/test/.../GoalResolutionPhaseTest.java` — test pattern for consolidation phases
- GitHub #719 — focal issue
- GitHub #477 — parent epic

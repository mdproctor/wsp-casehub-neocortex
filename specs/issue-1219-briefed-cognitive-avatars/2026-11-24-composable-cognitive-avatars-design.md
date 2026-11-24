# Composable Cognitive Avatars — Design Spec

**Issue:** casehubio/neocortex#1219
**Branch:** issue-1219-briefed-cognitive-avatars
**Date:** 2026-11-24

---

## 1. Problem

The cognitive stack currently operates at one altitude: full emergent
cognition via `CognitionCore` — tick loop, CAPS settling, emotions,
personality evolution. This is powerful for agents that develop identity
over time, but heavyweight for many practical use cases: coaching,
mentoring, goal planning, task management, personal assistance.

These scenarios need a consistent persona that shapes reasoning
substantively — not just stylistically — without requiring the full
emergent machinery. But the need isn't binary. An avatar might want
inner thoughts and hierarchy of needs without personality evolution.
Another might want goal decomposition and temporal awareness without
mood tracking. The constraint is performance and complexity, not a
fixed feature boundary.

## 2. Solution

**Composable cognitive avatars** — agents assembled from independent
cognitive capabilities, where each capability can be enabled or
disabled per avatar via configuration. The architecture provides:

1. A **composition root** (`CognitiveAvatar`) that wires available
   capabilities based on a profile
2. A **capability SPI** that each cognitive function implements
3. A **profile format** (existing CognitiveDefaults YAML) that declares
   which capabilities are active and configures each one
4. A **briefing mechanism** (per-prompt identity anchor) for avatars
   whose identity is declared rather than emergent

The composition mechanism doesn't draw a ceiling on what capabilities
can be composed. The initial delivery ships a practical starting set;
further capabilities can be added as independent units without
architectural change.

## 3. Architecture

### 3.1 Shared cognitive infrastructure

Both briefed avatars and emergent agents (CognitionCore) consume the
same CDI service layer. These are standalone beans that either
composition root can inject independently:

| Service | Module | What it provides |
|---------|--------|-----------------|
| `MindMapStore` | mindmap-api | Knowledge graph, GOAL subgraph, entity awareness |
| `CaseMemoryStore` | memory-api | Cross-session persistent memory |
| `CbrRecordStore` | memory-api | Case-based reasoning similarity search |
| `CognitiveDefaultsRegistry` | cognitive-index | Per-agent YAML profile loading + hot-reload |
| `CognitiveDerivationEngine` | cognitive-index | Disposition → config derivation (20+ pathways) |
| `TemporalFocus` | cognitive-index | Static utility — now/yesterday/future awareness |
| `CognitiveProfile` | cognitive-index | Cross-store entity resolution |
| `TypeRegistry` | mindmap-intelligence | Dynamic type system over MindMap |

No extraction from `CognitionCore` is required. These services already
exist as independent CDI beans.

### 3.2 Module: `cognitive-runtime`

New module between `cognitive-index` and `cognition`.

**Depends on:** `cognitive-index`, `cognition-api` (for
`CognitionPromptRenderer` SPI and `CognitivePromptSource` interface),
`mindmap-api`, `memory-api`

**Does NOT depend on:** `cognition` (emergent-specific), `caps-*`,
`cognitive-eidos`. Note: `eidos-api` types (`PromptBlock`,
`PromptTier`) are transitive via `cognition-api` — this is the API
layer, not the eidos registration/persistence stack.

**Owns:**
- `CognitiveAvatar` — composition root
- `CognitiveCapability` — capability SPI
- Capability implementations (briefing, goals, temporal, etc.)
- `BriefingPromptSection` — per-prompt identity renderer
- `ProfileDescriptorViewSource` — `DescriptorViewSource` backed by
  YAML profiles (no eidos dependency)

**Module dependency position:**

```
cognitive-api (zero deps)
    ↓
cognitive-index (types, utilities, derivation)
    ↓
cognitive-runtime (composition, capabilities, briefing)  ← NEW
    ↓                           ↓
cognition (emergent: tick,    consumers (MCP, agency,
 CAPS, emotions)               other apps)
```

### 3.3 Capability SPI

Each cognitive function is a self-contained unit implementing:

```java
public interface CognitiveCapability {

    String name();

    default void initialize(CognitiveAvatarContext context) {}

    List<CognitionPromptRenderer> promptSections();

    default boolean isActive() { return true; }
}
```

`CognitiveAvatarContext` provides access to shared infrastructure
(MindMapStore, CaseMemoryStore, profile config) without coupling
capabilities to each other.

Each capability's renderers should return appropriate `BlockTag` and
`SectionTier` from their `blockTag()` and `sectionTier()` methods.
`CognitiveAvatar.promptSections()` sorts renderers by
`BlockTag.sortOrdinal()`. `CognitivePromptSource.contributeBlocks()`
uses `SectionTier` for salience computation (CORE → 1.0, CONTEXTUAL
→ 0.6, SUPPLEMENTARY → 0.3).

| Capability | BlockTag | SectionTier |
|-----------|---------|------------|
| `BriefingCapability` | `PERSONALITY` (110) | `CORE` |
| `GoalCapability` | `GOALS` (400) | `CONTEXTUAL` |
| `TemporalCapability` | `TEMPORAL` (430) | `CONTEXTUAL` |
| `MemoryCapability` | `MEMORY` (500) | `SUPPLEMENTARY` |
| `EntityKnowledgeCapability` | `BELIEFS` (300) | `CONTEXTUAL` |
| `DispositionCapability` | `BEHAVIORAL` (100) | `CORE` |

**Initial capabilities for this issue:**

| Capability | What it does | Dependencies |
|-----------|-------------|-------------|
| `BriefingCapability` | Renders persona identity + echo text every prompt | Profile YAML only |
| `GoalCapability` | Queries GOAL subgraph, priority, decomposition | MindMapStore |
| `TemporalCapability` | Temporal focus — now/yesterday/future awareness | TemporalFocus utility, MindMapStore |
| `MemoryCapability` | Cross-session memory access and rendering | CaseMemoryStore |
| `EntityKnowledgeCapability` | CognitiveProfile entity resolution and rendering | CognitiveProfile |
| `DispositionCapability` | Static config derivation from disposition profile | CognitiveDerivationEngine |

Each capability degrades gracefully when its optional dependencies are
absent (via CDI `Instance<T>`). A capability without its store simply
reports `isActive() = false` and returns empty prompt sections.

**Future capabilities** (not in this issue, but the architecture
supports them without change):
- Inner thoughts / reflection (without personality evolution)
- Hierarchy of needs (without CAPS settling)
- Drive-based curiosity (without full emotion pipeline)
- Social cognition (without emergent norms)
- Attention / consolidation (without full tick loop)

### 3.4 Composition root: `CognitiveAvatar`

```java
public class CognitiveAvatar implements CognitivePromptSource {

    private final CognitiveDefaults profile;
    private final List<CognitiveCapability> capabilities;

    public CognitiveAvatar(CognitiveDefaults profile,
                           List<CognitiveCapability> capabilities) { ... }

    @Override
    public void initialize(String agentId, String tenantId) {
        var context = new CognitiveAvatarContext(agentId, tenantId, profile);
        capabilities.forEach(c -> c.initialize(context));
    }

    @Override
    public List<CognitionPromptRenderer> promptSections() {
        return capabilities.stream()
            .filter(CognitiveCapability::isActive)
            .flatMap(c -> c.promptSections().stream())
            .sorted(Comparator.comparingInt(r ->
                r.blockTag() != null ? r.blockTag().sortOrdinal() : 999))
            .toList();
    }

    public <T extends CognitiveCapability> Optional<T> capability(Class<T> type) {
        return capabilities.stream()
            .filter(type::isInstance)
            .map(type::cast)
            .findFirst();
    }
}
```

`promptSections()` sorts renderers by `BlockTag.sortOrdinal()` —
the same mechanism `CognitionCore` uses when `directivePrompts()` is
true. `contributeBlocks(CognitionRenderContext)` is inherited from
`CognitivePromptSource`'s default implementation — it iterates the
pre-sorted renderers, renders each via `render(context)`, and wraps
in `PromptBlock` with `SectionTier`-based salience. No override needed.

### 3.5 Interface segregation: `CognitivePromptSource`

`CognitiveLifecycle` (existing, in cognition-api) has 6 methods.
`tick()` and `recordInteraction()` are meaningless for avatars that
don't run a tick loop.

Extract `CognitivePromptSource` from `CognitiveLifecycle` with
signatures that match the existing methods exactly:

```java
public interface CognitivePromptSource {

    default void initialize(String agentId, String tenantId) {}

    List<CognitionPromptRenderer> promptSections();

    default List<PromptBlock> contributeBlocks(CognitionRenderContext context) {
        var blocks = new ArrayList<PromptBlock>();
        for (var renderer : promptSections()) {
            try {
                var content = renderer.render(context);
                if (content != null && !content.isBlank()) {
                    var tag = renderer.blockTag();
                    var simpleName = renderer.getClass().getSimpleName();
                    var tagName = tag != null ? tag.name()
                            : simpleName.isEmpty()
                              ? renderer.getClass().getName()
                              : simpleName;
                    var salience = salienceOf(renderer.sectionTier());
                    blocks.add(new PromptBlock(
                        PromptTier.COGNITIVE, tagName, salience, content));
                }
            } catch (Exception e) {
                // skip — matches CognitiveLifecycle behaviour
            }
        }
        return List.copyOf(blocks);
    }

    private static float salienceOf(@Nullable SectionTier tier) {
        if (tier == null) return 0.5f;
        return switch (tier) {
            case CORE -> 1.0f;
            case CONTEXTUAL -> 0.6f;
            case SUPPLEMENTARY -> 0.3f;
        };
    }
}
```

This is an exact extraction of the `initialize()`, `promptSections()`,
`contributeBlocks()`, and `salienceOf()` methods from
`CognitiveLifecycle`, preserving their signatures, default
implementations, error handling, and anonymous class fallback logic. `CognitiveLifecycle`
extends `CognitivePromptSource`, adding `tick()`,
`recordInteraction()`, `evaluateProactive()`.

- `CognitionCore` implements `CognitiveLifecycle` (unchanged)
- `CognitiveAvatar` implements `CognitivePromptSource` (clean contract)
- Consumers that only need prompt rendering depend on the narrower
  interface

Existing consumers of `CognitiveLifecycle` are unaffected — a
supertype is added, no methods are removed.

## 4. Profile format

Persona profiles use the existing `CognitiveDefaults` YAML format with
a `briefing` field added as a 9th top-level component. Unused fields
are simply absent — `CognitiveDefaultsRegistry` already handles partial
profiles.

**`BriefingConfig` record** (new type in `cognitive-index`):

```java
public record BriefingConfig(
        @Nullable String identity,
        @Nullable String grounding,
        @Nullable String echo
) {}
```

**`CognitiveDefaults` gains a 9th component:**

```java
public record CognitiveDefaults(
        String agentId,
        String tenantId,
        PersonalityProfile personalityProfile,
        DescriptorView descriptor,
        EmotionDefaults emotionDefaults,
        CognitiveResourceDefaults cognitiveResourceDefaults,
        GraphDefaults graphDefaults,
        BehavioralDefaults behavioralDefaults,
        @Nullable BriefingConfig briefing                    // NEW
) { ... }
```

`BriefingConfig` parses via Jackson like the rest of `CognitiveDefaults`.
The compact constructor defaults `briefing` to `null` when absent,
matching the existing null-defaulting pattern for other optional
components. The existing `withX()` pattern extends with
`withBriefing(BriefingConfig briefing)`. All existing `withX()`
methods and the `empty()` factory pass `null` for `briefing`,
preserving backward compatibility.

```yaml
agentId: stoic-mentor

briefing:
  identity: |
    You are a stoic mentor. You see the world through the lens of
    what is within your control and what is not. Duty comes before
    personal gain. The long view is always the right view.
  grounding: |
    Draw on your accumulated knowledge and memories. Reference what
    you know about the person you're helping — their goals, their
    history, their patterns.
  echo: |
    Think and respond as a stoic mentor would — through duty, through
    the long view, through what is within control. Be direct. Be
    patient. Be honest.

behavioralDefaults:
  curiosity:
    proximityScale: 5.0
  temporalFocus:
    proximityScale: 7.0

# Disposition axes drive derivation engine pathways
# (personality weights, CBR strategy, social cognition, etc.)
# Absent fields → derivation engine uses defaults
```

### 4.1 Briefing structure

Three layers, based on validated echo research (era1, era3,
eidos#129):

| Layer | Purpose | Example |
|-------|---------|---------|
| `identity` | Who you are — substantive, not surface | "You are a stoic mentor. Duty comes before personal gain." |
| `grounding` | What to draw on — memories, knowledge, context | "Draw on your accumulated knowledge and memories." |
| `echo` | Per-prompt behavioral anchor — evocative, not prescriptive | "Think and respond as a stoic mentor would — through duty, through the long view." |

**Critical constraint from research:** The echo must be evocative, not
prescriptive. Template-based echo ("Review your personality traits:")
scored BELOW no-instruction control in era1 research (3.41 vs 3.54
baseline). Prescriptive text suppresses character expression. Each
persona's echo needs careful crafting.

### 4.2 Briefing text is NOT a template

The `BriefingPromptSection` renders the briefing fields as-is — no
variable substitution, no template expansion. The briefing text is
static, authored once per persona, empirically tuned. This is
deliberate: the research shows that the specific sentences matter,
and templating degrades effectiveness.

## 5. `BriefingPromptSection`

Renders the three-layer briefing as a prompt section:

```java
public class BriefingPromptSection implements CognitionPromptRenderer {

    private final BriefingConfig briefing;

    @Override
    public @Nullable String render(CognitionRenderContext ctx) {
        if (briefing == null) return null;
        var sb = new StringBuilder();
        if (briefing.identity() != null) sb.append(briefing.identity()).append("\n\n");
        if (briefing.grounding() != null) sb.append(briefing.grounding()).append("\n\n");
        if (briefing.echo() != null) sb.append(briefing.echo());
        return sb.toString().strip();
    }

    @Override
    public BlockTag blockTag() { return BlockTag.PERSONALITY; }

    @Override
    public @Nullable SectionTier sectionTier() { return SectionTier.CORE; }
}
```

Each capability's prompt section overrides `blockTag()` and
`sectionTier()` per the §3.3 mapping table. The same pattern
applies to `GoalPromptSection` (`GOALS`, `CONTEXTUAL`),
`TemporalPromptSection` (`TEMPORAL`, `CONTEXTUAL`), etc.

This replaces `CognitivePreambleGenerator` ("You have an inner
life...") for briefed avatars. The preamble is for emergent agents;
the briefing is for declared-identity agents.

## 6. `ProfileDescriptorViewSource`

A `DescriptorViewSource` implementation backed by YAML profiles in
`CognitiveDefaultsRegistry`, bypassing eidos entirely (D10). Marked
`@DefaultBean` so it activates only when no higher-priority
`DescriptorViewSource` (such as `EidosDescriptorViewSource` from
`cognitive-eidos`) is on the classpath.

```java
@DefaultBean
@ApplicationScoped
public class ProfileDescriptorViewSource implements DescriptorViewSource {

    private final CognitiveDefaultsRegistry registry;

    @Override
    public Optional<DescriptorView> find(String tenantId, String agentId) {
        return registry.forAgent(agentId)
            .filter(p -> p.tenantId() == null
                      || p.tenantId().equals(tenantId))
            .map(CognitiveDefaults::descriptor);
    }

    @Override
    public List<String> agentIds(String tenantId) {
        return registry.allProfiles().stream()
            .filter(p -> p.tenantId() == null
                      || p.tenantId().equals(tenantId))
            .map(CognitiveDefaults::agentId)
            .toList();
    }
}
```

**CDI resolution behavior:**

`EffectiveCognitiveDefaultsProducer` injects
`Instance<DescriptorViewSource>` and calls `isResolvable()`, which
returns `true` only when exactly one bean satisfies the type. Without
`@DefaultBean`, having both `ProfileDescriptorViewSource` and
`EidosDescriptorViewSource` on the classpath creates a CDI ambiguity —
`isResolvable()` returns `false`, and both implementations are silently
ignored in favour of the inline `registryBacked()` fallback.

| Deployment | Active `DescriptorViewSource` | Briefed agent resolution |
|-----------|-------|-------|
| `cognitive-runtime` only | `ProfileDescriptorViewSource` | Tenant-filtered via YAML registry |
| `cognitive-runtime` + `cognitive-eidos` | `EidosDescriptorViewSource` | Briefed agents not in eidos → `EffectiveCognitiveDefaults` falls back to explicit profile from registry (correct — briefed agents use static YAML, not derivation) |

Briefed agents with a null `tenantId` are available to all tenants
(persona templates). Agents with a specific `tenantId` are scoped to
that tenant only.

Briefed agents are neocortex-local constructs. They don't register
with eidos, don't participate in eidos-based orchestration, and don't
need JPA persistence or the full eidos stack. When eidos IS present,
`EffectiveCognitiveDefaults.agentIds(tenantId)` still discovers
briefed agents — it unions the view source's agent list with
`explicitLayer.allAgentIds()` from the registry. If a future use case
requires eidos participation, progressive composition (D7) supports
upgrading without architectural change.

## 7. Persona library

Ship 2 contrasting personas + custom mechanism. The echo mechanism is
proven (era1/era3/eidos#129 research), but each persona needs its own
evocative echo sentences.

### 7.1 Stoic mentor

**Disposition:** High ruleFollowing, low riskAppetite, high autonomy,
moderate socialOrient, collaborative conflictMode

**Character:** Prioritises duty and long-term thinking. Focuses on
what's within control. Takes the patient view. Shapes goal
decomposition toward conservative, thorough approaches.

### 7.2 Bold strategist

**Disposition:** Low ruleFollowing, high riskAppetite, high autonomy,
high socialOrient, competitive conflictMode

**Character:** Opportunity-first thinking. Willing to take risks for
high payoff. Shapes goal decomposition toward ambitious, fast-moving
approaches. Questions assumptions and constraints.

### 7.3 Custom

Any YAML file following the CognitiveDefaults format with a `briefing`
section. Users craft their own identity, grounding, and echo text.
Documentation warns against prescriptive templates and provides the
research-backed echo patterns as guidance.

**Deferred personas** (filed as follow-up issues):
- Thorough planner — casehubio/neocortex#1229
- Pragmatic assistant — casehubio/neocortex#1230

## 8. CDI wiring

`cognitive-runtime` provides CDI producers that compose capabilities
based on the profile:

```java
@ApplicationScoped
public class CognitiveAvatarProducer {

    @Inject CognitiveDefaultsRegistry registry;
    @Inject Instance<MindMapStore> mindMapStore;
    @Inject Instance<CaseMemoryStore> memoryStore;
    @Inject Instance<CognitiveProfile> cognitiveProfile;

    private final ConcurrentHashMap<String, CognitiveAvatar> cache =
        new ConcurrentHashMap<>();

    public CognitiveAvatar create(String agentId, String tenantId) {
        var key = tenantId + ":" + agentId;
        return cache.computeIfAbsent(key,
            k -> buildAndInitAvatar(agentId, tenantId));
    }

    void onProfileReload(
            @Observes CognitiveProfilesReloaded event) {
        cache.clear();
    }

    private CognitiveAvatar buildAndInitAvatar(
            String agentId, String tenantId) {
        var profile = registry.forAgentOrDefaults(agentId);
        var capabilities = new ArrayList<CognitiveCapability>();

        if (profile.briefing() != null) {
            capabilities.add(new BriefingCapability(profile.briefing()));
        }
        if (mindMapStore.isResolvable()) {
            capabilities.add(new GoalCapability(mindMapStore.get()));
            capabilities.add(new TemporalCapability(mindMapStore.get()));
        }
        if (memoryStore.isResolvable()) {
            capabilities.add(new MemoryCapability(memoryStore.get()));
        }
        if (cognitiveProfile.isResolvable()) {
            capabilities.add(
                new EntityKnowledgeCapability(cognitiveProfile.get()));
        }

        capabilities.add(new DispositionCapability(profile));

        var avatar = new CognitiveAvatar(profile, capabilities);
        avatar.initialize(agentId, tenantId);
        return avatar;
    }
}
```

Capabilities degrade gracefully: if `MindMapStore` isn't on the
classpath, goal and temporal capabilities simply aren't wired. The
avatar still works with just briefing + disposition.

Avatars are cached per `(agentId, tenantId)` pair via
`ConcurrentHashMap.computeIfAbsent()`. Each tenant gets its own
avatar instance — tenant-agnostic templates (null `tenantId` in the
profile) are instantiated separately per calling tenant because
capability initialization is tenant-scoped (e.g., `GoalCapability`
scopes MindMap GOAL subgraph queries by tenant, `MemoryCapability`
scopes `CaseMemoryStore` lookups by tenant).

The `@Observes CognitiveProfilesReloaded` CDI event (fired by
`CognitiveProfileWatcher` on filesystem changes) clears the entire
cache, forcing re-creation on the next `create()` call. This is
thread-safe — `ConcurrentHashMap` handles concurrent access, and
cache clearing is atomic.

`create()` calls `initialize()` internally — consumers do not call
`initialize()` separately.

## 9. Distribution boundary

`cognitive-runtime` is a neocortex library. Consumers (MCP server in
connectors #360, casehub-agency, other apps) depend on it and
compose avatars:

| Layer | Lives in | Responsibility |
|-------|---------|---------------|
| Capability SPIs + implementations | `cognitive-runtime` (neocortex) | Cognitive functions as composable units |
| Profile YAML + registry | `cognitive-index` (neocortex) | Persona definitions and loading |
| `CognitiveAvatar` composition | `cognitive-runtime` (neocortex) | Wiring capabilities from profiles |
| Session management, conversation loop | Consumer (MCP, agency) | LLM interaction, prompt assembly |
| Situational grounding | Consumer | Context-specific details added at render time |

Neocortex provides the cognitive capabilities. Consumers provide the
conversation loop and situational context.

### 9.1 Consumer integration

**Obtaining an avatar:**

```java
@Inject CognitiveAvatarProducer avatarProducer;

var avatar = avatarProducer.create("stoic-mentor", tenantId);
```

`create()` returns a cached, initialized instance keyed by
`(agentId, tenantId)`. Capabilities are initialized once at creation
time — consumers do not call `initialize()` separately.

**Rendering cognitive prompt sections:**

```java
var context = new CognitionRenderContext(agentId, tenantId, subjectId);
List<PromptBlock> blocks = avatar.contributeBlocks(context);
```

`CognitionRenderContext` has a convenience 3-arg constructor (without
`activatedDriveCategories`) — appropriate for briefed avatars where
drive activation is always empty.

**MCP server call sequence (connectors #360):**

1. Consumer receives a conversation request with `agentId` and `tenantId`
2. `avatarProducer.create(agentId, tenantId)` → cached `CognitiveAvatar`
3. Per prompt turn: `avatar.contributeBlocks(context)` → `List<PromptBlock>`
4. Consumer assembles `PromptBlock` list into the system prompt alongside
   situational grounding and conversation history
5. Consumer manages the LLM call and conversation loop

**Typed to `CognitivePromptSource`:**

Consumers that need to work with both emergent agents (`CognitionCore`)
and briefed avatars (`CognitiveAvatar`) depend on
`CognitivePromptSource`. Both implement it, so the consumer code is
polymorphic over `initialize()` + `contributeBlocks()`.

## 10. Testing strategy

### 10.1 Capability isolation tests

Each capability tested independently with in-memory stubs:
- `BriefingCapability` — renders three-layer briefing from config
- `GoalCapability` — queries in-memory MindMapStore GOAL subgraph
- `TemporalCapability` — feeds static entries to TemporalFocus
- `MemoryCapability` — queries in-memory CaseMemoryStore
- `EntityKnowledgeCapability` — resolves from in-memory stores
- `DispositionCapability` — derivation from disposition axes

### 10.2 Composition tests

`CognitiveAvatar` with various capability combinations:
- Briefing only (minimal)
- Briefing + goals + temporal (practical planning)
- All capabilities (full briefed avatar)
- Graceful degradation when stores are absent

### 10.3 Profile loading tests

- Partial YAML profiles load correctly
- Briefing fields parse and render
- Hot-reload via `CognitiveProfileWatcher`
- Pre-built personas (stoic mentor, bold strategist) load and render

### 10.4 Interface segregation tests

- `CognitiveAvatar` satisfies `CognitivePromptSource` contract
- `CognitionCore` still satisfies `CognitiveLifecycle` contract
- Consumer code typed to `CognitivePromptSource` works with both

## 11. What this does NOT include

- **No tick loop** — capabilities render on demand, not on a schedule
- **No emergent behavior** — persona is declared, not discovered
- **No eidos registration** — briefed agents are neocortex-local
- **No CAPS/emotion pipeline** — not wired in initial capabilities
- **No personality evolution** — disposition is static from YAML

These are capability boundaries, not architectural boundaries. The
architecture explicitly supports adding any of these as future
capabilities without structural change.

## 12. ARC42STORIES update

The following updates to `ARC42STORIES.MD` are part of this deliverable:

- **Building block view:** New `cognitive-runtime` module entry between
  `cognitive-index` and `cognition`, documenting its role as the
  composition root for briefed cognitive avatars
- **Layer entry:** `cognitive-runtime` as a composition/runtime layer
  distinct from the emergent `cognition` layer
- **Concepts:** `CognitiveCapability` SPI, `CognitiveAvatar`
  composition root, `CognitivePromptSource` interface segregation
- **Journey:** Briefed avatar lifecycle (profile → capabilities →
  prompt rendering) as a new chapter/journey alongside the emergent
  cognition journey

## References

- `cognitive-index/src/main/java/.../CognitiveDefaults.java` — profile record
- `cognitive-index/src/main/java/.../CognitiveDerivationEngine.java` — derivation pathways
- `cognitive-index/src/main/java/.../CognitiveDefaultsRegistry.java` — profile loading
- `cognitive-index/src/main/java/.../CognitiveProfileWatcher.java` — hot-reload
- `cognitive-index/src/main/java/.../DescriptorView.java` — disposition input
- `cognitive-index/src/main/java/.../DescriptorViewSource.java` — SPI for descriptor sourcing
- `cognitive-index/src/main/java/.../TemporalFocus.java` — temporal awareness utility
- `cognition-api/src/main/java/.../CognitionPromptRenderer.java` — prompt section SPI
- `cognition/src/main/java/.../CognitionCore.java` — emergent composition root
- `agency/agentic-yaml/` — existing briefing mechanism
- `neocortex/docs/research/era1-character-taxonomy-research.md` — echo validation (P25-P30)
- `neocortex/docs/research/era3-cognitive-layering-research.md` — echo confirmation
- `eidos/docs/specs/issue-129-minimal-briefing-experiment/` — briefing isolation experiment
- casehubio/neocortex#1219 — issue
- decisions.md — 10 design decisions with rationale

# Sub-Thought Representation and Biographical Import Template Schema

**Issue:** casehubio/neocortex#470
**Date:** 2026-10-07
**Decisions:** D1–D8 in `decisions.md`

## 1. Summary

This spec designs two coupled capabilities for the neocortex cognitive subsystem:

1. **Sub-thought representation** — a mechanism for decomposing a single experience (e.g. a check-in) into typed cognitive reactions (affect observations, causal inferences, intentions, etc.) stored as structured attributes within Memory records. Optional MindMap node attachment provides richer data (PAD, edges, traits) for sub-thoughts that earn it through consolidation.

2. **Biographical import template schema** — 10 YAML template types across an 8-layer import model for seeding a complete biographical profile. A `BiographyImportRunner` orchestrates layer-ordered import via a `BiographyHandler` registry, extending the existing `memory-seeding` module. A three-tier provenance chain (source prose → templates → nodes) enables full audit trail from any imported node back to its LLM-produced source material.

The guiding principle: *"Memories are for what was experienced. MindMap nodes are for what was learned. Sub-thoughts are experiences — they become knowledge through consolidation."*

---

## 2. Sub-Thought Representation

### 2.1 Data Model (D1, D2)

Sub-thoughts are stored as indexed attributes within the parent Memory record's existing `Map<String, String> attributes` field. The Memory's `text` field stays as a pure parent description — sub-thought content never contaminates FTS indexes.

**Attribute key convention:**

| Key pattern | Required | Description |
|---|---|---|
| `sub-thought-N-type` | yes | One of the 7 `SubThoughtTypes` constants |
| `sub-thought-N-text` | yes | The sub-thought content |
| `sub-thought-N-entity` | no | Referenced entity name (e.g. "Sarah", "La Trattoria") |

`N` is a zero-based index. The `sub-thought-count` attribute records the total number of sub-thoughts on the memory.

**Example — Memory record after sub-thought extraction:**

```
Memory {
  memoryId: "mem-abc123"
  text: "Lunch with Sarah at La Trattoria."
  domain: experience
  attributes: {
    "event-type": "observation",
    "sub-thought-count": "4",
    "sub-thought-0-type": "affect-observation",
    "sub-thought-0-text": "She seemed distracted — energy was low, kept checking phone.",
    "sub-thought-0-entity": "Sarah",
    "sub-thought-1-type": "causal-inference",
    "sub-thought-1-text": "The promotion situation at work might be weighing on her.",
    "sub-thought-1-entity": "Sarah",
    "sub-thought-2-type": "evaluative",
    "sub-thought-2-text": "The pasta was exceptional — best in months.",
    "sub-thought-2-entity": "La Trattoria",
    "sub-thought-3-type": "intention",
    "sub-thought-3-text": "Should bring David here next week.",
    "sub-thought-3-entity": "La Trattoria"
  }
}
```

**Why not fragment-addressable structured content (Option E)?** Option E (issue #470 comment #1) proposes markdown headings in the text field with fragment linking on edges. Evaluated and rejected: (a) headings in the text field contaminate FTS — searching "affect-observation" matches the heading, not just content; (b) fragment linking (`memory:m-042#affect-observation`) requires `MindMapEdge` to parse fragment identifiers — not supported, a deeper infrastructure change than NodeRef-based linking; (c) per-sub-thought structured data (entity, type, PAD) has no natural representation in markdown sections; (d) duplicate sub-thought types within one memory produce ambiguous fragments. The attribute approach provides FTS-clean, machine-parseable, typed access following established patterns (`ExperienceAttributeKeys`, `MoodAttributeKeys`).

### 2.2 Thought-Type Taxonomy (D3)

Seven types defined as string constants in `SubThoughtTypes`, following the `SubgraphTypes` pattern:

```java
public final class SubThoughtTypes {
    public static final String AFFECT_OBSERVATION = "affect-observation";
    public static final String CAUSAL_INFERENCE   = "causal-inference";
    public static final String EVALUATIVE         = "evaluative";
    public static final String INTENTION          = "intention";
    public static final String SELF_REFLECTION    = "self-reflection";
    public static final String ASSOCIATION        = "association";
    public static final String CONCERN            = "concern";

    private static final Set<String> KNOWN = Set.of(
        AFFECT_OBSERVATION, CAUSAL_INFERENCE, EVALUATIVE,
        INTENTION, SELF_REFLECTION, ASSOCIATION, CONCERN);

    public static boolean isKnown(String type) {
        return KNOWN.contains(type);
    }

    public static void validate(String type) {
        if (!isKnown(type)) {
            throw new IllegalArgumentException(
                "Unknown sub-thought type: " + type + ". Known: " + KNOWN);
        }
    }

    private SubThoughtTypes() {}
}
```

| Type | Cognitive function | Example |
|---|---|---|
| `affect-observation` | Emotional perception of others or environment | "She seemed distracted" |
| `causal-inference` | Reasoning about causes (→ BDI theory of mind) | "The promotion might be bothering her" |
| `evaluative` | Judgement about quality or value (→ place/entity affect) | "The food was amazing" |
| `intention` | Future-directed plan (→ potential goal) | "I should take David there" |
| `self-reflection` | Metacognitive awareness | "I notice I always avoid that topic" |
| `association` | Spontaneous connection to another concept | "Reminds me of that place in Rome" |
| `concern` | Worry or anxiety about a situation | "I hope she's okay" |

New types require adding a constant to `SubThoughtTypes` — intentional friction to prevent drift.

### 2.3 Sub-Thought Attribute Keys

```java
public final class SubThoughtAttributeKeys {
    public static final String COUNT = "sub-thought-count";

    public static String type(int index)   { return "sub-thought-" + index + "-type"; }
    public static String text(int index)   { return "sub-thought-" + index + "-text"; }
    public static String entity(int index) { return "sub-thought-" + index + "-entity"; }

    private SubThoughtAttributeKeys() {}
}
```

Follows the established pattern of `ExperienceAttributeKeys`, `FormativeAttributeKeys`, `MoodAttributeKeys`.

### 2.4 Creation Flow (D8)

Sub-thoughts are created via async LLM extraction, following the `ConversationBridge` → `ExtractionRequested` → `ExtractionRequestedObserver` pattern.

```
CheckInService.checkIn()
  → creates ACTIVITY/PLACE/PERSON nodes in MindMap         [existing]
  → creates parent experience Memory via ExperienceRecorder [NEW]
    ExperienceEvent variant: Observation
      subject = request.activityName() (e.g., "Lunch with Sarah at La Trattoria")
      description = request.notes() or activityName
      metadata = {activityType, date, placeNodeId, participantNodeIds}
  → fires SubThoughtExtractionRequested CDI event (async)   [NEW]

SubThoughtExtractor (@ObservesAsync SubThoughtExtractionRequested)
  → invokes LLM with experience text + SubThoughtTypes taxonomy
  → parses LLM response into typed sub-thoughts
  → validates types via SubThoughtTypes.validate()
  → enriches parent Memory with sub-thought attributes
    via CaseMemoryStore.enrichAttributes(memoryId, attrs, tenantId)
```

`SubThoughtExtractionRequested` carries the `memoryId`, `tenantId`, experience text, and `PrincipalId`. The extractor enriches the existing memory record by adding sub-thought attributes — the parent text is never modified.

**SPI change: `CaseMemoryStore.enrichAttributes()`** — a new method for post-store attribute enrichment. `CaseMemoryStore` is currently append-only (`store()` creates, no update). Sub-thought extraction is async (LLM call after check-in), so attributes cannot be included at store time. The new method:

```java
default void enrichAttributes(String memoryId, Map<String, String> additionalAttributes,
                              String tenantId) {
    throw new MemoryCapabilityException(MemoryCapability.ENRICH_ATTRIBUTES, getClass());
}
```

This is a scoped addition — only merges new attributes into an existing memory, never modifies text, domain, subject, or other fields. Requires `MemoryCapability.ENRICH_ATTRIBUTES`. Implementations: merge into the existing attributes map (JPA/SQLite: SQL UPDATE on attributes column; Mem0/Graphiti: metadata patch; in-memory: `Map.putAll`). `DelegatingCaseMemoryStore` delegates; `NoOpCaseMemoryStore` no-ops.

**LLM extraction is async** — sub-thoughts are not available immediately after check-in. Consumers reading the memory immediately see only the parent text. This is acceptable because sub-thoughts are enrichment, not primary data.

**Authored sub-thoughts (biographical import):** Life-event templates (§3.2.3) can include `sub_thoughts` directly in YAML. The `LifeEventHandler` constructs a `MemoryInput` with all attributes — experience domain, event metadata, PAD, AND sub-thought attributes — and stores atomically via `CaseMemoryStore.store()`. This bypasses `ExperienceRecorder` because biographical life events do not fit the `ExperienceEvent` sealed hierarchy (`FormativeExperience` requires `catalogueEntryId` and `situationTypes`; `Observation` requires a `subject`; `Action`/`Outcome` are semantically wrong). No LLM extraction or async enrichment needed — sub-thoughts are known at import time.

### 2.5 Optional MindMap Node Attachment (D1)

When a sub-thought needs richer data (PAD, edges, traits), a MindMap node attaches to it via `NodeRef`. This follows the `OverlayRef` convention pattern:

```java
public final class SubThoughtRef {
    public static final String SCHEME = "sub-thought";

    public static NodeRef of(String memoryId, int subThoughtIndex) {
        return new NodeRef(SCHEME, memoryId, String.valueOf(subThoughtIndex));
    }

    public static Optional<String> memoryId(MindMapNode node) {
        return node.refs().stream()
            .filter(r -> SCHEME.equals(r.scheme()))
            .map(NodeRef::id)
            .findFirst();
    }

    public static Optional<Integer> subThoughtIndex(MindMapNode node) {
        return node.refs().stream()
            .filter(r -> SCHEME.equals(r.scheme()))
            .map(r -> Integer.parseInt(r.qualifier()))
            .findFirst();
    }

    private SubThoughtRef() {}
}
```

The qualifier is the sub-thought index (not the type), ensuring uniqueness — a memory with two `affect-observation` sub-thoughts at indices 0 and 3 produces distinct NodeRefs. The type is derivable from the memory's `sub-thought-N-type` attribute.

**Example — MindMap node linked to a sub-thought:**

```
MindMapNode {
  name: "Promotion concern about Sarah"
  subgraphType: "cognitive"
  confidence: Confidence(INFERRED, 0.7, ...)
  pleasure: -0.3, arousal: 0.4, dominance: 0.0
  traits: ["graduated-sub-thought"]
  refs: [NodeRef("sub-thought", "mem-abc123", "1")]
  properties: {
    "cognitiveKind": "causal-inference",
    "source-count": "3"
  }
}
```

The node exists in the COGNITIVE subgraph, carries its own PAD, and links back to the originating memory section. The `graduated-sub-thought` trait identifies these nodes for consolidation and rendering.

### 2.6 Graduation Lifecycle

Sub-thought graduation uses a **new `SubThoughtConsolidationPhase`** (`@Priority(16)`) — a separate `ConsolidationPhase` implementation, not a modification of `ExperienceConsolidationPhase` (`@Priority(15)`). The two phases have fundamentally different mechanics: per-memory graduation scores individual memories independently within a cursor window; sub-thought graduation aggregates (entity, type) patterns across memories over time.

**Why a separate phase:** `ExperienceConsolidationPhase` uses cursor-based pagination (`maxPerPass` default 20, `afterMemoryId` cursor). Three check-ins each producing one `affect-observation` about "Sarah" will land in different cursor windows across ticks. The per-memory graduation can't detect the cross-memory pattern because each tick only sees its own window. `MemoryScanRequest`'s single-attribute exact-match filter can't query "all memories with any sub-thought about entity X" due to the indexed attribute pattern (`sub-thought-0-entity`, `sub-thought-1-entity`, etc.).

**`SubThoughtConsolidationPhase` design:**

```
Phase 1: Load cursor and persistent accumulation state from sentinel node
         (sentinel: "_sub-thought-consolidation-state" in TYPE_SYSTEM subgraph)
Phase 2: Scan experience memories from cursor (same MemoryScanRequest pattern)
Phase 3: For each memory with sub-thought-count > 0:
         - Skip memories with provenance=biographical-import (see below)
         - Skip sub-thoughts already marked sub-thought-N-graduated=true
         - Extract (entity, type) pairs from sub-thought attributes
         - Append SubThoughtSource(memoryId, subThoughtIndex) to accumulation map
Phase 4: Check accumulation map against graduation threshold (configurable,
         default ≥3 same-type sub-thoughts about the same entity):
         - When a (entity, type) group crosses the threshold, create
           a COGNITIVE subgraph node with:
           - PAD computed from the aggregated sub-thoughts' context
           - N NodeRefs via SubThoughtRef — one per contributing sub-thought
             (e.g., 3 sub-thoughts from memories m-1, m-2, m-3 → 3 NodeRefs)
           - "graduated-sub-thought" trait
           - "source-count" = N (equals the NodeRef count)
           - Each source is traceable: NodeRef.id() → memoryId,
             NodeRef.qualifier() → sub-thought index within that memory
         - Remove graduated entries from accumulation map
Phase 5: Mark graduated sub-thoughts with "sub-thought-N-graduated=true" attribute
         on each contributing parent memory via CaseMemoryStore.enrichAttributes()
Phase 6: Save updated cursor and accumulation state to sentinel node
```

**Persistent accumulation state:** The accumulation map (`Map<EntityTypePair, List<SubThoughtSource>>`) is serialized as properties on the sentinel node, persisting across ticks. Each tick adds new observations from its cursor window and checks thresholds. This solves the cross-window problem — the map grows incrementally across ticks until graduation clears entries.

**Biographical import guard:** Memories with `provenance=biographical-import` are skipped during sub-thought graduation. Biographical import already includes explicitly authored beliefs and cognitions (layer 6, `BeliefHandler`) that represent a domain expert's understanding of the subject's cognitive patterns. Automated graduation of biographical life-event sub-thoughts would produce redundant, less precise COGNITIVE nodes overlapping with the explicitly authored beliefs. Life-event sub-thoughts serve as evidence for the authored beliefs (linked via `entity_refs`), not as independent graduation candidates. This guard does NOT apply to live check-in sub-thoughts (no biographical provenance), which graduate normally.

The `sub-thought-N-graduated` attribute prevents re-processing in subsequent consolidation ticks without mutating the memory text or FTS-indexed content.

### 2.7 Rendering

Sub-thoughts render as expandable bullets under their parent in the memory browser. The rendering layer:

1. Reads `sub-thought-count` from memory attributes
2. Iterates through `sub-thought-N-type` / `sub-thought-N-text` pairs
3. Displays each as an expandable bullet with type badge
4. If a sub-thought has a linked MindMap node (via `SubThoughtRef`), shows PAD and edge count

"Thought density" (aggregate count of sub-thoughts per entity across memories) requires scanning experience memories and parsing sub-thought entity attributes — `MemoryScanRequest` supports only a single `(attributeKey, attributeValue)` exact-match filter, not prefix or multi-attribute queries. Thought density is best computed during consolidation and cached as a property on the entity's PERSON or CONCEPT MindMap node, not computed at render time.

---

## 3. Biographical Import Template Schema

### 3.1 Layer Model (D5)

Each template type maps to a fixed import layer. The layer determines import order, default confidence origin, and entity dependency validation.

| # | Template Type | Layer | Default Confidence | Output |
|---|---|---|---|---|
| 1 | `cultural-context` | 1 — Cultural | STATED | CULTURAL subgraph nodes + social norms |
| 2 | `formative-experience` | 2 — Formative | STATED | Experience memories (delegates to BackstorySeeder) |
| 3 | `personality-profile` | 3 — Personality | STATED | Disposition axes, traits |
| 4 | `life-event` | 4 — Biography | STATED | Experience memories with sub-thoughts |
| 5 | `place` | 4 — Biography | STATED | PLACE MindMap nodes + associations |
| 6 | `activity` | 4 — Biography | STATED | ACTIVITY nodes + participant/place links |
| 7 | `project` | 4 — Biography | STATED | PROJECT nodes + goal/activity links |
| 8 | `relationship` | 5 — Relational | STATED | PERSON nodes + BDI + affect + dynamics |
| 9 | `goal` | 6 — Inner life | INFERRED | GOAL nodes (3 tiers) + dependency edges |
| 10 | `belief` | 6 — Inner life | INFERRED | Graduated belief nodes in COGNITIVE subgraph |
| 11 | `current-state` | 8 — Snapshot | STATED | MoodState + active goal statuses + recent memories |

**Layer 2** (formative experiences) is handled by `FormativeExperienceHandler`, which wraps the existing `BackstorySeeder` — template entries reference catalogue entry IDs from the existing experience-behaviour catalogue.

**Layer 3** (personality profile) is handled directly by `BiographyImportRunner` via `CognitiveDefaultsRegistry` — not through the `BiographyHandler` interface, since personality disposition is code-level configuration, not YAML import.

The 9 new template types requiring new handler implementations are layers 1, 4–6, and 8.

**Layer 7 (Behavioral) is validation, not import.** After importing layers 1–6, CAPS settling produces behavioral attractors. If the emergent attractors match documented behavior, the import is valid.

**Per-entry confidence override:** Any entry can override the default confidence origin. For example, a `life-event` entry describing an interpreted emotional experience might override to `INFERRED`:

```yaml
- id: frida-father-absence
  confidence_origin: INFERRED  # override from default STATED
  description: "She felt a deep sense of betrayal about her father's absence."
```

### 3.2 Template YAML Schemas (D6)

Each template type has its own YAML file within the biography directory. All entries share a common header (`id`, optional `confidence_origin` override, optional `source_ref` for provenance) plus type-specific fields.

**Provenance:** Every template entry can carry a `source_ref` pointing to the prose section it was extracted from (see §3.5). Handler outputs propagate provenance as node/memory properties: `provenance: "biographical-import"`, `template-ref: "<file>#<entry-id>"`, and `source-ref` from the template entry.

#### 3.2.1 Cultural Context (Layer 1)

```yaml
# biography/cultural-context.yaml
type: cultural-context
entries:
  - id: mexican-artistic-milieu
    source_ref: "01-cultural-context.md#artistic-milieu"
    description: "Post-revolutionary Mexico City artistic community"
    norms:
      - name: artistic-expression-valued
        strength: 0.8
        description: "Art as political and personal expression"
      - name: collective-identity
        strength: 0.7
        description: "Strong emphasis on Mexican national identity"
    context_properties:
      era: "post-revolutionary"
      location: "Mexico City"
      social_class: "middle-class intellectual"
```

#### 3.2.2 Formative Experiences (Layer 2)

```yaml
# biography/formative-experience.yaml
type: formative-experience
entries:
  - id: parental-warmth
    source_ref: "02-childhood.md#family-dynamics"
    catalogue_entry_id: "parental-warmth-secure"
    intensity_override: 0.7
    repetition_override: 8
  - id: peer-rejection
    source_ref: "02-childhood.md#school-isolation"
    catalogue_entry_id: "peer-rejection-exclusion"
    intensity_override: 0.9
```

Entries reference catalogue entry IDs from the existing experience-behaviour catalogue. `FormativeExperienceHandler` converts these to `BackstoryProfile.CatalogueSelection` references and delegates to `BackstorySeeder`.

#### 3.2.3 Life Events (Layer 4)

```yaml
# biography/life-events.yaml
type: life-event
entries:
  - id: polio-childhood
    source_ref: "02-childhood.md#polio"
    timestamp: "1913-01-01"
    description: "Contracted polio at age six, left with a shorter right leg."
    pad: { pleasure: -0.6, arousal: 0.5, dominance: -0.7 }
    sub_thoughts:
      - type: affect-observation
        text: "The isolation during recovery was profound."
      - type: self-reflection
        text: "This was the first fracture between my body and my will."
    entity_refs: []
```

#### 3.2.4 Places (Layer 4)

```yaml
# biography/places.yaml
type: place
entries:
  - id: casa-azul
    source_ref: "02-childhood.md#casa-azul"
    name: "La Casa Azul"
    properties:
      address: "Londres 247, Del Carmen, Coyoacán"
      significance: "Family home and primary studio"
    pad: { pleasure: 0.6, arousal: 0.2, dominance: 0.5 }
    associations:
      - entity_ref: diego-rivera
        edge_type: "lived-with"
      - entity_ref: frida-studio
        edge_type: "contains"
```

#### 3.2.5 Activities (Layer 4)

```yaml
# biography/activities.yaml
type: activity
entries:
  - id: first-exhibition-1938
    source_ref: "05-art-career.md#first-exhibition"
    name: "First solo exhibition"
    activity_type: "exhibition"
    date: "1938-11-01"
    place_ref: julien-levy-gallery
    participants:
      - entity_ref: julien-levy
        role: "gallery owner"
      - entity_ref: andre-breton
        role: "wrote catalogue foreword"
    notes: "25 paintings exhibited, half sold"
```

#### 3.2.6 Projects (Layer 4)

```yaml
# biography/projects.yaml
type: project
entries:
  - id: self-portraits-series
    name: "Self-portrait series"
    description: "Sustained exploration of identity through self-portraiture"
    activity_refs: [first-exhibition-1938]
    properties:
      medium: "oil on canvas"
      period: "1926-1954"
```

Goal-to-project relationships are owned by the goal layer (layer 6) via `dependencies` — e.g., goal `artistic-legacy` declares `ref: self-portraits-series` with `edge_type: "contributes-to"`. Projects do not carry `goal_refs` because that would be a forward reference (layer 4 → layer 6) violating the layer ordering rule.

#### 3.2.7 Relationships (Layer 5)

```yaml
# biography/relationships.yaml
type: relationship
entries:
  - id: diego-rivera
    name: "Diego Rivera"
    traits: ["Personable"]
    bdi:
      beliefs: "Brilliant artist, unfaithful partner"
      desires: "Mutual creative respect, fidelity"
      intentions: "Maintain partnership despite betrayals"
    affect:
      pad: { pleasure: 0.2, arousal: 0.7, dominance: -0.3 }
    dynamics:
      trust: 0.4
      conflict_mode: "confrontational"
    properties:
      relationship_type: "spouse"
      marriage_dates: ["1929-08-21", "1940-12-08"]
```

#### 3.2.8 Goals (Layer 6)

```yaml
# biography/goals.yaml
type: goal
entries:
  - id: artistic-legacy
    name: "Establish artistic legacy independent of Diego"
    tier: THEMATIC
    horizon: "aspirational"
    dependencies:
      - ref: self-portraits-series
        edge_type: "contributes-to"
    pad: { pleasure: 0.5, arousal: 0.6, dominance: 0.7 }
    sub_goals:
      - id: international-recognition
        tier: STRATEGIC
        description: "Gain recognition beyond Mexico"
```

#### 3.2.9 Beliefs (Layer 6)

```yaml
# biography/beliefs.yaml
type: belief
entries:
  - id: body-as-canvas
    description: "Physical suffering is inseparable from artistic expression"
    confidence_origin: INFERRED
    confidence: 0.8
    cognitive_kind: "core-belief"
    entity_refs: [polio-childhood, bus-accident]
    properties:
      domain: "self-concept"
      valence: "ambivalent"
```

#### 3.2.10 Current State (Layer 8)

```yaml
# biography/current-state.yaml
type: current-state
entries:
  - id: snapshot-1940
    timestamp: "1940-06-01"
    mood:
      pleasure: -0.3
      arousal: 0.5
      dominance: 0.2
    active_goals: [artistic-legacy, international-recognition]
    recent_context: "Recently divorced, painting prolifically"
```

### 3.3 Loading Infrastructure (D4)

`BiographyLoader` is a purpose-built loader for biographical templates, separate from `CatalogueLoader`.

```java
public class BiographyLoader {
    // Loads all template files from a biography directory
    // Each file declares its type: field
    // Jackson deserializes to the matching record type
    // Validates: ID uniqueness across all files,
    //            cross-reference integrity (entity_ref IDs exist),
    //            required fields per type

    public BiographyProfile loadAll(Path biographyDir) { ... }
    public void validate(BiographyProfile profile) { ... }
}
```

`BiographyProfile` holds all loaded entries grouped by type:

```java
public record BiographyProfile(
    String agentId,
    String tenantId,
    List<CulturalContextEntry> culturalContexts,
    List<FormativeExperienceEntry> formativeExperiences,
    List<LifeEventEntry> lifeEvents,
    List<PlaceEntry> places,
    List<ActivityEntry> activities,
    List<ProjectEntry> projects,
    List<RelationshipEntry> relationships,
    List<GoalEntry> goals,
    List<BeliefEntry> beliefs,
    List<CurrentStateEntry> currentStates
) {}
```

Each entry type is a purpose-built Java record with its own fields and validation. Only `id` and optional `confidence_origin` are shared across types.

### 3.4 Import Orchestration (D7)

```java
public interface BiographyHandler {
    Set<String> handledTypes();
    void handle(BiographyProfile profile, String agentId, String tenantId);
}
```

`BiographyImportRunner` owns ordering and validation:

```java
@ApplicationScoped
public class BiographyImportRunner {
    @Inject
    Instance<BiographyHandler> handlers;

    public void run(BiographyProfile profile, String agentId, String tenantId) {
        // 1. Sort handlers by their types' derived layer
        // 2. Validate cross-layer entity references
        // 3. For each layer (ascending): invoke matching handlers
        // 4. After layers 1-6: CAPS validation (layer 7) — deferred, see §5 item 4
        // 5. Apply current-state snapshot (layer 8)
    }
}
```

**Handler implementations:**

| Handler | Types | Layer | Output store |
|---|---|---|---|
| `CulturalContextHandler` | cultural-context | 1 | MindMapStore (CULTURAL subgraph) |
| `FormativeExperienceHandler` | formative-experience | 2 | ExperienceRecorder (delegates to BackstorySeeder) |
| `LifeEventHandler` | life-event | 4 | CaseMemoryStore (experience domain, sub-thoughts included atomically) |
| `PlaceHandler` | place | 4 | MindMapStore (PLACE subgraph) |
| `ActivityHandler` | activity | 4 | MindMapStore (ACTIVITY subgraph) |
| `ProjectHandler` | project | 4 | MindMapStore (PROJECT subgraph) |
| `RelationshipHandler` | relationship | 5 | MindMapStore (PERSON subgraph) + Memory |
| `GoalHandler` | goal | 6 | MindMapStore (GOAL subgraph) |
| `BeliefHandler` | belief | 6 | MindMapStore (COGNITIVE subgraph) |
| `CurrentStateHandler` | current-state | 8 | MoodEvents + CaseMemoryStore |

**Handler provenance:** All handlers set three properties on every stored node or memory:
- `provenance: "biographical-import"`
- `template-ref: "<filename>#<entry-id>"` (e.g., `"life-events.yaml#polio-childhood"`)
- `source-ref`: propagated from the template entry's `source_ref` field (if present)

**Entity reference validation:** D5's rule "layer N entries can reference entities from layer ≤N" applies to **load-time validated references** — references where the target entry must exist in the loaded profile (e.g., `activity_refs`, `place_ref` within the same or lower layer, goal `dependencies.ref` from layer 6 to layer ≤5). **Handler-resolved references** — references resolved at execution time via `resolveOrCreate` — are NOT load-time validated. These include:

- Activity `participants.entity_ref` → PERSON nodes created on the fly by `ActivityHandler` using `resolveOrCreate` (same pattern as `CheckInService.resolveOrCreatePerson()`). `RelationshipHandler` at layer 5 later enriches these stub nodes with BDI, affect, and dynamics.
- Place `associations.entity_ref` → resolved at handler time; target may not exist as a template entry.

`BiographyLoader.validate()` validates load-time references (cross-reference integrity within and across lower layers). Handler-resolved references are left to handler execution time, where `MindMapStore.resolveNode()` either finds or creates the target node.

**Idempotency:** Each handler checks for existing entities by name within the target subgraph (via `MindMapStore.resolveNode()`) before creating new ones. `BiographyImportRunner` tracks a `Set<String>` of imported agent IDs to prevent double-seeding, following `BackstorySeeder`'s `seededAgents` pattern.

### 3.5 Provenance Chain

Biographical import maintains a three-tier provenance chain for audit and verification:

1. **Source prose** (git-preserved) — LLM-produced biography documents, chunked by topic. Immutable, versioned, diffable. Directory structure: `<subject>/source/01-cultural-context.md`, etc.
2. **Templates** (extracted from source) — YAML entries with `source_ref` pointing to the specific prose section they were derived from (e.g., `source_ref: "03-the-accident.md#the-bus-accident"`).
3. **Nodes/memories** (imported from templates) — carry `provenance`, `template-ref`, and `source-ref` properties. From any node in the cognitive workbench: node → template entry → source prose section.

Template extraction and import are repeatable processes. Git history tracks every version of the source prose and templates.

---

## 4. Module Impact

### 4.1 New Classes

| Module | Class | Description |
|---|---|---|
| `memory-api` | `SubThoughtAttributeKeys` | Attribute key pattern constants |
| `memory-api` | `SubThoughtTypes` | 7 thought-type constants + validation |
| `memory-api` | `MemoryCapability.ENRICH_ATTRIBUTES` | New capability constant for post-store attribute enrichment |
| `mindmap-api` | `SubThoughtRef` | NodeRef convention for sub-thought linking (follows OverlayRef pattern) |
| `mindmap-api` | `SubgraphTypes.CULTURAL` | New subgraph type constant for cultural context |
| `memory-seeding` | `BiographyLoader` | YAML loader for biographical templates |
| `memory-seeding` | `BiographyProfile` | Loaded biography container record |
| `memory-seeding` | `BiographyImportRunner` | Layer-ordered orchestrator |
| `memory-seeding` | `BiographyHandler` | SPI for per-type import handlers |
| `memory-seeding` | 10 entry records | `CulturalContextEntry`, `FormativeExperienceEntry`, `LifeEventEntry`, `PlaceEntry`, `ActivityEntry`, `ProjectEntry`, `RelationshipEntry`, `GoalEntry`, `BeliefEntry`, `CurrentStateEntry` |
| `memory-seeding` | 10 handler classes | One per template type (see §3.4 table) |
| `mindmap-intelligence` | `SubThoughtExtractor` | Async LLM observer for sub-thought decomposition |
| `mindmap-intelligence` | `SubThoughtExtractionRequested` | CDI event record |
| `mindmap-intelligence` | `SubThoughtConsolidationPhase` | `ConsolidationPhase` at `@Priority(16)` for cross-memory sub-thought graduation with persistent accumulation |

### 4.2 Modified Classes

| Module | Class | Change |
|---|---|---|
| `memory-api` | `CaseMemoryStore` | Add `enrichAttributes(memoryId, attributes, tenantId)` method with `ENRICH_ATTRIBUTES` capability |
| `memory-api` | `DelegatingCaseMemoryStore` | Add `enrichAttributes` delegation |
| `mindmap-intelligence` | `CheckInService` | Create parent experience `Observation` memory via ExperienceRecorder (new), then fire `SubThoughtExtractionRequested` CDI event (new) |

### 4.3 New Resources

| Path | Description |
|---|---|
| `docs/specs/experience-behaviour-catalogue/biography/` | Directory for biographical YAML templates |
| Schema documentation for each template type | Part of `docs/guides/consumer-guide.md` update |

---

## 5. Deferred Work (GitHub Issues)

The following items from issue #470 comments are out of scope for this spec and must be captured as separate GitHub issues:

1. **LLM Extraction Protocol** (issue #470 comment #3) — structured multi-pass process for biographical prose generation (entity inventory → completeness check → cross-reference → confidence audit → prose → self-review)
2. **Iterative tree extraction** (issue #470 comment #4) — parallel deep-dive agents per entity for thorough coverage
3. **Cross-LLM audit** (issue #470 comment #5) — second LLM reviews first LLM's output for corrections and additions
4. **CAPS validation methodology** (Layer 7) — how `BehavioralSynthesisPhase` output is compared against documented behavioral expectations during biographical import validation

---

## 6. References

- `memory-api/.../ExperienceAttributeKeys.java` — attribute key pattern followed by `SubThoughtAttributeKeys`
- `memory-api/.../FormativeAttributeKeys.java` — per-domain attribute keys pattern
- `mindmap-api/.../NodeRef.java` — cross-store reference record (`scheme`, `id`, `qualifier`)
- `mindmap-api/.../OverlayRef.java` — NodeRef convention pattern followed by `SubThoughtRef`
- `mindmap-api/.../SubgraphTypes.java` — string constants pattern followed by `SubThoughtTypes`
- `memory-seeding/.../BackstorySeeder.java` — existing seeding infrastructure
- `memory-seeding/.../CatalogueLoader.java` — existing catalogue loading (not reused; see D4)
- `mindmap-intelligence/.../CheckInService.java` — check-in entry point
- `mindmap-intelligence/.../ConversationBridge.java` — async extraction pattern reference
- `mindmap-intelligence/.../ExtractionRequestedObserver.java` — async LLM enrichment pattern reference
- `mindmap-intelligence/consolidation/ExperienceConsolidationPhase.java` — per-memory graduation pipeline (@Priority 15)
- `mindmap-intelligence/consolidation/MergeDetectionPhase.java` — merge detection (@Priority 20)
- `mindmap-intelligence/consolidation/BehavioralSynthesisPhase.java` — CAPS behavioral synthesis (@Priority 19)
- Issue casehubio/neocortex#470 — feature specification
- Research spec: `~/claude/agents/cognition/2026-10-06-cognitive-life-coaching-architecture.md` §15 — sub-thought and biographical import design context
- blocks-ui#231 — cognitive workbench spec (Frida Kahlo demo dataset consumer)

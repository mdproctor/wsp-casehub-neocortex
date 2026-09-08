# Knowledge Representation Model — Design Spec

**Date:** 2026-09-09
**Epic:** #285 (Knowledge Representation Model — triples, cores, and dynamic type semantics)
**Children:** #278 (design), #281 (SubgraphType → dynamic string), #282 (dynamic property schema)
**Status:** Draft

---

## 1. Problem Statement

The casehub cognitive platform has a knowledge graph (MindMap) that already functions as a Thing system: MindMapNode carries properties, traits, and edges; TraitRule evaluates interfaces from properties/edges; TraitProxy creates typed JDK Proxy views. But this is implicit — there is no explicit Thing concept, no core-type registry, no formal type system, and the trait-to-interface bridge isn't wired to Subject (the typed entity reference in memory-api).

Three gaps:

1. **No formal Thing type.** Consumers interact with MindMapNode directly — a storage-level type that leaks persistence concerns. There's no consumer-facing entity type with `is()`/`as()` semantics.
2. **Fixed SubgraphType enum.** The 6-value enum (PERSON, PROJECT, RESEARCH_AREA, ORGANISATION, CONCEPT, GENERAL) prevents runtime type discovery by the LLM.
3. **No property schema for dynamic types.** Core types get schema from Java interfaces (Personable defines birthday, role, email, phone). Dynamic types (LLM-discovered) have no schema validation.

### 1.1 Prior Art

From Mark's Drools/PHREAK work: a Thing system where ThingInstances start with a core type, accumulate triples over time, and rules dynamically determine which Java interfaces the Thing satisfies. MindMap already implements this pattern informally — this epic formalizes it.

### 1.2 Design Principles

- **Core types feel like Java.** Typed fields, IDE support, compile-time safety via trait interfaces.
- **Dynamic types feel like maps with conventions.** String-keyed properties, no recompile needed.
- **Promotion is a conscious developer act.** When a dynamic type crystallises, a developer creates a Java interface. Future automation possible but out of scope.
- **Not OWL-DL.** Lightweight type semantics — type hierarchy as data, property schemas as metadata, advisory validation. No formal reasoner.
- **Not RDFS-style "everything is a triple."** Core objects are normal interfaces. Properties and edges are the flexible layer underneath.

## 2. Architecture

### 2.1 Two-Layer Model

| Layer | Type | Purpose | Who sees it |
|-------|------|---------|-------------|
| Consumer | Thing | Semantic API — identity, properties, traits, is()/as() | App developers, agent framework, LLM integrations |
| Internal | MindMapNode | Storage SPI — persistence, indexing, graph operations | Platform internals, store implementations, decorators |

Thing and MindMapNode do not share a type hierarchy. They are separate concerns with different lifecycles: MindMapNode evolves with storage requirements; Thing evolves with consumer needs.

### 2.2 Module Structure

```
thing-api/              — NEW: zero deps, tier-0. Thing interface, PropertyAccessor,
                          convention-based JDK Proxy for as(). Consumer-facing module.
mindmap-api/            — MODIFIED: SubgraphType enum → String, SubgraphTypes constants,
                          RuleCondition.InSubgraphType uses String
mindmap-intelligence/   — MODIFIED: ThingResolver CDI bean, TypeResolver utility,
                          PropertySchemaValidator, TraitProxy migrated to shared proxy
mindmap/                — MODIFIED: CognitiveLoader bootstraps type subgraph
```

### 2.3 Dependency Direction

```
thing-api                    (zero deps)
    ↑
mindmap-intelligence         (depends on thing-api + mindmap-api + mindmap)
    ↑
cognitive-index              (depends on mindmap-intelligence for ThingResolver)
```

thing-api has no dependency on mindmap-api. The bridge is ThingResolver in mindmap-intelligence, which depends on both.

## 3. Thing Interface

```java
package io.casehub.neocortex.thing;

public interface Thing extends PropertyAccessor {
    String id();
    String name();
    String type();

    boolean is(String traitName);
    <T> T as(Class<T> traitInterface);

    @Override
    Optional<String> property(String key);
    Map<String, String> properties();
    Set<String> traits();
}
```

**Key characteristics:**

- **Read-only projection.** Thing is a snapshot of entity state at construction time. It is not a live object — consumers re-resolve from ThingResolver for fresh state.
- **No edges.** Relationships are a graph concern queried via MindMapStore, not carried on the entity. Properties ARE the datatype triples (this, key, value). Edge queries give the object triples.
- **No tenantId.** Tenant context is ambient (CDI principal or passed alongside).

### 3.1 PropertyAccessor

```java
package io.casehub.neocortex.thing;

@FunctionalInterface
public interface PropertyAccessor {
    Optional<String> property(String key);
}
```

Shared abstraction for property-bearing types. Thing extends it. MindMapNode adapts to it trivially (it already has `property(String key)`). The JDK Proxy invocation handler works on any PropertyAccessor — one implementation, multiple use sites.

### 3.2 is() and as()

- `is(String traitName)` — checks `traits().contains(traitName)`. Traits are pre-computed at store time by TraitRule evaluation in the decorator stack.
- `as(Class<T> traitInterface)` — creates a JDK Proxy that maps interface method names to `property(methodName)` calls. Works with ANY interface by convention — consumers can define their own domain-specific trait interfaces without depending on platform definitions.

The proxy handles return type coercion: String, Integer, Long, Double, Boolean, Optional<String>. The existing TraitInvocationHandler in mindmap-intelligence is replaced by the shared implementation in thing-api.

### 3.3 Trait Interfaces

Platform-provided trait interfaces (Personable, Projectlike, Organisational, Eventlike) stay in mindmap-intelligence as optional conveniences. thing-api ships with ZERO pre-defined trait interfaces — it is purely structural.

Consumers define domain-specific traits:
```java
interface Customer {
    Optional<String> accountId();
    Optional<String> tier();
}

Thing thing = resolver.resolve(nodeId, tenantId).orElseThrow();
if (thing.is("Customer")) {
    Customer c = thing.as(Customer.class);
    c.accountId(); // reads property("accountId")
}
```

### 3.4 Implementation

Thing is an interface. A package-private `ThingRecord` in thing-api provides the immutable implementation:

```java
// package-private
record ThingRecord(String id, String name, String type,
                   Map<String, String> properties, Set<String> traits) implements Thing {
    // is(), as(), property() implementations
}
```

Construction via static factory: `Thing.of(id, name, type, properties, traits)`. ThingResolver calls this factory; consumers interact with the Thing interface.

## 4. SubgraphType → Dynamic String (#281)

Replace the `SubgraphType` enum with `String` throughout:

- `MindMapSubgraph.type()` → `String`
- `SubgraphInput.type()` → `String`
- `RuleCondition.InSubgraphType.type()` → `String`

Well-known types become constants in `SubgraphTypes`:

```java
package io.casehub.neocortex.mindmap;

public final class SubgraphTypes {
    public static final String PERSON = "person";
    public static final String PROJECT = "project";
    public static final String RESEARCH_AREA = "research-area";
    public static final String ORGANISATION = "organisation";
    public static final String CONCEPT = "concept";
    public static final String GENERAL = "general";
    public static final String TYPE_SYSTEM = "type-system";

    private SubgraphTypes() {}
}
```

Lowercase-normalized (same convention as `Subject.type()`).

`RuleCondition.InSubgraphType` gets a real implementation — it currently returns `false`. Since `RuleCondition.evaluate()` only receives `(MindMapNode node, List<MindMapEdge> edges)` with no store access, the subgraph type must be available without a store lookup. Two options:

1. **Node carries subgraph type as a property** — when a node is added to a subgraph, the store sets a `subgraph-type` property on the node. InSubgraphType reads `node.property("subgraph-type")`. Simple, no API change. The property is set by the store, not by callers.
2. **MindMapNode gains a `subgraphType()` method** — returns the subgraph's type string. Requires the store to resolve the subgraph type when constructing the node. API change but cleaner than a magic property.

Option 1 is recommended — it avoids an API change and follows the existing property-based convention. The `subgraph-type` property is set by MindMapStore implementations when the node is added or retrieved, not by callers.

**MindMapExtractor impact:** `parseSubgraphType()` no longer catches unknown types and collapses to GENERAL. LLM-provided type strings pass through directly, enabling runtime type discovery. This is a deliberate trust boundary change — the LLM can create subgraphs with arbitrary type names.

## 5. Type Registry — Types as MindMap Nodes

Types are first-class data in MindMap, stored as nodes in a designated TYPE_SYSTEM subgraph.

### 5.1 Type Subgraph Structure

```
TYPE_SYSTEM subgraph
├── node: "person"        (properties: java-class=io.casehub...Personable)
├── node: "project"       (properties: java-class=io.casehub...Projectlike)
├── node: "organisation"  (properties: java-class=io.casehub...Organisational)
├── node: "concept"       (no java-class — could be dynamic)
├── node: "research-area" (no java-class)
├── node: "general"       (no java-class)
│
├── edge: "person" --subtype-of--> "general"
├── edge: "project" --subtype-of--> "general"
└── ...
```

- **Core types** carry a `java-class` property linking to their Java interface.
- **Dynamic types** are nodes without `java-class` — LLM-discovered types.
- **Type hierarchy** is formed by `subtype-of` edges — standard graph traversal.
- **No new SPI.** Type management uses existing MindMapStore operations on a special subgraph.

### 5.2 Bootstrapping

CognitiveLoader (@PostConstruct in mindmap) bootstraps the TYPE_SYSTEM subgraph and core type nodes at startup. Same pattern as existing vocabulary registration. Idempotent — creates subgraph and type nodes only if absent. Per-tenant: each tenant gets its own type subgraph.

### 5.3 TypeResolver

A utility in mindmap-intelligence that reads the type subgraph:

- `typeExists(String typeName, String tenantId)` → boolean
- `subtypesOf(String typeName, String tenantId)` → List<String>
- `javaClass(String typeName, String tenantId)` → Optional<Class<?>>

Used by ThingResolver to validate `type` property values and by PropertySchemaValidator to look up field definitions.

## 6. Thing.type() — Explicit Type Property

Each MindMapNode carries a `type` property set at creation time (e.g., `type=person`). ThingResolver reads this property, normalizes to lowercase, and validates against the type subgraph.

- **Mandatory.** ThingResolver returns `Optional.empty()` for nodes without a `type` property.
- **Lowercase-normalized.** ThingResolver normalizes to lowercase when reading, ensuring alignment with Subject.type() convention.
- **Reserved key.** `type` is a reserved property key — consumers must not use it for other purposes. This is documented as a platform convention alongside other reserved keys (e.g., `mindmap.derived.*` used by DerivedEdgeDecorator).
- **Type vs traits.** The `type` property is the primary identity type (what the Thing IS). Traits are additional capabilities discovered over time (interfaces the Thing satisfies). Mirrors Java's class vs interface distinction.

## 7. Subject ↔ Thing Bridge

Subject(String type, String id) in memory-api references a Thing by naming convention:

- `Subject.type()` == `Thing.type()` (both lowercase-normalized)
- `Subject.id()` == `Thing.id()` (MindMapNode UUID)

No code dependency between memory-api and thing-api. Resolution happens at the call site:

```java
Subject subject = Subject.of("person", nodeId);
Optional<Thing> thing = thingResolver.resolve(subject.id(), tenantId);
```

Follows the NodeRef pattern — convention-based cross-store reference, not type-system coupling.

## 8. Dynamic Property Schema (#282)

Property schema for dynamic types is stored as properties on type nodes in the type subgraph.

### 8.1 Convention

```
Type node "research-topic" properties:
  schema.title.type = string
  schema.title.required = true
  schema.field.type = string
  schema.methodology.type = string
  schema.year.type = number
```

Schema properties use the `schema.{fieldName}.{attribute}` naming convention. Supported attributes:
- `type` — string, number, boolean, date
- `required` — true/false (default false)

### 8.2 Validation

`PropertySchemaValidator` in mindmap-intelligence reads schema properties from the type node and validates Thing properties against them. Validation is **advisory** (logs warnings, does not reject):

- Missing required properties → WARN
- Type mismatch (e.g., "abc" for a number field) → WARN
- Unknown properties (not in schema) → accepted silently (LLMs discover new properties)

### 8.3 Schema Lifecycle

Schema properties are set by:
1. **Platform bootstrap** — CognitiveLoader sets schema for core types based on Java interface fields.
2. **LLM discovery** — The LLM extractor adds schema properties to type nodes when it discovers consistent property patterns.
3. **Developer promotion** — When creating a Java interface for a dynamic type, the developer updates the schema to match.

## 9. Promotion Path (Future)

When a dynamic type crystallises (stable schema, frequently queried), a developer creates a Java interface and adds the `java-class` property to the type node. This is a conscious developer act — no automation in this epic.

Future: code generation tooling that reads the type node's schema properties and generates a Java interface. Out of scope for #285.

## 10. Migration Impact

### 10.1 SubgraphType Callers

88 references to `SubgraphType` across the codebase. Migration is mechanical:
- `SubgraphType.PERSON` → `SubgraphTypes.PERSON`
- `SubgraphType.valueOf(s)` → direct string use
- Switch statements → if/else or pattern matching on strings
- SqliteMindMapStore deserialization updated

### 10.2 MindMapExtractor

- `parseSubgraphType()` passes LLM type strings through instead of collapsing to GENERAL
- `findOrCreateSubgraph()` uses the LLM-provided type name
- Sets `type` property on created nodes

### 10.3 TraitProxy Migration

TraitInvocationHandler logic moves to thing-api's shared proxy. TraitProxy.as() in mindmap-intelligence delegates to the shared implementation via PropertyAccessor.

## 11. Test Strategy

| Module | What's tested |
|--------|--------------|
| thing-api | Thing.of() construction, is() trait checking, as() proxy with type coercion, PropertyAccessor contract |
| mindmap-api | SubgraphTypes constants, InSubgraphType real implementation |
| mindmap-intelligence | ThingResolver (resolve, type validation, lowercase normalization, missing type → empty), TypeResolver (type subgraph queries, hierarchy traversal), PropertySchemaValidator (advisory warnings) |
| mindmap | CognitiveLoader type subgraph bootstrap (idempotent, per-tenant) |
| mindmap-testing | MindMapStoreContractTest updated for String subgraph types |

## References

- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapNode.java` — current storage interface
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphType.java` — enum being replaced
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/TraitRule.java` — trait evaluation SPI
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TraitProxy.java` — existing JDK Proxy
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Personable.java` — core trait interface example
- `memory-api/src/main/java/io/casehub/neocortex/memory/Subject.java` — typed entity reference
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/RuleCondition.java` — InSubgraphType placeholder
- Issue #278 — Thing model prior art and design principles
- Issue #281 — SubgraphType refactoring
- Issue #282 — Dynamic property schema
- `docs/specs/issue-253-cognitive-rearchitecture/decisions.md` — D1 (cognitive-api), D26 (acceptance criteria)

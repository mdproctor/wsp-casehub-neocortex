# Knowledge Representation Model — Design Spec

**Date:** 2026-09-09
**Epic:** #285 (Knowledge Representation Model — triples, cores, and dynamic type semantics)
**Children:** #278 (design), #281 (SubgraphType → dynamic string), #282 (dynamic property schema)
**Status:** Final

---

## 1. Problem Statement

The casehub cognitive platform has a knowledge graph (MindMap) that already functions as a Thing system: MindMapNode carries properties, traits, and edges; TraitRule evaluates interfaces from properties/edges; TraitProxy creates typed JDK Proxy views. But this is implicit — there is no formal Thing concept, no `is()`/`as()` API, no core-type registry, and the trait-to-interface bridge isn't wired to Subject (the typed entity reference in memory-api).

Three gaps:

1. **No formal Thing type.** The knowledge representation base concept exists informally but has no interface. Consumers must know about TraitProxy, call `traits().contains()` manually, and depend on the full MindMapNode with its cognitive features (confidence, PAD, provenance) even when they only want identity, properties, and traits.
2. **Fixed SubgraphType enum.** The 6-value enum (PERSON, PROJECT, RESEARCH_AREA, ORGANISATION, CONCEPT, GENERAL) prevents runtime type discovery by the LLM.
3. **No property schema for dynamic types.** Core types get schema from Java interfaces (Personable defines birthday, role, email, phone). Dynamic types (LLM-discovered) have no schema definition.

### 1.1 Prior Art

From Mark's Drools/PHREAK work: a Thing system where ThingInstances start with a core type, accumulate triples (properties) over time, and rules dynamically determine which Java interfaces the Thing satisfies. MindMap already implements this pattern informally — this epic formalizes it.

### 1.2 Design Principles

- **Core types feel like Java.** Typed fields, IDE support, compile-time safety via trait interfaces.
- **Dynamic types feel like maps with conventions.** String-keyed properties, no recompile needed.
- **Promotion is a conscious developer act.** When a dynamic type crystallises, a developer creates a Java interface. Future automation possible but out of scope.
- **Not OWL-DL.** Lightweight type semantics — type hierarchy as data, property schemas as metadata, advisory validation. No formal reasoner.
- **Not RDFS-style "everything is a triple."** Core objects are normal interfaces. Properties and edges are the flexible layer underneath.

## 2. Architecture

### 2.1 Base Interface Hierarchy — Content vs Cognition

```
Thing (interface, thing-api, zero deps)
  — id(), name(), type(), property(), properties(), traits()
  — is(), as()  [default methods]

    └── MindMapNode (interface, mindmap-api, extends Thing)
        — confidence(), PAD, temporal bounds, provenance
        — principalId(), sharedWith(), refs()
        — subgraphId(), subgraphType()
```

**Thing** is the semantic knowledge representation base. Identity, properties, traits, and type — what something IS. Every entity in the knowledge graph is a Thing.

**MindMapNode** extends Thing with cognitive features — what the agent BELIEVES about the entity. Epistemic certainty (confidence), emotional assessment (PAD), temporal validity, provenance, visibility controls.

All MindMapNodes are Things. Content nodes (notes, links) and semantic entities (persons, projects) are both Things — they differ by type and richness of properties/traits.

### 2.2 Dependency Direction

```
thing-api              (zero deps)
    ↑
mindmap-api            (depends on thing-api + cognitive-api + platform-api)
    ↑
mindmap-intelligence   (depends on mindmap-api, TypeRegistry CDI bean)
    ↑
cognitive-index        (depends on mindmap-intelligence)
```

Consumers who want semantic knowledge representation depend on thing-api only (zero deps). Cognitive system components depend on mindmap-api for the full picture.

### 2.3 Module Changes

```
thing-api/              — NEW: zero deps, tier-0. Thing interface,
                          JDK Proxy handler for as()
mindmap-api/            — MODIFIED: MindMapNode extends Thing,
                          SubgraphType enum → String + SubgraphTypes constants,
                          MindMapNode gains subgraphType(),
                          RuleCondition.InSubgraphType uses String
mindmap-intelligence/   — MODIFIED: TypeRegistry CDI bean,
                          TraitProxy.as() deprecated (delegates to Thing.as())
mindmap/                — MODIFIED: CognitiveLoader delegates type bootstrap
                          to TypeRegistry, store implementations resolve
                          subgraphType() on nodes
```

## 3. Thing Interface

```java
package io.casehub.neocortex.thing;

import java.util.Map;
import java.util.Optional;
import java.util.Set;

public interface Thing {

    String id();
    String name();
    String type();

    Optional<String> property(String key);
    Map<String, String> properties();

    Set<String> traits();

    default boolean is(String traitName) {
        return traits().contains(traitName);
    }

    default <T> T as(Class<T> traitInterface) {
        if (!traitInterface.isInterface()) {
            throw new IllegalArgumentException(
                "Trait must be an interface: " + traitInterface.getName());
        }
        return ThingProxyHandler.createProxy(this, traitInterface);
    }
}
```

### 3.1 Key Characteristics

- **Read-only projection.** Thing is a snapshot of entity state. Consumers re-query MindMapStore for fresh state.
- **No edges.** Relationships are a graph concern queried via MindMapStore. Properties ARE the datatype triples (this, key, value). Edge queries give the object triples.
- **No tenantId.** Tenant context is ambient (CDI principal or passed alongside).
- **type() returns the subgraph type** — the entity's primary identity type. A node in a "person" subgraph has type "person". A note in a "general" subgraph has type "general".

### 3.2 ThingProxyHandler

Package-private class in thing-api. Maps interface method names to `thing.property(methodName)` calls with return type coercion:

| Return type | Coercion |
|-------------|----------|
| String | property value as-is |
| Optional\<String\> | Optional.ofNullable(property value) |
| Integer / int | Integer.parseInt |
| Long / long | Long.parseLong |
| Double / double | Double.parseDouble |
| Boolean / boolean | Boolean.parseBoolean |

Returns null for missing properties on non-Optional return types. Handles toString (node id + trait class), hashCode (node id hash), equals (same node id + same trait class).

This consolidates the existing TraitInvocationHandler from mindmap-intelligence (51 lines of type coercion logic) into thing-api. Boolean coercion is new — an enhancement over the existing handler.

### 3.3 Trait Interfaces

Platform-provided trait interfaces (Personable, Projectlike, Organisational, Eventlike) remain in mindmap-intelligence as optional conveniences.

Consumers define domain-specific traits — `as()` works with ANY interface by convention:

```java
interface Customer {
    Optional<String> accountId();
    Optional<String> tier();
}

MindMapNode node = store.getNode(nodeId, tenantId);
Thing thing = node; // widening — MindMapNode IS a Thing
if (thing.is("Customer")) {
    Customer c = thing.as(Customer.class);
    c.accountId(); // reads property("accountId")
}
```

### 3.4 TraitProxy Migration

The existing `TraitProxy.as()` in mindmap-intelligence delegates to `Thing.as()`:

```java
@Deprecated
public static <T> T as(MindMapNode node, Class<T> traitInterface) {
    return node.as(traitInterface); // MindMapNode inherits as() from Thing
}
```

Existing callers migrate at their own pace. No breaking change.

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

### 4.1 MindMapNode.subgraphType()

New method on MindMapNode:

```java
String subgraphType();
```

Returns the subgraph's type string for this node. Resolved by the store when constructing the node — the store already has `subgraphId()` and can resolve the subgraph's type via a join or cache lookup.

This is preferred over a magic `subgraph-type` property because:
- Type-safe and discoverable on the MindMapNode interface
- Cannot be overwritten by callers via NodeUpdate
- No consistency burden — value comes from the subgraph, not a copied property
- The store already resolves subgraph-dependent data during node construction

### 4.2 InSubgraphType Implementation

```java
record InSubgraphType(String type) implements RuleCondition {
    @Override
    public boolean evaluate(MindMapNode node, List<MindMapEdge> edges) {
        return type.equals(node.subgraphType());
    }
}
```

Currently returns `false` — this gives it a real implementation.

### 4.3 Thing.type() Derivation

`Thing.type()` returns the same value as `MindMapNode.subgraphType()`. Since Thing is an interface with no default for `type()`, the MindMapNode implementations (InMemoryMindMapNode, SqliteMindMapNode) provide it by returning the resolved subgraph type.

After SubgraphType → String, the subgraph type IS the entity type. No separate `type` property needed — no consistency problem between two sources of truth.

### 4.4 MindMapExtractor Impact

`parseSubgraphType()` passes LLM type strings through directly instead of collapsing unknown types to GENERAL. This enables runtime type discovery — the LLM can create entities with any type.

### 4.5 SQLite Data Migration

The SQLite `mindmap_subgraph` table stores type as the enum name (e.g., "PERSON"). A Flyway migration converts to lowercase strings ("person"). Store implementations updated to read/write strings.

## 5. Type Registry — Types as MindMap Nodes

Types are first-class data in MindMap, stored as nodes in a designated TYPE_SYSTEM subgraph. All access is mediated through a TypeRegistry CDI bean.

### 5.1 Type Subgraph Structure

```
TYPE_SYSTEM subgraph
├── node: "person"        (properties: java-class=io.casehub...Personable)
├── node: "project"       (properties: java-class=io.casehub...Projectlike)
├── node: "organisation"  (properties: java-class=io.casehub...Organisational)
├── node: "concept"       (no java-class — dynamic type)
├── node: "general"       (no java-class)
│
├── edge: "person" --subtype-of--> "general"
├── edge: "project" --subtype-of--> "general"
└── ...
```

- **Core types** carry a `java-class` property linking to their Java interface.
- **Dynamic types** are nodes without `java-class` — LLM-discovered types.
- **Type hierarchy** is formed by `subtype-of` edges — graph traversal.

Edge isolation: `MindMapStore.neighbors()` is node-scoped. Type hierarchy edges are between type nodes in the TYPE_SYSTEM subgraph — they never appear in instance node queries. Querying neighbors of "Alice" returns Alice's domain edges, not type hierarchy edges.

### 5.2 TypeRegistry

`@ApplicationScoped` CDI bean in mindmap-intelligence. Mediates all type operations:

```java
public class TypeRegistry {
    boolean typeExists(String typeName, String tenantId);
    List<String> subtypesOf(String typeName, String tenantId);
    Optional<Class<?>> javaClass(String typeName, String tenantId);
    Map<String, SchemaField> schemaFor(String typeName, String tenantId);
    void registerType(String typeName, String tenantId);
    void registerType(String typeName, String parentType, String tenantId);
}
```

Uses `Instance<MindMapStore>` for graceful degradation.

### 5.3 Bootstrapping

CognitiveLoader delegates to TypeRegistry at `@PostConstruct`. TypeRegistry creates the TYPE_SYSTEM subgraph and core type nodes if absent. Idempotent — safe on every startup. Per-tenant: each tenant gets its own type subgraph.

## 6. Subject ↔ Thing Bridge

Subject(String type, String id) in memory-api references a Thing by naming convention:

- `Subject.type()` == `Thing.type()` (both lowercase-normalized)
- `Subject.id()` == `Thing.id()` (MindMapNode UUID)

No code dependency between memory-api and thing-api. Resolution at the call site:

```java
Subject subject = Subject.of("person", nodeId);
MindMapNode node = store.getNode(subject.id(), tenantId);
Thing thing = node; // widening
assert thing.type().equals(subject.type());
```

## 7. Dynamic Property Schema (#282)

Property schema for dynamic types is stored as properties on type nodes in the TYPE_SYSTEM subgraph.

### 7.1 Convention

```
Type node "research-topic" properties:
  schema.title.type = string
  schema.title.required = true
  schema.field.type = string
  schema.methodology.type = string
  schema.year.type = number
```

Schema properties use the `schema.{fieldName}.{attribute}` naming convention. Supported types: string, number, boolean, date.

### 7.2 Access via TypeRegistry

`TypeRegistry.schemaFor(typeName, tenantId)` reads schema properties from the type node and returns structured `SchemaField` records. Consumers use this for:
- LLM prompt construction (expected properties for a type)
- Advisory validation (check if properties match schema)
- Documentation generation

No store-level enforcement. Schema is metadata for consumers, not constraints.

### 7.3 Schema Lifecycle

1. **Platform bootstrap** — TypeRegistry sets schema for core types based on Java interface fields.
2. **LLM discovery** — The LLM extractor adds schema properties to type nodes when it discovers consistent property patterns.
3. **Developer promotion** — When creating a Java interface for a dynamic type, the developer updates the schema to match.

## 8. Promotion Path (Future)

When a dynamic type crystallises (stable schema, frequently queried), a developer creates a Java interface and adds the `java-class` property to the type node. This is a conscious developer act — no automation in this epic.

Future: code generation tooling that reads the type node's schema properties and generates a Java interface. Out of scope for #285.

## 9. Migration Impact

### 9.1 SubgraphType Callers

88 references to `SubgraphType` across the codebase. Migration is mechanical:
- `SubgraphType.PERSON` → `SubgraphTypes.PERSON`
- `SubgraphType.valueOf(s)` → direct string use
- Switch statements → if/else or pattern matching on strings

### 9.2 SQLite Data Migration

Flyway migration to convert uppercase enum names to lowercase strings in the `mindmap_subgraph` table.

### 9.3 Store Implementations

InMemoryMindMapNode and SqliteMindMapNode gain `subgraphType()` and `type()` methods. The stores resolve the subgraph type when constructing nodes.

### 9.4 TraitProxy

TraitProxy.as() in mindmap-intelligence deprecated, delegates to Thing.as(). TraitInvocationHandler logic consolidated into ThingProxyHandler in thing-api.

## 10. Test Strategy

| Module | What's tested |
|--------|--------------|
| thing-api | Thing default methods: is() trait checking, as() proxy with type coercion (String, Integer, Long, Double, Boolean, Optional), ThingProxyHandler edge cases |
| mindmap-api | SubgraphTypes constants, InSubgraphType real implementation via subgraphType(), MindMapNode extends Thing (compile check) |
| mindmap-intelligence | TypeRegistry (bootstrap, typeExists, subtypesOf, javaClass, schemaFor, registerType), TraitProxy deprecation delegation |
| mindmap | CognitiveLoader type subgraph bootstrap (idempotent, per-tenant) |
| mindmap-testing | MindMapStoreContractTest updated for String subgraph types, subgraphType() resolution |
| mindmap-sqlite | Flyway migration for SubgraphType enum → lowercase strings |

## References

- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapNode.java` — current interface, will extend Thing
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphType.java` — enum being replaced
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/TraitRule.java` — trait evaluation SPI
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TraitProxy.java` — existing JDK Proxy (deprecated, delegating)
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TraitInvocationHandler.java` — logic moving to thing-api
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Personable.java` — core trait interface example
- `memory-api/src/main/java/io/casehub/neocortex/memory/Subject.java` — typed entity reference
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/RuleCondition.java` — InSubgraphType placeholder
- Issue #278 — Thing model prior art and design principles
- Issue #281 — SubgraphType refactoring
- Issue #282 — Dynamic property schema
- `docs/specs/issue-253-cognitive-rearchitecture/decisions.md` — D1 (cognitive-api), D26 (acceptance criteria)

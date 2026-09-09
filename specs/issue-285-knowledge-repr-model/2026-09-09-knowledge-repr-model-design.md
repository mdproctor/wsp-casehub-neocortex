# Knowledge Representation Model — Design Spec

**Date:** 2026-09-09
**Epic:** #285 (Knowledge Representation Model — triples, cores, and dynamic type semantics)
**Children:** #278 (design), #281 (SubgraphType → dynamic string), #282 (dynamic property schema)
**Status:** Draft (Round 1 revision)

---

## 1. Problem Statement

The casehub cognitive platform has a knowledge graph (MindMap) that already functions as a Thing system: MindMapNode carries properties, traits, and edges; TraitRule evaluates interfaces from properties/edges; TraitProxy creates typed JDK Proxy views. But this is implicit — there is no `is()`/`as()` API on MindMapNode, no core-type registry, no formal type system, and the trait-to-interface bridge isn't wired to Subject (the typed entity reference in memory-api).

Three gaps:

1. **No `is()`/`as()` on MindMapNode.** Consumers must call `TraitProxy.as(node, Class)` in mindmap-intelligence and manually check `traits().contains(name)`. These operations are fundamental to the knowledge model and belong on MindMapNode as default methods.
2. **Fixed SubgraphType enum.** The 6-value enum (PERSON, PROJECT, RESEARCH_AREA, ORGANISATION, CONCEPT, GENERAL) prevents runtime type discovery by the LLM.
3. **No property schema for dynamic types.** Core types get schema from Java interfaces (Personable defines birthday, role, email, phone). Dynamic types (LLM-discovered) have no schema definition.

### 1.1 Prior Art

From Mark's Drools/PHREAK work: a Thing system where ThingInstances start with a core type, accumulate triples over time, and rules dynamically determine which Java interfaces the Thing satisfies. MindMap already implements this pattern informally — this epic formalizes it.

### 1.2 Design Principles

- **Core types feel like Java.** Typed fields, IDE support, compile-time safety via trait interfaces.
- **Dynamic types feel like maps with conventions.** String-keyed properties, no recompile needed.
- **Promotion is a conscious developer act.** When a dynamic type crystallises, a developer creates a Java interface. Future automation possible but out of scope.
- **Not OWL-DL.** Lightweight type semantics — type hierarchy as data, property schemas as metadata, advisory validation. No formal reasoner.
- **Not RDFS-style "everything is a triple."** Core objects are normal interfaces. Properties and edges are the flexible layer underneath.

## 2. Architecture

### 2.1 MindMapNode as the Consumer API

MindMapNode is already a clean domain interface — not a storage-level type. It carries identity (`id()`, `name()`), epistemic certainty (`confidence()`), traits, properties, temporal bounds, affect dimensions, cross-store references, provenance, and visibility controls. None of these are persistence concerns — every field is a domain concept from the cognitive architecture.

Rather than introduce a separate Thing type to provide `is()`/`as()` semantics, this spec adds them directly to MindMapNode as default methods. The existing TraitProxy/TraitInvocationHandler in mindmap-intelligence is consolidated: a proxy handler moves to mindmap-api as a package-private class, and `as()` becomes a default method on MindMapNode.

### 2.2 Module Structure

```
mindmap-api/            — MODIFIED: SubgraphType enum → String, SubgraphTypes constants,
                          RuleCondition.InSubgraphType uses String,
                          MindMapNode gains subgraphType(), is(), as() default methods,
                          MindMapNodeProxyHandler (package-private)
mindmap-intelligence/   — MODIFIED: TypeRegistry CDI bean replaces ThingResolver/TypeResolver,
                          TraitProxy.as() deprecated (delegates to MindMapNode.as())
mindmap/                — MODIFIED: Store implementations resolve subgraphType() on nodes,
                          CognitiveLoader delegates type bootstrap to TypeRegistry
```

No new modules.

### 2.3 Key Design Decision

`is()` and `as()` are default methods on MindMapNode because:
- `is()` depends only on `traits()` — already on MindMapNode
- `as()` depends only on `property()` — already on MindMapNode
- The proxy handler has no dependencies beyond `java.lang.reflect.Proxy` and MindMapNode itself — it is a pure function from interface metadata + property lookup to typed proxy
- Adding a separate module and type hierarchy for three convenience methods is unnecessary complexity

## 3. MindMapNode Enhancements

### 3.1 Default Methods

```java
// On MindMapNode interface

default boolean is(String traitName) {
    return traits().contains(traitName);
}

default <T> T as(Class<T> traitInterface) {
    if (!traitInterface.isInterface()) {
        throw new IllegalArgumentException(
            "Trait must be an interface: " + traitInterface.getName());
    }
    return MindMapNodeProxyHandler.createProxy(this, traitInterface);
}
```

### 3.2 subgraphType() Accessor

```java
// On MindMapNode interface
String subgraphType();
```

Returns the subgraph's type string for this node. Resolved by the store when constructing the node — the store already has `subgraphId()` and can trivially resolve the subgraph's type via a join or cache lookup.

This gives `RuleCondition.InSubgraphType` a real implementation:

```java
record InSubgraphType(String type) implements RuleCondition {
    @Override
    public boolean evaluate(MindMapNode node, List<MindMapEdge> edges) {
        return type.equals(node.subgraphType());
    }
}
```

`subgraphType()` is preferred over a magic `subgraph-type` property because:
- It is type-safe and discoverable on the MindMapNode interface
- It cannot be overwritten by callers via `NodeUpdate.withProperties()`
- It has no consistency burden — the value comes from the subgraph, not a copied property
- The store already resolves subgraph-dependent data during node construction

### 3.3 MindMapNodeProxyHandler

Package-private class in mindmap-api. Maps interface method names to `node.property(methodName)` calls with return type coercion:

```java
final class MindMapNodeProxyHandler implements InvocationHandler {
    private final MindMapNode node;
    private final Class<?> traitInterface;

    // Handles: toString, hashCode, equals (identity by node ID + trait class)
    // Property lookup with coercion to:
    //   String, Integer, Long, Double, Boolean, Optional<String>
    // Returns null for missing properties on non-Optional return types

    static <T> T createProxy(MindMapNode node, Class<T> traitInterface) {
        return traitInterface.cast(Proxy.newProxyInstance(
            traitInterface.getClassLoader(),
            new Class<?>[] { traitInterface },
            new MindMapNodeProxyHandler(node, traitInterface)));
    }
}
```

Boolean coercion is new — the existing TraitInvocationHandler in mindmap-intelligence handles String, Integer, Long, Double, and Optional but not Boolean. This is an enhancement, not a migration of existing behaviour.

### 3.4 Trait Interfaces

Platform-provided trait interfaces (Personable, Projectlike, Organisational, Eventlike) remain in mindmap-intelligence as optional conveniences.

Consumers define domain-specific traits:
```java
interface Customer {
    Optional<String> accountId();
    Optional<String> tier();
}

MindMapNode node = store.getNode(nodeId, tenantId).orElseThrow();
if (node.is("Customer")) {
    Customer c = node.as(Customer.class);
    c.accountId(); // reads property("accountId")
}
```

### 3.5 TraitProxy Migration

The existing `TraitProxy.as()` in mindmap-intelligence delegates to `MindMapNode.as()`:

```java
@Deprecated
public static <T> T as(MindMapNode node, Class<T> traitInterface) {
    return node.as(traitInterface);
}
```

`TraitInvocationHandler` in mindmap-intelligence becomes unused once all callers migrate to `node.as()`. Existing callers compile unchanged during the transition.

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

**MindMapExtractor impact:** `parseSubgraphType()` no longer catches unknown types and collapses to GENERAL. LLM-provided type strings pass through directly, enabling runtime type discovery. This is a deliberate trust boundary change — the LLM can create subgraphs with arbitrary type names.

## 5. Type Registry

### 5.1 Persistence: Types as MindMap Nodes

Types are first-class data in MindMap, stored as nodes in a designated TYPE_SYSTEM subgraph:

```
TYPE_SYSTEM subgraph
├── node: "person"        (properties: java-class=io.casehub...Personable)
├── node: "project"       (properties: java-class=io.casehub...Projectlike)
├── node: "organisation"  (properties: java-class=io.casehub...Organisational)
├── node: "concept"       (no java-class — dynamic)
├── node: "research-area" (no java-class)
├── node: "general"       (no java-class)
│
├── edge: "researcher" --subtype-of--> "person"
├── edge: "startup" --subtype-of--> "organisation"
└── ...
```

This uses existing MindMapStore operations — no new SPI. Type nodes live in their own subgraph, isolated from domain instances.

**Edge isolation:** Type hierarchy edges (`subtype-of`) exist between type nodes in the TYPE_SYSTEM subgraph. Domain edges exist between instance nodes in domain subgraphs. `MindMapStore.neighbors()` is node-scoped — querying an instance node returns only domain edges connected to that node, never type hierarchy edges between type nodes in a different subgraph. There is no cross-contamination.

### 5.2 TypeRegistry CDI Bean

`@ApplicationScoped` CDI bean in mindmap-intelligence that provides a typed API over the TYPE_SYSTEM subgraph:

```java
@ApplicationScoped
public class TypeRegistry {

    // Queries
    boolean typeExists(String typeName, String tenantId);
    List<String> subtypesOf(String typeName, String tenantId);
    Optional<Class<?>> javaClass(String typeName);
    Optional<TypeSchema> schemaFor(String typeName, String tenantId);

    // Mutations
    void registerType(String typeName, String tenantId);
    void registerType(String typeName, Class<?> javaInterface, String tenantId);
    void registerSubtype(String subtypeName, String supertypeName, String tenantId);

    // Bootstrapping
    @PostConstruct void bootstrap();
}
```

All type queries and mutations go through TypeRegistry rather than raw MindMapStore operations on the TYPE_SYSTEM subgraph. This provides a clean, typed API while using the existing graph infrastructure for persistence.

`javaClass()` does not take `tenantId` because Java class mappings are platform-wide — registered programmatically at bootstrap, not tenant-specific data.

### 5.3 Type Hierarchy Semantics

- **Single supertype.** Each type has at most one `subtype-of` edge. No multiple inheritance.
- **Transitive.** `subtypesOf("person")` includes transitive subtypes (person → researcher → phd-researcher).
- **Schema inheritance.** A subtype inherits its supertype's schema properties and may add its own. Subtypes extend, not replace.
- **Independent of traits.** `is("Personable")` checks traits, which are computed by TraitRule evaluation from properties and edges. A node with `subgraphType()` "researcher" (subtype of "person") is NOT automatically `is("Personable")` — it must satisfy the PersonableTraitRule's conditions independently. Type hierarchy is about schema and classification; traits are about capabilities derived from data.

### 5.4 Bootstrapping

TypeRegistry `@PostConstruct` bootstraps the TYPE_SYSTEM subgraph and core type nodes at startup. Same pattern as CognitiveLoader's vocabulary registration — idempotent, creates subgraph and type nodes only if absent. Per-tenant: each tenant gets its own TYPE_SYSTEM subgraph.

Core type bootstrap maps:
- "person" → `Personable.class`
- "project" → `Projectlike.class`
- "organisation" → `Organisational.class`
- "concept", "research-area", "general" → no java-class (dynamic)

## 6. Subject ↔ MindMapNode Bridge

`Subject(String type, String id)` in memory-api references a MindMapNode by naming convention:

- `Subject.type()` == `node.subgraphType()` (both lowercase-normalized)
- `Subject.id()` == `node.id()` (MindMapNode UUID)

No code dependency between memory-api and mindmap-api. Resolution happens at the call site:

```java
Subject subject = Subject.of("person", nodeId);
MindMapNode node = store.getNode(subject.id(), tenantId).orElseThrow();
assert subject.type().equals(node.subgraphType());
```

Subject intentionally has no `scheme` field because it is a domain-level reference (what kind of entity), not a system-level reference (which store). NodeRef's `scheme` disambiguates target stores; Subject's `type` disambiguates entity semantics within the cognitive platform's single knowledge graph.

## 7. Dynamic Property Schema (#282)

### 7.1 Schema Storage

Property schema for types is stored as properties on type nodes in the TYPE_SYSTEM subgraph:

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

### 7.2 Schema Access

Schema is metadata managed by TypeRegistry, available via `schemaFor(typeName, tenantId)`:

```java
public record TypeSchema(Map<String, FieldSchema> fields) {}
public record FieldSchema(String type, boolean required) {}
```

No standalone PropertySchemaValidator. Schema is available for consumers who need it (LLM prompt construction, development tooling, documentation generation) but is not enforced at the store level:

- LLM-discovered entities regularly introduce new properties not in any schema — rejecting them would prevent knowledge discovery
- Advisory-only validation (log WARN) provides no programmatic signal — consumers cannot act on it
- Schema enforcement belongs to the consumer context (e.g., a form UI validates required fields; the LLM extractor does not)

### 7.3 Schema Lifecycle

Schema properties are set by:
1. **Platform bootstrap** — TypeRegistry sets schema for core types based on Java interface method signatures.
2. **LLM discovery** — The LLM extractor adds schema properties to type nodes when it discovers consistent property patterns.
3. **Developer promotion** — When creating a Java interface for a dynamic type, the developer updates the schema to match.

## 8. Promotion Path (Future)

When a dynamic type crystallises (stable schema, frequently queried), a developer creates a Java interface and adds the `java-class` property to the type node via TypeRegistry. This is a conscious developer act — no automation in this epic.

Future: code generation tooling that reads the type node's schema and generates a Java interface. Tracked as GitHub issue (see deferred items below).

### 8.1 Deferred Items (GitHub Issues)

- **Promotion automation** — automated code generation from type schema to Java interface. Filed as a GitHub issue, not deferred silently in the spec.

## 9. Migration Impact

### 9.1 SubgraphType Callers

88 references to `SubgraphType` across the codebase. Migration is mechanical:
- `SubgraphType.PERSON` → `SubgraphTypes.PERSON`
- `SubgraphType.valueOf(s)` → direct string use
- Switch statements → if/else or pattern matching on strings
- SqliteMindMapStore deserialization updated

### 9.2 SQLite Data Migration

The `mindmap_subgraph` table stores types as uppercase enum names. Migration maps each value:

| Current (enum name) | Target (lowercase string) |
|---------------------|--------------------------|
| PERSON | person |
| PROJECT | project |
| RESEARCH_AREA | research-area |
| ORGANISATION | organisation |
| CONCEPT | concept |
| GENERAL | general |

This is a one-time schema migration in SqliteMindMapStore, applied at startup via the existing migration mechanism.

### 9.3 MindMapExtractor

- `parseSubgraphType()` passes LLM type strings through instead of collapsing to GENERAL
- `findOrCreateSubgraph()` uses the LLM-provided type name
- `findOrCreateSubgraph()` cache key changes from `SubgraphType` to `String`

### 9.4 TraitProxy

`TraitProxy.as()` deprecated, delegates to `MindMapNode.as()`. Existing callers compile unchanged. `TraitInvocationHandler` superseded by `MindMapNodeProxyHandler` in mindmap-api.

### 9.5 MindMapNode subgraphType()

Store implementations (InMemoryMindMapStore, SqliteMindMapStore) resolve subgraph type when constructing MindMapNode instances:
- InMemoryMindMapStore: trivial lookup from in-memory subgraph data
- SqliteMindMapStore: JOIN on `mindmap_subgraph` table or cached lookup

Existing MindMapNode implementations (test doubles, mocks) need to provide `subgraphType()`. Since MindMapNode is an interface, the clean approach is to update all implementations — this forces every construction site to be explicit about the node's subgraph type.

## 10. Test Strategy

| Module | What's tested |
|--------|--------------|
| mindmap-api | SubgraphTypes constants, InSubgraphType with real evaluation via subgraphType(), MindMapNode.is() default method, MindMapNode.as() proxy with type coercion (String, Integer, Long, Double, Boolean, Optional), subgraphType() accessor |
| mindmap-intelligence | TypeRegistry (type subgraph queries, hierarchy traversal including transitive subtypes, schema lookup, bootstrap idempotency, java-class mapping), CognitiveLoader updated for TypeRegistry |
| mindmap | Store implementations resolve subgraphType(), SQLite data migration for lowercase types |
| mindmap-testing | MindMapStoreContractTest updated for String subgraph types |

## References

- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapNode.java` — enhanced with is(), as(), subgraphType()
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphType.java` — enum being replaced
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/TraitRule.java` — trait evaluation SPI
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TraitProxy.java` — existing JDK Proxy (deprecated by this spec)
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Personable.java` — core trait interface example
- `memory-api/src/main/java/io/casehub/neocortex/memory/Subject.java` — typed entity reference
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/RuleCondition.java` — InSubgraphType fixed
- Issue #278 — Thing model prior art and design principles
- Issue #281 — SubgraphType refactoring
- Issue #282 — Dynamic property schema
- `docs/specs/issue-253-cognitive-rearchitecture/decisions.md` — D1 (cognitive-api), D26 (acceptance criteria)

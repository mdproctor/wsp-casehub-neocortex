## D1: Identity term — Principal

**Choice:** `principalId` (String) as the identity scoping key for ownership
**Alternatives:**
- `actorId` — more about "who is doing" than "who owns"
- `agentId` — too narrow, excludes humans
- `userId` — too narrow, excludes agents
**Rationale:** Principal is the industry-standard term covering both humans and agents. Aligns with Quarkus SecurityIdentity and Java security model. casehubio/platform#271 delivers the formal type.
**Trade-offs:** Security connotation — but appropriate since identity is fundamentally a security/auth concern.
**Sources:** casehubio/platform#271, java.security.Principal, casehubio/neocortex#269 (principalId on EdgeInput/NodeInput)
**Exploration:** quick
**Status:** captured

## D2: Rename entityId to subjectId

**Choice:** Rename `entityId` → `subjectId` across the codebase, introduce `Subject(String type, String id)` as a polymorphic typed reference
**Alternatives:**
- Keep `entityId` as-is — vague name, no type information
- Use `NodeRef` from mindmap-api — creates coupling between memory-api and mindmap-api
**Rationale:** "Entity" is vague. "Subject" says exactly what it means: who/what the memory is about. The Subject record adds type information (person, project, research-topic) without an enum — the type vocabulary is dynamic, LLM-discovered at runtime. Pre-release, no migrations, IntelliJ refactoring handles the blast radius.
**Trade-offs:** Large mechanical refactoring across many files. Worth it for correct semantics.
**Sources:** MemoryInput.java, MemoryQuery.java, CaseMemoryStore.java, CbrCaseMemoryStore.java
**Exploration:** quick
**Depends on:** D1 (Principal identity term)
**Status:** captured

## D3: Subject type is dynamic, not an enum

**Choice:** `Subject(String type, String id)` — type is a free-form string, not a Java enum
**Alternatives:**
- Enum-based type (like SubgraphType) — requires recompile for new types
- OWL-DL formal ontology — too heavyweight for runtime LLM-driven type evolution
- RDFS triples — too cumbersome for developer experience
**Rationale:** The LLM discovers new entity types over time as it learns. Hardcoded enums prevent this. The type vocabulary is runtime data. Java/TypeScript developers think in terms of Type, Instance, extends, isA — not rdfs:Class or owl:Thing. Subject is a reference to a Thing (see #278) where cores get Java interfaces and dynamics get string types.
**Trade-offs:** No compile-time type safety on dynamic types. Mitigated by core types having Java interface projections.
**Sources:** SubgraphType.java (flagged as tech debt — should become dynamic), casehubio/neocortex#278
**Exploration:** quick
**Depends on:** D2 (Subject as typed reference)
**Status:** captured

## D4: Visibility model — owner + sharedWith

**Choice:** Two fields: `principalId` (nullable String, the owner) + `sharedWith` (Set<String>, additional principals)
**Alternatives:**
- Binary PRIVATE/SHARED flag — too simple, no selective sharing
- Access list only (Set<String> visibleTo) — loses the owner concept
**Rationale:** Three natural states: private (owner only), owned + shared (owner + named others), truly shared (no owner = everyone in tenant). Null principalId + empty sharedWith = truly shared (backward compat — all existing memories visible to everyone). Owner concept matters: the person who created a memory has a different relationship to it than someone it was shared with.
**Trade-offs:** Query-time filtering required. Acceptable — the filter is a simple OR check (is owner, or in sharedWith, or no owner).
**Sources:** Family model discussion, casehubio/neocortex#269 (principalId already on EdgeInput/NodeInput)
**Exploration:** quick
**Depends on:** D1 (Principal identity term), D2 (Subject as typed reference)
**Status:** captured

## D5: Terminology aligned to Java/TypeScript

**Choice:** Use Java/TypeScript vocabulary: Type, Instance, Property, extends, isA. No semantic web terminology.
**Alternatives:**
- RDFS vocabulary (rdfs:Class, rdf:type, rdfs:subClassOf) — unfamiliar to target audience
- OWL-DL vocabulary — even more unfamiliar
**Rationale:** Target audience is Java and TypeScript developers. These terms are already natural: `thing.isA("Person")` reads like runtime instanceof. `extends` is the hierarchy relationship. No learning curve.
**Trade-offs:** Loses formal semantic web interoperability. Not a concern — this is a runtime cognitive platform, not a linked data system.
**Sources:** Java instanceof, TypeScript structural typing, schema.org Thing
**Exploration:** quick
**Status:** captured

## D6: Thing as universal base concept

**Choice:** `Thing` as the name for the universal dynamic-property entity base
**Alternatives:**
- `Entity` — JPA/ORM baggage
- `Record` — Java keyword collision
- `Instance` — too generic
- `Object` — Java root collision
**Rationale:** "Thing" doesn't collide with any Java/TS keyword. schema.org precedent. Captures exactly what it is. In JS/TS, every object already IS a Thing (dynamic properties are the language default). In Java, Thing bridges the gap by giving objects dynamic property bags + structural type matching.
**Trade-offs:** Informal — but that's the point. Accessible to developers, not just ontology specialists.
**Sources:** schema.org Thing, Drools traits model (prior art), #278
**Exploration:** quick
**Depends on:** D5 (Java/TS terminology)
**Status:** captured

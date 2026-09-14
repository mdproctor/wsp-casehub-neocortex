# Cognitive Schema Flywheel — Design Spec

**Issue:** casehubio/neocortex#335
**Children:** #292 (schema discovery), #293 (code generation), #334 (adaptive extraction)
**Date:** 2026-09-14
**Branch:** issue-335-cognitive-schema-flywheel

## Summary

Self-improving knowledge representation: the cognitive graph discovers its own schema from extracted entities, uses known schemas to guide future extraction with precision, and optionally crystallises stable schemas into Java trait interfaces for developer ergonomics.

Three layers form a flywheel:
1. **Schema Discovery** — consolidation phase analyzes property patterns across entities of the same type, writes schema properties to type nodes
2. **Adaptive Extraction** — MindMapExtractor reads type schemas from the graph and injects them into the LLM extraction prompt as structured profile data
3. **Dev-time Promotion** — CLI tool generates Java trait interface source files from stabilized type schemas

The runtime flywheel (Layers 1 + 2) runs entirely on schema DATA stored as type node properties — no Java interfaces involved. Layer 3 is an optional developer tool for types that have stabilized enough that application code wants compile-time type safety.

## Architecture

### Dual-Path Design (D4)

```
Layer 1: Schema Discovery (consolidation phase)
   Entities extracted by LLM → property patterns analyzed → schema properties written to type nodes
                                                                    ↓
Layer 2: Adaptive Extraction (runtime prompt enrichment)            ↓
   MindMapExtractor reads type schemas → injects into prompt → LLM extracts with precision
       ↑                                                            ↓
       └────────────── feeds back ──────────────────────────────────┘

Layer 3: Dev-time Promotion (CLI code generation)
   Stable type schemas → Java trait interface source files → developer reviews + commits
```

Two distinct paths serve different consumers:

| Path | Consumer | What it needs | Timing |
|------|----------|---------------|--------|
| **Runtime data path** | Flywheel (extraction + consolidation) | Schema as data in type nodes | Runtime — no Java interfaces |
| **Promotion path** | Application developers | Java trait interface | Dev-time — when a type stabilizes |

`Thing.as()` bridges both — works with hand-written interfaces, generated interfaces, and ad-hoc interfaces. `ThingProxyHandler` already provides runtime typed access via JDK Proxy; Java interfaces add compile-time safety and discoverability for stable types only.

### SchemaField Extension (D8)

```java
public record SchemaField(
    String name,
    String type,              // string, number, boolean
    boolean required,
    boolean collection,       // single value vs list (default false)
    String description,       // human-readable hint for LLM (nullable)
    List<String> enumValues   // constrained values when known (nullable)
) {
    public SchemaField(String name, String type, boolean required) {
        this(name, type, required, false, null, null);
    }
}
```

Backward-compatible — existing 3-arg constructor delegates. Stored on type nodes as properties:

| Property | Example |
|----------|---------|
| `schema.date.type` | `string` |
| `schema.date.required` | `true` |
| `schema.date.collection` | `false` |
| `schema.date.description` | `when the meeting is scheduled` |
| `schema.date.enum` | (absent — unconstrained) |
| `schema.date.source` | `java` or `discovered` |
| `schema.date.first-seen-epoch` | `1726300800` (consolidation tick, discovered fields only) |

## Layer 1: Schema Discovery — SchemaDiscoveryPhase (#292)

**Module:** `mindmap-intelligence`
**Class:** `SchemaDiscoveryPhase implements ConsolidationPhase`
**Priority:** `@Priority(25)` — after MergeDetectionPhase(20) so schemas reflect deduplicated entities, before CommunitySummaryPhase(30)

### Algorithm

1. Query all nodes in the current subgraph
2. Group by type (subgraph type, or `cognitiveKind` property for cognitive nodes)
3. For each type with ≥ `min-samples` entities:
   a. Count property frequency across all entities of that type
   b. For each property at ≥ `threshold` frequency:
      - Read existing schema from type node (`TypeRegistry.schemaFor()`)
      - **Skip if `schema.{field}.source = java`** — Java-derived schema is immutable by discovery (D6)
      - Infer `type` from observed values: all parseable as numbers → `number`, all true/false → `boolean`, else `string`
      - Infer `collection`: if ≥60% of non-null values for a field contain commas AND have ≥2 comma-separated segments, mark as collection
      - Infer `enumValues` when ≤10 distinct values across all entities
      - Set `required = true` if frequency ≥ `required-threshold`
      - Write `schema.{field}.*` properties to the type node via `store.updateNode()`
      - Set `schema.{field}.source = discovered`
      - Set `schema.{field}.first-seen-epoch` on first discovery

### Configuration

```properties
casehub.mindmap.schema-discovery.threshold=0.8
casehub.mindmap.schema-discovery.min-samples=5
casehub.mindmap.schema-discovery.required-threshold=0.95
```

All configurable via Quarkus properties. Designed as candidates for future CBR auto-tuning — the config-driven approach makes that transition natural.

### Provenance Tracking (D5 feedback loop protection)

Schema-guided extraction creates a positive feedback loop: the LLM preferentially extracts properties it's told about, reinforcing their frequency. Mitigation:

- Each discovered property carries `schema.{field}.source` = `java` | `discovered`
- `schema.{field}.first-seen-epoch` records when the property was first discovered
- Properties discovered ONLY after guided extraction was enabled (never seen via open-ended extraction) are identifiable by their epoch vs the deployment's guided-extraction-enabled timestamp
- The CBR auto-tuning follow-on should factor this provenance into threshold adjustment

### Additive Enrichment (D6)

Schema discovery enriches ALL types, including those with Java interfaces:
- Java-derived schema (from `deriveSchemaFromInterface()`) is the baseline, written with `source=java`
- Discovery adds new properties with `source=discovered`
- Discovery never overwrites `source=java` fields
- `schemaFor()` merges both sources, Java fields taking precedence on conflict

### TypeRegistry Changes

`registerType(String, String, Class<?>, String)` updated to write `schema.{field}.source=java` for all Java-derived schema fields.

`schemaFor(String, String)` updated to read the new SchemaField fields (collection, description, enumValues) from type node properties.

`deriveSchemaFromInterface()` unchanged — still produces the base schema from Java reflection. The source tag is applied by `registerType()`.

## Layer 2: Adaptive Extraction — Schema-Guided Prompting (#334)

**Module:** `mindmap-intelligence`
**Changes to:** `MindMapExtractor`

### Mechanism

1. During `buildUserPrompt()`, after retrieving graph context, collect the types of entities found in the context
2. For each type present in the context, call `TypeRegistry.schemaFor(type, tenantId)`
3. If any schemas are non-empty, append to the user prompt as structured profile data:

```
Known type schemas:
  meeting: {date: string (required), attendees: string (collection), agenda: string, location: string}
  person: {role: string, email: string (required), department: string}

Extract all observed properties, including those not listed in known schemas.
```

4. The "extract all observed properties" instruction explicitly counteracts the feedback loop

### Selective Injection (D5)

Only types whose entities already exist in the graph AND appear in the context for this conversation turn get their schemas injected. Specifically, schemas are collected from types of nodes returned by `retrieveContext()` — which searches existing graph nodes by candidate terms from the conversation text. New types being mentioned for the first time will not have schemas injected (they haven't been extracted yet). This is correct behavior: schema guidance only applies to types the system has already learned about. A mature system with 50+ types doesn't bloat the prompt — only the 2-3 relevant types are included.

### Code Changes

- **New dependency:** `Instance<TypeRegistry>` — graceful degradation; no TypeRegistry = no schema injection, extraction works as before
- **New private method:** `buildSchemaHint(Map<String, Map<String, SchemaField>> schemas)` — formats schemas into profile-data string
- **Modified:** `buildUserPrompt()` gains a schema injection block after context assembly
- **Unchanged:** `SYSTEM_PROMPT`, `applyExtraction()`, `ExtractionJsonParser`

### Profile Data Approach (D5)

Per GE-20260914-e3cb03: present schema as labeled structured data, not behavioral directives. The LLM integrates schema knowledge emergently through its existing extraction behavior. Behavioral directives ("when you see a meeting, always extract date and attendees") override the extraction rules and produce uniform, less-contextual output. Profile data ("meeting has: date, attendees, agenda") lets the LLM decide what's relevant to THIS conversation turn.

## Layer 3: Dev-Time Promotion — Trait Interface Generator (#293)

**Module:** `schema-generator` (existing module, extended)
**Class:** `TraitInterfaceGenerator`

### Usage

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn exec:java \
  -pl schema-generator \
  -Dexec.mainClass=io.casehub.neocortex.schema.TraitInterfaceGenerator \
  -Dexec.args="--type meeting --tenant default --package io.casehub.neocortex.mindmap.intelligence"
```

### What It Does

1. Connects to a running MindMapStore (or reads an exported schema YAML file via `--schema-file`)
2. Calls `TypeRegistry.schemaFor(typeName, tenantId)` to get the full schema
3. Generates a Java interface source file:

```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Optional;

public interface Meetinglike {
    Optional<String> date();
    Optional<String> attendees();
    Optional<String> agenda();
    Optional<String> location();
}
```

### Naming Convention

Type name + `like` suffix for noun types, matching the existing pattern (Belieflike, Fearlike, Desirelike). PascalCase conversion: `meeting` → `Meetinglike`, `research-report` → `ResearchReportlike`.

### Output

Writes to stdout by default. `--output <dir>` writes to a file with the correct package directory structure. Developer reviews the generated interface, adjusts naming/methods if needed, copies to the target module, and commits.

### Intentional Limitations

- All properties generate `Optional<String>` return types — the developer promotes to `int`, `boolean`, etc. during review
- No automatic registration with TypeRegistry — the developer adds the Java class association via `registerType(name, parent, javaClass, tenantId)` in CognitiveLoader or equivalent bootstrap code
- No merge/diff on regeneration — the generated file is a starting point, not a managed artifact

## Module Impact

| Module | Change | Scope |
|--------|--------|-------|
| `mindmap-api` | Extend `SchemaField` record (3 new fields, backward-compatible constructor) | Small |
| `mindmap-intelligence` | `SchemaDiscoveryPhase` (new class), `MindMapExtractor` (schema injection in `buildUserPrompt`), `TypeRegistry` (read new fields in `schemaFor`, write `source=java` in `registerType`) | Medium |
| `schema-generator` | `TraitInterfaceGenerator` (new class, CLI entry point) | Small |

No new modules. No database migrations. No SPI changes.

## Testing Strategy

1. **SchemaDiscoveryPhase unit tests** — given N entities of type X with property patterns, verify schema properties written to type node at correct thresholds; verify Java-sourced fields are not overwritten; verify min-samples gate; verify collection/enum inference
2. **SchemaField backward compatibility** — existing callers of 3-arg constructor still compile and work
3. **TypeRegistry.schemaFor integration** — verify merged schema (Java-derived + discovered) with correct precedence; verify source tags read correctly
4. **MindMapExtractor schema injection** — verify prompt contains schema hints when TypeRegistry is available; verify extraction works unchanged when TypeRegistry is absent (graceful degradation); verify selective injection (only context-relevant types)
5. **TraitInterfaceGenerator** — verify generated Java source compiles, follows naming conventions, maps schema fields to `Optional<String>` methods
6. **Feedback loop protection** — verify "extract all observed properties" instruction is present; verify provenance source tracking on discovered fields

## Known Limitations (v1)

- **No cross-tenant schema sharing** — each tenant discovers independently. Future: global schema templates that tenants can inherit and override.
- **No schema deprecation/decay** — discovered properties persist until manually removed. Future: frequency decay over time, or CBR-driven deprecation.
- **Statistical weakness at small samples** — mitigated by configurable thresholds. Future: CBR auto-tuning of thresholds based on extraction quality outcomes.
- **No schema merge on entity merge** — when MergeDetectionPhase merges entities of different types, the surviving type's schema is not explicitly updated. Properties from merged entities naturally contribute to future discovery cycles.
- **Idle-gated discovery** — under continuous load, idle detection (≥1 min) may delay discovery. Acceptable for v1. Future: near-time event-driven accumulator (CDI events + in-memory counters).

## References

- TypeRegistry.java:91-112 — schemaFor() method
- TypeRegistry.java:136-162 — registerType() with Java class
- TypeRegistry.java:237-246 — deriveSchemaFromInterface()
- MindMapExtractor.java:39-66 — SYSTEM_PROMPT
- MindMapExtractor.java:158-198 — buildUserPrompt()
- MindMapExtractor.java:200-268 — applyExtraction()
- SchemaField.java — current record (name, type, required)
- CognitiveLoader.java:56-82 — @PostConstruct type registration
- ConsolidationScheduler.java — consolidation phase orchestration
- ConsolidationPhase SPI — phase interface
- #285 spec §1.2 — "Promotion is a conscious developer act"
- #322 spec — cognitive node type classification (trait interfaces, TypeRegistry integration)
- GE-20260912-c4c279 — Thing trait projections as typed facades
- GE-20260914-e3cb03 — profile data over prose directives for LLM cognitive state
- GE-20260912-ff141b — neocortex cognitive stack overview
- decisions.md D1-D8 — full decision rationale and alternatives

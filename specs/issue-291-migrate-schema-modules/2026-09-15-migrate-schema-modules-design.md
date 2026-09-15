# Migrate ShorthandModule and EnumInliningModule to shared platform versions

**Issue:** #291, #290
**Date:** 2026-09-15
**Scale:** S | **Complexity:** Low

## Summary

Replace the local `ShorthandModule` and `EnumInliningModule` in `schema-generator` with the shared versions from `casehub-platform-schema-generator`. `SealedHierarchyModule` is already using the platform version — no action needed.

## Current State

`CognitiveSchemaGenerator` wires three victools modules:

1. **`SealedHierarchyModule`** — already imports from `io.casehub.schema.generator.module`. Done.
2. **`EnumInliningModule`** — local copy at `io.casehub.neocortex.schema.EnumInliningModule`. Functionally identical to platform version (both inline enums as `{type: "string", enum: [...]}` with `CustomDefinition` set to inline mode).
3. **`ShorthandModule`** — local copy at `io.casehub.neocortex.schema.ShorthandModule`. Hardcodes three types: `Confidence`, `NodeRef`, `RecurrenceRule`. Each gets a `oneOf` with scalar and object forms.

## Target State

### EnumInliningModule

Drop-in replacement. Change the import in `CognitiveSchemaGenerator` from `io.casehub.neocortex.schema.EnumInliningModule` to `io.casehub.schema.generator.module.EnumInliningModule`. Delete the local class.

**Behavioural difference:** Local uses `new CustomDefinition(schema, true)`. Platform uses `new CustomDefinition(enumNode, DefinitionType.INLINE, AttributeInclusion.YES)`. The boolean `true` constructor is equivalent to `DefinitionType.INLINE` — no schema output change.

### ShorthandModule

The platform `ShorthandModule` constructor takes `Map<Class<?>, ShorthandDefinition>`. Each `ShorthandDefinition` provides `scalarSchema(config)` and `objectSchema(config)` — the module builds the `oneOf` wrapper.

Neocortex must provide three `ShorthandDefinition` registrations, built inline in `CognitiveSchemaGenerator`'s constructor (D1):

| Type | Scalar form | Object form |
|------|-------------|-------------|
| `Confidence` | `{type: "number", minimum: 0, maximum: 1}` | `{type: "object", properties: {origin: enum, value: number, decayReference: date-time}, required: [origin, value]}` |
| `NodeRef` | `{type: "string", pattern: "^[^:]+:.+$"}` | `{type: "object", properties: {scheme: string, id: string, qualifier: string}, required: [scheme, id]}` |
| `RecurrenceRule` | `{type: "string", pattern: "^FREQ="}` | `{type: "object", properties: {freq: enum, interval: integer, count: integer, until: date-time, byDay: array}, required: [freq]}` |

The schema output remains identical — the platform module wraps scalar + object in `oneOf` the same way the local code does.

## Files Changed

### Deleted
- `schema-generator/src/main/java/io/casehub/neocortex/schema/ShorthandModule.java`
- `schema-generator/src/main/java/io/casehub/neocortex/schema/EnumInliningModule.java`
- `schema-generator/src/test/java/io/casehub/neocortex/schema/EnumInliningModuleTest.java`

### Modified
- `schema-generator/src/main/java/io/casehub/neocortex/schema/CognitiveSchemaGenerator.java` — replace local module instantiation with platform imports + definitions map
- `schema-generator/src/test/java/io/casehub/neocortex/schema/ShorthandModuleTest.java` — repoint to platform `ShorthandModule` with neocortex definitions (D2)

### Unchanged
- `schema-generator/pom.xml` — `casehub-platform-schema-generator` dependency already present; `cognitive-api` and `mindmap-api` dependencies stay (needed for `Confidence`, `NodeRef`, `RecurrenceRule` class references in the definitions map)
- All other test files — `CognitiveSchemaGeneratorTest` verifies end-to-end schema equivalence without changes

## Verification

Existing tests are the schema equivalence gate:
- `CognitiveSchemaGeneratorTest.confidence_generatesShorthandOneOf` — verifies Confidence oneOf structure
- `CognitiveSchemaGeneratorTest.confidenceOrigin_generatesInlinedEnum` — verifies enum inlining
- `CognitiveSchemaGeneratorTest.allModulesWorkTogether_featureFieldWithNestedSealed` — verifies all modules compose correctly
- `ShorthandModuleTest` (9 tests) — verifies each type's scalar and object forms

No new tests needed. If all existing tests pass, schema equivalence is confirmed.

## References

- `CognitiveSchemaGenerator.java:56-68` — current module wiring
- `ShorthandModule.java` (local, 117 lines) — current hardcoded implementation
- `EnumInliningModule.java` (local, 43 lines) — current implementation
- `ShorthandDefinition` (platform) — new API interface
- `ShorthandModule` (platform) — new generic implementation
- casehubio/platform#279 — SealedHierarchyModule extraction (already done)
- casehubio/platform#280 — ShorthandModule extraction

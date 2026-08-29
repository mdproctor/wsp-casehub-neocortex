# Unified Confidence Model — Design Spec

**Issue:** casehubio/neocortex#229
**Epic:** #224 Structural Foundation / #253 Cognitive Architecture Re-architecture
**Scope:** M (multi-module, mechanical per-module)
**Stage:** pre-release — breaking changes are free

---

## Problem

Three incompatible confidence representations exist across the cognitive subsystems:

| Store | Current type | Origin tracking | Decay reference | Range |
|-------|-------------|----------------|-----------------|-------|
| MindMap | `ConfidenceOrigin` enum + `double confidence` | STATED/INFERRED/SPECULATED | `confirmedAt` (nodes), `updatedAt` (edges) | [0,1] |
| Memory | `Double importance` | None | None | [0,1] nullable |
| CBR | `Double confidence` + `CbrOutcome` EMA | None | `storedAt` on ScoredCbrCase | [0,1] nullable |

A MindMap node at confidence 0.7 and a CBR case at confidence 0.7 mean different things (origin-initial vs EMA-adjusted). Cross-store sorting, filtering, and comparison are impossible. Decay is computed differently per entity type.

## Solution

A single `Confidence` record in a new `cognitive-api` module, replacing all three representations.

---

## New Module: `cognitive-api`

**Maven coordinates:** `io.casehub:casehub-neocortex-cognitive-api`
**Package:** `io.casehub.neocortex.cognitive`
**Dependencies:** none (tier-0, pure Java)
**Depended on by:** `mindmap-api`, `memory-api`

Starts with 2 types. Growth path: `TemporalMark` (#234), `MemorySpace`/`Visibility` (#230), `Affect` (#238).

---

## Type Design

### `ConfidenceOrigin` (moved from `mindmap-api`)

```java
package io.casehub.neocortex.cognitive;

public enum ConfidenceOrigin {
    STATED,
    INFERRED,
    SPECULATED,
    UNKNOWN;
}
```

**Changes from current:**
- **Moved** from `io.casehub.neocortex.mindmap` to `io.casehub.neocortex.cognitive`
- **Added** `UNKNOWN` — represents absence of provenance information (used by Memory and CBR where origin was never tracked)
- **Removed** `initialConfidence()` — the values (STATED=1.0, INFERRED=0.7, SPECULATED=0.3) are MindMap extraction defaults, not cognitive axioms. A stated fact CAN have any confidence level. Defaults move to the MindMap store layer.
- **Non-nullable** on the `Confidence` record — exhaustive switch coverage everywhere

### `Confidence`

```java
package io.casehub.neocortex.cognitive;

import java.time.Instant;
import java.util.Objects;

public record Confidence(
    ConfidenceOrigin origin,
    double value,
    Instant decayReference
) {
    public Confidence {
        Objects.requireNonNull(origin, "origin required");
        if (!(value >= 0.0 && value <= 1.0)) {
            throw new IllegalArgumentException("value must be in [0,1], got: " + value);
        }
    }

    public static Confidence of(ConfidenceOrigin origin, double value) {
        return new Confidence(origin, value, null);
    }

    public static Confidence of(double value) {
        return new Confidence(ConfidenceOrigin.UNKNOWN, value, null);
    }

    public static Confidence stated(double value, Instant decayReference) {
        return new Confidence(ConfidenceOrigin.STATED, value, decayReference);
    }

    public static Confidence unknown(double value) {
        return new Confidence(ConfidenceOrigin.UNKNOWN, value, null);
    }

    public Confidence withValue(double newValue) {
        return new Confidence(origin, newValue, decayReference);
    }

    public Confidence withDecayReference(Instant newRef) {
        return new Confidence(origin, value, newRef);
    }
}
```

**Validation:** Uses `!(value >= 0.0 && value <= 1.0)` — the inverted range check that structurally rejects NaN via IEEE 754 semantics (per GE-20260604-043617).

**`decayReference`** is nullable. Null means "this confidence does not decay" — used by Memory entries where decay is not configured. When non-null, `ConfidenceDecayDecorator` applies exponential decay from this instant.

---

## Migration by Store

### MindMap (`mindmap-api`)

#### `MindMapNode`

| Field | Before | After |
|-------|--------|-------|
| `confidenceOrigin()` | `ConfidenceOrigin` | Removed — access via `confidence().origin()` |
| `confidence()` | `double` | `Confidence` — the unified record |
| `confirmedAt()` | `Instant` | **Removed** — subsumed by `confidence().decayReference()`. `updatedAt()` serves audit needs. |

#### `MindMapEdge`

| Field | Before | After |
|-------|--------|-------|
| `confidenceOrigin()` | `ConfidenceOrigin` | Removed |
| `confidence()` | `double` | `Confidence` |

No fields removed — edges never had `confirmedAt`. The decay decorator previously used `updatedAt()` as the decay reference; now uses `confidence().decayReference()`.

#### `NodeInput`

| Field | Before | After |
|-------|--------|-------|
| `ConfidenceOrigin confidenceOrigin` | Separate field, defaults to STATED | Removed |
| `Double confidence` | Separate nullable field | Removed |
| `Confidence confidence` | — | **New** nullable field. Null means "use store defaults" |

When `confidence` is null on NodeInput, the store layer applies MindMap-specific defaults:
- `origin = STATED` (existing behaviour)
- `value = origin.initialConfidence()` equivalent (1.0 for STATED) — this logic moves to a package-private `MindMapConfidenceDefaults` utility in the mindmap store layer
- `decayReference = Instant.now()`

#### `EdgeInput`

Same pattern as NodeInput.

#### `NodeUpdate`

| Field | Before | After |
|-------|--------|-------|
| `ConfidenceOrigin confidenceOrigin` | Separate field | Removed |
| `Double confidence` | Separate field | Removed |
| `Instant confirmedAt` | Separate field | Removed |
| `Confidence confidence` | — | **New** nullable field. Null = "don't change confidence". Non-null replaces entire confidence including decayReference. |

#### `MindMapQuery`

`Double minConfidence` and `ConfidenceOrigin confidenceOrigin` **stay as separate query predicates**. These are independent filters ("find nodes with confidence above X" / "find nodes that were stated"), not a value composition. They do not become a `Confidence` field on the query.

#### `ParsedEntity`

`ConfidenceOrigin confidence` renamed to `ConfidenceOrigin origin` for clarity. ParsedEntity carries origin only — the confidence value is derived at store time via defaults.

#### `ConfidenceDecayDecorator`

Migrates from reading entity-specific timestamps to reading `confidence().decayReference()`:

```java
// Before:
double decayed = applyDecay(node.confidence(), node.confirmedAt(), halfLifeDays);
// After:
Confidence c = node.confidence();
double decayed = applyDecay(c.value(), c.decayReference(), halfLifeDays);
```

Returns wrapped nodes/edges with a new `Confidence` carrying the decayed value (same origin, same decayReference):

```java
private MindMapNode withDecayedConfidence(MindMapNode node) {
    Confidence c = node.confidence();
    double decayed = applyDecay(c.value(), c.decayReference(), defaultHalfLifeDays);
    if (decayed == c.value()) return node;
    return new DecayedNode(node, c.withValue(decayed));
}
```

`DecayedNode`/`DecayedEdge` simplify — `confirmedAt()` delegation is no longer needed on DecayedNode (field removed from interface). One fewer method to delegate.

#### `MindMapAnalyzer.staleNodes`

Currently reads `confirmedAt` for staleness detection. Migrates to `confidence().decayReference()`.

#### Backends

**InMemoryMindMapStore:** `StoredNode` and `StoredEdge` replace their separate `confidenceOrigin`/`confidence` fields with a single `Confidence confidence` field. `confirmedAt` removed from `StoredNode`. Defaulting logic (when NodeInput.confidence is null) moves to `addNode()`.

**SqliteMindMapStore:** Schema change — `confidence_origin` + `confidence` + `confirmed_at` columns on `nodes` table replaced with `confidence_origin` + `confidence_value` + `decay_reference`. Same pattern for `edges` table (`confidence_origin` + `confidence` → `confidence_origin` + `confidence_value` + `decay_reference`). Flyway migration. Row-mapping methods (`toNode`, `toEdge`) construct `Confidence` from the three columns.

**MindMapStoreContractTest:** Test helpers and assertions update to use `Confidence`. Tests that set `confirmedAt` separately now construct a `Confidence` with a `decayReference`.

### Memory (`memory-api`)

#### `MemoryInput`

| Field | Before | After |
|-------|--------|-------|
| `Double importance` | Nullable, validated [0,1] | **Removed** |
| `Confidence confidence` | — | **New** nullable. Null means "no confidence assessment" |

`withAttribute`, `withAttributes`, `withText` methods updated to carry `confidence` through.

#### `Memory`

| Field | Before | After |
|-------|--------|-------|
| `Double importance` | Record component | **Removed** |
| `Confidence confidence` | — | **New** nullable |

#### Converters

All converters (`ExperienceEvents`, `MoodEvents`, `RelationshipEvents`, `ReflectionEvents`, `EngagementEvents`) currently pass `importance` when constructing `MemoryInput`. They update to pass `Confidence`:

```java
// Before (ReflectionEvents):
new MemoryInput(entityId, domain, tenantId, null, text, attrs,
    Math.min(0.3 + level * 0.2, 1.0))

// After:
new MemoryInput(entityId, domain, tenantId, null, text, attrs,
    Confidence.unknown(Math.min(0.3 + level * 0.2, 1.0)))
```

#### `PersonalityWeightedRetrieval` and `MoodModulatedRetrieval`

Currently read `memory.importance()`. Update to read `memory.confidence()` — null-safe, using `confidence != null ? confidence.value() : defaultValue`.

#### Backends

**InMemoryMemoryStore:** Internal map value updates field name.

**SqliteMemoryStore:** Column rename `importance` → `confidence_value`. Add `confidence_origin` column (stores enum name, defaults to `UNKNOWN`). Flyway migration.

**JpaMemoryStore:** Entity field rename. Flyway migration for the PostgreSQL table.

**Mem0CaseMemoryStore / GraphitiCaseMemoryStore:** REST payload field mapping update.

### CBR (`memory-api`)

#### `CbrCase`

| Method | Before | After |
|--------|--------|-------|
| `Double confidence()` | Returns nullable Double | `Confidence confidence()` — returns nullable Confidence |
| `withOutcome(String, Double)` | Double confidence param | `withOutcome(String, Confidence)` |

#### `TextualCbrCase`, `FeatureVectorCbrCase`, `PlanCbrCase`

Record component `Double confidence` → `Confidence confidence` (nullable). Validation changes from manual `< 0.0 || > 1.0` check to relying on `Confidence` constructor validation. `withOutcome` signature updates.

#### `CbrOutcome.adjustConfidence`

```java
// Before:
public static double adjustConfidence(Double oldConfidence, double successRate,
                                      double learningRate)

// After:
public static Confidence adjustConfidence(Confidence old, double successRate,
                                          double learningRate, Instant observedAt) {
    double oldValue = old != null ? old.value() : 1.0;
    double newValue = (1.0 - learningRate) * oldValue + learningRate * successRate;
    ConfidenceOrigin origin = old != null ? old.origin() : ConfidenceOrigin.UNKNOWN;
    return new Confidence(origin, newValue, observedAt);
}
```

Preserves origin (how the case was originally established), updates value via EMA, sets decayReference to `observedAt`.

#### `OutcomeWeightingCbrCaseMemoryStore`

Currently reads `cbrCase.confidence()` as a Double for score modulation. Updates to read `cbrCase.confidence().value()`, null-guarded.

#### `ScoredCbrCase`

No change to the record itself — `ScoredCbrCase.score()` is a retrieval score, not a confidence value. `ScoredCbrCase.storedAt()` stays — it's an entity timestamp, distinct from `Confidence.decayReference`.

#### CBR Backends

**InMemoryCbrCaseMemoryStore:** `recordOutcome` updates — constructs `Confidence` from EMA result.

**QdrantCbrCaseMemoryStore:** Payload serialization — `confidence` field becomes a structured object `{origin, value, decayReference}` in Qdrant payload. `recordOutcome` updates.

**JpaCbrCaseMemoryStore:** Entity column changes + Flyway migration.

---

## Dependency Graph Change

```
Before:
  mindmap-api (zero deps)
  memory-api → fusion-api, platform-api

After:
  cognitive-api (zero deps)
  mindmap-api → cognitive-api
  memory-api → cognitive-api, fusion-api, platform-api
```

Both `mindmap-api` and `memory-api` gain a dependency on the new tier-0 module. `cognitive-api` has no dependencies — it is pure Java records and enums.

---

## What Does NOT Change

- **`CbrOutcome` record** stays in `memory-api` — it carries CBR-specific fields (result, successRate, detail, observedAt)
- **`MindMapNode.updatedAt()`** stays — it's an entity audit timestamp
- **`ScoredCbrCase`** record is unchanged — `score()` is a retrieval ranking signal, not a confidence value
- **`MindMapQuery.minConfidence` and `MindMapQuery.confidenceOrigin`** stay as separate query predicates
- **`TemporalDecay`** (memory-api) is unrelated — it's post-scoring retrieval decay, not knowledge confidence decay
- **`MoodState` PAD values** are affect, not confidence — orthogonal (#238)

---

## Validation

The `Confidence` constructor uses the inverted range check pattern:

```java
if (!(value >= 0.0 && value <= 1.0)) {
    throw new IllegalArgumentException("value must be in [0,1], got: " + value);
}
```

This structurally rejects `Double.NaN` via IEEE 754 semantics — `NaN >= 0.0` is `false`, so `!(false && ...)` is `true`, and the guard fires. Explicit `Double.isNaN()` is not needed.

---

## Testing Strategy

1. **cognitive-api:** Unit tests for `Confidence` — construction, validation (boundary values, NaN rejection), factory methods, `withValue`/`withDecayReference`
2. **mindmap-api:** `MindMapStoreContractTest` updates (72 tests) — all test helpers and assertions migrate
3. **memory-api:** `CbrCaseMemoryStoreContractTest` updates (151 tests) — confidence field changes
4. **memory-testing:** `CbrOutcomeTest` — `adjustConfidence` now returns `Confidence`
5. **Backends:** Each backend's integration tests verify persistence of the three Confidence components (origin, value, decayReference)
6. **Decorators:** `ConfidenceDecayDecoratorTest` — decay reads `decayReference` from `Confidence`, not `confirmedAt`/`updatedAt`

---

## References

- [cognitive-architecture-roadmap.md §1a](../../docs/guides/cognitive-architecture-roadmap.md) — original design direction
- [cognitive-coherence-audit.md §Dimension 1](../../docs/guides/cognitive-coherence-audit.md) — identifies the three-model gap
- [GE-20260604-043617] — NaN silently passes range guards; inverted check pattern
- [GE-20260722-a9b61b] — ScoredCbrCase.score vs EnsemblePlan.ensembleConfidence range mismatch
- [ConfidenceOrigin.java](../../mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ConfidenceOrigin.java) — current enum
- [ConfidenceDecayDecorator.java](../../mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/ConfidenceDecayDecorator.java) — current decay logic
- [CbrOutcome.java](../../memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrOutcome.java) — current EMA
- [MemoryInput.java](../../memory-api/src/main/java/io/casehub/neocortex/memory/MemoryInput.java) — current importance field
- [decisions.md](decisions.md) — D1-D7 captured decisions

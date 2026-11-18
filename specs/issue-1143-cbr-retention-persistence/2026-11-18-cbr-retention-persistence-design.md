# CBR Persistence for Learned Retention Parameters

**Issue:** casehubio/neocortex#1143
**Date:** 2026-11-18
**Status:** Draft
**Parent:** casehubio/neocortex#1119 (Memory Hygiene Parameter Adaptation)

## Problem

`HygieneAdaptationPhase` (#1119) adjusts `retentionThreshold` via step-based adaptation with direction tracking. `AdaptiveRetentionConfig` holds the current config in an `AtomicReference<RetentionConfig>`, always starting from `RetentionConfig.DEFAULT` (threshold=0.1) on restart. Learned parameters are lost on every restart, forcing the system to re-converge from defaults each time.

For long-running deployments this is wasteful — a threshold that took dozens of consolidation ticks to converge is discarded and must be rediscovered. CBR persistence allows the system to resume from its last known-good configuration.

## Design

### Overview

Extend `HygieneAdaptationPhase` with two CBR operations:

1. **Retain:** When a config has been stable (held in target range) for N consecutive ticks, store it as a `CbrFeatureRecord` with workload context features.
2. **Retrieve:** On first tick per tenant, query CBR for the best prior config and seed `AdaptiveRetentionConfig` instead of leaving it at DEFAULT.

```
HygieneAdaptationPhase
    │
    ├─ First tick per tenant:
    │   ├─ Query CBR for retention-config cases (tenant-scoped)
    │   ├─ If match above minSimilarity → seed AdaptiveRetentionConfig
    │   └─ Store baseline summary (existing behaviour)
    │
    ├─ Subsequent ticks (existing adaptation logic):
    │   ├─ LOWERED / RAISED → reset stability counter
    │   └─ HELD (pressure in target range) → increment stability counter
    │       └─ If counter >= stabilityThreshold (default 3):
    │           ├─ Store CbrFeatureRecord
    │           ├─ Supersede previous case for this tenant
    │           ├─ Record CbrOutcome.SUCCESS on stored case
    │           └─ Reset counter
    │
    └─ After retrieval, if retrieved config leads to instability:
        └─ Normal adaptation takes over (step-based correction)
```

### CBR Schema

Case type: `"retention-config"`

```java
CbrRecordSchema.of("retention-config",
    new FeatureField.Numeric("evictionPressure", 0.0, 1.0),
    new FeatureField.Numeric("totalScored", 0, 100_000),
    new FeatureField.Numeric("consolidationGroups", 0, 10_000));
```

**Features rationale:**
- `evictionPressure` — the quality signal the adaptation responds to; primary discriminator for matching configs to workload conditions
- `totalScored` — memory volume; a threshold optimal for 100 memories may not suit 10,000
- `consolidationGroups` — number of merge-worthy memory clusters; indicates memory diversity

### CbrFeatureRecord Content

- **problem:** `"retention threshold <value> at pressure <value> for <totalScored> memories"` — descriptive text, not used for similarity (FEATURE_ONLY retrieval)
- **solution:** `"retentionThreshold=<value>"` — the learned parameter value
- **outcome:** null initially; `CbrOutcome.SUCCESS` recorded when stability is confirmed
- **confidence:** `Confidence(ConfidenceOrigin.INFERRED, 1.0, null)` — starts high, adjusted by EMA on outcome recording
- **features:** `{evictionPressure: <value>, totalScored: <value>, consolidationGroups: <value>}`

### Retrieval Query

```java
CbrQuery.of(tenantId, DOMAIN, Path.root(), "retention-config",
            Map.of("evictionPressure", FeatureValue.number(currentPressure),
                   "totalScored", FeatureValue.number(totalScored),
                   "consolidationGroups", FeatureValue.number(consolidationGroups)),
            1)  // topK=1
    .withMinSimilarity(0.3)
    .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
```

Low `minSimilarity` (0.3) because even a loosely matching prior config is likely better than DEFAULT. The adaptation will correct any mismatch within a few ticks.

### Supersession

When a new stable config is stored, supersede the previous case for this tenant:

1. Query `findCaseIds()` for existing `retention-config` cases in the tenant
2. `supersede(oldCaseId, newCaseId, "newer stable config", tenantId)`

One active case per tenant at any time. Superseded cases are retained for audit but excluded from retrieval.

### Tenant Isolation

Cases are stored and retrieved with `tenantId` — the CbrRecordStore enforces isolation at the storage layer. No cross-tenant retrieval. No global fallback. New tenants start from DEFAULT until their own adaptation stabilises (cold-start is acceptable; the step-based adaptation converges within a few cycles).

### Modified Types

#### `HygieneAdaptationPhase` (cognition)

New dependencies (via `Instance<>` for graceful degradation):
- `Instance<CbrRecordStore>` — optional; when absent, persistence is silently skipped

New internal state:
- `ConcurrentHashMap<String, Integer> stabilityCounters` — per-tenant tick counter for stability detection
- `ConcurrentHashMap<String, String> activeCaseIds` — per-tenant tracking of the current active CBR case ID for supersession

New config properties (added to `HygieneAdaptationConfig`):
- `stabilityThreshold` (int, default 3) — consecutive held ticks before storing a case
- `cbrMinSimilarity` (double, default 0.3) — minimum similarity for startup retrieval

New behaviour:
1. **Schema registration:** `@PostConstruct` registers the `retention-config` schema if CbrRecordStore is available
2. **First-tick retrieval:** Before the existing baseline return, query CBR. If match found, call `adaptiveConfig.update(matchedConfig)` and use it as the baseline
3. **Stability tracking:** When a tick results in HELD (no adaptation), increment the stability counter. When LOWERED or RAISED, reset it to 0
4. **Case storage:** When counter reaches `stabilityThreshold`, store the current config as a CbrFeatureRecord, supersede the previous case, record SUCCESS outcome, reset counter

#### `HygieneAdaptationConfig` (cognition)

Two new config properties:
```java
@WithDefault("3")
int stabilityThreshold();

@WithDefault("0.3")
double cbrMinSimilarity();
```

### Scope Boundaries

**In scope:**
- Stability detection in HygieneAdaptationPhase
- CBR schema registration for retention-config case type
- Case storage on stability confirmation
- Startup retrieval and config seeding on first tick
- Supersession of previous cases
- Config properties for stability threshold and CBR min similarity
- Unit tests for all new behaviour

**Out of scope:**
- Cross-tenant metadata aggregation (future analytics concern)
- Per-agent RetentionConfig adaptation (#1144)
- Weight parameter persistence (weights are personality-driven, not workload-driven)
- CbrOutcome.FAILURE recording on instability after retrieval (normal adaptation handles correction; failure recording is a refinement for a future iteration)

## Testing

- **Stability counter:** Verify counter increments on HELD, resets on LOWERED/RAISED, triggers storage at threshold
- **Case storage:** Verify CbrFeatureRecord is stored with correct features, problem/solution text, and confidence
- **Startup retrieval:** Given a pre-stored case, verify first tick seeds AdaptiveRetentionConfig with the matched config instead of DEFAULT
- **No CBR graceful degradation:** When CbrRecordStore is not available, verify the phase behaves exactly as before (no errors, no persistence)
- **Supersession:** Verify old case is superseded when new stable config is stored
- **Tenant isolation:** Verify cases stored for tenant A are not retrieved for tenant B

## References

- casehubio/neocortex#1119 — parent implementation (HygieneAdaptationPhase)
- casehubio/neocortex#1143 — this issue
- Design spec: `specs/issue-1119-hygiene-adaptation-phase/2026-11-18-hygiene-adaptation-phase-design.md`
- Decision D2 (revised) from #1119: acknowledged no persistence in v1
- BehavioralSynthesisPhase (mindmap-intelligence) — CBR outcome pattern template
- CbrRecordStore SPI (memory-api) — store/retrieve/supersede API
- CbrFeatureRecord (memory-api) — feature-vector CBR record type
- HygieneAdaptationPhaseTest (cognition) — existing test patterns

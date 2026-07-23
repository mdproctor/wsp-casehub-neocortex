# CBR Trust-Weighted Retention — Design Spec

**Issue:** casehubio/neocortex#154
**Date:** 2026-07-23
**Status:** Draft

## Problem

CBR retrieval scores cases by feature similarity, outcome confidence, and cross-encoder
reranking — but ignores the authority of the source that produced the case. A case
created by a highly trusted agent should carry more weight than one from an untrusted
agent, and an agent whose trust has been declining since the decision should produce
less authoritative precedents.

The ledger already computes per-agent, per-capability trust scores (`TrustScoreSource`
SPI in `casehub-ledger-api`), consumed by engine routing strategies. CBR needs to
bridge this signal into retrieval scoring without creating a direct dependency on ledger.

## Design

### Model Changes (memory-api)

**CbrCase interface** — two new methods with null defaults:

```java
default Double trustScore() { return null; }
default String producerAgentId() { return null; }
```

`trustScore` is the source authority at decision time — a snapshot of the producing
agent's trust when the case was stored. Immutable after creation. Nullable (unknown
trust is valid — the decorator skips weighting for null). Validated in [0,1] when
non-null — same constraint as `confidence`.

`producerAgentId` is intrinsic provenance — identifies who produced this case, for
trajectory lookup at retrieval time. Nullable (trajectory is skipped without it).

**FeatureVectorCbrCase:**

```java
public record FeatureVectorCbrCase(
    String problem, String solution,
    String outcome, Double confidence,
    Map<String, FeatureValue> features,
    Double trustScore, String producerAgentId
) implements CbrCase { ... }
```

`withOutcome()` and `withFeatures()` preserve both fields.

**PlanCbrCase:**

```java
public record PlanCbrCase(
    String problem, String solution,
    String outcome, Double confidence,
    Map<String, FeatureValue> features,
    List<PlanTrace> planTrace,
    Double trustScore, String producerAgentId
) implements CbrCase { ... }
```

**TextualCbrCase:**

```java
public record TextualCbrCase(
    String problem, String solution,
    String outcome, Double confidence,
    Double trustScore, String producerAgentId
) implements CbrCase { ... }
```

### AgentTrustProvider SPI (memory-api)

```java
package io.casehub.neocortex.memory.cbr;

import java.util.OptionalDouble;

@FunctionalInterface
public interface AgentTrustProvider {
    OptionalDouble currentTrustScore(String agentId);
}
```

Provides the agent's current trust score for trajectory computation. Implementations
bridge to the ledger's `TrustScoreSource.globalScore(actorId)` or any other trust
source.

No `@DefaultBean` no-op — the decorator injects `Instance<AgentTrustProvider>` and
checks `isResolvable()`. If absent, trajectory is disabled (authority-only mode). A
no-op would mask the absence.

### TrustWeightingFunction (memory-api)

```java
package io.casehub.neocortex.memory.cbr;

import java.util.OptionalDouble;

@FunctionalInterface
public interface TrustWeightingFunction {
    double apply(double similarity, double trustScore, OptionalDouble trustTrajectory);
}
```

Analogous to `OutcomeWeightingFunction(double similarity, double confidence)`. The
trajectory is the delta between stored trust and current trust (negative = declining).

### DefaultTrustWeightingFunction (memory module, @DefaultBean)

```java
@DefaultBean
@ApplicationScoped
public class DefaultTrustWeightingFunction implements TrustWeightingFunction {

    private final double influence;
    private final double trajectorySensitivity;

    @Inject
    DefaultTrustWeightingFunction(TrustWeightingConfig config) {
        this.influence = config.influence();
        this.trajectorySensitivity = config.trajectorySensitivity();
    }

    @Override
    public double apply(double similarity, double trustScore,
                        OptionalDouble trustTrajectory) {
        double weighted = similarity * (1.0 - influence + influence * trustScore);
        if (trustTrajectory.isPresent()) {
            double delta = trustTrajectory.getAsDouble();
            if (delta < 0) {
                weighted *= Math.max(0.5, 1.0 + trajectorySensitivity * delta);
            }
        }
        return weighted;
    }
}
```

**Authority formula:** `score * (1 - α + α * trustScore)` — same linear interpolation
as `DefaultOutcomeWeightingFunction`. With α=0.3 and trustScore=0.8: score * 0.94.
With trustScore=0.2: score * 0.76.

**Trajectory formula:** only applied when delta is negative (declining trust). Multiplier:
`max(0.5, 1.0 + β * delta)` where β=0.5 (default). A -0.4 trust decline → multiplier
0.8. Floor at 0.5 prevents complete zeroing.

Improving trust (positive delta) is ignored — the stored snapshot already captured the
authority at decision time. If the agent improved since then, that doesn't retroactively
make this specific decision better.

### TrustWeightingConfig (memory module)

```java
@ConfigMapping(prefix = "casehub.cbr.trust-weighting")
public interface TrustWeightingConfig {
    @WithDefault("false")
    boolean enabled();

    @WithDefault("0.3")
    double influence();

    @WithDefault("0.5")
    double trajectorySensitivity();
}
```

### TrustWeightedCbrCaseMemoryStore (memory module)

```java
@Decorator
@Priority(60)
@IfBuildProperty(name = "casehub.cbr.trust-weighting.enabled", stringValue = "true")
public class TrustWeightedCbrCaseMemoryStore implements CbrCaseMemoryStore {

    private final CbrCaseMemoryStore delegate;
    private final TrustWeightingFunction weightingFunction;
    private final AgentTrustProvider trustProvider;

    @Inject
    TrustWeightedCbrCaseMemoryStore(
            @Delegate @Any CbrCaseMemoryStore delegate,
            TrustWeightingFunction weightingFunction,
            Instance<AgentTrustProvider> trustProviderInstance) {
        this.delegate = delegate;
        this.weightingFunction = weightingFunction;
        this.trustProvider = trustProviderInstance.isResolvable()
                ? trustProviderInstance.get() : null;
    }
```

**retrieveSimilar():**

```java
@Override
public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(
        CbrQuery query, Class<C> caseClass) {
    List<ScoredCbrCase<C>> results = delegate.retrieveSimilar(query, caseClass);
    if (results.isEmpty()) return results;

    List<ScoredCbrCase<C>> weighted = new ArrayList<>(results.size());
    for (ScoredCbrCase<C> scored : results) {
        Double trust = scored.cbrCase().trustScore();
        if (trust == null) {
            weighted.add(scored);
            continue;
        }
        OptionalDouble trajectory = computeTrajectory(scored.cbrCase());
        double newScore = weightingFunction.apply(scored.score(), trust, trajectory);
        weighted.add(scored.withScore(newScore));
    }
    weighted.sort((a, b) -> Double.compare(b.score(), a.score()));
    return Collections.unmodifiableList(weighted);
}

private OptionalDouble computeTrajectory(CbrCase cbrCase) {
    if (trustProvider == null || cbrCase.producerAgentId() == null
            || cbrCase.trustScore() == null) {
        return OptionalDouble.empty();
    }
    OptionalDouble current = trustProvider.currentTrustScore(
            cbrCase.producerAgentId());
    if (current.isEmpty()) return OptionalDouble.empty();
    return OptionalDouble.of(current.getAsDouble() - cbrCase.trustScore());
}
```

**Reactive parity:** `ReactiveTrustWeightedCbrCaseMemoryStore` with same logic,
`@Decorator @Priority(60)`, same `@IfBuildProperty` gate.

**Decorator chain after this change:**

```
Tracking@50 → TrustWeighting@60 → OutcomeWeighting@65 → Reranking@75
→ ScopeDecay@85 → TrendEnrichment@90 → Base
```

### Backend Changes

**InMemoryCbrCaseMemoryStore:** `StoredCase` internal record gains `trustScore` and
`producerAgentId` fields. Written at store time, returned on CbrCase at retrieval.

**ReactiveQdrantCbrCaseMemoryStore:** Two new payload fields in `CbrPointBuilder`:
- `trust_score` (double, nullable)
- `producer_agent_id` (string, nullable)

Read at retrieval time, written at store time. No collection schema change (payload
fields are schemaless in Qdrant).

**JpaCbrCaseMemoryStore:** Two new nullable columns on `CbrCaseEntity`:
- `trust_score DOUBLE`
- `producer_agent_id VARCHAR(255)`

Flyway migration adds two nullable columns — no data backfill needed.

### Contract Tests

`CbrCaseMemoryStoreContractTest` gains:

| Test | What it verifies |
|------|-----------------|
| `trustScore_roundTrip` | Store FeatureVectorCbrCase with trustScore=0.85, retrieve, verify trustScore=0.85 |
| `producerAgentId_roundTrip` | Store with producerAgentId="agent-1", retrieve, verify |
| `trustScore_nullPreserved` | Store with null trustScore, retrieve, verify null |
| `trustScore_withOutcome_preserved` | Store with trustScore, recordOutcome, retrieve, verify trustScore unchanged |

### What This Does NOT Include

- **Engine wiring** — `CbrCaseRetainObserver` passing trust from routing context to CbrCase constructor. Separate issue on engine repo.
- **AgentTrustProvider implementation** — bridging `TrustScoreSource` to `AgentTrustProvider`. Separate issue on engine/ledger repo.
- **Trust-based retention policies** — purging low-trust cases. Future work if needed.

These are consumer-side concerns. Neocortex provides the SPI and decorator; consumers provide the trust data and bridge implementation.

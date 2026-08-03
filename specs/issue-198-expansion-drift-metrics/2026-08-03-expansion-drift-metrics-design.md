# Expansion Drift Metrics — Auto-Fallback When Expanded Query Drifts

**Issue:** #198
**Parent epic:** #115 (regression-free query expansion)
**Date:** 2026-08-03
**Status:** Approved

## Context

`QueryExpandingCaseRetriever` fans out expanded queries (HyDE hypothetical
documents, step-back abstractions, template reformulations) and fuses results
via RRF. Two of three #115 children are done: the original query is always
prepended to the expanded set (#119), and per-leg embedding separation routes
`searchText()` to dense and `text()` to sparse/BM25 (#113).

The remaining gap is observability and safety: when HyDE generates a
hypothetical document that drifts semantically from the original query,
retrieval quality degrades. There is no signal that this happened — the
drifted expansion silently dilutes RRF fusion. This spec adds drift
detection, logging, metering, and configurable auto-fallback.

## Design

### Placement

Drift detection lives inside `QueryExpandingCaseRetriever` as a
post-expansion quality gate. It runs after `expander.expand(query)` returns
and the original query is ensured present, but before the fan-out loop.
This is the natural location — expanded queries are local to this method
and never cross a SPI boundary.

### Drift Measurement

Dense embedding cosine similarity between the original query and each
expanded query:

1. Compute `EmbeddingModel.embedAll([original.text(), expanded[0].searchText(), expanded[1].searchText(), ...])`
   — one batch call, not N separate `embed()` calls.
2. Cosine similarity = dot(a, b) / (||a|| * ||b||). Pure Java, no library.
3. Compare each similarity against the configured threshold.

### Embedding Model Dependency

`EmbeddingModel` injected via CDI `Instance<EmbeddingModel>` — optional.
`rag-expansion` already depends on `langchain4j-core` transitively via
`ChatModel` in `LlmQueryExpander`. `EmbeddingModel` is in the same artifact
— zero additional dependency cost.

If `Instance<EmbeddingModel>` is not resolvable:
- Drift detection is silently disabled regardless of config.
- `ExpansionConfigValidator` warns at startup if `drift.enabled=true` but
  no `EmbeddingModel` is available.

### Config-Driven Behavior

```properties
casehub.rag.expansion.drift.enabled=false         # master switch
casehub.rag.expansion.drift.threshold=0.7          # cosine similarity floor
casehub.rag.expansion.drift.action=observe         # observe | drop
```

| `drift.enabled` | `EmbeddingModel` available | Behavior |
|------------------|---------------------------|----------|
| `false` | any | No drift detection (zero overhead) |
| `true` | no | Startup warning, no drift detection |
| `true` | yes | Active — observe or drop per `action` |

**Observe mode:** Log similarity at FINE for every expanded query. Log at
WARNING when similarity falls below threshold. Record Micrometer metrics.
All expansions proceed to fan-out — no behavioral change.

**Drop mode:** Same logging and metrics as observe. Additionally, remove
expanded queries whose similarity falls below threshold. If all expansions
are removed, the original query alone survives (the safety net from #119
guarantees it is always present). The single-query fast path already handles
this case — no special logic needed.

### Metrics

Three Micrometer instruments, all tagged by expansion `mode` (llm,
step-back, template) when detectable from the `QueryExpander` implementation
class name:

| Instrument | Type | Description |
|-----------|------|-------------|
| `casehub.rag.expansion.drift` | DistributionSummary | Cosine similarity per expanded query |
| `casehub.rag.expansion.drift.fallback` | Counter | Expansions dropped (drop mode only) |
| `casehub.rag.expansion.total` | Counter | Total expansion events (denominator) |

`MeterRegistry` injected via `Instance<MeterRegistry>` — optional. If not
resolvable, metrics are skipped but logging still operates.

### Code Changes

**`QueryExpandingCaseRetriever`:**
- New constructor params: `Instance<EmbeddingModel>`, `Instance<MeterRegistry>`,
  `ExpansionConfig`.
- New private method: `filterByDrift(RetrievalQuery original, List<RetrievalQuery> expanded)`
  — returns filtered list. Observe mode returns input unchanged. Drop mode
  removes entries below threshold.
- Call site: between "ensure original present" and fan-out loop.

**`ExpansionConfig`:**
```java
interface DriftConfig {
    @WithDefault("false")
    boolean enabled();

    @WithDefault("0.7")
    double threshold();

    @WithDefault("observe")
    String action();  // "observe" | "drop"
}

DriftConfig drift();
```

**`ExpansionConfigValidator`:**
Extended to check `drift.enabled && !embeddingModel.isResolvable()` →
startup warning: "Drift detection enabled but no EmbeddingModel available —
drift detection will be inactive."

### Dependencies

`rag-expansion/pom.xml`:
- `dev.langchain4j:langchain4j-core` — make explicit (already transitive via
  `rag-api`). Provides `EmbeddingModel`.
- `io.micrometer:micrometer-core` — `provided` scope (Quarkus supplies at
  runtime).

No new external dependencies.

## Testing

All tests in `QueryExpandingCaseRetrieverTest` using a stub `EmbeddingModel`
that returns deterministic vectors (hash-based) to control similarity values:

| Test | Mode | Assertion |
|------|------|-----------|
| Drift below threshold | observe | All expansions proceed, meter records similarity |
| Drift above threshold | observe | All expansions proceed (no drop), meter records |
| Drift above threshold | drop | Drifted expansion removed, original survives, fallback counter incremented |
| All expansions drift | drop | All removed, original alone survives via single-query fast path |
| No EmbeddingModel | any | Drift detection skipped, expansion works as before |
| Drift disabled | any | Drift detection skipped regardless of EmbeddingModel |
| Batch embedding | any | Single `embedAll()` call, not N separate `embed()` calls |

## Non-Goals

- Drift detection for non-embedding similarity (text overlap, token Jaccard).
  Cosine similarity on dense embeddings is the right measure for semantic drift.
- Per-expansion-mode thresholds. A single threshold is sufficient — mode-specific
  tuning can be added later if data warrants it.
- Persisting drift history. Micrometer metrics and log output are sufficient
  for the observe phase. A drift history store is overengineering at this stage.

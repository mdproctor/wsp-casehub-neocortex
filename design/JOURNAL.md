# Design Journal — issue-31-matryoshka-binary-quantization

### Dual-vector tiered search rejected — Qdrant native quantization sufficient · §4 Solution Strategy

Evaluated storing a second truncated+binary-quantized named vector per point for tiered search (binary first-pass → full-precision rescore). At CaseHub's per-tenant scale (<1M vectors per collection), the binary index RAM savings (~112 bytes/vec) are offset by the wasted HNSW graph on the unused full "dense" vector (~128 bytes/vec). Dual-vector pays off at 10M+ vectors per collection. Instead, Qdrant's native server-side quantization provides tiered search transparently — binary index for fast candidate selection, float32 rescore for accuracy — with zero search query changes.

### EmbeddingModel decorator over standalone utility · §4 Solution Strategy

Matryoshka truncation implemented as a LangChain4j `EmbeddingModel` decorator rather than a standalone `float[]` utility. The decorator makes `dimension()` return the truncated size, which flows transparently to `ensureCollection()` — collection vector dimensions are automatically correct. The alternative (standalone utility + manual dimension tracking) would require coordinating truncation across ingestors, retrievers, and collection creation. The decorator centralises this in one place.

### DenseQuantization naming — QuantizationType collision · §8 Crosscutting Concepts

Named the config enum `DenseQuantization` instead of `QuantizationType` because Qdrant client 1.18.1 already defines `io.qdrant.client.grpc.Collections.QuantizationType` (values: `UnknownQuantization`, `Int8`, `UNRECOGNIZED`). Both enums appear in `ensureCollection()` and `buildCreateRequest()` — sharing the name would create ambiguous unqualified usage.

### Reactive denseDimension bug — pre-existing, fixed · §7 Deployment View

`ReactiveRagBeanProducer.@PostConstruct` captured `denseDimension` from the raw CDI-injected `embeddingModel`, not the effective (wrapped) model. With Matryoshka wrapping active, this would create collections with the wrong dimension. Fixed by removing the `denseDimension` constructor parameter from `ReactiveQdrantEmbeddingIngestor` — the ingestor now computes dimension from its `embeddingModel` argument in the constructor. The cached field is retained (not eliminated) because `buildCreateRequest()` runs on Qdrant's gRPC callback thread via `directExecutor()` — calling `embeddingModel.dimension()` there risks blocking.

### Search-time oversampling on dense leg only · §6 Runtime View

Qdrant's default oversampling (1.0) is insufficient for binary quantization — hamming distance is a coarse approximation. Added configurable oversampling via `SearchParams.QuantizationSearchParams` on the dense prefetch leg. Applied to both hybrid (RRF) and dense-only code paths. Sparse prefetch is unaffected — sparse vectors are not quantized. `rescore` is hardcoded to `true` because oversampling without rescoring wastes I/O.

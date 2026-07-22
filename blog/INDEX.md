# Blog — casehub-neocortex

| Entry | Date | Summary |
|-------|------|---------|
| [2026-06-06-mdp01-native-image-gate.md](2026-06-06-mdp01-native-image-gate.md) | 2026-06-06 | Native image gate PASS — ONNX Runtime + DJL Tokenizers JNI validated in Quarkus native on macOS ARM |
| [2026-06-07-mdp02-spi-that-argued-back.md](2026-06-07-mdp02-spi-that-argued-back.md) | 2026-06-07 | InferenceModel SPI foundation — four design departures from the Hortora spec, earned through review |
| [2026-06-08-mdp03-qualifier-naming.md](2026-06-08-mdp03-qualifier-naming.md) | 2026-06-08 | CDI wiring for inference — @Inference qualifier naming, InjectionPoint producer pattern, SPLADE adapter |
| [2026-06-08-mdp03-floats-meaning.md](2026-06-08-mdp03-floats-meaning.md) | 2026-06-08 | inference-tasks layer — NLI, classification, regression, reranking task adapters that give raw ONNX floats meaning |
| [2026-06-09-mdp04-rag-pipeline-unified-qdrant.md](2026-06-09-mdp04-rag-pipeline-unified-qdrant.md) | 2026-06-09 | RAG pipeline — unified Qdrant gRPC, hybrid RRF fusion, tenancy strategy, reactive SPIs |
| [2026-06-09-mdp05-protocol-vs-codebase.md](2026-06-09-mdp05-protocol-vs-codebase.md) | 2026-06-09 | Protocol vs codebase divergence — reactive SPI conflicts, Mutiny adoption decisions for RAG pipeline |
| [2026-06-10-mdp05-bridge-is-the-problem.md](2026-06-10-mdp05-bridge-is-the-problem.md) | 2026-06-10 | Native reactive Qdrant — ListenableFuture→Uni bridge, memoize failure caching, @Startup producer gate |
| [2026-06-12-mdp06-storage-layer-that-wasnt-there.md](2026-06-12-mdp06-storage-layer-that-wasnt-there.md) | 2026-06-12 | Corpus storage module design — ZIP-backed rolling archives, chain integrity, CorpusStore→EmbeddingIngestor rename |
| [2026-06-12-mdp07-fifty-six-files-and-a-hash-bug.md](2026-06-12-mdp07-fifty-six-files-and-a-hash-bug.md) | 2026-06-12 | Corpus implementation — 56 files, 136 tests, hash ordering bug, versioned ZIP entries, zero-dep JSON |
| [2026-06-13-mdp08-four-reviews-and-a-fake-class.md](2026-06-13-mdp08-four-reviews-and-a-fake-class.md) | 2026-06-13 | Ingestion bridge — ChangeSource→chunk→embed→Qdrant, four spec review rounds, assertTenant fix, EmbeddingModel≠TokenCountEstimator |
| [2026-06-14-mdp09-showing-the-work.md](2026-06-14-mdp09-showing-the-work.md) | 2026-06-14 | Examples project — two demo modules, architecture justification with cited benchmarks, 23 smoke tests |
| [2026-06-15-mdp10-trailing-edges.md](2026-06-15-mdp10-trailing-edges.md) | 2026-06-15 | Post-review cleanup — langchain4j-embeddings versioning gotcha, CorpusTestSupport API redesign, protocol scope extension |
| [2026-06-15-mdp11-six-wrong-fields.md](2026-06-15-mdp11-six-wrong-fields.md) | 2026-06-15 | Doc sync — ARC42 corpus layers written from memory had 6 wrong API names; code review caught all of them |
| [2026-06-18-mdp12-guard-that-isnt-a-guard.md](2026-06-18-mdp12-guard-that-isnt-a-guard.md) | 2026-06-18 | TenantGuard — deployment-time tenancy strategy replaces null-guards; ARC42 boundary shift for Hortora rag-* adoption |
| [2026-06-18-mdp13-fifteen-branches-and-nine-missing-posts.md](2026-06-18-mdp13-fifteen-branches-and-nine-missing-posts.md) | 2026-06-18 | Code review fixes (#37), cross-repo branch audit, blog-routing.yaml for all 15 casehub workspaces, 9 unpublished entries recovered |
| [2026-06-20-mdp14-guard-that-wasnt-obvious.md](2026-06-20-mdp14-guard-that-wasnt-obvious.md) | 2026-06-20 | CRAG idempotency — CDI decorator ordering, reactive bridge, corrective RAG quality gating |
| [2026-06-23-mdp15-string-that-did-three-jobs.md](2026-06-23-mdp15-string-that-did-three-jobs.md) | 2026-06-23 | Query string overloading — one string carrying original query, hypothetical doc, and retrieval key in HyDE |
| [2026-06-24-mdp16-gate-that-didnt-need-opening.md](2026-06-24-mdp16-gate-that-didnt-need-opening.md) | 2026-06-24 | JVM mode by design — native image gate passed but service doesn't need it; cross-repo doc sync |
| [2026-06-25-mdp17-query-expansion-grows-up.md](2026-06-25-mdp17-query-expansion-grows-up.md) | 2026-06-25 | Query expansion module — step-back, HyDE, multi-query fan-out with RRF fusion |
| [2026-06-26-mdp18-embedall-batching.md](2026-06-26-mdp18-embedall-batching.md) | 2026-06-26 | embedAll batching — first-principles rethink of embedding batch API for Qdrant ingestion |
| [2026-06-27-mdp17-matryoshka-and-the-math-that-didnt-add-up.md](2026-06-27-mdp17-matryoshka-and-the-math-that-didnt-add-up.md) | 2026-06-27 | Matryoshka embeddings — dimension truncation math, binary quantization, Qdrant collection config |
| [2026-06-29-mdp01-index-qdrant-wont-build.md](2026-06-29-mdp01-index-qdrant-wont-build.md) | 2026-06-29 | Qdrant payload indexes — full-text on content (Word tokenizer for Java identifiers), keyword on tenantId/sourceDocumentId |
| [2026-06-30-mdp01-three-legs-flat-namespace.md](2026-06-30-mdp01-three-legs-flat-namespace.md) | 2026-06-30 | Three-leg hybrid search — BM25 as third retrieval leg, flat Qdrant namespace, metadata strategy |
| [2026-06-30-mdp02-the-memory-that-retrieves.md](2026-06-30-mdp02-the-memory-that-retrieves.md) | 2026-06-30 | CBR architecture — case-based reasoning as memory that retrieves, Qdrant-backed similarity search |
| [2026-07-01-mdp01-the-rename-that-touched-everything.md](2026-07-01-mdp01-the-rename-that-touched-everything.md) | 2026-07-01 | neural-text → neocortex — full rename: repo, 28 module artifactIds, all Java packages, parent repo CI/docs |
| [2026-07-01-mdp03-the-great-memory-migration.md](2026-07-01-mdp03-the-great-memory-migration.md) | 2026-07-01 | Memory migration — CaseMemoryStore SPI moved from platform to neocortex, cross-repo coordination |
| [2026-07-02-mdp01-the-remote-that-pointed-somewhere-else.md](2026-07-02-mdp01-the-remote-that-pointed-somewhere-else.md) | 2026-07-02 | Completing the rename — GitHub repos, directories, remotes, symlinks; workspace remote gotcha |
| [2026-07-03-mdp01-the-score-was-always-there.md](2026-07-03-mdp01-the-score-was-always-there.md) | 2026-07-03 | The score was always there |
| [2026-07-05-mdp01-cbr-reconciliation.md](2026-07-05-mdp01-cbr-reconciliation.md) | 2026-07-05 | CBR reconciliation — batch upsert, orphan cleanup, disaster recovery for Qdrant-backed CBR store |
| [2026-07-05-mdp02-features-are-not-filters.md](2026-07-05-mdp02-features-are-not-filters.md) | 2026-07-05 | Features are not filters |
| [2026-07-05-mdp02-nine-issues-one-branch.md](2026-07-05-mdp02-nine-issues-one-branch.md) | 2026-07-05 | Nine Issues, One Branch, and a Chicken-and-Egg Problem |
| [2026-07-06-mdp01-retrieval-tracking-spi.md](2026-07-06-mdp01-retrieval-tracking-spi.md) | 2026-07-06 | Retrieval tracking SPI — document usefulness measurement, frequency + outcome + feedback tracking |
| [2026-07-06-mdp02-the-alternative-that-didnt-replace-anything.md](2026-07-06-mdp02-the-alternative-that-didnt-replace-anything.md) | 2026-07-06 | @Alternative doesn't suppress injection point validation — NoOpQueryExpander @DefaultBean, explicit mode selection |
| [2026-07-06-mdp03-the-decorator-that-registered-but-never-fired.md](2026-07-06-mdp03-the-decorator-that-registered-but-never-fired.md) | 2026-07-06 | Arc decorators silently skip @Produces method beans — subclass generation requires managed beans |
| [2026-07-07-mdp01-why-records-cant-carry-behaviour.md](2026-07-07-mdp01-why-records-cant-carry-behaviour.md) | 2026-07-07 | SimilaritySpec sealed interface — why lambdas on records break value semantics, three-level precedence chain |
| [2026-07-08-mdp01-one-dependency-one-module.md](2026-07-08-mdp01-one-dependency-one-module.md) | 2026-07-08 | Module extraction — one dependency per module, cross-encoder separated from RAG core CDI wiring |
| [2026-07-09-mdp01-three-implementations-of-the-same-algorithm.md](2026-07-09-mdp01-three-implementations-of-the-same-algorithm.md) | 2026-07-09 | Three Implementations of the Same Algorithm |
| [2026-07-09-mdp02-the-api-that-wouldnt-evolve.md](2026-07-09-mdp02-the-api-that-wouldnt-evolve.md) | 2026-07-09 | The API That Wouldn't Evolve |
| [2026-07-10-mdp01-when-flat-features-arent-enough.md](2026-07-10-mdp01-when-flat-features-arent-enough.md) | 2026-07-10 | When Flat Features Aren't Enough |
| [2026-07-11-mdp01-when-flat-features-arent-enough-again.md](2026-07-11-mdp01-when-flat-features-arent-enough-again.md) | 2026-07-11 | When Flat Features Aren't Enough (Again) |
| [2026-07-12-mdp01-filling-in-the-cbr-gaps.md](2026-07-12-mdp01-filling-in-the-cbr-gaps.md) | 2026-07-12 | Five CBR enhancements — WarpingConstraint sealed interface, Itakura infeasibility, variable edit distance costs, NumericList+ContainsRange, AllOf polarity |
| [2026-07-12-mdp03-the-type-that-replaced-object.md](2026-07-12-mdp03-the-type-that-replaced-object.md) | 2026-07-12 | FeatureValue sealed type — replacing Map<String, Object> with typed values for CBR feature vectors |
| [2026-07-14-mdp01-the-missing-phase.md](2026-07-14-mdp01-the-missing-phase.md) | 2026-07-14 | CBR Reuse phase — PlanAdapter SPI for transforming retrieved plans into adapted plans for current context |
| [2026-07-14-mdp02-six-lines-of-boilerplate.md](2026-07-14-mdp02-six-lines-of-boilerplate.md) | 2026-07-14 | MemoryEmitter — fire-and-forget CDI service replacing six lines of boilerplate across three repos |
| [2026-07-14-mdp03-the-method-that-touched-twelve-files.md](2026-07-14-mdp03-the-method-that-touched-twelve-files.md) | 2026-07-14 | Four CBR small fixes — Boolean FeatureValue, purge retention API, temporal decay, decorator chain integration |
| [2026-07-14-mdp04-the-feature-half-built.md](2026-07-14-mdp04-the-feature-half-built.md) | 2026-07-14 | Trend detection layer — derived Numeric features from TimeSeries, TrendAnalyzer algorithms, enrichment decorator |
| [2026-07-19-mdp01-the-analysis-layer-that-lives-where-youd-least-expect.md](2026-07-19-mdp01-the-analysis-layer-that-lives-where-youd-least-expect.md) | 2026-07-19 | Retrieval analysis layer — pure computation in rag-api, findFeedback timestamp gotcha, quality signal classification |
| [2026-07-21-mdp01-tracing-the-wire.md](2026-07-21-mdp01-tracing-the-wire.md) | 2026-07-21 | CloudEvent outcome wiring — tracing platform dispatch, @CloudEventType qualifier, @Observes erratum |
| [2026-07-22-mdp01-when-the-obvious-architecture-is-wrong.md](2026-07-22-mdp01-when-the-obvious-architecture-is-wrong.md) | 2026-07-22 | Cross-plan ensemble adaptation — why the CBR literature says per-plan first, then ensemble; honest NoOp reporting |

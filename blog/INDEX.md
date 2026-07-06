# Blog — casehub-neocortex

| Entry | Date | Summary |
|-------|------|---------|
| [2026-06-06-mdp01-native-image-gate.md](2026-06-06-mdp01-native-image-gate.md) | 2026-06-06 | Native image gate PASS — ONNX Runtime + DJL Tokenizers JNI validated in Quarkus native on macOS ARM |
| [2026-06-07-mdp02-spi-that-argued-back.md](2026-06-07-mdp02-spi-that-argued-back.md) | 2026-06-07 | InferenceModel SPI foundation — four design departures from the Hortora spec, earned through review |
| [2026-06-08-mdp03-qualifier-naming.md](2026-06-08-mdp03-qualifier-naming.md) | 2026-06-08 | CDI wiring for inference — @Inference qualifier naming, InjectionPoint producer pattern, SPLADE adapter |
| [2026-06-09-mdp04-rag-pipeline-unified-qdrant.md](2026-06-09-mdp04-rag-pipeline-unified-qdrant.md) | 2026-06-09 | RAG pipeline — unified Qdrant gRPC, hybrid RRF fusion, tenancy strategy, reactive SPIs |
| [2026-06-10-mdp05-bridge-is-the-problem.md](2026-06-10-mdp05-bridge-is-the-problem.md) | 2026-06-10 | Native reactive Qdrant — ListenableFuture→Uni bridge, memoize failure caching, @Startup producer gate |
| [2026-06-12-mdp06-storage-layer-that-wasnt-there.md](2026-06-12-mdp06-storage-layer-that-wasnt-there.md) | 2026-06-12 | Corpus storage module design — ZIP-backed rolling archives, chain integrity, CorpusStore→EmbeddingIngestor rename |
| [2026-06-12-mdp07-fifty-six-files-and-a-hash-bug.md](2026-06-12-mdp07-fifty-six-files-and-a-hash-bug.md) | 2026-06-12 | Corpus implementation — 56 files, 136 tests, hash ordering bug, versioned ZIP entries, zero-dep JSON |
| [2026-06-13-mdp08-four-reviews-and-a-fake-class.md](2026-06-13-mdp08-four-reviews-and-a-fake-class.md) | 2026-06-13 | Ingestion bridge — ChangeSource→chunk→embed→Qdrant, four spec review rounds, assertTenant fix, EmbeddingModel≠TokenCountEstimator |
| [2026-06-14-mdp09-showing-the-work.md](2026-06-14-mdp09-showing-the-work.md) | 2026-06-14 | Examples project — two demo modules, architecture justification with cited benchmarks, 23 smoke tests |
| [2026-06-15-mdp10-trailing-edges.md](2026-06-15-mdp10-trailing-edges.md) | 2026-06-15 | Post-review cleanup — langchain4j-embeddings versioning gotcha, CorpusTestSupport API redesign, protocol scope extension |
| [2026-06-15-mdp11-six-wrong-fields.md](2026-06-15-mdp11-six-wrong-fields.md) | 2026-06-15 | Doc sync — ARC42 corpus layers written from memory had 6 wrong API names; code review caught all of them |
| [2026-06-18-mdp12-guard-that-isnt-a-guard.md](2026-06-18-mdp12-guard-that-isnt-a-guard.md) | 2026-06-18 | TenantGuard — deployment-time tenancy strategy replaces null-guards; ARC42 boundary shift for Hortora rag-* adoption |
| [2026-06-18-mdp13-fifteen-branches-and-nine-missing-posts.md](2026-06-18-mdp13-fifteen-branches-and-nine-missing-posts.md) | 2026-06-18 | Code review fixes (#37), cross-repo branch audit, blog-routing.yaml for all 15 casehub workspaces, 9 unpublished entries recovered |
| [2026-06-24-mdp16-gate-that-didnt-need-opening.md](2026-06-24-mdp16-gate-that-didnt-need-opening.md) | 2026-06-24 | JVM mode by design — native image gate passed but service doesn't need it; cross-repo doc sync |
| [2026-06-29-mdp01-index-qdrant-wont-build.md](2026-06-29-mdp01-index-qdrant-wont-build.md) | 2026-06-29 | Qdrant payload indexes — full-text on content (Word tokenizer for Java identifiers), keyword on tenantId/sourceDocumentId |
| [2026-07-01-mdp01-the-rename-that-touched-everything.md](2026-07-01-mdp01-the-rename-that-touched-everything.md) | 2026-07-01 | neural-text → neocortex — full rename: repo, 28 module artifactIds, all Java packages, parent repo CI/docs |
| [2026-07-02-mdp01-the-remote-that-pointed-somewhere-else.md](2026-07-02-mdp01-the-remote-that-pointed-somewhere-else.md) | 2026-07-02 | Completing the rename — GitHub repos, directories, remotes, symlinks; workspace remote gotcha |
| [2026-07-06-mdp02-the-alternative-that-didnt-replace-anything.md](2026-07-06-mdp02-the-alternative-that-didnt-replace-anything.md) | 2026-07-06 | @Alternative doesn't suppress injection point validation — NoOpQueryExpander @DefaultBean, explicit mode selection |
| [2026-07-06-mdp03-the-decorator-that-registered-but-never-fired.md](2026-07-06-mdp03-the-decorator-that-registered-but-never-fired.md) | 2026-07-06 | Arc decorators silently skip @Produces method beans — subclass generation requires managed beans |

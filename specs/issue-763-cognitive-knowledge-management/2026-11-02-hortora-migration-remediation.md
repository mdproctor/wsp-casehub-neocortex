# Hortora Engine Migration Remediation

> **Context:** The original implementation plan (Task 4) specified IntelliJ-based migration of Hortora's engine code into corpus-management. The previous session deviated by rewriting from scratch, producing partial reimplementations that lack 9 months of production maturity. This spec defines the recovery path.

**Decision:** D17 in decisions.md

---

## 1. Current State

- **corpus-management** has reimplementations: ChainWalkerFederatedSearch, ProvenanceStoreImpl, RetrieverCorpusSearch, CorpusReindexService (+ tests). These are thin approximations missing: HTTP federation, adaptive search, see-also expansion, feedback context, staleness reports, outcome tracking, collection migration.
- **corpus-management** also has genuinely new code: SqliteCorpusCatalogue, CoverDocumentParser, SqliteCorpusEntryStore, CoverDocumentGenerator, TranscriptCorpusInitializer, CorpusEntryPromoter, CorpusKnowledgePromptSection, all API types. These stay.
- **Hortora engine** has 34 source files and 22 test files, all untouched. 9 months of edge-case hardening.
- **IntelliJ workspace** is open with both projects.

## 2. Phase 1 — Delete Reimplementations

Delete from corpus-management (src/main AND src/test):
- `ChainWalkerFederatedSearch.java` + `ChainWalkerFederatedSearchTest.java`
- `ProvenanceStoreImpl.java` + `ProvenanceStoreImplTest.java`
- `RetrieverCorpusSearch.java` + `RetrieverCorpusSearchTest.java`
- `CorpusReindexService.java` + `CorpusReindexServiceTest.java`

Keep all other files — they are genuinely new.

## 3. Phase 2 — IntelliJ-Move Hortora Code

Use `ide_move_file` for each file. IntelliJ updates references in both projects automatically. After moving, generify: replace GardenConfig/garden-specific references with constructor params or CorpusRef.

### 3.1 Core Engine (move + generify)

| Hortora file | Target in corpus-management | Generification |
|---|---|---|
| `federation/ChainWalker.java` | `impl/ChainWalker.java` | FederationConfig → constructor param |
| `federation/RemoteGardenClient.java` | `impl/RemoteGardenClient.java` | Already generic |
| `federation/FederationConfig.java` | `impl/FederationConfig.java` | Already generic |
| `federation/FederationConfigParser.java` | `impl/FederationConfigParser.java` | Already generic |
| `provenance/ProvenanceStore.java` | `impl/ProvenanceStore.java` | GardenConfig.id() → CorpusRef param |
| `provenance/FeedbackContext.java` | `impl/FeedbackContext.java` | Value type, stays as-is |
| `provenance/StalenessReport.java` | `impl/StalenessReport.java` | Value type, stays as-is |
| `search/SearchResource.java` | `impl/CorpusSearchService.java` | Rename to generic; GardenConfig → CorpusRef |
| `search/SearchResult.java` | `impl/SearchResult.java` | Already generic |
| `search/AdaptiveResult.java` | `impl/AdaptiveResult.java` | Already generic |
| `search/SearchScoringConfig.java` | `impl/SearchScoringConfig.java` | Config record, stays |
| `search/TemporalDecayScorer.java` | SKIP — already in rag-scoring | |
| `search/VersionScorer.java` | SKIP — already in rag-scoring | |
| `search/SearchProfileStore.java` | `impl/SearchProfileStore.java` | Replace existing (Hortora's has more maturity) |
| `index/GardenReindexService.java` | `impl/CorpusReindexService.java` | Rename; GardenConfig → CorpusRef |
| `index/GardenMetadataExtractor.java` | `impl/CorpusMetadataExtractor.java` | Rename; garden format IS the cover format |
| `outcome/GardenOutcomeService.java` | `impl/CorpusOutcomeService.java` | Rename; GardenConfig → CorpusRef |
| `inference/CollectionMigration.java` | `impl/CollectionMigrationService.java` | Already adapted in 502d2d4 |

### 3.2 Deployment-Specific (stay in Hortora)

These files remain in Hortora engine — they configure corpus-management for the Hortora use case:
- `config/GardenConfig.java`, `config/MissingBeanDefaults.java`
- `mcp/GardenMcpTools.java` — thin wrapper, imports from corpus-management
- `search/EntryResource.java`, `search/EntryDetail.java`, `search/ProfileResource.java`, `search/SearchConfig.java`
- `provenance/ProvenanceConfig.java`, `provenance/ProvenanceResource.java`, `provenance/ProvenanceRecordRequest.java`
- `outcome/OutcomeResource.java`
- `index/GardenBindingProducer.java`, `index/ReconcileScheduler.java`, `index/ReindexResource.java`
- `inference/CrossEncoderProducer.java`, `inference/HybridSearchProducer.java`

### 3.3 Test files

Tests stay in Hortora. After the move, they import from corpus-management packages. IntelliJ updates the imports automatically. Tests that exercise moved code now test through the same code at its new location — this validates the migration.

## 4. Phase 3 — Wire Hortora as Thin Deployment

1. Add `casehub-neocortex-corpus-management` dependency to Hortora engine pom.xml
2. GardenMcpTools and REST resources now import from `io.casehub.neocortex.corpus.management.impl.*`
3. CDI producers wire corpus-management beans for the Hortora deployment context
4. GardenConfig stays as Hortora's deployment configuration

## 5. Phase 4 — Verify

1. `mvn test` on Hortora engine — all 22 test files must pass
2. `mvn test -pl corpus-management` on neocortex — all tests pass
3. Full neocortex build — clean
4. Hortora startup with Qdrant — MCP tools functional

## 6. Constraints

- ALL source file moves use `ide_move_file`. No bash cp/mv for .java files.
- IntelliJ workspace must be open with both projects for cross-project reference updates.
- Generification is minimal — change config injection patterns, not algorithms.
- If a moved file needs corpus-management-api types that don't exist yet, add them to corpus-management-api first.

## References

- Original plan Task 4: `plans/2026-11-02-cognitive-knowledge-management.md` §Batch 3
- Gap audit: 2 matched, 5 partial, 5 missing, 13 deployment-specific
- D17 in decisions.md
- Hortora engine: 34 source files, 22 test files

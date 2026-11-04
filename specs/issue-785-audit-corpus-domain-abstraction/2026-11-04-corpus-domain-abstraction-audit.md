# Corpus-Management Domain Abstraction Audit

**Issue:** casehubio/neocortex#785
**Date:** 2026-11-04
**Status:** Audit (no code changes)

## Executive Summary

The corpus-management codebase has a clean two-tier architecture:

- **Tier 1 (domain-neutral):** `corpus-api` SPIs (`CorpusStore`, `CorpusReader`, `ChangeSource`), and `corpus-management-api` SPIs (`CorpusCatalogue`, `CorpusManager`, `CorpusSearch`, `FederatedCorpusSearch`, `CorpusQuery`). These are genuinely generic. A clinical guideline corpus, legal precedent library, or game NPC knowledge base could use them without modification.

- **Tier 2 (Hortora-shaped):** Implementation classes in `corpus-management/impl` that were lifted from the Hortora garden engine without abstraction: `GardenMetadataExtractor`, `GardenReindexService`, `CorpusApiBean`, `SearchResource`, `CorpusIndexService`, `ProvenanceStore`, `FederationConfig`. These contain garden terminology, GE-ID patterns, markdown assumptions, and staleness-tier scoring baked in.

Between these tiers, the API layer has **6 leaks** where Hortora assumptions bled into the SPIs themselves. These are the highest-priority items because they constrain all consumers, not just the implementation.

## Use Cases

Five lenses stress-test the abstractions:

| Use case | Document types | Metadata model | Federation needs |
|----------|---------------|----------------|------------------|
| **Clinical guidelines** | HL7 FHIR JSON/XML bundles, PDF evidence summaries | Evidence grading (GRADE), regulatory versioning, CPG-on-FHIR | Hierarchical: WHO → national → hospital |
| **Legal precedents** | PDF case filings, HTML opinions, citation graphs | Jurisdiction, court level, year, citations, overruled status | Jurisdictional: federal → state → circuit |
| **Game NPC knowledge** | Text backstories, JSON dialogue trees, YAML world facts | Character traits, faction, location, quest references | Flat: single world, no federation |
| **Software documentation** | Markdown API docs, changelogs, multi-version tech docs | Version, API surface, deprecation status | Version-branched: v3 → v2 fallback |
| **Hortora (existing)** | Markdown with YAML frontmatter | GE-ID, domain, type, score, staleness, tags, see-also | DAG: upstream/peer gardens |

## Classification Scheme

Each leak is rated on three axes:

| Axis | Values | Meaning |
|------|--------|---------|
| **Impact** | Blocked / Partial / Works | Can a non-Hortora consumer work around this without modifying neocortex? |
| **Effort** | XS / S / M / L | How hard is the remediation? |
| **Risk** | None / Low / Med / High | Will fixing this break existing Hortora usage? |

---

## API-Layer Leaks (corpus-management-api)

These constrain all consumers, not just the implementation.

### L1: CorpusEntry.body is String

**File:** `corpus-management-api/.../CorpusEntry.java:10`
**Impact:** High | **Effort:** M | **Risk:** Low

The `body` field is `String`, forcing all corpus content through a text representation. Binary documents (PDFs, DICOM images, FHIR XML bundles) cannot be represented without base64 encoding, which breaks chunking and embedding.

| Use case | Impact | Example |
|----------|--------|---------|
| Clinical | Blocked | FHIR bundles are JSON/XML; evidence summaries are PDF |
| Legal | Blocked | Case filings are PDF; opinions may be HTML |
| Game NPC | Works | Backstories and world facts are text |
| Software | Partial | Markdown docs work; architecture diagrams don't |
| Hortora | Works | All entries are markdown |

**Remediation direction:** Introduce a `Content` sealed hierarchy (`TextContent(String body)`, `BinaryContent(byte[] data, String mediaType)`, `StructuredContent(Map<String,Object> data, String schemaRef)`). `CorpusEntry.body()` becomes a convenience accessor that delegates to `content().asText()` with a deprecation path.

### L2: CorpusType.KNOWLEDGE_GARDEN constant

**File:** `corpus-management-api/.../CorpusType.java:11-18`
**Impact:** High | **Effort:** S | **Risk:** None

`CorpusType` is a record with dynamic field schemas (good), but ships three hardcoded constants: `KNOWLEDGE_GARDEN`, `RESEARCH`, `TRANSCRIPT`. The `KNOWLEDGE_GARDEN` constant declares `staleness_threshold` and `invalidation_triggers` as optional fields — pure Hortora vocabulary. `RESEARCH` also includes `staleness_threshold`. `TRANSCRIPT` includes `interaction_type`, `activity_type`, `artifact_ref`, `related_nodes` — agent-transcript-specific.

| Use case | Impact | Example |
|----------|--------|---------|
| Clinical | Blocked | No matching type; would need custom `CLINICAL_GUIDELINE` with `evidence_grade`, `recommendation_strength` |
| Legal | Blocked | No matching type; would need `LEGAL_PRECEDENT` with `jurisdiction`, `court_level`, `overruled_by` |
| Game NPC | Blocked | No matching type; would need `WORLD_KNOWLEDGE` with `faction`, `location`, `quest_ref` |
| Software | Partial | Could use `KNOWLEDGE_GARDEN` awkwardly; `staleness_threshold` maps loosely to deprecation |
| Hortora | Works | These constants exist for Hortora |

**Remediation direction:** Move constants to a `HortoraCo rpusTypes` class in `corpus-management` (the Hortora-specific module, not the API). The `CorpusType` record itself is fine — it's already dynamic. Consumers create their own `CorpusType` instances with domain-appropriate field schemas.

### L3: InteractionContext / InteractionType / ActivityType are agent-centric

**Files:** `corpus-management-api/.../InteractionContext.java`, `InteractionType.java`, `ActivityType.java`
**Impact:** Medium | **Effort:** S | **Risk:** Low

`InteractionContext` requires `agentId`, `tenantId`, `InteractionType` (AGENT_HUMAN, AGENT_AGENT, TOOL_USE, SELF_REFLECTION), and `ActivityType` (RESEARCH, IMPLEMENTATION, DEBUGGING, DESIGN_DISCUSSION, REVIEW, PLANNING, GENERAL). These are cognitive-agent-specific concepts. A legal corpus has no "agents" or "turns." A clinical corpus has no "self-reflection."

| Use case | Impact | Example |
|----------|--------|---------|
| Clinical | Blocked | Guidelines don't have agent interactions; evidence review is not "DEBUGGING" |
| Legal | Blocked | Court proceedings aren't "AGENT_HUMAN" interactions |
| Game NPC | Partial | NPC dialogue could stretch into AGENT_HUMAN, but ActivityType values don't fit |
| Software | Partial | Could map code review to REVIEW, but it's a forced mapping |
| Hortora | Works | These types describe Claude session transcripts |

**Remediation direction:** These types belong in `corpus-management` alongside `TranscriptCorpusInitializer`, not in the API. They describe one specific corpus type (transcripts), not a universal concept. Move to `impl` or a `transcript` sub-package. If other corpus types need interaction tracking, define it via the `CorpusType` field schema mechanism.

### L4: CorpusDescriptor.qdrantCollection leaks vector store choice

**File:** `corpus-management-api/.../CorpusDescriptor.java:15`
**Impact:** Low | **Effort:** XS | **Risk:** Low

The `qdrantCollection` field on `CorpusDescriptor` exposes the vector store implementation. A consumer using Pinecone, Weaviate, or no vector store at all still carries this field.

| Use case | Impact | Example |
|----------|--------|---------|
| Clinical | Low | Would use Qdrant too (same infrastructure), but the field name is misleading |
| Legal | Low | Same — infrastructure choice, not a blocking issue |
| Game NPC | Low | Might not use vector search at all; field is vestigial |
| Software | Low | Same infrastructure |
| Hortora | Works | Uses Qdrant |

**Remediation direction:** Rename to `vectorCollection` or `storageRef`. Or absorb into the `metadata` map — the collection name is a deployment detail, not a domain concept.

### L5: CorpusQuery is text-only

**File:** `corpus-management-api/.../CorpusQuery.java:10`
**Impact:** Low | **Effort:** M | **Risk:** Low

`CorpusQuery` has a single `text` field for the query. No vector query, no structured filter query, no multi-modal query support. The `PayloadFilter` field helps, but the primary retrieval path is always text search.

| Use case | Impact | Example |
|----------|--------|---------|
| Clinical | Partial | Text search works for guideline titles, but FHIR code lookups need structured queries |
| Legal | Partial | Case search by text works, but citation graph traversal needs structured queries |
| Game NPC | Works | Text search for character names and facts is sufficient |
| Software | Works | Text search for API names and concepts is sufficient |
| Hortora | Works | Text search is the primary access pattern |

**Remediation direction:** Add `embeddingVector` and `structuredFilters` fields to `CorpusQuery`. Or introduce a `CorpusQuery` sealed hierarchy: `TextQuery`, `VectorQuery`, `StructuredQuery`, `HybridQuery`. Lower priority since the `PayloadFilter` mechanism provides structured filtering already.

### L6: CorpusEntry frontmatter pattern assumes YAML/markdown

**File:** `corpus-management-api/.../CorpusEntry.java:9`
**Impact:** Medium | **Effort:** S | **Risk:** Low

`CorpusEntry` uses `Map<String, Object> frontmatter` with typed accessor methods (`stringField`, `instantField`, `doubleField`). The naming "frontmatter" and the accessor pattern assume YAML frontmatter in markdown documents. A JSON corpus would store metadata differently; a PDF corpus would extract metadata via Tika.

| Use case | Impact | Example |
|----------|--------|---------|
| Clinical | Partial | FHIR resources have structured metadata, but not as "frontmatter" |
| Legal | Partial | Case metadata (court, date, parties) isn't "frontmatter" |
| Game NPC | Partial | YAML character sheets map OK, but naming is misleading |
| Software | Works | Markdown docs with YAML frontmatter is a common pattern |
| Hortora | Works | All entries use YAML frontmatter |

**Remediation direction:** Rename `frontmatter` to `metadata`. The typed accessors are useful and format-agnostic — the issue is naming, not mechanics.

---

## Implementation-Layer Leaks (corpus-management/impl)

These affect only the Hortora deployment path, not the SPIs. Other consumers would provide their own implementations. Still worth cataloguing for completeness and to scope the "extract Hortora-specific code" remediation phase.

### L7: GardenMetadataExtractor — hardcoded markdown/GE-ID assumptions

**File:** `corpus-management/impl/.../GardenMetadataExtractor.java`
**Impact:** N/A (impl) | **Effort:** S | **Risk:** None

The entire class is Hortora-specific:
- Line 21: `.md` extension filter — non-markdown files return empty body
- Line 27: YAML `---` frontmatter check — no frontmatter = empty body
- Lines 61-66: `staleness_threshold` → `decay_tier` mapping with hardcoded defaults (90 days)
- Line 94-95: GE-ID regex pattern (`GE-\d{8}-[0-9a-f]{6}`)
- Lines 92-93: `**See also:**` markdown convention for cross-references

**Remediation direction:** This class stays in a Hortora-specific module. No changes needed — it correctly implements `MetadataExtractor` SPI for the garden use case. Other consumers implement their own `MetadataExtractor`.

### L8: FederationConfig.gardenId

**File:** `corpus-management/impl/.../FederationConfig.java:6`
**Impact:** N/A (impl) | **Effort:** XS | **Risk:** Low

Field named `gardenId` instead of `corpusId`. Used throughout `SearchResource` (lines 97, 257, 261, 304) as a visited-set key and source identifier.

**Remediation direction:** Rename to `corpusId`. Straightforward find-and-replace.

### L9: SearchResource — staleness-tier decay and version scoring

**File:** `corpus-management/impl/.../SearchResource.java:192-246`
**Impact:** N/A (impl) | **Effort:** M | **Risk:** Med

Lines 194-199: Hardcoded `TIER_HALF_LIVES` map (tier 0=730d, 1=365d, 2=180d, 3=90d) for garden-specific staleness tiers.
Lines 218-246: `versionScore()` computes decay from BOM version distance — assumes entries track which stack version they were "verified on." This is specific to a software knowledge garden where entries reference library versions.

**Remediation direction:** Extract scoring strategies behind a `ScoringStrategy` SPI. The temporal-decay and version-distance patterns are useful but should be composable and optional, not hardwired. A clinical corpus would use evidence-grading score; a legal corpus would use precedent-recency.

### L10: CorpusIndexService — GE-ID filesystem patterns

**File:** `corpus-management/impl/.../CorpusIndexService.java`
**Impact:** N/A (impl) | **Effort:** S | **Risk:** Low

Lines 197-198: `entry()` resolves entries by walking filesystem looking for `entryId + ".md"`
Lines 238-243: `extractDocumentId()` matches `GE-\d{8}-[0-9a-f]{6}` regex
Lines 248-258: `passesMinDaysFilter()` parses dates from GE-ID filenames

**Remediation direction:** Move to Hortora-specific module. The `CorpusEntryStore` SPI in the API layer already handles entry CRUD generically.

### L11: ProvenanceStore — ge_id column naming

**File:** `corpus-management/impl/.../ProvenanceStore.java`
**Impact:** N/A (impl) | **Effort:** XS | **Risk:** Low

SQL columns named `ge_id` throughout (lines 34, 46, 80, 87, 119, 139, 144, 183, 199, 216, 230, 251). The `FeedbackContext` and `StalenessReport` records also use `geId` field naming.

**Remediation direction:** Rename column to `document_id` or `entry_id`. Flyway migration for schema change.

### L12: CorpusApiBean.gardenRoot

**File:** `corpus-management/impl/.../CorpusApiBean.java:20,29`
**Impact:** N/A (impl) | **Effort:** XS | **Risk:** Low

Constructor parameter and field named `gardenRoot` (a `Path`). Used to locate entry files on disk.

**Remediation direction:** Rename to `corpusRoot`.

### L13: SearchScoringConfig defaults tuned for garden

**File:** `corpus-management/impl/.../SearchScoringConfig.java:10-12`
**Impact:** N/A (impl) | **Effort:** XS | **Risk:** None

`defaults()` factory returns values calibrated for the Hortora garden: `versionDecayFactor=0.03`, `versionDecayFloor=0.5`, `versionTopicWeightDefault=0.3`. Not wrong — but these are domain-specific tuning, not universal defaults.

**Remediation direction:** No action needed. These are configuration values. Other consumers would provide their own config via `@ConfigMapping` or constructor injection.

---

## Remediation Roadmap

### Phase 1: Quick Renames (XS effort, ~1 day)

Low-risk, high-clarity changes that don't alter behaviour:

| Item | Change | Risk |
|------|--------|------|
| L4 | `qdrantCollection` → `vectorCollection` or absorb into `metadata` | Low |
| L6 | `frontmatter` → `metadata` in `CorpusEntry` | Low |
| L8 | `gardenId` → `corpusId` in `FederationConfig` | Low |
| L11 | `ge_id` → `document_id` in ProvenanceStore schema + code | Low |
| L12 | `gardenRoot` → `corpusRoot` in `CorpusApiBean` | Low |

### Phase 2: API Fixes (S-M effort, ~3-5 days)

Changes that modify the public API surface but don't restructure modules:

| Item | Change | Risk |
|------|--------|------|
| L2 | Move `KNOWLEDGE_GARDEN`/`RESEARCH`/`TRANSCRIPT` constants out of `CorpusType` to a Hortora-specific class | None |
| L3 | Move `InteractionContext`/`InteractionType`/`ActivityType` from API to `impl` or a `transcript` sub-package | Low |
| L5 | Add `embeddingVector` or query type hierarchy to `CorpusQuery` | Low |

### Phase 3: Structural Extraction (M-L effort, ~1-2 weeks)

Changes that restructure modules to cleanly separate Hortora-specific code:

| Item | Change | Risk |
|------|--------|------|
| L1 | Introduce `Content` sealed hierarchy in `CorpusEntry` | Med — touches all entry consumers |
| L7+L10 | Extract `GardenMetadataExtractor`, `CorpusIndexService` to a `corpus-management-hortora` module | Low — no API change |
| L9 | Extract scoring strategies behind a `ScoringStrategy` SPI | Med — changes SearchResource internals |
| L7 | Support pluggable metadata extraction per corpus type (already SPI-driven via `MetadataExtractor`, just needs proper module separation) | Low |

### Phase 3 Module Structure (suggested)

```
corpus-management-api/     -- SPIs (cleaned: no garden constants, no agent types)
corpus-management/         -- Generic runtime (SqliteCorpusCatalogue, ChainWalkerFederatedSearch, etc.)
corpus-management-hortora/ -- Hortora-specific: GardenMetadataExtractor, garden scoring, GE-ID patterns
```

---

## Summary Assessment

**Is corpus-management genuinely generic?** Partially. The architecture is sound — the SPI boundaries are in the right places, and the newer management-layer SPIs (`CorpusCatalogue`, `CorpusManager`, `CorpusSearch`) are clean. A non-Hortora consumer could build on the platform today by:

1. Providing their own `MetadataExtractor` (RAG SPI — already pluggable)
2. Defining their own `CorpusType` with domain-appropriate field schemas
3. Ignoring the `KNOWLEDGE_GARDEN` constant and agent-interaction types

**What blocks genuine multi-consumer adoption?** The 6 API-layer leaks (L1-L6). Of these, L1 (String body) and L2 (garden constants in API) are the most impactful. L1 blocks any non-text corpus. L2 pollutes the API namespace with Hortora vocabulary.

**What's cosmetic?** The implementation-layer leaks (L7-L13) are internal to the Hortora deployment. They should be cleaned up for clarity, but they don't block other consumers who would provide their own implementations.

## References

- `corpus-api/src/main/java/io/casehub/neocortex/corpus/` — CorpusStore, CorpusReader, ChangeSource SPIs
- `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/` — management-layer SPIs
- `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/` — implementation classes
- `rag/src/main/java/io/casehub/neocortex/rag/` — CorpusIngestionService, MetadataExtractor SPI
- casehubio/neocortex#785 — parent issue
- casehubio/neocortex#789 — parent epic

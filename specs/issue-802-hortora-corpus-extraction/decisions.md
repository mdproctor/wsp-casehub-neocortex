# Design Decisions — #802 Hortora Corpus Extraction

## D1: Content sealed hierarchy scope

**Choice:** All three variants — TextContent, BinaryContent, StructuredContent
**Alternatives:**
- TextContent only — YAGNI, add others when needed. But delays establishing the sealed hierarchy shape.
- Skip Content hierarchy — keep body as String. No current consumer blocked, but L1 is the highest-impact API leak.
**Rationale:** The sealed hierarchy is the API commitment. Introducing all three now means the SPI shape is stable from day one. Tests verify the contract even without a production consumer for binary/structured content.
**Trade-offs:** Three variants to maintain and test instead of one. Marginal cost since they're simple value types.
**Sources:** docs/specs/2026-11-04-corpus-domain-abstraction-audit.md (L1), CorpusEntry.java
**Exploration:** quick
**Status:** captured

## D2: Module extraction scope

**Choice:** Broad extraction with SPI seams — move GardenMetadataExtractor, CorpusIndexService, GardenReindexService, scoring implementations (TIER_HALF_LIVES, versionScore), and KNOWLEDGE_GARDEN constant to corpus-management-hortora. Extract SPIs (ScoringStrategy) into corpus-management-api. ProvenanceStore stays in generic module (generic concept, implementation already cleaned in Phase 1).
**Alternatives:**
- Strict: 3 classes only — less disruption but leaves Hortora-shaped scoring in generic module
- Minimal: 2 classes — too conservative, GardenReindexService is clearly Hortora-specific
**Rationale:** Pre-release, no backward compat needed. L9 (ScoringStrategy SPI) is already in scope — the SPI extraction creates the seam, Hortora module is where implementations land. Broad extraction leaves the generic module genuinely clean.
**Trade-offs:** More files to move and more churn. But one-time cost that pays off in API clarity.
**Depends on:** D1 (Content hierarchy affects CorpusEntry shape, which affects classes being moved)
**Sources:** docs/specs/2026-11-04-corpus-domain-abstraction-audit.md (L7, L9, L10), SearchResource.java, GardenMetadataExtractor.java, CorpusIndexService.java
**Exploration:** quick
**Status:** captured

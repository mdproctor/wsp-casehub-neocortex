# @McpDomain("corpus") Auto-Generated Endpoints — Design Spec

**Issue:** casehubio/neocortex#776
**Branch:** issue-763-cognitive-knowledge-management
**Depends on:** #775 (service migration — complete)

## Summary

Create a single `CorpusApi` interface annotated with `@McpDomain("neocortex/corpus")` in the `corpus-management` module. The platform's compile-time annotation processor auto-generates REST (JAX-RS) and GraphQL endpoints; the runtime MCP scanner registers tools. This replaces 7 hand-written Hortora files (991 lines total): SearchEndpoint, EntryResource, ProfileResource, ReindexResource, OutcomeResource, ProvenanceResource, and GardenMcpTools.

## Architecture

### Module placement

`CorpusApi` interface and its `CorpusApiBean` implementation live in `corpus-management` (the impl module). This module already depends on `casehub-platform-api` (which provides `@McpDomain`, `@PlatformQuery`, `@PlatformMutation`) and contains all services the API delegates to.

The `jandex-maven-plugin` must be added to `corpus-management/pom.xml` so the annotation processor can discover the `@McpDomain` interface at compile time.

### New service: CorpusIndexService

Five operations from GardenMcpTools directly call RAG-layer SPIs (`EmbeddingIngestor`, `RetrievalTracker`, `RetrievalAnalyzer`, `MetadataExtractor`). These need a proper service home. `CorpusIndexService` provides index-level operations:

- `status(corpusId)` → entry count, corpus path, collection state
- `deleteEntry(corpusId, entryId)` → remove vectors from Qdrant
- `reindexEntry(corpusId, entryId)` → delete + re-extract + re-ingest
- `unretrieved(corpusId, minDays, staleDays)` → never-retrieved and stale entries via RetrievalAnalyzer
- `recordFeedback(entryIds, outcome, ...)` → orchestrates RetrievalTracker.feedback() + ProvenanceStore.recordFeedbackContext() + ProvenanceStore.recordStaleness()

### CorpusApi interface — 19 operations

```java
@McpDomain(value = "neocortex/corpus", app = "neocortex",
    summary = "Corpus knowledge management — search, lifecycle, provenance, and feedback")
public interface CorpusApi {

    // --- Search ---

    @PlatformQuery("Search a corpus with optional domain, type, and tag filters. "
        + "Supports search profiles and inline stack overrides for BOM-style filtering.")
    List<SearchResult> search(String corpusId, String query,
            List<String> domains, String type, String tags,
            Integer limit, String profile, String stack);

    @PlatformQuery("Adaptive search with keyword boosting — extends results "
        + "when initial set is too small, trims when too large")
    AdaptiveResult adaptiveSearch(String corpusId, String query, String keywords,
            List<String> domains, String type, String tags, Integer limit);

    // --- Entry ---

    @PlatformQuery("Fetch a single corpus entry by ID — returns frontmatter metadata and markdown body")
    EntryDetail entry(String corpusId, String entryId);

    // --- Index management ---

    @PlatformQuery("Index status: entry count, corpus path, collection state")
    CorpusStatus status(String corpusId);

    @PlatformQuery("List entries that have never been retrieved or are stale "
        + "(not retrieved within staleDays)")
    UnretrievedReport unretrieved(String corpusId, Integer minDays, Integer staleDays);

    @PlatformMutation("Trigger full re-index: delete collection and rebuild from source")
    ReindexResult reindex(String corpusId);

    @PlatformMutation("Re-index a single entry: delete vectors then re-extract and re-ingest")
    String reindexEntry(String corpusId, String entryId);

    @PlatformMutation("Delete a single entry's vectors from the index")
    String deleteEntry(String corpusId, String entryId);

    // --- Search profiles ---

    @PlatformQuery("Get a search profile's BOM stack by name")
    String profile(String name);

    @PlatformQuery("List all search profile names")
    List<String> profiles();

    @PlatformMutation("Create or update a search profile with a BOM stack definition")
    void saveProfile(String name, String stack);

    @PlatformMutation("Delete a search profile by name")
    boolean deleteProfile(String name);

    // --- Provenance ---

    @PlatformQuery("Forward lineage: which corpus entries were used for a given issue")
    List<ProvenanceRecord> forwardLineage(String issueRepo, Integer issueNumber);

    @PlatformQuery("Reverse lineage: which issues consumed a given corpus entry")
    List<ProvenanceRecord> reverseLineage(String entryId);

    @PlatformQuery("Provenance statistics: total links, active entries, coverage")
    ProvenanceStats provenanceStats();

    @PlatformMutation("Record provenance links between corpus entries and an issue/spec")
    int recordProvenance(String issueRepo, Integer issueNumber,
            String specName, String entryIds, String recordedBy);

    // --- Outcomes ---

    @PlatformQuery("Outcome report: summary of recorded outcomes across entries")
    String outcomeReport();

    @PlatformMutation("Record an outcome for a corpus entry (success/failure with context)")
    String recordOutcome(String entryId, String issueRepo, Integer issueNumber,
            String workContext, Double successRate, String detail);

    // --- Feedback ---

    @PlatformMutation("Record retrieval feedback for entries — updates staleness "
        + "tracking and provenance context")
    String recordFeedback(String entryIds, String outcome,
            String stack, String issueRepo, Integer issueNumber);
}
```

### New result types

| Type | Fields | Source |
|------|--------|--------|
| `CorpusStatus` | entryCount, corpusPath, corpusId, collectionReady | New — from gardenStatus logic |
| `UnretrievedReport` | neverRetrieved (List), stale (List), neverRetrievedCount, staleCount | New — from gardenUnretrieved logic |
| `EntryDetail` | id, title, domain, type, score, body, source, sourcePrefix, seeAlsoIds | Move from Hortora EntryDetail |

Existing types reused without changes: `SearchResult`, `AdaptiveResult`, `ReindexResult`, `ProvenanceRecord`, `ProvenanceStats`.

### Implementation: CorpusApiBean

`@ApplicationScoped` bean implementing `CorpusApi`. Thin delegator:

| Dependency | Operations |
|------------|-----------|
| `SearchResource` | search, adaptiveSearch |
| `CorpusIndexService` (new) | status, unretrieved, reindexEntry, deleteEntry, entry, recordFeedback |
| `CorpusReindexService` | reindex |
| `SearchProfileStore` | profile, profiles, saveProfile, deleteProfile |
| `ProvenanceStore` | forwardLineage, reverseLineage, provenanceStats, recordProvenance |
| `CorpusOutcomeService` | outcomeReport, recordOutcome |

### Build changes

1. Add `jandex-maven-plugin` to `corpus-management/pom.xml` (required for `@McpDomain` discovery)
2. No new Maven module needed

### Hortora impact (after this issue)

Hortora can delete these files (replaced by auto-generated endpoints from corpus-management):
- `SearchEndpoint.java` (56 lines)
- `EntryResource.java` (106 lines)
- `ProfileResource.java` (55 lines)
- `ReindexResource.java` (27 lines)
- `OutcomeResource.java` (41 lines)
- `ProvenanceResource.java` (53 lines)
- `GardenMcpTools.java` (653 lines)
- `EntryDetail.java` (support type)
- `ProvenanceRecordRequest.java` (support type)

Total: ~991 lines of hand-written endpoint code replaced by auto-generation.

This is tracked as Hortora/engine#96 (strip engine to config-only deployment) — a separate issue after #776.

## Testing

- **CorpusIndexService**: Unit tests with in-memory stubs for EmbeddingIngestor, RetrievalTracker, MetadataExtractor
- **CorpusApiBean**: Unit tests verifying delegation to the correct services
- **Integration**: The compile-time annotation processor generates REST/GraphQL; verify the generated sources compile. MCP registration is verified at runtime in deployment tests.

## References

- `cognitive-observability-core/src/main/java/.../CognitionApi.java` — @McpDomain pattern reference
- `platform/mcp-api/src/main/java/.../McpDomain.java` — annotation definition
- `platform/graphql-generator/.../GraphQLResolverProcessor.java` — compile-time code generator
- Hortora `engine/src/main/java/io/hortora/garden/mcp/GardenMcpTools.java` — operations being replaced
- casehubio/neocortex#776 — tracking issue
- D18, D19, D20 in decisions.md — design decisions

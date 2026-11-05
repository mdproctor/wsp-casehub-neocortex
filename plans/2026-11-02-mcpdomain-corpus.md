# @McpDomain("corpus") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #776 — @McpDomain("corpus") auto-generated endpoints for corpus-management
**Issue group:** #763, #764, #776

**Goal:** Create a single `@McpDomain("neocortex/corpus")` interface that auto-generates REST, GraphQL, and MCP endpoints for all corpus operations, replacing 7 hand-written Hortora files (991 lines).

**Architecture:** `CorpusApi` interface in `corpus-management` module with `@PlatformQuery`/`@PlatformMutation` annotations. A new `CorpusIndexService` wraps RAG-layer SPIs for index management operations. `CorpusApiBean` implements the interface as a thin delegator to existing services.

**Tech Stack:** Java 21, `casehub-platform-api` (`@McpDomain`, `@PlatformQuery`, `@PlatformMutation`), Jandex (compile-time annotation indexing)

## Global Constraints

- Java package: `io.casehub.neocortex.corpus.management.impl`
- All new classes are framework-neutral POJOs (no CDI annotations in corpus-management — CDI wiring is in the deployment layer)
- Platform annotation imports: `io.casehub.platform.api.mcp.McpDomain`, `io.casehub.platform.api.mcp.PlatformQuery`, `io.casehub.platform.api.mcp.PlatformMutation`
- Pattern reference: `cognitive-observability-core/src/main/java/.../CognitionApi.java`
- Hortora reference: `hortora/engine/src/main/java/io/hortora/garden/mcp/GardenMcpTools.java`
- **IntelliJ workspace setup:** Before starting, open the workspace:
  `ide_open_workspace(modules=["/path/to/neocortex", "/path/to/platform"])`
  Use IntelliJ tools for all code navigation and structural editing.

---

## Batch 1: CorpusIndexService + result types

### Task 1: Result types and CorpusIndexService with tests

**Files:**
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusStatus.java`
- Create: `../../corpus-management-hortora/src/main/java/io/casehub/neocortex/corpus/management/hortora/UnretrievedReport.java`
- Create: `../../corpus-management-hortora/src/main/java/io/casehub/neocortex/corpus/management/hortora/EntryDetail.java`
- Create: `../../corpus-management-hortora/src/main/java/io/casehub/neocortex/corpus/management/hortora/CorpusIndexService.java`
- Create: `../../corpus-management-hortora/src/test/java/io/casehub/neocortex/corpus/management/hortora/CorpusIndexServiceTest.java`

**Interfaces:**
- Consumes: `EmbeddingIngestor` (from rag-api: `listDocuments(CorpusRef)`, `deleteDocument(CorpusRef, String)`, `ingest(CorpusRef, List<ChunkInput>)`), `RetrievalTracker` (from rag-api: `findRecords(CorpusRef, Instant, Instant)`, `feedback(String, String, RetrievalOutcome)`), `RetrievalAnalyzer` (from rag-api: static `qualitySignals(...)`), `GardenMetadataExtractor` (from corpus-management: `extract(String, byte[])`), `ProvenanceStore` (from corpus-management: `recordFeedbackContext(...)`, `recordStaleness(...)`)
- Produces: `CorpusIndexService` with methods: `status(CorpusRef)`, `deleteEntry(CorpusRef, String)`, `reindexEntry(CorpusRef, String, java.nio.file.Path)`, `unretrieved(CorpusRef, int, int)`, `recordFeedback(CorpusRef, List<String>, String, String, String, Integer)`, `entry(java.nio.file.Path, String)`. Also produces `CorpusStatus`, `UnretrievedReport`, `EntryDetail` records.

- [ ] **Step 1: Write the three result type records**

```java
// CorpusStatus.java
package io.casehub.neocortex.corpus.management.impl;

public record CorpusStatus(String corpusId, String corpusPath, int entryCount, boolean collectionReady) {}
```

```java
// UnretrievedReport.java
package io.casehub.neocortex.corpus.management.impl;

import java.util.List;
import java.util.Map;

public record UnretrievedReport(
        List<String> neverRetrieved,
        List<String> stale,
        List<String> lowQuality,
        int neverRetrievedCount,
        int staleCount,
        int lowQualityCount) {

    public static final UnretrievedReport EMPTY =
            new UnretrievedReport(List.of(), List.of(), List.of(), 0, 0, 0);
}
```

```java
// EntryDetail.java
package io.casehub.neocortex.corpus.management.impl;

import java.util.List;

public record EntryDetail(
        String id, String title, String domain, String type,
        double score, String body, String source, String sourcePrefix,
        List<String> seeAlsoIds) {}
```

- [ ] **Step 2: Write the failing test for CorpusIndexService.status()**

```java
// CorpusIndexServiceTest.java
package io.casehub.neocortex.corpus.management.impl;

import io.casehub.neocortex.rag.CorpusRef;
import io.casehub.neocortex.rag.EmbeddingIngestor;
import io.casehub.neocortex.rag.RetrievalTracker;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class CorpusIndexServiceTest {

    private StubEmbeddingIngestor ingestor;
    private StubRetrievalTracker tracker;
    private CorpusIndexService service;
    private CorpusRef corpusRef;

    @BeforeEach
    void setUp() {
        ingestor = new StubEmbeddingIngestor();
        tracker = new StubRetrievalTracker();
        corpusRef = new CorpusRef("test", "test-corpus");
        service = new CorpusIndexService(ingestor, tracker, null, null);
    }

    @Test
    void status_returns_entry_count() {
        ingestor.setDocuments(List.of("doc1", "doc2", "doc3"));
        CorpusStatus status = service.status(corpusRef, "/garden/path");
        assertThat(status.entryCount()).isEqualTo(3);
        assertThat(status.corpusId()).isEqualTo("test-corpus");
        assertThat(status.collectionReady()).isTrue();
    }

    @Test
    void status_returns_unavailable_when_ingestor_fails() {
        ingestor.setThrowOnList(true);
        CorpusStatus status = service.status(corpusRef, "/garden/path");
        assertThat(status.entryCount()).isEqualTo(-1);
        assertThat(status.collectionReady()).isFalse();
    }
}
```

The stub classes (`StubEmbeddingIngestor`, `StubRetrievalTracker`) implement the minimal methods used — `listDocuments()` and `findRecords()`. Provide static inner classes or package-private test helpers. Model them after the test stubs already used in corpus-management tests (check existing test sources for patterns).

- [ ] **Step 3: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management -Dtest=CorpusIndexServiceTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — `CorpusIndexService` does not exist.

- [ ] **Step 4: Implement CorpusIndexService**

```java
// CorpusIndexService.java
package io.casehub.neocortex.corpus.management.impl;

import io.casehub.neocortex.rag.ChunkInput;
import io.casehub.neocortex.rag.CorpusRef;
import io.casehub.neocortex.rag.DocumentQualitySignal;
import io.casehub.neocortex.rag.EmbeddingIngestor;
import io.casehub.neocortex.rag.ExtractionResult;
import io.casehub.neocortex.rag.QualitySignal;
import io.casehub.neocortex.rag.QualityThresholds;
import io.casehub.neocortex.rag.RetrievalAnalyzer;
import io.casehub.neocortex.rag.RetrievalOutcome;
import io.casehub.neocortex.rag.RetrievalRecord;
import io.casehub.neocortex.rag.RetrievalTracker;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.stream.Collectors;

public class CorpusIndexService {

    private static final Logger LOG = Logger.getLogger(CorpusIndexService.class.getName());

    private final EmbeddingIngestor embeddingIngestor;
    private final RetrievalTracker retrievalTracker;
    private final GardenMetadataExtractor metadataExtractor;
    private final ProvenanceStore provenanceStore;

    public CorpusIndexService(EmbeddingIngestor embeddingIngestor,
                               RetrievalTracker retrievalTracker,
                               GardenMetadataExtractor metadataExtractor,
                               ProvenanceStore provenanceStore) {
        this.embeddingIngestor = embeddingIngestor;
        this.retrievalTracker = retrievalTracker;
        this.metadataExtractor = metadataExtractor;
        this.provenanceStore = provenanceStore;
    }

    public CorpusStatus status(CorpusRef corpusRef, String corpusPath) {
        try {
            int count = embeddingIngestor.listDocuments(corpusRef).size();
            return new CorpusStatus(corpusRef.corpusName(), corpusPath, count, true);
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Failed to count indexed entries", e);
            return new CorpusStatus(corpusRef.corpusName(), corpusPath, -1, false);
        }
    }

    public String deleteEntry(CorpusRef corpusRef, String entryId) {
        Map<String, String> idMap = buildEntryIdToDocIdMap(corpusRef);
        String docId = idMap.get(entryId);
        if (docId == null) {
            return "Entry " + entryId + " not found in index — nothing to delete.";
        }
        try {
            embeddingIngestor.deleteDocument(corpusRef, docId);
            return "Deleted vectors for " + entryId + " from index.";
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Failed to delete entry vectors", e);
            return "Failed to delete " + entryId + ": " + e.getMessage();
        }
    }

    public String reindexEntry(CorpusRef corpusRef, String entryId, Path gardenRoot) {
        Map<String, String> idMap = buildEntryIdToDocIdMap(corpusRef);
        String docId = idMap.get(entryId);
        if (docId == null) {
            docId = resolveEntryPath(gardenRoot, entryId);
            if (docId == null) {
                return "Entry " + entryId + " not found in index or filesystem.";
            }
        }

        try {
            embeddingIngestor.deleteDocument(corpusRef, docId);
        } catch (Exception e) {
            LOG.log(Level.FINE, "No existing vectors to delete for " + entryId, e);
        }

        Path filePath = gardenRoot.resolve(docId);
        if (!Files.isRegularFile(filePath)) {
            return "File not found on disk: " + docId + ". Old vectors deleted if they existed.";
        }

        try {
            byte[] content = Files.readAllBytes(filePath);
            ExtractionResult extraction = metadataExtractor.extract(docId, content);
            if (extraction.body().isBlank()) {
                return "Entry " + entryId + " has no extractable content — skipped.";
            }
            ChunkInput chunk = new ChunkInput(extraction.body(), docId,
                    extraction.metadata(), extraction.listMetadata());
            embeddingIngestor.ingest(corpusRef, List.of(chunk));
            return "Re-indexed " + entryId + " in corpus.";
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Failed to re-index entry", e);
            return "Failed to re-index " + entryId + ": " + e.getMessage();
        }
    }

    public UnretrievedReport unretrieved(CorpusRef corpusRef, int minDays, int staleDays) {
        QualityThresholds thresholds = new QualityThresholds(
                3, 3, 0.7, Duration.ofDays(staleDays));

        List<DocumentQualitySignal> signals = RetrievalAnalyzer.qualitySignals(
                retrievalTracker, embeddingIngestor, corpusRef,
                Instant.EPOCH, Instant.now(), thresholds);

        List<String> unretrieved = signals.stream()
                .filter(s -> s.signal() == QualitySignal.NEVER_RETRIEVED)
                .map(DocumentQualitySignal::sourceDocumentId)
                .filter(id -> passesMinDaysFilter(id, minDays))
                .sorted()
                .toList();

        List<String> stale = signals.stream()
                .filter(s -> s.signal() == QualitySignal.STALE)
                .map(DocumentQualitySignal::sourceDocumentId)
                .sorted()
                .toList();

        List<String> lowQuality = signals.stream()
                .filter(s -> s.signal() == QualitySignal.HIGH_RETRIEVAL_LOW_QUALITY)
                .map(DocumentQualitySignal::sourceDocumentId)
                .sorted()
                .toList();

        return new UnretrievedReport(unretrieved, stale, lowQuality,
                unretrieved.size(), stale.size(), lowQuality.size());
    }

    public String recordFeedback(CorpusRef corpusRef, List<String> entryIds,
                                  String outcome, String stack,
                                  String issueRepo, Integer issueNumber) {
        boolean isOutdated = "OUTDATED".equals(outcome);
        if (isOutdated && (stack == null || stack.isBlank())) {
            return "Error: OUTDATED outcome requires a stack parameter.";
        }

        RetrievalOutcome parsedOutcome;
        try {
            parsedOutcome = isOutdated ? RetrievalOutcome.NOT_RELEVANT
                    : RetrievalOutcome.valueOf(outcome);
        } catch (IllegalArgumentException e) {
            return "Error: invalid outcome '" + outcome
                    + "'. Must be: HIGHLY_RELEVANT, RELEVANT, PARTIALLY_RELEVANT, NOT_RELEVANT, OUTDATED";
        }

        Map<String, String> idMap = buildEntryIdToDocIdMap(corpusRef);
        Instant since = Instant.now().minus(30, ChronoUnit.DAYS);
        List<RetrievalRecord> recentRecords = retrievalTracker.findRecords(
                corpusRef, since, Instant.now());

        int recorded = 0;
        int skipped = 0;
        for (String entryId : entryIds) {
            String docId = idMap.get(entryId);
            if (docId == null) { skipped++; continue; }

            String retrievalId = recentRecords.stream()
                    .filter(r -> r.documents().stream()
                            .anyMatch(d -> d.sourceDocumentId().equals(docId)))
                    .max(Comparator.comparing(RetrievalRecord::timestamp))
                    .map(RetrievalRecord::retrievalId)
                    .orElse(null);
            if (retrievalId == null) { skipped++; continue; }

            retrievalTracker.feedback(retrievalId, docId, parsedOutcome);
            recorded++;

            if (provenanceStore != null) {
                provenanceStore.recordFeedbackContext(docId,
                        issueRepo != null ? issueRepo : "",
                        issueNumber != null ? issueNumber : 0,
                        outcome);
                if (isOutdated) {
                    provenanceStore.recordStaleness(docId, stack, "corpus-api");
                }
            }
        }

        return "Feedback recorded: " + recorded + " entries, " + skipped + " skipped"
                + (isOutdated ? " (marked OUTDATED for stack: " + stack + ")" : "");
    }

    public EntryDetail entry(Path gardenRoot, String entryId) {
        String filename = entryId + ".md";
        Path filePath;
        try (var stream = Files.walk(gardenRoot)) {
            filePath = stream
                    .filter(Files::isRegularFile)
                    .filter(p -> p.getFileName().toString().equals(filename))
                    .findFirst()
                    .orElse(null);
        } catch (IOException e) {
            return null;
        }
        if (filePath == null) return null;

        try {
            byte[] content = Files.readAllBytes(filePath);
            String docId = gardenRoot.relativize(filePath).toString();
            ExtractionResult extraction = metadataExtractor.extract(docId, content);
            Map<String, String> meta = extraction.metadata();
            List<String> seeAlso = extraction.listMetadata().getOrDefault("see_also", List.of());
            return new EntryDetail(
                    entryId,
                    meta.getOrDefault("title", entryId),
                    meta.getOrDefault("domain", ""),
                    meta.getOrDefault("type", ""),
                    0.0,
                    extraction.body(),
                    meta.getOrDefault("source", ""),
                    meta.getOrDefault("source_prefix", ""),
                    seeAlso);
        } catch (IOException e) {
            LOG.log(Level.WARNING, "Failed to read entry " + entryId, e);
            return null;
        }
    }

    // --- private helpers (ported from GardenMcpTools) ---

    private Map<String, String> buildEntryIdToDocIdMap(CorpusRef corpusRef) {
        try {
            return embeddingIngestor.listDocuments(corpusRef).stream()
                    .collect(Collectors.toMap(
                            GardenMcpTools::extractDocumentId,
                            id -> id,
                            (a, b) -> a));
        } catch (Exception e) {
            return Map.of();
        }
    }

    static boolean passesMinDaysFilter(String documentId, int minDays) {
        // Ported from GardenMcpTools.passesMinDaysFilter
        String filename = documentId.contains("/")
                ? documentId.substring(documentId.lastIndexOf('/') + 1) : documentId;
        if (filename.matches("GE-\\d{8}-[0-9a-f]{6}\\.md")) {
            String dateStr = filename.substring(3, 11);
            try {
                java.time.LocalDate entryDate = java.time.LocalDate.parse(dateStr,
                        java.time.format.DateTimeFormatter.BASIC_ISO_DATE);
                return ChronoUnit.DAYS.between(entryDate, java.time.LocalDate.now()) >= minDays;
            } catch (java.time.format.DateTimeParseException e) {
                return true;
            }
        }
        return true;
    }

    private String resolveEntryPath(Path gardenRoot, String entryId) {
        String filename = entryId + ".md";
        try (var stream = Files.walk(gardenRoot)) {
            return stream
                    .filter(Files::isRegularFile)
                    .filter(p -> p.getFileName().toString().equals(filename))
                    .map(p -> gardenRoot.relativize(p).toString())
                    .findFirst()
                    .orElse(null);
        } catch (IOException e) {
            return null;
        }
    }
}
```

Note: The `buildEntryIdToDocIdMap` references `GardenMcpTools.extractDocumentId` — this static utility method must be moved from Hortora to corpus-management. Make it a static method on `CorpusIndexService` or a standalone utility. Its logic: strip `.md` extension, extract filename, validate GE-ID pattern, return the ID or the full path.

```java
static String extractDocumentId(String path) {
    if (path == null) return "";
    String withoutExt = path.replaceFirst("\\.md$", "");
    String filename = withoutExt.contains("/")
            ? withoutExt.substring(withoutExt.lastIndexOf('/') + 1)
            : withoutExt;
    if (filename.matches("GE-\\d{8}-[0-9a-f]{6}")) {
        return filename;
    }
    return withoutExt;
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management -Dtest=CorpusIndexServiceTest`
Expected: PASS

- [ ] **Step 6: Add more test coverage**

Add tests for:
- `deleteEntry` — entry found and deleted, entry not found
- `reindexEntry` — happy path (file exists, extracted, re-ingested), file not found
- `entry` — file found, file not found (returns null)
- `recordFeedback` — valid outcome, invalid outcome, OUTDATED without stack
- `passesMinDaysFilter` — recent entry filtered, old entry passes, non-GE-ID always passes

Use the same stub pattern from Step 2. Focus on the return values and error paths, not RAG internals.

- [ ] **Step 7: Run full test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusStatus.java corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/UnretrievedReport.java corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/EntryDetail.java corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusIndexService.java corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/CorpusIndexServiceTest.java
git commit -m "feat(#776): add CorpusIndexService — index management for @McpDomain Refs #776"
```

---

## Batch 2: CorpusApi interface + implementation + build wiring

### Task 2: CorpusApi interface + CorpusApiBean + jandex wiring

**Files:**
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApi.java`
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApiBean.java`
- Modify: `corpus-management/pom.xml` (add jandex-maven-plugin)
- Create: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/CorpusApiBeanTest.java`

**Interfaces:**
- Consumes: `SearchResource` (search, searchAdaptive, adaptiveSearchEndpoint), `CorpusIndexService` (status, deleteEntry, reindexEntry, unretrieved, recordFeedback, entry), `CorpusReindexService` (reindex), `SearchProfileStore` (put, get, getRawStack, list, delete), `ProvenanceStore` (record, forwardLineage, reverseLineage, stats), `CorpusOutcomeService` (recordOutcome, outcomeReport), `CorpusRef`, `FederationConfig`, `java.nio.file.Path` (gardenRoot)
- Produces: `CorpusApi` interface (19 operations), `CorpusApiBean` implementation

- [ ] **Step 1: Write the CorpusApi interface**

```java
// CorpusApi.java
package io.casehub.neocortex.corpus.management.impl;

import io.casehub.platform.api.mcp.McpDomain;
import io.casehub.platform.api.mcp.PlatformMutation;
import io.casehub.platform.api.mcp.PlatformQuery;

import java.util.List;

@McpDomain(value = "neocortex/corpus", app = "neocortex",
        summary = "Corpus knowledge management — search, lifecycle, provenance, and feedback")
public interface CorpusApi {

    @PlatformQuery("Search a corpus with optional domain, type, and tag filters. "
            + "Supports search profiles and inline stack overrides for BOM-style filtering.")
    List<SearchResult> search(String corpusId, String query,
            List<String> domains, String type, String tags,
            Integer limit, String profile, String stack);

    @PlatformQuery("Adaptive search with keyword boosting — extends results "
            + "when initial set is too small, trims when too large")
    AdaptiveResult adaptiveSearch(String corpusId, String query, String keywords,
            List<String> domains, String type, String tags, Integer limit);

    @PlatformQuery("Fetch a single corpus entry by ID — returns frontmatter metadata and markdown body")
    EntryDetail entry(String corpusId, String entryId);

    @PlatformQuery("Index status: entry count, corpus path, collection state")
    CorpusStatus status(String corpusId);

    @PlatformQuery("List entries that have never been retrieved or are stale")
    UnretrievedReport unretrieved(String corpusId, Integer minDays, Integer staleDays);

    @PlatformMutation("Trigger full re-index: delete collection and rebuild from source")
    GardenReindexService.ReindexResult reindex(String corpusId);

    @PlatformMutation("Re-index a single entry: delete vectors then re-extract and re-ingest")
    String reindexEntry(String corpusId, String entryId);

    @PlatformMutation("Delete a single entry's vectors from the index")
    String deleteEntry(String corpusId, String entryId);

    @PlatformQuery("Get a search profile's BOM stack by name")
    String profile(String name);

    @PlatformQuery("List all search profile names")
    List<String> profiles();

    @PlatformMutation("Create or update a search profile with a BOM stack definition")
    void saveProfile(String name, String stack);

    @PlatformMutation("Delete a search profile by name")
    boolean deleteProfile(String name);

    @PlatformQuery("Forward lineage: which corpus entries were used for a given issue")
    List<io.casehub.neocortex.rag.ProvenanceRecord> forwardLineage(String issueRepo, Integer issueNumber);

    @PlatformQuery("Reverse lineage: which issues consumed a given corpus entry")
    List<io.casehub.neocortex.rag.ProvenanceRecord> reverseLineage(String entryId);

    @PlatformQuery("Provenance statistics: total links, active entries, coverage")
    io.casehub.neocortex.rag.ProvenanceStats provenanceStats();

    @PlatformMutation("Record provenance links between corpus entries and an issue/spec")
    int recordProvenance(String issueRepo, Integer issueNumber,
            String specName, String entryIds, String recordedBy);

    @PlatformQuery("Outcome report: summary of recorded outcomes across entries")
    String outcomeReport();

    @PlatformMutation("Record an outcome for a corpus entry (success/failure with context)")
    String recordOutcome(String entryId, String issueRepo, Integer issueNumber,
            String workContext, Double successRate, String detail);

    @PlatformMutation("Record retrieval feedback for entries — updates staleness tracking and provenance context")
    String recordFeedback(String entryIds, String outcome,
            String stack, String issueRepo, Integer issueNumber);
}
```

Note: The `ProvenanceRecord` and `ProvenanceStats` return types reference inner types of `ProvenanceStore`. Check the actual type definitions in `ProvenanceStore.java` — if they are inner records, use the qualified name. If they are standalone types, import directly.

- [ ] **Step 2: Write the failing test for CorpusApiBean**

```java
// CorpusApiBeanTest.java
package io.casehub.neocortex.corpus.management.impl;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class CorpusApiBeanTest {

    @Test
    void search_delegates_to_search_resource() {
        // Verify CorpusApiBean exists and implements CorpusApi
        var bean = createBean();
        assertThat(bean).isInstanceOf(CorpusApi.class);
    }

    private CorpusApiBean createBean() {
        // Constructor args verified against CorpusApiBean constructor
        return new CorpusApiBean(null, null, null, null, null, null, null, null, null);
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management -Dtest=CorpusApiBeanTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — `CorpusApiBean` does not exist.

- [ ] **Step 4: Implement CorpusApiBean**

```java
// CorpusApiBean.java
package io.casehub.neocortex.corpus.management.impl;

import io.casehub.neocortex.rag.CorpusRef;

import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;

public class CorpusApiBean implements CorpusApi {

    private final SearchResource searchResource;
    private final CorpusIndexService indexService;
    private final GardenReindexService reindexService;
    private final SearchProfileStore profileStore;
    private final ProvenanceStore provenanceStore;
    private final CorpusOutcomeService outcomeService;
    private final CorpusRef corpusRef;
    private final FederationConfig federationConfig;
    private final Path gardenRoot;

    public CorpusApiBean(SearchResource searchResource,
                          CorpusIndexService indexService,
                          GardenReindexService reindexService,
                          SearchProfileStore profileStore,
                          ProvenanceStore provenanceStore,
                          CorpusOutcomeService outcomeService,
                          CorpusRef corpusRef,
                          FederationConfig federationConfig,
                          Path gardenRoot) {
        this.searchResource = searchResource;
        this.indexService = indexService;
        this.reindexService = reindexService;
        this.profileStore = profileStore;
        this.provenanceStore = provenanceStore;
        this.outcomeService = outcomeService;
        this.corpusRef = corpusRef;
        this.federationConfig = federationConfig;
        this.gardenRoot = gardenRoot;
    }

    @Override
    public List<SearchResult> search(String corpusId, String query,
            List<String> domains, String type, String tags,
            Integer limit, String profile, String stack) {
        return searchResource.search(query, domains, type, tags,
                limit != null ? limit : SearchResource.DEFAULT_LIMIT,
                null, profile, stack);
    }

    @Override
    public AdaptiveResult adaptiveSearch(String corpusId, String query,
            String keywords, List<String> domains, String type,
            String tags, Integer limit) {
        String expandedKeywords = keywords != null && !keywords.isBlank()
                ? keywords.replace("|", " ") : null;
        return searchResource.searchAdaptive(query, expandedKeywords,
                domains, type, tags, limit, null, null);
    }

    @Override
    public EntryDetail entry(String corpusId, String entryId) {
        return indexService.entry(gardenRoot, entryId);
    }

    @Override
    public CorpusStatus status(String corpusId) {
        return indexService.status(corpusRef, gardenRoot != null ? gardenRoot.toString() : "");
    }

    @Override
    public UnretrievedReport unretrieved(String corpusId, Integer minDays, Integer staleDays) {
        return indexService.unretrieved(corpusRef,
                minDays != null ? minDays : 30,
                staleDays != null ? staleDays : 90);
    }

    @Override
    public GardenReindexService.ReindexResult reindex(String corpusId) {
        return reindexService.reindex();
    }

    @Override
    public String reindexEntry(String corpusId, String entryId) {
        return indexService.reindexEntry(corpusRef, entryId, gardenRoot);
    }

    @Override
    public String deleteEntry(String corpusId, String entryId) {
        return indexService.deleteEntry(corpusRef, entryId);
    }

    @Override
    public String profile(String name) {
        return profileStore.getRawStack(name);
    }

    @Override
    public List<String> profiles() {
        return profileStore.list();
    }

    @Override
    public void saveProfile(String name, String stack) {
        profileStore.put(name, stack);
    }

    @Override
    public boolean deleteProfile(String name) {
        return profileStore.delete(name);
    }

    @Override
    public List<io.casehub.neocortex.rag.ProvenanceRecord> forwardLineage(String issueRepo, Integer issueNumber) {
        return provenanceStore.forwardLineage(issueRepo, issueNumber != null ? issueNumber : 0);
    }

    @Override
    public List<io.casehub.neocortex.rag.ProvenanceRecord> reverseLineage(String entryId) {
        return provenanceStore.reverseLineage(entryId);
    }

    @Override
    public io.casehub.neocortex.rag.ProvenanceStats provenanceStats() {
        return provenanceStore.stats();
    }

    @Override
    public int recordProvenance(String issueRepo, Integer issueNumber,
            String specName, String entryIds, String recordedBy) {
        List<String> ids = Arrays.stream(entryIds.split("\\|"))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .toList();
        return provenanceStore.record(issueRepo, issueNumber, specName, ids, recordedBy);
    }

    @Override
    public String outcomeReport() {
        return outcomeService.outcomeReport();
    }

    @Override
    public String recordOutcome(String entryId, String issueRepo, Integer issueNumber,
            String workContext, Double successRate, String detail) {
        return outcomeService.recordOutcome(entryId, issueRepo, issueNumber,
                workContext, successRate, detail);
    }

    @Override
    public String recordFeedback(String entryIds, String outcome,
            String stack, String issueRepo, Integer issueNumber) {
        List<String> ids = Arrays.stream(entryIds.split("\\|"))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .toList();
        return indexService.recordFeedback(corpusRef, ids, outcome, stack, issueRepo, issueNumber);
    }
}
```

- [ ] **Step 5: Add jandex-maven-plugin to corpus-management/pom.xml**

Add inside `<build><plugins>`:

```xml
<plugin>
    <groupId>io.smallrye</groupId>
    <artifactId>jandex-maven-plugin</artifactId>
    <executions>
        <execution>
            <id>make-index</id>
            <goals><goal>jandex</goal></goals>
        </execution>
    </executions>
</plugin>
```

This enables the platform's `GraphQLResolverProcessor` to discover the `@McpDomain` interface at compile time.

- [ ] **Step 6: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management`
Expected: All tests PASS

- [ ] **Step 7: Build verification — full module**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl corpus-management`
Expected: BUILD SUCCESS. Verify jandex index is generated in `target/classes/META-INF/jandex.idx`.

- [ ] **Step 8: Commit**

```bash
git add corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApi.java corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApiBean.java corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/CorpusApiBeanTest.java corpus-management/pom.xml
git commit -m "feat(#776): add CorpusApi @McpDomain interface + CorpusApiBean Closes #776"
```

---

## Implementation Notes

### What the annotation processor generates

When a downstream Quarkus app (e.g., Hortora) depends on `corpus-management` and the platform's `graphql-generator` is on the annotation processor path:
- A `CorpusApiResolver.java` is generated with `@GraphQLApi` + `@Query`/`@Mutation` methods
- A `CorpusApiResource.java` is generated with `@Path` + `@GET`/`@POST` methods
- At runtime, `GraphQLModelScanner` discovers `@McpDomain` beans and `DynamicToolRegistrar` registers MCP tools

### Hortora cleanup (tracked as Hortora/engine#96)

After #776, Hortora can:
1. Delete all 7 hand-written endpoint files (991 lines)
2. Replace them with a CDI producer that creates `CorpusApiBean` from its existing config
3. The auto-generated endpoints serve the same operations

This is a separate issue and not part of this plan.

## References

- [2026-11-02-mcpdomain-corpus-design.md] — design spec this plan implements
- [cognitive-observability-core/.../CognitionApi.java] — @McpDomain pattern reference
- [hortora/engine/.../GardenMcpTools.java] — operations being replaced
- [corpus-management/.../SearchResource.java] — search service
- [corpus-management/.../ProvenanceStore.java] — provenance service
- [corpus-management/.../CorpusOutcomeService.java] — outcome service
- [corpus-management/.../GardenReindexService.java] — reindex service
- [corpus-management/.../SearchProfileStore.java] — profile service
- [platform/mcp-api/.../McpDomain.java] — annotation definition
- [GitHub #776] — tracking issue

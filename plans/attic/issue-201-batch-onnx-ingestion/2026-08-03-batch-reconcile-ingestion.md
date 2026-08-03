# Batch Reconcile Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #201 — Batch ONNX inference in CorpusIngestionService — 4-8x reindex throughput
**Issue group:** #201

**Goal:** Refactor `doReconcile()` to collect chunks from all missing documents before calling `ingest()`, enabling ONNX batch inference.

**Architecture:** Single method refactor in `CorpusIngestionService.doReconcile()`. Collect all chunks from missing documents into one list, then call `ingestor.ingest()` once. `QdrantEmbeddingIngestor` already handles internal ONNX+upsert batching at `embeddingBatchSize`.

**Tech Stack:** Java 21, Quarkus, LangChain4j, ONNX Runtime

## Global Constraints

- No SPI changes — `EmbeddingIngestor.ingest(CorpusRef, List<ChunkInput>)` unchanged
- Reconcile always saves cursor at end regardless of partial failure
- `ingest()` call wrapped in try-catch — failure does not prevent stale-document deletion or cursor advancement
- Performance claims assume dedup disabled (the default)

---

### Task 1: Batch chunk collection in doReconcile()

**Files:**
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/CorpusIngestionService.java` (method `doReconcile`, lines 252-296)
- Modify: `rag/src/test/java/io/casehub/neocortex/rag/runtime/CorpusIngestionServiceTest.java`

**Interfaces:**
- Consumes: `EmbeddingIngestor.ingest(CorpusRef, List<ChunkInput>)`, `InMemoryEmbeddingIngestor` (test stub)
- Produces: no new interfaces — refactor of existing method

- [ ] **Step 1: Write failing test — multiple missing documents are all ingested**

```java
@Test
void reconcileBatchesChunksFromMultipleMissingDocuments() {
    var fullScan = new ChangeSet(
            List.of(
                    new ChangedEntry("docs/a.md", ChangeType.ADDED),
                    new ChangedEntry("docs/b.md", ChangeType.ADDED),
                    new ChangedEntry("docs/c.md", ChangeType.ADDED)
            ),
            "cursor-batch"
    );
    var binding = binding(
            fixedSource(fullScan),
            stubReader(Map.of(
                    "docs/a.md", "Alpha content",
                    "docs/b.md", "Beta content",
                    "docs/c.md", "Gamma content"
            ))
    );

    service().reconcile("garden", binding);

    assertThat(ingestor.listDocuments(CORPUS))
            .containsExactlyInAnyOrder("docs/a.md", "docs/b.md", "docs/c.md");
    assertThat(ingestor.getChunks(CORPUS))
            .extracting(ChunkInput::content)
            .containsExactlyInAnyOrder("Alpha content", "Beta content", "Gamma content");
    assertThat(cursorStore.load("garden")).contains("cursor-batch");
}
```

- [ ] **Step 2: Run test to verify it passes with existing code**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=CorpusIngestionServiceTest#reconcileBatchesChunksFromMultipleMissingDocuments -DfailIfNoTests=false`

Expected: PASS (existing per-document code produces the same end state). This validates the test setup before refactoring.

- [ ] **Step 3: Write failing test — extraction failure on one document does not block others**

```java
@Test
void reconcileExtractionFailureDoesNotBlockOtherDocuments() {
    var fullScan = new ChangeSet(
            List.of(
                    new ChangedEntry("docs/ok.md", ChangeType.ADDED),
                    new ChangedEntry("docs/fail.md", ChangeType.ADDED),
                    new ChangedEntry("docs/also-ok.md", ChangeType.ADDED)
            ),
            "cursor-partial"
    );
    MetadataExtractor failOnSecond = (path, content) -> {
        if (path.equals("docs/fail.md")) {
            throw new RuntimeException("extraction failed");
        }
        return new ExtractionResult(new String(content), Map.of());
    };
    var binding = binding(
            fixedSource(fullScan),
            stubReader(Map.of(
                    "docs/ok.md", "First doc",
                    "docs/fail.md", "Bad doc",
                    "docs/also-ok.md", "Third doc"
            )),
            failOnSecond
    );

    service().reconcile("garden", binding);

    assertThat(ingestor.listDocuments(CORPUS))
            .containsExactlyInAnyOrder("docs/ok.md", "docs/also-ok.md");
    assertThat(cursorStore.load("garden")).contains("cursor-partial");
}
```

- [ ] **Step 4: Run test to verify it passes with existing code**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=CorpusIngestionServiceTest#reconcileExtractionFailureDoesNotBlockOtherDocuments -DfailIfNoTests=false`

Expected: PASS (existing per-document code already isolates extraction errors).

- [ ] **Step 5: Write failing test — ingest failure does not prevent stale-document deletion**

```java
@Test
void reconcileIngestFailureDoesNotPreventStaleDeletion() {
    // Pre-populate Qdrant with a stale document
    ingestor.ingest(CORPUS, List.of(new ChunkInput("stale content", "docs/stale.md", Map.of())));

    // Corpus has a new document (will cause ingest) but NOT the stale one
    var fullScan = new ChangeSet(
            List.of(new ChangedEntry("docs/new.md", ChangeType.ADDED)),
            "cursor-ingest-fail"
    );

    // Use a failing ingestor wrapper to simulate ingest failure
    var failingIngestor = new EmbeddingIngestor() {
        private final EmbeddingIngestor delegate = ingestor;
        @Override
        public void ingest(CorpusRef corpus, List<ChunkInput> chunks) {
            throw new RuntimeException("Qdrant unavailable");
        }
        @Override
        public void deleteDocument(CorpusRef corpus, String sourceDocumentId) {
            delegate.deleteDocument(corpus, sourceDocumentId);
        }
        @Override
        public void deleteCorpus(CorpusRef corpus) { delegate.deleteCorpus(corpus); }
        @Override
        public List<String> listDocuments(CorpusRef corpus) {
            return delegate.listDocuments(corpus);
        }
    };

    var service = new CorpusIngestionService(failingIngestor, cursorStore);
    var binding = binding(
            fixedSource(fullScan),
            stubReader(Map.of("docs/new.md", "New content"))
    );

    service.reconcile("garden", binding);

    // Stale document should still be deleted despite ingest failure
    assertThat(failingIngestor.listDocuments(CORPUS)).isEmpty();
    // Cursor should still advance
    assertThat(cursorStore.load("garden")).contains("cursor-ingest-fail");
}
```

- [ ] **Step 6: Run test to verify it FAILS**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=CorpusIngestionServiceTest#reconcileIngestFailureDoesNotPreventStaleDeletion -DfailIfNoTests=false`

Expected: FAIL — current code calls `ingest()` per document inside a try-catch, but doesn't have a separate try-catch that isolates ingest failure from stale-document deletion. The current code's exception from `ingest()` propagates and stops the method before reaching the stale-deletion loop.

Actually — re-reading the current code: in `doReconcile()`, each `ingest()` IS inside a per-document try-catch (line 275-281). So a single document's ingest failure is caught. But in the BATCHED version, `ingest()` sits outside the per-document loop, so it needs its own try-catch.

This test validates that the new code adds that try-catch.

- [ ] **Step 7: Refactor doReconcile() — batch chunk collection**

Use `ide_replace_member` to replace the body of `doReconcile`:

```java
CorpusRef corpusRef = binding.corpusRef();

ChangeSet fullScan = binding.changeSource().fullScan();

List<String> qdrantDocs = ingestor.listDocuments(corpusRef);

Set<String> corpusPaths = new HashSet<>();
for (ChangedEntry entry : fullScan.entries()) {
    corpusPaths.add(entry.path());
}
Set<String> qdrantPaths = new HashSet<>(qdrantDocs);

List<ChunkInput> allChunks = new ArrayList<>();
for (String path : corpusPaths) {
    if (!qdrantPaths.contains(path)) {
        try {
            Optional<byte[]> content = binding.corpusReader().read(path);
            if (content.isEmpty()) {
                LOG.fine(() -> "Document '" + path + "' no longer readable during reconciliation — skipping");
                continue;
            }

            ExtractionResult result = binding.metadataExtractor().extract(path, content.get());
            List<ChunkInput> chunks = chunkDocument(path, result, splitter);
            allChunks.addAll(chunks);
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Failed to process document '" + path + "' during reconciliation", e);
        }
    }
}

if (!allChunks.isEmpty()) {
    try {
        ingestor.ingest(corpusRef, allChunks);
    } catch (Exception e) {
        LOG.log(Level.WARNING, "Failed to batch ingest chunks for corpus '" + corpusName + "' during reconciliation", e);
    }
}

for (String path : qdrantPaths) {
    if (!corpusPaths.contains(path)) {
        try {
            ingestor.deleteDocument(corpusRef, path);
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Failed to delete stale document '" + path + "' during reconciliation", e);
        }
    }
}

cursorStore.save(corpusName, fullScan.newCursor());
```

- [ ] **Step 8: Run all reconcile tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=CorpusIngestionServiceTest -DfailIfNoTests=false`

Expected: ALL PASS — including the new `reconcileIngestFailureDoesNotPreventStaleDeletion` test.

- [ ] **Step 9: Run full module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag`

Expected: ALL PASS — no regressions.

- [ ] **Step 10: Run ide_diagnostics to verify no compilation issues**

Run: `ide_diagnostics` on `CorpusIngestionService.java` and `CorpusIngestionServiceTest.java`

Expected: No errors.

- [ ] **Step 11: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add rag/src/main/java/io/casehub/neocortex/rag/runtime/CorpusIngestionService.java rag/src/test/java/io/casehub/neocortex/rag/runtime/CorpusIngestionServiceTest.java
```

Commit message: `fix(#201): batch chunk collection in doReconcile() — 4-8x reindex throughput`

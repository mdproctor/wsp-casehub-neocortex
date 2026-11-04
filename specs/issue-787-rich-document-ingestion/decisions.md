# Decisions — #787 Rich Document Ingestion

## D1: Binary storage pattern

**Choice:** Cover document — binary stored externally via `artifactRef`, positional markdown is the searchable text representation in `body`
**Alternatives:**
- Dual storage (binary + text in CorpusEntry) — adds storage complexity, binary in CorpusEntry breaks the String body contract
- Conversion pipeline only (discard binary) — loses the original; can't re-extract with improved parsers later
**Rationale:** Matches the existing pattern (CoverDocumentParser already works this way for transcripts). Keeps CorpusEntry lightweight — the binary lives in the corpus storage layer (which already handles byte[]), the markdown representation is what gets searched and embedded.
**Trade-offs:** Requires consumers to follow artifactRef to access the original binary. Re-extraction requires access to the original file. No SPI exists for resolving artifactRef back to bytes — consumers use CorpusReader with the artifact path directly.
**Sources:** CorpusEntry.java:12 (artifactRef field), CoverDocumentParser.java (existing cover document pattern), SqliteCorpusEntryStore.java:128 (ingestEmbedding creates ChunkInput from body)
**Exploration:** quick
**Status:** captured

## D2: CorpusEntry.body type

**Choice:** Keep `String body` — no Content sealed hierarchy. Positional markdown is a format convention, not a type system change. This is an alternative resolution to audit L1 — the cover document pattern (D1) means non-text corpora ARE representable as positional markdown text, unblocking the 5 audit use cases (Clinical, Legal, Research, Market research, Product research) without requiring a type hierarchy change.
**Alternatives:**
- Typed Content variants (TextContent, PositionalMarkdown, StructuredContent) — adds type safety but breaks all CorpusEntry consumers for marginal benefit when body is always a text representation
- Defer to #802 — would delay this issue without clear benefit
**Rationale:** The audit's L1 says "String body blocks non-text corpora." The cover document pattern resolves this differently than the audit proposed: instead of making body polymorphic, we convert non-text content to a rich text representation (positional markdown) that preserves spatial structure. The binary is accessible via artifactRef. This unblocks all L1 use cases without an API-breaking change. If a future need arises that the cover document pattern can't serve (e.g., streaming binary content through the entry), the Content hierarchy can still be introduced in #802.
**Trade-offs:** No compile-time enforcement of content format. A consumer can't pattern-match on body type. CorpusType metadata must convey format conventions instead. This explicitly supersedes the audit's L1 remediation direction for #787 — the audit should be updated to reflect the cover document resolution.
**Sources:** docs/specs/2026-11-04-corpus-domain-abstraction-audit.md (L1 remediation direction), CorpusEntry.java:10, HANDOFF.md (references Content sealed hierarchy — resolved via cover document pattern instead)
**Depends on:** D1 (cover document pattern makes BinaryContent unnecessary)
**Exploration:** quick
**Status:** revised (R1-01: explicitly reconciles with audit L1)

## D3: Positional markdown format

**Choice:** Frontmatter declares page layout with panel coordinates. `#@` block-level annotations (ytt-style) map text blocks to panels. Existing `word[alias]` inline annotations continue to work for entity anchoring. `#@` syntax: `^#@\s*(\w+):\s*(.*)$` — unambiguously a directive (not content), follows ytt convention, creates a clean two-tier annotation model.
**Alternatives:**
- HTML comments as structural markers (`<!-- panel:left -->`) — valid markdown but harder to parse reliably, no established convention
- Pandoc fenced divs (`::: {.panel id=left}`) — nesting gets complex, poor compatibility with plain markdown renderers
- `{panel: left}` curly-brace attributes — visually lighter but ambiguous with template syntax; annotations should look like annotations, not content
**Rationale:** Two-tier annotation model: `#@` for block-level spatial annotations, `word[alias]` for inline entity anchors. Both are strippable — `BlockAnnotationParser` strips `#@` lines, `AnchorAnnotationParser` strips `word[alias]` brackets. Clean text goes to chunking/embedding. Panel coordinates use normalized values (0.0–1.0 relative to page dimensions) for format independence across PDF/DOCX/image sources. Layout presets (single, 2-column, 3-column, grid) provide default panel definitions; ad-hoc layouts declare explicit panel coordinates.
**Trade-offs:** New `BlockAnnotationParser` needed. `#@` renders as inert text in standard markdown viewers (not a heading since no space after `#` per CommonMark), but the parser strips it before rendering anyway. `AnchorAnnotationParser` source lives in platform parent (annotation-api module), not in this repo's src/ — compiled classes available via dependency.
**Sources:** AnchorAnnotationParser (annotation-api, platform parent — inline annotation parser), ytt annotation convention
**Depends on:** D1 (cover document pattern), D2 (body stays String)
**Exploration:** deep-analysis
**Status:** revised (R1-05: consolidated D9 into D3; R1-09: added coordinate normalization)

## D4: Image handling

**Choice:** Three-layer image representation: (1) caption text from document context, (2) OCR via Tika's built-in TesseractOCRParser (not a separate Tesseract integration), (3) optional LLM vision description — config-gated via `casehub.corpus.parsers.llm.image-description.enabled`, off by default due to cost/latency.
**Alternatives:**
- Skip images entirely — handles 80% of cases but loses diagrams, charts, photos
- Caption + OCR only (no LLM) — cheaper but diagrams and photos get poor text representations
- Separate Tesseract integration — adds a native dependency; Tika already integrates TesseractOCRParser
**Rationale:** OCR captures text *in* the image; LLM describes what the image *shows*. Both are valuable for different content types (OCR for forms/tables, LLM for diagrams/charts). Leveraging Tika's built-in Tesseract integration avoids a separate native dependency — Tesseract on PATH is sufficient.
**Trade-offs:** LLM vision adds latency and cost per image when enabled. Tika's OCR requires Tesseract installed on system PATH. OCR quality varies with image quality.
**Sources:** TikaDocumentParser.java (existing Tika integration), Apache Tika TesseractOCRParser documentation
**Exploration:** quick
**Status:** revised (R1-08: use Tika's built-in Tesseract, not separate; R1-06: separate config flag)

## D5: Module architecture

**Choice:** New `corpus-management-parsers` module with `DocumentParser` SPI + format-specific implementations (PdfDocumentParser, DocxDocumentParser, ImageDocumentParser). `DocumentParser` is a corpus-management-layer SPI distinct from `MetadataExtractor` in rag-api.
**Alternatives:**
- Extend rag-tika — keeps Tika in one place but couples corpus-management concerns into the rag layer
- Inside corpus-management impl — no new module but impl grows and takes on Tika/PDFBox dependencies
- Make DocumentParser a MetadataExtractor variant — conflates two layers (corpus-management pre-processing vs RAG metadata extraction)
**Rationale:** `DocumentParser` and `MetadataExtractor` serve different layers and produce different outputs. `DocumentParser` converts binary → positional markdown with `#@` annotations (corpus-management pre-processing, runs before `CorpusEntryStore.add()`). `MetadataExtractor` converts bytes → flat text + metadata (RAG ingestion, runs in `CorpusIngestionService`). They are not the same abstraction: `DocumentParser` is structure-preserving; `MetadataExtractor` is content-extracting. `GardenMetadataExtractor` handles markdown files for the RAG pipeline — it would not be replaced by `DocumentParser`.
**Trade-offs:** Another Maven module. Two SPIs for binary-to-text conversion in the system, serving different layers. Clear layer separation justifies the distinction.
**Sources:** MetadataExtractor.java (rag-api), ExtractionResult.java (rag-api), GardenMetadataExtractor.java (corpus-management), CorpusIngestionService.java (rag-core)
**Exploration:** quick
**Status:** revised (R1-03: clarified DocumentParser vs MetadataExtractor relationship)

## D6: Chunking strategy + integration path

**Choice:** Structure-aware chunking via a new `StructuralChunker` interface that returns `List<StructuredChunk>` (text + per-chunk metadata: page number, panel ID, section heading). `SqliteCorpusEntryStore.ingestEmbedding()` is enhanced to use `StructuralChunker` for positional markdown bodies, falling back to existing single-ChunkInput behavior for plain text entries.
**Alternatives:**
- Standard chunking (strip markers, use existing TextChunker) — simpler but loses structural context per chunk
- Modify TextChunker to return List<ChunkInput> — breaks @FunctionalInterface contract and all callers
- Feed through CorpusIngestionService path instead — wrong layer; that path is for corpus-api → rag, not corpus-management → rag
**Rationale:** `TextChunker` returns `List<String>` — no per-chunk metadata. Structure-aware chunking needs to produce chunks WITH metadata. A new `StructuralChunker` interface avoids breaking the existing `TextChunker` contract. Integration path: document parsing happens before `CorpusEntryStore.add()` (the `DocumentParser` converts binary → positional markdown). Then `ingestEmbedding()` detects `#@` annotations in the body and uses `StructuralChunker` to produce `ChunkInput` objects with per-chunk metadata from the stripped annotations.
**Trade-offs:** New interface alongside TextChunker. `ingestEmbedding()` gains conditional logic (detect format, choose chunker). Must handle edge cases: sections larger than chunk size, very short sections (merge or standalone?).
**Sources:** TextChunker (rag-api, returns List<String>), ChunkInput (rag-api, carries Map<String,String> metadata), SqliteCorpusEntryStore.ingestEmbedding() line 128, CorpusIngestionService.chunkDocument() line 295-310
**Depends on:** D3 (positional markdown format provides structural markers)
**Exploration:** quick
**Status:** revised (R1-02: resolved dual ingestion path; R1-04: new StructuralChunker interface)

## D7: Format scope

**Choice:** PDF + DOCX + images — three formats in initial implementation. The `DocumentParser` SPI is designed for extensibility — additional formats (HTML, XLSX) can be added as separate implementations without API changes.
**Alternatives:**
- PDF only — reduces scope but DOCX is common and images are needed for OCR
- All Tika-supported formats — broad but shallow structural fidelity per format
**Rationale:** These are the three formats named in the issue. PDF is most structurally complex (multi-column, figures, tables). DOCX is the most common office format. Images need OCR. The SPI supports adding more formats incrementally.
**Trade-offs:** Three format-specific parsers to build. PDFBox for PDF structural extraction. Apache POI/docx4j for DOCX. Tika's TesseractOCRParser for image OCR.
**Sources:** Issue #787 (format requirements), audit L1 use case table
**Exploration:** quick
**Status:** captured

## D8: Parsing mode

**Choice:** Synchronous — parse at ingest time before the entry is stored. This is a deliberate contract commitment: `CorpusEntryStore.add()` returns a complete entry with parsed body and ingested embeddings.
**Alternatives:**
- Async with status (store immediately, parse in background) — better for large batches but requires status field, lifecycle state, polling/notification, and split embedding ingestion
**Rationale:** Corpus management is not real-time. Entries are complete when `add()` returns. Avoids partial-state entries. Note: switching to async later is not a simple change — it requires redesigning the add() contract, adding a status field, and splitting the store + embed phases. This is a deliberate lock-in to synchronous semantics, not a deferral.
**Trade-offs:** Large documents block the ingest call. Batch ingestion of many large PDFs will be slower. The sync contract is difficult to change once consumers depend on it.
**Sources:** CorpusEntryStore.add() (current synchronous contract), SqliteCorpusEntryStore.add() (SQL insert + embedding ingestion in same call)
**Exploration:** quick
**Status:** revised (R1-11: acknowledged sync-to-async switch cost as deliberate lock-in)

## D10: LLM-assisted layout detection

**Choice:** Optional LLM vision call to classify page layout and identify panels when programmatic extraction is uncertain. Config-gated via its own flag `casehub.corpus.parsers.llm.layout-detection.enabled` — independent from D4's image description flag. One LLM call per page can classify layout structure.
**Alternatives:**
- Programmatic only — fully deterministic but mis-classifies complex layouts (forms, worksheets, multi-panel documents)
- Defer — start programmatic, add LLM later if quality is insufficient
- Combined flag with image description — couples two independent concerns (layout accuracy vs image enrichment)
**Rationale:** LLM vision understands spatial structure as a human does — it can identify instruction boxes, exercise panels, sidebars, reference sections in a single pass. Programmatic extraction (PDFBox) gives raw text blocks with coordinates but doesn't understand what the regions *mean*. Independent config flag allows operators to enable accurate layout detection without paying for image descriptions (or vice versa).
**Trade-offs:** LLM call adds latency and cost per page. Not needed for simple single-column documents. For large documents (100+ pages), cost can be significant — consumers should estimate costs before enabling.
**Sources:** Claude vision capability (demonstrated on KS2 worksheets — spatial understanding of forms), issue #787 (positional format requirements)
**Depends on:** D3 (positional markdown format)
**Exploration:** quick
**Status:** revised (R1-06: separate config flag from D4)

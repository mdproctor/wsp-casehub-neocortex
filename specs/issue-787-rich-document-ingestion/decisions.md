# Decisions — #787 Rich Document Ingestion

## D1: Binary storage pattern

**Choice:** Cover document — binary stored externally via `artifactRef`, positional markdown is the searchable text representation in `body`
**Alternatives:**
- Dual storage (binary + text in CorpusEntry) — adds storage complexity, binary in CorpusEntry breaks the String body contract
- Conversion pipeline only (discard binary) — loses the original; can't re-extract with improved parsers later
**Rationale:** Matches the existing pattern (CoverDocumentParser already works this way for transcripts). Keeps CorpusEntry lightweight — the binary lives in the corpus storage layer (which already handles byte[]), the markdown representation is what gets searched and embedded.
**Trade-offs:** Requires consumers to follow artifactRef to access the original binary. Re-extraction requires access to the original file.
**Sources:** CorpusEntry.java:12 (artifactRef field), CoverDocumentParser.java (existing cover document pattern), SqliteCorpusEntryStore.java:128 (ingestEmbedding creates ChunkInput from body)
**Exploration:** quick
**Status:** captured

## D2: CorpusEntry.body type

**Choice:** Keep `String body` — no Content sealed hierarchy. Positional markdown is a format convention, not a type system change.
**Alternatives:**
- Typed Content variants (TextContent, PositionalMarkdown, StructuredContent) — adds type safety but breaks all CorpusEntry consumers for marginal benefit when body is always a text representation
- Defer to #802 — would delay this issue without clear benefit
**Rationale:** With the cover document pattern (D1), `body` is always a text representation of the content. The format (plain markdown vs positional markdown) is a corpus-level convention expressed via CorpusType and MetadataExtractor, not a per-entry type. The audit's L1 BinaryContent variant is unnecessary when binaries live externally.
**Trade-offs:** No compile-time enforcement of content format. A consumer can't pattern-match on body type. CorpusType metadata must convey format conventions instead.
**Sources:** docs/specs/2026-11-04-corpus-domain-abstraction-audit.md (L1 remediation direction), CorpusEntry.java:10
**Depends on:** D1 (cover document pattern makes BinaryContent unnecessary)
**Exploration:** quick
**Status:** captured

## D3: Positional markdown format

**Choice:** Frontmatter declares page layout with panel coordinates (x,y,w,h). `#@` block-level annotations (ytt-style) map text blocks to panels. Existing `word[alias]` inline annotations continue to work for entity anchoring.
**Alternatives:**
- HTML comments as structural markers (`<!-- panel:left -->`) — valid markdown but harder to parse reliably, no established convention
- Pandoc fenced divs (`::: {.panel id=left}`) — nesting gets complex, poor compatibility with plain markdown renderers
- `{panel: left}` curly-brace attributes — visually lighter but ambiguous with template syntax; annotations should look like annotations, not content
**Rationale:** `#@` is unambiguously a directive (never content), follows ytt convention, trivially parseable (`^#@\s*(\w+):\s*(.*)$`), and creates a clean two-tier annotation model with the existing `word[alias]` inline anchors. Frontmatter layout presets (single, 3-column, grid, ad-hoc) avoid repeating coordinates for standard document structures.
**Trade-offs:** New `#@` parser needed (AnchorAnnotationParser handles `word[alias]` only). `#@` renders as inert text in standard markdown viewers (not a heading since no space after `#` per CommonMark), but the parser strips it before rendering anyway.
**Sources:** AnchorAnnotationParser.java (existing inline annotation parser), AnchorAnnotationParserTest.java (word[alias] syntax), ytt annotation convention
**Depends on:** D1 (cover document pattern), D2 (body stays String)
**Exploration:** deep-analysis
**Status:** captured

## D4: Image handling

**Choice:** Three-layer image representation: (1) caption text from document context, (2) OCR via Tesseract for text in images, (3) optional LLM vision description — config-gated, off by default due to cost/latency.
**Alternatives:**
- Skip images entirely — handles 80% of cases but loses diagrams, charts, photos
- Caption + OCR only (no LLM) — cheaper but diagrams and photos get poor text representations
- External ref + OCR — stores original image separately, adds storage complexity
**Rationale:** OCR captures text *in* the image; LLM describes what the image *shows*. Both are valuable for different content types (OCR for forms/tables, LLM for diagrams/charts). Config gate means bulk ingestion stays cheap; high-value corpora can enable vision.
**Trade-offs:** LLM vision adds latency and cost per image when enabled. Tesseract adds a native dependency. OCR quality varies with image quality.
**Sources:** TikaDocumentParser.java (existing text extraction), issue #787 (OCR + image strategy requirements)
**Exploration:** quick
**Status:** captured

## D5: Module architecture

**Choice:** New `corpus-management-parsers` module with `DocumentParser` SPI + format-specific implementations (PdfParser, DocxParser, ImageParser).
**Alternatives:**
- Extend rag-tika — keeps Tika in one place but couples corpus-management concerns into the rag layer
- Inside corpus-management impl — no new module but impl grows and takes on Tika/Tesseract dependencies
**Rationale:** Clean separation. corpus-management depends on the SPI, not the implementations. Consumers can pick which parsers to include. Tika/Tesseract/PDFBox dependencies stay isolated. Existing rag-tika remains standalone for consumers who want raw text extraction without positional markdown.
**Trade-offs:** Another Maven module. Some overlap with rag-tika's Tika usage (though rag-tika does flat text extraction; this module does structural extraction).
**Sources:** rag-tika/TikaDocumentParser.java (existing standalone parser), corpus-management-api module structure
**Exploration:** quick
**Status:** captured

## D6: Chunking strategy

**Choice:** Structure-aware chunking — chunk at natural document boundaries (page breaks, section breaks) when they fall within the chunk size window. Fall back to token-based splitting for large sections. Structural markers (`#@` annotations) become chunk metadata (page number, section heading, panel ID).
**Alternatives:**
- Standard chunking (strip markers, use existing TextChunker) — simpler but loses structural context per chunk
- Defer chunking design — possible but chunking is integral to the ingestion pipeline
**Rationale:** Structural boundaries are semantically meaningful — a chunk that spans a page break or crosses from header to body mixes contexts. Structure-aware chunking produces higher-quality chunks for retrieval. The `#@` annotations provide natural split points that the chunker can use.
**Trade-offs:** More complex chunker implementation. Must handle edge cases: sections larger than chunk size, very short sections (merge or standalone?).
**Sources:** TextChunker (existing token-based chunker in rag-api), CorpusIngestionService.java:302 (current chunking call)
**Depends on:** D3 (positional markdown format provides structural markers)
**Exploration:** quick
**Status:** captured

## D7: Format scope

**Choice:** PDF + DOCX + images — three formats in initial implementation.
**Alternatives:**
- PDF only — reduces scope but DOCX is common and images are needed for OCR
- All Tika-supported formats — broad but shallow structural fidelity per format
**Rationale:** These are the three formats named in the issue. PDF is most structurally complex (multi-column, figures, tables). DOCX is the most common office format. Images need OCR. Together they cover the use cases listed in the audit (clinical PDFs, legal filings, research papers).
**Trade-offs:** Three format-specific parsers to build. PDFBox for PDF structural extraction (Tika alone gives flat text). Apache POI or docx4j for DOCX. Tesseract for image OCR.
**Sources:** Issue #787 (format requirements), audit L1 use case table
**Exploration:** quick
**Status:** captured

## D8: Parsing mode

**Choice:** Synchronous — parse at ingest time before the entry is stored.
**Alternatives:**
- Async with status (store immediately, parse in background) — better for large batches but adds state management complexity
**Rationale:** Corpus management is not real-time. Entries are complete when `add()` returns. Avoids partial-state entries and the need for a status field + polling mechanism.
**Trade-offs:** Large documents block the ingest call. Batch ingestion of many large PDFs will be slower. Can be revisited if latency becomes an issue.
**Sources:** CorpusEntryStore.add() (current synchronous contract)
**Exploration:** quick
**Status:** captured

## D9: Annotation syntax

**Choice:** `#@` (ytt-style) for block-level annotations in positional markdown.
**Alternatives:**
- `{panel: left}` curly-brace style — visually lighter but ambiguous with template syntax (Mustache, Handlebars, JSON)
**Rationale:** `#@` is unambiguously a directive. Creates a clean two-tier model: `#@` for block-level spatial annotations, `word[alias]` for inline entity anchors. `#` reads as "comment/directive" across most languages. Not a markdown heading (CommonMark requires `# ` with space). Follows ytt precedent — not novel syntax.
**Trade-offs:** Needs a new block-level annotation parser (existing AnchorAnnotationParser handles only `word[alias]`). `#@` renders as inert paragraph text in standard markdown viewers.
**Sources:** AnchorAnnotationParser.java (existing inline parser), ytt annotation convention
**Depends on:** D3 (positional markdown format)
**Exploration:** deep-analysis
**Status:** captured

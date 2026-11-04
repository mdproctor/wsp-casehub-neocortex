# Rich Document Ingestion — Design Spec

**Issue:** casehubio/neocortex#787
**Date:** 2026-11-04
**Status:** Draft

## Overview

corpus-management currently handles markdown entries. Real corpora contain PDFs, Word documents, and images. This design introduces a document parsing pipeline that converts binary documents into **positional markdown** — a text format that preserves the spatial structure of the original document using panel layouts and `#@` block annotations.

The binary is stored externally via `artifactRef` (cover document pattern). The positional markdown goes into `CorpusEntry.body` as the searchable text representation. `body` stays `String` — this resolves the audit's L1 ("String body blocks non-text corpora") via the cover document pattern rather than a Content sealed hierarchy.

## Positional Markdown Format

### Frontmatter: Layout Declaration

Each positional markdown document declares its page layout in YAML frontmatter. Panels define named regions with normalized coordinates (0.0–1.0 relative to page dimensions).

```yaml
---
source_format: pdf
source_pages: 1
page_size: [612, 792]
layout: ad-hoc
panels:
  - id: header
    x: 0.06
    y: 0.91
    w: 0.88
    h: 0.06
  - id: main-left
    x: 0.06
    y: 0.13
    w: 0.42
    h: 0.76
  - id: main-right
    x: 0.50
    y: 0.13
    w: 0.42
    h: 0.76
  - id: footer
    x: 0.06
    y: 0.05
    w: 0.88
    h: 0.06
---
```

**Layout presets** provide default panel definitions for standard document structures:

| Preset | Panels | Use case |
|--------|--------|----------|
| `single` | `main` (full page) | Simple single-column documents |
| `2-column` | `left`, `right` | Two-column academic papers, newsletters |
| `3-column` | `left`, `center`, `right` | Newspaper layouts, brochures |
| `header-body-footer` | `header`, `body`, `footer` | Standard document with header/footer |
| `grid-2x2` | `top-left`, `top-right`, `bottom-left`, `bottom-right` | Worksheets, forms |
| `grid-3x3` | 9 grid cells | Complex forms, grids |
| `ad-hoc` | Custom panel definitions required | Any non-standard layout |

When using a preset, panel coordinates are computed from the preset name — no explicit coordinate declarations needed:

```yaml
---
source_format: pdf
source_pages: 1
layout: 2-column
---
```

### Body: `#@` Block Annotations

Text blocks in the body are mapped to panels using `#@` annotations. Each `#@` line applies to all subsequent text until the next `#@` annotation.

```markdown
#@ panel: header
# Annual Report 2025 — Fiscal Summary

#@ panel: main-left
Revenue[metric-revenue] increased 23% year over year, driven primarily
by the expansion into Southeast Asian markets[region-sea]...

The board[org-board] approved a dividend increase of 15%.

#@ panel: main-right
| Quarter | Revenue | Growth |
|---------|---------|--------|
| Q1      | $4.2M   | 18%    |
| Q2      | $4.8M   | 22%    |
| Q3      | $5.1M   | 25%    |
| Q4      | $5.6M   | 28%    |

#@ panel: footer
Page 1 of 24 — Confidential
```

### `#@` Annotation Types

| Annotation | Syntax | Purpose |
|-----------|--------|---------|
| `panel` | `#@ panel: <panel-id>` | Map following text to a layout panel |
| `page` | `#@ page: <number>` | Page break marker |
| `layout` | `#@ layout: <preset-name>` | Per-page layout override (page-scoped, see §Multi-Page Documents precedence rules) |
| `figure` | `#@ figure: <key=value pairs>` | Figure marker with caption, alt text |
| `ocr` | `#@ ocr: "<text>"` | OCR-extracted text from an image region |
| `describe` | `#@ describe: "<text>"` | LLM-generated image/figure description |
| `table` | `#@ table: <key=value pairs>` | Table structure marker |

### Two-Tier Annotation Model

Positional markdown uses two annotation layers that compose:

1. **`#@` block annotations** — map text blocks to spatial panels. Parsed by `BlockAnnotationParser`. Produces clean text + `List<BlockAnnotation>` with type, key-value params, and text offsets.

2. **`word[alias]` inline annotations** — map individual words to entity aliases. Parsed by existing `AnchorAnnotationParser`. Produces clean text + `List<ParsedAnchor>` with alias, surface form, and offsets.

Both are strippable. The processing pipeline: raw positional markdown → strip `#@` lines (block annotations extracted) → strip `word[alias]` brackets (inline anchors extracted) → clean text for chunking/embedding.

### Multi-Page Documents

Multi-page documents use `#@ page:` annotations to mark page boundaries. Each page can have its own layout if the document structure changes across pages. For documents with consistent layout, a single frontmatter declaration covers all pages.

```markdown
---
source_format: pdf
source_pages: 3
layout: header-body-footer
---

#@ page: 1
#@ panel: header
# Chapter 1: Introduction

#@ panel: body
The study examined...

#@ panel: footer
Page 1

#@ page: 2
#@ panel: body
Continued analysis showed...
```

For documents where layout changes per page, use `#@ layout:` annotations:

```markdown
#@ page: 1
#@ layout: single
Full-width title page content...

#@ page: 2
#@ layout: 2-column
#@ panel: left
Left column text...
```

**Layout override precedence rules:**

1. **Frontmatter `layout:` is the default** — applies to all pages that do not carry an explicit `#@ layout:` annotation
2. **`#@ layout:` is page-scoped** — overrides the layout for that specific page only. It does NOT propagate to subsequent pages
3. **Subsequent pages revert to the frontmatter default** — a `#@ layout: single` on page 1 does not affect page 2 (which uses the frontmatter layout unless it has its own `#@ layout:`)
4. **Per-page layout overrides use preset panel definitions** — an `#@ layout: single` page gets the preset's `main` panel, regardless of any custom `panels:` defined in the frontmatter. Frontmatter panel definitions apply only to pages using the frontmatter layout
5. **A page with `#@ layout: ad-hoc` at page level is an error** unless inline `#@ panel:` definitions follow with explicit coordinates (not yet supported — deferred to a future iteration. For now, ad-hoc layouts are frontmatter-only)

**Panel ID validation:** When `#@ panel: <id>` references a panel ID that does not exist in the active layout (e.g., `#@ panel: header` on a page with `2-column` layout, which only defines `left` and `right`), the parser:
1. Logs a warning identifying the undefined panel ID and the active layout
2. Assigns the text to the **first panel** in the active layout's panel list (e.g., `left` for `2-column`)

This prevents silent data loss while being lenient about imperfect parser output. The warning is surfaced via `ParseResult.extractedMetadata` as a `parse_warnings` field (comma-separated), allowing callers to detect and act on panel mismatches.

## Module Architecture

### Layer Placement

The corpus-management subsystem (`corpus-management-api`, `corpus-management`, and the new `corpus-management-parsers`) is not currently in the ARC42STORIES layer architecture. These modules form a management layer above L8 (Corpus SPI) and L9 (Corpus Runtime), providing managed entries with metadata, cover documents, and structured parsing.

The ARC42STORIES should be updated to add a layer designation for this subsystem. The proposed structure:

| Module | Tier | Hortora? |
|--------|------|----------|
| `corpus-management-api` | Pure Java, zero deps (Tier 1) | ✅ yes |
| `corpus-management` | CDI library (Tier 2/3) | casehub only (depends on platform types via InteractionContext) |
| `corpus-management-parsers` | PDFBox, POI, Tika deps (Tier 3) | ✅ yes (domain-neutral, no platform deps) |

**Follow-up:** File GitHub issue to update ARC42STORIES with the corpus-management layer.

### New Module: `corpus-management-parsers`

**Maven coordinates:** `io.casehub:casehub-neocortex-corpus-management-parsers`
**Package:** `io.casehub.neocortex.corpus.management.parsers`

#### DocumentParser SPI

```java
public interface DocumentParser {
    ParseResult parse(InputStream content, String sourceRef, DocumentParserConfig config);
    Set<String> supportedMediaTypes();
}
```

```java
public record ParseResult(
    String positionalMarkdown,
    Layout layout,
    Map<String, String> extractedMetadata,
    List<ImageRegion> imageRegions
) {}
```

```java
public record Layout(
    String name,
    List<PanelDefinition> panels,
    int pageCount,
    int[] pageSize
) {}
```

`Layout` carries the structured layout data that `PositionalMarkdownBuilder` needs to construct the YAML frontmatter. `PanelDefinition` is the same record used by `LayoutClassifier` (shared type in `corpus-management-api`). `extractedMetadata` remains `Map<String, String>` for flat document metadata (title, author, date) — layout data is not mixed in.

```java
public record ImageRegion(
    String panelId,
    int pageNumber,
    String captionText,
    String ocrText,
    String llmDescription,
    byte[] imageBytes
) {}
```

**Image bytes lifecycle:** `imageBytes` are transient — used during parsing to produce OCR text and LLM descriptions, then discarded. They are NOT stored in the corpus. The original binary document is preserved via `artifactRef` (cover document pattern, D1), and images can be re-extracted from the original document at any time. This avoids duplicating image storage and keeps `CorpusEntry` lightweight. The `#@ figure:` and `#@ ocr:` annotations in the positional markdown carry the text representations; the `#@ describe:` annotation carries the LLM description. If a consumer needs the original image, they follow `artifactRef` to the binary document and re-extract.

```java
public record DocumentParserConfig(
    boolean ocrEnabled,
    boolean llmImageDescriptionEnabled,
    boolean llmLayoutDetectionEnabled,
    int maxPages
) {
    public static DocumentParserConfig defaults() {
        return new DocumentParserConfig(true, false, false, Integer.MAX_VALUE);
    }
}
```

`DocumentParserConfig` carries **cross-cutting per-invocation options** only. Format-specific options (PDF passwords, OCR language, DOCX track-changes visibility, image DPI) are construction-time concerns for each `DocumentParser` implementation — injected via Quarkus `@ConfigMapping` or constructor parameters. This keeps the SPI's format-agnostic contract clean: callers pass `DocumentParserConfig` without knowing which parser handles the document.

#### DocumentParser vs MetadataExtractor vs TikaDocumentParser

Three document processing components exist, serving different layers:

| | DocumentParser (new) | MetadataExtractor (existing) | TikaDocumentParser (existing) |
|---|---|---|---|
| **Module** | `corpus-management-parsers` | `rag-api` (SPI) | `rag-tika` |
| **Input** | Binary document (InputStream) | Raw bytes from CorpusReader | Binary document (InputStream) |
| **Output** | Positional markdown + metadata + image regions | Flat text + metadata (`ExtractionResult`) | `List<ChunkInput>` (ready for embedding) |
| **Purpose** | Structure-preserving conversion | Content extraction for RAG | Content extraction + chunking (flat text) |
| **When** | Before `CorpusEntryStore.add()` | During `CorpusIngestionService` polling | Standalone parsing utility |
| **Used by** | corpus-management consumers | RAG pipeline | Direct callers (not in the ingestion pipeline) |

**TikaDocumentParser** in `rag-tika` is a standalone utility that uses Tika's `AutoDetectParser` to extract flat text from PDFs/DOCX/images, then chunks via `TextChunker`. It is NOT superseded by the new `DocumentParser` implementations. The new `PdfDocumentParser` uses Apache PDFBox directly (not Tika) for structural text extraction with positions — a fundamentally different approach that preserves spatial layout. `DocxDocumentParser` uses Apache POI. `ImageDocumentParser` uses Tika's `TesseractOCRParser` for OCR only.

`GardenMetadataExtractor` (markdown → flat text for RAG) is not replaced.

#### Ingestion path constraint

Positional markdown documents MUST go through the corpus-management path:

```
DocumentParser → PositionalMarkdownBuilder → CoverDocumentParser → CorpusEntryStore.add() → ingestEmbedding() → StructuralChunker
```

They must NOT enter the system via `CorpusStore` → `CorpusIngestionService`. The `CorpusIngestionService` path uses `MetadataExtractor` (strips frontmatter) + `TextChunker` (character-based splitting with no structural awareness). `#@` annotations would be treated as ordinary text and structural chunking would be silently skipped. The `content_format: positional-markdown` metadata field is set by `PositionalMarkdownBuilder` — if a positional markdown file were written directly to a `CorpusStore`, this metadata would not be set and the detection in `ingestEmbedding()` would not trigger.

#### Implementations

| Class | Format | Dependencies |
|-------|--------|-------------|
| `PdfDocumentParser` | PDF | Apache PDFBox (structural text extraction with positions) |
| `DocxDocumentParser` | DOCX | Apache POI (paragraph/table/image extraction) |
| `ImageDocumentParser` | PNG, JPEG, TIFF | Apache Tika with TesseractOCRParser |

Each implementation:
1. Extracts text blocks with spatial positions from the source format
2. Classifies the page layout (programmatic heuristics, or LLM vision if enabled)
3. Assigns text blocks to panels based on position
4. Generates positional markdown with `#@` annotations
5. Extracts images and produces OCR text + optional LLM descriptions

### LLM Integration

LLM vision calls are gated by two independent config flags:

| Flag | Default | Purpose |
|------|---------|---------|
| `casehub.corpus.parsers.llm.layout-detection.enabled` | `false` | Classify page layout and panel structure via LLM vision |
| `casehub.corpus.parsers.llm.image-description.enabled` | `false` | Generate natural language descriptions of images/figures |

When layout detection is enabled, the parser sends the rendered page image to the LLM and receives a layout classification + panel boundaries. This produces more accurate panel assignments for complex layouts (forms, worksheets, multi-panel documents) than programmatic heuristics alone.

When image description is enabled, each extracted image is sent to the LLM for a natural language description. The description is included in the positional markdown via `#@ describe:` annotations.

#### LLM Vision SPIs

LLM vision is accessed through two narrow SPIs in `corpus-management-api`, not through `AgentProvider` (which is `io.casehub.platform.agent.AgentProvider` from `casehub-platform-agent-api` — a casehub platform type, not LangChain4j). Coupling the parsers module to `casehub-platform-agent-api` would break domain neutrality.

The two LLM vision operations have fundamentally different return types and are modelled as separate SPIs:

**Image description** — produces a natural language `String`:

```java
@FunctionalInterface
public interface ImageDescriber {
    String describe(byte[] imageBytes, String mimeType);
}
```

**Layout classification** — produces structured layout data (layout name + panel boundaries with normalized coordinates):

```java
public record PanelDefinition(String id, double x, double y, double w, double h) {}

public record LayoutClassification(String layoutName, List<PanelDefinition> panels) {}

@FunctionalInterface
public interface LayoutClassifier {
    LayoutClassification classify(byte[] pageImage, String mimeType);
}
```

Both SPIs are in `corpus-management-api` (Tier 1), keeping the parsers module domain-neutral. The casehub platform provides `AgentProvider`-backed implementations. Hortora or other consumers can provide their own implementations using any LLM client.

When a config flag is enabled but the corresponding SPI is unavailable (CDI `Instance.isUnsatisfied()`), a warning is logged and the feature degrades gracefully to programmatic-only. `ImageDescriber` gates `#@ describe:` annotation generation. `LayoutClassifier` gates LLM-assisted layout detection — without it, programmatic heuristics (PDFBox text block positions) are used.

## PositionalMarkdownBuilder

New class in `corpus-management-parsers`, analogous to `CoverDocumentGenerator` for transcripts:

```java
public class PositionalMarkdownBuilder {

    public String build(ParseResult parseResult, String artifactRef) { ... }
}
```

**Module:** `corpus-management-parsers`
**Input:** `ParseResult` (from `DocumentParser.parse()`) + `artifactRef` (reference to the original binary document)
**Output:** A YAML-frontmatter cover document string, suitable for `CoverDocumentParser.parse()`

The output has this structure:

```yaml
---
id: <generated CE-YYYYMMDD-XXXXXX>
content_format: positional-markdown
source_format: <from parseResult.extractedMetadata()>
source_pages: <from parseResult.layout().pageCount()>
page_size: <from parseResult.layout().pageSize()>
layout: <from parseResult.layout().name()>
panels:
  - id: <from parseResult.layout().panels()>
    x: <normalized x>
    y: <normalized y>
    w: <normalized width>
    h: <normalized height>
artifact_ref: <artifactRef>
---
<positional markdown body from parseResult>
```

**Data sources for frontmatter fields:**
- `layout`, `panels`, `source_pages`, `page_size` — from `parseResult.layout()` (structured `Layout` record)
- `source_format`, `title`, `author`, etc. — from `parseResult.extractedMetadata()` (flat `Map<String, String>`)
- `content_format` — hardcoded `"positional-markdown"` by the builder
- `artifact_ref` — from the `artifactRef` parameter

The `content_format: positional-markdown` metadata field is the structural signal used by `SqliteCorpusEntryStore.ingestEmbedding()` to detect positional markdown and route to `StructuralChunker`.

**CorpusType:** A new `CorpusType.DOCUMENT` constant is defined in `corpus-management-parsers` (not in `corpus-management-api` — follows the same remediation direction as audit L2, which moves domain-specific constants out of the API). Uses the actual `CorpusType` record constructor and `FieldSchema` enum values (consistent with `BuiltInCorpusTypes`):

```java
public static final CorpusType DOCUMENT = new CorpusType(
    "document",
    Map.of("content_format", FieldSchema.STRING,
           "source_format", FieldSchema.STRING,
           "layout", FieldSchema.STRING),
    Map.of("artifact_ref", FieldSchema.STRING,
           "source_pages", FieldSchema.INTEGER),
    null
);
```

Required fields: `content_format` (discriminator for `ingestEmbedding()`), `source_format` (original file type), `layout` (layout name or `ad-hoc`). Optional fields: `artifact_ref` (path to original binary — also stored as `CorpusEntry.artifactRef()`), `source_pages` (page count for multi-page documents).

## BlockAnnotationParser

New parser in `annotation-api`, analogous to `AnchorAnnotationParser`:

```java
public class BlockAnnotationParser {
    public BlockParseResult parse(String text) { ... }
}
```

```java
public record BlockParseResult(
    String cleanText,
    List<BlockAnnotation> annotations
) {}
```

```java
public record BlockAnnotation(
    String type,
    String value,
    Map<String, String> params,
    int startOffset,
    int endOffset
) {}
```

- Scans for lines matching `^#@\s*(\w+):\s*(.*)$`
- Strips `#@` lines from the text
- Records the text offset range each annotation applies to (from its position to the next `#@` or end of text)
- `type` is the annotation name (group 1: `panel`, `page`, `figure`, etc.)
- `value` is the raw parameter text after the colon (group 2), with leading/trailing whitespace stripped
- `params` is populated by parsing key=value pairs from the value string:
  - **Key=value pairs** (e.g., `caption="Fig 1" alt="diagram"`): parsed into the map. Quoted values have quotes stripped
  - **Single values** (e.g., `header`, `3`, `"extracted text"`): `params` is empty. Consumers use `value()` directly. Quoted single values have quotes stripped in `value()`
  - **Mixed** (e.g., `3 rows=5 cols=3`): the first token without `=` is the `value()`; remaining key=value pairs go into `params`

The `startOffset`/`endOffset` in `BlockAnnotation` refer to positions in the `cleanText` (after `#@` lines are removed), consistent with how `ParsedAnchor` offsets work in `AnchorAnnotationParser`.

## Structure-Aware Chunking

### StructuralChunker Interface

New interface in `corpus-management-api` (Tier 1 SPI — `SqliteCorpusEntryStore` in `corpus-management` consumes it via CDI `Instance<StructuralChunker>`, so the interface must be in a module that `corpus-management` already depends on. Implementations go in `corpus-management-parsers` (Tier 3). This follows the module-tier-structure protocol: SPI interfaces in the API tier, implementations in the runtime tier, dependency direction Tier 3 → Tier 1):

```java
public interface StructuralChunker {
    List<StructuredChunk> chunk(String positionalMarkdown, int maxChunkSize);
}
```

```java
public record StructuredChunk(
    String text,
    Map<String, String> metadata
) {}
```

The `metadata` map carries per-chunk structural context:

| Key | Example | Source |
|-----|---------|--------|
| `page` | `"3"` | `#@ page:` annotation |
| `panel` | `"main-left"` | `#@ panel:` annotation |
| `section` | `"Chapter 2: Methods"` | Nearest preceding markdown heading |
| `has_table` | `"true"` | `#@ table:` annotation presence |
| `has_figure` | `"true"` | `#@ figure:` annotation presence |

### Chunking Algorithm

1. Parse `#@` annotations via `BlockAnnotationParser` → clean text + annotations
2. Split at structural boundaries: `#@ page:`, `#@ panel:`, and `#@ layout:` annotations are hard split points. `#@ layout:` changes the active panel definitions for subsequent `#@ panel:` references on that page
3. Within a panel, split at heading boundaries if the panel text exceeds `maxChunkSize`
4. Within a section, fall back to character-based splitting (reuse `TextChunker.recursive()` logic) if text still exceeds limit. The overlap for fallback splitting is a construction-time parameter — the `StructuralChunker` implementation reads `casehub.corpus.parsers.chunk-overlap` from config at construction and passes it to `TextChunker.recursive(maxChunkSize, overlap)` internally. The `chunk()` method signature does not carry overlap because it is not a per-invocation concern
5. Very short chunks (< 20% of maxChunkSize) are merged with the next chunk in the same panel
6. Each chunk carries metadata from its enclosing annotations

### Integration with SqliteCorpusEntryStore

`SqliteCorpusEntryStore.ingestEmbedding()` is enhanced to detect positional markdown via the entry's metadata — not by scanning body content:

```java
private void ingestEmbedding(CorpusRef corpus, CorpusEntry entry) {
    List<ChunkInput> chunks;
    if ("positional-markdown".equals(entry.metadata().get("content_format"))) {
        // Structure-aware chunking for positional markdown
        List<StructuredChunk> structured = structuralChunker.chunk(entry.body(), chunkSize);
        chunks = structured.stream()
            .map(sc -> new ChunkInput(sc.text(), entry.id(), mergeMetadata(entry, sc)))
            .toList();
    } else {
        // Existing behavior: single chunk for plain text entries
        chunks = List.of(new ChunkInput(entry.body(), entry.id(), extractMetadata(entry)));
    }
    embeddingIngestor.ingest(corpus, chunks);
}
```

Detection uses `entry.metadata().get("content_format")` — a metadata field set by `PositionalMarkdownBuilder` during cover document generation. This is a structural signal set at parsing time, not a substring check on arbitrary body content. Plain text entries, transcripts, and garden entries do not carry this metadata field — no risk of false-positive detection.

The `StructuralChunker` is an optional dependency (via CDI `Instance<StructuralChunker>`). When not on the classpath, all entries use the existing single-chunk behavior.

## Configuration

```properties
# Document parser selection (classpath-activated, no explicit config needed)
# Each DocumentParser registers its supported media types

# OCR (via Tika's TesseractOCRParser — requires Tesseract on PATH)
casehub.corpus.parsers.ocr.enabled=true

# LLM vision features (independent flags)
casehub.corpus.parsers.llm.layout-detection.enabled=false
casehub.corpus.parsers.llm.image-description.enabled=false

# Chunking
casehub.corpus.parsers.chunk-size=512
casehub.corpus.parsers.chunk-overlap=64
```

## Data Flow

```
Binary document (PDF/DOCX/image)
    │
    ▼
DocumentParser.parse(inputStream, sourceRef, config)
    │
    ├─ PDFBox: extract text blocks with positions
    ├─ Tika TesseractOCR: extract text from images
    ├─ [optional] LayoutClassifier: classify layout → LayoutClassification
    ├─ [optional] ImageDescriber: describe images → String
    │
    ▼
ParseResult(positionalMarkdown, layout, metadata, imageRegions)
    │  ── layout: Layout(name, panels, pageCount, pageSize)
    │  ── imageBytes used for OCR/description, then discarded
    │
    ▼
PositionalMarkdownBuilder.build(parseResult, artifactRef)
    │  ── frontmatter: layout, panels, content_format: positional-markdown
    │  ── body: #@ annotated markdown
    │  ── analogous to CoverDocumentGenerator for transcripts
    │
    ▼
CoverDocumentParser.parse(coverDocument, CorpusType.DOCUMENT) → CorpusEntry
    │  ── metadata includes content_format: positional-markdown
    │
    ▼
CorpusEntryStore.add(corpus, entry)
    │
    ├─ SQLite: store entry (body as TEXT)
    │
    ├─ ingestEmbedding():
    │     ├─ detect: metadata.get("content_format") == "positional-markdown"
    │     ├─ StructuralChunker.chunk(body, maxChunkSize) → List<StructuredChunk>
    │     ├─ per chunk: AnchorAnnotationParser.parse(chunk.text) → cleaner text + anchors
    │     └─ EmbeddingIngestor.ingest(corpus, chunks)
    │
    ▼
Qdrant: chunks with per-chunk metadata (page, panel, section)
```

**Note:** Positional markdown documents must go through this corpus-management path. The `CorpusStore` → `CorpusIngestionService` path (used for file-based corpora like Hortora gardens) does not support structural chunking and would silently skip `#@` annotation processing.

## Testing Strategy

| Test level | What | How |
|-----------|------|-----|
| Unit | BlockAnnotationParser | Parse various `#@` annotations, verify clean text + offsets |
| Unit | StructuralChunker | Chunk positional markdown, verify split points and metadata |
| Unit | Layout presets | Verify preset panel coordinates |
| Unit | Each DocumentParser | Parse sample documents, verify positional markdown output |
| Integration | End-to-end ingestion | PDF → positional markdown → chunked → embedded |
| Contract | DocumentParser SPI | Abstract base test for parser implementations |

Sample test documents:
- Single-column PDF (simple case)
- Two-column academic paper (column detection)
- Form with labelled fields (ad-hoc panels)
- DOCX with tables and images
- Scanned image with text (OCR)

## Scope Boundary with #802

This issue (#787) delivers:
- Positional markdown format specification
- `BlockAnnotationParser` for `#@` annotations
- `DocumentParser` SPI + PDF/DOCX/image implementations
- `StructuralChunker` for structure-aware chunking
- Integration with `SqliteCorpusEntryStore`

Issue #802 (Phase 3 structural extraction) handles:
- Extracting Hortora-specific code to `corpus-management-hortora` module
- The audit's L7+L10 (GardenMetadataExtractor, CorpusIndexService extraction)
- The audit's L9 (ScoringStrategy SPI)

The audit's L1 (Content sealed hierarchy) is **partially resolved** by this issue's cover document pattern for **binary document formats** (PDF, DOCX, images) — D2 supersedes the audit's remediation direction for these formats. The cover document pattern converts binary documents to positional markdown, making them representable as `String body` with preserved spatial structure. Structured-text formats (FHIR JSON/XML, HTML, LaTeX, BibTeX) can already be stored as `String body` since they are text, but do not yet have format-specific `DocumentParser` implementations for structure-preserving conversion. The `DocumentParser` SPI is designed for extensibility — additional format parsers (e.g., `HtmlDocumentParser`, `FhirDocumentParser`) can be added without API changes. L1 remains partially open in #802's scope for structured-text formats that would benefit from structure-aware parsing.

## References

- `corpus-management-api/.../CorpusEntry.java` — current String body record
- `corpus-management/.../CoverDocumentParser.java` — existing cover document pattern
- `corpus-management/.../SqliteCorpusEntryStore.java` — current ingestEmbedding() behavior
- `rag-api/.../MetadataExtractor.java` — existing extraction SPI (not replaced)
- `rag-api/.../TextChunker.java` — existing chunker (not modified)
- `rag-tika/.../TikaDocumentParser.java` — existing Tika integration (standalone)
- `annotation-api/.../AnchorAnnotationParser.java` — existing inline annotation parser (neocortex L18 Annotation SPI)
- `docs/specs/2026-11-04-corpus-domain-abstraction-audit.md` — audit L1 analysis
- ytt annotation convention — `#@` syntax precedent
- decisions.md — all design decisions with rationale and alternatives

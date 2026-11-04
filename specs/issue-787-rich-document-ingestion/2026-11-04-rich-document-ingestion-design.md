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

## Module Architecture

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
    Map<String, String> extractedMetadata,
    List<ImageRegion> imageRegions
) {}
```

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

#### DocumentParser vs MetadataExtractor

These serve different layers:

| | DocumentParser | MetadataExtractor |
|---|---|---|
| **Layer** | corpus-management (pre-processing) | rag (ingestion pipeline) |
| **Input** | Binary document (InputStream) | Raw bytes from CorpusReader |
| **Output** | Positional markdown + metadata | Flat text + metadata |
| **Purpose** | Structure-preserving conversion | Content extraction for RAG |
| **When** | Before `CorpusEntryStore.add()` | During `CorpusIngestionService` polling |
| **Used by** | corpus-management consumers | RAG pipeline |

`GardenMetadataExtractor` (markdown → flat text for RAG) is not replaced. A PDF corpus would use `PdfDocumentParser` to create the positional markdown entry, then `MetadataExtractor` to extract text for RAG indexing (which strips `#@` annotations and produces flat text).

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

Both require an `AgentProvider` (LangChain4j) on the classpath. When the flag is enabled but no `AgentProvider` is available, a warning is logged and the feature degrades gracefully to programmatic-only.

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
    Map<String, String> params,
    int startOffset,
    int endOffset
) {}
```

- Scans for lines matching `^#@\s*(\w+):\s*(.*)$`
- Strips `#@` lines from the text
- Records the text offset range each annotation applies to (from its position to the next `#@` or end of text)
- Parses key=value pairs from the parameter string (supports quoted values: `caption="Figure 1: Overview"`)

The `startOffset`/`endOffset` in `BlockAnnotation` refer to positions in the `cleanText` (after `#@` lines are removed), consistent with how `ParsedAnchor` offsets work in `AnchorAnnotationParser`.

## Structure-Aware Chunking

### StructuralChunker Interface

New interface in `corpus-management-parsers` (not in rag-api — this is a corpus-management concern):

```java
public interface StructuralChunker {
    List<StructuredChunk> chunk(String positionalMarkdown, int maxChunkTokens);
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
2. Split at structural boundaries: `#@ page:` and `#@ panel:` annotations are hard split points
3. Within a panel, split at heading boundaries if the panel text exceeds `maxChunkTokens`
4. Within a section, fall back to token-based splitting (reuse `TextChunker.recursive()` logic) if text still exceeds limit
5. Very short chunks (< 20% of maxChunkTokens) are merged with the next chunk in the same panel
6. Each chunk carries metadata from its enclosing annotations

### Integration with SqliteCorpusEntryStore

`SqliteCorpusEntryStore.ingestEmbedding()` is enhanced to detect positional markdown in the body:

```java
private void ingestEmbedding(CorpusRef corpus, CorpusEntry entry) {
    List<ChunkInput> chunks;
    if (entry.body().contains("#@ ")) {
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
    ├─ [optional] LLM vision: classify layout
    ├─ [optional] LLM vision: describe images
    │
    ▼
ParseResult(positionalMarkdown, metadata, imageRegions)
    │
    ▼
CoverDocumentParser.buildEntry(parseResult, artifactRef)
    │  ── frontmatter (layout + panels) + body (#@ annotated markdown)
    │
    ▼
CorpusEntry(id, metadata, body=positionalMarkdown, artifactRef)
    │
    ▼
CorpusEntryStore.add(corpus, entry)
    │
    ├─ SQLite: store entry (body as TEXT)
    │
    ├─ ingestEmbedding():
    │     ├─ BlockAnnotationParser.parse(body) → clean text + annotations
    │     ├─ StructuralChunker.chunk(body, maxTokens) → List<StructuredChunk>
    │     ├─ AnchorAnnotationParser.parse(chunk.text) → cleaner text + anchors
    │     └─ EmbeddingIngestor.ingest(corpus, chunks)
    │
    ▼
Qdrant: chunks with per-chunk metadata (page, panel, section)
```

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

The audit's L1 (Content sealed hierarchy) is resolved by this issue's cover document pattern — D2 explicitly supersedes the audit's remediation direction. #802 should be updated to remove L1 from its scope.

## References

- `corpus-management-api/.../CorpusEntry.java` — current String body record
- `corpus-management/.../CoverDocumentParser.java` — existing cover document pattern
- `corpus-management/.../SqliteCorpusEntryStore.java` — current ingestEmbedding() behavior
- `rag-api/.../MetadataExtractor.java` — existing extraction SPI (not replaced)
- `rag-api/.../TextChunker.java` — existing chunker (not modified)
- `rag-tika/.../TikaDocumentParser.java` — existing Tika integration (standalone)
- `annotation-api/.../AnchorAnnotationParser.java` — existing inline annotation parser (platform parent)
- `docs/specs/2026-11-04-corpus-domain-abstraction-audit.md` — audit L1 analysis
- ytt annotation convention — `#@` syntax precedent
- decisions.md — all design decisions with rationale and alternatives

# HANDOFF — casehub-neocortex

## Last Session

Brainstormed, designed, and partially implemented **#787** (Rich document ingestion). 6/9 tasks complete across 3 of 4 batches.

**Design decisions (10):** Cover document pattern (binary via `artifactRef`, positional markdown in `body`), `body` stays `String` (resolves audit L1 via cover document pattern rather than Content sealed hierarchy), positional markdown format with `#@` block annotations + layout frontmatter + normalized panel coordinates, three-layer image handling (caption + OCR + optional LLM), new `corpus-management-parsers` module, structure-aware chunking with per-chunk metadata, PDF+DOCX+images format scope, synchronous parsing, independent LLM config flags for layout detection vs image description.

**Implemented:**
- `BlockAnnotationParser` (15 tests) — parses `#@` annotations, produces clean text + offset-mapped annotations
- SPI types in `corpus-management-api` — `PanelDefinition`, `StructuredChunk`, `StructuralChunker`, `ImageDescriber`, `LayoutClassifier`, `LayoutClassification`
- `corpus-management-parsers` Maven module — `DocumentParser` SPI, `ParseResult`, `Layout`, `ImageRegion`, `DocumentParserConfig`, `LayoutPresets` (5 presets)
- `PositionalMarkdownBuilder` + `DocumentCorpusTypes.DOCUMENT`
- `DefaultStructuralChunker` (11 tests) — splits at `#@` page/panel/layout boundaries, heading fallback, character-based fallback, small chunk merging
- `SqliteCorpusEntryStore` integration — `ingestEmbedding()` detects `content_format: positional-markdown` metadata and routes to `StructuralChunker`

**All existing tests pass.** 133 corpus-management tests + 27 new corpus-management-api tests + 26 new parsers tests.

## Immediate Next Step

Complete **Batch 4: Document Parsers** — 3 remaining tasks:
- **Task 7: PdfDocumentParser** — Apache PDFBox (from Tika transitive 2.0.31) structural text extraction with position data, programmatic layout classification, `#@` panel annotation generation
- **Task 8: DocxDocumentParser** — Apache POI (from Tika transitive 5.2.5) paragraph/table/image extraction
- **Task 9: ImageDocumentParser** — Tika TesseractOCRParser for OCR text extraction

After Batch 4: completeness audit, then `work next` to advance queue.

## Key Design Details

- **Positional markdown format:** YAML frontmatter declares layout (preset name or ad-hoc with panel coordinates). Body uses `#@` block annotations (`panel`, `page`, `layout`, `figure`, `ocr`, `describe`, `table`). Two-tier annotation model: `#@` for block-level spatial, `word[alias]` for inline entity.
- **Panel coordinates are normalized** (0.0–1.0 relative to page dimensions) for format independence across PDF/DOCX/image.
- **Layout presets:** `single`, `2-column`, `3-column`, `header-body-footer`, `grid-2x2`
- **Detection signal:** `content_format: positional-markdown` metadata field set by `PositionalMarkdownBuilder` — not body scanning.
- **LLM SPIs:** `ImageDescriber` and `LayoutClassifier` in `corpus-management-api` (Tier 1), not coupled to platform `AgentProvider`.
- **Dependency note:** PDFBox and POI come from Tika 2.9.2 transitive deps (PDFBox 2.0.31, POI 5.2.5) — no separate declarations due to convergence enforcer.

## References

- `specs/issue-787-rich-document-ingestion/2026-11-04-rich-document-ingestion-design.md` — design spec (Standard reviewed, 3 rounds, approved)
- `specs/issue-787-rich-document-ingestion/decisions.md` — 10 decisions with rationale
- `plans/2026-11-04-rich-document-ingestion.md` — implementation plan (9 tasks, 4 batches)
- `.plan` — queue position 4/11, active batch: Document Parsers
- `docs/specs/2026-11-04-corpus-domain-abstraction-audit.md` — audit (L1 resolved via cover document)

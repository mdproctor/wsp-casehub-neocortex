# HANDOFF — casehub-neocortex

## Last Session

Completed **#787** (Rich document ingestion — Positional Markdown format). Full lifecycle: brainstorming → spec → Standard review → implementation plan → all 9 tasks implemented. Queue advanced to #802.

**What was built:**
- **Positional Markdown (PMD)** format — YAML frontmatter layout declarations + `#@` block annotations mapping text to spatial panels + existing `word[alias]` inline entity annotations. Normalized coordinates (0.0–1.0).
- **corpus-management-parsers** module — `DocumentParser` SPI with `PdfDocumentParser` (PDFBox heuristics), `DocxDocumentParser` (Apache POI), `ImageDocumentParser` (Tika TesseractOCRParser)
- **BlockAnnotationParser** — parses `#@` annotations, produces clean text + offset-mapped annotations (15 tests)
- **SPI types** — `PanelDefinition`, `StructuredChunk`, `StructuralChunker`, `ImageDescriber`, `LayoutClassifier`, `LayoutClassification` in corpus-management-api
- **DefaultStructuralChunker** — structure-aware chunking at `#@` boundaries with per-chunk metadata (11 tests)
- **SqliteCorpusEntryStore integration** — `ingestEmbedding()` detects `content_format: positional-markdown` and routes to `StructuralChunker`
- **PositionalMarkdownBuilder** + `DocumentCorpusTypes.DOCUMENT`
- **LayoutPresets** — single, 2-column, 3-column, header-body-footer, grid-2x2
- **Enrichment pipeline hooks** — `LayoutClassifier` and `ImageDescriber` SPIs tested with stubs, ready for ONNX implementations (#814)

**52 new tests** in corpus-management-parsers, **27 new tests** in corpus-management-api. All existing tests pass.

**Also this session:**
- Filed **#814** (ONNX document layout model — YOLOv10/RT-DETR enrichment for PdfDocumentParser)
- Wrote blog entry: "The Text That Remembers Where It Was" — PMD format rationale with SVG diagrams
- Researched HURIDOCS, Docling, RasgaPDF as prior art. HURIDOCS VGT (95.4% accuracy) is closest; PMD differs by inline annotations vs sidecar JSON.

## Immediate Next Step

Pick up **#802** (Phase 3 structural extraction — extract Hortora-specific corpus code to dedicated module). L/High. Requires brainstorming: whether to create `corpus-management-hortora` Maven module or keep Hortora code in existing module with package boundaries. Audit items: L7+L10 (GardenMetadataExtractor, CorpusIndexService), L9 (ScoringStrategy SPI). Branch `issue-802-extract-hortora-specific-corpus-code` exists.

**Note:** L1 from the audit (Content sealed hierarchy) is resolved by #787's cover document pattern — update #802 scope to remove L1.

## References

- `specs/issue-787-rich-document-ingestion/` — design spec, decisions, pipeline state
- `plans/2026-11-04-rich-document-ingestion.md` — implementation plan (9 tasks, 4 batches, all complete)
- `blog/2026-11-04-mdp03-the-text-that-remembers-where-it-was.md` — PMD blog entry
- `docs/specs/2026-11-04-corpus-domain-abstraction-audit.md` — audit (L1 resolved, L7-L10 next)
- `.plan` — queue: #802 (next active), #788, #804, #810, #811, #812
- GitHub #814 — ONNX document layout model follow-up

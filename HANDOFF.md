# HANDOFF — casehub-neocortex

## Last Session

Completed five issues from the **#875 web capture pipeline** epic (#882–#886). Two remain (#887, #888).

**What was built:**

- **#882 — HtmlDocumentParser** (`corpus-management-parsers`): HTML → positional markdown via readability4j (article extraction) + flexmark (HTML→markdown conversion). Started hand-rolled (314 lines), rewrote with libraries (131 lines). Setext→ATX heading post-processor for DefaultStructuralChunker compatibility. 21 tests.

- **#883 — WebCaptureService** (`corpus-management`): web-cache domain metadata conventions (`url`, `fetched_at`, `http_status`, `content_type`, `ttl_days`, `capture_method`). URL-based dedup within TTL. Stale re-fetch creates versioned entry with `updates` relationship. `findByMetadataField` added to CorpusEntryStore SPI with SQLite `json_extract` implementation. 10 tests.

- **#884 — webCapture MCP tool** (`corpus-management`): corpus-first web fetch on CorpusApi. Cache hit returns stored content (zero network). Cache miss fetches via HttpClient or pre-rendered HTML, parses via `HtmlToMarkdownParser` SPI, stores via WebCaptureService. `HtmlToMarkdownParser` @FunctionalInterface in corpus-management-api keeps Tika/PDFBox deps out of corpus-management. Backward-compatible CorpusApiBean constructor.

- **#885 — PDF visual archive**: optional `artifactRef` parameter on webCapture and WebCaptureService for agent-provided PDF snapshots (e.g. Playwright page.pdf()). Does not block text capture.

- **#886 — TTL-based curation**: `WebCacheCurationService.purgeExpired()` — scans web-cache entries past TTL, checks access-renewal via RetrievalTracker.findRetrievedDocumentIds(), exempts archived entries. 7 tests.

**Blog:** "The Corpus That Grows Itself" revised with implementation insights — library reuse, SPI decoupling, access-as-curation. Two SVGs created.

## Immediate Next Step

Pick up **#887** (Image capture and LLM description) and **#888** (Captcha inbox) to complete epic #875.

## References

- `docs/blog/2026-11-09-mdp01-the-corpus-that-grows-itself.md` — revised blog entry
- Branch: `issue-882-html-positional-markdown-parser` — 9 commits, all tests green

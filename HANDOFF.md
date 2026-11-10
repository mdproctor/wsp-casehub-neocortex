# HANDOFF — casehub-neocortex

## Last Session

Production readiness audit of the web capture pipeline revealed that **CorpusApiBean never uses WebPlatform** — the connector extraction (#896) moved code to connectors but never wired the bridge. Two parallel implementations exist. SessionTransfer (#893) is unreachable from MCP tools.

**Session work:**

### Landed on main

- **#893 — SessionTransfer** (connectors `91abe8e6`): `BrowserCookie` record, `SessionTransfer` sub-interface on `WebPlatform`, shared `CookieManager` in `DefaultWebPlatform`. All three connector modules (web-spi, web-ref, web) updated with tests.

- **#899 — End-to-end smoke test** (neocortex `939a4104`): 6-test class covering fresh capture, cache hit, image capture with relationships, intervention request/resolve/store, TTL curation purge + access renewal. In-memory stores, < 1 second.

- **#898 — Agent integration guide** (neocortex `939a4104`): Consumer guide section on webCapture, intervention workflow, image handling, cache behavior. corpus-management modules added to dependency table.

- **Renamed** `GardenReindexService` → `CorpusReindexService`, `GardenMetadataExtractor` → `CorpusMetadataExtractor` (neocortex `c45f5ce5`). Domain-neutral code, historical naming leak.

- **Blog revised** — "The Corpus That Grows Itself" updated with session transfer and connector extraction sections + 2 new SVGs.

### Closed without code

- **#802** — closed as obsolete (rename, not module extraction)
- **#804** — closed as implemented (research workspace already built across #810/#811/#812 + #895 epic)
- **#788** — closed as sufficient (entry-level annotations built; sub-document text fragment anchoring deferred)
- **#895 epic** — all 12 child issues closed

### Filed for next session

4 issues from production readiness audit, all on branch `issue-908-web-capture-bridge`:

## Immediate Next Step — Production Readiness (Branch: `issue-908-web-capture-bridge`)

Work through all 4 issues in order:

### #908 — Bridge CorpusApiBean to WebPlatform (M/Med) ← START HERE

The core fix. CorpusApiBean currently constructs its own HttpClient, HtmlToMarkdownParser, WebImageProcessor, and InterventionQueue inline. Must:

1. Add `connectors-web-spi` dependency to `corpus-management/pom.xml`
2. `@Inject Instance<WebPlatform>` into CorpusApiBean (graceful degradation)
3. Delegate fetch/parse/image/intervention to WebPlatform capabilities
4. Delete duplicate neocortex types: `HtmlToMarkdownParser` (corpus-management-api), `ImageDescriber` (corpus-management-api), `WebImageProcessor`, `InterventionQueue`, `InterventionRequest`, `InterventionResult`, `ImageProcessingResult`, `CapturedImage` (all corpus-management/impl)
5. Wire CDI in CorpusManagementBeans

**Key files to read first:**
- `corpus-management/src/main/java/.../impl/CorpusApiBean.java` — lines 604-619 (inline fetch), the webCapture method, and all constructors
- `corpus-management/src/main/java/.../cdi/CorpusManagementBeans.java` — CDI producers (currently no WebPlatform)
- `connectors/web-spi/src/main/java/.../spi/WebPlatform.java` — the target SPI
- `connectors/web/src/main/java/.../DefaultWebPlatform.java` — the implementation with shared CookieManager

**Connectors is on main** at `/Users/mdproctor/claude/casehub/connectors` with web-spi, web-ref, web modules.

### #909 — Config properties (XS/Low)

Add `casehub.web.intervention.timeout-minutes` (default 10) and `casehub.web.default-ttl-days` (default 30). Wire via CDI.

### #910 — MCP cache management tools (S/Low)

Add `purgeExpiredWebCache` mutation and `webCacheStatus` query to CorpusApi.

### #911 — Error handling on fetch failure (XS/Low)

Catch fetch exceptions in webCapture, return WebCaptureResult with error field instead of throwing RuntimeException.

## Queue

```
- [ ] casehubio/neocortex#908 — Bridge CorpusApiBean to WebPlatform ← active
- [ ] casehubio/neocortex#909 — Config properties for web capture
- [ ] casehubio/neocortex#910 — MCP tools for web cache management
- [ ] casehubio/neocortex#911 — Error handling on fetch failure
```

## References

- Connectors repo: `/Users/mdproctor/claude/casehub/connectors` (main, web modules landed)
- Neocortex branch: `issue-908-web-capture-bridge` (created, no commits yet)
- Audit: production readiness audit 2026-11-09 (7 findings → 4 issues)
- Blog: `docs/blog/2026-11-09-mdp01-the-corpus-that-grows-itself.md`

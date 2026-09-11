# Decisions — #305 Feedback Context Enrichment

## D1: Feedback context representation

**Choice:** FeedbackContext record with typed fields (issueRepo, issueNumber) + Map<String, String> attributes
**Alternatives:**
- Issue fields only — too narrow, next caller with different context breaks the SPI
- Generic Map<String, String> only — loses type safety, can't index efficiently in SQLite
- Typed fields for all known dimensions (no map) — every new dimension is an SPI break
**Rationale:** Follows established neocortex pattern (MemoryInput, ExperienceEvent, CbrQuery): typed fields for high-value known dimensions, attributes map for the long tail. FeedbackAttributeKeys constants class for standard keys (same as ExperienceAttributeKeys).
**Trade-offs:** Slightly more ceremony at the call site vs. bare parameters. Nullable FeedbackContext maintains backward compatibility.
**Sources:** MemoryInput (memory-api), ExperienceEvent (memory-api), ExperienceAttributeKeys, CbrQuery (memory-api), GardenMcpTools (caller with issueRepo/issueNumber)
**Exploration:** quick
**Status:** captured

## D2: SPI backward compatibility strategy

**Choice:** Default method bridge — add feedback(id, docId, outcome, context) as new primary; old 3-param signature becomes a default method delegating with null context
**Alternatives:**
- Replace in place — clean break but forces all callers to pass null explicitly
- Both abstract — doubles implementation surface for no benefit
**Rationale:** Zero breakage for existing implementors and callers. Default method bridge is the standard Java SPI evolution pattern. Implementors override only the 4-param method; old callers continue to work unchanged.
**Trade-offs:** Leaves a bridge method that slightly increases API surface. Acceptable — it's a standard Java pattern.
**Sources:** RetrievalTracker SPI (rag-api), SqliteRetrievalTracker, InMemoryRetrievalTracker
**Exploration:** quick
**Depends on:** D1 (FeedbackContext type)
**Status:** captured

## D3: RetrievalFeedback and findFeedback() evolution

**Choice:** Carry context on RetrievalFeedback, no findFeedback() signature change — callers post-filter
**Alternatives:**
- Carry + filtered query overload — adds findFeedback(corpus, since, until, FeedbackFilter) for server-side filtering. Premature — no caller needs SQL-level filtering yet.
- Carry + RetrievalAnalyzer slicing — adds context-aware analysis overloads. Also premature — YAGNI until a consumer needs grouped analytics.
**Rationale:** Matches existing RetrievalAnalyzer pattern: load all feedback in window, post-filter in Java (already done for retrievalId join — GE-20260719-59b809). Adding SQL-level filtering is a future enhancement when data volume warrants it.
**Trade-offs:** Post-filtering loads all feedback regardless of context. Acceptable at current scale — feedback volume is low. If it grows, add the SQL overload as a separate issue.
**Sources:** RetrievalAnalyzer.documentStats() (existing post-filter pattern), GE-20260719-59b809 (timestamp semantics)
**Exploration:** quick
**Depends on:** D1 (FeedbackContext type)
**Status:** captured

## D4: SQLite storage strategy for context

**Choice:** JSON TEXT column for attributes, dedicated indexed columns for typed fields. V2 Flyway migration adds issue_repo (TEXT), issue_number (INTEGER), attributes (TEXT/JSON) columns to retrieval_feedback. Composite index on (issue_repo, issue_number).
**Alternatives:**
- Separate key-value table — normalized but adds JOINs and complexity for a rarely-queried dimension
**Rationale:** Simple, matches how Qdrant stores payload. SQLite has json_extract() for ad-hoc queries if needed. Typed fields get indexed columns for efficient WHERE filtering; attributes map goes to JSON for the long tail.
**Trade-offs:** JSON column is not indexable by individual keys. Acceptable — attributes are for the long tail, not primary query dimensions.
**Sources:** SqliteRetrievalTracker V1 schema (rag-tracking), Qdrant payload storage pattern
**Exploration:** quick
**Depends on:** D1 (FeedbackContext type)
**Status:** captured

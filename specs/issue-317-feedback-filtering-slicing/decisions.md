# Decisions — #317/#318 Feedback Filtering and Analyzer Slicing

## D1: RetrievalAnalyzer coupling to findFeedback filter

**Choice:** RetrievalAnalyzer methods that accept a FeedbackFilter delegate to the filtered findFeedback overload internally — consistent usage, reduces in-memory work
**Alternatives:**
- Post-filter only — loads all feedback, filters in Java. Independent but redundant when SQL can do it.
**Rationale:** The filter exists to reduce data at the query level. Using it in the analyzer is the natural composition. #317 and #318 form a coherent pipeline: store → filter → analyze.
**Trade-offs:** Analyzer overloads now depend on the findFeedback overload existing. Acceptable — they're in the same module boundary (rag-api).
**Sources:** RetrievalAnalyzer.documentStats() (current post-filter pattern), FeedbackContext (from #305)
**Exploration:** quick
**Status:** captured

## D2: FeedbackFilter shape

**Choice:** Mirror FeedbackContext — issueRepo, issueNumber, Map<String, String> attributes. Each field nullable (null = don't filter). SQL uses indexed columns for typed fields, json_extract for attributes.
**Alternatives:**
- Typed fields only (no attributes filtering) — simpler SQL but loses the ability to filter by agentId, sessionId, etc.
**Rationale:** Consistency with FeedbackContext. Callers store attributes via FeedbackContext, they should be able to query by them. json_extract is available in SQLite.
**Trade-offs:** json_extract queries are not indexed — acceptable at current scale.
**Sources:** FeedbackContext record (rag-api), SqliteMemoryStore (json_extract pattern)
**Exploration:** quick
**Depends on:** D1 (analyzer uses filter)
**Status:** captured

## D3: RetrievalAnalyzer overload scope

**Choice:** documentStats + qualitySignals — the two methods that consume feedback data directly
**Alternatives:**
- All feedback-consuming methods (+ correlationGraph, documentImpact) — full coverage but YAGNI for graph-level analysis
- documentStats only — minimal, but qualitySignals callers can't pass filter through
**Rationale:** documentStats builds per-document feedback distributions; qualitySignals derives quality flags from those. Both benefit from context scoping. correlationGraph and documentImpact are more complex and no consumer needs filtered versions yet.
**Trade-offs:** correlationGraph and documentImpact remain unfiltered. Add overloads when a consumer needs them.
**Sources:** RetrievalAnalyzer (rag-api)
**Exploration:** quick
**Depends on:** D1 (analyzer uses filter), D2 (filter shape)
**Status:** captured

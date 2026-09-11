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

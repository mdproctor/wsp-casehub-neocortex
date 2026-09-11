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

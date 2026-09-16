# Decisions — Cognitive S-Batch (#340, #342, #344)

## D1: Corroboration matching strategy for #340

**Choice:** Subject-based matching — corroborate by querying for experience memories with the same `Subject(type, id)` in the same tenant
**Alternatives:**
- Text similarity (embedding-based) — catches semantically related experiences about the same entity even with different Subject records, but adds embedding dependency and latency to consolidation
- Domain-only grouping — groups by MemoryDomain only, too coarse — would count unrelated observations about different entities as corroboration
**Rationale:** Subject is the typed entity reference that already exists on every Memory. Same Subject = same entity. Simple, exact, no new infrastructure. Text similarity deferred to follow-up #346.
**Trade-offs:** Misses corroboration across different Subject records that refer to the same real-world entity (e.g., Subject("person", "alice") vs Subject("colleague", "alice")). Acceptable because Subject normalization is a separate concern, and the 3+ threshold is conservative enough that false negatives (failing to graduate) are less harmful than false positives (premature promotion).
**Sources:** Issue #340, Memory.java, Subject.java, MemoryQuery.forSubject()
**Exploration:** quick
**Status:** captured

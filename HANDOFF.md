# HANDOFF — casehub-neocortex

## Last Session

Issue triage and backlog hygiene. Closed 12 stale issues, transferred 2 to connectors.

### Issues closed as already done
- #611 — RoutingEmbeddingModel migration (already uses `DenseEmbedder`)
- #613 — RoutingChatModel migration (zero LangChain4j ChatModel refs)
- #614 — CosineSimilarity replacement (zero refs)
- #693 — Workbench JS→TS migration (all .ts files exist)
- #612 — DocumentSplitter decision (zero refs)
- #22 — Extract corpus CDI to corpus-quarkus (corpus is pure Java, moot)
- #473 — WordNetTermNormalizer general domain (already has it)
- #696 — Migrate attractor eval tests (110+ test refs in neocortex)
- #573 — Per-corpus directory structure (frida-kahlo/, napoleon/ exist)
- #575 — Edge type vocabulary (RelationshipVocabulary exists)

### Issues transferred to connectors
- #414 → connectors#184 — LLM extraction from unstructured sources (closed as speculative)
- #425 → connectors#185 — Tile38 geofencing evaluation (still open)

### Abandoned branches (no work done, safe to delete after 14 days)
- `issue-414-unstructured-extraction` — both repos
- `issue-611-routing-model-consumption` — both repos

## Immediate Next Step

**#360 — Extract cbr-algorithms from memory-api** (M/Med). Module extraction refactor — memory-api is 144 files with substantial pure-Java algorithm code (DTW, edit distance, CbrSimilarityScorer, TrendAnalyzer) alongside SPI interfaces. Extract to `cbr-algorithms` or `cbr-core` module.

Then: **#660 — Spring parity for cognition layer** (M/Med). Create `cognition-spring` module mirroring `CognitionDefaultBeans` CDI producers.

## References

- `specs/issue-477-relational-schemas/2026-10-28-relational-schemas-design.md` — reviewed spec (authoritative)
- `specs/issue-477-relational-schemas/decisions.md` — 4 design decisions with rationale

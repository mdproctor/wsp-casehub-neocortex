# HANDOFF — casehub-neocortex

## Last Session

<<<<<<< HEAD
Batch of 4 XS/S maintenance fixes on branch `issue-491-batch-fixes`, all landed on main. Blog entry written with 2 SVG diagrams.

### #491 — Priority collision renumber (8 files)

Two `@Priority` collisions in the consolidation pipeline: `BehavioralSynthesisPhase` and `RelationalSchemaEvolutionPhase` both at 19, `MergeDetectionPhase` and `DriveProfileDerivationPhase` both at 20. Renumbered the 19–27 range so all 22 phases have unique priorities. Drive chain ordering preserved. CLAUDE.md updated to match.

### #494 — Stale vocabulary in tests (2 files)

Replaced `"collaborative"` with `"cooperative"` in 4 memory-seeding test sites. Tests were passing via the `default -> {}` no-op branch — the drive modulation paths they claimed to test never executed.

### #713 — CognitionConfig toggle mapping (1 file)

Added 24-row Javadoc table to `CognitionConfig` mapping each boolean toggle to its `CognitionDefinition` YAML section and the orchestrator/prompt section it gates.
=======
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
>>>>>>> issue-360-extract-cbr-algorithms

### #715 — executionChainId on CbrPlanRecord (4 files)

<<<<<<< HEAD
Nullable `executionChainId` field for linking triage attempts into chains. Backward-compatible 8-arg constructor (27 existing call sites unchanged). Qdrant store serialises/deserialises via `_execution_chain_id` payload key. `withExecutionChainId()` convenience method. 3 new tests.

## Suggested Next

#587 — Graduated SituationClassifier (L/High). The priority renumbering fixed phase ordering, but `BehavioralSynthesisPhase` still depends on `RuleBasedSituationClassifier` which uses academic vocabulary that doesn't match runtime language. #587 wires the existing `LlmSituationClassifier` as a fallback and adds CBR confidence accumulation.

## References

- `blog/2026-10-29-mdp02-four-bugs-that-passed-ci.md` — diary entry with 2 SVG diagrams
=======
**#360 — Extract cbr-algorithms from memory-api** (M/Med). Module extraction refactor — memory-api is 144 files with substantial pure-Java algorithm code (DTW, edit distance, CbrSimilarityScorer, TrendAnalyzer) alongside SPI interfaces. Extract to `cbr-algorithms` or `cbr-core` module.

Then: **#660 — Spring parity for cognition layer** (M/Med). Create `cognition-spring` module mirroring `CognitionDefaultBeans` CDI producers.

## References

- `specs/issue-477-relational-schemas/2026-10-28-relational-schemas-design.md` — reviewed spec (authoritative)
- `specs/issue-477-relational-schemas/decisions.md` — 4 design decisions with rationale
>>>>>>> issue-360-extract-cbr-algorithms

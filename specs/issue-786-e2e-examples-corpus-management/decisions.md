# Decisions — #786 E2E Corpus-Management Examples

## D1: Domain count and selection

**Choice:** All 4 candidate domains — knowledge garden, literature review, clinical guidelines, game NPC world knowledge
**Alternatives:**
- 3 domains (drop clinical) — maximizes diversity without redundancy, but user wants full coverage
- 2 domains — minimal proof, insufficient coverage
**Rationale:** Full coverage as specified in the issue validates generality across the widest set of schema shapes
**Trade-offs:** Clinical guidelines and literature review have structural overlap (both document-oriented with versioning); the extra domain costs implementation time without proportionally more API coverage
**Sources:** casehubio/neocortex#786 issue body
**Exploration:** quick
**Status:** captured

## D2: Module shape — standalone example module

**Choice:** Single standalone Maven module under `examples/`, activated by `-Pexamples-smoke`
**Alternatives:**
- Integration tests in corpus-management test tree — lighter but less discoverable as reference code
- Both standalone + shared test harness — over-engineered for examples
**Rationale:** Standalone modules are the established pattern (example-rag-pipeline, example-text-analysis). Consumers find reference code in examples/, not buried in test trees
**Trade-offs:** Adds a POM and build profile entry; small maintenance surface
**Sources:** examples/example-rag-pipeline/ (existing pattern), examples/example-text-analysis/
**Exploration:** quick
**Status:** captured

## D3: Single vs multiple modules

**Choice:** Single module `example-corpus-management/` with 4 domain packages
**Alternatives:**
- 4 separate modules — proves zero coupling but adds POM sprawl and build overhead
**Rationale:** Side-by-side comparison across domains in one module is more useful for consumers evaluating the API. Domains are already isolated by package.
**Trade-offs:** Cannot prove absolute zero coupling at the dependency level (though package isolation achieves the same practical effect)
**Sources:** Existing single-module pattern in example-rag-pipeline/
**Exploration:** quick
**Status:** captured

## D4: Backend — in-memory only

**Choice:** In-memory backend (SQLite `:memory:` mode)
**Alternatives:**
- SQLite file-backed — slightly heavier, still no Docker
- Dual profiles (in-memory for smoke, SQLite for full) — mirrors example-rag-pipeline but adds complexity for examples
**Rationale:** Examples prove the API surface, not the storage backend. In-memory is fast, requires no cleanup, and is `-Pexamples-smoke` compatible.
**Trade-offs:** Doesn't exercise file-backed persistence paths; acceptable since corpus-management's own tests cover those
**Sources:** SqliteCorpusEntryStore `:memory:` support, example-rag-pipeline smoke profile pattern
**Exploration:** quick
**Status:** captured

## D5: CorpusType — custom types only

**Choice:** Each domain defines its own CorpusType with domain-specific FieldSchemas
**Alternatives:**
- Mix: garden reuses KNOWLEDGE_GARDEN constant, others custom — shows both paths but couples to Phase 2 removals
**Rationale:** Phase 2 (#801) will move KNOWLEDGE_GARDEN/RESEARCH/TRANSCRIPT out of CorpusType. Custom types are future-proof and directly prove domain neutrality — the whole point of #786.
**Trade-offs:** Garden example won't demonstrate backward compatibility with the built-in constant; acceptable since the constant will be removed anyway
**Sources:** Phase 2 roadmap in docs/specs/2026-11-04-corpus-domain-abstraction-audit.md, CorpusType record API
**Exploration:** quick
**Status:** captured

## D6: Federation — dedicated cross-domain scenario

**Choice:** A 5th demo class (`FederatedSearchScenario`) that creates corpora from 2+ domains and federates search across them
**Alternatives:**
- Embedded in one domain — muddies single-domain clarity
- Both per-domain + cross-domain — redundant federation coverage
**Rationale:** Federation is a cross-cutting concern that deserves its own scenario. Cleanly separates single-corpus search (per domain) from cross-corpus federation.
**Trade-offs:** Adds a 5th scenario class; minor
**Sources:** FederatedCorpusSearch SPI, CorpusQuery.federationDepth
**Exploration:** quick
**Status:** captured

## D7: Demo structure — scenario-based @QuarkusTest

**Choice:** Per-domain scenario classes as plain JUnit tests with manual wiring via shared test harness
**Alternatives:**
- @QuarkusTest scenarios — no CDI producers exist for corpus-management; would require writing producers just for examples
- Programmatic main() demos — works but JUnit gives assertions and test lifecycle
- Single orchestrated test — fast but monolithic, failure in one domain blocks others
**Rationale:** corpus-management is deliberately framework-neutral — all implementations use constructor injection, no CDI annotations. Self-review found no @ApplicationScoped beans. The module's own tests use the same pattern: `SqliteDataSourceFactory.create(":memory:")` → manual wiring. Examples should match.
**Trade-offs:** Doesn't prove CDI integration (because none exists). Consumers wanting CDI must write their own producers.
**Sources:** SqliteCorpusEntryStoreTest.java (existing pattern), SqliteCorpusCatalogue.java (no CDI annotations)
**Exploration:** quick
**Status:** revised (self-review: corpus-management has no CDI wiring)

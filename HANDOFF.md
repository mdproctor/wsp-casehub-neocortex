# HANDOFF — casehub-neocortex

## Last Session

Continued cognitive rearchitecture on `issue-253-cognitive-rearchitecture`. Completed 3 issues this session (#243, #245, #230 design), advancing queue from position 12 to 14 of 25.

1. **#243 — CognitiveProfile** (M): Cross-store entity resolution. CDI `@ApplicationScoped` bean in cognitive-index with `Instance<T>` graceful degradation. `resolve(CognitiveProfileQuery)` returns `Optional<EntityKnowledge>` aggregating MindMap node, direct edges, memories across 6 cognitive domains (experience, relationship, reflection, mood, engagement, affect), affect trajectory (via AffectTrajectoryAnalyzer composition), and NodeRef following (scheme="memory" resolved, scheme="cbr" recorded as unresolved). CognitiveProfileQuery with `byId`/`byName` factories, `withDomains()`/`withIncludeEdges()`/`withMemoryLimit()` builders. Dual entity ID resolution (nodeId + nodeName) catches memories under either convention. 32 tests (10 query + 5 record + 17 resolve). Decisions D33-D43.

2. **#245 — Graph reasoning exploration** (S): Assessed DesiredState (casehub/desiredstate repo) graph reasoning for MindMap integration. Verdict: DesiredStateGraph DAG data model doesn't apply (acyclic enforcement, dependency semantics incompatible with MindMap's cyclic semantic graph). BUT three algorithmic patterns ARE transferable: GraphRuleEngine (iterative pattern-match → mutate → convergence), PatternEvaluator (structural graph pattern matching), declarative rule model (@GraphRule). Platform extraction opportunity noted — pure graph reasoning could be extracted behind a generic graph interface, consumed by both desiredstate (DAG) and MindMap (general graph). Short-term: extend MindMapAnalyzer with findPaths/reachableFrom/connectedComponents.

3. **#230 — Memory space model** (M, design only): Brainstormed and wrote spec for private/shared/selective memory visibility. New `memory-space-api` module (tier-0, zero deps) with MemorySpace, SpaceType, Visibility (sealed: Private, Shared, Selective), SpaceMembership (temporal validity, opaque string roles). SpaceMembershipStore SPI with three-tier CDI (in-memory + SQLite). NoOpSpaceMembershipStore @DefaultBean for graceful degradation (singleton private space per agentId). Space-as-tenant model — each space IS a tenantId, visibility layer sits above stores. Per-record Selective filtering deferred (requires store changes). Decisions D44-D50.

Roadmap sections marked DONE: §4a (Cross-Store Entity Resolution), §4c (Graph Reasoning Integration). Full project compiles clean.

## Immediate Next Step

Run `work continue` then invoke `writing-plans` for #230. The spec is at `specs/issue-253-cognitive-rearchitecture/2026-08-31-memory-space-model-design.md`. Implementation: 3 new modules (memory-space-api, memory-space-inmem, memory-space-sqlite), ~17 tests across type validation and SpaceMembershipStore contract tests.

## What's Next

| Item | Scale / Complexity |
|------|--------------------|
| #230 — Memory space model (implementation) | M / Med |
| #233 — Cross-store retrieval modulation | M / Med |
| #240 — Perspectival affect overlays | M / Med |

## References

- Spec: `specs/issue-253-cognitive-rearchitecture/2026-08-31-cognitive-profile-design.md`
- Spec: `specs/issue-253-cognitive-rearchitecture/2026-08-31-memory-space-model-design.md`
- Assessment: `specs/issue-253-cognitive-rearchitecture/2026-08-31-graph-reasoning-assessment.md`
- Decisions: `specs/issue-253-cognitive-rearchitecture/decisions.md` (D33-D50 for this session)
- Roadmap: `docs/guides/cognitive-architecture-roadmap.md`
- Design: `docs/guides/shared-memory-design.md` (authoritative design for memory spaces)

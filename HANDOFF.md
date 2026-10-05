# HANDOFF — casehub-neocortex

## Last Session

Completed #418 (Knowledge Pipeline Phase 2) — all 7 child issues landed on main as 769d4758. Then brainstormed Phase 3 direction: dimensional memory (CBR-based operational knowledge beyond hierarchical LLM memory), auto-generated task briefs, persistent RAG-indexed web content, and CBR learning loops.

**Phase 2 final work (#423):**
- CDI wiring: @ApplicationScoped, @Inject, DefaultBeans producers with Instance<LocationPlatform> multi-provider discovery
- Audit: wired KnowledgePipelineMetrics (was dead code), fixed @ApplicationScoped scoping on 4 producers, added @PreDestroy for ResearchSessionStore
- Config: consolidated into @ConfigMapping, fixed shared SqliteConfig default collision (separate ResearchSqliteConfig)
- Tests: 104 total — CDI smoke test, refreshStale, subsumption, provider error isolation
- Squashed 13→8 commits, pushed, merged to main, branch stamped
- 3 garden entries captured (SmallRye config gotchas)

**Phase 3 R&D doc:** Written at `specs/2026-10-05-knowledge-pipeline-phase-3-rnd.md` — explores dimensional memory, task briefs, RAG content indexing, platform integration map, cost analysis, skeptical assessment, incremental build order.

## Immediate Next Step

No active branch. Options:
- Start Phase 3a (dimensional memory foundation) if ready to implement
- Return to #412 (activity/CRM tracking) which has a stale .plan
- Review the Phase 3 R&D doc and refine before committing to implementation

## References

- Phase 3 R&D: `specs/2026-10-05-knowledge-pipeline-phase-3-rnd.md`
- Phase 2 plan: `plans/2026-10-04-knowledge-pipeline-phase-2.md`
- Diary: `blog/2026-10-05-mdp01-when-the-wiring-is-the-feature.md`

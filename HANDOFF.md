# HANDOFF — casehub-neocortex

## Last Session

Cross-repo circular dependency resolution. Built `check_repo_cycles.py` in parent repo — scans all pom.xml files, builds inter-repo dependency graph, detects cycles. Eliminated 7 of 9 cycles across 8 repos by fixing ownership boundaries: CBR types to neocortex, trust pipeline to engine, GoalCompiler to desiredstate, routing bridge to engine, work adapter to engine. Each move was architecturally motivated, not just the smallest diff.

## Immediate Next Step

Resolve `platform ↔ neocortex` cycle — 5 memory-* implementation modules in platform need to move to neocortex (SPI migrated in #56, implementations stayed).

## Cross-Module

- engine `fix/352-work-adapter` tests skipped (pre-existing — `InboundWorkItemSchedulerImpl` deleted, but remaining tests need `maven.test.skip` removed and verified)
- CLAUDE.md has one stale reference: `CbrOutcomeConsumer` description says "depends on casehub-desiredstate-api" — should say types are in memory-api

## References

- `parent/scripts/check_repo_cycles.py` — cycle detection script
- `parent/build/modules-core.csv` — updated repo dependency declarations
- Blog: `blog/2026-09-17-mdp01-breaking-circular-repo-entry.md`
- Issues: #348 (CBR types), #349 (trust consolidation), #350 (GoalCompiler), #351 (routing), #352 (work adapter)

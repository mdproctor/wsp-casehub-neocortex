# HANDOFF — casehub-neocortex

## Last Session

Completed all cross-repo circular dependency resolution. Started at 9 cycles, now at 0.

This session resolved the final 2:
- **#353 platform↔neocortex** — the 5 memory-* implementation modules (inmem, jpa, sqlite, mem0, graphiti) had already been migrated and evolved in neocortex; platform copies were stale forks. Deleted 6 directories and 2 module declarations from platform. Downstream consumers (devtown, clinical) had already switched coordinates.
- **#354 life↔openclaw** — false positive. openclaw depends on pages + blocks-ui repos, not life. The cycle detection script was picking up extracted Maven metadata from `life/life-ui/.casehub-packages/`. Fixed by adding `.casehub-packages` to SKIP_PARTS and correcting the CSV declarations.

## Cross-Module

- engine `fix/352-work-adapter` tests skipped (pre-existing — `InboundWorkItemSchedulerImpl` deleted, but remaining tests need `maven.test.skip` removed and verified)
- CLAUDE.md has one stale reference: `CbrOutcomeConsumer` description says "depends on casehub-desiredstate-api" — should say types are in memory-api
- `fsitrading` has 4 undeclared cross-repo deps (desiredstate, ops, ras) — not cycles, just missing CSV entries

## References

- `parent/scripts/check_repo_cycles.py` — cycle detection script (now with `.casehub-packages` skip)
- `parent/build/modules-core.csv` — platform no longer depends on neocortex
- `parent/build/modules-applications.csv` — openclaw deps corrected to pages + blocks-ui
- Issues: #348–#352 (prior session), #353 (platform cleanup), #354 (false positive fix)

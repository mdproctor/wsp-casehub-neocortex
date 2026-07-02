# Handoff — 2026-07-02

## What Changed

Completed the `neural-text` → `neocortex` rename at the infrastructure level. Three GitHub repos renamed (`casehubio/neocortex`, `mdproctor/neocortex`, `mdproctor/wsp-casehub-neocortex`), local directories moved, all git remotes updated, symlinks recreated, Claude project memory directory renamed, stale paths in `.claude/settings.local.json` fixed.

Discovered workspace repos use separate GitHub repos (`wsp-casehub-*` naming) — nearly broke the workspace by pointing its remote at the project fork. Garden entry GE-20260702-fc769a captures the gotcha.

## Immediate Next Step

Rename is done. Restart the Claude session from `~/claude/casehub/neocortex` (CWD still points to the old path). Close `neural-text` project in IntelliJ, re-open from the new path.

**Deferred:** `platform/.github/workflows/publish.yml` line 44 needs `neural-text` → `neocortex` in the CI dispatch list — do this when platform resumes.

## What's Left

*Unchanged — `git show HEAD~1:HANDOFF.md`*

## What's Next

*Unchanged — `git show HEAD~1:HANDOFF.md`*

## Key References

- Prior rename entry: `blog/2026-07-01-mdp01-the-rename-that-touched-everything.md` (workspace)
- This session's entry: `blog/2026-07-02-mdp01-the-remote-that-pointed-somewhere-else.md` (workspace)
- Garden gotcha: `GE-20260702-fc769a` — workspace remote naming convention

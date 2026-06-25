# Handoff — 2026-06-25

## What Changed

Removed `@QuarkusMain` from `NativeImageGateCommand` (inference-quarkus). The annotation hijacked the entry point of every consuming application — Hortora engine printed "FAIL: model directory argument required" and exited on startup. Commit `cf7f381` on main. Closes Hortora/engine#25.

4 local commits not pushed to remote — push before starting new work.

## Immediate Next Step

Push unpushed commits: `git push origin main`. Then pick from backlog — run `/work` to start.

## Cross-Module

**We owe:**
- `parent` — casehubio/parent#306: update `docs/repos/casehub-neural-text.md` native image section · XS · Low
- `hortora/engine` — hortora/engine#20: drop native image CI, update CLAUDE.md/DESIGN.md · S · Low

## What's Next

*Unchanged — `git show HEAD~1:HANDOFF.md`*

Removed: #40 (closed — no migration needed).

## Key References

- Blog: `blog/2026-06-24-mdp16-gate-that-didnt-need-opening.md`
- Spec: *Unchanged — `git show HEAD~1:HANDOFF.md`*

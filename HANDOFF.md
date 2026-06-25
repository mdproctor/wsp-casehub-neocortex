# Handoff — 2026-06-25

## What Changed

Branch `issue-43-step-back-multi-query-expander` implements #43 (step-back prompting) and #42 (multi-query HyDE). Complete — 11 commits, all tests pass, whole-branch code review clean. Not yet merged to main.

Key changes: `QueryExpander` SPI returns `List<RetrievalQuery>` (was single). `rag-hyde` renamed to `rag-expansion` (module, package, classes, config namespace). `RrfFusion` utility in `rag-api`. Multi-query fan-out + RRF merge in both decorators. `StepBackQueryExpander` + `hypotheticalCount` on `LlmQueryExpander`. Filed #45 (parallel LLM calls).

## Immediate Next Step

Resume `work-end` to close the branch: squash, rebase onto main, push to fork, deliver to blessed repo, close #43 and #42. Run `/work end`.

## Cross-Module

**We owe:**
- `parent` — casehubio/parent#306: update `docs/repos/casehub-neural-text.md` — now includes QueryExpander, CRAG, expansion module · S · Low
- `hortora/engine` — hortora/engine#20: drop native image CI/docs · S · Low

## What's Next

*Unchanged — `git show HEAD~1:HANDOFF.md`*

Additions: #45 (parallel LLM calls for multi-query HyDE — filed this session, deferred).

## Key References

- Spec: `specs/issue-43-step-back-multi-query-expander/2026-06-25-query-expansion-redesign.md`
- Plan: `plans/2026-06-25-query-expansion-redesign.md`
- Blog: `blog/2026-06-25-mdp17-query-expansion-grows-up.md`
- Garden: `jvm/GE-20260625-85a3aa.md` (Mutiny empty-list gotcha), `tools/GE-20260625-6b49f5.md` (IntelliJ MCP technique)

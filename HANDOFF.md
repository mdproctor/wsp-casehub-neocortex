*Updated: casehubio/parent#272 closed — removed from references.*

# Handoff — 2026-06-18

## What Changed

Closed #37 — code review follow-ups from #35/#36. Added backwards-compatible `default retrieve()` overloads to `CaseRetriever` and `ReactiveCaseRetriever`. Fixed `tenantFilter` → `mergedFilter` parameter name in `ReactiveHybridCaseRetriever`. Added null-guard to `InMemoryCaseRetriever.matches()` for `In` filter. Promoted corpus-storage-module spec from workspace staging. ARC42STORIES.MD stale scan fixed #10 reference tense.

Cross-repo hygiene: stamped 18 unstamped branches (3 project, 15 workspace). Created `blog-routing.yaml` for 13 casehub workspaces. Published 9 missing blog entries to mdproctor.github.io. Fixed drafthouse CLAUDE.md (missing artifact/routing tables) and platform CLAUDE.md (missing JOURNAL.md line). Remote branch `origin/issue-25-embeddingmodel-bean` still exists on mdproctor/neural-text — deletable.

## Immediate Next Step

Pick from remaining backlog — all items are discretionary. Run `/work` to start.

## What's Next

*Unchanged — `git show HEAD~1:HANDOFF.md`*

## Key References

- Blog: `blog/2026-06-18-mdp13-fifteen-branches-and-nine-missing-posts.md`
- Cross-repo: casehubio/parent#272 — closed (PLATFORM.MD deep-dive shipped)

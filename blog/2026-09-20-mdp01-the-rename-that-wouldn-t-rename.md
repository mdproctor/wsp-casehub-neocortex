---
title: "The Rename That Wouldn't Rename"
entry_type: note
subtype: diary
author: mdp
series: casehub-neocortex
date: 2026-09-20
tags: [refactoring, intellij-mcp, vocabulary, cbr]
---

# The Rename That Wouldn't Rename

The CBR subsystem had a name collision that predated most of the current code. `CbrCase` — the base interface for case-based reasoning records — shared its primary noun with the engine's `CaseInstance`. Two different concepts, same word, different subsystems. The vocabulary spec (#376) laid out the fix: `CbrCase` becomes `CbrRecord`, and 40+ types follow the pattern through.

A mechanical rename. A spec with a complete vocabulary table. I expected half a day of IntelliJ refactoring and we'd be done.

## The symlink trap

The first rename — `CbrCase` → `CbrRecord` — failed. IntelliJ's refactoring engine reported "read-only files or unresolved conflicts." The dry run said `canApply: true`, zero conflicts. We tried everything: different targeting strategies, restarting IntelliJ, clearing caches, deleting `.idea`. Same error.

The culprit was a symlink. Neocortex has a `wksp` symlink pointing to the workspace repo — a separate git repository with specs, plans, and blog entries. IntelliJ follows symlinks when searching for text references in non-code files. When the refactoring tried to update markdown references to `CbrCase` through the symlink, it hit files in a foreign git context. Read-only from IntelliJ's write-action perspective. Abort.

Removing the symlink fixed the base rename. But then `ScoredCbrCase` → `CbrMatch` failed with the same error. This time, the root cause was different: IntelliJ was showing a preview dialog in the GUI for text-based replacements in markdown files. The MCP plugin can't interact with GUI dialogs — it just sees "refactoring aborted." I couldn't see the dialog; the error message was identical. The user spotted it: "it had a preview dialog for refactoring, I pressed Refactor so it went ahead."

Two failure modes, same error message, different root causes. The preview dialog issue recurred on every rename that touched many markdown files. We adapted: I'd fire the rename, the user would watch IntelliJ for the dialog.

## The actual rename

Once we worked out the interaction pattern, the rename itself was clean. 220 files, 3567 insertions, 3570 deletions. The numbers tell the story — nearly equal insertions and deletions means this was a pure vocabulary substitution.

The spec's vocabulary table drove everything:

- `CbrCase` → `CbrRecord` (base interface), `cbrType()` → `recordType()`
- `ResolvedCase` → `CbrPlanRecord`, `ResolutionGuide` → `CbrGuidanceRecord`, `FeatureVectorCbrCase` → `CbrFeatureRecord`
- `ScoredCbrCase<T>` → `CbrMatch<T>`
- `CbrCaseMemoryStore` → `CbrRecordStore` with ISP sub-interfaces renamed to `CbrRecordOps`, `CbrRecordRetrieval`, `CbrRecordLifecycle`, `CbrRecordAdmin`
- 17 store implementations, decorators, and tracking classes
- CDI events, adaptation SPIs, config types

The review caught one real issue: `CbrMatch` still had a `cbrCase` record component — the accessor `.cbrCase()` appeared 304 times across the codebase. Renamed to `cbrRecord`. The coherence audit then found 70 more camelCase `cbrCase` variables in production code and tests. All cleaned.

## What the spec got right

The vocabulary spec's "two nouns" principle — Case (the engine concept) and Cbr (the reasoning subsystem) — made every rename decision mechanical. No judgment calls. If a type had `CbrCase` in its name, replace with `CbrRecord`. If it had `PlanAdapter`, prefix with `Cbr`. The spec anticipated the full scope: 42 neocortex files, 117 downstream across 7 repos. We landed the neocortex side; downstream repos update next.

The decision to skip `@Deprecated` bridges was the right call for pre-release. Clean break, no backward-compat debt accumulating in the API. Every downstream repo updates in one pass.

## What's next

Downstream coordination: engine (6 files), blocks (24 files), aml (24 files), clinical (40 files), quarkmind (18 files with custom `implements CbrCase` renames), iot (4 files), platform (1 file). The spec has the full audit — each repo's affected types are documented. Separate issues, separate branches, no bridges needed.

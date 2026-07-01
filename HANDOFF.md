# Handoff — 2026-07-01

## What Changed

Completed #58 (CBR spec update), #59 (reconstructCase discriminator fix), and the bulk of #56 (memory backend migration). All CaseMemoryStore SPI types (17) and five backend modules (inmem, jpa, sqlite, mem0, graphiti) moved from casehub-platform to casehub-neural-text. Package renamed `io.casehub.platform.api.memory` → `io.casehub.memory` across 10 repos (63 files). CbrCaseEntry deleted (zero consumers). `cbrType()` discriminator added to CbrCase interface. All repos pushed to mdproctor and casehubio remotes.

Design review ran (4 rounds, 15 issues, all resolved, $15.16). Garden entry GE-20260701-30e901 (IntelliJ workspace move gotcha).

## Immediate Next Step

Branch `issue-56-memory-backend-migration` needs work-end completion: squash commits, rebase onto main, push. Then start #57 (rename neural-text → neocortex) while IntelliJ workspace is still configured.

## What's Left

- PLATFORM.md update — filed as casehubio/parent#336 · S · Low
- ARC42STORIES.MD update — add memory-* module layers · S · Low
- Hortora/engine stashed rag changes — `git stash pop` on `issue-30-bge-m3-multi-modal` branch · XS · Low

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #57 | Rename neural-text to neocortex | M | Low | Do while IntelliJ workspace is hot |
| #46 | SPLADE/reranker tuning | M | Med | Paused in stack |
| #39 | Dedicated RelevanceEvaluator model | L | High | R&D |

## Key References

- Spec: `specs/issue-56-memory-backend-migration/2026-07-01-memory-backend-migration.md`
- Plan: `plans/2026-07-01-memory-backend-migration.md`
- Blog: `blog/2026-07-01-mdp03-the-great-memory-migration.md`
- Garden: GE-20260701-30e901 (IntelliJ workspace move gotcha)

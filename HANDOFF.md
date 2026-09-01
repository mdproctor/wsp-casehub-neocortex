# HANDOFF — casehub-neocortex

## Last Session

Continued cognitive rearchitecture on `issue-253-cognitive-rearchitecture`. Completed #231 (Builder APIs), filed #255 (space model rearchitecture), reordered queue based on dependency analysis. Queue position 17→18 of 25 (one item removed, one added).

### Completed

1. **#231 — Builder APIs** (S): Added CbrQuery-style `of()`/`empty()` factories and `withX()` methods to 5 record types. MindMapQuery (of + 10 withers), NodeInput (of + 12 withers including withPad, withProperty), EdgeInput (of + 10 withers), NodeUpdate (empty + 14 withers), MemoryInput (of + withCaseId + withConfidence completing existing coverage). Eliminates positional-null constructor calls. 38 new tests across mindmap-api and memory-api. Decisions D58-D61.

### Architectural Discovery

**Space-as-tenant model is a design mistake (D58).** The memory-space modules (api, inmem, sqlite, testing, space CDI) built a second tenancy system inside the first. The correct model: tenant is the hard boundary (organisation — home, business). Individual vs common memory is a property of the memory itself (entityId), not a partitioning system. SpaceMembershipStore is authorization infrastructure that belongs in the platform, not in the cognitive subsystem. Filed #255 to remove/rearchitect.

### Queue Changes

- **Reordered queue** based on dependency analysis: #231 → #246 → #247 → remaining YAML path was wrong. Correct topological order: #231 → #255 → #246 → #247 → #248 → #249 → #250 → #251.
- **Filed #255** — Remove memory-space modules. Added to queue after #231.
- **Deferred #252** (Memory space YAML) — blocked by #255, removed from queue.
- **Updated #252 on GitHub** — body marked as blocked, new blocker #255 noted.

## What's Next

| # | Title | Scale | Complexity | Notes |
|---|-------|-------|------------|-------|
| 255 | Remove memory-space modules | M | Med | Next up — remove api/inmem/sqlite/testing/space modules, clean up PerspectivalResolver + CognitiveProfile space deps |
| 246 | API-to-YAML mapping audit | S | Low | Audit only — no code changes. Blocked by #231 (done) |
| 247 | YAML schema design | M | Med | Conventions doc + SealedHierarchyModule design. Blocked by #246 |
| 248 | Cognitive profile YAML | M | Med | Agent cognitive config file. Blocked by #247 |
| 249 | Declarative rule DSL | M | High | YAML trait rules + derived edge rules. Blocked by #247 |
| 250 | YAML-to-Java compiler | L | High | Build-time/startup YAML→CDI loader. Blocked by #248, #249 |
| 251 | Identity-cognition derivation | M | High | AgentDescriptor→CognitiveDefaults. Blocked by #248 |

## Branch State

- Branch: `issue-253-cognitive-rearchitecture`
- All tests pass (mindmap-api 53, memory-api MemoryInputTest 21)
- No uncommitted changes in project repo
- Memory saved: space-model-correction (project memory)

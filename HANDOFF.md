# HANDOFF — casehub-neocortex

## Last Session

Continued cognitive rearchitecture on `issue-253-cognitive-rearchitecture`. Completed #255 (remove memory-space modules) and #246 (API-to-YAML mapping audit). Queue position 18→20 of 25.

### Completed

1. **#255 — Remove memory-space modules** (M): Deleted all 5 memory-space modules (api, CDI, inmem, sqlite, testing — 1081 lines). Refactored PerspectivalResolver to use agentId property filter within the same tenant instead of SpaceMembershipStore lookup. Added OverlayRef.AGENT_ID constant. Removed deps from cognitive-index pom.xml. Updated CLAUDE.md (11 references removed) and cognitive-architecture-roadmap.md (1f and 5g marked REMOVED). Decisions D62-D64.

2. **#246 — API-to-YAML mapping audit** (S): Produced comprehensive audit of 54 config-surface types across 5 modules. 28 direct records, 13 enums, 8 sealed hierarchies (40 variants), 10 reference/SPI types, 3 unmappable. Identified 8 key blockers for #247 (YAML schema design): sealed discriminator convention, nested sealed depth, recursive structures, functional→named-reference pattern, DerivedEdgeRule DSL gap, Confidence shorthand, map-keyed types, platform type imports.

### Key Design Decision

**D63 — PerspectivalResolver uses agentId property, not SpaceMembershipStore.** Overlay nodes carry `agentId` as a node property. PerspectivalResolver searches by trait `"overlay"` within the caller-provided tenant, filters by property client-side. Signature changed from `resolve(sharedNodes, agentId, asOf)` to `resolve(sharedNodes, agentId, tenantId)`. No SpaceMembershipStore dependency remains in the codebase.

### User Guidance

Goal is **parity between Java + DSL (builders) + annotations and YAML** — all front ends should express the same configuration. The audit document maps each type's YAML-friendliness toward this goal.

## What's Next

| # | Title | Scale | Complexity | Notes |
|---|-------|-------|------------|-------|
| 247 | YAML schema design | M | Med | Next up — conventions doc + SealedHierarchyModule design. Builds on #246 audit's 8 blockers. Consider victools/jsonschema-generator reuse from engine. |
| 248 | Cognitive profile YAML | M | Med | Agent cognitive config file. Blocked by #247 |
| 249 | Declarative rule DSL | M | High | YAML trait rules + derived edge rules. Blocked by #247 |
| 250 | YAML-to-Java compiler | L | High | Build-time/startup YAML→CDI loader. Blocked by #248, #249 |
| 251 | Identity-cognition derivation | M | High | AgentDescriptor→CognitiveDefaults. Blocked by #248 |

## Branch State

- Branch: `issue-253-cognitive-rearchitecture`
- All tests pass (cognitive-index 100 tests, full build green)
- No uncommitted changes in project repo
- Audit document: `specs/issue-253-cognitive-rearchitecture/2026-09-01-api-to-yaml-audit.md`

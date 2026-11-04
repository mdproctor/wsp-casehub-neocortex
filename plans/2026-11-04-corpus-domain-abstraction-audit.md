# Corpus Domain Abstraction Audit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #785 — Audit corpus-management for domain abstraction
**Issue group:** #789 (parent epic)

**Goal:** Publish the domain abstraction audit to the project repo and file follow-up remediation issues for each phase.

**Architecture:** The audit spec is complete — 13 leaks catalogued across API and implementation layers, classified on three axes (consumer impact, remediation effort, Hortora breakage risk), with a 3-phase remediation roadmap. This plan covers publishing the audit and creating actionable follow-up issues.

**Tech Stack:** Git, GitHub CLI

## Global Constraints

- No code changes — this is a documentation-only audit
- The audit document is the deliverable
- Follow-up remediation issues reference the audit as the source of truth

---

## Batch 1: Publish audit and file remediation issues

### Task 1: Publish audit to project repo

**Files:**
- Create: `docs/specs/2026-11-04-corpus-domain-abstraction-audit.md`

**Interfaces:**
- Consumes: workspace spec at `specs/issue-785-audit-corpus-domain-abstraction/2026-11-04-corpus-domain-abstraction-audit.md`
- Produces: project-committed audit document referenced by #785

- [ ] **Step 1: Copy audit spec to project docs/specs/**

```bash
cp "$WORKSPACE/specs/issue-785-audit-corpus-domain-abstraction/2026-11-04-corpus-domain-abstraction-audit.md" \
   docs/specs/2026-11-04-corpus-domain-abstraction-audit.md
```

- [ ] **Step 2: Verify the file is in place**

```bash
head -5 docs/specs/2026-11-04-corpus-domain-abstraction-audit.md
```

Expected: the spec header showing issue #785.

- [ ] **Step 3: Commit**

```bash
git add docs/specs/2026-11-04-corpus-domain-abstraction-audit.md
git commit -m "docs(#785): corpus-management domain abstraction audit

13 leaks catalogued across API and impl layers. 3-phase remediation
roadmap: quick renames → API fixes → structural extraction.

Closes #785"
```

### Task 2: File Phase 1 remediation issue (quick renames)

**Files:** None — GitHub issue only

**Interfaces:**
- Consumes: audit document leak items L4, L6, L8, L11, L12
- Produces: GitHub issue tracking Phase 1 remediation

- [ ] **Step 1: Create Phase 1 issue**

```bash
gh issue create --repo casehubio/neocortex \
  --title "Remediate corpus-management naming leaks (Phase 1 from #785 audit)" \
  --body "$(cat <<'EOF'
## Context

The domain abstraction audit (#785) identified 5 naming leaks that are low-risk, XS-effort renames:

| Leak | Change |
|------|--------|
| L4 | `CorpusDescriptor.qdrantCollection` → `vectorCollection` or absorb into metadata |
| L6 | `CorpusEntry.frontmatter` → `metadata` |
| L8 | `FederationConfig.gardenId` → `corpusId` |
| L11 | ProvenanceStore `ge_id` column → `document_id` (Flyway migration) |
| L12 | `CorpusApiBean.gardenRoot` → `corpusRoot` |

## Approach

Find-and-replace with `ide_refactor_rename` where possible. L11 requires a Flyway migration for the SQLite schema change.

## Acceptance criteria

- All 5 renames landed
- No garden-specific naming remains in the files touched
- Existing tests pass unchanged (renames are internal)

Scale: S | Complexity: Low

Parent epic: #789
Audit reference: docs/specs/2026-11-04-corpus-domain-abstraction-audit.md
EOF
)" \
  --label "scale: S" --label "complexity: Low"
```

- [ ] **Step 2: Record the issue number**

Note the issue number for the .plan update.

### Task 3: File Phase 2 remediation issue (API fixes)

**Files:** None — GitHub issue only

**Interfaces:**
- Consumes: audit document leak items L2, L3, L5
- Produces: GitHub issue tracking Phase 2 remediation

- [ ] **Step 1: Create Phase 2 issue**

```bash
gh issue create --repo casehubio/neocortex \
  --title "Remediate corpus-management API-layer leaks (Phase 2 from #785 audit)" \
  --body "$(cat <<'EOF'
## Context

The domain abstraction audit (#785) identified 3 API-layer leaks requiring design:

| Leak | Change |
|------|--------|
| L2 | Move `CorpusType.KNOWLEDGE_GARDEN/RESEARCH/TRANSCRIPT` constants to a Hortora-specific class |
| L3 | Move `InteractionContext/InteractionType/ActivityType` from API to impl or transcript sub-package |
| L5 | Add vector/structured query support to `CorpusQuery` |

## Approach

Brainstorm-first — L2 and L3 are straightforward moves, but L5 requires designing the query type hierarchy. Consider sealed interface approach (`TextQuery`, `VectorQuery`, `HybridQuery`).

## Acceptance criteria

- No Hortora-specific constants in corpus-management-api
- No agent-interaction types in corpus-management-api
- CorpusQuery supports at least text + payload filter queries (L5 may be deferred)
- Existing Hortora consumers compile and pass tests against the moved types

Scale: M | Complexity: Med

Parent epic: #789
Audit reference: docs/specs/2026-11-04-corpus-domain-abstraction-audit.md
EOF
)" \
  --label "scale: M" --label "complexity: Med"
```

- [ ] **Step 2: Record the issue number**

### Task 4: File Phase 3 remediation issue (structural extraction)

**Files:** None — GitHub issue only

**Interfaces:**
- Consumes: audit document leak items L1, L7, L9, L10
- Produces: GitHub issue tracking Phase 3 remediation

- [ ] **Step 1: Create Phase 3 issue**

```bash
gh issue create --repo casehubio/neocortex \
  --title "Extract Hortora-specific corpus code to dedicated module (Phase 3 from #785 audit)" \
  --body "$(cat <<'EOF'
## Context

The domain abstraction audit (#785) identified structural changes needed to cleanly separate Hortora-specific corpus code:

| Leak | Change |
|------|--------|
| L1 | Introduce `Content` sealed hierarchy in `CorpusEntry` (String body → polymorphic content) |
| L7+L10 | Extract `GardenMetadataExtractor`, `CorpusIndexService` to `corpus-management-hortora` module |
| L9 | Extract scoring strategies behind a `ScoringStrategy` SPI |

## Approach

Brainstorm-first — this is the structural phase. Key decision: whether to create a new `corpus-management-hortora` Maven module or keep Hortora-specific code in the existing module with clear package boundaries.

## Suggested module structure

```
corpus-management-api/     -- SPIs (cleaned in Phase 2)
corpus-management/         -- Generic runtime
corpus-management-hortora/ -- Hortora-specific: GardenMetadataExtractor, garden scoring, GE-ID patterns
```

## Acceptance criteria

- `corpus-management-api` has zero Hortora-specific types or constants
- `corpus-management` runtime is domain-neutral
- Hortora-specific code lives in a clearly separated module/package
- A non-Hortora consumer can depend on corpus-management-api + corpus-management without pulling in Hortora concepts

Scale: L | Complexity: High

Parent epic: #789
Audit reference: docs/specs/2026-11-04-corpus-domain-abstraction-audit.md
EOF
)" \
  --label "scale: L" --label "complexity: High"
```

- [ ] **Step 2: Record the issue number**

- [ ] **Step 3: Commit plan**

```bash
git -C "$WORKSPACE" add plans/
git -C "$WORKSPACE" commit -m "wip(plan): implementation plan for #785 Refs #785"
```

## References

- [2026-11-04-corpus-domain-abstraction-audit.md] — design spec this plan implements
- [corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/] — API-layer source files audited
- [corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/] — impl-layer source files audited
- [corpus-api/src/main/java/io/casehub/neocortex/corpus/] — storage-layer SPIs audited
- [GitHub #785] — focal issue
- [GitHub #789] — parent epic

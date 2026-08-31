# Affect Trajectory Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to
> implement this plan task-by-task. Each task follows TDD. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #239 — Affect trajectory log
**Issue group:** #253, ..., #239

**Goal:** Log PAD changes on MindMap nodes as timestamped affect entries,
enabling trajectory analysis (slope, volatility, trend direction).

**Architecture:** Decorator on MindMapStore intercepts updateNode(),
detects PAD changes, stores domain="affect" memories via CaseMemoryStore.
Trajectory utility computes metrics from stored affect memories.

**Tech Stack:** Java 21, Quarkus CDI

## Batch 1: AffectEvents converter + AffectRecorded event

### Task 1: AffectEvents + AffectRecorded (memory-api)

- AffectEvents: static converter nodeId+tenantId+PAD → MemoryInput(domain="affect")
- AffectRecorded: CDI event record(nodeId, tenantId, memoryId)

### Task 2: AffectTrajectoryDecorator (mindmap CDI)

- @Decorator @Priority(65) on MindMapStore
- Intercepts updateNode, detects PAD change, stores affect entry
- Instance<CaseMemoryStore> for graceful degradation

## Batch 2: Trajectory analyzer + docs

### Task 3: AffectTrajectoryAnalyzer + AffectTrajectory (cognitive-index)

- Static utility: analyze(List<Memory>) → AffectTrajectory
- Computes pleasure slope, arousal volatility, trend direction

### Task 4: Documentation

- CLAUDE.md updates
- Roadmap §3b DONE

## References

- cognitive-architecture-roadmap.md §3b
- TraitApplicationDecorator.java @Priority(70)
- MoodEvents.java (converter pattern)
- ExperienceRecorded.java (CDI event pattern)
- GitHub #239

# Design Decisions — #923 personality+memory drive sources

## D1: Drive data source

**Choice:** Read existing drive-intensity nodes from COGNITIVE subgraph
**Alternatives:**
- Compute fresh each tick — independent of consolidation but expensive, duplicates work
- Hybrid (consolidated + per-tick scan) — most complete but most complex, premature
**Rationale:** The consolidation pipeline already writes drive-intensity nodes per agent from personality + accumulated experience. Reusing these avoids duplicate computation and keeps drives stable between consolidation cycles — which is physically realistic (drives don't change tick-to-tick from memory).
**Trade-offs:** Drives won't reflect very recent memories until next consolidation. Acceptable — drives are slow-moving personality-level states, not reactive signals.
**Sources:** CognitionObservationBuilder.loadDriveIntensityNodes (existing reader), CuriosityDrive (pattern template), MindMap COGNITIVE subgraph
**Exploration:** quick
**Status:** captured

## D2: Personality fallback for cold start

**Choice:** CDE-derived — add drive baselines to CognitiveDefaults via CognitiveDerivationEngine
**Alternatives:**
- Inline in DriveSource — simpler but scatters personality→drive mapping across 3 classes
- DriveConfig static defaults — simplest but no personality influence at cold start
**Rationale:** CDE already derives personality-dependent defaults (regulation capacities, mood baselines, etc.) from disposition axes. Drive baselines are the same kind of derivation — centralising in CDE keeps one source of truth for personality→cognition mappings.
**Trade-offs:** Adds fields to CognitiveDefaults record (already large). Acceptable — drive baselines are a natural part of cognitive defaults.
**Sources:** CognitiveDerivationEngine.derive(), CognitiveDefaults record, DispositionAxes
**Exploration:** quick
**Depends on:** D1 (fallback only needed when COGNITIVE subgraph has no drive-intensity nodes)
**Status:** captured

## D3: One generic vs three separate DriveSource implementations

**Choice:** One generic MindMapDriveSource configured with target DriveAxis
**Alternatives:**
- Three separate (CompetenceDrive, AffiliationDrive, AutonomyDrive) — more room for future differentiation but premature since all follow the same read-from-MindMap pattern
**Rationale:** All three non-curiosity drives follow the same pattern: read drive-intensity node from COGNITIVE subgraph, fall back to CDE baseline. One class with axis configuration avoids duplication. If axes diverge later, extract then.
**Trade-offs:** Less room for axis-specific logic without conditional branches. Acceptable — YAGNI.
**Sources:** CuriosityDrive pattern (axis-specific because information-gap detection is unique to curiosity)
**Exploration:** quick
**Depends on:** D1, D2
**Status:** captured

## D4: Trigger string source

**Choice:** Use the drive-intensity node's `description` property, fall back to axis name
**Alternatives:**
- Personality summary ("cooperative social orientation") — static, always available but not memory-informed
- Intensity label ("strong drive") — simple but generic, no personality or memory context
**Rationale:** Consolidation already writes meaningful descriptions derived from personality + accumulated memories. Using them directly means the prompt gets context-rich trigger text ("deep need for social connection reinforced by recent collaborative successes") without computing anything new.
**Trade-offs:** Empty description at cold start before first consolidation. Fallback to axis name is acceptable for initial ticks.
**Sources:** CognitionObservationBuilder.loadDriveIntensityNodes (reads description property)
**Exploration:** quick
**Depends on:** D1
**Status:** captured

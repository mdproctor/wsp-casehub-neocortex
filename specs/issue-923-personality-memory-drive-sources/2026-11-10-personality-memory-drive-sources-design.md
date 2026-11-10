# Design: Personality+Memory-Driven DriveSource Implementations

**Issue:** casehubio/neocortex#923
**Date:** 2026-11-10
**Status:** approved

## Problem

The DriveOrchestrator uses stub DriveSource implementations for COMPETENCE, AFFILIATION, and AUTONOMY that return a static 0.1 intensity with trigger "stub". This makes drive prompt sections incoherent — appraisal modulation (#922) can't produce meaningful drive profiles from a 0.1 base, and the pipeline coherence eval (#894) scores 3/5.

CuriosityDrive is the only real DriveSource — it reads MindMap via InformationGapDetector and produces contextual intensities with descriptive triggers.

## Design

### MindMapDriveSource

A single generic `DriveSource` implementation parameterised by `DriveAxis`. Follows the CuriosityDrive pattern: read from MindMap, produce contextual intensity + descriptive trigger.

```java
public class MindMapDriveSource implements DriveSource {
    private final DriveAxis axis;
    private final MindMapStore mindMapStore;
    private final CognitiveDefaultsRegistry registry;

    public DriveIntensity evaluate(String agentId, String tenantId) {
        // 1. Search COGNITIVE subgraph for drive-intensity node
        //    matching this axis and agent
        // 2. If found: return node intensity + description
        // 3. If not found: return CDE-derived personality baseline
    }
}
```

**Data flow:**

```
Consolidation (sleep cycle)
    → writes drive-intensity nodes to COGNITIVE subgraph
        (personality baseline + memory-modulated intensity + description)

MindMapDriveSource.evaluate()
    → reads drive-intensity node from COGNITIVE subgraph
    → returns DriveIntensity(axis, intensity, description)
    → fallback: CognitiveDefaults.driveBaseline(axis) from CDE

DriveOrchestrator.tick()
    → MindMapDriveSource returns personality+memory base
    → DriveComposer modulates with mood + personality + narrative + appraisal
    → DrivePromptSection renders contextual drive profile
```

### CDE Drive Baselines (cold start fallback)

Add drive baselines to `CognitiveDefaults`, derived by `CognitiveDerivationEngine` from disposition axes:

| Disposition axis | Drive axis | Mapping |
|---|---|---|
| socialOrient | AFFILIATION | cooperative→0.6, moderate→0.4, independent→0.3 |
| ruleFollowing + riskAppetite | COMPETENCE | strict/aggressive→0.6, moderate→0.4, flexible/conservative→0.3 |
| autonomy | AUTONOMY | high→0.6, moderate→0.4, low→0.3 |

These are floor values — consolidation refines them from experience. The derivation uses the same `DispositionAxes` → numeric mapping pattern as `RegulationDefaults`.

### Wiring

In `CognitivePipelineBuilder.build()` and `CognitionTestHarness.Builder.build()`, replace the three stubs:

```java
// Before:
DriveSource competenceStub = (a, t) -> new DriveIntensity(DriveAxis.COMPETENCE, 0.1, "stub");

// After:
DriveSource competence = new MindMapDriveSource(DriveAxis.COMPETENCE, store, registry);
```

The `CognitionTestHarness` uses the same production `MindMapDriveSource` — no stubs, no mocks for drive sources. Test agents get personality-derived baselines from CDE, just like production.

### Trigger text

The drive-intensity node's `description` property provides the trigger for `DriveIntensity`. Consolidation writes descriptions derived from personality + accumulated memories (e.g., "strong mastery orientation reinforced by recent competitive successes"). At cold start before consolidation, falls back to the axis name ("competence").

## Scope

**In scope:**
- `MindMapDriveSource` class (cognition module)
- Drive baseline fields on `CognitiveDefaults` + derivation in CDE
- Wiring in `CognitivePipelineBuilder` and `CognitionTestHarness`
- Unit tests for MindMapDriveSource (with/without MindMap nodes)
- Verify pipeline coherence eval (#894) with real sources

**Out of scope:**
- Changes to consolidation (it already writes drive-intensity nodes)
- Changes to CuriosityDrive (stays separate — unique pattern)
- Changes to DriveComposer modulation (already works correctly)

## Test strategy

1. **MindMapDriveSource unit tests:** node present → returns node values; node absent → returns CDE baseline; no CDE entry → returns axis-name default
2. **CDE derivation tests:** verify disposition axes produce expected baselines
3. **Pipeline coherence eval (#894):** re-run with real sources, target 4+/5
4. **Harness integration test:** existing `AppraisalStatePropagationTest.harnessTickPropagatesAppraisalToDrives` should pass with real sources (competence no longer 0.1)

## References

- `CuriosityDrive` — pattern template for MindMap-reading DriveSource
- `CognitionObservationBuilder.loadDriveIntensityNodes` — existing reader for drive-intensity nodes from COGNITIVE subgraph
- `CognitiveDerivationEngine.derive()` — derivation point for personality→cognition mappings
- `DriveComposer.applyPersonalityModulation` — existing personality→drive modulation (post-hoc, stays unchanged)
- `AppraisalDriveModulator` (#922) — appraisal→drive pathway, benefits from realistic baselines
- Frijda (1986) action tendencies — grounded the emotion→drive mapping in #922
- Deci & Ryan (2000) SDT — CURIOSITY, COMPETENCE, AFFILIATION, AUTONOMY axes

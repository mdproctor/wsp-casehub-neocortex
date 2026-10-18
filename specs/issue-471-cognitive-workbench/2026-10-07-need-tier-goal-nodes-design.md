# Design: Store need-tier on GOAL nodes (#464)

## Problem

`NeedTier` enum exists (SAFETY, TASKS, SOCIAL, SELF_EXPRESSION, UNDERSTANDING) but is never set as a property on GOAL nodes in the MindMap. The goal dependency graph cannot show which need tier a goal serves, and the coaching system cannot prioritize goals by need hierarchy.

## Solution

Add `need-tier` as a string property on GOAL nodes at all creation points, derived from the goal's origin.

### DriveAxis → NeedTier mapping

| DriveAxis | NeedTier |
|-----------|----------|
| CURIOSITY | UNDERSTANDING |
| COMPETENCE | SELF_EXPRESSION |
| AFFILIATION | SOCIAL |
| AUTONOMY | SELF_EXPRESSION |

Static method `NeedTier.fromDriveAxis(DriveAxis)` in cognition-api provides the canonical mapping.

### Changes

1. **NeedTier.fromDriveAxis(DriveAxis)** — new static method returning the mapped tier.

2. **DriveGoalBridgeParticipant.createGoalNode()** — add `need-tier` property using `NeedTier.fromDriveAxis(proposal.axis()).name()`.

3. **DriveGoalBridgeParticipant.enrichExistingNode()** — also set `need-tier` on matched nodes so existing goals gain the property.

4. **GoalRecognitionPhase.run()** — add `need-tier` property with value `TASKS` (default for experience-recognized goals with no drive axis).

### Queryability

`need-tier` is a standard string property on MindMapNode. Existing `MindMapQuery` property filters work without changes — consumers can filter goals by `need-tier` immediately.

## Testing

- Unit test `NeedTier.fromDriveAxis()` covers all four axes.
- Existing `DriveGoalBridgeParticipantTest` extended to assert `need-tier` property on created and enriched nodes.
- Existing `GoalRecognitionPhaseTest` extended to assert `need-tier` = TASKS on recognized goals.

## References

- cognition-api/src/main/java/io/casehub/neocortex/cognition/need/NeedTier.java
- cognition-api/src/main/java/io/casehub/neocortex/cognition/drive/DriveAxis.java
- cognition/src/main/java/io/casehub/neocortex/cognition/goal/DriveGoalBridgeParticipant.java
- mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/GoalRecognitionPhase.java
- GitHub issue casehubio/neocortex#464

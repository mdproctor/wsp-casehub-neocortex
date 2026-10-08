# Design Journal — issue-478-sub-thought-tick-integration

## 2026-10-08 — Design + Batch 1 implementation

### Key architectural decision: FOUNDATION not DERIVED

The issue proposed SubThoughtTickParticipant at DERIVED phase (modeled on AppraisalTickParticipant). First-principles analysis showed this was wrong: sub-thought extraction is input parsing (text → typed structure), not cognitive evaluation. It has no dependency on mood, drives, or mental model state — only on observation text + entity names. DERIVED placement causes a one-tick lag for all high-value consumers (mental model runs in subject loop before DERIVED, drives.tick() runs first in DERIVED before custom participants).

FOUNDATION placement makes sub-thoughts available to all downstream phases in the same tick. The push/pull pattern follows naturally: push SubThoughtCue signals to MentalModelOrchestrator.record() (buffer consumed during subject loop), pull via accessor for drives, CAPS, and prompt rendering.

### Decision review caught a critical error in D2

The original plan called for four separate DriveSource classes (SubThoughtAffiliationDrive, etc.). The review agent read DriveOrchestrator and found DriveSource instances aren't CDI-discovered — DriveOrchestrator takes four named constructor parameters. The correct pattern is DriveComposer modulation via SubThoughtModulation.compute() following the NarrativeModulation precedent. This would have been a dead-end implementation path.

### Spec review surfaced ModulationLayer refactoring

The spec review proposed consolidating DriveComposer's separate nullable modulation map parameters into a `List<ModulationLayer>` — cleaner for N modulation sources and avoids the parameter explosion as more modulations are added. Also caught that SituationClassifier.classify() is only called from BehavioralSynthesisPhase (consolidation time), eliminating the "dual context" concern from D4.

### Batch 1 complete

SubThought, SubThoughtResult, SubThoughts utility, MentalStateSignal.SubThoughtCue, SubThoughtAttributeKeys.confidence(), CognitionConfig.subThoughtsEnabled, DriveConfig.subThoughtModulationStrength. 60 cognition-api tests pass. 4 batches remain.

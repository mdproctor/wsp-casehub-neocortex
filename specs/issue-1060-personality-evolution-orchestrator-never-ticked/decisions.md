# Decisions — #1060 Personality Evolution

## D1: Signal recording cadence

**Choice:** CDI event observer (event-driven)
**Alternatives:**
- TERMINAL tick participant — simpler wiring but runs even when nothing happened, wasteful
- Consolidation-only — delays signal recording by minutes, loses per-event granularity
**Rationale:** Signals should fire when events occur. CDI observers on `RelationshipRecorded`, `ExperienceRecorded` etc. match the existing event-driven patterns (`RelationshipObserver`, `SubThoughtExtractionObserver`). Zero overhead when no events arrive.
**Trade-offs:** More CDI wiring than a tick participant.
**Sources:** `RelationshipObserver.java`, `SubThoughtExtractionObserver.java` (CDI event patterns)
**Exploration:** quick
**Status:** captured

## D2: Evolution evaluation cadence

**Choice:** Consolidation phase
**Alternatives:**
- TERMINAL tick participant — per-agent context is free but evaluating every tick is wasteful for a slow process
- Throttled tick participant — tick participant with internal timer, adds complexity
**Rationale:** Personality evolution is inherently slow (days/weeks). Consolidation runs every few minutes — the right timescale. Consolidation phases enumerate agents per tenant via `EffectiveCognitiveDefaults.agentIds()`, which works for the multi-agent evaluation pattern.
**Trade-offs:** No per-agent context from CognitionTickContext; must resolve descriptors from DescriptorViewSource.
**Sources:** `ConsolidationScheduler.java`, `BehavioralSynthesisPhase.java` (consolidation phase patterns)
**Exploration:** quick
**Status:** captured

## D3: Propagation mechanism

**Choice:** Direct `EffectiveCognitiveDefaults.updateBase()` / `updateState()` call
**Alternatives:**
- CDI event + observer — decoupled but adds indirection
- Rely on CognitionCore.tick() path — requires Eidos descriptor to reflect profile store changes, which is the gap #1060 identifies
**Rationale:** PEO already has `EffectiveCognitiveDefaults` injected. Direct call is synchronous, explicit, no reliance on external descriptor refresh. Jungian evolution → `updateBase()` with new DescriptorView, PID-5 evolution → `updateState()` with homeOffset changes.
**Trade-offs:** Tight coupling between consolidation phase and EffectiveCognitiveDefaults.
**Sources:** `SituationalPersonalityParticipant.java:94` (existing updateState() pattern)
**Exploration:** quick
**Status:** captured

## D4: PID-5 scope

**Choice:** Include PID-5 facet evolution in this issue
**Alternatives:**
- Defer to separate issue — reduces scope but leaves the architecture half-built
**Rationale:** Jungian and PID-5 are the same fundamental process (accumulated pressure → lasting change). Building one without the other creates the artificial split the user identified. The convergence point (EffectiveCognitiveDefaults) already supports both paths.
**Trade-offs:** Larger scope (M → M+). Need PID-5 pressure sources and displacement-to-homeOffset graduation.
**Sources:** `PersonalityStateSnapshot.java` (homeOffset field exists but nothing writes it)
**Exploration:** quick
**Status:** captured

## D5: Unified signal model

**Choice:** Single `PersonalityPressure` signal type for all personality dimensions (Jungian terms and PID-5 facets), with one neocortex-native signal accumulator
**Alternatives:**
- Separate pipelines for Jungian (Eidos SignalStore) and PID-5 (displacement history) — preserves existing infrastructure but architecturally split
- Combined Eidos signal store extension — requires Eidos changes for a neocortex concern
**Rationale:** From first principles, both Jungian function evolution and PID-5 facet evolution are the same process: accumulated experiential pressure on a personality dimension causes lasting change. The dimension type (Jungian term vs PID-5 facet) determines what changes and where it propagates, not how signals accumulate. Separate signal stores for the same fundamental process is an accident of history.
**Trade-offs:** New signal accumulator replaces tested Eidos DispositionSignalStore. Eidos evolution SPIs (DispositionSignalStore, DispositionHealth, DispositionEvolution) become unused.
**Sources:** First-principles analysis
**Exploration:** deep-analysis
**Status:** captured

## D6: Architecture approach

**Choice:** Full neocortex unification — replace Eidos evolution SPIs with native evaluation
**Alternatives:**
- Adapter pattern — unified signals but delegate Jungian evaluation to existing Eidos SPIs. Less reimplementation but two evaluation paths remain.
**Rationale:** The evolution process (signal accumulation, threshold evaluation, decision-making) is a cognitive process that belongs in neocortex, not in the identity store (Eidos). Eidos should own identity state ("who this agent is") and provide read/write SPIs. Neocortex should own the process of change. The existing threshold/drift/dampening logic is not complex — the PEO test suite provides the behavioral specification for reimplementation.
**Trade-offs:** Reimplementation of evolution threshold logic. Eidos SPIs deprecated as follow-up.
**Sources:** `PersonalityEvolutionOrchestrator.java` (existing evolution logic), `PersonalityEvolutionOrchestratorTest.java` (behavioral spec)
**Exploration:** deep-analysis
**Depends on:** D5 (unified signal model)
**Status:** captured

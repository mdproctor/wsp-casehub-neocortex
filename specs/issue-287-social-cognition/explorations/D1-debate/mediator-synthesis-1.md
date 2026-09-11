# Mediator Synthesis — Architecture Debate Round 1

## Verdict: Position C Wins, With Position A's Bug Fix Absorbed

Position C is the right architecture. Position A identified a real bug that must be fixed within Position C's approach. Position B is the loser — it solves a problem that does not yet exist across types that do not yet need it.

## Why Position C Wins

The strongest argument in this entire debate is one Position C makes almost in passing: CognitiveProfile has **zero production callers**. This module is pre-consumer API. Positions A and B both propose re-architecting a system that has never been exercised under real load, with real caller patterns, by real consumers. That is exactly the condition under which large structural rewrites produce the wrong abstraction.

Position C's "extend the pattern" approach — one field addition to CognitiveProfileQuery, two new focused CDI beans — is the correct move for three reasons:

**First,** the codebase has 30+ modules with a proven small-type, focused-bean pattern. The module itself has 36 source files, 187 tests, and a largest class of 162 lines. Position A proposes replacing this with a compositional query engine that consolidates orchestration into one class. In a codebase where the largest class is 162 lines, introducing an orchestrator that absorbs three types' execution logic is a design regression, not an improvement.

**Second,** Position B's Perspective sealed interface adds perspective to every cognitive query type. But there is no evidence that perspectival TemporalIndex is needed. Adding a dimension to types that do not need it creates API surface area that must be tested, maintained, and explained — with zero current consumers to validate the design. When perspective becomes needed on TemporalIndex, adding PrincipalId later is backward-compatible.

**Third,** zero migration cost matters. Not because migration is expensive in absolute terms (7 call sites is trivial), but because migration forces a flag day where all tests must be rewritten simultaneously. Position C's 187 tests pass unmodified.

## What Position C Must Absorb From Position A

Position A's trajectory-before-perspective bug is confirmed and real. CognitiveProfile computes trajectory from the shared node's entity IDs, never consulting PerspectivalResolver. When the new `perspective` field is added to CognitiveProfileQuery, the fix is straightforward:

In CognitiveProfile.resolve(), when query.perspective() is non-null: (1) resolve the shared node, (2) call PerspectivalResolver to merge the overlay, (3) extract entity IDs from the **merged** node, (4) query memories from those IDs, (5) compute trajectory from those memories. The perspectival merge happens before trajectory computation. This is a ~15-line change inside the existing resolve() method.

## What the Final Architecture Looks Like

- **CognitiveProfileQuery** gains `PrincipalId perspective` (nullable). Backward-compatible.
- **CognitiveProfile.resolve()** applies PerspectivalResolver internally when perspective is set, BEFORE trajectory computation.
- **AffectComparator** — new @ApplicationScoped bean for #271 (multi-agent comparison).
- **CrossDomainAnalyzer** — new @ApplicationScoped bean for #283 (cross-domain correlation).
- **PerspectivalMerge, AffectTrajectoryAnalyzer** — unchanged pure static utilities.
- **PerspectivalResolver** — stays as-is internally; callers should prefer CognitiveProfile (which now composes it). Document the preferred path.

## What to Watch For

Position C's fragmentation risk is real but not yet present. The trigger to re-evaluate: when AffectComparator and CrossDomainAnalyzer start duplicating store-resolution boilerplate. If that happens, extract a shared resolution helper. The codebase's own history shows this reflex works (fusion-api extracted from rag-api).

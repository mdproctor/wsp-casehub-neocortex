# HANDOFF — casehub-neocortex

## Last Session

Landed epic #437 — extend query normalization pipeline beyond location to all platform SPIs. Four sub-issues (#459-#462): SpatialSearchableProvider adapter, CDI wiring for DomainRegistry with auto-discovery, orchestrator refactor to dispatch through DomainRegistry, ExpansionStrategy removal (replaced by DomainSupport.normalizerChain). Code review caught latent NPE in CDI producer (SpatialBlockingStrategy constructed with null). Branch audit passed all 4 dimensions. Merged to main as a21adb86.

Two acceptance criteria on #461 intentionally deferred: `promote()` still delegates to EntityPromoter directly (needs per-domain PromotionStrategy registry), `refreshStale()` retains `List<LocationPlatform>` (needs RefreshStrategy SPI).

## Immediate Next Step

No active branch. Options:
- Start cognitive workbench work (#471 epic, #463-470 child issues)
- Return to #343 (graph-as-retrieval-modality)
- Address #444 (wire CARMA + gut feeling into production runtime)

## References

- Design spec: `specs/issue-437-extend-query-normalization/2026-10-06-extend-query-normalization-design.md`
- Decisions: `specs/issue-437-extend-query-normalization/decisions.md`
- Diary: `blog/2026-10-06-mdp01-breaking-the-location-monopoly.md`

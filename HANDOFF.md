# HANDOFF — casehub-neocortex

## Last Session (2026-11-02)

Completed 5 issues on branch `issue-758-pipeline-wiring-and-corpus`. Major work: #732 folded EntityKnowledge/SocialComparison/DomainActivation prompt sections into consolidation-time drive descriptions (P22), eliminating register-degrading analytical sections. #733 expanded this with relationship/reflection memories, MindMap edges, and per-entity Theory of Mind via new `MentalModelLookup` SPI in cognition-api. Also advanced past #758 (tests, pre-existing), #759 (NarrativePipeline, pre-existing), #755 (agency branch stamps, pre-existing).

Key design decision: dependency analysis proved cognition-api → mindmap-intelligence has no cycle (cognition-api ≠ cognition). This unblocked full ToM integration without architectural compromise.

## Immediate Next Step

#753 — Manor CharacterCognition pipeline wiring. Cross-repo in casehub-mosaic. Cognitive profiles per Manor character + modulated memory retrieval routing. Start fresh session in this slot.

## References

- `specs/issue-758-pipeline-wiring-and-corpus/2026-11-02-drive-first-folding-design.md` — #732 spec
- `specs/issue-758-pipeline-wiring-and-corpus/2026-11-02-entity-enriched-drive-descriptions-design.md` — #733 spec
- `specs/issue-758-pipeline-wiring-and-corpus/decisions.md` — D1-D5 decisions
- `plans/2026-11-02-drive-first-folding.md` — #732 plan
- `plans/2026-11-02-entity-enriched-drive-descriptions.md` — #733 plan

# HANDOFF — casehub-neocortex

## Last Session

Closed epic #757 (cognitive pipeline wiring — all 11 children done). Implemented #752 entity reference pipeline with standoff annotations (7 commits), then discovered standoff was overengineered for name resolution. Design evolved through the session: standoff → bracket syntax multi-word problem → inline entity tokenisation with typed variants. Filed #799 as the replacement epic — structured entity records, surface form lookup table, `{{entity_id:variant:surface_form}}` token format. The standoff annotation modules are candidates for removal once #799 lands.

## Immediate Next Step

`work start 799` — brainstorm and implement inline entity tokenisation. The epic has 12 children, design is documented in #799 body and comments. Blog entry "Names Are Not Identity" captures the full reasoning.

## Cross-Module

#799 touches eidos (entity records from character descriptors) and examples (wacky-manor biography tokenisation). Both repos in slot 211.

## References

- `blog/2026-11-03-mdp03-names-are-not-identity.md` — design journey from standoff to tokenisation
- `specs/issue-757-cognitive-pipeline-wiring/2026-11-03-entity-reference-pipeline-design.md` — original standoff spec (superseded by #799)
- `plans/2026-11-03-entity-reference-pipeline.md` — original standoff implementation plan (superseded)

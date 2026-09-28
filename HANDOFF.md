# HANDOFF — casehub-neocortex

## Last Session

Closed blocks#306 (attention override policy) as superseded by blocks#303 — the SPI approach was wrong, configuration via `CognitiveDefaults` is the right abstraction when CognitionCore migrates. Ran work-end on `issue-306-attention-override-policy` branch. Rebased all 6 project repos in slot 203 against canonical main and pushed 2 neocortex commits that were ahead. Stamped and closed `wsp-casehub-blocks` branch `issue-307-cognition-snapshot-attention` (planning branch, all commits merged to main).

## Immediate Next Step

Pick up blocks#299 (SocialAvatarCognition CDI wiring, S/Low) or blocks#300 (GoalRevision decay-signal, XS/Low) — the two remaining prerequisites before the XL migration (blocks#303).

## Cross-Module

- blocks#303 (XL/High) — migrate cognitive state to neocortex. Blocked by blocks#299 + blocks#300.
- blocks#302 (mood congruence) — still open, batch 4 of the cognitive emotion epic.
- blocks#308 (L/High) — context-budget prompt rendering, still open.

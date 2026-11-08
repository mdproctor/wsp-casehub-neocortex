## D1: Overall approach — personality-modulated activation functions

**Choice:** Replace uniform logistic activation with per-parameter activation functions whose shape changes based on personality. Yerkes-Dodson peak position, Easterbrook narrowing rate, and fatigue resistance all derived from personality facets via CDE.

**Alternatives:**
- Situational strength multiplier — simpler math but can't represent Yerkes-Dodson inverted-U; patch on additive model rather than structural fix
- Separate extreme-intensity override layer — clean separation but introduces discontinuity at threshold boundary and doubles maintenance

**Rationale:** The literature (Yerkes-Dodson, Easterbrook, CAPS) describes continuous interaction effects. The inverted-U with personality-shifted peak is the core insight — only this approach can represent it structurally.

**Trade-offs:** Adds 5-8 fields to SearchBudgetConfig. CDE derivation pathway gets more complex. All changes contained in SearchBudgetConfig + TickParticipant + CDE — no API surface change.

**Sources:**
- `cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetTickParticipant.java` — current logistic activation
- `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/SearchBudgetConfig.java` — current config record
- `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java:646` — current CDE derivation
- `docs/specs/issue-765-cognitive-richness/2026-11-05-cognitive-search-budget-design.md` — original design
- Meyer, Dalal & Hermida (2010) — situational strength theory
- Yerkes & Dodson (1908) — inverted-U with personality-shifted peak
- Easterbrook (1959) — cue-utilisation narrowing under arousal
- Mischel & Shoda (1995) — CAPS rigid narrowing at extremes

**Exploration:** quick
**Status:** captured

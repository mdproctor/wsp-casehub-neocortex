## D1: SubThoughtTickParticipant phase placement

**Choice:** FOUNDATION phase (custom participant, runs after mood + memory hygiene)
**Alternatives:**
- DERIVED phase (as issue originally proposed) — modeled on AppraisalTickParticipant, but sub-thought extraction has no dependency on cognitive state computed in earlier phases, so DERIVED causes a one-tick lag for all high-value consumers (mental model, drives)
- Pre-phase hook on CognitionCore — clean but over-engineered for one use case, adds a new concept to the tick lifecycle
- CognitionTickContext field expansion — couples the context record to sub-thought infrastructure, changes API for all participants
**Rationale:** Sub-thought extraction is input parsing (text → typed structure), not cognitive evaluation. It depends only on observation text + entity names, not on mood/drives/mental model. FOUNDATION placement makes sub-thoughts available to ALL downstream phases in the same tick: mental model (subject loop), drives (DERIVED), CAPS, prompt rendering. Uses existing extension mechanism (CognitionTickParticipant + per-agent ConcurrentHashMap + accessor).
**Trade-offs:** Slightly stretches the semantic meaning of "FOUNDATION" (baseline state establishment vs input decomposition). FOUNDATION custom participants run after mood/hygiene, so sub-thoughts can't inform mood baseline — acceptable since mood doesn't consume sub-thoughts.
**Sources:** CognitionCore.java tick lifecycle, AppraisalTickParticipant.java (DERIVED reference pattern), CognitionTickParticipant.java SPI, issue #478 architecture diagram
**Exploration:** deep-analysis
**Status:** captured

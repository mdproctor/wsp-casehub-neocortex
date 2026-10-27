# HANDOFF — casehub-neocortex

## Last Session

Built a 3-step post-assembly verification pipeline for the extraction pipeline (#706, #707, #708, #709). Gap closure detects under-connected nodes per passage, dangling resolution matches name variants and back-fills missing entities. Regenerated Frida corpus: 71 critical dangles → 0, 152→191 nodes, 634→654 edges. Key finding (P102): separate generation from verification — two LLM calls with different cognitive modes beat one that tries to do both.

## Immediate Next Step

User wants to improve the extraction pipeline UI before starting Napoleon. Fresh session topic.

## References

- `extraction/scripts/orphan_closure.py` — Step 7.5: co-location gap closure
- `extraction/scripts/dangling_resolution.py` — Step 7.6: dangling edge resolution
- `docs/research/era3-cognitive-layering-research.md` — Entry 15, P102
- `blog/2026-10-27-mdp01-extract-locally-verify-globally.md` — session blog (published)
- `extraction/output/corpus.json` — regenerated Frida corpus

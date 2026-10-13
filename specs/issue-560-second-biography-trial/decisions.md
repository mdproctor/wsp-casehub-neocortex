## D1: Biography subject

**Choice:** Napoleon Bonaparte
**Alternatives:**
- Florence Nightingale — strong empathy/sorry-for coverage but weaker on gloating and interruption
- Marie Curie — good methodical contrast but lacks competitive rivalry dimensions
- Steve Jobs — modern figure, competitive but less distinct era/culture contrast
**Rationale:** Napoleon maximises cognitive model gap coverage per #498 analysis: competitive rivalry fills gloating + happy-for, military decisiveness fills interruption, moral certainty fills disgust + should_statements, strategic thinking fills fortune_telling. Emotional profile is the inverse of Frida's.
**Trade-offs:** Military campaigns risk producing many place/organisation nodes with shallow cognitive depth — mitigated by focusing biography on psychological richness over campaign logistics.
**Sources:** casehubio/neocortex#498 (gap analysis + dimension mapping)
**Exploration:** quick (pre-decided in #498)
**Status:** captured

## D2: Output directory layout

**Choice:** Parallel output directory (`extraction/output-napoleon/`) alongside existing Frida output
**Alternatives:**
- Per-corpus subdirectory restructure (`corpora/frida-kahlo/`, `corpora/napoleon/`) — cleaner long-term but more disruptive than #560 scope
**Rationale:** Pipeline already takes source and output-dir as CLI args. Per-corpus config (aliases.yaml, edge-corrections.yaml) is auto-discovered from the output directory. Zero structural changes needed.
**Trade-offs:** If a third biography is added, the flat layout starts looking messy — but that's a future concern.
**Sources:** extraction/scripts/run_pipeline.sh, extraction/scripts/assemble_corpus.py
**Exploration:** quick
**Status:** captured

## D3: Pipeline code fixes included

**Choice:** Fix 3 hardcoded Frida defaults within this issue
**Alternatives:**
- Track as separate issue — keeps #560 pure trial run, but blocks generality proof
**Rationale:** The fixes are small (2 default values in generate_overlay.py and assemble_corpus.py, 3 prompt examples in llm_gap_sweep.py and extract_structure.py) and directly required for the generality claim.
**Trade-offs:** None significant — these are 5-line changes.
**Sources:** Fork scan of extraction/scripts/*.py
**Exploration:** quick
**Status:** captured

## D4: Comparison scope

**Choice:** Structural counts + enrichment coverage + cognitive model gap verification against #498
**Alternatives:**
- Structural + coverage only — misses the primary motivation (filling Frida's cognitive gaps)
**Rationale:** The whole point of choosing Napoleon was to fill specific OCC emotion, action tendency, and cognitive distortion gaps. The comparison must verify whether those gaps are actually filled.
**Trade-offs:** Cognitive model coverage comparison requires cross-referencing against #498's dimension table — slightly more work in the comparison report.
**Sources:** casehubio/neocortex#498, extraction/docs/full-run-results.md
**Exploration:** quick
**Status:** captured

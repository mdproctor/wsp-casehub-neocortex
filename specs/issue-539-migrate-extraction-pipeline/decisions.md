## D1: Verification gate scope — diagnose + fix

**Choice:** Single tool (`verify_corpus.py`) with two modes: default diagnoses and produces a report; `--fix` applies safe fixes to corpus.json producing a corrected copy. Iterate until clean.
**Alternatives:**
- Report-only gate — simpler but doesn't help clean up the Frida corpus; manual fixes are tedious for 348 dangling edges
- Separate fix script — more modular but two scripts to maintain for one workflow
- Fix inline during verify — fastest single pass but harder to audit what changed
**Rationale:** The primary purpose is both repeatable QA and driving cleanup of the Frida corpus. A single tool with diagnose/fix modes keeps the workflow tight: run, review report, apply fixes, re-run to verify.
**Trade-offs:** Fix mode must be conservative — only apply fixes that are unambiguous (name resolution with one candidate, field renames from the schema). Ambiguous fixes stay in the report for manual review.
**Sources:** Issue #550, user clarification
**Exploration:** quick
**Status:** captured

## D2: Contract encoding — schema-driven verification

**Choice:** Define a `verify_schema.yaml` that declares the Java-side contract (field mappings per entity type, valid vocabularies, required fields, PAD ranges, reference resolution rules). `verify_corpus.py` loads this schema and validates against it. Fix rules are also schema-driven.
**Alternatives:**
- Hardcoded checks — simpler to write but 10 entry types × ~90 fields makes inline constants hard to maintain
- Java-extracted contract — parses Java source for @JsonProperty annotations; zero manual sync but fragile, adds build dependency
**Rationale:** The contract surface is large enough that a declarative schema pays for itself in readability and maintainability. Adding a new check is a YAML entry, not code. Fix rules (field renames, alias maps) are expressed declaratively.
**Trade-offs:** Another YAML file to maintain. If the Java side changes a field name, someone must update the schema. But hardcoding has the same burden hidden in code.
**Sources:** GoalEntry.java field mappings, GoalVocabulary.java canonical sets, BiographyLoader validation logic
**Exploration:** quick
**Status:** captured

## D3: Finding attribution — fix-level not just origin

**Choice:** Each finding reports where the fix is most reliable, not just where the problem originates. Some issues (field prefix mismatch) have a clean upstream fix. Others (LLM naming inconsistency, PAD range) are best fixed by post-processing — the verifier's `--fix` mode or a permanent assembler step. The recommendation says "fix here" pragmatically.
**Alternatives:**
- Origin-only attribution — traces to pipeline stage but doesn't say where to fix; the developer still has to decide
- Always-upstream bias — assumes LLM prompts can be fixed for everything; unrealistic for stochastic outputs
**Rationale:** LLM inference is inherently noisy. Some categories (short entity names, out-of-range values) can't be reliably fixed at the prompt level. Post-processing is the correct production fix for these. The report should reflect that pragmatism.
**Trade-offs:** Requires judgment about what's reliably fixable upstream vs what needs post-processing. The schema can encode this per-check-category.
**Sources:** User clarification — "it might be that some of the LLM inference is too hard to fix directly and post processing is the correct way"
**Exploration:** quick
**Status:** captured

## D4: Pipeline placement — standalone QA step

**Choice:** `verify_corpus.py` is a standalone pipeline step that runs after `assemble_corpus.py`. It stays as the independent gate. Fixes that prove reliable over multiple runs get promoted into `assemble_corpus.py` as permanent post-processing, but the verifier remains.
**Alternatives:**
- Fold fixes into assembler immediately — fewer pipeline steps but loses the independent verification perspective
- Explicit promotion path with auto-migration — elegant but over-engineered for current needs
**Rationale:** Keeping verification separate from assembly preserves the QA gate's independence. The assembler already has normalisation logic; the verifier catches what slips through and validates the whole contract, not just individual normalisations.
**Trade-offs:** Extra pipeline step. But it's fast (pure data checks, no LLM calls) and provides a clear pass/fail signal.
**Sources:** Issue #550 deliverable requirements
**Exploration:** quick
**Status:** captured

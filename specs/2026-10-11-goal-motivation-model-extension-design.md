# Goal & Motivation Model Extension — Design Specification

**Date:** 2026-10-11
**Tracks:** New epic (child of #526)
**Research:** `specs/2026-10-11-goal-motivation-taxonomy-rnd.md`
**Status:** Draft

---

## 1. Scope

Five work items, all in neocortex:

1. **Pipeline migration** — move extraction pipeline from `blocks-ui/examples/cognitive-workbench/scripts/` to `neocortex/extraction/`
2. **Model extension** — extend `Goallike` trait with Talevich content domain, SDT origin, clarity, evidence basis
3. **Extraction prompt updates** — GOAL_SYSTEM prompt uses new taxonomy, evidence basis, dual-granularity classification
4. **Assembler + dedup** — two-phase goal dedup (mechanical pre-filter + LLM semantic), updated coverage gates
5. **Importer update + re-process** — wire new fields into `GoalHandler`, re-run Frida extraction, re-import

## 2. Pipeline Migration

### 2.1 Target Structure

```
neocortex/
  extraction/                    # NEW — corpus extraction pipeline
    scripts/
      extract_structure.py       # entity/goal/edge/memory extraction
      enrich_cognitive.py        # cognitive checklist enrichment
      enrich_entity.py           # entity-level synthesis
      assemble_corpus.py         # corpus assembly + dedup
      chunk.py                   # passage chunking
      nlp_extract.py             # spaCy NLP baseline
      llm_gap_sweep.py           # LLM gap detection
      generate_overlay.py        # reference overlay
      coverage.py                # coverage gate library
      compare_corpus.py          # baseline comparison
      normalize.py               # entity name normalisation
      pipeline_state.py          # manifest/state tracking
      llm_client.py              # LLM client wrapper
      iterate.sh                 # iteration runner
      run_pipeline.sh            # full pipeline runner
      requirements.txt           # Python dependencies
    docs/
      field-registry.yaml        # field registry (85+ fields)
      cognitive-extraction-methodology.md  # (if exists in blocks-ui)
    sources/                     # biography source texts
      frida-kahlo-biography.md
    output/                      # baseline corpus (gitignored)
    tests/
      test_coverage.py
      test_pipeline_state.py
      test_convergence_extract.py
```

### 2.2 Migration Rules

- Move scripts verbatim — no refactoring during migration
- Update internal path references (SCRIPT_DIR, WORKBENCH, etc.)
- Create new `.venv` with same `requirements.txt`
- Add `extraction/output/` and `extraction/.venv/` to `.gitignore`
- Remove scripts from blocks-ui after migration verified
- blocks-ui workbench retains the *imported* corpus for its demo but no longer owns the pipeline

## 3. Model Extension

### 3.1 Goallike Trait — New Properties

Add to `mindmap-api` `Goallike` trait interface:

```java
// Content domain — Talevich Y-level (required)
Optional<String> goalContentDomain();

// Content subdomain — Talevich W-level (optional, when LLM is confident)
Optional<String> goalContentSubdomain();

// Motivation origin — Self-Determination Theory
Optional<String> goalOrigin();

// Clarity — how well-defined the goal is (0.0 = vague, 1.0 = precise)
Optional<Double> goalClarity();

// Evidence basis — one-line citation of textual support
Optional<String> goalEvidenceBasis();
```

### 3.2 Content Domain Values (Talevich Y-level)

9 values, grouped by superordinate:

**Meaning:**
- `morality-and-virtue`
- `religion-and-spirituality`
- `self-actualisation`

**Communion:**
- `avoidance`
- `social-relating`
- `health`
- `family`

**Agency:**
- `mastery-and-competence`
- `financial-and-occupational`

### 3.3 Content Subdomain Values (Talevich W-level)

25 values — used when the LLM can classify with confidence:

| Domain (Y) | Subdomains (W) |
|------------|---------------|
| morality-and-virtue | social-values, personal-morals, help-others, highly-regarded |
| religion-and-spirituality | religion-and-spirituality |
| self-actualisation | wisdom-and-serenity, self-knowledge-and-happiness, appreciating-beauty, exploration-and-passions, enjoy-life |
| avoidance | avoid-stress-harm-rejection-conflict, avoid-hassles |
| social-relating | relate-and-belong, intimacy, stability, power, leadership |
| health | health |
| family | family |
| mastery-and-competence | achievement, self-efficacy, practical-competence, intellectual-competence |
| financial-and-occupational | finances, occupational-success |

### 3.4 Motivation Origin Values (SDT)

```
intrinsic       — pursued for inherent interest/satisfaction
identified      — personally valued, accepted as own
introjected     — driven by internal pressure, guilt, shame
external        — driven by reward/punishment from others
```

### 3.5 GoalVocabulary Update

Add cross-tier linking edge type to `GoalVocabulary`:

```java
// Existing: enables, blocks, requires, contributes-to, decomposes-into
// New: none needed — "contributes-to" and "decomposes-into" already cover
// cross-tier linking (tactical "contributes-to" thematic)
```

No new edge types needed. The existing vocabulary handles cross-tier relationships.

### 3.6 Affinity Profile (Cognitive Profile YAML)

New section in cognitive profile YAML for synthetic agents:

```yaml
affinities:
  seeded:
    - domain: mastery-and-competence
      subdomain: intellectual-competence
      strength: 0.8
      content: null               # unresolved — environment determines
    - domain: self-actualisation
      subdomain: appreciating-beauty
      strength: 0.4
      content: "minimalist design" # resolved — author-declared taste
  reward-profile:
    feedback-speed: fast          # fast | moderate | slow
    novelty-demand: high          # low | moderate | high
    mastery-satisfaction: high    # low | moderate | high
```

Add to `CognitiveDefaults` record:

```java
record AffinityDefaults(
    List<SeededAffinity> seeded,
    RewardProfile rewardProfile
) {
    record SeededAffinity(String domain, String subdomain, double strength, String content) {}
    record RewardProfile(String feedbackSpeed, String noveltyDemand, String masterySatisfaction) {}
}
```

Wire into `CognitiveDerivationEngine` — derive affinity domain weights from disposition axes when no explicit affinities declared.

### 3.7 Schema Updates

Add fields to extraction `field-registry.yaml` under `node_fields`:

```yaml
- id: N24
  name: goal_content_domain
  ref: "Talevich Y-level"
  stages: [extraction, corpus, importer]
  type_filter: goal
- id: N25
  name: goal_content_subdomain
  ref: "Talevich W-level"
  stages: [extraction, corpus, importer]
  type_filter: goal
- id: N26
  name: goal_origin
  ref: "SDT"
  stages: [extraction, corpus, importer]
  type_filter: goal
- id: N27
  name: goal_clarity
  ref: "Emmons SAS"
  stages: [extraction, corpus, importer]
  type_filter: goal
- id: N28
  name: goal_evidence_basis
  ref: "§6.4"
  stages: [extraction, corpus]
  type_filter: goal
```

## 4. Extraction Prompt Updates

### 4.1 GOAL_SYSTEM Prompt

Update to request new fields with calibrated guidance:

```
For each goal, produce:
- name: concise goal description
- type: "goal"
- goal_tier: thematic | strategic | tactical
- goal_content_domain: classify into ONE of:
    Meaning: morality-and-virtue, religion-and-spirituality, self-actualisation
    Communion: avoidance, social-relating, health, family
    Agency: mastery-and-competence, financial-and-occupational
- goal_content_subdomain: (optional, when confident) one of the 25 W-level types
- goal_origin: classify the motivation source:
    intrinsic — pursued for inherent interest, joy, fascination
    identified — personally valued, deliberately chosen
    introjected — driven by guilt, shame, internal "should"
    external — driven by social expectation, reward, punishment
- goal_clarity: 0.0-1.0 (1.0 = precise actionable target, 0.0 = vague aspiration)
- goal_evidence_basis: one-line citation from the text that supports this goal
    Examples: "She resolved to be financially self-sufficient (§4)"
             "Pattern of choosing art over domestic life across §4-§8"
             null (for speculated goals with no direct textual support)
- goal_horizon: immediate | short | medium | long | aspirational
- goal_status: active | blocked | completed | dormant | abandoned
- goal_urgency: 0.0-1.0
- goal_need_tier: SAFETY | TASKS | SOCIAL | SELF_EXPRESSION | UNDERSTANDING
- goal_priority: 0.0-1.0
- goal_feasibility: 0.0-1.0
- confidence: {"origin": "STATED|INFERRED|SPECULATED", "value": 0.0-1.0}
    STATED = subject explicitly declares this goal
    INFERRED = consistent pattern of actions/choices implies this goal
    SPECULATED = plausible interpretation without direct behavioural evidence
```

### 4.2 Cross-Tier Linking

After goal extraction, the assembler identifies cross-tier relationships:

- For each tactical goal, check if a thematic/strategic goal in the same `goal_content_domain` exists
- If yes, create a `contributes-to` edge from tactical to thematic/strategic
- Use Jaro-Winkler + Jaccard on goal names as a signal, but the content domain match is the primary criterion

## 5. Assembler & Dedup

### 5.1 Two-Phase Goal Dedup

**Phase 1 — Mechanical pre-filter (existing, tuned):**
- Jaro-Winkler ≥ 0.90 AND Jaccard word overlap ≥ 0.50
- Same `goal_tier` required
- Same `goal_content_domain` required (new guard)
- Precision-first: reduces search space ~96%

**Phase 2 — LLM semantic judgment:**
- Batch near-miss candidates (JW ≥ 0.75 OR Jaccard ≥ 0.60) to an LLM
- LLM classifies each pair as: DUPLICATE (merge), RELATED (link), DISTINCT (keep separate)
- DUPLICATE → merge into canonical (keep highest-confidence version)
- RELATED → create `contributes-to` edge between them
- DISTINCT → no action

### 5.2 Coverage Gate Updates

Add new goal fields to `_NODE_CHECKERS`:

```python
'goal_content_domain': lambda e: bool(e.get('goal_content_domain')),
'goal_origin': lambda e: bool(e.get('goal_origin')),
'goal_clarity': lambda e: e.get('goal_clarity') is not None,
'goal_evidence_basis': lambda e: bool(e.get('goal_evidence_basis')),
```

All with `type_filter: goal` so they only apply to goal entities.

## 6. Importer Updates

### 6.1 GoalHandler

Update `GoalHandler` in `memory-seeding/biography/` to wire new fields:

```java
// Existing: name, type, horizon, priority, status, urgency, feasibility, target-date, need-tier
// New:
node.property("goal.content-domain", entry.contentDomain());
node.property("goal.content-subdomain", entry.contentSubdomain());  // nullable
node.property("goal.origin", entry.origin());
node.property("goal.clarity", entry.clarity());
node.property("goal.evidence-basis", entry.evidenceBasis());  // nullable
```

### 6.2 GoalEntry

Add fields to `GoalEntry` record in biography handler:

```java
record GoalEntry(
    String name,
    // ... existing fields ...
    String contentDomain,       // NEW — Talevich Y-level
    String contentSubdomain,    // NEW — Talevich W-level (nullable)
    String origin,              // NEW — SDT origin
    Double clarity,             // NEW — Emmons clarity
    String evidenceBasis        // NEW — textual citation (nullable)
) implements BiographyEntry {}
```

### 6.3 Cross-Tier Edge Creation

After importing all goals, scan for cross-tier relationships:
- Group goals by `contentDomain`
- Within each domain, if both thematic and tactical goals exist, create `contributes-to` edges

## 7. Re-Process and Re-Import

### 7.1 Re-Process Frida

After pipeline migration and prompt updates:

```bash
cd neocortex/extraction
bash scripts/iterate.sh --limit 3 --label "taxonomy-v1"
# Verify new fields populated, coverage gates pass
bash scripts/iterate.sh --limit 0 --label "taxonomy-full"
# Compare against previous full run
```

### 7.2 Verify

Check:
- All 138+ goals have `goal_content_domain` populated
- `goal_content_subdomain` populated on ≥50% of goals
- `goal_origin` populated on all goals
- `goal_clarity` populated on all goals
- `goal_evidence_basis` populated on STATED/INFERRED goals
- Cross-tier `contributes-to` edges created
- Mechanical dedup reduces goal count by 5-15%
- LLM dedup produces DUPLICATE/RELATED/DISTINCT classifications

### 7.3 Re-Import

Run `BiographyImportRunner` with updated corpus. Verify new fields appear in MindMap goal nodes.

## 8. Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Pipeline lives at `neocortex/extraction/` | Clean separation: extraction produces, memory-seeding imports. Alongside evaluation/ and scripts/ |
| D2 | Y-level required, W-level optional | 9 domains reliable for LLM; 25 types available when confident. Start coarse, refine empirically |
| D3 | Cross-tier goals linked via edges | `contributes-to` edges preserve both abstraction levels. Don't lose tactical specificity by merging into thematic |
| D4 | Two-phase dedup: mechanical + LLM | Mechanical reduces search space 96%. LLM handles semantic judgment. Precision-first on mechanical phase |
| D5 | Content domain added as dedup guard | Same-domain requirement prevents merging unrelated goals with similar wording |

## 9. Implementation Order

1. Pipeline migration (no model changes, just move + verify)
2. Model extension (Goallike trait, GoalEntry, field registry)
3. Extraction prompt update (GOAL_SYSTEM with new fields)
4. Assembler + dedup (content domain guard, cross-tier linking)
5. Coverage gate updates (new fields)
6. Subset test (3 passages, verify new fields)
7. Full run + compare
8. Importer update (GoalHandler, GoalEntry)
9. Re-import + verify

## References

- Research: `specs/2026-10-11-goal-motivation-taxonomy-rnd.md`
- Talevich et al. (2017): https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0172279
- Emmons (1986, 1992, 1999): Personal strivings framework + SAS
- `mindmap-api/.../Goallike.java` — current trait interface
- `memory-seeding/.../biography/GoalHandler.java` — current importer
- `memory-seeding/.../biography/GoalEntry.java` — current entry record
- `blocks-ui/examples/cognitive-workbench/scripts/` — current pipeline location

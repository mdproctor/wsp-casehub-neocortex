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

Add to `mindmap-intelligence` `Goallike` trait interface (`io.casehub.neocortex.mindmap.intelligence.Goallike`):

**Rename existing accessor:** `origin()` → `recognitionSource()` — the existing method returns provenance values like `"conversation"`, `"observation"`. Renaming eliminates the collision with the SDT motivation concept and makes the provenance semantics explicit.

**New accessors:**

```java
Optional<String> contentDomain();
Optional<String> contentSubdomain();
Optional<String> motivationOrigin();
Optional<String> clarity();
Optional<String> evidenceBasis();
```

All accessors return `Optional<String>` for consistency with the trait property model — `ThingProxyHandler` maps method names directly to `Thing.property(methodName)`, which always returns `Optional<String>`. Callers parse numeric values as needed (e.g., `clarity().map(Double::parseDouble).orElse(0.0)`).

**Property key convention:** For properties backed by the Goallike trait interface, the method name IS the property key. `contentDomain()` resolves to `thing.property("contentDomain")` via `ThingProxyHandler`. All goal creation paths (GoalHandler, GoalRecognitionPhase, GoalResolutionPhase, DriveGoalBridgeParticipant) must use the exact method name as the property key for any property accessed via the Goallike trait.

**Pre-existing non-trait property keys:** Existing properties such as `"goal-tier"`, `"need-tier"`, `"origin-drive"` use kebab-case and are accessed directly via `node.property(key)`, not through the Goallike trait proxy. These retain their current keys. If any are later promoted to Goallike trait methods, a property key migration to camelCase will be required.

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

25 values — used when the LLM can classify with confidence.

**Granularity choice:** The research doc (§6.1) recommended X-level (14 clusters) for subdomain classification. This spec uses W-level (25 named types) instead because W-level labels are concrete, self-describing motive types (e.g., "self-efficacy", "intimacy") whereas X-level labels are statistical cluster names (e.g., "Ambition & Ability") that are less useful for matching and less intuitive for LLM classification. The 25 W-level types map 1:1 from X-level parents, so no information is lost — only gained.

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

No new edge types needed — `contributes-to` and `decomposes-into` already cover cross-tier linking.

Add content domain and motivation origin vocabulary constants to `GoalVocabulary` (`mindmap-api`):

```java
public static final Set<String> CONTENT_DOMAINS = Set.of(
    "morality-and-virtue", "religion-and-spirituality", "self-actualisation",
    "avoidance", "social-relating", "health", "family",
    "mastery-and-competence", "financial-and-occupational");

public static final Set<String> MOTIVATION_ORIGINS = Set.of(
    "intrinsic", "identified", "introjected", "external");

public static final Set<String> CONTENT_SUBDOMAINS = Set.of(
    "social-values", "personal-morals", "help-others", "highly-regarded",
    "religion-and-spirituality",
    "wisdom-and-serenity", "self-knowledge-and-happiness", "appreciating-beauty",
    "exploration-and-passions", "enjoy-life",
    "avoid-stress-harm-rejection-conflict", "avoid-hassles",
    "relate-and-belong", "intimacy", "stability", "power", "leadership",
    "health", "family",
    "achievement", "self-efficacy", "practical-competence", "intellectual-competence",
    "finances", "occupational-success");
```

GoalHandler validates at import time: reject entries with domain, subdomain, or origin values not in these sets. The Python extraction prompt constrains output, but validation at the import boundary catches prompt drift or manual edits to the corpus JSON.

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

Wire into `CognitiveDerivationEngine` — derive affinity domain weights from disposition axes when no explicit affinities declared. The derivation mapping function (disposition axes → Talevich domain weights) is specified in the affinity profile issue (#543), not here — this spec defines the `AffinityDefaults` record and YAML schema, #543 defines the derivation logic.

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
  name: goal_motivation_origin
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
  stages: [extraction, corpus, importer]
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
- goal_motivation_origin: classify the motivation source:
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
- Same `goal_content_domain` required (new guard). **Null-domain handling:** if either goal in a candidate pair lacks `goal_content_domain`, skip the domain guard for that pair — let the LLM decide. This ensures dedup works during the transition before all goals have been re-extracted with taxonomy fields, and handles goals that fail domain classification.
- Precision-first: reduces search space ~96%

**Phase 2 — LLM semantic judgment:**
- Batch near-miss candidates (JW ≥ 0.75 OR Jaccard ≥ 0.60) to an LLM
- LLM classifies each pair as: DUPLICATE (merge), RELATED (link), DISTINCT (keep separate)
- DUPLICATE → merge into canonical (keep highest-confidence version)
- RELATED → create `contributes-to` edge between them
- DISTINCT → no action

**Batch and failure handling:**
- Batch pairs in groups of ≤20 per LLM call to stay within context limits
- On LLM failure or malformed response for a batch: retry once, then classify all pairs in that batch as DISTINCT (safe default — no false merges)
- **Transitivity:** DUPLICATE classification is transitive. Use union-find: if A≈B and B≈C, then A, B, C form one equivalence class. Merge all into the highest-confidence canonical.
- **Convergence:** After the initial LLM pass, re-check pairs that cross equivalence class boundaries (a pair where one member was merged into a different canonical). Run at most 2 convergence rounds to catch shadowed duplicates.

### 5.2 Coverage Gate Updates

Add new goal fields to `_NODE_CHECKERS`:

```python
'goal_content_domain': lambda e: bool(e.get('goal_content_domain')),
'goal_motivation_origin': lambda e: bool(e.get('goal_motivation_origin')),
'goal_clarity': lambda e: e.get('goal_clarity') is not None,
'goal_evidence_basis': lambda e: bool(e.get('goal_evidence_basis')) or e.get('confidence', {}).get('origin') == 'SPECULATED',
```

All with `type_filter: goal` so they only apply to goal entities.

### 5.3 Goal Taxonomy Vocabulary Validation

Apply the same normalisation pattern as OCC (#544) to prevent hallucinated vocabulary in goal taxonomy fields:

**Content domain (9 canonical values):** Normalisation map for likely LLM variants:

| Non-canonical | Maps to | Rationale |
|--------------|---------|-----------|
| career-development, professional-growth, work-success | financial-and-occupational | Occupational domain |
| achievement-and-competence, skill-building | mastery-and-competence | Competence domain |
| self-improvement, personal-growth, self-development | self-actualisation | Growth domain |
| relationships, social-connection, belonging | social-relating | Social domain |
| safety, security, harm-avoidance | avoidance | Avoidance domain |
| faith, spirituality | religion-and-spirituality | Spiritual domain |
| ethics, values, doing-good | morality-and-virtue | Moral domain |

**Content subdomain (25 canonical values):** Reject non-canonical subdomains — set to null rather than normalise. The subdomain is optional; a wrong value is worse than missing.

**Motivation origin (4 canonical values):** Normalisation map:

| Non-canonical | Maps to |
|--------------|---------|
| self-driven, autonomous, self-motivated | intrinsic |
| personally-valued, self-endorsed | identified |
| guilt-driven, shame-based, obligatory | introjected |
| socially-imposed, reward-driven, compliance | external |

**Implementation:** Add `normalise_goal_vocabulary()` to the assembler, called after extraction and before dedup. Preserves `original_content_domain` / `original_motivation_origin` when normalised (same audit trail pattern as OCC).

## 6. Importer Updates

### 6.1 GoalHandler

Update `GoalHandler` in `memory-seeding/biography/` to wire new fields. Property keys must match the Goallike trait method names exactly (ThingProxyHandler convention):

```java
// GoalHandler currently writes these properties: provenance, template-ref, source-ref, tier, horizon
// The following extraction fields exist in the corpus but are NOT currently imported:
//   status, urgency, priority, feasibility, need-tier
// This spec wires BOTH the missing extraction fields AND the new taxonomy fields.

// Wire previously-missing extraction fields:
// status, urgency, feasibility match existing Goallike trait methods (camelCase keys)
// priority is not a Goallike trait method but uses camelCase naturally
// need-tier is not a Goallike trait method; retains existing kebab-case key
if (entry.status() != null) props.put("status", entry.status());
if (entry.urgency() != null) props.put("urgency", entry.urgency());
if (entry.priority() != null) props.put("priority", entry.priority());
if (entry.feasibility() != null) props.put("feasibility", entry.feasibility());
if (entry.needTier() != null) props.put("need-tier", entry.needTier());

// New taxonomy fields — property keys = Goallike method names (camelCase):
props.put("contentDomain", entry.contentDomain());
if (entry.contentSubdomain() != null) props.put("contentSubdomain", entry.contentSubdomain());
props.put("motivationOrigin", entry.motivationOrigin());
if (entry.clarity() != null) props.put("clarity", String.valueOf(entry.clarity()));
if (entry.evidenceBasis() != null) props.put("evidenceBasis", entry.evidenceBasis());
```

Also rename the existing `origin` property key to `recognitionSource` to match the renamed Goallike accessor.

### 6.2 GoalEntry

The existing `GoalEntry` record has: `id`, `sourceRef`, `confidenceOrigin`, `name`, `tier`, `horizon`, `dependencies`, `pad`, `subGoals`. Extend with both previously-missing extraction fields and new taxonomy fields:

```java
@JsonIgnoreProperties(ignoreUnknown = true)
public record GoalEntry(
    String id,
    @JsonProperty("source_ref") String sourceRef,
    @JsonProperty("confidence_origin") String confidenceOrigin,
    String name,
    String tier,
    String horizon,
    String status,                                              // WIRED — in extraction, not previously imported
    String urgency,                                             // WIRED
    String priority,                                            // WIRED
    String feasibility,                                         // WIRED
    @JsonProperty("need_tier") String needTier,                 // WIRED
    @JsonProperty("content_domain") String contentDomain,       // NEW — Talevich Y-level
    @JsonProperty("content_subdomain") String contentSubdomain, // NEW — Talevich W-level (nullable)
    @JsonProperty("motivation_origin") String motivationOrigin, // NEW — SDT origin
    Double clarity,                                             // NEW — Emmons clarity (nullable, numeric in JSON)
    @JsonProperty("evidence_basis") String evidenceBasis,       // NEW — textual citation (nullable)
    List<Dependency> dependencies,
    PadValues pad,
    @JsonProperty("sub_goals") List<SubGoal> subGoals
) {}
```

`clarity` is `Double` in GoalEntry (matching the JSON numeric type) — GoalHandler converts to `String` via `String.valueOf()` for property storage, consistent with the `Optional<String>` trait contract.

### 6.3 Cross-Tier Edge Creation

**Ownership model:** The assembler (§4.2) is the sole authoritative source for cross-tier `contributes-to` edges. GoalHandler imports them via the existing dependency mechanism in the corpus JSON — no additional scanning in the importer.

This eliminates duplicate edge creation. If the assembler misses edges, fix the assembler's detection logic, don't add a second pass in GoalHandler.

**Runtime merge guard:** `GoalResolutionPhase.merge()` creates `contributes-to` edges only when merging sub-goals (with the existing `alreadyLinked` check). This is the only runtime source and is scoped to merge-created relationships.

### 6.4 Goal Decomposition — Taxonomy Propagation

When `GoalResolutionPhase.expand()` creates sub-goals via `CognitiveGoalDecomposer.decompose()`, the following taxonomy fields must be propagated from parent to sub-goal:

- `contentDomain` — inherited (decomposition doesn't change the domain)
- `motivationOrigin` — inherited (sub-goals share the parent's motivation source)

The following fields are NOT inherited:
- `clarity` — sub-goals may have different precision than the parent
- `evidenceBasis` — decomposed sub-goals are LLM-generated, not extracted from text

Implementation: after creating sub-goal nodes, set `contentDomain` and `motivationOrigin` from the parent node's properties. This ensures the §6.5 merge guard can correctly evaluate merge candidates for decomposed sub-goals — without inherited taxonomy, sub-goals would always fall through to the null-domain fallback path.

### 6.5 GoalResolutionPhase.merge() — Content Domain Guard

The current `merge()` uses Jaro-Winkler ≥ 0.85 with no content domain guard. After this spec's changes, `merge()` must:

1. Require matching `contentDomain` before considering a merge (same guard as extraction dedup §5.1)
2. Raise the similarity threshold to ≥ 0.90 (aligned with extraction's conservative pre-filter)
3. Preserve taxonomy fields from the surviving node (the merge target)

This prevents the runtime from re-merging goals that extraction's LLM classified as DISTINCT due to different content domains.

**Null contentDomain handling:** If either node in a candidate pair lacks `contentDomain`, skip the domain guard for that pair — apply JW ≥ 0.90 only. This covers three categories of domain-less goals:

- **Pre-existing goals** — created before this spec is implemented, not yet re-imported
- **Runtime-recognized goals** — `CognitiveGoalRecognizer` returns `RecognizedGoal(description, origin, suggestedHorizon, confidence)` with no content domain field. Goals from the recognition path will always lack `contentDomain` until the recognizer SPI is extended.
- **Decomposed sub-goals** — if §6.4 propagation fails or the parent itself lacks a domain

The "skip guard on null" strategy is consistent with §5.1's extraction-time dedup null handling. It avoids both false protection (null==null matching all domain-less goals into one group) and over-constraint (null≠non-null preventing runtime-recognized duplicates of imported goals from merging).

**Follow-up:** Taxonomy extension for runtime goal creation paths — tracked as a follow-up issue under #538 (the taxonomy epic). See §6.6 for the comprehensive scope.

### 6.6 Goal Creation Path Alignment

The codebase has four distinct code paths that create goal nodes. This section enumerates all four and specifies what changes each requires — both in this spec and in follow-up work.

| # | Path | Class | Module | Property key `"origin"` → `"recognitionSource"` | Taxonomy fields |
|---|------|-------|--------|--------------------------------------------------|----------------|
| 1 | Biography import | `GoalHandler` | memory-seeding | **This spec** (§6.1) | **This spec** (§6.1) |
| 2 | Runtime recognition | `GoalRecognitionPhase` | mindmap-intelligence | **This spec** | Follow-up |
| 3 | Runtime decomposition | `GoalResolutionPhase.expand()` | mindmap-intelligence | N/A (doesn't write origin) | **This spec** (§6.4 propagation) |
| 4 | Drive-based proposal | `DriveGoalBridgeParticipant` | cognition | **This spec** | Follow-up |

#### This-spec changes (mandatory — must ship with the Goallike interface rename)

The `origin()` → `recognitionSource()` rename on the Goallike trait changes the `ThingProxyHandler` lookup key. All paths that write `"origin"` must be updated atomically:

- **GoalRecognitionPhase** (line 126): `props.put("origin", goal.origin())` → `props.put("recognitionSource", goal.origin())`
- **DriveGoalBridgeParticipant** (line 117): `props.put("origin", "drive-proposal")` → `props.put("recognitionSource", "drive-proposal")`

Without this, `Goallike.recognitionSource()` returns `Optional.empty()` for all runtime-created goals — the trait proxy looks up `thing.property("recognitionSource")` but finds only `"origin"`.

#### Follow-up scope (tracked under #538)

The follow-up issue must cover:

1. **Taxonomy fields on runtime paths:** Extend `RecognizedGoal` with optional `contentDomain` and `motivationOrigin` fields. Extend `DriveGoalProposal` similarly. Wire these into `GoalRecognitionPhase` and `DriveGoalBridgeParticipant` when creating goal nodes.

2. **Vocabulary validation on runtime paths:** When runtime paths start writing taxonomy fields, apply `GoalVocabulary` validation — either via a shared static validator method on `GoalVocabulary` (preferred) or inline checks. The same defense-in-depth principle that justifies import-time validation applies to all goal creation paths.

3. **Content domain guard on recognition-time dedup:** `GoalRecognitionPhase.findMatch()` and `DriveGoalBridgeParticipant.findMatch()` currently use JW ≥ 0.85 with no content domain guard. Once taxonomy fields are populated on runtime goals, add a content domain guard matching §6.5's pattern (skip guard when either node lacks `contentDomain`). The lower threshold (0.85 vs §6.5's 0.90) is intentional — creation guards should be more aggressive than merge guards, since the cost of creating a duplicate (ongoing merge complexity) exceeds the cost of suppressing a redundant recognition (the recognizer will re-propose next tick).

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

### 7.2 Integration Checkpoint — Migration

Before Phase 3 prompt updates begin, verify the Phase 1 migration is stable:
- All script path references (SCRIPT_DIR, WORKBENCH, etc.) resolve to `neocortex/extraction/`
- `run_pipeline.sh` completes without path errors using the current (pre-taxonomy) prompts
- Coverage gates pass with existing field set
- Output matches the pre-migration baseline (same goal count, same coverage percentages)

### 7.3 Verify — Post-Taxonomy

Check:
- All 138+ goals have `goal_content_domain` populated
- `goal_content_subdomain` populated on ≥50% of goals
- `goal_motivation_origin` populated on all goals
- `goal_clarity` populated on all goals
- `goal_evidence_basis` populated on STATED/INFERRED goals
- Vocabulary normalisation ran — check `original_content_domain` fields for normalisation audit trail
- Cross-tier `contributes-to` edges created
- Mechanical dedup reduces goal count by 5-15%
- LLM dedup produces DUPLICATE/RELATED/DISTINCT classifications

### 7.4 Re-Import

Run `BiographyImportRunner` with updated corpus. Verify new fields appear in MindMap goal nodes.

## 8. Related Extraction Quality Items

The following corpus audit findings are tracked as independent issues with no structural dependency on the goal taxonomy extension. They share a common origin (Frida Kahlo corpus analysis) and will be implemented in Phase 3, but their design decisions are independent of §§2-6:

- **#544** — OCC emotion normalisation (assembler fix landed, prompt enforcement pending)
- **#545** — Lifecycle event vocabulary normalisation
- **#546** — Entity name normalisation/dedup
- **#547** — Edge extraction scaling investigation
- **#548** — Entity PAD on non-person types

See individual issues for design details.

## 9. Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Pipeline lives at `neocortex/extraction/` | Clean separation: extraction produces, memory-seeding imports. Alongside evaluation/ and scripts/ |
| D2 | Y-level required, W-level optional | 9 domains reliable for LLM; 25 types available when confident. Start coarse, refine empirically |
| D3 | Cross-tier goals linked via edges | `contributes-to` edges preserve both abstraction levels. Don't lose tactical specificity by merging into thematic |
| D4 | Two-phase dedup: mechanical + LLM | Mechanical reduces search space 96%. LLM handles semantic judgment. Precision-first on mechanical phase |
| D5 | Content domain added as dedup guard | Same-domain requirement prevents merging unrelated goals with similar wording |
| D6 | OCC normalisation in assembler (done) | Maps 46 non-canonical types to canonical 22. Preserves original_type for audit |
| D7 | Formative domain fix (done) | formative-experience is an event_type, not a domain. Domain is always experience |
| D8 | Entity PAD on all types | Extract PAD where subject has felt affect. Derive from memory PAD as fallback |
| D9 | W-level (25) for subdomain, not X-level (14) | W-level labels are concrete motive types; X-level labels are statistical cluster names. Better for LLM classification and domain matching |
| D10 | Assembler owns cross-tier linking | Single canonical algorithm; importer imports edges, doesn't re-derive them |
| D11 | GoalVocabulary enforces domain/origin values | Import-time validation via string constant sets catches prompt drift and corpus edits |
| D12 | NeedTier and ContentDomain coexist | NeedTier is a *functional* classification (which psychological need does this goal serve?) used by DriveAdaptationPhase, NeedsPyramidPromptSection, BackstorySeeder for need satisfaction dynamics. ContentDomain is a *content* classification (what is this goal about?) from Talevich. They are orthogonal: "learn cooking" has contentDomain=mastery-and-competence but needTier could be TASKS, SOCIAL, or SELF_EXPRESSION depending on the subject's motivation. NeedTier has 58 references across the cognition system — deprecation would be a cognition redesign, not a taxonomy task |
| D13 | Property key convention scoped to Goallike-trait-backed properties | `ThingProxyHandler` maps method names to property keys — camelCase convention is mandatory for trait-backed properties. Pre-existing kebab-case keys (`"goal-tier"`, `"need-tier"`) are not accessed via the trait and retain current form |
| D14 | `origin` → `recognitionSource` rename must be atomic across all four goal creation paths | `ThingProxyHandler` lookup breaks if any path writes the old key. GoalHandler, GoalRecognitionPhase, and DriveGoalBridgeParticipant all updated in this spec |
| D15 | Recognition dedup threshold (0.85) intentionally lower than merge threshold (0.90) | Creation guard should be more aggressive — cost of duplicate creation exceeds cost of suppressing redundant recognition. Content domain guard deferred until taxonomy fields are populated on runtime goals |
| D16 | `GoalVocabulary` includes `CONTENT_SUBDOMAINS` | Defense-in-depth: subdomains validated at import boundary alongside domains and origins. Consistent with §5.3's Python-side subdomain rejection |

## 10. Issue Map

| Issue | Title | Phase |
|-------|-------|-------|
| #538 | Epic: goal & motivation taxonomy | — |
| #539 | Migrate extraction pipeline | Phase 1 |
| #540 | Extend Goallike trait | Phase 2 |
| #541 | Update GOAL_SYSTEM prompt | Phase 3 |
| #542 | Two-phase goal dedup | Phase 4 |
| #543 | Affinity profile YAML | Phase 5 |
| #544 | OCC vocabulary enforcement | Phase 3 (prompt done, normalisation done) |
| #545 | Lifecycle vocabulary enforcement | Phase 3 |
| #546 | Entity name normalisation | Phase 3 |
| #547 | Edge extraction scaling | Phase 3 |
| #548 | PAD on non-person entities | Phase 3 |
| #549 | Formative domain mapping | Done |

## 11. Implementation Order

**Phase 1 — Migration**
1. Move scripts to `neocortex/extraction/`, update paths, verify (#539)

**Phase 2 — Model**
2. Extend Goallike trait with content domain, origin, clarity, evidence basis (#540)
3. Update GoalEntry + GoalHandler with new fields
4. Update field registry with new goal fields

**Phase 3 — Extraction quality**
5. Update GOAL_SYSTEM prompt with taxonomy + evidence basis (#541)
6. Strengthen OCC prompt enforcement (#544)
7. Lifecycle vocabulary normalisation + prompt enforcement (#545)
8. Entity name normalisation/dedup in assembler (#546)
9. Investigate + fix edge extraction scaling (#547)
10. Extend entity PAD to non-person types (#548)

**Phase 4 — Dedup + linking**
11. Content domain dedup guard in mechanical pre-filter (#542)
12. Cross-tier `contributes-to` edge linking
13. LLM semantic dedup for near-miss candidates

**Phase 5 — Affinity + verification**
14. Affinity profile YAML schema + CognitiveDefaults extension (#543)
15. Coverage gate updates for new fields
16. Subset test (3 passages)
17. Full run + compare against current baseline
18. Re-import + verify

## References

- Research: `specs/2026-10-11-goal-motivation-taxonomy-rnd.md`
- Talevich et al. (2017): https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0172279
- Emmons (1986, 1992, 1999): Personal strivings framework + SAS
- `mindmap-intelligence/.../Goallike.java` — current trait interface
- `memory-seeding/.../biography/GoalHandler.java` — current importer
- `memory-seeding/.../biography/GoalEntry.java` — current entry record
- `blocks-ui/examples/cognitive-workbench/scripts/` — current pipeline location

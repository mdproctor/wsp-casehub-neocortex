# Production Biography Extraction Pipeline — Stages 9-11

**Issue:** casehubio/neocortex#551
**Date:** 2026-10-12
**Status:** Design

## Overview

Extend the biography extraction pipeline with three new stages that bridge the Python extraction pipeline to the Java cognitive engine:

1. **Stage 9: Converter** — Python script (`convert_corpus.py`) transforms `corpus.json` into typed YAML files consumable by `BiographyLoader`
2. **Stage 10: Import** — Wire converter output into `BiographyImportRunner`, verify layer ordering and error isolation
3. **Stage 11: Validation** — Post-import store validation confirming round-trip integrity

The pipeline is the product; Frida Kahlo is the proving ground.

## Scope

### In scope
- `convert_corpus.py` script (Python, in `extraction/scripts/`)
- Java entry type extensions (GoalEntry, LifeEventEntry)
- New Java entry types and handlers (OrganisationEntry, EntityEnrichmentEntry, DispositionProfileEntry)
- Universal `associations` field on all MindMap-writing entry types
- `BiographyImportRunner` integration test
- Post-import validation script or test
- Per-corpus config via `verify_schema.yaml`

### Out of scope
- Modifying the extraction/enrichment pipeline (stages 1-8)
- Regression baseline infrastructure (separate issue)
- Second biography trial run (separate issue)
- formative-experience catalogue mapping (BackstorySeeder entries are handcrafted, not extracted)

## Stage 9: Corpus-to-YAML Converter

### Architecture

`convert_corpus.py` reads `corpus.json` and `verify_schema.yaml`, produces a directory of typed YAML files ready for `BiographyLoader.loadAll()`.

```
corpus.json + verify_schema.yaml
        │
        ▼
  convert_corpus.py
        │
        ├── places.yaml
        ├── organisations.yaml
        ├── activities.yaml
        ├── projects.yaml
        ├── relationships.yaml
        ├── goals.yaml
        ├── beliefs.yaml
        ├── life-events.yaml
        ├── current-state.yaml
        ├── entity-enrichments.yaml
        ├── disposition-profile.yaml
        └── conversion-report.json
```

### Node-to-Entry Mapping

| Corpus `subgraph_type` | YAML type | Entry record |
|------------------------|-----------|--------------|
| `person` | `relationship` | `RelationshipEntry` |
| `place` | `place` | `PlaceEntry` |
| `activity` | `activity` | `ActivityEntry` |
| `project` | `project` | `ProjectEntry` (new from `concept` where applicable) |
| `organisation` | `organisation` | `OrganisationEntry` (new) |
| `goal` | `goal` | `GoalEntry` (extended) |
| `concept` | `belief` | `BeliefEntry` |

### Memory-to-Entry Mapping

| Corpus `domain` | Corpus `event_type` | YAML type | Entry record |
|-----------------|---------------------|-----------|--------------|
| `experience` | `observation`, `action`, `outcome` | `life-event` | `LifeEventEntry` (extended) |
| `relationship` | any | `life-event` | `LifeEventEntry` (domain attribute distinguishes) |
| `reflection` | any | `life-event` | `LifeEventEntry` (domain attribute distinguishes) |
| `mood` | `mood-snapshot` | `current-state` | `CurrentStateEntry` |

### Edge Mapping Strategy

The converter assigns each edge to the source entity's entry using a priority cascade:

1. **Type-specific fields first** — edges that match a built-in field on the entry type:
   - GoalEntry: `contributes-to`, `enables`, `blocks`, `requires`, `decomposes-into` → `dependencies`
   - ActivityEntry: `at` → `place_ref`, `participated` → `participants`
   - PlaceEntry: `located-in` → `associations`
   - RelationshipEntry: relationship-type edges → `properties`
   
2. **Universal associations fallback** — remaining edges go to the source entity's `associations` list as `{entity_ref, edge_type, confidence}`.

3. **Unattributable edges** — edges where neither source nor target maps to a node entry (rare) are logged in the conversion report.

### ID Generation

Entry IDs are derived deterministically from corpus data:
- Node entries: `{subgraph_type}-{slugified_name}` (e.g., `goal-develop-physical-resilience`)
- Memory entries: `{domain}-{index:04d}` (e.g., `experience-0042`)
- Slugification: lowercase, non-alphanumeric → hyphen, max 60 chars, deduplicate with `-N` suffix

### Alias Resolution

The converter applies `verify_schema.yaml` entity aliases during edge mapping. Edge endpoints referencing an alias are resolved to the canonical name before entry lookup.

### Conversion Report

`conversion-report.json` records:
- Counts: nodes mapped, edges mapped (by method: specific/associations/unattributable), memories mapped
- Unmapped items with reasons
- Alias resolutions applied
- Warnings (e.g., concept nodes with no description)

## Stage 10: Java Entry Extensions

### D1: GoalEntry Extensions

Add 10 taxonomy fields to `GoalEntry`:

```java
public record GoalEntry(
    String id,
    @JsonProperty("source_ref") String sourceRef,
    @JsonProperty("confidence_origin") String confidenceOrigin,
    String name,
    String tier,
    String horizon,
    String status,                                    // NEW
    Double urgency,                                    // NEW
    @JsonProperty("need_tier") String needTier,        // NEW
    Double priority,                                   // NEW
    Double feasibility,                                // NEW
    @JsonProperty("content_domain") String contentDomain,      // NEW
    @JsonProperty("content_subdomain") String contentSubdomain, // NEW
    @JsonProperty("motivation_origin") String motivationOrigin, // NEW
    Double clarity,                                    // NEW
    @JsonProperty("evidence_basis") String evidenceBasis,       // NEW
    List<Dependency> dependencies,
    PadValues pad,
    @JsonProperty("sub_goals") List<SubGoal> subGoals
) {}
```

`GoalHandler` stores the new fields as node properties, matching the existing `tier`/`horizon` pattern.

### D6: LifeEventEntry Enrichment Extensions

Add enrichment fields to `LifeEventEntry`:

```java
public record LifeEventEntry(
    String id,
    @JsonProperty("source_ref") String sourceRef,
    @JsonProperty("confidence_origin") String confidenceOrigin,
    String timestamp,
    String description,
    String domain,                                                  // NEW — experience/relationship/reflection
    @JsonProperty("event_type") String eventType,                   // NEW — observation/action/outcome
    String subject,                                                  // NEW — entity subject name
    String period,                                                   // NEW — temporal period
    @JsonProperty("related_entities") List<String> relatedEntities,  // NEW
    PadValues pad,
    @JsonProperty("occ_emotions") List<OccEmotion> occEmotions,      // NEW
    @JsonProperty("sec_appraisal") SecAppraisal secAppraisal,        // NEW
    @JsonProperty("action_tendencies") List<ActionTendency> actionTendencies, // NEW
    @JsonProperty("cognitive_distortions") List<CognitiveDistortion> cognitiveDistortions, // NEW
    @JsonProperty("drive_impact") DriveImpact driveImpact,           // NEW
    @JsonProperty("caps_inputs") Map<String, Double> capsInputs,     // NEW
    @JsonProperty("goal_impacts") List<GoalImpact> goalImpacts,      // NEW
    Habituation habituation,                                          // NEW
    @JsonProperty("gut_feeling") GutFeeling gutFeeling,              // NEW
    @JsonProperty("sub_thoughts") List<SubThought> subThoughts,
    @JsonProperty("entity_refs") List<String> entityRefs
) {}
```

Inner records for the new fields:

```java
record OccEmotion(String type, Double intensity, String source) {}
record SecAppraisal(Double relevance, Double novelty, Double urgency,
    Double conduciveness, Double controllability, Double adjustability,
    @JsonProperty("internal_standards") Double internalStandards,
    @JsonProperty("external_standards") Double externalStandards) {}
record ActionTendency(String type, Double intensity) {}
record CognitiveDistortion(String type, Double strength) {}
record DriveImpact(Double curiosity, Double competence,
    Double affiliation, Double autonomy) {}
record GoalImpact(String goal, String relationship,
    @JsonProperty("urgency_delta") Double urgencyDelta) {}
record Habituation(String novelty,
    @JsonProperty("habituation_score") Double habituationScore,
    String echoes) {}
record GutFeeling(String valence, Double intensity, String resonance) {}
```

`LifeEventHandler` stores each enrichment field as indexed/flat string attributes following the `SubThoughtAttributeKeys` pattern. Attribute key conventions:

| Field | Attribute keys |
|-------|---------------|
| `occ_emotions` | `occ-emotion-count`, `occ-emotion-{i}-type`, `occ-emotion-{i}-intensity`, `occ-emotion-{i}-source` |
| `sec_appraisal` | `sec-relevance`, `sec-novelty`, `sec-urgency`, `sec-conduciveness`, `sec-controllability`, `sec-adjustability`, `sec-internal-standards`, `sec-external-standards` |
| `action_tendencies` | `action-tendency-count`, `action-tendency-{i}-type`, `action-tendency-{i}-intensity` |
| `cognitive_distortions` | `cognitive-distortion-count`, `cognitive-distortion-{i}-type`, `cognitive-distortion-{i}-strength` |
| `drive_impact` | `drive-curiosity`, `drive-competence`, `drive-affiliation`, `drive-autonomy` |
| `caps_inputs` | `caps-{input-name}` (dynamic keys from map) |
| `goal_impacts` | `goal-impact-count`, `goal-impact-{i}-goal`, `goal-impact-{i}-relationship`, `goal-impact-{i}-urgency-delta` |
| `habituation` | `habituation-novelty`, `habituation-score`, `habituation-echoes` |
| `gut_feeling` | `gut-valence`, `gut-intensity`, `gut-resonance` |
| `domain` | `domain` (overwrites default "experience") |
| `event_type` | `event-type` (overwrites default "observation") |
| `subject` | `subject` |
| `period` | `period` |
| `related_entities` | `related-entity-count`, `related-entity-{i}` |

A new `EnrichmentAttributeKeys` class (or extension to existing attribute key classes) provides constants for these keys.

### D3: Universal Associations

Add an optional `associations` field to entry types that write to MindMapStore but don't already have one:

| Entry type | Current edge fields | Add `associations`? |
|------------|--------------------|--------------------|
| `PlaceEntry` | Already has `associations` | No change |
| `GoalEntry` | Has `dependencies` | Yes |
| `RelationshipEntry` | Has `properties`, `dynamics` | Yes |
| `BeliefEntry` | Has `entity_refs` | Yes |
| `ActivityEntry` | Has `place_ref`, `participants` | Yes |
| `ProjectEntry` | Has `activity_refs` | Yes |
| `OrganisationEntry` | New | Yes (built-in) |
| `CulturalContextEntry` | Has `norms` | Yes |

```java
record Association(
    @JsonProperty("entity_ref") String entityRef,
    @JsonProperty("edge_type") String edgeType,
    Double confidence
) {}
```

Each handler processes `associations` by resolving the target node across all subgraphs and creating edges, following the `GoalHandler.resolveAcrossSubgraphs()` pattern.

### D5: OrganisationEntry + OrganisationHandler

```java
// OrganisationEntry.java
public record OrganisationEntry(
    String id,
    @JsonProperty("source_ref") String sourceRef,
    @JsonProperty("confidence_origin") String confidenceOrigin,
    String name,
    List<String> traits,
    Map<String, String> properties,
    PadValues pad,
    List<Association> associations,
    @JsonProperty("valid_from") String validFrom,
    @JsonProperty("valid_until") String validUntil
) {}
```

`OrganisationHandler` at layer 4 creates nodes in the `SubgraphTypes.ORGANISATION` subgraph, stores properties, applies PAD and temporal validity, processes associations.

### D2: EntityEnrichmentEntry + DispositionProfileEntry

**EntityEnrichmentEntry** (layer 7):

```yaml
type: entity-enrichment
entries:
  - id: frida-kahlo-enrichment
    entity_ref: "Frida Kahlo"
    drive_baselines:
      curiosity: { baseline: 0.85, justification: "..." }
      competence: { baseline: 0.88, justification: "..." }
      affiliation: { baseline: 0.58, justification: "..." }
      autonomy: { baseline: 0.92, justification: "..." }
    caps_patterns:
      - pattern: "physical_immobility → isolation_threat + loss_of_agency → CREATIVE_SUBLIMATION"
        frequency: 0.8
    behavioural_attractors:
      - name: "defiance-through-artistic-authenticity"
        description: "..."
    relationship_stages:
      - other_agent: "Diego Rivera"
        transitions:
          - from: "admiration/mentorship"
            to: "passionate/romantic"
            period: "1928-1929"
```

`EntityEnrichmentHandler` resolves the entity node in MindMap by name across all subgraphs:
- **Drive baselines** → node properties on the entity's MindMap node (e.g., `drive-baseline-curiosity=0.85`, `drive-baseline-curiosity-justification=...`)
- **CAPS patterns** → indexed node properties on the entity node (e.g., `caps-pattern-count=2`, `caps-pattern-0-pattern=...`, `caps-pattern-0-frequency=0.8`)
- **Behavioural attractors** → indexed node properties on the entity node (e.g., `behavioural-attractor-count=1`, `behavioural-attractor-0-name=defiance-through-artistic-authenticity`)
- **Relationship stages** → CaseMemoryStore memories in the `relationship` domain, one per transition, linking source agent to `other_agent`

**DispositionProfileEntry** (layer 7):

```yaml
type: disposition-profile
entries:
  - id: frida-kahlo-disposition
    entity_ref: "Frida Kahlo"
    social_orient: competitive
    rule_following: defiant
    risk_appetite: bold
    autonomy: autonomous
    conflict_mode: diplomatic
```

Axes are flat categorical strings matching `DispositionAxes` and `CognitiveDerivationEngine` lookup maps. The converter applies score-to-category conversion from `corpus.json` numeric scores using `DISPOSITION_CATEGORIES`:

| Axis | [0.0, 0.4) | [0.4, 0.7) | [0.7, 1.0] |
|------|-----------|-----------|-----------|
| socialOrient | independent | cooperative | competitive |
| ruleFollowing | defiant | flexible | conformist |
| riskAppetite | conservative | calculated | bold |
| autonomy | dependent | collaborative | autonomous |
| conflictMode | avoidant | diplomatic | confrontational |

`DispositionProfileHandler` writes a cognitive-profiles YAML file to the directory configured by `casehub.cognitive.profiles-dir` (watched by `CognitiveProfileWatcher`). The file follows `CognitiveDefaultsRegistry` format with the `disposition` section populated from the entry's categorical axes. `CognitiveDerivationEngine` then derives personality weights, mood baseline, curiosity config, CBR strategy, and other cognitive defaults from the disposition profile. The handler takes the profiles directory path via config injection.

### BiographyTemplateTypes Update

```
Layer 1: cultural-context
Layer 2: formative-experience
Layer 4: life-event, place, activity, project, organisation (NEW)
Layer 5: relationship
Layer 6: goal, belief
Layer 7: entity-enrichment (NEW), disposition-profile (NEW)
Layer 8: current-state
```

### BiographyProfile Update

Add three new list fields:
```java
List<OrganisationEntry> organisations,
List<EntityEnrichmentEntry> entityEnrichments,
List<DispositionProfileEntry> dispositionProfiles,
```

`BiographyLoader` adds cases for the three new types.

## Stage 11: Post-Import Validation

### Round-trip Integrity

A validation pass (Python script `validate_import.py` or Java `@QuarkusTest`) queries the stores and compares against corpus expectations:

| Check | Source | Target | Assertion |
|-------|--------|--------|-----------|
| Node count | corpus nodes by type | MindMap subgraph node counts | Within tolerance (±5% for alias merges) |
| Edge count | corpus edges | MindMap edge count | Within tolerance (edges may merge) |
| Memory count | corpus memories by domain | CaseMemoryStore scan by domain | Exact match |
| PAD fidelity | corpus node PAD | MindMap node PAD | Values match within floating-point epsilon |
| Vocabulary values | corpus goal fields | MindMap node properties | All values in GoalVocabulary valid sets |
| Subject alignment | corpus memory subjects | MindMap PERSON nodes | All subjects resolve |
| Goal graph | corpus goal edges | MindMap GOAL subgraph edges | decomposes-into and contributes-to chains connected |
| Enrichment presence | corpus entity_enrichments | MindMap node properties | Drive baselines present on enriched entities |
| Disposition presence | corpus disposition_profile | CognitiveDefaults YAML | Axes match |

### Validation Report

JSON report with pass/fail per check, counts, and details for failures. Non-zero failures are diagnostic, not blocking — the report tells you what to fix in the converter or handlers.

## Per-Corpus Configuration

`verify_schema.yaml` gains a `converter` section:

```yaml
converter:
  subject_name: "Frida Kahlo"
  output_dir: biography-output
  skip_formative_experiences: true  # these are handcrafted, not extracted
  concept_mapping: belief           # map concept nodes to belief entries
  edge_attribution: source_first    # assign edges to source entity
```

Everything else (aliases, vocabularies, field mappings) is already in the schema.

## Testing Strategy

### Unit tests (Python)
- `test_convert_corpus.py`: converter produces valid YAML for each entry type, edge mapping covers all priority levels, alias resolution works, ID generation is deterministic and unique

### Unit tests (Java)
- Extend existing handler tests for new fields (GoalHandlerTest, LifeEventHandlerTest)
- `OrganisationHandlerTest`: node creation, properties, associations
- `EntityEnrichmentHandlerTest`: drive baselines, CAPS patterns stored
- `DispositionProfileHandlerTest`: cognitive profile YAML written

### Integration test (Java)
- `BiographyImportRunnerTest`: full round-trip — load converter YAML output, run import, query stores, validate counts and field values
- Uses InMemoryMindMapStore + InMemoryMemoryStore

### Pipeline integration
- Add `convert_corpus.py` as Step 9 in `run_pipeline.sh`
- Add `validate_import.py` as Step 11 (or fold into the Java integration test)

## References

- GoalEntry.java, GoalHandler.java — existing goal import infrastructure
- LifeEventEntry.java, LifeEventHandler.java — existing life event import with sub-thoughts
- BiographyImportRunner.java, BiographyLoader.java — import orchestration
- BiographyTemplateTypes.java — layer ordering
- verify_schema.yaml — Java-side import contract
- corpus.json (extraction/output-test/) — source data format
- GoalVocabulary.java — valid vocabulary values
- SubThoughtAttributeKeys — attribute key pattern for indexed fields
- CognitiveDefaultsRegistry — cognitive profile YAML loading
- Issue #550 — verify_corpus.py design (verify_schema.yaml introduced)
- Issue #538 — parent epic (goal & motivation taxonomy)

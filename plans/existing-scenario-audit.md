# Existing Wacky Manor Scenario Audit

Audit of the current wacky-manor scenario for cognitive capability coverage, to inform the Traitors game format design (casehubio/examples#176, #203).

## 1. Scenario Structure

### World
- **6 rooms** connected linearly: Entrance Hall → Kitchen → Ballroom, Entrance Hall → Library → Laboratory → Cellar
- **Objects** with x-positions within rooms, some portable (rat-poison, brass-key, treasure-map), some interactable (puzzles, locked cabinet)
- **Triggers** — condition-based (character in room, item possession, scene completion). Currently 3 triggers: poison-discovery, tea-scene-start, scenario-complete

### Tick Loop (per character, parallel via virtual threads)
1. **Recall** — salience-scored memories + personality-weighted retrieval + reflections + relationships
2. **Observe** — render location, objects, characters, goals, plans, memories, insights, relationship notes
3. **Act** — LLM invocation → JSON response with thinking, dialogue, aside, action, moodImpact
4. **Resolve** — validate and execute action against WorldState
5. **Record** — experience ingest + disposition recording + trust update
6. **Reflect** — triggered by memory count threshold; produces insights → goal evaluation → plan evaluation

### Actions Available
MOVE, TAKE, USE, GIVE, EXAMINE, LOOK, STEAL, PULL_ASIDE, WAIT

### Win Condition
Tea-poisoning scene completes (scripted beats: offer-tea → pour-poison → foil → aftermath)

### Format
Open-ended exploration until trigger conditions align. No phases, no rounds, no structured confrontation points. Characters wander, discover, scheme, interact on their own initiative.

## 2. Characters

### Core Cast (5 with full biography profiles)

| Character | Entity Name | AMPD Profile | Attachment | Goals | Cognitive Role |
|-----------|-------------|-------------|------------|-------|----------------|
| **Penelope Pitstop** | Clara Bellingham | Very low pathology (all <25), secure | Secure | Find diamond, solve puzzles | Healthy baseline — tests curiosity, social harmony |
| **Hooded Claw** | Vincent Marsh | High dark triad (callousness 90, manipulativeness 85, deceitfulness 85), controlled | Dismissive-avoidant | Eliminate Clara, maintain disguise | Antagonist — tests deception, suppression, self-preservation |
| **Ant Hill Mob** | Brixton Boys | Moderate (suspiciousness 65, hostility 40, anxiousness 50) | Anxious-preoccupied | Protect Clara at all costs | Protector — tests vigilance, fear, attachment |
| **Dick Dastardly** | Reginald Foxworth | Moderate dark triad (grandiosity 80, irresponsibility 75, attention-seeking 85) | Dismissive-avoidant | Steal treasure, trick others | Schemer — tests impulsivity, competence drives |
| **Peter Perfect** | James Hartwell | Low pathology (grandiosity 30 is highest), secure | Secure (slight performance anxiety) | Impress Clara, find treasure | Romantic hero — tests affiliation, competence |

### Supporting Cast (13 in characters.yaml, no biography profiles)
Lazy Luke, Blubber Bear, Muttley, Pat Pending, Sergeant Blast, Private Meekly, Rock Slag, Gravel Slag, Rufus Ruffcut, Sawtooth, Big Gruesome, Little Gruesome, Red Max. These have start positions and inventories but no full personality profiles.

### Character Creation Pattern
Each character is defined by:
1. **Biography YAML** (in `biographies/<id>/`) — 5 files:
   - `personality-profile.yaml` — AMPD (25 facets), attachment, OCEAN, MBTI, Jungian stack, Enneagram, DISC, Belbin, Thomas-Kilmann, SDI, locus of control, archetypes, disposition axes
   - `goals.yaml` — thematic/tactical/operational goals with PAD values
   - `beliefs.yaml` — core beliefs
   - `life-events.yaml` — formative experiences
   - `relationships.yaml` — initial relational knowledge
2. **Descriptor YAML** (in `eidos/descriptors-*.yaml`) — Eidos agent descriptor with slot, disposition, capabilities, templates, constraints, briefing, voice
3. **Character entry** (in `characters.yaml`) — start room, x-position, inventory, think delay

Creating a new character requires all three layers. The biography layer feeds into CognitiveDefaults derivation (25 PID-5 facets → personality weights, mood baseline, search budget, etc.).

## 3. Cognitive Capabilities Currently Triggered

### Actively Exercised

| Capability | Mechanism | Coverage |
|-----------|-----------|----------|
| **Memory** (experience, recall, salience) | AgentExperienceService — every tick | Full |
| **Reflection** (insight synthesis) | ManorReflectionSynthesizer — triggered by memory threshold | Full |
| **Goal lifecycle** (formation, revision, completion) | ManorGoalEvaluator + ManorGoalFormationStrategy | Full |
| **Plan formation & revision** | ManorPlanEvaluator + ManorPlanFormationStrategy | Full |
| **Trust scoring** | ManorTrustProvider — accumulates from STEAL/GIVE actions | Partial — limited action variety |
| **Disposition recording** | ManorDispositionRecorder — maps action outcomes to signals | Partial |
| **Personality-weighted retrieval** | PersonalityWeightedRetrieval.reweight() | Full |
| **Mood** (PAD tracking, decay) | CognitionCore + MoodOrchestrator | Full |
| **Drives** (curiosity, competence, affiliation, autonomy) | DriveOrchestrator with 4 drive sources | Full |
| **Narrative identity** | NarrativeOrchestrator | Wired |
| **User model** (per-subject profiles) | UserModelOrchestrator | Wired |
| **Mental model** (BDI theory of mind) | MentalModelOrchestrator | Wired |
| **Strategy learning** | StrategyLearningOrchestrator | Wired |
| **CARMA appraisal** (SEC dimensions, OCC emotions) | LlmAppraisalStrategy — single Haiku call per recordInteraction | Wired |
| **CAPS** (cognitive-affective processing) | SituationClassifier + CapsEngine settling | Wired — precomputed per tick |
| **Emotion regulation** | CopingDefaults, RegulationDefaults | Wired via CognitionCore |
| **Cognitive profile** (entity knowledge resolution) | CognitiveProfile | Wired |
| **Consolidation** (experience graduation, merge detection, etc.) | ConsolidationScheduler | Wired but idle-gated |
| **Expression styles** | ExpressionStyleDefaults (AMPD-derived) | Wired |
| **Gut feeling** | GutFeelingParticipant | Wired |
| **Search budget** | SearchBudgetTickParticipant | Wired |
| **MindMap** (knowledge graph) | ConversationBridge + MindMapExtractor | Wired |

### Eval Infrastructure
- **Classification pipeline** (`classify_emotions.py`) — LLM-based drive expression quality scoring
- **Thinking-field scoring** — evaluates emotional grounding quality
- **Regulation eval** — baseline vs enabled comparison
- **Behavioral attractor eval** — confrontation vs harmony A/B test
- **Smoke scenario** — quick validation run
- 100+ eval runs archived in `docs/eval/`
- Extensive unit test suite (~100 test classes)

## 4. What's NOT Triggered (Cognitive Capability Gaps)

### Structural Gaps — the scenario format doesn't create conditions for these

| Capability | Why Not Triggered | What Would Trigger It |
|-----------|-------------------|----------------------|
| **Trust dynamics — betrayal/repair** | No mechanic for trust to be meaningfully broken and rebuilt. STEAL is the only negative trust action; no deception detection, no alliance breaking. | Traitors format: role reveals, false accusations, public trust tests |
| **Belief revision** | Characters rarely learn facts that contradict existing beliefs. The world is mostly static once explored. | Discovery of deception, role reveals, evidence contradicting assumptions |
| **Attachment disruption** | No elimination or separation mechanic. Characters are always present. | Banishment/elimination — forced loss of allies |
| **Relational schema evolution** | Relationships form slowly via co-location. No structural pressure to change relationship type (ally → rival, stranger → confidant). | Forced cooperation then competition, role-based relationship shifts |
| **Drive conflict (loyalty vs self-preservation)** | No mechanic that pits drives against each other. Characters can pursue all goals simultaneously. | Voting someone out to save yourself, choosing between allies |
| **Cognitive dissonance** | No contradictions in character knowledge or values. | Trusting someone proven to be a traitor, being forced to act against stated values |
| **Personality evolution under pressure** | Disposition signals accumulate slowly without intense emotional situations. | Repeated high-intensity confrontations at regular intervals |
| **Recurring thought / fixation / rumination** | Insufficient emotional intensity to push past healthy thresholds. | Elimination threats, repeated failures, unresolved interpersonal conflict |
| **Goal planning (dynamic, multi-step)** | Current goals are static (find diamond, protect Clara). No new goals emerge from changing circumstances. | Phase-based objectives, shifting alliances, elimination threats create new goals |
| **Information gap curiosity** | Limited discoverable information. Most world knowledge is revealed on first LOOK. | Hidden roles, clues scattered across time, pieces that form patterns |
| **Collaboration / competition dynamics** | 3-operator machine requires cooperation but rarely triggers. No structured cooperation challenges. | Phase-based team tasks where success requires collaboration but only one team wins |

### Partial Coverage — triggered but under-exercised

| Capability | Current State | What Would Improve It |
|-----------|---------------|----------------------|
| Theory of Mind | Characters observe each other but rarely need to predict intentions | Deduction mechanic — who is the traitor? Requires modelling others' motivations |
| Emotion regulation | Wired but scenarios rarely produce high-intensity emotions that need regulation | Regular forced confrontations (roundtables) with public emotional stakes |
| Social norms | No norm emergence — characters don't develop shared behavioural expectations | Repeated group interactions establish norms; norm violations become visible |
| Relationship memories | Recorded but rarely decisive for future actions | Relationship quality should gate cooperation (won't work with someone you distrust) |
| Inner life (proactive speech) | Wired but rarely triggered by environmental pressure | Elimination threat creates internal monologue pressure |

## 5. Character Creation Patterns

### What It Takes to Create a New Character
1. Create `biographies/<id>/` directory with 5 YAML files (personality-profile, goals, beliefs, life-events, relationships)
2. Add entry to `descriptors-composite.yaml` (or separate descriptor file) with Eidos configuration
3. Add entry to `characters.yaml` with start position and inventory
4. The biography seeder (`ManorCognitiveSeeder`) loads biographies at startup and seeds CaseMemoryStore + MindMapStore

### Personality Profile Richness
Each character's `personality-profile.yaml` carries 11 framework assessments:
- **AMPD** (25 PID-5 facets, 0-100 scale)
- **Attachment** (style + anxiety/avoidance scores)
- **OCEAN** (Big Five, 0-1)
- **MBTI** (4-letter type)
- **Jungian stack** (weighted cognitive functions)
- **Enneagram** (type + wing)
- **DISC** (primary/secondary)
- **Belbin** (team role)
- **Thomas-Kilmann** (conflict mode)
- **SDI** (motivational value system)
- **Locus of control** (general + per-domain)
- **Archetypes** (ranked family/sub-archetype)
- **Disposition axes** (5 axes: socialOrient, ruleFollowing, riskAppetite, autonomy, conflictMode)

The disposition axes feed into CognitiveDerivationEngine which derives all cognitive defaults.

### Creating New Variations
The quickest path to new characters:
1. Copy an existing biography directory
2. Modify the AMPD facets and disposition axes to stress different cognitive models
3. Write goals that create tension with other characters
4. Add beliefs that will be challenged by the scenario

**Characters designed to stress specific cognitive models:**
- **High suspiciousness + low trust** → stresses Theory of Mind, belief revision
- **High anxiousness + high separation insecurity** → stresses attachment, recurring thought
- **High impulsivity + high risk-taking** → stresses emotion regulation, search budget
- **High rigid perfectionism + high perseveration** → stresses cognitive dissonance, fixation
- **Conflicting goals between characters** → stresses drive conflict, strategy adaptation

## 6. Existing Test Infrastructure

### Unit Tests (~100 test classes)
- `CognitiveActivationTest` — verifies CognitionCore tick + prompt sections per config level
- `CognitivePipelineWiringTest` — verifies LLM calls fire via recordInteraction
- `RegulationTrackerTest`, `RegulationConfigWiringTest` — regulation mechanics
- `SocialCognitionIntegrationTest` — social cognition wiring
- `DriveAdaptationIntegrationTest` — drive adaptation
- `GoalLifecycleTest`, `PlanLifecycleTest` — goal/plan formation and revision
- `BehavioralAttractorEvalTest` — A/B test: confrontation vs harmony attractors

### LLM Eval Tests (tagged `@Tag("llm-eval")`)
- `BehavioralAttractorEvalTest` — attractor discrimination
- `ChannelWeightingEvalTest` — multi-channel thinking evaluation
- `DriveQualityEvalTest` — drive expression quality
- `MetacognitiveAwarenessEvalTest` — metacognitive awareness
- `SituationClassifierIntegrationTest` — CAPS situation classification
- `SmokeScenarioEvalTest` — quick scenario validation

### Classification Pipeline
Python scripts in `docs/eval/`:
- `classify_emotions.py` — drive quality scoring per event
- `score_thinking_field.py` — thinking field emotional grounding
- `correlate_instrumentation.py` — pipeline instrumentation correlation
- `cross_compare.py` — cross-run comparison

### Transcript Recording
`TranscriptRecorderTest` + `TranscriptStore` — records scenario runs as JSON for post-hoc analysis.

## 7. Summary: What the Traitors Format Must Provide

The current format is a **static exploration sandbox** — characters wander, discover, and interact at their own pace. The cognitive pipeline is fully wired but under-stimulated because the environment doesn't force emotional intensity, trust dynamics, or structural confrontation.

The Traitors format needs to provide:
1. **Structured confrontation** — regular forced interaction (roundtable) where characters must accuse, defend, or reveal
2. **Elimination mechanic** — creates attachment disruption, self-preservation pressure, and goal urgency
3. **Hidden roles** — drives Theory of Mind, belief revision, and information gap curiosity
4. **Phase structure** — day/night/roundtable creates different emotional contexts per phase
5. **Alliance mechanics** — cooperation that can be betrayed, creating relational schema evolution
6. **Dynamic goals** — survive, identify traitor, protect allies — goals that shift as the game progresses
7. **Sufficient duration** — relationship arcs need repeated interactions (>300 ticks for multi-arc coverage)
8. **Co-location pressure** — characters in the same space with reason to interact (not just wandering)

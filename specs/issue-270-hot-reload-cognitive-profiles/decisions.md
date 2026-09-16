## D1: File source — configurable filesystem directory

**Choice:** Configurable filesystem path via `casehub.cognitive.profiles-dir` config property
**Alternatives:**
- Classpath resources — baked into JAR at build time, not meant for runtime mutation
- Quarkus @ConfigMapping — can't model complex nested YAML (15-field records with vocabulary, rules, etc.)
**Rationale:** Filesystem path is the standard pattern for runtime-mutable config. Classpath is for immutable bundled resources.
**Trade-offs:** Requires deployers to configure a path; classpath loading remains the default when unconfigured.
**Sources:** CognitiveDefaultsRegistry.java:52-60 (current classpath loading)
**Exploration:** quick
**Status:** captured

## D2: Error handling — atomic all-or-nothing reload

**Choice:** Reject entire reload and keep previous state on any parse error
**Alternatives:**
- Accept valid files, skip broken ones — risks inconsistent state where profile A's rules reference vocabulary from profile B that didn't load
**Rationale:** Cognitive profiles can reference each other through rule overrides and vocabulary. Partial loads could leave inconsistent cross-profile state.
**Trade-offs:** A single broken file blocks all profile updates until fixed. Acceptable because the previous valid state is preserved.
**Sources:** CognitiveDefaults record (15 fields including vocabulary, traitRules, derivedEdgeRules with cross-profile merging)
**Exploration:** quick
**Status:** captured

## D3: Notification mechanism — CDI event

**Choice:** Fire `CognitiveProfilesReloaded` CDI event for downstream consumers
**Alternatives:**
- Direct method callbacks from watcher — tight coupling, watcher must know every consumer
**Rationale:** Decouples watcher from consumers, follows existing codebase patterns (ExtractionRequested, ConsolidationCompleted, CbrRetrievalRecorded). Future consumers can observe without modifying the watcher.
**Trade-offs:** Slightly more indirection than direct calls. CDI event dispatch adds minimal overhead.
**Sources:** ExtractionRequested, ConsolidationCompleted, CbrRetrievalRecorded (existing CDI event patterns)
**Exploration:** quick
**Status:** captured

## D4: File-watching mechanism — io.methvin:directory-watcher

**Choice:** Use `io.methvin:directory-watcher` (0.19.1), the project standard
**Alternatives:**
- Java NIO WatchService — on macOS uses polling internally anyway; complex API with no benefit
- ScheduledExecutorService polling — simpler but diverges from established project convention
**Rationale:** Project protocol mandates directory-watcher. Already used by FlatChangeSource with proven debounce + overflow recovery patterns.
**Trade-offs:** None — already a managed dependency in the parent POM.
**Sources:** FlatChangeSource.java (existing usage), corpus/pom.xml, project protocol
**Exploration:** quick
**Status:** captured

## D5: Module placement — cognitive-index

**Choice:** Watcher lives in `cognitive-index` module alongside CognitiveDefaultsRegistry
**Alternatives:**
- New dedicated module — adds overhead with no benefit; watcher is a private implementation detail
**Rationale:** The watcher serves CognitiveDefaultsRegistry and DeclarativeRuleRegistry, both in cognitive-index. No new SPI exposed. Only new dependency is directory-watcher (already in parent POM).
**Trade-offs:** cognitive-index gains a runtime dependency on directory-watcher. Acceptable since it's optional (watcher only starts when config property is set).
**Sources:** cognitive-index module structure
**Exploration:** quick
**Status:** captured

## D6: Activation — config-gated

**Choice:** Watcher starts only when `casehub.cognitive.profiles-dir` is set; classpath loading preserved as default
**Alternatives:**
- Always-on watching — breaks deployments that rely on classpath-only loading
- Separate boolean gate + path — unnecessary; presence of path is sufficient signal
**Rationale:** Follows existing pattern (casehub.rag.crag.enabled, casehub.cbr.reranking.enabled). No behavioural change for existing deployments.
**Trade-offs:** Deployers must explicitly configure the path to get hot-reload.
**Sources:** Existing config-gated patterns in rag-crossencoder, memory
**Exploration:** quick
**Status:** captured

## D7: Thread safety — volatile reference swap

**Choice:** Volatile reference swap for the profiles map
**Alternatives:**
- ReadWriteLock — adds contention for reads (the hot path) with no benefit since the map is already immutable via Map.copyOf()
**Rationale:** Registry already stores profiles in immutable Map.copyOf(). On reload: parse all YAML into new immutable map, assign to volatile field. Readers see either old or new — never partial state. Lock-free reads.
**Trade-offs:** None meaningful — volatile read cost is negligible.
**Sources:** CognitiveDefaultsRegistry.java:45 (current Map<String, CognitiveDefaults> field)
**Exploration:** quick
**Status:** captured

## D8: Watch scope — both directories

**Choice:** Watch both cognitive-profiles/ and rules/ directories
**Alternatives:**
- Watch profiles only — leaves a confusing gap where per-agent rules auto-refresh but global rules don't
**Rationale:** DeclarativeRuleRegistry reads per-agent rules from CognitiveDefaultsRegistry on every call (auto-refreshes with volatile swap). But global rules are a separate immutable list that needs explicit reload. Watching both gives consistent live-reload across the full rule system.
**Trade-offs:** Second watcher adds minimal overhead. Requires `casehub.cognitive.rules-dir` config property.
**Sources:** DeclarativeRuleRegistry.java:60-73 (global rules loading), :87-98 (per-agent merge on every call)
**Exploration:** quick
**Status:** captured

## D9: Vocabulary re-registration — full re-register

**Choice:** On reload, iterate all current profiles and call registerVocabulary() for each
**Alternatives:**
- Diff-based unregister/register — requires MindMapStore.unregisterVocabulary() SPI addition that doesn't exist
- Skip vocabulary reload — leaves stale vocabulary on modification, missing vocabulary on new profiles
**Rationale:** registerVocabulary() is idempotent for unchanged definitions. New/changed definitions overwrite. Removed profiles leave orphaned edge type definitions which are harmless metadata. No SPI changes needed.
**Trade-offs:** Orphaned vocabulary entries from removed profiles persist in the store. Acceptable — they're inert metadata that doesn't affect correctness.
**Sources:** CognitiveLoader.java:63-69 (current vocabulary registration loop), MindMapStore.registerVocabulary()
**Exploration:** quick
**Status:** captured

## D10: Architecture — single CognitiveProfileWatcher bean

**Choice:** Single @ApplicationScoped CognitiveProfileWatcher coordinates both directory watchers
**Alternatives:**
- Registry-internal watching — duplicates watcher infrastructure, makes cross-coordination harder (rules depend on profiles, reload order matters)
**Rationale:** Single coordination point ensures explicit ordering (profiles before rules), centralises watcher lifecycle, fires one CDI event for consumers.
**Trade-offs:** New bean adds to the CDI graph. Minimal — it's a single singleton.
**Depends on:** D4 (directory-watcher), D5 (cognitive-index module), D6 (config-gated)
**Sources:** ConsolidationScheduler.java (existing daemon thread + lifecycle pattern), FlatChangeSource.java (DirectoryWatcher usage pattern)
**Exploration:** quick
**Status:** captured

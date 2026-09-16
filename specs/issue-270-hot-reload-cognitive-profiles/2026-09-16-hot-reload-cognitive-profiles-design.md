# Hot-Reload Cognitive Profiles — Design Spec

**Issue:** casehubio/neocortex#270
**Epic:** #253 (Cognitive Rearchitecture)
**Date:** 2026-09-16

## Problem

V1 loads cognitive profiles and global rules from classpath YAML at startup via `@PostConstruct`. Changing an agent's personality weights, vocabulary, trait rules, or derived edge rules requires a full application restart. During iterative agent development, this creates a slow feedback loop.

## Goal

Enable live reload of cognitive profiles and global rules from filesystem directories without restart. Changes to YAML files are detected, parsed, validated, and applied atomically with thread-safe reads throughout.

## Scope

In scope:
- File watching on configurable filesystem directories for profiles and rules
- CognitiveDefaultsRegistry atomic refresh on file change
- DeclarativeRuleRegistry global rules refresh on file change
- CognitiveLoader vocabulary re-registration on profile change
- Thread safety for concurrent reads during reload
- CDI event notification for downstream consumers

Out of scope:
- `MindMapStore.unregisterVocabulary()` SPI — orphaned vocabulary from removed profiles is harmless metadata that doesn't affect correctness. Tracked as a follow-up issue.
- TypeRegistry refresh (cognitive types are static, not profile-driven)
- Quarkus @ConfigMapping integration (profiles are complex nested YAML, not key-value config)

## Architecture

### Component Overview

```
 ┌─────────────────────────────────────────────────────────────────┐
 │  CognitiveProfileWatcher (@ApplicationScoped)                  │
 │                                                                │
 │  - DirectoryWatcher for profiles-dir (500ms debounce)          │
 │  - DirectoryWatcher for rules-dir (500ms debounce)             │
 │                                                                │
 │  On profiles change:                                           │
 │    1. Re-parse all YAML from profiles dir                      │
 │    2. Validate → reject-all on error, keep previous state      │
 │    3. Merge filesystem with classpath baseline                  │
 │    4. Volatile swap on CognitiveDefaultsRegistry               │
 │    5. Fire CognitiveProfilesReloaded CDI event                 │
 │                                                                │
 │  On rules change:                                              │
 │    1. Re-parse all YAML from rules dir                         │
 │    2. Validate → reject-all on error, keep previous state      │
 │    3. Merge filesystem with classpath baseline                  │
 │    4. Single volatile swap on DeclarativeRuleRegistry           │
 │    (no CDI event — rules auto-merge on read)                   │
 └──────────┬──────────────────────────┬──────────────────────────┘
            │ reload()                 │ reloadGlobalRules()
            ▼                          ▼
 ┌──────────────────────┐   ┌──────────────────────────────┐
 │ CognitiveDefaults-   │   │ DeclarativeRuleRegistry      │
 │ Registry             │   │                              │
 │                      │   │ volatile GlobalRules holder   │
 │ volatile profiles    │   │ (single immutable record)    │
 │ Map.copyOf()         │   │                              │
 └──────────────────────┘   └──────────────────────────────┘
            │
            │ @Observes CognitiveProfilesReloaded
            ▼
 ┌──────────────────────┐
 │ CognitiveLoader      │
 │                      │
 │ re-register          │
 │ vocabulary for all   │
 │ current profiles     │
 └──────────────────────┘
```

All components live in the `cognitive-index` module (watcher, registries) and `mindmap-intelligence` module (CognitiveLoader). The watcher is the only new bean.

### Configuration

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `casehub.cognitive.profiles-dir` | Optional\<Path\> | absent | Filesystem directory for cognitive profile YAML files. When set, enables file watching. |
| `casehub.cognitive.rules-dir` | Optional\<Path\> | absent | Filesystem directory for global rule YAML files. When set, enables file watching. |

When neither property is set, behaviour is unchanged from V1 — classpath-only loading, no watching.

### CDI Initialisation Ordering

The watcher uses constructor injection for both `CognitiveDefaultsRegistry` and `DeclarativeRuleRegistry`. CDI guarantees that injected beans' `@PostConstruct` methods complete before the dependent bean's constructor returns. This ensures:

1. `CognitiveDefaultsRegistry.init()` loads classpath profiles first
2. `DeclarativeRuleRegistry.init()` loads classpath rules first
3. `CognitiveProfileWatcher` constructor receives fully initialised registries
4. `CognitiveProfileWatcher.init()` can snapshot the classpath baselines from the already-loaded registries

### Loading and Merge Semantics

**Startup sequence:**

1. `CognitiveDefaultsRegistry.init()` loads profiles from classpath `cognitive-profiles/` (unchanged)
2. `DeclarativeRuleRegistry.init()` loads global rules from classpath `rules/` (unchanged)
3. `CognitiveProfileWatcher.init()` (runs after registries are initialised via constructor injection):
   a. Snapshot classpath baselines from the already-loaded registries:
      - `classpathProfiles` = build `Map<String, CognitiveDefaults>` from `registry.allProfiles()`
      - `classpathRules` = snapshot current global rules from `ruleRegistry`
   b. If `profiles-dir` is configured:
      - Read filesystem profiles from configured directory
      - Merge: filesystem profiles override classpath on matching `agentId`
      - Call `registry.reload(merged)` — atomic volatile swap
   c. If `rules-dir` is configured:
      - Read filesystem rules from configured directory
      - Merge: filesystem rules override classpath on matching rule name
      - Call `ruleRegistry.reloadGlobalRules(mergedTraitRules, mergedDerivedRules)` — single atomic volatile swap
   d. Start DirectoryWatcher instances for configured directories
   e. If profiles were loaded from filesystem, fire initial `CognitiveProfilesReloaded` event (so CognitiveLoader re-registers vocabulary)

**Runtime reload — profiles directory change:**

1. DirectoryWatcher detects change → debounced callback (500ms)
2. Re-parse all YAML files from the profiles directory
3. If any file fails to parse: log error with filename and cause, keep previous state, return
4. Merge filesystem results with cached classpath baseline
5. Atomic volatile swap on `CognitiveDefaultsRegistry`
6. Fire `CognitiveProfilesReloaded` CDI event

Per-agent rules in `DeclarativeRuleRegistry` (`traitRules(agentId)`, `derivedEdgeRules(agentId)`) already read from `CognitiveDefaultsRegistry.forAgent()` on every call — they auto-refresh after the volatile swap without any rule reload. Global rules are not affected by profile changes (they don't reference vocabulary or profile data).

**Runtime reload — rules directory change:**

1. DirectoryWatcher detects change → debounced callback (500ms)
2. Re-parse all YAML files from the rules directory
3. If any file fails to parse: log error with filename and cause, keep previous state, return
4. Merge filesystem results with cached classpath baseline
5. Single atomic volatile swap on `DeclarativeRuleRegistry` (via `GlobalRules` holder)
6. No CDI event fired — global rules are read on demand, and per-agent rules come from the profiles registry

**Merge rule:** filesystem wins on conflict. Classpath profiles/rules are the baseline. Filesystem adds new entries and overrides existing ones by key (`agentId` for profiles, rule name for rules).

**Empty directory handling:** If a configured directory is empty or contains no `.yaml`/`.yml` files, the classpath baseline is used unmodified. This allows deployers to configure the path upfront and populate it later.

**Non-existent directory:** If the configured directory does not exist at startup, create it (matching `FlatChangeSource` pattern) and start watching. Initial load produces no filesystem entries — classpath baseline used.

### CognitiveProfileWatcher

New `@ApplicationScoped` bean in `io.casehub.neocortex.cognitive.index`.

```java
@ApplicationScoped
public class CognitiveProfileWatcher {

    private final CognitiveDefaultsRegistry registry;
    private final DeclarativeRuleRegistry ruleRegistry;
    private final Event<CognitiveProfilesReloaded> reloadEvent;
    private final Optional<Path> profilesDir;
    private final Optional<Path> rulesDir;

    // Classpath baselines — snapshotted at init from already-loaded registries
    private Map<String, CognitiveDefaults> classpathProfiles;
    private GlobalRules classpathRules;

    // DirectoryWatcher instances
    private volatile DirectoryWatcher profilesWatcher;
    private volatile DirectoryWatcher rulesWatcher;

    // Debounce infrastructure (per FlatChangeSource pattern)
    private ScheduledExecutorService debounceExecutor;

    @Inject
    CognitiveProfileWatcher(CognitiveDefaultsRegistry registry,
                            DeclarativeRuleRegistry ruleRegistry,
                            Event<CognitiveProfilesReloaded> reloadEvent,
                            @ConfigProperty(name = "casehub.cognitive.profiles-dir")
                                Optional<Path> profilesDir,
                            @ConfigProperty(name = "casehub.cognitive.rules-dir")
                                Optional<Path> rulesDir) {
        // Constructor injection guarantees registries are fully initialised
        this.registry = registry;
        this.ruleRegistry = ruleRegistry;
        this.reloadEvent = reloadEvent;
        this.profilesDir = profilesDir;
        this.rulesDir = rulesDir;
    }
    // ...
}
```

**Lifecycle:**
- `@PostConstruct`: snapshot classpath baselines from registries, initial filesystem load + merge, start watchers
- `@PreDestroy`: close watchers, shutdown debounce executor

**Debounce:** 500ms using `ScheduledExecutorService` with daemon thread, matching `FlatChangeSource`. Multiple rapid file changes coalesce into a single reload.

**Overflow handling:** On `DirectoryChangeEvent.EventType.OVERFLOW`, perform a full re-read of the affected directory (matching `FlatChangeSource.handleOverflow()`).

**File filtering:** Only process `.yaml` and `.yml` files. Ignore hidden files (starting with `.`) and directories.

### CognitiveDefaultsRegistry Changes

Minimal changes to the existing class:

1. `private Map<String, CognitiveDefaults> profiles` → `private volatile Map<String, CognitiveDefaults> profiles`
2. New package-private method:
   ```java
   void reload(Map<String, CognitiveDefaults> newProfiles) {
       this.profiles = Map.copyOf(newProfiles);
   }
   ```

No changes to the public API (`forAgent`, `forAgentOrDefaults`, `allProfiles`). All read from the volatile `profiles` field and return values from the immutable map — thread-safe without locking.

### DeclarativeRuleRegistry Changes

1. Replace two independent volatile fields with a single immutable holder to ensure atomic reads:
   ```java
   private record GlobalRules(List<DeclarativeTraitRule> traitRules,
                              List<DeclarativeDerivedEdgeRule> derivedEdgeRules) {}

   private volatile GlobalRules globalRules = new GlobalRules(List.of(), List.of());
   ```

2. `init()` sets the holder:
   ```java
   this.globalRules = new GlobalRules(
       List.copyOf(result.traitRules()),
       List.copyOf(result.derivedEdgeRules()));
   ```

3. New package-private method:
   ```java
   void reloadGlobalRules(List<DeclarativeTraitRule> traitRules,
                          List<DeclarativeDerivedEdgeRule> derivedRules) {
       this.globalRules = new GlobalRules(
           List.copyOf(traitRules), List.copyOf(derivedRules));
   }
   ```

4. Read methods access the holder:
   ```java
   public List<TraitRule> traitRules(String agentId) {
       var merged = new LinkedHashMap<String, TraitRule>();
       GlobalRules snapshot = globalRules;  // single volatile read
       snapshot.traitRules().forEach(r -> merged.put(r.traitName(), r));
       // ... per-agent merge from cognitiveDefaults
       return List.copyOf(merged.values());
   }
   ```

Single volatile write → single publication point → no torn reads between trait rules and derived edge rules.

Per-agent rules (`traitRules(agentId)`, `derivedEdgeRules(agentId)`) already read from `CognitiveDefaultsRegistry` on every call — they auto-refresh after the registry's volatile swap.

### CognitiveProfilesReloaded Event

```java
public record CognitiveProfilesReloaded(Collection<CognitiveDefaults> profiles) {}
```

Carries the new profile collection so observers don't need to re-inject the registry. Fired synchronously via `Event.fire()` — reload is complete before the event returns, ensuring consumers see consistent state.

**Fired only when profiles change.** Rules-only changes do not fire this event — global rules are read on demand and per-agent rules auto-refresh via the profiles registry volatile swap. This avoids misleading semantics and unnecessary vocabulary re-registration when only rules changed.

### CognitiveLoader Changes

Add an observer method:

```java
void onProfilesReloaded(@Observes CognitiveProfilesReloaded event) {
    if (store == null) return;
    int registered = 0;
    for (CognitiveDefaults defaults : event.profiles()) {
        if (defaults.vocabulary() != null) {
            try {
                store.registerVocabulary(defaults.vocabulary());
                registered++;
            } catch (VocabularyConflictException e) {
                LOG.warning("Vocabulary conflict during reload for agent '"
                    + defaults.agentId() + "': " + e.getMessage());
            }
        }
    }
    if (registered > 0) {
        LOG.info("Re-registered vocabulary from " + registered + " profile(s) after reload");
    }
}
```

The existing `profiles` field (constructor-snapshot) remains needed — `init()` reads it for initial vocabulary registration when no watcher is configured (no event fires in that path). The observer handles reloads; `init()` handles the no-watcher startup path.

### Module Dependency Change

`cognitive-index/pom.xml` gains:

```xml
<dependency>
    <groupId>io.methvin</groupId>
    <artifactId>directory-watcher</artifactId>
    <!-- version managed in parent POM -->
</dependency>
```

Already declared in the parent POM `<dependencyManagement>`. No version needed.

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| YAML parse error in one file | Reject entire reload, keep previous state, log error with filename and cause |
| Duplicate `agentId` in filesystem | Reject reload, log error (same as current startup behaviour) |
| Filesystem directory deleted at runtime | Watcher closes, log warning. Registry retains last known state. |
| IOException during file read | Reject reload, keep previous state, log error |
| DirectoryWatcher OVERFLOW event | Full re-read of affected directory (no partial state) |
| DirectoryWatcher creation fails at startup | Log warning, disable file watching, application starts with classpath-only loading |
| VocabularyConflictException during reload | Logged per-profile, non-fatal. Profiles are already swapped — vocabulary for conflicting profile is skipped. |
| CDI event observer throws (other) | Standard CDI error handling — logged, does not affect registry state (swap already complete) |

## Thread Safety

**Read path (hot):** All reads go through `volatile` fields pointing to immutable data. `CognitiveDefaultsRegistry` uses `Map.copyOf()`. `DeclarativeRuleRegistry` uses a single `GlobalRules` holder record containing `List.copyOf()` lists — a single volatile read captures both trait rules and derived edge rules atomically. No locking. Readers see either the complete old state or the complete new state — never partial.

**Write path (rare — file change only):** The watcher's debounce executor is single-threaded, serialising all reloads. No concurrent writes. The volatile swap is the publication point.

**Cross-registry consistency:** When profiles change, only `CognitiveDefaultsRegistry.profiles` is swapped. `DeclarativeRuleRegistry` reads per-agent rules from the profiles registry on every call via `forAgent()`, so it naturally sees the updated profiles after the volatile swap. Global rules are independent — no cross-registry atomicity needed.

**CDI event dispatch:** Synchronous on the watcher's debounce thread. Observers must not block indefinitely. `CognitiveLoader.onProfilesReloaded()` does lightweight in-memory work (vocabulary registration) — acceptable.

## Testing Strategy

**Unit tests:**

1. `CognitiveDefaultsRegistry.reload()` — verify volatile swap: write profiles, call reload with new profiles, verify reads return new state
2. `DeclarativeRuleRegistry.reloadGlobalRules()` — verify single-holder atomicity: reload, verify `traitRules()` and `derivedEdgeRules()` return consistent new state
3. `CognitiveProfileWatcher` — use `@TempDir`:
   - Write initial YAML files, verify startup load
   - Modify a file, verify reload fires event with updated profiles
   - Add a new file, verify new profile appears
   - Delete a file, verify profile removed (from filesystem set; classpath baseline preserved)
   - Write invalid YAML, verify previous state preserved and no event fired
   - Rules-only change, verify no `CognitiveProfilesReloaded` event fired
4. `CognitiveLoader` observer — mock MindMapStore, fire event, verify `registerVocabulary()` called for each profile with vocabulary
5. `CognitiveLoader` observer — vocabulary conflict: fire event with conflicting vocabulary, verify logged and non-fatal
6. Watcher creation failure — configure invalid directory path, verify graceful degradation (no watch, classpath-only)

**Integration notes:**

- macOS FSEvents delivers catch-up events at watcher startup (garden entry GE-20260422-a00b81). Tests must use `awaitility` polling for expected state rather than single-fire latches. Allow 1s warmup after `watchAsync()` before test mutations.
- Use `Awaitility.await().atMost(15, SECONDS)` for file-change assertions to handle platform-specific watch latency.

## References

- `cognitive-index/.../CognitiveDefaultsRegistry.java` — current classpath loading, `Map.copyOf()` pattern
- `cognitive-index/.../DeclarativeRuleRegistry.java` — global rules loading, per-agent merge-on-read
- `mindmap-intelligence/.../CognitiveLoader.java` — vocabulary registration loop, `VocabularyConflictException` handling
- `corpus/.../FlatChangeSource.java` — DirectoryWatcher usage pattern (debounce, overflow, daemon thread)
- `mindmap-intelligence/.../consolidation/ConsolidationScheduler.java` — daemon thread lifecycle pattern
- GE-20260422-a00b81 — Quarkus file watcher can silently stop on macOS (FSEvents limits)
- GE-20260512-523f68 — macOS catch-up events at watcher startup (testing implication)
- Project protocol: use `io.methvin:directory-watcher` for filesystem watching

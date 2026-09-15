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
- MindMapStore.unregisterVocabulary() SPI (orphaned vocabulary is harmless)
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
 │  On file change:                                               │
 │    1. Re-parse all YAML from affected dir                      │
 │    2. Validate → reject-all on error, keep previous state      │
 │    3. Merge filesystem with classpath baseline                  │
 │    4. Volatile swap on target registry                          │
 │    5. Fire CognitiveProfilesReloaded CDI event                 │
 └──────────┬──────────────────────────┬──────────────────────────┘
            │ reload()                 │ reloadGlobalRules()
            ▼                          ▼
 ┌──────────────────────┐   ┌──────────────────────────┐
 │ CognitiveDefaults-   │   │ DeclarativeRule-          │
 │ Registry             │   │ Registry                  │
 │                      │   │                           │
 │ volatile profiles    │   │ volatile globalTraitRules  │
 │ Map.copyOf()         │   │ volatile globalDerivedRules│
 └──────────────────────┘   └──────────────────────────┘
            │                          │
            └──────────┬───────────────┘
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

All components live in the `cognitive-index` module. The watcher is the only new bean.

### Configuration

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `casehub.cognitive.profiles-dir` | Optional\<Path\> | absent | Filesystem directory for cognitive profile YAML files. When set, enables file watching. |
| `casehub.cognitive.rules-dir` | Optional\<Path\> | absent | Filesystem directory for global rule YAML files. When set, enables file watching. |

When neither property is set, behaviour is unchanged from V1 — classpath-only loading, no watching.

### Loading and Merge Semantics

**Startup sequence:**

1. `CognitiveDefaultsRegistry.init()` loads profiles from classpath `cognitive-profiles/` (unchanged)
2. `DeclarativeRuleRegistry.init()` loads global rules from classpath `rules/` (unchanged)
3. `CognitiveProfileWatcher.init()` (runs after registries are initialised):
   a. If `profiles-dir` is configured:
      - Read classpath profiles as baseline (via existing `loadFromClasspath()`)
      - Read filesystem profiles from configured directory
      - Merge: filesystem profiles override classpath on matching `agentId`
      - Call `registry.reload(merged)` — atomic volatile swap
   b. If `rules-dir` is configured:
      - Read classpath rules as baseline (via existing `loadGlobalRules()`)
      - Read filesystem rules from configured directory
      - Merge: filesystem rules override classpath on matching rule name
      - Call `ruleRegistry.reloadGlobalRules(mergedTraitRules, mergedDerivedRules)`
   c. Start DirectoryWatcher instances for configured directories
   d. Fire initial `CognitiveProfilesReloaded` event (so CognitiveLoader re-registers)

**Runtime reload sequence (on file change):**

1. DirectoryWatcher detects change → debounced callback (500ms)
2. Re-parse all YAML files from the changed directory
3. If any file fails to parse: log error with filename and cause, keep previous state, return
4. Merge filesystem results with cached classpath baseline
5. Atomic volatile swap on the target registry
6. If both directories are watched and the profiles directory changed, also re-read rules (rules reference profiles via per-agent overrides)
7. Fire `CognitiveProfilesReloaded` CDI event

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

    // Cached classpath baselines for merge
    private volatile Map<String, CognitiveDefaults> classpathProfiles;
    private volatile RuleFile classpathRules;

    // DirectoryWatcher instances
    private volatile DirectoryWatcher profilesWatcher;
    private volatile DirectoryWatcher rulesWatcher;

    // Debounce infrastructure (per FlatChangeSource pattern)
    private ScheduledExecutorService debounceExecutor;
    // ...
}
```

**Lifecycle:**
- `@PostConstruct`: initial filesystem load + merge, start watchers
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
3. Existing `loadFromClasspath()` static method remains unchanged — reused by the watcher for classpath baseline loading.

No changes to the public API (`forAgent`, `forAgentOrDefaults`, `allProfiles`). All read from the volatile `profiles` field and return values from the immutable map — thread-safe without locking.

### DeclarativeRuleRegistry Changes

1. `private List<DeclarativeTraitRule> globalTraitRules` → `private volatile List<DeclarativeTraitRule> globalTraitRules`
2. `private List<DeclarativeDerivedEdgeRule> globalDerivedRules` → `private volatile List<DeclarativeDerivedEdgeRule> globalDerivedRules`
3. New package-private method:
   ```java
   void reloadGlobalRules(List<DeclarativeTraitRule> traitRules,
                          List<DeclarativeDerivedEdgeRule> derivedRules) {
       this.globalTraitRules   = List.copyOf(traitRules);
       this.globalDerivedRules = List.copyOf(derivedRules);
   }
   ```
4. Expose existing `loadGlobalRules()` static method as package-private for watcher reuse.

Per-agent rules (`traitRules(agentId)`, `derivedEdgeRules(agentId)`) already read from `CognitiveDefaultsRegistry` on every call — they auto-refresh after the registry's volatile swap.

### CognitiveProfilesReloaded Event

```java
public record CognitiveProfilesReloaded(Collection<CognitiveDefaults> profiles) {}
```

Carries the new profile collection so observers don't need to re-inject the registry. Fired synchronously via `Event.fire()` — reload is complete before the event returns, ensuring consumers see consistent state.

### CognitiveLoader Changes

Add an observer method:

```java
void onProfilesReloaded(@Observes CognitiveProfilesReloaded event) {
    if (store == null) return;
    int registered = 0;
    for (CognitiveDefaults defaults : event.profiles()) {
        if (defaults.vocabulary() != null) {
            store.registerVocabulary(defaults.vocabulary());
            registered++;
        }
    }
    if (registered > 0) {
        LOG.info("Re-registered vocabulary from " + registered + " profile(s) after reload");
    }
}
```

The existing `profiles` field (constructor-snapshot) is no longer needed for vocabulary — the event carries the current profiles. The field can remain for backward compatibility with any other logic that reads it, though currently none does.

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
| CDI event observer throws | Standard CDI error handling — logged, does not affect registry state (swap already complete) |

## Thread Safety

**Read path (hot):** All reads go through `volatile` fields pointing to immutable collections (`Map.copyOf()`, `List.copyOf()`). No locking. Reads see either the complete old state or the complete new state — never partial.

**Write path (rare — file change only):** The watcher's debounce executor is single-threaded, serialising all reloads. No concurrent writes. The volatile swap is the publication point.

**CDI event dispatch:** Synchronous on the watcher's debounce thread. Observers must not block indefinitely. `CognitiveLoader.onProfilesReloaded()` does lightweight in-memory work (vocabulary registration) — acceptable.

## Testing Strategy

**Unit tests:**

1. `CognitiveDefaultsRegistry.reload()` — verify volatile swap: write profiles, call reload with new profiles, verify reads return new state
2. `DeclarativeRuleRegistry.reloadGlobalRules()` — same pattern for rules
3. `CognitiveProfileWatcher` — use `@TempDir`:
   - Write initial YAML files, verify startup load
   - Modify a file, verify reload fires event with updated profiles
   - Add a new file, verify new profile appears
   - Delete a file, verify profile removed (from filesystem set; classpath baseline preserved)
   - Write invalid YAML, verify previous state preserved
4. `CognitiveLoader` observer — mock MindMapStore, fire event, verify `registerVocabulary()` called for each profile with vocabulary

**Integration notes:**

- macOS FSEvents delivers catch-up events at watcher startup (garden entry GE-20260422-a00b81). Tests must use `awaitility` polling for expected state rather than single-fire latches. Allow 1s warmup after `watchAsync()` before test mutations.
- Use `Awaitility.await().atMost(15, SECONDS)` for file-change assertions to handle platform-specific watch latency.

## References

- `cognitive-index/.../CognitiveDefaultsRegistry.java` — current classpath loading, `loadFromClasspath()`, `Map.copyOf()` pattern
- `cognitive-index/.../DeclarativeRuleRegistry.java` — global rules loading, per-agent merge-on-read
- `mindmap-intelligence/.../CognitiveLoader.java` — vocabulary registration loop
- `corpus/.../FlatChangeSource.java` — DirectoryWatcher usage pattern (debounce, overflow, daemon thread)
- `mindmap-intelligence/.../consolidation/ConsolidationScheduler.java` — daemon thread lifecycle pattern
- GE-20260422-a00b81 — Quarkus file watcher can silently stop on macOS (FSEvents limits)
- GE-20260512-523f68 — macOS catch-up events at watcher startup (testing implication)
- Project protocol: use `io.methvin:directory-watcher` for filesystem watching

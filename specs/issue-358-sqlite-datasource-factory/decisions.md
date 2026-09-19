## D1: API surface — static factory with overloaded create

**Choice:** Minimal static factory: `create(path, maxPoolSize, busyTimeoutMs, cacheSize)` with a 3-arg overload omitting cache. `migrate(ds, flywayLocation)` as a separate method. Plain utility class, no builder.
**Alternatives:**
- Builder pattern — more flexible but over-engineering for 4 parameters; YAGNI
**Rationale:** 3 of 5 stores share identical init with cache=64000. 2 stores omit cache. Two overloads cover both cases. Pool name is a one-liner only used by SqliteSnapshotStore — not worth parameterizing.
**Trade-offs:** If a 6th variation appears (e.g., different sync mode), an additional parameter or overload is needed. Acceptable at this scale.
**Sources:** SqliteMindMapStore.java, SqliteMemoryStore.java, SqliteRetrievalTracker.java, SqliteCbrRetrievalTracker.java, SqliteSnapshotStore.java — init patterns compared
**Exploration:** quick
**Status:** captured

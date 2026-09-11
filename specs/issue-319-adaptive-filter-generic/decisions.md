# Decisions — #319 AdaptiveFilter Generic

## D1: Replace RetrievedChunk-specific method with generic

**Choice:** Single generic `<T> List<T> filter(List<T>, int, AdaptiveFilterOptions<T>)` replaces the current `RetrievedChunk`-specific method entirely
**Alternatives:**
- Keep both methods (convenience overload + generic) — duplicates logic, two methods to maintain
- Interface approach (`ScoredItem`) — forces consumers to implement an interface; `ToDoubleFunction<T>` is more flexible
**Rationale:** `ToDoubleFunction<T>` is one extra argument, call sites are few (only `AdaptiveSearchWrapper` in-repo), and maintaining two methods with identical logic is pure duplication
**Trade-offs:** Slightly more verbose call sites (`RetrievedChunk::relevanceScore` must be passed explicitly)
**Sources:** `rag-api/AdaptiveFilter.java`, `rag-scoring/AdaptiveSearchWrapper.java`, issue #319 body
**Exploration:** quick
**Status:** captured

## D2: AdaptiveFilterOptions<T> for CE-aware behaviour

**Choice:** New `AdaptiveFilterOptions<T>` record bundles `AdaptiveSearchConfig` + `ToDoubleFunction<T> scoreExtractor` + optional CE behaviour (boundary predicate, cluster extension threshold)
**Alternatives:**
- Extend `AdaptiveSearchConfig` with CE fields — conflates serializable config (doubles/ints) with runtime behaviour (functions); breaks Quarkus `@ConfigMapping` consumers
**Rationale:** Keeps `AdaptiveSearchConfig` as pure data record; `AdaptiveFilterOptions<T>` is the call-site composition that adds type parameter and functional behaviour
**Trade-offs:** Two types instead of one — but they serve different layers (config vs runtime options)
**Sources:** `rag-api/AdaptiveSearchConfig.java`, engine `SearchResource.adaptiveFilter()` CE logic, issue #319 body
**Exploration:** quick
**Depends on:** D1 (generic method signature)
**Status:** captured

## D3: Module placement — rag-api

**Choice:** `AdaptiveFilterOptions<T>` lives in `rag-api` alongside `AdaptiveFilter` and `AdaptiveSearchConfig`
**Alternatives:**
- `rag-scoring` — wrong; engine consumers depend on `rag-api`, not `rag-scoring`
**Rationale:** Pure Java (record + `java.util.function` interfaces), no new deps. Engine gets direct access without pulling in `rag-scoring`
**Trade-offs:** None — clean fit
**Sources:** Module structure in CLAUDE.md
**Exploration:** quick
**Status:** captured

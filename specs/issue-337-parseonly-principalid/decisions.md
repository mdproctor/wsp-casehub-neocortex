## D1: MindMapExtractor parse/apply decomposition

**Choice:** Split `extract()` into public `parse()` + `apply()`, keep `extract()` as convenience composition
**Alternatives:**
- `parseOnly()` standalone method — duplicates context retrieval + LLM logic across two code paths
- Strategy/callback pattern — over-engineered for a two-mode operation
**Rationale:** Decomposes at the natural seam (LLM invocation vs store mutation). Callers get the parsed result and decide whether/how to persist. Makes `ParsedExtraction`, `ParsedEntity`, `ParsedRelationship`, `ParsedContradiction` public.
**Trade-offs:** Four package-private types become public API surface
**Sources:** MindMapExtractor.java:109-128, ExtractionRequestedObserver.java:44, casehubio/examples#55
**Exploration:** quick
**Status:** captured

## D2: ConversationBridge principalId type fix + confidence parameter

**Choice:** Fix `Object principalId` → `PrincipalId principalId`, add nullable `ConfidenceOrigin confidenceOrigin` parameter, wire both through to NodeInput and ExtractionRequested
**Alternatives:**
- Config object wrapper — indirection for only two fields, premature
- Overloads — proliferating signatures for a method with zero external callers
**Rationale:** Pre-release, zero external callers, broken parameter. Clean break: fix the type, add confidence control, propagate to async extraction path.
**Trade-offs:** None — no downstream consumers exist
**Sources:** ConversationBridge.java:40-77, NodeInput.java:101, MindMapConfidenceDefaults.java
**Exploration:** quick
**Status:** captured

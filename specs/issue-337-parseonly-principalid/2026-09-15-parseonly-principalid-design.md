# MindMapExtractor parse/apply + ConversationBridge principalId/confidence

**Issue:** casehubio/neocortex#337
**Module:** `mindmap-intelligence`
**Date:** 2026-09-15

## Problem

Two API gaps in `mindmap-intelligence` block the ConversationBridge path for dialogue knowledge extraction (casehubio/examples#55):

1. **MindMapExtractor.extract()** couples LLM parsing with store persistence. Callers who need only the extraction result (e.g. for per-listener node creation) get unwanted global nodes as a side effect.

2. **ConversationBridge.process()** accepts a `principalId` parameter typed as `Object` but never wires it through to node creation. Confidence is hardcoded to `ConfidenceOrigin.STATED` with no override mechanism.

## Design

### 1. MindMapExtractor — parse/apply decomposition

Split `extract()` at the natural seam between LLM invocation and store mutation:

```java
// New public method — LLM extraction without persistence
public ParsedExtraction parse(String conversationText, String tenantId,
                               List<String> recentEntityNames)

// New public method — persist a previously parsed result
public ExtractionResult apply(ParsedExtraction parsed, String tenantId)

// Existing method — becomes composition, zero behavioral change
public ExtractionResult extract(String text, String tenantId, List<String> recentEntityNames) {
    ParsedExtraction parsed = parse(text, tenantId, recentEntityNames);
    if (parsed == null) return ExtractionResult.EMPTY;
    return apply(parsed, tenantId);
}
```

**Visibility changes:** `ParsedExtraction`, `ParsedEntity`, `ParsedRelationship`, `ParsedContradiction` become `public` (currently package-private). These are pure value types with no store dependencies — safe to expose.

**`parse()` returns null** when the LLM is unavailable, the input is blank, or the response is malformed — same early-exit semantics as `extract()` today. Callers check for null.

**`apply()` is the current `applyExtraction()` made public** with no logic changes. It takes a `ParsedExtraction` and creates/updates nodes and edges in the store.

### 2. ConversationBridge — principalId and confidence

Fix the broken parameter and add confidence control:

```java
public SegmentationResult process(String cleanedText, String tenantId,
                                   List<String> recentEntityNames,
                                   PrincipalId principalId,
                                   ConfidenceOrigin confidenceOrigin)
```

**Changes:**
- `Object principalId` → `PrincipalId principalId` (fix the type)
- New parameter `ConfidenceOrigin confidenceOrigin` — nullable, defaults to `STATED` when null
- Wire `principalId` into node creation: `NodeInput.of(...).withPrincipalId(principalId)`
- Wire `confidenceOrigin` into confidence: `MindMapConfidenceDefaults.forOrigin(confidenceOrigin, Instant.now())`
- Add `principalId` field to `ExtractionRequested` record so the async extraction path can forward it

### 3. ExtractionRequested — carry principalId

```java
public record ExtractionRequested(
    String cleanedText,
    String tenantId,
    List<String> recentEntityNames,
    List<String> segmentNodeIds,
    PrincipalId principalId       // new field, nullable
)
```

`ExtractionRequestedObserver` passes the principalId through to `MindMapExtractor`. This requires that `apply()` also accept an optional `PrincipalId` to set on created nodes — add an overload:

```java
public ExtractionResult apply(ParsedExtraction parsed, String tenantId,
                               PrincipalId principalId)
```

The no-arg version delegates with `null` principalId (current behavior). The `applyExtraction` logic adds `.withPrincipalId(principalId)` to the `NodeInput` when non-null, and passes `principalId` to `EdgeInput` via its existing `principalId()` field.

## Scope

All changes are within `mindmap-intelligence`. No new modules, no new dependencies, no migrations.

**Files modified:**
- `MindMapExtractor.java` — decompose extract, make parse types public
- `ParsedExtraction.java` — visibility: package-private → public
- `ParsedEntity.java` — visibility: package-private → public
- `ParsedRelationship.java` — visibility: package-private → public
- `ParsedContradiction.java` — visibility: package-private → public
- `ConversationBridge.java` — fix principalId type, add confidenceOrigin param
- `ExtractionRequested.java` — add principalId field
- `ExtractionRequestedObserver.java` — forward principalId to apply()
- `MindMapExtractorTest.java` — add parse() and apply() tests
- `ConversationBridgeTest.java` — update signatures, add principalId/confidence tests

## Testing

- `parse()` returns `ParsedExtraction` without store mutation (verify store is empty after call)
- `apply()` with null principalId preserves current behavior
- `apply()` with non-null principalId sets it on created nodes
- `extract()` still works identically (composition test)
- `process()` with `PrincipalId` creates nodes scoped to that principal
- `process()` with null `confidenceOrigin` defaults to STATED
- `process()` with `ConfidenceOrigin.INFERRED` creates nodes at 0.7 confidence
- `ExtractionRequested` carries principalId through async path

## References

- `MindMapExtractor.java:109-128` — current extract() coupling parse + persist
- `ConversationBridge.java:40-77` — broken principalId, hardcoded confidence
- `NodeInput.java:101-103` — existing withPrincipalId() builder
- `MindMapConfidenceDefaults.java` — confidence value defaults per origin
- casehubio/examples#55 — upstream consumer that triggered this issue

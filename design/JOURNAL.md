# Design Journal — issue-137-approx-dtw-typed-cbr

## §8 Crosscutting Concepts — FeatureValue sealed hierarchy

**Decision:** Replace `Map<String, Object>` with `Map<String, FeatureValue>` across the entire CBR feature system. Seven variants: StringVal, NumberVal, RangeVal, StringListVal, NumberListVal, StructVal, StructListVal. Schema (FeatureField) provides semantics; value (FeatureValue) provides shape. Scorer dispatches on field type, pattern-matches on value — zero Object casts.

**Execution order reversed:** Spec planned #137 (DTW optimization) first, but brainstorming identified that #131 (typed features) should land first so DTW code is written once against clean types. User confirmed.

**HasMatch.subFields migrated:** `Map<String, Object>` → `Map<String, FeatureValue>`. Sub-field values use StringVal, NumberVal, RangeVal only (flat types). NumericRange stays for CbrFilter.ContainsRange (filter domain, not feature domain).

**LocalSimilarityFunction signature changed:** `compute(Object, Object)` → `compute(FeatureValue, FeatureValue)`. EXACT_MATCH constant uses FeatureValue.equals() (record structural equality).

**Qdrant serialization backward-compatible:** `_features_json` payload stays as raw JSON. Serialize FeatureValue → raw values; deserialize raw JSON + schema → FeatureValue. No collection migration needed.

## §12 Risks — Branch cleanup debt

Closed 4 orphaned branches from cross-repo sessions (issue-30, issue-56, issue-672, fix-ce-score-promotion). Root cause: engine sessions committed to neocortex branches without running work-end. Gap identified: no sweep catches branches without `.meta` that have unmerged commits ahead of main. Merged issue-672 (featureSimilarities on ScoredCbrCase) and re-applied fix-ce (CE score promotion to relevanceScore after reranking) to main.

## D1: ShorthandDefinition registration placement

**Choice:** Inline in CognitiveSchemaGenerator — build `Map<Class<?>, ShorthandDefinition>` directly in the constructor
**Alternatives:**
- Separate CognitiveShorthandDefinitions class — cleaner separation but adds a file for just 3 entries
**Rationale:** All module wiring already lives in CognitiveSchemaGenerator's constructor. Three registrations don't justify a new class.
**Trade-offs:** If more shorthand types are added later, the constructor grows — but that's a future refactor if it happens.
**Sources:** CognitiveSchemaGenerator.java:56-68, ShorthandModule.java (local), ShorthandDefinition (platform)
**Exploration:** quick
**Status:** captured

## D2: Local module unit test disposition

**Choice:** Keep ShorthandModuleTest (repointed to platform module + our definitions), delete EnumInliningModuleTest
**Alternatives:**
- Delete both — CognitiveSchemaGeneratorTest covers the integration
- Keep both, repoint to platform classes — tests platform code tested upstream
**Rationale:** ShorthandModuleTest verifies neocortex-specific definitions (Confidence, NodeRef, RecurrenceRule) produce correct schemas — those definitions are ours and worth testing. EnumInliningModuleTest tests generic platform behaviour with no neocortex-specific logic.
**Trade-offs:** Slightly less unit-level coverage for enum inlining, but CognitiveSchemaGeneratorTest.confidenceOrigin_generatesInlinedEnum already covers this path.
**Sources:** ShorthandModuleTest.java, EnumInliningModuleTest.java, CognitiveSchemaGeneratorTest.java:69-75
**Exploration:** quick
**Status:** captured

## D1: Single spec scope

**Choice:** Design all three issues (#292 schema discovery, #293 code generation, #334 adaptive extraction) as a single spec
**Alternatives:**
- #292 only — simpler scope but risks schema design choices that don't serve codegen or adaptive extraction
**Rationale:** The three issues form one flywheel — designing together ensures the schema representation works for discovery, codegen, AND guided extraction. Avoids re-opening decisions later.
**Trade-offs:** Larger spec scope; more decisions to validate at once
**Sources:** casehubio/neocortex#335 epic description (sequential dependency)
**Exploration:** quick
**Status:** captured

## D2: Schema discovery trigger — consolidation phase

**Choice:** New ConsolidationPhase (SchemaDiscoveryPhase) at @Priority(25) — after MergeDetectionPhase (@Priority(20)) so schemas reflect deduplicated entities, before CommunitySummaryPhase (@Priority(30))
**Alternatives:**
- Post-extraction inline — real-time but adds latency to every extraction and fires on too few samples
- Scheduled standalone — duplicates tenant enumeration and idle detection consolidation already handles
- Near-time event-driven accumulator — CDI events + in-memory counters; responsive but adds complexity; considered for future if idle-gating proves too slow
**Rationale:** Consolidation already iterates per-tenant, per-subgraph, has idle detection, and batches work. Schema discovery is naturally a consolidation concern — analyzing accumulated entity data to derive structural knowledge.
**Trade-offs:** Discovery is not immediate after extraction — it waits for the next consolidation cycle. Under continuous load, idle-gating (≥1 min) may delay discovery. Acceptable for v1 — the flywheel improves over time, not per-extraction.
**Sources:** ConsolidationScheduler.java, ConsolidationPhase SPI, existing phases (AccessFrequency@10, MergeDetection@20, CommunitySummary@30, CuriosityRefresh@40)
**Exploration:** quick
**Status:** revised (R1-02: phase ordering specified, near-time alternative acknowledged)

## D3: Schema consistency threshold — configurable with defaults

**Choice:** Configurable via Quarkus properties with defaults (80% property frequency threshold, min 5 samples, 95% for required flag). Designed as candidate for future CBR auto-tuning.
**Alternatives:**
- Hardcoded 80% + min 5 — simpler but inflexible
- Statistical chi-squared — rigorous but overkill for property frequency counting
**Rationale:** Properties with sensible defaults allow deployment-specific tuning without code changes. The thresholds are candidates for CBR outcome feedback auto-tuning in the future — the config-driven approach makes that transition natural.
**Trade-offs:** Adds config surface; optimal values may need empirical tuning per deployment
**Sources:** casehub.mindmap.schema-discovery.* config namespace (new)
**Exploration:** quick
**Status:** captured

## D4: Dual-path architecture — runtime data + dev-time promotion

**Choice:** Two distinct paths serving different consumers:
1. **Runtime data path:** Schema lives in type node properties. Discovery writes it. Adaptive extraction reads it. No Java interfaces involved in the flywheel loop.
2. **Promotion path:** Dev-time CLI generates Java trait interfaces from stabilized schemas. Developer reviews and commits.

Thing.as() bridges both — works with hand-written interfaces, generated interfaces, and ad-hoc interfaces.

**Alternatives:**
- Runtime code generation (ByteBuddy/ASM) — custom classloaders are messy in Quarkus; JDK Proxy via ThingProxyHandler already IS runtime code generation for typed access
- Build-time annotation processor — wrong timing; schemas don't exist at compile time
- No code generation — schema data + Thing.as() sufficient, but loses discoverability and IDE support for stable types
**Rationale:** The flywheel is a runtime data-flow system. Code generation is developer ergonomics, not flywheel mechanics. Separating the two avoids putting a human-speed bottleneck (recompile) in a machine-speed feedback loop. First-principles analysis: ThingProxyHandler already provides runtime typed access; Java interfaces add compile-time safety and discoverability for stable types only.
**Trade-offs:** Two mechanisms to understand; dynamic types lack IDE autocomplete until promoted
**Sources:** TypeRegistry.schemaFor(), ThingProxyHandler, #285 spec §1.2 ("Promotion is a conscious developer act"), GE-20260912-c4c279 (Thing trait projections)
**Exploration:** deep-analysis
**Status:** captured

## D5: Schema-enriched extraction prompt with feedback loop protection

**Choice:** Append known type schemas to the MindMapExtractor extraction prompt as structured profile data (not behavioral directives), with selective injection — only include schemas for types whose entities appear in the graph context for this conversation turn. Include an explicit instruction: "Extract all observed properties, including those not listed in known schemas."

**Feedback loop mitigation:** Schema-guided extraction creates a positive feedback loop (R1-01): the LLM preferentially extracts properties it's told about, reinforcing their frequency. Mitigation: the discovery phase tracks property provenance — `schema.{field}.source` as `java` or `discovered`. Properties discovered ONLY through guided extraction (never via open-ended extraction before schemas existed) are flagged as potentially reinforced. The CBR auto-tuning follow-on (D3) should factor this provenance into threshold adjustment.

**Alternatives:**
- Per-entity JSON schema constraint — tighter but suppresses novel property discovery
- Two-pass extraction — more thorough but costly. Token accounting makes this viable at scale (targeted calls are smaller) but adds latency and complexity for v1
**Rationale:** Profile-data approach (per GE-20260914-e3cb03) lets the LLM integrate schema knowledge emergently. Selective injection avoids bloating the prompt with irrelevant schemas. Explicit "extract all observed properties" instruction preserves novel property discovery.
**Trade-offs:** Less control over extraction fidelity; relies on LLM naturally following schema hints while still extracting novel properties. Selective injection depends on graph context containing entities of known types.
**Sources:** MindMapExtractor.SYSTEM_PROMPT, MindMapExtractor.retrieveContext(), GE-20260914-e3cb03
**Exploration:** quick
**Status:** revised (R1-01: feedback loop protection, R1-04: selective injection)

## D6: Additive schema enrichment with provenance protection

**Choice:** Schema discovery enriches schemas for ALL types, including those with Java interfaces. Java-derived schema is the baseline; discovered properties extend it. Provenance tracking prevents overwrite: each schema property carries `schema.{field}.source` = `java` | `discovered`. Discovery SKIPS fields where source=java — Java-derived schema is immutable by discovery. `schemaFor()` merges both sources, with Java fields taking precedence on any conflict.
**Alternatives:**
- Dynamic types only — avoids mixing hand-crafted and discovered schemas but misses emergent properties on known types
- Separate discovered schema namespace — cleaner audit trail but complicates schemaFor() queries
- Skip fields already present on type node (simplest) — prevents legitimate type corrections by discovery
**Rationale:** LLM extraction may discover legitimate properties beyond what hand-written interfaces define (e.g., 'department' on person nodes not in Personable). Additive enrichment with provenance protection captures this knowledge without risk of corrupting Java-derived schema.
**Trade-offs:** Extra property per schema field (source tag); schemaFor() must merge two property sets
**Sources:** TypeRegistry.schemaFor(), TypeRegistry.deriveSchemaFromInterface(), TypeRegistry.registerType() (writes schema.*.type properties)
**Exploration:** quick
**Status:** revised (R1-05: provenance tracking and overwrite protection added)

## D7: Java source output for code generation CLI

**Choice:** Generate .java interface source files matching the existing trait pattern (Personable, Belieflike)
**Alternatives:**
- YAML schema export only — lower automation, higher developer control
- Both Java + YAML — more output to manage
**Rationale:** Java source files are the most natural output for Java projects. Developer copies to the right package, reviews, commits. Follows the established pattern of existing trait interfaces.
**Trade-offs:** Generated code may need manual adjustment for naming conventions or additional methods
**Sources:** Personable.java, Belieflike.java — existing trait interface patterns
**Exploration:** quick
**Status:** captured

## D8: Extend SchemaField for guided extraction

**Choice:** Extend SchemaField with optional fields: `description` (human-readable hint for LLM prompts), `collection` (boolean, default false — distinguishes single value from list), `enumValues` (nullable List<String> — constrained values when known). Keep it a record for immutability. Backward-compatible — existing callers pass null/false for new fields.
**Alternatives:**
- Keep SchemaField minimal, enrich only in the prompt template — loses the schema-as-data principle
- Replace SchemaField with a richer SchemaProperty class — more fields than needed; over-engineering for v1
**Rationale:** SchemaField(name, type, required) is insufficient for guided extraction (R1-09). The LLM needs to know whether a property is a collection, what values are valid, and what the property means. These fields improve extraction quality while keeping the representation simple.
**Trade-offs:** Changes SchemaField signature — all callers of the constructor need updating (deriveSchemaFromInterface, schemaFor, registerType)
**Depends on:** D4 (runtime data path uses SchemaField), D5 (guided extraction prompt reads SchemaField)
**Sources:** SchemaField.java (mindmap-api), TypeRegistry.deriveSchemaFromInterface(), R1-09 (implicit decision from decision review)
**Exploration:** quick
**Status:** captured

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

**Choice:** New ConsolidationPhase (SchemaDiscoveryPhase) running alongside existing phases
**Alternatives:**
- Post-extraction inline — real-time but adds latency to every extraction and fires on too few samples
- Scheduled standalone — duplicates tenant enumeration and idle detection consolidation already handles
**Rationale:** Consolidation already iterates per-tenant, per-subgraph, has idle detection, and batches work. Schema discovery is naturally a consolidation concern — analyzing accumulated entity data to derive structural knowledge.
**Trade-offs:** Discovery is not immediate after extraction — it waits for the next consolidation cycle
**Sources:** ConsolidationScheduler.java, ConsolidationPhase SPI, existing phases (AccessFrequency, MergeDetection, CommunitySummary, CuriosityRefresh)
**Exploration:** quick
**Status:** captured

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

## D5: Schema-enriched extraction prompt

**Choice:** Append known type schemas to the MindMapExtractor system prompt as structured profile data (not behavioral directives). E.g. "Known type schemas: meeting: {date: string (required), attendees: string, agenda: string}".
**Alternatives:**
- Per-entity JSON schema constraint — tighter but suppresses novel property discovery
- Two-pass extraction — more thorough but doubles LLM calls
**Rationale:** Profile-data approach (per GE-20260914-e3cb03) lets the LLM integrate schema knowledge emergently through its existing extraction behavior. The LLM naturally extracts known properties when it classifies an entity as a known type, while remaining free to discover new properties.
**Trade-offs:** Less control over extraction fidelity than constrained or two-pass approaches; relies on LLM naturally following schema hints
**Sources:** MindMapExtractor.SYSTEM_PROMPT, GE-20260914-e3cb03 (profile data over prose directives)
**Exploration:** quick
**Status:** captured

## D6: Additive schema enrichment for all types

**Choice:** Schema discovery enriches schemas for ALL types, including those with Java interfaces. Java-derived schema is the baseline; discovered properties extend it without modifying the Java interface.
**Alternatives:**
- Dynamic types only — avoids mixing hand-crafted and discovered schemas but misses emergent properties on known types
- Separate discovered schema namespace — cleaner audit trail but complicates schemaFor() queries
**Rationale:** LLM extraction may discover legitimate properties beyond what hand-written interfaces define (e.g., 'department' on person nodes not in Personable). Additive enrichment captures this knowledge without disrupting existing interfaces.
**Trade-offs:** schemaFor() returns a mix of Java-derived and discovered fields; must avoid overwriting Java-derived schema
**Sources:** TypeRegistry.schemaFor(), TypeRegistry.deriveSchemaFromInterface()
**Exploration:** quick
**Status:** captured

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

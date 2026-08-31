# Graph Reasoning Exploration — Feasibility Assessment

**Issue:** casehubio/neocortex#245
**Type:** Exploration / spike
**Verdict:** Do NOT integrate DesiredState graph engine with MindMap.
Extend MindMapAnalyzer instead.

## Systems Compared

### DesiredState Graph (engine repo)

**Data model:** `ImmutableDesiredStateGraph` — directed acyclic graph
with dual adjacency maps (forward + reverse). Nodes are `DesiredNode`
(NodeId, NodeSpec, HumanGating). Edges are `Dependency(from, to)` with
provisioning semantics — "from depends on to" means "provision to
before from."

**Capabilities:**
- `dependenciesOf(node)` / `dependentsOf(node)` — forward/reverse adjacency
- `roots()` / `leaves()` — nodes with no deps / no dependents
- Cycle detection (DFS) with `CyclicDependencyException`
- Path finding (BFS) — private, used internally for cycle reporting
- `overlay()` — merge two graphs with conflict detection
- `connect()` — connect leaves of one graph to roots of another
- `filterByTypes()` — filter graph to specific node types
- `GraphRuleEngine` — iterative rule evaluation with pattern matching,
  graph mutation, convergence detection, conflict detection
- Immutable — every mutation returns a new instance

### MindMap (neocortex repo)

**Data model:** General semantic graph. Nodes are `MindMapNode` (name,
traits, PAD, confidence, temporal bounds, NodeRef, properties). Edges
are `MindMapEdge` (sourceNodeId, targetNodeId, edgeType, confidence,
PAD, properties). Edges are typed ("knows", "works-at", "parent-of")
and potentially cyclic (Alice knows Bob, Bob knows Alice).

**Existing graph analysis (`MindMapAnalyzer`):**
- `orphanNodes()` — nodes with no edges
- `degreeCentrality()` — edge count per node
- `betweennessCentrality()` — Brandes' algorithm, BFS-based
- `subgraphDensity()` — edge-to-node ratio
- `unvalidatedEdgeRatio()` — data quality metric
- `contradictions()` — conflicting edges of the same type
- `lowConfidenceCluster()` — per-subgraph confidence analysis
- `staleNodes()` — temporal freshness
- `DerivedEdgeDecorator` — forward-chaining rule engine on addEdge

## Fundamental Mismatch

DesiredState operates on a **directed acyclic dependency graph** with
provisioning semantics. MindMap operates on a **general semantic
knowledge graph** with typed, potentially cyclic edges.

| Dimension | DesiredState | MindMap |
|-----------|-------------|---------|
| Graph type | DAG (acyclic enforced) | General graph (cycles meaningful) |
| Edge semantics | Dependency (ordering) | Relationship (typed, semantic) |
| Node model | NodeSpec + HumanGating | Name, traits, PAD, temporal bounds, properties |
| Cycle handling | Prevention (throws) | Acceptance (knows ↔ knows is valid) |
| Mutation model | Immutable + version | Mutable store SPI |

An adapter mapping MindMap → DesiredStateGraph would:
1. **Lose information** — edge types, confidence, PAD, temporal bounds,
   traits, properties have no DesiredNode/Dependency equivalent
2. **Fight cycles** — DesiredState rejects what MindMap requires
3. **Mismatch direction** — DesiredState edges are directed with
   ordering semantics; MindMap edges are bidirectional relationships

## Use Case Assessment

### "Find all paths between Alice and Project X"

DesiredState has BFS `findPath()` but it's private, DAG-only, and
single-path (for cycle reporting). MindMap needs all-paths or
all-shortest-paths on a general graph.

**Verdict:** Implement directly on MindMap. BFS on `neighbors()` is
~30 lines. DesiredState's path finding is the wrong algorithm for the
wrong graph type.

### "What entities are transitively connected to this upcoming event?"

Simple BFS/DFS reachability from a starting node. DesiredState's
`dependenciesOf()` is directed — MindMap traversal follows edges in
both directions via `neighbors()`.

**Verdict:** Implement directly on MindMap. BFS reachability is ~20
lines.

### "Which knowledge areas are well-connected vs isolated?"

**Already done.** MindMapAnalyzer has `subgraphDensity()`,
`orphanNodes()`, `degreeCentrality()`, `betweennessCentrality()`.
DesiredState's "convergence" is about rule iteration convergence, not
graph connectivity.

### GraphRuleEngine for MindMap rules

The iterative pattern-matching + mutation + convergence model is
architecturally interesting. MindMap's `DerivedEdgeDecorator` is
simpler (one-shot forward chaining). Could GraphRuleEngine enhance
multi-hop MindMap inference?

**Verdict:** MEDIUM potential but wrong timing. DerivedEdgeDecorator
handles current needs (max depth 3, single-pass). Multi-hop inference
rules would need a fundamentally different MindMap rule model before
the engine would be useful. Revisit when MindMap rules outgrow
DerivedEdgeDecorator.

## Recommendation

**Do not integrate DesiredState's graph engine with MindMap.** The
type-level incompatibility, cycle semantics mismatch, and information
loss make the adapter effort high and the payoff negative.

**Instead, extend MindMapAnalyzer** with the missing graph queries:

| Query | Algorithm | Effort |
|-------|-----------|--------|
| `findPaths(nodeA, nodeB, maxDepth, tenantId)` | BFS all-shortest-paths | S (~30 lines) |
| `reachableFrom(nodeId, maxDepth, tenantId)` | BFS with depth limit | S (~20 lines) |
| `connectedComponents(subgraphId, tenantId)` | Union-find or BFS | S (~40 lines) |

These use `neighbors()` directly — no adapter, no information loss,
cycle-safe by default. Total effort: S, implementable in a single
session alongside other Phase 4 work.

**GraphRuleEngine integration:** Park for future consideration. The
trigger is when DerivedEdgeDecorator's single-pass forward chaining
becomes insufficient for complex multi-hop inference patterns. Not
expected in the current roadmap horizon.

## References

- `ImmutableDesiredStateGraph.java` — DAG implementation with cycle detection, path finding
- `GraphRuleEngine.java` — iterative rule evaluation with convergence
- `DesiredStateGraph.java` — graph API (dependenciesOf, dependentsOf, roots, leaves)
- `Dependency.java` — directed dependency edge
- `MindMapAnalyzer.java` — existing graph analysis (betweenness centrality, density, orphans)
- `DerivedEdgeDecorator.java` — current MindMap rule engine (forward-chaining)
- `MindMapStore.java` — neighbors() API for traversal
- cognitive-architecture-roadmap.md §4c — roadmap definition

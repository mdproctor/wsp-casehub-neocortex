# Position A: Unified Cognitive Query Engine

Replace disconnected types with a single CognitiveQueryEngine + compositional query builder.

## The Argument

The four query dimensions of cognitive-index — subject, perspective, temporal scope, and domain scope — are orthogonal. The current codebase fixes each dimension inside a separate type: CognitiveProfile resolves entities without perspective, PerspectivalResolver applies perspective without resolving memories, TemporalIndex builds timelines without entity context, AffectTrajectoryAnalyzer computes trajectories without knowing what entity or perspective produced them. A caller who needs any novel combination must orchestrate multiple calls and manually assemble results. This is not a design — it is an accident of incremental delivery.

The right fix is a single compositional query engine: one CDI bean (CognitiveQueryEngine), one query builder (CognitiveQuery), one sealed result hierarchy. The query builder composes orthogonal dimensions; the engine executes the composed plan against whichever stores are available.

## Why composition belongs in one engine

Each existing type duplicates the same store-resolution boilerplate. CognitiveProfile, PerspectivalResolver, and TemporalIndex all inject Instance<MindMapStore> with identical graceful-degradation guards. The engine consolidates this: one set of store references, one degradation policy.

More fundamentally, the query dimensions interact. Perspective changes what data you see: Alice's overlay on Grandma carries different PAD values than the shared node, which changes the trajectory computation. Subgraph scope restricts which memories are relevant, which changes entity resolution. These interactions are not additive — you cannot apply perspective as a post-filter over a perspective-unaware entity resolution. The current code proves this: CognitiveProfile.resolve() returns EntityKnowledge with a raw MindMapNode, and a caller who then applies PerspectivalResolver gets a merged node but the trajectory was already computed from the unmerged PAD. The result is incoherent. The engine fixes this by ensuring perspective is applied before trajectory computation, within a single execution plan.

## Why Position B fails

Making perspective a cross-cutting dimension on every existing type treats the symptom. It solves #271 for entity resolution but not for temporal queries. It gives you CognitiveProfile with perspective and TemporalIndex with perspective but not a perspectival temporal view scoped to a subgraph. Every new combination requires touching every type. With four dimensions and multiple values per dimension, the surface area is N×M and growing — and the interaction bugs persist because each type still owns its own execution logic.

## Why Position C fails

Adding more focused compositions treats each feature request as a new class. This is how cognitive-index got to its current state. The module has 36 source files already, and we are two features away from needing four more types. Each new combination is a new class with its own store injection, its own degradation logic, its own test surface. The module becomes a combinatorial catalog, not an architecture.

## Addressing weaknesses

**God class risk.** The engine is not a monolith — it is an orchestrator. Pure computations (PerspectivalMerge, AffectTrajectoryAnalyzer) remain as they are. The execution logic that today lives in three classes (~180 lines total) collapses into a single method that builds an execution plan from the query dimensions.

**Migration cost.** 7 call sites total. Existing types can be retained as thin facades during migration.

**Testing complexity.** Orthogonal dimensions mean isolated dimension tests + targeted interaction tests. Existing utility tests unchanged.

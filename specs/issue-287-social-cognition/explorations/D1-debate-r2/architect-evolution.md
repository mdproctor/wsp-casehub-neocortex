# Proposal 3: Signal-Producer Model (Evolution Resilience Lens)

## Core Change

Three-layer architecture: Resolve → Produce → Compose.

**ResolvedContext** — holds perspectivally-merged node(s), edges, memories. Multi-agent from the start (agentIds list). Resolution applies PerspectivalMerge per agent before any computation.

**CognitiveSignal** — sealed interface. AffectTrajectory, PerspectivalDivergence, TemporalCorrelation are all signals. Each carries source metadata.

**SignalProducer<T extends CognitiveSignal>** — CDI-discovered SPI. Each implementation produces one signal type from ResolvedContext. @DependsOn annotation for topological ordering.

**CognitiveView** replaces EntityKnowledge — holds ResolvedContext + Map<Class<Signal>, List<Signal>>. Open by construction.

## How #271 and #283 Land

**#271:** PerspectivalDivergenceProducer receives N merged views, computes divergence. No existing code modified.

**#283:** TemporalCorrelationProducer correlates temporal patterns across subgraphs. PrincipalScope on query ensures privacy.

## Extension Points

Future features are: new sealed permit + new producer implementation. CDI discovers them automatically.

- EmotionalContagion: new producer consuming multi-agent trajectories
- CoalitionDetection: new producer consuming divergence signals
- TrustDynamics: new producer over relationship memories + AgentTrustProvider

Each is additive. Nothing existing is modified.

## Key Argument

The evolution test: can a developer add emotional contagion by adding new types without modifying existing types? This architecture passes that test.

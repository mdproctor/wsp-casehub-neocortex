# Handoff — 2026-07-06

## What Changed

Fixed #114: `@Decorator` silently skipping `@Produces` method beans. Root cause: Arc applies decorators via subclass generation — producer method beans get client proxies that can't be subclassed. Converted `HybridCaseRetriever` and `ReactiveHybridCaseRetriever` from `@Produces` method beans to `@ApplicationScoped` managed beans with `@Inject` constructors. Also added `@Unremovable`, FINE logging, and `@QuarkusTest` integration test to both expansion decorators. Branch `issue-114-harden-decorator-activation`, 2 commits (`ec5fe25`, `5c9fb00`). Full build green, installed to local `.m2`.

*Updated: #114 closed and branch stamped — removed stale next step.*

## Immediate Next Step

Pick next work item from What's Next — `#109` (retrieval tracking analysis) and `#110` (retention policy) are unblocked now that #105 landed.

## Cross-Module

**We're blocking:**
- `Hortora/engine` — needs the new neocortex SNAPSHOT (`0.2-SNAPSHOT`) to pick up the managed-bean fix. Their `QueryExpansionTest` passes; dev-mode interception will work once they rebuild against the updated SNAPSHOT.

## What's Left

*Unchanged — `git show HEAD~1:HANDOFF.md`*

## What's Next

*Unchanged — `git show HEAD~1:HANDOFF.md`*

## Key References

- Garden: `GE-20260706-a4d5b0` — gotcha: Arc decorators skip @Produces method beans
- Garden: `GE-20260706-cda843` — undocumented: BuildTimeEnabledProcessor scans full combined index
- Blog: `blog/2026-07-06-mdp03-the-decorator-that-registered-but-never-fired.md`

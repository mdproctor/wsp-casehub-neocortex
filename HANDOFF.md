# Handoff — 2026-06-09

## What Changed

C7 (RAG Pipeline) — **DONE**. #7 closed. Four modules shipped: `rag-api` (CorpusStore + CaseRetriever SPIs), `rag` (unified Qdrant gRPC client, hybrid dense+sparse with RRF fusion, configurable TenancyStrategy, `MemoryPermissions.assertTenant()` defense-in-depth), `rag-tika` (optional Apache Tika parsing), `rag-testing` (in-memory stubs). Dropped `langchain4j-qdrant` — LangChain4j #4994 (Qdrant hybrid) still open. Qdrant client bumped 1.9.1→1.18.1 (Query API). ARC42STORIES.MD synced (C7 ✅, L6+L7 populated). Blog published (mdp04). 5 garden entries submitted. All J1+J2 journeys complete — C1–C7 ✅.

#11 (Reactive CorpusStore + CaseRetriever) — **In progress.** Branch `issue-11-reactive-rag-spis` scaffolded in both project and workspace. No implementation commits yet.

## Immediate Next Step

Continue #11 (`issue-11-reactive-rag-spis`) — reactive variants of `CorpusStore` and `CaseRetriever` SPIs, build-gated per `reactive-service-build-gating` protocol. Run `/work` to resume.

## What's Left

- **#11 Reactive RAG SPIs** — `ReactiveCorpusStore` + `ReactiveCaseRetriever`, build-gated — branch active, no code yet · M · Med
- **#12 LangChain4j #4994 migration** — when upstream ships Qdrant hybrid search natively · S · Low

## Key References

- ARC42STORIES.MD: C1–C7 ✅ — all chapters complete; #11 not yet captured
- Spec: `docs/specs/2026-06-08-rag-pipeline-design.md`
- Blog: `blog/2026-06-09-mdp04-rag-pipeline-unified-qdrant.md`
- Garden: GE-20260609-521cca (Qdrant Filter is Common.Filter), GE-20260609-26ffa5 (CDI POJO+Produces ambiguity), GE-20260609-c1998e (rrf() vs fusion()), GE-20260609-2a92d9 (Tika artifact), GE-20260609-2abdfd (Query API version)

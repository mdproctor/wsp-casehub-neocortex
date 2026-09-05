---
layout: post
title: "Whose Memories Are These?"
date: 2026-09-05
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [memory, visibility, identity, subject, cbr]
series: issue-277-principal-scoped-visibility
---

# Whose Memories Are These?

The memory subsystem had a blind spot. Every memory in a tenant was visible to every query. Alice's private observation about Bob? Bob could see it. An agent's internal reasoning about a sensitive interaction? Any other agent in the same tenant could read it.

This isn't a permissions bug — it's a missing concept. The stores had no notion of ownership, no vocabulary for "this belongs to me" versus "this is shared knowledge." The tenant boundary was the only wall, and inside it, everything was transparent.

## Subject — Naming What You're Talking About

The first problem was simpler than visibility: `entityId` was a bare `String`. It answered "who is this memory about?" with an opaque identifier that carried no type information. Is `"alice"` a person, an agent, a project? The code couldn't say.

`Subject(type, id)` fixes this. The type is a free-form string — not an enum — because the LLM discovers new entity types at runtime. Today it's `"person"` and `"agent"`. Tomorrow it might be `"research-topic"` or `"incident"`. The type vocabulary grows as the agent learns. Lowercase normalization on construction prevents `"Person"` and `"person"` from becoming phantom type splits.

This is a reference to a Thing — the formal dynamic type system tracked in #278. When that lands, `Subject` becomes `Thing.ref()`. The `(type, id)` pair is already compatible.

## Three States of Visibility

The model landed on three natural states:

| State | principalId | sharedWith | Who sees it |
|---|---|---|---|
| Truly shared | null | empty | Everyone in the tenant |
| Private | "alice" | empty | Only Alice |
| Owned + shared | "alice" | {"bob"} | Alice and Bob |

Null `principalId` means truly shared — backward compatible with all existing data. No behaviour change for code that doesn't set visibility fields.

The filtering predicate is four lines:

```java
if (callerPrincipalId == null) return true;
if (memoryPrincipalId == null) return true;
if (memoryPrincipalId.equals(callerPrincipalId)) return true;
return sharedWith != null && sharedWith.contains(callerPrincipalId);
```

Null caller sees everything. Null owner means shared. Owner match. SharedWith contains. That's the entire visibility model.

## Where the Filter Lives

I considered a decorator — one central filter wrapping all stores. It would have been DRY. It would also have broken `LIMIT` semantics for SQL stores. A decorator fetches N results, filters some out, returns fewer than requested. The SQL stores can push the predicate into the `WHERE` clause before `LIMIT`, returning the correct count every time.

So each store implements filtering in its own query language. SQLite gets a `WHERE` clause with `json_each(shared_with)`. JPA gets native SQL with the same pattern. Qdrant gets payload filters. Mem0 and Graphiti — REST-backed, no server-side filtering possible — apply the predicate as a post-filter after results come back. The spec acknowledges this asymmetry: post-filter truncation is an inherent limitation of REST adapters, acceptable because semantic search relevance degrades past the first few results anyway.

The shared `MemoryVisibility.isVisible()` utility gives the in-memory store and post-filter stores a single implementation. Seven contract tests enforce identical behaviour across all five backends.

## Erase Is Visibility-Unaware

One deliberate asymmetry: you can't read someone else's private memories, but a tenant admin can erase them. Read visibility is a cognitive concern. Erasure is a compliance concern — GDPR Art.17 doesn't care who created the data.

## What This Opens

The CBR subsystem gained the same fields — `callerPrincipalId` on `CbrQuery`, visibility on stored cases. An agent's case-based reasoning now respects whose cases it's drawing from.

The deprecated `entityId` shims still compile — hundreds of callers across test code haven't migrated yet. The shims delegate correctly; the cleanup is mechanical and can happen at any pace. The functional model is complete.

What's genuinely interesting is what comes next. The visibility model is within-tenant only. Cross-tenant memory sharing — a family where Alice and Bob are in different tenants but share certain knowledge — remains the open design question from the shared-memory-design doc. The within-tenant layer had to exist first. Now it does.

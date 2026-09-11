---
layout: post
title: "Context on the Wire"
date: 2026-09-11
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [rag, spi, feedback, retrieval-tracking]
series: issue-306-collection-compat-tests
---

# Context on the Wire

The retrieval feedback pipeline had a gap. `RetrievalTracker.feedback()` accepted three bare parameters — retrievalId, sourceDocumentId, outcome — and threw away everything the caller knew about *why* this retrieval mattered. The same document might be essential for one issue and irrelevant for another, but the SPI couldn't distinguish.

The interesting question wasn't whether to add context — it was how much. I started with "just issue fields" (issueRepo + issueNumber) since that's what `GardenMcpTools` already has at the call site. But that felt too narrow. The next caller would have an agentId, or a session identifier, or a work phase. Every new dimension would break the SPI.

The answer was already in the codebase. `MemoryInput`, `ExperienceEvent`, `CbrQuery` — they all follow the same pattern: typed fields for the high-value dimensions you know about, plus a `Map<String, String>` attributes map for everything else. `FeedbackAttributeKeys` provides the standard key constants, same as `ExperienceAttributeKeys`. The typed fields get indexed SQLite columns; the map gets a JSON TEXT column.

The SPI evolution used a default method bridge — the new 4-param `feedback()` is the primary method, and the old 3-param signature delegates with null context. Zero breakage for existing callers and implementors.

One surprise: `rag-api` is a zero-deps module. No `jakarta.annotation` on the classpath, so the `@Nullable` annotations I'd planned for `FeedbackContext` couldn't compile. I dropped them — nullability is conveyed by the spec, not the annotation. A 4-arg convenience constructor on `RetrievalFeedback` handled backward compatibility for all the existing test call sites.

The V2 Flyway migration adds `issue_repo`, `issue_number`, and `attributes` columns to `retrieval_feedback` with a composite index. Jackson handles JSON serialization — the same `toJson()`/`fromJson()` helper pattern from `SqliteMemoryStore`.

Two follow-ups filed: #317 for SQL-level context filtering when data volume warrants it, #318 for context-aware slicing in `RetrievalAnalyzer`. Both are genuine YAGNI right now — no caller needs them yet, and the post-filter pattern matches what `documentStats()` already does.

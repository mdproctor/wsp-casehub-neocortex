---
layout: post
title: "165 Lines of Duplication, Two Lines Each"
date: 2026-09-19
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [refactoring, sqlite, infrastructure]
---

# 165 Lines of Duplication, Two Lines Each

Five SQLite stores, each with ~20 lines of identical init: `:memory:` detection, SQLiteConfig WAL setup, HikariConfig pool sizing, Flyway migration. The only differences were the config property prefix and the Flyway migration location. Two stores had minor variations — one omitted cache size, one hardcoded pool size at 3 instead of 5.

I extracted `SqliteDataSourceFactory` into a new `sqlite-support` module with two overloaded `create()` methods (with and without cache size) and a `migrate()` method. Each store's init block went from ~20 lines to 2. The diff was satisfying: 37 additions, 202 deletions.

The interesting variation was `SqliteCbrRetrievalTracker`, which splits its init between a constructor (DataSource) and `@PostConstruct` (Flyway). The factory handles this naturally — `create()` in the constructor, `migrate()` in `@PostConstruct`. No special casing needed.

The net result is that adding a sixth SQLite store now requires two lines of init code and a single dependency on `sqlite-support`, rather than copying and adapting 20 lines from another store.

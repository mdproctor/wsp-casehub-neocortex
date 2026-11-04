---
layout: post
title: "Names Are Not Identity"
date: 2026-11-03
entry_type: article
subtype: diary
projects: [casehubio/neocortex]
tags: [entity-references, tokenisation, cognitive-architecture, knowledge-representation]
---

# Names Are Not Identity

Every cognitive system that stores memories about people hits the same problem eventually: names are baked into the text.

"Frida painted a self-portrait." That string lives in a memory store, gets retrieved by embedding similarity, gets rendered into an agent prompt. Everything works. Until Frida changes her name. Or until you want to reuse the same cognitive profile in a different context where that entity is called something else. Or until two entities share a name and the system can't distinguish them.

The string "Frida" is a surface form — a rendering of identity at a point in time. The entity is the thing behind the name: a node in a knowledge graph, a persistent identity with properties, relationships, and history. Conflating the two seems harmless at first. It becomes structural debt the moment you need to rename, merge, or recontextualise anything.

## The Practical Damage

This isn't a theoretical elegance concern. In a cognitive AI system like neocortex, literal names leak through every layer of the pipeline:

**Memory storage.** When an agent records "Alice told Bob about the project," those literal strings are stored as the memory's text. Embedding retrieval finds it. But no part of the system knows that "Alice" in this memory refers to the same entity as "Alice" in a separate knowledge graph node, or that "Alice" in one tenant context is a different entity from "Alice" in another.

**Prompt rendering.** Cognitive prompt sections render entity knowledge into the agent's system prompt. Edge relationships come through as raw node UUIDs — `"knows → 7f3a2b1c-..."` — because the prompt section has a node ID but no mechanism to resolve it to a human-readable name.

**Biography import.** Character biographies contain entity names throughout — goal names like "Protect Clara Bellingham from all dangers," relationship display names, life-event subjects. Every text field that mentions another entity does so by literal string.

The problem isn't just names. It's places ("Mexico City", "CDMX", "Ciudad de México"), organisations ("The Ant Hill Mob", "the mob"), artworks ("The Mona Lisa", "La Gioconda"), concepts ("Continental System", "the blockade"). Anything with a name that appears in text in multiple surface forms.

## The Wrong Answer: Standoff Annotations

I built the wrong thing first. The NLP literature pointed toward standoff annotations — store the text unchanged, maintain a parallel index of character offsets linking text spans to entity node IDs. The annotation infrastructure was mature: `EntityAnnotationIndex` SPI, SQLite and in-memory backends, lifecycle observers that automatically repoint annotations on entity merge and clean up on erasure. Biography import used it. The extraction pipeline used it. It worked.

It also required:
- A parallel data store to keep in sync with every text change
- Character offset arithmetic that breaks when names change length
- Lifecycle observers (`MergeRepointObserver`, `MemoryEntityErasedObserver`) purely to maintain sync between two representations of the same information
- A batch query SPI (`findBySource`) and a resolution utility (`EntityReferenceResolver`) with right-to-left offset substitution logic
- Every query that asks "which entities does this memory mention?" routing through an index join instead of reading the text

The complexity existed to preserve one property: **the original text stays unchanged.** But that property costs more than it's worth when the actual need is simpler.

## The Right Answer: Inline Tokenisation

The real requirement is: entity names in text should resolve to current canonical names at render time. That's a tokenisation problem, not an annotation problem.

Replace the name with a token that carries identity, variant, and the original surface form:

```
{{person_001:full:Clara Bellingham}} walked to the park.
She told {{person_002:first:Bob}} about the project.
They visited {{place_001:short:CDMX}} together.
```

The token format is `{{entity_id:variant:surface_form}}`. At render time, the renderer looks up `person_001` in the entity record, checks the variant (`full`, `first`, `short`, `pronoun:subject`), and resolves to the current canonical form. If Clara Bellingham was renamed to Penelope Pitstop, every `full` token renders the new name. The stored text doesn't change — the token is stable, the resolution is dynamic.

Multi-word names aren't a problem — the surface form extends to the closing `}}`. Pronouns work the same way: `{{person_001:pronoun:subject:She}}` — the renderer keeps "She" (pronouns don't change on rename unless the entity's pronouns change), but the system knows who "She" refers to.

## The Entity Record

For tokenisation to work, entities need structured identity — not just a single `name()` string. An entity record decomposes the name into parts and declares all known surface forms:

```yaml
person_001:
  type: person
  canonical:
    full: "Jane Doe"
    first: "Jane"
    last: "Doe"
    title_prefix: "Dr"
  pronouns:
    subject: "she"
    object: "her"
    possessive: "her"
    reflexive: "herself"
  preferred_short: "Jane"
  preferred_long: "Dr Jane Doe"
  aliases: ["JD", "Jane D."]
```

The variant taxonomy covers the ways a name appears in text:

| Variant | Meaning |
|---------|---------|
| `full` | Full name as written |
| `first` | Given name |
| `last` | Family name |
| `title` | Title + name |
| `preferred_short` | Entity's preferred short form |
| `preferred_long` | Entity's preferred long form |
| `pronoun:subject` | Subject pronoun |
| `pronoun:object` | Object pronoun |
| `pronoun:possessive` | Possessive |
| `other` | Nickname, initials, epithet |

This extends naturally to any entity type. Places get `short` and `formal` (original language). Organisations get `abbreviation`. Artworks get `formal` for the original-language title. The token format and lookup table are universal.

## Fast Lookup via Surface Form Table

At write time, the tokeniser needs to recognise any surface form and map it to an entity. A flat lookup table makes this fast:

| surface_form | entity_id | variant | tenant_id |
|---|---|---|---|
| Jane Doe | person_001 | full | t1 |
| Jane | person_001 | first | t1 |
| Dr Jane Doe | person_001 | preferred_long | t1 |
| JD | person_001 | other | t1 |
| Mexico City | place_001 | full | t1 |
| CDMX | place_001 | short | t1 |
| La Gioconda | thing_001 | formal | t1 |

The table is derived from entity records — rebuilt when an entity changes. The tokeniser scans text against the table, longest match wins. One lookup per candidate phrase.

At read time, "which entities does this text mention?" is a regex scan for `{{entity_id:` patterns — no index query, no join. `EntityTokens.entityIds(text)` returns the set. The three cognitive consumers that previously queried the annotation index (`EntityOverlapModulationFactor`, `EntityAwareSalienceStrategy`, `LlmReflectionSynthesizer`) become one-liners.

## Why This Matters

Entity tokenisation is the foundation for capabilities that literal names make impossible:

**Profile reuse.** A cognitive profile describes *how* an agent thinks, not *who* it thinks about. With tokens, the same profile operates in different contexts where entities have different names. No search-and-replace across thousands of stored memories.

**Entity merging.** "Dr. Smith" and "Professor Sarah Smith" turn out to be the same person. Find-and-replace `{{person_042` with `{{person_001` in stored text. One operation, complete. No parallel index to reconcile.

**Search.** "Find all memories about Mexico City" → search for `{{place_001`. Exact match. No embedding similarity, no missing "CDMX" because the vector didn't associate it with "Mexico City."

**Rename cascades.** Change an entity's preferred name → every token renders the new value at read time. No text changes, no backfill, no migration.

## What I Learned

I built standoff annotations first because the NLP literature recommended them and the architecture seemed elegant — original text preserved, annotations as a composable layer. But the elegance created a coordination problem: two systems to keep in sync, lifecycle observers to maintain consistency, offset arithmetic that breaks on length changes.

The simpler design — a token in the text that carries identity and variant — eliminates the coordination problem entirely. The token IS the reference. One system, one source of truth.

Sometimes the right design is the one that makes the hard problems disappear rather than the one that solves them elegantly.


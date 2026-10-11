---
title: "You Can't Parameterise Taste"
date: 2026-10-11
author: mdp
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [goals, motivation, taxonomy, cognitive-model, affinity]
status: draft
---

The Frida Kahlo extraction pipeline hit its targets — 276 entities, 138 goals, 57 formative experiences, all up from a baseline that had zero goals in the first import. The numbers are good. What's more interesting is what the numbers revealed about the model's blind spots.

## The goal taxonomy gap

The 138 goals had no classification system. "Build emotional resilience" and "carry a pregnancy to term" looked identical in the data — both thematic, both active. An audit agent flagged the first as "noise" because it sounded like self-help language. But it *is* a goal. The problem wasn't the extraction; it was that we had no vocabulary for distinguishing what *kind* of goal it was.

That sent me into the psychology literature. Talevich, Read, Walsh, Iyer & Chopra (2017) built a 5-level taxonomy of 161 human motives — empirically derived from card-sort data, not armchair theorising. The top level splits into three superordinate clusters: Meaning, Communion, Agency. Below that, nine content domains: morality, religion, self-actualisation, avoidance, social relating, health, family, mastery, financial. Every goal fits somewhere.

The title of the taxonomy paper is "Toward a comprehensive taxonomy of human motives" — and it uses the word *motives*, not goals, deliberately. Motives are what drives goals. Goals are the observable surface. Our model had drives (curiosity, competence, affiliation, autonomy) but nothing connecting them to specific content domains. A high-mastery agent wants to master *something* — but what?

## The affinity problem

This is where it got philosophically interesting. Disposition profiles predict the *shape* of motivation — which categories are likely strong. But they can't predict the content. I was born in 1975 and became obsessed with computers at age seven, before anyone in my family or social circle had one. You can trace contributing factors: male, probably high on openness and systematic thinking, which clusters toward technical domains. But those same factors could have produced an obsessive chess player or a watchmaker. The disposition narrowed the search space; the specific attachment was irreducible.

We talked through three pathways to caring about something:

**Seeded** — pre-experiential attractions. The child who picks up every insect before anyone taught them to care about insects. Initial conditions, not caused by anything in the agent's history.

**Acquired** — competence-driven feedback loops. You're good at it, success feels good, mastery drive reinforces. Computers are almost unfairly reinforcing here — the feedback cycle is milliseconds. Write code, run it, it works or it doesn't. Compare that to woodworking (days) or music (weeks before you sound decent). The feedback speed selects for specific personality profiles.

**Borrowed** — transferred from relationships or social context. Chess bonded to your father through every game you played together. The game's value is borrowed from the relationship. If the relationship fades, the attachment might dissolve — unless competence lock-in has taken over.

The cognitive model already has machinery for the second and third pathways. CBR outcome feedback handles competence loops. MindMap edges with affect trajectories handle association. What's missing is the first: the seed layer.

## You can't parameterise taste

For biographical agents, this isn't a problem. The biography *is* the seed — it tells you Frida chose painting, loved La Casa Azul, her taste ran to folk art and visceral self-portraiture. The extraction pipeline captures the resolved reality.

For synthetic agents, there's a gap. The disposition profile says *how* the agent processes. Nothing says *what* it reaches for when nothing is pushing it. A high-mastery agent with no content seeds is a personality without history — the drives fire but have nothing to latch onto.

The design principle we landed on: **derive the shape, observe the content.** The derived layer produces a probability distribution over motivational domains. The seed layer (or early experience) resolves the distribution to specific outcomes. The affinity profile YAML declares domain-level attractions — "drawn to systematic-technical domains" — and either the author resolves it to specific content ("computers") or the environment does through exposure and competence feedback.

The modelling limit is honest: you can parameterise the engine but you can't parameterise taste. Taste is input data, not output of computation. And that's fine — humans work the same way.

## What this opens up

The Talevich taxonomy gives us a grounded vocabulary that connects the drive system (which categories are strong) to goal content (what specific domain). The Emmons framework adds a motivation origin dimension (intrinsic/identified/introjected/external) that maps naturally to our confidence model — STATED goals with intrinsic origin get high confidence; SPECULATED goals get low.

The spec is written, reviewed (63 issues across four dimensions, all resolved), and planned. The extraction pipeline moves to neocortex. The Goallike trait gets five new accessors. The assembler gets vocabulary enforcement and two-phase dedup. Twelve issues track everything.

But the part that sticks is the affinity question. The cognitive model can simulate what it means to care about something — drives, attention, mood, affect trajectories, competence feedback. What it can't do is decide *what to care about* from first principles. That requires either a biography or an author. The engine is general; the content is personal.

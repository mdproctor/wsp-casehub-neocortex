# Handoff — 2026-06-27

## What Changed

Branch `issue-31-matryoshka-binary-quantization` implements #31 — Matryoshka embeddings + Qdrant quantization. Six commits, 15 files, 146 tests passing, full build green. Implementation complete; branch needs `work-end` to close.

Key design decisions: dual-vector tiered search rejected (HNSW overhead offsets binary index savings below 10M vectors). Instead: `MatryoshkaEmbeddingModel` decorator (truncation + renormalization) + Qdrant `DenseQuantization` config (binary/scalar at collection creation). Search-time oversampling on dense prefetch leg. Reactive `denseDimension` bug fixed (was capturing raw model dimension in `@PostConstruct`, not effective model).

## Immediate Next Step

Run `work-end` on branch `issue-31-matryoshka-binary-quantization` to close. Journal has 5 entries ready for ARC42 merge.

## What's Next

*Unchanged — retrieve with: `git show HEAD~1:HANDOFF.md`*

Remove #31 from the backlog after close.

## Key References

- Spec: `specs/issue-31-matryoshka-binary-quantization/2026-06-26-matryoshka-quantization-design.md`
- Blog: `blog/2026-06-27-mdp17-matryoshka-and-the-math-that-didnt-add-up.md`
- Garden: `intellij-platform/GE-20260627-fed7cf.md`, `jvm/GE-20260627-8b0fb8.md`
- Journal: `design/JOURNAL.md` (5 entries, §4, §6, §7, §8 anchors)

<div align="center">

# The baseline

**What a length-guided search reaches, and why what it misses is the point.**

[Documentation](../README.md) &nbsp;·&nbsp;
[The search](../../src/search/best_first.py)

</div>

---

## What was run

Best first search on total relator length, with a visited set keyed on the
presentation and a node budget. Run against the Akbulut–Kirby presentations,

    AK(n) = < x, y | x^n = y^(n+1),  x y x = y x y >

which are the classical candidate counterexamples and the usual thing a new
search is pointed at first.

## What it found

| Case | Result |
| :--- | :--- |
| `AK(2)`, AC | **18 moves**, verified by the repository's own verifier |
| `AK(2)`, stable AC | not found within 60,000 expanded nodes |
| `AK(3)`, AC | not found within 60,000 expanded nodes |

Every figure is a measurement from this repository, reproducible with

```bash
python -m src.search.best_first AK 2
```

## Why it stops where it does

Total relator length is a weak guide, and it fails for a structural reason
rather than a tuning reason. A trivialisation usually has to **lengthen** a
relator before the cancellation that shortens it becomes available: multiplying
by another relator makes the word longer, and only after conjugating does it
collapse. A search that prefers short presentations therefore walks away from
exactly the states a solution passes through.

That produces the pattern above. The easy cases fall quickly, and the hard ones
are not merely slow, they are invisible to the heuristic.

> [!NOTE]
> The stable case failing while the ordinary one succeeds is worth reading
> carefully. Stabilising adds both length and rank before it helps, so the same
> heuristic penalises the move that makes the stable problem easier in
> principle. The extra freedom costs search before it pays.

## What would beat it

Stated as what to try, not as what has been done here.

| Direction | Why it might help |
| :--- | :--- |
| Allow length to rise, under a budget | The known trivialisations are not monotone, so no monotone search will find them |
| Search from both ends | The target is a single known presentation, which makes meeting in the middle natural |
| Learn the move ordering | The branching factor is small and fixed, which is the shape a learned policy handles well |
| Reuse subpaths across the pool | Ten thousand presentations over the same two generators will share structure |

None of that is implemented. The baseline is here so that anything implemented
later has a number to beat, measured with the same verifier.

**[Back to the documentation](../README.md)** &nbsp;·&nbsp;
**[On to the open questions](open_questions.md)**

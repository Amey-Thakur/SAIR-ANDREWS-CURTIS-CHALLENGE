<div align="center">

# Open questions

**What is unfinished here, including the parts that would be easy to leave out.**

[Documentation](../README.md) &nbsp;·&nbsp;
[The baseline](baseline.md)

</div>

---

## Known gaps

| Gap | Status |
| :--- | :--- |
| The official submission format | Arrives with the Discovery Track on 11 September 2026. The reader follows the challenge's own description of a solution until then |
| The shared pool | The 10,115 presentations are released at launch, so nothing here has been run against them |
| Minimality | Nothing in this repository certifies that a path is shortest. Every length reported is an upper bound |
| Stable AC beyond the trivial cases | The baseline does not reach it, and no better search is implemented |
| The Proof Track | Not attempted |

## What the numbers here do and do not mean

The eighteen move trivialisation of `AK(2)` is a verified upper bound, found by
this repository's search and replayed by its own verifier. It is not a claim
that eighteen is shortest, and it is not a competition result, because the
competition has not opened.

The two failures are budget statements. A search that stops proves nothing
about the presentation, only about the search, and treating it otherwise is the
easiest mistake available in this problem.

## The question behind the rest

Reachability under the moves is an equivalence relation, so the conjecture says
there is exactly one class of balanced presentations of the trivial group at
each rank. A search can only ever confirm membership, never rule it out.

That asymmetry sets what is worth building. Confirming membership faster is
engineering with a clear objective and a cheap check. Ruling it out needs an
invariant that separates two classes, and the reason the problem is sixty years
old is that no computable one is known.

So the honest division of effort is to treat the Discovery Track as a search
problem and measure everything, and not to let a long run start to feel like
evidence about the conjecture.

**[Back to the documentation](../README.md)** &nbsp;·&nbsp;
**[Back to the moves](../../src/README.md)**

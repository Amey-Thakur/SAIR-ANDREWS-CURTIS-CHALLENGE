<div align="center">

# The competition

**Two tracks, two problems, and what a leaderboard entry is actually worth.**

[Documentation](../README.md) &nbsp;·&nbsp;
[The moves](../../src/README.md) &nbsp;·&nbsp;
[Competition](https://competition.sair.foundation/competitions/acc/overview)

</div>

---

## The shape of it

Run by Caltech and the SAIR Foundation, co-organised by Lucas Fagan, Sergei
Gukov and Terence Tao. Two tracks, each covering both problems.

| Track | What is submitted | Opens |
| :--- | :--- | :--- |
| **Discovery** | A challenge identifier and a list of moves | 11 September 2026, 16:00 UTC |
| **Proof** | A proof or disproof of either conjecture | 20 September 2026 |

Registration opened on 8 September 2026 and the deadline for everything is
30 November 2026.

## The Discovery Track

A shared pool of **10,115 two-generator presentations**. For each one, find a
short sequence of moves that simplifies it.

| Problem | Target | Constraint |
| :--- | :--- | :--- |
| AC | the ordered pair `(x, y)` | generators fixed at two |
| Stable AC | the empty presentation | at most 8 generators at any point |

A solution carries nothing but an identifier and the moves. The verifier
replays them. AC and Stable AC have separate leaderboards, and both reward the
**shortest verified path**. Sequences stay private during the competition and
are published afterwards.

> [!IMPORTANT]
> Because a solution is only a list of moves, the entire value of an entry is
> that it replays. There is no partial credit for a sequence that ends one move
> short, and no way to argue about it afterwards. Verifying locally costs
> nothing, which is why [check_solution](../../src/harness/check_solution.py)
> exists and why its exit code is the interface.

## What "shortest" makes hard

Rewarding the shortest path changes the search problem. A path that trivialises
is easy to want and easy to check; a path that is *minimal* is neither, because
nothing here certifies a lower bound. In practice an entry is a standing bid
that someone else may undercut, and improving a known path is as valuable as
finding a first one.

That has a direct consequence for effort. Time spent shaving moves off a
presentation somebody has already trivialised competes with time spent reaching
one nobody has, and only the second kind can be a first entry.

## The Proof Track

A proof must establish the full conjecture at every positive finite rank. A
disproof must establish its negation, and may do so by exhibiting a
counterexample **or** by proving that one exists without identifying it.

Submissions are public, versioned and timestamped, and may be a description, a
paper, an arXiv version, or a GitHub repository holding a Lean proof at a fixed
commit. Community peer review is invited, and Lean formalisations are open to
the same scrutiny.

## What is deliberately not attempted here

| Not done | Why |
| :--- | :--- |
| A submission client | The official format arrives at launch, and guessing it now would only have to be rewritten |
| A lower bound on any path | Nothing in this repository certifies minimality, so no figure here claims it |
| A proof-track argument | The conjecture is sixty years old, and a repository implying otherwise would be worth less than one that does not |

**[Back to the documentation](../README.md)** &nbsp;·&nbsp;
**[On to the baseline](../research/baseline.md)**

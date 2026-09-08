<div align="center">

# The conjecture

**What is being asked, and why the stable version is not the same question.**

[Documentation](../README.md) &nbsp;·&nbsp;
[The moves](../../src/README.md)

</div>

---

## Balanced presentations

A group presentation lists generators and defining relations. It is
**balanced** when there are as many relations as generators. The presentations
in this problem are balanced *and* present the trivial group: every relation
together forces every generator to be the identity.

The standard balanced presentation of the trivial group at rank `n` is the
obvious one, each generator set equal to the identity on its own. At rank two
that is the ordered pair `(x, y)`.

## The question

Andrews and Curtis asked, in 1965, whether every balanced presentation of the
trivial group can be carried to that standard one using only elementary moves
on the relators:

| Move | Replace `r` with |
| :--- | :--- |
| Invert | `r⁻¹` |
| Multiply | `r s` or `r s⁻¹`, where `s` is another relator |
| Conjugate | `c r c⁻¹`, where `c` is a generator or its inverse |

Each move touches one relator and leaves the rest alone, and adjacent inverse
letters cancel afterwards. Every move is invertible, so reachability is an
equivalence relation and the question is whether there is only one class.

## Why the stable version differs

The stable version allows introducing a fresh generator `z` with the relator
`z`, and deleting such a pair once `z` appears nowhere else. Those two moves
change the rank.

That is not a cosmetic extension. A path that is unavailable at fixed rank may
open up once there is room to work in, so a presentation could in principle be
stably trivialisable without being trivialisable. Whether that ever happens is
the second of the two open questions the challenge poses, and the challenge
caps the intermediate rank at eight generators so that the search space stays
finite in practice.

> [!NOTE]
> A disproof does not need an explicit counterexample. The challenge accepts a
> proof that one exists without identifying it, which is worth remembering
> before assuming the Proof Track is only about exhibiting a presentation.

## What obstructs a trivialisation

Very little, cheaply. Exponent sums survive conjugation and flip under
inversion, so they can refute a presentation immediately and otherwise say
nothing. Beyond that the known invariants are hard to compute and the practical
answer has been search.

That asymmetry is why the Discovery Track exists at all: for most presentations
nobody knows the shortest path, and the shortest known one is whatever the best
search has found so far.

**[Back to the documentation](../README.md)** &nbsp;·&nbsp;
**[On to the competition](../competition/analysis.md)**

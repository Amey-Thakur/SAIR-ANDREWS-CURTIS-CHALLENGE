# ==============================================================================
# File: moves.py
# Description: The Andrews-Curtis moves, exactly the ones the challenge lists,
#   and nothing else. Every move returns a new presentation and refuses rather
#   than silently repairing an illegal argument, because a verifier that quietly
#   fixes a bad move accepts a solution nobody actually found.
# Usage: from src.ac.moves import Invert, Multiply, Conjugate, apply
# Tech Stack: Python 3.10+, standard library only
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass

from .presentation import Presentation
from .word import conjugate, free_reduce, inverse, multiply, to_string

MAX_RANK = 8
"""The stable problem allows at most eight generators at any point."""


class IllegalMove(Exception):
    """The move cannot be applied to this presentation, and here is why."""


@dataclass(frozen=True)
class Invert:
    """Replace relator i by its inverse."""
    i: int

    def apply(self, p: Presentation) -> Presentation:
        _check_index(p, self.i)
        rels = list(p.relators)
        rels[self.i] = inverse(rels[self.i])
        return Presentation(p.rank, tuple(rels))

    def __str__(self):
        return f"invert r{self.i}"


@dataclass(frozen=True)
class Multiply:
    """Replace relator i by r_i r_j, or by r_i r_j inverse when sign is -1.

    The challenge says `s` is *another* relator, so i and j must differ. A
    relator multiplied by itself is not an Andrews-Curtis move."""
    i: int
    j: int
    sign: int = 1

    def apply(self, p: Presentation) -> Presentation:
        _check_index(p, self.i)
        _check_index(p, self.j)
        if self.i == self.j:
            raise IllegalMove("multiply needs two different relators")
        if self.sign not in (1, -1):
            raise IllegalMove("sign must be 1 or -1")
        other = p.relators[self.j]
        if self.sign == -1:
            other = inverse(other)
        rels = list(p.relators)
        rels[self.i] = multiply(rels[self.i], other)
        return Presentation(p.rank, tuple(rels))

    def __str__(self):
        return f"multiply r{self.i} by r{self.j}" + ("^-1" if self.sign < 0 else "")


@dataclass(frozen=True)
class Conjugate:
    """Replace relator i by c r_i c inverse, where c is a generator or inverse."""
    i: int
    c: int

    def apply(self, p: Presentation) -> Presentation:
        _check_index(p, self.i)
        if self.c == 0 or abs(self.c) > p.rank:
            raise IllegalMove(f"{self.c} is not a generator of rank {p.rank}")
        rels = list(p.relators)
        rels[self.i] = conjugate(rels[self.i], self.c)
        return Presentation(p.rank, tuple(rels))

    def __str__(self):
        return f"conjugate r{self.i} by {to_string((self.c,))}"


@dataclass(frozen=True)
class Stabilize:
    """Add a fresh generator z together with the relator z.

    Only legal in the stable problem, and only while the rank stays inside the
    cap the challenge sets."""

    def apply(self, p: Presentation) -> Presentation:
        if p.rank >= MAX_RANK:
            raise IllegalMove(f"stabilizing would exceed {MAX_RANK} generators")
        z = p.rank + 1
        return Presentation(z, p.relators + ((z,),))

    def __str__(self):
        return "stabilize"


@dataclass(frozen=True)
class Destabilize:
    """Delete relator i, which must be exactly the top generator, together with
    that generator, which no other relator may use."""
    i: int

    def apply(self, p: Presentation) -> Presentation:
        _check_index(p, self.i)
        if p.rank == 0:
            raise IllegalMove("nothing to destabilize")
        z = p.rank
        if p.relators[self.i] != (z,):
            raise IllegalMove(
                f"r{self.i} is {to_string(p.relators[self.i])}, not the bare "
                f"generator {to_string((z,))}")
        for k, r in enumerate(p.relators):
            if k != self.i and z in {abs(x) for x in r}:
                raise IllegalMove(
                    f"{to_string((z,))} still occurs in r{k}")
        rels = tuple(r for k, r in enumerate(p.relators) if k != self.i)
        return Presentation(z - 1, rels)

    def __str__(self):
        return f"destabilize r{self.i}"


ORDINARY = (Invert, Multiply, Conjugate)
STABLE = ORDINARY + (Stabilize, Destabilize)


def _check_index(p: Presentation, i: int) -> None:
    if not 0 <= i < len(p.relators):
        raise IllegalMove(f"there is no relator r{i}")


def apply(p: Presentation, move) -> Presentation:
    """Apply one move. Relators come back freely reduced."""
    out = move.apply(p)
    return Presentation(out.rank, tuple(free_reduce(r) for r in out.relators))


def apply_all(p: Presentation, moves):
    """Apply a sequence, returning the presentation after each step."""
    trail = [p]
    for move in moves:
        p = apply(p, move)
        trail.append(p)
    return trail


def neighbours(p: Presentation, stable: bool = False):
    """Every presentation one legal move away, with the move that got there.

    This is the branching factor a search pays: for two relators the ordinary
    moves give two inversions, four multiplications and eight conjugations."""
    out = []
    n = len(p.relators)
    for i in range(n):
        out.append((Invert(i), apply(p, Invert(i))))
        for j in range(n):
            if i == j:
                continue
            for sign in (1, -1):
                move = Multiply(i, j, sign)
                out.append((move, apply(p, move)))
        for c in range(1, p.rank + 1):
            for signed in (c, -c):
                move = Conjugate(i, signed)
                out.append((move, apply(p, move)))
    if stable:
        if p.rank < MAX_RANK:
            out.append((Stabilize(), apply(p, Stabilize())))
        for i in range(n):
            try:
                out.append((Destabilize(i), apply(p, Destabilize(i))))
            except IllegalMove:
                pass
    return out

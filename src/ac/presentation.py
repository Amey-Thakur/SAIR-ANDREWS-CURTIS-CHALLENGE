# ==============================================================================
# File: presentation.py
# Description: Balanced presentations of the trivial group, which is the only
#   kind the conjecture is about: as many defining relators as generators. The
#   type is immutable so that a search can put presentations in a visited set
#   and so that a move returns a new presentation rather than editing the one
#   it was handed.
# Usage: from src.ac.presentation import Presentation, AK, trivial
# Tech Stack: Python 3.10+, standard library only
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass

from .word import free_reduce, generators_used, to_string


@dataclass(frozen=True)
class Presentation:
    """`rank` generators and `relators` defining relators, in order.

    Order matters. The Andrews-Curtis target for two generators is the ordered
    pair (x, y), so a presentation that reaches (y, x) has not finished."""
    rank: int
    relators: tuple

    def __post_init__(self):
        if self.rank < 0:
            raise ValueError("rank cannot be negative")
        for r in self.relators:
            for letter in r:
                if letter == 0 or abs(letter) > self.rank:
                    raise ValueError(
                        f"relator {to_string(r)} uses a generator outside "
                        f"rank {self.rank}")

    @property
    def is_balanced(self) -> bool:
        return len(self.relators) == self.rank

    @property
    def total_length(self) -> int:
        """The sum of relator lengths, which is what a search descends."""
        return sum(len(r) for r in self.relators)

    def uses(self, generator: int) -> bool:
        return any(generator in generators_used(r) for r in self.relators)

    def __str__(self) -> str:
        gens = ", ".join(to_string((i,)) for i in range(1, self.rank + 1))
        rels = ", ".join(to_string(r) for r in self.relators)
        return f"< {gens or '-'} | {rels or '-'} >"


def presentation(rank: int, *relators) -> Presentation:
    """Build a presentation, freely reducing each relator on the way in."""
    return Presentation(rank, tuple(free_reduce(r) for r in relators))


# -- the two goals ----------------------------------------------------------

def trivial(rank: int = 2) -> Presentation:
    """The standard presentation at a given rank: each generator on its own.

    This is the Andrews-Curtis target. At rank two it is the ordered pair
    (x, y)."""
    return Presentation(rank, tuple((i,) for i in range(1, rank + 1)))


EMPTY = Presentation(0, ())
"""The empty presentation, which is the target of the stable problem."""


# -- the classical families -------------------------------------------------

def AK(n: int) -> Presentation:
    """The Akbulut-Kirby presentation

        < x, y | x^n = y^(n+1),  x y x = y x y >

    written with the relations moved to relators. These are the standard
    candidate counterexamples to the conjecture and the usual benchmark for a
    search, so they are here to be attempted rather than asserted about."""
    if n < 1:
        raise ValueError("AK is defined for n >= 1")
    r1 = (1,) * n + (-2,) * (n + 1)
    r2 = (1, 2, 1, -2, -1, -2)
    return presentation(2, r1, r2)


def AK_family(lo: int = 2, hi: int = 6):
    return {f"AK({n})": AK(n) for n in range(lo, hi + 1)}

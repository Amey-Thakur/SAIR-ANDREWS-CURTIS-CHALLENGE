# ==============================================================================
# File: word.py
# Description: Words in a free group, which is what a relator is. Generators are
#   numbered from 1 and an inverse is the negation, so x is 1, x inverse is -1,
#   y is 2. That representation makes inversion a reversal with a sign flip and
#   makes free reduction a single stack pass, which matters because reduction
#   runs after every move and the search does nothing else so often.
# Usage: from src.ac.word import free_reduce, inverse, multiply, conjugate
# Tech Stack: Python 3.10+, standard library only
# ==============================================================================

from __future__ import annotations

Word = tuple  # tuple[int, ...], each entry a non-zero generator index


def free_reduce(w) -> Word:
    """Cancel adjacent inverse pairs until none remain.

    The competition states that adjacent inverse letters cancel after each
    move, so every move in this package returns a freely reduced word and
    nothing downstream has to remember to do it."""
    out = []
    for letter in w:
        if out and out[-1] == -letter:
            out.pop()
        else:
            out.append(letter)
    return tuple(out)


def inverse(w) -> Word:
    """The inverse word: reverse the order and invert each letter."""
    return tuple(-letter for letter in reversed(w))


def multiply(a, b) -> Word:
    """The product a b, freely reduced."""
    return free_reduce(tuple(a) + tuple(b))


def conjugate(w, c: int) -> Word:
    """c w c inverse, for a single letter c."""
    if c == 0:
        raise ValueError("0 is not a generator")
    return free_reduce((c,) + tuple(w) + (-c,))


def generators_used(w) -> frozenset:
    """Which generators occur in the word, ignoring sign."""
    return frozenset(abs(letter) for letter in w)


def exponent_sum(w, generator: int) -> int:
    """The total exponent of one generator, which is invariant under
    conjugation and is the cheapest obstruction to trivialising."""
    return sum(1 if letter == generator else -1 if letter == -generator else 0
               for letter in w)


def to_string(w, names="xyzuvwst") -> str:
    """A word in the usual notation, so failures read as mathematics."""
    if not w:
        return "1"
    parts = []
    for letter in w:
        index = abs(letter) - 1
        name = names[index] if index < len(names) else f"g{abs(letter)}"
        parts.append(name if letter > 0 else name + "^-1")
    return " ".join(parts)


def parse(text: str, names="xyzuvwst") -> Word:
    """Read a word back from `to_string`, or from the compact form `x y^-1 x`."""
    out = []
    for token in text.split():
        if token == "1":
            continue
        negative = token.endswith("^-1")
        base = token[:-3] if negative else token
        if base in names:
            index = names.index(base) + 1
        elif base.startswith("g") and base[1:].isdigit():
            index = int(base[1:])
        else:
            raise ValueError(f"unknown generator: {base}")
        out.append(-index if negative else index)
    return free_reduce(tuple(out))

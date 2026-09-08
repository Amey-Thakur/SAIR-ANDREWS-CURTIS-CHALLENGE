# ==============================================================================
# File: best_first.py
# Description: A baseline search for short trivialisations. Best first on total
#   relator length, with a visited set and a node budget.
#
#   It is a baseline on purpose. Total length is a weak guide, because the
#   moves that eventually trivialise a hard presentation usually lengthen it
#   first, which is exactly why the Akbulut-Kirby family is hard and why
#   descending greedily is known not to be enough. Something honest to measure
#   against matters more here than something clever that has not been measured.
# Usage: python -m src.search.best_first AK 2
# Tech Stack: Python 3.10+, standard library only
# ==============================================================================

from __future__ import annotations

import heapq
import itertools
import sys

from ..ac.moves import neighbours
from ..ac.presentation import AK, Presentation, trivial
from ..ac.verify import target_for, verify


def best_first(start: Presentation, stable: bool = False, budget: int = 200_000,
               max_length: int | None = None):
    """Search for a move sequence from `start` to its target.

    Returns (moves, stats). `moves` is None when the budget ran out, which is
    a result and not a failure: the point of a budget is that the answer comes
    back either way."""
    goal = target_for(start, stable)
    cap = max_length if max_length is not None else max(60, start.total_length * 6)

    counter = itertools.count()
    seen = {start: 0}
    heap = [(start.total_length, next(counter), start, ())]
    expanded = 0

    while heap and expanded < budget:
        _, _, p, path = heapq.heappop(heap)
        if p == goal:
            return list(path), {"expanded": expanded, "seen": len(seen),
                                "length": len(path)}
        expanded += 1
        for move, q in neighbours(p, stable=stable):
            if q.total_length > cap:
                continue
            depth = len(path) + 1
            if seen.get(q, 1 << 30) <= depth:
                continue
            seen[q] = depth
            heapq.heappush(heap, (q.total_length + depth, next(counter), q,
                                  path + (move,)))

    return None, {"expanded": expanded, "seen": len(seen), "length": None}


def report(name: str, start: Presentation, stable: bool = False, **kw):
    moves, stats = best_first(start, stable=stable, **kw)
    label = "stable AC" if stable else "AC"
    print(f"{name}  {start}")
    if moves is None:
        print(f"  no {label} trivialisation inside the budget "
              f"({stats['expanded']} expanded, {stats['seen']} seen)")
        return None
    check = verify(start, moves, stable=stable)
    status = "verified" if check else f"REJECTED: {check.reason}"
    print(f"  {label} in {len(moves)} moves, {status} "
          f"({stats['expanded']} expanded)")
    for i, move in enumerate(moves, 1):
        print(f"    {i:>3}. {move}")
    return moves


if __name__ == "__main__":
    args = sys.argv[1:]
    stable = "--stable" in args
    args = [a for a in args if a != "--stable"]
    if args and args[0] == "AK":
        n = int(args[1]) if len(args) > 1 else 2
        report(f"AK({n})", AK(n), stable=stable)
    else:
        # The target itself, which every search must at least manage.
        report("trivial(2)", trivial(2), stable=stable)

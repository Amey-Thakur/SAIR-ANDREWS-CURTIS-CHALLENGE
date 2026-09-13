# ==============================================================================
# File: engine.py
# Description: The search engine behind Discovery Track entries. The baseline in
#   best_first.py stays as the honest reference point; this is the one meant to
#   compete. Three things make it faster and its paths shorter: a presentation
#   is a bare pair of tuples rather than a dataclass, a path is recovered from
#   parent pointers instead of being copied on every push, and every path it
#   finds is shortened afterwards by searching for detours around each stretch.
#   Nothing leaves this module unless the verifier in ..ac.verify replays it.
# Usage: from src.search.engine import solve
#        python -m src.search.engine AK 2
# Tech Stack: Python 3.10+, standard library only
# ==============================================================================

from __future__ import annotations

import heapq
import itertools
from collections import deque

from ..ac.moves import Conjugate, Destabilize, Invert, Multiply, neighbours
from ..ac.presentation import EMPTY, Presentation
from ..ac.verify import verify
from ..ac.word import free_reduce

TARGET = ((1,), (2,))
CONJ = (1, -1, 2, -2)
"""Conjugating letters in move-id order: x, x^-1, y, y^-1."""

# Move ids for two relators over two generators. Fourteen in all.
#   0, 1     invert r0, invert r1
#   2, 3     r0 <- r0 r1,  r0 <- r0 r1^-1
#   4, 5     r1 <- r1 r0,  r1 <- r1 r0^-1
#   6..9     r0 <- c r0 c^-1, for c in CONJ
#   10..13   r1 <- c r1 c^-1, for c in CONJ


# -- words ------------------------------------------------------------------

def join(a, b):
    """The product a b, for a and b already freely reduced.

    Only the junction can cancel, so this counts the overlap instead of
    rescanning both words."""
    la, lb = len(a), len(b)
    m = la if la < lb else lb
    k = 0
    while k < m and a[la - 1 - k] == -b[k]:
        k += 1
    return a + b if k == 0 else a[:la - k] + b[k:]


def invert(w):
    return tuple([-x for x in w[::-1]])


# -- moves ------------------------------------------------------------------

def expand(state):
    """Every state one ordinary move away, as (move id, state)."""
    r0, r1 = state
    i0 = invert(r0)
    i1 = invert(r1)
    out = [
        (0, (i0, r1)),
        (1, (r0, i1)),
        (2, (join(r0, r1), r1)),
        (3, (join(r0, i1), r1)),
        (4, (r0, join(r1, r0))),
        (5, (r0, join(r1, i0))),
    ]
    for k, c in enumerate(CONJ):
        out.append((6 + k, (join(join((c,), r0), (-c,)), r1)))
    for k, c in enumerate(CONJ):
        out.append((10 + k, (r0, join(join((c,), r1), (-c,)))))
    return out


def step(state, mid):
    """Apply one move id."""
    r0, r1 = state
    if mid == 0:
        return (invert(r0), r1)
    if mid == 1:
        return (r0, invert(r1))
    if mid == 2:
        return (join(r0, r1), r1)
    if mid == 3:
        return (join(r0, invert(r1)), r1)
    if mid == 4:
        return (r0, join(r1, r0))
    if mid == 5:
        return (r0, join(r1, invert(r0)))
    if 6 <= mid < 10:
        c = CONJ[mid - 6]
        return (join(join((c,), r0), (-c,)), r1)
    if 10 <= mid < 14:
        c = CONJ[mid - 10]
        return (r0, join(join((c,), r1), (-c,)))
    raise ValueError(f"there is no move id {mid}")


def to_move(mid):
    """The verifier's move object for a move id."""
    if mid == 0:
        return Invert(0)
    if mid == 1:
        return Invert(1)
    if mid == 2:
        return Multiply(0, 1, 1)
    if mid == 3:
        return Multiply(0, 1, -1)
    if mid == 4:
        return Multiply(1, 0, 1)
    if mid == 5:
        return Multiply(1, 0, -1)
    if 6 <= mid < 10:
        return Conjugate(0, CONJ[mid - 6])
    if 10 <= mid < 14:
        return Conjugate(1, CONJ[mid - 10])
    raise ValueError(f"there is no move id {mid}")


def replay(start, mids):
    states = [start]
    for m in mids:
        states.append(step(states[-1], m))
    return states


def _path(parent, node):
    out = []
    while parent[node] is not None:
        prev, move = parent[node]
        out.append(move)
        node = prev
    out.reverse()
    return out


# -- the finish -------------------------------------------------------------
# A search stops at any of the eight length-two trivial states. Getting from
# there to the actual target is a fixed cost, found once by exhaustive search
# over the handful of states that short.

TRIVIAL = tuple(((sa * a,), (sb * b,))
                for a, b in ((1, 2), (2, 1))
                for sa in (1, -1) for sb in (1, -1))


def _finish_ac(src):
    """Shortest ordinary-move route from a trivial state to (x, y)."""
    if src == TARGET:
        return []
    parent = {src: None}
    queue = deque([src])
    while queue:
        s = queue.popleft()
        for mid, t in expand(s):
            if t in parent or not t[0] or not t[1]:
                continue
            if len(t[0]) + len(t[1]) > 4:
                continue
            parent[t] = (s, mid)
            if t == TARGET:
                return _path(parent, t)
            queue.append(t)
    raise AssertionError(f"no route from {src} to {TARGET}")


def _finish_stable(src):
    """Shortest route from a trivial state to the empty presentation, allowing
    destabilisation, as verifier move objects."""
    start = Presentation(2, src)
    parent = {start: None}
    queue = deque([start])
    while queue:
        p = queue.popleft()
        for move, q in neighbours(p, stable=True):
            if q in parent or q.rank > 2 or q.total_length > 4:
                continue
            parent[q] = (p, move)
            if q == EMPTY:
                return _path(parent, q)
            queue.append(q)
    raise AssertionError(f"no stable route from {src}")


FINISH_AC = {t: _finish_ac(t) for t in TRIVIAL}
FINISH_STABLE = {t: _finish_stable(t) for t in TRIVIAL}


# -- search -----------------------------------------------------------------

def greedy(start, max_nodes=500_000, cap=None, weight=0.0):
    """Best first on total relator length, toward any trivial state.

    `weight` adds that multiple of the depth to the priority, trading a little
    reach for shorter paths. `cap` bounds each relator's length. Returns
    (move ids, nodes seen), with None for the ids when the budget runs out."""
    if start in FINISH_AC:
        return [], 1
    parent = {start: None}
    counter = itertools.count()
    heap = [(len(start[0]) + len(start[1]), 0, next(counter), start)]
    push, pop = heapq.heappush, heapq.heappop
    while heap and len(parent) < max_nodes:
        _, depth, _, s = pop(heap)
        nd = depth + 1
        for mid, t in expand(s):
            if t in parent:
                continue
            a, b = t
            if not a or not b:
                continue
            if cap is not None and (len(a) > cap or len(b) > cap):
                continue
            parent[t] = (s, mid)
            if t in FINISH_AC:
                return _path(parent, t), len(parent)
            push(heap, (len(a) + len(b) + weight * nd, nd, next(counter), t))
    return None, len(parent)


def _ball(src, depth, cap):
    """Every state within `depth` moves, with a shortest route to it."""
    routes = {src: []}
    frontier = [src]
    for _ in range(depth):
        nxt = []
        for s in frontier:
            base = routes[s]
            for mid, t in expand(s):
                if t in routes:
                    continue
                a, b = t
                if not a or not b or len(a) > cap or len(b) > cap:
                    continue
                routes[t] = base + [mid]
                nxt.append(t)
        frontier = nxt
    del routes[src]
    return routes


def shorten(start, mids, depth=3, slack=4):
    """Replace stretches of a path with shorter detours.

    Walks the path; from each state it searches every state within `depth`
    moves, and if one of those appears later on the path by more moves than the
    detour takes, the stretch between is replaced. The endpoint never moves, so
    a path to a trivial state stays a path to that same state."""
    mids = list(mids)
    states = replay(start, mids)
    cap = max(max(len(a), len(b)) for a, b in states) + slack
    i = 0
    while i < len(states) - 2:
        last = {s: k for k, s in enumerate(states)}
        j = last[states[i]]
        if j > i:                                   # a cycle: cut it out
            del mids[i:j]
            del states[i:j]
            continue
        best_j, best_route, best_saving = None, None, 0
        for t, route in _ball(states[i], depth, cap).items():
            j = last.get(t)
            if j is None or j <= i:
                continue
            saving = (j - i) - len(route)
            if saving > best_saving:
                best_j, best_route, best_saving = j, route, saving
        if best_j is None:
            i += 1
            continue
        mids[i:best_j] = best_route
        states[i:best_j + 1] = replay(states[i], best_route)
    return mids


# -- the whole job ----------------------------------------------------------

def solve(relators, max_nodes=500_000, caps=(None,), weights=(0.0,),
          depth=3):
    """Find, shorten and verify AC and stable AC paths for one presentation.

    Tries every (cap, weight) pair and keeps the shortest verified result for
    each problem. Returns {"ac": moves, "stable_ac": moves, "stats": ...}, where
    a problem with no verified path maps to None."""
    start = tuple(free_reduce(tuple(r)) for r in relators)
    if len(start) != 2:
        raise ValueError("the engine handles two relators over two generators")
    begin = Presentation(2, start)

    best = {"ac": None, "stable_ac": None}
    tried = []
    for cap in caps:
        for weight in weights:
            core, seen = greedy(start, max_nodes=max_nodes, cap=cap,
                                weight=weight)
            tried.append({"cap": cap, "weight": weight, "seen": seen,
                          "found": core is not None,
                          "raw": None if core is None else len(core)})
            if core is None:
                continue

            core = shorten(start, core, depth=depth)
            end = replay(start, core)[-1]

            ac_mids = shorten(start, core + FINISH_AC[end], depth=depth)
            ac = [to_move(m) for m in ac_mids]
            stable_a = [to_move(m) for m in core] + FINISH_STABLE[end]
            stable_b = ac + [Destabilize(1), Destabilize(0)]
            stable = min(stable_a, stable_b, key=len)

            for problem, moves, is_stable in (("ac", ac, False),
                                              ("stable_ac", stable, True)):
                check = verify(begin, moves, stable=is_stable)
                if not check:
                    raise AssertionError(
                        f"engine produced a {problem} path the verifier "
                        f"rejects: {check.reason}")
                if best[problem] is None or len(moves) < len(best[problem]):
                    best[problem] = moves

    return {"ac": best["ac"], "stable_ac": best["stable_ac"],
            "stats": {"tried": tried}}


if __name__ == "__main__":
    import sys
    import time

    from ..ac.presentation import AK

    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    budget = int(sys.argv[3]) if len(sys.argv) > 3 else 500_000
    p = AK(n)
    t0 = time.time()
    out = solve(p.relators, max_nodes=budget)
    dt = time.time() - t0
    print(f"AK({n})  {p}  budget {budget}  {dt:.1f}s")
    for problem in ("ac", "stable_ac"):
        moves = out[problem]
        print(f"  {problem:9} " + ("not found" if moves is None
                                  else f"{len(moves)} moves, verified"))
    for t in out["stats"]["tried"]:
        print(f"  tried {t}")

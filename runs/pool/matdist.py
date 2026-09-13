"""An admissible lower bound on the moves still needed, from exponent sums.

Write M for the 2x2 matrix of exponent sums: row i holds the total exponent of
x and of y in relator i. The moves act on it simply:

    invert r_i            negate row i
    r_i <- r_i r_j^{+-1}  row i += or -= row j
    conjugation           no change at all

The target (x, y) has M = identity. So the fewest row operations carrying M to
the identity is a lower bound on the number of non-conjugation moves left, and
therefore on the number of moves left. It is admissible, so a search may
discard any state whose bound exceeds its remaining budget without risking the
optimum.

The bound is precomputed once by breadth-first search outward from the identity
over the six elementary operations, which is why it costs nothing per state.

Usage:
  python runs/pool/matdist.py            # build, report size, sanity-check
"""
from collections import deque

IDENTITY = ((1, 0), (0, 1))


def neighbours(m):
    (a, b), (c, d) = m
    return (
        ((-a, -b), (c, d)),          # negate row 0
        ((a, b), (-c, -d)),          # negate row 1
        ((a + c, b + d), (c, d)),    # row 0 += row 1
        ((a - c, b - d), (c, d)),    # row 0 -= row 1
        ((a, b), (c + a, d + b)),    # row 1 += row 0
        ((a, b), (c - a, d - b)),    # row 1 -= row 0
    )


def build(max_depth=14, bound=40):
    """matrix -> fewest row operations to the identity, within the limits."""
    dist = {IDENTITY: 0}
    frontier = [IDENTITY]
    for depth in range(1, max_depth + 1):
        nxt = []
        for m in frontier:
            for t in neighbours(m):
                if t in dist:
                    continue
                (a, b), (c, d) = t
                if max(abs(a), abs(b), abs(c), abs(d)) > bound:
                    continue
                dist[t] = depth
                nxt.append(t)
        frontier = nxt
        if not frontier:
            break
    return dist


def matrix(state):
    """The exponent-sum matrix of a presentation."""
    rows = []
    for r in state:
        x = y = 0
        for letter in r:
            if letter == 1:
                x += 1
            elif letter == -1:
                x -= 1
            elif letter == 2:
                y += 1
            elif letter == -2:
                y -= 1
        rows.append((x, y))
    return (rows[0], rows[1])


if __name__ == "__main__":
    import json
    import pathlib
    import statistics
    import sys
    import time

    REPO = pathlib.Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(REPO))

    t0 = time.time()
    table = build()
    print(f"table: {len(table):,} matrices in {time.time() - t0:.1f}s, "
          f"max distance {max(table.values())}")

    # Every move must change the bound by at most one, or it is not admissible.
    from src.search import engine as E
    import random
    rng = random.Random(5)
    checked = violations = 0
    for _ in range(2000):
        s = tuple(tuple(rng.choice((1, -1, 2, -2)) for _ in range(rng.randint(1, 8)))
                  for _ in range(2))
        if not all(s):
            continue
        ds = table.get(matrix(s))
        if ds is None:
            continue
        for mid in range(14):
            dt_ = table.get(matrix(E.step(s, mid)))
            if dt_ is None:
                continue
            checked += 1
            if abs(dt_ - ds) > 1:
                violations += 1
    print(f"admissibility: {checked:,} move checks, {violations} violations")

    rows = [json.loads(l) for l in
            open(REPO / "runs/pool/pool.jsonl", encoding="utf-8")]
    known = [table.get(matrix(tuple(tuple(w) for w in r["relators"]))) for r in rows]
    inside = [d for d in known if d is not None]
    print(f"pool: bound known for {len(inside):,} of {len(rows):,} challenges; "
          f"median {statistics.median(inside):.0f}, max {max(inside)}")
    held = [(r["ac_best"], d) for r, d in zip(rows, known)
            if d is not None and r["ac_best"] is not None]
    tight = sum(1 for b, d in held if d >= b)
    print(f"of {len(held):,} solved challenges the bound already equals or exceeds "
          f"the held best on {tight}")

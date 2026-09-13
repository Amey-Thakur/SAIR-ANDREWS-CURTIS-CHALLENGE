"""Learn a distance-to-trivial heuristic from paths we have already solved.

The search priority so far has been total_length + w * moves_spent, and the
measurements say no single w works: a large w returns exact minima but cannot
reach a long path, a small w reaches it but wanders. The formula is the limit,
not the budget. What a search of this kind actually wants is an estimate of how
far a presentation really is from the trivial pair, which is what a learned
heuristic supplies and a hand-picked formula cannot.

Training data is free here. Every verified path we hold passes through states
whose true distance to the trivial pair is known exactly: the number of moves
remaining. Replaying our own solutions turns each into a labelled example.

The model has to be evaluable inside the compiled search, so it is linear in
features that are cheap to compute from the two int8 words. That keeps it a dot
product per generated state.

Usage (from the repo root):
  python runs/pool/learn_heuristic.py
"""
import json
import os
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.ac.verify import move_to_json  # noqa: E402
from src.search import engine as E  # noqa: E402

NFEAT = 9


def features(r0, r1):
    """Cheap structural features of one presentation, as a float vector.

    Kept deliberately simple: each must be computable inside the njit search
    from the two int8 arrays, in time comparable to hashing the state."""
    la, lb = len(r0), len(r1)
    a = sum(1 for g in r0 if g == 1) - sum(1 for g in r0 if g == -1)
    b = sum(1 for g in r0 if g == 2) - sum(1 for g in r0 if g == -2)
    c = sum(1 for g in r1 if g == 1) - sum(1 for g in r1 if g == -1)
    d = sum(1 for g in r1 if g == 2) - sum(1 for g in r1 if g == -2)
    alt = 0
    for w in (r0, r1):
        for i in range(len(w) - 1):
            if (w[i] > 0) != (w[i + 1] > 0):
                alt += 1
    return np.array([
        la + lb,                    # total length, the old priority
        abs(la - lb),               # imbalance
        abs(a) + abs(b) + abs(c) + abs(d),
        abs(a * d - b * c),         # |det| of the exponent-sum matrix
        alt,                        # sign alternations
        max(la, lb),
        min(la, lb),
        1.0 if (la == 1 and lb == 1) else 0.0,
        1.0,                        # bias
    ], dtype=np.float64)


ID_OF = {json.dumps(move_to_json(E.to_move(k)), sort_keys=True): k
         for k in range(14)}


RECORD = {}
for _l in open(REPO / "runs/pool/pool.jsonl", encoding="utf-8"):
    _r = json.loads(_l)
    RECORD[_r["id"]] = _r["ac_best"]


def rows_from(path):
    """(features, moves remaining) for every state along one stored solution.

    Only paths at or below the current record are used. Our own long paths are
    real paths but poor labels: calling a state 963 moves from trivial when it
    is 301 away teaches the model our inefficiency rather than the geometry.
    That mistake made the first fit worse than using total length alone."""
    out = []
    for line in open(path, encoding="utf-8"):
        rec = json.loads(line)
        if rec["problem"] != "ac":
            continue
        best = RECORD.get(rec["id"])
        if best is None or rec["length"] > best:
            continue
        try:
            ids = [ID_OF[json.dumps(m, sort_keys=True)] for m in rec["moves"]]
        except KeyError:
            continue
        state = tuple(tuple(w) for w in rec["relators"])
        n = len(ids)
        for i, mid in enumerate(ids):
            out.append((features(state[0], state[1]), n - i))
            state = E.step(state, mid)
        out.append((features(state[0], state[1]), 0))
    return out


def main():
    data = []
    for f in sorted((REPO / "runs/pool").glob("*/solutions.jsonl")):
        try:
            got = rows_from(f)
        except Exception as exc:
            print(f"  {f.parent.name}: skipped ({exc})", flush=True)
            continue
        if got:
            data.extend(got)
            print(f"  {f.parent.name}: {len(got)} states", flush=True)
    if len(data) < 200:
        raise SystemExit(f"only {len(data)} training states, need more solutions")

    X = np.stack([d[0] for d in data])
    y = np.array([d[1] for d in data], dtype=np.float64)
    print(f"\n{len(y)} labelled states, distance to go: median {np.median(y):.0f}, "
          f"max {y.max():.0f}")

    # plain least squares; the search only needs a ranking, not calibration
    w, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ w
    err = np.abs(pred - y)
    print(f"fit: mean |error| {err.mean():.1f} moves, median {np.median(err):.1f}")

    base = np.abs(X[:, 0] - y)      # what total length alone would predict
    print(f"total length alone: mean |error| {base.mean():.1f} moves, "
          f"median {np.median(base):.1f}")

    out = REPO / "runs/pool/heuristic.npz"
    np.savez(out, w=w)
    print(f"\nweights -> {out}")
    for name, v in zip(("total", "imbalance", "expsum", "det", "alt",
                        "maxlen", "minlen", "trivial", "bias"), w):
        print(f"   {name:>10}: {v:+.3f}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()

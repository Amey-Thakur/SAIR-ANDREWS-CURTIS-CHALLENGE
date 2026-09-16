"""Iterative-deepening A* on the learned heuristic.

Every other solver here stores every state it visits, so the node budget is a
memory budget and reach is capped by RAM: 12M states is about 1.3 GB and buys
roughly record 18. That is the binding constraint, not time.

IDA* removes it. It searches depth-first under a bound on f = g + h, raising the
bound to the smallest f that exceeded it, and keeps only the current path in
memory. Memory is O(depth) instead of O(nodes), so it can reach depths a stored
search cannot hold. The cost is re-expansion: each iteration redoes the work of
the last, which is affordable when the branching factor is high enough that the
final iteration dominates.

Two things make it usable on Andrews-Curtis:

- the moves are invertible, so cycles are everywhere. A state is rejected if it
  repeats any ancestor on the current path, which is exact and needs no table.
- a small transposition table catches the common case of reaching the same state
  by different orders at no worse depth. It is a filter, not a store: dropping an
  entry can only cost time, never correctness.

Usage (from the repo root):
  python runs/pool/idastar.py --check
  python runs/pool/idastar.py --min-held 19 --max-held 30 --max-k 2 --skip-held
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time

import numpy as np
from numba import njit

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "runs" / "pool"))
from astar import _h  # noqa: E402
from jit_engine import MAXLEN, _apply, _hash  # noqa: E402

MAXDEPTH = 512


@njit(cache=False)
def _dfs(pw0, pw1, pl0, pl1, phash, path, depth, g, bound, hw, weight,
         wordcap, tk, tv, tmask, budget, seen):
    """Depth-first under the f bound. Returns (found, next bound, nodes).

    `next bound` is the smallest f seen above the current bound, which is the
    value to try next; that is what makes the iteration terminate."""
    a0 = depth * MAXLEN
    la = pl0[depth]
    lb = pl1[depth]
    h = _h(hw, pw0[a0:a0 + MAXLEN], la, pw1[a0:a0 + MAXLEN], lb)
    f = g + weight * h
    if f > bound:
        return False, f, seen
    if la == 1 and lb == 1 and pw0[a0] == 1 and pw1[a0] == 2:
        return True, f, seen
    if depth + 1 >= MAXDEPTH or seen > budget:
        return False, 1.0e18, seen

    o0 = np.zeros(MAXLEN, dtype=np.int8)
    o1 = np.zeros(MAXLEN, dtype=np.int8)
    buf = np.zeros(MAXLEN, dtype=np.int8)
    tmp = np.zeros(MAXLEN + 2, dtype=np.int8)

    nxt = 1.0e18
    for mid in range(14):
        na, nb = _apply(mid, pw0[a0:a0 + MAXLEN], la, pw1[a0:a0 + MAXLEN], lb,
                        o0, o1, buf, tmp)
        if na == 0 or nb == 0 or na > wordcap or nb > wordcap:
            continue
        hh = _hash(o0, na, o1, nb)
        # exact cycle check against the current path, no table needed
        rep = False
        for d in range(depth + 1):
            if phash[d] == hh:
                rep = True
                break
        if rep:
            continue
        # Transposition filter, optional. It must never suppress a branch that
        # would have raised the next bound: if every child is filtered, `nxt`
        # stays at infinity and the iteration wrongly concludes the space is
        # exhausted. That is what made the first version stop after 83k nodes
        # with a 300M budget. Enabled only when tmask is non-zero.
        if tmask != np.uint64(0):
            slot = hh & tmask
            if tk[slot] == hh and tv[slot] < depth + 1:
                continue
            tk[slot] = hh
            tv[slot] = depth + 1

        b0 = (depth + 1) * MAXLEN
        for i in range(na):
            pw0[b0 + i] = o0[i]
        for i in range(nb):
            pw1[b0 + i] = o1[i]
        pl0[depth + 1] = na
        pl1[depth + 1] = nb
        phash[depth + 1] = hh
        path[depth] = mid
        seen += 1
        ok, cand, seen = _dfs(pw0, pw1, pl0, pl1, phash, path, depth + 1,
                              g + 1.0, bound, hw, weight, wordcap,
                              tk, tv, tmask, budget, seen)
        if ok:
            return True, cand, seen
        if cand < nxt:
            nxt = cand
    return False, nxt, seen


@njit(cache=False)
def search(r0, n0, r1, n1, hw, weight, wordcap, budget, table_bits, max_rounds,
           start_bound):
    size = 1 << table_bits if table_bits > 0 else 1
    tmask = np.uint64(size - 1) if table_bits > 0 else np.uint64(0)
    tk = np.zeros(size, dtype=np.uint64)
    tv = np.full(size, 32767, dtype=np.int32)

    pw0 = np.zeros(MAXDEPTH * MAXLEN, dtype=np.int8)
    pw1 = np.zeros(MAXDEPTH * MAXLEN, dtype=np.int8)
    pl0 = np.zeros(MAXDEPTH, dtype=np.int16)
    pl1 = np.zeros(MAXDEPTH, dtype=np.int16)
    phash = np.zeros(MAXDEPTH, dtype=np.uint64)
    path = np.zeros(MAXDEPTH, dtype=np.int8)

    for i in range(n0):
        pw0[i] = r0[i]
    for i in range(n1):
        pw1[i] = r1[i]
    pl0[0] = n0
    pl1[0] = n1
    phash[0] = _hash(r0, n0, r1, n1)

    # Starting the bound AT the record turns the search into a decision
    # problem: is there a path of at most that length? A* has already given us
    # an upper bound, so optimising from the heuristic upward wastes the
    # iterations below the record that cannot score anyway.
    if start_bound > 0.0:
        bound = start_bound
    else:
        bound = weight * _h(hw, r0, n0, r1, n1)
    total = 0
    for _ in range(max_rounds):
        for i in range(size):
            tv[i] = 32767
            tk[i] = np.uint64(0)
        ok, nxt, seen = _dfs(pw0, pw1, pl0, pl1, phash, path, 0, 0.0, bound,
                             hw, weight, wordcap, tk, tv, tmask, budget, 0)
        total += seen
        if ok:
            d = 0
            while d < MAXDEPTH and pl0[d] != 0:
                d += 1
            return True, path, total, bound
        if nxt > 1.0e17 or total > budget:
            return False, path, total, bound
        bound = nxt
    return False, path, total, bound


_W = None


def weights():
    global _W
    if _W is None:
        _W = np.load(REPO / "runs/pool/heuristic.npz")["w"].astype(np.float64)
    return _W


def solve(relators, weight=1.0, budget=40_000_000, table_bits=22,
          wordcap=MAXLEN - 2, max_rounds=60, start_bound=0.0):
    r0 = np.array(relators[0], dtype=np.int8)
    r1 = np.array(relators[1], dtype=np.int8)
    found, path, nodes, bound = search(r0, len(r0), r1, len(r1), weights(),
                                       weight, wordcap, budget, table_bits,
                                       max_rounds, start_bound)
    if not found:
        return None, int(nodes)
    # the path length is the bound reached, recovered by replaying
    from src.search import engine as E
    state = tuple(tuple(w) for w in relators)
    ids = []
    for mid in path:
        if state == E.TARGET:
            break
        ids.append(int(mid))
        state = E.step(state, int(mid))
        if state == E.TARGET:
            break
    return ids, int(nodes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--min-held", type=int, default=19)
    ap.add_argument("--max-held", type=int, default=30)
    ap.add_argument("--max-k", type=int, default=0)
    ap.add_argument("--skip-held", action="store_true")
    ap.add_argument("--weight", type=float, default=1.0)
    ap.add_argument("--budget", type=int, default=40_000_000)
    ap.add_argument("--table-bits", type=int, default=22)
    ap.add_argument("--limit", type=int, default=2000)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--at-record", action="store_true",
                    help="start the f bound at the record: ask only whether a "
                         "path that would score exists, not what the optimum is")
    ap.add_argument("--shorten", action="store_true")
    ap.add_argument("--out", default="runs/pool/ida")
    args = ap.parse_args()

    from src.ac.moves import Destabilize
    from src.ac.presentation import Presentation
    from src.ac.verify import move_to_json, verify
    from src.search import engine as E

    rows = [json.loads(l) for l in
            open(REPO / "runs/pool/pool.jsonl", encoding="utf-8")]

    if args.check:
        known = [r for r in rows if r["ac_best"] is not None
                 and r["ac_best"] <= 16][:8]
        solve(known[0]["relators"], args.weight, 200_000, 16)
        ok = 0
        for r in known:
            t0 = time.time()
            ids, nodes = solve(r["relators"], args.weight, args.budget,
                               args.table_bits)
            if ids is None:
                print(f"  {r['ac_id']} record {r['ac_best']:>2}: none "
                      f"({nodes:,} nodes, {time.time()-t0:.1f}s)", flush=True)
                continue
            good = verify(Presentation(2, tuple(tuple(w) for w in r["relators"])),
                          [E.to_move(m) for m in ids], stable=False)
            ok += bool(good)
            print(f"  {r['ac_id']} record {r['ac_best']:>2}: {len(ids):>3} "
                  f"({nodes:,} nodes, {time.time()-t0:.1f}s, verified {bool(good)})",
                  flush=True)
        print(f"\ncheck: {ok}/{len(known)} solved and verified", flush=True)
        sys.stdout.flush()
        os._exit(0)

    band = [r for r in rows if r["ac_best"] is not None
            and args.min_held <= r["ac_best"] <= args.max_held]
    if args.max_k:
        band = [r for r in band if r["ac_k"] <= args.max_k]
    if args.skip_held:
        held = {json.loads(l)["challenge_id"].replace("sac-", "ac-")
                for l in open(REPO / "runs/pool/LEDGER.jsonl", encoding="utf-8")}
        band = [r for r in band if r["ac_id"] not in held]
    band.sort(key=lambda r: (r["ac_best"], len(r["relators"][0]) + len(r["relators"][1])))
    band = band[:args.limit][args.shard::args.nshards]
    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    print(f"{len(band)} challenges, IDA* weight {args.weight}, "
          f"budget {args.budget:,} nodes, memory O(depth)", flush=True)
    solve(band[0]["relators"], args.weight, 200_000, 16)

    found = scoring = 0
    with (out / "solutions.jsonl").open("a", encoding="utf-8") as log:
        for r in band:
            start = tuple(tuple(w) for w in r["relators"])
            rec = r["ac_best"]
            t0 = time.time()
            sb = float(rec) if args.at_record else 0.0
            ids, nodes = solve(r["relators"], args.weight, args.budget,
                               args.table_bits, MAXLEN - 2, 60, sb)
            dt_s = time.time() - t0
            if not ids:
                print(f"  {r['ac_id']} record {rec:>4}: none "
                      f"({nodes:,} nodes, {dt_s:.1f}s)", flush=True)
                continue
            raw = len(ids)
            if args.shorten:
                try:
                    cut = E.shorten(start, ids, depth=3)
                    if len(cut) < len(ids):
                        ids = cut
                except Exception:
                    pass
            ac = [E.to_move(m) for m in ids]
            begin = Presentation(2, start)
            if not verify(begin, ac, stable=False):
                print(f"  {r['ac_id']}: path did not verify, skipped", flush=True)
                continue
            found += 1
            stable = ac + [Destabilize(1), Destabilize(0)]
            if not verify(begin, stable, stable=True):
                continue
            scores = len(ac) <= rec
            scoring += scores
            stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            for problem, moves in (("ac", ac), ("stable_ac", stable)):
                log.write(json.dumps({"id": r["id"], "problem": problem,
                                      "length": len(moves),
                                      "moves": [move_to_json(m) for m in moves],
                                      "relators": r["relators"], "found_at": stamp,
                                      "cfg": {"method": "idastar"}}) + "\n")
            log.flush()
            cutnote = f" (cut from {raw})" if len(ids) < raw else ""
            print(f"  {r['ac_id']} record {rec:>4} (k {r['ac_k']}): "
                  f"ours {len(ac):>3}{cutnote} ({nodes:,} nodes, {dt_s:.1f}s)"
                  f"{'  <-- SCORES' if scores else ''}", flush=True)
    print(f"\nfound {found}/{len(band)}, scoring {scoring}", flush=True)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()

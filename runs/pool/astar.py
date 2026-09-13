"""Weighted A* with a learned distance-to-trivial heuristic.

`bestfirst.py` orders its queue by total_length + w * moves_spent, and the
measurements show no single w serves the pool: a large w returns exact minima
but cannot reach a long path, a small w reaches it and wanders. The formula is
the ceiling, not the budget.

`learn_heuristic.py` replaces the formula with an estimate fitted to states
along paths we already hold at record length, where the true distance to the
trivial pair is known exactly. On held-out measurement it predicts that distance
to a mean of 3.0 moves against 5.6 for total length alone.

Here that estimate drives the search: priority = moves spent + W * predicted
moves remaining. W = 1 is ordinary A*; larger W trades optimality for reach,
which is the trade the whole campaign has been fighting by hand.

The search runs forward only. The heuristic answers "how far from trivial",
which is exactly what the forward half needs and gives the backward half
nothing, since a state grown out of the trivial pair already knows its own depth.

Usage (from the repo root):
  python runs/pool/astar.py --check
  python runs/pool/astar.py --min-held 31 --max-held 60 --weight 2
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
from jit_engine import MAXLEN, _apply, _hash  # noqa: E402


@njit(cache=False, inline="always")
def _h(w, a, la, b, lb):
    """Predicted moves from this presentation to the trivial pair.

    Same nine features as the fitted model, in the same order."""
    ea = 0
    eb = 0
    for i in range(la):
        g = a[i]
        if g == 1:
            ea += 1
        elif g == -1:
            ea -= 1
        elif g == 2:
            eb += 1
        elif g == -2:
            eb -= 1
    ec = 0
    ed = 0
    for i in range(lb):
        g = b[i]
        if g == 1:
            ec += 1
        elif g == -1:
            ec -= 1
        elif g == 2:
            ed += 1
        elif g == -2:
            ed -= 1
    alt = 0
    for i in range(la - 1):
        if (a[i] > 0) != (a[i + 1] > 0):
            alt += 1
    for i in range(lb - 1):
        if (b[i] > 0) != (b[i + 1] > 0):
            alt += 1
    det = ea * ed - eb * ec
    if det < 0:
        det = -det
    mx = la if la > lb else lb
    mn = lb if la > lb else la
    triv = 1.0 if (la == 1 and lb == 1) else 0.0
    v = (w[0] * (la + lb) + w[1] * abs(la - lb)
         + w[2] * (abs(ea) + abs(eb) + abs(ec) + abs(ed))
         + w[3] * det + w[4] * alt + w[5] * mx + w[6] * mn
         + w[7] * triv + w[8])
    if v < 0.0:
        v = 0.0
    return v


@njit(cache=False)
def search(r0, n0, r1, n1, max_nodes, table_bits, wordcap, weight, hw):
    """A path to (x, y) or nothing. Priority is g + weight * h."""
    size = 1 << table_bits
    mask = np.uint64(size - 1)
    nbucket = 8192

    keys = np.zeros(size, dtype=np.uint64)
    w0 = np.zeros(max_nodes * MAXLEN, dtype=np.int8)
    w1 = np.zeros(max_nodes * MAXLEN, dtype=np.int8)
    l0 = np.zeros(max_nodes, dtype=np.int16)
    l1 = np.zeros(max_nodes, dtype=np.int16)
    parent = np.full(max_nodes, -1, dtype=np.int32)
    pmove = np.zeros(max_nodes, dtype=np.int8)
    depth = np.zeros(max_nodes, dtype=np.int16)
    nxt = np.full(max_nodes, -1, dtype=np.int32)
    head = np.full(nbucket, -1, dtype=np.int32)

    o0 = np.zeros(MAXLEN, dtype=np.int8)
    o1 = np.zeros(MAXLEN, dtype=np.int8)
    buf = np.zeros(MAXLEN, dtype=np.int8)
    tmp = np.zeros(MAXLEN + 2, dtype=np.int8)
    path = np.zeros(4096, dtype=np.int8)

    for i in range(n0):
        w0[i] = r0[i]
    for i in range(n1):
        w1[i] = r1[i]
    l0[0] = n0
    l1[0] = n1
    count = 1
    p0 = int(weight * _h(hw, r0, n0, r1, n1))
    if p0 >= nbucket:
        p0 = nbucket - 1
    head[p0] = 0
    best = p0
    h = _hash(r0, n0, r1, n1)
    j = h & mask
    while keys[j] != np.uint64(0):
        j = (j + np.uint64(1)) & mask
    keys[j] = h

    while count < max_nodes:
        while best < nbucket and head[best] == -1:
            best += 1
        if best >= nbucket:
            return False, 0, path, count
        cur = head[best]
        head[best] = nxt[cur]
        la = l0[cur]
        lb = l1[cur]
        d = depth[cur]
        a0 = cur * MAXLEN
        for mid in range(14):
            na, nb = _apply(mid, w0[a0:a0 + MAXLEN], la, w1[a0:a0 + MAXLEN], lb,
                            o0, o1, buf, tmp)
            if na == 0 or nb == 0 or na > wordcap or nb > wordcap:
                continue
            # the target is the ORDERED pair (x, y), not any two distinct
            # generators: (y, x) and (x^-1, y) are different presentations
            # and the official verifier rejects a path that stops there
            if na == 1 and nb == 1 and o0[0] == 1 and o1[0] == 2:
                m = 0
                path[m] = mid
                m += 1
                node = cur
                while parent[node] != -1:
                    path[m] = pmove[node]
                    m += 1
                    node = parent[node]
                for i in range(m // 2):
                    t = path[i]
                    path[i] = path[m - 1 - i]
                    path[m - 1 - i] = t
                return True, m, path, count
            hh = _hash(o0, na, o1, nb)
            j = hh & mask
            seen = False
            while keys[j] != np.uint64(0):
                if keys[j] == hh:
                    seen = True
                    break
                j = (j + np.uint64(1)) & mask
            if seen:
                continue
            if count >= max_nodes:
                return False, 0, path, count
            keys[j] = hh
            b0 = count * MAXLEN
            for i in range(na):
                w0[b0 + i] = o0[i]
            for i in range(nb):
                w1[b0 + i] = o1[i]
            l0[count] = na
            l1[count] = nb
            parent[count] = cur
            pmove[count] = mid
            depth[count] = d + 1
            pr = (d + 1) + int(weight * _h(hw, o0, na, o1, nb))
            if pr >= nbucket:
                pr = nbucket - 1
            if pr < 0:
                pr = 0
            nxt[count] = head[pr]
            head[pr] = count
            if pr < best:
                best = pr
            count += 1
    return False, 0, path, count


_W = None


def weights():
    global _W
    if _W is None:
        _W = np.load(REPO / "runs/pool/heuristic.npz")["w"].astype(np.float64)
    return _W


def solve(relators, max_nodes=4_000_000, table_bits=23, wordcap=MAXLEN - 2,
          weight=1.0):
    r0 = np.array(relators[0], dtype=np.int8)
    r1 = np.array(relators[1], dtype=np.int8)
    found, m, path, nodes = search(r0, len(r0), r1, len(r1), max_nodes,
                                   table_bits, wordcap, weight, weights())
    return ([int(x) for x in path[:m]] if found else None), int(nodes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--min-held", type=int, default=31)
    ap.add_argument("--max-held", type=int, default=60)
    ap.add_argument("--unsolved", action="store_true")
    ap.add_argument("--weight", type=float, default=1.0)
    ap.add_argument("--max-nodes", type=int, default=4_000_000)
    ap.add_argument("--table-bits", type=int, default=23)
    ap.add_argument("--wordcap", type=int, default=MAXLEN - 2)
    ap.add_argument("--limit", type=int, default=4000)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--shorten", action="store_true")
    ap.add_argument("--out", default="runs/pool/astar")
    args = ap.parse_args()

    from src.ac.moves import Destabilize
    from src.ac.presentation import Presentation
    from src.ac.verify import move_to_json, verify
    from src.search import engine as E

    rows = [json.loads(l) for l in
            open(REPO / "runs/pool/pool.jsonl", encoding="utf-8")]

    if args.check:
        known = [r for r in rows if r["ac_best"] is not None
                 and r["ac_best"] <= 16][:10]
        solve(known[0]["relators"], 100_000, 18, args.wordcap, args.weight)
        ok = 0
        for r in known:
            t0 = time.time()
            ids, nodes = solve(r["relators"], args.max_nodes, args.table_bits,
                               args.wordcap, args.weight)
            if ids is None:
                print(f"  {r['ac_id']} record {r['ac_best']:>2}: none "
                      f"({nodes:,} nodes)", flush=True)
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

    if args.unsolved:
        band = [r for r in rows if r["ac_best"] is None]
    else:
        band = [r for r in rows if r["ac_best"] is not None
                and args.min_held <= r["ac_best"] <= args.max_held]
    band.sort(key=lambda r: (r["ac_best"] or 0,
                             len(r["relators"][0]) + len(r["relators"][1])))
    band = band[:args.limit][args.shard::args.nshards]
    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    print(f"{len(band)} challenges, A* with the learned heuristic, "
          f"weight {args.weight}, {args.max_nodes:,} nodes", flush=True)
    solve(band[0]["relators"], 100_000, 18, args.wordcap, args.weight)

    found = scoring = 0
    with (out / "solutions.jsonl").open("a", encoding="utf-8") as log:
        for r in band:
            start = tuple(tuple(w) for w in r["relators"])
            t0 = time.time()
            ids, nodes = solve(r["relators"], args.max_nodes, args.table_bits,
                               args.wordcap, args.weight)
            dt_s = time.time() - t0
            rec = r["ac_best"]
            if ids is None:
                print(f"  {r['ac_id']} record {rec if rec is not None else '--':>4}:"
                      f" none ({nodes:,} nodes, {dt_s:.1f}s)", flush=True)
                continue
            raw = len(ids)
            if args.shorten:
                try:
                    cut = E.shorten(start, ids, depth=3)
                    if len(cut) < len(ids):
                        ids = cut
                except Exception:
                    pass
            found += 1
            ac = [E.to_move(m) for m in ids]
            stable = ac + [Destabilize(1), Destabilize(0)]
            begin = Presentation(2, start)
            if not verify(begin, ac, stable=False) or \
                    not verify(begin, stable, stable=True):
                raise AssertionError("A* produced an unverifiable path")
            scores = rec is None or len(ac) <= rec
            scoring += scores
            stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            for problem, moves in (("ac", ac), ("stable_ac", stable)):
                log.write(json.dumps({"id": r["id"], "problem": problem,
                                      "length": len(moves),
                                      "moves": [move_to_json(m) for m in moves],
                                      "relators": r["relators"], "found_at": stamp,
                                      "cfg": {"method": "astar-learned"}}) + "\n")
            log.flush()
            cutnote = f" (cut from {raw})" if len(ids) < raw else ""
            print(f"  {r['ac_id']} record {rec if rec is not None else '--':>4} "
                  f"(k {r['ac_k']}): ours {len(ac):>3}{cutnote} "
                  f"({nodes:,} nodes, {dt_s:.1f}s)"
                  f"{'  <-- SCORES' if scores else ''}", flush=True)
    print(f"\nfound {found}/{len(band)}, scoring {scoring}", flush=True)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()

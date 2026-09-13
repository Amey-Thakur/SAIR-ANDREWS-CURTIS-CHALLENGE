"""Bidirectional best-first search, with length as a priority and not a wall.

Everything else in this campaign caps total relator length at size + slack and
throws away any state above it. That cap is why we lose. A good Andrews-Curtis
path usually goes UPHILL first, lengthening the relators before they collapse,
and a hard cap forbids exactly that, so our searches are pushed around the long
way: we return 70 to 140 moves where the record is 30 to 50. Widening the cap
does not fix it either, because a wider hard box explodes combinatorially and
the search then finds nothing at all. Both failures were measured.

Here total length orders a bucket queue instead of gating admission. Uphill
states remain reachable, they are just explored last, so the search can follow
a route that climbs and then falls. The only hard bound left is the compiled
word buffer.

Both halves run best-first and meet in the middle. The move set is closed under
inversion, so a state reached from the target by m1..mk returns by
INV[mk]..INV[m1].

Usage (from the repo root):
  python runs/pool/bestfirst.py --check
  python runs/pool/bestfirst.py --min-held 31 --max-held 60
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

INV = np.array([0, 1, 3, 2, 5, 4, 7, 6, 9, 8, 11, 10, 13, 12], dtype=np.int8)


@njit(cache=False)
def search(r0, n0, r1, n1, max_nodes, table_bits, wordcap, dw):
    """A short move sequence from the presentation to (x, y), or nothing.

    Returns (found, length, path, nodes). Best-first, so the answer is a good
    path rather than a proven minimum; the verifier decides if it scores."""
    size = 1 << table_bits
    mask = np.uint64(size - 1)
    # priority is total length plus dw moves spent. Pure length-greedy wanders
    # and returns paths many times the record; charging for depth pulls the
    # search toward short routes without ever forbidding an uphill step.
    nbucket = 4096

    fk = np.zeros(size, dtype=np.uint64)
    fv = np.zeros(size, dtype=np.int32)
    bk = np.zeros(size, dtype=np.uint64)
    bv = np.zeros(size, dtype=np.int32)

    fw0 = np.zeros(max_nodes * MAXLEN, dtype=np.int8)
    fw1 = np.zeros(max_nodes * MAXLEN, dtype=np.int8)
    fl0 = np.zeros(max_nodes, dtype=np.int16)
    fl1 = np.zeros(max_nodes, dtype=np.int16)
    fp = np.full(max_nodes, -1, dtype=np.int32)
    fm = np.zeros(max_nodes, dtype=np.int8)
    fnx = np.full(max_nodes, -1, dtype=np.int32)
    fhead = np.full(nbucket, -1, dtype=np.int32)

    bw0 = np.zeros(max_nodes * MAXLEN, dtype=np.int8)
    bw1 = np.zeros(max_nodes * MAXLEN, dtype=np.int8)
    bl0 = np.zeros(max_nodes, dtype=np.int16)
    bl1 = np.zeros(max_nodes, dtype=np.int16)
    bp = np.full(max_nodes, -1, dtype=np.int32)
    bm = np.zeros(max_nodes, dtype=np.int8)
    bnx = np.full(max_nodes, -1, dtype=np.int32)
    bhead = np.full(nbucket, -1, dtype=np.int32)

    o0 = np.zeros(MAXLEN, dtype=np.int8)
    o1 = np.zeros(MAXLEN, dtype=np.int8)
    buf = np.zeros(MAXLEN, dtype=np.int8)
    tmp = np.zeros(MAXLEN + 2, dtype=np.int8)
    path = np.zeros(4096, dtype=np.int8)

    for i in range(n0):
        fw0[i] = r0[i]
    for i in range(n1):
        fw1[i] = r1[i]
    fl0[0] = n0
    fl1[0] = n1
    fcount = 1
    fdepth = np.zeros(max_nodes, dtype=np.int16)
    bdepth = np.zeros(max_nodes, dtype=np.int16)
    fhead[n0 + n1] = 0
    h = _hash(r0, n0, r1, n1)
    j = h & mask
    while fk[j] != np.uint64(0):
        j = (j + np.uint64(1)) & mask
    fk[j] = h
    fv[j] = 0
    fbest = n0 + n1

    bw0[0] = 1
    bw1[0] = 2
    bl0[0] = 1
    bl1[0] = 1
    bcount = 1
    bhead[2] = 0
    t0 = np.zeros(1, dtype=np.int8)
    t1 = np.zeros(1, dtype=np.int8)
    t0[0] = 1
    t1[0] = 2
    h = _hash(t0, 1, t1, 1)
    j = h & mask
    while bk[j] != np.uint64(0):
        j = (j + np.uint64(1)) & mask
    bk[j] = h
    bv[j] = 0
    bbest = 2

    while fcount < max_nodes and bcount < max_nodes:
        # take a turn on whichever side has explored less
        forward = fcount <= bcount

        if forward:
            while fbest < nbucket and fhead[fbest] == -1:
                fbest += 1
            if fbest >= nbucket:
                return False, 0, path, fcount + bcount
            cur = fhead[fbest]
            fhead[fbest] = fnx[cur]
            la = fl0[cur]
            lb = fl1[cur]
            dcur = fdepth[cur]
            a0 = cur * MAXLEN
            src0 = fw0
            src1 = fw1
        else:
            while bbest < nbucket and bhead[bbest] == -1:
                bbest += 1
            if bbest >= nbucket:
                return False, 0, path, fcount + bcount
            cur = bhead[bbest]
            bhead[bbest] = bnx[cur]
            la = bl0[cur]
            lb = bl1[cur]
            dcur = bdepth[cur]
            a0 = cur * MAXLEN
            src0 = bw0
            src1 = bw1

        for mid in range(14):
            na, nb = _apply(mid, src0[a0:a0 + MAXLEN], la,
                            src1[a0:a0 + MAXLEN], lb, o0, o1, buf, tmp)
            # the only hard bound is the compiled buffer, not a length policy
            if na == 0 or nb == 0 or na > wordcap or nb > wordcap:
                continue
            hh = _hash(o0, na, o1, nb)

            own_k = fk if forward else bk
            j = hh & mask
            seen = False
            while own_k[j] != np.uint64(0):
                if own_k[j] == hh:
                    seen = True
                    break
                j = (j + np.uint64(1)) & mask
            if seen:
                continue

            other_k = bk if forward else fk
            other_v = bv if forward else fv
            j2 = hh & mask
            met = -1
            while other_k[j2] != np.uint64(0):
                if other_k[j2] == hh:
                    met = other_v[j2]
                    break
                j2 = (j2 + np.uint64(1)) & mask
            if met >= 0:
                m = 0
                if forward:
                    path[m] = mid
                    m += 1
                    node = cur
                    while fp[node] != -1:
                        path[m] = fm[node]
                        m += 1
                        node = fp[node]
                    for i in range(m // 2):
                        t = path[i]
                        path[i] = path[m - 1 - i]
                        path[m - 1 - i] = t
                    node = met
                    while bp[node] != -1:
                        path[m] = INV[bm[node]]
                        m += 1
                        node = bp[node]
                else:
                    node = met
                    k = 0
                    while fp[node] != -1:
                        path[k] = fm[node]
                        k += 1
                        node = fp[node]
                    for i in range(k // 2):
                        t = path[i]
                        path[i] = path[k - 1 - i]
                        path[k - 1 - i] = t
                    m = k
                    path[m] = INV[mid]
                    m += 1
                    node = cur
                    while bp[node] != -1:
                        path[m] = INV[bm[node]]
                        m += 1
                        node = bp[node]
                return True, m, path, fcount + bcount

            t = na + nb + dw * (dcur + 1)
            if t >= nbucket:
                continue
            if forward:
                if fcount >= max_nodes:
                    return False, 0, path, fcount + bcount
                own_k[j] = hh
                fv[j] = fcount
                b0 = fcount * MAXLEN
                for i in range(na):
                    fw0[b0 + i] = o0[i]
                for i in range(nb):
                    fw1[b0 + i] = o1[i]
                fl0[fcount] = na
                fl1[fcount] = nb
                fp[fcount] = cur
                fm[fcount] = mid
                fdepth[fcount] = dcur + 1
                fnx[fcount] = fhead[t]
                fhead[t] = fcount
                if t < fbest:
                    fbest = t
                fcount += 1
            else:
                if bcount >= max_nodes:
                    return False, 0, path, fcount + bcount
                own_k[j] = hh
                bv[j] = bcount
                b0 = bcount * MAXLEN
                for i in range(na):
                    bw0[b0 + i] = o0[i]
                for i in range(nb):
                    bw1[b0 + i] = o1[i]
                bl0[bcount] = na
                bl1[bcount] = nb
                bp[bcount] = cur
                bm[bcount] = mid
                bdepth[bcount] = dcur + 1
                bnx[bcount] = bhead[t]
                bhead[t] = bcount
                if t < bbest:
                    bbest = t
                bcount += 1
    return False, 0, path, fcount + bcount


def solve(relators, max_nodes=4_000_000, table_bits=23, wordcap=MAXLEN - 2,
          dw=1):
    r0 = np.array(relators[0], dtype=np.int8)
    r1 = np.array(relators[1], dtype=np.int8)
    found, m, path, nodes = search(r0, len(r0), r1, len(r1),
                                   max_nodes, table_bits, wordcap, dw)
    return ([int(x) for x in path[:m]] if found else None), int(nodes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--min-held", type=int, default=31)
    ap.add_argument("--max-held", type=int, default=60)
    ap.add_argument("--unsolved", action="store_true")
    ap.add_argument("--max-nodes", type=int, default=4_000_000)
    ap.add_argument("--table-bits", type=int, default=23)
    ap.add_argument("--wordcap", type=int, default=MAXLEN - 2)
    ap.add_argument("--depth-weight", type=int, default=1,
                    help="how much each move spent costs against total length")
    ap.add_argument("--limit", type=int, default=4000)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--shorten", action="store_true")
    ap.add_argument("--out", default="runs/pool/bf")
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
        solve(known[0]["relators"], 100_000, 18, MAXLEN - 2, args.depth_weight)
        ok = bad = 0
        for r in known:
            t0 = time.time()
            ids, nodes = solve(r["relators"], args.max_nodes, args.table_bits,
                               args.wordcap, args.depth_weight)
            if ids is None:
                print(f"  {r['ac_id']} record {r['ac_best']:>2}: none", flush=True)
                bad += 1
                continue
            good = verify(Presentation(2, tuple(tuple(w) for w in r["relators"])),
                          [E.to_move(m) for m in ids], stable=False)
            ok += bool(good)
            print(f"  {r['ac_id']} record {r['ac_best']:>2}: {len(ids):>3} "
                  f"({nodes:,} nodes, {time.time()-t0:.1f}s, verified {bool(good)})",
                  flush=True)
        print(f"\ncheck: {ok}/{len(known)} solved and verified", flush=True)
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
    print(f"{len(band)} challenges, best-first, no length cap, "
          f"{args.max_nodes:,} nodes/side, word cap {args.wordcap}", flush=True)
    solve(band[0]["relators"], 100_000, 18, MAXLEN - 2, args.depth_weight)

    found = scoring = 0
    with (out / "solutions.jsonl").open("a", encoding="utf-8") as log:
        for r in band:
            start = tuple(tuple(w) for w in r["relators"])
            t0 = time.time()
            ids, nodes = solve(r["relators"], args.max_nodes, args.table_bits,
                               args.wordcap, args.depth_weight)
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
                raise AssertionError("best-first produced an unverifiable path")
            scores = rec is None or len(ac) <= rec
            scoring += scores
            stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            for problem, moves in (("ac", ac), ("stable_ac", stable)):
                log.write(json.dumps({"id": r["id"], "problem": problem,
                                      "length": len(moves),
                                      "moves": [move_to_json(m) for m in moves],
                                      "relators": r["relators"], "found_at": stamp,
                                      "cfg": {"method": "bestfirst-bidir"}}) + "\n")
            log.flush()
            cutnote = f" (cut from {raw})" if len(ids) < raw else ""
            print(f"  {r['ac_id']} record {rec if rec is not None else '--':>4} "
                  f"(k {r['ac_k']}): ours {len(ac):>3}{cutnote} "
                  f"({nodes:,} nodes, {dt_s:.1f}s)"
                  f"{'  <-- SCORES' if scores else ''}", flush=True)
    print(f"\nfound {found}/{len(band)}, scoring {scoring}", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()

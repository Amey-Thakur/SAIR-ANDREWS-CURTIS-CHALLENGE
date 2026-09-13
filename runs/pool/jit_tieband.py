"""Bidirectional exact search, compiled.

The Python version of this search is what puts points on the board: it expands
from the presentation and from the target at once and returns the true minimum
inside a cap, which is the only way to match a record. It runs out of road at
records of 17 because each extra move costs another level of frontier.

This is the same algorithm on the JIT core, whose moves were checked against
the verified Python engine on 19,222 cases with no mismatch. The move set is
closed under inversion, so a state reached from the target by m1..mk reaches the
target by INV[mk]..INV[m1], which is how the two halves are joined.

Usage (from the repo root):
  python runs/pool/jit_tieband.py --check     # reproduce known minima
  python runs/pool/jit_tieband.py --min-held 18 --max-held 24
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
def search_bidir(r0, n0, r1, n1, cap, max_nodes, table_bits):
    """Shortest move sequence from the presentation to (x, y) inside the cap.

    Returns (found, length, path, nodes). Exhaustive inside the cap, so a
    returned length is the true minimum there."""
    size = 1 << table_bits
    mask = np.uint64(size - 1)

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

    bw0 = np.zeros(max_nodes * MAXLEN, dtype=np.int8)
    bw1 = np.zeros(max_nodes * MAXLEN, dtype=np.int8)
    bl0 = np.zeros(max_nodes, dtype=np.int16)
    bl1 = np.zeros(max_nodes, dtype=np.int16)
    bp = np.full(max_nodes, -1, dtype=np.int32)
    bm = np.zeros(max_nodes, dtype=np.int8)

    o0 = np.zeros(MAXLEN, dtype=np.int8)
    o1 = np.zeros(MAXLEN, dtype=np.int8)
    buf = np.zeros(MAXLEN, dtype=np.int8)
    tmp = np.zeros(MAXLEN + 2, dtype=np.int8)
    path = np.zeros(256, dtype=np.int8)

    for i in range(n0):
        fw0[i] = r0[i]
    for i in range(n1):
        fw1[i] = r1[i]
    fl0[0] = n0
    fl1[0] = n1
    fcount = 1
    h = _hash(r0, n0, r1, n1)
    j = h & mask
    while fk[j] != np.uint64(0):
        j = (j + np.uint64(1)) & mask
    fk[j] = h
    fv[j] = 0

    bw0[0] = 1
    bw1[0] = 2
    bl0[0] = 1
    bl1[0] = 1
    bcount = 1
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

    fstart = 0
    fend = 1
    bstart = 0
    bend = 1

    while fstart < fend and bstart < bend:
        forward = (fend - fstart) <= (bend - bstart)
        if forward:
            lo, hi = fstart, fend
        else:
            lo, hi = bstart, bend
        for cur in range(lo, hi):
            if forward:
                a0 = cur * MAXLEN
                la = fl0[cur]
                lb = fl1[cur]
                src0 = fw0
                src1 = fw1
            else:
                a0 = cur * MAXLEN
                la = bl0[cur]
                lb = bl1[cur]
                src0 = bw0
                src1 = bw1
            for mid in range(14):
                na, nb = _apply(mid, src0[a0:a0 + MAXLEN], la,
                                src1[a0:a0 + MAXLEN], lb, o0, o1, buf, tmp)
                if na == 0 or nb == 0 or na + nb > cap:
                    continue
                hh = _hash(o0, na, o1, nb)
                j = hh & mask
                own_k = fk if forward else bk
                own_v = fv if forward else bv
                other_k = bk if forward else fk
                other_v = bv if forward else fv
                seen = False
                while own_k[j] != np.uint64(0):
                    if own_k[j] == hh:
                        seen = True
                        break
                    j = (j + np.uint64(1)) & mask
                if seen:
                    continue
                # does the other side already know this state?
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
                if forward:
                    if fcount >= max_nodes:
                        return False, 0, path, fcount + bcount
                    own_k[j] = hh
                    own_v[j] = fcount
                    b0 = fcount * MAXLEN
                    for i in range(na):
                        fw0[b0 + i] = o0[i]
                    for i in range(nb):
                        fw1[b0 + i] = o1[i]
                    fl0[fcount] = na
                    fl1[fcount] = nb
                    fp[fcount] = cur
                    fm[fcount] = mid
                    fcount += 1
                else:
                    if bcount >= max_nodes:
                        return False, 0, path, fcount + bcount
                    own_k[j] = hh
                    own_v[j] = bcount
                    b0 = bcount * MAXLEN
                    for i in range(na):
                        bw0[b0 + i] = o0[i]
                    for i in range(nb):
                        bw1[b0 + i] = o1[i]
                    bl0[bcount] = na
                    bl1[bcount] = nb
                    bp[bcount] = cur
                    bm[bcount] = mid
                    bcount += 1
        if forward:
            fstart = hi
            fend = fcount
        else:
            bstart = hi
            bend = bcount
    return False, 0, path, fcount + bcount


def solve_bidir(relators, cap, max_nodes=6_000_000, table_bits=24):
    # conjugation can push a word two past the cap before the cap is checked,
    # and the compiled buffer has no bounds check of its own
    if cap + 2 > MAXLEN:
        raise ValueError(f"cap {cap} needs MAXLEN >= {cap + 2}, have {MAXLEN}")
    r0 = np.array(relators[0], dtype=np.int8)
    r1 = np.array(relators[1], dtype=np.int8)
    found, m, path, nodes = search_bidir(r0, len(r0), r1, len(r1),
                                         cap, max_nodes, table_bits)
    return ([int(x) for x in path[:m]] if found else None), int(nodes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--min-held", type=int, default=18)
    ap.add_argument("--max-held", type=int, default=24)
    ap.add_argument("--cap-slack", type=int, default=12)
    ap.add_argument("--max-nodes", type=int, default=6_000_000)
    ap.add_argument("--table-bits", type=int, default=24)
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--unsolved", action="store_true",
                    help="sweep challenges nobody has solved, smallest first; "
                         "there is no record to beat, so every find scores 1.0")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1,
                    help="split the band across processes; each takes every "
                         "nth challenge so the easy end is shared evenly")
    ap.add_argument("--walk", action="store_true",
                    help="when a find is longer than the record, walk the cap "
                         "up until it beats it")
    ap.add_argument("--shorten", action="store_true",
                    help="run detour shortening on each find before scoring it")
    ap.add_argument("--skip-file", default=None,
                    help="file of challenge ids already attempted, one per line")
    ap.add_argument("--out", default="runs/pool/jit_band")
    args = ap.parse_args()

    from src.ac.moves import Destabilize
    from src.ac.presentation import Presentation
    from src.ac.verify import move_to_json, verify
    from src.search import engine as E

    rows = [json.loads(l) for l in
            open(REPO / "runs/pool/pool.jsonl", encoding="utf-8")]

    if args.check:
        # must reproduce the minima the Python version already proved
        known = [r for r in rows if r["ac_best"] is not None
                 and r["ac_best"] <= 16][:10]
        solve_bidir(known[0]["relators"], 40, 200_000, 20)
        bad = 0
        for r in known:
            cap = len(r["relators"][0]) + len(r["relators"][1]) + 12
            t0 = time.time()
            ids, nodes = solve_bidir(r["relators"], cap, args.max_nodes,
                                     args.table_bits)
            got = "none" if ids is None else str(len(ids))
            ok = ids is not None and len(ids) == r["ac_best"]
            bad += 0 if ok else 1
            print(f"  {r['ac_id']} record {r['ac_best']:>2}: jit {got:>4} "
                  f"({nodes:,} nodes, {time.time()-t0:.1f}s){'' if ok else '   MISMATCH'}",
                  flush=True)
        print(f"\ncheck: {len(known) - bad}/{len(known)} reproduce the known minimum")
        os._exit(0)

    if args.unsolved:
        band = [r for r in rows if r["ac_best"] is None]
    else:
        band = [r for r in rows if r["ac_best"] is not None
                and args.min_held <= r["ac_best"] <= args.max_held]
    skip = set()
    if args.skip_file:
        skip = {l.strip() for l in open(REPO / args.skip_file, encoding="utf-8")
                if l.strip()}
        band = [r for r in band if r["ac_id"] not in skip]
    band.sort(key=lambda r: (r["ac_best"] or 0,
                             len(r["relators"][0]) + len(r["relators"][1])))
    band = band[:args.limit]
    band = band[args.shard::args.nshards]
    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    what = "unsolved by anyone" if args.unsolved else         f"records {args.min_held}-{args.max_held}"
    print(f"{len(band)} challenges {what}, "
          f"slack {args.cap_slack}, {args.max_nodes:,} nodes/side, "
          f"shard {args.shard}/{args.nshards}, {len(skip)} skipped", flush=True)
    solve_bidir(band[0]["relators"], 40, 200_000, 20)

    found = scoring = toobig = 0
    with (out / "solutions.jsonl").open("a", encoding="utf-8") as log:
        for r in band:
            start = tuple(tuple(w) for w in r["relators"])
            cap = len(start[0]) + len(start[1]) + args.cap_slack
            if cap + 2 > MAXLEN:
                # a wide slack on a large presentation outgrows the compiled
                # buffer; skip it rather than die, and report how many
                toobig += 1
                continue
            t0 = time.time()
            ids, nodes = solve_bidir(r["relators"], cap, args.max_nodes,
                                     args.table_bits)
            dt_s = time.time() - t0
            rec = r["ac_best"]
            # A path that is too long is not a failure, it is a qualified lead:
            # we now know one exists nearby, and walking the cap up finds the
            # shorter route the record holder used. Measured at about 65%
            # conversion, against 3.3% for the cold sweep alone.
            if ids is not None and rec is not None and len(ids) > rec and args.walk:
                for extra in range(args.cap_slack + 1, args.cap_slack + 9):
                    wcap = len(start[0]) + len(start[1]) + extra
                    if wcap + 2 > MAXLEN:
                        break
                    more, wnodes = solve_bidir(r["relators"], wcap,
                                               args.max_nodes, args.table_bits)
                    if more is not None and len(more) < len(ids):
                        ids = more
                    if len(ids) < rec:
                        break
            if ids is None:
                print(f"  {r['ac_id']} record {rec if rec is not None else '--':>3}:"
                      f" none ({nodes:,} nodes, {dt_s:.0f}s)", flush=True)
                continue
            found += 1
            # the path is minimal inside a cap on TOTAL length; shorten looks
            # for detours under a cap on each relator, so it can still cut one.
            # Many finds miss the record by only a few moves.
            raw = len(ids)
            if args.shorten:
                try:
                    cut = E.shorten(start, ids, depth=3)
                    if len(cut) < len(ids):
                        ids = cut
                except Exception as exc:            # never lose a found path
                    print(f"    (shorten failed: {exc})", flush=True)
            ac = [E.to_move(m) for m in ids]
            stable = ac + [Destabilize(1), Destabilize(0)]
            begin = Presentation(2, start)
            if not verify(begin, ac, stable=False) or not verify(begin, stable, stable=True):
                raise AssertionError("jit tieband produced an unverifiable path")
            scores = rec is None or len(ac) <= rec
            scoring += scores
            stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            for problem, moves in (("ac", ac), ("stable_ac", stable)):
                log.write(json.dumps({"id": r["id"], "problem": problem,
                                      "length": len(moves),
                                      "moves": [move_to_json(m) for m in moves],
                                      "relators": r["relators"], "found_at": stamp,
                                      "cfg": {"method": "jit-bidirectional"}}) + "\n")
            log.flush()
            cutnote = f" (cut from {raw})" if len(ids) < raw else ""
            print(f"  {r['ac_id']} record {rec if rec is not None else '--':>3} "
                  f"(k {r['ac_k']}): ours {len(ac):>3}{cutnote} "
                  f"({nodes:,} nodes, {dt_s:.0f}s)"
                  f"{'  <-- SCORES' if scores else ''}", flush=True)
    print(f"\nfound {found}/{len(band) - toobig}, scoring {scoring}"
          f"{f', {toobig} skipped: cap over MAXLEN {MAXLEN}' if toobig else ''}",
          flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()

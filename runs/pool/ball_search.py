"""Bidirectional search that builds the backward ball once and reuses it.

The backward half of `jit_tieband.search_bidir` expands from the trivial target
(x, y) under a single constraint, that total relator length stays inside the
cap. It never looks at the presentation. So every challenge of the same size
rebuilt the identical set of states, and the node counts gave it away: the same
7,226,201 appeared for four different challenges in one run and again in
another.

Here the ball is built once per cap and swept across every challenge of that
size. Two things follow. Each challenge then costs only its forward search,
and the ball can be made far deeper than 5M nodes because the cost is paid once
instead of per challenge, which is what actually raises the find rate.

Minimality is kept. The ball stores the exact distance from the target, the
forward search runs in layers of increasing depth, and the sweep stops only
once the forward depth reaches the best total found, at which point nothing
shorter can remain.

Usage (from the repo root):
  python runs/pool/ball_search.py --check
  python runs/pool/ball_search.py --min-held 121 --cap-slack 2
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
def build_ball(cap, max_nodes, table_bits):
    """Every state within `cap` reachable from the trivial pair, with its exact
    distance from it. Depends only on the cap, so one ball serves every
    challenge whose relators total the same length."""
    size = 1 << table_bits
    mask = np.uint64(size - 1)
    keys = np.zeros(size, dtype=np.uint64)
    slot = np.zeros(size, dtype=np.int32)

    w0 = np.zeros(max_nodes * MAXLEN, dtype=np.int8)
    w1 = np.zeros(max_nodes * MAXLEN, dtype=np.int8)
    l0 = np.zeros(max_nodes, dtype=np.int16)
    l1 = np.zeros(max_nodes, dtype=np.int16)
    parent = np.full(max_nodes, -1, dtype=np.int32)
    pmove = np.zeros(max_nodes, dtype=np.int8)
    depth = np.zeros(max_nodes, dtype=np.int16)

    o0 = np.zeros(MAXLEN, dtype=np.int8)
    o1 = np.zeros(MAXLEN, dtype=np.int8)
    buf = np.zeros(MAXLEN, dtype=np.int8)
    tmp = np.zeros(MAXLEN + 2, dtype=np.int8)

    w0[0] = 1
    w1[0] = 2
    l0[0] = 1
    l1[0] = 1
    count = 1
    t0 = np.zeros(1, dtype=np.int8)
    t1 = np.zeros(1, dtype=np.int8)
    t0[0] = 1
    t1[0] = 2
    h = _hash(t0, 1, t1, 1)
    j = h & mask
    while keys[j] != np.uint64(0):
        j = (j + np.uint64(1)) & mask
    keys[j] = h
    slot[j] = 0

    cur = 0
    while cur < count and count < max_nodes:
        a0 = cur * MAXLEN
        la = l0[cur]
        lb = l1[cur]
        d = depth[cur]
        for mid in range(14):
            na, nb = _apply(mid, w0[a0:a0 + MAXLEN], la, w1[a0:a0 + MAXLEN], lb,
                            o0, o1, buf, tmp)
            if na == 0 or nb == 0 or na + nb > cap:
                continue
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
                break
            keys[j] = hh
            slot[j] = count
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
            count += 1
        cur += 1
    return keys, slot, parent, pmove, depth, count, cur


@njit(cache=False)
def forward_meet(r0, n0, r1, n1, cap, max_nodes, table_bits, ball_bits,
                 ball_keys, ball_slot, ball_parent, ball_move, ball_depth):
    """Shortest path from the presentation into the ball, or nothing.

    Runs forward in layers of increasing depth. A meeting at forward depth df
    with a ball state at distance db gives a path of df + db, so once df
    reaches the best total already found, nothing shorter can remain and the
    search stops. That keeps the answer a true minimum inside the cap."""
    size = 1 << table_bits
    mask = np.uint64(size - 1)
    bmask = np.uint64((1 << ball_bits) - 1)

    keys = np.zeros(size, dtype=np.uint64)
    w0 = np.zeros(max_nodes * MAXLEN, dtype=np.int8)
    w1 = np.zeros(max_nodes * MAXLEN, dtype=np.int8)
    l0 = np.zeros(max_nodes, dtype=np.int16)
    l1 = np.zeros(max_nodes, dtype=np.int16)
    parent = np.full(max_nodes, -1, dtype=np.int32)
    pmove = np.zeros(max_nodes, dtype=np.int8)
    depth = np.zeros(max_nodes, dtype=np.int16)

    o0 = np.zeros(MAXLEN, dtype=np.int8)
    o1 = np.zeros(MAXLEN, dtype=np.int8)
    buf = np.zeros(MAXLEN, dtype=np.int8)
    tmp = np.zeros(MAXLEN + 2, dtype=np.int8)
    path = np.zeros(1024, dtype=np.int8)

    for i in range(n0):
        w0[i] = r0[i]
    for i in range(n1):
        w1[i] = r1[i]
    l0[0] = n0
    l1[0] = n1
    count = 1
    h = _hash(r0, n0, r1, n1)
    j = h & mask
    while keys[j] != np.uint64(0):
        j = (j + np.uint64(1)) & mask
    keys[j] = h

    # the start may already sit inside the ball
    best = 32767
    best_fwd = -1
    best_ball = -1
    j2 = h & bmask
    while ball_keys[j2] != np.uint64(0):
        if ball_keys[j2] == h:
            bi = ball_slot[j2]
            best = ball_depth[bi]
            best_fwd = 0
            best_ball = bi
            break
        j2 = (j2 + np.uint64(1)) & bmask

    cur = 0
    while cur < count:
        d = depth[cur]
        if d >= best:
            break
        a0 = cur * MAXLEN
        la = l0[cur]
        lb = l1[cur]
        for mid in range(14):
            na, nb = _apply(mid, w0[a0:a0 + MAXLEN], la, w1[a0:a0 + MAXLEN], lb,
                            o0, o1, buf, tmp)
            if na == 0 or nb == 0 or na + nb > cap:
                continue
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
                cur = count
                break
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
            # does the ball already know this state?
            j2 = hh & bmask
            while ball_keys[j2] != np.uint64(0):
                if ball_keys[j2] == hh:
                    bi = ball_slot[j2]
                    total = (d + 1) + ball_depth[bi]
                    if total < best:
                        best = total
                        best_fwd = count
                        best_ball = bi
                    break
                j2 = (j2 + np.uint64(1)) & bmask
            count += 1
        cur += 1

    if best_fwd < 0:
        return False, 0, path, count

    m = 0
    node = best_fwd
    while parent[node] != -1:
        path[m] = pmove[node]
        m += 1
        node = parent[node]
    for i in range(m // 2):
        t = path[i]
        path[i] = path[m - 1 - i]
        path[m - 1 - i] = t
    node = best_ball
    while ball_parent[node] != -1:
        path[m] = INV[ball_move[node]]
        m += 1
        node = ball_parent[node]
    return True, m, path, count


class Ball:
    """A backward ball held for one cap, rebuilt only when the cap changes."""

    def __init__(self, cap, max_nodes, table_bits):
        t0 = time.time()
        (self.keys, self.slot, self.parent, self.move, self.depth,
         self.count, self.expanded) = build_ball(cap, max_nodes, table_bits)
        self.cap = cap
        self.bits = table_bits
        self.secs = time.time() - t0
        self.complete = self.expanded >= self.count


def solve(relators, ball, cap, max_nodes=2_000_000, table_bits=22):
    if cap + 2 > MAXLEN:
        raise ValueError(f"cap {cap} needs MAXLEN >= {cap + 2}, have {MAXLEN}")
    r0 = np.array(relators[0], dtype=np.int8)
    r1 = np.array(relators[1], dtype=np.int8)
    found, m, path, nodes = forward_meet(
        r0, len(r0), r1, len(r1), cap, max_nodes, table_bits, ball.bits,
        ball.keys, ball.slot, ball.parent, ball.move, ball.depth)
    return ([int(x) for x in path[:m]] if found else None), int(nodes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--min-held", type=int, default=121)
    ap.add_argument("--max-held", type=int, default=100000)
    ap.add_argument("--unsolved", action="store_true")
    ap.add_argument("--cap-slack", type=int, default=2)
    ap.add_argument("--ball-nodes", type=int, default=12_000_000)
    ap.add_argument("--ball-bits", type=int, default=25)
    ap.add_argument("--fwd-nodes", type=int, default=2_000_000)
    ap.add_argument("--fwd-bits", type=int, default=22)
    ap.add_argument("--limit", type=int, default=4000)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--skip-file", default=None)
    ap.add_argument("--shorten", action="store_true",
                    help="run detour shortening on each find before scoring it")
    ap.add_argument("--shorten-depth", type=int, default=3)
    ap.add_argument("--out", default="runs/pool/ball_run")
    args = ap.parse_args()

    from src.ac.moves import Destabilize
    from src.ac.presentation import Presentation
    from src.ac.verify import move_to_json, verify
    from src.search import engine as E

    rows = [json.loads(l) for l in
            open(REPO / "runs/pool/pool.jsonl", encoding="utf-8")]

    if args.check:
        # must reproduce minima the verified bidirectional search already proved
        known = [r for r in rows if r["ac_best"] is not None
                 and r["ac_best"] <= 14][:8]
        print("warming the compiler", flush=True)
        warm = Ball(20, 50_000, 18)
        solve(known[0]["relators"], warm, 20, 50_000, 18)
        bad = 0
        for r in known:
            size = len(r["relators"][0]) + len(r["relators"][1])
            cap = size + 12
            ball = Ball(cap, 4_000_000, 24)
            ids, nodes = solve(r["relators"], ball, cap, 1_000_000, 22)
            got = "none" if ids is None else str(len(ids))
            ok = ids is not None and len(ids) == r["ac_best"]
            bad += 0 if ok else 1
            print(f"  {r['ac_id']} record {r['ac_best']:>2}: ball {got:>4} "
                  f"(ball {ball.count:,} in {ball.secs:.0f}s, fwd {nodes:,})"
                  f"{'' if ok else '   MISMATCH'}", flush=True)
        print(f"\ncheck: {len(known) - bad}/{len(known)} reproduce the known minimum",
              flush=True)
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
    # group by size so one ball serves a whole run of challenges
    band.sort(key=lambda r: (len(r["relators"][0]) + len(r["relators"][1]),
                             r["ac_best"] or 0))
    band = band[:args.limit]
    band = band[args.shard::args.nshards]
    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    what = "unsolved by anyone" if args.unsolved else \
        f"records {args.min_held}-{args.max_held}"
    print(f"{len(band)} challenges {what}, slack {args.cap_slack}, "
          f"ball {args.ball_nodes:,} nodes, forward {args.fwd_nodes:,}, "
          f"shard {args.shard}/{args.nshards}, {len(skip)} skipped", flush=True)

    print("warming the compiler", flush=True)
    warm = Ball(20, 50_000, 18)
    solve(band[0]["relators"], warm, 20, 50_000, 18)

    ball = None
    found = scoring = toobig = 0
    with (out / "solutions.jsonl").open("a", encoding="utf-8") as log:
        for r in band:
            start = tuple(tuple(w) for w in r["relators"])
            cap = len(start[0]) + len(start[1]) + args.cap_slack
            if cap + 2 > MAXLEN:
                toobig += 1
                continue
            if ball is None or ball.cap != cap:
                ball = Ball(cap, args.ball_nodes, args.ball_bits)
                print(f"  [ball cap {cap}: {ball.count:,} states in "
                      f"{ball.secs:.0f}s"
                      f"{', complete' if ball.complete else ''}]", flush=True)
            t0 = time.time()
            ids, nodes = solve(r["relators"], ball, cap,
                               args.fwd_nodes, args.fwd_bits)
            dt_s = time.time() - t0
            rec = r["ac_best"]
            if ids is None:
                print(f"  {r['ac_id']} record {rec if rec is not None else '--':>4}:"
                      f" none ({nodes:,} fwd nodes, {dt_s:.1f}s)", flush=True)
                continue
            found += 1
            # our path is minimal inside a cap on TOTAL length; shorten searches
            # detours under a cap on each relator, so it can still improve one.
            # That matters because our paths run about 10 percent over the
            # records we are trying to beat.
            raw = len(ids)
            if args.shorten:
                try:
                    cut = E.shorten(start, ids, depth=args.shorten_depth)
                    if len(cut) < len(ids):
                        ids = cut
                except Exception as exc:            # never lose a found path
                    print(f"    (shorten failed: {exc})", flush=True)
            ac = [E.to_move(m) for m in ids]
            stable = ac + [Destabilize(1), Destabilize(0)]
            begin = Presentation(2, start)
            if not verify(begin, ac, stable=False) or \
                    not verify(begin, stable, stable=True):
                raise AssertionError("ball search produced an unverifiable path")
            scores = rec is None or len(ac) <= rec
            scoring += scores
            stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            for problem, moves in (("ac", ac), ("stable_ac", stable)):
                log.write(json.dumps({"id": r["id"], "problem": problem,
                                      "length": len(moves),
                                      "moves": [move_to_json(m) for m in moves],
                                      "relators": r["relators"], "found_at": stamp,
                                      "cfg": {"method": "ball-bidirectional"}}) + "\n")
            log.flush()
            cutnote = f" (cut from {raw})" if len(ids) < raw else ""
            print(f"  {r['ac_id']} record {rec if rec is not None else '--':>4} "
                  f"(k {r['ac_k']}): ours {len(ac):>3}{cutnote} "
                  f"({nodes:,} fwd nodes, {dt_s:.1f}s)"
                  f"{'  <-- SCORES' if scores else ''}", flush=True)
    print(f"\nfound {found}/{len(band) - toobig}, scoring {scoring}"
          f"{f', {toobig} skipped: cap over MAXLEN {MAXLEN}' if toobig else ''}",
          flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()

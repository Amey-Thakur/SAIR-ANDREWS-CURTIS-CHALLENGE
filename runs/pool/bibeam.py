"""Level-synchronous bidirectional beam: the last untried search shape here.

What this campaign has already measured, so that this is not a fourth version of
the same thing:

  jit_tieband.solve_bidir  bidirectional, EXHAUSTIVE inside a hard cap on total
                           relator length. Returns true minima, cannot express a
                           path that leaves the cap. This is what scores.
  bestfirst.py             bidirectional, length as a GLOBAL bucket-queue
                           priority with no wall. Reaches far, paths not minimal
                           (record 15 against ours 32).
  policy_solve.py          forward-only, LEVEL-SYNCHRONOUS beam of fixed width,
                           length-ranked. This is the one that reached gap +1 on
                           ac-00678 (42 against a record of 41) and then stopped:
                           42 at beam 65,536 and 42 again at 262,144.

The missing combination is the third shape run from both ends. A fixed width per
depth level is what made the forward beam work, because it forces the search to
advance in depth while keeping B diverse states at each level, which a global
priority queue does not. Running it from both ends halves the depth each side
must cover, and depth is the axis the forward beam ran out of.

The backward half is presentation-independent - it expands from (x, y) under a
length cap and never reads the challenge - so it is built ONCE per (width, depth,
cap) and reused across every challenge. That was established when the repeated
node counts in the capped search were traced to the backward ball.

Unlike the exhaustive ball this frontier is truncated, so a join gives an UPPER
BOUND and not a minimum. That is the right trade here: we do not need to prove 41
is minimal, we need to produce a path of 41.

Every returned path is replayed through src.ac.verify before it is reported.

Usage (from the repo root):
  python runs/pool/bibeam.py --ids runs/pool/policy/two_resp.txt \\
      --back-beam 16384 --back-depth 26 --beam 16384 --steps 120
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "runs" / "pool"))
from jit_engine import MAXLEN, _apply, _hash  # noqa: E402
from policy_solve import expand, replay_ok  # noqa: E402

NMOVE = 14
INV = np.array([0, 1, 3, 2, 5, 4, 7, 6, 9, 8, 11, 10, 13, 12], dtype=np.int8)


class Back:
    """Every state the backward beam ever visited, with its exact depth.

    Accumulating all levels rather than keeping only the final frontier is the
    point: the forward side then has hundreds of thousands of admissible meeting
    points instead of the single state (x, y)."""

    def __init__(self, w0, l0, w1, l1, depth, parent, move):
        self.w0, self.l0, self.w1, self.l1 = w0, l0, w1, l1
        self.depth, self.parent, self.move = depth, parent, move
        h = np.empty(len(depth), dtype=np.uint64)
        for i in range(len(depth)):
            h[i] = _hash(w0[i], l0[i], w1[i], l1[i])
        order = np.argsort(h, kind="stable")
        self.sorted_h = h[order]
        self.sorted_idx = order.astype(np.int64)

    def lookup(self, cand_h):
        """Vectorised membership: (hit mask, store index per candidate)."""
        n = len(self.sorted_h)
        pos = np.searchsorted(self.sorted_h, cand_h)
        safe = np.minimum(pos, n - 1)
        hit = (pos < n) & (self.sorted_h[safe] == cand_h)
        return hit, self.sorted_idx[safe]

    def chain(self, i):
        """Moves that carry state i forward to (x, y)."""
        out = []
        while self.parent[i] >= 0:
            out.append(int(INV[self.move[i]]))
            i = self.parent[i]
        return out


def build_back(beam, depth_max, cap, rank="short", target=0, verbose=True):
    """Level-synchronous beam outward from (x, y), keeping every state seen.

    `rank` decides which children survive each level, and it turned out to be the
    whole thing. With "short" the frontier's mean total length saturates at about
    11 and never climbs, because keeping the shortest children at every depth is
    a "stay near (x, y)" search: at depth 26 the set is 365,563 states of mean
    length 11, while the forward beam on a size-35 presentation lives at length
    35 to 44. The two frontiers never approach each other in length space, so the
    join can only happen at the end of the forward descent, which is where the
    forward-only beam already lands. The measured consequence was identical path
    lengths, to the move, on all four targets.

    "band" ranks by distance from a target total length instead, which pulls the
    backward frontier up to where the forward one actually is. "long" pushes it
    as high as the cap allows."""
    sw0 = [np.zeros((1, MAXLEN), dtype=np.int8)]
    sw1 = [np.zeros((1, MAXLEN), dtype=np.int8)]
    sw0[0][0, 0] = 1
    sw1[0][0, 0] = 2
    sl0 = [np.ones(1, dtype=np.int16)]
    sl1 = [np.ones(1, dtype=np.int16)]
    sdep = [np.zeros(1, dtype=np.int16)]
    spar = [np.full(1, -1, dtype=np.int64)]
    smov = [np.zeros(1, dtype=np.int8)]
    seen = {int(_hash(sw0[0][0], 1, sw1[0][0], 1))}
    base = 0                                   # store offset of the frontier
    fw0, fw1 = sw0[0].copy(), sw1[0].copy()
    fl0, fl1 = sl0[0].copy(), sl1[0].copy()
    fidx = np.zeros(1, dtype=np.int64)
    total = 1

    B = beam
    cw0 = np.zeros((B * NMOVE, MAXLEN), dtype=np.int8)
    cw1 = np.zeros((B * NMOVE, MAXLEN), dtype=np.int8)
    cl0 = np.zeros(B * NMOVE, dtype=np.int16)
    cl1 = np.zeros(B * NMOVE, dtype=np.int16)
    chash = np.zeros(B * NMOVE, dtype=np.uint64)
    cvalid = np.zeros(B * NMOVE, dtype=np.int8)

    t0 = time.time()
    for d in range(1, depth_max + 1):
        nb = len(fl0)
        pw0 = np.zeros((B, MAXLEN), dtype=np.int8)
        pw1 = np.zeros((B, MAXLEN), dtype=np.int8)
        pl0 = np.zeros(B, dtype=np.int16)
        pl1 = np.zeros(B, dtype=np.int16)
        pw0[:nb], pw1[:nb] = fw0[:nb], fw1[:nb]
        pl0[:nb], pl1[:nb] = fl0[:nb], fl1[:nb]
        expand(pw0, pl0, pw1, pl1, nb, cap, cw0, cl0, cw1, cl1,
               cvalid=cvalid, chash=chash)
        m = nb * NMOVE
        ok = cvalid[:m].astype(bool)
        if not ok.any():
            break
        idx = np.flatnonzero(ok)
        # deduplicate against everything already stored, cheapest first
        hs = chash[idx]
        keep, khash = [], set()
        for j, h in zip(idx, hs):
            hi = int(h)
            if hi in seen or hi in khash:
                continue
            khash.add(hi)
            keep.append(j)
        if not keep:
            break
        keep = np.array(keep, dtype=np.int64)
        tot = (cl0[keep] + cl1[keep]).astype(np.int32)
        if rank == "long":
            key = -tot
        elif rank == "band":
            key = np.abs(tot - target)
        else:
            key = tot
        if len(keep) > B:
            sel = np.argpartition(key, B)[:B]
            keep, tot = keep[sel], tot[sel]
        for h in chash[keep]:
            seen.add(int(h))
        par = fidx[keep // NMOVE]
        mov = (keep % NMOVE).astype(np.int8)
        n = len(keep)
        sw0.append(cw0[keep].copy())
        sw1.append(cw1[keep].copy())
        sl0.append(cl0[keep].copy())
        sl1.append(cl1[keep].copy())
        sdep.append(np.full(n, d, dtype=np.int16))
        spar.append(par.astype(np.int64))
        smov.append(mov)
        fidx = np.arange(total, total + n, dtype=np.int64)
        total += n
        fw0, fw1 = sw0[-1], sw1[-1]
        fl0, fl1 = sl0[-1], sl1[-1]
        if verbose:
            print(f"    back depth {d:>3}: +{n:>7,} states, {total:>9,} total, "
                  f"mean length {tot.mean():.1f}", flush=True)
    b = Back(np.concatenate(sw0), np.concatenate(sl0), np.concatenate(sw1),
             np.concatenate(sl1), np.concatenate(sdep), np.concatenate(spar),
             np.concatenate(smov))
    if verbose:
        print(f"  backward set: {total:,} states to depth {depth_max}, "
              f"cap {cap}, {time.time() - t0:.0f}s", flush=True)
    return b


def solve_bi(relators, back, beam, steps, cap, best_cut=None):
    """Forward beam, joining against the backward set. Returns (path, nodes)."""
    B = beam
    w0 = np.zeros((B, MAXLEN), dtype=np.int8)
    w1 = np.zeros((B, MAXLEN), dtype=np.int8)
    l0 = np.zeros(B, dtype=np.int16)
    l1 = np.zeros(B, dtype=np.int16)
    r0, r1 = relators
    w0[0, :len(r0)] = np.array(r0, dtype=np.int8)
    w1[0, :len(r1)] = np.array(r1, dtype=np.int8)
    l0[0], l1[0] = len(r0), len(r1)
    nb = 1
    paths = np.zeros((B, steps), dtype=np.int8)
    depth = np.zeros(B, dtype=np.int16)

    cw0 = np.zeros((B * NMOVE, MAXLEN), dtype=np.int8)
    cw1 = np.zeros((B * NMOVE, MAXLEN), dtype=np.int8)
    cl0 = np.zeros(B * NMOVE, dtype=np.int16)
    cl1 = np.zeros(B * NMOVE, dtype=np.int16)
    chash = np.zeros(B * NMOVE, dtype=np.uint64)
    cvalid = np.zeros(B * NMOVE, dtype=np.int8)

    seen = set()
    nodes = 0
    best = None
    best_split = None
    joins = 0
    for t in range(steps):
        expand(w0, l0, w1, l1, nb, cap, cw0, cl0, cw1, cl1,
               cvalid=cvalid, chash=chash)
        nodes += nb * NMOVE
        m = nb * NMOVE
        valid = cvalid[:m].astype(bool)
        if not valid.any():
            break
        par = np.repeat(np.arange(nb), NMOVE)
        mv = np.tile(np.arange(NMOVE), nb)

        # every join available at this level, best total kept
        hit, bidx = back.lookup(chash[:m])
        hit &= valid
        if hit.any():
            rows = np.flatnonzero(hit)
            fdep = depth[par[rows]] + 1
            tot = fdep + back.depth[bidx[rows]]
            order = np.argsort(tot)
            for o in order[:32]:                # check a few, words must match
                r = int(rows[o])
                bi = int(bidx[r])
                if (cl0[r] != back.l0[bi] or cl1[r] != back.l1[bi]
                        or not np.array_equal(cw0[r, :cl0[r]],
                                              back.w0[bi, :cl0[r]])
                        or not np.array_equal(cw1[r, :cl1[r]],
                                              back.w1[bi, :cl1[r]])):
                    continue                    # hash collision, not a join
                i = par[r]
                d = int(depth[i])
                chain = back.chain(bi)
                cand = list(paths[i, :d]) + [int(mv[r])] + chain
                joins += 1
                if best is None or len(cand) < len(best):
                    best = [int(x) for x in cand]
                    # f is the moves the forward beam spent, b the depth of the
                    # backward state it met. b tells us whether the join is real
                    # or merely the forward search arriving at the target with a
                    # couple of free moves tacked on.
                    best_split = (d + 1, len(chain),
                                  int(cl0[r]) + int(cl1[r]))
                break
            if best is not None and best_cut is not None and len(best) <= best_cut:
                return best, nodes, best_split, joins

        cs = -(cl0[:m] + cl1[:m]).astype(np.float32)
        cs = np.where(valid, cs, -np.inf)
        order = np.argsort(-cs)
        nw0 = np.zeros((B, MAXLEN), dtype=np.int8)
        nw1 = np.zeros((B, MAXLEN), dtype=np.int8)
        nl0 = np.zeros(B, dtype=np.int16)
        nl1 = np.zeros(B, dtype=np.int16)
        npath = np.zeros((B, steps), dtype=np.int8)
        ndep = np.zeros(B, dtype=np.int16)
        k = 0
        for r in order:
            if not valid[r] or not np.isfinite(cs[r]):
                break
            h = int(chash[r])
            if h in seen:
                continue
            seen.add(h)
            i = par[r]
            d = int(depth[i])
            if d + 1 >= steps:
                continue
            nw0[k], nw1[k] = cw0[r], cw1[r]
            nl0[k], nl1[k] = cl0[r], cl1[r]
            npath[k, :d] = paths[i, :d]
            npath[k, d] = mv[r]
            ndep[k] = d + 1
            k += 1
            if k == B:
                break
        if k == 0:
            break
        w0, w1, l0, l1, paths, depth = nw0, nw1, nl0, nl1, npath, ndep
        nb = k
    return best, nodes, best_split, joins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="runs/pool/policy/two_resp.txt")
    ap.add_argument("--back-beam", type=int, default=16384)
    ap.add_argument("--back-depth", type=int, default=26)
    ap.add_argument("--beam", type=int, default=16384)
    ap.add_argument("--steps", type=int, default=120)
    ap.add_argument("--cap", type=int, default=44)
    ap.add_argument("--back-rank", default="short",
                    choices=["short", "long", "band"])
    ap.add_argument("--back-target", type=int, default=0,
                    help="total relator length the backward frontier aims "
                         "for with --back-rank band; 0 means the mean size "
                         "of the challenges being run")
    ap.add_argument("--out", default="runs/pool/policy/bibeam.jsonl")
    args = ap.parse_args()

    rows = {r["ac_id"]: r for r in
            (json.loads(l) for l in
             open(REPO / "runs/pool/pool.jsonl", encoding="utf-8"))}
    want = [l.split()[0] for l in
            open(REPO / args.ids, encoding="utf-8") if l.strip()]
    items = [rows[c] for c in want if c in rows]

    target = args.back_target
    if args.back_rank == "band" and target == 0:
        target = int(round(np.mean([len(r["relators"][0]) + len(r["relators"][1])
                                    for r in items])))
    print(f"{len(items)} challenges; backward beam {args.back_beam:,} to depth "
          f"{args.back_depth}, rank {args.back_rank}"
          f"{f' at length {target}' if args.back_rank == 'band' else ''}, "
          f"forward beam {args.beam:,}, cap {args.cap}", flush=True)
    back = build_back(args.back_beam, args.back_depth, args.cap,
                      rank=args.back_rank, target=target)

    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    found = scoring = 0
    with out.open("a", encoding="utf-8") as log:
        for r in items:
            t0 = time.time()
            path, nodes, split, joins = solve_bi(
                r["relators"], back, args.beam, args.steps, args.cap,
                best_cut=(r["ac_best"] - 1 if r["ac_best"] else None))
            el = time.time() - t0
            if path is None:
                print(f"  {r['ac_id']} record {r['ac_best']:>4}: none "
                      f"({nodes:,} nodes, {el:.0f}s)", flush=True)
                continue
            found += 1
            ok = replay_ok(r["relators"], path)
            sc = ok and r["ac_best"] is not None and len(path) <= r["ac_best"]
            scoring += sc
            sp = (f"join f={split[0]} + b={split[1]} at length {split[2]}, "
                  f"{joins:,} joins seen" if split else "")
            print(f"  {r['ac_id']} record {r['ac_best']:>4} (k {r['ac_k']}): "
                  f"ours {len(path):>4} verify={ok} ({nodes:,} nodes, {el:.0f}s)"
                  f"  [{sp}]{'  <-- SCORES' if sc else ''}", flush=True)
            log.write(json.dumps({"challenge_id": r["ac_id"],
                                  "record": r["ac_best"], "length": len(path),
                                  "verified": bool(ok), "moves": path,
                                  "mode": "bibeam", "beam": args.beam,
                                  "back_beam": args.back_beam,
                                  "back_depth": args.back_depth,
                                  "found_at": stamp}) + "\n")
            log.flush()
    print(f"\n{found} found, {scoring} at or under the record, of {len(items)}",
          flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()

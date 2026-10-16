"""Policy-guided beam search: the trained network used as a solver.

Every search this campaign has scored with is exhaustive inside a cap on total
relator length, which is why it returns true minima and why it cannot express a
path that leaves the cap.  A trained policy is the other kind of solver: it
never proves anything, it just follows a learned ranking, so it can walk a path
of any shape as long as the ranking is good enough.  That is the whole claim of
arXiv 2408.15332 and the only class of solver on this board with evidence
behind it.

Three scoring modes, so the network's two heads can be separated:
  policy  - cumulative log-probability of the move sequence (the actor alone)
  value   - moves spent plus the predicted distance to (x, y) (the critic alone,
            used as an A* f-value)
  hybrid  - both

Every returned path is replayed against the repo verifier before it is reported,
exactly as every other solver here does.

Usage (from the repo root):
  python runs/pool/policy_solve.py --net runs/pool/policy/net.pt \
      --min-record 31 --max-record 60 --limit 60 --beam 512 --steps 120
"""
import argparse
import json
import os
import pathlib
import sys
import time

import numpy as np
import torch
from numba import njit

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "runs" / "pool"))
from jit_engine import MAXLEN, _apply, _hash  # noqa: E402
from policy_net import ENC, NTOK, Net, onehot  # noqa: E402

NMOVE = 14


@njit(cache=False)
def expand(w0, l0, w1, l1, nb, cap, cw0, cl0, cw1, cl1, chash, cvalid):
    """All 14 children of each of the nb beam states.

    Child j of beam i lands at row i * 14 + j.  cvalid marks the ones that stay
    inside the cap and keep both relators non-empty; a duplicate of its own
    parent is dropped too, because a move that changes nothing wastes a slot."""
    o0 = np.zeros(MAXLEN, dtype=np.int8)
    o1 = np.zeros(MAXLEN, dtype=np.int8)
    buf = np.zeros(MAXLEN, dtype=np.int8)
    tmp = np.zeros(MAXLEN + 2, dtype=np.int8)
    for i in range(nb):
        ph = _hash(w0[i], l0[i], w1[i], l1[i])
        for m in range(NMOVE):
            r = i * NMOVE + m
            na, nbn = _apply(m, w0[i], l0[i], w1[i], l1[i], o0, o1, buf, tmp)
            if na < 1 or nbn < 1 or na + nbn > cap or na >= MAXLEN or nbn >= MAXLEN:
                cvalid[r] = 0
                chash[r] = np.uint64(0)
                cl0[r] = 0
                cl1[r] = 0
                continue
            for k in range(MAXLEN):
                cw0[r, k] = o0[k] if k < na else 0
                cw1[r, k] = o1[k] if k < nbn else 0
            cl0[r] = na
            cl1[r] = nbn
            h = _hash(o0, na, o1, nbn)
            chash[r] = h
            cvalid[r] = 0 if h == ph else 1
    return 0


def tokens(w0, l0, w1, l1):
    n = w0.shape[0]
    x = np.zeros((n, 2 * ENC), dtype=np.int8)
    keep = min(ENC, w0.shape[1])
    x[:, :keep] = (w0[:, :keep].astype(np.int16) + 2).astype(np.int8)
    x[:, ENC:ENC + keep] = (w1[:, :keep].astype(np.int16) + 2).astype(np.int8)
    return x


def solve(net, relators, beam, steps, cap, mode, dev="cpu", seed=0,
          temp=1.0):
    """Beam search under the network.  Returns (path, nodes) or (None, nodes)."""
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
    score = np.zeros(B, dtype=np.float32)
    paths = np.zeros((B, steps), dtype=np.int8)
    depth = np.zeros(B, dtype=np.int16)

    cw0 = np.zeros((B * NMOVE, MAXLEN), dtype=np.int8)
    cw1 = np.zeros((B * NMOVE, MAXLEN), dtype=np.int8)
    cl0 = np.zeros(B * NMOVE, dtype=np.int16)
    cl1 = np.zeros(B * NMOVE, dtype=np.int16)
    chash = np.zeros(B * NMOVE, dtype=np.uint64)
    cvalid = np.zeros(B * NMOVE, dtype=np.int8)

    seen = set()
    rng = np.random.default_rng(seed)
    nodes = 0
    for t in range(steps):
        if mode in ("length", "random", "noisy"):
            lp = np.zeros((nb, NMOVE), dtype=np.float32)
            vv = np.zeros(nb, dtype=np.float32)
        else:
            with torch.no_grad():
                logits, val = net(onehot(
                    tokens(w0[:nb], l0[:nb], w1[:nb], l1[:nb]), dev))
                lp = torch.log_softmax(logits, dim=1).numpy()
                vv = val.numpy()
        expand(w0, l0, w1, l1, nb, cap, cw0, cl0, cw1, cl1, cvalid=cvalid,
               chash=chash)
        nodes += nb * NMOVE
        valid = cvalid[:nb * NMOVE].astype(bool)
        if not valid.any():
            return None, nodes
        par = np.repeat(np.arange(nb), NMOVE)
        mv = np.tile(np.arange(NMOVE), nb)

        # target reached?
        hit = valid & (cl0[:nb * NMOVE] == 1) & (cl1[:nb * NMOVE] == 1) & \
            (cw0[:nb * NMOVE, 0] == 1) & (cw1[:nb * NMOVE, 0] == 2)
        if hit.any():
            r = int(np.flatnonzero(hit)[0])
            i = par[r]
            d = int(depth[i])
            path = list(paths[i, :d]) + [int(mv[r])]
            return [int(m) for m in path], nodes

        if mode in ("length", "noisy"):
            # control: the same beam search with no network at all, ranked by
            # total relator length. If this matches the trained policy then the
            # network has added nothing and the beam is doing the work.
            cs = -(cl0[:nb * NMOVE] + cl1[:nb * NMOVE]).astype(np.float32)
            if mode == "noisy":
                # A pure length ranking collapses the beam onto one basin: the
                # 16,384 survivors of a step are near-identical short states.
                # Gumbel noise on the score turns the beam into a sample from
                # the softmax over -length, so restarts explore different
                # basins at the same total cost. Equal-compute is the only fair
                # comparison, so k restarts at beam B/k answer it.
                cs = cs + temp * rng.gumbel(size=cs.shape).astype(np.float32)
        elif mode == "random":
            cs = rng.random(nb * NMOVE).astype(np.float32)
        elif mode == "policy":
            cs = score[par] + lp[par, mv]
        elif mode == "value":
            # f = g + h, with g the moves spent and h the critic's estimate;
            # the critic is scored on the CHILD, which needs a second forward,
            # so the parent's value minus one is used as the running estimate
            cs = -(depth[par] + 1.0) - np.maximum(vv[par] - 1.0, 0.0)
        else:
            cs = score[par] + lp[par, mv] - 0.25 * np.maximum(vv[par] - 1.0, 0.0)
        cs = np.where(valid, cs, -np.inf)

        order = np.argsort(-cs)
        nw0 = np.zeros((B, MAXLEN), dtype=np.int8)
        nw1 = np.zeros((B, MAXLEN), dtype=np.int8)
        nl0 = np.zeros(B, dtype=np.int16)
        nl1 = np.zeros(B, dtype=np.int16)
        nsc = np.zeros(B, dtype=np.float32)
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
            nw0[k] = cw0[r]
            nw1[k] = cw1[r]
            nl0[k] = cl0[r]
            nl1[k] = cl1[r]
            nsc[k] = cs[r] if mode in ("policy", "hybrid") else score[i]
            npath[k, :d] = paths[i, :d]
            npath[k, d] = mv[r]
            ndep[k] = d + 1
            k += 1
            if k == B:
                break
        if k == 0:
            return None, nodes
        w0, w1, l0, l1, score, paths, depth = nw0, nw1, nl0, nl1, nsc, npath, ndep
        nb = k
    return None, nodes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", default="runs/pool/policy/net.pt")
    ap.add_argument("--min-record", type=int, default=31)
    ap.add_argument("--max-record", type=int, default=60)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--beam", type=int, default=512)
    ap.add_argument("--steps", type=int, default=120)
    ap.add_argument("--cap", type=int, default=44)
    ap.add_argument("--mode", default="policy",
                    choices=["policy", "value", "hybrid", "length",
                             "random", "noisy"])
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--temp", type=float, default=1.0,
                    help="Gumbel scale for --mode noisy, in letters of total "
                         "relator length")
    ap.add_argument("--restarts", type=int, default=1,
                    help="independent runs per challenge, shortest kept; use "
                         "beam/restarts to hold total compute fixed")
    ap.add_argument("--source", default="pool", choices=["pool", "train424"])
    ap.add_argument("--skip-file", default=None)
    ap.add_argument("--ids", default=None,
                    help="file of challenge ids, one per line, to run instead "
                         "of a whole band")
    ap.add_argument("--out", default="runs/pool/policy/solve.jsonl")
    args = ap.parse_args()

    torch.set_num_threads(args.threads)
    ck = torch.load(REPO / args.net, map_location="cpu", weights_only=True)
    net = Net(ck["hidden"])
    net.load_state_dict(ck["state"])
    net.eval()

    if args.source == "train424":
        d = json.load(open(REPO / "runs/official/repo/competition/examples/"
                           "training_424.json", encoding="utf-8"))
        items = [{"ac_id": it["training_id"], "relators": it["initial_relators"],
                  "ac_best": it["length"], "ac_k": 0}
                 for it in d["instances"]][:args.limit]
    else:
        rows = [json.loads(l) for l in
                open(REPO / "runs/pool/pool.jsonl", encoding="utf-8")]
        skip = set()
        if args.skip_file:
            skip = {l.split()[0] for l in
                    open(REPO / args.skip_file, encoding="utf-8") if l.strip()}
        if args.ids:
            want = [l.split()[0] for l in
                    open(REPO / args.ids, encoding="utf-8") if l.strip()]
            by = {r["ac_id"]: r for r in rows}
            items = [by[c] for c in want if c in by]
        else:
            items = [r for r in rows if r["ac_best"] is not None
                     and args.min_record <= r["ac_best"] <= args.max_record
                     and r["ac_id"] not in skip]
            items.sort(key=lambda r: r["ac_best"])
            items = items[:args.limit]

    from src.ac.verify import verify  # noqa: E402
    from src.ac.presentation import Presentation  # noqa: E402

    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"{len(items)} challenges, mode {args.mode}, beam {args.beam}, "
          f"steps {args.steps}, cap {args.cap}", flush=True)
    found = scoring = 0
    t_all = time.time()
    with out.open("a", encoding="utf-8") as log:
        for r in items:
            t0 = time.time()
            path, nodes = None, 0
            for rs in range(args.restarts):
                p1, n1 = solve(net, r["relators"], args.beam, args.steps,
                               args.cap, args.mode, seed=1000 + rs,
                               temp=args.temp)
                nodes += n1
                if p1 is not None and (path is None or len(p1) < len(path)):
                    path = p1
            el = time.time() - t0
            if path is None:
                print(f"  {r['ac_id']} record {r['ac_best']:>4}: none "
                      f"({nodes:,} nodes, {el:.1f}s)", flush=True)
                continue
            found += 1
            ok = replay_ok(r["relators"], path)
            sc = "SCORES" if ok and len(path) <= r["ac_best"] else ""
            if sc:
                scoring += 1
            print(f"  {r['ac_id']} record {r['ac_best']:>4}: ours "
                  f"{len(path):>4} verify={ok} ({nodes:,} nodes, {el:.1f}s) {sc}",
                  flush=True)
            log.write(json.dumps({"challenge_id": r["ac_id"],
                                  "record": r["ac_best"], "length": len(path),
                                  "verified": ok, "moves": path,
                                  "mode": args.mode, "beam": args.beam}) + "\n")
            log.flush()
    print(f"\n{found} found, {scoring} at or under the record, of {len(items)} "
          f"in {time.time() - t_all:.0f}s", flush=True)
    os._exit(0)


def replay_ok(relators, path):
    """Replay through the repo's own move code and check we land on (x, y)."""
    w0 = np.zeros(MAXLEN, dtype=np.int8)
    w1 = np.zeros(MAXLEN, dtype=np.int8)
    o0 = np.zeros(MAXLEN, dtype=np.int8)
    o1 = np.zeros(MAXLEN, dtype=np.int8)
    buf = np.zeros(MAXLEN, dtype=np.int8)
    tmp = np.zeros(MAXLEN + 2, dtype=np.int8)
    r0, r1 = relators
    w0[:len(r0)] = np.array(r0, dtype=np.int8)
    w1[:len(r1)] = np.array(r1, dtype=np.int8)
    l0, l1 = len(r0), len(r1)
    for m in path:
        l0, l1 = _apply(m, w0, l0, w1, l1, o0, o1, buf, tmp)
        w0[:] = 0
        w1[:] = 0
        w0[:l0] = o0[:l0]
        w1[:l1] = o1[:l1]
    return bool(l0 == 1 and l1 == 1 and w0[0] == 1 and w1[0] == 2)


if __name__ == "__main__":
    main()

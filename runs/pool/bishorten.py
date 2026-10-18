"""Bidirectional path shortening: meet in the middle between EVERY pair of
states on a path we already hold, at any span.

Three shorteners already exist here and this is none of them:

| tool | question it asks | reach |
|---|---|---|
| `engine.shorten` | is there a detour of radius <= 3 from s_i to a later s_j | span any, detour <= 3, one-sided |
| `shortcut.py` | what is the TRUE minimum from s_i to s_j | span 6 to 22 only, inside a box of (max length in the window) + slack |
| `suffix_opt.py` | what is the true minimum from s_i to (x, y) | tail only |

The hole is a shortcut that is SHORT but spans a LONG stretch. `engine.shorten`
cannot see past radius 3, and `shortcut.py` never looked past span 22, so an
eight-move route across a forty-move stretch has never been tested. That is
exactly what a 1.76 median ratio would be made of if our paths wander: the 27
Sep finding that 467 of 467 windows re-derived our own length proves the path is
locally minimal over spans <= 22 and says nothing at all about longer spans.

The method. Grow a BFS ball of radius `depth` around every state on the path and
put them all in ONE hash table, tagged with the anchor index they came from. Any
state reached from both s_i and s_j is a meeting point, and because the fourteen
moves are closed under inversion the backward half is the forward half with
inverted move ids. A meet at depths (du, dv) replaces j - i moves with du + dv.
Cost is n balls, not n^2 searches, and it finds every shortcut of length up to
2 * depth across every span on the path at once.

Unlike `shortcut.py` the ball is capped on the WHOLE path's longest state plus
slack, not on the window's, so a shortcut is allowed to grow a relator past
anything the window itself contains.

Guards. The meet test is on 64-bit hashes, so every splice is replayed to
confirm the segment really carries s_i to s_j, and the whole path is then
replayed through `src.ac.verify` on its board before anything is written. The
endpoint never moves, so a path to a trivial state stays a path to that state
and the trailing destabilisations of a stable path stay legal.

Usage (from the repo root):
  python runs/pool/bishorten.py --check                     # planted control
  python runs/pool/bishorten.py --problem ac --depth 3 --out runs/pool/bs_ac
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time

os.environ.setdefault("ACC_MAXLEN", "120")

import numpy as np                                            # noqa: E402
from numba import njit                                        # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "runs" / "pool"))
from jit_engine import _apply, _hash                          # noqa: E402
from src.ac.presentation import Presentation                  # noqa: E402
from src.ac.verify import verify                              # noqa: E402
from src.search.engine import to_move                         # noqa: E402

INV = np.array([0, 1, 3, 2, 5, 4, 7, 6, 9, 8, 11, 10, 13, 12], dtype=np.int8)
CONJ = (1, -1, 2, -2)
TRIVIAL = {((1,), (2,)), ((1,), (-2,)), ((-1,), (2,)), ((-1,), (-2,)),
           ((2,), (1,)), ((2,), (-1,)), ((-2,), (1,)), ((-2,), (-1,))}


# -- the core ---------------------------------------------------------------

@njit(cache=False)
def best_shortcut(pw0, pl0, pw1, pl1, npath, depth, cap, table_bits,
                  max_nodes, max_level):
    """The single best meet-in-the-middle shortcut anywhere on the path.

    Returns (saving, i, j, segment, segment length, nodes used, overflow).
    A saving of 0 means the path admits no shortcut of length <= 2 * depth."""
    W = pw0.shape[1]
    S = 2 * cap + 8
    size = 1 << table_bits
    mask = np.uint64(size - 1)
    hkey = np.zeros(size, dtype=np.uint64)
    hhead = np.full(size, -1, dtype=np.int32)

    par = np.full(max_nodes, -1, dtype=np.int32)
    pmv = np.zeros(max_nodes, dtype=np.int8)
    anc = np.full(max_nodes, -1, dtype=np.int32)
    dep = np.zeros(max_nodes, dtype=np.int8)
    chain = np.full(max_nodes, -1, dtype=np.int32)

    cw0 = np.zeros((max_level, W), dtype=np.int8)
    cw1 = np.zeros((max_level, W), dtype=np.int8)
    cl0 = np.zeros(max_level, dtype=np.int16)
    cl1 = np.zeros(max_level, dtype=np.int16)
    cnode = np.zeros(max_level, dtype=np.int32)
    nw0 = np.zeros((max_level, W), dtype=np.int8)
    nw1 = np.zeros((max_level, W), dtype=np.int8)
    nl0 = np.zeros(max_level, dtype=np.int16)
    nl1 = np.zeros(max_level, dtype=np.int16)
    nnode = np.zeros(max_level, dtype=np.int32)

    o0 = np.zeros(S, dtype=np.int8)
    o1 = np.zeros(S, dtype=np.int8)
    buf = np.zeros(S, dtype=np.int8)
    tmp = np.zeros(S + 4, dtype=np.int8)

    cnt = 0
    hcnt = 0
    hmax = (size * 3) // 4
    overflow = 0
    # the best shortcut ENDING at each anchor, so one pass can splice many
    asav = np.zeros(npath, dtype=np.int32)
    apart = np.full(npath, -1, dtype=np.int32)
    au = np.full(npath, -1, dtype=np.int32)
    av = np.full(npath, -1, dtype=np.int32)

    for a in range(npath):
        if cnt >= max_nodes or hcnt >= hmax:
            overflow = 1
            break

        # level zero: the anchor state itself
        h = _hash(pw0[a], pl0[a], pw1[a], pl1[a])
        idx = h & mask
        while hkey[idx] != np.uint64(0) and hkey[idx] != h:
            idx = (idx + np.uint64(1)) & mask
        dup = False
        lsav = 0
        lv = -1
        if hkey[idx] == h:
            v = hhead[idx]
            while v != -1:
                if anc[v] == a:
                    dup = True
                    break
                sav = (a - anc[v]) - dep[v]
                if sav > lsav:
                    lsav = sav
                    lv = v
                v = chain[v]
        nc = 0
        if not dup:
            u = cnt
            cnt += 1
            par[u] = -1
            pmv[u] = 0
            anc[u] = a
            dep[u] = 0
            if hkey[idx] == np.uint64(0):
                hcnt += 1
            hkey[idx] = h
            chain[u] = hhead[idx]
            hhead[idx] = u
            if lsav > asav[a]:
                asav[a] = lsav
                apart[a] = anc[lv]
                au[a] = lv
                av[a] = u
            for t in range(pl0[a]):
                cw0[0, t] = pw0[a, t]
            for t in range(pl1[a]):
                cw1[0, t] = pw1[a, t]
            cl0[0] = pl0[a]
            cl1[0] = pl1[a]
            cnode[0] = u
            nc = 1

        for d in range(1, depth + 1):
            if nc == 0:
                break
            nn = 0
            for p in range(nc):
                if overflow == 1:
                    break
                for mid in range(14):
                    k0, k1 = _apply(mid, cw0[p], cl0[p], cw1[p], cl1[p],
                                    o0, o1, buf, tmp)
                    if k0 == 0 or k1 == 0:
                        continue
                    if k0 + k1 > cap:
                        continue
                    h = _hash(o0, k0, o1, k1)
                    idx = h & mask
                    while hkey[idx] != np.uint64(0) and hkey[idx] != h:
                        idx = (idx + np.uint64(1)) & mask
                    dup = False
                    lsav = 0
                    lv = -1
                    if hkey[idx] == h:
                        v = hhead[idx]
                        while v != -1:
                            if anc[v] == a:
                                dup = True
                                break
                            sav = (a - anc[v]) - (dep[v] + d)
                            if sav > lsav:
                                lsav = sav
                                lv = v
                            v = chain[v]
                    if dup:
                        continue
                    if cnt >= max_nodes or nn >= max_level or hcnt >= hmax:
                        overflow = 1
                        break
                    u = cnt
                    cnt += 1
                    par[u] = cnode[p]
                    pmv[u] = mid
                    anc[u] = a
                    dep[u] = d
                    if hkey[idx] == np.uint64(0):
                        hcnt += 1
                    hkey[idx] = h
                    chain[u] = hhead[idx]
                    hhead[idx] = u
                    if lsav > asav[a]:
                        asav[a] = lsav
                        apart[a] = anc[lv]
                        au[a] = lv
                        av[a] = u
                    for t in range(k0):
                        nw0[nn, t] = o0[t]
                    for t in range(k1):
                        nw1[nn, t] = o1[t]
                    nl0[nn] = k0
                    nl1[nn] = k1
                    nnode[nn] = u
                    nn += 1
            if overflow == 1:
                break
            for p in range(nn):
                for t in range(nl0[p]):
                    cw0[p, t] = nw0[p, t]
                for t in range(nl1[p]):
                    cw1[p, t] = nw1[p, t]
                cl0[p] = nl0[p]
                cl1[p] = nl1[p]
                cnode[p] = nnode[p]
            nc = nn
        if overflow == 1:
            break

    L = 2 * depth + 4
    seg = np.zeros((npath, L), dtype=np.int8)
    slen = np.zeros(npath, dtype=np.int16)
    ra = np.zeros(depth + 2, dtype=np.int8)
    for a in range(npath):
        if asav[a] <= 0:
            continue
        ns = 0
        na = 0
        v = au[a]
        while par[v] != -1:
            ra[na] = pmv[v]
            na += 1
            v = par[v]
        for t in range(na - 1, -1, -1):
            seg[a, ns] = ra[t]
            ns += 1
        v = av[a]
        while par[v] != -1:
            seg[a, ns] = INV[pmv[v]]
            ns += 1
            v = par[v]
        slen[a] = ns
    return asav, apart, seg, slen, cnt, overflow


# -- plain python side ------------------------------------------------------

def join(a, b):
    la, lb = len(a), len(b)
    m = la if la < lb else lb
    k = 0
    while k < m and a[la - 1 - k] == -b[k]:
        k += 1
    return a + b if k == 0 else a[:la - k] + b[k:]


def inv_word(w):
    return tuple(-x for x in w[::-1])


def step(state, mid):
    r0, r1 = state
    if mid == 0:
        return (inv_word(r0), r1)
    if mid == 1:
        return (r0, inv_word(r1))
    if mid == 2:
        return (join(r0, r1), r1)
    if mid == 3:
        return (join(r0, inv_word(r1)), r1)
    if mid == 4:
        return (r0, join(r1, r0))
    if mid == 5:
        return (r0, join(r1, inv_word(r0)))
    if 6 <= mid < 10:
        c = CONJ[mid - 6]
        return (join(join((c,), r0), (-c,)), r1)
    c = CONJ[mid - 10]
    return (r0, join(join((c,), r1), (-c,)))


def replay(start, mids):
    out = [start]
    for m in mids:
        out.append(step(out[-1], m))
    return out


def to_mid(m):
    """A stored move dict as a move id, or None when it is not an ordinary
    two-relator move."""
    kind = m["move"]
    if kind == "invert":
        return m["i"] if m["i"] in (0, 1) else None
    if kind == "multiply":
        if m["i"] == 0 and m["j"] == 1:
            return 2 if m["sign"] > 0 else 3
        if m["i"] == 1 and m["j"] == 0:
            return 4 if m["sign"] > 0 else 5
        return None
    if kind == "conjugate":
        if m["i"] not in (0, 1) or m["c"] not in CONJ:
            return None
        return (6 if m["i"] == 0 else 10) + CONJ.index(m["c"])
    return None


def split_path(moves):
    """(ordinary move ids, trailing moves kept verbatim).

    Our stable paths are an ordinary descent followed by destabilisations. The
    shortener works on the ordinary prefix and leaves the tail alone."""
    mids = []
    for k, m in enumerate(moves):
        mid = to_mid(m)
        if mid is None:
            return mids, moves[k:]
        mids.append(mid)
    return mids, []


def pack(states, cap):
    """The path states as the flat int8 arrays the core wants."""
    n = len(states)
    W = cap + 2
    pw0 = np.zeros((n, W), dtype=np.int8)
    pw1 = np.zeros((n, W), dtype=np.int8)
    pl0 = np.zeros(n, dtype=np.int16)
    pl1 = np.zeros(n, dtype=np.int16)
    for k, (a, b) in enumerate(states):
        pw0[k, :len(a)] = a
        pw1[k, :len(b)] = b
        pl0[k] = len(a)
        pl1[k] = len(b)
    return pw0, pl0, pw1, pl1


def shorten(start, mids, depth, slack, table_bits=23, node_cap=7_000_000,
            level_cap=700_000, log=None):
    """Splice in meet-in-the-middle shortcuts until none is left.

    Returns (move ids, passes, moves saved, overflowed)."""
    best = list(mids)
    saved = passes = 0
    over = False
    while True:
        states = replay(start, best)
        cap = max(len(a) + len(b) for a, b in states) + slack
        pw0, pl0, pw1, pl1 = pack(states, cap)
        n = len(states)
        asav, apart, seg, slen, nodes, ovf = best_shortcut(
            pw0, pl0, pw1, pl1, n, depth, cap, table_bits,
            max(400_000, node_cap), level_cap)
        passes += 1
        if ovf:
            over = True
        # every candidate, best saving first, applied while disjoint
        cand = [(int(asav[j]), int(apart[j]), j,
                 [int(x) for x in seg[j, :int(slen[j])]])
                for j in range(n) if asav[j] > 0]
        if not cand:
            return best, passes, saved, over
        cand.sort(key=lambda c: -c[0])
        taken = []
        used_hi = n + 1
        chosen = []
        for sav, i, j, route in cand:
            if any(not (j <= pi or i >= pj) for pi, pj, _ in chosen):
                continue
            # the meet test is on hashes: prove the segment really joins them
            if replay(states[i], route)[-1] != states[j]:
                if log:
                    log(f"      hash collision at ({i},{j}), rejected")
                continue
            chosen.append((i, j, route))
            if log:
                log(f"      ({i},{j}) span {j - i} -> {len(route)} "
                    f"save {sav}")
        if not chosen:
            return best, passes, saved, over
        chosen.sort(key=lambda c: -c[0])
        for i, j, route in chosen:
            saved += (j - i) - len(route)
            best = best[:i] + route + best[j:]
        if log:
            log(f"      pass {passes}: {len(chosen)} splices, "
                f"length {len(best)}, nodes {nodes}")


# -- drivers ---------------------------------------------------------------

def check():
    """Planted control: splice waste into an optimal path and take it out."""
    rng = np.random.default_rng(7)
    ok = bad = 0
    rows = [json.loads(l) for l in
            open(REPO / "runs/pool/work/near_ac.jsonl", encoding="utf-8")]
    for row in rows[:6]:
        start = tuple(tuple(r) for r in row["relators"])
        mids, tail = split_path(row["moves"])
        if not mids:
            continue
        base, _, _, _ = shorten(start, mids, 3, 4)
        # plant a detour: a move and its inverse, three times over
        k = int(rng.integers(1, max(2, len(base) - 1)))
        waste = []
        for _ in range(3):
            m = int(rng.integers(0, 14))
            waste += [m, int(INV[m])]
        planted = base[:k] + waste + base[k:]
        if replay(start, planted)[-1] != replay(start, base)[-1]:
            print(f"    {row['id']}: planted path does not land where the "
                  f"original does; move pairs are not involutions here")
            bad += 1
            continue
        out, _, sv, _ = shorten(start, planted, 3, 4)
        got = len(out) <= len(base) and replay(start, out)[-1] == \
            replay(start, base)[-1]
        print(f"    {row['id']}: optimal {len(base)}, planted "
              f"{len(planted)}, recovered {len(out)}, saved {sv} "
              f"{'OK' if got else 'FAIL'}")
        ok += got
        bad += not got
    print(f"  control: {ok} recovered, {bad} failed")
    return 0 if bad == 0 else 1


def run(args):
    src = REPO / f"runs/pool/work/near_{args.problem}.jsonl"
    rows = [json.loads(l) for l in open(src, encoding="utf-8")]
    if args.max_gap:
        rows = [r for r in rows if r["gap"] <= args.max_gap]
    if args.min_gap:
        rows = [r for r in rows if r["gap"] >= args.min_gap]
    if args.ids:
        want = set(open(args.ids, encoding="utf-8").read().split())
        rows = [r for r in rows if r["id"] in want or
                f"{r['problem']}-{r['id']}" in want]
    if args.limit:
        rows = rows[:args.limit]
    # a previous run's output is a better starting path than the ledger's
    for seed in args.seed_from:
        sp = pathlib.Path(seed)
        if not sp.exists():
            continue
        shorter = {}
        for line in open(sp, encoding="utf-8"):
            line = line.strip()
            if not line or line[0] != "{":
                continue
            r = json.loads(line)
            if r.get("problem") != args.problem:
                continue
            k = str(r["id"])
            if k not in shorter or r["length"] < shorter[k]["length"]:
                shorter[k] = r
        n = 0
        for row in rows:
            s = shorter.get(row["id"])
            if s and s["length"] < row["ours"]:
                row["ours"] = s["length"]
                row["moves"] = s["moves"]
                n += 1
        print(f"  seeded {n} shorter paths from {sp}", flush=True)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sol = open(out / "solutions.jsonl", "a", encoding="utf-8")
    stable = args.problem == "stable_ac"

    def log(s):
        print(s, flush=True)

    beats = ties = improved = 0
    t_start = time.time()
    for n, row in enumerate(rows, 1):
        start = tuple(tuple(r) for r in row["relators"])
        mids, tail = split_path(row["moves"])
        if len(mids) + len(tail) != row["ours"]:
            log(f"  {row['id']}: stored length {row['ours']} does not match "
                f"{len(mids)}+{len(tail)}; skipped")
            continue
        t0 = time.time()
        best, passes, saved, over = shorten(
            start, mids, args.depth, args.slack,
            node_cap=args.node_cap, level_cap=args.level_cap,
            table_bits=args.table_bits,
            log=log if args.verbose else None)
        total = len(best) + len(tail)
        rec = row["record"]
        mark = "BEAT" if total < rec else ("tie" if total == rec else "")
        log(f"  [{n}/{len(rows)}] {row['problem']} {row['id']} record {rec} "
            f"(k {row['k']}): {row['ours']} -> {total} saved {saved} "
            f"passes {passes}{' OVERFLOW' if over else ''} "
            f"{time.time() - t0:.1f}s {mark}")
        if saved == 0:
            continue
        improved += 1
        moves = [to_move(m) for m in best] + [_rebuild(m) for m in tail]
        chk = verify(Presentation(2, start), moves, stable=stable)
        if not chk:
            log(f"      VERIFIER REJECTED the spliced path: {chk.reason}")
            continue
        sol.write(json.dumps({"id": row["id"], "problem": row["problem"],
                              "length": total,
                              "moves": [_as_json(m) for m in moves],
                              "record_at_find": rec,
                              "was": row["ours"]}) + "\n")
        sol.flush()
        if total < rec:
            beats += 1
        elif total == rec:
            ties += 1
    sol.close()
    log(f"\n  {len(rows)} paths, {improved} shortened, {beats} BEAT a record, "
        f"{ties} landed on one, {(time.time() - t_start) / 60:.1f} min")
    return 0


def _rebuild(m):
    from src.ac.moves import Destabilize, Stabilize
    if m["move"] == "destabilize":
        return Destabilize(m["i"])
    if m["move"] == "stabilize":
        return Stabilize()
    raise ValueError(f"cannot rebuild {m}")


def _as_json(m):
    from src.search.campaign import move_to_json
    return move_to_json(m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", default="ac", choices=("ac", "stable_ac"))
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--slack", type=int, default=6)
    ap.add_argument("--max-gap", type=int, default=0)
    ap.add_argument("--min-gap", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--seed-from", nargs="*", default=[])
    ap.add_argument("--node-cap", type=int, default=7_000_000)
    ap.add_argument("--table-bits", type=int, default=23)
    ap.add_argument("--level-cap", type=int, default=700_000)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="runs/pool/bshort")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    print(f"  bishorten {dt.datetime.now(dt.timezone.utc).isoformat()} "
          f"depth {args.depth} slack {args.slack}", flush=True)
    if args.check:
        return check()
    return run(args)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

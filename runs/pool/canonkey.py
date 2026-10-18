"""The visited set keyed on a canonical presentation, measured against keying
on the exact one.

Backlog item 4. The idea is that the search re-explores presentations that are
the same up to things that cost almost nothing: the two relators in the other
order (which costs NOTHING - the move set and the trivial set are both symmetric
under the swap, so it is an exact symmetry of the graph), a relator replaced by
its inverse (one move), and a relator cyclically rotated (one conjugation per
letter moved). Keying the visited set on a representative of that class should
collapse the duplicates and buy depth at the same node budget.

This is NOT `canon_search.py`. That one canonicalises the STATE, performing the
conjugations and inversions as real moves, so its paths carry the cost of
canonicalising and come out longer. Here the stored state is the real one and
the real moves are expanded from it; only the visited KEY is canonical. The path
that comes back is an ordinary path and the verifier replays it unchanged.

What it costs, honestly: collapsing a class whose members are up to |r| moves
apart can prune the state that was on the shorter path, so the result is a valid
path but no longer a minimum inside the cap. That is why this is measured on
nodes-to-solution and solve rate, not offered as a replacement for the exact
search.

Three key modes:
  0  plain      the exact pair of words, the current behaviour
  1  swap+inv   relator order and relator inversion collapsed
  2  swap+inv+rot  and cyclic rotation collapsed, via Booth's least rotation

Usage (from the repo root):
  python runs/pool/canonkey.py --check
  python runs/pool/canonkey.py --bench 300 --nodes 300000
  python runs/pool/canonkey.py --pool --count 40 --nodes 2000000
"""
import argparse
import json
import os
import pathlib
import sys
import time

os.environ.setdefault("ACC_MAXLEN", "64")

import numpy as np                                            # noqa: E402
from numba import njit                                        # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "runs" / "pool"))
from jit_engine import MAXLEN, _apply, _hash                   # noqa: E402

W = MAXLEN
MODES = (0, 3, 4, 1, 2)

# The EXACT symmetries of the move graph that also fix the trivial set, and so
# are free: any automorphism of the free group that sends each generator to a
# generator or its inverse, applied letterwise to BOTH relators, commutes with
# all fourteen moves (invert, concatenate and conjugate-by-a-generator are all
# defined by word operations), and carries (x, y) to another trivial pair. With
# the relator swap, which the move set and the trivial set are both symmetric
# under, that is a group of order sixteen. Collapsing it is lossless: distance
# to the trivial set is identical for every member of an orbit.
#
# Row m, column l + 2, for l in -2, -1, 0, 1, 2. Column 2 is unused.
_T = []
for (g1, g2) in ((1, 2), (2, 1)):
    for e1 in (1, -1):
        for e2 in (1, -1):
            row = [0] * 5
            row[-2 + 2] = -e2 * g2
            row[-1 + 2] = -e1 * g1
            row[1 + 2] = e1 * g1
            row[2 + 2] = e2 * g2
            _T.append(row)
SYM = np.array(_T, dtype=np.int8)
NSYM = SYM.shape[0]


# -- the canonical form -----------------------------------------------------

@njit(cache=False, inline="always")
def _cyc_reduce(a, la, out):
    """The cyclically reduced core of a: strip matching inverse ends."""
    lo = 0
    hi = la - 1
    while lo < hi and a[lo] == -a[hi]:
        lo += 1
        hi -= 1
    n = 0
    for i in range(lo, hi + 1):
        out[n] = a[i]
        n += 1
    return n


@njit(cache=False, inline="always")
def _booth(s, n, f):
    """Index of the lexicographically least rotation of s[:n]. O(n)."""
    for i in range(2 * n):
        f[i] = -1
    k = 0
    for j in range(1, 2 * n):
        sj = s[j - n] if j >= n else s[j]
        i = f[j - k - 1]
        while i != -1:
            cmpc = s[(k + i + 1) % n]
            if sj == cmpc:
                break
            if sj < cmpc:
                k = j - i - 1
            i = f[i]
        if i == -1 and sj != s[(k + i + 1) % n]:
            if sj < s[k % n]:
                k = j
            f[j - k] = -1
        else:
            f[j - k] = i + 1
    return k


@njit(cache=False, inline="always")
def _rot_into(s, n, k, out):
    for i in range(n):
        out[i] = s[(k + i) % n]
    return n


@njit(cache=False, inline="always")
def _canon_word(a, la, mode, out, t1, t2, t3, f):
    """The canonical representative of relator a, written into out.

    mode 1 takes the smaller of the word and its inverse; mode 2 also takes the
    least cyclic rotation of each first."""
    n = _cyc_reduce(a, la, t1)
    if n == 0:
        return 0
    # t2 = inverse of the core
    for i in range(n):
        t2[i] = -t1[n - 1 - i]
    if mode >= 2:
        k = _booth(t1, n, f)
        _rot_into(t1, n, k, t3)
        for i in range(n):
            t1[i] = t3[i]
        k = _booth(t2, n, f)
        _rot_into(t2, n, k, t3)
        for i in range(n):
            t2[i] = t3[i]
    take2 = False
    for i in range(n):
        if t2[i] != t1[i]:
            take2 = t2[i] < t1[i]
            break
    src = t2 if take2 else t1
    for i in range(n):
        out[i] = src[i]
    return n


@njit(cache=False, inline="always")
def _word_orbit(a, la, nsym, hh):
    """The hash of this word under each of the nsym letter symmetries, in one
    pass over the word."""
    p = np.uint64(1099511628211)
    for m in range(nsym):
        hh[m] = (np.uint64(1469598103934665603) ^ np.uint64(la + 1)) * p
    for i in range(la):
        c = a[i] + 2
        for m in range(nsym):
            hh[m] = (hh[m] ^ np.uint64(SYM[m, c] + 3)) * p
    for m in range(nsym):
        h = hh[m]
        h ^= h >> np.uint64(29)
        h *= np.uint64(0xBF58476D1CE4E5B9)
        h ^= h >> np.uint64(32)
        hh[m] = h | np.uint64(1)
    return nsym


@njit(cache=False, inline="always")
def _mix(x, y):
    h = x * np.uint64(0x9E3779B97F4A7C15) ^ y
    h ^= h >> np.uint64(31)
    h *= np.uint64(0xD6E8FEB86659FD93)
    h ^= h >> np.uint64(32)
    return h | np.uint64(1)


@njit(cache=False, inline="always")
def _orbit_key(a, la, b, lb, nsym, ha, hb):
    """The least hash over the orbit: lossless for nsym 1 (swap only) and 8."""
    _word_orbit(a, la, nsym, ha)
    _word_orbit(b, lb, nsym, hb)
    best = np.uint64(0xFFFFFFFFFFFFFFFF)
    for m in range(nsym):
        x = ha[m]
        y = hb[m]
        k = _mix(x, y) if x < y else _mix(y, x)
        if k < best:
            best = k
    return best


@njit(cache=False, inline="always")
def _ckey(a, la, b, lb, mode, ca, cb, t1, t2, t3, f):
    """The visited key. mode 0 is the plain exact hash."""
    if mode == 0:
        return _hash(a, la, b, lb)
    if mode == 3:
        return _orbit_key(a, la, b, lb, 1, ca.view(np.uint64),
                          cb.view(np.uint64))
    if mode == 4:
        return _orbit_key(a, la, b, lb, NSYM, ca.view(np.uint64),
                          cb.view(np.uint64))
    na = _canon_word(a, la, mode, ca, t1, t2, t3, f)
    nb = _canon_word(b, lb, mode, cb, t1, t2, t3, f)
    # order the pair so the relator swap collapses
    first = True
    if nb < na:
        first = False
    elif nb == na:
        for i in range(na):
            if cb[i] != ca[i]:
                first = ca[i] < cb[i]
                break
    if first:
        return _hash(ca, na, cb, nb)
    return _hash(cb, nb, ca, na)


# -- the search -------------------------------------------------------------

@njit(cache=False)
def search(r0, n0, r1, n1, cap, max_nodes, table_bits, mode):
    """Best first on total relator length toward a trivial pair.

    Identical to jit_engine.search except that the visited set is keyed by
    _ckey. Returns (found, length, path, nodes)."""
    size = 1 << table_bits
    mask = np.uint64(size - 1)
    keys = np.zeros(size, dtype=np.uint64)

    w0 = np.zeros(max_nodes * MAXLEN, dtype=np.int8)
    w1 = np.zeros(max_nodes * MAXLEN, dtype=np.int8)
    ln0 = np.zeros(max_nodes, dtype=np.int16)
    ln1 = np.zeros(max_nodes, dtype=np.int16)
    parent = np.full(max_nodes, -1, dtype=np.int32)
    pmove = np.zeros(max_nodes, dtype=np.int8)
    nxt = np.full(max_nodes, -1, dtype=np.int32)

    nbucket = 2 * cap + 8
    head = np.full(nbucket, -1, dtype=np.int32)

    o0 = np.zeros(MAXLEN, dtype=np.int8)
    o1 = np.zeros(MAXLEN, dtype=np.int8)
    buf = np.zeros(MAXLEN, dtype=np.int8)
    tmp = np.zeros(MAXLEN + 4, dtype=np.int8)
    ca = np.zeros(8 * (NSYM + 2), dtype=np.int8)
    cb = np.zeros(8 * (NSYM + 2), dtype=np.int8)
    t1 = np.zeros(MAXLEN, dtype=np.int8)
    t2 = np.zeros(MAXLEN, dtype=np.int8)
    t3 = np.zeros(MAXLEN, dtype=np.int8)
    f = np.zeros(2 * MAXLEN + 4, dtype=np.int32)
    path = np.zeros(4096, dtype=np.int8)

    for i in range(n0):
        w0[i] = r0[i]
    for i in range(n1):
        w1[i] = r1[i]
    ln0[0] = n0
    ln1[0] = n1
    count = 1
    t0 = n0 + n1
    head[t0] = 0
    h = _ckey(r0, n0, r1, n1, mode, ca, cb, t1, t2, t3, f)
    idx = h & mask
    while keys[idx] != np.uint64(0):
        idx = (idx + np.uint64(1)) & mask
    keys[idx] = h

    best = 0
    while best < nbucket:
        cur = head[best]
        if cur == -1:
            best += 1
            continue
        head[best] = nxt[cur]
        a0 = cur * MAXLEN
        la = ln0[cur]
        lb = ln1[cur]
        for mid in range(14):
            na, nb = _apply(mid, w0[a0:a0 + MAXLEN], la,
                            w1[a0:a0 + MAXLEN], lb, o0, o1, buf, tmp)
            if na == 0 or nb == 0 or na > cap or nb > cap:
                continue
            if na + nb == 2 and abs(o0[0]) != abs(o1[0]):
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
            hh = _ckey(o0, na, o1, nb, mode, ca, cb, t1, t2, t3, f)
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
            ln0[count] = na
            ln1[count] = nb
            parent[count] = cur
            pmove[count] = mid
            t = na + nb
            nxt[count] = head[t]
            head[t] = count
            if t < best:
                best = t
            count += 1
    return False, 0, path, count


def solve(relators, cap, max_nodes, mode, table_bits=24):
    r0 = np.array(relators[0], dtype=np.int8)
    r1 = np.array(relators[1], dtype=np.int8)
    found, m, path, nodes = search(r0, len(r0), r1, len(r1), cap,
                                   max_nodes, table_bits, mode)
    return ([int(x) for x in path[:m]] if found else None), int(nodes)


# -- checks and measurement -------------------------------------------------

def check():
    """Every path a canonical key returns must still replay, and mode 0 must
    reproduce the existing engine exactly."""
    from jit_engine import solve_jit
    from src.ac.presentation import Presentation
    from src.ac.verify import verify
    from src.search.engine import FINISH_AC, replay, to_move

    rows = [json.loads(l) for l in
            open(REPO / "runs/bench/ms1190.jsonl", encoding="utf-8")][:40]
    bad = 0
    for row in rows:
        rels = [tuple(r) for r in row["relators"]]
        size = sum(len(r) for r in rels)
        cap = size + 6
        ref, _ = solve_jit(rels, cap=cap, max_nodes=200_000)
        mine, _ = solve(rels, cap, 200_000, 0)
        if (ref is None) != (mine is None) or (ref is not None
                                               and len(ref) != len(mine)):
            print(f"    {row['id']}: mode 0 disagrees with jit_engine "
                  f"({None if ref is None else len(ref)} vs "
                  f"{None if mine is None else len(mine)})")
            bad += 1
        for mode in (1, 2, 3, 4):
            got, _ = solve(rels, cap, 200_000, mode)
            if got is None:
                continue
            end = replay(tuple(rels), got)[-1]
            if end not in FINISH_AC:
                print(f"    {row['id']} mode {mode}: path does not end at a "
                      f"trivial pair")
                bad += 1
                continue
            moves = [to_move(m) for m in got + FINISH_AC[end]]
            chk = verify(Presentation(2, tuple(rels)), moves, stable=False)
            if not chk:
                print(f"    {row['id']} mode {mode}: verifier rejected: "
                      f"{chk.reason}")
                bad += 1
    print(f"  check: {len(rows)} presentations, {bad} failures")
    return 1 if bad else 0


def measure(rows, cap_of, nodes, label):
    """Per-mode results, reported BOTH over everything and over the subset
    every mode solved.

    The averages over everything are misleading on their own: a mode that
    solves more also solves harder cases, which pulls its mean nodes and mean
    length up. Nodes-to-solution is only comparable on the common subset."""
    res = {}
    for mode in MODES:
        got = {}
        t0 = time.time()
        seen = 0
        for row in rows:
            rels = [tuple(r) for r in row["relators"]]
            path, n = solve(rels, cap_of(rels), nodes, mode)
            seen += n
            if path is not None:
                got[row["id"]] = (n, len(path))
        res[mode] = {"got": got, "seconds": time.time() - t0,
                     "nodes_per_s": seen / max(1e-9, time.time() - t0)}

    # a mode that solves nothing would empty the intersection and take the
    # comparison with it, so only modes that solved something define it
    common = None
    for mode in MODES:
        ids = set(res[mode]["got"])
        if not ids:
            continue
        common = ids if common is None else (common & ids)
    common = common or set()
    names = {0: "plain", 1: "swap+inv", 2: "swap+inv+rot",
             3: "swap", 4: "swap+letters"}
    print(f"\n  {label}: {len(rows)} presentations, budget {nodes:,}, "
          f"common subset {len(common)}")
    print(f"  {'mode':14} {'solved':>8} {'nodes/solve':>12} "
          f"{'len':>7} | {'common nodes':>13} {'common len':>11} "
          f"{'nodes/s':>10}")
    base = None
    for mode in MODES:
        r = res[mode]
        g = r["got"]
        ns = [v[0] for v in g.values()]
        ls = [v[1] for v in g.values()]
        # a mode that solved nothing is not in the intersection at all
        cn = [g[i][0] for i in common if i in g]
        cl = [g[i][1] for i in common if i in g]
        if len(cn) != len(common):
            cn = cl = []
        mean_cn = sum(cn) / len(cn) if cn else 0
        mean_cl = sum(cl) / len(cl) if cl else 0
        if base is None:
            base = (mean_cn, mean_cl)
        print(f"  {names[mode]:14} {len(g):>4}/{len(rows):<3} "
              f"{(sum(ns) / max(1, len(ns))):>12,.0f} "
              f"{(sum(ls) / max(1, len(ls))):>7.1f} | "
              f"{mean_cn:>13,.0f} {mean_cl:>11.1f} "
              f"{r['nodes_per_s']:>10,.0f}")
    if base and base[0]:
        print(f"  on the common subset, relative to plain:")
        for mode in MODES:
            g = res[mode]["got"]
            cn = [g[i][0] for i in common if i in g]
            cl = [g[i][1] for i in common if i in g]
            if len(cn) != len(common) or not cn:
                print(f"    {names[mode]:14} not in the common subset")
                continue
            mn = sum(cn) / len(cn)
            ml = sum(cl) / len(cl)
            print(f"    {names[mode]:14} nodes x{mn / base[0]:.3f}  "
                  f"length x{ml / base[1]:.3f}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--bench", type=int, default=0)
    ap.add_argument("--pool", action="store_true")
    ap.add_argument("--count", type=int, default=40)
    ap.add_argument("--rec-lo", type=int, default=31)
    ap.add_argument("--rec-hi", type=int, default=45)
    ap.add_argument("--nodes", type=int, default=300_000)
    ap.add_argument("--slack", type=int, default=6)
    args = ap.parse_args()

    if args.check:
        return check()
    if args.bench:
        rows = [json.loads(l) for l in
                open(REPO / "runs/bench/ms1190.jsonl", encoding="utf-8")]
        rows = rows[:args.bench]
        measure(rows, lambda r: sum(len(x) for x in r) + args.slack,
                args.nodes, "ms1190")
    if args.pool:
        rows = []
        for line in open(REPO / "runs/pool/pool.jsonl", encoding="utf-8"):
            r = json.loads(line)
            if r["ac_best"] is not None and args.rec_lo <= r["ac_best"] <= args.rec_hi:
                rows.append(r)
        step = max(1, len(rows) // args.count)
        rows = rows[::step][:args.count]
        measure(rows, lambda r: sum(len(x) for x in r) + args.slack,
                args.nodes, f"pool records {args.rec_lo}-{args.rec_hi}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

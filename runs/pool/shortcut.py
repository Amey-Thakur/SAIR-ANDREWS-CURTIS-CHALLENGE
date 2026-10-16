"""Path shortcutting: the exact search asked for the distance between two states.

The join between two of this campaign's measurements. (1) Our paths run about ten
percent longer than the record holders', everywhere, structurally: 95 against 91,
106 against 93, 119 against 106, 142 against 131. (2) The exact bidirectional
search is excellent over SHORT ranges - it returns true minima inside a tight cap,
and that exactness is the source of every steal we have made.

So stop asking a search to find a whole path. Take a path we already hold,
s0..sn, pick a window (i, j), and ask the exact search for the shortest route
between the two CONCRETE states si and sj. If it is shorter than j - i, splice it
in. A ten percent gap on a 130-move path is thirteen moves, and they never have to
be found at once.

This is not `engine.shorten`. That hunts for detours and cycles of radius at most
`depth` between states already on the path, and measured 0 moves on beam paths and
about 2 percent on greedy ones. Shortcutting asks a different question - the true
minimum distance between these two specific states - over spans of 12 to 25 moves,
which is exactly the range where the exact search is reliable.

`search_between` is `jit_tieband.search_bidir` with the backward start
parameterised instead of hardcoded to (x, y); that hardcoding is why no existing
tool here could answer this question.

**Every splice is guarded twice**: the returned segment is replayed to confirm it
really carries si to sj (the meet test is on hashes alone, so a collision must not
be allowed to corrupt a path), and the whole spliced path is replayed through
src.ac.verify on both boards before anything is written.

Usage (from the repo root):
  python runs/pool/shortcut.py --check          # planted-detour control first
  python runs/pool/shortcut.py --paths runs/pool/policy/k1_close_64k.jsonl \\
      --ids runs/pool/policy/two_resp.txt
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
def search_between(a0, na, a1, nb, c0, mc, c1, md, cap, max_nodes, table_bits):
    """Shortest move sequence from (a0, a1) to (c0, c1) inside the cap.

    Identical to jit_tieband.search_bidir except that the backward half starts
    from a state passed in rather than from (x, y). The move set is closed under
    inversion, so a state reached from the far endpoint by m1..mk is carried to
    that endpoint by INV[mk]..INV[m1]."""
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

    for i in range(na):
        fw0[i] = a0[i]
    for i in range(nb):
        fw1[i] = a1[i]
    fl0[0] = na
    fl1[0] = nb
    fcount = 1
    h = _hash(a0, na, a1, nb)
    j = h & mask
    while fk[j] != np.uint64(0):
        j = (j + np.uint64(1)) & mask
    fk[j] = h
    fv[j] = 0

    for i in range(mc):
        bw0[i] = c0[i]
    for i in range(md):
        bw1[i] = c1[i]
    bl0[0] = mc
    bl1[0] = md
    bcount = 1
    h = _hash(c0, mc, c1, md)
    j = h & mask
    while bk[j] != np.uint64(0):
        j = (j + np.uint64(1)) & mask
    bk[j] = h
    bv[j] = 0

    # the endpoints may already coincide
    if _hash(a0, na, a1, nb) == _hash(c0, mc, c1, md):
        return True, 0, path, 2

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
            a = cur * MAXLEN
            if forward:
                la = fl0[cur]
                lb = fl1[cur]
                src0 = fw0
                src1 = fw1
            else:
                la = bl0[cur]
                lb = bl1[cur]
                src0 = bw0
                src1 = bw1
            for mid in range(14):
                nx, ny = _apply(mid, src0[a:a + MAXLEN], la,
                                src1[a:a + MAXLEN], lb, o0, o1, buf, tmp)
                if nx == 0 or ny == 0 or nx + ny > cap:
                    continue
                hh = _hash(o0, nx, o1, ny)
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
                    b = fcount * MAXLEN
                    for i in range(nx):
                        fw0[b + i] = o0[i]
                    for i in range(ny):
                        fw1[b + i] = o1[i]
                    fl0[fcount] = nx
                    fl1[fcount] = ny
                    fp[fcount] = cur
                    fm[fcount] = mid
                    fcount += 1
                else:
                    if bcount >= max_nodes:
                        return False, 0, path, fcount + bcount
                    own_k[j] = hh
                    own_v[j] = bcount
                    b = bcount * MAXLEN
                    for i in range(nx):
                        bw0[b + i] = o0[i]
                    for i in range(ny):
                        bw1[b + i] = o1[i]
                    bl0[bcount] = nx
                    bl1[bcount] = ny
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


def between(sa, sb, cap, max_nodes, table_bits):
    """Shortest route from state sa to state sb inside the cap, or None."""
    if cap + 2 > MAXLEN:
        return None, 0
    a0 = np.array(sa[0], dtype=np.int8)
    a1 = np.array(sa[1], dtype=np.int8)
    c0 = np.array(sb[0], dtype=np.int8)
    c1 = np.array(sb[1], dtype=np.int8)
    found, m, path, nodes = search_between(a0, len(a0), a1, len(a1),
                                           c0, len(c0), c1, len(c1),
                                           cap, max_nodes, table_bits)
    return ([int(x) for x in path[:m]] if found else None), int(nodes)


def apply_path(state, mids):
    """Replay mids from state with the compiled move code."""
    w0 = np.zeros(MAXLEN, dtype=np.int8)
    w1 = np.zeros(MAXLEN, dtype=np.int8)
    o0 = np.zeros(MAXLEN, dtype=np.int8)
    o1 = np.zeros(MAXLEN, dtype=np.int8)
    buf = np.zeros(MAXLEN, dtype=np.int8)
    tmp = np.zeros(MAXLEN + 2, dtype=np.int8)
    w0[:len(state[0])] = np.array(state[0], dtype=np.int8)
    w1[:len(state[1])] = np.array(state[1], dtype=np.int8)
    l0, l1 = len(state[0]), len(state[1])
    for m in mids:
        l0, l1 = _apply(m, w0, l0, w1, l1, o0, o1, buf, tmp)
        w0[:] = 0
        w1[:] = 0
        w0[:l0] = o0[:l0]
        w1[:l1] = o1[:l1]
    return (tuple(int(x) for x in w0[:l0]), tuple(int(x) for x in w1[:l1]))


def states_of(start, mids):
    out = [tuple(tuple(w) for w in start)]
    cur = out[0]
    for m in mids:
        cur = apply_path(cur, [m])
        out.append(cur)
    return out


def smooth(start, mids, wmin, wmax, slack, nodes, bits, verbose=True):
    """Sweep every window and splice in any shorter exact route.

    Returns (path, windows tried, splices, moves saved, reach failures)."""
    best = list(mids)
    tried = splices = saved = unreached = 0
    changed = True
    while changed:
        changed = False
        states = states_of(start, best)
        n = len(best)
        i = 0
        while i < n:
            hi = min(n, i + wmax)
            j = hi
            while j >= i + wmin:
                span = j - i
                sa, sb = states[i], states[j]
                # the cap must hold the window we already have, or the exact
                # search cannot even re-derive it
                have = max(len(states[k][0]) + len(states[k][1])
                           for k in range(i, j + 1))
                cap = have + slack
                tried += 1
                seg, _ = between(sa, sb, cap, nodes, bits)
                if seg is None:
                    unreached += 1
                    j -= 1
                    continue
                if len(seg) < span:
                    # guard: the meet test is on hashes, so confirm the segment
                    # really carries sa to sb before it touches the path
                    if apply_path(sa, seg) != sb:
                        if verbose:
                            print(f"      window ({i},{j}): hash collision, "
                                  f"segment rejected", flush=True)
                        j -= 1
                        continue
                    if verbose:
                        print(f"      window ({i},{j}) span {span} -> "
                              f"{len(seg)}, cap {cap}", flush=True)
                    best = best[:i] + seg + best[j:]
                    splices += 1
                    saved += span - len(seg)
                    changed = True
                    break
                j -= 1
            if changed:
                break
            i += 1
    return best, tried, splices, saved, unreached


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", nargs="+",
                    default=["runs/pool/policy/k1_close_64k.jsonl",
                             "runs/pool/policy/resp_256k.jsonl"])
    ap.add_argument("--ids", default="runs/pool/policy/two_resp.txt")
    ap.add_argument("--wmin", type=int, default=6)
    ap.add_argument("--wmax", type=int, default=22)
    ap.add_argument("--slack", type=int, default=2)
    ap.add_argument("--nodes", type=int, default=2_000_000)
    ap.add_argument("--bits", type=int, default=21)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default="runs/pool/policy/shortcut")
    args = ap.parse_args()

    rows = {r["ac_id"]: r for r in
            (json.loads(l) for l in
             open(REPO / "runs/pool/pool.jsonl", encoding="utf-8"))}

    from jit_tieband import solve_bidir  # noqa: E402
    from src.ac.moves import Destabilize  # noqa: E402
    from src.ac.presentation import Presentation  # noqa: E402
    from src.ac.verify import move_to_json, verify  # noqa: E402
    from src.search import engine as E  # noqa: E402

    # warm the compiler on something tiny
    between(((1,), (2,)), ((1,), (2,)), 8, 1000, 12)

    if args.check:
        print("planted-detour control: splice a known detour into an optimal "
              "path and confirm shortcutting removes exactly it", flush=True)
        cand = [r for r in rows.values() if r["ac_best"] is not None
                and 10 <= r["ac_best"] <= 14]
        cand.sort(key=lambda r: r["ac_best"])
        ok = bad = 0
        for r in cand[:5]:
            start = tuple(tuple(w) for w in r["relators"])
            size = len(start[0]) + len(start[1])
            base, _ = solve_bidir(r["relators"], size + 6, 2_000_000, 21)
            if base is None:
                continue
            base = list(base)
            # move 0 is an involution, so 0,0 is a two-move cycle: planting
            # three of them adds exactly six wasted moves and does not move the
            # endpoint
            k = len(base) // 2
            spoilt = base[:k] + [0, 0, 0, 0, 0, 0] + base[k:]
            assert apply_path(start, spoilt) == apply_path(start, base)
            got, tried, spl, saved, unre = smooth(
                start, spoilt, 2, args.wmax, 6, 2_000_000, 21, verbose=False)
            good = len(got) <= len(base) and apply_path(start, got) == \
                apply_path(start, base)
            ok += good
            bad += not good
            print(f"  {r['ac_id']}: optimal {len(base)}, spoilt "
                  f"{len(spoilt)}, shortcut {len(got)}  "
                  f"({spl} splices, {saved} moves saved, {tried} windows)"
                  f"{'' if good else '   FAILED'}", flush=True)
        print(f"\ncontrol: {ok} recovered, {bad} failed", flush=True)
        os._exit(0)

    best = {}
    for f in args.paths:
        p = REPO / f
        if not p.exists():
            continue
        for line in open(p, encoding="utf-8"):
            if not line.strip():
                continue
            q = json.loads(line)
            if not q.get("verified"):
                continue
            c = q["challenge_id"]
            if c not in best or q["length"] < best[c]["length"]:
                best[c] = q
    want = [l.split()[0] for l in
            open(REPO / args.ids, encoding="utf-8") if l.strip()]

    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    scored = 0
    for c in want:
        if c not in best:
            print(f"  {c}: no stored path", flush=True)
            continue
        pool = rows[c]
        rec = pool["ac_best"]
        start = tuple(tuple(w) for w in pool["relators"])
        have = list(best[c]["moves"])
        print(f"  {c} record {rec} (k {pool['ac_k']}), from {len(have)} moves, "
              f"windows {args.wmin}-{args.wmax}, slack {args.slack}:",
              flush=True)
        t0 = time.time()
        got, tried, spl, saved, unre = smooth(start, have, args.wmin, args.wmax,
                                              args.slack, args.nodes, args.bits)
        el = time.time() - t0
        ac = [E.to_move(m) for m in got]
        stable = ac + [Destabilize(1), Destabilize(0)]
        begin = Presentation(2, start)
        vok = (verify(begin, ac, stable=False).ok
               and verify(begin, stable, stable=True).ok)
        sc = vok and rec is not None and len(ac) <= rec
        scored += sc
        print(f"    -> {len(got)} against record {rec}: {spl} splices, "
              f"{saved} moves saved, {tried} windows, {unre} unreached, "
              f"verify={vok}, {el:.0f}s{'   <-- SCORES' if sc else ''}",
              flush=True)
        if not sc:
            continue
        with (out / "solutions.jsonl").open("a", encoding="utf-8") as log:
            for problem, moves in (("ac", ac), ("stable_ac", stable)):
                log.write(json.dumps(
                    {"id": pool["id"], "problem": problem,
                     "length": len(moves),
                     "moves": [move_to_json(m) for m in moves],
                     "relators": pool["relators"], "found_at": stamp,
                     "cfg": {"method": "beam+shortcut"}}) + "\n")
    print(f"\n{scored} at or under the record", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()

"""A JIT-compiled search core, for coverage rather than optimality.

The Python engine manages about 75,000 nodes a second, and coverage on this
pool is bought with nodes: raising the budget from 300k to 2M took the easiest
band from 2 solved of 12 to 7 of 12. This core is the same search and the same
fourteen moves, written so numba can compile it: relators are int8 arrays, the
visited set is an open-addressing table of 64-bit hashes, and the frontier is a
bucket queue keyed on total relator length, so pushing and popping cost nothing.

A hash collision can only make the search skip a state, never invent a path,
and every path is replayed by our verifier and then by the official one before
it is submitted.

Usage (from the repo root):
  python runs/pool/jit_engine.py          # equivalence with the Python engine, then speed
"""
import numpy as np
from numba import njit

# Words never exceed the length cap, and the only move that can grow a word
# past the cap is conjugation, which adds at most 2. The pool's longest
# presentation totals 40, so 44 covers every search that respects its cap.
# solve_bidir refuses a cap this cannot hold. Halving this from 64 is what
# lets several searches share the machine.
MAXLEN = 44
GENS = (1, -1, 2, -2)


@njit(cache=False, inline="always")
def _join(a, la, b, lb, out):
    """out = a b, freely reduced. Both inputs are already reduced, so only the
    junction can cancel."""
    k = 0
    m = la if la < lb else lb
    while k < m and a[la - 1 - k] == -b[k]:
        k += 1
    n = 0
    for i in range(la - k):
        out[n] = a[i]
        n += 1
    for i in range(k, lb):
        out[n] = b[i]
        n += 1
    return n


@njit(cache=False, inline="always")
def _inv(a, la, out):
    for i in range(la):
        out[i] = -a[la - 1 - i]
    return la


@njit(cache=False, inline="always")
def _conj(a, la, c, out, tmp):
    """out = c a c^-1, freely reduced."""
    tmp[0] = c
    n = _join(tmp, 1, a, la, out)
    tmp[0] = -c
    for i in range(n):
        a_copy = out[i]
        tmp[i + 1] = a_copy
    # tmp now holds [-c] at 0; rebuild as out = (c a) then append -c
    m = 0
    for i in range(n):
        tmp[i] = out[i]
    tmp[n] = -c
    # cancel at the junction between (c a) and c^-1
    if n > 0 and tmp[n - 1] == c:
        m = n - 1
    else:
        m = n + 1
    for i in range(m):
        out[i] = tmp[i]
    return m


@njit(cache=False, inline="always")
def _apply(mid, s0, l0, s1, l1, o0, o1, buf, tmp):
    """Apply move id to (s0, s1), writing into (o0, o1). Returns new lengths."""
    if mid == 0:
        n = _inv(s0, l0, o0)
        for i in range(l1):
            o1[i] = s1[i]
        return n, l1
    if mid == 1:
        for i in range(l0):
            o0[i] = s0[i]
        n = _inv(s1, l1, o1)
        return l0, n
    if mid == 2:
        n = _join(s0, l0, s1, l1, o0)
        for i in range(l1):
            o1[i] = s1[i]
        return n, l1
    if mid == 3:
        m = _inv(s1, l1, buf)
        n = _join(s0, l0, buf, m, o0)
        for i in range(l1):
            o1[i] = s1[i]
        return n, l1
    if mid == 4:
        n = _join(s1, l1, s0, l0, o1)
        for i in range(l0):
            o0[i] = s0[i]
        return l0, n
    if mid == 5:
        m = _inv(s0, l0, buf)
        n = _join(s1, l1, buf, m, o1)
        for i in range(l0):
            o0[i] = s0[i]
        return l0, n
    if mid < 10:
        c = GENS[mid - 6]
        n = _conj(s0, l0, c, o0, tmp)
        for i in range(l1):
            o1[i] = s1[i]
        return n, l1
    c = GENS[mid - 10]
    n = _conj(s1, l1, c, o1, tmp)
    for i in range(l0):
        o0[i] = s0[i]
    return l0, n


@njit(cache=False, inline="always")
def _hash(a, la, b, lb):
    h = np.uint64(1469598103934665603)
    p = np.uint64(1099511628211)
    h = (h ^ np.uint64(la + 1)) * p
    for i in range(la):
        h = (h ^ np.uint64(a[i] + 3)) * p
    h = (h ^ np.uint64(lb + 2)) * p
    for i in range(lb):
        h = (h ^ np.uint64(b[i] + 3)) * p
    h ^= h >> np.uint64(29)
    h *= np.uint64(0xBF58476D1CE4E5B9)
    h ^= h >> np.uint64(32)
    return h | np.uint64(1)


@njit(cache=False)
def search(r0, n0, r1, n1, cap, max_nodes, table_bits):
    """Best first on total relator length toward a trivial pair.

    Returns (found, path length, path array, nodes seen)."""
    size = 1 << table_bits
    mask = np.uint64(size - 1)
    keys = np.zeros(size, dtype=np.uint64)
    slot = np.zeros(size, dtype=np.int32)

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
    tmp = np.zeros(MAXLEN + 2, dtype=np.int8)
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
    h = _hash(r0, n0, r1, n1)
    idx = h & mask
    while keys[idx] != np.uint64(0):
        idx = (idx + np.uint64(1)) & mask
    keys[idx] = h
    slot[idx] = 0

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
            na, nb = _apply(mid, w0[a0:a0 + MAXLEN], la, w1[a0:a0 + MAXLEN], lb,
                            o0, o1, buf, tmp)
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
            slot[j] = count
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


def solve_jit(relators, cap=48, max_nodes=20_000_000, table_bits=26):
    """Move ids to a trivial pair, or None."""
    r0 = np.array(relators[0], dtype=np.int8)
    r1 = np.array(relators[1], dtype=np.int8)
    found, m, path, nodes = search(r0, len(r0), r1, len(r1),
                                   cap, max_nodes, table_bits)
    return ([int(x) for x in path[:m]] if found else None), int(nodes)


if __name__ == "__main__":
    import json
    import os
    import random
    import sys
    import time

    sys.path.insert(0, ".")
    from src.search import engine as E

    report = open("runs/pool/jit_probe.txt", "w", encoding="utf-8")

    def say(line):
        print(line, flush=True)
        report.write(line + "\n")
        report.flush()

    # every move must produce exactly what the verified Python engine produces
    @njit(cache=False)
    def one_move(r0, n0, r1, n1, mid, o0, o1, buf, tmp):
        return _apply(mid, r0, n0, r1, n1, o0, o1, buf, tmp)

    rng = random.Random(11)
    o0 = np.zeros(MAXLEN, dtype=np.int8)
    o1 = np.zeros(MAXLEN, dtype=np.int8)
    buf = np.zeros(MAXLEN, dtype=np.int8)
    tmp = np.zeros(MAXLEN + 2, dtype=np.int8)
    checked = bad = 0
    for _ in range(1500):
        s = tuple(E.free_reduce(tuple(rng.choice((1, -1, 2, -2))
                                      for _ in range(rng.randint(1, 10))))
                  for _ in range(2))
        if not all(s):
            continue
        a = np.array(s[0], dtype=np.int8)
        b = np.array(s[1], dtype=np.int8)
        pa = np.zeros(MAXLEN, dtype=np.int8)
        pb = np.zeros(MAXLEN, dtype=np.int8)
        pa[:len(a)] = a
        pb[:len(b)] = b
        for mid in range(14):
            na, nb = one_move(pa, len(a), pb, len(b), mid, o0, o1, buf, tmp)
            got = (tuple(int(x) for x in o0[:na]), tuple(int(x) for x in o1[:nb]))
            want = E.step(s, mid)
            checked += 1
            if got != want:
                bad += 1
                if bad <= 3:
                    say(f"  MISMATCH move {mid} on {s}: got {got} want {want}")
    say(f"equivalence: {checked} move checks, {bad} mismatches")

    if bad == 0:
        rows = [json.loads(l) for l in
                open("runs/pool/pool.jsonl", encoding="utf-8")]
        solved = [r for r in rows if r["ac_best"] is not None
                  and 21 <= r["ac_best"] <= 50][:6]
        t0 = time.time()
        solve_jit(solved[0]["relators"], 48, 100_000, 20)
        say(f"jit compile: {time.time() - t0:.0f}s")
        for r in solved:
            t0 = time.time()
            ids, nodes = solve_jit(r["relators"], cap=48,
                                   max_nodes=8_000_000, table_bits=24)
            dt = time.time() - t0
            rate = nodes / dt / 1e6 if dt > 0 else 0
            if ids is None:
                say(f"  {r['id']} held {r['ac_best']:>3}: not found, "
                    f"{nodes:,} nodes in {dt:.0f}s ({rate:.2f}M/s)")
            else:
                say(f"  {r['id']} held {r['ac_best']:>3}: FOUND raw {len(ids)}, "
                    f"{nodes:,} nodes in {dt:.0f}s ({rate:.2f}M/s)")
    report.close()
    os._exit(0)

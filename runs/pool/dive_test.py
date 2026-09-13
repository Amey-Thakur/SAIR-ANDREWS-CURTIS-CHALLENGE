"""Annealing dive search on the 56-challenge pool sample.

Random moves; downhill always accepted, uphill accepted with a cooling
probability; restart from the best state reached; cut cycles; shorten.
Memory-light: no visited set. Compares with the held best per band.
"""
import json
import math
import random
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"C:\Users\archi\OneDrive\Desktop\Shreyas\SAIR-ANDREWS-CURTIS-CHALLENGE")
from src.search import engine as E  # noqa: E402

TRIV = E.FINISH_AC


def cut_cycles(start, mids):
    states, index, out = [start], {start: 0}, []
    for m in mids:
        t = E.step(states[-1], m)
        k = index.get(t)
        if k is not None:
            for s in states[k + 1:]:
                index.pop(s, None)
            states = states[:k + 1]
            out = out[:k]
        else:
            states.append(t)
            out.append(m)
            index[t] = len(states) - 1
    return out


def dive(state, rng, steps, cap, t0):
    path = []
    L = len(state[0]) + len(state[1])
    best_len, best_k, best_state = L, -1, state
    s = state
    for k in range(steps):
        T = t0 * (1.0 - k / steps) + 0.05
        m = rng.randrange(14)
        t = E.step(s, m)
        a, b = t
        if not a or not b or len(a) > cap or len(b) > cap:
            continue
        Lt = len(a) + len(b)
        d = Lt - L
        if d <= 0 or rng.random() < math.exp(-d / T):
            s, L = t, Lt
            path.append(m)
            if t in TRIV:
                return path, True, len(path) - 1, t, L
            if L < best_len:
                best_len, best_k, best_state = L, len(path) - 1, t
    return path, False, best_k, best_state, best_len


def work(task):
    r, budget_s = task
    start = tuple(tuple(w) for w in r["relators"])
    rng = random.Random(int(r["id"]) * 7919 + 17)
    cap = 3 * max(len(start[0]), len(start[1])) + 6
    t0 = time.time()
    base_state, base_path = start, []
    base_len = len(start[0]) + len(start[1])
    tries = 0
    while time.time() - t0 < budget_s:
        tries += 1
        path, ok, bk, bs, bl = dive(base_state, rng, 20000, cap,
                                    rng.choice((0.5, 1.0, 2.0, 3.0)))
        if ok:
            raw = base_path + path
            core = cut_cycles(start, raw)
            end = E.replay(start, core)[-1]
            depth = 3 if len(core) <= 2500 else 2
            core = E.shorten(start, core, depth=depth)
            ac = E.shorten(start, core + E.FINISH_AC[end], depth=depth)
            assert E.replay(start, ac)[-1] == E.TARGET
            st = min(len(core) + len(E.FINISH_STABLE[end]), len(ac) + 2)
            return r["id"], len(raw), len(ac), st, tries, time.time() - t0
        if bk >= 0 and bl < base_len:
            base_path = base_path + path[:bk + 1]
            base_state, base_len = bs, bl
        elif tries % 6 == 0:
            base_state, base_path = start, []
            base_len = len(start[0]) + len(start[1])
    return r["id"], None, None, None, tries, time.time() - t0


if __name__ == "__main__":
    rows = [json.loads(l) for l in open("runs/pool/pool.jsonl", encoding="utf-8")]
    rng = random.Random(7)
    bands = [(21, 50, 12), (51, 100, 16), (101, 300, 16), (301, 1000, 12)]
    sample = []
    for lo, hi, n in bands:
        pick = [r for r in rows if r["ac_best"] is not None and lo <= r["ac_best"] <= hi]
        sample += [((lo, hi), r) for r in rng.sample(pick, n)]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(work, [(r, 20) for _, r in sample]))
    info = {r["id"]: (band, r) for band, r in sample}
    print(f"annealing dives, 20 s each, {len(sample)} challenges in {time.time()-t0:.0f}s\n")
    print("band held      n solved ac<=held ac<held sac<=held  median raw->ac  median ours/held")
    for band in [(b[0], b[1]) for b in bands]:
        items = [(info[i][1], raw, ac, st)
                 for i, raw, ac, st, tr, secs in res if info[i][0] == band]
        solved = [x for x in items if x[2] is not None]
        le = sum(1 for r, raw, ac, st in solved if ac <= r["ac_best"])
        lt = sum(1 for r, raw, ac, st in solved if ac < r["ac_best"])
        sle = sum(1 for r, raw, ac, st in solved if st <= r["sac_best"])
        mr = (f"{statistics.median([x[1] for x in solved]):.0f}->"
              f"{statistics.median([x[2] for x in solved]):.0f}") if solved else "-"
        ratio = (f"{statistics.median([x[2] / x[0]['ac_best'] for x in solved]):.2f}"
                 if solved else "-")
        print(f"{band[0]:>4}-{band[1]:<5} {len(items):>4} {len(solved):>6} {le:>8} "
              f"{lt:>7} {sle:>9}  {mr:>13}  {ratio:>8}")

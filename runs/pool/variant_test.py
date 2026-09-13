import heapq, itertools, json, random, statistics, sys, time
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, r"C:\Users\archi\OneDrive\Desktop\Shreyas\SAIR-ANDREWS-CURTIS-CHALLENGE")
from src.search import engine as E

def cyc(w):
    i, j = 0, len(w) - 1
    while i < j and w[i] == -w[j]:
        i += 1; j -= 1
    return j - i + 1 if w else 0

def greedy(start, max_nodes, mode, cap):
    if start in E.FINISH_AC:
        return [], 1
    key = (lambda a, b: len(a) + len(b)) if mode == "raw" else \
          (lambda a, b: cyc(a) + cyc(b) + 0.01 * (len(a) + len(b)))
    parent = {start: None}
    counter = itertools.count()
    heap = [(key(*start), 0, next(counter), start)]
    while heap and len(parent) < max_nodes:
        _, d, _, s = heapq.heappop(heap)
        for mid, t in E.expand(s):
            if t in parent:
                continue
            a, b = t
            if not a or not b:
                continue
            if cap and (len(a) > cap or len(b) > cap):
                continue
            parent[t] = (s, mid)
            if t in E.FINISH_AC:
                return E._path(parent, t), len(parent)
            heapq.heappush(heap, (key(a, b), d + 1, next(counter), t))
    return None, len(parent)

def work(task):
    r, mode, capmul = task
    s = tuple(tuple(w) for w in r["relators"])
    cap = capmul * max(len(s[0]), len(s[1])) if capmul else None
    core, seen = greedy(s, 300_000, mode, cap)
    if core is None:
        return r["id"], mode, capmul, None, None
    end = E.replay(s, core)[-1]
    core = E.shorten(s, core)
    ac = E.shorten(s, core + E.FINISH_AC[end])
    st = min(len(core) + len(E.FINISH_STABLE[end]), len(ac) + 2)
    return r["id"], mode, capmul, len(ac), st

if __name__ == "__main__":
    rows = [json.loads(l) for l in open("runs/pool/pool.jsonl", encoding="utf-8")]
    rng = random.Random(7)
    bands = [(21, 50, 12), (51, 100, 16), (101, 300, 16), (301, 1000, 12)]
    sample = []
    for lo, hi, n in bands:
        pick = [r for r in rows if r["ac_best"] is not None and lo <= r["ac_best"] <= hi]
        sample += [((lo, hi), r) for r in rng.sample(pick, n)]
    variants = [("raw", 0), ("cyc", 0), ("cyc", 2), ("raw", 2)]
    tasks = [(r, m, c) for _, r in sample for m, c in variants]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(work, tasks))
    print(f"{len(tasks)} solves in {time.time()-t0:.0f}s\n")
    info = {r["id"]: (band, r) for band, r in sample}
    print("variant        band      n solved ac<=held ac<held sac<=held")
    for m, c in variants:
        for band in [(b[0], b[1]) for b in bands]:
            items = [(info[i][1], ac, st) for i, mm, cc, ac, st in res
                     if mm == m and cc == c and info[i][0] == band]
            solved = [x for x in items if x[1] is not None]
            le = sum(1 for r, ac, st in solved if ac <= r["ac_best"])
            lt = sum(1 for r, ac, st in solved if ac < r["ac_best"])
            sle = sum(1 for r, ac, st in solved if st <= r["sac_best"])
            print(f"{m}+cap{c:<2}   {band[0]:>4}-{band[1]:<5} {len(items):>3} {len(solved):>6} {le:>8} {lt:>7} {sle:>9}")
        print()

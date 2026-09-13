import json, random, statistics, sys, time
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, r"C:\Users\archi\OneDrive\Desktop\Shreyas\SAIR-ANDREWS-CURTIS-CHALLENGE")
from src.search.engine import solve

def work(r):
    t0 = time.time()
    out = solve(r["relators"], max_nodes=300_000)
    ac = out["ac"]
    st = out["stable_ac"]
    return r, (None if ac is None else len(ac)), (None if st is None else len(st)), time.time() - t0

if __name__ == "__main__":
    rows = [json.loads(l) for l in open("runs/pool/pool.jsonl", encoding="utf-8")]
    rng = random.Random(7)
    bands = [(21, 50, 12), (51, 100, 16), (101, 300, 16), (301, 1000, 12)]
    sample = []
    for lo, hi, n in bands:
        pick = [r for r in rows if r["ac_best"] is not None and lo <= r["ac_best"] <= hi]
        for r in rng.sample(pick, n):
            sample.append(((lo, hi), r))
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(work, [r for _, r in sample]))
    by_band = {}
    for (band, _), (r, ac, st, secs) in zip(sample, results):
        by_band.setdefault(band, []).append((r, ac, st, secs))
    print(f"sampled {len(sample)} in {time.time()-t0:.0f}s on 6 workers\n")
    print("band held      n  solved  ac<=held  ac<held  sac<=held  median ours/held (solved)")
    for band, items in by_band.items():
        solved = [(r, ac, st) for r, ac, st, _ in items if ac is not None]
        ac_le = sum(1 for r, ac, st in solved if ac <= r["ac_best"])
        ac_lt = sum(1 for r, ac, st in solved if ac < r["ac_best"])
        st_le = sum(1 for r, ac, st in solved if r["sac_best"] is not None and st <= r["sac_best"])
        ratio = statistics.median([ac / r["ac_best"] for r, ac, st in solved]) if solved else float("nan")
        print(f"{band[0]:>4}-{band[1]:<5} {len(items):>4} {len(solved):>7} {ac_le:>9} {ac_lt:>8} {st_le:>10}   {ratio:.2f}")
    print("\nexamples where we score:")
    shown = 0
    for band, items in by_band.items():
        for r, ac, st, secs in items:
            if ac is not None and ac <= r["ac_best"] and shown < 8:
                print(f"  {r['id']} size {len(r['relators'][0])+len(r['relators'][1])} held ac {r['ac_best']} (k {r['ac_k']}) -> ours {ac}; sac held {r['sac_best']} -> ours {st}")
                shown += 1

import json, statistics, sys, time
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, r"C:\Users\archi\OneDrive\Desktop\Shreyas\SAIR-ANDREWS-CURTIS-CHALLENGE")
from src.search.engine import solve

def work(inst):
    t0 = time.time()
    out = solve(inst["initial_relators"], max_nodes=300_000)
    return inst, (None if out["ac"] is None else len(out["ac"])), time.time() - t0

if __name__ == "__main__":
    d = json.load(open("runs/official/repo/competition/examples/training_424.json", encoding="utf-8"))
    insts = d["instances"]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(work, insts))
    solved = [(i, L) for i, L, _ in res if L is not None]
    print(f"training_424: solved {len(solved)} of {len(insts)} at 300k nodes in {time.time()-t0:.0f}s")
    le = sum(1 for i, L in solved if L <= i["length"])
    print(f"  ours <= known on {le} of {len(solved)} solved; median ours/known "
          f"{statistics.median([L / i['length'] for i, L in solved]):.2f}")
    by_n = {}
    for i, L, _ in res:
        by_n.setdefault(i["n"], [0, 0])
        by_n[i["n"]][1] += 1
        if L is not None:
            by_n[i["n"]][0] += 1
    print("  solved by n: " + ", ".join(f"n={n}: {a}/{b}" for n, (a, b) in sorted(by_n.items())))
    wl = {}
    for i, L, _ in res:
        k = len(i["w_vector"])
        wl.setdefault(k, [0, 0]); wl[k][1] += 1
        if L is not None: wl[k][0] += 1
    print("  solved by |w|: " + ", ".join(f"{k}: {a}/{b}" for k, (a, b) in sorted(wl.items())))
    unsolved = [i for i, L, _ in res if L is None]
    print("  unsolved examples (n, w, known length): " + "; ".join(f"({i['n']}, {i['w']}, {i['length']})" for i in unsolved[:8]))

"""Hunt for paths on challenges nobody has solved yet.

On an unsolved challenge any verified path is a full point, and the same path
plus [16, 15] is a second point on the Stable AC board, so length does not
matter here; coverage does. Two methods: best-first greedy with a large node
budget, and annealing dives with restarts. Every path is verified by our
verifier before it is written, in the campaign's solutions.jsonl format, so
`python -m src.harness.submit OUT` reads it directly and re-checks it with the
official verifier.

Usage (from the repo root):
  python runs/pool/hunt.py --method dive   --count 24 --skip 0  --budget-s 30 --workers 5 --out runs/pool/hunt_dive
  python runs/pool/hunt.py --method greedy --count 8  --skip 24 --nodes 2000000 --workers 2 --out runs/pool/hunt_greedy
"""
import argparse
import datetime as dt
import json
import math
import pathlib
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

REPO = r"C:\Users\archi\OneDrive\Desktop\Shreyas\SAIR-ANDREWS-CURTIS-CHALLENGE"
sys.path.insert(0, REPO)
from src.ac.moves import Destabilize  # noqa: E402
from src.ac.presentation import Presentation  # noqa: E402
from src.ac.verify import move_to_json, verify  # noqa: E402
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


def dive_search(start, budget_s, seed):
    rng = random.Random(seed)
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
            return cut_cycles(start, base_path + path)
        if bk >= 0 and bl < base_len:
            base_path = base_path + path[:bk + 1]
            base_state, base_len = bs, bl
        elif tries % 6 == 0:
            base_state, base_path = start, []
            base_len = len(start[0]) + len(start[1])
    return None


def finish(start, core):
    """Shorten a path to a trivial state and turn it into verified AC and
    Stable AC move lists."""
    depth = 3 if len(core) <= 2500 else 2
    end = E.replay(start, core)[-1]
    core = E.shorten(start, core, depth=depth)
    ac_ids = E.shorten(start, core + E.FINISH_AC[end], depth=depth)
    ac = [E.to_move(m) for m in ac_ids]
    stable = min([E.to_move(m) for m in core] + E.FINISH_STABLE[end],
                 ac + [Destabilize(1), Destabilize(0)], key=len)
    begin = Presentation(2, start)
    if not verify(begin, ac, stable=False) or not verify(begin, stable, stable=True):
        raise AssertionError("a hunted path failed local verification")
    return ac, stable


def work(task):
    r, method, budget_s, nodes = task
    start = tuple(tuple(w) for w in r["relators"])
    t0 = time.time()
    if method == "greedy":
        core, _ = E.greedy(start, max_nodes=nodes)
    else:
        core = dive_search(start, budget_s, int(r["id"]) * 7919 + 17)
    if core is None:
        return r, None, None, time.time() - t0
    ac, stable = finish(start, core)
    return (r, [move_to_json(m) for m in ac],
            [move_to_json(m) for m in stable], time.time() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=("dive", "greedy"), required=True)
    ap.add_argument("--count", type=int, default=24)
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--budget-s", type=float, default=30.0)
    ap.add_argument("--nodes", type=int, default=2_000_000)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(pathlib.Path(REPO) / "runs/pool/pool.jsonl",
                                          encoding="utf-8")]
    unsolved = [r for r in rows if r["ac_best"] is None]
    random.Random(args.seed).shuffle(unsolved)
    chosen = unsolved[args.skip:args.skip + args.count]
    out = pathlib.Path(REPO) / args.out
    out.mkdir(parents=True, exist_ok=True)
    cfg = {"method": args.method, "budget_s": args.budget_s, "nodes": args.nodes}
    print(f"hunting {len(chosen)} of {len(unsolved)} unsolved with {cfg}, "
          f"{args.workers} workers", flush=True)

    found = 0
    t0 = time.time()
    with (out / "solutions.jsonl").open("a", encoding="utf-8") as log, \
            ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(work, (r, args.method, args.budget_s, args.nodes))
                   for r in chosen]
        for fut in as_completed(futures):
            r, ac, stable, secs = fut.result()
            if ac is None:
                print(f"  {r['id']} size {len(r['relators'][0]) + len(r['relators'][1])}: "
                      f"not found in {secs:.0f}s", flush=True)
                continue
            found += 1
            stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            for problem, moves in (("ac", ac), ("stable_ac", stable)):
                log.write(json.dumps({"id": r["id"], "problem": problem,
                                      "length": len(moves), "moves": moves,
                                      "relators": r["relators"], "found_at": stamp,
                                      "cfg": cfg}) + "\n")
            log.flush()
            print(f"  {r['id']}: FOUND ac {len(ac)} stable {len(stable)} in {secs:.0f}s",
                  flush=True)
    print(f"found {found} of {len(chosen)} in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()

# ==============================================================================
# File: campaign.py
# Description: Runs the engine over a pool of presentations on every core, and
#   keeps the shortest verified path for each presentation and each problem.
#   Results go to an append-only log, so a crash loses at most the
#   presentations in flight and a rerun resumes where it stopped. The log holds
#   solutions, and sequences stay private until the competition ends, which is
#   why runs/ is never committed.
# Usage: python -m src.search.campaign POOL.jsonl --out runs/NAME [options]
# Tech Stack: Python 3.10+, standard library only
# ==============================================================================

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from ..ac.verify import move_to_json
from .engine import solve

PROBLEMS = ("ac", "stable_ac")


def load_pool(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def load_best(out):
    """The shortest recorded path per (id, problem), read back from the log."""
    best = {}
    log = pathlib.Path(out) / "solutions.jsonl"
    if log.exists():
        with log.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:          # a line still being written
                    continue
                key = (rec["id"], rec["problem"])
                if key not in best or rec["length"] < best[key]["length"]:
                    best[key] = rec
    return best


def _work(task):
    rec, cfg = task
    t0 = time.time()
    try:
        out = solve(rec["relators"], max_nodes=cfg["max_nodes"],
                    caps=cfg["caps"], weights=cfg["weights"],
                    depth=cfg["depth"])
    except Exception as exc:        # an engine bug must not stop the campaign
        return rec, None, f"{type(exc).__name__}: {exc}", time.time() - t0
    found = {p: [move_to_json(m) for m in out[p]]
             for p in PROBLEMS if out[p] is not None}
    return rec, found, None, time.time() - t0


def summarize(pool, best):
    ids = [r["id"] for r in pool]
    s = {}
    for p in PROBLEMS:
        lengths = [best[(i, p)]["length"] for i in ids if (i, p) in best]
        s[p] = {"solved": len(lengths), "of": len(ids),
                "total_moves": sum(lengths)}
    refs = [r for r in pool if r.get("greedy_ref") is not None]
    if refs:
        ours = [(r, best.get((r["id"], "ac"))) for r in refs]
        both = [(r["greedy_ref"], b["length"]) for r, b in ours if b]
        beyond = sum(1 for r in pool if r.get("greedy_ref") is None
                     and (r["id"], "ac") in best)
        s["vs_acsolver_greedy"] = {
            "their_solved": len(refs),
            "we_solve_of_theirs": len(both),
            "we_solve_beyond_theirs": beyond,
            "their_moves_on_shared": sum(a for a, _ in both),
            "our_ac_moves_on_shared": sum(b for _, b in both),
            "note": "their paths end at any trivial state; ours end at (x, y)",
        }
    return s


def parse_caps(text):
    return tuple(None if c.strip().lower() == "none" else int(c)
                 for c in text.split(","))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pool", help="JSONL of {id, relators}")
    ap.add_argument("--out", required=True, help="run directory under runs/")
    ap.add_argument("--workers", type=int,
                    default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--max-nodes", type=int, default=300_000)
    ap.add_argument("--caps", default="none",
                    help="comma list of relator length caps, none for no cap")
    ap.add_argument("--weights", default="0",
                    help="comma list of depth weights")
    ap.add_argument("--depth", type=int, default=3,
                    help="detour radius for path shortening")
    ap.add_argument("--improve", action="store_true",
                    help="rerun solved presentations, keeping only shorter paths")
    ap.add_argument("--limit", type=int, default=0,
                    help="only the first N presentations")
    args = ap.parse_args(argv)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg = {"max_nodes": args.max_nodes, "caps": parse_caps(args.caps),
           "weights": tuple(float(w) for w in args.weights.split(",")),
           "depth": args.depth}

    best = load_best(out)
    pool = list(load_pool(args.pool))
    if args.limit:
        pool = pool[:args.limit]
    todo = [r for r in pool
            if args.improve or not all((r["id"], p) in best for p in PROBLEMS)]
    print(f"{len(pool)} presentations, {len(todo)} to run, "
          f"{args.workers} workers, cfg {cfg}", flush=True)

    stamp_cfg = {**cfg, "caps": list(cfg["caps"]),
                 "weights": list(cfg["weights"])}
    done = recorded = 0
    t0 = time.time()
    with (out / "solutions.jsonl").open("a", encoding="utf-8") as log, \
         (out / "errors.jsonl").open("a", encoding="utf-8") as errors, \
         ProcessPoolExecutor(max_workers=args.workers) as ex:
        # No max_tasks_per_child. On this Windows Python the pool never
        # replaces a retired worker, so the first benchmark hung silently at
        # exactly workers x 25 = 150 completions with no error anywhere.
        futures = [ex.submit(_work, (r, cfg)) for r in todo]
        for fut in as_completed(futures):
            done += 1
            try:
                rec, found, err, secs = fut.result()
            except Exception as exc:        # a worker died, e.g. out of memory
                errors.write(json.dumps({"id": None,
                                         "error": f"worker: {exc!r}"}) + "\n")
                errors.flush()
                continue
            if err:
                errors.write(json.dumps({"id": rec["id"], "error": err}) + "\n")
                errors.flush()
            for problem, moves in (found or {}).items():
                key = (rec["id"], problem)
                if key in best and best[key]["length"] <= len(moves):
                    continue
                entry = {"id": rec["id"], "problem": problem,
                         "length": len(moves), "moves": moves,
                         "relators": rec["relators"],
                         "found_at": dt.datetime.now(dt.timezone.utc)
                         .isoformat(timespec="seconds"),
                         "cfg": stamp_cfg}
                log.write(json.dumps(entry) + "\n")
                best[key] = entry
                recorded += 1
            log.flush()
            if done % 25 == 0 or done == len(todo):
                solved = {p: sum(1 for r in pool if (r["id"], p) in best)
                          for p in PROBLEMS}
                rate = done / max(time.time() - t0, 1e-9)
                print(f"  {done}/{len(todo)}  ac {solved['ac']}  stable "
                      f"{solved['stable_ac']}  recorded {recorded}  "
                      f"{rate:.2f}/s", flush=True)

    summary = summarize(pool, best)
    summary["elapsed_s"] = round(time.time() - t0, 1)
    (out / "summary.json").write_text(json.dumps(summary, indent=2),
                                      encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

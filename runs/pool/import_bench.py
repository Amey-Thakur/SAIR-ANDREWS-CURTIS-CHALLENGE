import json
pool = [json.loads(l) for l in open("runs/pool/pool.jsonl", encoding="utf-8")]
by_rel = {json.dumps(r["relators"]): r["id"] for r in pool}
bench = {}
for l in open("runs/bench/ms1190/solutions.jsonl", encoding="utf-8"):
    r = json.loads(l)
    key = (json.dumps(r["relators"]), r["problem"])
    if key not in bench or r["length"] < bench[key]["length"]:
        bench[key] = r
matched = 0
with open("runs/pool/main/solutions.jsonl", "a", encoding="utf-8") as fh:
    for (rel, problem), r in bench.items():
        pid = by_rel.get(rel)
        if pid is None:
            continue
        fh.write(json.dumps(dict(r, id=pid, source="ms1190-benchmark")) + "\n")
        matched += 1
print(f"benchmark: {len(bench)} solutions, {matched} matched to pool challenges by exact relators")

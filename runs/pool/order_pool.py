import json
rows = [json.loads(l) for l in open("runs/pool/pool.jsonl", encoding="utf-8")]
size = lambda r: len(r["relators"][0]) + len(r["relators"][1])
unsolved = sorted([r for r in rows if r["ac_best"] is None], key=size)
solved = sorted([r for r in rows if r["ac_best"] is not None], key=lambda r: -r["ac_best"])
out = []
for i in range(max(len(unsolved), len(solved))):
    if i < len(solved):
        out.append(solved[i])
    if i < len(unsolved):
        out.append(unsolved[i])
with open("runs/pool/pool_priority.jsonl", "w", encoding="utf-8") as fh:
    for r in out:
        fh.write(json.dumps(r) + "\n")
print(f"reordered {len(out)}: {len(solved)} solved by held best descending, interleaved with {len(unsolved)} unsolved by size")

# ==============================================================================
# File: submit.py
# Description: Sends Discovery Track solutions to the SAIR API in the published
#   TXT contract. A path is sent only when it can score: the challenge is
#   unsolved, or our path is no longer than the current best. Every line must
#   replay in our verifier (the campaign guarantees that) and again in the
#   official reference verifier, with the same length, before it is sent. Our
#   ledger records what the platform verified, so nothing is resent unless it
#   got shorter. The API key is read from SAIR_API_KEY and never printed. Dry
#   run is the default; --live sends.
# Usage: python -m src.harness.submit runs/pool/main [--live] [--max-batches N]
# Tech Stack: Python 3.10+, standard library only
# ==============================================================================

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

from ..search.campaign import load_best

BASE = "https://api.sair.foundation/api/public/v1"
COMPETITION = "acc"
TEAM_NUMBER = "ACC01-T00013"
# Cloudflare answers error 1010 to a non-browser user agent before the API
# ever sees the request, which looks exactly like a revoked key.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

REPO = pathlib.Path(__file__).resolve().parents[2]
OFFICIAL = REPO / "runs" / "official" / "repo" / "competition"
MANIFEST = OFFICIAL / "tools" / "verifier" / "data" / "manifest.json"
PREFIX = {"ac": "ac-", "stable_ac": "sac-"}
CONJ = (1, -1, 2, -2)
RANK = {"unsolved": 0, "steal": 1, "tie": 2, "defend": 3}


# -- the API ----------------------------------------------------------------

def call(method, path, body=None, retry=True):
    """One API call. GETs back off on 429; a POST is never retried, because
    the submission endpoint has no idempotency and a retry is a second batch."""
    key = os.environ.get("SAIR_API_KEY")
    if not key:
        raise SystemExit("SAIR_API_KEY is not set")
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json",
               "Content-Type": "application/json", "User-Agent": UA}
    for _ in range(6 if retry else 1):
        req = urllib.request.Request(BASE + path, data=data, method=method,
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else {}), dict(r.headers)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                payload = json.loads(raw)
            except ValueError:
                payload = {"raw": raw[:500]}
            if e.code == 429 and retry:
                time.sleep(min(int(e.headers.get("Retry-After", "30")), 300))
                continue
            return e.code, payload, dict(e.headers)
    return 429, {"error": "still rate limited after retries"}, {}


def participation():
    code, body, _ = call("GET", f"/competitions/{COMPETITION}/me")
    if code != 200:
        return {"ok": False, "status": code, "body": body}
    return {"ok": True, **body["data"]}


def current_bests():
    """challengeId -> (current best length or None, teams tied), both problems."""
    out = {}
    for problem in PREFIX:
        code, body, _ = call(
            "GET", f"/competitions/{COMPETITION}/discoveries/snapshot"
                   f"?problem={problem}")
        if code != 200:
            raise SystemExit(f"cannot read the {problem} snapshot: "
                             f"HTTP {code} {str(body)[:300]}")
        for item in body["data"]["items"]:
            out[item["challengeId"]] = (item["currentBestLength"],
                                        item["kTeams"])
    return out


# -- translation ------------------------------------------------------------

def official_id(move):
    """The official move id for one of our verified move objects (as JSON).

    AC ids 0-13 are the same table as the engine's. Stable AC keeps 0-13 and
    adds 14 for stabilize and 15 + i for destabilizing relator i."""
    kind = move["move"]
    if kind == "invert" and move["i"] in (0, 1):
        return move["i"]
    if kind == "multiply":
        pair, sign = (move["i"], move["j"]), move["sign"]
        if pair == (0, 1):
            return 2 if sign == 1 else 3
        if pair == (1, 0):
            return 4 if sign == 1 else 5
    if kind == "conjugate" and move["i"] in (0, 1) and move["c"] in CONJ:
        return (6 if move["i"] == 0 else 10) + CONJ.index(move["c"])
    if kind == "stabilize":
        return 14
    if kind == "destabilize" and 0 <= move["i"] <= 7:
        return 15 + move["i"]
    raise ValueError(f"no official id for {move}")


def to_line(problem, pid, moves):
    ids = ", ".join(str(official_id(m)) for m in moves)
    return f"{PREFIX[problem]}{pid}: [{ids}]"


def official_check(lines):
    """Replay lines in the official reference verifier.

    Returns ({challenge id: verified length}, [failed results])."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
        name = fh.name
    env = {**os.environ, "PYTHONPATH": str(OFFICIAL / "tools"),
           "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "verifier", "--manifest", str(MANIFEST),
             "--submission", name, "--pretty"],
            capture_output=True, env=env, cwd=str(OFFICIAL.parent))
    finally:
        os.unlink(name)
    try:
        receipt = json.loads(proc.stdout.decode("utf-8"))
    except ValueError:
        raise SystemExit(
            f"the official verifier returned no JSON (exit {proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace')[:600]}")
    results = receipt.get("results", [])
    ok = {r["challenge_id"]: r.get("length") for r in results if r.get("ok")}
    bad = [r for r in results if not r.get("ok") and not r.get("skipped")]
    return ok, bad


# -- what to send -----------------------------------------------------------

def load_sent(out):
    """Challenge id -> shortest length the platform verified for this team."""
    sent = {}
    path = pathlib.Path(out) / "submitted.jsonl"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("ok"):
                cid = r["challenge_id"]
                if cid not in sent or r["length"] < sent[cid]:
                    sent[cid] = r["length"]
    return sent


def plan(out, bests, sent):
    """Every scoring opportunity, best first: unsolved challenges, then strict
    improvements by the size of the gain, then ties, then shortening a record
    we already hold alone."""
    rows = []
    for (pid, problem), rec in load_best(out).items():
        cid = PREFIX[problem] + pid
        if cid not in bests:
            continue                        # not a scored challenge
        ours = rec["length"]
        if cid in sent and sent[cid] <= ours:
            continue                        # nothing new to send
        held, k = bests[cid]
        if held is None:
            kind, gain = "unsolved", 0
        elif ours < held:
            kind = "defend" if sent.get(cid) == held and k == 1 else "steal"
            gain = held - ours
        elif ours == held:
            kind, gain = "tie", 0
        else:
            continue                        # longer than the record: no points
        rows.append({"kind": kind, "gain": gain, "cid": cid, "held": held,
                     "k": k, "length": ours, "problem": problem, "pid": pid,
                     "moves": rec["moves"]})
    rows.sort(key=lambda r: (RANK[r["kind"]], -r["gain"], r["cid"]))
    return rows


def batches(rows, max_lines, max_bytes):
    cur, size = [], 0
    for row in rows:
        b = len(row["line"].encode("utf-8")) + 1
        if cur and (len(cur) >= max_lines or size + b > max_bytes):
            yield cur
            cur, size = [], 0
        cur.append(row)
        size += b
    if cur:
        yield cur


def poll(sid, timeout_s=1200):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        code, body, _ = call("GET",
                             f"/competitions/{COMPETITION}/submissions/{sid}")
        if code == 200 and body["data"]["status"] in ("complete", "failed"):
            return body["data"]
        time.sleep(15)
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", help="campaign directory holding solutions.jsonl")
    ap.add_argument("--live", action="store_true", help="actually send")
    ap.add_argument("--max-batches", type=int, default=2,
                    help="batches to send in this invocation")
    args = ap.parse_args(argv)
    out = pathlib.Path(args.out)

    bests = current_bests()
    sent = load_sent(out)
    rows = plan(out, bests, sent)
    for row in rows:
        row["line"] = to_line(row["problem"], row["pid"], row["moves"])
    kinds = collections.Counter(r["kind"] for r in rows)
    print(f"opportunities: {dict(kinds)}  (total {len(rows)})")

    if rows:
        ok, bad = official_check([r["line"] for r in rows])
        if bad:
            print(f"official verifier REJECTED {len(bad)}; first: "
                  f"{json.dumps(bad[:3])[:600]}")
        mismatch = [r for r in rows
                    if r["cid"] in ok and ok[r["cid"]] != r["length"]]
        if mismatch:
            print(f"length mismatch on {len(mismatch)}; first {mismatch[0]['cid']}")
        rows = [r for r in rows
                if r["cid"] in ok and ok[r["cid"]] == r["length"]]
    print(f"verified by the official verifier: {len(rows)}")
    for r in rows[:6]:
        print(f"  {r['kind']:8} {r['cid']}  ours {r['length']}  "
              f"held {r['held']}  k {r['k']}")

    code, body, _ = call("GET", f"/competitions/{COMPETITION}/submission-spec")
    if code != 200:
        raise SystemExit(f"cannot read the submission spec: HTTP {code}")
    spec = body["data"]
    limits = spec["limits"]
    chunks = list(batches(rows, limits["maxSolutions"],
                          limits["maxBodyBytes"] - 65536))
    print(f"{len(chunks)} batch(es) at up to {limits['maxSolutions']} lines; "
          f"daily limit {limits['dailySubmissions']}")
    if not args.live or not chunks:
        return 0

    me = participation()
    if not me.get("ok") or not me.get("canSubmit") or not spec["submissionOpen"]:
        print(f"not submitting: canSubmit={me.get('canSubmit')} "
              f"open={spec['submissionOpen']} "
              f"blocked={me.get('submitBlockedReason')}")
        return 3

    batch_dir = out / "batches"
    batch_dir.mkdir(exist_ok=True)
    for n, chunk in enumerate(chunks[:args.max_batches], 1):
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        text = "\n".join(r["line"] for r in chunk) + "\n"
        (batch_dir / f"{stamp}-{n}.txt").write_text(text, encoding="utf-8")
        mix = dict(collections.Counter(r["kind"] for r in chunk))
        try:
            code, body, headers = call(
                "POST", f"/competitions/{COMPETITION}/submissions",
                {"payload": {"text": text},
                 "meta": {"description": f"batch {stamp}-{n}"}},
                retry=False)
        except Exception as exc:
            print(f"batch {n}: POST outcome UNCERTAIN ({exc!r}). Check team "
                  f"history before sending again; stopping.")
            return 5
        with (out / "submit_log.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": stamp, "batch": n, "lines": len(chunk),
                                 "mix": mix, "status": code,
                                 "body": body}) + "\n")
        if code == 429:
            details = (body.get("error") or {}).get("details")
            print(f"batch {n}: daily quota exhausted {details}; stopping")
            return 4
        if code != 202:
            print(f"batch {n}: HTTP {code} {json.dumps(body)[:600]}; stopping")
            return 4
        sid = body["data"]["submissionId"]
        print(f"batch {n}: accepted as submission {sid}, {len(chunk)} lines "
              f"{mix}; waiting for verification")
        final = poll(sid)
        by_cid = {r["cid"]: r for r in chunk}
        with (out / "submitted.jsonl").open("a", encoding="utf-8") as fh:
            if final is None:
                print(f"  still verifying after the wait; re-read submission {sid} later")
                for r in chunk:
                    fh.write(json.dumps({"challenge_id": r["cid"], "ok": None,
                                         "submissionId": sid, "at": stamp}) + "\n")
                continue
            outcomes = collections.Counter()
            for res in final.get("results", []):
                cid = res["challenge_id"]
                entry = {"challenge_id": cid, "ok": res.get("ok"),
                         "submissionId": sid, "at": stamp}
                if res.get("ok"):
                    entry["length"] = res["length"]
                    outcomes["ok"] += 1
                else:
                    entry["code"] = res.get("code")
                    outcomes[res.get("code") or "skipped"] += 1
                entry["kind"] = by_cid.get(cid, {}).get("kind")
                fh.write(json.dumps(entry) + "\n")
            print(f"  {final['status']}: {dict(outcomes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

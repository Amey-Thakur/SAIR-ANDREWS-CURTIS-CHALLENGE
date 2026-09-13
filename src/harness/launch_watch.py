# ==============================================================================
# File: launch_watch.py
# Description: One look at everything that changes when the Discovery Track
#   opens: the published submission schema, whether this team can submit, both
#   leaderboards, and any ACC page on the official docs site. Anything new is
#   saved under the output directory, and a single JSON status line is printed
#   so a scheduled run can decide what to do next. Reads only; never submits.
# Usage: python -m src.harness.launch_watch runs/official
# Tech Stack: Python 3.10+, standard library only
# ==============================================================================

from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import re
import sys
import urllib.request

from .submit import TEAM_NUMBER, UA, call

DOCS = "https://docs.sair.foundation"


def _save_if_changed(path, obj):
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def main(argv=None):
    out = pathlib.Path((argv or sys.argv[1:] or ["runs/official"])[0])
    out.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    status = {"at": now}

    code, body, _ = call("GET", "/competitions/acc")
    spec = body.get("data", {}).get("submissionSpec", {}) if code == 200 else {}
    status["spec_keys"] = sorted(spec)
    status["schema_published"] = bool(set(spec) - {"kind"})
    status["spec_changed"] = _save_if_changed(out / "spec_acc.json", body)

    code, body, _ = call("GET", "/competitions/acc/me")
    data = body.get("data", {}) if code == 200 else {}
    status["can_submit"] = data.get("canSubmit")
    status["blocked"] = data.get("submitBlockedReason")

    status["leaderboards"] = {}
    for problem in ("ac", "stable_ac"):
        code, body, _ = call(
            "GET", f"/competitions/acc/leaderboard?problem={problem}&limit=100")
        entry = {"status": code}
        if code == 200:
            items = body.get("data", {}).get("items", [])
            entry["rows"] = len(items)
            mine = [r for r in items if r.get("teamNumber") == TEAM_NUMBER]
            entry["ours"] = mine[0] if mine else None
            entry["top"] = items[:3]
            snap = out / f"leaderboard_{problem}.jsonl"
            with snap.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": now, "body": body}) + "\n")
        else:
            entry["error"] = (body.get("error") or {}).get("code") \
                if isinstance(body, dict) else None
        status["leaderboards"][problem] = entry

    try:
        sitemap = _fetch(f"{DOCS}/sitemap.xml")
        pages = sorted({u for u in re.findall(r"<loc>([^<]+)</loc>", sitemap)
                        if re.search(r"acc|andrews|curtis", u, re.I)
                        and "/docs-md/" in u})
        status["docs_pages"] = pages
        docs_dir = out / "docs"
        docs_dir.mkdir(exist_ok=True)
        for url in pages:
            text = _fetch(url)
            name = re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("/docs-md/")[-1])
            path = docs_dir / name
            digest = hashlib.sha256(text.encode()).hexdigest()
            if not path.exists() or hashlib.sha256(
                    path.read_bytes()).hexdigest() != digest:
                path.write_text(text, encoding="utf-8")
    except Exception as exc:
        status["docs_error"] = repr(exc)[:200]

    status["ready"] = bool(status["schema_published"] and status["can_submit"])
    # ASCII escapes, so a team name outside cp1252 cannot crash a Windows
    # console halfway through a scheduled run.
    print(json.dumps(status))
    return 0


if __name__ == "__main__":
    sys.exit(main())

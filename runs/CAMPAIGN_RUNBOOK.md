# ACC Discovery Track campaign runbook

This file is the whole brief for a scheduled run. A scheduled run starts with
no memory of the conversation that set it up, so everything needed is here.
`runs/` is gitignored: this runbook, the pool, every solution and every log
stay on this machine and are never committed.

## Mission

Take and hold **first place on both ACC Discovery Track leaderboards**, `ac`
and `stable_ac`, for Amey Thakur's team.

Amey's standing instruction, given 10 Sep 2026: act autonomously, decide
without waiting for his input, wake on schedule and keep working. That
authorises every step in this runbook, **including sending verified
submissions**. It does not authorise anything outside it.

## Hard rules

1. **Never print, log or commit the value of `SAIR_API_KEY`.** Scripts read it
   from the environment. Report only status codes, key name, scopes, expiry.
2. Every API call needs `Authorization: Bearer $SAIR_API_KEY` **and a browser
   `User-Agent`**. Without the UA, Cloudflare answers 403 error 1010, which
   looks like a revoked key and is not. `src/harness/submit.py:call` does both.
3. **Never submit a path the local verifier does not replay**, and never send
   a payload shape guessed ahead of the published schema. `submit.py` enforces
   both; do not bypass it.
4. **Never commit anything under `runs/`.** Sequences stay private during the
   competition. Before every commit run `git status --short` and confirm no
   `runs/` path is staged.
5. **Campaign code stays private until the 30 Nov 2026 deadline.**
   `src/search/engine.py`, `src/search/campaign.py`, `src/harness/submit.py`,
   `src/harness/launch_watch.py` and `tests/test_engine.py` are gitignored so
   the search method is not handed to the other teams. Edit them freely; they
   are never committed while the competition runs. Only public-safe changes
   (the verifier, docs, correctness fixes) are committed, with the subject
   **`SAIR`** exactly, no body, no co-author trailers. Signing is configured
   per repo; do not change git config.
6. Work solo. **No multi-agent workflows or agent fan-outs**: Amey forbids them
   for token cost. Heavy compute belongs in detached Python processes, not in
   the model.
7. Keep a run short when nothing has changed: check, log one line, stop.
8. Never create accounts, change account or team settings, or touch the API
   key. If authentication fails, log it and stop.
9. Append a dated entry to `runs/campaign_log.md` at the end of every run.

## Facts

| | |
| :--- | :--- |
| Repo | `C:\Users\archi\OneDrive\Desktop\Shreyas\SAIR-ANDREWS-CURTIS-CHALLENGE` |
| Competition id | `acc`, submission kind `acc-solutions` |
| Team | number **`ACC01-T00013`**, role owner; the API reports an empty team name, so match leaderboard rows on `teamNumber` |
| Problems | `ac` (target the ordered pair `(x, y)`) and `stable_ac` (target the empty presentation, at most 8 generators) |
| Scoring | shortest verified path, separate leaderboards per problem |
| Pool | 10,115 two-generator presentations, published at launch |
| Discovery opens | 11 Sep 2026, 16:00 UTC, which is 12:00 local (EDT, UTC-4) |
| Proof Track | opens 20 Sep 2026. Out of scope for this campaign |
| Deadline | 30 Nov 2026 |
| API key | name `Sept 2026`, expires 8 Mar 2027 |
| API docs | `https://docs.sair.foundation/llms.txt`, Markdown mirror under `/docs-md/` |
| Submit | `POST /api/public/v1/competitions/acc/submissions` with `{payload, meta}` |
| Eligibility | `GET /competitions/acc/me`, field `canSubmit` |
| Machine | 8 cores, 16 GB RAM, often only ~2.6 GB free |

Before launch the API answered `ACC_NOT_READY` ("freeze has not been
announced") on the leaderboard and submissions, and `submissionSpec` held only
`kind`. No ACC page existed on the docs site.

## Tools

Run everything from the repo root with `PYTHONIOENCODING=utf-8`.

| Command | What it does |
| :--- | :--- |
| `python -m src.harness.launch_watch runs/official` | Read-only. Saves the spec, eligibility, both leaderboards and any ACC docs page; prints one JSON status line with `ready`, `can_submit`, `schema_published`, `leaderboards` |
| `python -m src.search.campaign POOL --out DIR [--workers N --max-nodes N --caps none,18,24 --weights 0,0.5 --depth 3 --improve]` | Multi-core search. Appends improvements to `DIR/solutions.jsonl`, resumable |
| `python -m src.harness.submit DIR --problem ac` | Dry run: counts verified, unsent-or-shorter paths |
| `python -m src.harness.submit DIR --problem ac --live` | Sends them, after checking `canSubmit` and the schema. Ledger in `DIR/submitted.jsonl` |
| `python -m src.search.engine AK 3 1000000` | One presentation, for experiments |
| `python -m pytest tests -q` | Must pass before any code commit |

Engine facts: about 445 bytes and 19,000 nodes per second per process.
`workers x max_nodes x 445 B` must stay under ~2 GB.

**Never pass `max_tasks_per_child` to the process pool.** On this Windows
Python a retired worker is never replaced, and the run hangs with no error
after `workers x N` completions. The first benchmark stopped at exactly
6 x 25 = 150. A campaign whose `.out` log has not advanced while its process is
alive and no worker processes exist is this hang: stop it and restart, and it
resumes from `solutions.jsonl`.

**Start long searches detached so they outlive the run**, and record the PID:

```powershell
$repo = 'C:\Users\archi\OneDrive\Desktop\Shreyas\SAIR-ANDREWS-CURTIS-CHALLENGE'
$p = Start-Process python -ArgumentList '-u','-m','src.search.campaign','runs\pool\pool.jsonl','--out','runs\pool\main','--workers','6','--max-nodes','300000' -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput "$repo\runs\pool\main.out" -RedirectStandardError "$repo\runs\pool\main.err" -PassThru
$p.Id | Set-Content "$repo\runs\pool\main.pid"
```

Check whether one is running:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object CommandLine -like '*src.search.campaign*' | Select-Object ProcessId, CommandLine
```

## Every run

1. Read the last entries of `runs/campaign_log.md`.
2. `python -m src.harness.launch_watch runs/official` and read the status.
3. **Schema not published yet**: also check the ACC competition page and docs
   sitemap for news. If the benchmark below still has unsolved cases and it is
   before launch, you may spend the run improving the engine. Otherwise log
   and stop.
4. **Schema published, `build_payload` not yet written**: read
   `runs/official/spec_acc.json` and every file in `runs/official/docs/`.
   Implement `build_payload` in `src/harness/submit.py` exactly as documented,
   including any translation from our move JSON
   (`{"move": "invert"|"multiply"|"conjugate"|"stabilize"|"destabilize", ...}`,
   relator indices from 0, conjugating letter as a signed generator) to the
   official move encoding, and any batching limits. Add a test built from the
   documented example to `tests/test_engine.py`. Run pytest. These files are
   private (rule 5), so there is nothing to commit.
5. **Pool**: if `runs/pool/pool.jsonl` does not exist, find where the pool is
   published (spec, docs, API endpoints, the competition page) and convert it
   to JSONL lines `{"id": <official challenge identifier>, "relators": [[..],[..]]}`
   with generators as signed integers `x=1, y=2`. Record where it came from in
   the log.
6. **Search**: if no campaign process is running and presentations remain
   unsolved, start one detached (settings below). Escalate on each pass:
   - pass 1: `--max-nodes 300000`
   - pass 2, unsolved only: `--max-nodes 1000000 --caps none,18,24,32 --weights 0,0.5 --workers 2`
   - improve passes on solved: `--improve --depth 4`
7. **Submit** whenever a shorter verified path exists than what was sent:
   `submit.py --problem ac --live`, then `--problem stable_ac --live`. On HTTP
   422, read the error body, fix `build_payload`, test, retry once. On 403
   window errors, log and stop. On 429, `submit.py` waits `Retry-After`.
8. **Standing**: read our row for both problems from the status. If we are not
   first on a board, compare with the leader (solved count, total moves) and
   decide the next lever:
   - they solve presentations we do not: raise budgets, add caps and weights,
     then improve the engine (see backlog)
   - same coverage, fewer moves: run improve passes with deeper shortening,
     then improve shortening
9. Log: time, schema and eligibility state, pool size, solved `ac`/`stable_ac`,
   submitted, ranks on both boards, what you did, what the next run should do.

## Benchmark

`runs/bench/ms1190.jsonl`: AC-Solver's 1,190 Miller-Schupp presentations, from
the Gukov group paper *What makes math problems hard for reinforcement
learning* (arXiv 2408.15332). Their greedy search trivialised **533**, for
19,173 moves in total. Our first pass ran on 10 Sep 2026 into
`runs/bench/ms1190/` with `summary.json` comparing against theirs. Use it to
measure every engine change before trusting it on the pool.

## Engine backlog, most valuable first

1. **Bidirectional shortening**: meet in the middle between two states on a
   path, far beyond the current depth-3 detour radius.
2. **Beam and weighted variants** in the portfolio for presentations greedy
   cannot reach: moves often have to lengthen a relator before it cancels.
3. **Stable shortcuts**: stabilising can shorten a stable path; search with
   `Stabilize` and `Destabilize` for the hardest cases rather than always
   finishing through `(x, y)`.
4. **Canonical visited set**: key states up to relator order, inversion and
   cyclic rotation to cut revisits, keeping real states for path recovery.
5. A native C++ or Rust core once the Python design is settled.

## The cap walk (added 12 Sep 2026)

**A found path that is too long is a qualified lead, not a failure.** Our search
returns the true minimum inside cap = size + slack. When that is longer than the
record, the holder's shorter path simply leaves the box, and because we already know a
path exists nearby, walking the cap up one step at a time finds it. This does NOT work
from a cold start: on an unsolved challenge a wider cap just explodes the space and
finds nothing.

Measured conversion is roughly 65 percent, against 3.3 percent for a cold sweep, and
wins have come from 1 to 5 moves over the record.

- `runs/pool/nearmiss.py <list> <nodes> <outdir>` retries a list of
  `ac-NNNNN record ours k` lines at slack 1 to 8.
- `jit_tieband.py --walk` does the same inline, so a sweep converts its own leads.
- Build a list by scanning every `*.out` for lines where `ours` exceeds `record`.

**Push past a tie.** A tie pays 2^(1-k), an outright beat pays 1.0 and drops the
holder to zero, so the stop condition is `len(best) < rec`, not `<=`.

## Skip lists must record settled-ness, not attempts

A challenge is only settled when the EXACT search ran at that band's best slack
(records 18-22 slack 4, 23-30 slack 2, 31-60 slack 0). Attempts by the ball search or
at the wrong slack do not settle it. `runs/pool/skip_exact.txt` is built that way.

## Refresh the pool before every campaign of work

`runs/pool/pool.jsonl` goes stale fast and a stale pool wastes the whole run.
Records only improve, so a target beaten since the snapshot can never be won, and
`submit` correctly refuses the result. On 12 Sep an eight-hour-old pool sent a retry
pass after records that had all moved under it:

| challenge | ours | record then | record now |
|-----------|-----:|------------:|-----------:|
| ac-08051  |   40 |          40 |         39 |
| ac-02214  |   41 |          41 |         38 |
| ac-03562  |   45 |          45 |         42 |
| ac-00217  |   39 |          39 |         38 |

Run `python runs/pool/refresh_pool.py` first, and again between passes. It rebuilds
from `/competitions/acc/discoveries/snapshot?problem=...`, which returns all 10,115
challenges in ONE response with no pagination. `include=initialRelators` is rejected
with E_MALFORMED, so relators are carried over from the existing file; they never
change.

**A refresh also refills the productive band.** Other teams shortening long records
pushes challenges down into records 31-60, which went from 1,250 to 1,392 in one
night, while the unsolved pool fell from 2,849 to 2,756. Refreshing is not only
hygiene, it is where new work comes from.

## The cycle that works

Everything that scored on 12 Sep came from pre-qualified targets: challenges where we
ALREADY hold a verified path, so the cap walk knows a solution exists nearby and only
needs room to find a shorter route. Cold sweeps are finished as a technique here; one
managed 4 finds and 0 scoring in 83 attempts even with the walk folded in.

    python runs/pool/refresh_pool.py      # records move constantly; never skip this
    python runs/pool/build_targets.py     # writes t_near.txt and t_ties.txt
    python runs/pool/nearmiss.py runs/pool/t_near.txt 7000000 runs/pool/<out>
    python runs/pool/nearmiss.py runs/pool/t_ties.txt 7000000 runs/pool/<out>
    # then merge ledgers and submit, and start again

Two target kinds, both built by `build_targets.py`:

- **Near miss**: we have a path longer than the record. Sort closest first.
- **Live tie**: we hold the record jointly with k <= 4 AND the record is >= 20.

**Do not chase ties shared by many teams.** They are shared precisely because the
minimum is short and everyone found it: k=8 ties have a median record of 15, and a
pass over the highest-k ties scored 0 from 61 steps (ac-01635 returns 8 at slack 1 and
still 8 at slack 8, proving 8 is optimal). Sorted by record descending, the longest
records flip most: 8 of 21 on the top half against 1 of 21 on the bottom.

Measured yield on 12 Sep: 9 wins from 42 tie targets, 14 from the near-miss lists,
nearly all outright steals rather than ties.

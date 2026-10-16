# ACC campaign log

Newest entries at the bottom. Every scheduled run appends one.

## 2026-09-10 23:20 EDT, setup (interactive session)

- **State**: Discovery Track not open. `launch_watch` reports `schema_published: false`, `can_submit: false`, blocked "ACC freeze has not been announced.", both leaderboards 503 `ACC_NOT_READY`. Docs site has no ACC page.
- **Eligibility**: enrolled, team `ACC01-T00013`, role owner. Team name is empty on the API.
- **Built**: `src/search/engine.py`, `src/search/campaign.py`, `src/harness/submit.py`, `src/harness/launch_watch.py`, `tests/test_engine.py`. Problem id corrected to `stable_ac`.
- **Engine check**: AK(2) in 0.7 s, 18 `ac` moves and 20 `stable_ac` moves, both verified. AK(3) not reached at 200k nodes.
- **Benchmark**: started detached on `runs/bench/ms1190.jsonl`, 6 workers, 300k nodes, output `runs/bench/ms1190/`, pid in `runs/bench/ms1190.pid`. Compare `summary.json` with AC-Solver greedy's 533 solved.
- **Scheduled**: `acc-launch` once at 2026-09-11 12:07 EDT; `acc-steward` every 3 h at :17.
- **Next**: steward runs before launch should read the benchmark summary when it lands and, if coverage trails 533, spend the run on the engine backlog. The launch run wires up `build_payload`, the pool, the campaign and the first submissions.

## 2026-09-10 23:30 EDT, benchmark hang found and fixed (interactive session)

- **Symptom**: benchmark log frozen at 150/1190, process alive, zero worker processes, no stderr, no engine errors.
- **Cause**: `ProcessPoolExecutor(max_tasks_per_child=25)`. Each of the 6 workers retired after 25 tasks and this Windows Python never spawned replacements, so the pool deadlocked at exactly 6 x 25 = 150. The live campaign would have frozen the same way.
- **Fix**: removed `max_tasks_per_child` from `src/search/campaign.py`; runbook and memory now forbid it.
- **Action**: killed the hung run (pids 20732, 9912), restarted on the same output directory. It resumes past the 150 presentations already solved for both problems.
- **Also noted**: the unrelated `birdclef-experiment-loop` scheduled task points at a missing SKILL.md, so it cannot run and is not competing for CPU.

## 2026-09-11 17:52 EDT, live: first scoring submissions

- **Submitted and verified**: batch 165 (1 line, `sac-08491` tie) and batch 175 (20 lines, 10 challenges tied on both boards). Every line came back `ok`. Team name is now AMEY, `ACC01-T00013`.
- **What scores**: `runs/pool/tieband.py`, bidirectional BFS from the presentation and from the target at once, inside a total-relator-length cap. Exhaustive inside the cap, so it returns the true minimum: 10 of the 60 shortest held bests, all matching the record exactly (held 8 to 13).
- **What does not**: greedy plus local shortening. On the pool it solved 2 of 56 solved-by-others challenges, both longer than the held best, and 0 of 32 unsolved at 300k and 2M nodes, and 0 of 8 in the 101-300 band at 2M. Annealing dives solved 8 of 56 at 3.5x to 6x the held length. Cyclic-reduced priority, relator caps and 12-move search changed nothing. Meet-in-the-middle shortening gains 5-10%, still not enough.
- **Why**: 10,000 of the 10,115 challenges are random balanced presentations from a separate draw, not Miller-Schupp. The engine solves all 424 official training presentations with paths a median 35% shorter than the certified ones, and that strength does not transfer.
- **Next**: widen the bidirectional caps (slack 10, depth 16 running) and extend past the first 60 of the band. Each tie pays 2^(1-k); only 13 AC challenges under held 24 have a single holder, so the whole band is worth roughly 15-20 points.

## 2026-09-11 22:30 EDT, on the board at #9 (AC)

- **Submitted**: 165, 175, 183, 185, 188, 190. All verified, 99 lines total. AC rank 9 with 32 challenges held; Stable AC rank 10 with 31.
- **The method that scores** is `runs/pool/tieband.py`: bidirectional BFS from the presentation and from the target at once, inside a cap on total relator length, exhaustive inside the cap so it returns the true minimum and can match a record exactly.
- **The parameter ladder**, measured, where slack is added to the initial total relator length and depth bounds the path:
  - slack 6, depth 13: reaches held best <= 13. Seconds per challenge.
  - slack 8, depth 14: reaches held 14. 4 to 11 s per challenge.
  - slack 10, depth 15: reaches held 15. 14 to 40 s per challenge.
  - slack 10, depth 16, 4 workers: thrashes, no output in 7 minutes, had to be killed.
  Each extra held move costs roughly one more slack and one more depth, and the cost per challenge climbs steeply.
- **Dead ends measured tonight**: canonical-form search (0 of 12 unsolved, 5x slower per node than plain, identical coverage); annealing dives (3.5x to 6x the held length); meet-in-the-middle shortening (5 to 10 percent, never enough); 12-move search; cyclic-reduced priority; relator caps; greedy at 2M nodes on the 101-300 band (0 of 8).
- **Operational**: killed multiprocessing runs leave orphaned workers holding hundreds of MB each. Clear them by parent-is-gone before judging free memory, or the next run thrashes.
- **Board is volatile**: JDD took first from Dirac within the hour (2165 vs 1543), so held bests move and our ties can be displaced.
- **Next**: the written but unrun `runs/pool/matdist.py` gives an admissible lower bound from the exponent-sum matrix (inversion negates a row, multiplication adds or subtracts one, conjugation does nothing, target is the identity). Pruning on it should buy depth that widening cannot.

## 2026-09-11 22:45 EDT, rank 8 on both boards

- **Submissions**: 165, 175, 183, 185, 188, 190, 193, 198. All verified, 116 lines. AC rank 8 with 52 challenges held, Stable AC rank 8 with 50.
- **The ladder now reaches held 16.** Each rung costs roughly one more slack, one more depth, and several times the seconds per challenge:
  - slack 6, depth 13: held <= 13, seconds each
  - slack 8, depth 14: held 14, 4 to 11 s
  - slack 10, depth 15: held 15, 14 to 40 s
  - slack 12, depth 17: held 16, 51 to 85 s
  - running now: slack 14, depth 19 for held 19-20
  Use `--min-held` so a run does not redo ground a cheaper setting already covered; without it the second run wasted its whole budget re-solving the first run's wins.
- **The exponent-sum lower bound is not usable for pruning.** `runs/pool/matdist.py` builds it correctly (24,080 matrices, admissibility verified on 6,482 move checks, zero violations), but across the pool its median is 5 and its maximum 13, and on 0 of 6,610 solved challenges does it reach the held best. A bound of 5 prunes nothing in a depth-15 search. Do not revisit without a stronger invariant.
- **Submitting**: copy the previous run directory's `submitted.jsonl` into the new one before `python -m src.harness.submit runs/pool/NAME --live`, or the same ties are sent again and waste lines against the 40-batch daily limit.

## 2026-09-11 23:00 EDT, reachable band harvested

- **Standing**: AC rank 8, score 2.8516, 75 challenges held. Stable AC rank 7, score 2.5000, 72 held. Ten submissions, 146 verified lines, every line accepted.
- **The reachable band is now cornered**: of the 76 challenges whose record is 17 moves or shorter, we hold 75. Only one was newly available on the refresh.
- **Held 18 and above is out of reach on this machine.** Depth 17 cannot express an 18-move minimum, and raising depth to 19 balloons memory: slack 14 gave 0 results with workers at 2.3 GB, and even a tight slack 10 at depth 19 produced nothing while growing past 2 GB. One worker reached 4.2 GB before being killed.
- **The ongoing play is refresh and harvest, not a bigger search.** The reachable band refills only when another team shortens a record into it, and records move constantly: the leader changed twice tonight and Dirac fell from 2,536 to 1,543 within an hour. Refresh the snapshot, rebuild `runs/pool/pool.jsonl`, then run the tie band on any challenge newly at held <= 17.
- **Cost of a scoring line is low but so is its value**: our ties are shared with 2 to 7 teams, paying 2^(1-k) each, which is why 75 held challenges total under 3 points.

## 2026-09-12 01:10Z, rank 7 on both boards, score 2.85 -> 24.5 in one evening

- **Standing**: AC rank 7, 24.5273, 136 challenges held. Stable AC rank 7, 22.8398, 128 held. ~25 submissions, every line verified.
- **What changed everything: the cap, not the budget.** The bidirectional search is exhaustive inside a cap on total relator length. A tighter cap concentrates the same budget deeper, and a wider one wastes it. Measured on records 18-22 at a fixed 12M nodes/side: slack 12 scored 9 of 29, slack 8 scored 11, slack 4 scored 23 found / 18 scoring. Widening to 16 LOST challenges that slack 12 had found, including our first outright steal.
- **The slack ladder by record band**, all at 8-12M nodes/side:
  - records <= 17: the Python bidirectional already holds all 76
  - records 18-22: slack 4
  - records 23-30: slack 2
  - records 31-60: slack 0
  - records 61+: closed. Slack 0 exhausts the box in under 1M nodes (too small to contain a path); slack 6 burns 10.7M nodes without finding one (too big to search). Neither works.
- **The JIT core** (`runs/pool/jit_engine.py`, `runs/pool/jit_tieband.py`) is 15x faster than the Python engine, 0.7-1.4M nodes/s, and its moves were checked against the verified engine on 19,222 cases with zero mismatches. numba segfaults on interpreter teardown under this Python: write results as they are produced and end with os._exit(0).
- **Steals beat ties by a lot.** A tie pays 2^(1-k) and most of ours are shared 2-7 ways; an outright beat pays a full 1.0 and drops the previous holder to zero. The exhaustive search produces steals wherever a record was set heuristically and is not optimal, e.g. ac-04702 at 22 against a record of 24, ac-02359 at 27 against 31.
- **Submitting**: merge every run's ledger before each submission, `cat runs/pool/*/submitted.jsonl | sort -u > runs/pool/LEDGER.jsonl`, then copy it into the run directory. Copying one run's ledger over another's loses its history and resends challenges we already hold.

## 2026-09-12 01:35Z, the long-record band is where the points are

- **Standing at the 01:20Z snapshot**: AC rank 7, 26.5215, 138 held. Stable AC rank 7,
  24.8398, 130 held. Submission 258 added two single-holder steals (ac-08646 at 32
  against 33).
- **The gaps are much smaller than the early-evening reading suggested**, because the
  teams just above us are close together while the top four are far away:

  | rank | team | AC score | to pass |
  |-----:|:-----|---------:|--------:|
  | 5 | RyanP | 101.90 | +75.4 |
  | 6 | jr | 33.83 | **+7.3** |
  | 7 | AMEY | 26.52 | - |

  Rank 6 is roughly seven scoring lines away, not the fifty I estimated earlier.
- **Why records 31-60 are worth far more per line than the short bands.** Of the 1,250
  challenges there, **1,150 have a single holder**, so a line here is worth far more than in
  the short bands. Beating the holder pays a full 1.0 and drops them to zero; merely
  matching makes k=2 and pays 0.5, halving theirs. Our six finds in this band were
  four beats and two ties, so budget about 0.83 per scoring line. Confirmed against
  the board: two submitted steals moved AC by exactly +1.9942. In the short bands our ties were shared 2 to 7
  ways and paid 2^(1-k), which is why 75 held challenges were worth under 3 points. The
  measured hit rate in this band is 6 of 56 at slack 0, about 11 percent, and 1,184
  challenges are untried: roughly 130 points, enough for rank 5.
- **Failures here are node-limited, not cap-limited.** The repeated "10,795,847 nodes"
  is the per-side budget running out, not the box being exhausted, so the constraint is
  throughput. Throughput was bound by memory, at one search per machine.
- **Three changes made parallel search possible**:
  - `MAXLEN` in `jit_engine.py` cut from 64 to 44. Words never exceed the cap, and only
    conjugation can overshoot it, by 2; the pool's longest presentation totals 40.
    `solve_bidir` now refuses a cap the buffer cannot hold.
  - `jit_tieband.py` takes `--shard i --nshards n` and `--skip-file`, so several
    processes split one band without overlap or repeating attempts.
  - Budget 5M nodes/side and `--table-bits 23`, which puts a process at about 1.2 GB
    instead of 2.5 GB.
- **Watch commit charge, not free memory.** Three shards at 6M/side ran the machine to
  36.3 GB committed against a 37.0 GB limit with 1.5 GB available, which is where
  allocations start failing. `Get-Counter '\Memory\Available MBytes'` and
  `'\Memory\Committed Bytes'` are the honest readings; `FreePhysicalMemory` excludes
  reclaimable standby and reads far too low.
- **Records 61-120 are closed**, confirmed from both directions: slack 0 exhausts the
  box in under 1M nodes, slack 6 burns 10.7M without finding a path.

## 2026-09-12 02:10Z, rank 6 on AC

- **Standing**: AC rank 6, 31.9902, 145 held, having passed jr (30.30). Rank 5 (RyanP)
  is 90.87, so +58.9 away. Submissions 263 (15 lines, 8 steals) and 264 (2 ties).
- **The board deflates as well as inflates.** RyanP fell 101.90 to 90.87 and Dirac 641
  to 595 without us touching those challenges, because every tie we or anyone else
  joins halves the holders' share. Gaps must be re-read, never assumed.
- **The unsolved pool is closed to this method. Tested and rejected**, 2,849 challenges
  nobody has solved, about 190 attempted across three cap settings, zero finds:
  - slack 0: the box is exhausted in 368 to 900,000 nodes. Far too small to hold a path.
  - slack 4: exhausted in 31,000 to 259,000 nodes. Still too small.
  - slack 12: 7.6M nodes per failure, now node-limited, still nothing.
  There is no cap that is both large enough to contain a path and small enough to
  search. Do not revisit without a fundamentally different search.
- **The abelianisation filter is sound but empty.** A balanced presentation of the
  trivial group must have exponent-sum matrix determinant +/-1, and 0 of the 7,266
  solved challenges violate this, which confirms the test. But all 2,849 unsolved
  challenges already satisfy it, so the organisers pre-filtered the draw and the test
  eliminates nothing. Worth knowing, not worth running again.
- **What the record bands actually look like**, and why the long ones may be the prize:

  | records | challenges | single-holder | size median |
  |--------:|-----------:|--------------:|------------:|
  | 31-60   | 1,250 | 1,150 | 29 |
  | 61-120  | 2,119 | 2,084 | 29 |
  | 121-300 | 2,303 | 2,291 | 30 |
  | 301+    | 1,353 | 1,350 | 30 |

  The presentations are the same size in every band; only the record differs. Our
  search returns the minimum inside a cap and never looks at the record, so the find
  rate is a property of the presentation, not of the band. The record only decides
  whether a find scores. Against a record of 121 or more, essentially any find we make
  is an outright steal.
- **Two probes running on that idea**: records 121+ at slack 0, and records 61-120 at
  slack 2. The earlier "61-120 is closed" call was made from slack 0 and slack 6 only,
  and never tested the middle, which is where the ladder says the answer should sit.
- **Three processes is the machine's ceiling.** Commit charge sits at 36.0 of 38.0 GB
  with three searches at about 1.1 GB each; a fourth would thrash.

## 2026-09-12 02:30Z, the backward ball was being rebuilt thousands of times

- **Standing**: rank 6 on both boards. AC 32.4902 with 146 held, Stable AC 30.0547
  with 139 held. Rank 5 (RyanP) is +58.4 on AC and +58.0 on stable.
- **The bug was in the economics, not the code.** Identical node counts gave it away:
  7,226,201 appeared for four different challenges in one run and again in another,
  and 7,512,679 twice more. The backward half of the bidirectional search expands
  from the trivial pair under one constraint, that total relator length stays inside
  the cap. It never reads the presentation. So every challenge of a given size was
  rebuilding the identical set of states, burning most of a 5M-node budget on work
  already done thousands of times.
- **`runs/pool/ball_search.py` builds that ball once per cap and sweeps every
  challenge of that size against it.** Validated 8 of 8 against known minima
  (records 8 to 14, every one reproduced exactly). A ball of 4,000,000 states builds
  in 4 seconds, about 1M states/s, so a 14M ball costs roughly 12 seconds once
  instead of 22 seconds per challenge.
- **Minimality is preserved.** The ball stores each state's exact distance from the
  target, the forward search runs in layers of increasing depth, and it stops only
  once the forward depth reaches the best total found, so nothing shorter can remain.
  Every path is still replayed by our verifier and then the official one.
- **The long-record hypothesis was wrong and is now measured.** I reasoned that since
  presentation size is identical across bands (median 29 to 30), the find rate should
  be too, making records 121+ a field of guaranteed steals. It is not: records 121+ at
  slack 2 found 0 of 13, and records 79-120 found 1 of 12, at length 87 against a
  record of 79, so it did not even score. Record length is a proxy for difficulty, not
  an independent axis. The presentations are the same size but not the same hardness.
- **What slack 2 actually produces is a path of 78 to 87 moves**, so it can only score
  against records above about 88. That, not the band size, is the constraint.

## 2026-09-12 03:00Z, the ball search finds more and scores less

- **The amortised ball works exactly as intended and still does not help.** It builds
  once per cap (16M states in 20 to 38s), each challenge then costs 0.2 to 12s instead
  of 20s, and it raises the find rate sharply: records 61+ went from 0 of 13 under the
  old search to 3 of 4. But it has scored nothing, in 25 attempts on records 88+ and
  22 on records 31-60.
- **Why: find rate is the wrong metric, exactness is the right one.** A truncated ball
  reaches only so deep, so the forward search meets it wherever it can and returns an
  upper bound, not the minimum. The old alternating search expands whichever frontier
  is smaller, which keeps the two halves balanced and lands on the true minimum inside
  the cap. That exactness is the whole source of our steals. Measured side by side on
  records 31-60: old search 3.3 percent scoring, ball search 0 of 22.
- **Our paths are about 10 percent longer than the records, everywhere**, and the size
  of the gap does not depend on the band:

  | record | ours | over |
  |-------:|-----:|-----:|
  | 91 | 95 | 4% |
  | 93 | 106 | 14% |
  | 106 | 119 | 12% |
  | 131 | 142 | 8% |
  | 56 | 88 | 57% |

- **Widening the cap does not close that gap, it breaks the search.** Measured on
  ac-03055 (record 91): slack 2 gives 95, slack 4 gives nothing at all. The space
  inside the cap grows faster than any budget we can throw at it, so the wider cap
  loses the path instead of shortening it. This kills the obvious idea that more room
  buys a shorter route.
- **What remains untested is shortening.** Every path we produce is minimal inside a
  cap on TOTAL relator length, while `engine.shorten` hunts detours under a cap on
  EACH relator, so it can still cut a path our search called minimal. It is now wired
  into both searches behind `--shorten`. Many finds miss by only a few moves, for
  example 41 against a record of 35 and 53 against 47, and the shortener was measured
  at 5 to 10 percent earlier in the campaign.

## 2026-09-12 03:20Z, why the native stable search was not built

- The stable move spec is fully machine-readable:
  `runs/official/repo/competition/tools/verifier/data/stable_move_spec.json`, 257
  moves each carrying category, relator, other/conjugator, invert_other and its own
  inverse id. `max_rank` 8, extra generators g3 to g8, and `target_relators` is the
  EMPTY presentation. Filtering to relators 0-2 with conjugators x, y, g3 gives the
  33 moves a rank-3 search needs, so the build is tractable.
- **It was still the wrong thing to build.** AC and Stable AC are separate
  leaderboards. A rank-3 stable search moves only the stable board, leaving AC near
  50, while the branching factor goes from 14 to 33 exactly where the search is
  already budget-bound. Every ordinary AC path we find already yields a stable line
  as well, so the exact rank-2 search moves both boards at once. Reconsider only if
  the stable board alone becomes the goal.
- **Records 88+ closed**: 0 scoring in 24 attempts with shortening on. Redirected to
  records 61-87 at slack 0, which the exact search has never swept.

## 2026-09-12 03:35Z, the 10 percent gap is structural

Three independent attempts to close it, all measured, all failed:

1. **Widen the cap.** ac-03055, record 91: slack 2 returns 95, slack 4 returns nothing
   at all. The space inside the cap grows faster than any budget, so a wider cap loses
   the path instead of shortening it.
2. **Detour shortening at depth 3.** About 2 percent (106 to 104, 119 to 117).
3. **Detour shortening deeper.** Depth 4 buys one further move (104 to 103) for six
   times the time. The easy detours are gone after depth 3 and the returns collapse,
   so depth 5 will not reach 10 percent either.

**Conclusion.** Our search wins a challenge only when its true minimum happens to fit
inside a tight cap, which is the 3.3 percent of records 31-60 we have been harvesting.
It is not a rate that can be tuned upward, and the roughly 10 percent by which we
trail the record holders is a property of the method, not of its settings. Rank 5
(+58) needs a different class of solver.

**Remaining work that does pay**, from a skip list rebuilt on settled-ness rather than
on mere attempts (a challenge is only settled when the EXACT search ran at that band's
best slack, so slack-2 and ball-method attempts do not count):

| records | total | held | settled | only weak setting | never tried |
|--------:|------:|-----:|--------:|------------------:|------------:|
| 23-30   |   136 |   34 |  n/a (slack 2 is correct here, 30% scoring) | 81 | 21 |
| 31-60   | 1,250 |   16 |     628 |                33 |         589 |
| 61-87   | 1,101 |    0 |      20 |                28 |       1,053 |

Four searches are on those: two on 31-60 at slack 0, one on 61-87 at slack 0, one on
the 23-30 remnant at slack 2, all with shortening enabled.

## 2026-09-12 03:55Z, the near-miss retry, and a correction

**Correction to the entry above.** I concluded that widening the cap always breaks the
search. That is true only from a cold start, where ac-03055 found 95 at slack 2 and
nothing at slack 4. It is false on a challenge we have ALREADY solved: there we know a
path exists nearby, so walking the cap up a step at a time finds the shorter route the
record holder used. ac-00104 needed slack 5, far wider than anything the ladder had
been running.

**The method.** `runs/pool/nearmiss.py` takes challenges where our best path is longer
than the record and retries each at slack 1 through 8, stopping at the first result
that beats or matches. Early returns: 3 wins from the first 3 processed.

- ac-00104: 23 to 22 against a record of 22
- ac-00217: 41 to 39 against 39
- ac-00980: 46 to 44 against 44

Submission 267 accepted 3 lines.

**Why this is the best seam left.** A cold sweep of records 31-60 scores about 3.3
percent and costs ~20s a challenge. These targets are pre-qualified: we already hold a
verified path, we know exactly how many moves we need to save, and almost all of them
are single-holder. There are 76 such challenges, 27 within 4 moves of the record and
50 further out, all listed in `runs/pool/nearmiss.txt` and `nearmiss2.txt`.

**The general lesson**: a fixed slack is the wrong policy. Slack should be walked
upward per challenge until a path appears and then a little further to shorten it.
Every "found but too long" result in the whole campaign is a retry candidate, and
until now they were all being discarded.

## 2026-09-12 04:15Z, the cap walk earns outright steals

- **Submission 279: 8 lines, 6 steals**, every one single-holder, so each takes a full
  point and drops the previous holder to zero:
  - ac-05561: 35 -> 27 against a record of 33
  - ac-05393: 37 -> 34 against 36
  - ac-07215: 45 -> 42 against 43
  Earlier batches 267, 269 and 273 landed 15 more lines as ties.
- **Pushing past a tie is what produced them.** The stop condition was
  `len(best) <= rec`, which halted the walk the moment it matched. Changed to
  `len(best) < rec`, the walk keeps widening and lands under the record instead of on
  it. A tie pays 2^(1-k) and is usually split; a beat pays 1.0 and zeroes the holder.
- **Standing**: AC rank 6, 34.14 with 151 held; Stable rank 6, 30.19 with 142.
  Session start was AC rank 7 at 24.5 with 136.
- **The cold sweep is finished as a technique here**: `walkF` managed 4 finds and 0
  scoring in 83 attempts even with the walk folded in, while the retry took 7 wins
  from about 30 challenges. Both workers are now on retry targets. The sweep's only
  remaining value is as a generator of leads for the retry.

## 2026-09-12 04:40Z, a tie shared many ways is not an opportunity

- **Standing**: AC rank 6, 40.6753 with 160 held; Stable rank 6, 36.9688 with 151.
  Session start was AC 24.5273 with 136. Gap to rank 5 down from +58 to +48.1.
  Submissions 279, 282, 283 and 285 were all outright steals.
- **Of our 161 held AC challenges only 20 are outright; 135 are shared ties.** On
  paper, upgrading all of them to beats is worth 117 points, which is more than the
  gap to rank 5. I ran it highest-holder-count first, reasoning that a tie split eight
  ways pays 2^-7 and so has the most to gain.
- **That was backwards, and the pass scored 0 from 61 steps.** ac-01635 returns 8 at
  slack 1 and still 8 at slack 8: the search proves 8 is the true minimum, so there is
  nothing to find. The reason is visible in the structure:

  | holders | count | median record |
  |--------:|------:|--------------:|
  |      10 |     1 |             8 |
  |       8 |    48 |            15 |
  |       3 |    19 |            26 |
  |       2 |    20 |    26, up to 48 |

  **A challenge is shared by many teams precisely because its minimum is short and
  everybody found it.** High k is evidence of optimality already reached, not of
  opportunity. The beatable ties are the low-k ones at long records, where the
  incumbent may still be suboptimal.
- **Re-targeted to k<=4 with record>=20**: 42 challenges, worth about 28 points, with
  93 skipped as provably optimal. Both workers are on those.

## 2026-09-12 07:25Z, our score rose and our rank fell

- **AC 46.6509 with 162 held, rank 7. Stable 43.6953 with 153, rank 7.** The score is
  up from 42.91 but the rank is down from 6, because the field changed underneath us:
  a new team ACC01-T00032 entered straight at rank 4 with 293.52, and the board
  re-scored hard. NavierStoked went 3714 to 4641, JDD 1945 to 1313, Dirac 587 to 232.
- **Read the gap, never the rank.** Rank 6 (RyanP, 78.65) is +32.0 away, closer in
  absolute terms than an hour ago. Rank 5 is now Dirac at 232.25, so +185.6, where it
  had been about +46. Our own progress and our standing move independently.
- **Cycle two produced submissions 316 and 344**: 7 steals and 10 ties, including some
  large margins, ac-06960 45 to 33, ac-04308 33 to 23, ac-01734 48 to 38, ac-06321 41
  to 31 against a record of 35.
- **The cycle is now mechanical**: refresh_pool, build_targets, two cap-walk workers
  over t_near.txt and t_ties.txt, merge ledgers, submit, repeat. Eighteen submissions
  tonight, every line accepted by the official verifier.
- **Session arc**: AC 24.5273 with 136 held at the start, 46.6509 with 162 now, so the
  score has nearly doubled while the competition got materially stronger.

## 2026-09-12 19:45Z, the field converged and ties became worthless

- **Our score fell 46.65 to 19.61 while our holdings barely moved**, 162 to 154. We did
  not regress; the value of what we hold collapsed. Of the 177 challenges we have ever
  submitted, 156 are still at the record and only 21 were beaten outright by someone
  else.
- **The cause is convergence.** Our holds are now shared with up to SIXTEEN teams:

  | holders | our challenges |
  |--------:|---------------:|
  |       1 |              8 |
  |    9-13 |             64 |
  |   14-16 |              6 |

  At k=12 a tie pays 2^-11, about 0.0005. All 156 holds together are worth 22.63
  points. Earlier in the campaign the same holdings were worth more than double that.
- **The whole board re-scored, not just us.** Dirac went 232 to 4135 and took first,
  NavierStoked fell 4641 to 1044, JDD 1313 to 143, RyanP 78 to 13.5.
- **The decisive comparison**: ACC01-T00032 sits at rank 5 with 45.08 points from only
  62 challenges, a quarter of our holdings and more than double our score. Their holds
  must be overwhelmingly outright. **Quantity of ties is worthless; only outright beats
  pay.**
- **Retargeted accordingly.** `build_targets.py` now keeps a tie only when it could
  plausibly become a beat, k of 2 or 3 with a record of 24 or more, which cut the tie
  list from 39 to 28. Both workers are on the near-miss list, where a win is a beat by
  construction, and the generator keeps feeding it.
- Rank 6 on both boards. Rank 5 is +25.5 on ac, the smallest absolute gap of the
  campaign, and it needs roughly 26 outright steals rather than any number of ties.

## 2026-09-12 20:10Z, bulk solving from one ball does not work

- **Measured**: one ball at cap 40 with 22,000,000 states, built in 19 seconds,
  contained exactly **2 of the 10,115 challenges**, and both only matched their record.
- **Why, and it is the same lever as everything else here.** At a tight cap most moves
  break the cap and are rejected, so branching is low and the ball reaches deep. At cap
  40 nearly every move is legal, branching explodes, and 22M states buys only about 8
  to 10 moves of depth, while the pool sits 20 to 130 moves from the trivial pair. **No
  single cap is both wide enough to hold every challenge and tight enough to reach
  it.** That is why per-challenge caps of size+2 work and a global cap cannot.
- The idea was worth testing because the ball never depends on the challenge, so a hit
  is an exact minimum for one hash lookup. It just does not reach.
- **On top 3.** It needs +1025 points. The leaders get there by holding thousands of
  challenges OUTRIGHT: Dirac has 4,443 holds for 4,135 points and gained roughly 325
  outright holds per hour today. We hold 8 outright, and our best measured rate all
  campaign is about 3 per hour. That is a hundredfold gap in solver capability, not in
  effort or uptime, and no amount of grinding this method closes it. Top 5 at +25.5 is
  the realistic target; top 3 needs the RL-guided class of solver the AC-Solver paper
  describes, which is a research project rather than a tuning job.

## 2026-09-12 20:30Z, repo sync, and the Proof Track was already open

- **Our repo is clean and in sync with origin.** The official clone at
  `runs/official/repo` was two commits behind; pulled to a0fd6e6. The changes are
  documentation only, with **no move-spec and no verifier change**, so every path
  submitted so far remains valid.
- **The Proof Track is live and we missed it.** The rules used to say it opens "before
  September 20"; they now read "launched September 11, 2026", the same day Discovery
  opened. New requirements: cite any prior work used, and any GitHub link must carry a
  full commit hash.
- **This is a second scoring surface we have not touched**, and it wants exactly what
  this campaign has produced: measured partial results. The cap ladder by band, why a
  wider cap breaks a cold search but works on a challenge already solved, why the ball
  search raises find rate yet scores nothing, why one global ball cannot bulk-solve the
  pool, and why a tie split many ways is proof the minimum is already found. All of it
  is measured, reproducible, and currently sitting in a gitignored log.
- **Where the remaining Discovery volume is**, from the 19:45Z snapshot:

  | record | challenges | single-holder |
  |-------:|-----------:|--------------:|
  |   <=60 |      2,282 |         1,801 |
  | 61-120 |      2,616 |         2,574 |
  | 121-300|      1,592 |         1,588 |
  |301-1000|        599 |           599 |
  |  >1000 |        296 |           296 |

  Every challenge above 300 is single-holder, and their presentations are the usual
  size, median 30. Against a record that long, ANY path we find is an outright steal,
  so the find rate is the only thing that matters there. Two hunters are on those 895.

## 2026-09-12 21:15Z, the hard length cap was the defect

- **Every search in this campaign until now rejected any state whose total relator
  length exceeded size + slack.** That cap is why we lose. A good Andrews-Curtis path
  characteristically goes UPHILL, lengthening the relators before they collapse, and a
  hard cap forbids exactly that, so the search is forced the long way round. It is
  visible in every measurement: we return 70 to 140 moves where the record is 30 to 50.
  Widening the cap does not fix it, because a wider hard box explodes combinatorially
  and then finds nothing at all, which is what killed slack 4 on ac-03055 and slack 6
  and 10 on records 301+.
- **`runs/pool/bestfirst.py` makes length a PRIORITY instead of a wall.** Bidirectional
  best-first on a bucket queue keyed by total length, no length ceiling, with only the
  compiled word buffer as a hard bound. Uphill states stay reachable and are simply
  explored last.
- **Validated 10 of 10 on known challenges, and the cost collapsed:**

  | | exact search | best-first |
  |---|---:|---:|
  | nodes to find a path | millions | **176 to 4,710** |
  | seconds | 5 to 25 | **0.4 to 0.6** |

  About a thousandfold cheaper to find a path at all, at roughly 1.14M nodes/s.
- **The paths are not minimal**, which is the trade: record 15 gave 32, record 14 gave
  129. So it cannot beat a tight record directly. What it changes is which targets are
  reachable at all.
- **Unsolved pool: still closed, but for a new reason.** 0 of 34, and now exhausting the
  full 8M-node budget in 7 seconds rather than dying in hundreds of nodes. They are
  budget-limited, not structurally blocked, but they are about a thousand times harder
  than the knowns, so more budget will not bridge that.
- **The target this unlocks is long records.** Best-first makes long paths cheaply and a
  long path beats a long record. Records 121-300 hold 1,588 single-holder challenges and
  301+ holds 895 more, all previously unreachable because a capped search cannot express
  a path that length. Both bands are running now.

## 2026-09-12 21:45Z, the depth weight, and the campaign's real result

Two defects, found in sequence, and the second one is the big one.

**1. Length was a wall.** Every search capped total relator length at size+slack.
Good AC paths go UPHILL before collapsing, so the cap forced the long way round.
`bestfirst.py` makes length order a bucket queue instead of gating admission.

**2. The priority charged nothing for moves spent.** With length alone as the
priority the search wandered: it returned 1,912 moves for a challenge whose record
is 121, and 3,742 against a record of 301. Iterated shortening cut those to 396 and
963 and then plateaued, still three times over.

Charging for depth as well, priority = total length + dw * moves spent, fixed it.
Measured on the same ten known challenges, same budget:

| record | dw=0 | dw=1 | dw=4 |
|-------:|-----:|-----:|-----:|
|     15 |   32 |   16 | **15** |
|     15 |  140 |   17 | **15** |
|     14 |  129 |   15 | **14** |
|     10 |   13 |   11 | **10** |
|     14 |   75 |   17 | **14** |
|     11 |   21 |   16 | **11** |
|     13 |   49 |   15 | **13** |
|      8 |   10 |   10 |  **8** |

**At dw=4, eight of ten match the record exactly and the other two miss by one, in
0.3 seconds and 1,118 to 80,046 nodes.** The old exact search needed 5 to 25 seconds
and millions of nodes to do worse. Uphill steps stay legal; they are simply no longer
free to accumulate.

This is the result the campaign was missing. Every earlier negative in this log,
the unsolved pool, records 121+, records 301+, the bulk ball, was measured with a
search that had a wall where it needed a gradient.

Running now: records 20-60 at dw=6 with shortening, and a dw=12 tuning check.

## 2026-09-12 21:05Z, the solver boundary, and what it settles

The new best-first solver was re-run against every band, so the campaign's earlier
negatives are now re-measured with a search that works rather than one with a wall.

| records | attempted | scoring | holders on the wins |
|--------:|----------:|--------:|:--------------------|
|    8-16 |        10 |  **10** | (already ours)      |
|   17-26 |        22 |       4 | k = 6, 6, 9, 13     |
|   27-40 |        21 |       0 |                     |
|   20-60 |        36 |       2 | k = 6, 8            |
| 121-300 |        35 |       0 | dw 0 overshoots 3x  |
|    301+ |        17 |       0 |                     |
|unsolved |        28 |       0 |                     |

**The solver's competence ends at about record 18, and everything inside that boundary
is already shared six to thirteen ways.** The four wins at records 17-26 are worth
about 0.07 points combined, because 2^(1-13) is 0.0002.

**That is the whole finding: this solver matches optimal records exactly where the
field has already converged, and cannot reach anywhere the field has not.** The two
facts are the same fact. A record is short and heavily shared precisely because it is
easy to find optimally; a record is long and single-held precisely because nobody,
including us, can reach it.

**The depth weight has no setting that helps.** High dw gives exact minima but bounds
reachable depth (a 200-move path costs 2400 in priority): 0 of 35 on records 121-300.
Low dw reaches those challenges but wanders: 1,912 moves against a record of 121,
shortening to 396 and then plateauing. dw 2 and dw 4 get neither.

**Standing**: AC rank 7, 19.8964, 156 held. Two new teams have entered above us in the
last hours, ACC01-T00032 at 45.08 and ACC01-T00020 at 26.80. Rank 6 is +6.9, rank 3 is
+1024.5.

**On top 3, honestly.** It needs +1024. Dirac holds 4,442 challenges outright; we hold
8 outright and 148 shared. Nothing measured tonight closes a gap of that shape, and
the bands where outright holds could still exist are exactly the bands no search we
have can reach. It would take the RL-guided solver class from arXiv 2408.15332, which
is a research build, not a parameter.

## 2026-09-13, the learned heuristic: built, measured, and honest about it

**What was built.** `runs/pool/learn_heuristic.py` fits a distance-to-trivial
estimate on states drawn from paths we already hold, where the true distance is
known exactly (moves remaining). `runs/pool/astar.py` runs weighted A* on it,
priority = moves spent + W * predicted moves remaining. This is the mechanism
behind a learned search policy without the PPO loop, which needs a GPU we do not
have.

**A methodological error worth recording.** The first fit trained on every path
we had ever produced, including our own 963 and 1,912 move wanderings, and came
out WORSE than using total length alone: mean error 42.1 moves against 38.1.
Labelling a state as 963 from trivial when it is 301 away teaches our own
inefficiency rather than the geometry. Restricting training to paths at or below
the current record fixed it:

| estimator | mean error | median |
|---|---:|---:|
| total length alone | 5.6 | 4.0 |
| learned, record-quality paths only | **3.0** | **1.9** |

Learned weights are interpretable: relator imbalance +5.6 and max relator length
+4.2 raise the estimate, exponent-sum mass -7.0 lowers it.

**A bug the verifier caught, and why that matters.** The first A* accepted any two
distinct single generators as the goal, so it stopped at (y, x) and (x^-1, y).
The target is the ORDERED pair (x, y). It reported paths SHORTER than known
optimal records, which is the tell, and all ten failed verification. A wrong path
can waste a run; it cannot reach the leaderboard, because every path is replayed
by our verifier and then the official one before submission.

**The result, fixed and measured.**

| solver | exact matches on 10 knowns | nodes |
|---|---:|---:|
| best-first, length + 12*depth | **10/10** | 2,028 to 2,456,933 |
| A* with learned h, W=1 | 3/10 | **319 to 101,023** |
| A* with learned h, W=3 | 1/10 | 899 to 8,835 |

**The learned heuristic buys about twenty times fewer nodes and loses accuracy.**
It does not beat a hand-tuned priority on path quality. A least-squares fit
overestimates on some states, which removes A*'s optimality guarantee; lowering
the weight trades nodes back for exactness. Being faster does not help here,
because the binding constraint is never speed on the reachable band, it is reach
on the unreachable one.

## 2026-09-13, the stratification is two-sided, and it is the campaign's result

Targeting was sharpened twice and the answer did not change.

- **Searches were re-deriving our own holdings.** The 12M-node probe reported a win on
  ac-09058, which is already in the ledger. True yield of that run: 0 new from 17.
  `bestfirst.py` now takes `--skip-held` and `--max-k`.
- **Aimed at what is actually worth points**, unheld challenges with k <= 2 at records
  19-30, where a match pays 0.25 to 0.50: **0 scoring from 16**.

Putting both sides together:

| reachable | holders | a match pays | measured |
|---|---|---|---|
| record <= 18 | 6 to 13 | ~0.008 | all but 1 already held |
| record 19, k=6 | 6 | 0.008 | reached |
| record 19-30, k <= 2 | 1 to 2 | 0.25 to 0.50 | **0 of 16** |

**What we can reach is worthless and what is valuable we cannot reach.** These are the
same fact seen from two sides: a record stays single-held because it is hard, and
becomes widely shared because it is easy. The scoring rule 2^(1-k) then guarantees
that the accessible records pay almost nothing.

This is why the score does not move, and it is a sharper statement than "our solver is
too weak". The pool is stratified so that solver competence and point value are
anti-correlated, and no amount of targeting inside a fixed competence boundary escapes
it. Value distribution in records 19-30 alone: 73 unheld at k=1 worth 0.5 each, 45 at
k=2 worth 0.25, about 48 points, all of it behind the boundary.

## 2026-09-13, why no constant-factor engineering win is worth building

The competence boundary sits near record 18 and is node-bound, and nodes are
memory-bound, so the obvious lever is to store states more compactly. Letters are
{+-1, +-2}, two bits each, stored today in a byte: packing gives 103 bytes per state
down to 37, a 2.8x gain.

Priced before building, using the measured cost of solving at each record:

| record | states needed |
|-------:|--------------:|
|      8 |         2,028 |
|     14 |       172,372 |
|     16 |     2,456,933 |
|     19 |    12,812,195 |

That is about **1.7x more states per extra record**, so a 2.8x budget buys roughly
**2.2 more records of reach**, from 18 to about 21.

What that opens, counting only unheld challenges with k <= 2, which are the ones worth
0.25 to 0.50 each:

| band | challenges | value |
|---|---:|---:|
| records 19-21 | 2 | **0.8 pts** |
| records 19-23 | 7 | 2.5 pts |
| records 19-25 | 19 | 7.8 pts |

**A hot-loop rewrite buys under one point.** The unheld low-k value is concentrated at
records 26-30, beyond anything a constant-factor memory win can reach, because reach
grows logarithmically in budget while the value sits exponentially further out. Do not
build the packed representation, and do not expect any similar constant-factor
optimisation to matter: the gap is 1,265 points and the mechanism yields fractions.

**Also closed this cycle**: stable-board-only opportunities, 0 of 201. Every path we
hold that would beat a stable record while missing its ac record has already been
submitted by the harness, which evaluates both boards independently.

## 2026-09-13, A* reaches the valuable band, and the wall reappears one level out

**The one real advance.** `astar.py`, the learned heuristic driving weighted A*, reaches
challenges the capped and best-first searches cannot:

| solver | unheld, k <= 2, records 19-60 |
|---|---|
| best-first, length + 12*depth | 0 found of 23 |
| **A\*, learned h, weight 3** | **34 found of 222** |

Every find there is a k=1 or k=2 challenge, worth 0.25 to 0.50 rather than the 0.008
the reachable short records pay. This partially breaks the anti-correlation recorded
above, and it came from correcting a judgement: A* had been dismissed for producing
worse paths than best-first (3/10 exact against 10/10), which was true and irrelevant.
On this band the binding constraint is reach, not quality, and A* is about twenty times
cheaper per node, which is exactly what buys reach. The solvers had been compared on
the wrong axis.

**Two design errors found and fixed.**
- The cap walk cannot convert an A* find. It re-runs the capped exact search at
  increasing slack, and those challenges are reachable only because that search cannot
  reach them at any slack. 62 steps, 0 wins, architecturally impossible.
- Searches were re-deriving records already in the ledger and reporting them as wins.
  `--skip-held` and `--max-k` now target unheld low-k challenges only.

**And the wall reappears.** Lowering the A* weight to convert reach into quality fails
the same way the depth weight did:

| weight | found | scoring |
|---:|---:|---:|
| 3 | 34 of 222 | 1 |
| 1 | 4 of 21 | 1, the same challenge |
| 0.5 | 0 of 19 | 0 |

Weight 0.5 is nearly admissible and loses reach entirely; weight 3 reaches and
overshoots. There is no setting that both arrives and arrives short, which is the same
trade seen at every level of this campaign.

**Standing**: AC rank 10, 17.0870, 156 held. Rank 9 is +19.3, rank 3 is +3,319.

## 2026-09-13, IDA* removes the memory wall, and the band still does not open

**Why it was worth building.** Every other solver stores every state, so the node
budget is a memory budget: 12M states is about 1.3 GB and buys roughly record 18.
`runs/pool/idastar.py` searches depth-first under an f = g + h bound and keeps only
the current path, so memory is O(depth). Budget stopped being capped by RAM.

**It validates and it is fast**: 8 of 8 known optima reproduced and verified, using
1,766 to 368,825 nodes at 0.0 to 0.5 s, roughly ten times fewer nodes than best-first
needed for the same challenges. Paths run 0 to 6 moves over optimal, the usual price
of an inadmissible heuristic at weight 1.

**A bug worth recording.** The first version reported failures after 83,000 to 700,000
nodes against a 300,000,000 budget. The transposition filter was the cause: when every
child of a node is filtered, the next bound is never raised, so the iteration concludes
the space is exhausted and stops. A filter must never be able to suppress the bound
update. The table is now optional (`--table-bits 0`) and the exact ancestor cycle check
is sufficient on its own.

**The measurement, with the bug fixed**: unheld k <= 2 at records 19-30, weight 1,
200,000,000 node budget, **0 found of 17**. Several challenges consumed the entire
budget, 200M nodes and 206 seconds each, and returned nothing.

**Conclusion.** The memory wall was real and is now gone; the band still does not open,
because at records 19-30 the space is too large for 200M nodes even with a learned
heuristic. That is sixteen times what any stored search on this machine could hold.
The constraint was never only memory, and removing it changed the failure mode without
changing the outcome.

**Where that leaves the ranking.** A* at weight 3 remains the only solver that reaches
this band at all, at 15 percent find and about 0.5 percent scoring. Nothing measured
tonight scales to the 3,319 points that separate us from rank 3.

## 2026-09-16, five architectures, one conclusion

Three days on, the board has moved and we have not: rank 12, 3.1617, 146 held, every
one shared and none outright. Our score fell from 4.48 with no activity, purely to
dilution. A new team, AC-Solver =D, entered at rank 4 with 412 points, which is the
name of the RL solver in arXiv 2408.15332.

**The refreshed pool did open value**: 1,012 unheld challenges at k <= 2 and records
21-45, worth about 388 points, against +591 to rank 3. For the first time the
opportunity and the gap are the same order of magnitude.

**Measured against that band, every architecture we have:**

| architecture | result |
|---|---|
| capped bidirectional | 0 |
| best-first with depth weight | 0 of 23 |
| weighted A* on the learned heuristic | reaches 17-27%, **0 scoring** |
| IDA*, memory-free, 200M nodes | 0 of 17 |
| decision-mode IDA*, bound at the record | 0 of 8 |

A* is the only one that reaches at all, and its paths land 5 to 18 moves over. Nothing
converts them: not shortening, not the cap walk, not a lower weight, not a deeper
budget.

**Decision mode was the right question and still did not pay.** Starting the bound at
the record spends the whole budget on the only length that scores instead of
optimising through lengths that cannot. Seven of eight consumed 150M nodes without
deciding. The eighth, ac-07351, **exhausted its space at 75.6M nodes**, which proves no
Andrews-Curtis path of length at most 24 exists for that presentation within word cap
42. That is a real if small mathematical result and is now section 6b of the Proof
Track submission.

**Conclusion for the Discovery Track.** The ceiling on this hardware is reached. Five
architectures, a learned heuristic, every cap and weight policy, bulk precomputation
and two pipeline designs all fail on the band that pays, and the failure mode is
consistent: we reach what is worthless and cannot reach what is valuable. Closing that
needs a trained policy on different hardware.

## 2026-09-26, the walk lands on records instead of under them

Nine days without a run. The pool was 9 days stale, so the first act was
`refresh_pool.py`: 10,115 challenges, snapshot 01:30Z, and it changed the shape of
every target list.

**Standing.** Before: ac rank 22, 0.0357, 144 held; stable_ac rank 22, 0.0449, 128
held. After: **ac rank 22, 0.0388, 148 held; stable_ac rank 22, 0.0464, 131 held.**
Submissions 2319, 2320 and 2321, 7 lines, every line `ok` from the official
verifier. Rank unchanged on both boards. Leaders AC-Solver =D 2086.92 and
冰冻野鸡大学 2024.72; rank 3 (Catsitter) is 519.39, so +519.4 to pass.

**Every one of our 148 holds is a joint hold, k between 8 and 41, and none is
outright.** All 148 together are worth 0.0388 points. One outright beat is worth
1.0. That ratio, not compute, is the campaign.

### Leads had to be attributed to a solver before spending anything

`build_targets.py` scrapes "found but too long" lines out of every `*.out`, which
mixes solvers that the cap walk can convert with solvers it cannot. Attributed by
each log's own header:

| origin of the lead | leads | convertible by the walk |
|---|---:|---|
| exact capped bidirectional | 78 | yes |
| ball search | 52 | yes, same cap |
| the cap walk's own earlier output | 2 | yes |
| best-first / IDA* | 4 | no |
| A* on the learned heuristic | 105 | **no**, architecturally |

The A* leads are the largest group and they are worthless to the walk: those
challenges are reachable only because the exact search cannot reach them at any
slack, which the log already measured at 62 steps and 0 wins. That left **124
convertible leads**, written to `runs/pool/t_exact.txt`, of which **39 are within 5
moves of the record** and the rest need 6 or more moves saved, which the walk has
never done.

### Slacks 4 to 8 of the walk were measuring nothing

The first pass ran `nearmiss.py` at 5,000,000 nodes/side over slacks 1 to 8. Its
failures carry the signature the log identified in the cold sweep: **identical node
counts across different challenges.**

    ac-06321 slack 4 -> none (7,226,201 nodes)   ac-00637 slack 4 -> none (7,226,201 nodes)
    ac-06321 slack 5 -> none (7,306,923 nodes)   ac-00637 slack 5 -> none (7,306,923 nodes)
    ac-06321 slack 6 -> none (7,452,439 nodes)   ac-00637 slack 6 -> none (7,452,439 nodes)

Across the two shards, 3 different challenges returned 7,795,847 at slack 8 and 3
more returned 7,775,585 at slack 7. A count that depends only on presentation size
and slack is the presentation-independent backward ball: at slack 4 and above the
whole budget goes on rebuilding it and the forward half never moves. **The proof
that these are budget failures and not absences is that the boxes nest** —
ac-06321 returns 36 at slack 3 and "none" at slack 4, and the slack-3 box is a
subset of the slack-4 box.

So slacks 5 to 8 cost about 140 s per challenge and carry no information. Both
shards were stopped and the budget reallocated: **slacks 1 to 4 at 12,000,000
nodes/side**, which does complete (ac-09409 finished slack 2 on 18.3M nodes). Two
new arguments were added rather than editing constants: `nearmiss.py` takes the top
slack as `argv[5]`, and `jit_engine.MAXLEN` reads `ACC_MAXLEN`.

### The walk now arrives exactly on the record and not under it

39 closest leads, slacks 1-4, 12M nodes/side:

| challenge | our old path | walk result | record | outcome |
|---|---:|---:|---:|---|
| ac-03611 | 36 | 34 | 34 | tie, k 9 |
| ac-05751 | 34 | 31 | 31 | tie, k 10 |
| ac-08702 | 27 | 26 | 26 | tie, k 13 |
| ac-05653 | 31 | 29 | 28 | no score |
| ac-05726 | 40 | 38 | 35 | no score |

**3 ties, 2 improvements, 0 beats from 39 pre-qualified leads.** In April the same
method took outright steals off these lists (35 -> 27 against 33). It no longer
does, and the reason is visible in the failures: ac-01443 returns 26 at slack 3 and
26 at slack 4 against a record of 24; ac-07186 returns 26 at slack 2 and 3 against
a record of 23. Our search returns the true minimum inside its cap, so those
records are held by paths that **leave the box at cap = size + 4**. Earlier in the
campaign records in this band were heuristic and beatable; the field has since
converged onto paths our cap cannot express.

`walk` stopping at `len(best) < rec` never fires now, so the walk exhausts its
slacks and reports the record itself. That is why today's yield is ties.

### Cold sweeps, re-measured on the refreshed bands

All with the exact search, the band's correct slack, `--walk --shorten`, and
`skip_all.txt` (settled plus held):

| band | slack | attempted | found | scoring |
|---|---:|---:|---:|---:|
| records 23-30, open remnant | 2 | 94 | 2 | 1 tie (k 15) |
| records 31-45, open | 0 | 157 | 4 | **0** |
| records 46-60, open | 0 | 145 | 2 | **0** |

Records 23-30 scored 30 percent on 12 Sep; it scores 1 percent now, on the part of
the band that is left. **Records 46-60 had never been swept** (5 of 1,942 settled,
because every earlier sweep sorted ascending and its `--limit` ran out inside
31-45); 1,937 challenges were open there and 721 are single-holder, so it was the
largest untried volume in the pool. It measures the same as 31-45: the find rate
survives, the scoring rate is zero, because our path lands over the record.

### The long-record tail: a new seam, opened and closed

The one target class no solver in this campaign had ever touched. Records above
1,000 are almost certainly heuristic wanderings, not minima, and best-first at
depth-weight 0 is a wandering solver too: on records of 301 it has produced 799 and
963 after one shortening pass. Against a record of 2,116 a 900-move path is an
outright point. The earlier `bf301` run had stopped after 5 challenges at records
301-302, so nothing above 302 had been attempted; ac-01669 (record 2,116) and the
nine other records above 2,000 had never been given to any solver.

| probe | challenges | nodes/side | found |
|---|---:|---:|---:|
| records 501-2,116, dw 0, shorten | 109 | 4,000,000 | **0** |
| records 1,000-2,116, dw 0, shorten | 23 | 16,000,000 | **0** |

**Every one of the 132 failures exhausted its full budget**, including 32,000,000
nodes on each of the ten records above 2,000. The failure is budget-limited rather
than structural, and quadrupling the budget changed nothing, so the seam is closed
at this hardware. Iterated shortening cannot help either: `itcut` shows pass 1 doing
all the work (1,912 -> 415) and pass 3 gaining nothing.

### Our own joint holds cannot be walked into beats

148 holds are all at the record, which makes them the most pre-qualified list that
exists: a path is known, its length is known, and one move less pays 1.0. The 25
holds at record >= 20 not already walked at the current record were walked at slacks
1-6 with 12M nodes/side. **11 challenges, 66 walk steps, 0 finds** — the exact
search cannot even re-derive our own record-length path (ac-05077 exhausted
20,224,667 nodes at slack 1 looking for a 30-move path we hold). Those paths were
found under different caps and budgets and are not recoverable inside this box.

### Two hypotheses killed cheaply

**The rank-3 stable search is dead.** The standing argument for building it was
that `sac_best - ac_best` ran as low as -104, proving stabilisation could shorten a
path dramatically. On the refreshed snapshot that is no longer true:

| sac_best - ac_best | challenges |
|---|---:|
| +2 | 6,707 |
| +1 | 615 |
| 0 | 75 |
| > +2 | 35 |
| negative | 11, never by more than 2 |

The field's stable records are now just the ac record plus two destabilises, which
is exactly what our harness already emits. There is no 104-move win to chase and
the build is not worth starting. The -104 figure in memory is stale.

**MAXLEN 44 was not the binding constraint.** It caps slack at 42 - size, which
allows only slack 2 at size 40, so it looked like the reason the walk stopped at 8.
Measured: **0 of the 124 convertible leads is truncated at slack 8** — they all sit
on presentations of size 34 or less. `ACC_MAXLEN` is kept for walks past slack 8;
it buys nothing on the current list.

### Where the value is, and why we cannot reach it

Single-holder challenges, where a match pays 0.5 and a beat 1.0:

| record band | single-holder | our reach |
|---|---:|---|
| <= 30 | **2** | exact search reaches all of it |
| 31-60 | 891 | reaches, lands over the record |
| 61-300 | 2,615 | does not reach |
| 301+ | 316 | does not reach |

Of 3,824 single-holder challenges, 2 are at records our search settles. The
anti-correlation the log recorded in September has hardened: records <= 30 are now
shared 8 to 41 ways because everyone finds the optimum there, and 2^(1-k) makes
that band pay nothing. `skip_exact.txt` grew from 780 to 1,245 settled ids today.

### What is and is not reachable on this hardware

Reachable, and done: every challenge whose true minimum fits inside cap = size + 4
and whose record we can match. That is 148 holds worth 0.0388 points, and today's
work added 0.0031 of it.

Not reachable: anything paying 0.25 or more. Rank 3 needs +519.4, which is about
520 outright beats. Our best rate all campaign was 3 per hour and today's rate was
0 per six hours across 570 challenges in six target classes. The binding constraint is
that a path of 31 to 60 moves must be expressible inside a cap of size + 0 to + 4
to be found exactly, and the teams above us have solvers that produce such paths
without that restriction. **Top 3 is not reachable on this machine by any parameter
setting, and the honest ceiling of the present method is a score under 0.1.**

**One more knob, closed.** Raising the beam's length cap from 44 to 68
(`ACC_MAXLEN=72 --cap 68`), which the exact search can never do, changed nothing
on the five closest record-31 targets at beam 16,384: 31, 32, 32, 35, 34 against
31, 32, 32, 34, 34 at cap 44. A wider cap only fills the beam with long states,
because the ranking is length itself. The cap is not the constraint; the ranking
is.

### What the next run should do

The three cold sweeps were stopped at the end of the run rather than left to hold
5.4 GB overnight on a machine with no free physical memory: 368 challenges between
them, 7 finds, 0 scoring, so their expected yield did not justify the load. Their
ids are folded into `skip_exact.txt`, which is why it grew to 1,245, and their
"found but too long" lines are lead candidates for the next `t_exact.txt`. No
python processes are left running and commit charge is back to 23.2 GB.

Next run: refresh, rebuild `t_exact.txt` through the attribution filter (exact and
ball origin only, distance <= 5), and walk at slacks 1-4 with 12M nodes/side. Do
not spend anything on slacks 5-8 at a 5M budget, on A*-origin leads, on the long
record tail, on our own joint holds, or on a rank-3 stable search. All five are
measured negatives as of today.

## 2026-09-26 15:00Z, the trained policy, measured, and a beam that reaches the record

The pool was 16 hours stale, so `refresh_pool.py` first: 10,115 challenges,
snapshot 13:30Z. The refresh opened exactly **10** challenges we neither hold nor
have settled at a record the exact search can reach, all in the 18-22 band.
Records 23-30 now have 205 open challenges and **0 unsettled**; the band is
finished.

**Standing.** Before, 13:35Z: ac rank 22, 0.0310, 148 held; stable_ac rank 22,
0.0361, 131 held. After, 14:50Z: **ac rank 22, 0.0303, 149 held; stable_ac rank
22, 0.0351, 131 held.** Submission 2406, 1 line, `ok` from the official
verifier. The score FELL while a hold was added, purely to dilution: leaders
AC-Solver =D 1975.89 on ac and the rank-1 stable team 2059.85, rank 3 (Catsitter) 585.14, so
+585.1 to pass.

### The harvest: 10 challenges, 3 leads, 0 points

Exact bidirectional search, records 18-22, slack 4, `--shorten`.

| challenge | record | k | ours |
|---|---:|---:|---:|
| ac-00338 | 20 | 13 | 26 |
| ac-01059 | 22 | 11 | 23 |
| ac-03926 | 22 |  8 | 23 |

The other seven returned none with the familiar signature: 6,831,269 nodes on
two different challenges, 6,838,907 and 6,835,153 and 6,818,033 on three more.
Presentation-independent backward ball, budget failure, not absence.

The walk on the two one-move leads measured nothing again. ac-01059 returns
none at slack 1 and then **23 at slack 2, 23 at slack 3 and 23 at slack 4**
against a record of 22, and slack 5 was still running after ten minutes when it
was killed. The record is held by a path that leaves cap = size + 4.

**An operational correction worth keeping.** The first harvest attempt ran at
10,000,000 nodes/side with `--table-bits 23` and took 50 minutes to clear two
challenges. `solve_bidir` allocates its arrays INSIDE the njit function, so
every challenge zeroes about 2.1 GB, and with ~2 GB of physical memory free that
is page faults, not search. At 4,000,000 nodes/side and `--table-bits 22` the
same ten finished in about two minutes. **On this machine the exact search is
memory-bound before it is compute-bound; size the budget to free physical
memory, not to the commit limit.**

### The trained policy of arXiv 2408.15332, built and measured

The paper itself is the first piece of evidence and it was not read closely
enough before. Its PPO is an actor-critic with two hidden layers of 512 units,
trained for 100 million environment interactions. Its results on the 1,190
Miller-Schupp presentations: greedy search **533**, breadth-first **278**, PPO
**431** at horizon 200 and **402** at horizon 400, and the paper states the
constant-horizon PPO solutions "formed a subset of the presentations solved by
the greedy search". Only with a variable horizon schedule did it solve **2**
presentations greedy could not. So the method whose name sits at rank 1 on this
board was, in its own paper, weaker than greedy search on 1,188 of 1,190 cases.
Our greedy solves 452 of the same 1,190 (`runs/bench/ms1190/summary.json`).

That does not settle whether a network helps HERE, so one was built. Three new
scripts, all local: `runs/pool/policy_data.py`, `policy_net.py`,
`policy_solve.py`, plus `policy_eval424.py` and `policy_export.py`.

**Supervision is free and does not need PPO.** Scramble backwards from (x, y)
and the correct action is known by construction. `policy_data.py` produced
**3,000,000 labelled states from 200,000 walks in 2.2 s (1.37M rows/s)** under a
cap of 44 on total relator length, mean total length 26.8 against the pool's
median of 29.

**The network trains here comfortably.** 516,623 parameters, one shared
two-by-512 body with a policy head and a value head. Eight epochs over 2.95M
rows in **1,199 s at 16,400 to 22,700 samples/s** on three to six CPU threads.
Held-out accuracy: top-1 **0.342**, top-3 **0.635** against a uniform baseline
of 0.071 and 0.214, value MAE 5.75.

**And the accuracy is concentrated exactly where it is worthless.**

| distance from the target | top-1 | top-3 |
|---|---:|---:|
| 1-5 | 0.628 | 0.869 |
| 6-10 | 0.455 | 0.720 |
| 11-20 | 0.355 | 0.636 |
| 21-30 | 0.245 | 0.557 |
| 31-45 | **0.189** | 0.517 |
| 46-64 | **0.177** | 0.518 |

| total relator length of the state | top-1 |
|---|---:|
| 2-10 | 0.511 |
| 11-20 | 0.471 |
| 21-30 | 0.392 |
| 31-38 | 0.286 |
| 39-43 | **0.199** |

Records 31-60 are reached through states of length 31-43 at distances of 31-60.
There the policy is at 0.18-0.20 against a 0.071 baseline. This is the same
stratification every other architecture in this campaign hit, now measured
inside the network itself rather than inferred from its failures.

**Retraining on deep states only does not lift it.** 1,125,647 rows at distance
25 and above, 13 epochs: top-1 went **0.185 -> 0.198** and was flat from epoch 1.
Spending all the capacity and all the data on the band that pays buys nothing, so
the ceiling is the problem and not the budget.

**Off-distribution it is worse, and the critic is useless.** Replayed against the
organisers' 424 certified paths (14,257 states, the only ground truth that
exists): the certified move is top-1 on **0.258** and top-3 on **0.535**, which
is honest generalisation, but the value head's MAE against true moves remaining
is **16.13** where the mean remaining is 25.0. A critic that far out cannot order
a frontier. Worth noting: those certified states have mean total length **10.3**,
a third of the pool's, so the published training data does not live where the
pool does either.

### The control beat the network, and then the control scored

40 pool challenges at record 31, beam 512, 200 steps, cap 44:

| ranking | found | at or under the record | shortest |
|---|---:|---:|---:|
| policy (actor alone) | 2 | 0 | 67 |
| hybrid (actor + critic) | 12 | 0 | 35 |
| **total relator length, no network at all** | 12 | 0 | **33** |

Head to head at beam 4096 on the 18 both solved: the network's paths are longer
on **14 of 18**, median **71.5 against 52.0**, best 34 against 32. Only length
scores, so the network is a net negative in the one dimension that pays.

**The beam itself is the finding.** The same search with no network, ranked on
total relator length, scales:

| beam | found of 40 | shortest against record 31 |
|---|---:|---:|
| 512 | 12 | 33 |
| 4,096 | 20 | 32 |
| 16,384 | 12 of the closest 12 | **31, one tie** |
| 65,536 | 5 of 5 | **31, two ties** |

ac-07084 and ac-07163 both returned exactly 31 against a record of 31. **This is
the first time anything in this campaign has landed ON a record in the 31-60
band**, and it does it at cap 44 where the exact search cannot go at any slack.
`submit` sent ac-07084 (2406, verified). ac-07163 is **not** a new find and the
distinction matters: we already hold it at 31 from an earlier run, so the beam
re-derived a path we own, which is a useful check that it can land on a known
record and nothing more. Neither scores on stable_ac, because our stable path is
the ac path plus two destabilises while the sac record there is ac + 1. So the
honest count from the twelve closest targets at record 31 is **one new scoring
line**.

**And it stops at the record, measurably.** ac-07673 returned **32 at beam 4,096,
32 at 16,384 and 32 at 65,536** - a sixteenfold budget increase for zero moves.
Beam width buys the first ten moves cheaply and then nothing.

**Where it matters it does not reach.** The 161 single-holder challenges at
records 31-45, where a match pays 0.5 and a beat 1.0, at beam 16,384: the first
nine gave 6 found and **0 scoring**, with paths of 38, 45, 47, 57, 65 and 194
against records of 32 to 35. The sweep was left running (`runs/pool/policy/
k1_len16k.out`) because it is the only lever with any slope left; the next run
should collect it. The record-31 group that matched has k between 11 and 15,
which is the old anti-correlation restated: the beam lands on records that
everyone already ties, where 2^(1-k) is 0.00006.

### Machine facts, measured

- Network forward only: **31,551 states/s at batch 256 to 58,295 at batch 8,192**.
  Forward and backward at batch 2,048: **17,992 states/s** on three threads with
  the machine contended.
- Scramble generation: **1.37-1.85M states/s** on the numba core.
- **Estimate, derived from those measured rates**: one PPO run at the paper's
  100M environment interactions costs about 2,000 s of action sampling plus about
  22,200 s of update if PPO takes four passes over each rollout, so roughly
  **seven hours per run**, and the environment itself is free. The paper's loop
  is affordable here. It is simply aimed at a signal that is not present past
  distance 30.
- **There is a GPU, and the brief said there was not.** `nvidia-smi` reports an
  **NVIDIA GeForce MX250, 2,048 MiB, compute capability 6.1, driver 582.53**.
  numba lists it as SUPPORTED but `cuda.is_available()` is False because NVVM is
  not installed, and the installed torch is **2.11.0+cpu**. A CUDA wheel does
  exist for this interpreter (`torch-2.10.0+cu126-cp314-cp314-win_amd64`). It is
  not obviously worth the swap: the beam search measured here spends its time in
  node expansion and the candidate loop, not in the 516k-parameter forward, and
  2 GB of VRAM on a Pascal part is perhaps five times this CPU on dense matmul.
  Amey should decide, not the run.

### Verdict on the trained-policy approach on this hardware

**Trainable: yes, comfortably.** A network of the paper's shape trains at 20k
samples/s, data costs nothing, and a full PPO run at the paper's scale is about
seven hours.

**Useful: no, and the reason is measured rather than argued.** The learned policy
is four to nine times better than chance near the target and 2.5 times better
than chance at distance 31-45; restricting the model to deep states does not move
that; the critic does not transfer at all; and in the only test that pays, the
network's paths are longer than ranking by total relator length on 14 of 18
challenges. The paper's own PPO was a subset of greedy on 1,188 of 1,190 cases,
which is the same result from the other direction.

**What the run did leave behind is a better classical solver than we had.** A
fixed-width beam over total relator length at cap 44 lands on records of 31,
which nothing here has done before, and its cost curve is known: 512 to 65,536 is
128 times the budget for two to nine moves, then flat.

### What the next run should do

1. Collect `runs/pool/policy/k1_len16k.out` (161 single-holder challenges at
   records 31-45, beam 16,384). If any path is within 3 of the record, re-run
   that id at beam 65,536; that is the only conversion path with a measured
   slope.
2. Refresh, then harvest records 18-22 at slack 4 and **4M nodes/side, not 10M**.
3. Do not spend anything on: the trained policy as built (this entry), the cap
   walk past slack 4, records 23-30 (settled), A*-origin leads, the long-record
   tail, our own joint holds, or a native stable search.
4. The open question with any slope left is whether the beam's length ranking can
   be replaced by something better than the network tried here - and the honest
   reading of this entry is that the next real gain is hardware or a different
   idea, not another parameter.

**Nothing was committed this run.** Five new files are local only:
`runs/pool/policy_data.py`, `policy_net.py`, `policy_solve.py`,
`policy_eval424.py`, `policy_export.py`, plus `runs/pool/policy/` and
`runs/pool/skip_run0926b.txt`, `runs/pool/t_h0926.txt`.

## 2026-09-27 00:45Z, the beam was taken to its limit and the limit is measured

Continuation of the run above, at Amey's instruction to keep going toward top 3.
The sweep left running overnight completed and five further mechanisms were
tested. **Nothing scored, and by the end nothing left had a measured slope.**

**Standing, unchanged all session**: ac rank 22, 0.0303, 149 held; stable_ac rank
22, 0.0351, 131 held (snapshot 00:40Z). No submission this half of the run,
because nothing produced a path at or under a record.

### The single-holder band, measured in full

The beam over **all 161 single-holder challenges at records 31-45** - the whole
accessible volume where a match pays 0.5 and a beat 1.0 - at beam 16,384, cap 44,
11,129 s:

**112 found, 49 none, 0 at or under the record.**

The gap distribution is the result, not the find rate:

| gap, ours minus record | challenges |
|---|---:|
| +0 to +4 | 3 |
| +5 to +9 | 3 |
| +10 to +19 | 17 |
| +20 to +34 | 36 |
| +35 to +59 | 25 |
| +60 and over | 28 |

**Median gap +32. Median ratio ours/record 1.80.** Only four challenges came
within five moves. Against that, beam width's measured slope is 2 to 9 moves per
128-fold increase. Closing a median gap of +32 is arithmetic that does not work.

### The four near misses, escalated until they stopped

| challenge | record | k | beam 16,384 | 65,536 | 262,144 |
|---|---:|---:|---:|---:|---:|
| ac-05726 | 35 | 1 | 38 | 38 | - |
| ac-06045 | 36 | 1 | 40 | 40 | - |
| ac-08995 | 45 | 1 | 49 | 47 | **46** |
| ac-00678 | 41 | 1 | 46 | 42 | **42** |

Two reached **gap +1 against a single holder**, which is the most valuable
position this campaign has ever been in: one move is a tie worth 0.5, two is an
outright point. Then the beam stopped. **ac-00678 returned 42 at beam 65,536 and
42 again at 262,144** - a fourfold increase, 126 million nodes, zero moves. Same
signature as ac-07673 returning 32 at 4,096, 16,384 and 65,536.

### Four ways to get one more move, all measured negative

**Stochastic restarts do not help, so the beam's limit is the ranking and not
basin collapse.** A length ranking collapses the beam onto near-identical short
states, so the textbook fix is Gumbel noise on the score plus restarts, sampling
different basins at the same total cost. 32 restarts at beam 8,192, temperature
1.5, which is 2 to 12 times the compute of the single wide beam:

| challenge | best wide beam | 32 noisy restarts | nodes spent |
|---|---:|---:|---:|
| ac-05726 | 38 | 38 | 376M vs 30M |
| ac-06045 | 40 | **42** | 147M vs 32M |
| ac-08995 | 46 | **53** | 188M vs 143M |
| ac-00678 | 42 | **49** | 173M vs 126M |

Equal on one, worse on three, at more compute on all four. That kills the
diversity hypothesis directly rather than by inference.

**Detour shortening gains nothing on a beam path, and this was checked with a
control rather than believed.** `engine.shorten` had never been run on a beam
path; `runs/pool/policy_shorten.py` does it. On all six paths within 8 of a
record: **0 moves at depth 2, 3, 4 and 5** (depth 5 costs 16.7 s on a 42-move
path). The result looked too clean, so a control was run: the same call on the
same path with a deliberate two-move cycle planted in it cuts exactly two moves
in 0.03 s. The tool works; the paths have no detours. That is what a length
ranking means - it minimises length at every step, so its path is already locally
tight. Shortening was built for greedy paths that wander.

**The cap walk is closed on these targets, and the reason is memory.** At 4M
nodes/side the walk returned none on all four with the presentation-independent
ball signature. At 12M nodes/side, which the 26 Sep entry recorded as completing,
it burned **1,808 s of CPU and 1.5 GB without printing one slack line** and had to
be killed: 12M/side allocates about 2.5 GB inside the njit call, and that is
thrashing on this machine whatever the commit limit says. The budget the machine
can actually hold was measured directly on ac-00678 at slack 1:

| nodes/side | table bits | nodes used | wall | nodes/s |
|---|---:|---:|---:|---:|
| 2,000,000 | 21 | 2,692,962 | 3.2 s | 838,307 |
| 4,000,000 | 22 | 6,835,153 | 11.8 s | 580,299 |
| 8,000,000 | 23 | 10,835,153 | 21.4 s | 505,254 |

**6,835,153 and 10,835,153 differ by exactly 4,000,000, the whole budget
increase.** One side consumes its entire allowance while the other finishes at
about 2.8M. That is the backward ball, pinned numerically rather than inferred
from repeated counts. Raising the budget feeds the ball and never the forward
half. The walk re-run at 8M/side, the largest this machine holds: **0 of 4**, and
ac-05726 returns **38 at slack 2**, exactly what the beam returned, then nothing
at slacks 3 and 4. The exact search independently confirms 38 is the true minimum
inside cap = size + 2 and that the record of 35 is held by a path leaving that
box.

**The wider cap and the trained policy were already closed** in the entry above.

### Why this is the ceiling, in the one number that matters

Rank 3 (Catsitter) went **585.14 at 14:50Z to 686.32 at 23:35Z**, which is
**+11.6 points per hour**. Our best rate in the whole campaign was 12 Sep, 2.85
to 24.5 points across about a day, under **1 point per hour**. This session's
rate was **0 across roughly eleven hours and 175 targets** in four escalations
and five mechanisms.

The target is receding an order of magnitude faster than the best rate this
method has ever achieved. That is not a parameter away. **Top 3 is not reachable
from here and the honest thing is to stop rather than run another sweep.**

What this session did establish, and it is worth keeping: a fixed-width beam
ranked on total relator length reaches **gap +1 against single holders at records
41 and 45**, which no search in this campaign had come near, and its exact
stopping point is now known in five independent directions. If the ranking is
ever replaced by something better - not the network tried here - those two
challenges are one move from a point.

### Skip lists were not corrupted

The 161 beam attempts are recorded in **`runs/pool/beam_attempted.txt`** with the
width used, the path found and the gap, and deliberately **not** folded into
`skip_exact.txt`. That file records settled-ness of the EXACT search at a band's
correct slack, and a beam attempt settles nothing; mixing them would break the
one skip list the campaign trusts.

### What the next run should do

Nothing in the present method. The measured negatives now cover the trained
policy, beam width past 262,144, stochastic restarts, detour shortening, the
wider length cap, the cap walk at every budget this machine holds, records 23-30,
A*-origin leads, the long-record tail, our own joint holds, and a native stable
search. A run that starts by picking one of those is burning budget.

The two things that are not measured negatives are both outside the machine: a
solver of the class the leaders are actually running, and hardware that can hold
a search whose backward half does not eat the whole budget. Both are Amey's
decisions, not a run's.

**Nothing was committed. Two further local files: `runs/pool/policy_shorten.py`
and `runs/pool/beam_attempted.txt`, plus `--mode noisy`, `--temp`, `--restarts`
and `--ids` added to `runs/pool/policy_solve.py`.**

## 2026-09-27 02:30Z, the bidirectional beam, and why a meet in the middle cannot happen here

Resumed at Amey's instruction with the goal reaffirmed. The one lever my ceiling
report did not list as tried was a **bidirectional** beam: everything that has
ever scored here is bidirectional, while the beam that reached gap +1 is
forward-only. Built it, validated it, and measured it to a mechanism. It is a
negative, and for the first time the reason is quantified rather than inferred.

**Standing**: refreshed at 01:00Z. ac rank 22, 0.0303, 149 held; stable_ac rank
22, 0.0351, 131 held. **Nothing submitted: nothing came in at or under a record.**
Rank 3 (Catsitter) is now 692.78 on ac, up from 585.14 at 14:50Z yesterday.

**Harvest first, as always.** The refresh opened **nothing new**: the open and
unsettled band at records 18-30 is the same ten challenges already run at slack 4
earlier in this session, for three leads and no points.

**A detail worth having on the two best targets.** ac-00678 and ac-08995 both have
`sac_best = ac_best + 2` with **k = 1 on both boards** (41/43 and 45/47). Our
harness emits stable as the ac path plus two destabilises, so one move on either
is worth **0.5 on ac and 0.5 on stable**, and two moves is worth **2.0 in total**.
That is double what the previous entry assumed and it is why they were worth this
much effort.

### What was actually new about it

Three search shapes already existed and it matters that this is not a fourth
version of one of them:

| | shape | behaviour |
|---|---|---|
| `jit_tieband.solve_bidir` | bidirectional, **exhaustive** inside a hard cap | true minima, cannot leave the cap |
| `bestfirst.py` | bidirectional, length as a **global** bucket priority | reaches far, paths not minimal |
| `policy_solve.py --mode length` | forward-only, **level-synchronous** beam of fixed width | the one that reached 42 against 41 |

The missing combination is the third shape run from both ends. Fixed width per
depth level is what made the forward beam work, because it forces progress in
depth while holding B diverse states per level, which a global priority queue
does not. `runs/pool/bibeam.py` does that, with the backward half built once per
(width, depth, cap) and reused, since it is presentation-independent.

**It was validated before it was believed**: on eight challenges with records 8 to
13 it reproduced the record exactly, 8 of 8, every path replayed.

### It returns the forward-only answer, at every backward configuration

All at forward beam 32,768 on ac-00678, record 41:

| backward half | states | result | nodes | time |
|---|---:|---:|---:|---:|
| none (forward-only control) | - | **43** | 16,844,842 | 67 s |
| short-ranked, depth 12 | 1,875,787 | **43** | 52,168,746 | 196 s |
| band-ranked at length 38, depth 8 | 136,187 | **43** | 52,168,746 | 156 s |
| band-ranked at length 38, depth 24 | 660,475 | **43** | 52,168,746 | 223 s |

A backward set of **1.88 million states, 57 times the forward beam width**,
changes the answer by zero moves at three times the cost. On the four near-miss
targets at forward beam 16,384 the bidirectional run returned 38, 40, 49, 46 -
**identical to the move** to the forward-only beam at the same width.

**The identical node counts across different backward sets are expected, not the
bug this campaign has been caught by twice.** The count is the forward beam's own
expansion total, and the forward beam is deterministic and unaffected by what the
backward set contains. Checked before reporting.

### Why, measured

The run was instrumented to report where the winning join actually lands. On
ac-00678 against the 1,875,787-state backward set:

    join f=36 + b=7 at total relator length 11, 85 joins seen

Three numbers, and they close the idea:

1. **85 joins.** From 52.2 million forward candidates tested against 1.88 million
   backward states, the two frontiers intersected 85 times in the whole run. Two
   sparse sets do not meet in this space.
2. **The join is at total relator length 11.** Not in the middle. Meets happen
   only where the state space is small enough for sparse sets to collide, and that
   is the short-length region immediately around (x, y).
3. **f = 36, b = 7.** The forward beam had already descended all the way to a
   near-trivial state on its own; the backward set contributed seven free moves at
   the very end, which is no better than the forward beam's own last seven.

So bidirectionality here is **degenerate**: it shortens the tail of a descent the
forward beam was going to finish anyway. That also explains the band-ranked
failure without a further experiment. Pulling the backward frontier up to length
38, where the forward beam actually spends its time, removes the only region where
a meet is possible, so it does worse (43 where forward-only at 65,536 gets 42).

**One instinct of mine was wrong and checking it was the right call.** I expected
a backward frontier to need depth about 18 to reach total length 38, on the
grounds that conjugation adds at most two letters. It reached mean length 36.1 at
**depth 7**, because concatenation replaces a relator with a product and grows
length geometrically. The depth floor I assumed does not exist; the barrier is
state-space size, which is what the 85 joins measure. Asserting the bound would
have produced a wrong explanation of a right result.

### Nothing left has a measured slope, and this is the third independent statement of it

The closed list now covers: the trained policy, beam width past 262,144,
stochastic restarts, detour shortening, the cap walk at every budget this machine
holds, the wider length cap, **the bidirectional beam at every backward width,
depth and ranking tried**, records 23-30, A*-origin leads, cold sweeps in every
band, the unsolved pool, the long-record tail, and walking our own holds into
beats.

The board, for scale: rank 3 went **585.14 to 692.78 in about ten hours**, roughly
**+11 points per hour**. This campaign's best rate ever was under 1 point per
hour; the last two sessions produced 0 across some twenty hours and around 180
targets. ac-00678 and ac-08995 remain one move short, and one move is worth 1.0
across the two boards, but five distinct mechanisms have now failed to find it.

**The honest position is unchanged and better evidenced: top 3 is not reachable
from this machine by this method.** What is left is a solver of the class the
leaders run, or hardware that can hold a search whose backward half does not
consume the whole budget. Neither is a parameter and neither is a run's decision.

**Nothing was committed.** New local file `runs/pool/bibeam.py`; no other changes.

## 2026-09-27 17:40Z, shortcutting, the long-record band, and the ratio that ends the argument

Three things this session: a persistent harvest cycle, path shortcutting with the
exact search, and a paired test of the long-record band. All three are negatives.
The last of them produced the single cleanest statement of this campaign's ceiling
and it is a number, not an argument.

**Standing.** ac rank 22, **0.0243**, 149 held; stable_ac rank 22, **0.0281**, 131
held (17:40Z). Down from 0.0303 and 0.0351 with the held counts UNCHANGED, so the
loss is entirely other teams tying our records. Rank 3 is now **memcon.ai at
1,016.35**, where it was Catsitter at 692.78 twelve hours earlier. **Nothing was
submitted: nothing came in at or under a record.**

### The harvest cycle has a measured rate of zero

Six refreshes: 01:35, 01:50, 02:20, 02:35, 02:45 and 16:40Z, the last spanning a
thirteen-hour gap. **Every one returned 0 open and unsettled challenges at records
18-30.** The ten that were open at the start of the session were run at slack 4
and are now recorded in `skip_exact.txt` (1,245 -> 1,255).

This matters because the harvest was the one thing with a nonzero rate. The 12 Sep
entry recorded the band refilling as other teams pushed long records down into it
(records 31-60 went 1,250 to 1,392 in a night). **That mechanism no longer
operates at records 18-30.** There are 373 challenges at records <= 30 and every
one is either held by us or settled; across fifteen hours the field pushed nothing
new into the range the exact search can reach. The harvest is not a slow source of
points, it is an empty one, and the score falling while the holds stay flat is the
same fact from the other side.

### Shortcutting: the paths are locally minimal, and now proven so

The idea was the right shape and it is not `engine.shorten`. Shorten hunts
detours of radius at most `depth` between states already on a path. Shortcutting
asks the exact search for the TRUE MINIMUM between two concrete states si and sj.
No tool here could answer that, because `jit_tieband.search_bidir` hardcodes its
backward start as (x, y); `runs/pool/shortcut.py` parameterises it.

**Validated first, on a planted control.** Take a path the exact search proves
optimal, splice six wasted moves into it (three copies of the involution pair
0,0), and confirm shortcutting removes exactly them: **5 of 5 recovered the
optimal length**, endpoint preserved.

Then on the two targets one move from a point, sweeping every window of span 6 to
22:

| challenge | record | path | windows | splices | moves saved |
|---|---:|---:|---:|---:|---:|
| ac-00678 | 41 | 42 | 493 | **0** | 0 |
| ac-08995 | 45 | 46 | 561 | **0** | 0 |

**Instrumented, because 0 of 1,054 windows is the kind of number that is either a
result or a bug.** For every window, the length the exact search returns minus the
length we hold:

    delta  +0: 467     delta > 0: 0     delta < 0: 0     unreached: 26

**467 of 467 reachable windows re-derived our own length exactly.** Never longer -
which is the check that matters, because our own window is a witness of that
length, so a longer answer would have proved the search was not finding minima and
that the idea had never been tested. Never shorter either.

So this is the second of the two possible results, the one that closes the idea:
**our 42-move path for ac-00678 is minimal over every subpath of span 6 to 22.**
The missing move is not recoverable by any local reoptimisation. The holder's
41-move path differs from ours globally, not in any 22-move stretch. That also
says something about the structural ten percent gap: **our paths are locally
optimal and globally too long**, so the holders are in a different basin rather
than a better-polished version of ours.

### The long-record band: paired, and the cap was never the constraint

The argument for this band was good: 2,841 single-holder challenges sit at records
61 or above, each worth a full point, and only 25 attempts had ever been made
there, which cannot distinguish a 0 percent rate from 3 percent. The stronger
version used this campaign's own data - the beam found paths on 112 of 161
challenges at records 31-45, and those paths have **median absolute length 74 with
80 percent under 121** - so if length were independent of the record, every one of
the 1,049 single-holder challenges above record 121 would be a free beat.

Tested on a stratified 40 (15 at records 61-120, 15 at 121-300, 10 at 301+;
records 63 to 1,147; presentation size median 30, the same as every other band):

| cap | found | at or under the record | s/attempt |
|---:|---:|---:|---:|
| 44 | **1 of 40** | 0 | 110 |
| 80 | **3 of 40** | 0 | 140 |

Find rate 1/40 = 2.5% [0.4%, 12.9%] against **69.6% [62.1%, 76.1%]** at records
31-45. Non-overlapping: the band is genuinely harder, presentation size is
identical, so **record length is a proxy for difficulty after all**, exactly as the
13 Sep entry said. The earlier 0/13 was not a sample-size artefact.

**Raising the cap looked like it helped and did not, and the check that settled it
was replaying the paths.** Cap 80 found three where cap 44 found one, which is
Fisher p = 0.62, not significant. More decisively, every one of the three paths was
replayed and its peak total relator length recorded:

    ac-08370  len 109 vs record 67   peak length 27
    ac-03941  len 209 vs record 76   peak length 29
    ac-02900  len 235 vs record 87   peak length 23

**All three fit inside the old cap of 44 with room to spare.** The cap was never
binding; widening it merely reshuffled which 16,384 states survive each level. The
hypothesis is closed on a mechanism, not on a rate.

And the three finds are 1.6, 2.8 and 2.7 times their records. The argument
required path length to be roughly constant regardless of the record. It is not:
**it scales with the record.**

### The ratio, across everything the beam has ever solved

Every distinct challenge any beam run has solved, 25 result files, 150
challenges, ratio = our length / the record:

| ratio | challenges |
|---|---:|
| exactly 1.00 | **10** |
| strictly below 1.00 | **0** |
| median | **1.76** |

**In 150 solved challenges this solver has never once beaten a record.** The ten
it matched are at k = 12 to 41 - records that a dozen to forty teams already
share, where 2^(1-k) is between 0.0005 and 0.0000000000005. That is the campaign
in one line: it can match what everybody already has, and has never produced an
outright point.

At 140 s per attempt the 1,684 single-holder targets above record 88 are 66
CPU-hours, and the measured scoring rate to spend them against is 0 of 40 with a
95 percent upper bound of 8.8 percent. But the upper bound is not what decides it.
The ratio does: **scoring requires ratio <= 1, and 150 measurements put the
minimum at 1.00 and the median at 1.76.**

### Plainly

Fourteen mechanisms are now closed, three of them this session with a mechanism
rather than a rate. The harvest, the only source with a nonzero rate, measured zero
over fifteen hours. The score is falling while the holds stand still. Rank 3 moved
from 692 to 1,016 in twelve hours; our total is 0.0243.

**Top 3 is not reachable from this machine by this method, and the ratio is why.**
Not the budget, not the cap, not the band, not the ranking: this solver's output is
between 1.00 and 5.88 times the record and has never been below 1.00. A method that
cannot produce a path shorter than a record cannot take one, at any scale. Closing
that needs a different class of solver, which is a build and a hardware decision,
not a run.

**Nothing was committed.** New local files this session: `runs/pool/shortcut.py`,
`runs/pool/suffix_opt.py`; `skip_exact.txt` grew by the ten settled ids.

---

## 16 October 2026 — every scoring opportunity on this machine is already sent

The question this run was asked is whether anything solved here is still
unsubmitted. The campaign wrote solutions into one directory per run and each
directory carries its own `submitted.jsonl`, so no single ledger can answer it:
a path found in run A and sent from run A is invisible to run B. The
leaderboard can answer it, and `runs/pool/reconcile.py` now does, by reading
the API rather than any local ledger.

It pulls the full 10,115-challenge snapshot for each problem, which carries the
current record and the number of teams tied at it, then the team-challenges
endpoint, which lists exactly what is scoring for us, then every solution file
under `runs/pool`. 792 distinct scored challenges are solved on this machine
across 88 result files.

| | `ac` | `stable_ac` |
| :--- | ---: | ---: |
| solved here | 396 | 396 |
| ties the record, already held | 149 | 131 |
| longer than the record | 247 | 265 |
| beats the record | **0** | **0** |
| unsolved by anyone | **0** | **0** |
| ties a record we do not hold | **0** | **0** |

**Actionable: zero.** Everything that can score has been sent, and everything
else is longer than the record and would score nothing. The 904 solutions in
`runs/bench/ms1190` are the Miller-Schupp benchmark family, ids `ms-NNNN`, not
the scored pool, and are correctly outside this count.

This is the same conclusion the 25 September entry reached from the other
direction, and it is now closed against the live board rather than against the
beam's own output: the ratio of our length to the record has a minimum of 1.00
over 150 measurements, so there is no path here shorter than a record to send.

Standing at the 2026-10-16T01:40Z snapshot: `ac` rank 28 of the ranked field,
score 0.0003, 149 held; `stable_ac` rank 25, score 0.0016, 131 held. The score
keeps falling as other teams match the same records, which is the `2^(1-k)`
rule working as designed and not a regression on our side.

Committed this session: the nine solvers written since the last commit, the two
that changed, and `reconcile.py`. No sequence left the machine.

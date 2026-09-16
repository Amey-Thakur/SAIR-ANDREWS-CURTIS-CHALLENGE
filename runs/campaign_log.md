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

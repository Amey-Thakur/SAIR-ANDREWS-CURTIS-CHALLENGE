# Proof Track submission, field by field

Go to competition.sair.foundation → Create Submission → **Choose Proof Track**.
Do not use Discovery Track; that one is submitted automatically through the API.

---

## Title

```
Length as a priority, not a bound: measured structure of Andrews-Curtis search on the ACC pool
```

## Authors

```
Amey Thakur
```

## Claim type

**AC** — **proof**

(The direction records what the work is aimed at, not a finished argument.)

## Result completeness

**Partial result**

## GitHub repository link

Leave empty. The search code stays private until the 30 November deadline. The
Commit SHA field is only required when a repository link is given, so leave that
empty too.

## arXiv / Paper link

Leave empty.

## References

Skip "Add reference". That field wants a published ACC submission to build on,
and this one builds on none. The paper and repository used are cited in the
Description, which is what the rules ask for.

## Sharing checkbox

Tick "I understand that my submission will be public on SAIR Contributor
Network", then **Publish Proof**.

---

## Description

Paste everything below the line.

---

**Empirical structure of the Andrews-Curtis search space on the ACC Discovery
pool, and what it implies for search design.**

This is a partial result. It proves nothing about the conjecture. It reports
reproducible measurements over the 10,115 balanced presentations of the
Discovery pool that constrain how an AC search should be built, together with
four negative results that are cheap to state and expensive to rediscover.

**1. A bound on total relator length is the wrong constraint.**

Bidirectional search over this pool is naturally written with a cap: reject any
intermediate presentation whose total relator length exceeds the initial length
plus a slack. That cap is the dominant error. An AC path characteristically
lengthens the relators before they collapse, so a hard cap forbids exactly the
intermediate states a short path passes through and forces the search onto a
longer route.

Measured on ten pool presentations with known optimal lengths 8 to 16, at a
fixed node budget, reporting the path length found against records 15, 15, 14,
10, 14, 11, 13, 8:

- capped exact search: frequently no path at all inside the cap
- priority = total length: 32, 140, 129, 13, 75, 21, 49, 10
- priority = total length + 4 x (moves spent): 15, 15, 14, 10, 14, 11, 13, 8
- priority = total length + 12 x (moves spent): 15, 15, 14, 10, 14, 11, 13, 8

At the last setting all ten are solved at exactly the known optimum in 0.3 to
2.6 seconds using 2,000 to 2.5M states, where the capped search needed millions
of states and 5 to 25 seconds per presentation to do worse. Making length order
the queue rather than gate admission, and charging for moves spent, was worth
more than any budget increase measured.

Widening the cap is not a substitute for removing it. On one presentation with
record 91, slack 2 returned 95 and slack 4 returned nothing at all: a wider hard
box grows faster than the budget can cover.

**2. The two halves of the priority trade against each other sharply.**

The coefficient on moves spent cannot be set once for the pool. A large
coefficient yields exact minima but bounds reachable depth, since a path of
length L carries priority at least wL: at w = 12 every presentation with record
at most 16 was solved exactly and none of 35 attempted with record at least 121.
A small coefficient reaches those presentations and wanders: at w = 0 a path of
1,912 moves was found for a presentation with record 121, and 3,742 against
record 301. Values 1, 2 and 4 achieved neither on that band. A search of this
shape is competent on a band, not on a pool.

**3. Detour shortening converges immediately and cannot rescue a poor path.**

Replacing stretches of a path by shorter detours found within a small radius cut
the 1,912-move path to 415 on the first pass, then to 396, then to no further
change. On already-short paths one pass gains about 2 percent, and a deeper
radius gains 1 percent more at six times the cost. Long paths carry large slack
and short paths almost none; in neither case does shortening reach the optimum
from a poor start.

**4. The backward half of a bidirectional search is independent of the
presentation.**

The half expanding from the trivial pair is constrained only by the length
bound and never reads the presentation, so every presentation of a given size
rebuilds an identical state set. This is visible in raw node counts: the value
7,226,201 recurred across four different presentations in one run and again in
another. Building that set once per length bound and reusing it reduced each
presentation to the cost of its forward search alone.

The same observation bounds what precomputation can achieve. One such set built
at total length 40 with 22,000,000 states, in 19 seconds, contained 2 of the
10,115 pool presentations. Under a tight bound most moves are rejected,
branching is low and the set reaches deep; under a loose bound branching
explodes and 22M states buys roughly 8 to 10 moves of depth, while the pool sits
20 to 130 moves from the trivial pair. No single bound is simultaneously wide
enough to contain the pool and tight enough to reach it.

**5. Hardness stratification, and why leaderboard records converge.**

Grouping challenges by how many teams share the current record, over the 156 we
hold: one challenge shared by 10 teams has median record 8; 48 shared by 8 teams
have median record 15; 19 shared by 3 teams have median record 26; 20 shared by
2 teams have median record 26, ranging to 48.

A record is short and shared by many teams precisely because its optimum is easy
to reach, and long and held by one team precisely because it is not. Consistent
with this, a search returning exact optima below record 18 returned nothing on
21 attempts at records 27 to 40, nothing on 35 attempts at records 121 to 300,
and nothing on 17 attempts above record 301.

One consequence is practical. Attempting to improve a record shared by many
teams is provably wasted work in the cases checked: on a presentation with
record 8 shared ten ways, the search returns 8 at every slack from 1 to 8, which
witnesses that 8 is optimal there. Zero of 61 such attempts yielded an
improvement.

**6. Two further negative results.**

The abelianisation test is sound and empty on this pool. A balanced presentation
of the trivial group must have exponent-sum matrix of determinant plus or minus
one. Zero of the 7,266 solved challenges violate this, which confirms the test,
but all 2,756 unsolved challenges already satisfy it, so it eliminates nothing.
The pool was evidently pre-filtered.

The exponent-sum lower bound is admissible and far too weak to prune. Across
24,080 matrices its median is 5 and its maximum 13, and on none of the solved
challenges does it approach the held record, whose median exceeds 100.

**What remains open from this vantage.** Every method measured here is competent
exactly where the optimum is short, and the presentations with long records are
precisely those where no method reached any path at all. That region is where
the difficulty of the Discovery Track actually lives. A learned search policy of
the kind described in the work cited below is the relevant class of method; a
least-squares distance-to-trivial heuristic fitted on our own record-length
paths reduced node counts about twentyfold but did not improve path quality over
the tuned priority above, which suggests the useful policy is not a linear
function of simple word statistics.

**Prior work used.** The official SAIR Andrews-Curtis repository,
https://github.com/SAIRcompetition/Andrews-Curtis, for the move specification
and the reference verifier, against which every path reported here was checked.
A. Shehper, A. M. Medina-Mardones, B. Lewis, L. Pinar, S. Gukov et al., "What
makes math problems hard for reinforcement learning: a case study",
arXiv:2408.15332, used only as a yardstick for greedy baseline coverage and as
the reference for the learned-policy approach named above.

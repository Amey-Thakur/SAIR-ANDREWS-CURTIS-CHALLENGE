# Proof Track submission

competition.sair.foundation → Create Submission → **Choose Proof Track**.
Discovery Track is submitted automatically through the API; do not paste there.

| Field | Value |
|---|---|
| Title | see below |
| Authors | `Amey Thakur` |
| Claim type | **AC**, direction **proof** |
| Result completeness | **Partial result** |
| Repository link | `https://github.com/Amey-Thakur/SAIR-ANDREWS-CURTIS-CHALLENGE` |
| Commit SHA | see below |
| arXiv / Paper link | leave empty |
| References | skip; prior work is cited in the Description |
| Sharing agreement | tick it, then Publish Proof |

**Title**

```
Length as priority, not constraint: search geometry of the Andrews-Curtis Challenge pool
```

**Commit SHA** — run `git rev-parse HEAD` in the repository for the current value.
At the time of writing:

```
829725698d2b1de3358b5751f24dc9b2e8358260
```

---

## Description

Everything below the line goes in the Description field. Markdown and math are
supported there.

---

## Summary

A **partial result**: no claim is made about the conjecture itself. This reports
reproducible measurements over the $10{,}115$ balanced presentations of the
Discovery pool that determine how an Andrews–Curtis search should be structured,
and identifies a structural obstruction that limits what any search of this
family can score.

Write a presentation as $P = \langle x, y \mid r_1, r_2 \rangle$, with total
length $\ell(P) = |r_1| + |r_2|$ and $d(P)$ the number of moves applied. Every
path reported here was checked with the official reference verifier.

Code: `runs/pool/` (solvers) and `src/` (engine and verifier) in the linked
repository.

---

## 1. Bounding total length is the wrong constraint

Bidirectional search on this pool is naturally written with a cap: reject any
intermediate presentation with $\ell(P) > \ell(P_0) + s$ for a slack $s$. **That
cap is the dominant error.** An Andrews–Curtis path characteristically
*lengthens* the relators before they collapse, so a hard cap excludes precisely
the states a short path must traverse.

Replacing the cap with an ordering — priority $f(P) = \ell(P) + w \cdot d(P)$,
with no admission test — changes the outcome entirely. On ten presentations of
known optimum, at fixed node budget:

| priority | lengths found, against optima $15, 15, 14, 10, 14, 11, 13, 8$ |
|---|---|
| capped exact search | often no path inside the cap |
| $w = 0$ | $32, 140, 129, 13, 75, 21, 49, 10$ |
| $w = 4$ | $15, 15, 14, 10, 14, 11, 13, 8$ |
| $w = 12$ | $15, 15, 14, 10, 14, 11, 13, 8$ |

At $w = 12$ all ten are solved **at exactly the known optimum**, in $0.3$–$2.6$ s
using $2 \times 10^3$ to $2.5 \times 10^6$ states. The capped search needed
millions of states and $5$–$25$ s per presentation to do worse.

Widening the cap is not a substitute for removing it: on a presentation with
record $91$, slack $s = 2$ returned $95$ and $s = 4$ returned **nothing**. A
wider hard box grows faster than any budget covers.

## 2. The two terms of the priority trade off sharply

No single $w$ serves the pool, because $f \geq w \cdot d$ bounds reachable depth.

- $w = 12$: every presentation with record $\leq 16$ solved exactly; **0 of 35**
  with record $\geq 121$.
- $w = 0$: reaches those presentations but wanders — $1{,}912$ moves against
  record $121$, $3{,}742$ against record $301$.
- $w \in \{1, 2, 4\}$: neither, on that band.

A search of this form is competent on a *band*, not on a pool.

## 3. Detour shortening converges immediately

Replacing path segments by shorter detours found within a small radius:

$$1{,}912 \longrightarrow 415 \longrightarrow 396 \longrightarrow 396$$

The first pass does essentially all the work. On already-short paths one pass
gains $\approx 2\%$, and a larger radius gains $1\%$ more at six times the cost.
Shortening does not recover an optimum from a poor starting path.

## 4. The backward half is independent of the presentation

In bidirectional search the half expanding from the trivial pair $(x, y)$ is
constrained only by the length bound and **never reads the presentation**. Every
presentation of a given size therefore rebuilds an identical state set. This is
directly visible in node counts: the value $7{,}226{,}201$ recurred across four
distinct presentations in one run and again in another. Building that set once
per bound and reusing it reduces each presentation to the cost of its forward
search alone.

The same observation bounds precomputation. One set built at $\ell \leq 40$ with
$2.2 \times 10^7$ states, in $19$ s, contained **2 of the $10{,}115$** pool
presentations. Under a tight bound most moves are rejected, branching is low and
the set reaches deep; under a loose bound branching explodes and $2.2 \times
10^7$ states buy only $\approx 8$–$10$ moves of depth, while the pool lies
$20$–$130$ moves from $(x, y)$. **No single bound is simultaneously wide enough
to contain the pool and tight enough to reach it.**

## 5. Hardness stratification

Grouping the $156$ challenges we hold by the number of teams $k$ sharing the
record:

| $k$ | challenges | median record |
|---:|---:|---:|
| $10$ | $1$ | $8$ |
| $8$ | $48$ | $15$ |
| $3$ | $19$ | $26$ |
| $2$ | $20$ | $26$ (max $48$) |

A record is short and widely shared *precisely because* its optimum is easy to
reach, and long and singly held *precisely because* it is not.

## 6. Competence and point value are anti-correlated

This has a sharp consequence for scoring, which we then confirmed directly. A tie
pays $2^{1-k}$, so matching a record held by one team pays $0.5$ while matching
one shared six ways pays $0.008$. Since the short records are the widely shared
ones, **the records a search can reach are exactly those worth almost nothing.**

Measured with the solver of §1 at $w = 12$ and $1.2 \times 10^7$ states per side:

| target | $k$ | a match pays | result |
|---|---:|---:|---|
| record $\leq 18$ | $6$–$13$ | $\approx 0.008$ | reached reliably |
| record $19$, $k = 6$ | $6$ | $0.008$ | reached |
| record $19$–$30$, $k \leq 2$ | $1$–$2$ | $0.25$–$0.50$ | **0 of 16** |

In records $19$–$30$ alone there are $73$ unheld challenges at $k = 1$ and $45$
at $k = 2$, together about $48$ points, and all of it lies beyond the competence
boundary. Consistently, a search returning exact optima below record $18$
returned nothing on $21$ attempts at records $27$–$40$, nothing on $35$ attempts
at $121$–$300$, and nothing on $17$ attempts above $301$.

This is a stronger statement than "the search is too weak". Solver competence and
point value are anti-correlated *by construction*, so no amount of target
selection within a fixed competence boundary escapes it; only moving the boundary
does.

A practical corollary: improving a heavily shared record is provably futile in
the cases checked. For a presentation with record $8$ shared ten ways, the search
returns $8$ at every slack $s \in [1, 8]$, witnessing optimality. **Zero of $61$**
such attempts yielded an improvement.

## 7. Two further negative results

**The abelianisation test is sound but empty here.** A balanced presentation of
the trivial group satisfies $\det M(P) = \pm 1$ for the exponent-sum matrix
$M(P)$. Zero of the $7{,}266$ solved challenges violate this, confirming the
test — but all $2{,}756$ unsolved challenges already satisfy it. The pool was
evidently pre-filtered.

**The exponent-sum lower bound is admissible and far too weak.** Across
$24{,}080$ matrices its median is $5$ and its maximum $13$, while held records
have median $> 100$. It prunes nothing.

## What remains open

Every method measured is competent exactly where the optimum is short, and the
presentations with long records are precisely those where no method reached any
path at all. That region is where the difficulty of the Discovery Track resides,
and §6 shows it is also where essentially all the point value sits.

A learned search policy is the relevant class of method. As a first probe, a
least-squares estimator of distance to $(x, y)$, fitted on our own record-length
paths, achieved mean absolute error $3.0$ moves against $5.6$ for $\ell(P)$
alone, and reduced node counts roughly twentyfold as an $A^*$ heuristic — but
**did not improve path quality** over the tuned priority of §1. This suggests the
useful policy is not a linear function of simple word statistics.

## Prior work used

- Official SAIR Andrews–Curtis repository,
  https://github.com/SAIRcompetition/Andrews-Curtis — move specification and
  reference verifier, against which every path reported here was checked.
- A. Shehper, A. M. Medina-Mardones, B. Lewis, L. Pinar, S. Gukov et al.,
  *What makes math problems hard for reinforcement learning: a case study*,
  arXiv:2408.15332 — used as a yardstick for greedy baseline coverage and as the
  reference for the learned-policy approach named above.

# Proof Track submission

competition.sair.foundation → Andrews–Curtis → **Proof Track** → Submit. There
is **no Proof Track API**: the competition exposes only `acc` with submission
kind `acc-solutions`, which is the Discovery Track, so this one is submitted
through the web form. Discovery is submitted through the API and nothing here
belongs there.

Submissions opened 11 September 2026; the deadline is **30 November 2026 AoE**.

| Form field | What to enter |
|---|---|
| Conjecture | **AC** |
| Direction | **proof** |
| Description | the block under *Description* below, in full |
| Public GitHub repository link | `https://github.com/Amey-Thakur/SAIR-ANDREWS-CURTIS-CHALLENGE` |
| Git commit hash | the full hash below |
| arXiv or paper link | leave empty until Paper III is announced |
| Sharing agreement | required; tick it |

The direction states what the work aims at, not what it has achieved. This is a
partial result and says so in its first sentence.

**Git commit hash** — the form requires the full hash whenever a repository link
is given. Run `git rev-parse HEAD` for the current value; at the time of writing:

```
COMMIT_HASH_PLACEHOLDER
```

---

## Description

Everything between the two rules goes in the Description field, starting at the
title line. Markdown and math are supported there.

---

# Length as priority, not constraint: search geometry of the Andrews–Curtis Challenge pool

**Amey Thakur** · [ORCID 0000-0001-5644-1575](https://orcid.org/0000-0001-5644-1575)

## Summary

**This is a partial result. It makes no claim about the Andrews–Curtis
conjecture itself, in either direction.** What it reports is a set of
reproducible measurements over the $10{,}115$ balanced presentations of the
Discovery pool which fix how a search for an AC reduction should be structured,
together with a structural obstruction that limits what any search of this
family can score, and one verified non-existence statement at a bounded length.

Write a presentation as $P = \langle x, y \mid r_1, r_2 \rangle$, with total
length $\ell(P) = |r_1| + |r_2|$ and $d(P)$ the number of moves applied. Every
path reported here was replayed by the official reference verifier before it was
counted, and every path submitted to the Discovery Track was replayed again by
the platform.

**What is established.** A hard bound on total relator length is the dominant
design error in this search (§1); the two terms of a length-plus-depth priority
trade off against each other in a way that makes any one setting competent on a
band rather than on the pool (§2); the backward half of a bidirectional search
does not read the presentation, which both permits amortisation and bounds what
precomputation can buy (§4); solver competence and point value are
anti-correlated by construction under a $2^{1-k}$ tie rule (§6); and for one
presentation no AC path of length at most $24$ exists within word cap $42$
(§6b).

**What remains open.** Every method measured here is competent exactly where the
optimum is short, and the presentations with long records are precisely those
where no method reached any path at all. That region holds essentially all of the
point value, and closing it is not a matter of more budget for these
architectures — five of them were measured and all score zero there (§6b, §7).
The relevant class of method is a learned search policy, and the probe reported
at the end of this description was not sufficient.

Code in the linked repository: `runs/pool/` (solvers), `src/` (engine and
verifier), and `runs/campaign_log.md` (the measurement log these figures are
drawn from).

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

| challenge | optimum | $w = 1$ | $w = 4$ | $w = 12$ |
|---|---:|---:|---:|---:|
| `ac-00236` | $15$ | $16$ | $15$ | $15$ |
| `ac-00343` | $15$ | $17$ | $15$ | $15$ |
| `ac-00488` | $14$ | $15$ | $14$ | $14$ |
| `ac-00742` | $10$ | $11$ | $10$ | $10$ |
| `ac-00807` | $14$ | $17$ | $14$ | $14$ |
| `ac-00894` | $14$ | $17$ | $15$ | $14$ |
| `ac-01143` | $16$ | $17$ | $17$ | $16$ |
| `ac-01411` | $11$ | $16$ | $11$ | $11$ |
| `ac-01586` | $13$ | $15$ | $13$ | $13$ |
| `ac-01635` | $8$ | $10$ | $8$ | $8$ |
| **exact** | | $0/10$ | $8/10$ | $\mathbf{10/10}$ |

Every path was replayed by the reference verifier. At $w = 12$ all ten are
solved **at exactly the known optimum**, in $0.4$–$2.6$ s using $2{,}028$ to
$2{,}456{,}933$ states. The capped search needed millions of states and $5$–$25$ s
per presentation to do worse.

The depth charge is what buys exactness, and it is paid for in states: $w = 1$
finds a path in $177$–$858$ states but never the optimum, $w = 4$ takes
$1{,}118$–$80{,}046$ and reaches eight of ten, and $w = 12$ reaches all ten.
Removing the charge entirely leaves length alone to order the queue, which finds
paths very cheaply and far from minimal — $32$ against an optimum of $15$, $129$
against $14$.

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

## 6b. Asking the decision question instead of the optimisation question

Every search above optimises: it works upward from the heuristic estimate and
spends most of its budget on path lengths that could not score even if found.
Only one question pays, and it is binary: **does a path of at most the record
length exist?**

Starting the iterative-deepening bound *at the record* asks exactly that, and
the upper bound needed to make it well posed comes free from the weighted A* of
the previous section. Measured on unheld $k \leq 2$ challenges at records 21 to
30, memory $O(\text{depth})$, budget $1.5 \times 10^8$ states:

| challenge | record | outcome |
|---|---:|---|
| ac-07351 | 24 | space **exhausted** at $7.6 \times 10^7$ states |
| ac-06403 | 22 | budget consumed, undecided |
| ac-02353 | 24 | budget consumed, undecided |

The first line is a genuine, if small, negative result: within the word cap of
42 there is **no Andrews-Curtis path of length at most 24** for that
presentation, and the search terminated by exhaustion rather than by running
out of budget. The same method applied at scale would partition the pool into
challenges provably out of reach at a given length and challenges merely
unreached, which is a sharper object than a leaderboard position.

It does not, however, score. Reformulating the question concentrated the budget
without changing the outcome, which is the fifth search architecture to behave
that way here.

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

## Prior work used, and what is used from it

- **Official SAIR Andrews–Curtis repository**,
  <https://github.com/SAIRcompetition/Andrews-Curtis>. The move specification,
  the challenge data and the reference verifier. Every path reported above was
  replayed by that verifier, and the engine's internal move numbering was checked
  equal to the repository's `core.apply_move` on $38{,}682$ pairs before any
  result here was trusted. The $2^{1-k}$ tie rule of §6 is the competition's own
  scoring rule, taken from its published documentation.
- **J. J. Andrews and M. L. Curtis**, *Free groups and handlebodies*,
  Proceedings of the American Mathematical Society, 1965. The conjecture and the
  move set this work searches over.
- **C. F. Miller III and P. E. Schupp**, *Some presentations of the trivial
  group*, Contemporary Mathematics, 1999. The source of the Miller–Schupp family,
  which makes up part of the Discovery pool alongside the competition's own draw;
  §5 and §6 stratify holdings across both.
- **A. Shehper, A. M. Medina-Mardones, B. Lewis, L. Pinar, S. Gukov and
  co-authors**, *What makes math problems hard for reinforcement learning: a case
  study*, [arXiv:2408.15332](https://arxiv.org/abs/2408.15332). Used two ways:
  as the yardstick for greedy baseline coverage on the Miller–Schupp
  presentations, and as the reference for the learned-policy direction named
  under *What remains open*. Their result that a greedy baseline solves a
  substantial fraction of that family is what made the failure of greedy search
  on this pool worth reporting rather than assuming.
- **I. Pohl**, *Bi-directional search*, Machine Intelligence, 1971, and
  *Heuristic search viewed as path finding in a graph*, Artificial Intelligence,
  1970. The bidirectional formulation of §4 and the weighted-$A^*$ formulation of
  §6 are both standard and are used as given; nothing about either is claimed as
  new here.
- **R. E. Korf**, *Depth-first iterative-deepening: an optimal admissible tree
  search*, Artificial Intelligence, 1985. The memory-free iterative-deepening
  search used in §6b, again used as given.

**What this submission contributes**, as distinct from the above: the
measurements themselves, and five specific findings drawn from them — that the
length cap rather than the budget is what defeats this search (§1), the band
structure that any single priority setting imposes (§2), the
presentation-independence of the backward ball together with the bound on what
precomputing it can buy (§4), the anti-correlation of competence and point value
under the tie rule (§6), and the single verified non-existence statement for
`ac-07351` (§6b). The negative results in §7 and the closing probe are also
original to this work, and are reported because they bound what the approach can
do rather than because they succeeded.

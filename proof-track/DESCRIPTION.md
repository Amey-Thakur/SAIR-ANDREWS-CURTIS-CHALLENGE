# Length as priority, not constraint: search geometry of the Andrews–Curtis Challenge pool

**This is a partial result. It makes no claim about the Andrews–Curtis conjecture in either direction.** It reports reproducible measurements over the $10{,}115$ presentations of the Discovery pool that fix how an AC search should be structured, a structural obstruction limiting what any search of this family can score, and one verified non-existence statement at a bounded length.

Write $P = \langle x, y \mid r_1, r_2 \rangle$, with $\ell(P) = |r_1| + |r_2|$ and $d(P)$ the moves applied. Every path below was replayed by the official reference verifier, and the move numbering checked equal to official `core.apply_move` on $38{,}682$ pairs.

## 1. A hard bound on total length is the dominant design error

Bidirectional search here is naturally written with a cap: reject any state with $\ell(P) > \ell(P_0) + s$. An AC path characteristically *lengthens* relators before they collapse, so the cap excludes exactly the states a short path must cross.

Replacing the cap with an ordering — priority $f(P) = \ell(P) + w \cdot d(P)$, no admission test — changes the outcome. On ten presentations of known optimum at fixed budget:

| challenge | optimum | $w{=}1$ | $w{=}4$ | $w{=}12$ |

|---|---:|---:|---:|---:|

| ac-00236 | 15 | 16 | 15 | 15 |

| ac-00343 | 15 | 17 | 15 | 15 |

| ac-00488 | 14 | 15 | 14 | 14 |

| ac-00742 | 10 | 11 | 10 | 10 |

| ac-00807 | 14 | 17 | 14 | 14 |

| ac-00894 | 14 | 17 | 15 | 14 |

| ac-01143 | 16 | 17 | 17 | 16 |

| ac-01411 | 11 | 16 | 11 | 11 |

| ac-01586 | 13 | 15 | 13 | 13 |

| ac-01635 | 8 | 10 | 8 | 8 |

| **exact** | | 0/10 | 8/10 | **10/10** |

At $w{=}12$ all ten are solved **at exactly the known optimum**, in $0.4$–$2.6$ s using $2{,}028$–$2{,}456{,}933$ states; the capped search needed millions of states and $5$–$25$ s to do worse. The depth charge buys exactness and is paid for in states: $w{=}1$ finds a path in $177$–$858$ states but never the optimum, $w{=}4$ takes $1{,}118$–$80{,}046$ and reaches eight of ten. With no charge, paths are far from minimal — $32$ against optimum $15$, $129$ against $14$.

Widening the cap is no substitute for removing it: at record $91$, slack $2$ returned $95$ and slack $4$ **nothing**. A wider box grows faster than any budget covers.

## 2. The two terms trade off sharply

No single $w$ serves the pool, because $f \geq w \cdot d$ bounds reachable depth. $w{=}12$ solves every record $\leq 16$ exactly and **0 of 35** at record $\geq 121$. $w{=}0$ reaches those but wanders: $1{,}912$ moves against record $121$, $3{,}742$ against $301$. Intermediate $w$ does neither on that band. A search of this form is competent on a *band*, not on a pool. Nor does shortening rescue a poor path: detour replacement converges at once ($1{,}912 \to 415 \to 396 \to 396$) and gains $\approx 2\%$ on short paths.

## 3. The backward half never reads the presentation

In bidirectional search the half expanding from $(x, y)$ is constrained only by the length bound, so every presentation of a given size rebuilds an identical state set. This is directly visible in node counts: $7{,}226{,}201$ recurred across four distinct presentations in one run and again in another. Building the set once per bound reduces each presentation to its forward search alone.

It also bounds precomputation. One set built at $\ell \leq 40$ with $2.2 \times 10^7$ states, in $19$ s, contained **2 of the $10{,}115$** pool presentations. Under a tight bound branching is low and the set reaches deep; under a loose bound $2.2 \times 10^7$ states buy only $\approx 8$–$10$ moves of depth, while the pool lies $20$–$130$ moves from $(x, y)$. **No single bound is both wide enough to contain the pool and tight enough to reach it.**

## 4. Hardness stratification

Grouping the $156$ challenges held by the number of teams $k$ sharing the record: $k{=}10$, 1 challenge, median 8; $k{=}8$, 48, median 15; $k{=}3$, 19, median 26; $k{=}2$, 20, median 26 (max 48). A record is short and widely shared *precisely because* its optimum is easy to reach, and long and singly held *precisely because* it is not.

## 5. Competence and point value are anti-correlated by construction

A tie pays $2^{1-k}$, so matching a record held by one team pays $0.5$ and one shared six ways pays $0.008$. Since the short records are the widely shared ones, **the records a search can reach are exactly those worth almost nothing.** Measured at $w{=}12$, $1.2 \times 10^7$ states per side:

| target | $k$ | a match pays | result |

|---|---:|---:|---|

| record $\leq 18$ | 6–13 | $\approx 0.008$ | reached reliably |

| record 19, $k{=}6$ | 6 | $0.008$ | reached |

| record 19–30, $k \leq 2$ | 1–2 | $0.25$–$0.50$ | **0 of 16** |

In records 19–30 alone there are $73$ unheld challenges at $k{=}1$ and $45$ at $k{=}2$, about $48$ points, all beyond the competence boundary. Consistently: nothing on $21$ attempts at records $27$–$40$, nothing on $35$ at $121$–$300$, nothing on $17$ above $301$.

This is stronger than "the search is too weak". Competence and value are anti-correlated *by construction*, so no target selection within a fixed boundary escapes it; only moving the boundary does. Improving a heavily shared record was also futile in every case checked: for a record-$8$ presentation shared ten ways the search returns $8$ at every slack $s \in [1,8]$, witnessing optimality, and **zero of $61$** such attempts improved anything.

## 5b. The decision question instead of the optimisation question

Every search above optimises, spending most of its budget on lengths that could not score. Only one question pays, and it is binary: **does a path of at most the record length exist?** Starting the iterative-deepening bound *at the record* asks exactly that, with the upper bound coming free from the weighted $A^*$ above. On unheld $k \leq 2$ challenges at records 21–30, memory $O(\text{depth})$, budget $1.5 \times 10^8$ states:

| challenge | record | outcome |

|---|---:|---|

| ac-07351 | 24 | space **exhausted** at $7.6 \times 10^7$ states |

| ac-06403 | 22 | budget consumed, undecided |

| ac-02353 | 24 | budget consumed, undecided |

The first line is a genuine, if small, negative result: **within word cap 42 there is no Andrews–Curtis path of length at most 24 for `ac-07351`**, and the search terminated by exhaustion, not by running out of budget. At scale this would partition the pool into challenges provably out of reach at a given length and those merely unreached — a sharper object than a leaderboard position. It does not score: the fifth architecture here to concentrate its budget without changing the outcome.

## 6. Two further negative results

**The abelianisation test is sound but empty here.** A balanced presentation of the trivial group satisfies $\det M(P) = \pm 1$ for the exponent-sum matrix. Zero of $7{,}266$ solved challenges violate it, confirming the test — but all $2{,}756$ unsolved challenges already satisfy it. The pool was evidently pre-filtered.

**The exponent-sum lower bound is admissible and far too weak.** Across $24{,}080$ matrices its median is $5$ and maximum $13$, while held records have median $> 100$. It prunes nothing.

## What remains open

Every method measured is competent exactly where the optimum is short; the long-record presentations are those where no method reached any path at all. That region holds, by §5, essentially all the point value. Five architectures were measured there — capped bidirectional, best-first with depth weight, weighted $A^*$ on a learned heuristic, IDA\* and decision-mode IDA\* — and all score zero, so more budget will not close it.

A learned search policy is the relevant class of method. As a first probe, a least-squares estimator of distance to $(x,y)$ fitted on record-length paths reached mean absolute error $3.0$ moves against $5.6$ for $\ell(P)$ alone, and cut node counts roughly twentyfold as an $A^*$ heuristic — but **did not improve path quality** over the tuned priority of §1. The useful policy is evidently not linear in simple word statistics.

## Prior work used, and what is used from it

- **Official SAIR Andrews–Curtis repository** (github.com/SAIRcompetition/Andrews-Curtis): move specification, challenge data and reference verifier, against which every path here was replayed. The $2^{1-k}$ tie rule of §5 is the competition's own scoring rule.

- **J. J. Andrews and M. L. Curtis**, *Free groups and handlebodies*, Proc. Amer. Math. Soc., 1965 — the conjecture and the move set searched over.

- **C. F. Miller III and P. E. Schupp**, *Some presentations of the trivial group*, Contemp. Math., 1999 — the Miller–Schupp family, part of the pool that §4 and §5 stratify.

- **A. Shehper, A. M. Medina-Mardones, B. Lewis, L. Pinar, S. Gukov et al.**, *What makes math problems hard for reinforcement learning: a case study*, arXiv:2408.15332 — the yardstick for greedy baseline coverage on Miller–Schupp, and the reference for the learned-policy direction above. Their result that greedy solves a substantial fraction of that family is what made greedy's failure here worth reporting rather than assuming.

- **I. Pohl**, *Bi-directional search* (1971) and *Heuristic search viewed as path finding in a graph* (1970), and **R. E. Korf**, *Depth-first iterative-deepening* (1985) — the bidirectional formulation of §3, the weighted $A^*$ of §5 and the memory-free search of §5b. All used as given; none claimed as new.

**Contribution**: the measurements, and five findings — the length cap not the budget defeats this search (§1); the band structure any single priority setting imposes (§2); the presentation-independence of the backward ball and the bound on what precomputing it buys (§3); the anti-correlation of competence and value under the tie rule (§5); and the non-existence statement for `ac-07351` (§5b). The §6 negatives and the closing probe are also original, reported because they bound the approach.


"""Summarise an arbitrage-band sweep: find rate per visited key, and the ratio
achieved against the ratio the arbitrage actually requires.

The question the sweep answers is not "did we find a path" but "did we find one
short enough that `ac + 2` beats the stable record". Those are different by a
factor of five to eight, and only the second one scores, so both are reported.

Usage (from the repo root):
  python runs/pool/arb_summary.py runs/pool/arb_band.out
"""
import collections
import re
import statistics
import sys

HEAD = re.compile(r"\s+\[(\d+)/(\d+)\]\s+(\S+) record (\d+) \(k (\d+)\) size (\d+)")
FOUND = re.compile(
    r"\s+mode (\d+): found (\d+) -> shortened (\d+) -> with finish (\d+) "
    r"vs record (\d+) \(ratio ([\d.]+)\), required <= (\d+) \(ratio ([\d.]+)\)")
NONE = re.compile(r"\s+mode (\d+): none, ([\d,]+) nodes")


def main(path):
    cur = None
    per = collections.defaultdict(lambda: {"tried": 0, "found": 0,
                                           "ratios": [], "req": [],
                                           "scored": 0, "raw": []})
    for line in open(path, encoding="utf-8", errors="replace"):
        m = HEAD.match(line)
        if m:
            cur = m.group(3)
            continue
        m = FOUND.match(line)
        if m:
            mode = int(m.group(1))
            d = per[mode]
            d["tried"] += 1
            d["found"] += 1
            d["raw"].append(int(m.group(2)))
            d["ratios"].append(float(m.group(6)))
            d["req"].append(float(m.group(8)))
            d["scored"] += int(m.group(4)) <= int(m.group(7))
            continue
        m = NONE.match(line)
        if m:
            per[int(m.group(1))]["tried"] += 1

    names = {0: "plain key (control)", 1: "swap+inversion (lossy)",
             3: "swap (lossless)", 4: "swap+letters (lossless)"}
    print(f"\n  {path}")
    print(f"  {'key':24} {'tried':>6} {'found':>6} {'find rate':>10} "
          f"{'median raw':>11} {'median ratio':>13} {'req ratio':>10} "
          f"{'SCORED':>7}")
    for mode in sorted(per):
        d = per[mode]
        if not d["tried"]:
            continue
        rate = d["found"] / d["tried"]
        mr = statistics.median(d["ratios"]) if d["ratios"] else 0
        mq = statistics.median(d["req"]) if d["req"] else 0
        mraw = statistics.median(d["raw"]) if d["raw"] else 0
        print(f"  {names.get(mode, str(mode)):24} {d['tried']:>6} "
              f"{d['found']:>6} {rate:>9.0%} {mraw:>11,.0f} "
              f"{mr:>13.2f} {mq:>10.2f} {d['scored']:>7}")
    for mode in sorted(per):
        d = per[mode]
        if d["ratios"]:
            print(f"\n  mode {mode} ratio achieved: min {min(d['ratios']):.2f}, "
                  f"median {statistics.median(d['ratios']):.2f}, "
                  f"max {max(d['ratios']):.2f}")
            print(f"  mode {mode} ratio required: min {min(d['req']):.2f}, "
                  f"median {statistics.median(d['req']):.2f}, "
                  f"max {max(d['req']):.2f}")
            gap = [a / b for a, b in zip(d["ratios"], d["req"])]
            print(f"  mode {mode} achieved/required: min {min(gap):.1f}x, "
                  f"median {statistics.median(gap):.1f}x, max {max(gap):.1f}x")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1
                  else "runs/pool/arb_band.out"))

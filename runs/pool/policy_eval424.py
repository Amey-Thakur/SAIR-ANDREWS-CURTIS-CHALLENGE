"""Does the scramble-trained policy agree with the organisers' certified paths?

The network is trained on backward scrambles from (x, y), which is free but is
not the distribution the pool is drawn from.  The 424 certified trivializations
the organisers publish are the only ground truth that exists for this problem,
so replaying them and asking the network for the next move is the one honest
out-of-distribution check available.

Three numbers per path: how often the certified move is the network's first
choice, how often it is in the top three, and how the value head's estimate of
the distance to (x, y) compares with the true remaining length.  A policy that
cannot rank a certified move above the other thirteen cannot guide a search
along one either.

Usage (from the repo root):
  python runs/pool/policy_eval424.py --net runs/pool/policy/net.pt
"""
import argparse
import json
import pathlib
import sys

import numpy as np
import torch

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "runs" / "pool"))
from jit_engine import MAXLEN, _apply  # noqa: E402
from policy_net import ENC, Net, onehot  # noqa: E402
from policy_solve import tokens  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", default="runs/pool/policy/net.pt")
    ap.add_argument("--threads", type=int, default=3)
    args = ap.parse_args()
    torch.set_num_threads(args.threads)

    ck = torch.load(REPO / args.net, map_location="cpu", weights_only=True)
    net = Net(ck["hidden"])
    net.load_state_dict(ck["state"])
    net.eval()

    d = json.load(open(REPO / "runs/official/repo/competition/examples/"
                       "training_424.json", encoding="utf-8"))
    o0 = np.zeros(MAXLEN, dtype=np.int8)
    o1 = np.zeros(MAXLEN, dtype=np.int8)
    buf = np.zeros(MAXLEN, dtype=np.int8)
    tmp = np.zeros(MAXLEN + 2, dtype=np.int8)

    X, Y, R, TOT = [], [], [], []
    truncated = 0
    for it in d["instances"]:
        r0, r1 = it["initial_relators"]
        w0 = np.zeros(MAXLEN, dtype=np.int8)
        w1 = np.zeros(MAXLEN, dtype=np.int8)
        if len(r0) >= MAXLEN or len(r1) >= MAXLEN:
            truncated += 1
            continue
        w0[:len(r0)] = r0
        w1[:len(r1)] = r1
        l0, l1 = len(r0), len(r1)
        n = len(it["moves"])
        bad = False
        for i, m in enumerate(it["moves"]):
            X.append((w0.copy(), l0, w1.copy(), l1))
            Y.append(m)
            R.append(n - i)
            TOT.append(l0 + l1)
            na, nb = _apply(m, w0, l0, w1, l1, o0, o1, buf, tmp)
            if na >= MAXLEN or nb >= MAXLEN:
                bad = True
                break
            w0[:] = 0
            w1[:] = 0
            w0[:na] = o0[:na]
            w1[:nb] = o1[:nb]
            l0, l1 = na, nb
        if bad:
            truncated += 1

    n = len(X)
    w0 = np.stack([x[0] for x in X])
    w1 = np.stack([x[2] for x in X])
    l0 = np.array([x[1] for x in X], dtype=np.int16)
    l1 = np.array([x[3] for x in X], dtype=np.int16)
    y = np.array(Y)
    rem = np.array(R, dtype=np.float32)
    tot = np.array(TOT)
    xt = tokens(w0, l0, w1, l1)

    top1 = top3 = 0
    vmae = 0.0
    with torch.no_grad():
        for i in range(0, n, 8192):
            logits, val = net(onehot(xt[i:i + 8192], "cpu"))
            lg = logits.numpy()
            yb = y[i:i + 8192]
            top1 += int((lg.argmax(1) == yb).sum())
            t3 = np.argpartition(-lg, 3, axis=1)[:, :3]
            top3 += int((t3 == yb[:, None]).any(1).sum())
            vmae += float(np.abs(val.numpy() - rem[i:i + 8192]).sum())

    print(f"states on certified paths: {n:,}  (paths dropped for buffer "
          f"overflow: {truncated})")
    print(f"total relator length on those states: mean {tot.mean():.1f} "
          f"median {np.median(tot):.0f} max {tot.max()}")
    print(f"certified move is top-1: {top1 / n:.3f}   top-3: {top3 / n:.3f}"
          f"   (uniform baseline 0.071 / 0.214)")
    print(f"value head MAE against true moves remaining: {vmae / n:.2f} "
          f"(mean true remaining {rem.mean():.1f})")
    inside = tot <= 44
    print(f"states inside the training cap of 44: {inside.mean():.3f}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Plot the Figure 2 provision-time CDFs from the archived results."""
import argparse
import csv
import glob
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXPECTED = os.path.join(ROOT, "expected")

ALGS = [
    ("kube", "Kube-scheduler", "tab:blue"),
    ("image", "Image Locality", "tab:orange"),
    ("layer", "Layer Locality", "tab:green"),
    ("infra", "Infrastructure Aware", "tab:red"),
]


def cdf(values):
    values = sorted(values)
    n = len(values)
    return values, [(i + 1) / n for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "fig2.png"))
    args = ap.parse_args()

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for folder, label, color in ALGS:
        path = glob.glob(os.path.join(EXPECTED, folder, "*provision_time*.csv"))
        if len(path) != 1:
            raise SystemExit("expected one provision_time file for " + folder)
        with open(path[0]) as f:
            values = [float(r["provision_time"]) for r in csv.DictReader(f, delimiter=";")]
        x, y = cdf(values)
        ax.plot(x, y, label=label, color=color, linewidth=1.8)

    ax.set_xlabel("Provision time (s)")
    ax.set_ylabel("CDF")
    ax.set_title("ISCC 2021: container provision time")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(args.out, dpi=200)
    print(args.out)


if __name__ == "__main__":
    main()

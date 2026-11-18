#!/usr/bin/env python3
"""Run one ISCC 2021 scenario with the paper-era ContainerSim code."""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True,
                    help="scenario JSON, e.g. data/scenarios/kube-scheduler.json")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--reports", nargs="+",
                    default=["provisionTime", "cacheStatus", "containerAllTimes", "hostOccupation"],
                    choices=["provisionTime", "cacheStatus", "containerAllTimes",
                             "hostOccupation", "networkLog", "registryUsage", "timePerApp"])
    args = ap.parse_args()

    scenario = args.scenario if os.path.isabs(args.scenario) else os.path.join(ROOT, args.scenario)
    for d in ("logs", "reports", "images"):
        os.makedirs(os.path.join(ROOT, d), exist_ok=True)

    cmd = [
        sys.executable, os.path.join(ROOT, "code", "main.py"),
        "--file", scenario,
        "--seed", str(args.seed),
        "--reports", *args.reports,
    ]
    print(" ".join(cmd))
    p = subprocess.run(cmd, cwd=ROOT)
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())

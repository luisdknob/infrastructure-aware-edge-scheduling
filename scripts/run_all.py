#!/usr/bin/env python3
"""Run the four ISCC 2021 scheduling scenarios."""
import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCENARIOS = [
    ("kube", "data/scenarios/kube-scheduler.json"),
    ("image", "data/scenarios/image-locality.json"),
    ("layer", "data/scenarios/layer-locality.json"),
    ("infra", "data/scenarios/infrastructure-aware.json"),
]


def run_one(name, scenario, seed, reports):
    cmd = [
        sys.executable, os.path.join(HERE, "run_experiment.py"),
        "--scenario", scenario, "--seed", str(seed),
        "--reports", *reports,
    ]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return name, p.returncode, p.stdout[-1000:], p.stderr[-2000:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--reports", nargs="+",
                    default=["provisionTime", "cacheStatus", "containerAllTimes", "hostOccupation"],
                    choices=["provisionTime", "cacheStatus", "containerAllTimes",
                             "hostOccupation", "networkLog", "registryUsage", "timePerApp"])
    args = ap.parse_args()

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(run_one, name, scen, args.seed, args.reports): name
                   for name, scen in SCENARIOS}
        for future in as_completed(futures):
            name, rc, out, err = future.result()
            print(("OK   " if rc == 0 else "FAIL ") + name)
            if rc != 0:
                print(err)
    print("reports written to", os.path.join(ROOT, "reports"))


if __name__ == "__main__":
    main()

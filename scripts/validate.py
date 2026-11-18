#!/usr/bin/env python3
"""Validate the archived ISCC 2021 results against Table II.

The paper's 99th percentile is the linearly interpolated 99th percentile
(equivalent to numpy.percentile(values, 99)), not the nearest-rank value.
"""
import argparse
import csv
import glob
import json
import os
import statistics
import sys
from zipfile import ZipFile

import bitmath

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXPECTED = os.path.join(ROOT, "expected")
ORIGINAL_LOGS = os.path.join(ROOT, "archive", "iscc-original-logs.zip")

ALGS = [
    ("kube", "Kube-scheduler"),
    ("image", "Image Locality"),
    ("layer", "Layer Locality"),
    ("infra", "Infrastructure Aware"),
]

SCENARIOS = {
    "kube": "kube-scheduler.json",
    "image": "image-locality.json",
    "layer": "layer-locality.json",
    "infra": "infrastructure-aware.json",
}

# Table II: avg, p99, max, cache hit, cache miss, storage min, storage avg,
# storage max, distribution std, distribution min, distribution max,
# used nodes.
PAPER = {
    "kube": (28.03, 207.27, 279.31, 2042, 8169, 9.94, 749.31, 1423.77, 2.57, 2, 12, 168),
    "image": (26.56, 221.84, 279.31, 2618, 7593, 9.94, 701.40, 1266.60, 2.60, 2, 12, 168),
    "layer": (22.20, 192.11, 279.31, 3808, 6403, 9.94, 595.35, 1314.16, 3.09, 2, 16, 168),
    "infra": (13.47, 90.69, 136.04, 3913, 6248, 0.00, 584.31, 1490.30, 5.46, 0, 16, 150),
}


def one(folder, pattern):
    paths = glob.glob(os.path.join(EXPECTED, folder, pattern))
    if len(paths) != 1:
        raise SystemExit("expected exactly one file for %s/%s, found %d" %
                         (folder, pattern, len(paths)))
    return paths[0]


def percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    index = q * (len(values) - 1)
    lo = int(index)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


def provision_metrics(folder):
    path = one(folder, "*provision_time*.csv")
    with open(path) as f:
        values = [float(r["provision_time"]) for r in csv.DictReader(f, delimiter=";")]
    return {
        "prov_n": len(values),
        "prov_avg": statistics.fmean(values),
        "prov_p99": percentile(values, 0.99),
        "prov_max": max(values),
    }


def cache_metrics(folder):
    path = one(folder, "*cache_status*.csv")
    with open(path) as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    return {
        "cache_hit": sum(int(r["hit"]) for r in rows),
        "cache_miss": sum(int(r["miss"]) for r in rows),
    }


def storage_metrics(folder):
    report = os.path.basename(one(folder, "*host_occupation*.csv"))
    trace = report.replace("host_occupation", "network_log").replace(".csv", ".json")
    with ZipFile(ORIGINAL_LOGS) as archive:
        member = archive.getinfo(trace)
        with archive.open(member) as log:
            # The simulator writes the final graph after the event history.
            size = 1024 * 1024
            while True:
                start = max(0, member.file_size - size)
                log.seek(start)
                tail = log.read()
                marker = tail.rfind(b'\n"graph":')
                if marker >= 0:
                    break
                if start == 0:
                    raise ValueError(f"{trace} does not contain a final graph")
                size *= 2
    graph = json.loads(b"{" + tail[marker + 1:])["graph"]
    values = [
        float(sum((bitmath.parse_string(layer[1]) for layer in node["layers"]),
                  bitmath.Byte(0)).to_MB())
        for node in graph["nodes"] if node["type"] == "chost"
    ]
    return {
        "storage_min": min(values),
        "storage_avg": statistics.fmean(values),
        "storage_max": max(values),
    }


def distribution_metrics(folder):
    path = one(folder, "*host_occupation*.csv")
    per_host = {}
    with open(path) as f:
        for row in csv.DictReader(f, delimiter=";"):
            replica = row["name"].split("-sha256")[0]
            per_host.setdefault(row["host"], set()).add(replica)
    # The paper's distribution includes worker nodes with zero replicas.  The
    # host_occupation report only contains used nodes, so read the scenario's
    # chost list too.
    with open(os.path.join(ROOT, "data", "scenarios", SCENARIOS[folder])) as f:
        scenario = json.load(f)
    hosts = [n["name"] for n in scenario["nodes"] if n.get("type") == "chost"]
    counts = [len(per_host.get(host, set())) for host in hosts]
    return {
        "dist_std": statistics.stdev(counts) if len(counts) > 1 else 0.0,
        "dist_min": min(counts),
        "dist_max": max(counts),
        "used_nodes": sum(1 for c in counts if c > 0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="fail on differences greater than 0.05 from the paper values")
    args = ap.parse_args()

    rows = []
    print(f"{'algorithm':22s} {'n':>6s} {'avg':>8s} {'p99':>8s} {'max':>8s} "
          f"{'hit':>6s} {'miss':>6s} {'st_min':>8s} {'st_avg':>8s} {'st_max':>8s}")
    for folder, label in ALGS:
        p = provision_metrics(folder)
        c = cache_metrics(folder)
        s = storage_metrics(folder)
        d = distribution_metrics(folder)
        row = dict(folder=folder, label=label, **p, **c, **s, **d)
        rows.append(row)
        print(f"{label:22s} {p['prov_n']:6d} {p['prov_avg']:8.2f} {p['prov_p99']:8.2f} "
              f"{p['prov_max']:8.2f} {c['cache_hit']:6d} {c['cache_miss']:6d} "
              f"{s['storage_min']:8.2f} {s['storage_avg']:8.2f} {s['storage_max']:8.2f}")

    print("\nPaper Table II comparison:")
    print(f"{'algorithm':22s} {'avg':>8s} {'p99':>8s} {'max':>8s} {'hit':>6s} "
          f"{'miss':>6s} {'st_avg':>8s} {'dist_std':>8s} {'nodes':>6s}")
    for row in rows:
        paper = PAPER[row["folder"]]
        print(f"{row['label']:22s} {row['prov_avg']:8.2f} {row['prov_p99']:8.2f} "
              f"{row['prov_max']:8.2f} {row['cache_hit']:6d} {row['cache_miss']:6d} "
              f"{row['storage_avg']:8.2f} {row['dist_std']:8.2f} {row['used_nodes']:6d}")

    out = os.path.join(EXPECTED, "table2_verified.csv")
    fields = ["folder", "label", "prov_n", "prov_avg", "prov_p99", "prov_max",
              "cache_hit", "cache_miss", "storage_min", "storage_avg",
              "storage_max", "used_nodes", "dist_std", "dist_min", "dist_max",
              "paper_avg", "paper_p99", "paper_max", "paper_hit", "paper_miss",
              "paper_storage_avg", "paper_dist_std", "paper_used_nodes"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for row in rows:
            paper = PAPER[row["folder"]]
            w.writerow({
                "folder": row["folder"], "label": row["label"],
                "prov_n": row["prov_n"], "prov_avg": round(row["prov_avg"], 4),
                "prov_p99": round(row["prov_p99"], 4), "prov_max": round(row["prov_max"], 4),
                "cache_hit": row["cache_hit"], "cache_miss": row["cache_miss"],
                "storage_min": round(row["storage_min"], 4),
                "storage_avg": round(row["storage_avg"], 4),
                "storage_max": round(row["storage_max"], 4),
                "used_nodes": row["used_nodes"],
                "dist_std": round(row["dist_std"], 4),
                "dist_min": row["dist_min"], "dist_max": row["dist_max"],
                "paper_avg": paper[0], "paper_p99": paper[1],
                "paper_max": paper[2], "paper_hit": paper[3],
                "paper_miss": paper[4], "paper_storage_avg": paper[6],
                "paper_dist_std": paper[8], "paper_used_nodes": paper[11],
            })
    print("\nwrote", out)

    if args.strict:
        failed = False
        for row in rows:
            paper = PAPER[row["folder"]]
            checks = [
                ("avg", row["prov_avg"], paper[0]),
                ("p99", row["prov_p99"], paper[1]),
                ("max", row["prov_max"], paper[2]),
                ("hit", row["cache_hit"], paper[3]),
                ("miss", row["cache_miss"], paper[4]),
                ("storage_min", row["storage_min"], paper[5]),
                ("storage_avg", row["storage_avg"], paper[6]),
                ("storage_max", row["storage_max"], paper[7]),
                ("dist_std", row["dist_std"], paper[8]),
                ("dist_min", row["dist_min"], paper[9]),
                ("dist_max", row["dist_max"], paper[10]),
                ("used_nodes", row["used_nodes"], paper[11]),
            ]
            for name, got, want in checks:
                if abs(got - want) > 0.05:
                    print("FAIL %s %s got %s want %s" % (row["folder"], name, got, want),
                          file=sys.stderr)
                    failed = True
        if failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()

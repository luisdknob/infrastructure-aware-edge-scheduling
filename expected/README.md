# Archived ISCC 2021 reports

These four runs provide the per-replica provision-time reports used for Figure 2.

| Folder | Algorithm | Timestamp |
| --- | --- | --- |
| [kube](kube/) | Kube-scheduler | 1622215549 |
| [image](image/) | Image Locality | 1622215867 |
| [layer](layer/) | Layer Locality | 1622350539 |
| [infra](infra/) | Infrastructure Aware | 1622350423 |

Each run includes per-layer timings and destinations (`container_all_times`), per-replica provision times (`provision_time`), per-node cache counts (`cache_status`), and layer sizes by node (`host_occupation`).

## Table II

The provision time is the sum of layer download durations for each replica. The 99th percentile uses linear interpolation. Cache counts come from `cache_status`, and the distribution statistics count replicas across all 168 workers.

The [comparison CSV](table2_verified.csv) is produced by `scripts/validate.py`. It computes storage across all 168 workers from the final graph in each original network trace. The [archived Table II](TABLE_II.md) shows the recalculated values. [Original simulator logs and network traces](../archive/iscc-original-logs.zip)

See the [errata](../ERRATA.md#cache-storage-and-distribution) for the cache and distribution differences between the archive and Table II.

## Provision-Time Verification

Truncating the archived mean provision times to two decimal places reproduces the published means. Elapsed time from arrival to the last layer finishing is a separate measurement available in the layer timing reports.

## Estimator Check

In a separate rerun with seed 1, the printed formula gave a mean provision time of 10.41 s and a mean elapsed time of 18.02 s. With the same seed, the paper version gave 13.50 s and 16.41 s, respectively. Seed 42 showed the same direction. The published results use the estimator from the paper version.

## Source Provenance

[Original source archive](../archive/iscc-original-source.zip)

The archived Infrastructure Aware and Layer Locality scenario files assign weights 5/5/30 to `LeastRequestedPriority`, `SelectorSpreadPriority`, and the respective placement priority. The runnable scenarios use 10/10/30, the weights recorded for both final runs. [Experiment log](experiments.log)

The runnable snapshot defers the Basemap import, reads cache counters from `host["log"]["cache"]`, honors seed 0, and removes the unused `classes/utils.py` module, which imports `containerSim.objects`. The original `cache_status` reporter reads `host["cache"]`, which raises a `KeyError` on this code line.

## Archived Replay

The original runs did not record a scheduler seed. Seeds 1–100 were tested on the full Kube-scheduler scenario. The closest mean was 28.0414 s with seed 14, compared with 28.0385 s in the archive. Its p99 was 217.47 s, compared with 207.27 s in the archive. The run reported 2,041 hits and 8,170 misses, compared with 2,042 and 8,169. The host-occupation storage estimates were 753.26 MB and 749.30 MB.

| Kube-scheduler prefix | Validation against full seed-1 run | Seeds searched against archive | Best match |
| --- | ---: | ---: | --- |
| First 20 lifecycle operations, up to 50 s | 66/66 replicas | 0–100 | Seed 26, 32/66 replicas |
| First 8 lifecycle operations, up to 10 s | 22/22 replicas | 0–1,000 | Seed 936, 15/22 replicas |

Neither search reproduced the archived prefix. In the original code, `if args.seed` skipped seeding when the flag was omitted or set to zero. The scheduler's random sequence also depends on the scenario, Python version, and order of operations.

The full seed-1 Kube run gives a mean of 28.81 s, p99 of 223.30 s, 1,969 cache hits, and a storage estimate of 758.44 MB. The corresponding archived values are 28.04 s, 207.27 s, 2,042 hits, and 749.31 MB.

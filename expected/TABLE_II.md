# Table II — Archived ISCC 2021 results

The results below use the four final archived runs. Each run has 1,250 application replicas. Provision time sums each replica's layer download durations. The 99th percentile uses linear interpolation.

## Provision time and cache

| Algorithm | Mean (s) | p99 (s) | Max (s) | Hits | Misses |
| --- | ---: | ---: | ---: | ---: | ---: |
| Kube-scheduler | 28.03 | 207.27 | 279.31 | 2,042 | 8,169 |
| Image Locality | 26.56 | 221.84 | 279.31 | 2,618 | 7,593 |
| Layer Locality | 22.20 | 192.11 | 279.31 | 3,638 | 6,573 |
| Infrastructure Aware | 13.47 | 90.69 | 136.04 | 3,776 | 6,435 |

## Storage and replica distribution

Storage is measured from the final network graphs across all 168 workers, including workers with zero usage. Time and storage values are truncated to two decimals here to match the paper's convention.

| Algorithm | Min (MB) | Mean (MB) | Max (MB) | Replica count SD | Min replicas | Max replicas | Workers used |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kube-scheduler | 9.94 | 749.31 | 1423.77 | 2.57 | 2 | 12 | 168 |
| Image Locality | 9.94 | 701.40 | 1266.60 | 2.60 | 2 | 12 | 168 |
| Layer Locality | 9.94 | 595.35 | 1314.16 | 2.92 | 2 | 16 | 168 |
| Infrastructure Aware | 0.00 | 584.31 | 1490.30 | 5.54 | 0 | 16 | 150 |

See the [errata](../ERRATA.md#cache-storage-and-distribution) for the differences in cache counts and replica distribution. [Data CSV](table2_verified.csv)

# ISCC 2021 Errata

These corrections refer to the published version of [Improving Container Deployment in Edge Computing Using the Infrastructure Aware Scheduling Algorithm](https://doi.org/10.1109/ISCC53001.2021.9631490).

## Table II

Figure 2 and Table II measure provision time as the sum of the layer download durations for each replica. In Section IV-D.1, 90.69 s, 192.11 s, and 207.27 s are 99th percentiles. The maxima printed in Table II are 136.04 s for Infrastructure Aware and 279.31 s for both Layer Locality and Kube-scheduler.

Using the mean provision times in Table II, the reductions described in Section IV-D.1 are approximately 5% for Image Locality and 21% for Layer Locality relative to Kube-scheduler, and 39% for Infrastructure Aware relative to Layer Locality.

In Section IV-D.2, the Layer Locality mean storage usage should read 595.35 MB, as in Table II.

### Cache, Storage, and Distribution

| Algorithm | Published hits / misses | Final archived hits / misses | Published distribution SD | Final archived distribution SD |
| --- | ---: | ---: | ---: | ---: |
| Layer Locality | 3,808 / 6,403 | 3,638 / 6,573 | 3.09 | 2.92 |
| Infrastructure Aware | 3,913 / 6,248 | 3,776 / 6,435 | 5.46 | 5.54 |

An earlier Layer Locality run matches the published cache counts and distribution standard deviation. The final Layer Locality run matches the published latency and storage metrics. For Infrastructure Aware, the counts printed in Table II imply a 38.51% hit rate. Section IV-D.3 gives 38.31%. The final archived run gives 36.98%. [Archived run comparison](expected/README.md#table-ii)

## Algorithm 1

Algorithm 1, lines 14–15, divides `sum(aL \ mL \ cL)` by the bandwidth. Here `aL` is the set of application layers, `mL` the layers already in the node's download queue, and `cL` the cached layers. This estimates the transfer time for the additional data the application adds to the queue. A layer already waiting in the queue contributes zero even when the application still depends on it.

The paper version uses the union of application layers and queued layers.

```python
total_time = sum((application_layers | messages_layers).values()) / bandwidth
```

Replace lines 5–15 of Algorithm 1 with the following pseudocode to match the paper version.

```text
for each candidate node c:
    mL ← empty map
    for each scheduled application on c:
        for each replica of that application assigned to c:
            for each message m of that replica:
                if m.status ∈ {0, 3, 4, 5}:
                    mL[m.layer_digest] ← m.size − m.transmitted

    layers ← copy(aL)
    for each (digest, remaining) in mL:
        layers[digest] ← remaining

    bw ← configured_bandwidth(c)
    if c.rate ≠ 0:
        bw ← c.rate in the estimator's bandwidth units
    ttInst[c] ← sum(values(layers)) / bw
```

The retained message statuses are scheduled (0), active (3), contained (4), and downloaded (5).

For each queued layer, the paper version uses the remaining bytes. The score can include a cached layer because the estimator does not check the cache.

## Conclusion

These corrections leave the paper’s main conclusion intact. Infrastructure Aware had the lowest mean and 99th-percentile provision times among the four schedulers evaluated. [Recalculated Table II](expected/TABLE_II.md)

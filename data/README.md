# Data

## Scenarios

| File | Algorithm |
|---|---|
| `kube-scheduler.json` | Kube-scheduler |
| `image-locality.json` | Image Locality |
| `layer-locality.json` | Layer Locality |
| `infrastructure-aware.json` | Infrastructure Aware |

The scenario files include the topology, image layers, application definitions, and lifecycle operations.

The Infrastructure Aware and Layer Locality scenarios use the weights `10/10/30` recorded for the final runs. [Experiment log](../expected/experiments.log)

The paper's workload is described in Table I: 28 PoPs, one 100 Mbps server node per PoP, five edge nodes per PoP with 10–60 Mbps links, a 10 Gbps registry, 24 Docker Hub images, 350 applications, and 1,250 replicas.

[Archived results](../expected/README.md)

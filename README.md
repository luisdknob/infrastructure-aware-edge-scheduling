# Improving Container Deployment in Edge Computing Using the Infrastructure Aware Scheduling Algorithm

This repository contains the ContainerSim experiments for ISCC 2021. The study compares Infrastructure Aware, which uses the download queue and available bandwidth to score candidate nodes, with Kube-scheduler, Image Locality, and Layer Locality.

Luis Augusto Dias Knob, Carlos Henrique Kayser, and Tiago Ferreto (2021). *Improving Container Deployment in Edge Computing Using the Infrastructure Aware Scheduling Algorithm*. IEEE Symposium on Computers and Communications. [Paper](https://doi.org/10.1109/ISCC53001.2021.9631490)

## Release Note

> [!NOTE]
> This post-publication release is part of an ongoing effort to improve the reproducibility and verifiability of my research. For this paper, I am making the source code and experimental configurations publicly available. I plan to gradually release artifacts from more of my research projects over time.
>
> I used GPT-6.2 Sol and DeepSeek V4.1 Flash 1017 to help prepare this repository, fix minor execution issues, and review the code and results against the published paper. I kept the code here as close as possible to the implementation used in the original experiments.
>
> I used a random function in the scheduler and didn’t set a seed for the original runs. If you run the experiments again, the overall results can be similar even if containers end up on different nodes and deployment times vary. See [Archived Replay](#archived-replay) for how the new runs compare with the originals.
>
> I documented minor corrections and clarifications in the [errata](ERRATA.md). The results still support the paper’s main conclusions.

## Simulation Scenario

The four scenarios use the 197-node Ipê topology, 24 Docker Hub images, 350 applications, and 1,250 application replicas. The simulator models bandwidth sharing using max-min fairness.

| Algorithm | Scenario file | Additional scheduler priority |
| --- | --- | --- |
| Kube-scheduler | [kube-scheduler.json](data/scenarios/kube-scheduler.json) | — |
| Image Locality | [image-locality.json](data/scenarios/image-locality.json) | `ImageLocalityPriority` |
| Layer Locality | [layer-locality.json](data/scenarios/layer-locality.json) | `LayerLocalityPriority` |
| Infrastructure Aware | [infrastructure-aware.json](data/scenarios/infrastructure-aware.json) | `LeastCongestedNodePriority` |

### Dataset

- The [original source archive](archive/iscc-original-source.zip) includes the paper-era simulator, scenario files, and original analysis scripts.
- The [archived reports](expected/README.md) contain the original layer timings, replica provision times, cache counts, and host occupation for the four final runs.
- The [original logs](archive/iscc-original-logs.zip) contain the four simulator logs and the four network traces used for storage statistics.
- The [scenario files](data/README.md) contain the topology, image layers, application workloads, and scheduler settings. The final Layer Locality and Infrastructure Aware weights are recorded in the [experiment log](expected/experiments.log).
- The [source notes](expected/README.md#source-provenance) describe the scenario weights and compatibility adjustments in the runnable copy.

### Settings and Execution

From the repository root, install the dependencies with Python 3.9.

```bash
python3.9 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the Kube-scheduler scenario with seed 1. A full run takes about 90 seconds on one core.

```bash
python scripts/run_experiment.py \
  --scenario data/scenarios/kube-scheduler.json \
  --seed 1
```

Reports go to `reports/` and simulator logs go to `logs/`. Run all four scenarios with the same seed using the batch runner.

```bash
python scripts/run_all.py --workers 1 --seed 1
```

### Results

Recalculate the archived statistics and regenerate the Figure 2 CDF.

```bash
python scripts/validate.py
python scripts/plot_cdf.py
```

The validator writes the [Table II comparison CSV](expected/table2_verified.csv). The plotter writes `fig2.png`. See the [recalculated Table II](expected/TABLE_II.md) and the [errata](ERRATA.md#table-ii).

### Archived Replay

The [replay notes](expected/README.md#archived-replay) compare a fresh run with the archived results.

## Citation

```bibtex
@inproceedings{knob2021iscc,
  author    = {Dias Knob, Luis Augusto and Kayser, Carlos Henrique and Ferreto, Tiago},
  title     = {Improving Container Deployment in Edge Computing Using the Infrastructure Aware Scheduling Algorithm},
  booktitle = {2021 IEEE Symposium on Computers and Communications (ISCC)},
  year      = {2021},
  doi       = {10.1109/ISCC53001.2021.9631490}
}
```

## License

The code is released under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE).

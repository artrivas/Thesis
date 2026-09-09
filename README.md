# Sensitivity of graph-distribution comparison workflows to structural perturbations

Do representative graph-comparison workflows actually detect controlled changes in
a graph-generating process as the perturbation strength `α` increases?

The experiment is **paired**: for each source graph `G_i` the pipeline builds a
perturbed counterpart `G_i^α` from the same base graph, so distribution-level and
per-pair behaviour can both be measured. Four workflows are compared across four
datasets (three synthetic families plus IMDB-BINARY), six perturbation types, an
α grid from 0 to 1, and 24 seeds.

**Results live in [`results/RESULTS.md`](results/RESULTS.md)** — start there to find
the current run and the figures that belong in the thesis.

## Layout

```
├── src/experimentation/     Python package (pure standard library)
├── tests/                   135 unittest tests
├── scripts/                 dataset fetcher + thesis/poster figure generators
├── docs/experimentation/    protocol, theory, audits, changelog
├── results/                 traceable run directories — see results/RESULTS.md
├── references/              cited papers (PDF)
├── data/                    downloaded datasets (not committed)
└── archive/                 superseded material (not committed)
```

Everything runs **from the repo root**. The package sits under `src/`; nothing else
does.

## Setup

The core package and its SVG figure generator have **no third-party dependencies** —
Python 3.11+ and the standard library are enough to run every experiment and the
test suite. The extras are only for the dashboard and the thesis/poster figures.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[figures,dashboard]"
```

Without an install, prefix commands with `PYTHONPATH=src`.

## Running

```bash
# Full grid into a fresh traceable run directory under results/runs/
python -m experimentation.cli run --config full --console-log

# Small run, for checking the pipeline end to end
python -m experimentation.cli run --config debug --evaluate --figures

# Split a run across machines, then combine the shards
python -m experimentation.cli run --config full --seed-range 0:12
python -m experimentation.cli merge --shard results/runs/<id-a> --shard results/runs/<id-b> \
    --output results/runs/<combined> --evaluate --figures

# Tables and figures from an existing result CSV
python -m experimentation.cli evaluate_results --results results/runs/<id>/results/results.csv
python -m experimentation.cli generate_figures  --results results/runs/<id>/results/results.csv
```

Each run writes its own directory — `results.csv`, `logs/`, `evaluation/`,
`figures/`, and a `run_manifest.json` recording the git commit, config hash, seeds,
host, and library versions. See [`docs/experimentation/traceability.md`](docs/experimentation/traceability.md).

Runs are resumable: re-invoking with `--run-id <id>` picks up from
`logs/checkpoint.json`.

## Real datasets

IMDB-BINARY is fetched, not committed:

```bash
python scripts/fetch_imdb_binary.py
```

## Tests

```bash
python -m unittest discover -s tests -t tests
# or, with pytest installed:
pytest
```

## Dashboard

```bash
streamlit run src/experimentation/dashboard.py
```

It discovers runs under `results/runs/` and defaults to the current merged run.

## What is and is not committed

Result CSVs, logs, and pipeline figures are regenerable and bulky, so they stay out
of git. What *is* tracked: every `run_manifest.json`, the merged run's gzipped
result table (1.1 MB for 20,328 rows), its evaluation tables, and the curated
`figures_final/` and `poster_figures/` sets. The code reads `results.csv.gz`
transparently when the raw CSV is absent, so a fresh clone can regenerate every
figure without re-running the experiments.

## Documentation

| Document | Covers |
|---|---|
| [`theory.md`](docs/experimentation/theory.md) | The scientific question and the four behaviours evaluated |
| [`experimental_protocol.md`](docs/experimentation/experimental_protocol.md) | Datasets → perturbations → workflows → metrics |
| [`results_schema.md`](docs/experimentation/results_schema.md) | Every column in `results.csv` |
| [`traceability.md`](docs/experimentation/traceability.md) | Run directories and the manifest |
| [`parallelism.md`](docs/experimentation/parallelism.md) | Workers, sharding, resume |
| [`seed_sweep.md`](docs/experimentation/seed_sweep.md) | Seed breadth |
| [`failure_map.md`](docs/experimentation/failure_map.md) | Failure-cause taxonomy |
| [`alpha_validation.md`](docs/experimentation/alpha_validation.md) | Why α is a valid strength axis |
| [`implementation_audit.md`](docs/experimentation/implementation_audit.md) | Correctness audits of the workflows |
| [`CHANGELOG.md`](docs/experimentation/CHANGELOG.md) | Work items, newest first |

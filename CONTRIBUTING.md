# Contributing

## Environment

Requires Python 3.11 or 3.12, [`uv`](https://docs.astral.sh/uv/), and Node.js 18 or newer (the dashboard
validation runs the dashboard's measure code in Node).

```bash
make setup      # uv sync --extra dev
make pipeline   # generate, validate, load, dbt build, analytics, dashboard, lint, mypy, pytest
```

## Checks a change must pass

These are the same commands CI runs:

```bash
uv sync --extra dev
make pipeline
uv run pytest
uv run ruff check src tests spark airflow scripts
uv run mypy src
```

| Target | What it does |
|---|---|
| `make setup` | Install locked dependencies including dev tools |
| `make build` | Generate data, validate sources, load DuckDB, run `dbt build` |
| `make dashboard` | Build `dashboard/index.html` and tie every measure to the warehouse |
| `make dashboard-export` | Write the BI CSV exports in `data/exports/` |
| `make dashboard-screenshots` | Recapture `dashboard/screenshots/` (needs Chrome or Chromium) |
| `make test` | Ruff, mypy and pytest with coverage |
| `make clean` | Remove generated data, exports, artifacts and the local warehouse |

## Conventions

- Business logic lives in dbt SQL. Python and JavaScript must not redefine a certified metric.
- A new metric needs a definition in `docs/metric_dictionary.md`, a test, and, if it appears on the
  dashboard, a case in `src/dashboard/validate.py`.
- Never display a roadmap metric. If a mart and test do not exist, the metric does not ship.
- Synthetic-data rules belong in `docs/data_generation_rules.md` with the test that proves them.

"""Loader audit trail and run close-out, on a tiny generated dataset."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import duckdb
import pytest

from src.generation.generate import generate
from src.ingestion.load_duckdb import load
from src.validation.run_audit import close_run


@pytest.fixture()
def warehouse(tmp_path: Path) -> Path:
    config = tmp_path / "config.yml"
    config.write_text(
        "seed: 5\nstart_date: '2024-01-01'\nend_date: '2024-12-31'\naccounts: 20\n"
        "usage_events: 50\nbase_currency: USD\ncurrencies: {USD: 1.0}\n"
    )
    raw = tmp_path / "raw"
    generate(config, raw)
    database = tmp_path / "w.duckdb"
    load(raw, database)
    return database


def test_loader_writes_audit_row_and_loaded_at_on_every_contract_view(warehouse: Path) -> None:
    with duckdb.connect(str(warehouse), read_only=True) as con:
        run = con.execute("select status, source_files, source_rows, length(source_sha256) from audit.pipeline_runs").fetchone()
        assert run is not None and run[0] == "loaded" and run[1] > 20 and run[2] > 0 and run[3] == 64
        views = [r[0] for r in con.execute(
            "select table_name from information_schema.tables where table_schema='raw' and table_type='VIEW'").fetchall()]
        assert views
        for view in views:
            columns = {r[0] for r in con.execute(f'describe raw."{view}"').fetchall()}
            assert "_loaded_at" in columns, view


def _evidence(path: Path, statuses: list[str]) -> Path:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["status"])
        writer.writeheader()
        writer.writerows({"status": s} for s in statuses)
    return path


def _results(path: Path, statuses: list[str]) -> Path:
    path.write_text(json.dumps({"results": [{"status": s} for s in statuses]}))
    return path


def test_close_run_marks_a_healthy_run_passed(warehouse: Path, tmp_path: Path) -> None:
    summary = close_run(warehouse, _results(tmp_path / "r.json", ["pass", "success"]), _evidence(tmp_path / "e.csv", ["pass"] * 3))
    assert summary["status"] == "passed" and summary["dbt"] == "2/2" and summary["dashboard"] == "3/3"
    with duckdb.connect(str(warehouse), read_only=True) as con:
        row = con.execute("select status, finished_at is not null, dbt_resources_total from audit.pipeline_runs").fetchone()
    assert row == ("passed", True, 2)


def test_close_run_marks_any_failure_failed(warehouse: Path, tmp_path: Path) -> None:
    summary = close_run(warehouse, _results(tmp_path / "r.json", ["pass", "error"]), _evidence(tmp_path / "e.csv", ["pass", "FAIL"]))
    assert summary["status"] == "failed"

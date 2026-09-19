"""Validate the portable metric contract in metrics/semantic_layer.yml against the warehouse.

For every governed metric this module checks the contract fields, computes the metric from its source model
with the contract's own SQL, compares it month by month with the reference mart column where one exists, and
checks the metric's bounds. It also writes docs/metric_dictionary.md from the contract, so the human-readable
dictionary cannot drift from the definitions that are tested.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import yaml

CONTRACT = Path("metrics/semantic_layer.yml")
REQUIRED = ["id", "name", "version", "business_question", "owner_role", "description", "grain", "source_model",
            "calculation", "numerator", "denominator", "inclusions", "exclusions", "valid_dimensions", "time_basis",
            "refresh_expectation", "quality_checks", "known_limits"]
TOLERANCE = 0.005


def load_contract(path: Path = CONTRACT) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def contract_problems(contract: dict[str, Any], dbt_models: set[str]) -> list[str]:
    problems = []
    metrics = contract["metrics"]
    ids = [m.get("id") for m in metrics]
    names = [m.get("name") for m in metrics]
    for label, values in (("id", ids), ("name", names)):
        dupes = sorted({v for v in values if values.count(v) > 1})
        if dupes:
            problems.append(f"duplicate metric {label}: {dupes}")
    models = {m["name"]: m for m in contract["semantic_models"]}
    for m in metrics:
        missing = [f for f in REQUIRED if m.get(f) in (None, "", [])]
        if missing:
            problems.append(f"{m.get('id')}: missing {missing}")
        if m.get("semantic_model") not in models:
            problems.append(f"{m.get('id')}: unknown semantic model {m.get('semantic_model')}")
        if m.get("source_model") not in dbt_models:
            problems.append(f"{m.get('id')}: source model {m.get('source_model')} is not a dbt model")
    return problems


def dbt_model_names(root: Path = Path("dbt/models")) -> set[str]:
    return {p.stem for p in root.rglob("*.sql")}


def compute(con: duckdb.DuckDBPyConnection, contract: dict[str, Any]) -> pd.DataFrame:
    """Every metric computed from its semantic model with the contract SQL, one row per month (or one total)."""
    models = {m["name"]: m for m in contract["semantic_models"]}
    frames = []
    for metric in contract["metrics"]:
        sm = models[metric["semantic_model"]]
        relation, time = sm["model"], sm["time_dimension"]
        if time:
            sql = (f"select date_trunc('month', {time})::date as month_start, {metric['sql']} as value "
                   f"from {relation} group by 1 order by 1")
        else:
            sql = f"select null::date as month_start, {metric['sql']} as value from {relation}"
        frame = con.execute(sql).df()
        frame.insert(0, "metric_id", metric["id"])
        frames.append(frame)
    out = pd.concat(frames, ignore_index=True)
    out["value"] = out["value"].astype(float)
    return out


def validate(con: duckdb.DuckDBPyConnection, contract: dict[str, Any]) -> pd.DataFrame:
    """One row per metric and month: contract value, reference mart value, and whether they tie and stay in bounds."""
    values = compute(con, contract)
    rows = []
    for metric in contract["metrics"]:
        mine = values[values["metric_id"] == metric["id"]]
        ref = metric.get("reference")
        reference = None
        if ref:
            reference = con.execute(f"select month_start::date as month_start, {ref['column']}::double as ref "
                                    f"from {ref['model']}").df().set_index("month_start")["ref"]
        low, high = (metric.get("bounds") or [None, None])
        for r in mine.itertuples():
            ref_value = None if reference is None else reference.get(r.month_start)
            ties = True if reference is None else (
                (pd.isna(r.value) and pd.isna(ref_value)) or ref_value is not None and abs(float(r.value) - float(ref_value)) <= TOLERANCE)
            in_bounds = pd.isna(r.value) or ((low is None or r.value >= low - 1e-9) and (high is None or r.value <= high + 1e-9))
            rows.append({"metric_id": metric["id"], "month_start": r.month_start, "contract_value": r.value,
                         "reference_value": ref_value, "ties_to_reference": bool(ties), "within_bounds": bool(in_bounds)})
    return pd.DataFrame(rows)


def dictionary_markdown(contract: dict[str, Any]) -> str:
    lines = ["# Metric dictionary", "",
             "> Synthetic data from a seeded generator. Not real company, customer or financial results.", "",
             f"Generated from `metrics/semantic_layer.yml` (contract version {contract['contract_version']}) by "
             "`python -m src.validation.semantic_layer`. That file is a portable metric contract shaped like a dbt "
             "Semantic Layer spec; it is validated against the marts by this project, not executed by MetricFlow. "
             "The broader catalog, including backlog definitions, is in [metric_backlog.md](metric_backlog.md) and "
             "`dbt/metrics.yml`. Change rules: [metric governance](metric_governance.md).", ""]
    for m in contract["metrics"]:
        ref = m.get("reference")
        lines += [f"## {m['name']}", "",
                  f"- **ID and version:** `{m['id']}` v{m['version']}" + (" (headline KPI)" if m.get("headline") else ""),
                  f"- **Business question:** {m['business_question']}",
                  f"- **Owner role:** {m['owner_role']}",
                  f"- **Description:** {m['description']}",
                  f"- **Grain:** {m['grain']}",
                  f"- **Source model:** `{m['source_model']}` (semantic model `{m['semantic_model']}`)",
                  f"- **Calculation:** `{m['calculation']}`",
                  f"- **Numerator:** {m['numerator']}",
                  f"- **Denominator:** {m['denominator']}",
                  f"- **Inclusions:** {m['inclusions']}",
                  f"- **Exclusions:** {m['exclusions']}",
                  f"- **Valid dimensions:** {', '.join(m['valid_dimensions'])}",
                  f"- **Time basis:** {m['time_basis']}",
                  f"- **Refresh expectation:** {m['refresh_expectation']}",
                  f"- **Quality checks:** {', '.join(m['quality_checks'])}",
                  "- **Tie-out:** " + (f"`{ref['model']}.{ref['column']}`" if ref else "contract value is the reference; Tableau and Excel tie to it"),
                  f"- **Known limits:** {m['known_limits']}", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/warehouse/subscription.duckdb"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/semantic_layer_validation.csv"))
    parser.add_argument("--dictionary", type=Path, default=Path("docs/metric_dictionary.md"))
    args = parser.parse_args()
    contract = load_contract()
    problems = contract_problems(contract, dbt_model_names())
    with duckdb.connect(str(args.database), read_only=True) as con:
        result = validate(con, contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    args.dictionary.write_text(dictionary_markdown(contract), encoding="utf-8")
    failed = result[~(result["ties_to_reference"] & result["within_bounds"])]
    print(f"{len(result) - len(failed)} of {len(result)} metric-months tie and stay in bounds; "
          f"{len(problems)} contract problems")
    for p in problems:
        print("  " + p)
    if len(failed):
        print(failed.to_string(index=False))
    return 1 if problems or len(failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())

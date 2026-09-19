"""The portable metric contract: structure, tie-outs to the marts, bounds, and the failure cases it must catch."""

from __future__ import annotations

import copy
from pathlib import Path

import duckdb
import pytest

from src.validation.semantic_layer import (
    compute,
    contract_problems,
    dbt_model_names,
    dictionary_markdown,
    load_contract,
    validate,
)

DB = Path("data/warehouse/subscription.duckdb")
needs_db = pytest.mark.skipif(not DB.exists(), reason="warehouse not built")
CONTRACT = load_contract()


def test_contract_has_every_required_field_and_real_models() -> None:
    assert contract_problems(CONTRACT, dbt_model_names()) == []


def test_duplicate_metric_names_are_rejected() -> None:
    broken = copy.deepcopy(CONTRACT)
    broken["metrics"].append(copy.deepcopy(broken["metrics"][0]))
    assert any("duplicate metric" in p for p in contract_problems(broken, dbt_model_names()))


def test_missing_source_model_is_rejected() -> None:
    broken = copy.deepcopy(CONTRACT)
    broken["metrics"][0]["source_model"] = "fct_that_does_not_exist"
    assert any("not a dbt model" in p for p in contract_problems(broken, dbt_model_names()))


def test_headline_kpis_are_in_the_contract() -> None:
    headline = {m["id"] for m in CONTRACT["metrics"] if m.get("headline")}
    assert {"ending_mrr", "net_new_mrr", "gross_revenue_retention", "net_revenue_retention", "active_customers",
            "failed_payment_exposure", "reconciliation_variance", "exception_count"} <= headline


def test_generated_dictionary_matches_the_contract() -> None:
    assert Path("docs/metric_dictionary.md").read_text(encoding="utf-8") == dictionary_markdown(CONTRACT)


@needs_db
def test_every_metric_ties_to_its_mart_and_stays_in_bounds() -> None:
    with duckdb.connect(str(DB), read_only=True) as con:
        result = validate(con, CONTRACT)
    assert result["ties_to_reference"].all(), result[~result["ties_to_reference"]]
    assert result["within_bounds"].all(), result[~result["within_bounds"]]


@needs_db
def test_mrr_bridge_variance_is_exactly_zero_every_month() -> None:
    with duckdb.connect(str(DB), read_only=True) as con:
        worst = con.execute("select max(abs(reconciliation_difference)) from analytics_revenue.mart_mrr_bridge").fetchone()[0]
    assert float(worst) == 0.0


@pytest.fixture()
def scratch(tmp_path):
    """A writable copy of the marts the contract reads, for tamper tests."""
    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    con.execute(f"attach '{DB}' as src (read_only)")
    for schema, table in [("analytics_revenue", "fct_mrr_movement"), ("analytics_revenue", "mart_mrr_bridge"),
                          ("analytics_revenue", "mart_revenue_kpis"), ("analytics_finance", "fct_billing_reconciliation"),
                          ("analytics_finance", "mart_finance_exceptions")]:
        con.execute(f"create schema if not exists {schema}")
        con.execute(f"create table {schema}.{table} as select * from src.{schema}.{table}")
    yield con
    con.close()


@needs_db
def test_a_bridge_that_does_not_roll_forward_is_caught(scratch) -> None:
    month = scratch.execute("select max(month_start) from analytics_revenue.fct_mrr_movement").fetchone()[0]
    scratch.execute("update analytics_revenue.fct_mrr_movement set closing_mrr = closing_mrr + 100 "
                    "where month_start = ? and customer_id = (select min(customer_id) from analytics_revenue.fct_mrr_movement "
                    "where month_start = ?)", [month, month])
    result = validate(scratch, CONTRACT)
    assert not result[result["metric_id"] == "ending_mrr"]["ties_to_reference"].all()


@needs_db
def test_retention_outside_bounds_is_caught(scratch) -> None:
    month = scratch.execute("select max(month_start) from analytics_revenue.fct_mrr_movement").fetchone()[0]
    scratch.execute("update analytics_revenue.fct_mrr_movement set churned_mrr = churned_mrr + 100000000 where month_start = ?", [month])
    result = validate(scratch, CONTRACT)
    grr = result[result["metric_id"] == "gross_revenue_retention"]
    assert not grr["within_bounds"].all()


@needs_db
def test_invoice_arithmetic_mismatch_is_caught(scratch) -> None:
    scratch.execute("update analytics_finance.fct_billing_reconciliation set total_amount = total_amount + 10 "
                    "where invoice_id = (select min(invoice_id) from analytics_finance.fct_billing_reconciliation)")
    result = validate(scratch, CONTRACT)
    assert not result[result["metric_id"] == "reconciliation_variance"]["within_bounds"].all()


@needs_db
def test_zero_opening_mrr_gives_an_empty_ratio_not_zero(scratch) -> None:
    first = scratch.execute("select min(month_start) from analytics_revenue.fct_mrr_movement").fetchone()[0]
    values = compute(scratch, CONTRACT)
    grr = values[(values["metric_id"] == "gross_revenue_retention") & (values["month_start"] == first)]["value"]
    assert grr.isna().all()

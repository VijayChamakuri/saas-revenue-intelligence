"""Build the Tableau package: governed extracts, the packaged four-dashboard workbook, expected KPIs and a tie-out.

Extracts come only from the tested marts, the metric contract and the model-score artifact; never from raw
generator output. The workbook XML is written by ``src/tableau/twb.py`` and packaged with one Hyper extract per
data source. Publishing to Tableau Public is a manual step (docs/tableau_public_release.md).

Run: ``python -m src.tableau.build``.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import yaml

from src.tableau.twb import (
    Box,
    Column,
    Dashboard,
    Datasource,
    Filter,
    FilterAction,
    Legend,
    ParamControl,
    Parameter,
    Pill,
    QuickFilter,
    Sheet,
    Text,
    View,
    Workbook,
)
from src.validation.semantic_layer import compute, load_contract

TITLE = "SaaS Revenue Intelligence | MRR, Retention & Billing Controls"
WORKBOOK_FILE = "saas_revenue_intelligence.twbx"
BANNER = "Synthetic data from a seeded generator. Not real company, customer or financial results."
MONEY = 'c"$"#,##0'
PCT = "p0.0%"
NUM = "n#,##0"
THRESHOLDS = [round(x / 100, 2) for x in range(1, 21)]  # 0.01 to 0.20; model scores sit in this range
DEFAULT_THRESHOLD = 0.04  # the threshold selected on the calibration split (artifacts/modeling/churn_metrics.json)
SCORE = "logistic_regression_risk"
CAPTIONS: dict[str, tuple[str, str | None]] = {
    "month_start": ("Period", None), "expansion_mrr": ("Expansion MRR", MONEY), "churned_mrr": ("Churned MRR", MONEY),
    "new_mrr": ("New MRR", MONEY), "contraction_mrr": ("Contraction MRR", MONEY), "reactivation_mrr": ("Reactivation MRR", MONEY),
    "opening_mrr": ("Opening MRR", MONEY), "billed_amount": ("Billed amount", MONEY), "month_label": ("Month label", None), "closing_mrr": ("Ending MRR", MONEY), "arr": ("ARR", MONEY),
    "net_new_mrr": ("Net new MRR", MONEY), "gross_revenue_retention": ("Gross revenue retention", PCT),
    "net_revenue_retention": ("Net revenue retention", PCT), "active_customers": ("Active customers", NUM),
    "churned_customers": ("Churned customers", NUM), "failed_payment_exposure": ("Failed-payment exposure", MONEY),
    "billed_amount": ("Billed amount", MONEY), "reconciliation_variance": ("Reconciliation variance", "c\"$\"#,##0.00"),
    "exception_count": ("Billing exceptions", NUM), "component": ("MRR component", None), "value": ("MRR", MONEY),
    "segment": ("Segment", None), "plan_name": ("Plan", None), "acquisition_channel": ("Acquisition channel", None),
    "cohort_month": ("Acquisition cohort", None), "months_since_start": ("Months since start", NUM),
    "logo_retention": ("Logo retention", PCT), "net_dollar_retention": ("Net dollar retention", PCT),
    "account_id": ("Account (synthetic ID)", None), "risk": ("Churn risk score", "p0.0%"),
    "risk_bucket": ("Risk score band", None), "accounts": ("Accounts", NUM), "churned": ("Churned within 90 days", NUM),
    "decile": ("Risk decile (1 = highest)", None), "churn_rate": ("Observed churn rate", PCT), "lift": ("Lift", "n0.00"),
    "threshold": ("Risk threshold", "p0%"), "precision": ("Precision", PCT), "recall": ("Recall", PCT),
    "queue_size": ("Accounts in queue", NUM), "invoiced": ("Invoiced", MONEY), "paid": ("Paid", MONEY),
    "refunded": ("Refunded", MONEY), "recognized": ("Recognized", MONEY), "deferred": ("Deferred", MONEY),
    "variance": ("Tie-out variance", "c\"$\"#,##0.00"), "exception_type": ("Exception class", None),
    "severity": ("Severity", None), "invoice_id": ("Invoice (synthetic ID)", None), "customer_id": ("Customer (synthetic ID)", None),
    "invoice_date": ("Invoice date", None), "check": ("Control", None), "status": ("Status", None), "detail": ("Detail", None),
}
COMPONENT_LABELS = {"opening_mrr": "Opening", "new_mrr": "New", "expansion_mrr": "Expansion", "reactivation_mrr": "Reactivation",
                    "contraction_mrr": "Contraction", "churned_mrr": "Churned", "closing_mrr": "Ending"}
DISALLOWED = {"customer_name", "account_name", "email", "phone"}


# ---- extracts ------------------------------------------------------------------------------------------

def extracts(con: duckdb.DuckDBPyConnection, scores: pd.DataFrame) -> dict[str, pd.DataFrame]:
    q = lambda sql: con.execute(sql).df()  # noqa: E731
    contract = load_contract()
    values = compute(con, contract)
    monthly = values.dropna(subset=["month_start"]).pivot(index="month_start", columns="metric_id", values="value")
    kpi = monthly.rename(columns={"ending_mrr": "closing_mrr", "logo_churn": "churned_customers"}).reset_index()
    exception_total = float(values.loc[values["metric_id"] == "exception_count", "value"].iloc[0])
    kpi["exception_count"] = exception_total
    kpi["month_start"] = pd.to_datetime(kpi["month_start"]).dt.date.astype(str)
    kpi.insert(1, "month_label", kpi["month_start"].str[:7])
    out: dict[str, pd.DataFrame] = {"kpi_monthly": kpi}
    out["mrr_bridge_long"] = q("""
        select month_start::varchar as month_start, component, component_order, value from (
            unpivot (select month_start, opening_mrr, new_mrr, expansion_mrr, reactivation_mrr,
                            -contraction_mrr as contraction_mrr, -churned_mrr as churned_mrr, closing_mrr
                     from analytics_revenue.mart_mrr_bridge)
            on opening_mrr, new_mrr, expansion_mrr, reactivation_mrr, contraction_mrr, churned_mrr, closing_mrr
            into name component value value)
        join (values ('opening_mrr', 1), ('new_mrr', 2), ('expansion_mrr', 3), ('reactivation_mrr', 4),
                     ('contraction_mrr', 5), ('churned_mrr', 6), ('closing_mrr', 7)) o(component, component_order)
        using (component) order by month_start, component_order""")
    out["mrr_bridge_long"]["value"] = out["mrr_bridge_long"]["value"].astype(float)
    out["mrr_bridge_long"]["component"] = out["mrr_bridge_long"]["component"].map(COMPONENT_LABELS)
    out["mrr_bridge_long"].insert(1, "month_label", out["mrr_bridge_long"]["month_start"].str[:7])
    out["mrr_by_segment"] = q("""
        select m.month_start::varchar as month_start, c.segment, p.plan_name, c.acquisition_channel,
               sum(m.opening_mrr)::double as opening_mrr, sum(m.new_mrr)::double as new_mrr,
               sum(m.expansion_mrr)::double as expansion_mrr, sum(m.reactivation_mrr)::double as reactivation_mrr,
               sum(m.contraction_mrr)::double as contraction_mrr, sum(m.churned_mrr)::double as churned_mrr,
               sum(m.closing_mrr)::double as closing_mrr
        from analytics_revenue.fct_mrr_movement m
        join analytics_core.dim_customer c using (customer_id)
        join analytics_core.dim_plan p using (plan_id)
        group by all order by 1, 2, 3, 4""")
    out["cohort_retention"] = q("""
        select cohort_month::varchar as cohort_month, months_since_start, cohort_customers, active_customers,
               logo_retention::double as logo_retention, net_dollar_retention::double as net_dollar_retention
        from analytics_growth.mart_cohort_retention order by 1, 2""")
    accounts = q("select account_id, any_value(segment) as segment from analytics_core.dim_customer group by 1")
    latest = scores[scores["as_of_date"] == scores["as_of_date"].max()].merge(accounts, on="account_id", how="left")
    out["risk_queue"] = latest.assign(risk=latest[SCORE].astype(float), churned=latest["churned_within_90d"].astype(int))[
        ["account_id", "as_of_date", "segment", "risk", "churned"]].sort_values("risk", ascending=False)
    out["risk_thresholds"] = risk_thresholds(scores)
    out["risk_lift"] = risk_lift(scores)
    out["risk_distribution"] = risk_distribution(scores)
    out["billing_monthly"] = q("""
        select date_trunc('month', invoice_date)::date::varchar as month_start, count(*) as invoices,
               sum(total_amount)::double as invoiced, sum(successful_payments)::double as paid,
               sum(failed_payment_exposure)::double as failed_payment_exposure, sum(refunded_amount)::double as refunded,
               sum(recognized_amount)::double as recognized, sum(deferred_amount)::double as deferred,
               round(sum(total_amount) - sum(successful_payments) - sum(failed_payment_exposure), 2)::double as variance
        from analytics_finance.fct_billing_reconciliation group by 1 order by 1""")
    out["exceptions"] = q("""
        select e.invoice_id, e.exception_type, e.severity, b.invoice_date::varchar as invoice_date, b.customer_id,
               b.total_amount::double as billed_amount
        from analytics_finance.mart_finance_exceptions e
        left join analytics_finance.fct_billing_reconciliation b using (invoice_id) order by e.exception_type, e.invoice_id""")
    out["controls"] = controls(con, out)
    for name, frame in out.items():
        bad = DISALLOWED & {c.lower() for c in frame.columns}
        if bad:
            raise ValueError(f"extract {name} contains personal fields: {sorted(bad)}")
    return out


def risk_thresholds(scores: pd.DataFrame) -> pd.DataFrame:
    """Precision, recall and queue size at each threshold, on the held-out test rows."""
    rows = []
    for t in THRESHOLDS:
        chosen = scores[scores[SCORE] >= t]
        positives = int(scores["churned_within_90d"].sum())
        hits = int(chosen["churned_within_90d"].sum())
        rows.append({"threshold": t, "queue_size": len(chosen),
                     "precision": hits / len(chosen) if len(chosen) else None,
                     "recall": hits / positives if positives else None})
    return pd.DataFrame(rows)


def risk_lift(scores: pd.DataFrame) -> pd.DataFrame:
    ranked = scores.sort_values(SCORE, ascending=False).reset_index(drop=True)
    ranked["decile"] = (ranked.index * 10 // len(ranked) + 1).astype(int)
    base = ranked["churned_within_90d"].mean()
    out = ranked.groupby("decile").agg(accounts=("account_id", "size"), churned=("churned_within_90d", "sum")).reset_index()
    out["churn_rate"] = out["churned"] / out["accounts"]
    out["lift"] = out["churn_rate"] / base
    out["decile"] = out["decile"].map(lambda d: f"D{d:02d}")
    return out


def risk_distribution(scores: pd.DataFrame) -> pd.DataFrame:
    edges = [0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.075, 0.10, 1.0]
    labels = ["0-1%", "1-2%", "2-3%", "3-4%", "4-5%", "5-7.5%", "7.5-10%", "10%+"]
    bucket = pd.cut(scores[SCORE], bins=edges, labels=labels, include_lowest=True)
    out = scores.assign(risk_bucket=bucket).groupby("risk_bucket", observed=False).agg(
        accounts=("account_id", "size"), churned=("churned_within_90d", "sum")).reset_index()
    out["risk_bucket"] = out["risk_bucket"].astype(str)
    return out


def controls(con: duckdb.DuckDBPyConnection, out: dict[str, pd.DataFrame]) -> pd.DataFrame:
    bridge_breaks = int(con.execute("select count(*) from analytics_revenue.mart_mrr_bridge "
                                    "where abs(reconciliation_difference) > 0.005").fetchone()[0])  # type: ignore[index]
    max_invoice = con.execute("select max(invoice_date) from analytics_finance.fct_billing_reconciliation").fetchone()[0]  # type: ignore[index]
    variance_months = int((out["billing_monthly"]["variance"].abs() > 0.005).sum())
    rows = [
        {"check": "MRR bridge rolls forward", "status": "PASS" if bridge_breaks == 0 else "FAIL",
         "detail": f"{bridge_breaks} months with a bridge difference above half a cent"},
        {"check": "Invoice tie-out (billed = paid + failed exposure)", "status": "PASS" if variance_months == 0 else "FAIL",
         "detail": f"{variance_months} months with a variance"},
        {"check": "Finance exception queue", "status": "REVIEW",
         "detail": f"{len(out['exceptions'])} invoice-rule pairs queued for review"},
        {"check": "Data freshness", "status": "INFO", "detail": f"latest invoice date {max_invoice}; static seeded dataset"},
    ]
    return pd.DataFrame(rows)


def expected_kpis(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    kpi = frames["kpi_monthly"]
    fields = ["closing_mrr", "net_new_mrr", "gross_revenue_retention", "net_revenue_retention", "active_customers",
              "failed_payment_exposure", "reconciliation_variance", "exception_count"]
    long = kpi.melt(id_vars="month_start", value_vars=fields, var_name="field", value_name="expected_value")
    long["tableau_sheet"] = long["field"].map(lambda f: "KPI " + CAPTIONS[f][0])
    return long.sort_values(["month_start", "field"])


# ---- workbook ------------------------------------------------------------------------------------------

def _ds(key: str, caption: str, frame: pd.DataFrame, calcs: list[Column] | None = None,
        strings: tuple[str, ...] = (), dates: tuple[str, ...] = (), dims: tuple[str, ...] = ()) -> Datasource:
    cols = []
    for name, dtype in frame.dtypes.items():
        n = str(name)
        if n in dates:
            dt = "date"
        elif n in strings:
            dt = "string"
        elif pd.api.types.is_bool_dtype(dtype):
            dt = "boolean"
        elif pd.api.types.is_integer_dtype(dtype):
            dt = "integer"
        elif pd.api.types.is_float_dtype(dtype):
            dt = "real"
        else:
            dt = "string"
        cap = CAPTIONS.get(n)
        role = "dimension" if dt in ("string", "date", "boolean") or n in dims else "measure"
        cols.append(Column(n, dt, role=role, caption=cap[0] if cap else None,
                           fmt=cap[1] if cap and dt in ("integer", "real") else None,
                           type="ordinal" if n in dims else ""))
    return Datasource(key, caption, "Data/Extracts", f"{key}.hyper", cols, calcs or [])


def build_workbook(frames: dict[str, pd.DataFrame], refresh: str) -> Workbook:
    months = list(frames["kpi_monthly"]["month_label"])
    month = Parameter("month_param", "Month", "string", months[-1], members=months)
    threshold = Parameter("threshold_param", "Risk threshold", "real", DEFAULT_THRESHOLD, members=list[object](THRESHOLDS), fmt="p0%")
    wb = Workbook(TITLE, params=[month, threshold])
    in_month = Column("in_selected_month", "boolean", role="dimension", caption="In selected month",
                      formula="[month_label] = [Parameters].[month_param]")
    kpi = _ds("kpi_monthly", "KPIs by month", frames["kpi_monthly"], [in_month], dates=("month_start",))
    bridge = _ds("mrr_bridge_long", "MRR bridge", frames["mrr_bridge_long"], [in_month], dates=("month_start",),
                 dims=("component_order",))
    seg = _ds("mrr_by_segment", "MRR by segment", frames["mrr_by_segment"], dates=("month_start",))
    cohort = _ds("cohort_retention", "Cohort retention", frames["cohort_retention"], dims=("months_since_start",))
    queue = _ds("risk_queue", "Risk queue", frames["risk_queue"], [
        Column("above_threshold", "boolean", role="dimension", caption="At or above threshold",
               formula="[risk] >= [Parameters].[threshold_param]")], strings=("as_of_date",))
    thr = _ds("risk_thresholds", "Threshold tradeoff", frames["risk_thresholds"], [
        Column("selected_threshold", "boolean", role="dimension", caption="Selected threshold",
               formula="ABS([threshold] - [Parameters].[threshold_param]) < 0.0001")], dims=("threshold",))
    lift = _ds("risk_lift", "Lift by decile", frames["risk_lift"])
    dist = _ds("risk_distribution", "Risk distribution", frames["risk_distribution"])
    bill = _ds("billing_monthly", "Billing tie-out", frames["billing_monthly"], dates=("month_start",))
    exc = _ds("exceptions", "Finance exceptions", frames["exceptions"], strings=("invoice_date",))
    ctl = _ds("controls", "Controls and freshness", frames["controls"])
    wb.datasources = [kpi, bridge, seg, cohort, queue, thr, lift, dist, bill, exc, ctl]
    sel = Filter("in_selected_month", ["true"])

    def tile(field: str, title: str, ds: Datasource = kpi, filters: list[Filter] | None = None) -> Sheet:
        return Sheet(f"KPI {CAPTIONS[field][0]}", ds, "Text", text=[Pill(field, "Sum")], filters=filters or [sel],
                     title=title, label_text="{v}", font_size=20)

    s = [tile("closing_mrr", "Ending MRR"), tile("net_new_mrr", "Net new MRR"),
         tile("gross_revenue_retention", "Gross revenue retention"), tile("net_revenue_retention", "Net revenue retention"),
         tile("active_customers", "Active customers"), tile("exception_count", "Billing exceptions to review"),
         tile("failed_payment_exposure", "Failed-payment exposure, selected month"),
         tile("reconciliation_variance", "Reconciliation variance, selected month")]
    s.append(Sheet("MRR bridge", bridge, "Bar", cols=[Pill("component")], rows=[Pill("value", "Sum")],
                   color=Pill("component"), label=[Pill("value", "Sum")], filters=[sel],
                   sort=(Pill("component"), Pill("component_order", "Sum"), "ASC"),
                   title="MRR bridge for the selected month: opening + new + expansion + reactivation - contraction - churn = ending"))
    s.append(Sheet("Ending MRR trend", kpi, "Line", cols=[Pill("month_start", "Month-Trunc")], rows=[Pill("closing_mrr", "Sum")],
                   mark_color="#1f3a5f", title="Ending MRR by month"))
    s.append(Sheet("MRR movement by month", bridge, "Bar", cols=[Pill("month_start", "Month-Trunc")], rows=[Pill("value", "Sum")],
                   color=Pill("component"), filters=[Filter("component", ["New", "Expansion", "Reactivation",
                                                                          "Contraction", "Churned"])],
                   title="MRR movement by month (contraction and churn shown below zero)"))
    s.append(Sheet("Retention trend", kpi, "Line", cols=[Pill("month_start", "Month-Trunc")],
                   rows=[Pill("gross_revenue_retention", "Sum"), Pill("net_revenue_retention", "Sum")],
                   mark_color="#2a9d8f", title="Gross and net revenue retention by month"))
    s.append(Sheet("Movement by segment", seg, "Bar", rows=[Pill("segment")],
                   cols=[Pill("expansion_mrr", "Sum"), Pill("churned_mrr", "Sum")],
                   filters=[Filter("plan_name", group=41), Filter("acquisition_channel", group=42),
                            Filter("month_start", derivation="Year", group=43)],
                   title="Expansion and churned MRR by segment (filters: plan, channel, year)"))
    s.append(Sheet("Cohort logo retention", cohort, "Square", rows=[Pill("cohort_month")], cols=[Pill("months_since_start")],
                   color=Pill("logo_retention", "Avg"),
                   title="Logo retention by acquisition cohort and months since start"))
    s.append(Sheet("Risk distribution", dist, "Bar", cols=[Pill("risk_bucket")], rows=[Pill("accounts", "Sum")],
                   label=[Pill("accounts", "Sum")], mark_color="#1f3a5f", title="Accounts by churn risk score band (test rows)"))
    s.append(Sheet("Lift by decile", lift, "Bar", cols=[Pill("decile")], rows=[Pill("lift", "Sum")],
                   label=[Pill("lift", "Sum")], mark_color="#2a9d8f",
                   title="Lift: observed churn rate by risk decile over the base rate (1.0 = no better than random)"))
    s += [Sheet("KPI Precision", thr, "Text", text=[Pill("precision", "Sum")], filters=[Filter("selected_threshold", ["true"])],
                title="Precision at threshold", label_text="{v}", font_size=20),
          Sheet("KPI Recall", thr, "Text", text=[Pill("recall", "Sum")], filters=[Filter("selected_threshold", ["true"])],
                title="Recall at threshold", label_text="{v}", font_size=20),
          Sheet("KPI Queue size", thr, "Text", text=[Pill("queue_size", "Sum")], filters=[Filter("selected_threshold", ["true"])],
                title="Accounts in queue (test rows)", label_text="{v}", font_size=20)]
    s.append(Sheet("Risk action queue", queue, "Text", rows=[Pill("account_id"), Pill("segment")], text=[Pill("risk", "Sum")],
                   filters=[Filter("above_threshold", ["true"])], sort=(Pill("account_id"), Pill("risk", "Sum"), "DESC"),
                   title="Action queue: latest scores at or above the threshold (synthetic IDs)", fit="fit-width"))
    s.append(Sheet("Billing tie-out", bill, "Bar", cols=[Pill("month_start", "Month-Trunc")],
                   rows=[Pill("invoiced", "Sum"), Pill("paid", "Sum")], mark_color="#1f3a5f",
                   title="Invoiced and paid by month"))
    s.append(Sheet("Tie-out variance", bill, "Line", cols=[Pill("month_start", "Month-Trunc")], rows=[Pill("variance", "Sum")],
                   mark_color="#c0392b", title="Invoiced - paid - failed exposure (must be zero)"))
    s.append(Sheet("Failed-payment exposure trend", bill, "Bar", cols=[Pill("month_start", "Month-Trunc")],
                   rows=[Pill("failed_payment_exposure", "Sum")], mark_color="#e8a33d", title="Failed-payment exposure by invoice month"))
    s.append(Sheet("Exception classes", exc, "Bar", rows=[Pill("exception_type")], cols=[Pill("invoice_id", "CountD")],
                   label=[Pill("invoice_id", "CountD")], color=Pill("severity"),
                   title="Exception classes (select a bar to list its invoices)"))
    s.append(Sheet("Exception rows", exc, "Text", rows=[Pill("invoice_id"), Pill("exception_type"), Pill("invoice_date")],
                   text=[Pill("billed_amount", "Sum")], title="Exception invoices (synthetic IDs)", fit="fit-width"))
    s.append(Sheet("Control status", ctl, "Text", rows=[Pill("check"), Pill("status"), Pill("detail")],
                   text=[Pill("check", "CountD")], title="Reconciliation status and data freshness", fit="fit-width"))
    wb.sheets = s

    def header(title: str, sub: str) -> Box:
        return Box("vert", [Text(title, 16, True, "#1f3a5f"), Text(BANNER, 10, True, "#9c0006"),
                            Text(sub, 9, False, "#555555")], [4, 2, 2])

    foot = f"Source: dbt marts (DuckDB). {refresh}. Definitions: docs/metric_dictionary.md (metrics/semantic_layer.yml)."
    reset = Text("Reset: set Month to the latest month and use Revert on the toolbar.", 8, False, "#555555")

    def month_ctrl() -> ParamControl:
        return ParamControl("month_param", "compact", "Month")

    wb.dashboards = [
        Dashboard("Executive overview", 1366, 768, Box("vert", [
            header("Executive overview", "What changed: December 2025 churn is concentrated on the last day of the data window. "
                   "Why: likely cancellation dating at the window edge. Action: confirm dating before reporting it as behavior."),
            Box("horz", [month_ctrl(), reset], [1, 4]),
            Box("horz", [View("KPI Ending MRR"), View("KPI Net new MRR"), View("KPI Gross revenue retention"),
                         View("KPI Net revenue retention"), View("KPI Active customers"), View("KPI Billing exceptions")]),
            Box("horz", [View("MRR bridge"), View("Ending MRR trend")], [1, 1]),
            Text(foot, 8, False, "#555555")], [9, 3, 7, 27, 2])),
        Dashboard("Revenue and retention", 1366, 768, Box("vert", [
            header("Revenue and retention", "GRR excludes expansion and is bounded at 100%. NRR can exceed 100%."),
            Box("horz", [QuickFilter("Movement by segment", "plan_name"), QuickFilter("Movement by segment", "acquisition_channel"),
                         QuickFilter("Movement by segment", "month_start", derivation="Year"),
                         Legend("MRR movement by month", "component")], [1, 1, 1, 2]),
            Box("horz", [View("MRR movement by month"), View("Retention trend")], [3, 2]),
            Box("horz", [View("Movement by segment"), View("Cohort logo retention")], [2, 3]),
            Text(foot, 8, False, "#555555")], [9, 4, 16, 16, 2])),
        Dashboard("Customer risk", 1366, 768, Box("vert", [
            header("Customer risk", "Prioritization aid, not automated action. The model is weak (test ROC-AUC 0.63): "
                   "use lift and the queue size to decide how many accounts Customer Success can contact."),
            Box("horz", [ParamControl("threshold_param", "compact", "Risk threshold"), View("KPI Precision"), View("KPI Recall"),
                         View("KPI Queue size")], [2, 1, 1, 1]),
            Box("horz", [View("Risk distribution"), View("Lift by decile"), View("Risk action queue")], [1, 1, 1]),
            Text(foot, 8, False, "#555555")], [9, 7, 30, 2])),
        Dashboard("Finance controls", 1366, 768, Box("vert", [
            header("Finance controls", "Invoices must equal successful payments plus unpaid failed exposure. "
                   "Exceptions are a review queue; all current exceptions trace to invoice dating in the generator."),
            Box("horz", [Box("vert", [month_ctrl(), View("KPI Failed-payment exposure")], [2, 5]),
                         Box("vert", [Text(" ", 8), View("KPI Reconciliation variance")], [2, 5]), View("Control status")], [1, 1, 3]),
            Box("horz", [View("Billing tie-out"), View("Tie-out variance"), View("Failed-payment exposure trend")]),
            Box("horz", [View("Exception classes"), View("Exception rows")], [1, 1]),
            Text(foot, 8, False, "#555555")], [9, 9, 14, 14, 2])),
    ]
    wb.actions = [FilterAction("Show invoices for the selected exception class", "Finance controls", "Exception classes",
                               ["Exception rows"], "exception_type")]
    return wb


def calculated_fields_doc(wb: Workbook) -> str:
    lines = ["# Calculated fields and parameters", "", f"> {BANNER}", "",
             "Generated by `python -m src.tableau.build` from the workbook specification. These are the exact formulas "
             "in `tableau/workbook/saas_revenue_intelligence.twbx`.", "", "## Parameters", "",
             "| Parameter | Type | Values | Default |", "|---|---|---|---|"]
    for p in wb.params:
        values = f"{len(p.members)} values, {p.members[0]} to {p.members[-1]}" if p.members else ""
        lines.append(f"| {p.caption} | {p.datatype} | {values} | {p.value} |")
    lines += ["", "## Calculated fields", "", "| Data source | Field | Formula |", "|---|---|---|"]
    for d in wb.datasources:
        for c in d.calcs:
            lines.append(f"| {d.caption} | {c.caption or c.name} | `{c.formula}` |")
    return "\n".join(lines) + "\n"


def manifest(wb: Workbook) -> dict[str, Any]:
    return {"workbook_title": wb.title, "file": f"tableau/workbook/{WORKBOOK_FILE}",
            "tableau_version_tested": "Tableau Public 2026.2.2 (macOS, Apple silicon)",
            "size": {"width": 1366, "height": 768, "mode": "fixed"}, "parameters": [p.caption for p in wb.params],
            "data_sources": [{"name": d.caption, "extract": d.hyper_path, "csv": f"tableau/data/{d.key}.csv"} for d in wb.datasources],
            "worksheets": [s.name for s in wb.sheets],
            "dashboards": [{"name": d.name, "worksheets": d.sheet_names()} for d in wb.dashboards],
            "actions": [{"name": a.name, "dashboard": a.dashboard, "source": a.source, "targets": a.targets} for a in wb.actions]}


def hyper_tieout(twbx: Path, expected: pd.DataFrame) -> pd.DataFrame:
    from tableauhyperapi import Connection, HyperProcess, Telemetry

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(twbx) as z:
            z.extract("Data/Extracts/kpi_monthly.hyper", tmp)
        with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, parameters={"log_config": ""}) as hp:
            with Connection(hp.endpoint, str(Path(tmp) / "Data/Extracts/kpi_monthly.hyper")) as con:
                rows = []
                for r in expected.itertuples():
                    got = con.execute_scalar_query(
                        f'SELECT SUM("{r.field}") FROM "Extract"."Extract" WHERE "month_start" = DATE \'{r.month_start}\'')
                    value = float(got) if got is not None else float("nan")
                    exp = float(r.expected_value)
                    ok = (pd.isna(value) and pd.isna(exp)) or abs(value - exp) <= 0.005
                    rows.append({"month_start": r.month_start, "field": r.field, "tableau_sheet": r.tableau_sheet,
                                 "expected_value": exp, "extract_value": value, "passed": bool(ok)})
    return pd.DataFrame(rows)


def build_package(database: Path, scores_csv: Path, target: Path) -> Path:
    with duckdb.connect(str(database), read_only=True) as con:
        frames = extracts(con, pd.read_csv(scores_csv))
    data = target / "data"
    if data.exists():
        shutil.rmtree(data)
    data.mkdir(parents=True)
    for name, frame in frames.items():
        frame.to_csv(data / f"{name}.csv", index=False)
    expected = expected_kpis(frames)
    expected.to_csv(target / "expected_kpis.csv", index=False)
    wb = build_workbook(frames, f"Data through {frames['kpi_monthly']['month_start'].max()[:7]}")
    (target / "workbook").mkdir(parents=True, exist_ok=True)
    twbx = target / "workbook" / WORKBOOK_FILE
    with tempfile.TemporaryDirectory() as tmp:
        wb.package(twbx, {d.key: data / f"{d.key}.csv" for d in wb.datasources}, Path(tmp))
    (target / "calculated_fields.md").write_text(calculated_fields_doc(wb), encoding="utf-8")
    (target / "workbook_manifest.yml").write_text("# Generated by python -m src.tableau.build.\n"
                                                  + yaml.safe_dump(manifest(wb), sort_keys=False), encoding="utf-8")
    (target / "field_dictionary.md").write_text(field_dictionary(frames), encoding="utf-8")
    hyper_tieout(twbx, expected).to_csv(target / "validation_evidence.csv", index=False)
    return target


def field_dictionary(frames: dict[str, pd.DataFrame]) -> str:
    contract = {m["tableau_field"]: m for m in load_contract()["metrics"]}
    lines = ["# Field dictionary", "", f"> {BANNER}", "",
             "Generated by `python -m src.tableau.build`. Definitions for KPI fields come from `metrics/semantic_layer.yml`.", ""]
    for name, frame in frames.items():
        lines += [f"## {name}", "", f"{len(frame):,} rows.", "", "| Field | Caption | Definition |", "|---|---|---|"]
        for column in frame.columns:
            c = str(column)
            lines.append(f"| `{c}` | {CAPTIONS.get(c, (c, None))[0]} | {contract[c]['description'] if c in contract else ''} |")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/warehouse/subscription.duckdb"))
    parser.add_argument("--scores", type=Path, default=Path("artifacts/modeling/churn_scores.csv"))
    parser.add_argument("--output", type=Path, default=Path("tableau"))
    args = parser.parse_args()
    print(build_package(args.database, args.scores, args.output))

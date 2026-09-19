"""Tie every dashboard measure back to the warehouse and write the QA evidence file.

The dashboard's own measure code (dashboard/measures.js) is run in Node against the exported
payload. Each result is compared with a total recomputed here from warehouse SQL or pandas.
Any variance above tolerance fails the run.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from src.dashboard.payload import CHURN_SCORES, RISK_MODEL, WAREHOUSE, build_payload

EVIDENCE = Path("dashboard/validation_evidence.csv")
CURRENCY_TOLERANCE = 0.01
RATIO_TOLERANCE = 1e-6


@dataclass
class Case:
    page: str
    measure: str
    filter: dict[str, Any] = field(default_factory=dict)
    kind: str = "currency"  # currency | ratio | count


def _month(ym: str) -> str:
    return f"{ym}-01"


class Warehouse:
    """Independent recomputation of each measure straight from marts and source scores."""

    def __init__(self, database: Path, scores: Path) -> None:
        self.con = duckdb.connect(str(database), read_only=True)
        churn = pd.read_csv(scores)
        snap = self.con.execute(
            "select account_id, as_of_date::varchar as as_of_date, mrr from raw.model_churn_snapshots"
        ).df()
        merged = churn.merge(snap, on=["account_id", "as_of_date"], validate="1:1")
        self.risk = merged.rename(columns={f"{RISK_MODEL}_risk": "risk"})

    def one(self, sql: str, params: list[Any] | None = None) -> float:
        row = self.con.execute(sql, params or []).fetchone()
        if row is None or row[0] is None:
            raise LookupError(f"no result for {sql[:80]}")
        return float(row[0])

    def movement(self, column: str, f: dict[str, Any]) -> float:
        clauses, params = ["m.month_start = ?"], [_month(f["month"])]
        for key, col in (("segment", "c.segment"), ("plan", "pl.plan_name"),
                         ("product", "pr.product_name"), ("customerId", "m.customer_id")):
            if f.get(key):
                clauses.append(f"{col} = ?")
                params.append(f[key])
        sql = f"""
            select coalesce(sum({column}), 0) from analytics_revenue.fct_mrr_movement m
            left join analytics_core.dim_customer c using (customer_id)
            left join analytics_core.dim_plan pl using (plan_id)
            left join analytics_core.dim_product pr on m.product_id = pr.product_id
            where {' and '.join(clauses)}"""
        return self.one(sql, params)

    def ratio(self, name: str, f: dict[str, Any]) -> float:
        opening = self.movement("m.opening_mrr", f)
        expansion = self.movement("m.expansion_mrr + m.reactivation_mrr", f)
        loss = self.movement("m.contraction_mrr + m.churned_mrr", f)
        if opening == 0:
            return float("nan")  # retention is undefined without opening MRR
        if name == "nrr":
            return (opening + expansion - loss) / opening
        return (opening - loss) / opening

    def cash(self, column: str, ym: str | None) -> float:
        where, params = ("", [])
        if ym:
            where, params = "where date_trunc('month', invoice_date) = ?", [_month(ym)]
        return self.one(
            f"select coalesce(sum({column}), 0) from analytics_finance.fct_billing_reconciliation {where}",
            params,
        )

    def risk_metrics(self, threshold: float) -> dict[str, float]:
        frame = self.risk
        flagged = frame[frame["risk"] >= threshold]
        tp = int(flagged["churned_within_90d"].sum())
        positives = int(frame["churned_within_90d"].sum())
        fp = len(flagged) - tp
        value = tp * (6000 * 0.18 - 35) - fp * 35
        latest = frame.sort_values("as_of_date").groupby("account_id").tail(1)
        return {
            "risk_scored": float(len(frame)),
            "risk_flagged": float(len(flagged)),
            "risk_true_positives": float(tp),
            "risk_precision": tp / len(flagged) if len(flagged) else float("nan"),
            "risk_recall": tp / positives,
            "risk_exposed_mrr": float(flagged["mrr"].sum()),
            "risk_net_value": float(value),
            "risk_queue_accounts": float((latest["risk"] >= threshold).sum()),
        }

    def expected(self, case: Case) -> float:
        m, f = case.measure, case.filter
        col = {"closing_mrr": "m.closing_mrr", "new_mrr": "m.new_mrr",
               "expansion_mrr": "m.expansion_mrr", "contraction_mrr": "m.contraction_mrr",
               "churned_mrr": "m.churned_mrr", "reactivation_mrr": "m.reactivation_mrr",
               "opening_mrr": "m.opening_mrr"}
        if m in col:
            return self.movement(col[m], f)
        if m == "arr":
            return self.movement("m.closing_mrr", f) * 12
        if m == "net_new_mrr":
            return self.movement(
                "m.new_mrr + m.expansion_mrr + m.reactivation_mrr - m.contraction_mrr - m.churned_mrr",
                f,
            )
        if m in ("nrr", "grr"):
            return self.ratio(m, f)
        if m == "bridge_variance":
            return self.movement(
                "m.opening_mrr + m.new_mrr + m.expansion_mrr + m.reactivation_mrr "
                "- m.contraction_mrr - m.churned_mrr - m.closing_mrr", f)
        cash = {"cash_collected": "net_collected_cash", "invoiced": "total_amount",
                "failed_payment_exposure": "failed_payment_exposure",
                "refunded": "refunded_amount", "recognized": "recognized_amount",
                "deferred": "deferred_amount"}
        if m in cash:
            return self.cash(cash[m], f["month"])
        if m == "tie_out_variance":
            return (self.cash("total_amount", f["month"]) - self.cash("successful_payments", f["month"])
                    - self.cash("failed_payment_exposure", f["month"]))
        if m.startswith("conflicts_"):
            base = """from analytics_staging.stg_invoices i
                join analytics_staging.stg_subscriptions s using (subscription_id)
                join analytics_staging.stg_contracts k using (contract_id) where """
            where = {
                "conflicts_before_contract_start": "i.invoice_date < k.contract_start_date",
                "conflicts_same_month_as_start": "i.invoice_date < k.contract_start_date and "
                "date_trunc('month', i.invoice_date) = date_trunc('month', k.contract_start_date)",
                "conflicts_after_contract_end": "i.invoice_date > k.contract_end_date",
            }[m]
            return self.one(f"select count(*) {base} {where}")
        if m in ("cancellations_in_latest_month", "cancellations_on_last_day"):
            last = "(select max(end_date) from analytics_staging.stg_subscriptions where status = 'canceled')"
            cond = (f"end_date = {last}" if m == "cancellations_on_last_day"
                    else f"date_trunc('month', end_date) = date_trunc('month', {last})")
            return self.one(f"select count(*) from analytics_staging.stg_subscriptions where status = 'canceled' and {cond}")
        if m == "cash_collected_total":
            return self.cash("net_collected_cash", None)
        if m == "invoiced_total":
            return self.cash("total_amount", None)
        if m == "failed_payment_exposure_total":
            return self.one("select sum(failed_payment_exposure) from analytics_finance.fct_billing_reconciliation where status <> 'paid'")
        if m == "failed_payment_attempts":
            return self.one("select count(*) from analytics_finance.fct_billing_reconciliation where status <> 'paid'")
        if m.startswith("exception_"):
            clauses, params = ["1=1"], []
            if f.get("severity", "all") != "all":
                clauses.append("e.severity = ?")
                params.append(f["severity"])
            if f.get("rule", "all") != "all":
                clauses.append("e.exception_type = ?")
                params.append(f["rule"])
            where = " and ".join(clauses)
            if m == "exception_records":
                return self.one(f"select count(*) from analytics_finance.mart_finance_exceptions e where {where}", params)
            if m == "exception_invoices":
                return self.one(f"select count(distinct invoice_id) from analytics_finance.mart_finance_exceptions e where {where}", params)
            return self.one(
                f"""select coalesce(sum(r.total_amount), 0) from analytics_finance.fct_billing_reconciliation r
                    where r.invoice_id in (select invoice_id from analytics_finance.mart_finance_exceptions e where {where})""",
                params)
        if m.startswith("cohort_"):
            column = {"cohort_logo_retention": "logo_retention", "cohort_customers": "cohort_customers",
                      "cohort_ndr": "net_dollar_retention"}[m]
            return self.one(
                f"select {column} from analytics_growth.mart_cohort_retention where cohort_month = ? and months_since_start = ?",
                [_month(f["cohort"]), f["age"]])
        if m.startswith("risk_"):
            return self.risk_metrics(f["threshold"])[m]
        raise KeyError(m)


def cases() -> list[Case]:
    out: list[Case] = []
    for ym in ("2025-12", "2025-06", "2023-01"):
        for measure in ("closing_mrr", "arr", "net_new_mrr", "churned_mrr"):
            out.append(Case("Executive Overview", measure, {"month": ym}))
        for measure in ("nrr", "grr"):
            if ym != "2023-01":  # no opening MRR in the first month
                out.append(Case("Executive Overview", measure, {"month": ym}, "ratio"))
    out += [
        Case("Executive Overview", "cash_collected", {"month": "2025-12"}),
        Case("Executive Overview", "cash_collected_total"),
        Case("Executive Overview", "exception_exposure", {}),
        Case("Executive Overview", "exception_invoices", {}, "count"),
        Case("Executive Overview", "failed_payment_exposure_total"),
        Case("Executive Overview", "failed_payment_attempts", {}, "count"),
        Case("Executive Overview", "cancellations_in_latest_month", {}, "count"),
        Case("Executive Overview", "cancellations_on_last_day", {}, "count"),
        Case("Finance Controls", "conflicts_before_contract_start", {}, "count"),
        Case("Finance Controls", "conflicts_same_month_as_start", {}, "count"),
        Case("Finance Controls", "conflicts_after_contract_end", {}, "count"),
    ]
    slices = [
        {"month": "2025-12", "segment": "enterprise"},
        {"month": "2025-12", "segment": "smb", "plan": "Growth"},
        {"month": "2025-06", "plan": "Growth"},
        {"month": "2024-12", "product": "Workflow Automation"},
        {"month": "2025-12", "segment": "mid-market", "product": "Core Analytics", "plan": "Starter"},
        {"month": "2025-12", "customerId": "C000844"},
    ]
    for f in slices:
        for measure in ("closing_mrr", "new_mrr", "expansion_mrr", "contraction_mrr", "churned_mrr",
                        "bridge_variance"):
            out.append(Case("Revenue & Retention", measure, f))
        out += [Case("Revenue & Retention", "nrr", f, "ratio"), Case("Revenue & Retention", "grr", f, "ratio")]
    for cohort, age in (("2023-01", 12), ("2024-03", 6), ("2025-01", 0)):
        cell: dict[str, Any] = {"cohort": cohort, "age": age}
        out += [
            Case("Revenue & Retention", "cohort_customers", cell, "count"),
            Case("Revenue & Retention", "cohort_logo_retention", cell, "ratio"),
            Case("Revenue & Retention", "cohort_ndr", cell, "ratio"),
        ]
    for threshold in (0.02, 0.04, 0.10):
        limit: dict[str, Any] = {"threshold": threshold}
        for measure in ("risk_scored", "risk_flagged", "risk_true_positives", "risk_queue_accounts"):
            out.append(Case("Customer Risk", measure, limit, "count"))
        for measure in ("risk_precision", "risk_recall"):
            out.append(Case("Customer Risk", measure, limit, "ratio"))
        out += [Case("Customer Risk", "risk_exposed_mrr", limit), Case("Customer Risk", "risk_net_value", limit)]
    for ym in ("2025-12", "2024-06"):
        for measure in ("invoiced", "cash_collected", "failed_payment_exposure", "refunded",
                        "recognized", "deferred", "tie_out_variance"):
            out.append(Case("Finance Controls", measure, {"month": ym}))
    for f in ({"severity": "all", "rule": "all"}, {"severity": "medium", "rule": "contract_date_conflict"},
              {"severity": "high", "rule": "all"}):
        out.append(Case("Finance Controls", "exception_records", f, "count"))
        out.append(Case("Finance Controls", "exception_exposure", f))
    return out


def _filter_text(f: dict[str, Any]) -> str:
    return "; ".join(f"{k}={v}" for k, v in f.items()) or "none"


def run_node(payload_path: Path, cases_path: Path) -> list[float | None]:
    script = Path(__file__).with_name("evaluate.js")
    done = subprocess.run(
        ["node", str(script), str(payload_path), str(cases_path)],
        capture_output=True, text=True, check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(f"Node evaluation failed: {done.stderr.strip()}")
    return json.loads(done.stdout)


def validate(database: Path, scores: Path, output: Path) -> list[dict[str, Any]]:
    payload = build_payload(database, scores)
    payload_text = json.dumps(payload, separators=(",", ":"))
    run_id = hashlib.sha256(payload_text.encode()).hexdigest()[:12]
    case_list = cases()
    warehouse = Warehouse(database, scores)
    with tempfile.TemporaryDirectory() as tmp:
        payload_path, cases_path = Path(tmp, "payload.json"), Path(tmp, "cases.json")
        payload_path.write_text(payload_text)
        cases_path.write_text(json.dumps([{"measure": c.measure, "filter": c.filter} for c in case_list]))
        reported = run_node(payload_path, cases_path)
    rows: list[dict[str, Any]] = []
    for case, report in zip(case_list, reported, strict=True):
        expected = warehouse.expected(case)
        tolerance = RATIO_TOLERANCE if case.kind == "ratio" else (0.0 if case.kind == "count" else CURRENCY_TOLERANCE)
        if report is None and expected != expected:  # both undefined, e.g. no opening MRR
            variance, ok = 0.0, True
        elif report is None:
            variance, ok = float("nan"), False
        else:
            variance = report - expected
            ok = abs(variance) <= tolerance + 1e-12
        rows.append({
            "run_id": run_id, "page": case.page, "measure": case.measure,
            "filter": _filter_text(case.filter), "warehouse_total": "n/a" if expected != expected else f"{expected:.6f}",
            "report_total": "n/a" if report is None else f"{report:.6f}",
            "variance": f"{variance:.6f}", "tolerance": tolerance,
            "status": "pass" if ok else "FAIL",
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=WAREHOUSE)
    parser.add_argument("--scores", type=Path, default=CHURN_SCORES)
    parser.add_argument("--output", type=Path, default=EVIDENCE)
    args = parser.parse_args()
    result = validate(args.database, args.scores, args.output)
    failed = [r for r in result if r["status"] != "pass"]
    print(f"{len(result) - len(failed)}/{len(result)} dashboard measures tie to the warehouse")
    for row in failed:
        print("FAIL", row["page"], row["measure"], row["filter"], row["warehouse_total"], row["report_total"])
    raise SystemExit(1 if failed else 0)

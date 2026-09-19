"""Dashboard measure and validation tests. Fixture tests are hermetic; warehouse tests skip
when the pipeline has not been run."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from src.dashboard.payload import CHURN_SCORES, WAREHOUSE, build_payload
from src.dashboard.validate import Case, Warehouse, run_node, validate

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required")
needs_warehouse = pytest.mark.skipif(
    not (WAREHOUSE.exists() and CHURN_SCORES.exists()), reason="run `make pipeline` first"
)


def _tiny_payload() -> dict[str, Any]:
    # months: 2024-01, 2024-02. Customer 0 expands, customer 1 churns, customer 2 is new.
    #                 month seg plan prod cust open  close new   exp  con churn react
    rows = [
        [0, 0, 0, 0, 0, 100.0, 100.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [0, 1, 0, 0, 1, 50.0, 50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [1, 0, 0, 0, 0, 100.0, 130.0, 0.0, 30.0, 0.0, 0.0, 0.0],
        [1, 1, 0, 0, 1, 50.0, 0.0, 0.0, 0.0, 0.0, 50.0, 0.0],
        [1, 1, 0, 0, 2, 0.0, 20.0, 20.0, 0.0, 0.0, 0.0, 0.0],
    ]
    return {
        "meta": {"months": ["2024-01", "2024-02"],
                 "economics": {"contact_cost": 10.0, "retained_margin": 1000.0, "success_rate": 0.5}},
        "movement": {"segments": ["enterprise", "smb"], "plans": ["Starter"], "products": ["Core"],
                     "customers": [["C0", "A", "enterprise", "us"], ["C1", "B", "smb", "us"],
                                   ["C2", "C", "smb", "us"]], "rows": rows},
        "cash": [{"ym": "2024-02", "invoiced": 100.0, "successful_payments": 90.0,
                  "failed_exposure": 10.0, "refunded": 5.0, "net_cash": 85.0, "recognized": 100.0,
                  "deferred": 0.0}],
        "exceptions": [
            {"invoice_id": "I1", "exception_type": "contract_date_conflict", "severity": "medium",
             "total_amount": 40.0},
            {"invoice_id": "I1", "exception_type": "invalid_discount", "severity": "medium",
             "total_amount": 40.0},
            {"invoice_id": "I2", "exception_type": "contract_date_conflict", "severity": "high",
             "total_amount": 60.0},
        ],
        "open_invoices": [{"invoice_id": "I3", "failed_payment_exposure": 10.0}],
        "cohorts": [{"cohort": "2024-01", "age": 1, "size": 2, "active": 1, "logo": 0.5, "ndr": 0.8}],
        # account, as_of, risk, churned, mrr, then driver columns
        "risk": {"rows": [
            ["A1", "2024-01-31", 0.30, 1, 100.0, 0.1, 0.5, 1, 0, 3.0, "monthly", "smb"],
            ["A1", "2024-02-29", 0.20, 0, 100.0, None, 0.5, 1, 0, 3.0, "monthly", "smb"],
            ["A2", "2024-02-29", 0.05, 0, 200.0, 0.2, 0.7, 0, 0, 1.0, "annual", "enterprise"],
            ["A3", "2024-02-29", 0.02, 1, 300.0, 0.3, 0.9, 0, 0, 2.0, "annual", "enterprise"],
        ]},
    }


def _evaluate(payload: dict[str, Any], cases: list[Case], tmp_path: Path) -> list[Any]:
    payload_path, cases_path = tmp_path / "payload.json", tmp_path / "cases.json"
    payload_path.write_text(json.dumps(payload))
    cases_path.write_text(json.dumps([{"measure": c.measure, "filter": c.filter} for c in cases]))
    return run_node(payload_path, cases_path)


def test_bridge_identities_and_retention(tmp_path: Path) -> None:
    feb = {"month": "2024-02"}
    cases = [Case("t", m, feb) for m in
             ("opening_mrr", "closing_mrr", "new_mrr", "expansion_mrr", "churned_mrr", "net_new_mrr",
              "arr", "nrr", "grr", "bridge_variance")]
    values = dict(zip([c.measure for c in cases], _evaluate(_tiny_payload(), cases, tmp_path), strict=True))
    assert values["opening_mrr"] == 150.0 and values["closing_mrr"] == 150.0
    assert values["new_mrr"] == 20.0 and values["expansion_mrr"] == 30.0
    assert values["churned_mrr"] == 50.0 and values["net_new_mrr"] == 0.0
    assert values["arr"] == 1800.0
    assert values["nrr"] == pytest.approx((150 + 30 - 50) / 150)
    assert values["grr"] == pytest.approx((150 - 50) / 150)
    assert values["bridge_variance"] == 0.0


def test_slicing_by_name_and_customer_and_undefined_retention(tmp_path: Path) -> None:
    cases = [
        Case("t", "closing_mrr", {"month": "2024-02", "segment": "smb"}),
        Case("t", "churned_mrr", {"month": "2024-02", "customerId": "C1"}),
        Case("t", "nrr", {"month": "2024-02", "customerId": "C2"}),  # no opening MRR
    ]
    closing, churned, nrr = _evaluate(_tiny_payload(), cases, tmp_path)
    assert closing == 20.0 and churned == 50.0 and nrr is None


def test_exception_exposure_counts_each_invoice_once(tmp_path: Path) -> None:
    cases = [Case("t", "exception_records", {}), Case("t", "exception_invoices", {}),
             Case("t", "exception_exposure", {}),
             Case("t", "exception_exposure", {"severity": "medium", "rule": "all"})]
    records, invoices, exposure, medium = _evaluate(_tiny_payload(), cases, tmp_path)
    assert (records, invoices, exposure, medium) == (3, 2, 100.0, 40.0)


def test_risk_measures_match_hand_calculation(tmp_path: Path) -> None:
    f = {"threshold": 0.10}
    cases = [Case("t", m, f) for m in ("risk_flagged", "risk_true_positives", "risk_precision",
                                       "risk_recall", "risk_exposed_mrr", "risk_net_value",
                                       "risk_queue_accounts")]
    flagged, tp, precision, recall, exposed, value, queue = _evaluate(_tiny_payload(), cases, tmp_path)
    assert (flagged, tp) == (2, 1)
    assert precision == 0.5 and recall == 0.5 and exposed == 200.0
    assert value == 1 * (1000 * 0.5 - 10) - 1 * 10  # one true positive, one false positive
    assert queue == 1  # A1's latest snapshot (risk 0.20) qualifies; A2 and A3 do not
    (undefined,) = _evaluate(_tiny_payload(), [Case("t", "risk_precision", {"threshold": 0.9})], tmp_path)
    assert undefined is None


def test_unknown_measure_and_filter_fail_loudly(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Unknown measure"):
        _evaluate(_tiny_payload(), [Case("t", "made_up_measure", {"month": "2024-02"})], tmp_path)
    with pytest.raises(RuntimeError, match="Unknown segment"):
        _evaluate(_tiny_payload(), [Case("t", "closing_mrr", {"month": "2024-02", "segment": "nope"})], tmp_path)


@needs_warehouse
def test_every_dashboard_measure_ties_to_the_warehouse(tmp_path: Path) -> None:
    rows = validate(WAREHOUSE, CHURN_SCORES, tmp_path / "evidence.csv")
    assert len(rows) > 100
    assert {r["status"] for r in rows} == {"pass"}


@needs_warehouse
def test_validation_detects_a_tampered_dashboard_payload(tmp_path: Path) -> None:
    payload = build_payload()
    tampered = copy.deepcopy(payload)
    tampered["movement"]["rows"][0][6] += 1.0  # inflate one closing MRR row
    case = Case("t", "closing_mrr", {"month": payload["meta"]["months"][0]})
    honest, dishonest = (_evaluate(p, [case], tmp_path)[0] for p in (payload, tampered))
    expected = Warehouse(WAREHOUSE, CHURN_SCORES).expected(case)
    assert abs(honest - expected) < 0.01
    assert abs(dishonest - expected) >= 0.99


@needs_warehouse
def test_built_dashboard_is_self_contained(tmp_path: Path) -> None:
    from src.dashboard.build import build

    html = build(tmp_path / "index.html").read_text(encoding="utf-8")
    for placeholder in ("/*STYLE*/", "/*PAYLOAD*/", "/*MEASURES*/", "/*APP*/"):
        assert placeholder not in html
    assert "http://" not in html and "https://" not in html.replace("https://www.w3.org", "")
    assert html.count("<script") == 3


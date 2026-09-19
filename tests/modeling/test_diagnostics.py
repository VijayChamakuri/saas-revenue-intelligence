import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.modeling.churn import (
    InterventionEconomics,
    SplitDates,
    run_churn_experiment,
    synthetic_churn_fixture,
    temporal_split,
)
from src.modeling.diagnostics import (
    calibration_table,
    confusion_at_threshold,
    decile_lift,
    feature_drift,
    threshold_sensitivity,
    write_run_artifacts,
)
from src.modeling.forecast import rolling_backtest, summarize_backtest, synthetic_monthly_fixture


def test_confusion_matrix_matches_hand_count() -> None:
    y = [1, 1, 0, 0, 0, 1]
    p = [0.9, 0.2, 0.8, 0.1, 0.3, 0.6]
    c = confusion_at_threshold(y, p, 0.5)
    assert (c["true_positives"], c["false_positives"], c["false_negatives"], c["true_negatives"]) == (2, 1, 1, 2)
    assert c["precision"] == pytest.approx(2 / 3) and c["recall"] == pytest.approx(2 / 3)
    assert c["prevalence"] == pytest.approx(0.5)


def test_threshold_sensitivity_economics_are_explicit() -> None:
    economics = InterventionEconomics(contact_cost=10.0, retained_margin_if_successful=1000.0, intervention_success_rate=0.5)
    table = threshold_sensitivity([1, 0, 1, 0], [0.9, 0.8, 0.2, 0.1], economics, thresholds=[0.5])
    row = table.iloc[0]
    assert row["expected_contacts"] == 2 and row["expected_saves"] == 0.5
    assert row["expected_margin"] == pytest.approx(0.5 * 1000 - 2 * 10)


def test_calibration_and_deciles_partition_all_rows() -> None:
    rng = np.random.default_rng(3)
    p = rng.uniform(0, 0.2, 1000)
    y = (rng.uniform(0, 1, 1000) < p).astype(int)
    assert calibration_table(y, p)["n"].sum() == 1000
    lift = decile_lift(y, p)
    assert lift["n"].sum() == 1000
    assert lift["cumulative_capture"].iloc[-1] == pytest.approx(1.0)


def test_mismatched_inputs_fail_loudly() -> None:
    with pytest.raises(ValueError, match="same length"):
        confusion_at_threshold([1, 0], [0.5], 0.5)


def test_feature_drift_flags_a_shifted_test_period() -> None:
    frame = synthetic_churn_fixture(seed=5, accounts=900)
    train, calibration, test = temporal_split(frame, SplitDates("2023-06-30", "2024-06-30"))
    shifted = test.assign(mrr=test["mrr"] * 3)
    drift = feature_drift(train, calibration, shifted)
    mrr = drift[(drift.feature == "mrr") & (drift.period == "test")].iloc[0]
    assert mrr["standardized_shift"] > 0.5


def test_run_artifacts_are_versioned_and_hash_recorded(tmp_path: Path) -> None:
    frame = synthetic_churn_fixture(seed=8, accounts=1200)
    dates = SplitDates("2023-12-31", "2024-12-31")
    economics = InterventionEconomics()
    results, scores = run_churn_experiment(frame, dates, economics)
    args = (frame, dates, economics, results, scores, "logistic_regression", temporal_split(frame, dates), "fixture")
    one = write_run_artifacts(tmp_path, *args)
    two = write_run_artifacts(tmp_path, *args)
    assert one == two  # same parameters and input give the same run id
    manifest = json.loads((one / "manifest.json").read_text())
    assert {"params.json", "metrics.json", "threshold_sensitivity.csv", "calibration.csv",
            "lift_deciles.csv", "feature_drift.csv"} <= set(manifest["files"])
    metrics = json.loads((one / "metrics.json").read_text())
    assert 0 < metrics["class_prevalence_test"] < 1
    assert metrics["split_rows"]["test"] == len(scores)


def test_backtest_summary_reports_wape_alongside_mape() -> None:
    summary = summarize_backtest(rolling_backtest(synthetic_monthly_fixture(), horizon=3, min_train=18))
    assert {"mae", "mape", "wape"} <= set(summary.columns)
    assert (summary["wape"] >= 0).all() and not pd.isna(summary["wape"]).any()

"""Rolling-origin subscription forecasts and transparent planning scenarios."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Scenario:
    name: str
    churn_change_pct: float = 0.0
    pricing_change_pct: float = 0.0
    expansion_change_pct: float = 0.0
    failed_payment_recovery_pct: float = 0.0
    marketing_spend_change_pct: float = 0.0
    assumed_marketing_roas: float = 1.2


def validate_monthly(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "month",
        "mrr",
        "churned_mrr",
        "expansion_mrr",
        "cash_collected",
        "failed_payment_exposure",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing forecast columns: {missing}")
    data = frame.copy()
    data["month"] = pd.to_datetime(data["month"], errors="raise")
    if data["month"].duplicated().any():
        raise ValueError("Monthly forecast input has duplicate months")
    if (data[list(required - {"month"})] < 0).any().any():
        raise ValueError("Forecast measures cannot be negative")
    return data.sort_values("month").reset_index(drop=True)


def _predict(history: np.ndarray, horizon: int, method: str, season: int = 12) -> np.ndarray:
    if method == "naive":
        return np.repeat(history[-1], horizon)
    if method == "seasonal_naive":
        if len(history) < season:
            return np.repeat(history[-1], horizon)
        return np.array([history[-season + (index % season)] for index in range(horizon)])
    if method == "drift":
        slope = (history[-1] - history[0]) / max(len(history) - 1, 1)
        return history[-1] + slope * np.arange(1, horizon + 1)
    raise ValueError(f"Unsupported forecast method: {method}")


def rolling_backtest(
    frame: pd.DataFrame,
    target: str = "mrr",
    horizon: int = 3,
    min_train: int = 18,
    methods: tuple[str, ...] = ("naive", "seasonal_naive", "drift"),
) -> pd.DataFrame:
    data = validate_monthly(frame)
    if target not in data:
        raise ValueError(f"Unknown target: {target}")
    if len(data) < min_train + horizon:
        raise ValueError("Insufficient observations for rolling backtest")
    rows = []
    for cutoff in range(min_train, len(data) - horizon + 1):
        actual = data[target].iloc[cutoff : cutoff + horizon].to_numpy(dtype=float)
        for method in methods:
            predicted = _predict(data[target].iloc[:cutoff].to_numpy(dtype=float), horizon, method)
            for step, (truth, estimate) in enumerate(zip(actual, predicted, strict=False), start=1):
                rows.append(
                    {
                        "method": method,
                        "cutoff_month": data["month"].iloc[cutoff - 1],
                        "horizon": step,
                        "actual": truth,
                        "forecast": max(float(estimate), 0.0),
                        "absolute_error": abs(truth - estimate),
                        "ape": abs(truth - estimate) / truth if truth else np.nan,
                    }
                )
    return pd.DataFrame(rows)


def summarize_backtest(backtest: pd.DataFrame) -> pd.DataFrame:
    return (
        backtest.groupby("method", as_index=False)
        .agg(
            mae=("absolute_error", "mean"),
            mape=("ape", "mean"),
            total_abs_error=("absolute_error", "sum"),
            total_actual=("actual", "sum"),
            observations=("actual", "size"),
        )
        .assign(wape=lambda d: d["total_abs_error"] / d["total_actual"].replace(0, np.nan))
        .drop(columns=["total_abs_error", "total_actual"])
        .sort_values(["mae", "method"])
        .reset_index(drop=True)
    )


def forecast_best_method(
    frame: pd.DataFrame, target: str, horizon: int = 12
) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = validate_monthly(frame)
    backtest = rolling_backtest(data, target=target)
    summary = summarize_backtest(backtest)
    method = str(summary.iloc[0]["method"])
    values = _predict(data[target].to_numpy(dtype=float), horizon, method)
    months = pd.date_range(data["month"].max() + pd.offsets.MonthEnd(1), periods=horizon, freq="ME")
    forecast = pd.DataFrame(
        {"month": months, "metric": target, "forecast": np.maximum(values, 0), "method": method}
    )
    return forecast, summary


def apply_scenario(baseline: pd.DataFrame, scenario: Scenario) -> pd.DataFrame:
    data = validate_monthly(baseline)
    output = data.copy()
    output["scenario"] = scenario.name
    avoided_churn = output["churned_mrr"] * (-scenario.churn_change_pct)
    additional_expansion = output["expansion_mrr"] * scenario.expansion_change_pct
    pricing_effect = output["mrr"] * scenario.pricing_change_pct
    recovered_cash = output["failed_payment_exposure"] * scenario.failed_payment_recovery_pct
    marketing_effect = (
        output.get("marketing_spend", pd.Series(0.0, index=output.index))
        * scenario.marketing_spend_change_pct
        * scenario.assumed_marketing_roas
    )
    output["scenario_mrr"] = (
        output["mrr"] + avoided_churn + additional_expansion + pricing_effect + marketing_effect
    )
    output["scenario_cash_collected"] = output["cash_collected"] + recovered_cash
    output["incremental_mrr_estimate"] = output["scenario_mrr"] - output["mrr"]
    output["incremental_cash_estimate"] = recovered_cash
    return output


def synthetic_monthly_fixture(seed: int = 42, periods: int = 48) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    months = pd.date_range("2022-01-31", periods=periods, freq="ME")
    trend = 200_000 + np.arange(periods) * 7_500
    seasonal = 12_000 * np.sin(np.arange(periods) * 2 * np.pi / 12)
    mrr = np.maximum(trend + seasonal + rng.normal(0, 4_000, periods), 1)
    return pd.DataFrame(
        {
            "month": months,
            "mrr": mrr,
            "churned_mrr": mrr * rng.uniform(0.018, 0.035, periods),
            "expansion_mrr": mrr * rng.uniform(0.025, 0.045, periods),
            "cash_collected": mrr * rng.uniform(0.94, 1.03, periods),
            "failed_payment_exposure": mrr * rng.uniform(0.005, 0.018, periods),
            "marketing_spend": rng.uniform(20_000, 38_000, periods),
        }
    )


def main(input_csv: str | None = None, output_dir: str = "data/exports/modeling") -> None:
    data = (
        pd.read_csv(input_csv)
        if input_csv and Path(input_csv).exists()
        else synthetic_monthly_fixture()
    )
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    summaries = {}
    forecasts = []
    for metric in ("mrr", "churned_mrr", "cash_collected"):
        forecast, summary = forecast_best_method(data, metric)
        forecasts.append(forecast)
        summaries[metric] = summary.to_dict(orient="records")
    pd.concat(forecasts, ignore_index=True).to_csv(target / "forecast.csv", index=False)
    (target / "forecast_backtest.json").write_text(
        json.dumps(summaries, indent=2), encoding="utf-8"
    )
    scenarios = [
        Scenario("baseline"),
        Scenario("retention_focus", churn_change_pct=-0.10, failed_payment_recovery_pct=0.20),
        Scenario("pricing_and_expansion", pricing_change_pct=0.03, expansion_change_pct=0.10),
    ]
    pd.concat([apply_scenario(data, item) for item in scenarios], ignore_index=True).to_csv(
        target / "scenarios.csv", index=False
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv")
    parser.add_argument("--output-dir", default="data/exports/modeling")
    arguments = parser.parse_args()
    main(arguments.input_csv, arguments.output_dir)

"""Generate README evidence charts from verified pipeline outputs."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, PercentFormatter

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "data" / "exports"
ARTIFACTS = ROOT / "artifacts"
OUTPUT = ROOT / "assets" / "readme"

NAVY = "#102A43"
BLUE = "#2F6BFF"
TEAL = "#11A683"
RED = "#D64545"
AMBER = "#F2A93B"
SLATE = "#627D98"
LIGHT = "#E8EEF5"


def money_millions(value: float, _position: int) -> str:
    return f"${value / 1_000_000:.1f}M"


def setup() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titleweight": "bold",
            "axes.titlesize": 14,
            "axes.labelcolor": NAVY,
            "axes.edgecolor": LIGHT,
            "xtick.color": SLATE,
            "ytick.color": SLATE,
            "text.color": NAVY,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def revenue_story() -> None:
    kpis = pd.read_csv(EXPORTS / "revenue_kpis.csv", parse_dates=["month_start"])
    bridge = pd.read_csv(EXPORTS / "mrr_bridge.csv", parse_dates=["month_start"])
    latest = bridge.iloc[-1]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4), gridspec_kw={"width_ratios": [1.55, 1]})
    ax = axes[0]
    ax.plot(kpis.month_start, kpis.closing_mrr, color=BLUE, linewidth=3)
    ax.fill_between(kpis.month_start, kpis.closing_mrr, color=BLUE, alpha=0.08)
    ax.scatter(kpis.month_start.iloc[-1], kpis.closing_mrr.iloc[-1], color=RED, s=55, zorder=3)
    ax.annotate(
        f"Dec 2025\n${kpis.closing_mrr.iloc[-1] / 1_000_000:.2f}M MRR",
        xy=(kpis.month_start.iloc[-1], kpis.closing_mrr.iloc[-1]),
        xytext=(-72, -52),
        textcoords="offset points",
        fontsize=10,
        fontweight="bold",
        arrowprops={"arrowstyle": "-", "color": SLATE},
    )
    ax.set_title("Recurring revenue scaled, then reversed in the closing month", loc="left")
    ax.set_ylabel("Monthly recurring revenue")
    ax.yaxis.set_major_formatter(FuncFormatter(money_millions))
    ax.grid(axis="y", color=LIGHT, linewidth=0.8)
    ax.grid(axis="x", visible=False)

    movement_names = ["New", "Expansion", "Contraction", "Churn"]
    movement_values = [
        latest.new_mrr,
        latest.expansion_mrr,
        -latest.contraction_mrr,
        -latest.churned_mrr,
    ]
    colors = [TEAL, BLUE, AMBER, RED]
    ax = axes[1]
    bars = ax.bar(movement_names, movement_values, color=colors, width=0.68)
    ax.axhline(0, color=NAVY, linewidth=0.9)
    for bar, value in zip(bars, movement_values, strict=False):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + (5500 if value >= 0 else -5500),
            f"${abs(value) / 1000:.0f}K",
            ha="center",
            va="bottom" if value >= 0 else "top",
            fontweight="bold",
            fontsize=9,
        )
    ax.set_title("Churn dominates the December MRR bridge", loc="left")
    ax.set_ylabel("MRR movement")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value / 1000:.0f}K"))
    ax.tick_params(axis="x", rotation=18)
    ax.grid(axis="y", color=LIGHT, linewidth=0.8)
    ax.grid(axis="x", visible=False)

    for axis in axes:
        axis.spines[["top", "right", "left"]].set_visible(False)
    fig.suptitle(
        "Revenue movement: 36 months reconcile to the cent",
        x=0.04,
        y=1.03,
        ha="left",
        fontsize=18,
        fontweight="bold",
    )
    fig.text(
        0.04, -0.01, "Synthetic portfolio dataset. Source: tested dbt revenue marts.", color=SLATE
    )
    fig.tight_layout()
    fig.savefig(OUTPUT / "revenue_movement.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def finance_story() -> None:
    billing = pd.read_csv(EXPORTS / "billing_reconciliation.csv", parse_dates=["invoice_date"])
    exceptions = pd.read_csv(EXPORTS / "finance_exceptions.csv")
    monthly = (
        billing.assign(month=billing.invoice_date.dt.to_period("M").dt.to_timestamp())
        .groupby("month", as_index=False)
        .agg(
            failed_payment_exposure=("failed_payment_exposure", "sum"),
            collected_cash=("net_collected_cash", "sum"),
        )
    )
    exception_counts = exceptions.exception_type.value_counts()
    total_exposure = billing.failed_payment_exposure.sum()
    failed_attempts = int((billing.failed_payment_exposure > 0).sum())

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.3), gridspec_kw={"width_ratios": [1.6, 1]})
    ax = axes[0]
    ax.bar(monthly.month, monthly.failed_payment_exposure, width=21, color=RED, alpha=0.88)
    ax.set_title("Failed-payment exposure concentrates as revenue scales", loc="left")
    ax.set_ylabel("Monthly exposure")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value / 1000:.0f}K"))
    ax.grid(axis="y", color=LIGHT, linewidth=0.8)
    ax.grid(axis="x", visible=False)
    ax.text(
        0.01,
        0.94,
        f"${total_exposure / 1_000_000:.3f}M exposure across {failed_attempts} failed attempts",
        transform=ax.transAxes,
        fontsize=11,
        fontweight="bold",
        color=RED,
        va="top",
    )

    ax = axes[1]
    bars = ax.barh(
        exception_counts.index.str.replace("_", " ").str.title(), exception_counts, color=AMBER
    )
    ax.bar_label(bars, padding=6, fontweight="bold")
    ax.set_title("Contract dates drive the exception queue", loc="left")
    ax.set_xlabel("Detected exceptions")
    ax.set_xlim(0, exception_counts.max() * 1.18)
    ax.grid(axis="x", color=LIGHT, linewidth=0.8)
    ax.grid(axis="y", visible=False)

    for axis in axes:
        axis.spines[["top", "right", "left"]].set_visible(False)
    fig.suptitle(
        "Finance control evidence: exposure is quantified and exceptions are actionable",
        x=0.04,
        y=1.03,
        ha="left",
        fontsize=18,
        fontweight="bold",
    )
    fig.text(
        0.04, -0.01, "Synthetic portfolio dataset. Source: tested dbt finance marts.", color=SLATE
    )
    fig.tight_layout()
    fig.savefig(OUTPUT / "finance_controls.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def model_story() -> None:
    metrics = json.loads((ARTIFACTS / "modeling" / "churn_metrics.json").read_text())
    backtests = json.loads((ARTIFACTS / "forecast" / "forecast_backtest.json").read_text())
    model_names = ["Logistic baseline", "Gradient boosting"]
    model_keys = ["logistic_regression", "hist_gradient_boosting"]
    metric_names = ["ROC-AUC", "PR-AUC", "Recall"]
    metric_keys = ["roc_auc", "pr_auc", "recall"]
    values = np.array([[metrics[model][metric] for metric in metric_keys] for model in model_keys])

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    ax = axes[0]
    x = np.arange(len(metric_names))
    width = 0.34
    for index, (name, color) in enumerate(zip(model_names, [BLUE, TEAL], strict=False)):
        bars = ax.bar(x + (index - 0.5) * width, values[index], width, label=name, color=color)
        ax.bar_label(
            bars, labels=[f"{value:.3f}" for value in values[index]], padding=4, fontsize=9
        )
    ax.set_xticks(x, metric_names)
    ax.set_ylim(0, 1.12)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_title("Transparent baseline remains competitive", loc="left")
    ax.legend(frameon=False, loc="lower left")
    ax.grid(axis="y", color=LIGHT, linewidth=0.8)
    ax.grid(axis="x", visible=False)

    selected = {}
    for metric, rows in backtests.items():
        best = min(rows, key=lambda row: row["mae"])
        selected[metric] = best
    labels = ["MRR", "Churned MRR", "Cash"]
    mapes = [selected[key]["mape"] for key in ["mrr", "churned_mrr", "cash_collected"]]
    methods = [
        selected[key]["method"].replace("_", " ").title()
        for key in ["mrr", "churned_mrr", "cash_collected"]
    ]
    ax = axes[1]
    bars = ax.bar(labels, mapes, color=[BLUE, RED, TEAL], width=0.62)
    for bar, mape, method in zip(bars, mapes, methods, strict=False):
        if mape > 0.25:
            label_y = mape - 0.07
            vertical_alignment = "top"
            label_color = "white"
        else:
            label_y = mape + 0.08
            vertical_alignment = "bottom"
            label_color = NAVY
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            label_y,
            f"{mape:.1%}\n{method}",
            ha="center",
            va=vertical_alignment,
            fontweight="bold",
            fontsize=9,
            color=label_color,
        )
    ax.set_title("Rolling backtests expose the hard-to-forecast metric", loc="left")
    ax.set_ylabel("Selected method MAPE")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.grid(axis="y", color=LIGHT, linewidth=0.8)
    ax.grid(axis="x", visible=False)

    for axis in axes:
        axis.spines[["top", "right", "left"]].set_visible(False)
    fig.suptitle(
        "Predictive proof: time-aware churn validation and rolling forecast backtests",
        x=0.04,
        y=1.03,
        ha="left",
        fontsize=18,
        fontweight="bold",
    )
    fig.text(
        0.04,
        -0.01,
        "Synthetic signals make churn unusually separable. Metrics are evidence of pipeline behavior, not production impact.",
        color=SLATE,
    )
    fig.tight_layout()
    fig.savefig(OUTPUT / "model_validation.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    setup()
    revenue_story()
    finance_story()
    model_story()
    print(f"Generated README visuals in {OUTPUT}")


if __name__ == "__main__":
    main()

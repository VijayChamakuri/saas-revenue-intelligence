"""Charts for the README, drawn from the committed extracts.

The warehouse exports are not in git. These figures use tableau/data and
dashboard/validation_evidence.csv, which are.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tableau" / "data"
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
            "axes.titlesize": 13,
            "axes.labelcolor": NAVY,
            "axes.edgecolor": LIGHT,
            "xtick.color": SLATE,
            "ytick.color": SLATE,
            "text.color": NAVY,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def _dollars(value: float) -> str:
    sign = "−" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def revenue_story() -> None:
    kpis = pd.read_csv(DATA / "kpi_monthly.csv", parse_dates=["month_start"])
    bridge = pd.read_csv(DATA / "mrr_bridge_long.csv")
    latest = bridge[bridge["month_label"] == "2025-12"].set_index("component")["value"]
    ending = float(kpis.loc[kpis["month_label"] == "2025-12", "closing_mrr"].iloc[0])

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.6), gridspec_kw={"width_ratios": [1.45, 1]})
    ax = axes[0]
    ax.plot(kpis.month_start, kpis.closing_mrr, color=BLUE, linewidth=2.4)
    ax.fill_between(kpis.month_start, kpis.closing_mrr, color=BLUE, alpha=0.08)
    ax.scatter(kpis.month_start.iloc[-1], ending, color=RED, s=42, zorder=3)
    ax.annotate(
        f"Dec 2025\n{_dollars(ending)}",
        xy=(kpis.month_start.iloc[-1], ending),
        xytext=(-78, -46),
        textcoords="offset points",
        fontsize=9,
        fontweight="bold",
        arrowprops={"arrowstyle": "-", "color": SLATE},
    )
    ax.set_title("Ending MRR", loc="left")
    ax.set_ylabel("Monthly recurring revenue")
    ax.yaxis.set_major_formatter(FuncFormatter(money_millions))
    ax.grid(axis="y", color=LIGHT, linewidth=0.8)
    ax.grid(axis="x", visible=False)

    names = ["New", "Expansion", "Contraction", "Churn"]
    # The long extract stores contraction and churn as negative movements.
    values = [
        float(latest["New"]),
        float(latest["Expansion"]),
        float(latest["Contraction"]),
        float(latest["Churned"]),
    ]
    colors = [TEAL, BLUE, AMBER, RED]
    ax = axes[1]
    bars = ax.bar(names, values, color=colors, width=0.68)
    ax.axhline(0, color=NAVY, linewidth=0.8)
    for bar, value in zip(bars, values, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + (12000 if value >= 0 else -12000),
            _dollars(value),
            ha="center",
            va="bottom" if value >= 0 else "top",
            fontsize=8,
            fontweight="bold",
        )
    ax.set_title("December 2025 movements", loc="left")
    ax.set_ylabel("MRR movement")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value / 1000:.0f}K"))
    ax.set_ylim(-390000, 120000)
    ax.grid(axis="y", color=LIGHT, linewidth=0.8)
    ax.grid(axis="x", visible=False)

    for axis in axes:
        axis.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUTPUT / "revenue_movement.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def _wape(series: list[float], method: str, horizon: int = 3, min_train: int = 18) -> float:
    total_abs = 0.0
    total_act = 0.0
    for cutoff in range(min_train, len(series) - horizon + 1):
        history = series[:cutoff]
        actual = series[cutoff : cutoff + horizon]
        if method == "naive":
            predicted = [history[-1]] * horizon
        elif method == "seasonal_naive":
            season = 12
            predicted = [history[-season + (index % season)] for index in range(horizon)]
        elif method == "drift":
            slope = (history[-1] - history[0]) / max(len(history) - 1, 1)
            predicted = [history[-1] + slope * (index + 1) for index in range(horizon)]
        else:
            raise ValueError(method)
        for truth, estimate in zip(actual, predicted, strict=True):
            estimate = max(estimate, 0.0)
            total_abs += abs(truth - estimate)
            total_act += truth
    return total_abs / total_act


def model_story() -> None:
    kpis = list(csv.DictReader((DATA / "kpi_monthly.csv").open()))
    bridge: dict[str, dict[str, float]] = {}
    for row in csv.DictReader((DATA / "mrr_bridge_long.csv").open()):
        bridge.setdefault(row["month_start"], {})[row["component"]] = float(row["value"])
    closing = [float(row["closing_mrr"]) for row in kpis]
    churned = [-bridge[row["month_start"]]["Churned"] for row in kpis]
    methods = ["naive", "seasonal_naive", "drift"]
    labels = ["Naive", "Seasonal naive", "Drift"]
    mrr = [_wape(closing, method) for method in methods]
    churn = [_wape(churned, method) for method in methods]

    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    x = np.arange(len(labels))
    width = 0.36
    b1 = ax.bar(x - width / 2, mrr, width, label="Ending MRR", color=BLUE)
    b2 = ax.bar(x + width / 2, churn, width, label="Churned MRR", color=RED)
    ax.bar_label(b1, labels=[f"{value:.1%}" for value in mrr], padding=3, fontsize=8)
    ax.bar_label(b2, labels=[f"{value:.1%}" for value in churn], padding=3, fontsize=8)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.25)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.0%}"))
    ax.set_ylabel("Weighted absolute percentage error")
    ax.set_title("Rolling-origin backtest, 48 forecast points", loc="left")
    ax.legend(frameon=False)
    ax.grid(axis="y", color=LIGHT, linewidth=0.8)
    ax.grid(axis="x", visible=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUTPUT / "model_validation.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def finance_story() -> None:
    billing = pd.read_csv(DATA / "billing_monthly.csv", parse_dates=["month_start"])
    exceptions = pd.read_csv(DATA / "exceptions.csv")
    evidence = pd.read_csv(ROOT / "dashboard" / "validation_evidence.csv")
    attempts = int(
        evidence.loc[evidence["measure"] == "failed_payment_attempts", "warehouse_total"].iloc[0]
    )
    total = float(billing["failed_payment_exposure"].sum())
    counts = exceptions["exception_type"].value_counts()

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.4), gridspec_kw={"width_ratios": [1.6, 1]})
    ax = axes[0]
    ax.bar(billing.month_start, billing.failed_payment_exposure, width=20, color=RED, alpha=0.9)
    ax.set_title("Failed-payment exposure by invoice month", loc="left")
    ax.set_ylabel("Exposure")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value / 1000:.0f}K"))
    ax.text(
        0.01,
        0.95,
        f"{_dollars(total)} across {attempts} invoices, all months",
        transform=ax.transAxes,
        fontsize=9,
        fontweight="bold",
        color=RED,
        va="top",
    )
    ax.grid(axis="y", color=LIGHT, linewidth=0.8)
    ax.grid(axis="x", visible=False)

    ax = axes[1]
    names = [name.replace("_", " ") for name in counts.index]
    bars = ax.barh(names, counts.values, color=AMBER)
    ax.bar_label(bars, padding=4, fontweight="bold")
    ax.set_title("Exception queue", loc="left")
    ax.set_xlabel("Invoice-rule rows")
    ax.set_xlim(0, counts.max() * 1.25)
    ax.grid(axis="x", color=LIGHT, linewidth=0.8)
    ax.grid(axis="y", visible=False)

    for axis in axes:
        axis.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUTPUT / "finance_controls.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    setup()
    revenue_story()
    finance_story()
    model_story()
    print(f"Wrote charts to {OUTPUT}")


if __name__ == "__main__":
    main()

"""Leakage-safe churn modeling with calibration and economic thresholding.

The expected input grain is one account snapshot per ``as_of_date``. The label
``churned_within_90d`` must only use outcomes after that snapshot. Identifiers
and post-outcome fields are deliberately excluded from the feature matrix.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC_FEATURES = [
    "usage_change_30d",
    "feature_adoption_rate",
    "support_tickets_90d",
    "failed_payments_90d",
    "contract_age_months",
    "seats",
    "engagement_recency_days",
    "prior_downgrades",
    "mrr",
]
CATEGORICAL_FEATURES = ["plan_type", "customer_size"]
LABEL = "churned_within_90d"
DATE = "as_of_date"


@dataclass(frozen=True)
class SplitDates:
    train_end: str
    calibration_end: str


@dataclass(frozen=True)
class InterventionEconomics:
    contact_cost: float = 35.0
    retained_margin_if_successful: float = 6000.0
    intervention_success_rate: float = 0.18

    @property
    def true_positive_value(self) -> float:
        return (
            self.retained_margin_if_successful * self.intervention_success_rate - self.contact_cost
        )

    @property
    def false_positive_cost(self) -> float:
        return self.contact_cost


def validate_snapshot_data(frame: pd.DataFrame) -> pd.DataFrame:
    required = {DATE, LABEL, *NUMERIC_FEATURES, *CATEGORICAL_FEATURES}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing churn columns: {missing}")
    clean = frame.copy()
    clean[DATE] = pd.to_datetime(clean[DATE], errors="raise")
    if not clean[LABEL].dropna().isin([0, 1, False, True]).all():
        raise ValueError(f"{LABEL} must be binary")
    if clean[LABEL].isna().any():
        raise ValueError(f"{LABEL} cannot be null")
    if "account_id" in clean and clean.duplicated(["account_id", DATE]).any():
        raise ValueError("Duplicate account snapshots detected")
    return clean.sort_values(DATE).reset_index(drop=True)


def temporal_split(
    frame: pd.DataFrame, dates: SplitDates
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data = validate_snapshot_data(frame)
    train_end = pd.Timestamp(dates.train_end)
    calibration_end = pd.Timestamp(dates.calibration_end)
    if train_end >= calibration_end:
        raise ValueError("train_end must precede calibration_end")
    train = data[data[DATE] <= train_end]
    calibration = data[(data[DATE] > train_end) & (data[DATE] <= calibration_end)]
    test = data[data[DATE] > calibration_end]
    for name, part in (("train", train), ("calibration", calibration), ("test", test)):
        if part.empty or part[LABEL].nunique() < 2:
            raise ValueError(f"{name} split must be nonempty and contain both label classes")
    return train, calibration, test


def _preprocessor() -> ColumnTransformer:
    numeric = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    categorical = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("one_hot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        [("numeric", numeric, NUMERIC_FEATURES), ("categorical", categorical, CATEGORICAL_FEATURES)]
    )


def _fit_calibrated(
    estimator: Pipeline, train: pd.DataFrame, calibration: pd.DataFrame
) -> CalibratedClassifierCV:
    features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    estimator.fit(train[features], train[LABEL])
    try:
        # FrozenEstimator is the supported prefit interface in scikit-learn 1.6+.
        from sklearn.frozen import FrozenEstimator

        calibrated = CalibratedClassifierCV(estimator=FrozenEstimator(estimator), method="sigmoid")
    except ImportError:
        try:
            calibrated = CalibratedClassifierCV(estimator=estimator, method="sigmoid", cv="prefit")
        except TypeError:  # scikit-learn versions using base_estimator=
            calibrated = CalibratedClassifierCV(
                base_estimator=estimator, method="sigmoid", cv="prefit"
            )
    calibrated.fit(calibration[features], calibration[LABEL])
    return calibrated


def fit_models(train: pd.DataFrame, calibration: pd.DataFrame) -> dict[str, CalibratedClassifierCV]:
    baseline = Pipeline(
        [
            ("prepare", _preprocessor()),
            ("model", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
        ]
    )
    challenger = Pipeline(
        [
            ("prepare", _preprocessor()),
            (
                "model",
                HistGradientBoostingClassifier(
                    max_iter=160, learning_rate=0.06, max_leaf_nodes=15, random_state=42
                ),
            ),
        ]
    )
    return {
        "logistic_regression": _fit_calibrated(baseline, train, calibration),
        "hist_gradient_boosting": _fit_calibrated(challenger, train, calibration),
    }


def choose_business_threshold(
    y_true: Iterable[int], probabilities: Iterable[float], economics: InterventionEconomics
) -> tuple[float, pd.DataFrame]:
    y = np.asarray(list(y_true), dtype=int)
    p = np.asarray(list(probabilities), dtype=float)
    rows = []
    for threshold in np.linspace(0.01, 0.99, 99):
        selected = p >= threshold
        tp = int(np.sum(selected & (y == 1)))
        fp = int(np.sum(selected & (y == 0)))
        value = tp * economics.true_positive_value - fp * economics.false_positive_cost
        rows.append(
            {
                "threshold": threshold,
                "true_positives": tp,
                "false_positives": fp,
                "selected": int(selected.sum()),
                "expected_net_value": value,
            }
        )
    table = pd.DataFrame(rows)
    best = table.sort_values(["expected_net_value", "threshold"], ascending=[False, False]).iloc[0]
    return float(best["threshold"]), table


def evaluate(y_true: pd.Series, probabilities: np.ndarray, threshold: float) -> dict[str, float]:
    predicted = probabilities >= threshold
    prevalence = float(np.mean(y_true))
    selected = max(int(predicted.sum()), 1)
    return {
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "pr_auc": float(average_precision_score(y_true, probabilities)),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "precision": float(precision_score(y_true, predicted, zero_division=0)),
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "lift_at_threshold": float((y_true[predicted].sum() / selected) / prevalence)
        if prevalence
        else 0.0,
        "threshold": threshold,
        "selected_accounts": int(predicted.sum()),
    }


def run_churn_experiment(
    frame: pd.DataFrame,
    dates: SplitDates,
    economics: InterventionEconomics | None = None,
) -> tuple[dict[str, Mapping[str, float | str]], pd.DataFrame]:
    economics = economics or InterventionEconomics()
    train, calibration, test = temporal_split(frame, dates)
    models = fit_models(train, calibration)
    features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    results: dict[str, Mapping[str, float | str]] = {}
    scored = test[[column for column in ("account_id", DATE, LABEL) if column in test]].copy()
    for name, model in models.items():
        calibration_probability = model.predict_proba(calibration[features])[:, 1]
        threshold, _ = choose_business_threshold(
            calibration[LABEL], calibration_probability, economics
        )
        test_probability = model.predict_proba(test[features])[:, 1]
        results[name] = evaluate(test[LABEL], test_probability, threshold)
        scored[f"{name}_risk"] = test_probability
        scored[f"{name}_intervene"] = test_probability >= threshold
    results["split_metadata"] = {
        "train_rows": len(train),
        "calibration_rows": len(calibration),
        "test_rows": len(test),
        "train_end": dates.train_end,
        "calibration_end": dates.calibration_end,
        **asdict(economics),
    }
    return results, scored


def synthetic_churn_fixture(seed: int = 42, accounts: int = 1400) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2022-01-31", "2025-12-31", freq="ME")
    snapshot_date = rng.choice(dates, accounts)
    latent_risk = rng.normal(0, 1, accounts)
    future_regime = pd.to_datetime(snapshot_date) >= pd.Timestamp("2025-01-01")
    usage_change = rng.normal(-0.02 - 0.08 * latent_risk, 0.31, accounts)
    adoption = np.clip(rng.beta(2.5, 2.0, accounts) - 0.045 * latent_risk, 0, 1)
    tickets = rng.poisson(np.clip(1.7 + 0.20 * latent_risk, 0.2, None))
    failures = rng.binomial(2, np.clip(0.07 + 0.018 * latent_risk, 0.01, 0.25))
    recency = rng.gamma(2.0, np.clip(7.0 + 0.7 * latent_risk, 2, None))
    downgrade = rng.binomial(2, np.clip(0.09 + 0.018 * latent_risk, 0.01, 0.25))
    logit = (
        -2.65
        - 0.75 * usage_change
        - 0.50 * adoption
        + 0.10 * tickets
        + 0.38 * failures
        + 0.012 * recency
        + 0.28 * downgrade
        + 0.48 * latent_risk
        + 0.35 * future_regime
        + rng.normal(0, 0.65, accounts)
    )
    probability = 1 / (1 + np.exp(-logit))
    labels = rng.binomial(1, probability)
    noisy_labels = rng.random(accounts) < 0.025
    labels[noisy_labels] = 1 - labels[noisy_labels]
    return pd.DataFrame(
        {
            "account_id": [f"A{i:06d}" for i in range(accounts)],
            "as_of_date": snapshot_date,
            "usage_change_30d": usage_change,
            "feature_adoption_rate": adoption,
            "support_tickets_90d": tickets,
            "failed_payments_90d": failures,
            "contract_age_months": rng.integers(1, 61, accounts),
            "seats": rng.integers(2, 400, accounts),
            "engagement_recency_days": recency,
            "prior_downgrades": downgrade,
            "mrr": rng.lognormal(6.0, 0.8, accounts),
            "plan_type": rng.choice(["monthly", "annual"], accounts),
            "customer_size": rng.choice(
                ["small", "mid_market", "enterprise"], accounts, p=[0.55, 0.32, 0.13]
            ),
            "churned_within_90d": labels,
        }
    ).sort_values("as_of_date")


def main(input_csv: str | None = None, output_dir: str = "data/exports/modeling") -> None:
    frame = (
        pd.read_csv(input_csv)
        if input_csv and Path(input_csv).exists()
        else synthetic_churn_fixture()
    )
    dates = SplitDates("2024-06-30", "2024-12-31")
    results, scores = run_churn_experiment(frame, dates)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "churn_metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    scores.to_csv(target / "churn_scores.csv", index=False)

    from src.modeling.diagnostics import write_run_artifacts  # avoids a circular import

    source = Path(input_csv) if input_csv and Path(input_csv).exists() else None
    input_hash = (
        hashlib.sha256(source.read_bytes()).hexdigest() if source else "synthetic-fixture"
    )
    write_run_artifacts(
        target / "runs",
        frame,
        dates,
        InterventionEconomics(),
        results,
        scores,
        "logistic_regression",
        temporal_split(frame, dates),
        input_hash,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv")
    parser.add_argument("--output-dir", default="data/exports/modeling")
    arguments = parser.parse_args()
    main(arguments.input_csv, arguments.output_dir)

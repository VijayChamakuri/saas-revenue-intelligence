"""Decision diagnostics for the churn model and versioned run artifacts.

ROC-AUC alone overstates usefulness on a rare outcome, so this module reports the
quantities a retention team acts on: the confusion matrix at the business threshold,
expected contacts, saves and margin across thresholds, lift by decile, calibration,
and feature drift between the train, calibration and future-test periods.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from src.modeling.churn import (
    CATEGORICAL_FEATURES,
    LABEL,
    NUMERIC_FEATURES,
    InterventionEconomics,
    SplitDates,
)


def _arrays(y_true: Sequence[int], probability: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(probability, dtype=float)
    if y.shape != p.shape:
        raise ValueError("labels and probabilities must have the same length")
    return y, p


def confusion_at_threshold(
    y_true: Sequence[int], probability: Sequence[float], threshold: float
) -> dict[str, float]:
    y, p = _arrays(y_true, probability)
    selected = p >= threshold
    tp = int(np.sum(selected & (y == 1)))
    fp = int(np.sum(selected & (y == 0)))
    fn = int(np.sum(~selected & (y == 1)))
    tn = int(np.sum(~selected & (y == 0)))
    return {
        "threshold": float(threshold),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "prevalence": float(y.mean()),
        "precision": tp / (tp + fp) if tp + fp else float("nan"),
        "recall": tp / (tp + fn) if tp + fn else float("nan"),
    }


def threshold_sensitivity(
    y_true: Sequence[int],
    probability: Sequence[float],
    economics: InterventionEconomics,
    thresholds: Sequence[float] = tuple(np.round(np.arange(0.01, 0.21, 0.01), 2)),
) -> pd.DataFrame:
    """Contacts, expected saves and margin at each threshold.

    Expected saves are flagged churners times the assumed intervention success rate.
    Expected margin is saves times retained margin, less the cost of every contact.
    """
    rows = []
    for threshold in thresholds:
        c = confusion_at_threshold(y_true, probability, float(threshold))
        contacts = c["true_positives"] + c["false_positives"]
        saves = c["true_positives"] * economics.intervention_success_rate
        rows.append(
            {
                **c,
                "expected_contacts": contacts,
                "expected_saves": saves,
                "expected_margin": saves * economics.retained_margin_if_successful
                - contacts * economics.contact_cost,
            }
        )
    return pd.DataFrame(rows)


def calibration_table(
    y_true: Sequence[int], probability: Sequence[float], bins: int = 10
) -> pd.DataFrame:
    y, p = _arrays(y_true, probability)
    order = np.argsort(p, kind="stable")
    rows = []
    for index, chunk in enumerate(np.array_split(order, bins), start=1):
        if chunk.size == 0:
            continue
        rows.append(
            {
                "bin": index,
                "n": int(chunk.size),
                "mean_predicted": float(p[chunk].mean()),
                "observed_rate": float(y[chunk].mean()),
                "churners": int(y[chunk].sum()),
            }
        )
    return pd.DataFrame(rows)


def decile_lift(y_true: Sequence[int], probability: Sequence[float]) -> pd.DataFrame:
    y, p = _arrays(y_true, probability)
    order = np.argsort(-p, kind="stable")
    prevalence, total_positive = y.mean(), y.sum()
    rows, captured = [], 0
    for index, chunk in enumerate(np.array_split(order, 10), start=1):
        churners = int(y[chunk].sum())
        captured += churners
        rate = churners / chunk.size
        rows.append(
            {
                "decile": index,
                "n": int(chunk.size),
                "churners": churners,
                "rate": rate,
                "lift": rate / prevalence if prevalence else float("nan"),
                "cumulative_capture": captured / total_positive if total_positive else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def feature_drift(
    train: pd.DataFrame, calibration: pd.DataFrame, test: pd.DataFrame
) -> pd.DataFrame:
    """Standardized mean difference of each numeric feature against the training period."""
    rows = []
    for feature in NUMERIC_FEATURES:
        base = train[feature].dropna()
        spread = float(base.std(ddof=0)) or float("nan")
        for name, part in (("calibration", calibration), ("test", test)):
            values = part[feature].dropna()
            rows.append(
                {
                    "feature": feature,
                    "period": name,
                    "train_mean": float(base.mean()),
                    "period_mean": float(values.mean()),
                    "standardized_shift": (float(values.mean()) - float(base.mean())) / spread,
                    "missing_rate": float(part[feature].isna().mean()),
                }
            )
    for feature in CATEGORICAL_FEATURES:
        base_share = train[feature].value_counts(normalize=True)
        for name, part in (("calibration", calibration), ("test", test)):
            share = part[feature].value_counts(normalize=True)
            top = base_share.index[0]
            rows.append(
                {
                    "feature": f"{feature}={top}",
                    "period": name,
                    "train_mean": float(base_share.iloc[0]),
                    "period_mean": float(share.get(top, 0.0)),
                    "standardized_shift": float("nan"),
                    "missing_rate": float(part[feature].isna().mean()),
                }
            )
    return pd.DataFrame(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_run_artifacts(
    root: Path,
    frame: pd.DataFrame,
    dates: SplitDates,
    economics: InterventionEconomics,
    metrics: dict[str, Any],
    scores: pd.DataFrame,
    model: str,
    parts: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    input_hash: str,
) -> Path:
    """Write everything needed to audit one run under ``root/<run_id>/``."""
    params = {
        "model": model,
        "split_dates": asdict(dates),
        "economics": asdict(economics),
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "label": LABEL,
        "input_sha256": input_hash,
        "input_rows": int(len(frame)),
    }
    run_id = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]
    target = root / run_id
    target.mkdir(parents=True, exist_ok=True)
    y, p = scores[LABEL], scores[f"{model}_risk"]
    threshold = float(metrics[model]["threshold"])
    (target / "params.json").write_text(json.dumps(params, indent=2, sort_keys=True), encoding="utf-8")
    (target / "metrics.json").write_text(
        json.dumps(
            {
                "roc_auc": float(roc_auc_score(y, p)),
                "pr_auc": float(average_precision_score(y, p)),
                "brier_score": float(brier_score_loss(y, p)),
                "class_prevalence_test": float(np.mean(y)),
                "confusion_at_business_threshold": confusion_at_threshold(y, p, threshold),
                "split_rows": {n: int(len(part)) for n, part in zip(("train", "calibration", "test"), parts, strict=True)},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    threshold_sensitivity(y, p, economics).to_csv(target / "threshold_sensitivity.csv", index=False)
    calibration_table(y, p).to_csv(target / "calibration.csv", index=False)
    decile_lift(y, p).to_csv(target / "lift_deciles.csv", index=False)
    feature_drift(*parts).to_csv(target / "feature_drift.csv", index=False)
    hashes = {f.name: _sha256(f) for f in sorted(target.iterdir()) if f.name != "manifest.json"}
    (target / "manifest.json").write_text(
        json.dumps({"run_id": run_id, "files": hashes}, indent=2, sort_keys=True), encoding="utf-8"
    )
    return target

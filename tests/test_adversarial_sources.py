"""Adversarial cases: each test corrupts a small generated dataset in one specific way."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from src.generation.generate import generate
from src.validation.validate_sources import validate


@pytest.fixture()
def raw(tmp_path: Path) -> Path:
    config = tmp_path / "config.yml"
    config.write_text(
        "seed: 23\nstart_date: '2024-01-01'\nend_date: '2024-12-31'\n"
        "accounts: 25\nusage_events: 100\nbase_currency: USD\ncurrencies: {USD: 1.0}\n"
    )
    out = tmp_path / "raw"
    generate(config, out)
    return out


def _mutate(raw: Path, table: str, change: Callable[[pd.DataFrame], pd.DataFrame]) -> None:
    path = raw / f"{table}.csv"
    change(pd.read_csv(path)).to_csv(path, index=False)


def _errors(raw: Path) -> list[str]:
    with pytest.raises(ValueError) as caught:
        validate(raw)
    return json.loads(str(caught.value))["errors"]


def test_clean_dataset_passes(raw: Path) -> None:
    assert validate(raw)["status"] == "passed"


def test_duplicated_subscription_events(raw: Path) -> None:
    _mutate(raw, "fact_subscription_events", lambda f: pd.concat([f, f.head(3)], ignore_index=True))
    assert any("subscription_event_id must be unique" in e for e in _errors(raw))


def test_refund_exceeding_payment(raw: Path) -> None:
    def inflate(frame: pd.DataFrame) -> pd.DataFrame:
        frame.loc[0, "amount"] = 10_000_000.0
        return frame

    _mutate(raw, "fact_refunds", inflate)
    assert any("refunds exceed the original payment" in e for e in _errors(raw))


def test_currency_mismatch_between_invoice_and_subscription(raw: Path) -> None:
    def swap(frame: pd.DataFrame) -> pd.DataFrame:
        frame.loc[0, "currency"] = "EUR"
        return frame

    _mutate(raw, "fact_invoices", swap)
    assert any("currency differs from its subscription" in e for e in _errors(raw))


def test_overlapping_contract_dates(raw: Path) -> None:
    def overlap(frame: pd.DataFrame) -> pd.DataFrame:
        clone = frame.head(1).copy()
        clone["contract_id"] = "C-OVERLAP"
        return pd.concat([frame, clone], ignore_index=True)

    _mutate(raw, "fact_contracts", overlap)
    assert any("contracts overlap within a subscription" in e for e in _errors(raw))


def test_late_arriving_payment_dated_before_invoice(raw: Path) -> None:
    def backdate(frame: pd.DataFrame) -> pd.DataFrame:
        frame.loc[0, "payment_date"] = "1999-01-01"
        return frame

    _mutate(raw, "fact_payments", backdate)
    assert any("dated before their invoice" in e for e in _errors(raw))


def test_missing_dimension_member(raw: Path) -> None:
    _mutate(raw, "dim_plan", lambda f: f.iloc[1:])
    assert any("unknown dim_plan keys" in e for e in _errors(raw))


def test_invalid_date_is_rejected(raw: Path) -> None:
    def corrupt(frame: pd.DataFrame) -> pd.DataFrame:
        frame["invoice_date"] = frame["invoice_date"].astype(object)
        frame.loc[0, "invoice_date"] = "not-a-date"
        return frame

    _mutate(raw, "fact_invoices", corrupt)
    assert any("invoice_date contains invalid dates" in e for e in _errors(raw))

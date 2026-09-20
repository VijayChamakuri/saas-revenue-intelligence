"""The Tableau package: manifest integrity, disclaimers, privacy guard, and the KPI tie-out."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

import pandas as pd
import pytest
import yaml

from src.tableau.build import BANNER, WORKBOOK_FILE, hyper_tieout

TABLEAU = Path("tableau")
needs_package = pytest.mark.skipif(not (TABLEAU / "workbook" / WORKBOOK_FILE).exists(), reason="package not built")


@pytest.fixture(scope="module")
def twb() -> str:
    with zipfile.ZipFile(TABLEAU / "workbook" / WORKBOOK_FILE) as z:
        return z.read(next(n for n in z.namelist() if n.endswith(".twb"))).decode("utf-8")


@needs_package
def test_four_dashboards_in_order(twb) -> None:
    names = re.findall(r'<dashboard name="([^"]+)">', twb)
    assert names == ["Executive overview", "Revenue and retention", "Customer risk", "Finance controls"]


@needs_package
def test_manifest_matches_the_packaged_workbook(twb) -> None:
    manifest = yaml.safe_load((TABLEAU / "workbook_manifest.yml").read_text())
    with zipfile.ZipFile(TABLEAU / "workbook" / WORKBOOK_FILE) as z:
        members = set(z.namelist())
    for ds in manifest["data_sources"]:
        assert ds["extract"] in members and Path(ds["csv"]).exists()
    for sheet in manifest["worksheets"]:
        assert f"<worksheet name={quoteattr(sheet)}>" in twb, sheet
    for dash in manifest["dashboards"]:
        assert set(dash["worksheets"]) <= set(manifest["worksheets"])


@needs_package
def test_a_manifest_naming_a_missing_sheet_is_detected(twb) -> None:
    manifest = yaml.safe_load((TABLEAU / "workbook_manifest.yml").read_text())
    manifest["worksheets"].append("No such sheet")
    assert not all(f"<worksheet name={quoteattr(s)}>" in twb for s in manifest["worksheets"])


@needs_package
def test_every_dashboard_shows_the_synthetic_notice_source_and_refresh(twb) -> None:
    for block in re.findall(r"<dashboard name=.*?</dashboard>", twb, flags=re.S):
        assert BANNER in block and "Source: dbt marts" in block and "Data through" in block
        assert "maxwidth='1366'" in block
    risk = re.search(r'<dashboard name="Customer risk">.*?</dashboard>', twb, flags=re.S).group(0)
    assert "Prioritization aid, not automated action" in risk


@needs_package
def test_extracts_carry_no_personal_fields() -> None:
    for path in (TABLEAU / "data").glob("*.csv"):
        columns = {c.lower() for c in pd.read_csv(path, nrows=1).columns}
        assert not columns & {"customer_name", "account_name", "email", "phone"}, path.name


@needs_package
def test_tieout_passes_and_detects_drift() -> None:
    evidence = pd.read_csv(TABLEAU / "validation_evidence.csv")
    assert evidence["passed"].all()
    expected = pd.read_csv(TABLEAU / "expected_kpis.csv")
    expected.loc[expected.index[0], "expected_value"] += 1
    assert not hyper_tieout(TABLEAU / "workbook" / WORKBOOK_FILE, expected)["passed"].all()


@needs_package
def test_readme_labels_the_data_synthetic_and_claims_no_impact() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    assert "Synthetic data" in text
    for phrase in ("recovered revenue", "reduced churn", "saved $"):
        assert phrase not in text.lower()

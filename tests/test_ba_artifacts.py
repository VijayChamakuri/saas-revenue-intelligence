"""The business-analysis documents: structure, working references, and guarded language.

These documents cite tests and files as evidence. This module fails if a cited path does not exist, if
a cited test is not defined in the file the citation names, if a test is cited without its file, if a
required section is missing, if the synthetic-data caveat is dropped, or if a phrase that would claim
real data or real stakeholder interviews appears without a denial.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

DOCS = REPO / "docs"
CAVEAT = "All project data is synthetic."
REQUIRED_SECTIONS = {
    "user_stories.md": ["# User stories and acceptance criteria", "## US-01", "## US-02"],
    "process_map.md": ["# Process map", "## As-is", "## To-be", "## Step to implementation"],
    "uat_plan.md": ["# User acceptance test plan", "## Exit criteria"],
    "requirements_traceability.md": ["# Requirements traceability matrix", "## Coverage"],
    "gap_analysis.md": ["# Gap analysis", "## Remaining gaps"],
}
# Phrases that would overclaim. Each must be denied on the line where it appears.
GUARDED = ["real customer", "real company", "real revenue", "interviewed", "focus group", "workshop with",
           "power bi", "recovered", "saved", "roi"]
NEGATION = re.compile(r"\b(not|no|never|without|cannot|nor|neither|nothing|none|unless|instead of)\b|n't", re.I)
TEST_NAME = re.compile(r"\btest_[a-z0-9_]+\b(?!\.py)")  # a cited test function, not a module file name
DBT_TEST = re.compile(r"\bassert_[a-z0-9_]+\b")
PATH_REF = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|sql|yml|yaml|csv|json|md|xlsx|pdf|twbx))`")
# A pytest citation names its file and its function, so a real test named in the wrong file fails.
CITATION = re.compile(r"`(tests/[A-Za-z0-9_./-]+\.py)::(test_[a-z0-9_]+)`")


def read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def repo_test_locations() -> dict[str, set[str]]:
    """Every test function in the repository, mapped to the files that define it."""
    where: dict[str, set[str]] = {}
    for path in (REPO / "tests").rglob("test_*.py"):
        for found in re.findall(r"def (test_[a-z0-9_]+)", path.read_text(encoding="utf-8")):
            where.setdefault(found, set()).add(str(path.relative_to(REPO)))
    return where


def repo_dbt_tests() -> set[str]:
    return {p.stem for p in (REPO / "dbt" / "tests").rglob("*.sql")}


def test_stakeholder_roles_are_documented() -> None:
    roles = re.findall(r"\*\*As a\*\* ([^,]+),", read("user_stories.md"))
    documented = read("stakeholder_question_map.md").lower()
    for role in {r.strip().lower() for r in roles}:
        head = role.replace(" analyst", "").replace(" manager", "").strip()
        assert head in documented, f"role not in the stakeholder map: {role}"


@pytest.mark.parametrize("name", sorted(REQUIRED_SECTIONS))
def test_document_exists_with_its_sections_in_order(name: str) -> None:
    text = read(name)
    position = -1
    for heading in REQUIRED_SECTIONS[name]:
        found = text.find(heading)
        assert found >= 0, f"{name}: missing {heading}"
        assert found > position, f"{name}: {heading} is out of order"
        position = found


@pytest.mark.parametrize("name", sorted(REQUIRED_SECTIONS))
def test_document_carries_the_synthetic_caveat(name: str) -> None:
    assert CAVEAT in read(name), name


@pytest.mark.parametrize("name", sorted(REQUIRED_SECTIONS))
def test_every_referenced_path_exists(name: str) -> None:
    for ref in set(PATH_REF.findall(read(name))):
        # A bare document name may be quoted from the BRD, where it means the file next to it in docs/.
        assert (REPO / ref).exists() or (DOCS / ref).exists(), f"{name}: {ref} does not exist"


@pytest.mark.parametrize("name", sorted(REQUIRED_SECTIONS))
def test_every_cited_test_is_defined_in_the_file_it_names(name: str) -> None:
    where, text = repo_test_locations(), read(name)
    for path, func in sorted(set(CITATION.findall(text))):
        assert (REPO / path).exists(), f"{name}: no such test file {path}"
        assert func in where, f"{name}: no such pytest test {func}"
        assert path in where[func], f"{name}: {func} is defined in {sorted(where[func])}, not in {path}"
    for cited in sorted(set(DBT_TEST.findall(text))):
        assert cited in repo_dbt_tests(), f"{name}: no such dbt test {cited}"


@pytest.mark.parametrize("name", sorted(REQUIRED_SECTIONS))
def test_no_pytest_test_is_cited_without_its_file(name: str) -> None:
    """A bare function name cannot be path-checked, so every citation must carry its file."""
    stray = sorted(set(TEST_NAME.findall(CITATION.sub("", read(name)))))
    assert not stray, f"{name}: cite these as `path/to/test_file.py::name` so the path is checked: {stray}"


@pytest.mark.parametrize("name", sorted(REQUIRED_SECTIONS))
def test_guarded_phrases_only_appear_with_a_denial(name: str) -> None:
    for number, line in enumerate(read(name).splitlines(), start=1):
        for phrase in GUARDED:
            if phrase in line.lower():
                assert NEGATION.search(line), f"{name}:{number} uses '{phrase}' without a denial: {line}"


def test_every_story_has_gherkin_criteria_and_evidence() -> None:
    text = read("user_stories.md")
    blocks = re.split(r"\n## (US-\d+)", text)[1:]
    pairs = list(zip(blocks[::2], blocks[1::2], strict=True))
    assert len(pairs) >= 10
    for story, body in pairs:
        assert body.count("**Given**") >= 2, f"{story}: fewer than two acceptance criteria"
        assert "**when**" in body and "**then**" in body, story
        assert "Check:" in body, f"{story}: no executable check named"


def test_traceability_covers_every_functional_requirement() -> None:
    brd = read("business_requirements.md")
    rtm = read("requirements_traceability.md")
    requirements = re.findall(r"^(\d{1,2})\. (.+)$", brd.split("## Functional requirements")[1].split("##")[0], flags=re.M)
    assert len(requirements) == 14, requirements
    for number, text in requirements:
        rid = f"FR-{int(number):02d}"
        assert rid in rtm, f"{rid} is not in the RTM"
        quoted = text.strip().rstrip(".")
        assert quoted[:40] in rtm, f"{rid} text not quoted in the RTM: {quoted[:40]}"
    assert "14 of 14" in rtm


def test_uat_plan_lists_scenarios_with_evidence() -> None:
    rows = [line for line in read("uat_plan.md").splitlines() if line.startswith("| UAT-")]
    assert len(rows) >= 8
    for row in rows:
        assert "tests/" in row or "tableau/" in row or "dashboard/" in row or "dbt " in row, row


def test_gap_analysis_says_not_measured_where_nothing_was_measured() -> None:
    text = read("gap_analysis.md")
    assert text.count("Not measured") >= 2
    assert not re.search(r"\b(saved|savings|roi|return on investment)\b[^.]*\$", text, flags=re.I)

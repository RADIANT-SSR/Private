"""Tests for the scenario-gaps promotion gate in ``scripts/check_org_rules.py`` (CU-387).

Run with the rest of the tooling suite::

    pytest scripts/ -q

The gate exists because the 2026-09-30 external review's top finding had been
independently recorded in **five** scenario ``gaps.md`` files — rated HIGH in
four, with correct physics and a correct impact estimate — and shipped through
v0.2.0 and v0.3.0 anyway, because none of the five reached a governed registry.
The battery checks code; this finding class never reaches code.

Both row shapes in the tree are covered, because CU-387's own first triage pass
grepped only the table shape and missed the vertical one entirely — which is the
argument for machine-checking rather than trusting a reviewer's eye. The last
test runs the real check over the real tree, which is what the gate does.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_org_rules import (  # noqa: E402  (path insert must precede the import)
    check_scenario_gap_promotion,
)

_REL = "scenarios/99_test_persona/99.1_fixture/gaps.md"


@pytest.fixture
def gaps_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A scenario gaps.md at the real relative path, under a temp REPO."""
    import check_org_rules

    target = tmp_path / _REL
    target.parent.mkdir(parents=True)
    monkeypatch.setattr(check_org_rules, "REPO", tmp_path)
    return target


def _write(target: Path, body: str) -> None:
    target.write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# Table shape: | # | Gap | Severity | Status | Evidence |
# ---------------------------------------------------------------------------

_TABLE_HEAD = (
    "## Gap Closure Status\n\n| # | Gap | Severity | Status | Evidence |\n|---|---|---|---|---|\n"
)


class TestTableShape:
    def test_open_without_a_reference_is_reported(self, gaps_file: Path) -> None:
        _write(gaps_file, _TABLE_HEAD + "| 1 | Something is wrong | Medium | Open | reproduced |\n")
        errors = check_scenario_gap_promotion([_REL])
        assert len(errors) == 1
        assert "names no registry home" in errors[0]
        assert _REL in errors[0]

    @pytest.mark.parametrize("ref", ["CU-380", "Gap 134", "GUI-12", "Findings-Log"])
    def test_any_governed_reference_satisfies_it(self, gaps_file: Path, ref: str) -> None:
        _write(
            gaps_file,
            _TABLE_HEAD + f"| 1 | Something is wrong | Medium | Open | reproduced — see {ref} |\n",
        )
        assert check_scenario_gap_promotion([_REL]) == []

    @pytest.mark.parametrize("status", ["FIXED", "RESOLVED", "CLOSED", "DECLINED"])
    def test_settled_rows_need_no_reference(self, gaps_file: Path, status: str) -> None:
        _write(
            gaps_file,
            _TABLE_HEAD + f"| 1 | Something was wrong | Medium | {status} | fixed in place |\n",
        )
        assert check_scenario_gap_promotion([_REL]) == []

    @pytest.mark.parametrize("status", ["WORKAROUND", "BLOCKED", "PARTIAL"])
    def test_other_unsettled_statuses_also_require_one(self, gaps_file: Path, status: str) -> None:
        """A scriptable workaround is not a resolution — RADIANT still lacks it."""
        _write(
            gaps_file,
            _TABLE_HEAD + f"| 1 | Something is wrong | Medium | {status} | script does it |\n",
        )
        assert len(check_scenario_gap_promotion([_REL])) == 1

    def test_the_message_names_the_heading_it_sits_under(self, gaps_file: Path) -> None:
        _write(
            gaps_file,
            "## My Findings Table\n\n"
            "| # | Gap | Severity | Status | Evidence |\n|---|---|---|---|---|\n"
            "| 1 | Something is wrong | Medium | Open | reproduced |\n",
        )
        (error,) = check_scenario_gap_promotion([_REL])
        assert "My Findings Table" in error


# ---------------------------------------------------------------------------
# Vertical shape: | **Status** | OPEN |   (scenarios 10.3 / 10.4)
# ---------------------------------------------------------------------------


class TestVerticalShape:
    def test_open_without_a_reference_is_reported(self, gaps_file: Path) -> None:
        _write(
            gaps_file,
            "## G3 — the thing is broken\n\n| Field | Value |\n|---|---|\n"
            "| **Status** | OPEN |\n| **Severity** | High |\n",
        )
        (error,) = check_scenario_gap_promotion([_REL])
        assert "G3 — the thing is broken" in error

    def test_a_reference_in_the_status_cell_satisfies_it(self, gaps_file: Path) -> None:
        _write(
            gaps_file,
            "## G3 — the thing is broken\n\n| Field | Value |\n|---|---|\n"
            "| **Status** | OPEN — promoted to [[CU-388]] |\n",
        )
        assert check_scenario_gap_promotion([_REL]) == []

    def test_a_resolved_status_needs_no_reference(self, gaps_file: Path) -> None:
        _write(
            gaps_file,
            "## G4 — was broken\n\n| Field | Value |\n|---|---|\n"
            "| **Status** | **RESOLVED** — fixed 2026-08-01 |\n",
        )
        assert check_scenario_gap_promotion([_REL]) == []

    def test_a_workaround_status_requires_one(self, gaps_file: Path) -> None:
        _write(
            gaps_file,
            "## G1 — no door for this\n\n| Field | Value |\n|---|---|\n"
            "| **Status** | WORKAROUND |\n",
        )
        assert len(check_scenario_gap_promotion([_REL])) == 1

    def test_the_workaround_field_label_is_not_a_status(self, gaps_file: Path) -> None:
        """``| **Workaround** | text |`` is a field, not a status value.

        Conflating the two is a mistake CU-387's triage actually made, which
        inflated the apparent backlog by 16 rows.
        """
        _write(
            gaps_file,
            "## G4 — was broken\n\n| Field | Value |\n|---|---|\n"
            "| **Status** | RESOLVED |\n"
            "| **Workaround** | none needed any more |\n",
        )
        assert check_scenario_gap_promotion([_REL]) == []


class TestScope:
    def test_non_scenario_gaps_files_are_ignored(self, gaps_file: Path) -> None:
        """The governed registries carry their own rules; this gate is not them."""
        other = gaps_file.parent / "walkthrough.md"
        other.write_text("| 1 | x | Medium | Open | y |\n", encoding="utf-8")
        rel = str(other.relative_to(gaps_file.parents[3]))
        assert check_scenario_gap_promotion([rel]) == []


class TestTheRealTree:
    def test_every_unresolved_scenario_row_names_its_home(self) -> None:
        """What the gate asserts on this repository, as the battery runs it."""
        import subprocess

        import check_org_rules

        files = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            cwd=check_org_rules.REPO,
            check=True,
        ).stdout.splitlines()
        assert check_org_rules.check_scenario_gap_promotion(files) == []

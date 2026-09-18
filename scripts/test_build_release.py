"""Tests for the pure helpers in ``scripts/build_release.py`` (Support_Documentation_Plan §9).

Run with the rest of the tooling suite::

    pytest scripts/ -q

No test builds a wheel, runs pandoc, or shells out to git — a release build takes minutes
and needs a TeX installation. What is exercised here is the logic that can silently rot
while the build still "succeeds": the tracked-file listing parse, the staging path mapping
(a path-escape bug there writes outside the staging tree), and the wheel-verification
predicate, which is fed synthetic member-name lists including the exact regressions the
first real release build produced.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_release import (  # noqa: E402
    SCENARIO_PREFIX,
    human_size,
    parse_tracked_files,
    staging_targets,
    verify_wheel_names,
)

#: A minimal but complete wheel name list: four volumes, three scenario files, and a
#: couple of ordinary package members. Helpers below perturb it one defect at a time.
PDFS = (
    "radiant/manuals/radiant_theory.pdf",
    "radiant/manuals/radiant_users_guide.pdf",
    "radiant/manuals/radiant_tech_ref.pdf",
    "radiant/manuals/radiant_examples.pdf",
)
SCENARIOS = (
    "radiant/scenarios/README.md",
    "radiant/scenarios/01_sarah/1.1_maritime/run.py",
    "radiant/scenarios/01_sarah/1.1_maritime/inputs/.gitkeep",
)
GOOD_WHEEL = (*PDFS, *SCENARIOS, "radiant/__init__.py", "radiant-0.1.0.dist-info/METADATA")


def check(names: tuple[str, ...], **kwargs: object) -> list[str]:
    """Run the predicate with the fixture's counts unless a test overrides them."""
    params: dict[str, object] = {"scenario_count": len(SCENARIOS), "pdf_count": len(PDFS)}
    params.update(kwargs)
    return verify_wheel_names(names, **params)  # type: ignore[arg-type]


# --- git ls-files parsing -------------------------------------------------------------


def test_parse_tracked_files_splits_on_nul() -> None:
    """``git ls-files -z`` output is NUL-separated with a trailing NUL."""
    assert parse_tracked_files("a/b.yaml\0a/c.py\0") == ["a/b.yaml", "a/c.py"]


def test_parse_tracked_files_empty_output() -> None:
    """An empty listing is an empty list, not a one-element list of ``""``."""
    assert parse_tracked_files("") == []


def test_parse_tracked_files_keeps_spaces_and_newlines_verbatim() -> None:
    """The reason for ``-z``: git's newline form would quote and escape these."""
    assert parse_tracked_files("a/with space.md\0a/odd\nname.md\0") == [
        "a/with space.md",
        "a/odd\nname.md",
    ]


# --- staging path mapping -------------------------------------------------------------


def test_staging_targets_strips_prefix_and_preserves_depth() -> None:
    repo = Path("/repo")
    staged = Path("/repo/src/radiant/scenarios")
    pairs = staging_targets(
        ["scenarios/01_sarah/1.1_maritime/inputs/a.yaml", "scenarios/README.md"], repo, staged
    )
    assert pairs == [
        (
            repo / "scenarios/01_sarah/1.1_maritime/inputs/a.yaml",
            staged / "01_sarah/1.1_maritime/inputs/a.yaml",
        ),
        (repo / "scenarios/README.md", staged / "README.md"),
    ]


def test_staging_targets_rejects_entry_outside_prefix() -> None:
    """A listing that strayed outside scenarios/ must not be copied into the package."""
    with pytest.raises(ValueError, match="outside"):
        staging_targets(["docs/index.md"], Path("/repo"), Path("/staged"))


@pytest.mark.parametrize("entry", ["scenarios/../secrets.txt", "scenarios/"])
def test_staging_targets_rejects_escapes_and_bare_prefix(entry: str) -> None:
    """``..`` would write outside the staging tree; the bare prefix names no file."""
    with pytest.raises(ValueError):
        staging_targets([entry], Path("/repo"), Path("/staged"))


def test_staging_targets_prefix_is_the_module_constant() -> None:
    """The default prefix is the canonical suite root, not a copy that can drift."""
    assert SCENARIO_PREFIX == "scenarios/"


# --- wheel verification ---------------------------------------------------------------


def test_verify_wheel_names_accepts_a_good_wheel() -> None:
    assert check(GOOD_WHEEL) == []


def test_verify_wheel_names_flags_missing_volume() -> None:
    names = tuple(n for n in GOOD_WHEEL if n != PDFS[1])
    problems = check(names)
    assert any("expected 4 PDF(s)" in p for p in problems)


def test_verify_wheel_names_flags_stray_non_pdf_under_manuals() -> None:
    problems = check((*GOOD_WHEEL, "radiant/manuals/notes.txt"))
    assert any("non-PDF" in p for p in problems)


def test_verify_wheel_names_flags_dropped_gitkeep_placeholders() -> None:
    """The real first-build regression: `scenarios/**/*` never matches a leading dot."""
    names = tuple(n for n in GOOD_WHEEL if not n.endswith(".gitkeep"))
    problems = check(names)
    assert any("scenario file(s)" in p and "found 2" in p for p in problems)


def test_verify_wheel_names_flags_pycache_and_bytecode() -> None:
    problems = check(
        (
            *GOOD_WHEEL,
            "radiant/scenarios/01_sarah/__pycache__/run.cpython-311.pyc",
        ),
        scenario_count=len(SCENARIOS) + 1,
    )
    assert any("__pycache__" in p for p in problems)
    assert any("bytecode" in p for p in problems)


def test_verify_wheel_names_flags_scenario_package_init() -> None:
    """An ``__init__.py`` would make the scenario data an importable subpackage."""
    problems = check(
        (*GOOD_WHEEL, "radiant/scenarios/__init__.py"), scenario_count=len(SCENARIOS) + 1
    )
    assert any("not a package" in p for p in problems)


def test_verify_wheel_names_tolerates_package_init_outside_scenarios() -> None:
    """``radiant/__init__.py`` is in the good fixture — the check is scoped, not global."""
    assert "radiant/__init__.py" in GOOD_WHEEL
    assert check(GOOD_WHEEL) == []


def test_verify_wheel_names_flags_missing_spot_key() -> None:
    problems = check(GOOD_WHEEL, spot_keys=("radiant/scenarios/MISSING.md",))
    assert any("absent from the wheel" in p for p in problems)


def test_verify_wheel_names_reports_every_defect_at_once() -> None:
    """A release build should show the whole picture, not the first failure."""
    problems = verify_wheel_names(("radiant/scenarios/a.py",), scenario_count=5, pdf_count=4)
    assert len(problems) >= 3


# --- formatting -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("num_bytes", "expected"),
    [(0, "0 B"), (512, "512 B"), (2048, "2.0 KB"), (5 * 1024**2, "5.0 MB")],
)
def test_human_size(num_bytes: int, expected: str) -> None:
    assert human_size(num_bytes) == expected

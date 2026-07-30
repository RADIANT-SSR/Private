"""Tests for the cited-commit ancestry gate in ``scripts/check_org_rules.py`` (CU-279).

Run with the rest of the tooling suite::

    pytest scripts/ -q

The extraction and ancestry logic is exercised against a hand-built prefix index
so the tests do not depend on this repository's history; two tests at the end run
the real check over the real registries, which is what the gate itself does.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_org_rules import (  # noqa: E402  (path insert must precede the import)
    REPO,
    ancestor_index,
    check_cited_shas,
)

#: Two fabricated "ancestors" whose 7-char prefixes differ.
_ON_MAIN = (
    "abcdef1234567890abcdef1234567890abcdef12",
    "0f1e2d3c4b5a69788796a5b4c3d2e1f009182736",
)


@pytest.fixture
def index() -> dict[str, list[str]]:
    """Prefix index for :data:`_ON_MAIN`, in the shape ``ancestor_index`` returns."""
    out: dict[str, list[str]] = {}
    for full in _ON_MAIN:
        out.setdefault(full[:7], []).append(full)
    return out


def test_an_abbreviated_ancestor_passes(index: dict[str, list[str]]) -> None:
    assert check_cited_shas("RESOLVED, commit `abcdef1`.", index, "reg.md") == []


def test_a_full_length_ancestor_passes(index: dict[str, list[str]]) -> None:
    assert check_cited_shas(f"commit `{_ON_MAIN[0]}`.", index, "reg.md") == []


def test_an_intermediate_length_ancestor_passes(index: dict[str, list[str]]) -> None:
    """A 10-char abbreviation is keyed on 7 chars, then prefix-matched in full."""
    assert check_cited_shas("commit `abcdef12345`.", index, "reg.md") == []


def test_a_non_ancestor_is_reported(index: dict[str, list[str]]) -> None:
    errors = check_cited_shas("RESOLVED, commit `452cccd`.", index, "reg.md")
    assert len(errors) == 1
    assert "452cccd" in errors[0]
    assert "reg.md" in errors[0]
    assert "not an ancestor of HEAD" in errors[0]
    # Rule 15: the message must say what to do about it, both ways out.
    assert "(not on main)" in errors[0]
    assert "grep" in errors[0]


def test_object_existence_is_not_the_test(index: dict[str, list[str]]) -> None:
    """The three CU-279 hashes are real objects in this repo; ancestry still fails.

    This is the whole point of the check — ``git cat-file -t`` passes on all of
    them, so a check written against object existence would have found nothing.
    """
    for sha in ("452cccd", "c2634b6", "97eafb6"):
        kind = subprocess.run(
            ["git", "cat-file", "-t", sha], capture_output=True, text=True, cwd=REPO
        )
        if kind.returncode != 0:  # pragma: no cover — object garbage-collected
            pytest.skip(f"{sha} has been garbage-collected; ancestry semantics unchanged")
        assert kind.stdout.strip() == "commit"
        assert check_cited_shas(f"commit `{sha}`.", ancestor_index(), "reg.md") != []


def test_the_off_main_marker_exempts_a_hash(index: dict[str, list[str]]) -> None:
    text = "landed as `abcdef1` (cherry-picked from original commit `452cccd` (not on main))"
    assert check_cited_shas(text, index, "reg.md") == []


def test_the_marker_must_immediately_follow_the_hash(index: dict[str, list[str]]) -> None:
    """A marker further down the sentence does not exempt — no action at a distance."""
    text = "original commit `452cccd`, which is (not on main)"
    assert len(check_cited_shas(text, index, "reg.md")) == 1


def test_a_decimal_literal_in_backticks_is_not_a_sha(index: dict[str, list[str]]) -> None:
    """``999999999999`` is a bounds-test value the backlog quotes, not a commit."""
    assert check_cited_shas("`_try_resolve` rejects `999999999999`.", index, "reg.md") == []


def test_a_hash_shorter_than_git_abbreviates_is_not_matched(index: dict[str, list[str]]) -> None:
    """Six hex chars is below git's minimum abbreviation — likelier prose than a SHA."""
    assert check_cited_shas("the `abc123` marker", index, "reg.md") == []


def test_each_offender_is_reported_once(index: dict[str, list[str]]) -> None:
    text = "commit `452cccd` ... see also commit `452cccd` ... and commit `c2634b6`"
    errors = check_cited_shas(text, index, "reg.md")
    assert len(errors) == 2


def test_hashes_are_extracted_outside_the_word_commit(index: dict[str, list[str]]) -> None:
    """The forms a word-anchored regex would skip: bare lists, labels, prose."""
    text = "RESOLVED (commits `abcdef1` 3.1, `452cccd` 5.2); cherry-picked `c2634b6` as `0f1e2d3`"
    assert sorted(e.split("`")[1] for e in check_cited_shas(text, index, "reg.md")) == [
        "452cccd",
        "c2634b6",
    ]


@pytest.mark.parametrize("registry", ["Cleanup_Backlog.md", "gaps.md"])
def test_the_live_registries_cite_only_ancestors(registry: str) -> None:
    """The gate's own assertion, as a test: no dangling closure link in either registry."""
    path = REPO / "docs" / "tracking" / registry
    errors = check_cited_shas(path.read_text(encoding="utf-8"), ancestor_index(), registry)
    assert errors == [], "\n".join(errors)


def test_the_ancestor_index_is_keyed_on_seven_chars() -> None:
    index = ancestor_index()
    assert index, "git rev-list HEAD returned no commits"
    for prefix, fulls in index.items():
        assert len(prefix) == 7
        assert all(len(f) == 40 and f.startswith(prefix) for f in fulls)

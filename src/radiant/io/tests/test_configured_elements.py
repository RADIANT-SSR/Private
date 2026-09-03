"""Tests for configured rows in the ``optical_elements`` document (Gap 103 v1.1).

The io-level syntax layer of `docs/plans/Configuration_Set_Expansion_Plan.md`
§3a-bis (owner-ratified 2026-09-02, live review): an element row carries one
complete entry per configuration, written in place as ``- configured: {...}``.
Every binding rule is checked at load with a `ConfigError` naming the row
position and, where it applies, the configuration.

End-to-end persistence through `ConfigurationSet.save`/`load` is
`test_config_set_persistence.py`; the model operations are
`api/tests/test_config_set.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from radiant.io.config import ConfigError
from radiant.io.configured_elements import (
    CONFIGURED_KEY,
    configured_rows_need_a_configuration_set,
    has_configured_rows,
    is_configured_row,
    merge_element_document,
    resolve_element_document,
    split_element_document,
)

_MEMBERS = ("A", "B")


def _mirror(name: str = "M1", **fields: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": name,
        "transfer_mode": "REFLECTIVE",
        "reflectance": 0.97,
        "temperature_K": 293.0,
    }
    entry.update(fields)
    return entry


def _filter(name: str = "band_filter", **fields: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": name,
        "transfer_mode": "REFRACTIVE",
        "kind": "FILTER",
        "transmittance": 0.90,
        "temperature_K": 240.0,
    }
    entry.update(fields)
    return entry


def _configured(**by_member: dict[str, Any]) -> dict[str, Any]:
    return {CONFIGURED_KEY: dict(by_member)}


@pytest.mark.level0
class TestRowDetection:
    def test_is_configured_row(self) -> None:
        assert is_configured_row(_configured(A=_filter(), B=_filter()))
        assert not is_configured_row(_filter())
        assert not is_configured_row("not a mapping")

    def test_has_configured_rows(self) -> None:
        assert has_configured_rows([_mirror(), _configured(A=_filter(), B=_filter())])
        assert not has_configured_rows([_mirror(), _filter()])

    def test_a_malformed_document_answers_false_rather_than_raising(self) -> None:
        """It is the dispatch question, asked before the document is validated."""
        assert not has_configured_rows(None)
        assert not has_configured_rows("optical_elements")
        assert not has_configured_rows({"name": "M1"})


@pytest.mark.level0
class TestSplit:
    def test_shared_and_configured_rows_are_separated_by_position(self) -> None:
        doc = split_element_document(
            [_mirror(), _configured(A=_filter(), B=_filter(transmittance=0.4)), _mirror("M2")],
            member_names=_MEMBERS,
        )
        assert [e["name"] for e in doc.shared] == ["M1", "M2"]
        assert set(doc.configured) == {1}
        assert doc.length == 3
        assert doc.configured[1]["B"]["transmittance"] == pytest.approx(0.4, rel=1e-12)

    def test_a_document_with_no_configured_row_splits_to_all_shared(self) -> None:
        doc = split_element_document([_mirror(), _filter()], member_names=_MEMBERS)
        assert len(doc.shared) == 2 and doc.configured == {}

    def test_every_row_may_be_configured(self) -> None:
        doc = split_element_document(
            [_configured(A=_mirror(), B=_mirror()), _configured(A=_filter(), B=_filter())],
            member_names=_MEMBERS,
        )
        assert doc.shared == () and set(doc.configured) == {0, 1}
        assert doc.length == 2

    def test_entries_are_validated_through_the_element_parser(self) -> None:
        """One authority: the same parse the shared rows face."""
        bad = {"name": "band_filter", "transfer_mode": "REFRACTIVE"}  # no transmittance
        with pytest.raises(ConfigError) as exc:
            split_element_document(
                [_mirror(), _configured(A=_filter(), B=bad)], member_names=_MEMBERS
            )
        msg = str(exc.value)
        assert "row 1" in msg and "configuration 'B'" in msg and "transmittance" in msg

    def test_kirchhoff_violation_is_caught_at_load_naming_the_member(self) -> None:
        with pytest.raises(ConfigError) as exc:
            split_element_document(
                [_configured(A=_mirror(), B=_mirror(reflectance=1.5))], member_names=_MEMBERS
            )
        msg = str(exc.value)
        assert "row 0" in msg and "configuration 'B'" in msg

    def test_missing_member_is_a_density_error(self) -> None:
        with pytest.raises(ConfigError) as exc:
            split_element_document(
                [_mirror(), {CONFIGURED_KEY: {"A": _filter()}}], member_names=_MEMBERS
            )
        msg = str(exc.value)
        assert "row 1" in msg and "missing ['B']" in msg and "dense" in msg

    def test_unknown_member_key_is_a_density_error(self) -> None:
        with pytest.raises(ConfigError) as exc:
            split_element_document(
                [_configured(A=_filter(), B=_filter(), SWIR=_filter())], member_names=_MEMBERS
            )
        msg = str(exc.value)
        assert "row 0" in msg and "unknown ['SWIR']" in msg

    def test_sibling_key_beside_configured_is_refused(self) -> None:
        row = _configured(A=_filter(), B=_filter())
        row["temperature_K"] = 240.0
        with pytest.raises(ConfigError) as exc:
            split_element_document([row], member_names=_MEMBERS)
        assert "sibling key(s) 'temperature_K'" in str(exc.value)

    def test_configured_value_must_be_a_mapping(self) -> None:
        with pytest.raises(ConfigError, match="must be a mapping of configuration name"):
            split_element_document([{CONFIGURED_KEY: [_filter()]}], member_names=_MEMBERS)

    def test_a_member_entry_must_be_a_mapping(self) -> None:
        with pytest.raises(ConfigError) as exc:
            split_element_document(
                [{CONFIGURED_KEY: {"A": _filter(), "B": "filter.csv"}}], member_names=_MEMBERS
            )
        assert "configuration 'B'" in str(exc.value)

    def test_a_shared_row_must_be_a_mapping(self) -> None:
        with pytest.raises(ConfigError, match="row 1 must be a mapping"):
            split_element_document([_mirror(), ["not", "a", "row"]], member_names=_MEMBERS)

    def test_document_must_be_a_list(self) -> None:
        with pytest.raises(ConfigError, match="must be a list of element rows"):
            split_element_document({"name": "M1"}, member_names=_MEMBERS)

    def test_a_configured_row_without_a_configuration_set_is_refused(self) -> None:
        with pytest.raises(ConfigError, match="ConfigurationSet.load"):
            split_element_document([_configured(A=_filter(), B=_filter())], member_names=None)

    def test_path_is_named_in_every_error(self) -> None:
        with pytest.raises(ConfigError) as exc:
            split_element_document(
                [{CONFIGURED_KEY: {"A": _filter()}}],
                member_names=_MEMBERS,
                path=Path("study.yaml"),
            )
        assert "study.yaml" in str(exc.value)


@pytest.mark.level0
class TestResolveAndMerge:
    def test_resolve_walks_the_full_document_in_order(self) -> None:
        doc = split_element_document(
            [
                _mirror(),
                _configured(A=_filter(), B=_filter(name="filter_b", transmittance=0.4)),
                _mirror("M2"),
            ],
            member_names=_MEMBERS,
        )
        train_a = resolve_element_document(doc.shared, doc.configured, "A")
        train_b = resolve_element_document(doc.shared, doc.configured, "B")
        assert [e["name"] for e in train_a] == ["M1", "band_filter", "M2"]
        assert [e["name"] for e in train_b] == ["M1", "filter_b", "M2"]

    def test_resolved_entries_are_copies(self) -> None:
        doc = split_element_document([_configured(A=_filter(), B=_filter())], member_names=_MEMBERS)
        resolve_element_document(doc.shared, doc.configured, "A")[0]["transmittance"] = 0.0
        assert doc.configured[0]["A"]["transmittance"] == pytest.approx(0.90, rel=1e-12)

    def test_merge_is_the_inverse_of_split(self) -> None:
        entries = [
            _mirror(),
            _configured(A=_filter(), B=_filter(transmittance=0.4)),
            _mirror("M2"),
        ]
        doc = split_element_document(entries, member_names=_MEMBERS)
        assert merge_element_document(doc.shared, doc.configured) == entries

    def test_merge_places_configured_rows_at_their_positions(self) -> None:
        doc = split_element_document(
            [_configured(A=_mirror(), B=_mirror()), _filter()], member_names=_MEMBERS
        )
        merged = merge_element_document(doc.shared, doc.configured)
        assert CONFIGURED_KEY in merged[0] and merged[1]["name"] == "band_filter"


@pytest.mark.level1
class TestSpectralFilePathParity:
    """CU-177: resolve on load, relativize on save — as configured values do."""

    @staticmethod
    def _csv(path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("3.0,0.40\n5.0,0.45\n", encoding="utf-8")
        return path

    def test_relative_references_resolve_against_the_config_dir(self, tmp_path: Path) -> None:
        cfg = tmp_path / "cfg"
        self._csv(cfg / "coating.csv")
        doc = split_element_document(
            [_configured(A=_filter(), B=_filter(transmittance="coating.csv"))],
            member_names=_MEMBERS,
            base_dir=cfg,
        )
        assert Path(doc.configured[0]["B"]["transmittance"]) == (cfg / "coating.csv").resolve()

    def test_a_missing_spectral_file_fails_at_load(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError) as exc:
            split_element_document(
                [_configured(A=_filter(), B=_filter(transmittance="nope.csv"))],
                member_names=_MEMBERS,
                base_dir=tmp_path,
            )
        assert "configuration 'B'" in str(exc.value)

    def test_absolute_references_relativize_on_merge(self, tmp_path: Path) -> None:
        csv = self._csv(tmp_path / "data" / "coating.csv")
        doc = split_element_document(
            [_configured(A=_filter(), B=_filter(transmittance=str(csv.resolve())))],
            member_names=_MEMBERS,
        )
        merged = merge_element_document(doc.shared, doc.configured, relative_to=tmp_path / "cfg")
        # Forward slashes on both platforms (Rule 30).
        assert merged[0][CONFIGURED_KEY]["B"]["transmittance"] == "../data/coating.csv"

    def test_scalars_are_untouched_by_relativize(self, tmp_path: Path) -> None:
        doc = split_element_document([_configured(A=_filter(), B=_filter())], member_names=_MEMBERS)
        merged = merge_element_document(doc.shared, doc.configured, relative_to=tmp_path)
        assert merged[0][CONFIGURED_KEY]["B"]["transmittance"] == pytest.approx(0.90, rel=1e-12)

    def test_merge_without_a_destination_leaves_paths_as_stored(self, tmp_path: Path) -> None:
        csv = self._csv(tmp_path / "data" / "coating.csv")
        doc = split_element_document(
            [_configured(A=_filter(), B=_filter(transmittance=str(csv.resolve())))],
            member_names=_MEMBERS,
        )
        merged = merge_element_document(doc.shared, doc.configured)
        assert merged[0][CONFIGURED_KEY]["B"]["transmittance"] == str(csv.resolve())


@pytest.mark.level0
def test_refusal_error_names_the_loader_that_can_read_the_file() -> None:
    exc = configured_rows_need_a_configuration_set(Path("study.yaml"))
    msg = str(exc)
    assert "study.yaml" in msg and "ConfigurationSet.load(path)" in msg

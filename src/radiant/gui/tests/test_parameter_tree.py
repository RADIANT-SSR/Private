"""Schema-driven parameter tree tests (GUI plan Phase 2, Task A — read-only).

These prove the tree is generated *entirely* from ``Sensor.parameter_defs()`` and the
resolved set — never a hand-listed parameter name (Gap 70). Every expected value is
derived from the live API inside the test, so the assertions cannot drift from the
schema. A real example YAML populates the tree; the pure ``param_format`` helpers are
unit-tested without a widget.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from radiant.api.sensor import Sensor
from radiant.gui import param_format
from radiant.gui.param_format import (
    DERIVED_BADGE,
    UNSET_TEXT,
    format_value,
    ordered_namespaces,
    provenance_label,
    safe_provenance,
)
from radiant.gui.widgets.parameter_panel import ParameterPanel

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture
def sensor() -> Sensor:
    """A Sensor loaded from a real example config (resolves cleanly)."""
    return Sensor.from_yaml(_EXAMPLE)


@pytest.fixture
def panel(sensor: Sensor, qtbot) -> ParameterPanel:  # type: ignore[no-untyped-def]
    """A ParameterPanel populated from the example sensor."""
    p = ParameterPanel()
    qtbot.addWidget(p)
    p.populate(sensor)
    return p


class TestSchemaMatch:
    def test_every_def_appears_exactly_once(self, panel: ParameterPanel, sensor: Sensor) -> None:
        """Both directions: schema dot-paths == tree rows, one-to-one, no extras."""
        expected = set(sensor.parameter_defs())
        assert panel.row_dotpaths() == expected
        # Exactly once: leaf-item count equals the schema size (no duplicate rows).
        total_leaves = sum(
            panel.tree.topLevelItem(i).childCount() for i in range(panel.tree.topLevelItemCount())
        )
        assert total_leaves == len(expected)

    def test_every_row_maps_back_to_a_def(self, panel: ParameterPanel, sensor: Sensor) -> None:
        """No tree row exists that the schema does not define."""
        defs = sensor.parameter_defs()
        for dotpath in panel.row_dotpaths():
            assert dotpath in defs

    def test_namespaces_geometry_first_chain_order(
        self, panel: ParameterPanel, sensor: Sensor
    ) -> None:
        """Top-level groups are the schema namespaces, geometry first, chain order."""
        groups = [panel.tree.topLevelItem(i).text(0) for i in range(panel.tree.topLevelItemCount())]
        assert groups == ordered_namespaces(sensor.parameter_defs().keys())
        assert groups[0] == "geometry"


class TestRowRendering:
    def test_dimensional_rows_carry_their_unit(self, panel: ParameterPanel, sensor: Sensor) -> None:
        """Every dimensional value row shows its schema unit suffix (R-UNITS)."""
        checked = 0
        for dotpath, pdef in sensor.parameter_defs().items():
            if not pdef.input_unit:
                continue
            text = panel.value_text(dotpath)
            if text == UNSET_TEXT or text.endswith(UNSET_TEXT):
                continue  # unresolved (required-unless superseded) — no value/unit
            assert pdef.input_unit in text, f"{dotpath}: unit {pdef.input_unit!r} missing"
            # The rendered value equals the formatting helper's output.
            expected = format_value(sensor.get_input(dotpath), pdef.input_unit)
            assert text.endswith(expected)
            checked += 1
        assert checked > 0  # the example has dimensional parameters

    def test_derived_rows_are_badged(self, panel: ParameterPanel) -> None:
        """Rows whose provenance is 'derived' carry the ⚡ marker (§4.3)."""
        derived = [dp for dp in panel.row_dotpaths() if panel.source_text(dp) == "derived"]
        assert derived, "the example config has at least one derived parameter"
        for dotpath in derived:
            assert panel.value_text(dotpath).startswith(DERIVED_BADGE)

    def test_editability_follows_derived_flag(self, panel: ParameterPanel) -> None:
        """Task B: non-derived leaves are editable; derived (⚡) leaves are not."""
        for dotpath in panel.row_dotpaths():
            derived = panel.source_text(dotpath) == "derived"
            assert panel.is_editable(dotpath) is (not derived), dotpath

    def test_provenance_labels_from_resolved_set(
        self, panel: ParameterPanel, sensor: Sensor
    ) -> None:
        """Each Source cell matches the provenance from the structured accessor."""
        for dotpath in panel.row_dotpaths():
            token = safe_provenance(sensor, dotpath)
            assert panel.source_text(dotpath) == provenance_label(token)


class TestFilter:
    def test_filter_enabled_after_populate(self, panel: ParameterPanel) -> None:
        """Populating enables the live filter box."""
        assert panel.filter_box.isEnabled()

    def test_filter_narrows_and_restores(self, panel: ParameterPanel, sensor: Sensor) -> None:
        """A substring narrows the visible rows; clearing restores the full tree."""
        namespace = ordered_namespaces(sensor.parameter_defs().keys())[0]  # "geometry"
        full = panel.row_dotpaths()

        panel.filter_box.setText(namespace)
        visible = panel.visible_dotpaths()
        assert visible  # some rows match
        assert visible < full  # strictly fewer
        assert all(namespace in dp for dp in visible)

        panel.filter_box.setText("")
        assert panel.visible_dotpaths() == full

    def test_filter_no_match_hides_everything(self, panel: ParameterPanel) -> None:
        """A query matching nothing hides all rows (and their groups)."""
        panel.filter_box.setText("zzz_no_such_parameter_zzz")
        assert panel.visible_dotpaths() == set()


class TestEmptyState:
    def test_bare_panel_shows_empty_state(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """No sensor → the themed 'no configuration loaded' state, no rows."""
        p = ParameterPanel()
        qtbot.addWidget(p)
        p.populate(None)
        assert p.row_dotpaths() == set()
        assert not p.tree.isVisible()
        assert not p.filter_box.isEnabled()

    def test_repopulate_replaces_rows(self, panel: ParameterPanel, sensor: Sensor) -> None:
        """Re-populating from None clears a previously populated tree."""
        assert panel.row_dotpaths()  # populated by fixture
        panel.populate(None)
        assert panel.row_dotpaths() == set()


class TestParamFormatHelpers:
    """Pure-function contract for the presentation helpers (no widget)."""

    def test_format_value_dimensional(self) -> None:
        assert format_value(0.3, "m") == "0.3 m"
        assert format_value(500000.0, "m") == "500000 m"

    def test_format_value_dimensionless(self) -> None:
        assert format_value(4.0, "") == "4"

    def test_format_value_bool_and_none(self) -> None:
        assert format_value(True, "") == "true"
        assert format_value(None, "m") == UNSET_TEXT

    def test_provenance_label_maps_tokens(self) -> None:
        assert provenance_label("config_file") == "config"
        assert provenance_label("user_set") == "user-set"

    def test_provenance_label_absent(self) -> None:
        assert provenance_label(None) == ""
        assert provenance_label("") == ""

    def test_safe_provenance_empty_for_unresolved_sensor(self) -> None:
        """CU-105: an unresolvable sensor yields "" (not a crash) via safe_provenance."""
        from radiant.api.sensor import Sensor

        blank = Sensor()  # required params unset → cannot resolve
        assert safe_provenance(blank, "optics.aperture_diameter_m") == ""

    def test_namespace_order_matches_chain(self) -> None:
        """Ordering is chain-derived; unknown namespaces append in sorted order."""
        chain = param_format.chain_namespace_order()
        assert chain[0] == "geometry"
        got = ordered_namespaces(["optics.d", "geometry.a", "zzz.q", "source.s"])
        assert got[0] == "geometry"
        assert got.index("source") < got.index("optics")
        assert got[-1] == "zzz"  # unknown namespace appended last

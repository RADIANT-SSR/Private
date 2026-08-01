"""Tests for the Geometry screen's site-elevation card (CU-301).

``geometry.site_elevation_m`` is results-affecting (it moves the Hufnagel-Valley Cn²
surface term, CU-262) and is deliberately outside the mode manifest — the schema tags it
``non_mode`` — so before this card it was reachable only from YAML or the scripting API.
The contracts driven here, on the real widget over the shipped example config, offscreen:

* the Geometry **Inputs** tab declares the card, and the pane builds it below the mode
  forms (the doors are typed first, then the standalone scene fact);
* the field **renders** the live value with its unit — every displayed value carries one;
* entry and display are **symmetric in a non-default unit**: the row shows km, the editor
  opens in km, a km number typed in lands as the right number of metres, and the row reads
  the km value back — no mental arithmetic anywhere (display-units rule);
* an accepted edit is exactly **one** ``sensor.set`` on the live sensor plus one
  ``parameterEdited`` emission, so results go stale and the host re-evaluates (the shared
  Parameter Editor's validate-on-a-clone reject path, identical to every other field);
* the value **round-trips** to the ``Sensor`` — the card is a view, not a second store;
* the **manifest exclusion is untouched**: adding a GUI entry point did not put the
  parameter into a mode family, which ``geometry/tests/test_mode_manifest.py`` and
  ``gui/tests/test_geometry_screen.py`` both derive from the ``non_mode`` tag.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.geometry_modes import all_mode_params  # noqa: E402
from radiant.gui.param_format import display_in_unit  # noqa: E402
from radiant.gui.stage_views import STAGE_COMPOSITIONS  # noqa: E402
from radiant.gui.widgets import site_elevation_panel as sep  # noqa: E402
from radiant.gui.widgets.field_row import UNSET  # noqa: E402
from radiant.gui.widgets.geometry_mode_form import GeometryModeForm  # noqa: E402
from radiant.gui.widgets.site_elevation_panel import (  # noqa: E402
    SITE_ELEVATION_PARAM,
    SiteElevationPanel,
)
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 15000

# A real elevated site: Mauna Kea, 4207 m MSL — the CU-262 mountain-top observatory case.
_MAUNA_KEA_M = 4207.0


@pytest.fixture(scope="module")
def sensor() -> Sensor:
    """A sensor loaded from the shipped example config (read-only in these tests)."""
    return Sensor.load(_EXAMPLE)


def _panel(  # type: ignore[no-untyped-def]
    qtbot,
    sensor: Sensor | None = None,
    display_units: dict[str, str] | None = None,
) -> SiteElevationPanel:
    """A card bound to *sensor* (or unbound) with the given display-unit store."""
    panel = SiteElevationPanel()
    qtbot.addWidget(panel)
    panel.bind_sensor(sensor, {} if display_units is None else display_units)
    return panel


# ---------------------------------------------------------------------------
# Rendering — the field exists and always carries its unit
# ---------------------------------------------------------------------------


class TestRendering:
    def test_the_card_carries_the_site_elevation_row(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        panel = _panel(qtbot, sensor)
        assert panel.field_row.dotpath == SITE_ELEVATION_PARAM

    def test_the_default_value_renders_with_its_unit(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """The schema default (0 m MSL) shows as a number AND a unit, never bare."""
        panel = _panel(qtbot, sensor)
        assert panel.value_text() == "0 m"

    def test_a_set_value_renders_with_its_unit(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        live = Sensor.load(_EXAMPLE)
        live.set(SITE_ELEVATION_PARAM, _MAUNA_KEA_M)
        panel = _panel(qtbot, live)
        assert panel.value_text() == "4207 m"

    def test_no_sensor_shows_the_unset_marker(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Pre-config (File → New before a load): a visible unset state, not a fake 0."""
        assert _panel(qtbot, None).value_text() == UNSET

    def test_refresh_picks_up_a_value_set_elsewhere(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A value typed in the parameter tree shows here on the shared refresh beat."""
        live = Sensor.load(_EXAMPLE)
        panel = _panel(qtbot, live)
        assert panel.value_text() == "0 m"
        live.set(SITE_ELEVATION_PARAM, 1500.0)
        panel.refresh()
        assert panel.value_text() == "1500 m"


# ---------------------------------------------------------------------------
# Display units — entry and display symmetric, no mental arithmetic
# ---------------------------------------------------------------------------


class TestDisplayUnits:
    def test_the_row_shows_the_chosen_non_default_unit(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """With km chosen for the row, 4207 m reads as 4.207 km — value AND unit."""
        live = Sensor.load(_EXAMPLE)
        live.set(SITE_ELEVATION_PARAM, _MAUNA_KEA_M)
        panel = _panel(qtbot, live, {SITE_ELEVATION_PARAM: "km"})
        expected = display_in_unit(_MAUNA_KEA_M, "m", "km", "m")
        assert panel.value_text() == f"{expected:g} km"
        assert panel.value_text().endswith(" km")

    def test_the_editor_opens_in_the_rows_chosen_unit(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Symmetry, half one: the editor is handed the unit the row is displaying."""
        live = Sensor.load(_EXAMPLE)
        live.set(SITE_ELEVATION_PARAM, _MAUNA_KEA_M)
        panel = _panel(qtbot, live, {SITE_ELEVATION_PARAM: "km"})
        seen: list[str | None] = []

        def capture_exec(self):  # type: ignore[no-untyped-def]
            assert self.unit_combo is not None
            seen.append(str(self.unit_combo.currentData()))
            # The editor is pre-filled with the km number, not the metre one.
            expected_km = display_in_unit(_MAUNA_KEA_M, "m", "km", "m")
            assert float(self.value_editor.text()) == pytest.approx(expected_km, rel=1e-12)
            return 0

        monkeypatch.setattr(sep.ParameterEditorDialog, "exec", capture_exec)
        panel._open_editor(SITE_ELEVATION_PARAM)  # noqa: SLF001
        assert seen == ["km"]

    def test_a_value_entered_in_km_lands_as_metres_and_reads_back_as_km(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """Symmetry, the whole loop: type 2.5 km, the sensor holds 2500 m, the row says km.

        This is the display-units rule end to end — the operator never converts. The
        canonical value is asserted on the public ``Sensor`` surface, so a card that
        merely *displayed* km while storing 2.5 would fail here.
        """
        live = Sensor.load(_EXAMPLE)
        panel = _panel(qtbot, live, {SITE_ELEVATION_PARAM: "km"})

        def fake_exec(self):  # type: ignore[no-untyped-def]
            assert self.unit_combo is not None and self.unit_combo.currentData() == "km"
            self.value_editor.setText("2.5")
            self.apply(close=True)
            return 0

        monkeypatch.setattr(sep.ParameterEditorDialog, "exec", fake_exec)
        with qtbot.waitSignal(panel.parameterEdited, timeout=_WAIT_MS):
            panel._open_editor(SITE_ELEVATION_PARAM)  # noqa: SLF001

        assert live.get(SITE_ELEVATION_PARAM) == pytest.approx(2500.0, rel=1e-12)
        assert panel.value_text() == "2.5 km"

    def test_the_unit_store_is_shared_not_copied(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A unit chosen on another surface reaches this row through the session store."""
        live = Sensor.load(_EXAMPLE)
        live.set(SITE_ELEVATION_PARAM, _MAUNA_KEA_M)
        units: dict[str, str] = {}
        panel = _panel(qtbot, live, units)
        assert panel.value_text() == "4207 m"
        units[SITE_ELEVATION_PARAM] = "km"  # as if set by the parameter tree
        panel.refresh()
        assert panel.value_text() == "4.207 km"


# ---------------------------------------------------------------------------
# Commit path — one API call, the shared clone-validate seam
# ---------------------------------------------------------------------------


class TestCommitPath:
    def test_edit_is_one_set_and_one_signal(self, qtbot, monkeypatch, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """Exactly one ``sensor.set`` on the live sensor + one ``parameterEdited``.

        Same discipline as every other geometry field: the commit goes through the shared
        Parameter Editor (validated on a throwaway clone first), so there is no bespoke
        setter here and a rejected value never reaches the live sensor.
        """
        live = Sensor.load(_EXAMPLE)
        panel = _panel(qtbot, live)

        set_calls: list[str] = []
        orig_set = type(live).set

        def counting_set(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if self is live and args:
                set_calls.append(args[0])
            return orig_set(self, *args, **kwargs)

        monkeypatch.setattr(type(live), "set", counting_set)

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setText(str(_MAUNA_KEA_M))
            self.apply(close=True)
            return 0

        monkeypatch.setattr(sep.ParameterEditorDialog, "exec", fake_exec)
        with qtbot.waitSignal(panel.parameterEdited, timeout=_WAIT_MS) as blocker:
            panel._open_editor(SITE_ELEVATION_PARAM)  # noqa: SLF001

        assert set_calls == [SITE_ELEVATION_PARAM]
        assert blocker.args == [SITE_ELEVATION_PARAM]
        assert live.get(SITE_ELEVATION_PARAM) == pytest.approx(_MAUNA_KEA_M, rel=1e-12)
        assert panel.value_text() == "4207 m"
        # The module-fixture sensor is untouched (no shared mutable state).
        assert sensor.get(SITE_ELEVATION_PARAM) == pytest.approx(0.0, abs=0.0)

    def test_an_out_of_bounds_value_never_reaches_the_live_sensor(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """The clone-validate seam: the schema's 10 km ceiling rejects, the sensor holds.

        The dialog keeps itself open and shows the actionable what/why/action; nothing is
        committed and no ``parameterEdited`` fires, so no re-evaluation is scheduled on a
        value the model rejected.
        """
        live = Sensor.load(_EXAMPLE)
        panel = _panel(qtbot, live)
        emitted: list[str] = []
        panel.parameterEdited.connect(emitted.append)

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setText("99000")  # above the schema's (0, 1e4) m bound
            self.apply(close=True)
            return 0

        monkeypatch.setattr(sep.ParameterEditorDialog, "exec", fake_exec)
        panel._open_editor(SITE_ELEVATION_PARAM)  # noqa: SLF001

        assert live.get(SITE_ELEVATION_PARAM) == pytest.approx(0.0, abs=0.0)
        assert emitted == []
        assert panel.value_text() == "0 m"

    def test_an_unbound_card_ignores_an_edit_request(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """No sensor, no dialog — the pre-config state is inert, not a crash."""
        panel = _panel(qtbot, None)
        panel._open_editor(SITE_ELEVATION_PARAM)  # noqa: SLF001 — must not raise


# ---------------------------------------------------------------------------
# Wiring — the Geometry pane mounts it below the mode forms
# ---------------------------------------------------------------------------


class TestGeometryPaneWiring:
    def test_inputs_tab_declares_the_card(self) -> None:
        """The Qt-free composition puts the card on the Geometry Inputs sub-view."""
        inputs = STAGE_COMPOSITIONS["geometry"].subviews[0]
        assert inputs.title == "Inputs"
        assert inputs.site_elevation_panel

    def test_the_schematic_tab_does_not_mount_it(self) -> None:
        """One mount only — the Schematic tab is the viewer, not a second entry point."""
        schematic = STAGE_COMPOSITIONS["geometry"].subviews[1]
        assert schematic.title == "Schematic"
        assert not schematic.site_elevation_panel

    def test_pane_builds_the_card_below_the_mode_form(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        qtbot.addWidget(pane)
        panel = pane.site_elevation_panel
        form = pane.geometry_form
        assert panel is not None
        assert form is not None
        parent = panel.parentWidget()
        assert parent is not None
        layout = parent.layout()
        assert layout is not None
        order = [layout.itemAt(i).widget() for i in range(layout.count())]
        assert order.index(form) < order.index(panel)

    def test_binding_the_pane_binds_the_card(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The card joins the shared bind/refresh path, so it is never left stale."""
        live = Sensor.load(_EXAMPLE)
        live.set(SITE_ELEVATION_PARAM, _MAUNA_KEA_M)
        pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        qtbot.addWidget(pane)
        pane.bind_sensor(live, {})
        panel = pane.site_elevation_panel
        assert panel is not None
        assert panel.value_text() == "4207 m"

        live.set(SITE_ELEVATION_PARAM, 1000.0)
        pane.refresh_geometry_forms()
        assert panel.value_text() == "1000 m"

    def test_the_card_relays_edits_through_the_panes_signal(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """``parameterEdited`` reaches the pane, which is what marks results stale."""
        pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        qtbot.addWidget(pane)
        panel = pane.site_elevation_panel
        assert panel is not None
        with qtbot.waitSignal(pane.parameterEdited, timeout=_WAIT_MS) as blocker:
            panel.parameterEdited.emit(SITE_ELEVATION_PARAM)
        assert blocker.args == [SITE_ELEVATION_PARAM]


# ---------------------------------------------------------------------------
# The exclusion this card exists *because* of, left exactly as it was
# ---------------------------------------------------------------------------


class TestManifestExclusionUntouched:
    def test_site_elevation_is_still_outside_the_mode_manifest(self, sensor: Sensor) -> None:
        """Giving it a GUI entry point did not make it an input-mode door.

        The ``non_mode`` tag is the single authority both drift tests subtract (CU-309);
        this asserts the tag and the manifest still agree with each other.
        """
        pdef = sensor.parameter_defs()[SITE_ELEVATION_PARAM]
        assert "non_mode" in pdef.tags
        assert SITE_ELEVATION_PARAM not in set(all_mode_params())

    def test_the_mode_form_does_not_render_it(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        """No second entry point: the manifest-driven form still has no such row."""
        form = GeometryModeForm()
        qtbot.addWidget(form)
        form.bind_sensor(sensor, {})
        with pytest.raises(KeyError):
            form.field_value_text(SITE_ELEVATION_PARAM)

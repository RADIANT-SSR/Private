"""Tests for the Source stage instrument (GUI plan Phase PS-1, arch doc §4.4.1 Source rows).

The Source stage's contextual center becomes a real instrument, matching the Geometry-screen
standard: pre-atmosphere target + background **emission** spectra
(``result.plot.spectral_source_emission``, FP-1), editable schema-driven radiometric inputs
(the shared :class:`FieldRow`), the shared target shape/size/orientation editor
(:class:`TargetShapePanel` — the same widget the Geometry Schematic tab mounts), and an
Outputs readout carrying the tentative regime with units. Every test drives the real widgets
on the shipped example config, offscreen.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.stage_views import STAGE_COMPOSITIONS  # noqa: E402
from radiant.gui.widgets.field_row import FieldRow  # noqa: E402
from radiant.gui.widgets.source_inputs_form import _RADIOMETRY_FIELDS  # noqa: E402
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402
from radiant.gui.widgets.target_shape_panel import (  # noqa: E402
    NOMINAL_SHAPE_DIMENSIONS,
)

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 15000
_ALL_SHAPES = ("sphere", "cylinder", "flat_plate", "box", "cone")


def _evaluate(sensor: Sensor) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sensor.evaluate()


def _source_pane(qtbot, sensor: Sensor) -> StagePane:
    """A bound, populated Source StagePane on the example config."""
    pane = StagePane("source", STAGE_COMPOSITIONS["source"])
    qtbot.addWidget(pane)
    pane.bind_sensor(sensor, {})
    pane.populate(_evaluate(sensor))
    return pane


def _load_window(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    window.resize(1440, 900)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


# ---------------------------------------------------------------------------
# Composition (Qt-free)
# ---------------------------------------------------------------------------


class TestSourceComposition:
    def test_emission_is_the_primary_plot(self) -> None:
        """GT-0: the thermal tab leads with the FP-1 emission accessor; the reflective
        tab carries the at-aperture radiance (owner: keep it available)."""
        comp = STAGE_COMPOSITIONS["source"]
        methods = [p.method for sub in comp.subviews for p in sub.plots]
        assert methods[0] == "spectral_source_emission"
        assert "spectral_source" in methods

    def test_source_declares_scene_first_tabs_without_shape(self) -> None:
        """GT-0: four owner-ordered tabs, scene declaration first; the shape editor is
        GONE from Source (extent is geometry content post-TEG)."""
        comp = STAGE_COMPOSITIONS["source"]
        titles = [sub.title for sub in comp.subviews]
        assert titles == [
            "Scene & regime",
            "Target — thermal",
            "Target — point source",
            "Target — reflective",
            "Background & contrast",
        ]
        assert comp.subviews[0].source_groups == ("scene",)
        assert comp.subviews[0].outputs is True
        assert not any(sub.target_shape for sub in comp.subviews)
        assert comp.target_shape is False


# ---------------------------------------------------------------------------
# The pane composition (plots + inputs + shape + outputs)
# ---------------------------------------------------------------------------


class TestSourcePane:
    def test_emission_figure_renders_after_evaluate(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Source center draws the emission-spectrum figure (target arm) after evaluate."""
        pane = _source_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        assert pane.plot_canvases  # at least the emission section
        assert pane.plot_canvases[0].has_figure()

    def test_inputs_are_the_shared_field_row(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Every radiometric input is the shared FieldRow (by-construction consistency)."""
        pane = _source_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        forms = pane._source_forms  # noqa: SLF001 — one per GT-0 tab
        assert len(forms) == 5
        rows: dict[str, FieldRow] = {}
        for form in forms:
            for dotpath in form.field_dotpaths():
                rows[dotpath] = form.row(dotpath)
        for _label, dotpath in _RADIOMETRY_FIELDS:
            assert isinstance(rows[dotpath], FieldRow)
        thermal = next(f for f in forms if "source.target.temperature" in f.field_dotpaths())
        # The value carries its unit (R-UNITS): temperature reads in K.
        assert thermal.field_value_text("source.target.temperature").endswith("K")

    def test_shape_panel_removed_from_source_but_kept_on_geometry(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """GT-0 regression guard: extent editing left Source (it is geometry content);
        the Geometry Schematic tab still mounts the shared TargetShapePanel."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        source_pane = _source_pane(qtbot, sensor)
        assert source_pane.target_shape_panel is None
        geo_pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
        qtbot.addWidget(geo_pane)
        geo_pane.bind_sensor(sensor, {})
        panel = geo_pane.geometry_panel
        assert panel is not None and panel.shape_combo.count() > 1
        # No 3D scene on the Source stage → no triad toggle.
        assert not panel.triad_checkbox.isVisible()

    def test_outputs_readout_shows_regime_with_units(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Outputs readout carries the tentative regime + a dimensional output with unit."""
        pane = _source_pane(qtbot, Sensor.from_yaml(_EXAMPLE))
        readout = pane.outputs_readout
        assert readout is not None
        keys = readout.rendered_keys()
        assert "regime_tentative" in keys
        # The enum renders by its value string, not its repr.
        assert readout.value_text("regime_tentative") == "extended"
        # An extended target has an unbounded angular extent — rendered as the ∞
        # sentinel without a (meaningless) unit, not "inf rad" (CU-135).
        assert readout.value_text("angular_extent_rad") == "∞"


# ---------------------------------------------------------------------------
# Edit-and-watch: one sensor.set, re-evaluate, refresh
# ---------------------------------------------------------------------------


class TestSourceEditAndWatch:
    def test_editing_target_temperature_sets_once_and_reevaluates(  # type: ignore[no-untyped-def]
        self, qtbot, monkeypatch
    ) -> None:
        """A radiometric-input edit → one live sensor.set → debounced re-evaluate → refresh."""
        window = _load_window(qtbot)
        center = window.central_canvas.stage_center
        window.stage_strip.stageClicked.emit("source")
        pane = center.pane("source")
        forms = pane._source_forms  # noqa: SLF001 — one per GT-0 tab
        form = next(f for f in forms if "source.target.temperature" in f.field_dotpaths())

        dotpath = "source.target.temperature"
        live = window.sensor
        set_calls: list[str] = []
        orig_set = type(live).set

        def counting_set(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if self is live and args:
                set_calls.append(args[0])
            return orig_set(self, *args, **kwargs)

        monkeypatch.setattr(type(live), "set", counting_set)

        from radiant.gui.widgets import source_inputs_form as sif

        def fake_exec(self):  # type: ignore[no-untyped-def]
            self.value_editor.setText("321.0")  # float param → QLineEdit
            self.apply(close=True)
            return 0

        monkeypatch.setattr(sif.ParameterEditorDialog, "exec", fake_exec)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            form._open_editor(dotpath)  # noqa: SLF001 — exercises the commit path

        # Exactly one set on the live sensor, for the edited parameter.
        assert set_calls.count(dotpath) == 1
        assert window.sensor.get_input(dotpath) == pytest.approx(321.0)
        # The form re-synced to the committed value and the emission figure re-rendered.
        assert form.field_value_text(dotpath) == "321 K"
        assert pane.plot_canvases[0].has_figure()

    def test_selecting_shape_seeds_nominal_and_reevaluates_clean(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Picking a shape on the Source stage seeds nominal dims (CU-125) and evaluates clean."""
        for shape in _ALL_SHAPES:
            sensor = Sensor.from_yaml(_EXAMPLE)
            # GT-0: extent editing lives on Geometry now; the seeding contract is the
            # same (shared panel, one compound edit).
            pane = StagePane("geometry", STAGE_COMPOSITIONS["geometry"])
            qtbot.addWidget(pane)
            pane.bind_sensor(sensor, {})
            panel = pane.geometry_panel
            assert panel is not None
            compound: list[list[str]] = []
            pane.compoundParameterEdited.connect(compound.append)
            panel.shape_combo.setCurrentText(shape)  # emits shapeRequested → pane seeds dims
            for dotpath, nominal in NOMINAL_SHAPE_DIMENSIONS[shape].items():
                assert float(sensor.get(dotpath)) == pytest.approx(nominal)
            # CU-141: the shape pick + the dims seeded alongside it are emitted as ONE
            # compound edit (shape first) so the host records them under a single undo macro.
            assert len(compound) == 1
            assert compound[0][0] == "geometry.target.shape"
            assert set(compound[0][1:]) == set(NOMINAL_SHAPE_DIMENSIONS[shape].keys())
            # The subsequent physics re-evaluate succeeds (no ParameterBoundsError).
            assert _evaluate(sensor) is not None


class TestReflectiveAndSceneType:
    """GS-1 (GUI Capability Expansion plan): reflective/solar path + scene-type declaration."""

    def test_manifest_exposes_reflective_solar_and_scene_fields(self) -> None:
        paths = {dotpath for _label, dotpath in _RADIOMETRY_FIELDS}
        for required in (
            "source.target.reflectance",
            "geometry.solar_illumination",
            "geometry.solar_zenith_rad",
            "source.scene_type",
            "source.regime_override",
            "source.target.fill_fraction",
            "source.target.is_hot_target",
            "source.background.material",
        ):
            assert required in paths, f"GS-1 field missing from form: {required}"

    def test_manifest_paths_exist_in_schema(self) -> None:
        sensor = Sensor.from_yaml(_EXAMPLE)
        defs = sensor.parameter_defs()
        for _label, dotpath in _RADIOMETRY_FIELDS:
            assert dotpath in defs, f"unknown parameter in manifest: {dotpath}"

    def test_day_night_toggle_changes_reflective_signal(self) -> None:
        """The GS-1 checkpoint physics: on the mixed emit+reflect path (T3 — ε+T set,
        Kirchhoff ρ = 1−ε), toggling day → night removes the reflected-solar term and
        the collected signal must drop. (Pure-reflective T2 is ρ-alone by design: the
        engine rejects ρ combined with ε/T with an actionable error — the form's editor
        reject discipline surfaces that message verbatim.)"""

        def run(illumination: str) -> float:
            s = Sensor.from_yaml(_EXAMPLE)
            s.set("source.target.emissivity", 0.7)  # Kirchhoff: rho = 0.3 reflected
            s.set("geometry.solar_zenith_rad", 0.5)
            s.set("geometry.solar_illumination", illumination)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r = s.evaluate()
            return float(r.stage_outputs["spectral_integration"]["signal_e"])

        day = run("day")
        night = run("night")
        assert day > night, (
            f"reflected-solar term had no effect: day={day:.4g} e- vs night={night:.4g} e-"
        )

    def test_declared_scene_type_mismatch_warns(self) -> None:
        """Declaring point_source on the extended example fires the T2 cross-check warning."""
        s = Sensor.from_yaml(_EXAMPLE)
        s.set("source.scene_type", "point_source")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            s.evaluate()
        texts = [str(w.message) for w in caught]
        assert any("scene_type" in t or "declared" in t.lower() for t in texts), (
            f"no declared-vs-derived warning; warnings seen: {texts[:5]}"
        )


class TestRelevanceGating:
    """Gap 85 (source stage): declared scene type gates parameter relevance."""

    def _form(self, qtbot, sensor):  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.source_inputs_form import SourceInputsForm

        form = SourceInputsForm()
        qtbot.addWidget(form)
        form.bind_sensor(sensor, {})
        return form

    def test_auto_gates_nothing(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        form = self._form(qtbot, sensor)
        for dotpath in ("source.target.fill_fraction", "source.contrast_reference.temperature"):
            assert form.row(dotpath).isEnabled(), dotpath

    def test_extended_disables_subpixel_fields(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set("source.scene_type", "extended")
        form = self._form(qtbot, sensor)
        # Sub-pixel-only knobs gate off; the explanation names the declared type.
        for dotpath in ("source.target.fill_fraction", "source.background.temperature"):
            assert not form.row(dotpath).isEnabled(), dotpath
            assert "extended" in form.row(dotpath).toolTip()
        # Extended-relevant + regime-independent fields stay editable.
        assert form.row("source.contrast_reference.temperature").isEnabled()
        assert form.row("source.target.temperature").isEnabled()
        # The scene-type selector itself never gates (the way back out).
        assert form.row("source.scene_type").isEnabled()

    def test_point_source_enables_intensity_extended_disables(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The point-intensity inputs gate ON for a point_source scene, OFF otherwise (Gap 98 D)."""
        intensity_paths = (
            "source.target.point_intensity_temperature_K",
            "source.target.point_intensity_area_m2",
            "source.target.point_intensity_emissivity",
            "source.target.point_intensity_band_W_per_sr",
        )
        ps = Sensor.from_yaml(_EXAMPLE)
        ps.set("source.scene_type", "point_source")
        form_ps = self._form(qtbot, ps)
        for dotpath in intensity_paths:
            assert form_ps.row(dotpath).isEnabled(), dotpath
        # Conversely the surface-radiance (ε, T) rows gate OFF — they are not the
        # point-source input (a point source is defined by intensity).
        assert not form_ps.row("source.target.temperature").isEnabled()
        assert not form_ps.row("source.target.emissivity").isEnabled()

        ext = Sensor.from_yaml(_EXAMPLE)
        ext.set("source.scene_type", "extended")
        form_ext = self._form(qtbot, ext)
        for dotpath in intensity_paths:
            assert not form_ext.row(dotpath).isEnabled(), dotpath
            assert "point_source" in form_ext.row(dotpath).toolTip()

    def test_sub_pixel_disables_contrast_reference(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set("source.scene_type", "sub_pixel")
        form = self._form(qtbot, sensor)
        assert not form.row("source.contrast_reference.temperature").isEnabled()
        assert form.row("source.target.fill_fraction").isEnabled()
        assert form.row("source.background.temperature").isEnabled()

    def test_declaring_back_to_auto_reenables(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set("source.scene_type", "extended")
        form = self._form(qtbot, sensor)
        assert not form.row("source.target.fill_fraction").isEnabled()
        sensor.set("source.scene_type", "auto")
        form.refresh()
        assert form.row("source.target.fill_fraction").isEnabled()

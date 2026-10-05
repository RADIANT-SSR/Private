"""The per-element detail editor (Gap 142).

What it exists to fix, from the 2026-10-04 live review: the train table has one value
column, so a cavity element's definition — two surface coatings, a thickness, a bulk —
was invisible, its value cell blank, and a refusal naming ``alpha`` unreadable because
``alpha`` appeared nowhere on screen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.widgets.element_detail_editor import (  # noqa: E402
    FLAGGED_SEPARATOR,
    NO_SUBSTRATE,
    SEED_SURFACE_R,
    SEED_THICKNESS_M,
    ElementDetailEditor,
    ElementModel,
    model_of_entry,
)

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

_MIRROR = {"name": "M1", "transfer_mode": "REFLECTIVE", "reflectance": 0.97, "temperature_K": 290.0}
_SIMPLE = {
    "name": "cold_window",
    "kind": "window",
    "transfer_mode": "REFRACTIVE",
    "transmittance": 0.92,
    "temperature_K": 200.0,
}
_CAVITY = {
    "name": "L1_ge",
    "kind": "lens",
    "transfer_mode": "REFRACTIVE",
    "substrate": "germanium",
    "thickness_m": 0.008,
    "R1": 0.01,
    "R2": 0.01,
    "temperature_K": 290.0,
}


def _editor(qtbot):  # type: ignore[no-untyped-def]
    widget = ElementDetailEditor()
    qtbot.addWidget(widget)
    return widget


class TestModelIsReadFromTheEntry:
    @pytest.mark.parametrize(
        ("entry", "expected"),
        [
            (_MIRROR, ElementModel.REFLECTIVE),
            (_SIMPLE, ElementModel.SIMPLE),
            (_CAVITY, ElementModel.CAVITY),
            ({"transfer_mode": "REFRACTIVE", "T2": 0.99}, ElementModel.CAVITY),
        ],
    )
    def test_predicate(self, entry: dict[str, object], expected: ElementModel) -> None:
        assert model_of_entry(entry) is expected

    def test_binding_selects_the_matching_model_button(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_CAVITY))
        assert widget.model is ElementModel.CAVITY


class TestOverSpecificationIsUnconstructible:
    """The error from the live review cannot be produced through this widget.

    The io parser still refuses a substrate *and* an explicit alpha — it is the
    validation authority and configs are hand-editable — but the state is unreachable
    here, which is better than refusing it with better words.
    """

    def test_choosing_a_substrate_clears_any_explicit_alpha(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry({**_CAVITY, "substrate": None, "alpha": 2.0})
        widget._named_radio.setChecked(True)
        widget._substrate_combo.setCurrentIndex(widget._substrate_combo.findData("germanium"))
        entry = widget.entry
        assert entry["substrate"] == "germanium"
        assert "alpha" not in entry

    def test_choosing_explicit_alpha_clears_the_substrate(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_CAVITY))
        widget._explicit_radio.setChecked(True)
        widget._alpha.setText("2.0")
        widget._alpha.editingFinished.emit()
        entry = widget.entry
        assert "substrate" not in entry
        assert entry["alpha"] == pytest.approx(2.0, abs=1e-12)


class TestSubstratePicker:
    def test_the_default_is_the_custom_path_not_a_blank(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        assert widget._substrate_combo.itemText(0) == NO_SUBSTRATE
        assert widget._substrate_combo.itemData(0) == ""

    def test_flagged_materials_sit_below_a_disabled_separator(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        combo = widget._substrate_combo
        texts = [combo.itemText(i) for i in range(combo.count())]
        assert FLAGGED_SEPARATOR in texts
        index = texts.index(FLAGGED_SEPARATOR)
        assert not combo.model().item(index).isEnabled()
        # Germanium is tier B, so it must be below the line, not beside ZnSe.
        assert texts.index("Germanium (Ge)") > index

    def test_the_facts_line_names_the_tier_and_the_grade_spread(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_CAVITY))
        text = widget._substrate_facts.text()
        assert "tier B" in text
        assert "class-typical" in text
        assert "window" in text


class TestTemperatureValidity:
    """Germanium's α is published at one temperature and valid over a stated window."""

    def test_an_in_range_temperature_says_so(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_CAVITY))
        assert "in range" in widget._validity.text()

    def test_an_out_of_range_temperature_is_called_out(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """70 K germanium: the case that looked plausible in live review."""
        widget = _editor(qtbot)
        widget.bind_entry({**_CAVITY, "temperature_K": 70.0})
        assert "OUTSIDE" in widget._validity.text()

    def test_no_substrate_means_no_validity_claim(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry({**_CAVITY, "substrate": None, "alpha": 2.0})
        assert widget._validity.text() == ""


class TestModelSwitching:
    def test_simple_to_cavity_seeds_and_says_it_seeded(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_SIMPLE))
        widget._choose_model(ElementModel.CAVITY)
        entry = widget.entry
        assert entry["R1"] == pytest.approx(SEED_SURFACE_R, abs=1e-12)
        assert entry["R2"] == pytest.approx(SEED_SURFACE_R, abs=1e-12)
        assert entry["thickness_m"] == pytest.approx(SEED_THICKNESS_M, abs=1e-12)
        assert "transmittance" not in entry
        note = widget._note.text()
        assert "Not applied yet" in note
        assert "guess at the coatings" in note
        assert f"{SEED_THICKNESS_M * 1000:g} mm" in note

    def test_cavity_to_simple_discards_and_says_what_it_discarded(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_CAVITY))
        widget._choose_model(ElementModel.SIMPLE)
        entry = widget.entry
        for key in ("R1", "R2", "thickness_m", "substrate"):
            assert key not in entry, key
        assert "transmittance" in entry
        assert "stops emitting" in widget._note.text()

    def test_to_reflective_drops_the_refractive_keys(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_CAVITY))
        widget._choose_model(ElementModel.REFLECTIVE)
        entry = widget.entry
        assert entry["transfer_mode"] == "REFLECTIVE"
        assert "reflectance" in entry
        for key in ("R1", "R2", "thickness_m", "substrate", "kind"):
            assert key not in entry, key

    def test_switching_emits_the_replacement_entry(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_SIMPLE))
        with qtbot.waitSignal(widget.entryEdited, timeout=1000) as blocker:
            widget._choose_model(ElementModel.CAVITY)
        assert blocker.args[0]["R1"] == pytest.approx(SEED_SURFACE_R, abs=1e-12)


class TestSurfacesAreIndependent:
    def test_each_surface_writes_its_own_key(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_CAVITY))
        widget._surface1._value.setText("0.02")
        widget._surface2._value.setText("0.05")
        widget._surface1._value.editingFinished.emit()
        entry = widget.entry
        assert entry["R1"] == pytest.approx(0.02, abs=1e-12)
        assert entry["R2"] == pytest.approx(0.05, abs=1e-12)

    def test_switching_a_surface_to_T_removes_its_R(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_CAVITY))
        widget._surface2._t_radio.setChecked(True)
        widget._surface2._on_side_changed(1)
        entry = widget.entry
        assert "R2" not in entry
        # The value converts rather than carrying over: R = 0.01 is T = 0.99.
        assert entry["T2"] == pytest.approx(0.99, abs=1e-9)

    def test_a_csv_path_survives_as_a_string(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """One of the three forms a surface accepts; it must not be coerced."""
        widget = _editor(qtbot)
        widget.bind_entry(dict(_CAVITY))
        widget._surface1._value.setText("coatings/ar_s1.csv")
        widget._surface1._value.editingFinished.emit()
        assert widget.entry["R1"] == "coatings/ar_s1.csv"


class TestClearingAFieldRemovesTheKey:
    """The CU-344 contract: a blank means "this entry does not specify it"."""

    def test_clearing_thickness_removes_it_rather_than_writing_zero(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_CAVITY))
        widget._thickness.setText("")
        widget._thickness.editingFinished.emit()
        assert "thickness_m" not in widget.entry

    def test_clearing_temperature_removes_it(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_MIRROR))
        widget._temperature.setText("")
        widget._temperature.editingFinished.emit()
        assert "temperature_K" not in widget.entry

    def test_a_spectral_sentinel_is_never_written_back_as_a_string(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """ "spectral (2 pts)" is a rendering of an inline table, not a value."""
        table = {"wavelength_um": [3.0, 5.0], "values": [0.96, 0.98]}
        widget = _editor(qtbot)
        widget.bind_entry({**_MIRROR, "reflectance": table})
        assert widget._single_value.text() == "spectral (2 pts)"
        widget._single_value.editingFinished.emit()
        assert widget.entry["reflectance"] == table


class TestThicknessIsShownInMillimetres:
    def test_metres_in_the_document_millimetres_on_screen(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_CAVITY))
        assert widget._thickness.text() == "8"

    def test_an_edit_round_trips_back_to_metres(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_CAVITY))
        widget._thickness.setText("12.5")
        widget._thickness.editingFinished.emit()
        assert widget.entry["thickness_m"] == pytest.approx(0.0125, abs=1e-15)


class TestBulkAbsentOnNonCavityElements:
    @pytest.mark.parametrize("entry", [_MIRROR, _SIMPLE])
    def test_the_bulk_tab_explains_rather_than_offering(self, qtbot, entry: dict) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(entry))
        # isVisible() needs a shown parent, so assert the widget's own visibility
        # intent: the bulk controls are hidden and the explanation is shown.
        assert widget._bulk.isHidden()
        assert not widget._bulk_absent.isHidden()
        text = widget._bulk_absent.text()
        assert "No bulk on this element" in text
        assert "refuses it rather than accepting it quietly" in text


class TestWiredToTheTrainEditor:
    """One write path: the detail editor never touches a sensor itself."""

    def test_an_edit_reaches_the_document(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.optical_element_editor import OpticalElementEditor

        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements([dict(_MIRROR), dict(_CAVITY)])
        train = OpticalElementEditor()
        qtbot.addWidget(train)
        train.bind_sensor(sensor, {})
        train.table.setCurrentCell(1, 0)
        row, entry = train.selected_entry()
        assert row == 1 and entry is not None
        entry["thickness_m"] = 0.012
        assert train.replace_entry(row, entry)
        document = sensor.optical_elements()
        assert document is not None
        assert document[1]["thickness_m"] == pytest.approx(0.012, abs=1e-15)
        # The row the edit did not touch is byte-identical (CU-344).
        assert document[0] == _MIRROR

    def test_replacing_an_entry_refreshes_the_cells_the_table_owns(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Otherwise the stale Transfer combo overlays back over the new entry."""
        from PySide6.QtWidgets import QComboBox

        from radiant.gui.widgets.optical_element_editor import (
            _COL_TRANSFER,
            OpticalElementEditor,
        )

        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements([dict(_SIMPLE)])
        train = OpticalElementEditor()
        qtbot.addWidget(train)
        train.bind_sensor(sensor, {})
        train.table.setCurrentCell(0, 0)
        converted = {
            "name": "cold_window",
            "transfer_mode": "REFLECTIVE",
            "reflectance": 0.9,
            "temperature_K": 200.0,
        }
        assert train.replace_entry(0, converted)
        combo = train.table.cellWidget(0, _COL_TRANSFER)
        assert isinstance(combo, QComboBox)
        assert combo.currentText() == "REFLECTIVE"
        document = sensor.optical_elements()
        assert document is not None
        assert document[0]["transfer_mode"] == "REFLECTIVE"
        assert "transmittance" not in document[0]


class TestAbsorptionIsOneClickAway:
    """ "If I want to see what the absorption is, I should be able to navigate there."""

    def test_the_button_asks_the_host_for_the_selected_material(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_CAVITY))
        with qtbot.waitSignal(widget.showAbsorption, timeout=1000) as blocker:
            widget._view_alpha.click()
        assert blocker.args[0] == "germanium"

    def test_it_is_disabled_without_a_named_material(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """There is no library curve to draw for a custom alpha the operator typed."""
        widget = _editor(qtbot)
        widget.bind_entry({**_CAVITY, "substrate": None, "alpha": 2.0})
        assert not widget._view_alpha.isEnabled()


class TestAbsorptionRendersInThePanel:
    def test_the_panel_draws_the_figure_into_its_detail_canvas(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.transmission_panel import TransmissionPanel

        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements([dict(_CAVITY)])
        panel = TransmissionPanel()
        qtbot.addWidget(panel)
        panel.bind_sensor(sensor, {})
        panel.element_editor.table.setCurrentCell(0, 0)
        panel.detail_editor._view_alpha.click()
        figure = panel.element_editor.detail_canvas._figure
        assert figure is not None
        assert figure.axes[0].get_yscale() == "log"
        assert "Germanium (Ge)" in figure.axes[0].get_title()

    def test_the_run_band_is_shaded_on_it(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.transmission_panel import TransmissionPanel

        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_optical_elements([dict(_CAVITY)])
        panel = TransmissionPanel()
        qtbot.addWidget(panel)
        panel.bind_sensor(sensor, {})
        panel.element_editor.table.setCurrentCell(0, 0)
        panel.detail_editor._view_alpha.click()
        assert panel.element_editor.detail_canvas._figure.axes[0].patches


class TestAlphaTakesASpectrum:
    """α(λ) is the usual case, not the exception (owner, 2026-10-04).

    A measured coupon comes off an FTIR as a spectrum and every library material is
    one. The field always accepted a CSV path — the config layer resolves scalar, path
    and inline table alike — but with no button the only way to discover that was to
    read the parser.
    """

    def test_a_csv_path_is_kept_as_a_path_not_coerced(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry({**_CAVITY, "substrate": None, "alpha": 2.0})
        widget._explicit_radio.setChecked(True)
        widget._alpha.setText("coatings/ge_alpha.csv")
        widget._alpha.editingFinished.emit()
        assert widget.entry["alpha"] == "coatings/ge_alpha.csv"

    def test_an_inline_spectrum_is_not_written_back_as_its_rendering(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        table = {"wavelength_um": [3.0, 5.0], "values": [0.4, 0.9]}
        widget = _editor(qtbot)
        widget.bind_entry({**_CAVITY, "substrate": None, "alpha": table})
        assert widget._alpha.text() == "spectral (2 pts)"
        widget._alpha.editingFinished.emit()
        assert widget.entry["alpha"] == table

    def test_the_csv_button_is_offered_on_the_explicit_path(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry({**_CAVITY, "substrate": None, "alpha": 2.0})
        assert widget._alpha_csv.isEnabled()


class TestNoRefractiveIndexField:
    """CU-399: the index entered no formula, so the form does not ask for it."""

    def test_the_form_has_no_index_input(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = _editor(qtbot)
        widget.bind_entry(dict(_CAVITY))
        assert not hasattr(widget, "_n_refr")

    def test_an_edit_never_writes_the_removed_key(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A legacy document carrying n_refr must not have it re-emitted."""
        widget = _editor(qtbot)
        widget.bind_entry({**_CAVITY, "substrate": None, "alpha": 2.0, "n_refr": 4.0})
        widget._alpha.setText("3.0")
        widget._alpha.editingFinished.emit()
        assert "n_refr" not in widget.entry

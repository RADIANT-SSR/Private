"""Tests for the inline spectral-table dialog + its element-editor/io integration.

Owner request 2026-07-16: define a component's λ-vs-R/T (and QE) response by typing
into a table or pasting from a spreadsheet — no external CSV required. The document
form is the inline ``{"wavelength_um": [...], "values": [...]}`` table the io element
parser now accepts, so an authored spectrum round-trips through ``Sensor.save``.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.widgets.optical_element_editor import OpticalElementEditor  # noqa: E402
from radiant.gui.widgets.spectral_table_dialog import (  # noqa: E402
    SpectralTableDialog,
    parse_spectrum_text,
)

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


class TestParseText:
    def test_accepts_commas_tabs_whitespace_and_comments(self) -> None:
        text = "# gold coating\n3.0, 0.97\n4.0\t0.975\n5.0 0.98\n\n"
        assert parse_spectrum_text(text) == [(3.0, 0.97), (4.0, 0.975), (5.0, 0.98)]

    def test_bad_line_named_in_error(self) -> None:
        with pytest.raises(ValueError, match="line 2"):
            parse_spectrum_text("3.0, 0.97\nnot-a-number, 0.9")


class TestDialog:
    def test_typed_rows_validate_and_sort(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = SpectralTableDialog()
        qtbot.addWidget(dialog)
        assert not dialog.ok_enabled()  # empty table: OK gated off
        dialog.load_text("5.0, 0.98\n3.0, 0.97")
        assert dialog.ok_enabled()
        assert "2 points" in dialog.status_text
        spectrum = dialog.spectrum()
        assert spectrum["wavelength_um"] == [3.0, 5.0]  # λ-sorted
        assert spectrum["values"] == [0.97, 0.98]

    def test_single_point_keeps_ok_disabled(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = SpectralTableDialog()
        qtbot.addWidget(dialog)
        dialog.load_text("3.0, 0.97")
        assert not dialog.ok_enabled()
        assert "at least 2 required" in dialog.status_text


class TestInlineSpectrumDocument:
    def test_editor_spectrum_round_trips_through_save(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Author a spectral mirror in the editor → Apply → save → load → intact."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        # Attach an inline spectrum the way _edit_spectrum would store it.
        item = editor.table.item(0, 3)
        from radiant.gui.widgets.optical_element_editor import _SPECTRUM_ROLE

        item.setData(_SPECTRUM_ROLE, {"wavelength_um": [3.0, 5.0], "values": [0.96, 0.98]})
        item.setText("spectral (2 pts)")
        assert editor.apply_train()

        path = tmp_path / "spectral_train.yaml"
        sensor.save(path)
        text = path.read_text()
        assert "wavelength_um" in text  # the inline table persisted into the YAML

        reloaded = Sensor.load(path)
        document = reloaded.optical_elements()
        assert document is not None
        assert document[0]["reflectance"]["values"] == [0.96, 0.98]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            a = sensor.evaluate().metrics["snr"]
            b = reloaded.evaluate().metrics["snr"]
        assert b == pytest.approx(a, rel=1e-12)

    def test_typing_over_sentinel_discards_stored_table(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        editor = OpticalElementEditor()
        qtbot.addWidget(editor)
        editor.bind_sensor(sensor, {})
        editor._add_mirror.click()
        item = editor.table.item(0, 3)
        from radiant.gui.widgets.optical_element_editor import _SPECTRUM_ROLE

        item.setData(_SPECTRUM_ROLE, {"wavelength_um": [3.0, 5.0], "values": [0.96, 0.98]})
        item.setText("0.9")  # the user typed a scalar over it — the text wins
        entry = editor.entries()[0]
        assert entry["reflectance"] == pytest.approx(0.9, abs=1e-12)


class TestDefineQeTable:
    """Detector form: define QE(λ) inline → CSV written → qe_table_path set (one call)."""

    def test_define_qe_writes_csv_and_binds_path(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.detector_inputs_form import DetectorInputsForm

        sensor = Sensor.from_yaml(_EXAMPLE)
        form = DetectorInputsForm()
        qtbot.addWidget(form)
        form.bind_sensor(sensor, {})
        csv_path = tmp_path / "qe.csv"
        with qtbot.waitSignal(form.parameterEdited, timeout=2000) as blocker:
            form.define_qe_table(
                {"wavelength_um": [3.0, 4.0, 5.0], "values": [0.35, 0.4, 0.3]}, csv_path
            )
        assert blocker.args == ["detector.qe_table_path"]
        assert csv_path.read_text().startswith("wavelength_um,qe")
        assert sensor.get_input("detector.qe_table_path") == str(csv_path)

    def test_defined_qe_curve_changes_signal(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """The curve is consumed by the chain: halving QE roughly halves signal_e."""
        from radiant.gui.widgets.detector_inputs_form import DetectorInputsForm

        sensor = Sensor.from_yaml(_EXAMPLE)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            baseline = sensor.clone().evaluate().stage_outputs["spectral_integration"]["signal_e"]
        form = DetectorInputsForm()
        qtbot.addWidget(form)
        form.bind_sensor(sensor, {})
        half_qe = float(sensor.get_input("detector.qe_value")) / 2.0
        form.define_qe_table(
            {"wavelength_um": [3.0, 5.5], "values": [half_qe, half_qe]}, tmp_path / "qe.csv"
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with_curve = sensor.evaluate().stage_outputs["spectral_integration"]["signal_e"]
        assert float(with_curve) == pytest.approx(float(baseline) / 2.0, rel=1e-6)

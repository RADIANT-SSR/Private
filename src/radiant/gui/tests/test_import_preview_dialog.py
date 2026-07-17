"""Tests for the D5 confirm-before-Apply import preview (ADR-0009 D5)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.widgets.import_preview_dialog import ImportPreviewDialog  # noqa: E402

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"
_TAPE7 = _REPO / "modtran" / "synthetic" / "E3.synthetic.tp7"


def _qe_csv(tmp_path: Path) -> Path:
    path = tmp_path / "vendor_qe.csv"
    path.write_text("wavelength_um,qe\n3.0,0.35\n4.0,0.40\n5.0,0.30\n", encoding="utf-8")
    return path


class TestDialogParse:
    def test_qe_parse_arms_apply_with_unit_labeled_info(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        dialog = ImportPreviewDialog("qe_csv")
        qtbot.addWidget(dialog)
        assert not dialog.apply_enabled()
        assert dialog.load_path(str(_qe_csv(tmp_path)))
        assert dialog.apply_enabled()
        assert "3 points" in dialog.info_text
        assert "µm" in dialog.info_text
        assert dialog.selected_path() is not None

    def test_bad_file_shows_actionable_error_and_keeps_apply_off(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        bad = tmp_path / "junk.csv"
        bad.write_text("not,a\nqe,file\n", encoding="utf-8")
        dialog = ImportPreviewDialog("qe_csv")
        qtbot.addWidget(dialog)
        assert not dialog.load_path(str(bad))
        assert not dialog.apply_enabled()
        assert "Parse failed" in dialog.info_text
        assert dialog.selected_path() is None

    @pytest.mark.skipif(not _TAPE7.exists(), reason="synthetic tape7 fixture absent")
    def test_tape7_parse_shows_two_series(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = ImportPreviewDialog("tape7")
        qtbot.addWidget(dialog)
        assert dialog.load_path(str(_TAPE7))
        assert dialog.apply_enabled()
        assert "Transmittance" in dialog.info_text

    def test_unknown_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown kind"):
            ImportPreviewDialog("nonsense")


class TestFormHooks:
    def test_detector_import_binds_qe_path(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.detector_inputs_form import DetectorInputsForm

        sensor = Sensor.from_yaml(_EXAMPLE)
        form = DetectorInputsForm()
        qtbot.addWidget(form)
        form.bind_sensor(sensor, {})
        csv = _qe_csv(tmp_path)

        def fake_exec(dialog):  # type: ignore[no-untyped-def]
            assert dialog.load_path(str(csv))
            return int(dialog.DialogCode.Accepted)

        from radiant.gui.widgets import detector_inputs_form as dif

        monkeypatch.setattr(dif.ImportPreviewDialog, "exec", fake_exec)
        with qtbot.waitSignal(form.parameterEdited, timeout=2000) as blocker:
            form._on_import_qe()  # noqa: SLF001
        assert blocker.args == ["detector.qe_table_path"]
        assert sensor.get_input("detector.qe_table_path") == str(csv)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sensor.evaluate()  # the bound curve is chain-consumable

    @pytest.mark.skipif(not _TAPE7.exists(), reason="synthetic tape7 fixture absent")
    def test_atmosphere_import_binds_tape7_path(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.atmosphere_inputs_form import AtmosphereInputsForm

        sensor = Sensor.from_yaml(_EXAMPLE)
        form = AtmosphereInputsForm()
        qtbot.addWidget(form)
        form.bind_sensor(sensor, {})

        def fake_exec(dialog):  # type: ignore[no-untyped-def]
            assert dialog.load_path(str(_TAPE7))
            return int(dialog.DialogCode.Accepted)

        from radiant.gui.widgets import atmosphere_inputs_form as aif

        monkeypatch.setattr(aif.ImportPreviewDialog, "exec", fake_exec)
        with qtbot.waitSignal(form.parameterEdited, timeout=2000) as blocker:
            form._on_import_tape7()  # noqa: SLF001
        assert blocker.args == ["atmosphere.modtran.tape7_path"]
        assert sensor.get_input("atmosphere.modtran.tape7_path") == str(_TAPE7)

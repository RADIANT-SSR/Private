"""The Run → Run Sweep… dialog — 1-D / 2-D parameter sweeps as a GUI flow (GT-1).

:class:`SweepDialog` is the Tier-2 sweep surface: pick a parameter (schema-driven —
every float `ParameterDef`), enter a range **in the parameter's input unit**
(converted once at the dialog boundary, Rule 2), pick the metric, and Run. The
sweep executes on a worker thread through the public `Sensor.sweep` /
`Sensor.sweep_2d` with the Gap 72 progress/cancel hooks; a progress bar shows
done/total, and Cancel aborts cleanly (`OperationCancelledError` is an expected
outcome — the API returns **no partial results on cancel** by contract, and the
dialog says so honestly rather than pretending). The finished curve (1-D) or
heatmap (2-D) renders into the dialog's canvas, and **Copy as script** puts the
equivalent one-liner on the clipboard so a GUI-configured sweep graduates to the
scripting console.

The sweep runs against a **clone** of the live sensor (the session config is
never mutated by a trade study). The completed result is exposed via
:attr:`sweep_result` for the host to retain (export via ``SweepResult.to_csv``).

One widget class per file (Rule 19); styling from the QSS theme via object names.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from matplotlib.figure import Figure
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.api import OperationCancelledError
from radiant.core.exceptions import RadiantError
from radiant.core.units import convert
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor


class _SweepWorker(QThread):
    """Runs one sweep (1-D or 2-D) off the UI thread with progress/cancel."""

    progressed = Signal(int, int)
    finished_ok = Signal(object)  # SweepResult | Sweep2DResult
    cancelled = Signal(int, int)  # (done, total) at abort
    failed = Signal(object)  # Exception

    def __init__(self, sensor: Sensor, spec: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self._sensor = sensor
        self._spec = spec
        self._cancel = False
        self._done = 0
        self._total = 0

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:  # noqa: D102 — QThread override
        def progress(done: int, total: int) -> None:
            self._done, self._total = done, total
            self.progressed.emit(done, total)

        def cancel() -> bool:
            return self._cancel

        spec = self._spec
        try:
            if spec["mode"] == "1d":
                result = self._sensor.sweep(
                    spec["param1"],
                    spec["values1"],
                    metric=spec["metric"],
                    keep_results=spec["keep_results"],
                    progress=progress,
                    cancel=cancel,
                )
            else:
                result = self._sensor.sweep_2d(
                    spec["param1"],
                    spec["values1"],
                    spec["param2"],
                    spec["values2"],
                    metric=spec["metric"],
                    progress=progress,
                    cancel=cancel,
                )
        except OperationCancelledError:
            self.cancelled.emit(self._done, self._total)
            return
        except RadiantError as exc:
            self.failed.emit(exc)
            return
        self.finished_ok.emit(result)


class SweepDialog(QDialog):
    """Configure and run a 1-D / 2-D parameter sweep (Tier-2 GT-1)."""

    #: fires once per run on any terminal outcome (done / cancelled / failed)
    sweepSettled = Signal()

    def __init__(
        self,
        sensor: Sensor,
        metric_names: tuple[str, ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("sweepDialog")
        self.setWindowTitle("Run Sweep")
        self.resize(640, 620)

        self._sensor = sensor
        self._worker: _SweepWorker | None = None
        self.sweep_result: Any | None = None
        self._last_spec: dict[str, Any] | None = None

        # Float parameters only — the sweepable set, straight off the schema.
        self._defs = {
            name: pdef for name, pdef in sensor.parameter_defs().items() if pdef.dtype is float
        }

        layout = QVBoxLayout(self)
        grid_host = QWidget(self)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)

        self._param1 = QComboBox(self)
        self._param1.addItems(sorted(self._defs))
        self._param1.currentTextChanged.connect(lambda _t: self._refresh_unit_labels())
        self._start1, self._stop1, self._n1 = QLineEdit("0"), QLineEdit("1"), QLineEdit("11")
        self._unit1 = QLabel("", self)
        self._log1 = QCheckBox("log spacing", self)
        grid.addWidget(QLabel("Parameter"), 0, 0)
        grid.addWidget(self._param1, 0, 1, 1, 3)
        grid.addWidget(self._unit1, 0, 4)
        grid.addWidget(QLabel("Start"), 1, 0)
        grid.addWidget(self._start1, 1, 1)
        grid.addWidget(QLabel("Stop"), 1, 2)
        grid.addWidget(self._stop1, 1, 3)
        grid.addWidget(QLabel("Points"), 2, 0)
        grid.addWidget(self._n1, 2, 1)
        grid.addWidget(self._log1, 2, 2, 1, 2)

        self._enable_2d = QCheckBox("Second parameter (2-D grid)", self)
        self._enable_2d.toggled.connect(self._on_2d_toggled)
        grid.addWidget(self._enable_2d, 3, 0, 1, 4)

        self._param2 = QComboBox(self)
        self._param2.addItems(sorted(self._defs))
        self._param2.currentTextChanged.connect(lambda _t: self._refresh_unit_labels())
        self._start2, self._stop2, self._n2 = QLineEdit("0"), QLineEdit("1"), QLineEdit("11")
        self._unit2 = QLabel("", self)
        grid.addWidget(QLabel("Parameter 2"), 4, 0)
        grid.addWidget(self._param2, 4, 1, 1, 3)
        grid.addWidget(self._unit2, 4, 4)
        grid.addWidget(QLabel("Start"), 5, 0)
        grid.addWidget(self._start2, 5, 1)
        grid.addWidget(QLabel("Stop"), 5, 2)
        grid.addWidget(self._stop2, 5, 3)
        grid.addWidget(QLabel("Points"), 6, 0)
        grid.addWidget(self._n2, 6, 1)

        self._metric = QComboBox(self)
        self._metric.addItems(list(metric_names) or ["snr"])
        grid.addWidget(QLabel("Metric"), 7, 0)
        grid.addWidget(self._metric, 7, 1, 1, 3)
        layout.addWidget(grid_host)

        self._canvas = MatplotlibCanvas(self)
        layout.addWidget(self._canvas, 1)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self._status = QLabel("", self)
        self._status.setObjectName("sweepStatusLabel")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        buttons = QWidget(self)
        from PySide6.QtWidgets import QHBoxLayout

        row = QHBoxLayout(buttons)
        row.setContentsMargins(0, 0, 0, 0)
        self._run = QPushButton("Run sweep", buttons)
        self._run.setObjectName("sweepRunButton")
        self._cancel = QPushButton("Cancel run", buttons)
        self._cancel.setEnabled(False)
        self._copy = QPushButton("Copy as script", buttons)
        self._copy.setEnabled(False)
        row.addWidget(self._run)
        row.addWidget(self._cancel)
        row.addStretch(1)
        row.addWidget(self._copy)
        layout.addWidget(buttons)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        box.rejected.connect(self.reject)
        box.accepted.connect(self.accept)
        layout.addWidget(box)

        self._run.clicked.connect(self.start_sweep)
        self._cancel.clicked.connect(self._on_cancel_clicked)
        self._copy.clicked.connect(self._on_copy_script)

        self._on_2d_toggled(False)
        self._refresh_unit_labels()

    # -- spec assembly ---------------------------------------------------------

    def _refresh_unit_labels(self) -> None:
        for combo, label in ((self._param1, self._unit1), (self._param2, self._unit2)):
            pdef = self._defs.get(combo.currentText())
            label.setText(f"[{pdef.input_unit or '–'}]" if pdef else "")

    def _on_2d_toggled(self, on: bool) -> None:
        for w in (self._param2, self._start2, self._stop2, self._n2, self._unit2):
            w.setEnabled(on)

    def _axis_values(
        self, dotpath: str, start_text: str, stop_text: str, n_text: str, log: bool
    ) -> np.ndarray:
        """Range entered in the input unit → canonical-unit values (one conversion)."""
        pdef = self._defs[dotpath]
        start, stop, n = float(start_text), float(stop_text), int(n_text)
        if n < 2:
            raise ValueError(f"points must be >= 2, got {n}")
        if log:
            if start <= 0 or stop <= 0:
                raise ValueError("log spacing needs positive start/stop")
            values = np.logspace(np.log10(start), np.log10(stop), n)
        else:
            values = np.linspace(start, stop, n)
        if pdef.input_unit and pdef.input_unit != pdef.canonical_unit:
            values = np.array(
                [convert(float(v), pdef.input_unit, pdef.canonical_unit) for v in values]
            )
        return values

    def _build_spec(self) -> dict[str, Any]:
        p1 = self._param1.currentText()
        spec: dict[str, Any] = {
            "mode": "2d" if self._enable_2d.isChecked() else "1d",
            "param1": p1,
            "values1": self._axis_values(
                p1,
                self._start1.text(),
                self._stop1.text(),
                self._n1.text(),
                self._log1.isChecked(),
            ),
            "metric": self._metric.currentText(),
            "keep_results": True,
            # display-unit echo for the script/copy path
            "start1": self._start1.text(),
            "stop1": self._stop1.text(),
            "n1": self._n1.text(),
            "log1": self._log1.isChecked(),
        }
        if spec["mode"] == "2d":
            p2 = self._param2.currentText()
            if p2 == p1:
                raise ValueError("2-D sweep needs two different parameters")
            spec["param2"] = p2
            spec["values2"] = self._axis_values(
                p2, self._start2.text(), self._stop2.text(), self._n2.text(), log=False
            )
        return spec

    # -- run --------------------------------------------------------------------

    def start_sweep(self) -> None:
        """Validate the spec and launch the worker (UI stays live)."""
        try:
            spec = self._build_spec()
        except (ValueError, KeyError) as exc:
            self._status.setText(f"Invalid sweep spec — {exc}")
            return
        self._last_spec = spec
        total = len(spec["values1"]) * (len(spec.get("values2", [1])))
        self._progress.setRange(0, total)
        self._progress.setValue(0)
        self._status.setText(f"Running… 0/{total}")
        self._run.setEnabled(False)
        self._cancel.setEnabled(True)
        # A trade study never mutates the session config: sweep a clone.
        self._worker = _SweepWorker(self._sensor.clone(), spec, self)
        self._worker.progressed.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)
        self._status.setText(f"Running… {done}/{total}")

    def _on_cancel_clicked(self) -> None:
        if self._worker is not None:
            self._worker.request_cancel()
            self._status.setText("Cancelling after the current point…")

    def _on_cancelled(self, done: int, total: int) -> None:
        self._finish_ui()
        self.sweepSettled.emit()
        # Honest state (Gap 72 contract): the API returns no partial results on
        # cancel — say so rather than pretending an empty curve is data.
        self._status.setText(
            f"Cancelled at {done}/{total}. No partial results (sweep API contract)."
        )

    def _on_failed(self, exc: BaseException) -> None:
        self._finish_ui()
        self.sweepSettled.emit()
        self._status.setText(f"Sweep failed — {exc}")

    def _on_finished(self, result: Any) -> None:
        self._finish_ui()
        self.sweepSettled.emit()
        self.sweep_result = result
        self._copy.setEnabled(True)
        spec = self._last_spec or {}
        figure = Figure(figsize=(5.6, 3.4), tight_layout=True)
        axis = figure.add_subplot(111)
        if spec.get("mode") == "1d":
            axis.plot(result.values, result.metric_values, marker="o")
            pdef = self._defs[spec["param1"]]
            axis.set_xlabel(f"{spec['param1']} [{pdef.canonical_unit or '-'}]")
            axis.set_ylabel(spec.get("metric", "metric"))
            if spec.get("log1"):
                axis.set_xscale("log")
            self._status.setText(f"Done — {len(result.values)} points.")
        else:
            image = axis.imshow(
                result.grid,
                origin="lower",
                aspect="auto",
                extent=(
                    float(result.values2[0]),
                    float(result.values2[-1]),
                    float(result.values1[0]),
                    float(result.values1[-1]),
                ),
            )
            figure.colorbar(image, ax=axis, label=spec.get("metric", "metric"))
            axis.set_xlabel(spec["param2"])
            axis.set_ylabel(spec["param1"])
            self._status.setText(f"Done — {result.grid.shape[0]}×{result.grid.shape[1]} grid.")
        axis.grid(True, alpha=0.3)
        self._canvas.show_figure(figure)

    def _finish_ui(self) -> None:
        self._run.setEnabled(True)
        self._cancel.setEnabled(False)
        if self._worker is not None:
            self._worker.wait(5000)
            self._worker = None

    # -- copy as script -----------------------------------------------------------

    def script_text(self) -> str:
        """The equivalent console one-liner for the last-run spec."""
        spec = self._last_spec
        if spec is None:
            return ""
        space = "np.logspace" if spec.get("log1") else "np.linspace"
        start, stop, n = spec["start1"], spec["stop1"], spec["n1"]
        if spec.get("log1"):
            axis1 = f"{space}(np.log10({start}), np.log10({stop}), {n})"
        else:
            axis1 = f"{space}({start}, {stop}, {n})"
        pdef = self._defs[spec["param1"]]
        unit_note = f"  # values in {pdef.input_unit or 'canonical'} — convert if needed"
        if spec["mode"] == "1d":
            return (
                f'sweep = sensor.sweep("{spec["param1"]}", {axis1}, '
                f'metric="{spec["metric"]}", keep_results=True){unit_note}'
            )
        return (
            f'sweep2d = sensor.sweep_2d("{spec["param1"]}", {axis1}, '
            f'"{spec["param2"]}", values2, metric="{spec["metric"]}"){unit_note}'
        )

    def _on_copy_script(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.script_text())
        self._status.setText("Script copied to clipboard — paste into the console.")

    def _worker_done_signal(self):  # type: ignore[no-untyped-def]
        """A signal that fires on any terminal worker outcome (tests).

        Returns the dialog-level ``sweepSettled`` signal, emitted from the
        finished/cancelled/failed handlers.
        """
        return self.sweepSettled

    # -- accessors (tests) ----------------------------------------------------------

    @property
    def status_text(self) -> str:
        """The status-line text (tests)."""
        return self._status.text()


__all__ = ["SweepDialog"]

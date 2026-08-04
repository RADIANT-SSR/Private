"""The Run → Run Sweep… dialog — 1-D / 2-D parameter sweeps as a GUI flow (GT-1).

:class:`SweepDialog` is the Tier-2 sweep surface: pick a parameter (schema-driven —
every float `ParameterDef`), enter a range **in the parameter's input unit**
(converted once at the dialog boundary, Rule 2), pick the metric, and Run. The
sweep executes on a worker thread through the public `Sensor.sweep` /
`Sensor.sweep_2d` with the Gap 72 progress/cancel hooks; a progress bar (shown
only while a run exists) tracks done/total, and Cancel aborts cleanly
(`OperationCancelledError` is an expected outcome — the API returns **no partial
results on cancel** by contract, and the dialog says so honestly rather than
pretending). The finished curve (1-D) or heatmap (2-D) renders into the dialog's
canvas **in the units the analyst typed** (entry/display symmetry — the owner
hard rule; CU-326 item 4), every axis and the colorbar unit-suffixed, and
**Copy as script** puts a complete, runnable, *reproducing* reproduction block on
the clipboard so a GUI-configured sweep graduates to the scripting console
(CU-325: the emitted values are the canonical values the sweep actually ran).

Escape/Close during a run does not orphan the worker (CU-325): the dialog
requests a cancel, stays open with an honest status line, and closes itself when
the worker settles. Ranges are validated against the schema bounds **before**
launch, so a bad axis fails at 0/N with the offending endpoint named, not at
point 1 of 121. On selecting a parameter the range seeds around the session's
current value (clamped to bounds) and the unit chip shows that current value —
the analyst never has to remember it from the main window. The last-run spec
persists across dialog openings (Sarah's 3–5×/week loop re-opens configured).

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
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.api import OperationCancelledError
from radiant.core.exceptions import RadiantError
from radiant.gui.display_units import pretty_unit
from radiant.gui.errors import GuiValidationError
from radiant.gui.metric_format import metric_display_label
from radiant.gui.settings_store import SettingsStore
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas

if TYPE_CHECKING:
    from PySide6.QtGui import QCloseEvent

    from radiant.api.sensor import Sensor

# The idle hint shown before any run (an empty axes region reads as broken).
_IDLE_HINT = "Configure a range and Run sweep — the result plots here."


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
        settings: SettingsStore | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("sweepDialog")
        self.setWindowTitle("Run Sweep")
        self.resize(640, 620)

        self._sensor = sensor
        self._settings = settings if settings is not None else SettingsStore()
        self._worker: _SweepWorker | None = None
        self.sweep_result: Any | None = None
        self._last_spec: dict[str, Any] | None = None
        self._close_pending = False

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
        self._start1, self._stop1, self._n1 = QLineEdit("0"), QLineEdit("1"), QLineEdit("11")
        self._unit1 = QLabel("", self)
        self._log1 = QCheckBox("Log spacing", self)
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
        self._start2, self._stop2, self._n2 = QLineEdit("0"), QLineEdit("1"), QLineEdit("11")
        self._unit2 = QLabel("", self)
        self._log2 = QCheckBox("Log spacing", self)
        grid.addWidget(QLabel("Parameter 2"), 4, 0)
        grid.addWidget(self._param2, 4, 1, 1, 3)
        grid.addWidget(self._unit2, 4, 4)
        grid.addWidget(QLabel("Start"), 5, 0)
        grid.addWidget(self._start2, 5, 1)
        grid.addWidget(QLabel("Stop"), 5, 2)
        grid.addWidget(self._stop2, 5, 3)
        grid.addWidget(QLabel("Points"), 6, 0)
        grid.addWidget(self._n2, 6, 1)
        grid.addWidget(self._log2, 6, 2, 1, 2)

        self._metric = QComboBox(self)
        for key in metric_names or ("snr",):
            # Display name in the row, registry key as the data (the spec uses keys).
            self._metric.addItem(metric_display_label(key), userData=key)
        grid.addWidget(QLabel("Metric"), 7, 0)
        grid.addWidget(self._metric, 7, 1, 1, 3)
        layout.addWidget(grid_host)

        self._canvas = MatplotlibCanvas(self)
        layout.addWidget(self._canvas, 1)

        # Hidden until a run exists — an idle "0%" meter is noise (2026-08-03 critique).
        self._progress = QProgressBar(self)
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status = QLabel(_IDLE_HINT, self)
        self._status.setObjectName("sweepStatusLabel")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        buttons = QWidget(self)
        row = QHBoxLayout(buttons)
        row.setContentsMargins(0, 0, 0, 0)
        self._run = QPushButton("Run sweep", buttons)
        self._run.setObjectName("sweepRunButton")
        self._run.setDefault(True)  # Enter runs — the dialog's one loud element
        self._cancel = QPushButton("Cancel run", buttons)
        self._cancel.setEnabled(False)
        self._copy = QPushButton("Copy as script", buttons)
        self._copy.setEnabled(False)
        self._close = QPushButton("Close", buttons)
        row.addWidget(self._run)
        row.addWidget(self._cancel)
        row.addStretch(1)
        row.addWidget(self._copy)
        row.addWidget(self._close)
        layout.addWidget(buttons)

        self._run.clicked.connect(self.start_sweep)
        self._cancel.clicked.connect(self._on_cancel_clicked)
        self._copy.clicked.connect(self._on_copy_script)
        self._close.clicked.connect(self.reject)

        # Range seeding around the session's current value; the last-run spec
        # (persisted) wins over the seed so a reopened dialog is ready to re-run.
        self._param1.currentTextChanged.connect(self._on_param1_changed)
        self._param2.currentTextChanged.connect(lambda _t: self._refresh_unit_labels())

        self._on_2d_toggled(False)
        if not self._restore_last_spec():
            self._on_param1_changed(self._param1.currentText())
        self._refresh_unit_labels()

    # -- seeding + persistence -------------------------------------------------

    def _current_input_value(self, dotpath: str) -> float | None:
        """The session's current value for *dotpath*, in its input unit."""
        try:
            value = self._sensor.get_input(dotpath)
        except (KeyError, RadiantError):
            return None
        return None if value is None else float(value)

    def _seed_range_from_current(self, dotpath: str) -> None:
        """Seed Start/Stop at ×0.5 / ×1.5 of the current value, clamped to bounds.

        The critique's "physics-blind defaults" fix: a sweep starts life
        bracketing where the analyst actually is, in the input unit, instead of
        an alphabetical parameter's 0→1. A parameter with no current value (or a
        zero, where ×0.5/×1.5 collapses) keeps the previous field contents.
        """
        pdef = self._defs.get(dotpath)
        current = self._current_input_value(dotpath)
        if pdef is None or current is None or current == 0.0:
            return
        lo, hi = current * 0.5, current * 1.5
        if pdef.bounds is not None:
            # Schema bounds are declared in the input unit (e.g. pixel pitch
            # 0.1–1000 µm), the same unit the fields are typed in.
            b_lo, b_hi = pdef.bounds
            lo = min(max(lo, b_lo), b_hi)
            hi = min(max(hi, b_lo), b_hi)
        self._start1.setText(f"{lo:g}")
        self._stop1.setText(f"{hi:g}")

    def _on_param1_changed(self, dotpath: str) -> None:
        self._seed_range_from_current(dotpath)
        # Parameter 2 must differ — nudge it off a collision (guaranteed-error default).
        if self._param2.currentText() == dotpath:
            for name in sorted(self._defs):
                if name != dotpath:
                    self._param2.setCurrentText(name)
                    break
        self._refresh_unit_labels()

    def _restore_last_spec(self) -> bool:
        """Re-fill the form from the persisted last-run spec; True on success."""
        raw = self._settings.last_sweep_spec()
        if not raw:
            return False
        try:
            if raw["param1"] not in self._defs:
                return False
            self._param1.setCurrentText(raw["param1"])
            self._start1.setText(raw["start1"])
            self._stop1.setText(raw["stop1"])
            self._n1.setText(raw["n1"])
            self._log1.setChecked(bool(raw.get("log1", False)))
            index = self._metric.findData(raw.get("metric"))
            if index >= 0:
                self._metric.setCurrentIndex(index)
            if raw.get("mode") == "2d" and raw.get("param2") in self._defs:
                self._enable_2d.setChecked(True)
                self._param2.setCurrentText(raw["param2"])
                self._start2.setText(raw.get("start2", "0"))
                self._stop2.setText(raw.get("stop2", "1"))
                self._n2.setText(raw.get("n2", "11"))
                self._log2.setChecked(bool(raw.get("log2", False)))
        except (KeyError, TypeError):
            return False
        return True

    def _persist_spec(self, spec: dict[str, Any]) -> None:
        keep = {
            k: spec[k]
            for k in ("mode", "param1", "start1", "stop1", "n1", "log1", "metric")
            if k in spec
        }
        for k in ("param2", "start2", "stop2", "n2", "log2"):
            if k in spec:
                keep[k] = spec[k]
        self._settings.set_last_sweep_spec(keep)

    # -- spec assembly ---------------------------------------------------------

    def _refresh_unit_labels(self) -> None:
        """Unit chip + the current session value — the range's reference point."""
        for combo, label in ((self._param1, self._unit1), (self._param2, self._unit2)):
            pdef = self._defs.get(combo.currentText())
            if pdef is None:
                label.setText("")
                continue
            unit = pretty_unit(pdef.input_unit) if pdef.input_unit else "–"
            current = self._current_input_value(combo.currentText())
            if current is not None:
                label.setText(f"[{unit}] · now {current:g}")
            else:
                label.setText(f"[{unit}]")

    def _on_2d_toggled(self, on: bool) -> None:
        for w in (self._param2, self._start2, self._stop2, self._n2, self._unit2, self._log2):
            w.setEnabled(on)

    def _axis_values(
        self, dotpath: str, start_text: str, stop_text: str, n_text: str, log: bool
    ) -> np.ndarray:
        """The typed range as the array `Sensor.sweep` consumes — **input-unit** values.

        ``Sensor.sweep`` interprets values exactly as ``sensor.set`` does: in the
        parameter's input unit, with the single Rule-2 conversion happening
        inside the API. The dialog therefore passes the typed numbers through
        untouched. (Until CU-325 it converted them to canonical first, so any
        parameter whose input unit differs from canonical — pixel pitch in µm,
        jitter in µrad — swept values 10⁶-ish off or died on the bounds check.
        The sweep, its plot, and the emitted script now all share one unit: the
        one the analyst typed.)

        Pre-validates against the schema bounds (declared in the input unit), so
        a bad range fails **here**, at 0/N, with the offending endpoint named —
        never at point 1 of 121 mid-run.
        """
        pdef = self._defs[dotpath]
        start, stop, n = float(start_text), float(stop_text), int(n_text)
        if n < 2:
            raise GuiValidationError(f"points must be >= 2, got {n}")
        if log:
            if start <= 0 or stop <= 0:
                raise GuiValidationError("log spacing needs positive start/stop")
            values = np.logspace(np.log10(start), np.log10(stop), n)
        else:
            values = np.linspace(start, stop, n)
        if pdef.bounds is not None:
            b_lo, b_hi = pdef.bounds
            lo, hi = min(start, stop), max(start, stop)
            if lo < b_lo or hi > b_hi:
                unit = pretty_unit(pdef.input_unit) if pdef.input_unit else ""
                raise GuiValidationError(
                    f"{dotpath}: range {start:g}–{stop:g} {unit} escapes the schema "
                    f"bounds [{b_lo:g}, {b_hi:g}] {unit} — narrow the range before running"
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
            "metric": self._metric.currentData() or self._metric.currentText(),
            "keep_results": True,
            # display-unit echo for the plot axes + persistence
            "start1": self._start1.text(),
            "stop1": self._stop1.text(),
            "n1": self._n1.text(),
            "log1": self._log1.isChecked(),
        }
        if spec["mode"] == "2d":
            p2 = self._param2.currentText()
            if p2 == p1:
                raise GuiValidationError("2-D sweep needs two different parameters")
            spec["param2"] = p2
            spec["values2"] = self._axis_values(
                p2,
                self._start2.text(),
                self._stop2.text(),
                self._n2.text(),
                self._log2.isChecked(),
            )
            spec["start2"] = self._start2.text()
            spec["stop2"] = self._stop2.text()
            spec["n2"] = self._n2.text()
            spec["log2"] = self._log2.isChecked()
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
        self._persist_spec(spec)
        total = len(spec["values1"]) * (len(spec.get("values2", [1])))
        self._progress.setVisible(True)
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

    def _display_axis(self, dotpath: str, values: np.ndarray) -> tuple[np.ndarray, str]:
        """Sweep-axis values with their unit-suffixed label (CU-326 item 4).

        ``SweepResult`` carries the values exactly as entered (input units — see
        :meth:`_axis_values`), so the plot is entry/display symmetric for free;
        this helper only writes the truthful label.
        """
        pdef = self._defs[dotpath]
        unit = pdef.input_unit or pdef.canonical_unit or ""
        return values, f"{dotpath} [{pretty_unit(unit) or '–'}]"

    def _metric_axis_label(self, metric_key: str, result: Any) -> str:
        """Metric display name, unit-suffixed when the retained results carry one."""
        label = metric_display_label(metric_key)
        results = getattr(result, "results", ())
        if results:
            try:
                for rec in results[0].metric_records():
                    if rec.name == metric_key and rec.unit and rec.unit != "dimensionless":
                        return f"{label} [{pretty_unit(rec.unit)}]"
            except (AttributeError, RadiantError):
                pass
        return label

    def _on_finished(self, result: Any) -> None:
        self._finish_ui()
        self.sweepSettled.emit()
        self.sweep_result = result
        self._copy.setEnabled(True)
        spec = self._last_spec or {}
        figure = Figure(figsize=(5.6, 3.4), tight_layout=True)
        axis = figure.add_subplot(111)
        metric_key = spec.get("metric", "metric")
        if spec.get("mode") == "1d":
            x, x_label = self._display_axis(spec["param1"], np.asarray(result.values))
            axis.plot(x, result.metric_values, marker="o")
            axis.set_xlabel(x_label)
            axis.set_ylabel(self._metric_axis_label(metric_key, result))
            if spec.get("log1"):
                axis.set_xscale("log")
            self._status.setText(f"Done — {len(result.values)} points.")
        else:
            # pcolormesh with the real coordinate arrays: correct for log-spaced
            # axes, where imshow's linear extent silently mis-places every cell.
            x, x_label = self._display_axis(spec["param2"], np.asarray(result.values2))
            y, y_label = self._display_axis(spec["param1"], np.asarray(result.values1))
            mesh = axis.pcolormesh(x, y, np.asarray(result.grid), shading="nearest")
            figure.colorbar(mesh, ax=axis, label=metric_display_label(metric_key))
            axis.set_xlabel(x_label)
            axis.set_ylabel(y_label)
            if spec.get("log2"):
                axis.set_xscale("log")
            if spec.get("log1"):
                axis.set_yscale("log")
            self._status.setText(f"Done — {result.grid.shape[0]}×{result.grid.shape[1]} grid.")
        axis.grid(True, alpha=0.3)
        self._canvas.show_figure(figure)

    def _finish_ui(self) -> None:
        self._run.setEnabled(True)
        self._cancel.setEnabled(False)
        if self._worker is not None:
            self._worker.wait(5000)
            self._worker = None
        if self._close_pending:
            self._close_pending = False
            self.accept()

    # -- close guard (CU-325) ---------------------------------------------------

    def _guard_close(self) -> bool:
        """True when it is safe to close now; otherwise cancel + close-on-settle."""
        if self._worker is None or not self._worker.isRunning():
            return True
        self._close_pending = True
        self._worker.request_cancel()
        self._status.setText("Cancelling — the dialog closes when the current point finishes…")
        return False

    def reject(self) -> None:  # noqa: D102 — QDialog override (Esc / Close)
        if self._guard_close():
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 — Qt override
        """Never orphan the worker: a close during a run cancels, then closes."""
        if self._guard_close():
            super().closeEvent(event)
        else:
            event.ignore()

    # -- copy as script -----------------------------------------------------------

    def script_text(self) -> str:
        """A complete, runnable reproduction block for the last-run spec (CU-325).

        Both axes are constructed in the block (the old 2-D emission referenced
        an undefined ``values2`` and raised ``NameError`` on paste), with the
        exact typed endpoints — ``Sensor.sweep`` interprets them in the input
        unit, the same way the dialog just did, so pasting the block reproduces
        the plotted numbers exactly. The unit rides in a comment.
        """
        spec = self._last_spec
        if spec is None:
            return ""

        def axis_line(var: str, param: str, values_key: str, log: bool) -> str:
            pdef = self._defs[param]
            values = spec[values_key]
            lo, hi, n = float(values[0]), float(values[-1]), len(values)
            if log:
                expr = f"np.logspace(np.log10({lo!r}), np.log10({hi!r}), {n})"
            else:
                expr = f"np.linspace({lo!r}, {hi!r}, {n})"
            unit = pdef.input_unit or "canonical"
            return f"{var} = {expr}  # {param} in {unit} (input unit, as entered)"

        lines = [axis_line("values1", spec["param1"], "values1", bool(spec.get("log1")))]
        if spec["mode"] == "1d":
            lines.append(
                f'sweep = sensor.sweep("{spec["param1"]}", values1, '
                f'metric="{spec["metric"]}", keep_results=True)'
            )
        else:
            lines.append(axis_line("values2", spec["param2"], "values2", bool(spec.get("log2"))))
            lines.append(
                f'sweep2d = sensor.sweep_2d("{spec["param1"]}", values1, '
                f'"{spec["param2"]}", values2, metric="{spec["metric"]}")'
            )
        return "\n".join(lines)

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

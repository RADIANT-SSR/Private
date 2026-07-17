"""Tools → Solve for… — the inverse-solver dialog (Tier-2 GT-6 / GUI-8).

:class:`SolveDialog` wraps :meth:`Sensor.solve_for` (Gap 10): pick the free
parameter (every float `ParameterDef`), the target metric and value, and a
bracket **in the parameter's input unit** (the API's contract); the Brent
iteration runs on a worker thread against a **clone** (a solve never mutates
the session config until you say so). Success reports the solution with its
unit, the achieved metric, and the evaluation count — and offers **Apply
solution** (one ``sensor.set`` on the live sensor). A non-bracketing target
surfaces the API's actionable `SolveBracketError` (both endpoint metric values)
inline; a plateaued metric cannot be bracketed, and the message says so.

One widget class per file (Rule 19).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.core.exceptions import RadiantError

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor


class _SolveWorker(QThread):
    """One solve_for call off the UI thread (no progress hooks by design)."""

    finished_ok = Signal(object)  # SolveResult
    failed = Signal(object)  # Exception

    def __init__(self, sensor: Sensor, spec: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self._sensor = sensor
        self._spec = spec

    def run(self) -> None:  # noqa: D102 — QThread override
        try:
            result = self._sensor.solve_for(
                self._spec["param"],
                self._spec["target"],
                bounds=self._spec["bounds"],
                metric=self._spec["metric"],
            )
        except RadiantError as exc:
            self.failed.emit(exc)
            return
        self.finished_ok.emit(result)


class SolveDialog(QDialog):
    """Solve a parameter for a target metric value (GT-6)."""

    #: fires on any terminal outcome (solved / failed)
    solveSettled = Signal()

    def __init__(
        self,
        sensor: Sensor,
        metric_names: tuple[str, ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("solveDialog")
        self.setWindowTitle("Solve for Parameter")
        self.resize(520, 300)
        self._sensor = sensor
        self._worker: _SolveWorker | None = None
        self.solve_result: Any | None = None

        self._defs = {
            name: pdef for name, pdef in sensor.parameter_defs().items() if pdef.dtype is float
        }

        layout = QVBoxLayout(self)
        host = QWidget(self)
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 0, 0, 0)

        self._param = QComboBox(self)
        self._param.addItems(sorted(self._defs))
        self._param.currentTextChanged.connect(lambda _t: self._refresh_unit())
        self._unit = QLabel("", self)
        grid.addWidget(QLabel("Free parameter"), 0, 0)
        grid.addWidget(self._param, 0, 1, 1, 3)
        grid.addWidget(self._unit, 0, 4)

        self._metric = QComboBox(self)
        self._metric.addItems(list(metric_names) or ["snr"])
        self._target = QLineEdit("500", self)
        grid.addWidget(QLabel("Target metric"), 1, 0)
        grid.addWidget(self._metric, 1, 1)
        grid.addWidget(QLabel("="), 1, 2)
        grid.addWidget(self._target, 1, 3)

        self._lo, self._hi = QLineEdit("0.1", self), QLineEdit("1.0", self)
        grid.addWidget(QLabel("Bracket"), 2, 0)
        grid.addWidget(self._lo, 2, 1)
        grid.addWidget(QLabel("to"), 2, 2)
        grid.addWidget(self._hi, 2, 3)
        layout.addWidget(host)

        self._status = QLabel("", self)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        buttons = QWidget(self)
        from PySide6.QtWidgets import QHBoxLayout

        row = QHBoxLayout(buttons)
        row.setContentsMargins(0, 0, 0, 0)
        self._run = QPushButton("Solve", buttons)
        self._run.clicked.connect(self.start_solve)
        self._apply = QPushButton("Apply solution", buttons)
        self._apply.setEnabled(False)
        self._apply.clicked.connect(self._on_apply)
        row.addWidget(self._run)
        row.addStretch(1)
        row.addWidget(self._apply)
        layout.addWidget(buttons)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        box.rejected.connect(self.reject)
        box.accepted.connect(self.accept)
        layout.addWidget(box)
        self._refresh_unit()

    def _refresh_unit(self) -> None:
        pdef = self._defs.get(self._param.currentText())
        self._unit.setText(f"[{pdef.input_unit or '–'}]" if pdef else "")

    def start_solve(self) -> None:
        """Validate the spec and launch the worker (clone — never the live sensor)."""
        try:
            spec = {
                "param": self._param.currentText(),
                "metric": self._metric.currentText(),
                "target": float(self._target.text()),
                "bounds": (float(self._lo.text()), float(self._hi.text())),
            }
        except ValueError as exc:
            self._status.setText(f"Invalid solve spec — {exc}")
            return
        self._run.setEnabled(False)
        self._apply.setEnabled(False)
        self._status.setText("Solving… (Brent iteration; evaluation count is not predictable)")
        self._worker = _SolveWorker(self._sensor.clone(), spec, self)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_failed(self, exc: BaseException) -> None:
        self._finish()
        self._status.setText(f"Solve failed — {exc}")
        self.solveSettled.emit()

    def _on_finished(self, result: Any) -> None:
        self._finish()
        self.solve_result = result
        pdef = self._defs[result.param_name]
        self._status.setText(
            f"{result.param_name} = {result.solution:.6g} {pdef.input_unit or ''} → "
            f"{result.metric_name} = {result.achieved:.6g} "
            f"({result.n_evaluations} evaluations)"
        )
        self._apply.setEnabled(True)
        self.solveSettled.emit()

    def _finish(self) -> None:
        self._run.setEnabled(True)
        if self._worker is not None:
            self._worker.wait(5000)
            self._worker = None

    def _on_apply(self) -> None:
        """Commit the solution to the live sensor — one sensor.set (input units)."""
        result = self.solve_result
        if result is None:
            return
        self._sensor.set(result.param_name, float(result.solution))
        self._status.setText(
            f"Applied: {result.param_name} = {result.solution:.6g} — re-evaluate to see it."
        )

    @property
    def status_text(self) -> str:
        """The status-line text (tests)."""
        return self._status.text()


__all__ = ["SolveDialog"]

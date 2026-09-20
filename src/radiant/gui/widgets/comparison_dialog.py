"""The Tools → Compare Config Files… dialog (Tier-2 GT-3, over Gap 79's primitive).

:class:`ComparisonDialog` compares the **current config** against N config **files on
disk**. The label says "config files" deliberately (CU-214, ADR-0010 D-10): since the
multi-configuration work landed, a bare "configuration" means a member of one study's
configuration set, and the per-configuration comparison surface for those is the
Performance stage's columns (§4.4.1) and the scripting ``ConfigurationSet.compare``.
This dialog is the *file* comparison and is unrelated to a study's configurations.

Each column evaluates once on a worker thread (sequential, with
progress), then :func:`radiant.api.compare_configs` builds the aligned matrix —
union-of-metrics rows with registry units, per-metric deltas against the chosen
baseline, and conservative best-per-metric marks (rendered bold with a ✓). A
metric absent from a config shows "—", never a zero (Rule 17). The atmosphere
A/B swap (GUI-10) falls out: load a variant file, or save the current config,
flip one parameter, and add the saved file.

Evaluation always runs on **clones** (the session sensor is never mutated).
One widget class per file (Rule 19); styling from the QSS theme.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from radiant.api import ComparisonError, Sensor, compare_configs
from radiant.api.config_set import ConfigurationSet
from radiant.core.exceptions import RadiantError

# The one place the Tools action and the dialog title agree on their wording (CU-214).
# The trailing ellipsis marks the menu item as opening a dialog; the window title drops
# it, per the platform convention the rest of the menu bar follows.
COMPARE_FILES_MENU_TEXT: str = "Compare Config Files…"
COMPARE_FILES_TITLE: str = "Compare Config Files"

if TYPE_CHECKING:
    from radiant.api import ComparisonResult


def _column_labels(path: Path) -> list[str]:
    """The column labels *path* will contribute, without evaluating anything.

    One label (the stem) for a plain config or an unreadable file (its failure
    surfaces when the comparison runs); ``stem:name`` per configuration for a study.
    """
    try:
        config_set = ConfigurationSet.load(path)
    except RadiantError:
        return [path.stem]
    if len(config_set) == 1 and not config_set.configured():
        return [path.stem]
    return [f"{path.stem}:{name}" for name in config_set.names()]


def _columns_for(path: Path) -> list[tuple[str, Sensor]]:
    """``(label, sensor)`` columns for *path* — the loaded plain config, or each
    configuration of a study materialized through ``sensor_for`` (the API's one
    materialization path, so configured values and element rows apply)."""
    config_set = ConfigurationSet.load(path)
    if len(config_set) == 1 and not config_set.configured():
        return [(path.stem, config_set.base)]
    return [(f"{path.stem}:{name}", config_set.sensor_for(name)) for name in config_set.names()]


class _EvaluateAllWorker(QThread):
    """Evaluate each labeled sensor clone sequentially, off the UI thread."""

    progressed = Signal(int, int)
    finished_ok = Signal(object)  # list[tuple[str, ChainResult]]
    failed = Signal(str, object)  # (label, Exception)

    def __init__(self, items: list[tuple[str, Sensor]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items = items

    def run(self) -> None:  # noqa: D102 — QThread override
        results: list[tuple[str, Any]] = []
        total = len(self._items)
        for i, (label, sensor) in enumerate(self._items):
            try:
                results.append((label, sensor.evaluate()))
            except RadiantError as exc:
                self.failed.emit(label, exc)
                return
            self.progressed.emit(i + 1, total)
        self.finished_ok.emit(results)


class ComparisonDialog(QDialog):
    """Compare the current config against loaded config files (GT-3)."""

    def __init__(self, sensor: Sensor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("comparisonDialog")
        self.setWindowTitle(COMPARE_FILES_TITLE)
        self.resize(760, 560)

        self._sensor = sensor
        self._worker: _EvaluateAllWorker | None = None
        self.comparison: ComparisonResult | None = None
        # Added files: (path, column labels). A plain config is one column named by
        # its stem; a study file is one column per configuration, "stem:name"
        # (CU-375 F-23 — the dialog reads both kinds through the one loader File ▸
        # Open uses, instead of refusing a study with an API instruction).
        self._entries: list[tuple[Path, list[str]]] = []

        layout = QVBoxLayout(self)

        top = QWidget(self)
        row = QHBoxLayout(top)
        row.setContentsMargins(0, 0, 0, 0)
        self._config_list = QListWidget(top)
        self._config_list.addItem("current (live sensor)")
        row.addWidget(self._config_list, 1)
        side = QVBoxLayout()
        self._add = QPushButton("Add config file…", top)
        self._add.clicked.connect(self._on_add)
        self._remove = QPushButton("Remove selected", top)
        self._remove.clicked.connect(self._on_remove)
        side.addWidget(self._add)
        side.addWidget(self._remove)
        side.addStretch(1)
        row.addLayout(side)
        layout.addWidget(top)

        base_row = QWidget(self)
        brow = QHBoxLayout(base_row)
        brow.setContentsMargins(0, 0, 0, 0)
        brow.addWidget(QLabel("Baseline:", base_row))
        self._baseline = QComboBox(base_row)
        self._baseline.addItem("current")
        brow.addWidget(self._baseline, 1)
        self._run = QPushButton("Evaluate && compare", base_row)
        self._run.clicked.connect(self.start_comparison)
        brow.addWidget(self._run)
        layout.addWidget(base_row)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self._table = QTableWidget(0, 0, self)
        self._table.setObjectName("comparisonTable")
        layout.addWidget(self._table, 1)

        self._status = QLabel("", self)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        box.rejected.connect(self.reject)
        box.accepted.connect(self.accept)
        layout.addWidget(box)

    # -- config list -------------------------------------------------------------

    def _on_add(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Add RADIANT config", "", "RADIANT config (*.yaml *.yml);;All files (*)"
        )
        if filename:
            self.add_config(Path(filename))

    def add_config(self, path: Path) -> None:
        """Add a config file: one column (file stem) or, for a study, one per configuration.

        The file is read now to learn its columns (``ConfigurationSet.load`` reads
        both document kinds, exactly as File ▸ Open does); a file that does not load
        is still listed, so **Run comparison** reports the failure actionably.
        """
        labels = _column_labels(path)
        self._entries.append((path, labels))
        suffix = f"  ({len(labels)} configurations)" if len(labels) > 1 else ""
        self._config_list.addItem(f"{path}{suffix}")
        for label in labels:
            self._baseline.addItem(label)

    def _on_remove(self) -> None:
        index = self._config_list.currentRow()
        if index <= 0:  # the current-sensor column is fixed
            return
        self._config_list.takeItem(index)
        _path, labels = self._entries.pop(index - 1)
        # Baseline items mirror the evaluated columns: "current", then every
        # entry's labels in order — drop this entry's block.
        first = 1 + sum(len(entry_labels) for _p, entry_labels in self._entries[: index - 1])
        for _ in labels:
            self._baseline.removeItem(first)

    # -- run -----------------------------------------------------------------------

    def start_comparison(self) -> None:
        """Load + evaluate every column on the worker, then build the matrix."""
        items: list[tuple[str, Sensor]] = [("current", self._sensor.clone())]
        try:
            for path, _labels in self._entries:
                items.extend(_columns_for(path))
        except RadiantError as exc:
            what = str(getattr(exc, "what", "") or exc)
            self._status.setText(f"Config load failed — {what}")
            return
        if len(items) < 2:
            self._status.setText("Add at least one config file to compare against.")
            return
        self._run.setEnabled(False)
        self._progress.setRange(0, len(items))
        self._progress.setValue(0)
        self._status.setText(f"Evaluating 0/{len(items)}…")
        self._worker = _EvaluateAllWorker(items, self)
        self._worker.progressed.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        self._progress.setValue(done)
        self._status.setText(f"Evaluating {done}/{total}…")

    def _on_failed(self, label: str, exc: BaseException) -> None:
        self._finish_ui()
        self._status.setText(f"'{label}' failed to evaluate — {exc}")
        self.comparisonSettled.emit()

    def _on_finished(self, results: list[tuple[str, Any]]) -> None:
        self._finish_ui()
        try:
            self.comparison = compare_configs(results, baseline=self._baseline.currentIndex())
        except ComparisonError as exc:
            self._status.setText(str(exc))
            return
        self._render(self.comparison)
        self.comparisonSettled.emit()
        self._status.setText(
            f"{len(self.comparison.rows)} metrics × {len(self.comparison.labels)} configs "
            f"(Δ vs {self.comparison.labels[self.comparison.baseline_index]}; ✓ = best)"
        )

    def _finish_ui(self) -> None:
        self._run.setEnabled(True)
        if self._worker is not None:
            self._worker.wait(5000)
            self._worker = None

    # -- render -----------------------------------------------------------------------

    def _render(self, cmp_: ComparisonResult) -> None:
        headers = ["metric", "unit", *cmp_.labels]
        self._table.setRowCount(len(cmp_.rows))
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        for r, row in enumerate(cmp_.rows):
            self._table.setItem(r, 0, QTableWidgetItem(row.name))
            self._table.setItem(r, 1, QTableWidgetItem(row.unit))
            for c, value in enumerate(row.values):
                if value is None:
                    text = "—"  # absent, never zero-filled (Rule 17)
                else:
                    text = f"{value:.6g}"
                    delta = row.deltas[c]
                    if delta is not None and c != cmp_.baseline_index:
                        text += f"  (Δ {delta:+.4g})"
                if row.best_index == c:
                    text = f"✓ {text}"
                item = QTableWidgetItem(text)
                item.setToolTip(row.description)
                if row.best_index == c:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self._table.setItem(r, 2 + c, item)
        self._table.resizeColumnsToContents()

    # -- accessors (tests) ---------------------------------------------------------------

    @property
    def status_text(self) -> str:
        """The status-line text (tests)."""
        return self._status.text()

    @property
    def table(self) -> QTableWidget:
        """The comparison table (tests)."""
        return self._table

    def settled_signal(self):  # type: ignore[no-untyped-def]
        """Terminal-outcome signal for tests."""
        return self.comparisonSettled

    #: fires on any terminal outcome of a run (rendered / failed)
    comparisonSettled = Signal()


__all__ = ["COMPARE_FILES_MENU_TEXT", "COMPARE_FILES_TITLE", "ComparisonDialog"]

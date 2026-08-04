"""The accent Run / Evaluate button (mockup ``.runbtn``; QSS hook ``#runButton``).

:class:`RunButton` is the terracotta-accent primary action from the mockup's KPI
strip, living in the right-rail footer since the contextual-layout retrofit (§4.5).
It carries the GUI's **staleness trust signal** (arch doc §8.4, CU-327): when the
displayed results predate the last edit — or the last run failed — the button flips
to the ``warn`` fill and reads *Re-evaluate*, so the primary action itself says
"these numbers are out of date." The flip is driven by :meth:`set_stale` from the
main window's edit/failure/success slots; styling comes from the
``QPushButton#runButton`` QSS rules and their ``[stale="true"]`` variant (GUI plan
§4.9) — this file holds no colour, font, or size literal.
"""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QWidget

# The label pairs the action with its shortcut (Run ▸ Evaluate, F5 — arch doc §10).
_LABEL: str = "Evaluate  F5"
# The stale-state label: same action, urgent voice (arch doc §8.4 "re-evaluate").
_LABEL_STALE: str = "Re-evaluate  F5"


class RunButton(QPushButton):
    """The accent Evaluate button; construction leaves it disabled until a config loads.

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_LABEL, parent)
        self.setObjectName("runButton")
        # Disabled until the evaluate loop has a loaded config (arch doc §3.2).
        self.setEnabled(False)
        self.setProperty("stale", False)
        self.setToolTip("Evaluate the full chain (F5) — available once a config is loaded")

    def set_stale(self, stale: bool) -> None:
        """Flip the staleness trust signal (arch doc §8.4, CU-327).

        ``True`` — results on screen predate the last edit (or the last run
        failed): warn fill, *Re-evaluate* label. ``False`` — the displayed
        results are current: accent fill, *Evaluate* label. Repolishes the
        style so the ``[stale="true"]`` QSS variant applies immediately.
        """
        if bool(self.property("stale")) == stale:
            return
        self.setProperty("stale", stale)
        self.setText(_LABEL_STALE if stale else _LABEL)
        self.setToolTip(
            "Results predate the last edit — press to re-evaluate (F5)"
            if stale
            else "Evaluate the full chain (F5)"
        )
        style = self.style()
        style.unpolish(self)
        style.polish(self)

    def is_stale(self) -> bool:
        """Whether the stale trust signal is currently shown."""
        return bool(self.property("stale"))

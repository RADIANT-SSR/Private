"""A small themed status dot (the stage-strip / noise-term health indicator).

:class:`HealthDot` is the reusable 9–11 px circle described in
``RADIANT_GUI_Architecture.md`` §8.4: a fill in one of the themed status tokens
(``ok`` / ``warn`` / ``err`` / ``stale``) wrapped in a soft ring. The colour comes
entirely from the QSS theme, keyed off the widget's ``status`` dynamic property —
this widget sets structure and the property only, never a colour (GUI plan §4.9).

In GUI plan Phase 1 every dot is ``"stale"`` (nothing has been evaluated yet); the
:meth:`set_status` hook is what Phase 4 calls once the chain reports per-stage health.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtWidgets import QFrame, QWidget

# The valid health states, matching the themed tokens (§8.1/§8.4). The setter fails
# loudly (ValueError) on an unknown state rather than silently rendering unstyled.
VALID_STATUSES: Final[tuple[str, ...]] = ("ok", "warn", "err", "stale")

# Diameter in device-independent px (§8.4: a 9–11 px circle). Geometry, not a design
# token — the colour is the token, sourced from the theme via the ``status`` property.
_DIAMETER_PX: Final[int] = 11


class HealthDot(QFrame):
    """A themed health dot whose colour follows its ``status`` dynamic property.

    Parameters
    ----------
    status:
        One of :data:`VALID_STATUSES`. Phase 1 always passes ``"stale"``.
    parent:
        The owning widget, if any.
    """

    def __init__(self, status: str = "stale", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("healthDot")
        self.setFixedSize(_DIAMETER_PX, _DIAMETER_PX)
        self._status = ""
        self.set_status(status)

    @property
    def status(self) -> str:
        """The current health status (one of :data:`VALID_STATUSES`)."""
        return self._status

    def set_status(self, status: str) -> None:
        """Set the health status, re-polishing so the QSS colour updates.

        Raises :class:`ValueError` on an unknown status — an unstyled dot would be a
        silent failure (Rule 17), so the caller hears about a bad state immediately.
        """
        if status not in VALID_STATUSES:
            raise ValueError(f"HealthDot status must be one of {VALID_STATUSES}, got {status!r}")
        self._status = status
        # QSS targets QFrame#healthDot[status="..."]; the property drives the colour.
        self.setProperty("status", status)
        # Force a style refresh so a status change after construction re-colours.
        style = self.style()
        style.unpolish(self)
        style.polish(self)

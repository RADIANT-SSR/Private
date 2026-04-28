"""Interaction state — frame switcher + active edit + canonical view.

Phase 5 (PLAN_v2.md §13) interaction state machine, separate from
``SceneState`` so the *physics* state and the *UI* state stay
decoupled. ``SceneState`` controls what the radiometry would see;
``InteractionState`` controls what the user is looking at and editing.

Why separate? The frame switcher (World / Body / Sensor) is a display
concern: it doesn't change the radiometric inputs, just how they are
projected for the human reader. Likewise the active-edit selection is
a UI cursor, not a physics input. Keeping them in their own dataclass
means the C3 invariant (``projected_area_m2`` matches
``shape.projected_area``) is unaffected by anything the user clicks
on.

Rule 19: own file. The view-mode enum, the active-edit cursor, and
the canonical-view enum are tightly coupled (they all live in this
state and update together) — Rule 19's "tightly coupled" carve-out
applies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from typing import Final


@unique
class DisplayFrame(Enum):
    """Which coordinate frame the readouts and overlay label express."""

    WORLD = "world"
    BODY = "body"
    SENSOR = "sensor"

    @property
    def display_name(self) -> str:
        return self.value.title()


@unique
class CanonicalView(Enum):
    """The seven view-cube faces, all reachable via keyboard shortcut."""

    FRONT = "front"   # +X looking at target along -X
    BACK = "back"     # -X
    LEFT = "left"     # +Y
    RIGHT = "right"   # -Y
    TOP = "top"       # +Z
    BOTTOM = "bottom"  # -Z
    ISO = "iso"       # canonical isometric


# Maps the 1–6 keyboard shortcut number to its canonical view.
KEY_TO_VIEW: Final[dict[str, CanonicalView]] = {
    "1": CanonicalView.FRONT,
    "2": CanonicalView.BACK,
    "3": CanonicalView.LEFT,
    "4": CanonicalView.RIGHT,
    "5": CanonicalView.TOP,
    "6": CanonicalView.BOTTOM,
}


@dataclass(frozen=True)
class InteractionState:
    """UI state that's distinct from physics state.

    Frozen so the parent ``GeometryMainWindow`` can swap the whole
    object on every change and rely on equality comparisons to detect
    drift. Replace fields with ``dataclasses.replace``.
    """

    display_frame: DisplayFrame = DisplayFrame.BODY
    active_edit: str | None = None
    last_canonical_view: CanonicalView = CanonicalView.ISO

    def with_display_frame(self, frame: DisplayFrame) -> "InteractionState":
        from dataclasses import replace

        return replace(self, display_frame=frame)

    def with_active_edit(self, name: str | None) -> "InteractionState":
        from dataclasses import replace

        return replace(self, active_edit=name)

    def with_canonical_view(self, view: CanonicalView) -> "InteractionState":
        from dataclasses import replace

        return replace(self, last_canonical_view=view)


# Frame indicator overlay text (PLAN_v2.md §13 step 7) — one line for the
# top-left HUD label.
def frame_indicator_text(state: InteractionState) -> str:
    """Top-left HUD line: 'Frame: Body  ·  Origin: Target centroid'."""
    return f"Frame: {state.display_frame.display_name}  \u00b7  Origin: Target centroid"

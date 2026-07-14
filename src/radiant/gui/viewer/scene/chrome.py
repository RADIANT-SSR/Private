"""``SceneChrome`` — the theme-bound chrome colors the 3D viewer follows (ADR-0007 §3).

The viewer's *chrome* — the viewport background, the leader-line connectors, and the
label pill — must match the surrounding app so the 3D panel does not read as "a different
app in a window" (ADR-0007 §3, the light-theme integration goal). Unlike the semantic
glyph colors in :mod:`radiant.gui.viewer.scene.palette` (which encode physics and stay
constant), chrome is resolved from the active :class:`~radiant.gui.themes.tokens.Theme`
so the Phase-9 theme toggle restyles the viewport by re-applying a different theme.

This module holds **no color literals** — every field is read from a passed-in
``Theme`` (which lives in ``themes/``, the single owner of visual tokens). The builder
constructs one :class:`SceneChrome` per render and threads it to the two primitives that
paint chrome: the ground fade plane (background match) and the leader labels.
"""

from __future__ import annotations

from dataclasses import dataclass

from radiant.gui.themes.tokens import Theme


def _hex_to_rgb_unit(hex_color: str) -> tuple[float, float, float]:
    """Convert a ``#rrggbb`` token to a 0–1 RGB triple (VTK color convention)."""
    s = hex_color.lstrip("#")
    return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0, int(s[4:6], 16) / 255.0)


@dataclass(frozen=True)
class SceneChrome:
    """Theme-derived chrome colors for one viewer render.

    Attributes
    ----------
    viewport_bg:
        The plotter background and the ground fade plane — the app surface token
        (``Theme.bg``) so the 3D panel blends into the window.
    leader_line:
        Leader-line connectors and anchor dots — the muted neutral token
        (``Theme.muted``): visible on both themes without competing with the
        family-colored vectors.
    label_pill_rgb:
        The 0–1 RGB fill behind label text — a panel surface (``Theme.panel``) so the
        pill reads as a subtle annotation chip on either theme.
    """

    viewport_bg: str
    leader_line: str
    label_pill_rgb: tuple[float, float, float]

    @classmethod
    def from_theme(cls, theme: Theme) -> SceneChrome:
        """Resolve the chrome colors from a design-system :class:`Theme`."""
        return cls(
            viewport_bg=theme.bg,
            leader_line=theme.muted,
            label_pill_rgb=_hex_to_rgb_unit(theme.panel),
        )


__all__ = ["SceneChrome"]

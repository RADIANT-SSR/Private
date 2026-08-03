"""Token-derived matplotlib house style for every ``result.plot.*`` figure.

One computation (Rule 19): the RADIANT figure style — colour tokens, the
CVD-validated series palette, font-stack resolution, and the rcParams dict the
plot layer applies around each figure build. The owner reversed the old
"figures are not restyled" ruling (arch doc §4.4) on 2026-08-03: figures are
now styled **API-wide** — GUI, scripts, notebooks, and saved PNGs all get the
same instrument look, light or dark.

Token provenance
----------------
The hex values below mirror ``radiant.gui.themes.tokens`` (the GUI token
owner). The API layer cannot import ``radiant.gui`` (import rules: ``gui``
imports ``api``, never the reverse, and the ``gui`` extra may not be
installed), so the values are duplicated here deliberately and the equality is
**test-enforced** (``test_plot_style.py::test_tokens_match_gui_theme``) — the
two copies cannot drift without a red test.

Series palette
--------------
The categorical cycle draws the configuration-accent hues in a **fixed,
CVD-validated order**: blue → amber → teal → terracotta → purple → green
(series 7+ should fold to the slate "other" colour rather than cycling). The
raw slot order fails colour-deficient separation (deuteranopia ΔE·100 ≈ 3.8 on
magenta↔green, Machado severity-1.0 simulation in OKLab); this order's worst
adjacent pair holds ΔE·100 ≥ 10 in both themes (target ≥ 8). The gate is
test-enforced (``test_plot_style.py``). Per-configuration overlays do NOT use
this cycle — a configuration keeps its slot accent (Slot Identity Rule).
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Final

#: Chrome tokens, light theme (mirror of ``gui.themes.tokens.LIGHT`` — see above).
LIGHT: Final[dict[str, str]] = {
    "bg": "#ebeef2",
    "panel": "#fafbfc",
    "panel_2": "#f1f3f6",
    "line": "#cfd5de",
    "line_2": "#b7bfcb",
    "ink": "#1b2230",
    "ink_2": "#384050",
    "muted": "#6b7380",
    "accent": "#b8431a",
    "accent_soft": "#f6e2d6",
    "warn": "#a97c14",
    "warn_soft": "#f5ebcf",
    "focus": "#2f5aa8",
    "focus_soft": "#dde6f4",
}

#: Chrome tokens, dark theme (mirror of ``gui.themes.tokens.DARK``).
DARK: Final[dict[str, str]] = {
    "bg": "#0f1216",
    "panel": "#171a21",
    "panel_2": "#1d2029",
    "line": "#2b3140",
    "line_2": "#3a4254",
    "ink": "#e6e9ef",
    "ink_2": "#c3c9d4",
    "muted": "#8b94a4",
    "accent": "#e08157",
    "accent_soft": "#3a2218",
    "warn": "#e0b249",
    "warn_soft": "#3a2f16",
    "focus": "#86a8df",
    "focus_soft": "#1e2a3e",
}

#: CVD-validated categorical series order (see module docstring), light theme.
SERIES_LIGHT: Final[tuple[str, ...]] = (
    "#2f5aa8",  # blue
    "#a97c14",  # amber
    "#1f7a7a",  # teal
    "#b8431a",  # terracotta
    "#7a3a8e",  # purple
    "#2f7a3a",  # green
)

#: The same six hues, index-matched, stepped for the dark surfaces.
SERIES_DARK: Final[tuple[str, ...]] = (
    "#86a8df",
    "#e0b249",
    "#6fc0c0",
    "#e08157",
    "#c79ad8",
    "#7fb987",
)

#: Fold-to colour for series beyond the cycle ("other"), light / dark.
OTHER_LIGHT: Final[str] = "#5a6270"
OTHER_DARK: Final[str] = "#a8b0be"

#: Design font stacks (mirror of ``gui.themes.tokens`` FONT_SANS / FONT_MONO
#: families, in matplotlib list form). Resolved against the host's installed
#: families before use so matplotlib never warns about a missing family
#: (the same graceful-degradation move ``gui.themes.fonts`` makes — CU-169).
SANS_STACK: Final[tuple[str, ...]] = (
    "IBM Plex Sans",
    "Helvetica Neue",
    "Segoe UI",
    "Cantarell",
    "DejaVu Sans",
)
MONO_STACK: Final[tuple[str, ...]] = (
    "IBM Plex Mono",
    "Menlo",
    "Consolas",
    "DejaVu Sans Mono",
)

# The active theme variant. ``plot_theme(dark=True)`` flips it for the calling
# context; the ``_styled`` wrapper in ``radiant.api.plot`` reads it at figure
# build time. A ContextVar so nested/threaded GUI workers cannot race.
_DARK_ACTIVE: ContextVar[bool] = ContextVar("radiant_plot_dark", default=False)


def active_dark() -> bool:
    """Whether the dark plot variant is active in this context."""
    return _DARK_ACTIVE.get()


def set_dark(dark: bool) -> object:
    """Activate the dark (or light) variant; returns the reset token."""
    return _DARK_ACTIVE.set(dark)


def reset_dark(token: object) -> None:
    """Restore the variant state captured by :func:`set_dark`."""
    _DARK_ACTIVE.reset(token)  # type: ignore[arg-type]


def resolve_stack(stack: tuple[str, ...]) -> list[str]:
    """Drop families the host does not have, keeping the stack's order.

    Returns at least the last (always-shipped DejaVu) family so matplotlib
    always resolves without a findfont warning. Without matplotlib installed
    the stack is returned unchanged (nothing will render anyway).
    """
    try:
        from matplotlib import font_manager
    except ImportError:  # pragma: no cover - matplotlib is required to plot at all
        return list(stack)
    available = set(font_manager.get_font_names())
    kept = [family for family in stack if family in available]
    return kept if kept else [stack[-1]]


def series(dark: bool | None = None) -> tuple[str, ...]:
    """The categorical series cycle for the given (default: active) variant."""
    if dark is None:
        dark = active_dark()
    return SERIES_DARK if dark else SERIES_LIGHT


def tokens(dark: bool | None = None) -> dict[str, str]:
    """The chrome token set for the given (default: active) variant."""
    if dark is None:
        dark = active_dark()
    return DARK if dark else LIGHT


def rcparams(dark: bool | None = None) -> dict[str, Any]:
    """The full rcParams dict for one theme variant.

    Applied by ``radiant.api.plot`` around every figure build. Values derive
    from the chrome tokens and the validated series cycle; nothing here is a
    free literal.
    """
    from cycler import cycler

    if dark is None:
        dark = active_dark()
    t = tokens(dark)
    return {
        "figure.facecolor": t["panel"],
        "savefig.facecolor": t["panel"],
        "axes.facecolor": t["panel_2"] if dark else "#ffffff",
        "font.family": resolve_stack(SANS_STACK),
        "font.size": 10.5,
        "text.color": t["ink"],
        "axes.labelcolor": t["ink_2"],
        "axes.labelsize": 10.5,
        "axes.titlesize": 11.5,
        "axes.titleweight": "semibold",
        "axes.titlecolor": t["ink"],
        "axes.titlelocation": "left",
        "axes.titlepad": 10.0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": t["line_2"],
        "axes.linewidth": 1.0,
        "xtick.color": t["muted"],
        "ytick.color": t["muted"],
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": t["line"],
        "grid.linewidth": 0.8,
        "grid.alpha": 0.6 if dark else 1.0,
        "axes.prop_cycle": cycler(color=list(series(dark))),
        "lines.linewidth": 2.0,
        "lines.markersize": 5.0,
        "lines.solid_capstyle": "round",
        "legend.frameon": True,
        "legend.framealpha": 1.0,
        "legend.facecolor": t["panel"],
        "legend.edgecolor": t["line"],
        "legend.fontsize": 9.0,
        "legend.title_fontsize": 9.5,
        "image.cmap": "viridis",
    }


def mono_family() -> list[str]:
    """The resolved mono stack — for tick labels and value annotations."""
    return resolve_stack(MONO_STACK)

"""Phase 3 layout test — verify the slider / radio / dropdown inventory.

Walks the Dash component tree recursively and counts each control kind. The
totals are pinned to PLAN.md §6:

  * 19 sliders (5 observer + 10 target + 2 sun + 2 sensor)
  *  2 radio item groups (regime override, background kind)
  *  1 dropdown (target shape)

Also asserts the canonical `SLIDER_INPUTS` order published by
`controls_panel.py` is the single source of truth — every published ID must
appear exactly once in the rendered tree.
"""

from __future__ import annotations

from typing import Any

from dash import dcc

from dev_tools.geometry_gui.app.layout.controls_panel import (
    NON_SLIDER_INPUTS,
    SLIDER_INPUTS,
)
from dev_tools.geometry_gui.app.main import app


def _walk(component: Any) -> list[Any]:
    """Yield this component plus every descendant via the `children` attribute."""
    out: list[Any] = [component]
    children = getattr(component, "children", None)
    if children is None:
        return out
    if isinstance(children, (list, tuple)):
        for child in children:
            out.extend(_walk(child))
    else:
        out.extend(_walk(children))
    return out


def test_slider_count() -> None:
    """Exactly 19 sliders are rendered (PLAN.md §6)."""
    sliders = [c for c in _walk(app.layout) if isinstance(c, dcc.Slider)]
    assert len(sliders) == 19, (
        f"expected 19 sliders, got {len(sliders)}: "
        f"{[s.id for s in sliders]}"
    )


def test_radio_count() -> None:
    """Exactly 2 RadioItems groups are rendered (regime override, background)."""
    radios = [c for c in _walk(app.layout) if isinstance(c, dcc.RadioItems)]
    assert len(radios) == 2, (
        f"expected 2 RadioItems, got {len(radios)}: {[r.id for r in radios]}"
    )


def test_dropdown_count() -> None:
    """Exactly 1 Dropdown is rendered (target shape)."""
    dropdowns = [c for c in _walk(app.layout) if isinstance(c, dcc.Dropdown)]
    assert len(dropdowns) == 1, (
        f"expected 1 Dropdown, got {len(dropdowns)}: {[d.id for d in dropdowns]}"
    )
    assert dropdowns[0].id == "tgt-shape"


def test_slider_ids_match_canonical_order() -> None:
    """Every ID in SLIDER_INPUTS appears in the layout exactly once."""
    rendered_ids = {c.id for c in _walk(app.layout) if isinstance(c, dcc.Slider)}
    assert rendered_ids == set(SLIDER_INPUTS), (
        f"slider IDs in layout {sorted(rendered_ids)} != "
        f"SLIDER_INPUTS {sorted(SLIDER_INPUTS)}"
    )


def test_non_slider_ids_present() -> None:
    """All NON_SLIDER_INPUTS components (dropdown + radios + checklist) render."""
    rendered_ids = {
        c.id
        for c in _walk(app.layout)
        if isinstance(c, (dcc.Dropdown, dcc.RadioItems, dcc.Checklist))
    }
    assert rendered_ids == set(NON_SLIDER_INPUTS), (
        f"non-slider IDs {sorted(rendered_ids)} != "
        f"NON_SLIDER_INPUTS {sorted(NON_SLIDER_INPUTS)}"
    )


def test_slider_inputs_constant_length() -> None:
    """SLIDER_INPUTS has exactly 19 entries — pinned by PLAN.md §6."""
    assert len(SLIDER_INPUTS) == 19


def test_non_slider_inputs_constant_length() -> None:
    """NON_SLIDER_INPUTS has 4 entries: 1 dropdown + 2 radios + 1 checklist."""
    assert len(NON_SLIDER_INPUTS) == 4

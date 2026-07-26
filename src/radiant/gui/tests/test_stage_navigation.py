"""Integration tests for stage-strip navigation + live health dots (GUI plan Phase 4).

These drive the real main window on the shipped example config, offscreen: clicking
each of the nine stage chips scrolls the parameter panel to that stage's namespace and
swaps the center to that stage's contextual composite (arch doc §4.4). They also assert
the health-dot life cycle:
stale (pre-evaluate) → yellow (a warning run — the example's NIIRS extrapolation) →
green (a clean run) → red (a failed evaluation), and edit → back to stale.

The per-stage *composite content* (which plots/tables each stage shows) is covered in
``test_stage_center.py``; here the focus is the navigation contract — the left tree and
the selected-stage state track every chip click.
"""

from __future__ import annotations

from pathlib import Path

from radiant.api.sensor import Sensor
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.widgets import actionable_error_dialog as aed
from radiant.gui.widgets.stage_strip import STAGE_NAMESPACES

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_APERTURE = "optics.aperture_diameter_m"
_FULL_WELL = "readout.full_well_capacity_e"
_WAIT_MS = 15000


def _load_window(qtbot):  # type: ignore[no-untyped-def]
    """Build a window on the example config and wait for its auto-evaluation."""
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


class TestStageNavigation:
    def test_click_each_chip_navigates_panel_and_center(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Clicking every chip scrolls the panel to its namespace and swaps the center."""
        window = _load_window(qtbot)
        center = window.central_canvas.stage_center
        panel = window.parameter_panel

        for namespace in STAGE_NAMESPACES:
            # Fire the strip's click signal (what a real chip click emits).
            window.stage_strip.stageClicked.emit(namespace)

            # (a) selected chip tracks the click.
            assert window.stage_strip.selected_namespace == namespace

            # (b) parameter panel scrolled to and selected the namespace group.
            current = panel.tree.currentItem()
            assert current is not None
            assert current.text(0) == namespace
            assert current.isExpanded()

            # (c) the center swapped to the stage's contextual composite.
            assert center.selected_stage == namespace
            assert center.active_pane() is center.pane(namespace)

    def test_geometry_readout_shows_angles_with_units(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Geometry composite renders derived stage-output angles/ranges with units."""
        window = _load_window(qtbot)
        window.stage_strip.stageClicked.emit("geometry")

        readout = window.central_canvas.stage_center.pane("geometry").geometry_readout
        assert readout is not None
        keys = readout.rendered_keys()
        # A representative angle and a representative range are present, with units.
        assert "theta_s_rad" in keys
        assert readout.value_text("theta_s_rad").endswith("rad")
        assert "slant_range_m" in keys
        assert readout.value_text("slant_range_m").endswith("m")
        # A structured stage output (los_geometry) is not part of the angle summary.
        assert "los_geometry" not in keys

    def test_spectral_stage_renders_a_real_figure(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A spectral-domain stage renders its Gap-86 accessor figure in the composite."""
        window = _load_window(qtbot)
        window.stage_strip.stageClicked.emit("source")
        pane = window.central_canvas.stage_center.pane("source")
        assert pane.plot_canvases
        assert all(c.has_figure() for c in pane.plot_canvases)


class TestHealthDotTransitions:
    def test_pre_evaluate_all_stale(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A window with no sensor never evaluates: every stage dot is stale."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)
        for chip in window.stage_strip.chips:
            assert chip.status == "stale"

    def test_warning_run_marks_all_yellow(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """An actionable chain warning turns every dot yellow.

        Per the documented v1 decision (arch doc §4.2) warnings are not attributed
        per-stage, so any warning marks the whole run yellow. A valid scenario now
        evaluates warning-free (CU-166), so this drives a genuine full-well-clip
        warning to exercise the yellow branch (CU-167).
        """
        window = _load_window(qtbot)
        window.sensor.set(_FULL_WELL, 100000.0)  # forces a hard full-well clip
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_FULL_WELL)
        assert window.right_rail.messages.warning_count >= 1
        for chip in window.stage_strip.chips:
            assert chip.status == "warn"

    def test_clean_run_marks_all_green(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A warning-free result turns every dot green.

        The shipped examples always emit the NIIRS extrapolation warning, so a genuinely
        clean run is simulated by delivering the same real result with an empty warning
        list to the ok-handler — exercising the exact green branch a warning-free chain
        would take.
        """
        window = _load_window(qtbot)
        assert window.last_result is not None
        window._on_result_ok(window.last_result, [])
        for chip in window.stage_strip.chips:
            assert chip.status == "ok"

    def test_edit_flips_dots_back_to_stale(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A parameter edit grays the dots (results are now out of date)."""
        window = _load_window(qtbot)
        # Green them first so the transition to stale is unambiguous.
        window._on_result_ok(window.last_result, [])
        assert all(c.status == "ok" for c in window.stage_strip.chips)

        # An edit fires parameterEdited; the handler grays the dots immediately (before
        # the debounced re-run lands).
        window.parameter_panel.parameterEdited.emit(_APERTURE)
        for chip in window.stage_strip.chips:
            assert chip.status == "stale"
        # Let the coalesced re-evaluation drain so no worker outlives the test.
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            pass

    def test_failed_run_marks_all_red(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """A failed evaluation turns every dot red (documented whole-run attribution)."""
        window = _load_window(qtbot)
        monkeypatch.setattr(aed.ActionableErrorDialog, "exec", lambda self: 0)

        # Aperture 0 passes set() but the resolver rejects it at evaluate() time.
        window.sensor.set(_APERTURE, 0.0)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_APERTURE)

        for chip in window.stage_strip.chips:
            assert chip.status == "err"

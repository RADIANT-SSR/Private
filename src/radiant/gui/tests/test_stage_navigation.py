"""Integration tests for stage-strip navigation + live health dots (GUI plan Phase 4).

These drive the real main window on the shipped example config, offscreen: clicking
each of the nine stage chips scrolls the parameter panel to that stage's namespace and
swaps the central canvas to the stage's default visualization (a matplotlib figure, the
geometry angle readout, or a gap panel). They also assert the health-dot life cycle:
stale (pre-evaluate) → yellow (a warning run — the example's NIIRS extrapolation) →
green (a clean run) → red (a failed evaluation), and edit → back to stale.
"""

from __future__ import annotations

from pathlib import Path

from radiant.api.sensor import Sensor
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.widgets import actionable_error_dialog as aed
from radiant.gui.widgets.stage_strip import STAGE_NAMESPACES

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_APERTURE = "optics.aperture_diameter_m"
_WAIT_MS = 15000

# Which plot-area pane each stage's default visualization lands on (arch doc §4.4):
# geometry → the angle readout; the spectral-domain stages → the Gap-86 panel; the rest
# → a real ``result.plot.*`` figure on the matplotlib canvas.
_GEOMETRY_STAGES = ("geometry",)
_GAP_STAGES = ("source", "atmosphere", "spectral_integration")
_PLOT_STAGES = ("optics", "platform", "detector", "readout", "performance")


def _load_window(qtbot):  # type: ignore[no-untyped-def]
    """Build a window on the example config and wait for its auto-evaluation."""
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


class TestStageNavigation:
    def test_click_each_chip_navigates_panel_and_canvas(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Clicking every chip scrolls the panel to its namespace and swaps the canvas."""
        window = _load_window(qtbot)
        canvas = window.central_canvas
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

            # (c) canvas swapped to the stage's default visualization pane.
            assert canvas.selected_stage == namespace
            if namespace in _GEOMETRY_STAGES:
                assert canvas.active_pane is canvas.geometry_readout
            elif namespace in _GAP_STAGES:
                assert canvas.active_pane is canvas.gap_panel
            else:
                assert namespace in _PLOT_STAGES
                assert canvas.active_pane is canvas.matplotlib_canvas
                assert canvas.matplotlib_canvas.has_figure()

    def test_geometry_readout_shows_angles_with_units(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The Geometry pane renders derived stage-output angles/ranges with units."""
        window = _load_window(qtbot)
        canvas = window.central_canvas
        window.stage_strip.stageClicked.emit("geometry")

        readout = canvas.geometry_readout
        keys = readout.rendered_keys()
        # A representative angle and a representative range are present, with units.
        assert "theta_s_rad" in keys
        assert readout.value_text("theta_s_rad").endswith("rad")
        assert "slant_range_m" in keys
        assert readout.value_text("slant_range_m").endswith("m")
        # A structured stage output (los_geometry) is not part of the angle summary.
        assert "los_geometry" not in keys

    def test_gap_panel_names_gap_86(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A spectral-domain stage shows the Gap-86 panel, not a faked figure."""
        window = _load_window(qtbot)
        canvas = window.central_canvas
        window.stage_strip.stageClicked.emit("source")
        assert canvas.active_pane is canvas.gap_panel
        assert canvas.gap_panel.gap_number == 86
        assert "Gap 86" in canvas.gap_panel.detail_text()


class TestHealthDotTransitions:
    def test_pre_evaluate_all_stale(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A window with no sensor never evaluates: every stage dot is stale."""
        window = RADIANTMainWindow()
        qtbot.addWidget(window)
        for chip in window.stage_strip.chips:
            assert chip.status == "stale"

    def test_warning_run_marks_all_yellow(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The example config's NIIRS extrapolation warning turns every dot yellow.

        Per the documented v1 decision (arch doc §4.2) warnings are not attributed
        per-stage, so any warning marks the whole run yellow.
        """
        window = _load_window(qtbot)
        assert window.central_canvas.warning_strip.warning_count >= 1
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
        window._on_eval_ok(window.last_result, [])
        for chip in window.stage_strip.chips:
            assert chip.status == "ok"

    def test_edit_flips_dots_back_to_stale(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A parameter edit grays the dots (results are now out of date)."""
        window = _load_window(qtbot)
        # Green them first so the transition to stale is unambiguous.
        window._on_eval_ok(window.last_result, [])
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

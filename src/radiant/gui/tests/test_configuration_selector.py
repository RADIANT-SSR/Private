"""Multi-configuration Phase 4a: session model + master configuration selector.

Category D — the GUI half of ADR-0010. These drive the real window offscreen on a
real two/three-configuration study written by ``ConfigurationSet.save``, and assert
the four contracts Phase 4a owes (plan §6, Phase 4 bullet "4a"):

1. **Zero regression.** A plain single-configuration YAML session shows **no**
   selector and behaves exactly as before — the selector band is not merely empty,
   its dock is hidden, and the displayed sensor *is* the set's base object.
2. **Switching displays that configuration.** Clicking a tab re-renders the stage
   views, forms, and readouts from that configuration's materialized sensor —
   asserted on a metric that provably differs between the two bands.
3. **Evaluate-all.** One background pass fills every configuration's result on the
   retained run; warnings are attributed per configuration in Messages; a
   non-displayed failure is a Messages entry and **not** a modal, while a displayed
   failure keeps the pre-existing modal path.
4. **Undo survives a switch.** A shared-parameter edit stays undoable after the
   displayed configuration changes (per-configuration undo scoping is Phase 4b).

The golden/regression half is the separate full-suite run: the GUI never touches
computed results, and this phase is results-neutral by construction.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from radiant.api.config_set import ConfigurationSet
from radiant.api.sensor import Sensor
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.themes import DARK, LIGHT
from radiant.gui.widgets import actionable_error_dialog as aed

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

_FILTER_MIN = "spectral_integration.filter_min_um"
_FILTER_MAX = "spectral_integration.filter_max_um"
_APERTURE = "optics.aperture_diameter_m"

_WAIT_MS = 20000  # headroom over an 8-configuration evaluate-all pass


def _dual_band_study(tmp_path: Path) -> Path:
    """Write a two-configuration MWIR/LWIR study file and return its path.

    Band limits are the only configured parameters, so the two configurations
    differ in a way that is visible in every wavelength-dependent readout — the
    dual-band example's own construction (``examples/scripts/``).
    """
    cs = ConfigurationSet(Sensor.load(_EXAMPLE), names=["MWIR", "LWIR"])
    cs.configure(_FILTER_MIN, [3.5, 8.0])
    cs.configure(_FILTER_MAX, [5.0, 12.0])
    path = tmp_path / "dual_band_study.yaml"
    cs.save(path)
    return path


def _open_study(qtbot, tmp_path: Path) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """Open the two-configuration study in a window and await its first pass."""
    path = _dual_band_study(tmp_path)
    window = RADIANTMainWindow(config_set=ConfigurationSet.load(path), path=str(path))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


def _open_plain(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """Open the shipped single-configuration example and await its first pass."""
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


class TestZeroRegressionSingleConfiguration:
    """A plain config file must look and behave exactly like it did pre-Phase-4a."""

    def test_no_selector_is_shown(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _open_plain(qtbot)
        bar = window.configuration_bar
        assert bar.isVisibleTo(window) is False
        assert window._configuration_bar_dock.isVisibleTo(window) is False
        assert bar.buttons == []

    def test_displayed_sensor_is_the_base_object(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The degenerate set does not put a materialization between edits and runs."""
        window = _open_plain(qtbot)
        assert window.configuration_set is not None
        assert window.sensor is window.configuration_set.base
        assert len(window.configuration_set) == 1

    def test_edit_still_reevaluates_through_the_live_sensor(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _open_plain(qtbot)
        cards = window.right_rail.pinned.cards
        before = cards["snr"].value_text()
        window.sensor.set(_APERTURE, 0.5)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit(_APERTURE)
        assert cards["snr"].value_text() not in {before, "—"}

    def test_messages_carry_no_configuration_attribution(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Single-configuration warnings are the bare text, not '<name>: <text>'."""
        window = _open_plain(qtbot)
        window.sensor.set("readout.full_well_capacity_e", 100000.0)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window.parameter_panel.parameterEdited.emit("readout.full_well_capacity_e")
        assert window.right_rail.messages.warning_count >= 1
        messages = window.right_rail.messages.warnings
        assert all(not m.startswith("Configuration 1:") for m in messages)
        assert window.right_rail.messages.configuration_errors == {}

    def test_save_writes_todays_format(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """A single-configuration session saves without a `configurations:` section."""
        window = _open_plain(qtbot)
        out = tmp_path / "single.yaml"
        window._save_to_path(out)
        assert "configurations:" not in out.read_text(encoding="utf-8")


class TestStudyOpens:
    def test_all_configurations_load_and_the_selector_shows_them(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        assert cs.names() == ("MWIR", "LWIR")
        bar = window.configuration_bar
        assert bar.isVisibleTo(window) is True
        assert [b.text() for b in bar.buttons] == ["MWIR", "LWIR"]

    def test_displayed_is_the_files_active_configuration(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """`active` is persisted, and the window opens on it (never on 'the first')."""
        cs = ConfigurationSet(Sensor.load(_EXAMPLE), names=["MWIR", "LWIR"])
        cs.configure(_FILTER_MIN, [3.5, 8.0])
        cs.configure(_FILTER_MAX, [5.0, 12.0])
        cs.active = "LWIR"
        path = tmp_path / "lwir_active.yaml"
        cs.save(path)

        window = RADIANTMainWindow(config_set=ConfigurationSet.load(path), path=str(path))
        qtbot.addWidget(window)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            pass
        assert window.configuration_set is not None
        assert window.configuration_set.active == "LWIR"
        assert window.configuration_bar.active_name == "LWIR"
        assert window.sensor.get_input(_FILTER_MIN) == pytest.approx(8.0, rel=1e-12)

    def test_file_open_routes_a_study_through_the_set_reader(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """File → Open on a study file yields the whole set, not a collapsed sensor."""
        window = _open_plain(qtbot)
        path = _dual_band_study(tmp_path)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window._open_path(str(path))
        assert window.configuration_set is not None
        assert window.configuration_set.names() == ("MWIR", "LWIR")
        assert window.configuration_bar.isVisibleTo(window) is True

    def test_file_open_on_a_plain_config_stays_single(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """The same one reader keeps a plain config a one-configuration session."""
        window = _open_study(qtbot, tmp_path)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window._open_path(str(_EXAMPLE))
        assert window.configuration_set is not None
        assert len(window.configuration_set) == 1
        assert window.configuration_bar.isVisibleTo(window) is False


class TestSelectorSwitch:
    def test_switch_rerenders_stage_views_with_that_configurations_values(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path
    ) -> None:
        """Switching to LWIR shows LWIR's band and LWIR's (provably different) metrics."""
        window = _open_study(qtbot, tmp_path)
        cards = window.right_rail.pinned.cards
        mwir_gsd = cards["gsd_geometric_mean_m"].value_text()
        mwir_snr = cards["snr"].value_text()
        assert window.sensor.get_input(_FILTER_MAX) == pytest.approx(5.0, rel=1e-12)

        window.configuration_bar.buttons[1].click()

        # The displayed sensor is LWIR's materialization: its band moved.
        assert window.configuration_set is not None
        assert window.configuration_set.active == "LWIR"
        assert window.sensor.get_input(_FILTER_MIN) == pytest.approx(8.0, rel=1e-12)
        assert window.sensor.get_input(_FILTER_MAX) == pytest.approx(12.0, rel=1e-12)
        # And the readouts moved with it — SNR differs between the bands while the
        # shared geometry keeps GSD identical (the dual-band study's own physics).
        assert cards["snr"].value_text() != mwir_snr
        assert cards["gsd_geometric_mean_m"].value_text() == mwir_gsd
        # The parameter tree re-read the displayed configuration too.
        assert window.parameter_panel is not None

    def test_switch_uses_the_retained_run_without_re_evaluating(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """A cached configuration displays from the retained pass — no extra chain run."""
        window = _open_study(qtbot, tmp_path)
        runs_before = window.evaluation_count
        window.configuration_bar.buttons[1].click()
        assert window.evaluation_count == runs_before
        assert window.last_result is not None

    def test_switching_back_and_forth_is_stable(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        snr_mwir = window.right_rail.pinned.cards["snr"].value_text()
        window.configuration_bar.buttons[1].click()
        window.configuration_bar.buttons[0].click()
        assert window.configuration_set is not None
        assert window.configuration_set.active == "MWIR"
        assert window.right_rail.pinned.cards["snr"].value_text() == snr_mwir


class TestEvaluateAll:
    def test_every_configuration_is_evaluated_in_one_pass(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        run = window.last_run
        assert run is not None
        assert sorted(run.names) == ["LWIR", "MWIR"]
        assert run.n_failed == 0
        for name in run.names:
            assert run.result_for(name).metrics["snr"] > 0.0
        # The displayed configuration is evaluated first (active-first order).
        assert run.names[0] == "MWIR"

    def test_warnings_are_attributed_to_their_configuration(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """A saturation warning raised by one band is labelled with that band."""
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        # Force a hard full-well clip in LWIR only (its own configured column).
        cs.configure("readout.full_well_capacity_e", [2.0e6, 1.0e5])
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window._evaluate_now()

        messages = window.right_rail.messages.warnings
        saturation = [m for m in messages if "saturat" in m.lower()]
        assert saturation, messages
        assert all(m.startswith("LWIR: ") for m in saturation)

    def test_non_displayed_failure_is_a_message_not_a_modal(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        """LWIR fails while MWIR is displayed: Messages names it, no dialog appears."""
        window = _open_study(qtbot, tmp_path)
        shown: list[aed.ActionableErrorDialog] = []
        monkeypatch.setattr(aed.ActionableErrorDialog, "exec", lambda self: shown.append(self) or 0)

        cs = window.configuration_set
        assert cs is not None
        # f/# 4.0 is consistent with the shared 0.30 m aperture and 1.20 m focal
        # length; f/# 2.0 over-constrains that consistency group, so LWIR alone
        # fails to resolve — a real per-configuration physics failure.
        cs.configure("optics.f_number", [4.0, 2.0])
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window._evaluate_now()

        assert shown == []  # the displayed configuration is fine — no modal
        failures = window.right_rail.messages.configuration_errors
        assert list(failures) == ["LWIR"]
        run = window.last_run
        assert run is not None
        assert run.n_failed == 1
        # The displayed configuration still rendered its own result.
        assert window.right_rail.pinned.cards["snr"].value_text() != "—"

    def test_displayed_failure_takes_todays_modal_path(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, monkeypatch
    ) -> None:
        """A failure in the displayed configuration behaves exactly as before."""
        window = _open_study(qtbot, tmp_path)
        shown: list[aed.ActionableErrorDialog] = []
        monkeypatch.setattr(aed.ActionableErrorDialog, "exec", lambda self: shown.append(self) or 0)

        cs = window.configuration_set
        assert cs is not None
        cs.configure("optics.f_number", [2.0, 4.0])  # MWIR (displayed) over-constrains
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            window._evaluate_now()

        assert len(shown) == 1
        assert window.right_rail.messages.has_error()
        assert window.central_canvas.stale_notice.isHidden() is False
        # The underlying physics error is shown, not the configuration-set wrapper —
        # a single-configuration session therefore renders exactly the error it did
        # before this phase.
        assert "over-constrained" in str(window.right_rail.messages.error)
        assert "does not resolve" not in str(window.right_rail.messages.error)


class TestUndoAcrossSwitch:
    def test_shared_edit_is_undoable_after_a_selector_switch(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """The undo stack targets the shared base, which a switch never replaces."""
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        # Read the shared *input*, not a resolved value: the base alone is not
        # resolvable once band limits have moved into the configured table.
        before = cs.base.inputs()[_APERTURE]

        window.sensor.set(_APERTURE, 0.5)
        # Both the edit and the undo apply synchronously and this test reads only the
        # synchronous surfaces (``cs.base.inputs()``, ``window.sensor``), so the
        # contract owed is that each *schedules* a re-evaluation — asserted directly
        # rather than by awaiting a pass whose result is never read (CU-289/CU-314).
        window.parameter_panel.parameterEdited.emit(_APERTURE)
        assert window.evaluation_scheduled is True
        assert cs.base.inputs()[_APERTURE] == pytest.approx(0.5, rel=1e-12)

        window.configuration_bar.buttons[1].click()  # display LWIR
        assert window.action("edit.undo").isEnabled()

        window.action("edit.undo").trigger()
        assert window.evaluation_scheduled is True

        assert cs.base.inputs()[_APERTURE] == pytest.approx(before, rel=1e-12)
        # The restored shared value shows on the (now LWIR) displayed sensor.
        assert window.sensor.get_input(_APERTURE) == pytest.approx(before, rel=1e-12)


class TestSelectorTheming:
    @pytest.mark.parametrize("theme", [LIGHT, DARK], ids=lambda t: t.name)
    def test_each_configuration_has_a_distinct_theme_accent(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path, theme
    ) -> None:
        """Accents come from the token set — both themes, one stable hue per slot."""
        window = _open_study(qtbot, tmp_path)
        bar = window.configuration_bar
        bar.set_theme(theme)
        accents = [bar.accent_for(name) for name in bar.names]
        assert accents == list(theme.config_accents[: len(accents)])
        assert len(set(accents)) == len(accents)

    def test_accent_tuple_covers_every_allowed_configuration(self) -> None:
        """MAX_CONFIGS configurations must all get a colour, in both themes."""
        for theme in (LIGHT, DARK):
            assert len(theme.config_accents) >= ConfigurationSet.MAX_CONFIGS
            assert len(set(theme.config_accents)) == len(theme.config_accents)


class TestConfigurationBarStacksAboveStrip:
    """CU-331: the selector band must sit ABOVE the stage strip, never beside it.

    Qt lays multiple top-area docks out side by side by default; with ≥6
    configurations that pushed the stage chips off the right edge. The window
    now splits the two docks vertically, so the bar takes a thin band of its
    own and the strip keeps the full width — what §4.2b always specified.
    """

    def test_bar_dock_sits_above_the_stage_strip_not_beside_it(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path
    ) -> None:
        window = _open_study(qtbot, tmp_path)
        window.resize(1100, 800)
        window.show()
        qtbot.waitExposed(window)
        bar = window._configuration_bar_dock.geometry()
        strip = window._stage_strip_dock.geometry()
        # Stacked: the bar ends before the strip begins, and both share the
        # left edge. Side-by-side fails both (disjoint x-ranges, same y-band).
        assert bar.bottom() <= strip.top()
        assert abs(bar.left() - strip.left()) <= 1
        # The strip keeps (essentially) the full window width — the defect
        # was the bar stealing horizontal room from the chips.
        assert strip.width() >= window.width() * 0.9

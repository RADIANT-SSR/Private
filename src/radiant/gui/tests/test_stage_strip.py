"""Widget-level tests for the clickable stage strip + the per-stage view mapping.

Covers GUI plan Phase 4 task 1's strip half at the widget level: a chip click emits
the stage's real schema namespace (not the shortened eyebrow — CU-106), the selected
state tracks one chip, the health status drives both the dot and the chip tint, and the
CU-106 guard (every chip namespace is a real chain stage) holds. The per-stage
default-visualization mapping (:mod:`radiant.gui.stage_views`) is asserted here too,
since it is pure and Qt-free.
"""

from __future__ import annotations

from PySide6.QtCore import Qt

from radiant.gui import stage_views
from radiant.gui.param_format import chain_namespace_order
from radiant.gui.widgets.health_dot import VALID_STATUSES
from radiant.gui.widgets.stage_strip import (
    STAGE_NAMESPACES,
    STAGE_TITLES,
    StageStrip,
)


class TestStageStripNamespaces:
    def test_namespaces_are_real_chain_stages(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Every chip namespace is a real chain stage — the CU-106 fix, guarded."""
        strip = StageStrip()
        qtbot.addWidget(strip)
        chain = chain_namespace_order()
        assert chain == STAGE_NAMESPACES  # exact order + names (geometry-first)
        for chip in strip.chips:
            assert chip.namespace in chain

    def test_spectral_namespace_is_spectral_integration(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """CU-106 regression: the 6th chip navigates to ``spectral_integration``.

        Its eyebrow display abbreviates to ``spectral`` but the navigable namespace is
        the real schema name — the one-token mismatch CU-106 flagged is gone.
        """
        strip = StageStrip()
        qtbot.addWidget(strip)
        spectral_chip = strip.chips[5]
        assert spectral_chip.stage_title == "Spectral Int."
        assert spectral_chip.namespace == "spectral_integration"
        assert strip.chip("spectral_integration") is spectral_chip

    def test_titles_unchanged(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The nine display titles are still geometry-first, in chain order."""
        strip = StageStrip()
        qtbot.addWidget(strip)
        assert [c.stage_title for c in strip.chips] == list(STAGE_TITLES)


class TestStageStripClick:
    def test_click_emits_namespace(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A left-click on a chip emits that chip's namespace (navigation only)."""
        strip = StageStrip()
        qtbot.addWidget(strip)
        strip.show()
        optics = strip.chip("optics")
        with qtbot.waitSignal(strip.stageClicked, timeout=2000) as blocker:
            qtbot.mouseClick(optics, Qt.MouseButton.LeftButton)
        assert blocker.args == ["optics"]

    def test_select_marks_one_chip(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """``select`` marks exactly the named chip selected and clears the others."""
        strip = StageStrip()
        qtbot.addWidget(strip)
        strip.select("detector")
        assert strip.selected_namespace == "detector"
        for chip in strip.chips:
            assert chip.selected == (chip.namespace == "detector")
            assert chip.property("selected") == ("true" if chip.selected else "false")
        # Selecting another chip moves the selection.
        strip.select("geometry")
        assert strip.chip("geometry").selected
        assert not strip.chip("detector").selected


class TestStageStripHealth:
    def test_set_all_status_drives_dots_and_chips(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """``set_all_status`` updates every dot and chip status (the whole-run states)."""
        strip = StageStrip()
        qtbot.addWidget(strip)
        for status in VALID_STATUSES:
            strip.set_all_status(status)
            for chip in strip.chips:
                assert chip.status == status
                assert chip.dot.status == status
                assert chip.property("status") == status

    def test_set_status_targets_one_stage(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """``set_status`` updates just the named stage."""
        strip = StageStrip()
        qtbot.addWidget(strip)
        strip.set_all_status("ok")
        strip.set_status("performance", "warn")
        assert strip.chip("performance").status == "warn"
        assert strip.chip("geometry").status == "ok"


class TestStageCompositionMapping:
    """The contextual per-stage composition spec (arch doc §4.4.1). Content assertions
    live in ``test_stage_center.py``; here the mapping-integrity contract is checked."""

    def test_every_chain_namespace_has_a_composition(self) -> None:
        """Every real chain stage resolves to a StageComposition (no unmapped stage)."""
        for namespace in chain_namespace_order():
            assert namespace in stage_views.STAGE_COMPOSITIONS

    def test_geometry_is_the_readout_composition(self) -> None:
        """Geometry's composite tabs the angle-summary readout + the schematic (Phase 7).

        The readout and input forms live on the "Inputs" sub-view; the 2D geometry
        schematic viewer on the "Schematic" sub-view (ADR-0007, superseded 2026-07-14).
        Neither tab carries a ``result.plot`` figure.
        """
        comp = stage_views.composition_for("geometry")
        assert comp is not None
        assert [sv.title for sv in comp.subviews] == ["Inputs", "Schematic"]
        inputs, viewer = comp.subviews
        assert inputs.geometry_readout and inputs.geometry_form
        assert viewer.geometry_viewer
        assert comp.plots == ()

    def test_spectral_domain_stages_carry_spectral_accessors(self) -> None:
        """Source/Atmosphere/Spectral-Integration plot their spectral figures (Gap 86).

        Source's spectral figure is the **source-side** emission, not an at-aperture
        radiance: owner walkthrough items 5 and 6 moved that post-atmosphere view to
        the Atmosphere stage, which owns the step and draws it per arm through
        ``spectral_at_aperture_arms`` (asserted in ``test_atmosphere_instrument.py``).
        """
        expected = {
            "source": "spectral_source_emission",
            "atmosphere": "spectral_atmosphere",
            # CU-242 (owner-directed): the Spectral-Integration screen shows only
            # what it computes. Its spectral figure is the at-image irradiance —
            # this stage's own product — not the in-band radiance that fed it.
            "spectral_integration": "spectral_irradiance_at_image",
        }
        for namespace, method in expected.items():
            comp = stage_views.composition_for(namespace)
            assert comp is not None
            # A tabbed stage (Source post-GT-0) carries its plots on the subviews.
            methods = {spec.method for spec in comp.plots}
            methods |= {spec.method for sub in comp.subviews for spec in sub.plots}
            assert method in methods

    def test_default_stage_is_performance(self) -> None:
        """No stage selected → the center lands on Performance (metrics + system MTF)."""
        assert stage_views.DEFAULT_STAGE == "performance"
        assert stage_views.composition_for(stage_views.DEFAULT_STAGE) is not None

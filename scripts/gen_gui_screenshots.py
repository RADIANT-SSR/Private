"""Generate the manual's GUI figures by driving the real GUI offscreen.

Single-source rule (Support_Documentation_Plan §5): every GUI figure in the manual
suite is *generated* from the shipped GUI on a committed input config, never
hand-captured. A stale screenshot is then a one-command fix rather than an
archaeology project::

    python scripts/gen_gui_screenshots.py --all

Ruling Q7 (owner-ratified 2026-09-16): **all** figures are captured under
``QT_QPA_PLATFORM=offscreen``. Offscreen rendering paints Fusion-style chrome rather
than native macOS/Windows decorations, which makes the figures platform-neutral —
the same bytes regardless of who regenerates them. There are no native "hero shots".

How it works
------------
For each :class:`Capture` in :data:`CAPTURES` the generator builds the *real*
:class:`~radiant.gui.main_window.RADIANTMainWindow` on the named config, waits for the
auto-evaluation that the window schedules on load (``QTimer.singleShot(0,
_evaluate_now)`` → worker thread → ``evaluationFinished``), selects the requested stage
workspace, applies any per-figure dock geometry, and writes ``QWidget.grab()`` to
``docs/guides/figures/gui/<name>.png``. Captures therefore show an **evaluated** window
— populated KPI cards and plots — not an empty shell.

Two spike lessons (plan §5) are first-class registry fields: the default parameter-dock
width elides long parameter names, so a capture can widen it (``param_dock_width``), and
detail figures are made by grabbing a single child widget rather than the whole window
(``target``). A third field, ``tab``, selects one of a stage's sub-view tabs by its visible
label (Geometry *Inputs | Schematic*, Optics *Inputs | Transmission | MTF | PSF + Pupil*,
Detector *Inputs | Noise | Detector + PSF*) — without it every tabbed stage would only ever
be photographed on its first tab. A fourth, ``set_parameters``, applies field edits to the
loaded document's shared base before the window is built (one ``Sensor.set`` each, the same
call the GUI makes), for the figures whose subject is a state an operator reaches by toggling
something rather than a state any committed config is in; the manifest records every such edit.

Input configs are read with :meth:`radiant.api.ConfigurationSet.load`, the same reader the
GUI's ``File → Open`` uses, so a capture may name either a plain config or a
``configurations:`` study; a study opens with the configuration selector and the
per-configuration metric columns visible, exactly as it does for an operator.

Usage::

    python scripts/gen_gui_screenshots.py --list             # capture names
    python scripts/gen_gui_screenshots.py optics_workspace   # one (or several)
    python scripts/gen_gui_screenshots.py --all              # everything
    python scripts/gen_gui_screenshots.py --all --out /tmp/x # smoke-test elsewhere

Requires the optional ``gui`` extra (``pip install -e ".[gui]"``). Every run also
rewrites ``MANIFEST.md`` next to the figures — the Rule 26(b) provenance record naming
this generator, each figure's input config and window size, and the current commit.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - import-time typing only
    from PySide6.QtWidgets import QWidget

# Headless Qt, pinned before anything can construct a QApplication (the GUI suite's
# conftest does the same). ``setdefault`` so a developer debugging a capture can run
# with a real display: ``QT_QPA_PLATFORM=cocoa python scripts/gen_gui_screenshots.py ...``
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# The scripting console defaults to an in-process Jupyter kernel (CU-138); every window
# this script builds would pay that startup. The REPL fallback is the same backend the
# GUI suite pins, and the console is not in any figure.
os.environ.setdefault("RADIANT_CONSOLE_FORCE_REPL", "1")

REPO = Path(__file__).resolve().parents[1]
FIGURES = REPO / "docs" / "guides" / "figures" / "gui"
MANIFEST_NAME = "MANIFEST.md"

#: Default capture geometry (plan §5: 1440×900, the size the spike proved).
DEFAULT_WIDTH = 1440
DEFAULT_HEIGHT = 900

#: A capture name must be a safe, lowercase file stem — it *is* the PNG filename.
NAME_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")

#: How long to wait for the window's auto-evaluation before failing (seconds). The
#: GUI suite allows 15 s per window; a cold first run pays import + atmosphere load.
EVALUATION_TIMEOUT_S = 120.0


class ScreenshotError(RuntimeError):
    """A capture could not be produced. Carries an actionable message (Rule 15 style).

    Deliberately *not* a :class:`radiant.core.exceptions.RadiantError`: this is build
    tooling outside the library's error taxonomy, and the script must be importable in
    a checkout with no installed package.
    """


@dataclass(frozen=True)
class Capture:
    """One named figure: what to load, what to show, and how big to make it.

    Parameters
    ----------
    name:
        Capture name — also the PNG stem (``<name>.png``) and the CLI selector.
    config:
        Repo-relative path of the input config (an ``examples/`` YAML, a scenario
        baseline, or a GUI exercise baseline).
    stage:
        Stage namespace whose workspace to show (``"performance"``, ``"geometry"``, …),
        or ``None`` to capture the window as it opens.
    tab:
        Visible label of the stage sub-view tab to select before grabbing (e.g.
        ``"Schematic"``, ``"MTF"``, ``"Noise"``), spelled exactly as the stage spec
        declares it in :mod:`radiant.gui.stage_views` — write ``"Scene & regime"``, not
        the Qt-escaped ``"Scene && regime"``; :func:`_select_tab` applies ``StagePane``'s
        own mnemonic escaping when it matches. ``None`` leaves the stage on the tab it
        opens with — the first one. Only the tabbed stages (Geometry, Source, Optics,
        Platform, Detector) have sub-views; naming a tab on a single-pane stage is a
        capture error rather than a silent no-op.
    target:
        Dotted attribute path of a child widget to grab instead of the whole window
        (e.g. ``"parameter_panel"``, ``"central_canvas.stage_center"``). Panel-level
        grabs are how detail figures are made (plan §5 spike lesson).
    width, height:
        Window size in pixels before the grab.
    param_dock_width:
        Width in pixels to force on the left Parameters dock. The default proportions
        elide long parameter names (plan §5 spike lesson), so parameter-tree figures
        widen it.
    rail_dock_width:
        Width in pixels to force on the right rail dock.
    splitter_sizes:
        Pixel sizes to force on named splitters inside the window, keyed by Qt
        ``objectName`` (e.g. ``{"stagePanelSplit": (520, 380)}``). A figure that needs
        one pane of a stage workspace bigger sets this rather than the whole window.
    set_parameters:
        Dot-path → value edits applied to the loaded document's **shared base** before
        the window is built — one ``Sensor.set`` each, exactly the call the GUI makes
        when an operator edits that field. It exists for the figures whose subject is a
        *state the operator reaches by toggling something*, not a state any committed
        config is in: a deselected metric group, an activated calibration scheme. The
        input config is still a committed one and the manifest records the edits, so the
        figure stays reproducible by one command. Values are in the parameter's input
        unit (the schema's), since that is what ``Sensor.set`` takes without a ``unit=``.
    caption:
        One line describing what the figure shows — carried into the manifest.
    """

    name: str
    config: str
    stage: str | None = None
    tab: str | None = None
    target: str | None = None
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    param_dock_width: int | None = None
    rail_dock_width: int | None = None
    splitter_sizes: Mapping[str, tuple[int, ...]] = field(default_factory=dict)
    set_parameters: Mapping[str, Any] = field(default_factory=dict)
    caption: str = ""

    @property
    def filename(self) -> str:
        """The PNG filename this capture writes."""
        return f"{self.name}.png"

    @property
    def config_path(self) -> Path:
        """Absolute path of the input config."""
        return REPO / self.config


_MINIMAL = "examples/mwir_leo_minimal.yaml"

#: Landsat 9 TIRS band 10 — the flagship baseline Volume IV ch. 2 reads metric group by
#: metric group. A thermal band computes the whole metric surface (SNR *and* NEDT *and*
#: the spatial family), so no group's cards are empty in the figures.
_TIRS_B10 = "scenarios/09_flagship_missions/9.2_landsat_tirs_nedt/tirs_b10_nedt_300k.yaml"

#: Landsat 9 OLI-2 band 4 — a single-band config carrying a real coated optical train
#: (mirrors, refractive corrector, per-band interference filter), so the element rows in
#: the Optics → Transmission figure are the shipped provenance-cited ones.
_OLI2_B04 = "scenarios/09_flagship_missions/9.4_landsat_oli2_snr/oli2_b04_snr_ltyp.yaml"

#: The OLI-2 nine-band study — the one committed ``configurations:`` document. Opening it
#: is how Volume IV ch. 2 shows configuration comparison without inventing a config.
_OLI2_STUDY = "scenarios/09_flagship_missions/9.4_landsat_oli2_snr/oli2_all_bands_study.yaml"

#: A GeoSNAP-18 MWIR config built on an FPA part-library preset (Gap 119), used for the
#: preset walkthrough's figure.
_FPA_PRESET = (
    "scenarios/02_mike_detector_engineer/2.8_fpa_part_library/inputs/geosnap18_mwir_leo.yaml"
)

# -- Volume IV Part C, tier-1 GUI-led case studies (plan §7) --------------------------
# Each case study is illustrated from the scenario's own committed GUI baseline — the
# ``<id>.gui.yaml`` emitted from the scenario runner by ``scenarios/tools/emit_gui_yaml.py``
# and pinned by a ``<id>.gui.expected.json``. Using the scenario's own artifact (rather
# than a figure-only config) is what keeps a chapter's quoted numbers checkable against
# the scenario that produced them.

#: Scenario 1.1 — MWIR maritime surveillance, 30 cm aperture baseline (Sarah).
_CASE_MARITIME = (
    "scenarios/01_sarah_systems_engineer/1.1_mwir_maritime_surveillance/"
    "inputs/1.1_mwir_maritime_surveillance.gui.yaml"
)

#: Scenario 2.1 — InSb-vs-HgCdTe bench shootout, InSb branch (Mike).
_CASE_SHOOTOUT = (
    "scenarios/02_mike_detector_engineer/2.1_insb_vs_hgcdte_noise_budget/"
    "inputs/2.1_insb_vs_hgcdte_noise_budget.gui.yaml"
)

#: Scenario 3.1 — ISR pass planning, 30 deg off-nadir baseline (Raj).
_CASE_PASS_PLANNING = (
    "scenarios/03_raj_mission_planner/3.1_isr_pass_planning/inputs/3.1_isr_pass_planning.gui.yaml"
)

#: Scenario 10.2 — air-to-air level-arm MWIR IRST, 50 km nominal point.
_CASE_IRST = (
    "scenarios/10_direction_general/10.2_air_to_air_level_irst/"
    "inputs/10.2_air_to_air_level_irst.gui.yaml"
)

#: The capture registry. Phase 0 shipped the four workspaces the feasibility spike proved;
#: Phase 4 adds the Volume IV ch. 2 walkthrough figures. Definitions go here and only here.
CAPTURES: tuple[Capture, ...] = (
    Capture(
        name="performance_workspace",
        config=_MINIMAL,
        stage="performance",
        caption="Performance workspace on the minimal MWIR LEO example, after evaluation.",
    ),
    Capture(
        name="geometry_workspace",
        config=_MINIMAL,
        stage="geometry",
        caption="Geometry workspace as it opens — the Inputs tab, mode cards and ranges.",
    ),
    Capture(
        name="optics_workspace",
        config=_MINIMAL,
        stage="optics",
        caption="Optics workspace as it opens — the Inputs tab and the derived optics outputs.",
    ),
    Capture(
        name="detector_workspace",
        config=_MINIMAL,
        stage="detector",
        caption="Detector workspace — QE and noise-term breakdown.",
    ),
    # -- Volume IV ch. 2, walkthrough 1: build a sensor from scratch ------------------
    Capture(
        name="build_geometry_inputs",
        config=_MINIMAL,
        stage="geometry",
        tab="Inputs",
        param_dock_width=520,
        caption=(
            "Geometry workspace, Inputs tab, with the Parameters dock widened so the "
            "full dot-paths are readable."
        ),
    ),
    Capture(
        name="build_geometry_schematic",
        config=_MINIMAL,
        stage="geometry",
        tab="Schematic",
        caption="Geometry workspace, Schematic tab — the 2D viewing-triangle schematic.",
    ),
    Capture(
        name="build_optics_inputs",
        config=_MINIMAL,
        stage="optics",
        tab="Inputs",
        param_dock_width=520,
        caption="Optics workspace, Inputs tab — aperture, focal length, and derived outputs.",
    ),
    # -- Volume IV ch. 2, walkthrough 2: read a flagship baseline ---------------------
    Capture(
        name="flagship_performance",
        config=_TIRS_B10,
        stage="performance",
        caption=(
            "Performance workspace on the Landsat 9 TIRS band-10 baseline — every metric "
            "group card populated after evaluation."
        ),
    ),
    Capture(
        name="flagship_mtf_budget",
        config=_TIRS_B10,
        stage="optics",
        tab="MTF",
        caption="Optics workspace, MTF tab — system MTF curve and the per-term budget table.",
    ),
    Capture(
        name="flagship_noise_budget",
        config=_TIRS_B10,
        stage="detector",
        tab="Noise",
        caption="Detector workspace, Noise tab — the noise-budget table beside its chart.",
    ),
    # -- Volume IV ch. 2, walkthrough 3: pick an FPA preset ---------------------------
    Capture(
        name="fpa_preset_detector",
        config=_FPA_PRESET,
        stage="detector",
        tab="Inputs",
        # No param_dock_width: widening the dock narrows the central form past its
        # column-relayout threshold, where the painted field values go blank (CU-363).
        # At default width the fields paint, and the dock's `preset` badges — the
        # figure's subject — are visible anyway.
        caption=(
            "Detector workspace, Inputs tab, on a config built from the GeoSNAP-18 FPA "
            "preset — the preset-supplied fields carry the part's provenance."
        ),
    ),
    # -- Volume IV ch. 2, walkthrough 4: edit an element train ------------------------
    Capture(
        name="element_train_transmission",
        config=_OLI2_B04,
        stage="optics",
        tab="Transmission",
        param_dock_width=520,
        caption=(
            "Optics workspace, Transmission tab, on the Landsat 9 OLI-2 band-4 config — "
            "the element train and the transmission it produces."
        ),
    ),
    # -- Volume IV ch. 2, walkthrough 5: run a sweep ----------------------------------
    Capture(
        name="sweep_parameter_panel",
        config=_MINIMAL,
        stage="optics",
        tab="Inputs",
        target="parameter_panel",
        param_dock_width=560,
        caption=(
            "Parameters dock (panel-level grab) — the optics branch holding "
            "optics.aperture_diameter_m, the axis the sweep walkthrough varies."
        ),
    ),
    # -- Volume IV ch. 2, walkthrough 6: compare configurations -----------------------
    Capture(
        name="compare_configurations",
        config=_OLI2_STUDY,
        stage="performance",
        caption=(
            "Performance workspace on the nine-configuration OLI-2 study — one metric "
            "column per configuration, in set order, plain values only (ADR-0010 D-9)."
        ),
    ),
    # -- Volume II (User's Guide) captures --------------------------------------------
    # Chapters 1–6 teach the *interface* rather than a task, so these figures are
    # anatomy shots: the whole window, then the three permanent columns one at a time
    # as panel-level grabs, then the scene-defining workspaces. They deliberately use
    # configs and tabs no Volume IV capture already photographs, so no two figures in
    # this folder are the same picture under two names.
    Capture(
        name="ug_window_anatomy",
        config=_MINIMAL,
        stage="geometry",
        tab="Inputs",
        # Default dock proportions on purpose: this is the window an operator's first
        # launch actually shows, before anyone has dragged a splitter.
        caption=(
            "The main window at default proportions — configuration-free minimal MWIR "
            "example, Geometry workspace, after the load-time evaluation."
        ),
    ),
    Capture(
        name="ug_stage_strip",
        config=_MINIMAL,
        stage="performance",
        target="stage_strip",
        caption=(
            "The signal-chain strip (panel-level grab) — ten stage chips in chain order, "
            "each with its health dot; Performance is the selected chip."
        ),
    ),
    Capture(
        name="ug_parameter_dock",
        config=_MINIMAL,
        stage="geometry",
        target="parameter_panel",
        param_dock_width=560,
        caption=(
            "The Parameters dock (panel-level grab) — filter box above the "
            "Parameter / Value / Source tree, scrolled to the geometry namespace."
        ),
    ),
    Capture(
        name="ug_right_rail",
        config=_MINIMAL,
        stage="performance",
        target="right_rail",
        caption=(
            "The right rail (panel-level grab) — pinned metric cards, the Edit Config "
            "(YAML) button, the Messages panel, and the Evaluate footer."
        ),
    ),
    Capture(
        name="ug_configuration_bar",
        config=_OLI2_STUDY,
        stage="performance",
        target="configuration_bar",
        caption=(
            "The configuration selector (panel-level grab) on the nine-band OLI-2 study "
            "— one accent-chipped tab per configuration plus the manager gear."
        ),
    ),
    Capture(
        name="ug_geometry_inputs",
        config=_TIRS_B10,
        stage="geometry",
        tab="Inputs",
        # No param_dock_width: the subject is the centre pane (scene-class card + mode
        # cards), and a widened dock squeezes the mode cards until their value fields
        # are clipped at the right edge. The Parameters dock has its own detail figure.
        caption=(
            "Geometry workspace, Inputs tab, on the Landsat 9 TIRS band-10 baseline — "
            "scene-class card, one mode card per geometry family, derived-angle readout."
        ),
    ),
    Capture(
        name="ug_geometry_schematic",
        config=_TIRS_B10,
        stage="geometry",
        tab="Schematic",
        # Give the tab's side panel enough width that its mode-card values are not
        # clipped mid-number; the canvas keeps the larger share.
        splitter_sizes={"geometryViewerSplit": (400, 360)},
        caption=(
            "Geometry workspace, Schematic tab, on the TIRS band-10 baseline — a 705 km "
            "space-to-ground view drawn not to scale, altitudes carried by leader labels."
        ),
    ),
    Capture(
        name="ug_source_scene_regime",
        config=_MINIMAL,
        stage="source",
        tab="Scene & regime",
        caption=(
            "Source workspace, Scene & regime tab — the declared scene type, the regime "
            "override, and the tentative classification the source stage publishes."
        ),
    ),
    Capture(
        name="ug_source_thermal",
        config=_MINIMAL,
        stage="source",
        tab="Target — thermal",
        caption=(
            "Source workspace, Target — thermal tab — target and background temperature "
            "and emissivity beside the pre-atmosphere emitted-radiance spectra."
        ),
    ),
    Capture(
        name="ug_source_reflective",
        # The bundled VNIR mission template: a scalar-reflectance sunlit scene with no
        # file-valued parameters, so the figure carries no machine-specific absolute
        # path (the parameter tree shows a path parameter *resolved*, which is how the
        # OLI-2 configs — whose coating and radiance CSVs are relative on disk — would
        # have leaked one into the manual).
        config="src/radiant/data/templates/aerial_vnir_imaging.yaml",
        stage="source",
        tab="Target — reflective",
        caption=(
            "Source workspace, Target — reflective tab, on the bundled aerial VNIR "
            "template — target reflectance beside the reflected radiance it produces."
        ),
    ),
    Capture(
        name="ug_atmosphere_workspace",
        config=_MINIMAL,
        stage="atmosphere",
        # The atmosphere workspace stacks two spectra under the model card, which is
        # taller than the default window: as a full-window shot the Background-path
        # plot was cut mid-axes and the figure read as broken (CU-370 II-022). The
        # chapter's prose discusses only this pane — the model selector and the two
        # spectra — so it becomes a panel grab, big enough to hold the whole stack
        # and legible in print rather than set at 4 pt (X-07).
        target="central_canvas.stage_center",
        width=1720,
        height=1300,
        caption=(
            "Atmosphere workspace — the model selector with only the active backend's "
            "knobs shown, above the transmittance and path-radiance spectra."
        ),
    ),
    # -- Volume II batch 2 captures ----------------------------------------------------
    # Chapters 7–12 cover the sensor side, studies, the evaluate loop, sweeps, the YAML
    # round-trip and troubleshooting. As in batch 1 these are anatomy shots rather than
    # task screenshots, and each deliberately uses a config/tab combination no earlier
    # capture photographs, so the folder holds no picture twice under two names.
    Capture(
        name="ug_optics_inputs",
        config=_TIRS_B10,
        stage="optics",
        tab="Inputs",
        param_dock_width=520,
        caption=(
            "Optics workspace, Inputs tab, on the Landsat 9 TIRS band-10 baseline — "
            "aperture and wavefront-error fields above the stage's derived outputs, "
            "including the final regime classification."
        ),
    ),
    Capture(
        name="ug_optics_transmission_scalar",
        config=_MINIMAL,
        stage="optics",
        tab="Transmission",
        param_dock_width=440,
        caption=(
            "Optics workspace, Transmission tab, in Scalar throughput mode — the mode "
            "selector, the banner stating which definition is in force, the single "
            "τ_opt field, and the flat τ_opt(λ) it produces."
        ),
    ),
    Capture(
        name="ug_platform_workspace",
        config=_TIRS_B10,
        stage="platform",
        tab="Inputs",
        param_dock_width=520,
        # Every committed config leaves jitter and smear at zero, which makes the whole
        # output block read 0 m with EE_box 1 — true, and it teaches nothing. One
        # isotropic jitter value (the field an operator types first) gives the derived
        # outputs something to be.
        set_parameters={"platform.jitter_rms_urad": 8.0},
        caption=(
            "Platform workspace, Inputs tab, with an 8 µrad isotropic jitter entered — "
            "the jitter and motion/smear knobs beside the jitter σ, smear width and "
            "EE_box the stage derives from them."
        ),
    ),
    Capture(
        name="ug_detector_inputs",
        config=_TIRS_B10,
        stage="detector",
        tab="Inputs",
        # No param_dock_width (CU-363): narrowing the central area past the detector
        # form's column-relayout threshold blanks its painted field values.
        caption=(
            "Detector workspace, Inputs tab — the FPA part-library row above the "
            "full detector schema in labelled groups, with no preset applied."
        ),
    ),
    Capture(
        name="ug_readout_workspace",
        config=_OLI2_B04,
        stage="readout",
        param_dock_width=520,
        caption=(
            "Readout workspace on the Landsat 9 OLI-2 band-4 config — architecture, "
            "read noise, ADC, full well, TDI, co-adds, binning and acquisition groups "
            "beside the DN and noise outputs."
        ),
    ),
    Capture(
        name="ug_calibration_workspace",
        config=_TIRS_B10,
        stage="calibration",
        param_dock_width=520,
        # The committed configs all leave calibration.scheme at 'none', which shows the
        # selector and nothing else — a true but uninformative picture of a stage whose
        # whole design is scheme-contextual. Two edits put it in the state the chapter
        # describes; both are ordinary field edits an operator makes on this screen.
        set_parameters={"calibration.scheme": "one_point", "calibration.cal_temp_low_K": 290.0},
        caption=(
            "Calibration workspace with a one-point scheme active — the scheme selector "
            "and the groups it reveals, beside the residual, drift and bias outputs."
        ),
    ),
    Capture(
        name="ug_configured_parameters",
        config=_OLI2_STUDY,
        stage="spectral_integration",
        target="parameter_panel",
        param_dock_width=560,
        caption=(
            "The Parameters dock (panel-level grab) on the nine-band OLI-2 study — the "
            "configured parameters carry the red C badge; everything unmarked is shared."
        ),
    ),
    Capture(
        name="ug_performance_selection",
        config=_MINIMAL,
        stage="performance",
        # Two groups switched off — exactly what the Compute checkboxes do, one
        # sensor.set each. No committed config ships a reduced metric selection, and
        # the whole point of the figure is what a reduced one looks like.
        set_parameters={
            "performance.metrics.spatial_mtf": False,
            "performance.metrics.interpretability": False,
        },
        caption=(
            "Performance workspace with the Spatial / MTF and Interpretability groups "
            "deselected — the Compute row's state and the card sections that survive it."
        ),
    ),
    Capture(
        name="ug_messages_error",
        config=_TIRS_B10,
        stage="calibration",
        target="right_rail",
        # A calibration scheme switched on without its cal points: the advisory-routed
        # incomplete-config state (no modal), which is what makes it capturable — and
        # what chapter 12 uses to show the Messages rail carrying a real failure.
        set_parameters={"calibration.scheme": "two_point"},
        caption=(
            "The right rail (panel-level grab) after a failed evaluation — pinned cards "
            "flipped to their stale marker and the Messages panel carrying the error."
        ),
    ),
    # ==================================================================================
    # Volume IV Part C captures — the four tier-1 GUI-led case studies (plan §7, ruling
    # Q3). Three registry conventions are load-bearing here and are repeated per figure
    # rather than left implicit:
    #   * No ``param_dock_width`` on any *form* capture. Widening the dock narrows the
    #     central column past the schema form's relayout threshold, where painted field
    #     values go blank or clip — CU-363, first recorded against the detector form and
    #     reproduced on the geometry mode form at 520 px. Form figures keep the default
    #     dock; the parameter tree gets its own panel-level grab where it is the subject.
    #   * Panel grabs (``target="central_canvas.stage_center"``) where the parameter
    #     dock would otherwise render an absolute filesystem path in a visible cell
    #     (Findings_Log 2026-09-16) — scenario 1.1 carries an emissivity CSV path.
    #   * Schematic captures narrow the dock instead (``param_dock_width=220``): the
    #     subject is the viewport, and the extra width keeps the sensor's altitude
    #     leader pill inside it.
    # ==================================================================================
    # -- Case study: 1.1 MWIR maritime surveillance (Sarah) ---------------------------
    Capture(
        name="case_maritime_geometry",
        config=_CASE_MARITIME,
        stage="geometry",
        tab="Inputs",
        caption=(
            "Geometry workspace, Inputs tab, on the scenario 1.1 baseline — the derived "
            "space_to_ground scene class and the V1 path-zenith viewing mode."
        ),
    ),
    Capture(
        name="case_maritime_scene_regime",
        config=_CASE_MARITIME,
        stage="source",
        tab="Scene & regime",
        target="central_canvas.stage_center",
        caption=(
            "Source workspace, Scene & regime tab (panel grab) — the declared sub-pixel "
            "scene, the 240 m^2 projected area, and the resulting angular extent."
        ),
    ),
    Capture(
        name="case_maritime_atmosphere",
        config=_CASE_MARITIME,
        stage="atmosphere",
        target="central_canvas.stage_center",
        # The grabbed panel is only as tall and wide as the window leaves it: at the
        # default size the Background-path plot was cut mid-axes and the target-path
        # plot's two y-axis labels overlapped each other (CU-370 IV-032).
        width=1720,
        height=1300,
        caption=(
            "Atmosphere workspace (panel grab) — the parametric maritime/midlat_summer "
            "inputs and the target-path transmittance and path radiance they produce."
        ),
    ),
    Capture(
        name="case_maritime_optics",
        config=_CASE_MARITIME,
        stage="optics",
        tab="Inputs",
        param_dock_width=520,
        caption=(
            "Optics workspace, Inputs tab — the 30 cm f/2.5 aperture and the stage "
            "outputs, including the final radiometric regime."
        ),
    ),
    Capture(
        name="case_maritime_noise",
        config=_CASE_MARITIME,
        stage="detector",
        tab="Noise",
        caption=(
            "Detector workspace, Noise tab — the per-term noise budget of the maritime "
            "sub-pixel scene, where background shot nearly matches signal shot."
        ),
    ),
    Capture(
        name="case_maritime_performance",
        config=_CASE_MARITIME,
        stage="performance",
        caption=(
            "Performance workspace on the scenario 1.1 baseline — all five metric "
            "groups, with SNR and contrast SNR two orders of magnitude apart."
        ),
    ),
    # -- Case study: 2.1 InSb vs HgCdTe noise budget (Mike) ----------------------------
    Capture(
        name="case_shootout_detector",
        config=_CASE_SHOOTOUT,
        stage="detector",
        tab="Inputs",
        caption=(
            "Detector workspace, Inputs tab, on the scenario 2.1 InSb bench branch — "
            "the FPA part-library row, the scalar QE, and the vendor dark rate."
        ),
    ),
    Capture(
        name="case_shootout_noise",
        config=_CASE_SHOOTOUT,
        stage="detector",
        tab="Noise",
        caption=(
            "Detector workspace, Noise tab — the InSb bench noise budget, photon-limited "
            "with quantization as the second term."
        ),
    ),
    Capture(
        name="case_shootout_readout",
        config=_CASE_SHOOTOUT,
        stage="readout",
        caption=(
            "Readout workspace — the shared ROIC: analog well, 305 e-/DN conversion "
            "gain over 14 bits, and the 1 ms frame integration."
        ),
    ),
    Capture(
        name="case_shootout_performance",
        config=_CASE_SHOOTOUT,
        stage="performance",
        caption=(
            "Performance workspace on the InSb bench branch — the metric groups a "
            "detector-only bench populates, and the ones it cannot."
        ),
    ),
    # -- Case study: 3.1 ISR pass planning (Raj) ---------------------------------------
    Capture(
        name="case_pass_geometry",
        config=_CASE_PASS_PLANNING,
        stage="geometry",
        tab="Inputs",
        caption=(
            "Geometry workspace, Inputs tab, on the scenario 3.1 baseline — a 600 km "
            "orbit looking 30 deg off nadir through the V1 path-zenith mode."
        ),
    ),
    Capture(
        name="case_pass_schematic",
        config=_CASE_PASS_PLANNING,
        stage="geometry",
        tab="Schematic",
        param_dock_width=220,
        caption=(
            "Geometry workspace, Schematic tab — the off-nadir look with the sun vector "
            "and the not-to-scale altitude leader pill."
        ),
    ),
    Capture(
        name="case_pass_sweep_axis",
        config=_CASE_PASS_PLANNING,
        stage="geometry",
        tab="Inputs",
        target="parameter_panel",
        param_dock_width=560,
        caption=(
            "Parameters dock (panel grab) — the geometry branch holding "
            "geometry.path_zenith_rad, the axis the pass-planning sweep walks."
        ),
    ),
    Capture(
        name="case_pass_performance",
        config=_CASE_PASS_PLANNING,
        stage="performance",
        caption=(
            "Performance workspace at 30 deg off nadir — GSD, swath, NIIRS and SNR, the "
            "four numbers a collection plan is argued from."
        ),
    ),
    # -- Case study: 10.2 air-to-air level-arm IRST ------------------------------------
    Capture(
        name="case_irst_scene_class",
        config=_CASE_IRST,
        stage="geometry",
        tab="Inputs",
        caption=(
            "Geometry workspace, Inputs tab, on the scenario 10.2 baseline — the derived "
            "air_to_air scene class, its off-by-default metric list, and the V0 mode."
        ),
    ),
    Capture(
        name="case_irst_schematic",
        config=_CASE_IRST,
        stage="geometry",
        tab="Schematic",
        param_dock_width=220,
        caption=(
            "Geometry workspace, Schematic tab — the level composition with both "
            "endpoints at altitude and the tangent-depression leader pill."
        ),
    ),
    Capture(
        name="case_irst_mtf",
        config=_CASE_IRST,
        stage="optics",
        tab="MTF",
        caption=(
            "Optics workspace, MTF tab — the undersampled IRST's MTF budget, where the "
            "pixel aperture rings past its first zero above Nyquist."
        ),
    ),
    Capture(
        name="case_irst_noise",
        config=_CASE_IRST,
        stage="detector",
        tab="Noise",
        caption=(
            "Detector workspace, Noise tab — the 50 km noise budget, dominated by the "
            "target's own shot noise rather than by the sky floor."
        ),
    ),
    Capture(
        name="case_irst_performance",
        config=_CASE_IRST,
        stage="performance",
        caption=(
            "Performance workspace on the level arm — the ground-projection metric "
            "family absent by scene class, target-plane sample distance in its place."
        ),
    ),
)


# -- pure helpers (unit-tested; no Qt) --------------------------------------------


def capture_by_name(name: str) -> Capture | None:
    """The registry entry called *name*, or ``None``."""
    for capture in CAPTURES:
        if capture.name == name:
            return capture
    return None


def validate_registry(captures: tuple[Capture, ...] = CAPTURES) -> list[str]:
    """Problems with the capture registry, one message per problem (empty when sound).

    Checked: unique names, filename-safe names, input configs that exist, positive
    window sizes, dock widths that fit inside the window, and splitter sizes that are
    a non-empty run of positive pixel sizes.
    """
    problems: list[str] = []
    seen: set[str] = set()
    for capture in captures:
        if capture.name in seen:
            problems.append(f"duplicate capture name: {capture.name}")
        seen.add(capture.name)
        if not NAME_RE.match(capture.name):
            problems.append(
                f"capture name is not a safe file stem: {capture.name!r} "
                "(lowercase letters, digits, single underscores)"
            )
        if not capture.config_path.is_file():
            problems.append(f"{capture.name}: input config not found: {capture.config}")
        if capture.width <= 0 or capture.height <= 0:
            problems.append(
                f"{capture.name}: window size must be positive, got "
                f"{capture.width}x{capture.height}"
            )
        for label, dock_width in (
            ("param_dock_width", capture.param_dock_width),
            ("rail_dock_width", capture.rail_dock_width),
        ):
            if dock_width is not None and not 0 < dock_width < capture.width:
                problems.append(
                    f"{capture.name}: {label}={dock_width} does not fit in a "
                    f"{capture.width}px-wide window"
                )
        if capture.tab is not None and not capture.tab.strip():
            problems.append(
                f"{capture.name}: tab must be a visible tab label, not blank "
                "(e.g. 'Inputs', 'Schematic', 'MTF')"
            )
        if capture.tab is not None and capture.stage is None:
            problems.append(
                f"{capture.name}: tab={capture.tab!r} needs a stage — sub-view tabs belong "
                "to a stage workspace, and no workspace is selected without one"
            )
        for object_name, sizes in capture.splitter_sizes.items():
            if not sizes or any(size <= 0 for size in sizes):
                problems.append(
                    f"{capture.name}: splitter_sizes[{object_name!r}]={tuple(sizes)} must be "
                    "a non-empty run of positive pixel sizes"
                )
        for dotpath in capture.set_parameters:
            if not dotpath or "." not in dotpath:
                problems.append(
                    f"{capture.name}: set_parameters key {dotpath!r} is not a parameter "
                    "dot-path (e.g. 'performance.metrics.spatial_mtf')"
                )
    return problems


def git_commit() -> str:
    """``git rev-parse --short HEAD``, or ``"unknown"`` when git or the history is absent."""
    if shutil.which("git") is None:
        return "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError:
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def png_dimensions(path: Path) -> tuple[int, int]:
    """``(width, height)`` read straight out of a PNG's IHDR chunk.

    Header-only, so verifying a generated figure needs no image library (Rule: no new
    dependencies). Raises :class:`ScreenshotError` if the file is not a PNG.
    """
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ScreenshotError(
            f"not a PNG file: {path}\n"
            "  why: the figure verifier reads width/height from the PNG IHDR chunk.\n"
            "  action: delete the file and re-run the generator for that capture."
        )
    width, height = struct.unpack(">II", header[16:24])
    return int(width), int(height)


def render_manifest(
    captures: tuple[Capture, ...] = CAPTURES,
    *,
    commit: str = "unknown",
    generated_on: str = "",
) -> str:
    """The provenance record for the figure set (Rule 26(b)).

    Names the generator, every figure's input config, capture name, window size and
    the commit the figures were generated from. Rendered from the whole registry, not
    from the subset a partial run regenerated, so the file does not churn with the CLI
    selection.
    """
    stamp = generated_on or date.today().isoformat()
    lines = [
        "# GUI Figure Manifest",
        "",
        "Status: Generated — do not hand-edit.",
        "",
        "Every figure in this folder is produced by `scripts/gen_gui_screenshots.py`,",
        "which drives the real `RADIANTMainWindow` under `QT_QPA_PLATFORM=offscreen` on a",
        "committed input config and grabs the window (or a named panel) after the window's",
        "auto-evaluation completes. Offscreen rendering uses platform-neutral Fusion chrome",
        "(Support_Documentation_Plan §10, ruling Q7), so the figures do not depend on who",
        "regenerated them.",
        "",
        "Regenerate the whole set with:",
        "",
        "```",
        "python scripts/gen_gui_screenshots.py --all",
        "```",
        "",
        "- Generator: `scripts/gen_gui_screenshots.py`",
        f"- Commit: `{commit}`",
        f"- Generated: {stamp}",
        f"- Figures: {len(captures)}",
        "",
        "| Figure | Capture | Input config | Workspace | Target | Window |",
        "|---|---|---|---|---|---|",
    ]
    for capture in captures:
        target = f"`{capture.target}`" if capture.target else "full window"
        stage = f"`{capture.stage}`" if capture.stage else "as opened"
        if capture.tab:
            stage = f"{stage} → {capture.tab}"
        lines.append(
            f"| `{capture.filename}` | `{capture.name}` | `{capture.config}` | "
            f"{stage} | {target} | {capture.width}×{capture.height} |"
        )
    lines.append("")
    edited = [c for c in captures if c.set_parameters]
    if edited:
        lines.append("## Pre-capture parameter edits")
        lines.append("")
        lines.append(
            "These figures show a state an operator reaches by editing a field, so the "
            "generator applies the edits below to the loaded config's shared base "
            "(one `Sensor.set` each, values in the schema's input unit) before building "
            "the window."
        )
        lines.append("")
        for capture in edited:
            edits = "; ".join(f"`{k}` = `{v!r}`" for k, v in capture.set_parameters.items())
            lines.append(f"- `{capture.filename}` — {edits}")
        lines.append("")
    captioned = [c for c in captures if c.caption]
    if captioned:
        lines.append("## Captions")
        lines.append("")
        for capture in captioned:
            lines.append(f"- `{capture.filename}` — {capture.caption}")
        lines.append("")
    return "\n".join(lines)


def write_manifest(out_dir: Path, *, commit: str | None = None) -> Path:
    """Write :func:`render_manifest` into *out_dir*. Returns the manifest path."""
    path = out_dir / MANIFEST_NAME
    path.write_text(
        render_manifest(commit=commit if commit is not None else git_commit()),
        encoding="utf-8",
    )
    return path


# -- Qt driving ------------------------------------------------------------------


def require_pyside() -> None:
    """Fail with an actionable message when the optional ``gui`` extra is absent."""
    try:
        import PySide6  # noqa: F401
    except ImportError as exc:
        raise ScreenshotError(
            "PySide6 is not installed, so the GUI cannot be driven.\n"
            "  why: the manual's GUI figures are captured from the real RADIANT GUI,\n"
            "       which ships in the optional 'gui' extra.\n"
            '  action: pip install -e ".[gui]" and re-run.'
        ) from exc


def _resolve_target(window: object, dotted: str) -> QWidget:
    """Resolve a dotted attribute path against *window*, e.g. ``central_canvas.stage_center``."""
    current: Any = window
    walked: list[str] = []
    for part in dotted.split("."):
        walked.append(part)
        if not hasattr(current, part):
            raise ScreenshotError(
                f"capture target {dotted!r} does not resolve: no attribute "
                f"{'.'.join(walked)!r} on the main window.\n"
                "  why: panel-level figures grab a child widget by its public accessor.\n"
                "  action: name an accessor that exists on RADIANTMainWindow "
                "(e.g. parameter_panel, central_canvas, right_rail, stage_strip)."
            )
        current = getattr(current, part)
    return current  # type: ignore[no-any-return]


def _wait_for_evaluation(app: Any, window: Any, timeout_s: float) -> None:
    """Block until the window's auto-evaluation has produced a run, or fail loudly.

    The window schedules its first evaluation with ``QTimer.singleShot(0,
    _evaluate_now)`` and runs it on a worker thread, so the result only appears once
    the event loop has turned. This pumps the loop and polls ``last_run`` — the same
    completion signal the GUI tests await via ``evaluationFinished`` — never sleeping
    blindly and never hanging (Rule 17: no silent failure).
    """
    from PySide6.QtCore import QEventLoop

    deadline = time.monotonic() + timeout_s
    while window.last_run is None:
        if time.monotonic() > deadline:
            raise ScreenshotError(
                f"the GUI did not finish evaluating within {timeout_s:.0f} s.\n"
                "  why: figures must show populated metrics, so the capture waits for the\n"
                "       window's auto-evaluation (RADIANTMainWindow.last_run) to complete.\n"
                "  action: check that the input config resolves — run\n"
                "          `radiant run <config>` — then re-run this generator."
            )
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    # One more turn so the result-driven repaint (KPI cards, figures) has been applied.
    _settle(app, turns=5)


def _settle(app: Any, *, turns: int = 3) -> None:
    """Pump the event loop a few times so pending layout/paint work is applied."""
    from PySide6.QtCore import QEventLoop

    for _ in range(turns):
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)


#: Qt ``objectName`` of the per-stage sub-view tab bar (``StagePane``). Every tabbed
#: stage builds one; the unselected stages keep theirs in the tree as hidden pages, which
#: is why the selector filters on visibility.
STAGE_SUBVIEW_TABS = "stageSubViewTabs"


def _select_tab(window: Any, capture: Capture) -> None:
    """Select the capture's named sub-view tab in the currently shown stage workspace.

    Called after the stage is selected — the per-stage composite (and its tab bar) is
    built on selection, so there is nothing to search before then. Only *visible* tab
    bars are considered: the stages that are not showing keep theirs in the widget tree,
    and a bare ``findChild`` would happily switch a tab nobody is looking at.
    """
    from PySide6.QtWidgets import QTabWidget

    if capture.tab is None:
        return
    # ``StagePane`` escapes "&" to "&&" when it adds a tab, because Qt reads a bare "&"
    # in a tab title as a mnemonic marker ("Scene & regime" would render "Scene _regime").
    # The registry names the *stage spec's* title, so the same escaping is applied here
    # rather than asking every capture to spell the Qt form — which would also break the
    # registry-vs-spec check in scripts/test_gen_gui_screenshots.py.
    wanted = capture.tab.replace("&", "&&")
    visible = [t for t in window.findChildren(QTabWidget, STAGE_SUBVIEW_TABS) if t.isVisible()]
    if not visible:
        raise ScreenshotError(
            f"{capture.name}: the {capture.stage!r} workspace has no sub-view tabs, but the "
            f"capture asks for tab {capture.tab!r}.\n"
            "  why: only the tabbed stages (Geometry, Source, Optics, Platform, Detector)\n"
            "       declare sub-views; the rest render a single pane.\n"
            "  action: drop the capture's `tab` field, or name a stage that has tabs."
        )
    labels: list[str] = []
    for tabs in visible:
        for index in range(tabs.count()):
            label = tabs.tabText(index)
            # Report the un-escaped form, so the error names what the capture should say.
            labels.append(label.replace("&&", "&"))
            if label == wanted:
                tabs.setCurrentIndex(index)
                return
    raise ScreenshotError(
        f"{capture.name}: no sub-view tab labelled {capture.tab!r} in the {capture.stage!r} "
        f"workspace.\n"
        f"  why: tabs are selected by their visible label. This workspace offers: "
        f"{', '.join(repr(text) for text in labels)}.\n"
        "  action: use one of those labels (they are the tab titles in "
        "src/radiant/gui/stage_views.py)."
    )


def _apply_dock_widths(window: Any, capture: Capture) -> None:
    """Resize the parameter / right-rail docks to the capture's widths.

    Caution (CU-363): narrowing the central area past a schema form's column-relayout
    threshold leaves ``DetectorInputsForm``'s field values painted blank (the model
    keeps them; the rebuilt rows do not repaint) — regardless of whether the resize
    lands before or after the stage is selected. Until that is fixed, captures of the
    full-schema detector form should not request a wide parameter dock.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDockWidget

    docks: list[QDockWidget] = []
    widths: list[int] = []
    for object_name, wanted in (
        ("parameterDock", capture.param_dock_width),
        ("rightRailDock", capture.rail_dock_width),
    ):
        if wanted is None:
            continue
        dock = window.findChild(QDockWidget, object_name)
        if dock is None:
            raise ScreenshotError(
                f"{capture.name}: dock {object_name!r} not found on the main window.\n"
                "  why: the capture asks for a non-default dock width.\n"
                "  action: the GUI's dock objectNames changed — update this generator."
            )
        docks.append(dock)
        widths.append(wanted)
    if docks:
        window.resizeDocks(docks, widths, Qt.Orientation.Horizontal)


def _apply_splitters(window: Any, capture: Capture) -> None:
    """Apply the capture's named splitter sizes.

    Called **after** the stage and tab selection: the per-stage composites (and their
    splitters) are built on selection, so an earlier application would look for a
    widget that does not exist yet.
    """
    from PySide6.QtWidgets import QSplitter

    for object_name, sizes in capture.splitter_sizes.items():
        # Several stage composites build a splitter with the *same* objectName (e.g.
        # "stagePanelSplit" per stage panel), and the unselected ones stay in the tree
        # as hidden pages — so a bare findChild would silently size the wrong, invisible
        # one. Only the visible matches (the ones in the figure) are touched.
        matches = window.findChildren(QSplitter, object_name)
        visible = [s for s in matches if s.isVisible()]
        if not visible:
            raise ScreenshotError(
                f"{capture.name}: no visible splitter named {object_name!r} in this "
                f"workspace ({len(matches)} hidden match(es)).\n"
                "  why: the capture asks for non-default splitter sizes, and the pane it\n"
                "       names is either absent from this workspace or has been renamed.\n"
                "  action: check the objectName against the stage's widget "
                "(src/radiant/gui/widgets/), or drop the splitter_sizes entry."
            )
        for splitter in visible:
            splitter.setSizes(list(sizes))


def _release(app: Any, window: Any) -> None:
    """Close and actually delete a captured window (the CU-212 accumulation fix).

    ``close()`` only hides; without the ``deleteLater`` + deferred-delete drain, every
    window a multi-capture run builds stays in the live widget tree that
    ``QApplication.setStyleSheet`` walks.

    Teardown-only, so it swallows the one error class it can provoke: pumping the loop
    after a delete can deliver a timer whose target C++ object is already gone
    (shiboken's ``Internal C++ object already deleted``). Letting that escape a
    ``finally`` would *replace* the real capture failure with teardown noise — which is
    exactly how the actionable message for a bad capture definition got masked. Nothing
    else is suppressed, and a genuine capture error still propagates from the caller.
    """
    import contextlib

    from PySide6.QtCore import QEvent

    with contextlib.suppress(RuntimeError):
        window.close()
        window.setParent(None)
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        _settle(app, turns=2)


def _qapplication(settings_dir: Path) -> Any:
    """The process-wide :class:`QApplication`, themed light and sandboxed from user prefs.

    The light theme is pinned rather than read from ``QSettings`` so the figures do not
    depend on whether the developer regenerating them last used dark mode; redirecting
    the INI path keeps the run from reading *or writing* the real user's GUI
    preferences (the same sandbox the GUI suite's conftest installs).
    """
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from radiant.gui.themes import LIGHT, apply_theme

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_dir))

    app = QApplication.instance() or QApplication([])
    apply_theme(app, LIGHT)
    return app


def _apply_parameter_edits(config_set: Any, capture: Capture) -> None:
    """Apply the capture's ``set_parameters`` to the loaded document's shared base.

    One ``Sensor.set`` per entry — the same single API call the GUI makes for a field
    edit — so the captured window is in a state an operator could have reached, not a
    state synthesized behind the API. A rejected value fails the capture loudly
    (Rule 17): the message names the capture and the dot-path.
    """
    if not capture.set_parameters:
        return
    from radiant.core.exceptions import RadiantError

    for dotpath, value in capture.set_parameters.items():
        try:
            config_set.base.set(dotpath, value)
        except RadiantError as exc:
            raise ScreenshotError(
                f"{capture.name}: set_parameters[{dotpath!r}] = {value!r} was rejected.\n"
                f"  why: the API refused the edit — {exc}\n"
                "  action: fix the value (or the dot-path) in this capture's "
                "set_parameters in scripts/gen_gui_screenshots.py."
            ) from exc


def capture_one(app: Any, capture: Capture, out_dir: Path) -> Path:
    """Build the window for *capture*, wait for its evaluation, grab it, write the PNG."""
    from radiant.api import ConfigurationSet
    from radiant.gui.main_window import RADIANTMainWindow
    from radiant.gui.settings_store import SettingsStore

    if not capture.config_path.is_file():
        raise ScreenshotError(
            f"{capture.name}: input config not found: {capture.config}\n"
            "  why: every figure is generated from a committed config.\n"
            "  action: fix the capture's `config` field in scripts/gen_gui_screenshots.py."
        )

    # The GUI's File → Open reads every document through ConfigurationSet.load, which
    # returns the full study for a `configurations:` file and the degenerate
    # one-configuration set for a plain config. Using the same reader here is what lets a
    # capture name a multi-configuration study and get the selector and the
    # per-configuration metric columns the operator sees.
    config_set = ConfigurationSet.load(capture.config_path)
    _apply_parameter_edits(config_set, capture)
    window = RADIANTMainWindow(
        config_set=config_set, path=str(capture.config_path), settings=SettingsStore()
    )
    try:
        # Size first (the layout the window realizes must be the captured one), then
        # show, evaluate, select the stage, and only then apply the fine geometry.
        window.resize(capture.width, capture.height)
        window.show()
        _settle(app)
        _wait_for_evaluation(app, window, EVALUATION_TIMEOUT_S)

        if capture.stage is not None:
            window.stage_strip.stageClicked.emit(capture.stage)
            _settle(app, turns=5)
        _select_tab(window, capture)
        _settle(app, turns=3)
        _apply_dock_widths(window, capture)
        _apply_splitters(window, capture)
        _settle(app, turns=3)

        widget = _resolve_target(window, capture.target) if capture.target else window
        pixmap = widget.grab()
        if pixmap.isNull():
            raise ScreenshotError(
                f"{capture.name}: QWidget.grab() produced an empty pixmap.\n"
                "  why: an unrealized or zero-sized widget cannot be rendered.\n"
                "  action: check the capture's target and window size."
            )
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / capture.filename
        if not pixmap.save(str(path), "PNG"):
            raise ScreenshotError(
                f"{capture.name}: could not write {path}.\n"
                "  why: Qt refused to encode or write the PNG.\n"
                "  action: check the output directory is writable and has free space."
            )
        return path
    finally:
        _release(app, window)


def run_captures(captures: list[Capture], out_dir: Path) -> int:
    """Capture every entry in *captures* into *out_dir*, then refresh the manifest."""
    require_pyside()
    with tempfile.TemporaryDirectory(prefix="radiant-shots-") as settings_dir:
        app = _qapplication(Path(settings_dir))
        for capture in captures:
            path = capture_one(app, capture, out_dir)
            width, height = png_dimensions(path)
            size_kb = path.stat().st_size / 1024
            print(
                f"wrote {path.relative_to(REPO) if path.is_relative_to(REPO) else path} "
                f"({width}x{height} px, {size_kb:.0f} kB)"
            )
    manifest = write_manifest(out_dir)
    print(f"wrote {manifest.relative_to(REPO) if manifest.is_relative_to(REPO) else manifest}")
    return 0


# -- CLI ---------------------------------------------------------------------------


def resolve_captures(names: list[str], *, capture_all: bool) -> tuple[list[Capture], int]:
    """Turn the CLI selection into a capture list. Returns ``(captures, status)``."""
    known = ", ".join(c.name for c in CAPTURES)
    if capture_all:
        return list(CAPTURES), 0
    if not names:
        print(
            "error: no capture named, and --all not given.\n"
            f"  why: the generator needs to know what to capture. Known: {known}\n"
            "  action: pass one or more capture names, --all, or --list.",
            file=sys.stderr,
        )
        return [], 2
    selected: list[Capture] = []
    for name in names:
        capture = capture_by_name(name)
        if capture is None:
            print(
                f"error: unknown capture: {name}\n"
                f"  why: only registered captures can be generated. Known: {known}\n"
                "  action: run with --list, or add the capture to CAPTURES in this script.",
                file=sys.stderr,
            )
            return [], 2
        selected.append(capture)
    return selected, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gen_gui_screenshots.py",
        description="Generate the manual's GUI figures by driving the GUI offscreen.",
    )
    parser.add_argument(
        "captures",
        nargs="*",
        metavar="NAME",
        help="capture name(s) to generate (see --list)",
    )
    parser.add_argument("--all", action="store_true", help="generate every registered capture")
    parser.add_argument("--list", action="store_true", help="list capture names and exit")
    parser.add_argument(
        "--out",
        metavar="DIR",
        default=None,
        help=f"output directory (default: {FIGURES.relative_to(REPO).as_posix()})",
    )
    args = parser.parse_args(argv)

    problems = validate_registry()
    if problems:
        for problem in problems:
            print(f"error: capture registry: {problem}", file=sys.stderr)
        return 1

    if args.list:
        for capture in CAPTURES:
            target = capture.target or "full window"
            print(
                f"{capture.name:<24} {capture.config:<32} "
                f"stage={capture.stage or '-':<12} target={target}"
            )
        return 0

    if args.all and args.captures:
        print(
            "error: --all and an explicit capture list are mutually exclusive.\n"
            "  why: the two say different things about what to generate.\n"
            "  action: pass --all, or name the captures, not both.",
            file=sys.stderr,
        )
        return 2

    captures, status = resolve_captures(args.captures, capture_all=args.all)
    if status != 0:
        return status

    out_dir = Path(args.out).expanduser().resolve() if args.out else FIGURES
    try:
        return run_captures(captures, out_dir)
    except ScreenshotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Registry of one GUI-loadable *baseline* per validated scenario.

Each scenario runner (``scenarios/<persona>/<slug>/scripts/run_*.py``) was
validated against the backend engine but stores its configuration as an
``.xlsx`` plus hard-coded Python — none of which the GUI can open (the GUI
opens YAML only, ``File -> Open YAML``). This registry names, for every
scenario, a single *baseline* :class:`~radiant.api.Sensor` derived from the
validated runner. ``emit_gui_yaml.py`` serialises each to
``inputs/<slug>.gui.yaml``; ``verify_gui_yaml.py`` reloads and re-evaluates
each to prove the GUI artifact reproduces the backend metrics.

A "baseline" is the nominal point of a sweep (mid-range aperture, nominal
atmosphere, etc.) — a portable config that opens and runs in the GUI with no
external staged files (MODTRAN tape7 variants use the ``simple`` atmosphere
here; the scripting-window script demonstrates the tape7 path separately).

Adding a scenario: append a :class:`GuiScenario`. Prefer ``runner_factory``
(imports the validated builder — zero drift). Only when a runner exposes no
importable factory, transcribe the baseline into an inline ``build`` and let
``verify_gui_yaml`` confirm it evaluates cleanly.
"""

from __future__ import annotations

import math  # noqa: F401  (used by inline builders)
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from _runner_import import import_runner

from radiant.api import Sensor

REPO = Path(__file__).resolve().parents[2]
SCENARIOS = REPO / "scenarios"


@dataclass(frozen=True)
class GuiScenario:
    """One scenario's GUI baseline."""

    id: str  # "1.1"
    persona: str  # "01_sarah_systems_engineer"
    slug: str  # "1.1_mwir_maritime_surveillance"
    title: str
    build: Callable[[], Sensor]
    # Headline metrics the verify gate snapshots + re-checks after reload.
    metrics: tuple[str, ...] = ("snr", "nedt_K", "niirs")
    notes: str = ""
    # Extra stage-output scalars to snapshot (dotted "stage.key"), optional.
    stage_scalars: tuple[str, ...] = field(default_factory=tuple)
    # Console-script micro-sweep axis (the scenario's real trade variable).
    # (param_dotpath, human label, unit-for-display). None -> generator picks
    # aperture, else integration time.
    sweep: tuple[str, str, str] | None = None

    @property
    def folder(self) -> Path:
        return SCENARIOS / self.persona / self.slug

    @property
    def yaml_path(self) -> Path:
        return self.folder / "inputs" / f"{self.slug}.gui.yaml"

    @property
    def expected_path(self) -> Path:
        return self.folder / "inputs" / f"{self.slug}.gui.expected.json"

    @property
    def gui_script_path(self) -> Path:
        return self.folder / "scripts" / f"gui_console_{self.slug}.py"


def runner_factory(
    persona: str,
    slug: str,
    runner_file: str,
    make: Callable[[object], Sensor],
) -> Callable[[], Sensor]:
    """Build a baseline by importing the validated runner and calling ``make``.

    ``make`` receives the imported runner module and returns a configured
    :class:`Sensor` (e.g. ``lambda m: Sensor.from_dict(m.make_config(0.30,
    "simple"))``). The runner's ``main()`` never fires.
    """

    def _build() -> Sensor:
        mod = import_runner(
            SCENARIOS / persona / slug / "scripts" / runner_file,
            f"scenrunner_{slug}",
        )
        return make(mod)

    return _build


def _recenter(sensor: Sensor, overrides: dict[str, object]) -> Sensor:
    """Apply GUI-baseline re-center overrides to a runner-built ``Sensor``.

    CU-170 / CU-166(iv): a handful of GUI baselines captured a *saturating*
    mid-sweep point (full-well / ADC clip), and the CU-166 applicability gate
    now returns NIIRS N/A outside the GIQE-5 envelope. This applies the
    owner-approved re-center (raise ADC gain/bits to a well-matched value, or
    shorten integration time so the nominal point no longer clips) and/or the
    ``performance.niirs.allow_extrapolated`` opt-in for walkthroughs whose story
    is a NIIRS trend. The override is on the *GUI baseline only* — the validated
    runner sweep is unchanged; each move is documented in the scenario
    walkthrough and ``notes``.
    """

    for dotpath, value in overrides.items():
        sensor.set(dotpath, value)
    return sensor


# ---------------------------------------------------------------------------
# Inline baseline builders for runners with no importable factory. Each
# transcribes the runner's *nominal* config (or, for MODTRAN-interpolation
# runners, its chain config with a portable SimpleAtmosphere) faithfully.
# ---------------------------------------------------------------------------
def _build_3_3_vendor_a(m: object) -> Sensor:
    """Scenario 3.3 baseline = Vendor A (transcribes ``evaluate_vendor``)."""
    spec = m.VENDORS["Vendor A"]  # type: ignore[attr-defined]
    focal = spec["fnum"] * spec["aperture"]
    s = Sensor()
    s.set("source.scene_type", "extended")
    s.set("source.target.temperature", m.SCENE_TEMP_K, unit="K")  # type: ignore[attr-defined]
    s.set("source.target.emissivity", m.SCENE_EMIS)  # type: ignore[attr-defined]
    s.set("source.target.is_hot_target", True)
    s.set("atmosphere.model", "simple")
    s.set("atmosphere.standard_atmosphere", "us_standard")
    s.set("geometry.sensor_altitude_m", m.ALT_M)  # type: ignore[attr-defined]
    s.set("optics.aperture_diameter_m", spec["aperture"])
    s.set("optics.focal_length_m", focal)
    s.set("optics.transmission_scalar", spec["tau"])
    s.set("detector.pixel_pitch_x_um", spec["pitch"])
    s.set("detector.pixel_pitch_y_um", spec["pitch"])
    s.set("detector.qe_value", spec["qe"])
    s.set("detector.dark_rate_e_per_s", spec["dark"])
    s.set("detector.detector_temperature_K", spec["tdet"])
    s.set("detector.n_pixels_cross", m.N_PIX_CROSS)  # type: ignore[attr-defined]
    s.set("spectral_integration.filter_min_um", spec["band"][0])
    s.set("spectral_integration.filter_max_um", spec["band"][1])
    s.set("spectral_integration.integration_time_s", m.T_INT_S)  # type: ignore[attr-defined]
    s.set("readout.read_noise_e_rms", spec["read"])
    s.set("readout.gain_e_per_dn", 20.0)
    s.set("readout.adc_bits", 14)
    s.set("readout.full_well_capacity_e", 6e6)
    return s


def _build_5_2_nominal(m: object) -> Sensor:
    """Scenario 5.2 baseline = mid pixel-pitch row (transcribes the sweep body)."""
    pitches = m.pitches_um  # type: ignore[attr-defined]
    d = m.det_table  # type: ignore[attr-defined]
    idx = len(pitches) // 2
    p_um = pitches[idx]
    config = {
        "source": {
            "target": {"temperature": m.target_temp, "emissivity": m.target_emiss},  # type: ignore[attr-defined]
            "background": {"temperature": m.bg_temp, "emissivity": m.bg_emiss},  # type: ignore[attr-defined]
        },
        "atmosphere": {"model": "simple"},
        "geometry": {"sensor_altitude_m": m.altitude_m},  # type: ignore[attr-defined]
        "optics": {
            "aperture_diameter_m": m.aperture_m,  # type: ignore[attr-defined]
            "focal_length_m": m.focal_length_m,  # type: ignore[attr-defined]
            "transmission_scalar": m.transmission,  # type: ignore[attr-defined]
            "optics_temperature_K": m.optics_temp_K,  # type: ignore[attr-defined]
        },
        "detector": {
            "pixel_pitch_x_um": p_um,
            "pixel_pitch_y_um": p_um,
            "qe_value": float(d["Quantum efficiency (in-band)"][idx]) / 100.0,
            "dark_rate_e_per_s": float(d["Dark current"][idx]),
            "detector_temperature_K": 77.0,
        },
        "spectral_integration": {
            "filter_min_um": m.band_min_um,  # type: ignore[attr-defined]
            "filter_max_um": m.band_max_um,  # type: ignore[attr-defined]
            "integration_time_s": float(d["Integration time (nom.)"][idx]) / 1000.0,
        },
        "readout": {
            "read_noise_e_rms": float(d["Read noise (CDS)"][idx]),
            "gain_e_per_dn": float(d["System gain"][idx]),
            "adc_bits": int(d["ADC resolution"][idx]),
            "full_well_capacity_e": float(d["Full well capacity"][idx]),
        },
    }
    return Sensor.from_dict(config)


def _build_8_1_nominal(m: object) -> Sensor:
    """Scenario 8.1 baseline = query off-nadir, portable SimpleAtmosphere.

    The runner's tape7/synthetic MODTRAN family is not portable; the nominal
    query point uses SimpleAtmosphere at the same us_standard profile.
    """
    config = {
        "source": {
            "scene_type": "extended",
            "target": {"temperature": 300.0, "emissivity": 0.95},
            "background": {"temperature": 288.0, "emissivity": 0.95},
        },
        "geometry": {
            "sensor_altitude_m": 100_000.0,
            "path_zenith_rad": math.radians(m.QUERY_ZENITH_DEG),  # type: ignore[attr-defined]
        },
        "optics": {
            "aperture_diameter_m": 0.30,
            "focal_length_m": 0.75,
            "transmission_scalar": 0.85,
        },
        "detector": {
            "pixel_pitch_x_um": 20.0,
            "pixel_pitch_y_um": 20.0,
            "qe_value": 0.70,
            "dark_rate_e_per_s": 1.0e4,
            "detector_temperature_K": 120.0,
        },
        "spectral_integration": {
            "filter_min_um": m.BAND_MIN_UM,  # type: ignore[attr-defined]
            "filter_max_um": m.BAND_MAX_UM,  # type: ignore[attr-defined]
            "integration_time_s": 5.0e-4,
        },
        "readout": {
            "read_noise_e_rms": 20.0,
            "gain_e_per_dn": 125.0,
            "adc_bits": 14,
            "full_well_capacity_e": 2.0e6,
        },
        "atmosphere": {"model": "simple", "standard_atmosphere": "us_standard"},
    }
    return Sensor.from_dict(config)


def _build_8_2_nominal(m: object) -> Sensor:
    """Scenario 8.2 baseline = LWIR chain, portable SimpleAtmosphere.

    The runner's target-altitude MODTRAN family is not portable; the nominal
    point uses SimpleAtmosphere at the family's midlat_summer profile.
    """
    config = {
        "source": {
            "scene_type": "extended",
            "target": {"temperature": 250.0, "emissivity": 0.95},
            "background": {"temperature": 220.0, "emissivity": 0.95},
        },
        "geometry": {"sensor_altitude_m": 35_000.0},
        "optics": {
            "aperture_diameter_m": 0.20,
            "focal_length_m": 0.60,
            "transmission_scalar": 0.80,
        },
        "detector": {
            "pixel_pitch_x_um": 25.0,
            "pixel_pitch_y_um": 25.0,
            "qe_value": 0.65,
            "dark_rate_e_per_s": 5.0e3,
            "detector_temperature_K": 77.0,
        },
        "spectral_integration": {
            "filter_min_um": m.BAND_MIN_UM,  # type: ignore[attr-defined]
            "filter_max_um": m.BAND_MAX_UM,  # type: ignore[attr-defined]
            "integration_time_s": 1.0e-4,
        },
        "readout": {
            "read_noise_e_rms": 25.0,
            "gain_e_per_dn": 200.0,
            "adc_bits": 14,
            "full_well_capacity_e": 3.0e6,
        },
        "atmosphere": {"model": "simple", "standard_atmosphere": "midlat_summer"},
    }
    return Sensor.from_dict(config)


# ---------------------------------------------------------------------------
# Registry.  One entry per scenario.  Grouped by persona folder.
# ---------------------------------------------------------------------------
REGISTRY: list[GuiScenario] = [
    # -- 01 Sarah — systems engineer ---------------------------------------
    GuiScenario(
        id="1.1",
        persona="01_sarah_systems_engineer",
        slug="1.1_mwir_maritime_surveillance",
        title="MWIR maritime surveillance — aperture trade (30 cm baseline)",
        build=runner_factory(
            "01_sarah_systems_engineer",
            "1.1_mwir_maritime_surveillance",
            "run_mwir_maritime_surveillance.py",
            lambda m: Sensor.from_dict(m.make_config(0.30, "simple")),
        ),
        notes=(
            "Baseline = 30 cm aperture, SimpleAtmosphere (maritime aerosol). "
            "The MODTRAN-D2 tape7 variant needs a staged file; the console "
            "script shows how to switch to it."
        ),
    ),
    GuiScenario(
        id="1.2",
        persona="01_sarah_systems_engineer",
        slug="1.2_vnir_gsd_aperture_altitude",
        title="VNIR GSD trade — 50 cm aperture, 500 km reference point",
        build=runner_factory(
            "01_sarah_systems_engineer",
            "1.2_vnir_gsd_aperture_altitude",
            "run_gsd_trade.py",
            lambda m: m.build_sensor(m.REF_APERTURE_M, m.REF_ALT_M, math.radians(40)),
        ),
        notes="Reference aperture/altitude; solar zenith 40 deg (representative daytime).",
    ),
    GuiScenario(
        id="1.3",
        persona="01_sarah_systems_engineer",
        slug="1.3_dual_band_mwir_lwir",
        title="Dual-band MWIR/LWIR — MWIR option at nominal hotspot T",
        build=runner_factory(
            "01_sarah_systems_engineer",
            "1.3_dual_band_mwir_lwir",
            "run_dual_band_trade.py",
            lambda m: m.build_sensor("MWIR", m.T_nominal),
        ),
        notes="MWIR band at the nominal hotspot temperature from the runner's spec sheet.",
    ),
    GuiScenario(
        id="1.4",
        persona="01_sarah_systems_engineer",
        slug="1.4_tdi_pushbroom_optimization",
        title="TDI pushbroom — baseline config (N_tdi=1 reference)",
        build=runner_factory(
            "01_sarah_systems_engineer",
            "1.4_tdi_pushbroom_optimization",
            "run_tdi_pushbroom_trade.py",
            lambda m: _recenter(
                Sensor.from_dict(m.base_config),
                {"performance.niirs.allow_extrapolated": True},
            ),
        ),
        notes=(
            "Runner's module-level base_config (nominal); the N_tdi sweep varies from here. "
            "NIIRS is the scenario's headline trade metric, so allow_extrapolated=true opts "
            "the baseline into the GIQE-5 rating past its SNR-calibration envelope (CU-166/CU-170)."
        ),
    ),
    GuiScenario(
        id="1.5",
        persona="01_sarah_systems_engineer",
        slug="1.5_obscured_aperture_spider_vanes",
        title="Obscured aperture — 30% obscuration, 4 spiders, 1 cm vanes",
        build=runner_factory(
            "01_sarah_systems_engineer",
            "1.5_obscured_aperture_spider_vanes",
            "run_obscured_aperture.py",
            lambda m: m.build_sensor(m.OBSCURATION, 4, 0.01),
        ),
        notes="Baseline central obscuration with a 4-vane spider (1 cm width).",
    ),
    # -- 02 Mike — detector engineer ---------------------------------------
    GuiScenario(
        id="2.1",
        persona="02_mike_detector_engineer",
        slug="2.1_insb_vs_hgcdte_noise_budget",
        title="Detector shootout — InSb baseline",
        build=runner_factory(
            "02_mike_detector_engineer",
            "2.1_insb_vs_hgcdte_noise_budget",
            "run_detector_shootout.py",
            lambda m: Sensor.from_dict(m.build_config("InSb")),
        ),
        notes="InSb option; the HgCdTe variant is the other build_config branch.",
    ),
    GuiScenario(
        id="2.2",
        persona="02_mike_detector_engineer",
        slug="2.2_1f_noise_corner_frequency",
        title="1/f noise vs frame rate — nominal config",
        build=runner_factory(
            "02_mike_detector_engineer",
            "2.2_1f_noise_corner_frequency",
            "run_1f_noise_vs_frame_rate.py",
            lambda m: Sensor.from_dict(m.make_config()),
        ),
        notes="Runner's default make_config (no flicker); the sweep varies frame rate.",
    ),
    GuiScenario(
        id="2.3",
        persona="02_mike_detector_engineer",
        slug="2.3_ipc_impact_on_mtf",
        title="IPC impact on MTF — 2% IPC baseline",
        build=runner_factory(
            "02_mike_detector_engineer",
            "2.3_ipc_impact_on_mtf",
            "run_ipc_sweep.py",
            lambda m: _recenter(
                Sensor.from_dict(m.make_ipc_config(0.02)),
                {"readout.gain_e_per_dn": 110.0},
            ),
        ),
        notes=(
            "Nominal 2% inter-pixel capacitance fraction. GUI baseline uses a well-matched "
            "gain (110 e-/DN vs the runner's 1.2) so the 14-bit ADC spans the 1.8 Me- well "
            "instead of clipping the signal (CU-170)."
        ),
    ),
    GuiScenario(
        id="2.5",
        persona="02_mike_detector_engineer",
        slug="2.5_well_capacity_optimization",
        title="Well-capacity trade — 300 K scene, 1 ms integration",
        build=runner_factory(
            "02_mike_detector_engineer",
            "2.5_well_capacity_optimization",
            "run_well_capacity_trade.py",
            # COMPARE_T_INT (0.001 s) is defined below the runner's analysis, so
            # the hermetic halt never binds it — pass the literal.
            lambda m: Sensor.from_dict(m.make_config(300.0, 0.001)),
        ),
        notes="Nominal 300 K scene temperature at the 1 ms comparison integration time.",
    ),
    # -- 03 Raj — mission planner ------------------------------------------
    GuiScenario(
        id="3.1",
        persona="03_raj_mission_planner",
        slug="3.1_isr_pass_planning",
        title="ISR pass planning — 30 deg off-nadir baseline",
        build=runner_factory(
            "03_raj_mission_planner",
            "3.1_isr_pass_planning",
            "run_pass_planning.py",
            lambda m: m.build_sensor(30.0),
        ),
        notes="Nominal 30 deg off-nadir look.",
    ),
    GuiScenario(
        id="3.2",
        persona="03_raj_mission_planner",
        slug="3.2_weather_sensitivity",
        title="Weather sensitivity — baseline clear atmosphere",
        build=runner_factory(
            "03_raj_mission_planner",
            "3.2_weather_sensitivity",
            "run_weather_sensitivity.py",
            lambda m: _recenter(
                Sensor.from_dict(m.make_config(m.baseline_vis_km, m.baseline_pwv_cm)),
                {"performance.niirs.allow_extrapolated": True},
            ),
        ),
        notes=(
            "Runner's baseline visibility and precipitable-water values. NIIRS-vs-weather is "
            "the scenario's headline, so allow_extrapolated=true opts the baseline into the "
            "GIQE-5 rating past its SNR-calibration envelope (CU-166/CU-170)."
        ),
    ),
    GuiScenario(
        id="3.3",
        persona="03_raj_mission_planner",
        slug="3.3_multi_sensor_comparison",
        title="Multi-sensor comparison — Vendor A baseline",
        build=runner_factory(
            "03_raj_mission_planner",
            "3.3_multi_sensor_comparison",
            "run_sensor_comparison.py",
            lambda m: _recenter(
                _build_3_3_vendor_a(m),
                {
                    "readout.gain_e_per_dn": 400.0,
                    "performance.niirs.allow_extrapolated": True,
                },
            ),
        ),
        notes=(
            "Vendor A of the three-vendor comparison (transcribes evaluate_vendor). GUI "
            "baseline uses a well-matched gain (400 e-/DN vs Vendor A's 20) so the 14-bit ADC "
            "spans the 6 Me- well at the 8 ms point instead of clipping; NIIRS is a per-vendor "
            "comparison column, so allow_extrapolated=true keeps the rating (CU-170/CU-166)."
        ),
    ),
    GuiScenario(
        id="3.4",
        persona="03_raj_mission_planner",
        slug="3.4_off_nadir_agility",
        title="Off-nadir agility — nadir baseline config",
        build=runner_factory(
            "03_raj_mission_planner",
            "3.4_off_nadir_agility",
            "run_off_nadir_agility.py",
            lambda m: _recenter(
                Sensor.from_dict(m.base_config),
                {"performance.niirs.allow_extrapolated": True},
            ),
        ),
        notes=(
            "Runner's module-level base_config (nadir); the sweep varies path zenith. NIIRS-vs-"
            "off-nadir is the headline trade, so allow_extrapolated=true opts the baseline into "
            "the GIQE-5 rating past its SNR-calibration envelope (CU-166/CU-170)."
        ),
    ),
    GuiScenario(
        id="3.5",
        persona="03_raj_mission_planner",
        slug="3.5_nighttime_mwir_feasibility",
        title="Nighttime MWIR feasibility — MWIR thermal-emission pixel",
        build=runner_factory(
            "03_raj_mission_planner",
            "3.5_nighttime_mwir_feasibility",
            "run_nighttime_feasibility.py",
            lambda m: _recenter(
                m.build(m.BANDS["MWIR"], m.T_TARGET_K, m.E_TARGET, m.T_BG_K),
                {"readout.gain_e_per_dn": 160.0},
            ),
        ),
        notes=(
            "MWIR band, nominal target/background thermal temperatures. The 0.2 ms / 1e7 e- "
            "well is deliberately sized so neither band saturates (well OK); the GUI baseline "
            "adds a well-matched gain (160 e-/DN) so the 16-bit ADC no longer clips (CU-170)."
        ),
    ),
    # -- 04 Lisa — analyst --------------------------------------------------
    GuiScenario(
        id="4.1",
        persona="04_lisa_analyst",
        slug="4.1_target_detection_matrix",
        title="Target detection matrix — Sensor A (MWIR smallsat)",
        build=lambda: _recenter(
            Sensor.from_yaml(
                SCENARIOS
                / "04_lisa_analyst"
                / "4.1_target_detection_matrix"
                / "inputs"
                / "sensor_a_mwir_smallsat.yaml"
            ),
            {
                "spectral_integration.integration_time_s": 0.0015,
                "readout.gain_e_per_dn": 48.0,
            },
        ),
        notes=(
            "Reuses the committed sensor_a_mwir_smallsat.yaml (this scenario ships YAML). GUI "
            "baseline shortens integration to 1.5 ms (well ~47% vs 1.26x over-full at the "
            "runner's 4 ms) and uses a well-matched gain (48 e-/DN) so neither the 0.8 Me- well "
            "nor the 14-bit ADC clips. The committed sensor YAML + the scenario's figures are "
            "left untouched (the detection verdict is clutter-limited SCNR, not well-limited), "
            "so only the GUI baseline is re-centered (CU-170)."
        ),
    ),
    GuiScenario(
        id="4.3",
        persona="04_lisa_analyst",
        slug="4.3_camouflage_effectiveness",
        title="Camouflage effectiveness — bare vehicle, LWIR FLIR at nadir",
        build=runner_factory(
            "04_lisa_analyst",
            "4.3_camouflage_effectiveness",
            "run_camouflage_analysis.py",
            # The per-material radiance CSVs live in the (gitignored) outputs/
            # derived/ tree; ``radiance_csv`` reads one on demand and says how to
            # regenerate them if the runner has never been run here (CU-164). The
            # bare-vehicle case at nadir over the full 8-12 um LWIR band is the
            # reference the camo options compare against.
            lambda m: m.build_sensor(m.radiance_csv("Bare vehicle"), 8.0, 12.0, 0.0),
        ),
        metrics=("snr", "contrast_snr", "nedt_K"),
        notes=(
            "Bare oxidized-steel vehicle vs scrub, LWIR FLIR at nadir. The YAML "
            "references a derived radiance CSV; run the runner once to generate it "
            "before re-emitting this baseline (CU-164)."
        ),
    ),
    GuiScenario(
        id="4.4",
        persona="04_lisa_analyst",
        slug="4.4_time_of_day_analysis",
        title="Time-of-day analysis — 300 K, emissivity 0.9 pixel",
        build=runner_factory(
            "04_lisa_analyst",
            "4.4_time_of_day_analysis",
            "run_diurnal_analysis.py",
            lambda m: _recenter(
                m.build_pixel(300.0, 0.9),
                {"readout.gain_e_per_dn": 400.0},
            ),
        ),
        notes=(
            "Nominal 300 K surface, emissivity 0.9. The 0.1 ms integration keeps the well "
            "~43% full (linear contrast); the GUI baseline adds a well-matched gain "
            "(400 e-/DN) so the 14-bit ADC spans the 6 Me- well instead of clipping (CU-170)."
        ),
    ),
    GuiScenario(
        id="4.5",
        persona="04_lisa_analyst",
        slug="4.5_altitude_trade_uav",
        title="UAV altitude trade — 2000 m reference altitude",
        build=runner_factory(
            "04_lisa_analyst",
            "4.5_altitude_trade_uav",
            "run_uav_altitude_trade.py",
            lambda m: m.build_sensor(2000.0),
        ),
        notes=(
            "Runner's reference altitude (2 km). NOT re-centered: the 16 ms frame is the "
            "microbolometer's thermal time constant (NETD is quoted at it) and cannot move, "
            "while the photon-model signal (~5.5e9 e-) is 55x the schema's max full well — so "
            "the well/ADC saturation warning is a photon-FPA check misapplied to a bolometer, "
            "not a re-centerable operating point. See Gap 101; the scenario's real metric is "
            "the delta-T-vs-NETD detection threshold, which is unaffected (CU-170)."
        ),
    ),
    # -- 05 Tom — optical designer -----------------------------------------
    GuiScenario(
        id="5.1",
        persona="05_tom_optical_designer",
        slug="5.1_wfe_budget_allocation",
        title="WFE budget — nominal base config",
        build=runner_factory(
            "05_tom_optical_designer",
            "5.1_wfe_budget_allocation",
            "run_wfe_budget_trade.py",
            lambda m: _recenter(
                Sensor.from_dict(m.base_config),
                {"performance.niirs.allow_extrapolated": True},
            ),
        ),
        notes=(
            "Runner's module-level base_config; the sweep varies WFE RMS. NIIRS-vs-WFE is the "
            "headline budget metric, so allow_extrapolated=true opts the baseline into the "
            "GIQE-5 rating past its SNR-calibration envelope (CU-166/CU-170)."
        ),
    ),
    GuiScenario(
        id="5.2",
        persona="05_tom_optical_designer",
        slug="5.2_pixel_pitch_optimization",
        title="Pixel-pitch sweep — mid pixel-pitch baseline",
        build=runner_factory(
            "05_tom_optical_designer",
            "5.2_pixel_pitch_optimization",
            "run_pixel_pitch_sweep.py",
            lambda m: _recenter(
                _build_5_2_nominal(m),
                {
                    "spectral_integration.integration_time_s": 0.001,
                    "readout.gain_e_per_dn": 32.0,
                },
            ),
        ),
        notes=(
            "Middle pixel-pitch row of the sweep (transcribes the loop body). GUI baseline "
            "shortens integration to 1 ms (well ~52% vs clipping at the runner's 2 ms) and "
            "uses a well-matched gain (32 e-/DN) so the 14-bit ADC no longer clips (CU-170)."
        ),
    ),
    GuiScenario(
        id="5.3",
        persona="05_tom_optical_designer",
        slug="5.3_mono_vs_poly_psf",
        title="Chromatic PSF — monochromatic baseline (single wavelength)",
        build=runner_factory(
            "05_tom_optical_designer",
            "5.3_mono_vs_poly_psf",
            "run_chromatic_psf_comparison.py",
            lambda m: _recenter(
                Sensor.from_dict(m.make_config(m.band_min_um, m.band_max_um, 1)),
                {
                    "spectral_integration.integration_time_s": 0.001,
                    "readout.gain_e_per_dn": 32.0,
                },
            ),
        ),
        notes=(
            "Single-wavelength (mono) PSF baseline; poly variant raises psf_n_wavelengths. GUI "
            "baseline shortens integration to 1 ms (well ~52%) and uses a well-matched gain "
            "(32 e-/DN) so the 14-bit ADC no longer clips at the runner's 2 ms point (CU-170)."
        ),
    ),
    GuiScenario(
        id="5.4",
        persona="05_tom_optical_designer",
        slug="5.4_jitter_induced_blur",
        title="Jitter tolerance — nominal base config",
        build=runner_factory(
            "05_tom_optical_designer",
            "5.4_jitter_induced_blur",
            "run_jitter_tolerance.py",
            lambda m: Sensor.from_dict(m.base_config),
        ),
        notes="Runner's module-level base_config; the sweep varies jitter RMS.",
    ),
    GuiScenario(
        id="5.5",
        persona="05_tom_optical_designer",
        slug="5.5_stray_light_veiling_glare",
        title="Stray light — clean (no veiling glare) baseline",
        build=runner_factory(
            "05_tom_optical_designer",
            "5.5_stray_light_veiling_glare",
            "run_straylight_analysis.py",
            lambda m: _recenter(
                m.build(m.RHO_TARGET),
                {
                    "spectral_integration.integration_time_s": 0.001,
                    "readout.gain_e_per_dn": 8.0,
                },
            ),
        ),
        notes=(
            "Rooftop target reflectance, zero veiling-glare (clean reference). GUI baseline "
            "shortens integration to 1 ms (well ~75% vs 3.75x over-full at the runner's 5 ms) "
            "and uses a well-matched gain (8 e-/DN) so neither the 0.3 Me- well nor the 16-bit "
            "ADC clips (CU-170). NIIRS stays absent — the extrapolated rating (>11 at SNR ~470) "
            "is outside any physical NIIRS range, so it is not opted in (CU-166)."
        ),
    ),
    # -- 06 Dr Chen — researcher -------------------------------------------
    GuiScenario(
        id="6.1",
        persona="06_dr_chen_researcher",
        slug="6.1_published_snr_benchmark",
        title="Published SNR benchmark — datasheet sensor",
        build=runner_factory(
            "06_dr_chen_researcher",
            "6.1_published_snr_benchmark",
            "run_datasheet_benchmark.py",
            lambda m: _recenter(
                m.build_sensor(),
                {"readout.gain_e_per_dn": 640.0},
            ),
        ),
        notes=(
            "Fixed datasheet-benchmark configuration. The 30 us integration is chosen to stay "
            "unsaturated on the intense LWIR flux (well ~61%); the GUI baseline adds a "
            "well-matched gain (640 e-/DN) so the 14-bit ADC spans the 1e7 e- well instead of "
            "clipping (CU-170)."
        ),
    ),
    GuiScenario(
        id="6.2",
        persona="06_dr_chen_researcher",
        slug="6.2_atmospheric_intercomparison",
        title="Atmospheric intercomparison — US Standard, SimpleAtmosphere",
        build=runner_factory(
            "06_dr_chen_researcher",
            "6.2_atmospheric_intercomparison",
            "run_atmospheric_intercomparison.py",
            lambda m: Sensor.from_dict(m._make_config("simple", "us_standard", None)),
        ),
        notes="SimpleAtmosphere at us_standard; the MODTRAN tape7 arm needs staged files.",
    ),
    GuiScenario(
        id="6.3",
        persona="06_dr_chen_researcher",
        slug="6.3_noise_model_verification",
        title="Noise-model verification — reference sensor",
        build=runner_factory(
            "06_dr_chen_researcher",
            "6.3_noise_model_verification",
            "run_verification.py",
            lambda m: _recenter(
                m.sensor,
                {"readout.adc_bits": 21},
            ),
        ),
        notes=(
            "Runner's module-level verification sensor. GUI baseline widens the ADC to 21 bits "
            "(from 14) so the bright MWIR signal (~1.6 Me-) fits the ADC range instead of "
            "clipping; gain stays 1.0 e-/DN, so every verified noise term — quantization = "
            "gain/sqrt(12) = 0.289 e- included — is bit-identical to the runner (CU-170)."
        ),
    ),
    GuiScenario(
        id="6.4",
        persona="06_dr_chen_researcher",
        slug="6.4_synthetic_scene_generation",
        title="Synthetic scene — first target pixel baseline",
        build=runner_factory(
            "06_dr_chen_researcher",
            "6.4_synthetic_scene_generation",
            "run_synthetic_scene.py",
            lambda m: m.build(m.TARGETS[0][2], m.TARGETS[0][3], m.TARGETS[0][1] * 1e3),
        ),
        notes="First scene target (temperature, emissivity, range->altitude).",
    ),
    # -- 07 Karen — test engineer ------------------------------------------
    GuiScenario(
        id="7.1",
        persona="07_karen_test_engineer",
        slug="7.1_nedt_reconciliation",
        title="NEDT reconciliation — primary target temperature",
        build=runner_factory(
            "07_karen_test_engineer",
            "7.1_nedt_reconciliation",
            "run_nedt_reconciliation.py",
            # T_primary (298.15 K) is defined below the runner's analysis, so the
            # hermetic halt never binds it — pass the literal.
            lambda m: Sensor.from_dict(m.make_config(298.15)),
        ),
        notes="Nominal (primary) target temperature 298.15 K (25 C).",
    ),
    GuiScenario(
        id="7.2",
        persona="07_karen_test_engineer",
        slug="7.2_radiometric_calibration",
        title="Radiometric calibration — as-built sensor",
        build=runner_factory(
            "07_karen_test_engineer",
            "7.2_radiometric_calibration",
            "run_radiometric_calibration.py",
            lambda m: m.sensor,
        ),
        notes="Runner's module-level as-built sensor; the sweep varies blackbody T.",
    ),
    GuiScenario(
        id="7.3",
        persona="07_karen_test_engineer",
        slug="7.3_mtf_measurement_vs_prediction",
        title="MTF measurement vs prediction — nominal config",
        build=runner_factory(
            "07_karen_test_engineer",
            "7.3_mtf_measurement_vs_prediction",
            "run_mtf_measurement_vs_prediction.py",
            lambda m: Sensor.from_dict(m.config),
        ),
        # This is an MTF lab bench: a VNIR band with a 300 K thermal-only source
        # emits ~no in-band photons, so SNR/NEDT are meaningless by design. The
        # scenario's real headline is the MTF/spatial metrics — snapshot those.
        metrics=("mtf_at_nyquist", "rer", "strehl", "fwhm_x_m"),
        notes="MTF bench (VNIR, thermal source) — SNR is ~0 by design; MTF is the metric.",
    ),
    GuiScenario(
        id="7.4",
        persona="07_karen_test_engineer",
        slug="7.4_cold_stop_sweep",
        title="Cold-stop sweep — baseline (unshuttered) config",
        build=runner_factory(
            "07_karen_test_engineer",
            "7.4_cold_stop_sweep",
            "run_cold_stop_sweep.py",
            lambda m: _recenter(
                Sensor.from_dict(m.config),
                {"readout.gain_e_per_dn": 512.0},
            ),
        ),
        notes=(
            "Runner's module-level baseline config; the sweep varies cold-stop f-number. GUI "
            "baseline uses a well-matched gain (512 e-/DN vs the runner's 2.5) so the 14-bit "
            "ADC spans the 8.5 Me- well instead of clipping (CU-170)."
        ),
    ),
    GuiScenario(
        id="7.5",
        persona="07_karen_test_engineer",
        slug="7.5_environmental_temp_extremes",
        title="Environmental extremes — 77 K nominal detector",
        build=runner_factory(
            "07_karen_test_engineer",
            "7.5_environmental_temp_extremes",
            "run_environmental_test.py",
            lambda m: m.build_sensor(77.0, 5e4, 0.78),
        ),
        notes="Nominal 77 K detector (dark 5e4 e-/s, QE 0.78).",
    ),
    # -- 08 Interpolation demonstrations -----------------------------------
    GuiScenario(
        id="8.1",
        persona="08_interpolation_demonstrations",
        slug="8.1_off_nadir_angle_interpolation",
        title="Off-nadir interpolation — query angle, SimpleAtmosphere",
        build=runner_factory(
            "08_interpolation_demonstrations",
            "8.1_off_nadir_angle_interpolation",
            "run_off_nadir_interpolation.py",
            _build_8_1_nominal,
        ),
        notes="Query off-nadir angle; SimpleAtmosphere (tape7 family not portable).",
    ),
    GuiScenario(
        id="8.2",
        persona="08_interpolation_demonstrations",
        slug="8.2_target_altitude_interpolation",
        title="Target-altitude interpolation — LWIR, SimpleAtmosphere",
        build=runner_factory(
            "08_interpolation_demonstrations",
            "8.2_target_altitude_interpolation",
            "run_target_altitude_interpolation.py",
            _build_8_2_nominal,
        ),
        notes="Nominal LWIR chain; SimpleAtmosphere (tape7 family not portable).",
    ),
    # ------------------------------------------------------------------
    # 10 — direction-general validation (Geometry-Flexibility Phase 5).
    # One scenario per newly-opened ADR-0011 scene class. The ground-projection
    # metric family (GSD/NIIRS/...) is OFF by default for these non-ground-target
    # classes (scene relevance, G3), so the snapshot metrics are the ones the
    # class actually computes.
    # ------------------------------------------------------------------
    GuiScenario(
        id="10.1",
        persona="10_direction_general",
        slug="10.1_ground_to_air_mwir_detection",
        title="Ground-to-air MWIR detection — up-looking, sky background",
        build=runner_factory(
            "10_direction_general",
            "10.1_ground_to_air_mwir_detection",
            "run_ground_to_air_mwir_detection.py",
            lambda m: m.make_sensor(),  # type: ignore[attr-defined]
        ),
        metrics=("snr", "contrast_snr", "nedt_K"),
        stage_scalars=("geometry.theta_o_rad", "geometry.slant_range_m"),
        sweep=("geometry.path_zenith_rad", "Lower-endpoint zenith ζ_low", "deg"),
        notes="scene_class ground_to_air; los_direction up; SkyBackground behind the target.",
    ),
    GuiScenario(
        id="10.2",
        persona="10_direction_general",
        slug="10.2_air_to_air_level_irst",
        title="Air-to-air level IRST — horizontal arm, target kinematics",
        build=runner_factory(
            "10_direction_general",
            "10.2_air_to_air_level_irst",
            "run_air_to_air_level_irst.py",
            lambda m: m.make_sensor(),  # type: ignore[attr-defined]
        ),
        metrics=("snr", "contrast_snr", "detection_range_m"),
        stage_scalars=("geometry.theta_o_rad", "geometry.slant_range_m"),
        sweep=("geometry.target_range_m", "Level-arm slant range", "km"),
        notes="scene_class air_to_air; los_direction level; Δh sag pill on the schematic.",
    ),
    GuiScenario(
        id="10.3",
        persona="10_direction_general",
        slug="10.3_ground_to_space_sst_visible",
        title="Ground-to-space SST — visible, seeing-limited, full column",
        build=runner_factory(
            "10_direction_general",
            "10.3_ground_to_space_sst_visible",
            "run_ground_to_space_sst_visible.py",
            lambda m: m.make_sensor(),  # type: ignore[attr-defined]
        ),
        metrics=("snr", "contrast_snr", "mtf_at_nyquist"),
        stage_scalars=("geometry.theta_o_rad", "geometry.slant_range_m"),
        sweep=("geometry.path_zenith_rad", "Telescope zenith ζ_low", "deg"),
        notes="scene_class ground_to_space; HV-5/7 turbulence; MODTRAN anchor deferred (batch 2).",
    ),
    GuiScenario(
        id="10.4",
        persona="10_direction_general",
        slug="10.4_leo_to_geo_exo",
        title="LEO→GEO exo SDA — θ_o = π, vacuum path",
        build=runner_factory(
            "10_direction_general",
            "10.4_leo_to_geo_exo",
            "run_leo_to_geo_exo.py",
            lambda m: m.make_sensor(),  # type: ignore[attr-defined]
        ),
        metrics=("snr", "contrast_snr", "detection_range_m"),
        stage_scalars=("geometry.theta_o_rad", "geometry.slant_range_m"),
        sweep=("spectral_integration.integration_time_s", "Integration time", "ms"),
        notes="scene_class space_to_space; wholly-vacuum up-looking path (τ = 1 exact).",
    ),
]

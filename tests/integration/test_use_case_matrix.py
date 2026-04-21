"""90-cell parametric coverage sweep of the RADIANT use-case matrix.

This is the Stage 8 integration coverage test for Option C:
``docs/RADIANT_Use_Case_Matrix.md`` §3.2 (60 primary cells) plus §3.3
(30 no_atmosphere sub-case cells) = 90 cells total.

For each cell, the test either:

* **PASS** — Construct a representative scenario and run the relevant
  pipeline (full :class:`RadiantSession` chain for cells the legacy
  inferrer can reach, or an ``_InjectedSource`` harness for cells
  requiring T5 / UserSpectralBackground).  Assert that the chain
  completes end-to-end and at-aperture spectral radiance is finite.

* **RAISE** — Cells marked invalid per matrix §7 (all at_aperture ×
  {sub_pixel, point_source}) must raise :class:`ParameterBoundsError`
  at descriptor construction.

* **XFAIL** — Cells that are genuinely deferred for an architectural
  reason (e.g. require a parameter surface that doesn't yet exist).

Emits a JSON coverage report (``_use_case_coverage.json``) after the
sweep so downstream documentation (``docs/Use_Case_gaps.md``) can be
updated by comparing test-run outputs directly.

The test is parametrized per-cell so failures are isolated — one cell
failing does not blank out the rest of the sweep.

Reference: ``docs/Option_C_Implementation_Plan.md`` Stage 8.
"""

from __future__ import annotations

import json
import math
import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np
import pytest

from radiant.api._param_registry import build_parameter_set
from radiant.api.session import RadiantSession
from radiant.atmosphere.stage import AtmosphereStage
from radiant.core.chain import ChainRunner, ChainState
from radiant.core.descriptors import (
    AtApertureBackground,
    ColdSpaceBackground,
    T1Thermal,
    T5AtAperture,
    UserSpectralBackground,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.regime import RadiometricRegime
from radiant.core.spectral import SpectralData
from radiant.detector.stage import DetectorStage
from radiant.optics.stage import OpticsStage
from radiant.performance.stage import PerformanceStage
from radiant.platform.stage import PlatformStage
from radiant.readout.stage import ReadoutStage
from radiant.spectral_integration.stage import SpectralIntegrationStage


# ---------------------------------------------------------------------------
# Regime-specific grids and defaults
# ---------------------------------------------------------------------------


# Per-regime wavelength grid (coarse enough to run fast, fine enough to
# make Planck well-behaved).  Each grid aligns with the matrix §1.2 bands.
_REGIME_GRIDS: dict[str, np.ndarray] = {
    "VIS": np.linspace(0.4, 0.7, 31),
    "NIR": np.linspace(0.7, 1.0, 31),
    "SWIR": np.linspace(1.0, 2.5, 61),
    "MWIR": np.linspace(3.0, 5.0, 41),
    "LWIR": np.linspace(8.0, 13.0, 51),
}


# Per-regime sensible target temperature defaults (chosen so the T1Thermal
# legacy inferrer produces a non-zero signal in bands where thermal emission
# dominates; near-zero in VIS/NIR is acceptable — we only require the chain
# to run end-to-end).
_REGIME_TARGET_K: dict[str, float] = {
    "VIS": 300.0,
    "NIR": 300.0,
    "SWIR": 400.0,      # warm enough to have SWIR thermal tail (and stay <700K so SWIR warning doesn't fire)
    "MWIR": 320.0,
    "LWIR": 300.0,
}


# ---------------------------------------------------------------------------
# Helpers — shared scenario plumbing
# ---------------------------------------------------------------------------


def _grey_sd(wl: np.ndarray, value: float, name: str = "eps") -> SpectralData:
    return SpectralData(
        name=name,
        wavelength_um=np.asarray(wl, dtype=np.float64),
        values=np.full_like(wl, value, dtype=np.float64),
        unit="",
        source="test_use_case_matrix",
    )


def _user_lbg_sd(wl: np.ndarray, L_value: float) -> SpectralData:
    return SpectralData(
        name="test.user_L_bg",
        wavelength_um=np.asarray(wl, dtype=np.float64),
        values=np.full_like(wl, L_value, dtype=np.float64),
        unit="W/m²/sr/µm",
        source="test_use_case_matrix",
    )


def _at_aperture_radiance_sd(wl: np.ndarray, L_value: float) -> SpectralData:
    return SpectralData(
        name="test.user_L_t_aperture",
        wavelength_um=np.asarray(wl, dtype=np.float64),
        values=np.full_like(wl, L_value, dtype=np.float64),
        unit="W/m²/sr/µm",
        source="test_use_case_matrix",
    )


def _seed_optics_detector_readout(params: ParameterSet, regime: str) -> None:
    """Seed a minimal imaging system appropriate for the given regime."""
    # Pixel pitch and filter bounds are regime-specific so the optical and
    # spectral stages receive sensible inputs.
    if regime in ("VIS", "NIR"):
        pixel_pitch_um = 5.0
        read_noise_e = 5.0
        qe = 0.85
        dark_rate = 50.0
        t_int = 0.002
    elif regime == "SWIR":
        pixel_pitch_um = 15.0
        read_noise_e = 20.0
        qe = 0.70
        dark_rate = 500.0
        t_int = 0.005
    elif regime == "MWIR":
        pixel_pitch_um = 18.0
        read_noise_e = 20.0
        qe = 0.60
        dark_rate = 800.0
        t_int = 0.008
    else:  # LWIR
        pixel_pitch_um = 20.0
        read_noise_e = 12.0
        qe = 0.55
        dark_rate = 800.0
        t_int = 0.010

    wl = _REGIME_GRIDS[regime]
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.45)
    params.set("optics.transmission_scalar", 0.62)
    params.set("detector.pixel_pitch_x_um", pixel_pitch_um)
    params.set("detector.pixel_pitch_y_um", pixel_pitch_um)
    params.set("detector.qe_value", qe)
    params.set("detector.dark_rate_e_per_s", dark_rate)
    params.set("spectral_integration.filter_min_um", float(wl[0]))
    params.set("spectral_integration.filter_max_um", float(wl[-1]))
    params.set("spectral_integration.integration_time_s", t_int)
    params.set("readout.read_noise_e_rms", read_noise_e)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)


# ---------------------------------------------------------------------------
# Injected-source harness for cells the legacy inferrer cannot synthesize
# ---------------------------------------------------------------------------


class _InjectedSource:
    """Stand-in SourceStage that injects pre-built descriptors into
    ``stage_outputs["source"]`` instead of running the legacy inferrer.

    Used for cells that the legacy inferrer cannot construct:

    * at_aperture × extended (requires T5AtAperture + AtApertureBackground)
    * no_atmosphere × ground_test / lab_test (requires UserSpectralBackground)

    Mirrors the keys SourceStage publishes, so every downstream stage
    (AtmosphereStage onward) runs unmodified.
    """

    def __init__(
        self,
        target: Any,
        background: Any,
        los: LineOfSightGeometry | None,
        regime_tentative: RadiometricRegime = RadiometricRegime.EXTENDED,
        angular_extent_rad: float = float("inf"),
        fill_fraction: float = 1.0,
        projected_area_m2: float = 0.0,
        range_m: float = 0.0,
    ) -> None:
        self._target = target
        self._background = background
        self._los = los
        self._regime = regime_tentative
        self._angular = angular_extent_rad
        self._fill = fill_fraction
        self._area = projected_area_m2
        self._range = range_m

    @property
    def name(self) -> str:
        return "source"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        state = state.with_stage_output("source", "regime_tentative", self._regime)
        state = state.with_stage_output("source", "projected_area_m2", self._area)
        state = state.with_stage_output("source", "range_m", self._range)
        state = state.with_stage_output("source", "fill_fraction", self._fill)
        state = state.with_stage_output("source", "angular_extent_rad", self._angular)
        state = state.with_stage_output("source", "regime_override", "auto")
        state = state.with_stage_output("source", "target", self._target)
        state = state.with_stage_output("source", "background", self._background)
        return state.with_stage_output("source", "los_geometry", self._los)


def _run_injected_chain(
    target: Any,
    background: Any,
    los: LineOfSightGeometry | None,
    params: ParameterSet,
    wl: np.ndarray,
) -> ChainState:
    """Run the downstream chain with ``_InjectedSource`` in place of SourceStage."""
    runner = ChainRunner([
        _InjectedSource(target, background, los),
        AtmosphereStage(),
        OpticsStage(),
        PlatformStage(),
        SpectralIntegrationStage(),
        DetectorStage(),
        ReadoutStage(),
        PerformanceStage(),
    ])
    return runner.run(params, wl)


# ---------------------------------------------------------------------------
# Cell specification and expected outcomes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CellSpec:
    """Describes one matrix cell and how the test should handle it."""

    cell_id: str                      # e.g. "1", "28", "G13", "L1"
    location: str                     # at_aperture | terrestrial | airborne | no_atm_space | ground_test | lab_test
    regime: str                       # VIS | NIR | SWIR | MWIR | LWIR
    scene_type: str                   # extended | sub_pixel | point_source
    outcome: str                      # "pass" | "raise" | "xfail"
    notes: str = ""


def _build_primary_cells() -> list[CellSpec]:
    """Enumerate the 60 primary cells from matrix §3.2 Tables A–D.

    Each location table is 15 cells = 5 regimes × 3 scene_types, in the
    same row order as the matrix (VIS/NIR/SWIR/MWIR/LWIR, each with
    extended/sub_pixel/point_source).
    """
    regimes = ("VIS", "NIR", "SWIR", "MWIR", "LWIR")
    scene_types = ("extended", "sub_pixel", "point_source")

    cells: list[CellSpec] = []
    cell_num = 1

    for location, tag in (
        ("at_aperture", "A"),
        ("terrestrial", "B"),
        ("airborne", "C"),
        ("no_atm_space", "D"),
    ):
        for regime in regimes:
            for scene_type in scene_types:
                # Matrix §7: at_aperture is extended-only.  All other scene
                # types at_aperture must raise.
                if location == "at_aperture" and scene_type != "extended":
                    outcome = "raise"
                    notes = "at_aperture requires extended (matrix §7)"
                else:
                    outcome = "pass"
                    notes = ""
                cells.append(
                    CellSpec(
                        cell_id=str(cell_num),
                        location=location,
                        regime=regime,
                        scene_type=scene_type,
                        outcome=outcome,
                        notes=notes,
                    )
                )
                cell_num += 1
    return cells


def _build_subcase_cells() -> list[CellSpec]:
    """Enumerate the 30 sub-case cells: D-ground G1..G15 and D-lab L1..L15."""
    regimes = ("VIS", "NIR", "SWIR", "MWIR", "LWIR")
    scene_types = ("extended", "sub_pixel", "point_source")
    cells: list[CellSpec] = []
    for prefix, location in (("G", "ground_test"), ("L", "lab_test")):
        idx = 1
        for regime in regimes:
            for scene_type in scene_types:
                cells.append(
                    CellSpec(
                        cell_id=f"{prefix}{idx}",
                        location=location,
                        regime=regime,
                        scene_type=scene_type,
                        outcome="pass",
                        notes="",
                    )
                )
                idx += 1
    return cells


ALL_CELLS: tuple[CellSpec, ...] = tuple(_build_primary_cells() + _build_subcase_cells())


# ---------------------------------------------------------------------------
# Coverage JSON aggregation
# ---------------------------------------------------------------------------


_COVERAGE_PATH = Path(__file__).parent / "_use_case_coverage.json"
_COVERAGE_RESULTS: dict[str, str] = {}


def _record_result(cell_id: str, outcome: str) -> None:
    """Record a per-cell outcome; the session finalizer writes JSON."""
    _COVERAGE_RESULTS[cell_id] = outcome


@pytest.fixture(scope="session", autouse=True)
def _write_coverage_report_at_end() -> Iterable[None]:
    """Session-scoped finalizer: write ``_use_case_coverage.json`` after the run."""
    yield
    # Only write if we actually ran at least one cell (test filtering may
    # leave the dict empty, in which case there's nothing meaningful to write).
    if not _COVERAGE_RESULTS:
        return
    # Preserve ordering by cell_id (natural matrix order) as best we can.
    expected_order = [c.cell_id for c in ALL_CELLS]
    ordered: dict[str, str] = {}
    for cid in expected_order:
        if cid in _COVERAGE_RESULTS:
            ordered[cid] = _COVERAGE_RESULTS[cid]
    # Any unexpected IDs appended at the end.
    for cid, out in _COVERAGE_RESULTS.items():
        if cid not in ordered:
            ordered[cid] = out
    _COVERAGE_PATH.write_text(json.dumps(ordered, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Scenario execution per cell
# ---------------------------------------------------------------------------


def _run_terrestrial_or_airborne_cell(cell: CellSpec) -> None:
    """Run a terrestrial / airborne cell through the full RadiantSession.

    The legacy inferrer synthesises a T1Thermal target from scalar (ε, T)
    plus a GroundBackground placeholder for sub_pixel / point_source
    scenes.  For VIS/NIR cells the T1Thermal at 300 K produces negligible
    signal — we only assert the chain runs and L_aperture is finite.
    """
    wl = _REGIME_GRIDS[cell.regime]
    T_t = _REGIME_TARGET_K[cell.regime]
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()

    params.set("source.target.temperature", T_t)
    params.set("source.target.emissivity", 0.95)
    params.set("source.target_location", "auto")  # inferrer → terrestrial
    params.set("source.scene_type", cell.scene_type)

    # Airborne vs terrestrial: only differ in target altitude.
    if cell.location == "airborne":
        params.set("geometry.target_altitude_m", 10_000.0)
    else:
        params.set("geometry.target_altitude_m", 0.0)

    # Scene-type-specific geometry for sub_pixel / point_source.  The
    # inferrer honours explicit source.scene_type so we don't need to
    # tune fill_fraction precisely — we only need the GroundBackground
    # branch to populate.  Both sub_pixel and point_source need
    # projected_area_m2 + range_m for SpectralIntegrationStage (it
    # computes Omega_target = A_t / R² in both regimes).
    if cell.scene_type == "sub_pixel":
        # Sub-pixel target fills partial pixel; √A_t/R placed well above
        # the point-source reclassify threshold (0.01·PSF_FWHM).
        params.set("source.target.projected_area_m2", 100.0)  # 10 m × 10 m
        params.set("source.target.range_m", 1e6)
        params.set("source.target.fill_fraction", 0.5)
    elif cell.scene_type == "point_source":
        # The point-source angular-size guard (matrix §7) fires when
        # √A_t/d > 0.1·PSF_FWHM.  Use a small target/large range so the
        # descriptor genuinely is a point source.
        params.set("source.target.projected_area_m2", 0.01)
        params.set("source.target.range_m", 1e6)
        params.set("source.target.fill_fraction", 1.0)

    # Atmosphere model = simple (midlat_summer) for terrestrial/airborne.
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.sensor_altitude_m", 800_000.0)

    _seed_optics_detector_readout(params, cell.regime)
    params.resolve()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        result = session.run(params)

    # Primary assertion: the chain ran and at-aperture radiance is finite.
    L = result.frames["at_aperture"].spectral_radiance
    assert np.all(np.isfinite(L)), f"cell {cell.cell_id}: L_aperture contains non-finite"
    # The target arm should be ≥ 0 everywhere (L_path_up adds a positive
    # baseline for terrestrial; VIS/NIR has near-zero L_self but L_path > 0).
    assert np.all(L >= -1e-12), f"cell {cell.cell_id}: L_aperture has negative values"


def _run_no_atm_space_cell(cell: CellSpec) -> None:
    """Run a ``no_atmosphere`` space cell through the full RadiantSession.

    The legacy inferrer maps ``atmosphere.model=exo`` to the space
    sub-case.  Space background is ColdSpaceBackground (L≡0); scene_type
    sub_pixel / point_source use GroundBackground placeholder — but the
    inferrer assigns ColdSpaceBackground for all no_atmosphere + space,
    independent of scene_type.
    """
    wl = _REGIME_GRIDS[cell.regime]
    T_t = _REGIME_TARGET_K[cell.regime]
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()

    params.set("source.target.temperature", T_t)
    params.set("source.target.emissivity", 0.95)
    params.set("source.target_location", "auto")  # exo → no_atm + space
    params.set("source.scene_type", cell.scene_type)
    params.set("atmosphere.model", "exo")
    params.set("geometry.sensor_altitude_m", 800_000.0)
    # Stage 7 Earth-intercept precondition: platform.h_sensor must be user-set.
    params.set("platform.h_sensor", 800_000.0)

    if cell.scene_type == "sub_pixel":
        params.set("source.target.projected_area_m2", 100.0)  # 10 m × 10 m
        params.set("source.target.range_m", 1e6)
        params.set("source.target.fill_fraction", 0.5)
    elif cell.scene_type == "point_source":
        # Small target, large range — true point source (≪ PSF_FWHM).
        params.set("source.target.projected_area_m2", 0.01)
        params.set("source.target.range_m", 1e6)
        params.set("source.target.fill_fraction", 1.0)

    _seed_optics_detector_readout(params, cell.regime)
    params.resolve()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        result = session.run(params)

    L = result.frames["at_aperture"].spectral_radiance
    assert np.all(np.isfinite(L)), f"cell {cell.cell_id}: L_aperture contains non-finite"
    assert np.all(L >= -1e-12), f"cell {cell.cell_id}: L_aperture has negative values"


def _run_at_aperture_extended_cell(cell: CellSpec) -> None:
    """Run an at_aperture extended cell through the injected-source chain.

    The legacy inferrer builds T1Thermal (not T5AtAperture) for at_aperture
    scenes, which fails at AtmosphereStage.  We bypass that by injecting a
    T5AtAperture descriptor directly.
    """
    wl = _REGIME_GRIDS[cell.regime]
    # Pick an at-aperture radiance value that is plausible for the band
    # (W/m²/sr/µm): use ε·B(300K) evaluated at mid-band as a rough scale.
    # For simplicity use a regime-tuned scalar.
    L_value = {
        "VIS": 50.0,       # reflected-solar magnitude in VIS
        "NIR": 40.0,
        "SWIR": 5.0,
        "MWIR": 1.0,
        "LWIR": 8.0,       # ε·B(300K) near 10 µm
    }[cell.regime]

    target = T5AtAperture(
        scene_type="extended",
        target_location="at_aperture",
        L_t_aperture=_at_aperture_radiance_sd(wl, L_value),
    )
    background = AtApertureBackground(L_bg_aperture=None)

    params = build_parameter_set()
    # Required schema defaults (unused but needed for params.resolve()).
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("atmosphere.model", "exo")
    params.set("geometry.sensor_altitude_m", 800_000.0)
    _seed_optics_detector_readout(params, cell.regime)
    params.resolve()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        state = _run_injected_chain(target, background, los=None, params=params, wl=wl)

    L = state.frames["at_aperture"].spectral_radiance
    assert np.all(np.isfinite(L)), f"cell {cell.cell_id}: L_aperture contains non-finite"


def _run_at_aperture_invalid_cell(cell: CellSpec) -> None:
    """Cells 2,3,5,6,8,9,11,12,14,15 — all at_aperture × {sub_pixel,point_source}.

    Matrix §7: at_aperture is extended-only.  Constructing a T5AtAperture
    with a non-extended scene_type must raise at descriptor construction
    (the base TargetDescriptor.__post_init__ enforces this).
    """
    wl = _REGIME_GRIDS[cell.regime]
    with pytest.raises(ParameterBoundsError, match="at_aperture"):
        T5AtAperture(
            scene_type=cell.scene_type,  # type: ignore[arg-type]
            target_location="at_aperture",
            L_t_aperture=_at_aperture_radiance_sd(wl, 1.0),
        )


def _run_subcase_cell(cell: CellSpec) -> None:
    """Run a D-ground (G1..G15) or D-lab (L1..L15) sub-case cell.

    The legacy inferrer raises for ground_test / lab_test (the legacy
    parameter surface has no L_bg channel); we use the _InjectedSource
    harness with a UserSpectralBackground.
    """
    wl = _REGIME_GRIDS[cell.regime]
    T_t = _REGIME_TARGET_K[cell.regime]
    subcase = "ground_test" if cell.location == "ground_test" else "lab_test"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        target = T1Thermal(
            scene_type=cell.scene_type,  # type: ignore[arg-type]
            target_location="no_atmosphere",
            no_atmosphere_subcase=subcase,  # type: ignore[arg-type]
            h_tgt=0.0,
            epsilon=_grey_sd(wl, 0.95),
            T_t=T_t,
            A_t=(0.01 if cell.scene_type != "extended" else None),
        )
    background = UserSpectralBackground(L_bg=_user_lbg_sd(wl, 0.2))
    los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)

    params = build_parameter_set()
    params.set("source.target.temperature", T_t)
    params.set("source.target.emissivity", 0.95)
    params.set("atmosphere.model", "exo")
    params.set("geometry.sensor_altitude_m", 0.0)
    _seed_optics_detector_readout(params, cell.regime)
    params.resolve()

    # Set the regime_tentative appropriately so OpticsStage doesn't misfire
    # on sub_pixel / point_source angular-size checks.
    regime_tentative = {
        "extended": RadiometricRegime.EXTENDED,
        "sub_pixel": RadiometricRegime.SUB_PIXEL,
        "point_source": RadiometricRegime.POINT_SOURCE,
    }[cell.scene_type]
    # For sub_pixel / point_source we need a finite angular extent so the
    # PSF-dependent guard has something to work with; extended stays at inf
    # (which makes the guard a no-op for extended).  Also populate
    # projected_area_m2 + range_m so SpectralIntegrationStage can compute
    # Omega_target = A_t/R² for sub_pixel and point_source.
    if cell.scene_type == "extended":
        angular = float("inf")
        area_m2 = 0.0
        range_m = 0.0
    elif cell.scene_type == "sub_pixel":
        # √A_t/R_eff chosen to be well above the 0.01·PSF_FWHM reclassify
        # threshold but well below 0.1·PSF_FWHM — safe middle ground.
        area_m2 = 100.0   # 10 m × 10 m test-range target
        range_m = 100.0   # 100 m test range
        angular = math.sqrt(area_m2) / range_m  # 0.1 rad
    else:  # point_source
        # √A_t/R_eff far below 0.1·PSF_FWHM — genuine point source.
        # The PSF-FWHM for the seed optics (D=0.15 m, f=0.45 m) is ~few µrad
        # in VIS and ~50 µrad in LWIR; the OpticsStage guard requires
        # √A_t/d ≤ 0.1·PSF_FWHM, so we pick a value ~2 orders below that
        # bound (1e-8 rad) to be comfortably inside the point-source regime
        # across every band.
        area_m2 = 1e-8     # 0.1 mm × 0.1 mm collimated point aperture
        range_m = 1e4      # 10 km optical path
        angular = math.sqrt(area_m2) / range_m  # 1e-8 rad

    runner = ChainRunner([
        _InjectedSource(
            target=target,
            background=background,
            los=los,
            regime_tentative=regime_tentative,
            angular_extent_rad=angular,
            projected_area_m2=area_m2,
            range_m=range_m,
        ),
        AtmosphereStage(),
        OpticsStage(),
        PlatformStage(),
        SpectralIntegrationStage(),
        DetectorStage(),
        ReadoutStage(),
        PerformanceStage(),
    ])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        state = runner.run(params, wl)

    L = state.frames["at_aperture"].spectral_radiance
    assert np.all(np.isfinite(L)), f"cell {cell.cell_id}: L_aperture contains non-finite"


def _run_cell(cell: CellSpec) -> None:
    """Dispatch a cell to the right scenario-runner based on its location."""
    if cell.location == "at_aperture":
        if cell.outcome == "raise":
            _run_at_aperture_invalid_cell(cell)
        else:
            _run_at_aperture_extended_cell(cell)
        return
    if cell.location in ("terrestrial", "airborne"):
        _run_terrestrial_or_airborne_cell(cell)
        return
    if cell.location == "no_atm_space":
        _run_no_atm_space_cell(cell)
        return
    if cell.location in ("ground_test", "lab_test"):
        _run_subcase_cell(cell)
        return
    raise AssertionError(f"Unknown location {cell.location!r} for cell {cell.cell_id}")


# ---------------------------------------------------------------------------
# The parametric test
# ---------------------------------------------------------------------------


def _cell_id(cell: CellSpec) -> str:
    """Human-readable pytest parameter id."""
    return f"{cell.cell_id}-{cell.location}-{cell.regime}-{cell.scene_type}"


@pytest.mark.parametrize("cell", ALL_CELLS, ids=[_cell_id(c) for c in ALL_CELLS])
def test_use_case_matrix_cell(cell: CellSpec) -> None:
    """Run (or assert the expected raise of) one matrix cell.

    Each cell is one independent test case — failures are isolated.  The
    coverage JSON is written at session end; here we record the per-cell
    outcome for aggregation.
    """
    if cell.outcome == "xfail":
        pytest.xfail(f"Cell {cell.cell_id} deferred: {cell.notes}")

    try:
        _run_cell(cell)
    except Exception:
        _record_result(cell.cell_id, "fail")
        raise

    # Recorded as whichever the expected outcome was (for 'raise' cells the
    # pytest.raises context inside _run_cell has already validated the raise).
    _record_result(cell.cell_id, cell.outcome)

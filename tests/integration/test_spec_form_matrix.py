"""Phase 7 Step 7.1 — S-form coverage sweep.

Complement to :mod:`tests.integration.test_use_case_matrix`, which sweeps
the (scene_type × wavelength_regime × target_location) axes.  This sibling
sweeps **Axis A** of the Target Definition Matrix — the radiometric spec
forms S1..S12 enumerated in
[`docs/RADIANT_Target_Definition_Matrix.md`](../../docs/RADIANT_Target_Definition_Matrix.md).

For each spec form, the test parametrizes a representative scene type
(one per §2 compatibility column) and asserts either:

* **pass** — the user-facing input path resolves to the canonical
  descriptor and the chain runs end-to-end with finite at-aperture radiance.
* **raise** — §2 marks the combination invalid (``✗``) and the expected
  :class:`~radiant.core.parameters.ParameterBoundsError` fires at either
  the boundary converter, the descriptor constructor, or the §7
  cross-field check.

The status per S-form is aggregated into a ``spec_forms`` block of
``_use_case_coverage.json`` so docs tooling can track which spec-form
surfaces are live.
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from radiant.api._param_registry import build_parameter_set
from radiant.api.session import RadiantSession
from radiant.atmosphere.stage import AtmosphereStage
from radiant.core.chain import ChainRunner
from radiant.core.descriptors import (
    AtApertureBackground,
    T5AtAperture,
)
from radiant.core.regime import RadiometricRegime
from radiant.core.spectral import SpectralData
from radiant.detector.stage import DetectorStage
from radiant.optics.stage import OpticsStage
from radiant.performance.stage import PerformanceStage
from radiant.platform.stage import PlatformStage
from radiant.readout.stage import ReadoutStage
from radiant.source.converters.user_intensity import user_intensity_to_descriptor
from radiant.spectral_integration.stage import SpectralIntegrationStage
from tests.integration.test_use_case_matrix import (
    _REGIME_GRIDS,
    _at_aperture_radiance_sd,
    _InjectedSource,
    _seed_optics_detector_readout,
)

_WL_LWIR = _REGIME_GRIDS["LWIR"]
_WL_VIS = _REGIME_GRIDS["VIS"]


# ---------------------------------------------------------------------------
# Cell specification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpecCell:
    """One (spec_form, scene_type) combination."""

    spec_form: str              # "S1".."S12"
    scene_type: str             # extended | sub_pixel | point_source
    outcome: str                # "pass" | "raise"
    notes: str = ""


# Per §2 of the matrix.  For forms that "→ S10" at point_source (S1–S8,
# S11, S12), the current pipeline accepts the native descriptor with a
# small A_t + large range (i.e., we do not hard-reject — the matrix
# documents the preferred canonical form, not a validation rule).
_CELLS: tuple[SpecCell, ...] = (
    # S1 Blackbody — T only, ε ≡ 1.
    SpecCell("S1", "extended",     "pass"),
    SpecCell("S1", "sub_pixel",    "pass"),
    SpecCell("S1", "point_source", "pass"),
    # S2 Graybody scalar — T + scalar ε.
    SpecCell("S2", "extended",     "pass"),
    SpecCell("S2", "sub_pixel",    "pass"),
    SpecCell("S2", "point_source", "pass"),
    # S3 Graybody spectral — T + ε(λ).  The inferrer accepts a scalar ε
    # that is materialized to a constant SpectralData (the tabulated-
    # constant limit of S3).  We reuse S2's surface here; the distinction
    # from S2 matters for the matrix but not for the coverage assertion.
    SpecCell("S3", "extended",     "pass"),
    SpecCell("S3", "sub_pixel",    "pass"),
    SpecCell("S3", "point_source", "pass"),
    # S4 Reflective scalar — ρ scalar (Phase 3).
    SpecCell("S4", "extended",     "pass"),
    SpecCell("S4", "sub_pixel",    "pass"),
    SpecCell("S4", "point_source", "pass"),
    # S5 Reflective spectral — ρ(λ) via reflectance_path (Gap G Step G.2:
    # CSV loader wired through the inferrer via the shared two-column
    # reader).  All three scenes exercise the CSV path.
    SpecCell("S5", "extended",     "pass"),
    SpecCell("S5", "sub_pixel",    "pass"),
    SpecCell("S5", "point_source", "pass"),
    # S6 Albedo — alias of S5.  Extended scene exercises the albedo_path
    # CSV (Gap G G.4); sub_pixel / point_source exercise scalar albedo.
    SpecCell("S6", "extended",     "pass"),
    SpecCell("S6", "sub_pixel",    "pass"),
    SpecCell("S6", "point_source", "pass"),
    # S7 Mixed emit+reflect — ε + T via T3Mixed (the default inferrer
    # path when emissivity < 1 and solar irradiance is available).
    SpecCell("S7", "extended",     "pass"),
    SpecCell("S7", "sub_pixel",    "pass"),
    SpecCell("S7", "point_source", "pass"),
    # S8 User radiance at source — T6TabulatedAtSource (Phase 4).
    SpecCell("S8", "extended",     "pass"),
    SpecCell("S8", "sub_pixel",    "pass"),
    SpecCell("S8", "point_source", "pass"),
    # S9 User radiance at aperture — T5AtAperture; §2 extended-only.
    SpecCell("S9", "extended",     "pass"),
    SpecCell("S9", "sub_pixel",    "raise", "at_aperture + sub_pixel §7"),
    SpecCell("S9", "point_source", "raise", "at_aperture + point_source §7"),
    # S10 User intensity — T7IntensityAtSource (Phase 5); point-source only.
    SpecCell("S10", "extended",     "raise", "intensity is point-source only"),
    SpecCell("S10", "sub_pixel",    "raise", "intensity is point-source only"),
    SpecCell("S10", "point_source", "pass"),
    # S11 Brightness temperature — converter → T1Thermal or T6 (Phase 2).
    # Extended scene exercises brightness_temperature_path CSV (Gap G G.4);
    # sub_pixel / point_source exercise scalar brightness_temperature_K.
    SpecCell("S11", "extended",     "pass"),
    SpecCell("S11", "sub_pixel",    "pass"),
    SpecCell("S11", "point_source", "pass"),
    # S12 Radiance temperature — converter → T1Thermal (Phase 2).
    SpecCell("S12", "extended",     "pass"),
    SpecCell("S12", "sub_pixel",    "pass"),
    SpecCell("S12", "point_source", "pass"),
)


# ---------------------------------------------------------------------------
# Coverage aggregation — merged into _use_case_coverage.json
# ---------------------------------------------------------------------------


_COVERAGE_PATH = Path(__file__).parent / "_use_case_coverage.json"
_SPEC_RESULTS: dict[str, dict[str, str]] = {}


def _record(spec: str, scene: str, outcome: str) -> None:
    """Record a per-(spec, scene_type) outcome for the JSON finalizer."""
    _SPEC_RESULTS.setdefault(spec, {})[scene] = outcome


@pytest.fixture(scope="session", autouse=True)
def _augment_coverage_with_spec_forms() -> Iterable[None]:
    """Merge per-S-form statuses into ``_use_case_coverage.json``."""
    yield
    if not _SPEC_RESULTS:
        return
    try:
        existing: dict[str, object] = json.loads(_COVERAGE_PATH.read_text())
    except FileNotFoundError:
        existing = {}
    except json.JSONDecodeError:
        existing = {}
    existing["spec_forms"] = dict(
        sorted(
            _SPEC_RESULTS.items(),
            key=lambda kv: int(kv[0][1:]),  # natural S1..S12 order
        )
    )
    _COVERAGE_PATH.write_text(json.dumps(existing, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Scenario helpers
# ---------------------------------------------------------------------------


def _write_csv(path: Path, wl: np.ndarray, value: float) -> Path:
    lines = [f"{float(w)},{float(value)}" for w in wl]
    path.write_text("\n".join(lines))
    return path


def _assert_chain_ran(session: RadiantSession, params) -> None:
    params.resolve()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        warnings.simplefilter("ignore", DeprecationWarning)
        result = session.run(params)
    L = result.frames["at_aperture"].spectral_radiance
    assert np.all(np.isfinite(L)), "at-aperture radiance contains non-finite values"


# ---------------------------------------------------------------------------
# Per-spec dispatch
# ---------------------------------------------------------------------------


def _run_thermal_spec(scene: str, *, T_t: float, epsilon: float | None) -> None:
    session = RadiantSession(wavelength_um=_WL_LWIR)
    params = session.default_params()
    params.set("source.target.temperature", T_t)
    if epsilon is not None:
        params.set("source.target.emissivity", epsilon)
    params.set("source.target_location", "auto")
    params.set("source.scene_type", scene)
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.sensor_altitude_m", 800_000.0)
    params.set("geometry.target_altitude_m", 0.0)
    if scene == "sub_pixel":
        params.set("source.target.projected_area_m2", 100.0)
        params.set("source.target.range_m", 1e6)
        params.set("source.target.fill_fraction", 0.5)
    elif scene == "point_source":
        params.set("source.target.projected_area_m2", 0.01)
        params.set("source.target.range_m", 1e6)
        params.set("source.target.fill_fraction", 1.0)
    _seed_optics_detector_readout(params, "LWIR")
    _assert_chain_ran(session, params)


def _run_reflective_spec(
    scene: str,
    *,
    reflectance: float | None = None,
    albedo: float | None = None,
    reflectance_path: Path | None = None,
    albedo_path: Path | None = None,
) -> None:
    session = RadiantSession(wavelength_um=_WL_VIS)
    params = session.default_params()
    if reflectance is not None:
        params.set("source.target.reflectance", reflectance)
    if albedo is not None:
        params.set("source.target.albedo", albedo)
    if reflectance_path is not None:
        params.set("source.target.reflectance_path", str(reflectance_path))
    if albedo_path is not None:
        params.set("source.target.albedo_path", str(albedo_path))
    params.set("source.target_location", "auto")
    params.set("source.scene_type", scene)
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.sensor_altitude_m", 800_000.0)
    params.set("geometry.target_altitude_m", 0.0)
    if scene == "sub_pixel":
        params.set("source.target.projected_area_m2", 100.0)
        params.set("source.target.range_m", 1e6)
        params.set("source.target.fill_fraction", 0.5)
    elif scene == "point_source":
        params.set("source.target.projected_area_m2", 0.01)
        params.set("source.target.range_m", 1e6)
        params.set("source.target.fill_fraction", 1.0)
    _seed_optics_detector_readout(params, "VIS")
    _assert_chain_ran(session, params)


def _run_user_radiance(scene: str, tmp_path: Path) -> None:
    csv = _write_csv(tmp_path / "L_source.csv", _WL_LWIR, 5.0)
    session = RadiantSession(wavelength_um=_WL_LWIR)
    params = session.default_params()
    params.set("source.target.user_radiance_path", str(csv))
    params.set("source.target_location", "auto")
    params.set("source.scene_type", scene)
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.sensor_altitude_m", 800_000.0)
    params.set("geometry.target_altitude_m", 0.0)
    if scene == "sub_pixel":
        params.set("source.target.projected_area_m2", 100.0)
        params.set("source.target.range_m", 1e6)
        params.set("source.target.fill_fraction", 0.5)
    elif scene == "point_source":
        params.set("source.target.projected_area_m2", 0.01)
        params.set("source.target.range_m", 1e6)
        params.set("source.target.fill_fraction", 1.0)
    _seed_optics_detector_readout(params, "LWIR")
    _assert_chain_ran(session, params)


def _run_user_aperture(scene: str) -> None:
    """S9: T5AtAperture + extended via injected-source harness."""
    wl = _WL_LWIR
    if scene != "extended":
        # Constructor raises — propagate so the outer harness records
        # this cell as an expected raise.
        T5AtAperture(
            scene_type=scene,  # type: ignore[arg-type]
            target_location="at_aperture",
            L_t_aperture=_at_aperture_radiance_sd(wl, 8.0),
        )
        return

    target = T5AtAperture(
        scene_type="extended",
        target_location="at_aperture",
        L_t_aperture=_at_aperture_radiance_sd(wl, 8.0),
    )
    background = AtApertureBackground(L_bg_aperture=None)
    params = build_parameter_set()
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("atmosphere.model", "exo")
    params.set("geometry.sensor_altitude_m", 800_000.0)
    _seed_optics_detector_readout(params, "LWIR")
    params.resolve()

    runner = ChainRunner([
        _InjectedSource(
            target=target,
            background=background,
            los=None,
            regime_tentative=RadiometricRegime.EXTENDED,
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
    assert np.all(np.isfinite(L))


def _run_user_intensity(scene: str, tmp_path: Path) -> None:
    if scene != "point_source":
        # Boundary converter rejects non-point-source intensity.  Let
        # the raise propagate so the outer harness records it.
        I_sd = SpectralData(
            name="test.I",
            wavelength_um=_WL_LWIR,
            values=np.full_like(_WL_LWIR, 0.1),
            unit="W/sr/um",
            source="test_spec_form_matrix",
        )
        user_intensity_to_descriptor(
            I_sd,
            scene_type=scene,  # type: ignore[arg-type]
            target_location="terrestrial",
        )
        return

    csv = _write_csv(tmp_path / "I_source.csv", _WL_LWIR, 0.1)
    session = RadiantSession(wavelength_um=_WL_LWIR)
    params = session.default_params()
    params.set("source.target.user_intensity_path", str(csv))
    params.set("source.target_location", "auto")
    params.set("source.scene_type", "point_source")
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.sensor_altitude_m", 800_000.0)
    params.set("geometry.target_altitude_m", 0.0)
    params.set("source.target.range_m", 1e6)
    params.set("source.target.fill_fraction", 1.0)
    _seed_optics_detector_readout(params, "LWIR")
    _assert_chain_ran(session, params)


def _run_brightness_temperature(
    scene: str,
    tmp_path: Path,
    *,
    use_csv_path: bool = False,
) -> None:
    # S11: scalar brightness_temperature_K (Phase 2) OR λ-varying
    # brightness_temperature_path CSV (Gap G Step G.3 — shared two-column
    # reader routes to T1Thermal for flat T_B or T6TabulatedAtSource for
    # λ-varying T_B).
    session = RadiantSession(wavelength_um=_WL_LWIR)
    params = session.default_params()
    if use_csv_path:
        csv = _write_csv(tmp_path / "T_B.csv", _WL_LWIR, 320.0)
        params.set("source.target.brightness_temperature_path", str(csv))
    else:
        params.set("source.target.brightness_temperature_K", 320.0)
    params.set("source.target_location", "auto")
    params.set("source.scene_type", scene)
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.sensor_altitude_m", 800_000.0)
    params.set("geometry.target_altitude_m", 0.0)
    if scene == "sub_pixel":
        params.set("source.target.projected_area_m2", 100.0)
        params.set("source.target.range_m", 1e6)
        params.set("source.target.fill_fraction", 0.5)
    elif scene == "point_source":
        params.set("source.target.projected_area_m2", 0.01)
        params.set("source.target.range_m", 1e6)
        params.set("source.target.fill_fraction", 1.0)
    _seed_optics_detector_readout(params, "LWIR")
    _assert_chain_ran(session, params)


def _run_radiance_temperature(scene: str) -> None:
    session = RadiantSession(wavelength_um=_WL_LWIR)
    params = session.default_params()
    params.set("source.target.radiance_temperature_K", 320.0)
    params.set("source.target.radiance_temperature_band_lo_um", 8.0)
    params.set("source.target.radiance_temperature_band_hi_um", 13.0)
    params.set("source.target_location", "auto")
    params.set("source.scene_type", scene)
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.sensor_altitude_m", 800_000.0)
    params.set("geometry.target_altitude_m", 0.0)
    if scene == "sub_pixel":
        params.set("source.target.projected_area_m2", 100.0)
        params.set("source.target.range_m", 1e6)
        params.set("source.target.fill_fraction", 0.5)
    elif scene == "point_source":
        params.set("source.target.projected_area_m2", 0.01)
        params.set("source.target.range_m", 1e6)
        params.set("source.target.fill_fraction", 1.0)
    _seed_optics_detector_readout(params, "LWIR")
    _assert_chain_ran(session, params)


def _dispatch(cell: SpecCell, tmp_path: Path) -> None:
    match cell.spec_form:
        case "S1":
            _run_thermal_spec(cell.scene_type, T_t=320.0, epsilon=1.0)
        case "S2":
            _run_thermal_spec(cell.scene_type, T_t=320.0, epsilon=0.8)
        case "S3":
            _run_thermal_spec(cell.scene_type, T_t=320.0, epsilon=0.95)
        case "S4":
            _run_reflective_spec(cell.scene_type, reflectance=0.3)
        case "S5":
            csv = _write_csv(tmp_path / "rho.csv", _WL_VIS, 0.3)
            _run_reflective_spec(cell.scene_type, reflectance_path=csv)
        case "S6":
            # Exercise albedo_path CSV at the extended scene (Gap G G.4
            # coverage); scalar albedo at the other two scenes.
            if cell.scene_type == "extended":
                csv = _write_csv(tmp_path / "alb.csv", _WL_VIS, 0.3)
                _run_reflective_spec(cell.scene_type, albedo_path=csv)
            else:
                _run_reflective_spec(cell.scene_type, albedo=0.3)
        case "S7":
            _run_thermal_spec(cell.scene_type, T_t=320.0, epsilon=0.7)
        case "S8":
            _run_user_radiance(cell.scene_type, tmp_path)
        case "S9":
            _run_user_aperture(cell.scene_type)
        case "S10":
            _run_user_intensity(cell.scene_type, tmp_path)
        case "S11":
            # Exercise brightness_temperature_path CSV at the extended
            # scene (Gap G G.4 coverage); scalar K at the other scenes.
            _run_brightness_temperature(
                cell.scene_type,
                tmp_path,
                use_csv_path=(cell.scene_type == "extended"),
            )
        case "S12":
            _run_radiance_temperature(cell.scene_type)
        case _:
            raise AssertionError(f"Unknown spec form: {cell.spec_form!r}")


# ---------------------------------------------------------------------------
# The parametric test
# ---------------------------------------------------------------------------


def _cell_id(cell: SpecCell) -> str:
    return f"{cell.spec_form}-{cell.scene_type}-{cell.outcome}"


@pytest.mark.parametrize("cell", _CELLS, ids=[_cell_id(c) for c in _CELLS])
def test_spec_form_matrix_cell(cell: SpecCell, tmp_path: Path) -> None:
    """Exercise one (spec_form, scene_type) cell and record coverage."""
    if cell.outcome == "raise":
        # S9 non-extended and S10 non-point-source already assert inside
        # the dispatcher; any other "raise" outcome surfaces through the
        # dispatched helper.
        try:
            _dispatch(cell, tmp_path)
        except Exception:
            _record(cell.spec_form, cell.scene_type, "raise")
            return
        else:
            _record(cell.spec_form, cell.scene_type, "unexpected_pass")
            pytest.fail(
                f"{cell.spec_form} + {cell.scene_type} was expected to raise "
                f"({cell.notes or 'see matrix §2'}) but did not."
            )
    else:  # "pass"
        _dispatch(cell, tmp_path)
        _record(cell.spec_form, cell.scene_type, "pass")

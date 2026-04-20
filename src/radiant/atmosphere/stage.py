"""AtmosphereStage — chain wrapper for atmospheric transmission and path radiance.

Stage 3 Option C — **shadow-mode dual-path execution**.

This stage runs *both* the legacy ``build_state`` path (``L·τ + L_path``) and
the new descriptor-driven assembly path (``evaluate`` + ``assemble_*``), and —
when the ``RADIANT_OPTION_C_SHADOW`` env var is set to ``"1"`` — asserts that
the two paths agree on the cells classified as ``invariant`` in the Stage 0
baseline snapshot (see ``tests/integration/snapshots/option_c_baseline.yaml``).

Produces
--------
Frame ``"at_aperture"`` with spectral radiance
    (LEGACY path, still authoritative in Stage 3):
    ``L_at_aperture(λ) = L_target(λ) · τ_atm(λ) + L_path(λ)``

Stage outputs under ``stage_outputs["atmosphere"]``:
    - ``tau_atm``: transmittance values (ndarray) — legacy τ
    - ``L_path``: upwelling path radiance (ndarray) — legacy L_path
    - ``L_atm_down``: downwelling graybody emission (ndarray) — legacy
    - ``atm_quantities``: the new :class:`AtmosphericQuantities` bundle
      (ndarray fields; stored for inspection / Stage 4 promotion)
    - ``L_aperture_new``: the new assembly-path at-aperture spectral
      radiance (target arm, ndarray).  Stage 4 renames this to the
      authoritative ``at_aperture`` frame.
    - ``L_bg_aperture_new``: the new background at-aperture spectral
      radiance (ndarray or ``None``; None → bg photon term skipped
      in Stage 5 per Decision #13).

Shadow-mode policy (env var ``RADIANT_OPTION_C_SHADOW``)
-------------------------------------------------------
- **default**: ``"1"`` — shadow-mode checks run.
- **"0"**: shadow-mode disabled; both paths still run (legacy stays
  authoritative); no cross-path comparison happens.
- When on, for each scenario classified in the baseline snapshot:
    * ``classification == "invariant"``: hard-assert
      ``np.allclose(L_aperture_new, L_aperture_legacy, rtol=1e-6)``
      on the target-arm at-aperture radiance.
    * ``classification == "expected_to_change_at_stage_3"`` /
      ``"expected_to_change_at_stage_6"``: log-only (INFO-level).
    * Unclassified / missing-from-snapshot: the comparison is skipped
      entirely (no way to know what the expectation is, and the
      snapshot lives outside the chain-state).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.assembly import (
    assemble_background_at_aperture,
    assemble_target_at_aperture,
)
from radiant.atmosphere.exo import ExoAtmosphere
from radiant.atmosphere.protocol import AtmosphericGeometry
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame

logger = logging.getLogger(__name__)

# Env var that toggles shadow-mode hard assertions on the invariant cells.
# Default is "1" in Stage 3 (per the Option C plan); Stage 4 will stop
# consulting this var entirely.
_SHADOW_ENV_VAR: str = "RADIANT_OPTION_C_SHADOW"

# Shadow-mode agreement tolerance on invariant cells.
_SHADOW_RTOL: float = 1.0e-6
_SHADOW_ATOL: float = 1.0e-12


def _shadow_mode_enabled() -> bool:
    """True iff ``RADIANT_OPTION_C_SHADOW`` is ``"1"`` (default) or unset.

    Any value other than ``"0"`` is treated as enabled — defensive default
    for Stage 3.  Stage 4 removes this function entirely.
    """
    val = os.environ.get(_SHADOW_ENV_VAR, "1")
    return val != "0"


class AtmosphereStage:
    """Chain stage for atmospheric transmission and path radiance.

    Stage 3 of Option C: runs both the legacy and new descriptor-driven
    paths; emits both under stage_outputs; and enforces the invariant-cell
    agreement contract when shadow mode is on.
    """

    @property
    def name(self) -> str:
        return "atmosphere"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        model_name: str = params.get("atmosphere.model")

        # ------------------------------------------------------------------
        # 1. Build the atmospheric model (pure — no chain coupling)
        # ------------------------------------------------------------------
        if model_name == "exo":
            model: object = ExoAtmosphere()
        elif model_name == "tabulated":
            model = self._build_tabulated(params)
        elif model_name == "modtran":
            model = self._build_modtran(params)
        elif model_name == "interpolated":
            model = self._build_interpolated(params)
        else:
            # Default: simple parametric model.
            model = SimpleAtmosphere(
                visibility_km=params.get("atmosphere.visibility_km"),
                aerosol_type=params.get("atmosphere.aerosol_type"),
                precipitable_water_cm=params.get("atmosphere.precipitable_water_cm"),
                standard_atmosphere=params.get("atmosphere.standard_atmosphere"),
            )

        # ------------------------------------------------------------------
        # 2. Legacy path: build_state(geometry) and assemble L_aperture
        #    exactly as Stages 0-2 did.  Stays authoritative in Stage 3.
        # ------------------------------------------------------------------
        geometry = AtmosphericGeometry(
            sensor_altitude_m=params.get("geometry.sensor_altitude_m"),
            target_altitude_m=params.get("geometry.target_altitude_m"),
            path_zenith_rad=params.get("geometry.path_zenith_rad"),
            solar_zenith_rad=params.get("geometry.solar_zenith_rad"),
            solar_azimuth_rad=params.get("geometry.solar_azimuth_rad"),
        )
        atm_state = model.build_state(state.wavelength_um, geometry)  # type: ignore[attr-defined]

        at_target = state.frames["at_target"]
        L_target = at_target.spectral_radiance
        if L_target is None:
            raise ValueError(
                "AtmosphereStage: 'at_target' frame has no spectral_radiance. "
                "SourceStage must run first and produce spectral radiance."
            )

        tau_legacy: np.ndarray = np.asarray(atm_state.transmittance.values, dtype=np.float64)
        L_path_legacy: np.ndarray = np.asarray(atm_state.path_radiance.values, dtype=np.float64)
        L_atm_down_legacy: np.ndarray = np.asarray(
            atm_state.atm_emission_down.values, dtype=np.float64
        )
        L_aperture_legacy: np.ndarray = L_target * tau_legacy + L_path_legacy

        frame = RadiometricFrame(
            name="at_aperture",
            wavelength_um=state.wavelength_um,
            spectral_radiance=L_aperture_legacy,
            notes=f"L_target × τ_atm + L_path ({model_name})",
        )

        # ------------------------------------------------------------------
        # 3. New path: evaluate() + assemble_*(), driven by descriptors that
        #    SourceStage published in stage_outputs["source"].  If any of
        #    those keys are missing we skip the new path entirely — this
        #    keeps the stage runnable during staged rollouts where a
        #    downstream-only test rig is hitting AtmosphereStage without a
        #    real Stage-2 refactor.
        # ------------------------------------------------------------------
        target_desc = state.stage_outputs.get("source", {}).get("target")
        background_desc = state.stage_outputs.get("source", {}).get("background")
        los = state.stage_outputs.get("source", {}).get("los_geometry")

        atm_quantities: AtmosphericQuantities | None = None
        L_aperture_new: np.ndarray | None = None
        L_bg_aperture_new: np.ndarray | None = None

        if target_desc is not None and los is not None:
            atm_quantities = model.evaluate(  # type: ignore[attr-defined]
                state.wavelength_um, los, params
            )
            L_aperture_new = assemble_target_at_aperture(
                target_desc, atm_quantities, los,
            )
            L_bg_aperture_new = assemble_background_at_aperture(
                background_desc, atm_quantities, los,
            )
        else:
            logger.debug(
                "AtmosphereStage: skipping new-path assembly because "
                "SourceStage did not publish target/LOS descriptors."
            )

        # ------------------------------------------------------------------
        # 4. Shadow-mode agreement check (invariant cells only).
        # ------------------------------------------------------------------
        if (
            _shadow_mode_enabled()
            and L_aperture_new is not None
        ):
            self._shadow_compare(
                state=state,
                L_legacy=L_aperture_legacy,
                L_new=L_aperture_new,
            )

        # ------------------------------------------------------------------
        # 5. Emit state — legacy frame + stage outputs for both paths.
        # ------------------------------------------------------------------
        state = (
            state.with_frame(frame)
            .with_stage_output("atmosphere", "tau_atm", tau_legacy)
            .with_stage_output("atmosphere", "L_path", L_path_legacy)
            .with_stage_output("atmosphere", "L_atm_down", L_atm_down_legacy)
        )

        if atm_quantities is not None:
            state = state.with_stage_output(
                "atmosphere", "atm_quantities", atm_quantities,
            )
        if L_aperture_new is not None:
            state = state.with_stage_output(
                "atmosphere", "L_aperture_new", L_aperture_new,
            )
        # Always publish the new bg key (even None) so Stage 5 can consume
        # it explicitly — Decision #13 uses the None sentinel.
        state = state.with_stage_output(
            "atmosphere", "L_bg_aperture_new", L_bg_aperture_new,
        )

        # Turbulence: store Fried parameter for downstream stages.
        try:
            r0_m: float = params.get("atmosphere.r0_m")
        except (KeyError, TypeError):
            r0_m = 0.0
        if r0_m > 0.0:
            state = state.with_stage_output("atmosphere", "r0_m", r0_m)

        return state

    # ------------------------------------------------------------------
    # Shadow-mode comparison
    # ------------------------------------------------------------------

    @staticmethod
    def _shadow_compare(
        state: ChainState,
        L_legacy: np.ndarray,
        L_new: np.ndarray,
    ) -> None:
        """Compare legacy vs. new at-aperture radiance under shadow mode.

        Policy (from ``docs/Option_C_Implementation_Plan.md`` Stage 3):

        * ``classification == "invariant"``: hard-assert agreement within
          ``rtol = 1e-6``.  A failure raises :class:`AssertionError` with
          actionable context.
        * ``classification == "expected_to_change_at_stage_3"`` or
          ``"expected_to_change_at_stage_6"``: log-only (INFO) with the max
          abs/rel delta — this documents the drift without gating CI.
        * No classification available (the baseline snapshot does not
          accompany the chain state in production): skip entirely.

        The baseline snapshot lookup is keyed by the scenario path that the
        caller stashes under ``state.stage_outputs["meta"]["scenario_path"]``
        — callers that don't publish that key (unit tests, ad-hoc runs)
        silently skip the comparison.
        """
        classification = (
            state.stage_outputs.get("meta", {}).get("option_c_classification")
        )
        if classification is None:
            # No classification → we don't know what the expectation is.
            # The *test harness* (``tests/integration/...``) is responsible
            # for populating this; production runs don't see it.
            return

        diff = np.asarray(L_new - L_legacy, dtype=np.float64)
        max_abs = float(np.max(np.abs(diff))) if diff.size else 0.0
        denom = np.maximum(np.abs(L_legacy), 1e-30)
        max_rel = float(np.max(np.abs(diff) / denom)) if diff.size else 0.0

        scenario = (
            state.stage_outputs.get("meta", {}).get("scenario_path", "(unknown)")
        )

        if classification == "invariant":
            if not np.allclose(L_new, L_legacy, rtol=_SHADOW_RTOL, atol=_SHADOW_ATOL):
                raise AssertionError(
                    "AtmosphereStage shadow-mode disagreement on invariant cell. "
                    f"scenario={scenario!r} "
                    f"max_abs_diff={max_abs:.3e} "
                    f"max_rel_diff={max_rel:.3e} "
                    f"tol=rtol={_SHADOW_RTOL:.0e} atol={_SHADOW_ATOL:.0e}. "
                    "The new descriptor-driven path produced a different at-aperture "
                    "radiance than the legacy L·τ + L_path path on a cell that is "
                    "classified as INVARIANT in tests/integration/snapshots/"
                    "option_c_baseline.yaml. Stop and debug the atmospheric backend "
                    "or the assembly code; do not update the baseline. See "
                    "docs/Option_C_Implementation_Plan.md Stage 3 §Regression."
                )
            logger.info(
                "AtmosphereStage shadow-mode: invariant cell %s agreement ok "
                "(max_abs=%.3e, max_rel=%.3e).",
                scenario, max_abs, max_rel,
            )
            return

        if classification.startswith("expected_to_change"):
            logger.info(
                "AtmosphereStage shadow-mode: scenario %s classified %s; "
                "legacy vs new max_abs=%.3e max_rel=%.3e (not enforced).",
                scenario, classification, max_abs, max_rel,
            )
            return

        raise AssertionError(
            f"AtmosphereStage shadow-mode: unknown classification "
            f"{classification!r} for scenario {scenario!r}. Allowed values: "
            "'invariant', 'expected_to_change_at_stage_3', "
            "'expected_to_change_at_stage_6'.  Update "
            "tests/integration/snapshots/option_c_baseline.yaml or the test "
            "harness that set this key."
        )

    # ------------------------------------------------------------------
    # Model builders (file I/O happens here, before build_state)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_tabulated(params: ParameterSet) -> object:
        """Construct a TabulatedAtmosphere from parameters."""
        from radiant.atmosphere.tabulated import TabulatedAtmosphere

        tau_file = params.get("atmosphere.tabulated_transmittance_file")
        lpath_file = params.get("atmosphere.tabulated_path_radiance_file")
        ldown_file = params.get("atmosphere.tabulated_downwelling_file")

        if not tau_file or not lpath_file:
            raise ValueError(
                "AtmosphereStage: model='tabulated' requires "
                "atmosphere.tabulated_transmittance_file and "
                "atmosphere.tabulated_path_radiance_file to be set."
            )

        # Detect format by extension.
        if str(tau_file).endswith(".npz"):
            return TabulatedAtmosphere.from_npz(tau_file)
        return TabulatedAtmosphere.from_csv(
            tau_file, lpath_file, ldown_file if ldown_file else None,
        )

    @staticmethod
    def _build_modtran(params: ParameterSet) -> object:
        """Construct a ModtranAtmosphere from parameters."""
        from radiant.atmosphere.modtran import ModtranAtmosphere, ModtranConfig

        config = ModtranConfig(
            binary_path=Path(params.get("atmosphere.modtran.binary_path")),
            cache_dir=Path(
                str(params.get("atmosphere.modtran.cache_dir")).replace(
                    "~", str(Path.home()),
                )
            ),
            allow_fallback=params.get("atmosphere.modtran.allow_fallback"),
            atmosphere_profile=params.get("atmosphere.modtran.atmosphere_profile"),
            aerosol_model=params.get("atmosphere.modtran.aerosol_model"),
            h2o_scale=params.get("atmosphere.modtran.h2o_scale"),
            o3_scale=params.get("atmosphere.modtran.o3_scale"),
            spectral_resolution_cm1=params.get(
                "atmosphere.modtran.spectral_resolution_cm1"
            ),
        )
        return ModtranAtmosphere(config)

    @staticmethod
    def _build_interpolated(params: ParameterSet) -> object:
        """Construct an InterpolatedAtmosphere from a data directory.

        The data directory must contain NPZ files, each with keys
        ``wavelength_um``, ``transmittance``, ``path_radiance``, and
        optionally ``atm_emission_down``.  Each file must also contain
        a ``geometry`` key with a JSON-encoded dict of coordinate
        values.
        """
        import json

        from radiant.atmosphere.interpolated import (
            GeometryPoint,
            InterpolatedAtmosphere,
        )
        from radiant.atmosphere.tabulated import TabulatedAtmosphere

        data_dir = params.get("atmosphere.interpolated_data_dir")
        if not data_dir:
            raise ValueError(
                "AtmosphereStage: model='interpolated' requires "
                "atmosphere.interpolated_data_dir to be set."
            )

        axes_str: str = params.get("atmosphere.interpolation_axes")
        axes = [a.strip() for a in axes_str.split(",")]
        method: str = params.get("atmosphere.interpolation_method")

        data_path = Path(data_dir)
        if not data_path.exists():
            raise FileNotFoundError(
                f"AtmosphereStage: interpolated data directory not found: "
                f"{data_path}."
            )

        npz_files = sorted(data_path.glob("*.npz"))
        if len(npz_files) < 2:
            raise ValueError(
                f"AtmosphereStage: interpolated data directory {data_path} "
                f"must contain at least 2 NPZ files, found {len(npz_files)}."
            )

        points: list[GeometryPoint] = []
        for npz_file in npz_files:
            data = np.load(npz_file, allow_pickle=True)

            if "geometry" not in data:
                raise ValueError(
                    f"AtmosphereStage: NPZ file {npz_file} is missing a "
                    "'geometry' key with coordinate values."
                )

            geom_raw = data["geometry"]
            coords = geom_raw.item() if hasattr(geom_raw, "item") else json.loads(str(geom_raw))

            tab = TabulatedAtmosphere.from_npz(npz_file)
            points.append(
                GeometryPoint(
                    coordinates=coords,
                    transmittance=tab.transmittance_data,
                    path_radiance=tab.path_radiance_data,
                    atm_emission_down=tab.atm_emission_down_data,
                )
            )

        return InterpolatedAtmosphere(points, axes, method)


# Re-export for the test harness that needs to read the current shadow-mode
# state.
__all__ = ["AtmosphereStage"]

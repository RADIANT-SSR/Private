"""CalibrationStage — radiometric calibration error model (Gap 120, ADR-0012).

Terms-only stage (PlatformStage precedent) registered between ReadoutStage
and PerformanceStage. The chain position is load-bearing: residual-FPN
noise terms are appended AFTER readout's TDI/coadd scaling, so calibration
residuals are structurally exempt from sqrt(N) averaging — correlated
errors do not average down. Do not move this stage without re-reading
ADR-0012 and the contract tests.

Under an active scheme the stage:

1. maps the declared cal temperatures to cal signals with the band
   photon-radiance ratio (``cal_points.py``), anchored at the delivered
   post-readout signal (``stage_outputs["readout"]["signal_e_final"]``);
2. emits the residual noise terms (``nuc_residual``, ``gain_drift``,
   ``offset_drift`` — SPATIAL_TERMS ∩ CALIBRATION_TERMS) via
   ``state.with_noise``;
3. emits the cal-source bias terms via ``state.with_bias`` (accuracy
   budget only — never RSS'd into noise);
4. publishes its own post-calibration totals under
   ``stage_outputs["calibration"]`` (``sigma_total_e`` = readout total ⊕
   calibration residuals). Rule 7 forbids editing readout's published
   total, so downstream metrics prefer the calibration total when present
   (``performance/snr.py``, ``contrast_snr.py``).

Noise-regime note: ``detector.noise_regime = "imaging"`` excludes pre-cal
FPN as "calibrated out". The calibration residuals are precisely what
survives that calibration, so they enter the total in BOTH regimes — that
is the point of the model (calibration-limited NEDT).

This stage adds no PSF kernel and no MTF term: residual FPN is spatial
*noise*, not a spatial *degradation* — neither Rule 4 path gains a
contributor and the consistency check is unaffected (plan §2.5).
"""

from __future__ import annotations

import logging
import math

from radiant.calibration.cal_points import cal_point_signal_e
from radiant.calibration.cal_source_bias import (
    source_emissivity_bias_frac,
    source_temp_bias_frac,
)
from radiant.calibration.errors import (
    CalibrationConfigIncompleteError,
    CalibrationValidationError,
)
from radiant.calibration.gain_drift import gain_drift_residual_e
from radiant.calibration.nuc_residual import one_point_residual_e, two_point_residual_e
from radiant.calibration.offset_drift import offset_drift_residual_e
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import BiasTerm, NoiseTerm

logger = logging.getLogger(__name__)

#: Sentinel: cal temperatures default to 0.0 = "unset" (see _schema.py).
_UNSET = 0.0

# Canonical display units for this stage's scalar ``stage_outputs`` (CU-118).
OUTPUT_UNITS: dict[str, str] = {
    "s1_e": "e-",
    "s2_e": "e-",
    "nuc_residual_e": "e-",
    "gain_drift_e": "e-",
    "offset_drift_e": "e-",
    "sigma_calibration_e": "e-",
    "sigma_total_e": "e-",
    "bias_total_frac": "",
    "calibration_nedt_K": "K",
}


def _validate_active_scheme(scheme: str, params: ParameterSet) -> None:
    """Rule 16: validate an active scheme's configuration before any physics.

    Raises the *incomplete* subtype when required cal points are unset (a
    mid-switch config — advisory routing) and the plain validation error
    when values present are unphysical (a rejected input — modal routing).
    """
    t_low: float = params.get("calibration.cal_temp_low_K")
    t_high: float = params.get("calibration.cal_temp_high_K")

    if t_low == _UNSET:
        raise CalibrationConfigIncompleteError(
            f"calibration.scheme = '{scheme}' needs a cal point, but "
            "calibration.cal_temp_low_K is unset.\n"
            "  Why: an active NUC scheme corrects at known cal-source "
            "temperatures; without them there is nothing to correct at.\n"
            "  Action: set calibration.cal_temp_low_K (and cal_temp_high_K "
            "for two_point), or set calibration.scheme = 'none'."
        )
    if scheme == "two_point":
        if t_high == _UNSET:
            raise CalibrationConfigIncompleteError(
                "calibration.scheme = 'two_point' needs two cal points, but "
                "calibration.cal_temp_high_K is unset.\n"
                "  Why: two-point NUC corrects per-pixel gain and offset at "
                "two cal-source temperatures.\n"
                "  Action: set calibration.cal_temp_high_K above "
                f"cal_temp_low_K = {t_low} K, or use scheme = 'one_point'."
            )
        if t_high <= t_low:
            raise CalibrationValidationError(
                f"calibration.cal_temp_high_K = {t_high} K must exceed "
                f"cal_temp_low_K = {t_low} K.\n"
                "  Why: two-point NUC is ill-conditioned as the cal points "
                "converge (plan §15) and undefined when inverted.\n"
                "  Action: separate the cal temperatures (high > low)."
            )


def _require_chain_scalar(name: str, value: object, source: str) -> float:
    """A positive chain scalar the residual model anchors to (Rule 16)."""
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value <= 0.0:
        raise CalibrationValidationError(
            f"calibration needs {source} > 0, got {value!r}.\n"
            "  Why: the residual model anchors cal signals to the delivered "
            f"chain signal via {name}; without it there is no scale.\n"
            "  Action: evaluate a thermal scene with non-zero signal, or set "
            "calibration.scheme = 'none'."
        )
    return float(value)


class CalibrationStage:
    """Stage protocol implementation for the calibration error model."""

    @property
    def name(self) -> str:
        return "calibration"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        scheme: str = params.get("calibration.scheme")

        if scheme == "none":
            logger.debug("calibration: scheme=none — model off, no terms emitted")
            return state.with_stage_output("calibration", "scheme", "none").with_stage_output(
                "calibration", "enabled", False
            )

        _validate_active_scheme(scheme, params)

        ro = state.stage_outputs.get("readout", {})
        det = state.stage_outputs.get("detector", {})
        si = state.stage_outputs.get("spectral_integration", {})

        signal_e = _require_chain_scalar(
            "stage_outputs['readout']['signal_e_final']",
            ro.get("signal_e_final"),
            "the post-readout signal",
        )
        scene_temp_K: float = params.get("source.target.temperature")
        lam_min_um: float = params.get("spectral_integration.filter_min_um")
        lam_max_um: float = params.get("spectral_integration.filter_max_um")

        # --- Cal points in the signal domain -----------------------------
        t_low: float = params.get("calibration.cal_temp_low_K")
        s1_e = cal_point_signal_e(
            t_cal_K=t_low,
            scene_temp_K=scene_temp_K,
            scene_signal_e=signal_e,
            lam_min_um=lam_min_um,
            lam_max_um=lam_max_um,
        )
        state = state.with_stage_output("calibration", "s1_e", s1_e)

        prnu_frac = float(det.get("precal_prnu_pct", 0.0)) / 100.0

        if scheme == "two_point":
            t_high: float = params.get("calibration.cal_temp_high_K")
            s2_e = cal_point_signal_e(
                t_cal_K=t_high,
                scene_temp_K=scene_temp_K,
                scene_signal_e=signal_e,
                lam_min_um=lam_min_um,
                lam_max_um=lam_max_um,
            )
            state = state.with_stage_output("calibration", "s2_e", s2_e)
            # Full-scale reference for the quadratic coefficient, in the same
            # summed domain as signal_e_final: the counting effective well
            # when the DROIC branch ran, else the per-pixel analog capacity
            # scaled by the accumulation gain the signal actually received
            # (TDI/binning/coadds) — signal_e_final over the detector's
            # per-pixel signal_e. Keeping numerator and denominator in one
            # domain is what makes the residual's signal-relative size
            # invariant in N (the sqrt(N)-exemption contract test).
            well = ro.get("effective_well_e")
            if well is None:
                capacity: float = params.get("readout.full_well_capacity_e")
                det_signal = det.get("signal_e")
                accum_gain = (
                    signal_e / float(det_signal)
                    if isinstance(det_signal, (int, float)) and det_signal > 0.0
                    else 1.0
                )
                well = capacity * accum_gain
            full_well_e = _require_chain_scalar(
                "the well capacity (readout.full_well_capacity_e or the counting effective_well_e)",
                well,
                "the well capacity",
            )
            nuc_e = two_point_residual_e(
                signal_e=signal_e,
                s1_e=s1_e,
                s2_e=s2_e,
                nonlinearity_frac=params.get("calibration.nonlinearity_pct"),
                full_well_e=full_well_e,
            )
            t_cal_bias_K = 0.5 * (t_low + t_high)
        else:  # one_point
            nuc_e = one_point_residual_e(signal_e=signal_e, s1_e=s1_e, prnu_frac=prnu_frac)
            t_cal_bias_K = t_low

        # --- Drift terms --------------------------------------------------
        time_s: float = params.get("calibration.time_since_cal_s")
        gain_drift_e = gain_drift_residual_e(
            signal_e=signal_e,
            gain_drift_frac_per_s=params.get("calibration.gain_drift_frac_per_s"),
            time_since_cal_s=time_s,
        )
        offset_drift_e = offset_drift_residual_e(
            offset_drift_e_per_s=params.get("calibration.offset_drift_e_per_s"),
            time_since_cal_s=time_s,
        )

        # --- Emit noise terms (post-scaling: sqrt(N)-exempt by position) --
        for term_name, value_e, basis in (
            ("nuc_residual", nuc_e, f"post-NUC residual ({scheme})"),
            ("gain_drift", gain_drift_e, "gain drift since cal (time-linear, D4)"),
            ("offset_drift", offset_drift_e, "offset drift since cal (time-linear, D4)"),
        ):
            state = state.with_noise(
                NoiseTerm(
                    name=term_name,
                    value_e=value_e,
                    origin_frame="photoelectrons",
                    physical_basis=basis,
                    contributes_to=("spatial", "total"),
                )
            )

        sigma_cal_e = math.sqrt(nuc_e**2 + gain_drift_e**2 + offset_drift_e**2)
        ro_sigma = float(ro.get("sigma_total_e", 0.0))
        sigma_total_e = math.sqrt(ro_sigma**2 + sigma_cal_e**2)

        # --- Bias terms (accuracy budget only, D3) ------------------------
        dt_src: float = params.get("calibration.source_temp_uncertainty_K")
        if dt_src > 0.0:
            state = state.with_bias(
                BiasTerm(
                    name="source_temp",
                    value_frac=source_temp_bias_frac(
                        delta_t_K=dt_src,
                        t_cal_K=t_cal_bias_K,
                        lam_min_um=lam_min_um,
                        lam_max_um=lam_max_um,
                    ),
                    origin="calibration.source_temp_uncertainty_K",
                    physical_basis="band Planck dL/dT at T_cal",
                )
            )
        d_eps: float = params.get("calibration.source_emissivity_uncertainty")
        if d_eps > 0.0:
            state = state.with_bias(
                BiasTerm(
                    name="source_emissivity",
                    value_frac=source_emissivity_bias_frac(
                        delta_eps=d_eps,
                        eps_source=params.get("calibration.source_emissivity"),
                    ),
                    origin="calibration.source_emissivity_uncertainty",
                    physical_basis="radiance scale (delta_eps/eps_src)",
                )
            )
        gain_unc: float = params.get("calibration.gain_uncertainty_pct")
        if gain_unc > 0.0:
            state = state.with_bias(
                BiasTerm(
                    name="gain",
                    value_frac=gain_unc,  # canonical unit is already a fraction
                    origin="calibration.gain_uncertainty_pct",
                    physical_basis="absolute radiometric gain uncertainty",
                )
            )
        bias_total_frac = math.sqrt(sum(t.value_frac**2 for t in state.bias_terms))

        # --- Published totals + diagnostics -------------------------------
        state = state.with_stage_output("calibration", "scheme", scheme)
        state = state.with_stage_output("calibration", "enabled", True)
        state = state.with_stage_output("calibration", "nuc_residual_e", nuc_e)
        state = state.with_stage_output("calibration", "gain_drift_e", gain_drift_e)
        state = state.with_stage_output("calibration", "offset_drift_e", offset_drift_e)
        state = state.with_stage_output("calibration", "sigma_calibration_e", sigma_cal_e)
        state = state.with_stage_output("calibration", "sigma_total_e", sigma_total_e)
        state = state.with_stage_output("calibration", "bias_total_frac", bias_total_frac)

        # NEDT-equivalent of the calibration floor (edit-and-watch readout;
        # None when the scene has no thermal derivative).
        ds_dt = si.get("ds_dt_e_per_K")
        if ds_dt is not None and ds_dt > 0.0:
            state = state.with_stage_output(
                "calibration", "calibration_nedt_K", sigma_cal_e / ds_dt
            )
        return state

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
import warnings

from radiant.calibration.cal_points import (
    band_thermal_photon_fraction,
    cal_point_ds_dt_e_per_K,
    cal_point_signal_e,
)
from radiant.calibration.cal_source_bias import (
    source_emissivity_bias_frac,
    source_temp_bias_frac,
)
from radiant.calibration.errors import (
    CalibrationConfigIncompleteError,
    CalibrationValidationError,
)
from radiant.calibration.gain_drift import gain_drift_residual_e
from radiant.calibration.internal_cal import fore_optics_fraction
from radiant.calibration.nuc_residual import (
    one_point_residual_e,
    three_point_residual_e,
    two_point_residual_e,
)
from radiant.calibration.offset_drift import offset_drift_residual_e
from radiant.calibration.source_uniformity import (
    one_point_uniformity_residual_e,
    three_point_uniformity_residual_e,
    two_point_uniformity_residual_e,
)
from radiant.calibration.spectral_cal import spectral_cal_bias_frac
from radiant.core.chain import ChainState
from radiant.core.descriptors import T2Reflective
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import BiasTerm, NoiseTerm

logger = logging.getLogger(__name__)

# CU-346: below this in-band share of the scene-temperature blackbody's photon
# exitance, the declared temperature cannot be sourcing the collected signal
# and the Planck cal-point anchor is a stand-in. Discrimination is huge —
# ~1e-22 (VNIR at 300 K, fires) vs ~8e-7 (SWIR at 300 K, stays quiet) vs
# ~2e-5 (LWIR at 77 K lab, stays quiet) — so the exact value is uncritical;
# a diagnostic bound, not tuned physics.
_THERMAL_ANCHOR_FLOOR: float = 1e-9

#: Sentinel: cal temperatures default to 0.0 = "unset" (see _schema.py).
_UNSET = 0.0

# Canonical display units for this stage's scalar ``stage_outputs`` (CU-118).
OUTPUT_UNITS: dict[str, str] = {
    "s1_e": "e-",
    "s2_e": "e-",
    "s3_e": "e-",
    "nuc_residual_e": "e-",
    "cal_source_uniformity_e": "e-",
    "gain_drift_e": "e-",
    "offset_drift_e": "e-",
    "sigma_calibration_e": "e-",
    "sigma_total_e": "e-",
    "bias_total_frac": "",
    "calibration_nedt_K": "K",
    "internal_cal_fore_e": "e-",
    "internal_cal_fore_frac": "",
    "narcissus_fpn_e": "e-",
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
    if scheme == "three_point":
        t_mid: float = params.get("calibration.cal_temp_mid_K")
        if t_high == _UNSET or t_mid == _UNSET:
            missing = "cal_temp_high_K" if t_high == _UNSET else "cal_temp_mid_K"
            raise CalibrationConfigIncompleteError(
                "calibration.scheme = 'three_point' needs three cal points, but "
                f"calibration.{missing} is unset.\n"
                "  Why: three-point NUC corrects piecewise gain and offset at "
                "three cal-source temperatures (Gap 122 item 2).\n"
                "  Action: set cal_temp_low_K < cal_temp_mid_K < cal_temp_high_K, "
                "or use scheme = 'two_point'."
            )
        if not (t_low < t_mid < t_high):
            raise CalibrationValidationError(
                f"three-point cal temperatures must be strictly increasing, got "
                f"low = {t_low} K, mid = {t_mid} K, high = {t_high} K.\n"
                "  Why: the piecewise correction needs ordered, distinct "
                "segments; coincident or unordered points are ill-conditioned "
                "(plan §15).\n"
                "  Action: order the cal temperatures (low < mid < high)."
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


def _validate_flux_mode(scheme: str, params: ParameterSet) -> None:
    """Rule 16 for cal_point_mode = 'flux_fraction' (Gap 122 item 5).

    Flux-declared cal points carry no thermal anchor, so every
    temperature-anchored input is over-specification here — rejected, not
    ignored (a set value silently doing nothing is the CU-093 failure
    class). Drift, gain, and the internal-shutter path are temperature-free
    and validate as usual.
    """
    rejected = (
        ("calibration.cal_temp_low_K", 0.0),
        ("calibration.cal_temp_mid_K", 0.0),
        ("calibration.cal_temp_high_K", 0.0),
        ("calibration.source_temp_uncertainty_K", 0.0),
        ("calibration.source_uniformity_K", 0.0),
        ("calibration.band_center_uncertainty_um", 0.0),
        ("calibration.source_emissivity_uncertainty", 0.0),
    )
    for name, unset in rejected:
        if float(params.get(name)) != unset:
            raise CalibrationValidationError(
                f"{name} is set, but calibration.cal_point_mode = "
                "'flux_fraction'.\n"
                "  Why: a flux-declared cal point has no thermal anchor — "
                "temperature-anchored inputs (cal temperatures, source ΔT, "
                "uniformity-in-K, band-center Δλ, source Δε) have no "
                "meaning under it and would silently do nothing.\n"
                f"  Action: unset {name}, or use cal_point_mode = "
                "'temperature'."
            )
    f_low: float = params.get("calibration.cal_flux_low")
    f_high: float = params.get("calibration.cal_flux_high")
    f_mid: float = params.get("calibration.cal_flux_mid")
    if f_low == _UNSET:
        raise CalibrationConfigIncompleteError(
            f"calibration.scheme = '{scheme}' with cal_point_mode = "
            "'flux_fraction' needs a cal point, but calibration.cal_flux_low "
            "is unset.\n"
            "  Why: an active NUC scheme corrects at known cal levels.\n"
            "  Action: set cal_flux_low (a fraction of the scene signal), "
            "or calibration.scheme = 'none'."
        )
    if scheme in ("two_point", "three_point") and f_high == _UNSET:
        raise CalibrationConfigIncompleteError(
            f"calibration.scheme = '{scheme}' (flux_fraction) needs an upper "
            "cal point, but calibration.cal_flux_high is unset.\n"
            "  Why: multi-point NUC corrects between two or three levels.\n"
            "  Action: set cal_flux_high above cal_flux_low."
        )
    if scheme == "three_point" and f_mid == _UNSET:
        raise CalibrationConfigIncompleteError(
            "calibration.scheme = 'three_point' (flux_fraction) needs "
            "calibration.cal_flux_mid.\n"
            "  Why: piecewise NUC needs the middle level.\n"
            "  Action: set cal_flux_low < cal_flux_mid < cal_flux_high."
        )
    candidates = (
        f_low,
        f_mid if scheme == "three_point" else None,
        f_high if scheme != "one_point" else None,
    )
    ordered = [f for f in candidates if f is not None]
    if any(b <= a for a, b in zip(ordered, ordered[1:], strict=False)):
        raise CalibrationValidationError(
            f"flux cal points must be strictly increasing, got {ordered}.\n"
            "  Why: coincident or unordered levels are ill-conditioned "
            "(plan §15), same as the temperature form.\n"
            "  Action: order the flux fractions (low < [mid <] high)."
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
            if params.get("calibration.cal_path") != "full_aperture":
                raise CalibrationValidationError(
                    "calibration.cal_path = 'internal_shutter' with "
                    "calibration.scheme = 'none'.\n"
                    "  Why: the path mismatch is defined relative to a NUC — "
                    "with no calibration there is nothing the fore-optics "
                    "emission is excluded FROM.\n"
                    "  Action: select an active scheme, or leave cal_path = "
                    "'full_aperture'."
                )
            logger.debug("calibration: scheme=none — model off, no terms emitted")
            return state.with_stage_output("calibration", "scheme", "none").with_stage_output(
                "calibration", "enabled", False
            )

        cal_point_mode: str = params.get("calibration.cal_point_mode")
        if cal_point_mode == "flux_fraction":
            _validate_flux_mode(scheme, params)
        else:
            _validate_active_scheme(scheme, params)

        # CU-346 guard (owner-ratified 2026-09-07: guard now, flux-ratio door
        # later — Gap 122). On a reflective scene the Planck cal-point mapping
        # S(T_cal) = S_scene · Bq(T_cal)/Bq(T_scene) anchors at a temperature
        # that describes none of the collected signal: the band carries no
        # thermal photons at the declared scene temperature, so the signal is
        # solar-reflected and a physical blackbody at T_cal would deliver ~0
        # in-band. Two doors reach it: a pure-reflective descriptor
        # (T2Reflective — definitionally no thermal term), or a thermal/mixed
        # descriptor whose declared temperature emits nothing in the sensing
        # band (the scenario-1.4 shape: T1Thermal at 300 K on 0.5–0.85 µm,
        # in-band photon share ~1e-22 — the signal rides Kirchhoff-reflected
        # sunlight). The cal signals stay deterministic stand-ins (the
        # residual *structure* — plateau, √N exemption — survives; the
        # absolute level does not), so the run proceeds under a loud advisory
        # rather than silently (Rule 17).
        # The guard concerns the Planck stand-in; a flux-declared point IS
        # the door it promised (Gap 122 item 5), so flux mode skips it.
        scene_temp_guard_K: float = params.get("source.target.temperature")
        lam_min_guard_um: float = params.get("spectral_integration.filter_min_um")
        lam_max_guard_um: float = params.get("spectral_integration.filter_max_um")
        target_desc = state.stage_outputs.get("source", {}).get("target")
        thermal_frac = band_thermal_photon_fraction(
            scene_temp_guard_K, lam_min_guard_um, lam_max_guard_um
        )
        if cal_point_mode == "temperature" and (
            isinstance(target_desc, T2Reflective) or thermal_frac < _THERMAL_ANCHOR_FLOOR
        ):
            note = (
                "calibration cal points on this scene are Planck stand-ins: "
                f"a blackbody at the declared scene temperature "
                f"({scene_temp_guard_K:.1f} K) puts {thermal_frac:.1e} of its "
                f"photons into the {lam_min_guard_um:.2f}-{lam_max_guard_um:.2f} um "
                "band, so the collected signal is (solar-)reflected, not "
                "thermal, and the Planck anchor describes none of it. Residual "
                "magnitudes (and SNR/NEDT under this scheme) are "
                "structure-true but level-approximate. For a reflective "
                "scene, declare the cal points as flux fractions instead — "
                "calibration.cal_point_mode = 'flux_fraction' (the CU-346 "
                "flux-ratio door, delivered as Gap 122 item 5) — or set "
                "calibration.scheme = 'none' to silence."
            )
            warnings.warn(f"CU-346: {note}", UserWarning, stacklevel=2)
            state = state.with_stage_output("calibration", "reflective_scene_cal_note", note)

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
        # Two declaration forms (Gap 122 item 5): temperature (Planck
        # photon-radiance ratio, the v1 form) or flux_fraction (direct
        # fractions of the scene signal — integrating-sphere flat fields).
        if cal_point_mode == "flux_fraction":
            t_low = 0.0  # no thermal anchor in this mode (validated unset)
            s1_e = float(params.get("calibration.cal_flux_low")) * signal_e
        else:
            t_low = params.get("calibration.cal_temp_low_K")
            s1_e = cal_point_signal_e(
                t_cal_K=t_low,
                scene_temp_K=scene_temp_K,
                scene_signal_e=signal_e,
                lam_min_um=lam_min_um,
                lam_max_um=lam_max_um,
            )
        state = state.with_stage_output("calibration", "s1_e", s1_e)

        prnu_frac = float(det.get("precal_prnu_pct", 0.0)) / 100.0

        if scheme in ("two_point", "three_point"):
            t_high: float = (
                0.0
                if cal_point_mode == "flux_fraction"
                else params.get("calibration.cal_temp_high_K")
            )
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
            if scheme == "three_point":
                t_mid_run: float = (
                    0.0
                    if cal_point_mode == "flux_fraction"
                    else params.get("calibration.cal_temp_mid_K")
                )
                if cal_point_mode == "flux_fraction":
                    s2_e = float(params.get("calibration.cal_flux_mid")) * signal_e
                    s3_e = float(params.get("calibration.cal_flux_high")) * signal_e
                else:
                    s2_e = cal_point_signal_e(
                        t_cal_K=t_mid_run,
                        scene_temp_K=scene_temp_K,
                        scene_signal_e=signal_e,
                        lam_min_um=lam_min_um,
                        lam_max_um=lam_max_um,
                    )
                    s3_e = cal_point_signal_e(
                        t_cal_K=t_high,
                        scene_temp_K=scene_temp_K,
                        scene_signal_e=signal_e,
                        lam_min_um=lam_min_um,
                        lam_max_um=lam_max_um,
                    )
                state = state.with_stage_output("calibration", "s2_e", s2_e)
                state = state.with_stage_output("calibration", "s3_e", s3_e)
                nuc_e = three_point_residual_e(
                    signal_e=signal_e,
                    s1_e=s1_e,
                    s2_e=s2_e,
                    s3_e=s3_e,
                    nonlinearity_frac=params.get("calibration.nonlinearity_pct"),
                    full_well_e=full_well_e,
                )
                t_cal_bias_K = (t_low + t_mid_run + t_high) / 3.0
            else:
                if cal_point_mode == "flux_fraction":
                    s2_e = float(params.get("calibration.cal_flux_high")) * signal_e
                else:
                    s2_e = cal_point_signal_e(
                        t_cal_K=t_high,
                        scene_temp_K=scene_temp_K,
                        scene_signal_e=signal_e,
                        lam_min_um=lam_min_um,
                        lam_max_um=lam_max_um,
                    )
                state = state.with_stage_output("calibration", "s2_e", s2_e)
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

        # --- Source-uniformity residual (Gap 122 item 1) ------------------
        # The cal plate's spatial gradient imprints through the correction:
        # non-zero even AT the cal points, where the NUC parabola vanishes.
        dt_unif: float = params.get("calibration.source_uniformity_K")
        unif_e = 0.0
        if dt_unif > 0.0:
            d1 = cal_point_ds_dt_e_per_K(
                t_cal_K=t_low,
                scene_temp_K=scene_temp_K,
                scene_signal_e=signal_e,
                lam_min_um=lam_min_um,
                lam_max_um=lam_max_um,
            )
            if scheme == "three_point":
                d2 = cal_point_ds_dt_e_per_K(
                    t_cal_K=params.get("calibration.cal_temp_mid_K"),
                    scene_temp_K=scene_temp_K,
                    scene_signal_e=signal_e,
                    lam_min_um=lam_min_um,
                    lam_max_um=lam_max_um,
                )
                d3 = cal_point_ds_dt_e_per_K(
                    t_cal_K=t_high,
                    scene_temp_K=scene_temp_K,
                    scene_signal_e=signal_e,
                    lam_min_um=lam_min_um,
                    lam_max_um=lam_max_um,
                )
                unif_e = three_point_uniformity_residual_e(
                    signal_e=signal_e,
                    s1_e=s1_e,
                    s2_e=s2_e,
                    s3_e=s3_e,
                    delta_t_unif_K=dt_unif,
                    ds_dt_cal1_e_per_K=d1,
                    ds_dt_cal2_e_per_K=d2,
                    ds_dt_cal3_e_per_K=d3,
                )
            elif scheme == "two_point":
                d2 = cal_point_ds_dt_e_per_K(
                    t_cal_K=t_high,
                    scene_temp_K=scene_temp_K,
                    scene_signal_e=signal_e,
                    lam_min_um=lam_min_um,
                    lam_max_um=lam_max_um,
                )
                unif_e = two_point_uniformity_residual_e(
                    signal_e=signal_e,
                    s1_e=s1_e,
                    s2_e=s2_e,
                    delta_t_unif_K=dt_unif,
                    ds_dt_cal1_e_per_K=d1,
                    ds_dt_cal2_e_per_K=d2,
                )
            else:  # one_point
                unif_e = one_point_uniformity_residual_e(
                    delta_t_unif_K=dt_unif, ds_dt_cal_e_per_K=d1
                )

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

        # --- Internal-cal path mismatch (Gap 122 item 4) ------------------
        # An internal shutter blocks the fore-optics during cal, so the NUC
        # never sees their emission; it returns in operation as an offset
        # (bias, below) plus a narcissus-pattern FPN (spatial noise, here).
        cal_path: str = params.get("calibration.cal_path")
        fore_frac = 0.0
        fore_e = 0.0
        narcissus_e = 0.0
        if cal_path == "internal_shutter":
            n_fore: int = params.get("calibration.shutter_after_element")
            if n_fore < 1:
                raise CalibrationConfigIncompleteError(
                    "calibration.cal_path = 'internal_shutter' needs "
                    "calibration.shutter_after_element >= 1 (0 = unset).\n"
                    "  Why: the mismatch is the emission of the elements in "
                    "front of the shutter — the split needs its position.\n"
                    "  Action: set shutter_after_element to the number of "
                    "optical-train elements on the scene side of the flag."
                )
            opt = state.stage_outputs.get("optics", {})
            elements = opt.get("elements")
            if elements is not None and n_fore > len(elements):
                raise CalibrationValidationError(
                    f"calibration.shutter_after_element = {n_fore} exceeds the "
                    f"optical train's {len(elements)} configured elements.\n"
                    "  Why: the shutter cannot sit behind more elements than "
                    "the train holds.\n"
                    "  Action: set shutter_after_element <= the element count."
                )
            det_nearfield_e = float(det.get("nearfield_e", 0.0))
            if det_nearfield_e > 0.0:
                per_element = opt.get("nearfield_per_element")
                if per_element is None or elements is None:
                    raise CalibrationValidationError(
                        "internal_shutter cal path needs the per-element "
                        "near-field split, but the optics stage published "
                        "none for this run.\n"
                        "  Why: the mismatch is a per-element sum — a bulk "
                        "nearfield_e cannot be split without it.\n"
                        "  Action: define the optical train's elements "
                        "(near-field emission derives only from defined "
                        "elements, Gap 127) or use cal_path = 'full_aperture'."
                    )
                fore_names = tuple(e.name for e in elements[:n_fore])
                fore_frac = fore_optics_fraction(
                    per_element=per_element,
                    fore_names=fore_names,
                    lam_min_um=lam_min_um,
                    lam_max_um=lam_max_um,
                )
                fore_e = det_nearfield_e * fore_frac
            narcissus_e = params.get("calibration.narcissus_fpn_pct") * fore_e

        # --- Emit noise terms (post-scaling: sqrt(N)-exempt by position) --
        for term_name, value_e, basis in (
            ("nuc_residual", nuc_e, f"post-NUC residual ({scheme})"),
            (
                "cal_source_uniformity",
                unif_e,
                "source spatial non-uniformity imprinted at cal (Gap 122 item 1)",
            ),
            ("gain_drift", gain_drift_e, "gain drift since cal (time-linear, D4)"),
            ("offset_drift", offset_drift_e, "offset drift since cal (time-linear, D4)"),
            (
                "narcissus_fpn",
                narcissus_e,
                "narcissus-pattern FPN of the uncorrected fore-optics offset "
                "(internal-shutter cal, Gap 122 item 4)",
            ),
        ):
            if term_name == "narcissus_fpn" and narcissus_e == 0.0:
                continue  # absent, not zero-valued, when the path is full-aperture
            state = state.with_noise(
                NoiseTerm(
                    name=term_name,
                    value_e=value_e,
                    origin_frame="photoelectrons",
                    physical_basis=basis,
                    contributes_to=("spatial", "total"),
                )
            )

        sigma_cal_e = math.sqrt(
            nuc_e**2 + unif_e**2 + gain_drift_e**2 + offset_drift_e**2 + narcissus_e**2
        )
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
        d_lam: float = params.get("calibration.band_center_uncertainty_um")
        if d_lam > 0.0:
            # Gap 122 item 3: the cal absorbs the band-shift scale error at
            # its own temperature, so the surviving bias is the scene-vs-cal
            # log-derivative difference — zero at T_scene = t_cal_bias_K.
            state = state.with_bias(
                BiasTerm(
                    name="spectral_cal",
                    value_frac=spectral_cal_bias_frac(
                        delta_lam_um=d_lam,
                        t_scene_K=scene_temp_guard_K,
                        t_cal_K=t_cal_bias_K,
                        lam_min_um=lam_min_um,
                        lam_max_um=lam_max_um,
                    ),
                    origin="calibration.band_center_uncertainty_um",
                    physical_basis=(
                        "band-shift log-derivative difference, scene vs cal temperature"
                    ),
                )
            )
        if fore_e > 0.0:
            # Gap 122 item 4: the uncorrected fore-optics offset, expressed
            # as its radiance-equivalent fraction of the scene signal.
            state = state.with_bias(
                BiasTerm(
                    name="internal_cal_offset",
                    value_frac=fore_e / signal_e,
                    origin="calibration.cal_path",
                    physical_basis=(
                        "fore-optics near-field emission the internal-shutter "
                        "cal never sees (offset / scene signal)"
                    ),
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
        state = state.with_stage_output("calibration", "cal_source_uniformity_e", unif_e)
        state = state.with_stage_output("calibration", "gain_drift_e", gain_drift_e)
        state = state.with_stage_output("calibration", "offset_drift_e", offset_drift_e)
        state = state.with_stage_output("calibration", "cal_path", cal_path)
        if cal_path == "internal_shutter":
            state = state.with_stage_output("calibration", "internal_cal_fore_e", fore_e)
            state = state.with_stage_output("calibration", "internal_cal_fore_frac", fore_frac)
            state = state.with_stage_output("calibration", "narcissus_fpn_e", narcissus_e)
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

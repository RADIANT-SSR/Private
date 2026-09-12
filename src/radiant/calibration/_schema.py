"""Parameter definitions for the calibration stage (Gap 120, ADR-0012).

Per ``docs/plans/Calibration_Model_Plan.md`` §4. All defaults produce the
``scheme = "none"`` limit — today's PRNU/DSNU behavior, bit-identical.

Sentinel convention: ``cal_temp_low_K`` / ``cal_temp_high_K`` default to
0.0 = "unset" (the codebase's 0.0-unset convention — ``default=None``
would make them required for every config, breaking ``scheme = none``;
same trap the Gap 117 counting parameters documented). The stage validates
presence at evaluate time when a scheme is active.
"""

from __future__ import annotations

from radiant.core.parameters import ParameterDef

SCHEME = ParameterDef(
    name="calibration.scheme",
    description=(
        "Radiometric calibration scheme: 'none' (no calibration model — "
        "detector PRNU/DSNU act as static dispersions, today's behavior), "
        "'one_point' (offset corrected at one cal point), 'two_point' "
        "(per-pixel gain and offset corrected at two cal points; residual "
        "set by nonlinearity dispersion and drift), or 'three_point' "
        "(piecewise gain+offset through three cal points — each segment's "
        "nonlinearity parabola shrinks to that segment's span; Gap 122 "
        "item 2, owner-scoped to three points). Active schemes emit the "
        "post-NUC residual noise terms and calibration bias terms."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="none",
    enum_values=("none", "one_point", "two_point", "three_point"),
    tags=frozenset({"calibration", "scheme"}),
)

CAL_TEMP_LOW_K = ParameterDef(
    name="calibration.cal_temp_low_K",
    description=(
        "Calibration-source temperature of the (lower) cal point [K]. "
        "Required when scheme is 'one_point' or 'two_point'; 0.0 = unset. "
        "Cal-point fluxes are derived from cal temperatures through the "
        "band — never supplied directly (over-specification guard)."
    ),
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=0.0,
    bounds=(0.0, 3000.0),
    tags=frozenset({"calibration"}),
)

CAL_TEMP_HIGH_K = ParameterDef(
    name="calibration.cal_temp_high_K",
    description=(
        "Calibration-source temperature of the upper cal point [K]. "
        "Required when scheme is 'two_point' (must exceed cal_temp_low_K); "
        "0.0 = unset."
    ),
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=0.0,
    bounds=(0.0, 3000.0),
    tags=frozenset({"calibration"}),
)

CAL_TEMP_MID_K = ParameterDef(
    name="calibration.cal_temp_mid_K",
    description=(
        "Middle calibration-source temperature [K] for the 'three_point' "
        "scheme (Gap 122 item 2). Must satisfy cal_temp_low_K < cal_temp_mid_K "
        "< cal_temp_high_K; 0.0 = unset (evaluate-time validation when the "
        "scheme is active, matching the other cal points' sentinel)."
    ),
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=0.0,
    bounds=(0.0, 1000.0),
    tags=frozenset({"calibration"}),
)

NONLINEARITY_PCT = ParameterDef(
    name="calibration.nonlinearity_pct",
    description=(
        "Per-pixel quadratic-nonlinearity dispersion (1-sigma, % of the "
        "full-scale-referenced quadratic coefficient). Sets the post-NUC "
        "residual FPN amplitude under 'two_point' — the parabolic residual "
        "vanishing at both cal points (plan §3.2, D1)."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="%",
    default=0.0,
    bounds=(0.0, 100.0),
    tags=frozenset({"calibration"}),
)

TIME_SINCE_CAL_S = ParameterDef(
    name="calibration.time_since_cal_s",
    description=(
        "Elapsed time since the last calibration event. Drift terms grow "
        "linearly with this interval (time-linear v1, D4)."
    ),
    dtype=float,
    canonical_unit="s",
    input_unit="hour",
    default=0.0,
    bounds=(0.0, 8760.0),
    tags=frozenset({"calibration", "drift"}),
)

GAIN_DRIFT_FRAC_PER_S = ParameterDef(
    name="calibration.gain_drift_frac_per_s",
    description=(
        "Effective linear gain-drift rate since calibration (1-sigma "
        "fractional responsivity change per unit time; input as %/hour). "
        "Produces the signal-proportional 'gain_drift' residual term."
    ),
    dtype=float,
    canonical_unit="1/s",
    input_unit="%/hour",
    default=0.0,
    bounds=(0.0, 100.0),
    tags=frozenset({"calibration", "drift"}),
)

OFFSET_DRIFT_E_PER_S = ParameterDef(
    name="calibration.offset_drift_e_per_s",
    description=(
        "Effective linear offset-drift rate since calibration (1-sigma, "
        "electrons per unit time; input as e-/hour). Produces the "
        "signal-independent 'offset_drift' residual term."
    ),
    dtype=float,
    canonical_unit="e-/s",
    input_unit="e-/hour",
    default=0.0,
    bounds=(0.0, 1.0e9),
    tags=frozenset({"calibration", "drift"}),
)

SOURCE_UNIFORMITY_K = ParameterDef(
    name="calibration.source_uniformity_K",
    description=(
        "Calibration-source spatial non-uniformity (1-sigma) across the "
        "aperture [K] (Gap 122 item 1). Imprinted into the correction at cal "
        "time: residual FPN = dT_unif x dS/dT at the cal temperature(s), "
        "non-zero even AT the cal points (unlike the NUC nonlinearity "
        "parabola). Cavity blackbodies typically hold 0.01-0.05 K. "
        "0.0 (default) = perfectly uniform source, term off — bit-identical "
        "to the pre-Gap-122 model."
    ),
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=0.0,
    bounds=(0.0, 10.0),
    tags=frozenset({"calibration"}),
)

SOURCE_TEMP_UNCERTAINTY_K = ParameterDef(
    name="calibration.source_temp_uncertainty_K",
    description=(
        "Calibration-source temperature uncertainty (1-sigma) [K]. "
        "Becomes a radiance-scale BIAS term via the band-integrated Planck "
        "derivative at the cal temperature — accuracy budget only, never "
        "RSS'd into noise (plan §3.4/§3.5)."
    ),
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=0.0,
    bounds=(0.0, 100.0),
    tags=frozenset({"calibration", "bias"}),
)

SOURCE_EMISSIVITY_UNCERTAINTY = ParameterDef(
    name="calibration.source_emissivity_uncertainty",
    description=(
        "Calibration-source emissivity uncertainty (1-sigma, absolute). "
        "Becomes a radiance-scale BIAS term (delta-eps / eps_src) — "
        "accuracy budget only."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"calibration", "bias"}),
)

SOURCE_EMISSIVITY = ParameterDef(
    name="calibration.source_emissivity",
    description=(
        "Calibration-source emissivity (nominal). A scene-side material "
        "property of the cal source, so a legitimate independent input "
        "(Rule 5 applies to optical elements, not sources). Must be > 0 "
        "when an emissivity uncertainty is set; validated at evaluate time."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=1.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"calibration"}),
)

CAL_POINT_MODE = ParameterDef(
    name="calibration.cal_point_mode",
    description=(
        "How the NUC cal points are declared: 'temperature' (cal_temp_*_K, "
        "mapped to cal signals through the band Planck photon-radiance "
        "ratio — the v1 form) or 'flux_fraction' (cal_flux_* as fractions "
        "of the scene signal — the integrating-sphere / flat-field form, "
        "the CU-346 flux-ratio door, Gap 122 item 5). Under flux_fraction "
        "the temperature-anchored inputs (cal_temp_*_K, "
        "source_temp_uncertainty_K, source_uniformity_K, "
        "band_center_uncertainty_um, source_emissivity_uncertainty) have "
        "no anchor and are rejected as over-specification; drift, gain, "
        "and the internal-shutter path are temperature-free and flow "
        "unchanged."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="temperature",
    enum_values=("temperature", "flux_fraction"),
    tags=frozenset({"calibration", "scheme"}),
)

CAL_FLUX_LOW = ParameterDef(
    name="calibration.cal_flux_low",
    description=(
        "Lower cal point as a fraction of the scene signal "
        "(cal_point_mode = 'flux_fraction'); 0.0 = unset. Must be "
        "strictly below cal_flux_high (and cal_flux_mid, three_point)."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 10.0),
    tags=frozenset({"calibration"}),
)

CAL_FLUX_MID = ParameterDef(
    name="calibration.cal_flux_mid",
    description=(
        "Middle cal point as a fraction of the scene signal "
        "(three_point + flux_fraction only); 0.0 = unset."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 10.0),
    tags=frozenset({"calibration"}),
)

CAL_FLUX_HIGH = ParameterDef(
    name="calibration.cal_flux_high",
    description=(
        "Upper cal point as a fraction of the scene signal "
        "(cal_point_mode = 'flux_fraction'); 0.0 = unset."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.0,
    bounds=(0.0, 10.0),
    tags=frozenset({"calibration"}),
)

CAL_PATH = ParameterDef(
    name="calibration.cal_path",
    description=(
        "What the calibration view sees: 'full_aperture' (cal source fills "
        "the whole optical path — the NUC corrects every emission source; "
        "v1 behavior) or 'internal_shutter' (a flag/shutter inside the "
        "train — the NUC never sees the emission of elements in FRONT of "
        "it, which returns in operation as an uncorrected offset bias plus "
        "narcissus-pattern FPN; Gap 122 item 4, the ADR-0012 ops-level "
        "growth path). Requires an active scheme and "
        "shutter_after_element >= 1."
    ),
    dtype=str,
    canonical_unit="",
    input_unit="",
    default="full_aperture",
    enum_values=("full_aperture", "internal_shutter"),
    tags=frozenset({"calibration", "cal_path"}),
)

SHUTTER_AFTER_ELEMENT = ParameterDef(
    name="calibration.shutter_after_element",
    description=(
        "Number of optical-train elements in FRONT of the internal cal "
        "shutter (scene side) — the flag sits behind the first N elements. "
        "Those N elements' near-field emission is what the internal cal "
        "cannot correct (the flag blocks them from the cal view; the NUC "
        "corrects only the elements behind it). Required when cal_path = "
        "'internal_shutter'; 0 = unset. N equal to the train length is "
        "legal — a flag at the detector leaves the entire train "
        "uncorrected, the maximum mismatch."
    ),
    dtype=int,
    canonical_unit="",
    input_unit="",
    default=0,
    bounds=(0, 99),
    tags=frozenset({"calibration", "cal_path"}),
)

NARCISSUS_FPN_PCT = ParameterDef(
    name="calibration.narcissus_fpn_pct",
    description=(
        "Fraction of the uncorrected fore-optics offset appearing as "
        "spatial FPN (1-sigma, %) — the narcissus / vignetting pattern the "
        "internal cal imprints. Applies only under "
        "cal_path = 'internal_shutter'; the mean offset itself is the "
        "internal_cal_offset BIAS term regardless of this value."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="%",
    default=0.0,
    bounds=(0.0, 100.0),
    tags=frozenset({"calibration", "cal_path"}),
)

BAND_CENTER_UNCERTAINTY_UM = ParameterDef(
    name="calibration.band_center_uncertainty_um",
    description=(
        "Band-center wavelength uncertainty (1-sigma) [um] — spectral-cal "
        "or filter drift as a rigid band shift. Becomes a scene-temperature-"
        "dependent radiance BIAS term: the calibration absorbs the scale "
        "error at its own temperature, so the residual is the scene-vs-cal "
        "difference of band-shift log-derivatives (Gap 122 item 3) — "
        "accuracy budget only, never RSS'd into noise. Zero at "
        "T_scene = T_cal; Wien-side (short-wave) bands are most sensitive."
    ),
    dtype=float,
    canonical_unit="um",
    input_unit="um",
    default=0.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"calibration", "bias"}),
)

GAIN_UNCERTAINTY_PCT = ParameterDef(
    name="calibration.gain_uncertainty_pct",
    description=(
        "Absolute radiometric gain (responsivity-scale) uncertainty "
        "(1-sigma, %). Direct BIAS input for systems whose absolute-cal "
        "budget is known as a number — accuracy budget only."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="%",
    default=0.0,
    bounds=(0.0, 100.0),
    tags=frozenset({"calibration", "bias"}),
)

ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    SCHEME,
    CAL_TEMP_LOW_K,
    CAL_TEMP_HIGH_K,
    NONLINEARITY_PCT,
    TIME_SINCE_CAL_S,
    GAIN_DRIFT_FRAC_PER_S,
    OFFSET_DRIFT_E_PER_S,
    CAL_TEMP_MID_K,
    SOURCE_UNIFORMITY_K,
    SOURCE_TEMP_UNCERTAINTY_K,
    SOURCE_EMISSIVITY_UNCERTAINTY,
    SOURCE_EMISSIVITY,
    BAND_CENTER_UNCERTAINTY_UM,
    GAIN_UNCERTAINTY_PCT,
    CAL_PATH,
    SHUTTER_AFTER_ELEMENT,
    NARCISSUS_FPN_PCT,
    CAL_POINT_MODE,
    CAL_FLUX_LOW,
    CAL_FLUX_MID,
    CAL_FLUX_HIGH,
)

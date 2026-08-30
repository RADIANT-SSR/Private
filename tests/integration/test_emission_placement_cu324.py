"""Integration: the CU-324 emission-placement measurements against real MODTRAN.

CU-324 asked three refinement questions of the CU-321 layered-emission
machinery.  All three were measured against the delivered run set and **none
was adopted**; this module is the reproducible record of why, so the rulings
rest on pinned numbers rather than on a report nobody can re-run.

Item 1 — the ``z_em = 200 m`` downwelling proxy
    Measured on the nine-rung P-block downwelling ladder (H5 + P1–P8, measured
    hemispheric-proxy downwelling at 0/1/5/10/20/29/50/60/80 km, all at the
    48.2° diffusivity angle).  The layered replacement — the sky column's
    emergent radiance at 48.2° escaping toward the ground, ``π·L``, straight
    off the shipped :func:`SimpleAtmosphere._segment_emission_temperature_K` —
    does beat the proxy on the raw ladder (RMS |ln ratio| 2.0776 → 1.9385).
    But the decomposition below shows the whole gain belongs to the
    **emissivity exponent** (the CU-155 fitted ``D = 1.1`` → the anchor's own
    ``sec 48.2° = 1.4966``), not to the layered temperature: holding the
    exponent fixed and swapping only the temperature makes the ladder *worse*.
    Not adopted; the exponent finding is flagged for an owner ruling.

Item 2 — O₃ lumped into the well-mixed gas floor
    The 9.4–9.9 µm ozone feature is measurably mis-placed: the current form
    runs warm on every matched pair.  A split does improve it (0.1519 →
    0.1000 RMS |ln ratio|), but only through a single free parameter — the
    ozone share of the gas-floor OD — which the CU-161 region table cannot
    supply, because its 8.00–10.00 µm region is 2 µm wide and flat and
    therefore contains no identifiable ozone band.  Only the *before* side is
    pinned here (it is the side shipped code computes); the measured after
    side lives in ``docs/validation/atmosphere_modtran_parity.md`` §2.

Item 3 — grazing-arc opacity distribution
    M6–M8 were evaluated as candidate anchors and cannot discriminate: at
    85/88/89.5° from a ground site the vertical and along-arc placements differ
    by ≤ 1.2 % in band-mean thermal radiance, well under the 3–7 %
    model/MODTRAN residual there.  The R block (R1–R3) was authored into the
    run matrix as the geometry that would discriminate; the tripwire below
    fires when those decks are delivered.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.modtran import Tape7Reader
from radiant.atmosphere.near_horizon_air_mass import (
    apply_species_air_mass,
    near_horizon_species_air_mass,
)
from radiant.atmosphere.segment_simple import column_segment_optical_depth
from radiant.atmosphere.segments import ColumnSegmentSpec
from radiant.atmosphere.simple import (
    _ESKY_DIFFUSIVITY_D,
    H_AER_M,
    H_H2O_M,
    H_MOL_M,
    PROFILE_PWV_CM,
    SimpleAtmosphere,
)
from radiant.core.constants import R_EARTH_M, c, h, k_B

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_RUNS = _REPO_ROOT / "modtran" / "real_runs"
_MATRIX_CSV = _REPO_ROOT / "docs" / "plans" / "modtran_run_matrix.csv"

pytestmark = pytest.mark.skipif(not _REAL_RUNS.exists(), reason="real MODTRAN run set not staged")

_MWIR = (3.0, 5.0)
_LWIR = (8.0, 12.0)
#: The O₃ ν₂ fundamental.  Measuring the LWIR band mean alone hides this: the
#: feature is a 0.5 µm slice of a 4 µm band, so a placement change worth 20 % here
#: is worth ~3 % there.
_O3_FEATURE = (9.4, 9.9)

#: The diffusivity angle the whole downwelling ladder was run at; π·L(48.2°) is
#: the measured hemispheric-flux proxy (H5/P-block convention).
_DIFFUSIVITY_ANGLE_DEG = 48.2
_SEC_DIFFUSIVITY = 1.0 / math.cos(math.radians(_DIFFUSIVITY_ANGLE_DEG))

#: Top of the modelled column [m] — the ladder's own upper endpoint.
_H_ATM_TOP_M = 1.0e5


def _read(run: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(wavelength_um, total_transmittance, path_thermal_radiance)``."""
    native = Tape7Reader(_REAL_RUNS / f"{run}.tp7").parse()
    nu = native.wavenumber_cm1
    keep = nu > 0.0
    nu = nu[keep]
    lam = 1.0e4 / nu
    order = np.argsort(lam)
    return (
        lam[order],
        native.total_transmittance[keep][order],
        (native.path_thermal_radiance[keep] * nu**2)[order],
    )


def _band_mean(lam: np.ndarray, values: np.ndarray, lo: float, hi: float) -> float:
    band = (lam >= lo) & (lam <= hi)
    return float(np.trapezoid(values[band], lam[band]) / (hi - lo))


def _planck(lam_um: np.ndarray, t_K: float | np.ndarray) -> np.ndarray:
    """B(λ, T) [W/m²/sr/µm] longhand — independent of ``core.blackbody``."""
    lam_m = lam_um * 1.0e-6
    return 2.0 * h * c**2 / lam_m**5 / np.expm1(h * c / (lam_m * k_B * t_K)) * 1.0e-6


def _atm(profile: str) -> SimpleAtmosphere:
    return SimpleAtmosphere(
        standard_atmosphere=profile,
        precipitable_water_cm=PROFILE_PWV_CM[profile],
        visibility_km=23.0,
        aerosol_type="rural",
    )


def _rms_log(ratios: list[float]) -> float:
    return math.sqrt(float(np.mean(np.square([math.log(r) for r in ratios]))))


# ---------------------------------------------------------------------------
# Item 1 — the z_em = 200 m downwelling proxy vs the layered sky column
# ---------------------------------------------------------------------------

#: run -> lower endpoint altitude [m].  H5 is the 0 km rung (Rule 27 — not re-run
#: as a P row); P1–P8 lift it to 1/5/10/20/29/50/60/80 km.
_DOWNWELLING_LADDER: dict[str, float] = {
    "H5": 0.0,
    "P1": 1.0e3,
    "P2": 5.0e3,
    "P3": 1.0e4,
    "P4": 2.0e4,
    "P5": 2.9e4,
    "P6": 5.0e4,
    "P7": 6.0e4,
    "P8": 8.0e4,
}


def _sky_species_od(
    atm: SimpleAtmosphere, lam: np.ndarray, h_tgt_m: float
) -> dict[str, np.ndarray]:
    """Vertical per-species OD of the ``h_tgt → h_atm_top`` sky column.

    Reproduces ``SimpleAtmosphere.evaluate``'s ``od_*_sun`` block exactly — the
    column ``E_sky_thermal`` is built on.
    """
    col_mol = atm._column_length_km(h_tgt_m, _H_ATM_TOP_M, H_MOL_M)
    col_aer = atm._column_length_km(h_tgt_m, _H_ATM_TOP_M, H_AER_M)
    col_h2o = atm._column_length_km(h_tgt_m, _H_ATM_TOP_M, H_H2O_M)
    return {
        "mol": atm._rayleigh_extinction_km(lam, 0.0) * col_mol,
        "aer": atm._aerosol_extinction_km(lam, 0.0) * col_aer,
        "h2o": atm._h2o_vertical_od(lam, col_h2o),
        "gas": atm._gas_floor_vertical_od(lam, col_mol),
    }


def _e_sky_shipped(atm: SimpleAtmosphere, lam: np.ndarray, h_tgt_m: float) -> np.ndarray:
    """The shipped CU-155 form: ``(1 − e^{−D·τ_vert})·π·B(T(h + z_em))``."""
    od = _sky_species_od(atm, lam, h_tgt_m)
    od_vert = od["mol"] + od["aer"] + od["h2o"] + od["gas"]
    t_eff = atm._downwelling_effective_temperature_K(h_tgt_m)
    return -np.expm1(-_ESKY_DIFFUSIVITY_D * od_vert) * np.pi * _planck(lam, t_eff)


def _e_sky_variant(
    atm: SimpleAtmosphere, lam: np.ndarray, h_tgt_m: float, *, slant: bool, layered: bool
) -> np.ndarray:
    """``π·L`` for one corner of the 2×2 (emissivity exponent) × (temperature).

    ``slant`` swaps the fitted ``D = 1.1`` for the ladder's own
    ``sec 48.2°``; ``layered`` swaps ``T(h + z_em)`` for the CU-321 layered
    solution of the same column escaping toward the ground.
    """
    od = _sky_species_od(atm, lam, h_tgt_m)
    od_vert = od["mol"] + od["aer"] + od["h2o"] + od["gas"]
    exponent = _SEC_DIFFUSIVITY if slant else _ESKY_DIFFUSIVITY_D
    emissivity = -np.expm1(-exponent * od_vert)
    if layered:
        slant_od = {key: value * _SEC_DIFFUSIVITY for key, value in od.items()}
        t_eff: float | np.ndarray = atm._segment_emission_temperature_K(
            lam,
            h_low_m=h_tgt_m,
            h_high_m=_H_ATM_TOP_M,
            od_slant_mol=slant_od["mol"],
            od_slant_aer=slant_od["aer"],
            od_slant_h2o=slant_od["h2o"],
            od_slant_gas=slant_od["gas"],
            escape="lower",
        )
    else:
        t_eff = atm._downwelling_effective_temperature_K(h_tgt_m)
    return emissivity * np.pi * _planck(lam, t_eff)


#: Measured 2026-08-29 on the delivered ladder: RMS |ln(model/π·L_MODTRAN)| over
#: all nine rungs × both bands, per corner of the 2×2.  ``(D, z_em)`` is what
#: ships.  The ordering is the finding: the exponent carries the whole gain, and
#: the layered temperature costs against either exponent.
_LADDER_RMS = {
    ("D", "z_em"): 2.0776,
    ("sec", "z_em"): 1.9233,
    ("D", "layered"): 2.1080,
    ("sec", "layered"): 1.9385,
}


@pytest.mark.level2
def test_the_downwelling_ladder_ranks_the_four_candidate_forms() -> None:
    """All four corners of (emissivity exponent) × (emission temperature).

    The CU-324 item-1 ruling rests on the *ordering* here, not on any single
    number: ``sec+z_em`` is the best corner and ``sec+layered`` is worse than
    it, so adopting the layered downwelling would ship a form strictly worse
    than one already available.  Whichever corner wins, the layered temperature
    is the losing factor.
    """
    atm = _atm("midlat_summer")
    measured: dict[tuple[str, str], list[float]] = {key: [] for key in _LADDER_RMS}
    for run, h_tgt_m in _DOWNWELLING_LADDER.items():
        lam, _tau, l_mod = _read(run)
        for band in (_MWIR, _LWIR):
            reference = math.pi * _band_mean(lam, l_mod, *band)
            assert reference > 0.0, f"{run}: MODTRAN thermal band mean is not positive"
            for (exponent, temperature), bucket in measured.items():
                model = _e_sky_variant(
                    atm,
                    lam,
                    h_tgt_m,
                    slant=exponent == "sec",
                    layered=temperature == "layered",
                )
                bucket.append(_band_mean(lam, model, *band) / reference)

    rms = {key: _rms_log(values) for key, values in measured.items()}
    for key, expected in _LADDER_RMS.items():
        assert rms[key] == pytest.approx(expected, abs=0.002), f"{key} ladder parity moved"

    # The ruling, as assertions rather than prose.
    assert rms[("sec", "z_em")] < rms[("sec", "layered")], (
        "the layered temperature must still cost against the sec exponent"
    )
    assert rms[("D", "z_em")] < rms[("D", "layered")], (
        "the layered temperature must still cost against the fitted D exponent"
    )
    assert rms[("sec", "z_em")] < rms[("D", "z_em")], (
        "the fitted D = 1.1 exponent must still lose to the ladder's own sec 48.2°"
    )


@pytest.mark.level2
def test_the_shipped_downwelling_form_is_what_the_ladder_comparison_used() -> None:
    """``_e_sky_variant(D, z_em)`` is bit-identical to the shipped CU-155 form.

    Without this the 2×2 above could rank four forms none of which is the one
    that ships, and the ruling would be about nothing.
    """
    atm = _atm("midlat_summer")
    for run, h_tgt_m in _DOWNWELLING_LADDER.items():
        lam, _tau, _l_mod = _read(run)
        np.testing.assert_array_equal(
            _e_sky_variant(atm, lam, h_tgt_m, slant=False, layered=False),
            _e_sky_shipped(atm, lam, h_tgt_m),
            err_msg=f"{run}: the 2×2 baseline corner drifted from the shipped form",
        )


@pytest.mark.level2
def test_the_layered_downwelling_is_bounded_by_the_profile_it_integrates() -> None:
    """Sanity on the rejected candidate: it is never hotter than the proxy.

    The layered solution averages the whole sky column, the proxy reads one
    near-surface altitude, and the ICAO profile decreases with height — so the
    layered temperature can only be colder, which is precisely why it moves an
    already-under-predicting model further down.
    """
    atm = _atm("midlat_summer")
    for run, h_tgt_m in _DOWNWELLING_LADDER.items():
        lam, _tau, _l_mod = _read(run)
        proxy = atm._downwelling_effective_temperature_K(h_tgt_m)
        slant_od = {
            key: value * _SEC_DIFFUSIVITY
            for key, value in _sky_species_od(atm, lam, h_tgt_m).items()
        }
        layered = atm._segment_emission_temperature_K(
            lam,
            h_low_m=h_tgt_m,
            h_high_m=_H_ATM_TOP_M,
            od_slant_mol=slant_od["mol"],
            od_slant_aer=slant_od["aer"],
            od_slant_h2o=slant_od["h2o"],
            od_slant_gas=slant_od["gas"],
            escape="lower",
        )
        assert float(np.max(layered)) <= proxy + 1.0e-9, f"{run}: layered T_eff exceeds the proxy"


# ---------------------------------------------------------------------------
# Item 2 — the 9.6 µm ozone feature is mis-placed, warm, on every matched pair
# ---------------------------------------------------------------------------

#: run -> (escape end, profile, h_low_m, h_high_m, zeta_deg).  The CU-321 anchor
#: set, re-read in the O₃ feature rather than the whole LWIR band.
_MATCHED_PAIRS: dict[str, tuple[str, str, float, float, float]] = {
    "O1": ("upper", "midlat_summer", 0.0, 1.0e3, 0.0),
    "O2": ("upper", "midlat_summer", 0.0, 5.0e3, 0.0),
    "O3": ("upper", "midlat_summer", 0.0, 1.0e4, 48.2),
    "O4": ("upper", "midlat_summer", 0.0, 1.0e4, 60.0),
    "O5": ("upper", "midlat_summer", 0.0, 1.0e5, 48.2),
    "K1": ("lower", "midlat_summer", 0.0, 1.0e3, 0.0),
    "K3": ("lower", "midlat_summer", 0.0, 5.0e3, 0.0),
    "K5": ("lower", "midlat_summer", 0.0, 2.0e4, 0.0),
    "N4": ("lower", "midlat_summer", 0.0, 1.0e4, 48.2),
    "N9": ("lower", "midlat_summer", 0.0, 1.0e4, 60.0),
    "N10": ("lower", "midlat_summer", 0.0, 2.0e4, 60.0),
    "H1": ("lower", "us_standard", 0.0, 1.0e5, 0.0),
    "H4": ("lower", "tropical", 0.0, 1.0e5, 48.2),
    "H5": ("lower", "midlat_summer", 0.0, 1.0e5, 48.2),
}

#: Measured 2026-08-29: RMS |ln ratio| of the shipped model against MODTRAN over
#: the fourteen matched pairs, in the O₃ feature and in the whole LWIR band.  The
#: feature is three times worse than the band that contains it — the asymmetry
#: that makes the mis-placement worth a CU rather than a shrug.
_O3_FEATURE_RMS_SHIPPED = 0.1519
_LWIR_BAND_RMS_SHIPPED = 0.2611


def _model_thermal(run: str, lam: np.ndarray) -> np.ndarray:
    escape, profile, h_low, h_high, zeta_deg = _MATCHED_PAIRS[run]
    atm = _atm(profile)
    spec = ColumnSegmentSpec(h_low_m=h_low, h_high_m=h_high, zeta_low_rad=math.radians(zeta_deg))
    od, _air_mass, _lengths, species_od = column_segment_optical_depth(atm, lam, spec)
    t_eff = atm._segment_emission_temperature_K(
        lam,
        h_low_m=h_low,
        h_high_m=h_high,
        od_slant_mol=species_od["mol"],
        od_slant_aer=species_od["aer"],
        od_slant_h2o=species_od["h2o"],
        od_slant_gas=species_od["gas"],
        escape=escape,
    )
    return (1.0 - np.exp(-od)) * _planck(lam, t_eff)


@pytest.mark.level2
def test_the_ozone_feature_is_biased_warm_on_every_matched_pair() -> None:
    """9.4–9.9 µm parity of the shipped gas-floor placement.

    Every one of the fourteen pairs over-predicts, and the deep columns worst
    (O5 reaches 1.44×) — the signature of emission placed too low, i.e. too
    warm, which is exactly what lumping O₃ with the well-mixed gases at the
    pressure-broadened 4 km scale height does to a band whose real emission
    sits near 25 km.  A one-sided bias is the evidence; a two-sided scatter
    would have been noise.
    """
    ratios = []
    for run in _MATCHED_PAIRS:
        lam, _tau, l_mod = _read(run)
        ratio = _band_mean(lam, _model_thermal(run, lam), *_O3_FEATURE) / _band_mean(
            lam, l_mod, *_O3_FEATURE
        )
        ratios.append(ratio)
    assert min(ratios) > 0.80, f"an O₃-feature ratio fell out of the measured band: {min(ratios)}"
    warm = [r for r in ratios if r > 1.0]
    assert len(warm) >= 12, f"the warm bias broke up: only {len(warm)}/14 pairs over-predict"
    assert _rms_log(ratios) == pytest.approx(_O3_FEATURE_RMS_SHIPPED, abs=0.002)


@pytest.mark.level2
def test_the_ozone_feature_error_hides_inside_the_lwir_band_mean() -> None:
    """Why the CU-321 LWIR scoreboard never saw this.

    The feature is 0.5 µm of a 4 µm band, so a placement error worth 15 % there
    is worth ~3 % in the band mean the CU-321 anchors report.  This is the
    measurement that justifies anchoring item 2 on the sub-band.
    """
    lwir = []
    for run in _MATCHED_PAIRS:
        lam, _tau, l_mod = _read(run)
        lwir.append(
            _band_mean(lam, _model_thermal(run, lam), *_LWIR) / _band_mean(lam, l_mod, *_LWIR)
        )
    assert _rms_log(lwir) == pytest.approx(_LWIR_BAND_RMS_SHIPPED, abs=0.002)
    # The feature is a *sub*-band: it must be narrow enough to be masked.
    assert (_O3_FEATURE[1] - _O3_FEATURE[0]) < 0.2 * (_LWIR[1] - _LWIR[0])


# ---------------------------------------------------------------------------
# Item 3 — M6–M8 cannot discriminate; the R block is the deck that would
# ---------------------------------------------------------------------------

#: M6/M7/M8 LOS zenith [deg] — ground site, full column to 100 km.
_SST_FAN = {"M6": 85.0, "M7": 88.0, "M8": 89.5}

#: Measured 2026-08-29: model/MODTRAN band-mean thermal radiance for the shipped
#: (vertical) emission placement, ``run -> (MWIR, LWIR)``.
_SST_FAN_PARITY = {
    "M6": (1.053, 1.045),
    "M7": (1.058, 1.030),
    "M8": (1.061, 1.029),
}

#: The along-arc placement moves these band means by at most this much, in
#: |ln| — measured 2026-08-29 with the total optical depth held bit-identical.
_ALONG_ARC_MAX_LOG_SHIFT = 0.01196


def _sst_fan_thermal(run: str, lam: np.ndarray) -> np.ndarray:
    """Shipped (vertical-placement) thermal radiance of a ground-rooted grazing column."""
    atm = _atm("midlat_summer")
    r_tangent_m = R_EARTH_M * math.sin(math.radians(_SST_FAN[run]))
    col_mol = atm._column_length_km(0.0, _H_ATM_TOP_M, H_MOL_M)
    col_aer = atm._column_length_km(0.0, _H_ATM_TOP_M, H_AER_M)
    col_h2o = atm._column_length_km(0.0, _H_ATM_TOP_M, H_H2O_M)
    masses = near_horizon_species_air_mass(
        r_tangent_m,
        0.0,
        _H_ATM_TOP_M,
        col_mol_km=col_mol,
        col_aer_km=col_aer,
        col_h2o_km=col_h2o,
        scale_height_mol_m=H_MOL_M,
        scale_height_aer_m=H_AER_M,
        scale_height_h2o_m=H_H2O_M,
    )
    od_vert_mol = atm._rayleigh_extinction_km(lam, 0.0) * col_mol
    od_vert_aer = atm._aerosol_extinction_km(lam, 0.0) * col_aer
    od_vert_h2o = atm._h2o_vertical_od(lam, col_h2o)
    od_vert_gas = atm._gas_floor_vertical_od(lam, col_mol)
    od = apply_species_air_mass(
        masses,
        od_vert_mol=od_vert_mol,
        od_vert_aer=od_vert_aer,
        od_vert_h2o=od_vert_h2o,
        od_vert_gas=od_vert_gas,
    )
    t_eff = atm._segment_emission_temperature_K(
        lam,
        h_low_m=0.0,
        h_high_m=_H_ATM_TOP_M,
        od_slant_mol=od_vert_mol * masses.m_mol,
        od_slant_aer=od_vert_aer * masses.m_aer,
        od_slant_h2o=od_vert_h2o * masses.m_h2o,
        od_slant_gas=od_vert_gas * masses.m_mol,
        escape="lower",
    )
    return (1.0 - np.exp(-od)) * _planck(lam, t_eff)


@pytest.mark.level2
@pytest.mark.parametrize("run", sorted(_SST_FAN))
def test_the_sst_fan_residual_is_larger_than_the_placement_question(run: str) -> None:
    """M6–M8 cannot settle item 3: the residual swamps the effect.

    The shipped placement already sits 3–6 % from MODTRAN on this fan, while
    the entire vertical-vs-along-arc choice is worth ≤ 1.2 %.  An anchor whose
    own error exceeds the signal cannot discriminate, whichever way it lands —
    that is the item-3 gating ruling, and this is the arithmetic behind it.
    """
    lam, _tau, l_mod = _read(run)
    model = _sst_fan_thermal(run, lam)
    for band, expected in zip((_MWIR, _LWIR), _SST_FAN_PARITY[run], strict=True):
        ratio = _band_mean(lam, model, *band) / _band_mean(lam, l_mod, *band)
        assert ratio == pytest.approx(expected, abs=0.01), f"{run} placement parity moved"
        assert abs(math.log(ratio)) > _ALONG_ARC_MAX_LOG_SHIFT, (
            f"{run}: the model/MODTRAN residual has fallen to the size of the "
            "placement effect — M6–M8 may now discriminate; re-open CU-324 item 3"
        )


@pytest.mark.level2
def test_the_grazing_placement_anchor_block_is_authored_and_still_pending() -> None:
    """R1–R3 are the decks that would settle item 3 — tripwire on delivery.

    The item is gated, not declined, and the gate is these three runs.  When
    their tape7s land this fails, which is the intended prompt to do the
    comparison rather than to let an authored-but-forgotten block rot.
    """
    with _MATRIX_CSV.open(encoding="utf-8") as handle:
        rows = {row["run_id"]: row for row in csv.DictReader(handle)}
    authored = sorted(rid for rid in rows if rid.startswith("R") and rid[1:].isdigit())
    assert authored == ["R1", "R2", "R3"], f"the CU-324 anchor block changed: {authored}"

    for run_id in authored:
        row = rows[run_id]
        assert "FUTURE RUN" in row["notes"], f"{run_id} lost its FUTURE RUN marker"
        assert row["deck_builder_support"] == "tangent_transit_angle_gt_90", (
            f"{run_id}: a tangent-rooted arc needs Card-3 ANGLE = 90°, past "
            "AtmosphericGeometry's 89.5° ceiling — the Q7/Q8 precedent"
        )
        # The discriminating band is below the 11 km tropopause: above it the
        # ICAO profile is isothermal and the two placements are identical.
        assert 0.0 < float(row["h1_sensor_km"]) < 11.0, (
            f"{run_id}: an elevated rung at or above the tropopause cannot "
            "discriminate — the profile is isothermal there"
        )
        assert not (_REAL_RUNS / f"{run_id}.tp7").exists(), (
            f"{run_id} has been delivered — CU-324 item 3 is now anchorable: "
            "measure the along-arc placement against it and close the gate"
        )

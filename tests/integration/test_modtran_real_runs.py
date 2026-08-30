"""Integration: physics cross-checks over the real 2026-07-17 MODTRAN 6 run set.

These assert relationships *between* runs in the 39-run matrix
(`docs/plans/modtran_run_matrix.csv`) that no single-file parse test can
cover — the mutual consistency of the two altitude ladders, and the
airmass behaviour that confirms the Card-3 ANGLE convention (CU-065).

The runs live gitignored under ``modtran/real_runs/`` until the committed
fixture subset lands (plan §7.1), so every test here is ``skipif``-guarded
on their presence and is a no-op in CI. They are the real-data analogue of
the plan §4 "free integration test requiring no extra runs".
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.modtran import Tape7Reader

_REAL_RUNS = Path(__file__).resolve().parents[2] / "modtran" / "real_runs"

pytestmark = pytest.mark.skipif(
    not _REAL_RUNS.exists(),
    reason="real MODTRAN run set not staged (modtran/real_runs/ is gitignored "
    "until the fixture subset is committed — plan §7.1)",
)


def _band_mean_transmittance(run: str, lo_um: float, hi_um: float) -> float:
    """Mean total transmittance of ``run`` over a wavelength window [µm]."""
    wl, trans, _, _ = Tape7Reader(_REAL_RUNS / f"{run}.tp7").to_radiant_units()
    band = (wl >= lo_um) & (wl <= hi_um)
    return float(trans[band].mean())


@pytest.mark.level2
def test_cross_ladder_consistency_C_vs_G() -> None:
    """Plan §4 cross-ladder identity: transmittance is multiplicative along
    a nadir path, so τ(100→h) / τ(35→h) must be constant across target
    altitude h — namely τ(100→35 km), the shared upper column. Block C
    (midlat_summer, 35 km sensor) and Block G (same, 100 km sensor)
    therefore validate each other with no extra runs.
    """
    # (h_tgt km, Block-C run [35 km sensor], Block-G run [100 km sensor]).
    # h=0 uses A3 for the space ladder (the plan's designated G h_tgt=0 anchor).
    pairs = [
        (0, "C1", "A3"),
        (1, "C2", "G1"),
        (5, "C3", "G2"),
        (10, "C4", "G3"),
        (20, "C5", "G4"),
        (29, "C6", "G5"),
    ]
    ratios = []
    for _h, c_run, g_run in pairs:
        tau_c = _band_mean_transmittance(c_run, 10.0, 11.0)  # LWIR window
        tau_g = _band_mean_transmittance(g_run, 10.0, 11.0)
        ratios.append(tau_g / tau_c)
    ratios_arr = np.array(ratios)
    # The ratio is the 35→100 km column transmittance: near-unity in the
    # LWIR window (thin upper atmosphere) and, crucially, constant.
    assert ratios_arr.std() < 1.0e-3, f"cross-ladder ratio not constant: {ratios_arr}"
    assert np.all(ratios_arr < 1.0)  # extra column only attenuates
    assert ratios_arr.mean() == pytest.approx(0.998, abs=3.0e-3)


@pytest.mark.level2
def test_airmass_monotonicity_confirms_angle_convention() -> None:
    """CU-065 physics: the B-block zenith fan (us_standard full column at
    increasing off-nadir angle) must show transmittance *decreasing* with
    off-nadir angle — proving ANGLE=180 is the shortest (nadir) path, not
    grazing. An inverted convention would reverse the ordering.
    """
    # (run, off-nadir deg) — A1 nadir (ANGLE 180), B1/B2/B3 = 30/45/60 off.
    fan = [("A1", 0.0), ("B1", 30.0), ("B2", 45.0), ("B3", 60.0)]
    taus = [_band_mean_transmittance(run, 10.0, 12.0) for run, _ in fan]
    assert taus == sorted(taus, reverse=True), (
        f"transmittance not decreasing with off-nadir angle: {taus}"
    )
    # Beer's-law airmass cross-check at 45° off-nadir (airmass = √2):
    # τ(45°) ≈ τ_nadir**(1/cos45°) = τ_nadir**√2.
    tau_nadir, tau_45 = taus[0], taus[2]
    assert tau_45 == pytest.approx(tau_nadir ** np.sqrt(2.0), rel=0.02)


@pytest.mark.level2
def test_c_ladder_pinned_constants_match_files() -> None:
    """The committed MODTRAN_C_LADDER_TAU goldens in test_table_c_cells.py
    must equal what the staged tape7s actually contain — guards the
    pinned constants against transcription drift (Gap 39)."""
    from tests.integration.test_table_c_cells import MODTRAN_C_LADDER_TAU

    run_by_h = {1000.0: "C2", 5000.0: "C3", 10000.0: "C4", 20000.0: "C5", 29000.0: "C6"}
    for h, run in run_by_h.items():
        wl, trans, _, _ = Tape7Reader(_REAL_RUNS / f"{run}.tp7").to_radiant_units()
        band_813 = float(trans[(wl >= 8.0) & (wl <= 13.0)].mean())
        band_1012 = float(trans[(wl >= 10.0) & (wl <= 12.0)].mean())
        ref_813, ref_1012 = MODTRAN_C_LADDER_TAU[h]
        assert band_813 == pytest.approx(ref_813, abs=1e-5)
        assert band_1012 == pytest.approx(ref_1012, abs=1e-5)


# ---------------------------------------------------------------------------
# ω₀(λ, aerosol) derivation from the E-runs (Gap 38 — plan §8 criterion #4)
# ---------------------------------------------------------------------------

# Empirical band-median single-scattering albedo derived 2026-07-17 by
# inverting the simple model's own closed form against the real E-run
# flux tables:  ω₀_eff(λ) = E_diffuse(λ) / [E_TOA(λ)·cos θ_s·(1−τ_vert(λ))]
# with E_diffuse from the flux DOWN column (ground level), τ_vert from the
# paired nadir full-column tape7 (rural→A1, maritime→D2, urban→D3), and
# E_TOA from radiant.core.solar. Valid in the solar-dominated region
# (≤ 2.5 µm; thermal contamination of DOWN is negligible there — the
# owner-ratified band-limited convention, gaps.md Gap 38).
#
# aerosol -> {band: ω₀_eff}. For contrast: the simple backend's effective
# ω₀ for a space-sensor column is ≈ 1.000 in ALL of these cells (its
# extinction-weighted formula evaluates at the column mean altitude,
# where only pure-scattering molecules survive) — a 1.2–5× over-
# prediction of diffuse sky irradiance, largest for urban and in SWIR.
OMEGA0_EFF: dict[str, dict[str, float]] = {
    "rural": {"VIS": 0.791, "NIR": 0.698, "SWIR": 0.187},
    "maritime": {"VIS": 0.835, "NIR": 0.758, "SWIR": 0.339},
    "urban": {"VIS": 0.423, "NIR": 0.430, "SWIR": 0.263},
}

_OMEGA0_BANDS = {"VIS": (0.4, 0.7), "NIR": (0.7, 1.4), "SWIR": (1.4, 2.5)}
_OMEGA0_CASES = [
    ("rural", "E1", "A1"),
    ("maritime", "E3", "D2"),
    ("urban", "E4", "D3"),
]


@pytest.mark.level2
def test_omega0_eff_derivation_matches_pinned_table() -> None:
    """Re-derive OMEGA0_EFF from the staged flux + tape7 files and assert
    the committed table (Gap 38 reference; guards transcription drift)."""
    from radiant.atmosphere.modtran import ModtranFluxReader
    from radiant.core.solar import toa_solar_spectral_irradiance

    cos_s = np.cos(np.radians(30.0))
    for aerosol, flux_run, tau_run in _OMEGA0_CASES:
        wl, _e_direct, e_diffuse = ModtranFluxReader(
            _REAL_RUNS / f"{flux_run}_flux.csv"
        ).to_radiant_units()
        wl_t, tau, _, _ = Tape7Reader(_REAL_RUNS / f"{tau_run}.tp7").to_radiant_units()
        np.testing.assert_allclose(wl, wl_t)

        e_toa = toa_solar_spectral_irradiance(wl)
        denom = e_toa * cos_s * (1.0 - tau)
        good = denom > 1e-6
        omega = np.where(good, e_diffuse / np.maximum(denom, 1e-30), np.nan)

        for band, (lo, hi) in _OMEGA0_BANDS.items():
            in_band = (wl >= lo) & (wl <= hi) & good
            derived = float(np.nanmedian(omega[in_band]))
            assert derived == pytest.approx(OMEGA0_EFF[aerosol][band], abs=2e-3), (
                f"{aerosol}/{band}: derived ω₀_eff {derived:.3f} != pinned "
                f"{OMEGA0_EFF[aerosol][band]:.3f}"
            )


@pytest.mark.level2
def test_omega0_aerosol_ordering_physical() -> None:
    """Physics sanity on the pinned table: urban (soot-absorbing) is the
    darkest aerosol in the VIS/NIR; every ω₀ falls from VIS to SWIR for
    the continental types (scattering dies faster than absorption)."""
    for band in ("VIS", "NIR"):
        assert OMEGA0_EFF["urban"][band] < OMEGA0_EFF["rural"][band]
        assert OMEGA0_EFF["urban"][band] < OMEGA0_EFF["maritime"][band]
    for aerosol in ("rural", "maritime", "urban"):
        assert OMEGA0_EFF[aerosol]["SWIR"] < OMEGA0_EFF[aerosol]["VIS"]


# ---------------------------------------------------------------------------
# E_sky_thermal parity (MODTRAN_Run_Matrix_Plan §8 criterion #5)
# ---------------------------------------------------------------------------


def _band_integral(wl: np.ndarray, values: np.ndarray, lo_um: float, hi_um: float) -> float:
    """Band-integrated quantity [unit·µm] over [lo, hi] µm."""
    band = (wl >= lo_um) & (wl <= hi_um)
    return float(np.trapezoid(values[band], wl[band]))


def _resolved_esky_params(wl: np.ndarray, profile: str) -> object:
    """A resolved ``ParameterSet`` for a simple-backend ``E_sky_thermal`` read.

    Only the atmosphere entries matter to the quantity under test; everything
    else is present because ``resolve()`` requires a closed configuration.
    Shared by the two E_sky_thermal parity tests so they cannot drift apart in
    anything except the profile.
    """
    from radiant.api.session import RadiantSession
    from radiant.atmosphere.simple import PROFILE_PWV_CM

    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", profile)
    params.set("atmosphere.precipitable_water_cm", PROFILE_PWV_CM[profile])
    params.set("geometry.sensor_altitude_m", 100_000.0)
    params.set("optics.aperture_diameter_m", 0.08)
    params.set("optics.focal_length_m", 0.20)
    params.set("optics.transmission_scalar", 0.60)
    params.set("detector.pixel_pitch_x_um", 17.0)
    params.set("detector.pixel_pitch_y_um", 17.0)
    params.set("detector.qe_value", 0.55)
    params.set("detector.dark_rate_e_per_s", 1000.0)
    params.set("spectral_integration.filter_min_um", float(wl[0]))
    params.set("spectral_integration.filter_max_um", float(wl[-1]))
    params.set("spectral_integration.integration_time_s", 0.015)
    params.set("readout.read_noise_e_rms", 20.0)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)
    params.resolve()
    return params


def _modtran_esky_thermal(run: str) -> tuple[np.ndarray, np.ndarray]:
    """E_sky_thermal from an up-looking H-run: π·L_sky at the 48.2°
    diffusivity angle approximates the hemispheric downwelling flux."""
    reader = Tape7Reader(_REAL_RUNS / f"{run}.tp7")
    wl, _, l_path, _ = reader.to_radiant_units()
    return wl, np.pi * l_path


@pytest.mark.level2
def test_diffusivity_angle_matches_hemispheric_flux() -> None:
    """Methodology check: π·L_sky(48.2°) from the up-looking H2 run must
    agree with the true hemispheric DOWN flux from the E1 flux table
    (independent MODTRAN products, same us_standard profile) to within
    the textbook diffusivity-approximation error (~15%). This validates
    using H-runs as the E_sky_thermal reference at all.
    """
    from radiant.atmosphere.modtran import ModtranFluxReader

    wl_h, esky_h = _modtran_esky_thermal("H2")
    wl_f, _e_direct, e_diffuse = ModtranFluxReader(_REAL_RUNS / "E1_flux.csv").to_radiant_units()

    i_h = _band_integral(wl_h, esky_h, 8.0, 12.0)
    i_f = _band_integral(wl_f, e_diffuse, 8.0, 12.0)
    # Measured 2026-07-17: ratio = 0.849 (diffusivity angle slightly
    # under-weights the warm, opaque low-elevation sky).
    assert i_h / i_f == pytest.approx(0.85, abs=0.10)


@pytest.mark.level2
def test_esky_thermal_simple_vs_modtran_characterization() -> None:
    """Criterion #5: SimpleAtmosphere's graybody E_sky_thermal compared
    against real MODTRAN H-run downwelling (us_standard H2, tropical H4).

    RESULT (2026-07-18, CU-155 FIXED): the pre-fix deficit (~7× LWIR /
    ~25–50× MWIR for a space-sensor column, caused by T_atm_eff at
    0.5·h_sensor clamping to the 216.65 K tropopause + vertical-beam
    emissivity) is closed by the target-anchored, H-run-fit model
    E = (1 − τ_sky,vert^D)·π·B(T(h_tgt + z_em)) (see the _ESKY_*
    constants in simple.py). Band-integrated model/MODTRAN, at the fit and
    now:

                             at the fit    2026-08-29 (post-CU-324 swap)
        H2 us_standard LWIR   1.24          1.594
        H2 us_standard MWIR   0.70          0.869
        H4 tropical    LWIR   1.41          1.226
        H4 tropical    MWIR   1.34          0.928

    Two things moved these off their fit-time values: the τ recalibrations
    since (τ_sky enters the emissivity), and the CU-324 exponent swap
    (D = 1.1 → sec 48.2° = 1.50030), which raises all four. H2 and H4 are
    the two decks D = 1.1 was FITTED against, so the swap must look like a
    regression here; the criterion it was judged on is the nine-rung ladder
    below, which the fit never saw.

    The residual ±40% is the CU-161 region-flat spectral-shape fragility
    (documented in simple.py), not temperature structure. This test pins
    BOTH sides: the MODTRAN reference magnitudes (stable goldens) and the
    parity — the envelope for the regime, and the four measured points to
    ±0.005 so a drift *inside* the envelope cannot pass unnoticed, which is
    how the H4 row above reached 1.03/0.78 from 1.41/1.34 unrecorded.
    """
    import warnings as _warnings

    from radiant.atmosphere.simple import PROFILE_PWV_CM, SimpleAtmosphere
    from radiant.core.los_geometry import LineOfSightGeometry

    # (run, profile, LWIR MODTRAN golden W/m², MWIR MODTRAN golden W/m²)
    cases = [
        ("H2", "us_standard", 20.87, 2.44),
        ("H4", "tropical", 66.76, 4.11),
    ]
    for run, profile, lwir_ref, mwir_ref in cases:
        wl, esky_mod = _modtran_esky_thermal(run)

        # MODTRAN reference magnitudes are stable goldens (2026-07-17 set).
        assert _band_integral(wl, esky_mod, 8.0, 12.0) == pytest.approx(lwir_ref, rel=0.02)
        assert _band_integral(wl, esky_mod, 3.0, 5.0) == pytest.approx(mwir_ref, rel=0.02)

        # Simple backend at the matching geometry: ground target, space
        # sensor (full column), matching profile + profile-coupled PWV.
        params = _resolved_esky_params(wl, profile)

        atm = SimpleAtmosphere(
            standard_atmosphere=profile,
            precipitable_water_cm=PROFILE_PWV_CM[profile],
        )
        los = LineOfSightGeometry(
            h_tgt=0.0,
            h_sensor=100_000.0,
            theta_o=0.0,
            h_atm_top=1.0e5,
            theta_s=None,
            delta_phi=None,
        )
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            quantities = atm.evaluate(wl, los, params)

        lwir_simple = _band_integral(wl, quantities.E_sky_thermal, 8.0, 12.0)
        mwir_simple = _band_integral(wl, quantities.E_sky_thermal, 3.0, 5.0)

        # The parity envelope, re-measured 2026-08-29 after the CU-324
        # exponent swap (D = 1.1 → sec 48.2° = 1.50030): simple/MODTRAN in
        # [1.1, 1.8] LWIR, [0.7, 1.2] MWIR for these profiles.
        assert 1.1 < lwir_simple / lwir_ref < 1.8, (
            f"{run}/{profile}: LWIR E_sky_thermal ratio "
            f"{lwir_simple / lwir_ref:.3f} outside the parity "
            "envelope — if the downwelling model changed, update this "
            "record and the CU-155 Resolved entry together."
        )
        assert 0.7 < mwir_simple / mwir_ref < 1.2, (
            f"{run}/{profile}: MWIR E_sky_thermal ratio "
            f"{mwir_simple / mwir_ref:.3f} outside the parity envelope."
        )

        # The measured points themselves, pinned tighter than the envelope so a
        # silent drift inside it still fails (2026-08-29, post-swap).
        expected = {"H2": (1.594, 0.869), "H4": (1.226, 0.928)}[run]
        assert lwir_simple / lwir_ref == pytest.approx(expected[0], abs=0.005)
        assert mwir_simple / mwir_ref == pytest.approx(expected[1], abs=0.005)


# ---------------------------------------------------------------------------
# E_sky_thermal against the nine-rung downwelling ladder (CU-324 item 1)
# ---------------------------------------------------------------------------


def _modtran_esky_thermal_only(run: str) -> tuple[np.ndarray, np.ndarray]:
    """``(wavelength_um, π·L_thermal)`` — the *thermal* column alone [W/m²/µm].

    Distinct from :func:`_modtran_esky_thermal`, which returns MODTRAN's
    thermal **+ scattered** path radiance.  Against a purely thermal model
    quantity the scattered part is contamination: at the ground-rooted
    midlat_summer rungs it inflates the 3–5 µm reference by ~18 % (H5) while
    leaving 8–12 µm untouched to 3e−4.  The CU-324 ladder measurement used the
    thermal column, so this is what reproduces it.

    The ``× ν²`` factor is the same canonical conversion
    :meth:`Tape7Reader.to_radiant_units` documents (the spectral Jacobian
    ``ν²/1e4`` times the ``1e4`` W/cm² → W/m² factor), applied to the one
    column that method sums away.
    """
    native = Tape7Reader(_REAL_RUNS / f"{run}.tp7").parse()
    nu = native.wavenumber_cm1
    keep = nu > 0.0
    nu = nu[keep]
    lam = 1.0e4 / nu
    order = np.argsort(lam)
    return lam[order], np.pi * (native.path_thermal_radiance[keep] * nu**2)[order]


#: run -> target altitude [m].  H5 is the 0 km rung; P1–P8 lift it to
#: 1/5/10/20/29/50/60/80 km.  All nine are up-looking midlat_summer decks at the
#: 48.2° diffusivity angle, so π·L is the hemispheric-flux proxy throughout.
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

#: Measured 2026-08-29 with the shipped ``D = sec 48.2°``: ``run -> (MWIR, LWIR)``
#: band-integrated ``E_sky_thermal`` / ``π·L_MODTRAN``.  The retired ``D = 1.1``
#: values are in the trailing comment on each row — every rung rises by the same
#: factor family (``≈ sec/1.1`` where the column is optically thin), which is the
#: whole content of the swap.
_LADDER_PARITY: dict[str, tuple[float, float]] = {
    "H5": (1.041, 1.263),  # was (0.864, 1.020)
    "P1": (0.9735, 1.286),  # was (0.7914, 1.006)
    "P2": (0.8353, 1.558),  # was (0.6463, 1.173)
    "P3": (0.5824, 0.7057),  # was (0.4386, 0.5243)
    "P4": (0.3381, 0.2354),  # was (0.2497, 0.1733)
    "P5": (0.08183, 0.1178),  # was (0.06014, 0.08649)
    "P6": (0.008033, 0.08879),  # was (0.005891, 0.06510)
    "P7": (0.02678, 0.3655),  # was (0.01963, 0.2680)
    "P8": (2.286, 16.26),  # was (1.676, 11.92)
}

#: RMS |ln(model / π·L_MODTRAN)| over the nine rungs × both bands, and over the
#: four tropospheric rungs alone.  Measured 2026-08-29; the retired D = 1.1 gave
#: 2.0776 and 0.4167 respectively.  These two numbers are the CU-324 item-1
#: ruling's evidence, restated against the shipped code rather than a candidate.
_LADDER_RMS_COMPOSITE = 1.9233
_LADDER_RMS_TROPOSPHERIC = 0.3087
_TROPOSPHERIC_RUNGS = ("H5", "P1", "P2", "P3")


@pytest.mark.level2
def test_esky_thermal_vs_the_nine_rung_downwelling_ladder() -> None:
    """The shipped ``E_sky_thermal`` against every measured downwelling rung.

    The CU-155 fit saw two decks (H2, H4, both ground-rooted).  The P block
    added seven elevated rungs six weeks later, and CU-324 item 1 measured the
    exponent against all nine: the geometric ``sec 48.2°`` beats the fitted
    ``D = 1.1`` (composite RMS |ln ratio| 2.0776 → 1.9233; tropospheric-only
    0.4167 → 0.3087), which is the measurement the owner ruled on 2026-08-29.

    This test drives the **shipped** ``SimpleAtmosphere.evaluate`` — not a
    reimplementation — so it is the anchor for the swapped constant rather than
    a record of the study that motivated it.  Both aggregates and every
    individual rung are pinned: an exponent regression moves all eighteen ratios
    in the same direction at once, and a spectral-shape regression moves them
    apart.

    The composite RMS is dominated by P6–P8, where a 50–80 km target sees a
    near-vacuum sky and the closed form under-predicts by two to three orders of
    magnitude (P8's 16× over-prediction is the same story inverted, against a
    3e−6 W/m² reference).  The tropospheric figure is the one that describes a
    scene anybody images; both are pinned so neither can be quietly traded for
    the other.
    """
    import warnings as _warnings

    from radiant.atmosphere.simple import PROFILE_PWV_CM, SimpleAtmosphere
    from radiant.core.los_geometry import LineOfSightGeometry

    atm = SimpleAtmosphere(
        standard_atmosphere="midlat_summer",
        precipitable_water_cm=PROFILE_PWV_CM["midlat_summer"],
        visibility_km=23.0,
        aerosol_type="rural",
    )

    log_all: list[float] = []
    log_tropospheric: list[float] = []
    for run, h_tgt_m in _DOWNWELLING_LADDER.items():
        wl, esky_mod = _modtran_esky_thermal_only(run)

        # E_sky_thermal reads none of the sensor parameters; they exist only so
        # resolve() closes.  The geometry the backend uses is the LOS below.
        params = _resolved_esky_params(wl, "midlat_summer")

        los = LineOfSightGeometry(
            h_tgt=h_tgt_m,
            h_sensor=1.0e5,
            theta_o=0.0,
            h_atm_top=1.0e5,
        )
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            quantities = atm.evaluate(wl, los, params)

        for band, expected in zip(((3.0, 5.0), (8.0, 12.0)), _LADDER_PARITY[run], strict=True):
            reference = _band_integral(wl, esky_mod, *band)
            assert reference > 0.0, f"{run}: MODTRAN π·L band integral is not positive"
            ratio = _band_integral(wl, quantities.E_sky_thermal, *band) / reference
            assert ratio == pytest.approx(expected, rel=0.01), (
                f"{run} {band[0]:g}–{band[1]:g} µm E_sky_thermal parity moved: "
                f"{ratio:.5g} vs pinned {expected:.5g}"
            )
            log_all.append(math.log(ratio))
            if run in _TROPOSPHERIC_RUNGS:
                log_tropospheric.append(math.log(ratio))

    rms_all = math.sqrt(float(np.mean(np.square(log_all))))
    rms_tropospheric = math.sqrt(float(np.mean(np.square(log_tropospheric))))
    assert rms_all == pytest.approx(_LADDER_RMS_COMPOSITE, abs=0.002)
    assert rms_tropospheric == pytest.approx(_LADDER_RMS_TROPOSPHERIC, abs=0.002)
    # The swap's whole justification, as an assertion: both aggregates must stay
    # below what the retired D = 1.1 scored on this same ladder.
    assert rms_all < 2.0776
    assert rms_tropospheric < 0.4167


# ---------------------------------------------------------------------------
# Flux-file downwelling ingestion on the tape7-import path (CU-157)
# ---------------------------------------------------------------------------


@pytest.mark.level2
def test_flux_import_downwelling_matches_e1_flux_column() -> None:
    """CU-157: with the E1 flux CSV imported alongside the E1 tape7, the
    chain's sky-reflection irradiance reproduces the real MODTRAN DOWN
    column — LWIR to E_sky_thermal, VIS to E_sky_scattered — instead of the
    Gap 81 zeros. Truth anchors are the E1 DOWN band integrals read straight
    from the flux file (independent of the chain under test):

        DOWN(8–12 µm)   ≈ 24.60 W/m²   (thermal band → E_sky_thermal)
        DOWN(0.4–0.7 µm) ≈ 124.16 W/m²  (reflective band → E_sky_scattered)

    The band split at 4 µm is a labelling boundary only: the assembly
    consumes E_sky_scattered + E_sky_thermal, so the sum must equal the full
    DOWN column regardless of the split.
    """
    import warnings as _warnings

    from radiant.api.session import RadiantSession
    from radiant.atmosphere.modtran import (
        FluxImport,
        ModtranAtmosphere,
        ModtranConfig,
        Tape7Import,
    )
    from radiant.core.los_geometry import LineOfSightGeometry

    flux = FluxImport.from_file(_REAL_RUNS / "E1_flux.csv")
    # Native-grid truth anchors (independent of the chain).
    lwir_ref = _band_integral(flux.wavelength_um, flux.e_diffuse, 8.0, 12.0)
    vis_ref = _band_integral(flux.wavelength_um, flux.e_diffuse, 0.4, 0.7)
    assert lwir_ref == pytest.approx(24.60, rel=0.01)
    assert vis_ref == pytest.approx(124.16, rel=0.01)

    atm = ModtranAtmosphere(
        ModtranConfig(binary_path=Path("/nonexistent"), allow_fallback=False),
        tape7_import=Tape7Import.from_file(_REAL_RUNS / "E1.tp7"),
        flux_import=flux,
    )
    # Fine chain grid so resampling loss is small (< 1%).
    wl = np.linspace(0.4, 14.0, 4000)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("atmosphere.model", "modtran")
    params.set("geometry.sensor_altitude_m", 100_000.0)
    params.set("geometry.solar_zenith_rad", np.radians(30.0))
    params.set("optics.aperture_diameter_m", 0.08)
    params.set("optics.focal_length_m", 0.20)
    params.set("optics.transmission_scalar", 0.60)
    params.set("detector.pixel_pitch_x_um", 17.0)
    params.set("detector.pixel_pitch_y_um", 17.0)
    params.set("detector.qe_value", 0.55)
    params.set("detector.dark_rate_e_per_s", 1000.0)
    params.set("spectral_integration.filter_min_um", float(wl[0]))
    params.set("spectral_integration.filter_max_um", float(wl[-1]))
    params.set("spectral_integration.integration_time_s", 0.015)
    params.set("readout.read_noise_e_rms", 20.0)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)
    params.resolve()

    los = LineOfSightGeometry(
        h_tgt=0.0,
        h_sensor=100_000.0,
        theta_o=0.0,
        h_atm_top=1.0e5,
        theta_s=np.radians(30.0),
        delta_phi=0.0,
    )
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore")
        q = atm.evaluate(wl, los, params)

    # Thermal band routes entirely to E_sky_thermal (scattered ≈ 0 in LWIR).
    assert _band_integral(wl, q.E_sky_thermal, 8.0, 12.0) == pytest.approx(lwir_ref, rel=0.02)
    assert _band_integral(wl, q.E_sky_scattered, 8.0, 12.0) == 0.0
    # Reflective band routes entirely to E_sky_scattered (thermal ≈ 0 in VIS).
    assert _band_integral(wl, q.E_sky_scattered, 0.4, 0.7) == pytest.approx(vis_ref, rel=0.02)
    assert _band_integral(wl, q.E_sky_thermal, 0.4, 0.7) == 0.0
    # Disjoint at the 4 µm boundary and the sum reconstructs the full column.
    assert np.all(q.E_sky_scattered[wl >= 4.0] == 0.0)
    assert np.all(q.E_sky_thermal[wl < 4.0] == 0.0)
    full_ref = _band_integral(flux.wavelength_um, flux.e_diffuse, 0.4, 14.0)
    e_sum = q.E_sky_scattered + q.E_sky_thermal
    assert _band_integral(wl, e_sum, 0.4, 14.0) == pytest.approx(full_ref, rel=0.02)

"""Option C Stage 0 anchor tests — Cell 28 and Cell 58.

These are the regression anchors enforced from Stage 0 through Stage 5 of
the Option C implementation plan
([docs/Option_C_Implementation_Plan.md](../../docs/Option_C_Implementation_Plan.md)).
They assert that the full signal chain produces the same SNR, NEDT,
MTF-at-Nyquist, and at-aperture radiance (on a fixed wavelength grid) for:

* **Cell 28** — terrestrial LWIR extended scene (thermal graybody,
  midlatitude-summer atmosphere, nadir view at 2 km AGL).
* **Cell 58** — space LWIR extended scene (thermal graybody, vacuum / exo
  atmosphere, nadir view at 800 km).

Both scenarios are deterministic — no RNG is used, and ``params.resolve()``
freezes the configuration before the chain runs. Values are captured and
persisted in ``docs/option_c_baseline.md``.

If an anchor value moves, **stop** and investigate per
``docs/Option_C_Implementation_Plan.md`` "Regression Invariants" — do not
modify the tolerance.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.api.session import RadiantSession


# The fixed wavelength grid used for L_aperture captures.
# Chosen to land exactly on multiple of the integration grids below so that
# index selection is unambiguous (no interpolation).
FIXED_LAMBDA_UM = (8.0, 9.0, 10.0, 11.0, 12.0, 13.0)


def _sig_figs(x: float, n: int = 6) -> float:
    """Round ``x`` to ``n`` significant figures."""
    if not math.isfinite(x) or x == 0.0:
        return float(x)
    from math import floor, log10

    mag = floor(log10(abs(x)))
    factor = 10.0 ** (n - 1 - mag)
    return round(x * factor) / factor


def _nearest_index(wl_grid: np.ndarray, lam_um: float) -> int:
    return int(np.argmin(np.abs(wl_grid - lam_um)))


# ---------------------------------------------------------------------------
# Cell 28 — terrestrial LWIR extended
# ---------------------------------------------------------------------------

# Grid: 501 samples covering 8–13 µm gives exact 0.01 µm spacing so that every
# FIXED_LAMBDA_UM anchor lands on a grid point.
CELL28_WL = np.linspace(8.0, 13.0, 501)

# Anchor values captured on main @ 4953c90 (pre-option-c-baseline) on
# 2026-04-19. Tolerance 1e-6 per the Option C Regression Invariants table.
CELL28_EXPECTED = {
    # These are filled in by the first run and pinned here. The test below
    # actually *computes* the values and prints them; then we pin them to
    # 6 sig figs. Initially use a loose sentinel.
}

ANCHOR_TOLERANCE = 1e-6


@pytest.fixture(scope="module")
def cell28_result():
    """Run the Cell 28 anchor scenario (terrestrial LWIR extended)."""
    session = RadiantSession(wavelength_um=CELL28_WL)
    params = session.default_params()

    # Target: 300 K, ε=0.95 (Rule 5 — emissivity is an independent scene
    # property here, not an optical-element property).
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)

    # Atmosphere: simple midlat summer, terrestrial (airborne at 2 km — the
    # existing simple model treats h_tgt = 0 implicitly; the altitude below is
    # sensor altitude, which the simple backend uses for the column length).
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.sensor_altitude_m", 2000.0)

    # Optics: 0.08 m aperture, f/2.5.
    params.set("optics.aperture_diameter_m", 0.08)
    params.set("optics.focal_length_m", 0.20)
    params.set("optics.transmission_scalar", 0.60)

    # Detector: 17 µm pitch, QE 0.55, 1000 e-/s dark.
    params.set("detector.pixel_pitch_x_um", 17.0)
    params.set("detector.pixel_pitch_y_um", 17.0)
    params.set("detector.qe_value", 0.55)
    params.set("detector.dark_rate_e_per_s", 1000.0)

    # Spectral: LWIR 8–13 µm, 15 ms integration.
    params.set("spectral_integration.filter_min_um", 8.0)
    params.set("spectral_integration.filter_max_um", 13.0)
    params.set("spectral_integration.integration_time_s", 0.015)

    # Readout: 20 e- RMS read noise, 14-bit ADC, 2 e-/DN.
    params.set("readout.read_noise_e_rms", 20.0)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)

    params.resolve()
    return session.run(params)


# ---------------------------------------------------------------------------
# Cell 58 — space LWIR extended (no atmosphere)
# ---------------------------------------------------------------------------

CELL58_WL = np.linspace(8.0, 13.0, 501)


@pytest.fixture(scope="module")
def cell58_result():
    """Run the Cell 58 anchor scenario (space LWIR extended, vacuum path)."""
    session = RadiantSession(wavelength_um=CELL58_WL)
    params = session.default_params()

    # Target: 285 K (Earth surface seen from space), ε=0.98.
    params.set("source.target.temperature", 285.0)
    params.set("source.target.emissivity", 0.98)

    # Atmosphere: exo (vacuum path — τ≡1, L_path≡0).
    params.set("atmosphere.model", "exo")

    # Geometry: 800 km LEO nadir.
    params.set("geometry.sensor_altitude_m", 800000.0)
    # Stage 7 (Option C): exo atmosphere → no_atmosphere='space' sub-case,
    # which requires platform.h_sensor for the Earth-intercept precondition
    # check (matrix §7).  Same altitude as geometry.sensor_altitude_m.
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.45)
    params.set("optics.transmission_scalar", 0.62)

    # Detector: 20 µm pitch, QE 0.55.
    params.set("detector.pixel_pitch_x_um", 20.0)
    params.set("detector.pixel_pitch_y_um", 20.0)
    params.set("detector.qe_value", 0.55)
    params.set("detector.dark_rate_e_per_s", 800.0)

    # Spectral: LWIR 8–13 µm, 10 ms integration.
    params.set("spectral_integration.filter_min_um", 8.0)
    params.set("spectral_integration.filter_max_um", 13.0)
    params.set("spectral_integration.integration_time_s", 0.010)

    # Readout: 12 e- RMS read, 14-bit ADC, 2 e-/DN.
    params.set("readout.read_noise_e_rms", 12.0)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)

    params.resolve()
    return session.run(params)


# ---------------------------------------------------------------------------
# Pinned expected values (6 sig figs) captured at SHA 4953c90 on 2026-04-19.
# ---------------------------------------------------------------------------

CELL28_PINNED = {
    # Stage 4 Option C landing (2026-04-19): extended terrestrial scenes
    # no longer construct a scalar L_background from source.background.*
    # and feed it into the SpectralIntegrationStage background-shot
    # noise term.  Decision #13 pins BackgroundDescriptor to None for
    # extended terrestrial; Decision #15 documents that the legacy
    # source.background.* parameters were a nomenclature-trap proxy for
    # atmospheric path radiance (already owned by AtmosphereStage).
    # With background_e = 0, the background_shot term drops out of the
    # RSS and the SNR lifts from 5.52 (pre-Stage-4) to ~315.5.
    # L_aperture is unchanged because the target-arm radiance transport
    # is unchanged.
    "snr": 315.54933814882156,
    # NEDT repinned 2026-07-08 (Gap 43): exact band-integrated dS/dT via the
    # Planck log-derivative replaced the single-λ (band-center) Planck-factor
    # approximation. +0.29% for this LWIR cell; reduces to the old value
    # exactly in the narrow-band limit. Was 0.20598616453385415.
    # NEDT + L_aperture repinned 2026-07-09 (Gap 57): the midlat_summer
    # preset now carries its standard water column (2.92 cm) when
    # precipitable_water_cm is left at its schema default, replacing the
    # US-standard 1.4 cm. More water → lower τ, more path emission:
    # L@8 µm drops 34% (water continuum at the band edge), NEDT +0.89%
    # (was 0.20658998527586545). The SNR pin is unchanged because this
    # cell saturates (signal 3.5e8 e- clips to full well), which makes
    # snr ≈ √FWC scene-independent.
    # NEDT + L_aperture repinned 2026-07-12 (CU-088): the simple-model aerosol
    # Ångström power law is now clamped at the MWIR-LWIR boundary (5 µm), so
    # LWIR aerosol extinction is frozen at its 5 µm value instead of decaying
    # unphysically toward zero. Slightly more LWIR extinction → marginally
    # lower τ and at-aperture radiance; NEDT −0.008% (was 0.20841920600038896),
    # L_aperture −0.4% to −0.6% across the band. SNR unchanged (saturation-
    # limited). MTF unaffected (spatial). Cell 58 (vacuum) is unaffected.
    # NEDT repinned 2026-07-18 (CU-161 gas-band recalibration): the LWIR
    # water response is now curve-of-growth (super-linear continuum) and a
    # well-mixed O₃/CO₂ floor exists; at this 2 km midlat_summer column the
    # band-integrated dS/dT and noise mix shift slightly. −2.4%
    # (was 0.20840328308841266).
    "nedt_K": 0.2034629042771887,
    # MTF@Nyquist repinned 2026-07-10 (CU-003 option a): the pixel-aperture
    # kernel is now area-integrated (anti-aliased edges) instead of a binary
    # mask that quantised the rect width to the sample grid. The old kernel
    # was effectively wider → over-blurred → MTF low by ~5.6% at Nyquist.
    # Was 0.07587823.
    "mtf_at_nyquist": 0.08012242959201417,
    # L_aperture repinned 2026-07-18 (CU-161 gas-band recalibration; prior
    # repin 2026-07-12 CU-088). The calibrated region model reshapes the
    # in-band spectrum toward the real MODTRAN 6 anchors: brighter at the
    # 8–9 µm edge (the old 6.3 µm Lorentzian far-wing over-absorbed there,
    # +72% at 8 µm) and darker at 12–13 µm (the 12–14.29 µm region carries
    # the real CO₂ 15 µm wing floor + super-linear water continuum, −34%
    # at 12 µm). Band-integrated values move the anchors toward the real
    # A3/F-run band means (scenario 3.5 validation note).
    "L_aperture_W_m2_sr_um": {
        8.0: 6.643141,
        9.0: 7.193199,
        10.0: 7.751573,
        11.0: 7.477523,
        12.0: 5.112159,
        13.0: 4.690788,
    },
}

CELL58_PINNED = {
    # Stage 4 Option C landing (2026-04-19): exo atmosphere → no
    # BackgroundDescriptor for extended, so background_e = 0 and the
    # background_shot noise drops out of the RSS. SNR lifts from 6.47
    # (pre-Stage-4) to ~316.0. L_aperture is unchanged.
    "snr": 315.9745217365823,
    # NEDT repinned 2026-07-08 (Gap 43): exact band-integrated dS/dT.
    # −0.18% for this LWIR cell. Was 0.18606860088514812.
    "nedt_K": 0.18574197176729387,
    # MTF@Nyquist repinned 2026-07-10 (CU-003 option a — see Cell 28 note).
    # Was 0.06690769 (+7.9%).
    "mtf_at_nyquist": 0.07221495554327903,
    "L_aperture_W_m2_sr_um": {
        8.0: 6.485012,
        9.0: 7.268780,
        10.0: 7.541965,
        11.0: 7.438298,
        12.0: 7.091011,
        13.0: 6.606269,
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestCell28TerrestrialLWIRExtended:
    """Option C anchor: Cell 28 — terrestrial LWIR extended."""

    def test_snr(self, cell28_result) -> None:
        actual = cell28_result.metrics["snr"]
        assert actual == pytest.approx(CELL28_PINNED["snr"], rel=ANCHOR_TOLERANCE)

    def test_nedt(self, cell28_result) -> None:
        actual = cell28_result.metrics["nedt_K"]
        assert actual == pytest.approx(CELL28_PINNED["nedt_K"], rel=ANCHOR_TOLERANCE)

    def test_mtf_at_nyquist(self, cell28_result) -> None:
        actual = cell28_result.metrics["mtf_at_nyquist"]
        assert actual == pytest.approx(
            CELL28_PINNED["mtf_at_nyquist"], rel=ANCHOR_TOLERANCE, abs=1e-9
        )

    def test_L_aperture_on_fixed_grid(self, cell28_result) -> None:
        L = cell28_result.frames["at_aperture"].spectral_radiance
        wl = cell28_result.wavelength_um
        for lam, expected in CELL28_PINNED["L_aperture_W_m2_sr_um"].items():
            idx = _nearest_index(wl, lam)
            actual = float(L[idx])
            assert actual == pytest.approx(expected, rel=ANCHOR_TOLERANCE), (
                f"Cell 28 L_aperture(λ={lam} µm): expected {expected!r}, got {actual!r}"
            )


@pytest.mark.level2
class TestCell58SpaceLWIRExtended:
    """Option C anchor: Cell 58 — space LWIR extended (vacuum path)."""

    def test_snr(self, cell58_result) -> None:
        actual = cell58_result.metrics["snr"]
        assert actual == pytest.approx(CELL58_PINNED["snr"], rel=ANCHOR_TOLERANCE)

    def test_nedt(self, cell58_result) -> None:
        actual = cell58_result.metrics["nedt_K"]
        assert actual == pytest.approx(CELL58_PINNED["nedt_K"], rel=ANCHOR_TOLERANCE)

    def test_mtf_at_nyquist(self, cell58_result) -> None:
        actual = cell58_result.metrics["mtf_at_nyquist"]
        assert actual == pytest.approx(
            CELL58_PINNED["mtf_at_nyquist"], rel=ANCHOR_TOLERANCE, abs=1e-9
        )

    def test_L_aperture_on_fixed_grid(self, cell58_result) -> None:
        L = cell58_result.frames["at_aperture"].spectral_radiance
        wl = cell58_result.wavelength_um
        for lam, expected in CELL58_PINNED["L_aperture_W_m2_sr_um"].items():
            idx = _nearest_index(wl, lam)
            actual = float(L[idx])
            assert actual == pytest.approx(expected, rel=ANCHOR_TOLERANCE), (
                f"Cell 58 L_aperture(λ={lam} µm): expected {expected!r}, got {actual!r}"
            )

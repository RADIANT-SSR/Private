# RADIANT Testing and Validation Framework

**Date:** 2026-04-07
**Status:** Accepted
**Depends on:** RADIANT_Signal_Chain_Architecture.md, RADIANT_Parameter_System.md
**Scope:** Defines the test hierarchy, reference validation cases, numerical tolerances, provenance tracking, and error handling philosophy. All RADIANT code must satisfy this framework before a module is considered complete.

---

## 1. Test Hierarchy

Four levels of tests. Every level must pass before the next level is meaningful. Level 0 failures are bugs in physics fundamentals — they invalidate every result the tool has ever produced.

| Level | Name | pytest marker | Scope | Speed |
|-------|------|--------------|-------|-------|
| **0** | Physics correctness | `level0` | Single equations and constants against known-good analytic results | < 1 s per test |
| **1** | Module-level | `level1` | Individual stage or module with controlled inputs | < 10 s per test |
| **2** | End-to-end chain | `level2` | Full signal chain against multi-stage reference scenarios | < 60 s per scenario |
| — | Regression (golden) | `golden` | Full chain against frozen golden output files | < 120 s per golden |

The registered markers in `pyproject.toml` are exactly `level0`, `level1`, `level2`, and `golden` — golden regression is its own marker, **not** a "level3" (no `level3` marker exists; `--strict-markers` would reject it). All levels run in CI on every PR. Level 0–2 run in < 5 minutes total. Golden tests run in a separate CI job on main branch only (not on every PR, to avoid golden file drift blocking development).

---

## 2. Level 0: Physics Correctness Tests

These tests are **the ground truth for the entire tool**. They use no RADIANT infrastructure beyond `constants.py` and `units.py`. They test equations against literature values.

### 2.1 Planck and Stefan-Boltzmann

**Test:** Numerical integral of `Planck(T=300K, λ)` over 0.01–100 µm equals `σ × T⁴`.

```python
def test_planck_stefan_boltzmann():
    """Integral of spectral radiance over all wavelengths = σ T⁴ / π."""
    from radiant.core.constants import h, c, k_B, sigma_SB
    import numpy as np
    from scipy.integrate import quad

    T = 300.0  # K
    def planck_w_m2_sr_um(lam_um):
        lam_m = lam_um * 1e-6
        return (2 * h * c**2 / lam_m**5) / (np.exp(h * c / (lam_m * k_B * T)) - 1) * 1e-6  # W/m²/sr/µm

    integral, _ = quad(planck_w_m2_sr_um, 0.1, 200.0, limit=500)
    expected = sigma_SB * T**4 / np.pi  # W/m²/sr (Lambertian hemisphere)
    assert abs(integral - expected) / expected < 0.001  # < 0.1%
```

**Test:** Wien's displacement law: `λ_max × T = 2897.77 µm·K`.

```python
@pytest.mark.parametrize("T,expected_lam_peak_um", [
    (300, 9.659),   # LWIR
    (1000, 2.898),  # MWIR
    (6000, 0.483),  # solar
])
def test_wiens_displacement(T, expected_lam_peak_um):
    """λ_max · T = 2897.77 µm·K (CODATA 2018 Wien constant)."""
    from radiant.core.blackbody import planck_spectral_radiance
    import numpy as np
    wl = np.linspace(0.2, 30.0, 5000)
    L = planck_spectral_radiance(wl, T)
    lam_peak = wl[np.argmax(L)]
    assert abs(lam_peak - expected_lam_peak_um) / expected_lam_peak_um < 0.005  # < 0.5%
```

### 2.2 Shot Noise

**Test:** Shot noise variance equals signal (Poisson statistics).

```python
@pytest.mark.parametrize("n_signal", [100, 1000, 10000, 100000, 1_000_000])
def test_shot_noise_is_sqrt_signal(n_signal):
    """σ_shot = √(signal). This must be exact — no approximations."""
    from radiant.detector.shot_noise import shot_noise_e
    sigma = shot_noise_e(n_signal)
    assert sigma == pytest.approx(np.sqrt(n_signal), rel=1e-10)
```

### 2.3 Quantization Noise

**Test:** ADC quantization noise = LSB / √12.

```python
@pytest.mark.parametrize("lsb_e", [50, 100, 200, 500])
def test_quantization_noise(lsb_e):
    """σ_q = LSB / √12. Exact formula — no approximation."""
    from radiant.readout.adc import AnalogToDigital
    adc = AnalogToDigital(gain_e_per_dn=lsb_e, n_bits=16)
    assert adc.quantization_noise_e() == pytest.approx(lsb_e / np.sqrt(12), rel=1e-10)
```

### 2.4 Diffraction Limit

**Test:** Airy disk first dark ring at `r = 1.22 λf/D` on the focal plane. There is no closed-form `airy_first_dark_ring` helper — the PSF is computed via FFT of the complex pupil (`radiant.optics.psf_mono.compute_psf`), and the first minimum of its radial profile is located numerically (this is exactly how `optics/tests/test_diffraction.py::TestAiryFirstZero` does it):

```python
def test_airy_first_zero_location(config, psf_unaberrated):
    """First zero of the Airy pattern at r = 1.22 λf/D.
    Truth anchor: Born & Wolf, Principles of Optics, §8.5.2."""
    c = config.padded_npix // 2
    profile = psf_unaberrated[c, c:]                 # radial profile from center
    r_zero_expected = 1.21966989 * lam_m * f_m / D_m
    for i in range(1, len(profile) - 1):             # first local minimum
        if profile[i] < profile[i - 1] and profile[i] <= profile[i + 1]:
            r_min = i * config.focal_spacing_m
            break
    assert r_min == pytest.approx(r_zero_expected, rel=0.01)
```

**Test:** Optical MTF from the pupil autocorrelation (`radiant.optics.pupil_mtf`, Rule 4 — no separate `circular_aperture_mtf` exists) is 1.0 at zero frequency and 0.0 at and beyond cutoff `f_c = D / (λ f)`:

```python
def test_pupil_mtf_normalization(amplitude, phase, config):
    from radiant.optics.pupil_mtf import (
        pupil_autocorrelation_mtf_1d,
        pupil_autocorrelation_mtf_2d,
    )
    mtf_2d = pupil_autocorrelation_mtf_2d(amplitude, phase, config.padded_npix)
    freq, mtf = pupil_autocorrelation_mtf_1d(mtf_2d, config.focal_spacing_m, axis="x")
    f_cutoff = D_m / (lam_m * f_m)                   # cycles/m (focal plane)
    assert mtf[0] == pytest.approx(1.0, abs=1e-8)
    assert np.all(mtf[freq >= f_cutoff] < 1e-6)
```

### 2.5 Pixel Aperture MTF

**Test:** `MTF(f) = |sinc(f × p)|` where `p` is pixel pitch.

The pixel aperture MTF has no standalone helper — `DetectorStage` computes it inline as `np.abs(np.sinc(freq_m * pixel_pitch))` and publishes it as `mtf_pixel_aperture_x` / `mtf_pixel_aperture_y` (`detector/stage.py`). The Level 0 check therefore reads the stage's published MTF term:

```python
def test_pixel_aperture_mtf(state_after_detector, freq_m):
    """MTF at Nyquist = sinc(0.5) ≈ 0.6366. At Nyquist/2 = sinc(0.25) ≈ 0.9003."""
    import numpy as np
    p = 18e-6   # m
    f_ny = 1 / (2 * p)   # Nyquist frequency (cycles/m)
    mtf = state_after_detector.mtf_terms["mtf_pixel_aperture_x"]
    assert np.interp(f_ny, freq_m, mtf) == pytest.approx(np.sinc(0.5), rel=1e-3)
    assert np.interp(f_ny / 2, freq_m, mtf) == pytest.approx(np.sinc(0.25), rel=1e-3)
```

### 2.6 kTC Noise and CDS Cancellation

**Test:** kTC noise magnitude and exact cancellation by CDS.

```python
def test_ktc_cds_cancellation():
    """CDS completely cancels kTC noise. Without CDS, kTC = √(k_B T C) / q."""
    from radiant.detector.noise.roic import ktc_reset_noise
    from radiant.core.constants import k_B, q
    T_roic = 290      # K
    C_node = 50e-15   # F (50 fF)
    expected = np.sqrt(k_B * T_roic * C_node) / q

    # With CDS enabled: kTC contribution = 0
    assert ktc_reset_noise(C_node, T_roic, cds_enabled=True) == 0.0
    assert ktc_reset_noise(C_node, T_roic, cds_enabled=False) == pytest.approx(expected, rel=1e-6)
```

### 2.7 TDI Signal and Noise Scaling

**Test:** TDI improves SNR by exactly √N_TDI (in shot-noise-limited regime).

```python
@pytest.mark.parametrize("n_tdi", [1, 2, 4, 8, 16])
def test_tdi_snr_improvement(n_tdi):
    """N-stage TDI: signal scales as N, shot noise as √N, SNR as √N."""
    S_single = 10000.0   # e- per stage
    S_total = S_single * n_tdi
    sigma_shot = np.sqrt(S_total)   # shot-noise dominated
    snr = S_total / sigma_shot
    snr_single = S_single / np.sqrt(S_single)
    expected_improvement = np.sqrt(n_tdi)
    assert snr / snr_single == pytest.approx(expected_improvement, rel=1e-8)
```

### 2.8 Beer-Lambert Transmittance

**Test:** Simple atmosphere transmittance follows Beer-Lambert law.

There is no standalone `beer_lambert_transmittance` helper — `SimpleAtmosphere` (`radiant/atmosphere/simple.py`) computes the column-integrated optical depth per species and applies `τ = exp(−OD)` internally. The check verifies the model's transmittance against a hand-computed optical depth (this is `atmosphere/tests/test_simple.py::test_truth_anchor_1_rayleigh_only_matches_hand_calc`):

```python
def test_beer_lambert_matches_hand_calc():
    """τ(λ) = exp(-OD) with OD hand-computed from the column integral."""
    state = simple_atmosphere.build_state(...)      # Rayleigh-only configuration
    od = sigma_0 * col_mol                          # hand-computed column OD
    expected_tau = math.exp(-od)
    assert state.transmittance.values[i] == pytest.approx(expected_tau, rel=1e-12, abs=1e-12)
```

### 2.9 Encircled Energy — Airy Disk

**Test:** Airy disk EE at first dark ring = 83.8%.

```python
def test_airy_encircled_energy_at_first_dark(psf_data):
    """~84% of Airy energy within the first zero (Born & Wolf: 83.8%
    within the first dark ring). PSFData.encircled_energy uses a square
    box, so the tolerance is loose (this is
    optics/tests/test_psf.py::test_airy_84_percent)."""
    D, f, lam_m = 0.30, 1.20, 4.2e-6
    r_first_dark = 1.22 * lam_m * f / D   # radius of first dark ring (m, focal plane)
    ee = psf_data.encircled_energy(r_first_dark)
    assert ee == pytest.approx(0.84, abs=0.05)
```

(The pixel-box coupling quantity `EE_box` itself is computed by `radiant.optics.ee_box.compute_ee_box(psf, n_pixels)` from the `EffectivePSF`.)

### 2.10 Unit Conversion Roundtrip

**Test:** All defined unit conversions are invertible and consistent.

```python
def test_unit_conversion_roundtrip():
    from radiant.core.units import convert
    pairs = [
        (1.0, "deg", "rad"),
        (1.0, "urad", "rad"),
        (10.0, "ms", "s"),
        (5.0, "um", "m"),
        (600.0, "km", "m"),
    ]
    for value, from_u, to_u in pairs:
        converted = convert(value, from_u, to_u)
        roundtripped = convert(converted, to_u, from_u)
        assert roundtripped == pytest.approx(value, rel=1e-12)
```

---

## 3. Level 1: Module-Level Tests

Each physics subpackage tests its own stage in isolation, with controlled inputs (no file I/O, no other stages).

### 3.1 Module Test Requirements

Every module-level test must:
1. Construct the minimum `ParameterSet` needed for the stage under test.
2. Construct a `ChainState` that represents the stage's expected input.
3. Call the stage's `.run()` method.
4. Assert on specific fields in the returned `ChainState`.
5. Not read any file from disk (use in-memory spectral arrays or fixtures loaded in `conftest.py`).

### 3.2 Coverage Requirements

| Subpackage | Required coverage |
|-----------|------------------|
| `core/` | 95% line, 90% branch |
| Each physics stage | 85% line, 75% branch |
| `io/` | 80% line |
| `api/`, `cli/` | 75% line |

Coverage is enforced via `pytest-cov` in CI. PRs that reduce coverage require justification.

### 3.3 Key Module Tests (Non-Exhaustive)

**SourceStage — thermal emission:**
- T=300K, ε=0.95: verify at_target frame spectral radiance matches 0.95 × Planck(300K, λ)
- T=1000K, ε=1.0: verify spectral peak near 2.9 µm (Wien's law)
- Regime classification: 100 m² target at 10 km range → extended; 0.1 m² target at 10 km → point

**AtmosphereStage — MODTRAN tape7 reader:**
- Load fixture tape7; verify τ_atm(4.2 µm) ∈ [0.6, 0.9] (plausible range)
- Verify wavelength array is ascending (MODTRAN is descending wavenumber → must flip)
- Verify Jacobian conversion: W/cm²/sr/µm → W/m²/sr/µm (factor of 1e4)
- Simple model: Beer-Lambert at 10 km, 23 km visibility → τ ≈ 0.65

**OpticsStage:**
- f/# derivation: D=0.30m, f=1.20m → f/#=4.0
- EE_box for diffraction-limited unobscured aperture: verify > 0.8 for 1-pixel box
- MTF_diffraction at f=0: 1.0; at f=f_cutoff: 0.0

**DetectorStage — noise terms:**
- Signal = 10,000 e-, dark_current = 500 e-/s, t_int = 5 ms → dark = 2.5 e-; σ_dark = √2.5
- CDS enabled → kTC = 0; CDS disabled → kTC ≠ 0
- IPC α=0.0 → MTF_IPC = 1.0 everywhere

**ReadoutStage:**
- gain = 100 e-/DN, 14-bit ADC: FWC in DN = full_well / gain; saturation flag if signal > FWC
- Fowler-N read noise reduction: N=2 samples → σ_read_effective = σ_read / √2

---

## 4. Level 2: End-to-End Reference Scenarios

Ten reference scenarios with known-good results. These test the full chain but not frozen bit-for-bit outputs.

### 4.1 Scenario Table

| # | Name | Configuration | Key check | Tolerance |
|---|------|---------------|-----------|-----------|
| **E01** | MWIR blackbody, no atmosphere | T=500K, ε=1.0, no atmosphere, 0.3m aperture, 80mm focal length, 15µm pixel, QE=0.70, t_int=1ms | SNR = √(S), where S = computed photoelectrons (shot-noise limited) | SNR within 1% of √S |
| **E02** | Shot-noise limited SNR | Extended scene, increase aperture by 2× → SNR should increase by 2× (signal ∝ A², shot noise ∝ A) | SNR(2D) / SNR(D) = 2.0 | within 1% |
| **E03** | NEDT vs. analytic | T_target=300K, T_bg=290K; compute NEDT numerically; compare to (σ_total / signal) × (1 / (dL/dT × A × Ω × τ × QE × t_int / L)) | NEDT within 2% of analytic | 2% relative |
| **E04** | MODTRAN round-trip | Load midlat_summer_mwir.tape7; apply to 300K blackbody; verify at-aperture radiance is τ × L_source + L_path (at 4.2 µm) | ΔL < 0.5% relative at λ=4.2 µm | 0.5% |
| **E05** | MTF product | Compute system MTF as product of 5 terms; verify MTF_system ≤ min(individual terms) at all frequencies | Monotonic, bounded by minimum component | exact inequality |
| **E06** | Point source EE_box | Sub-resolution target (A_target → 0); verify signal scales as EE_box; EE_box → 1 as PSF → 0 | Signal = S_extended × EE_box within 1% | 1% |
| **E07** | TDI gain end-to-end | N_TDI=4; verify total signal = 4 × single-line signal; total noise = 2 × single-line noise; SNR = 2 × single-line SNR | Exact TDI scaling | 0.1% |
| **E08** | GIQE5 reference case | Published NGA GIQE5 test case: GSD=1.0m, SNR=30, RER=0.35 → NIIRS=6.0 (approx.) | NIIRS within ±0.1 of reference | ±0.1 |
| **E09** | NEDT vs. temperature sweep | NEDT as a function of T_target from 200–350K in LWIR; should have minimum near scene temperature for MWIR crossover | NEDT monotonically well-behaved; minimum at ≈ crossover temperature | qualitative check + < 5% vs. manual calculation at 300K |
| **E10** | Dark-current dominated regime | Very long integration time (t_int=1.0 s, dark=1e6 e-/s); verify σ_total dominated by √(dark × t_int) = 1000 e- (> read noise = 25 e-) | Dominant noise term = dark_current_shot; σ_dark_shot / σ_total > 0.90 | exact fraction check |

### 4.2 Additional Correctness Checks

**Wavelength grid self-consistency:** Run any scenario twice with `n_points=200` and `n_points=1000`. Key metrics (SNR, NEDT) should agree within 0.5%. This validates numerical integration convergence.

**Regime consistency:** For an extended scene (large target), verify the regime is `"extended"` and EE_box does not appear in the signal computation. For a point target (A_target < 0.01 m² at 10 km range), verify regime = `"point"` and signal scales with EE_box.

**Provenance completeness:** After any `result = sensor.evaluate()`, call `result.to_provenance_record()` and verify:
- `"radiant_version"` key is present and non-empty
- `"resolved_at"` is a valid ISO 8601 timestamp
- Every required parameter has a provenance entry
- No parameter provenance entry is `None`

---

## 5. Golden Regression Tests (`@pytest.mark.golden`)

Golden results are frozen JSON files representing the exact output of a full chain evaluation for a reference scenario. They are not updated automatically — updates require an intentional command.

### 5.1 Golden File Structure

```json
{
    "golden_version": "1",
    "radiant_version": "0.1.0",
    "config_hash": "sha256:abc123...",
    "frozen_at": "2026-04-07T14:30:00Z",
    "scenario": "mwir_leo_baseline",
    "metrics": {
        "snr": 47.312,
        "nedt": 0.02314,
        "niirs": 5.41,
        "gsd": 3.60,
        "mtf_at_nyquist": 0.422,
        "rer": 0.281
    },
    "noise_budget": {
        "photon_shot": 111.6,
        "dark_current_shot": 89.2,
        "read_noise": 25.0,
        "1_over_f": 12.0,
        "ipc_crosstalk": 8.1,
        "prnu_residual": 7.3,
        "dsnu_residual": 4.2,
        "quantization": 3.2,
        "total_rss": 263.3
    },
    "signal": {
        "photoelectrons": 12450,
        "dn": 124.5
    }
}
```

### 5.2 Golden Test Protocol

```python
def test_golden_mwir_baseline(radiant_golden):
    """Full chain against frozen golden result for MWIR LEO pushbroom baseline."""
    result = Sensor.from_yaml("tests/fixtures/mwir_leo_baseline.yaml").evaluate()
    golden = radiant_golden.load("tests/golden/mwir_leo_baseline.json")
    radiant_golden.assert_within_tolerance(result, golden)
```

The `radiant_golden` fixture loads the golden file and provides `assert_within_tolerance()`, which checks each metric against the golden value with the tolerances from §6.

### 5.3 Intentional Golden Updates

When a physics improvement legitimately changes golden results (e.g., improved MODTRAN reader, corrected Marechal formula), golden files are updated via:

```bash
# Update a specific golden file:
radiant freeze-golden tests/fixtures/mwir_leo_baseline.yaml \
    --output tests/golden/mwir_leo_baseline.json \
    --message "Fix Marechal WFE formula: Strehl now uses exact integral vs. approximation"

# Update all golden files:
radiant freeze-all-golden --message "Bump numpy from 1.26 to 2.0"
```

The `--message` flag is mandatory. It is stored in the golden JSON as `"frozen_reason"`. Golden file updates require:
1. PR with description of why the physics changed
2. At least one reviewer who is a domain expert
3. Before/after comparison table in the PR description (from `radiant compare-golden old.json new.json`)

Golden files are committed to the repository. They are not `.gitignore`d.

---

## 6. Numerical Tolerances

### 6.1 Per-Test Tolerances

| Test type | Tolerance | Rationale |
|-----------|-----------|-----------|
| Physical constants | exact (≤ 1e-12 relative) | CODATA 2018 values are exact by definition |
| Pure physics formulas (Planck, sinc, Beer-Lambert) | < 0.01% relative | Floating-point rounding only |
| Spectral integrals (∫L dλ) | < 0.1% relative | Numerical quadrature error on 500-point grid |
| Full-chain SNR, NEDT | < 1% relative | Accumulated numerical errors through chain |
| NIIRS | ± 0.05 | GIQE5 is already empirical ± 0.3 |
| MTF at specific frequency | < 0.5% relative | Interpolation + numerical PSF error |
| Noise terms individually | < 1% relative | Acceptable numerical precision |
| Golden regression (SNR, NEDT) | < 0.1% relative | Detect unexpected changes |
| Golden regression (NIIRS) | ± 0.02 | Detect rounding changes |

### 6.2 When Tests May Legitimately Fail

A physics improvement that changes results beyond tolerance is **not a test failure** — it is a golden update. The protocol in §5.3 governs.

Scenarios that require intentional golden updates:
- MODTRAN reader bug fix (incorrect Jacobian)
- Improved IPC MTF model (from sinc-based to actual kernel)
- Marechal approximation replaced with full OTF integral
- Dependency version bump (numpy ≥ 2.0 changed default float precision in `trapz`)

Tests that fail for non-physics reasons (platform, random seed, file path):
- Are bugs to fix, not golden updates
- Must never be silenced with `pytest.mark.skip` without a linked issue

---

## 7. Provenance Tracking

Every RADIANT result output must be fully reproducible from its provenance record alone.

### 7.1 What the Provenance Record Contains

```json
{
    "run_id": "a4f7c2e1-8b3d-4e9a-a0b1-2c3d4e5f6789",
    "radiant_version": "0.1.0",
    "git_commit": "abc1234def5678",
    "git_tag": "v0.1.0",
    "python_version": "3.12.3",
    "dependencies": {
        "numpy": "1.26.4",
        "scipy": "1.13.0",
        "pyyaml": "6.0.1"
    },
    "resolved_at": "2026-04-07T14:30:00.123456Z",
    "config_hash": "sha256:3a7b9c2d...",
    "input_file_hashes": {
        "sensors/baseline_mwir.yaml": "sha256:1a2b3c4d...",
        "scenarios/leo_mwir_clear.yaml": "sha256:5e6f7a8b...",
        "data/midlat_summer_mwir.tape7": "sha256:9c0d1e2f..."
    },
    "parameters": {
        "sensor.optics.aperture_diameter": {
            "value": 0.30,
            "canonical_unit": "m",
            "provenance": "config_file",
            "source": "sensors/baseline_mwir.yaml"
        },
        "sensor.optics.f_number": {
            "value": 4.0,
            "provenance": "derived",
            "derived_from": {
                "sensor.optics.focal_length": 1.20,
                "sensor.optics.aperture_diameter": 0.30
            }
        }
    },
    "active_models": {
        "atmosphere": "modtran",
        "qe_model": "hgcdte_cutoff",
        "dark_current_model": "rule07",
        "mtf_wfe_model": "marechal"
    }
}
```

### 7.2 Run ID

Every evaluation generates a UUID4 run ID. The run ID is:
- Embedded in every output file
- Logged to console at evaluation start: `[RADIANT] Run a4f7c2e1 started`
- Used to correlate provenance record with result files

### 7.3 Config Hash

The config hash is the SHA256 of the fully resolved parameter set (after all inheritance, imports, and CLI overrides are applied, before evaluation). Two runs with identical config hashes are guaranteed to produce identical results if the software version and input file hashes match.

```python
import hashlib, json
def config_hash(resolved_params: dict) -> str:
    canonical = json.dumps(resolved_params, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
```

### 7.4 Reproducibility from Provenance

Given a provenance record, a result is exactly reproducible by:

```bash
radiant reproduce provenance.json
```

This command:
1. Verifies the current RADIANT version matches `radiant_version` in the record (warn if different, continue)
2. Reconstructs the parameter set from `parameters` (bypasses config file loading)
3. Verifies input file SHA256 hashes match (error if any file has changed)
4. Runs the chain
5. Reports whether the result matches the original (within golden tolerances)

If the software version does not match, `radiant reproduce` warns but still runs. The user is responsible for verifying that the physics models have not changed between versions.

---

## 8. Error Handling Philosophy

### 8.1 Every Error Must Answer Three Questions

1. **What:** What went wrong, stated precisely. Not "parameter error" — `sensor.optics.aperture_diameter = -0.30 is invalid`.
2. **Why:** Why it's wrong. "Aperture diameter must be positive (it is a physical length)."
3. **What to do:** What the user should change. "Set sensor.optics.aperture_diameter to a positive value in meters."

The base class `RadiantError` lives in `radiant.core.exceptions` (re-exported as `radiant.RadiantError`). It is currently a plain `Exception` subclass — the structured `what / why / action / context` payload is carried by `ParameterBoundsError`, the most user-facing subclass. The other concrete subclasses (`KirchhoffViolationError`, `ModtranUnavailableError`, `Tape7ParseError`, `ConfigError`, `ElementConfigError`) carry the same information in their message strings until the carve-out is generalized.

```python
# radiant/core/exceptions.py
class RadiantError(Exception):
    """Base class for all RADIANT-defined exceptions."""

# radiant/core/parameters.py — the canonical structured form
class ParameterBoundsError(RadiantError, ValueError):
    def __init__(
        self,
        what: str,
        why: str = "",
        action: str = "",
        context: dict[str, Any] | None = None,
    ) -> None: ...
```

Concrete subclasses MAY co-inherit from a built-in exception (`ValueError`, `RuntimeError`) for back-compat with `except ValueError` / `pytest.raises(ValueError, ...)` patterns; new RADIANT exception classes SHOULD inherit from `RadiantError` only.

### 8.2 No Silent Failures

These behaviors are never acceptable:
- Returning `NaN` or `inf` without raising an exception
- Clipping a value to bounds without warning
- Defaulting to a model when the specified model fails to load
- Catching an exception and returning a placeholder value
- Logging a warning and continuing when the physics is undefined

**The rule:** If RADIANT cannot compute a physically meaningful result, it raises an exception. The user gets an error with context, not a wrong answer.

### 8.3 Validate Before Compute

The validation pipeline (type → bounds → enum → required → consistency → file) runs before any physics computation begins. A config that fails validation never reaches the chain runner. The user sees all validation errors in one pass (not fail-fast per error — collect all, report all).

Validation is cheap. Physics is expensive. Never skip validation to save time.

### 8.4 Progressive Disclosure

Error messages have two levels:

**Summary (always shown):**
```
ConfigValidationError: 2 errors in 'configs/leo_mwir_clear.yaml'
  [1] sensor.detector.operating_temp = 400 K (out of bounds: 1–300 K)
  [2] target.temperature not provided (required, no default)
```

**Detail (shown with --verbose or when requested):**
```
[1] ParameterBoundsError
    Parameter: sensor.detector.operating_temp
    Value: 400 K
    Source: sensors/baseline_mwir.yaml, line 18
    Bounds: 1 K ≤ operating_temp ≤ 300 K
    Why: HgCdTe and InSb detectors operate at cryogenic temperatures.
         300 K is the upper bound because above this, dark current is
         astronomically high (Rule 07 activation).
    Fix: Typical operating temperatures: HgCdTe 77–120 K, InSb 77 K,
         InGaAs 220–300 K, Si CMOS 230–300 K.
         For uncooled microbolometer, use material=VOx and remove this parameter.
```

Verbose mode is enabled with `-v` on CLI or `sensor.validate(verbose=True)` in the API.

### 8.5 Exception Hierarchy

Current hierarchy (matches code):

```
RadiantError (radiant.core.exceptions; re-exported as radiant.RadiantError)
├── ParameterBoundsError      (also ValueError)  — radiant.core.parameters
├── KirchhoffViolationError   (also ValueError)  — radiant.optics.element
├── ModtranUnavailableError   (also RuntimeError)— radiant.atmosphere.modtran
├── Tape7ParseError           (also ValueError)  — radiant.atmosphere.modtran
├── ConfigError                                  — radiant.io.config
└── ElementConfigError        (also ValueError)  — radiant.io.element_config
```

`RadiantError` itself is importable from `radiant` (top-level re-export) and from `radiant.core.exceptions`. Each concrete subclass is importable from the module that raises it.

The richer multi-tier hierarchy that earlier drafts of this doc described (`PhysicsError`, `PluginError`, `ReproductionError`, finer-grained `ParameterTypeError`/`ParameterEnumError`/etc.) has been deferred — see CU-NEW-01 follow-up tracking in `docs/tracking/Cleanup_Backlog.md`. The single-tier hierarchy above is the load-bearing contract today.

---

## 9. Test Infrastructure

### 9.1 Fixtures

```
tests/
├── conftest.py              # session-scoped fixtures: load tape7 once, build reference params
├── fixtures/
│   ├── sample_tape7.txt     # MODTRAN tape7 for midlat summer MWIR (4-column format)
│   ├── mwir_leo_baseline.yaml   # complete config for E01–E10 reference scenarios
│   ├── lwir_geo_stare.yaml
│   ├── vis_aerial.yaml
│   └── point_source.yaml
└── golden/
    ├── mwir_leo_baseline.json
    ├── lwir_geo_stare.json
    ├── vis_aerial.json
    └── point_source.json
```

### 9.2 Property-Based Testing (Hypothesis)

Physics invariants that should hold for all valid inputs are tested with Hypothesis:

```python
from hypothesis import given, strategies as st

@given(
    T=st.floats(min_value=50, max_value=5000),
    lam_min=st.floats(min_value=0.3, max_value=5.0),
    lam_max=st.floats(min_value=6.0, max_value=25.0),
)
def test_planck_always_positive(T, lam_min, lam_max):
    """Planck function is always positive for positive T."""
    from radiant.core.blackbody import planck_spectral_radiance
    import numpy as np
    wl = np.linspace(lam_min, lam_max, 50)
    L = planck_spectral_radiance(wl, T)
    assert np.all(L > 0)

@given(n=st.floats(min_value=0.0, max_value=1e9))
def test_shot_noise_always_nonnegative(n):
    """σ_shot = √n is non-negative and monotonic for all valid signals."""
    from radiant.detector.shot_noise import shot_noise_e
    assert shot_noise_e(n) >= 0.0
```

### 9.3 CI Configuration

```yaml
# .github/workflows/tests.yml (abridged)
jobs:
  test:
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
        os: [ubuntu-latest, macos-latest]
    steps:
      - uses: actions/setup-python
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v --cov=radiant --cov-fail-under=85
            -m "not golden"    # golden tests in separate job
  
  golden:
    needs: test
    if: github.ref == 'refs/heads/main'
    steps:
      - run: pytest tests/ -v -m golden
```

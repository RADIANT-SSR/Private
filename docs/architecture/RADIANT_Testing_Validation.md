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
    from radiant.core.constants import h, c, k_B, sigma_sb
    import numpy as np
    from scipy.integrate import quad

    T = 300.0  # K
    def planck_w_m2_sr_um(lam_um):
        lam_m = lam_um * 1e-6
        return (2 * h * c**2 / lam_m**5) / (np.exp(h * c / (lam_m * k_B * T)) - 1) * 1e-6  # W/m²/sr/µm

    integral, _ = quad(planck_w_m2_sr_um, 0.1, 200.0, limit=500)
    expected = sigma_sb * T**4 / np.pi  # W/m²/sr (Lambertian hemisphere)
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

**Test:** `MTF(f) = |sinc(f × p × √FF)|` where `p` is pixel pitch and `FF` is the areal fill factor.

The pixel aperture MTF has no standalone helper — `DetectorStage` computes it inline as `np.abs(np.sinc(freq_m * pixel_pitch * sqrt_ff))`, where `sqrt_ff = math.sqrt(detector.fill_factor)` (the photosite linear width is `pitch·√FF` for areal fill factor `FF`, CU-074), and publishes it as `mtf_pixel_aperture_x` / `mtf_pixel_aperture_y` (`detector/stage.py`, ~lines 153–162). This width matches the PSF-path pixel-aperture kernel exactly, so the two Rule-4 paths agree at `fill_factor < 1`. At `FF = 1` the √FF factor is unity and the term reduces to the plain `|sinc(f·p)|`. The Level 0 check reads the stage's published MTF term:

```python
def test_pixel_aperture_mtf(state_after_detector, freq_m):
    """FF = 1: MTF at Nyquist = sinc(0.5) ≈ 0.6366. At Nyquist/2 = sinc(0.25) ≈ 0.9003."""
    import numpy as np
    p = 18e-6   # m
    f_ny = 1 / (2 * p)   # Nyquist frequency (cycles/m); fill_factor = 1.0
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

### 3.2 Coverage

Coverage is **not gated in CI today.** `pytest-cov` is available as a dev dependency, so a contributor can run `pytest --cov=radiant --cov-report=html` locally (see CLAUDE.md "Running Tests Locally"), but no CI job passes `--cov` or `--cov-fail-under`, and there is no per-subpackage coverage threshold enforced anywhere. The `ci.yml` test jobs run `pytest -m level0/level1/level2` with `--strict-markers` only (§9.3). Do not read a coverage floor into this doc that the pipeline does not enforce.

**[DESIGN-TARGET]** A future per-subpackage coverage gate (e.g. higher bars on `core/` and `api/`, lower on `cli/`) is a reasonable target, but until a CI job actually asserts it, treat coverage as an informational local metric, not a merge gate.

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

**Provenance completeness:** After a run, call `ChainResult.to_provenance_record()` and verify (this mirrors what `tests/test_provenance.py` asserts):
- `"radiant_version"` key is present and non-empty
- `"run_id"` is a UUID4 string for a run that went through `ChainRunner.run` (`None` for a synthetic state)
- `"parameter_set"` has one entry per resolved parameter, each carrying value + unit + per-parameter provenance
- `"input_file_hashes"` is a list of `{"path", "sha256"}` records for every config file consumed

The exact key set is `run_id`, `radiant_version`, `git_commit`, `python_version`, `dependency_versions`, `parameter_set`, `input_file_hashes`, `active_models` — see §7.1.

---

## 5. Golden Regression Tests (`@pytest.mark.golden`)

Golden results are frozen JSON files representing the output of a full chain evaluation for a reference scenario. They are not updated automatically — updates require an intentional command (`scripts/update_golden.py`, §5.3). Today there is exactly one golden file: `tests/integration/golden/mwir_leo_minimal.json`, driven by `examples/mwir_leo_minimal.yaml`.

### 5.1 Golden File Structure

Each value in the real golden file is a `{value, unit, provenance}` object (not a bare number), and a top-level `_provenance` block records how the file was generated. The current shape (read `tests/integration/golden/mwir_leo_minimal.json`):

```json
{
    "_provenance": {
        "config": "examples/mwir_leo_minimal.yaml",
        "wavelength_grid": "np.linspace(3.5, 5.0, 500)",
        "chain_stages": [
            "source", "atmosphere", "optics",
            "spectral_integration", "detector", "readout", "performance"
        ],
        "generated_by": "scripts/update_golden.py",
        "notes": "CU-155 refresh (2026-07-18). ... human-readable history of every value change ...",
        "last_updated": "2026-07-20T12:52:23.144171+00:00"
    },
    "signal_e":          {"value": 956457.31579691, "unit": "e-",        "provenance": "chain output, T3Mixed routing"},
    "e_rate_per_s":      {"value": 191291463.159382, "unit": "e-/s",     "provenance": "signal_e / t_int"},
    "A_collect":         {"value": 0.07068583470577035, "unit": "m^2",   "provenance": "pi/4 * 0.30^2"},
    "Omega_pixel":       {"value": 2.25e-10, "unit": "sr",               "provenance": "(18e-6)^2 / 1.20^2"},
    "noise_shot":        {"value": 977.9863576742315, "unit": "e- RMS",  "provenance": "sqrt(signal_e)"},
    "noise_dark_shot":   {"value": 0.7071067811865476, "unit": "e- RMS", "provenance": "sqrt(dark_rate * t_int)"},
    "noise_read":        {"value": 5.0, "unit": "e- RMS",                "provenance": "readout.read_noise_e_rms"},
    "noise_quantization":{"value": 9.237604307034013, "unit": "e- RMS",  "provenance": "gain / sqrt(12)"},
    "noise_rss":         {"value": 978.0430200815521, "unit": "e- RMS",  "provenance": "RSS of the noise terms"},
    "snr":               {"value": 977.9296985496178, "unit": "dimensionless", "provenance": "signal_e_final / sigma_total_e"}
}
```

There is no `golden_version`, `config_hash`, `frozen_at`, `metrics`, `noise_budget`, or `signal` block — those were an earlier design that never shipped. The frozen fields are the scalar chain outputs (`signal_e`, `e_rate_per_s`, `A_collect`, `Omega_pixel`), the individual noise terms, their RSS, and `snr`.

### 5.2 Golden Test Protocol

There is no `radiant_golden` fixture and no `assert_within_tolerance()` helper. The golden test lives with the integration suite under `tests/integration/`, loads the JSON directly, and asserts each recorded `value` against a freshly-run chain with an explicit `pytest.approx` tolerance (§6). Shape:

```python
@pytest.mark.golden
def test_golden_mwir_leo_minimal():
    """Full chain against the frozen golden result for the MWIR LEO minimal scenario."""
    golden = json.loads(
        (GOLDEN_DIR / "mwir_leo_minimal.json").read_text(encoding="utf-8")
    )
    # ... build params from examples/mwir_leo_minimal.yaml, run RadiantSession ...
    assert snr == pytest.approx(golden["snr"]["value"], rel=1e-6)
```

### 5.3 Intentional Golden Updates

When a physics improvement legitimately changes golden results (e.g. improved MODTRAN reader, a corrected routing rule such as CU-007/CU-155), the golden file is regenerated with the dedicated script — there is no `radiant freeze-golden` CLI:

```bash
python scripts/update_golden.py --i-know-what-im-doing
```

The `--i-know-what-im-doing` flag is mandatory: without it the script prints an error and exits non-zero. The script re-runs the MWIR LEO minimal chain, logs every value that changed (old → new with relative change), preserves the human-readable `_provenance.notes` history, and rewrites `_provenance.last_updated`. A golden update requires:
1. A PR describing **why** the physics changed (the reason is also appended to `_provenance.notes`).
2. Domain-expert review of the before/after values the script logs.

Golden files are committed to the repository. They are not `.gitignore`d.

**There are two golden families, with two regeneration scripts.** The above covers the MWIR
LEO minimal golden under `tests/integration/golden/`. The **scenario GUI baselines** —
`scenarios/<persona>/<slug>/inputs/<slug>.gui.expected.json`, gated by
`tests/integration/test_gui_baselines.py` (CU-179) — regenerate with a different command:

```bash
PYTHONPATH=./src python scenarios/tools/emit_gui_yaml.py          # all scenarios
PYTHONPATH=./src python scenarios/tools/emit_gui_yaml.py 10.1     # one, by id
```

Three things about it are load-bearing:

- **Pass an id when only one scenario legitimately moved.** Regenerating all 34 hides which
  ones the change actually touched, which is the review signal.
- **`PYTHONPATH=./src` is required inside a `git worktree`.** The emitter imports `radiant`,
  and the editable install's `.pth` pins that to whichever checkout ran `pip install -e .` —
  normally the primary tree. Without it you regenerate baselines against *unfixed* library
  code and the diff looks clean. (`pytest` is immune: `pythonpath = ["src", "."]` in
  `pyproject.toml` is rootdir-relative. `ruff` and `mypy` take explicit paths. `lint-imports`
  is **not** immune — it resolves `radiant` by import, so it needs the same prefix.)
- **The emitter repoints generated inputs at their committed counterparts** and raises
  `UnreloadableBaselineError` if none exists (CU-273). A baseline that references the
  scenario's gitignored `outputs/` tree reloads only in the tree that just ran the scenario;
  `test_gui_baseline_references_only_committed_files` is the static guard against it.

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

Every RADIANT result carries a provenance record so a run's inputs and environment are recoverable. The record is produced by `ChainResult.to_provenance_record()` (`radiant/io/results.py`) and implements the contract in `RADIANT_Master_Architecture.md` §C13; `tests/test_provenance.py` pins the exact key set.

### 7.1 What the Provenance Record Contains

The real record has exactly these eight keys (copy the shape from `to_provenance_record()`):

```json
{
    "run_id": "a4f7c2e1-8b3d-4e9a-a0b1-2c3d4e5f6789",
    "radiant_version": "0.1.0",
    "git_commit": "abc1234",
    "python_version": "3.11.9",
    "dependency_versions": {
        "numpy": "1.26.4",
        "scipy": "1.13.0",
        "pyyaml": "6.0.1",
        "click": "8.1.7"
    },
    "parameter_set": {
        "optics.aperture_diameter_m": {
            "value": 0.30,
            "unit": "m",
            "provenance": "config_file"
        },
        "optics.focal_length_m": {
            "value": 1.20,
            "unit": "m",
            "provenance": "config_file"
        }
    },
    "input_file_hashes": [
        {"path": "examples/mwir_leo_minimal.yaml", "sha256": "1a2b3c4d..."}
    ],
    "active_models": [
        "source", "atmosphere", "optics",
        "spectral_integration", "detector", "readout", "performance"
    ]
}
```

Field notes (per the `to_provenance_record` docstring):
- `run_id` — UUID4 assigned at chain-runtime (`radiant.core.provenance.new_run_id`); `None` if the result came from a synthetic state that never went through `ChainRunner.run`.
- `git_commit` — short SHA of the working-tree HEAD; `"unknown"` outside a git repo.
- `dependency_versions` — `{name: version}` for the declared runtime deps (numpy, scipy, pyyaml, click).
- `parameter_set` — `{dotpath: ResolvedValue.to_dict()}` for every resolved parameter (value + unit + per-parameter provenance); empty if no `ParameterSet` was attached.
- `input_file_hashes` — an ordered **list** of `{"path", "sha256"}` records for every config file consumed via `radiant.io.config.load_config`.
- `active_models` — an ordered **list of stage names** that ran (mirrors `ChainResult.history`), not a model-id dict.

There is no `git_tag`, `resolved_at`, `config_hash`, or `dependencies` key, and `parameters`/`active_models` are not the nested-dict shapes an earlier draft described.

### 7.2 Run ID

Every chain run generates a UUID4 run ID (`radiant.core.provenance.new_run_id`), surfaced as the `run_id` provenance field and preserved across `ChainResult.save()`/`load()`. It is **not** logged to the console today (`[RADIANT] Run … started` is not implemented) — it is a provenance field only.

### 7.3 Reproducibility

Reproducibility today rests on determinism, not a dedicated tool:

- **Same inputs → same outputs.** The chain has no random component; re-running the same config on the same RADIANT version and inputs reproduces the result bit-for-bit (this is what the golden regression test asserts).
- To re-run a recorded scenario, load the same config (`examples/*.yaml`) through `RadiantSession`/`Sensor` and execute the chain again.
- The provenance record captures what an external observer needs to confirm the environment: `radiant_version`, `git_commit`, `dependency_versions`, and `input_file_hashes` (so a changed input file is detectable by hash comparison).

**[DESIGN-TARGET]** A `config_hash` (SHA256 of the fully-resolved parameter set) and a one-shot `radiant reproduce provenance.json` command that reconstructs the parameter set, re-verifies input hashes, and re-runs the chain are **not implemented** — no such CLI subcommand or hash field exists in the code. They remain a reasonable future target but must not be documented as shipped.

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
ConfigError in configs/leo_mwir_clear.yaml: sensor.detector.operating_temp = 400 K
  (out of bounds: 1–300 K)
```
(The config loader raises `radiant.io.config.ConfigError`; a bad parameter value raises `ParameterBoundsError`. There is no `ConfigValidationError` class.)

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

**[DESIGN-TARGET]** The two-level summary/detail rendering above is the intended error-presentation model. Today, RADIANT exceptions already carry the actionable `what / why / action` payload (via `ParameterBoundsError` and its structured `context`) and message strings, but there is no `sensor.validate(verbose=True)` API and no `--verbose` error-detail switch — those remain a design target, not a shipped surface.

### 8.5 Exception Hierarchy

Current hierarchy (matches code). `RadiantError` is a single-tier base — every concrete class derives directly from it, and most co-inherit the built-in exception they historically raised as (shown in parentheses) per the Rule 15 / CU-043 back-compat carve-out. `tests/test_exceptions.py` pins this set.

```
RadiantError (radiant.core.exceptions; re-exported as radiant.RadiantError)
│
├── Core / parameters
│   ├── CoreValidationError        (ValueError)   — radiant.core.exceptions
│   ├── CoreStateError             (RuntimeError) — radiant.core.exceptions
│   ├── UnknownParameterError      (KeyError)     — radiant.core.parameters
│   ├── ParameterBoundsError       (ValueError)   — radiant.core.parameters  [structured what/why/action/context]
│   └── ParameterEnumError         (ValueError)   — radiant.core.parameters
│
├── Per-stage validation / state families
│   ├── GeometrySpecificationError                — radiant.geometry.errors
│   ├── SourceValidationError      (ValueError)   — radiant.source.errors
│   ├── AtmosphereValidationError  (ValueError)   — radiant.atmosphere.errors
│   ├── AtmosphereStateError       (RuntimeError) — radiant.atmosphere.errors
│   ├── ModtranUnavailableError    (RuntimeError) — radiant.atmosphere.modtran
│   ├── Tape7ParseError            (ValueError)   — radiant.atmosphere.modtran
│   ├── OpticsValidationError      (ValueError)   — radiant.optics.errors
│   ├── KirchhoffViolationError    (ValueError)   — radiant.optics.element
│   ├── PlatformValidationError    (ValueError)   — radiant.platform.errors
│   ├── SpectralIntegrationValidationError (ValueError)   — radiant.spectral_integration.errors
│   ├── SpectralIntegrationStateError      (RuntimeError) — radiant.spectral_integration.errors
│   ├── DetectorValidationError    (ValueError)   — radiant.detector.errors
│   ├── ReadoutValidationError     (ValueError)   — radiant.readout.errors
│   └── PerformanceValidationError (ValueError)   — radiant.performance.errors
│
├── I/O
│   ├── ConfigError                               — radiant.io.config
│   └── ElementConfigError         (ValueError)   — radiant.io.element_config
│
└── API / CLI / GUI
    ├── ApiValidationError         (ValueError)   — radiant.api.errors
    ├── BatchRunnerError                          — radiant.api.batch
    ├── ErrorBudgetError                          — radiant.api.error_budget
    ├── SolveBracketError                         — radiant.api.solve
    ├── CalibrationAnalysisError                  — radiant.api.calibration_analysis
    ├── MtfComparisonError                        — radiant.api.compare
    ├── ComparisonError                           — radiant.api.compare
    ├── OperationCancelledError                   — radiant.api._progress
    └── GuiValidationError         (ValueError)   — radiant.gui.errors
```

`RadiantError` itself is importable from `radiant` (top-level re-export) and from `radiant.core.exceptions`. Each concrete subclass is importable from the module that raises it. Catching `RadiantError` catches every framework-defined error while letting unrelated bugs (`KeyError`, `AttributeError` from a buggy stage) propagate.

---

## 9. Test Infrastructure

### 9.1 Test Layout and Fixtures

Tests live in three places (there is no top-level `tests/conftest.py`, no `tests/fixtures/` tree, and no `tests/golden/` directory):

```
src/radiant/<stage>/tests/       # module-local Level 0 / Level 1 tests + fixtures,
                                 #   co-located with the stage they exercise
tests/                           # cross-cutting tests: exceptions, provenance,
                                 #   public-API surface (test_exceptions.py,
                                 #   test_provenance.py, ...)
tests/integration/               # Level 2 full-chain tests
tests/integration/golden/        # frozen golden data
    └── mwir_leo_minimal.json    #   the single current golden file
```

Fixtures are defined locally in the test modules / package-level `conftest.py` files that need them (e.g. a stage's own `src/radiant/<stage>/tests/conftest.py`), not in one session-scoped root conftest. This mirrors the "How to Find Things" table in `CLAUDE.md`.

### 9.2 Property-Based Testing

**[DESIGN-TARGET]** `hypothesis` is declared as a dev dependency in `pyproject.toml`, but it has **zero imports** anywhere in `src/` or `tests/` — no property-based tests exist today. Physics invariants (Planck positivity, `σ_shot = √n ≥ 0`, MTF ∈ [0, 1], etc.) are currently exercised by parametrized `level0` tests, not by generated inputs. Adopting Hypothesis for these invariants is a reasonable future target; until a test actually imports it, this section describes an aspiration, not shipped coverage. (Tracked as a cleanup item — the unused dependency should either be used or dropped.)

### 9.3 CI Configuration

The only CI workflow is `.github/workflows/ci.yml`. It runs on push/PR to `main` (and `workflow_dispatch`), on a single interpreter (Python 3.11, `ubuntu-latest`) — there is no Python 3.11 × 3.12 or ubuntu × macos matrix, and no `--cov` / `--cov-fail-under` gate. The jobs are:

| Job | What it runs |
|-----|--------------|
| `static` | `ruff check src/`; `ruff format --check src/`; `mypy --strict src/radiant/core src/radiant/api`; `lint-imports --config pyproject.toml`; `python scripts/check_org_rules.py`; `python scripts/check_physics_conversions.py`; `python scripts/check_approx_tolerances.py` |
| `fast-tests` | `pytest -m level0 --strict-markers -q` then `pytest -m level1 --strict-markers -q` |
| `integration-tests` | `pytest -m level2 --strict-markers -q` (needs `fast-tests`) |
| `gui-tests` | Geometry GUI v2 suite under `xvfb-run` (needs `fast-tests`; installs Qt/VTK system libs + `dev_tools/geometry_gui_v2`) |
| `golden` | `pytest -m golden --strict-markers -q` — **main only** (`if: github.event_name == 'push' || github.event_name == 'workflow_dispatch'`), so golden drift never blocks a PR |

The golden job being main-only is what §1 refers to when it says golden tests run in a separate job on the main branch rather than on every PR.

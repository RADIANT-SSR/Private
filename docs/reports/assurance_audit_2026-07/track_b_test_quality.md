# Track B — Test-Quality Audit

Status: Complete
Produced by: two read-only audit agents, 2026-07-22. Dispositions: see findings.md.
Scope B1: src/radiant/{optics,platform,performance,spectral_integration}/tests/
Scope B2: src/radiant/{core,source,atmosphere,detector,readout,geometry}/tests/ (incl. source/converters/tests)

Audit criteria (per CLAUDE.md): tests must use known-good analytic values, not values computed
by other RADIANT code; every pytest.approx must carry explicit rel=/abs=; a test is weak if it
would still pass against a gutted implementation.

---

# B1 — optics / platform / performance / spectral_integration (34 files, ~13.7k lines)

Overall assessment: an unusually strong test suite. Most files carry genuine analytic anchors
(Airy first zero via Born & Wolf, Bessel cross-check, Maréchal Strehl, Kolmogorov hand values,
cavity-model hand calculations, GIQE sensitivity vs finite differences, ROC vs Φ(SNR/√2)), and
tolerance discipline is near-universal. Findings below are the exceptions that survived
verification.

## B1 Findings

### B1-1. GIQE-5 coefficients are never pinned — hand-calc test uses the code's own constants
- File: `src/radiant/performance/tests/test_giqe.py:17,28-38` (with `src/radiant/performance/giqe.py:25-30`)
- Category: self-referential / gut-proof — **Severity: High**
- Evidence: `test_hand_calculation` imports `C0..C5` from the implementation and rebuilds
  `expected` from them, so it verifies only formula *structure*; the three "published GIQE-5
  case" tests (lines 41-57) assert only 2-NIIRS-wide windows (e.g. `7.0 < niirs < 9.0`), and no
  test anywhere asserts `C0 == 9.57`, `C3 == 1.559`, etc. A silent edit of `C5` (-0.01 → -0.1)
  or `C3` (1.559 → 1.0) passes the entire file; only a gross sign flip in `C1` would trip the
  range checks.
- Strengthen: pin the six coefficients to their literature values in one test and/or assert one
  full NIIRS value computed by hand with numeric literals, not imported constants.

### B1-2. NEP ↔ noise-electrons converter has no absolute anchor — a λ unit slip passes
- File: `src/radiant/performance/tests/test_noise_spec_converters.py:46-68` (impl `src/radiant/performance/nep_electrons.py:45-70`)
- Category: self-referential (round-trip only) — **Severity: Medium**
- Evidence: `TestNepElectrons` contains only a round-trip, a 2× scaling ratio, and a
  monotonicity check; the implementation converts `wavelength_um * 1e-6` — if that conversion
  were dropped (10⁶ error) or `hc` were wrong, every test in the class still passes because both
  directions share the error.
- Strengthen: one hand-computed anchor, e.g. σ=100 e⁻, η=0.7, λ=10 µm, t=0.01 s →
  NEP = 100·1.9864e-25/(0.7·10e-6·0.01) ≈ 2.84e-16 W, `rel=1e-6`.

### B1-3. `compute_ee_box` tested only qualitatively — a factor-2 box-size error passes
- File: `src/radiant/optics/tests/test_ee_box.py:48-80` (impl `src/radiant/optics/ee_box.py:44` → `psf.ensquared_energy_nxn`)
- Category: gut-proof — **Severity: Medium**
- Evidence: all assertions are `0 < ee < 1`, monotone-in-n, and →1 at n=50; an implementation
  that ensquared over half (or twice) the pixel pitch satisfies every one. The only quantitative
  cross-check elsewhere (`platform/tests/test_stage.py:566-572`) compares PlatformStage's EE_box
  to `epsf.ensquared_energy_nxn(1)` itself — circular. This is the number Rule 9 feeds into the
  point-source signal chain; a factor-2 box error directly scales predicted SNR.
- Strengthen: anchor EE(1×1) for a known configuration against an independently computed value
  (analytic Airy ensquared energy in a p×p box — see Track A2 anchor EE_□(Q=2) = 0.177327 — or a
  hand-integrated Gaussian PSF).

### B1-4. `temperature_retrieval` tests are a closed loop — scale/band-integration errors cancel
- File: `src/radiant/performance/tests/test_temperature_retrieval.py` (whole file; impl `performance/temperature_retrieval.py:48`)
- Category: self-referential — **Severity: Medium**
- Evidence: the round-trip inverts the same forward model it built the "measurement" with;
  the Jacobian test is the definition restated; the FD test differentiates the same function. No
  absolute radiance anchor for `band_planck_radiance`. Mitigation: it wraps
  `core.blackbody.planck_spectral_radiance` (anchored in core tests), so only the
  band-integration wrapper is unguarded.
- Strengthen: one absolute anchor — band radiance T=300 K, 8–12 µm ≈ 38.5 W/m²/sr (Track A1
  value 38.5004239), `rel=1e-3`.

### B1-5. Rule 9 positive path (EE_box applied in sub-pixel/point-source) untested at unit level
- File: `src/radiant/spectral_integration/tests/test_stage.py:83-91`
- Category: missing-edge — **Severity: Medium**
- Evidence: the stage suite tests only the extended-regime *guard* (EE_box≠1 raises); no unit
  test that a sub-pixel or point-source run multiplies the signal by EE_box exactly once, nor
  that the background term is exempt in sub-pixel regime (both documented Rule 9 behaviors).
  Chain-level coverage only (`tests/integration/test_regime_continuity.py`).
- Strengthen: stage test — point-source state with EE_box=0.5 → photoelectrons exactly 0.5× the
  EE_box=1.0 run; sub-pixel background term unchanged.

### B1-6. `pytest.approx` with no explicit tolerance (rule violation)
- Files: `src/radiant/optics/tests/test_stage_pupil_maps.py:110,121`;
  `src/radiant/performance/tests/test_minimum_resolvable.py:41`
- Category: tolerance — **Severity: Low**
- The only violations in the four directories (all other wrapped calls carry tolerances —
  verified).

### B1-7. Tautological cross-model test — identical call compared with itself
- File: `src/radiant/platform/tests/test_smear.py:159-170`
- Category: trivial — **Severity: Low**
- `test_along_vs_cross_track_same_formula` computes `smear_mtf_1d(freq, w)` twice with identical
  arguments and asserts equality; cannot fail under any implementation.

### B1-8. Folded-MTF DC test satisfied by a no-op implementation
- File: `src/radiant/performance/tests/test_folded_mtf.py:146-156`
- Category: trivial / gut-proof — **Severity: Low**
- Docstring says "folded(0) > optical(0)" but asserts `>=`, which a no-op also passes
  (quantitative anchors elsewhere in the file do catch a no-op — style-level).

### B1-9. NIIRS dispatcher tests assert only `niirs > 0`
- File: `src/radiant/performance/tests/test_niirs.py:22-35`
- Category: gut-proof — **Severity: Low**
- Mitigated: lines 38-60 assert exact equality against `compute_giqe5`/`compute_iirs`, and
  IIRS≡GIQE-5 in v1 makes band dispatch currently unobservable. Becomes load-bearing the day
  IIRS diverges from GIQE-5.

## B1 summary: gut-proof 3, tolerance 1 (3 sites), self-referential 3, missing-edge 1, trivial 1.

Explicitly verified as sound: jitter/smear/pixel-aperture analytic MTFs, Airy/Bessel PSF
anchors, pupil-autocorrelation vs FFT(PSF) dual-path tests (genuinely independent paths),
cavity-model hand calcs, GSD spherical-geometry hand values, GIQE sensitivity FD cross-check,
Zernike orthonormality integrals, CU-165 FFT equivalence tests, and the
SNR/NEDT/SCNR/Johnson/detectivity anchor suites.

---

# B2 — core / source / atmosphere / detector / readout / geometry (91 files, ~26k lines)

Overall verdict: unusually strong suite. Planck, viewing triangle, orbit, turbulence,
diffusion, IPC, TDI, ADC, coadd, and binning tests all use genuine independent anchors
(CODATA/NIST radiation constants, Stefan–Boltzmann, Wien, Koschmieder, real MODTRAN 6 band
means) with tight tolerances. Findings below are the exceptions.

## B2 Findings

### B2-1. `core/tests/test_responsivity.py:153-165` — gut-proof — **Severity: High**
`TestElectronsToRadiance.test_round_trip_consistency` docstring says "signal_e ÷ (R_band ×
t_int) should give back radiance," but the only assertions are `L is not None` and `L > 0.0`.
Verified against `core/responsivity.py:113-149`: dropping `t_int`, the QE factor, or the λ/hc
term entirely would still return a positive float and pass. The "round trip" is never actually
asserted.
Fix: flat τ/QE state, compute expected L analytically, assert `rel=1e-9`; or invert a known
input radiance end-to-end.

### B2-2. `core/tests/test_responsivity.py:130-144` — gut-proof — **Severity: High**
`TestBandIntegratedResponsivity` asserts only `r_band > 0` and `r_half < r_full`. A factor-of-2,
factor-of-π, or 1e6 unit slip in the band integral passes. (Spectral R(λ) point values are
anchored above; the integration step — the thing this class exists to test — has no value
check.)
Fix: for constant τ·QE the band integral is closed-form:
R_band = A·Ω·τ·QE·(λ_max²−λ_min²)/(2hc) (λ in m); assert `rel=1e-6`.

### B2-3. `source/tests/test_invert_band_radiance.py:34-62` — self-referential — **Severity: Medium**
The three "TestRoundTripAnchors" invert the module's own `integrate_planck_over_band` output —
any scale error in the forward band integral cancels exactly; anchors validate only the root
solver. Repo-wide grep: **no absolute anchor for `integrate_planck_over_band` exists anywhere**;
forward model tested only for monotonicity. `test_radiance_temperature_converter.py:64-92`
inherits the same cancellation.
Fix: one absolute anchor — ∫₈¹² B(λ, 300 K) dλ = 38.500 W/m²/sr (Track A1), `rel=1e-3`.

### B2-4. `source/tests/test_no_atmosphere_subcases.py:142-162` — tolerance — **Severity: Medium**
Test claims "exo reduces to ε·B(T_t)" (Cell 58) but asserts only `3 < L < 15` W/m²/sr/µm — a
factor-of-2-low result still passes.
Fix: `assert_allclose(L, 0.98·B(λ, 285 K), rtol=1e-9)` — the exo path makes this exact.

### B2-5. `core/tests/test_repeat_ground_track.py:71-85` — gut-proof — **Severity: Medium**
`TestRevisit` asserts only orderings. Unlike its siblings (ISS regression −5.0°/day, spacing
2626 km), `revisit_interval_days` has no value anchor — any constant-factor error passes.
Fix: hand anchor (600 km / 50 km swath at equator), `rel=2e-2`.

### B2-6. `source/tests/test_emissivity_path.py:56-66` — missing value check — **Severity: Medium**
CSV resample test asserts only "monotone ramp within [0,1]" — interpolated values never
checked; a wrong-column read that still yields an increasing ramp passes.
Fix: with table (7, 0.60), (10, 0.80), (13, 0.95): assert ε(8)≈0.6667, ε(10)≈0.80, ε(12)≈0.90
at `rel=1e-9`.

### B2-7. 26 `pytest.approx` calls with no explicit rel=/abs= — rule violation — **Severity: Low**
All are pass-through/exception-context checks, not physics values (default rel=1e-6 adequate),
but the project rule is explicit. Sites:
- source/tests/test_brightness_temperature_converter.py:504,521,540,541
- source/tests/test_inferrer_reflective.py:595,631,632
- atmosphere/tests/test_simple.py:349,350,351,740,742,744,746
- atmosphere/tests/test_interpolated.py:657
- detector/tests/test_ipc.py:205; detector/tests/test_qe.py:28,29
- geometry/tests/test_stage.py:83,124,139,148,216,226; geometry/tests/test_modes.py:124,225

### B2-8. `core/tests/test_solar_geometry.py:71-75` — anchor-comment mismatch — **Severity: Low**
Comment records the hand calc as "cos θ_z = 0.0768 → 85.6°" but the assertion is `83.4 ± 1.0`.
The correct hand calc is sin60·sin(−23.44) + cos60·cos(−23.44) = 0.1143 → 83.44° — the
*assertion* is right and the recorded anchor arithmetic is wrong. Fix the comment so anchor
provenance is trustworthy.

## B2 summary: gut-proof 3, tolerance 1, self-referential 2, missing value 1, approx-without-tolerance 26 sites, trivial 0.

Verified sound (not findings): test_blackbody.py (three genuinely independent anchors, full
edge coverage — model of the genre); CU-161 MODTRAN 6 band-mean anchors with exact
Beer–Lambert hand-calc at rel=1e-12; the layered stage-vs-primitive pattern (each referenced
primitive carries its own Level-0 anchor; atmosphere/tests/test_stage.py:165-185 re-derives
Planck from raw CODATA constants to avoid circularity); MODTRAN parser tests assert
hand-converted values; kernel-FFT-vs-analytic cross-model checks (diffusion, IPC, electronics
MTF).

---

# Combined ranked top findings (both scopes)

1. B1-1 GIQE-5 coefficients unpinned (High)
2. B2-1 responsivity "round trip" asserts only positivity (High)
3. B2-2 band-integrated responsivity has no value anchor (High)
4. B2-3 integrate_planck_over_band has no absolute anchor repo-wide (Medium)
5. B1-2 NEP↔electrons round-trip only (Medium)
6. B1-3 EE_box qualitative-only; the one cross-check is circular (Medium)
7. B1-5 Rule 9 positive path untested at unit level (Medium)

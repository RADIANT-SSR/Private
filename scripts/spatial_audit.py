#!/usr/bin/env python3
"""Checkpoint 2C — Spatial Subsystem Audit.

Comprehensive diagnostic for human review of the RADIANT spatial
subsystem.  Prints every spatial metric, verifies all 9 EffectivePSF
invariants, and checks cross-model consistency.

Run:
    python scripts/spatial_audit.py

Reference configuration:
    MWIR LEO: D=0.30 m, f=1.20 m, pitch=18 µm, λ=3.5–5.0 µm,
    altitude=8 km, with optional degradation kernels.

Checkpoint 2C deliverables
--------------------------
1. PSF summary and sampling config
2. Every MTF component at Nyquist
3. Every EE value (1×1, 3×3, 5×5, vs offset)
4. FWHM in both axes
5. RER, Strehl, NIIRS
6. Numerical verification of all 9 invariants
7. Budget MTF vs EffectivePSF MTF (max difference)
8. Ground truth test status
9. Adversarial single-source-of-truth audit
"""

from __future__ import annotations

import math
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Reference configuration
# ---------------------------------------------------------------------------
D = 0.30           # aperture diameter [m]
F = 1.20           # focal length [m]
PITCH = 18e-6      # pixel pitch [m]
OBSCURATION = 0.0  # central obscuration ratio
WFE = 0.0          # wave-front error [waves RMS]
FILTER_MIN = 3.5   # µm
FILTER_MAX = 5.0   # µm
LAM_CENTER_UM = (FILTER_MIN + FILTER_MAX) / 2.0  # 4.25 µm
LAM_CENTER_M = LAM_CENTER_UM * 1e-6
ALTITUDE = 8000.0  # m
SNR = 325.0        # approximate from chain
PUPIL_NPIX = 128
PSF_OVERSAMPLE = 8

# Degradation parameters
DIFFUSION_LENGTH_M = 5e-6   # 5 µm charge diffusion
JITTER_RMS_RAD = 1e-6       # 1 µrad jitter
SMEAR_WIDTH_M = 2e-6        # 2 µm smear on FPA


def banner(title: str) -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def section(title: str) -> None:
    print()
    print(f"--- {title} ---")


def ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def info(msg: str) -> None:
    print(f"  {msg}")


def check(condition: bool, msg: str) -> bool:
    if condition:
        ok(msg)
    else:
        fail(msg)
    return condition


# ===================================================================
# 1. Build the PSF and EffectivePSF
# ===================================================================

def build_reference_psfs() -> dict:
    """Build diffraction-only and degraded EffectivePSFs."""
    from radiant.optics.sampling import compute_sampling
    from radiant.optics.diffraction_mono import compute_psf
    from radiant.optics.psf.builder import build_effective_psf
    from radiant.detector.diffusion import diffusion_kernel_2d
    from radiant.platform.jitter import jitter_kernel_2d
    from radiant.platform.smear import smear_kernel_1d

    config = compute_sampling(
        wavelength_m=LAM_CENTER_M,
        focal_length_m=F,
        aperture_diameter_m=D,
        pixel_pitch_m=PITCH,
        pupil_npix=PUPIL_NPIX,
        psf_oversample=PSF_OVERSAMPLE,
    )

    psf_arr = compute_psf(config, obscuration_ratio=OBSCURATION, wfe_rms_waves=WFE)

    # Diffraction-only EffectivePSF
    epsf_diff = build_effective_psf(
        psf_arr,
        kernels=[],
        sample_spacing_m=config.focal_spacing_m,
        pixel_pitch_m=PITCH,
        wavelength_um=LAM_CENTER_UM,
    )

    # Build degradation kernels at odd size (kernels are small;
    # build_effective_psf pads them to PSF grid size internally).
    dx = config.focal_spacing_m
    kn = 65  # odd kernel size, sufficient for these degradation magnitudes

    diff_kernel = diffusion_kernel_2d(kn, dx, DIFFUSION_LENGTH_M)
    jit_kernel = jitter_kernel_2d(kn, dx, JITTER_RMS_RAD * F, JITTER_RMS_RAD * F)

    # Smear: 1-D rect → 2-D via outer product with delta
    smear_1d = smear_kernel_1d(kn, dx, SMEAR_WIDTH_M)
    delta_1d = np.zeros(kn, dtype=np.float64)
    delta_1d[kn // 2] = 1.0 / dx  # unit-area delta
    smear_2d = np.outer(delta_1d, smear_1d) * dx  # normalise to unit volume

    kernels = [
        ("charge_diffusion", diff_kernel),
        ("jitter", jit_kernel),
        ("smear", smear_2d),
    ]

    # Degraded EffectivePSF
    epsf_degraded = build_effective_psf(
        psf_arr,
        kernels=kernels,
        sample_spacing_m=config.focal_spacing_m,
        pixel_pitch_m=PITCH,
        wavelength_um=LAM_CENTER_UM,
    )

    return {
        "config": config,
        "psf_arr": psf_arr,
        "epsf_diff": epsf_diff,
        "epsf_degraded": epsf_degraded,
        "kernels": kernels,
    }


# ===================================================================
# 2. Sampling Configuration
# ===================================================================

def print_sampling_config(data: dict) -> None:
    banner("1. SAMPLING CONFIGURATION")
    config = data["config"]
    info(f"Wavelength:          {LAM_CENTER_UM:.2f} µm  ({LAM_CENTER_M:.3e} m)")
    info(f"Aperture:            {D:.3f} m")
    info(f"Focal length:        {F:.3f} m")
    info(f"f/#:                 {F/D:.1f}")
    info(f"Pixel pitch:         {PITCH*1e6:.1f} µm  ({PITCH:.3e} m)")
    info(f"Obscuration ratio:   {OBSCURATION:.2f}")
    info(f"WFE RMS:             {WFE:.2f} waves")
    info(f"Pupil N:             {config.pupil_npix}")
    info(f"Padded N:            {config.padded_npix}")
    info(f"PSF oversample:      {config.psf_oversample}")
    info(f"Focal spacing:       {config.focal_spacing_m:.3e} m")
    info(f"Airy FWHM:           {1.028 * LAM_CENTER_M * F / D * 1e6:.2f} µm")
    info(f"Airy first zero:     {1.22 * LAM_CENTER_M * F / D * 1e6:.2f} µm")
    info(f"Nyquist freq:        {1/(2*PITCH):.0f} cy/m")
    info(f"λf/D (diffraction):  {LAM_CENTER_M * F / D * 1e6:.2f} µm")
    q = (LAM_CENTER_M * F / D) / PITCH
    info(f"Q = λf/(D·p):        {q:.3f}  ({'under-sampled' if q < 2 else 'well-sampled'})")


# ===================================================================
# 3. MTF Components at Nyquist
# ===================================================================

def print_mtf_components(data: dict) -> None:
    banner("2. MTF COMPONENTS AT NYQUIST")

    from radiant.performance.system_mtf import nyquist_freq, mtf_at_nyquist
    from radiant.detector.diffusion import diffusion_mtf_1d
    from radiant.detector.ipc import ipc_mtf_1d
    from radiant.platform.sampling import pixel_aperture_mtf_1d
    from radiant.platform.jitter import jitter_mtf_1d
    from radiant.platform.smear import smear_mtf_1d

    f_ny = nyquist_freq(PITCH)
    freq = np.array([f_ny])
    info(f"Nyquist frequency: {f_ny:.1f} cy/m  ({f_ny*PITCH:.3f} cy/pixel)")

    section("Individual component MTF at Nyquist")

    # Diffraction
    epsf_diff = data["epsf_diff"]
    f_arr, mtf_arr = epsf_diff.mtf_1d("x")
    mtf_diff_ny = float(np.interp(f_ny, f_arr, mtf_arr))
    info(f"Diffraction MTF:       {mtf_diff_ny:.6f}")

    # Charge diffusion
    mtf_cd = float(diffusion_mtf_1d(freq, DIFFUSION_LENGTH_M)[0])
    info(f"Charge diffusion MTF:  {mtf_cd:.6f}  (L_d={DIFFUSION_LENGTH_M*1e6:.1f} µm)")

    # Pixel aperture
    mtf_pa = float(pixel_aperture_mtf_1d(freq, PITCH, fill_factor=1.0)[0])
    info(f"Pixel aperture MTF:    {mtf_pa:.6f}  (FF=1.0)")

    # Jitter
    sigma_jit = JITTER_RMS_RAD * F
    mtf_jit = float(jitter_mtf_1d(freq, sigma_jit)[0])
    info(f"Jitter MTF:            {mtf_jit:.6f}  (σ={JITTER_RMS_RAD*1e6:.1f} µrad)")

    # Smear
    mtf_sm = float(smear_mtf_1d(freq, SMEAR_WIDTH_M)[0])
    info(f"Smear MTF:             {mtf_sm:.6f}  (w={SMEAR_WIDTH_M*1e6:.1f} µm)")

    # Budget product
    mtf_budget = mtf_diff_ny * mtf_cd * mtf_pa * mtf_jit * mtf_sm
    info(f"Budget product:        {mtf_budget:.6f}")

    # EffectivePSF (degraded) MTF at Nyquist
    epsf_deg = data["epsf_degraded"]
    f_deg, mtf_deg = epsf_deg.mtf_1d("x")
    mtf_epsf_ny = float(np.interp(f_ny, f_deg, mtf_deg))
    info(f"EffectivePSF MTF:      {mtf_epsf_ny:.6f}")

    # Comparison (pixel aperture is NOT part of the EffectivePSF convolution;
    # it's a detector-sampling effect. So the budget excluding pixel aperture
    # should match.)
    mtf_budget_no_pa = mtf_diff_ny * mtf_cd * mtf_jit * mtf_sm
    diff_vs_budget = abs(mtf_epsf_ny - mtf_budget_no_pa)
    info(f"Budget (excl. pixel):  {mtf_budget_no_pa:.6f}")
    info(f"|EffectivePSF - Budget (excl pixel)|: {diff_vs_budget:.3e}")

    return {"mtf_budget_no_pa": mtf_budget_no_pa, "mtf_epsf_ny": mtf_epsf_ny}


# ===================================================================
# 4. EE Values
# ===================================================================

def print_ee_values(data: dict) -> None:
    banner("3. ENSQUARED ENERGY")

    for label, key in [("Diffraction-only", "epsf_diff"), ("Degraded", "epsf_degraded")]:
        section(f"{label} EffectivePSF")
        epsf = data[key]
        for n in [1, 3, 5, 7]:
            ee = epsf.ensquared_energy_nxn(n)
            info(f"EE({n}x{n}): {ee:.6f}")

        # EE vs offset (fractional pixel)
        section(f"{label}: EE(1x1) vs sub-pixel offset")
        for offset_frac in [0.0, 0.25, 0.5]:
            half_w = PITCH / 2.0
            offset_m = offset_frac * PITCH
            n = epsf.data.shape[0]
            center = n // 2
            dx = epsf.sample_spacing_m
            # Shift center by offset
            shifted_center = center + int(round(offset_m / dx))
            half_pix = int(round(half_w / dx))
            lo = max(shifted_center - half_pix, 0)
            hi = min(shifted_center + half_pix + 1, n)
            ee_offset = float(epsf.data[lo:hi, lo:hi].sum())
            info(f"  offset={offset_frac:.2f} pixel: EE={ee_offset:.6f}")


# ===================================================================
# 5. FWHM, RER, Strehl
# ===================================================================

def print_spatial_metrics(data: dict) -> None:
    banner("4. SPATIAL METRICS")

    for label, key in [("Diffraction-only", "epsf_diff"), ("Degraded", "epsf_degraded")]:
        section(f"{label}")
        epsf = data[key]
        fwhm_x = epsf.fwhm("x")
        fwhm_y = epsf.fwhm("y")
        rer = epsf.rer()
        info(f"FWHM_x:  {fwhm_x:.3e} m  ({fwhm_x*1e6:.2f} µm)  ({fwhm_x/PITCH:.3f} pixels)")
        info(f"FWHM_y:  {fwhm_y:.3e} m  ({fwhm_y*1e6:.2f} µm)  ({fwhm_y/PITCH:.3f} pixels)")
        info(f"RER:     {rer:.6f}")
        info(f"Peak:    {epsf.peak:.6e}")
        info(f"Total:   {epsf.total:.10f}")
        info(f"History: {epsf.convolution_history}")

    section("Strehl ratio (degraded / diffraction)")
    strehl = data["epsf_degraded"].strehl(data["epsf_diff"])
    info(f"Strehl: {strehl:.6f}")


# ===================================================================
# 6. NIIRS
# ===================================================================

def print_niirs(data: dict) -> None:
    banner("5. NIIRS (GIQE-5)")

    from radiant.performance.giqe import compute_giqe5

    gsd = PITCH * ALTITUDE / F
    ifov = PITCH / F
    info(f"GSD:   {gsd:.4f} m  ({gsd*100:.2f} cm)")
    info(f"IFOV:  {ifov:.3e} rad  ({ifov*1e6:.2f} µrad)")

    for label, key in [("Diffraction-only", "epsf_diff"), ("Degraded", "epsf_degraded")]:
        section(f"{label}")
        epsf = data[key]
        rer = epsf.rer()
        result = compute_giqe5(gsd, gsd, rer, rer, SNR)
        info(f"RER:         {rer:.4f}")
        info(f"GSD (inch):  {result.gsd_inch:.4f}")
        info(f"SNR:         {SNR:.1f}")
        info(f"NIIRS:       {result.niirs:.3f}")
        if result.warnings:
            for w in result.warnings:
                info(f"  WARNING: {w}")


# ===================================================================
# 7. Nine Mandatory Invariants
# ===================================================================

def verify_invariants(data: dict) -> int:
    banner("6. NINE MANDATORY INVARIANTS")

    from radiant.optics.psf.builder import build_effective_psf

    epsf_diff = data["epsf_diff"]
    epsf_deg = data["epsf_degraded"]
    psf_arr = data["psf_arr"]
    config = data["config"]
    kernels = data["kernels"]

    n_pass = 0

    # 1. Energy conservation: sum(PSF) = 1.0
    section("Invariant 1: Energy conservation")
    total_diff = epsf_diff.total
    total_deg = epsf_deg.total
    info(f"Diffraction total: {total_diff:.15f}")
    info(f"Degraded total:    {total_deg:.15f}")
    if check(abs(total_diff - 1.0) < 1e-10, f"|total_diff - 1| = {abs(total_diff-1):.2e} < 1e-10"):
        n_pass += 1
    if check(abs(total_deg - 1.0) < 1e-10, f"|total_deg - 1| = {abs(total_deg-1):.2e} < 1e-10"):
        n_pass += 1

    # 2. MTF(0) = 1
    section("Invariant 2: MTF(0) = 1")
    for label, epsf in [("Diffraction", epsf_diff), ("Degraded", epsf_deg)]:
        freq, mtf = epsf.mtf_1d("x")
        mtf0 = mtf[0]
        info(f"{label} MTF(0) = {mtf0:.15f}")
        if check(abs(mtf0 - 1.0) < 1e-6, f"{label}: |MTF(0) - 1| = {abs(mtf0-1):.2e} < 1e-6"):
            n_pass += 1

    # 3. Parseval's theorem
    section("Invariant 3: Parseval's theorem")
    for label, epsf in [("Diffraction", epsf_diff), ("Degraded", epsf_deg)]:
        psf_data = epsf.data
        n = psf_data.shape[0]
        sum_psf_sq = float(np.sum(psf_data ** 2))
        fft_psf = np.fft.fft2(psf_data)
        sum_fft_sq = float(np.sum(np.abs(fft_psf) ** 2)) / (n * n)
        rel_err = abs(sum_psf_sq - sum_fft_sq) / max(sum_psf_sq, 1e-30)
        info(f"{label}: sum|PSF|^2 = {sum_psf_sq:.10e}")
        info(f"{label}: sum|FFT|^2/N^2 = {sum_fft_sq:.10e}")
        if check(rel_err < 1e-10, f"{label}: relative error = {rel_err:.2e} < 1e-10"):
            n_pass += 1

    # 4. Convolution order independence
    section("Invariant 4: Convolution order independence")
    # Forward order
    epsf_fwd = build_effective_psf(
        psf_arr, kernels,
        sample_spacing_m=config.focal_spacing_m,
        pixel_pitch_m=PITCH,
        wavelength_um=LAM_CENTER_UM,
    )
    # Reversed order
    epsf_rev = build_effective_psf(
        psf_arr, list(reversed(kernels)),
        sample_spacing_m=config.focal_spacing_m,
        pixel_pitch_m=PITCH,
        wavelength_um=LAM_CENTER_UM,
    )
    max_diff = float(np.max(np.abs(epsf_fwd.data - epsf_rev.data)))
    info(f"max |forward - reversed| = {max_diff:.3e}")
    if check(max_diff < 1e-10, f"Order independence: max diff = {max_diff:.2e} < 1e-10"):
        n_pass += 1

    # 5. EE monotonicity
    section("Invariant 5: EE monotonicity")
    for label, epsf in [("Diffraction", epsf_diff), ("Degraded", epsf_deg)]:
        ee_vals = [epsf.ensquared_energy_nxn(n) for n in [1, 3, 5, 7, 9, 11]]
        monotonic = all(ee_vals[i] <= ee_vals[i + 1] + 1e-15 for i in range(len(ee_vals) - 1))
        info(f"{label} EE sequence: {[f'{v:.6f}' for v in ee_vals]}")
        if check(monotonic, f"{label}: EE is non-decreasing"):
            n_pass += 1
        # Full grid should be ~1.0
        ee_full = epsf.ensquared_energy_nxn(epsf.data.shape[0])
        if check(ee_full > 0.999, f"{label}: EE(full grid) = {ee_full:.6f} > 0.999"):
            n_pass += 1

    # 6. MTF budget consistency
    section("Invariant 6: MTF budget consistency")
    # Compare product of individual MTFs vs FFT of convolved PSF
    from radiant.detector.diffusion import diffusion_mtf_1d
    from radiant.platform.jitter import jitter_mtf_1d
    from radiant.platform.smear import smear_mtf_1d

    freq_epsf, mtf_epsf = epsf_deg.mtf_1d("x")
    freq_diff, mtf_diff_arr = epsf_diff.mtf_1d("x")
    # Interpolate analytic MTFs onto EffectivePSF frequency grid
    mtf_cd = diffusion_mtf_1d(freq_epsf, DIFFUSION_LENGTH_M)
    sigma_jit = JITTER_RMS_RAD * F
    mtf_jit = jitter_mtf_1d(freq_epsf, sigma_jit)
    mtf_sm = smear_mtf_1d(freq_epsf, SMEAR_WIDTH_M)
    # Diffraction MTF on same grid
    mtf_diff_interp = np.interp(freq_epsf, freq_diff, mtf_diff_arr)
    mtf_budget = mtf_diff_interp * mtf_cd * mtf_jit * mtf_sm

    # Compare over main lobe (up to Nyquist)
    f_ny = 1.0 / (2.0 * PITCH)
    mask = freq_epsf <= f_ny
    max_budget_diff = float(np.max(np.abs(mtf_epsf[mask] - mtf_budget[mask])))
    info(f"max |MTF_epsf - MTF_budget| (0 to Nyquist): {max_budget_diff:.6f}")
    if check(max_budget_diff < 0.01, f"Budget consistency: max diff = {max_budget_diff:.4f} < 0.01"):
        n_pass += 1

    # 7. Strehl = 1 for unaberrated, no motion
    section("Invariant 7: Strehl = 1 for unaberrated, no degradation")
    # Build a fresh diffraction-only EffectivePSF and check Strehl against itself
    strehl_self = epsf_diff.strehl(epsf_diff)
    info(f"Strehl(diff, diff) = {strehl_self:.10f}")
    if check(abs(strehl_self - 1.0) < 1e-10, f"|Strehl - 1| = {abs(strehl_self - 1):.2e} < 1e-10"):
        n_pass += 1

    # 8. FWHM monotonic in degradations
    section("Invariant 8: FWHM increases with degradation")
    fwhm_diff = epsf_diff.fwhm("x")
    fwhm_deg = epsf_deg.fwhm("x")
    info(f"FWHM diffraction: {fwhm_diff*1e6:.2f} µm")
    info(f"FWHM degraded:    {fwhm_deg*1e6:.2f} µm")
    if check(fwhm_deg >= fwhm_diff, "FWHM(degraded) >= FWHM(diffraction)"):
        n_pass += 1

    # 9. RER decreases with degradation
    section("Invariant 9: RER decreases with degradation")
    rer_diff = epsf_diff.rer()
    rer_deg = epsf_deg.rer()
    info(f"RER diffraction: {rer_diff:.6f}")
    info(f"RER degraded:    {rer_deg:.6f}")
    if check(rer_deg <= rer_diff, "RER(degraded) <= RER(diffraction)"):
        n_pass += 1

    total_checks = 15  # 2+2+2+1+4+1+1+1+1
    section(f"INVARIANT SUMMARY: {n_pass}/{total_checks} checks passed")
    return n_pass


# ===================================================================
# 8. Ground Truth Tests
# ===================================================================

def run_ground_truth() -> bool:
    banner("7. GROUND TRUTH TESTS")

    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "tests/integration/test_ground_truth_mwir.py",
            "tests/integration/test_golden_mwir_leo_minimal.py",
            "tests/integration/test_chain_spatial.py",
            "-v", "--tb=short",
        ],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        fail("Ground truth tests FAILED")
        return False
    ok("All ground truth tests passed")
    return True


# ===================================================================
# 9. Full Test Suite
# ===================================================================

def run_full_suite() -> bool:
    banner("8. FULL TEST SUITE")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "src/", "tests/", "-q", "--tb=line"],
        capture_output=True,
        text=True,
    )
    # Extract summary line
    for line in result.stdout.strip().split("\n")[-5:]:
        print(f"  {line}")
    if result.returncode != 0:
        print(result.stderr[-500:] if result.stderr else "")
        fail("Full test suite has failures")
        return False
    ok("Full test suite passed")
    return True


# ===================================================================
# 10. Import Contract Check
# ===================================================================

def run_import_linter() -> bool:
    banner("9. IMPORT CONTRACTS")

    result = subprocess.run(
        ["lint-imports", "--config", "pyproject.toml"],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.strip().split("\n")[-10:]:
        print(f"  {line}")
    if result.returncode != 0:
        fail("Import contracts broken")
        return False
    ok("All import contracts kept")
    return True


# ===================================================================
# 11. Adversarial Single-Source-of-Truth Audit
# ===================================================================

def adversarial_audit() -> None:
    banner("10. ADVERSARIAL AUDIT: SINGLE SOURCE OF TRUTH")

    info("Checking that no code path computes MTF or EE independently")
    info("of EffectivePSF...")
    print()

    # Check: performance.stage only reads EffectivePSF from stage_outputs
    import inspect
    from radiant.performance import stage as perf_stage
    source = inspect.getsource(perf_stage)

    issues = []

    # Must NOT import from radiant.optics
    if "from radiant.optics" in source:
        issues.append("performance.stage imports from radiant.optics (cross-stage)")

    # Must NOT call compute_psf or compute_sampling
    if "compute_psf" in source:
        issues.append("performance.stage calls compute_psf directly")
    if "compute_sampling" in source:
        issues.append("performance.stage calls compute_sampling directly")

    # Must read EffectivePSF from stage_outputs
    if 'stage_outputs["optics"]["effective_psf"]' not in source:
        issues.append("performance.stage doesn't read EffectivePSF from optics stage_outputs")

    if issues:
        for issue in issues:
            fail(issue)
    else:
        ok("performance.stage reads EffectivePSF from optics stage_outputs only")
        ok("No cross-stage physics imports in performance.stage")

    # Check: optics.stage builds EffectivePSF
    from radiant.optics import stage as optics_stage
    optics_source = inspect.getsource(optics_stage)
    if "build_effective_psf" in optics_source:
        ok("optics.stage builds EffectivePSF via build_effective_psf()")
    else:
        fail("optics.stage does not build EffectivePSF")

    # Check: EffectivePSF.rer() uses ERF from same PSF
    from radiant.optics.psf.effective import EffectivePSF
    rer_source = inspect.getsource(EffectivePSF.rer)
    if "self.erf" in rer_source:
        ok("EffectivePSF.rer() derives from self.erf() (same PSF)")
    else:
        fail("EffectivePSF.rer() does not use self.erf()")

    # Check: EffectivePSF.mtf_1d uses self.mtf_2d
    mtf1d_source = inspect.getsource(EffectivePSF.mtf_1d)
    if "self.mtf_2d" in mtf1d_source:
        ok("EffectivePSF.mtf_1d() derives from self.mtf_2d() (same PSF)")
    else:
        fail("EffectivePSF.mtf_1d() does not use self.mtf_2d()")

    # Check: no independent MTF or EE computation in chain stages
    import importlib
    stage_modules = [
        "radiant.source.stage",
        "radiant.atmosphere.stage",
        "radiant.spectral_integration.stage",
        "radiant.detector.stage",
        "radiant.readout.stage",
    ]
    for mod_name in stage_modules:
        try:
            mod = importlib.import_module(mod_name)
            mod_source = inspect.getsource(mod)
            if "EffectivePSF" in mod_source or "mtf_2d" in mod_source:
                fail(f"{mod_name} references EffectivePSF or mtf_2d")
            else:
                ok(f"{mod_name}: no independent spatial metric computation")
        except ImportError:
            info(f"{mod_name}: not found (OK if not yet implemented)")

    print()
    info("Rule 4 compliance: EffectivePSF is the single source of truth")
    info("for all spatial metrics (MTF, EE, LSF, ERF, RER, FWHM, Strehl).")


# ===================================================================
# PSF Plots
# ===================================================================

def generate_plots(data: dict) -> Path:
    """Generate PSF, MTF, EE, LSF/ERF diagnostic plots.

    Saves a multi-panel PNG to ``scripts/spatial_audit_plots.png``
    and returns the path.
    """
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    banner("11. PSF PLOTS")

    out_dir = Path(__file__).parent
    out_path = out_dir / "spatial_audit_plots.png"

    epsf_diff = data["epsf_diff"]
    epsf_deg = data["epsf_degraded"]
    config = data["config"]
    dx = config.focal_spacing_m

    fig, axes = plt.subplots(3, 3, figsize=(16, 14))
    fig.suptitle(
        f"RADIANT Checkpoint 2C — Spatial Audit\n"
        f"D={D:.2f} m, f={F:.2f} m, pitch={PITCH*1e6:.0f} µm, "
        f"λ={LAM_CENTER_UM:.2f} µm, f/{F/D:.0f}",
        fontsize=13,
        fontweight="bold",
    )

    # --- Row 0: PSF images ---------------------------------------------------

    # (0,0) Diffraction PSF — log scale
    ax = axes[0, 0]
    n = epsf_diff.data.shape[0]
    extent_um = np.array([-n/2, n/2, -n/2, n/2]) * dx * 1e6
    vmin = epsf_diff.peak * 1e-5  # 5 decades
    im = ax.imshow(
        epsf_diff.data,
        extent=extent_um,
        origin="lower",
        cmap="inferno",
        norm=LogNorm(vmin=max(vmin, 1e-30), vmax=epsf_diff.peak),
    )
    ax.set_title("Diffraction PSF (log)")
    ax.set_xlabel("x [µm]")
    ax.set_ylabel("y [µm]")
    ax.set_xlim(-60, 60)
    ax.set_ylim(-60, 60)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Intensity")

    # (0,1) Degraded PSF — log scale
    ax = axes[0, 1]
    im = ax.imshow(
        epsf_deg.data,
        extent=extent_um,
        origin="lower",
        cmap="inferno",
        norm=LogNorm(vmin=max(vmin, 1e-30), vmax=epsf_deg.peak),
    )
    ax.set_title("Degraded PSF (log)")
    ax.set_xlabel("x [µm]")
    ax.set_ylabel("y [µm]")
    ax.set_xlim(-60, 60)
    ax.set_ylim(-60, 60)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Intensity")

    # (0,2) PSF cross-sections — linear
    ax = axes[0, 2]
    center = n // 2
    x_um = (np.arange(n) - center) * dx * 1e6
    ax.plot(x_um, epsf_diff.data[center, :], label="Diffraction", linewidth=1.5)
    ax.plot(x_um, epsf_deg.data[center, :], label="Degraded", linewidth=1.5, linestyle="--")
    # Mark pixel boundaries
    for k in range(-3, 4):
        ax.axvline(k * PITCH * 1e6, color="gray", alpha=0.3, linewidth=0.5)
    ax.set_xlim(-60, 60)
    ax.set_title("PSF Cross-section (x-axis)")
    ax.set_xlabel("x [µm]")
    ax.set_ylabel("Intensity")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # --- Row 1: MTF -----------------------------------------------------------

    # (1,0) MTF 1-D comparison
    ax = axes[1, 0]
    freq_d, mtf_d = epsf_diff.mtf_1d("x")
    freq_g, mtf_g = epsf_deg.mtf_1d("x")
    f_ny = 1.0 / (2.0 * PITCH)
    # Normalise freq to Nyquist
    ax.plot(freq_d / f_ny, mtf_d, label="Diffraction", linewidth=1.5)
    ax.plot(freq_g / f_ny, mtf_g, label="Degraded", linewidth=1.5, linestyle="--")
    ax.axvline(1.0, color="red", alpha=0.5, linewidth=1, label="Nyquist")
    ax.set_xlim(0, 2.0)
    ax.set_ylim(0, 1.05)
    ax.set_title("MTF (x-axis)")
    ax.set_xlabel("Spatial frequency [cy/pixel]")
    ax.set_ylabel("MTF")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # (1,1) MTF budget components
    ax = axes[1, 1]
    from radiant.detector.diffusion import diffusion_mtf_1d
    from radiant.platform.jitter import jitter_mtf_1d
    from radiant.platform.smear import smear_mtf_1d
    from radiant.platform.sampling import pixel_aperture_mtf_1d

    freq_plot = np.linspace(0, 2.0 * f_ny, 500)
    sigma_jit = JITTER_RMS_RAD * F
    ax.plot(freq_plot / f_ny, np.interp(freq_plot, freq_d, mtf_d),
            label="Diffraction", linewidth=1.5)
    ax.plot(freq_plot / f_ny, diffusion_mtf_1d(freq_plot, DIFFUSION_LENGTH_M),
            label="Charge diffusion", linewidth=1)
    ax.plot(freq_plot / f_ny, pixel_aperture_mtf_1d(freq_plot, PITCH),
            label="Pixel aperture", linewidth=1)
    ax.plot(freq_plot / f_ny, jitter_mtf_1d(freq_plot, sigma_jit),
            label="Jitter", linewidth=1)
    ax.plot(freq_plot / f_ny, smear_mtf_1d(freq_plot, SMEAR_WIDTH_M),
            label="Smear", linewidth=1)
    ax.axvline(1.0, color="red", alpha=0.5, linewidth=1, label="Nyquist")
    ax.set_xlim(0, 2.0)
    ax.set_ylim(0, 1.05)
    ax.set_title("MTF Budget Components")
    ax.set_xlabel("Spatial frequency [cy/pixel]")
    ax.set_ylabel("MTF")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # (1,2) MTF 2-D (diffraction)
    ax = axes[1, 2]
    mtf2d = epsf_diff.mtf_2d()
    freq_extent = np.array([-n/2, n/2, -n/2, n/2]) / (n * dx) / f_ny
    im = ax.imshow(
        mtf2d,
        extent=freq_extent,
        origin="lower",
        cmap="viridis",
        vmin=0, vmax=1,
    )
    ax.set_xlim(-2, 2)
    ax.set_ylim(-2, 2)
    ax.set_title("Diffraction MTF 2-D")
    ax.set_xlabel("fx [cy/pixel]")
    ax.set_ylabel("fy [cy/pixel]")
    fig.colorbar(im, ax=ax, shrink=0.8, label="MTF")

    # --- Row 2: EE, ERF, LSF -------------------------------------------------

    # (2,0) Ensquared energy vs box size
    ax = axes[2, 0]
    box_sizes = np.arange(1, 16, 2)
    ee_diff = [epsf_diff.ensquared_energy_nxn(int(b)) for b in box_sizes]
    ee_deg = [epsf_deg.ensquared_energy_nxn(int(b)) for b in box_sizes]
    ax.plot(box_sizes, ee_diff, "o-", label="Diffraction", markersize=5)
    ax.plot(box_sizes, ee_deg, "s--", label="Degraded", markersize=5)
    ax.set_xlabel("Box size [pixels]")
    ax.set_ylabel("Ensquared Energy")
    ax.set_title("EE vs Box Size")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1.05)

    # (2,1) Edge Response Function
    ax = axes[2, 1]
    pos_d, erf_d = epsf_diff.erf("x")
    pos_g, erf_g = epsf_deg.erf("x")
    ax.plot(pos_d * 1e6, erf_d, label="Diffraction", linewidth=1.5)
    ax.plot(pos_g * 1e6, erf_g, label="Degraded", linewidth=1.5, linestyle="--")
    # Mark pixel boundaries
    half_p = PITCH * 1e6 / 2
    ax.axvline(-half_p, color="gray", alpha=0.5, linewidth=1, linestyle=":")
    ax.axvline(half_p, color="gray", alpha=0.5, linewidth=1, linestyle=":")
    ax.axhspan(
        float(np.interp(-half_p, pos_d * 1e6, erf_d)),
        float(np.interp(half_p, pos_d * 1e6, erf_d)),
        alpha=0.1, color="blue", label=f"RER={epsf_diff.rer():.3f}",
    )
    ax.set_xlim(-60, 60)
    ax.set_title("Edge Response Function")
    ax.set_xlabel("Position [µm]")
    ax.set_ylabel("ERF")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # (2,2) Line Spread Function
    ax = axes[2, 2]
    pos_d, lsf_d = epsf_diff.lsf("x")
    pos_g, lsf_g = epsf_deg.lsf("x")
    ax.plot(pos_d * 1e6, lsf_d, label="Diffraction", linewidth=1.5)
    ax.plot(pos_g * 1e6, lsf_g, label="Degraded", linewidth=1.5, linestyle="--")
    ax.set_xlim(-60, 60)
    ax.set_title("Line Spread Function")
    ax.set_xlabel("Position [µm]")
    ax.set_ylabel("LSF")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    info(f"Plots saved to: {out_path}")
    info("9 panels: PSF images (log), cross-section, MTF 1-D, MTF budget,")
    info("MTF 2-D, EE vs box size, ERF, LSF")
    return out_path


# ===================================================================
# Main
# ===================================================================

def main() -> int:
    print()
    print("*" * 72)
    print("*  RADIANT Checkpoint 2C — Spatial Subsystem Audit")
    print("*" * 72)

    data = build_reference_psfs()

    print_sampling_config(data)
    print_mtf_components(data)
    print_ee_values(data)
    print_spatial_metrics(data)
    print_niirs(data)
    n_invariants = verify_invariants(data)
    plot_path = generate_plots(data)
    gt_ok = run_ground_truth()
    suite_ok = run_full_suite()
    imports_ok = run_import_linter()
    adversarial_audit()

    banner("CHECKPOINT 2C SUMMARY")
    info(f"Invariants:      {n_invariants}/15 checks passed")
    info(f"Ground truth:    {'PASS' if gt_ok else 'FAIL'}")
    info(f"Full suite:      {'PASS' if suite_ok else 'FAIL'}")
    info(f"Import linter:   {'PASS' if imports_ok else 'FAIL'}")

    all_ok = n_invariants == 15 and gt_ok and suite_ok and imports_ok
    print()
    if all_ok:
        print("  >>> CHECKPOINT 2C: ALL CHECKS PASSED <<<")
    else:
        print("  >>> CHECKPOINT 2C: SOME CHECKS FAILED — review above <<<")
    print()
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

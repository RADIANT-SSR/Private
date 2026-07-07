# CU-003 — Pixel-aperture rect kernel: anti-aliased construction

**Category:** C (physics implementation — touches the dual-path consistency invariant from CLAUDE.md Rule 4).
**Triggered from:** [docs/Cleanup_Backlog.md](Cleanup_Backlog.md) CU-003, escalated 2026-04-24 by Phase 2 Track A investigation (commit `cfc94c0`).
**Scope:** ~30–80 lines of production code in [src/radiant/optics/pixel_kernel.py](../src/radiant/optics/pixel_kernel.py), plus new tests and one possible golden-snapshot refresh on `swir_aerial_gas`.

---

## Problem statement

[scripts/capture_option_c_baseline.py](../scripts/capture_option_c_baseline.py) emits a Rule-4 consistency-check warning on `examples/templates/swir_aerial_gas.yaml`:

> `max_err_x = max_err_y = 0.05196` against tolerance `0.0500` — the only failing scenario in the 14-cell baseline.

Phase 2 Track A investigation (see CU-003 entry) localized the residual: it is *entirely* the pixel-aperture term's discretization mismatch between paths. Substituting the discrete rect kernel's actual FFT into the MTF-product path (in place of the analytic `sinc(π·pitch·f)`) drops `max_err` from `0.05196` to `0.00000` — proving there is no missing degradation, no aberration-path drift, no jitter/smear inconsistency. It is one term, one root cause.

### Root cause

[src/radiant/optics/pixel_kernel.py:57](../src/radiant/optics/pixel_kernel.py#L57) `_rect_1d` builds a binary mask:

```python
def _rect_1d(npix, sample_spacing_m, width_m):
    c = npix // 2
    x = (np.arange(npix) - c) * sample_spacing_m
    half = width_m / 2.0
    kernel = np.where(np.abs(x) <= half, 1.0, 0.0)  # <-- binary edge
    total = kernel.sum()
    if total > 0.0:
        kernel /= total
    return kernel
```

When `pixel_pitch / sample_spacing` is **non-integer** (the common case), the rect's edges fall between samples. The binary mask either includes or excludes the edge sample wholesale — there is no fractional-area weighting — so the discrete kernel's FFT differs from the analytic `sinc` (which assumes a continuous rect of exactly `width_m`). The deviation is largest near Nyquist and grows worst at low Q.

For `swir_aerial_gas`: `Q = 0.338` (suite minimum), `sample_spacing = 1.6875 µm`, `pitch = 20 µm` → `11.852 samples/pixel` (non-integer). The next-lowest-Q scenario, `vnir_leo_highres`, has `Q ≈ 1.0` and lands well inside tolerance — confirming this is a low-Q numerical edge, not a routine-condition bug.

### Why a fix is needed

CLAUDE.md Rule 4 requires PSF-path ↔ MTF-product-path agreement to ~1e-6. The current scenario is **5×10⁴** looser than that. As the baseline-snapshot suite grows (Stage 5/6/7 add scenarios), additional low-Q cases will drift the same way and risk being mis-attributed to a stage's physics changes. Fixing this term puts the consistency check back on a physics signal instead of a discretization signal.

---

## Required reading (do not skip)

1. [CLAUDE.md](../CLAUDE.md) — Rule 4 in full (dual-path spatial architecture). The whole task lives inside this rule's invariant.
2. [docs/architecture/RADIANT_Optics.md](RADIANT_Optics.md) — pupil → PSF → optical MTF derivation; pixel-aperture kernel description.
3. [docs/architecture/RADIANT_Spatial_Complete.md](RADIANT_Spatial_Complete.md) §6 step 1 — pixel-aperture kernel as PSF convolution.
4. [src/radiant/optics/pixel_kernel.py](../src/radiant/optics/pixel_kernel.py) — the file you will edit.
5. [src/radiant/optics/stage.py](../src/radiant/optics/stage.py) — `_compute_optical_mtf_terms` (the analytic `sinc` consumer side; **do not change** unless approach 2 is chosen).
6. [src/radiant/performance/consistency_check.py](../src/radiant/performance/consistency_check.py) — the check that fires; tolerance `5e-2` lives here. Tolerance is **not** the lever to pull; the kernel is.
7. [docs/Cleanup_Backlog.md](Cleanup_Backlog.md) CU-003 — the full investigation record (numbers, per-term sensitivity table, decisive verification).

---

## Approach decision (raise to user before coding)

Two physically equivalent paths. **Recommended: Approach 1.**

### Approach 1 — Anti-aliased rect kernel (recommended)

Rebuild `_rect_1d` so each sample's value equals the **fractional area** of the analytic rect that falls inside that sample's bin (cell) of width `sample_spacing_m`:

```python
def _rect_1d(npix, sample_spacing_m, width_m):
    c = npix // 2
    # Bin edges centered on each sample
    x_edges_lo = (np.arange(npix) - c - 0.5) * sample_spacing_m
    x_edges_hi = x_edges_lo + sample_spacing_m
    half = width_m / 2.0
    # Overlap of analytic rect [-half, +half] with each [edge_lo, edge_hi] bin
    overlap = np.clip(np.minimum(x_edges_hi, half) - np.maximum(x_edges_lo, -half), 0.0, None)
    kernel = overlap / sample_spacing_m  # normalize to "fraction of bin covered"
    total = kernel.sum()
    if total > 0.0:
        kernel /= total
    return kernel
```

**Why this is correct.** The analytic continuous-domain operation is convolution with a rect of width `width_m`. The correct discretization is *area integration* of that rect over each sample's bin (Riemann-integral discretization of a function), not a binary point sample. With this kernel, FFT-of-PSF agrees with the analytic `sinc` to floating-point precision regardless of `pitch/sample_spacing` ratio — the `0.05196` residual on `swir_aerial_gas` will collapse to ~1e-7 (driven by the FFT/interpolation arithmetic, not the kernel).

**Pros.**
- Preserves the MTF-product path as the analytic-`sinc` reference (no coupling to the PSF sampling grid).
- 5–10 lines of production change.
- Fixes every current and future low-Q scenario at once.

**Cons.**
- Tiny radiometric shift on integer-`pitch/spacing` scenarios (binary mask and area-integration agree exactly only when the rect edge lands on a bin edge; for non-integer ratios both kernels were "wrong" in different ways, but the analytic `sinc` is ground truth, so the fix moves toward — not away from — physics).

### Approach 2 — FFT-based product-path pixel-aperture term

Replace `_compute_optical_mtf_terms`' analytic `sinc(π·pitch·f)` for the pixel-aperture term with `FFT(_rect_1d(...))`, using the same sample spacing as the PSF path. Symmetric: both paths see the same discretization.

**Pros.**
- Even simpler conceptually: "compute the kernel once, use it on both paths."

**Cons.**
- Couples the MTF-product path to the PSF sampling grid (currently independent). Surrenders the analytic reference. Every future analyst inspecting the MTF budget will need to know the kernel was sampled on the PSF grid.
- A latent bug-attractor: if PSF sampling changes (Stage 5/6 may), the MTF product silently changes too.

**Reject Approach 2** unless Approach 1 turns out to leave a residual >1e-4. Approach 1 is the structurally correct fix.

---

## Implementation steps (after approach decision)

1. **Branch.** `git switch -c chore/cu-003-rect-kernel`.
2. **Write the failing test first** (Level 0, before edits). New file `src/radiant/optics/tests/test_pixel_kernel.py`. Three tests:
   - **A1.** `_rect_1d` of a unit-pitch rect on an integer-sampled grid (e.g., 10 samples/pitch) matches the binary mask to floating-point precision (regression guard for the integer-grid case).
   - **A2.** `_rect_1d` FFT vs analytic `sinc(π·pitch·f)` at non-integer ratio (pitch=20µm, spacing=1.6875µm) agrees to **abs ≤ 1e-6** at every frequency below Nyquist. **Today this test fails** — the binary mask deviates by up to 0.052. After the fix, it passes.
   - **A3.** Continuous-limit test: as `sample_spacing_m → 0` (e.g., 1000 samples/pixel), the kernel converges to a normalized rect of width `width_m` (sum of kernel·spacing equals `width_m` to relative 1e-9).
3. **Implement Approach 1.** Edit only `_rect_1d`. Confirm `make_pixel_aperture_kernel_2d` continues to produce a separable, normalized 2-D kernel (it should — the outer product and renormalization don't care which 1-D function is used).
4. **Re-run the new tests.** All three must pass.
5. **Re-run the consistency check on `swir_aerial_gas`.** Expected `max_err < 1e-6`. Capture exact values for the report.
6. **Re-run `scripts/capture_option_c_baseline.py`** (the script — do **not** silently overwrite the snapshot YAML). Diff `tests/integration/snapshots/option_c_baseline.yaml`:
   - **Expected:** the `swir_aerial_gas` row's `mtf_at_nyquist` shifts by some small amount (the PSF path was over-attenuating; corrected MTF will be slightly higher).
   - **Expected:** other 13 rows' `mtf_at_nyquist` unchanged to ≤1e-6 (any larger drift is a Rule-4 violation in another scenario and a STOP trigger).
   - **Expected:** all `L_aperture_W_m2_sr_um`, `nedt_K`, `snr` values unchanged to floating-point precision (the pixel-aperture kernel doesn't enter radiometry — only spatial-frequency response).
7. **Update the golden snapshot** following [docs/architecture/RADIANT_Testing_Validation.md](RADIANT_Testing_Validation.md) §5.3. Document the before/after `mtf_at_nyquist` for `swir_aerial_gas` in the commit body. **Do not touch any other row.**
8. **Full regression gate:**
   ```
   pytest src/ -q                       # 2360 + 3 new = 2363 expected
   pytest tests/integration/ -q         # 381 expected
   mypy --strict src/radiant/core src/radiant/api
   ruff check src/
   lint-imports --config pyproject.toml
   ```
9. **Move CU-003 to Resolved** in `docs/Cleanup_Backlog.md` with the commit hash and the new `max_err` value.
10. **Commit.** Format: `chore(debt): CU-003 — anti-aliased rect kernel closes Rule-4 swir_aerial_gas miss`. Body cites the new `max_err`, the `mtf_at_nyquist` delta, and confirms no other scenario drifted.

---

## Stop triggers

Stop and ask the user before continuing if any of these fire:

- **Any other scenario's `mtf_at_nyquist` shifts by > 1e-6.** That is a Rule-4 cross-scenario regression; the fix has changed something it shouldn't have.
- **Any radiometric value (`L_aperture`, `nedt_K`, `snr`) shifts at all.** The pixel-aperture kernel does not enter radiometry; any drift means an unintended coupling.
- **Approach 1 leaves `max_err > 1e-4` on `swir_aerial_gas`.** The fix is incomplete; either there is a second discretization issue or the analytic `sinc` reference frequency grid disagrees with the FFT. Diagnose before proceeding.
- **The change touches > 50 lines of production code.** Approach 1 should be ≤10 lines; if it isn't, you're rewriting more than the kernel.
- **Any unit/import/type error appears that wasn't there before.** Investigate; it may be uncovering a real bug.
- **The PSF-path EE_box, RER, FWHM, or Strehl values shift in any of the optics tests in [src/radiant/optics/tests/](../src/radiant/optics/tests/).** The kernel feeds those metrics; small shifts are expected (the PSF *should* be slightly different now), but they need explicit acknowledgment in the report rather than silent goldens.

---

## Validation requirements (Category C — full)

### Numerical truth anchors (≥3 required)

1. **Analytic `sinc(π·pitch·f)`** at `pitch=20 µm` evaluated at three frequencies `f = {0.1·f_Nyq, 0.5·f_Nyq, 0.99·f_Nyq}`. Compare to `|FFT(_rect_1d)|` on the swir_aerial_gas grid. Expected agreement: **abs ≤ 1e-6** at each frequency.
2. **DC value.** Continuous rect of width `pitch` integrates to `pitch`; the discrete area-integrated kernel multiplied by `sample_spacing_m` and summed must equal `pitch` to **rel ≤ 1e-12** (this is the area-conservation invariant).
3. **First null.** Analytic `sinc` first null is at `f = 1/pitch`. The discrete kernel's FFT must have a zero crossing within **one frequency bin** of that location.

### Dimensional audit

| Stage | Input units | Output units | Conversion | Check |
|---|---|---|---|---|
| `npix`, `c` | dimensionless count | dimensionless count | none | ✓ |
| `x_edges_*` | (count) · m | m | × `sample_spacing_m` | ✓ |
| `half` | m | m | / 2 | ✓ |
| `overlap` | m | m | min/max/clip in m | ✓ |
| `kernel` (pre-norm) | m | dimensionless | / `sample_spacing_m` | ✓ |
| `kernel` (post-norm) | dimensionless | dimensionless (sum=1) | / `total` | ✓ |
| 2-D outer product | dimensionless × dimensionless | dimensionless (sum=1) | renormalize | ✓ |

The analytic `sinc(π·pitch·f)` consumed in `_compute_optical_mtf_terms` takes `f` in cycles/m at the focal plane — verify the sampling-grid frequencies in the comparison test agree on units.

### Failure modes

- `width_m == 0` → kernel of all zeros, `total == 0`, function returns the unnormalized zero array (current behavior — preserve).
- `width_m > npix * sample_spacing_m` → all bins fully covered → uniform kernel summing to 1. Verify.
- `width_m == sample_spacing_m` → narrow case, only the central bin gets non-zero overlap. Verify single-bin kernel.
- `npix` even (currently the docstring says "must be odd" but the code uses `c = npix // 2`) → behavior is asymmetric. Decide: enforce odd or fix to handle both. Document.
- `fill_factor` at the calling site — verify `fill_factor < 1.0` still works (it scales `width_m` smaller).

### Assumptions

- **Bins are centered on samples, edges at half-spacing.** Standard convention. Document this in the docstring.
- **Continuous rect is the physical truth.** Photodetectors integrate light over the photosensitive area; the area integral over each sample's bin is the physically correct discretization.
- **Sample spacing is uniform.** True throughout RADIANT's optics path.

### Fragility analysis

- **Q < 0.2** (very-low-Q hypothetical case): the rect width is comparable to one sample. The first-null of the analytic `sinc` may fall below the smallest resolved frequency; the FFT-of-kernel cannot reproduce a feature it cannot sample. Document this floor; an `optics/sampling.py`-style sanity check might warn at very low Q (out of scope for this task).
- **`pitch / sample_spacing` very large** (e.g., > 1000): kernel becomes essentially uniform; finite-grid effects vanish. Verified by truth anchor 2.

### Cross-model consistency

The post-fix consistency check is itself the cross-model invariant. Required: `max_err_x = max_err_y < 1e-6` on every scenario in the Option C baseline, including the four currently flagged `expected_to_change_at_stage_*` cells (those classifications govern radiometry, not MTF — verify their MTF rows do not drift).

### Traceability

- Same inputs → identical outputs: yes (numpy arithmetic, no RNG).
- Deterministic seed: N/A.
- Intermediate values inspectable: kernel returned as ndarray; FFT inspectable via `np.fft.fft`.

---

## Out of scope (do not touch)

- The MTF-product-path analytic `sinc` in `_compute_optical_mtf_terms`. (Approach 1 leaves it as the reference.)
- The consistency-check tolerance (`5e-2` in `consistency_check.py`). Once Approach 1 lands, the tolerance is conservative for the right reasons; tightening it is a separate decision.
- Any other contributor MTF (jitter, smear, IPC, diffusion, TDI, optics). Investigation already excluded these.
- `_compute_optical_mtf_terms`' frequency conversion `freq_cycles_per_mrad = freq_m * focal_length_m * 1e3`. Independent.
- The Stage-deferred backlog items (CU-007/011/014 etc.). Not this task.

---

## Completion criteria

- [ ] CU-003 entry in `docs/Cleanup_Backlog.md` moved to Resolved with this task's commit hash and the new `max_err` value documented.
- [ ] New `src/radiant/optics/tests/test_pixel_kernel.py` covers the three Level 0 anchors plus the failure-mode cases above.
- [ ] `pytest src/` and `pytest tests/integration/` green; `mypy --strict`, `ruff`, `lint-imports` clean.
- [ ] `swir_aerial_gas`'s `option_c_baseline.yaml` row updated (and only that row's `mtf_at_nyquist`).
- [ ] Structured Category C report attached to the commit body or PR description with all eight Validation Section Specifications (Numerical Truth Anchors, Dimensional Audit, Failure Modes, Assumptions, Fragility, Traceability, Cross-Model Consistency, Integration & Regression).

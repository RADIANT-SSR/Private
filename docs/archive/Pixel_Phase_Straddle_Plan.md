# Pixel Sampling Phase (Straddle Factor) for Point-Source / Sub-Pixel EE_box — Plan

> **HISTORICAL** — completed 2026-09-11 by branch `gap129/pixel-phase` (Gap 129); archived in the same PR per Rule 24.

**Status:** Complete
**Date:** 2026-09-11
**Registry:** Gap 129 (`docs/tracking/gaps.md`)
**Branch:** `gap129/pixel-phase`
**Category:** C (physics: optics / platform / performance) + D (GUI + integration)

**Read first:**
`docs/architecture/RADIANT_Spatial_Complete.md` (§2 `EffectivePSF`, §6 convolution pipeline),
`docs/architecture/RADIANT_Spectral_Integration.md` (§2 EE_box source, §4 regime assemblies),
`docs/architecture/RADIANT_Detector_Complete.md` (§3.3 pixel geometry),
`docs/architecture/RADIANT_Metrics.md` (§4.10 EE),
`docs/architecture/RADIANT_GUI_Architecture.md` (§4.4.1 Detector row),
`CLAUDE.md` Rules 4, 9, 11, 19, 20, 29.

---

## 1. Objective

Make the **pixel sampling phase** of a point-source / sub-pixel target an explicit,
selectable convention. Today the chain applies the uniform-phase *average* ensquared
energy implicitly (rect ⊛ rect = triangle), while every doc and docstring says the PSF is
*centred* on the pixel. After this plan:

- the analyst chooses **average** (default, bit-identical to today), **centered**,
  **worst_case** (source on a four-pixel corner), or a **specified** (x, y) offset;
- the chain reports the resulting `EE_box`, the centred reference `EE_box_centered`, and
  their ratio `straddle_factor`;
- `ee_1x1` / `ee_3x3` follow the same convention (Rule 4: one `EffectivePSF`, one answer);
- the GUI exposes the three parameters on the Detector Inputs tab and shifts the PSF
  pixel-grid overlay by the resolved phase so the straddle is *visible*;
- the docs say what the code does.

## 2. Physics

Let `PSF(x)` be the optical PSF including every blur (WFE, diffusion, jitter, smear,
turbulence), `p` the pitch, `w = p·√FF` the photosite width, and `δ` the displacement of
the geometric image point from the pixel centre. The ensquared energy at phase δ is

$$\mathrm{EE}(\delta) = \iint \mathrm{PSF}(x)\,\mathrm{rect}_w(x-\delta)\,dx .$$

The chain convolves the unit-sum photosite rect into the `EffectivePSF`
(`optics/stage.py` §6 step 1): `conv(x) = (PSF ⊛ rect_w/w²)(x)`. Therefore

$$\mathrm{EE}(\delta) = w^2\,\mathrm{conv}(\delta)
  = \mathrm{FF}\cdot p^2\,\mathrm{conv}(\delta) ,$$

i.e. **the pixel-convolved PSF evaluated at δ is the ensquared energy at phase δ** — no
second box integral, no un-convolution. The stage that consumes `EE_box` multiplies by
`FF` separately (CU-074 collection efficiency), so the value the chain needs is
`EE_box(δ) = p²·conv(δ)` — exactly what `n²`-pixel boxing of `conv` gives when averaged.
The three conventions are:

| Mode | δ | Value |
|---|---|---|
| `average` | uniform over one pitch | $\frac{1}{p^2}\int_{\text{pitch}} p^2\,\mathrm{conv}(\delta)\,d\delta$ = the existing pitch-wide box integral of `conv` (unchanged code path) |
| `centered` | (0, 0) | $p^2\,\mathrm{conv}(0)$ — equals the optics-only analytic anchor (0.177327 at Q=2) |
| `worst_case` | (p/2, p/2) | $p^2\,\mathrm{conv}(p/2, p/2)$ — the four-pixel straddle |
| `specified` | (φ_x·p, φ_y·p), φ ∈ [−0.5, 0.5] | $p^2\,\mathrm{conv}(\delta)$, bilinear between samples |

For an n×n block the value is the sum over the block's pixel centres,
$\sum_{i,j} p^2\,\mathrm{conv}(\delta + (i,j)p)$; the average mode's n-pitch box integral is
that sum's phase expectation, so all four modes agree on their definitions for every n.

Measured on the Q=2 Airy of the anchor test (`optics/tests/test_ee_box.py`): centred 0.1771,
average 0.1606 (chain today), edge 0.1532, corner 0.1321. At Q=1: 0.525 / 0.392 / 0.208.

**No MTF-path term.** Sampling phase is a *position*, not a blur: it has no kernel and no
MTF, so the product path and the consistency check are untouched (same standing as the
TDI mis-registration term, which is MTF-only for the mirror-image reason).

**Reference point.** δ is measured from the PSF grid centre — the geometric (chief-ray)
image point — not from the degraded PSF's centroid. For asymmetric blur (smear) the
"centred" and "worst-case" conventions are therefore defined relative to where the
optics *place* the image, which is what a pointing or centroiding analysis controls.

## 3. Ownership decision (owner question, 2026-09-11)

| Candidate | Verdict | Why |
|---|---|---|
| **Detector (parameters)** | **chosen** | The phase is "where on the *detector's* pixel grid the image lands"; `pixel_pitch_*` and `fill_factor`, which define the box, already live in `detector._schema`; the GUI home is the Detector Inputs tab beside them. |
| Platform (computation) | **kept as-is** | Rule 9 requires `EE_box` from the *fully degraded* PSF, which only exists after `PlatformStage`'s kernels. The stage already reads cross-stage parameters (`optics.focal_length_m`); reading `detector.pixel_phase_*` is the same pattern. |
| Optics | rejected | Produces the PSF but knows nothing about target placement on the grid; `optics/ee_box.py` stays a thin helper. The **method** lives on `EffectivePSF` (optics-owned) because that is the one object every spatial metric derives from (Rule 4); stages call it duck-typed (Rule 11). |
| Source / scenario | rejected | "average" vs "worst case" is an analysis convention, not a scene property. |

## 4. Parameters (`src/radiant/detector/_schema.py`)

| Name | dtype | unit | default | bounds / enum |
|---|---|---|---|---|
| `detector.pixel_phase_mode` | str | — | `average` | `average`, `centered`, `worst_case`, `specified` |
| `detector.pixel_phase_x` | float | fraction of pitch | 0.0 | [−0.5, 0.5]; used only in `specified` |
| `detector.pixel_phase_y` | float | fraction of pitch | 0.0 | [−0.5, 0.5]; used only in `specified` |

Ignored (documented, not warned) in the extended regime, where `EE_box ≡ 1` (Rule 9).

## 5. Phases

Each phase: Level-0 test first, then code, then commit. Tests never use RADIANT-computed
expectations except where the identity under test *is* the equality of two RADIANT paths.

**P1 — Schema.** Three `ParameterDef`s + `ALL_PARAMETERS`; regenerate
`docs/guides/parameter_reference.md`. Test: schema registration, bounds, enum rejection.

**P2 — Optics: phase-resolved ensquared energy.**
`optics/pixel_phase.py::resolve_pixel_phase(mode, phase_x, phase_y) -> tuple[float, float] | None`
(one computation, one module — Rule 19; `None` ⇒ average).
`EffectivePSF.ensquared_energy_nxn(n_pixels, *, phase_mode="average", phase=(0.0, 0.0))`:
average ⇒ existing box integral; otherwise the block sum of `p²·conv(δ + (i,j)p)` with
bilinear interpolation, guarded by an actionable `OpticsValidationError` when
`"pixel_aperture"` is absent from `convolution_history` (the identity needs it).
Tests (`optics/tests/test_pixel_phase.py`): centred on the pixel-convolved Q=2 Airy equals
0.177327 (abs 1e-3) — the chain-level anchor the old test lacked; average equals the
explicit 33×33 phase average (abs 5e-4); corner < edge < centred; specified (0,0) ≡
centred; specified (0.5,0.5) ≡ worst_case; 3×3 average ≡ box; symmetry ±φ; missing pixel
kernel raises; bad mode raises.

**P3 — Platform.** `_compute_ee_box` takes mode + phase; publishes `EE_box` (mode),
`EE_box_centered`, `straddle_factor = EE_box / EE_box_centered`, `pixel_phase_mode`,
`pixel_phase_x_pix`, `pixel_phase_y_pix` (resolved; NaN-free — average publishes 0,0 with
the mode string carrying the meaning); `OUTPUT_UNITS` updated. Tests: default bit-identical
to `ensquared_energy_nxn(1)`; worst_case < average < centered; extended ⇒ 1.0 and
straddle 1.0.

**P4 — Performance.** `ee_1x1` / `ee_3x3` pass the mode through; new metric
`straddle_factor` (registry, `spatial_mtf` group, reconciliation test list, Metrics doc
§4.10 + §6 key list). Test: metric present, equals platform output, 1.0 in extended.

**P5 — API plot.** `_overlay_pixel_grid(ax, psf, span_pixels, phase_pix=(0,0))` shifts the
gridlines by the resolved phase; `plot_psf(..., pixel_phase=...)`;
`result.plot.psf_pixel_grid()` reads the platform outputs and passes them (average draws
the centred grid and appends "phase: average" to the title). Test: gridline positions
shift by φ·pitch.

**P6 — GUI.** `DetectorInputsForm`: new group **"Pixel sampling phase"** with the three
rows (enum row edits through the existing `ParameterEditorDialog` combo — no new widget).
Tests: manifest-equals-schema test still passes (it must — the new params are in the
schema); the form lists the three dot-paths; editing the mode re-evaluates and the
Detector + PSF tab's grid moves. **Owner live review before merge** (ratified 2026-09-01).

**P7 — Docs (Rule 20, same PR).** `RADIANT_Spatial_Complete.md` §2 (real signature; drop
the phantom `offset_m`), new §6.1 "Pixel sampling phase (straddle)"; `RADIANT_Spectral_Integration.md`
§2 EE_box bullet; `RADIANT_Detector_Complete.md` §3.3 + §11.1 (27 → 30);
`RADIANT_Metrics.md` §4.10 + key list; `RADIANT_GUI_Architecture.md` §4.4.1 Detector row;
`RADIANT_Signal_Chain_Architecture.md` PlatformStage row; `CLAUDE.md` Rule 9 and
`RADIANT_Master_Architecture.md` C6 (one clause each: EE_box is evaluated at the selected
pixel phase); `CHANGELOG.md` **Added** (not results-affecting at default); Gap 129 → FIXED;
this plan → `docs/archive/`.

## 6. Gates

Schema touched ⇒ **full battery**: `pytest -q` (includes the GUI suite), `pytest scripts/`,
`mypy --strict src/radiant/core src/radiant/api`, `ruff check` + `ruff format --check` on
the four trees, `lint-imports`, `check_org_rules.py`, `gen_param_reference.py --check`.
Golden baselines must not move (default = average = today's number).

## 7. Decisions and open questions

- **Default = `average`.** Bit-identical to shipped results and the physically expected
  value for a randomly placed source. The owner may re-rule to `worst_case` for
  requirement flow-down; that would be Results-affecting and re-baseline the point-source
  goldens.
- **Sub-pixel regime** reuses the point-source EE_box (existing approximation): the offset
  applies to the PSF, not to a PSF ⊛ target-footprint. Recorded as a known limitation in
  §6.1, not solved here.
- **Pd averaging.** Averaging EE then computing Pd ≠ averaging Pd over phase. The
  `specified` mode plus the existing sweep machinery is the route to the honest number;
  no new metric is added for it.

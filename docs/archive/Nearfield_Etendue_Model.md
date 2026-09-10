> **HISTORICAL — archived 2026-09-09 (completed by the coding agent; W1–W6 all landed on branch `gap128/etendue-nearfield`).** Effective pupil in `optics/effective_pupil.py`; cone-only near-field in `optics/etendue_cone.py` + `optics/nearfield_irradiance.py`; `optics.nearfield_fraction` (+ alias), `optics.optics_distance_to_fpa_m`, and the element-format `diameter_m` / `distance_to_fpa_m` keys deleted with Gap-128-naming errors; scenarios 7.2/7.5/10.1 retuned to realistic coated trains and 7.4 rebuilt as the undersizing sweep. Anchors verified (§4): Ω_cone(f/6) = 0.0217036 sr vs paraxial 0.0218166 sr (−0.52 %); BLIP integral reproduced within the exact-form correction; the legacy-coincidence check reproduces the Gap-127-era number to exactly that difference. Defaults (u = 0) bit-identical on every non-element result; the four element-mode scenario deltas are enumerated in `CHANGELOG.md`.

# Étendue-Conserving Near-Field and the Cold Stop as Pupil Stop (Gap 128)

**Status:** Complete — owner ratified the model rules in conversation, 2026-09-09 (two
rounds: cone-only geometry + perfect out-of-cone blocking; then the cold stop as an
undersized aperture stop).

**Date:** 2026-09-09
**Category:** C (physics model change; D-style regression section — element-mode
scenarios change results).
**Tracking:** Gap 128 (`docs/tracking/gaps.md`). Successor to Gap 127.

**Read first:**
`docs/architecture/RADIANT_Optics.md` (§4 aperture, §6 elements, §7 nearfield),
`docs/architecture/RADIANT_Master_Architecture.md` (Rule 4 dual-path),
`docs/plans/Optics_Emission_Model_Rules.md` (Gap 127 — the model this completes).

---

## 1. The defect

The near-field model gives each element a private geometry, Ω_i = π(D_i/2)²/d_i²
(`OpticalElement.nearfield_solid_angle_sr`). But the pixel's étendue is fixed by the
Lagrange invariant: every in-beam element is seen through the reimaging optics and can
fill at most the acceptance cone set by the working f/#. Measured violation: a mirror
with D = 0.3 m at d = 1.0 m in the f/6 SDA scenario claimed Ω = 0.0707 sr against a
cone of ≈ 0.0218 sr — 3.2× more than physics permits. The legacy scalar lump was
correct only by coincidence (D = aperture, d = focal length ⇒ exactly π/(4N²)).
Separately, `optics.nearfield_fraction` (η_cold) multiplies element emission — but a
cold stop cannot block in-cone emission; it arrives through the imaging path itself.

## 2. Owner-ratified rules (2026-09-09)

1. **One geometry: the étendue cone.** Ω_cone = 2π(1 − cos θ), θ = arctan(1/(2·N_eff)),
   exact form (not the paraxial π/(4N²)). Per-element `diameter_m` and
   `distance_to_fpa_m` are deleted everywhere (schema, YAML element format, factories,
   GUI element table — GUI lands separately after this plan).
2. **Near-field:** `E_nf(λ) = Ω_cone · Σ_i ε_i(λ) · B(λ, T_i) · τ_down_i(λ)`.
3. **Perfect out-of-cone blocking, always.** No enclosure term, no shield temperature;
   `optics.nearfield_fraction` and its deprecated alias `cold_stop_efficiency` are
   deleted.
4. **The cold stop is the aperture stop, slightly undersized for tolerancing.** New
   parameters (names final at implementation, schema-reviewed):
   - `optics.cold_stop_undersize_frac` (default 0.0): fractional reduction of the
     pupil diameter — `D_eff = (1 − u) · D`;
   - `optics.cold_stop_obscuration_ratio` (default 0.0): obscuration imposed by the
     cold shield — effective obscuration = max(primary obscuration, this).
   The **effective pupil** (D_eff, obs_eff) feeds A_collect, N_eff = f/D_eff, the
   complex pupil function (diffraction PSF/MTF — Rule 4: both paths), and Ω_cone.
   Signal and near-field scale together, as they physically do. Defaults preserve
   today's geometry bit-exactly.

**Accepted limitations (document, don't model):** field-conjugate (direct-view)
elements are treated as pupil-filling; uncooled cameras without a cold stop are outside
the near-field model's scope.

## 3. Work items

**W1 — Effective pupil.** In `OpticsStage`, derive (D_eff, obs_eff) from the primary
aperture + the two new cold-stop parameters, once, before anything consumes aperture
geometry. Everything downstream — `A_collect`, f/# resolution, pupil amplitude mask,
PSF/MTF, sampling — uses the effective pupil. Rule 4 audit: the change must enter the
pupil ONCE so both spatial paths stay consistent (consistency check must stay green).
New `_schema.py` entries with bounds and justifications; `f_number` consistency-group
interaction reviewed (`optics.f_number` refers to the primary; N_eff derived).

**W2 — Cone-only near-field.** Replace the Ω_i sum in
`optics/nearfield_irradiance.py` with rule (2) (Ω_cone passed in from the stage;
`nearfield_solid_angle_sr` property deleted). `compute_nearfield_irradiance` signature
changes; `cold_stop_efficiency` argument deleted.

**W3 — Schema/format deletions.** `optics.nearfield_fraction` (+ alias) removed from
`_schema.py`; `diameter_m` / `distance_to_fpa_m` removed from `OpticalElement`, the
factories, `io/element_config.py` (YAML keys become unknown-key errors with an
actionable message naming Gap 128), and templates/examples if any carry them.

**W4 — Scenario retune (results-affecting, deliberate).**
- 7.2 / 7.5 / 10.1: replace the fallacy-era single mirror (ε = 0.26–0.32) with a
  realistic train (per-mirror R ≈ 0.97–0.98 ⇒ train ε ≈ 0.03–0.06); η_cold deletion
  and ε correction land together; goldens regenerate under the
  `RADIANT_Testing_Validation.md` §5.3 protocol with per-metric deltas reported.
- 7.4 becomes the **cold-stop undersizing sweep**: sweep `cold_stop_undersize_frac`
  (e.g. 0–10 %) showing SNR / near-field / MTF response — the tolerancing-margin vs
  signal trade. Walkthrough and gui_workflow.md rewritten accordingly.
- SDA template comment refreshed if it references the old geometry.

**W5 — Tests.** Level 0: Ω_cone exact form vs hand calc at f/2 and f/6 (state the
paraxial delta); étendue ceiling — no element-mode config can exceed Ω_cone; effective
pupil arithmetic; default-zero bit-identity regression (u = 0 ⇒ today's numbers).
Level 1/2: near-field scales with Ω_cone under undersizing; PSF/MTF respond to D_eff;
consistency check green.

**W6 — Docs + CHANGELOG.** `RADIANT_Optics.md` §4/§6/§7 rewritten for the effective
pupil and cone-only near-field; parameter reference regenerated; CHANGELOG
**Results-affecting** (η_cold deletion magnitudes; scenario retunes) + **Added**
(cold-stop parameters) + **Removed** (nearfield_fraction, element geometry fields).

## 4. Validation (Category C)

- **Anchors:** (1) Ω_cone hand calc: f/6 → 2π(1−cos(arctan(1/12))) = 0.021703 sr vs
  paraxial π/144 = 0.021817 sr (−0.52 %); (2) the classic BLIP background integral
  Q = (π/(4N²))·A_pix·∫ε·B·(λ/hc) dλ·t reproduced within the exact-form correction;
  (3) legacy-coincidence check: a one-lump train at D = aperture, d = f reproduces the
  Gap 127-era number to the paraxial-vs-exact difference exactly.
- **Regression:** full battery; default-zero cold stop must leave every non-element
  golden bit-identical; element-mode scenario deltas enumerated per §5.3.

## 5. Out of scope

- GUI Transmission-tab redesign (owner ordering 2026-09-09: physics first; separate
  plan/live review) — includes removing the two dead element-table columns.
- CU-351 (up/down reference-phase charge) — separate owner ruling pending.
- Any enclosure/no-cold-stop emission model (accepted limitation).

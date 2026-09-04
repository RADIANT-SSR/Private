# Changelog

All notable changes to RADIANT are recorded here, per CLAUDE.md Rule 29.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Newest entries
at the top of `[Unreleased]`; on release, `[Unreleased]` rolls into a dated
version heading. Categories: **Added** / **Changed** / **Deprecated** /
**Removed** / **Fixed**. Entries that change computed numbers (physics models,
parameter defaults, golden baselines) are prefixed **Results-affecting:** and
state the direction and rough magnitude of the change.

What gets an entry (Rule 29): changes to computed results, public API surface
(methods, parameters, metrics, error classes, config fields), and capability
additions or removals. What does not: refactors, doc-only, test-only, and
internal changes with no observable effect.

This changelog begins 2026-07-07. Earlier history lives in `git log`,
`docs/tracking/gaps.md`, and `docs/tracking/Cleanup_Backlog.md` and is not
retroactively reconstructed.

## [Unreleased]

### Added
- **Per-configuration optical elements — configured element rows** (Gap 103
  v1.1, ADR-0010 D-7 supersession, owner-ratified 2026-09-02 in live review). A
  **row** of the shared `optical_elements:` document can be configured, exactly
  as a parameter can: it then carries one complete entry per configuration —
  dense, every member present — written in place in the YAML as
  `- configured: {member: entry, …}` and re-validated at load through the single
  io element-parser authority (Kirchhoff included) with the owning configuration
  named. Row identity is **positional**: the row count and order are shared by
  every configuration, and the entry's `name` configures with the row. New
  scripting API on `ConfigurationSet`: `configure_element` / `set_element_for` /
  `element_for` / `unconfigure_element(keep=)` / `is_element_configured` /
  `configured_element_indices` / `element_count` / `effective_optical_elements`;
  `sensor_for` and `evaluate_all` pick up each member's effective train
  automatically. In the GUI Elements tab a study's rows carry the same
  right-click *Configure across configurations…* / *Un-configure row (keep
  <first>'s entry)…* actions and the same red "C" as a configured parameter;
  editing a configured row's cell writes the **displayed** configuration's entry
  only (ADR-0010 D-8), while a shared row writes the document every
  configuration inherits. Per-configuration addition or removal of a row remains
  excluded — structure is shared.

### Changed
- **The Elements tab commits on edit, like every other parameter surface**
  (owner-ratified 2026-09-03; the *Apply train* button is removed). A completed
  cell edit, combo change, CSV pick, spectrum entry, add, remove, or reorder
  writes the document immediately and the evaluation follows. A transiently
  invalid row (e.g. a REFLECTIVE→REFRACTIVE flip before the value is retyped)
  stays a visible pending draft with the parser's message shown inline and
  commits with the next valid edit.

### Fixed
- **Results-affecting: Elements-tab commits are now entry-faithful (CU-344).**
  The table previously injected `diameter_m: 0.1` / `distance_to_fpa_m: 1.0`
  into entries that never specified them, dropped a refractive row's
  `reflectance`, and case-rewrote `kind` — on every commit, for rows the
  operator never touched. Cells for keys an entry does not carry now render
  blank and write nothing; unrepresented keys ride through untouched. Direction
  and magnitude: GUI-committed studies with minimal-key element entries change
  computed results toward the scripting-API answer for the same document — on
  the three-band review scenario, SNR for the edited band moves from 220.5 to
  58.5 (dimensionless), the faithfully-authored value.
- **Elements-tab Apply no longer loses the train edit in a study session.**
  Previously Apply wrote the element document to the displayed configuration's
  throwaway materialization, so in any session with configured values the edit
  vanished on the next selector switch; Apply now targets the study document
  (the shared skeleton, plus the displayed configuration's entry for each
  configured row).
- **Elements tab: removing a row no longer breaks the coating-detail pane.** Qt
  emits the selection change *during* the row removal, so the pane serialized a
  table whose cell widgets were already gone and raised inside the Qt event
  loop; the table is now silenced across every structural mutation and refreshed
  once it is complete.
- **Mission-template welcome screen (GUI, §4.4a — owner-confirmed brief).** With
  no configuration loaded, the central canvas shows six hand-authored mission
  templates (ground→air MWIR detection, LEO thermal mapping, maritime sub-pixel
  LWIR, lab blackbody calibration, airborne LWIR surveillance, SDA
  space-to-space) as one-click cards beside Blank config and Open recent.
  Picking a card runs the ordinary open pipeline, auto-evaluates, and surfaces
  the template's tune-next parameters as clickable guidance rows in Messages
  that reveal the named row in the parameter tree. Every template is CI-gated
  to load, evaluate warning-free, and derive its declared regime.
- **`radiant.api.config_io.read_template_meta(path)`** — the
  `_radiant.template` metadata block of a config without loading a sensor.

### Changed
- **File → New returns to the welcome screen** (after the unsaved-edits
  guard); its Blank config card performs the previous blank-adopt exactly.


### Changed
- **Results-affecting: the calibrated gas table is re-fitted with both sides of the
  floor measured on one spectral grid (CU-336) — small VIS τ *increase* above 0.45 µm,
  a decrease below it.** `floor_add` is a *difference* of two band optical depths: the
  MODTRAN ladder's, and the model's own non-water (Rayleigh + aerosol) reference. The
  two were not measured the same way. The ladder's comes off MODTRAN's native grid,
  uniform in **wavenumber** at 1 cm⁻¹ (so Δλ ∝ λ²), while
  `scripts/fit_simple_atmosphere_gas_bands.py` evaluated its reference on a uniform-λ
  grid; both band optical depths are `−ln` of an *unweighted* mean of the samples in the
  band, so for the λ⁻⁴-steep Rayleigh term the two weightings disagree, always toward an
  over-large floor. CU-335 measured and recorded that bias as its own residual; this is
  the fix. The generator now evaluates the reference on the ladder's grid and asserts
  the staged runs share one before using it. `k_h2o` and `b_h2o` are bit-identical on
  all seventeen rows a second time, and everything from 5.00 µm up — including CU-330's
  ozone triple — is unmoved again.
  **Floors, CU-335 → CU-336:** 0.45–0.70 µm `0.1597 → 0.1375` (−0.0222), 0.70–1.30 µm
  `0.0517 → 0.0402` (−0.0115) — exactly the offsets CU-335 measured — plus ≤ 0.0004 at
  1.50–5.00 µm. The same convention also removed a *coverage* mismatch in the first row:
  the delivered tape7 grid starts at 0.374953 µm, so the measured 0.30–0.45 µm optical
  depth was always the 0.375–0.45 µm mean while the reference spanned the whole region,
  including 0.30–0.375 µm where Rayleigh alone is enormous. That inflated reference, not
  the aerosol, is what held the row at the zero clamp; it now reads
  `0.0000 → 0.1262`, within 0.014 OD of the 0.45–0.70 µm floor, replacing an artificial
  0.16 OD step at the 0.45 µm edge with a continuous short-λ deficit.
  **Direction and magnitude:** **more transmissive above 0.45 µm, less transmissive
  below it.** VIS/NIR SNRs **rise** 0.4–5.8 % (1.2 +2.0 % at every aperture × altitude cell,
  1.4 +5.8 % and per-line signal +9.1 %, 1.5 +1.5 %, 3.1 +1.6…2.0 %, 3.4 +4.0 %,
  5.1 +4.2 %, 5.4 +2.2 %, 10.3 +0.4 %); 5.5's contrast SNR eases −0.15 % (the mirror of
  the CU-335 move — both pedestals rise together). MWIR and LWIR products move by
  ≤ 0.03 % (the Rayleigh λ⁻⁴ tail: 3.50–5.00 µm floor 0.4498 → 0.4494). Nineteen of the 43
  scenarios moved — their committed figures re-render differently, and scenario figures are
  pixel-reproducible on a fixed tree — so the other 24 are unchanged. **No verdict flips** — 3.1's 42° NIIRS-floor
  crossing and 478 km corridor, 1.4's N_tdi = 96 saturation knee, 5.4's out-of-reach
  NIIRS = 6.0 floor and 10.3's failing published-extinction anchor all stand, the last
  easing 0.282 → 0.261 mag/airmass against a published 0.12–0.20 band.
  **Parity:** at the fit's own A1 anchor the model's 0.45–0.70 µm band optical depth
  reads 0.4566 against MODTRAN's 0.4561 — **0.1 %**, from 4.3 % under CU-335 and 30 %
  before it. Band-mean τ over the thirteen full-column anchors improves a further
  **2.6×** on 0.45–0.70 µm (RMS |ln ratio| 0.0294 → 0.0111, 14× since CU-161), **1.8×**
  on 0.45–0.85 µm and **1.2×** on 0.85–1.40 µm, and the 0.70–1.30 µm row CU-335 degraded
  **recovers past its starting point** (0.0402 → 0.0286 against 0.0312). The MWIR and
  LWIR controls are unchanged to the metric's 0.002 resolution. Two trades are recorded
  rather than tuned: the 0.40–0.90 µm composite reads 0.0244 → 0.0292 because its
  0.40–0.45 µm half was 8–21 % too transmissive on every anchor and is now inside
  0.4 %, so what the band mean loses is a cancellation, not accuracy (the sub-band itself
  improves 8×); and the up-looking single-scatter sky anchors drift ≤ 2 % away from unity
  (worst VIS excursion 1.217× → 1.231×) because a column with less absorbing opacity
  scatters less — every adoption ceiling still holds. The remaining VIS floor is still
  more than gas chemistry supplies; that attribution is CU-337.
- **Results-affecting: the calibrated gas table's VIS/NIR/SWIR floors are re-fitted
  against the corrected Rayleigh (CU-335, owner-approved 2026-08-30) — VIS SNRs drop
  5–35 %.** `SimpleAtmosphere`'s well-mixed-gas floor is defined as the measured band
  opacity *in excess of* what Rayleigh and aerosol already supply, clamped at zero
  rather than allowed to go negative. CU-161 fitted it on 2026-07-17 against a
  Rayleigh optical depth ~8× too large, so every floor below 1.5 µm clamped; CU-253
  corrected Rayleigh on 2026-07-28 and the fit was never re-run, leaving the model
  ~15 % too transmissive in the visible. This is the follow-through: the same
  generator, the same three-point closed form, the same D4/A1/D5 water ladder.
  Only `floor_od` moves — `k_h2o` and `b_h2o` are solved from the MODTRAN band
  optical depths alone and are bit-identical on all seventeen rows:
  0.45–0.70 µm `0.0000 → 0.1597`, 0.70–1.30 µm `0.0000 → 0.0517`,
  1.50–1.75 µm `0.0133 → 0.0219`, 2.05–2.40 µm `0.0725 → 0.0749`, and the Rayleigh
  λ⁻⁴ tail at 2.40–3.10 / 3.10–3.50 / 3.50–5.00 µm (`+0.0010 / +0.0005 / +0.0001`).
  Every row from 5.00 µm up, including CU-330's three ozone rows, is bit-identical.
  **Direction and magnitude:** uniformly **less transmissive** in the VIS/NIR — band-mean
  τ on 0.45–0.85 µm falls ~11 % on a full column — so VIS SNRs **drop**. Measured on the
  scenario sweep: 1.2 −15 % at every aperture × altitude cell, 1.4 −40 % (and the TDI
  saturation knee moves 64 → 96), 1.5 −14.8 %, 3.1 −15 %, 3.4 −34 %, 5.1 −33 %,
  5.4 −27 %, 5.5 contrast SNR **+1.8 %** (the background pedestal falls with the target),
  10.3 −4.9 %. MWIR and LWIR products move by ≤ 0.01 % (the λ⁻⁴ tail) and 22 of the 43
  scenario runners are byte-identical. Three verdicts move: 3.1's NIIRS ≥ 6 access
  corridor narrows 527 → 478 km (the quality limit now binds inside the 45° agility
  envelope), 5.4's NIIRS = 6.0 floor becomes unreachable at any jitter, and 10.3's
  published astronomical-extinction anchor flips PASS → FAIL (0.127 → 0.282 mag/airmass
  against a published 0.12–0.20 band — the model's configured rural-23 aerosol is
  dirtier than the good-site literature that band is quoted for; the MODTRAN anchor on
  the same band improved 5.3× in the same change).
  **Parity:** band-mean τ against the thirteen full-column MODTRAN anchors improves
  **5.3×** on 0.45–0.70 µm (RMS |ln ratio| 0.1556 → 0.0294), **4.2×** on 0.40–0.90 µm
  and **2.5×** on 0.45–0.85 µm; the MWIR and LWIR controls are unchanged to the metric's
  0.002 resolution. Two residuals are recorded rather than tuned: 0.70–1.30 µm parity
  moves the wrong way (0.0312 → 0.0402) because the generator's non-water reference is
  measured on a uniform-λ grid while the ladder's band OD comes off the tape7 grid
  (+0.011 OD of over-supply there, +0.022 in the visible), and 0.16 optical depths is
  more than real 0.45–0.70 µm gas chemistry supplies, so part of the visible floor is an
  aerosol deficit wearing a gas label. Both are in the parity document's limitations
  register (items 14 and 15); correcting either changes CU-161's calibration convention
  and needs its own authorisation.
  The table is now a single vintage — one generator run reproduces all seventeen rows,
  CU-330's included — so the per-row vintage split beside it is closed.
- **Results-affecting: 9.6 µm ozone emission is now placed at the ozone layer, not on
  the well-mixed gas profile (CU-324 item 2, owner-approved 2026-08-30).** The
  height-resolved emission temperature placed the whole calibrated gas floor —
  CO₂/N₂O/CH₄ *and* O₃ — on one pressure-broadened 4 km profile, so a band whose real
  emission comes from the mid stratosphere was emitted from the first few kilometres of
  air. Inside the 9.40–9.90 µm O₃ ν₂ region the floor is now partitioned: the ozone share
  rides a Gaussian layer at 25 km (σ = 5 km, the US Standard Atmosphere ozone profile)
  and the remainder keeps the 4 km placement.
  **Zero fitted coefficients.** The share is computed from the τ table rather than
  written down — the blended floor is evaluated twice, once as shipped and once with the
  band row carrying its clean-window neighbour's floor, and the ozone is the excess:
  `(0.8877 − 0.1494)/0.8877 = 0.8317` today, tracking any future re-fit automatically.
  Because both floors pass through the same CU-267 smoothstep, the placement is
  continuous in λ at 9.40 and 9.90 µm with no second ramp implementation.
  **Direction and magnitude:** the 9.6 µm band emits from colder air, so LWIR path
  thermal falls inside 9.4–9.9 µm. Against the fourteen matched MODTRAN pairs the
  feature's RMS |ln ratio| improves 2.6× (0.3581 → 0.1389 — better than the 0.1519 that
  preceded CU-330, so the interim regression that landing recorded is cleared), the
  one-sided warm bias collapses (12/14 pairs over-predicting → 5/14, worst pair
  1.95× → 1.27×), and the 8–12 µm band mean improves 0.2632 → 0.2522. The τ-derived
  share lands 3.1 % off the free optimum it was never fitted to, inside the ruling's
  15 % stop-and-flag bar by a factor of five. The 14-anchor LWIR thermal scoreboard
  reads its best yet: 0.2632 → 0.2522 RMS, ten rungs moving toward unity (H1
  1.243 → 1.055 is the largest). Up-looking sky radiance improves too: H2 1.26 → 1.12,
  H4 1.08 → 1.05.
  **Nothing outside the band moves.** Where the ozone share is zero — any grid that does
  not reach 9.4–9.9 µm — no layer is constructed and the emission temperature is
  bit-identical to the four-species form; every MWIR anchor ratio is unmoved, and τ is
  untouched everywhere (this is a redistribution in altitude, not a change of opacity).
  Downstream: Cell 28 `nedt_K` +0.0042 % with all six `L_aperture` anchors and `snr`
  holding to the 1e-6 anchor tolerance; six scenario GUI baselines move (`snr` −0.005 %
  to −2.37 %, largest 8.2 1656.94 → 1617.60; `nedt_K` +0.003 % to +2.64 %); the MWIR LEO
  golden is untouched. Three shallow up-looking rungs (1/3/5 km) move slightly *away*
  from unity, which is the τ table handing a low column ozone opacity it does not hold —
  now visible instead of cancelled, and recorded as limitation 15 in
  `docs/validation/atmosphere_modtran_parity.md` §3. The 9.90–10.00 µm long-wave tail is
  deliberately out of scope and still placed as well mixed. Full tables: §2.14(b).
- **Results-affecting: the 8–10 µm gas region is split at the 9.6 µm ozone band
  (CU-330, owner-scheduled 2026-08-29).** `SimpleAtmosphere`'s calibrated gas table
  carried one flat region across 8.00–10.00 µm — a 2 µm slab spanning both the clean
  window and the O₃ ν₂ fundamental — so the model had no identifiable ozone opacity
  anywhere: on a nadir full column `τ(9.60 µm)` and `τ(8.70 µm)` agreed to six
  figures. The CU-161 fit was re-run, unchanged, on a partition cut at the band edges
  the delivered MODTRAN ladder shows, giving three rows in place of one:
  8.00–9.40 µm `(0.1494, 0.0992, 1.204)`, 9.40–9.90 µm `(0.8877, 0.0409, 1.701)`,
  9.90–10.00 µm `(0.3013, 0.0379, 1.805)`. The table now has 17 regions and 16
  interior blend edges.
  **Direction and magnitude:** the model gains in-band optical depth (the retired slab
  fitted `−ln⟨τ⟩` over a span containing a deep 0.5 µm feature and so understated it),
  so τ falls and the atmosphere's own emission rises inside 8–10 µm. Nothing outside
  8–10 µm moves at all — every MWIR quantity in the sweep is bit-identical, as are the
  11, 12 and 13 µm anchors. Band-mean τ parity against 13 full-column MODTRAN anchors
  improves 4.0× in the clean window (RMS |ln ratio| 0.1606 → 0.0397) and 3.2× in the
  ozone band (0.5637 → 0.1747); 8–12 µm improves 0.0510 → 0.0482.
  Downstream: Cell 28 `L_aperture` +0.20 % at 8 µm, +0.17 % at 9 µm, +0.41 % at 10 µm
  and bit-identical at 11/12/13 µm, `nedt_K` −0.0025 %; the MWIR LEO golden is
  untouched; five scenario GUI baselines move (`snr` −0.03 % to −0.36 %, largest 6.4
  922.13 → 918.80), and the 25-cell horizontal-arm τ grid moves 0.2–3.1 %.
  **One product gets worse, deliberately:** 9.4–9.9 µm *path-thermal* parity on the
  fourteen matched pairs reads RMS |ln ratio| 0.3581 against 0.1519 before, because the
  flat slab had been under-supplying the very opacity whose known mis-placement carries
  that error. The 8–12 µm band mean is essentially unmoved (0.2611 → 0.2632), so no
  standard LWIR band regresses. Placing the opacity at its real altitude is CU-324
  item 2, which this change unblocks by making the ozone share of the well-mixed floor
  arithmetic — `(0.8877 − 0.1494)/0.8877 = 0.832` — instead of a free parameter.
  Measured against the emission parity it was not fitted to, that share lands within
  7 % of the parity's own optimum. Full tables: `docs/validation/atmosphere_modtran_parity.md`
  §2.15 (τ) and §2.14(b) (the re-measured item-2 sweep).
- **Results-affecting (late attribution, CU-334): scenario 1.6's MWIR point-source
  SDA numbers moved on 2026-08-03 with CU-321, and were not recorded at the time.**
  A bisect of 1.6's runner over every `main` landing between the 2026-08-02
  walkthrough refresh and 2026-08-29 pins the movement to a single commit —
  `6cf6eaa9` (merge `2192eac8`), the CU-321 height-resolved emission temperature —
  with every other candidate in that window (CU-315/CU-323, CU-316, the CU-325
  sweep-dialog family, the CU-329 point-source (ε, T) door un-grey, the display-unit
  preference) leaving 1.6 bit-identical. **Direction and magnitude:** SNR
  17.6717 → 20.3494 (**+15.2 %**) and detection range 1 254.70 → 1 347.81 km
  (**+7.4 %**). The signal is untouched (20 932.83 e⁻ to all digits — the target is a
  declared point intensity) and so is τ (identical to 13 significant figures); the
  whole movement is the background. Down-looking band-mean path radiance falls
  0.4806 → 0.2545 W/m²/sr/µm because the column stops emitting at its near-surface
  endpoint temperature — the emission temperature inverted from
  `L_path = (1 − τ)·B(λ, T_eff)` goes 292.9 → 277.4 K at 4.0 µm and becomes
  spectrally structured — so `background_shot`, the only noise term that moves,
  falls 1 171.9 → 1 014.1 e⁻ RMS. **This is the intended direction of the CU-321
  fix**, by the same mechanism CU-321 already recorded for scenario 10.1
  (SNR 130.1 → 144.6). What was missed is the §5.3 refresh: 1.6 is the only one of
  the 20 scenario configurations that moved whose walkthrough was not re-run in that
  PR, because it is the only moved scenario with no `gui.expected.json` baseline for
  the sweep to key on. Its walkthrough is now refreshed and attributed. This also
  corrects the range quoted in the CU-321 entry below: the measured SNR movement
  across shipped scenario configurations spans **−14.9 % (1.1) to +15.2 % (1.6)**,
  not the "−11 % to +11 %" recorded there. No library code changed with this entry;
  the numbers on `main` are unchanged by it.
- **Results-affecting: the downwelling flux-diffusivity exponent is now geometric,
  not fitted (CU-324 item 1, owner-ratified 2026-08-29).** `E_sky_thermal` used the
  CU-155 fitted `D = 1.1`; it now uses `sec 48.2° = 1.50030`, the secant of the
  diffusivity angle every up-looking MODTRAN deck in its reference set was run at.
  **Direction and magnitude:** the sky's effective emissivity rises everywhere —
  `E_sky_thermal` increases by up to `sec/1.1 = 1.364×` where the sky column is
  optically thin, tapering to no change where it already saturates. Every
  reflected-sky term rises with it, so scenes with a reflective target or background
  under sky gain signal; purely emissive targets and every directional path-radiance
  product are untouched (they never used this exponent). Measured band-integrated
  `E_sky_thermal` rises +20–28 % (LWIR) and +19–23 % (MWIR) on the H2/H4 columns.
  Downstream: the MWIR LEO golden moves `signal_e` +0.32 % and `snr` +0.16 %; ten
  scenario GUI baselines and nine scenario walkthroughs move, the largest being
  1.1 (`snr` 980.55 → 1001.47, +2.1 %). Scenario 4.1's detection matrix moves both
  ways because its criterion is a signed contrast: sub-background targets (ε 0.30–0.35
  at 295 K) lose range as the reflected sky brightens. Parity against the nine-rung
  measured downwelling ladder improves: RMS |ln(model/MODTRAN)| 2.0776 → 1.9233 over
  9 rungs × 2 bands, and 0.4167 → 0.3087 over the tropospheric rungs alone. The
  retired value had been fitted against two ground-rooted decks six weeks before that
  ladder existed.

### Added
- **Per-element coating detail view (Gap 116).** Selecting a row in the Optics
  Elements tab now draws that element's R/T/ε on the coating's **native source
  grid** (full stored extent, not the run band), one autoscaled panel per
  quantity, with the evaluation band shaded — percent-level coating dispersion
  that the fixed-[0,1] all-element overlay flattens is now inspectable, and a
  draft row previews before Apply. New public API:
  `radiant.api.plot_coating_detail(sensor, name, *, entries=None)` and the
  `plot_element_coating` renderer in `radiant.api.plot`. No computed result
  changes.
- **Scenario 9.4 — Landsat 9 OLI-2** (`scenarios/09_flagship_missions/9.4_landsat_oli2_snr/`):
  first scenario to exercise the full per-element optical prescription (Mode 5) —
  four protected-silver mirrors, AR window, and per-band interference filters, all
  **synthetic coating curves** (generator: `scripts/gen_oli2_coatings.py`) — and the
  first flagship use of an ADR-0010 configuration set (all eight 30 m bands as one
  study via a shared composite butcher-block filter element; pan standalone, Gap 103).
  Nine-band SNR @ L_typ anchored to the published OLI requirement tables
  (`docs/validation/landsat_oli2_source_data.md`; offline-compiled, verification pass
  logged). No library code changed; no existing result moves.

### Fixed
- **Matrix cards use the full Performance pane again (CU-333).** The CU-332
  frozen-label rework exposed a latent layout bug: the empty second card-grid
  column took half the pane in study sessions, clipping the value area to one
  configuration column. Column stretches are now mode-dependent.
- **Scrolling a wide Performance matrix no longer loses the metric labels
  (CU-332).** Each group card now freezes the metric-label column and scrolls
  only the configuration columns beside it (row heights synchronized, all
  cards' scrollbars linked); an 8-configuration study previously showed bare
  numbers once scrolled.
- **The configuration selector no longer pushes the stage strip off-screen
  (CU-334).** Qt laid the two top bands out side by side, so an 8-configuration
  study clipped stages 4–9 at laptop widths; the bar now stacks in its own thin
  band above the strip, as the GUI architecture doc always specified.
- **Point-source scenes no longer grey out the surface-radiance (ε, T) inputs
  that drive them (CU-329).** `source.target.temperature_K`/`emissivity` now
  carry `regime:point_source`: the surface-radiance door is a documented legal
  point-source specification (intensity = L·A_proj), and the GUI was disabling
  the exact parameters producing the on-screen emission curve.
- **All-Parameters regime exclusion reads as a dimmed row + tooltip, not a
  value-cell suffix.** The old `(n/a: <scene>)` text inside the Value column
  blew the content-sized column open and starved the parameter names (the
  truncation regression the owner hit on scenario 10.1).

### Changed
- **All-Parameters panel polish (2026-08-03 critique P1s).** Values render
  mono and right-aligned (digits line up like a calibrated column);
  provenance renders as the §8.4 pill for changed/derived rows with "default"
  receding; a **Changed only** toggle beside the filter shows just the
  user-set/config rows — the deviation from default is the configuration.
- **Results-affecting (GUI sweeps only): the Sweep dialog swept unit-converted
  parameters at the wrong magnitude (CU-325).** The dialog pre-converted typed
  ranges to canonical units, but `Sensor.sweep` interprets values in the
  *input* unit — a pixel-pitch sweep typed in µm ran values 10⁶ smaller (or
  failed the bounds check). Typed values now pass through untouched; scripted
  and API sweeps were never affected.
- **"Copy as script" now emits a complete, runnable, reproducing block
  (CU-325).** The old 2-D emission referenced an undefined variable
  (`NameError` on paste) and the 1-D block carried a "convert if needed"
  caveat; both axes are now constructed with the exact typed endpoints.
- **Esc/Close during a running sweep no longer orphans the worker thread
  (CU-325)** — the dialog cancels, reports honestly, and closes on settle.

### Changed
- **Sweep dialog usability (CU-325/CU-326).** Ranges seed around the session's
  current value (clamped to schema bounds) with the current value shown beside
  the unit; the last-run spec persists across openings; log spacing is
  per-axis; ranges validate against schema bounds before launch; plot axes
  render in the entry units, unit-suffixed; the 2-D heatmap uses `pcolormesh`
  (correct cells for log-spaced axes); metrics list under display names; the
  Run button carries the accent; the idle progress bar is hidden.

### Added
- **`midlat_summer_sst_column_fan_site900m` — the SST full column from a 900 m
  elevated site** (MODTRAN rows M9–M13, delivered 2026-08-03). Five nodes,
  lower endpoint 0.9 km → 100 km atmosphere top, LOS zenith 0–78.5°
  (sec 1–5). Shipped as a **sibling** of `midlat_summer_sst_column_fan` rather
  than a sensor-altitude axis on it: the 0 m fan is unchanged, byte for byte.
  Like the 0 m fan it is `explicit_dir_only` — `path_zenith_rad` is the schema
  default for `atmosphere.interpolation_axes` and the signature is already
  claimed — so it is adopted by name, through
  `atmosphere.interpolated_data_dir`, never by default dispatch. Elevation is
  worth a lot: band-mean 8–12 µm τ of the full column is 0.702 from 900 m
  against 0.583 from sea level at nadir, and 0.302 against 0.137 at sec 5.
  With it, **27 of the 38 shipped GUI scenarios now switch to
  `atmosphere.model = "interpolated"` and evaluate first try** (was 26);
  scenario 10.3, the 900 m mountaintop SST scene, is the one that moved, which
  completes the CU-322 acceptance criterion. The remaining 11 still produce
  exactly one advisory. No existing scenario changed families.
- **Two further measured rungs on `midlat_summer_uplooking_sensor_ladder`** —
  60 km and 80 km (MODTRAN P7/P8), so the observer-altitude axis is measured to
  80 km instead of interpolating the whole 50 → 100 km span in one step.
- **Global display-unit preference — angles in degrees (CU-326, owner-ruled).**
  Parameters whose schema unit is `rad` now display, seed their editors, and
  interpret typed values in **degrees** everywhere (parameter tree, stage
  forms, editor dialogs); `mrad`/`µrad` parameters keep their schema units.
  Per-row unit overrides still win; a persisted View → *Angles in Degrees*
  toggle restores schema units. Display-only — canonical storage and the API
  are unchanged (Rule 2).

### Changed
- **One metric, one unit, everywhere (CU-326).** The Performance cards now
  route through the same display scaling as the pinned badges (NEDT reads
  25 mK on both, not 0.025 K on one and 25 mK on the other), and metrics
  whose magnitude would render in scientific notation get an automatic
  engineering prefix (a 2.13e−05 m FWHM reads 21.3 µm). ASCII exponent units
  render typeset across the GUI: `m2` → `m²`, `um` → `µm`, `urad` → `µrad`.
- **The Run button now carries the staleness trust signal (CU-327).** When results
  predate the last edit — or the last run failed — the right-rail Evaluate button
  flips to the warn fill and reads "Re-evaluate  F5", clearing on the next clean
  run. This implements the behavior arch doc §8.4 had documented since Phase 1.

### Changed
- **All-Parameters panel columns no longer truncate parameter names (CU-328).**
  Value and Source columns are content-sized (previously fixed 104/72 px) and
  names elide in the middle, so the discriminating suffix always survives — the
  eight `target.shape.*` rows no longer render identically.
- **GUI accessibility pass (2026-08-03 critique):** Messages rows are keyboard-
  focusable and activate on Return/Space with severity spelled out for screen
  readers, and their text reads in ink (warn-on-warn-soft failed WCAG AA);
  rail count subtitles moved up one contrast step; metric-card pin affordances
  keep a reserved slot (no value jitter on hover) and reveal on keyboard focus;
  "+ Pin…" is disabled with an explanatory tooltip until a result exists;
  picker-added pins show the metric's display label instead of its raw key;
  the unpin glyph is ✕ (was the edit-pencil ✎); unpin/+Pin hovers no longer
  borrow the accent (One Loud Element).
- **Token-derived house style for all `result.plot.*` figures (owner ruling
  2026-08-03, reversing the "figures are not restyled" stance).** New module
  `radiant.api.plot_style`: theme surfaces/fonts/grid/spines mirroring
  `gui/themes/tokens.py` (equality test-enforced) plus a **CVD-validated**
  categorical series palette (fixed order blue → amber → teal → terracotta →
  purple → green; adjacent-pair colour-blind separation gated by test). Applied
  **API-wide** — scripts, notebooks, saved PNGs, and the GUI render identically;
  `plot_theme(dark=…)` now styles both variants (`dark=False` is no longer a
  no-op). Figure titles are left-located (`ax.get_title(loc="left")`).
- **`plot_noise_budget(scale="log"|"linear")`** — the noise budget bar is
  log-scale by default so every term is legible across decades, with mono
  value labels in e⁻ RMS, the dominant term accented, sub-floor (≤ 0.05 e⁻ RMS)
  terms named in a caption, and the RSS total; `scale="linear"` restores the
  proportional view.
- **`plot_sweep` full-well saturation shading** — when a sweep retained
  per-point results, the value span whose points ran with a clipped well
  (`well_status() == "clipped"`, Gap 65) is shaded in the warn tint and
  labelled, so a flat-top metric curve reads as clipping, not physics. Sweep
  axes now carry the swept parameter's schema unit and analyst-facing metric
  names (`snr` → `SNR`).

### Changed
- **Results-affecting: the 60 km and 80 km `atm_emission_down` rungs are now
  measured, not modelled** (MODTRAN P7/P8, delivered 2026-08-03). They were a
  log-linear extrapolation on the measured 29 → 50 km slope, clamped
  non-increasing; the measurement shows that slope badly under-predicted the
  collapse above 50 km. The shipped values **fall**: 3–5 µm band mean by
  **10.6×** at 60 km and **8 791×** at 80 km; 8–12 µm by 4.9× and 349×.
  Direction: downwelling at high-altitude targets decreases. Ten NPZ nodes
  moved (`midlat_summer_boost_ladder` targets 60/80 km and
  `midlat_summer_boost_offnadir` target 80 km, at both sensor rungs); the other
  136 shipped nodes are SHA-256 identical, so **every rung at or below 50 km,
  and every ground-target node, is unchanged**. Per the CU-181 carve-out this
  is observable only in a **reflective elevated-target** scene above 50 km —
  none of which ships — because for a self-emitting body the reflected-sky term
  is bounded at ≲ 1e−3 of its own radiance. Zero golden-baseline movement.
  The only band still extrapolated is an off-node query strictly between 80 km
  and the 100 km atmosphere top, bracketed by a measured value below and the
  exact-zero identity above; no shipped family holds a node there.
- **`plot_atmosphere_spectral` renders as two stacked, x-sharing panels**
  (τ_atm above, L_path below, direct-labelled) instead of twin y-axes on one
  plot — two unrelated scales overlaid invite reading meaningless crossings.
- **`plot_mtf_terms` collapses ≈-unity contributors to a caption** (min ≥ 0.995
  across the band; all drawn if every term is at unity), direct-labels sparse
  overlays (≤ 4 curves), and draws the Nyquist marker in the ink tone with an
  in-plot annotation instead of a red dashed line.
- **GUI Detector Noise tab primary chart is `noise_budget()`** (log-scale bar)
  in place of the retired pie.

### Deprecated
- **`plot_noise_pie` / `result.plot.noise_pie()`** — emits `DeprecationWarning`
  (owner ruling 2026-08-03): a variance-share pie collapses everything but the
  dominant term into invisible slivers. Use `noise_budget()` (log default).

- **`Sensor.atmosphere_family_suggestion()` — the pre-validated interpolated-family
  recommendation (CU-322).** Returns an `AtmosphereFamilySuggestion` (`family`, `gap`,
  `considered`, `los_direction`, `vacuum_path`, plus `serves` / `advisory_text` /
  `advisory_error()`), which walks the bundled catalogue and returns the first family
  whose **complete** query the chain would accept — direction, axes, LOS zenith, target
  ceiling (including the up-looking exo guard) and the family's own rendered lower
  endpoint. When nothing serves the scene it carries one structured `FamilyGap` naming
  the closest miss with units, instead of leaving the caller to collect one refusal per
  gate. Companion additions: `Sensor.atmosphere_family_gap(family)` (the same check for
  one named family) and `radiant.api.is_atmosphere_coverage_refusal(exc)` (whether an
  error is an atmosphere-coverage refusal rather than a rejected parameter — structural,
  never message text). New module `radiant.atmosphere.family_suitability`; new
  `ShippedFamily.pending_runs` field naming authored-but-unrun MODTRAN rows that would
  widen a family (today: the SST column fan's M9–M13 elevated-site decks).
- **Four new shipped atmosphere families from the MODTRAN batch-2 delivery
  (run-matrix rows M1–Q8, delivered 2026-08-02).** Three up-looking:
  `midlat_summer_uplooking_zenith_fan` (ground observer, targets 0–20 km × LOS
  zenith 0°/48.2°/60°, i.e. a uniform sec ζ = 1.0/1.4999/2.0 ladder — axes
  `target_altitude_m,path_zenith_rad`), `midlat_summer_uplooking_sensor_ladder`
  (an *elevated* observer's full column to the 100 km atmosphere top, observer
  0–50 km at the 48.2° diffusivity angle — axes `sensor_altitude_m`), and
  `midlat_summer_sst_column_fan` (ground observer's full column at sec ζ = 1…5,
  the space-surveillance anchor; reachable only through an explicit
  `atmosphere.interpolated_data_dir`, because its axes string is the schema
  default and publishing it would silently widen an existing refusal). One
  down-looking: `midlat_summer_upwelling_offnadir` (ground target, sensor
  10 km / 100 km / 40 000 km × LOS zenith 0°/48.2°/60° — axes
  `sensor_altitude_m,path_zenith_rad`). **No existing result moves**: every new
  family takes a `(direction, axes)` key no shipped family had, so the loader's
  existing dispatch is untouched.
- **Off-vertical up-looking interpolated queries are served, not refused
  (GF-10).** An up-looking family that carries a `path_zenith_rad` axis now
  interpolates the zenith in airmass sec(ζ) space, exactly as the down-looking
  fans do (CU-160). The refusal is narrowed rather than removed: an up-looking
  family with no zenith axis still raises for any zenith other than the one it
  was rendered at, and the message now names the new fans as the remedy
  alongside `atmosphere.model = "simple"`. The near-horizon rungs M6–M8
  (85°/88°/89.5°) were run but are deliberately **not** shipped — past the 88.8°
  airmass ceiling the sec-space mapping is unvalidated.
- **The interpolated atmosphere library is picked from a list, not typed as a key
  (CU-239).** The Atmosphere screen's *Interpolated run matrix* group leads with a family
  picker built from `radiant.api.shipped_atmosphere_families()`: one row per bundled
  family with its rendered profile and a plain-language coverage line in operator units
  (km, degrees). Choosing a row writes `atmosphere.interpolation_axes` — and
  `atmosphere.interpolated_data_dir` where the family needs one — as derived values, in a
  single undo step. The family the resolved scene calls for is marked *(recommended for
  this scene)* and, when what is configured cannot serve the scene, pre-selected as a
  **proposal** that an explicit *Use this family* click applies: choosing a family can
  change the atmosphere profile, so it is never written behind the operator's back, and
  the profile-change caveat shows beside the row whenever it would. *Custom axes…
  (advanced)* keeps the old free-text field for a run matrix outside the catalogue.
  **`midlat_summer_boost_ladder` is now reachable**: its 24 committed MODTRAN runs
  (nadir, targets 0–100 km) share the 2-axis ladders' `(direction, axes)` key, so no axes
  string could ever select them; the picker offers the family by name and writes its
  bundled directory. **No computed result moves** — the loader's default-family dispatch,
  and therefore every existing 2-axis result, is untouched; this adds a way to reach data
  that already shipped.
- **`Sensor.suggested_atmosphere_family()` and
  `Sensor.atmosphere_profile_change_warning(family)` (CU-239).** The first derives the
  bundled family a scene calls for from the sensor's own resolved geometry (a
  recommendation — it writes nothing); the second renders the sentence to show when
  adopting a family would change an explicitly-set `atmosphere.standard_atmosphere`.
  `shipped_atmosphere_families()` now also lists families reachable only through an
  explicit directory, each carrying `explicit_dir_only` and `bundled_dir`.
- **The atmosphere coverage check now fires on edit, not only at Evaluate (CU-239).** A
  scene/axes mismatch appears in the GUI Messages rail — with the exact axes string to
  set — the moment the offending parameter is edited, and clears again when the config is
  fixed, instead of arriving ~1 s later as a failed evaluation.

- **`geometry.site_elevation_m` has a GUI entry point (CU-301).** The Geometry screen's
  Inputs tab gains a site-elevation card below the input-mode forms. The parameter is a
  standalone scene fact rather than an input-mode door, so the manifest-driven forms
  deliberately do not render it (schema tag `non_mode`) — which left a results-affecting
  turbulence parameter (CU-262: the Hufnagel-Valley Cn² surface term is evaluated at
  `h − site_elevation_m`, so an elevated site keeps its own boundary layer) reachable only
  from YAML or the scripting API. The card is the same shared `FieldRow` +
  `ParameterEditorDialog` as every other field: the value displays and is entered in the
  row's chosen unit (enter 2.5 km, the model stores 2500 m, the row reads 2.5 km back),
  each accepted edit is one validated `sensor.set` that marks results stale, and a
  rejected value never touches the live sensor. **No computed result moves** — this adds a
  way to reach an existing parameter, not a new parameter or a new default.

- **`optics.pupil_npix` and `optics.psf_oversample` — the PSF/MTF FFT grid is now
  tuneable (CU-288).** Formerly hardcoded (128 / 8) in `optics/stage.py`, and the
  dominant cost of every chain evaluation (~3.1 s of a 4.2 s five-evaluate GUI profile).
  Both parameters are read once per evaluation and threaded to the target PSF, the
  Strehl reference PSF, and the MTF product path, so both Rule-4 spatial paths always
  share one grid. Defaults unchanged — **no computed result moves** (set-vs-default
  identity pinned by test). Bounds (32–512) × (4–16): every corner measured within the
  2e-2 dual-path consistency tolerance (worst 0.0075); `psf_oversample` floors at 4
  because ≤ 3 aliases the FFT-of-PSF path at the grid edge (measured 0.032).

- **`geometry.site_elevation_m` now warns when it cannot reach the selected Cn² profile
  (CU-302).** The parameter feeds only the Hufnagel-Valley surface term (CU-262); with
  `atmosphere.cn2_profile = "tabulated"` (the table carries its own site) or `"direct"`
  (no profile at all) a non-zero elevation changes nothing, and until now it did so in
  silence. A `UserWarning` from `atmosphere.cn2_profiles.warn_if_site_elevation_inert`
  now names the elevation, why that profile cannot use it, and the two ways forward.
  **No computed result moves** — measured on a 2635 m site with a ground→space vertical
  path at the 4 µm band centre: r₀ is 0.601494 m with `tabulated` and 0.100000 m with
  `direct` both before and after (delta 0.000e+00 m in each), while the `hufnagel_valley`
  control moves 2.557716 m → 0.663070 m as CU-262 intends. A sea-level (default 0 m)
  elevation never warns. **What to watch:** a batch runner with `-W error` and a config
  that sets both will now stop; either switch to `hufnagel_valley` or leave the elevation
  at 0 and let the table's own altitudes describe the site.
- **Results-affecting (up-looking interpolated scenes only): the shipped up-looking
  MODTRAN library is now reachable from a chain run (CU-226).**
  `atmosphere.model = "interpolated"` with an up-looking scene and
  `atmosphere.interpolation_axes = "target_altitude_m"` previously loaded
  `midlat_summer_uplooking_ladder/` and then raised a capability error at
  `AtmosphereStage`; it now composes a result. The observer leg (sensor → target)
  comes from the MODTRAN-derived run family; the target's illumination and the sky
  radiance along the LOS continuation come from a `SimpleAtmosphere` companion the
  loader attaches to the family, because an up-looking run family carries neither
  leg. The split is declared, never silent: a `UserWarning` names both models and
  `result.inspect()` →
  `stage_outputs["atmosphere"]["topology_provenance"]["backend_split"]` records
  which leg came from which. **No existing result moves** — nothing else reaches
  this path, and every golden and GUI baseline is bit-identical. For a ground
  sensor looking straight up at a 10 km target in the shipped MWIR example, the
  observer leg's band-mean (3–5 µm) transmittance goes from 0.5715 [-] (simple) to
  0.4725 [-] (library, −17.3 %) and its band-mean path radiance from 0.3995 to
  0.5414 W/m²/sr/µm (+35.5 %), moving SNR from 1207.2 [-] to 1152.7 [-] (−4.5 %).
  New public surface:
  `radiant.atmosphere.uplooking_quantities.UplookingColumnBackend` (structural
  protocol) and the keyword-only `InterpolatedAtmosphere(uplooking_companion=...)`
  with its `uplooking_companion` property. A **level** path on an up-looking family
  is refused with an actionable error rather than approximated.
- **`geometry.site_elevation_m` — an elevated site keeps its own turbulence boundary
  layer (CU-262).** New public parameter [m, default 0 = mean sea level]: the terrain
  elevation beneath the line of sight. The Hufnagel-Valley $C_n^2$ **surface term** is
  now evaluated at `h − site_elevation_m` while the jet-stream and free-atmosphere terms
  stay on MSL, so a site above sea level no longer starts above its own 100 m-scale-height
  boundary layer. Whose terrain it is follows the LOS topology (down-looking = the
  target's, up-looking = the sensor's, level = the arm's own) and is *not* derived from
  the lowest point of the line of sight — a level air-to-air leg therefore carries no
  surface term, because the 100 m scale height suppresses it, not because of a special
  case. An altitude below the declared site is refused with a `ParameterBoundsError`
  instead of being modelled as a path through the ground. Consumed only by
  `atmosphere.cn2_profile = "hufnagel_valley"`; a `"tabulated"` profile already carries
  its own site and is not shifted.
  **Results-affecting only when `geometry.site_elevation_m` is set non-zero** — at the
  default 0 the profile, the domain check, and every provenance string are bit-identical,
  and no golden or GUI baseline moves. Where it is set, turbulence gets *stronger*: the
  HV-5/7 vertical anchor at a 900 m site goes from $r_0$ = 15.0 cm (0.67″ seeing at
  0.5 µm) to 5.22 cm (1.94″), restoring the model's defining $r_0 = 5$ cm to within the
  +4 % the free-atmosphere column below the site genuinely buys. Before this fix
  `atmosphere.cn2_hv_ground_strength` was inert at an elevated site (a 10 000× change in
  $A$ moved the seeing at a 2635 m site by 0.0 %); it now behaves as documented.
- **Interpolated-atmosphere coverage is checked at config time, and the shipped-family
  catalogue is public (CU-239).** New `Sensor.validate_atmosphere_coverage()` and
  `radiant.api.atmosphere_families` (`shipped_atmosphere_families`,
  `shipped_family_for_axes`, `suggested_interpolation_axes`, `ShippedFamily`).
  `atmosphere.model = "interpolated"` with a scene the configured
  `atmosphere.interpolation_axes` cannot serve — the common case being an above-ground
  `geometry.target_altitude_m` against the `"path_zenith_rad"` schema default — now raises
  **pre-chain**, from `build_atmosphere_model`, instead of five stages later inside
  `InterpolatedAtmosphere.evaluate`. The refusal names the exact axes string to set, the
  shipped family it selects with its coverage in km and degrees, and a profile-change
  caveat when that family's rendered atmosphere profile differs from an explicitly-set
  `atmosphere.standard_atmosphere`. Not breaking: every configuration that evaluated
  successfully before still does, and every configuration that failed still fails — the
  same `AtmosphereCapabilityError` type, raised earlier with a longer, actionable message.
  No computed results change. Evaluate-time checks remain as defence in depth.
- **`Sensor.validate_target_spec()` — resolve-time target-spec over-specification check
  (CU-244).** Runs the source inferrer's `source.target.*` mutual-exclusivity guards
  (reflectance/albedo aliases, ρ vs (ε, T), ρ vs the S8/S10 radiance/intensity paths,
  ρ vs S11/S12 brightness/radiance temperature, S11 vs S12) without physics, file I/O,
  or a resolved config, raising the same actionable `ParameterBoundsError` — identical
  what/why/action text — that `evaluate()` produces. The GUI's clone-validate edit
  discipline (parameter tree and Parameter Editor dialog) now calls it on every commit,
  so a conflicting pair such as `source.target.reflectance` + `reflectance_path` is
  rejected at the door instead of surviving until Evaluate; a conflict that pre-exists
  on the live sensor still surfaces at Evaluate and never blocks unrelated edits.
  Evaluate-time checks are unchanged (defence in depth); no computed results change.

### Changed
- **Results-affecting: atmospheric path thermal emission is now emitted at a
  height-resolved, spectrally resolved temperature `T_eff(λ)` (CU-321).** The Kirchhoff
  term `(1 − τ)·B` that CU-224 added to the down-looking side, and that the up-looking
  segment evaluators have always carried, used **one** temperature per segment — the
  profile temperature at its lower endpoint. A tall column is not isothermal, and it is
  not isothermal in a *spectrally structured* way: an opaque channel emits from wherever
  its own optical depth reaches unity as seen by the observer, a transparent one from the
  whole column weighted by absorber density. `atmosphere/emission_temperature.py` now
  supplies the temperature that makes the one-slab form reproduce the layered formal
  solution of the segment's own air, evaluated once per escape end. **Every τ in the model
  is bit-identical** — only the altitude the emission is weighted at changes — and an
  isothermal (level) segment returns its own temperature exactly, so level arms are
  unaffected. No new parameter: the pressure-broadening scale heights are derived
  (`α ∝ ρ_absorber·p_air`, so the well-mixed floor emits on 4 km against its 8 km density
  profile and water on 1.6 km against its 2 km) and the sub-layer count is a
  convergence-tested quadrature.

  **Direction and magnitude.** Down-looking MWIR path thermal **drops** on tall columns,
  which is what this fixes: band-mean model/MODTRAN parity against the batch-2 O-block
  goes 2.01/2.25/2.42× → **1.14/1.22/1.22×** (O3/O4/O5) and LWIR 1.33/1.35/1.43× →
  **1.06/1.06/1.09×**. Up-looking path thermal drops too — LWIR walks onto unity
  (K5 1.230 → 1.033, H5 1.263 → 1.074, H1 1.530 → 1.189) while MWIR falls further *below*
  it (K5 0.878 → 0.586, H5 1.041 → 0.721). Over the 25-run anchor set the RMS |ln ratio|
  is LWIR 0.330 → **0.269** (−19 %) and MWIR 0.474 → **0.522** (+10 %). The MWIR cost is
  un-masking, not new error: scored against MODTRAN's own recovered emission temperature
  the model was up to 25 K too warm and is now within 11 K everywhere (RMS 9.5/10.4 K →
  4.3/3.2 K), and with MODTRAN's own emissivity substituted the radiance RMS |ln ratio|
  improves 0.287 → 0.148. The retired warm bias had been partly cancelling the CU-161
  region-flat spectral-shape deficit in the up-looking direction; that deficit is now
  visible rather than hidden, and it is the named remaining limitation.

  **What moves in shipped configs.** Every `atmosphere.model = "simple"` scene with a
  thermal path-radiance contribution. MWIR LEO golden: `signal_e` −13.2 %, SNR −6.8 %
  (1204.28 → 1122.18). Option-C Cell 28 (2 km LWIR): NEDT −0.007 %, at-aperture radiance
  −1.0 % to −6.4 % across 8–13 µm. Chain-spatial SNR pin 1178.65 → 1094.62 (−7.1 %).
  Nineteen scenario GUI baselines move, between −11 % and +11 % in SNR (down-looking
  scenes lose path signal; the up-looking 10.1 detection scene *gains* SNR 130.1 → 144.6
  because its background falls). Level-path and exo scenes are unaffected.
  *(Corrected 2026-08-29 by the CU-334 bisect — see the CU-334 entry at the top of
  `[Unreleased]`. The measured span across shipped scenario configurations is
  −14.9 % to +15.2 %, and a twentieth scene moved: 1.6, +15.2 % SNR, which had no
  GUI baseline and so was missed by this PR's refresh sweep.)*
- **`evaluate()` now refuses every over-specified `source.target.emissivity_path` pair, as
  the seam already did (CU-323).** The ε(λ) door dispatches last, so nine of its ten rival
  surfaces — `source.target.reflectance`, `albedo`, `reflectance_path`, `albedo_path`,
  `brightness_temperature_K`, `brightness_temperature_path`, `radiance_temperature_K`,
  `user_radiance_path`, `user_intensity_path` — opened a door that built the target first
  and the user's ε(λ) CSV was **silently discarded** (Rule 17), while
  `Sensor.validate_target_spec()` refused the same pairs. Extending the CU-293 ruling
  class, `target_spec.check_emissivity_path_conflicts` is now a **pre-dispatch** check run
  first at both entry points instead of a per-door guard registered last: all ten pairs
  raise `ParameterBoundsError` at `evaluate()` with text identical to the seam's. Remedy
  for anyone hitting the new refusal: set either `emissivity_path` or the rival surface,
  not both — the error names the pair. No computed result moves (refusal-only, and the
  guard is a no-op unless `emissivity_path` is user-set and non-empty); none of the 67
  shipped YAML configs sets that surface, so none newly raises.
- **`Sensor.validate_target_spec()` now refuses an over-specified `source.target.emissivity_path`
  spec at the resolve-time seam (CU-318).** The ε(λ) door was the last one whose exclusivity
  guard was inlined in the source inferrer, so it ran only at `evaluate()`. It moved verbatim to
  `radiant.source.target_spec.check_emissivity_path_conflicts` and is registered last in
  `validate_target_spec` — the position the door occupies in dispatch order. Behaviour change at
  the seam: `emissivity_path` paired with scalar `source.target.emissivity`, a ρ-family surface,
  S8, S10, S11 or S12 now raises `ParameterBoundsError` at resolve time (and so at the GUI
  parameter editor's clone-validate commit), where it previously passed. Evaluate-time refusals
  are unchanged apart from the CU-295 module prefix now opening the message
  (`"source.target_spec: …"`). No computed result moves — refusal-only; all 67 shipped YAML
  configs still pass the seam.
- **`Sensor.suggested_atmosphere_family()` never recommends a family the chain would
  refuse (CU-322).** Same signature, pre-validated answer. It now (a) derives the LOS
  zenith from the resolved line of sight rather than reading `geometry.path_zenith_rad`
  — the two differ on a spherical scene, and a family rendered at one fixed zenith is
  refused on exactly that difference; (b) can return an `explicit_dir_only` family,
  which no axes string reaches; and (c) returns `None`, with a reason available from
  `atmosphere_family_suggestion()`, where it used to name a family that then refused.
  Measured over the 38 shipped GUI scenarios: 26 now switch to `atmosphere.model =
  'interpolated'` and evaluate first try (was 25 — scenario 10.1 was recommended the
  vertical-only up-looking ladder at ζ = 29.9°, which the zenith fan covers), and the
  remaining 12 produce exactly one advisory naming the missing coverage. **No computed
  result moves** — the recommendation writes nothing, and every scenario that already
  had a working family keeps it.
- **GUI: an atmosphere coverage refusal is an advisory, not a "Parameter Rejected"
  modal (CU-322).** `RADIANTMainWindow` routes any refusal
  `is_atmosphere_coverage_refusal()` recognises to the Messages rail and the status bar
  with no modal; the modal stays for inputs the framework genuinely rejected. The
  family picker pre-selects the pre-validated recommendation (including explicit-dir
  families, by name), says on the highlighted row when it cannot serve the scene, and
  proposes a replacement when the *configured* family cannot — which the axes-only
  coverage check could not detect. When no bundled family serves the scene, the
  Messages rail carries one gap advisory in place of the axes-coverage refusal.
- **Results-affecting: the shipped atmosphere library's `atm_emission_down` is
  altitude-resolved (CU-181).** A down-looking node's downwelling sky radiance is
  now the measured value at *that node's target altitude*, interpolated from the
  H5 (ground) + P1–P6 (1/5/10/20/29/50 km) MODTRAN rung ladder, instead of the
  single ground-level H5 value the library attached to every node. **Direction
  and magnitude:** elevated-target nodes fall — by 1.4× at a 1 km target rising
  to 142× at 50 km (3–5 µm band mean; 1.7× to 442× at 8–12 µm) — and the 100 km
  atmosphere-top rung becomes exactly zero (an observer there has no sky above
  it). Ground-target nodes are **byte-identical**, so `midlat_summer_sensor_ladder`,
  `us_standard_zenith_fan`, `profiles/`, and every ladder's 0 km target rung do
  not move; no golden baseline changes. The exposure this closes is the reflected
  sky term on a cold, low-emissivity body at altitude, where CU-181 measured the
  old constant at up to +2 567 % apparent radiance. Nodes above 50 km remain
  modelled (log-linear on the 29→50 km slope, clamped non-increasing) rather than
  measured. **CU-181's ≳10⁴ acceptance criterion is not met and should not be**:
  MODTRAN's real decay over 0→50 km is 142×/442×, one-to-two orders less than the
  entry's analytic table, which had been computed from `SimpleAtmosphere`'s own
  `E_sky_thermal` rather than from an independent reference.
- **Results-affecting (up-looking / level sky at ζ > 0 only): one curve-of-growth
  linearisation convention across all three path evaluators (CU-320).** `segment_simple`
  linearised the CU-161 water curve of growth and the well-mixed-gas floor against the
  **vertical** column while `segment_grazing` and `level_whole_path` used the **slant** one.
  Because `OD_h2o = k·w^b` is sub-linear, the two differ by `m_h2o^(b−1)` in the effective
  water weight and therefore in ω₀ wherever water absorbs — which was the whole of the
  surviving 80° hand-over step. `segment_simple` now uses the slant column, the amount the
  path actually traverses, and `column_segment_optical_depth` publishes `slant_column_*_km`
  provenance under the same key names the near-horizon branch already used.
  **Direction and magnitude:** the 80° grazing/column hand-over step falls from 1.078 (VIS),
  1.568 (NIR), 1.497 (SWIR), 1.024 (MWIR), 0.998 (LWIR) to 0.995/0.995/0.992/0.998/0.998 —
  within 0.8 % and, more usefully, the same size in every band. Up-looking scattered sky moves
  at any ζ > 0 (e.g. band-mean model/MODTRAN at ζ = 60° against the new M2 run: VIS
  0.734 → 0.762, NIR 0.993 → 1.226, SWIR 1.447 → 1.778, MWIR 1.221 → 1.254, LWIR unchanged);
  at ζ = 0 the air mass is exactly 1 and the result is bit-identical, so the K-ladder
  species-split anchors and every shipped baseline are unmoved. **This is a consistency fix,
  not an accuracy one** — against the M-block the overall RMS |ln ratio| is 0.316 → 0.318, a
  wash: VIS and NIR improve, SWIR and MWIR degrade slightly, and what is left is the
  single-scatter source's own limits (§3.1).
- **A ground-to-space up-looking scene now runs against a full-column interpolated run family,
  and is refused against a partial-column one (CU-224 checklist / ex-CU-308).** The exo branch
  of `uplooking_quantities._illumination_products` substitutes the exact vacuum identity
  (`τ_sun ≡ 1`, `E_sky ≡ 0`) when the target sits at or above `h_atm_top`; with a
  library-backed observer leg, whether that identity may be *composed* with the MODTRAN leg
  depends on how far up the backing family actually measured, and the family now answers that
  itself through the new `InterpolatedAtmosphere.uplooking_target_ceiling_m`.
  **New capability:** a family whose ceiling reaches `h_atm_top` integrated the entire column,
  so the remaining path to an exo target is vacuum and the composed observer leg is
  *identically* that family's own top-of-column run. `InterpolatedAtmosphere` serves such a
  target from the ceiling node — the target-axis mirror of the sensor-axis vacuum equivalence
  it already shipped for the ladders' 40,000 km node — and records it in the segment
  provenance under `exo_target_vacuum_clamp`. This makes `midlat_summer_sst_column_fan` and
  `midlat_summer_uplooking_sensor_ladder` reachable for the ground-to-space scenes they were
  built for; every such scene previously raised.
  **New refusal:** a family whose ceiling stops inside the atmosphere (the 20 km
  `midlat_summer_uplooking_ladder` and `midlat_summer_uplooking_zenith_fan`) raises an
  actionable `ParameterBoundsError` naming its measured ceiling and the full-column families
  that do serve the scene, instead of the family's own out-of-hull error. The clamp is gated
  at `h_atm_top` and nowhere else — a 50 km target through a 20 km ladder still fails the hull
  check, unchanged.
  **No existing computed result moves:** every endo-target scene, every down-looking scene and
  `atmosphere.model='simple'` are untouched; the two affected cases previously raised rather
  than returning a number.
- **Results-affecting: down-looking path radiance now carries the atmosphere's own thermal
  emission (CU-224).** `SimpleAtmosphere.evaluate`'s `L_path_up` and `L_path_full` were
  single-scatter **solar only**, so a pure-thermal LWIR down-looking scene had
  `L_path_up ≡ 0` exactly while the up-looking segment evaluators carried the Kirchhoff
  term `(1 − τ)·B(λ, T_eff)` — one column of air read in the two directions differed by
  three to four orders of magnitude. Both products now add that same term, reusing
  `atmosphere/segment_thermal.py` and the CU-155 emission-height helper at each column's
  **lower** endpoint (`h_tgt` for the target leg, the ground for the full column); nothing
  new is fitted and no transmittance moves (τ stays bit-identical — the term is additive on
  radiance alone). Upwelling MWIR/LWIR path radiance is emission-dominated, not
  scatter-dominated, so this is a first-order correction, not a refinement.
  **Anchored** against the batch-2 O-block upwelling MODTRAN runs (O1–O5, each the
  direction partner of an already-delivered up-looking run on the identical column):
  band-mean model/MODTRAN thermal path radiance moves from 2e-3…3e-8 to **0.42–2.42**
  (MWIR 3–5 µm) and **0.53–1.43** (LWIR 8–12 µm) — the same band the up-looking side
  already occupies on those columns, so the residual is the shared CU-155/CU-161
  spectral-shape and one-temperature-graybody approximation, not a direction-specific
  defect. The up/down thermal asymmetry drops from 2e2…4e7 to 1.00–1.44 against MODTRAN's
  measured 1.006–2.34.
  **Direction and magnitude:** every down-looking MWIR/LWIR result **increases**, by more
  the longer and warmer the column. MWIR LEO golden `signal_e` +53.5 %, `snr` +23.9 %
  (971.93 → 1204.28); Option-C Cell 28 (2 km LWIR) `L_aperture` +20 % to +171 % across
  8–13 µm and NEDT +0.63 %; the 17 shipped GUI baselines that moved run from +0.08 %
  (1.3, a cold high-altitude MWIR band) to +59.2 % SNR (8.2), with NEDT falling
  correspondingly (−0.008 % to −38.4 %). Scenes with no atmosphere between target and
  sensor (exo, vacuum, `h_tgt → h_sensor`) are unchanged: `τ → 1` makes the term exactly
  zero.
- **Results-affecting: the level-topology sky background is evaluated as one whole traversed
  path (CU-224 checklist / ex-CU-276, owner ruling 2026-08-01).** The level branch of
  `uplooking_quantities` composed the sky as `L_arm→sensor + τ_arm · L_continuation`, joined
  at the target plane, because nothing could evaluate "constant-altitude arm then ascending
  arc" as one segment. New module `atmosphere/level_whole_path.py` does: it integrates the
  real traversed path — descending half-chord, ascending half-chord, ascending continuation
  — about the chord's true perigee `r_p = √(r_arm² − (L/2)²)`, per species. That removes the
  target-plane join *and* the level arm's constant-density approximation from the sky path.
  A zero-length arm now reduces exactly to `segment_grazing.evaluate_grazing_segment` at
  ζ = π/2, so the level and ascending sky topologies join with no step.
  **Direction and magnitude:** the level sky **increases**. Thermal bands move ≤ 0.6 %
  (they saturate toward `B(T_eff)`); a **daytime VIS/NIR** level sky moves **1.13× to 2.43×**,
  because the retired form multiplied the continuation's scattered term by `τ_arm` and
  weighted the two halves separately. **Affected scenes:** level topology on
  `atmosphere.model = "simple"` (an up-looking *interpolated* scene refuses a level path
  outright).
  - **One shipped baseline moves: scenario 10.2** (air-to-air level IRST, MWIR night, where
    the thermal bands saturate): `snr` 282.8023208926127 → 282.80224590038495,
    `detection_range_m` 197 900.031129053 m → 197 899.51752931994 m (−0.51 m, −2.6e-6
    relative). Its `.gui.expected.json` and walkthrough numbers are refreshed in this PR.
  - `level_arm.py` is **not** superseded (Rule 27): it still computes the observer leg — the
    τ that attenuates the target and the `L_path` that adds to it — which is a different
    path between different endpoints.
  - Correction to the filed defect: the level join did **not** carry a CU-254-sized
    temperature non-additivity. Both composed sub-segments were keyed to the same altitude
    and therefore the same `T_eff` (measured 227.850 K either side of the join on 10.2), so
    the mechanism CU-276 named was absent; what the fix removes is the constant-density arm
    and the split-weighted scattering.

- **Results-affecting: the down-looking and solar columns hand over to the exact spherical
  slant integral past 80° zenith (CU-224 checklist / ex-CU-275, owner ruling 2026-08-01).**
  `SimpleAtmosphere.evaluate`'s observer column (`tau_up`, `tau_full_up`), its solar column
  (`tau_sun`), and `segment_simple.column_segment_optical_depth` used `sec ζ` over their whole
  legal domain. Near the horizon the plane-parallel answer diverges: `sec ζ` over-states the
  air mass by **3.8 % at 80°, 13 % at 85° and 237 % at 89.4°**, and over-states it
  *differently per species* (water vapour and molecular air are 2.3× apart in error at
  89.4°). All three now take the same 80° hand-over the up-looking sky has had since
  CU-225/CU-274, through the new `atmosphere/near_horizon_air_mass.py`, with a **per-species**
  effective air mass. **Direction and magnitude:** transmittance and SNR move **up** past 80°
  and never down — median τ rises 10.6 % on a ground → 100 km column at the switch itself,
  and by a factor of ~3 in optical depth at 89.4°. **Affected scenes:** any scene past 80°
  LOS zenith or 80° solar zenith on `atmosphere.model = "simple"`. **No shipped golden or
  scenario baseline moves** — nothing that ships exceeds 37.5° LOS or 40° solar zenith, and
  at or below 80° the optical depth is bit-for-bit what it was.
  - The solar column's 89.5° clamp is **retired**: the plane-parallel construction had to
    clamp θ_s at `ZENITH_CEILING_RAD`, which is exactly where `sec ζ` is most wrong, so a
    twilight scene at θ_s = 89.9° now gets its own column instead of the 89.5° one.
    `ZENITH_CEILING_RAD` still bounds `path_zenith_rad`; the observer domain is unchanged.
  - **Removed:** the module-level alias `radiant.atmosphere.simple.ZENITH_CEILING_RAD_SIMPLE`,
    which existed only to serve that clamp. Import `ZENITH_CEILING_RAD` from
    `radiant.atmosphere.protocol` instead.
  - The near-horizon transmittance is **not yet MODTRAN-anchored** at those angles (the
    twilight/refraction calibration pair is a batch-2 deck) and refraction remains unmodelled,
    so past ~85° this is a better-conditioned model, not a validated one.

- **Results-affecting: the single-scatter sky's species split is weighted at the segment's
  lower endpoint, not at its arithmetic-mean altitude (CU-224 checklist / ex-CU-260, owner
  ruling 2026-08-01).** `segment_simple.py` sets the ω₀ and P(Θ) species proportions of every column
  segment — the up-looking **observer leg** and the up-looking / level **sky background**
  alike — at the column's lower endpoint, which is what
  `segment_grazing.py` and `level_arm.py` already did — the three evaluators now weight
  alike. The retired mean-altitude form put the weights above the altitude where the
  aerosol and water coefficients underflow for any column taller than ≈ 40 km, so ω₀
  became exactly 1 and the Henyey-Greenstein forward peak collapsed onto the
  isotropic-Rayleigh 1.5: a tall column scattered as if `visibility_km` had never been set.
  **Direction and magnitude:** the daytime VIS/NIR/SWIR sky **increases**, by up to 2.3×
  on a ground-rooted 0–20 km column (band-mean MODTRAN/model at that rung goes 3.085× →
  1.342× VIS, 3.024× → 1.262× NIR, 8.712× → 1.666× SWIR at the worst rung); MWIR moves ≤ 20 %,
  LWIR ≤ 4e-4 (thermal-dominated, inert to the choice). **Affected scenes:** up-looking and
  level scenes on `atmosphere.model = "simple"` with the sun above the local horizon and a
  grid below 3 µm. **No shipped golden or scenario baseline moves** — every shipped
  up/level scene is either night (10.1, 10.2) or has the sun below the horizon (10.3).
  Anchored against the shipped `midlat_summer_uplooking_ladder` MODTRAN family;
  the anchors are frozen in `tests/integration/test_species_split_anchors.py`.

- **BREAKING — a brightness-temperature + radiance-temperature pair now raises at
  `evaluate()` (CU-293, owner ruling 2026-08-01).** Setting both
  `source.target.brightness_temperature_K` (or `_path`) **and**
  `source.target.radiance_temperature_K` used to evaluate cleanly: the S11 door
  dispatches first and had no S12 guard, so the radiance temperature the user supplied
  was **silently discarded** and the run reported results for the brightness temperature
  alone (Rule 17). S11 and S12 are parallel user-entry forms for the same thermal
  target, so the pair is an over-specification and now raises an actionable
  `ParameterBoundsError` naming both surfaces — same ruling class as CU-256/CU-264.
  **Remedy: unset one surface** — keep `brightness_temperature_*` for a λ-resolved
  `T_B(λ)`, or `radiance_temperature_K` + its band edges for a scalar band-averaged
  `T_R`. `Sensor.validate_target_spec()` already refused this pair, so the change is to
  `evaluate()` only, and the two now raise the identical message. Sweep: **no shipped
  scenario or example sets either surface**, so nothing in the repo changes behaviour.
  No computed result moves for any config that keeps running.
- **The S8, S10 and S10b door-exclusivity guards now also run at the resolve-time seam
  (CU-293, ex-CU-294).** `source.target.user_radiance_path` + (ε, T), `user_radiance_path`
  + `user_intensity_path`, the two point-intensity modes
  (`point_intensity_temperature_K` + `point_intensity_band_W_per_sr`) together, and
  `user_intensity_path` / `point_intensity_*` + (ε, T) were rejected only at `evaluate()`
  because their guards were inlined in the inferrer; they moved to
  `radiant.source.target_spec` (`check_user_radiance_conflicts`,
  `check_point_intensity_conflicts`, `check_user_intensity_conflicts`) and are registered
  in `Sensor.validate_target_spec()`. **Remedy is unchanged** — unset one of the paired
  surfaces — but a GUI edit that introduces one of these pairs is now rejected at commit
  time rather than accepted and failed at Evaluate. Their `what=` prefix follows the
  CU-295 convention (`"source.target_spec: "`). No computed result moves.
- **Results-affecting: the simple atmosphere's calibrated gas-region table is no longer
  read as a step function — region coefficients are blended across each edge (CU-267).**
  `_CALIBRATED_GAS_REGIONS` is piecewise-constant in `(floor_od, k_h2o, b_h2o)`, so
  `SimpleAtmosphere` used to step τ(λ) discontinuously at all fourteen interior region
  edges (measured −90 % at 2.40 µm, +821 % relative at 8.00 µm), which made a band-mean τ
  that straddled an edge depend on how finely the band was sampled — 1.83 % between 31 and
  1001 sample points on 3.0–5.0 µm, exactly 0 for bands crossing no edge. The three
  coefficients are now joined across each edge by a C¹ smoothstep ramp of half-width
  0.02 µm (full width 0.04 µm), so τ(λ) is continuous with continuous slope and the grid
  dependence at the edge is gone.
  **Direction and magnitude:** band-mean τ_up moves **down** on every shipped band that
  straddles an edge, by ≤ 0.71 % — −0.20 % (0.5–0.8 µm), −0.12 % (0.4–0.9), −0.71 %
  (3.0–5.0), −0.27 % (8–12), −0.21 % (8–14), −0.19 % (11.5–12.5) — and by **exactly zero**
  on bands that cross no edge (3.7–4.8 and 10.6–11.2 µm are bit-identical). Region
  interiors are untouched by construction: only λ within 0.02 µm of an edge sees a
  different coefficient. Downstream, the 34 shipped scenario GUI baselines move on 26 of
  them by ≤ 1.04 % (largest: scenario 10.1 SNR −1.03 %, NEDT +0.98 %); the MWIR LEO minimal
  golden moves signal_e −1.22 %, SNR −0.61 %. A **single wavelength sitting exactly on an
  edge** can move much further (Cell-28 L_aperture at 8.0 µm −54.9 %, at 12.0 µm +16.4 %),
  because the pre-blend value there was the arbitrary one-sided pick — the half-open
  region mask handed each edge wholly to its upper region — and is now the two regions'
  mean. Only `atmosphere.model = "simple"` is affected (and the CU-226 hybrid's simple
  companion legs); tabulated/MODTRAN-derived atmospheres carry their own τ.

- **BREAKING — `SpectralData.plot()` returns the `Figure`, not the `Axes`, and builds it
  unregistered (CU-286).** `radiant.core.spectral.SpectralData.plot(ax=None)` used to do
  `_, ax = plt.subplots()` and hand back only the `Axes`, so the figure it created was a
  process-global pyplot resource reachable only via `plt.gcf()` and releasable only via
  `plt.close("all")` — 1 retained figure per call. It now builds a plain
  `Figure(layout="constrained")` (the CU-116 convention every `radiant.api.plot` helper
  already follows) and returns it; `plt.get_fignums()` is unchanged by the call. Passing
  your own `ax` returns that Axes' own figure, untouched. **What stops working:** code
  doing `ax = sd.plot(); ax.set_ylim(...)` — use `fig.axes[0]`, or pass the `ax` you
  already have. Not results-affecting: no computed number is involved.
- **A plot call no longer switches the host process's matplotlib backend (CU-287).**
  `radiant.api.plot` forced `matplotlib.use("Agg")` on **every** entry, so the first
  `result.plot.*` call silently switched an embedder's backend — a Jupyter session
  running `%matplotlib qt`, or any process that had chosen its own. Agg is now forced
  only when *nothing* has been selected yet, which preserves the headless guarantee
  exactly (a bare script or CI runner still lands on Agg) while leaving a chosen
  backend alone. Figures are pyplot-free either way (CU-116), so nothing about how they
  render, save, or embed changes.
- **BREAKING — a declared target extent is refused at the point-source intensity door
  (CU-256).** Setting any S10/S10b intensity surface (`source.target.user_intensity_path`,
  `source.target.point_intensity_temperature_K`, `source.target.point_intensity_band_W_per_sr`)
  together with a declared extent (`geometry.target.projected_area_m2` or
  `geometry.target.shape`, including the deprecated `source.target.*` aliases) now raises
  `ParameterBoundsError` naming which surface to drop. **What stops working:** configs that
  supplied both and ran anyway — the extent was silently discarded, because T7 publishes a
  fictitious reference area `A_fict` and therefore an `angular_extent_rad` sentinel of
  ~1e-11 rad, which disarmed the matrix §7 point-source validity guard (a 500 m² target at
  25 km, ≈20 pixels across, evaluated as a point source). The refusal fires at the door,
  before the sentinels are published, and also at config time via
  `Sensor.validate_target_spec()`. `source.target.point_intensity_area_m2` is unaffected —
  it belongs to the intensity door and scales `I(λ) = ε·A·B(λ,T)`. **Not results-affecting:**
  the declared extent never influenced any computed number, so configs that drop the
  redundant parameter reproduce their previous results exactly (verified on scenario 10.2:
  29/29 metrics identical). One shipped scenario needed the follow-up edit —
  `scenarios/10_direction_general/10.2_air_to_air_level_irst` (both its `.gui.yaml` and its
  run script) declared `geometry.target.projected_area_m2` alongside the T7 blackbody door.
  ADR-0004's `A_fict` algebra is unchanged.
- **BREAKING — a `sub_pixel` declaration below 1% of PSF_FWHM now raises instead of warning
  (CU-264).** `OpticsStage._validate_psf_regime_consistency` raised `ParameterBoundsError`
  for a declared `point_source` above `0.1·PSF_FWHM` but only emitted a `UserWarning` for a
  declared `sub_pixel` below `0.01·PSF_FWHM`. Both now raise. **What stops working:** configs
  declaring `source.scene_type='sub_pixel'` for a target whose angular extent is under 1% of
  the system PSF FWHM. Those runs previously continued with the regime promoted to
  `point_source` — which changes the applied EE_box handling — under a warning batch runners
  routinely suppress (Rule 17). No shipped scenario, example, or golden baseline is in that
  band (swept 2026-07-30: every shipped `sub_pixel` config sits three or more orders of
  magnitude above the threshold). No computed results change.
- **Plot-card readability at GUI card sizes: colorbars, titles, and the noise pie's labels
  (CU-241).** Presentation-only — no computed value changes. `plot_pupil_amplitude` and
  `plot_pupil_phase` now size their colorbar as `plot_psf` already did
  (`fraction=0.046, pad=0.04`), so the bar shrinks with the aspect-locked map instead of
  spanning the figure height at ~15 % of its width. Axes titles longer than 34 characters
  soft-wrap (`plot_psf`, both pupil maps, `plot_noise_pie`), because matplotlib clips an
  over-long title at both canvas edges rather than shrinking it — measured 4 px of
  clipping on `psf_pixel_grid`'s title and 10 px on the pie's at the sizes the GUI renders
  them. `plot_noise_pie` moves its legend from the axes' right edge to below the pie and
  draws on-wedge labels *inside* the wedge (`labeldistance` 0.62, translucent label box),
  which stops a wide label running off the card. Callers matching a full title string need
  to normalise newlines; label text and legend content are unchanged.
- **`result.plot.*` / `radiant.api.plot` figures are no longer registered with `pyplot`
  (CU-116).** Every helper now builds a plain `matplotlib.figure.Figure(layout=
  "constrained")` instead of `plt.subplots(constrained_layout=True)`. Returned figures
  are identical to render, save (`fig.savefig(...)`), embed, and theme
  (`plot_theme(dark=True)` still applies — rcParams are read at construction), but they
  do not appear in `plt.get_fignums()`, are never `plt.gcf()`, and need no `plt.close()`
  — a figure is freed when its last reference drops. Scripts that relied on the implicit
  "current figure" (`result.plot.mtf()` followed by a bare `plt.savefig(...)`) must use
  the returned figure instead; `plt.show()` was already a no-op because the helpers force
  the non-interactive Agg backend. This ends the GUI holding one process-global figure per
  visited stage (22 figures after all nine stages), which tripped matplotlib's 20-figure
  `max_open_warning`.
- **`TopologyProducts.sky_source_radiance` is now `sky_radiance_at_aperture`, and the
  `SkyBackground` assembly arm is a pass-through (CU-254).** The keyword argument on
  `assemble_background_at_aperture()` and `assemble_background_source_emission()` is
  renamed to match. The quantity changed meaning, not just name: it used to be the sky
  at the *target* plane, which assembly re-propagated as `L_sky·τ_full_up + L_path_full`;
  it is now the whole line of sight evaluated from the *sensor*, so it is already the
  at-aperture background and that arm applies no transport at all. Code that passed the
  old keyword raises `TypeError`; code that read the old field raises `AttributeError`.

### Removed
- **`radiant.source.resolve_direct_intensity` deleted (CU-299).** The legacy Path-4
  resolver deprecated under [ADR-0004](docs/adr/0004-t7-intensity-at-source.md) is gone,
  together with its module `radiant/source/resolvers/intensity.py` and both package
  re-exports (`radiant.source`, `radiant.source.resolvers`). It has emitted a
  `DeprecationWarning` since ADR-0004 and returned a `ResolvedTarget`, which the Option-C
  chain does not consume, so nothing in the chain could reach it. **Migration:** build the
  descriptor instead —
  `radiant.source.converters.user_intensity.user_intensity_to_descriptor(...)`, or set
  `source.target.user_intensity_path` (S10) / `source.target.point_intensity_*` (S10b) in
  YAML. **No computed result moves**: no in-tree caller remained, and the only test that
  exercised it tested the deprecated function itself.

### Fixed
- **Results-affecting: `alias_fraction_at_nyquist` reports 0 for oversampled
  configurations instead of float noise (CU-315).** The fraction
  `(folded − optical)/folded` was evaluated wherever the folded MTF was merely
  non-zero, so for optics that cut off below Nyquist it divided ~1e-16 by ~1e-16 and
  returned an arbitrary number — the dual-band example's two LWIR configurations
  (Q = 2.22) printed **0.944314, now 0.0**. The ratio is now evaluated only where the
  folded MTF exceeds `folded_mtf.ALIAS_FRACTION_MTF_FLOOR` = 1e-9 of the DC response
  `MTF(0) = 1`; below that floor (at any frequency, not just Nyquist) the reported
  fraction is exactly zero, which is the physical answer — an oversampled design
  aliases nothing. Undersampled values are untouched bit-for-bit: the same example's
  MWIR configuration stays at 0.500004 and scenario 3.4's nadir case at 0.5000. This
  closes the caveat the CU-209 entry below left open. No golden baseline, snapshot, or
  `*.gui.expected.json` carries the key, so no baseline was re-reviewed.
- **Results-affecting (tabulated- and MODTRAN-served τ on a chain grid that differs from
  the file's): the log-τ resample convention is now universal across all three
  file-backed backends (CU-316).** CU-306 moved `InterpolatedAtmosphere`'s wavelength
  resample into ln(τ) space — the Beer-Lambert space, where optical depth, not τ, is what
  varies smoothly — but left `TabulatedAtmosphere` and `ModtranAtmosphere` resampling
  linearly in τ, so *the same stored MODTRAN column returned different numbers depending
  on which backend served it*: up to ~1.5 % relative τ on a 200-point MWIR chain grid,
  landing exactly at the magnitude of the physics differences a fast-path-vs-tabulated
  comparison exists to expose. All five τ-resample sites in those two backends
  (`TabulatedAtmosphere.build_state` / `.evaluate`; `ModtranAtmosphere`'s primary column,
  up-leg `τ_up`, and sun-leg `τ_sun`) now go through the shared
  `radiant.atmosphere.log_tau_resample.resample_transmittance`, with the same
  `TAU_FLOOR` = 1e-30 guard (opaque bands resample to the floor, never to −inf). **τ moves
  down** — the geometric mean is ≤ the arithmetic mean — by ≤ ~1.5 % relative at low-τ
  wavelengths on realistic grids, and the cross-backend divergence is eliminated (three
  backends now agree to float round-off on one stored column). Radiances (`L_path`,
  `L_atm_down`) deliberately stay linear: additive emission terms with no exponential
  path-length law. A query on the file's own grid is a bit-identical no-op.
- **Results-affecting (every point-source `detection_range_m`): the detection criterion
  is shot-noise-consistent, and the down-looking arm is path-aware (CU-263, folding
  ex-CU-236).** Two coupled changes in one owner-gated PR:
  1. All three solvers held the **total** noise at its reference-range value while
     scaling the signal outward, so the reported range depended on the range the chain
     happened to be evaluated at — 123.4 km referenced at 25 km against 182.5 km at
     100 km for one unchanged air-to-air configuration (1.48×). The target's own shot
     variance in electrons *is* the signal, so it falls as the target dims. The
     criterion is now `S(R)/√(S(R) + N₀²) = threshold` with `N₀² = σ_ref² − S_ref` the
     target-free floor (new `performance/detection_noise_floor.py` and
     `performance/detection_shot_consistent_snr.py`, which also owns the closed form
     `S* = ½(T² + √(T⁴ + 4T²N₀²))` — in vacuum the answer is `R_ref√(S_ref/S*)` with no
     root finding). Both forms agree exactly at the reference range, so the correction
     is zero there, grows outward, **always lengthens** the range, and vanishes for a
     background-limited chain.
  2. The `down` topology now goes through `performance/detection_path_aware.py` like
     `up` and `level` (ex-CU-236): extinction past the reference range is resolved along
     the actual ray instead of extrapolated from one constant `α = −ln τ̄ / R_ref`, which
     over-attenuates a receding sensor whose extra path is in thinner air and then
     vacuum. `performance/path_optical_depth.py` measures ranges from the ray's **lower
     endpoint** — the target when looking down, the sensor when looking up.

  **Direction and magnitude — detection ranges lengthen everywhere, most for bright
  targets referenced close in.** Measured on shipped scenarios: 10.4 LEO→GEO vacuum
  **78 138.9 → 90 015.3 km (+15.20 %)**; 10.2 air-to-air level arm at its 50 km
  reference **150.949 → 198.815 km (+31.71 %)**, and the 25 km-to-100 km spread across
  that sweep collapses from 1.48× to **1.00×**; 1.6 MWIR SDA (down-looking, both changes)
  **1 198.9 → 1 522.1 km (+26.96 %)**. Scenario 4.1's matrix does **not** move — it
  bisects a script-side SCNR in the sub-pixel regime and never enters a solver (verified
  by tripwire over all 144 cells).

  **What to watch:** (a) a down-looking scene whose **sensor is inside the atmosphere**
  (`h_sensor < h_atm_top` with `τ̄ < 1`) now emits **no** `detection_range_m` — the
  continuation runs through altitude-varying extinction the metric layer cannot
  integrate, so it is a named `failure_reason` on `detection_range_result` rather than a
  constant-α guess (Rule 17; the same refusal up-looking scenes have had since GF-15).
  Spaceborne down-looking sensors are unaffected — they sit above `h_atm_top`, so the
  receding leg is exact vacuum. (b) `detection_range_beer_lambert` and
  `detection_range_path_aware` now require the signal and total noise to come from the
  **same** evaluation: `σ_ref² < S_ref` has no target-free floor and returns a named
  failure instead of a number. (c) `detection_range_generic`'s signature changed — it
  takes a **signal**-vs-range callable plus `noise_floor_e` in place of an
  SNR-vs-range callable, so no caller can reintroduce a frozen-noise SNR.

- **Results-affecting (interpolated atmosphere on a non-matching chain grid): τ is now
  resampled onto the chain's wavelength grid in log-τ, not linearly in τ (CU-306).**
  `InterpolatedAtmosphere.build_state` interpolated the run family in log-τ (correct —
  Beer-Lambert makes optical depth the quantity linear in path length) and then resampled
  the result onto the chain grid linearly in τ. The two operations do not commute, so the
  answer depended on their order. Both are now linear in ln(τ). Measured on the shipped
  `midlat_summer_ladders` family, target-altitude midpoint at 35 km sensor: the analytic
  log-τ midpoint identity on an off-node grid collapses from **2.077e-02 absolute /
  1.36e-01 relative (τ > 0.1)** to **1.110e-16 / 5.47e-16** — machine precision, matching
  what the stored grid always gave. On realistic 200-point band grids τ moves by up to
  **1.3 % (LWIR 8–12 µm), 1.5 % (MWIR 3–5 µm, τ > 0.01), 0.5 % (VIS 0.4–0.9 µm)**;
  **direction: τ decreases** at every point (the log-space result is the geometric rather
  than arithmetic mean of the bracketing samples, and GM ≤ AM), so SNR through an
  interpolated atmosphere edges down. Deep absorption bands move by more in relative terms
  (τ ~ 1e-9 → 1e-20) but are radiometrically zero either way. **A query on the stored grid
  is bit-identical** — no resample happens, so nothing changes for it — and `L_path` /
  `L_atm_down` are bit-identical everywhere: they are additive emission terms with no
  Beer-Lambert exponential in path length, so their resample deliberately stays linear.
  Opaque bands are unaffected: the constructor's existing `TAU_FLOOR` (1e-30 ≡ OD ≈ 69)
  clamp keeps ln(τ) finite, so a τ = 0 band resamples to the floor, never to NaN or −inf.
- **Results-affecting: the folded (aliased) MTF now replicates at the sampling frequency
  `f_s = 2·f_Nyquist`, not at `f_Nyquist` (CU-209).** `compute_folded_mtf` shifted the
  aliasing replicas by `k·f_Nyquist`, so at `f = f_Nyquist` the `k = −1` copy landed on DC
  and added `MTF(0) = 1` to every system, sampled or not. **`mtf_folded_at_nyquist` and
  `alias_fraction_at_nyquist` therefore drop for every scenario**, with two distinct
  magnitudes: an *oversampled* design (optics cut off below Nyquist) goes from ≈ 1 to ≈ 0 —
  the dual-band example's LWIR configuration (Q = 2.22) reads 0.995689 → 9.72747e-16
  (−100 %); an *undersampled* design loses the spurious unit DC term and settles at twice
  the pre-sampling MTF at Nyquist — the same example's MWIR configuration (Q = 0.944) reads
  1.52851 → 0.533365 (−65 %, = 2 × 0.266683) with the alias fraction 0.825528 → 0.500004,
  and scenario 3.4's nadir case 1.4475 → 0.4544 with alias fraction 0.8430 → 0.5000.
  Values above 1.0, which the old form produced routinely, are now the exception rather
  than the rule. No golden baseline, snapshot, or `*.gui.expected.json` carries either key,
  so no baseline was re-reviewed. **Caveat, unchanged by this fix:** for an oversampled
  band `alias_fraction_at_nyquist` divides ~1e-16 by ~1e-16 and reports meaningless float
  noise (0.944 in the LWIR case) — read the absolute folded value there; whether the alias
  fraction needs an absolute floor is deliberately left open.

- **Results-affecting (up-looking scenes): the sky background no longer depends on where
  along the ray the target sits (CU-254).** The per-segment single-effective-temperature
  graybody is not additive, so splitting the sky column at the target plane traded part
  of a warm ground-anchored emitter for a cold target-anchored one. On the shipped
  scenario 10.1, varying only `geometry.target_altitude_m` at fixed pointing, the
  background ran 1.94207e5 e⁻ (10 km target) → 2.14046e5 (20 km) → 2.21479e5 (whole
  column); all three are now 2.21479e5. **Direction: up, by up to ~14 % for
  low-altitude targets** (SCNR was correspondingly optimistic). Target signal is
  unchanged. **Level scenes are bit-identical** — a level ray is tangent at the chord
  midpoint, so its sky keeps the two-segment composition (a sensor-rooted arc would drop
  up to 25 % of the traversed column) and therefore keeps the residual dependence,
  tracked as CU-276. Down-looking scenes are untouched.
- **Results-affecting (up-looking/level near-horizon): the sky hands over to the exact
  spherical slant integral at 80° instead of 89.5° (CU-225).** The plane-parallel column
  form was carried 9.5° past the point where its air mass stops being `sec ζ`. The
  hand-over discontinuity in band-mean LWIR sky radiance drops from ≈ 8 % (≈ 28 % on the
  3 km level arm originally measured) to **0.64 %**, and the whole 80–89.5° band is now
  served by the exact integral rather than by an air mass that was 14–62 % low there.
  Scenes below 80° zenith are unaffected.
- **Results-affecting (near-horizon, >80° only): the "spherical-Earth correction" branch
  of `AtmosphericGeometry.slant_path_length_m` is removed (CU-274).** It computed the
  geometric chord of a 100 km slab rather than a density-weighted air mass, and made the
  air mass *drop* 18 % across its own switch (5.7023 at 79.9° → 4.8072 at 80.1°) — so
  transmittance was discontinuous in look angle for every scene class, down-looking
  included. `L_slant = Δh_absorbing / cos ζ` now covers the whole legal domain, so the
  model is continuous and monotone in ζ. **Nothing at or below 80° moves** (it was
  already `sec ζ`), and no shipped scenario exceeds 37.5° LOS zenith or 40° solar zenith.
  Past 80° the near-horizon air mass is now overestimated (+13 % at 85°, +237 % at 89.4°
  against the exact integral) rather than underestimated — pessimistic SNR rather than
  optimistic — for the callers that have no grazing route; tracked as CU-275.
- **The provisional VIS/NIR sky warning now reaches the ground-to-space and air-to-space
  classes (CU-260, partial).** The ADR-0011 decision-10 `UserWarning` lives on the path
  through `sky_radiance_along_los`, which an exo-altitude target short-circuited before
  it was ever called — so exactly the daytime SST scenes the band gating exists for ran
  silently. Rooting the sky at the sensor removes the short-circuit, and the near-horizon
  branch now emits the warning explicitly (`warn_if_scattered_sky_provisional` is public
  for that purpose). The species-split half of CU-260 is unfixed and remains open.

### Fixed
- **A rejected Parameter-Editor Apply no longer writes a tolerance (CU-219).** The
  single-value path committed the tolerance before the value, so when the value write
  failed a Monte-Carlo spread was left behind for a value that never landed. Both
  Apply paths now validate everything first and then commit in the same order (value,
  then tolerance).

### Fixed
- **Results-affecting (up-looking only): air mass is evaluated on the atmospheric
  slab, not the endpoint separation (CU-255).** For a path ending above the
  atmosphere — a ground site viewing a 700 km target — the slant-path formula was
  handed a 700 km "slab", a hundred times the real column. The result saturated, so
  optical depth *fell* as the ray tilted away from vertical: τ(0.55 µm) went 0.0137
  at 79.9° to 0.0980 at 80.1°, a physically impossible air mass. Both branches now
  clamp at the column top, and `air_mass` normalises by the same thickness so it can
  no longer report below 1 for an exo target. **Paths that end inside the atmosphere
  are bit-identical** (air mass at 0/30/60° is still exactly sec θ), so no
  down-looking or in-column scene moves.

### Changed
- **Spectral Integration screen shows only what it computes (CU-242, owner-directed).**
  The `Qe scalar` input echo is gone, `Nearfield` / `Stray` rows hide when their path
  is not configured rather than displaying `0 e-`, every remaining row explains via
  tooltip why the value is computed at this stage (Rule 8), and the in-band radiance
  plot is removed — it was the input to the integration, not its product, and the
  Atmosphere view owns radiance. The at-image irradiance plot stays.
- **PSF kernel cards name the stage that applied them (CU-243).** The Platform "PSF
  degradation" tab enumerates the *accumulated* kernel stack, so Optics' pixel-aperture
  kernel appeared under Platform with no owner — correct data reading as a wrong-stage
  bug. Each card is now titled `<kernel> · added by <Stage>`, and the empty state says
  what was inherited, from where, and why nothing was added here.
- **`eta_rad` is labelled "Look angle at sensor" (CU-246).** "Nadir (off-nadir) angle"
  is wrong for an up-looking scene, where η is measured from the sensor's zenith.

### Fixed
- **A configured filesystem-path parameter keeps its Browse… picker (CU-220).**
  Configuring a `*_path` / `*_file` / `*_dir` parameter moved editing to the
  per-configuration rows, which had no picker — so making a path per-configuration
  silently downgraded it to hand-typed. Every configuration row now has one.

### Changed
- **`radiant run --provenance` now writes one schema (CU-218).** A plain config
  previously produced a three-key record (`radiant_version`, `resolved_at`,
  `parameters`) while a `--configuration` run produced the full run record, so a
  consumer of the single flag had to detect which shape it received. Both paths now
  write the run record — `run_id`, `radiant_version`, `git_commit`, `parameter_set`,
  … — plus a `configuration` key naming the configuration, or `null` for a plain run.
  **Scripts reading the old `parameters` key should read `parameter_set`.**

### Changed
- **`geometry.sensor_off_nadir_rad` renamed to `geometry.sensor_off_boresight_rad`
  (CU-247).** Since ADR-0011 the reference axis is resolved from the altitudes — the
  sensor's nadir when it is above the target, its zenith when below — so the old name
  contradicted its own description and invited the wrong-hemisphere entry the
  agreement checks exist to catch. The old dot-path remains as a **deprecated alias**
  that warns and redirects, so existing YAML configs and scripts keep working
  unchanged.
- **Metric `diffraction_limit_ground_m` renamed to
  `diffraction_limit_target_plane_m` (CU-231).** The value is `angular × slant_range`
  with no incidence projection and no ground-plane assumption — correct for every LOS
  direction, including up-looking scenes where the `gsd_*` family is (correctly)
  absent, which is where the old name read as an inconsistency. **Both keys are
  published with the identical value**; the old one is registered as deprecated. No
  computed value changes.

### Fixed
- **A ground-based sensor keeps its ground-referenced metrics (CU-232).** GSD and the
  diffraction limit treated `geometry.sensor_altitude_m <= 0` as "geometry not
  available", but the schema defines 0 as a legal ground-based sensor, so those scenes
  silently lost `gsd_*` for a reason unrelated to what they asked. Only a negative
  altitude is now skipped.

### Added
- **`atmosphere.r0_reference_wavelength_um` — declare what wavelength your seeing
  value is quoted at (CU-228).** Fried's parameter goes as λ^(6/5), so the
  astronomer's habitual 10 cm at 500 nm is 1.30 m at a 4.25 µm band centre; entering
  the habitual number and running an MWIR scene made the turbulence MTF roughly an
  order of magnitude too aggressive, silently. Set the new parameter and `r0_m` is
  rescaled to the band centre, with both values recorded in the resolution
  provenance. **The default (unset) preserves existing behaviour bit-identically** —
  no scene moves unless it opts in. A `UserWarning` fires when `r0_m` is set, the
  reference is unset, and the band centre is more than a factor of two from 0.5 µm.

### Fixed
- **Results-affecting: the T7 intensity door had no sky (CU-258).** Solar geometry
  was stripped for every descriptor except T2/T3, so an intensity-door scene received
  a purely thermal sky (~1e-18 W/m²/sr/µm in the VIS). Every daytime intensity-door
  scene was therefore missing the sky pedestal — for a visible measurement, its
  dominant noise term. VIS/NIR intensity-door noise and SNR change accordingly;
  thermal-band scenes are unaffected.
- **An eclipsed intensity-door target no longer reports full signal silently
  (CU-259).** The door consumes I(λ) verbatim, so τ_sun — which carries the eclipse
  verdict — never scaled the target term: an object in the Earth's shadow returned
  the same signal with no indication. RADIANT cannot tell reflected sunlight from
  self-emission given I(λ) alone (that is the illumination-aware door of Gap 114), so
  it now computes the number and warns plainly about what the number omits, only when
  the scene declares a sun *and* the target is eclipsed. No computed value changes.
- **A wholly-vacuum path with a sky-terminated background no longer raises
  (CU-261).** The vacuum topology published "no sky" where the correct answer is a
  sky of exactly zero radiance; assembly's refusal to invent a missing sky is
  unchanged.
- **A set optics temperature that does nothing now says so (CU-265).** In scalar
  transmission mode the optics emit ε·B(T) with ε defaulting to 0, so an uncooled
  293 K telescope evaluated bit-identically to an 80 K one while the user believed
  warm-optics emission was modelled. Warns when the temperature is explicitly set and
  the emissivity leaves it inert, naming both ways to make it live.

### Changed
- **PSF plots read in focal-plane micrometres, not sample indices (CU-241).**
  `result.plot.psf()` and `psf_pixel_grid()` previously labelled their axes in raw
  PSF sample numbers (e.g. 500–560 on a 1024 grid), so the reader could not tell how
  large the blur was without converting through the sample spacing — while the title
  quoted the detector pitch in µm. Both axes are now µm on the focal plane, measured
  from the PSF core, and the pixel outline and pixel-boundary gridlines share the
  same transform. A degenerate grid (no usable sample spacing) still falls back to
  sample axes rather than inventing a physical scale. The colorbar is also sized so
  it no longer takes a third of a narrow card, and a plot column placed beside an
  embedded panel now has a minimum readable width so the panel cannot squeeze the
  figures into an unreadable strip.

### Fixed
- **Scenario 4.3's GUI baseline reloads in a clean checkout again (CU-273).** The
  CU-253 baseline regeneration rewrote its `user_radiance_path` from the committed
  `inputs/` copy to a gitignored `outputs/derived/` path, so the baseline failed to
  load anywhere the scenario had not just been run. The generator defect that caused
  it is tracked as CU-273.

### Fixed
- **Results-affecting: the simple atmosphere's molecular (Rayleigh) optical depth was
  ~8× too large in VIS/NIR (CU-253).** `0.0088·λ⁻⁴·⁰⁹` is the published **total
  vertical** Rayleigh optical depth (dimensionless — 0.1015 at 550 nm, matching the
  0.0973–0.10 of Hansen & Travis 1974 / Bucholtz 1995), but it was named
  `RAYLEIGH_COEFF_KM` and consumed as a km⁻¹ volume extinction, so multiplying it by
  the ~8 km molecular column inflated every molecular optical depth by exactly the
  column depth. The sea-level coefficient is now *derived* from the published optical
  depth through the exponential profile's own identity τ_vert = σ₀·H_mol, so the two
  cannot drift apart again.

  **Direction and magnitude.** Molecular optical depth falls 8.00× at every
  wavelength. Band transmittance rises steeply in the blue and negligibly in the
  thermal bands: τ_mol for a full vertical column goes 0.13 → 0.78 at 440 nm,
  0.44 → 0.90 at 550 nm, 0.93 → 0.99 at 1 µm, and by ≤ 0.03 points beyond 2 µm.
  Corrected zenith Rayleigh extinction is 0.110 mag/airmass, just under the published
  *total* 0.12–0.20 band (which also carries aerosol and ozone). The LWIR anchors move
  by +2.74 ppm at 8 µm decaying monotonically to +0.29 ppm at 13 µm — the λ⁻⁴·⁰⁹
  signature, which is the check that this repin is the Rayleigh term and nothing else.

  **Downstream, the VIS/NIR effect is not simply "more signal".** Removing the excess
  molecular scattering raises transmission *and* halves the scattered-sky irradiance
  that illuminates the target. For a visible reflective scene the sky term dominates,
  so the net signal falls: on scenario 5.1 (0.5–0.8 µm), τ_up 0.494 → 0.741 and
  τ_sun 0.445 → 0.708, while `E_sky_scattered` drops 524 → 257 W/m²/µm and the
  collected signal halves (58 710 → 29 940 e⁻), taking SNR 242 → 173. 73 metric values
  across 30 scenario baselines moved; the largest are SNR −34 % (5.4), −29 % (1.4),
  −29 % (5.1), −27 % (3.4) and **+24 % (10.3, ground-to-space visible)**, with NEDT up
  to +53 %. Six scenarios whose SNR previously fell outside the GIQE-5 envelope now
  report a NIIRS value instead of `null`. All 38 GUI baselines regenerated per
  `RADIANT_Testing_Validation.md` §5.3.

  **Caveat carried forward:** the VIS/NIR *magnitudes* above now rest on the
  single-scatter sky model, whose own defects are still open — CU-224 (up- vs
  down-looking path radiance use different physics), CU-225 (28 % step at the grazing
  hand-over) and CU-260 (single-scatter species split underflow). This fix removes a
  first-order unit error; it does not validate the sky model that the corrected
  numbers now expose.

### Added
- **Up-looking topology provenance is published (CU-266).** `AtmosphereStage` now
  publishes `stage_outputs["atmosphere"]["topology_provenance"]` for up-looking and
  level scenes — the observer-leg detail, segment provenance, GF-9 illumination note
  and sky-continuation note that previously survived only in an INFO log record. An
  analyst can now see from `result.inspect()` why τ_sun took its value (sunlit vs
  shadowed). Absent for down-looking and vacuum paths, which carry no such narrative;
  no computed value changes.

### Changed
- **Atmospheric capability refusals are now `RadiantError`s (CU-240).** The three
  "this backend cannot serve this geometry" refusals (`InterpolatedAtmosphere`,
  `ModtranAtmosphere`, `TabulatedAtmosphere`) raise a new
  `AtmosphereCapabilityError` instead of a bare `NotImplementedError`. The GUI shows
  them as actionable refusals rather than "Unexpected Error" crash dialogs, and
  `except RadiantError` in user scripts now catches them. The class co-inherits
  `NotImplementedError`, so existing `except NotImplementedError` call sites keep
  working.
- **The horizon-guard shoulder warning now sizes the refraction it excludes
  (CU-269).** The `UserWarning` states what a k = 4/3 refracted ray would have done
  to this path's tangent depression, and the structured context carries the refracted
  depression plus the peak and path-mean sampling-altitude error. v1.x still models no
  refraction — this only quantifies the omission. Segments with no interior tangent
  point say the sizing does not apply instead of quoting an inapplicable number.

### Added
- **Direction-aware Geometry GUI (Geometry-Flexibility Phase 4).** The 2D
  geometry schematic now composes by the stage-derived `los_direction`:
  up-looking scenes draw the sensor as the path's lower endpoint (on the ground
  plane for a ground observer) with the LOS ascending, and level arms draw both
  endpoints at one abstract height. Two new revealable angle annotations — the
  path zenith θ_o (obtuse-capable) and the lower-endpoint zenith ζ_low — join
  the catalog, plus a level-arm Δh tangent-sag leader pill sourced from the core
  horizon-guard classifier. Down-looking scenes render byte-identically to
  before. The Geometry Inputs tab gains the **scene-class steering card**: the
  derived observer→target class chip, the optional `geometry.scene_class`
  assertion (mission-type entry point; asserted-vs-derived mismatches tint the
  card in-context), and a per-class preview of the metrics off by default.
  Viewing-mode labels are re-worded direction-general ("Path zenith at lower
  endpoint (V1)", "Off-boresight angle (V2)", "Elevation angle, signed (V4)").
- **`radiant.api.scene_relevance`** — new public bridge re-exporting the
  scene-class → default-metric-relevance map (`SCENE_RELEVANCE`,
  `default_off_metrics`, …) from `radiant.performance.scene_relevance` for view
  layers (guardrail G3: one declarative map, no GUI-side copy).

### Fixed
- **A smear wider than the PSF grid no longer crashes the evaluation (CU-235).**
  `PlatformStage` forced each kernel size odd and *then* clamped it to the PSF
  grid — which is 1024, even — so any degradation wide enough to reach the clamp
  came back out even and the kernel builder raised, aborting the whole chain. The
  guard that existed to make an over-wide smear survivable was the thing that
  crashed it, and it was reachable from ordinary inputs (a 7000 m/s LEO
  ground-track speed at the shipped 5 ms integration time). All three kernel
  sites — smear, turbulence and jitter — had the same defect and now share
  `radiant.platform.kernel_size.odd_kernel_size`, which clamps first and forces
  odd downward. The over-wide notice is also now a `UserWarning` rather than a
  log line (clamping is clipping, Rule 17) and states what the truncation costs:
  the PSF path carries less blur than the MTF product's analytic smear term, so
  EE/RER/FWHM are optimistic and the dual-path consistency check flags it.

### Added
- **Target reflectance ρ(λ) is published and plotted (GUI walkthrough item 6).**
  `SourceStage` publishes `stage_outputs["source"]["reflectance"]` — the target's
  resolved ρ(λ) as dimensionless `SpectralData` on the chain grid — for both
  reflective pathways: a user-supplied ρ (scalar or a ρ(λ) CSV) and the Kirchhoff
  ρ = 1 − ε of a mixed emit+reflect target. It is absent, not zero, for a target
  that carries no reflectance. `AtmosphereStage` publishes the companion
  `at_source_target_reflected` frame — the ρ-proportional part of the source
  emission (direct solar + diffuse sky, no self-emission). `result.plot` gains
  `target_reflectance()` and `spectral_reflected_radiance()`, which are now the
  two figures on the Source stage's *Target — reflective* tab. Both publications
  reuse the decomposition and the reflectance resolver the radiance path already
  used (the resolver moved to `radiant.core.target_reflectance` so SourceStage
  and the atmosphere assembly share one implementation), so no computed metric
  moves and every golden baseline is unchanged.
- **The reflective tab can input a spectral ρ(λ) (GUI walkthrough item 6).**
  `source.target.reflectance_path` — a λ-dependent reflectance CSV that the
  schema and the inferrer already supported — is now mounted on the Source
  *Target — reflective* input card beside the scalar ρ, so a spectral
  reflectance no longer requires hand-editing YAML. The two surfaces stay
  mutually exclusive; the engine's rejection reaches the operator through the
  actionable evaluate dialog and the Messages panel.
- **At-image spectral irradiance (GUI walkthrough item 16).**
  `SpectralIntegrationStage` publishes
  `stage_outputs["spectral_integration"]["spectral_irradiance_at_image"]` —
  E(λ) in W/m²/µm on one detector pixel — and `result.plot` gains the matching
  `spectral_irradiance_at_image()` accessor, now the lead figure on the
  Spectral Integration view. This is the stage's own `photon_rate` expressed as
  power per unit focal-plane area, not a re-derivation, so it is regime-correct
  by construction (the rate already carries Ω_pixel for an extended scene and
  Ω_target for a point source) and integrates back to the published `signal_e`
  exactly — pinned by a round-trip test.

### Changed
- **Sun geometry is read-only on the Source reflective tab (GUI walkthrough
  item 6).** `geometry.solar_illumination` / `solar_zenith_rad` /
  `solar_azimuth_rad` were mounted there as editable rows, a second editor for
  three Geometry-owned parameters. They now render through the new
  `FieldRow.set_read_only` — fully legible (they answer "why is my reflected
  term dark?") but inert, each naming the Geometry stage as their owner. The
  Source *Target — reflective* tab also no longer plots the at-aperture
  `spectral_source`; that post-atmosphere view belongs to the Atmosphere stage,
  the same move item 5 made for the point-source tab.
- **Source "Target — point source" plots the source-side emission, not the
  at-aperture radiance (GUI walkthrough item 5).** The tab defines what the
  target *emits* (blackbody T/area/ε or a band-integrated intensity in W/sr),
  but plotted `spectral_source` — the radiance after the atmosphere has already
  attenuated it — so the operator could not see the effect of the intensity they
  were typing. It now plots `spectral_source_emission`. The at-aperture view
  still lives on the Atmosphere stage, which owns that step.
- **Integration time is edited on Readout only (GUI walkthrough item 21).**
  `spectral_integration.integration_time_s` was mounted on both the
  Spectral-Integration and Readout input cards, giving one parameter two
  editors. The Spectral-Integration card is now the filter bandpass alone. The
  schema is unchanged — the parameter keeps its dot-path and owning stage; only
  which form surfaces it changed.
- **The PSF plots now show the fully degraded PSF, cropped to the core (GUI
  walkthrough items 14 and 20).** `result.plot.psf()` and
  `result.plot.psf_pixel_grid()` read `stage_outputs["optics"]["effective_psf"]`
  — the PSF *before* PlatformStage convolves jitter, smear and turbulence into
  it. Rule 4 makes one `EffectivePSF` the source of every spatial metric, and
  that one is the fully degraded PSF the later stages build (`performance` >
  `platform` > `optics`), so the figure disagreed with the EE_box, RER, FWHM and
  Strehl computed beside it: with 15 µrad of jitter the plotted peak was ~5×
  too high. Both accessors now resolve the most-degraded PSF available. They
  also crop to ±6 detector pixels around the core (`span_pixels`) instead of
  rendering the whole array — a 1024² grid at ~8 samples/pixel is ±60 pixels of
  mostly empty field — and `psf()` outlines the pixel the core lands in
  (`pixel_outline`). `plot_psf(pixel_grid_span=...)` is deprecated in favour of
  `span_pixels=...`, which now applies to both variants.
- **The Optics MTF tab is re-laid out and the MTF-at-Nyquist bar chart is gone
  (GUI walkthrough items 10-12).** The `mtf()` overlay now marks the detector
  Nyquist frequency with a red dashed vertical line, and the per-contributor
  budget moved *below* the figure and split into X and Y tabs, each sampling
  every contributor at 0.25, 0.5, 0.75 and 1.0 × Nyquist plus a system-product
  row — where a single MTF@Nyquist column showed only where each roll-off ends.
  The separate `mtf_budget` bar chart was dropped from the tab (it re-marked the
  table's own numbers); the `result.plot.mtf_budget()` accessor itself is
  unchanged and still available to scripts.
- **The Optics PSF + Pupil tab puts its three maps on one row** (walkthrough
  item 13), ordered cause-then-effect: pupil apodization, pupil WFE, PSF.
- **The Detector noise table sits beside the pie rather than under it**
  (walkthrough item 17), so every term is visible without scrolling.

### Added
- **The Atmosphere view separates the target and background columns (GUI
  walkthrough item 8).** These are genuinely different paths whenever the target
  sits above the surface: the target is seen through `τ_up` (target → sensor)
  while a surface background is seen through `τ_full_up` (ground → sensor,
  including the air *below* the target). On the shipped MWIR example with a
  500 km sensor and a 10 km target the two transmittances are 0.87 and 0.50 —
  the effect that sets contrast, previously invisible because only the target
  arm was plotted. New `result.plot.spectral_atmosphere_background()` draws the
  background column, and `result.plot.spectral_at_aperture_arms()` puts both
  at-aperture radiances on one axis. `result.plot.spectral_atmosphere()` is
  unchanged except for a title now naming it as the target arm. For a
  surface-level target, or an up-looking scene, the two columns coincide by
  construction and the figures agree.
- **PSF convolution kernels are now visible, not just named (GUI walkthrough
  items 15 and 19).** `EffectivePSF` gained a `kernels` field holding the arrays
  convolved in, paired with the names `convolution_history` already recorded —
  so a view can show *what* each degradation did rather than only that it
  happened. New `result.plot.psf_kernels()` draws every retained kernel as a row
  of 2-D maps (each cropped to its own support and scaled independently, since
  they differ by orders of magnitude), and `result.plot.detector_kernels()`
  draws only the detector-side subset (pixel aperture, charge diffusion, IPC).
  The Platform stage gains a **PSF degradation** tab pairing the kernels with
  the post-convolution PSF; the Detector **Detector + PSF** tab now places the
  pixel illustration beside the kernel that pixel imposes.
- **`radiant.performance.mtf_fraction_table`** — samples each MTF contributor at
  a ladder of Nyquist fractions (default 0.25/0.5/0.75/1.0). Sampling only: no
  new MTF physics. `PerformanceStage` publishes
  `stage_outputs["performance"]["mtf_fraction_table_x"]` / `_y`, plus
  `nyquist_freq_cycles_per_mrad` (the Nyquist limit on the chain's angular axis,
  so views need not re-derive the cycles/m ↔ cycles/mrad conversion).

### Changed
- **GUI preferences now persist to a portable INI file (CU-233).** `SettingsStore`
  built its `QSettings` with the two-argument `QSettings(organization,
  application)` constructor, which ignores `QSettings.setDefaultFormat()` and
  resolves to the platform-native backend (a plist under
  `~/Library/Preferences` on macOS). That made the store unreachable by the test
  suite's path redirection — the cause of the theme resets fixed above — and it
  persisted differently on macOS than on Windows. It now uses the explicit
  `IniFormat` / `UserScope` constructor that `PinnedPanel` already used, so both
  GUI persistence surfaces share one portable, redirectable backend.
  **One-time reset (owner-ratified):** no migration reads the old native store
  forward, so the remembered theme, recent-files list, and panel show/hide state
  start empty on the next launch. The GUI opens in the light default once; the
  View menu re-establishes the preference and it persists from then on.

### Fixed
- **Results-affecting (turbulence scenes only; no shipped baseline affected):
  turbulence now actually enters the MTF-product path.** A unit slip
  (`* 1e3` for `* 1e-3` in the cycles/mrad → cycles/m conversion, present
  since the dual-path architecture landed 2026-04-18) left
  `mtf_turbulence_x/y ≡ 1`, so every MTF-product consumer (MTF budget,
  MTF-at-Nyquist, folded MTF, GIQE/NIIRS) ignored turbulence while the PSF
  path applied it — a Rule-4 dual-path violation of up to 0.88 absolute MTF
  error. Direction of change: MTF-product metrics decrease (correctly) on
  scenes with turbulence; no shipped scenario or golden baseline sets
  `atmosphere.r0_m`, so no recorded result moves. (CU-234)

- **An up-looking scene no longer aborts the whole chain evaluation (GUI
  walkthrough items 3 & 4).** Ground sample distance is a down-looking quantity —
  it is the ground footprint of a pixel — but `PerformanceStage` computed it
  whenever a sensor altitude and focal length were set, regardless of where the
  line of sight pointed. An up-looking scene publishes θ_o = π, which
  `compute_gsd_from_geometry` correctly rejects as outside `[0, π/2)`, and that
  raise propagated out of `Sensor.evaluate()` — killing every other stage and
  metric with it. In the GUI it surfaced as *"Parameter Rejected —
  compute_gsd_from_geometry: incidence_angle_rad = 3.141592653589793 must be in
  [0, pi/2)"* on raising `geometry.target_altitude_m` above the sensor, and as a
  geometry schematic that then refused to redraw. `gsd_cross_track_m`,
  `gsd_along_track_m`, and `gsd_geometric_mean_m` are now simply **absent** for
  up-looking and level scenes, following this stage's existing convention that a
  metric which does not apply is not published. Down-looking results are
  unchanged. Note `diffraction_limit_ground_m` still publishes for these scenes
  (it is a slant-range quantity despite its name) — tracked as CU-231.
- **Monte-Carlo tolerances are entered and shown in the parameter's displayed
  unit (GUI walkthrough item 2).** The tolerance fields in the parameter editor
  were unlabelled and passed their numbers to `Sensor.set_tolerance` raw, so a
  target altitude displayed in km silently took its spread in metres. Each field
  now states the unit it is read in, follows the value editor's unit selector,
  and converts once at the API boundary. The conversion is per-field because the
  fields are not the same kind of quantity: `std` is a *difference* (scale only —
  a σ of 1 °C is a σ of 1 K, not 274.15 K), `low`/`high` are *absolute* bounds
  (the affine offset applies), and log-normal `sigma` is dimensionless and is
  never converted. New Qt-free module `radiant.gui.tolerance_units` holds that
  rule. Stored tolerance values are unchanged; only entry and display move.
- **The GUI test suite no longer overwrites the developer's real preferences
  (GUI walkthrough item 1).** A chosen dark theme kept reverting to the light
  default between launches. Persistence was working — the culprit was the suite:
  `QSettings(organization, application)` ignores `QSettings.setDefaultFormat()`
  and resolves to `NativeFormat`, so the CU-115 isolation fixture never
  redirected `SettingsStore` at all. Every GUI test that built a window without
  injecting a store wrote to the real user preferences, and the configuration
  theme-toggle test stamped an arbitrary theme over the operator's choice on each
  run. The fixture now sandboxes the store's `QSettings` construction directly.
  The underlying backend inconsistency (`SettingsStore` on `NativeFormat` while
  `PinnedPanel` uses `IniFormat`) is tracked as CU-233 — fixing it relocates
  saved preferences and needs an owner call.

### Added
- **Geometry-Flexibility Phase 3 — direction-aware degradations and metrics
  (Gaps 110, 111; findings GF-13, GF-15; guardrail G3).** Four capabilities land
  together and are itemised below: the Cn²-profile-driven Fried parameter, the
  derived scene class + target kinematics in `GeometryStage`, the moving-target
  smear arm, and the scene-class → metric relevance map with its target-plane
  sample distance and path-aware detection range.
  **Results-affecting: NONE.** No existing scene's computed value changes.
  Every new behaviour activates only through a newly-set parameter — target
  velocity and LOS rate default to *unset* (the platform-only rate is
  numerically the rate the smear arm always derived), `atmosphere.cn2_profile`
  defaults to `direct` (the pre-Gap-110 `r0_m` passthrough), and the relevance
  map's `*_to_ground` off-set contains only metric keys this phase created.
  The one *selection* change — a non-ground-target scene now defaults the
  ground-projection metric family off and the target-plane family on — alters
  which metrics are emitted, never what any emitted metric computes. Proved
  end-to-end in `tests/integration/test_phase3_conditioning.py`,
  `test_los_rate_zero_drift.py`, `test_moving_target_smear.py`,
  `test_scene_relevance_chain.py`; all 78 golden baselines unchanged.
- **Moving-target smear (Geometry-Flexibility Phase 3, Gap 111 consumer).**
  `PlatformStage` now consumes the relative line-of-sight angular rate
  published by `GeometryStage` and turns it into the smear extent
  (`platform/relative_motion_smear.py`, Rule 19: `s = ω_LOS · f · t_int`),
  feeding both Rule-4 spatial paths — the rect PSF kernel and the
  `mtf_smear_*` product terms — from that one rate. Platform and target
  motion compose as vectors upstream (`v_rel = v_target − v_sensor`), so they
  are one smear rather than two combined: a co-moving target smears not at
  all, a counter-moving one smears twice as much, and an RSS of two separate
  smears (which would return √2× in both cases) is never formed. A direct
  `platform.smear_length_um` still wins, and now warns when it suppresses a
  kinematics-derived smear. **Not results-affecting for existing scenes:** the
  arm engages only when a kinematics door (`geometry.target_speed_m_s` /
  `target_heading_rad` / `target_climb_rad`, or `geometry.los_angular_rate_rad_s`)
  is explicitly set; with none set the stage runs the unchanged
  velocity/range door and every smear number is bit-identical (proved by exact
  equality over a 576-configuration grid plus the golden suite).
- **Target-plane sample distance (Geometry-Flexibility Phase 3, finding GF-13).**
  Three new metrics — `target_plane_sample_distance_x_m`, `_y_m`,
  `_geometric_mean_m` (module `performance/target_plane_sample_distance.py`,
  Rule 19) — the non-ground counterpart of GSD: the pixel's angular subtense
  projected at the slant range (`pitch × R / f`), with no ground-plane `cos`
  projection, in the plane through the target normal to the line of sight.
  Defined where GSD is not, because it needs no incidence angle. **Not
  results-affecting for existing scenes:** surfaced by default only for a
  non-ground target (see the relevance map below), so every ground-target run
  emits exactly the metric set it did before.
- **Scene-class → metric relevance map (Geometry-Flexibility Phase 3,
  guardrail G3, finding GF-13).** One declarative map
  (`performance/scene_relevance.py`) supplies the *engine-side defaults* of the
  Gap 96 selection machinery, keyed on the derived scene class published by
  `GeometryStage`. For an air or space target the ground-projection family
  (`gsd_*`, `ground_range_m`, `swath_width_m`, `access_rate_m2_s`,
  `diffraction_limit_ground_m`, `max_integration_time_s`, `niirs`,
  `niirs_extrapolated`) defaults **off** and the target-plane sample distance
  defaults **on**; angular-resolution, radiometric, spatial/MTF and saturation
  metrics are band-independent and unaffected. Override semantics are
  unchanged: the map conditions a metric group only while that group's
  `performance.metrics.*` flag is still at its default provenance, so an
  explicitly-set flag wins outright. Physics never branches on the class
  (ADR-0011 decision 8). **Results-affecting only for non-ground-target
  scenes**, and only in *which* metrics are emitted — no computed value
  changes. A ground-target scene's default metric set is bit-identical to
  before.
- **Path-aware point-source detection range for up/level topologies
  (Geometry-Flexibility Phase 3, finding GF-15).** `detection_range_m` now
  dispatches on the derived LOS direction. `up` and `level` paths evaluate
  τ(R) along the actual ray (`performance/detection_path_aware.py` over
  `performance/path_optical_depth.py`) instead of extrapolating one constant
  extinction coefficient: the profile is piecewise and stops accruing optical
  depth where the ray leaves the modelled column, and the bisection's upper
  bound is the analytic vacuum solution `R_ref·√(SNR_ref/threshold)` rather
  than a fixed ceiling. An up-looking path whose continuation is still inside
  the atmosphere is **refused** with a named `failure_reason` rather than
  answered with the wrong model (Rule 17). **Not results-affecting for
  existing scenes:** the down-looking arm is untouched and bit-identical;
  migrating it is a separate owner decision.
- **Cn²-profile-driven Fried parameter (Geometry-Flexibility Phase 3, Gap 110).**
  Turbulence stops being a path-blind user-entered `r0`. New parameters
  `atmosphere.cn2_profile` (`direct` | `hufnagel_valley` | `tabulated`),
  `atmosphere.cn2_hv_wind_rms_m_s`, `atmosphere.cn2_hv_ground_strength`,
  `atmosphere.cn2_tabulated_file`, `atmosphere.turbulence_wave_type`
  (`plane` | `spherical`). Selecting a profile makes r₀ a derived quantity:
  `atmosphere/r0_path.py` integrates
  `r0 = [0.423 k² sec ζ ∫ Cn²(h) W(h) dh]^(-3/5)` over the part of the line of
  sight inside the atmosphere, with ζ the lower-endpoint zenith (ADR-0011
  decision 3, via the Phase-2 `observer_leg` machinery), plane- or
  spherical-wave weighting (the spherical weight peaks **at the aperture** —
  turbulence near the sensor dominates), and a closed-form constant-altitude
  branch for level paths. Profiles live one-per-module:
  `atmosphere/cn2_hufnagel_valley.py` (HV; schema defaults are HV-5/7, which
  reproduce the published r₀ = 5 cm and θ₀ = 7 µrad at 0.5 µm for a vertical
  path) and `atmosphere/cn2_tabulated.py` (measured table, log-linear
  interpolation, zero-with-a-`UserWarning` outside its range; the CSV is read
  pre-chain by `loaders.build_cn2_profile` and injected at
  `stage_outputs["atmosphere_config"]["cn2_profile"]`, Rule 6).
  **Not results-affecting:** `atmosphere.cn2_profile` defaults to `direct`,
  which passes `atmosphere.r0_m` through unchanged and consults no geometry —
  every existing scene is bit-identical, and the new `r0_resolution` stage
  output appears only when a profile is actually evaluated.
- **New error class `radiant.atmosphere.errors.TurbulenceSpecificationError`**
  (a `RadiantError`). Raised when `atmosphere.cn2_profile` selects a profile
  *and* `atmosphere.r0_m` is explicitly set to a value the profile does not
  reproduce within 1 % (the CU-093 redundant-entry pattern), or is explicitly
  set to `0` alongside a profile (contradictory intent).
- **Derived scene class + target kinematics in GeometryStage
  (Geometry-Flexibility Phase 3; ADR-0011 decision 8, Gap 111).** Two additive
  publications in `stage_outputs["geometry"]`, both reachable only through newly
  legal inputs — **not results-affecting**: no existing scene's numbers change
  (proved in `tests/integration/test_los_rate_zero_drift.py`).
  1. **Scene class** — `geometry/scene_class.py` derives the ADR-0011
     observer × target band label (`ground` h < 1 km, `air` 1–100 km, `space`
     h > 100 km, the `h_atm_top` convention; both boundaries closed from below)
     and publishes `scene_class` / `observer_class` / `target_class`. The 1 km
     boundary is a naming convention with **no physical effect** and physics
     never branches on the class. New optional parameter `geometry.scene_class`
     lets a user *assert* the class; a disagreement with the derivation raises
     `GeometrySpecificationError` naming asserted vs. derived and both altitudes
     (the CU-093 pattern — it catches wrong-magnitude altitude typos). The
     assertion is never required (`auto` = unset).
  2. **LOS angular rate** — `geometry/los_rate.py` publishes
     `los_angular_rate_rad_s` (ω = |v_rel,⊥| / R) and `los_rate_mode`. Both
     Gap 111 doors ship, provenance-resolved with the ADR-0006 1 % agreement
     check: the new `geometry.los_angular_rate_rad_s` (direct, K1) and the new
     target-velocity triple `geometry.target_speed_m_s` /
     `geometry.target_heading_rad` / `geometry.target_climb_rad` (K2). With
     neither set the published rate is the platform-only value
     `ground_speed / slant_range`, which is *exactly* the rate
     `platform/smear.py` already derives. Heading is referenced to the
     observer's ground azimuth (the `delta_phi` zero); the platform track is
     modelled cross-track to the LOS azimuth plane, matching the existing smear
     arm. `None` only for coincident endpoints. Its consumer is the
     moving-target smear arm above, which landed in the same phase.
  Also new: a `los_rate` family in `geometry/mode_manifest.py` (K0/K1/K2), so
  the GUI mode form follows automatically, and `rad/s` (with `deg/s`, `mrad/s`,
  `urad/s`) in the `core.units` registry.
- **Shipped up-looking atmosphere library family + direction-aware family
  dispatch (Geometry-Flexibility Phase 2, GF-10; Gap 109).** New committed
  family `midlat_summer_uplooking_ladder/` — the MODTRAN K-block vertical
  partial-column ladder (ground sensor looking up to targets at 1/3/5/10/20 km,
  plus a synthesized exact zero-length node at 0 km). It is the first
  **up-looking** run family, and its radiance product is the *downward* path
  radiance (`L_toward_lower`), stored under a distinct NPZ key
  (`path_radiance_toward_lower`) with a `los_direction = "up"` marker so it can
  never be read as an upwelling column. New public surface:
  `InterpolatedAtmosphere.uplooking_column_product(wavelength_um, los) ->
  UplookingColumnProduct` (τ + `L_toward_lower`, 1-D log-τ interpolation over
  target altitude, sensor endpoint taken from `los.h_sensor` per guardrail G2),
  the `family_direction` constructor keyword (default `"down"`), and the
  `family_direction` property. `InterpolatedAtmosphere.evaluate` now refuses an
  up-looking family and vice versa. Shipped-family default selection is keyed on
  `(los_direction, interpolation_axes)` instead of the axes string alone; an
  unshipped combination raises the existing actionable error, now naming every
  shipped combination in both directions. **Not results-affecting** — every
  pre-existing family, construction and query path is byte-identical (proven by
  regenerating all 97 committed NPZ files and comparing array-for-array).
  Deliberate limits, all refusals rather than approximations: the family is
  vertical-only (an off-vertical up-looking interpolated query raises and points
  at `atmosphere.model = "simple"`; the sec(ζ)-space mapping is deferred until an
  up-looking zenith fan is run — the K6 45° holdout measures the error it would
  have made at 0.1–2.2 % band-mean τ), ground-endpoint-only (1 m tolerance), and
  hull-limited to 20 km.
- **Direction-aware atmosphere — up-looking and level paths compute
  (Geometry-Flexibility Phase 2; Gaps 107/108/109; ADR-0011).** `AtmosphereStage`
  now dispatches on the derived `los.los_direction`
  (`atmosphere/topology.py::evaluate_path_topology`): `down` takes the backend's own
  `evaluate` **unchanged and not rerouted**, while `up` and `level` are served by
  ADR-0011 path-segment composition — an observer-leg column keyed to the *sensor*
  (the lower endpoint) or a constant-altitude arm, the target-side illumination
  products reused as-is, and a sky continuation. Ground-to-air (matrix E2),
  air-to-air level (E5), ground-to-space SST (E3) and air-to-space (E6) run
  end-to-end on `atmosphere.model = "simple"`. Transmittance reciprocity is
  pinned: the same physical line expressed both ways gives the same τ to within
  an ULP, exactly for the vertical case. **Not results-affecting** — the new
  behaviour is reachable only through inputs that were rejected before Phase 1,
  and every down-looking golden baseline is unchanged.

  **Zero drift, stated explicitly (Rule 29):** no existing scene's numbers moved
  anywhere in Geometry-Flexibility Phase 2. The full suite is green with **zero**
  golden-baseline changes, and no entry in this release carries a
  **Results-affecting:** prefix on account of Phase 2. The only Phase-2 change of
  *outcome* for a previously-computable scene is the retired collocated carve-out
  recorded under **Changed** below, which was landed in Phase 1.
- **`SkyBackground` background descriptor (matrix B2; Gap 108).** New
  `radiant.core.descriptors.SkyBackground` — the sky radiance along the LOS
  continuation, for scenes whose line of sight leaves the atmosphere past the
  target instead of landing on the Earth. It carries **no user parameters**: the
  radiance is computed from the scene (`atmosphere/sky_radiance.py`, or
  `atmosphere/segment_grazing.py` for a near-tangent continuation past the 89.5°
  column ceiling) and passed into assembly. Selected automatically for up-looking
  and level point-source / sub-pixel scenes by the new
  `radiant.core.los_termination.classify_los_termination` (Use-Case Matrix Rule B);
  the down-looking default is untouched, so `GroundBackground` is still required
  for a down-looking non-extended scene exactly as before. Band-gated per the
  ratified decision: MWIR/LWIR first-class, VIS/NIR computes with a provisional
  `UserWarning`. A `GroundBackground` supplied for an up-looking or level path now
  raises (there is no ground behind the target).
- **Per-altitude solar illumination — the terminator shadow-height test (GF-9;
  ratified decision 21).** New `radiant.atmosphere.solar_shadow` (`sunlit`,
  `shadow_height_m`, `solar_tangent_radius_m`) replaces the global
  sun-above-the-horizon rule, so sunlit-target-over-dark-ground is expressible: a
  60 km booster is lit at 5° solar depression while the ground beneath it
  (shadow height ≈ 24 km) is not. A sunlit target below the terminator gets a
  two-arm tangent transit for `τ_sun` (`radiant.atmosphere.solar_transit`,
  **provisional** — no MODTRAN twilight deck in batch 1); a shadowed one gets
  `τ_sun ≡ 0`. Supporting primitives: `radiant.atmosphere.grazing_column`
  (spherical slant column through an exponential shell, validated against
  Chapman's analytic grazing limit and Kasten-Young air mass) and
  `radiant.atmosphere.segment_grazing`.

- **MODTRAN horizontal (ITYPE=1) path length is wired — `ModtranConfig.hrange_km`
  (Geometry-Flexibility Phase 2; Gap 109).** New config field `hrange_km: float = 0.0`
  carries Card 3 `RANGE` (the geometric path length of a constant-altitude path, km).
  `render_tape5` writes it, and for `itype=1` writes the horizontal `ANGLE = 90.000`
  a level path has by definition rather than reading `path_zenith_rad` (MODTRAN ignores
  H2/ANGLE for ITYPE=1, and a level path's 90° is an interior-tangent quantity
  `AtmosphericGeometry` deliberately refuses to carry). Validation is two-sided and
  actionable: `itype=1` without `hrange_km` is a zero-length path and raises;
  `hrange_km` with `itype` 2 or 3 over-specifies a slant path (MODTRAN derives RANGE
  from H1/H2/ANGLE) and raises. **Not results-affecting**: the field defaults to 0.0
  and `f"{0.0:10.3f}"` reproduces the exact ten-character literal the RANGE field held
  before, so every non-horizontal deck renders byte-identically (proven over the 63
  ITYPE≠1 run-matrix rows and a 34 560-configuration parameter grid, exact string
  equality against the pre-change builder). Consequence: the 25-row horizontal 5×5
  grid (`docs/plans/modtran_run_matrix.csv` rows L1–L25) is regenerable from the
  matrix instead of needing a hand-edited HRANGE, and its `deck_builder_support`
  moves from `phase2_range_wiring` to `current`.
- **Generalized viewing geometry — the geometry core is direction-general
  (Geometry-Flexibility Phase 1, ADR-0011; Gap 107).** RADIANT can now *express and
  resolve* any observer/target altitude pair and LOS direction, not only
  sensor-above-target. Concretely:
  - `geometry.path_zenith_rad` (θ_o) spans the **closed** domain `[0, π]` — up from
    `[0, 1.562]` (≈89.5°). `π` is the vertical up-looking case (a ground sensor with
    the target at its zenith; a LEO sensor directly beneath a GEO target) and is
    attained exactly. *(ADR-0011 writes `[0, π)`; that was a notation slip —
    owner-confirmed 2026-07-26 (plan §8.3). The closed interval is implemented, with the
    discrepancy noted at the domain validator.)*
  - `geometry.elevation_angle_rad` becomes **signed**: bounds widen from
    `[0.0088, 1.5708]` to `[−π/2, π/2]`. The 0.5° grazing floor is superseded by the
    horizon guard, which judges the path's tangent topology rather than the raw angle.
  - **Every entered viewing angle is referenced to the path's lower endpoint**
    (ADR-0011 decision 3). Exactly back-compatible — today's target is always the
    lower endpoint — but it is what makes V1/V2/V4 unambiguous when the sensor is
    below the target. V2 (`geometry.sensor_off_nadir_rad`) is therefore an
    off-**boresight** angle whose reference axis (nadir or zenith) is resolved from
    the altitudes, never declared.
  - `LineOfSightGeometry` carries **both** endpoints: `h_sensor` joins `h_tgt`, and
    the object exposes the derived `los_direction` (`down`/`up`/`level`) and
    `is_uplooking`. `GeometryStage` always populates `h_sensor` and publishes
    `stage_outputs["geometry"]["los_direction"]`. Serialization extends
    back-compatibly: `h_sensor` is emitted only when carried, so a legacy payload
    round-trips to the identical byte sequence, and `from_dict` maps both an absent
    key and an explicit `null` to `None`.
  - `h_sensor` on the LOS is now the **single source of truth** for the sensor
    altitude inside `radiant.atmosphere`; no backend reads
    `geometry.sensor_altitude_m` from the `ParameterSet` (guardrail G2). A LOS that
    does not carry it raises an actionable error rather than silently falling back.
  - **Up-looking space-to-space (LEO→GEO) runs end-to-end**, vertical and slant —
    both endpoints above `h_atm_top` make the whole path, and its continuation,
    vacuum (`τ ≡ 1`, `L_path ≡ 0`, `E_sky ≡ 0`, cold-space background).
  - **Not yet: the atmosphere.** It remains direction-blind, so `AtmosphereStage`
    refuses — before backend dispatch, with an error naming the pending capability —
    any up-looking or level path whose lower endpoint is inside the modelled column.
    Direction-aware path products, sky-along-LOS backgrounds, and the horizontal arm
    are Phase 2 (Gaps 108/109).
- **Horizon guard for near-horizontal paths (ADR-0011 decision 6, plan §8.3).** Paths
  where unmodelled refraction would dominate now fail loudly or warn quantitatively
  instead of returning a plausible wrong number (Rule 17). The guard keys on the
  segment's tangent-point topology: *endpoint-minimum* paths use angular bands at the
  lower endpoint (< 0.5° raise, 0.5–2° compute + `UserWarning`), *interior-tangent*
  paths use the tangent-height depression Δh ≈ L²/8R_E (< 100 m clean, 100 m–2 km
  compute + `UserWarning`, > 2 km raise as a limb-like transit). Thresholds are named
  module constants in `core/viewing_triangle.py` and are **provisional** pending
  Phase 2 MODTRAN calibration. New public helpers: `classify_horizon_topology`,
  `check_horizon_guard`, `HorizonGuardResult`, `solve_from_lower_zenith`, and the
  `level_*` central-angle family.

### Changed
- **Turbulence is no longer gated on observer type (ADR-0011 guardrail G4,
  Rule 27).** `RADIANT_Atmosphere.md`'s rule that "the parameter resolver
  rejects turbulence for a space observer with a `ScopeError`" is retired: the
  path integral simply finds no atmospheric column above a space sensor,
  returns a finite huge r₀ (saturated at 1 km, flagged `negligible`), and the
  turbulence MTF term is omitted entirely rather than forced to unity. The rule
  was documentation-only — no code implemented it — so this is a doc/behaviour
  reconciliation, not a results change. A 20 km sensor looking up through the
  residual HV-5/7 column gets r₀ = 4.13 m at 0.5 µm, a real (if small) number.
- **Horizon-guard thresholds are stored in radians (CU-222).**
  `radiant.core.viewing_triangle.GUARD_HARD_DEG` / `GUARD_WARN_DEG` become
  `GUARD_HARD_RAD` / `GUARD_WARN_RAD` (`math.radians(0.5)` / `math.radians(2.0)`),
  `horizon_band_action` compares and returns in radians, and
  `HorizonGuardResult.band_deg` becomes `band_rad`. Degrees survive only in
  message text. The error `context` keys move with them: `band_deg` → `band_rad`,
  `guard_hard_deg` → `guard_hard_rad`, `guard_warn_deg` → `guard_warn_rad` (no
  deprecated aliases — the only readers were in-repo and moved in the same
  change). Rule 2: radians are the canonical internal angular unit. Verdicts are
  unchanged, with one deliberate repair: the boundary comparison now carries
  1e-12 rad of slack, so a band landing *exactly* on a ratified threshold falls
  on the permissive side regardless of how the caller's angle was constructed —
  without it, `math.radians(89.5)` and `π/2 − math.radians(0.5)` differ by ~1e-16
  rad and flip the verdict at 89.5° exactly. **Not results-affecting.**
- **`geometry.solar_zenith_rad` upper bound widened from 1.5707 rad to π**, and
  `AtmosphericGeometry.solar_zenith_rad` likewise accepts the closed `[0, π]`
  (was `[0, π/2)`). A sun below the local horizontal is now legal input; whether a
  point is illuminated is decided per-altitude by `atmosphere/solar_shadow.py`, not
  by the bound. **Not results-affecting**: every scene with `θ_s ≤ π/2` — everything
  expressible before — keeps the backend's own solar column, bit-identical.
- **Down-looking θ_o in roughly (88°, 90°) now emits a `UserWarning`** where the old
  89.5° schema bound accepted it silently. Results-neutral: no shipped scenario or
  golden baseline is in that band (the existing set tops out near 75°), so no computed
  number moves — only the warning surface.
- **Results-affecting (unreachable configurations only): the collocated
  "no viewing triangle" carve-out is retired (guardrail G4, Rule 27).** An
  equal-altitude scene that carries *any* separation — a lab bench with
  `geometry.target_range_m`, a tower pair with `geometry.ground_range_m` — now
  resolves the full horizontal triangle through the central-angle form
  (θ_o = π/2 + φ/2, real `slant_range_m` / `ground_range_m` / `eta_rad` /
  `incidence_angle_rad`) instead of publishing θ_o = 0 with three `None`s. Only
  *coincident* endpoints (equal altitudes, no separation at all) have no path; they
  publish θ_o = π/2 rather than the old nadir default of 0. Direction and magnitude:
  θ_o moves by up to π/2 rad for such scenes and the range/angle outputs change from
  `None` to metre-accurate values (e.g. two 30 m towers 8 km apart: θ_o = 90.036°,
  slant = 8000.0 m). No golden baseline or shipped scenario changes value. One
  reachable composition changes *outcome* rather than value: an equal-altitude scene
  over a real atmosphere (e.g. `sensor_altitude_m = target_altitude_m = 0` with
  `atmosphere.model = "simple"`) is now classified `level`, where it previously
  integrated a zero-length column. On `simple` it is served by the Phase-2
  constant-altitude arm (A5); on any other backend it raises the capability error.
  That is the intended consequence of retiring the carve-out: a degenerate
  zero-length column was never a substitute for a horizontal path.
- **`no_atmosphere` no longer rewrites `h_tgt` to 0 on a non-down-looking path.**
  The historical override (the no-atmosphere arm never integrates a column, so the
  only consumer of `h_tgt` was the Earth-limb intercept check) is kept verbatim for
  every down-looking scene — bit-identical results — but on an up-looking or level
  path it would fabricate an `(h_sensor, h_tgt, θ_o)` triple that violates the new
  altitude/hemisphere invariant. The real target altitude is kept there instead, and
  the intercept check reads the true segment.
- **`LineOfSightGeometry.intercepts_earth` reports a bad input as a bad input.** An
  altitude/zenith combination that admits no viewing triangle at all (e.g. a
  down-looking θ_o paired with a sensor *below* the target) previously fell into a
  degenerate branch and answered `True` — "intercepts Earth". It now raises,
  naming the contradiction and the ray's perigee altitude. Consequence worth
  knowing: for a LOS that carries `h_sensor`, a genuinely Earth-intercepting chord
  is now caught one layer earlier by the horizon guard, which classifies it as a
  limb-like transit (its tangent depression is hundreds of km). The `no_atmosphere
  (space)` Earth-intercept precondition is unchanged and still permanent; only the
  validator that fires first has moved.
- **Up-looking and level atmospheric paths fail — when they fail — at
  `AtmosphereStage`, with one actionable error.** A ground→air scene previously
  surfaced whatever the configured backend happened to say (a `ZENITH_CEILING`
  bound, a "looking-up configuration" message). Phase 1 replaced that with a
  single pending-capability `ParameterBoundsError`; Phase 2 (above) turned it
  into a **backend-capability** error, raised only when the configured backend
  cannot serve the topology. On `atmosphere.model = "simple"` the scene now
  computes. The error names what *is* supported (simple for any endo path; any
  backend for a wholly-vacuum path). The matrix's
  `test_sensor_below_space_target_raises` negative path moved with it.
- **GUI: the Parameter Editor edits every configuration at once, and can make a
  parameter configurable (owner UX round, 2026-07-26).** Opened on a **configured**
  parameter in a study, the *Edit — &lt;dotpath&gt;* dialog now shows **one seeded value box
  per configuration** — accent chip, name, editor, unit, in set order — instead of one
  box for the displayed configuration. Apply commits the whole column in a single
  `set_values(..., unit=)` call recorded as one undo step; a rejected value names the
  offending configuration, commits nothing, and keeps the dialog open. Opened on a
  **shared** parameter it offers *Configure across configurations…*, which expands the
  dialog in place into the same boxes and — only on Apply — promotes the parameter and
  writes the typed values as one atomic `configure(dotpath, values, unit=)` call, so
  Cancel leaves it shared and one undo returns it there. A single-configuration session
  gets the existing actionable hint naming `Edit → Configurations…`, never a silent
  no-op. The single canonical preview becomes a per-configuration one
  (`= MWIR: 3.5 um · LWIR: 8 um`), and the Tolerance section gains a one-line note that
  a tolerance is shared across configurations (ADR-0010).
- **API: `ConfigurationSet.configure(dotpath, values, *, unit=None)`.** `unit=` reads
  every supplied value in the caller's unit and converts once at the boundary, exactly
  as `set_values(unit=)` does — so a caller can promote a parameter *and* set its
  per-configuration values atomically in the unit the user typed. Only meaningful with
  explicit `values`; passing it without them is refused with an actionable error rather
  than ignored. A rejected value configures nothing. Results-neutral.

### Changed
- **GUI: the red "C" now sits immediately right of the parameter name** (owner request).
  In per-stage form fields the badge moved from after the value box to the slot between
  the label and the value box (its space is reserved when hidden, so configuring a
  parameter never reflows the row); in the parameter tree it moved from a decoration icon
  on the left of the name to a painted glyph just after the name text.
- **GUI: the configuration manager's grid-points fields say what they set.** The shared
  field, the *Grid points* column heading, and every per-row box now carry a tooltip
  stating that the number is the count of **wavelength samples** in that configuration's
  spectral evaluation grid (which spans its own `filter_min_um → filter_max_um`), that a
  blank row inherits the shared value, and that RADIANT's default is 500.

### Removed
- **`radiant.atmosphere.exo_target.evaluate_with_exo_target` and
  `radiant.atmosphere._uplooking_guard`** (ADR-0011 guardrail G4 / Rule 27 — a
  generalization retires its carve-outs in the same PR). The Gap-95 exo-altitude
  target is now the down-looking arm of `atmosphere/topology.py` written as the
  segment composition it always was, and the Phase-1 blanket refusal of
  up-looking/level paths is replaced by direction dispatch plus a *capability*
  refusal that names what each backend can serve. **Not results-affecting**: the
  exo fold is bit-identical over a 3 124-configuration differential proof
  (exact `==` on all nine `AtmosphericQuantities` fields, simple and tabulated
  backends).
- **GUI: the stand-alone *Configured values* dialog.** Its per-configuration table is now
  the Parameter Editor's per-configuration mode (above), so the badge / *Edit configured
  values…* route opens that one dialog instead. No capability is lost — per-configuration
  editing is reachable from exactly the same places, plus the tree and every stage form —
  and the behaviour it guaranteed (display units, whole-column atomicity, the
  configuration-named rejection) is asserted against the editor dialog by the same tests.

### Added
- **CLI: studies run and validate from the command line (multi-configuration Phase 5 —
  close-out).** `radiant run study.yaml --configuration NAME` evaluates one named
  configuration of a study config file: `ConfigurationSet.load` → `sensor_for(NAME)` →
  the ordinary run path, with the configuration named in every output form (a
  `Configuration:` header line in text, a `configuration` key in `--format json` and in
  the `--output` / `--provenance` files, and a leading `configuration` column in
  `--format csv`). Plain config files are byte-for-byte unaffected in all four forms.
  `radiant validate study.yaml` now validates **every** configuration through
  `ConfigurationSet.validate_all()` and prints one line each — `ok` with that
  configuration's band (µm) and grid-point count, or `ERROR` with the actionable
  what-line — exiting non-zero if any failed, so one configuration's failure never hides
  another's. This replaces Phase 2's blanket refusal of study files: `radiant run` still
  refuses a study **without** `--configuration`, now with a message naming every
  configuration and the flag (the study's `active` designation is GUI display state and
  is deliberately not honored by scripting), and `--configuration` against a plain config
  file is refused the same way. `--set` overrides the materialized configuration on
  `run`; on `validate` it edits the shared base and refuses a configured dot-path (one
  value has no unambiguous target across N configurations). `--wavelength-min/-max` are
  refused with `--configuration` (each configuration spans its own resolved band,
  ADR-0010 D-F); an explicit `--wavelength-points` overrides the study's own count while
  the flag's default no longer silently does. No API change and no computed result
  changes.
- **GUI: studies are a first-class document — YAML view/editor, console `configs`, and
  persistence polish (multi-configuration Phase 4e; completes the GUI half of the
  capability).** The right-rail **Edit Config (YAML)** modal now shows and edits the
  **whole study**, `configurations:` section included, and re-parses it through
  `ConfigurationSet.load` on Apply: a valid edit — including an edit to a configured
  value inside the section — becomes the new session state exactly as `File → Open`
  would, while an invalid one leaves the session untouched and renders the loader's own
  what/why/action (which already names the configuration and the parameter). Because
  Apply goes through the ordinary loader, adding a section by hand turns a plain session
  into a study and deleting one collapses a study back to a plain session. The scripting
  console binds **`configs`** — the live `ConfigurationSet`, the same object the selector,
  the configuration manager, and Save write through — beside `sensor` (which stays the
  displayed configuration), and its **Refresh** now re-adopts that whole document instead
  of refusing to act on a study. The window title carries `(N configurations)` for a
  study; switching the displayed configuration deliberately does **not** mark the document
  dirty (`active` is view state, captured silently at save time) while every model change
  does. A single-configuration session is unchanged in every one of these surfaces: same
  YAML text, same file format, same title, same console behaviour. No computed results
  change.
- **GUI: the configuration manager can set a study's shared spectral grid points**
  (CU-213). A *Shared grid points* field above the rows writes
  `ConfigurationSet.set_wavelength_points(None, n)` — the number every blank per-row
  override already named in its placeholder, and until now editable only from the YAML
  editor or the console. It reverses with the rest of the manager transaction in one undo
  step. Changing it changes each configuration's spectral sampling density and therefore
  its computed metrics, exactly as editing `_radiant.wavelength_points` in the YAML always
  did; the default is untouched, so no existing result moves.
- **GUI: the Performance stage shows every configuration side by side (multi-configuration
  Phase 4d).** In a study, each metric group card becomes a **metric × configuration
  matrix** — the same groups in the same order, plus one column per configuration in set
  order, headed by the configuration's name and the accent chip it carries in the
  selector band (both themes). Cells are **plain values with their registry units** and
  nothing else: no delta column and no best-per-metric mark in the GUI — those stay on
  the scripting `ConfigurationSet.compare` / `compare_configs` surface. A metric a
  configuration did not compute shows `—`, never zero; a configuration that **failed**
  keeps its column, reads *not evaluated*, and carries the error's what-line on its
  header while the other columns keep their real numbers; a configuration that warned
  gets a marker pointing at its Messages entries. Everything renders from the retained
  evaluate-all pass, so switching the displayed configuration re-marks the columns
  without re-running anything. A single-configuration session is unchanged — no columns,
  no headers, no chips. No computed results change.
- **GUI: configuration manager — define how many configurations a study has and name
  them (multi-configuration Phase 4c).** A new `Edit → Configurations…` dialog (also on
  the gear at the right end of the selector band) creates, duplicates, renames, removes,
  reorders, and picks the baseline configuration, one `ConfigurationSet` call per action.
  Each row shows the configuration's accent chip and name, a baseline marker, its
  spectral **grid-point** override (blank inherits the study's shared default, whose
  value and meaning the blank row states), and a live **status** from
  `validate_all()` — `OK`, or the failing configuration's error line with its full
  what/why/action on hover; the status is resolve-only, so the dialog never runs physics.
  Every refusal — a ninth configuration, a duplicate or empty name, removing the last
  configuration — is the API's own actionable message rendered inline, and removing the
  displayed configuration moves the display to the first survivor after a confirmation
  that states it. The dialog edits a private copy and applies on OK, so Cancel changes
  nothing and the whole transaction is **one** undo step that restores the prior
  membership, order, configured value columns (including a removed configuration's
  values), grid overrides, and baseline/active designations. This is also how a plain
  single-model session becomes a study: adding a second configuration reveals the
  selector and makes Save write the `configurations:` section. No computed results
  change.
- **GUI: the all-configurations value table now works in the parameter's chosen display
  unit** (CU-211). Setting a row to `km` in the Parameter Editor and then opening that
  configured parameter's table shows and accepts kilometres, instead of silently
  switching back to the schema input unit; the conversion happens once at the API
  boundary and the whole column still commits atomically.
- **`ConfigurationSet.wavelength_points(config=None)`** (CU-210) — read the spectral
  grid point count back: the shared default in force with no argument, or a named
  configuration's override (`None` when it inherits). Its write counterpart
  `set_wavelength_points(config, n)` now also accepts `n=None` to **clear** an override
  (or the shared default), so an editable setting has a way back.
- **`Sensor.wavelength_points`** — read-only property exposing the sensor's spectral
  grid point count, the counterpart of `with_wavelength_points` and of the
  `_radiant.wavelength_points` config-file field.
- **`ConfigurationSet.set_values(dotpath, values, *, unit=None)`** (CU-211) — the dense
  whole-column write now accepts a unit, converting every value from the caller's unit
  at the API boundary exactly as `set_value(unit=)` does, without giving up
  validate-then-commit atomicity.
- **GUI: configure a parameter across configurations — red "C" badges, an
  all-configurations value table, and scoped undo (multi-configuration Phase 4b).**
  Any editable parameter can now be marked **configured** from its context menu in the
  all-parameters tree or on any per-stage form field: *Configure across
  configurations…* seeds one value per configuration from the current shared value
  (one `ConfigurationSet.configure` call). A configured parameter carries a small red
  **C** everywhere it appears, whose tooltip lists every configuration's value with
  units in set order (`MWIR: 3.5 um · LWIR: 8 um`). *Edit configured values…* opens a
  compact table — one row per configuration with its accent chip, a schema-driven value
  editor, and the unit — that commits the whole column in one `set_values` call, so a
  rejected value leaves the set untouched and the rejection names the offending
  configuration. *Un-configure* always keeps configuration #1's value and states that
  value, with its unit, in the confirmation before collapsing the column. Editing a
  configured parameter inline while a configuration is displayed still changes that
  configuration only (ADR-0010 D-8) and is now **undoable**: configure, un-configure,
  table edits, and per-configuration edits all round-trip through Edit → Undo/Redo,
  restoring both the value and the scope it lives in (the Phase-4a "per-configuration
  edits are not undoable" caveat is gone). **A single-configuration session is
  unchanged** — no badges, no reachable dialogs; the configure action answers with an
  actionable message pointing at the (Phase 4c) configuration manager rather than
  doing nothing. No public API surface changed and no computed results change.
- **GUI: master configuration selector and evaluate-all session model
  (multi-configuration Phase 4a).** The desktop GUI's session is now a
  `ConfigurationSet` rather than a single `Sensor`. Opening a study file (one with a
  `configurations:` section) loads every configuration and reveals a compact selector
  band above the signal-chain strip; picking a configuration displays it across all
  nine stage views, the input forms, the readouts, and the right rail, each
  configuration carrying a stable accent colour from the theme token set (light and
  dark). The background evaluate loop became evaluate-all: one pass runs every
  configuration with the displayed one first, per-configuration warnings appear in
  Messages prefixed with their configuration name, and a configuration that fails
  while it is not displayed is a named Messages entry rather than a modal — the rest
  of the study still evaluates. Saving a study writes the whole study document.
  **Opening a plain config file is unchanged**: no selector is shown, the file saves
  in exactly the format it did before, and the session behaves as it always has. No
  computed results change. Still to come: per-parameter `configure` and the red "C"
  badge (4b), the configuration manager dialog (4c), per-configuration Performance
  columns (4d), and the study YAML view / console `configs` object (4e) — in this
  phase the selector is read-only over whatever the loaded file defines, the YAML
  editor and console Refresh state that they are single-configuration surfaces
  instead of silently collapsing a study, and per-configuration edits are not yet
  undoable.
- **`ConfigurationSet.clone()`.** Returns an independent copy of a set — cloned base,
  copied configured table, wavelength-point overrides, and `active`/`baseline`. The
  set-level counterpart of `Sensor.clone()`, and what lets the GUI hand its worker a
  private snapshot; a copy rebuilt from the public accessors would lose the
  wavelength-point overrides (CU-210).
- **Per-configuration warning attribution and `ConfigSetRunResult.summary()`
  (multi-configuration Phase 3).** `ConfigurationSet.evaluate_all` now evaluates each
  configuration inside its own warning-capture window and records the warnings it
  raised on the new `ConfigRun.warnings` field (`tuple[str, ...]`, formatted
  `"<Category>: <message>"` — the same rendering the GUI evaluation worker shows). A
  warning raised by configuration X is attributed to X and to no other, including on
  configurations that then failed. Captured warnings are also re-emitted through
  `logging` (`radiant.api.config_set`), so nothing is dropped; they are not re-raised
  into the caller's warning filters. New on `ConfigSetRunResult`: `warnings`
  (name → messages, quiet configurations absent), `n_warnings`, and `summary()` — a
  plain-text triage view, one line per configuration, with every metric value carrying
  the unit the metric registry declares for it and an uncomputed metric omitted rather
  than zero-filled. No computed results change.
- **Config format: the `configurations:` structured section, and
  `ConfigurationSet.load` / `save` / `to_yaml` (ADR-0010 D-D, multi-configuration
  Phase 2).** One config file is one study: today's shared parameter document plus a
  `configurations:` section carrying names (1–8), `active`/`baseline`, optional
  per-configuration `wavelength_points`, and the dense configured table (dot-path →
  one value per configuration). Every section violation raises `ConfigError` naming
  the config file, the configuration, and the parameter — list-length mismatch (never
  padded), duplicate names, more than 8, unknown dot-path (did-you-mean preserved), a
  dot-path in both the shared body and the section, a non-member `active`/`baseline`.
  Configured file-path values relativize and resolve against the config file's
  directory exactly like shared ones (CU-177). **A config file with no
  `configurations:` key is byte-for-byte the previous format** and loads unchanged
  everywhere; a section-bearing file loaded through `Sensor.load` / `from_yaml` /
  `from_dict`, a bare `load_config`, or the CLI (`radiant run` / `validate`) now
  raises an actionable "load it with `ConfigurationSet.load`" error instead of
  running one study's shared body (Rule 17). New keywords on the loaders/writers:
  `Sensor.from_yaml/from_dict/load(..., sections_out=)` and
  `Sensor.save/to_yaml(..., extra_sections=, validate=)`. No computed results change.
- **`Sensor.set(..., source=)` / `set_many(..., source=)`, `Sensor.inputs()`, and
  `Sensor.resolve()` (CU-208).** Three additive, back-compatible public seams:
  `source=` sets the provenance **label** recorded with an input (the provenance
  class stays `USER_SET`; defaults are unchanged), `inputs()` returns a read-only
  snapshot of the explicitly-set inputs in input units, and `resolve()` is a public,
  idempotent ensure-resolved surface returning `self`. `ConfigurationSet` uses all
  three instead of reaching into `Sensor` internals. No computed results change.
- **`ConfigurationSet` — up to eight named configurations of one modeling problem
  (ADR-0010, multi-configuration Phase 1).** New public api surface
  `radiant.api.ConfigurationSet` (plus `ConfigSetRunResult`, `ConfigRun`, and the
  `ConfigSetError` error class): a shared base `Sensor` plus a dense table of
  *configured* parameters carrying one value per configuration (CODE V zoom
  semantics). `configure`/`unconfigure`/`set_value(s)` move a parameter between the
  shared and per-configuration stores; `sensor_for(name)` materializes a
  configuration as an isolated `Sensor` (configured values carry provenance
  `source="config:<name>"`); `validate_all` resolves every configuration without
  running physics; `evaluate_all` evaluates all of them active-first with
  progress/cancel support and per-configuration failure capture; `compare` adapts a
  run into the existing `compare_configs` matrix. Persistence (`load`/`save`/
  `to_yaml`) lands in Phase 2. No computed results change — a single-configuration
  set is observably identical to a bare `Sensor`.
- **`Sensor.with_wavelength_points(n)`.** Returns a clone evaluated on *n* spectral
  grid points over the same resolved band — the supported way to vary grid density
  after construction (previously constructor-only). Raises `ApiValidationError` for
  `n < 2`, matching `Sensor.load`'s check on `_radiant.wavelength_points`. Backs the
  per-configuration `wavelength_points` of `ConfigurationSet` (ADR-0010 D-F).
- **ADC↔well match diagnostics (Windows finding 10).** `ReadoutStage` now publishes
  three read-only outputs — `adc_full_scale_e` (`(2^bits−1)·gain`),
  `matched_gain_e_per_dn` (`full_well / 2^bits`), and `adc_well_match_ratio`
  (`adc_full_scale / full_well`; 1.0 = matched) — so the relationship between
  `gain_e_per_dn`, `adc_bits`, and `full_well_capacity_e` is visible in the GUI and
  scripting. An **egregious** mismatch (ratio outside 0.1–10) additionally emits a
  `UserWarning` pointing at the matched gain. The three parameters stay **independent
  inputs** — `gain = full_well/2^bits` is the matched-ADC design target, not a physical
  law (non-matched ADCs are legitimate), so gain is not derived. No computed results
  change; documented in `RADIANT_Detector_Complete.md` §6.

### Removed
- **GUI: the Source tab no longer shows the target shape/dimensions/orientation
  editor (Windows finding 14).** Target extent is geometry content
  (`geometry.target.shape*`, geometry-first / Rule 10): the shared shape panel is
  edited on Geometry → Schematic only, and the Source stage keeps only the
  radiometric target properties (temperature, emissivity, contrast reference,
  scene declaration). The user-visible duplicate was removed by the GT-0
  Source-screen rework (2026-07-16, previously unrecorded here); this entry also
  covers deleting the now-dead `target_shape` composition flag and its mount
  machinery so the duplicate cannot silently return. All `geometry.target.*`
  parameters remain fully editable from Geometry (and the parameter tree).

### Changed
- **GUI: Tools → "Compare Configurations…" is now "Compare Config Files…"** (CU-214).
  The item compares the live config against config **files on disk**; since the
  multi-configuration work landed, a bare "configuration" means a member of one study's
  configuration set (managed by `Edit → Configurations…`, compared on the Performance
  stage's new columns), so the two menu items no longer use one word for two things. The
  dialog's window title moves with the label; behaviour is unchanged.
- **GUI: the Performance screen is the grouped metric readout (Windows finding 12 +
  owner redesign 2026-07-25, two rounds).** Replaces the flat single-column readout
  ("wall of text") with one clean page: a compact Compute toggle row (Gap 96,
  checkbox order matching the sections — geometry first) above one themed card per
  metric group — *Sampling / geometry*, *Spatial / MTF*, *Radiometric*,
  *Interpretability*, *Saturation* — with **human metric labels** ("GSD
  (cross-track)" instead of `gsd_cross_track_m`), rows in physics order, values with
  registry units, and hover-revealed pins. The system-MTF and MTF-budget plots no
  longer render on Performance (owner decision; both remain on the Optics MTF tab).
  Presentation-only: which metrics compute, their values, and their units are
  unchanged.
- **The desktop GUI stack is now a base dependency (owner decision 2026-07-24).**
  `PySide6`, `matplotlib`, `qtconsole`, and `openpyxl` moved from the `[gui]`
  optional-extra into base `dependencies`, so a plain `pip install radiant` ships a
  runnable `radiant gui` with no extra install step (Windows first-deploy note: the
  GUI packages were not being installed). The core library still imports and runs
  without constructing any Qt object (the GUI is import-time-lazy). `radiant[gui]`
  is retained as a no-op back-compat alias.

### Fixed
- **Reference data now ships inside the package (Windows first-deploy finding 5).**
  The bundled reference-data tree (emissivity / detector-QE / solar CSVs and the
  MODTRAN-derived atmosphere NPZ library) moved from repo-root `data/` to
  `src/radiant/data/tables/` and is included in the wheel via
  `[tool.setuptools.package-data]` + `MANIFEST.in`. Previously a non-editable
  `pip install radiant` shipped **no** reference data (the loaders resolved a
  repo-root path that does not exist in an installed package), so material /
  detector / solar / shipped-atmosphere lookups failed off a clean install. The
  three loaders (`radiant.data.library`, `radiant.atmosphere.loaders`, the GUI
  Browse picker) now resolve the tree relative to their module (Rule 30). The
  atmosphere-library build script writes to the new location. No computed results
  change. OPERATING_MODEL §6 gains a carve-out so the data-tree manifests may live
  beside the data (Rule 26).

### Added
- **Version/build provenance is now visible (WS-A3, Windows first-deploy report).**
  `radiant --version` prints the package version, the on-disk **load path** the
  `radiant` package was imported from, and (when that path is a git checkout) the
  short commit SHA + dirty flag. The GUI window title gains the same `vX.Y.Z (+sha)`
  label. New public helper `radiant.api.build_info.build_info()`. This makes a
  stale/wrong install — the root cause behind several "already-fixed but not visible"
  findings — a glance instead of a guess. `--version` output format changed (was
  Click's bare `radiant, version 0.1.0`).
- **Temperature input in K / °C / °F (Windows finding 13).** Temperatures remain
  canonically Kelvin, but may now be *entered* in Celsius (`degC`) or Fahrenheit
  (`degF`) via the unit-aware `Sensor.set(..., unit=...)` boundary and the GUI
  parameter-editor unit dropdown (which auto-offers them for any Kelvin parameter,
  e.g. `source.target.temperature`, `detector.detector_temperature_K`). Implemented
  as a new affine-conversion table in `radiant.core.units` (`_AFFINE_CONVERSIONS`);
  `convert` / `inverse_convert` / `units_for` / `input_units` / `targets_for` now
  cover offset units. Canonical values and computed results are unchanged (Rule 2 —
  conversion happens once, at the input boundary).
- **GUI: Readout acquisition controls (Gap 102).** The Readout stage's Inputs
  form gains grouped sections for TDI (`readout.n_tdi` / `tdi_mode` /
  `tdi_misalign_pixels`), co-adding (`n_coadds` / `coadd_mode`), on/off-chip
  binning (x/y), and frame timing (`readout.frame_period_s` beside the shared
  integration time) — previously reachable only via the parameter tree, YAML,
  or scripting. The frame-timing stage outputs (`frame_period_s`,
  `frame_rate_hz`, `duty_cycle`) now carry display units in the Outputs
  readout (they rendered as bare numbers since their introduction). No
  computed results change.
- **Frame-rate / duty-cycle timing (RADIANT_Conventions.md §4).** New parameter
  `readout.frame_period_s` (seconds; default `0.0` = unset) stores the frame
  period independently of `spectral_integration.integration_time_s`.
  `radiant.readout.frame_timing.compute_frame_timing` derives the frame rate
  (`1/frame_period`) and duty cycle (`t_int/frame_period`); `ReadoutStage`
  publishes `frame_period_s` / `frame_rate_hz` / `duty_cycle` /
  `frame_period_defaulted` in `stage_outputs["readout"]`. An unset frame period
  defaults to `t_int` (duty cycle 1.0, continuous readout — the prior implicit
  behavior, so existing results are unchanged); a duty cycle > 1 is rejected.
  Implements the previously-unbuilt §4 contract (assurance audit D1 / R4.1).
- **Boost-phase atmosphere families — targets to 100 km + off-nadir + airborne
  sensors (MODTRAN boost-ladder expansion).** The shipped interpolated library
  gains three midlat_summer families built from 17 new real MODTRAN 6 runs
  (G7–G11, I1–I9, H5, J1–J2): `midlat_summer_boost_ladder/` (space sensor ×
  target 0–100 km, nadir), `midlat_summer_boost_offnadir/` (× LOS zenith
  0/45/60°), and `midlat_summer_sensor_ladder/` (airborne→space sensor
  3 km–GEO, ground target). Each boost family closes to a synthesized exact
  100 km vacuum rung (τ ≡ 1, present at every zenith), giving continuous τ_up
  from the ground through the Gap 95 exo handoff. New `interpolation_axes`
  defaults: `sensor_altitude_m` → sensor ladder,
  `sensor_altitude_m,target_altitude_m,path_zenith_rad` → off-nadir. A single
  `interpolated` config can now sweep `geometry.target_altitude_m` 0→300 km at
  any zenith ≤ 60° with monotone τ_up and no geometry warnings.
- **Real downwelling sky radiance for midlat_summer** (H5 up-looking 48.2° run),
  attached to all midlat_summer families and the `profiles/midlat_summer.npz`
  profile — the zero-downwelling default no longer applies to this profile
  (three profiles with no H-run still load zero).

### Changed
- **Readout parameter display units (findings 7, 9).** `readout.read_noise_e_rms`
  now carries the unit `e-` and `readout.gain_e_per_dn` the unit `e-/DN` (both
  were dimensionless `""`, shown as "(none)" in the parameter editor). Display-only
  — the canonical values and all computed results are unchanged; the gain unit now
  matches the `stage_outputs["readout"]["gain_e_per_dn"]` output unit that already
  reported `e-/DN`. New registry unit `("e-/DN","e-/DN")` in `core/units.py`.
- **`readout.full_well_capacity_e` upper bound raised `1e8` → `1e12` e- (finding
  11)** so high-dynamic-range focal planes can be configured. Default and all valid
  existing values are unchanged.
- **Results-affecting: EE_box (ensquared energy) is now cell-area-overlap
  weighted, removing an O(dx) box-edge bias that over-stated point-source /
  sub-pixel signal (CU-188).** `EffectivePSF.ensquared_energy` previously gave
  every PSF sample within `floor(half_width/dx)` full weight and only tapered a
  fractional overshoot cell — so at critical sampling (integral half-width, the
  common case) the box-edge cells were counted at full weight instead of half.
  The box now weights each cell by the fraction of its area inside the box
  (`w(d)=clamp(H−d+0.5,0,1)`). EE_box for an unaberrated Airy at Q=2 now matches
  the analytic 0.177327 to ~3e-4 at the default `psf_oversample=8` (was 0.219,
  +24 %). **Effect:** point-source and sub-pixel SNR **decrease** and NEDT
  **increase** by roughly the old EE_box over-statement (e.g. GUI baselines 1.1
  SNR −7.4 % / NEDT +8.0 %, 1.3 SNR −5.3 % / NEDT +5.6 %); extended-scene
  results (EE_box ≡ 1) are unchanged. Two GUI-baseline snapshots regenerated.
- **File-path parameters are now stored portably — relative to the config's own
  directory instead of as an absolute machine path (CU-177).** Parameters that name a
  data file (`source.target`/`background` emissivity/reflectance/albedo/brightness-
  temperature/radiance/intensity paths, `detector.qe_table_path`, `optics.zernike_file`,
  the three `atmosphere.tabulated_*_file`) carry a new `ParameterDef.is_file_path` flag;
  `Sensor.save` / `save_config` write their value relative to the output YAML directory
  (forward-slashed, cross-platform), and `load_config` resolves it back to absolute against
  the source YAML directory. A config referencing a repo-internal data file is now portable
  across checkout locations, machines, and OSes. New optional `Sensor.to_yaml(relative_to=...)`
  kwarg exposes the same relativization for string exports. Back-compatible: configs written
  before this change (absolute paths) still load unchanged; system/staging paths (MODTRAN
  binary, cache/data dirs, tape7/flux) are unaffected. User-observable: the shipped `1.1` and
  `4.3` GUI baselines now store `../…`-relative data-file paths and load on any checkout.
- **The detector-oversampling (Nyquist > diffraction cutoff) diagnostic is now a
  `logger.debug` note instead of a `logger.warning` (CU-166 approach 4).** Oversampling
  (Q > 2) is a valid, documented sampling regime — the operative fact is already surfaced
  as structured status (`q_center`/`q_min`/`q_max`, `sampling_regime_code`, `mtf_at_nyquist
  ≈ 0`), so it no longer emits a per-evaluate warning, per the zero-warnings-for-valid-
  scenarios bar. User-observable: scenario `6.4` (and any oversampled config) now evaluates
  warning-free. Not results-affecting (log level only; no metric changes). Completes the
  CU-166 chain-wide warning-site audit — of 42 warning sites, only saturation (genuinely
  actionable, kept) and this notice fired on valid shipped configs.
- **Example `nintendo.yaml` `source.scene_type` corrected `point_source` → `auto`.** The
  config declared a point source but the 2000 K target has no angular size, so the engine
  correctly derives an `extended` regime; the declaration tripped the (correct, kept)
  declared-vs-derived regime-mismatch warning. `auto` lets the engine infer, so the shipped
  example evaluates warning-free without weakening the actionable mismatch warning.
- **Results-affecting: 11 saturating GUI-baseline scenarios re-centered to a
  warning-free operating point, and all 34 `.gui.expected.json` baselines refreshed
  (CU-170 + CU-166 item iv; CU-175).** The shipped GUI baselines for `2.3, 3.3, 3.5,
  4.1, 4.4, 5.2, 5.3, 5.5, 6.1, 6.3, 7.4` captured a mid-sweep point that clipped the
  full well and/or the ADC. Each is re-centered on the GUI baseline only (the validated
  runner sweeps are unchanged): ADC-only clips get a well-matched `readout.gain_e_per_dn`
  (or, for `6.3`, `adc_bits` 14→21 so the verified `gain=1.0` and every noise term stay
  bit-identical); well clips additionally shorten integration time (`4.1` 4→1.5 ms,
  `5.2`/`5.3` 2→1 ms, `5.5` 5→1 ms). Direction/magnitude: these baselines now report
  unclipped SNR/NEDT (mostly higher SNR than the clipped values, ±small from added
  quantization noise). Separately, every baseline's snapshot was refreshed for (a) the
  CU-166 gate — `niirs` drops to N/A on out-of-envelope configs, with
  `performance.niirs.allow_extrapolated=true` opted in for the five NIIRS-headline
  scenarios (`1.4, 3.2, 3.3, 3.4, 5.1`) — and (b) post-2026-07-18 physics drift (Gap 38
  VNIR scattered-sky; CU-155/157/161 + Gap 94/95 MWIR/LWIR recalibration), which had
  never been re-snapshotted (e.g. `1.1` SNR 526→794, +51%, from the gas-band
  recalibration). `verify_gui_yaml.py` is now 34/34; 32/34 evaluate fully warning-free.
  `4.5` is deliberately **not** re-centered — its saturation is a photon-FPA charge-well
  check misapplied to a bolometric detector (Gap 101), documented in its walkthrough.
- **Results-affecting: NIIRS/IIRS is now N/A when outside the GIQE-5 calibration
  envelope (CU-166 approach 2; owner-ratified strict refusal).** When any GIQE-5 input
  (GSD 1.18–31.5 inch, RER 0.2–0.95, SNR 2–130) is out of range, the `niirs` metric is no
  longer emitted; `niirs_result` carries a result-typed `failure_reason` (new
  `GIQEResult.failure_reason`/`.applicable`), and the computed extrapolated value remains
  inspectable on the result object. New parameter `performance.niirs.allow_extrapolated`
  (default false) restores the previous behavior. Direction/magnitude: no numeric value
  changes; the metric disappears by default on out-of-envelope configs — which includes
  26 of 32 shipped scenario baselines (mostly SNR above 130) and the golden example
  (SNR ≈ 978); their stored GUI baselines are refreshed with the CU-170 pass. The
  `niirs_extrapolated` status metric is emitted in all cases. Real IR-calibrated IIRS is
  tracked as Gap 100.
- **PSF-path FFT fast paths — up to ~2.7× faster `evaluate()` on heavily-oversampled
  configs (CU-165).** Kernel convolution (`build_effective_psf`, `EffectivePSF.with_kernel`)
  now uses real-input FFTs with the exact even-grid shift-elision identity, and
  `EffectivePSF.mtf_1d` uses the projection-slice theorem (one 1-D FFT of the LSF instead
  of the full 2-D FFT). Same grid, same discretization, mathematically identical results —
  measured metric agreement ≤5e-16 relative (the CU-165 Q≈8 reference config drops
  97 s → 37 s; the golden config is unchanged at ≤1e-15). Not results-affecting.
- **Results-affecting: `E_sky_scattered` now uses the MODTRAN-derived effective
  single-scattering albedo `omega0_eff(lambda, aerosol)` (Gap 38 swap).** The simple
  model's diffuse scattered-solar sky irradiance replaces its internal
  extinction-weighted column omega_0 (which evaluated ~1.000 for space-sensor columns)
  with band-median values inverted from the real MODTRAN 6 flux tables (e.g. rural
  0.791/0.698/0.187 in VIS/NIR/SWIR). Direction and magnitude: diffuse sky irradiance
  DROPS toward MODTRAN parity in the reflective bands — band-integrated
  E_sky_scattered at theta_s = 30 deg falls ~21% (rural VIS) to ~77% (rural SWIR) and
  ~58% (urban VIS); scenes gain correct aerosol dependence (previously nearly
  aerosol-independent). In the MWIR the edge-extended SWIR value slightly RAISES the
  small sky-reflected term (mwir_leo_minimal golden: signal +0.60%, SNR +0.30% —
  golden updated in this change). L_path single-scatter is unchanged (still the
  internal omega_0 with the phase function). New module
  `radiant.atmosphere.omega0_eff`.
- **Shipped atmosphere library records full run geometry; geometry-mismatch
  warnings sharpened (boost plan §4.6 / CU-167 follow-through).** Every
  `data/atmospheres/` NPZ now records all five run-geometry fields (spectral
  arrays are byte-identical — no computed results change). Consequences a user
  can observe: an airborne-sensor query against the space-column zenith fan now
  warns instead of silently receiving the 100 km column; a solar zenith other
  than the runs' 30° now warns on interpolated families; a LEO/GEO sensor above
  a recorded at-TOA sensor is recognized as vacuum-exact and does NOT warn; and
  pure-thermal scenes (no declared solar geometry) adopt the recorded run sun
  instead of spuriously warning.

### Added
- **`radiant.api.geometry_modes` — public geometry input-mode manifest (CU-120).** The
  ADR-0006 family → mode → parameter structure (viewing V0–V4, solar S1–S3 + night,
  kinematics direct/circular: entry dot-paths, anchors, default doors, and provenance-based
  `active_mode_key` detection) is now owned by `radiant.geometry.mode_manifest` and
  re-exported through `radiant.api.geometry_modes` (the `metric_groups` precedent). The GUI
  Geometry screen consumes it instead of a hand-transcribed grouping and keeps only display
  labels. No results change.
- **`radiant.api.plot.plot_theme(dark=…)` context manager (CU-139).** A public seam that
  applies a dark or light matplotlib *chrome* theme (background/axes/text/ticks/grid) around
  figure production, so GUI/notebook callers can request a dark-styled `result.plot.*` figure
  without restyling it themselves. The GUI theme toggle now re-renders its stage plots through
  it, ending the bright-rectangle-in-dark-mode look. Data-series colours are unchanged.
- **`Sensor.resolved(dotpath)` and `Sensor.provenance(dotpath)` accessors (CU-105).**
  Structured, machine-readable passthroughs to the resolved parameter record — value,
  units, `provenance` (a `Provenance` enum), and source — replacing the need to parse the
  human-readable `Sensor.explain` string. The GUI now reads provenance through these.
- **Named unit-enumeration accessors on `radiant.api.units` (CU-109).** New public
  `units_for(canonical_unit)`, `input_units()`, and `targets_for(from_unit)` replace
  reaching into the underscored `_CONVERSIONS` registry, which is no longer re-exported
  from `radiant.api.units` (it stays private to `radiant.core.units`). The GUI unit
  selector and the `radiant convert` CLI now use these accessors. No results change.
- **Per-metric group selection for performance metrics (Gap 96).** Five new
  boolean parameters — `performance.metrics.radiometric`,
  `performance.metrics.spatial_mtf`, `performance.metrics.interpretability`,
  `performance.metrics.sampling`, `performance.metrics.saturation` (all default
  `True`) — select which metric families `PerformanceStage` computes and
  surfaces. Turning a group off stops the *computation* of its metrics (and any
  warnings they emit), not merely their display; hidden prerequisites are still
  computed via the metric dependency closure (enabling only Interpretability
  computes `snr`/`rer`/`gsd_*` for NIIRS but does not surface them). Saved in
  YAML and scriptable; the GUI Performance stage adds a "Metric selection" card
  of five checkboxes (one toggle ↔ one `sensor.set`). New public surface:
  `radiant.api.metric_groups` (`GROUP_PARAMS`, `METRIC_GROUPS`,
  `resolve_selection`, `group_of`) and `ChainState.without_metric`. **Not
  results-affecting**: the all-on default reproduces every existing metric
  exactly.
- **GUI: point-source intensity inputs on the Source instrument (Gap 98 D).**
  A new "Target — point source" tab exposes the point-intensity inputs
  (`point_intensity_temperature_K`/`_area_m2`/`_emissivity`, `_band_W_per_sr`),
  gated ON only for a declared `point_source` scene (schema `regime:point_source`
  tag); conversely the surface-radiance `source.target.temperature`/`emissivity`
  rows gate OFF for point-source (a point source is defined by intensity, not
  radiance × area). Completes Gap 98 (with the A/C engine fixes above).
- **Point-source intensity convenience inputs (Gap B).** A true point source
  (SDA object, star) is defined by radiant intensity `I(λ)` [W/sr/µm], not
  surface radiance × area. Two new opt-in ways to supply it without a CSV, both
  routing to the same `T7IntensityAtSource` (point-source regime):
  - **Blackbody emitter** — `source.target.point_intensity_temperature_K`,
    `point_intensity_area_m2`, `point_intensity_emissivity` →
    `I(λ) = ε·A·B(λ,T)`.
  - **Scalar band flux** — `source.target.point_intensity_band_W_per_sr`, taken
    as the in-band integral `∫ I(λ) dλ` [W/sr] over the filter band and modeled
    as spectrally flat within it.
  Mutually exclusive with each other, the CSV intensity path, and the
  surface-radiance (ε, T) path (actionable errors on conflict / zero area). New
  module `radiant.source.converters.point_intensity`. Not results-affecting for
  existing configs (all params default to their "not set" sentinel).
- **GUI: the Target-shape panel gains a Projected-area field, mutually exclusive
  with the shape dimensions.** When the shape library is `none`, the panel shows a
  scalar **Projected area** field (`geometry.target.projected_area_m2`); when a
  shape is selected it shows that shape's dimensions instead — never both. Shape
  and projected area are two ways to size the same target, so the GUI now enforces
  "one or the other" by construction (the engine's shape-wins precedence remains
  the backstop for raw configs that set both). Previously a shapeless target's area
  could be set only from the parameter tree.
- **GUI: the Geometry Schematic now shows the target's projected area (CU-168).**
  A leader-label pill by the target reads `A_t  <area> m²  ·  <n> px` (the pixel
  multiple is √A/range over the detector IFOV — the sub-pixel-vs-resolved cue),
  drawn whenever a target area is defined. Previously a target sized only by
  `geometry.target.projected_area_m2` (shape library = "none") drew a bare point
  marker, so a defined area was visible only in the parameter tree. Read verbatim
  from `stage_outputs["source"]`; no physics change.
- **Results-affecting (opt-in): MODTRAN flux-file downwelling on the tape7-import
  path (CU-157).** New parameter `atmosphere.modtran.flux_path` names a Block E
  spectral flux CSV (`*_flux.csv`) alongside `atmosphere.modtran.tape7_path`.
  When set, the run's ground-level DOWN irradiance feeds the sky-reflection
  terms — `E_sky_thermal` from the thermal band (≥ 4 µm) and `E_sky_scattered`
  from the reflective-solar band (< 4 µm) — superseding the Gap 81 zeros for
  flux-equipped imports (no more zero-downwelling warning). This raises reflected-
  sky background for low-ε / mixed emit+reflect targets on the MODTRAN-import
  path (e.g. E1 LWIR downwelling ≈ 24.6 W/m², VIS ≈ 124 W/m², previously 0).
  Only affects configurations that set `flux_path`; all existing scenarios and
  goldens (none set it) are unchanged. New `FluxImport` public class.
- **Exo-altitude targets over an atmospheric background (Gap 95).**
  `LineOfSightGeometry` now accepts any target altitude ≥ 0 m; a target at or
  above the atmosphere top (default 100 km — satellite, post-burnout booster)
  is served by every atmosphere backend with the exact vacuum target leg
  (τ_up ≡ 1, L_path_up ≡ 0, τ_sun ≡ 1) while the ground→sensor full column
  (τ_full_up, L_path_full) is retained for the background/noise branch —
  identical to a surface-target evaluation of the same backend. Implemented
  once, model-agnostically (`atmosphere/exo_target.py`), so single-column file
  imports work too. Previously these configurations were rejected at LOS
  construction. The 29–100 km band remains data-limited pending the boost-ladder
  run set (`docs/plans/MODTRAN_Boost_Ladder_Expansion_Plan.md`; 14 runs appended
  to the run matrix).
- **`InterpolatedAtmosphere` warns when non-axis query geometry is ignored
  (CU-167).** Querying a data set at a geometry the samples don't cover in a
  non-interpolated dimension (e.g. the nadir-only ladders at 45° LOS zenith) now
  emits a `UserWarning` naming the ignored field and the value actually served
  (~1°/1 m tolerance), instead of silently substituting the stored column; a
  recorded non-axis field that varies across sample points is refused at
  construction.
- **Airborne targets (h_tgt > 0) on the file-backed atmosphere paths (Gap 94).**
  (1) `InterpolatedAtmosphere.evaluate()` now serves elevated targets when the grid
  carries a `target_altitude_m` axis — two interpolator queries give the real two-leg
  split (target→sensor τ_up/L_path_up at `h_tgt`, ground→sensor τ_full_up/L_path_full
  at 0 m), which un-strands the shipped `data/atmospheres/midlat_summer_ladders/`
  family (0–29 km targets, 35 km–GEO sensors) for boost-phase / near-space scenarios.
  No extrapolation: targets beyond the grid hull are still refused loud.
  (2) New parameter `atmosphere.modtran.tape7_up_path`: a second target→sensor tape7
  (a MODTRAN run with H2 = target altitude) imported alongside `tape7_path`'s full
  column, enabling h_tgt > 0 on the tape7 file-import path. Surface-target results are
  unchanged on both paths (previously these configurations raised
  `NotImplementedError`). The no-sun-file collapse warning on both backends now states
  precisely what is aliased (τ_sun onto τ_up).
- **GUI: Browse… picker on path parameters.** The Parameter Editor dialog adds a native
  file/directory picker next to the value field for every `*_path`/`*_file`/`*_dir`
  parameter (e.g. `atmosphere.interpolated_data_dir`), so paths no longer have to be
  typed by hand. Commit still goes through the single validated `sensor.set` on Apply.
  An empty field's picker opens on the parameter's shipped-data home (`atmosphere.*` →
  `data/atmospheres/`, `detector.*` → `data/detectors/`, `source.*` →
  `data/emissivity/`), not the working directory.
- **`atmosphere.model = "interpolated"` works out of the box.** With
  `atmosphere.interpolated_data_dir` unset, the loader now defaults to the shipped
  library family matching `atmosphere.interpolation_axes` (`path_zenith_rad` →
  `us_standard_zenith_fan`; `sensor_altitude_m,target_altitude_m` →
  `midlat_summer_ladders`), with a logged notice; an explicit directory always wins and
  uncovered axes still raise the actionable error. Previously an unset directory always
  errored. Pointing `interpolated_data_dir` at a library ROOT (e.g. `data/atmospheres/`
  itself) now descends into the family folder matching the axes instead of failing with
  "found 0 NPZ files"; a directory with no matching family fails with the family
  subfolders listed.
- **`InterpolatedAtmosphere` accepts any query wavelength grid inside the stored
  spectral range (CU-156).** `build_state` linearly resamples the
  geometry-interpolated spectra onto the query grid (the `TabulatedAtmosphere`
  pattern) instead of requiring an exact grid match; out-of-range queries still fail
  loud. Sessions no longer need to run on the library's grid to use the shipped
  interpolated families.

### Fixed
- **GUI pinned-panel set persists across sessions (CU-115).** Pinning/unpinning a metric
  or stage-output card is now saved via `QSettings` and restored on the next launch (falling
  back to the default five-metric set when none is stored). Previously the pin set reset
  every relaunch.
- **`SpectralDataStore` warns on gross spectral extrapolation (CU-085).** When a curve
  covers less than ~80% of the requested band (> 20% constant-extrapolated), the store now
  raises a `UserWarning` naming the extrapolated fraction instead of a silent debug log;
  legitimate near-edge extrapolation (≤ 20%) stays quiet, so shipped scenarios remain
  warning-free. Also added test coverage for the digital-TDI noise-scaling branches.
- **MODTRAN cache key fingerprints the binary (CU-070).** The binary-invocation cache
  key now includes a hash of the MODTRAN executable's bytes, so upgrading the binary
  invalidates stale entries instead of silently serving the old version's results. The
  fingerprint is read from the executable's bytes (never by invoking it). Existing
  binary-path caches regenerate on first use.
- **MODTRAN state validates arrays before clamping (CU-071, Rule 17).** A tape7 import
  or cached array with transmittance well outside [0, 1] or a clearly-negative path
  radiance now raises an actionable `AtmosphereValidationError` (naming the likely
  unit-confusion / corrupt-file cause) instead of being silently snapped into range;
  only ≤1e-12 float noise is still clipped. Matches `TabulatedAtmosphere`.
- **GUI NEDT metric badge displays in mK (CU-108).** The NEDT badge now shows its
  canonical Kelvin value at a legible milli-Kelvin scale (0.045 K → 45 mK) via a single
  per-metric display-scale table in `metric_format`; the base unit still comes from the
  registry and the stored result is unchanged. Display-only.
- **GUI Geometry form re-syncs immediately on a parameter-tree edit (CU-121).** A
  geometry value edited in the left parameter tree now updates the Geometry Inputs/Schematic
  form at once, instead of only after the next debounced evaluation. Display-only.
- **GUI Parameter Editor: Current/Bounds rows follow the chosen unit after Apply
  (CU-111).** Applying a new unit without closing the dialog now re-expresses the
  informative Current and Bounds rows in that unit (e.g. `8 km`, not `8000 m`), so they
  agree with the unit combo. Display-only; the canonical value is unchanged.
- **GUI Source Outputs readout: `inf`/`None` render cleanly (CU-135).** An
  extended-target angular extent shows `∞` instead of `inf rad`, and an absent
  (`None`) background descriptor is skipped rather than shown as a backwards `— ` row.
  Display-only.
- **`inspect_result` summarises nested NumPy arrays (CU-113).** Arrays reached only
  via a stage-output object's own `repr` (tuples, dataclasses) are now collapsed to
  NumPy's summarized `[a, b, … y, z]` form instead of dumping hundreds of
  continuation lines — the shipped-example dump drops from ~3900 lines to ~230. The
  structural tree is unchanged; only oversized array bodies shrink.
- **`result.plot.psf()` default axes labelled "x/y (PSF samples)" (CU-136).** The
  default (non-grid) render's imshow extent is the PSF sample grid, not the detector
  pixel grid, so the previous "x/y (pixels)" labels were misleading for an oversampled
  PSF. Label-only; no data change.
- **Warning-free evaluate: four informational chain warnings reclassified (owner
  bar — a valid scenario evaluates warning-free).** These fired a `UserWarning`
  on every evaluate for a *documented, legitimate* behavior, so they polluted the
  GUI Messages panel and console on valid scenarios: (C) the detector
  temperature-inert dark-rate note (CU-081) is now `stage_outputs["detector"]
  ["dark_temperature_note"]` (rendered once in the Outputs readout); (A) the
  SimpleAtmosphere Ångström aerosol clamp beyond 5 µm (CU-088), (B) the
  extended-scene "background.* ignored" notice (ADR-0002 #15), and (D) the MWIR
  non-mixed model advisory (matrix §3.2) now log at `debug` (quiet by default,
  discoverable) instead of warning. Saturation warnings (full-well/ADC/pixel)
  stay as-is — they signal untrustworthy results. The 36 shipped configs now
  evaluate with zero non-deprecation warnings except genuine saturation. No
  physics/results change. (`docs/plans/Warning_Free_UX_Plan.md`.)
- **GUI: no more `qt.qpa.fonts` warning on launch (CU-169).** The theme's font
  stacks led with "IBM Plex Sans"/"IBM Plex Mono", which are usually not
  installed, so Qt logged `Populating font family aliases took … ms. Replace uses
  of missing font family "IBM Plex Mono" …` (and paid a ~170 ms cost) every
  launch. The generated stylesheet now names only families Qt actually has —
  unavailable design fonts are dropped from each stack (Qt was already falling
  back to the same next family, so the UI look is unchanged) — and a startup hook
  registers any IBM Plex `.ttf` bundled under `gui/assets/fonts/` (CU-103
  infrastructure) so the design font is used when shipped. First item of the
  Warning-Free UX campaign (`docs/plans/Warning_Free_UX_Plan.md`).
- **Point-source workflow: range fallback + actionable "no intensity" error (Gap 98 A/C).**
  (C) A `point_source` target no longer requires `geometry.target_range_m` to be set
  explicitly — `source.range_m` falls back to the GeometryStage-derived slant range
  (from altitude + zenith / orbit / site modes), so a point-source config that derives
  its range now runs instead of failing with "requires … range_m". (A) When a
  `point_source` target has no radiant intensity, the error now steers to the intensity
  inputs (`point_intensity_*` / `user_intensity_path`) instead of pointing back to
  `projected_area_m2` — a point source is defined by intensity, not radiance × area.
  Not results-affecting for existing configs (only enables previously-erroring ones).
- **Results-affecting: sub-pixel signal now derives `fill_fraction` from the target
  projected area (Gap 97).** In the `sub_pixel` regime the target's share of the
  pixel was taken from `source.target.fill_fraction` (default 1.0) and never from
  `geometry.target.projected_area_m2` — so a specified target area was silently
  ignored and the chain computed an extended-scene signal regardless of target
  size. `SourceStage` now derives `fill_fraction = A_proj / (Ω_pixel · range²)`
  (clamped to 1.0 on overfill) whenever a projected area is given and no explicit
  `fill_fraction` is set; an explicit `fill_fraction` is still honored. **Direction/
  magnitude:** only affects sub-pixel targets specified by area without an explicit
  fill fraction; for genuinely sub-pixel targets it *reduces* the target signal /
  contrast by the fill factor (e.g. a 24 m² target at 532 km, 15 µm/0.75 m optics:
  `contrast_snr` −84 → −17, a ~4.8× correction). Shipped scenarios are unchanged
  (1.1 maritime overfills → clamps to 1.0; 1.3 sets `fill_fraction` explicitly);
  no golden moved. New module `radiant.source.fill_fraction`.
- **GUI: File → New (or opening an incomplete config) no longer wedges the window.**
  A result belongs to the sensor that produced it; the stage center now drops its
  stored result when the sensor is swapped, so navigating to a stage after a swap
  shows the placeholder instead of re-populating the *stale* result against the new
  live sensor. Previously that re-render resolved the new (blank) sensor through the
  geometry viewer and crashed with `CoreValidationError: Circular dependency …
  ['optics.aperture_diameter_m', 'optics.focal_length_m', 'optics.f_number']`,
  leaving the whole window unusable behind a modal error (screens would not switch).
- **GUI: the geometry schematic's "unavailable" guard panel now recovers (CU-163).**
  A build failure during `show_result` still surfaces the actionable panel, but a
  later evaluate that builds cleanly rebuilds the canvas and re-enters schematic
  mode — one transient adapter error no longer disables the viewer for the rest
  of the session (previously the panel was one-way and required restarting the app).
- **GUI: night scenes no longer kill the geometry schematic.** With
  `geometry.solar_illumination = "night"` the geometry stage publishes the solar
  angles as `None`; the schematic adapter crashed on `float(None)` and the viewer
  degraded to its permanent "unavailable" panel. Night scenes now render with the sun
  (glyph, SUN→TARGET / SUN→GROUND vectors, drop lines, legend rows, and the θ_s / Δφ /
  phase angle annotations) simply absent; the sensor/target geometry is unchanged.

### Removed
- **Dead `readout.read_noise_is_post_cds` parameter (CU-077).** The parameter was never
  read by any code (no pre/post-CDS √2 scaling is modelled); removed from the schema.
  Enter `read_noise_e_rms` as the effective per-frame (post-CDS) value. The likewise-unimplemented
  `cds_1f_suppression` was doc-only and the `RADIANT_Detector_Complete.md` CDS table is
  corrected to match the code (neither factor is applied).
- **Dead source exports `CompositeTarget` and `SubPixelSource` (CU-084).** These two
  `radiant.source` classes had no live constructor in the chain (self-references only);
  removed along with their modules and tests. The rest of the former "shadow" source
  system (`ThermalSource`/`ReflectedSolarSource`/`CombinedSource`/`SurfaceMaterial`/the
  `resolvers`) is now the wired live source-object system and is unaffected.

### Changed
- **Structured errors for parameter bounds/enum rejection (CU-107).** The
  `ParameterSet` resolver now raises `ParameterBoundsError` (out-of-bounds) and the new
  `ParameterEnumError` (invalid enum choice) — each carrying a `what / why / action /
  context` payload (Rule 15) — instead of a flat `CoreValidationError`, so the GUI's
  actionable dialog can show why and how to fix, not just what. Both co-inherit
  `ValueError` + `RadiantError`, so existing `except ValueError` / `except RadiantError`
  and message-match callers are unaffected. No results change.
- **Cross-platform text I/O: explicit `encoding="utf-8"` everywhere (CU-149).** All
  text-mode `open()`/`read_text()`/`write_text()` call sites in `src/`, `scripts/`, and
  `dev_tools/` now pass `encoding="utf-8"`, so UTF-8 data/config files (containing `µ`,
  `°`, `⁻`) decode correctly on stock Windows (cp1252 locale) instead of raising or
  silently mojibaking. Ruff `PLW1514` (`unspecified-encoding`) is enabled to prevent
  regression. Not results-affecting on macOS/Linux (UTF-8 is already the default).
- **Cross-platform MODTRAN `binary_path` default (CU-151).** The default MODTRAN
  executable path now resolves to `modtran` on `PATH`, else the per-platform install
  location (POSIX `/usr/local/bin/modtran`; Windows `C:\Program Files\MODTRAN\modtran.exe`),
  instead of a hardcoded POSIX path that could never exist on Windows.
  `ModtranUnavailableError` names both a Windows and a POSIX example. Not
  results-affecting (the macOS default string is unchanged).
- **Pinned line endings via `.gitattributes` (CU-150).** A root `.gitattributes`
  (`* text=auto eol=lf` + `-text` for binary assets) keeps tracked text at LF in the
  working tree, so byte-level comparisons (golden baselines, checksummed reference data,
  MODTRAN decks) stay identical across macOS/Windows. The MODTRAN deck writers also pass
  `newline="\n"` explicitly. Not results-affecting.
- **NIIRS out-of-calibration is now structured status, not a per-evaluate warning
  (CU-166).** When a NIIRS/IIRS input falls outside the GIQE-5 calibration band the
  chain no longer emits a `UserWarning` (nor a `logger.warning`) on every evaluate —
  the condition is carried solely on the result (`GIQEResult.extrapolated`,
  `.warnings`, and the `niirs_extrapolated` metric), which was always available.
  This stops the warning flood in sweeps / Monte-Carlo / the GUI console (owner bar:
  a valid, nominally-operating scenario evaluates warning-free). No computed value
  changes. Up-front metric-applicability gating and the MWIR→IIRS/GIQE-5 routing
  question remain deferred, gated on the Gap 96 metric-selection decision.
- **Results-affecting (simple-atmosphere scenes with a reflected-sky term):
  SimpleAtmosphere downwelling sky emission rebuilt against the real MODTRAN 6
  up-looking runs (CU-155).** `E_sky_thermal` (and the legacy `L_atm_down`) now
  use a target-anchored emission temperature `T(h_tgt + 200 m)` with a
  flux-diffusivity exponent `D = 1.1` on the **vertical target→h_atm_top**
  column — the sensor's altitude and viewing zenith no longer enter (the old
  model evaluated `T` at `0.5·h_sensor`, clamping every space column to the
  216.65 K tropopause). Direction/magnitude: downwelling sky irradiance rises
  ~5× in LWIR and ~40× in MWIR for space-sensor columns, landing within
  [0.7, 1.4]× of the real H-run references (was 0.02–0.21×). Scenes with
  low-emissivity targets/backgrounds gain reflected-sky signal and background;
  high-ε scenes shift little (golden `mwir_leo_minimal`, ε = 0.95: signal_e
  +1.48%, SNR +0.74% — re-baselined per Testing §5.3 with provenance). The
  MWIR crossover anchor re-calibrated to the corrected thermal (ratio bound
  10 → 20 at 4 µm, intent unchanged).
- **Results-affecting (all simple-atmosphere configs): SimpleAtmosphere recalibrated against
  the real MODTRAN 6 run set (CU-161).** Two model changes: (1) the five-Lorentzian water fit —
  whose far wings made the MWIR water response ~5× too steep — is replaced by a 15-region
  curve-of-growth model `OD_h2o = k(λ)·w_eff^b(λ)` fit to the real water ladder (D4/A1/D5,
  H₂O ×0.5/×1/×2; sub-linear b in saturated bands, super-linear b≈1.3–1.75 in the LWIR
  continuum); (2) a **well-mixed-gas absorption floor** (CO₂ 4.3/15 µm, N₂O, O₃ 9.6 µm, O₂/CH₄)
  is added per region — the term whose absence made the old model attribute the MWIR CO₂ floor
  to water. The gas term also enters the single-scattering-albedo denominator (pure absorber),
  improving the ω₀ ≈ 1 space-column defect (Gap 38). **Direction/magnitude:** MWIR signals rise
  substantially where water over-absorbed (golden `mwir_leo_minimal` signal_e +147%, SNR
  616→968 — verified against a real-MODTRAN chain run at 869k e-/SNR 932: the old golden was
  2.3× too low, the new model is within 8% of truth); LWIR at-aperture spectra reshape
  (brighter 8–9 µm, darker 12–13 µm, toward the real anchors); dry/arctic profiles darken
  slightly. Cross-validated to ≤ ±0.012 band-mean τ on five non-calibration profile anchors;
  partial-column parity vs the real C-ladder tightens 3–5× (envelope now two-sided
  [−0.04, +0.05] band-mean). Goldens re-baselined per Testing §5.3: `mwir_leo_minimal.json`,
  Cell 28 NEDT/L_aperture, `test_chain_spatial` SNR (604.97→945.94), table-C envelope.
  Calibration generator: `scripts/fit_simple_atmosphere_gas_bands.py`; anchors pinned in
  `test_simple.py::test_cu161_water_ladder_anchor`.
- **Results-affecting (off-node zenith queries only): `InterpolatedAtmosphere` and the
  run-matrix family interpolator now interpolate zenith-angle axes in airmass sec(θ) space
  (CU-160).** Optical depth scales with airmass, so log-τ linear in sec(θ) is Beer-Lambert-
  exact between nodes; the previous linear-in-angle axis carried a measured −4% in-band τ
  bias at fan midpoints. Direction/magnitude: mid-angle zenith queries of angle-gridded data
  (e.g. the shipped `us_standard_zenith_fan/`) gain up to ~+4% band-mean τ, converging on the
  real MODTRAN holdout truth (45° from 30°/60°: −0.10% vs −4.07%). Node queries are unchanged.
  Zenith nodes ≥ ~88.8° are now refused (sec diverges at the horizon). Level-0 Beer-exactness
  tests + a committed-library holdout test pin the property.
- **Scenario 8.1 (off-nadir interpolation) upgraded to the real MODTRAN 6 zenith fan**, adding a
  holdout validation of the interpolation method itself: predicting the real 45° run from its
  30°/60° neighbors lands −4.07% (log-τ linear in angle) vs +6.84% for nearest-neighbor — and
  −0.10% when interpolated in airmass sec(θ) space, filed as CU-160 (also affects the shipped
  zenith-fan library's off-node queries). Figure/walkthrough regenerated from real data.
- **Scenarios 1.1 (MWIR maritime) and 6.2 (atmospheric intercomparison) upgraded from
  synthetic to real MODTRAN 6 data (2026-07-17 run set).** Both scripts auto-detect the
  staged real runs (synthetic remains a loud fallback); walkthroughs, figures, and results
  tables regenerated. The comparisons are now validated benchmarks: SimpleAtmosphere
  over-responds to profile water vapor (6.2: in-band MWIR τ spans 0.16–0.81 vs real
  MODTRAN's 0.42–0.57, near-exact at us_standard, ±40–60% at climate extremes; 1.1:
  maritime τ 0.239 vs real 0.432 → detection range understated by ~25%). Model behavior
  is unchanged — these are data/scenario updates; the SimpleAtmosphere accuracy findings
  are tracked in Gap 38/gaps.md and CU-155.
- **Gap 39 closed (A3 partial-column MODTRAN parity):** the chain's τ_up(h_tgt) is now
  pinned against real MODTRAN C-ladder goldens on every test run
  (`tests/integration/test_table_c_cells.py::TestTableCModtranPinned`), with the
  characterized envelope (simple optimistic by up to +0.13 band-mean τ at low altitude)
  recorded in the registry.

### Added
- **Shipped nominal atmosphere library (`data/atmospheres/`).** Committed NPZ spectra derived
  from the real 2026-07-17 MODTRAN 6 run matrix: six standard-profile nadir columns (tabulated;
  us_standard/tropical include real downwelling sky radiance from the up-looking H-runs), a
  us_standard LOS-zenith fan 0–60° (interpolated), and a midlat_summer sensor×target-altitude
  grid spanning 35 km–GEO × 0–29 km (interpolated, with a 40,000 km duplicate node so orbital
  sensors fall inside the hull). Slit-degraded to 5 cm⁻¹ FWHM (~4 MB). Users without a MODTRAN
  license now get real-radiative-transfer atmospheres via `atmosphere.model="tabulated"` /
  `"interpolated"`. Generator: `scripts/build_atmosphere_library.py`; design record:
  `data/atmospheres/MANIFEST.md`. Known limitation: the interpolated families require the
  session to run on the library grid (CU-156).
- **`ModtranFluxReader` — reader for MODTRAN 6 spectral flux CSVs (CU-154).** Block E irradiance
  runs export their direct/diffuse solar irradiance to a separate `*_flux.csv` (UP/DOWN/SOLAR per
  altitude level), a format nothing read before. `parse()` returns per-level native flux
  (`ModtranFluxOutput`); `to_radiant_units()` returns ground-level `(wavelength_um, e_direct,
  e_diffuse_down)` in W/m²/µm via the same ν² Jacobian as the radiance path. Validated on the real
  E1 run (LWIR direct beam = 0, downwelling diffuse ≈ π·B near surface, VIS direct ≈ TOA·τ·cos θ_s).
  Not yet wired into the chain — that is the open Gap 38 decision.
- **`Tape7Reader` now reads MODTRAN 6 tape7 output (CU-154).** The parser recognised only the
  classic space-delimited column vocabulary (`TOT TRANS`, `PTH THRML`, `SOL SCAT`, `GRND RFLT`);
  the first real MODTRAN run set (2026-07-17) is MODTRAN 6, whose tape7 uses underscore labels
  (`TOT_TRANS`, `THRML_EM`, `GRND_RFLT`) and splits the combined solar-scatter column into
  `MULT_SCAT` + `SING_SCAT`. Both vocabularies are now accepted (one reader per binary);
  `path_scattered_radiance` uses the classic `SOL_SCAT` when present, else the `MULT_SCAT +
  SING_SCAT` sum. MODTRAN's `-9999.` end-of-block sentinel is now detected and excluded. This is
  the enabling change for real-MODTRAN integration (Gap 39/38, CU-011, the shipped atmosphere
  library); the delivered 39-run matrix all parses. No change to results for existing
  (synthetic-fixture / SimpleAtmosphere) configs.

### Fixed
- **GUI: undoing a target-shape pick now also reverses the dimensions seeded alongside it, in one
  step (CU-141, view-only).** Picking a shape auto-seeds any still-unset required dimensions to
  nominal values (CU-125); previously Undo reversed only the shape enum and left the seeds behind.
  The shape edit and its seeds are now recorded under a single `QUndoStack` macro, so one Undo
  restores the exact pre-pick state (shape *and* dimensions). Golden results untouched.
- **GUI: Evaluate gains a `Ctrl+Return` (⌘+Return on macOS) shortcut alongside `F5` (CU-142,
  view-only).** A bare `F5` needs the Fn modifier on stock macOS, leaving the app's most-used action
  keyboard-unreachable there; the added chord fixes reachability while keeping the familiar F5=Run
  convention. Menu items and the Run button are unchanged.
- **Results-affecting (both-set configs only): `geometry.target.shape` now wins over
  `geometry.target.projected_area_m2` in the *published* projected area, not just the descriptor
  (CU-148).** When a config set **both** a concrete shape and an explicit `projected_area_m2`, the
  inferrer applied "shape wins" to the descriptor `A_t` and emitted a `shape wins` warning, but
  `SourceStage` still published the **param** area to the regime classification and the
  SpectralIntegration solid angle — so the SNR-bearing path silently used a different area than the
  descriptor and the warning reported. `SourceStage` now adopts the descriptor's authoritative `A_t`
  unconditionally, so the published area, the descriptor, and the warning agree. **Direction/magnitude:**
  affects only configs that set both a shape and `projected_area_m2`; for those, regime and SNR shift by
  the ratio of shape-area to param-area. **No existing golden or example uses that combination, so all
  baselines are byte-identical** (verified full-suite); a new `test_stage.py` both-set test covers the fix.

### Added
- **Scene-type parameter relevance gating (Gap 85 partial, results-neutral).** Source-stage
  parameters now carry `regime:<scene_type>` schema tags (background + contrast-reference +
  fill-fraction); with a declared `source.scene_type`, the GUI Source form **disables** (never
  hides) rows irrelevant to that type with a tooltip naming the relevant regimes — declare
  `extended` and the sub-pixel knobs gate off, declare `sub_pixel` and the contrast reference
  gates off, `auto` gates nothing. Metadata-only schema change; no computed value changes.
- **GUI: confirm-before-Apply import previews (ADR-0009 D5, results-neutral).** New shared
  `ImportPreviewDialog`: pick a file, see the parsed curve + unit-labeled parse facts (point
  count, λ span, value ranges), then Apply commits the path with one `sensor.set` — or the
  loader's actionable error shows inline and Apply stays disabled. Wired for vendor QE CSVs
  (Detector → "Import QE curve (preview)…" → `detector.qe_table_path`) and MODTRAN tape7s
  (Atmosphere → MODTRAN → "Import tape7 (preview)…" → `atmosphere.modtran.tape7_path`; shows
  transmittance + path radiance). Backed by the new `radiant.api.preview_spectral_import`.
- **Zemax Zernike wavefront via config (`optics.zernike_file`) + GUI import (GS-4 split 2).**
  New parameter: point at a Zemax 'Zernike Standard Coefficients' export and the API layer loads
  it pre-chain, injecting the ZERNIKE-mode wavefront (supersedes the scalar WFE; the report's
  reference wavelength is honored, `optics.wfe_reference_wavelength_um` is the fallback). Persists
  via Save/Open and works from the CLI. The Optics Inputs card gains the WFE fields (reference
  wavelength, Zernike file, defocus) and an **Import Zemax Zernike…** button with a
  confirm-before-Apply summary (terms, non-piston RSS waves, reference λ — new
  `radiant.api.preview_zemax_zernike`). Results-neutral unless the parameter is set.
- **GUI: unsaved-edit guards, script-editor line numbers, File → New crash fix (CU-140 /
  CU-144 / CU-145, results-neutral).** File → New / Open / Open Recent now ask
  Save / Discard / Cancel when the config has unsaved edits; closing a dirty script tab asks
  Discard / Cancel; the script Editor pane gains a theme-aware line-number margin.
  **Fixed:** File → New crashed (uncaught resolution error) — every provenance/value display
  surface now falls back to an unset display on a not-yet-resolvable config (new
  `safe_provenance` helper used across the parameter tree, geometry forms, YAML view, and the
  editor dialog), so a blank config is editable as intended.
- **Bulk parameter reset + CLI element-config support + integration-time mirror (Gap 93 /
  CU-153, results-neutral).** New `Sensor.reset_all(scope="user_set"|"all")` (over the new
  `ParameterSet.input_provenances()` snapshot); the GUI's Edit → Reset to Defaults is now live —
  with a current file it reverts by clean reload (exact file state), without one it clears to
  schema defaults, both behind confirmation. `radiant run`/`validate` now accept
  `optical_elements`-bearing configs (CU-153): run injects the parsed train pre-chain, validate
  checks the section through the same facade the API uses. The Readout card additionally shows
  the (shared) `spectral_integration.integration_time_s` under an "Acquisition" heading —
  presentation only, same parameter, no schema change.
- **Inline spectral tables + type-or-paste spectrum entry (owner request, ADR-0009 follow-on).**
  Element-document R/T values now accept an inline `{wavelength_um: [...], values: [...]}` table
  (persists in the YAML — no external CSV needed) alongside scalars and CSV paths. New GUI
  `SpectralTableDialog`: define a spectral response by typing rows or pasting two columns from a
  spreadsheet (live validation; λ-sorted). Wired in two places: the Optics element editor's
  **Spectrum…** button (per-row R/T λ-table) and the Detector form's **Define QE(λ) table…**
  button (writes a QE CSV and sets `detector.qe_table_path` in one call). **Fixed (latent
  engine bug):** spectral element inputs carrying their own grid (coating CSVs, inline tables)
  previously broadcast-crashed the optics stage when their grid differed from the run grid —
  `_scalar_to_spectral` now resamples onto the evaluation grid (linear, never silent
  extrapolation; a run band wider than the table raises the actionable range error). Facade
  validation/preview now runs on each entry's native grid. GUI polish: FieldRow value buttons
  are width-capped so labels no longer truncate in wide panes; element-editor Kind column locks
  to mirror on reflective rows.
- **GUI: existing-API menu wire-ups (GUI Capability Expansion plan GX-1, results-neutral).**
  Enabled four disabled menu placeholders, each one API call: File → Export YAML…
  (`Sensor.save` snapshot — does not rebind the current file), File → Export JSON Result…
  (`ChainResult.to_provenance_record` as JSON, armed once a result exists), Tools → Parameter
  Schema Browser (new read-only, filterable tree over `Sensor.parameter_defs()`, Gap 70), and
  Tools → Explain Parameter… (parameter picker → `Sensor.explain`). Run-menu sweep/MC/Batch
  placeholders stay disabled (deferred tier, owner ruling 2026-07-16); Edit → Reset to Defaults
  stays disabled pending a public provenance/reset-all accessor (new Gap 93). View-only.
- **GUI: Optics element-train editor (GUI Capability Expansion plan GS-4, results-neutral).**
  New **Elements** tab on the Optics stage: author the mixed-train element list in a table
  (per-element name, transfer mode, kind, R/T as scalar or spectral-CSV path, temperature,
  geometry); *Apply* commits through one `Sensor.set_optical_elements` call (io-parser
  validation — a Kirchhoff violation or bad file shows the actionable dialog and never touches
  the live sensor); ε is a **derived read-only** column (Rule 5); the authored train persists
  through Save/Open (ADR-0009 D4) and drives full-prescription optics on the next evaluation.
  Also fixed: an empty/directory spectral-file reference in `io/element_config.py` now raises
  the actionable `ElementConfigError` instead of leaking `IsADirectoryError` (Rule 15).
- **GUI: Source Inputs — reflective/solar pathway + scene-type declaration (GUI Capability
  Expansion plan GS-1, results-neutral).** The Source card grows from 6 thermal fields to four
  groups: Thermal (T/ε + hot-target opt-out), **Reflective (solar)** (`source.target.reflectance`
  pure-ρ pathway + `geometry.solar_illumination` day/night + solar zenith/azimuth), Background &
  contrast reference (+ `source.background.material` library name), and **Scene type & regime**
  (`source.scene_type` declared, `source.regime_override` force, fill fraction). VIS reflective
  and MWIR mixed emit+reflect scenarios are now configurable in the GUI; the ADR-0008 T2
  declared-vs-derived warning surfaces in the Messages panel. View-only — no computed value
  changes.
- **GUI: Detector Inputs expanded to the full schema (GUI Capability Expansion plan GS-3,
  results-neutral).** The Detector Inputs tab grows from 6 fields to every `detector.*`
  parameter (27), grouped: pixel geometry & temperature, QE (scalar / CSV curve import /
  temperature coefficients), dark current & glow, 1/f noise, G-R & Johnson, fixed-pattern
  noise & regime, persistence, IPC & diffusion. A manifest-equals-schema test keeps the form
  complete as the schema grows. View-only — no computed value changes.
- **GUI: Atmosphere stage Inputs card (GUI Capability Expansion plan GS-2, results-neutral).**
  The Atmosphere stage gains its first editable inputs (audit A-1…A-4): the `atmosphere.model`
  selector (`simple`/`exo`/`tabulated`/`modtran`/`interpolated`) showing only the active
  backend's parameter group (simple profile/aerosol/visibility/PWV; MODTRAN tape7 import +
  profile/aerosol/H₂O/O₃ scaling; tabulated file paths; interpolated run-matrix dir/axes/method;
  exo note) plus turbulence r₀ — all schema-driven `FieldRow`s, one `sensor.set` per edit. The
  stage also gains a scalar Outputs readout and tells propagation as before/after: pre-atmosphere
  emission (`spectral_source_emission`) beside τ/L_path and the at-aperture radiance. View-only —
  no computed value changes.
- **Optical-element document facade + config persistence (ADR-0009 / GUI plan FW-1,
  results-neutral).** New public surface for authoring the mixed-train element list as a
  declarative document: `Sensor.set_optical_elements(entries, base_dir=...)` /
  `Sensor.optical_elements()` (validate-and-attach; parsed onto the evaluation grid per run and
  injected as `optics_config.element_list`), and `radiant.api.preview_optical_elements` /
  `normalize_element_document` / `ElementPreview` (parse-for-display without mutation — feeds the
  GUI import-preview dialog; emissivity reported Kirchhoff-derived per Rule 5). The
  `optical_elements:` YAML section now **round-trips**: `Sensor.save` writes it and
  `Sensor.load` / `from_yaml` / `from_dict` re-attach it (previously the section was
  API-injection-only and vanished on save). A bare `io.config.load_config` call now **raises an
  actionable `ConfigError`** on a section-bearing config instead of the old "Unknown parameter"
  failure (never a silent skip; opt-in via new `sections_out=`); `save_config` gains
  `sections=`. `io.element_config.parse_element_entries` is the new document-level parser seam
  under `load_element_list`. Goldens byte-identical (view/plumbing only — an attached train
  changes results exactly as the same train injected manually always did).
- **Declared-vs-derived regime cross-check (ADR-0008 T2, results-neutral).** When a config
  **declares** an explicit `source.scene_type` (`extended` / `sub_pixel` / `point_source`, i.e. not
  `auto`) that disagrees with the radiometric regime the chain **derives** from the target angular
  size vs the PSF/IFOV, OpticsStage now surfaces a `UserWarning` naming both (Rule 17 — never silent).
  The run still uses the derived regime; to *force* a regime, use `source.regime_override` (the hard
  binding) rather than `scene_type` (the soft declaration). Warning-only — no computed value changes;
  goldens byte-identical. Clarifies the `scene_type` (declared intent) vs `regime_override` (hard
  force) distinction in `RADIANT_Source_Target_System` §8.10.
- **RADIANT Desktop GUI v1 — complete (GUI Development Plan closed, view-only capability).**
  `radiant gui [config.yaml]` launches the PySide6 contextual per-stage workspace: a 9-stage
  geometry-first strip, a schema-driven All-Parameters tree, per-stage **instruments** for all
  nine stages at the Geometry gold standard (Inputs → one `sensor.set` per edit / unit-carrying
  Outputs from `stage_outputs` / stage plots from `result.plot.*`), a persistent right rail
  (pinned metric cards, Edit-Config-YAML modal, Messages, Evaluate footer), the 2D `QPainter`
  geometry schematic viewer (ADR-0007), the embedded scripting window (Command Window + Workspace
  + multi-tab script Editor), and full File round-trip / undo-redo / light-dark theme toggle. The
  four framework-plot additions that back the Source and Optics instruments ship as public
  accessors — `result.plot.spectral_source_emission()` (Gap 91), `pupil_amplitude()` / `pupil_phase()`
  (Gap 89), `optical_throughput()` / `coating_spectra()` (Gap 90), plus `noise_pie()` /
  `psf_pixel_grid()` — reusable from any script or the console. The GUI is a pure view over the
  scripting API (one action ↔ one API call); **golden results are byte-identical to pre-GUI**.
  Out-of-v1 GUI features and the v1.1 Sweep/Batch tab are tracked in `docs/tracking/gaps.md`
  (GUI-1…GUI-17); the completed plan is archived at `docs/archive/GUI_Development_Plan.md`. The
  entries below record the individual phases that composed this capability.
- **GUI scripting window — Pass 2: the multi-tab script Editor (arch doc §4.6.1, view-only).**
  The scripting window now hosts all three MATLAB-style panes: a new **Editor** (top pane) over
  the Pass-1 Command Window + Workspace. The Editor opens, writes, saves, and **runs** multiple
  Python scripts at once — a tabbed set of `.py` buffers each with a file name + unsaved-edits
  (`*`) marker, plain-text **New / Open / Open Recent / Save / Save As** (a persisted
  recent-scripts list, kept distinct from the config recent list), syntax highlighting, and a
  File/Run menu + toolbar (Run = F5 / ⌘⏎, Run Selection). **Run** executes the active tab in the
  *same* namespace the Command Window and Workspace share, so a script's `x = result.snr()`
  leaves `x` usable at the command line and visible in the Workspace; stdout/stderr and any
  traceback route to the Command Window (surfaced, not swallowed), and a `sensor.set(...)` in a
  script marks the main GUI stale exactly like a typed command. Completes the ratified
  scripting-window vision (CU-143 closed).
- **GUI scripting window — Pass 1: separate window + Command Window + Workspace (arch doc
  §4.6.1, view-only).** The MATLAB-style scripting environment is now a **separate top-level
  window** ("RADIANT Scripting"), launched from **Tools → Scripting Window** (`Ctrl+Shift+P`)
  — movable to a second monitor, and re-launching raises the single existing instance rather
  than spawning a duplicate. It hosts the reused **Command Window** REPL (live
  `sensor`/`result`/`plot`/`inspect_result`, history, figure pop-out) beside a new live
  **Workspace** variable browser that lists each namespace variable's name, type, and a short
  value/size summary (e.g. `x: ndarray (500,)`, `snr: float 616.0`), refreshing after each
  command and after every evaluate/refresh, with a detail dump (a `ChainResult`'s inspect
  tree, else `repr`) for the selected variable. A `sensor.set(...)` typed in the window still
  marks the main GUI stale and offers one-click Refresh (coherence unchanged). The multi-tab
  script Editor is Pass 2 (deferred, CU-143).
- **GUI file round-trip, undo/redo, and the light/dark theme toggle (GUI plan Phase 9, arch
  doc §10, view-only).** The **File** menu is complete: New, Open, **Open Recent** (persisted
  across launches via `QSettings`), Save, and Save As — all file I/O through `Sensor.load()` /
  `Sensor.save()` only (one action ↔ one API call, §4.1). The window **title** shows the current
  config's file name with a `*` **dirty marker** that sets on any edit (tree, stage form, YAML
  editor, console) and clears on save; Open / New swap the sensor through the shared adopt path
  so every panel + the console rebind and re-evaluate, and a bad file surfaces an actionable
  error (Rule 15). **Edit → Undo / Redo** (Ctrl+Z / Ctrl+Shift+Z) reverse the last ~20 parameter
  edits via a `QUndoStack` of named `sensor.set` commands (each labelled e.g. *"Set
  optics.aperture_diameter_m = 0.5 m"*); an undo re-reads the value into the parameter panel/forms
  and re-evaluates. Whole-config swaps (Open / New / YAML-editor Apply / console Refresh) clear the
  undo history (documented — explicit beats a fragile merge). **View** menu: a **light/dark theme
  toggle** that re-applies the design-system QSS + palette, re-themes the custom-painted widgets
  (the 2D schematic viewer and the detector pixel illustration via their `set_theme`), and
  persists the choice (`QSettings`) so the next launch reopens in the same theme; plus panel
  show/hide (Parameter Panel F6, Right Rail F7, both persisted) and stage-jump shortcuts
  (Ctrl+1..9). New public entry surface: `launch_gui(sensor, path=...)` threads the launched
  config path into the title/recent list. Golden suite untouched (a view over the scripting API;
  no physics, schema, or result changed).
- **GUI embedded scripting console (GUI plan Phase 8, arch doc §4.6.1, view-only).** A
  MATLAB-style command window as a **global tool** — a dockable `ScriptingConsole` (bottom
  `QDockWidget`, hidden at launch) opened from **Tools → Python Console** (`Ctrl+`` ` ``) or the
  View-menu toggle; enabled once a sensor is loaded. Its REPL namespace binds live objects:
  `sensor` (the window's live `Sensor`), `result` (the last `ChainResult`, re-bound after each
  evaluation), `plot` (`ResultPlotNamespace(result)` — the public `result.plot.*` figure surface),
  plus `inspect_result` and `Sensor` conveniences. A command that returns a matplotlib `Figure`
  (e.g. `plot.mtf()`) pops out into its own window. **GUI ↔ console coherence** is explicit, not
  magic: after a command that mutates the sensor the console shows a *"console changed state —
  Refresh"* banner and the window marks itself stale (stage dots + status bar); one-click
  **Refresh** adopts the console's current `sensor` (covering both in-place `sensor.set(...)` and a
  full `sensor = Sensor.load(...)` rebind), re-reads it into the parameter tree + input forms, and
  re-evaluates. **Decision (CU-138):** shipped as a REPL over `code.InteractiveConsole`, not the
  preferred `qtconsole` in-process kernel (not installed here + fragile/untestable under the
  offscreen QPA) — the plan-sanctioned fallback; the `qtconsole` pin is retained for the deferred
  kernel path. Golden suite untouched (a view over the scripting API).
- **GUI Platform + Readout stage instruments (GUI plan Phase PS-5, arch doc §4.4.1
  Platform/Readout rows, v1-minimal, view-only).** Both stages' contextual centers become clean
  minimal instruments (single flat panes): editable schema-driven inputs as shared `FieldRow`s
  beside the scalar outputs readout and a themed *v1-minimal* note. **Platform** — a new
  `PlatformInputsForm` (jitter RMS isotropic + cross/along-track under a *Jitter* heading,
  `ground_velocity_m_s` + `smear_length_um` under a *Motion & smear* heading) beside the
  outputs (`jitter_sigma_x_m`/`jitter_sigma_y_m`/`smear_width_m` in m, `EE_box` fraction); no
  dedicated MTF (owner-ratified — the smear/jitter MTF terms stay in the Optics/Performance
  overlays). **Readout** — a new `ReadoutInputsForm` (`read_noise_e_rms` under *Read noise*,
  `gain_e_per_dn` + `adc_bits` under *ADC*, `full_well_capacity_e` under *Full well*) beside the
  outputs (`signal_dn_final` DN, `sigma_total_e`/`total_well_e` e-, `well_fill_fraction`, …) and
  the scalar noise budget (`result.plot.noise_budget()` — read noise + quantization live in this
  stage; §4.7 relocates the Noise Budget detail tab to the Detector/Readout views). Editing any
  input is one `sensor.set` (validate-on-a-clone reject discipline) and re-evaluates so the
  outputs (and the Readout noise budget) refresh (edit-and-watch). Group headings are a
  presentation choice only — **no schema change**. Golden suite untouched (view over the API).
- **GUI Performance stage instrument metric-failure surfacing (GUI plan Phase PS-6, arch doc
  §4.4.1 Performance row, view-only).** The Performance center's metric summary
  (`OutputsReadout.show_metrics` over `result.metric_records()`) now renders a **result-typed
  metric failure** — a non-finite metric value (Rule 17 carve-out for the `radiant.performance`
  metric layer, e.g. an SNR/NEDT that could not compute) — as `n/a (<failure_reason>)`, reading
  the structured `failure_reason` from the metric's result object (`stage_outputs["performance"]`),
  never a bare `nan` and never a blank. Finite metrics render value + registry unit unchanged
  (SNR/NEDT/NIIRS/GSD/MTF@Nyquist and every other `metric_records()` entry), above the system-MTF
  (`result.plot.mtf()`) and MTF-budget (`result.plot.mtf_budget()`) plots. This completes all nine
  per-stage instruments. Golden suite untouched.
- **GUI Spectral-Integration stage instrument (GUI plan Phase PS-4, arch doc §4.4.1
  Spectral-Integration rows, view-only).** The Spectral-Integration stage's contextual center
  becomes an instrument (a single flat pane, owner judgment): editable band + acquisition
  inputs (a new `SpectralIntegrationInputsForm` — the filter bandpass edges
  `spectral_integration.filter_min_um` / `filter_max_um` under a *Filter bandpass* heading and
  `integration_time_s` under an *Acquisition* heading, per the §4.4.1 GUI-grouping note — as
  shared `FieldRow`s), the scalar electron-budget outputs readout (`signal_e`, `e_rate_per_s`,
  `background_e`, `contrast_e`, `qe_scalar`, …, units from `api.stage_output_units`), the in-band
  signal spectral radiance as the primary plot (`result.plot.spectral_inband()`), and a themed
  note that the per-λ noise spectrum is deferred (Gap 92; noise is scalar per term, computed once
  post-integration — Rule 8). Editing any input is one `sensor.set` (validate-on-a-clone reject
  discipline) and re-evaluates, so the in-band spectrum re-clips to the new band and the electron
  budget re-scales with the integration time (edit-and-watch). The `integration_time_s` grouping
  is a presentation choice only — **no schema change** (the sensor path is unchanged). Golden
  suite untouched (the GUI is a view over the scripting API).
- **`result.plot.noise_pie()` framework accessor (GUI plan Phase PS-3 Part A, owner-ratified
  §8 decision 2, results-neutral).** A new pie-chart accessor on `ResultPlotNamespace` (builder
  `radiant.api.plot.plot_noise_pie`), the pie sibling of the shipped `noise_budget()` bar over
  the same `result.noise_terms` data. Presentation choice (documented): noise adds in
  **quadrature** (σ_total² = Σ σ_i²), so the slices are proportional to each term's **variance**
  (σ_i²) and sum to 100 % of the noise **power**; each wedge is labelled with the term name, its
  σ_i in **e- RMS**, and its % of the variance (zero terms omitted). Raises `ApiValidationError`
  when the result carries no noise terms. Purely additive — no computed result changes; the
  golden suite is byte-identical.
- **`result.plot.psf_pixel_grid()` framework accessor (GUI plan Phase PS-3 Part B,
  results-neutral).** `psf()` with the **detector pixel grid** overlaid — pixel-boundary
  gridlines at the detector pixel pitch (`EffectivePSF.pixel_pitch_m` over samples spaced at
  `sample_spacing_m`), cropped to the PSF core, with the pitch (µm) in the title. Implemented as
  an optional `pixel_grid` parameter on `plot_psf` (default `False` leaves the shipped image
  unchanged). A view over already-computed data — no results change.
- **GUI Detector stage instrument (GUI plan Phase PS-3, arch doc §4.4.1 Detector rows,
  view-only).** The Detector stage's contextual center becomes a tabbed instrument (the §4.4
  sub-view hook, now used by Geometry, Optics, and Detector): three tabs — **Inputs** (editable
  detector `FieldRow`s — quantum efficiency / dark rate / pixel pitch x,y / fill factor /
  detector temperature — beside the scalar outputs readout, `signal_e`/`dark_e`/…), **Noise**
  (the ratified `noise_pie()` variance pie as the primary chart above the per-term table +
  click-to-explain; the redundant bar is suppressed), and **Detector + PSF** (a new Qt-drawn
  pixel illustration labelled with the pitch in µm + fill factor, beside `psf_pixel_grid()`).
  Editing any detector input is one `sensor.set` (validate-on-a-clone reject discipline) and
  re-evaluates, so every tab refreshes — editing the dark rate shifts the noise pie, editing the
  pixel pitch redraws the illustration and the PSF grid (edit-and-watch). New widgets
  `DetectorInputsForm`, `DetectorIllustration`; `NoiseBudgetPanel` gains a `show_chart` toggle.
  Golden suite untouched (the GUI is a view over the scripting API).
- **GUI Optics stage instrument (GUI plan Phase PS-2, arch doc §4.4.1 Optics rows,
  view-only).** The Optics stage's contextual center becomes the richest per-stage view and
  the **first production use of the tabbed sub-view hook** (`StageComposition.subviews`): four
  tabs — **Inputs** (editable optics `FieldRow`s — aperture / focal length / f-number /
  obscuration / spiders / scalar throughput / WFE / optics temperature — beside the
  **FINAL-regime** outputs readout, `stage_outputs["optics"]["regime"]`, Rule 10), **MTF** (the
  per-term MTF@Nyquist table + `mtf()` overlay via `MtfPanel`, plus the `mtf_budget()` bar),
  **PSF + Pupil** (`psf()` beside the FP-2 `pupil_amplitude()` apodization map and
  `pupil_phase()` wavefront-error map in waves), and **Throughput** (the FP-3
  `optical_throughput()` τ_opt(λ) + per-element `coating_spectra()`). Editing any optics input
  is one `sensor.set` (validate-on-a-clone reject discipline) and re-evaluates, so every tab
  refreshes — editing `wfe_rms_waves` makes the pupil-phase map gain structure, editing the
  aperture updates MTF/PSF, editing the coating updates throughput (edit-and-watch). New widget
  `OpticsInputsForm`; the `optics` composition gains its four `StageSubView` tabs (the hook is
  now used by Geometry and Optics). Golden suite untouched (the GUI is a view over the scripting
  API).
- **GUI Source stage instrument (GUI plan Phase PS-1, arch doc §4.4.1 Source rows,
  view-only).** The Source stage's contextual center is brought to the Geometry-screen
  standard. It now shows: the pre-atmosphere **target + background emission spectra**
  (`result.plot.spectral_source_emission()`, FP-1) as the primary plot, with the at-aperture
  radiance (`spectral_source()`) kept as a secondary plot; editable **radiometric inputs**
  (`source.target`/`background`/`contrast_reference` ε & T) as shared `FieldRow`s, one
  `sensor.set` per edit with the validate-on-a-clone reject discipline; the shared
  **shape / size / orientation** editor (`source.target.shape*`) — the same `TargetShapePanel`
  the Geometry Schematic tab mounts, with nominal-dim seeding on shape-select (CU-125); and an
  **Outputs readout** carrying the tentative regime (`stage_outputs["source"]["regime_tentative"]`,
  Rule 10) plus `projected_area_m2`/`range_m`/`fill_fraction`/`angular_extent_rad`, each with its
  unit. Editing any input re-evaluates and the spectra + readout refresh (edit-and-watch). New
  widgets `TargetShapePanel` (factored out of the Geometry `GeometryAnglePanel` — one
  target-shape editor, two homes, Rule 19) and `SourceInputsForm`; `OutputsReadout` now renders
  an enum output (the regime) by its value; `radiant.api.stage_output_units` gains the Source
  scalar-output units. Golden suite untouched (the GUI is a view over the scripting API).
  Per-scenario-type input relevance stays deferred (Gap 85).
- **Complex-pupil diagnostic maps + `result.plot.pupil_amplitude()` / `pupil_phase()` (Gap 89,
  GUI plan Phase FP-2).** `OpticsStage` now persists the two diagnostic faces of the complex
  pupil it already builds for the MTF autocorrelation: `pupil_amplitude` (dimensionless
  apodization/transmission mask — central obscuration, spider vanes, and any measured
  `pupil_mask_override` included) and `pupil_phase_waves` (the wavefront-error map in **waves**,
  `phase_radians / 2π`, at `pupil_wavelength_um` — band centre for polychromatic runs — masked
  to zero outside the clear aperture), plus `pupil_plane_extent_m` (physical pupil diameter for
  axis scaling) in `stage_outputs["optics"]`. New public accessors
  `ResultPlotNamespace.pupil_amplitude()` (colorbar "transmission (dimensionless)") and
  `pupil_phase()` (colorbar "wavefront error (waves)"), mirroring `psf()` (2-D imshow +
  colorbar). Purely additive diagnostic views captured verbatim from the same arrays the
  autocorrelation consumes — never read back into the PSF/MTF path (Rule 4 untouched); the full
  golden suite is **byte-identical**. Also renames the internal
  `pupil_mtf._resolve_wfe_for_wavelength` → `resolve_wfe_for_wavelength` (module-internal helper,
  no public surface).
- **Optics coating / throughput spectra — `result.plot.optical_throughput()` /
  `coating_spectra()` (Gap 90, GUI plan Phase FP-3).** Two additive view accessors on
  `ResultPlotNamespace` render the optics `SpectralData` OpticsStage already stores, with no
  physics or results change. `optical_throughput()` plots the assembled system transmission
  `stage_outputs["optics"]["tau_opt_spectral"]` — τ_opt(λ) [dimensionless] — vs wavelength.
  `coating_spectra()` overlays, per element in `stage_outputs["optics"]["elements"]`, its
  reflectance R, transmittance T, and Kirchhoff-derived emissivity ε (`element.emissivity`;
  ε = 1 − R for mirrors, declared train ε for lumped, 0 for simple refractives) — all
  dimensionless on one y-axis; an identically-zero curve is omitted (a mirror shows R + ε, a
  simple refractive shows T + R). New plot builders `plot_optical_throughput` /
  `plot_coating_spectra` in `radiant.api.plot`. Each accessor raises `ApiValidationError` when
  the optics outputs / elements are absent. Purely additive: the golden suite is
  **byte-identical**.
- **Pre-atmosphere source-emission frames + `result.plot.spectral_source_emission()` (Gap 91,
  GUI plan Phase FP-1).** `AtmosphereStage` now persists two additive `RadiometricFrame`s —
  `at_source_target` (always) and `at_source_background` (when a background descriptor is
  present) — carrying the emitted+reflected spectral radiance *leaving the source*
  (`L_source`, W/m²/sr/µm) **before** the atmospheric up-leg, satisfying
  `at_aperture_target ≈ τ_up · at_source_target + L_path_up`. New public accessor
  `ResultPlotNamespace.spectral_source_emission()` draws the target (+ optional background)
  emission spectrum, isolating what the target emits from what reaches the aperture (vs the
  post-atmosphere `spectral_source()`). New assembly functions
  `assemble_target_source_emission` / `assemble_background_source_emission`. Purely additive:
  the new frames feed no metric and the full golden suite is **byte-identical** (505/505
  integration tests pass unchanged).
- **GUI geometry schematic — ground vectors for elevated targets (owner feedback 2026-07-14,
  view-only).** When the target is above the ground (`geometry.target_altitude_m > 0`) the
  Schematic tab now additionally draws a **SENSOR→GROUND** vector (blue, dashed) and a
  **SUN→GROUND** vector (amber, dashed), both landing at the target's **ground projection**
  (nadir footprint, directly below the body on the ground plane). The VECTORS legend gains
  matching rows, shown only when the vectors are present. A ground target (altitude 0) has
  target == ground, so the two vectors are degenerate and absent — unchanged behaviour there.
  Colours come from the allowlisted physics palette (sensor = blue, sun = amber). Golden
  untouched (the GUI is a view over the scripting API).
- **GUI geometry Schematic tab — editable + nominal shape dims (owner feedback 2026-07-14,
  view-only).** Three changes to the Geometry stage's Schematic tab (golden untouched — the
  GUI is a view over the scripting API): (1) **Geometry is now settable from the Schematic
  tab.** Its side panel gains a **Geometry inputs** accordion page hosting the reusable
  Phase-5 `GeometryModeForm`, wired through the same edit → one `sensor.set` → debounced
  re-evaluate → schematic re-render path as the Inputs tab, so the user can edit geometry and
  watch the schematic + arcs move. Both geometry forms (Inputs + Schematic) read the one live
  sensor and re-sync on the next clean evaluation. New public GUI surface:
  `GeometryAnglePanel.geometry_form` property; `StagePane.refresh_geometry_forms`. (2)
  **Shapes load with nominal dimensions (CU-125).** Selecting a target shape whose required
  dimensions are still the `0.0` "not set" sentinel now seeds them to nominal non-zero values
  (`geometry_angle_panel.NOMINAL_SHAPE_DIMENSIONS`) — one `sensor.set` each, only where unset,
  never overwriting a user value — so the re-evaluate succeeds instead of tripping the
  `radiant.source` shape factory. The schema keeps the `0.0` Rule-12 default; the nominal map
  is a GUI-side UX default only.
- **GUI geometry schematic — Pass 2 (annotations + shape editing; ADR-0007, view-only).**
  The 2D orthographic schematic gains the annotations and shape-editing the mockup/owner
  specify. (1) **Angle arcs + degree labels (CU-128):** revealable arcs for off-nadir η,
  sun-zenith θ_s, relative-azimuth Δφ (ground), and phase α_t, each drawn with the ported
  projection math but labelled with the angle **value from `stage_outputs["geometry"]`**
  (bound verbatim into `ViewerState`) shown in **degrees** (§6.3); the phase arc is
  symbol-only (no stage-output phase angle). The side-panel angle toggles now reveal/hide
  the arcs and repaint. (2) **Altitude leader labels (CU-129):** `h_s` / `h_t` pills in
  km/m, the not-to-scale magnitude annotation (§6.1). (3) **Full shape library + ALL
  dimension inputs (CU-131 + owner request):** the schematic draws distinct
  sphere/box/cylinder/cone/flat-plate wireframes (aspect ratio from the shape's own dims,
  never metric magnitude), and the side panel exposes every relevant dimension input for
  the selected shape (radius / length / width / height / base-radius), showing only the
  subset the shape uses, each one `sensor.set` per edit. (4) **RPY triad (CU-130):** the
  on-target body-axes gizmo (roll +X′ pink / pitch +Y′ green / yaw +Z′ purple) from
  `source.target.shape_{yaw,pitch,roll}_rad`, with the body wireframe rotated by the same
  ZYX Euler. New public GUI surface: `GeometryAnglePanel.dimensionRequested` signal +
  `set_dimension_bounds`/`set_dimensions`/`dimension_spin`; `SchematicView.set_revealed_angles`;
  new modules `radiant.gui.viewer.angle_catalog` / `radiant.gui.viewer.angle_truth`. A
  **binding angle-truth consistency test** asserts the viewer's local angle recomputation
  agrees with `stage_outputs["geometry"]` within `ANGLE_CONSISTENCY_ABS_TOL_RAD = 1e-9` rad
  (measured residual ~1e-16). No computed results change (the stage remains the single
  source of angle truth); golden untouched.

### Removed
- **`gui` extra no longer pins `pyvista` / `pyvistaqt` (CU-134, GUI plan Phase 9).** The 2D
  `QPainter` schematic viewer (ADR-0007) replaced the PyVista/VTK 3D viewer, and no
  `radiant.gui` module imports pyvista/pyvistaqt/vtk (grep-guarded by
  `test_no_pyvista_import_in_gui`), so the two pins were dropped from the optional `gui`
  extra. `pip install "radiant[gui]"` no longer pulls the VTK native dependency chain;
  `matplotlib` and `qtconsole` remain pinned. No runtime behavior change (the pins were unused).
- **GUI geometry Schematic tab — redundant derived-angles table removed (owner feedback
  2026-07-14, view-only).** The Schematic tab's side panel no longer carries the derived
  "Geometry — derived angles & ranges" `GeometryReadout` (it duplicated the Inputs tab; the
  key derived values surface on the schematic itself as arc degree labels + altitude leader
  labels). The angle-arc reveal toggles remain; the Inputs-tab readout is unchanged. Removed
  public GUI surface: `GeometryAnglePanel.readout` property + `populate_readout` method.
- **GUI lifted VTK/PyVista scene library removed (CU-132, ADR-0007 Rule 27).** The
  superseded `radiant.gui.viewer.scene` render library (~3.9 kLoC across `builder`,
  `arcs/`, `frames/`, `glyphs/`, `ground/`, `labels/`, `target/`, `vectors/`) is deleted now
  that the 2D `QPainter` schematic fully replaces it; only the allowlisted glyph-colour
  module `radiant.gui.viewer.scene.palette` survives. `radiant.gui.viewer` no longer imports
  `pyvista`/`pyvistaqt`/`vtk` (the `gui`-extra pins are retained pending a dependency-drop
  audit — CU-134).

### Changed
- **Target spatial extent moved from the `source.target.*` to the `geometry.target.*` parameter
  namespace (ADR-0008 Phase A, public surface — goldens byte-identical).** The target's shape,
  dimensions, orientation, and projected area — `shape`, `shape_radius_m`, `shape_length_m`,
  `shape_width_m`, `shape_height_m`, `shape_base_radius_m`, `shape_yaw_rad`, `shape_pitch_rad`,
  `shape_roll_rad`, `projected_area_m2` — are now defined under `geometry.target.*` (the Geometry
  stage owns the extent → projected-area → angular-subtense chain). The old `source.target.*`
  names keep working as **deprecated aliases** (a `DeprecationWarning` redirects them; provenance
  records the canonical name). The **spectral/material** target params (`source.target.temperature`,
  `emissivity`, `reflectance`, BRDF) and the sub-pixel `source.target.fill_fraction` are **unchanged**
  — the namespace was split, not renamed wholesale. Results-neutral: this relocates parameter
  definitions only; no computation changed and the full golden suite is byte-identical. Closes the
  §8 inventory drift (CU-146).
- **GUI scripting window — Editor Run auto-displays top-level bare expressions (arch doc §4.6.1,
  view-only).** A whole-script **Run** now behaves like the command line: `run_script` executes the
  source one top-level statement at a time, so a bare expression on its own line (e.g. `plot.mtf()`
  or `result.snr()`) fires the display hook — a Figure pops out into its own window, any other value
  echoes its `repr`, `None` stays silent. A script's bare `plot.mtf()` therefore pops its figure with
  **no** `show()` / `sys.displayhook(...)` wrapper (the MATLAB "run a script, see the plots"
  behaviour). Statement order and side effects are preserved; the explicit `sys.displayhook(fig)`
  pattern still works; a runtime exception still surfaces its traceback and halts the run (Rule 17).
- **GUI: `Tools → Python Console` (a bottom dock) → `Tools → Scripting Window` (a separate
  window), view-only.** The menu action is renamed and repurposed to open the new separate
  scripting window (action key `tools.console` → `tools.scripting_window`, shortcut unchanged
  at `Ctrl+Shift+P`). The old `View → Show/Hide Python Console` dock toggle (`view.toggle_console`)
  and the bottom-dock console host (`consoleDock`) are removed (Rule 27); the launcher replaces
  them. No change to the REPL's behaviour, binding, or coherence model.
- **GUI geometry Schematic tab — Target shape & orientation fields restyled to match the
  Geometry inputs (owner feedback 2026-07-14, view-only).** The **Target shape & orientation**
  accordion page's controls previously rendered with default-Qt chrome (a plain combo, and
  `QDoubleSpinBox`es with native up/down arrows for the dimension and yaw/pitch/roll values),
  which looked nothing like the styled **Geometry inputs** fields. They are now built from the
  **same** building blocks as the `GeometryModeForm`: `geoModeFamily` cards, a
  `geoModeSelector`-styled shape combo, and the shared `FieldRow` (label + value button) —
  factored into a new `radiant.gui.widgets.field_row` module (`FieldRow`, `ElidingLabel`) that
  both surfaces import, so they cannot visually diverge again. Editing a dimension or RPY value
  now opens the shared `ParameterEditorDialog` (value + unit + validate-on-a-clone reject path,
  one `sensor.set` on commit) instead of a bare spin box, matching the Inputs-tab fields.
  Changed public GUI surface: `GeometryAnglePanel` replaces its `dimensionRequested(str,float)`
  / `orientationRequested(str,float)` signals + `dimension_spin` / `rpy_spin` accessors with a
  single `editRequested(str)` signal + `dimension_row` / `rpy_row` (returning `FieldRow`), and
  drops `set_orientation_bounds` / `set_dimension_bounds` (the dialog now enforces schema
  bounds). Golden untouched (the GUI is a view over the scripting API).
- **GUI geometry Schematic tab — angle-arc selector moved to a plot overlay (owner feedback
  2026-07-14, view-only).** The angle-arc reveal toggles (θ_s sun zenith, Δφ relative
  azimuth, α_t phase angle, η off nadir) moved **out** of the right-column accordion's
  "Angles" page and **onto the schematic plot** as a compact **bottom-left overlay**
  (`AngleToggleOverlay`, new module `radiant.gui.viewer.angle_overlay`), mirroring the
  top-left VECTORS legend. It is a real child `QWidget` on the `SchematicView` canvas,
  repositioned bottom-left on resize, and stays interactive — each checkbox still reveals its
  arc via `GeometryViewer.set_angle_revealed` (reveal path unchanged). The right-column
  accordion now holds only the **Geometry inputs** and **Target shape & orientation** pages.
  Removed public GUI surface: `GeometryAnglePanel.angleToggled` signal + `angle_checkbox`
  accessor (both now on `SchematicView.angle_overlay`). Golden untouched (the GUI is a view
  over the scripting API).
- **GUI geometry viewer reimplemented as a 2D orthographic schematic — view-only
  (ADR-0007 superseded 2026-07-14, Pass 1).** The Geometry stage's viewer is no longer a
  PyVista/VTK render but a crisp, antialiased **2D orthographic line-schematic** drawn with
  `QPainter`, porting the `geometry_viewer` mockup's `geometry.js` projection (new modules
  `radiant.gui.viewer.projection` + `radiant.gui.viewer.schematic_view`). The Geometry
  center tab is renamed **"3D View" → "Schematic"**. Pass 1 draws the ground grid, X/Y/Z
  axes, the four labelled vectors (sun→target, sensor→target, sun→ground, zenith),
  sun/sensor glyphs, a wireframe target (sphere/box/point), ground drop-lines, and the
  VECTORS legend, with orthographic yaw/pitch by mouse drag. The `GeometryViewer` public
  surface (`show_result`, `set_angle_revealed`/`set_triad_visible` as Pass-2 no-op-safe
  stubs, `close_viewer`, `set_theme`) and the `ViewerState` adapter are preserved. The
  three-backend "3D viewer unavailable" degradation ladder is removed — a pure-Qt canvas
  has no VTK/OpenGL dependency and renders/tests faithfully headless. No computed results
  change (the stage remains the single source of angle truth). Deferred to Pass 2: angle
  arcs, altitude leader labels, RPY triad, shape library + dimensions, the angle-truth
  test, and removal of the now-unwired lifted VTK scene library (CU-128–CU-133).

### Fixed
- **GUI: three widget validation guards now raise a `RadiantError` subclass, not bare
  `ValueError` (Rule 15).** `HealthDot.set_status`, `StageChip.set_status`, and the `StageStrip`
  namespace-drift check raised bare `ValueError`, tripping the `tests/test_exceptions.py`
  no-bare-builtin-raises guard on the full suite (they were missed by the scoped GUI test runs).
  New `radiant.gui.errors.GuiValidationError(RadiantError, ValueError)` (mirrors
  `SourceValidationError`) — co-inherits `ValueError` so any `except ValueError` still works.
  Also fixes a stale `test_gui_cli` double whose `fake_launch` did not accept the `path=` kwarg
  the CLI passes since the Phase-9 `launch_gui(sensor, path=...)` signature. No behavior change.
- **GUI scripting console now opens on macOS (owner report 2026-07-15, view-only).** The
  **Tools → Python Console** shortcut was the portable ``Ctrl+` ``, which Qt maps to ⌘` on
  macOS — an OS-reserved shortcut (cycle windows) that never reaches the app, so the console
  "wouldn't open". Rebound to **Ctrl+Shift+P** (⌘⇧P on macOS; unreserved and free on
  Windows/Linux, no collision with existing bindings). The reveal path is also hardened so
  the menu item and shortcut always produce a clearly-visible console: the dock is raised
  front-most and resized to a usable height on reveal, and the console carries a ≥180 px
  minimum height so it is never a zero/sliver-height strip. Golden untouched.
- **GUI geometry Schematic tab — inputs no longer clipped horizontally (owner bug
  2026-07-14, view-only).** The right-column "Geometry inputs" form was wider than its
  accordion column, so the value fields (e.g. `8000 m`, `1.5708 rad`) were cut off behind a
  horizontal scrollbar. The mode-selector combos and field-value editors now size to the
  available column width (expanding, minimum-contents sizing) instead of forcing their
  content width, the long form title wraps, and the raw dot-path field labels elide (full
  name on hover) — so the form fits its column and scrolls only vertically when tall, never
  clipping horizontally. Golden untouched.
- **GUI geometry schematic — centred + framed, no longer bottom-anchored (view-only).**
  The 2D orthographic schematic rendered anchored to the *bottom* of its panel with the
  canvas above it empty (owner screenshot 2026-07-14). Two compounding causes fixed:
  (1) the schematic canvas ballooned taller than its tab viewport — the Geometry
  "Schematic" tab shares a `QTabWidget` stack with the tall "Inputs" tab, whose full-height
  derived-angles readout inflated the shared minimum height; each non-canvas sub-view is now
  wrapped in its own `QScrollArea` so the canvas fills the viewport (with a sensible
  `Expanding` policy + 360×360 minimum + concrete `sizeHint`) instead of growing unbounded;
  (2) the orthographic fit anchored the scene origin low (`cy = 0.72·height`) with a
  width-limited scale, so on a too-tall canvas the scene clustered near the bottom — the
  camera now scales the projected scene bounding box to the *live* paint rect with a
  symmetric margin and centres it on both axes, recomputed every paint so the scene stays
  centred and framed on resize (short / tall / wide). No computed results change; golden
  untouched.

### Added
- **GUI 3D geometry viewer — interactions: angle annotations, shape library, RPY triad
  (GUI plan Phase 7 Part B, ADR-0007).** The Geometry "3D View" becomes a split of the
  viewport and a new accordion side panel (`GeometryAnglePanel`). (1) **Click-to-reveal
  angle annotations:** per-angle toggles reveal an arc (off-nadir η, sun-zenith θ_s,
  phase-angle α_t) with the numeric value pinned from `stage_outputs["geometry"]` verbatim
  (never recomputed; the phase angle is symbol-only as it has no stage-output truth), split
  target-frame vs ground-frame to match the Phase-5 readout — which the panel **shares**,
  not duplicates. (2) **Target shape library:** a shape combo populated from the
  `source.target.shape` schema `enum_values`; selecting a shape performs one `sensor.set`
  and re-renders. (3) **RPY triad:** an on-target body-axes gizmo (pink=Roll / green=Pitch /
  purple=Yaw) rendered from `source.target.shape_{yaw,pitch,roll}_rad`; editing those tilts
  the triad and the orientation-dependent geometry. A **binding consistency test** asserts
  the viewer's local angle recomputation (ported `geometry.js` math, used only for
  camera/picking) agrees with the stage outputs within 1e-9 rad — the stage is the single
  source of angle truth. In-scene VTK picking and platform-attitude are deferred
  (CU-124/CU-122). View-only — no computed results change.
- **GUI 3D geometry viewer — static bound scene (GUI plan Phase 7 Part A, ADR-0007).** The
  Geometry stage center becomes a two-tab composite — **Inputs** (the mode forms + angle
  readout) and **3D View** — the latter embedding a new `GeometryViewer`
  (`radiant.gui.viewer`). It renders a not-to-scale PyVista schematic of the sun / sensor /
  target geometry (ground reference, target/regime glyph, the four vectors, sun/sensor
  glyphs, deconflicted leader labels) bound to `stage_outputs["geometry"]` + the final
  optics regime after each evaluate, via the new `ViewerState` adapter. The Qt-free scene
  library is lifted from `dev_tools/geometry_gui_v2` into `radiant.gui.viewer.scene`
  (imports no physics stage; gui → api + core kept). Viewport background and label/leader
  chrome follow the design-system `Theme`; the physics-domain glyph palette
  (sun = amber, sensor = blue, normal = green, target = teal) lives in one allowlisted
  module. Three render backends (live `QtInteractor` / static offscreen image / actionable
  degradation panel) keep the app alive where OpenGL/VTK is unavailable. `StageComposition`
  and `StageSubView` gained a `geometry_viewer` field. Angle-arc annotations, the shape
  library, and the RPY triad are deferred to Part B. View-only — no computed results change.
- **GUI Geometry screen — stage-0 input-mode forms + frame-grouped derived-angle readout
  (GUI plan Phase 5).** The Geometry stage's contextual center gains a `GeometryModeForm`
  (new `radiant.gui.widgets.geometry_mode_form`, over a Qt-free `radiant.gui.geometry_modes`
  manifest): a mode selector per family (viewing V0–V4 / solar S1–S3+night / kinematics
  direct-or-circular) with only the active mode's fields editable, all fields schema-driven,
  each edit one `sensor.set` through the shared Parameter Editor (validate-on-clone reject,
  display-unit aware). The `GeometryReadout` now groups its values by reference frame
  (target-frame vs ground/platform frame vs resolution), each with unit and symbol. An
  over-/under-specified geometry (the stage's `GeometrySpecificationError`) highlights the
  offending mode selector and navigates to the Geometry screen. `StageComposition` gained a
  `geometry_form` field. View-only — no computed results change.
- **GUI per-stage center tabbed sub-view hook (provision only, deferred content).** A stage's
  center composite can now be presented as multiple named tabs: `StageComposition` (in
  `radiant.gui.stage_views`) gained an optional `subviews` field of the new `StageSubView`,
  and `StagePane` renders a `QTabWidget` when two or more are declared, falling back to the
  current single pane otherwise. **No v1 stage declares any sub-view** — every stage renders
  exactly as before; this is the seam a later per-stage phase fills. View-only — no computed
  results change.
- **`radiant.api.stage_output_units.stage_output_unit(stage, key)` — canonical display unit
  for a scalar stage output.** Stage outputs are computed values with no per-field unit
  metadata (Gap 87); this new public accessor (and its `STAGE_OUTPUT_UNITS` table) supplies
  the canonical unit string a renderer needs to honour the R-UNITS rule. View-only — no
  computed results change.

### Fixed
- **GUI Geometry derived-angles readout had a short scrollbar that did not span the table
  (owner report 2026-07-14).** On the Geometry "Inputs" tab the derived-angles readout sat
  in its own inner scroll area *inside* the stage pane's outer scroll; the tall input form
  above it crushed the readout to a ~100 px sliver, so its inner scrollbar covered only that
  sliver instead of the full table. `GeometryReadout` gains a `scrollable` flag (default
  `True`, keeping the inner scroll for the compact 3D-view accordion side panel); the Inputs
  tab now uses `scrollable=False` so the table sizes to its full content and the pane's outer
  scroll owns scrolling — one full-height scrollbar spans the whole form + derived table. The
  stage pane omits its trailing stretch when a filling section (the readout or the 3D-view
  split) is present so that section absorbs the slack. View-only — no computed results change.
- **GUI 3D geometry viewer did not visually update on re-render (owner report 2026-07-14).**
  Parameter edits, re-evaluations, and annotation/triad toggles reached the viewer, but the
  embedded viewport showed the stale scene. On the live pyvistaqt `QtInteractor` (macOS /
  real display) a `clear()` → rebuild → `render()` sequence does not reliably repaint the GL
  widget — the VTK `render()` alone can be a no-visual-op after a scene rebuild. `_render_live`
  now follows the VTK `render()` with an explicit Qt `update()` of the interactor widget, and
  the static-image backend now calls `update()` after `setPixmap`, so both backends repaint on
  every re-render. The user's current camera is preserved (PyVista's `camera_set` flag survives
  `clear()`, so the default-camera call is a no-op after the first render — the view is never
  snapped back). View-only — no computed results change.
- **GUI Evaluate button relocated to the right-rail footer (owner feedback 2026-07-13).**
  The accent Evaluate (F5) button sat in a thin run bar in the center of the window, which
  read as out-of-place. It now lives as a persistent footer pinned at the bottom-right of
  the right rail (the persistence area), below the Messages panel, so it never scrolls away.
  The center run bar is removed. F5 and Run ▸ Evaluate still drive the same evaluation.
  View-only — no computed results change.
- **Twin-axis plot y-labels clipped at the figure edges in the narrow embedded pane (owner
  feedback 2026-07-13).** The Atmosphere plot's rotated y-axis labels were spelled-out and
  long — `"Transmittance τ_atm (dimensionless)"` and `"Path radiance L_path (W/m²/sr/µm)"` —
  and overflowed the figure edges at GUI embedded width even under constrained_layout.
  `plot_atmosphere_spectral` now labels the axes with the symbol + unit form only
  (`"τ_atm (dimensionless)"`, `"L_path (W/m²/sr/µm)"`); the unit is always retained (R-UNITS).
  All other builders already used short symbol + unit labels. View-only — no computed
  results change.
- **MTF Budget overlay legend blanketed the curves in the narrow embedded pane (CU-117).**
  `plot_mtf_terms` drew one legend entry per term — ~16 for an 8-contributor × x/y overlay —
  inside the axes, covering much of the curve area at GUI embedded width. Each contributor's
  `_x`/`_y` are now merged into a single legend entry when they coincide (~16 → ~8 labels;
  differing x/y keep both), and the legend is placed below the axes in a compact multi-column
  block so it never overlaps the curves. All contributor curves are still plotted. View-only —
  no computed results change.
- **GUI stage Outputs readout showed dimensional values as bare numbers (R-UNITS
  violation).** The per-stage Outputs readout inferred a value's unit from the output key's
  trailing suffix, so keys without a canonical suffix (`optics.A_collect`, `optics.Omega_pixel`)
  rendered unit-free and a mid-key token (`readout.signal_e_final`, `spectral_integration.e_rate_per_s`)
  was mislabelled or dropped. Units now come from the single authoritative framework table
  (`radiant.api.stage_output_units`): `A_collect` → `m²`, `Omega_pixel` → `sr`,
  `e_rate_per_s` → `e-/s`, etc. Booleans/strings and genuine dimensionless numerics stay
  unit-free. View-only — no computed results change.

- **GUI contextual per-stage center + global Inspector (contextual-layout retrofit
  Step B, arch doc §4.4 / §4.6 / §4.7).** Selecting a stage in the signal-chain strip now
  makes the center show **only that stage's contextual composite** — its outputs readout
  (scalar `stage_outputs` values with units, or the performance metric surface), its
  plot(s) drawn from the public `result.plot.*` accessors, and its relocated detail content
  (the MTF per-term table + overlay on Optics, the noise-budget table + bars + click-explain
  on Detector, the geometry angle readout on Geometry). This replaces the single shared
  canvas. Every Outputs / Metrics row carries a **pin affordance** that adds the value to
  the right-rail Pinned panel — a stage-output pin re-reads `stage_outputs` on each run; a
  metric pin reads the metric surface (CU-115 Step-B clause delivered). A new global
  **Inspector** tool (Tools → Inspector / the menu-bar `◈ Inspector` button, `Ctrl+I`) opens
  the full `inspect_result(result)` variable dump as a collapsible tree; it is disabled
  until the first evaluation.
- **GUI contextual-layout right rail — Pinned / Edit Config (YAML) / Messages
  (contextual-layout retrofit Step A, arch doc §4.5).** A persistent right-side dock now
  carries three sections: a **Pinned** panel of metric cards (default set = SNR · NEDT ·
  NIIRS · GSD · MTF@Nyquist, each value + unit sourced from `ChainResult.metric_records()`,
  with unpin and a `+ Pin…` picker over the metric surface; session-scoped); an **Edit
  Config (YAML)** button that opens a roomy modal editor preloaded with the current config
  and re-parses the edited text through `Sensor.load` on Apply (invalid YAML shows the
  actionable error and leaves the live config untouched — validated on a throwaway sensor);
  and a **Messages** panel listing chain warnings and errors (the widened warning strip),
  each clickable to its full-text dialog. The full-well saturation banner stays in the
  center column (high-signal, non-dismissible).
- **GUI detail tabs — Spectral, MTF, Noise Budget, Variables, YAML (GUI plan
  Phase 4 Task B).** The bottom detail dock's five tabs are now live, each its own
  widget class and each populated on every successful evaluation from a public API
  surface (no plotting or physics in GUI code): **Spectral** (a themed selector over
  `result.plot.spectral_source()` / `spectral_atmosphere()` / `spectral_inband()`,
  showing the accessor's actionable message when a frame is absent for the regime);
  **MTF** (per-contributor MTF@Nyquist table discovered from the result's
  `mtf_budget.per_term_at_nyquist`, x/y columns, dimensionless → bare numbers, plus the
  `result.plot.mtf()` overlay); **Noise Budget** (per-term σ table in e- RMS from
  `result.noise_terms`, `result.plot.noise_budget()` bars, and a click-a-term describe
  panel from the `NoiseTerm` metadata); **Variables** (`radiant.api.inspect.inspect_result`
  re-rendered as a collapsible tree); and **YAML** (read-only provenance-coloured current
  config via `Sensor.save`, with an Export… button — the tab's only file I/O). Units on
  every numeric cell (R-UNITS); all styling from theme tokens. Visual/UX capability only;
  results-neutral.
- **Spectral-radiance figure accessors on `result.plot.*` (Gap 86).** The
  `ResultPlotNamespace` gains three accessors — `spectral_source()` (target +
  optional background at-aperture radiance vs λ [W/m²/sr/µm]),
  `spectral_atmosphere()` (τ_atm(λ) [dimensionless] and L_path(λ) [W/m²/sr/µm]
  on twin unit-labelled axes), and `spectral_inband()` (band-filtered
  post-optics radiance vs λ [W/m²/sr/µm]) — plus two supporting module
  functions in `radiant.api.plot` (`plot_spectral_multi`,
  `plot_atmosphere_spectral`). Each accessor plots only real stored frames /
  stage outputs (no recomputation) and raises an actionable `ApiValidationError`
  when the required frame is absent. This carries the arch-doc §4.4 Source /
  Atmosphere / Spectral-Integration default views and unblocks the GUI Phase 4B
  Spectral detail tab. Public-surface addition; results-neutral.
- **GUI stage-strip navigation, per-stage default visualizations, and live health
  dots (GUI plan Phase 4 Task A).** The 9-stage signal-chain strip is now clickable:
  a click scrolls the parameter panel to that stage's namespace group and swaps the
  central canvas to the stage's default visualization (arch doc §4.4) — the derived
  geometry angle/range **readout** (values with units + symbols) for Geometry, an
  MTF overlay (`result.plot.mtf()`) for Optics/Platform/Performance, a noise-budget
  bar chart (`result.plot.noise_budget()`) for Detector/Readout, and a themed
  "visualization not yet available (Gap 86)" panel for Source/Atmosphere/Spectral
  Integration whose spectral-radiance figure the `result.plot` surface does not yet
  carry (no faked figure — ground rule §4.1). Every figure is one call on the public
  `result.plot.*` surface (no plotting in GUI code). The per-stage **health dots**
  now update live: gray/stale before a run and on any parameter edit, green after a
  clean run, yellow on a run with chain warnings (whole-run, not per-stage), red on a
  failed evaluation. Selecting a stage highlights its chip. Visual/UX capability
  only; results-neutral.
- **GUI display units — rows and the Parameter Editor show the user's unit (GUI
  plan Phase 3 checkpoint punch-list round 2, owner feedback 2026-07-13).** A
  parameter row now displays its value in the unit the user chose (an altitude set
  as 500 km reads `500 km`, not `500000 m`), not always the schema canonical/input
  unit. Committing a Parameter-Editor edit with an explicit unit adopts that unit as
  the row's display unit; the editor opens on it (Current line, value field, unit
  combo, and bounds), and inline Value-column edits interpret the typed number in it
  and write it back with the same unit (type `550` into a km row → `550000 m`
  canonical, row shows `550 km`). All canonical↔display conversion routes through the
  public `radiant.api.units` seam (no ad-hoc GUI maths); a unit that is not soundly
  convertible (offset/one-way) falls back to the canonical unit. The unit suffix is
  always part of the string. Session-scoped (QSettings persistence lands in Phase 9).
  Visual/UX capability only; results-neutral.
- **GUI in-window chain-warning strip (GUI plan Phase 3 checkpoint punch-list round
  2, owner feedback 2026-07-13).** Chain `UserWarning`s (saturation clip, NIIRS
  extrapolation, …) — which previously printed only to the terminal — are now
  captured by the evaluation worker and shown in a themed **warn-token** strip
  between the KPI badges and the canvas, reading `⚠ N warnings` with the first
  message inline and, clicked, opening a dialog listing all messages verbatim. The
  strip clears on a warning-free evaluation. Captured warnings are also re-logged, so
  nothing is swallowed (Rule 17). Visual/UX capability only; results-neutral.
- **`radiant.api.units.inverse_convert` re-export.** The public units seam now
  re-exports `inverse_convert` (canonical → display-unit) alongside `convert` and
  `_CONVERSIONS`, the sanctioned surface for output-side conversion (used by the GUI
  display-unit feature). Additive-offset and one-way units remain unregistered, so it
  is sound (invertible) for every registered conversion.
- **GUI Parameter Editor dialog (GUI plan Phase 3 checkpoint punch-list).** The
  parameter panel gains a full-detail editor box that opens on a parameter
  (double-click its Parameter or Source column, or right-click → **Edit…**) and
  shows the complete dot-path the narrow tree truncates, the schema description,
  the current value with unit + provenance, the bounds, and the derived/read-only
  state. It edits the value with a per-dtype control and, for a dimensional
  parameter, a **unit selector** populated from the units the conversion registry
  can convert to the canonical unit (public `radiant.api.units` seam, never a
  hardcode); it previews the resulting canonical value (enter `8` `km` → `= 8000 m`)
  and commits one `sensor.set(dotpath, value, unit=…)`, validated on a clone so a
  rejected value never touches the live sensor and its actionable error renders in
  the dialog. Derived parameters open read-only. The Value column keeps its
  existing fast in-place editor (two complementary edit paths). Visual/UX capability
  only; results-neutral.
- **GUI evaluate loop, live metric badges, and saturation banner (GUI plan
  Phase 3 — Milestone A / D2).** `radiant gui` now runs the full chain: opening
  or editing a config evaluates `sensor.evaluate()` on a background worker thread
  (the Qt thread never runs the chain), driven by Run → Evaluate (F5) or the
  accent Run button, and auto-re-evaluated after a 200 ms debounce on any
  parameter edit (full chain — no incremental engine, CU-079). The five KPI
  badges (SNR · NEDT · NIIRS · GSD · MTF@Nyquist) fill from the `ChainResult`
  metric surface with each value's unit sourced from the result metadata
  (`metric_records()`), a result-typed metric failure shows its `failure_reason`
  (never a blank), and the central matplotlib canvas renders the existing
  `result.plot.*` figure (default: the MTF overlay). A failed evaluation keeps
  the previous result on screen, flagged stale ("last evaluation failed"), and
  shows the actionable error (`RadiantError` → what/why/action; otherwise a
  traceback dialog). A **non-dismissible saturation banner** appears whenever
  `result.well_status().is_saturated`, showing the fill fraction and the
  accumulated-vs-capacity electrons with units, and clears on the next
  unsaturated result. Visual/UX capability only; the GUI is results-neutral (no
  computed-result or public-API change).
- **`ChainResult.well_status()` — full-well saturation on the result surface
  (CU-101).** The readout stage's well-capacity clip decision is now a
  first-class accessor returning a `WellStatus` record (exported as
  `radiant.api.WellStatus`): `.status` (`"ok"`/`"clipped"`, equal to
  `stage_outputs["readout"]["well_status"]`), `.is_saturated`, `.fill_fraction`
  (dimensionless), `.total_well_e` [e-], and `.full_well_capacity_e` [e-]. The
  readout stage additionally publishes `well_fill_fraction`, `total_well_e`, and
  `full_well_capacity_e` to `stage_outputs["readout"]` (serialization-safe, so
  the surface survives `save()`/`load()`). Lets the GUI saturation banner — and
  scripting users — read a metric instead of digging into `stage_outputs`; the
  underlying silent-clip trap (Gap 65) is now surfaced. Public-surface addition
  only; no computed-result change.
- **Schema-driven parameter tree in the GUI (GUI plan Phase 2, Task A —
  read-only half).** The parameter dock now populates a Parameter / Value /
  Source tree generated entirely from `Sensor.parameter_defs()` (never a
  transcribed list), grouped by dot-path namespace in chain order (geometry
  first). Each row shows the resolved value with its schema unit suffix; derived
  parameters carry a ⚡ marker; the Source column shows provenance (config /
  default / derived / user-set) read from the resolved set. A live filter box
  narrows rows by substring across dot-paths. Launched on a config the tree is
  populated; launched bare it shows a "no configuration loaded" state. Visual/UX
  capability only; no computed-result or public-API change.
  **Task B (editing):** non-derived rows are now editable in place — a
  schema-typed editor (combo for enums with schema-sourced choices, checkbox for
  bools, spin box for ints, line edit for floats/strings), each commit one
  `sensor.set`; rejected values (bounds / enum / consistency-group) render their
  actionable what/why/action inline and in a modal and never stick; right-click
  gives Copy dot-path, Explain (`sensor.explain`), and Reset to Default
  (`sensor.reset`).
- **`radiant gui` entry point and the `radiant.gui` package (GUI plan Phase 1,
  Task A).** A new PySide6 desktop-GUI shell — `launch_gui(sensor=None)` and the
  `radiant gui [CONFIG.yaml]` CLI subcommand — behind a new optional dependency
  group, `pip install "radiant[gui]"`. The GUI is a view over the scripting API
  (no physics, no computed-result changes); this phase ships only the window
  shell (menus, empty stage strip, dock panels, status bar). Without the `gui`
  extra installed, `radiant gui` raises an actionable error naming the remedy and
  the rest of RADIANT is unaffected. Not results-affecting.
- **GUI design-system theme (GUI plan Phase 1, Task B).** The shell now boots with
  the ratified design-system look (arch doc §8): a **light** QSS theme is applied at
  startup (the v1 launch default) with a **dark** alternate deriving from the same
  token set. `radiant.gui.themes` is the single owner of every colour, font, and
  spacing value; a mechanical test blocks any hardcoded colour/font literal elsewhere
  in the GUI. Visual change only — no computed results, no public API change beyond
  the internal `themes` helpers.

### Fixed
- **Embedded matplotlib plots no longer clip titles / axis labels / legends
  (owner feedback 2026-07-13).** Every `radiant.api.plot` builder (and thus every
  `ResultPlotNamespace` / `result.plot.*` figure) now uses matplotlib constrained
  layout instead of a one-shot `tight_layout()`, so titles, axis labels, and legends
  keep a reserved margin and re-fit on resize — fixing the cut-off "Source spectral
  radiance" title, the "MTF Budget" title overlapped by its legend, and edge-crowded
  axis labels in the GUI (and improving `savefig` output for script users too). The
  dense MTF-terms legend now sits inside the axes so it never reaches the title band at
  any canvas width. In the GUI, the MTF per-term table's first column shows its full
  "Contributor" header (was truncated to "trib…") and every column sizes to its
  contents; the MTF/noise panels' embedded canvases keep a minimum height so a short
  window scrolls rather than collapsing the figure. Visual only — no computed results
  changed.
- **GUI Parameter-Editor unit dropdown no longer clips (GUI plan Phase 3
  checkpoint punch-list round 2, owner feedback 2026-07-13).** The unit selector's
  popup previously truncated unit names to ~2 characters ("cr", "kı"); the combo now
  sizes to its contents and its popup view is sized to the widest unit label, so every
  unit reads in full. Visual only.

### Changed
- **Results-affecting: Earth radius unified to 6371.0 km mean (CU-097).**
  RADIANT previously used two Earth radii: the atmospheric slant-path /
  airmass geometry ran on the WGS-84 equatorial radius (6378.137 km) while
  slant range, incidence, ground range, and orbital kinematics used the
  6371.0 km mean radius. Both now use the single canonical
  `constants.R_EARTH_M = 6.371e6 m` (IUGG / US Standard 1976 mean). Nadir
  results are unchanged; off-nadir atmospheric path lengths and airmass
  shift at the sub-percent level (−0.11 % radius, e.g. the 60° reference
  slant path drops 195601 → 195566 m, ~0.018 %), in the
  correct-consistency direction (one triangle, one Earth). No golden
  baseline changed (all 14 sit at the nadir default).

### Removed
- **GUI bottom detail-tabs dock (contextual-layout retrofit Step B, arch doc §4.7).**
  The bottom `DetailTabs` dock and its five tab widgets are removed; their content is
  **relocated**, not discarded: the MTF and Noise Budget tabs became the embeddable
  `MtfPanel` / `NoiseBudgetPanel` (Optics / Detector center views), the Spectral tab's
  three figures became per-stage plot sections (Source / Atmosphere / Spectral
  Integration), the Variable Explorer tab became the global `InspectorDialog` tool, and
  the read-only YAML tab was superseded by the Step-A right-rail Edit Config (YAML) modal.
  The `View → Show/Hide Detail Panel` action is removed with the dock it toggled.
- **GUI global metric-badge row and floating warning strip (contextual-layout
  retrofit Step A).** The `KpiBadgeRow`, `MetricBadge`, and `WarningStrip` widget
  classes are retired: the metrics relocated to the right-rail Pinned cards and the
  warnings to the Messages panel (nothing user-facing is lost — badges → pinnable
  cards, strip → Messages). The accent Evaluate button that lived in the badge row
  moved to the central canvas run bar.
- `radiant.core` no longer exports `ObserverGeometry`, `TargetGeometry`,
  `SceneGeometry` (CU-094, ADR-0006 Phase 4). The flat-Earth scene
  dataclasses had zero consumers outside their own tests and were
  superseded by GeometryStage + `core.viewing_triangle`. The module's
  live functions (`slant_range_spherical_m`, `incidence_angle_rad`,
  Euler helpers) are unchanged.

### Deprecated
- `platform.h_sensor` → folded into `geometry.sensor_altitude_m` (CU-090,
  ADR-0006 Phase 3). One sensor altitude, one owner; the old name keeps
  working via `deprecated_aliases` (warn-and-redirect) for one release
  cycle. The no_atmosphere 'space' Earth-limb check now reads the
  canonical name (its error message names `geometry.sensor_altitude_m`).

### Added
- **Range-consistency enforcement (CU-093).** `geometry.target_range_m`
  set together with an explicit viewing angle now must agree with the
  angle-implied slant range within 1% or GeometryStage raises an
  actionable `GeometrySpecificationError`. A user range combined with
  *defaulted* viewing angles (mode V0) keeps the historical behavior —
  range drives regime/detection, nadir drives spatial metrics — but the
  previously silent disagreement now emits a `UserWarning` naming both
  distances.

### Fixed
- Lab/bench configurations with `geometry.sensor_altitude_m = 0` (sensor
  and target collocated) no longer trip the GeometryStage viewing
  triangle: the degenerate case publishes `None` slant/ground/incidence
  and the chain proceeds on the V0 range/regime path. (Regression
  introduced by the Phase-1 stage landing earlier today; caught in the
  CU-090 call-site audit — lab scenario scripts are not in the test
  suite.) Uplooking (`sensor below target`) still raises, per the
  owner-ratified v1 policy.

### Changed
- **Geometry input modes now steer the whole chain (ADR-0006 Phase 2).**
  SourceStage adopts the GeometryStage-published scene LOS (so the off-nadir /
  ground-range / elevation / site+time / night modes reach the atmospheric
  assembly and shape view directions); PlatformStage consumes the published
  slant range for velocity smear; PerformanceStage consumes the published
  slant range, incidence angle, ground range, and ground speed (GSD, ground
  metrics, diffraction ground projection, access rate — `circular_orbit`
  now yields `access_rate_m2_s` with no manual speed entry).
- **Results-affecting (off-nadir configurations only):** GSD, ground range,
  diffraction ground projection, and velocity smear now derive from the
  canonical target-side zenith θ_o via one spherical triangle
  (`core.viewing_triangle`, R_E = 6378.137 km), where they previously
  re-derived from `geometry.path_zenith_rad` *misread as the sensor-side
  off-nadir angle* on a 6371 km Earth (CU-096; CU-097). At nadir — every
  shipped golden baseline — values are unchanged (verified byte-identical).
  At off-nadir the new values are the physically consistent ones; e.g. at
  h = 500 km, θ_o = 45°: slant range 683.1 km (was 737.3 km when 45° was
  treated as the sensor-side η) — metrics that scale with slant range shrink
  by ~7 % there, more at steeper angles.

### Added
- `performance.gsd.compute_gsd_from_geometry` — GSD from already-derived
  (slant range, incidence angle); the legacy `compute_gsd(altitude, angle)`
  remains for direct callers (CU-096 tracks retiring it).

### Added
- **GeometryStage — geometry is stage 0 of the chain (ADR-0006).** The signal
  chain is now `geometry → source → … → performance` (9 stages;
  `ChainResult.history` and provenance `active_models` gain a leading
  `"geometry"` entry). The new stage owns the `geometry.*` namespace, resolves
  the scene-geometry input mode, and publishes every derived quantity once via
  `stage_outputs["geometry"]` (`los_geometry`, `theta_o_rad`, `eta_rad`,
  `slant_range_m`, `ground_range_m`, `incidence_angle_rad`, solar geometry,
  ground speed, and the mode labels). Zero numerical drift: existing
  configurations resolve exactly as before (all goldens byte-identical);
  downstream stages still read the canonical parameters until the Phase-2
  re-plumb (`docs/plans/Geometry_Stage_Plan.md`).
- **New geometry input modes** (published by the stage; chain-steering lands
  with Phase 2): `geometry.sensor_off_nadir_rad` (off-nadir η — wires the
  CU-005-reserved `theta_o_from_eta` converter), `geometry.ground_range_m`
  (surface-arc entry), `geometry.elevation_angle_rad` (grazing-angle entry),
  `geometry.solar_elevation_rad`, site+time solar inputs
  (`geometry.site_latitude_rad`, `geometry.day_of_year`,
  `geometry.local_solar_time_h`, `geometry.ltan_h` — wires the previously
  consumer-less `core.solar_geometry`), and `geometry.circular_orbit`
  (derives ground-track speed and orbital period from altitude via
  `core.orbit`). Over-specified or mutually inconsistent entries raise the
  new actionable `radiant.geometry.GeometrySpecificationError`.
- `core.viewing_triangle` — θ_o-referenced spherical viewing-triangle
  solutions (`eta_from_theta_o`, `slant_range_from_theta_o_m`,
  `ground_range_from_theta_o_m`, `theta_o_from_ground_range_m`).

### Deprecated
- `source.target.range_m` → renamed `geometry.target_range_m` (ADR-0006).
  The old name keeps working via `deprecated_aliases` (set/get redirect with
  a `DeprecationWarning`) for one release cycle.

### Changed
- Uplooking configurations (`geometry.sensor_altitude_m` at or below
  `geometry.target_altitude_m`) are now rejected by GeometryStage at the head
  of the chain with an actionable error, instead of surfacing later as the
  atmosphere Earth-limb check. Same v1 policy (uplooking rejection,
  owner-ratified 2026-07-11); earlier, clearer error site.

### Added
- MODTRAN downwelling zeroing now warns (Gap 81, partial): a
  MODTRAN-backed atmospheric state emits a `UserWarning` that the
  downwelling sky emission (`atm_emission_down` / `E_sky_thermal`) and
  scattered-solar sky radiance are set to zero (the standard IEMSCT=2
  tape7 carries no downwelling column) — switching `atmosphere.model`
  from `simple` to `modtran` no longer *silently* drops the thermal-band
  background terms. The full fix (ingest a separate downwelling run via
  `atmosphere.modtran.tape7_down_path`) is deferred on MODTRAN access.

### Fixed
- **Results-affecting (`simple` atmosphere, wavelengths > 5 µm only):**
  the aerosol Ångström power law is now clamped at the MWIR–LWIR boundary
  (5 µm) instead of extrapolating toward zero into the LWIR, where real
  aerosol extinction is absorption-dominated and roughly flat (CU-088).
  Beyond 5 µm the extinction is frozen at its 5 µm value (raising LWIR
  aerosol extinction vs the old extrapolation), and `SimpleAtmosphere`
  warns once per run when the clamp engages. MWIR (≤ 5 µm) and the golden
  baseline are unchanged; the clamp only affects LWIR `simple`-model runs.

### Changed
- **Results-affecting (only when `dark_activation_energy_eV > 0` and the
  reference was left at its default):** `detector.dark_reference_temperature_K`
  default changed 300 K → 77 K to match the `detector_temperature_K` default
  (CU-081), so the default config is self-consistent. With the default
  `dark_activation_energy_eV = 0` the dark rate is temperature-inert, so
  `dark_e` is unchanged for the default config and the golden baseline.

### Added
- Enum validation on `readout.tdi_mode` (`analog`/`digital`) and
  `detector.noise_regime` (`imaging`/`detection`) (CU-076): a typo now
  raises at resolve instead of silently selecting the wrong model
  (analog scaling / dropped spatial noise).
- Dark-current temperature-inertness warning (CU-081): when
  `detector_temperature_K` differs from the reference and
  `dark_activation_energy_eV = 0`, `DetectorStage` warns that the
  temperature setting has no effect on dark noise (a GUI temperature
  slider that silently does nothing).
- Validation hardening (CU-085): `Tolerance` now validates its
  distribution and required spread parameters at construction (a
  parameter-less gaussian previously sampled zero spread silently); the
  consistency-group over-specification check no longer skips when the
  first parameter lacks a derivation rule; velocity smear warns instead
  of silently returning 0 when altitude/integration time is missing; the
  IPC y-axis MTF uses the y pitch (was x — wrong for rectangular pixels);
  the CLI provenance version reads `radiant.__version__` (was hardcoded
  "0.1.0"); the `pixel_pitch_y_um` "defaults to x pitch" description
  (false — it is required) is corrected.
- SCNR and in-chain point-source detection range (Gap 77): new `scnr`
  metric (signal-to-clutter-plus-noise — target contrast over the
  clutter-inclusive total noise √(σ_temporal² + σ_spatial²), the detection
  figure of merit, unlike `snr`/`contrast_snr` which respect
  `noise_regime`); new `detection_range_m` metric, computed in the
  point-source regime by bisecting the Beer-Lambert solver to the range
  where SNR falls to the new `performance.detection_snr_threshold`
  parameter (default 5.0). New modules `radiant.performance.scnr` and a
  `radiant.performance._schema`. The detection range uses a constant
  atmospheric extinction (exact in vacuum; first-order for atmospheric
  paths) — the geometry-aware slant-path refinement is deferred (Gap 77
  narrowed). The wider acquisition-metric family (Pd/ROC, Johnson DRI,
  NEΔL/NEΔρ, D*/NEP/NEI) stays library-only pending GUI-phase surfacing
  (Gap 78).
- Orbit-derived ground velocity + duplicate collapse (Gap 75):
  `Sensor.set_ground_velocity_from_orbit()` derives
  `platform.ground_velocity_m_s` from `geometry.sensor_altitude_m` via the
  circular-orbit sub-satellite ground-track speed (`radiant.core.orbit`,
  previously wired to nothing). `platform.ground_velocity_m_s` and
  `geometry.ground_speed_m_s` — the same physical quantity, previously two
  independent fields that could silently disagree — are now a collapsed
  identity consistency group: setting either derives the other, and
  setting both to disagreeing values raises an over-specification error.
  (The analogous altitude duplicate `sensor_altitude_m` vs
  `platform.h_sensor` is deferred — CU-090.)
- Pushbroom/TDI scan-timing feasibility guard (Gap 74, minimum slice):
  when `platform.ground_velocity_m_s` is set, `PerformanceStage` computes
  the per-line dwell `t_dwell = GSD_along / v_ground`, stores it as the new
  `max_integration_time_s` metric, and warns when
  `spectral_integration.integration_time_s` exceeds it (the along-track
  image smears more than one ground sample per integration — an unphysical
  TDI timing whose SNR would otherwise look authoritative). New module
  `radiant.performance.scan_feasibility`. Parameter-gated: inert without a
  ground velocity, so existing results are unchanged.

### Fixed
- `ChainResult.signal_at(DN)` (and DN propagation generally) no longer
  raises when the well fully saturates (`signal_e_final = 0`) — a state
  now reachable when a bright point-source background pedestal fills the
  well (Gap 73). The `post_readout→dn` transfer factor falls back to the
  linear `1/gain` conversion, so a saturated pixel reports 0 DN instead
  of a missing-transfer-factor error. New readout output `gain_e_per_dn`.
- **Results-affecting (IPC coupling > 0 only):** the PSF-path IPC kernel is
  now resampled to the PSF sample grid (CU-083). The raw 3×3 kernel was
  convolved onto the sub-µm PSF grid, placing its α couplings one *sample*
  (not one pixel pitch) away — so the PSF-path IPC blur was orders of
  magnitude too small and diverged from the analytic MTF-product term.
  Now `ipc_kernel_pitch_spaced` places the couplings at ±pitch, so RER,
  FWHM, EE, and MTF-at-Nyquist reflect the correct IPC degradation
  (e.g. MTF at Nyquist × (1−4α)) and the dual-path consistency check
  passes. At `ipc_coupling = 0` (default, golden baseline) no kernel is
  built — golden unchanged. New `detector` stage output `ipc_kernel_psf`;
  the raw 3×3 `ipc_kernel` output is retained for provenance.
- **Results-affecting (fill_factor < 1 only):** `detector.fill_factor` now
  couples consistently across all three affected paths (CU-074). It is the
  areal photosensitive fraction, so a square photosite has linear width
  `pitch·√FF`: this width now drives BOTH the PSF-path pixel-aperture
  kernel and the MTF-product pixel sinc (previously the sinc used the full
  pitch, diverging the two Rule-4 paths and warning on every FF<1 run), and
  the collecting area `pitch²·FF` scales the radiometric signal (previously
  the full-pitch area was used, overcounting signal). Nearfield and stray
  electrons also scale by FF. Direction at FF<1: signal ↓ by factor FF,
  pixel MTF ↑ (narrower photosite). At FF=1 (the default and the golden
  baseline) every change is an exact no-op — golden unchanged.
- **Results-affecting (point-source regime only):** point targets now sit
  on a full-pixel background pedestal (Gap 73). Previously the
  point-source branch hardcoded `background_e = 0`, so a compact target
  against a bright background (daytime sky, sunlit cloud) had zero
  background shot noise and zero well fill from the sky — optimistic
  SNR/detection-range, and a discontinuous noise budget across the
  sub-pixel→point-source boundary. Now `background_e` is the full-pixel
  pedestal (same formula as the extended/sub-pixel background reference)
  when an at-aperture background frame exists; it feeds background shot
  noise and the readout well-fill (regime-gated — the pedestal is
  additional well charge only in point-source, where signal_e is
  target-only). Target signal and `contrast_e = signal_e` are unchanged;
  extended/sub-pixel results and the golden baseline are unchanged.
  Direction: point-source SNR against non-dark backgrounds decreases;
  magnitude scales with background radiance.

### Added
- Progress and cancellation hooks (Gap 72): `progress(done, total)` and
  `cancel() -> bool` keyword arguments on `Sensor.sweep`/`sweep_2d`/
  `monte_carlo`/`sensitivity` (and the underlying API functions) and
  `BatchRunner.run`. Cancellation raises the new
  `radiant.api.OperationCancelledError` (a `RadiantError` carrying
  operation/done/total). `solve_for` is excluded (unpredictable
  iteration count).
- `UnknownParameterError` (CU-073): typo'd parameter names in
  `set`/`get`/`reset`/`set_tolerance`/`parameter_def` now raise a
  `RadiantError` subclass (co-inheriting `KeyError` for back-compat)
  with the did-you-mean suggestion — the documented `except
  RadiantError` boundary now catches the most common user mistake.

### Fixed
- Parallel sweep crash (CU-072): `n_workers > 1` no longer dies with an
  unhandled `PicklingError` when the run function or its returned
  `ChainResult` cannot pickle (the common case — results carry
  `MappingProxyType` fields). Pickling failures are now caught at both
  submit time and result time and the sweep falls back to sequential
  with a logged warning, as originally documented.

### Added
- Non-scalar input reachability (Gap 68): `Sensor.set_stage_output(group,
  key, value)` and `Sensor.evaluate(extra_stage_outputs=...)` forward
  pre-chain injections to every evaluation, including all trade studies
  (sweep/sweep_2d/monte_carlo/sensitivity/solve_for). Optics
  transmission modes `spectral_file`/`telescope_plus_filters`/
  `key_elements` and stray-light `spectral_file` now actually consume
  their `optics_config` injections (previously these schema-selectable
  modes raised unconditionally); injected curves are resampled onto the
  chain grid with a loud out-of-coverage error.

### Changed
- `optics.transmission_input_mode`, `optics.wfe_mode`, and
  `optics.stray.input_mode` now validate against explicit enum values
  (Gap 68). The always-raising modes `opd_map` (no pupil-phase
  representation in v1) and `pst_file` (needs a scene radiance
  distribution v1 lacks) are no longer offered — setting them now fails
  at `params.set`/resolve with the allowed list instead of deep in the
  optics stage.

### Added
- Metric metadata contract (Gap 71): every computed metric now carries a
  non-empty unit, description, and kind via the reconciled metric
  registry; new `ChainResult.metric_records()` returns unit-labelled
  `MetricRecord` tuples, and `radiant.performance.metric_info(name)`
  exposes single-metric metadata. `MetricSpec` gains
  `unit`/`description`/`kind`/`requires_mtf_terms` fields.

### Removed
- Metric registry phantoms (CU-078): the never-computed registry
  entries `nedt`, `nedl`, `nedr`, `csnr`, `ee`, `edge_slope`,
  `detection_range`, `saturation_margin`, `dynamic_range` are gone;
  the catalog now registers exactly the 32 keys the performance stage
  computes (real keys: `nedt_K`, `ee_1x1`/`ee_3x3`,
  `well_margin_dB`/`adc_margin_dB`, `dynamic_range_dB`, …).
  NEΔL/NEΔρ/edge-slope/detection-range specs return with the commits
  that compute them (Gaps 77/78). Reconciliation is CI-enforced.

### Added
- Persistence (Gap 67): `Sensor.save(path)` / `Sensor.load(path)` —
  YAML round trip of explicit inputs, tolerance distributions, and
  `wavelength_points` via a new `_radiant` config metadata block
  (`RADIANT_Config_Format.md` §1.7); reloading reproduces the original
  resolution and provenance exactly. `ChainResult.save(path)` /
  `ChainResult.load(path)` — single-file zip archive (JSON manifest +
  npz arrays) holding the full ChainState with dtype-preserving,
  full-fidelity reload and the provenance record frozen at save time.
  Supporting public surface: `ParameterSet.inputs()`,
  `radiant.io.config.read_radiant_meta()`, `save_config(scope=)`,
  `radiant.io.serialization` (`ResultArchiveError`,
  `UnserializedValue`).
- Public schema-introspection API (Gap 70): `ParameterSet.parameter_defs()`,
  `parameter_def(name)`, `consistency_groups()`, `tolerances()`,
  `is_resolved`, and `copy()`, plus `Sensor.parameter_defs()` /
  `Sensor.parameter_def(dotpath)` passthroughs. GUIs/CLIs/sweep tooling
  can now enumerate the full parameter schema (dtype, units, bounds,
  enums, defaults, descriptions, tags) without touching private state;
  all framework consumers migrated off the `_defs`/`_groups`/`_inputs`/
  `_tolerances`/`_resolved_flag` privates. Side effect: sweep- and
  sensitivity-cloned ParameterSets now carry loaded-file provenance
  records (previously dropped by the private clone path).

### Fixed
- **CU-065 (deck-side):** `render_tape5` now converts RADIANT's
  lower-endpoint path zenith to MODTRAN's Card 3 ANGLE-at-H1
  convention: downlooking decks render `180° − zenith` (a nadir
  space sensor renders ANGLE = 180, previously 0), uplooking decks
  are unchanged. Matches `modtran_run_matrix.csv`'s hand-worked
  `modtran_angle_at_h1_deg` column for every ITYPE=2 row; the
  rendered decks in `modtran/decks/` (regenerable) are what a real
  MODTRAN run will consume. No computed chain result changes (no
  binary has ever run), but downlooking tape5 decks — and therefore
  their SHA-256 cache keys — differ from pre-fix renders. CU-065's
  remaining residue: confirm the convention against the MODTRAN
  manual on access.

### Added
- `atmosphere.modtran.tape7_sun_path` (CU-011, file flavor): optional
  sun-leg tape7 for the Option C two-leg split. When set (requires
  `tape7_path`), `tau_sun` comes from the sun-leg file's transmittance
  instead of aliasing the up-leg value, the single-τ collapse
  `UserWarning` is not emitted, and the assembly's direct-solar term
  consumes the split. Unset, behavior is unchanged (alias + warning).
  The binary-invocation two-run flavor and real-MODTRAN physics parity
  remain deferred under CU-011.
- `atmosphere.modtran.tape7_path`: first-class MODTRAN tape7 file import.
  Setting it (with `atmosphere.model="modtran"`) builds the atmospheric
  state directly from a tape7 file produced elsewhere — parsed before
  chain execution (Rule 6), no MODTRAN binary, cache, or fallback
  involved. Replaces the manual side-door (Tape7Reader → temp CSVs →
  `atmosphere.model="tabulated"`) that every consumer hand-rolled;
  outputs are identical to that side-door (integration-tested to exact
  equality). Unset, the binary/cache/fallback behavior is unchanged.
  Like tabulated files, an imported tape7 is geometry-agnostic, and
  airborne targets (`h_tgt > 0`) are rejected. See
  `RADIANT_Atmosphere.md` §5.1.

### Changed
- **CU-066:** `Tape7Reader` now locates MODTRAN tape7 columns by their
  header label (left-to-right order of appearance), not a fixed token
  index. The prior positional mapping would have silently swapped
  `path_scattered_radiance` and `ground_reflected_radiance` with the
  wrong columns (THRML SCT / SURF EMIS instead of SOL SCAT / GRND
  RFLT) on real MODTRAN output, and could ingest numeric card-echo
  lines as spectral data. No shipped result is affected — no
  MODTRAN-derived value has ever been computed by RADIANT. Tape7
  files with no recognisable header now emit a `UserWarning` and use
  the old positional mapping as a documented fallback.
- **Results-affecting (NEDT, small):** exact band-integrated NEDT dS/dT
  (Gap 43). `SpectralIntegrationStage` now computes
  `dS/dT = ∫ (signal integrand)·(∂B/∂T)/B dλ` — the exact Planck
  log-derivative over the band — and `PerformanceStage` uses it (σ/(dS/dT))
  in place of the single-λ (band-center) Planck-factor approximation. The
  two agree **exactly** in the narrow-band limit; over a wide band NEDT
  shifts by the Planck band curvature: ~+0.3% / −0.2% for LWIR cells,
  ~+4.5% for a 3.5–5 µm MWIR band. No golden baseline asserted NEDT; the
  two pinned Option-C LWIR anchors were repinned with provenance. The
  single-λ form remains the fallback when no target temperature is set.

### Added
- `ParameterDef.required_unless` (Gap 66): a required parameter may now
  name an alternative that supersedes it — when the alternative is
  explicitly set, the requirement is waived and the parameter is left
  unresolved (never phantom-populated). First use: `detector.qe_value`
  is required unless `detector.qe_table_path` is set, so a spectral QE
  CSV now works WITHOUT also setting a meaningless scalar QE — the
  schema always documented the table as superseding the scalar, but the
  resolver rejected the config ("Required parameter 'detector.qe_value'
  is not set"); scenarios 1.1 and 1.2 both hit this and worked around
  it by band-averaging. The required-parameter error message now also
  names the superseding alternative when one exists.
- Saturation warnings (Gap 65, Rule 17): `ReadoutStage` now emits a
  `UserWarning` whenever the well-capacity or ADC saturation check clips
  the signal, naming the exceeded ceiling, the clipped value, and the
  remedies (integration time / gain / ADC bits / FWC). Previously both
  clips were silent outside `stage_outputs["readout"]["well_status"]` /
  `["adc_status"]`, which cost three scenarios (6.1, 6.2, 8.2) real
  debugging time on bit-identical "no effect" results. No computed
  values change — warning only.
- MODTRAN deck-builder fields, opt-in (CU-063/064/069): `ModtranConfig.visibility_km`
  (`float | None`, default `None` = IHAZE default) threads to Card 2 VIS;
  `ModtranConfig.itype` (`int`, default `2`) and `ModtranConfig.iemsct`
  (`int`, default `2`) thread to Card 1, adding ITYPE=3 (slant path to
  space) and IEMSCT=3 (solar/lunar irradiance mode). All defaults
  reproduce the pre-change tape5 deck byte-for-byte.
- Veiling-glare spatial halo, opt-in (Gap 60 partial): new parameters
  `optics.stray.veiling_glare_mtf` (int 0/1, default 0) and
  `optics.stray.halo_sigma_um` (default 50 µm). When enabled with
  `veiling_glare_fraction > 0`, the stray fraction is re-imaged as a
  Gaussian halo entering BOTH spatial paths (Rule 4): kernel
  `(1−vgf)·δ + vgf·G(σ)` on the `EffectivePSF` and the exact Fourier
  pair `(1−vgf) + vgf·exp(−2π²σ²f²)` on the MTF product
  (`mtf_stray_x/y`) — the low-frequency contrast-modulation loss the
  CU-062 radiometric pedestal cannot express. Default-off: existing
  results are bit-identical; enabling it is results-affecting for
  veiling-glare configs (MTF/RER/NIIRS drop toward the (1−vgf) floor).
  The 2-D PST/vendor-PSF import (`pst_file`) stays deferred
  (single-pixel scope decision).
- ROC / detection-probability model (scenario 6.4):
  `radiant.performance.roc` — `roc_curve` (P_d vs P_fa from a detection
  index / contrast SNR), `detection_probability` (`Q(Q⁻¹(P_fa)−SNR)`), and
  `roc_auc` (`Φ(SNR/√2)`) for the equal-variance Gaussian model. New error
  class `RocError`. No chain change.
- Multi-frame persistence sequence (scenario 2.4):
  `radiant.detector.persistence_sequence` — `persistence_residual_e` /
  `persistence_residual_sequence_e` (residual ghost signal
  `prior·f·exp(−(n−1)Δt/τ)` over a frame sequence) and `frames_to_clear`
  (frames until the residual drops below one LSB). Extends the existing
  single-frame `persistence_noise` term to the temporal domain. New error
  class `PersistenceSequenceError`. No chain change.
- Temperature retrieval + emissivity/temperature Jacobian (scenario 6.5):
  `radiant.performance.temperature_retrieval` — `retrieve_temperature_K`
  (invert a measured band radiance for surface T given an assumed ε, via
  Brent), `band_planck_radiance`, and the Jacobians `emissivity_jacobian`
  (∂L/∂ε = B̄(T)) and `temperature_jacobian` (∂L/∂T = ε·∫dB/dT). New error
  class `TemperatureRetrievalError`. Analysis model — no chain change.

### Added
- `geometry.solar_illumination` day/night toggle (Gap 59): `night` removes
  the solar terms for reflective/mixed (T2/T3) targets (`theta_s = None` —
  no direct-solar reflection, no single-scatter solar sky) while thermal
  self-emission and reflected thermal downwelling remain. Previously the
  `solar_zenith_rad` schema default (0.5 rad) gave every T2/T3 scene a
  phantom daytime sun and night was inexpressible. The `day` default
  preserves every existing configuration bit-for-bit.
- Spectral GroundBackground ε_g(λ) (CU-008): two new parameters give the
  sub-pixel/point-source background a spectral emissivity surface —
  `source.background.material` (a named `radiant.data.SpectralLibrary`
  entry: vegetation_green, snow, soil_dry, asphalt, … ; default `grey`
  keeps the exact scalar back-compat path) and
  `source.background.emissivity_path` (measured two-column CSV; wins over
  material). Resolution happens in the API layer pre-chain (Rule 6) and is
  injected via `stage_outputs["source_config"]["background_emissivity"]`.
  The Stage-2 "grey placeholder" `UserWarning` is removed — grey is now an
  explicit choice, and all existing sub-pixel configs are numerically
  unchanged. Unknown material names are rejected with the legal
  vocabulary.
- `source.lab_test_mode` parameter (Gap 40): positive `dark`/`lit`
  assertion for the ground_test/lab_test sub-cases. `dark` declares a
  no-external-illumination configuration (the D-lab dark-cal sub-mode) and
  is validated — a user-set `source.target.reflectance` contradicts it and
  is rejected with an actionable error; `lit` is a recorded assertion;
  the empty-string default is unasserted and preserves every existing
  config byte-for-byte.
- Stage-scoped error classes (CU-043, Rule 15): every stage package now
  exposes a `<Stage>ValidationError(RadiantError, ValueError)` — plus
  `CoreStateError`, `AtmosphereStateError`, and
  `SpectralIntegrationStateError` co-inheriting `RuntimeError` — in its
  `errors.py` (`CoreValidationError`/`CoreStateError` live in
  `core/exceptions.py`). All 428 bare `raise ValueError`/`RuntimeError`
  sites across core, the eight physics stages, and `api/` were migrated to
  these classes, so `except RadiantError` now catches every framework
  rejection. **No behavioral change for existing code**: the classes
  co-inherit their historical built-in type (the sanctioned Rule 15
  back-compat carve-out), so `except ValueError` /
  `pytest.raises(ValueError)` call sites keep working unchanged. A
  regression guard (`tests/test_exceptions.py::TestNoBareBuiltinRaises`)
  forbids new bare built-in raises.

### Changed
- **Results-affecting (PSF-path spatial metrics; small):** the
  pixel-aperture rect kernel is now sampled by exact area overlap
  (anti-aliased edges) instead of a binary inside/outside mask (CU-003
  option a). The binary mask quantised the rect width to the PSF sample
  grid, over- or under-blurring by up to half a sample; MTF-at-Nyquist,
  RER, and EE shift by a few percent in configurations where the grid did
  not divide the pitch (Option-C anchors: Cell 28 MTF@Ny +5.6%, Cell 58
  +7.9% — repinned with provenance). FFT-vs-analytic-sinc agreement
  improves ~13× (4.5e-2 → 3.6e-3 at Nyquist, worst config); the worst
  full-chain dual-path residual drops from ~5.8e-2 to ~1e-2. Radiometric
  goldens (signal/noise/SNR) are unaffected.
- Dual-path consistency default tolerance tightened 5e-2 → 2e-2 (CU-045):
  ~2× margin over the worst measured full-chain residual after CU-003.
  The check remains warn-only by design — it is a diagnostic invariant,
  and raising would abort runs whose physics is otherwise valid.
- **Results-affecting (non-default atmosphere profiles; large in
  water-sensitive bands):** the `atmosphere.standard_atmosphere` preset now
  carries its standard water column (Gap 57). When
  `precipitable_water_cm` is left at its schema default, the simple-model
  loader substitutes the profile's McClatchey/MODTRAN column
  (tropical 4.11 cm, midlat_summer 2.92, midlat_winter 0.85,
  subarctic_summer 2.08, subarctic_winter 0.42; us_standard stays 1.4) —
  previously "tropical" silently ran US-standard humidity. An explicitly
  set `precipitable_water_cm` always wins (provenance-based). Configs
  using a non-default profile without explicit PWV shift: the
  `mwir_leo_minimal` golden (midlat_summer) drops 52% in signal / 31% in
  SNR (more water → less MWIR transmission; regenerated via
  `update_golden.py` with the §5.3 protocol), and the Cell-28 LWIR anchor
  repins NEDT +0.9% / L@8µm −34%. Default-everything (us_standard)
  configs are bit-identical.

### Fixed
- **Results-affecting (defocused configs; moderate):** defocus is now
  unified as pupil Zernike Z4 on BOTH spatial paths (CU-058, Rule 4). The
  PSF path previously applied a Gaussian kernel (σ = |δ|/(4·f/#·√3)) while
  the MTF product path folded Z4 into the pupil — and, when scalar-RMS WFE
  was combined with defocus, discarded the RMS screen entirely, so any such
  config structurally failed the dual-path consistency check (scenario 7.3:
  max_err 0.169 vs tol 0.05). Now `_add_defocus_to_wfe` preserves the
  scalar-RMS screen (screen + Z4 in one pupil phase), the fold happens once
  before both paths, and the former Gaussian defocus kernel — plus the
  `optics.defocus` module (`defocus_kernel_2d`, `defocus_sigma_m`) and the
  `defocus_sigma_m` stage output — are removed. PSF-path spatial metrics for
  defocused systems change (Gaussian → true Z4 defocus OTF, ~few % at
  moderate defocus); configs with `defocus_um = 0` (all goldens) are
  unchanged. Also fixes a latent reference-wavelength bug: the folded Z4 is
  now rescaled to the WFE's reference wavelength, so the defocus OPD is
  correct when `reference_wavelength_um` differs from band center. All three
  pupil-phase dispatch sites now share one builder
  (`pupil_phase.make_pupil_phase_for_wfe`).
- Saturated `contrast_snr` is now flagged, not reported silently (CU-061).
  When the pixel saturates the readout caps the signal (and its shot noise)
  at full well but the contrast ΔS is not re-derived from the clipped
  signals, so `contrast_snr = ΔS/σ` was inflated and unreliable.
  `compute_contrast_snr` now detects the clip (`signal_e_final < signal_e`),
  emits a `UserWarning`, and sets `failure_reason` on the `contrast_snr_result`
  (so `.ok` is False). The metric value is unchanged for unsaturated runs
  (no golden impact); only the flag/warning are new.
- **Results-affecting (stray light / noise; large where used):** veiling-glare
  stray light (`optics.stray.input_mode = veiling_glare`) was effectively
  inert (CU-062). `OpticsStage` scaled the in-FOV image-plane irradiance by
  the pixel IFOV solid angle `Ω_pixel = pitch²/focal²` instead of the f-cone
  solid angle `Ω_cone = A_collect/focal²`, under-counting stray by
  `A_collect/A_pixel ≈ (D/pitch)²·π/4` (~10⁷–10⁸) so any `veiling_glare_fraction`
  produced ~zero stray. Now `stray_e = vgf × signal_e` for a uniform extended
  scene. Only affects runs using `veiling_glare` mode with a non-zero fraction
  (default 0.0 → no change; goldens unaffected); such runs gain the correct
  stray-light shot-noise penalty (lower SNR/NIIRS). `absolute_irradiance` and
  `spectral_file` modes were already correct.

### Changed
- Lab/ground-test scenarios reachable from the config surface (Gap 42):
  `source.no_atmosphere_subcase` ∈ {`ground_test`, `lab_test`} now builds a
  grey-body chamber/test-range background `L_bg(λ) = ε_bg·B(λ, T_bg)` from
  `source.background.temperature`/`.emissivity` (which Decision #15 makes
  valid for the no-atmosphere sub-cases) instead of raising and requiring a
  manual `UserSpectralBackground` injection. Warns if the chamber
  temperature is left at the schema default (Rule 17). A measured `L_bg(λ)`
  can still be injected directly. **Behaviour change:** these sub-cases
  previously raised `ParameterBoundsError` at inference; they now run. No
  golden change (no golden used these sub-cases).

### Added
- Spectral target emissivity input (Gap 47): new parameter
  `source.target.emissivity_path` — a 2-column `(wavelength_um, emissivity)`
  CSV. When set, the source inferrer builds the thermal descriptor with a
  spectral ε(λ) (`L_t(λ) = ε(λ)·B(λ, source.target.temperature)`) instead of
  a grey scalar, reusing the existing `SpectralData` emissivity that
  `T1Thermal`/`T3Mixed` already accept. Mutually exclusive with the scalar
  `source.target.emissivity` and every reflective / radiance /
  brightness-temperature surface (raises `ParameterBoundsError`). Opt-in;
  goldens unchanged. Retires the S8 `user_radiance_path` workaround for
  spectral-emissivity thermal targets (scenario 4.3).
- Minimum resolvable temperature / contrast (Gap 53):
  `radiant.performance.minimum_resolvable` —
  `minimum_resolvable_temperature_K` (MRT = k·NETD/MTF_sys(f)) and
  `minimum_resolvable_contrast` (MRC = k·NEΔρ/MTF_sys(f)), the
  contrast-limited resolution metrics (k = 2.25 observer SNR default). New
  metric `mrt_at_nyquist_K` (additive; requires NEDT + MTF). New error
  class `MinimumResolvableError`. Companion to the sampling-limited Johnson
  model; consumed by scenario 3.5.
- Extended target-vs-background contrast (ADR-0005, Gap 52): new
  parameters `source.contrast_reference.temperature` and
  `source.contrast_reference.emissivity` make `contrast_snr` a true
  two-pixel spatial differential in the extended regime — `ΔS = S_target −
  S_reference`, combined noise `√(N_t² + N_ref²)` — which nulls at the
  radiance crossover. The reference is metric-only: it never enters the
  noise budget, so absolute SNR (and Decision #13's pinned anchors) are
  unchanged. Opt-in (`temperature = 0` disables it, the default), so no
  golden result moves. Supersedes the two-pixel-differencing workaround in
  scenarios 4.3/4.4. New error class n/a; explicitly distinct from the
  deprecated `source.background.*` (Decision #15).
- D*/NEP/NETD noise-spec converters (scenarios 6.1, 4.5 prerequisite):
  `performance/detectivity.py` (`nep_from_dstar`/`dstar_from_nep`,
  `D* = √(A·Δf)/NEP`), `performance/nep_electrons.py`
  (`nep_from_noise_electrons`/`noise_electrons_from_nep`,
  `NEP = σ_e·hc/(η·λ·t_int)`, plus `integrating_bandwidth_hz`), and
  `performance/nep_netd.py` (`netd_from_nep`/`nep_from_netd`,
  `NETD = NEP/(dP/dT)`). Standard radiometric definitions relating
  datasheet detector figures of merit to the chain's electron-domain
  noise. New error classes `DetectivityError`, `NepElectronsError`,
  `NepNetdError`. No chain change.
- QE temperature dependence (Gap 48): new parameters
  `detector.qe_temperature_coeff_per_K` and `detector.qe_temperature_ref_K`
  apply a linear QE(T) factor `1 + coeff·(T_det − T_ref)` to the scalar
  `qe_value` or the `qe_table_path` curve, folded in at the API layer.
  **Results-affecting only when `coeff ≠ 0`** (lower/higher QE shifts SNR
  and NEDT); the default `coeff = 0` is byte-identical (goldens intact).
  QE is clamped to [0, 1] with a `UserWarning` if the factor pushes it out
  of range (Rule 17).
- Spectral QE from a file (Gap 44): `detector.qe_table_path` — a
  schema-only parameter until now — is wired. When set, `RadiantSession`
  loads the wavelength-vs-QE CSV (`io.qe_csv`, Rule 6: file I/O in the api
  layer) onto the wavelength grid and applies it spectrally, superseding
  the scalar `detector.qe_value`; QE past the measured cutoff is zero.
  Absent a path, the scalar `qe_value` behaviour is unchanged (goldens
  intact).
- Arbitrary / measured pupil-mask injection (Gap 54): inject
  `optics_config["pupil_mask_override"]` (a `(pupil_npix, pupil_npix)`
  amplitude array) via `extra_stage_outputs` to supersede the parametric
  circular/obscuration/spider pupil — for segmented or non-circular
  apertures. Threaded through `make_pupil_amplitude` into both the PSF and
  MTF paths (Rule 4). No default-behavior change (absent ⇒ parametric
  mask; 504 optics + 10 golden tests unchanged).
- Detector figures of merit (Gap 45): `performance/dark_crossover_rate.py`
  (`dark_shot_crossover_rate_e_per_s` = σ_read²/t_int),
  `performance/blip_rate.py` (`blip_rate_e_per_s` = signal_e/t_int), and
  `performance/noise_equivalent_irradiance.py`
  (`noise_equivalent_irradiance_ph_s_cm2`). Standalone helpers for the
  detector cooler-budget/sensitivity trade; new error classes. No chain
  change.
- Radiometric-calibration analysis (Gap 46):
  `radiant.api.calibration_analysis` — `analyze_calibration` → a
  `CalibrationReport` (gain/offset fit, temperature & radiance
  responsivity, linearity residuals % full-scale, N-frame temperature
  uncertainty), plus the underlying `gain_offset_fit`,
  `linearity_residuals_pct_fs`, etc. New error `CalibrationAnalysisError`.
  Pure sweep-array analysis; no chain change.
- Repeat-ground-track & revisit model (Gap 51):
  `radiant.core.repeat_ground_track` — `nodal_regression_rate_deg_per_day`
  (J2 secular Ω̇), `sun_synchronous_inclination_deg`,
  `equatorial_ground_track_spacing_m`, and a first-order
  `revisit_interval_days`. New Earth constant `J2_earth`; new error class
  `RepeatGroundTrackError`. Standalone analysis model — no chain change.
- Diffraction-limited-resolution metrics (Gap 49):
  `diffraction_limit_angular_urad` (Rayleigh `1.22 λ_c / D`) and
  `diffraction_limit_ground_m` (projected to the slant range, companion to
  GSD) in the new `performance/diffraction_limit.py`. Analysis outputs
  only — no existing result changes.
- Sampling-regime flag (Gap 50): `sampling_regime_code` metric
  (0 detector-limited / 1 near-critical / 2 diffraction-limited, from
  `q_center`) in the new `performance/sampling_regime.py`. New error
  classes `DiffractionLimitError`, `SamplingRegimeError`. Additive
  metrics; goldens unchanged.
- Spider-vane / secondary-support struts (scenario 1.5 prerequisite):
  new optics parameters `optics.n_spiders`, `optics.spider_width_m`,
  `optics.spider_angle_deg` implement RADIANT_Optics.md §3.3 (previously
  aspirational). Struts enter the pupil amplitude mask
  (`make_pupil_amplitude` via the new `SpiderVaneSpec`), so they degrade
  **both** spatial paths (PSF and MTF) per Rule 4, and subtract from the
  radiometric clear area (`CircularAperture.clear_area_m2`).
  **Results-affecting only when `n_spiders > 0` and `spider_width_m > 0`**
  — lowers SNR (less collecting area), EE_box, and RER (diffraction
  spikes); the `strehl` metric is unaffected (vanes are common-mode in
  the WFE reference). Default (no struts) reproduces all existing results
  byte-for-byte (496 optics + 10 golden tests unchanged).
- Johnson-criteria DRI calculator (scenario 4.2 prerequisite):
  `radiant.performance.johnson_criteria` — `johnson_range_m`,
  `resolved_cycles`, and the standard `JOHNSON_N50` cycle table
  (detection/orientation/recognition/identification). Computes the range
  at which a discrimination task's N50 cycles are resolved across a
  target's critical dimension (`R = D / (2·IFOV·N50)`). Sampling-limited
  form (no MRT/MRC coupling). New error class `JohnsonCriteriaError`.
- Orbit-kinematics calculator (scenario 3.1 prerequisite):
  `radiant.core.orbit` — `orbital_velocity_m_s`, `orbital_period_s`, and
  `ground_track_speed_m_s` for a circular LEO altitude (two-body,
  spherical Earth, non-rotating ground track). Feeds the
  `ground_speed_m_s` input that `performance.access_rate` could not
  itself compute. New Earth gravitational-parameter constant
  `mu_earth_m3_s2` in `core.constants`; new error class `OrbitError`.
- Solar-geometry calculator (scenario 1.2 prerequisite):
  `radiant.core.solar_geometry` — `solar_zenith_angle_rad(latitude_deg,
  day_of_year, local_solar_time_hr)`, `solar_declination_deg`
  (Spencer's series), and `local_solar_time_from_ltan` for
  sun-synchronous orbits. Converts date/latitude/LTAN into the solar
  zenith angle for `geometry.solar_zenith_rad`. New error class
  `SolarGeometryError`.
- ASTER spectral-library import (scenario 1.3 prerequisite):
  `radiant.io.aster_library.load_aster_spectrum` parses JPL/NASA ASTER
  library text files (metadata header + wavelength/reflectance columns,
  descending order handled) into an `AsterSpectrum` with `emissivity()`
  (ε = 1 − ρ, opaque scene material) and `band_averaged_emissivity()`.
  New error class `AsterLibraryError`. No extrapolation outside the
  measured range.
- Batch matrix execution (scenario 4.1 prerequisite):
  `radiant.api.batch.BatchRunner` — the `BatchRunner` named in the
  architecture's api layout — runs one evaluation per cell of a labeled
  cartesian grid (targets × atmospheres × sensors), with per-cell
  parameter overrides and Rule 17 failure capture (a failed cell is a
  recorded `error` row, never silently dropped). Returns a `BatchResult`
  with a `pivot()` helper. New error class `BatchRunnerError`.
- Target-library import (scenario 4.1 prerequisite):
  `radiant.io.target_library.load_target_library` reads a mission target
  list workbook into validated `TargetEntry` objects with derived
  `projected_area_m2`; lazy openpyxl (actionable error naming the
  `[scenarios]` extra). New error class `TargetLibraryError`.
- Vendor detector-datasheet importers (scenario 2.1 prerequisites):
  `radiant.io.qe_csv.load_qe_csv` reads wavelength-vs-QE vendor CSVs
  (nm/µm × percent/fraction, header-token or explicit unit resolution)
  into a canonical-units `QeCurve` with grid evaluation and band
  averaging; `radiant.io.dark_current_csv.load_dark_current_csv` reads
  `T_K, Jdark_A_cm2` curves into a `DarkCurrentCurve` with
  Arrhenius-faithful interpolation (ln J linear in 1/T),
  `dark_rate_e_per_s(T, pixel_pitch_m=)` conversion (J·A_pixel/q), and
  the inverse `temperature_at_rate`. New error classes `QeCsvParseError`
  and `DarkCurrentCsvParseError` (both `RadiantError`). Neither loader
  extrapolates outside the measured range by default.

### Fixed
- Scatter (Gap 31) and defocus (Gap 29) kernel sizing crashed with
  `ValueError: npix must be a positive odd integer, got 256` whenever
  the 6σ kernel span exceeded the PSF grid — the odd-forcing happened
  before the cap to the (even) grid size. The cap now clamps to the
  largest odd size within the grid. Fine-spacing configurations (VNIR
  band, small pixels) with `optics.surface_roughness_nm` or large
  `optics.defocus_um` now run; no numeric change for configurations
  that previously ran. Found by the scenario 7.3 refresh.

### Deprecated
- `optics.cold_stop_efficiency` renamed to `optics.nearfield_fraction`
  (Gap 12) — the old name inverted the vendor convention ("100%
  efficient cold stop" = complete blocking, but η=1 here means *no*
  cold stop). Same semantics, no numeric change:
  `nearfield_fraction = 1 − vendor_cold_stop_efficiency`. The old name
  still works via a new parameter-alias mechanism
  (`ParameterDef.deprecated_aliases`) with a `DeprecationWarning`, and
  will be removed in a future release.

### Fixed
- **Results-affecting (labels/exports only):** the MTF product-path
  frequency grid `ChainState.spatial_freq_cycles_per_mrad` (and
  `MTFBudgetResult.freq_cycles_per_mrad`) stored values 1e6× true
  cycles/mrad (conversion used `× f·1e3` instead of `× f·1e-3`). All
  internal consumers round-tripped with the same inverse factor, so
  MTF curves, metrics, and golden results are unchanged — but the grid
  values themselves and the cycles/mrad axis of `result.plot.mtf()`
  now read correctly (e.g. 33.3 cy/mrad at Nyquist for an 18 µm pixel
  at f = 1.2 m, previously 3.33e7). Found during Gap 27.

### Added
- `scenarios` optional-dependency group (`pip install -e ".[scenarios]"`):
  openpyxl + matplotlib, required by the scenario run scripts (CU-057).
- Zemax Zernike importer (Gap 26): `radiant.io.zemax_zernike.
  load_zemax_zernike` parses "Zernike Standard Coefficients" text
  exports (Noll-indexed waves, UTF-8/UTF-16 tolerant) into the existing
  Zernike WFE pipeline via `ZemaxZernikeResult.to_wavefront_error()`.
- Measurement import + comparison (Gap 30):
  `radiant.io.measurement.load_measured_curve` (CSV → `MeasuredCurve`)
  and `radiant.api.compare.compare_mtf` (unit-aware measured-vs-predicted
  MTF residuals, overlap-only interpolation). Excel import out of scope
  (CSV export required).
- Surface-roughness scatter (Gap 31): new `optics.surface_roughness_nm`
  and `optics.scatter_halo_sigma_um` parameters drive a TIS model
  (`optics/scatter.py`): TIS = 1 − exp(−(4πσ/λ)²), scattered fraction
  into a Gaussian halo. **Results-affecting only when roughness is set
  nonzero** — lowers MTF/RER at all frequencies via both spatial paths
  (Rule 4 Fourier pair); default 0 preserves all results.
- MTF budget reporting (Gap 19): `MTFBudgetResult.table()` and
  `plot_mtf_budget` / `ResultPlotNamespace.mtf_budget()` — human-facing
  views over the existing per-contributor MTF-at-Nyquist decomposition.
- `Sensor.solve_for(param, target, bounds=, metric=)` (Gap 10): inverse
  solver — Brent root-finding for the parameter value that hits a target
  metric, replacing sweep-and-interpolate. New `api/solve.py` module,
  `SolveResult` exported from `radiant.api`.
- `ErrorBudget` / `BudgetContributor` (Gaps 23+28): generic RSS error
  budget with allocation tracking, headroom queries, budget table, and
  dict round-trip — one model for jitter (µrad) and WFE (waves)
  budgets. Exported from `radiant.api`.
- Unit-aware parameter input (Gap 6): `ParameterSet.set(name, value,
  unit=...)` and `Sensor.set(dotpath, value, unit=...)` convert from the
  caller's native unit (cm, ms, %, min, …) at the set boundary. Bounds
  validated after conversion; original value+unit recorded in
  provenance. Omitting `unit=` keeps historical input-unit behavior —
  no result changes.
- `convert_spatial_frequency()` (Gap 27): cy/m ↔ cy/mm ↔ cy/mrad ↔
  cy/pixel conversion utility in the new
  `performance/frequency_units.py` module.
- PSF weighting spectrum override (Gap 17): `RadiantSession.run` gains an
  `extra_stage_outputs` injection argument;
  `optics_config["psf_weighting_spectrum"]` (SpectralData) decouples
  polychromatic PSF weighting from the scene spectrum. Radiometry is
  unaffected; weighting provenance recorded in
  `stage_outputs["optics"]["psf_weighting_source"]`. No default-behavior
  change.
- Electronics MTF (Gap 32): new `readout.electronics_sigma_um` parameter
  (default 0.0 = ideal electronics, no result change) models readout
  amplifier bandwidth as a Gaussian blur along the readout (x) axis.
  **Results-affecting only when set nonzero** — enters both the
  EffectivePSF and the MTF product per Rule 4, lowering x-axis MTF,
  RER, and NIIRS. New `readout/electronics_mtf.py` module and
  `mtf_electronics_x/_y` product terms.
- `giqe5_sensitivity()` (Gap 20): analytic d(NIIRS)/d(GSD, RER, SNR, H, G)
  partials and exact per-+1% deltas in the new
  `performance/giqe_sensitivity.py` module. Analysis utility only — no
  chain output changes.
- GIQE-5 calibration-range flagging (Gap 22): NIIRS results outside the
  published fit ranges (GSD 3–80 cm, RER 0.2–0.95, SNR 2–130) now carry
  `GIQEResult.extrapolated=True`, a `UserWarning`, and a new
  `niirs_extrapolated` metric (0.0/1.0). The NIIRS value itself is
  unchanged — flagging only. The prior ad-hoc low-end checks (SNR < 5,
  RER < 0.2) are replaced by the spec-based ranges, both ends.
- `optics.scalar_emissivity` parameter (default 0.0): declared effective
  emissivity of the lumped train in scalar transmission mode, enabling
  warm-optics nearfield emission from the simplest input mode (Gap 37).
  **Results-affecting only when set nonzero** — it adds nearfield background
  and shot noise (lower SNR, higher NEDT) for warm-optics MWIR/LWIR
  configurations; the default preserves all existing results (`ε = 0`,
  nearfield dark). `OpticalElement` gains a `declared_emissivity` field,
  legal only on `kind=LUMPED` pseudo-elements; `KirchhoffViolationError`
  on physical surfaces or when `ε + τ + R > 1`.

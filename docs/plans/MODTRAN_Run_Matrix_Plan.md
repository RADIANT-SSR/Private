# MODTRAN Run Matrix — Acquisition and Integration Plan

**Status:** Draft
**Owner:** Jason Forsyth
**Created:** 2026-07-10
**Companion artifact:** [`modtran_run_matrix.csv`](modtran_run_matrix.csv) — the machine-readable run list this document explains.

---

## 1. Purpose

RADIANT has a complete MODTRAN interface (`src/radiant/atmosphere/modtran.py`: tape5 deck
builder, `Tape7Reader`, SHA-256-keyed cache) but **no real MODTRAN output has ever passed
through it** — every parser test uses synthetic fixtures, `tests/integration/fixtures/` is
empty, and all 35 scenarios run on `SimpleAtmosphere` (parametric) or `exo` (vacuum).

Five tracked items are gated on MODTRAN access, and their deferral records name "donated
tape7 fixtures" as an acceptable gate-opener:

| Item | What it needs |
|------|---------------|
| Gap 39 / CU-011 gating family | Reference τ(h_tgt, θ_o) for the A3 partial-column two-run differential |
| CU-011 | Independent τ_sun vs τ_up to validate the two-leg split in the MODTRAN backend |
| Gap 38 | ω₀(λ, aerosol) reference for `E_sky_scattered` fidelity |
| Scenario 1.1 (empty stub) | Maritime-aerosol MWIR atmosphere |
| Scenario 6.2 (empty stub) | MODTRAN-vs-SimpleAtmosphere intercomparison data |

Additionally, several implemented scenarios carry SimpleAtmosphere anchors unpinned against
any external reference (3.2 visibility/PWV sweep, 3.4 off-nadir transmittance, 3.5 tropical,
4.1 profile matrix, 4.4's explicit "MODTRAN would change absolute signals" remark), and the
just-landed Gap 57 `PROFILE_PWV_CM` table has no MODTRAN-side confirmation.

This plan defines the **minimum set of MODTRAN runs** (39 total; 33 core, 6 optional) that
unblocks all of the above, plus the subset that ships with the package as a nominal
atmosphere library.

## 2. Why the matrix is small

One MODTRAN run at 700–25,000 cm⁻¹ (0.4–14.3 µm) covers VNIR through LWIR in a single
tape7, so the matrix spans only **geometry × profile × aerosol/water** — never band.
The run blocks are chosen so each tape7 serves multiple consumers (development reference,
committed test fixture, and shipped interpolation node).

## 3. Conventions (read before running)

All runs unless a CSV cell overrides:

- **Spectral:** V1 = 700 cm⁻¹, V2 = 25,000 cm⁻¹, DV = FWHM = 1.0 cm⁻¹ (triangular slit).
- **Mode:** ITYPE = 2 (slant H1→H2), IEMSCT = 2 (thermal + solar radiance), IMULT = 1
  (multiple scattering). Block E uses IEMSCT = 3 (solar irradiance) with the flux table for
  the diffuse component.
- **Surface:** SURREF = 0.0 — pure-atmosphere quantities; RADIANT applies target/background
  reflectance itself. (Diffuse sky irradiance depends weakly on ground albedo under
  IMULT = 1; albedo 0 is the convention for these tables and must be recorded in the
  manifest.)
- **Solar geometry:** IPARM = 2; solar azimuth 0°; solar zenith 30° except where the run
  varies it.
- **Angle convention — important:** the CSV carries two columns.
  `path_zenith_deg_radiant` is RADIANT's LOS zenith (0° = nadir-looking sensor).
  `modtran_angle_at_h1_deg` is what goes on **Card 3** — MODTRAN measures ANGLE from zenith
  *at H1 (the sensor)*, so a down-looking path is `180 − θ_RADIANT` (nadir = 180°).
  Use the Card-3 column when building decks by hand. See §6 finding PW-3.
- **Archive per run:** tape7 **and** the rendered tape5 **and** the MODTRAN version/band-model
  identifiers. The RADIANT cache is keyed on the SHA-256 of the deck, and Rule 26 requires
  every committed artifact to name its generator in a manifest.

## 4. Run blocks

| Block | Runs | Configuration theme | Primary consumers |
|-------|------|--------------------|-------------------|
| A — Profile baselines | A1–A6 | Space (100 km) → ground, nadir, rural/23 km, one run per standard profile | `Tape7Reader` first-real-data validation; Gap 57 PWV anchors; SimpleAtmosphere per-profile τ/L_path parity; scenario 6.2 backbone; 4.1 profile cells |
| B — Zenith fan | B1–B3 | us_standard full column at θ = 30/45/60° (A1 supplies 0°) | CU-011 two-leg split (these double as sun-leg τ at θ_s); airmass-scaling parity; scenario 3.4 |
| C — Partial column | C1–C7 | midlat_summer, sensor 35 km, target 0/1/5/10/20/29 km + one 45° point | Gap 39 (the exact Table C / Cell 43 configuration in `tests/integration/test_table_c_cells.py`); the `ModtranAtmosphere.evaluate` two-run-differential extension |
| D — Aerosol & water | D1–D6 | Full column, nadir: rural/5 km, maritime/23 km, urban/5 km, H₂O ×0.5, ×2.0, (opt) tropospheric/50 km | Scenario 3.2 visibility + PWV axes; 4.1 weather cells; 1.1 maritime; Gap 38 aerosol variation in scattered path radiance |
| E — Sky irradiance | E1–E4 | Ground-level direct + diffuse solar irradiance: rural θ_s 30/60°, maritime, urban/5 km | Gap 38 ω₀(λ, aerosol); Gap 59 day/night anchor |
| F — Airborne sensor | F1–F3 | 3 km → ground (tropical; midlat_summer), (opt) 5 km at 75° maritime | Scenarios 3.5, 4.3, 4.4 (absolute-signal claim check), (opt) 4.2 horizon path |
| G — Space-sensor partial column | G1–G6 | midlat_summer, sensor 100 km (= LEO/GEO, see below), target 1/5/10/20/29 km + (opt) one 45° point; h_tgt = 0 anchor is A3 | LEO/GEO sensors viewing airborne targets; Gap 39 space-sensor branch; cross-ladder consistency check against Block C |
| H — Thermal downwelling | H1–H4 | Ground looking up (H1 = 0, H2 = 100 km), IEMSCT = 2: us_standard at 0°/48.2°/(opt) 70°, tropical at 48.2° | `E_sky_thermal` parity — the only chain quantity no down-looking run measures; LWIR sky-reflected term on low-ε targets; scenario 3.5 |

**LEO/GEO note (Block G).** MODTRAN's model atmosphere ends at 100 km, so a sensor at
LEO (500 km) or GEO (35,786 km) at the same LOS zenith sees the **identical** column as
H1 = 100 km — the extra path is vacuum. One ladder at H1 = 100 km therefore serves every
sensor altitude above TOA; no separate LEO and GEO runs exist or are needed.

**Cross-ladder consistency identity.** At nadir, transmittance is multiplicative along the
path: τ(100→h) = τ(100→35) · τ(35→h). Blocks C and G therefore validate each other —
the ratio τ_G(h)/τ_C(h) must be constant (= τ of the 35–100 km column) across all five
shared target altitudes. This is a free integration test requiring no extra runs.

Full per-run parameters: [`modtran_run_matrix.csv`](modtran_run_matrix.csv).

### Chain-coverage traceability

The chain consumes seven spectral arrays (`AtmosphericQuantities`,
`src/radiant/atmosphere/_quantities.py`). Every one must be derivable from the matrix:

| Chain quantity | Source in the matrix |
|----------------|----------------------|
| `tau_up` (target→sensor) | Total-transmittance column of the run matching the path; C/G ladders for airborne targets |
| `tau_full_up` (ground→sensor) | Full-column runs (A-block, C1) paired with the ladders |
| `tau_sun` (sun→target) | B-block zenith fan as sun-leg τ at θ_s (ground targets); C7/G6 validate the θ×h_tgt coupling for airborne targets |
| `L_path_up`, `L_path_full` | Thermal + scattered path-radiance columns, archived on every IEMSCT=2 run |
| `E_TOA` | **Not from MODTRAN** — `radiant.core.solar` (AM0 CSV in `data/solar/`) |
| `E_sky_scattered` | Block E (direct + diffuse solar irradiance at ground) |
| `E_sky_thermal` | Block H (up-looking thermal sky radiance; π·L_sky at the 48.2° diffusivity angle approximates the hemispheric flux) |

Known thin spots, accepted for a minimum set: airborne-target `tau_sun` and sky irradiance
*at altitude* are point-validated (C7, G6), not gridded — the validated partial-column
model generalizes them; and `E_sky_scattered`/`E_sky_thermal` reference data are
ground-level only.

### CSV data dictionary

| Column | Meaning |
|--------|---------|
| `run_id`, `block`, `priority` | Identifier; block letter; `core` or `optional` |
| `deck_builder_support` | `current` = expressible with today's `ModtranConfig`; otherwise names the required extension (§6) |
| `purpose`, `unblocks` | One-line description; gaps/CUs/scenarios the run serves |
| `profile`/`modtran_model`, `aerosol`/`ihaze` | RADIANT name and the MODTRAN card value (MODEL 1–6, IHAZE) |
| `vis_km` | Intended visibility [km]; 23 = IHAZE default (expressible today as VIS = 0.000) |
| `h2o_scale`, `o3_scale` | Column scaling factors (Card 2C, `g` suffix) |
| `surface_albedo_surref` | SURREF; 0.0 everywhere by convention |
| `h1_sensor_km`, `h2_target_km` | Card 3 altitudes [km] |
| `path_zenith_deg_radiant`, `modtran_angle_at_h1_deg` | Both angle conventions (§3); blank RADIANT angle on Block E = sun-pointing LOS |
| `solar_zenith_deg`, `solar_azimuth_deg` | Card 3A1 PARM1/PARM2 [deg] |
| `itype`, `iemsct`, `imult` | Card 1 mode flags |
| `v1_cm1`, `v2_cm1`, `dv_cm1`, `fwhm_cm1`, `band_um` | Spectral window and resolution |
| `outputs_needed` | tape7 columns (or irradiance products) that must be archived |
| `destination` | `test_fixture` (committed golden), `shipped_library` (nominal NPZ node), `dev_only` (cache/archive, gitignored) |

## 5. Batching by readiness

**Status update 2026-07-10:** PW-1 and PW-2 are resolved (CU-063, CU-064, CU-069 — the
ITYPE gap CU-064 didn't originally cover). All 39 decks are now expressible with
`ModtranConfig` and pre-rendered under `modtran/decks/` (regenerate with
`scripts/render_modtran_decks.py`; see that directory's README for what's committed vs.
regenerate-on-demand). The batching below is preserved as a historical readiness record;
it no longer gates deck rendering, only MODTRAN *execution*, which is still unblocked
only by binary/tape7 access.

| Batch | Runs | Precondition (historical) |
|-------|------|--------------|
| 1 | A1–A6, B1–B3, C1–C7, D2, D4, D5, F1, F2, G1–G5, H1, H2, H4 (29 runs) | None — expressible with the current deck builder (H runs are up-looking, so PW-3 is not in play). Highest value: unblocks Gap 39, CU-011, scenario 6.2, Gap 57 anchors, and the E_sky_thermal anchor in one sitting. |
| 2 | D1, D3, D6, F3 (4 runs) | PW-1 (VIS field) for the D runs — **resolved** (CU-063); F3 needs only a refraction sanity check. |
| 3 | E1–E4 (4 runs) | PW-2 (irradiance mode) — **resolved** (CU-064); E4 also needed PW-1 — **resolved** (CU-063). ITYPE was also hardcoded for these rows, found and resolved as CU-069. |

## 6. Deck-builder pre-work (findings from this audit)

Three latent issues in `src/radiant/atmosphere/modtran.py` surfaced while assembling the
matrix, filed as CU-063/064/065 (Rule 21). A fourth (ITYPE, CU-069) and a fifth (Card 1's
stale field-name comment, CU-067) surfaced while implementing PW-2. Status as of
2026-07-10:

- **PW-1 — `ModtranConfig` has no visibility field.** Card 2 hardcoded `VIS 0.000`
  (IHAZE default), so degraded-visibility runs (D1, D3, D6, E4) could not be expressed.
  **Resolved as CU-063**: `visibility_km: float | None` threads to Card 2.
- **PW-2 — No solar-irradiance mode.** The deck builder emitted IEMSCT = 2 only; Block E
  needs IEMSCT = 3. **Resolved as CU-064** (`ModtranConfig.iemsct`) plus a follow-on,
  **CU-069**: ITYPE was also hardcoded to 2, but Block E's slant-to-space geometry needs
  ITYPE = 3 too — `ModtranConfig.itype` added alongside `iemsct`. The diffuse-flux
  option (IMULT) was already configurable via the existing `imult=1` default.
- **PW-3 — Card 3 ANGLE convention is suspect.** `render_tape5` writes RADIANT's
  `path_zenith_rad` directly as ANGLE, but MODTRAN measures ANGLE from zenith at H1
  (sensor): a nadir-looking space sensor needs ANGLE = 180°, not 0°. Never exercised (no
  binary has ever run), so it is a latent bug, not a regression. **Still open as CU-065**
  — needs the MODTRAN manual + a real run to verify. Every deck under `modtran/decks/`
  is generated with the RADIANT-convention angle and flagged in `MANIFEST.md` wherever
  it differs from the matrix's independently-worked-out `modtran_angle_at_h1_deg`
  column; verify before trusting `ANGLE` on any rendered deck.
- **CU-067 (found during CU-064)** — Card 1's inline field-name comment doesn't align
  index-for-index with its own tokens; the IEMSCT/ITYPE token positions used by CU-064/069
  were re-derived from `render_tape5`'s prose docstring instead. Deferred alongside PW-3.

## 7. Ship-with-package plan

Two artifacts, both strict subsets/repackagings of the runs above — **zero MODTRAN time
beyond the development set**.

### 7.1 Committed test fixtures (~10 tape7s)

A1, A3, B2, C1, C3, C7, D2, D5, E1, E2 → `tests/integration/fixtures/modtran/`, at full
1 cm⁻¹ resolution, each with its tape5 and a `MANIFEST.md` naming generator deck + MODTRAN
version (Rule 26: golden baselines that tests assert against). These permanently unblock
Gap 39 / CU-011 / Gap 38 regression testing for anyone without a MODTRAN license.

### 7.2 Nominal runtime library (`data/atmospheres/`)

Repackage 25 runs into the `InterpolatedAtmosphere` NPZ grid format
(`atmosphere.model = "interpolated"`, axes from `_GEOMETRY_FIELDS`; the format also
carries downwelling emission, which `InterpolatedAtmosphere` interpolates linearly):

- **Profile anchors:** A1–A6 (six standard atmospheres, nadir).
- **Zenith fan (us_standard):** A1 + B1–B3 (θ_o = 0/30/45/60°).
- **Altitude ladder, stratospheric sensor (midlat_summer, 35 km):** C1–C7 (h_tgt 0–29 km, + 45° point).
- **Altitude ladder, space sensor (midlat_summer, 100 km = LEO/GEO):** A3 + G1–G6 (h_tgt 0–29 km, + 45° point).
- **Thermal downwelling nodes:** H1, H2, H4 (us_standard 0°/48.2°, tropical 48.2°).

**Grid packaging for orbital sensor altitudes:** `InterpolatedAtmosphere` refuses to
extrapolate outside the convex hull of its nodes, so a grid whose sensor-altitude axis
tops out at 100 km would reject queries at 500 km or GEO. Duplicate the Block G states at
a second sensor-altitude node (e.g. 40,000 km) — interpolating between identical values is
exact and physically correct (the added path is vacuum), and every space sensor then falls
inside the hull. The alternative (clamping sensor altitude to TOA in the loader/adapter)
touches code; node duplication is data-only. Decide at implementation; record the choice
in the library manifest.

Shipped copies degraded to ~5 cm⁻¹ FWHM (band-integrating sensor metrics are insensitive;
keeps the library ≈ 10–20 MB) while test fixtures stay at 1 cm⁻¹. Aerosol/visibility
variants (Block D/E) deliberately do **not** ship — they are condition-specific studies,
regenerate-on-demand per the existing `data/atmospheres/README.md` philosophy.

**Rule 20 lock-step:** `data/atmospheres/README.md` currently claims pre-tabulation "would
require thousands of files" — written before `InterpolatedAtmosphere` (log-τ interpolation
over a structured grid) existed. The PR that lands the library must rewrite that README and
update `RADIANT_Atmosphere.md`.

## 8. Acceptance criteria

| Item | Done when |
|------|-----------|
| Tape7 parser validation | `Tape7Reader` round-trips ≥ 1 real tape7 (A1) with unit-conversion checks against hand-computed values at ≥ 3 wavelengths |
| Gap 39 | `ModtranAtmosphere.evaluate` two-run differential reproduces C2–C6 τ(h_tgt) within stated tolerance; `test_table_c_cells.py` gains MODTRAN-pinned assertions |
| CU-011 | Second tape7 invocation keyed on (h_tgt, θ_s); τ_sun from B-runs ≠ τ_up; cache key includes θ_s |
| Gap 38 | ω₀(λ) lookup (rural/maritime/urban) derived from E-runs; Cells 25/40/55 re-audited |
| E_sky_thermal parity | Simple-backend `(1−τ_down)·π·B(T_atm_eff)` compared against H-run sky radiance (us_standard and tropical); error characterized per band, tolerance decision recorded |
| Scenario 6.2 | Built from Block A: MODTRAN vs SimpleAtmosphere per profile, walkthrough + gui_workflow per scenario rules |
| Scenario 1.1 | Built using D2 (maritime) |
| Shipped library | §7.2 NPZ set loads via `atmosphere.model = "interpolated"`; README + docs updated in lock-step |

---

*When this plan completes, move it to `docs/archive/` with a HISTORICAL banner in the same
PR (Rule 24).*
